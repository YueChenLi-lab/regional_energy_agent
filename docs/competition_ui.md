# 比赛展示界面：设计与集成

启动新增入口：`python -m streamlit run competition_app.py`。旧入口 `app.py` 保留。无需新增依赖；现有 Python 3.12、Streamlit 1.66.0、pandas 足够运行。请从仓库根目录启动，以加载项目主题和本机 `.env`；已有环境变量不会被覆盖。页面刷新、标签切换和读取归档证据均不调用模型。

## 设计规范

| 项目 | 规则 |
| --- | --- |
| 色彩 | 页面 `#07111f`，卡片 `#0d1c2e`，浮层 `#12263c`，分隔线 `#29415a`；青蓝 `#59dfeb` 表示交互/重点，青绿 `#71dfb7` 表示通过，暖黄 `#ffd286` 表示需注意；状态始终带文字 |
| 字体 | 本机 Segoe UI / PingFang SC / Microsoft YaHei，无外部字体请求；正文跟随 Streamlit 默认字号，标签约12–13px，卡片标题16px，指标约22–30px；数字使用等宽数字特性 |
| 间距 | 以8px为基准；网格间16px，卡片内20px，区段24px；桌面页边40px，窄屏16px；内容最大1480px |
| 卡片 | 12px圆角、1px低对比分隔线、无重阴影；首页主视觉18px圆角，青蓝渐变仅用于主视觉 |
| 层级 | 首页先定位和入口；结果先推荐/可行性与四个主指标，再配置/曲线；技术JSON、来源细节和工具轨迹折叠 |
| 响应式 | 超过1100px指标四列；720–1100px两列；不超过720px单列；顶栏换行，导航可横向滚动；数据表保留横向滚动，不压缩单位 |
| 可访问性 | 保留原生表单、键盘焦点和标签；不靠颜色单独表达通过/失败；不隐藏Streamlit工具栏或用JavaScript接管交互 |

原生主题在 [`.streamlit/config.toml`](../.streamlit/config.toml)，项目内两个入口共用配色。组件CSS在 [`energy_agent/console/theme.css`](../energy_agent/console/theme.css)，包含少量针对锁定Streamlit版本的 `data-testid` 选择器；升级Streamlit后应重跑AppTest并检查浏览器截图。页面没有自定义JavaScript、CDN、第三方前端框架或新增Python依赖。

## 页面与真实数据接口

| 标签 | 展示与边界 |
| --- | --- |
| 项目首页 | 项目定位、Agent/计算/校验架构亮点，两个原生导航按钮；不展示虚构成绩 |
| 问答工作台 | 复用 `render_model(annual_run)`；真实当前请求快照、用户回答与助手文本使用 `st.chat_message`；修改/保留清单、澄清、恢复、取消、重选基准与模型按钮保留原逻辑；不是新增完整历史聊天存储 |
| 优化结果 | 复用三类原有评估表单，显式提交才求解；读取 `RunResult` 推荐、容量、初投、运行费、NPV、排放、校验与求解状态；没有结果显示“待评估”，未启用经济模型显示“未启用” |
| 实验验证 | 从 `docs/v032_evidence/peak_study.json` 读真实归档三情景；标为归档、未重新求解、非实时模型输出；显示比较口径C与输入电量改变的影响 |
| 证据详情 | 当前运行来源分类、边界、假设、独立校验、工具记录和下载。历史结果引用的导出文件不在本机时明确提示；JSON来自当前实际RunResult |

运行曲线读取 `dispatch.points` 和 `task.data`，未重采样或改变求解数据；使用原生Vega-Lite缩放平移。时间轴统一显示UTC，并保留来源JSON中的原始时区，避免浏览器时区改变时间含义。电侧任务不绘制零热曲线。求解器最优性与独立校验分别标注；容量优化的最优性只针对当前模型，有限候选只针对本次比较范围。

## 组件封装

