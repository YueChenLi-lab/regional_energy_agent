# 反事实约束修复报告

在用户授权范围内搜索替代决策，保持全部负荷、时段、服务与其余业务输入；各路径互为替代，不自动采用。无可行上界时，只能说在当前范围内尚未找到经验证的修复方案。电侧模式不代表供热已建模或得到保障；购电上限放宽不含额外接入增容工程费用。

请求ID：multiple_conflicts_6h；基准run_id：e8c99d42446a4cc698b0a20f43e00e30；输入版本：1。

原输入SHA-256：0a27604fedad2a1c584b380297ca14de7540db14844c695e1951bfbce21627a9；原数据指纹：789406d7e7494994866a0cf886f00a33c1429d4027659b64bd416b1d1213bf54。

原任务复核：infeasible；原始求解状态：{'A': 'rejected'}。

锁定条件：electric_load、heat_load、period、service；每条路径其余全部业务输入亦保持不变。

仅放宽预算、排放或购电功率上界，其余输入、固定候选集/容量边界和逐时足额供能保持，因此原可行解在更宽上界下仍可行。该性质不把超时当成不可行，也不证明唯一冲突原因。

各路径是互为替代的单参数决策，不是必须同时修改的清单，不等于发现唯一不可行原因。探索结果不自动采用。

## 追加初始投资预算 · e36936ae832e9180

状态：not_found。在当前范围内尚未找到经验证的修复方案；末端状态已保留，不归因于唯一约束。

原值：0 元；允许范围：[0, 50000]；精度：10 元。

完整搜索轨迹：

- expand，12500.0，infeasible，原始状态{'A': 'rejected'}，run_id=632fda3d69784155913467b0c90180b4，结果SHA=3dd20544b49df6b3ac5290f11e1375bf11e5ab8b015e57ac9e6faa187a1dbc2b

- expand，25000.0，infeasible，原始状态{'A': 'infeasible'}，run_id=e2968be41fa94463a6649662fa5c51e2，结果SHA=5dfad979c838d749b97937800768e58360eb2caf31df4eac598faae294411aa4

- expand，50000.0，infeasible，原始状态{'A': 'infeasible'}，run_id=a6afa87eefaf44d9bda7d3d26b8ffd5f，结果SHA=24a21242125d956ab3fae98dab10468fde959b4975c50176887d3c1e7370a8a2

## 增加购电功率上限 · d9d727ff750d2abd

状态：not_found。在当前范围内尚未找到经验证的修复方案；末端状态已保留，不归因于唯一约束。

原值：0 kW；允许范围：[0, 30]；精度：0.01 kW。

完整搜索轨迹：

- expand，7.5，infeasible，原始状态{'A': 'rejected'}，run_id=9b5ec976ea8343b198c074f35e09c498，结果SHA=105372e485f436b80238f44e2afc679120aee8b8eefb35132e23adaf900ef1a6

- expand，15.0，infeasible，原始状态{'A': 'rejected'}，run_id=cdb0fe2f2f734e8193216118c04f75e7，结果SHA=810a2763052e32196f858acc2651b30c5237ff5dc00d1736feb012589525ce4f

- expand，30.0，infeasible，原始状态{'A': 'rejected'}，run_id=a839ed63a2554260ac9d6cf4284f4b11，结果SHA=9a1e7c7a57e12694429ccdc9c35c6efac9d498a9b91177e833d31cb0e8a40397

## 资源与来源

求解适配器调用：7；总耗时：0.048秒；限制：{'single_solve_seconds': 3.0, 'max_solver_calls': 32, 'total_seconds': 30.0}。

调用数统计现有求解适配器（含预检查），容量适配器内部可包含LP/MILP两阶段；时间预算为协作式，构模/校验/文件写出可能带来少量超时开销，耗时如实记录。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-06T06:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零", "反事实验收合成负荷：常规电功率恒10kW，热功率恒20kW_th；原168小时随机日型未拼接或年化；光伏沿用固定种子逐时合成"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-06T06:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json", "研究假设：预算60000元，购电12kW，排放上限按hours*230/24 kgCO2e；只统计实际输入期"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合", "研究假设：三个固定候选A(锅炉20)、C(热泵20)、D(光伏50/储能20kW150kWh/热泵20)；容量不随约束放宽而改变"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]

数据可为合成或混合研究情景，以上沿用原任务口径；不年化短时结果，不含设备隐含排放，不构成工程投资决定或理论原创性声明。
