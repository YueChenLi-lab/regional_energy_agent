# 两项决策扩展的可运行合成演示

2026-10-19，基于main `18abb3137f7f901aaf0ed572f19f1cba0bc4baeb` 增量开发。保留原始规划、Agent、MILP、来源与会话持久化接口。没有新增依赖，没有付费模型请求，也没有自动合并或部署。

## 页面使用

启动 `python -m streamlit run app.py`，进入“优化结果”。不需要先运行当前项目：

1. 展开“反事实约束修复”或“多情景稳健决策”。
2. 展开对应“可运行的24小时合成演示”，点击“加载…演示数据”。查看输入、容量、来源、处理范围与资源预算，可下载输入JSON。
3. 勾选“确认仅对上述合成数据执行所列搜索/情景，不采用到当前项目”。点击“确认并运行…合成演示”。
4. 查看真实求解的修复卡片或成本/后悔矩阵、独立校验及下载报告。

仅加载、切换页面或刷新不求解。同一演示请求重试恢复原始基准与工具回执；想重新计算时显式再次加载，生成新ID并重新确认。演示保存于 `ENERGY_AGENT_OUTPUT_DIR/decision_demos`（默认 `outputs/decision_demos`），与当前项目状态隔离。演示没有“采用”按钮；当前项目原有修复表单仍需单独授权和显式采用。两个演示各有独立合成基准，不是自动将修复路径写回后再做情景分析。

两个功能分别遵循既有开关 `ENERGY_AGENT_ENABLE_COUNTERFACTUAL`、`ENERGY_AGENT_ENABLE_REGRET`。关闭对应功能时，其演示入口也不显示。

## 截图报错的修复

- 空修复授权在创建Pydantic请求前给出“请至少选择一项明确允许修改的上限”，不调用注册表或求解器。不再暴露 `allowed_fields` 的原始英文校验错误。授权与锁定冲突同样先提示。
- 情景候选为空时先给出中文提示，不求解。
- 两个入口提交时动态创建工具表，显式重绑静态白名单中的两个工具及其输入/输出schema。核心Agent也使用同一注册函数。模拟旧工具表缺少 `evaluate_minimax_regret` 时，补齐后实际执行矩阵求解；未知工具仍被拒绝。
- 当前main源码原本已注册多情景工具，因此截图只能证明运行中的注册表缺项；无法仅凭截图确定公网进程的模块缓存或部署版本。代码没有绕过白名单，也没有将注册失败伪装成计算成功。若Cloud仍运行旧代码，应在合并、完成更新后人工核对提交版本，必要时使用原应用的Reboot；本轮未修改Cloud设置。

## 实际计算口径

两个输入均为24个逐小时区间，固定随机种子42。负荷为合成数据，价格、排放因子、设备成本和约束均是演示假设；不是当地现行值、实测楼宇或真实工程投资结论。不年化，不把短期购能费与全部投资相加称生命周期成本，未启用NPV。

反事实：固定电负荷10kW、热负荷20kW_th，预算60000元、运行排放上限230kgCO2e、购电上限12kW。三个候选及全部服务输入保持，每次只放宽一个上限。基准独立运行最多3次、每次3秒；之后工具复核/搜索最多128次、每次3秒、共享60秒。已确认不可行与可行的边界夹逼才称达到精度，不把未知当不可行。三条路径互为替代，不代表三个条件必须一起改，也不证明唯一不可行原因。

| 路径 | 已发现可行上界 | 调整量 | 指定精度 | 独立校验 |
|---|---:|---:|---:|---|
| 初始预算 | 401191.40625 元 | +341191.40625 元 | 1000 元 | 通过 |
| 运行排放上限 | 239.7412109375 kgCO2e | +9.7412109375 kgCO2e | 0.05 kgCO2e | 通过 |
| 购电功率上限 | 16.2529296875 kW | +4.2529296875 kW | 0.01 kW | 通过 |

三条最终求解均为optimal、gap=0；均达到指定边界精度。预算上限是边界搜索近似值，不等于精确设备投资：对应配置投资401000元。基准run_id和完整成本、容量、排放详见[实际报告](decision_demo_evidence/summary.md)。本次工具102次调用、0.667秒，基准另外3次；这是本次环境耗时，不是对Cloud的性能保证。

多情景：A/B/C三个固定配置 × 基准、购电价格×1.2、燃气价格×1.2、光伏出力×0.8。逐时运行可适应，热负荷、时段、容量、预算及其余约束保持。比较24小时购能费；投资单列。12/12单元独立校验通过，状态certified（仅这个有限矩阵），推荐C；A/B/C最坏后悔分别约903.69/378.22/0元。推荐与基准最低成本相同如实保留，不人为制造反转。工具12次调用、0.152秒，基准另外3次。

## 复现

Windows：

```powershell
conda activate regional-energy
git fetch origin
git switch fix/decision-extension-demos
python -m pip install -e . --no-deps
python -m streamlit run app.py
python scripts/run_decision_demos.py --output "outputs/决策演示 新运行"
python -m pytest -q tests/test_decision_demos.py
```

云端使用 `.venv/bin/python` 替换上述 `python`。归档命令（目录必须新建或为空，不覆盖旧证据）：

```bash
.venv/bin/python scripts/run_decision_demos.py --output outputs/decision_demo_validation --evidence docs/decision_demo_evidence
```

仓库已包含本次上述命令的输出；再次执行请换两个新目录。`--evidence`只收集该次运行的JSON/CSV/Markdown，压缩逐时见证，并写SHA256清单，不收集环境、密钥、虚拟环境或锁文件。

## 验证记录

- 最终全量命令：`.venv/bin/python -m pytest -q --junitxml=outputs/decision_demo_final_tests.xml`，**373 passed in 91.22s**，退出码0；原365项保留，新增8项。完整输出保存在 `decision_demo_evidence/pytest_output.txt`。定向测试最终8项通过；`pip check`通过；构建wheel并逐字节核对3个新增运行模块及CSS，见 `package_check.json`。本地是Linux，Windows CI结果单独见本PR的Checks，不等同于Windows真实浏览器验收。

- 新测试覆盖：空授权/空候选不求解；旧注册表兼容后真实求解；两种实际演示；跨会话同ID回执恢复；当前任务、供热和输入保持；显式确认；刷新不求解；重新加载撤回旧授权；归档所有文件及最终见证SHA。网络被测试夹具禁止。
- 真实Chromium桌面1440×1000、手机390×844均通过加载→确认→实际求解。截图在[证据目录](decision_demo_evidence/README.md)，手机表格内部横向滚动、页面无整体溢出；没有采用按钮。未进行Windows真实浏览器验收。
- 公网此前在本任务中被代理403阻止访问，无法确认Streamlit Cloud已更新。代码推送和PR不是部署成功证据；请合并后在原公网按上述步骤核实。本轮真实模型请求0次，未进行真实DeepSeek验收。
