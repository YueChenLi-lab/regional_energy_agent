"""Opt-in annual and model workflows. Ordinary demo/test paths stay offline."""
import json
from pathlib import Path

from .agent import EnergyAgent
from .annual import build_annual_case
from .conversation import AgentSession, ConnectivityCheck, PlanningIntent
from .frontier import SensitivityRequest, sensitivity_analysis
from .llm import LLMError, OpenAICompatibleClient, RequestBudget, RuleClient, get_llm_client
from .schemas import RunResult, SolverOptions, TaskRequest


def register_planning_commands(commands):
    annual=commands.add_parser('annual-build',help='真实全年Q＋同期NASA；供热可显式启用仿真研究情景')
    annual.add_argument('--bundle',type=Path,help='随代码许可全年数据包；无需网络或原始ZIP')
    annual.add_argument('--year',type=int,default=2017)
    annual.add_argument('--heat',action='store_true')
    annual.add_argument('--online',action='store_true')
    annual.add_argument('--retain-flagged-jumps',action='store_true',help='显式保留告警原值并披露，不是消除异常')
    annual.add_argument('--budget',type=float,default=10000000)
    annual.add_argument('--output',type=Path,required=True)
    annual.add_argument('--run',action='store_true')
    annual.add_argument('--time-limit',type=float,default=60)
    study=commands.add_parser('plan-study',help='有限成本—排放扫描，非完整全局前沿')
    study.add_argument('--task',type=Path,required=True)
    study.add_argument('--output',type=Path,required=True)
    study.add_argument('--scans',type=int,default=3)
    study.add_argument('--time-limit',type=float,default=60)
    chat=commands.add_parser('agent-chat',help='显式调用模型；原确认运行＋稳定请求ID')
    chat.add_argument('--run',type=Path,required=True)
    chat.add_argument('--text',required=True)
    chat.add_argument('--request-id',required=True)
    chat.add_argument('--output',type=Path,required=True)
    chat.add_argument('--time-limit',type=float,default=60)
    check=commands.add_parser('llm-check',help='一次显式连通请求，消耗模型额度')
    check.add_argument('--output',type=Path,default=Path('outputs/model_check'))
    acceptance=commands.add_parser('llm-acceptance',help='真实接口验收，含重试最多10次；需要已确认电热运行')
    acceptance.add_argument('--run',type=Path,required=True)
    acceptance.add_argument('--output',type=Path,required=True)
    acceptance.add_argument('--time-limit',type=float,default=60)


def configured_client(output):
    client=get_llm_client()
    if isinstance(client,OpenAICompatibleClient):
        client.budget=RequestBudget(log_path=Path(output)/'model_requests.json')
    return client


def handle_planning_command(args):
    out=args.output;out.mkdir(parents=True,exist_ok=True)
    if args.command=='annual-build':
        if any(out.iterdir()):raise ValueError('年度输入输出需要新空目录，防止覆盖来源与旧结果')
        task=build_annual_case(year=args.year,heat=args.heat,offline=not args.online,budget=args.budget,
            retain_flagged_jumps=args.retain_flagged_jumps,output=out,bundle_dir=args.bundle)
        print('已保存完整日历年输入',out/'task.json')
        if args.run:
            run=EnergyAgent(out/'runs',SolverOptions(time_limit_seconds=args.time_limit,mip_rel_gap=0.002)).run(task)
            print(run.run_id,run.state.value,run.files['json'])
            return 0 if run.state.value=='完成' else 2
        return 0
    if args.command=='plan-study':
        task=TaskRequest.model_validate_json(args.task.read_text(encoding='utf-8'))
        study=sensitivity_analysis(SensitivityRequest(task=task,output_dir=str(out),scans=args.scans,
            options=SolverOptions(time_limit_seconds=args.time_limit,mip_rel_gap=0.002)))
        print(study.model_dump_json(indent=2));return 0
    client=configured_client(out)
    if isinstance(client,RuleClient):
        status={'status':'not_verified','reason':'当前运行环境缺少完整模型配置；未发起真实请求','actual_requests':0}
        (out/'acceptance.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(status,ensure_ascii=False));return 2
    if args.command=='llm-check':
        result=client.call_tool('connectivity_check',ConnectivityCheck,{'request':'仅返回status=ok，不调用其他工具'})
        print(result.model_dump_json(),f'本会话请求次数={client.budget.count}');return 0
    previous=RunResult.model_validate_json(args.run.read_text(encoding='utf-8'))
    agent=EnergyAgent(out/'runs',SolverOptions(time_limit_seconds=args.time_limit,mip_rel_gap=0.002))
    session=AgentSession(agent,client,out/'session')
    if args.command=='agent-chat':
        reply=session.submit(args.text,previous,request_id=args.request_id)
        print(reply.text);return 0
    return real_acceptance(client,session,previous,out)


def real_acceptance(client,session,previous,out):
    evidence={'status':'running','checks':[],'actual_requests':client.budget.count,'verified_real_endpoint':False}
    def check(name,condition):
        evidence['checks'].append({'name':name,'passed':bool(condition)})
        if not condition:raise LLMError('真实验收检查未通过：'+name)
    try:
        if previous.task.assessment_mode!='electric_heat':raise LLMError('真实验收需要已确认且有供热负荷的电热任务')
        check('connectivity',client.call_tool('connectivity_check',ConnectivityCheck,{'request':'返回status=ok'}).status=='ok')
        intent=client.call_tool('planning_intent',PlanningIntent,{'request':'预算减少20%，供热要求保持不变。','budget_yuan':previous.task.constraints.budget_yuan,'assessment_mode':'electric_heat'})
        check('structured_relative_patch',intent.operation=='modify' and intent.patch is not None and intent.patch.budget_multiplier==0.8 and intent.patch.preserve_heat)
        reply=session.submit('预算减少20%，供热要求保持不变。',previous,request_id='acceptance-budget20')
        check('heat_unchanged_and_recomputed',reply.run is not None and reply.run.run_id!=previous.run_id and reply.heat_unchanged and reply.run.task.constraints.budget_yuan==previous.task.constraints.budget_yuan*0.8)
        check('current_evidence_explanation',reply.explanation_verified)
        count=client.budget.count
        duplicate=session.submit('预算减少20%，供热要求保持不变。',reply.run,request_id='acceptance-budget20')
        check('duplicate_is_idempotent',duplicate.run.run_id==reply.run.run_id and count==client.budget.count)
        ambiguity=session.submit('希望方案更好一点，帮我调整。',reply.run,request_id='acceptance-ambiguity')
        check('ambiguous_requirement_clarified',ambiguity.status=='clarification')
        infeasible=session.submit('初始投资预算设为0元，供热要求保持不变。',previous,request_id='acceptance-infeasible')
        check('infeasible_truthfully_explained',infeasible.run is not None and not any(s.validation.valid for s in infeasible.run.scenarios) and infeasible.explanation_verified)
        evidence.update(status='passed',verified_real_endpoint=True)
    except (LLMError,ValueError) as exc:
        # Errors are locally authored and do not include raw response bodies.
        evidence.update(status='not_verified',reason=str(exc))
    finally:
        evidence['actual_requests']=client.budget.count
        evidence['fees']='未核实，不推算费用'
        (out/'acceptance.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(evidence,ensure_ascii=False,indent=2))
    return 0 if evidence['status']=='passed' else 2
