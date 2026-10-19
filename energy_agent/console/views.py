"""Presentation of actual runs and bundled evidence, without backend mutations."""
from pathlib import Path

import pandas as pd
import streamlit as st

from ..comparability import basis_summary
from ..data import case_label
from ..peak_sensitivity import PeakStudyResult
from ..reporting import ordered_scenarios, scenario_row
from .components import empty, execution, metrics, number, safe, section, series_chart

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/v032_evidence'


def run_options() -> dict:
    """References to existing state; no copied runs or new persistence."""
    names = {'annual_run': '全年规划', 'last_run': '合成演示', 'real_run': '外部数据电侧'}
    return {key: f'{label} · v{run.input_version} · {run.run_id[:8]}'
            for key, label in names.items() if (run := st.session_state.get(key)) is not None}


def selected_run():
    options = run_options()
    if not options:
        return None
    key = st.selectbox('当前运行', list(options), format_func=options.get, key='console_run_key')
    return st.session_state[key]


def results(run) -> None:
    if run is None:
        metrics([('初始投资', None, '元'), ('评估期运行费', None, '元'),
                 ('NPV 成本', None, '元'), ('运行阶段排放', None, 'kg · 物质依任务确定')])
        empty('尚无运行结果。请在“准备评估条件”中加载案例，确认条件后主动启动评估。')
        return
    execution(run)
    st.caption(case_label(run.task))
    if run.task.case_context:
        st.caption('服务边界：' + run.task.case_context.boundary)
    if run.issues:
        st.error('输入未就绪，未形成可用规划结论。')
        st.dataframe(pd.DataFrame([i.model_dump() for i in run.issues]), hide_index=True)
    recommended = run.comparison.recommended_id if run.comparison else None
    scenario = next((s for s in run.scenarios if s.candidate.candidate_id == recommended), None)
    if scenario:
        st.success(run.comparison.explanation)
        m = scenario.validation.metrics
        metrics([('初始投资', scenario.investment_yuan, '元'),
                 ('年度购能费' if run.task.resolution == 'full_year' else '评估期运行费', m.operating_cost_yuan if m else None, '元'),
                 ('NPV 成本', scenario.economics.npv_cost_yuan if scenario.economics else '未启用', '元 · 按任务规划期' if scenario.economics else '当前任务未启用全年经济评价'),
                 ('年度运行排放' if run.task.resolution == 'full_year' else '评估期运行排放', m.emissions_kg if m else None, f'kg{run.task.emission_species}')])
    elif run.scenarios:
        st.warning('本次评估没有通过全部约束的推荐方案。未找到解不等于已证明不可行，请查看各方案求解状态。')
    if run.previous_run_id:
        st.info(basis_summary(run))
        with st.expander('前后差异与比较口径证据'):
            st.caption('基准 run_id：' + run.previous_run_id)
            st.json(run.changes)
    section('配置对照', '求解状态与独立校验分别展示；未证明最优的解保留状态说明')
    cards = []
    for s in ordered_scenarios(run):
        c, d = s.candidate, s.dispatch
        status = {'optimal': '已证明最优', 'feasible_limit': '可行解 · 未证明最优',
                  'no_solution_limit': '达到限制 · 未找到解', 'infeasible': '求解无解',
                  'rejected': '预检查不通过', 'error': '求解错误', 'invalid': '校验不通过'}.get(d.status, d.status)
        context = '当前容量模型内' if run.task.planning_mode == 'capacity' else '该候选运行'
        cards.append(f'<article class="rea-card"><span class="rea-badge {"good" if s.validation.valid else "warn"}">'
                     f'{safe(status)} · {safe(context)}</span><h3>{safe(c.name)}</h3>'
                     f'<p>独立校验：{"通过" if s.validation.valid else "未通过"}</p>'
                     f'<p>光伏 {number(c.pv_kw)} kW<br>储能 {number(c.battery_power_kw)} kW / {number(c.battery_energy_kwh)} kWh'
                     f'<br>热泵 {number(c.hp_kw_th)} / 锅炉 {number(c.boiler_kw_th)} kW_th</p>'
                     f'<p>初投 {number(s.investment_yuan)} 元 · 相对间隙 {number(d.mip_gap, 4) if d.mip_gap is not None else "未提供"}<br>'
                     f'求解 {number(d.solve_seconds)} 秒</p></article>')
    if cards:
        st.html('<div class="rea-grid">' + ''.join(cards) + '</div>')
        labels = {'candidate_id': '方案', 'investment_yuan': '初投 元', 'operating_cost_yuan': '评估期运行费 元',
                  'npv_cost_yuan': 'NPV 元', 'emissions_kg': f'运行排放 kg{run.task.emission_species}',
                  'grid_kwh': '购电 kWh', 'gas_kwh_lhv': '燃气 kWh_LHV', 'curtailed_pv_kwh': '弃光 kWh',
                  'supply_satisfied': '供能满足', 'constraints_passed': '独立校验', 'reason': '求解说明'}
        frame = pd.DataFrame([scenario_row(s) for s in ordered_scenarios(run)])
        st.dataframe(frame[list(labels)].rename(columns=labels), hide_index=True, width='stretch')
    failed = [s for s in run.scenarios if not s.validation.valid]
    if failed:
        with st.expander('不满足约束 / 未完成求解', expanded=True):
            for s in failed:
                st.write(s.candidate.name + '：' + s.dispatch.message)
                for reason in s.dispatch.reasons:
                    st.write(reason)
                st.caption('仅列已执行的检查与求解器证据；没有冲突诊断时不推断唯一原因。')
    solved = {s.candidate.candidate_id: s for s in ordered_scenarios(run) if s.dispatch.points}
    if not solved:
        return
    section('能源运行曲线', '实际逐时计算值 · 可拖选区间，不将短期结果年化')
    key = st.selectbox('曲线方案', list(solved), key='console_curve_' + run.run_id)
    s = solved[key]
    frame = pd.DataFrame([p.model_dump() for p in s.dispatch.points]).set_index('timestamp')
    electric = frame[['grid_kw', 'pv_used_kw', 'charge_kw', 'discharge_kw', 'hp_electric_kw']].rename(columns={
        'grid_kw': '电网购电', 'pv_used_kw': '光伏利用', 'charge_kw': '电池充电', 'discharge_kw': '电池放电', 'hp_electric_kw': '热泵用电'})
    if run.task.data:
        electric['常规电负荷'] = run.task.data.electric_load_kw
    series_chart(electric, '电功率 kW', 'console_electric_' + run.run_id)
    if run.task.assessment_mode == 'electric_only':
        st.info('电侧评估：供热模块停用。未核查热需求，不代表建筑没有供热需求或供热已获保障。')
    else:
        heat = frame[['hp_heat_kw_th', 'boiler_heat_kw_th']].rename(columns={'hp_heat_kw_th': '热泵供热', 'boiler_heat_kw_th': '锅炉供热'})
        if run.task.data:
            heat['热负荷'] = run.task.data.heat_load_kw_th
        series_chart(heat, '热功率 kW_th', 'console_heat_' + run.run_id)
    if s.candidate.battery_energy_kwh:
        with st.expander('电池边界状态（N+1）'):
            st.caption('第0项为期初，第N项为期末；所有状态来自求解器。')
            st.dataframe(pd.DataFrame({'区间边界': range(len(s.dispatch.soc_kwh)), '储能量 kWh': s.dispatch.soc_kwh}), hide_index=True)


