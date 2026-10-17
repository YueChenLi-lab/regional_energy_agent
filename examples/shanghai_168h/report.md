# 区域综合能源低碳规划评估报告

项目：EnergyDetective上海匿名办公楼test电侧评估

运行 ID：`2c9014edf78d4f058d4dcafb6c570c14`；输入版本：1；状态：完成。

**实测与假设混合案例**。实测、估算与人为假设逐字段记录；不代表真实工程投资决策，未知信息不能视为实测依据。

## 任务条件

168 个区间，时间步长 1 h，评估时长 168 h。区间开始时间：2017-01-01T00:00:00+08:00 至 2017-01-07T23:00:00+08:00；最后区间结束时间为最后开始时间加一个时间步。仅报告该时段结果。

| 条件 | 数值 | 单位 |
| --- | --- | --- |
| 初始投资预算 | 3,000,000.0000 | 元 |
| 评估期排放上限 | 不限制 | kgCO2e |
| 电网购电功率上限 | 1,170.0000 | kW |
| 光伏场地上限 | 540.0000 | kW |

项目条件来源：`electric-scenario`。

求解设置：每个候选时限 30 秒；相对最优性间隙容差 1e-06。

## 候选配置与结果

| 方案 | 光伏 kW | 电池 kW / kWh | 热泵 kW_th | 锅炉 kW_th | 投资 元 | 运行费 元 | 排放 kgCO2e | 求解状态 | 约束通过 | 容量来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPB 电网＋新增光伏储能 | 540.0000 | 270 / 540 | 0.0000 | 0.0000 | 2,685,825.0000 | 62,394.7814 | 47,487.5864 | 已证明最优（该候选运行） | 是 | electric-scenario |
| GP 电网＋新增光伏 | 540.0000 | 0 / 0 | 0.0000 | 0.0000 | 1,987,200.0000 | 64,411.5961 | 47,316.8895 | 已证明最优（该候选运行） | 是 | electric-scenario |
| GB 电网＋新增储能 | 0.0000 | 270 / 540 | 0.0000 | 0.0000 | 698,625.0000 | 65,315.8083 | 49,718.9263 | 已证明最优（该候选运行） | 是 | electric-scenario |
| G 既有电网基线 | 0.0000 | 0 / 0 | 0.0000 | 0.0000 | 0.0000 | 67,332.6230 | 49,548.2295 | 已证明最优（该候选运行） | 是 | electric-scenario |

| 方案 | 购电 kWh | 燃气 kWh_LHV | 弃光 kWh | 常规用电 kWh | 供热 kWh_th | 供能满足 | 求解秒数 | 相对最优性间隙 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPB | 86,341.0661 | 0.0000 | 0.0000 | 90,087.6900 | 0.0000 | 是 | 0.0308 | 0.0000 |
| GP | 86,030.7082 | 0.0000 | 0.0000 | 90,087.6900 | 0.0000 | 是 | 0.0063 | 0.0000 |
| GB | 90,398.0479 | 0.0000 | 0.0000 | 90,087.6900 | 0.0000 | 是 | 0.0317 | 0.0000 |
| G | 90,087.6900 | 0.0000 | 0.0000 | 90,087.6900 | 0.0000 | 是 | 0.0094 | 0.0000 |

## 比较与推荐

在本次评估的候选方案中，推荐 **GPB**。在本次评估的候选方案中，GPB 通过全部约束校验，按评估期运行费升序排名第一。初始投资与评估期排放单独展示；此结果不代表全部可能容量配置的全局最优。

先筛选预算、供能与排放等约束，再按本评估期运行费排序；投资与排放完整列出以展示取舍。若某候选仅取得可行解，则排序基于当前可行解，不能据此证明该候选运行最优。

## 不可行、未完成求解与独立检查

