"""Strict unified format and deterministic synthetic demonstration data."""
import json
from importlib.resources import files
from pathlib import Path

import numpy as np
import pandas as pd

from .schemas import (
    SERIES_UNITS, InputValidation, Issue, ProjectTask, Source,
    TaskRequest, TimeSeriesData,
)


def check_data(data: TimeSeriesData) -> list[Issue]:
    issues = []
    n = len(data.timestamps)
    for field, unit in SERIES_UNITS.items():
        values = getattr(data, field)
        if len(values) != n:
            issues.append(Issue(field=f"data.{field}", message=f"长度 {len(values)} 与时间戳数 {n} 不符"))
        if data.units.get(field) != unit:
            issues.append(Issue(field=f"data.units.{field}", message=f"单位必须为 {unit}，不自动猜测或换算"))
        if not data.source_ids.get(field):
            issues.append(Issue(field=f"data.source_ids.{field}", message="缺少来源标识", kind="missing"))
    if any(t.utcoffset() is None for t in data.timestamps):
        issues.append(Issue(field="data.timestamps", message="时间戳必须包含时区"))
    else:
        seconds = np.array([t.timestamp() for t in data.timestamps])
        if len(set(seconds)) != n:
            issues.append(Issue(field="data.timestamps", message="存在重复时间戳"))
        if n > 1 and not np.allclose(np.diff(seconds), data.step_hours * 3600, rtol=0, atol=1e-6):
            issues.append(Issue(field="data.timestamps", message="时间必须递增、连续且间隔等于 step_hours；不自动补零"))
    return issues


def validate_inputs(request: TaskRequest) -> InputValidation:
    issues = []
    for name in ("data", "devices", "constraints", "candidates"):
        if not getattr(request, name):
            issues.append(Issue(field=name, message=f"请补充 {name}", kind="missing"))
    if request.constraints is not None and request.constraints.budget_yuan is None:
        issues.append(Issue(field="constraints.budget_yuan", message="请补充初始投资预算（元）", kind="missing"))
    if request.unsupported_demands:
        issues.append(Issue(field="unsupported_demands", message="v0.1 尚不支持：" + "、".join(request.unsupported_demands), kind="unsupported"))
    if request.data:
        issues.extend(check_data(request.data))
    source_ids = [s.source_id for s in request.sources]
    if len(source_ids) != len(set(source_ids)):
        issues.append(Issue(field="sources", message="source_id 不得重复"))
    refs = set(request.data.source_ids.values()) if request.data else set()
    refs |= {obj.source_id for obj in (request.devices, request.constraints) if obj is not None}
    refs |= {c.source_id for c in request.candidates or []}
    for ref in sorted(refs - set(source_ids)):
        issues.append(Issue(field="sources", message=f"来源 {ref} 未登记", kind="missing"))
    if request.candidates:
        ids = [c.candidate_id for c in request.candidates]
        if len(ids) != len(set(ids)):
            issues.append(Issue(field="candidates", message="candidate_id 不得重复"))
    if issues:
        return InputValidation(ready=False, issues=issues)
    return InputValidation(ready=True, task=ProjectTask.model_validate(request.model_dump()))


def load_csv(path: str | Path, metadata: dict) -> TimeSeriesData:
    """Read only our documented CSV + metadata format; never fill missing values."""
    if set(metadata) != {"step_hours", "units", "source_ids"}:
        raise ValueError("metadata 必须恰包含 step_hours、units、source_ids，不能覆盖 CSV 数据列")
    frame = pd.read_csv(path)
    expected = {"timestamp", *SERIES_UNITS}
    if set(frame.columns) != expected:
        raise ValueError(f"CSV 列必须恰为 {sorted(expected)}；缺少 {sorted(expected-set(frame.columns))}，未支持列 {sorted(set(frame.columns)-expected)}")
    if frame.isna().any().any():
        affected = frame.loc[frame.isna().any(axis=1), "timestamp"].astype(str).tolist()
        raise ValueError(f"存在缺失值，不自动填零。受影响时间：{affected[:10]}")
    payload = {name: frame[name].tolist() for name in SERIES_UNITS}
    payload.update(metadata)
    payload["timestamps"] = frame["timestamp"].tolist()
    data = TimeSeriesData.model_validate(payload)
    issues = check_data(data)
    if issues:
        raise ValueError("; ".join(issue.message for issue in issues))
    return data


