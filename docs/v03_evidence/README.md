# v0.3 实际证据索引

- `test_output.txt`：完整本地测试126通过；`pip_check.txt`、`ui_health.txt`为实际环境检查。
- `annual_results.json`：三个真实全年重算的标量、参数、逐年现金流、独立约束最大违反量、输入/结果SHA与热指纹。
- `annual_*_report.md` / `budget20_report.md`、相应CSV：实际运行导出的报告和方案表。
- `heat_unchanged.json`：版本、父子运行、预算、容量、NPV和排放差异；这是确定性工具验收，未调用真实模型。
- `study.json` / `tradeoffs.csv`：5个实际求得点、基线和非支配点；不是完整全局前沿。
- `earlier_limits.json`：早期实际超时结果，保留有解/无解及可得间隙。
- `deepseek_acceptance.json`：真实模型未验收（0次），不能用模拟测试替代。
- `network_checks.json`：实际读取的官方说明/元数据摘要、原始响应SHA及瑞丽下载限制。

原始许可全年负荷与NASA响应位于examples/shanghai_2017，完整逐时结果可按README离线重算生成。这里保存的run_id和耗时属于本次实际运行，不保证重新运行UUID/耗时相同。报告中的outputs相对路径是当次生成记录，不代表这些大体积文件全部已提交；源码与输入足以重新生成并从UI下载。
