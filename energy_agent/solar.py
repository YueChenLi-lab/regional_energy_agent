"""NASA UTC cache adapter and documented pvlib resource-to-PV estimation.

This module has local artificial-fixture tests. A real NASA fetch is a separate
network acceptance step; a cache miss never becomes synthetic weather.
"""
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlencode

import json
import numpy as np
import pandas as pd
import pvlib
from pydantic import Field

from .adapters import fetch_cached, sha256_file
from .quality import shanghai_timestamps
from .schemas import Artifact, Fraction, Model, Source


class SolarSettings(Model):
    latitude: float = Field(default=31.23, ge=-90, le=90)
    longitude: float = Field(default=121.47, ge=-180, le=180)
    coordinate_scope: str = "上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差"
    tilt_degrees: float = Field(default=20, ge=0, le=90)
    azimuth_degrees: float = Field(default=180, ge=0, le=360, description="正北0，正东90，正南180")
    system_loss_fraction: Fraction = 0.14
    gamma_pdc: float = Field(default=-0.004, ge=-0.02, le=0)
    inverter_efficiency: float = Field(default=0.96, gt=0, le=1)


def nasa_hourly_url(timestamps, settings: SolarSettings) -> str:
    times = shanghai_timestamps(timestamps, "Asia/Shanghai").tz_convert("UTC")
    params = {"parameters": "ALLSKY_SFC_SW_DWN,T2M,WS10M", "community": "RE",
        "longitude": settings.longitude, "latitude": settings.latitude,
        "start": times.min().strftime("%Y%m%d"), "end": times.max().strftime("%Y%m%d"),
        "format": "JSON", "time-standard": "UTC"}
    return "https://power.larc.nasa.gov/api/temporal/hourly/point?" + urlencode(params)


def parse_nasa_hourly(path: str | Path, timestamps, settings: SolarSettings) -> pd.DataFrame:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    header = payload.get("header", {})
    if header.get("time_standard", "").upper() != "UTC":
        raise ValueError("NASA响应必须明确time_standard=UTC；不把LST当地太阳时当北京时间")
    coordinates = payload.get("geometry", {}).get("coordinates", [])
    if len(coordinates) < 2 or not np.allclose(coordinates[:2], [settings.longitude, settings.latitude], atol=0.001, rtol=0):
        raise ValueError("NASA响应坐标与请求代表点不一致")
    parameters = payload.get("properties", {}).get("parameter", {})
    definitions = payload.get("parameters", {})
    required = {"ALLSKY_SFC_SW_DWN": {"Wh/m^2", "W/m^2"}, "T2M": {"C"}, "WS10M": {"m/s"}}
    data = {}
    fill = header.get("fill_value", -999)
    for name, units in required.items():
        if name not in parameters or definitions.get(name, {}).get("units") not in units:
            raise ValueError(f"NASA缺少{name}或单位未支持；支持单位为{sorted(units)}，不猜测换算")
        series = pd.Series(parameters[name], dtype=float)
        index = pd.to_datetime(series.index, format="%Y%m%d%H", utc=True, errors="raise").tz_convert("Asia/Shanghai")
        if index.duplicated().any():
            raise ValueError("NASA响应有重复小时")
        data[name] = pd.Series(series.to_numpy(), index=index)
    frame = pd.DataFrame(data)
    requested = shanghai_timestamps(timestamps, "Asia/Shanghai")
    frame = frame.reindex(requested)
    if frame.isna().any().any() or not np.isfinite(frame.to_numpy()).all() or (frame == fill).any().any():
        raise ValueError("NASA所需小时存在缺失、fill_value或非法数值；禁止补零或换成年份")
    frame.columns = ["ghi", "temp_air", "wind_speed"]
    # Hourly Wh/m² divided by exactly one hour equals hourly mean W/m².
    if not frame.ghi.between(0, 1500).all() or not frame.temp_air.between(-90, 65).all() or not frame.wind_speed.between(0, 100).all():
        raise ValueError("NASA气象超出受支持边界，需核查而非裁剪")
    return frame


