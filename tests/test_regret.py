"""Independent arithmetic, real small dispatches, and explicit status fixtures."""
from pathlib import Path

import pytest

from energy_agent.agent import EnergyAgent, ToolRegistry
from energy_agent.counterfactual import digest
from energy_agent.data import make_demo_task
from energy_agent.regret import (RegretRequest, RegretScenario, available_candidates, bind_candidate,
    capacity_fingerprint, default_scenarios, derive_scenario, evaluate_minimax_regret)
from energy_agent.regret_math import CostObservation, analyze_regret, regret_difference
from energy_agent.schemas import DispatchResult, RunResult


def observations(costs, statuses=None):
    result=[]
    for k,row in costs.items():
        for i,cost in enumerate(row):
            status=(statuses or {}).get((k,i),'optimal' if cost is not None else 'infeasible')
            feasibility={'optimal':'feasible','feasible_limit':'feasible','infeasible':'infeasible','no_solution_limit':'uncertain','rejected':'rejected'}[status]
            result.append(CostObservation(candidate_id=k,scenario_id=str(i),solver_status=status,
                feasibility=feasibility,cost_yuan=cost,cost_is_optimal=status=='optimal'))
    return result


def test_hand_computed_regret_baseline_and_minimax_cost_are_different():
    # Pure algorithm unit data, not an energy experiment or model output.
    a=analyze_regret(observations({'A':[100,160,220],'B':[120,130,180],'C':[150,140,160]}),['A','B','C'],['0','1','2'],'0')
    assert a.scenario_best_costs=={'0':100,'1':130,'2':160}
    assert a.regret_matrix=={'A':{'0':0,'1':30,'2':60},'B':{'0':20,'1':0,'2':20},'C':{'0':50,'1':10,'2':0}}
    assert a.worst_regret_yuan=={'A':60,'B':20,'C':50}
    assert a.recommended_ids==['B'] and a.baseline_cheapest_ids==['A'] and a.minimax_cost_ids==['C']
    assert a.status=='certified'


def test_per_scenario_best_includes_candidates_infeasible_elsewhere():
    a=analyze_regret(observations({'A':[1,None],'B':[2,3]}),['A','B'],['0','1'],'0')
    assert a.scenario_best_costs=={'0':1,'1':3}
    assert a.full_scenario_feasible_ids==['B'] and a.worst_regret_yuan['B']==1
    assert a.worst_regret_yuan['A'] is None and a.recommended_ids==['B']


def test_ties_preserved_and_no_arbitrary_infeasibility_penalty():
    a=analyze_regret(observations({'Z':[2,3],'A':[2,3]}),['Z','A'],['0','1'],'0')
    assert a.recommended_ids==['A','Z'] and a.scenario_best_ids['0']==['A','Z']
    no=analyze_regret(observations({'A':[None,None],'B':[None,None]}),['A','B'],['0','1'],'0')
    assert no.status=='no_recommendation' and not no.recommended_ids
    assert all(v is None for row in no.regret_matrix.values() for v in row.values())
    assert 'Infinity' not in no.model_dump_json() and 'NaN' not in no.model_dump_json()


@pytest.mark.parametrize('status',['no_solution_limit','rejected'])
def test_unknown_baseline_not_dropped_to_certify_full_set(status):
    a=analyze_regret(observations({'A':[1,None],'B':[2,3]},{('A',1):status}),['A','B'],['0','1'],'0')
    assert a.status=='partial' and a.recommended_ids==[] and a.provisional_ids==['B']
    assert not a.scenario_baselines_complete['1']


def test_feasible_limit_is_upper_cost_and_only_approximate():
    a=analyze_regret(observations({'A':[1,4],'B':[2,3]},{('A',1):'feasible_limit'}),['A','B'],['0','1'],'0')
    assert a.status=='approximate' and not a.scenario_baselines_complete['1']
    assert a.recommended_ids and '近似' in a.note


def test_optimal_solver_status_with_nonzero_or_missing_gap_not_exact_certificate():
    rows=observations({'A':[1,2],'B':[2,3]})
    rows[0].cost_is_optimal=False
    result=analyze_regret(rows,['A','B'],['0','1'],'0')
    assert result.status=='approximate' and not result.scenario_baselines_complete['0']


