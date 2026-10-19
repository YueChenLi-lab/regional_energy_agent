"""Opt-in, offline, controlled peak-treatment experiments on immutable inputs."""
import csv
from datetime import datetime
import json
from math import ceil
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field

from .adapters import sha256_file
from .agent import EnergyAgent
from .annual import build_annual_case,validate_calendar_year
from .comparability import compare_basis
from .data import check_data
from .frontier import run_summary
from .modifications import fingerprint
from .schemas import CAPACITY_FIELDS,Model,NonNegative,Positive,Source,SolverOptions,TaskRequest


class SuspectPoint(Model):
    timestamp: datetime
    expected_original_kw: NonNegative


class PeakStudySpec(Model):
    format: Literal['regional-energy-peak-study-v1']
    year: int
    building: Literal['test']
    meter: Literal['Q']
    points: list[SuspectPoint] = Field(min_length=1)
    local_reference_hours_each_side: Positive = 24
    cap_rounding_kw: Positive = 100
    capacity_relative_threshold: Positive = .01
    capacity_absolute_threshold: Positive = 1
    npv_relative_threshold: Positive = .01
    method_statement: str


class PeakStudyResult(Model):
    raw_file_sha256: str
    parent_normalized_sha256: str
    controls_sha256: str
    spec: PeakStudySpec
    scenarios: list[dict]
    conclusion: str
    files: dict[str,str]


_NAMES={'original':'原值基准','linear':'列出点邻时线性插值假设','local_cap':'列出点局部参考上限假设'}
_WARNING='人为处理研究假设，不认定原数据错误，不是校准后的实测。负荷电量本身改变会影响成本和排放，不能把全部差值归因于设备配置改善；仅评价推荐对这些峰值处理假设是否敏感，不判断真实峰值应是多少。'


def fixed_controls(task):
    """Explicitly keep all non-electric-load numerical inputs/search bounds."""
    data=task.data.model_dump(mode='json',exclude={'electric_load_kw','source_ids'})
    data['source_ids']={k:v for k,v in task.data.source_ids.items() if k!='electric_load_kw'}
    return {'data':data,**{k:getattr(task,k).model_dump(mode='json') for k in ('constraints','capacity_bounds','devices','economics')},
        'assessment_mode':task.assessment_mode,'resolution':task.resolution,'planning_mode':task.planning_mode,
        'capacity_objective':task.capacity_objective,'emission_species':task.emission_species,
        'candidates':[c.model_dump(mode='json') for c in task.candidates],
        'service_boundary':task.case_context.boundary,'excluded_services':task.case_context.excluded,
        'investment_scope':task.case_context.investment_scope,'timestamp_convention':task.case_context.timestamp_convention}


