# 反事实约束修复报告

在用户授权范围内搜索替代决策，保持全部负荷、时段、服务与其余业务输入；各路径互为替代，不自动采用。无可行上界时，只能说在当前范围内尚未找到经验证的修复方案。电侧模式不代表供热已建模或得到保障；购电上限放宽不含额外接入增容工程费用。

请求ID：synthetic-24h-repair；基准run_id：93ecbb892f3f40ec94ab01a8e8c83136；输入版本：1。

原输入SHA-256：2a4e624b0265bd1cd3a48fa02fca8213c1b9c3b4b592d12c6d40339b27f3b2eb；原数据指纹：826a675882113482635b7e066ca0402a7a933df9cad60c94300e526fcd6a18d7。

原任务复核：infeasible；原始求解状态：{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}。

锁定条件：electric_load、heat_load、period、service；每条路径其余全部业务输入亦保持不变。

仅放宽预算、排放或购电功率上界，其余输入、固定候选集/容量边界和逐时足额供能保持，因此原可行解在更宽上界下仍可行。该性质不把超时当成不可行，也不证明唯一冲突原因。

各路径是互为替代的单参数决策，不是必须同时修改的清单，不等于发现唯一不可行原因。探索结果不自动采用。

## 追加初始投资预算 · a53bb3c9adf0be42

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：60000 元；允许范围：[60000, 600000]；精度：1000 元。

已发现且复核可行：401191 元；调整量：+341191 元。

可行/不可行边界精度达到：True；已知不可行下界：400664.0625；已知可行上界：401191.40625。

替代运行：7732f271842747c3bb347feac0b957cd；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.017913855999722728秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "D", "name": "光伏＋储能＋热泵", "source_id": "demo-candidates", "pv_kw": 50.0, "battery_power_kw": 20.0, "battery_energy_kwh": 150.0, "hp_kw_th": 20.0, "boiler_kw_th": 0.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 400999.99999999994, "operating_cost_yuan": 67.79668307060774, "emissions_kg": 60.506869110090804, "grid_kwh": 110.0124892910742, "gas_kwh_lhv": 0.0, "curtailed_pv_kwh": 13.643055750247058, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，195000.0，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=4295a24df6ca4aee9650a76e6dfcacf3，结果SHA=6e3a8cb378275fc39157039b608109a78db827acfe76e374696e51920ece7172

- expand，330000.0，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=e23b322a065542cdafc28e1b7235d9b1，结果SHA=b4f6b742e35a739a635acf638bcbf140ab40bcd453e652dc333b8eb7a67c9181

- expand，600000.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=2527d8690d664f178fda75b6cc18447e，结果SHA=1119ea74882e393236c1d0caf2e8c7dbfe34f69b186f1d08d7ff0d09ddf8e987

- bisect，465000.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=af8e70f8f4e541898b4e75061f7960ea，结果SHA=b12b7cdb1ecea257313d7b63ed759464381c236302b444ed15e99f96cfb42104

- bisect，397500.0，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=1e7f76dfb7f24482b215c381a50ab3ec，结果SHA=a502599a5918a80075ff1f7dbc54fb9d754ce0502479fbae8e4216b1c3752859

- bisect，431250.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=05c25aaaacc5407ca798c04ae87f2e3e，结果SHA=54e9c270c4ddd42e1317077f5fed816ddff578ec06a1caaa5d6fcaade1751567

- bisect，414375.0，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=18cf8499313b4df29c37402bc7c208b8，结果SHA=06a33b1b468706b4a5d3a8320453d2b58077896d64615f640a6aaa4c41c3ba6f

- bisect，405937.5，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=704559a8ab4648989a19247fa901f0b0，结果SHA=858ad8c091d7342909ea75e262f9489f1f3495b72100b70b6a37203db74dfae1

- bisect，401718.75，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=06d23d6d19d34250b1810e91977e7b1b，结果SHA=b66601fbe254f4826061fb79941f92bfd8ccc61506dd769b2b3d5f4e9c9465c7

- bisect，399609.375，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=fc48ceb1c556413ea21bdf057fed1670，结果SHA=ea06d3a3dd9cdda0b9035b1cac868d89b20448693112c69e4ed5c3dc40788b38

- bisect，400664.0625，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=2a4c0f1924c04eaeb25d63ad6a80f179，结果SHA=533bb25d57d76829f3ccff6ce6ab10bc4434ccae37201113bd7fb2c36c8e2603

- bisect，401191.40625，feasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'optimal'}，run_id=7732f271842747c3bb347feac0b957cd，结果SHA=b1e1fbf2a83798e0b4615d7c599e7bb773eb6bb91e65cc9cc8155c4f3b417345

