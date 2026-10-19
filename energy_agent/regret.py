"""Scenario recourse for fixed investments, using only existing solver tools."""
import csv
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Literal

from pydantic import Field, model_validator

from .comparability import compare_basis
from .counterfactual import _Budget, _atomic_json, data_fingerprint, digest
from .data import case_label, validate_inputs
from .economics import evaluate_economics
from .evaluation import validate_solution
from .regret_math import CostObservation, RegretAnalysis, analyze_regret
from .schemas import (CAPACITY_FIELDS, Candidate, CapacityBounds, CapacityRange, ConstraintCheck,
    Model, RunResult, SolutionValidation, SolverOptions, Source, ToolCall, ValidationRequest)
from .storage import file_lock

ScenarioField = Literal['electricity_price_multiplier','gas_price_multiplier','pv_multiplier','electric_load_multiplier']
FIELDS = {'electricity_price_multiplier':'electricity_price','gas_price_multiplier':'gas_price',
          'pv_multiplier':'pv_per_kw','electric_load_multiplier':'electric_load_kw'}


def regret_enabled():
    return os.getenv('ENERGY_AGENT_ENABLE_REGRET','1').lower() not in ('0','false','off')


def capacity_fingerprint(candidate):
    return digest({k:getattr(candidate,k) for k in CAPACITY_FIELDS})


class RegretScenario(Model):
    scenario_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,40}$')
    name: str
    is_baseline: bool = False
    electricity_price_multiplier: float = Field(default=1,ge=0,le=10)
    gas_price_multiplier: float = Field(default=1,ge=0,le=10)
    pv_multiplier: float = Field(default=1,ge=0,le=10)
    electric_load_multiplier: float = Field(default=1,ge=0,le=10)
    multiplier_unit: Literal['1'] = '1'
    assumption: str = '人为研究假设，不是价格、资源或负荷预测'

    @model_validator(mode='after')
    def baseline_unchanged(self):
        if self.is_baseline and any(getattr(self,k)!=1 for k in FIELDS):
            raise ValueError('基准情景必须保持全部倍数为1')
        return self


def default_scenarios():
    return [RegretScenario(scenario_id='base',name='基准',is_baseline=True),
        RegretScenario(scenario_id='electric_up',name='购电价格上涨20%',electricity_price_multiplier=1.2),
        RegretScenario(scenario_id='gas_up',name='燃气价格上涨20%',gas_price_multiplier=1.2),
        RegretScenario(scenario_id='pv_down',name='光伏出力下降20%',pv_multiplier=.8)]


class RegretCandidate(Model):
    candidate: Candidate
    capacity_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    origin: Literal['task','solved_run']
    source_run_id: str


def available_candidates(run):
    result=[]
    for c in run.task.candidates or []:
        result.append(RegretCandidate(candidate=c,capacity_sha256=capacity_fingerprint(c),origin='task',source_run_id=run.run_id))
    for s in run.scenarios:
        if s.validation.valid and not any(c.candidate.candidate_id==s.candidate.candidate_id for c in result):
            result.append(RegretCandidate(candidate=s.candidate,capacity_sha256=capacity_fingerprint(s.candidate),origin='solved_run',source_run_id=run.run_id))
    return result


def check_original_bounds(task, candidate):
    if task.capacity_bounds is None:
        return True
    b=task.capacity_bounds
    if any(not getattr(b,k).lower-1e-7<=getattr(candidate,k)<=getattr(b,k).upper+1e-7 for k in CAPACITY_FIELDS):
        return False
    return (candidate.battery_power_kw*b.battery_min_duration_hours<=candidate.battery_energy_kwh+1e-7
        and candidate.battery_energy_kwh<=candidate.battery_power_kw*b.battery_max_duration_hours+1e-7)


