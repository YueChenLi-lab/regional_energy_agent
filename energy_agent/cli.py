"""CLI for the same agent used by the Chinese demonstration UI."""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from .agent import EnergyAgent, revise_task
from .data import make_demo_task
from .schemas import RunResult, RunState, SolverOptions, TaskPatch


def main(argv=None) -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    parser = argparse.ArgumentParser(description="区域综合能源低碳规划评估 Agent v0.2")
    commands = parser.add_subparsers(dest="command", required=True)
    from .import_cli import register_import_commands
    register_import_commands(commands)
    demo = commands.add_parser("demo", help="合成演示数据，无需模型密钥")
    demo.add_argument("--seed", type=int, default=42)
    demo.add_argument("--hours", type=int, default=168)
    demo.add_argument("--task-out", type=Path, help="另存可编辑的完整任务 JSON")
    run = commands.add_parser("run", help="评估统一格式的任务 JSON")
    run.add_argument("--task", type=Path, required=True)
    revise = commands.add_parser("revise", help="修改已保存运行，增加版本并重新计算")
    revise.add_argument("--run", type=Path, required=True)
    for command in (demo, run, revise):
        command.add_argument("--output", type=Path, default=Path("outputs"))
        command.add_argument("--time-limit", type=float, default=30.0, help="每个候选的求解时限（秒）")
    for command in (demo, revise):
        command.add_argument("--budget", type=float)
        command.add_argument("--emission-limit", type=float)
        command.add_argument("--clear-emission-limit", action="store_true")
        command.add_argument("--demand-scale", type=float)
        command.add_argument("--grid-limit", type=float)
        command.add_argument("--pv-limit", type=float)
    args = parser.parse_args(argv)
    if args.command in ("data-fetch", "data-import", "data-replay"):
        from .import_cli import handle_import_command
        return handle_import_command(args)
    previous = None
    try:
        if args.command == "run":
            task = json.loads(args.task.read_text(encoding="utf-8"))
        else:
            if args.command == "demo":
                task = make_demo_task(seed=args.seed, hours=args.hours)
            else:
                previous = RunResult.model_validate_json(args.run.read_text(encoding="utf-8"))
                task = previous.task
            patch = TaskPatch(budget_yuan=args.budget, emission_limit_kg=args.emission_limit,
                clear_emission_limit=args.clear_emission_limit, demand_scale=args.demand_scale,
                grid_limit_kw=args.grid_limit, pv_limit_kw=args.pv_limit)
            if args.command == "revise" or patch.model_dump(exclude_none=True, exclude_defaults=True):
                task = revise_task(task, patch, parent_run_id=previous.run_id if previous else None)
            if args.command == "demo" and args.task_out:
                args.task_out.parent.mkdir(parents=True, exist_ok=True)
                args.task_out.write_text(task.model_dump_json(indent=2), encoding="utf-8")
        result = EnergyAgent(args.output, options=SolverOptions(time_limit_seconds=args.time_limit)).run(task, previous=previous)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"输入或文件错误：{exc}\n")
    print(f"run_id={result.run_id} 输入版本={result.input_version} 状态={result.state}")
    if result.task.demo:
        print("合成演示数据；价格、排放因子和设备单价均为演示假设。")
    elif result.task.case_context:
        from .data import case_label
        print(case_label(result.task), result.task.case_context.boundary)
    if result.comparison:
        print(result.comparison.explanation)
    for scenario in result.scenarios:
        m = scenario.validation.metrics
        suffix = f"运行费={m.operating_cost_yuan:.2f}元 排放={m.emissions_kg:.2f}kg{result.task.emission_species}" if m else "；".join(scenario.dispatch.reasons)
        print(f"{scenario.candidate.candidate_id}: {scenario.dispatch.status} 投资={scenario.investment_yuan:.2f}元 {suffix}")
    for issue in result.issues:
        print(f"待处理 {issue.field}: {issue.message}")
    print(json.dumps(result.files, ensure_ascii=False, indent=2))
    return 0 if result.state == RunState.COMPLETED else (2 if result.state == RunState.NEEDS_INPUT else 1)


if __name__ == "__main__":
    raise SystemExit(main())
