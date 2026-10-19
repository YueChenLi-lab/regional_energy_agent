"""Opt-in synthetic demos: loading, rerendering and downloads never solve."""
import os
from pathlib import Path
from uuid import uuid4

import streamlit as st

from .decision_demos import demo_task, run_decision_demo


def render_decision_demo(kind):
    label = '反事实修复' if kind == 'repair' else '多情景决策'
    prefix = 'decision_demo_' + kind
    with st.expander(f'{label} · 可运行的24小时合成演示', expanded=False):
        st.caption('合成演示数据 · 固定种子42 · 非真实工程。先加载，再明确确认并运行；无需模型密钥，不改写当前项目。')
        if st.button(f'加载{label}演示数据', key=prefix+'_load'):
            st.session_state[prefix+'_request_id'] = 'demo-' + uuid4().hex
            st.session_state.pop(prefix+'_result', None)
            st.session_state[prefix+'_confirm'] = False
        if prefix+'_request_id' not in st.session_state:
            st.caption('待执行：加载后可查看输入及授权范围。')
            return
        task = demo_task(kind)
        st.write(f'24个逐小时区间；新建项目投资口径；{len(task.candidates)}种固定候选；只统计该24小时，不折算全年。')
        if kind == 'repair':
            st.write('电负荷10kW、热负荷20kW_th。基准：预算6万元、运行排放上限230kgCO2e、购电上限12kW。')
            st.write('三条替代路径分别搜索：预算6万→60万元（精度1000元）；排放230→300kgCO2e（精度0.05）；购电12→25kW（精度0.01）。每次只改一项，供热、时段和其余输入保持。')
            st.caption('先求解独立基准（最多3次、每次3秒），再复核与搜索（最多128次、每次3秒、共享60秒）。不确定状态不当作不可行。')
        else:
            st.write('使用A/B/C三种固定配置，实际计算3×4矩阵：基准、购电价格×1.2、燃气价格×1.2、光伏出力×0.8。负荷、供热、时段、约束及配置保持。')
            st.caption('价格与设备参数均为演示假设；无未来预测。比较24小时购能费，投资另列，不计算NPV。先求解基准（最多3次、每次3秒），矩阵最多12次、每次3秒、共享45秒。')
        with st.expander('查看演示负荷、容量、来源与全部假设'):
            st.dataframe([c.model_dump(exclude={'source_id'}) for c in task.candidates], hide_index=True, width='stretch')
            st.line_chart({'电负荷 kW': task.data.electric_load_kw, '热负荷 kW_th': task.data.heat_load_kw_th})
            st.json(task.model_dump(mode='json'))
        st.download_button('下载合成演示输入JSON', task.model_dump_json(indent=2),
            file_name=f'{kind}_24h_synthetic_input.json', mime='application/json', key=prefix+'_input')
        confirmed = st.checkbox('确认仅对上述合成数据执行所列搜索/情景，不采用到当前项目', key=prefix+'_confirm')
        if st.button(f'确认并运行{label}合成演示', disabled=not confirmed, key=prefix+'_run', type='primary'):
            try:
                with st.spinner('真实求解与独立校验中；不调用模型……'):
                    st.session_state[prefix+'_result'] = run_decision_demo(kind,
                        Path(os.getenv('ENERGY_AGENT_OUTPUT_DIR', 'outputs')) / 'decision_demos',
                        st.session_state[prefix+'_request_id'])
            except (ValueError, OSError) as exc:
                st.error(f'演示未完成：{exc}')
        pair = st.session_state.get(prefix+'_result')
        if pair is None:
            st.caption('待执行：此处没有预置计算结果。')
            return
        baseline, result = pair
        st.caption(f'合成演示基准 run_id={baseline.run_id} · v{baseline.input_version}；结果仅属于此演示，未采用。')
        if kind == 'repair':
            from .console.decision_components import repair_board
            st.write('基准复核：'+{'infeasible':'已确认不可行', 'feasible':'已确认可行'}.get(
                result.baseline_verification.feasibility, '尚未确定可行性'))
            repair_board(result)  # deliberately no adoption callback in demo
            for key, title in [('json', 'JSON'), ('markdown', '中文Markdown报告')]:
                p = Path(result.files[key])
                st.download_button('下载演示反事实'+title, p.read_bytes(), file_name=p.name, key=prefix+'_dl_'+key)
            with st.expander('完整搜索与独立校验证据'):
                st.json(result.model_dump(mode='json'))
        else:
            from .console.decision_components import regret_board
            regret_board(result, key_prefix=prefix)
