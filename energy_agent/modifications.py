"""Deterministic, deliberately bounded Chinese edit contracts.

LLMs propose operations. This module independently authorizes fields/units and
values, never lets a model drop an unrelated constraint, and refuses ambiguity.
"""
import hashlib
import json
import re
from decimal import Decimal

from pydantic import Field

from .schemas import Model, TaskPatch


class MissingField(Model):
    field: str
    question: str
    reason: str


class ModificationContract(Model):
    base_run_id: str
    resolved_request: str = ""
    input_version: int
    patch: TaskPatch
    edits: list[dict] = Field(default_factory=list)
    preserves: list[str] = Field(default_factory=list)
    unchanged: list[str] = Field(default_factory=list)
    missing: list[MissingField] = Field(default_factory=list)

    @property
    def ready(self):
        return not self.missing and bool(self.edits)


ASSETS = {
    '电池功率变换器':'battery_power_kw','电池功率':'battery_power_kw','PCS':'battery_power_kw',
    '电池能量':'battery_energy_kwh','电池':'battery_energy_kwh','储能':'battery_energy_kwh',
    '光伏':'pv_kw','热泵':'hp_kw_th','锅炉':'boiler_kw_th',
}
PRESERVES = {'供热':'heat_load','热负荷':'heat_load','电负荷':'electric_load','用电需求':'electric_load','电力需求':'electric_load',
    '评估时段':'period','时段':'period','预算':'budget','排放上限':'emission_limit','排放约束':'emission_limit',
    '购电上限':'grid_limit','光伏场地':'pv_limit','经济参数':'economics','折现率':'economics.discount_rate','规划期':'economics.horizon_years'}
PATHS = {'heat_load':'data.heat_load_kw_th','electric_load':'data.electric_load_kw',
    'period':'data.timestamps','budget':'constraints.budget_yuan','emission_limit':'constraints.emission_limit_kg',
    'grid_limit':'constraints.grid_limit_kw','pv_limit':'constraints.pv_limit_kw','economics':'economics'}
for key in ('discount_rate','horizon_years','additional_fixed_om_yuan_per_year','battery_variable_om_per_kwh','hp_variable_om_per_kwh_th','boiler_variable_om_per_kwh_th'):
    PATHS['economics.'+key]='economics.'+key
for asset in sorted(set(ASSETS.values())):
    for field in ('lifetime_years','fixed_om_fraction'):
        key='economics.assets.'+asset+'.'+field
        PATHS[key]=key
NUM = r'(\d+(?:\.\d+)?)'


def get_path(obj,path):
    for key in path.split('.'):
        if obj is None:return None
        obj = obj[key] if isinstance(obj,dict) else getattr(obj,key)
    return obj


def fingerprint(value):
    def canonical(item):
        if hasattr(item,'model_dump'):item=item.model_dump(mode='json',exclude={'source_id'})
        if isinstance(item,bool):return item
        if isinstance(item,(int,float)):return {'number':str(Decimal(str(item)).normalize())}
        if isinstance(item,dict):return {k:canonical(v) for k,v in item.items()}
        if isinstance(item,(list,tuple)):return [canonical(v) for v in item]
        return item
    return hashlib.sha256(json.dumps(canonical(value),sort_keys=True,default=str).encode()).hexdigest()


def _normalize(text):
    text=text.replace('％','%').replace('百分之十五','15%').replace('百分之二十','20%').replace('百分之三十','30%').replace('百分之十','10%')
    return re.sub(r'百分之'+NUM,lambda m:m[1]+'%',text)


def _clauses(text):
    pieces=[]
    subjects=['预算','折现率','规划期','规划年数','评价期','电负荷','用电需求','电力需求','热负荷','热需求','供热','购电上限','光伏场地上限','排放上限','排放约束','碳上限',*ASSETS]
    pattern=r'(?:保持|保留|维持|将|把|不要取消|不取消|无需取消|禁止取消|不能取消)?(?:'+ '|'.join(re.escape(x) for x in sorted(subjects,key=len,reverse=True))+r')'
    for clause in re.split(r'[，,。；;\n]',_normalize(text)):
        clause=clause.strip()
        if not clause:continue
        # A list with a shared preservation predicate stays together. Mixed
        # edits/keeps are split at subjects, including sentences without commas.
        if re.search(r'不变|保持|保留|维持|不要取消|不取消|无需取消|禁止取消|不能取消',clause) and not re.search(r'减少|降低|下调|削减|增加|提高|降到|降至|改为|设为|调整为',clause):
            pieces.append(clause);continue
        starts=[m.start() for m in re.finditer(pattern,clause)]
        cuts=sorted(set([0,*starts,len(clause)]))
        pieces.extend(clause[a:b].strip() for a,b in zip(cuts,cuts[1:]) if clause[a:b].strip())
    return pieces


