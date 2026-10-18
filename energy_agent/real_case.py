"""Build an explicitly bounded electric-only mixed-source assessment."""
import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from pydantic import Field, model_validator

from .adapters import ImportedLoad
from .quality import save_quality, shanghai_timestamps
from .schemas import (SERIES_UNITS, Candidate, CaseContext, Constraints, DeviceParameters,
                      Fraction, Model, NonNegative, Source, TaskRequest, TimeSeriesData)
from .solar import SolarSettings, load_nasa_pv


class PricePeriod(Model):
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)
    yuan_per_kwh: NonNegative


class TariffSettings(Model):
    region: str = "上海（人工情景，非官方现行电价）"
    applicable_year: str = "情景假设，不宣称适用于2017或当前年份"
    customer_class: str = "办公建筑情景，未核实电压等级与用户分类"
    cost_scope: str = "仅按购电量计费；未计基本电费、需量费、容量费、功率因数调整及税费差异"
    periods: list[PricePeriod] = Field(default_factory=lambda: [
        PricePeriod(start_hour=0, end_hour=7, yuan_per_kwh=0.38),
        PricePeriod(start_hour=7, end_hour=17, yuan_per_kwh=0.72),
        PricePeriod(start_hour=17, end_hour=22, yuan_per_kwh=1.15),
        PricePeriod(start_hour=22, end_hour=24, yuan_per_kwh=0.72),
    ])

    @model_validator(mode="after")
    def complete_day(self):
        counts = np.zeros(24, dtype=int)
        for period in self.periods:
            if period.end_hour <= period.start_hour:
                raise ValueError("跨午夜价格段需在0/24点拆成两段，禁止反向或空区间")
            counts[period.start_hour:period.end_hour] += 1
        if not (counts == 1).all():
            raise ValueError("时段电价必须恰好覆盖每天24小时，无重叠或空档")
        return self

    def expand(self, timestamps):
        hours = pd.DatetimeIndex(timestamps).tz_convert("Asia/Shanghai").hour
        prices = np.zeros(len(hours))
        for period in self.periods:
            prices[(hours >= period.start_hour) & (hours < period.end_hour)] = period.yuan_per_kwh
        return prices.tolist()


class ElectricCaseParameters(Model):
    budget_yuan: NonNegative | None = None
    grid_limit_kw: NonNegative | None = None
    pv_limit_kw: NonNegative | None = None
    emission_limit_kg: NonNegative | None = None
    emission_factor: NonNegative = 0.55
    emission_species: str = Field(default="CO2e", pattern=r"^(CO2|CO2e)$")
    emission_factor_year: str = "人为情景假设，非官方历史因子"
    tariff: TariffSettings = Field(default_factory=TariffSettings)
    pv_cost_per_kw: NonNegative = 3200
    battery_cost_per_kwh: NonNegative = 900
    battery_power_cost_per_kw: NonNegative = 450
    installation_fraction: NonNegative = 0.15
    battery_charge_efficiency: float = Field(default=0.95, gt=0, le=1)
    battery_discharge_efficiency: float = Field(default=0.95, gt=0, le=1)
    battery_power_fraction_of_peak: float = Field(default=0.25, gt=0, le=2)
    battery_duration_hours: float = Field(default=2, gt=0, le=24)
    pv_fraction_of_peak: float = Field(default=0.5, gt=0, le=5)
    solar: SolarSettings = Field(default_factory=SolarSettings)
    include_solar: bool = False


def load_hourly_tariff(path: str | Path, timestamps) -> list[float]:
    frame = pd.read_csv(path)
    if set(frame.columns) != {"timestamp", "yuan_per_kwh"}:
        raise ValueError("逐时电价CSV必须恰为timestamp,yuan_per_kwh，单位元/kWh")
    index = shanghai_timestamps(frame.timestamp, "Asia/Shanghai")
    values = pd.to_numeric(frame.yuan_per_kwh, errors="coerce").to_numpy(dtype=float)
    if index.hasnans or index.duplicated().any() or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("逐时电价含非法时间、重复、缺失、非有限或负值")
    prices = pd.Series(values, index=index).reindex(pd.DatetimeIndex(timestamps))
    if prices.isna().any():
        raise ValueError("逐时电价未覆盖全部负荷小时，不前向填充或补零")
    return prices.tolist()


