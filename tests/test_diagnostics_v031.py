from pathlib import Path
from hashlib import sha256

import pytest

from energy_agent.annual import build_annual_case
from energy_agent.diagnostics import diagnose_peak,export_diagnostics


def test_actual_peak_and_jump_neighbors_do_not_change_source_or_load(tmp_path):
    raw=Path('examples/shanghai_2017/records.csv');before=sha256(raw.read_bytes()).hexdigest()
    task=build_annual_case(heat=True,bundle_dir='examples/shanghai_2017',retain_flagged_jumps=True)
    original=task.model_dump_json()
    d=diagnose_peak(task)
    assert len(d.jumps)==2 and d.peak_kw==pytest.approx(4907.06)
    assert d.baseline_no_pv_storage_required_grid_kw==d.peak_kw
    assert len(d.peak_neighbors)==7
    assert max(r['electric_load_kw'] for r in d.peak_neighbors)==d.peak_kw
    assert d.peak_necessary_battery_power_kw==0
    assert '必要条件' in d.summary and '不是校准' in d.treatment
    export_diagnostics(d,tmp_path)
    assert (tmp_path/'peak_diagnostics.json').exists()
    assert task.model_dump_json()==original
    assert sha256(raw.read_bytes()).hexdigest()==before
    task.constraints.grid_limit_kw=100
    constrained=diagnose_peak(task)
    assert constrained.peak_necessary_battery_power_kw>0
    assert constrained.peak_necessary_battery_power_kw<=d.peak_kw
