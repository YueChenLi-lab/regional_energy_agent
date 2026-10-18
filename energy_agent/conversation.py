"""Confirmed-task actions, idempotent edits and numerical evidence-bound replies."""
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from .agent import EnergyAgent, Tool, revise_task
from .frontier import SensitivityRequest, StudyResult, sensitivity_analysis
from .llm import LLMError, RuleClient, _preserve_unsupported
from .schemas import Model, RunResult, TaskPatch


class PlanningIntent(Model):
    operation: Literal['modify','clarify','evaluate','compare','sensitivity','report','explain']
    patch: TaskPatch | None = None
    question: str | None = Field(default=None,max_length=400)


class FactClaim(Model):
    reference: str
    value: float


class GroundedExplanation(Model):
    run_id: str
    conclusion: Literal['可行且通过独立校验','无可行方案','待补信息或执行失败']
    claims: list[FactClaim] = Field(max_length=40)


class ConnectivityCheck(Model):
    status: Literal['ok']


class ConversationReply(Model):
    status: Literal['clarification','completed']
    text: str
    run: RunResult | None = None
    study: StudyResult | None = None
    request_id: str
    heat_unchanged: bool | None = None
    explanation_verified: bool = False


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


def deterministic_reply(run):
    text=f'当前运行 {run.run_id}，输入版本 {run.input_version}：{actual_conclusion(run)}。运行排放单位kg{run.task.emission_species}。'
    for s in run.scenarios:
        text+=f'\n方案 {s.candidate.candidate_id}：{s.dispatch.status}。'
        if s.validation.valid:
            facts=current_facts(run);root='scenarios.'+s.candidate.candidate_id+'.'
            text+='；'.join(f'{label}={facts[root+key]:.6f} [{root+key}]' for key,label in _LABELS.items() if root+key in facts)
        else:text+='；'.join(s.dispatch.reasons) or s.dispatch.message
    if run.changes:
        text+='\n相对父运行的变化（当前减前次；排放负值表示减排）：'+json.dumps(run.changes['scenarios'],ensure_ascii=False)
    return text


