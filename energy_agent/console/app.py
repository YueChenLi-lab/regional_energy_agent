"""Optional competition console, composing existing Streamlit workflows."""
import streamlit as st

from .components import empty, execution, feature_cards, section, theme
from .views import conversation_snapshot, evidence, experiment, results, selected_run

PAGES = ['项目首页', '问答工作台', '优化结果', '实验验证', '证据详情']


def navigate(page: str) -> None:
    st.session_state.console_navigation = page


def home() -> None:
    st.html('''<section class="rea-hero"><div class="rea-eyebrow">Regional Energy · Planning Agent</div>
    <h1>让能源规划建议<br>有计算依据，也有可追溯证据。</h1>
    <p>区域综合能源低碳规划评估 Agent<br>
    将预算、负荷与运行排放约束转化为可比较的供能方案。
    模型理解需求，确定性工具计算，独立校验复核，报告保留来源与假设。</p></section>''')
    with st.container(horizontal=True):
        st.button('进入演示与评估 →', type='primary', on_click=navigate, args=('优化结果',), key='console_start')
        st.button('查看 8760 小时实验证据 →', on_click=navigate, args=('实验验证',), key='console_experiment')
    section('一个工作流，三层可信依据', '单供能节点 · 全年容量优化 / 有限候选对照 · 运行阶段排放')
    feature_cards([
        ('01 / Understand', '受约束的 Agent', '必要时先澄清；修改契约记录变更与保留项。模型不能执行任意代码，也不能替代数值计算。'),
        ('02 / Compute', '确定性规划与调度', '光伏、储能、热泵、锅炉与购电联合评估；初始投资、评估期运行费与规划期NPV分列。'),
        ('03 / Verify', '独立检查与来源追溯', '复核逐时电热平衡、设备容量和SOC。区分实测、估算、合成与假设，保留run_id和报告。'),
    ])
    st.caption('展示范围：研究原型。电侧模式不承诺供热保障；未计算设备隐含排放，不提供零碳认证。页面刷新不调用付费模型。')


def prepare() -> None:
    """Compose existing forms once; all their session keys and calls stay intact."""
    from ..import_ui import render_import
    from ..planning_ui import render_planning
    from ..ui import render_demo

    before = {k: getattr(st.session_state.get(k), 'run_id', None) for k in ('annual_run', 'last_run', 'real_run')}
    adopted_real = st.session_state.pop('cf_refresh_real', None)
    if adopted_real:
        st.session_state.real_budget = float(adopted_real.task.constraints.budget_yuan)
        st.session_state.real_grid = float(adopted_real.task.constraints.grid_limit_kw)
        st.session_state.real_carbon_on = adopted_real.task.constraints.emission_limit_kg is not None
        if adopted_real.task.constraints.emission_limit_kg is not None:
            st.session_state.real_carbon_limit = float(adopted_real.task.constraints.emission_limit_kg)
    if st.session_state.pop('console_collapse_prepare', False):
        st.session_state.console_prepare_open = False
    with st.expander('准备评估条件 · 加载案例 / 修改参数', expanded=not any(
        st.session_state.get(k) for k in ('annual_run', 'last_run', 'real_run')
    ), key='console_prepare_open', on_change='rerun'):
        workflow = st.radio('案例入口', ['合成演示', '外部数据导入（电侧）', '全年规划与Agent'], horizontal=True, key='workflow')
        # Results are rendered below using the exact run stored by these forms.
        if workflow == '全年规划与Agent':
            render_planning(lambda run: None, include_model=False, include_experiment=False)
        elif workflow == '外部数据导入（电侧）':
            render_import(lambda run: None)
        else:
            render_demo(lambda run: None)
    after = {k: getattr(st.session_state.get(k), 'run_id', None) for k in before}
    if any(after[k] and after[k] != before[k] for k in before):
        st.session_state.console_collapse_prepare = True
        st.rerun()


def workbench(run) -> None:
    from .chat_workspace import render
    render(run, navigate)


def main() -> None:
    st.set_page_config(page_title='区域能源规划 · Agent 工作台', page_icon='⚡', layout='wide')
    theme()
    st.html('''<header class="rea-header"><div><span class="rea-eyebrow">Energy Planning Console</span>
    <strong>区域综合能源低碳规划评估 Agent</strong></div>
    <span class="rea-badge">比赛展示界面 · 复用现有计算流程</span></header>''')
    # All five tabs render each time: Streamlit keeps existing widget-backed
    # session keys alive, and no data/model/solver is called just by navigating.
    tabs = st.tabs(PAGES, key='console_navigation', on_change='rerun')
    with tabs[0]:
        home()
    # Render preparation first so a submitted form is visible everywhere in
    # this render, including the dialogue and evidence tabs.
    with tabs[2]:
        section('优化结果', '先确认输入，再比较配置；数值仅来自计算工具')
        prepare()
        run = selected_run()
        results(run)
        from ..counterfactual_ui import render_counterfactual
        def adopt_repair(adopted):
            key = st.session_state.console_run_key
            st.session_state[key] = adopted
            if key == 'annual_run':
                st.session_state.annual_task = adopted.task
            elif key == 'last_run':
                st.session_state.task = adopted.task
                st.session_state.refresh_conditions = True
            else:
                st.session_state.cf_refresh_real = adopted
        render_counterfactual(run, on_adopt=adopt_repair)
        from ..regret_ui import render_regret
        render_regret(run)
    with tabs[1]:
        workbench(run)
    with tabs[3]:
        experiment()
        from .decision_archives import render_archived_decisions
        render_archived_decisions()
    with tabs[4]:
        evidence(run)


if __name__ == '__main__':
    main()
