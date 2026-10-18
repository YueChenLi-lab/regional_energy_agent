"""Actual licensed published files, offline annual solve; not synthetic fixtures."""
from pathlib import Path
import httpx
import numpy as np
import pytest

from energy_agent.annual import build_annual_case
from energy_agent.agent import EnergyAgent, revise_task
from energy_agent.conversation import heat_fingerprint
from energy_agent.schemas import SolverOptions, TaskPatch


@pytest.mark.parametrize('heat',[False,True])
def test_actual_captured_full_year_energy_balances_economics_and_budget(tmp_path,monkeypatch,heat):
    def forbidden(*a,**k):pytest.fail('published annual replay must not contact network')
    monkeypatch.setattr(httpx.Client,'send',forbidden)
    task=build_annual_case(bundle_dir=Path('examples/shanghai_2017'),heat=heat,retain_flagged_jumps=True)
    assert len(task.data.timestamps)==8760
    assert sum(task.data.electric_load_kw)==pytest.approx(3961671.29,abs=.0001)
    assert 'Q' in task.case_context.boundary and '2个' in task.case_context.quality_summary
    assert sum(task.data.heat_load_kw_th)==pytest.approx(437095.641 if heat else 0)
    assert not any('W暖通' in s.name for s in task.sources if s.source_id==task.data.source_ids['electric_load_kw'])
    agent=EnergyAgent(tmp_path, SolverOptions(time_limit_seconds=60,mip_rel_gap=.002))
    run=agent.run(task)
    assert run.state.value=='完成' and run.scenarios[0].validation.valid
    s=run.scenarios[0];points=s.dispatch.points
    assert len(points)==8760 and len(s.dispatch.soc_kwh)==8761
    assert max(min(p.charge_kw,p.discharge_kw) for p in points)<1e-5
    assert s.dispatch.soc_kwh[0]==pytest.approx(s.dispatch.soc_kwh[-1],abs=1e-5)
    assert s.economics.npv_cost_yuan==pytest.approx(s.dispatch.model_statistics.objective_value,abs=.0001)
    assert Path(run.files['markdown']).read_text().find('现金流')>=0
    if heat:
        reduced=revise_task(task,TaskPatch(budget_multiplier=.8,preserve_heat=True),parent_run_id=run.run_id)
        new=agent.run(reduced,previous=run)
        assert new.input_version==2 and new.run_id!=run.run_id
        assert heat_fingerprint(new.task)==heat_fingerprint(task)
        assert new.scenarios[0].validation.valid
        assert new.scenarios[0].investment_yuan<=8000000.0001
        assert 'delta_npv_cost_yuan' in new.changes['scenarios'][0]


def test_annual_capture_requires_explicit_warning_retention():
    from energy_agent.adapters import ImportQualityError
    with pytest.raises(ImportQualityError,match='跳变'):
        build_annual_case(bundle_dir='examples/shanghai_2017')
