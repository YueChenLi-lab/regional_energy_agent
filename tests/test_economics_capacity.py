"""Business/physical checks; artificial short cases are separate from annual capture."""
import numpy as np
import pandas as pd
import pytest

from energy_agent.annual import default_economics, validate_calendar_year, HeatSimulation
from energy_agent.capacity import CapacitySolveRequest, solve_capacity
from energy_agent.data import make_demo_task
from energy_agent.economics import asset_flows, capacity_npv_coefficients, evaluate_economics, unit_investments
from energy_agent.evaluation import validate_solution
from energy_agent.optimization import solve_dispatch
from energy_agent.schemas import (CAPACITY_FIELDS, AssetEconomics, CapacityBounds, CapacityRange,
                                 Candidate, SolveRequest, ValidationRequest, TimeSeriesData)


def capacity_task(hours=12):
    t=make_demo_task(hours=hours)
    t.economics=default_economics('demo-equipment')
    t.capacity_bounds=CapacityBounds(source_id='demo-equipment',**{k:CapacityRange(upper=u) for k,u in zip(CAPACITY_FIELDS,[200,100,400,150,150])})
    t.planning_mode='capacity'
    # Artificial short horizon only exercises the solver; public Agent rejects
    # representative-year NPV until an actual complete calendar year is supplied.
    return t


def test_replacement_and_residual_no_terminal_purchase():
    a=AssetEconomics(lifetime_years=8,replacement_fraction=0.7)
    replacements,residual=asset_flows(800,a,20)
    assert replacements=={8:560,16:560}
    assert residual==280
    assert asset_flows(800,a,16)==({8:560},0)
    assert asset_flows(800,a,4)==({},400)
    assert asset_flows(800,a.model_copy(update={'residual_method':'none'}),4)==({},0)


@pytest.mark.parametrize('discount',[0,0.05])
def test_cashflows_npv_matches_linear_objective_without_double_counting(discount):
    t=capacity_task();t.economics.discount_rate=discount
    t.economics.horizon_years=20
    c=t.candidates[3]
    d=solve_dispatch(SolveRequest(task=t,candidate=c))
    v=validate_solution(ValidationRequest(task=t,candidate=c,dispatch=d))
    assert v.valid
    e=evaluate_economics(t,c,d,v.metrics)
    capital=np.array([getattr(c,k) for k in CAPACITY_FIELDS])@capacity_npv_coefficients(t.devices,t.economics)
    annual=sum((1+discount)**-y for y in range(1,21))
    assert e.npv_cost_yuan==pytest.approx(capital+t.devices.grid_connection_cost_yuan+annual*(e.annual_energy_cost_yuan+e.annual_variable_om_yuan))
    assert e.cashflows[0].investment_yuan==v.metrics.investment_yuan
    assert all(f.investment_yuan==0 for f in e.cashflows[1:])
    assert e.horizon_operating_emissions_kg==e.annual_emissions_kg*20
    if discount==0: assert e.npv_cost_yuan==pytest.approx(sum(f.net_yuan for f in e.cashflows))


def test_joint_capacity_fixed_bounds_regresses_to_dispatch():
    t=capacity_task();c=t.candidates[3]
    t.capacity_bounds=CapacityBounds(source_id=c.source_id,**{k:CapacityRange(lower=getattr(c,k),upper=getattr(c,k)) for k in CAPACITY_FIELDS})
    fixed=solve_dispatch(SolveRequest(task=t,candidate=c))
    result=solve_capacity(CapacitySolveRequest(task=t))
    v=validate_solution(ValidationRequest(task=t,candidate=result.candidate,dispatch=result.dispatch))
    assert v.valid
    assert result.dispatch.objective_yuan==pytest.approx(fixed.objective_yuan,abs=1e-5)
    assert all(getattr(result.candidate,k)==pytest.approx(getattr(c,k)) for k in CAPACITY_FIELDS)
    assert max(min(p.charge_kw,p.discharge_kw) for p in result.dispatch.points)<1e-6
    assert result.dispatch.soc_kwh[-1]==pytest.approx(result.dispatch.soc_kwh[0])


