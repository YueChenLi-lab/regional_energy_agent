# 比赛展示界面验证记录

日期：2026-10-19。环境：Linux、Python 3.12.14、Streamlit 1.66.0；复用项目 `.venv`。新增展示入口与CSS，不新增依赖，不修改优化算法、Agent业务调用或持久化逻辑。

## 已实际通过

| 验证 | 命令/方式 | 结果 |
| --- | --- | --- |
| 全部自动测试 | `.venv/bin/python -m pytest -q` | 270 passed，58.60秒（原266项＋展示层4项） |
| 最后一次界面回归 | `.venv/bin/python -m pytest -q tests/test_competition_console.py tests/test_ui.py tests/test_planning_ui.py tests/test_ui_v032.py tests/test_dialog_ui_v031.py tests/test_import_ui.py` | 10 passed，5.31秒；含最终主题、条件收起与状态展示 |
| 依赖一致性 | `.venv/bin/python -m pip check` | No broken requirements found |
| 实际启动 | `.venv/bin/python -m streamlit run competition_app.py --server.headless true --server.port 8511 --browser.gatherUsageStats false` | Streamlit启动成功，`/_stcore/health`返回ok |
| 浏览器检查 | 系统现有Chromium headless，Linux，桌面1440×1100、窄屏390×1000 | 实际点击加载合成案例、求解、结果、实验和证据页；无页面异常；390px页面scrollWidth=390、卡片单列 |

浏览器检查用原生DevTools协议操作现有Chromium，只作为本次验收工具，没有向产品添加JavaScript或浏览器依赖。截图与机器记录在 [competition_ui_evidence](competition_ui_evidence/)；结果截图中的金额、容量与运行ID来自该次实际合成案例求解，不是视觉占位数字。

初次浏览器检查发现顶部内容被原生固定栏遮挡，已增加顶部留白后复查；最初浏览器脚本按button查找标签而失败，改为原生role=tab后完成全部导航。这些是检查过程中已修复的问题，不计为最终失败。

## 自动测试实际覆盖

新增 `tests/test_competition_console.py` 的4项测试包含：

- 禁止HTTP与求解器调用时，初始空结果和全部标签仍可展示；归档表与真实文件峰值一致，不调用求解器。
- 从新入口实际完成合成求解、导出和预算降为0的真实重算；验证新版本、父运行ID、无推荐，以及标签切换保留原运行。
- 方案名称中的HTML被转义；原报告文件不在本机时不会崩溃或生成伪下载文件。
- 模拟服务下，含糊要求先澄清；回答“减少15%”真实重算并核对预算、供热保持和新run_id；重复提交不新增调用或求解。

最后一项属于**模拟模型协议测试＋实际确定性求解**，不能称为真实DeepSeek验收。此次真实模型请求为**0次**。页面普通刷新不调用付费接口，现有模型连接测试仍需用户明确点击。

## 展示证据的边界

- 实验页读取仓库已有的三组8760小时计算记录，本轮没有重新执行峰值实验。页面明确显示“归档/未重新求解/非实时模型输出”，结论保留负荷电量变化的限制。
- 结果、来源与独立校验均绑定现有RunResult；缺少结果显示待评估；未启用经济评价时显示未启用。
- AppTest与实际Chromium检查分别执行；浏览器缩放至390px是窄屏布局检查，不等于手机实机验收。
- 本轮**未重新执行Windows浏览器、Windows Streamlit AppTest、Safari/Firefox、真实触屏或屏幕阅读器验收**。此前仓库Windows CI记录仍属于原版本的历史证据。
- 不自动推送、合并或部署展示页面；代码供本机启动与集成。原始计算、模型和会话存储保持现有方式。
