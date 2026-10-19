"""One deterministic orchestrator; model interpretation cannot replace tools."""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from .data import validate_inputs
from .evaluation import compare_scenarios, validate_solution
from .optimization import solve_dispatch
from .capacity import CapacitySolveRequest, CapacitySolution, solve_capacity
from .economics import evaluate_economics
from .planning import build_candidates, investment_yuan
from .reporting import export_run, generate_report
from .schemas import (
    ConstraintCheck, CandidateList, Comparison, ComparisonRequest, DispatchResult, InputValidation,
    Issue, ProjectTask, ReportRequest, ReportText, RunResult, RunState, ScenarioResult,
    SolutionValidation, SolveRequest, SolverOptions, Source, TaskPatch, TaskRequest,
    ToolCall, ValidationRequest,
)


@dataclass(frozen=True)
class Tool:
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    function: Callable


class ToolRegistry:
    """Closed allowlist. Every call validates both sides of its contract."""

    def __init__(self):
        self._tools = {
            "validate_inputs": Tool(TaskRequest, InputValidation, validate_inputs),
            "build_candidates": Tool(ProjectTask, CandidateList, build_candidates),
            "solve_dispatch": Tool(SolveRequest, DispatchResult, solve_dispatch),
            "validate_solution": Tool(ValidationRequest, SolutionValidation, validate_solution),
            "compare_scenarios": Tool(ComparisonRequest, Comparison, compare_scenarios),
            "generate_report": Tool(ReportRequest, ReportText, generate_report),
            "solve_capacity": Tool(CapacitySolveRequest, CapacitySolution, solve_capacity),
        }
        # Imported here to keep the optional repair module free of an import
        # cycle. Its contract cannot authorize arbitrary task edits or tools.
        from .counterfactual import CounterfactualRequest, CounterfactualResult, search_counterfactual_repairs
        self._tools["search_counterfactual_repairs"] = Tool(CounterfactualRequest, CounterfactualResult, search_counterfactual_repairs)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def call(self, name: str, payload):
        if name not in self._tools:
            raise ValueError(f"未注册的工具：{name}")
        tool = self._tools[name]
        raw = payload.model_dump() if isinstance(payload, BaseModel) else payload
        value = tool.input_schema.model_validate(raw)
        output = tool.function(value)
        raw_output = output.model_dump() if isinstance(output, BaseModel) else output
        return tool.output_schema.model_validate(raw_output)


