# 数据字典与统一输入约定

本表解释 v0.1 的字段、单位和边界。完整机器可读定义见 [`energy_agent/schemas.py`](../energy_agent/schemas.py)；Pydantic 模型禁止额外字段与非有限数值。未知来源信息明确记为“未知”，不猜测补齐。任务 JSON 使用 `TaskRequest`；只有通过信息完整性与质量检查后才进入 `ProjectTask`。

## 任务与项目条件

| 数据 | 单位 / 类型 | 说明 |
| --- | --- | --- |
| `project_name` 项目名称 | 文本 | 被评估的建筑或园区；单节点聚合 |
| `version` 任务版本 | 正整数 | 条件变更后递增；与独立 run_id 一起追溯 |
| run_id | 标识符 | 每次实际运行唯一，不作为可复现数值的一部分 |
| `constraints.budget_yuan` | 元 | 必要条件，约束初始新建投资；不能代替运行费上限 |
| `constraints.emission_limit_kg` | kgCO2e / 可空 | 约束输入评估期的运行排放；空值表示未设置该约束 |
| `constraints.pv_limit_kw` | kW | 可安装光伏额定电功率上限；不在本版进行面积和朝向建模 |
| `constraints.grid_limit_kw` | kW | 每个时间区间的外部电网购电功率上限 |
| `TaskPatch.demand_scale` | 无量纲倍数，(0, 100] | 相对当前任务对电热负荷显式缩放，记录处理及新版本 |
| `unsupported_demands` | 文本列表 | 包括供冷、管网与故障备用等；存在时拒绝运行并明确提示 |

任务还包括 `data`（时序）、`devices`（设备参数）、`candidates`（1 至 32 个容量候选）、`sources`（来源目录）、`demo`（演示标记）及 `parent_run_id`（前一版本运行）。`TaskPatch` 支持预算、排放上限、负荷比例、购电及光伏场地上限变更；`clear_emission_limit=true` 可显式取消排放上限。

非演示任务缺少预算、负荷或关键设备参数时，应返回“待补信息”及字段、原因等结构化待补项。演示模式可以显式加载一套完整预设，界面与报告持续标注“合成演示数据”。

## 时序

| 数据 | 单位 | 校验与解释 |
| --- | --- | --- |
| `timestamps` | 含时区的日期时间列表 | 时间区间起点，递增、唯一、等间隔；所有时序对齐 |
| `step_hours` | 小时 | 正数，须与时间戳间隔一致；功率乘步长得到区间能量 |
| `electric_load_kw` | kW | 有限且非负；不含优化后另行计算的热泵耗电 |
| `heat_load_kw_th` | kW_th | 有限且非负，必须逐区间满足 |
| `pv_per_kw` | kW/kW，数值无量纲 | [0, 1]；乘以光伏额定功率得到可用出力 |
| `electricity_price` | 元/kWh | 购电的演示/用户输入价格；本版不支持售电 |
| `gas_price` | 元/kWh_LHV | 燃料低位热值口径价格，不能直接填元/m³ |
| `grid_emission_factor` | kgCO2e/kWh | 购电运行排放因子 |
| `gas_emission_factor` | kgCO2e/kWh_LHV | 燃料运行排放因子；不能与单位热量排放因子混用 |

`TimeSeriesData.units` 将上述七个数值列映射到对应的精确单位字符串；`source_ids` 将每列映射到 `Source.source_id`。JSON 中所有列均为列表，并与 `timestamps` 等长。

时序数量由数据确定，模型不固定为 168。所有序列长度一致，禁止缺失值、无穷值和静默补零。导入统一格式时校验单位标识，不推断用户给定数字的单位。负价格等未支持边界应在输入校验时显式反馈。

统一格式适配器仅处理本项目文档与代码定义的格式。四个拟接入外部数据源的专用格式尚未实现，参见 [数据来源清单](data_sources.md)。

### 统一 CSV 接口

`energy_agent.data.load_csv(path, metadata)` 读取且只读取以下八列，列顺序不限，不允许额外列：

```csv
timestamp,electric_load_kw,heat_load_kw_th,pv_per_kw,electricity_price,gas_price,grid_emission_factor,gas_emission_factor
2025-01-06T00:00:00+08:00,55,70,0,0.38,0.32,0.55,0.202
```

此行仅为格式示例，数值仍为演示假设；一行不代表完整评估算例。CSV 中时间列名是单数 `timestamp`，返回模型中是列表 `timestamps`。

`metadata` 是 Python 字典，包含 `step_hours`、`units` 和 `source_ids`。下面展示加载操作，来源 ID 需在完整任务的 `sources` 目录另行登记：

```python
from energy_agent.data import load_csv
from energy_agent.schemas import SERIES_UNITS

data = load_csv("input.csv", {
    "step_hours": 1.0,
    "units": dict(SERIES_UNITS),
    "source_ids": {column: "my-verified-source" for column in SERIES_UNITS},
})
```

