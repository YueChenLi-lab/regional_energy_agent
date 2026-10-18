"""Confirmed-task actions, idempotent edits and numerical evidence-bound replies."""
import hashlib
import json
import re
from functools import wraps
from pathlib import Path
from typing import Literal

from pydantic import Field

from .agent import EnergyAgent, Tool, revise_task
from .frontier import SensitivityRequest, StudyResult, sensitivity_analysis
from .llm import LLMError, RuleClient, _preserve_unsupported
from .schemas import Model, RunResult, TaskPatch
from .modifications import (ModificationContract, MissingField, compile_contract, validate_proposal, assert_preserved)


class PlanningIntent(Model):
    operation: Literal['modify','clarify','evaluate','compare','sensitivity','report','explain']
    patch: TaskPatch | None = None
    question: str | None = Field(default=None,max_length=400)
    missing_fields: list[str] = Field(default_factory=list)


class FactClaim(Model):
    reference: str
    value: float


class GroundedExplanation(Model):
    run_id: str
    conclusion: Literal['可行且通过独立校验','无可行方案','待补信息或执行失败']
    claims: list[FactClaim] = Field(max_length=40)


class ConnectivityCheck(Model):
    status: Literal['ok']


class PendingDialog(Model):
    request_id: str
    original_request: str
    base_run_id: str
    input_version: int
    base_file: str
    confirmed_conditions: dict
    missing_fields: list[MissingField] = Field(default_factory=list)
    answers: list[dict] = Field(default_factory=list)
    generation: int = 1
    status: Literal["awaiting_answer", "ready", "completed", "cancelled"] = "awaiting_answer"
    history: list[dict] = Field(default_factory=list)


class ConversationReply(Model):
    status: Literal['clarification','completed','cancelled']
    text: str
    run: RunResult | None = None
    study: StudyResult | None = None
    request_id: str
    heat_unchanged: bool | None = None
    explanation_verified: bool = False
    pending: PendingDialog | None = None
    contract: ModificationContract | None = None


def heat_fingerprint(task):
    raw={'assessment_mode':task.assessment_mode,'timestamps':[t.isoformat() for t in task.data.timestamps],
         'step_hours':task.data.step_hours,'heat_kw_th':task.data.heat_load_kw_th,'supply':'every_interval_no_shedding'}
    return hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()


def current_facts(run):
    facts={'input_version':float(run.input_version)}
    for s in run.scenarios:
        root='scenarios.'+s.candidate.candidate_id+'.'
        for key in ('pv_kw','battery_power_kw','battery_energy_kwh','hp_kw_th','boiler_kw_th'):
            facts[root+key]=getattr(s.candidate,key)
        facts[root+'investment_yuan']=s.investment_yuan
        if s.validation.metrics:
            for key in ('operating_cost_yuan','emissions_kg','grid_kwh','gas_kwh_lhv'):
                facts[root+key]=getattr(s.validation.metrics,key)
        if s.economics:
            facts[root+'npv_cost_yuan']=s.economics.npv_cost_yuan
            facts[root+'horizon_operating_emissions_kg']=s.economics.horizon_operating_emissions_kg
    for item in run.changes.get('scenarios',[]):
        for key,value in item.items():
            if key.startswith('delta_') and isinstance(value,(int,float)):
                facts['changes.'+item['candidate_id']+'.'+key]=value
    return facts


def actual_conclusion(run):
    if run.state.value!='完成': return '待补信息或执行失败'
    return '可行且通过独立校验' if any(s.validation.valid for s in run.scenarios) else '无可行方案'


def validate_explanation(explanation,run):
    ex=GroundedExplanation.model_validate(explanation)
    if ex.run_id!=run.run_id or ex.conclusion!=actual_conclusion(run):
        raise LLMError('模型解释引用了旧运行或错误的可行性结论，已拒绝显示')
    facts=current_facts(run)
    if any(s.validation.valid for s in run.scenarios) and not ex.claims:
        raise LLMError('模型解释缺少可核对结果引用')
    for claim in ex.claims:
        if claim.reference not in facts or abs(claim.value-facts[claim.reference])>1e-6:
            raise LLMError('模型解释数字与当前运行的字段不一致，已拒绝显示')
    return ex


