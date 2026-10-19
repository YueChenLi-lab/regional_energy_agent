"""Bounded single-constraint feasibility searches around the existing solvers.

No MILP is constructed here. Infeasibility, a verified feasible witness and an
unknown solver outcome are different oracle answers, never Boolean aliases.
"""
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Literal

from pydantic import Field, model_validator

from .data import validate_inputs
from .evaluation import validate_solution
from .schemas import Model, RunResult, SolutionValidation, SolverOptions, TaskRequest, ToolCall, ValidationRequest
from .storage import file_lock

RepairField = Literal['budget_yuan', 'emission_limit_kg', 'grid_limit_kw']
Feasibility = Literal['feasible', 'infeasible', 'uncertain', 'error', 'rejected']
LOCKS = {'budget_yuan', 'emission_limit_kg', 'grid_limit_kw', 'electric_load', 'heat_load',
         'period', 'service', 'devices', 'candidates', 'capacity_bounds', 'economics', 'pv_limit_kw', 'sources'}
NAMES = {'budget_yuan': '追加初始投资预算', 'emission_limit_kg': '放宽运行排放上限', 'grid_limit_kw': '增加购电功率上限'}


def counterfactual_enabled():
    return os.getenv('ENERGY_AGENT_ENABLE_COUNTERFACTUAL', '1').lower() not in ('0', 'false', 'off')


def digest(value) -> str:
    if isinstance(value, Model):
        value = value.model_dump(mode='json')
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def data_fingerprint(task: TaskRequest) -> str:
    return digest(task.data)


def unit_for(task, field):
    return {'budget_yuan': '元', 'grid_limit_kw': 'kW', 'emission_limit_kg': 'kg' + task.emission_species}[field]


class RepairRange(Model):
    lower: float = Field(ge=0, description='允许搜索的绝对下界，采用unit所示单位')
    upper: float = Field(ge=0, description='允许搜索的绝对上界')
    precision: float = Field(gt=0, description='可行/不可行边界区间的最大宽度，不是最优性间隙')
    unit: str

    @model_validator(mode='after')
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError('搜索下界不能超过上界')
        return self


class CounterfactualRequest(Model):
    request_id: str = Field(min_length=1, max_length=128)
    parent_request_id: str | None = None
    original_request: str = ''
    baseline: RunResult | None = None
    task: TaskRequest | None = None
    base_run_id: str = Field(min_length=1)
    input_version: int = Field(ge=1)
    data_fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    allowed_fields: list[RepairField] = Field(min_length=1, max_length=3)
    locked_conditions: list[str] = Field(default_factory=lambda: ['electric_load', 'heat_load', 'period', 'service'])
    ranges: dict[RepairField, RepairRange]
    explore_alternatives: bool = False
    single_solve_seconds: float = Field(default=5, gt=0, le=300)
    max_solver_calls: int = Field(default=48, ge=1, le=256)
    total_seconds: float = Field(default=60, gt=0, le=3600)
    mip_rel_gap: float = Field(default=1e-6, ge=0, le=.1)
    output_dir: str = 'outputs/counterfactual'

    @model_validator(mode='after')
    def permission_and_binding(self):
        if (self.task is None) == (self.baseline is None):
            raise ValueError('必须且只能提供task或已确认baseline之一')
        task = self.baseline.task if self.baseline else self.task
        if self.baseline and (self.baseline.run_id != self.base_run_id or self.baseline.input_version != self.input_version):
            raise ValueError('基准run_id或输入版本不匹配')
        if task.version != self.input_version or data_fingerprint(task) != self.data_fingerprint:
            raise ValueError('基准版本或原始数据指纹不匹配')
        if not validate_inputs(task).ready:
            raise ValueError('原任务缺少必要条件或数据不合法；请先修正输入，不能以放宽约束代替输入校验')
        if len(set(self.allowed_fields)) != len(self.allowed_fields) or set(self.allowed_fields) != set(self.ranges):
            raise ValueError('授权字段必须唯一，且与搜索区间字段完全一致')
        if set(self.locked_conditions) - LOCKS:
            raise ValueError('存在未支持的保持条件，不能静默忽略')
        if set(self.allowed_fields) & set(self.locked_conditions):
            raise ValueError('用户锁定的约束不得搜索或修改')
        for field, interval in self.ranges.items():
            original = getattr(task.constraints, field)
            if original is None:
                raise ValueError('原任务没有排放上限，不能假装存在可放宽的排放约束')
            if interval.unit != unit_for(task, field):
                raise ValueError(f'{field}单位必须为{unit_for(task, field)}')
            if interval.lower < original or interval.upper <= original:
                raise ValueError('只能放宽上限，搜索范围不能低于基准且必须包含大于原值的允许值')
            floor = .0001 if field == 'grid_limit_kw' else .001
            if interval.precision < floor:
                raise ValueError(f'{field}精度不得小于{floor} {interval.unit}，避免低于现有独立校验数值容差')
        if task.assessment_mode == 'electric_only' and '供热' in self.original_request:
            raise ValueError('当前电侧任务未建模供热，请先澄清服务边界，不能宣称保持供热保障')
        return self

    @property
    def original_task(self):
        return self.baseline.task if self.baseline else self.task