def _amount(clause):
    match=re.search(NUM+r'\s*(万元|万|元)',clause)
    return (float(Decimal(match[1])*(10000 if match[2] in ('万元','万') else 1))) if match else None


def _relative(clause):
    match=re.search(NUM+r'\s*%',clause)
    if not match:return None
    value=Decimal(match[1])/100
    if re.search(r'降到|降至|减少到|减少至|降低到|降低至|削减至|下调至|减至|变为原来|到原来|原来的|原来.*的',clause):return float(value)
    if re.search(r'减少|降低|削减|下调|缩减|下降',clause):return float(1-value)
    if re.search(r'增加|提高|上调|增长|上升',clause):return float(1+value)
    return None


def _is_target(clause):
    return bool(re.search(r'降到|降至|减少到|减少至|降低到|降低至|削减至|下调至|减至|增加到|增加至|提高到|提高至|上调至',clause))


def _budget(clause,current):
    if re.search(r'[-－负]\s*\d|至少|不低于|或者|或|范围',clause):return None
    money=list(re.finditer(NUM+r'\s*(万元|万|元)',clause))
    if len(money)>1:
        if len(money)!=2 or '从' not in clause or not re.search('到|至',clause):return None
        start=float(Decimal(money[0][1])*(10000 if money[0][2] in ('万','万元') else 1))
        end=float(Decimal(money[1][1])*(10000 if money[1][2] in ('万','万元') else 1))
        return {'budget_yuan':end} if abs(start-current)<=1e-6 else None
    factor=_relative(clause)
    if factor is not None:return {'budget_multiplier':factor}
    amount=_amount(clause)
    if amount is not None:
        if re.search(r'减少到|减少至|降低到|降低至|削减至|下调至|减至',clause):pass
        elif re.search(r'减少|降低|削减|下调|缩减',clause):amount=current-amount
        elif re.search(r'增加|提高|上调',clause):amount=current+amount
        return {'budget_yuan':amount}
    return None


def _flat(patch):
    raw=patch.model_dump(exclude_none=True,exclude_defaults=True)
    for key in ('preserve_heat','preserve_conditions','unsupported_demands'):raw.pop(key,None)
    def flatten(value,prefix=''):
        out={}
        for k,v in value.items():
            key=prefix+k
            if isinstance(v,dict):out.update(flatten(v,key+'.'))
            else:out[key]=v
        return out
    return flatten(raw)


