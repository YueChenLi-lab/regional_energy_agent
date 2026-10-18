"""Explicit UI actions using a simulated service; no paid requests."""
import json
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent
from energy_agent.data import make_demo_task
from energy_agent.llm import OpenAICompatibleClient


def test_ui_clarification_restore_answer_and_duplicate_without_real_network(tmp_path,monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path))
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    calls=[]
    def handle(req):
        body=json.loads(req.content);calls.append(body)
        name=body['tools'][0]['function']['name'];ctx=json.loads(body['messages'][1]['content'])
        if name=='planning_intent':
            c=ctx['authorized_contract']
            result={'operation':'clarify' if c['missing'] else 'modify','patch':None if c['missing'] else c['patch']}
        else:
            result={'run_id':ctx['run_id'],'conclusion':ctx['conclusion'],'claims':[{'reference':'input_version','value':ctx['current_facts']['input_version']}]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[{'type':'function','function':{'name':name,'arguments':json.dumps(result)}}]}}]})
    model=OpenAICompatibleClient('https://api.deepseek.com','fixture-model','artificial-key',client=httpx.Client(transport=httpx.MockTransport(handle)))
    app=AppTest.from_string('import streamlit as st\nfrom energy_agent.planning_ui import render_model\nrender_model(st.session_state["test_run"])',default_timeout=30)
    app.session_state['test_run']=base;app.session_state['planning_llm']=model
    app.run();assert not app.exception and len(calls)==0
    app.button(key='assistant_submit').click().run()
    assert not app.exception
    first=app.session_state['agent_reply'];assert first.status=='clarification' and len(calls)==1
    app.session_state['agent_reply']=None
    app.button(key='assistant_restore').click().run()
    assert not app.exception and len(calls)==1
    assert app.session_state['agent_reply'].pending.base_run_id==base.run_id
    app.text_area(key='assistant_answer').set_value('减少15%。')
    app.button(key='assistant_answer_submit').click().run()
    assert not app.exception
    reply=app.session_state['agent_reply']
    assert reply.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.85
    assert reply.heat_unchanged and reply.explanation_verified and len(calls)==3
    assert '基准运行' in reply.text and '保持：' in reply.text and '变化' in reply.text
    app.button(key='assistant_resume').click().run()
    assert not app.exception
    assert app.session_state['agent_reply'].run.run_id==reply.run.run_id and len(calls)==3
