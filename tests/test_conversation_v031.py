"""Offline contracts and real local recalculation; no paid or external requests."""
from pathlib import Path
from types import SimpleNamespace
import shutil

import pytest

from energy_agent.agent import EnergyAgent,revise_task
from energy_agent.annual import default_economics
from energy_agent.conversation import AgentSession,heat_fingerprint
from energy_agent.data import make_demo_task
from energy_agent.llm import LLMError
from energy_agent.modifications import compile_contract,validate_proposal,assert_preserved
from energy_agent.schemas import TaskPatch


class SimulatedModel:
    def __init__(self):self.calls=[];self.fail_explanation=False
    def call_tool(self,name,cls,context,**kwargs):
        self.calls.append((name,context))
        if name=='planning_intent':
            contract=context['authorized_contract']
            return cls.model_validate({'operation':'clarify' if contract['missing'] else 'modify',
                'patch':None if contract['missing'] else contract['patch']})
        if self.fail_explanation:raise LLMError('simulated lost explanation response')
        return cls.model_validate({'run_id':context['run_id'],'conclusion':context['conclusion'],
            'claims':[{'reference':k,'value':v} for k,v in list(context['current_facts'].items())[:10]]})


@pytest.fixture
def base(tmp_path):
    return EnergyAgent(tmp_path/'base').run(make_demo_task(hours=12))


@pytest.mark.parametrize('percent',[10,15,20,30])
def test_general_reductions_and_amount_units_are_authorized_and_heat_preserved(base,percent):
    c=compile_contract(f'预算减少{percent}%，供热不变',base)
    assert c.ready
    new=revise_task(base.task,c.patch)
    assert new.constraints.budget_yuan==pytest.approx(base.task.constraints.budget_yuan*(1-percent/100))
    assert heat_fingerprint(new)==heat_fingerprint(base.task)
    assert_preserved(base.task,new,c)
    to=compile_contract(f'预算降到原来的{percent}%，供热不变',base)
    assert to.patch.budget_multiplier==pytest.approx(percent/100)


@pytest.mark.parametrize('text,expected', [('预算设为85万元',850000),('预算改为850000元',850000),('预算减少10万元',1100000),('预算从120万元降低到85万元',850000),('预算降低到85万元',850000)])
def test_yuan_and_wan_have_explicit_distinct_values(base,text,expected):
    contract=compile_contract(text,base)
    assert contract.ready
    assert revise_task(base.task,contract.patch).constraints.budget_yuan==expected


@pytest.mark.parametrize('text',['预算少一点，供热不变','预算减少15%，预算改为900万元','供热不变，热负荷减少10%','预算改为100','折现率改为5','预算从100万元降低到85万元','预算改为-100万元'])
def test_ambiguity_conflicts_and_missing_units_never_authorize_solve(base,text):
    assert not compile_contract(text,base).ready


def test_electric_and_heat_changes_are_separate_and_unsolicited_edits_fail(base):
    contract=compile_contract('供热不变，电负荷增加10%',base)
    assert contract.ready
    updated=revise_task(base.task,contract.patch)
    assert updated.data.electric_load_kw==pytest.approx([x*1.1 for x in base.task.data.electric_load_kw])
    assert heat_fingerprint(updated)==heat_fingerprint(base.task)
    assert_preserved(base.task,updated,contract)
    budget=compile_contract('预算减少15%，供热不变',base)
    with pytest.raises(ValueError):validate_proposal(TaskPatch(budget_multiplier=.85,preserve_heat=True,clear_emission_limit=True),budget)
    with pytest.raises(ValueError):validate_proposal(TaskPatch(budget_multiplier=.85,heat_demand_scale=.9),budget)