def test_empty_column_partial_matrix_and_negative_regret_are_not_silently_fixed():
    a=analyze_regret(observations({'A':[1,None],'B':[2,None]}),['A','B'],['0','1'],'0')
    assert a.scenario_best_costs['1'] is None and a.recommended_ids==[]
    assert all(a.regret_matrix[k]['1'] is None for k in ['A','B'])
    assert regret_difference(1-1e-5,1,1e-4)==0
    with pytest.raises(ValueError,match='负后悔'):regret_difference(.9,1,1e-4)
    obs=observations({'A':[1,2]})
    with pytest.raises(ValueError,match='完整'):analyze_regret(obs[:1],['A'],['0','1'],'0')
    with pytest.raises(ValueError,match='完整'):analyze_regret(obs+obs,['A'],['0','1'],'0')


@pytest.fixture
def baseline(tmp_path):
    return EnergyAgent(tmp_path/'baseline').run(make_demo_task(hours=24))


def request(tmp_path, baseline, **changes):
    raw=dict(request_id='matrix-001',baseline=baseline,base_run_id=baseline.run_id,input_version=baseline.input_version,
        input_sha256=digest(baseline.task),candidates=available_candidates(baseline)[:3],scenarios=default_scenarios(),
        cost_basis='period_energy',output_dir=str(tmp_path/'analysis'))
    raw.update(changes)
    return RegretRequest(**raw)


def test_actual_24_hour_matrix_fixed_capacities_reoptimizes_and_exports(tmp_path,baseline):
    before=baseline.model_dump_json()
    result=ToolRegistry().call('evaluate_minimax_regret',request(tmp_path,baseline))
    assert result.solver_calls==12 and result.analysis.status=='certified'
    assert all(c.capacities_fixed and c.validation.valid and c.cost_is_optimal for c in result.cells)
    assert len({c.cache_key for c in result.cells})==12 and len({c.run_id for c in result.cells})==12
    assert all(Path(p).is_file() for p in result.files.values())
    assert result.analysis.recommended_ids==result.analysis.baseline_cheapest_ids==['C']  # No manufactured robust victory.
    for cell in result.cells:
        selected=next(c for c in result.candidates if c.candidate.candidate_id==cell.candidate_id)
        run=RunResult.model_validate_json(Path(cell.result_file).read_bytes())
        assert cell.capacity_sha256==capacity_fingerprint(run.scenarios[0].candidate)==selected.capacity_sha256
        assert run.task.data.heat_load_kw_th==baseline.task.data.heat_load_kw_th
        assert run.task.data.timestamps==baseline.task.data.timestamps and run.task.constraints==baseline.task.constraints
        assert cell.npv_cost_yuan is None and cell.cost_yuan==cell.operating_cost_yuan
        assert cell.validation.metrics.period_hours==24
    assert baseline.model_dump_json()==before
    assert '不是生命周期投资最优' in result.explanation


def test_scenarios_independent_noncompound_and_explicit_load_authorization(tmp_path,baseline):
    s=RegretScenario(scenario_id='load',name='假设电负荷增10%',electric_load_multiplier=1.1)
    with pytest.raises(ValueError,match='授权'):request(tmp_path,baseline,scenarios=[default_scenarios()[0],s])
    req=request(tmp_path,baseline,scenarios=[default_scenarios()[0],s],allowed_changes=['electric_load_multiplier'],allow_electric_load_change=True)
    derived=derive_scenario(baseline.task,s,baseline.run_id)
    assert derived.data.electric_load_kw[0]==baseline.task.data.electric_load_kw[0]*1.1
    assert derived.data.heat_load_kw_th==baseline.task.data.heat_load_kw_th
    for scenario in default_scenarios()[1:3]:
        d=derive_scenario(baseline.task,scenario,baseline.run_id)
        assert d.data.electricity_price[0]==baseline.task.data.electricity_price[0]*scenario.electricity_price_multiplier
        assert d.data.gas_price[0]==baseline.task.data.gas_price[0]*scenario.gas_price_multiplier
        assert d.sources[:-1]==baseline.task.sources and d.sources[-1].category=='assumption'
    assert req.allow_electric_load_change


@pytest.mark.parametrize('data',[
    {'pv_multiplier':float('nan')},{'electricity_price_multiplier':-1},{'gas_price_multiplier':float('inf')},
    {'multiplier_unit':'%'},{'heat_load_multiplier':.8},{'grid_limit_kw':2000},
])
def test_illegal_scenario_values_units_and_fields_rejected(data):
    with pytest.raises(ValueError):RegretScenario(scenario_id='bad',name='bad',**data)


