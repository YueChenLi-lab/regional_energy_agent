"""Human-readable reports and machine-readable, traceable run artifacts."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .schemas import ReportRequest, ReportText, RunResult, ScenarioResult


STATUS_LABELS = {
    "optimal": "已证明最优（该候选运行）",
    "feasible_limit": "已有可行解，未证明最优",
    "no_solution_limit": "达到限制，未找到解",
    "infeasible": "运行无解",
    "rejected": "预检查不通过",
    "error": "求解错误",
    "invalid": "独立校验不通过",
}

ASSUMPTIONS = [
    "区域内所有建筑合并为一个供能节点，仅建模常规用电和供热，要求每个时间区间足额供能。",
    "光伏、电池、热泵和燃气锅炉按新建项目计投资；预算约束初始投资，运行费仅统计本评估期。",
    "热泵采用固定 COP，锅炉采用固定效率；燃气统一按低位热值 kWh_LHV 计量。",
    "电池以 N+1 个区间边界状态记录：SOC[t] 是区间 t 开始状态，SOC[t+1] 是结束状态；期末等于期初。",
    "电池充放电使用二进制互斥约束；不允许售电，不采用隐含缺供或负荷削减。",
    "排放为购电与燃气使用的运行阶段排放，不代表设备全生命周期排放或全生命周期零碳。",
    "仅比较配置文件提供的有限候选；不构成连续容量空间的全局规划最优证明。",
    "尚未实现供冷、冷热管网、空间选址、设备故障备用、售电、绿证、碳抵消、全生命周期隐含排放。",
    "不将本评估期结果乘以 52 等系数冒充全年指标，也不将全部投资与短期运行费相加称为生命周期成本。",
]


def ordered_scenarios(run: RunResult) -> list[ScenarioResult]:
    """Show feasible scenarios by operating-cost rank, followed by all others."""
    rank = {candidate_id: i for i, candidate_id in enumerate(run.comparison.ranked_ids)} if run.comparison else {}
    return sorted(run.scenarios, key=lambda scenario: rank.get(scenario.candidate.candidate_id, len(rank)))


def scenario_row(scenario: ScenarioResult, rank: int | None = None) -> dict[str, Any]:
    """One complete comparison row, including infeasible and rejected scenarios."""
    c, d, v = scenario.candidate, scenario.dispatch, scenario.validation
    m = v.metrics
    return {
        "candidate_id": c.candidate_id,
        "rank": rank,
        "name": c.name,
        "source_id": c.source_id,
        "pv_kw": c.pv_kw,
        "battery_power_kw": c.battery_power_kw,
        "battery_energy_kwh": c.battery_energy_kwh,
        "hp_kw_th": c.hp_kw_th,
        "boiler_kw_th": c.boiler_kw_th,
        "investment_yuan": scenario.investment_yuan,
        "operating_cost_yuan": m.operating_cost_yuan if m else None,
        "emissions_kg": m.emissions_kg if m else None,
        "grid_kwh": m.grid_kwh if m else None,
        "gas_kwh_lhv": m.gas_kwh_lhv if m else None,
        "curtailed_pv_kwh": m.curtailed_pv_kwh if m else None,
        "electric_load_kwh": m.electric_load_kwh if m else None,
        "heat_load_kwh_th": m.heat_load_kwh_th if m else None,
        "period_hours": m.period_hours if m else None,
        "supply_satisfied": m.supply_satisfied if m else None,
        "constraints_passed": v.valid,
        "status": d.status,
        "solve_seconds": d.solve_seconds,
        "mip_gap": d.mip_gap,
        "reason": "；".join(d.reasons) or d.message,
    }


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        if 0 < abs(value) < 0.001:
            return f"{value:.4g}"
        return f"{value:,.4f}"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(_cell(v) for v in row) + " |" for row in rows),
    ])


def generate_report(request: ReportRequest) -> ReportText:
    run = request.run
    task = run.task
    scenarios = ordered_scenarios(run)
    chunks = [
        "# 区域综合能源低碳规划评估报告",
        f"项目：{_cell(task.project_name)}\n\n运行 ID：`{run.run_id}`；输入版本：{run.input_version}；状态：{run.state.value}。",
        "**合成演示数据**：负荷、资源、价格、排放因子和设备费用为演示假设，不代表当地现行参数。"
        if task.demo else "数据性质与使用条件见来源记录；未知信息不能视为实测依据。",
        "## 任务条件",
    ]
    if task.data is not None:
        data = task.data
        chunks.append(
            f"{len(data.timestamps)} 个区间，时间步长 {data.step_hours:g} h，评估时长 "
            f"{len(data.timestamps) * data.step_hours:g} h。区间开始时间："
            f"{data.timestamps[0].isoformat()} 至 {data.timestamps[-1].isoformat()}；"
            "最后区间结束时间为最后开始时间加一个时间步。仅报告该时段结果。"
        )
    if task.constraints is not None:
        c = task.constraints
        chunks.append(_table(["条件", "数值", "单位"], [
            ["初始投资预算", c.budget_yuan, "元"],
            ["评估期排放上限", c.emission_limit_kg if c.emission_limit_kg is not None else "不限制", "kgCO2e"],
            ["电网购电功率上限", c.grid_limit_kw, "kW"],
            ["光伏场地上限", c.pv_limit_kw, "kW"],
        ]))
        chunks.append(f"项目条件来源：`{c.source_id}`。")
    chunks.append(f"求解设置：每个候选时限 {run.solver_options.time_limit_seconds:g} 秒；相对最优性间隙容差 {run.solver_options.mip_rel_gap:g}。")
    if run.issues:
        chunks.extend(["## 待补充或修正", _table(["字段", "类别", "说明"], [
            [i.field, i.kind, i.message] for i in run.issues
        ])])
    chunks.append("## 候选配置与结果")
    if run.scenarios:
        chunks.append(_table(
            ["方案", "光伏 kW", "电池 kW / kWh", "热泵 kW_th", "锅炉 kW_th", "投资 元", "运行费 元", "排放 kgCO2e", "求解状态", "约束通过", "容量来源"],
            [[s.candidate.candidate_id + " " + s.candidate.name,
              s.candidate.pv_kw, f"{s.candidate.battery_power_kw:g} / {s.candidate.battery_energy_kwh:g}",
              s.candidate.hp_kw_th, s.candidate.boiler_kw_th, s.investment_yuan,
              s.validation.metrics.operating_cost_yuan if s.validation.metrics else None,
              s.validation.metrics.emissions_kg if s.validation.metrics else None,
              STATUS_LABELS[s.dispatch.status], s.validation.valid, s.candidate.source_id] for s in scenarios],
        ))
        chunks.append(_table(
            ["方案", "购电 kWh", "燃气 kWh_LHV", "弃光 kWh", "常规用电 kWh", "供热 kWh_th", "供能满足", "求解秒数", "相对最优性间隙"],
            [[s.candidate.candidate_id,
              *([s.validation.metrics.grid_kwh, s.validation.metrics.gas_kwh_lhv,
                 s.validation.metrics.curtailed_pv_kwh, s.validation.metrics.electric_load_kwh,
                 s.validation.metrics.heat_load_kwh_th, s.validation.metrics.supply_satisfied]
                if s.validation.metrics else [None, None, None, None, None, "未验证（无运行解）"]),
              s.dispatch.solve_seconds, s.dispatch.mip_gap] for s in scenarios],
        ))
    else:
        chunks.append("未进行候选求解；请先补充或修正输入。")
    chunks.append("## 比较与推荐")
    if run.comparison is not None and run.comparison.recommended_id is not None:
        chunks.append(
            f"在本次评估的候选方案中，推荐 **{run.comparison.recommended_id}**。"
            f"{run.comparison.explanation}\n\n"
            "先筛选预算、供能与排放等约束，再按本评估期运行费排序；投资与排放完整列出以展示取舍。"
            "若某候选仅取得可行解，则排序基于当前可行解，不能据此证明该候选运行最优。"
        )
    else:
        chunks.append("在本次评估的候选方案中，暂无通过全部约束与独立校验的可行方案。" +
                      (run.comparison.explanation if run.comparison else "输入未就绪或未完成比较。"))
    chunks.append("## 不可行、未完成求解与独立检查")
    for scenario in scenarios:
        chunks.append(f"### {scenario.candidate.candidate_id}：{STATUS_LABELS[scenario.dispatch.status]}")
        chunks.append(_cell(scenario.dispatch.message))
        if scenario.dispatch.reasons:
            chunks.append("\n".join(f"- {_cell(reason)}" for reason in scenario.dispatch.reasons))
        chunks.append(_table(["检查", "通过", "最大违反量", "容差", "说明"], [
            [check.name, check.passed, check.max_violation, check.tolerance, check.detail]
            for check in scenario.validation.checks
        ]))
    if task.devices is not None:
        d = task.devices
        chunks.extend(["## 设备与新建项目投资假设", _table(["参数", "值", "单位"], [
            ["光伏设备单价", d.pv_cost_per_kw, "元/kW"],
            ["电池能量单价", d.battery_cost_per_kwh, "元/kWh"],
            ["电池功率单价", d.battery_power_cost_per_kw, "元/kW"],
            ["热泵设备单价", d.hp_cost_per_kw_th, "元/kW_th"],
            ["锅炉设备单价", d.boiler_cost_per_kw_th, "元/kW_th"],
            ["安装费/设备费", d.installation_fraction, "无量纲"],
            ["电网接入费用", d.grid_connection_cost_yuan, "元"],
            ["固定热泵 COP", d.hp_cop, "kWh_th/kWh"],
            ["锅炉效率", d.boiler_efficiency, "kWh_th/kWh_LHV"],
            ["充电效率 / 放电效率", f"{d.charge_efficiency:g} / {d.discharge_efficiency:g}", "无量纲"],
            ["SOC 下限 / 上限 / 初值", f"{d.soc_min_fraction:g} / {d.soc_max_fraction:g} / {d.soc_initial_fraction:g}", "额定能量比例"],
        ]), f"设备参数与费用来源：`{d.source_id}`。\n\n初始投资 = 设备购置费合计 × (1 + 安装费比例) + 电网接入费。电网接入费对所有候选采用相同口径。"])
    chunks.append("## 数据与参数来源")
    for source in task.sources:
        chunks.append(_table(["项目", "记录"], [
            ["source_id", source.source_id], ["名称", source.name], ["地区", source.region],
            ["时间范围", source.time_range], ["类别", source.category],
            ["单位", json.dumps(source.units, ensure_ascii=False)],
            ["处理记录", "；".join(source.processing) or "未处理 / 未知"],
            ["使用条件", source.conditions],
        ]))
    if task.data is not None:
        chunks.append("时序字段来源映射：\n\n" + _table(["字段", "source_id", "单位"], [
            [name, source_id, task.data.units.get(name, "未知")]
            for name, source_id in task.data.source_ids.items()
        ]))
    chunks.extend(["## 模型假设、适用范围与尚未实现内容", "\n".join(f"- {item}" for item in ASSUMPTIONS)])
    if run.previous_run_id is not None:
        chunks.extend(["## 场景变更", f"前次运行：`{run.previous_run_id}`；本次输入版本 {run.input_version}，计算状态见执行追溯。",
                       "```json\n" + json.dumps(run.changes, ensure_ascii=False, indent=2) + "\n```"])
    chunks.extend(["## 执行追溯", "状态流转：" + " → ".join(s.value for s in run.states),
                   _table(["工具", "输入版本", "状态", "耗时 秒", "结果文件", "摘要"], [
                       [call.tool_name, call.input_version, call.status, call.seconds, call.result_file, call.summary]
                       for call in run.tool_calls
                   ])])
    if run.files:
        chunks.append("结果文件：\n\n" + "\n".join(f"- {name}: `{path}`" for name, path in run.files.items()))
    return ReportText(markdown="\n\n".join(chunks) + "\n")


def _write_csv(path: Path, rows: list[dict], empty_fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else empty_fields)
        writer.writeheader()
        writer.writerows(rows)


def export_run(run: RunResult, output_dir: Path) -> dict[str, str]:
    """Write finalized records; repeatable after the Agent appends its last tool call."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "json": str(directory / "result.json"),
        "csv": str(directory / "scenarios.csv"),
        "markdown": str(directory / "report.md"),
    }
    ranks = {name: i + 1 for i, name in enumerate(run.comparison.ranked_ids)} if run.comparison else {}
    _write_csv(Path(files["csv"]), [dict(run_id=run.run_id, input_version=run.input_version, **scenario_row(s, ranks.get(s.candidate.candidate_id))) for s in ordered_scenarios(run)], ["run_id", "input_version", "candidate_id", "status"])
    for scenario in run.scenarios:
        dispatch = scenario.dispatch
        path = directory / f"dispatch_{scenario.candidate.candidate_id}.csv"
        rows = []
        for index, point in enumerate(dispatch.points):
            row = point.model_dump(mode="json")
            row["soc_start_kwh"] = dispatch.soc_kwh[index] if index < len(dispatch.soc_kwh) else None
            row["soc_end_kwh"] = dispatch.soc_kwh[index + 1] if index + 1 < len(dispatch.soc_kwh) else None
            if run.task.data is not None:
                row["step_hours"] = run.task.data.step_hours
                row["electric_load_kw"] = run.task.data.electric_load_kw[index]
                row["heat_load_kw_th"] = run.task.data.heat_load_kw_th[index]
                row["pv_available_kw"] = run.task.data.pv_per_kw[index] * scenario.candidate.pv_kw
            rows.append(row)
        _write_csv(path, rows, ["timestamp", "grid_kw", "soc_start_kwh", "soc_end_kwh"])
        files[f"dispatch_{scenario.candidate.candidate_id}"] = str(path)
    run.files = files
    Path(files["json"]).write_text(run.model_dump_json(indent=2), encoding="utf-8")
    Path(files["markdown"]).write_text(generate_report(ReportRequest(run=run)).markdown, encoding="utf-8")
    return files
