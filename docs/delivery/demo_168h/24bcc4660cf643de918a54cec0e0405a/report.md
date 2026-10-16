# 区域综合能源低碳规划评估报告

项目：区域综合能源低碳规划评估 Agent — 合成演示园区

运行 ID：`24bcc4660cf643de918a54cec0e0405a`；输入版本：1；状态：完成。

**合成演示数据**：负荷、资源、价格、排放因子和设备费用为演示假设，不代表当地现行参数。

## 任务条件

168 个区间，时间步长 1 h，评估时长 168 h。区间开始时间：2025-01-06T00:00:00+08:00 至 2025-01-12T23:00:00+08:00；最后区间结束时间为最后开始时间加一个时间步。仅报告该时段结果。

| 条件 | 数值 | 单位 |
| --- | --- | --- |
| 初始投资预算 | 1,200,000.0000 | 元 |
| 评估期排放上限 | 不限制 | kgCO2e |
| 电网购电功率上限 | 180.0000 | kW |
| 光伏场地上限 | 180.0000 | kW |

项目条件来源：`demo-conditions`。

求解设置：每个候选时限 30 秒；相对最优性间隙容差 1e-06。

## 候选配置与结果

| 方案 | 光伏 kW | 电池 kW / kWh | 热泵 kW_th | 锅炉 kW_th | 投资 元 | 运行费 元 | 排放 kgCO2e | 求解状态 | 约束通过 | 容量来源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D 光伏＋储能＋热泵＋辅助燃气锅炉 | 120.0000 | 40 / 100 | 100.0000 | 60.0000 | 800,050.0000 | 7,002.1648 | 5,861.0019 | 已证明最优（该候选运行） | 是 | demo-candidates |
| C 光伏＋热泵＋辅助燃气锅炉 | 120.0000 | 0 / 0 | 100.0000 | 60.0000 | 675,850.0000 | 7,381.5913 | 5,833.9306 | 已证明最优（该候选运行） | 是 | demo-candidates |
| B 光伏＋电网＋燃气锅炉 | 120.0000 | 0 / 0 | 0.0000 | 120.0000 | 486,100.0000 | 9,235.2736 | 6,461.7402 | 已证明最优（该候选运行） | 是 | demo-candidates |
| A 电网＋燃气锅炉 | 0.0000 | 0 / 0 | 0.0000 | 120.0000 | 44,500.0000 | 12,889.7611 | 9,195.6884 | 已证明最优（该候选运行） | 是 | demo-candidates |

| 方案 | 购电 kWh | 燃气 kWh_LHV | 弃光 kWh | 常规用电 kWh | 供热 kWh_th | 供能满足 | 求解秒数 | 相对最优性间隙 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D | 9,892.9019 | 2,078.7420 | 0.0000 | 11,917.1361 | 11,768.0059 | 是 | 0.0638 | 1.039e-15 |
| C | 9,843.6813 | 2,078.7420 | 9.1448 | 11,917.1361 | 11,768.0059 | 是 | 0.0103 | 0.0000 |
| B | 6,946.3212 | 13,075.5621 | 204.6402 | 11,917.1361 | 11,768.0059 | 是 | 0.0077 | 0.0000 |
| A | 11,917.1361 | 13,075.5621 | 0.0000 | 11,917.1361 | 11,768.0059 | 是 | 0.0084 | 0.0000 |

## 比较与推荐

在本次评估的候选方案中，推荐 **D**。在本次评估的候选方案中，D 通过全部约束校验，按评估期运行费升序排名第一。初始投资与评估期排放单独展示；此结果不代表全部可能容量配置的全局最优。

先筛选预算、供能与排放等约束，再按本评估期运行费排序；投资与排放完整列出以展示取舍。若某候选仅取得可行解，则排序基于当前可行解，不能据此证明该候选运行最优。

## 不可行、未完成求解与独立检查

