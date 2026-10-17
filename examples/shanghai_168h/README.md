# 实际外部文件：上海匿名办公楼168小时电侧案例

本目录是**实际取得数据的许可子集与捕获的NASA响应**，不是人工测试样本。来源和处理逐项见[source_manifest.json](source_manifest.json)。整个案例仍是**实测与假设混合案例**，不是工程投资决策结论。

- [实际评估报告](report.md) / [方案CSV](scenarios.csv) / [完整JSON](result.json)
- [原始计量许可子集](records.csv) / [统一数据](normalized.csv) / [任务](task.json)
- [Q窗口质量](quality_window_Q.md) / [W窗口质量](quality_window_W.md) / [Q整份质量](quality_full_Q.md) / [W整份质量](quality_full_W.md)
- [转换能量核对](energy_audit.json) / [原始NASA响应](nasa_power_response.json) / [字段来源](provenance.json)

## 实际来源、许可和改动

### EnergyDetective

Tong Xiao、Peng Xu、Huajing Sha、Zhe Chen、Jiefan Gu (2022), **XuPengResearchGroup/EnergyDetective2020_dataset**，DOI [10.5281/zenodo.6590976](https://doi.org/10.5281/zenodo.6590976)，[正式记录](https://zenodo.org/records/6590976)。已实际读取该记录元数据，许可为[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)。保留署名、许可链接并说明修改；不暗示原作者认可本项目结论。

正式ZIP：`dataset_v2.zip`，26,354,282 bytes。发布校验值`md5:b54c73f1fb441db156b8e6cc7c7551b2`已核对；SHA-256为`ae43c6fb205fb9442ab7ac8da7156afdf91767e06ed4a3252a2fa94c662c2fde`。

CSV成员`test_building/test_building_records.csv`的SHA-256为`7a9f6158ca5d6102c72c24623bce7930fc57e16825a2803d8e55b66bd3bb78f9`。本目录`records.csv`只抽取2017-01-01 00:00至2017-01-08 00:00（末端不含）的Q/W共336行，保留原字段、行序与数值字符串，仅统一换行符为LF；并非原始全年文件。处理后文件有独立校验值。

发布说明确认`Record`为每小时kWh，Q为照明插座，W为暖通用电。仅按发布方两类别合计，不称全楼总电量；文件没有电气回路图可以核实遗漏与回路重叠。**时间区间起点与Asia/Shanghai仍为显式假设**，没有把假设冒充发布方事实，也未改动2017年日期。W作为电负荷保留，不推算或重复增加热负荷。

### NASA POWER与光伏估算

The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division.

The data was obtained from the POWER Project's **Hourly API v2.10.3**, accessed on **2026-10-17T08:55:51.536164Z**. [实际请求](https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN%2CT2M%2CWS10M&community=RE&longitude=121.47&latitude=31.23&start=20161231&end=20170107&format=JSON&time-standard=UTC)，[官方小时API说明](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/)，[引用与再分发说明](https://power.larc.nasa.gov/docs/referencing/)。项目请求成果/再分发通知；本轮没有发送任何外部通知。该来源不套用EnergyDetective的CC BY许可。

原响应SHA-256：`9bde056e44b1dc75c8b25e8a9d5102f6d172be907ed4c4a2e8a43486e5cb6570`。请求UTC整日2016-12-31—2017-01-07，共192小时，严格选择2017-01-01—01-08北京时间的168小时；官方FAQ明确小时标签为区间起点。GHI单位Wh/m²每小时，除以1h成为平均W/m²；温度℃，风速m/s。资源来自卫星/模型网格，**不是楼宇气象或PV实测**。

代表点31.23°N、121.47°E仅为上海市级位置，非匿名楼宇地址；默认倾角20°、正南、损耗14%等是假设。pvlib 0.16.1通过中点太阳位置、Erbs、isotropic转置、Faiman温度和PVWatts DC/AC估算出力，见[模型说明](../../docs/model.md)。示例累计7.512929245142238 kWh/kW_DC，不把辐照直接当发电。

## 能量、边界与复现

实测类别合计90,087.69 kWh。转换差值1.4551915228366852e-11 kWh，容差0.0002 kWh；声明数值分辨率0.01 kWh，不是已核实仪表精度。源数值舍入不确定性上界1.68 kWh另列，不拿它掩盖转换误差。不插补、填零或删除异常，整份源文件与窗口质量分别报告。

只评估电网/新增PV/新增储能；供热零数组只是停用占位，不代表建筑没有供热需求或已得到保障。G基线新增投资为0，既有电网、照明和暖通设备不在增量投资中。价格、排放因子、设备成本和场地是[人工情景参数](parameters.json)，仅计按电量收费，不计需量费等费用。官方2022上海0.5849 kgCO2/kWh不是2017适用因子，默认保留0.55 kgCO2e/kWh假设，没有冒充官方CO2e。

在本次候选中，GPB运行费最低；GP投资和排放更低。168小时仅报告本时段，不乘52，不声称全局容量最优或零碳认证。

```bash
python -m energy_agent.cli data-replay --bundle examples/shanghai_168h --output outputs/replay
python -m energy_agent.cli data-replay --bundle examples/shanghai_168h --budget 0 --output outputs/budget0
```

命令离线校验全部文件SHA、重新解析原始子集和NASA响应、重新估算PV，再调用相同Agent与优化工具。更换预算产生新版本并重新求解；不复用旧推荐。原始全年文件和ZIP保留本地缓存，不随代码打包；本目录派生CSV仅将导出的CRLF换行统一为LF，未改动数值。
