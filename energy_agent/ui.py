"""Chinese demo UI; all evaluation goes through the structured Agent API."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from .agent import EnergyAgent, revise_task
from .data import case_label, make_demo_task
from .reporting import ASSUMPTIONS, STATUS_LABELS, ordered_scenarios, scenario_row
from .schemas import RunResult, TaskPatch


DISPLAY_COLUMNS = {
    "rank": "运行费排名", "candidate_id": "方案", "name": "名称", "investment_yuan": "初始投资（元）",
    "operating_cost_yuan": "评估期运行费（元）", "emissions_kg": "评估期排放（kgCO2e）",
    "grid_kwh": "购电量（kWh）", "gas_kwh_lhv": "燃气（kWh_LHV）",
    "curtailed_pv_kwh": "弃光（kWh）", "constraints_passed": "全部约束通过",
    "supply_satisfied": "供能满足", "status": "求解状态", "reason": "说明",
    "solve_seconds": "求解时间（秒）", "mip_gap": "相对最优性间隙",
}


def _show_results(run: RunResult) -> None:
    st.subheader(f"评估结果 · 输入版本 {run.input_version}")
    st.caption(f"运行 ID：{run.run_id}　状态：{run.state.value}")
    st.caption(case_label(run.task))
    st.caption(" → ".join(state.value for state in run.states))
    if run.issues:
        st.error("输入尚未就绪，请补充或修正以下条件。")
        st.dataframe(pd.DataFrame([issue.model_dump() for issue in run.issues]), hide_index=True)
    if run.comparison and run.comparison.recommended_id:
        st.success(f"在本次评估的候选方案中，推荐 {run.comparison.recommended_id}。")
        st.write(run.comparison.explanation)
    elif run.scenarios:
        st.warning("在本次评估的候选方案中，没有通过全部约束的可行方案。")
    if run.scenarios:
        ranks = {name: i + 1 for i, name in enumerate(run.comparison.ranked_ids)} if run.comparison else {}
        rows = [scenario_row(s, ranks.get(s.candidate.candidate_id)) for s in ordered_scenarios(run)]
        frame = pd.DataFrame(rows)
        frame["status"] = frame["status"].map(STATUS_LABELS)
        columns = {**DISPLAY_COLUMNS, "rank": "NPV排名" if run.task.economics else "运行费排名", "emissions_kg": f"评估期排放（kg{run.task.emission_species}）"}
        st.dataframe(frame[list(columns)].rename(columns=columns), hide_index=True)
        st.caption("初始投资与购能费分列；NPV使用完整年现金流，运行排放不折现。" if run.task.economics else "投资与评估期运行费分列；不年化、不相加为生命周期成本。")
        if run.task.economics:
            economic_rows=[{"方案":s.candidate.candidate_id,"NPV成本 元":s.economics.npv_cost_yuan,"年度固定维护 元":s.economics.annual_fixed_om_yuan,"年度变动维护 元":s.economics.annual_variable_om_yuan,"规划期运行排放 kg":s.economics.horizon_operating_emissions_kg} for s in run.scenarios if s.economics]
            st.dataframe(pd.DataFrame(economic_rows),hide_index=True)
        failures = [s for s in run.scenarios if not s.validation.valid]
        if failures:
            with st.expander("不满足约束或未完成求解的方案", expanded=True):
                for scenario in failures:
                    st.write(f"**{scenario.candidate.candidate_id}：{STATUS_LABELS[scenario.dispatch.status]}**")
                    st.write(scenario.dispatch.message)
                    for reason in scenario.dispatch.reasons:
                        st.write(f"- {reason}")
                    if scenario.validation.checks:
                        st.dataframe(pd.DataFrame([c.model_dump() for c in scenario.validation.checks]), hide_index=True)
        solved = {s.candidate.candidate_id: s for s in ordered_scenarios(run) if s.dispatch.points}
        if solved:
            selected = st.selectbox("查看运行曲线", list(solved), key=f"curve_{run.run_id}")
            scenario = solved[selected]
            dispatch = pd.DataFrame([point.model_dump() for point in scenario.dispatch.points]).set_index("timestamp")
            st.write("电功率（kW）")
            electric = dispatch[["grid_kw", "pv_used_kw", "hp_electric_kw", "charge_kw", "discharge_kw"]].copy()
            if run.task.data is not None:
                electric["常规电负荷"] = run.task.data.electric_load_kw
            st.line_chart(electric.rename(columns={"grid_kw": "电网购电", "pv_used_kw": "光伏利用", "hp_electric_kw": "热泵用电", "charge_kw": "充电", "discharge_kw": "放电"}))
            if run.task.assessment_mode == "electric_only":
                st.caption("供热模块已停用，未核查热需求或供热保障；不绘制零热曲线暗示已满足供热。")
            else:
                st.write("热功率（kW_th）")
                heat = dispatch[["hp_heat_kw_th", "boiler_heat_kw_th"]].copy()
                if run.task.data is not None:
                    heat["热负荷"] = run.task.data.heat_load_kw_th
                st.line_chart(heat.rename(columns={"hp_heat_kw_th": "热泵供热", "boiler_heat_kw_th": "锅炉供热"}))
            if scenario.candidate.battery_energy_kwh > 0:
                st.write("电池边界状态（kWh；第 0 项为期初，第 N 项为期末）")
                st.line_chart(pd.DataFrame({"储能量": scenario.dispatch.soc_kwh}))
            with st.expander("独立约束检查"):
                st.dataframe(pd.DataFrame([c.model_dump() for c in scenario.validation.checks]), hide_index=True)
    if run.previous_run_id:
        from .comparability import basis_summary
        st.info(basis_summary(run))
        with st.expander("条件变更与前后差异（详细证据）", expanded=False):
            st.caption(f"前次运行：{run.previous_run_id}")
            st.json(run.changes)
    if run.files:
        st.subheader("下载评估结果")
        for key, label, mime in [
            ("json", "下载 JSON 完整结果", "application/json"),
            ("csv", "下载 CSV 方案对照", "text/csv"),
            ("markdown", "下载 Markdown 报告", "text/markdown"),
        ]:
            path = Path(run.files[key])
            st.download_button(label, path.read_bytes(), file_name=f"{run.run_id}_{path.name}", mime=mime, key=f"download_{key}")
        with st.expander("下载逐时运行 CSV"):
            for key, value in run.files.items():
                if key.startswith("dispatch_"):
                    path = Path(value)
                    st.download_button(f"下载 {key.removeprefix('dispatch_')} 逐时结果", path.read_bytes(), file_name=path.name, mime="text/csv", key=key)
    with st.expander("工具调用追溯"):
        st.dataframe(pd.DataFrame([call.model_dump() for call in run.tool_calls]), hide_index=True)


def main() -> None:
    st.set_page_config(page_title="区域综合能源低碳规划评估 Agent", layout="wide")
    st.title("区域综合能源低碳规划评估 Agent")
    st.write("v0.3.2 · 可接续对话 · 单供能节点 · 全年容量/有限候选 · 运行阶段排放")
    st.info("规则演示模式：支持预设任务和表单修改，可在没有模型密钥时完成评估；不具备任意自然语言理解能力。")
    workflow = st.radio("工作流程", ["合成演示", "外部数据导入（电侧）", "全年规划与Agent"], horizontal=True, key="workflow")
    if workflow == "全年规划与Agent":
        from .planning_ui import render_planning
        render_planning(_show_results)
        return
    if workflow == "外部数据导入（电侧）":
        from .import_ui import render_import
        render_import(_show_results)
        return
    if st.button("加载合成演示案例", key="load_demo"):
        st.session_state.task = make_demo_task()
        st.session_state.last_run = None
        st.session_state.applied_scale = 1.0
        for key in ("budget", "emission_enabled", "emission_limit", "demand_scale", "grid_limit", "pv_limit"):
            st.session_state.pop(key, None)
    if "task" not in st.session_state:
        st.write("加载固定随机种子的 168 小时合成案例后，可修改条件并运行完整评估。")
        return
    if st.session_state.pop("refresh_conditions", False):
        for key in ("budget", "emission_enabled", "emission_limit", "demand_scale", "grid_limit", "pv_limit"):
            st.session_state.pop(key, None)
    task = st.session_state.task
    constraints = task.constraints
    if constraints is None:
        st.error("缺少项目约束。请重新加载演示案例。")
        return
    st.warning("合成演示数据：价格、排放因子、设备费用均为演示假设，不代表当地现行参数。")
    with st.expander("数据来源与演示假设"):
        for source in task.sources:
            st.write(f"**{source.name}**（{source.source_id}）")
            st.json(source.model_dump(mode="json"))
        for assumption in ASSUMPTIONS:
            st.write(f"- {assumption}")
        if task.devices is not None:
            st.write("设备参数与投资假设")
            st.json(task.devices.model_dump())
    with st.form("conditions"):
        st.subheader("项目条件")
        left, right = st.columns(2)
        with left:
            budget = st.number_input("初始投资预算（元）", min_value=0.0, value=float(constraints.budget_yuan or 0), step=10000.0, key="budget")
            enabled = st.checkbox("启用评估期排放上限", value=constraints.emission_limit_kg is not None, key="emission_enabled")
            emission = st.number_input("评估期排放上限（kgCO2e）", min_value=0.0, value=float(constraints.emission_limit_kg if constraints.emission_limit_kg is not None else 10000), step=100.0, key="emission_limit")
        with right:
            current_scale = float(st.session_state.applied_scale)
            scale = st.number_input("电、热负荷倍数（相对原始演示）", min_value=min(0.1, current_scale), max_value=max(10.0, current_scale), value=current_scale, step=0.1, key="demand_scale")
            grid = st.number_input("电网购电功率上限（kW）", min_value=0.0, value=float(constraints.grid_limit_kw), step=10.0, key="grid_limit")
            pv = st.number_input("光伏场地装机上限（kW）", min_value=0.0, value=float(constraints.pv_limit_kw), step=10.0, key="pv_limit")
        submitted = st.form_submit_button("启动评估 / 修改后重新评估", key="evaluate")
    if submitted:
        previous = st.session_state.last_run
        emission_value = emission if enabled else None
        modified = (
            budget != constraints.budget_yuan or emission_value != constraints.emission_limit_kg
            or grid != constraints.grid_limit_kw or pv != constraints.pv_limit_kw
            or scale != st.session_state.applied_scale
        )
        with st.spinner("正在校验输入、求解候选并生成可追溯报告……"):
            try:
                if modified:
                    task = revise_task(task, TaskPatch(
                        budget_yuan=budget, emission_limit_kg=emission_value,
                        clear_emission_limit=not enabled, demand_scale=scale / st.session_state.applied_scale,
                        grid_limit_kw=grid, pv_limit_kw=pv,
                    ), parent_run_id=previous.run_id if previous else None)
                result = EnergyAgent(output_dir=Path(os.environ.get("ENERGY_AGENT_OUTPUT_DIR", "outputs"))).run(task, previous=previous)
            except (ValueError, OSError) as exc:
                st.error(f"评估未完成：{exc}")
            else:
                st.session_state.task = task
                st.session_state.applied_scale = scale
                st.session_state.last_run = result
    with st.expander("可选：自然语言修改参数"):
        st.caption("只有点击下方按钮才调用所配置的模型服务，可能产生费用；演示和表单评估不自动调用模型。模型仅转换结构化参数，数值结果仍由相同计算工具产生。真实模型接入需单独显式验收。")
        text = st.text_area("修改要求", placeholder="例如：将预算改为 800000 元，排放上限设为 6000 kgCO2e", key="natural_language")
        if st.button("调用已配置模型并重新评估", key="interpret"):
            from .llm import LLMError, get_llm_client

            if not text.strip():
                st.warning("请输入具体参数修改要求。")
            else:
                previous = st.session_state.last_run
                current_task = st.session_state.task
                if st.session_state.get("demo_last_nl_text") != text:
                    st.session_state.demo_nl_request_id = __import__("uuid").uuid4().hex
                    st.session_state.demo_last_nl_text = text
                try:
                    with st.spinner("正在解析结构化参数并重新计算……"):
                        result = EnergyAgent(output_dir=Path(os.environ.get("ENERGY_AGENT_OUTPUT_DIR", "outputs"))).run_text(
                            text, current_task, get_llm_client(), previous=previous,
                            request_id=st.session_state.setdefault("demo_nl_request_id", __import__("uuid").uuid4().hex),
                        )
                except (LLMError, ValueError, OSError) as exc:
                    st.error(f"自然语言修改未完成：{exc}")
                else:
                    st.session_state.task = result.task
                    st.session_state.last_run = result
                    # Widgets will initialize from the new task on the next rerun.
                    st.session_state.refresh_conditions = True
                    old_load = sum(current_task.data.electric_load_kw) if current_task.data else 0
                    new_load = sum(result.task.data.electric_load_kw) if result.task.data else 0
                    if old_load > 0:
                        st.session_state.applied_scale *= new_load / old_load
                    st.rerun()
    if st.session_state.last_run is not None:
        _show_results(st.session_state.last_run)


if __name__ == "__main__":
    main()
