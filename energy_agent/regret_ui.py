"""Passive presentation and explicit bounded form; does not adopt any result."""
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from .agent import ToolRegistry
from .counterfactual import digest
from .regret import (RegretRequest, RegretScenario, available_candidates,
                     default_scenarios, regret_enabled)

STATUS = {'certified':'已认证（仅当前有限矩阵）', 'approximate':'近似结果（含成本上界）',
          'partial':'待定 / 部分结果', 'no_recommendation':'没有完整推荐'}


def heatmap(matrix, cells, title):
    rows = [dict(配置=c.candidate_id, 情景=c.scenario_id, 金额=matrix[c.candidate_id][c.scenario_id],
                 状态=f'{c.solver_status or "未执行"} / {c.feasibility}') for c in cells]
    st.caption(title+'（元）；灰色表示无有效成本，详见状态，不能按0解释。')
    st.vega_lite_chart(pd.DataFrame(rows), {
        'height':max(100, 44*len(matrix)),
        'encoding':{'x':{'field':'情景','type':'nominal','axis':{'labelAngle':0}},
                    'y':{'field':'配置','type':'nominal'},
                    'tooltip':[{'field':'配置'},{'field':'情景'},{'field':'金额','format':',.2f'},{'field':'状态'}]},
        'layer':[{'mark':{'type':'rect','cornerRadius':4}, 'encoding':{
            'color':{'condition':{'test':'isValid(datum.金额)','field':'金额','type':'quantitative',
                      'scale':{'scheme':'blues'}}, 'value':'#49596c'}}},
            {'mark':{'type':'text','color':'#071c35','fontSize':12}, 'encoding':{
                'text':{'field':'金额','type':'quantitative','format':',.0f'}}}],
    }, width='stretch')


def show_regret_result(result):
    a = result.analysis
    st.subheader(STATUS[a.status])
    st.caption(f'基准 {result.base_run_id} · v{result.input_version} · 请求 {result.request_id}')
    cols = st.columns(3)
    cols[0].metric('基准情景最便宜', '、'.join(a.baseline_cheapest_ids) or '不可用')
    cols[1].metric('最小最大后悔候选', '、'.join(a.recommended_ids) or '待定 / 无完整推荐')
    cols[2].metric('实际求解适配器调用', str(result.solver_calls))
    st.info(result.explanation)
    heatmap(a.cost_matrix, result.cells, '成本热力图 · '+('规划期NPV' if result.cost_basis=='npv' else '评估期购能费'))
    heatmap(a.regret_matrix, result.cells, '后悔成本热力图 · 相对各情景当前候选集最佳')
    st.caption('最坏后悔对比：仅列出全部指定情景均有可行见证的配置；部分/近似状态不表示精确最优。')
    worst = {k:v for k,v in a.worst_regret_yuan.items() if v is not None}
    if worst:
        st.bar_chart(pd.DataFrame({'最坏后悔（元）':worst}), color='#24bed2')
    st.dataframe(pd.DataFrame([{'配置':c.candidate_id,'情景':c.scenario_id,
        '投资（元）':c.investment_yuan,'成本（元）':c.cost_yuan,
        '运行排放（kg）':c.emissions_kg,'状态':c.solver_status or '未执行',
        '可行性':c.feasibility,'独立校验':bool(c.validation and c.validation.valid),'gap':c.mip_gap} for c in result.cells]),hide_index=True)
    st.caption('排放物质与核算边界见原任务；排放未折现。没有“采用”按钮：本分析不会改写当前确认任务。')
    for kind, label, mime in [('json','下载结构化结果','application/json'),('csv','下载矩阵CSV','text/csv'),('markdown','下载中文报告','text/markdown')]:
        path=Path(result.files[kind])
        if path.is_file():
            st.download_button(label,path.read_bytes(),file_name=path.name,mime=mime,key=f'regret_download_{kind}_{result.base_run_id}')
    with st.expander('情景定义、容量指纹与逐单元证据'):
        st.json(result.model_dump(mode='json'))


