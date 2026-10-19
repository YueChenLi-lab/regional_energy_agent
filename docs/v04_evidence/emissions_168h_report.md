# 反事实约束修复报告

在用户授权范围内搜索替代决策，保持全部负荷、时段、服务与其余业务输入；各路径互为替代，不自动采用。无可行上界时，只能说在当前范围内尚未找到经验证的修复方案。电侧模式不代表供热已建模或得到保障；购电上限放宽不含额外接入增容工程费用。

请求ID：emissions_168h；基准run_id：a705177e4f7b4b4d935b3a99dc0773b9；输入版本：1。

原输入SHA-256：73f0d7e213b9631b1dac5b167a6ec383ae789b44baff85913295389f07229f4e；原数据指纹：bb653e46124eee9f3a6d5bf637c0299a4fc812068ce40da264f53642d4d3ca2c。

原任务复核：infeasible；原始求解状态：{'A': 'infeasible'}。

锁定条件：electric_load、heat_load、period、service；每条路径其余全部业务输入亦保持不变。

仅放宽预算、排放或购电功率上界，其余输入、固定候选集/容量边界和逐时足额供能保持，因此原可行解在更宽上界下仍可行。该性质不把超时当成不可行，也不证明唯一冲突原因。

各路径是互为替代的单参数决策，不是必须同时修改的清单，不等于发现唯一不可行原因。探索结果不自动采用。

## 放宽运行排放上限 · 606d6dd58191f800

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：0 kgCO2e；允许范围：[0, 3000]；精度：0.1 kgCO2e。

已发现且复核可行：1678.16 kgCO2e；调整量：+1678.16 kgCO2e。

可行/不可行边界精度达到：True；已知不可行下界：1678.070068359375；已知可行上界：1678.16162109375。

替代运行：98259dcf8af34cec9e3b1fe275ef9d0f；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.00673800200002006秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "A", "name": "电网＋锅炉", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 20.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 15750.0, "operating_cost_yuan": 2388.1666666666665, "emissions_kg": 1678.1333333333337, "grid_kwh": 1680.0, "gas_kwh_lhv": 3733.333333333334, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 1680.0, "heat_load_kwh_th": 3360.0, "supply_satisfied": true, "period_hours": 168.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，750.0，infeasible，原始状态{'A': 'infeasible'}，run_id=3fa6ead034aa45699d9e930f6898074d，结果SHA=6971cc6c34e0f75c6d7b544b76416bc3fd5086ca5b2d88c176f4d4a34efaa35f

- expand，1500.0，infeasible，原始状态{'A': 'infeasible'}，run_id=7f0c36a9169a4f35bef4cdde9a3c84fd，结果SHA=a29df462c55893ac93435f40083a4ad730428b5586cc7c1c06e789486da0c68f

- expand，3000.0，feasible，原始状态{'A': 'optimal'}，run_id=86efb27b49e845f49f90bdea6866d7f8，结果SHA=cf4a087164436847f9605dbf83e51323f073c09b74cb989b06270e06c4d98828

- bisect，2250.0，feasible，原始状态{'A': 'optimal'}，run_id=4a570fadb070463bb7f08b082b17e61d，结果SHA=065582f24f37b5ce3da0cda05153c888fb1f9136913dde5cd2eac6ddffa4df9f

- bisect，1875.0，feasible，原始状态{'A': 'optimal'}，run_id=96477e78c7ee473a94d7fde05010357a，结果SHA=0aea418c95b2756be01510c2cbae472f82af174c98a2b1f394237de422c95a3c

- bisect，1687.5，feasible，原始状态{'A': 'optimal'}，run_id=43f98e161e1749f0a9603071b11ebeb6，结果SHA=57f1ee7e0ae4eb671a3e54f06f4d81411025487e61e0a2147c6244269729cca7

