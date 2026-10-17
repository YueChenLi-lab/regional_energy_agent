# v0.2第一阶段实际验证

环境：Python 3.12.14，项目`.venv`，pvlib 0.16.1；依赖版本见锁文件。实测负荷、资源估算和人为假设明确区分。

## 已运行命令与结果

|命令/检查|实际结果|
|---|---|
|`.venv/bin/python -m pytest -q`|97 passed；保留原58项，无跳过；[原输出](v02_evidence/test_output.txt)|
|`data-fetch --provider zenodo --online`|实际下载正式26MB档案，发布MD5匹配，并保存容器/成员SHA-256；元数据CC BY4.0|
|`data-import --provider zenodo --building test --meters Q,W --acknowledge-category-sum --timestamp-position start --acknowledge-time-assumption --start 2017-01-01 --hours 168 --parameters configs/electric_assumptions.json --with-solar --output outputs/v02_formal --run`|正式CSV和同期NASA缓存，四个电侧候选全部optimal，独立校验通过并导出|
|`data-replay --output outputs/v02_offline_acceptance`|离线重新解析/估算并优化；关键指标与保存案例相差<1e-6|
|`data-replay --budget 0 --output outputs/v02_budget_acceptance`|新run_id、输入版本2；推荐GPB→G，其他新增投资候选被预算拒绝|
|Streamlit AppTest|实际加载人工格式缓存、导入预览、确认参数、求解、下载入口和修改预算重算通过；不是实际浏览器视觉验收|

表中CLI子命令均经`.venv/bin/python -m energy_agent.cli`执行。NASA真实响应与发布方原文件验收单独记录，不用人工传输测试代替。

实际联网状态见[网络请求记录](v02_evidence/network_checks.json)；锁定环境重复安装成功，见[安装摘要](v02_evidence/setup_tail.txt)。应用实际在127.0.0.1:8502启动，内部健康请求返回ok；功能由AppTest验证，不生成云端localhost预览链接。

## 原始与转换能量

Q/W共336条，168小时；原始类别电量90087.68999999999 kWh，转换90087.69 kWh；差值1.4551915228366852e-11 kWh < 0.0002 kWh容差。

0.01kWh是声明的输入数值分辨率，不是仪表精度证据。转换无舍入，容差为各测点输入分辨率1/100之和（至少1e-8）；源数值舍入不确定性上界1.68kWh另列，不掩盖转换错误。无填零、插补、时间重编号或负荷缩放。

|范围|记录|缺失时段|重复|负值|缺失/非有限|跳变告警|
|---|---:|---:|---:|---:|---:|---:|
|全文件/Q|8760|0|0|0|0|2|
|全文件/W|8760|0|0|0|0|68|
|窗口/Q|168|0|0|0|0|0|
|窗口/W|168|0|0|0|0|0|

全文件窗外告警保留、未自动删除；窗口单独合格。类别合计不是全楼总电量，Time起点与北京时间是显式假设；NASA小时UTC起点则已根据官方说明核查。

## 本次候选结果（实测与假设混合案例）

|方案|新增投资 元|168h运行费 元|运行排放 kgCO2e|
|---|---:|---:|---:|
|G|0.00|67332.62|49548.23|
|GB|698625.00|65315.81|49718.93|
|GP|1987200.00|64411.60|47316.89|
|GPB|2685825.00|62394.78|47487.59|

GPB运行费最低；GP投资和排放更低，储能并非自动减排。电价、成本及0.55kgCO2e/kWh均为人为情景，仅计电量收费，未年化或相加为生命周期成本。预算约束增量投资，既有电网基线新增投资为0。

[完整报告与许可案例](../examples/shanghai_168h/README.md)；[机器可读证据](v02_evidence/real_case.json)；[详细方法与边界](real_data.md)。

## 明确区分验收类型

- 实际网络：正式Zenodo ZIP/元数据、NASA UTC小时接口、官方因子公告和模型文档均实际读取。网络曾返回403，后来恢复后完成，未使用错误响应充当数据。
- 实际外部文件：正式CSV完整读取并检查，连续168小时真实计量子集和真实NASA响应保存并通过离线重新计算；独立测试`test_published_case.py`没有网络。
- 人工样本：数据换算、重复/缺失/非法、累计复位、UTC/LST拒绝、档案校验和UI等风险测试使用明确标记的人工小样本。
- 模型适配器：仍是本地模拟响应测试通过，没有连接真实LLM；无付费模型调用。

## 尚未验证

原楼宇时间锚点/时区、完整计量边界/回路独立性、真实位置/屋顶/设备参数、2017适用电价/其他收费、实测PV校准仍未核实。Windows命令已提供但未在Windows执行；真实浏览器视觉、年度优化性能、实际耗尽墙钟时限和新云快照恢复未验收。未扩展供冷/供热估算、多节点、全年规划或零碳认证。

本记录为本地验收；远程CI状态以对应PR的Checks为准。
