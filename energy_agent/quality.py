"""Conservative interval conversion and auditable quality checks, without imputation."""
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import Field, model_validator

from .schemas import Model, Positive


class IntervalContract(Model):
    quantity: Literal["power_kw", "interval_kwh", "cumulative_kwh"]
    source_step_minutes: Positive
    timestamp_position: Literal["start", "end", "boundary"]
    source_timezone: str
    numeric_precision: Positive = Field(description="声明的输入数值分辨率，不冒称仪表精度")

    @model_validator(mode="after")
    def anchor(self):
        if (self.quantity == "cumulative_kwh") != (self.timestamp_position == "boundary"):
            raise ValueError("累计读数需使用boundary时刻；区间功率/电量需明确start或end")
        return self


class QualityFinding(Model):
    code: str
    field: str
    count: int
    severity: Literal["error", "warning"]
    message: str
    examples: list[str] = Field(default_factory=list)


class QualityReport(Model):
    scope: str
    records: int
    time_start: str | None
    time_end: str | None
    expected_step_minutes: float
    observed_step_minutes: list[float]
    missing_records: int
    duplicate_records: int
    invalid_timestamps: int
    missing_values: int
    nonfinite_values: int
    negative_values: int
    jump_count: int
    findings: list[QualityFinding]
    valid: bool
    jump_rule: str
    treatment: str = "不填零、不插补、不删除异常；先选择合格连续窗口。异常跳变需人工确认。"

    def markdown(self) -> str:
        rows = [("范围", self.scope), ("记录数", self.records), ("起止", f"{self.time_start} — {self.time_end}"),
                ("期望间隔（分钟）", self.expected_step_minutes), ("缺失时段", self.missing_records),
                ("重复时间", self.duplicate_records), ("非法时间", self.invalid_timestamps),
                ("缺失值", self.missing_values), ("非有限/非数值", self.nonfinite_values),
                ("负值", self.negative_values), ("异常跳变", self.jump_count), ("可进入转换", self.valid)]
        text = "# 数据质量报告\n\n|检查|结果|\n|---|---|\n" + "\n".join(f"|{k}|{v}|" for k, v in rows)
        text += "\n\n" + self.treatment + "\n\n跳变规则：" + self.jump_rule + "\n"
        for finding in self.findings:
            text += f"\n- {finding.severity} / {finding.code}：{finding.message}（{finding.count}）；示例：{'、'.join(finding.examples)}\n"
        return text


class EnergyAudit(Model):
    raw_energy_kwh: float
    normalized_energy_kwh: float
    difference_kwh: float
    tolerance_kwh: float
    input_numeric_precision: float
    source_rounding_bound_kwh: float
    passed: bool
    explanation: str


def shanghai_timestamps(values, timezone: str) -> pd.DatetimeIndex:
    try:
        index = pd.DatetimeIndex(pd.to_datetime(values, errors="coerce"))
        if index.tz is None:
            index = index.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
        return index.tz_convert("Asia/Shanghai").as_unit("ns")
    except (ValueError, TypeError) as exc:
        raise ValueError("无法按声明时区解析时间；不能猜测混合时区或夏令时：" + str(exc)) from exc


def inspect_series(timestamps, values, *, step_minutes: float, timezone: str,
                   scope: str, field: str = "Record", jump_ratio: float = 8.0,
                   jump_absolute: float = 100.0) -> QualityReport:
    """Report original order and all invalid categories; never fix a record."""
    index = shanghai_timestamps(timestamps, timezone)
    raw = pd.Series(list(values))
    if len(index) != len(raw):
        raise ValueError("时间和值长度不一致")
    numeric = pd.to_numeric(raw, errors="coerce").to_numpy(dtype=float)
    missing_value = raw.isna().to_numpy()
    invalid = ~np.isfinite(numeric) & ~missing_value
    negative = np.isfinite(numeric) & (numeric < 0)
    valid_times = index.dropna()
    unique = valid_times.unique().sort_values()
    minutes = np.diff(unique.asi8) / 60e9
    duplicates = index.duplicated(keep=False) & index.notna()
    gap_count = 0
    if len(unique):
        expected = pd.date_range(unique[0], unique[-1], freq=pd.Timedelta(minutes=step_minutes))
        gaps = expected.difference(unique)
        gap_count = len(gaps)
    else:
        gaps = pd.DatetimeIndex([])
    off_grid = bool(len(minutes) and not np.allclose(minutes / step_minutes, np.rint(minutes / step_minutes)))
    off_grid = off_grid or (len(unique) > 0 and not (unique == unique.floor(pd.Timedelta(minutes=step_minutes))).all())
    original_order_invalid = not valid_times.is_monotonic_increasing
    # Detect jumps only between genuinely adjacent intervals, never across gaps.
    order = np.argsort(index.asi8, kind="stable")
    sorted_t, sorted_v = index[order], numeric[order]
    adjacent = np.diff(sorted_t.asi8) == round(step_minutes * 60e9)
    left, right = sorted_v[:-1], sorted_v[1:]
    jump = adjacent & np.isfinite(left) & np.isfinite(right)
    jump &= (np.abs(right - left) > jump_absolute) & (np.maximum(left, right) > jump_ratio * np.maximum(np.minimum(left, right), 1e-6))
    findings = []

    def finding(code, count, mask, message, severity="error"):
        if count:
            examples = [str(x) for x in mask][:20]
            findings.append(QualityFinding(code=code, field=field, count=int(count), severity=severity, message=message, examples=examples))

    finding("empty_series", int(len(raw) == 0), [], "没有记录，不能用于评估")
    finding("invalid_timestamp", int(index.isna().sum()), np.flatnonzero(index.isna()), "无法解析时间戳")
    finding("duplicate_timestamp", int(duplicates.sum()), index[duplicates], "同一测点存在重复时间，禁止直接求和")
    finding("missing_interval", gap_count, gaps, "缺失时段，不允许重编号为连续时间或补零")
    finding("missing_value", int(missing_value.sum()), index[missing_value], "缺失值")
    finding("nonfinite_value", int(invalid.sum()), index[invalid], "非法、非数值或无穷值")
    finding("negative_value", int(negative.sum()), index[negative], "负用电或累计读数复位，需核查")
    finding("abnormal_jump", int(jump.sum()), sorted_t[1:][jump], "异常跳变告警；不自动删除，当前窗口需另选或核实", "warning")
    finding("off_grid_interval", int(bool(off_grid)), unique, "间隔不是声明步长的整数倍")
    finding("unsorted_time", int(original_order_invalid), valid_times[:3], "时间未按递增顺序排列；请显式排序并记录处理")
    return QualityReport(scope=scope, records=len(raw), time_start=str(unique[0]) if len(unique) else None,
        time_end=str(unique[-1]) if len(unique) else None, expected_step_minutes=step_minutes,
        observed_step_minutes=sorted(set(float(x) for x in minutes)), missing_records=gap_count,
        duplicate_records=int(duplicates.sum()), invalid_timestamps=int(index.isna().sum()),
        missing_values=int(missing_value.sum()), nonfinite_values=int(invalid.sum()), negative_values=int(negative.sum()),
        jump_count=int(jump.sum()), findings=findings, valid=not findings,
        jump_rule=f"相邻时段变化>{jump_absolute:g}（输入单位）且较大值>{jump_ratio:g}×较小值；仅为人工审查阈值，不代表故障判定")