### GPB：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 1.137e-13 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 0.0000 | 1e-05 |  |
| boiler_efficiency | 是 | 0.0000 | 1e-05 |  |
| pv_allocation | 是 | 0.0000 | 1e-05 |  |
| nonnegative_flows | 是 | 0.0000 | 1e-05 |  |
| grid_limit | 是 | 0.0000 | 1e-05 |  |
| pv_availability | 是 | 0.0000 | 1e-05 |  |
| heat_pump_capacity | 是 | 0.0000 | 1e-05 |  |
| boiler_capacity | 是 | 0.0000 | 1e-05 |  |
| battery_charge_power | 是 | 0.0000 | 1e-05 |  |
| battery_discharge_power | 是 | 0.0000 | 1e-05 |  |
| soc_lower | 是 | 0.0000 | 1e-05 |  |
| soc_upper | 是 | 0.0000 | 1e-05 |  |
| soc_initial | 是 | 0.0000 | 1e-05 |  |
| soc_terminal | 是 | 0.0000 | 1e-05 | 期末必须恢复初始能量，不允许免费消耗初始储能 |
| soc_dynamics | 是 | 0.0000 | 1e-05 |  |
| binary_charge_mode | 是 | 0.0000 | 1e-05 |  |
| charge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| discharge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| no_simultaneous_charge_discharge | 是 | 0.0000 | 1e-05 |  |
| investment_budget | 是 | 0.0000 | 0.0001 |  |
| pv_site_limit | 是 | 0.0000 | 1e-05 |  |
| emission_limit | 是 | 0.0000 | 0.0001 | 未设置排放上限 |
| objective_recalculation | 是 | 7.276e-12 | 0.0001 |  |

### GP：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 1.137e-13 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 0.0000 | 1e-05 |  |
| boiler_efficiency | 是 | 0.0000 | 1e-05 |  |
| pv_allocation | 是 | 0.0000 | 1e-05 |  |
| nonnegative_flows | 是 | 0.0000 | 1e-05 |  |
| grid_limit | 是 | 0.0000 | 1e-05 |  |
| pv_availability | 是 | 0.0000 | 1e-05 |  |
| heat_pump_capacity | 是 | 0.0000 | 1e-05 |  |
| boiler_capacity | 是 | 0.0000 | 1e-05 |  |
| battery_charge_power | 是 | 0.0000 | 1e-05 |  |
| battery_discharge_power | 是 | 0.0000 | 1e-05 |  |
| soc_lower | 是 | 0.0000 | 1e-05 |  |
| soc_upper | 是 | 0.0000 | 1e-05 |  |
| soc_initial | 是 | 0.0000 | 1e-05 |  |
| soc_terminal | 是 | 0.0000 | 1e-05 | 期末必须恢复初始能量，不允许免费消耗初始储能 |
| soc_dynamics | 是 | 0.0000 | 1e-05 |  |
| binary_charge_mode | 是 | 0.0000 | 1e-05 |  |
| charge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| discharge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| no_simultaneous_charge_discharge | 是 | 0.0000 | 1e-05 |  |
| investment_budget | 是 | 0.0000 | 0.0001 |  |
| pv_site_limit | 是 | 0.0000 | 1e-05 |  |
| emission_limit | 是 | 0.0000 | 0.0001 | 未设置排放上限 |
| objective_recalculation | 是 | 7.276e-12 | 0.0001 |  |

### GB：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 5.684e-14 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 0.0000 | 1e-05 |  |
| boiler_efficiency | 是 | 0.0000 | 1e-05 |  |
| pv_allocation | 是 | 0.0000 | 1e-05 |  |
| nonnegative_flows | 是 | 0.0000 | 1e-05 |  |
| grid_limit | 是 | 0.0000 | 1e-05 |  |
| pv_availability | 是 | 0.0000 | 1e-05 |  |
| heat_pump_capacity | 是 | 0.0000 | 1e-05 |  |
| boiler_capacity | 是 | 0.0000 | 1e-05 |  |
| battery_charge_power | 是 | 0.0000 | 1e-05 |  |
| battery_discharge_power | 是 | 0.0000 | 1e-05 |  |
| soc_lower | 是 | 0.0000 | 1e-05 |  |
| soc_upper | 是 | 0.0000 | 1e-05 |  |
| soc_initial | 是 | 0.0000 | 1e-05 |  |
| soc_terminal | 是 | 0.0000 | 1e-05 | 期末必须恢复初始能量，不允许免费消耗初始储能 |
| soc_dynamics | 是 | 0.0000 | 1e-05 |  |
| binary_charge_mode | 是 | 0.0000 | 1e-05 |  |
| charge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| discharge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| no_simultaneous_charge_discharge | 是 | 0.0000 | 1e-05 |  |
| investment_budget | 是 | 0.0000 | 0.0001 |  |
| pv_site_limit | 是 | 0.0000 | 1e-05 |  |
| emission_limit | 是 | 0.0000 | 0.0001 | 未设置排放上限 |
| objective_recalculation | 是 | 0.0000 | 0.0001 |  |