### D：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 1.421e-14 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 7.105e-15 | 1e-05 |  |
| boiler_efficiency | 是 | 7.105e-15 | 1e-05 |  |
| pv_allocation | 是 | 0.0000 | 1e-05 |  |
| nonnegative_flows | 是 | 0.0000 | 1e-05 |  |
| grid_limit | 是 | 0.0000 | 1e-05 |  |
| pv_availability | 是 | 0.0000 | 1e-05 |  |
| heat_pump_capacity | 是 | 0.0000 | 1e-05 |  |
| boiler_capacity | 是 | 0.0000 | 1e-05 |  |
| battery_charge_power | 是 | 0.0000 | 1e-05 |  |
| battery_discharge_power | 是 | 0.0000 | 1e-05 |  |
| soc_lower | 是 | 3.553e-15 | 1e-05 |  |
| soc_upper | 是 | 0.0000 | 1e-05 |  |
| soc_initial | 是 | 0.0000 | 1e-05 |  |
| soc_terminal | 是 | 0.0000 | 1e-05 | 期末必须恢复初始能量，不允许免费消耗初始储能 |
| soc_dynamics | 是 | 1.243e-14 | 1e-05 |  |
| binary_charge_mode | 是 | 4.324e-15 | 1e-05 |  |
| charge_mode_limit | 是 | 0.0000 | 1e-05 |  |
| discharge_mode_limit | 是 | 1.776e-14 | 1e-05 |  |
| no_simultaneous_charge_discharge | 是 | 0.0000 | 1e-05 |  |
| investment_budget | 是 | 0.0000 | 0.0001 |  |
| pv_site_limit | 是 | 0.0000 | 1e-05 |  |
| emission_limit | 是 | 0.0000 | 0.0001 | 未设置排放上限 |
| objective_recalculation | 是 | 9.095e-13 | 0.0001 |  |

### C：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 1.421e-14 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 7.105e-15 | 1e-05 |  |
| boiler_efficiency | 是 | 7.105e-15 | 1e-05 |  |
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

### B：已证明最优（该候选运行）

HiGHS 在所设容差内求得最优运行解

| 检查 | 通过 | 最大违反量 | 容差 | 说明 |
| --- | --- | --- | --- | --- |
| solver_has_solution | 是 | 0.0000 | 0.0000 | 求解状态：optimal |
| candidate_identity | 是 | 0.0000 | 0.0000 |  |
| result_dimensions | 是 | 0.0000 | 0.0000 | 逐时点=N，SOC=N+1，充放电模式=N |
| timestamps | 是 | 0.0000 | 0.0000 |  |
| objective_available | 是 | 0.0000 | 0.0000 |  |
| electric_balance | 是 | 1.421e-14 | 1e-05 |  |
| heat_balance | 是 | 0.0000 | 1e-05 |  |
| heat_pump_cop | 是 | 0.0000 | 1e-05 |  |
| boiler_efficiency | 是 | 7.105e-15 | 1e-05 |  |
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
| objective_recalculation | 是 | 1.819e-12 | 0.0001 |  |

### A：已证明最优（该候选运行）

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
| boiler_efficiency | 是 | 7.105e-15 | 1e-05 |  |
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

## 设备与新建项目投资假设

| 参数 | 值 | 单位 |
| --- | --- | --- |
| 光伏设备单价 | 3,200.0000 | 元/kW |
| 电池能量单价 | 900.0000 | 元/kWh |
| 电池功率单价 | 450.0000 | 元/kW |
| 热泵设备单价 | 1,800.0000 | 元/kW_th |
| 锅炉设备单价 | 250.0000 | 元/kW_th |
| 安装费/设备费 | 0.1500 | 无量纲 |
| 电网接入费用 | 10,000.0000 | 元 |
| 固定热泵 COP | 3.2000 | kWh_th/kWh |
| 锅炉效率 | 0.9000 | kWh_th/kWh_LHV |
| 充电效率 / 放电效率 | 0.95 / 0.95 | 无量纲 |
| SOC 下限 / 上限 / 初值 | 0.1 / 0.9 / 0.5 | 额定能量比例 |

设备参数与费用来源：`demo-equipment`。

初始投资 = 设备购置费合计 × (1 + 安装费比例) + 电网接入费。电网接入费对所有候选采用相同口径。

## 数据与参数来源

| 项目 | 记录 |
| --- | --- |
| source_id | demo-series |
| 名称 | 合成演示数据：电热负荷与光伏 |
| 地区 | 虚构园区（未知真实地区） |
| 时间范围 | 2025-01-06T00:00:00+08:00 至 2025-01-13T00:00:00+08:00（末端不含） |
| 类别 | synthetic |
| 单位 | {"electric_load_kw": "kW", "heat_load_kw_th": "kW_th", "pv_per_kw": "kW/kW"} |
| 处理记录 | NumPy default_rng 固定随机种子 42；电热负荷：解析日周期加正态随机扰动后非负裁剪；光伏：正弦包络乘有界均匀随机系数，夜间显式置零 |
| 使用条件 | 仅用于功能演示，非实测，不能直接用于工程决策 |