class RepairTrial(Model):
    phase: Literal['baseline', 'expand', 'bisect']
    field: RepairField | None = None
    value: float | None = None
    run_id: str
    input_version: int
    task_sha256: str
    data_fingerprint: str
    feasibility: Feasibility
    solver_statuses: dict[str, str]
    verified_precheck_exclusions: list[str] = Field(default_factory=list)
    locks_preserved: bool
    solver_calls: int
    effective_solve_limits_seconds: list[float] = Field(default_factory=list)
    seconds: float
    result_file: str
    result_sha256: str
    reasons: list[str]


class CounterfactualRepairPath(Model):
    path_id: str
    field: RepairField
    unit: str
    original_value: float
    search_range: RepairRange
    suggested_value: float | None = None
    adjustment: float | None = None
    known_infeasible_lower: float | None = None
    known_feasible_upper: float | None = None
    boundary_precision_reached: bool = False
    boundary_kind: Literal['bracket', 'permitted_left_edge', 'not_established'] = 'not_established'
    status: Literal['not_started', 'verified_repair', 'already_feasible', 'not_found', 'uncertain', 'budget_exhausted', 'error'] = 'not_started'
    locks_preserved: bool | None = None
    base_run_id: str
    new_input_version: int | None = None
    run_id: str | None = None
    result_file: str | None = None
    result_sha256: str | None = None
    candidate: dict | None = None
    metrics: dict | None = None
    npv_cost_yuan: float | None = None
    solver_status: str | None = None
    mip_gap: float | None = None
    solve_seconds: float | None = None
    final_validation: SolutionValidation | None = None
    sources: list[dict] = Field(default_factory=list)
    trace: list[RepairTrial] = Field(default_factory=list)
    note: str = ''


class CounterfactualResult(Model):
    request_id: str
    parent_request_id: str | None
    request_sha256: str
    base_run_id: str
    input_version: int
    input_sha256: str
    data_fingerprint: str
    status: Literal['completed', 'partial', 'not_started']
    baseline_verification: RepairTrial
    paths: list[CounterfactualRepairPath]
    solver_calls: int
    elapsed_seconds: float
    limits: dict
    allowed_fields: list[RepairField]
    locked_conditions: list[str]
    sources: list[dict]
    files: dict[str, str]
    note: str
    tool_call: ToolCall | None = None
    monotonicity: str = ('仅放宽预算、排放或购电功率上界，其余输入、固定候选集/容量边界和逐时足额供能保持，'
                         '因此原可行解在更宽上界下仍可行。该性质不把超时当成不可行，也不证明唯一冲突原因。')


def _preserved(original, modified, field):
    """Compare every non-authorized input, not just a hand-picked heat check."""
    a, b = original.model_dump(mode='json'), modified.model_dump(mode='json')
    source_ok = b['sources'][:len(a['sources'])] == a['sources'] and len(b['sources']) == len(a['sources']) + 1
    for value in (a, b):
        for key in ('version', 'parent_run_id', 'sources'):
            value.pop(key)
        value['constraints'].pop(field)
        value['constraints'].pop('source_id')
    return source_ok and digest(a) == digest(b) and modified.version == original.version + 1


class _BudgetExceeded(RuntimeError):
    pass


