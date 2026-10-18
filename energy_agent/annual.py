"""Complete historical calendar years and explicitly parameterized research heat."""
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import Field

from .adapters import MeterSelection, fetch_zenodo_energydetective, import_energydetective
from .real_case import ElectricCaseParameters, build_electric_task, export_import
from .schemas import (CAPACITY_FIELDS, AssetEconomics, Candidate, CapacityBounds, CapacityRange,
                      Economics, Model, Source)
from .solar import parse_nasa_hourly, nasa_hourly_url
from .adapters import fetch_cached


def validate_calendar_year(data) -> int:
    if data is None: raise ValueError("全年评估缺少时序")
    index = pd.DatetimeIndex(data.timestamps)
    if index.tz is None: raise ValueError("全年时间必须含时区")
    index = index.tz_convert("Asia/Shanghai")
    year = int(index[0].year)
    if data.step_hours <= 0: raise ValueError("时间步长必须为正")
    expected = pd.date_range(f"{year}-01-01", f"{year+1}-01-01",freq=pd.Timedelta(hours=data.step_hours),inclusive="left",tz="Asia/Shanghai")
    if len(expected)*data.step_hours != (pd.Timestamp(f'{year+1}-01-01')-pd.Timestamp(f'{year}-01-01')).total_seconds()/3600:
        raise ValueError("全年步长不能完整划分该日历年")
    if not index.equals(expected):
        raise ValueError(f"完整日历年需要{len(expected)}个原始连续区间，起于{year}-01-01 00:00北京时间；不重复周、不改年、不补缺失")
    return year


class HeatSimulation(Model):
    floor_area_m2: float = Field(default=20000, gt=0)
    envelope_area_m2: float = Field(default=30000, gt=0)
    envelope_u_w_m2_k: float = Field(default=0.7, gt=0)
    air_volume_m3: float = Field(default=60000, gt=0)
    air_changes_per_hour: float = Field(default=0.5, ge=0)
    air_heat_capacity_wh_m3_k: float = Field(default=0.33, gt=0)
    indoor_setpoint_c: float = Field(default=20, ge=5, le=30)
    heating_months: list[int] = Field(default_factory=lambda:[1,2,3,11,12])
    start_hour: int = Field(default=7, ge=0, le=23)
    end_hour: int = Field(default=20, ge=1, le=24)

    def calculate(self, timestamps, temperature):
        if self.end_hour <= self.start_hour or not set(self.heating_months) <= set(range(1,13)):
            raise ValueError("供热日程非法")
        times = pd.DatetimeIndex(timestamps).tz_convert("Asia/Shanghai")
        temp = np.asarray(temperature,dtype=float)
        if len(temp)!=len(times) or not np.isfinite(temp).all(): raise ValueError("仿真供热必须与实际气温严格对齐")
        ua_kw_k=(self.envelope_area_m2*self.envelope_u_w_m2_k+self.air_volume_m3*self.air_changes_per_hour*self.air_heat_capacity_wh_m3_k)/1000
        schedule = np.isin(times.month,self.heating_months)&(times.hour>=self.start_hour)&(times.hour<self.end_hour)&(times.dayofweek<5)
        return (ua_kw_k*np.maximum(self.indoor_setpoint_c-temp,0)*schedule).tolist()


def default_economics(source_id="annual-assumptions"):
    lifetimes = (25,15,10,15,20)
    return Economics(source_id=source_id,assets={k:AssetEconomics(lifetime_years=life,fixed_om_fraction=0.015,replacement_fraction=1) for k,life in zip(CAPACITY_FIELDS,lifetimes)},
        battery_variable_om_per_kwh=0.01,hp_variable_om_per_kwh_th=0.005,boiler_variable_om_per_kwh_th=0.003)


