# v0.4.0 · 反事实约束修复

“面向不可行规划任务的反事实约束修复机制：在保持供能服务与用户锁定条件的前提下，搜索可行性恢复所需的条件调整，形成可量化、可校验的替代决策路径。”

这是成熟优化思想在综合能源Agent中的机制设计与工程集成，不宣称理论原创性。算法在 `energy_agent/counterfactual.py`，不构造或重写MILP，继续调用既有 `solve_dispatch` / `solve_capacity`、EnergyAgent编排与独立 `validate_solution`。

## 输入和权限

`CounterfactualRequest` 必须提供 `task` 或已确认 `baseline` 之一，以及稳定 `request_id`、固定 `base_run_id`、输入版本和数据SHA-256。传Task时，base_run_id是调用方声明的输入锚点；真实基准复算run_id另存于baseline_verification，不把声明锚点伪装成实际已执行运行。传RunResult时核对其真实run_id/版本，且仍重新求解原任务，不信任一句“无解”或未经复核的旧状态。

`allowed_fields` 必须与 `ranges` 的键完全一致；每项有绝对上下界、精度、单位。只接受：

| 路径 | 单位 | 行为 |
| --- | --- | --- |
| `budget_yuan` | 元 | 仅提高初始投资上限，NPV目标不变 |
| `emission_limit_kg` | kgCO2或kgCO2e，严格匹配原任务 | 仅提高已有运行排放上限，未设置则拒绝此路径 |
| `grid_limit_kw` | kW | 仅提高购电功率上限，不等于已获接入许可，不估算额外增容工程费用 |

不接受万元冒充元、kWh冒充kW或CO2/CO2e互换。搜索下界不得低于原值，上界必须大于原值。为避免声明低于独立校验数值容差的精度，预算/排放精度至少0.001对应单位，购电功率至少0.0001kW。

`locked_conditions` 可锁定上述任一字段以及电/热负荷、时段、服务、设备、候选集、容量边界、经济参数、场地与来源；锁定字段和可修改字段冲突时立即拒绝。无论显式锁定清单如何，每个试探任务都完整比较其余全部业务输入。仅允许任务版本/父运行ID变化、选中约束变化和追加一条修改来源；原来源前缀、数据数组、时间戳、步长、服务边界、排放物质、价格/因子、设备、候选与经济假设保持。

电侧任务的零热数组仅代表未建模供热。含“供热”要求的电侧请求须先澄清，不能宣称供热保障保持或已验收。通过表单可在明确电侧边界下执行电侧修复。

## 可行性判据

| 原始求解与独立校验 | 搜索判据 |
| --- | --- |
| `optimal`且校验通过 | 已有可行见证；运行目标在当前模型/容差内已证明最优 |
| `feasible_limit`且校验通过 | 已有可行见证；最优性未证明，保存gap；可以作为可行上界 |
| 所有固定候选均`infeasible`，或容量问题`infeasible` | 在声明候选集/容量模型内确认不可行 |
| `rejected` | 默认是拒绝，不是无解。仅对固定候选独立重算投资超预算、PV超场地这两个必要条件；覆盖全部候选后才可形成候选集不可行证据，原始rejected状态仍保留 |
| `no_solution_limit`、调用预算中止 | 不确定，不是不可行 |
| 求解错误、未知拒绝、独立校验失败或未授权输入变化 | error/rejected，不能形成有效可行性边界 |

任何一个通过校验的固定候选足以证明存在可行解，不必所有候选都完成运行优化；但确认候选集不可行必须覆盖全部候选，没有缺失或错误。部分运行因预算终止时，已验证见证仍可输出，不能宣称未求解的其余方案都不可行或已找到全局最佳方案。

## 搜索与边界声明

1. 校验输入、权限、单位和绑定；在同一总预算内重新运行原任务。
2. 只有原任务被确认不可行，或显式设置 `explore_alternatives=True`，才进入路径搜索。原任务可行且允许区间包含原值时，无需修复，不伪造“追加量”。
3. 每条路径从同一个原任务派生 `version+1`，只改该上限，所有兄弟路径互为替代，不串联或叠加。
4. 从原值加允许跨度的四分之一（至少一个精度步长）开始，逐步扩大至允许上界；若允许下界大于原值，先实际求解该下界。
5. 模型可行集具有集合包含关系：放宽单个上界，原可行解仍满足新上界。此论证依赖已核对的固定候选/容量边界和其余输入不变，不依赖语言模型猜测。
6. 得到**确认不可行下界**和**独立校验可行上界**后，才二分。每次中点真实求解；不可行更新下界，可行更新上界。
7. 任一中点不确定或失败，立即停止该路径二分，不跨越它推断边界。可以保留之前的经校验上界，但 `boundary_precision_reached=False`。
8. 区间宽度不超过指定精度，才报告在现有模型、数值容差、指定范围与精度下找到可行边界。允许区间左端即经验证可行时，单独标为 `permitted_left_edge`；不声称找到了区间之外的真实阈值。
9. 最终见证再次调用独立校验；失败则清除建议值，不提供可采用路径。

