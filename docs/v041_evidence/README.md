# v0.4.1 实际矩阵与证据

本目录仅保存本轮新证据，不覆盖v0.4.0或v0.3.2归档。

- `summary.md` / `summary.json`：24小时3×4及8760小时2×3实际重算摘要。
- `*_result.json`、`*_matrix.csv`、`*_report.md`：完整费用/后悔/状态、来源与中文解释。
- `*_request.json.gz`：完整请求，含确认基准与原容量边界、数据/参数来源。
- `*_<配置>_<情景>_run.json.gz`：每个单元真实RunResult逐时解；保留实际run_id、输入版本、原状态和独立校验，不是预置回答。
- `manifest.json`：上述数值归档的SHA256；`verification.json` 为重新读取后18个单元的复核结果。
- `competition_regret_*.png`：真实Chromium浏览器截图（如存在）；168小时合成案例与已计算矩阵，不能当作全年截图。`browser_observation.txt`为同一页面可见文字快照。

归档JSON中的绝对 `result_file`/`files` 是当时运行位置，不是用户机器可用的下载路径。对应见证使用本目录确定命名规则查找，复核脚本不依赖原绝对路径。所有数据来自既有公开离线包或合成数据，不含虚拟环境、密钥或登录凭据。

```bash
python scripts/archive_regret_evidence.py --output docs/v041_evidence
```

此命令校验归档文件SHA，重建每个情景/配置的预期输入并检查一致性，重新独立核对物理约束、容量指纹、NPV/购能费及原求解目标，重算后悔矩阵；不运行MILP或调用模型。实际新求解另见 `scripts/run_regret_cases.py --annual`。

24小时采用合成电热负荷；8760小时采用上海test楼Q照明插座局部实测、NASA资源估算PV、参数化仿真供热及假设价格/设备/经济参数。保留原Q异常峰值，不称全楼实测改造或工程预测；原W不参与供热推算。20年、5%折现、重复2017代表年仅研究假设，运行排放未折现，未做设备隐含排放核算。详细使用条件沿用 `examples/shanghai_2017` 和 `docs/data_sources.md`。