_LABELS={'investment_yuan':'初始投资（元）','npv_cost_yuan':'规划期NPV（元）','emissions_kg':'评估期运行排放（kg，物质见任务）',
         'operating_cost_yuan':'评估期购能费（元）','pv_kw':'光伏（kW）','battery_power_kw':'电池功率（kW）',
         'battery_energy_kwh':'电池能量（kWh）','hp_kw_th':'热泵（kW_th）','boiler_kw_th':'锅炉（kW_th）'}


_ASSET_LABELS={'pv_kw':'光伏','battery_power_kw':'电池功率变换器','battery_energy_kwh':'电池能量部分','hp_kw_th':'热泵','boiler_kw_th':'锅炉'}
_ECON_LABELS={'discount_rate':'折现率','horizon_years':'规划期','additional_fixed_om_yuan_per_year':'项目额外年固定维护费',
    'battery_variable_om_per_kwh':'电池按放电量维护单价','hp_variable_om_per_kwh_th':'热泵变动维护单价','boiler_variable_om_per_kwh_th':'锅炉变动维护单价'}


def _edit_label(path):
    if path.startswith('economics.assets.'):
        parts=path.split('.')
        return _ASSET_LABELS[parts[2]]+('寿命' if parts[3]=='lifetime_years' else '年固定维护费率')
    return _ECON_LABELS.get(path.removeprefix('economics.'),path)


def _edit_value(value,path,unit):
    if value is None:return '未设置'
    if path.endswith(('discount_rate','fixed_om_fraction')):return f'{value:.2%}'
    if unit=='年':return f'{value:g}年'
    if unit.startswith('元'):return f'{value:,.2f}{unit}'
    if unit=='相对基准倍数':return f'{value:g}倍'
    return f'{value:g}{unit}' if isinstance(value,(float,int)) else str(value)


