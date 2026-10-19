"""Presentation regressions exercise actual workflows; never use paid services."""
import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent
from energy_agent.data import make_demo_task
from energy_agent.llm import OpenAICompatibleClient

APP = Path(__file__).resolve().parents[1] / 'competition_app.py'


@pytest.fixture
def offline(tmp_path, monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR', str(tmp_path / 'results'))
    def forbidden(*args, **kwargs):
        raise AssertionError('The competition console must not initiate HTTP on refresh')
    monkeypatch.setattr(httpx.Client, 'send', forbidden)


def html(app):
    return '\n'.join(item.proto.body for item in app.get('html'))


def test_empty_navigation_and_archived_evidence_do_not_solve_or_contact_model(offline, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('No automatic optimization')
    monkeypatch.setattr(EnergyAgent, 'run', forbidden)
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert '待评估' in html(app)
    assert not any(k in app.session_state for k in ('last_run', 'annual_run', 'real_run'))
    app.button(key='console_experiment').click().run()
    assert app.session_state['console_navigation'] == '实验验证'
    assert not app.exception
    assert '本页面未重新求解' in html(app)
    frame = next(d.value for d in app.dataframe if '峰值 kW' in d.value.columns)
    assert len(frame) == 3 and frame.iloc[0]['峰值 kW'] == 4907.06
    assert any('不是实时模型输出' in x.value for x in app.info)
    app.button(key='console_start').click().run()
    assert app.session_state['console_navigation'] == '优化结果'


def test_actual_demo_revision_exports_and_state_across_tabs(offline, tmp_path):
    app = AppTest.from_file(str(APP), default_timeout=60).run()
    app.button(key='load_demo').click().run()
    assert app.session_state['last_run'] is None
    app.button(key='evaluate').click().run()
    assert not app.exception
    first = app.session_state['last_run']
    chosen = next(s for s in first.scenarios if s.candidate.candidate_id == first.comparison.recommended_id)
    assert f'{chosen.investment_yuan:,.2f}' in html(app)
    assert '未启用' in html(app)  # Weekly demo does not invent an NPV.
    assert len(app.get('download_button')) >= 6
    assert all(Path(first.files[k]).is_file() for k in ('json', 'csv', 'markdown'))
    for page in ('证据详情', '问答工作台', '优化结果'):
        app.session_state['console_navigation'] = page
        app.run()
        assert not app.exception
        assert app.session_state['last_run'].run_id == first.run_id
    app.number_input(key='budget').set_value(0.0)
    app.button(key='evaluate').click().run()
    revised = app.session_state['last_run']
    assert not app.exception
    assert revised.input_version == first.input_version + 1
    assert revised.previous_run_id == first.run_id
    assert revised.task.constraints.budget_yuan == 0
    assert revised.comparison.recommended_id is None
    assert any('没有通过全部约束' in x.value for x in app.warning)


def test_missing_export_and_untrusted_labels_do_not_break_or_inject(offline, tmp_path):
    run = EnergyAgent(tmp_path / 'base').run(make_demo_task(hours=6))
    run.scenarios[0].candidate.name = '<img src=x onerror=alert(1)>'
    run.files = {'csv': str(tmp_path / 'absent.csv')}
    app = AppTest.from_file(str(APP))
    app.session_state['last_run'] = run
    app.run()
    assert not app.exception
    assert '<img src=x' not in html(app)
    assert '&lt;img src=x onerror=alert(1)&gt;' in html(app)
    assert any('原导出文件不在当前机器' in c.value for c in app.caption)


def test_workbench_uses_existing_clarification_recompute_and_request_protection(tmp_path, monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR', str(tmp_path / 'console'))
    base = EnergyAgent(tmp_path / 'base').run(make_demo_task(hours=6))
    calls = []
    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        name = body['tools'][0]['function']['name']
        ctx = json.loads(body['messages'][1]['content'])
        if name == 'planning_intent':
            c = ctx['authorized_contract']
            result = {'operation': 'clarify' if c['missing'] else 'modify', 'patch': None if c['missing'] else c['patch']}
        else:
            result = {'run_id': ctx['run_id'], 'conclusion': ctx['conclusion'],
                      'claims': [{'reference': 'input_version', 'value': ctx['current_facts']['input_version']}]}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'tool_calls', 'message': {
            'content': None, 'tool_calls': [{'type': 'function', 'function': {'name': name, 'arguments': json.dumps(result)}}]}}]})
    client = OpenAICompatibleClient('https://api.deepseek.com', 'fixture-model', 'artificial-key',
                                  client=httpx.Client(transport=httpx.MockTransport(handle)))
    app = AppTest.from_file(str(APP), default_timeout=60)
    app.session_state['annual_run'] = base
    app.session_state['planning_llm'] = client
    app.session_state['assistant_session_id'] = 'console-test-' + tmp_path.name
    app.run()
    assert not app.exception and not calls
    app.button(key='assistant_submit').click().run()
    assert not app.exception and len(calls) == 1
    assert app.session_state['agent_reply'].status == 'clarification'
    assert app.session_state['annual_run'].run_id == base.run_id
    assert any('预算少一点' in m.value for m in app.chat_message[0].markdown)
    app.text_area(key='assistant_answer').set_value('减少15%。')
    app.button(key='assistant_answer_submit').click().run()
    assert not app.exception
    reply = app.session_state['agent_reply']
    assert reply.run.run_id != base.run_id
    assert reply.run.task.constraints.budget_yuan == base.task.constraints.budget_yuan * .85
    assert reply.heat_unchanged and reply.explanation_verified
    assert app.session_state['annual_run'].run_id == reply.run.run_id
    assert reply.run.run_id in '\n'.join(c.value for c in app.caption)
    count = len(calls)
    app.button(key='assistant_resume').click().run()
    assert not app.exception and len(calls) == count
    assert app.session_state['annual_run'].run_id == reply.run.run_id
