# DeepSeek 与受限规划 Agent

当前接口、可接续澄清、修改契约、中文结果和复现命令见[v0.3.1助手说明](conversation_v031.md)。本轮安全绑定已收到，**真实接口10次验收通过**；普通CI和页面刷新不调用模型。历史v0.3的0次记录保留在[原验证记录](v03_validation.md)，不代表当前状态。

继续复用`energy_agent/llm.py`：DeepSeek非思考模式发送`thinking.type=disabled`、文档支持的指定工具选择、temperature和明确max_tokens；不发送未列入其协议的parallel_tool_calls，不使用Beta strict。仍保留本地schema、白名单、当前run_id及数字引用检查。模型不执行Shell/Python/任意网络。

项目根`.env`或环境变量配置；入口`override=False`，密钥只作为不透明绑定发送指定HTTPS服务，不打印、不按前缀猜有效性、不写入源码。实际调用、限额和未完成项详见[v0.3.1验收证据](v031_validation.md)；真实与模拟测试分开。
