"""Opt-in repair form; rendering and refresh never run an optimizer or model."""
import os
from pathlib import Path
from uuid import uuid4

import streamlit as st

from .agent import ToolRegistry
from .counterfactual import (CounterfactualRequest, NAMES, RepairRange, adopt_counterfactual_path,
                            clarify_repair_request, counterfactual_enabled, data_fingerprint, unit_for)


def render_counterfactual(run, on_adopt=None):
    with st.expander('反事实约束修复', expanded=False):
        if not counterfactual_enabled():
            st.caption('反事实约束修复已关闭，原有规划流程可继续使用。')
            return
        st.caption('显式执行才搜索；三条路径分别调整一个上限，其余负荷、时段、服务和输入保持。未采用前不改写已确认任务。')
        if run is None:
            st.write('待执行：请先完成一次规划评估。')
            return
        suffix = run.run_id
        st.caption(f'固定基准 {suffix} · v{run.input_version}')
        text = st.text_input('修复问题（可选，仅支持下列预设问句的离线路由）', key='cf_question_'+suffix,
                             placeholder='预算不够，那至少还差多少？')
        with st.expander('受限问句与路径建议（不调用模型，不视为授权）'):
            st.write('预算不够，那至少还差多少？ / 预算不能增加，碳约束可以放宽多少？ / 保持供热不变，还有什么可行的调整？ / 给我三条可以比较的修复路径。')
            if text:
                guidance = clarify_repair_request(text, run)
                st.write(guidance.clarification)
                st.caption('建议路径：' + '、'.join(NAMES[f] for f in guidance.requested_fields))
                st.caption('应锁定：' + '、'.join(NAMES[f] for f in guidance.locked_fields))
        guidance = clarify_repair_request(text, run) if text else None
        forbidden = set(guidance.locked_fields if guidance else [])
        available = [f for f in NAMES if getattr(run.task.constraints, f) is not None and f not in forbidden]
        with st.form('cf_form_'+suffix):
            request_id = st.text_input('修复请求ID（重试保持相同；修改搜索参数请用新ID）', value=uuid4().hex, key='cf_request_'+suffix)
            parent = st.text_input('原对话请求ID（如有，保留追溯绑定）', value=st.session_state.get('annual_request_id',''), key='cf_parent_'+suffix)
            allowed = st.multiselect('明确允许修改的上限（未选中即锁定）', available, format_func=NAMES.get, key='cf_allowed_'+suffix)
            locked = st.multiselect('额外锁定约束', list(NAMES), format_func=NAMES.get, default=list(forbidden), key='cf_locked_'+suffix)
            if run.task.constraints.emission_limit_kg is None:
                st.caption('原任务未设排放上限，本轮不能搜索排放放宽路径。')
            if run.task.assessment_mode == 'electric_only':
                st.warning('当前为电侧模式：保持的是已声明电侧服务；不声称供热已建模或得到保障。')
            st.caption('自动保持：电热负荷、逐时时段/步长、禁止缺供、候选集/容量边界、设备/经济/价格/资源及来源。')
            ranges = {}
            for field in available:
                origin = getattr(run.task.constraints,field)
                unit = unit_for(run.task,field)
                st.write(f'{NAMES[field]}：基准 {origin:g} {unit}')
                a, b = st.columns(2)
                upper = a.number_input('允许的绝对上界 '+unit, min_value=float(origin), value=float(origin+max(origin*.5,1000 if field!='grid_limit_kw' else 10)), key='cf_upper_'+field+suffix)
                precision = b.number_input('边界精度 '+unit, min_value=.000001, value=float(max((upper-origin)/100,.01)), key='cf_precision_'+field+suffix)
                ranges[field] = RepairRange(lower=origin, upper=upper, precision=precision, unit=unit)
            explore = st.checkbox('即使基准尚未确认不可行，也显式探索替代条件', key='cf_explore_'+suffix)
            a,b,c = st.columns(3)
            seconds = a.number_input('单次求解时限 秒', min_value=.1, max_value=30., value=3., key='cf_single_'+suffix)
            calls = b.number_input('总求解适配器调用上限', min_value=1, max_value=96, value=48, key='cf_calls_'+suffix)
            total = c.number_input('总时间预算 秒', min_value=1., max_value=120., value=30., key='cf_total_'+suffix)
            if run.task.resolution == 'full_year':
                annual_ack = st.checkbox('确认主动进行8760/8784小时重计算，已了解云端资源限制；建议优先离线CLI', key='cf_annual_ack_'+suffix)
            else:
                annual_ack = True
            submitted = st.form_submit_button('执行授权的反事实搜索', key='cf_search_'+suffix, disabled=not annual_ack)
        if submitted:
            try:
                if guidance and not guidance.recognized:
                    raise ValueError(guidance.clarification)
                request = CounterfactualRequest(baseline=run, base_run_id=run.run_id, input_version=run.input_version,
                    request_id=request_id, parent_request_id=parent or None, original_request=text,
                    data_fingerprint=data_fingerprint(run.task), allowed_fields=allowed,
                    locked_conditions=list(set(locked)|forbidden|{'electric_load','heat_load','period','service'}),
                    ranges={f:ranges[f] for f in allowed}, explore_alternatives=explore,
                    single_solve_seconds=seconds, max_solver_calls=calls, total_seconds=total,
                    output_dir=str(Path(os.getenv('ENERGY_AGENT_OUTPUT_DIR','outputs'))/'counterfactual'))
                with st.spinner('复核原任务，按预算搜索并独立校验……'):
                    result = ToolRegistry().call('search_counterfactual_repairs', request)
                st.session_state['cf_result_'+suffix] = result
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        result = st.session_state.get('cf_result_'+suffix)
        from .console.decision_components import repair_board
        def adopt_card(path_vm):
            if on_adopt and st.button('确认采用此路径',key='cf_adopt_'+path_vm.path_id):
                try:
                    adopted = adopt_counterfactual_path(result,run,path_vm.path_id,confirmed=True,
                        adoption_id=result.request_id+':'+path_vm.path_id)
                    on_adopt(adopted)
                    st.rerun()
                except (ValueError,OSError) as exc:
                    st.error(str(exc))
        if result is None:
            st.caption('待执行 / 未授权：尚无当前基准的修复结果。')
        repair_board(result,adopt=adopt_card if on_adopt else None)
        if result:
            for key, label in [('json','JSON'),('markdown','中文Markdown报告')]:
                path=Path(result.files[key])
                st.download_button('下载反事实'+label,path.read_bytes(),file_name=path.name,key='cf_download_'+key+suffix)
            with st.expander('搜索权限、容量、轨迹与独立校验证据'):
                st.json(result.model_dump(mode='json'))
