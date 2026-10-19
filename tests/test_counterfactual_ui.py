"""Explicit UI search/adoption with real small solves; refresh is passive."""
import httpx
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent
from energy_agent.data import make_demo_task


def test_form_search_is_explicit_and_only_confirm_adopts(tmp_path,monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path/'ui'))
    def no_network(*a,**k):raise AssertionError('No paid calls or network in repair UI')
    monkeypatch.setattr(httpx.Client,'send',no_network)
    task=make_demo_task(hours=6);task.candidates=task.candidates[:1];task.constraints.budget_yuan=0
    base=EnergyAgent(tmp_path/'base').run(task)
    app=AppTest.from_string('''import streamlit as st
from energy_agent.counterfactual_ui import render_counterfactual
def adopt(run): st.session_state['base']=run
render_counterfactual(st.session_state['base'],on_adopt=adopt)
''',default_timeout=60)
    app.session_state['base']=base
    app.run()
    assert not app.exception and app.session_state['base'].run_id==base.run_id
    assert any('待执行' in c.value for c in app.caption)
    assert 'cf_result_'+base.run_id not in app.session_state
    app.multiselect(key='cf_allowed_'+base.run_id).set_value(['budget_yuan'])
    app.number_input(key='cf_upper_budget_yuan'+base.run_id).set_value(100000.)
    app.button(key='cf_search_'+base.run_id).click().run()
    assert not app.exception
    result=app.session_state['cf_result_'+base.run_id]
    p=result.paths[0]
    assert p.final_validation.valid and p.boundary_precision_reached
    assert app.session_state['base'].task.constraints.budget_yuan==0
    # A rerun and a duplicate explicit request both restore the receipt.
    import energy_agent.counterfactual as module
    def forbidden(*a,**k):raise AssertionError('A repeat must not solve again')
    monkeypatch.setattr(module,'_search',forbidden)
    app.run();app.button(key='cf_search_'+base.run_id).click().run()
    assert not app.exception and app.session_state['cf_result_'+base.run_id]==result
    app.button(key='cf_adopt_'+p.path_id).click().run()
    assert not app.exception
    adopted=app.session_state['base']
    assert adopted.run_id==p.run_id and adopted.input_version==base.input_version+1
    assert adopted.task.constraints.budget_yuan==p.suggested_value
    assert base.task.constraints.budget_yuan==0 and adopted.task.data==base.task.data


def test_question_cannot_override_explicit_budget_lock(tmp_path,monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path))
    task=make_demo_task(hours=6);task.candidates=task.candidates[:1];task.constraints.budget_yuan=0;task.constraints.emission_limit_kg=1000
    base=EnergyAgent(tmp_path/'base').run(task)
    app=AppTest.from_string('import streamlit as st\nfrom energy_agent.counterfactual_ui import render_counterfactual\nrender_counterfactual(st.session_state["base"])')
    app.session_state['base']=base
    app.run()
    app.text_input(key='cf_question_'+base.run_id).set_value('预算不能增加，碳约束可以放宽多少？').run()
    assert not app.exception
    assert '追加初始投资预算' not in app.multiselect(key='cf_allowed_'+base.run_id).options
    # Explicitly contradictory form locks are caught before a solver is used.
    app.multiselect(key='cf_allowed_'+base.run_id).set_value(['emission_limit_kg'])
    app.multiselect(key='cf_locked_'+base.run_id).set_value(['budget_yuan','emission_limit_kg'])
    app.button(key='cf_search_'+base.run_id).click().run()
    assert not app.exception and app.error
    assert 'cf_result_'+base.run_id not in app.session_state


def test_competition_console_adoption_refreshes_existing_task_and_form(tmp_path,monkeypatch):
    from pathlib import Path
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path/'console'))
    def no_network(*a,**k):raise AssertionError('No model requests')
    monkeypatch.setattr(httpx.Client,'send',no_network)
    task=make_demo_task(hours=6);task.candidates=task.candidates[:1];task.constraints.budget_yuan=0
    base=EnergyAgent(tmp_path/'base').run(task)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'competition_app.py'),default_timeout=60)
    app.session_state['last_run']=base
    app.session_state['task']=task
    app.session_state['applied_scale']=1.
    app.run()
    assert not app.exception
    app.multiselect(key='cf_allowed_'+base.run_id).set_value(['budget_yuan'])
    app.number_input(key='cf_upper_budget_yuan'+base.run_id).set_value(100000.)
    app.button(key='cf_search_'+base.run_id).click().run()
    assert not app.exception and app.session_state['last_run'].run_id==base.run_id
    p=app.session_state['cf_result_'+base.run_id].paths[0]
    app.button(key='cf_adopt_'+p.path_id).click().run()
    assert not app.exception
    new=app.session_state['last_run']
    assert new.run_id==p.run_id and new.task==app.session_state['task']
    assert app.number_input(key='budget').value==p.suggested_value
    assert new.task.data==base.task.data and base.task.constraints.budget_yuan==0
