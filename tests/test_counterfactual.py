"""Real small MILPs, explicit unknown-state simulations, no paid model calls."""
import hashlib
from pathlib import Path

import pytest

from energy_agent.agent import EnergyAgent, ToolRegistry
from energy_agent.counterfactual import (CounterfactualRequest, RepairRange, adopt_counterfactual_path,
    clarify_repair_request, data_fingerprint, search_counterfactual_repairs)
from energy_agent.counterfactual_cases import make_repair_case
from energy_agent.data import make_demo_task
from energy_agent.planning import investment_yuan
from energy_agent.schemas import DispatchResult, RunResult


def request(tmp_path, task=None, field='budget_yuan', **changes):
    task = task or make_demo_task(hours=6)
    if task is not None and field == 'budget_yuan' and 'baseline' not in changes:
        task = task.model_copy(deep=True)
    origin = getattr(task.constraints, field)
    ranges = {'budget_yuan': (100000., 10., '元'), 'grid_limit_kw': (200., .01, 'kW'),
              'emission_limit_kg': (max(2000.,len(task.data.timestamps)*100.), .05, 'kgCO2e')}
    upper, precision, unit = ranges[field]
    base = dict(task=task, request_id='repair-001', base_run_id='confirmed-task-001', input_version=task.version,
                data_fingerprint=data_fingerprint(task), allowed_fields=[field], ranges={field:RepairRange(lower=origin,upper=max(upper,origin+1),precision=precision,unit=unit)},
                output_dir=str(tmp_path), single_solve_seconds=2, max_solver_calls=64, total_seconds=30)
    base.update(changes)
    if base.get('baseline') is not None:
        base['task'] = None
    return CounterfactualRequest(**base)


def boiler_task(hours=6):
    t = make_demo_task(hours=hours)
    t.candidates = t.candidates[:1]
    return t


def test_budget_boundary_heat_period_sources_and_real_final_validation(tmp_path):
    task=boiler_task();task.constraints.budget_yuan=0
    before=task.model_dump_json()
    result=search_counterfactual_repairs(request(tmp_path,task))
    p=result.paths[0]
    cost=investment_yuan(task.candidates[0],task.devices)
    assert result.baseline_verification.feasibility=='infeasible'
    assert result.baseline_verification.solver_statuses=={'A':'rejected'}
    assert result.baseline_verification.verified_precheck_exclusions==['A']
    assert p.status=='verified_repair' and p.boundary_precision_reached
    assert cost-1e-4<=p.suggested_value<=cost+p.search_range.precision
    assert p.known_infeasible_lower<p.suggested_value
    assert p.suggested_value-p.known_infeasible_lower<=p.search_range.precision
    assert p.final_validation.valid and p.locks_preserved and p.solver_status=='optimal'
    assert p.metrics['supply_satisfied'] and p.unit=='元'
    run=RunResult.model_validate_json(Path(p.result_file).read_bytes())
    assert run.task.data==task.data
    assert run.task.sources[:-1]==task.sources
    assert run.task.parent_run_id==result.base_run_id
    assert run.input_version==task.version+1
    assert task.model_dump_json()==before
    assert hashlib.sha256(Path(p.result_file).read_bytes()).hexdigest()==p.result_sha256
    assert result.data_fingerprint==data_fingerprint(task)
    assert Path(result.files['markdown']).is_file()
    assert '不自动采用' in Path(result.files['markdown']).read_text(encoding='utf-8')


@pytest.mark.parametrize('hours',[6,24,168])
def test_emission_boundary_is_period_specific_and_really_solved(tmp_path,hours):
    task=boiler_task(hours);task.constraints.emission_limit_kg=0
    result=search_counterfactual_repairs(request(tmp_path,task,field='emission_limit_kg'))
    p=result.paths[0]
    assert p.suggested_value is not None and p.boundary_precision_reached
    assert p.metrics['period_hours']==hours
    assert p.metrics['emissions_kg']<=p.suggested_value+1e-4
    assert p.suggested_value-p.metrics['emissions_kg']<=p.search_range.precision+1e-4
    assert p.unit=='kgCO2e' and task.constraints.emission_limit_kg==0


def test_grid_boundary_and_single_parameter_failure_from_conflicting_constraints(tmp_path):
    task=boiler_task();task.constraints.grid_limit_kw=0
    p=search_counterfactual_repairs(request(tmp_path/'grid',task,field='grid_limit_kw')).paths[0]
    assert p.boundary_precision_reached
    assert max(task.data.electric_load_kw)<=p.suggested_value+1e-5
    assert p.suggested_value-max(task.data.electric_load_kw)<=.01
    task.constraints.budget_yuan=0
    result=search_counterfactual_repairs(request(tmp_path/'conflict',task))
    p=result.paths[0]
    assert p.suggested_value is None and p.status=='not_found'
    assert all(t.feasibility=='infeasible' for t in p.trace)
    assert p.trace[-1].value==p.search_range.upper
    assert '尚未找到' in p.note


