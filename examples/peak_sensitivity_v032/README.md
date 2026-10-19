# Q峰值处理假设实验：独立派生输入

这些是**原值基准及人为处理研究假设**，不是认定原数据错误，也不是校准后的实测。原始发布文件`../shanghai_2017/records.csv`保持不变。

- 原始用电数据作者：Tong Xiao、Peng Xu、Huajing Sha、Zhe Chen、Jiefan Gu（2022），[Zenodo 6590976](https://zenodo.org/records/6590976)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。仅选择test楼Q照明插座，未选择W；不称为全楼用电或实测全楼改造。
- NASA POWER实际同期UTC资源来源、获取时间和版本见`../shanghai_2017`；[NASA归属说明](https://power.larc.nasa.gov/docs/referencing/)。PV为pvlib气象估算；热负荷为参数化物理仿真。价格、排放因子、设备成本及经济参数为假设。没有给NASA套用CC许可。
- 三个目录各含完整8760小时`standardized.csv`及`treatment.json`。原值的小时kWh转换为区间平均kW；时间假设为北京时间区间起点。派生数据单位、数值与处理证据见treatment；统一字段见数据字典。
- `linear`仅把2017-01-13 00:00的4907.06kW按相邻未处理区间线性插值为242.43kW；`local_cap`仅把该点限制为900kW（原值前后24小时48个未处理点最大819.48kW向上取整到100kW）。没有修改其他点或时间。
- 每份派生记录保存原文件SHA、标准化父文件SHA、方法、处理点、原值/处理值与阈值；`manifest.json`保存实际导出文件的SHA。三组使用同一原值基准确定的容量边界与购电限制，未按处理后峰值重新定范围。
- 部分CSV浮点末位来自模型计算；哈希核对对应实际文件字节，不要求不同OS重新计算浮点CSV字节完全相同。关键指标复核采用求解及输入精度容差。

离线重建并真实求解（使用新空目录）：

```bash
python -m energy_agent.cli peak-study --bundle examples/shanghai_2017 --spec configs/peak_sensitivity_v032.json --output outputs/my_peak_study --time-limit 120
```

完整来源与边界沿用`../shanghai_2017/README.md`；实际实验结论、求解状态和独立检查见`../../docs/v032_evidence/peak_report.md`和`peak_study.json`。不通过改变电量形成“设备改善”结论，不判断真实峰值应是多少。
