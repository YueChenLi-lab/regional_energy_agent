"""Artificial NASA-shaped responses, not evidence of a successful real NASA fetch."""
import json

import httpx
import numpy as np
import pandas as pd
import pytest

from energy_agent.adapters import fetch_cached
from energy_agent.solar import SolarSettings, estimate_pv, load_nasa_pv, nasa_hourly_url, parse_nasa_hourly


def artificial_nasa(times, settings):
    ghi=[max(0,np.sin((t.hour-6)*np.pi/12))*800 for t in times]
    keys=times.tz_convert('UTC').strftime('%Y%m%d%H')
    return {"header":{"time_standard":"UTC","fill_value":-999,"api":{"version":"ARTIFICIAL-TEST"}},
        "geometry":{"coordinates":[settings.longitude,settings.latitude,0]},
        "parameters":{"ALLSKY_SFC_SW_DWN":{"units":"Wh/m^2"},"T2M":{"units":"C"},"WS10M":{"units":"m/s"}},
        "properties":{"parameter":{"ALLSKY_SFC_SW_DWN":dict(zip(keys,ghi)),"T2M":dict.fromkeys(keys,20),"WS10M":dict.fromkeys(keys,2)}}}


@pytest.fixture
def sample(tmp_path):
    times=pd.date_range('2017-01-01',periods=48,freq='h',tz='Asia/Shanghai')
    settings=SolarSettings()
    payload=artificial_nasa(times,settings)
    path=tmp_path/'ARTIFICIAL_NASA_FORMAT.json'
    path.write_text(json.dumps(payload))
    return path,times,settings,payload


def test_nasa_utc_request_and_alignment_keep_actual_historical_hours(sample):
    path,times,settings,payload=sample
    url=nasa_hourly_url(times,settings)
    assert 'time-standard=UTC' in url and 'start=20161231' in url
    weather=parse_nasa_hourly(path,times,settings)
    assert weather.index.equals(times)
    assert weather.index[0].year==2017
    assert weather.ghi.iloc[12]==800  # Wh/m² per 1h converted to W/m².
    estimated=estimate_pv(weather,settings)
    assert estimated.between(0,1).all()
    assert (estimated.loc[(times.hour<6)|(times.hour>=18)]==0).all()
    assert estimated.max()>0
    assert not np.allclose(estimated,weather.ghi/1000)  # temperature/geometry/loss model actually used.
    altered=estimate_pv(weather,SolarSettings(system_loss_fraction=0.4))
    assert altered.sum()<estimated.sum()


@pytest.mark.parametrize('case',['lst','missing','fill','units','coordinates','wind'])
def test_bad_resource_never_silently_becomes_pv_or_zero(sample,case):
    path,times,settings,payload=sample
    key=next(iter(payload['properties']['parameter']['ALLSKY_SFC_SW_DWN']))
    if case=='lst':payload['header']['time_standard']='LST'
    elif case=='missing':del payload['properties']['parameter']['ALLSKY_SFC_SW_DWN'][key]
    elif case=='fill':payload['properties']['parameter']['ALLSKY_SFC_SW_DWN'][key]=-999
    elif case=='units':payload['parameters']['ALLSKY_SFC_SW_DWN']['units']='kWh/m^2'
    elif case=='coordinates':payload['geometry']['coordinates'][0]=100
    else:payload['properties']['parameter']['WS10M'][key]=-1
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):parse_nasa_hourly(path,times,settings)


def test_nasa_cached_replay_uses_no_network_and_records_estimated_parent_sources(sample,tmp_path,monkeypatch):
    path,times,settings,payload=sample
    url=nasa_hourly_url(times,settings)
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))
    cached,_=fetch_cached(url,tmp_path/'cache',offline=False,client=client)
    def forbidden(*args,**kwargs):pytest.fail('offline replay cannot create an HTTP client')
    monkeypatch.setattr(httpx,'Client',forbidden)
    pv,sources,read=load_nasa_pv(times,settings,cache_dir=tmp_path/'cache',offline=True)
    assert read==cached and len(pv)==48
    estimated=next(s for s in sources if s.source_id=='estimated-pv')
    assert estimated.category=='estimated'
    assert estimated.parent_source_ids==['nasa-resource','pv-assumptions']
    assert all(s.category!='measured' for s in sources)


def test_cached_resource_enables_distinct_electric_candidates_and_real_solver(sample,tmp_path):
    from energy_agent.adapters import MeterSelection,import_energydetective
    from energy_agent.real_case import ElectricCaseParameters,build_electric_task
    from energy_agent.agent import EnergyAgent
    path,times,settings,payload=sample
    url=nasa_hourly_url(times,settings)
    client=httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload)))
    fetch_cached(url,tmp_path/'cache',offline=False,client=client)
    records=tmp_path/'ARTIFICIAL_records.csv'
    pd.DataFrame({'Time':times.tz_localize(None).astype(str),'Type':'W','Record':30.0}).to_csv(records,index=False)
    load=import_energydetective(records,MeterSelection(building='test',meters=['W'],timestamp_position='start',
        timestamp_assumption_acknowledged=True,data_kind='artificial_fixture'),hours=48)
    task=build_electric_task(load,ElectricCaseParameters(budget_yuan=1000000,include_solar=True),cache_dir=tmp_path/'cache',offline=True)
    assert [c.candidate_id for c in task.candidates]==['G','GB','GP','GPB']
    assert len({(c.pv_kw,c.battery_power_kw,c.battery_energy_kwh) for c in task.candidates})==4
    result=EnergyAgent(tmp_path/'runs').run(task)
    assert all(s.validation.valid for s in result.scenarios)
    assert task.data.heat_load_kw_th==[0]*48