def derive_peak_tasks(task,spec,*,raw_file_sha256,parent_normalized_sha256):
    """Prepare all treatments from the ORIGINAL array; no model or solver call."""
    spec=PeakStudySpec.model_validate(spec)
    if task.data is None or task.capacity_bounds is None or task.economics is None or task.case_context is None:
        raise ValueError('峰值实验需要完整时序、固定容量边界、经济参数与服务边界')
    issues=check_data(task.data,task.emission_species)
    if issues:raise ValueError('实验输入未通过质量检查：'+'；'.join(i.message for i in issues))
    times=task.data.timestamps;original=np.asarray(task.data.electric_load_kw,dtype=float)
    lookup={t:i for i,t in enumerate(times)}
    if len({p.timestamp for p in spec.points})!=len(spec.points):raise ValueError('列出的处理点重复')
    selected=[]
    for point in spec.points:
        if point.timestamp.tzinfo is None or point.timestamp not in lookup:raise ValueError('处理点必须含时区且精确对应原时序')
        i=lookup[point.timestamp]
        if i in (0,len(times)-1):raise ValueError('端点不能用双侧邻时插值')
        if abs(original[i]-point.expected_original_kw)>1e-8:raise ValueError('原始点值与预声明不一致；不能把配置应用于其他数据')
        selected.append(i)
    selected_set=set(selected);remaining=np.asarray([i for i in range(len(times)) if i not in selected_set])
    if not len(remaining):raise ValueError('缺少未处理参考点')
    before_controls=fingerprint(fixed_controls(task));tasks={};treatments={}
    for method in _NAMES:
        derived=task.model_copy(deep=True);values=original.copy();changes=[]
        if method!='original':
            for i in selected:
                left=max(j for j in remaining if j<i);right=min(j for j in remaining if j>i)
                references=[j for j in remaining if 0<abs((times[j]-times[i]).total_seconds())/3600<=spec.local_reference_hours_each_side]
                if not references:raise ValueError('局部参考窗口无可用原始参考点')
                local_max=float(max(original[references]));cap=ceil(local_max/spec.cap_rounding_kw)*spec.cap_rounding_kw
                after=float(np.interp(i,[left,right],original[[left,right]])) if method=='linear' else min(float(original[i]),cap)
                values[i]=after
                changes.append({'timestamp':times[i].isoformat(),'before_kw':float(original[i]),'after_kw':after,
                    'method':method,'affected_energy_kwh':(after-float(original[i]))*task.data.step_hours,
                    'left_reference':times[left].isoformat(),'right_reference':times[right].isoformat(),
                    'local_reference_hours_each_side':spec.local_reference_hours_each_side,'local_reference_count':len(references),
                    'local_max_kw':local_max,'cap_rounding_kw':spec.cap_rounding_kw,'predeclared_rule_cap_kw':cap})
            sid='peak-assumption-'+method
            derived.data.electric_load_kw=values.tolist();derived.data.source_ids['electric_load_kw']=sid
            derived.version=task.version+(1 if method=='linear' else 2)
            derived.project_name=task.project_name+' · '+_NAMES[method]
            source=Source(source_id=sid,name=_NAMES[method]+'（人为处理，非校准实测）',category='assumption',
                region=next(s.region for s in task.sources if s.source_id==task.data.source_ids['electric_load_kw']),
                time_range=times[0].isoformat()+' 至 '+times[-1].isoformat(),units={'electric_load_kw':'kW','delta_energy_kwh':'kWh'},
                parent_source_ids=[task.data.source_ids['electric_load_kw']],version='v0.3.2',
                processing=[json.dumps({'raw_file_sha256':raw_file_sha256,'parent_normalized_sha256':parent_normalized_sha256,
                    'method':method,'spec':spec.model_dump(mode='json'),'changes':changes},ensure_ascii=False)],conditions=_WARNING)
            derived.sources.append(source)
            derived.case_context.quality_summary='原始Q跳变仍未核实；仅对预声明点采用'+_NAMES[method]+'，原始文件只读。'
            derived.case_context.energy_check='原始转换能量核对仅适用于原值基准；本派生情景另列修改前后电量与差值，不冒充校准实测。'
            derived.case_context.pending=[x for x in derived.case_context.pending if 'Q跳变保留' not in x]+[_WARNING]
        if fingerprint(fixed_controls(derived))!=before_controls:raise ValueError('峰值情景改变了应保持的条件，停止实验')
        tasks[method]=derived
        treatments[method]={'method':method,'label':_NAMES[method],'category':'original' if method=='original' else 'assumption',
            'raw_file_sha256':raw_file_sha256,'parent_normalized_sha256':parent_normalized_sha256,
            'controls_sha256':before_controls,'spec':spec.model_dump(mode='json'),'changes':changes,'warning':_WARNING}
    return tasks,treatments


def standardized_csv(task):
    import io
    stream=io.StringIO(newline='');writer=csv.writer(stream)
    fields=['timestamps',*[k for k in type(task.data).model_fields if isinstance(getattr(task.data,k),list) and k!='timestamps']]
    writer.writerow(["timestamp",*fields[1:]])
    for i,t in enumerate(task.data.timestamps):writer.writerow([t.isoformat(),*[getattr(task.data,k)[i] for k in fields[1:]]])
    return stream.getvalue().encode('utf-8')


