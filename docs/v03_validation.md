# v0.3 实际验证与交付边界

2026-10-18，Linux云端，项目`.venv` Python3.12.14。从远程main `d711b0f`新建`feat/annual-capacity-deepseek`，开始时工作区干净，无AGENTS.md。基线97项重新通过。本轮依赖没有新增，沿用requirements.lock.txt；editable安装版本0.3.0，pip check无依赖冲突。不修改全局Python。

## 已实际运行

```bash
.venv/bin/python -m pytest -q
# 126 passed in 47.37s；原97项保留，新增29项
.venv/bin/python -m pytest -q tests/test_deepseek_agent.py tests/test_data_agent.py tests/test_planning_ui.py
# 后续输入与UI边界修正后的针对性复核：36 passed；最终计算/Agent复核63 passed、UI复核4 passed
.venv/bin/python -m pip install -e . --no-deps --cache-dir data_cache/pip
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q energy_agent
.venv/bin/python -m energy_agent.cli annual-build --bundle examples/shanghai_2017 --heat --retain-flagged-jumps --output outputs/annual_final_heat --run --time-limit 60
.venv/bin/python -m energy_agent.cli annual-build --bundle examples/shanghai_2017 --retain-flagged-jumps --output outputs/annual_final_electric --run --time-limit 60
.venv/bin/python -m energy_agent.cli plan-study --task outputs/annual_final_heat/task.json --scans 3 --time-limit 120 --output outputs/annual_tradeoff_verified
.venv/bin/python -m energy_agent.cli llm-acceptance --run outputs/annual_final_heat/runs/da9172d5ef5242f9a2f72203aeb66e2d/result.json --output outputs/deepseek_acceptance
# 返回not_verified、退出2：配置缺失、真实请求0次，不是通过
```

另用同一EnergyAgent对已确认电热任务调用 `revise_task(TaskPatch(budget_multiplier=0.8,preserve_heat=True))` 后实际全年重算；下表及heat_unchanged.json为证据。不是预置模型答复。Streamlit8503实际启动，health返回HTTP200 ok；AppTest覆盖旧演示、导入及新增全年来源/确认/加载，不触发模型请求。已停止本轮启动的进程。

## 实际外部样本、人工测试和模型模拟分开

- **实际外部样本**：Zenodo正式完整CSV、正式README及NASA同期全年UTC JSON，附许可证/归属、原始SHA、父ZIP SHA和发布MD5。Q年电量3961671.29kWh，逐小时kWh→平均kW能量核对未缩放、未年化；核对阈值0.0001kWh（输入声明分辨率0.01kWh/100），不是仪表误差限；原值浮点求和差异在该阈值内。源量化舍入界限43.8kWh另列，不能拿它掩盖转换错误。2个跳变保留，风险未解除。NASA原始请求UTC跨到2016-12-31，只为了覆盖北京时间2017-01-01，未换年。实际样本测试禁止HTTP，重新解析、估算PV、全年优化及独立校验，并对电热预算变更再次优化。
- **人工小算例**：零/正折现、更换/残值与终点不更换；分析可解的小型容量基准、固定容量退化、预算/排放无解、供热日程、普通/闰年和UTC转换。新容量模型超时有/无解分别模拟，原有物理/时间/异常/边界测试继续通过。
- **模型模拟**：MockTransport返回协议响应，真实调用本地求解工具；检查DeepSeek非思考、工具参数、截断/非法输出、401/403、有限重试/10次上限、日志脱敏、相对修改、供热指纹、重复提交、工具失败、错误数字、旧run_id、dotenv不覆盖。它不证明真实模型理解或真实服务可用性。

## 全年求解结果

输入均8760小时，电量3961671.29kWh；电热研究另含437095.641kWh_th物理仿真供热。20年、折现5%，同一历史年度在未来重复；所有经济与排放参数为研究假设。运行排放为CO2e假设，非官方2017因子，不是生命周期碳。每年物理排放不折现。

|案例|run_id|初始投资 元|NPV 元|年度运行排放 kgCO2e|耗时 秒|状态/间隙|
|---|---|---:|---:|---:|---:|---|
|电侧Q|0cb43fb6cad74358b50ff67b18b6932c|10000000|27560461.4581|1145967.4308|12.69|optimal / 0|
|Q＋仿真供热|da9172d5ef5242f9a2f72203aeb66e2d|10000000|29718716.5160|1255841.1465|13.23|optimal / 0|
|供热不变、预算×0.8|5cdc6e94ddbf45999616268e763f87ac|8000000|30531925.8908|1417604.4579|13.79|optimal / 0|

原MILP规模：70086变量、8760二进制、105127约束，约249657非零元。60秒上限；LP松弛最优经整数模式转换后满足原约束，目标未变，取得原模型下界等于整数可行目标的证书；独立物理/NPV计算再核对。上述“最优”只针对声明的线性设备、容量范围与假设，不是工程最优。初期45秒原MILP仅有可行解（间隙分别约0.53%/8.08%）也被单独保留于earlier_limits.json，没有改标为最优。

预算减少20%：光伏1819.445→1502.493kW，电池421.702/2628.218→321.400/2049.329kW/kWh，热泵184.591→0kW_th，锅炉480.068→664.659kW_th。**热需求、时段和逐时足额保障未变**，没有用降低需求制造可行性。初始投资减200万元，NPV增加813209.3749元，年度运行排放增加161763.3114kgCO2e。运行版本1→2，确实重新求解，不是改报告文字。

## 成本—排放取舍

明确基线为Q电网＋满足同一仿真热需求的新建锅炉：初投183445.884元，NPV39194982.8389元，年度排放2277022.8978kgCO2e。

最低NPV参考为29718716.5160元、1255841.1465kg/年；最低运行排放参考为1196231.2273kg/年、NPV32732965.8846元。三项排放上限1211133.7071/1226036.1869/1240938.6667kg下，NPV分别30295891.3603/29846268.9011/29743641.8596元，均optimal、独立校验通过；耗时70.28/59.48/41.13秒，上限120秒。配置、初投增量、NPV增量、年度减排及已得非支配点完整保存于study.json/tradeoffs.csv。

初次60秒扫描未找到中间点可行解的记录也保留。调整了LP阶段时间分配并以120秒上限重新运行，未删除失败记录。有限扫描不证明完整全局前沿，也不把最低排放参考当零碳。

## 未完成/未验证

- **真实DeepSeek接口验收未完成，实际模型请求0次。** 当前环境和项目.env无模型配置；没有从聊天写入或调用用户密钥。安全环境配置项已保存供用户在环境设置中填写。配置草稿保存不等于已应用或发布；本机步骤见deepseek_agent.md。
- 瑞丽元数据/新目录文件名可读，但数据实体下载接口返回code403：“目前只支持部分数据集的说明文件下载，数据文件请通过数据申请获取。”实际文件未解析，不能称瑞丽接入完成。
- Q异常峰值、计量回路、时间锚点、匿名楼宇精确位置、供热模型/参数、场地、电价、设备报价与排放年份尚未工程核实。仿真供热未校准，不含W/供冷/热水等被排除服务。
- 新全年功能未在Windows重测；无浏览器视觉验收（已有AppTest功能及HTTP健康检查），未部署、未合并。
- 无多气象年、不确定性、设备衰减、设备隐含排放或生命周期碳核算；不超出本轮范围。

随代码保存的报告、参数、标量结果、现金流、原始输入和SHA便于审查；输出目录的完整逐时JSON/CSV可用上述命令离线重新生成，run_id及耗时自然会改变，关键指标应在数值容差内复现。源文件许可与缓存规则独立于代码许可证。