def test_economic_edits_use_units_devices_and_preserve_discount(base):
    base.task.economics=default_economics('demo-equipment')
    c=compile_contract('预算改为85万元，折现率改为4%，规划期25年，光伏寿命改为30年，电池寿命改为12年，光伏年维护费率改为2%，项目额外年固定维护费改为1万元，电池变动维护费改为0.02元/kWh',base)
    assert c.ready
    t=revise_task(base.task,c.patch)
    assert t.economics.discount_rate==.04 and t.economics.horizon_years==25
    assert t.economics.assets['pv_kw'].lifetime_years==30
    assert t.economics.assets['battery_energy_kwh'].lifetime_years==12
    assert t.economics.assets['pv_kw'].fixed_om_fraction==.02
    assert t.economics.additional_fixed_om_yuan_per_year==10000
    assert t.economics.battery_variable_om_per_kwh==.02
    c=compile_contract('折现率不变，规划期改为25年',base)
    t=revise_task(base.task,c.patch);assert_preserved(base.task,t,c)
    assert t.economics.discount_rate==base.task.economics.discount_rate
    bad=TaskPatch(economics={'horizon_years':25,'discount_rate':0})
    with pytest.raises(ValueError):validate_proposal(bad,c)


def test_pending_request_restores_after_move_and_answers_original_budget(base,tmp_path):
    model=SimulatedModel();path=tmp_path/'session'
    session=AgentSession(EnergyAgent(tmp_path/'runs'),model,path)
    first=session.submit('预算少一点，供热不变。',base,request_id='root')
    assert first.status=='clarification' and first.pending.missing_fields[0].field=='budget'
    assert first.pending.original_request=='预算少一点，供热不变。'
    assert first.pending.base_run_id==base.run_id
    assert first.pending.confirmed_conditions['budget_yuan']==base.task.constraints.budget_yuan
    assert not (tmp_path/'runs').exists()
    moved=tmp_path/'moved';shutil.copytree(path,moved)
    restored=AgentSession(EnergyAgent(tmp_path/'runs'),model,moved)
    reply=restored.answer('root','减少15%。',turn_id='answer1')
    assert reply.status=='completed' and reply.heat_unchanged and reply.explanation_verified
    assert reply.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.85
    assert reply.run.input_version==base.input_version+1
    assert reply.run.previous_run_id==base.run_id
    assert 'NPV' not in reply.text # short legacy demo has no annual economics
    assert '保持：' in reply.text and '变化' in reply.text and base.run_id in reply.text
    count=len(model.calls)
    duplicate=restored.answer('root','减少15%。',turn_id='answer1')
    assert duplicate.run.run_id==reply.run.run_id and len(model.calls)==count
    duplicate=restored.submit('预算少一点，供热不变。',reply.run,request_id='root')
    assert duplicate.run.run_id==reply.run.run_id and len(model.calls)==count


def test_edit_answer_and_rebase_do_not_compound_relative_budget(base,tmp_path):
    model=SimulatedModel();s=AgentSession(EnergyAgent(tmp_path/'runs'),model,tmp_path/'session')
    s.submit('预算少一点，供热不变',base,request_id='root')
    first=s.answer('root','减少15%',turn_id='a')
    edited=s.edit_answer('root','a','减少30%',edit_id='edit1')
    assert edited.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.7
    assert edited.run.input_version>first.run.input_version
    assert edited.run.run_id!=first.run.run_id
    count=len(model.calls)
    assert s.edit_answer('root','a','减少30%',edit_id='edit1').run.run_id==edited.run.run_id
    assert len(model.calls)==count
    newbase=EnergyAgent(tmp_path/'another').run(revise_task(base.task,TaskPatch(budget_yuan=900000)))
    rebase=s.rebase('root',newbase)
    assert rebase.status=='clarification' and rebase.pending.base_run_id==newbase.run_id
    assert len(model.calls)==count
    resumed=s.resume('root')
    assert resumed.run.task.constraints.budget_yuan==900000*.7
    assert resumed.run.previous_run_id==newbase.run_id


