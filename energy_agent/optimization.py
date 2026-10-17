"""Finite-capacity dispatch MILP; no hidden load shedding or export.

Each power is an interval average. ``soc[t]`` is the energy immediately
before interval t, so an N-interval problem has N+1 boundary states.
"""
from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .planning import investment_yuan
from .schemas import DispatchPoint, DispatchResult, SolveRequest


def solve_dispatch(request: SolveRequest) -> DispatchResult:
    """Minimize period energy purchase cost for one fixed candidate."""
    request = SolveRequest.model_validate(request)
    task, candidate = request.task, request.candidate
    data, devices, limits = task.data, task.devices, task.constraints
    n, dt = len(data.timestamps), data.step_hours
    started = perf_counter()

    def failure(status: str, message: str, reasons: list[str]) -> DispatchResult:
        return DispatchResult(candidate_id=candidate.candidate_id, status=status,
                              message=message, reasons=reasons,
                              solve_seconds=perf_counter() - started)

    # These failures have concrete, independently explainable necessary conditions.
    rejection = []
    investment = investment_yuan(candidate, devices)
    if investment > limits.budget_yuan + 1e-7:
        rejection.append(f"初始投资 {investment:.2f} 元超过预算 {limits.budget_yuan:.2f} 元")
    if candidate.pv_kw > limits.pv_limit_kw + 1e-7:
        rejection.append(f"光伏装机 {candidate.pv_kw:g} kW 超过场地上限 {limits.pv_limit_kw:g} kW")
    if rejection:
        return failure("rejected", "候选未通过规划约束预检查", rejection)
    arrays = [data.electric_load_kw, data.heat_load_kw_th, data.pv_per_kw,
              data.electricity_price, data.gas_price, data.grid_emission_factor,
              data.gas_emission_factor]
    if any(len(values) != n for values in arrays):
        return failure("error", "时序长度不一致；必须先通过输入质量检查", ["时序长度不一致"])
    electric, heat, pv_unit, eprice, gprice, gef, gaf = map(np.asarray, arrays)
    available_pv = pv_unit * candidate.pv_kw
    if np.max(heat) > candidate.hp_kw_th + candidate.boiler_kw_th + 1e-7:
        return failure("infeasible", "供热能力预检查失败", [
            f"最大热负荷 {np.max(heat):.3f} kW_th 超过热泵与锅炉总容量 "
            f"{candidate.hp_kw_th + candidate.boiler_kw_th:.3f} kW_th"])
    minimum_hp_electric = np.maximum(heat - candidate.boiler_kw_th, 0) / devices.hp_cop
    instantaneous_supply = limits.grid_limit_kw + available_pv + candidate.battery_power_kw
    shortage = electric + minimum_hp_electric - instantaneous_supply
    if np.max(shortage) > 1e-7:
        t = int(np.argmax(shortage))
        return failure("infeasible", "供电能力必要条件预检查失败", [
            f"{data.timestamps[t].isoformat()} 常规负荷与最低热泵耗电之和超过电网、可用光伏和"
            f"最大放电功率之和 {shortage[t]:.3f} kW；此上界尚未考虑电池能量限制"])

    # Variable blocks: grid, pv_used, hp_heat, boiler_heat, charge, discharge,
    # soc (N+1), charge_mode (N). Only charge_mode is integer.
    offsets = {name: i * n for i, name in enumerate(
        ("grid", "pv", "hp", "boiler", "charge", "discharge", "soc"))}
    offsets["mode"] = 7 * n + 1
    size = 8 * n + 1
    lower, upper, cost = np.zeros(size), np.full(size, np.inf), np.zeros(size)
    integrality = np.zeros(size, dtype=np.int32)

    def block(name: str, length: int = n) -> slice:
        return slice(offsets[name], offsets[name] + length)

    upper[block("grid")] = limits.grid_limit_kw
    upper[block("pv")] = available_pv
    upper[block("hp")] = candidate.hp_kw_th
    upper[block("boiler")] = candidate.boiler_kw_th
    upper[block("charge")] = upper[block("discharge")] = candidate.battery_power_kw
    lower[block("soc", n + 1)] = candidate.battery_energy_kwh * devices.soc_min_fraction
    upper[block("soc", n + 1)] = candidate.battery_energy_kwh * devices.soc_max_fraction
    initial = candidate.battery_energy_kwh * devices.soc_initial_fraction
    lower[offsets["soc"]] = upper[offsets["soc"]] = initial
    lower[offsets["soc"] + n] = upper[offsets["soc"] + n] = initial
    upper[block("mode")] = 1 if candidate.battery_power_kw else 0
    integrality[block("mode")] = 1
    cost[block("grid")] = dt * eprice
    cost[block("boiler")] = dt * gprice / devices.boiler_efficiency

    rows, cols, values, row_lower, row_upper = [], [], [], [], []

    def constraint(terms, lb, ub):
        row = len(row_lower)
        for column, value in terms:
            if value:
                rows.append(row)
                cols.append(column)
                values.append(value)
        row_lower.append(lb)
        row_upper.append(ub)

    for t in range(n):
        def at(name):
            return offsets[name] + t

        constraint([(at("grid"), 1), (at("pv"), 1), (at("discharge"), 1),
                    (at("hp"), -1 / devices.hp_cop), (at("charge"), -1)], electric[t], electric[t])
        constraint([(at("hp"), 1), (at("boiler"), 1)], heat[t], heat[t])
        constraint([(at("soc") + 1, 1), (at("soc"), -1),
                    (at("charge"), -dt * devices.charge_efficiency),
                    (at("discharge"), dt / devices.discharge_efficiency)], 0, 0)
        constraint([(at("charge"), 1), (at("mode"), -candidate.battery_power_kw)], -np.inf, 0)
        constraint([(at("discharge"), 1), (at("mode"), candidate.battery_power_kw)],
                   -np.inf, candidate.battery_power_kw)
    if limits.emission_limit_kg is not None:
        terms = [(offsets["grid"] + t, dt * gef[t]) for t in range(n)]
        terms += [(offsets["boiler"] + t, dt * gaf[t] / devices.boiler_efficiency) for t in range(n)]
        constraint(terms, -np.inf, limits.emission_limit_kg)

    matrix = coo_matrix((values, (rows, cols)), shape=(len(row_lower), size)).tocsc()
    try:
        result = milp(cost, integrality=integrality, bounds=Bounds(lower, upper),
                      constraints=LinearConstraint(matrix, row_lower, row_upper),
                      options={"time_limit": request.options.time_limit_seconds,
                               "mip_rel_gap": request.options.mip_rel_gap, "presolve": True})
    except (ValueError, RuntimeError) as exc:
        return failure("error", f"HiGHS 求解失败：{exc}", ["求解器错误；未生成可用运行解"])
    elapsed = perf_counter() - started
    if result.status == 2:
        reasons = ["HiGHS 判定当前容量、逐时供能、电池初末状态和运行约束的联合模型不可行；"
                   "未进行最小冲突集诊断，不能归因于单一约束"]
        if limits.emission_limit_kg is not None:
            reasons.append(f"模型已包含评估期排放上限 {limits.emission_limit_kg:g} kg{task.emission_species}")
        return failure("infeasible", "运行模型不可行", reasons)
    has_solution = result.x is not None and np.all(np.isfinite(result.x))
    if result.status == 1 and not has_solution:
        return failure("no_solution_limit", "达到求解限制，尚未找到可行解", [str(result.message)])
    if result.status not in (0, 1) or not has_solution:
        return failure("error", "求解器未返回可用解", [str(result.message)])
    x = result.x
    points = []
    for t in range(n):
        def value(name):
            return float(x[offsets[name] + t])

        points.append(DispatchPoint(
            timestamp=data.timestamps[t], grid_kw=value("grid"), pv_used_kw=value("pv"),
            curtailment_kw=float(available_pv[t] - value("pv")),
            hp_heat_kw_th=value("hp"), hp_electric_kw=value("hp") / devices.hp_cop,
            boiler_heat_kw_th=value("boiler"), gas_kw_lhv=value("boiler") / devices.boiler_efficiency,
            charge_kw=value("charge"), discharge_kw=value("discharge")))
    raw_gap = getattr(result, "mip_gap", None)
    gap = float(raw_gap) if raw_gap is not None and np.isfinite(raw_gap) else None
    return DispatchResult(
        candidate_id=candidate.candidate_id,
        status="optimal" if result.status == 0 else "feasible_limit",
        message=("HiGHS 在所设容差内求得最优运行解" if result.status == 0 else
                 "达到求解限制，已有解但未证明最优；须通过独立约束校验"),
        solve_seconds=elapsed, mip_gap=gap, objective_yuan=float(cost @ x), points=points,
        soc_kwh=x[block("soc", n + 1)].tolist(), charge_mode=x[block("mode")].tolist())
