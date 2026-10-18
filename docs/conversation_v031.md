# v0.3.1：可接续的规划助手

本轮复用现有全年容量与逐时运行模型，没有另建优化器。模型只能提出注册操作与结构化修改，容量、费用、NPV、排放和差值继续来自确定性工具。普通CI、页面刷新、数据诊断和状态恢复不调用付费模型。

## 配置和真实接口状态

本轮云端四项配置均已收到，仅检查存在性，不输出变量值。LLM_API_KEY作为不透明绑定直接用于指定HTTPS服务；不检查sk前缀，不读取代理背后的真实密钥，不绕过代理。项目根`.env`仍按`override=False`加载，`.env.example`密钥为空，不修改Codex认证或全局配置。

**已实际完成10次请求，全部HTTP200，无HTTP/schema重试，达到本轮上限后未再调用。** 包括1次连接、5次结构化意图、4次当前结果引用解释。连接、澄清、15%接续、20%修改、不可行解释与经济参数修改均通过。真实验收与模拟测试分开，详见[v0.3.1证据](v031_validation.md)。历史v0.3的“0次、未验收”记录仅描述当时环境。

共享`RequestBudget`将每次尝试（含重试）计入最多10次，验收计数持久保存；不重置旧目录计数。401/403不盲重试，429/5xx有限重试，网络超时30秒，解析输出上限1400 token、解释2600 token（真实验收配置）。脱敏日志只记录必要服务、工具、时间、状态和token用量，不记录密钥、Authorization头或原始HTTP正文，不估算费用。

## 澄清与固定基准

`PendingDialog`保存原始请求、待补字段与原因、基准run_id/输入版本、完整基准快照、已确认条件、回答、生成代次和历史。模型收到原请求＋回答＋基准摘要和已独立核对的修改契约，不接收全年数组。

例：

1. 用户：“预算少一点，供热不变。”
2. 助手询问减少幅度，保存`budget`待补项，**不求解**。
3. 用户：“减少15%。”（通过answer入口，带原request_id及新的turn_id）
4. 系统基于原确认预算乘0.85，保留热负荷、时段及逐时足额供能规则，版本增加并重新优化、校验和解释。

回答不能作为无上下文的新指令：没有待接续请求、错误字段或已取消请求会被拒绝。重启后可恢复同一目录，待补状态的基准/结果快照使用目录内相对文件名；测试覆盖复制到新目录后的接续。历史报表导出路径仍按当次运行保存，跨机器迁移全部历史报表尚未验收。

`request_id`保护原请求，`turn_id`保护回答，`edit_id`保护回答修订。重复提交返回既有结果，不连续乘比例，也不重复调用模型。原子保存快照；同一请求还有跨进程非阻塞文件锁，正在处理的重复请求在调用模型前被拒绝，进程退出后OS释放锁。验收入口也有目录级锁。回答或修订已完成计算但解释失败时，同一ID重试只补解释；计算结果与回执分步保存之间中断，也从已保存结果恢复，不重复求解或增加版本。

取消只停止后续动作，不删除基准和历史结果。修改已有回答产生新的输入版本，仍基于固定原预算；例如15%改30%使用原预算×0.7。重新选择基准会保存原基准历史并要求显式接续，不自动求解。

## 通用修改契约

`ModificationContract`独立记录：基准、规范化的修改、前后值/单位/用户证据、明确保留项、其余保持项与待补项。模型提议必须与契约逐项一致，不能夹带取消排放上限、减少热负荷、改变时段或其他未请求修改；执行前后再检查保留条件。

支持有明确字段/单位的受控中文表达（不是任意自然语言保证）：

- 预算减少10%/15%/20%/30%等：乘1−比例；“降到原来的20%”：乘0.2，区别于减少20%乘0.8。支持削减/降低/下调等、不同语序和明确元/万元金额；“少一点”、无单位或矛盾值先澄清。
- 电负荷与热负荷分别缩放。保持供热时可单独改变电负荷，热数组与时段指纹仍必须相同。旧表单明确的“电热共同倍数”继续保留，不能与分别缩放混用。
- 折现率（%或0…1）、规划期（年）、各设备寿命（年）、年固定维护费率（设备含安装初投比例）和支持设备的按量变动维护单价。
- “项目额外年固定维护费”按元/年单列，在原设备比例维护费之外计费，年1…H每年一次，第0年不计；NPV与优化目标常数同步更新，不改变初始投资预算。缺少全年经济参数时不猜测。
- 电池“寿命”指能量/电芯部分；功率变换器寿命应明确说电池功率变换器/PCS。两部分原模型独立计费。
- 用户可明确保留供热、电负荷、时段、预算、排放上限、购电/场地上限、经济参数、折现率、规划期或设备寿命/维护费率。未请求的字段默认保持。

