"""Actual complete-year optimization, artificial constant fixture, no network."""
import numpy as np
import pandas as pd
import pytest

from energy_agent.agent import EnergyAgent,revise_task
from energy_agent.annual import default_economics
from energy_agent.data import make_demo_task
from energy_agent.economics import annuity_factor
from energy_agent.schemas import CAPACITY_FIELDS,CapacityBounds,CapacityRange,TaskRequest,TaskPatch
from energy_agent.modifications import compile_contract


def test_additional_annual_fixed_fee_is_once_per_year_and_changes_npv_not_initial_budget(tmp_path):
    raw=make_demo_task(hours=1).model_dump()
    times=pd.date_range('2021-01-01','2022-01-01',freq='h',inclusive='left',tz='Asia/Shanghai')
    raw['data']['timestamps']=times.to_pydatetime().tolist()
    constants={'electric_load_kw':10,'heat_load_kw_th':20,'pv_per_kw':0,'electricity_price':1,'gas_price':.5,'grid_emission_factor':.55,'gas_emission_factor':.202}
    for key,value in constants.items():raw['data'][key]=[value]*len(times)
    raw['candidates']=[raw['candidates'][0]];raw['candidates'][0]['boiler_kw_th']=20
    raw['economics']=default_economics(raw['devices']['source_id']).model_dump()
    raw['resolution']='full_year';raw['planning_mode']='capacity'
    raw['capacity_bounds']=CapacityBounds(source_id=raw['devices']['source_id'],**{k:CapacityRange(lower=20 if k=='boiler_kw_th' else 0,upper=20 if k=='boiler_kw_th' else 0) for k in CAPACITY_FIELDS}).model_dump()
    task=TaskRequest.model_validate(raw)
    agent=EnergyAgent(tmp_path)
    first=agent.run(task);assert first.scenarios[0].validation.valid
    contract=compile_contract('项目额外年固定维护费改为1万元，供热不变',first)
    second=agent.run(revise_task(task,contract.patch,first.run_id),previous=first)
    a,b=first.scenarios[0],second.scenarios[0]
    assert b.validation.valid
    assert b.economics.npv_cost_yuan-a.economics.npv_cost_yuan==pytest.approx(10000*annuity_factor(task.economics))
    assert b.investment_yuan==a.investment_yuan
    assert b.validation.metrics.operating_cost_yuan==a.validation.metrics.operating_cost_yuan
    assert b.economics.horizon_operating_emissions_kg==a.economics.horizon_operating_emissions_kg
    assert all(f.fixed_om_yuan-a.economics.cashflows[f.year].fixed_om_yuan==10000 for f in b.economics.cashflows[1:])
    assert b.dispatch.model_statistics.objective_value==pytest.approx(b.economics.npv_cost_yuan)