def build_electric_task(load: ImportedLoad, parameters: ElectricCaseParameters, *, cache_dir="data_cache/raw", offline=True,
                         hourly_prices: list[float] | None = None, price_source: Source | None = None) -> TaskRequest:
    p = ElectricCaseParameters.model_validate(parameters)
    times = pd.DatetimeIndex(load.frame.timestamp)
    n = len(times)
    peak = float(load.frame.electric_load_kw.max())
    power = float(max(10, np.ceil(peak * p.battery_power_fraction_of_peak / 10) * 10))
    energy = power * p.battery_duration_hours
    pv_capacity = float(max(10, np.ceil(peak * p.pv_fraction_of_peak / 10) * 10))
    grid_limit = p.grid_limit_kw if p.grid_limit_kw is not None else float(max(10, np.ceil(peak * 1.1 / 10)*10))
    site_limit = p.pv_limit_kw if p.pv_limit_kw is not None else pv_capacity
    sources = [load.source]
    pending = ["匿名建筑精确位置、计量回路覆盖及Time区间锚点缺少独立证明，采用明确的边界与时间假设",
               "价格、排放因子、设备成本和场地均为人工情景，尚未核实2017适用政策或工程条件"]
    pv = [0.0] * n
    solar_available = False
    if p.include_solar:
        try:
            pv, solar_sources, _ = load_nasa_pv(times, p.solar, cache_dir=cache_dir, offline=offline)
        except (OSError, ValueError, httpx.HTTPError) as exc:
            pending.append(f"光伏候选未完成：NASA POWER不可用或校验失败（{type(exc).__name__}: {exc}）；仅评估电网与储能，没有用合成或改年EPW替代")
        else:
            sources.extend(solar_sources)
            solar_available = True
    else:
        pending.append("本次显式未启用光伏；没有将无气象输入解释为实测无日照，光伏候选未运行")
    if not solar_available:
        sources.append(Source(source_id="pv-disabled", name="光伏模块未启用占位", category="assumption",
            units={"pv_per_kw": "kW/kW"}, processing=["pv_per_kw零数组只用于停用PV；所有候选pv_kw=0"], conditions="不代表真实太阳资源为零"))
    inactive = Source(source_id="heating-disabled", name="电侧模式明确停用供热/燃气", category="assumption",
        units={"heat_load_kw_th": "kW_th", "gas_price": "元/kWh_LHV", "gas_emission_factor": f"kg{p.emission_species}/kWh_LHV"},
        processing=["热负荷、燃气价格和因子为零占位；候选热泵与锅炉容量均为零，不把W暖通电量转为热需求"],
        conditions="不建模供热，不代表楼宇没有供热需求，也不代表供热已得到保障；W若选中仍保留为电负荷")
    tariff_source = price_source or Source(source_id="scenario-tariff", name="人工情景时段电价（非上海官方历史价格）", category="assumption",
        region=p.tariff.region, time_range=p.tariff.applicable_year, units={"electricity_price": "元/kWh"},
        processing=[p.tariff.model_dump_json(), "按原负荷日期的北京时间小时展开，不改动时间轴"], conditions=p.tariff.customer_class + "；" + p.tariff.cost_scope)
    if hourly_prices is not None and price_source is None:
        raise ValueError("自定义逐时电价必须同时给出来源与费用范围")
    prices = hourly_prices if hourly_prices is not None else p.tariff.expand(times)
    if len(prices) != n:
        raise ValueError("逐时电价与负荷长度不同")
    carbon = Source(source_id="scenario-emissions", name="人工情景常数排放因子（未冒充官方因子）", category="assumption",
        region="上海情景；非已核实官方省级因子", time_range=p.emission_factor_year, units={"grid_emission_factor": f"kg{p.emission_species}/kWh"},
        processing=[f"人工设置{p.emission_factor:g} kg{p.emission_species}/kWh，展开为逐时常数；不是实测逐时碳强度"],
        conditions="仅购电运行排放情景，不含生命周期；CO2和CO2e按用户声明分别保留，不互换。官方适用年份与核算范围尚待核实")
    equipment = Source(source_id="electric-scenario", name="新增电侧设备、容量与项目约束假设", category="assumption", region="匿名上海办公楼情景",
        units={"pv_cost_per_kw": "元/kW_DC", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW_DC"},
        parent_source_ids=[load.source.source_id], processing=[p.model_dump_json(),
            f"负荷保持原值：峰值{peak:.8g}kW；电池功率=ceil(峰值×{p.battery_power_fraction_of_peak}/10)×10={power:g}kW，能量=功率×{p.battery_duration_hours:g}h={energy:g}kWh",
            f"光伏候选容量=ceil(峰值×{p.pv_fraction_of_peak}/10)×10={pv_capacity:g}kW_DC；规模受控的情景容量，不是优化定容或已核实屋顶容量"],
        conditions="增量投资：只计新增PV、电池、功率变换与比例安装费；既有电网接入、既有暖通及照明设备不计投资，不主张新建全楼投资")
    sources += [inactive, tariff_source, carbon, equipment]
    base = dict(source_id="electric-scenario", hp_kw_th=0, boiler_kw_th=0)
    candidates = [Candidate(candidate_id="G", name="既有电网基线", pv_kw=0, battery_power_kw=0, battery_energy_kwh=0, **base),
        Candidate(candidate_id="GB", name="电网＋新增储能", pv_kw=0, battery_power_kw=power, battery_energy_kwh=energy, **base)]
    if solar_available:
        candidates += [Candidate(candidate_id="GP", name="电网＋新增光伏", pv_kw=pv_capacity, battery_power_kw=0, battery_energy_kwh=0, **base),
            Candidate(candidate_id="GPB", name="电网＋新增光伏储能", pv_kw=pv_capacity, battery_power_kw=power, battery_energy_kwh=energy, **base)]
    units = {k: v.replace("CO2e", p.emission_species) for k,v in SERIES_UNITS.items()}
    data = TimeSeriesData(timestamps=times.to_pydatetime().tolist(), step_hours=1,
        electric_load_kw=load.frame.electric_load_kw.tolist(), heat_load_kw_th=[0]*n, pv_per_kw=pv,
        electricity_price=prices, gas_price=[0]*n, grid_emission_factor=[p.emission_factor]*n, gas_emission_factor=[0]*n,
        units=units, source_ids={"electric_load_kw": load.source.source_id, "heat_load_kw_th": inactive.source_id,
            "pv_per_kw": "estimated-pv" if solar_available else "pv-disabled", "electricity_price": tariff_source.source_id,
            "gas_price": inactive.source_id, "grid_emission_factor": carbon.source_id, "gas_emission_factor": inactive.source_id})
    devices = DeviceParameters(source_id=equipment.source_id, hp_cop=1, boiler_efficiency=1,
        charge_efficiency=p.battery_charge_efficiency, discharge_efficiency=p.battery_discharge_efficiency,
        soc_min_fraction=0.1, soc_max_fraction=0.9, soc_initial_fraction=0.5,
        pv_cost_per_kw=p.pv_cost_per_kw, battery_cost_per_kwh=p.battery_cost_per_kwh,
        battery_power_cost_per_kw=p.battery_power_cost_per_kw, hp_cost_per_kw_th=0, boiler_cost_per_kw_th=0,
        installation_fraction=p.installation_fraction, grid_connection_cost_yuan=0)
    return TaskRequest(project_name=f"EnergyDetective上海匿名办公楼{load.selection.building}电侧评估", data=data, devices=devices,
        constraints=Constraints(source_id=equipment.source_id, budget_yuan=p.budget_yuan, grid_limit_kw=grid_limit,
            pv_limit_kw=site_limit, emission_limit_kg=p.emission_limit_kg), candidates=candidates, sources=sources, demo=False,
        assessment_mode="electric_only", emission_species=p.emission_species,
        case_context=CaseContext(boundary=load.boundary,
            excluded=["未选中的计量类别及发布文件未覆盖的用电", "供热需求及供热保障（零热数组仅为停用占位）", "供冷服务量、管网、故障备用、全生命周期、基本电费和需量费"],
            timestamp_convention=load.timestamp_note, investment_scope=equipment.conditions,
            location=p.solar.coordinate_scope, quality_summary=f"选中窗口{n}小时、{len(load.selection.meters)}类测点全部通过；整份所选建筑原文件{load.raw_rows}行。各类别全文件：" + "；".join(f"{load.selection.meters[i]}记录{r.records}、缺失{r.missing_records}、重复{r.duplicate_records}、负值{r.negative_values}、非法/缺失数值{r.nonfinite_values+r.missing_values}、跳变{r.jump_count}" for i,r in enumerate(load.whole_reports)) + "。窗外异常保留并单独报告，未自动删除。", energy_check=load.audit.model_dump_json(), pending=pending))


def export_import(load: ImportedLoad, task: TaskRequest, directory: str | Path) -> dict[str,str]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for i,report in enumerate(load.whole_reports):
        files = save_quality(report, directory, f"quality_full_{load.selection.meters[i]}")
        paths.update({f"quality_full_{i}_{k}": v for k,v in files.items()})
    for i,report in enumerate(load.selected_reports):
        files = save_quality(report, directory, f"quality_window_{load.selection.meters[i]}")
        paths.update({f"quality_window_{i}_{k}": v for k,v in files.items()})
    paths["energy_audit"] = str(directory/"energy_audit.json")
    Path(paths["energy_audit"]).write_text(load.audit.model_dump_json(indent=2), encoding="utf-8")
    data = task.data
    frame = pd.DataFrame({"timestamp": [t.isoformat() for t in data.timestamps], **{name: getattr(data,name) for name in SERIES_UNITS}})
    paths["normalized_csv"] = str(directory/"normalized.csv")
    frame.to_csv(paths["normalized_csv"], index=False)
    paths["series_metadata"] = str(directory/"series_metadata.json")
    Path(paths["series_metadata"]).write_text(json.dumps({"step_hours": data.step_hours, "units": data.units, "source_ids": data.source_ids},ensure_ascii=False,indent=2), encoding="utf-8")
    paths["task"] = str(directory/"task.json")
    paths["provenance"] = str(directory/"provenance.json")
    task.case_context.import_files = paths
    Path(paths["task"]).write_text(task.model_dump_json(indent=2), encoding="utf-8")
    Path(paths["provenance"]).write_text(json.dumps([s.model_dump(mode="json") for s in task.sources],ensure_ascii=False,indent=2), encoding="utf-8")
    return paths