def robustness_conclusion(rows,spec):
    if not all(r['feasible'] for r in rows):return '至少一个情景没有通过独立校验的可行解，尚不能确认推荐稳健。'+_WARNING
    base=rows[0];changed=[]
    for row in rows[1:]:
        for k in CAPACITY_FIELDS:
            threshold=max(spec.capacity_absolute_threshold,abs(base[k])*spec.capacity_relative_threshold)
            if abs(row[k]-base[k])>threshold:changed.append(row['method']+'的'+k)
        if abs(row['npv_cost_yuan']-base['npv_cost_yuan'])>abs(base['npv_cost_yuan'])*spec.npv_relative_threshold:changed.append(row['method']+'的NPV')
    label='超过预声明判据，对这些峰值处理假设敏感' if changed else '未超过预声明判据，在本次预算、范围及假设下推荐未显示明显敏感'
    qualifiers='' if all(r['status']=='optimal' and r.get('mip_gap') is not None and r['mip_gap']<=1e-5 for r in rows) else '部分解未证明最优或仍有间隙；此结论仅比较已求得的可行解，不能证明最优推荐稳健。'
    return label+f'（容量差阈值max({spec.capacity_absolute_threshold:g}kW、kW_th或kWh,基准容量×{spec.capacity_relative_threshold:.1%})；NPV差阈值{spec.npv_relative_threshold:.1%}）。'+qualifiers+_WARNING


