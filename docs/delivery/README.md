# v0.1 交付包

本目录保存实际执行证据和完整168小时演示产物，与源码、依赖及测试一起纳入Git。此次交付不扩展业务功能；仅修正合成数据处理说明，并避免Markdown将小容差或残差显示为零。

## 直接查看

- [实际命令、输出和退出状态](verification.txt)：Python 3.12.14，依赖检查通过，**58项测试全部通过**，演示完成。
- [168小时Markdown报告](demo_168h/24bcc4660cf643de918a54cec0e0405a/report.md)
- [完整JSON结果与输入、来源、校验](demo_168h/24bcc4660cf643de918a54cec0e0405a/result.json)
- [方案对照CSV](demo_168h/24bcc4660cf643de918a54cec0e0405a/scenarios.csv)
- [逐时运行及工具记录目录](demo_168h/24bcc4660cf643de918a54cec0e0405a/)
- [可复算的统一格式任务](demo_task.json)
- [演示产物SHA-256清单](manifest.sha256)
- [PR描述](PR_DESCRIPTION.md)

运行ID：`24bcc4660cf643de918a54cec0e0405a`。所有文件路径以仓库根目录为基准。完整ZIP中的数据和报告可离线阅读；GitHub仓库中的Markdown可直接预览。

## 计算口径与方案取舍

全部为**合成演示数据**，随机种子42，168个一小时时段。价格、排放因子、成本及设备参数均为演示假设；不代表当地现行参数。电热负荷采用解析日周期加正态扰动后非负裁剪，光伏采用正弦包络乘有界均匀随机系数、夜间置零。

只比较本次有限候选，初始投资按新建项目计算，预算约束投资；运行费和排放仅对应这168小时，不乘52、不称为生命周期费用或全生命周期零碳。

|方案|投资（元）|168小时运行费（元）|运行排放（kgCO2e）|
|---|---:|---:|---:|
|D|800050.00|7002.16|5861.00|
|C|675850.00|7381.59|5833.93|
|B|486100.00|9235.27|6461.74|
|A|44500.00|12889.76|9195.69|

在本次评估的候选方案中，D运行费最低；C投资和排放均较低，不能将储能默认视为减排。所有方案逐时供能及独立约束校验通过，原始精度以JSON为准。

## 下载和复算

交付PR关联的分支保留完整源码树。GitHub仓库切换该分支后，使用 **Code → Download ZIP**；也可在提交页面下载该提交对应的归档。PR的Files changed用于审查本次增量，完整源码以分支/提交快照为准。

本聊天没有可上传二进制附件的工具，因此下载通过GitHub提供；最终回复提供固定提交的ZIP和从初始化提交开始的完整差异链接，不依赖云端内部路径。私有仓库需使用有仓库权限的GitHub登录。

```bash
bash scripts/setup.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m energy_agent.cli run --task docs/delivery/demo_task.json --output outputs/reproduced
.venv/bin/streamlit run app.py --server.headless true
# 检查版本控制中的演示产物
sha256sum -c docs/delivery/manifest.sha256
```

ZIP只包含Git跟踪文件，不包含`.venv`、真实`.env`、密钥、登录凭据或Git认证配置；`.env.example`仅为空值配置模板。

## 验收边界

模型适配器通过的是**本地模拟响应测试**，包括白名单、非法输出重试和无配置不联网；**真实模型接口未连接验证**。四项外部数据未读取或接入，完整年度MILP性能、真实墙钟超时、浏览器视觉验收和新云任务快照恢复未验收。Streamlit AppTest与服务健康检查通过，不将其等同于真实浏览器验收。

上一实现PR #1已由远端合并，此次另建交付PR，保持未合并。远程CI结果以交付PR的Checks为准；[验证说明](../validation.md)列出本地记录和上一提交的实际CI链接。
