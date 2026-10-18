"""Read-only peak/jump diagnostics; never repair or overwrite measured samples."""
from pathlib import Path
import json

import numpy as np
from pydantic import Field

from .schemas import Model, TaskRequest


class PeakDiagnostics(Model):
    source_id: str
    records: int
    source_category: str = "unknown"
    peak_timestamp: str
    peak_kw: float
    second_highest_kw: float
    percentile_99_kw: float
    grid_limit_kw: float
    baseline_no_pv_storage_required_grid_kw: float
    peak_necessary_battery_power_kw: float
    configured_capacity_bounds: dict
    jumps: list[dict]
    peak_neighbors: list[dict]
    summary: str
    treatment: str = '本诊断不替代、删点、插补或缩放输入，不覆盖原始发布文件。若输入已有人工情景处理，应按来源记录解释，不是校准实测数据。未执行替代值敏感性求解。'


def diagnose_peak(request:TaskRequest) -> PeakDiagnostics:
    task=TaskRequest.model_validate(request)
    if task.data is None or task.constraints is None:raise ValueError('峰值诊断需要负荷与项目约束')
    from .data import check_data
    issues=check_data(task.data,task.emission_species)
    if issues:raise ValueError('；'.join(i.field+': '+i.message for i in issues))
    data=task.data;n=len(data.timestamps);values=np.asarray(data.electric_load_kw,dtype=float)
    if len(values)!=n or not np.isfinite(values).all() or (values<0).any():raise ValueError('负荷缺失、非有限或非法，不能诊断峰值')
    peak=int(np.argmax(values))
    def neighbors(index):
        return [{'timestamp':data.timestamps[t].isoformat(),'electric_load_kw':float(values[t]),'heat_load_kw_th':data.heat_load_kw_th[t],
            'pv_per_kw':data.pv_per_kw[t],'is_peak':t==peak} for t in range(max(0,index-3),min(n,index+4))]
    small=np.minimum(values[1:],values[:-1]);large=np.maximum(values[1:],values[:-1])
    jump_indices=np.flatnonzero((np.abs(np.diff(values))>100)&(large>8*np.maximum(small,1e-12)))+1
    jumps=[{'timestamp':data.timestamps[i].isoformat(),'previous_kw':float(values[i-1]),'current_kw':float(values[i]),
        'absolute_change_kw':float(abs(values[i]-values[i-1])),'neighbors':neighbors(int(i))} for i in jump_indices]
    bounds=task.capacity_bounds
    max_pv=min(task.constraints.pv_limit_kw,bounds.pv_kw.upper) if bounds else task.constraints.pv_limit_kw
    max_boiler=bounds.boiler_kw_th.upper if bounds else max((c.boiler_kw_th for c in task.candidates or []),default=0)
    minimum_hp=max(0,data.heat_load_kw_th[peak]-max_boiler)/(task.devices.hp_cop if task.devices else 1)
    min_battery=max(0,values[peak]+minimum_hp-task.constraints.grid_limit_kw-max_pv*data.pv_per_kw[peak])
    second=float(np.sort(values)[-2]) if n>1 else float(values[0])
    summary=(f'当前输入{n}个区间（每区间{data.step_hours:g}小时）电负荷峰值{values[peak]:.2f}kW，发生于{data.timestamps[peak].isoformat()}；第二大值{second:.2f}kW，99分位数{np.percentile(values,99):.2f}kW。'
        f'按相邻差值>100kW且大值>小值8倍的既有规则，检出{len(jumps)}个跳变。当前购电上限{task.constraints.grid_limit_kw:.2f}kW。'
        f'无PV/储能的电网基线至少需要覆盖原电峰值{values[peak]:.2f}kW（尚未加热泵用电）；在当前PV/锅炉最大容量下，该峰值时段还要求至少{min_battery:.2f}kW放电功率，'
        '这只是瞬时必要条件，不证明电池能量或SOC足够。全年案例的默认购电上限和容量上界按原峰值量级设置，异常峰值会改变可行域，'
        '但不等于优化一定选择这些上界。跳变真实性和回路关系尚未核实，不能据此认定测量错误或替换原值。')
    return PeakDiagnostics(source_id=data.source_ids['electric_load_kw'],source_category=next((s.category for s in task.sources if s.source_id==data.source_ids['electric_load_kw']),'unknown'),records=n,peak_timestamp=data.timestamps[peak].isoformat(),peak_kw=float(values[peak]),
        second_highest_kw=second,percentile_99_kw=float(np.percentile(values,99)),grid_limit_kw=task.constraints.grid_limit_kw,
        baseline_no_pv_storage_required_grid_kw=float(values[peak]),peak_necessary_battery_power_kw=float(min_battery),
        configured_capacity_bounds=bounds.model_dump() if bounds else {},jumps=jumps,peak_neighbors=neighbors(peak),summary=summary)


def export_diagnostics(diagnostic,directory):
    p=Path(directory);p.mkdir(parents=True,exist_ok=True)
    (p/'peak_diagnostics.json').write_text(diagnostic.model_dump_json(indent=2),encoding='utf-8')
    lines=['# 峰值与邻近时段诊断',diagnostic.summary,diagnostic.treatment,'|时间|电负荷 kW|仿真/输入热负荷 kW_th|单位PV出力|','|---|---:|---:|---:|']
    lines.extend(f"|{r['timestamp']}|{r['electric_load_kw']:.6f}|{r['heat_load_kw_th']:.6f}|{r['pv_per_kw']:.6f}|" for r in diagnostic.peak_neighbors)
    for event in diagnostic.jumps:
        lines.append(f"跳变：{event['timestamp']}，{event['previous_kw']:.6f}→{event['current_kw']:.6f}kW。")
    (p/'peak_diagnostics.md').write_text('\n\n'.join(lines),encoding='utf-8')
    return {'json':str(p/'peak_diagnostics.json'),'markdown':str(p/'peak_diagnostics.md')}