def estimate_pv(weather: pd.DataFrame, settings: SolarSettings) -> pd.Series:
    if set(weather.columns) != {"ghi", "temp_air", "wind_speed"} or weather.index.tz is None:
        raise ValueError("光伏估算需要对齐且带时区的ghi、temp_air、wind_speed")
    if weather.isna().any().any() or not np.isfinite(weather.to_numpy()).all() or (weather.ghi < 0).any() or (weather.wind_speed < 0).any():
        raise ValueError("光伏气象输入存在缺失或非法边界")
    # Mid-interval solar position approximates hourly average geometry.
    times = weather.index + pd.Timedelta(minutes=30)
    position = pvlib.solarposition.get_solarposition(times, settings.latitude, settings.longitude)
    ghi = pd.Series(weather.ghi.to_numpy(), index=times)
    decomposition = pvlib.irradiance.erbs(ghi, position.zenith, times)
    poa = pvlib.irradiance.get_total_irradiance(settings.tilt_degrees, settings.azimuth_degrees,
        position.apparent_zenith, position.azimuth, decomposition.dni, ghi, decomposition.dhi,
        model="isotropic", albedo=0.2).poa_global
    poa = poa.where(position.apparent_zenith < 90, 0).clip(lower=0)
    cell_temperature = pvlib.temperature.faiman(poa, weather.temp_air.to_numpy(), weather.wind_speed.to_numpy(), u0=25, u1=6.84)
    dc = pvlib.pvsystem.pvwatts_dc(poa, cell_temperature, pdc0=1.0, gamma_pdc=settings.gamma_pdc)
    ac = pvlib.inverter.pvwatts(dc * (1-settings.system_loss_fraction), pdc0=1.0, eta_inv_nom=settings.inverter_efficiency)
    result = pd.Series(np.asarray(ac), index=weather.index, name="pv_per_kw")
    if not np.isfinite(result).all() or not result.between(0, 1).all():
        raise ValueError("光伏模型返回非法出力；不采用未经解释的结果裁剪")
    return result


def load_nasa_pv(timestamps, settings: SolarSettings, *, cache_dir="data_cache/raw", offline=True):
    url = nasa_hourly_url(timestamps, settings)
    path, artifact = fetch_cached(url, cache_dir, offline=offline)
    weather = parse_nasa_hourly(path, timestamps, settings)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    pv = estimate_pv(weather, settings)
    period = f"{weather.index[0].isoformat()}至{(weather.index[-1]+pd.Timedelta(hours=1)).isoformat()}"
    resource = Source(source_id="nasa-resource", name="NASA POWER网格太阳资源与气象（非楼宇实测）", category="estimated",
        region=settings.coordinate_scope, time_range=period, units={"ghi": "W/m²（一小时平均）", "temp_air": "℃", "wind_speed": "m/s"},
        url=url, version="NASA POWER Hourly API " + metadata.get("header",{}).get("api",{}).get("version","未知"), artifacts=[artifact],
        processing=["显式请求time-standard=UTC，解析后转Asia/Shanghai；官方FAQ Other Time Range说明小时标签为区间起点；严格匹配原历史小时，不填补、不换年", "ALLSKY_SFC_SW_DWN若为Wh/m²，除以1h得到W/m²"],
        conditions="官方POWER免费网格资源，非楼宇或屋顶实测。已读取https://power.larc.nasa.gov/docs/referencing/：成果须包含POWER Reference和Data Reference（服务名、版本和获取日期）；NASA项目请求再分发通知，当前未发送任何通知。致谢NASA Langley Research Center POWER Project，NASA Earth Science Division资助。")
    resource.processing.append(f"API按UTC整日返回{len(metadata['properties']['parameter']['ALLSKY_SFC_SW_DWN'])}小时；严格选取与负荷对齐的{len(weather)}小时，保留完整原响应缓存")
    parameters = Source(source_id="pv-assumptions", name="光伏安装与模型参数假设", category="assumption", region=settings.coordinate_scope,
        units={"tilt_degrees": "度", "azimuth_degrees": "度（北0南180）", "system_loss_fraction": "1", "gamma_pdc": "1/℃"},
        processing=[settings.model_dump_json(), "固定albedo=0.2、Faiman u0=25 W/(m²·K)、u1=6.84 W·s/(m³·K)；未校准遮挡、积雪与屋顶条件"],
        conditions="安装角度和损耗为可修改情景假设，非现场勘查")
    estimated = Source(source_id="estimated-pv", name="pvlib光伏归一化AC出力估算，按1kW_DC额定容量", category="estimated", region=settings.coordinate_scope,
        time_range=period, units={"pv_per_kw": "kW/kW"}, url="https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.pvwatts_dc.html",
        version=f"pvlib {version('pvlib')}", parent_source_ids=["nasa-resource", "pv-assumptions"],
        processing=["区间中点太阳位置；Erbs分解GHI为DNI/DHI，isotropic转倾斜面POA；Faiman电池温度；PVWatts DC与逆变器AC效率；固定系统损耗", "夜间太阳高度角<=0时估算出力为0；未把辐照量直接当出力；无售电"],
        conditions="气象驱动的模型估算，不能称为楼宇实测光伏；粗略代表点与小时中点近似带来误差")
    return pv.tolist(), [resource, parameters, estimated], path