### G：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 0.0000 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 0.0000 | 1e-05 |  |
| boiler_efficiency | 是 | 0.0000 | 1e-05 |  |
| pv_allocation | 是 | 0.0000 | 1e-05 |  |
| nonnegative_flows | 是 | 0.0000 | 1e-05 |  |
| grid_limit | 是 | 0.0000 | 1e-05 |  |
| pv_availability | 是 | 0.0000 | 1e-05 |  |
| heat_pump_capacity | 是 | 0.0000 | 1e-05 |  |
| boiler_capacity | 是 | 0.0000 | 1e-05 |  |
| battery_charge_power | 是 | 0.0000 | 1e-05 |  |
| battery_discharge_power | 是 | 0.0000 | 1e-05 |  |
| soc_lower | 是 | 0.0000 | 1e-05 |  |
| soc_upper | 是 | 0.0000 | 1e-05 |  |
| soc_initial | 是 | 0.0000 | 1e-05 |  |
| soc_terminal | 是 | 0.0000 | 1e-05 | 期末必须恢复初始能量，不允许免费消耗初始储能 |
| soc_dynamics | 是 | 0.0000 | 1e-05 |  |
| binary_charge_mode | 是 | 0.0000 | 1e-05 |  |
| charge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| discharge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| no_simultaneous_charge_discharge | 是 | 0.0000 | 1e-05 |  |
| investment_budget | 是 | 0.0000 | 0.0001 |  |
| pv_site_limit | 是 | 0.0000 | 1e-05 |  |
| emission_limit | 是 | 0.0000 | 0.0001 | 未设置排放上限 |
| objective_recalculation | 是 | 0.0000 | 0.0001 |  |

## 设备与投资假设（电侧模式：热泵与锅炉停用，参数不参与计算）

| 参数 | 值 | 单位 |
| --- | --- | --- |
| 光伏设备单价 | 3,200.0000 | 元/kW |
| 电池能量单价 | 900.0000 | 元/kWh |
| 电池功率单价 | 450.0000 | 元/kW |
| 热泵设备单价 | 0.0000 | 元/kW_th |
| 锅炉设备单价 | 0.0000 | 元/kW_th |
| 安装费/设备费 | 0.1500 | 无量纲 |
| 电网接入费用 | 0.0000 | 元 |
| 固定热泵 COP | 1.0000 | kWh_th/kWh |
| 锅炉效率 | 1.0000 | kWh_th/kWh_LHV |
| 充电效率 / 放电效率 | 0.95 / 0.95 | 无量纲 |
| SOC 下限 / 上限 / 初值 | 0.1 / 0.9 / 0.5 | 额定能量比例 |

设备参数与费用来源：`electric-scenario`。

初始投资 = 设备购置费合计 × (1 + 安装费比例) + 电网接入费。电网接入费对所有候选采用相同口径。

## 数据与参数来源