class RegretRequest(Model):
    request_id: str = Field(min_length=1,max_length=128)
    parent_request_id: str | None = None
    baseline: RunResult
    base_run_id: str
    input_version: int = Field(ge=1)
    input_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    candidates: list[RegretCandidate] = Field(min_length=1,max_length=4)
    scenarios: list[RegretScenario] = Field(min_length=1,max_length=5)
    allowed_changes: list[ScenarioField] = Field(default_factory=lambda:list(FIELDS)[:3])
    allow_electric_load_change: bool = False
    cost_basis: Literal['npv','period_energy']
    single_solve_seconds: float = Field(default=5,gt=0,le=300)
    max_solver_calls: int = Field(default=20,ge=1,le=20)
    total_seconds: float = Field(default=60,gt=0,le=1800)
    mip_rel_gap: float = Field(default=1e-6,ge=0,le=.1)
    cost_tolerance_yuan: float = Field(default=1e-4,gt=0,le=.01)
    confirm_large_annual: bool = False
    output_dir: str = 'outputs/regret'

    @model_validator(mode='after')
    def bound_request(self):
        task=self.baseline.task
        if (self.base_run_id!=self.baseline.run_id or self.input_version!=task.version
                or self.input_version!=self.baseline.input_version or self.input_sha256!=digest(task)):
            raise ValueError('基准run_id、版本或完整输入指纹不一致')
        checked=validate_inputs(task)
        if not checked.ready:
            raise ValueError('原任务信息不完整；先完成输入校验与确认评估')
        if not any(s.validation.valid and validate_solution(ValidationRequest(task=checked.task,candidate=s.candidate,dispatch=s.dispatch)).valid for s in self.baseline.scenarios):
            raise ValueError('原任务没有经复核的可行见证；不可行时请先使用反事实约束修复，未知时先完成评估')
        if self.cost_basis!=('npv' if task.economics else 'period_energy'):
            raise ValueError('完整年度经济任务必须使用NPV；无经济参数时仅使用评估期购能费')
        if task.economics and not self.confirm_large_annual:
            raise ValueError('全年矩阵须显式确认资源预算')
        if len(set(self.allowed_changes))!=len(self.allowed_changes):
            raise ValueError('情景权限字段不能重复')
        ids=[c.candidate.candidate_id for c in self.candidates]
        if len(set(ids))!=len(ids):
            raise ValueError('候选配置ID必须唯一')
        for c in self.candidates:
            original=next((x for x in available_candidates(self.baseline) if x.origin==c.origin and x.candidate==c.candidate),None)
            if original is None or c.source_run_id!=self.base_run_id or c.capacity_sha256!=capacity_fingerprint(c.candidate):
                raise ValueError('候选必须是同一确认任务中的已有候选或已求得配置，容量指纹与来源必须一致')
            if not check_original_bounds(task,c.candidate):
                raise ValueError('候选违反原始容量/储能时长边界，不能用固定容量绑定绕过用户边界')
        if len({s.scenario_id for s in self.scenarios})!=len(self.scenarios) or sum(s.is_baseline for s in self.scenarios)!=1:
            raise ValueError('情景ID必须唯一，且必须恰有一个基准情景')
        for s in self.scenarios:
            for field,column in FIELDS.items():
                multiplier=getattr(s,field)
                if multiplier!=1 and (field not in self.allowed_changes or field=='electric_load_multiplier' and not self.allow_electric_load_change):
                    raise ValueError('情景包含未授权修改；电负荷变化须额外明确启用')
                if column=='pv_per_kw' and any(v*multiplier>1 for v in task.data.pv_per_kw):
                    raise ValueError('光伏倍数使归一化出力超过1，拒绝而不静默裁剪')
        return self


class RegretCell(CostObservation):
    run_id: str | None = None
    input_version: int | None = None
    capacity_sha256: str
    scenario_sha256: str
    cache_key: str
    task_sha256: str | None = None
    data_sha256: str | None = None
    investment_yuan: float
    emissions_kg: float | None = None
    operating_cost_yuan: float | None = None
    npv_cost_yuan: float | None = None
    mip_gap: float | None = None
    solve_seconds: float | None = None
    effective_solve_limits_seconds: list[float] = Field(default_factory=list)
    validation: SolutionValidation | None = None
    capacities_fixed: bool | None = None
    returned_capacities: dict | None = None
    result_file: str | None = None
    result_sha256: str | None = None
    reasons: list[str] = Field(default_factory=list)


