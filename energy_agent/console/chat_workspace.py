"""Two-column Agent workbench. Wraps the existing assistant; never solves or calls a model itself."""
import hashlib
import os
from pathlib import Path

import streamlit as st

from .components import empty, execution, section
from .decision_components import chat_stream, decision_theme, intent_selector, pipeline, task_summary
from .decision_presenters import (build_conversation_vm, build_task_summary, derive_stages, g,
                                  intent_options, router_available)


def _context(run, annual) -> dict:
    from ..counterfactual import counterfactual_enabled
    from ..regret import regret_enabled
    return {'has_annual': annual is not None, 'has_run': run is not None,
            'has_witness': bool(run is not None and any(s.validation.valid for s in run.scenarios)),
            'cf_enabled': counterfactual_enabled(), 'regret_enabled': regret_enabled()}


def _load_base(reply):
    """Read the existing receipt snapshot without constructing an AgentSession."""
    pending = g(reply, 'pending')
    sid = st.session_state.get('assistant_session_id')
    if pending is None or not sid or not g(pending, 'base_file'):
        return None
    try:
        from ..schemas import RunResult
        folder = (Path(os.getenv('ENERGY_AGENT_OUTPUT_DIR', 'outputs')) / 'ui_conversations'
                  / hashlib.sha256(sid.encode()).hexdigest() / 'receipts')
        name = g(pending, 'base_file')
        expected = hashlib.sha256(str(g(pending,'request_id')).encode()).hexdigest()+f'.base{g(pending,"generation")}.json'
        if name != expected:
            return None
        target=(folder/name).resolve()
        if target.parent!=folder.resolve():
            return None
        run=RunResult.model_validate_json(target.read_bytes())
        return run if run.run_id==g(pending,'base_run_id') and run.input_version==g(pending,'input_version') else None
    except (OSError, ValueError):
        return None


def render(run, navigate) -> None:
    """Replaces console.app.workbench(run)'s body. render_model(annual) is called exactly once."""
    decision_theme()
    section('问答工作台', '理解请求 → 校验与授权 → 工具执行 → 独立复核 → 结果解释')
    annual = st.session_state.get('annual_run')
    left, right = st.columns([13, 7], gap='large')
    with left:
        stage_slot = st.container()       # filled after render_model so a reply created in this run is shown
        intent_selector(intent_options(_context(run, annual)), navigate=navigate, router_ready=router_available())
        chat_slot = st.container()
        if annual is None:
            empty('持续对话沿用现有“全年规划与Agent”任务入口。请先在优化结果中加载并评估全年任务；'
                  '合成演示的表单与原有参数修改入口仍可使用。')
        else:
            if run is not None and run.run_id != annual.run_id:
                st.warning('结果页当前选择了其他运行；下方对话助手的确认基准仍为全年规划运行，不会自动替换基准。')
            st.caption(f'助手当前任务：{annual.run_id} · v{annual.input_version}。会话恢复和重新选择基准使用原有处理逻辑。')
            from ..planning_ui import render_model
            render_model(annual)          # existing widgets/keys/callbacks untouched
    reply = st.session_state.get('agent_reply')
    current = st.session_state.get('annual_run') or run
    stages = derive_stages(reply)
    with stage_slot:
        pipeline(stages)
    with chat_slot:
        if reply is None:
            st.caption('尚无对话快照；请在下方助手输入要求。尚未发起模型调用或求解。')
        else:
            chat_stream(build_conversation_vm(reply, current))
        study=g(reply,'study')
        if study is not None:
            with st.expander('本请求的成本—排放扫描结果（只读）',expanded=True):
                st.caption('扫描基线 run_id：'+str(g(study,'baseline_run_id'))+'；这是已保存的有限扫描，不是新执行或完整全局前沿。')
                st.write(g(study,'note',''))
                st.dataframe(g(study,'points',[]) or [],hide_index=True)
                st.caption('已记录非支配运行：'+'、'.join(g(study,'nondominated_run_ids',[]) or []))
                for kind,raw in (g(study,'files',{}) or {}).items():
                    path=Path(raw)
                    if path.is_file():
                        st.download_button('下载本请求扫描 '+kind,path.read_bytes(),file_name=path.name,
                            key='dw_study_'+str(g(reply,'request_id'))+'_'+kind)
    with right:
        task_summary(build_task_summary(reply, current, _load_base(reply)), stages, navigate=navigate)
        if current is not None:
            with st.expander('运行状态流转（来自 RunResult.states）'):
                execution(current)