| 项目 | 记录 |
| --- | --- |
| source_id | energydetective-load |
| 名称 | EnergyDetective实测用电/建筑test/Q + W |
| 地区 | 中国上海；匿名办公楼精确位置未知 |
| 时间范围 | 2017-01-01T00:00:00+08:00至2017-01-08T00:00:00+08:00（末端不含） |
| 类别 | measured |
| 单位 | {"raw.Record": "kWh/一小时间隔", "electric_load_kw": "kW"} |
| 处理记录 | 发布方只称Time为timestamp，未明确区间锚点/时区；本次显式假设原时间为Asia/Shanghai、区间start；转换后为区间起点，不改历史年份；原文件建筑筛选=test；类别=['Q', 'W']；对每类按原时间稳定排序；检查(time,type)重复，未去重；按发布方README把Record解释为每小时电量，除以1h得到区间平均kW；未缩放实测负荷，未插补、删点或填零；输入数值分辨率按0.01kWh声明用于核对，不代表已核实仪表精度；浮点长尾保留；{"raw_energy_kwh":90087.68999999999,"normalized_energy_kwh":90087.69,"difference_kwh":1.4551915228366852e-11,"tolerance_kwh":0.0002,"input_numeric_precision":0.01,"source_rounding_bound_kwh":1.68,"passed":true,"explanation":"转换前后使用同一输入且不舍入，只允许浮点求和误差；容差取声明输入能量分辨率的1/100与1e-8 kWh较大者。原始数值舍入不确定性上界另列，不等同于转换误差或仪表精度。"} |
| 使用条件 | 已读取Zenodo记录metadata.license.id=cc-by-4.0；引用Xiao、Xu、Sha、Chen、Gu（2022），DOI 10.5281/zenodo.6590976，CC BY 4.0。派生数据需署名、链接许可并说明转换；本案例仅计量边界分析，不代表全楼完整计量。 |
| 发布链接 | https://zenodo.org/records/6590976 |
| 版本 | Zenodo 6590976 / DOI 10.5281/zenodo.6590976 / dataset_v2.zip |
| 原始文件、SHA-256与获取时间 | [{"url": "https://zenodo.org/api/records/6590976/files/dataset_v2.zip/content", "filename": "test_building_records.csv", "sha256": "7a9f6158ca5d6102c72c24623bce7930fc57e16825a2803d8e55b66bd3bb78f9", "retrieved_at": "2026-10-17T08:56:43.164462Z", "member_path": "test_building/test_building_records.csv", "container_sha256": "ae43c6fb205fb9442ab7ac8da7156afdf91767e06ed4a3252a2fa94c662c2fde", "publisher_checksum": "md5:b54c73f1fb441db156b8e6cc7c7551b2", "license_id": "CC-BY-4.0"}, {"url": "https://zenodo.org/api/records/6590976/files/dataset_v2.zip/content", "filename": "README.md", "sha256": "2dc077de74c79637c661db62c732f3b3d24ff3decef3d1809c2b5e69a6a6b5c7", "retrieved_at": "2026-10-17T08:56:43.164462Z", "member_path": "README.md", "container_sha256": "ae43c6fb205fb9442ab7ac8da7156afdf91767e06ed4a3252a2fa94c662c2fde", "publisher_checksum": "md5:b54c73f1fb441db156b8e6cc7c7551b2", "license_id": "CC-BY-4.0"}] |
| 父来源 | 无 / 未知 |

| 项目 | 记录 |
| --- | --- |
| source_id | nasa-resource |
| 名称 | NASA POWER网格太阳资源与气象（非楼宇实测） |
| 地区 | 上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差 |
| 时间范围 | 2017-01-01T00:00:00+08:00至2017-01-08T00:00:00+08:00 |
| 类别 | estimated |
| 单位 | {"ghi": "W/m²（一小时平均）", "temp_air": "℃", "wind_speed": "m/s"} |
| 处理记录 | 显式请求time-standard=UTC，解析后转Asia/Shanghai；官方FAQ Other Time Range说明小时标签为区间起点；严格匹配原历史小时，不填补、不换年；ALLSKY_SFC_SW_DWN若为Wh/m²，除以1h得到W/m²；API按UTC整日返回192小时；严格选取与负荷对齐的168小时，保留完整原响应缓存 |
| 使用条件 | 官方POWER免费网格资源，非楼宇或屋顶实测。已读取https://power.larc.nasa.gov/docs/referencing/：成果须包含POWER Reference和Data Reference（服务名、版本和获取日期）；NASA项目请求再分发通知，当前未发送任何通知。致谢NASA Langley Research Center POWER Project，NASA Earth Science Division资助。 |
| 发布链接 | https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN%2CT2M%2CWS10M&community=RE&longitude=121.47&latitude=31.23&start=20161231&end=20170107&format=JSON&time-standard=UTC |
| 版本 | NASA POWER Hourly API v2.10.3 |
| 原始文件、SHA-256与获取时间 | [{"url": "https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN%2CT2M%2CWS10M&community=RE&longitude=121.47&latitude=31.23&start=20161231&end=20170107&format=JSON&time-standard=UTC", "filename": "point", "sha256": "9bde056e44b1dc75c8b25e8a9d5102f6d172be907ed4c4a2e8a43486e5cb6570", "retrieved_at": "2026-10-17T08:55:51.536164Z", "member_path": null, "container_sha256": null, "publisher_checksum": null, "license_id": "未知"}] |
| 父来源 | 无 / 未知 |

