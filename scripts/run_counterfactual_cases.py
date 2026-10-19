"""Reproduce small synthetic repairs, optionally one explicit full-year case.

Run from the repository root. This never contacts a model or data service.
"""
import argparse
import json
from pathlib import Path

from energy_agent.agent import EnergyAgent
from energy_agent.counterfactual import (CounterfactualRequest, RepairRange, data_fingerprint,
                                       search_counterfactual_repairs)
from energy_agent.counterfactual_cases import make_repair_case


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--annual',action='store_true',help='显式追加真实8760小时混合电热研究案例，不在普通测试中执行')
    args=parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('请使用新的空输出目录，不能覆盖已有证据')
    args.output.mkdir(parents=True,exist_ok=True)
    cases=[]
    task=make_repair_case(24)
    cases.append(('three_paths_24h',task,{
        'budget_yuan':RepairRange(lower=60000,upper=600000,precision=1000,unit='元'),
        'emission_limit_kg':RepairRange(lower=230,upper=300,precision=.05,unit='kgCO2e'),
        'grid_limit_kw':RepairRange(lower=12,upper=25,precision=.01,unit='kW')},128,60))
    task=make_repair_case(6);task.candidates=task.candidates[:1]
    task.constraints.budget_yuan=0;task.constraints.emission_limit_kg=None;task.constraints.grid_limit_kw=30
    cases.append(('budget_6h',task,{'budget_yuan':RepairRange(lower=0,upper=50000,precision=10,unit='元')},32,30))
    task=make_repair_case(168);task.candidates=task.candidates[:1]
    task.constraints.emission_limit_kg=0;task.constraints.grid_limit_kw=30
    cases.append(('emissions_168h',task,{'emission_limit_kg':RepairRange(lower=0,upper=3000,precision=.1,unit='kgCO2e')},32,30))
    task=make_repair_case(6);task.candidates=task.candidates[:1]
    task.constraints.budget_yuan=0;task.constraints.grid_limit_kw=0
    cases.append(('multiple_conflicts_6h',task,{'budget_yuan':RepairRange(lower=0,upper=50000,precision=10,unit='元'),
        'grid_limit_kw':RepairRange(lower=0,upper=30,precision=.01,unit='kW')},32,30))
    if args.annual:
        from energy_agent.annual import build_annual_case
        task=build_annual_case(heat=True,bundle_dir=Path('examples/shanghai_2017'),retain_flagged_jumps=True,budget=0)
        cases.append(('annual_heat_8760h',task,{'budget_yuan':RepairRange(lower=0,upper=1000000,precision=20000,unit='元')},12,120))
    summaries=[]
    for name,task,ranges,calls,seconds in cases:
        out=args.output/name
        out.mkdir()
        (out/'task.json').write_text(task.model_dump_json(indent=2),encoding='utf-8')
        baseline=EnergyAgent(out/'baseline').run(task)
        req=CounterfactualRequest(baseline=baseline,base_run_id=baseline.run_id,input_version=baseline.input_version,
            data_fingerprint=data_fingerprint(task),request_id=name,original_request='显式离线研究验收；仅授权所列上限逐条放宽',
            allowed_fields=list(ranges),ranges=ranges,output_dir=str(out/'search'),
            max_solver_calls=calls,total_seconds=seconds,single_solve_seconds=15 if name.startswith('annual') else 3)
        (out/'request.json').write_text(req.model_dump_json(indent=2),encoding='utf-8')
        result=search_counterfactual_repairs(req)
        summaries.append({'case':name,'hours':len(task.data.timestamps)*task.data.step_hours,
            'baseline_run_id':baseline.run_id,'baseline_status':result.baseline_verification.feasibility,
            'result_file':result.files['json'],'report_file':result.files['markdown'],
            'solver_calls':result.solver_calls,'seconds':result.elapsed_seconds,
            'paths':[p.model_dump(mode='json',exclude={'trace','final_validation'}) for p in result.paths]})
        print(name,result.status,result.solver_calls,[(p.field,p.suggested_value,p.boundary_precision_reached) for p in result.paths],flush=True)
    (args.output/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 反事实修复离线验收', '6/24/168小时为固定种子的合成研究案例；如包含8760小时案例，则为上海Q实测与仿真供热、NASA估算资源及人为参数的混合研究情景。',
           '基准不可行时没有可比较的基准运行费用或排放结果；表中费用与排放仅来自各自已求解修复方案。不同路径是替代决策，不是联合修改要求。']
    for s in summaries:
        lines.append(f'## {s["case"]} · {s["hours"]:g}小时\n\n基准：{s["baseline_status"]}；run_id：{s["baseline_run_id"]}；求解适配器调用{s["solver_calls"]}；耗时{s["seconds"]:.3f}秒。')
        for p in s['paths']:
            lines.append(f'- {p["field"]}：{p["original_value"]} → {p["suggested_value"]} {p["unit"]}；调整{p["adjustment"]}；状态{p["status"]}；边界精度达到{p["boundary_precision_reached"]}；求解{p["solver_status"]}，gap={p["mip_gap"]}；指标{p["metrics"]}；NPV={p["npv_cost_yuan"]}；run_id={p["run_id"]}。')
    (args.output/'summary.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