只有实际确认文件单位与 `SERIES_UNITS` 相符后才可这样声明。不同列也可以使用不同来源 ID。适配器不自动换算单位，不填补缺失，不重采样；任何预处理应在导入前完成并写入来源的 `processing`。额外需求列（例如供冷）不会被静默丢弃，而会作为未支持列报错。

## 设备、成本与候选

| 数据 | 单位 / 范围 | 说明 |
| --- | --- | --- |
| `Candidate.pv_kw` | kW | 非负额定电功率，受场地上限限制 |
| `Candidate.battery_power_kw` | kW | 非负最大充/放电功率，与能量独立记录 |
| `Candidate.battery_energy_kwh` | kWh | 非负；与电池功率必须同时为零或同时为正 |
| `Candidate.hp_kw_th` | kW_th | 非负最大供热功率；电输入等于供热/COP |
| `Candidate.boiler_kw_th` | kW_th | 非负最大供热功率；燃料输入等于供热/效率 |
| `devices.hp_cop` | 无量纲，[1, 10] | 固定演示系数；未建模气温、部分负荷或化霜影响 |
| `devices.boiler_efficiency` | (0, 1] | 热量输出与燃料 LHV 能量输入之比 |
| `devices.charge_efficiency` / `discharge_efficiency` | 各自 (0, 1] | 按状态方程分别作用，不能只填往返效率而不说明拆分 |
| `soc_min_fraction` / `soc_max_fraction` / `soc_initial_fraction` | [0, 1] | `devices` 内的比例；最小 ≤ 初始 ≤ 最大；最终等于初始 |
| `pv_cost_per_kw` / `battery_power_cost_per_kw` | 元/kW | `devices` 内的光伏、电池功率单位造价 |
| `battery_cost_per_kwh` | 元/kWh | `devices` 内的电池能量单位造价 |
| `hp_cost_per_kw_th` / `boiler_cost_per_kw_th` | 元/kW_th | `devices` 内的热泵、锅炉热功率单位造价 |
| `devices.installation_fraction` | 非负无量纲比例 | 安装费 / 设备购置费 |
| `devices.grid_connection_cost_yuan` | 元 | 各新建方案统一计入的电网接入费 |
| `Candidate.candidate_id` / `name` | 文本 | 唯一标识只含字母、数字、下划线或连字符，1 至 40 字符；名称可中文 |
| `source_id` | 来源标识 | 设备参数、约束和每个候选都分别指向来源目录 |

所有方案采用同一新建口径。弃用“既有锅炉免费、其它设备新购”的混合比较方式，除非未来明确实现既有资产场景。

演示预设位于 [`energy_agent/demo_config.json`](../energy_agent/demo_config.json)，定义四个容量组合、设备参数和项目约束；实际候选按配置生成。用户也可在完整任务 JSON 中提供自己的候选列表，最多 32 个，不能把运行比较结果写死在配置里。

## 逐时运行结果

| 数据 | 单位 | 解释 |
| --- | --- | --- |
| `points[].grid_kw` | kW | 非负且不超过购电上限 |
| `points[].pv_used_kw` / `curtailment_kw` | kW | 二者相加等于光伏可用功率 |
| `points[].charge_kw` / `discharge_kw` | kW | 非负、受功率限制且同一区间互斥 |
| `soc_kwh` | kWh 列表 | N+1 个边界状态，E_t 为区间 t 的起点；E_N = E_0 |
| `charge_mode` | 二进制列表 | N 个值，1 允许充电，0 允许放电；无运行可两者均为零 |
| `points[].hp_heat_kw_th` / `boiler_heat_kw_th` | kW_th | 二者相加等于热需求 |
| `points[].hp_electric_kw` | kW | 热泵供热 / COP，必须计入电力平衡 |
| `points[].gas_kw_lhv` | kW_LHV | 锅炉供热 / 锅炉效率；积分后为燃气用量 |

时序 CSV 的每行代表一个区间；若输出区间起点与终点 SOC，两列分别表示 E_t 与 E_(t+1)，不能误将 N 个区间的功率与 N+1 个边界状态直接对齐。

## 指标、校验与日志

