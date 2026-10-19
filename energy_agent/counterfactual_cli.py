"""Explicit offline commands; no model configuration or network required."""
from pathlib import Path

from .counterfactual import (CounterfactualRequest, CounterfactualResult,
                            adopt_counterfactual_path, search_counterfactual_repairs)
from .schemas import RunResult


def register_counterfactual_commands(commands):
    command = commands.add_parser('counterfactual', help='显式、有限预算的反事实约束修复；不自动采用')
    command.add_argument('--request', type=Path, required=True, help='CounterfactualRequest JSON，含固定基准与授权范围')
    command.add_argument('--output', type=Path, help='覆盖结果根目录，不覆盖旧请求或证据')
    adopt = commands.add_parser('counterfactual-adopt', help='显式采用已计算且独立校验的修复路径')
    adopt.add_argument('--result', type=Path, required=True)
    adopt.add_argument('--baseline', type=Path, required=True)
    adopt.add_argument('--path-id', required=True)
    adopt.add_argument('--adoption-id', required=True)
    adopt.add_argument('--confirm', action='store_true')
    adopt.add_argument('--output', type=Path, required=True, help='保存采用版本到新JSON文件，不覆盖基准')


def handle_counterfactual_command(args):
    if args.command == 'counterfactual':
        request = CounterfactualRequest.model_validate_json(args.request.read_bytes())
        if args.output is not None:
            request.output_dir = str(args.output)
        result = search_counterfactual_repairs(request)
        print(result.model_dump_json(indent=2))
        return 0 if any(p.suggested_value is not None for p in result.paths) else 2
    result = CounterfactualResult.model_validate_json(args.result.read_bytes())
    baseline = RunResult.model_validate_json(args.baseline.read_bytes())
    run = adopt_counterfactual_path(result, baseline, args.path_id, confirmed=args.confirm, adoption_id=args.adoption_id)
    if args.output.exists():
        if RunResult.model_validate_json(args.output.read_bytes()) != run:
            raise ValueError('输出文件已存在且内容不同，拒绝覆盖')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(run.model_dump_json(indent=2), encoding='utf-8')
    print(f'已显式采用 {run.run_id}，版本{run.input_version}；原基准未改写。')
    return 0
