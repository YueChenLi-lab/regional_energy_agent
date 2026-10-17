# 区域综合能源低碳规划评估 Agent · v0.2

可运行的单节点电热规划原型：根据负荷、预算、场地与运行排放约束，比较有限的光伏、储能、热泵、燃气锅炉组合。单个 Agent 编排确定性工具，SciPy/HiGHS 求解运行，独立算术检查复核结果，中文 Streamlit 界面与 CLI 共用同一流程。

**合成演示入口采用合成演示数据。** 价格、排放因子、成本与设备参数都是演示假设，不代表当地现行值。结果只覆盖输入的评估期，不年化，也不称为全生命周期零碳或所有容量组合的全局最优。


## v0.2 第一阶段：真实数据电侧评估

保留原有电热合成演示与模型适配器，新增独立的“外部数据导入（电侧）”入口。已实际读取Zenodo 6590976的`dataset_v2.zip`、核对发布MD5与SHA-256及CC BY 4.0；Q/W的`Record`是每小时kWh。**Q+W只称发布方计量类别合计，不声称全楼总电量**，重复测点与不明格式会被拒绝；Time起止约定未获发布方证明，需要显式确认假设。

真实168小时案例与NASA UTC资源、质量报告及原始校验值已随代码保存于[许可与离线案例](examples/shanghai_168h/README.md)。光伏由pvlib估算，非楼宇实测。价格、排放因子、设备成本、场地和时间锚点仍是假设，整体标为**实测与假设混合案例**。仅比较电网/光伏/储能；W若被选中保留为电负荷，不再推算热需求。供热模块显式停用，不代表供热需求不存在或已获保障。

无需网络即可重新解析原始子集、校验NASA资源、估算光伏并实际优化：

```bash
.venv/bin/python -m energy_agent.cli data-replay --output outputs/real_replay
.venv/bin/python -m energy_agent.cli data-replay --budget 0 --output outputs/real_budget0
```

自行下载、选择建筑/测点/窗口（联网必须显式启用；已缓存后去掉`--online`可重放）：

```bash
.venv/bin/python -m energy_agent.cli data-fetch --provider zenodo --online
.venv/bin/python -m energy_agent.cli data-import --provider zenodo --building test --meters Q,W --acknowledge-category-sum --timestamp-position start --acknowledge-time-assumption --start 2017-01-01 --hours 168 --parameters configs/electric_assumptions.json --with-solar --online --output outputs/my_shanghai --run
```

每次导入使用新的空结果目录，避免覆盖旧记录。省略预算时返回待补项，不默认假定用户预算；示例参数文件明确加载人工情景。支持`--records`本地原CSV、`--dataset reference --building <BuildingID>`、`--tariff-csv`逐时电价和带年份/费用范围的`--price-description`。详细格式、处理、许可及证据见[v0.2说明](docs/real_data.md)。

Windows Conda（已有`regional-energy`环境，Python 3.12）：

```powershell
conda activate regional-energy
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m pytest -q
python -m energy_agent.cli data-replay --output outputs/real_replay
python -m streamlit run app.py
```

云端继续使用项目`.venv`与`bash scripts/setup.sh`；新增依赖`pvlib==0.16.1`及其依赖已固定于锁文件。Windows命令是兼容性说明，本轮执行环境为Linux，未实际在Windows验收。

## 安装与启动

已实际验证 Python **3.12.14**。在项目目录使用独立虚拟环境，不需要数据库、外部数据或模型密钥：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m pytest -q
.venv/bin/python -m energy_agent.cli demo --output outputs/demo --task-out outputs/demo_task.json
.venv/bin/streamlit run app.py --server.headless true --browser.gatherUsageStats false
```

`requirements.lock.txt` 固定了本次实际安装的全部依赖版本；`pyproject.toml` 固定直接依赖。主要版本：Pydantic 2.14.1、NumPy 2.5.4、pandas 3.0.6、SciPy 1.18.1、Streamlit 1.66.0、pytest 9.1.1。

界面点击“加载合成演示案例”，修改条件后点击“启动评估 / 修改后重新评估”。可查看方案与失败原因、逐时电热曲线、电池状态、来源、约束检查和工具记录，下载 JSON、CSV 与 Markdown。

## 命令行和场景变更

```bash
# 固定种子42，默认168小时；统一数据接口不限定时长
.venv/bin/energy-agent demo --seed 42 --hours 168 --output outputs/demo

# 编辑完整任务 JSON 后重新计算，包含设备参数、来源和候选配置
.venv/bin/energy-agent run --task outputs/demo_task.json --output outputs/custom

# 替换 RUN_ID；读取已有运行，版本+1并实际重新求解
.venv/bin/energy-agent revise --run outputs/demo/RUN_ID/result.json --budget 50000 --output outputs/revised
.venv/bin/energy-agent revise --run outputs/demo/RUN_ID/result.json --demand-scale 1.2 --emission-limit 6000