def test_three_paths_are_alternatives_same_inputs_and_control_boundaries(tmp_path):
    task=make_repair_case()
    ranges={'budget_yuan':RepairRange(lower=60000,upper=600000,precision=1000,unit='元'),
            'emission_limit_kg':RepairRange(lower=230,upper=300,precision=.05,unit='kgCO2e'),
            'grid_limit_kw':RepairRange(lower=12,upper=25,precision=.01,unit='kW')}
    req=request(tmp_path,task,allowed_fields=list(ranges),ranges=ranges,max_solver_calls=128)
    result=ToolRegistry().call('search_counterfactual_repairs',req)
    assert result.baseline_verification.feasibility=='infeasible'
    assert len(result.paths)==3
    assert all(p.boundary_precision_reached and p.final_validation.valid for p in result.paths)
    assert [p.candidate['candidate_id'] for p in result.paths]==['D','A','C']
    for p in result.paths:
        run=RunResult.model_validate_json(Path(p.result_file).read_bytes())
        for f in ranges:
            assert getattr(run.task.constraints,f)==(p.suggested_value if f==p.field else getattr(task.constraints,f))
        assert run.task.data==task.data and run.task.candidates==task.candidates


@pytest.mark.parametrize('change,match',[
    ({'locked_conditions':['budget_yuan']},'锁定'),
    ({'allowed_fields':['budget_yuan','grid_limit_kw']},'授权字段'),
    ({'input_version':2},'版本'),
    ({'data_fingerprint':'0'*64},'指纹'),
    ({'locked_conditions':['cooling_guarantee']},'未支持'),
])
def test_invalid_permission_and_binding_rejected_before_solving(tmp_path,change,match):
    task=boiler_task();task.constraints.budget_yuan=0
    with pytest.raises(ValueError,match=match):request(tmp_path,task,**change)


def test_absent_carbon_constraint_wrong_units_and_forbidden_field_cannot_be_invented(tmp_path):
    task=boiler_task();task.constraints.emission_limit_kg=None
    with pytest.raises(ValueError,match='没有排放上限'):
        request(tmp_path,task,allowed_fields=['emission_limit_kg'],ranges={'emission_limit_kg':RepairRange(lower=0,upper=500,precision=1,unit='kgCO2e')})
    task.constraints.budget_yuan=0
    with pytest.raises(ValueError,match='单位'):
        request(tmp_path,task,ranges={'budget_yuan':RepairRange(lower=0,upper=100000,precision=10,unit='万元')})
    with pytest.raises(ValueError):request(tmp_path,task,allowed_fields=['heat_demand_scale'])


def test_feasible_baseline_does_not_search_without_explicit_exploration(tmp_path):
    task=boiler_task()
    result=search_counterfactual_repairs(request(tmp_path,task))
    assert result.status=='not_started' and result.solver_calls==1
    assert result.baseline_verification.feasibility=='feasible' and result.paths[0].trace==[]
    task.constraints.budget_yuan=100000
    result=search_counterfactual_repairs(request(tmp_path/'explore',task,explore_alternatives=True))
    assert result.paths[0].status=='already_feasible' and result.paths[0].adjustment is None


@pytest.mark.parametrize('outcome',['no_solution_limit','error','rejected'])
def test_unknown_or_failed_upper_stops_without_fabricated_bisection(tmp_path,monkeypatch,outcome):
    import energy_agent.agent as agent_module
    real=agent_module.solve_dispatch
    def solver(req):
        if req.task.constraints.budget_yuan>0:
            return DispatchResult(candidate_id=req.candidate.candidate_id,status=outcome,message='人工求解状态模拟，未产生解')
        return real(req)
    monkeypatch.setattr(agent_module,'solve_dispatch',solver)
    task=boiler_task();task.constraints.budget_yuan=0
    result=search_counterfactual_repairs(request(tmp_path,task,ranges={'budget_yuan':RepairRange(lower=0,upper=200000,precision=10,unit='元')}))
    p=result.paths[0]
    assert len(p.trace)==1 and p.trace[0].solver_statuses=={'A':outcome}
    assert p.trace[0].feasibility!='infeasible'
    assert not p.boundary_precision_reached and p.suggested_value is None
    assert p.known_infeasible_lower==0