def test_capacity_analytical_heat_benchmark_and_budget_infeasibility():
    t=capacity_task(4);t.data.electric_load_kw=[10]*4;t.data.heat_load_kw_th=[20]*4
    t.data.pv_per_kw=[0]*4;t.data.electricity_price=[1]*4;t.data.gas_price=[1]*4
    for k in ('pv_kw','battery_power_kw','battery_energy_kwh'):
        setattr(t.capacity_bounds,k,CapacityRange(upper=0))
    t.constraints.budget_yuan=1000000
    r=solve_capacity(CapacitySolveRequest(task=t))
    assert r.dispatch.status=='optimal'
    # With four annual operating hours, boiler capital dominates heat pump.
    assert r.candidate.boiler_kw_th==pytest.approx(20)
    assert r.candidate.hp_kw_th==pytest.approx(0)
    v=validate_solution(ValidationRequest(task=t,candidate=r.candidate,dispatch=r.dispatch))
    assert v.valid
    t.constraints.budget_yuan=0
    assert solve_capacity(CapacitySolveRequest(task=t)).dispatch.status=='infeasible'
    t.constraints.budget_yuan=1000000;t.constraints.emission_limit_kg=0
    assert solve_capacity(CapacitySolveRequest(task=t)).dispatch.status=='infeasible'


@pytest.mark.parametrize('year,hours',[(2017,8760),(2020,8784)])
def test_full_year_calendar_local_utc_and_missing(year,hours):
    data=make_demo_task(hours=1).data
    times=pd.date_range(f'{year}-01-01',f'{year+1}-01-01',freq='h',inclusive='left',tz='Asia/Shanghai')
    d=data.model_copy(update={'timestamps':times.tz_convert('UTC').to_pydatetime().tolist()})
    assert len(times)==hours and validate_calendar_year(d)==year
    with pytest.raises(ValueError,match='完整日历年'):
        validate_calendar_year(d.model_copy(update={'timestamps':d.timestamps[:-1]}))
    with pytest.raises(ValueError):
        validate_calendar_year(d.model_copy(update={'timestamps':[d.timestamps[0]]*hours}))


def test_physical_heat_schedule_and_no_w_conversion():
    h=HeatSimulation(envelope_area_m2=100,envelope_u_w_m2_k=1,air_volume_m3=100,air_changes_per_hour=1)
    t=pd.date_range('2017-01-02 06:00',periods=3,freq='h',tz='Asia/Shanghai')
    assert h.calculate(t,[0,0,30])==pytest.approx([0,2.66,0])


def test_capacity_timeout_without_incumbent_and_with_incumbent(monkeypatch):
    from types import SimpleNamespace
    import energy_agent.capacity as module
    task=capacity_task(4)
    real=module.milp
    captured=[]
    def limited(*args,**kwargs):
        if not np.any(kwargs['integrality']):return SimpleNamespace(status=1,x=None)
        result=real(*args,**kwargs);result.status=1
        captured.append(result)
        return result
    monkeypatch.setattr(module,'milp',limited)
    result=module.solve_capacity(CapacitySolveRequest(task=task))
    assert result.dispatch.status=='feasible_limit'
    assert validate_solution(ValidationRequest(task=task,candidate=result.candidate,dispatch=result.dispatch)).valid
    monkeypatch.setattr(module,'milp',lambda *a,**k:SimpleNamespace(status=1,x=None))
    assert module.solve_capacity(CapacitySolveRequest(task=task)).dispatch.status=='no_solution_limit'


def test_capacity_independent_checks_detect_tampered_capacity():
    task=capacity_task(4)
    result=solve_capacity(CapacitySolveRequest(task=task))
    task.capacity_bounds.hp_kw_th.upper=0
    result.candidate.hp_kw_th=999
    validation=validate_solution(ValidationRequest(task=task,candidate=result.candidate,dispatch=result.dispatch))
    assert not validation.valid
    assert any(c.name=='capacity_bound_hp_kw_th' and not c.passed for c in validation.checks)
