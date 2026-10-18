"""Artificial format fixtures only. Real external-file acceptance is documented separately."""
import json
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from energy_agent.adapters import (ImportQualityError, MeterSelection, fetch_cached, import_energydetective)
from energy_agent.agent import EnergyAgent, revise_task
from energy_agent.cli import main
from energy_agent.data import case_label, load_csv, validate_inputs
from energy_agent.quality import IntervalContract, inspect_series, normalize_intervals
from energy_agent.real_case import ElectricCaseParameters, PricePeriod, TariffSettings, build_electric_task, export_import, load_hourly_tariff
from energy_agent.schemas import Candidate, TaskPatch


@pytest.fixture
def artificial_csv(tmp_path):
    path = tmp_path / "ARTIFICIAL_energydetective_format.csv"
    times = pd.date_range("2017-01-01", periods=48, freq="h")
    rows = [{"Time": t.isoformat(sep=" "), "Type": meter, "Record": value}
            for t in times for meter,value in [("Q",20.0),("W",10.0)]]
    pd.DataFrame(rows).to_csv(path,index=False)
    return path


def selection(**changes):
    return MeterSelection(building="test", meters=["Q","W"], timestamp_position="start",
        acknowledge_category_sum=True, timestamp_assumption_acknowledged=True,
        data_kind="artificial_fixture", **changes)


def test_power_energy_and_cumulative_resampling_are_distinct_and_conserve_energy():
    starts=pd.date_range("2017-01-01",periods=8,freq="15min")
    kwargs=dict(source_step_minutes=15,source_timezone="Asia/Shanghai",numeric_precision=0.01)
    power,a=normalize_intervals(starts,[8]*8,IntervalContract(quantity="power_kw",timestamp_position="start",**kwargs))
    energy,b=normalize_intervals(starts,[2]*8,IntervalContract(quantity="interval_kwh",timestamp_position="start",**kwargs))
    cumulative,c=normalize_intervals(pd.date_range(starts[0],periods=9,freq="15min"),list(range(0,18,2)),IntervalContract(quantity="cumulative_kwh",timestamp_position="boundary",**kwargs))
    assert power.electric_load_kw.tolist()==energy.electric_load_kw.tolist()==cumulative.electric_load_kw.tolist()==[8,8]
    assert a.raw_energy_kwh==b.raw_energy_kwh==c.raw_energy_kwh==16
    assert all(x.passed and abs(x.difference_kwh)<=x.tolerance_kwh for x in [a,b,c])
    wrong,_=normalize_intervals(starts,[8]*8,IntervalContract(quantity="interval_kwh",timestamp_position="start",**kwargs))
    assert wrong.electric_load_kw.tolist()==[32,32]  # kWh must not be averaged as if kW.


def test_utc_interval_end_alignment_preserves_historical_date():
    ends=pd.date_range("2016-12-31T16:15:00Z",periods=4,freq="15min")
    frame,audit=normalize_intervals(ends,[2]*4,IntervalContract(quantity="interval_kwh",source_step_minutes=15,
        timestamp_position="end",source_timezone="UTC",numeric_precision=0.01))
    assert frame.timestamp.iloc[0].isoformat()=="2017-01-01T00:00:00+08:00"
    assert frame.electric_load_kw.iloc[0]==8 and audit.normalized_energy_kwh==8


@pytest.mark.parametrize("case",["gap","duplicate","negative","nan","infinite","text","jump","off_grid","empty"])
def test_quality_risks_are_reported_without_silent_changes(case):
    times=list(pd.date_range("2017-01-01",periods=4,freq="h"))
    values=[10.0]*4
    expected={"gap":"missing_interval","duplicate":"duplicate_timestamp","negative":"negative_value","nan":"missing_value",
        "infinite":"nonfinite_value","text":"nonfinite_value","jump":"abnormal_jump","off_grid":"off_grid_interval","empty":"empty_series"}
    if case=="gap": del times[1];del values[1]
    elif case=="duplicate":times[1]=times[0]
    elif case=="negative":values[1]=-1
    elif case=="nan":values[1]=np.nan
    elif case=="infinite":values[1]=np.inf
    elif case=="text":values[1]="bad"
    elif case=="jump":values[1]=1000
    elif case=="off_grid":times[1]+=pd.Timedelta(minutes=5)
    else:times=[];values=[]
    report=inspect_series(times,values,step_minutes=60,timezone="Asia/Shanghai",scope="人工异常样本")
    assert not report.valid
    assert expected[case] in {f.code for f in report.findings}
    assert report.records==len(values)


