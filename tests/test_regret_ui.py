"""Actual short solves via presentation; no network or implicit baseline changes."""
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent
from energy_agent.data import make_demo_task


def test_explicit_matrix_passive_refresh_replay_and_baseline_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path/'中文 空格'))
    def forbidden(*a,**k):raise AssertionError('No network or model calls')
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=24))
    app=AppTest.from_string('import streamlit as st\nfrom energy_agent.regret_ui import render_regret\nrender_regret(st.session_state["base"])',default_timeout=60)
    app.session_state['base']=base
    app.run()
    prefix='regret_'+base.run_id
    assert not app.exception and prefix+'_result' not in app.session_state
    app.button(key=prefix+'_start').click().run()
    assert app.error and prefix+'_result' not in app.session_state
    app.checkbox(key=prefix+'_confirm').check()
    app.button(key=prefix+'_start').click().run()
    assert not app.exception
    result=app.session_state[prefix+'_result']
    assert result.analysis.status=='certified' and len(result.cells)==12
    assert all(c.validation.valid and c.capacities_fixed for c in result.cells)
    assert len(app.get('download_button'))==3
    assert len(app.get('vega_lite_chart'))>=2
    import energy_agent.regret as module
    monkeypatch.setattr(module,'_evaluate',forbidden)
    app.run();app.button(key=prefix+'_start').click().run()
    assert not app.exception and app.session_state[prefix+'_result']==result
    assert app.session_state['base']==base
    assert all(Path(p).is_file() for p in result.files.values())


def test_competition_entry_pending_and_feature_switch(monkeypatch):
    monkeypatch.setattr(EnergyAgent,'run',lambda *a,**k: (_ for _ in ()).throw(AssertionError('no automatic solve')))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'competition_app.py')).run()
    assert not app.exception
    assert any('多情景稳健决策' in exp.label for exp in app.expander)
    monkeypatch.setenv('ENERGY_AGENT_ENABLE_REGRET','0')
    app.run()
    assert not app.exception and not any('多情景稳健决策' in exp.label for exp in app.expander)


def test_budget_partial_ui_never_certifies(tmp_path,monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path/'partial'))
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    app=AppTest.from_string('import streamlit as st\nfrom energy_agent.regret_ui import render_regret\nrender_regret(st.session_state["base"])',default_timeout=60)
    app.session_state['base']=base
    app.run()
    prefix='regret_'+base.run_id
    app.number_input(key=prefix+'_calls').set_value(1)
    app.checkbox(key=prefix+'_confirm').check()
    app.button(key=prefix+'_start').click().run()
    assert not app.exception
    result=app.session_state[prefix+'_result']
    assert result.analysis.status=='partial' and not result.analysis.recommended_ids
    assert any('待定 / 部分结果' in item.value for item in app.subheader)
