"""Actual captured external data; distinct from artificial transport/format fixtures.

No network is used here. Network acquisition and published checksums were
verified separately and recorded with the bundle's source attribution.
"""
from pathlib import Path

import httpx
import pytest

from energy_agent.agent import EnergyAgent, revise_task
from energy_agent.replay import load_case_bundle
from energy_agent.schemas import TaskPatch


BUNDLE = Path(__file__).resolve().parents[1]/'examples'/'shanghai_168h'


def test_captured_real_case_parses_models_and_optimizes_offline(tmp_path,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('captured real case replay must not request network')
    monkeypatch.setattr(httpx,'Client',forbidden)
    task=load_case_bundle(BUNDLE)
    assert task.assessment_mode=='electric_only' and not task.demo
    assert task.sources[0].category=='measured'
    assert task.sources[0].artifacts[0].license_id=='CC-BY-4.0'
    assert len(task.data.timestamps)==168
    assert task.data.timestamps[0].isoformat()=='2017-01-01T00:00:00+08:00'
    assert sum(task.data.electric_load_kw)==pytest.approx(90087.69,abs=0.0002)
    assert sum(task.data.pv_per_kw)==pytest.approx(7.512929245142238,abs=1e-10)
    assert all(x==0 for x in task.data.heat_load_kw_th)
    agent=EnergyAgent(tmp_path)
    first=agent.run(task)
    assert all(s.validation.valid for s in first.scenarios)
    assert first.comparison.recommended_id=='GPB'
    grid=first.scenarios[0].validation.metrics
    assert grid.grid_kwh==pytest.approx(90087.69,abs=0.0002)
    assert grid.operating_cost_yuan==pytest.approx(67332.623,abs=0.0002)
    second=agent.run(revise_task(task,TaskPatch(budget_yuan=0),first.run_id),previous=first)
    assert second.input_version==2 and second.comparison.recommended_id=='G'
    assert all(s.dispatch.status=='rejected' for s in second.scenarios[1:])
