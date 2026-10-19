"""Explicit reproducible recourse matrices. No network, no paid model calls."""
import argparse
import json
from pathlib import Path

from energy_agent.agent import EnergyAgent, ToolRegistry
from energy_agent.counterfactual import digest
from energy_agent.data import make_demo_task
from energy_agent.regret import RegretRequest, available_candidates, default_scenarios
from energy_agent.schemas import SolverOptions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--annual', action='store_true', help='显式执行8760小时混合电热2×3矩阵')
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('请使用新的空目录，保留旧证据')
    args.output.mkdir(parents=True, exist_ok=True)
    cases = [('synthetic_24h', make_demo_task(hours=24), 3, default_scenarios(), 5, 60)]
    if args.annual:
        from energy_agent.annual import build_annual_case
        task = build_annual_case(heat=True, bundle_dir=Path('examples/shanghai_2017'),
                                 retain_flagged_jumps=True, budget=10000000)
        # Existing BASE/PV fixed candidates; original capacity boundaries retained.
        task.planning_mode = 'candidates'
        scenarios = default_scenarios()
        cases.append(('mixed_heat_8760h', task, 2, [scenarios[i] for i in (0, 1, 3)], 20, 180))
    summaries = []
    for name, task, count, scenarios, single, total in cases:
        out = args.output / name
        out.mkdir()
        (out / 'task.json').write_text(task.model_dump_json(indent=2), encoding='utf-8')
        baseline = EnergyAgent(out / 'baseline', SolverOptions(time_limit_seconds=single)).run(task)
        request = RegretRequest(request_id=name, baseline=baseline, base_run_id=baseline.run_id,
            input_version=baseline.input_version, input_sha256=digest(baseline.task),
            candidates=available_candidates(baseline)[:count], scenarios=scenarios,
            cost_basis='npv' if task.economics else 'period_energy', confirm_large_annual=bool(task.economics),
            single_solve_seconds=single, total_seconds=total, max_solver_calls=count*len(scenarios),
            output_dir=str(out / 'matrix'))
        (out / 'request.json').write_text(request.model_dump_json(indent=2), encoding='utf-8')
        result = ToolRegistry().call('evaluate_minimax_regret', request)
        summary = dict(case=name, intervals=len(task.data.timestamps), step_hours=task.data.step_hours,
            base_run_id=baseline.run_id, input_sha256=digest(baseline.task),
            solver_calls=result.solver_calls, elapsed_seconds=result.elapsed_seconds,
            analysis=result.analysis.model_dump(mode='json'), files=result.files,
            cells=[c.model_dump(mode='json', exclude={'validation'}) | {
                'independently_valid':bool(c.validation and c.validation.valid),
                'checks':len(c.validation.checks) if c.validation else 0} for c in result.cells])
        summaries.append(summary)
        print(name, result.analysis.status, result.solver_calls, result.analysis.recommended_ids,
              f'{result.elapsed_seconds:.3f}s', flush=True)
    (args.output / 'summary.json').write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 固定配置多情景实际重算',
        '24小时为合成演示；8760小时（如有）为上海Q局部实测＋NASA估算PV＋仿真供热与人为经济参数的混合研究情景。情景倍数是研究假设，不是预测。']
    for item in summaries:
        a = item['analysis']
        lines += [f'## {item["case"]}', f'基准run_id={item["base_run_id"]}；状态={a["status"]}；'
            f'{item["solver_calls"]}次；{item["elapsed_seconds"]:.3f}秒；推荐={a["recommended_ids"]}。',
            '成本矩阵（元）：'+json.dumps(a['cost_matrix'],ensure_ascii=False),
            '后悔矩阵（元）：'+json.dumps(a['regret_matrix'],ensure_ascii=False),
            '最坏后悔（元）：'+json.dumps(a['worst_regret_yuan'],ensure_ascii=False)]
    lines += ['推荐与基准相同时如实保留；短期仅购能费，投资另列；全年NPV沿用20年重复代表年假设。未自动采用任何配置。']
    (args.output / 'summary.md').write_text('\n\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