| 项目 | 记录 |
| --- | --- |
| source_id | pv-assumptions |
| 名称 | 光伏安装与模型参数假设 |
| 地区 | 上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差 |
| 时间范围 | 未知 |
| 类别 | assumption |
| 单位 | {"tilt_degrees": "度", "azimuth_degrees": "度（北0南180）", "system_loss_fraction": "1", "gamma_pdc": "1/℃"} |
| 处理记录 | {"latitude":31.23,"longitude":121.47,"coordinate_scope":"上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差","tilt_degrees":20.0,"azimuth_degrees":180.0,"system_loss_fraction":0.14,"gamma_pdc":-0.004,"inverter_efficiency":0.96}；固定albedo=0.2、Faiman u0=25 W/(m²·K)、u1=6.84 W·s/(m³·K)；未校准遮挡、积雪与屋顶条件 |
| 使用条件 | 安装角度和损耗为可修改情景假设，非现场勘查 |
| 发布链接 | 未知 |
| 版本 | 未知 |
| 原始文件、SHA-256与获取时间 | [] |
| 父来源 | 无 / 未知 |

| 项目 | 记录 |
| --- | --- |
| source_id | estimated-pv |
| 名称 | pvlib光伏归一化AC出力估算，按1kW_DC额定容量 |
| 地区 | 上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差 |
| 时间范围 | 2017-01-01T00:00:00+08:00至2017-01-08T00:00:00+08:00 |
| 类别 | estimated |
| 单位 | {"pv_per_kw": "kW/kW"} |
| 处理记录 | 区间中点太阳位置；Erbs分解GHI为DNI/DHI，isotropic转倾斜面POA；Faiman电池温度；PVWatts DC与逆变器AC效率；固定系统损耗；夜间太阳高度角<=0时估算出力为0；未把辐照量直接当出力；无售电 |
| 使用条件 | 气象驱动的模型估算，不能称为楼宇实测光伏；粗略代表点与小时中点近似带来误差 |
| 发布链接 | https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.pvsystem.pvwatts_dc.html |
| 版本 | pvlib 0.16.1 |
| 原始文件、SHA-256与获取时间 | [] |
| 父来源 | nasa-resource、pv-assumptions |

| 项目 | 记录 |
| --- | --- |
| source_id | heating-disabled |
| 名称 | 电侧模式明确停用供热/燃气 |
| 地区 | 未知 |
| 时间范围 | 未知 |
| 类别 | assumption |
| 单位 | {"heat_load_kw_th": "kW_th", "gas_price": "元/kWh_LHV", "gas_emission_factor": "kgCO2e/kWh_LHV"} |
| 处理记录 | 热负荷、燃气价格和因子为零占位；候选热泵与锅炉容量均为零，不把W暖通电量转为热需求 |
| 使用条件 | 不建模供热，不代表楼宇没有供热需求，也不代表供热已得到保障；W若选中仍保留为电负荷 |
| 发布链接 | 未知 |
| 版本 | 未知 |
| 原始文件、SHA-256与获取时间 | [] |
| 父来源 | 无 / 未知 |

| 项目 | 记录 |
| --- | --- |
| source_id | scenario-tariff |
| 名称 | 人工情景时段电价（非上海官方历史价格） |
| 地区 | 上海（人工情景，非官方现行电价） |
| 时间范围 | 情景假设，不宣称适用于2017或当前年份 |
| 类别 | assumption |
| 单位 | {"electricity_price": "元/kWh"} |
| 处理记录 | {"region":"上海（人工情景，非官方现行电价）","applicable_year":"情景假设，不宣称适用于2017或当前年份","customer_class":"办公建筑情景，未核实电压等级与用户分类","cost_scope":"仅按购电量计费；未计基本电费、需量费、容量费、功率因数调整及税费差异","periods":[{"start_hour":0,"end_hour":7,"yuan_per_kwh":0.38},{"start_hour":7,"end_hour":17,"yuan_per_kwh":0.72},{"start_hour":17,"end_hour":22,"yuan_per_kwh":1.15},{"start_hour":22,"end_hour":24,"yuan_per_kwh":0.72}]}；按原负荷日期的北京时间小时展开，不改动时间轴 |
| 使用条件 | 办公建筑情景，未核实电压等级与用户分类；仅按购电量计费；未计基本电费、需量费、容量费、功率因数调整及税费差异 |
| 发布链接 | 未知 |
| 版本 | 未知 |
| 原始文件、SHA-256与获取时间 | [] |
| 父来源 | 无 / 未知 |

