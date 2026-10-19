# 智碳推演 v0.5 UI 验收 · 2026-10-19

基于远程main `c9252ca5af01ff60c8a8174fec531502a5e66835`，确认已含PR #8和#9。开工工作区干净；分支`feat/v0.5-decision-workbench-ui`。10份独立附件均已收到并读取核心草稿/交接说明，没有寻找ZIP或执行原始Claude文本。实现修正及文件职责见[集成说明](decision_workbench_ui.md)。

## 已实际通过

| 项目 | 实际证据 |
|---|---|
| 完整测试 | **365 passed，74.47秒**，命令`.venv/bin/python -m pytest -q --junitxml=outputs/v05_final_tests.xml`，退出0；[完整输出](v05_ui_evidence/pytest_output.txt) |
| 原测试保留 | 原333项＋新增32项；未删除/跳过测试或删除业务断言。仅把全年入口测试的`button[0]`定位改为“加载许可全年离线案例”按钮，仍断言未确认时禁用，避免新首页按钮改变索引 |
| 入口切换前 | 比赛页完整361项通过、真实浏览器及入口专项32项通过后，才最小切换`app.py`；新增细化测试后再执行最终365项 |
| 依赖与编译 | 项目`.venv` Python3.12；`pip check`退出0、No broken requirements found；`compileall`通过；无新增运行依赖 |
| 包资源 | 按既有pyproject隔离构建v0.5.0 wheel；CSS及5个控制台Python模块逐字节匹配当前源文件；[包资源校验](v05_ui_evidence/package_resources.json) |
| 真实归档 | Pydantic加载24小时三条修复路径、合成24小时3×4、混合8760小时2×3；校验原归档SHA，展示真实状态/单位/来源；浏览不重算 |
| 采用与锁定 | 原反事实授权、范围、预算锁、采用、刷新回执和表单更新回归通过；按钮仍为`cf_adopt_<path_id>`，调用原采用函数 |
| 对话 | 模拟HTTP传输走原AgentSession：澄清→回答→真实6小时重算、恢复、进程/浏览器新实例恢复、修订回答、重复提交和取消；保持原基准、供热及版本；每次布局仅一个render_model实例 |
| 页面被动性 | AppTest对刷新、输入关键词提示、导航、归档浏览同时禁止ToolRegistry/优化器/HTTP，实际0次调用；原功能主动按钮仍真实重算 |
| 状态真实性 | None/NaN/Inf/真实0、null、未执行/拒绝/错误/未知、校验失败、feasible_limit/近似、无可靠端点均有测试；不静默填0、不虚构边界、不使用旧认证背书 |
| 比较口径 | 同为短期但负荷改变、同为全年但折现率改变均标敏感性；原始差值不冒称同口径生命周期节省 |
| 原版兼容 | app.py与competition_app.py均五页，legacy_app.py保留原版；全部入口无密钥/无网络正常打开，预览需显式门控 |

实际运行命令（项目根目录；Windows使用Conda中的python）：

```bash
.venv/bin/python -m pytest -q --junitxml=outputs/v05_final_tests.xml
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q energy_agent app.py competition_app.py legacy_app.py dev_preview_app.py
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m pip wheel . --no-deps --wheel-dir outputs/v05_wheel
.venv/bin/python -m streamlit run competition_app.py --server.port 8515 --server.headless true
.venv/bin/python -m streamlit run app.py --server.port 8516 --server.headless true --server.fileWatcherType none --browser.gatherUsageStats false
```

最后一条用于固定源码版本的浏览器验收，`fileWatcherType none`仅是本地验收启动参数，没有写入Cloud配置。安装构建均在项目虚拟环境/临时隔离构建环境，不修改全局Python。

## 真实浏览器结果

Chromium headless/CDP，实际尺寸1440×900与390×844。实际在根`app.py`中加载上海全年离线任务、显式选择有限候选并执行评估，再进入问答页及归档实验页。没有点击任何付费模型按钮，截图中的对话为空时明确显示未开始，不使用开发预览的虚构数据。

- 桌面左/右列实测约845.5/440.5px（扣除留白和列间距），右侧sticky；手机两列均348px、同一x坐标16px，position static，成为单栏。
- 手机页面无水平溢出；热表容器宽314px、内容520px，可横向滚动。滚动150px后首列位置误差3px（表格border-spacing），首列保持可见。
- 8760小时2×3结果有两张表、12个有效单元，未写死维度；AppTest另覆盖3×4真实归档。
- 表格单元`tabindex=0`，真实focus成为activeElement；`title`保留状态、金额及后悔，边界`role=img/aria-label`可见于实际DOM；原生单元选择器提供手机/键盘详情。
- 检测CSS计算样式中两套10档颜色；正常/斜纹最低文字对比度 **4.897:1**，达到目标4.5:1。没有将此结果扩大为整个站点完整WCAG认证。
- `prefers-reduced-motion=reduce`下动画名为none。只有可靠轨迹的三路径归档显示可行色带；未知状态的中性轴另有单元回归。
- 在真实浏览器点击JSON、CSV、Markdown下载，文件逐字节匹配8760小时原归档；[下载校验](v05_ui_evidence/browser_downloads.json)。