基准不确定但显式授权探索时，可以找到可行调整；没有不可行下界就不宣称最小边界。未找到可行上界时返回“在当前范围内尚未找到经验证的修复方案”，附状态和证据；不能表述为此项目永远不可行，也不能归因于唯一约束。

条件调整最小化与运行目标优化是两件事：可行边界允许使用校验通过的feasible_limit见证，NPV仍必须标为当前可行解，不能声称NPV最优。固定候选修复只适用于声明的候选集，连续容量模式只适用于现有线性设备模型与边界。

## 资源、证据与幂等

每个请求具有单次适配器时限、总适配器调用上限和总时间预算。基准复核、所有路径与二分共享预算。每次调用前检查剩余资源，并把求解器时限缩短至 `min(single_solve_seconds, remaining_seconds)`；记录实际传入的时限和原始状态。调用数包含预检查返回的适配器调用；既有容量适配器内部可能执行LP/MILP两阶段，不把它说成只调用了一次HiGHS。

采用既有求解器协作式时限，不承诺进程级硬实时终止：构模、解提取、独立校验及序列化可能增加少量超时开销，报告实际耗时。耗尽预算后不再发起新求解；不会把预算耗尽当作不可行。

默认工具预算为单次5秒、总48次、总60秒；基础界面为单次3秒、总48次、总30秒，用户可明确修改；UI最多单次30秒/96次/总120秒。普通加载/刷新/标签切换只读，不触发搜索；全年任务另需显式资源确认，推荐CLI离线运行。设置 `ENERGY_AGENT_ENABLE_COUNTERFACTUAL=0` 可关闭新工具/采用入口，不影响原规划。

输出按request_id的SHA目录保存，包含原授权请求、原任务复核、全部试探状态/值/版本/指纹/时限/文件SHA、各自原RunResult及工具轨迹、最后独立校验、JSON与中文Markdown。文件锁复用 `storage.file_lock`（含Windows实现）。同ID同请求只读回执，不再次调用求解器；同ID换基准/权限/参数拒绝；中断后没有完整回执则不自动重跑，需新ID重新明确授权资源，不隐性重复消费预算。不要删除旧回执以绕过预算。

## Agent、对话与采用

注册工具名 `search_counterfactual_repairs`，输入输出经过Pydantic和白名单校验。容量工具改为在注册表构造时注册，方便局部预算封装；原求解函数与MILP文件不变。

本版优先使用独立工具/表单，**不改现有conversation状态机或自然语言修改语义**。可选问题入口仅支持文档中四个预设中文问句的离线路由（末尾标点可省略），给出路径建议/待补权限；不宣称任意自然语言理解。预算锁定提示不能被模型或表单范围夹带覆盖。未可靠识别的问题先澄清，不搜索；可清空文字改用完整明确的表单。

保持原会话request_id为 `parent_request_id`，另用稳定修复request_id绑定确认基准。现有LLM会话不会自动发起反事实搜索，本轮没有真实付费模型请求，也不将全年数组传给模型。后续模型只能提议同样的受限schema，不能代替实际搜索、数值或确认。

探索不更新 `annual_run/last_run/real_run`。只有“确认采用此路径”或CLI `--confirm` 才采用已经真实重算的 `version+1` 结果：核对当前基准、原授权清单、原结果SHA、路径轨迹、单字段保持关系并再次独立校验，另存采用回执。采用旧基准结果到新任务、伪造结果或同采用ID换路径均拒绝。重复采用不会继续加预算或增加版本。旧任务对象与基准文件不覆盖。

## 复现

Windows先 `conda activate regional-energy`，项目根目录执行；云端把 `python` 换为 `.venv/bin/python`：

```bash
# 新空目录；6/24/168小时真实小问题求解，无模型/网络请求
python scripts/run_counterfactual_cases.py --output outputs/my_repairs
# 显式追加8760小时上海Q＋仿真供热混合研究案例；非普通CI
python scripts/run_counterfactual_cases.py --output outputs/my_repairs_annual --annual
python -m streamlit run competition_app.py
python -m pytest -q tests/test_counterfactual.py tests/test_counterfactual_ui.py
```

生成的每个案例含Task、基准运行、CounterfactualRequest及报告，可重放已完成请求：

```bash
python -m energy_agent.cli counterfactual --request outputs/my_repairs/three_paths_24h/request.json
# 换输出根目录才是新的一次显式离线计算；不能覆盖旧回执
python -m energy_agent.cli counterfactual --request outputs/my_repairs/three_paths_24h/request.json --output outputs/another_repair
```

显式采用：从repair.json读取路径ID，BASE与RESULT使用同一案例文件，OUTPUT使用新文件：

```bash
python -m energy_agent.cli counterfactual-adopt --result RESULT --baseline BASE --path-id PATH --adoption-id adopt-001 --confirm --output outputs/adopted/result.json
```

实际结果和限制见 [counterfactual_validation.md](counterfactual_validation.md) 与 [v04_evidence/summary.md](v04_evidence/summary.md)。归档结果只作离线证据，采用操作需要本机的完整请求/运行文件；请先通过上面命令重放生成，不把原云端内部路径当作可下载文件。