| 数据 | 单位 / 类型 | 解释 |
| --- | --- | --- |
| `investment_yuan` | 元 | 设备容量与成本假设计算的全新设备投资 |
| `operating_cost_yuan` | 元 | 购电费与燃气费之和，仅对应输入时段 |
| `emissions_kg` | kgCO2e | 购电和燃气运行排放，非全生命周期排放 |
| `grid_kwh` / `gas_kwh_lhv` / `curtailed_pv_kwh` | kWh / kWh_LHV / kWh | 对功率按 Δt 求和 |
| `electric_load_kwh` / `heat_load_kwh_th` | kWh / kWh_th | 评估期常规电负荷与热负荷总量 |
| `period_hours` | 小时 | 区间数乘以步长 |
| `supply_satisfied` | 布尔 | 来自独立电热平衡检查；无解时 `metrics` 为空 |
| `checks` | 结构化结果列表 | 检查名、`passed`、`max_violation`、`tolerance` 和 `detail` |
| `dispatch.status` | 枚举 | `optimal`、`feasible_limit`、`no_solution_limit`、`infeasible`、`rejected`、`error`、`invalid` |
| `dispatch.solve_seconds` | 秒 | 实测墙钟耗时，不作为复现一致性的判断项 |
| `dispatch.mip_gap` | 无量纲 / 可空 | 求解器可提供时记录；未知不设成零 |
| `ranked_ids` / `recommended_id` | 候选 ID 列表 / 可空 ID | 仅比较通过校验的候选；按评估期运行费排序 |
| `tool_calls` | `ToolCall` 列表 | `run_id`、`input_version`、`tool_name`、`status`、`seconds`、`summary`、`source_ids`、`result_file` |
| `changes` / `previous_run_id` | 结构化记录 / 可空 ID | 变更字段、前后任务版本及实际重算指标变化 |

JSON 是完整可追溯结果；CSV 便于比较与绘图；Markdown 报告描述任务、推荐依据、不可行方案、来源和适用范围。缺少结果时保留空值与状态，不能用 0 替代未求得的费用、排放或缺供量。

## 来源记录

`Source` 包含 `source_id`、`name`、`region`、`time_range`、`units`、`category`、`processing` 和 `conditions`。`category` 可为 `measured`（实测）、`simulated`（仿真）、`synthetic`（合成）、`user`（用户输入）或 `unknown`。地区、时间范围和使用条件的缺省文字为“未知”；未知类别为 `unknown`。处理记录说明操作及影响区间，尤其是负荷缩放或其它数据转换；本版不默认插补缺失数据。

运行状态记录在 `state` 和 `states` 中，使用明确的中文状态枚举。`Issue.kind` 为 `missing`、`invalid` 或 `unsupported`，配合 `field` 与 `message` 返回结构化待补项或问题。


## v0.2兼容扩展

- `TaskRequest.assessment_mode`：默认`electric_heat`保留旧流程；`electric_only`必须提供`case_context`、零热占位且候选热泵/锅炉容量均为0。
- `case_context`：计量边界、排除项、时间约定、投资范围、位置精度、质量摘要、能量核对、待核实事项与导入文件位置。零热值不代表无供热需求或已保障供热。
- `emission_species`：`CO2e`（兼容默认）或`CO2`；`units`中的因子单位必须同步为`kgCO2e/kWh`或`kgCO2/kWh`，气体基准同理，报告/界面/无解说明保留物质口径。`emissions_kg`与排放约束均按此物质计kg，不做CO2↔CO2e替换。
- `Source`新增`url`、`version`、`artifacts`、`parent_source_ids`；类别新增`estimated`（模型/资源估计）与`assumption`（人为假设），保持原有枚举。`Artifact`保存下载URL、文件名、SHA-256、获取时间、档案成员路径、容器SHA、发布方校验值及实际核实的许可标识。用户本地文件获取时间可空，不假装网络下载。
- `MeterSelection`：建筑、Q/W类别、明确的区间起/止假设、类别合计与时区确认。`data_kind=artificial_fixture`将人工样本标为合成，不冒充外部实测。
- `IntervalContract`：`power_kw`区间平均功率按时长积分，`interval_kwh`逐间隔电量求和，`cumulative_kwh`相邻边界读数做差；累计复位拒绝。不支持隐含上采样，降采样只接收完整且对齐的目标区间。原时区声明后统一到Asia/Shanghai。
- `QualityReport`：记录数、起止、观测/期望步长、缺失、重复、非法时间、缺失/非有限/负值、跳变与带时间示例的问题；整份所选建筑/测点与窗口分别报告。跳变阈值是审查规则，不是自动故障判断，不自动填补、删点。
- `EnergyAudit`：转换前后kWh、差值、容差、声明数值分辨率、源舍入不确定性上界及解释。输入分辨率不是已核实的仪表精度；同一输入的无舍入转换只允许浮点误差。

逐时电价CSV只支持`timestamp,yuan_per_kwh`两列，严格对齐全部负荷小时，拒绝重复、负值和缺失。时段价格表必须恰好覆盖24小时，无重叠或空档；只核算按电量收费，其他收费不默认为0已核实。

`load_csv(..., emission_species="CO2")`可读CO2口径的统一CSV；省略仍为旧版CO2e。NASA适配器只接受响应明确UTC与已支持单位的GHI、T2M、WS10M，拒绝fill值和缺失；小时Wh/m²除以1h成为平均W/m²，再经独立光伏模型得到kW/kW，不能直接当光伏出力。
