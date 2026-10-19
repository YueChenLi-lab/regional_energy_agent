# 多情景最小最大后悔决策报告

当前基准run_id：fc1f95100d874cab890d956d5758a3ad；研究成本口径：评估期购能费（初始投资另列，不是生命周期投资最优），单位元。

合成演示数据

基准情景最便宜：C；最小最大后悔候选：C。

当前有限候选×有限情景内，全部单元已证明最优且校验通过或已确认不可行；在所设数值容差内认证最小最大后悔。 并列项按ID稳定展示，不代表严格优劣；未分配情景概率。

C：全部指定情景均有经独立校验的可行运行；最坏情景base、electric_up、gas_up、pv_down，比该情景当前候选集内最佳已得成本多付0.0000元。

最小最大成本项（不同准则）：C；未给情景分配概率，不把平均值称为期望。

投资容量固定、逐时运行可适应；有限候选和有限研究假设不覆盖全部未来，不构成连续容量空间全局稳健最优。探索未改写或采用确认任务。

## 授权情景（非预测）

{"scenario_id": "base", "name": "基准", "is_baseline": true, "electricity_price_multiplier": 1.0, "gas_price_multiplier": 1.0, "pv_multiplier": 1.0, "electric_load_multiplier": 1.0, "multiplier_unit": "1", "assumption": "人为研究假设，不是价格、资源或负荷预测"}

{"scenario_id": "electric_up", "name": "购电价格上涨20%", "is_baseline": false, "electricity_price_multiplier": 1.2, "gas_price_multiplier": 1.0, "pv_multiplier": 1.0, "electric_load_multiplier": 1.0, "multiplier_unit": "1", "assumption": "人为研究假设，不是价格、资源或负荷预测"}

{"scenario_id": "gas_up", "name": "燃气价格上涨20%", "is_baseline": false, "electricity_price_multiplier": 1.0, "gas_price_multiplier": 1.2, "pv_multiplier": 1.0, "electric_load_multiplier": 1.0, "multiplier_unit": "1", "assumption": "人为研究假设，不是价格、资源或负荷预测"}

{"scenario_id": "pv_down", "name": "光伏出力下降20%", "is_baseline": false, "electricity_price_multiplier": 1.0, "gas_price_multiplier": 1.0, "pv_multiplier": 0.8, "electric_load_multiplier": 1.0, "multiplier_unit": "1", "assumption": "人为研究假设，不是价格、资源或负荷预测"}

## 固定配置与来源

{"candidate": {"candidate_id": "A", "name": "电网＋燃气锅炉", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 120.0}, "capacity_sha256": "517c329997cb3da4c281ed248b6ba7f553059a8dee16f6e19b35766af673634b", "origin": "task", "source_run_id": "fc1f95100d874cab890d956d5758a3ad"}

{"candidate": {"candidate_id": "B", "name": "光伏＋电网＋燃气锅炉", "source_id": "demo-candidates", "pv_kw": 120.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 120.0}, "capacity_sha256": "fc9ef8c8b0bbcce8d255a08adb5d1f9937c062597b91097ecd5084dccfa4f3cb", "origin": "task", "source_run_id": "fc1f95100d874cab890d956d5758a3ad"}

{"candidate": {"candidate_id": "C", "name": "光伏＋热泵＋辅助燃气锅炉", "source_id": "demo-candidates", "pv_kw": 120.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 100.0, "boiler_kw_th": 60.0}, "capacity_sha256": "04bc7728e79a888a25d5e511fbf59cc1472702f3cc170625430c932788e09be4", "origin": "task", "source_run_id": "fc1f95100d874cab890d956d5758a3ad"}

## 成本矩阵 / 后悔矩阵（元；null表示不可用，不是0）

{"A": {"base": 1845.381528336603, "electric_up": 2094.383810073651, "gas_up": 1965.4555522668757, "pv_down": 1845.381528336603}, "B": {"base": 1319.9093341493235, "electric_up": 1463.8171770489157, "gas_up": 1439.983358079596, "pv_down": 1414.5931822233913}, "C": {"base": 1060.7301966794612, "electric_up": 1253.690411908401, "gas_up": 1061.7606852789559, "pv_down": 1168.4272832077643}}

{"A": {"base": 784.6513316571418, "electric_up": 840.6933981652501, "gas_up": 903.6948669879198, "pv_down": 676.9542451288387}, "B": {"base": 259.1791374698623, "electric_up": 210.12676514051464, "gas_up": 378.2226728006401, "pv_down": 246.16589901562702}, "C": {"base": 0.0, "electric_up": 0.0, "gas_up": 0.0, "pv_down": 0.0}}