def build_annual_case(*, year=2017, heat=False, cache_dir="data_cache/raw", offline=True,
                      retain_flagged_jumps=False, budget=10000000, heat_parameters=None, output=None, bundle_dir=None):
    """Known published test-building file only. No fabricated acquisition fallback."""
    if bundle_dir:
        import json
        from .schemas import Artifact
        from .adapters import sha256_file
        bundle=Path(bundle_dir).resolve()
        manifest=json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('format')!='regional-energy-annual-input-v1': raise ValueError('不支持的全年数据包')
        for name,digest in manifest['files'].items():
            item=(bundle/name).resolve()
            if not item.is_relative_to(bundle) or sha256_file(item)!=digest:raise ValueError('全年数据包校验失败：'+name)
        meta=json.loads((bundle/'source_manifest.json').read_text(encoding='utf-8'))
        path=bundle/'records.csv';artifact=Artifact.model_validate(meta['records']);documentation=Artifact.model_validate(meta['documentation'])
        cache_dir=bundle
    else:
        path, artifact, documentation = fetch_zenodo_energydetective(cache_dir=cache_dir,offline=offline)
    hours = int((pd.Timestamp(f'{year+1}-01-01')-pd.Timestamp(f'{year}-01-01')).total_seconds()/3600)
    selection=MeterSelection(building="test",meters=["Q"],timestamp_position="start",timestamp_assumption_acknowledged=True)
    load=import_energydetective(path,selection,start=f'{year}-01-01',hours=hours,artifact=artifact,documentation=documentation,
                              retain_flagged_jumps=retain_flagged_jumps)
    task=build_electric_task(load,ElectricCaseParameters(budget_yuan=budget,pv_limit_kw=2500,include_solar=True),cache_dir=cache_dir,offline=offline)
    if not any(s.source_id=="estimated-pv" for s in task.sources):
        raise ValueError("全年容量研究需要同期NASA资源，未获得时可用原data-import执行电网基线；不以合成天气替代")
    task.case_context.excluded=[item.replace('全生命周期、','设备隐含排放与生命周期碳、') for item in task.case_context.excluded]
    task.resolution="full_year"
    task.planning_mode="capacity"
    source=Source(source_id="annual-assumptions",name="全年研究情景：容量及经济参数假设",category="assumption",region="上海匿名楼宇研究情景",
        time_range=f"{year}代表年，未来20年重复，不是预测",units={"capacities":"kW/kWh/kW_th","cost":"元","gas_price":"元/kWh_LHV","gas_emission_factor":"kgCO2e/kWh_LHV"},
        processing=["使用完整原始Q照明插座电量；排除W暖通，不缩放、不改日期", "容量上界：PV2500kW，电池1000kW/4000kWh；场地未实勘，无强制最低装机", default_economics().model_dump_json()],
        conditions="设备寿命、维护、更换、残值与价格/排放均为研究假设，可修改；无工程报价，不含税费、土地、融资、设备隐含排放")
    task.sources.append(source)
    task.economics=default_economics()
    peakheat=0
    if heat:
        weather_path,_=fetch_cached(nasa_hourly_url(task.data.timestamps,ElectricCaseParameters().solar),cache_dir=cache_dir,offline=offline)
        weather=parse_nasa_hourly(weather_path,task.data.timestamps,ElectricCaseParameters().solar)
        hp=heat_parameters or HeatSimulation()
        task.data.heat_load_kw_th=hp.calculate(task.data.timestamps,weather.temp_air)
        task.data.source_ids['heat_load_kw_th']='simulated-heating'
        task.data.gas_price=[0.32]*hours
        task.data.gas_emission_factor=[0.202]*hours
        task.data.source_ids['gas_price']=task.data.source_ids['gas_emission_factor']='annual-assumptions'
        task.sources.append(Source(source_id="simulated-heating",name="Q局部实测电量＋稳态物理仿真供热研究情景",category="simulated",region="上海代表点，非匿名建筑精确定位",
            time_range=load.source.time_range,units={"heat_load_kw_th":"kW_th"},parent_source_ids=["nasa-power","annual-assumptions"],
            processing=[hp.model_dump_json(),"H=(A_envelope*U + volume*ACH*0.33)/1000 * max(Tset-Tout,0)；仅指定供热月份、工作日及时段。未计太阳得热、内热源、蓄热和动态预热；面积参数为假设，未校准"],
            conditions="非实测热负荷、非全楼改造；排除W暖通用电，避免同一供热重复计量；未覆盖供冷、热水、原暖通服务及非选中计量类别"))
        # NASA adapter's source id is checked rather than guessing an external data column.
        nasa_id=next(s.source_id for s in task.sources if s.source_id not in {'estimated-pv'} and 'NASA' in s.name)
        task.sources[-1].parent_source_ids=[nasa_id,'annual-assumptions']
        task.assessment_mode="electric_heat"
        task.devices.hp_cop=3.2
        task.devices.boiler_efficiency=0.9
        task.devices.hp_cost_per_kw_th=1100
        task.devices.boiler_cost_per_kw_th=240
        task.devices.source_id='annual-assumptions'
        peakheat=float(max(task.data.heat_load_kw_th))
        task.case_context.boundary=load.boundary+"；另加参数化仿真供热，不含W，不是实测全楼改造"
        task.case_context.excluded=["W及其他未选中用电", "供冷、热水、原暖通服务与完整全楼边界", "设备隐含排放与生命周期碳核算"]
        source.processing += [hp.model_dump_json(),"新增热泵1100元/kW_th，锅炉240元/kW_th，燃气0.32元/kWh_LHV、0.202kgCO2e/kWh_LHV均为假设；安装费沿用15%"]
    thermal_upper=max(0.0,peakheat*1.2)
    peak=float(max(task.data.electric_load_kw))
    pv_upper=float(np.ceil(0.5*peak/100)*100)
    battery_upper=float(np.ceil(0.2*peak/100)*100)
    ranges=[pv_upper,battery_upper,4*battery_upper,thermal_upper,thermal_upper]
    source.processing.append(f"容量上界量级依据：原Q峰值{peak:g}kW，PV=ceil(0.5*峰值/100)*100={pv_upper:g}，电池功率=ceil(0.2*峰值/100)*100={battery_upper:g}，能量上界=4h*功率；热容量上界=1.2*仿真峰值={thermal_upper:g}；候选PV=ceil(0.2*峰值/100)*100；均为可修改研究范围，非实测场地")
    task.capacity_bounds=CapacityBounds(source_id='annual-assumptions',**{k:CapacityRange(upper=u) for k,u in zip(CAPACITY_FIELDS,ranges)})
    base=dict(source_id='annual-assumptions',battery_power_kw=0,battery_energy_kwh=0,hp_kw_th=0,boiler_kw_th=peakheat)
    task.candidates=[Candidate(candidate_id='BASE',name='电网＋新建锅炉研究基线' if heat else '既有电网基线',pv_kw=0,**base),
                     Candidate(candidate_id='PV',name='按Q峰值20%取整光伏对照',pv_kw=float(np.ceil(0.2*peak/100)*100),**base)]
    task.project_name=f'上海{year}全年Q'+('＋仿真供热研究' if heat else '电侧研究')
    task.case_context.quality_summary=f"全年{hours}小时，Q跳变告警{load.whole_reports[0].jump_count}个；显式保留全部原值，未核实测点异常，结果受原值影响；不宣称已消除质量风险"
    task.case_context.investment_scope='既有电网与Q用电设备不计改造投资；新增PV/储能'+('及满足仿真供热的全部新建热设备' if heat else '')+'，安装15%；各模式边界相同'
    task.case_context.pending += ['全年Q跳变保留且未获发布方核实；峰值可能影响容量决策','热需求为仿真研究条件' if heat else '电侧不建模供热，不能保证供热']
    validate_calendar_year(task.data)
    if output:
        export_import(load,task,output)
    return task
