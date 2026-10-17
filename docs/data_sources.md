# 数据来源、实际读取与使用条件（v0.2）

## 已实际取得和读取

|来源|实际文件/响应|已核实内容|条件与边界|
|---|---|---|---|
|[EnergyDetective Zenodo 6590976](https://zenodo.org/records/6590976)|`dataset_v2.zip`、成员README及`test_building/test_building_records.csv`|正式ZIP 26,354,282 bytes；发布MD5已核对；元数据`license.id=cc-by-4.0`；CSV 17,520行，Q/W各8,760小时，日期2017-01-01—12-31|CC BY 4.0；署名、链接许可、注明子集筛选与单位转换；不暗示作者背书。仅所选计量类别，不是已证实全楼计量|
|[发布方GitHub](https://github.com/XuPengResearchGroup/EnergyDetective2020)|固定提交`40a8c1a8e378155d0a3ed30f96ff5c99d4822053`的dataset/README、test CSV、ref_building_info.csv及一个EPW|README明确Time、Type、Record，Record为每小时kWh；Q=照明插座，W=暖通用电；GitHub与正式CSV仅换行差异|GitHub仓库本身未声明代码/数据许可，未给整个仓库套用Zenodo许可。案例使用已核实Zenodo档案；代码许可与数据许可分开|
|[NASA POWER Hourly](https://power.larc.nasa.gov/docs/services/api/temporal/hourly/)|UTC请求2016-12-31—2017-01-07的实际JSON；`ALLSKY_SFC_SW_DWN`、`T2M`、`WS10M`|API v2.10.3，UTC；GHI Wh/m²、T2M ℃、WS10M m/s；原响应192小时，选取同期开窗168小时|卫星/模型网格资源，不是楼宇实测。代表点31.23N/121.47E非建筑精确地址；详见引用条件和原始校验信息|
|[生态环境部/国家统计局2022因子公告](https://www.mee.gov.cn/xxgk2018/xxgk/xxgk01/202412/t20241226_1099413.html)|实际读取公告正文与表3|2022年上海省级电力平均因子0.5849 kgCO2/kWh，2024年发布，电力消费CO2核算参考|年份不等于2017，物质为CO2而非CO2e；没有自动用于当前案例。默认0.55 kgCO2e/kWh仍为人工情景|

正式ZIP SHA-256：`ae43c6fb205fb9442ab7ac8da7156afdf91767e06ed4a3252a2fa94c662c2fde`；发布MD5：`b54c73f1fb441db156b8e6cc7c7551b2`。

正式全年CSV SHA-256：`7a9f6158ca5d6102c72c24623bce7930fc57e16825a2803d8e55b66bd3bb78f9`。GitHub对应文件SHA：`790e028ff217265dba21508b3b4acfb22b02583d5c720f5031d35e2d3494c01b`；规范化CRLF后逐字节相同，未把两个原始文件的SHA混用。

已读取的ref_building_info.csv包含BuildingID、Space usage、Stair1、Stair2、Area、HVACType；本轮实际评估用匿名测试楼，不使用未经读取的reference负荷数值。reference负荷适配契约依据已读取的发布说明，并以人工格式样本测试，不声称所有楼宇都已验收。

### 核查中发现并保留的问题

- 发布说明只称Time为timestamp，没有明确区间起/止或时区。使用Asia/Shanghai与区间起点是显式假设，必须由调用者确认；没有改动历史日期。
- Q/W是发布方汇总类别，未提供电气回路图。对每个建筑、时间、类别查重；只有确认后才允许Q+W类别合计，仍不能称为全楼总电量。
- 发布方`CHN_Shanghai.Shanghai.583620_2017.epw`实际内部日期为2005年，`data_type=CSWD`；本轮未把它改成2017年参与评估，也不推断其具体形成原因。
- 价格、电压/用户类型、基本电费/需量费、设备成本、屋顶可装容量及真实楼宇位置未核实。已有暖通用电保留为电量；没有把它转为热需求或重复计入。

### 数据许可与引用

EnergyDetective数据：Tong Xiao、Peng Xu、Huajing Sha、Zhe Chen、Jiefan Gu (2022), *XuPengResearchGroup/EnergyDetective2020_dataset*, DOI [10.5281/zenodo.6590976](https://doi.org/10.5281/zenodo.6590976)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。随代码仅附带经许可的168小时子集，保留署名和改动记录；不附带全年原文件、楼宇图纸或私有元数据。

NASA POWER：已读取[Referencing Guide](https://power.larc.nasa.gov/docs/referencing/)。成果包含POWER Reference（NASA Langley Research Center POWER Project，由NASA Earth Science Division资助）与Data Reference（Hourly API v2.10.3及实际获取日期）。项目请求成果/再分发通知，本轮未发送任何外部通知。官网说明数据免费访问；未将NASA资源标为CC BY或楼宇实测。实际缓存与引用详见[案例清单](../examples/shanghai_168h/source_manifest.json)。

## 实际字段来源

|字段|类别|来源|
|---|---|---|
|electric_load_kw|实测与明确转换|正式CSV的Q/W小时kWh，除以1h；类别边界、时间锚点另作假设|
|pv_per_kw|模型估算|NASA同期网格资源+pvlib 0.16.1；安装角度/损耗与代表点为假设|
|electricity_price|人工假设或用户来源|示例为人工时段表；可提供严格对齐的逐时CSV并声明年份/费用范围|
|grid_emission_factor|人工假设|0.55 kgCO2e/kWh逐时常数，非官方2017因子、非实测逐时碳强度|
|heat_load_kw_th / gas_price / gas_emission_factor|明确停用占位|电侧模式为0，热设备容量为0；不是无热需求的事实|
|成本、效率、预算、场地与候选容量|人工假设|新增加的PV/储能增量投资，规模按实际峰值而不缩放负荷|

`Source`与`Artifact`记录URL、地区、时间、类别、处理、条件、版本、获取时间、文件/容器SHA和原发布校验；每个统一时序字段用source_ids映射，估算可追溯父来源。用户上传本地文件时，不假装已与远程版本比对。人工小样本显式标为artificial_fixture，只用于格式/风险测试。

## 仍仅登记，不编造接入

|来源|地区/类别|本轮状态|
|---|---|---|
|[瑞丽冷热电气负荷](https://www.nbsdc.cn/general/dataDetail?id=64edc551bb16e07753c33a6c&type=1)|中国瑞丽，建筑负荷仿真|未取得实际文件，字段/许可/样本量未知，不为其阻塞上海案例；供冷不在本轮范围|
|[NREL End Use Load Profiles](https://data.openei.org/submissions/4520)|国际，校准建筑仿真|仅登记，未读取具体文件，不声称有可用热负荷|
|[Calliope城市示例](https://calliope.readthedocs.io/en/latest/examples/urban_scale/)|国际，模型/示例|仅登记，未适配；不等同实测城市数据|

原v0.1合成来源demo-series、demo-market、demo-equipment、demo-conditions、demo-candidates保留，仍明确标为synthetic。导入有实测负荷但包含估算和假设时，整体显示“实测与假设混合案例”，不靠demo=False删除假设提示。