def test_unknown_baseline_requires_explicit_exploration_and_never_certifies_boundary(tmp_path,monkeypatch):
    import energy_agent.agent as agent_module
    real=agent_module.solve_dispatch
    def solver(req):
        if req.task.constraints.budget_yuan==0:
            return DispatchResult(candidate_id=req.candidate.candidate_id,status='no_solution_limit',message='人工超时无解模拟')
        return real(req)
    monkeypatch.setattr(agent_module,'solve_dispatch',solver)
    task=boiler_task();task.constraints.budget_yuan=0
    result=search_counterfactual_repairs(request(tmp_path,task))
    assert result.status=='not_started' and not result.paths[0].trace
    result=search_counterfactual_repairs(request(tmp_path/'explicit',task,explore_alternatives=True,
        ranges={'budget_yuan':RepairRange(lower=0,upper=200000,precision=10,unit='元')}))
    p=result.paths[0]
    assert p.suggested_value==50000 and p.final_validation.valid
    assert not p.boundary_precision_reached and p.known_infeasible_lower is None


def test_feasible_limit_incumbent_is_feasible_but_not_claimed_optimal(tmp_path,monkeypatch):
    import energy_agent.agent as agent_module
    real=agent_module.solve_dispatch
    def solver(req):
        d=real(req)
        if d.status=='optimal':d.status='feasible_limit';d.mip_gap=.03
        return d
    monkeypatch.setattr(agent_module,'solve_dispatch',solver)
    task=boiler_task();task.constraints.budget_yuan=0
    p=search_counterfactual_repairs(request(tmp_path,task)).paths[0]
    assert p.final_validation.valid and p.boundary_precision_reached
    assert p.solver_status=='feasible_limit' and p.mip_gap==.03


def test_uncertain_midpoint_preserves_verified_upper_without_boundary_claim(tmp_path,monkeypatch):
    import energy_agent.agent as agent_module
    real=agent_module.solve_dispatch
    def solver(req):
        value=req.task.constraints.budget_yuan
        if value==25000:return DispatchResult(candidate_id='A',status='no_solution_limit',message='人工中点超时')
        return real(req)
    monkeypatch.setattr(agent_module,'solve_dispatch',solver)
    task=boiler_task();task.constraints.budget_yuan=0
    p=search_counterfactual_repairs(request(tmp_path,task,ranges={'budget_yuan':RepairRange(lower=0,upper=200000,precision=10,unit='元')})).paths[0]
    assert p.status=='uncertain' and p.suggested_value==50000
    assert p.final_validation.valid and not p.boundary_precision_reached
    assert p.known_infeasible_lower==0 and len(p.trace)==2


def test_budget_and_time_guard_include_baseline_and_do_not_label_exhaustion_infeasible(tmp_path,monkeypatch):
    task=boiler_task();task.constraints.budget_yuan=0
    result=search_counterfactual_repairs(request(tmp_path,task,max_solver_calls=1))
    assert result.solver_calls==1 and result.paths[0].status=='budget_exhausted'
    assert result.paths[0].suggested_value is None
    import energy_agent.counterfactual as module
    ticks=iter(i*.25 for i in range(100))
    monkeypatch.setattr(module,'perf_counter',lambda:next(ticks))
    result=search_counterfactual_repairs(request(tmp_path/'time',task,total_seconds=.5))
    assert result.solver_calls==0 and result.baseline_verification.feasibility=='uncertain'
    assert not result.paths[0].boundary_precision_reached


def test_duplicate_request_replays_and_changed_parameters_rejected(tmp_path,monkeypatch):
    task=boiler_task();task.constraints.budget_yuan=0
    req=request(tmp_path,task)
    first=search_counterfactual_repairs(req)
    def forbidden(*a,**k):raise AssertionError('Replay must not recompute')
    monkeypatch.setattr(EnergyAgent,'run',forbidden)
    assert search_counterfactual_repairs(req)==first
    req.max_solver_calls+=1
    with pytest.raises(ValueError,match='同一request_id'):search_counterfactual_repairs(req)
    assert task.constraints.budget_yuan==0


