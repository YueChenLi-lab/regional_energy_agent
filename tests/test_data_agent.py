import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from energy_agent.agent import EnergyAgent, ToolRegistry, revise_task
from energy_agent.cli import main
from energy_agent.data import check_data, load_csv, make_demo_task, validate_inputs
from energy_agent.schemas import RunResult, RunState, SolverOptions, TaskPatch, TaskRequest, TimeSeriesData


def test_demo_quality_and_extensible_horizon():
    task = make_demo_task(hours=8760)
    assert validate_inputs(task).ready
    assert len(task.data.timestamps) == 8760
    for t, pv, electric, heat in zip(task.data.timestamps, task.data.pv_per_kw, task.data.electric_load_kw, task.data.heat_load_kw_th):
        assert electric >= 0 and heat >= 0 and 0 <= pv <= 1
        if t.hour <= 6 or t.hour >= 18:
            assert pv == 0
    assert all(s.category == "synthetic" for s in task.sources)


@pytest.mark.parametrize("change,fragment", [
    ("duplicate", "重复"), ("gap", "间隔"), ("unit", "单位"), ("length", "长度"), ("timezone", "时区"),
])
def test_quality_errors_never_silently_correct_data(change, fragment):
    data = make_demo_task(hours=4).data
    if change == "duplicate":
        data.timestamps[1] = data.timestamps[0]
    elif change == "gap":
        data.timestamps[1] += pd.Timedelta(minutes=10)
    elif change == "unit":
        data.units["electric_load_kw"] = "MW"
    elif change == "length":
        data.electric_load_kw.pop()
    else:
        data.timestamps[0] = data.timestamps[0].replace(tzinfo=None)
    assert any(fragment in issue.message for issue in check_data(data))


@pytest.mark.parametrize("field,value", [("electric_load_kw", -1), ("pv_per_kw", 1.01), ("heat_load_kw_th", float("nan")), ("electricity_price", float("inf")), ("gas_price", None)])
def test_invalid_numeric_inputs_are_rejected(field, value):
    payload = make_demo_task(hours=4).data.model_dump()
    payload[field][0] = value
    with pytest.raises(ValidationError):
        TimeSeriesData.model_validate(payload)


def test_csv_roundtrip_and_missing_values(tmp_path):
    data = make_demo_task(hours=5).data
    frame = pd.DataFrame({"timestamp": [t.isoformat() for t in data.timestamps], **{field: getattr(data, field) for field in data.units}})
    path = tmp_path / "data.csv"
    frame.to_csv(path, index=False)
    metadata = {name: getattr(data, name) for name in ("step_hours", "units", "source_ids")}
    restored = load_csv(path, metadata)
    assert restored.electric_load_kw == pytest.approx(data.electric_load_kw)
    frame.loc[2, "heat_load_kw_th"] = np.nan
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="缺失值"):
        load_csv(path, metadata)
    frame["cooling_load_kw"] = 1
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="未支持列"):
        load_csv(path, metadata)


def test_missing_inputs_and_unsupported_demands_are_structured(tmp_path):
    result = EnergyAgent(tmp_path).run({})
    assert result.state == RunState.NEEDS_INPUT
    assert {i.field for i in result.issues} >= {"data", "devices", "constraints", "candidates"}
    assert not result.scenarios
    request = make_demo_task().model_dump()
    request["unsupported_demands"] = ["供冷"]
    result = EnergyAgent(tmp_path).run(request)
    assert result.state == RunState.NEEDS_INPUT
    assert any(i.kind == "unsupported" and "供冷" in i.message for i in result.issues)
    request["cooling_kw"] = 10
    result = EnergyAgent(tmp_path).run(request)
    assert result.state == RunState.NEEDS_INPUT
    assert any(i.field == "cooling_kw" for i in result.issues)


def test_missing_parameter_budget_and_unknown_source_are_not_assumed(tmp_path):
    payload = make_demo_task(hours=2).model_dump()
    payload["devices"].pop("hp_cop")
    result = EnergyAgent(tmp_path).run(payload)
    assert any(i.field == "devices.hp_cop" and i.kind == "missing" for i in result.issues)
    task = TaskRequest.model_validate(make_demo_task(hours=2).model_dump())
    task.constraints.budget_yuan = None
    task.sources = []
    checked = validate_inputs(task)
    assert not checked.ready
    assert any(i.field == "constraints.budget_yuan" for i in checked.issues)
    assert any(i.field == "sources" for i in checked.issues)