def test_unauthorized_pv_out_of_range_and_binding_metadata_rejected(tmp_path,baseline):
    with pytest.raises(ValueError,match='裁剪'):
        request(tmp_path,baseline,scenarios=[default_scenarios()[0],RegretScenario(scenario_id='pv',name='非法',pv_multiplier=10)])
    with pytest.raises(ValueError,match='授权'):
        request(tmp_path,baseline,allowed_changes=[])
    with pytest.raises(ValueError,match='指纹'):
        request(tmp_path,baseline,input_sha256='0'*64)
    selections=available_candidates(baseline)[:1]
    selections[0].candidate=selections[0].candidate.model_copy(update={'pv_kw':123.})
    with pytest.raises(ValueError,match='候选'):
        request(tmp_path,baseline,candidates=selections)
    with pytest.raises(ValueError,match='NPV'):
        request(tmp_path,baseline,cost_basis='npv')


def test_candidate_must_respect_original_capacity_bounds(tmp_path,baseline):
    from energy_agent.schemas import CapacityBounds,CapacityRange,CAPACITY_FIELDS
    task=baseline.task
    task.capacity_bounds=CapacityBounds(source_id=task.devices.source_id,**{k:CapacityRange(upper=1) for k in CAPACITY_FIELDS})
    with pytest.raises(ValueError,match='原始容量'):
        request(tmp_path,baseline,input_sha256=digest(task))


def test_infeasible_original_requires_repair_not_auto_relaxation(tmp_path):
    task=make_demo_task(hours=6);task.constraints.budget_yuan=0
    run=EnergyAgent(tmp_path/'base').run(task)
    with pytest.raises(ValueError,match='反事实'):request(tmp_path,run)
    assert run.task.constraints.budget_yuan==0


@pytest.mark.parametrize('status',['no_solution_limit','error','rejected','feasible_limit','infeasible'])
def test_actual_pipeline_preserves_solver_status_and_cost_availability(tmp_path,baseline,monkeypatch,status):
    import energy_agent.agent as module
    real=module.solve_dispatch
    def solve(req):
        if status=='feasible_limit':
            d=real(req);d.status='feasible_limit';d.mip_gap=.05;return d
        return DispatchResult(candidate_id=req.candidate.candidate_id,status=status,message='人工状态模拟，仅用于错误路径测试')
    monkeypatch.setattr(module,'solve_dispatch',solve)
    result=evaluate_minimax_regret(request(tmp_path,baseline))
    assert all(c.solver_status==status for c in result.cells)
    if status=='feasible_limit':
        assert result.analysis.status=='approximate' and all(c.validation.valid and not c.cost_is_optimal for c in result.cells)
    else:
        assert all(c.cost_yuan is None for c in result.cells)
        assert not result.analysis.recommended_ids
        assert result.analysis.status==('no_recommendation' if status=='infeasible' else 'partial')


def test_resource_exhaustion_and_idempotent_replay(tmp_path,baseline,monkeypatch):
    req=request(tmp_path,baseline,max_solver_calls=2)
    result=evaluate_minimax_regret(req)
    assert result.solver_calls==2 and len(result.cells)==12
    assert sum(c.feasibility=='not_run' for c in result.cells)==10
    assert result.analysis.status=='partial' and result.analysis.recommended_ids==[]
    import energy_agent.regret as module
    monkeypatch.setattr(module,'_evaluate',lambda *a:(_ for _ in ()).throw(AssertionError('Replay may not solve')))
    assert evaluate_minimax_regret(req)==result
    changed=req.model_copy(deep=True);changed.scenarios[1].electricity_price_multiplier=1.3
    with pytest.raises(ValueError,match='同一request_id'):evaluate_minimax_regret(changed)


def test_total_time_and_feature_switch(tmp_path,baseline,monkeypatch):
    import energy_agent.regret as module
    # Request validation is real; exhausted time is simulated only at the budget gate.
    clock=module.perf_counter
    monkeypatch.setattr(module,'perf_counter',lambda:clock()+100)
    result=evaluate_minimax_regret(request(tmp_path,baseline,total_seconds=1))
    assert result.solver_calls==0 and all(c.feasibility=='not_run' for c in result.cells)
    monkeypatch.setenv('ENERGY_AGENT_ENABLE_REGRET','0')
    with pytest.raises(ValueError,match='关闭'):evaluate_minimax_regret(request(tmp_path,baseline))