## 原始求解状态、独立复核和证据

- A / base：optimal；feasible；成本1845.381528336603元；gap=0.0；校验=True；run_id=2b1135111e964a0c8535970c3285f918；SHA=332edf5239014ce2c7c9ebc747d94065a148fc1f880fbce0d601e33af985262e；原因[]

- B / base：optimal；feasible；成本1319.9093341493235元；gap=0.0；校验=True；run_id=2db97b3c7db74e80877119c99e3b6cce；SHA=fa10ed96a1c2851a7626a85794b89ac29e14a4d35ce79717d09d5da02a54c9fe；原因[]

- C / base：optimal；feasible；成本1060.7301966794612元；gap=0.0；校验=True；run_id=fd4e103a9d314b27a4d9b2b9aa32d41c；SHA=f86dcc29fd1200881530a2ddf6b5cc6380551ac2e3abd020429b8ca48ce53f90；原因[]

- A / electric_up：optimal；feasible；成本2094.383810073651元；gap=0.0；校验=True；run_id=e73e238bff304dc0890015357b535e0e；SHA=ec8131d5f896f4f94d39ef109d91ec1b5f674b3d57f2a68fd93c820fc7d13e6f；原因[]

- B / electric_up：optimal；feasible；成本1463.8171770489157元；gap=0.0；校验=True；run_id=a0e53ce62e5843d59fd0bc4a5e1a7a93；SHA=4e220f2cb0fa3e131c2649bcbe711014e008d26583544cfe9fdadd8177bcd4ed；原因[]

- C / electric_up：optimal；feasible；成本1253.690411908401元；gap=0.0；校验=True；run_id=47a63924fe0d4b94b9673b12f449f4f7；SHA=5b4a52cc0e6804f79b50c520aade762dab8519a9bf57bce79c76a1eee885c83f；原因[]

- A / gas_up：optimal；feasible；成本1965.4555522668757元；gap=0.0；校验=True；run_id=9627f8f1dc864d2e9796d76e96b3a7e2；SHA=1b2b49cdafc0de0d54de1a5b2d1c2bb5ecb696ba89304f1dfe32088f643102f4；原因[]

- B / gas_up：optimal；feasible；成本1439.983358079596元；gap=0.0；校验=True；run_id=41bd6201589b48bd93cfe11749a2a7e1；SHA=39a51d2d2117b130da79c73415948164a0313440ea0fe0a938585432b2da6139；原因[]

- C / gas_up：optimal；feasible；成本1061.7606852789559元；gap=0.0；校验=True；run_id=4a1297ca1fad4ede839a1d6bcda59192；SHA=86e1e6b55b3d7e35d6af1e0b92552ea3cc6c3cbd1aaf161ab3ba074c8abba752；原因[]

- A / pv_down：optimal；feasible；成本1845.381528336603元；gap=0.0；校验=True；run_id=4c997d7dfba94f2491c10593331a990e；SHA=e6a124c2cbfc4871b6be3b590973cd1f1803e574c3caab40890ec2d4bbae78d4；原因[]

- B / pv_down：optimal；feasible；成本1414.5931822233913元；gap=0.0；校验=True；run_id=819f1e656eb4441281a53147a6660dfd；SHA=d50838e5eb7e53a262fc4e889b00c965d34f94a365a8f7abc34d5e63a9422e5c；原因[]

- C / pv_down：optimal；feasible；成本1168.4272832077643元；gap=0.0；校验=True；run_id=b679d38cd8a34fb3abefaf03f2f0e34c；SHA=4ceb41fe50f5c371f141e4050e12cb8cb3a5ecad0793b27da2e06471807e7f9e；原因[]

## 口径与资源

调用12次；耗时0.152秒；限制{'single_solve_seconds': 3.0, 'max_solver_calls': 12, 'total_seconds': 45.0}。求解适配器可能内部执行LP/MILP两阶段，协作式时限不等于进程级硬截止。

全年NPV使用原重复代表年、寿命、更换、残值、固定及变动维护假设；物理排放不折现，不含设备隐含排放。短期不乘52、不与全部投资相加称生命周期成本。

每个情景的最佳基准包括该情景所有有效成本候选，包含在其他情景不可行的候选；未知单元与限时可行上界不能支撑精确认证。

最小后悔是成熟准则；项目贡献为受限编排、物理校验、状态处理与可解释交互，不宣称理论原创。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]