def conversation_snapshot(reply) -> None:
    """Only the stored current request; do not fabricate a chat transcript."""
    if reply is None:
        empty('尚无对话记录。先确认任务，再使用下方现有助手提交要求。含糊条件会先澄清，不会自动求解。')
        return
    st.caption(f'当前请求快照 · request_id：{reply.request_id} · 状态：{reply.status}（非完整历史聊天记录）')
    if reply.pending:
        with st.chat_message('user'):
            st.write(reply.pending.original_request)
        for answer in reply.pending.answers:
            with st.chat_message('user'):
                st.write(answer['text'])
        st.caption(f'确认基准：{reply.pending.base_run_id} · v{reply.pending.input_version}')
    with st.chat_message('assistant'):
        st.write(reply.text)
    if reply.contract:
        from ..conversation import contract_brief
        brief = contract_brief(reply.contract)
        with st.container(border=True):
            st.write('准备修改 / 已执行修改（以请求状态为准）')
            st.write('；'.join(brief['changes']) or '尚需澄清，未生成可执行修改。')
            st.caption(brief['preserves'])
    if reply.run:
        st.caption(f'结果 run_id：{reply.run.run_id} · 数值引用核对：{reply.explanation_verified}')


def experiment() -> None:
    section('8760 小时 · 峰值假设敏感性', '真实归档证据 / 离线读取 / 本页面未重新求解')
    st.info('以下为已归档的确定性求解结果，不是实时模型输出。替代值是研究假设，不认定原始峰值错误，也不称为校准实测。')
    path = EVIDENCE / 'peak_study.json'
    if not path.is_file():
        empty('本机没有归档实验文件，请在原版全年规划入口导入实验记录。')
        return
    try:
        record = PeakStudyResult.model_validate_json(path.read_bytes())
    except ValueError as exc:
        st.error('实验记录格式无法校验：' + str(exc))
        return
    st.write(record.conclusion)
    labels = {'label': '情景', 'annual_electric_kwh': '年电量 kWh', 'peak_kw': '峰值 kW',
              'investment_yuan': '初投 元', 'npv_cost_yuan': 'NPV 元', 'annual_emissions_kg': '年运行排放 kgCO2e',
              'feasible': '可行', 'status': '求解状态', 'mip_gap': '间隙', 'solve_seconds': '求解 秒'}
    frame = pd.DataFrame(record.scenarios)
    st.dataframe(frame[list(labels)].rename(columns=labels), hide_index=True, width='stretch')
    st.warning('比较口径C：负荷电量发生变化。成本与排放差值包含电量变化，不能全部归因于设备配置改善。各情景保持相同的预算、容量边界及其他控制条件。')
    with st.expander('容量、修改点、父文件哈希与独立校验'):
        capacities = {'label': '情景', 'pv_kw': '光伏 kW', 'battery_power_kw': '电池 kW', 'battery_energy_kwh': '电池 kWh', 'hp_kw_th': '热泵 kW_th', 'boiler_kw_th': '锅炉 kW_th'}
        st.dataframe(frame[list(capacities)].rename(columns=capacities), hide_index=True)
        st.json(record.model_dump(mode='json'))
    for name, label in [('peak_report.md', '中文实验报告'), ('peak_study.json', '机器可读实验记录'), ('peak_scenarios.csv', '实验对照CSV')]:
        path = EVIDENCE / name
        if path.is_file():
            st.download_button('下载' + label, path.read_bytes(), file_name=name, key='console_peak_' + name)


