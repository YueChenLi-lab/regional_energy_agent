"""Shared contracts. Powers are interval averages; all money is CNY (元)."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonNegative = Annotated[float, Field(ge=0)]
Positive = Annotated[float, Field(gt=0)]
Fraction = Annotated[float, Field(ge=0, le=1)]
Efficiency = Annotated[float, Field(gt=0, le=1)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


class Source(Model):
    source_id: str
    name: str
    region: str = "未知"
    time_range: str = "未知"
    units: dict[str, str] = Field(default_factory=dict)
    category: Literal["measured", "simulated", "synthetic", "user", "unknown"] = "unknown"
    processing: list[str] = Field(default_factory=list)
    conditions: str = "未知"


SERIES_UNITS = {
    "electric_load_kw": "kW", "heat_load_kw_th": "kW_th",
    "pv_per_kw": "kW/kW", "electricity_price": "元/kWh",
    "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh",
    "gas_emission_factor": "kgCO2e/kWh_LHV",
}


class TimeSeriesData(Model):
    timestamps: list[datetime] = Field(min_length=1, description="区间开始时间，等间隔且含时区")
    step_hours: Positive = Field(description="每个区间长度，h")
    electric_load_kw: list[NonNegative] = Field(description="常规用电功率，kW")
    heat_load_kw_th: list[NonNegative] = Field(description="供热功率，kW_th")
    pv_per_kw: list[Fraction] = Field(description="单位光伏装机平均出力，kW/kW，0..1")
    electricity_price: list[NonNegative] = Field(description="购电价格，元/kWh")
    gas_price: list[NonNegative] = Field(description="燃气低位热值价格，元/kWh_LHV")
    grid_emission_factor: list[NonNegative] = Field(description="电网运行排放因子，kgCO2e/kWh")
    gas_emission_factor: list[NonNegative] = Field(description="燃气运行排放因子，kgCO2e/kWh_LHV")
    units: dict[str, str]
    source_ids: dict[str, str] = Field(description="每个时序列到 Source.source_id 的映射")


class DeviceParameters(Model):
    source_id: str
    hp_cop: Annotated[float, Field(ge=1, le=10)] = Field(description="固定热泵COP，kWh_th/kWh")
    boiler_efficiency: Efficiency = Field(description="锅炉热效率，kWh_th/kWh_LHV")
    charge_efficiency: Efficiency = Field(description="充电效率，无量纲")
    discharge_efficiency: Efficiency = Field(description="放电效率，无量纲")
    soc_min_fraction: Fraction = Field(description="电池储能下限/额定能量，无量纲")
    soc_max_fraction: Fraction = Field(description="电池储能上限/额定能量，无量纲")
    soc_initial_fraction: Fraction = Field(description="期初及期末储能/额定能量，无量纲")
    pv_cost_per_kw: NonNegative = Field(description="光伏设备单价，元/kW")
    battery_cost_per_kwh: NonNegative = Field(description="电池能量容量单价，元/kWh")
    battery_power_cost_per_kw: NonNegative = Field(description="电池功率单价，元/kW")
    hp_cost_per_kw_th: NonNegative = Field(description="热泵热功率单价，元/kW_th")
    boiler_cost_per_kw_th: NonNegative = Field(description="锅炉热功率单价，元/kW_th")
    installation_fraction: NonNegative = Field(description="安装费/设备购置费，无量纲")
    grid_connection_cost_yuan: NonNegative = Field(description="新建项目统一电网接入费用，元")

    @model_validator(mode="after")
    def valid_soc(self):
        if not self.soc_min_fraction <= self.soc_initial_fraction <= self.soc_max_fraction:
            raise ValueError("SOC 初值必须位于上下限内")
        return self


class Constraints(Model):
    source_id: str
    budget_yuan: NonNegative | None = Field(default=None, description="初始投资预算，元；缺失需补充")
    grid_limit_kw: NonNegative = Field(description="电网购电功率上限，kW")
    pv_limit_kw: NonNegative = Field(description="场地可容纳光伏装机上限，kW")
    emission_limit_kg: NonNegative | None = Field(default=None, description="评估期运行排放上限，kgCO2e；空表示不限制")


class Candidate(Model):
    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    name: str
    source_id: str
    pv_kw: NonNegative = Field(description="光伏装机，kW")
    battery_power_kw: NonNegative = Field(description="电池双向功率上限，kW")
    battery_energy_kwh: NonNegative = Field(description="电池额定能量，kWh")
    hp_kw_th: NonNegative = Field(description="热泵热功率上限，kW_th")
    boiler_kw_th: NonNegative = Field(description="锅炉热功率上限，kW_th")

    @model_validator(mode="after")
    def battery_pair(self):
        if (self.battery_power_kw == 0) != (self.battery_energy_kwh == 0):
            raise ValueError("电池功率与能量容量必须同时为零或同时为正")
        return self


class TaskRequest(Model):
    project_name: str = "区域综合能源规划"
    version: int = Field(default=1, ge=1)
    parent_run_id: str | None = None
    data: TimeSeriesData | None = None
    devices: DeviceParameters | None = None
    constraints: Constraints | None = None
    candidates: list[Candidate] | None = Field(default=None, max_length=32)
    sources: list[Source] = Field(default_factory=list)
    unsupported_demands: list[str] = Field(default_factory=list, description="例如供冷；存在时拒绝运行并要求明确移除")
    demo: bool = False


class ProjectTask(TaskRequest):
    data: TimeSeriesData
    devices: DeviceParameters
    constraints: Constraints
    candidates: list[Candidate] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def budget_required(self):
        if self.constraints.budget_yuan is None:
            raise ValueError("缺少初始投资预算")
        if self.unsupported_demands:
            raise ValueError("存在尚未支持的需求：" + "、".join(self.unsupported_demands))
        return self


class Issue(Model):
    field: str
    message: str
    kind: Literal["missing", "invalid", "unsupported"] = "invalid"


class InputValidation(Model):
    ready: bool
    issues: list[Issue] = Field(default_factory=list)
    task: ProjectTask | None = None


class SolverOptions(Model):
    time_limit_seconds: Positive = 30.0
    mip_rel_gap: Annotated[float, Field(ge=0, le=0.1)] = 1e-6


class SolveRequest(Model):
    task: ProjectTask
    candidate: Candidate
    options: SolverOptions = Field(default_factory=SolverOptions)


class DispatchPoint(Model):
    timestamp: datetime
    grid_kw: float
    pv_used_kw: float
    curtailment_kw: float
    hp_heat_kw_th: float
    hp_electric_kw: float
    boiler_heat_kw_th: float
    gas_kw_lhv: float = Field(description="燃气低位热值输入功率，kW；乘dt得到kWh_LHV")
    charge_kw: float
    discharge_kw: float


class DispatchResult(Model):
    candidate_id: str
    status: Literal["optimal", "feasible_limit", "no_solution_limit", "infeasible", "rejected", "error", "invalid"]
    message: str
    solve_seconds: NonNegative = 0
    mip_gap: NonNegative | None = None
    objective_yuan: float | None = None
    points: list[DispatchPoint] = Field(default_factory=list)
    soc_kwh: list[float] = Field(default_factory=list, description="N+1个边界状态：e[0]初值，e[t+1]区间t结束")
    charge_mode: list[float] = Field(default_factory=list, description="二进制：1可充电、0可放电")
    reasons: list[str] = Field(default_factory=list)


class ConstraintCheck(Model):
    name: str
    passed: bool
    max_violation: NonNegative = 0
    tolerance: NonNegative = 1e-5
    detail: str = ""


class Metrics(Model):
    investment_yuan: NonNegative = Field(description="新建项目初始投资，元")
    operating_cost_yuan: float = Field(description="评估期购电与购气费用，元")
    emissions_kg: float = Field(description="评估期运行阶段排放，kgCO2e")
    grid_kwh: float = Field(description="评估期购电量，kWh")
    gas_kwh_lhv: float = Field(description="评估期燃气低位热值输入量，kWh_LHV")
    curtailed_pv_kwh: float = Field(description="评估期弃光量，kWh")
    electric_load_kwh: float = Field(description="评估期常规用电需求，kWh")
    heat_load_kwh_th: float = Field(description="评估期供热需求，kWh_th")
    supply_satisfied: bool
    period_hours: Positive = Field(description="评估期长度，h")


class SolutionValidation(Model):
    valid: bool
    checks: list[ConstraintCheck]
    metrics: Metrics | None = None


class ValidationRequest(Model):
    task: ProjectTask
    candidate: Candidate
    dispatch: DispatchResult


class CandidateList(Model):
    candidates: list[Candidate]


class ScenarioResult(Model):
    candidate: Candidate
    investment_yuan: NonNegative
    dispatch: DispatchResult
    validation: SolutionValidation


class ComparisonRequest(Model):
    scenarios: list[ScenarioResult]


class Comparison(Model):
    ranked_ids: list[str]
    recommended_id: str | None
    explanation: str


class RunState(StrEnum):
    RECEIVED = "接收任务"
    VALIDATING = "校验输入"
    NEEDS_INPUT = "待补信息"
    READY = "准备运行"
    BUILDING = "生成候选"
    SOLVING = "求解"
    CHECKING = "结果校验"
    COMPARING = "比较"
    REPORTING = "报告"
    COMPLETED = "完成"
    FAILED = "执行失败"


class ToolCall(Model):
    run_id: str
    input_version: int
    tool_name: str
    status: Literal["success", "error"]
    seconds: NonNegative
    summary: str
    source_ids: list[str]
    result_file: str


class RunResult(Model):
    run_id: str
    input_version: int
    state: RunState
    states: list[RunState]
    task: TaskRequest
    solver_options: SolverOptions = Field(default_factory=SolverOptions)
    issues: list[Issue] = Field(default_factory=list)
    scenarios: list[ScenarioResult] = Field(default_factory=list)
    comparison: Comparison | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    previous_run_id: str | None = None
    changes: dict = Field(default_factory=dict)


class TaskPatch(Model):
    budget_yuan: NonNegative | None = None
    emission_limit_kg: NonNegative | None = None
    clear_emission_limit: bool = False
    demand_scale: Annotated[float, Field(gt=0, le=100)] | None = None
    grid_limit_kw: NonNegative | None = None
    pv_limit_kw: NonNegative | None = None
    unsupported_demands: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_emission_change(self):
        if self.clear_emission_limit and self.emission_limit_kg is not None:
            raise ValueError("不能同时设置与清除排放上限")
        return self


class ReportRequest(Model):
    run: RunResult


class ReportText(Model):
    markdown: str