class _Budget:
    def __init__(self, req):
        self.req, self.started, self.calls = req, perf_counter(), 0
        self.exhausted = False
        self.call_limits = []

    def wrap(self, function):
        def solve(payload):
            remaining = self.req.total_seconds - (perf_counter() - self.started)
            if self.calls >= self.req.max_solver_calls or remaining <= 0:
                self.exhausted = True
                raise _BudgetExceeded('反事实搜索总调用/时间预算已用尽，未继续求解；这不是不可行证明')
            self.calls += 1
            options = payload.options.model_copy(update={'time_limit_seconds': min(self.req.single_solve_seconds, remaining)})
            self.call_limits.append(options.time_limit_seconds)
            return function(payload.model_copy(update={'options': options}))
        return solve


def _classify(run):
    # A verified incumbent suffices to prove feasibility, even without optimality.
    if any(s.validation.valid and s.dispatch.status in ('optimal', 'feasible_limit') for s in run.scenarios):
        return 'feasible', []
    expected = 1 if run.task.planning_mode == 'capacity' else len(run.task.candidates)
    excluded = []
    if run.issues:
        return ('uncertain' if any('_BudgetExceeded' in i.message for i in run.issues) else 'error'), excluded
    if len(run.scenarios) != expected:
        return 'uncertain', excluded
    for scenario in run.scenarios:
        # Rejected is NOT itself an infeasibility proof. Independently compute
        # only the two explicit fixed-candidate necessary planning conditions.
        if scenario.dispatch.status == 'rejected' and run.task.planning_mode == 'candidates':
            from .planning import investment_yuan
            if (investment_yuan(scenario.candidate, run.task.devices) > run.task.constraints.budget_yuan + 1e-7
                    or scenario.candidate.pv_kw > run.task.constraints.pv_limit_kw + 1e-7):
                excluded.append(scenario.candidate.candidate_id)
    if all(s.dispatch.status == 'infeasible' or s.candidate.candidate_id in excluded for s in run.scenarios):
        return 'infeasible', excluded
    if any(s.dispatch.status in ('error', 'invalid') for s in run.scenarios):
        return 'error', excluded
    if any(s.dispatch.status in ('optimal', 'feasible_limit') and not s.validation.valid for s in run.scenarios):
        return 'error', excluded
    if any(s.dispatch.status == 'rejected' for s in run.scenarios):
        return 'rejected', excluded
    return 'uncertain', excluded


