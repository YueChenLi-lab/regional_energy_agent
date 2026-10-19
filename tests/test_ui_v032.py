from pathlib import Path
import httpx
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent
from energy_agent.data import make_demo_task
from energy_agent.llm import RuleClient


def test_prepare_view_and_saved_peak_summary_are_readable_and_never_contact_model(tmp_path,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Read-only prepare/peak views must not send HTTP')
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path/'ui'))
    task=make_demo_task(hours=6);task.constraints.budget_yuan=10000000
    base=EnergyAgent(tmp_path/'base').run(task)
    app=AppTest.from_string('import streamlit as st\nfrom energy_agent.planning_ui import render_model\nrender_model(st.session_state["run"])',default_timeout=30)
    app.session_state['run']=base;app.session_state['planning_llm']=RuleClient()
    app.run();app.text_area(key='annual_nl').set_value('预算增加到1200万元，供热不变').run()
    assert not app.exception
    assert any('准备修改' in x.value and '12,000,000.00元' in x.value for x in app.markdown)
    assert any('保持：' in x.value for x in app.caption)
    assert any('比较口径A' in x.value for x in app.caption)
    app.text_area(key='annual_nl').set_value('不要把预算减少20%').run()
    assert not app.exception and any('尚需澄清' in x.value for x in app.caption)
    peak=AppTest.from_string('from energy_agent.planning_ui import render_peak_experiment_view\nrender_peak_experiment_view()',default_timeout=30).run()
    peak.button(key='peak_study_view').click().run()
    assert not peak.exception and any('未显示明显敏感' in x.value for x in peak.info)
    assert len(peak.dataframe[0].value)==3