截图与DOM测量：

- [桌面问答工作台](v05_ui_evidence/workbench_desktop.png)
- [手机工作台](v05_ui_evidence/workbench_mobile.png) / [手机助手与当前任务](v05_ui_evidence/workbench_input_mobile.png)
- [三路径归档](v05_ui_evidence/repair_desktop.png)
- [NPV决策摘要](v05_ui_evidence/regret_summary_desktop.png)
- [桌面矩阵](v05_ui_evidence/regret_desktop.png) / [手机矩阵](v05_ui_evidence/regret_mobile.png)
- [计算样式与布局测量](v05_ui_evidence/browser_measurements.json)

6/168小时的实际计算与修改由既有UI回归执行；24小时及8760小时新组件读取实际归档。本轮没有重新宣称完成全年情景矩阵求解：其真实求解、校验和来源仍属于v0.4/v0.4.1证据。浏览器额外主动执行的是全年有限候选任务，仅为新入口交互验收。

## 模拟、失败修正及未验证

**模拟通过**：本轮模型交互采用httpx.MockTransport，不连DeepSeek；测试中真实调用确定性工具并核对预算/供热/版本。模拟状态用于未知、feasible_limit和错误显示，不当作本轮真实超时事件。

**真实付费模型调用0次**。页面刷新/导航的禁止调用测试中求解器/ToolRegistry/HTTP均0次。历史v0.3.1真实接口验收未被包装成本轮新验收。

修复过程中发现并重验：缺少待执行caption的旧UI回归、草稿局部导入造成path_title未绑定、数值/边界/费用可比性问题；首次尝试无隔离wheel构建因项目虚拟环境无setuptools后端失败，改用pyproject既定隔离构建成功。新study测试曾错误假设老归档含较新字段，改为核对老归档实际NPV/排放列，未删除点数和来源断言。开发热更新期间旧Pydantic内存类实例曾失配，重启后用固定源码版本重新完成浏览器验收，未修改核心模型/存储或归档。

**Ubuntu/Windows CI**：保留原双平台Python3.12离线矩阵、pip check、中文路径demo和离线重放。本文写入时尚待推送；最终执行状态及链接在PR Checks和交付报告中更新，本地365计数不替代Windows实际执行。Windows Conda真实浏览器和屏幕阅读器未执行，不用Linux尺寸模拟冒充真机测试。

**公网未验证**：探测`https://regional-energy-agent.streamlit.app/`时得到ProxyError，无法检查公网页面/健康或Cloud管理日志。Cloud绑定main/app.py依据用户说明，本轮没有Cloud管理台权限证据，没有更改设置、删除/重建应用或切换域名。PR未人工合并前不能声称v0.5已上线。

## 人工合并后的公网检查与回退

1. 审查并手动合并PR；原Cloud仍使用同一仓库、main、app.py与原域名。
2. 等待Community Cloud同步，重新访问原网站或开启新标签页；核对五页、双栏/手机工作台、三类受限入口及证据下载。
3. 在实验页选择两个真实归档，确认来源/只读提示、2×3与3×4、null/近似文字和报告下载。仅浏览或刷新不应出现求解/模型调用。
4. 无模型密钥时验证合成案例；需要验证模型时须另行明确授权，本轮不自动调用。不要以服务“已配置”代替真实连接验收。
5. 若仍显示旧页或发生加载错误：用户在`Manage app → Logs`检查；确认拉取的提交、入口依旧app.py；必要时`Manage app → Reboot app`，再重开页面。不要重新创建应用或更换域名。
6. 本地旧版回退：`python -m streamlit run legacy_app.py`。公网回退通过新的GitHub回退PR，将app.py导入恢复为`energy_agent.ui.main`，或对v0.5合并提交执行`git revert -m 1 <合并SHA>`后提交审核。基线main为c9252ca；不强推、不丢弃历史回执，不在本轮自动合并回退。

未实现统一自由文本自动路由，`router_available=False`；它是后续独立工作，不属于本次UI验收。没有新增优化算法、真实模型费用或前端基础设施。
