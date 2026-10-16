"""Business and physics checks, including independent tamper detection."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from energy_agent.data import make_demo_task
from energy_agent.evaluation import compare_scenarios, validate_solution
from energy_agent.optimization import solve_dispatch
from energy_agent.planning import investment_yuan
from energy_agent.schemas import (ComparisonRequest, ScenarioResult, SolveRequest,
                                  ValidationRequest)


def solve_and_check(task, candidate):
    result = solve_dispatch(SolveRequest(task=task, candidate=candidate))
    validation = validate_solution(ValidationRequest(task=task, candidate=candidate, dispatch=result))
    return result, validation


@pytest.fixture(scope="module")
def standard_scenarios():
    task = make_demo_task(seed=42, hours=168)
    scenarios = []
    for candidate in task.candidates:
        result, validation = solve_and_check(task, candidate)
        scenarios.append(ScenarioResult(candidate=candidate,
                         investment_yuan=investment_yuan(candidate, task.devices),
                         dispatch=result, validation=validation))
    return task, scenarios


def test_standard_all_candidates_obey_physics_and_period_accounting(standard_scenarios):
    task, scenarios = standard_scenarios
    for scenario in scenarios:
        assert scenario.dispatch.status == "optimal"
        assert scenario.validation.valid
        assert all(check.passed for check in scenario.validation.checks)
        metrics = scenario.validation.metrics
        assert metrics.period_hours == 168
        assert metrics.electric_load_kwh == pytest.approx(sum(task.data.electric_load_kw))
        assert metrics.heat_load_kwh_th == pytest.approx(sum(task.data.heat_load_kw_th))
        assert metrics.operating_cost_yuan == pytest.approx(scenario.dispatch.objective_yuan)
        assert metrics.supply_satisfied
        for t, point in enumerate(scenario.dispatch.points):
            assert point.grid_kw + point.pv_used_kw + point.discharge_kw == pytest.approx(
                task.data.electric_load_kw[t]
                + point.hp_electric_kw + point.charge_kw, abs=1e-5)
            if point.timestamp.hour <= 6 or point.timestamp.hour >= 18:
                assert point.pv_used_kw == pytest.approx(0, abs=1e-6)
            assert min(point.charge_kw, point.discharge_kw) <= 1e-6
        assert scenario.dispatch.soc_kwh[-1] == pytest.approx(scenario.dispatch.soc_kwh[0])
    comparison = compare_scenarios(ComparisonRequest(scenarios=scenarios))
    assert comparison.ranked_ids == [s.candidate.candidate_id for s in sorted(
        scenarios, key=lambda s: s.validation.metrics.operating_cost_yuan)]
    assert comparison.recommended_id == "D"
    assert "在本次评估的候选方案中" in comparison.explanation
    # Storage trades emissions against cost under the synthetic tariff/factors.
    assert scenarios[3].validation.metrics.operating_cost_yuan < scenarios[2].validation.metrics.operating_cost_yuan
    assert scenarios[3].validation.metrics.emissions_kg > scenarios[2].validation.metrics.emissions_kg


def test_budget_below_every_candidate_returns_no_feasible_candidate():
    task = make_demo_task(hours=8)
    task.constraints.budget_yuan = 0
    scenarios = []
    for candidate in task.candidates:
        result, validation = solve_and_check(task, candidate)
        assert result.status == "rejected"
        assert "预算" in "".join(result.reasons)
        assert not validation.valid
        assert validation.metrics is None
        scenarios.append(ScenarioResult(candidate=candidate,
                         investment_yuan=investment_yuan(candidate, task.devices),
                         dispatch=result, validation=validation))
    assert compare_scenarios(ComparisonRequest(scenarios=scenarios)).recommended_id is None


def test_insufficient_heating_is_explained_by_precheck():
    task = make_demo_task(hours=4)
    candidate = task.candidates[0].model_copy(update={"boiler_kw_th": 1.0})
    result, validation = solve_and_check(task, candidate)
    assert result.status == "infeasible"
    assert "最大热负荷" in result.reasons[0]
    assert not validation.valid


def test_zero_carbon_cap_makes_positive_fossil_supply_infeasible():
    task = make_demo_task(hours=12)
    task.constraints.emission_limit_kg = 0
    result, validation = solve_and_check(task, task.candidates[0])
    assert result.status == "infeasible"
    assert "排放上限 0" in "".join(result.reasons)
    assert not validation.valid
    assert result.points == []  # No hidden curtailment or load-shedding slack.


def test_binding_carbon_cap_changes_actual_dispatch(standard_scenarios):
    original, scenarios = standard_scenarios
    task = original.model_copy(deep=True)
    task.constraints.emission_limit_kg = 5800
    result, validation = solve_and_check(task, task.candidates[2])
    baseline = scenarios[2].validation.metrics
    assert result.status == "optimal" and validation.valid
    assert validation.metrics.emissions_kg == pytest.approx(5800, abs=1e-5)
    assert validation.metrics.gas_kwh_lhv < baseline.gas_kwh_lhv
    assert validation.metrics.grid_kwh > baseline.grid_kwh
    assert validation.metrics.operating_cost_yuan > baseline.operating_cost_yuan


def test_site_and_grid_limit_prechecks():
    task = make_demo_task(hours=4)
    task.constraints.pv_limit_kw = 1
    result, _ = solve_and_check(task, task.candidates[1])
    assert result.status == "rejected"
    assert "场地" in result.reasons[0]
    task.constraints.grid_limit_kw = 0
    result, _ = solve_and_check(task, task.candidates[0])
    assert result.status == "infeasible"
    assert "供电" in result.message


def test_arbitrary_half_hour_step_converts_power_to_energy():
    task = make_demo_task(hours=6)
    data = task.data
    data.step_hours = 0.5
    data.timestamps = pd.date_range(data.timestamps[0], periods=6, freq="30min").to_pydatetime().tolist()
    data.electric_load_kw = [10.0] * 6
    data.heat_load_kw_th = [18.0] * 6
    data.electricity_price = [1.0] * 6
    data.gas_price = [0.3] * 6
    result, validation = solve_and_check(task, task.candidates[0])
    assert result.status == "optimal" and validation.valid
    metrics = validation.metrics
    assert metrics.period_hours == 3
    assert metrics.grid_kwh == pytest.approx(30)
    assert metrics.gas_kwh_lhv == pytest.approx(60)
    assert metrics.operating_cost_yuan == pytest.approx(48)
    assert metrics.heat_load_kwh_th == pytest.approx(54)


def test_battery_cannot_profit_from_consuming_initial_energy():
    task = make_demo_task(hours=4)
    task.data.electric_load_kw = [10.0] * 4
    task.data.heat_load_kw_th = [0.0] * 4
    task.data.electricity_price = [1.0] * 4
    candidate = task.candidates[3].model_copy(update={"pv_kw": 0.0})
    result, validation = solve_and_check(task, candidate)
    assert result.status == "optimal" and validation.valid
    assert result.soc_kwh[0] == pytest.approx(50)
    assert result.soc_kwh[-1] == pytest.approx(50)
    assert validation.metrics.grid_kwh == pytest.approx(40)
    assert validation.metrics.operating_cost_yuan == pytest.approx(40)


@pytest.mark.parametrize("field,check_name", [
    ("grid_kw", "electric_balance"), ("hp_electric_kw", "heat_pump_cop"),
    ("gas_kw_lhv", "boiler_efficiency"), ("curtailment_kw", "pv_allocation"),
    ("boiler_heat_kw_th", "heat_balance"),
])
def test_independent_checker_rejects_modified_dispatch(standard_scenarios, field, check_name):
    task, scenarios = standard_scenarios
    scenario = scenarios[3]
    damaged = scenario.dispatch.model_copy(deep=True)
    setattr(damaged.points[0], field, getattr(damaged.points[0], field) + 10)
    validation = validate_solution(ValidationRequest(task=task, candidate=scenario.candidate, dispatch=damaged))
    assert not validation.valid
    assert not next(c for c in validation.checks if c.name == check_name).passed


def test_checker_detects_simultaneous_flows_and_terminal_energy_theft(standard_scenarios):
    task, scenarios = standard_scenarios
    candidate = scenarios[3].candidate
    damaged = scenarios[3].dispatch.model_copy(deep=True)
    damaged.points[0].charge_kw += 10
    damaged.points[0].discharge_kw += 10
    damaged.soc_kwh[-1] -= 5
    validation = validate_solution(ValidationRequest(task=task, candidate=candidate, dispatch=damaged))
    failed = {c.name for c in validation.checks if not c.passed}
    assert {"no_simultaneous_charge_discharge", "soc_terminal", "soc_dynamics"} <= failed
    scenario = ScenarioResult(candidate=candidate, investment_yuan=800050,
                              dispatch=damaged, validation=validation)
    assert compare_scenarios(ComparisonRequest(scenarios=[scenario])).recommended_id is None


def test_fixed_seed_and_input_reproduce_key_metrics(standard_scenarios):
    original_task, scenarios = standard_scenarios
    repeated = make_demo_task(seed=42, hours=168)
    assert repeated.data == original_task.data
    result, validation = solve_and_check(repeated, repeated.candidates[3])
    assert result.status == "optimal" and validation.valid
    for field in ("operating_cost_yuan", "emissions_kg", "grid_kwh", "gas_kwh_lhv", "curtailed_pv_kwh"):
        assert getattr(validation.metrics, field) == pytest.approx(getattr(scenarios[3].validation.metrics, field), abs=1e-6)


def test_limit_without_incumbent_is_not_called_infeasible(monkeypatch):
    import energy_agent.optimization as optimization
    task = make_demo_task(hours=2)
    monkeypatch.setattr(optimization, "milp", lambda *args, **kwargs:
                        SimpleNamespace(status=1, x=None, message="Time limit reached"))
    result, validation = solve_and_check(task, task.candidates[0])
    assert result.status == "no_solution_limit"
    assert not validation.valid
    assert result.solve_seconds >= 0


def test_limit_with_incumbent_is_valid_but_not_claimed_optimal(monkeypatch):
    import energy_agent.optimization as optimization
    real_milp = optimization.milp

    def limited(*args, **kwargs):
        result = real_milp(*args, **kwargs)
        result.status = 1
        result.message = "Time limit reached (simulated status using a real incumbent)"
        result.mip_gap = 0.02
        return result

    task = make_demo_task(hours=2)
    monkeypatch.setattr(optimization, "milp", limited)
    result, validation = solve_and_check(task, task.candidates[0])
    assert result.status == "feasible_limit" and validation.valid
    assert result.mip_gap == pytest.approx(0.02)
    assert "未证明最优" in result.message
    scenario = ScenarioResult(candidate=task.candidates[0], investment_yuan=44500,
                              dispatch=result, validation=validation)
    comparison = compare_scenarios(ComparisonRequest(scenarios=[scenario]))
    assert comparison.recommended_id == "A"
    assert "尚未全部证明最优" in comparison.explanation
