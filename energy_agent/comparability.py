"""One deterministic comparison-basis decision for reports, UI and dialogue."""
from typing import Literal
from pydantic import Field

from .modifications import fingerprint
from .schemas import Model


class BasisCheck(Model):
    field: str
    label: str
    group: Literal['period','service','emissions','economics','resource']
    same: bool
    previous_sha256: str
    current_sha256: str


class ComparisonBasis(Model):
    kind: Literal['A_same_basis','B_economic_sensitivity','C_input_sensitivity','D_mixed_sensitivity']
    directly_comparable: bool
    checks: list[BasisCheck]
    changed_labels: list[str] = Field(default_factory=list)
    summary: str
    note: str = '该判断核对已声明输入口径，不代表来源、工程假设或实测边界已获外部核实。原始差值为当前减基准；不同候选ID不强行配对。'


def compare_basis(previous,current) -> ComparisonBasis:
    checks=[]
    def check(field,label,group,a,b):
        left,right=fingerprint(a),fingerprint(b)
        checks.append(BasisCheck(field=field,label=label,group=group,same=left==right,previous_sha256=left,current_sha256=right))
    def context(task,fields):
        c=task.case_context
        return {k:getattr(c,k) for k in fields} if c else {'boundary':'模型默认单节点常规电与供热','supply':'逐时足额，无缺供'}
    def source(task,key):
        if task.data is None:return None
        sid=task.data.source_ids.get(key)
        s=next((s for s in task.sources if s.source_id==sid),None)
        return s.model_dump(mode='json',exclude={'source_id'}) if s else None
    def data_check(key,label,group):
        a,b=previous.data,current.data
        check('data.'+key,label,group,{'values':getattr(a,key) if a else None,'unit':a.units.get(key) if a else None},
            {'values':getattr(b,key) if b else None,'unit':b.units.get(key) if b else None})
    a,b=previous.data,current.data
    check('period','评估时段、步长与完整年/快速模式','period',
        [a.timestamps,a.step_hours,previous.resolution] if a else None,[b.timestamps,b.step_hours,current.resolution] if b else None)
    check('boundary','电热服务与计量边界','service',[previous.assessment_mode,context(previous,['boundary','excluded','timestamp_convention'])],
          [current.assessment_mode,context(current,['boundary','excluded','timestamp_convention'])])
    for key,label in [('electric_load_kw','常规电负荷'),('heat_load_kw_th','供热负荷')]:data_check(key,label,'service')
    check('emission_species','排放物质','emissions',previous.emission_species,current.emission_species)
    # The model always includes operational grid+fuel emissions, excluding
    # embodied emissions. Factor source conditions add their declared scope.
    check('emission_scope','运行排放范围与因子来源条件','emissions',
        {key:source(previous,key) for key in ('grid_emission_factor','gas_emission_factor')},
        {key:source(current,key) for key in ('grid_emission_factor','gas_emission_factor')})
    for key,label in [('grid_emission_factor','电网运行排放因子'),('gas_emission_factor','燃气运行排放因子')]:data_check(key,label,'emissions')
    for key,label in [('electricity_price','电价'),('gas_price','燃气价格')]:data_check(key,label,'economics')
    check('economics','规划年数、折现率、寿命、更换、残值及维护假设','economics',previous.economics,current.economics)
    cost_fields=('pv_cost_per_kw','battery_cost_per_kwh','battery_power_cost_per_kw','hp_cost_per_kw_th','boiler_cost_per_kw_th','installation_fraction','grid_connection_cost_yuan')
    def device_values(task,fields):return {k:getattr(task.devices,k) for k in fields} if task.devices else None
    check('device_costs','设备单价、安装费与接入投资假设','economics',device_values(previous,cost_fields),device_values(current,cost_fields))
    check('investment_scope','既有/新增投资边界','economics',context(previous,['investment_scope']),context(current,['investment_scope']))
    physical=[k for k in type(previous.devices).model_fields if k not in (*cost_fields,'source_id')] if previous.devices else []
    check('device_physics','效率、COP与SOC物理假设','resource',device_values(previous,physical),device_values(current,physical))
    data_check('pv_per_kw','同期光伏资源','resource')
    changed=[c for c in checks if not c.same];economic=any(c.group=='economics' for c in changed);other=any(c.group!='economics' for c in changed)
    kind='D_mixed_sensitivity' if economic and other else 'B_economic_sensitivity' if economic else 'C_input_sensitivity' if other else 'A_same_basis'
    labels=[c.label for c in changed]
    summaries={
        'A_same_basis':'比较口径A：同一口径下的预算/配置比较；时段、负荷与服务边界、运行排放口径及经济假设一致。',
        'B_economic_sensitivity':'比较口径B：经济假设敏感性比较；'+ '、'.join(labels)+'发生变化。原始数值与差值可展示，不能直接表述为同口径下节省的生命周期成本。',
        'C_input_sensitivity':'比较口径C：数据/服务/排放/资源假设敏感性比较；'+'、'.join(labels)+'发生变化。差值同时受到输入变化影响，不能全部归因于设备配置改善。',
        'D_mixed_sensitivity':'比较口径D：经济与输入口径同时变化；'+'、'.join(labels)+'发生变化。只展示原始数值与差值，不解释为同口径成本节省或纯设备配置改善。',
    }
    return ComparisonBasis(kind=kind,directly_comparable=not changed,checks=checks,changed_labels=labels,summary=summaries[kind])


def basis_summary(run):
    raw=run.changes.get('comparison_basis')
    return ComparisonBasis.model_validate(raw).summary if raw else '缺少前后口径核对证据，尚未证明结果可直接比较。'
