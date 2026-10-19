"""Two-layer authorization + complete simulated-model/local-solver regressions."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from energy_agent.agent import EnergyAgent, revise_task
from energy_agent.annual import default_economics
from energy_agent.conversation import AgentSession, heat_fingerprint
from energy_agent.data import make_demo_task
from energy_agent.edit_semantics import EditMeaningError, parse_edit
from energy_agent.modifications import compile_contract


class SimulatedPlanner:
    def __init__(self):self.operations=[]
    def call_tool(self,name,cls,context,**kwargs):
        self.operations.append(name)
        if name=='planning_intent':
            c=context['authorized_contract']
            return cls.model_validate({'operation':'clarify' if c['missing'] else 'modify','patch':None if c['missing'] else c['patch']})
        return cls.model_validate({'run_id':context['run_id'],'conclusion':context['conclusion'],
            'claims':[{'reference':k,'value':v} for k,v in list(context['current_facts'].items())[:5]]})


@pytest.fixture
def base(tmp_path):
    task=make_demo_task(hours=6);task.constraints.budget_yuan=10000000
    return EnergyAgent(tmp_path/'base').run(task)


CORRECT=[('预算增加到1200万元',12000000),('预算增加200万元',12000000),('预算增加20%',12000000),('预算比原来增加20%',12000000),
    ('预算提高到原来的120%',12000000),('预算减少200万元',8000000),('预算减少到200万元',2000000),
    ('预算从1000万元增加到1200万元',12000000),('预算减少20%',8000000),('预算降到原来的20%',2000000)]


@pytest.mark.parametrize('text,expected',CORRECT)
def test_authorization_and_simulated_conversation_use_correct_budget_and_keep_heat(base,tmp_path,text,expected):
    c=compile_contract(text+'，供热不变',base)
    assert c.ready and c.edits[0]['field']=='constraints.budget_yuan'
    assert c.edits[0]['after']==expected and c.edits[0]['unit']=='元'
    assert 'heat_load' in c.preserves and 'period' in c.unchanged
    assert revise_task(base.task,c.patch).constraints.budget_yuan==expected
    planner=SimulatedPlanner();session=AgentSession(EnergyAgent(tmp_path/'new'),planner,tmp_path/'session')
    reply=session.submit(text+'，供热不变',base,request_id='budget')
    assert reply.status=='completed' and reply.run.input_version==base.input_version+1
    assert reply.run.task.constraints.budget_yuan==expected
    assert reply.heat_unchanged and heat_fingerprint(reply.run.task)==heat_fingerprint(base.task)
    assert reply.explanation_verified and reply.run.run_id!=base.run_id
    assert any(s.validation.valid for s in reply.run.scenarios)
    count=len(planner.operations)
    assert session.submit(text+'，供热不变',base,request_id='budget').run.run_id==reply.run.run_id
    assert len(planner.operations)==count


INVALID=['预算不要减少20%','不要把预算减少20%','不要将预算增加200万元','预算提高到120%',
    '预算增加20','预算改为负100万元','预算改为－100万元','预算改为- 100万元','预算增加一点','预算增加20%左右','预算增加到大约1200万元',
    '预算无须减少20%','勿把预算减少20%','预算不需要减少20%','电负荷增加约10%',
    '光伏寿命增加约5年','光伏维护费率改为大概2%','预算增加20%以上','预算增加20%以内','预算增加到超过1200万元','购电上限改为1000kWh','购电上限改为1000kW_th',
    '购电上限改为1000kWfoo','购电上限改为1000kW/h','预算改为1200万元/kWh',
    '电负荷不要减少20%','不要把热负荷增加20%','电负荷提高到120%',
    '光伏寿命不要减少5年','光伏维护费率不要减少20%', '热泵变动维护费改为0.02元/kWh',
    '光伏寿命改为20年/kWh','排放上限改为100kgCO2','排放上限改为100kgCO2e/kWh']


@pytest.mark.parametrize('text',INVALID)
def test_ambiguous_negated_or_wrong_dimension_never_enters_solver(base,tmp_path,text):
    # Economic parsing is tested against confirmed scalar conditions; no fake
    # annual solve is needed for a request that must stop before calculation.
    base.task.economics=default_economics(base.task.devices.source_id) if any(w in text for w in ('寿命','维护')) else None
    c=compile_contract(text+'，供热不变',base)
    assert not c.ready and c.missing
    if base.task.economics:
        # AgentSession requires a valid annual baseline. The unit-level economic
        # cases above independently prove rejection; end-to-end uses valid demo.
        base.task.economics=None
    planner=SimulatedPlanner();session=AgentSession(EnergyAgent(tmp_path/'new'),planner,tmp_path/'session')
    reply=session.submit(text+'，供热不变',base,request_id='invalid')
    assert reply.status=='clarification' and reply.run is None
    assert not (tmp_path/'new').exists() and planner.operations==['planning_intent']
    assert session.restore('invalid').status=='clarification'
    assert session.cancel('invalid').status=='cancelled'


@pytest.mark.parametrize('unit',['t','T','吨'])
def test_metric_tonne_units_have_identical_conversion_and_full_dialogue(base,tmp_path,unit):
    c=compile_contract('排放上限改为100'+unit,base)
    assert c.ready and c.patch.emission_limit_kg==100000
    assert c.edits[0]['unit']=='kgCO2e'
    reply=AgentSession(EnergyAgent(tmp_path/'new'),SimulatedPlanner(),tmp_path/'session').submit('排放上限改为100'+unit,base,request_id='mass')
    assert reply.run.task.constraints.emission_limit_kg==100000
    assert reply.run.input_version==2 and any(s.validation.valid for s in reply.run.scenarios)


@pytest.mark.parametrize('text,current,dimension,expected',[
    ('寿命增加到30年',25,'years',30),('寿命增加5年',25,'years',30),
    ('维护费用增加到3万元/年',10000,'annual_money',30000),('维护费用增加3万元/年',10000,'annual_money',40000),
    ('维护费率提高到2%',.015,'rate',.02),('维护费率增加20%',.015,'rate',.018),
    ('电负荷提高到原来的120%',1,'scale',1.2),('电负荷增加20%',1,'scale',1.2),
    ('热功率改为100kW_th',20,'thermal_power',100),('电量改为100kWh',20,'energy',100),
    ('热量改为100kWh_th',20,'thermal_energy',100),('热泵单价改为0.02元/kWh_th',.01,'thermal_om',.02)])
def test_same_operation_and_exact_unit_rules_apply_to_other_dimensions(text,current,dimension,expected):
    assert parse_edit(text,current,dimension).value==pytest.approx(expected)


def test_negation_scope_and_unrequested_changes_cannot_be_smuggled(base,tmp_path):
    text='不要把预算减少20%同时电负荷增加10%，供热不变'
    c=compile_contract(text,base)
    assert not c.ready and c.patch.budget_multiplier is None and c.patch.electric_demand_scale is None
    kept=compile_contract('预算增加200万元，排放上限不要取消，供热不变',base)
    assert kept.ready and 'emission_limit' in kept.preserves and not kept.patch.clear_emission_limit


@pytest.mark.parametrize('text,current,dimension',[
    ('预算增加到800万元',10000000,'money'),('预算减少到1200万元',10000000,'money'),
    ('维护费率降低到2%',.015,'rate'),('寿命增加到20年',25,'years'),
    ('负荷提高到原来的80%',1,'scale')])
def test_contradictory_target_direction_is_not_silently_prioritized(text,current,dimension):
    with pytest.raises(EditMeaningError,match='方向矛盾'):parse_edit(text,current,dimension)


@pytest.mark.parametrize('text',['预算不要减少20%','购电上限改为1000kWh'])
def test_even_a_model_proposing_an_edit_cannot_bypass_local_ambiguity(base,tmp_path,text):
    class RoguePlanner(SimulatedPlanner):
        def call_tool(self,name,cls,context,**kwargs):
            self.operations.append(name)
            return cls.model_validate({'operation':'modify','patch':{'budget_multiplier':.8}})
    reply=AgentSession(EnergyAgent(tmp_path/'new'),RoguePlanner(),tmp_path/'session').submit(text,base,request_id='rogue')
    assert reply.status=='clarification' and reply.run is None and not (tmp_path/'new').exists()


@pytest.mark.parametrize('utterance,answer,field,expected',[
    ('购电上限改为1000kWh，供热不变','改为1000kW','grid_limit_kw',1000),
    ('用电需求少一点，供热不变','减少15%','electric_load',.85),
    ('碳上限改为100kWh，供热不变','改为100T','emission_limit_kg',100000)])
def test_unit_and_alias_clarification_answers_replace_the_original_pending_clause(base,tmp_path,utterance,answer,field,expected):
    session=AgentSession(EnergyAgent(tmp_path/'runs'),SimulatedPlanner(),tmp_path/'session')
    pending=session.submit(utterance,base,request_id='clarify')
    assert pending.status=='clarification' and not (tmp_path/'runs').exists()
    result=session.answer('clarify',answer,turn_id='correction')
    assert result.status=='completed' and result.run.input_version==base.input_version+1
    assert result.heat_unchanged and result.run.task.data.timestamps==base.task.data.timestamps
    if field=='electric_load':assert result.run.task.data.electric_load_kw==pytest.approx([v*expected for v in base.task.data.electric_load_kw])
    else:assert getattr(result.run.task.constraints,field)==expected
