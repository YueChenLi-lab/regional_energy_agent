# 智碳推演 v0.5 · 展示层集成说明

使用用户上传的Claude整合草稿，核对当前仓库后增量集成；不是重建框架或新增规划算法。六个草稿文件的原始SHA和长度见 `v05_ui_evidence/draft_sources.json`。Claude原始文本仅作交接参考，未作为可执行源码拼接入生产。

## 组件与真实接口

| 文件 | 职责 / 实际接口 |
|---|---|
| `console/decision_presenters.py` | 只读dataclass ViewModel；读取真实 `ConversationReply`、`PendingDialog`、`ModificationContract`、`RunResult`、`CounterfactualResult`、`RegretResult`，兼容同字段dict |
| `console/decision_components.py` | 转义后的HTML、原生控件、三路径边界图、动态热力表、最坏后悔条、工具/证据与下载；不调用求解器、模型或ToolRegistry |
| `console/chat_workspace.py` | 65/35双栏，移动端单栏；每次布局只调用一次原有 `render_model(annual)`；会话键、恢复/取消/修订按钮沿用 |
| `console/decision_theme.css` | 深蓝/青蓝主题、10档热色、窄屏内部滚动/粘性首列、聚焦及降低动画设置；既有package-data已覆盖CSS |
| `console/decision_archives.py` | 新增只读适配：校验既有归档、Pydantic加载、映射本地下载；未找到时报错，不生成替代样例 |
| `console/dev_preview.py` / 根 `dev_preview_app.py` | 上传的可选开发预览；环境变量门控、醒目虚构标记，正式入口不导入 |

`console.app`保留 `main/prepare/PAGES`、五个tabs及采用回调。`workbench(run)`包装新工作台。三类入口只导航或提示，`router_available()`保持False。关键词建议不是自由文本自动工具路由，不授权修改、不调用模型。

## 对草稿的修正

1. **真实契约字段**：`ModificationContract.ready`是属性，不在JSON中；dict根据`edits/missing`判断，不把缺字段当作已授权。变更/保持说明复用原`contract_brief`。对话状态使用真实枚举；`study`读取已有StudyResult点和来源run_id，不伪装单次规划结果。
2. **比较口径**：以`compare_basis`核对任务输入，替代“是否都是full_year”的推断。预算比较与负荷、价格、折现率等敏感性区别标记；展示原始差值时标明敏感性，不写成设备改善或同口径生命周期节省。
3. **可靠边界**：只有真实可行/不可行轨迹、锁定保持、最终校验及合法范围共同支持时才显示区间色带；未知仅显示中性轴/记录点，不自动推断可行区间。区间宽度按实际比例，不用最小视觉宽度夸大精度。边界精度和运行目标最优性分别显示；`feasible_limit`使用警告。
4. **合法数值**：None、NaN、Inf、布尔值及非法数值显示缺失，不假填0；真实0保留。候选容量缺失不填0。单元必须有校验和固定容量证据才显示有效成本；展示完整性不符撤下完整推荐。非最优成本标上界/近似，部分结果不标完整认证。
5. **容量/矩阵**：动态候选×情景，不写死3×5；容量一致性须全部单元已验证，不能凭一个True替整行背书；使用原结果金额容差。并列、暂定和近似保留。
6. **基准快照**：核对现有存储确为`outputs/ui_conversations/<会话SHA>/receipts`。只读加载固定请求/代次文件，验证目录、文件名、run_id和版本，拒绝路径穿越；不构造新的AgentSession或改写回执。快照缺失时不编造前后指标。
7. **采用与幂等**：保留`cf_adopt_<path_id>`、`adopt_counterfactual_path`和`on_adopt`；采用ID绑定已保存结果的request_id，避免编辑尚未执行的表单ID影响旧结果采用回执。探索与刷新均不自动采用。
8. **下载与键**：真实归档映射到仓库内文件，保留数值和原JSON不变；实时/归档控件分别加前缀，同一次五页渲染不会重复注册键。旧原生Vega视图置于折叠区保留图像/数据导出和原流程验证。
9. **CSS与可访问性**：用显式10档颜色替代未经核实的中间色文字切换；斜纹保持对比度。真实浏览器验证`:has()`、内联位置、title、aria、tabindex、粘性列、减动画。状态均有文字；键盘/手机可通过原生聚焦单元控件查看详情，不依赖hover。
10. **Windows字节保持**：归档SHA校验不能受checkout换行转换影响；`.gitattributes`为三个证据目录设置`-text`，没有修改原数据或已发布归档字节。

右侧分别显示确认基准及结果/current run_id和版本，避免新旧混淆。锁定条件、已确认预算/时段、比较说明、独立校验和真实工具记录均来自原模型。未有对话时保持紧凑提示，不生成聊天历史或实时进度。

## 入口、运行与回退

通过本地比赛页浏览器及入口专项验收后，根`app.py`最小改为导入`energy_agent.console.app.main`，保留原文件名。`competition_app.py`为同一控制台别名；`legacy_app.py`保存原入口。dotenv仍为项目目录、`override=False`，每个入口仅由所调用的main设置一次page config。

Windows：

```powershell
conda activate regional-energy
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m streamlit run app.py
# 旧界面本地回退
python -m streamlit run legacy_app.py
```

云端使用项目`.venv/bin/python`替换python。`python -m streamlit run competition_app.py`仍可用。可选预览必须显式设置`ENERGY_AGENT_DEV_PREVIEW=1`再运行`dev_preview_app.py`，禁止将其作为比赛或Cloud入口。

没有更改Cloud仓库、分支、入口设置或域名，没有删除/重建应用。公网更新以人工合并后真实页面/日志为准，见[验收及公网检查](v05_ui_validation.md)。

## 未实现及边界

统一自然语言三工具自动路由仍是后续TODO。本轮无新优化模型、数据库、第三方前端框架或依赖，无真实付费模型验收。真实接口历史验收属于先前版本，本轮仅模拟测试与既有工具调用流程。

正式页面不导入虚构预览。已归档24小时/8760小时数据继续保留合成/混合来源、服务边界与假设，不变成实时新计算。开发过程中源码热更新可能令旧内存中的Pydantic类实例失配，重新启动开发服务器并重新加载会话后验证；普通无源码变更的刷新/导航已另测，不改动历史JSON回执以掩盖此问题。