class RegretResult(Model):
    request_id: str
    parent_request_id: str | None
    request_sha256: str
    base_run_id: str
    input_version: int
    input_sha256: str
    cost_basis: Literal['npv','period_energy']
    cost_unit: str = '元'
    case_label: str
    candidates: list[RegretCandidate]
    scenarios: list[RegretScenario]
    scenario_inputs: dict[str,dict]
    original_capacity_bounds: dict | None
    cells: list[RegretCell]
    analysis: RegretAnalysis
    solver_calls: int
    elapsed_seconds: float
    limits: dict
    sources: list[dict]
    files: dict[str,str]
    tool_call: ToolCall
    explanation: str


def derive_scenario(task, scenario, base_run_id):
    """Always derive from the original task; never compound prior scenarios."""
    result=task.model_copy(deep=True)
    result.version=task.version+1;result.parent_run_id=base_run_id
    sid='regret-scenario-'+digest(scenario)[:16]
    if any(s.source_id==sid for s in task.sources):
        raise ValueError('情景来源ID与原来源冲突，拒绝覆盖')
    steps=[];units={};parents=[]
    for field,column in FIELDS.items():
        factor=getattr(scenario,field)
        if factor!=1:
            values=[v*factor for v in getattr(task.data,column)]
            setattr(result.data,column,values)
            result.data.source_ids[column]=sid
            units[column]=task.data.units[column]
            parents.append(task.data.source_ids[column])
            steps.append(f'{column}:原值乘{factor:g}；原数组SHA={digest(getattr(task.data,column))}；新数组SHA={digest(values)}')
    result.sources.append(Source(source_id=sid,name='研究假设情景：'+scenario.name,category='assumption',
        region=task.sources[0].region if task.sources else '未知',time_range=task.sources[0].time_range if task.sources else '未知',
        units=units,processing=[f'独立派生自run_id={base_run_id}，v{task.version}，原输入SHA={digest(task)}',*steps],
        parent_source_ids=sorted(set(parents)),conditions=scenario.assumption+'；不修改原始文件，不改变热负荷、供能要求、时间轴、约束、设备及经济参数'))
    if task.case_context:
        result.case_context.pending.append('当前为明确倍数的研究情景；改变的实测字段不再作为原值实测，原文件保留。')
    return result


def bind_candidate(scenario_task, candidate, cache_key, cost_basis):
    """Bind capacities for recourse; retain user bounds in provenance separately."""
    task=scenario_task.model_copy(deep=True)
    task.candidates=[candidate.model_copy(deep=True)]
    task.planning_mode='candidates';task.capacity_objective='npv'
    if cost_basis=='npv':
        binding='regret-binding-'+cache_key[:16]
        old=scenario_task.capacity_bounds
        duration=candidate.battery_energy_kwh/candidate.battery_power_kw if candidate.battery_power_kw else 1
        task.capacity_bounds=CapacityBounds(source_id=binding,
            **{k:CapacityRange(lower=getattr(candidate,k),upper=getattr(candidate,k)) for k in CAPACITY_FIELDS},
            battery_min_duration_hours=old.battery_min_duration_hours if old else min(.5,duration),
            battery_max_duration_hours=old.battery_max_duration_hours if old else max(8,duration))
        task.planning_mode='capacity'
        task.sources.append(Source(source_id=binding,name='算法固定容量绑定（不是修改用户原边界）',category='user',
            units={k:'kWh' if k=='battery_energy_kwh' else 'kW_th' if k in ('hp_kw_th','boiler_kw_th') else 'kW' for k in CAPACITY_FIELDS},
            processing=[f'用户已选配置{candidate.candidate_id}；容量SHA={capacity_fingerprint(candidate)}',
                '原用户边界='+json.dumps(old.model_dump(mode='json') if old else None,ensure_ascii=False)],
            conditions='上下界都固定为已选投资容量；仅逐时运行适应情景，固定投资不重选'))
    return task


