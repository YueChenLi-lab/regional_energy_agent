"""Independent arithmetic checks and period-only metrics; no solver matrices."""
import numpy as np

from .planning import investment_yuan
from .schemas import (Comparison, ComparisonRequest, ConstraintCheck, Metrics,
                      SolutionValidation, ValidationRequest)


def validate_solution(request: ValidationRequest) -> SolutionValidation:
    request = ValidationRequest.model_validate(request)
    task, candidate, result = request.task, request.candidate, request.dispatch
    data, devices, limits = task.data, task.devices, task.constraints
    n, dt, tolerance = len(data.timestamps), data.step_hours, 1e-5
    checks = []

    def check(name, violation, detail="", tol=tolerance):
        amount = max(0.0, float(np.max(np.atleast_1d(violation))))
        checks.append(ConstraintCheck(name=name, passed=amount <= tol,
                                      max_violation=amount, tolerance=tol, detail=detail))

    check("solver_has_solution", 0 if result.status in ("optimal", "feasible_limit") else 1,
          f"求解状态：{result.status}", tol=0)
    check("candidate_identity", 0 if result.candidate_id == candidate.candidate_id else 1, tol=0)
    dimensions_ok = len(result.points) == n and len(result.soc_kwh) == n + 1 and len(result.charge_mode) == n
    check("result_dimensions", 0 if dimensions_ok else 1,
          "逐时点=N，SOC=N+1，充放电模式=N", tol=0)
    if not dimensions_ok or result.status not in ("optimal", "feasible_limit"):
        return SolutionValidation(valid=False, checks=checks)
    check("timestamps", 0 if [p.timestamp for p in result.points] == data.timestamps else 1, tol=0)
    check("objective_available", 0 if result.objective_yuan is not None else 1, tol=0)
    points = result.points
    grid = np.array([p.grid_kw for p in points])
    pv = np.array([p.pv_used_kw for p in points])
    curtailment = np.array([p.curtailment_kw for p in points])
    hp = np.array([p.hp_heat_kw_th for p in points])
    hp_electric = np.array([p.hp_electric_kw for p in points])
    boiler = np.array([p.boiler_heat_kw_th for p in points])
    gas = np.array([p.gas_kw_lhv for p in points])
    charge = np.array([p.charge_kw for p in points])
    discharge = np.array([p.discharge_kw for p in points])
    soc, mode = np.array(result.soc_kwh), np.array(result.charge_mode)
    electric, heat = np.array(data.electric_load_kw), np.array(data.heat_load_kw_th)
    available_pv = np.array(data.pv_per_kw) * candidate.pv_kw
    check("electric_balance", np.abs(grid + pv + discharge - electric - hp_electric - charge))
    check("heat_balance", np.abs(hp + boiler - heat))
    check("heat_pump_cop", np.abs(hp - devices.hp_cop * hp_electric))
    check("boiler_efficiency", np.abs(boiler - devices.boiler_efficiency * gas))
    check("pv_allocation", np.abs(pv + curtailment - available_pv))
    check("nonnegative_flows", -np.concatenate([grid, pv, curtailment, hp, hp_electric,
                                               boiler, gas, charge, discharge]))
    check("grid_limit", grid - limits.grid_limit_kw)
    check("pv_availability", pv - available_pv)
    check("heat_pump_capacity", hp - candidate.hp_kw_th)
    check("boiler_capacity", boiler - candidate.boiler_kw_th)
    check("battery_charge_power", charge - candidate.battery_power_kw)
    check("battery_discharge_power", discharge - candidate.battery_power_kw)
    check("soc_lower", candidate.battery_energy_kwh * devices.soc_min_fraction - soc)
    check("soc_upper", soc - candidate.battery_energy_kwh * devices.soc_max_fraction)
    initial = candidate.battery_energy_kwh * devices.soc_initial_fraction
    check("soc_initial", abs(soc[0] - initial))
    check("soc_terminal", abs(soc[-1] - initial), "期末必须恢复初始能量，不允许免费消耗初始储能")
    check("soc_dynamics", np.abs(np.diff(soc) - dt * devices.charge_efficiency * charge
                                + dt / devices.discharge_efficiency * discharge))
    check("binary_charge_mode", np.maximum(np.abs(mode - np.rint(mode)), np.maximum(-mode, mode - 1)))
    check("charge_mode_limit", charge - candidate.battery_power_kw * mode)
    check("discharge_mode_limit", discharge - candidate.battery_power_kw * (1 - mode))
    check("no_simultaneous_charge_discharge", np.minimum(charge, discharge))
    investment = investment_yuan(candidate, devices)
    check("investment_budget", investment - limits.budget_yuan, tol=1e-4)
    check("pv_site_limit", candidate.pv_kw - limits.pv_limit_kw)
    operating_cost = float(dt * np.sum(grid * np.array(data.electricity_price) + gas * np.array(data.gas_price)))
    emissions = float(dt * np.sum(grid * np.array(data.grid_emission_factor) + gas * np.array(data.gas_emission_factor)))
    check("emission_limit", 0 if limits.emission_limit_kg is None else emissions - limits.emission_limit_kg,
          "未设置排放上限" if limits.emission_limit_kg is None else "按评估期统计", tol=1e-4)
    if result.objective_yuan is not None:
        check("objective_recalculation", abs(operating_cost - result.objective_yuan), tol=1e-4)
    supply_ok = all(c.passed for c in checks if c.name in ("electric_balance", "heat_balance"))
    metrics = Metrics(
        investment_yuan=investment, operating_cost_yuan=operating_cost, emissions_kg=emissions,
        grid_kwh=float(dt * grid.sum()), gas_kwh_lhv=float(dt * gas.sum()),
        curtailed_pv_kwh=float(dt * curtailment.sum()), electric_load_kwh=float(dt * electric.sum()),
        heat_load_kwh_th=float(dt * heat.sum()), supply_satisfied=supply_ok, period_hours=n * dt)
    return SolutionValidation(valid=all(c.passed for c in checks), checks=checks, metrics=metrics)


def compare_scenarios(request: ComparisonRequest) -> Comparison:
    request = ComparisonRequest.model_validate(request)
    eligible = [s for s in request.scenarios if s.validation.valid
                and s.validation.metrics is not None and s.validation.metrics.supply_satisfied
                and s.dispatch.status in ("optimal", "feasible_limit")]
    eligible.sort(key=lambda s: (s.validation.metrics.operating_cost_yuan, s.candidate.candidate_id))
    ranked = [s.candidate.candidate_id for s in eligible]
    if not ranked:
        return Comparison(ranked_ids=[], recommended_id=None,
                          explanation="在本次评估的候选方案中，没有通过供能、预算、场地、排放及独立结果校验的可行方案。")
    explanation = (f"在本次评估的候选方案中，{ranked[0]} 通过全部约束校验，按评估期运行费升序排名第一。"
                   "初始投资与评估期排放单独展示；此结果不代表全部可能容量配置的全局最优。")
    if any(s.dispatch.status == "feasible_limit" for s in eligible):
        explanation += " 部分方案为达到求解限制后的可行解，排序基于当前已得运行费，尚未全部证明最优。"
    return Comparison(ranked_ids=ranked, recommended_id=ranked[0], explanation=explanation)