def run_peak_study(*,bundle_dir='examples/shanghai_2017',spec_file='configs/peak_sensitivity_v032.json',output='outputs/peak_study',time_limit=120):
    out=Path(output)
    if out.exists() and any(out.iterdir()):raise ValueError('峰值实验需要新空目录，防止覆盖旧证据')
    out.mkdir(parents=True,exist_ok=True)
    spec=PeakStudySpec.model_validate_json(Path(spec_file).read_text(encoding='utf-8'))
    raw=Path(bundle_dir)/'records.csv';raw_sha=sha256_file(raw)
    base=build_annual_case(bundle_dir=bundle_dir,year=spec.year,heat=True,retain_flagged_jumps=True)
    validate_calendar_year(base.data)
    import hashlib
    parent_csv=standardized_csv(base);parent_sha=hashlib.sha256(parent_csv).hexdigest()
    tasks,treatments=derive_peak_tasks(base,spec,raw_file_sha256=raw_sha,parent_normalized_sha256=parent_sha)
    controls=fixed_controls(base);control_sha=fingerprint(controls)
    (out/'controls.json').write_text(json.dumps(controls,ensure_ascii=False,indent=2),encoding='utf-8')
    # All thresholds/treatments are persisted BEFORE any solver is invoked.
    (out/'predeclared_treatments.json').write_text(json.dumps(treatments,ensure_ascii=False,indent=2),encoding='utf-8')
    agent=EnergyAgent(out/'runs',SolverOptions(time_limit_seconds=time_limit,mip_rel_gap=0))
    original_run=None;rows=[];result_files={}
    for method,task in tasks.items():
        folder=out/'inputs'/method;folder.mkdir(parents=True)
        (folder/'task.json').write_text(task.model_dump_json(indent=2),encoding='utf-8')
        (folder/'standardized.csv').write_bytes(standardized_csv(task))
        (folder/'metadata.json').write_text(json.dumps({k:getattr(task.data,k) for k in ('step_hours','units','source_ids')},ensure_ascii=False,indent=2),encoding='utf-8')
        (folder/'treatment.json').write_text(json.dumps(treatments[method],ensure_ascii=False,indent=2),encoding='utf-8')
        if fingerprint(fixed_controls(task))!=control_sha:raise ValueError('求解前固定条件核对失败')
        run=agent.run(task,previous=original_run)
        if original_run is None:original_run=run
        info=run_summary(run)
        info.update(method=method,label=_NAMES[method],annual_electric_kwh=float(sum(task.data.electric_load_kw)*task.data.step_hours),
            peak_kw=float(max(task.data.electric_load_kw)),controls_unchanged=True,controls_sha256=control_sha,
            supply_satisfied=all(s.validation.valid and s.validation.metrics.supply_satisfied for s in run.scenarios) if run.scenarios else False,
            independent_checks=[{'candidate_id':s.candidate.candidate_id,'valid':s.validation.valid,'checks':[c.model_dump() for c in s.validation.checks]} for s in run.scenarios],
            comparison_basis=compare_basis(base,task).model_dump(mode='json'),result_file=run.files.get('json'),
            result_sha256=sha256_file(Path(run.files['json'])),treatment=treatments[method])
        if method!='original':
            info['deltas']={k:info[k]-rows[0][k] for k in ('annual_electric_kwh','peak_kw',*CAPACITY_FIELDS,'investment_yuan','npv_cost_yuan','annual_emissions_kg') if k in info and k in rows[0]}
        rows.append(info);result_files[method]=run.files
    if sha256_file(raw)!=raw_sha:raise ValueError('原始文件哈希改变，实验无效')
    result=PeakStudyResult(raw_file_sha256=raw_sha,parent_normalized_sha256=parent_sha,controls_sha256=control_sha,
        spec=spec,scenarios=rows,conclusion=robustness_conclusion(rows,spec),files={'json':str(out/'study.json'),'csv':str(out/'scenarios.csv'),'markdown':str(out/'report.md')})
    Path(result.files['json']).write_text(result.model_dump_json(indent=2),encoding='utf-8')
    columns=['method','run_id','annual_electric_kwh','peak_kw',*CAPACITY_FIELDS,'investment_yuan','npv_cost_yuan','annual_emissions_kg','feasible','status','mip_gap','solve_seconds']
    with Path(result.files['csv']).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows({k:r.get(k) for k in columns} for r in rows)
    lines=['# Q疑似峰值处理假设敏感性实验',_WARNING,spec.method_statement,
        f'原始SHA256：`{raw_sha}`；标准化父文件SHA256：`{parent_sha}`；固定条件SHA256：`{control_sha}`。',
        '上海2017全年8760小时Q局部实测＋物理仿真供热，NASA估算PV；价格/排放/设备/经济均为研究假设。',
        '三组保持预算、容量上下界、购电上限、设备参数、经济参数、电价、燃气价格、排放因子、光伏和供热负荷；不根据处理后峰值重设范围。',
        '单位：电量kWh、功率kW、储能kWh、热设备kW_th、费用元、年度运行排放kgCO2e；NPV含代表年重复假设，运行排放不折现。',
        '|情景|年用电量 kWh|峰值 kW|PV kW|电池 kW/kWh|热泵/锅炉 kW_th|初投 元|NPV 元|年排放 kgCO2e|状态/间隙|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    def fmt(r,k):return f'{r[k]:,.6f}' if k in r else '未求得'
    for r in rows:
        lines.append('|'+ '|'.join([r['label'],fmt(r,'annual_electric_kwh'),fmt(r,'peak_kw'),fmt(r,'pv_kw'),fmt(r,'battery_power_kw')+'/'+fmt(r,'battery_energy_kwh'),fmt(r,'hp_kw_th')+'/'+fmt(r,'boiler_kw_th'),fmt(r,'investment_yuan'),fmt(r,'npv_cost_yuan'),fmt(r,'annual_emissions_kg'),r['status']+'/'+str(r.get('mip_gap'))])+'|')
    lines.extend(['## 处理证据与原值差异'])
    for r in rows:
        lines.extend([f"### {r['label']} · `{r['run_id']}`",'固定条件核对通过；'+r['comparison_basis']['summary'],
            '处理与阈值：\n\n```json\n'+json.dumps(r['treatment']['changes'],ensure_ascii=False,indent=2)+'\n```',
            '相对原值基准差值：\n\n```json\n'+json.dumps(r.get('deltas',{}),ensure_ascii=False,indent=2)+'\n```'])
    lines.extend(['## 稳健性结论',result.conclusion,'仅对本次声明的研究情景和预设判据有效；没有运行替代楼宇、其他峰值点或多价格/天气年实验。'])
    Path(result.files['markdown']).write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    return result