def evaluate_minimax_regret(request: RegretRequest) -> RegretResult:
    if not regret_enabled():
        raise ValueError('多情景最小后悔功能已关闭')
    req=RegretRequest.model_validate(request)
    signature=digest(req.model_dump(mode='json',exclude={'output_dir'}))
    out=Path(req.output_dir)/hashlib.sha256(req.request_id.encode()).hexdigest()
    out.mkdir(parents=True,exist_ok=True)
    with file_lock(out/'request.lock'):
        manifest=out/'request.json';saved=out/'regret.json'
        if manifest.exists():
            if json.loads(manifest.read_text(encoding='utf-8'))['request_sha256']!=signature:
                raise ValueError('同一request_id已绑定其他候选、情景、基准或预算，拒绝修改')
            if not saved.exists():
                raise ValueError('旧请求中断且没有完整回执；不自动重复计算，请使用新ID显式授权')
            result=RegretResult.model_validate_json(saved.read_bytes())
            if result.request_sha256!=signature:
                raise ValueError('结果与请求回执不一致')
            return result
        _atomic_json(manifest,{'request_sha256':signature,'request':req.model_dump(mode='json')})
        return _evaluate(req,signature,out)


def _evaluate(req,signature,out):
    from .agent import EnergyAgent,Tool
    from .planning import investment_yuan
    budget=_Budget(req)  # Same bounded adapter-call pattern as constraint repair.
    base=req.baseline.task
    cells=[];scenario_inputs={}
    for scenario in req.scenarios:
        scenario_task=derive_scenario(base,scenario,req.base_run_id)
        checked=validate_inputs(scenario_task)
        if not checked.ready:
            raise ValueError('情景派生不合法：'+'；'.join(i.message for i in checked.issues))
        scenario_inputs[scenario.scenario_id]={'scenario_sha256':digest(scenario),'task_sha256':digest(scenario_task),
            'data_sha256':data_fingerprint(scenario_task),'comparison_basis':compare_basis(base,scenario_task).model_dump(mode='json'),
            'sources':[s.model_dump(mode='json') for s in scenario_task.sources[len(base.sources):]]}
        for selection in req.candidates:
            candidate=selection.candidate
            key=digest({'input':req.input_sha256,'selection':selection.model_dump(mode='json'),'scenario':scenario.model_dump(mode='json'),
                'economics':base.economics.model_dump(mode='json') if base.economics else None,'objective':req.cost_basis,'options':[req.single_solve_seconds,req.mip_rel_gap]})
            cell=RegretCell(candidate_id=candidate.candidate_id,scenario_id=scenario.scenario_id,feasibility='not_run',
                capacity_sha256=selection.capacity_sha256,scenario_sha256=digest(scenario),cache_key=key,
                investment_yuan=investment_yuan(candidate,base.devices))
            cells.append(cell)
            if budget.calls>=req.max_solver_calls or perf_counter()-budget.started>=req.total_seconds:
                cell.reasons=['共享调用/时间预算耗尽，单元未执行；不是不可行']
                continue
            task=bind_candidate(scenario_task,candidate,key,req.cost_basis)
            agent=EnergyAgent(out/'runs',SolverOptions(time_limit_seconds=req.single_solve_seconds,mip_rel_gap=req.mip_rel_gap))
            name='solve_capacity' if req.cost_basis=='npv' else 'solve_dispatch'
            tool=agent.registry._tools[name]
            raw_capacities={}
            if req.cost_basis=='npv':
                def fixed_solver(payload):
                    solved=tool.function(payload.model_copy(update={'candidate_id':candidate.candidate_id}))
                    raw_capacities.update({k:getattr(solved.candidate,k) for k in CAPACITY_FIELDS})
                    if solved.dispatch.status in ('optimal','feasible_limit'):
                        if any(abs(raw_capacities[k]-getattr(candidate,k))>1e-6 for k in CAPACITY_FIELDS):
                            raise ValueError('固定容量求解返回了不同投资配置，拒绝作为同一方案')
                        solved.candidate=candidate.model_copy(update={'source_id':task.capacity_bounds.source_id})
                    return solved
                function=fixed_solver
            else:
                function=tool.function
            agent.registry._tools[name]=Tool(tool.input_schema,tool.output_schema,budget.wrap(function))
            before=budget.calls
            run=agent.run(task)
            cell.effective_solve_limits_seconds=budget.call_limits[before:]
            cell.run_id=run.run_id;cell.input_version=run.input_version
            cell.task_sha256=digest(run.task);cell.data_sha256=data_fingerprint(run.task)
            path=Path(run.files['json']);cell.result_file=str(path);cell.result_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            cell.reasons=[i.message for i in run.issues]
            if not run.scenarios:
                cell.feasibility='uncertain' if budget.exhausted else 'error'
                continue
            outcome=run.scenarios[0];dispatch=outcome.dispatch
            cell.solver_status=dispatch.status;cell.solve_seconds=dispatch.solve_seconds;cell.mip_gap=dispatch.mip_gap
            cell.reasons+=dispatch.reasons
            cell.returned_capacities=raw_capacities or {k:getattr(outcome.candidate,k) for k in CAPACITY_FIELDS}
            cell.capacities_fixed=all(abs(getattr(outcome.candidate,k)-getattr(candidate,k))<=1e-7 for k in CAPACITY_FIELDS) if dispatch.status in ('optimal','feasible_limit') else None
            cell.validation=validate_solution(ValidationRequest(task=validate_inputs(run.task).task,candidate=outcome.candidate,dispatch=dispatch))
            cell.validation.checks.append(ConstraintCheck(name='first_stage_fixed',passed=cell.capacities_fixed is not False,max_violation=1 if cell.capacities_fixed is False else 0))
            cell.validation.checks.append(ConstraintCheck(name='original_agent_validation',passed=outcome.validation.valid,max_violation=0 if outcome.validation.valid else 1))
            unchanged=digest(run.task)==digest(task)
            cell.validation.checks.append(ConstraintCheck(name='scenario_input_fixed',passed=unchanged,max_violation=0 if unchanged else 1))
            cell.validation.valid=all(c.passed for c in cell.validation.checks)
            if dispatch.status in ('optimal','feasible_limit') and outcome.validation.valid and cell.validation.valid and cell.capacities_fixed:
                economic=evaluate_economics(run.task,outcome.candidate,dispatch,cell.validation.metrics)
                cost=economic.npv_cost_yuan if economic else cell.validation.metrics.operating_cost_yuan
                expected=dispatch.model_statistics.objective_value if economic and dispatch.model_statistics else dispatch.objective_yuan
                violation=abs(cost-expected) if expected is not None else 1
                cell.validation.checks.append(ConstraintCheck(name='regret_cost_objective',passed=violation<=req.cost_tolerance_yuan,max_violation=violation,tolerance=req.cost_tolerance_yuan))
                cell.validation.valid=all(c.passed for c in cell.validation.checks)
                if cell.validation.valid:
                    cells[-1]=RegretCell.model_validate({**cell.model_dump(), 'feasibility':'feasible','cost_yuan':cost,
                        'cost_is_optimal':dispatch.status=='optimal' and dispatch.mip_gap==0,'operating_cost_yuan':cell.validation.metrics.operating_cost_yuan,
                        'emissions_kg':cell.validation.metrics.emissions_kg,'npv_cost_yuan':economic.npv_cost_yuan if economic else None})
                    continue
            cell.feasibility={'infeasible':'infeasible','no_solution_limit':'uncertain','rejected':'rejected'}.get(dispatch.status,'error')
    analysis=analyze_regret(cells,[c.candidate.candidate_id for c in req.candidates],[s.scenario_id for s in req.scenarios],
        next(s.scenario_id for s in req.scenarios if s.is_baseline),req.cost_tolerance_yuan)
    files={k:str(out/n) for k,n in [('json','regret.json'),('csv','matrix.csv'),('markdown','regret.md'),('request','request.json')]}
    elapsed=perf_counter()-budget.started
    result=RegretResult(request_id=req.request_id,parent_request_id=req.parent_request_id,request_sha256=signature,
        base_run_id=req.base_run_id,input_version=req.input_version,input_sha256=req.input_sha256,cost_basis=req.cost_basis,
        case_label=case_label(base),candidates=req.candidates,scenarios=req.scenarios,scenario_inputs=scenario_inputs,
        original_capacity_bounds=base.capacity_bounds.model_dump(mode='json') if base.capacity_bounds else None,
        cells=cells,analysis=analysis,solver_calls=budget.calls,elapsed_seconds=elapsed,
        limits={'single_solve_seconds':req.single_solve_seconds,'max_solver_calls':req.max_solver_calls,'total_seconds':req.total_seconds},
        sources=[s.model_dump(mode='json') for s in base.sources],files=files,
        tool_call=ToolCall(run_id=req.request_id,input_version=req.input_version,tool_name='evaluate_minimax_regret',status='success',seconds=elapsed,
            summary=f'{analysis.status}；{budget.calls}次求解适配器调用；不自动采用',source_ids=[s.source_id for s in base.sources],result_file=files['json']),explanation='')
    result.explanation=explain_regret(result)
    _export(result)
    return result