class AgentSession:
    """A local session around the same deterministic EnergyAgent.

    Request IDs are stable over retries. To deliberately apply a second relative
    reduction, submit a new request ID. Receipts are written before parsing and
    the new run path is recorded before explanation, so retries cannot compound.
    """
    def __init__(self, agent:EnergyAgent, client, directory='outputs/conversation'):
        self.agent,self.client,self.directory=agent,client,Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        agent.registry._tools['sensitivity_analysis']=Tool(SensitivityRequest,StudyResult,sensitivity_analysis)

    def submit(self,text,previous:RunResult,*,request_id:str):
        if not request_id: raise ValueError('必须提供可重试的request_id')
        key=hashlib.sha256(request_id.encode()).hexdigest()
        path=self.directory/(key+'.json')
        text_sha=hashlib.sha256(text.encode()).hexdigest()
        receipt=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if receipt:
            if receipt['text_sha']!=text_sha:raise ValueError('相同request_id不能用于不同要求')
            if receipt.get('reply'):return ConversationReply.model_validate(receipt['reply'])
            if receipt.get('new_run_file'):
                run=RunResult.model_validate_json(Path(receipt['new_run_file']).read_text(encoding='utf-8'))
                return self._complete(run,receipt,path,request_id)
            if receipt['base_run_id']!=previous.run_id:raise ValueError('该请求已有确认的基准运行，请用原始基准重试')
        else:
            receipt={'text_sha':text_sha,'base_run_id':previous.run_id,'base_version':previous.input_version}
            self._save(path,receipt)
        if isinstance(self.client,RuleClient):raise LLMError(self.client.description)
        task=previous.task
        # No promise of heat assurance for an electric-only case, even if the model omits it.
        if '供热' in text and task.assessment_mode=='electric_only':
            reply=ConversationReply(status='clarification',text='当前任务是电侧评估，未建模供热。请先确认热负荷、原暖通边界与供热保障要求；不能宣称供热保持不变已验收。',request_id=request_id)
            return self._remember(reply,receipt,path)
        context={'request':text,'confirmed_run_id':previous.run_id,'input_version':task.version,
            'budget_yuan':task.constraints.budget_yuan,'assessment_mode':task.assessment_mode,
            'planning_mode':task.planning_mode,'emission_species':task.emission_species,'economics':task.economics.model_dump() if task.economics else None,
            'quality_summary':task.case_context.quality_summary if task.case_context else '合成演示',
            'boundary':task.case_context.boundary if task.case_context else '单节点常规电与热',
            'period_start':task.data.timestamps[0].isoformat(),'intervals':len(task.data.timestamps),'heat_fingerprint':heat_fingerprint(task),
            'supported_operations':['modify','clarify','evaluate','compare','sensitivity','report','explain']}
        if 'intent' not in receipt:
            intent=self.client.call_tool('planning_intent',PlanningIntent,context)
            receipt['intent']=intent.model_dump();self._save(path,receipt)
        intent=PlanningIntent.model_validate(receipt['intent'])
        if intent.operation=='clarify':
            question=intent.question or '请明确希望修改的预算或排放约束及数值。'
            if re.search(r'[0-9]|已(?:求得|推荐|满足)|最优',question):
                question='请明确希望修改的预算、排放目标与需要保持的服务边界；尚未应用修改或生成新的计算结论。'
            reply=ConversationReply(status='clarification',text=question,request_id=request_id)
            return self._remember(reply,receipt,path)
        if intent.operation=='sensitivity':
            study=self.agent.registry.call('sensitivity_analysis',SensitivityRequest(task=task,options=self.agent.options,output_dir=str(self.directory/key/'study')))
            reply=ConversationReply(status='completed',text=study.note,study=study,request_id=request_id)
            return self._remember(reply,receipt,path)
        if intent.operation in ('compare','report','explain'):
            return self._complete(previous,receipt,path,request_id)
        revised=task
        if intent.operation=='modify':
            if intent.patch is None:raise LLMError('修改操作缺少结构化参数，未应用修改')
            patch=_preserve_unsupported(text,task,intent.patch)
            core=re.search(r'预算.{0,8}(?:减少|降低|削减|下调)\s*20\s*[%％]',text)
            if core:
                if patch.budget_multiplier!=0.8 or patch.budget_yuan is not None or patch.demand_scale not in (None,1):
                    raise LLMError('相对预算参数不符合确认要求；应基于当前预算乘0.8，未应用修改')
                if any(getattr(patch,k) is not None for k in ('emission_limit_kg','grid_limit_kw','pv_limit_kw')) or patch.clear_emission_limit:
                    raise LLMError('预算修改包含未要求的约束变更，未应用修改')
                if '供热' in text and not patch.preserve_heat:raise LLMError('模型未声明保持供热要求，未应用修改')
            revised=revise_task(task,patch,parent_run_id=previous.run_id)
            if patch.preserve_heat and heat_fingerprint(revised)!=heat_fingerprint(task):
                raise LLMError('修改影响供热负荷或时段，已阻止运行')
        run=self.agent.run(revised,previous=previous)
        receipt['new_run_file']=run.files['json']
        receipt['heat_unchanged']=task.assessment_mode=='electric_heat' and heat_fingerprint(task)==heat_fingerprint(run.task)
        self._save(path,receipt)
        return self._complete(run,receipt,path,request_id)

    def _complete(self,run,receipt,path,request_id):
        context={'run_id':run.run_id,'conclusion':actual_conclusion(run),'current_facts':current_facts(run),
            'failures':[{ 'candidate_id':s.candidate.candidate_id,'status':s.dispatch.status,'reasons':s.dispatch.reasons} for s in run.scenarios if not s.validation.valid]}
        explanation=self.client.call_tool('grounded_explanation',GroundedExplanation,context,explain=True)
        validate_explanation(explanation,run)
        receipt['explanation']=explanation.model_dump()
        reply=ConversationReply(status='completed',text=deterministic_reply(run),run=run,request_id=request_id,
            heat_unchanged=receipt.get('heat_unchanged'),explanation_verified=True)
        return self._remember(reply,receipt,path)

    def _remember(self,reply,receipt,path):
        receipt['reply']=reply.model_dump(mode='json');self._save(path,receipt);return reply

    @staticmethod
    def _save(path,receipt):
        tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
