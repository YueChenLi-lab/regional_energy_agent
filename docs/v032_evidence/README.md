# v0.3.2 实际证据

- `baseline_tests.txt`：main基线169项测试。
- `semantics_before.json`：main已复现问题；修复结果及最终测试另见验收记录。
- `peak_study.json`：三组实际全年求解，含run_id、容量、指标、原值差异、模型规模、耗时、状态、间隙、固定条件指纹和38项独立检查。
- `peak_scenarios.csv`、`peak_report.md`：实验机器表及中文报告。
- `predeclared_treatments.json`：任何求解前固定的处理点、方法、阈值及保持条件。
- 各`*_report.md`/`*_scenarios.csv`：实际运行导出。完整逐时数组可由命令重算；未将内部outputs路径作为下载方式。
- 标准化CSV及处理来源在`../../examples/peak_sensitivity_v032`，原文件和许可在`../../examples/shanghai_2017`。

这些是实测与假设混合研究情景。处理数据是人为假设，不是校准实测；没有真实API请求。Windows CI、AppTest和真实浏览器验收分开记录于`../v032_validation.md`。
