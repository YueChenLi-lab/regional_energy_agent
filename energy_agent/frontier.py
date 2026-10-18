"""Finite epsilon-constraint scan of solved points; no complete-frontier claim."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import Field

from .agent import EnergyAgent
from .schemas import Model, RunResult, SolverOptions, TaskRequest


class SensitivityRequest(Model):
    task: TaskRequest
    options: SolverOptions = Field(default_factory=SolverOptions)
    scans: int = Field(default=3,ge=0,le=8)
    output_dir: str = "outputs/study"


class StudyResult(Model):
    baseline_run_id: str
    run_ids: list[str]
    points: list[dict]
    nondominated_run_ids: list[str]
    files: dict[str,str]
    note: str = "仅展示已求得且通过独立校验的非支配点；有限排放约束扫描不证明完整全局前沿；超时解不代表已证明最优"


def run_summary(run):
    scenario=next((s for s in run.scenarios if s.validation.valid),None)
    return dict(run_id=run.run_id,version=run.input_version,status=run.scenarios[0].dispatch.status if run.scenarios else run.state.value,
        feasible=scenario is not None,emission_cap_kg=run.task.constraints.emission_limit_kg,
        **({**scenario.candidate.model_dump(exclude={'name','source_id'}),'investment_yuan':scenario.investment_yuan,
            'npv_cost_yuan':scenario.economics.npv_cost_yuan,'annual_emissions_kg':scenario.validation.metrics.emissions_kg,
            'annual_energy_cost_yuan':scenario.validation.metrics.operating_cost_yuan,'solve_seconds':scenario.dispatch.solve_seconds,
            'mip_gap':scenario.dispatch.mip_gap,'model_statistics':scenario.dispatch.model_statistics.model_dump() if scenario.dispatch.model_statistics else None} if scenario else {}))


def sensitivity_analysis(request: SensitivityRequest) -> StudyResult:
    req=SensitivityRequest.model_validate(request)
    if req.task.economics is None or req.task.capacity_bounds is None:
        raise ValueError("成本—排放分析需要全年经济参数和容量边界")
    out=Path(req.output_dir);out.mkdir(parents=True,exist_ok=True)
    agent=EnergyAgent(out/'runs',req.options)
    baseline_task=req.task.model_copy(deep=True)
    baseline_task.planning_mode='candidates';baseline_task.candidates=[baseline_task.candidates[0]]
    baseline_task.constraints.emission_limit_kg=None
    baseline=agent.run(baseline_task)
    runs=[]
    for objective in ('npv','emissions'):
        task=req.task.model_copy(deep=True);task.planning_mode='capacity';task.capacity_objective=objective
        runs.append(agent.run(task))
    ends=[run_summary(r) for r in runs]
    if all(p['feasible'] for p in ends):
        lower,upper=ends[1]['annual_emissions_kg'],ends[0]['annual_emissions_kg']
        for cap in np.linspace(lower,upper,req.scans+2)[1:-1]:
            task=req.task.model_copy(deep=True);task.planning_mode='capacity';task.capacity_objective='npv'
            task.constraints.emission_limit_kg=float(cap)
            runs.append(agent.run(task))
    points=[run_summary(r) for r in runs]
    base=run_summary(baseline)
    for p in points:
        if base['feasible'] and p['feasible']:
            p['delta_initial_investment_yuan']=p['investment_yuan']-base['investment_yuan']
            p['delta_npv_cost_yuan']=p['npv_cost_yuan']-base['npv_cost_yuan']
            p['annual_emission_reduction_kg']=base['annual_emissions_kg']-p['annual_emissions_kg']
    feasible=[p for p in points if p['feasible']]
    non=[]
    for p in feasible:
        dominated=any(q['npv_cost_yuan']<=p['npv_cost_yuan']+1e-4 and q['annual_emissions_kg']<=p['annual_emissions_kg']+1e-4
            and (q['npv_cost_yuan']<p['npv_cost_yuan']-1e-4 or q['annual_emissions_kg']<p['annual_emissions_kg']-1e-4) for q in feasible)
        if not dominated:non.append(p['run_id'])
    for point in points:
        point['nondominated_among_solved']=point['run_id'] in non
    files={key:str(out/name) for key,name in [('json','study.json'),('csv','tradeoffs.csv'),('markdown','study.md')]}
    result=StudyResult(baseline_run_id=baseline.run_id,run_ids=[r.run_id for r in runs],points=points,nondominated_run_ids=non,files=files)
    Path(files['json']).write_text(json.dumps({'baseline':base,**result.model_dump()},ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(points).drop(columns=['model_statistics'],errors='ignore').to_csv(files['csv'],index=False)
    lines=['# 全年成本—运行排放研究',result.note, '基线：'+json.dumps(base,ensure_ascii=False), '初始投资增量与NPV增量=当前减基线；年度减排=基线减当前。']
    lines.extend(json.dumps(p,ensure_ascii=False) for p in points)
    Path(files['markdown']).write_text('\n\n'.join(lines),encoding='utf-8')
    return result