未知修改句不能因其他字段已识别就被忽略：它会成为独立待补项。用户可改述该项，或明确取消该项；其他已确认修改仍保留。负荷修改是人为研究情景，来源和报告会标记，不冒充原始实测；不会自动放宽购电或容量上界来制造可行性。

## 中文结果

默认摘要显示基准/新run_id、哪些条件改变/保持、可行性和最优性状态、容量变化、初投/NPV/年度运行排放变化、推荐依据与关键假设。数字、差值、单位、百分比格式均由程序从计算结果生成，不让用户读原始JSON理解结果；详细引用放折叠区。

模型解释仍须引用当前run_id及现有字段，每个金额/容量/排放值严格核对；旧run_id、错误值和未知字段被拒绝。无解只引用实际预检查或求解器证据；没有冲突诊断时不猜测唯一原因。超时有解与已证明最优分开。

## 命令行：Windows Conda / 云端

先在仓库根目录安装依赖并运行全年电热案例；RUN替换为命令输出的实际result.json路径。每个全年输入目录需新建，避免覆盖证据：

```powershell
conda activate regional-energy
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m energy_agent.cli annual-build --bundle examples/shanghai_2017 --heat --retain-flagged-jumps --output outputs/v031_heat --run --time-limit 60
python -m energy_agent.cli agent-chat --run RUN --text "预算少一点，供热不变。" --request-id budget-dialog-001 --output outputs/my_dialog
python -m energy_agent.cli agent-dialog --action status --request-id budget-dialog-001 --output outputs/my_dialog
python -m energy_agent.cli agent-dialog --action answer --request-id budget-dialog-001 --turn-id answer-001 --text "减少15%。" --output outputs/my_dialog
python -m energy_agent.cli agent-dialog --action edit --request-id budget-dialog-001 --turn-id answer-001 --edit-id edit-001 --text "减少30%。" --output outputs/my_dialog
python -m energy_agent.cli agent-dialog --action cancel --request-id budget-dialog-001 --output outputs/my_dialog
```

重选基准（取消后的请求不能复活，请在未取消的请求上执行）：

```powershell
python -m energy_agent.cli agent-dialog --action rebase --request-id budget-dialog-001 --run NEW_RUN --output outputs/my_dialog
python -m energy_agent.cli agent-dialog --action resume --request-id budget-dialog-001 --output outputs/my_dialog
```

本机先安全配置项目`.env`并重启Streamlit；不要在聊天或命令行传密钥。界面“全年规划与Agent”包含会话/请求恢复、待补回答、修改回答、取消和重选基准。保存会话ID与请求ID可在同一服务器恢复。云端命令使用`.venv/bin/python`，安装恢复为`bash scripts/setup.sh`。

独立真实验收（会调用付费服务，最多10次含重试，普通CI不运行；本轮云端额度已用完，不自动重跑）：

```powershell
python -m energy_agent.cli llm-acceptance --run RUN --output outputs/my_live_acceptance --time-limit 60
```

只读数据诊断（不调用模型）：

```powershell
python -m energy_agent.cli data-diagnose --task RUN --output outputs/peak_review
python -m streamlit run app.py
```

## Q数据可靠性

保留原文件与原值。诊断列出峰值、99分位数、第二大值、两个跳变与前后3个区间，给出当前购电限制、容量上界及峰值时段所需放电功率的必要条件；不把瞬时条件当SOC全年可行性证明。当前原Q峰值4907.06kW在2017-01-13 00:00，第二大898.55kW，购电上限5400kW。峰值影响无PV/储能基线的购电需求，也影响按峰值设置的候选容量范围；不等于优化必然选择上界。

未作替代值敏感性求解、未认定数据错误或校准。用户若修改负荷，诊断按当前输入及来源类别解释，不再声称它是原始实测。测点真实性、Time锚点、匿名楼宇位置和参数仍待核实。