def test_agent_roundtrip_exports_logs_versions_and_real_recalculation(tmp_path, monkeypatch):
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    agent = EnergyAgent(tmp_path)
    task = make_demo_task()
    result = agent.run(task)
    assert result.state == RunState.COMPLETED
    assert result.comparison.recommended_id == "D"
    assert len(result.scenarios) == 4
    assert len(result.tool_calls) == 12
    assert all(call.status == "success" and Path(call.result_file).is_file() for call in result.tool_calls)
    assert set(agent.registry.names) == {call.tool_name for call in result.tool_calls}
    saved = RunResult.model_validate_json(Path(result.files["json"]).read_text())
    assert saved == result
    table = pd.read_csv(result.files["csv"])
    assert len(table) == 4
    assert table.candidate_id.tolist() == result.comparison.ranked_ids
    assert table["rank"].tolist() == [1, 2, 3, 4]
    assert len(pd.read_csv(result.files["dispatch_D"])) == 168
    report = Path(result.files["markdown"]).read_text()
    assert "合成演示数据" in report and "在本次评估的候选方案中" in report
    assert "generate_report" in report
    changed = revise_task(task, TaskPatch(budget_yuan=50000), parent_run_id=result.run_id)
    second = agent.run(changed, previous=result)
    assert second.input_version == 2 and second.run_id != result.run_id
    assert second.comparison.recommended_id == "A"
    assert sum(s.validation.valid for s in second.scenarios) == 1
    assert second.changes["previous_recommended"] == "D"
    assert second.changes["current_recommended"] == "A"
    assert task.constraints.budget_yuan == 1200000  # Earlier version untouched.
    scaled = revise_task(changed, TaskPatch(demand_scale=0.5), second.run_id)
    third = agent.run(scaled, previous=second)
    assert third.input_version == 3
    assert third.scenarios[0].validation.metrics.grid_kwh == pytest.approx(second.scenarios[0].validation.metrics.grid_kwh / 2)
    assert third.scenarios[0].validation.metrics.gas_kwh_lhv == pytest.approx(second.scenarios[0].validation.metrics.gas_kwh_lhv / 2)
    assert any("全部已提供时间区间" in p for p in scaled.sources[-1].processing)


def test_all_budget_rejected_and_carbon_rejected_reports(tmp_path):
    agent = EnergyAgent(tmp_path)
    task = revise_task(make_demo_task(hours=24), TaskPatch(budget_yuan=0))
    result = agent.run(task)
    assert result.state == RunState.COMPLETED and result.comparison.recommended_id is None
    assert all(s.dispatch.status == "rejected" for s in result.scenarios)
    task = revise_task(make_demo_task(hours=24), TaskPatch(emission_limit_kg=0))
    result = agent.run(task)
    assert result.state == RunState.COMPLETED and result.comparison.recommended_id is None
    assert all(s.dispatch.status == "infeasible" for s in result.scenarios)


def test_registry_rejects_arbitrary_calls_and_invalid_tool_output():
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="未注册"):
        registry.call("shell", {"cmd": "anything"})
    with pytest.raises(ValidationError):
        registry.call("solve_dispatch", {"task": {}})


def test_rejected_input_preserves_valid_identity_version_and_provenance(tmp_path):
    task = make_demo_task(hours=2).model_dump(mode="json")
    task.update(version=5, parent_run_id="previous-run", project_name="验证拒绝输入的追溯")
    task["devices"]["hp_cop"] = None
    result = EnergyAgent(tmp_path).run(task)
    assert result.state == RunState.NEEDS_INPUT
    assert result.input_version == 5
    assert result.task.project_name == task["project_name"]
    assert result.previous_run_id == "previous-run"
    assert len(result.task.sources) == 5
    assert result.task.demo and result.task.data is not None
    assert result.task.devices is None
    assert result.tool_calls[0].input_version == 5
    assert "demo-equipment" in result.tool_calls[0].source_ids
    assert any(i.field == "devices.hp_cop" for i in result.issues)


def test_nondefault_solver_options_are_preserved_in_result_and_report(tmp_path):
    options = SolverOptions(time_limit_seconds=7, mip_rel_gap=0.03)
    result = EnergyAgent(tmp_path, options=options).run(make_demo_task(hours=2))
    saved = RunResult.model_validate_json(Path(result.files["json"]).read_text())
    assert saved.solver_options == options
    report = Path(result.files["markdown"]).read_text()
    assert "时限 7 秒" in report and "容差 0.03" in report


def test_cli_demo_and_revision(tmp_path, capsys):
    task_path = tmp_path / "task.json"
    assert main(["demo", "--hours", "12", "--output", str(tmp_path / "runs"), "--task-out", str(task_path)]) == 0
    result_paths = list((tmp_path / "runs").glob("*/result.json"))
    assert len(result_paths) == 1
    assert main(["revise", "--run", str(result_paths[0]), "--budget", "0", "--output", str(tmp_path / "changed")]) == 0
    result = json.loads(next((tmp_path / "changed").glob("*/result.json")).read_text())
    assert result["input_version"] == 2
    assert result["comparison"]["recommended_id"] is None
    assert "合成演示数据" in capsys.readouterr().out