def test_fixed_capacity_npv_objective_accounts_for_maintenance_replacement_residual():
    """Artificial 4-hour objective unit benchmark, NOT an accepted annual case."""
    from energy_agent.annual import default_economics
    from energy_agent.capacity import solve_capacity,CapacitySolveRequest
    from energy_agent.economics import evaluate_economics
    from energy_agent.evaluation import validate_solution
    from energy_agent.optimization import solve_dispatch
    from energy_agent.schemas import Candidate,SolveRequest,ValidationRequest
    task=make_demo_task(hours=4)
    task.economics=default_economics(task.devices.source_id)
    task.economics.horizon_years=10;task.economics.discount_rate=0
    task.economics.hp_variable_om_per_kwh_th=1
    task.economics.assets['hp_kw_th'].lifetime_years=3
    task.data.electric_load_kw=[10.]*4;task.data.heat_load_kw_th=[20.]*4;task.data.electricity_price=[.1]*4
    c=Candidate(candidate_id='fixed',name='固定配置单元基准',source_id='demo-candidates',pv_kw=0,battery_power_kw=0,battery_energy_kwh=0,hp_kw_th=20,boiler_kw_th=20)
    bound=bind_candidate(task,c,'a'*64,'npv')
    assert all(getattr(bound.capacity_bounds,k).lower==getattr(bound.capacity_bounds,k).upper==getattr(c,k) for k in ['pv_kw','battery_power_kw','battery_energy_kwh','hp_kw_th','boiler_kw_th'])
    solved=solve_capacity(CapacitySolveRequest(task=bound,candidate_id='fixed'))
    checked=validate_solution(ValidationRequest(task=bound,candidate=solved.candidate,dispatch=solved.dispatch));assert checked.valid
    economic=evaluate_economics(bound,solved.candidate,solved.dispatch,checked.metrics)
    assert economic.npv_cost_yuan==pytest.approx(solved.dispatch.model_statistics.objective_value,abs=1e-4)
    assert sum(p.hp_heat_kw_th for p in solved.dispatch.points)==pytest.approx(0,abs=1e-6)
    raw=task.model_copy(deep=True);raw.economics=None
    energy=solve_dispatch(SolveRequest(task=raw,candidate=c))
    assert sum(p.hp_heat_kw_th for p in energy.points)==pytest.approx(80)
    assert any(f.replacement_yuan>0 for f in economic.cashflows) and economic.cashflows[-1].residual_credit_yuan>0
    assert economic.npv_cost_yuan==pytest.approx(sum(f.net_yuan for f in economic.cashflows))


def test_battery_configuration_recourse_and_validation_failure_not_scored(tmp_path,baseline,monkeypatch):
    selections=available_candidates(baseline)
    req=request(tmp_path,baseline,request_id='battery',candidates=[selections[0],selections[3]],
                scenarios=[default_scenarios()[i] for i in (0,1,3)])
    result=evaluate_minimax_regret(req)
    assert len(result.cells)==6 and all(c.validation.valid for c in result.cells)
    for cell in result.cells:
        if cell.candidate_id=='D':
            run=RunResult.model_validate_json(Path(cell.result_file).read_bytes())
            assert run.scenarios[0].dispatch.soc_kwh[0]==pytest.approx(run.scenarios[0].dispatch.soc_kwh[-1])
            assert all(p.charge_kw*p.discharge_kw<1e-6 for p in run.scenarios[0].dispatch.points)
    import energy_agent.agent as module
    real=module.solve_dispatch
    def invalid(req):
        dispatch=real(req)
        dispatch.points[0].grid_kw+=100
        return dispatch
    monkeypatch.setattr(module,'solve_dispatch',invalid)
    rejected=evaluate_minimax_regret(request(tmp_path,baseline,request_id='invalid',candidates=[selections[0]],scenarios=default_scenarios()[:1]))
    assert rejected.cells[0].feasibility=='error' and rejected.cells[0].cost_yuan is None
    assert not rejected.cells[0].validation.valid and not rejected.analysis.recommended_ids


def test_interrupted_request_not_silently_reexecuted(tmp_path,baseline,monkeypatch):
    import energy_agent.regret as module
    req=request(tmp_path,baseline)
    def interrupted(*a):raise RuntimeError('人工进程中断')
    monkeypatch.setattr(module,'_evaluate',interrupted)
    with pytest.raises(RuntimeError):evaluate_minimax_regret(req)
    with pytest.raises(ValueError,match='中断'):evaluate_minimax_regret(req)


def test_recourse_dispatch_actually_adapts_not_just_scaled_metrics(tmp_path,baseline):
    req=request(tmp_path,baseline,candidates=available_candidates(baseline)[2:3],
                scenarios=[default_scenarios()[0],default_scenarios()[2]])
    result=evaluate_minimax_regret(req)
    runs=[RunResult.model_validate_json(Path(c.result_file).read_bytes()) for c in result.cells]
    assert result.cells[0].capacity_sha256==result.cells[1].capacity_sha256
    first,other=[sum(p.hp_heat_kw_th for p in r.scenarios[0].dispatch.points) for r in runs]
    assert abs(first-other)>1  # Higher gas price changes actual hourly heating allocation.
