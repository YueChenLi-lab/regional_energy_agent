"""Joint capacity and chronological dispatch MILP with bounded linear big-M.

No product of an unknown capacity and a binary: charge<=P, charge<=Pmax*z,
discharge<=P, discharge<=Pmax*(1-z). Every hour remains in the model.
"""
from time import perf_counter
from typing import Literal

import numpy as np
from pydantic import Field
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .economics import annuity_factor, capacity_npv_coefficients, unit_investments
from .schemas import (CAPACITY_FIELDS, Candidate, DispatchPoint, DispatchResult, Model,
                      ModelStatistics, ProjectTask, SolverOptions)


class CapacitySolveRequest(Model):
    task: ProjectTask
    options: SolverOptions = Field(default_factory=SolverOptions)
    objective: Literal["npv", "emissions"] = "npv"
    candidate_id: str = "OPT"


class CapacitySolution(Model):
    candidate: Candidate
    dispatch: DispatchResult


def solve_capacity(request: CapacitySolveRequest) -> CapacitySolution:
    request = CapacitySolveRequest.model_validate(request)
    task = request.task
    if not task.capacity_bounds or not task.economics:
        raise ValueError("容量优化需要容量上下限和经济参数")
    data, dev, bounds, ec = task.data, task.devices, task.capacity_bounds, task.economics
    n, dt = len(data.timestamps), data.step_hours
    started = perf_counter()
    names = ("grid", "pv", "hp", "boiler", "charge", "discharge", "soc")
    offsets = {name: i*n for i,name in enumerate(names)}
    offsets["mode"] = 7*n+1
    cap_start = 8*n+1
    size = cap_start+5
    ci = {name: cap_start+i for i,name in enumerate(CAPACITY_FIELDS)}
    lo, hi = np.zeros(size), np.full(size, np.inf)
    integrality = np.zeros(size, dtype=np.int32)
    def block(name, length=n):
        return slice(offsets[name], offsets[name]+length)
    hi[block("grid")] = task.constraints.grid_limit_kw
    for name in CAPACITY_FIELDS:
        lo[ci[name]], hi[ci[name]] = getattr(bounds, name).lower, getattr(bounds,name).upper
    hi[ci["pv_kw"]] = min(hi[ci["pv_kw"]], task.constraints.pv_limit_kw)
    pmax = bounds.battery_power_kw.upper
    hi[block("charge")] = hi[block("discharge")] = pmax
    hi[block("mode")] = int(pmax > 0)
    integrality[block("mode")] = int(pmax > 0)
    cost = np.zeros(size)
    annual = annuity_factor(ec)
    if request.objective == "npv":
        cost[cap_start:] = capacity_npv_coefficients(dev, ec)
        cost[block("grid")] = dt * np.asarray(data.electricity_price) * annual
        cost[block("boiler")] = dt * (np.asarray(data.gas_price)/dev.boiler_efficiency + ec.boiler_variable_om_per_kwh_th) * annual
        cost[block("hp")] = dt * ec.hp_variable_om_per_kwh_th * annual
        cost[block("discharge")] = dt * ec.battery_variable_om_per_kwh * annual
        constant = dev.grid_connection_cost_yuan + annual * ec.additional_fixed_om_yuan_per_year
    else:
        cost[block("grid")] = dt*np.asarray(data.grid_emission_factor)
        cost[block("boiler")] = dt*np.asarray(data.gas_emission_factor)/dev.boiler_efficiency
        constant = 0
    rows, cols, vals, lbs, ubs = [], [], [], [], []
    def constraint(terms, lb=-np.inf, ub=0):
        row = len(lbs)
        for col, val in terms:
            if val:
                rows.append(row); cols.append(col); vals.append(val)
        lbs.append(lb); ubs.append(ub)
    for t in range(n):
        def at(name): return offsets[name]+t
        constraint([(at("grid"),1),(at("pv"),1),(at("discharge"),1),(at("hp"),-1/dev.hp_cop),(at("charge"),-1)], data.electric_load_kw[t],data.electric_load_kw[t])
        constraint([(at("hp"),1),(at("boiler"),1)],data.heat_load_kw_th[t],data.heat_load_kw_th[t])
        constraint([(at("pv"),1),(ci["pv_kw"],-data.pv_per_kw[t])])
        constraint([(at("hp"),1),(ci["hp_kw_th"],-1)])
        constraint([(at("boiler"),1),(ci["boiler_kw_th"],-1)])
        constraint([(at("charge"),1),(ci["battery_power_kw"],-1)])
        constraint([(at("discharge"),1),(ci["battery_power_kw"],-1)])
        constraint([(at("charge"),1),(at("mode"),-pmax)])
        constraint([(at("discharge"),1),(at("mode"),pmax)],ub=pmax)
        constraint([(at("soc")+1,1),(at("soc"),-1),(at("charge"),-dt*dev.charge_efficiency),(at("discharge"),dt/dev.discharge_efficiency)],0,0)
    for t in range(n+1):
        constraint([(offsets["soc"]+t,1),(ci["battery_energy_kwh"],-dev.soc_max_fraction)])
        constraint([(offsets["soc"]+t,-1),(ci["battery_energy_kwh"],dev.soc_min_fraction)])
    for t in (0,n):
        constraint([(offsets["soc"]+t,1),(ci["battery_energy_kwh"],-dev.soc_initial_fraction)],0,0)
    constraint([(ci["battery_power_kw"],bounds.battery_min_duration_hours),(ci["battery_energy_kwh"],-1)])
    constraint([(ci["battery_energy_kwh"],1),(ci["battery_power_kw"],-bounds.battery_max_duration_hours)])
    constraint([(cap_start+i,v) for i,v in enumerate(unit_investments(dev))], ub=task.constraints.budget_yuan-dev.grid_connection_cost_yuan)
    if task.constraints.emission_limit_kg is not None:
        constraint([(offsets['grid']+t,dt*data.grid_emission_factor[t]) for t in range(n)]+
                   [(offsets['boiler']+t,dt*data.gas_emission_factor[t]/dev.boiler_efficiency) for t in range(n)],ub=task.constraints.emission_limit_kg)
    matrix = coo_matrix((vals,(rows,cols)),shape=(len(lbs),size)).tocsc()
    stats = ModelStatistics(intervals=n,variables=size,binaries=int(np.sum(integrality)),constraints=len(lbs),nonzeros=matrix.nnz,objective_kind=request.objective)
    candidate = Candidate(candidate_id=request.candidate_id,name="连续容量联合规划",source_id=bounds.source_id,**dict.fromkeys(CAPACITY_FIELDS,0))
    def failure(status, message):
        return CapacitySolution(candidate=candidate,dispatch=DispatchResult(candidate_id=candidate.candidate_id,status=status,message=message,
            reasons=[message],solve_seconds=perf_counter()-started,model_statistics=stats))
    if np.any(lo>hi): return failure("rejected","容量上下限与场地上限矛盾")
    try:
        # A feasible integer point at the LP relaxation optimum certifies the
        # original MILP optimum. Only use it after all original rows are checked;
        # otherwise solve the unmodified MILP with the remaining time budget.
        result = milp(cost,integrality=np.zeros(size,dtype=np.int32),bounds=Bounds(lo,hi),constraints=LinearConstraint(matrix,lbs,ubs),
            options={"time_limit":max(0.001,request.options.time_limit_seconds*0.9-(perf_counter()-started)),"presolve":True})
        certified = False
        relaxed_incumbent = None
        if result.status in (0,1) and result.x is not None:
            trial=result.x.copy()
            trial[block("mode")]=(trial[block("charge")]>1e-7).astype(float)
            activity=matrix@trial
            integer_feasible=bool(np.all(activity>=np.asarray(lbs)-1e-6) and np.all(activity<=np.asarray(ubs)+1e-6)
                and np.all(trial>=lo-1e-6) and np.all(trial<=hi+1e-6))
            certified=integer_feasible and result.status==0
            if integer_feasible:
                relaxed_incumbent=trial
            if certified:
                result.x=trial
                result.mip_gap=0.0
                result.mip_dual_bound=float(cost@trial)
        if not certified:
            remaining=max(0.001,request.options.time_limit_seconds-(perf_counter()-started))
            result = milp(cost,integrality=integrality,bounds=Bounds(lo,hi),constraints=LinearConstraint(matrix,lbs,ubs),
                options={"time_limit":remaining,"mip_rel_gap":request.options.mip_rel_gap,"presolve":True})
            if result.status == 1 and result.x is None and relaxed_incumbent is not None:
                result.x=relaxed_incumbent
                result.mip_gap=None
                result.mip_dual_bound=None
    except (ValueError,RuntimeError):
        return failure("error","HiGHS未完成容量优化；未生成可用解")
    if result.status == 2:
        return failure("infeasible","HiGHS判定容量边界、预算、逐时供能与排放等联合约束不可行；未计算最小冲突集，不能指定唯一原因")
    has = result.x is not None and np.isfinite(result.x).all()
    if result.status == 1 and not has: return failure("no_solution_limit","达到求解限制，尚未找到可行容量与运行解")
    if result.status not in (0,1) or not has: return failure("error","求解器未返回可用容量与运行解")
    x=result.x
    capacities={name:max(0.0,float(x[ci[name]])) for name in CAPACITY_FIELDS}
    candidate=Candidate(candidate_id=request.candidate_id,name="连续容量联合规划",source_id=bounds.source_id,**capacities)
    points=[]
    for t in range(n):
        def v(name): return float(x[offsets[name]+t])
        points.append(DispatchPoint(timestamp=data.timestamps[t],grid_kw=v('grid'),pv_used_kw=v('pv'),curtailment_kw=data.pv_per_kw[t]*candidate.pv_kw-v('pv'),
            hp_heat_kw_th=v('hp'),hp_electric_kw=v('hp')/dev.hp_cop,boiler_heat_kw_th=v('boiler'),gas_kw_lhv=v('boiler')/dev.boiler_efficiency,charge_kw=v('charge'),discharge_kw=v('discharge')))
    energy_cost=dt*sum(p.grid_kw*data.electricity_price[t]+p.gas_kw_lhv*data.gas_price[t] for t,p in enumerate(points))
    stats.objective_value=float(cost@x+constant)
    bound=getattr(result,'mip_dual_bound',None)
    stats.dual_bound=float(bound+constant) if bound is not None and np.isfinite(bound) else None
    gap=getattr(result,'mip_gap',None)
    return CapacitySolution(candidate=candidate,dispatch=DispatchResult(candidate_id=candidate.candidate_id,
        status="optimal" if result.status==0 else "feasible_limit",message=("LP下界与满足全部原MILP约束的整数解一致，已证明最优；" if certified else "")+"HiGHS容量与逐时运行联合解；最优性仅适用于声明的线性设备模型与输入边界" if result.status==0 else "达到时限，已有解但未证明最优；需要独立校验",
        solve_seconds=perf_counter()-started,mip_gap=float(gap) if gap is not None and np.isfinite(gap) else None,
        objective_yuan=energy_cost,points=points,soc_kwh=x[block('soc',n+1)].tolist(),charge_mode=x[block('mode')].tolist(),model_statistics=stats))