def explain_regret(result):
    a=result.analysis
    def ids(values):return '、'.join(values) or '无可用结果'
    label='规划期NPV成本' if result.cost_basis=='npv' else '评估期购能费（初始投资另列，不是生命周期投资最优）'
    lines=[f'当前基准run_id：{result.base_run_id}；研究成本口径：{label}，单位元。',result.case_label,
        '基准情景最便宜：'+ids(a.baseline_cheapest_ids)+'；最小最大后悔候选：'+ids(a.recommended_ids)+'。',a.note]
    if a.provisional_ids:lines.append('仅已完成范围的暂定项：'+ids(a.provisional_ids)+'；不作为原全部候选的完整推荐。')
    for k in a.recommended_ids+a.provisional_ids:
        lines.append(f'{k}：全部指定情景均有经独立校验的可行运行；最坏情景{ids(a.worst_scenario_ids[k])}，比该情景当前候选集内最佳已得成本多付{a.worst_regret_yuan[k]:,.4f}元。')
    lines.append('最小最大成本项（不同准则）：'+ids(a.minimax_cost_ids)+'；未给情景分配概率，不把平均值称为期望。')
    lines.append('投资容量固定、逐时运行可适应；有限候选和有限研究假设不覆盖全部未来，不构成连续容量空间全局稳健最优。探索未改写或采用确认任务。')
    return '\n\n'.join(lines)


