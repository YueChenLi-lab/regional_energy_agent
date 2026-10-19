"""Real UI flows with deterministic computations and simulated model transport."""
import hashlib
import json
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent, ToolRegistry
from energy_agent.data import make_demo_task
from energy_agent.llm import OpenAICompatibleClient

ROOT=Path(__file__).resolve().parents[1]


def test_archived_24h_and_8760h_boards_passive_downloads_and_navigation(tmp_path,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Browsing cannot call a solver, tool or network')
    monkeypatch.setattr(EnergyAgent,'run',forbidden)
    monkeypatch.setattr(ToolRegistry,'call',forbidden)
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    app=AppTest.from_file(str(ROOT/'competition_app.py'),default_timeout=60).run()
    assert not app.exception and len(app.tabs)==5
    for name in ['反事实 · 24小时三路径','后悔决策 · 合成24小时3×4','后悔决策 · 混合8760小时2×3']:
        app.selectbox(key='dw_archive_select').set_value(name).run()
        assert not app.exception
        assert any('不是当前项目的新计算' in info.value for info in app.info)
        assert len(app.get('download_button'))>=5
        assert not any(b.key and b.key.startswith('cf_adopt_') for b in app.button)
        assert not any(k in app.session_state for k in ('annual_run','last_run','real_run'))
    app.run()
    assert not app.exception


def test_one_render_model_and_hint_is_only_navigation(tmp_path,monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path))
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    import energy_agent.planning_ui as module
    calls=[];original=module.render_model
    def counted(run):calls.append(run.run_id);return original(run)
    monkeypatch.setattr(module,'render_model',counted)
    def forbidden(*a,**k):raise AssertionError('No implicit execution')
    monkeypatch.setattr(ToolRegistry,'call',forbidden)
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    app=AppTest.from_file(str(ROOT/'competition_app.py'),default_timeout=60)
    app.session_state['annual_run']=base
    app.run()
    assert not app.exception and calls==[base.run_id]
    assert len([b for b in app.button if b.key=='assistant_submit'])==1
    app.text_input(key='dw_hint_text').set_value('预算不够，如何修复？').run()
    assert not app.exception and calls==[base.run_id]*2
    assert any('仅为提示' in c.value for c in app.caption)
    app.session_state['dw_intent']='counterfactual'
    app.run()
    app.button(key='dw_go_counterfactual').click().run()
    assert not app.exception and app.session_state['console_navigation']=='优化结果'
    assert app.session_state['annual_run']==base


