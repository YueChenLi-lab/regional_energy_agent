from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent,revise_task
from energy_agent.annual import default_economics
from energy_agent.comparability import compare_basis
from energy_agent.conversation import AgentSession,deterministic_reply
from energy_agent.data import make_demo_task
from energy_agent.schemas import CaseContext,TaskPatch,TaskRequest


def test_budget_comparison_uses_one_shared_basis_in_report_dialogue_and_ui(tmp_path):
    agent=EnergyAgent(tmp_path/'runs');a=agent.run(make_demo_task(hours=6))
    b=agent.run(revise_task(a.task,TaskPatch(budget_yuan=0)),previous=a)
    basis=b.changes['comparison_basis'];assert basis['kind']=='A_same_basis' and basis['directly_comparable']
    assert all(c['same'] for c in basis['checks'])
    summary=basis['summary']
    assert summary in Path(b.files['markdown']).read_text(encoding='utf-8')
    assert summary in deterministic_reply(b,a)
    app=AppTest.from_string('import streamlit as st\nfrom energy_agent.ui import _show_results\n_show_results(st.session_state["result"])')
    app.session_state['result']=b;app.run()
    assert not app.exception and any(x.value==summary for x in app.info)


@pytest.mark.parametrize('change,group',[
    ('timestamps','period'),('step','period'),('mode','service'),('boundary','service'),('electric','service'),('heat','service'),
    ('species','emissions'),('scope','emissions'),('grid_factor','emissions'),('gas_factor','emissions'),
    ('price','economics'),('cost','economics'),('rate','economics'),('horizon','economics'),('lifetime','economics'),('pv','resource')])
def test_comparison_detects_each_material_basis_change(change,group):
    a=make_demo_task(hours=6);a.economics=default_economics(a.devices.source_id)
    a.case_context=CaseContext(boundary='单节点电热',excluded=[],timestamp_convention='区间开始',investment_scope='新建')
    b=a.model_copy(deep=True)
    if change=='timestamps':b.data.timestamps=[t+timedelta(days=1) for t in b.data.timestamps]
    elif change=='step':b.data.step_hours=.5
    elif change=='mode':
        b.data.heat_load_kw_th=[0]*6
        for c in b.candidates:c.hp_kw_th=0;c.boiler_kw_th=0
        b.assessment_mode='electric_only'
    elif change=='boundary':b.case_context.boundary='不同计量回路'
    elif change in ('electric','heat'):getattr(b.data,'electric_load_kw' if change=='electric' else 'heat_load_kw_th')[0]+=1
    elif change=='species':b.emission_species='CO2'
    elif change=='scope':next(s for s in b.sources if s.source_id==b.data.source_ids['grid_emission_factor']).conditions='仅CO2核算，来源范围已变'
    elif change=='grid_factor':b.data.grid_emission_factor[0]+=.01
    elif change=='gas_factor':b.data.gas_emission_factor[0]+=.01
    elif change=='price':b.data.electricity_price[0]+=.1
    elif change=='cost':b.devices.pv_cost_per_kw+=100
    elif change=='rate':b.economics.discount_rate=.04
    elif change=='horizon':b.economics.horizon_years=25
    elif change=='lifetime':b.economics.assets['pv_kw'].lifetime_years=30
    elif change=='pv':b.data.pv_per_kw[0]=.1
    basis=compare_basis(a,b)
    assert not basis.directly_comparable
    assert any(c.group==group and not c.same for c in basis.checks)
    assert basis.kind==('B_economic_sensitivity' if group=='economics' else 'C_input_sensitivity')


def test_actual_annual_economic_dialogue_marks_npv_as_sensitivity_not_savings(tmp_path):
    raw=make_demo_task(hours=1).model_dump()
    times=pd.date_range('2021-01-01','2022-01-01',freq='h',inclusive='left',tz='Asia/Shanghai')
    raw['data']['timestamps']=times.to_pydatetime().tolist()
    for key,v in {'electric_load_kw':10,'heat_load_kw_th':20,'pv_per_kw':0,'electricity_price':1,'gas_price':.5,'grid_emission_factor':.55,'gas_emission_factor':.202}.items():raw['data'][key]=[v]*len(times)
    raw['resolution']='full_year';raw['economics']=default_economics(raw['devices']['source_id']).model_dump()
    raw['candidates']=[raw['candidates'][0]];raw['candidates'][0]['boiler_kw_th']=20
    task=TaskRequest.model_validate(raw);agent=EnergyAgent(tmp_path/'runs');base=agent.run(task)
    assert base.scenarios[0].validation.valid
    class SimulatedModel:
        def call_tool(self,name,cls,c,**kwargs):
            if name=='planning_intent':return cls.model_validate({'operation':'modify','patch':c['authorized_contract']['patch']})
            return cls.model_validate({'run_id':c['run_id'],'conclusion':c['conclusion'],
                'claims':[{'reference':k,'value':v} for k,v in list(c['current_facts'].items())[:5]]})
    reply=AgentSession(agent,SimulatedModel(),tmp_path/'session').submit('规划期增加5年，折现率改为4%，光伏寿命增加到30年，项目额外年固定维护费增加到3万元，供热不变',base,request_id='financial')
    run=reply.run
    assert run and run.scenarios[0].validation.valid and run.input_version==2
    assert run.task.economics.horizon_years==25 and run.task.economics.discount_rate==.04
    assert run.task.economics.assets['pv_kw'].lifetime_years==30
    assert run.task.economics.additional_fixed_om_yuan_per_year==30000
    assert run.changes['comparison_basis']['kind']=='B_economic_sensitivity'
    summary=run.changes['comparison_basis']['summary']
    assert summary in reply.text and summary in Path(run.files['markdown']).read_text(encoding='utf-8')
    assert '原始差值（含口径变化）' in reply.text
    assert run.changes['scenarios'][0]['delta_npv_cost_yuan']==pytest.approx(run.scenarios[0].economics.npv_cost_yuan-base.scenarios[0].economics.npv_cost_yuan)

    count=len(list((tmp_path/'runs').glob('*/result.json')))
    session=AgentSession(agent,SimulatedModel(),tmp_path/'financial-invalid')
    for i,text in enumerate(['光伏寿命改为20kWh','光伏寿命不要增加5年','项目额外年固定维护费增加到3万元/kWh','光伏维护费率改为2kWh']):
        stopped=session.submit(text,base,request_id='invalid-'+str(i))
        assert stopped.status=='clarification' and stopped.run is None
        assert len(list((tmp_path/'runs').glob('*/result.json')))==count