def revise_task(task: TaskRequest, patch: TaskPatch, parent_run_id: str | None = None, *, new_version: int | None = None) -> TaskRequest:
    """Create a new input version, retaining prior provenance and recomputing later."""
    patch = TaskPatch.model_validate(patch)
    if patch.preserve_heat and task.assessment_mode == "electric_only":
        raise ValueError("电侧任务未建模供热，请先澄清供热边界")
    if patch.budget_multiplier is not None:
        if task.constraints is None or task.constraints.budget_yuan is None:
            raise ValueError("相对修改需要已确认预算")
        patch = patch.model_copy(update={"budget_yuan": task.constraints.budget_yuan*patch.budget_multiplier, "budget_multiplier": None})
    payload = task.model_dump(mode="json")
    if new_version is not None and new_version <= task.version:
        raise ValueError("新输入版本必须高于基准版本")
    payload["version"] = new_version or task.version + 1
    payload["parent_run_id"] = parent_run_id
    source_id = f"revision-v{payload['version']}"
    changes = patch.model_dump(exclude_none=True, exclude_defaults=True)
    if patch.clear_emission_limit and patch.emission_limit_kg is not None:
        raise ValueError("不能同时设置与清除排放上限")
    constraint_fields = ("budget_yuan", "emission_limit_kg", "grid_limit_kw", "pv_limit_kw")
    if any(getattr(patch, name) is not None for name in constraint_fields) or patch.clear_emission_limit:
        if payload["constraints"] is None:
            raise ValueError("请先补全项目约束，再修改参数")
        for name in constraint_fields:
            if getattr(patch, name) is not None:
                payload["constraints"][name] = getattr(patch, name)
        if patch.clear_emission_limit:
            payload["constraints"]["emission_limit_kg"] = None
        payload["constraints"]["source_id"] = source_id
    scales = {"electric_load_kw": patch.electric_demand_scale, "heat_load_kw_th": patch.heat_demand_scale}
    if patch.demand_scale is not None:
        scales = dict.fromkeys(scales,patch.demand_scale)
    for name, scale in scales.items():
        if scale is not None:
            if payload["data"] is None:
                raise ValueError("请先补全负荷，再修改需求规模")
            payload["data"][name] = [x * scale for x in payload["data"][name]]
            payload["data"]["source_ids"][name] = source_id
            if payload.get("case_context") and scale != 1:
                payload["case_context"]["pending"].append(f"本版本{name}按用户明确倍数{scale:g}作情景缩放，不再是该字段原始实测；原转换能量核对只适用于未缩放输入。")
    if patch.economics:
        if payload["economics"] is None:
            raise ValueError("当前任务缺少全年经济参数，不能猜测经济评价条件")
        economic_changes=patch.economics.model_dump(exclude_none=True)
        assets=economic_changes.pop("assets",{})
        payload["economics"].update(economic_changes)
        for asset, edits in assets.items():
            payload["economics"]["assets"][asset].update(edits)
        payload["economics"]["source_id"]=source_id
    if patch.unsupported_demands:
        payload["unsupported_demands"] = list(dict.fromkeys(payload["unsupported_demands"] + patch.unsupported_demands))
    payload["sources"].append(Source(
        source_id=source_id, name=f"用户场景修改 v{payload['version']}", category="synthetic" if task.demo else "user",
        time_range=task.sources[0].time_range if task.sources else "未知",
        units={"budget_yuan": "元", "emission_limit_kg": f"kg{task.emission_species}", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "demand_scale": "1", "electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "discount_rate":"1", "horizon_years":"年", "lifetime_years":"年", "fixed_om_fraction":"1/年", "additional_fixed_om_yuan_per_year":"元/年"},
        processing=[f"由输入v{task.version}派生；父运行 {parent_run_id or '未知'}", json.dumps(changes, ensure_ascii=False), "负荷缩放作用于全部已提供时间区间；无缺失填充"],
        conditions="用户设定的场景；原始来源保留；合成演示属性保持" if task.demo else "用户指定的情景假设，不代表实测",
    ).model_dump(mode="json"))
    return TaskRequest.model_validate(payload)


def compare_runs(previous: RunResult, current: RunResult) -> dict:
    from .comparability import compare_basis
    basis=compare_basis(previous.task,current.task)
    before = {s.candidate.candidate_id: s for s in previous.scenarios}
    differences = []
    for scenario in current.scenarios:
        old = before.get(scenario.candidate.candidate_id)
        item = {"candidate_id": scenario.candidate.candidate_id, "previous_status": old.dispatch.status if old else None,
                "current_status": scenario.dispatch.status, "previous_valid": old.validation.valid if old else None,
                "current_valid": scenario.validation.valid}
        if old and old.validation.metrics and scenario.validation.metrics:
            for metric in ("investment_yuan", "operating_cost_yuan", "emissions_kg", "grid_kwh", "gas_kwh_lhv"):
                item[f"delta_{metric}"] = getattr(scenario.validation.metrics, metric) - getattr(old.validation.metrics, metric)
        if old:
            for key in ("pv_kw", "battery_power_kw", "battery_energy_kwh", "hp_kw_th", "boiler_kw_th"):
                item["delta_"+key] = getattr(scenario.candidate,key)-getattr(old.candidate,key)
            if old.economics and scenario.economics:
                item["delta_npv_cost_yuan"] = scenario.economics.npv_cost_yuan-old.economics.npv_cost_yuan
        differences.append(item)
    return {
        "previous_version": previous.input_version, "current_version": current.input_version,
        "previous_recommended": previous.comparison.recommended_id if previous.comparison else None,
        "current_recommended": current.comparison.recommended_id if current.comparison else None,
        "previous_constraints": previous.task.constraints.model_dump() if previous.task.constraints else None,
        "current_constraints": current.task.constraints.model_dump() if current.task.constraints else None,
        "scenarios": differences,
        "comparison_basis": basis.model_dump(mode="json"),
        "note": "差值为当前运行减前次运行；"+basis.summary,
    }


class EnergyAgent:
    def __init__(self, output_dir: str | Path = "outputs", options: SolverOptions | None = None):
        self.output_dir = Path(output_dir)
        self.options = options or SolverOptions()
        self.registry = ToolRegistry()

    def run(self, task: TaskRequest | dict, previous: RunResult | None = None) -> RunResult:
        run_id = uuid4().hex
        run_dir = self.output_dir / run_id
        (run_dir / "tools").mkdir(parents=True, exist_ok=False)
        try:
            request = TaskRequest.model_validate(task.model_dump() if isinstance(task, BaseModel) else task)
        except ValidationError as exc:
            issues = [Issue(field=".".join(map(str, e["loc"])), message=e["msg"], kind="missing" if e["type"] == "missing" else "invalid") for e in exc.errors(include_input=False)]
            # Retain independently valid identity, provenance and input sections.
            # Rejected fields are identified in issues; unknown values are not logged.
            raw = task.model_dump() if isinstance(task, BaseModel) else task
            preserved = {}
            if isinstance(raw, dict):
                for field in TaskRequest.model_fields:
                    if field in raw:
                        try:
                            checked_field = TaskRequest.model_validate({field: raw[field]})
                        except ValidationError:
                            continue
                        preserved[field] = getattr(checked_field, field)
            request = TaskRequest.model_validate(preserved)
            result = RunResult(run_id=run_id, input_version=request.version, state=RunState.NEEDS_INPUT,
                states=[RunState.RECEIVED, RunState.VALIDATING, RunState.NEEDS_INPUT], task=request, issues=issues,
                solver_options=self.options, previous_run_id=previous.run_id if previous else request.parent_run_id)
            path = run_dir / "tools" / "001_validate_inputs.json"
            path.write_text(json.dumps({"issues": [i.model_dump() for i in issues]}, ensure_ascii=False, indent=2), encoding="utf-8")
            result.tool_calls.append(ToolCall(run_id=run_id, input_version=request.version, tool_name="validate_inputs", status="error", seconds=0,
                summary="输入 schema 校验失败；保留合法输入部分，未执行任何求解", source_ids=[s.source_id for s in request.sources], result_file=str(path)))
            result.files = export_run(result, run_dir)
            return result
        result = RunResult(run_id=run_id, input_version=request.version, state=RunState.RECEIVED,
            states=[RunState.RECEIVED], task=request, solver_options=self.options,
            previous_run_id=previous.run_id if previous else request.parent_run_id)

        def state(value):
            result.state = value
            result.states.append(value)

        def invoke(name, payload):
            started = perf_counter()
            path = run_dir / "tools" / f"{len(result.tool_calls)+1:03d}_{name}.json"
            try:
                value = self.registry.call(name, payload)
            except Exception as exc:
                path.write_text(json.dumps({"error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
                result.tool_calls.append(ToolCall(run_id=run_id, input_version=request.version, tool_name=name, status="error",
                    seconds=perf_counter()-started, summary=f"{type(exc).__name__}: {exc}", source_ids=[s.source_id for s in request.sources], result_file=str(path)))
                raise
            raw = payload.model_dump_json() if isinstance(payload, BaseModel) else json.dumps(payload, sort_keys=True)
            path.write_text(json.dumps({"input_sha256": hashlib.sha256(raw.encode()).hexdigest(), "output": value.model_dump(mode="json")}, ensure_ascii=False, indent=2), encoding="utf-8")
            result.tool_calls.append(ToolCall(run_id=run_id, input_version=request.version, tool_name=name, status="success", seconds=perf_counter()-started,
                summary=f"{name} 已执行并通过输入/输出 schema 校验", source_ids=[s.source_id for s in request.sources], result_file=str(path)))
            return value

        try:
            state(RunState.VALIDATING)
            checked = invoke("validate_inputs", request)
            if not checked.ready:
                result.issues = checked.issues
                state(RunState.NEEDS_INPUT)
            else:
                ready = checked.task
                state(RunState.READY)
                state(RunState.BUILDING)
                candidates = invoke("build_candidates", ready).candidates
                if ready.planning_mode == "capacity":
                    state(RunState.SOLVING)
                    capacity = invoke("solve_capacity", CapacitySolveRequest(task=ready,options=self.options,objective=ready.capacity_objective))
                    candidates = [capacity.candidate]
                for candidate in candidates:
                    state(RunState.SOLVING)
                    dispatch = capacity.dispatch if ready.planning_mode == "capacity" else invoke("solve_dispatch", SolveRequest(task=ready, candidate=candidate, options=self.options))
                    state(RunState.CHECKING)
                    validation = invoke("validate_solution", ValidationRequest(task=ready, candidate=candidate, dispatch=dispatch))
                    economic = evaluate_economics(ready,candidate,dispatch,validation.metrics) if validation.valid else None
                    if validation.valid and ready.planning_mode == "capacity":
                        actual = economic.npv_cost_yuan if ready.capacity_objective == "npv" else validation.metrics.emissions_kg
                        expected = dispatch.model_statistics.objective_value
                        violation = abs(actual-expected) if expected is not None else 1
                        validation.checks.append(ConstraintCheck(name="planning_objective_recalculation",passed=violation<=1e-4,max_violation=violation,tolerance=1e-4,detail="独立逐年现金流NPV或物理排放与规划目标核对"))
                        validation.valid = all(check.passed for check in validation.checks)
                    result.scenarios.append(ScenarioResult(candidate=candidate, investment_yuan=investment_yuan(candidate, ready.devices), dispatch=dispatch, validation=validation, economics=economic))
                state(RunState.COMPARING)
                result.comparison = invoke("compare_scenarios", ComparisonRequest(scenarios=result.scenarios,planning_mode=ready.planning_mode,objective=ready.capacity_objective))
                if previous:
                    result.changes = compare_runs(previous, result)
                state(RunState.REPORTING)
                invoke("generate_report", ReportRequest(run=result))
                state(RunState.COMPLETED)
        except Exception as exc:
            result.issues.append(Issue(field="execution", message=f"工具执行失败：{type(exc).__name__}: {exc}"))
            state(RunState.FAILED)
        # Final serialization includes the report tool log and paths, avoiding stale trace files.
        result.files = export_run(result, run_dir)
        return result

    def run_text(self, text: str, task: TaskRequest, client, previous: RunResult | None = None, *, request_id: str | None = None) -> RunResult:
        # Every connected model path uses the same authorization and durable
        # conversation layer; there is no legacy absolute-edit bypass.
        if hasattr(client, "call_tool"):
            from .conversation import AgentSession
            from .llm import LLMError
            if previous is None or not request_id:
                raise LLMError("自然语言修改需要已确认的基准运行与稳定request_id；请先完成表单评估")
            reply = AgentSession(self,client,self.output_dir/"receipts").submit(text,previous,request_id=request_id)
            if reply.run is None:raise LLMError(reply.text)
            return reply.run
        # Preserve the explicit rule-mode error and the replaceable parse-only
        # protocol, but enforce the same local contract before any calculation.
        patch=client.parse_patch(text,task)
        from .modifications import compile_contract,validate_proposal,assert_preserved
        from .llm import LLMError
        if previous is None or not request_id:raise LLMError("自然语言修改需要已确认运行与稳定request_id")
        contract=compile_contract(text,previous)
        if not contract.ready:raise LLMError("仍有待补或矛盾条件，未求解")
        validate_proposal(patch,contract)
        revised=revise_task(previous.task,contract.patch,parent_run_id=previous.run_id)
        assert_preserved(previous.task,revised,contract)
        # Parse-only integrations cannot promise durable model explanations;
        # require the full tool adapter for automatic conversational execution.
        raise LLMError("该模型适配器仅提供参数解析；请使用支持call_tool的适配器或表单执行已校验修改")