def compile_contract(text,previous,answers=()):
    task=previous.task
    raw={};eco={};edits=[];missing=[];preserves=[];seen={}
    clauses=_clauses(text)
    # An answer is bound to an explicitly pending field. It is never parsed as a
    # new task. Original clauses for that field are superseded, preserves remain.
    resolved={a['field']:a['text'] for a in answers}
    aliases={'budget':'预算','electric_load':'电负荷','heat_load':'热负荷','discount_rate':'折现率','horizon_years':'规划期'}
    for field,answer in resolved.items():
        if field.startswith('clause_'):
            clauses=[c for c in clauses if 'clause_'+hashlib.sha256(c.encode()).hexdigest()[:10]!=field]
            if not re.search('取消|不做|不修改|不考虑|去掉',answer):clauses.extend(_clauses(answer))
            continue
        if field=='request_details':clauses.extend(_clauses(answer));continue
        prefix=aliases.get(field,field)
        clauses=[c for c in clauses if prefix not in c or re.search(r'不变|保持|保留',c)]
        clauses.extend(_clauses(answer if prefix in answer else prefix+answer))
    def need(field,question,reason='数值、单位或含义不明确，未应用修改'):
        if not any(m.field==field for m in missing):missing.append(MissingField(field=field,question=question,reason=reason))
    def record(key,value,old,unit,clause):
        if key in seen and seen[key]!=value:
            need(key,'同一参数给出了冲突值，请明确最终采用哪个值。','矛盾修改不能猜测优先级');return
        seen[key]=value
        edits.append({'field':key,'before':old,'after':value,'unit':unit,'evidence':clause})
    for c in clauses:
        counts=(len(edits),len(missing),len(preserves))
        if re.search(r'[-－负]\s*\d|或者|或|至少|不低于|范围|\d\s*(?:~|～|—)\s*\d',c):
            need('clause_'+hashlib.sha256(c.encode()).hexdigest()[:10],
                '请给出该项修改唯一、有效且无歧义的数值：'+c+'。','负值、多个选项或范围不能取其中一个正数执行')
            continue
        keep=bool(re.search(r'不变|保持|保留|维持|不要取消|不取消|无需取消|禁止取消|不能取消',c))
        if keep:
            asset=next((value for name,value in ASSETS.items() if name in c),None)
            if '寿命' in c or '维护' in c:
                field='lifetime_years' if '寿命' in c else 'fixed_om_fraction'
                preserves.extend(k for k in PATHS if k.startswith('economics.assets.') and k.endswith('.'+field) and (asset is None or '.'+asset+'.' in k) and k not in preserves)
            for name,key in PRESERVES.items():
                if name in c and key not in preserves:preserves.append(key)
        if '预算' in c and not (keep and not re.search(r'减少|增加|降低|降到|降至|设为|改为|调整为',c)):
            proposal=_budget(c,task.constraints.budget_yuan)
            if proposal:
                for k,v in proposal.items():raw[k]=v;record('constraints.budget_yuan',task.constraints.budget_yuan*v if k=='budget_multiplier' else v,task.constraints.budget_yuan,'元',c)
            else:need('budget','预算要减少多少？请说明减少百分比、降到原来比例，或明确金额（元/万元）。')
        for names,key in [(('电负荷','用电需求','电力需求'),'electric_demand_scale'),(('热负荷','热需求','供热需求','供热要求'),'heat_demand_scale')]:
            if any(name in c for name in names) and not keep:
                factor=_relative(c)
                if factor is None:need('electric_load' if key.startswith('electric') else 'heat_load','请明确该负荷的修改比例。')
                else:raw[key]=factor;record('data.electric_load_kw' if key.startswith('electric') else 'data.heat_load_kw_th',factor,1,'相对基准倍数',c)
        if '折现率' in c and not keep:
            if task.economics is None:need('economics','当前没有全年经济参数，请先建立经济评价条件。');continue
            match=re.search(NUM+r'\s*(%|个百分点)?',c)
            if not match:need('discount_rate','请给出折现率（%或0到1的小数）。');continue
            v=float(Decimal(match[1])/(100 if match[2] else 1))
            relative=_relative(c)
            if match[2]=='个百分点':v=task.economics.discount_rate+(-v if re.search('减少|降低|下降|下调',c) else v)
            elif relative is not None and (not _is_target(c) or '原来' in c):v=task.economics.discount_rate*relative
            eco['discount_rate']=v;record('economics.discount_rate',v,task.economics.discount_rate,'1',c)
        if re.search('规划期|规划年数|评价期',c) and not keep:
            match=re.search(NUM+r'\s*年',c)
            if not match:need('horizon_years','请明确规划期年数。')
            elif task.economics is None:need('economics','请先提供完整年度经济评价条件。')
            else:
                value=float(match[1]);prior=task.economics.horizon_years
                if not _is_target(c):
                    if re.search('减少|降低|削减|下调|缩减',c):value=prior-value
                    elif re.search('增加|提高|上调|延长',c):value=prior+value
                eco['horizon_years']=value;record('economics.horizon_years',value,prior,'年',c)
        if re.search('寿命|维护|运维',c) and not keep:
            asset=next((value for name,value in ASSETS.items() if name in c),None)
            if task.economics is None:need('economics','请先提供完整年度经济参数。');continue
            if '寿命' in c:
                m=re.search(NUM+r'\s*年',c)
                if not asset or not m:need('asset_lifetime','请说明哪种设备的寿命及年数。')
                else:
                    value=float(m[1])
                    if not _is_target(c):
                        if re.search('减少|降低|削减|下调|缩减',c):value=task.economics.assets[asset].lifetime_years-value
                        elif re.search('增加|提高|上调|延长',c):value=task.economics.assets[asset].lifetime_years+value
                    eco.setdefault('assets',{}).setdefault(asset,{})['lifetime_years']=value
                    record('economics.assets.'+asset+'.lifetime_years',value,task.economics.assets[asset].lifetime_years,'年',c)
            elif re.search('变动|按放电|每.*kWh',c,re.I):
                var_key={'battery_energy_kwh':'battery_variable_om_per_kwh','hp_kw_th':'hp_variable_om_per_kwh_th','boiler_kw_th':'boiler_variable_om_per_kwh_th'}.get(asset)
                m=re.search(NUM+r'\s*元\s*/\s*kWh(_th)?',c,re.I)
                if not var_key or not m or (asset in ('hp_kw_th','boiler_kw_th') and not m[2]):
                    need('variable_maintenance','请明确设备及按放电kWh/供热kWh_th收费的变动维护单价。')
                else:
                    value=float(m[1]);eco[var_key]=value
                    record('economics.'+var_key,value,getattr(task.economics,var_key),'元/kWh' if asset=='battery_energy_kwh' else '元/kWh_th',c)
            elif re.search('项目.*(?:额外|附加).*固定|(?:额外|附加).*项目.*固定',c):
                value=_amount(c)
                if value is None:need('additional_fixed_om','请给出项目额外年固定维护费用（元/年或万元/年）。')
                else:
                    prior=task.economics.additional_fixed_om_yuan_per_year
                    if not _is_target(c):
                        if re.search('减少|降低|下调',c):value=prior-value
                        elif re.search('增加|提高|上调',c):value=prior+value
                    eco['additional_fixed_om_yuan_per_year']=value;record('economics.additional_fixed_om_yuan_per_year',value,prior,'元/年',c)
            else:
                m=re.search(NUM+r'\s*%',c)
                if not asset or not m:need('asset_maintenance','请明确设备和年固定维护费率（占初始设备含安装投资的%），或项目额外年固定费用。')
                else:
                    value=float(Decimal(m[1])/100)
                    relative=_relative(c)
                    if relative is not None and (not _is_target(c) or '原来' in c):value=task.economics.assets[asset].fixed_om_fraction*relative
                    eco.setdefault('assets',{}).setdefault(asset,{})['fixed_om_fraction']=value
                    record('economics.assets.'+asset+'.fixed_om_fraction',value,task.economics.assets[asset].fixed_om_fraction,'1/年',c)
        if re.search('排放上限|排放约束|碳上限',c) and not keep:
            if re.search('取消|移除|清除|不设',c):raw['clear_emission_limit']=True;record('constraints.emission_limit_kg',None,task.constraints.emission_limit_kg,'kg'+task.emission_species,c)
            else:
                m=re.search(NUM+r'\s*(吨|t|kg|千克)',c,re.I)
                if not m:need('emission_limit','请明确排放上限数值及kg/吨单位（沿用当前任务物质范围）。')
                else:raw['emission_limit_kg']=float(m[1])*(1000 if m[2] in ('吨','t') else 1);record('constraints.emission_limit_kg',raw['emission_limit_kg'],task.constraints.emission_limit_kg,'kg'+task.emission_species,c)
        for token,key in [('购电上限','grid_limit_kw'),('光伏场地上限','pv_limit_kw')]:
            if token in c and not keep:
                m=re.search(NUM+r'\s*kW',c,re.I)
                if not m:need(key,'请给出'+token+'，单位kW。')
                else:raw[key]=float(m[1]);record('constraints.'+key,float(m[1]),getattr(task.constraints,key),'kW',c)
        if counts==(len(edits),len(missing),len(preserves)) and not keep and re.search('改为|设为|减少|降低|削减|增加|提高|降到|降至|寿命|维护|上限|负荷',c):
            field='clause_'+hashlib.sha256(c.encode()).hexdigest()[:10]
            need(field,'该项修改尚未明确或未支持：'+c+'。请改述为支持的参数，或明确取消这一项。','该句不能静默忽略')
    if eco:raw['economics']=eco
    if 'heat_load' in preserves:raw['preserve_heat']=True
    # Preserve metadata is authorization supplied by the user, never an LLM edit.
    raw['preserve_conditions']=preserves
    if 'heat_load' in preserves and task.assessment_mode=='electric_only':need('heating_boundary','当前电侧任务未建模供热，请先明确供热边界与负荷。')
    for key in preserves:
        path=PATHS[key]
        if any(e['field']==path or e['field'].startswith(path+'.') for e in edits):
            need(key,'要求保持的条件同时被修改，请明确保留还是修改。','修改与保留条件矛盾')
    try:patch=TaskPatch.model_validate(raw)
    except ValueError:
        need('edit_conflict','参数超出范围或修改互相矛盾，请明确有效数值。');patch=TaskPatch()
    if not edits and not missing:need('request_details','请明确希望修改的参数、数值和需要保持的条件。')
    changed={e['field'] for e in edits}
    unchanged=[k for k,path in PATHS.items() if not any(p==path or p.startswith(path+'.') for p in changed)]
    if 'period' not in unchanged:unchanged.append('period')
    return ModificationContract(base_run_id=previous.run_id,resolved_request='，'.join(clauses),input_version=task.version,patch=patch,edits=edits,preserves=preserves,unchanged=unchanged,missing=missing)


def validate_proposal(proposal,contract):
    """Reject any numerical or constraint edit not independently requested."""
    if _flat(proposal)!=_flat(contract.patch):
        raise ValueError('相对预算或其他修改与授权契约不一致，包含未请求/遗漏/错误数值；未应用修改')
    if contract.patch.preserve_heat and not proposal.preserve_heat:
        raise ValueError('模型未声明保持供热条件，未应用修改')


def assert_preserved(before,after,contract):
    for key in set(contract.preserves+contract.unchanged):
        if fingerprint(get_path(before,PATHS[key]))!=fingerprint(get_path(after,PATHS[key])):
            raise ValueError('保留条件被改变：'+key)
    if before.data.step_hours!=after.data.step_hours or before.assessment_mode!=after.assessment_mode:
        raise ValueError('时间步长或服务模式被改变')
