# 反事实约束修复报告

在用户授权范围内搜索替代决策，保持全部负荷、时段、服务与其余业务输入；各路径互为替代，不自动采用。无可行上界时，只能说在当前范围内尚未找到经验证的修复方案。电侧模式不代表供热已建模或得到保障；购电上限放宽不含额外接入增容工程费用。

请求ID：three_paths_24h；基准run_id：a205baf811c94edda23a41c6b7efc097；输入版本：1。

原输入SHA-256：2a4e624b0265bd1cd3a48fa02fca8213c1b9c3b4b592d12c6d40339b27f3b2eb；原数据指纹：826a675882113482635b7e066ca0402a7a933df9cad60c94300e526fcd6a18d7。

原任务复核：infeasible；原始求解状态：{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}。

锁定条件：electric_load、heat_load、period、service；每条路径其余全部业务输入亦保持不变。

仅放宽预算、排放或购电功率上界，其余输入、固定候选集/容量边界和逐时足额供能保持，因此原可行解在更宽上界下仍可行。该性质不把超时当成不可行，也不证明唯一冲突原因。

各路径是互为替代的单参数决策，不是必须同时修改的清单，不等于发现唯一不可行原因。探索结果不自动采用。

## 追加初始投资预算 · d92a5b675429aba6

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：60000 元；允许范围：[60000, 600000]；精度：1000 元。

已发现且复核可行：401191 元；调整量：+341191 元。

可行/不可行边界精度达到：True；已知不可行下界：400664.0625；已知可行上界：401191.40625。

替代运行：41f6eebb103040ceb42adf5d4036fb8f；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.015902064000101745秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "D", "name": "光伏＋储能＋热泵", "source_id": "demo-candidates", "pv_kw": 50.0, "battery_power_kw": 20.0, "battery_energy_kwh": 150.0, "hp_kw_th": 20.0, "boiler_kw_th": 0.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 400999.99999999994, "operating_cost_yuan": 67.79668307060774, "emissions_kg": 60.506869110090804, "grid_kwh": 110.0124892910742, "gas_kwh_lhv": 0.0, "curtailed_pv_kwh": 13.643055750247058, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，195000.0，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=9a487381a3d44c999954d3fea987b307，结果SHA=e94078d8d2c7c6e8dede3c828f55ba67b88d49f87bc28dcbaaca59f6ada7f903

- expand，330000.0，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=7205251d8f014f53b54c3539d6b9f179，结果SHA=8b3f68133572c5342e2115742620fe196576a0b5a0e27f3f13600e7ee08579e1

- expand，600000.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=7eea8e5ad65d452bb073f11e0af1b62e，结果SHA=d1f4711180455c25fd8d24609bb1ec2c9c4dc75f0ffb2f28f4b1424631882475

- bisect，465000.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=6e18d5fe019a4e319b80e42fd4eeda4d，结果SHA=b811a0f692351faa74c9eb69792ab56e1498b53cc23d1a13a9f855a2f9f4b6f7

- bisect，397500.0，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=9574adad42544a2f8801f6ff9235e68e，结果SHA=0b1b8719bebea4444699961ac016e3ab99c484abba3963eb81c2df5593c68fa5

- bisect，431250.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=5beb532a22494cdf9304ee77e1816634，结果SHA=5f0165211ddaa5844559da976d02abe54a6c26316f3c8369395b7c5202a36c59

- bisect，414375.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=6cb9bed9a7544f9cbe16290716e537fa，结果SHA=394c740da7b39c6e9b0bea3e80cab40f1dcbc3fb1a2ac265c7963df9dd700c97

- bisect，405937.5，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=8c6c2bc313f649b1a340be76da4e3f75，结果SHA=a3b2204c9db98dde74b01daa9a669f9242f196fc02e506132a3d518de55c6e22

- bisect，401718.75，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=97299d0581ea4074881eb6406d2e6792，结果SHA=75193e0abf4a7f2159035184f0295aa92ce5cbbf47e731059ca5641c6294cc40

- bisect，399609.375，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=162016257fc64a1289596448092a47d8，结果SHA=3a8741acd8b975cce319c1d09dd769af28918e07994619ddf0e04baa864ed1a9

- bisect，400664.0625，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=eb12877f5d914d6d9c8d8b209817774a，结果SHA=ecf4a2d116876b463af8e262e1e4129be17477470495801c63ac7cee141d56ab

- bisect，401191.40625，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=41f6eebb103040ceb42adf5d4036fb8f，结果SHA=04bb7a057083ba0bc7e52d90351c0befea77f972185bcefa15713389628cc5fa

## 放宽运行排放上限 · 37c427a72518ec21

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：230 kgCO2e；允许范围：[230, 300]；精度：0.05 kgCO2e。

已发现且复核可行：239.741 kgCO2e；调整量：+9.74121 kgCO2e。

可行/不可行边界精度达到：True；已知不可行下界：239.70703125；已知可行上界：239.7412109375。

替代运行：ef514b4bc4304e198492b869030b45f4；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.002047931999868524秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "A", "name": "电网＋锅炉", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 20.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 15750.0, "operating_cost_yuan": 341.16666666666663, "emissions_kg": 239.73333333333335, "grid_kwh": 240.0, "gas_kwh_lhv": 533.3333333333333, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，247.5，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=73a3836d282e400a870277dc7be1d8b9，结果SHA=4d8b48e0e8f84eca7330df0cdf0dd917026159aebaef1aa8cb55ef8b0ab028fb

- bisect，238.75，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=3add4421eeab415cb6c7effb8fa4f5b2，结果SHA=dc62f3ce7afbda12c192e8da6b619cdf45a4a029c251242b5a78acdaaf0cfdce

