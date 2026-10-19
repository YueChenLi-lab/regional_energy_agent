# 两项决策扩展 · 新增合成演示的实际证据

这些结果由 `scripts/run_decision_demos.py` 重新计算，不是dev_preview虚构数据，也没有覆盖既有v0.4/v0.4.1/v0.5证据。

- [中文汇总](summary.md) / [机器汇总](summary.json)：实际run_id、状态、指标、调用次数、耗时。
- `repair_input.json` / `regret_input.json`：全部合成输入、来源、价格与设备假设。
- `repair_result.json` / `repair_report.md`：实际三路径搜索和独立校验。
- `regret_result.json` / `regret_matrix.csv` / `regret_report.md`：实际3×4矩阵及独立校验。
- `witnesses.zip`：上述CLI运行的全部生成JSON/CSV/Markdown，含基准、工具回执、各次调度及逐时结果。解压到新的目录以检查，不覆盖旧输出。JSON中路径保留执行时相对路径 `outputs/decision_demo_validation/`；ZIP内去掉这一前缀，未更改见证字节或哈希。
- `manifest.json`：归档文件与每个ZIP成员的SHA256。测试逐一核对，并核对最终修复/单元调度JSON的原始SHA。
- `repair_browser.png` / `regret_browser.png` / `regret_mobile.png`：真实浏览器另一次主动执行的演示，因此run_id与CLI不同；不是模型输出。`browser_checks.json`保存实际DOM、基准ID、矩阵单元数、无采用按钮及手机滚动测量。alerts是其他标签页的既有研究假设提示，并非计算失败。

只有24小时的合成研究假设，不代表全年规划、真实工程或未来预测。不自动采用任何结果，不调用付费模型。完整操作与计算口径见[演示说明](../decision_extension_demos.md)。

最终离线全量373项测试通过（91.22秒），见 `pytest_output.txt`；构建包字节核对见 `package_check.json`；公网代理阻塞记录见 `public_probe.json`。Windows CI在GitHub分别执行，真实Windows浏览器未在本任务中运行。