## 放宽运行排放上限 · cb48bf5edf1e1d6e

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：230 kgCO2e；允许范围：[230, 300]；精度：0.05 kgCO2e。

已发现且复核可行：239.741 kgCO2e；调整量：+9.74121 kgCO2e。

可行/不可行边界精度达到：True；已知不可行下界：239.70703125；已知可行上界：239.7412109375。

替代运行：5f73cbba7a2845d38fb3a7a3093ca951；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.002507484001398552秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "A", "name": "电网＋锅炉", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 0.0, "boiler_kw_th": 20.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 15750.0, "operating_cost_yuan": 341.16666666666663, "emissions_kg": 239.73333333333335, "grid_kwh": 240.0, "gas_kwh_lhv": 533.3333333333333, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，247.5，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=25aae213d1b644338d7aaf8213e2458f，结果SHA=e0857fd5d37bdb9a523a1121f756a09e0df9012b0c7e3db7f206d025fb7d4ac8

- bisect，238.75，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=748d5b1d9ae241e5844621ec7518839a，结果SHA=007821bdce4a330a18ac0504e2a3619bcfdf77426a93b386193dff7047ad8756

- bisect，243.125，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=cc6b79f8402f4bf3b698aec3cdd057a9，结果SHA=b4a360018324ba6685c277c27d8802a886e9c4e5bd9f4da9ecc5db16a67966b4

- bisect，240.9375，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=f6b1c05cd1154e739d42fdea3955f4cc，结果SHA=aae1f0cd635bf4beb9a1b4a9f84c6786a2eec2364fdac0297e2ad46a3811db9b

- bisect，239.84375，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=daea2250e4854622816cdfe056f7b314，结果SHA=16d0be306ad411379a62a1c793e643c36a950d13cdc14b79aea24ec590e981f7

- bisect，239.296875，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=2469fe4764ba4a7c9d8983cfaac98cee，结果SHA=d798fb71c5649158d233ab2d7b031f97e942d3ddff2880731e60d12fe5d13916

- bisect，239.5703125，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=e4aa96597db14a1abb81faf5d86847b1，结果SHA=756d1bfe9e7e3c7d9c15f953a2236136050ae7111c73ad3ec31f20f4fbc1efa4

- bisect，239.70703125，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=845f216523b34d7cbba456c5e5ad30e4，结果SHA=96fcbce8d3f9df9ff5f05baa26824bc6211f6a1d21acfda727151b5082e4511a

- bisect，239.775390625，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=ad6f43d121b6446687306dc0e372c7e2，结果SHA=ee0a1169f341eeec4423fc6a6810ce7a4621778407380d51be4a033603f76d42

- bisect，239.7412109375，feasible，原始状态{'A': 'optimal', 'C': 'infeasible', 'D': 'rejected'}，run_id=5f73cbba7a2845d38fb3a7a3093ca951，结果SHA=001039b124ff4e0fece234d0403f8541b0370e78a75841cefc07a4f93f7a0e92

## 增加购电功率上限 · 4a4d2f5010470082

状态：verified_repair。在声明范围、现有模型和指定精度下找到可行边界；不代表运行目标或所有可能设备模型的全局最优。

原值：12 kW；允许范围：[12, 25]；精度：0.01 kW。

已发现且复核可行：16.2529 kW；调整量：+4.25293 kW。

可行/不可行边界精度达到：True；已知不可行下界：16.24658203125；已知可行上界：16.2529296875。

替代运行：4317dec289c94b89b1d8818a3078dd12；新版本：2；求解状态：optimal；gap：0.0；求解耗时：0.002322902000742033秒；独立复核：True。

设备容量（kW / kWh / kW_th）：{"candidate_id": "C", "name": "电网＋热泵", "source_id": "demo-candidates", "pv_kw": 0.0, "battery_power_kw": 0.0, "battery_energy_kwh": 0.0, "hp_kw_th": 20.0, "boiler_kw_th": 0.0}

指标（投资/购能费：元；排放物质与单位见原任务；仅输入评估期）：{"investment_yuan": 51400.0, "operating_cost_yuan": 277.0625, "emissions_kg": 214.5, "grid_kwh": 390.0, "gas_kwh_lhv": 0.0, "curtailed_pv_kwh": 0.0, "electric_load_kwh": 240.0, "heat_load_kwh_th": 480.0, "supply_satisfied": true, "period_hours": 24.0, "emission_unit": "kgCO2e"}

NPV成本：未启用全年经济评价。

完整搜索轨迹：

- expand，15.25，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=b1fb6e4322a94bf1bfb1720671e97f01，结果SHA=e111aba3d78f5ba198e748ad1e544559ef47087466d3fed82d7ab0cdca2013fd