def normalize_intervals(timestamps, values, contract: IntervalContract, target_step_minutes: float = 60.0):
    """kW means -> energy; kWh sums; cumulative differences. Full bins only."""
    if not np.isfinite(target_step_minutes) or target_step_minutes <= 0:
        raise ValueError("目标步长必须为有限正数")
    ratio = target_step_minutes / contract.source_step_minutes
    if ratio < 1 or not np.isclose(ratio, round(ratio)):
        raise ValueError("仅支持源步长整数倍的完整区间降采样，不猜测上采样")
    index = shanghai_timestamps(timestamps, contract.source_timezone)
    report = inspect_series(index, values, step_minutes=contract.source_step_minutes, timezone="Asia/Shanghai", scope="转换区间", jump_absolute=float("inf"))
    if not report.valid:
        raise ValueError(report.markdown())
    values = np.asarray(values, dtype=float)
    dt = contract.source_step_minutes / 60.0
    if contract.quantity == "cumulative_kwh":
        if len(values) < 2:
            raise ValueError("累计表读数至少需两个边界读数")
        energies = np.diff(values)
        if np.any(energies < 0):
            raise ValueError("累计表读数下降/复位，不自动修复")
        starts = index[:-1]
        precision_kwh = contract.numeric_precision
    else:
        starts = index - pd.Timedelta(minutes=contract.source_step_minutes) if contract.timestamp_position == "end" else index
        energies = values * dt if contract.quantity == "power_kw" else values
        precision_kwh = contract.numeric_precision * dt if contract.quantity == "power_kw" else contract.numeric_precision
    series = pd.Series(energies, index=starts)
    groups = series.resample(pd.Timedelta(minutes=target_step_minutes), origin="start_day", label="left", closed="left")
    count = groups.count()
    if not (count == round(ratio)).all() or not (starts == starts.floor(pd.Timedelta(minutes=contract.source_step_minutes))).all():
        raise ValueError("存在不完整或未对齐目标边界的区间，不能无提示丢弃首末记录")
    energy = groups.sum(min_count=round(ratio))
    normalized = pd.DataFrame({"timestamp": energy.index, "electric_load_kw": energy.to_numpy() / (target_step_minutes / 60)})
    before = float(np.sum(energies))
    after = float(normalized.electric_load_kw.sum() * target_step_minutes / 60)
    tolerance = max(1e-8, precision_kwh / 100)
    audit = EnergyAudit(raw_energy_kwh=before, normalized_energy_kwh=after, difference_kwh=after-before,
        tolerance_kwh=tolerance, input_numeric_precision=contract.numeric_precision,
        source_rounding_bound_kwh=len(values) * precision_kwh / 2,
        passed=abs(after-before) <= tolerance,
        explanation="转换前后使用同一输入且不舍入，只允许浮点求和误差；容差取声明输入能量分辨率的1/100与1e-8 kWh较大者。原始数值舍入不确定性上界另列，不等同于转换误差或仪表精度。")
    if not audit.passed:
        raise ValueError("能量核对失败：" + audit.model_dump_json())
    return normalized, audit


def save_quality(report: QualityReport, directory: str | Path, name: str) -> dict[str, str]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {"json": directory / f"{name}.json", "markdown": directory / f"{name}.md"}
    paths["json"].write_text(report.model_dump_json(indent=2), encoding="utf-8")
    paths["markdown"].write_text(report.markdown(), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}
