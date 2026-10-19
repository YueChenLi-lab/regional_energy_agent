"""Archive and independently recheck already-computed matrices; never solves."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from energy_agent.counterfactual import digest
from energy_agent.data import validate_inputs
from energy_agent.economics import evaluate_economics
from energy_agent.evaluation import validate_solution
from energy_agent.regret import (RegretRequest, RegretResult, capacity_fingerprint,
                                 derive_scenario, bind_candidate)
from energy_agent.regret_math import analyze_regret
from energy_agent.schemas import RunResult, ValidationRequest


def archive(source, output):
    if output.exists() and any(output.iterdir()):
        raise ValueError('请使用新的空归档目录，不覆盖证据')
    output.mkdir(parents=True,exist_ok=True)
    summaries=json.loads((source/'summary.json').read_text(encoding='utf-8'))
    files={}
    def save(name, content, compressed=False):
        path=output/name
        path.write_bytes(gzip.compress(content,mtime=0) if compressed else content)
        files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    for item in summaries:
        name=item['case']
        request=RegretRequest.model_validate_json((source/name/'request.json').read_bytes())
        result=RegretResult.model_validate_json(Path(item['files']['json']).read_bytes())
        save(name+'_request.json.gz',request.model_dump_json().encode(),True)
        save(name+'_result.json',result.model_dump_json(indent=2).encode())
        save(name+'_report.md',Path(result.files['markdown']).read_bytes())
        save(name+'_matrix.csv',Path(result.files['csv']).read_bytes())
        for cell in result.cells:
            if cell.result_file:
                save(f'{name}_{cell.candidate_id}_{cell.scenario_id}_run.json.gz',Path(cell.result_file).read_bytes(),True)
    save('summary.json',(source/'summary.json').read_bytes())
    save('summary.md',(source/'summary.md').read_bytes())
    (output/'manifest.json').write_text(json.dumps({'format':'regret-evidence-v1','files':files},ensure_ascii=False,indent=2),encoding='utf-8')


def verify(output):
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    for name,sha in manifest['files'].items():
        path=(output/name).resolve()
        if not path.is_relative_to(output.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('归档校验值不符：'+name)
    checks=[]
    for path in sorted(output.glob('*_result.json')):
        name=path.name.removesuffix('_result.json')
        result=RegretResult.model_validate_json(path.read_bytes())
        req=RegretRequest.model_validate_json(gzip.decompress((output/(name+'_request.json.gz')).read_bytes()))
        assert result.request_sha256==digest(req.model_dump(mode='json',exclude={'output_dir'}))
        for cell in result.cells:
            if cell.result_file is None:
                continue
            witness=gzip.decompress((output/f'{name}_{cell.candidate_id}_{cell.scenario_id}_run.json.gz').read_bytes())
            assert hashlib.sha256(witness).hexdigest()==cell.result_sha256
            run=RunResult.model_validate_json(witness)
            scenario=next(s for s in req.scenarios if s.scenario_id==cell.scenario_id)
            candidate=next(c.candidate for c in req.candidates if c.candidate.candidate_id==cell.candidate_id)
            expected=bind_candidate(derive_scenario(req.baseline.task,scenario,req.base_run_id),candidate,cell.cache_key,req.cost_basis)
            assert digest(run.task)==digest(expected)==cell.task_sha256
            assert run.run_id==cell.run_id and run.input_version==req.input_version+1
            if cell.cost_yuan is not None:
                solved=run.scenarios[0]
                independent=validate_solution(ValidationRequest(task=validate_inputs(run.task).task,candidate=solved.candidate,dispatch=solved.dispatch))
                assert independent.valid and cell.validation.valid
                assert capacity_fingerprint(solved.candidate)==cell.capacity_sha256
                economics=evaluate_economics(run.task,solved.candidate,solved.dispatch,independent.metrics)
                cost=economics.npv_cost_yuan if economics else independent.metrics.operating_cost_yuan
                assert abs(cost-cell.cost_yuan)<=req.cost_tolerance_yuan
                expected_objective=solved.dispatch.model_statistics.objective_value if economics else solved.dispatch.objective_yuan
                assert abs(cost-expected_objective)<=req.cost_tolerance_yuan
            checks.append({'case':name,'candidate':cell.candidate_id,'scenario':cell.scenario_id,
                'run_id':cell.run_id,'cost_yuan':cell.cost_yuan,'witness_verified':True})
        analysis=analyze_regret(result.cells,[c.candidate.candidate_id for c in req.candidates],
            [s.scenario_id for s in req.scenarios],next(s.scenario_id for s in req.scenarios if s.is_baseline),req.cost_tolerance_yuan)
        assert analysis==result.analysis
    report={'method':'SHA256 + original-derived input equality + fixed capacities + independent physics + cost/objective + matrix recalculation; no new solves',
            'verified_cells':len(checks),'cells':checks}
    (output/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(checks)} archived cell witnesses verified; no solver/model invoked')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='省略时仅重验归档')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.source:
        archive(args.source,args.output)
    verify(args.output)
