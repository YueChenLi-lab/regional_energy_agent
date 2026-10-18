# DeepSeek 与受限规划 Agent

应用复用 `energy_agent/llm.py`。项目根目录 `.env` 由CLI和app入口加载，`override=False`，不覆盖已有环境变量。`.env`被Git忽略，`.env.example`密钥为空。不从聊天复制真实密钥；在本机文件/环境设置中填写。密钥仅用于配置的模型服务请求头，不进入任务、优化、报告或模型上下文。不改Codex认证或全局模型配置。

```dotenv
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=
LLM_PROVIDER=deepseek
```

实际读取当前[Chat Completion官方协议](https://api-docs.deepseek.com/api/create-chat-completion/)：列有deepseek-flash/deepseek-v4-pro，`thinking.type=disabled`关闭思考后支持required/指定工具。DeepSeek配置发送这一开关、文档支持的temperature=0、指定单工具、显式max_tokens和stream=false；不发送文档未列的parallel_tool_calls，不使用Beta严格模式。模型名可配置，实际账号可用性仍需连通检查。通用OpenAI兼容配置保留其独立参数。

普通CI、页面刷新、表单与离线求解不调用模型。构造客户端也不联网。只有明确的连接测试、自然语言按钮或相应CLI调用。解析输出1000token、解释1600token，构造器可分别修改（1—4096）。超时30秒；schema最多3次尝试，429/500/502/503/504最多一次短退避，401/403立即失败。共享 `RequestBudget` 包括所有重试、最多10个实际请求；CLI验收文件记录可跨重启保留计数。UI会话也限10次。日志只保存提供商、模型、工具、UTC时间、状态、耗时与服务返回token用量；不保存提示词、响应正文、密钥或请求头，不估算未核实费用。

## 可用工具与确认任务

单个EnergyAgent仍负责validate_inputs、build_candidates、solve_dispatch/solve_capacity、validate_solution、compare_scenarios、generate_report。AgentSession只在同一编排器周围管理已确认任务、请求回执与模型结构化提议。其封闭操作表为modify、clarify、evaluate、compare、sensitivity、report、explain；敏感性工具调用同一确定性求解和独立检查。没有Shell、任意Python或任意网络工具。

模型只收到版本/预算、边界、质量摘要、经济参数、时间起止和条数，以及当前结果标量引用；不发送全年数组、密钥、原文件或运行全日志。截断、空输出、未知工具、错误字段、未支持需求、非法数值不能应用。全寿命周期**经济**NPV已允许，设备隐含排放/生命周期碳仍明确不支持。

核心要求“预算减少20%，供热要求保持不变”必须给出budget_multiplier=0.8和preserve_heat=true，由代码计算当前已确认预算×0.8；禁止模型夹带负荷缩放、其他边界变化、取消排放约束。比较热负荷、时段、步长和足额供热规则的SHA指纹后才重算。电侧任务先返回供热边界澄清。父运行与输入版本保留，容量/投资/购能/NPV/排放差值来自实际新解。不可行时没有推荐，不编造精确原因。

每次提交必须带稳定request_id。回执在模型解析前保存基准，在求解后、解释前保存新运行文件；重试/重复提交会返回同一运行，不再次乘0.8，也不再次付费。若确实希望在新预算上再次减少20%，显式使用新的request_id。模型解释必须引用当前run_id，结论与可行性一致，每个数字与当前标量字段精确核对。中文显示由经核对字段渲染，错误数字、旧run_id被拒绝；不是仅检查JSON合法。

## 真实验收与离线模拟必须区分

离线测试使用MockTransport验证真实工具重算、重试限额、相对修改、重复提交、错误数字、旧运行引用、参数协议及脱敏。这证明本地适配器行为，**不能证明真实模型理解或账号接口已经通过**。

本轮云端没有LLM配置或项目.env，实际模型请求**0次**。用户在聊天提供的密钥未写入文件，也未据此调用。真实连通、完整电热修改解释、歧义澄清及不可行解释均未验收。用户在本机配置后可执行：

```powershell
# RUN为annual-build输出的实际电热result.json路径；OUT需为新的验收目录
python -m energy_agent.cli llm-check --output outputs/model_check
python -m energy_agent.cli llm-acceptance --run RUN --output outputs/deepseek_acceptance --time-limit 60
python -m energy_agent.cli agent-chat --run RUN --text "预算减少20%，供热要求保持不变。" --request-id budget20-001 --output outputs/chat
```

`llm-acceptance`自身最多10次（所有重试计入），依次完成最小连通、结构化修改、完整修改与重算解释、重复提交检查、歧义澄清、不可行任务解释。`llm-check`是另一个显式单请求命令；若需要把全部调用严格计入同一10次验收预算，**直接运行llm-acceptance即可，无需先运行llm-check**。查看acceptance.json和model_requests.json；遇到错误不会伪装通过。云端命令将python换为.venv/bin/python。
