"""Chinese import/quality workflow. No network is requested during evaluation."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import numpy as np
import pandas as pd
import streamlit as st

from .adapters import ImportQualityError, MeterSelection, fetch_energydetective, fetch_zenodo_energydetective, import_energydetective
from .agent import EnergyAgent
from .data import case_label
from .real_case import ElectricCaseParameters, PricePeriod, TariffSettings, build_electric_task, export_import
from .solar import SolarSettings, load_nasa_pv


def render_import(show_results):
    st.subheader("实测数据导入与电侧评估")
    st.info("导入后区分实测与假设混合案例、人工格式样本。仅所选Q/W计量边界；价格、排放、设备成本和场地未经核实，不代表真实工程投资决策。")
    cache = Path(os.environ.get("ENERGY_AGENT_DATA_CACHE", "data_cache/raw"))
    output = Path(os.environ.get("ENERGY_AGENT_OUTPUT_DIR", "outputs"))
    st.selectbox("数据来源", ["EnergyDetective 发布方逐小时CSV（已实现）"], key="real_source")
    provider = st.selectbox("获取渠道", ["zenodo", "github"], format_func=lambda x: "Zenodo 6590976 正式档案（26MB，CC BY 4.0）" if x == "zenodo" else "发布方GitHub固定版本（未单独声明许可）",key="real_provider")
    fetcher = fetch_zenodo_energydetective if provider == "zenodo" else fetch_energydetective
    dataset = st.selectbox("发布文件", ["test", "reference"], format_func=lambda x: "匿名测试办公楼（2017）" if x == "test" else "参考办公楼（BuildingID）", key="real_dataset")
    st.caption("Zenodo正式档案已核实CC BY 4.0，使用派生数据需署名、链接许可并说明处理。GitHub未单独声明许可。网络获取需要显式点击，原文件保存于本地忽略缓存。")
    if st.button("获取发布方原文件和说明到本地缓存", key="real_fetch"):
        try:
            with st.spinner("读取固定发布版本，不执行评估……"):
                fetcher(dataset, cache, offline=False)
        except (OSError, ValueError, httpx.HTTPError) as exc:
            st.error(f"获取未完成：{exc}。可上传已取得的原文件，或离线使用完整缓存。")
        else:
            st.success("原文件和SHA-256来源清单已缓存；后续评估可离线运行。")
    uploaded = st.file_uploader("或上传发布方原始CSV（不接受未说明格式）", type="csv", key="real_upload")
    artifact = documentation = None
    path = None
    if uploaded is not None:
        content = uploaded.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        path = cache / "uploads" / f"{digest}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        elif path.read_bytes() != content:
            st.error("上传缓存校验不符。")
            return
    else:
        try:
            path, artifact, documentation = fetcher(dataset, cache, offline=True)
        except (OSError, ValueError) as exc:
            st.caption(f"本地暂无可用文件：{exc}")
    if path is None:
        return
    try:
        raw = pd.read_csv(path)
        buildings = sorted(raw.BuildingID.astype(str).unique()) if "BuildingID" in raw else ["test"]
    except (OSError, ValueError) as exc:
        st.error(f"CSV读取失败：{exc}")
        return
    st.caption(f"原文件 {len(raw):,} 行。以下预览保留历史日期；文件名不作为时间、单位或计量边界的证据。")
    st.dataframe(raw.head(8), hide_index=True)
    with st.form("real_selection"):
        building = st.selectbox("建筑", buildings, key="real_building")
        kind = st.selectbox("文件性质声明", ["发布方实际文件", "人工格式测试样本（非实测）"], key="real_kind")
        meters = st.selectbox("计量边界", ["Q", "W", "Q,W"], format_func=lambda x: {"Q":"Q：照明插座", "W":"W：暖通用电（不是热量）", "Q,W":"Q与W发布方类别合计（不称全楼总电量）"}[x], key="real_meters")
        boundary_ack = st.checkbox("确认只比较上述类别边界；Q+W不代表已核实回路完整或无重叠", key="real_boundary_ack")
        anchor = st.selectbox("原时间的区间含义（发布说明未明确，必须显式选择假设）", ["未确认", "假设区间起点", "假设区间终点"], key="real_anchor")
        time_ack = st.checkbox("确认采用Asia/Shanghai与所选起止假设；未冒充发布方已证实", key="real_time_ack")
        start = st.text_input("评估起点（北京时间ISO日期；留空优先选择完整连续窗口）", key="real_start")
        hours = st.number_input("窗口小时数", min_value=1, max_value=8784, value=168, step=1, key="real_hours")
        preview = st.form_submit_button("校验并预览导入", key="real_preview")
    if preview:
        st.session_state.pop("real_load", None)
        st.session_state.pop("real_run", None)
        if anchor == "未确认" or not time_ack:
            st.error("请先声明原时间区间含义并确认时区假设。")
        else:
            try:
                selection = MeterSelection(building=building, meters=meters.split(","),
                    timestamp_position="start" if anchor == "假设区间起点" else "end",
                    acknowledge_category_sum=boundary_ack, timestamp_assumption_acknowledged=time_ack,
                    data_kind="artificial_fixture" if kind != "发布方实际文件" else "published")
                load = import_energydetective(path, selection, start=start or None, hours=int(hours), artifact=artifact, documentation=documentation)
            except (ValueError, OSError) as exc:
                st.error(f"导入未通过，未启动优化：{exc}")
                if isinstance(exc, ImportQualityError):
                    text = "\n\n".join(r.markdown() for r in exc.reports)
                    st.download_button("下载失败数据质量报告", text, file_name="quality_failed.md", key="real_failed_quality")
                    with st.expander("失败质量详情JSON"):
                        st.json([r.model_dump() for r in exc.reports])
            else:
                st.session_state.real_load = load
                st.session_state.real_file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                for key in ("real_grid", "real_site"):
                    st.session_state.pop(key, None)
    load = st.session_state.get("real_load")
    if load is None:
        st.write("选择窗口并通过质量校验后，才可进入参数确认与评估。")
        return
    if hashlib.sha256(path.read_bytes()).hexdigest() != st.session_state.get("real_file_hash"):
        st.warning("原文件已改变，请重新校验导入；旧预览不能用于新文件。")
        return
    st.success(f"当前已验证窗口：{load.frame.timestamp.iloc[0].isoformat()}起，{len(load.frame)}小时。以下评估使用此窗口。")
    st.write(load.boundary)
    st.warning("不建模供热：零热数组只为停用占位，不表示没有供热需求或已保障供热；选中的W仍完整保留为电负荷。")
    st.dataframe(load.frame.head(24).rename(columns={"timestamp":"区间起点（北京时间）", "electric_load_kw":"计量边界用电（kW）"}), hide_index=True)
    summary = [{"范围":r.scope, "记录数":r.records, "缺失":r.missing_records, "重复":r.duplicate_records,
        "非法/非有限":r.nonfinite_values+r.missing_values, "负值":r.negative_values, "跳变":r.jump_count, "通过":r.valid} for r in load.selected_reports]
    st.dataframe(pd.DataFrame(summary), hide_index=True)
    st.write(f"能量核对：原始 {load.audit.raw_energy_kwh:.8f} kWh → 转换 {load.audit.normalized_energy_kwh:.8f} kWh；差值 {load.audit.difference_kwh:.4g} kWh，容差 {load.audit.tolerance_kwh:g} kWh。")
    st.caption(load.audit.explanation)
    quality_md = "\n\n".join(r.markdown() for r in load.selected_reports + load.whole_reports)
    quality_json = json.dumps({"selected_window":[r.model_dump() for r in load.selected_reports], "whole_file":[r.model_dump() for r in load.whole_reports], "energy_audit":load.audit.model_dump()},ensure_ascii=False,indent=2)
    st.download_button("下载数据质量报告（中文）", quality_md, file_name="quality.md", key="real_quality_md")
    st.download_button("下载数据质量报告（JSON）", quality_json, file_name="quality.json", key="real_quality_json")
    st.download_button("下载已导入电负荷CSV", load.frame.to_csv(index=False), file_name="electric_load.csv", key="real_load_csv")
    with st.expander("整份原文件质量、来源和详细JSON（窗外异常仍完整报告）"):
        st.dataframe(pd.DataFrame([{"范围":r.scope, "记录数":r.records, "缺失":r.missing_records, "重复":r.duplicate_records, "跳变":r.jump_count, "通过":r.valid} for r in load.whole_reports]), hide_index=True)
        st.json(load.source.model_dump(mode="json"))
        st.json(json.loads(quality_json))
    st.subheader("填写与确认仍缺少的项目参数")
    st.caption("费用仅为按电量收费的部分，未计基本电费/需量费；新增设备成本与场地容量均是假设。排放常数不是实测逐时碳强度，不自动把CO₂改称CO₂e。")
    acknowledged = st.checkbox("确认下列价格、排放、成本和容量为我设置的情景假设，非当地现行或工程已核实参数", key="real_assumptions_ack")
    with st.expander("光伏资源与安装假设（可选；评估仅离线读取缓存）"):
        lat = st.number_input("代表点纬度（不是匿名楼宇精确坐标）", -90.0, 90.0, 31.23, key="real_lat")
        lon = st.number_input("代表点经度", -180.0, 180.0, 121.47, key="real_lon")
        tilt = st.number_input("光伏倾角（度）", 0.0, 90.0, 20.0, key="real_tilt")
        azimuth = st.number_input("朝向（北0、南180，度）", 0.0, 360.0, 180.0, key="real_azimuth")
        losses = st.number_input("系统损耗比例", 0.0, 1.0, 0.14, key="real_losses")
        solar = SolarSettings(latitude=lat, longitude=lon, tilt_degrees=tilt, azimuth_degrees=azimuth, system_loss_fraction=losses)
        if st.button("显式获取同期NASA资源缓存", key="real_nasa_fetch"):
            try:
                load_nasa_pv(load.frame.timestamp, solar, cache_dir=cache, offline=False)
            except (OSError, ValueError, httpx.HTTPError) as exc:
                st.error(f"NASA资源未完成：{exc}；仍可进行电网与储能评估，不使用合成光伏替代。")
            else:
                st.success("NASA UTC响应及估算已校验，可离线重放；光伏是模型估算而非实测。")
    with st.form("real_parameters"):
        peak = float(load.frame.electric_load_kw.max())
        budget = st.number_input("新增设备投资预算（元）", min_value=0.0, value=3000000.0, key="real_budget")
        grid = st.number_input("电网购电上限（kW，默认峰值×1.1向上取整假设）", min_value=0.0, value=float(np.ceil(peak*1.1/10)*10), key="real_grid")
        site = st.number_input("光伏可安装上限（kW_DC，需现场核实）", min_value=0.0, value=float(np.ceil(peak*0.5/10)*10), key="real_site")
        low = st.number_input("假设谷价00–07（元/kWh）", min_value=0.0, value=0.38, key="real_price_low")
        normal = st.number_input("假设平价07–17、22–24（元/kWh）", min_value=0.0, value=0.72, key="real_price_normal")
        high = st.number_input("假设峰价17–22（元/kWh）", min_value=0.0, value=1.15, key="real_price_high")
        species = st.selectbox("排放核算物质（必须与因子一致）", ["CO2e", "CO2"], key="real_species")
        factor = st.number_input("人工情景排放因子（kg所选物质/kWh）", min_value=0.0, value=0.55, key="real_factor")
        carbon_on = st.checkbox("启用评估期排放约束", key="real_carbon_on")
        carbon_limit = st.number_input("排放上限（kg所选物质）", min_value=0.0, value=100000.0, key="real_carbon_limit")
        pv_cost = st.number_input("光伏单位成本（元/kW_DC）", min_value=0.0, value=3200.0, key="real_pv_cost")
        battery_cost = st.number_input("电池能量成本（元/kWh）", min_value=0.0, value=900.0, key="real_battery_cost")
        power_cost = st.number_input("电池功率成本（元/kW）", min_value=0.0, value=450.0, key="real_power_cost")
        fraction = st.number_input("电池功率/实测峰值（情景定容）", min_value=0.01, max_value=2.0, value=0.25, key="real_power_fraction")
        duration = st.number_input("电池时长（h）", min_value=0.1, max_value=24.0, value=2.0, key="real_duration")
        use_solar = st.checkbox("启用已缓存NASA估算光伏；缓存不可用时仅保留电网/储能并报告未完成", key="real_use_solar")
        evaluate = st.form_submit_button("评估已验证的电侧案例 / 修改预算后重新计算", key="real_evaluate", disabled=not acknowledged)
    if evaluate:
        try:
            tariff = TariffSettings(periods=[PricePeriod(start_hour=0,end_hour=7,yuan_per_kwh=low), PricePeriod(start_hour=7,end_hour=17,yuan_per_kwh=normal), PricePeriod(start_hour=17,end_hour=22,yuan_per_kwh=high), PricePeriod(start_hour=22,end_hour=24,yuan_per_kwh=normal)])
            params = ElectricCaseParameters(budget_yuan=budget, grid_limit_kw=grid, pv_limit_kw=site, tariff=tariff,
                emission_factor=factor, emission_species=species, emission_limit_kg=carbon_limit if carbon_on else None,
                pv_cost_per_kw=pv_cost, battery_cost_per_kwh=battery_cost, battery_power_cost_per_kw=power_cost,
                battery_power_fraction_of_peak=fraction, battery_duration_hours=duration, include_solar=use_solar, solar=solar)
            task = build_electric_task(load, params, cache_dir=cache, offline=True)
            previous = st.session_state.get("real_run")
            if previous:
                task.version = previous.input_version + 1
                task.parent_run_id = previous.run_id
            export_import(load, task, output/"imports"/uuid4().hex)
            with st.spinner("校验电侧任务、实际求解并导出报告……"):
                run = EnergyAgent(output/"real_runs").run(task, previous=previous)
        except (OSError, ValueError) as exc:
            st.error(f"电侧评估未完成：{exc}")
        else:
            st.session_state.real_run = run
    run = st.session_state.get("real_run")
    if run:
        st.warning(case_label(run.task) + "；仅当前已验证计量窗口，人工样本不能代替真实数据验收。")
        for pending in run.task.case_context.pending:
            st.caption(pending)
        show_results(run)
        normalized = Path(run.task.case_context.import_files["normalized_csv"])
        st.download_button("下载完整统一格式数据CSV", normalized.read_bytes(), file_name="normalized.csv", key="real_normalized")
