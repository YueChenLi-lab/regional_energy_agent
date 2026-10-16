## 交付目的

将v0.1实际测试证据与168小时演示完整产物保存到版本控制，提供可离线下载、审查与复算的交付。不扩展业务功能，也不合并本PR。

源码、锁定依赖、58项测试、CLI及中文Streamlit界面沿用已合并的实现。此次保存完整JSON、Markdown、方案和逐时CSV、工具调用记录、可复算任务、实际命令日志及SHA-256清单；修正随机扰动说明和Markdown小数容差显示。

## 实际验证

- `.venv/bin/python -m pip check`：无依赖冲突。
- `.venv/bin/python -m pytest -q`：**58 passed**。
- `.venv/bin/python -m energy_agent.cli demo --seed 42 --hours 168 --output docs/delivery/demo_168h --task-out docs/delivery/demo_task.json`：4候选全部optimal、独立校验通过、所有导出和工具文件存在。
- 完整输出见`docs/delivery/verification.txt`；报告见`docs/delivery/demo_168h/24bcc4660cf643de918a54cec0e0405a/report.md`。

全部为合成演示数据。D的168小时运行费最低（7002.16元），C投资和排放均低于D；预算约束初始投资，不年化、不混同生命周期成本或全生命周期零碳，不宣称全部容量配置中的全局最优。

## 复现

```bash
bash scripts/setup.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m energy_agent.cli run --task docs/delivery/demo_task.json --output outputs/reproduced
.venv/bin/streamlit run app.py --server.headless true
sha256sum -c docs/delivery/manifest.sha256
```

## 未验证事项

真实LLM接口未连接；通过的是模型适配器本地模拟响应测试。外部真实数据、完整年度优化性能、真实超时、真实浏览器视觉验收及新云任务恢复未验收。原实现的GitHub CI已通过；当前提交CI状态以本PR的Checks为准。

ZIP下载使用本分支/提交快照，包含完整源码而非仅此次PR增量；不含虚拟环境、真实密钥或登录凭据。完整初始版本差异可从初始化提交`76a1dfd`比较到本PR头提交获得。
