# v0.5 UI 实际验收证据

所有截图来自真实Chromium，桌面1440×900、手机390×844；根入口`app.py`运行同一五页控制台。未导入dev_preview虚构样例。

- `workbench_desktop.png`：双栏工作台，当前任务为主动加载并执行的上海全年有限候选任务；尚无模型对话，不虚构消息。
- `workbench_mobile.png` / `workbench_input_mobile.png`：单栏阶段、任务选择、实际助手和当前任务卡。
- `repair_desktop.png`：既有24小时三路径真实归档；明确只读，非本页面新求解，无采用操作。
- `regret_summary_desktop.png` / `regret_desktop.png` / `regret_mobile.png`：既有8760小时2×3真实归档；成本NPV、后悔和容量来源不变，手机表格内部可横向滚动。
- `browser_measurements.json`：实际DOM测量、布局、位置、20档计算样式及WCAG对比度、键盘、title/aria、减动画。正常/斜纹最低4.897:1；没有对全部站点作完整WCAG认证。
- `browser_downloads.json`：真实浏览器下载的JSON/CSV/Markdown与归档逐字节一致的SHA及大小。
- `draft_sources.json`：用户上传草稿的原始校验信息，不声称原草稿已经运行通过。
- `runtime_versions.json`、`pytest_output.txt`、`pip_check.txt`、`package_resources.json`：实际运行环境、完整测试和包资源证据。
- `public_probe.json`：当前任务探测既有公网遇到ProxyError；不是部署成功证据。

数值见证仍位于既有 `docs/v04_evidence`、`docs/v041_evidence`，没有覆盖或重算它们。新界面归档浏览校验原文件SHA，使用Pydantic实际加载；失败时明确提示，不替换成人工样例。