```python
from energy_agent.console.components import theme, section, metrics
from energy_agent.console.views import results, evidence

# 应用入口设置page_config后，仅加载一次主题。
theme()
section("优化结果", "仅显示当前运行的计算结果")
metrics([("初始投资", None, "元")])  # None明确显示待评估，不能假定为0
results(st.session_state.get("annual_run"))  # RunResult | None
evidence(st.session_state.get("annual_run"))
```

| 文件 | 职责/可复用接口 |
| --- | --- |
| `competition_app.py` | 本机配置加载与独立展示入口 |
| `console/app.py` | `main`、首页、原表单组合、工作台和原生标签导航 |
| `console/components.py` | `theme`、`section`、`empty`、`metrics`、`feature_cards`、`execution`、`series_chart`；只读展示 |
| `console/views.py` | `results(RunResult | None)`、`evidence(RunResult | None)`、`conversation_snapshot(ConversationReply | None)`、`experiment()`；按实际业务schema读取 |

所有拼接进HTML的用户、模型、来源和方案文字均转义；模型文本通过原生 `st.write` 展示，不作为不受信任HTML执行。空值不生成容量、金额或排放替代值。

## 保留状态与业务调用的集成位置

1. `energy_agent/ui.py` 将原 `main()` 中的合成表单提取为 `render_demo(show_results)`；原入口仍调用它，原按钮/表单/session键、`revise_task` 与 `EnergyAgent.run/run_text` 的调用体保留。
2. `planning_ui.render_planning` 新增默认True的纯显示开关 `include_model`、`include_experiment`。展示入口传False，把同一个助手与归档实验放在各自标签；原入口行为保持。
3. 三种运行继续保存在 `last_run`、`real_run`、`annual_run`。展示层仅保存 `console_` 前缀的导航、选中运行和条件折叠状态，没有新运行副本，没有新文件存储或持久化路径。
4. 五个标签每次均渲染，保留工作台中既有widget-backed请求ID/会话ID。评估后仅触发一次UI重绘以收起条件区；重复重绘不会再次提交表单或调用模型。原会话锁、幂等ID与持久化逻辑不变。
5. 结果页可查看多个既有运行，但对话助手仍明确绑定 `annual_run`。选择其他结果不会偷偷重选对话基准。全年对话接续更新后，各页读取现有的最新运行对象。

没有修改优化器、Agent、工具注册、修改契约、来源处理或文件锁。合成案例和外部导入继续使用各自原表单；持续对话沿用现有全年任务入口。

## 启动与验证

Windows（项目根目录）：

```powershell
conda activate regional-energy
python -m streamlit run competition_app.py
```

云端（现有项目虚拟环境）：

```bash
.venv/bin/python -m streamlit run competition_app.py --server.headless true --browser.gatherUsageStats false
.venv/bin/python -m pytest -q tests/test_competition_console.py
```

可先进入“优化结果”→加载合成案例→启动评估→查看配置和曲线→“证据详情”下载报告。全年助手：在同一条件区切换“全年规划与Agent”，确认边界并加载、评估后，再进入问答工作台；仅显式模型按钮可能产生费用。模型配置和限制沿用原项目。

本轮验证详情见 [competition_ui_validation.md](competition_ui_validation.md)。普通CI和AppTest不请求真实模型；比赛界面没有新增算法或重新执行归档全年敏感性实验。

## v0.4.1 多情景决策集成

`console.app.main` 在结果及反事实修复之后调用 `regret_ui.render_regret(run)`，只读当前选择的RunResult。独立 `regret_<run_id>` 控件/结果状态键保留原会话键和业务调用。只有已确认表单提交才运行注册工具；相同输入的稳定请求ID重放落盘回执，刷新不执行。默认折叠；配置、情景及授权先展示，结果按真实认证/近似/待定状态生成；证据和JSON在展开区。没有采用操作，不改变原任务持久化。`ENERGY_AGENT_ENABLE_REGRET=0` 可关闭。真实桌面/430px截图和对应合成168小时页面文字见 `v041_evidence`，不是全年截图。