- expand，18.5，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=00728c5fa4604c9a8711bc2623bf964c，结果SHA=cd890b8536a70c0ac750f1311dec229722be97d7ec33a0cd49d9c265d91eade5

- bisect，16.875，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=1aadd1a577064f56bf2e46ea79864617，结果SHA=5f9d8a8dba0fc510251cd839054ba0375fc736d3345109c80d804f12beced21b

- bisect，16.0625，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=acc74f33366f4c189512bad187d03069，结果SHA=755ef620662087b206d982423bfa48c6cedab1d20c5ac978247ebb17f37ba6d7

- bisect，16.46875，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=3adb28af0e734ee3b5d3d4ece21d4dee，结果SHA=27f6778ad87c2bd0cfd556d788ba665366f1b0d56187d90bd79deb43fc9c5532

- bisect，16.265625，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=102a10c9518f47dfbde57bd8daa999ac，结果SHA=2a3bdd19df1acb50777ce5b0df72eb5acb534cd13a456659b102713dc5127c1a

- bisect，16.1640625，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=cdbc0aa1ad62444489b286548a1d219a，结果SHA=1324148ffe08ce99eb730537c55760e02a8ba619ed2be4135e1b44be577c4ca8

- bisect，16.21484375，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=bb2bd9a831ef460e9e174c22d3f5c494，结果SHA=34aba3875a34bebdd7191051d323eef6fd798750b503c25328c241847ceea6f3

- bisect，16.240234375，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=fe6ea78f47c644468e9f0cc3b523be16，结果SHA=973c740e20cf0d17b33c4e9e662c8758b44815e6a7d7e7bf45e66a124087f50d

- bisect，16.2529296875，feasible，原始状态{'A': 'infeasible', 'C': 'optimal', 'D': 'rejected'}，run_id=4317dec289c94b89b1d8818a3078dd12，结果SHA=cc98198b2fda65977177cb51b3701a782df139b116c2780dbb648024aabe5b88

- bisect，16.24658203125，infeasible，原始状态{'A': 'infeasible', 'C': 'infeasible', 'D': 'rejected'}，run_id=ebee464076224d2a8ddc73028dfa0587，结果SHA=90cb0674249d69ad59cc36419095e48cc57f282242ea207f5a8bb1f9ab0bb379

## 资源与来源

求解适配器调用：102；总耗时：0.667秒；限制：{'single_solve_seconds': 3.0, 'max_solver_calls': 128, 'total_seconds': 60.0}。

调用数统计现有求解适配器（含预检查），容量适配器内部可包含LP/MILP两阶段；时间预算为协作式，构模/校验/文件写出可能带来少量超时开销，耗时如实记录。

来源：[{"source_id": "demo-series", "name": "合成演示数据：电热负荷与光伏", "region": "虚构园区（未知真实地区）", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"}, "category": "synthetic", "processing": ["NumPy default_rng 固定随机种子 42", "电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零", "反事实验收合成负荷：常规电功率恒10kW，热功率恒20kW_th；原168小时随机日型未拼接或年化；光伏沿用固定种子逐时合成"], "conditions": "仅用于功能演示，非实测，不能直接用于工程决策", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-market", "name": "合成演示数据：价格与排放因子假设", "region": "未知", "time_range": "2025-01-06T00:00:00+08:00 至 2025-01-07T00:00:00+08:00（末端不含）", "units": {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"}, "category": "synthetic", "processing": ["预设峰谷电价、固定燃气价格和排放因子"], "conditions": "全部为演示假设，不代表当地现行价格或排放因子", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-equipment", "name": "合成演示数据：设备与新建成本假设", "region": "未知", "time_range": "未知", "units": {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"}, "category": "synthetic", "processing": ["读取 demo_config.json"], "conditions": "演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-conditions", "name": "合成演示数据：项目条件", "region": "未知", "time_range": "未知", "units": {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"}, "category": "synthetic", "processing": ["读取 demo_config.json", "研究假设：预算60000元，购电12kW，排放上限按hours*230/24 kgCO2e；只统计实际输入期"], "conditions": "预算、场地和接入功率均为演示假设", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}, {"source_id": "demo-candidates", "name": "合成演示数据：有限候选容量", "region": "未知", "time_range": "未知", "units": {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"}, "category": "synthetic", "processing": ["读取 demo_config.json 的四个明确容量组合", "研究假设：三个固定候选A(锅炉20)、C(热泵20)、D(光伏50/储能20kW150kWh/热泵20)；容量不随约束放宽而改变"], "conditions": "不代表所有可能配置；辅助锅炉不构成故障备用保证", "url": null, "version": "未知", "artifacts": [], "parent_source_ids": []}]

数据可为合成或混合研究情景，以上沿用原任务口径；不年化短时结果，不含设备隐含排放，不构成工程投资决定或理论原创性声明。
