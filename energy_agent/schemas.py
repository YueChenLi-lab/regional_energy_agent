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


class Artifact(Model):
    url: str
    filename: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieved_at: datetime | None = None
    member_path: str | None = None
    container_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    publisher_checksum: str | None = None
    license_id: str = "未知"


class Source(Model):
    source_id: str
    name: str
    region: str = "未知"
    time_range: str = "未知"
    units: dict[str, str] = Field(default_factory=dict)
    category: Literal["measured", "simulated", "synthetic", "estimated", "assumption", "user", "unknown"] = "unknown"
    processing: list[str] = Field(default_factory=list)
    conditions: str = "未知"
    url: str | None = None
    version: str = "未知"
    artifacts: list[Artifact] = Field(default_factory=list)
    parent_source_ids: list[str] = Field(default_factory=list)


class CaseContext(Model):
    boundary: str
    excluded: list[str]
    timestamp_convention: str
    investment_scope: str
    location: str = "未知"
    quality_summary: str = "未知"
    energy_check: str = "未知"
    pending: list[str] = Field(default_factory=list)
    import_files: dict[str, str] = Field(default_factory=dict)


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
    grid_emission_factor: list[NonNegative] = Field(description="电网运行排放因子，kgCO2e/kWh；任务emission_species=CO2时为kgCO2/kWh")
    gas_emission_factor: list[NonNegative] = Field(description="燃气运行排放因子，kgCO2e/kWh_LHV；物质为CO2时相应改为kgCO2/kWh_LHV")
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
    emission_limit_kg: NonNegative | None = Field(default=None, description="评估期运行排放上限，kgCO2e或kgCO2，见任务emission_species；空表示不限制")


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


CAPACITY_FIELDS = ("pv_kw", "battery_power_kw", "battery_energy_kwh", "hp_kw_th", "boiler_kw_th")


class CapacityRange(Model):
    lower: NonNegative = 0
    upper: NonNegative

    @model_validator(mode="after")
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError("容量下限不得大于上限")
        return self


class CapacityBounds(Model):
    source_id: str
    pv_kw: CapacityRange
    battery_power_kw: CapacityRange
    battery_energy_kwh: CapacityRange
    hp_kw_th: CapacityRange
    boiler_kw_th: CapacityRange
    battery_min_duration_hours: Positive = 0.5
    battery_max_duration_hours: Positive = 8

    @model_validator(mode="after")
    def duration(self):
        if self.battery_min_duration_hours > self.battery_max_duration_hours:
            raise ValueError("电池时长范围反向")
        return self


class AssetEconomics(Model):
    lifetime_years: int = Field(ge=1, le=100)
    fixed_om_fraction: NonNegative = Field(default=0, description="每年固定维护费/该设备含安装的第0年投资")
    replacement_fraction: NonNegative = Field(default=1, description="更换费用/该设备含安装的第0年投资")
    residual_method: Literal["straight_line", "none"] = "straight_line"


class Economics(Model):
    source_id: str
    horizon_years: int = Field(default=20, ge=1, le=100)
    discount_rate: float = Field(default=0.05, ge=0, le=1)
    assets: dict[str, AssetEconomics]
    battery_variable_om_per_kwh: NonNegative = Field(default=0, description="按放电电量收取，元/kWh")
    hp_variable_om_per_kwh_th: NonNegative = 0
    boiler_variable_om_per_kwh_th: NonNegative = 0
    representative_year_assumption: str = Field(min_length=1, default="同一完整年度的负荷、资源、价格和排放因子重复用于未来每年；无增长、衰减或多年预测")

    @model_validator(mode="after")
    def known_assets(self):
        if set(self.assets) != set(CAPACITY_FIELDS):
            raise ValueError("经济参数必须完整包含五种容量的寿命、维护、更换与残值")
        return self


class CashFlow(Model):
    year: int
    investment_yuan: float = 0
    energy_yuan: float = 0
    fixed_om_yuan: float = 0
    variable_om_yuan: float = 0
    replacement_yuan: float = 0
    residual_credit_yuan: float = 0
    net_yuan: float
    discounted_yuan: float


class EconomicResult(Model):
    npv_cost_yuan: float
    annual_energy_cost_yuan: float
    annual_fixed_om_yuan: float
    annual_variable_om_yuan: float
    annual_emissions_kg: float
    horizon_operating_emissions_kg: float
    cashflows: list[CashFlow]
    assumption: str


class ModelStatistics(Model):
    intervals: int
    variables: int
    binaries: int
    constraints: int
    nonzeros: int
    objective_kind: str
    objective_value: float | None = None
    dual_bound: float | None = None


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
    assessment_mode: Literal["electric_heat", "electric_only"] = "electric_heat"
    emission_species: Literal["CO2e", "CO2"] = "CO2e"
    case_context: CaseContext | None = None
    planning_mode: Literal["candidates", "capacity"] = "candidates"
    capacity_objective: Literal["npv", "emissions"] = "npv"
    resolution: Literal["period", "full_year", "quick_period"] = "period"
    capacity_bounds: CapacityBounds | None = None
    economics: Economics | None = None


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
        if self.assessment_mode == "electric_only":
            if self.case_context is None:
                raise ValueError("电侧评估必须声明计量边界与未建模供热")
            if any(self.data.heat_load_kw_th):
                raise ValueError("电侧评估不建模供热，热负荷占位数组必须全部为零")
            if any(c.hp_kw_th or c.boiler_kw_th for c in self.candidates):
                raise ValueError("电侧候选不得含热泵或锅炉，不保证供热需求")
        if self.planning_mode == "capacity" and (self.capacity_bounds is None or self.economics is None):
            raise ValueError("容量规划需要容量范围与全年经济参数")
        if self.assessment_mode == "electric_only" and self.capacity_bounds:
            if self.capacity_bounds.hp_kw_th.upper or self.capacity_bounds.boiler_kw_th.upper:
                raise ValueError("电侧模式不能启用热设备容量")
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
    model_statistics: ModelStatistics | None = None


class ConstraintCheck(Model):
    name: str
    passed: bool
    max_violation: NonNegative = 0
    tolerance: NonNegative = 1e-5
    detail: str = ""


class Metrics(Model):
    investment_yuan: NonNegative = Field(description="新建项目初始投资，元")
    operating_cost_yuan: float = Field(description="评估期购电与购气费用，元")
    emissions_kg: float = Field(description="评估期运行阶段排放，kgCO2e或kgCO2，见任务emission_species；禁止互换")
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
    economics: EconomicResult | None = None


class ComparisonRequest(Model):
    scenarios: list[ScenarioResult]
    planning_mode: Literal["candidates", "capacity"] = "candidates"
    objective: Literal["npv", "emissions"] = "npv"


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
    budget_multiplier: Annotated[float, Field(gt=0, le=10)] | None = None
    preserve_heat: bool = False

    @model_validator(mode="after")
    def consistent_emission_change(self):
        if self.budget_yuan is not None and self.budget_multiplier is not None:
            raise ValueError("绝对预算与相对预算不能同时修改")
        if self.preserve_heat and self.demand_scale not in (None, 1):
            raise ValueError("保持供热时不得缩放负荷")
        if self.clear_emission_limit and self.emission_limit_kg is not None:
            raise ValueError("不能同时设置与清除排放上限")
        return self


class ReportRequest(Model):
    run: RunResult


class ReportText(Model):
    markdown: str
