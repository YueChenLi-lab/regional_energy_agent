"""Provider and Agent protocol simulation only; no real service calls."""
import json
from pathlib import Path

import httpx
import pytest

from energy_agent.agent import EnergyAgent, revise_task
from energy_agent.conversation import (AgentSession, GroundedExplanation, current_facts,
                                       heat_fingerprint, validate_explanation)
from energy_agent.data import make_demo_task
from energy_agent.llm import LLMError, OpenAICompatibleClient, RequestBudget
from energy_agent.schemas import TaskPatch


def response(name,args,finish='tool_calls'):
    return {'choices':[{'finish_reason':finish,'message':{'content':None,'tool_calls':[{'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}}],
            'usage':{'prompt_tokens':123,'completion_tokens':30,'total_tokens':153,'unknown_secret':'test-key'}}


def model(handler,**kwargs):
    return OpenAICompatibleClient('https://api.deepseek.com','deepseek-flash','test-key',client=httpx.Client(transport=httpx.MockTransport(handler)),**kwargs)


def test_deepseek_non_thinking_protocol_has_no_undocumented_parallel_parameter():
    calls=[]
    def handler(req):
        calls.append(json.loads(req.content));return httpx.Response(200,json=response('propose_task_patch',{'budget_multiplier':0.8,'preserve_heat':True}))
    m=model(handler)
    p=m.parse_patch('预算减少20%，供热要求保持不变',make_demo_task(hours=4))
    assert p.budget_multiplier==0.8 and p.preserve_heat
    assert calls[0]['thinking']=={'type':'disabled'}
    assert calls[0]['tool_choice']['function']['name']=='propose_task_patch'
    assert 'parallel_tool_calls' not in calls[0]
    assert calls[0]['max_tokens']==1000
    assert 'strict' not in calls[0]['tools'][0]['function']
    assert '/beta' not in str(m._url)


@pytest.mark.parametrize('bad',[response('propose_task_patch',{},'length'),response('execute_shell',{}),{'choices':[]}])
def test_deepseek_truncated_empty_unknown_rejected(bad):
    m=model(lambda r:httpx.Response(200,json=bad))
    with pytest.raises(LLMError):m.parse_patch('预算减少20%',make_demo_task(hours=2))
    assert m.budget.count==3


def test_limits_http_retry_and_sanitized_persistent_log(tmp_path):
    seq=iter([429,503,200])
    m=model(lambda r:httpx.Response(next(seq),text='test-key private-response'),budget=RequestBudget(log_path=tmp_path/'calls.json'))
    with pytest.raises(LLMError,match='HTTP 503'):m.parse_patch('修改预算',make_demo_task(hours=2))
    assert m.budget.count==2
    saved=(tmp_path/'calls.json').read_text()
    assert 'test-key' not in saved and 'Authorization' not in saved and 'private-response' not in saved
    budget=RequestBudget(log_path=tmp_path/'calls.json')
    assert budget.count==2
    for _ in range(8):budget.reserve('deepseek','deepseek-flash','test')
    with pytest.raises(LLMError,match='上限'):budget.reserve('deepseek','deepseek-flash','test')


@pytest.mark.parametrize('code',[401,403])
def test_auth_errors_never_retry(code):
    m=model(lambda r:httpx.Response(code,text='private test-key'))
    with pytest.raises(LLMError,match=f'HTTP {code}'):m.parse_patch('预算修改',make_demo_task(hours=2))
    assert m.budget.count==1


def test_new_economics_allowed_but_lifecycle_carbon_preserved():
    m=model(lambda r:httpx.Response(200,json=response('propose_task_patch',{})))
    assert m.parse_patch('进行全生命周期经济评价和NPV比较',make_demo_task(hours=2)).unsupported_demands==[]
    assert m.parse_patch('计算生命周期碳和设备隐含排放',make_demo_task(hours=2)).unsupported_demands


def test_relative_patch_preserves_heat_and_period():
    task=make_demo_task(hours=24)
    revised=revise_task(task,TaskPatch(budget_multiplier=.8,preserve_heat=True))
    assert revised.constraints.budget_yuan==task.constraints.budget_yuan*.8
    assert heat_fingerprint(revised)==heat_fingerprint(task)
    assert revised.version==task.version+1
    with pytest.raises(ValueError):TaskPatch(budget_multiplier=.8,budget_yuan=1)
    with pytest.raises(ValueError):TaskPatch(preserve_heat=True,demand_scale=.8)


def test_core_model_action_real_recompute_idempotent_and_current_numeric_evidence(tmp_path):
    previous=EnergyAgent(tmp_path/'old').run(make_demo_task(hours=12))
    calls=[]
    def handler(req):
        body=json.loads(req.content);calls.append(body)
        name=body['tools'][0]['function']['name'];ctx=json.loads(body['messages'][1]['content'])
        if name=='planning_intent':
            args={'operation':'modify','patch':{'budget_multiplier':.8,'preserve_heat':True}}
        else:
            args={'run_id':ctx['run_id'],'conclusion':ctx['conclusion'],'claims':[{'reference':k,'value':v} for k,v in ctx['current_facts'].items()][:30]}
        return httpx.Response(200,json=response(name,args))
    m=model(handler)
    session=AgentSession(EnergyAgent(tmp_path/'new'),m,tmp_path/'receipts')
    reply=session.submit('预算减少20%，供热要求保持不变。',previous,request_id='stable-request')
    assert reply.heat_unchanged and reply.explanation_verified
    assert reply.run.run_id!=previous.run_id
    assert reply.run.input_version==previous.input_version+1
    assert reply.run.task.constraints.budget_yuan==previous.task.constraints.budget_yuan*.8
    assert any(c.tool_name=='solve_dispatch' for c in reply.run.tool_calls)
    assert reply.run.run_id in reply.text
    duplicate=session.submit('预算减少20%，供热要求保持不变。',reply.run,request_id='stable-request')
    assert duplicate.run.run_id==reply.run.run_id and len(calls)==2
    assert 'electric_load_kw' not in calls[0]['messages'][1]['content']
    # Restart the session, as after a lost HTTP response/browser retry.
    duplicate=AgentSession(EnergyAgent(tmp_path/'new'),m,tmp_path/'receipts').submit('预算减少20%，供热要求保持不变。',reply.run,request_id='stable-request')
    assert len(calls)==2 and duplicate.run.task.constraints.budget_yuan==reply.run.task.constraints.budget_yuan


def test_electric_task_clarifies_heat_without_network(tmp_path):
    from energy_agent.schemas import TaskRequest, CaseContext
    raw=make_demo_task(hours=2).model_dump()
    raw['assessment_mode']='electric_only';raw['data']['heat_load_kw_th']=[0,0]
    for c in raw['candidates']:c['hp_kw_th']=c['boiler_kw_th']=0
    raw['case_context']=CaseContext(boundary='人工电侧测试',excluded=['供热'],timestamp_convention='起点',investment_scope='测试').model_dump()
    task=TaskRequest.model_validate(raw)
    # Session checks the declared service boundary before any model request.
    previous=EnergyAgent(tmp_path).run(task)
    m=model(lambda r:pytest.fail('clarification must not need a paid request'))
    reply=AgentSession(EnergyAgent(tmp_path/'next'),m,tmp_path/'session').submit('预算减少20%，供热要求保持不变',previous,request_id='heat')
    assert reply.status=='clarification' and '未建模供热' in reply.text


def test_wrong_values_and_old_run_rejected(tmp_path):
    run=EnergyAgent(tmp_path).run(make_demo_task(hours=3))
    facts=current_facts(run);ref=next(iter(facts))
    good={'run_id':run.run_id,'conclusion':'可行且通过独立校验','claims':[{'reference':ref,'value':facts[ref]}]}
    assert validate_explanation(good,run)
    with pytest.raises(LLMError,match='旧运行'):validate_explanation({**good,'run_id':'old-run'},run)
    with pytest.raises(LLMError,match='数字'):validate_explanation({**good,'claims':[{'reference':ref,'value':facts[ref]+1}]},run)


def test_model_cannot_drop_core_heat_or_change_absolute_budget(tmp_path):
    old=EnergyAgent(tmp_path/'old').run(make_demo_task(hours=2))
    m=model(lambda r:httpx.Response(200,json=response('planning_intent',{'operation':'modify','patch':{'budget_yuan':1,'demand_scale':.5}})))
    session=AgentSession(EnergyAgent(tmp_path/'new'),m,tmp_path/'session')
    with pytest.raises(LLMError,match='相对预算'):session.submit('预算减少20%，供热要求保持不变',old,request_id='bad')
    assert not (tmp_path/'new').exists()


def test_model_tool_failure_is_not_a_fabricated_solution(tmp_path):
    previous=EnergyAgent(tmp_path/'old').run(make_demo_task(hours=2))
    def handler(req):
        b=json.loads(req.content);name=b['tools'][0]['function']['name'];ctx=json.loads(b['messages'][1]['content'])
        args={'operation':'modify','patch':{'budget_multiplier':.8,'preserve_heat':True}} if name=='planning_intent' else {
            'run_id':ctx['run_id'],'conclusion':ctx['conclusion'],'claims':[]}
        return httpx.Response(200,json=response(name,args))
    agent=EnergyAgent(tmp_path/'new')
    tool=agent.registry._tools['solve_dispatch']
    from energy_agent.agent import Tool
    def failed(_):raise RuntimeError('intentional solver failure')
    agent.registry._tools['solve_dispatch']=Tool(tool.input_schema,tool.output_schema,failed)
    reply=AgentSession(agent,model(handler),tmp_path/'receipts').submit('预算减少20%，供热要求保持不变',previous,request_id='failure')
    assert reply.run.state.value=='执行失败' and reply.explanation_verified
    assert '待补信息或执行失败' in reply.text
    assert any(call.status=='error' for call in reply.run.tool_calls)


def test_project_environment_loading_never_overrides_exported_value(tmp_path,monkeypatch):
    from dotenv import load_dotenv
    p=tmp_path/'.env';p.write_text('LLM_MODEL=from_local\nLLM_API_KEY=artificial_test_only\n')
    monkeypatch.setenv('LLM_MODEL','exported-model')
    monkeypatch.delenv('LLM_API_KEY',raising=False)
    load_dotenv(p,override=False)
    import os
    assert os.getenv('LLM_MODEL')=='exported-model'
    assert os.getenv('LLM_API_KEY')=='artificial_test_only'
    assert 'override=False' in Path('app.py').read_text() and 'override=False' in Path('energy_agent/cli.py').read_text()
