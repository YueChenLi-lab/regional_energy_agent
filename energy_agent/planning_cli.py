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
    dialog=commands.add_parser('agent-dialog',help='恢复、回答、修改回答、取消或重新选择已有对话基准')
    dialog.add_argument('--action',choices=['status','answer','edit','cancel','rebase','resume'],required=True)
    dialog.add_argument('--request-id',required=True)
    dialog.add_argument('--output',type=Path,required=True,help='与原agent-chat相同的会话输出目录')
    dialog.add_argument('--text')
    dialog.add_argument('--field')
    dialog.add_argument('--turn-id')
    dialog.add_argument('--edit-id')
    dialog.add_argument('--run',type=Path,help='仅rebase时使用新的已确认result.json')
    dialog.add_argument('--time-limit',type=float,default=60)
    diagnostic=commands.add_parser('data-diagnose',help='只读峰值及邻近时段诊断，不处理或覆盖原值')
    diagnostic.add_argument('--task',type=Path,required=True,help='任务JSON或result.json')
    diagnostic.add_argument('--output',type=Path,required=True)
    peak=commands.add_parser('peak-study',help='三组离线全年Q峰值处理假设实验；不覆盖原始数据')
    peak.add_argument('--bundle',type=Path,default=Path('examples/shanghai_2017'))
    peak.add_argument('--spec',type=Path,default=Path('configs/peak_sensitivity_v032.json'))
    peak.add_argument('--output',type=Path,required=True)
    peak.add_argument('--time-limit',type=float,default=120)
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
    if args.command=='peak-study':
        from .peak_sensitivity import run_peak_study
        result=run_peak_study(bundle_dir=args.bundle,spec_file=args.spec,output=out,time_limit=args.time_limit)
        print(result.conclusion)
        print(json.dumps(result.files,ensure_ascii=False))
        return 0 if all(r['feasible'] for r in result.scenarios) else 2
    if args.command=='data-diagnose':
        from .diagnostics import diagnose_peak,export_diagnostics
        raw=json.loads(args.task.read_text(encoding='utf-8'))
        task=RunResult.model_validate(raw).task if 'run_id' in raw else TaskRequest.model_validate(raw)
        diagnostic=diagnose_peak(task)
        export_diagnostics(diagnostic,out)
        print(diagnostic.summary);print(diagnostic.treatment);return 0
    if args.command=='agent-dialog':
        session=AgentSession(EnergyAgent(out/'runs',SolverOptions(time_limit_seconds=args.time_limit,mip_rel_gap=.002)),configured_client(out),out/'session')
        if args.action=='status':reply=session.restore(args.request_id)
        elif args.action=='cancel':reply=session.cancel(args.request_id)
        elif args.action=='resume':reply=session.resume(args.request_id)
        elif args.action=='rebase':
            if args.run is None:raise ValueError('重新选择基准需要--run')
            reply=session.rebase(args.request_id,RunResult.model_validate_json(args.run.read_text(encoding='utf-8')))
        elif args.action=='answer':
            if args.text is None or not args.turn_id:raise ValueError('回答需要--text和稳定--turn-id')
            reply=session.answer(args.request_id,args.text,turn_id=args.turn_id,field=args.field)
        else:
            if args.text is None or not args.turn_id or not args.edit_id:raise ValueError('修改回答需要--text、--turn-id和--edit-id')
            reply=session.edit_answer(args.request_id,args.turn_id,args.text,edit_id=args.edit_id)
        print(reply.text)
        if reply.pending:print(reply.pending.model_dump_json(indent=2))
        return 0
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
    from .acceptance import run_live_acceptance
    evidence=run_live_acceptance(previous,out,agent.options)
    print(json.dumps(evidence,ensure_ascii=False,indent=2))
    return 0 if evidence['status']=='passed' else 2