def deterministic_reply(run,previous=None,contract=None):
    """All values, differences and units are rendered locally from tool results."""
    annual=run.task.resolution=='full_year'
    period='年度' if annual else '评估期'
    lines=[f'当前运行 {run.run_id}，输入版本 {run.input_version}：{actual_conclusion(run)}。运行排放单位kg{run.task.emission_species}。']
    if previous:lines.append(f'基准运行：{previous.run_id}，版本{previous.input_version}。')
    if contract:
        names={'constraints.budget_yuan':'初始投资预算','economics.discount_rate':'折现率','economics.horizon_years':'规划期','data.electric_load_kw':'电负荷倍数','data.heat_load_kw_th':'热负荷倍数'}
        for edit in contract.edits:
            lines.append(f"- 修改：{names.get(edit['field'],_edit_label(edit['field']))}，{_edit_value(edit['before'],edit['field'],edit['unit'])} → {_edit_value(edit['after'],edit['field'],edit['unit'])}。")
        keep_names={'heat_load':'供热负荷与逐时足额保障','electric_load':'电负荷','period':'评估时段和步长','budget':'预算','emission_limit':'排放上限','grid_limit':'购电上限','pv_limit':'光伏场地限制','economics':'经济参数'}
        keys=list(dict.fromkeys(contract.preserves+contract.unchanged))
        if 'economics' in keys:keys=[k for k in keys if not k.startswith('economics.')]
        labels=[]
        for key in keys:
            if key.startswith('economics.assets.'):
                label='其余设备寿命' if key.endswith('lifetime_years') else '其余设备年维护费率'
            else:label=keep_names.get(key,_edit_label(key))
            if label not in labels:labels.append(label)
        lines.append('保持：'+'、'.join(labels)+'。')
    old={s.candidate.candidate_id:s for s in previous.scenarios} if previous else {}
    for s in run.scenarios:
        state={'optimal':'当前模型及容差内已证明最优','feasible_limit':'已有可行解，未证明最优','no_solution_limit':'达到时限，未找到可行解'}.get(s.dispatch.status,s.dispatch.status)
        lines.append(f'方案 {s.candidate.candidate_id}：{state}；独立校验'+('通过。' if s.validation.valid else '未通过或无可用解。'))
        if not s.validation.valid:
            lines.extend('- '+r for r in s.dispatch.reasons)
            continue
        before=old.get(s.candidate.candidate_id)
        for key,label in _LABELS.items():
            if key in ('investment_yuan','npv_cost_yuan','emissions_kg','operating_cost_yuan'):continue
            value=getattr(s.candidate,key)
            delta=f'，同ID方案变化 {value-getattr(before.candidate,key):+.2f}' if before and before.validation.valid else ''
            lines.append(f'- {label}：{value:.2f}{delta}。')
        metrics=[('初始投资','元',s.investment_yuan,before.investment_yuan if before and before.validation.valid else None)]
        if s.economics:
            metrics.append(('规划期NPV','元',s.economics.npv_cost_yuan,before.economics.npv_cost_yuan if before and before.economics else None))
        metrics.append((period+'运行排放','kg'+run.task.emission_species,s.validation.metrics.emissions_kg,before.validation.metrics.emissions_kg if before and before.validation.valid else None))
        metrics.append((period+'购能费','元',s.validation.metrics.operating_cost_yuan,before.validation.metrics.operating_cost_yuan if before and before.validation.valid else None))
        for label,unit,value,prior in metrics:
            delta=f'；同ID方案变化 {value-prior:+,.2f}{unit}' if prior is not None else ''
            lines.append(f'- {label}：{value:,.2f}{unit}{delta}。')
    if run.comparison:lines.append('推荐依据：'+run.comparison.explanation)
    if run.task.economics:
        e=run.task.economics
        lines.append(f'经济口径：规划期{e.horizon_years}年，折现率{e.discount_rate:.2%}，重复同一完整代表年；运行排放不折现，不含设备隐含排放。')
    if run.task.demo:lines.append('关键假设：合成演示数据，价格、排放和设备参数为假设。')
    elif run.task.case_context:lines.append('服务边界：'+run.task.case_context.boundary+'。关键假设与待核实事项见当前报告；不构成真实工程决策。')
    return '\n'.join(lines)


