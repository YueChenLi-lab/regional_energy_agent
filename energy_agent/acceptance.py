"""Explicit live acceptance; never imported to automatically spend API quota."""
import json
from pathlib import Path

from .agent import EnergyAgent
from .conversation import AgentSession,ConnectivityCheck,heat_fingerprint
from .frontier import run_summary
from .llm import LLMError,OpenAICompatibleClient,RequestBudget


def run_live_acceptance(previous,output,options):
    from .storage import file_lock
    with file_lock(Path(output)/'acceptance.lock'):
        return _run_live_acceptance(previous,output,options)


def _run_live_acceptance(previous,output,options):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    budget=RequestBudget(log_path=out/'model_requests.json')
    client=OpenAICompatibleClient.from_environment(budget=budget,max_attempts=2,parse_max_tokens=1400,explain_max_tokens=2600)
    path=out/'acceptance.json'
    evidence=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'base_run_id':previous.run_id,'stages':{},'actual_requests':budget.count}
    if 'base_run_id' not in evidence:raise ValueError('旧验收目录缺少基准标识，请保留旧证据并使用新目录')
    if evidence['base_run_id']!=previous.run_id:raise ValueError('验收目录已绑定其他基准，请使用新目录；不重置已有请求计数')
    session=AgentSession(EnergyAgent(out/'runs',options),client,out/'session')
    def save():
        evidence['actual_requests']=budget.count
        evidence['status']='passed' if all(evidence['stages'].get(n,{}).get('status')=='passed' for n in ('connectivity','clarification','continuation','relative20','infeasible')) else 'not_verified'
        evidence['fees']='未核实，不估算费用'
        path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    def stage(name,function,minimum_requests=1):
        if evidence['stages'].get(name,{}).get('status')=='passed':return
        if budget.maximum-budget.count<minimum_requests:
            evidence['stages'][name]={'status':'not_verified','reason':'剩余真实请求预算不足；没有越过10次上限'};save();return
        try:
            result=function()
            evidence['stages'][name]={'status':'passed',**result}
        except (ValueError,OSError,LLMError) as exc:
            evidence['stages'][name]={'status':'not_verified','reason':str(exc)}
        save()
    connectivity=out/'connectivity.json'
    if connectivity.exists() and json.loads(connectivity.read_text()).get('status')=='passed' and any(r.get('tool')=='connectivity_check' and r.get('status')=='200' for r in budget.records):
        evidence['stages']['connectivity']={'status':'passed','evidence':'connectivity.json；计入同一model_requests.json'}
    else:
        stage('connectivity',lambda:{'response':client.call_tool('connectivity_check',ConnectivityCheck,{'request':'仅返回status=ok'}).status})
    if evidence['stages']['connectivity']['status']!='passed':save();return evidence
    def clarification():
        reply=session.submit('预算少一点，供热不变。',previous,request_id='live-multiround')
        if reply.status!='clarification' or not any(m.field=='budget' for m in reply.pending.missing_fields):raise ValueError('未按预期澄清预算幅度')
        _,receipt=session._read('live-multiround')
        if receipt['intent']['operation']!='clarify':raise ValueError('模型没有选择澄清操作；本地安全检查阻止了求解')
        (out/'clarification_reply.json').write_text(reply.model_dump_json(indent=2),encoding='utf-8')
        return {'user':'预算少一点，供热不变。','assistant':reply.text,'base_run_id':reply.pending.base_run_id,'input_version':reply.pending.input_version,'model_operation':'clarify'}
    stage('clarification',clarification)
    def continuation():
        reply=session.answer('live-multiround','减少15%。',turn_id='live-answer15')
        if not reply.run or not reply.explanation_verified or not reply.heat_unchanged:raise ValueError('接续结果未通过解释或供热检查')
        if reply.run.task.constraints.budget_yuan!=previous.task.constraints.budget_yuan*.85:raise ValueError('预算没有按原基准乘0.85')
        if reply.run.run_id==previous.run_id or reply.run.input_version<=previous.input_version:raise ValueError('没有生成新版本和新运行')
        before=budget.count
        duplicate=session.answer('live-multiround','减少15%。',turn_id='live-answer15')
        if duplicate.run.run_id!=reply.run.run_id or budget.count!=before:raise ValueError('重复提交不幂等')
        (out/'continuation_reply.json').write_text(reply.model_dump_json(indent=2),encoding='utf-8')
        return {'user':'减少15%。','assistant':reply.text,'result':run_summary(reply.run),'heat_unchanged':True,'period_unchanged':reply.run.task.data.timestamps==previous.task.data.timestamps,'explanation_verified':True,'duplicate_api_requests':budget.count-before}
    if evidence['stages'].get('clarification',{}).get('status')=='passed':stage('continuation',continuation,2)
    def modify(text,request_id,expected_budget=None,infeasible=False,economic=False):
        reply=session.submit(text,previous,request_id=request_id)
        if not reply.run or not reply.explanation_verified or not reply.heat_unchanged:raise ValueError('修改/供热/当前结果解释未通过')
        if expected_budget is not None and reply.run.task.constraints.budget_yuan!=expected_budget:raise ValueError('预算不符合授权值')
        if infeasible and any(s.validation.valid for s in reply.run.scenarios):raise ValueError('预期不可行任务出现可行解，请核查基准')
        if economic and (reply.run.task.economics.discount_rate!=.04 or reply.run.task.economics.horizon_years!=25):raise ValueError('经济参数没有按契约更新')
        (out/(request_id+'_reply.json')).write_text(reply.model_dump_json(indent=2),encoding='utf-8')
        return {'user':text,'assistant':reply.text,'result':run_summary(reply.run),'heat_unchanged':True,'explanation_verified':True}
    stage('relative20',lambda:modify('预算减少20%，供热要求保持不变。','live-budget20',previous.task.constraints.budget_yuan*.8),2)
    stage('infeasible',lambda:modify('初始投资预算设为0元，供热要求保持不变。','live-infeasible',0,infeasible=True),2)
    stage('economics',lambda:modify('折现率改为4%，规划期25年，光伏寿命改为30年，光伏年维护费率改为2%，项目额外年固定维护费改为1万元，供热不变。','live-economics',economic=True),2)
    save();return evidence
