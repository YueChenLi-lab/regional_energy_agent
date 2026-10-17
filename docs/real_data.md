# v0.2 第一阶段：真实文件、质量与可追溯电侧评估

本轮实际运行了一个正式外部文件案例，没有用人工小样本代替网络与真实样本验收。代码同时保留v0.1合成电热流程；单Agent与原优化/独立校验共用。

## 从实际文件开始

读取发布方固定GitHub说明和CSV后，又实际下载[Zenodo 6590976](https://zenodo.org/records/6590976)正式`dataset_v2.zip`，核对发布MD5并保存SHA-256。档案元数据许可为CC BY 4.0；正式CSV与GitHub固定版本仅CRLF差异，分别保存原始哈希，没有把规范化后的哈希冒充原文件哈希。字段、类别、单位与未知项详见[来源清单](data_sources.md)。

选用匿名测试办公楼（原文件不含BuildingID，适配器标为test），2017-01-01 00:00起连续168小时。Q/W各168条，窗口无缺失、重复、非法/负值或跳变告警。Q照明插座，W暖通，Record为小时kWh，除以1h成为平均kW；**W不转成热需求**。Q+W仅为发布方类别合计，需要显式确认；没有回路图证明全楼覆盖与电气无重叠，故不称全楼总电量。

原Time起止与时区未被发布说明明确：本例假设北京时间区间起点，保留原始历史日期，并在来源、界面、任务和报告中记录。系统也支持显式终点输入，按原步长向前移动区间锚点，不重新编号或换年。

正式文件中存在窗外跳变告警；全文件与选中窗口分别输出，未以删除异常行制造完整数据。发布方名为2017的EPW内部实际为2005/CSWD，不用于同期评估。未猜测形成原因或强改日期。

## 已实现的数据流程

- `adapters.py`：只适配实际读取过/说明中已核对的Time、Type、Record及可选BuildingID。对测点类别/重复组合、未知列和不确定类别合计给出原因。单建筑先筛选，禁止跨楼求和。原文件和处理产物分开保存。
- `quality.py`：原始与窗口记录数、时间范围、步长、重复、缺失、负值、非有限值、跳变；同时生成中文Markdown与JSON。无法定位的Time直接拒绝，不能假设在窗口外。自动选择质量合格连续窗口，不填零、不插值、不默认删除异常。跳变规则“相邻变化>100输入单位且较大值>8倍较小值”只为审查，不是设备故障断言。
- 功率按时长积分、电量求和、累计表相邻差分，完整区间降采样并核对能量。累计读数下降、部分目标区间、未对齐边界和隐含上采样都拒绝。`IntervalContract`明确quantity、单位口径、源时区、步长、起止及数值分辨率。
- `real_case.py`：实测负荷保持原值；由峰值与可修改比例生成G/GB，资源可用时再增加GP/GPB。设备只计新增PV/储能与安装，既有电网和原有照明/暖通不在增量投资范围。电侧停用供热与燃气，热设备容量为0；零数组不证明无热需求或已保障供热。
- `solar.py`：NASA UTC小时请求与JSON缓存，严格校验坐标、单位、填充值、时间覆盖；源Wh/m²/1h成为平均W/m²。用pvlib的太阳位置、Erbs、isotropic、Faiman和PVWatts子模型估算PV。T2M/WS10M代表2m温度/10m风速，作为环境近似，未做现场高度或入射角光学校准，统一系统损耗为假设。
- `Source`/`Artifact`：发布URL/版本、时间地区、输入字段与来源映射、SHA、容器/成员、发布校验、获取时间、已核实许可和处理记录；估算保留父资源/参数来源。没有把demo=False当成真实工程标签。
- `replay.py`：离线验证许可案例所有文件SHA，重新解析原始子集和NASA原响应、重新估算PV，之后再实际求解。不是读取旧推荐并改报告文字。

## 同期光伏、价格与排放

NASA API实际响应为v2.10.3，UTC整日返回192小时；转换至Asia/Shanghai后选取与负荷同窗的168小时。官方FAQ明确小时标签为区间起点；LST不会被当成北京时间。31.23N/121.47E是市级代表点，不是匿名楼宇精确位置，网格资源也不是气象站/屋顶实测。

默认光伏安装倾角20°、朝向正南、损耗14%、逆变器效率0.96等为可修改假设。原响应、参数、计算方法和父来源已保存；得到7.512929245142238 kWh/kW_DC的168小时估算产出，未把辐照数值直接当出力。

示例价格是人工时段情景（00–07:0.38；07–17、22–24:0.72；17–22:1.15元/kWh），并非已核实的上海2017或现行电价。明确用户类别未核实、仅计算按电量收费，未计基本电费、需量费和其他收费。支持JSON时段表及严格对齐的逐时电价CSV。

已实际核查官方2022年上海因子0.5849 kgCO2/kWh，但不自动回填2017或改称CO2e。默认案例保留0.55 kgCO2e/kWh人为情景。若用户提供CO2因子，必须声明emission_species=CO2并使用kgCO2单位，报告和无解说明不混淆。年度平均或情景常数展开为逐时常数，不代表实测逐时碳强度。

## 运行方式

Windows已有Conda环境：

```powershell
conda activate regional-energy
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
python -m energy_agent.cli data-replay --output outputs/replay
python -m streamlit run app.py
```

云端：

```bash
bash scripts/setup.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m energy_agent.cli data-replay --output outputs/replay
.venv/bin/streamlit run app.py --server.headless true
```

下载正式档案并自行选择窗口：

```bash
.venv/bin/python -m energy_agent.cli data-fetch --provider zenodo --online
.venv/bin/python -m energy_agent.cli data-import --provider zenodo --building test --meters Q,W --acknowledge-category-sum --timestamp-position start --acknowledge-time-assumption --start 2017-01-01 --hours 168 --parameters configs/electric_assumptions.json --with-solar --online --output outputs/custom_case --run
```

`--online`仅在明确获取时使用。缓存存在后不带它可离线导入；已缓存文件与清单哈希不符时拒绝使用，不关闭TLS/跳过校验。缓存缺失不会用合成数据替代。NASA暂不可用时，明确未完成的PV候选，仅继续电网/储能；输出目录非空时不覆盖。

本地已取得CSV可用`--records <路径>`；其真实性与下载时间若无法验证会如实标注本地文件，不声称从发布方下载。reference使用`--dataset reference --building <实际ID>`，实际楼宇负荷验收仍限本例test。人工样本必须使用`--artificial-fixture`，不能作为真实样本验收证据。

逐时电价：`--tariff-csv prices.csv --price-description '地区、适用年份、用户类别、仅电量费用/含哪些费用、是否假设'`。价格CSV恰有timestamp、yuan_per_kwh两列，不自动填缺或重采样。缺少预算时保存质量/任务并返回结构化待补项；本例参数文件是显式选择的人为情景。

## 中文界面

保留“合成演示”，新增“外部数据导入（电侧）”。选择Zenodo/GitHub获取渠道、建筑、计量类别、窗口、起止与时区声明；先显示原文件和负荷预览、中文质量摘要及能量差值。未通过校验或未确认情景参数时不能评估。详细来源/JSON折叠；可下载电负荷CSV、完整统一CSV、质量Markdown/JSON与优化结果。

填写预算、电网/场地、分时价格、排放物质及因子、设备成本和储能规模后实际求解。修改预算生成新版本、重新计算并展示差异；不缩放原始实测负荷迁就设备。不对零热曲线显示“已保障供热”。

## 验收与限制

- [实际捕获案例与完整报告](../examples/shanghai_168h/README.md)：经许可真实子集及NASA响应，默认测试对它做无网络重放和实际优化。
- `test_importing.py`、`test_solar_import.py`、`test_zenodo_cache.py`、`test_import_ui.py`使用**人工格式/传输样本**覆盖坏数据与界面，不冒充外部数据。
- Zenodo/NASA真实请求、文件校验与正式168小时计算属于单独的实际样本验收，详见[本轮验证证据](v02_validation.md)。真实模型适配器仍只有模拟测试，未连接真实LLM。
- 未核实：建筑精确坐标/电气回路、Time原始区间锚点、2017适用价格及费用、现场设备成本/屋顶/效率；未做PV实测校准、真实浏览器视觉验收、Windows实际运行、完整年度MILP性能或真实墙钟超时验收。
- 未扩展供热推算、供冷服务、多节点、全年规划、售电、生命周期或零碳认证；所有结论限定本次候选和评估时段。