def make_demo_task(seed: int = 42, hours: int = 168) -> ProjectTask:
    if not isinstance(hours, int) or hours < 1:
        raise ValueError("hours 必须为正整数")
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2025-01-06", periods=hours, freq="h", tz="Asia/Shanghai")
    hour = timestamps.hour.to_numpy()
    daytime = (hour >= 8) & (hour < 19)
    electric = np.maximum(0, 55 + 35 * daytime + rng.normal(0, 2, hours))
    heat = np.maximum(0, 70 + 18 * np.cos((hour - 6) * np.pi / 12) + rng.normal(0, 2, hours))
    pv = np.clip(np.sin((hour - 6) * np.pi / 12), 0, 1) * rng.uniform(0.65, 0.95, hours)
    pv[(hour <= 6) | (hour >= 18)] = 0.0
    price = np.where((hour >= 17) & (hour < 22), 1.15, np.where((hour < 7), 0.38, 0.72))
    values = {
        "electric_load_kw": electric.tolist(), "heat_load_kw_th": heat.tolist(), "pv_per_kw": pv.tolist(),
        "electricity_price": price.tolist(), "gas_price": [0.32] * hours,
        "grid_emission_factor": [0.55] * hours, "gas_emission_factor": [0.202] * hours,
    }
    period = f"{timestamps[0].isoformat()} 至 {(timestamps[-1] + pd.Timedelta(hours=1)).isoformat()}（末端不含）"
    config = json.loads(files("energy_agent").joinpath("demo_config.json").read_text(encoding="utf-8"))
    sources = [
        Source(source_id="demo-series", name="合成演示数据：电热负荷与光伏", region="虚构园区（未知真实地区）", time_range=period,
               units={k: v for k, v in SERIES_UNITS.items() if k in ("electric_load_kw", "heat_load_kw_th", "pv_per_kw")},
               category="synthetic", processing=[f"NumPy default_rng 固定随机种子 {seed}", "解析日周期加有界随机扰动；夜间光伏显式置零；负荷非负裁剪"], conditions="仅用于功能演示，非实测，不能直接用于工程决策"),
        Source(source_id="demo-market", name="合成演示数据：价格与排放因子假设", region="未知", time_range=period,
               units={k: v for k, v in SERIES_UNITS.items() if k not in ("electric_load_kw", "heat_load_kw_th", "pv_per_kw")},
               category="synthetic", processing=["预设峰谷电价、固定燃气价格和排放因子"], conditions="全部为演示假设，不代表当地现行价格或排放因子"),
        Source(source_id="demo-equipment", name="合成演示数据：设备与新建成本假设", category="synthetic",
               units={"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"},
               processing=["读取 demo_config.json"], conditions="演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列"),
        Source(source_id="demo-conditions", name="合成演示数据：项目条件", category="synthetic",
               units={"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, processing=["读取 demo_config.json"], conditions="预算、场地和接入功率均为演示假设"),
        Source(source_id="demo-candidates", name="合成演示数据：有限候选容量", category="synthetic",
               units={"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, processing=["读取 demo_config.json 的四个明确容量组合"], conditions="不代表所有可能配置；辅助锅炉不构成故障备用保证"),
    ]
    return ProjectTask(
        project_name="区域综合能源低碳规划评估 Agent — 合成演示园区", demo=True,
        data=TimeSeriesData(timestamps=timestamps.to_pydatetime().tolist(), step_hours=1, **values, units=SERIES_UNITS,
            source_ids={k: "demo-series" if k in ("electric_load_kw", "heat_load_kw_th", "pv_per_kw") else "demo-market" for k in SERIES_UNITS}),
        sources=sources, **config,
    )