def evidence(run) -> None:
    section('来源与计算证据', '实测、估算与人为假设分别标注')
    if run is None:
        empty('尚无当前运行证据。请先完成评估；归档峰值实验位于“实验验证”页。')
        return
    st.caption(f'本页所有证据绑定 run_id：{run.run_id} · v{run.input_version}')
    st.info(case_label(run.task))
    if run.task.case_context:
        st.write('用能边界：' + run.task.case_context.boundary)
        with st.expander('质量摘要、假设与未覆盖内容'):
            st.write(run.task.case_context.model_dump(mode='json'))
    else:
        st.write('合成案例：价格、排放因子、设备费用为演示假设，不代表当地现行参数。')
    st.caption('运行阶段排放不含设备隐含排放；有限候选不等于完整容量空间的全局最优；本界面不构成工程投资决策。')
    categories = {'measured': '实测', 'estimated': '模型估算', 'simulated': '仿真', 'synthetic': '合成', 'assumption': '人为假设', 'user': '用户提供', 'unknown': '未知'}
    for source in run.task.sources:
        with st.expander(source.name + ' · ' + categories.get(source.category, source.category)):
            st.write('地区：' + source.region + ' · 时段：' + source.time_range)
            st.write('使用条件：' + str(source.conditions))
            st.json(source.model_dump(mode='json'))
    section('独立校验', '未通过的检查保留原始误差与容差')
    for s in run.scenarios:
        with st.expander(s.candidate.name + (' · 通过' if s.validation.valid else ' · 未通过')):
            st.dataframe(pd.DataFrame([c.model_dump() for c in s.validation.checks]), hide_index=True)
    section('导出结果', '下载内容来自当前运行文件；不伪造缺失的本机产物')
    st.download_button('下载当前运行 JSON', run.model_dump_json(indent=2), file_name=run.run_id + '_result.json', key='console_result_json')
    for key, label in [('csv', '方案对照 CSV'), ('markdown', '评估报告 Markdown')]:
        path = Path(run.files[key]) if run.files.get(key) else None
        if path and path.is_file():
            st.download_button('下载' + label, path.read_bytes(), file_name=run.run_id + '_' + path.name, key='console_result_' + key)
        else:
            st.caption(label + '：原导出文件不在当前机器，请重算生成。')
    with st.expander('结构化输入、工具调用与完整结果'):
        st.dataframe(pd.DataFrame([c.model_dump() for c in run.tool_calls]), hide_index=True)
        st.json(run.model_dump(mode='json', exclude={'scenarios', 'task'}))
        st.caption('完整逐时数组与输入来源请下载JSON，避免首页堆积技术细节。')
