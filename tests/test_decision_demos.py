"""Real bounded demo computations and UI safety regressions; no paid APIs."""
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from energy_agent.agent import EnergyAgent, ToolRegistry
from energy_agent.counterfactual import digest
from energy_agent.data import make_demo_task
from energy_agent.decision_demos import demo_task, run_decision_demo
from energy_agent.decision_tools import decision_registry


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('No model/network requests in demos')
    monkeypatch.setattr(httpx.Client, 'send', forbidden)


def test_empty_repair_permission_is_chinese_and_does_not_call_tool(tmp_path, monkeypatch):
    base = EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    import energy_agent.counterfactual_ui as ui
    monkeypatch.setattr(ui, 'decision_registry', lambda: pytest.fail('Empty permissions must not call a tool'))
    app = AppTest.from_string('import streamlit as st\nfrom energy_agent.counterfactual_ui import render_counterfactual\nrender_counterfactual(st.session_state["base"])')
    app.session_state['base'] = base
    app.run().button(key='cf_search_'+base.run_id).click().run()
    assert not app.exception
    assert any('请至少选择一项' in e.value for e in app.error)
    assert not any('validation error' in e.value for e in app.error)
    assert 'cf_result_'+base.run_id not in app.session_state


def test_fresh_decision_registration_repairs_missing_optional_tool(tmp_path, monkeypatch):
    old_init = ToolRegistry.__init__
    def stale_init(self):
        old_init(self)
        self._tools.pop('evaluate_minimax_regret')
    monkeypatch.setattr(ToolRegistry, '__init__', stale_init)
    assert 'evaluate_minimax_regret' not in ToolRegistry().names
    assert 'evaluate_minimax_regret' in decision_registry().names
    with pytest.raises(ValueError, match='未注册的工具'):
        decision_registry().call('execute_python', {})
    # It is a real matrix solve through the repaired registry, not just a name.
    base, result = run_decision_demo('regret', tmp_path, 'missing-tool')
    assert result.base_run_id == base.run_id
    assert result.analysis.status == 'certified'
    assert len(result.cells) == 12 and all(c.validation.valid for c in result.cells)


@pytest.mark.parametrize('kind', ['repair', 'regret'])
def test_actual_demo_receipt_replay_and_input_preservation(kind, tmp_path, monkeypatch):
    task = demo_task(kind)
    fingerprint = digest(task)
    base, result = run_decision_demo(kind, tmp_path/'中文 空格', 'same-id')
    assert digest(base.task) == fingerprint == digest(demo_task(kind))
    assert len(base.task.data.timestamps) == 24 and base.task.demo
    assert all(Path(p).is_file() for p in result.files.values())
    if kind == 'repair':
        assert result.baseline_verification.feasibility == 'infeasible'
        assert len(result.paths) == 3
        assert all(p.boundary_precision_reached and p.final_validation.valid and p.locks_preserved for p in result.paths)
        assert result.solver_calls <= 128
    else:
        assert result.analysis.status == 'certified'
        assert result.solver_calls == 12
        assert all(c.capacities_fixed and c.validation.valid for c in result.cells)
    # A different process/session with the same ID restores the saved baseline,
    # then the existing tool receipt; neither part starts another optimization.
    def forbidden(*a, **k): pytest.fail('Identical demo must restore, not solve')
    monkeypatch.setattr(EnergyAgent, 'run', forbidden)
    base2, result2 = run_decision_demo(kind, tmp_path/'中文 空格', 'same-id')
    assert base2 == base and result2 == result


@pytest.mark.parametrize('kind', ['repair', 'regret'])
def test_demo_ui_opt_in_real_run_passive_refresh_and_project_unchanged(kind, tmp_path, monkeypatch):
    monkeypatch.setenv('ENERGY_AGENT_OUTPUT_DIR', str(tmp_path))
    app = AppTest.from_string('''import streamlit as st
from energy_agent.counterfactual_ui import render_counterfactual
from energy_agent.regret_ui import render_regret
render_counterfactual(None)
render_regret(None)
''', default_timeout=60)
    app.session_state['task'] = make_demo_task(hours=6)
    original = app.session_state['task'].model_copy(deep=True)
    prefix = 'decision_demo_'+kind
    app.run()
    assert not app.exception
    assert prefix+'_result' not in app.session_state
    app.button(key=prefix+'_load').click().run()
    assert not app.exception
    assert app.button(key=prefix+'_run').disabled
    assert not list(tmp_path.rglob('baseline.json'))  # loading is passive
    app.checkbox(key=prefix+'_confirm').check().run()
    app.button(key=prefix+'_run').click().run()
    assert not app.exception and not app.error
    base, result = app.session_state[prefix+'_result']
    assert result.base_run_id == base.run_id
    assert app.session_state['task'] == original
    assert 'last_run' not in app.session_state and 'annual_run' not in app.session_state
    assert not any('采用此路径' in b.label for b in app.button)
    assert len(app.get('download_button')) == (3 if kind == 'repair' else 4)
    def forbidden(*a, **k): pytest.fail('Refresh/duplicate must not solve')
    monkeypatch.setattr(EnergyAgent, 'run', forbidden)
    app.run().button(key=prefix+'_run').click().run()
    assert not app.exception and not app.error
    assert app.session_state[prefix+'_result'] == (base, result)
    assert app.session_state['task'] == original
    # Explicit new loading clears old authorization/results only in demo scope.
    app.button(key=prefix+'_load').click().run()
    assert not app.exception and app.button(key=prefix+'_run').disabled
    assert prefix+'_result' not in app.session_state and app.session_state['task'] == original


def test_empty_matrix_selection_does_not_call_tool(tmp_path, monkeypatch):
    base = EnergyAgent(tmp_path/'base').run(make_demo_task(hours=6))
    import energy_agent.regret_ui as ui
    monkeypatch.setattr(ui, 'decision_registry', lambda: pytest.fail('No candidate means no solve'))
    app = AppTest.from_string('import streamlit as st\nfrom energy_agent.regret_ui import render_regret\nrender_regret(st.session_state["base"])')
    app.session_state['base'] = base
    prefix = 'regret_'+base.run_id
    app.run()
    app.multiselect(key=prefix+'_candidates').set_value([])
    app.checkbox(key=prefix+'_confirm').check()
    app.button(key=prefix+'_start').click().run()
    assert not app.exception and any('至少选择一个固定配置' in e.value for e in app.error)
    assert prefix+'_result' not in app.session_state


def test_published_demo_evidence_hashes_and_complete_witness_archive():
    import hashlib
    import json
    from zipfile import ZipFile
    root = Path(__file__).resolve().parents[1]/'docs'/'decision_demo_evidence'
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    with ZipFile(root/'witnesses.zip') as archive:
        assert archive.namelist() and all(Path(p).suffix in ('.json', '.csv', '.md') for p in archive.namelist())
        for name, expected in manifest.items():
            content = archive.read(name.removeprefix('witnesses/')) if name.startswith('witnesses/') else (root/name).read_bytes()
            assert hashlib.sha256(content).hexdigest() == expected, name
        # All reported final solutions and matrix cells have independently
        # checkable saved dispatch witnesses, not just a summary JSON.
        repair = json.loads((root/'repair_result.json').read_text(encoding='utf-8'))
        regret = json.loads((root/'regret_result.json').read_text(encoding='utf-8'))
        output_prefix = 'outputs/decision_demo_validation/'
        for item in repair['paths']+regret['cells']:
            member = item['result_file'].removeprefix(output_prefix)
            assert hashlib.sha256(archive.read(member)).hexdigest() == item['result_sha256']