def test_partial_bins_and_counter_resets_are_rejected():
    contract=IntervalContract(quantity="power_kw",source_step_minutes=15,timestamp_position="start",source_timezone="Asia/Shanghai",numeric_precision=0.01)
    with pytest.raises(ValueError,match="不完整"):
        normalize_intervals(pd.date_range("2017-01-01 00:15",periods=4,freq="15min"),[8]*4,contract)
    with pytest.raises(ValueError,match="下降/复位"):
        normalize_intervals(pd.date_range("2017-01-01",periods=3,freq="h"),[100,110,5],IntervalContract(quantity="cumulative_kwh",source_step_minutes=60,timestamp_position="boundary",source_timezone="Asia/Shanghai",numeric_precision=0.01))


def test_meter_categories_aggregate_only_after_boundary_acknowledgement(artificial_csv):
    chosen=selection()
    load=import_energydetective(artificial_csv,chosen,hours=24)
    assert load.frame.electric_load_kw.tolist()==[30]*24
    assert load.audit.raw_energy_kwh==720
    assert load.audit.normalized_energy_kwh==720
    assert all(r.valid and r.duplicate_records==0 for r in load.selected_reports)
    assert "不声称全楼总电量" in load.boundary
    assert load.source.category=="synthetic" and "人工" in load.source.name
    chosen.acknowledge_category_sum=False
    with pytest.raises(ValueError,match="显式确认"):
        import_energydetective(artificial_csv,chosen,hours=24)
    chosen.acknowledge_category_sum=True
    chosen.timestamp_assumption_acknowledged=False
    with pytest.raises(ValueError,match="区间锚点"):
        import_energydetective(artificial_csv,chosen,hours=24)


def test_repeated_meter_missing_meter_and_extra_column_rejected(artificial_csv):
    raw=pd.read_csv(artificial_csv)
    pd.concat([raw,raw.iloc[[0]]]).to_csv(artificial_csv,index=False)
    with pytest.raises(ImportQualityError) as exc:
        import_energydetective(artificial_csv,selection(),start="2017-01-01",hours=24)
    assert any(r.duplicate_records for r in exc.value.reports)
    raw.loc[~((raw.Type=="W") & (raw.Time==raw.Time.iloc[0]))].to_csv(artificial_csv,index=False)
    with pytest.raises(ImportQualityError):
        import_energydetective(artificial_csv,selection(),start="2017-01-01",hours=24)
    raw["MeterID"]="unknown relationship"
    raw.to_csv(artificial_csv,index=False)
    with pytest.raises(ValueError,match="额外列"):
        import_energydetective(artificial_csv,selection(),hours=24)


def test_reference_building_selection_never_sums_multiple_buildings(artificial_csv):
    raw=pd.read_csv(artificial_csv)
    raw["BuildingID"]=1
    other=raw.assign(BuildingID=2,Record=10000)
    pd.concat([raw,other]).to_csv(artificial_csv,index=False)
    chosen=selection();chosen.building="1"
    load=import_energydetective(artificial_csv,chosen,hours=24)
    assert load.frame.electric_load_kw.tolist()==[30]*24


def test_unlocatable_raw_timestamp_cannot_be_silently_excluded_from_window(artificial_csv):
    raw=pd.read_csv(artificial_csv)
    raw.loc[len(raw)]={"Time":"not a time","Type":"Q","Record":20}
    raw.to_csv(artificial_csv,index=False)
    with pytest.raises(ImportQualityError,match="无法定位"):
        import_energydetective(artificial_csv,selection(),hours=24)