def _serialized(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        request_id=kwargs.get('request_id') if method.__name__=='submit' else (args[0] if args else kwargs.get('request_id'))
        from .storage import file_lock
        with file_lock(self._path(request_id).with_suffix('.lock')):
            return method(self,*args,**kwargs)
    return call


class AgentSession:
    """Durable, baseline-pinned conversations around the existing EnergyAgent.

    A root request and every answer have independent idempotency keys. All
    pending fields and baseline snapshots survive process/browser restarts.
    """
    def __init__(self,agent:EnergyAgent,client,directory='outputs/conversation'):
        self.agent,self.client,self.directory=agent,client,Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        agent.registry._tools['sensitivity_analysis']=Tool(SensitivityRequest,StudyResult,sensitivity_analysis)

    def _path(self,request_id):
        if not request_id:raise ValueError('必须提供可重试的request_id')
        return self.directory/(hashlib.sha256(request_id.encode()).hexdigest()+'.json')

    def _read(self,request_id):
        path=self._path(request_id)
        if not path.exists():raise ValueError('没有待接续请求，回答不能作为无上下文的新指令；请先提交原请求')
        receipt=json.loads(path.read_text(encoding='utf-8'))
        if 'dialog' not in receipt:raise ValueError('旧回执缺少原始请求或基准快照，请重新提交原请求；不能无上下文接续')
        return path,receipt

    def get_pending(self,request_id):
        _,receipt=self._read(request_id)
        return PendingDialog.model_validate(receipt['dialog'])

    def restore(self,request_id):
        path,receipt=self._read(request_id)
        if receipt.get('reply'):return ConversationReply.model_validate(receipt['reply'])
        dialog=PendingDialog.model_validate(receipt['dialog'])
        text='已恢复原请求和固定基准，尚未发起模型调用或求解。请显式接续。'
        if receipt.get('new_run_file'):text+='已有计算结果快照；接续只重试解释，不重复缩减预算。'
        return ConversationReply(status='cancelled' if dialog.status=='cancelled' else 'clarification',text=text,request_id=request_id,pending=dialog)

    def _pin_base(self,previous,path,generation):
        if previous.task.constraints is None or previous.task.constraints.budget_yuan is None or previous.task.data is None:
            raise ValueError('基准任务缺少已确认的预算、负荷或约束')
        if previous.input_version!=previous.task.version:raise ValueError('基准运行与任务版本不一致')
        from .data import validate_inputs
        checked=validate_inputs(previous.task)
        if not checked.ready:raise ValueError('基准输入未通过校验：'+'；'.join(i.field+': '+i.message for i in checked.issues))
        base_file=path.with_name(path.stem+f'.base{generation}.json')
        self._save(base_file,previous.model_dump(mode='json'))
        return base_file.name

    @_serialized
    def submit(self,text,previous:RunResult,*,request_id:str):
        path=self._path(request_id)
        digest=hashlib.sha256(text.encode()).hexdigest()
        if path.exists():
            receipt=json.loads(path.read_text(encoding='utf-8'))
            if receipt['text_sha']!=digest:raise ValueError('相同request_id不能用于不同要求；回答请使用answer入口')
            if receipt.get('reply'):return ConversationReply.model_validate(receipt['reply'])
            return self._advance(receipt,path)
        base_file=self._pin_base(previous,path,1)
        dialog=PendingDialog(request_id=request_id,original_request=text,base_run_id=previous.run_id,
            input_version=previous.input_version,base_file=base_file,confirmed_conditions=self._conditions(previous))
        receipt={'text_sha':digest,'base_run_id':previous.run_id,'base_version':previous.input_version,'dialog':dialog.model_dump()}
        self._save(path,receipt)
        return self._advance(receipt,path)

    @_serialized
    def answer(self,request_id,text,*,turn_id,field=None):
        path,receipt=self._read(request_id)
        if not turn_id:raise ValueError('回答需要稳定turn_id')
        turn_file=path.with_name(path.stem+'.turn.'+hashlib.sha256(turn_id.encode()).hexdigest()+'.json')
        digest=hashlib.sha256(text.encode()).hexdigest()
        if turn_file.exists():
            saved=json.loads(turn_file.read_text(encoding='utf-8'))
            if saved['text_sha']!=digest:raise ValueError('同一turn_id回答不同；请使用edit_answer并提供新的edit_id')
            if field is not None and saved.get('field',field)!=field:raise ValueError('同一turn_id不能回答不同字段')
            return ConversationReply.model_validate(saved['reply'])
        dialog=PendingDialog.model_validate(receipt['dialog'])
        if dialog.status=='cancelled':raise ValueError('请求已取消，回答不能恢复已取消任务；请创建新请求')
        prior=next((a for a in dialog.answers if a['turn_id']==turn_id),None)
        if prior:
            if prior['text']!=text or (field is not None and prior['field']!=field):raise ValueError('回答已记录，修改请使用edit_answer')
            if any(m.field=='confirm_rebase' for m in dialog.missing_fields):raise ValueError('基准已重选，请显式resume确认，不能用旧回答重试代替确认')
            # A failed explanation (or interrupted turn receipt write) must
            # retain the already computed run and generation on answer retry.
            reply=ConversationReply.model_validate(receipt['reply']) if receipt.get('reply') else self._advance(receipt,path)
            self._save(turn_file,{'text_sha':digest,'field':prior['field'],'reply':reply.model_dump(mode='json')})
            return reply
        if dialog.status=='completed':raise ValueError('请求已完成；修改既有回答请使用edit_answer')
        available=[m.field for m in dialog.missing_fields]
        field=field or (available[0] if len(available)==1 else None)
        if field not in available:raise ValueError('请指定当前待补字段，不能把回答当作新的自由指令')
        dialog.answers.append({'turn_id':turn_id,'field':field,'text':text})
        self._reset(receipt,dialog)
        self._save(path,receipt)
        reply=self._advance(receipt,path)
        self._save(turn_file,{'text_sha':digest,'field':field,'reply':reply.model_dump(mode='json')})
        return reply

    @_serialized
    def edit_answer(self,request_id,turn_id,text,*,edit_id):
        path,receipt=self._read(request_id)
        if not edit_id:raise ValueError('修改回答需要稳定edit_id')
        edit_file=path.with_name(path.stem+'.edit.'+hashlib.sha256(edit_id.encode()).hexdigest()+'.json')
        digest=hashlib.sha256(text.encode()).hexdigest()
        if edit_file.exists():
            saved=json.loads(edit_file.read_text(encoding='utf-8'))
            if saved['text_sha']!=digest or saved.get('turn_id',turn_id)!=turn_id:raise ValueError('edit_id已用于其他回答')
            return ConversationReply.model_validate(saved['reply'])
        dialog=PendingDialog.model_validate(receipt['dialog'])
        if dialog.status=='cancelled':raise ValueError('请求已取消，不能修改回答')
        prior=next((h for h in dialog.history if h.get('event')=='edit_answer' and h.get('edit_id')==edit_id),None)
        if prior:
            if prior['turn_id']!=turn_id or prior['text_sha']!=digest:raise ValueError('edit_id已用于其他回答')
            if prior['generation']!=dialog.generation:raise ValueError('此修改后已有其他变更，请恢复当前状态；不能重放旧修改')
            reply=ConversationReply.model_validate(receipt['reply']) if receipt.get('reply') else self._advance(receipt,path)
            self._save(edit_file,{'text_sha':digest,'turn_id':turn_id,'reply':reply.model_dump(mode='json')})
            return reply
        answer=next((a for a in dialog.answers if a['turn_id']==turn_id),None)
        if answer is None:raise ValueError('未找到该回答turn_id')
        dialog.history.append({'event':'edit_answer','edit_id':edit_id,'text_sha':digest,'generation':dialog.generation+1,
            'turn_id':turn_id,'previous_text':answer['text'],'previous_run_id':receipt.get('new_run_id')})
        answer['text']=text;dialog.generation+=1
        self._reset(receipt,dialog);self._save(path,receipt)
        reply=self._advance(receipt,path)
        self._save(edit_file,{'text_sha':digest,'turn_id':turn_id,'reply':reply.model_dump(mode='json')})
        return reply

    @_serialized
    def rebase(self,request_id,previous:RunResult):
        path,receipt=self._read(request_id);dialog=PendingDialog.model_validate(receipt['dialog'])
        if dialog.status=='cancelled':raise ValueError('已取消请求不能重新选择基准')
        dialog.history.append({'event':'rebase','previous_base_run_id':dialog.base_run_id,'previous_input_version':dialog.input_version})
        dialog.generation+=1;dialog.base_run_id=previous.run_id;dialog.input_version=previous.input_version
        dialog.base_file=self._pin_base(previous,path,dialog.generation);dialog.confirmed_conditions=self._conditions(previous)
        self._reset(receipt,dialog)
        receipt['base_run_id']=previous.run_id;receipt['base_version']=previous.input_version
        self._save(path,receipt)
        return self._clarify(receipt,path,[MissingField(field='confirm_rebase',question='基准已重新选择，确认接续原请求与已收集回答吗？',reason='重新选择基准后不自动求解')])

    @_serialized
    def resume(self,request_id):
        path,receipt=self._read(request_id)
        if receipt['dialog']['status']=='cancelled':raise ValueError('请求已取消')
        if receipt.get('reply',{}).get('status')=='completed':return ConversationReply.model_validate(receipt['reply'])
        receipt.pop('reply',None)
        return self._advance(receipt,path)

    @_serialized
    def cancel(self,request_id):
        path,receipt=self._read(request_id);dialog=PendingDialog.model_validate(receipt['dialog'])
        dialog.status='cancelled';dialog.history.append({'event':'cancel'})
        receipt['dialog']=dialog.model_dump()
        return self._remember(ConversationReply(status='cancelled',text='请求已取消；基准和历史结果保留，未继续求解。',request_id=request_id,pending=dialog),receipt,path)

    @staticmethod
    def _conditions(previous):
        task=previous.task
        return {'budget_yuan':task.constraints.budget_yuan,'emission_limit_kg':task.constraints.emission_limit_kg,
            'grid_limit_kw':task.constraints.grid_limit_kw,'pv_limit_kw':task.constraints.pv_limit_kw,
            'assessment_mode':task.assessment_mode,'emission_species':task.emission_species,'period_start':task.data.timestamps[0].isoformat(),
            'period_end':task.data.timestamps[-1].isoformat(),'step_hours':task.data.step_hours,'intervals':len(task.data.timestamps),
            'heat_fingerprint':heat_fingerprint(task),'economics':task.economics.model_dump() if task.economics else None}

    @staticmethod
    def _reset(receipt,dialog):
        for key in ('intent','reply','new_run_file','new_run_id','explanation','heat_unchanged','contract'):receipt.pop(key,None)
        dialog.status='ready';receipt['dialog']=dialog.model_dump()

    def _advance(self,receipt,path):
        dialog=PendingDialog.model_validate(receipt['dialog'])
        previous=RunResult.model_validate_json((self.directory/dialog.base_file).read_text(encoding='utf-8'))
        if receipt.get('new_run_file'):
            run=RunResult.model_validate_json((self.directory/receipt['new_run_file']).read_text(encoding='utf-8'))
            return self._complete(run,receipt,path,dialog.request_id)
        if dialog.status=='cancelled':raise ValueError('请求已取消')
        if isinstance(self.client,RuleClient):raise LLMError(self.client.description)
        contract=compile_contract(dialog.original_request,previous,dialog.answers)
        receipt['contract']=contract.model_dump()
        if '供热' in dialog.original_request and previous.task.assessment_mode=='electric_only':
            return self._clarify(receipt,path,[MissingField(field='heating_boundary',question='当前电侧任务未建模供热，请先确认供热边界和热负荷；不能宣称供热保持不变已验收。',reason='缺少供热模型')])
        context={'request':dialog.original_request,'answers':dialog.answers,'confirmed_run_id':previous.run_id,'input_version':previous.input_version,
            **dialog.confirmed_conditions,'authorized_contract':contract.model_dump(mode='json'),
            'quality_summary':previous.task.case_context.quality_summary if previous.task.case_context else '合成演示',
            'boundary':previous.task.case_context.boundary if previous.task.case_context else '单节点电热',
            'supported_operations':['modify','clarify','evaluate','compare','sensitivity','report','explain']}
        if 'intent' not in receipt:
            intent=self.client.call_tool('planning_intent',PlanningIntent,context)
            receipt['intent']=intent.model_dump();self._save(path,receipt)
        intent=PlanningIntent.model_validate(receipt['intent'])
        if contract.missing and any(m.field!='request_details' for m in contract.missing):
            return self._clarify(receipt,path,contract.missing)
        if intent.operation=='clarify':
            fields=contract.missing or [MissingField(field='request_details',question='请明确希望修改的参数、数值和保留条件。',reason='需求仍需确认')]
            return self._clarify(receipt,path,fields)
        if intent.operation=='sensitivity':
            study=self.agent.registry.call('sensitivity_analysis',SensitivityRequest(task=previous.task,options=self.agent.options,output_dir=str(self.directory/path.stem/'study')))
            return self._remember(ConversationReply(status='completed',text=study.note,study=study,request_id=dialog.request_id),receipt,path)
        if intent.operation in ('compare','report','explain'):
            if contract.edits:return self._clarify(receipt,path,[MissingField(field='request_details',question='你要求修改条件，模型没有选择修改操作，请明确修改要求。',reason='操作与请求不符')])
            return self._complete(previous,receipt,path,dialog.request_id)
        task=previous.task
        if intent.operation=='modify':
            if not contract.ready:return self._clarify(receipt,path,contract.missing)
            if intent.patch is None:raise LLMError('修改操作缺少结构化参数，未应用修改')
            try:validate_proposal(intent.patch,contract)
            except ValueError as exc:
                receipt.pop('intent',None);self._save(path,receipt);raise LLMError(str(exc)) from None
            patch=_preserve_unsupported(contract.resolved_request,previous.task,contract.patch)
            task=revise_task(previous.task,patch,parent_run_id=previous.run_id,new_version=previous.input_version+dialog.generation)
            assert_preserved(previous.task,task,contract)
        elif contract.edits:
            raise LLMError('请求包含修改，但模型未选择修改操作；未求解')
        # Store the independently authorized before/after/preserve list before solving.
        self._save(path,receipt)
        run=self.agent.run(task,previous=previous)
        snapshot=path.with_name(path.stem+f'.result{dialog.generation}.json')
        self._save(snapshot,run.model_dump(mode='json'))
        receipt['new_run_file']=snapshot.name;receipt['new_run_id']=run.run_id
        receipt['heat_unchanged']=task.assessment_mode=='electric_heat' and heat_fingerprint(task)==heat_fingerprint(previous.task)
        self._save(path,receipt)
        return self._complete(run,receipt,path,dialog.request_id)

    def _clarify(self,receipt,path,fields):
        dialog=PendingDialog.model_validate(receipt['dialog']);dialog.status='awaiting_answer';dialog.missing_fields=fields
        receipt['dialog']=dialog.model_dump()
        text='尚未修改或求解。'+ ' '.join(m.question for m in fields)+f' 基准运行 {dialog.base_run_id}，版本{dialog.input_version}；回答将接续该请求。'
        contract=ModificationContract.model_validate(receipt['contract']) if receipt.get('contract') else None
        return self._remember(ConversationReply(status='clarification',text=text,request_id=dialog.request_id,pending=dialog,contract=contract),receipt,path)

    def _complete(self,run,receipt,path,request_id):
        context={'run_id':run.run_id,'conclusion':actual_conclusion(run),'current_facts':current_facts(run),
            'failures':[{'candidate_id':s.candidate.candidate_id,'status':s.dispatch.status,'reasons':s.dispatch.reasons} for s in run.scenarios if not s.validation.valid]}
        explanation=self.client.call_tool('grounded_explanation',GroundedExplanation,context,explain=True)
        validate_explanation(explanation,run);receipt['explanation']=explanation.model_dump()
        dialog=PendingDialog.model_validate(receipt['dialog']);dialog.status='completed';dialog.missing_fields=[]
        receipt['dialog']=dialog.model_dump()
        previous=RunResult.model_validate_json((self.directory/dialog.base_file).read_text(encoding='utf-8'))
        contract=ModificationContract.model_validate(receipt['contract']) if receipt.get('contract') else None
        reply=ConversationReply(status='completed',text=deterministic_reply(run,previous,contract),run=run,request_id=request_id,
            heat_unchanged=receipt.get('heat_unchanged'),explanation_verified=True,pending=dialog,contract=contract)
        return self._remember(reply,receipt,path)

    def _remember(self,reply,receipt,path):
        receipt['reply']=reply.model_dump(mode='json');self._save(path,receipt);return reply

    @staticmethod
    def _save(path,receipt):
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
