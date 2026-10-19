"""Run both explicit 24h synthetic demos; optionally archive complete witnesses."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from energy_agent.decision_demos import demo_task, run_decision_demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='新的空输出目录')
    parser.add_argument('--evidence', type=Path, help='可选：新的空归档目录，只归档本次合成运行文件')
    args = parser.parse_args()
    for directory in [args.output, args.evidence]:
        if directory is not None:
            if directory.exists() and any(directory.iterdir()):
                parser.error('请使用新的空目录，不覆盖已有证据')
            directory.mkdir(parents=True, exist_ok=True)
    summary = {}
    results = {}
    for kind in ('repair', 'regret'):
        baseline, result = run_decision_demo(kind, args.output, 'synthetic-24h-'+kind)
        results[kind] = result
        item = dict(base_run_id=baseline.run_id, input_version=baseline.input_version,
            intervals=24, step_hours=1, label='合成演示数据；价格、排放因子、设备和约束均为假设',
            baseline_solver_calls=sum(t.tool_name == 'solve_dispatch' for t in baseline.tool_calls),
            tool_solver_calls=result.solver_calls, tool_seconds=result.elapsed_seconds, files=result.files)
        if kind == 'repair':
            item.update(status=result.status, baseline_feasibility=result.baseline_verification.feasibility,
                paths=[p.model_dump(mode='json', exclude={'trace', 'sources', 'final_validation'}) | {
                    'independently_valid': bool(p.final_validation and p.final_validation.valid)} for p in result.paths])
        else:
            item.update(status=result.analysis.status, analysis=result.analysis.model_dump(mode='json'),
                independently_valid_cells=sum(bool(c.validation and c.validation.valid) for c in result.cells))
        summary[kind] = item
        print(kind, item['status'], 'calls=', item['tool_solver_calls'], 'seconds=', item['tool_seconds'], flush=True)
    (args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    r, g = summary['repair'], summary['regret']
    lines = ['# 两项决策扩展 · 实际合成演示验收',
        '24小时、固定随机种子42。全部负荷为合成数据，设备、价格、排放因子和约束为演示假设；非真实工程，不调用模型。两个案例基准独立，不是将修复结果自动采用后再分析。',
        '## 反事实三路径', f'基准run_id={r["base_run_id"]}；v{r["input_version"]}；复核={r["baseline_feasibility"]}。'
        f'搜索调用{r["tool_solver_calls"]}次、耗时{r["tool_seconds"]:.3f}秒；基准另外调用{r["baseline_solver_calls"]}次。',
        '固定常规电负荷10kW、热负荷20kW_th；预算60000元、排放230kgCO2e、购电12kW。每次只修改一个允许上限，其余负荷、供热、时段、设备、候选和服务保持。']
    for p in r['paths']:
        lines.append(f'- {p["field"]}：{p["original_value"]:g} → {p["suggested_value"]} {p["unit"]}；调整{p["adjustment"]}；'
            f'边界精度{p["search_range"]["precision"]}，达到={p["boundary_precision_reached"]}；'
            f'状态{p["solver_status"]}，gap={p["mip_gap"]}；独立校验={p["independently_valid"]}；run_id={p["run_id"]}。'
            f' 投资/购能费/运行排放等指标：{json.dumps(p["metrics"], ensure_ascii=False)}')
    lines += ['不同路径属于替代决策，不是必须一起修改；不证明唯一不可行原因。结果未自动采用。基准不可行，不能伪造基准费用或排放差值。',
        '## 多情景最小最大后悔', f'基准run_id={g["base_run_id"]}；v{g["input_version"]}；状态{g["status"]}；'
        f'{g["tool_solver_calls"]}次矩阵调用、{g["tool_seconds"]:.3f}秒；基准另外调用{g["baseline_solver_calls"]}次；'
        f'{g["independently_valid_cells"]}/12单元独立校验通过。',
        '固定A/B/C容量，只让逐时运行适应四个情景：基准、购电价×1.2、燃气价×1.2、光伏出力×0.8。'
        '负荷、供热、时段、预算及约束保持。仅比较该24小时购能费，投资另列；无NPV、不年化、不与全部投资混称生命周期费用。',
        '成本矩阵（元）：'+json.dumps(g['analysis']['cost_matrix'],ensure_ascii=False),
        '后悔矩阵（元）：'+json.dumps(g['analysis']['regret_matrix'],ensure_ascii=False),
        '最坏后悔（元）：'+json.dumps(g['analysis']['worst_regret_yuan'],ensure_ascii=False),
        '当前有限矩阵推荐：'+json.dumps(g['analysis']['recommended_ids'],ensure_ascii=False)+'。不是连续容量空间的全局稳健最优，也不是未来预测。',
        '## 证据与复现', '普通测试、加载数据和页面刷新不调用模型或求解器。完整JSON含来源、版本、输入指纹、求解状态、gap及独立校验。'
        '资源限制是现有求解适配器的协作式预算，不是进程级硬终止；未知结果不会展示成已确认不可行。']
    report = '\n\n'.join(lines)+'\n'
    (args.output/'summary.md').write_text(report, encoding='utf-8')
    if args.evidence:
        manifest = {}
        for kind, result in results.items():
            files = {'input.json': demo_task(kind).model_dump_json(indent=2).encode('utf-8'),
                     'result.json': Path(result.files['json']).read_bytes(),
                     'report.md': Path(result.files['markdown']).read_bytes()}
            if kind == 'regret': files['matrix.csv'] = Path(result.files['csv']).read_bytes()
            for suffix, content in files.items():
                name = kind+'_'+suffix
                (args.evidence/name).write_bytes(content)
                manifest[name] = hashlib.sha256(content).hexdigest()
        for name in ['summary.json', 'summary.md']:
            content = (args.output/name).read_bytes()
            (args.evidence/name).write_bytes(content)
            manifest[name] = hashlib.sha256(content).hexdigest()
        # Only known generated synthetic artifacts, never environment files.
        with ZipFile(args.evidence/'witnesses.zip', 'w', ZIP_DEFLATED) as archive:
            for p in sorted(args.output.rglob('*')):
                if p.is_file() and p.suffix in ('.json', '.csv', '.md'):
                    name = p.relative_to(args.output).as_posix()
                    archive.write(p, name)
                    manifest['witnesses/'+name] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest['witnesses.zip'] = hashlib.sha256((args.evidence/'witnesses.zip').read_bytes()).hexdigest()
        (args.evidence/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