def test_end_label_default_window_is_shifted_without_date_replacement(artificial_csv):
    chosen=selection();chosen.timestamp_position='end'
    load=import_energydetective(artificial_csv,chosen,hours=24)
    assert load.frame.timestamp.iloc[0].isoformat()=='2016-12-31T23:00:00+08:00'
    assert load.audit.normalized_energy_kwh==720


def test_local_format_file_does_not_claim_to_be_a_verified_remote_download(artificial_csv):
    chosen=selection();chosen.data_kind='published'
    load=import_energydetective(artificial_csv,chosen,hours=24)
    assert '远程对应版本未知' in load.source.version
    assert load.source.artifacts[0].retrieved_at is None
    assert '未核验' in load.source.artifacts[0].url


def test_window_does_not_silently_move_a_non_hour_start(artificial_csv):
    with pytest.raises(ValueError,match='整点'):
        import_energydetective(artificial_csv,selection(),start='2017-01-01T00:30:00',hours=24)


def test_missing_building_identifier_is_not_a_new_named_building(artificial_csv):
    raw=pd.read_csv(artificial_csv);raw['BuildingID']=1.0;raw.loc[0,'BuildingID']=np.nan
    raw.to_csv(artificial_csv,index=False)
    chosen=selection();chosen.building='nan'
    with pytest.raises(ValueError,match='BuildingID存在缺失'):
        import_energydetective(artificial_csv,chosen,hours=24)


def test_import_executes_optimization_exports_and_budget_change_recomputes(artificial_csv,tmp_path):
    load=import_energydetective(artificial_csv,selection(),hours=24)
    task=build_electric_task(load,ElectricCaseParameters(budget_yuan=1000000))
    assert validate_inputs(task).ready
    assert all(x==0 for x in task.data.heat_load_kw_th)
    assert all(c.hp_kw_th==c.boiler_kw_th==c.pv_kw==0 for c in task.candidates)
    assert task.data.electric_load_kw==[30]*24  # W is retained as electricity, never as heat.
    files=export_import(load,task,tmp_path/"import")
    restored=load_csv(files["normalized_csv"],json.loads(Path(files["series_metadata"]).read_text()))
    assert restored==task.data
    agent=EnergyAgent(tmp_path/"runs")
    first=agent.run(task)
    assert first.comparison.recommended_id=="GB"
    assert all(s.validation.valid for s in first.scenarios)
    grid=first.scenarios[0]
    assert grid.validation.metrics.grid_kwh==720
    assert grid.validation.metrics.operating_cost_yuan==pytest.approx(sum(task.data.electricity_price)*30)
    assert grid.investment_yuan==0
    assert "供热" in Path(first.files["markdown"]).read_text()
    second=agent.run(revise_task(task,TaskPatch(budget_yuan=0),first.run_id),previous=first)
    assert second.input_version==2 and second.comparison.recommended_id=="G"
    assert second.scenarios[1].dispatch.status=="rejected"
    assert second.run_id != first.run_id


def test_mixed_label_and_co2_scope_not_silently_relabelled(artificial_csv,tmp_path):
    load=import_energydetective(artificial_csv,selection(),hours=24)
    # Classification contract test only; this fixture is not external-file evidence.
    load.source.category="measured"
    task=build_electric_task(load,ElectricCaseParameters(budget_yuan=1000000,emission_species="CO2"))
    assert case_label(task)=="实测与假设混合案例"
    assert task.data.units["grid_emission_factor"]=="kgCO2/kWh"
    assert validate_inputs(task).ready
    result=EnergyAgent(tmp_path).run(task)
    assert set(pd.read_csv(result.files['csv']).emissions_unit)=={'kgCO2'}
    report=Path(result.files["markdown"]).read_text()
    assert "排放 kgCO2|" in report or "排放 kgCO2 |" in report
    assert "排放 kgCO2e" not in report
    assert "实测与假设混合案例" in report
    assert "不代表楼宇没有供热需求" in report or "不代表楼宇没有供热需求" in task.sources[1].conditions
    task.data.heat_load_kw_th[0]=1
    assert not validate_inputs(task).ready


