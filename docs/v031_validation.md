# v0.3.1 实际验证记录

2026-10-18，从远程最新main `caf97f5`创建`feat/v0.3.1-conversation-assistant`。工作区初始干净，无AGENTS.md。沿用项目Python3.12.14 `.venv`、固定依赖，没有新增第三方依赖；不改全局Python、Codex认证或模型配置。

## 真实 DeepSeek：10次，全部通过

四项配置仅确认存在，没有输出变量值、检查密钥前缀或读取真实密钥。通过既有代理/HTTPS绑定调用，无绕过。共享同一持久计数器，**10次HTTP200、0次HTTP/schema重试**，已达本轮上限，随后未自动调用。共1次connectivity_check、5次planning_intent、4次grounded_explanation。服务返回token用量在`v031_evidence/real_requests.json`，未核实费用，不推算金额。

|验收|结果|证据|
|---|---|---|
|最小连通|通过|真实工具响应ok，计入10次|
|原请求“预算少一点，供热不变”|通过|模型选择clarify，budget待补，未求解|
|回答“减少15%”接续|通过|基准预算×0.85，新版本、全年实际重算|
|当前结果解释|通过|当前run_id、字段和值逐项核对|
|重复回答|通过|返回相同run_id，额外API请求0次|
|减少20%、供热不变|通过|实际重算，与此前数值容差内复现|
|预算0且供热不变|通过|真实求解不可行，无虚构推荐/唯一原因|
|折现率/规划期/寿命/维护修改|通过|4%、25年、PV30年、PV年维护率2%、额外年固定维护1万元实际生效并重算|

真实日志与本地模拟分开。普通CI不运行真实验收；重跑`llm-acceptance`需用户显式调用，最多10次含重试，旧目录不会重置计数。实际证据见`real_acceptance.json`、`run_evidence.json`、`real_dialogue.md`。中文模板随后改为易读标签；对同一已核实运行重渲染摘要，不增加API请求，也不冒充新的模型回答。

## 真实多轮运行

基准run_id：`5a529fa3feba4cc099df2e7e545cdbb8`，v1，初始预算10000000元，20年/5%经济条件。输入仍是上海2017完整8760小时Q实测＋仿真供热，NASA估算PV，价格/排放/设备参数为假设，不是实测全楼改造。

用户：**预算少一点，供热不变。**

助手：**预算要减少多少？请说明减少百分比、降到原来比例，或明确金额（元/万元）。** 原请求、基准和待补字段已保存，未求解。

用户：**减少15%。**

新run_id：`1c7b3c1df00b4ca1a81f88046b902afd`，v2，父运行是上述基准；预算8500000元。热负荷、评估时段和逐时足额供热规则不变，实际8760小时求解optimal，间隙0，约9.41秒。初投8500000元，NPV30271904.8001元，年度运行排放1374782.5976kgCO2e。

相对基准：初投减少150万元，NPV增加553188.2841元，年度运行排放增加118941.4511kgCO2e。光伏1587.3041kW，电池343.67kW/2192.9868kWh，热泵27.9924kW_th、锅炉636.6666kW_th。没有通过降低热需求、换时段或缺供制造可行性。

其他实际新运行：

- 20%：`fc8d26e2ee0545aba908a62047a2eaa8`，预算800万元，NPV30531925.8908元，年度排放1417604.4579kgCO2e，optimal。
- 不可行：`8101a4e852514e97adcef244f4e917e6`，预算0；联合约束不可行，未做最小冲突集诊断，不指定唯一原因。
- 经济修改：`673a042320464a00847cd4046405600c`，NPV36174005.7410元，年度排放1253956.3411kgCO2e，optimal；完整现金流、参数与独立检查已保存。

所有结果保持原始数据和研究边界；运行排放不折现，不含设备隐含排放。无周数据年化或多年预测声明。

## 离线验证

基线126项重新通过。完整套件包含原测试和新增多轮恢复、单位/一般百分比、经济参数、保留条件、并发重复提交、真实外部峰值诊断及模拟UI服务测试。具体计数以`v031_evidence/test_output.txt`为准（最终套件158项，37.66秒）。

实际命令：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_conversation_v031.py tests/test_deepseek_agent.py tests/test_dialog_ui_v031.py
.venv/bin/python -m pip install -e . --no-deps --cache-dir data_cache/pip
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q energy_agent
.venv/bin/python -m energy_agent.cli data-diagnose --task outputs/v031_real/baseline/5a529fa3feba4cc099df2e7e545cdbb8/result.json --output outputs/v031_peak
.venv/bin/python -m energy_agent.cli agent-dialog --action status --request-id live-multiround --output outputs/v031_real
```

真实验收通过显式调用`run_live_acceptance`，复用首个连通请求计数，再执行整套流程；现已由相同`llm-acceptance` CLI暴露。没有以模拟回答替代真实响应。模拟测试使用Fake/MockTransport，真实本地优化仍实际执行。状态恢复测试覆盖目录复制、解释失败后不重复求解、回答修订不连续扣减、显式rebase和取消；错误数字/旧run_id等原测试保留。

## 峰值可靠性与限制

只读诊断确认原Q峰值4907.06kW在2017-01-13 00:00，第二大898.55kW、99分位853.85kW；两个相邻跳变及7个邻近时段已保存。当前购电上限5400kW足以覆盖该原电峰值；无PV/储能基线至少需覆盖峰值，夜间PV不能消除它。峰值也用于默认PV/储能容量范围的量级设置，因此异常风险会影响可行域；没有据此声称最优装机必然改变。

没有删点、改日期、插补、替代或覆盖原文件，没有进行替代值敏感性求解。真实性、回路关系、时间锚点仍未核实；数据来源、物理供热、场地、价格/排放等既有研究假设不因此变成工程依据。详细邻时表见peak_diagnostics.md/json。

未验证：Windows实际运行（已有Conda命令，但本轮环境Linux）、Windows文件锁分支、真实浏览器视觉/跨机器完整历史报表迁移；已用AppTest验证界面并在Linux核查锁与状态恢复；Streamlit实际启动健康接口HTTP200/ok，检查后已停止进程。接口凭据、服务模型后续变化不属于永久可用保证。未合并、未部署。
