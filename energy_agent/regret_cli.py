"""Explicit offline minimax-regret invocation; no model or implicit adoption."""
from pathlib import Path

from .agent import ToolRegistry
from .regret import RegretRequest


def register_regret_commands(commands):
    command = commands.add_parser('regret', help='显式重算固定配置×授权情景；不采用结果')
    command.add_argument('--request', type=Path, required=True)
    command.add_argument('--output', type=Path, help='覆盖输出根目录；同ID内容变化仍会拒绝')


def handle_regret_command(args):
    request = RegretRequest.model_validate_json(args.request.read_bytes())
    if args.output is not None:
        request.output_dir = str(args.output)
    result = ToolRegistry().call('evaluate_minimax_regret', request)
    print(result.explanation)
    print(result.files)
    return 0 if result.analysis.status in ('certified', 'approximate') else 2