def _atomic_json(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(data.model_dump_json(indent=2) if isinstance(data, Model) else json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def _render_report(result):
    lines = ['# 反事实约束修复报告', result.note,
             f'请求ID：{result.request_id}；基准run_id：{result.base_run_id}；输入版本：{result.input_version}。',
             f'原输入SHA-256：{result.input_sha256}；原数据指纹：{result.data_fingerprint}。',
             f'原任务复核：{result.baseline_verification.feasibility}；原始求解状态：{result.baseline_verification.solver_statuses}。',
             '锁定条件：' + '、'.join(result.locked_conditions) + '；每条路径其余全部业务输入亦保持不变。',
             result.monotonicity,
             '各路径是互为替代的单参数决策，不是必须同时修改的清单，不等于发现唯一不可行原因。探索结果不自动采用。']
    for p in result.paths:
        lines += [f'## {NAMES[p.field]} · {p.path_id}', f'状态：{p.status}。{p.note}',
                  f'原值：{p.original_value:g} {p.unit}；允许范围：[{p.search_range.lower:g}, {p.search_range.upper:g}]；精度：{p.search_range.precision:g} {p.unit}。']
        if p.suggested_value is not None:
            lines.append(f'已发现且复核可行：{p.suggested_value:g} {p.unit}；调整量：+{p.adjustment:g} {p.unit}。')
            lines.append(f'可行/不可行边界精度达到：{p.boundary_precision_reached}；已知不可行下界：{p.known_infeasible_lower}；已知可行上界：{p.known_feasible_upper}。')
            lines.append(f'替代运行：{p.run_id}；新版本：{p.new_input_version}；求解状态：{p.solver_status}；gap：{p.mip_gap}；求解耗时：{p.solve_seconds}秒；独立复核：{p.final_validation.valid}。')
            if p.solver_status == 'feasible_limit':
                lines.append('运行目标最优性未证明：这是经校验的可行见证，不能将其NPV称为已证明最优。可行性边界精度与运行目标最优性是不同结论。')
            lines.append('设备容量（kW / kWh / kW_th）：' + json.dumps(p.candidate, ensure_ascii=False))
            lines.append('指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：' + json.dumps(p.metrics, ensure_ascii=False))
            lines.append(f'NPV成本：{p.npv_cost_yuan if p.npv_cost_yuan is not None else "未启用全年经济评价"}。')
        lines.append('完整搜索轨迹：')
        lines += [f'- {t.phase}，{t.value}，{t.feasibility}，原始状态{t.solver_statuses}，run_id={t.run_id}，结果SHA={t.result_sha256}' for t in p.trace]
    lines += ['## 资源与来源', f'求解适配器调用：{result.solver_calls}；总耗时：{result.elapsed_seconds:.3f}秒；限制：{result.limits}。',
              '调用数统计现有求解适配器（含预检查），容量适配器内部可包含LP/MILP两阶段；时间预算为协作式，构模/校验/文件写出可能带来少量超时开销，耗时如实记录。',
              '来源：' + json.dumps(result.sources, ensure_ascii=False),
              '数据可为合成或混合研究情景，以上沿用原任务口径；不年化短时结果，不含设备隐含排放，不构成工程投资决定或理论原创性声明。']
    return '\n\n'.join(lines) + '\n'


def search_counterfactual_repairs(request: CounterfactualRequest) -> CounterfactualResult:
    """Explicit tool entry; durable request IDs never reapply a relaxation."""
    if not counterfactual_enabled():
        raise ValueError('反事实修复功能已关闭，不发起搜索')
    req = CounterfactualRequest.model_validate(request)
    request_sha = digest(req.model_dump(mode='json', exclude={'output_dir'}))
    directory = Path(req.output_dir) / hashlib.sha256(req.request_id.encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    with file_lock(directory / 'request.lock'):
        manifest, result_file = directory / 'request.json', directory / 'repair.json'
        if manifest.exists():
            stored = json.loads(manifest.read_text(encoding='utf-8'))
            if stored['request_sha256'] != request_sha:
                raise ValueError('同一request_id已绑定其他基准或权限/搜索参数，请恢复原请求或显式使用新ID')
            if result_file.exists():
                result = CounterfactualResult.model_validate_json(result_file.read_bytes())
                if result.request_sha256 != request_sha or result.input_sha256 != digest(req.original_task):
                    raise ValueError('搜索回执与固定基准不一致，拒绝重放')
                return result
            raise ValueError('此请求曾中断且没有完整回执；未自动重跑，需新ID显式重新授权资源预算')
        _atomic_json(manifest, {'request_sha256': request_sha, 'request': req.model_dump(mode='json')})
        return _search(req, request_sha, directory)


def _search(req, request_sha, directory):
    from .agent import EnergyAgent, Tool, revise_task
    from .schemas import TaskPatch
    budget = _Budget(req)
    options = SolverOptions(time_limit_seconds=req.single_solve_seconds, mip_rel_gap=req.mip_rel_gap)
    agent = EnergyAgent(directory / 'runs', options)
    for name in ('solve_dispatch', 'solve_capacity'):
        tool = agent.registry._tools[name]
        agent.registry._tools[name] = Tool(tool.input_schema, tool.output_schema, budget.wrap(tool.function))
    original = req.original_task

    def evaluate(task, phase, field=None, value=None):
        preserved = task == original if field is None else _preserved(original, task, field)
        if not preserved:
            raise ValueError('检测到未经授权的输入或服务变更，未调用求解器')
        calls, started = budget.calls, perf_counter()
        run = agent.run(task, previous=req.baseline if field else None)
        feasibility, excluded = _classify(run)
        preserved = digest(run.task) == digest(original) if field is None else _preserved(original, run.task, field)
        if not preserved:
            feasibility = 'error'
        path = Path(run.files['json'])
        trial = RepairTrial(phase=phase, field=field, value=value, run_id=run.run_id, input_version=run.input_version,
            task_sha256=digest(run.task), data_fingerprint=data_fingerprint(run.task), feasibility=feasibility,
            solver_statuses={s.candidate.candidate_id: s.dispatch.status for s in run.scenarios},
            verified_precheck_exclusions=excluded, locks_preserved=preserved, solver_calls=budget.calls-calls,
            effective_solve_limits_seconds=budget.call_limits[calls:],
            seconds=perf_counter()-started, result_file=str(path), result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            reasons=[i.message for i in run.issues] + [r for s in run.scenarios for r in s.dispatch.reasons]
                + ['独立校验失败：'+','.join(c.name for c in s.validation.checks if not c.passed)
                   for s in run.scenarios if s.dispatch.status in ('optimal','feasible_limit') and not s.validation.valid])
        return run, trial

    _, baseline = evaluate(original, 'baseline')  # Always recompute, never trust a prose "infeasible".
    permitted = baseline.feasibility == 'infeasible' or req.explore_alternatives
    paths = []
    for field in req.allowed_fields:
        interval = req.ranges[field]
        origin = getattr(original.constraints, field)
        p = CounterfactualRepairPath(path_id=digest([req.request_id, field])[:16], field=field, unit=interval.unit,
            original_value=origin, search_range=interval, base_run_id=req.base_run_id)
        paths.append(p)
        if not permitted:
            p.note = '原任务未被确认不可行，且用户未显式授权探索替代条件；未启动此路径。'
            continue
        if baseline.feasibility == 'feasible' and interval.lower == origin:
            p.status, p.note = 'already_feasible', '基准已有经校验可行解，无需追加条件；未伪造修复。'
            continue
        p.status = 'not_found'
        low = origin if baseline.feasibility == 'infeasible' else None
        best, best_trial = None, None
        left_edge = False
        next_value = interval.lower if interval.lower > origin else min(interval.upper, origin + max(interval.precision, (interval.upper-origin)/4))
        while True:
            if budget.calls >= req.max_solver_calls or perf_counter()-budget.started >= req.total_seconds:
                budget.exhausted = True
                p.status, p.note = 'budget_exhausted', '总调用/时间预算已用尽，未继续搜索；未得到不可行结论。'
                break
            task = revise_task(original, TaskPatch(**{field: next_value}), parent_run_id=req.base_run_id)
            task.sources[-1].processing.append('反事实探索；是否采用以单独的显式确认回执为准，未改写基准任务')
            run, trial = evaluate(task, 'bisect' if best is not None else 'expand', field, next_value)
            p.trace.append(trial)
            if trial.feasibility == 'feasible':
                best, best_trial = run, trial
                if next_value == interval.lower:
                    left_edge = True
                    break
            elif trial.feasibility == 'infeasible':
                low = next_value
            else:
                p.status = 'budget_exhausted' if budget.exhausted else 'uncertain' if trial.feasibility == 'uncertain' else 'error'
                p.note = '出现不确定、拒绝或失败状态，停止此路径的边界推断；未把它当作不可行下界。'
                break
            if best is not None:
                if low is None:
                    p.note = '找到可行方案，但没有已确认不可行下界；不宣称最小边界。'
                    break
                if best_trial.value - max(low, interval.lower) <= interval.precision:
                    break
                next_value = (best_trial.value + max(low, interval.lower))/2
            else:
                if next_value >= interval.upper:
                    p.note = '在当前范围内尚未找到经验证的修复方案；末端状态已保留，不归因于唯一约束。'
                    break
                next_value = min(interval.upper, origin + 2*(next_value-origin))
        p.locks_preserved = all(t.locks_preserved for t in p.trace) if p.trace else None
        p.known_infeasible_lower = low
        if best is not None:
            scenario = next(s for s in best.scenarios if s.validation.valid and s.dispatch.status in ('optimal', 'feasible_limit'))
            check = validate_solution(ValidationRequest(task=validate_inputs(best.task).task, candidate=scenario.candidate, dispatch=scenario.dispatch))
            if not check.valid or not _preserved(original, best.task, field):
                p.status, p.note = 'error', '最终独立复核或保持项核对失败，不输出可采用结果。'
                continue
            p.suggested_value, p.adjustment = best_trial.value, best_trial.value-origin
            p.known_feasible_upper = best_trial.value
            p.boundary_precision_reached = left_edge or (low is not None and best_trial.value-max(low, interval.lower) <= interval.precision
                                                        and p.status not in ('uncertain', 'budget_exhausted', 'error'))
            p.boundary_kind = 'permitted_left_edge' if left_edge else 'bracket' if p.boundary_precision_reached else 'not_established'
            p.new_input_version, p.run_id = best.input_version, best.run_id
            p.result_file, p.result_sha256 = best_trial.result_file, best_trial.result_sha256
            p.candidate, p.metrics = scenario.candidate.model_dump(mode='json'), {**check.metrics.model_dump(), 'emission_unit': 'kg' + original.emission_species}
            p.npv_cost_yuan = scenario.economics.npv_cost_yuan if scenario.economics else None
            p.solver_status, p.mip_gap, p.solve_seconds = scenario.dispatch.status, scenario.dispatch.mip_gap, scenario.dispatch.solve_seconds
            p.final_validation = check
            p.sources = [s.model_dump(mode='json') for s in best.task.sources]
            if p.status == 'not_found':
                p.status = 'verified_repair'
            if p.boundary_precision_reached:
                p.note = ('允许区间左端即有可行解；未探索区间之外的更低值。' if left_edge else '在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。')
            elif not p.note:
                p.note = '仅输出最小已发现的经校验可行调整，尚未完成指定边界精度。'
    status = 'not_started' if not permitted else 'partial' if any(p.status in ('uncertain', 'budget_exhausted', 'error') for p in paths) else 'completed'
    result = CounterfactualResult(request_id=req.request_id, parent_request_id=req.parent_request_id, request_sha256=request_sha,
        base_run_id=req.base_run_id, input_version=req.input_version, input_sha256=digest(original), data_fingerprint=req.data_fingerprint,
        status=status, baseline_verification=baseline, paths=paths, solver_calls=budget.calls, elapsed_seconds=perf_counter()-budget.started,
        limits={'single_solve_seconds': req.single_solve_seconds, 'max_solver_calls': req.max_solver_calls, 'total_seconds': req.total_seconds},
        allowed_fields=req.allowed_fields, locked_conditions=req.locked_conditions, sources=[s.model_dump(mode='json') for s in original.sources],
        files={'json': str(directory/'repair.json'), 'markdown': str(directory/'repair.md'), 'request': str(directory/'request.json')},
        note='在用户授权范围内搜索替代决策，保持全部负荷、时段、服务与其余业务输入；各路径互为替代，不自动采用。无可行上界时，只能说在当前范围内尚未找到经验证的修复方案。电侧模式不代表供热已建模或得到保障；购电上限放宽不含额外接入增容工程费用。')
    Path(result.files['markdown']).write_text(_render_report(result), encoding='utf-8')
    result.tool_call = ToolCall(run_id=req.request_id, input_version=req.input_version,
        tool_name='search_counterfactual_repairs', status='success', seconds=result.elapsed_seconds,
        summary=f'已执行受限搜索；状态{status}；求解适配器{budget.calls}次；不自动采用',
        source_ids=[s.source_id for s in original.sources], result_file=result.files['json'])
    _atomic_json(result.files['json'], result)
    return result


def adopt_counterfactual_path(result: CounterfactualResult, baseline: RunResult, path_id: str, *, confirmed: bool, adoption_id: str) -> RunResult:
    """Adopt a verified computed version only after explicit confirmation."""
    if not confirmed or not adoption_id:
        raise ValueError('必须显式确认采用并提供稳定adoption_id')
    if not counterfactual_enabled():
        raise ValueError('反事实修复功能已关闭，不采用新路径')
    stored = CounterfactualResult.model_validate_json(Path(result.files['json']).read_bytes())
    if digest(stored) != digest(result):
        raise ValueError('修复结果与保存的搜索回执不一致，拒绝采用')
    manifest = json.loads(Path(result.files['request']).read_text(encoding='utf-8'))
    permission = CounterfactualRequest.model_validate(manifest['request'])
    permission_sha = digest(permission.model_dump(mode='json', exclude={'output_dir'}))
    if permission_sha != result.request_sha256 or digest(permission.original_task) != result.input_sha256:
        raise ValueError('授权清单与固定输入不符，拒绝采用')
    if baseline.run_id != result.base_run_id or digest(baseline.task) != result.input_sha256:
        raise ValueError('当前确认任务与修复基准不匹配；不得将旧结果应用到新任务')
    path = next((p for p in result.paths if p.path_id == path_id), None)
    if path is None or path.suggested_value is None or not path.final_validation or not path.final_validation.valid:
        raise ValueError('该路径没有经独立校验的可采用运行')
    if (path.field not in permission.allowed_fields or path.field in permission.locked_conditions
            or not permission.ranges[path.field].lower <= path.suggested_value <= permission.ranges[path.field].upper):
        raise ValueError('路径超出用户授权范围')
    raw = Path(path.result_file).read_bytes()
    if hashlib.sha256(raw).hexdigest() != path.result_sha256:
        raise ValueError('替代运行文件校验值不符，拒绝采用')
    run = RunResult.model_validate_json(raw)
    if not any(t.run_id == run.run_id and t.feasibility == 'feasible' and t.result_sha256 == path.result_sha256
               and t.task_sha256 == digest(run.task) for t in path.trace):
        raise ValueError('路径缺少一致的实际搜索轨迹证据')
    if (run.run_id != path.run_id or not _preserved(baseline.task, run.task, path.field)
            or run.task.parent_run_id != baseline.run_id or getattr(run.task.constraints, path.field) != path.suggested_value):
        raise ValueError('替代运行与授权变更或基准不一致')
    scenario = next((s for s in run.scenarios if s.validation.valid), None)
    if not scenario or not validate_solution(ValidationRequest(task=validate_inputs(run.task).task, candidate=scenario.candidate, dispatch=scenario.dispatch)).valid:
        raise ValueError('采用前独立校验失败')
    receipt = Path(result.files['json']).parent / ('adopt_' + hashlib.sha256(adoption_id.encode()).hexdigest() + '.json')
    payload = {'adoption_id': adoption_id, 'base_run_id': baseline.run_id, 'request_sha256': result.request_sha256,
               'path_id': path_id, 'adopted_run_id': run.run_id, 'input_version': run.input_version}
    with file_lock(receipt.with_suffix('.lock')):
        if receipt.exists() and json.loads(receipt.read_text(encoding='utf-8')) != payload:
            raise ValueError('此采用ID已经绑定另一条路径')
        if not receipt.exists():
            _atomic_json(receipt, payload)
    return run


class RepairGuidance(Model):
    recognized: bool = False
    requested_fields: list[RepairField] = Field(default_factory=list)
    locked_fields: list[RepairField] = Field(default_factory=list)
    clarification: str


def clarify_repair_request(text: str, baseline: RunResult) -> RepairGuidance:
    """Small explicit offline routing, not arbitrary natural-language understanding.

    Suggestions are not authorization. Bounds and permissions still require the
    independent form; this deliberately leaves the old conversation untouched.
    """
    requests = {
        '预算不够，那至少还差多少？': (['budget_yuan'], []),
        '预算不能增加，碳约束可以放宽多少？': (['emission_limit_kg'], ['budget_yuan']),
        '保持供热不变，还有什么可行的调整？': ([], []),
        '给我三条可以比较的修复路径。': (['budget_yuan', 'emission_limit_kg', 'grid_limit_kw'], []),
    }
    normalized = text.strip().rstrip('。？！?!')
    matched = next((item for key,item in requests.items() if key.rstrip('。？！?!') == normalized),None)
    fields, locked = matched or ([], [])
    if 'emission_limit_kg' in fields and baseline.task.constraints.emission_limit_kg is None:
        fields = [f for f in fields if f != 'emission_limit_kg']
        note = '原任务没有排放上限，不能放宽不存在的约束。'
    else:
        note = ''
    if '供热' in text and baseline.task.assessment_mode == 'electric_only':
        return RepairGuidance(clarification='当前任务未建模供热；请先确认服务边界，不能声称供热保持或保障已验收。')
    return RepairGuidance(recognized=matched is not None,requested_fields=fields, locked_fields=locked,
        clarification=note + ('请在表单中明确勾选允许调整项、锁定项、绝对搜索上界和精度后执行。' if matched else '自由表述尚未可靠识别；请选用支持的问句或清空文本后仅通过表单明确授权。')
            + '此问句仅作路径建议，不求解、不授权、不修改基准。')
