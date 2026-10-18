# v0.3.1 验收证据

- `real_requests.json`：10次真实HTTP200的时间、工具、耗时和服务返回token用量；为遵守不输出配置值，省略模型配置值，不含密钥/请求头。
- `real_acceptance.json`：每项真实验收状态、用户输入及当时实际摘要。其中文标签是当时版本。
- `real_dialogue.md`：真实多轮原请求/问题/回答，及按最终确定性中文模板重渲染的同一结果；没有增加API请求。
- `run_evidence.json`：基准、新run_id/版本、契约、保留检查、容量、NPV、排放、现金流、结果SHA、真实模型意图与逐项核验的引用。
- 各`*_report.md`和`*_scenarios.csv`：当次实际运行导出；完整逐时数组可按README离线重算，不把本地outputs路径当下载文件。
- `peak_diagnostics.json/md`：真实Q峰值与邻近时段，只读，未做替代值求解。
- `startup_check.json`：Streamlit实际启动健康检查HTTP200/ok，检查后停止进程。
- `test_output.txt`：完整离线回归；真实接口记录与Fake/MockTransport测试严格分开。

原始许可数据在examples/shanghai_2017；计价/排放/供热与经济参数仍为研究假设。未合并、未部署，未完成Windows实际验收。
