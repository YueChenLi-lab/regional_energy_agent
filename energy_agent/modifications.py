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
from .edit_semantics import EditMeaningError, has_negation, is_explicit_preservation, parse_edit


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
        # Negation scope is retained as a whole; never detach 不要/不要把
        # from its subject and accidentally authorize the positive operation.
        if has_negation(clause):
            pieces.append(clause);continue
        # A list with a shared preservation predicate stays together. Mixed
        # edits/keeps are split at subjects, including sentences without commas.
        if re.search(r'不变|保持|保留|维持|不要取消|不取消|无需取消|禁止取消|不能取消',clause) and not re.search(r'减少|降低|下调|削减|增加|提高|降到|降至|改为|设为|调整为',clause):
            pieces.append(clause);continue
        starts=[m.start() for m in re.finditer(pattern,clause)]
        cuts=sorted(set([0,*starts,len(clause)]))
        pieces.extend(clause[a:b].strip() for a,b in zip(cuts,cuts[1:]) if clause[a:b].strip())
    return pieces


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
    aliases={'budget':('预算',),'electric_load':('电负荷','用电需求','电力需求'),'heat_load':('热负荷','热需求','供热'),
        'discount_rate':('折现率',),'horizon_years':('规划期','规划年数','评价期'),
        'grid_limit_kw':('购电上限',),'pv_limit_kw':('光伏场地上限',),
        'emission_limit':('排放上限','排放约束','碳上限')}
    for field,answer in resolved.items():
        if field.startswith('clause_'):
            clauses=[c for c in clauses if 'clause_'+hashlib.sha256(c.encode()).hexdigest()[:10]!=field]
            if not re.search('取消|不做|不修改|不考虑|去掉',answer):clauses.extend(_clauses(answer))
            continue
        if field=='request_details':clauses.extend(_clauses(answer));continue
        names=aliases.get(field,(field,));prefix=names[0]
        clauses=[c for c in clauses if not any(name in c for name in names) or is_explicit_preservation(c)]
        clauses.extend(_clauses(answer if any(name in answer for name in names) else prefix+answer))
    def need(field,question,reason='数值、单位或含义不明确，未应用修改'):
        if not any(m.field==field for m in missing):missing.append(MissingField(field=field,question=question,reason=reason))
    def record(key,value,old,unit,clause):
        if key in seen and seen[key]!=value:
            need(key,'同一参数给出了冲突值，请明确最终采用哪个值。','矛盾修改不能猜测优先级');return
        seen[key]=value
        edits.append({'field':key,'before':old,'after':value,'unit':unit,'evidence':clause})
    for c in clauses:
        counts=(len(edits),len(missing),len(preserves))
        clause_id='clause_'+hashlib.sha256(c.encode()).hexdigest()[:10]
        if has_negation(c) and not is_explicit_preservation(c):
            need(clause_id,'修改包含否定，请明确是否修改和最终目标：'+c+'。','保留否定作用范围；未执行被否定的修改')
            continue
        keep=bool(re.search(r'不变|保持|保留|维持|不要取消|不取消|无需取消|禁止取消|不能取消',c))
        if keep:
            asset=next((value for name,value in ASSETS.items() if name in c),None)
            if '寿命' in c or '维护' in c:
                field='lifetime_years' if '寿命' in c else 'fixed_om_fraction'
                preserves.extend(k for k in PATHS if k.startswith('economics.assets.') and k.endswith('.'+field) and (asset is None or '.'+asset+'.' in k) and k not in preserves)
            for name,key in PRESERVES.items():
                if name in c and key not in preserves:preserves.append(key)
        def parsed(current,dimension,field=clause_id):
            try:return parse_edit(c,current,dimension,species=task.emission_species)
            except EditMeaningError as exc:
                question=('预算要如何修改？请明确增减幅度、原来比例，或最终金额（元/万元）。' if field=='budget' else '请明确该项修改：')
                need(field,question+' '+str(exc),str(exc));return None
        def edited(key,result,old):
            count=len(edits)
            record(key,result.value,old,result.canonical_unit,c)
            if len(edits)>count:edits[-1].update(operation=result.operation,input_unit=result.input_unit)
        if '预算' in c and not (keep and not re.search(r'减少|增加|降低|提高|下调|上调|降到|降至|设为|改为|调整为',c)):
            result=parsed(task.constraints.budget_yuan,'money','budget')
            if result:
                raw['budget_multiplier' if result.multiplier is not None else 'budget_yuan']=result.multiplier if result.multiplier is not None else result.value
                edited('constraints.budget_yuan',result,task.constraints.budget_yuan)
        for names,key in [(('电负荷','用电需求','电力需求'),'electric_demand_scale'),(('热负荷','热需求','供热需求','供热要求'),'heat_demand_scale')]:
            if any(name in c for name in names) and not keep:
                result=parsed(1,'scale','electric_load' if key.startswith('electric') else 'heat_load')
                if result:
                    raw[key]=result.value;edited('data.electric_load_kw' if key.startswith('electric') else 'data.heat_load_kw_th',result,1)
        if re.search('折现率|规划期|规划年数|评价期|寿命|维护|运维',c) and not keep:
            if task.economics is None:
                need('economics','当前没有全年经济参数，请先建立经济评价条件。');continue
            if '折现率' in c:
                result=parsed(task.economics.discount_rate,'rate','discount_rate')
                if result:eco['discount_rate']=result.value;edited('economics.discount_rate',result,task.economics.discount_rate)
            elif re.search('规划期|规划年数|评价期',c):
                result=parsed(task.economics.horizon_years,'years','horizon_years')
                if result:eco['horizon_years']=result.value;edited('economics.horizon_years',result,task.economics.horizon_years)
            else:
                asset=next((value for name,value in ASSETS.items() if name in c),None)
                if '寿命' in c:
                    if not asset:need(clause_id,'请明确哪种设备的寿命。');continue
                    prior=task.economics.assets[asset].lifetime_years
                    result=parsed(prior,'years')
                    if result:
                        eco.setdefault('assets',{}).setdefault(asset,{})['lifetime_years']=result.value
                        edited('economics.assets.'+asset+'.lifetime_years',result,prior)
                elif re.search('变动|按放电|每.*kWh',c,re.I):
                    var_key={'battery_energy_kwh':'battery_variable_om_per_kwh','hp_kw_th':'hp_variable_om_per_kwh_th','boiler_kw_th':'boiler_variable_om_per_kwh_th'}.get(asset)
                    if not var_key:need(clause_id,'请明确设备与按电量/热量收费的维护单价。');continue
                    prior=getattr(task.economics,var_key)
                    result=parsed(prior,'electric_om' if asset=='battery_energy_kwh' else 'thermal_om')
                    if result:eco[var_key]=result.value;edited('economics.'+var_key,result,prior)
                elif re.search('项目.*(?:额外|附加).*固定|(?:额外|附加).*项目.*固定',c):
                    prior=task.economics.additional_fixed_om_yuan_per_year
                    result=parsed(prior,'annual_money')
                    if result:eco['additional_fixed_om_yuan_per_year']=result.value;edited('economics.additional_fixed_om_yuan_per_year',result,prior)
                else:
                    if not asset:need(clause_id,'请明确设备和年维护费率（占含安装初投的比例），或项目额外年固定费用。');continue
                    prior=task.economics.assets[asset].fixed_om_fraction
                    result=parsed(prior,'rate')
                    if result:
                        eco.setdefault('assets',{}).setdefault(asset,{})['fixed_om_fraction']=result.value
                        edited('economics.assets.'+asset+'.fixed_om_fraction',result,prior)
        if re.search('排放上限|排放约束|碳上限',c) and not keep:
            if re.search('取消|移除|清除|不设',c):raw['clear_emission_limit']=True;record('constraints.emission_limit_kg',None,task.constraints.emission_limit_kg,'kg'+task.emission_species,c)
            else:
                # Relative changes require a finite confirmed starting value.
                if task.constraints.emission_limit_kg is None and re.search('增加|减少|提高|降低',c) and not re.search('到|至',c):
                    need(clause_id,'当前未设排放上限，不能计算相对变化；请给出绝对目标。');continue
                result=parsed(task.constraints.emission_limit_kg or 0,'emissions','emission_limit')
                if result:raw['emission_limit_kg']=result.value;edited('constraints.emission_limit_kg',result,task.constraints.emission_limit_kg)
        for token,key in [('购电上限','grid_limit_kw'),('光伏场地上限','pv_limit_kw')]:
            if token in c and not keep:
                prior=getattr(task.constraints,key);result=parsed(prior,'power',key)
                if result:raw[key]=result.value;edited('constraints.'+key,result,prior)
        if counts==(len(edits),len(missing),len(preserves)) and not keep and re.search('改为|设为|减少|降低|削减|增加|提高|降到|降至|寿命|维护|上限|负荷',c):
            need(clause_id,'该项修改尚未明确或未支持：'+c+'。请改述为支持的参数，或明确取消这一项。','该句不能静默忽略')
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
