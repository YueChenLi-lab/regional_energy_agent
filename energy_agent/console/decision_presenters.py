"""Pure, read-only ViewModels for the decision workbench.

No Streamlit, no solver, no LLM. Inputs are existing business models or plain
dicts with the same field names (``g`` reads either).

FIELD CONTRACT (every field below is already accessed by the existing code):
  RegretResult: request_id, base_run_id, input_version, cost_basis, case_label,
    candidates[].candidate/.capacity_sha256/.origin, scenarios[], cells[],
    analysis, solver_calls, elapsed_seconds, explanation, files
  RegretCell: candidate_id, scenario_id, feasibility, solver_status, cost_yuan,
    cost_is_optimal, investment_yuan, emissions_kg, operating_cost_yuan,
    mip_gap, solve_seconds, validation(.valid), capacities_fixed, run_id, reasons
  RegretAnalysis: status, cost_matrix, regret_matrix, scenario_best_costs,
    scenario_best_ids, full_scenario_feasible_ids, worst_regret_yuan,
    worst_scenario_ids, recommended_ids, provisional_ids, baseline_cheapest_ids,
    minimax_cost_ids, numerical_tolerance_yuan, note
  CounterfactualResult / RepairPath / RepairTrial: see counterfactual.py
  ConversationReply: request_id, status, text, pending, contract, run,
    explanation_verified, heat_unchanged
  PendingDialog: original_request, answers[{text,turn_id}], base_run_id,
    input_version, status, missing_fields[{field,question}], confirmed_conditions
Verified against v0.4.1 schemas/conversation/modifications. Contract.ready is a
property (not serialized); dict snapshots derive it from edits and missing.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import Any, Mapping

MISSING = '—'
REPLY_STATUS = {'clarification': '等待澄清', 'completed': '已完成', 'cancelled': '已取消'}
DIALOG_STATUS = {'awaiting_answer': '等待你的回答', 'ready': '待接续', 'completed': '已完成', 'cancelled': '已取消'}


def g(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def num(value: Any, decimals: int = 2, unit: str = '') -> str:
    """None is missing, never a manufactured zero."""
    if value is None or isinstance(value, bool):
        return MISSING
    try:
        number = float(value)
        if not isfinite(number):
            return MISSING
        text = f'{number:,.{decimals}f}'
    except (TypeError, ValueError, OverflowError):
        return MISSING
    return f'{text} {unit}'.strip()


@dataclass(frozen=True)
class Badge:
    text: str
    tone: str = 'muted'  # good | warn | bad | info | muted


# ───────────────────────── regret ─────────────────────────
SCENARIO_FIELDS = (('electricity_price_multiplier', '购电价格'), ('gas_price_multiplier', '燃气价格'),
                   ('pv_multiplier', '光伏出力'), ('electric_load_multiplier', '电负荷'))
CAPACITY_ROWS = (('pv_kw', '光伏', 'kW'), ('battery_power_kw', '储能功率', 'kW'),
                 ('battery_energy_kwh', '储能容量', 'kWh'), ('hp_kw_th', '热泵', 'kW_th'),
                 ('boiler_kw_th', '锅炉', 'kW_th'))
CELL_TEXT = {'infeasible': '不可行', 'unknown': '未完成', 'rejected': '被拒绝', 'error': '错误', 'not_run': '未执行'}
CELL_LABEL = {'optimal': '已证明最优', 'upper_bound': '可行 · 成本为上界（未证明最优）',
              'infeasible': '已确认不可行', 'unknown': '求解未完成 · 未确定（不等于不可行）',
              'rejected': '预检查拒绝', 'error': '求解或校验错误', 'not_run': '未执行（预算耗尽等，不是不可行）'}
REGRET_STATUS = {'certified': ('已认证 · 仅限当前有限矩阵', 'good'),
                 'approximate': ('近似结果 · 含成本上界', 'warn'),
                 'partial': ('部分结果 · 存在未定单元', 'warn'),
                 'no_recommendation': ('无完整推荐', 'bad')}
SOLVER_LABEL = {'optimal': '已证明最优（当前模型）', 'feasible_limit': '可行解 · 未证明最优',
                'no_solution_limit': '达到限制 · 未找到解', 'infeasible': '求解无解',
                'rejected': '预检查不通过', 'error': '求解错误', 'invalid': '校验不通过'}


def cell_kind(cell: Any) -> str:
    feasibility = g(cell, 'feasibility')
    if feasibility == 'feasible':
        if g(g(cell, 'validation'), 'valid') is not True or g(cell, 'capacities_fixed') is not True:
            return 'error'
        if g(cell, 'solver_status') not in ('optimal', 'feasible_limit'):
            return 'unknown'
        return 'optimal' if (g(cell, 'cost_is_optimal') and g(cell, 'solver_status')=='optimal' and g(cell, 'mip_gap')==0) else 'upper_bound'
    return {'infeasible': 'infeasible', 'uncertain': 'unknown', 'rejected': 'rejected',
            'error': 'error', 'not_run': 'not_run'}.get(feasibility, 'unknown')


@dataclass(frozen=True)
class ScenarioVM:
    id: str
    name: str
    is_baseline: bool
    chips: tuple[str, ...]
    assumption: str


@dataclass(frozen=True)
class CellVM:
    candidate_id: str
    scenario_id: str
    kind: str
    cost: float | None
    regret: float | None
    cost_text: str
    regret_text: str
    cost_level: int | None
    regret_level: int | None
    regret_zero: bool
    scenario_best: bool
    tooltip: str
    detail: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CandidateVM:
    id: str
    name: str
    origin: str
    capacities: tuple[tuple[str, str], ...]
    capacity_sha8: str
    capacities_consistent: bool | None
    investment: str
    recommended: bool
    provisional: bool
    baseline_cheapest: bool
    minimax_cost: bool
    eligible: bool
    worst_regret: float | None
    worst_scenarios: tuple[str, ...]
    feasible_count: int
    total: int
    infeasible_count: int
    unresolved_count: int


@dataclass(frozen=True)
class RegretVM:
    status: str
    status_label: str
    status_tone: str
    status_note: str
    request_id: str
    base_run_id: str
    input_version: Any
    solver_calls: Any
    elapsed: str
    basis_title: str
    basis_note: str
    period_note: str
    case_label: str
    scenarios: tuple[ScenarioVM, ...]
    candidates: tuple[CandidateVM, ...]
    cells: dict
    recommended_ids: tuple[str, ...]
    provisional_ids: tuple[str, ...]
    baseline_cheapest_ids: tuple[str, ...]
    minimax_cost_ids: tuple[str, ...]
    cost_range: tuple[float | None, float | None]
    regret_max: float | None
    paragraphs: tuple[str, ...]
    unresolved: int
    infeasible: int
    tolerance: float


def _level(value, lo, hi):
    if value is None:
        return None
    if hi is None or lo is None or hi <= lo:
        return 0
    return max(0, min(9, round(9 * (value - lo) / (hi - lo))))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _scenario_vm(s: Any) -> ScenarioVM:
    chips = tuple(f'{label} ×{g(s, key):g}' for key, label in SCENARIO_FIELDS
                  if finite(g(s, key)) and g(s, key) != 1)
    return ScenarioVM(id=g(s, 'scenario_id', ''), name=g(s, 'name', ''), is_baseline=bool(g(s, 'is_baseline')),
                      chips=chips, assumption=g(s, 'assumption', '') or '')


def build_regret_vm(result: Any) -> RegretVM:
    a = g(result, 'analysis')
    tol = float(g(a, 'numerical_tolerance_yuan', 1e-4) or 1e-4)
    cost_m = g(a, 'cost_matrix', {}) or {}
    regret_m = g(a, 'regret_matrix', {}) or {}
    best = g(a, 'scenario_best_costs', {}) or {}
    best_ids = g(a, 'scenario_best_ids', {}) or {}
    worst = g(a, 'worst_regret_yuan', {}) or {}
    worst_scn = g(a, 'worst_scenario_ids', {}) or {}
    eligible = set(g(a, 'full_scenario_feasible_ids', []) or [])
    recommended = tuple(g(a, 'recommended_ids', []) or [])
    provisional = tuple(g(a, 'provisional_ids', []) or [])
    cheapest = tuple(g(a, 'baseline_cheapest_ids', []) or [])
    minimax_cost = tuple(g(a, 'minimax_cost_ids', []) or [])
    raw_cells = {(g(c, 'candidate_id'), g(c, 'scenario_id')): c for c in (g(result, 'cells', []) or [])}
    scenarios = tuple(_scenario_vm(s) for s in (g(result, 'scenarios', []) or []))
    scen_name = {s.id: s.name for s in scenarios}

    # 1) status per cell; numbers only for cells that are verified feasible
    kinds, costs, regrets = {}, {}, {}
    for cid in (g(g(sel, 'candidate'), 'candidate_id') for sel in (g(result, 'candidates', []) or [])):
        for s in scenarios:
            raw = raw_cells.get((cid, s.id))
            kind = cell_kind(raw) if raw is not None else 'not_run'
            cost = (cost_m.get(cid) or {}).get(s.id)
            regret = (regret_m.get(cid) or {}).get(s.id)
            if kind in ('optimal', 'upper_bound') and (not finite(cost) or not finite(g(raw,'cost_yuan')) or abs(cost-g(raw,'cost_yuan'))>tol):
                kind = 'unknown'
            if regret is not None and (not finite(regret) or regret < -tol):
                kind = 'error'
            if kind not in ('optimal', 'upper_bound'):
                cost = regret = None
            kinds[(cid, s.id)], costs[(cid, s.id)], regrets[(cid, s.id)] = kind, cost, regret
    valid_costs = [v for v in costs.values() if v is not None]
    valid_regrets = [v for v in regrets.values() if v is not None]
    lo, hi = (min(valid_costs), max(valid_costs)) if valid_costs else (None, None)
    rmax = max(valid_regrets) if valid_regrets else None

    # 2) cells
    cells: dict = {}
    for (cid, sid), kind in kinds.items():
        raw = raw_cells.get((cid, sid))
        cost, regret = costs[(cid, sid)], regrets[(cid, sid)]
        zero = regret is not None and regret <= tol
        r_level = None
        if regret is not None and not zero and rmax and rmax > tol:
            r_level = max(1, min(9, 1 + round(8 * regret / rmax)))
        elif regret is not None and not zero:
            r_level = 1
        prefix = '≤ ' if kind == 'upper_bound' else ''
        cost_text = f'{prefix}{cost:,.0f}' if cost is not None else CELL_TEXT.get(kind, MISSING)
        regret_text = ('0' if zero else f'≈ {regret:,.0f}' if kind == 'upper_bound' else f'{regret:,.0f}') \
            if regret is not None else CELL_TEXT.get(kind, MISSING)
        validation = g(raw, 'validation')
        valid_flag = g(validation, 'valid')
        reasons = [str(r) for r in (g(raw, 'reasons', []) or [])]
        detail = (
            ('状态', CELL_LABEL[kind]), ('成本（元）', num(cost, 2)), ('后悔（元）', num(regret, 2)),
            ('该情景当前候选集最佳成本（元）', num(best.get(sid), 2)),
            ('初始投资（元）', num(g(raw, 'investment_yuan'), 2)),
            ('运行排放（kg，物质见原任务）', num(g(raw, 'emissions_kg'), 2)),
            ('求解状态', SOLVER_LABEL.get(g(raw, 'solver_status'), str(g(raw, 'solver_status') or '未执行'))),
            ('相对间隙 gap', num(g(raw, 'mip_gap'), 6) if g(raw, 'mip_gap') is not None else '未提供'),
            ('求解耗时（秒）', num(g(raw, 'solve_seconds'), 3)),
            ('独立校验', '通过' if valid_flag is True else '未通过' if valid_flag is False else '未执行'),
            ('run_id', str(g(raw, 'run_id') or MISSING)),
        ) + ((('原因', reasons[0]),) if reasons else ())
        tooltip = '\n'.join([f'{cid} × {scen_name.get(sid, sid)}', f'状态：{CELL_LABEL[kind]}',
                             f'成本：{num(cost, 2, "元")}', f'后悔：{num(regret, 2, "元")}'] +
                            ([f'原因：{reasons[0]}'] if reasons and cost is None else []))
        cells[(cid, sid)] = CellVM(
            candidate_id=cid, scenario_id=sid, kind=kind, cost=cost, regret=regret,
            cost_text=cost_text, regret_text=regret_text, cost_level=_level(cost, lo, hi),
            regret_level=r_level, regret_zero=bool(zero), scenario_best=cid in (best_ids.get(sid) or []) and cost is not None,
            tooltip=tooltip, detail=detail)

    # 3) candidates
    candidates = []
    for sel in (g(result, 'candidates', []) or []):
        cand = g(sel, 'candidate')
        cid = g(cand, 'candidate_id', '')
        own = [raw_cells[k] for k in raw_cells if k[0] == cid]
        fixed = [g(c, 'capacities_fixed') for c in own]
        consistent = False if any(f is False for f in fixed) else True if len(fixed)==len(scenarios) and all(f is True for f in fixed) else None
        row_kinds = [cells[(cid, s.id)].kind for s in scenarios if (cid, s.id) in cells]
        invest = next((g(c, 'investment_yuan') for c in own if g(c, 'investment_yuan') is not None), None)
        candidates.append(CandidateVM(
            id=cid, name=g(cand, 'name', '') or '', origin='任务候选' if g(sel, 'origin') == 'task' else '已求得配置',
            capacities=tuple((label, num(g(cand, key), 2, unit)) for key, label, unit in CAPACITY_ROWS),
            capacity_sha8=str(g(sel, 'capacity_sha256', ''))[:8], capacities_consistent=consistent,
            investment=num(invest, 0, '元'), recommended=cid in recommended, provisional=cid in provisional,
            baseline_cheapest=cid in cheapest, minimax_cost=cid in minimax_cost, eligible=cid in eligible,
            worst_regret=worst.get(cid) if finite(worst.get(cid)) and len(row_kinds)==len(scenarios) and all(k in ('optimal','upper_bound') for k in row_kinds) else None, worst_scenarios=tuple(scen_name.get(s, s) for s in (worst_scn.get(cid) or [])),
            feasible_count=sum(k in ('optimal', 'upper_bound') for k in row_kinds), total=len(row_kinds),
            infeasible_count=row_kinds.count('infeasible'),
            unresolved_count=sum(k in ('unknown', 'rejected', 'error', 'not_run') for k in row_kinds)))

    status = g(a, 'status', 'no_recommendation')
    integrity_warning = any(g(raw_cells.get(pair),'feasibility')=='feasible' and kind not in ('optimal','upper_bound')
                            for pair,kind in kinds.items())
    if status=='certified' and 'upper_bound' in kinds.values():
        status='approximate'
    if status in ('certified','approximate') and any(kind not in ('optimal','upper_bound','infeasible') for kind in kinds.values()):
        status='partial'
        recommended=()
        candidates=[replace(c,recommended=False) for c in candidates]
    label, tone = REGRET_STATUS.get(status, (str(status), 'muted'))
    npv = g(result, 'cost_basis') == 'npv'
    hours = next((g(g(g(c, 'validation'), 'metrics'), 'period_hours') for c in raw_cells.values()
                  if g(g(g(c, 'validation'), 'metrics'), 'period_hours') is not None), None)
    all_kinds = [c.kind for c in cells.values()]
    return RegretVM(
        status=status, status_label=label, status_tone=tone, status_note=('展示完整性核对未通过；原始声明不能作为完整认证。' if integrity_warning else g(a, 'note', '') or ''),
        request_id=str(g(result, 'request_id', '')), base_run_id=str(g(result, 'base_run_id', '')),
        input_version=g(result, 'input_version'), solver_calls=g(result, 'solver_calls'),
        elapsed=num(g(result, 'elapsed_seconds'), 2, '秒'),
        basis_title='规划期 NPV 成本' if npv else '评估期购能费',
        basis_note='含投资、维护、更换、残值，沿用原任务经济参数；物理排放不折现' if npv
        else '仅比较评估期运行购能费；初始投资另列，不是生命周期成本，不年化',
        period_note=f'评估期 {hours:g} 小时' if (hours and not npv) else '',
        case_label=str(g(result, 'case_label', '') or ''), scenarios=scenarios, candidates=tuple(candidates),
        cells=cells, recommended_ids=recommended, provisional_ids=provisional, baseline_cheapest_ids=cheapest,
        minimax_cost_ids=minimax_cost, cost_range=(lo, hi), regret_max=rmax,
        paragraphs=(('展示完整性核对未通过；不提供完整推荐，原始声明仅在证据区保留。',) if integrity_warning else
                    tuple(p for p in str(g(result, 'explanation', '') or '').split('\n\n') if p.strip())),
        unresolved=sum(k in ('unknown', 'rejected', 'error', 'not_run') for k in all_kinds),
        infeasible=all_kinds.count('infeasible'), tolerance=tol)


# ─────────────────── counterfactual ───────────────────
CF_STATUS = {'not_started': ('未启动', 'muted'), 'verified_repair': ('已验证可行调整', 'good'),
             'already_feasible': ('基准已可行', 'info'), 'not_found': ('范围内尚未找到', 'warn'),
             'uncertain': ('边界不确定', 'warn'), 'budget_exhausted': ('搜索预算耗尽', 'warn'),
             'error': ('求解或校验失败', 'bad')}
CF_RESULT_STATUS = {'completed': ('搜索完成', 'good'), 'partial': ('部分完成', 'warn'), 'not_started': ('未启动', 'muted')}
FEASIBILITY_TEXT = {'feasible': '可行', 'infeasible': '不可行', 'uncertain': '未确定', 'error': '错误', 'rejected': '被拒绝'}
_FALLBACK_TITLES = {'budget_yuan': '追加初始投资预算', 'emission_limit_kg': '放宽运行排放上限', 'grid_limit_kw': '增加购电功率上限'}


def path_title(field_name: str) -> str:
    try:  # keep in sync with counterfactual.NAMES
        from ..counterfactual import NAMES
        return NAMES.get(field_name, field_name)
    except Exception:
        return _FALLBACK_TITLES.get(field_name, field_name)


@dataclass(frozen=True)
class BoundaryVM:
    unit: str
    drawable: bool
    kind: str
    reached: bool
    segments: tuple[tuple[str, float, float, str], ...]   # kind, start%, end%, label
    markers: tuple[tuple[str, float, str], ...]           # kind, pos%, label
    trials: tuple[tuple[str, float, str], ...]            # feasibility, pos%, tooltip
    scale: tuple[str, str]
    readout: tuple[str, ...]


@dataclass(frozen=True)
class PathVM:
    path_id: str
    field: str
    index: int
    title: str
    unit: str
    status: str
    status_label: str
    tone: str
    note: str
    original_text: str
    suggested_text: str | None
    adjustment_text: str | None
    verified: bool
    can_adopt: bool
    boundary: BoundaryVM
    candidate_name: str | None
    capacities: tuple[tuple[str, str], ...]
    metrics: tuple[tuple[str, str], ...]
    solver_label: str | None
    gap_text: str
    seconds_text: str
    validation_text: str
    validation_ok: bool | None
    caveat: str
    trace_header: tuple[str, ...]
    trace_rows: tuple[tuple[str, ...], ...]
    run_id: str | None


@dataclass(frozen=True)
class CounterfactualVM:
    status: str
    status_label: str
    status_tone: str
    baseline_label: str
    baseline_tone: str
    baseline_reasons: tuple[str, ...]
    solver_calls: Any
    elapsed: str
    limits: tuple[tuple[str, str], ...]
    locked: tuple[str, ...]
    paths: tuple[PathVM, ...]
    note: str
    monotonicity: str
    request_id: str
    base_run_id: str
    input_version: Any


def _boundary(p: Any) -> BoundaryVM:
    rng = g(p, 'search_range')
    lo, hi, prec = g(rng, 'lower'), g(rng, 'upper'), g(rng, 'precision')
    origin, unit = g(p, 'original_value'), g(p, 'unit', '') or ''
    lower, upper = g(p, 'known_infeasible_lower'), g(p, 'known_feasible_upper')
    kind = g(p, 'boundary_kind', 'not_established')
    if not all(finite(v) for v in (origin,lo,hi,prec)) or hi<=origin or prec<=0:
        return BoundaryVM(unit, False, kind, False, (), (), (), (MISSING,MISSING), ('没有合法范围，不绘制边界',))
    def pos(value):
        return max(0.,min(100.,100*(value-origin)/(hi-origin)))
    trace = list(g(p,'trace',[]) or [])
    def evidenced(value,feasibility):
        return finite(value) and any(g(t,'locks_preserved') is True and g(t,'feasibility')==feasibility
            and ((finite(g(t,'value')) and abs(g(t,'value')-value)<=1e-8)
                 or g(t,'phase')=='baseline' and abs(value-origin)<=1e-8) for t in trace)
    locked = g(p,'locks_preserved') is True
    verified = (g(p,'status')=='verified_repair' and locked and g(g(p,'final_validation'),'valid') is True
                and g(p,'solver_status') in ('optimal','feasible_limit'))
    bracket = (verified and kind=='bracket' and evidenced(lower,'infeasible') and evidenced(upper,'feasible')
               and origin<=lower<upper<=hi)
    edge = (verified and kind=='permitted_left_edge' and evidenced(upper,'feasible')
            and abs(upper-lo)<=1e-8 and origin<=lo<=hi)
    reached = bool(g(p,'boundary_precision_reached')) and (bracket and upper-lower<=prec+1e-8 or edge)
    segments=[];markers=[('orig',0.,'原值 '+num(origin,2,unit))];readout=[]
    if bracket:
        segments=[('inf',0.,pos(lower),'单调范围内已证不可行'),('gap',pos(lower),pos(upper),'未判定'),('ok',pos(upper),100.,'原可行见证可保持')]
        markers += [('inf',pos(lower),'已测不可行 '+num(lower,4,unit)),('ok',pos(upper),'已测可行 '+num(upper,4,unit))]
        readout=[f'经证据核对的不可行下界 {num(lower,4,unit)} / 可行上界 {num(upper,4,unit)}',
                 f'区间宽度 {num(upper-lower,4,unit)}；精度 {num(prec,4,unit)}；'+('已达指定精度' if reached else '未达指定精度')]
    elif edge:
        segments=[('out',0.,pos(lo),'范围外未检验'),('ok',pos(upper),100.,'原可行见证可保持')]
        markers += [('ok',pos(upper),'已测可行 '+num(upper,4,unit))]
        readout=['允许搜索下界已可行；未证明范围外最小值。']
    else:
        readout=['尚无经证据核对的可靠边界；中性轴仅显示已记录测试点，不推断区间可行性。']
    trials=tuple((g(t,'feasibility','uncertain'),pos(g(t,'value')),
                  num(g(t,'value'),4,unit)+' · '+FEASIBILITY_TEXT.get(g(t,'feasibility'),'未确定'))
                 for t in trace if finite(g(t,'value')) and origin<=g(t,'value')<=hi)
    return BoundaryVM(unit,True,kind,reached,tuple(segments),tuple(markers),trials,
                      (num(origin,2,unit),num(hi,2,unit)),tuple(readout))


def _path_vm(p: Any, index: int) -> PathVM:
    status = g(p, 'status', 'not_started')
    label, tone = CF_STATUS.get(status, (str(status), 'muted'))
    unit = g(p, 'unit', '') or ''
    sug = g(p, 'suggested_value')
    verified = (status == 'verified_repair' and finite(sug) and g(g(p,'final_validation'),'valid') is True
                and g(p,'locks_preserved') is True and g(p,'solver_status') in ('optimal','feasible_limit'))
    validation = g(p, 'final_validation')
    checks = list(g(validation, 'checks', []) or [])
    passed = sum(1 for c in checks if g(c, 'passed'))
    m = g(p, 'metrics') or {}
    hours = m.get('period_hours') if isinstance(m, Mapping) else None
    op_label = '年度购能费' if hours and hours >= 8000 else f'评估期购能费（{hours:g} h）' if hours else '评估期购能费'
    npv = g(p, 'npv_cost_yuan')
    metrics = ()
    if verified and isinstance(m, Mapping):
        metrics = (('初始投资', num(m.get('investment_yuan'), 2, '元')), (op_label, num(m.get('operating_cost_yuan'), 2, '元')),
                   ('运行排放', num(m.get('emissions_kg'), 2, m.get('emission_unit', ''))),
                   ('NPV 成本', num(npv, 2, '元') if npv is not None else '未启用全年经济评价'))
    cand = g(p, 'candidate') or {}
    solver = g(p, 'solver_status')
    trace = tuple((str(i + 1), str(g(t, 'phase')), num(g(t, 'value'), 4, unit),
                   FEASIBILITY_TEXT.get(g(t, 'feasibility'), str(g(t, 'feasibility'))),
                   ' / '.join(f'{k}:{v}' for k, v in (g(t, 'solver_statuses', {}) or {}).items()),
                   str(g(t, 'solver_calls')), str(g(t, 'run_id', ''))[:8])
                  for i, t in enumerate(g(p, 'trace', []) or []))
    return PathVM(
        path_id=str(g(p, 'path_id', '')), field=g(p, 'field', ''), index=index, title=path_title(g(p, 'field', '')),
        unit=unit, status=status, status_label=label, tone=tone, note=g(p, 'note', '') or '',
        original_text=num(g(p, 'original_value'), 2, unit),
        suggested_text=num(sug, 2, unit) if verified else None,
        adjustment_text=('+' + num(g(p, 'adjustment'), 2, unit)) if verified and g(p, 'adjustment') is not None else None,
        verified=verified, can_adopt=bool(verified and g(validation, 'valid') is True), boundary=_boundary(p),
        candidate_name=(f'{g(cand, "candidate_id")} · {g(cand, "name")}' if cand and verified else None),
        capacities=tuple((lab, num(g(cand,key),2,u)) for key, lab, u in CAPACITY_ROWS) if cand and verified else (),
        metrics=metrics, solver_label=SOLVER_LABEL.get(solver, solver) if verified else None,
        gap_text=num(g(p, 'mip_gap'), 6) if g(p, 'mip_gap') is not None else '未提供',
        seconds_text=num(g(p, 'solve_seconds'), 3, '秒'),
        validation_text=f'独立复核 {passed}/{len(checks)} 项通过' if checks else '未执行独立复核',
        validation_ok=g(validation, 'valid'),
        caveat=('已有经校验的可行方案，运行目标最优性未证明；边界搜索精度与目标最优性间隙是两个不同结论。'
                if solver == 'feasible_limit' else ''),
        trace_header=('#', '阶段', '取值', '可行性', '各方案求解状态', '调用', 'run_id'),
        trace_rows=trace, run_id=g(p, 'run_id'))


def build_counterfactual_vm(result: Any) -> CounterfactualVM:
    status = g(result, 'status', 'not_started')
    label, tone = CF_RESULT_STATUS.get(status, (str(status), 'muted'))
    baseline = g(result, 'baseline_verification')
    feas = g(baseline, 'feasibility')
    b_tone = {'infeasible': 'bad', 'feasible': 'good'}.get(feas, 'warn')
    limits = g(result, 'limits', {}) or {}
    return CounterfactualVM(
        status=status, status_label=label, status_tone=tone,
        baseline_label=f'原任务复核：{FEASIBILITY_TEXT.get(feas, feas or MISSING)}', baseline_tone=b_tone,
        baseline_reasons=tuple(str(r) for r in (g(baseline, 'reasons', []) or [])[:3]),
        solver_calls=g(result, 'solver_calls'), elapsed=num(g(result, 'elapsed_seconds'), 2, '秒'),
        limits=(('单次求解时限', num(limits.get('single_solve_seconds'), 1, '秒')),
                ('调用上限', str(limits.get('max_solver_calls', MISSING))),
                ('总时间预算', num(limits.get('total_seconds'), 1, '秒'))),
        locked=tuple(g(result, 'locked_conditions', []) or []),
        paths=tuple(_path_vm(p, ('budget_yuan','emission_limit_kg','grid_limit_kw').index(g(p,'field')))
                    for p in (g(result,'paths',[]) or []) if g(p,'field') in _FALLBACK_TITLES),
        note=g(result, 'note', '') or '', monotonicity=g(result, 'monotonicity', '') or '',
        request_id=str(g(result, 'request_id', '')), base_run_id=str(g(result, 'base_run_id', '')),
        input_version=g(result, 'input_version'))


# ─────────────────── conversation ───────────────────
KIND_LABEL = {'USER_MESSAGE': '你的请求', 'AGENT_CLARIFICATION': 'Agent 需要澄清', 'AGENT_CONFIRMATION': '等待你确认',
              'TOOL_PENDING': '工具待执行', 'TOOL_RUNNING': '工具执行中', 'TOOL_RESULT': '工具结果',
              'TOOL_UNCERTAIN': '结果未确定', 'AGENT_EXPLANATION': 'Agent 解释', 'ERROR_MESSAGE': '错误'}
# TOOL_RUNNING is reserved: persisted snapshots carry no live progress, so it is never emitted here.
STAGES = (('understand', '理解请求'), ('authorize', '校验与授权'), ('execute', '工具执行'),
          ('verify', '独立复核'), ('explain', '结果解释'))
STATE_TEXT = {'pending': '未开始', 'running': '进行中', 'done': '已完成', 'clarify': '需澄清',
              'uncertain': '未确定', 'failed': '失败'}


@dataclass(frozen=True)
class MessageVM:
    kind: str
    role: str  # user | assistant | tool
    title: str
    body: str = ''
    chips: tuple[Badge, ...] = ()
    items: tuple[str, ...] = ()
    metrics: tuple[tuple[str, str, str], ...] = ()
    tone: str = 'muted'


@dataclass(frozen=True)
class StageVM:
    key: str
    label: str
    state: str
    detail: str = ''


@dataclass(frozen=True)
class ConversationVM:
    empty: bool
    messages: tuple[MessageVM, ...]
    stages: tuple[StageVM, ...]


def _brief(contract: Any) -> tuple[list[str], str]:
    try:
        from ..conversation import contract_brief
        from ..modifications import ModificationContract
        brief = contract_brief(ModificationContract.model_validate(contract) if isinstance(contract,Mapping) else contract)
        return list(brief.get('changes') or []), str(brief.get('preserves') or '')
    except Exception:  # display-only; unknown contract shape must not break the page
        return [], ''


def recommended_metrics(run: Any) -> dict | None:
    rid = g(g(run, 'comparison'), 'recommended_id')
    sc = next((s for s in (g(run, 'scenarios', []) or []) if g(g(s, 'candidate'), 'candidate_id') == rid), None)
    if sc is None or g(g(sc,'validation'),'valid') is not True:
        return None
    m, task = g(g(sc, 'validation'), 'metrics'), g(run, 'task')
    return dict(candidate_id=rid, name=g(g(sc, 'candidate'), 'name'), investment=g(sc, 'investment_yuan'),
                operating=g(m, 'operating_cost_yuan'), emissions=g(m, 'emissions_kg'),
                npv=g(g(sc, 'economics'), 'npv_cost_yuan'), full_year=g(task, 'resolution') == 'full_year',
                species=g(task, 'emission_species') or '')


def _result_metrics(rm: dict) -> tuple[tuple[str, str, str], ...]:
    return (('初始投资', num(rm['investment'], 2), '元'),
            ('年度购能费' if rm['full_year'] else '评估期运行费', num(rm['operating'], 2), '元'),
            ('NPV 成本', num(rm['npv'], 2) if rm['npv'] is not None else '未启用', '元 · 按任务规划期' if rm['npv'] is not None else ''),
            ('年度运行排放' if rm['full_year'] else '评估期运行排放', num(rm['emissions'], 2), 'kg' + str(rm['species'])))


def derive_stages(reply: Any) -> tuple[StageVM, ...]:
    if reply is None:
        return tuple(StageVM(k, l, 'pending') for k, l in STAGES)
    pending, contract, run = g(reply, 'pending'), g(reply, 'contract'), g(reply, 'run')
    missing = g(pending, 'missing_fields') or []
    awaiting = g(pending, 'status') == 'awaiting_answer' and bool(missing)
    cancelled = g(pending, 'status') == 'cancelled'
    scenarios = list(g(run, 'scenarios', []) or [])
    if run is None and g(reply, 'study') is not None:
        return (StageVM('understand', '理解请求', 'done'), StageVM('authorize', '校验与授权', 'done'),
                StageVM('execute', '工具执行', 'done', '敏感性扫描已完成'),
                StageVM('verify', '独立复核', 'pending', '扫描结果不适用逐方案校验'),
                StageVM('explain', '结果解释', 'done'))
    st = {}
    st['understand'] = ('clarify', f'待补 {len(missing)} 项') if awaiting else ('done', '')
    if awaiting:
        st['authorize'] = ('pending', '等待回答')
    elif cancelled:
        st['authorize'] = ('pending', '请求已取消')
    elif contract is not None:
        ready = g(contract, 'ready', bool(g(contract,'edits')) and not g(contract,'missing'))
        st['authorize'] = ('done', f'保留项 {len(g(contract, "preserves", []) or [])}') if ready is not False \
            else ('clarify', '修改契约未就绪')
    else:
        st['authorize'] = ('done', '') if run is not None else ('pending', '')
    if run is None:
        st['execute'] = st['verify'] = st['explain'] = ('pending', '')
    else:
        statuses = {g(g(s, 'dispatch'), 'status') for s in scenarios}
        if g(run, 'issues'):
            st['execute'] = ('failed', '输入未就绪')
        elif statuses & {'error','rejected','invalid'}:
            st['execute'] = ('failed','存在失败/拒绝/校验不通过，见真实状态')
        elif 'no_solution_limit' in statuses:
            st['execute'] = ('uncertain', '达到限制 · 存在未找到解')
        else:
            st['execute'] = ('done', f'{len(g(run, "tool_calls", []) or [])} 次工具调用')
        valid = sum(1 for s in scenarios if g(g(s, 'validation'), 'valid'))
        st['verify'] = ('done', f'{valid}/{len(scenarios)} 方案通过') if valid else \
            ('uncertain', '没有通过校验的可行方案') if scenarios else ('pending', '')
        ok = g(reply, 'explanation_verified')
        st['explain'] = ('done', '数值引用已核对') if ok is True else ('uncertain', '数值引用未核对通过')
    return tuple(StageVM(k, l, *st[k]) for k, l in STAGES)


def build_conversation_vm(reply: Any, run: Any = None) -> ConversationVM:
    if reply is None:
        return ConversationVM(True, (), derive_stages(None))
    pending, contract, rrun = g(reply, 'pending'), g(reply, 'contract'), g(reply, 'run')
    status = g(reply, 'status')
    status_chip = Badge('状态 ' + REPLY_STATUS.get(status, str(status)), 'muted')
    msgs: list[MessageVM] = []
    if pending is not None:
        msgs.append(MessageVM('USER_MESSAGE', 'user', KIND_LABEL['USER_MESSAGE'], str(g(pending, 'original_request', ''))))
        for a in (g(pending, 'answers', []) or []):
            msgs.append(MessageVM('USER_MESSAGE', 'user', '补充回答', str(g(a, 'text', ''))))
    missing = g(pending, 'missing_fields') or []
    pstat = g(pending, 'status')
    text = str(g(reply, 'text', '') or '')
    if pstat == 'awaiting_answer' and missing:
        msgs.append(MessageVM('AGENT_CLARIFICATION', 'assistant', KIND_LABEL['AGENT_CLARIFICATION'], text,
                              (Badge(f'待补 {len(missing)} 项', 'warn'), status_chip),
                              tuple(str(g(m, 'question', '')) for m in missing), tone='warn'))
    elif g(reply, 'study') is not None:
        msgs.append(MessageVM('TOOL_RESULT', 'tool', KIND_LABEL['TOOL_RESULT'],
                              str(g(g(reply, 'study'), 'note', '') or text),
                              (Badge('成本—排放扫描', 'info'), status_chip), tone='good'))
    elif rrun is not None:
        rm = recommended_metrics(rrun)
        scenarios = list(g(rrun, 'scenarios', []) or [])
        if g(rrun, 'issues'):
            msgs.append(MessageVM('ERROR_MESSAGE', 'tool', KIND_LABEL['ERROR_MESSAGE'],
                                  '输入未就绪，未形成可用规划结论。',
                                  items=tuple(str(g(i, 'message', i)) for i in g(rrun, 'issues')), tone='bad'))
        elif rm:
            msgs.append(MessageVM('TOOL_RESULT', 'tool', KIND_LABEL['TOOL_RESULT'],
                                  f'推荐方案 {rm["candidate_id"]} · {rm["name"]}',
                                  (Badge(f'run {str(g(rrun, "run_id"))[:8]}', 'info'),),
                                  metrics=_result_metrics(rm), tone='good'))
        else:
            unknown = any(g(g(s, 'dispatch'), 'status') == 'no_solution_limit' for s in scenarios)
            msgs.append(MessageVM('TOOL_UNCERTAIN' if unknown else 'TOOL_RESULT', 'tool',
                                  KIND_LABEL['TOOL_UNCERTAIN' if unknown else 'TOOL_RESULT'],
                                  '没有通过全部约束的推荐方案。未找到解不等于已证明不可行，请查看各方案求解状态。',
                                  tone='warn'))
        verified = g(reply, 'explanation_verified')
        msgs.append(MessageVM('AGENT_EXPLANATION', 'assistant', KIND_LABEL['AGENT_EXPLANATION'], text,
                              (Badge('数值引用已核对' if verified is True else '数值引用未核对通过', 'good' if verified is True else 'warn'),
                               status_chip)))
    elif pstat == 'cancelled':
        msgs.append(MessageVM('AGENT_EXPLANATION', 'assistant', '请求已取消（保留历史，不再求解）', text, (status_chip,)))
    else:
        if g(contract, 'ready', bool(g(contract,'edits')) and not g(contract,'missing')) is True:
            msgs.append(MessageVM('AGENT_CONFIRMATION', 'assistant', KIND_LABEL['AGENT_CONFIRMATION'], text,
                                  (status_chip,), tone='info'))
            msgs.append(MessageVM('TOOL_PENDING', 'tool', KIND_LABEL['TOOL_PENDING'],
                                  '确定性求解将在你显式点击下方按钮后执行；刷新页面不会求解，也不会调用模型。', tone='info'))
        else:
            msgs.append(MessageVM('AGENT_EXPLANATION', 'assistant', KIND_LABEL['AGENT_EXPLANATION'], text, (status_chip,)))
    return ConversationVM(False, tuple(msgs), derive_stages(reply))


@dataclass(frozen=True)
class TaskSummaryVM:
    request_id: str
    base_run_id: str
    input_version: str
    dialog_status: str
    conditions: tuple[tuple[str, str], ...]
    preserves: tuple[str, ...]
    changes: tuple[str, ...]
    preserves_text: str
    result_run_id: str
    result_version: str
    basis_text: str
    before_after: tuple[tuple[str, str, str, str], ...]
    before_after_note: str
    verify_text: str
    verify_tone: str
    tool_rows: tuple[tuple[str, str, str, str], ...]


def before_after_rows(new: Any, old: Any) -> tuple[tuple[str, str, str, str], ...]:
    a, b = recommended_metrics(old), recommended_metrics(new)
    if not a or not b:
        return ()
    from ..comparability import compare_basis
    from ..schemas import TaskRequest
    try:
        comparable = compare_basis(TaskRequest.model_validate(g(old,'task')),TaskRequest.model_validate(g(new,'task'))).directly_comparable
    except (ValueError,TypeError,AttributeError):
        comparable = None
    items = (('初始投资（元）', 'investment'), ('年度购能费（元）' if b['full_year'] else '评估期运行费（元）', 'operating'),
             ('NPV 成本（元）', 'npv'), (f'运行排放（kg{b["species"]}）', 'emissions'))
    rows = []
    for label, key in items:
        x, y = a[key], b[key]
        delta = (('' if comparable else '敏感性差值 ') + f'{y-x:+,.2f}') if comparable is not None and finite(x) and finite(y) else MISSING
        rows.append((label, num(x), num(y), delta))
    return tuple(rows)


def build_task_summary(reply: Any, annual: Any, old_run: Any = None) -> TaskSummaryVM | None:
    if reply is None and annual is None:
        return None
    pending, contract, run = g(reply, 'pending'), g(reply, 'contract'), g(reply, 'run') or annual
    cond = g(pending, 'confirmed_conditions') or {}
    if not cond and annual is not None:
        task=g(annual,'task'); data=g(task,'data'); times=g(data,'timestamps') or []
        cond={'budget_yuan':g(g(task,'constraints'),'budget_yuan'),'period_start':str(times[0]) if times else None,'period_end':str(times[-1]) if times else None}
    conditions = ()
    if isinstance(cond, Mapping):
        conditions = tuple(x for x in (
            ('已确认预算', num(cond.get('budget_yuan'), 2, '元') if cond.get('budget_yuan') is not None else None),
            ('评估时段', f'{cond.get("period_start")} 至 {cond.get("period_end")}' if cond.get('period_start') else None)) if x[1])
    changes, preserves_text = _brief(contract) if contract is not None else ([], '')
    basis = ''
    if run is not None and g(run, 'previous_run_id'):
        try:
            from ..comparability import basis_summary,compare_basis
            from ..schemas import TaskRequest
            basis = compare_basis(TaskRequest.model_validate(g(old_run,'task')),TaskRequest.model_validate(g(run,'task'))).summary if old_run is not None else str(basis_summary(run))
        except Exception:
            basis = ''
    scenarios = list(g(run, 'scenarios', []) or [])
    valid = sum(1 for s in scenarios if g(g(s, 'validation'), 'valid'))
    verify_text, verify_tone = ('尚无结果', 'muted') if run is None else \
        (f'{valid}/{len(scenarios)} 方案通过独立校验', 'good' if valid else 'warn')
    calls = tuple((str(g(c, 'tool_name')), str(g(c, 'status')), num(g(c, 'seconds'), 3), str(g(c, 'summary', '')))
                  for c in (g(run, 'tool_calls', []) or []))
    ba = before_after_rows(run, old_run) if run is not None and old_run is not None else ()
    return TaskSummaryVM(
        request_id=str(g(reply, 'request_id', MISSING)), base_run_id=str(g(pending, 'base_run_id', g(annual, 'run_id', MISSING))),
        input_version=f'v{g(pending, "input_version", g(annual, "input_version", "?"))}',
        dialog_status=DIALOG_STATUS.get(g(pending, 'status'), REPLY_STATUS.get(g(reply, 'status'), MISSING)), conditions=conditions,
        preserves=tuple(str(x) for x in (g(contract, 'preserves', []) or [])), changes=tuple(changes),
        preserves_text=preserves_text, result_run_id=str(g(run, 'run_id', '') or ''),
        result_version=f'v{g(run,"input_version","?")}', basis_text=basis,
        before_after=ba,
        before_after_note=('差值为当前减基准；口径变化时标为敏感性差值，不能解释为同口径生命周期成本节省。' if ba else
                           ('基准快照缺失，或基准/当前无有效推荐指标；未列新旧数值，口径说明见上。' if run is not None and g(run, 'previous_run_id') else '')),
        verify_text=verify_text, verify_tone=verify_tone, tool_rows=calls)


# ─────────────────── intents ───────────────────
@dataclass(frozen=True)
class IntentVM:
    key: str
    title: str
    tagline: str
    example: str
    shows: tuple[str, ...]
    dest_page: str | None
    dest_hint: str
    available: bool
    reason: str


_INTENTS = (
    ('plan_modify', '规划修改', '用自然语言修改预算、负荷、排放或设备条件', '预算减少15%，供热不变。',
     ('修改项与保留项', '必要澄清', '确认后计算', '新旧结果对照'), None,
     '在下方「可持续对话规划助手」输入并确认；模型调用只在显式点击带“可能计费”的按钮时发生。'),
    ('counterfactual', '反事实修复', '不可行时，搜索单个约束要放宽到哪里才可行', '预算不够，怎么调整才能有可行方案？',
     ('当前不可行状态', '允许修改与必须保持的字段', '三条独立修复路径', '显式采用按钮'), '优化结果',
     '到「优化结果」页展开「反事实约束修复」，勾选允许调整项、搜索范围并显式执行。'),
    ('regret', '情景稳健决策', '固定装机，比较各方案在不同情景下的后悔值', '如果电价上涨，哪个方案更值得选？',
     ('固定容量候选', '情景假设与授权', '成本与后悔热图', '稳健推荐解释'), '优化结果',
     '到「优化结果」页展开「多情景稳健决策」，选择配置与情景并确认授权后执行。'))


def intent_options(ctx: Mapping) -> tuple[IntentVM, ...]:
    gates = {'plan_modify': (bool(ctx.get('has_annual')), '需要先在「优化结果」加载并评估全年规划任务'),
             'counterfactual': (bool(ctx.get('has_run') and ctx.get('cf_enabled')), '需要一个已评估的运行，且反事实功能未被关闭'),
             'regret': (bool(ctx.get('has_witness') and ctx.get('regret_enabled')),
                        '需要一个含经校验可行见证的运行，且多情景功能未被关闭；不可行时先用反事实修复')}
    return tuple(IntentVM(k, t, tag, ex, shows, page, hint, *gates[k]) for k, t, tag, ex, shows, page, hint in _INTENTS)


def suggest_intent(text: str) -> tuple[str | None, str]:
    """HINT ONLY. Never routes, authorizes or executes anything."""
    t = (text or '').strip()
    if not t:
        return None, ''
    rules = (('counterfactual', ('不够', '怎么调整', '至少还差', '放宽', '可行方案', '不可行', '修复')),
             ('regret', ('电价', '燃气价', '哪个方案', '稳健', '后悔', '更值得', '光伏下降')),
             ('plan_modify', ('减少', '增加', '降低', '提高', '预算', '负荷', '供热不变')))
    for key, words in rules:
        hit = next((w for w in words if w in t), None)
        if hit:
            return key, f'文字中出现“{hit}”'
    return None, ''


def router_available() -> bool:
    """False until Codex ships the unified router (see integration prompt)."""
    return False