# 业务上没有可行方案时，仍完成报告并如实标注
.venv/bin/energy-agent demo --budget 0 --output outputs/no-budget
.venv/bin/energy-agent demo --emission-limit 0 --output outputs/no-carbon
```

`--demand-scale` 相对于被修改任务，同时缩放电热需求；UI 显示相对于原始演示的倍数。`--clear-emission-limit` 取消排放约束；`--grid-limit` 和 `--pv-limit` 修改主要约束。`--time-limit` 为每个候选的求解秒数上限。CLI 成功完成评估（包括“无可行方案”）返回 0，待补信息返回 2，工具执行失败返回 1。

每次运行生成独立 `outputs/<分组>/<run_id>/`：

- `result.json`：输入版本、全部来源、候选、逐时结果、指标、校验、状态流转、工具日志与前后差异。
- `scenarios.csv`：所有候选的配置、投资、评估期费用/排放、能量、可行性与求解状态。
- `dispatch_A.csv` 等：逐时功率、燃气LHV输入功率、区间首末SOC、负荷及步长。
- `report.md`：任务、推荐、取舍、失败解释、假设、数据来源和限制。
- `tools/*.json`：每次工具的结果与输入摘要哈希；完整任务保存在 `result.json`。

`outputs/` 已忽略，不提交虚拟环境、运行产物或真实密钥。

## 模型与业务边界

配置在 [energy_agent/demo_config.json](energy_agent/demo_config.json)。默认四候选：A 电网＋锅炉，B 加光伏，C 光伏＋热泵＋辅助锅炉，D 再加储能。它们统一采用新建投资口径。辅助锅炉不代表故障备用保证。自定义任务可配置最多32个候选。

每个时间步满足电力与热量等式；热泵耗电计入电力平衡。电池以二进制变量禁止同时充放电，SOC 有上下限与效率，期末严格恢复期初；不设隐藏缺供变量。投资预算及光伏场地先筛选，运行模型施加购电上限与评估期排放约束。通过独立校验后按运行费排序，同时展示投资和排放。达到求解时限时区分“未找到解”与“已有解但未证明最优”，后者仍需校验才能参与比较。

不支持供冷、冷热管网、空间选址、故障备用、售电、绿证、碳抵消或设备隐含排放。`unsupported_demands` 非空会返回待处理项；未知字段也会被拒绝，不能静默丢弃。缺失预算、负荷或关键参数会返回结构化待补项。CSV 只支持已定义的统一格式，见[数据字典](docs/data_dictionary.md)，不自动填零或猜测单位。

## Agent 与可选模型

状态：接收任务 → 校验输入 → 待补信息 / 准备运行 → 生成候选 → 求解 → 独立校验 → 比较 → 报告。

注册工具：`validate_inputs`、`build_candidates`、`solve_dispatch`、`validate_solution`、`compare_scenarios`、`generate_report`，输入输出均经过 Pydantic 校验。模型只能提出经过 schema 校验的参数修改，不执行 Python/shell、不产生计算结果替代求解。

默认规则模式支持表单和预设，不宣称任意自然语言理解。可复制 `.env.example` 为 `.env` 并自行配置 `LLM_BASE_URL`、`LLM_MODEL`、`LLM_API_KEY`。适配器使用 OpenAI-compatible `chat/completions` 工具协议，只有在界面明确点击模型按钮或显式调用 `EnergyAgent.run_text` 时才请求模型；不自动使用付费服务。非法输出最多尝试3次，之后明确失败。只有本地模拟响应测试已验证，**尚未连接真实模型验收**。

## 代码与验证

| 模块 | 职责 |
| --- | --- |
| `schemas.py` / `data.py` | 单位、来源、数据质量、统一CSV、合成演示 |
| `planning.py` / `optimization.py` | 有限配置、投资、逐时MILP |
| `evaluation.py` | 独立物理校验、指标、排序 |
| `agent.py` / `llm.py` | 状态、工具注册、任务版本、可替换模型接口 |
| `reporting.py` / `ui.py` / `cli.py` | 报告与导出、中文界面、命令行 |

测试覆盖标准168小时闭环、预算全拒绝、供热不足、碳约束无解与绑定后的运行变化、半小时时步能量换算、电池互斥与终态、篡改结果的独立检出、固定种子复现、版本与实际重算、缺失/异常数据、无密钥UI和模型适配器。超时分类用模拟求解器返回状态验证；完整年度运行性能与真实模型未验收。

v0.2实际验证：**97 项测试通过**（原58项保留），包括真实捕获数据离线求解与中文导入界面；详见[v0.2验证记录](docs/v02_validation.md)。v0.1历史记录见[原验证记录](docs/validation.md)。可下载快照内包含[完整交付报告、JSON/CSV和命令日志](docs/delivery/README.md)。

进一步阅读：[数学模型](docs/model.md)、[数据字典](docs/data_dictionary.md)、[数据来源登记](docs/data_sources.md)、[后续路线](docs/roadmap.md)。EnergyDetective正式档案与NASA POWER同期资源已实际读取；瑞丽、NREL和Calliope仍仅登记。