def render_regret(run):
    if not regret_enabled():
        return
    with st.expander('多情景稳健决策 · 固定投资，运行可适应'):
        st.write('基准情景最便宜的方案，未必是在各类变化下后悔成本最小的方案。')
        st.caption('预设问题引导受限表单，不代表任意自然语言理解；刷新和切换页面不求解，不调用付费模型。')
        if run is None:
            st.caption('待执行：请先确认一个已有可行任务；不可行时先使用反事实约束修复。')
            return
        if not any(s.validation.valid for s in run.scenarios):
            st.warning('当前任务没有经校验的可行见证；请先使用反事实约束修复，或完成尚未确定的评估。')
            return
        prefix='regret_'+run.run_id
        st.selectbox('问题引导（仅表单提示）',['电价涨了、光伏发电偏低，哪个方案更不容易后悔？','现在最便宜的方案，遇到其他情况还合适吗？'],key=prefix+'_hint')
        choices=available_candidates(run)
        ids=[c.candidate.candidate_id for c in choices]
        with st.form(prefix+'_form'):
            selected=st.multiselect('固定配置（最多4个）',ids,default=ids[:3],max_selections=4,key=prefix+'_candidates')
            st.caption('容量沿用已确认任务的候选/已求得配置，跨情景保持不变；投资仍受原预算约束。')
            enabled=st.multiselect('研究情景（基准必选）',['electric_up','gas_up','pv_down'],default=['electric_up','gas_up','pv_down'],
                format_func=lambda x:{'electric_up':'购电价格变化','gas_up':'燃气价格变化','pv_down':'光伏出力变化'}[x],key=prefix+'_scenarios')
            columns=st.columns(3)
            e=columns[0].number_input('购电价格倍数',min_value=0.,max_value=10.,value=1.2,key=prefix+'_electric')
            g=columns[1].number_input('燃气价格倍数',min_value=0.,max_value=10.,value=1.2,key=prefix+'_gas')
            p=columns[2].number_input('光伏出力倍数',min_value=0.,max_value=10.,value=.8,key=prefix+'_pv')
            load_on=st.checkbox('额外明确授权电负荷倍数情景（不改变供热）',key=prefix+'_load_on')
            load=st.number_input('电负荷倍数（仅启用后生效）',min_value=0.,max_value=10.,value=1.1,key=prefix+'_load')
            st.caption('以上是人为研究假设、不是预测。供热、时间轴、服务保障、预算、购电/排放/场地边界、设备和经济参数全部保持。光伏越界直接拒绝。')
            columns=st.columns(3)
            single=columns[0].number_input('每次求解时限（秒）',1.,300.,5.,key=prefix+'_single')
            total=columns[1].number_input('共享总时间（秒）',1.,1800.,60.,key=prefix+'_total')
            calls=columns[2].number_input('共享调用上限',1,20,20,key=prefix+'_calls')
            annual_ok=st.checkbox('明确允许完整年度矩阵（若有经济参数，采用同规划期NPV；可能耗时）',key=prefix+'_annual')
            confirmed=st.checkbox('确认上述情景字段授权及全部保持条件；仅探索，不采用',key=prefix+'_confirm')
            start=st.form_submit_button('开始多情景分析',key=prefix+'_start')
        if start:
            try:
                if not confirmed:
                    raise ValueError('请明确确认情景授权与保持条件')
                defaults=default_scenarios()
                multipliers=[('electric_up',e,'electricity_price_multiplier'),('gas_up',g,'gas_price_multiplier'),('pv_down',p,'pv_multiplier')]
                scenarios=[defaults[0]]+[RegretScenario(scenario_id=i,name=f'{field} × {factor:g}',**{field:factor}) for i,factor,field in multipliers if i in enabled]
                allowed=['electricity_price_multiplier','gas_price_multiplier','pv_multiplier']
                if load_on:
                    scenarios.append(RegretScenario(scenario_id='electric_load',name=f'电负荷 × {load:g}',electric_load_multiplier=load))
                    allowed.append('electric_load_multiplier')
                # Stable ID for identical confirmed form; changed parameters create a new explicit request.
                content=dict(base=run.run_id,input=digest(run.task),candidates=selected,scenarios=[s.model_dump() for s in scenarios],
                             single=single,total=total,calls=calls,annual=annual_ok,load=load_on)
                request_id='regret-ui-'+digest(content)
                request=RegretRequest(request_id=request_id,baseline=run,base_run_id=run.run_id,
                    input_version=run.input_version,input_sha256=digest(run.task),
                    candidates=[c for c in choices if c.candidate.candidate_id in selected],scenarios=scenarios,
                    allowed_changes=allowed,allow_electric_load_change=load_on,
                    cost_basis='npv' if run.task.economics else 'period_energy',confirm_large_annual=annual_ok,
                    single_solve_seconds=single,total_seconds=total,max_solver_calls=calls,
                    output_dir=str(Path(os.getenv('ENERGY_AGENT_OUTPUT_DIR','outputs'))/'regret'))
                with st.spinner('固定配置，逐情景求解与独立校验…'):
                    st.session_state[prefix+'_result']=ToolRegistry().call('evaluate_minimax_regret',request)
            except (ValueError,OSError) as exc:
                st.error(f'分析未执行或未完成：{exc}')
        result=st.session_state.get(prefix+'_result')
        if result is not None:
            show_regret_result(result)
        else:
            st.caption('待执行：尚无当前任务的情景矩阵，不显示虚构指标。')