- bisect，243.125，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=df064055242a41da8c288528026481fc，结果SHA=2d0142a25cc21655256f114138a02ae0d11caed841c237b76f7ad3314963e250

- bisect，240.9375，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=3ad76ff8e3504b368b073bbf000fa995，结果SHA=5723476d0a9f79b45e640885babda88484e09a055cd28b86d18491d2a01477b1

- bisect，239.84375，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=e85d1e3b99914dee92532c0e328712fc，结果SHA=1e433cc5996fbf85a2a9c9fff60d7aa94280a426d2fdfb1916db63bbd81589a1

- bisect，239.296875，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=e6bad70ceb8a4b68b3f938585fc6d42f，结果SHA=9a8b4fc4692a556ab0dcd056c154c0b4a3458d22a9cf857a79a4ec94c2be9b96

- bisect，239.5703125，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=05da752ea0bc44b2b9178bc614f9d9e1，结果SHA=64525f434253823583b481a5817d5a8b88167b558976e3f7f755dca0a65af3c7

- bisect，239.70703125，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=921faca8fcdb47a289b7e44bbaf485e7，结果SHA=68034a7560cc7fddd060d9d51242023ed408533446d0e7b63b1a39c91f8d5ec8

- bisect，239.775390625，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=ddb15484b4834ee785e735601ed6934f，结果SHA=77c7eabc7b5075c34fe390c0f677ae40ac5f722fb3e4ad4321c3747a98ed9459

- bisect，239.7412109375，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=ef514b4bc4304e198492b869030b45f4，结果SHA=69524f5ddeaef21deb6823b5b6d58fd9b6deb5ed7356f093712f99939f142ea5

## 增加购电功率上限 · 41e2e0108ea0d64b

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：12 kW；允许范围：[12, 25]；精度：0.01 kW。

已发现且复核可行：16.2529 kW；调整量：+4.25293 kW。

可行/不可行边界精度达到：True；已知不可行下界：16.24658203125；已知可行上界：16.2529296875。

替代运行：b8df5a9878bc46db9ff2f2ef2ab507fc；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.001991252000152599秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "C", "name": "电网＋热泵", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 20.0, "boiler_kw_th": 0.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 51400.0, "operating_cost_yuan": 277.0625, "emissions_kg": 214.5, "grid_kwh": 390.0, "gas_kwh_lhv": 0.0, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，15.25，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=4eca34d576844629a07c8cfdf8e81c49，结果SHA=909c208a4589b4960951d53bb9dee1917dcfee8aaa4e0ca4d611771a6ec51113

- expand，18.5，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=06b01107cb5141fa9bffe9a0bace07e3，结果SHA=c006024a9757ee78e80b1bd94c503fa388676603da3a2e1031896779c161758a

- bisect，16.875，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=65f3f029ee794ec6a828669b8d41af93，结果SHA=0426fdc977ec1f3d11c79df7f33ce3677c44d377a31a97fa3bbdac0fc8a8fd7e

- bisect，16.0625，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=b65c9db8f2e948a3b3627f954b65ba3c，结果SHA=b6c98242fb7695a87f92be474e1dd099962ef0a7d528bc89b685e1df869c7241

- bisect，16.46875，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=ee4f5579a32e4b2495257f18d17b6047，结果SHA=0ed6c3e92f6d44c7211a0d6952fbb273cb1e5a348ce4a2102f1c1a71575623aa

- bisect，16.265625，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=44cdfa658af442f9b79f47604e318aa9，结果SHA=2000b26e0fcd6106b977ea6ff79f0dda6bf2346957cdae09a6a94dacdbda5e78

- bisect，16.1640625，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=152d5e57903c44e3a53bf9227c4ccc4c，结果SHA=eb5a8d17a2b7647c2de35e88dad8a7ec04598a3cca6c6c3dc9ccaf339f5f2cb0

- bisect，16.21484375，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=6d0925c7a8ba4d5ca0341f748d4c1c7e，结果SHA=16979b1d04ab4a38e9aec3fb0ec9d277ae55c8012c640540897432246969c453

- bisect，16.240234375，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=6043fc1897974890aee5de0b439a7690，结果SHA=32621131e9a7921d9922e77f2224fb7710c55118d264e86f41f803597fea3f73

- bisect，16.2529296875，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=b8df5a9878bc46db9ff2f2ef2ab507fc，结果SHA=89a5beb60fefe022c1708eaa1b45bcf5c2447c9953a9612fd14358d1e554d2f5

- bisect，16.24658203125，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=8a2af845bc5545e8b02be08308dd9af6，结果SHA=0a43055b4c869300d99efde39fc9273462ebbcb3259fc71b9f4c55ec470fafb3

## 资源与来源

求解适配器调用：102；总耗时：0.641秒；限制：{'single_solve_seconds': 3.0, 'max_solver_calls': 128, 'total_seconds': 60.0}。

调用数统计现有求解适配器（含预检查），容量适配器内部可包含LP/MILP两阶段；时间预算为协作式，构模/校验/文件写出可能带来少量超时开销，耗时如实记录。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零", "反事实验收合成负荷：常规电功率恒10kW，热功率恒20kW_th；原168小时随机日型未拼接或年化；光伏沿用固定种子逐时合成"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json", "研究假设：预算60000元，购电12kW，排放上限按hours*230/24 kgCO2e；只统计实际输入期"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合", "研究假设：三个固定候选A(锅炉20)、C(热泵20)、D(光伏50/储能20kW150kWh/热泵20)；容量不随约束放宽而改变"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]

数据可为合成或混合研究情景，以上沿用原任务口径；不年化短时结果，不含设备隐含排放，不构成工程投资决定或理论原创性声明。
