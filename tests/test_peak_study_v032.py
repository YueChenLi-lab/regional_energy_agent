"""Published-array treatment tests; synthetic small runs exercise the full exporter."""
from hashlib import sha256
from pathlib import Path
import json

import pytest

from energy_agent.annual import build_annual_case
from energy_agent.modifications import fingerprint
from energy_agent.peak_sensitivity import PeakStudySpec,derive_peak_tasks,fixed_controls,standardized_csv,robustness_conclusion


@pytest.fixture(scope='module')
def annual_inputs():
    return build_annual_case(bundle_dir='examples/shanghai_2017',heat=True,retain_flagged_jumps=True)


def test_only_predeclared_point_is_edited_and_all_other_controls_are_fixed(annual_inputs):
    raw=Path('examples/shanghai_2017/records.csv');digest=sha256(raw.read_bytes()).hexdigest()
    original=annual_inputs.model_dump_json();spec=PeakStudySpec.model_validate_json(Path('configs/peak_sensitivity_v032.json').read_text())
    parent_sha=sha256(standardized_csv(annual_inputs)).hexdigest()
    variants,evidence=derive_peak_tasks(annual_inputs,spec,raw_file_sha256=digest,parent_normalized_sha256=parent_sha)
    assert annual_inputs.model_dump_json()==original and sha256(raw.read_bytes()).hexdigest()==digest
    point=annual_inputs.data.timestamps.index(spec.points[0].timestamp)
    assert variants['linear'].data.electric_load_kw[point]==pytest.approx(242.43)
    assert variants['local_cap'].data.electric_load_kw[point]==900
    controls=fingerprint(fixed_controls(annual_inputs))
    for method,task in variants.items():
        assert fingerprint(fixed_controls(task))==controls
        changed=[i for i,(a,b) in enumerate(zip(task.data.electric_load_kw,annual_inputs.data.electric_load_kw)) if a!=b]
        assert changed==([] if method=='original' else [point])
        assert task.capacity_bounds==annual_inputs.capacity_bounds and task.constraints==annual_inputs.constraints
        if method!='original':
            source=next(s for s in task.sources if s.source_id==task.data.source_ids['electric_load_kw'])
            record=json.loads(source.processing[0]);assert source.category=='assumption'
            assert record['raw_file_sha256']==digest and record['parent_normalized_sha256']==parent_sha
            assert evidence[method]['changes'][0]['predeclared_rule_cap_kw']==900
            assert sum(task.data.electric_load_kw)-sum(annual_inputs.data.electric_load_kw)==pytest.approx(evidence[method]['changes'][0]['affected_energy_kwh'])


@pytest.mark.parametrize('fault',['duplicate','wrong_value','endpoint','naive'])
def test_treatment_spec_refuses_wrong_or_unbracketed_points(annual_inputs,fault):
    spec=PeakStudySpec.model_validate_json(Path('configs/peak_sensitivity_v032.json').read_text())
    if fault=='duplicate':spec.points.append(spec.points[0])
    elif fault=='wrong_value':spec.points[0].expected_original_kw=100
    elif fault=='endpoint':spec.points[0].timestamp=annual_inputs.data.timestamps[0]
    elif fault=='naive':spec.points[0].timestamp=spec.points[0].timestamp.replace(tzinfo=None)
    with pytest.raises(ValueError):derive_peak_tasks(annual_inputs,spec,raw_file_sha256='0'*64,parent_normalized_sha256='1'*64)


def test_sensitivity_conclusion_is_qualified_when_solve_has_not_proved_optimal():
    spec=PeakStudySpec.model_validate_json(Path('configs/peak_sensitivity_v032.json').read_text())
    row=dict(feasible=True,method='original',status='feasible_limit',mip_gap=.1,npv_cost_yuan=1000,
        pv_kw=100,battery_power_kw=10,battery_energy_kwh=40,hp_kw_th=10,boiler_kw_th=10)
    note=robustness_conclusion([row,{**row,'method':'linear','pv_kw':120}],spec)
    assert '敏感' in note and '未证明最优' in note and '不能把全部差值归因于设备配置改善' in note


def test_standardized_export_reloads_through_existing_csv_contract(annual_inputs,tmp_path):
    from energy_agent.data import load_csv
    path=tmp_path/'标准 导出.csv';path.write_bytes(standardized_csv(annual_inputs))
    loaded=load_csv(path,{k:getattr(annual_inputs.data,k) for k in ('step_hours','units','source_ids')})
    assert loaded.timestamps==annual_inputs.data.timestamps
    assert loaded.electric_load_kw==pytest.approx(annual_inputs.data.electric_load_kw,abs=1e-10)
    assert sum(loaded.electric_load_kw)*loaded.step_hours==pytest.approx(3961671.29,abs=.01)