def test_cancel_or_unbound_answers_cannot_become_new_requests(base,tmp_path):
    m=SimulatedModel();s=AgentSession(EnergyAgent(tmp_path/'runs'),m,tmp_path/'session')
    with pytest.raises(ValueError,match='无上下文'):s.answer('unknown','减少15%',turn_id='a')
    s.submit('预算少一点，供热不变',base,request_id='root')
    count=len(m.calls);assert s.cancel('root').status=='cancelled'
    with pytest.raises(ValueError,match='取消'):s.answer('root','减少15%',turn_id='a')
    assert len(m.calls)==count and not (tmp_path/'runs').exists()


def test_lost_explanation_recovers_same_new_run_without_double_reduction(base,tmp_path):
    m=SimulatedModel();m.fail_explanation=True
    s=AgentSession(EnergyAgent(tmp_path/'runs'),m,tmp_path/'session')
    with pytest.raises(LLMError):s.submit('预算减少15%，供热不变',base,request_id='root')
    results=list((tmp_path/'runs').glob('*/result.json'));assert len(results)==1
    m.fail_explanation=False
    restored=AgentSession(EnergyAgent(tmp_path/'runs'),m,tmp_path/'session')
    reply=restored.submit('预算减少15%，供热不变',base,request_id='root')
    assert len(list((tmp_path/'runs').glob('*/result.json')))==1
    assert reply.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.85


@pytest.mark.parametrize('text,factor',[('供热不变的前提下将预算下调15%',.85),('把预算削减30%并保持供热不变',.7),('预算降低10%同时供热维持不变',.9)])
def test_general_word_order_does_not_depend_on_one_phrase(base,text,factor):
    c=compile_contract(text,base)
    assert c.ready and c.patch.budget_multiplier==pytest.approx(factor)
    assert c.patch.preserve_heat
    revised=revise_task(base.task,c.patch)
    assert_preserved(base.task,revised,c)



def test_unhandled_change_requires_clarification_and_cancelling_only_that_clause_keeps_budget(base,tmp_path):
    m=SimulatedModel();s=AgentSession(EnergyAgent(tmp_path/'runs'),m,tmp_path/'session')
    reply=s.submit('预算减少15%，光伏容量增加100kW，供热不变',base,request_id='scope')
    assert reply.status=='clarification' and not (tmp_path/'runs').exists()
    field=next(f.field for f in reply.pending.missing_fields if f.field.startswith('clause_'))
    result=s.answer('scope','取消这一项容量修改',turn_id='scope-answer',field=field)
    assert result.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.85
    assert result.heat_unchanged and result.explanation_verified



def test_simultaneous_retry_is_rejected_before_second_model_request(base,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    entered=Event();release=Event()
    class WaitingModel(SimulatedModel):
        def call_tool(self,*args,**kwargs):
            entered.set();assert release.wait(5)
            return super().call_tool(*args,**kwargs)
    first_model=WaitingModel();second_model=SimulatedModel()
    first=AgentSession(EnergyAgent(tmp_path/'runs'),first_model,tmp_path/'session')
    second=AgentSession(EnergyAgent(tmp_path/'runs'),second_model,tmp_path/'session')
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(first.submit,'预算少一点，供热不变',base,request_id='same')
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError,match='正在处理中'):
                second.submit('预算少一点，供热不变',base,request_id='same')
        finally:release.set()
        reply=future.result(timeout=10)
    assert reply.status=='clarification' and len(first_model.calls)==1 and len(second_model.calls)==0
    assert second.restore('same').pending.base_run_id==base.run_id


@pytest.mark.parametrize('text',['预算减少15%，排放上限不要取消，供热不变','不要取消排放上限，预算减少15%，供热不变'])
def test_negated_cancellation_is_preservation_not_a_clear_operation(base,text):
    base.task.constraints.emission_limit_kg=10000
    c=compile_contract(text,base)
    assert c.ready and not c.patch.clear_emission_limit
    assert 'emission_limit' in c.preserves
    updated=revise_task(base.task,c.patch)
    assert updated.constraints.emission_limit_kg==10000
    assert_preserved(base.task,updated,c)
    with pytest.raises(ValueError):validate_proposal(TaskPatch(budget_multiplier=.85,preserve_heat=True,clear_emission_limit=True),c)
