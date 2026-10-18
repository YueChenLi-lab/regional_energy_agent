# 上海2017全年许可输入：离线重放

这是**实测与假设混合研究案例**，不是实测全楼改造。

- `records.csv`：Zenodo dataset_v2.zip 内 test_building/test_building_records.csv 的完整字节，含Q/W各8760小时。当前只选Q照明插座；W不进入电侧或电热研究。
- 数据作者：Tong Xiao、Peng Xu、Huajing Sha、Zhe Chen、Jiefan Gu（2022）。[DOI 10.5281/zenodo.6590976](https://zenodo.org/records/6590976)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。原数据未改；解析小时kWh为平均kW，时间起点/北京时间是假设，2个Q跳变原值保留且未核实。
- `publisher_README.md`为正式档案内说明原字节，`source_manifest.json`保留父ZIP SHA/发布MD5、成员SHA、获取时间及许可；`manifest.json`校验输入字节。
- `95d1d9061ffd6002_point`：NASA POWER实际UTC响应，API v2.10.3，市级代表点31.23N121.47E；获取时间与原始请求链接在同名缓存manifest。按[官方Referencing Guide](https://power.larc.nasa.gov/docs/referencing/)保留归属与版本；NASA POWER提供公开资源，未自行套用CC许可。只选取对应北京时间2017全年，不改年、不补值。PV为pvlib估算，非实测楼宇PV。
- 价格、排放因子、经济参数、场地/设备规模以及供热物理模型参数均为研究假设。供热研究完全排除W以避免重复，不含供冷/热水/全楼完整服务，也不包含设备隐含排放。

```bash
python -m energy_agent.cli annual-build --bundle examples/shanghai_2017 --retain-flagged-jumps --output outputs/annual_electric --run
python -m energy_agent.cli annual-build --bundle examples/shanghai_2017 --heat --retain-flagged-jumps --output outputs/annual_heat --run
python -m energy_agent.cli plan-study --task outputs/annual_heat/task.json --scans 3 --output outputs/study --time-limit 60
```

不需要网络或模型。默认拒绝跳变，开关表示接受原值的研究风险，不代表已消除质量问题。详细参数、能源边界与限制见 `docs/annual_planning.md`；实际计算证据见 `docs/v03_validation.md`。168小时旧案例独立保留。
