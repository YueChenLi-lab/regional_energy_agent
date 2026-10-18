"""Annual planning UI; model calls happen only under explicit buttons."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from .agent import EnergyAgent, revise_task
from .annual import build_annual_case
from .conversation import AgentSession, ConnectivityCheck
from .frontier import SensitivityRequest, sensitivity_analysis
from .llm import LLMError, OpenAICompatibleClient, get_llm_client
from .schemas import CAPACITY_FIELDS, RunResult, SolverOptions, TaskPatch, TaskRequest


_NAMES=dict(zip(CAPACITY_FIELDS,['光伏 kW','电池功率 kW','电池能量 kWh','热泵 kW_th','锅炉 kW_th']))


def render_planning(show_results):
    st.subheader('全年规划与可核对 Agent')
    st.info('上海2017全年Q照明插座实测＋NASA估算PV；可选择参数化仿真供热。价格、成本和经济条件为假设；不是实测全楼改造。原始2个跳变告警保留，峰值影响容量，尚未获发布方核实。')
    heat=st.checkbox('加入物理仿真供热（排除W，研究情景）',value=True,key='annual_heat')
    ack=st.checkbox('确认Q局部边界、北京时间区间起点假设及保留跳变原值的研究风险',key='annual_ack')
    if st.button('加载许可全年离线案例',disabled=not ack):
        try:
            task=build_annual_case(heat=heat,bundle_dir=Path(__file__).resolve().parents[1]/'examples/shanghai_2017',retain_flagged_jumps=True)
            for k in list(st.session_state):
                if k.startswith(('lo_','hi_','life_','om_','replace_','salvage_')) or k in ('annual_study','agent_reply'):
                    st.session_state.pop(k,None)
            st.session_state.annual_task=task;st.session_state.annual_run=None
        except (ValueError,OSError) as exc:st.error(str(exc))
    upload=st.file_uploader('或导入统一全年任务JSON（含来源、经济与容量边界）',type=['json'],key='annual_upload')
    if upload and st.button('校验并加载上传任务'):
        from .data import validate_inputs
        try:
            task=TaskRequest.model_validate_json(upload.getvalue())
            validation=validate_inputs(task)
            if not validation.ready:st.error('；'.join(i.message for i in validation.issues))
            else:st.session_state.annual_task=task;st.session_state.annual_run=None
        except ValueError as exc:st.error(str(exc))
    task=st.session_state.get('annual_task')
    if task is None:return
    st.write(task.project_name)
    st.caption(task.case_context.boundary if task.case_context else '用户声明边界')
    with st.expander('数据质量、来源与研究假设'):
        st.write(task.case_context.quality_summary if task.case_context else '未知')
        st.write(task.case_context.pending if task.case_context else [])
        st.json([s.model_dump(mode='json') for s in task.sources])
    if task.economics is None or task.capacity_bounds is None:
        st.error('全年规划入口需要完整经济参数与容量边界');return
    with st.form('annual_conditions'):
        mode=st.selectbox('规划模式',['容量优化','有限候选对照'])
        resolution=st.selectbox('运行范围',['全年逐时（含NPV）','168小时快速运行检查（不计算全年NPV）'])
        budget=st.number_input('初始投资预算 元',min_value=0.0,value=float(task.constraints.budget_yuan),step=100000.0)
        cap_on=st.checkbox('启用年度运行排放上限',value=task.constraints.emission_limit_kg is not None)
        emission=st.number_input(f'年度运行排放上限 kg{task.emission_species}',min_value=0.0,value=float(task.constraints.emission_limit_kg or 2000000))
        grid=st.number_input('购电功率上限 kW',min_value=0.0,value=float(task.constraints.grid_limit_kw))
        horizon=st.number_input('规划年数',min_value=1,max_value=100,value=task.economics.horizon_years)
        rate=st.number_input('折现率',min_value=0.0,max_value=1.0,value=task.economics.discount_rate)
        seconds=st.number_input('每个求解时限 秒',min_value=1.0,value=60.0)
        ranges={};assets={}
        with st.expander('容量下限/上限、设备寿命与费用（假设，可修改）'):
            for key in CAPACITY_FIELDS:
                b=getattr(task.capacity_bounds,key);asset=task.economics.assets[key]
                st.write(_NAMES[key]);a,c=st.columns(2)
                lower=a.number_input('容量下限',min_value=0.0,value=float(b.lower),key='lo_'+key)
                upper=c.number_input('容量上限',min_value=0.0,value=float(b.upper),key='hi_'+key)
                life=st.number_input('寿命 年',min_value=1,max_value=100,value=asset.lifetime_years,key='life_'+key)
                fixed=st.number_input('年固定维护费/初始设备含安装投资',min_value=0.0,value=asset.fixed_om_fraction,key='om_'+key)
                replacement=st.number_input('更换费/初始设备含安装投资',min_value=0.0,value=asset.replacement_fraction,key='replace_'+key)
                salvage=st.selectbox('期末残值',['straight_line','none'],index=0 if asset.residual_method=='straight_line' else 1,key='salvage_'+key)
                ranges[key]={'lower':lower,'upper':upper};assets[key]={'lifetime_years':life,'fixed_om_fraction':fixed,'replacement_fraction':replacement,'residual_method':salvage}
            variable={k:st.number_input(k+' 元/kWh（热设备为kWh_th）',min_value=0.0,value=float(getattr(task.economics,k))) for k in ('battery_variable_om_per_kwh','hp_variable_om_per_kwh_th','boiler_variable_om_per_kwh_th')}
        evaluate=st.form_submit_button('保存条件并重新评估')
        study=st.form_submit_button('保存条件并执行成本—排放扫描')
    if evaluate or study:
        try:
            revised=revise_task(task,TaskPatch(budget_yuan=budget,emission_limit_kg=emission if cap_on else None,clear_emission_limit=not cap_on,grid_limit_kw=grid))
            raw=revised.model_dump(mode='json')
            raw['planning_mode']='capacity' if mode=='容量优化' else 'candidates'
            raw['economics'].update(horizon_years=horizon,discount_rate=rate,assets=assets,**variable)
            raw['capacity_bounds'].update(ranges);raw['constraints']['pv_limit_kw']=ranges['pv_kw']['upper']
            revision=raw['constraints']['source_id']
            raw['economics']['source_id']=raw['capacity_bounds']['source_id']=revision
            next(s for s in raw['sources'] if s['source_id']==revision)['processing'].append(json.dumps({'economics':raw['economics'],'capacity_bounds':raw['capacity_bounds']},ensure_ascii=False))
            if resolution.startswith('168'):
                if study or mode=='容量优化':raise ValueError('快速检查仅用于有限候选运行；全年NPV/容量优化需要完整年，不能将168小时年化')
                raw['resolution']='quick_period';raw['economics']=None
                raw['data']={k:(v[:168] if isinstance(v,list) else v) for k,v in raw['data'].items()}
            revised=TaskRequest.model_validate(raw)
            options=SolverOptions(time_limit_seconds=seconds,mip_rel_gap=0.002)
            with st.spinner('求解并独立核查，每个问题有明确时限……'):
                if study:
                    result=sensitivity_analysis(SensitivityRequest(task=revised,options=options,output_dir='outputs/ui_study/'+uuid4().hex))
                    st.session_state.annual_study=result
                    st.session_state.annual_task=revised
                    st.session_state.annual_run=None
                else:
                    run=EnergyAgent('outputs/ui_annual',options).run(revised,previous=st.session_state.get('annual_run'))
                    st.session_state.annual_study=None
                    st.session_state.annual_run=run
                    # Keep the full-year template when running a quick dispatch check.
                    if revised.economics:st.session_state.annual_task=run.task
        except (ValueError,OSError) as exc:st.error(str(exc))
    result=st.session_state.get('annual_study')
    if result:
        st.write(result.note)
        frame=pd.DataFrame(result.points)
        frame['已求得点类型']=frame.run_id.map(lambda rid:'已求得非支配点' if rid in result.nondominated_run_ids else '其余已求得点')
        st.dataframe(frame.drop(columns=['model_statistics'],errors='ignore'),hide_index=True)
        feasible=frame[frame.feasible]
        if not feasible.empty:st.scatter_chart(feasible,x='annual_emissions_kg',y='npv_cost_yuan',color='已求得点类型')
        for key,file in result.files.items():st.download_button('下载取舍分析 '+key,Path(file).read_bytes(),file_name=Path(file).name,key='study_'+key)
    run=st.session_state.get('annual_run')
    if run:
        show_results(run)
        render_model(run)


def render_model(run):
    with st.expander('DeepSeek / 可配置模型 Agent',expanded=True):
        if 'planning_llm' not in st.session_state:st.session_state.planning_llm=get_llm_client()
        client=st.session_state.planning_llm
        if not isinstance(client,OpenAICompatibleClient):st.caption(client.description);return
        st.caption(f'提供商：{client.provider}；模型：{client._model}；密钥已配置（不显示）；本会话请求 {client.budget.count}/10。只在点击按钮时联网。')
        if st.button('显式测试模型连接（1次请求，可能计费）'):
            try:
                result=client.call_tool('connectivity_check',ConnectivityCheck,{'request':'返回status=ok'})
                st.success('真实服务结构化连通检查通过：'+result.status)
            except LLMError as exc:st.error(str(exc))
        text=st.text_area('自然语言要求',value='预算减少20%，供热要求保持不变。',key='annual_nl')
        request_id=st.text_input('请求ID：重试保持相同；再次应用同一修改请换ID',value=uuid4().hex,key='annual_request_id')
        if st.button('调用模型并执行受支持工具（可能计费）'):
            try:
                session=AgentSession(EnergyAgent('outputs/ui_agent',run.solver_options),client,'outputs/ui_agent_receipts')
                reply=session.submit(text,run,request_id=request_id)
                st.session_state.agent_reply=reply
                if reply.run:
                    st.session_state.annual_run=reply.run
                    st.session_state.annual_task=reply.run.task
            except (ValueError,OSError) as exc:st.error(str(exc))
        reply=st.session_state.get('agent_reply')
        if reply:
            st.write(reply.text)
            st.caption(f'供热与时段完全不变：{reply.heat_unchanged}；当前结果数字核对：{reply.explanation_verified}')
            if reply.run:
                with st.expander('工具步骤与前后差异'):
                    st.dataframe(pd.DataFrame([c.model_dump() for c in reply.run.tool_calls]),hide_index=True)
                    st.json(reply.run.changes)
        with st.expander('脱敏服务调用记录'):st.json(client.budget.records)
