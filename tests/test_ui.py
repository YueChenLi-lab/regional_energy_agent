"""Exercise the real no-key UI workflow, including recomputation and export."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_demo_evaluate_revise_and_download(tmp_path, monkeypatch):
    monkeypatch.setenv("ENERGY_AGENT_OUTPUT_DIR", str(tmp_path))
    for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=120).run()
    assert not app.exception
    app.button(key="load_demo").click().run()
    assert not app.exception
    app.button(key="evaluate").click().run(timeout=120)
    assert not app.exception
    first = app.session_state["last_run"]
    assert first.comparison.recommended_id is not None
    assert len(first.scenarios) >= 4
    assert any("在本次评估的候选方案中" in item.value for item in app.success)
    for format_name in ("json", "csv", "markdown"):
        assert Path(first.files[format_name]).is_file()
    assert len(app.get("download_button")) >= 3
    app.number_input(key="budget").set_value(0.0)
    app.button(key="evaluate").click().run(timeout=120)
    assert not app.exception
    revised = app.session_state["last_run"]
    assert revised.input_version == first.input_version + 1
    assert revised.run_id != first.run_id
    assert revised.previous_run_id == first.run_id
    assert revised.task.constraints.budget_yuan == 0
    assert revised.comparison.recommended_id is None
    assert all(not scenario.validation.valid for scenario in revised.scenarios)
    assert any("没有通过全部约束" in item.value for item in app.warning)
    app.text_area(key="natural_language").set_value("将预算改为 800000 元")
    app.button(key="interpret").click().run()
    assert not app.exception
    assert any("不支持任意自然语言理解" in item.value for item in app.error)
    assert app.session_state["last_run"].run_id == revised.run_id


def test_zero_emission_limit_is_retained_after_widget_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("ENERGY_AGENT_OUTPUT_DIR", str(tmp_path))
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    app.button(key="load_demo").click().run()
    app.checkbox(key="emission_enabled").check()
    app.number_input(key="emission_limit").set_value(0.0)
    app.button(key="evaluate").click().run()
    assert not app.exception
    assert app.session_state["last_run"].comparison.recommended_id is None
    app.session_state["refresh_conditions"] = True
    app.run()
    assert app.number_input(key="emission_limit").value == 0.0
    assert app.checkbox(key="emission_enabled").value is True
