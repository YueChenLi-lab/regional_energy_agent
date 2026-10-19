"""Small, real, offline decision demos, isolated from confirmed user projects."""
from pathlib import Path

from .agent import EnergyAgent
from .counterfactual import CounterfactualRequest, RepairRange, _atomic_json, data_fingerprint, digest
from .counterfactual_cases import make_repair_case
from .data import make_demo_task
from .decision_tools import decision_registry
from .regret import RegretRequest, available_candidates, default_scenarios
from .schemas import RunResult, SolverOptions
from .storage import file_lock

KINDS = ('repair', 'regret')


def demo_task(kind):
    if kind not in KINDS:
        raise ValueError('仅支持反事实修复与多情景合成演示')
    task = make_repair_case(24) if kind == 'repair' else make_demo_task(seed=42, hours=24)
    if kind == 'regret':
        task.project_name = '多情景决策 · 24小时合成演示 · 非真实工程'
        task.candidates = task.candidates[:3]
    return task


def run_decision_demo(kind, output_dir, request_id):
    """Explicitly run; repeated IDs restore the baseline and existing receipts.

    Output is a separate demo namespace. No confirmed session/project is read or
    written. Baseline solves: at most 3 × 3s; then bounded tool-specific budgets.
    """
    task = demo_task(kind)
    if not isinstance(request_id, str) or not request_id or len(request_id) > 100:
        raise ValueError('演示请求ID需为1至100字符')
    root = Path(output_dir) / kind / digest(request_id)
    with file_lock(root / 'demo.lock'):
        saved = root / 'baseline.json'
        if saved.is_file():
            baseline = RunResult.model_validate_json(saved.read_text(encoding='utf-8'))
            if digest(baseline.task) != digest(task):
                raise ValueError('演示输入已变化，请显式重新加载演示，生成新请求ID')
        else:
            baseline = EnergyAgent(root / 'baseline', SolverOptions(time_limit_seconds=3)).run(task)
            _atomic_json(saved, baseline)
        if kind == 'repair':
            request = CounterfactualRequest(request_id=request_id, baseline=baseline,
                base_run_id=baseline.run_id, input_version=baseline.input_version,
                data_fingerprint=data_fingerprint(task), allowed_fields=['budget_yuan', 'emission_limit_kg', 'grid_limit_kw'],
                ranges={
                    'budget_yuan': RepairRange(lower=60000, upper=600000, precision=1000, unit='元'),
                    'emission_limit_kg': RepairRange(lower=230, upper=300, precision=.05, unit='kgCO2e'),
                    'grid_limit_kw': RepairRange(lower=12, upper=25, precision=.01, unit='kW')},
                original_request='显式授权合成演示三条单参数路径，保持电热负荷、时段和供能服务；不采用',
                single_solve_seconds=3, max_solver_calls=128, total_seconds=60, output_dir=str(root / 'search'))
            name = 'search_counterfactual_repairs'
        else:
            request = RegretRequest(request_id=request_id, baseline=baseline,
                base_run_id=baseline.run_id, input_version=baseline.input_version,
                input_sha256=digest(task), candidates=available_candidates(baseline), scenarios=default_scenarios(),
                cost_basis='period_energy', single_solve_seconds=3, max_solver_calls=12,
                total_seconds=45, output_dir=str(root / 'matrix'))
            name = 'evaluate_minimax_regret'
        _atomic_json(root / 'request.json', request)
        result = decision_registry().call(name, request)
        return baseline, result