def _export(result):
    a=result.analysis
    rows=[]
    for c in result.cells:
        rows.append({**c.model_dump(exclude={'validation','returned_capacities','effective_solve_limits_seconds'}),
            'regret_yuan':a.regret_matrix[c.candidate_id][c.scenario_id],
            'scenario_best_cost_yuan':a.scenario_best_costs[c.scenario_id],
            'worst_regret_yuan':a.worst_regret_yuan[c.candidate_id],'certification_status':a.status,
            'independently_valid':c.validation.valid if c.validation else None})
    with Path(result.files['csv']).open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# 多情景最小最大后悔决策报告',result.explanation,'## 授权情景（非预测）',
        *[json.dumps(s.model_dump(mode='json'),ensure_ascii=False) for s in result.scenarios],
        '## 固定配置与来源',*[json.dumps(c.model_dump(mode='json'),ensure_ascii=False) for c in result.candidates],
        '## 成本矩阵 / 后悔矩阵（元；null表示不可用，不是0）',
        json.dumps(a.cost_matrix,ensure_ascii=False),json.dumps(a.regret_matrix,ensure_ascii=False),
        '## 原始求解状态、独立复核和证据']
    lines += [f'- {c.candidate_id} / {c.scenario_id}：{c.solver_status or "未执行"}；{c.feasibility}；成本{c.cost_yuan}元；gap={c.mip_gap}；校验={c.validation.valid if c.validation else None}；run_id={c.run_id}；SHA={c.result_sha256}；原因{c.reasons}' for c in result.cells]
    lines += ['## 口径与资源',f'调用{result.solver_calls}次；耗时{result.elapsed_seconds:.3f}秒；限制{result.limits}。求解适配器可能内部执行LP/MILP两阶段，协作式时限不等于进程级硬截止。',
        '全年NPV使用原重复代表年、寿命、更换、残值、固定及变动维护假设；物理排放不折现，不含设备隐含排放。短期不乘52、不与全部投资相加称生命周期成本。',
        '每个情景的最佳基准包括该情景所有有效成本候选，包含在其他情景不可行的候选；未知单元与限时可行上界不能支撑精确认证。',
        '最小后悔是成熟准则；项目贡献为受限编排、物理校验、状态处理与可解释交互，不宣称理论原创。',
        '来源：'+json.dumps(result.sources,ensure_ascii=False)]
    Path(result.files['markdown']).write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    _atomic_json(result.files['json'],result)
