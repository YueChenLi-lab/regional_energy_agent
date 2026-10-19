# 反事实约束修复报告

在用户授权范围内搜索替代决策，保持全部负荷、时段、服务与其余业务输入；各路径互为替代，不自动采用。无可行上界时，只能说在当前范围内尚未找到经验证的修复方案。电侧模式不代表供热已建模或得到保障；购电上限放宽不含额外接入增容工程费用。

请求ID：budget_6h；基准run_id：63ed208b3f074f05bacc5757391aaa04；输入版本：1。

原输入SHA-256：42af99c907dd6e2d0deea79077c16524f06f808aa2bc1bcfd2d12c37f8866e09；原数据指纹：789406d7e7494994866a0cf886f00a33c1429d4027659b64bd416b1d1213bf54。

原任务复核：infeasible；原始求解状态：{'A': 'rejected'}。

锁定条件：electric_load、heat_load、period、service；每条路径其余全部业务输入亦保持不变。

仅放宽预算、排放或购电功率上界，其余输入、固定候选集/容量边界和逐时足额供能保持，因此原可行解在更宽上界下仍可行。该性质不把超时当成不可行，也不证明唯一冲突原因。

各路径是互为替代的单参数决策，不是必须同时修改的清单，不等于发现唯一不可行原因。探索结果不自动采用。

## 追加初始投资预算 · 15b428a659f78da0

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：0 元；允许范围：[0, 50000]；精度：10 元。

已发现且复核可行：15753.2 元；调整量：+15753.2 元。

可行/不可行边界精度达到：True；已知不可行下界：15747.0703125；已知可行上界：15753.173828125。

替代运行：658f5a07d1e84abd88d7dfd4d1e89ca0；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.0015064589999838063秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "A", "name": "电网＋锅炉", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 20.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 15750.0, "operating_cost_yuan": 65.46666666666667, "emissions_kg": 59.93333333333333, "grid_kwh": 60.0, "gas_kwh_lhv": 133.33333333333334, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 60.0, "heat_load_kwh_th": 120.0, "supply_satisfied": true, "period_hours": 6.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，12500.0，infeasible，原始状态{'A': 'rejected'}，run_id=4bd9b33c75cd49c9a9beb4012d99c23a，结果SHA=24d3abc5f7632c95b4694fdaea44925ef2d620e00a0b3e95abc54c6906d36431

- expand，25000.0，feasible，原始状态{'A': 'optimal'}，run_id=1b61f4a577b641249c1f31e56081248f，结果SHA=b17668ceb5a8e1ccb9d8fefa7c5b37c633b5f79f4f0045f2075a380f0d121c39

- bisect，18750.0，feasible，原始状态{'A': 'optimal'}，run_id=d8948db857a14d0eaea3a7bdae7896b6，结果SHA=d619774db014857e20e64a47d8d918ce2fe72586ff7ffd39d52893c4f59967ed

- bisect，15625.0，infeasible，原始状态{'A': 'rejected'}，run_id=8425a50a72154e7abdda9412d316f673，结果SHA=a1634208674c6e228a0f135ddf9ef9a4e7bd19f658815b3e694dc1d19560c79a

- bisect，17187.5，feasible，原始状态{'A': 'optimal'}，run_id=bc07befc804e464499f83a7c9945cdb7，结果SHA=bcb790580fdad37630721457a65834d98fede0b96cf134361326ced7d2bbdfc8

- bisect，16406.25，feasible，原始状态{'A': 'optimal'}，run_id=f81b4caf082f46b4a9c81aa602429961，结果SHA=96aa39bfb4e925d6e7f0db948922e10d0ca4292d312d7bf0ec1fef8dfc095e12

- bisect，16015.625，feasible，原始状态{'A': 'optimal'}，run_id=734099675a2c464f987158dc161fe39f，结果SHA=f1475ed06f2f804435d691f71a470df3bb2676e9420fd2241c9df6a030a0f00d

- bisect，15820.3125，feasible，原始状态{'A': 'optimal'}，run_id=f7b8fedc02e24632a97b7ca8e5f8ae0c，结果SHA=05dc4ccb96b5b9e9e279e259a07b14c7a1723e9a4c6b7d81c68c6af03aa32378

- bisect，15722.65625，infeasible，原始状态{'A': 'rejected'}，run_id=5cea3e42d54048009b61cc84c333a19b，结果SHA=58e039bc3b70a1059c24f4e197476372a560c7cc4b561e30a9aa86dc3bb38148

- bisect，15771.484375，feasible，原始状态{'A': 'optimal'}，run_id=e6936fb2722b43b18c35eb025e129b2b，结果SHA=a34013ec920404de663527bda0c181fb480ba1556e880cc746acd18aaef2ba6b

- bisect，15747.0703125，infeasible，原始状态{'A': 'rejected'}，run_id=64b400763a0848e68281fbbc0ae3107a，结果SHA=1a037e72ff6659ed72ff8617beeae90a4a670a4261a1db9cf005c2ca31a4f227

- bisect，15759.27734375，feasible，原始状态{'A': 'optimal'}，run_id=56917d555a4140198e6f7f7e689c1da8，结果SHA=b8c697f63ee0c3be3700915784c078f3e954eafc0a32cceba36d41440d2d953f

- bisect，15753.173828125，feasible，原始状态{'A': 'optimal'}，run_id=658f5a07d1e84abd88d7dfd4d1e89ca0，结果SHA=37ce9ce138ff68ee98414598ec5b58b44198e3709c6e81615e7f2d38902499ae

## 资源与来源

求解适配器调用：14；总耗时：0.149秒；限制：{'single_solve_seconds': 3.0, 'max_solver_calls': 32, 'total_seconds': 30.0}。

调用数统计现有求解适配器（含预检查），容量适配器内部可包含LP/MILP两阶段；时间预算为协作式，构模/校验/文件写出可能带来少量超时开销，耗时如实记录。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-06T06:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零", "反事实验收合成负荷：常规电功率恒10kW，热功率恒20kW_th；原168小时随机日型未拼接或年化；光伏沿用固定种子逐时合成"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-06T06:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json", "研究假设：预算60000元，购电12kW，排放上限按hours*230/24 kgCO2e；只统计实际输入期"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合", "研究假设：三个固定候选A(锅炉20)、C(热泵20)、D(光伏50/储能20kW150kWh/热泵20)；容量不随约束放宽而改变"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]

数据可为合成或混合研究情景，以上沿用原任务口径；不年化短时结果，不含设备隐含排放，不构成工程投资决定或理论原创性声明。