| 项目 | 记录 |
| --- | --- |
| source_id | scenario-emissions |
| 名称 | 人工情景常数排放因子（未冒充官方因子） |
| 地区 | 上海情景；非已核实官方省级因子 |
| 时间范围 | 人为情景假设，非官方历史因子 |
| 类别 | assumption |
| 单位 | {"grid_emission_factor": "kgCO2e/kWh"} |
| 处理记录 | 人工设置0.55 kgCO2e/kWh，展开为逐时常数；不是实测逐时碳强度 |
| 使用条件 | 仅购电运行排放情景，不含生命周期；CO2和CO2e按用户声明分别保留，不互换。官方适用年份与核算范围尚待核实 |
| 发布链接 | 未知 |
| 版本 | 未知 |
| 原始文件、SHA-256与获取时间 | [] |
| 父来源 | 无 / 未知 |

| 项目 | 记录 |
| --- | --- |
| source_id | electric-scenario |
| 名称 | 新增电侧设备、容量与项目约束假设 |
| 地区 | 匿名上海办公楼情景 |
| 时间范围 | 未知 |
| 类别 | assumption |
| 单位 | {"pv_cost_per_kw": "元/kW_DC", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW_DC"} |
| 处理记录 | {"budget_yuan":3000000.0,"grid_limit_kw":null,"pv_limit_kw":null,"emission_limit_kg":null,"emission_factor":0.55,"emission_species":"CO2e","emission_factor_year":"人为情景假设，非官方历史因子","tariff":{"region":"上海（人工情景，非官方现行电价）","applicable_year":"情景假设，不宣称适用于2017或当前年份","customer_class":"办公建筑情景，未核实电压等级与用户分类","cost_scope":"仅按购电量计费；未计基本电费、需量费、容量费、功率因数调整及税费差异","periods":[{"start_hour":0,"end_hour":7,"yuan_per_kwh":0.38},{"start_hour":7,"end_hour":17,"yuan_per_kwh":0.72},{"start_hour":17,"end_hour":22,"yuan_per_kwh":1.15},{"start_hour":22,"end_hour":24,"yuan_per_kwh":0.72}]},"pv_cost_per_kw":3200.0,"battery_cost_per_kwh":900.0,"battery_power_cost_per_kw":450.0,"installation_fraction":0.15,"battery_charge_efficiency":0.95,"battery_discharge_efficiency":0.95,"battery_power_fraction_of_peak":0.25,"battery_duration_hours":2.0,"pv_fraction_of_peak":0.5,"solar":{"latitude":31.23,"longitude":121.47,"coordinate_scope":"上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差","tilt_degrees":20.0,"azimuth_degrees":180.0,"system_loss_fraction":0.14,"gamma_pdc":-0.004,"inverter_efficiency":0.96},"include_solar":true}；负荷保持原值：峰值1060.97kW；电池功率=ceil(峰值×0.25/10)×10=270kW，能量=功率×2h=540kWh；光伏候选容量=ceil(峰值×0.5/10)×10=540kW_DC；规模受控的情景容量，不是优化定容或已核实屋顶容量 |
| 使用条件 | 增量投资：只计新增PV、电池、功率变换与比例安装费；既有电网接入、既有暖通及照明设备不计投资，不主张新建全楼投资 |
| 发布链接 | 未知 |
| 版本 | 未知 |
| 原始文件、SHA-256与获取时间 | [] |
| 父来源 | energydetective-load |

时序字段来源映射：

| 字段 | source_id | 单位 |
| --- | --- | --- |
| electric_load_kw | energydetective-load | kW |
| heat_load_kw_th | heating-disabled | kW_th |
| pv_per_kw | estimated-pv | kW/kW |
| electricity_price | scenario-tariff | 元/kWh |
| gas_price | heating-disabled | 元/kWh_LHV |
| grid_emission_factor | scenario-emissions | kgCO2e/kWh |
| gas_emission_factor | heating-disabled | kgCO2e/kWh_LHV |

## 本次评估边界、质量与未覆盖项

| 项目 | 说明 |
| --- | --- |
| 模式 | electric_only |
| 计量边界 | Q照明插座与W暖通用电的发布方类别合计；仅所选计量边界，不声称全楼总电量；无电气回路图可独立核实重叠或遗漏 |
| 未覆盖 | 未选中的计量类别及发布文件未覆盖的用电；供热需求及供热保障（零热数组仅为停用占位）；供冷服务量、管网、故障备用、全生命周期、基本电费和需量费 |
| 时间假设 | 发布方只称Time为timestamp，未明确区间锚点/时区；本次显式假设原时间为Asia/Shanghai、区间start；转换后为区间起点，不改历史年份 |
| 投资范围 | 增量投资：只计新增PV、电池、功率变换与比例安装费；既有电网接入、既有暖通及照明设备不计投资，不主张新建全楼投资 |
| 位置精度 | 上海市级代表点，非匿名楼宇精确位置；与NASA网格存在空间代表性误差 |
| 质量摘要 | 选中窗口168小时、2类测点全部通过；整份所选建筑原文件17520行。各类别全文件：Q记录8760、缺失0、重复0、负值0、非法/缺失数值0、跳变2；W记录8760、缺失0、重复0、负值0、非法/缺失数值0、跳变68。窗外异常保留并单独报告，未自动删除。 |
| 转换能量核对 | {"raw_energy_kwh":90087.68999999999,"normalized_energy_kwh":90087.69,"difference_kwh":1.4551915228366852e-11,"tolerance_kwh":0.0002,"input_numeric_precision":0.01,"source_rounding_bound_kwh":1.68,"passed":true,"explanation":"转换前后使用同一输入且不舍入，只允许浮点求和误差；容差取声明输入能量分辨率的1/100与1e-8 kWh较大者。原始数值舍入不确定性上界另列，不等同于转换误差或仪表精度。"} |
| 未完成或待核实 | 匿名建筑精确位置、计量回路覆盖及Time区间锚点缺少独立证明，采用明确的边界与时间假设；价格、排放因子、设备成本和场地均为人工情景，尚未核实2017适用政策或工程条件 |

## 模型假设、适用范围与尚未实现内容

- 仅评估已声明计量边界的电侧；保留选中W类别的暖通用电；不估算热需求，不保证供热。零热数组仅为停用占位，不代表没有供热需求。
- 增量投资只计新增光伏/储能及安装；既有电网接入和既有用能设备不在投资范围，运行费仅统计本评估期的电量收费部分。
- 热泵采用固定 COP，锅炉采用固定效率；燃气统一按低位热值 kWh_LHV 计量。
- 电池以 N+1 个区间边界状态记录：SOC[t] 是区间 t 开始状态，SOC[t+1] 是结束状态；期末等于期初。
- 电池充放电使用二进制互斥约束；不允许售电，不采用隐含缺供或负荷削减。
- 排放为购电与燃气使用的运行阶段排放，不代表设备全生命周期排放或全生命周期零碳。
- 仅比较配置文件提供的有限候选；不构成连续容量空间的全局规划最优证明。
- 尚未实现供冷、冷热管网、空间选址、设备故障备用、售电、绿证、碳抵消、全生命周期隐含排放。
- 不将本评估期结果乘以 52 等系数冒充全年指标，也不将全部投资与短期运行费相加称为生命周期成本。

## 执行追溯

状态流转：接收任务 → 校验输入 → 准备运行 → 生成候选 → 求解 → 结果校验 → 求解 → 结果校验 → 求解 → 结果校验 → 求解 → 结果校验 → 比较 → 报告 → 完成

| 工具 | 输入版本 | 状态 | 耗时 秒 | 结果文件 | 摘要 |
| --- | --- | --- | --- | --- | --- |
| validate_inputs | 1 | success | 0.0026 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/001_validate_inputs.json | validate_inputs 已执行并通过输入/输出 schema 校验 |
| build_candidates | 1 | success | 0.0007752 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/002_build_candidates.json | build_candidates 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0148 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/003_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0026 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/004_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0365 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/005_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0027 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/006_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0106 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/007_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0020 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/008_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0356 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/009_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0037 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/010_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| compare_scenarios | 1 | success | 0.0050 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/011_compare_scenarios.json | compare_scenarios 已执行并通过输入/输出 schema 校验 |
| generate_report | 1 | success | 0.0060 | examples/shanghai_168h/runs/2c9014edf78d4f058d4dcafb6c570c14/tools/012_generate_report.json | generate_report 已执行并通过输入/输出 schema 校验 |

结果文件：

- json: `examples/shanghai_168h/result.json`
- csv: `examples/shanghai_168h/scenarios.csv`
- markdown: `examples/shanghai_168h/report.md`
- dispatch_G: `examples/shanghai_168h/dispatch_G.csv`
- dispatch_GB: `examples/shanghai_168h/dispatch_GB.csv`
- dispatch_GP: `examples/shanghai_168h/dispatch_GP.csv`
- dispatch_GPB: `examples/shanghai_168h/dispatch_GPB.csv`