def test_workspace_multiturn_restores_pinned_base_edits_cancels_without_real_api(tmp_path,monkeypatch):
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
            result={'run_id':ctx['run_id'],'conclusion':ctx['conclusion'],
                    'claims':[{'reference':'input_version','value':ctx['current_facts']['input_version']}]}
        return httpx.Response(200,json={'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[{'type':'function','function':{'name':name,'arguments':json.dumps(result)}}]}}]})
    client=OpenAICompatibleClient('https://api.deepseek.com','fixture-model','artificial-key',
        client=httpx.Client(transport=httpx.MockTransport(handle)))
    app=AppTest.from_file(str(ROOT/'competition_app.py'),default_timeout=60)
    app.session_state['annual_run']=base;app.session_state['planning_llm']=client
    app.session_state['assistant_session_id']='v05-session'
    app.run()
    app.button(key='assistant_submit').click().run()
    reply=app.session_state['agent_reply']
    assert not app.exception and len(calls)==1 and reply.status=='clarification'
    app.session_state['agent_reply']=None
    app.button(key='assistant_restore').click().run()
    assert not app.exception and len(calls)==1
    app.text_area(key='assistant_answer').set_value('减少15%')
    app.button(key='assistant_answer_submit').click().run()
    reply=app.session_state['agent_reply'];assert not app.exception
    assert reply.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.85
    assert reply.heat_unchanged and reply.explanation_verified and len(calls)==3
    html='\n'.join(x.proto.body for x in app.get('html'))
    assert '修改前后差异' in html and '差值为当前减基准' in html
    # A fresh AppTest simulates a browser process restart while receipt files remain.
    fresh=AppTest.from_file(str(ROOT/'competition_app.py'),default_timeout=60)
    fresh.session_state['annual_run']=reply.run;fresh.session_state['planning_llm']=client
    fresh.session_state['assistant_session_id']='v05-session';fresh.session_state['annual_request_id']=reply.request_id
    fresh.run();fresh.button(key='assistant_restore').click().run()
    assert not fresh.exception and len(calls)==3
    fresh.text_area(key='assistant_edit_text_'+reply.pending.answers[0]['turn_id']).set_value('减少10%')
    fresh.button(key='assistant_edit_submit').click().run()
    edited=fresh.session_state['agent_reply']
    assert not fresh.exception and edited.run.task.constraints.budget_yuan==base.task.constraints.budget_yuan*.9
    assert edited.pending.base_run_id==base.run_id
    count=len(calls)
    fresh.button(key='assistant_resume').click().run()
    assert len(calls)==count
    fresh.button(key='assistant_cancel').click().run()
    assert not fresh.exception and fresh.session_state['agent_reply'].status=='cancelled' and len(calls)==count


def test_snapshot_path_traversal_or_wrong_binding_not_read(tmp_path,monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR',str(tmp_path))
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    directory=tmp_path/'ui_conversations'/hashlib.sha256(b'session').hexdigest()/'receipts'
    directory.mkdir(parents=True)
    name=hashlib.sha256(b'req').hexdigest()+'.base1.json'
    (directory/name).write_text(base.model_dump_json(),encoding='utf-8')
    app=AppTest.from_string('''import streamlit as st
from energy_agent.console.chat_workspace import _load_base
st.session_state['loaded']=_load_base(st.session_state['reply'])
''')
    app.session_state['assistant_session_id']='session'
    app.session_state['reply']={'pending':{'base_file':name,'request_id':'req','generation':1,'base_run_id':base.run_id,'input_version':base.input_version}}
    app.run();assert not app.exception and app.session_state['loaded']==base
    reply=app.session_state['reply'];reply['pending']['base_file']='../'+name
    app.session_state['reply']=reply
    app.run();assert not app.exception and app.session_state['loaded'] is None
    reply['pending']['base_file']=name;reply['pending']['base_run_id']='wrong'
    app.session_state['reply']=reply
    app.run();assert app.session_state['loaded'] is None


def test_preview_is_gated_and_not_imported_by_production(monkeypatch):
    monkeypatch.delenv('ENERGY_AGENT_DEV_PREVIEW',raising=False)
    preview=AppTest.from_file(str(ROOT/'dev_preview_app.py')).run()
    assert not preview.exception and preview.error
    monkeypatch.setenv('ENERGY_AGENT_DEV_PREVIEW','1')
    preview.run()
    assert not preview.exception
    assert any('全部数值均为虚构' in h.proto.body for h in preview.get('html'))
    for path in ['app.py','competition_app.py','energy_agent/console/app.py','energy_agent/console/chat_workspace.py']:
        assert 'dev_preview' not in (ROOT/path).read_text(encoding='utf-8')


def test_default_alias_and_legacy_entries_all_work_offline(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Entry load must not solve or contact service')
    monkeypatch.setattr(EnergyAgent,'run',forbidden)
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    for filename in ['app.py','competition_app.py','legacy_app.py']:
        app=AppTest.from_file(str(ROOT/filename)).run()
        assert not app.exception and app.radio(key='workflow')
        if filename!='legacy_app.py':assert len(app.tabs)==5


def test_study_reply_displays_actual_saved_points_without_rerunning(tmp_path,monkeypatch):
    from energy_agent.frontier import StudyResult
    from energy_agent.conversation import ConversationReply
    raw=json.loads((ROOT/'docs/v03_evidence/study.json').read_text(encoding='utf-8'))
    raw.pop('baseline')
    raw['files']={'json':str(ROOT/'docs/v03_evidence/study.json')}
    study=StudyResult.model_validate(raw)
    base=EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    def forbidden(*a,**k):raise AssertionError('Saved scan must be displayed, not rerun')
    monkeypatch.setattr(ToolRegistry,'call',forbidden)
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    app=AppTest.from_file(str(ROOT/'competition_app.py'))
    app.session_state['annual_run']=base
    app.session_state['agent_reply']=ConversationReply(status='completed',text=study.note,request_id='archived-study',study=study)
    app.run()
    assert not app.exception
    frame=next(f.value for f in app.dataframe if 'annual_emissions_kg' in f.value.columns and 'npv_cost_yuan' in f.value.columns)
    assert len(frame)==len(study.points)
    assert any(study.baseline_run_id in c.value for c in app.caption)