| 项目 | 记录 |
| --- | --- |
| source_id | demo-market |
| 名称 | 合成演示数据：价格与排放因子假设 |
| 地区 | 未知 |
| 时间范围 | 2025-01-06T00:00:00+08:00 至 2025-01-13T00:00:00+08:00（末端不含） |
| 类别 | synthetic |
| 单位 | {"electricity_price": "元/kWh", "gas_price": "元/kWh_LHV", "grid_emission_factor": "kgCO2e/kWh", "gas_emission_factor": "kgCO2e/kWh_LHV"} |
| 处理记录 | 预设峰谷电价、固定燃气价格和排放因子 |
| 使用条件 | 全部为演示假设，不代表当地现行价格或排放因子 |

| 项目 | 记录 |
| --- | --- |
| source_id | demo-equipment |
| 名称 | 合成演示数据：设备与新建成本假设 |
| 地区 | 未知 |
| 时间范围 | 未知 |
| 类别 | synthetic |
| 单位 | {"hp_cop": "kWh_th/kWh", "efficiency_and_soc": "1", "pv_cost_per_kw": "元/kW", "battery_cost_per_kwh": "元/kWh", "battery_power_cost_per_kw": "元/kW", "hp_cost_per_kw_th": "元/kW_th", "boiler_cost_per_kw_th": "元/kW_th", "installation_fraction": "1", "grid_connection_cost_yuan": "元"} |
| 处理记录 | 读取 demo_config.json |
| 使用条件 | 演示假设；统一新建投资；安装费为设备购置费的15%，接入费单列 |

| 项目 | 记录 |
| --- | --- |
| source_id | demo-conditions |
| 名称 | 合成演示数据：项目条件 |
| 地区 | 未知 |
| 时间范围 | 未知 |
| 类别 | synthetic |
| 单位 | {"budget_yuan": "元", "grid_limit_kw": "kW", "pv_limit_kw": "kW", "emission_limit_kg": "kgCO2e"} |
| 处理记录 | 读取 demo_config.json |
| 使用条件 | 预算、场地和接入功率均为演示假设 |

| 项目 | 记录 |
| --- | --- |
| source_id | demo-candidates |
| 名称 | 合成演示数据：有限候选容量 |
| 地区 | 未知 |
| 时间范围 | 未知 |
| 类别 | synthetic |
| 单位 | {"pv_kw": "kW", "battery_power_kw": "kW", "battery_energy_kwh": "kWh", "hp_kw_th": "kW_th", "boiler_kw_th": "kW_th"} |
| 处理记录 | 读取 demo_config.json 的四个明确容量组合 |
| 使用条件 | 不代表所有可能配置；辅助锅炉不构成故障备用保证 |

时序字段来源映射：

| 字段 | source_id | 单位 |
| --- | --- | --- |
| electric_load_kw | demo-series | kW |
| heat_load_kw_th | demo-series | kW_th |
| pv_per_kw | demo-series | kW/kW |
| electricity_price | demo-market | 元/kWh |
| gas_price | demo-market | 元/kWh_LHV |
| grid_emission_factor | demo-market | kgCO2e/kWh |
| gas_emission_factor | demo-market | kgCO2e/kWh_LHV |

## 模型假设、适用范围与尚未实现内容

- 区域内所有建筑合并为一个供能节点，仅建模常规用电和供热，要求每个时间区间足额供能。
- 光伏、电池、热泵和燃气锅炉按新建项目计投资；预算约束初始投资，运行费仅统计本评估期。
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
| validate_inputs | 1 | success | 0.0030 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/001_validate_inputs.json | validate_inputs 已执行并通过输入/输出 schema 校验 |
| build_candidates | 1 | success | 0.0006845 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/002_build_candidates.json | build_candidates 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0134 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/003_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0041 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/004_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0191 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/005_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0037 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/006_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0170 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/007_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0023 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/008_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| solve_dispatch | 1 | success | 0.0689 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/009_solve_dispatch.json | solve_dispatch 已执行并通过输入/输出 schema 校验 |
| validate_solution | 1 | success | 0.0060 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/010_validate_solution.json | validate_solution 已执行并通过输入/输出 schema 校验 |
| compare_scenarios | 1 | success | 0.0077 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/011_compare_scenarios.json | compare_scenarios 已执行并通过输入/输出 schema 校验 |
| generate_report | 1 | success | 0.0093 | docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/tools/012_generate_report.json | generate_report 已执行并通过输入/输出 schema 校验 |

结果文件：

- json: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/result.json`
- csv: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/scenarios.csv`
- markdown: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/report.md`
- dispatch_A: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/dispatch_A.csv`
- dispatch_B: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/dispatch_B.csv`
- dispatch_C: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/dispatch_C.csv`
- dispatch_D: `docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/dispatch_D.csv`