def test_electric_mode_does_not_accept_heating_candidates_or_ambiguous_basis(artificial_csv):
    load=import_energydetective(artificial_csv,selection(),hours=24)
    task=build_electric_task(load,ElectricCaseParameters(budget_yuan=1000000))
    task.candidates[0].hp_kw_th=10
    assert any("热泵" in i.message for i in validate_inputs(task).issues)
    task.candidates[0].hp_kw_th=0
    task.emission_species="CO2"
    assert any("单位" in i.message for i in validate_inputs(task).issues)


def test_cache_replay_without_network_and_tamper_detection(tmp_path):
    requests=[]
    client=httpx.Client(transport=httpx.MockTransport(lambda r: requests.append(r) or httpx.Response(200,content=b'artificial fixture')))
    path,artifact=fetch_cached('https://example.invalid/sample.csv',tmp_path,offline=False,client=client)
    assert len(requests)==1
    offline=httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('offline replay requested network')))
    replay,same=fetch_cached('https://example.invalid/sample.csv',tmp_path,offline=True,client=offline)
    assert replay==path and same==artifact
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match="完整性"):
        fetch_cached('https://example.invalid/sample.csv',tmp_path,offline=True,client=offline)
    with pytest.raises(FileNotFoundError,match="不会用人工"):
        fetch_cached('https://example.invalid/missing.csv',tmp_path,offline=True,client=offline)


def test_nasa_unavailable_preserves_baseline_and_states_missing_comparison(artificial_csv,tmp_path):
    load=import_energydetective(artificial_csv,selection(),hours=24)
    task=build_electric_task(load,ElectricCaseParameters(budget_yuan=1000000,include_solar=True),cache_dir=tmp_path/"empty",offline=True)
    assert [c.candidate_id for c in task.candidates]==["G","GB"]
    assert any("光伏候选未完成" in p for p in task.case_context.pending)
    assert EnergyAgent(tmp_path/"runs").run(task).comparison.recommended_id


def test_tariff_scope_hourly_alignment_and_period_completeness(tmp_path):
    with pytest.raises(ValidationError,match="覆盖"):
        TariffSettings(periods=[PricePeriod(start_hour=0,end_hour=7,yuan_per_kwh=1)])
    times=pd.date_range("2017-01-01",periods=3,freq="h",tz="Asia/Shanghai")
    path=tmp_path/"prices.csv"
    pd.DataFrame({"timestamp":times.astype(str),"yuan_per_kwh":[0.5,1.0,2.0]}).to_csv(path,index=False)
    assert load_hourly_tariff(path,times)==[0.5,1.0,2.0]
    with pytest.raises(ValueError,match="未覆盖"):
        load_hourly_tariff(path,pd.date_range(times[0],periods=4,freq="h"))


def test_cli_conversion_is_reproducible_and_failed_quality_has_machine_report(artificial_csv,tmp_path,capsys):
    args=['data-import','--records',str(artificial_csv),'--building','test','--meters','Q,W','--acknowledge-category-sum',
        '--timestamp-position','start','--acknowledge-time-assumption','--hours','24','--artificial-fixture','--budget','1000000']
    assert main(args+['--output',str(tmp_path/'one'),'--run'])==0
    assert main(args+['--output',str(tmp_path/'two'),'--run'])==0
    one=json.loads((tmp_path/'one'/'energy_audit.json').read_text())
    two=json.loads((tmp_path/'two'/'energy_audit.json').read_text())
    assert one==two
    assert (tmp_path/'one'/'normalized.csv').read_bytes()==(tmp_path/'two'/'normalized.csv').read_bytes()
    raw=pd.read_csv(artificial_csv);raw.loc[0,'Record']=-1;raw.to_csv(artificial_csv,index=False)
    assert main(args+['--start','2017-01-01','--output',str(tmp_path/'bad')])==2
    assert (tmp_path/'bad'/'import_error.json').exists()
    assert list((tmp_path/'bad').glob('quality_failed_*.json'))
    assert '人工' in capsys.readouterr().out
