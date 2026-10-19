"""Explicit registration of the two bounded decision tools, also for UI reruns.

A fresh UI registry rebinds these known schemas/functions rather than relying on
an older imported registry instance. This never accepts dynamic tool names/code.
"""


def register_decision_tools(registry):
    from .agent import Tool
    from .counterfactual import CounterfactualRequest, CounterfactualResult, search_counterfactual_repairs
    from .regret import RegretRequest, RegretResult, evaluate_minimax_regret
    registry._tools.update({
        'search_counterfactual_repairs': Tool(CounterfactualRequest, CounterfactualResult, search_counterfactual_repairs),
        'evaluate_minimax_regret': Tool(RegretRequest, RegretResult, evaluate_minimax_regret),
    })
    return registry


def decision_registry():
    # Resolve the class at the explicit action, not when a Streamlit page was
    # first imported. Re-register only this static allowlist (idempotent).
    from .agent import ToolRegistry
    return register_decision_tools(ToolRegistry())
