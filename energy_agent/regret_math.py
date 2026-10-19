"""Finite-set regret arithmetic, independent of energy models and UI."""
from typing import Literal

from pydantic import Field, model_validator

from .schemas import Model


class CostObservation(Model):
    candidate_id: str
    scenario_id: str
    feasibility: Literal['feasible', 'infeasible', 'uncertain', 'error', 'rejected', 'not_run']
    solver_status: str | None = None
    cost_yuan: float | None = None
    cost_is_optimal: bool = False

    @model_validator(mode='after')
    def consistent(self):
        valid = self.feasibility == 'feasible'
        if valid != (self.cost_yuan is not None):
            raise ValueError('仅经独立校验可行的单元允许提供成本；其余必须为null')
        if valid and self.solver_status not in ('optimal','feasible_limit'):
            raise ValueError('可行成本与原始求解状态/最优性不一致')
        if self.cost_is_optimal and (not valid or self.solver_status != 'optimal'):
            raise ValueError('成本最优性必须有optimal可行解')
        return self


class RegretAnalysis(Model):
    status: Literal['certified', 'approximate', 'partial', 'no_recommendation']
    cost_matrix: dict[str, dict[str, float | None]]
    regret_matrix: dict[str, dict[str, float | None]]
    scenario_best_costs: dict[str, float | None]
    scenario_best_ids: dict[str, list[str]]
    scenario_baselines_complete: dict[str, bool]
    full_scenario_feasible_ids: list[str]
    worst_regret_yuan: dict[str, float | None]
    worst_scenario_ids: dict[str, list[str]]
    recommended_ids: list[str]
    provisional_ids: list[str]
    baseline_cheapest_ids: list[str]
    minimax_cost_ids: list[str]
    numerical_tolerance_yuan: float
    note: str


def regret_difference(cost: float, best: float, tolerance: float) -> float:
    delta = cost-best
    if delta < -tolerance:
        raise ValueError('出现超出容差的负后悔，基准或成本不一致，停止认证')
    return max(0., delta)


def analyze_regret(observations: list[CostObservation], candidates: list[str], scenarios: list[str],
                   baseline_scenario_id: str, tolerance: float = 1e-4) -> RegretAnalysis:
    """All cells required, including explicit not_run entries. No probabilities."""
    if not candidates or not scenarios or len(set(candidates)) != len(candidates) or len(set(scenarios)) != len(scenarios):
        raise ValueError('候选与情景必须非空且标识唯一')
    if baseline_scenario_id not in scenarios or not 0 < tolerance <= .01:
        raise ValueError('基准情景或金额容差不合法')
    entries = [CostObservation.model_validate(o.model_dump(include=set(CostObservation.model_fields)) if isinstance(o,Model) else o) for o in observations]
    by_pair = {(o.candidate_id,o.scenario_id):o for o in entries}
    expected = {(k,s) for k in candidates for s in scenarios}
    if len(by_pair)!=len(entries) or set(by_pair)!=expected:
        raise ValueError('必须提供无重复的完整配置—情景矩阵，未执行单元应显式标not_run')
    costs = {k:{s:by_pair[k,s].cost_yuan for s in scenarios} for k in candidates}
    best, best_ids, complete = {}, {}, {}
    for s in scenarios:
        available = [o for (k,sid),o in by_pair.items() if sid==s and o.feasibility=='feasible']
        best[s] = min((o.cost_yuan for o in available),default=None)
        best_ids[s] = sorted(o.candidate_id for o in available if abs(o.cost_yuan-best[s])<=tolerance)
        complete[s] = all(by_pair[k,s].feasibility=='infeasible' or by_pair[k,s].cost_is_optimal for k in candidates)
    regrets = {k:{s:regret_difference(costs[k][s],best[s],tolerance)
        if costs[k][s] is not None and best[s] is not None else None for s in scenarios} for k in candidates}
    eligible = [k for k in candidates if all(by_pair[k,s].feasibility=='feasible' for s in scenarios)]
    worst = {k:max(regrets[k].values()) if k in eligible else None for k in candidates}
    worst_scenarios = {k:[s for s in scenarios if k in eligible and abs(regrets[k][s]-worst[k])<=tolerance] for k in candidates}
    def ties(values):
        return sorted(k for k,v in values.items() if abs(v-min(values.values()))<=tolerance) if values else []
    winners = ties({k:worst[k] for k in eligible})
    minimax = ties({k:max(costs[k].values()) for k in eligible})
    unknown = any(o.feasibility not in ('feasible','infeasible') for o in entries)
    if unknown:
        status = 'partial'
        note = '存在未知、失败、拒绝或未执行单元；情景基准及后悔仅按已得可行成本计算，不能认证原全部候选集中的最小后悔。'
    elif not winners or any(v is None for v in best.values()):
        status = 'no_recommendation'
        note = '没有全情景可行配置，或某情景无有效成本；不输出完整推荐，不用罚分代替不可行。'
    elif all(complete.values()):
        status = 'certified'
        note = '当前有限候选×有限情景内，全部单元已证明最优且校验通过或已确认不可行；在所设数值容差内认证最小最大后悔。'
    else:
        status = 'approximate'
        note = '含feasible_limit、非零或未提供gap的成本上界，当前后悔和排序为近似结果；存在可行运行不等于成本已证明最优。'
    return RegretAnalysis(status=status,cost_matrix=costs,regret_matrix=regrets,scenario_best_costs=best,
        scenario_best_ids=best_ids,scenario_baselines_complete=complete,full_scenario_feasible_ids=eligible,
        worst_regret_yuan=worst,worst_scenario_ids=worst_scenarios,
        recommended_ids=winners if status in ('certified','approximate') else [],provisional_ids=winners if status=='partial' else [],
        baseline_cheapest_ids=best_ids[baseline_scenario_id],minimax_cost_ids=minimax,
        numerical_tolerance_yuan=tolerance,note=note+' 并列项按ID稳定展示，不代表严格优劣；未分配情景概率。')