def test_explicit_adoption_uses_new_version_and_cannot_rebase_or_tamper(tmp_path):
    task=boiler_task();task.constraints.budget_yuan=0
    baseline=EnergyAgent(tmp_path/'base').run(task)
    req=request(tmp_path/'repair',task,baseline=baseline,base_run_id=baseline.run_id)
    result=search_counterfactual_repairs(req);p=result.paths[0]
    with pytest.raises(ValueError,match='显式确认'):
        adopt_counterfactual_path(result,baseline,p.path_id,confirmed=False,adoption_id='a1')
    adopted=adopt_counterfactual_path(result,baseline,p.path_id,confirmed=True,adoption_id='a1')
    assert adopted.input_version==baseline.input_version+1 and adopted.task.constraints.budget_yuan==p.suggested_value
    assert adopt_counterfactual_path(result,baseline,p.path_id,confirmed=True,adoption_id='a1')==adopted
    with pytest.raises(ValueError,match='基准'):
        adopt_counterfactual_path(result,adopted,p.path_id,confirmed=True,adoption_id='a2')
    Path(p.result_file).write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='校验值'):
        adopt_counterfactual_path(result,baseline,p.path_id,confirmed=True,adoption_id='a3')
    assert baseline.task.constraints.budget_yuan==0


def test_allowed_left_edge_is_not_claimed_as_threshold_outside_interval(tmp_path):
    task=boiler_task();task.constraints.budget_yuan=0
    p=search_counterfactual_repairs(request(tmp_path,task,ranges={'budget_yuan':RepairRange(lower=60000,upper=100000,precision=10,unit='元')})).paths[0]
    assert p.suggested_value==60000 and p.boundary_kind=='permitted_left_edge'
    assert p.boundary_precision_reached and len(p.trace)==1


def test_guidance_is_only_suggestion_and_preserves_absent_heat_carbon_context(tmp_path):
    base=EnergyAgent(tmp_path).run(boiler_task())
    guidance=clarify_repair_request('预算不能增加，碳约束可以放宽多少？',base)
    assert guidance.locked_fields==['budget_yuan'] and not guidance.requested_fields
    assert '没有排放上限' in guidance.clarification
    assert clarify_repair_request('预算不够，那至少还差多少？',base).requested_fields==['budget_yuan']
    assert not clarify_repair_request('随便改我的负荷',base).requested_fields
    base.task.assessment_mode='electric_only'
    assert '未建模供热' in clarify_repair_request('保持供热不变，还有什么可行的调整？',base).clarification


def test_final_recheck_failure_is_not_a_repair(tmp_path,monkeypatch):
    import energy_agent.counterfactual as module
    from energy_agent.schemas import ConstraintCheck,SolutionValidation
    monkeypatch.setattr(module,'validate_solution',lambda _:SolutionValidation(valid=False,checks=[ConstraintCheck(name='independent_recheck_fixture',passed=False,max_violation=1)]))
    task=boiler_task();task.constraints.budget_yuan=0
    p=search_counterfactual_repairs(request(tmp_path,task)).paths[0]
    assert p.status=='error' and p.suggested_value is None and not p.boundary_precision_reached


def test_model_numbers_cannot_replace_a_physical_check(tmp_path,monkeypatch):
    import energy_agent.agent as module
    real=module.solve_dispatch
    def tampered(req):
        dispatch=real(req)
        if dispatch.status=='optimal':dispatch.points[0].grid_kw+=5
        return dispatch
    monkeypatch.setattr(module,'solve_dispatch',tampered)
    task=boiler_task();task.constraints.budget_yuan=0
    p=search_counterfactual_repairs(request(tmp_path,task,ranges={'budget_yuan':RepairRange(lower=0,upper=200000,precision=10,unit='元')})).paths[0]
    assert p.status=='error' and p.suggested_value is None
    assert any('electric_balance' in reason for reason in p.trace[0].reasons)


def test_emission_species_precision_and_disable_are_enforced(tmp_path,monkeypatch):
    task=boiler_task();task.emission_species='CO2';task.constraints.emission_limit_kg=0
    for k in ('grid_emission_factor','gas_emission_factor'):
        task.data.units[k]=task.data.units[k].replace('CO2e','CO2')
        for source in task.sources:
            if k in source.units:source.units[k]=source.units[k].replace('CO2e','CO2')
    req=request(tmp_path,task,field='emission_limit_kg',ranges={'emission_limit_kg':RepairRange(lower=0,upper=1000,precision=.1,unit='kgCO2')})
    result=search_counterfactual_repairs(req)
    assert result.paths[0].metrics['emission_unit']=='kgCO2'
    with pytest.raises(ValueError,match='精度'):
        request(tmp_path/'tiny',task,field='emission_limit_kg',ranges={'emission_limit_kg':RepairRange(lower=0,upper=1000,precision=.000001,unit='kgCO2')})
    monkeypatch.setenv('ENERGY_AGENT_ENABLE_COUNTERFACTUAL','0')
    with pytest.raises(ValueError,match='关闭'):search_counterfactual_repairs(req)