- bisect，1593.75，infeasible，原始状态{'A': 'infeasible'}，run_id=ab21ceb487dc48249e05081bed3cf76c，结果SHA=8baa50f1ff42488b89aac77b3459641a9c6aae138fccf6f0a2a3bf12212ef100

- bisect，1640.625，infeasible，原始状态{'A': 'infeasible'}，run_id=3e76b040b7b14820877a8a3e354e957a，结果SHA=39efc1b06d12423bf6c0433a5623daeb1eca9501e0db9d52ad992e0f230891d3

- bisect，1664.0625，infeasible，原始状态{'A': 'infeasible'}，run_id=21e5754848994c3e9559754d361825b7，结果SHA=91a904a5ac9b1c67aa0d41ab8a21933d89ed243f2c6adc215c6d7a341a7ba641

- bisect，1675.78125，infeasible，原始状态{'A': 'infeasible'}，run_id=c2da96a614354d46a0cc8e0f5ea6ac1f，结果SHA=cd8924edd0b1e4bc045f14d81ccb0317ef913b3098aca8f37aaf1eb463971eb2

- bisect，1681.640625，feasible，原始状态{'A': 'optimal'}，run_id=5ddcb20f98b94eac96e0ca5495656111，结果SHA=33a029afdb31ce8fa61d560f9ea3530dc42128f970599ba88fea4cde7f941b9a

- bisect，1678.7109375，feasible，原始状态{'A': 'optimal'}，run_id=6a4bb1453baf482293a2c2d0ab6b8189，结果SHA=96b05a2d8b5046ef69c8a58beec55c9111ca055e347e603bf427b56e57f97d08

- bisect，1677.24609375，infeasible，原始状态{'A': 'infeasible'}，run_id=c26084a3bd694587b80cf3a89a70696a，结果SHA=0788764a1493993487eaf3d5a772c220478f2d389580d6247a00dcc96c85cdf6

- bisect，1677.978515625，infeasible，原始状态{'A': 'infeasible'}，run_id=d26dc6ff02b14e88826c7d1ac9ad0cef，结果SHA=68be7a83c63275fd2383a10bb766a705feb627edf4ad6173e5d656c8b34bc417

- bisect，1678.3447265625，feasible，原始状态{'A': 'optimal'}，run_id=bf4609f935e04f7183202188e4b3f383，结果SHA=b3e8b283d31e437d69b270056d55ee4b8ce854c6781fa8f20971a17e36c6bb3c

- bisect，1678.16162109375，feasible，原始状态{'A': 'optimal'}，run_id=98259dcf8af34cec9e3b1fe275ef9d0f，结果SHA=9070a9dc7f398a810d719bad0ff584f33b7a8c05571be05629ab4fcec088cd5b

- bisect，1678.070068359375，infeasible，原始状态{'A': 'infeasible'}，run_id=c39d6bdd01854a85876558390bc4be61，结果SHA=f66cf1c6cf050adb9160eeda6fde675d77548b0563e9543f7cd4056d5d92ac47

## 资源与来源

求解适配器调用：18；总耗时：0.423秒；限制：{'single_solve_seconds': 3.0, 'max_solver_calls': 32, 'total_seconds': 30.0}。

调用数统计现有求解适配器（含预检查），容量适配器内部可包含LP/MILP两阶段；时间预算为协作式，构模/校验/文件写出可能带来少量超时开销，耗时如实记录。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-13T00:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零", "反事实验收合成负荷：常规电功率恒10kW，热功率恒20kW_th；原168小时随机日型未拼接或年化；光伏沿用固定种子逐时合成"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-13T00:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json", "研究假设：预算60000元，购电12kW，排放上限按hours*230/24 kgCO2e；只统计实际输入期"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合", "研究假设：三个固定候选A(锅炉20)、C(热泵20)、D(光伏50/储能20kW150kWh/热泵20)；容量不随约束放宽而改变"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]

数据可为合成或混合研究情景，以上沿用原任务口径；不年化短时结果，不含设备隐含排放，不构成工程投资决定或理论原创性声明。
