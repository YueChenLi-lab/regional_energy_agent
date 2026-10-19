# 多情景最小最大后悔决策报告

当前基准run_id：b7c6cf390f91496092682d634aa0c325；研究成本口径：评估期购能费（初始投资另列，不是生命周期投资最优），单位元。

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

{"candidate": {"candidate_id": "A", "name": "电网＋燃气锅炉", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 120.0}, "capacity_sha256": "517c329997cb3da4c281ed248b6ba7f553059a8dee16f6e19b35766af673634b", "origin": "task", "source_run_id": "b7c6cf390f91496092682d634aa0c325"}

{"candidate": {"candidate_id": "B", "name": "光伏＋电网＋燃气锅炉", "source_id": "demo-candidates", "pv_kw": 120.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 120.0}, "capacity_sha256": "fc9ef8c8b0bbcce8d255a08adb5d1f9937c062597b91097ecd5084dccfa4f3cb", "origin": "task", "source_run_id": "b7c6cf390f91496092682d634aa0c325"}

{"candidate": {"candidate_id": "C", "name": "光伏＋热泵＋辅助燃气锅炉", "source_id": "demo-candidates", "pv_kw": 120.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 100.0, "boiler_kw_th": 60.0}, "capacity_sha256": "04bc7728e79a888a25d5e511fbf59cc1472702f3cc170625430c932788e09be4", "origin": "task", "source_run_id": "b7c6cf390f91496092682d634aa0c325"}

## 成本矩阵 / 后悔矩阵（元；null表示不可用，不是0）

{"A": {"base": 1845.381528336603, "electric_up": 2094.383810073651, "gas_up": 1965.4555522668757, "pv_down": 1845.381528336603}, "B": {"base": 1319.9093341493235, "electric_up": 1463.8171770489157, "gas_up": 1439.983358079596, "pv_down": 1414.5931822233913}, "C": {"base": 1060.7301966794612, "electric_up": 1253.690411908401, "gas_up": 1061.7606852789559, "pv_down": 1168.4272832077643}}

{"A": {"base": 784.6513316571418, "electric_up": 840.6933981652501, "gas_up": 903.6948669879198, "pv_down": 676.9542451288387}, "B": {"base": 259.1791374698623, "electric_up": 210.12676514051464, "gas_up": 378.2226728006401, "pv_down": 246.16589901562702}, "C": {"base": 0.0, "electric_up": 0.0, "gas_up": 0.0, "pv_down": 0.0}}

## 原始求解状态、独立复核和证据

- A / base：optimal；feasible；成本1845.381528336603元；gap=0.0；校验=True；run_id=a737603541a648038ddd3d4bd3501d8d；SHA=352625976dde85b644e7bd4998d3f03885d3f5dadbc35f12701d8be5fca7d487；原因[]

- B / base：optimal；feasible；成本1319.9093341493235元；gap=0.0；校验=True；run_id=65335bb93a724021a27e00572ca08d58；SHA=b140a01c0ad98252e0a2a392083765e5a37efa55ce70197e7ebce7d482d4e650；原因[]

- C / base：optimal；feasible；成本1060.7301966794612元；gap=0.0；校验=True；run_id=d01d3c187839468298596de123ee2329；SHA=e96fe7924a87f12bf7e1e135528cfb298f9cd39b5719deb8a4f2a320931604f6；原因[]

- A / electric_up：optimal；feasible；成本2094.383810073651元；gap=0.0；校验=True；run_id=4f484ac95c2142109fc7428c6a69095d；SHA=923bf8f612c0bb012caa030372c704d9a015ca87570c24b3eff96f90e7351e12；原因[]

- B / electric_up：optimal；feasible；成本1463.8171770489157元；gap=0.0；校验=True；run_id=5bc379367a7d49cf98d0f6207161602e；SHA=fe460fce3ca5bed75ade7f6266bd1d96cca3b58e38fb9432d53060b8b63d4459；原因[]

- C / electric_up：optimal；feasible；成本1253.690411908401元；gap=0.0；校验=True；run_id=09d03090614a47148ae14e2e265cc842；SHA=03e022d8e9434371128d8469db0431ea4827cdad72cb4e18b54397f8a9d33fce；原因[]

- A / gas_up：optimal；feasible；成本1965.4555522668757元；gap=0.0；校验=True；run_id=d7ce4fa69447400e8aa888a269520895；SHA=4ed7aac263ce0bd323202b959e5ff3eea90e2ab0dc9ce3773ef5a02f9fbbf8a5；原因[]

- B / gas_up：optimal；feasible；成本1439.983358079596元；gap=0.0；校验=True；run_id=a3662dc56b744e7bb87ff85f5068d0b2；SHA=f0cc709ba8d62385f675da835ade623fce105fd19ec4aa3c63c47d9afb3d5c22；原因[]

- C / gas_up：optimal；feasible；成本1061.7606852789559元；gap=0.0；校验=True；run_id=81a4eb3819684b679eeba5ad21611f03；SHA=0551e35df28f07effc106cb6155d2dafe83e81492f03958be12dd9e8fcb999b5；原因[]

- A / pv_down：optimal；feasible；成本1845.381528336603元；gap=0.0；校验=True；run_id=4edaa595388d41919ffd581fa763156d；SHA=735144b2ed57eea262735c323cdb4d87b2fcaa3a6c7b1db6c8e3615fffc83f6e；原因[]

- B / pv_down：optimal；feasible；成本1414.5931822233913元；gap=0.0；校验=True；run_id=3c61f08d6473450081bd6c1d50e3c259；SHA=bc0383d592692b0dc575a8a575663824b0f09b52a4cac66edec6a22268aa6790；原因[]

- C / pv_down：optimal；feasible；成本1168.4272832077643元；gap=0.0；校验=True；run_id=bc57eb28c42c4147a9996b1da1267e6b；SHA=acf4471410dddf60e202a925d369078eecf17167c0c0dcb8bba28e298f5b1e69；原因[]

## 口径与资源

调用12次；耗时0.159秒；限制{'single_solve_seconds': 5.0, 'max_solver_calls': 12, 'total_seconds': 60.0}。求解适配器可能内部执行LP/MILP两阶段，协作式时限不等于进程级硬截止。

全年NPV使用原重复代表年、寿命、更换、残值、固定及变动维护假设；物理排放不折现，不含设备隐含排放。短期不乘52、不与全部投资相加称生命周期成本。

每个情景的最佳基准包括该情景所有有效成本候选，包含在其他情景不可行的候选；未知单元与限时可行上界不能支撑精确认证。

最小后悔是成熟准则；项目贡献为受限编排、物理校验、状态处理与可解释交互，不宣称理论原创。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]
