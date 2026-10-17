# v0.1 实际验证记录

验证环境：Python 3.12.14，项目独立 `.venv`；依赖完整版本见 `requirements.lock.txt`。未修改全局 Python。下列命令记录来自云工作区实际执行；GitHub CI结果另有运行链接，新云任务快照恢复尚未验收。

## 执行与结果

| 实际命令或检查 | 结果 |
| --- | --- |
| `bash scripts/setup.sh` | 安装/重复安装锁定依赖及可编辑项目成功 |
| `.venv/bin/python -m pip check` | No broken requirements found |
| `.venv/bin/python -m pytest -q` | **58 passed**，无跳过、无预期失败 |
| `.venv/bin/python -m energy_agent.cli demo --output outputs/final --task-out outputs/final_task.json` | 168小时、四候选全部 optimal，独立校验全通过，三类导出成功 |
| `energy_agent.cli revise --run <基准结果JSON> --budget 50000 --output outputs/revised` | 新run_id，版本1→2，重新计算后仅A可行，推荐D→A，保存前后差异 |
| `energy_agent.cli demo --budget 0 --output outputs/no-budget` | 四候选全部预算预检查拒绝，没有可行推荐，正常导出报告 |
| `energy_agent.cli demo --emission-limit 0 --output outputs/no-carbon` | 四候选运行模型全部不可行，没有伪装可行的负荷削减 |
| `.venv/bin/streamlit run app.py --server.headless true --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false` | 服务实际启动 |
| `curl --fail --silent --show-error http://127.0.0.1:8501/_stcore/health` | `ok` |
| Streamlit AppTest（包含在 pytest 中） | 实际加载案例、求解、下载入口、预算修改、版本变更、无模型配置提示、零排放上限刷新均通过 |
| `git diff --check` | 通过 |

CLI 表中简写的 `energy_agent.cli` 均通过 `.venv/bin/python -m energy_agent.cli` 执行。

最新交付再次执行上述测试，仍为 **58 passed**。完整命令输出、可复算任务和168小时报告已提交至 [交付目录](delivery/README.md)。

上一实现提交 `ad6249f` 的远程 [push CI](https://github.com/YueChenLi-lab/regional_energy_agent/actions/runs/38903493834) 与 [PR CI](https://github.com/YueChenLi-lab/regional_energy_agent/actions/runs/38903560825) 均已通过。交付补充提交的状态以对应PR检查为准。

## 固定种子42的168小时结果

所有数值为**合成演示数据**与演示假设下的该时段结果。

| 方案 | 新建投资（元） | 评估期运行费（元） | 评估期排放（kgCO2e） | 运行费排名 |
| --- | ---: | ---: | ---: | ---: |
| D 光伏＋储能＋热泵＋辅助锅炉 | 800050.00 | 7002.16 | 5861.00 | 1 |
| C 光伏＋热泵＋辅助锅炉 | 675850.00 | 7381.59 | 5833.93 | 2 |
| B 光伏＋电网＋锅炉 | 486100.00 | 9235.27 | 6461.74 | 3 |
| A 电网＋锅炉 | 44500.00 | 12889.76 | 9195.69 | 4 |

在本次评估的候选方案中，D运行费最低；C投资和排放均低于D。该取舍来自分时电价、电池损耗与固定排放因子的共同作用，不能把储能自动解释为减排。投资与运行费不相加为生命周期成本，也不将168小时结果外推全年。

## 测试证据覆盖

- 逐时电热平衡、COP、锅炉效率与燃气LHV口径、设备容量、PV可用量及弃光、购电上限。
- SOC下限/上限/初始/终端/递推、充放电二进制模式、无同时充放电、无法消耗初始储能获益。
- 人为篡改功率、燃气、COP、弃光、SOC会被独立校验检出并排除推荐。
- 预算全拒绝、热容量不足、购电/场地限额、零碳上限无解；绑定碳上限会真实改变燃气与热泵运行。
- 任意等间隔时步：半小时算例按步长正确计算能量和费用；8760点输入生成与质量校验通过（没有声称年度MILP性能验收）。
- 固定种子与输入重算的关键指标一致；预算和需求倍数修改产生新版本及真实指标变化。
- 缺失、重复、时间间隔、无时区、单位错误、负值、非有限值、PV越界、未知来源、未支持需求均会拒绝或给出待补项。
- 模型工具白名单、非法输出有限重试、未支持需求保留、不泄漏服务响应/密钥、无配置不联网。使用本地HTTP模拟响应，不请求真实模型。
- 错误输入仍保留合法版本/来源；求解选项写入结果；最终JSON包含报告工具日志及文件位置；CSV按真实排名排列。

## 尚未验证或不属于本版

- 真实LLM服务、四项外部数据格式及实际地区参数未接入；API兼容性只通过本地模拟测试。
- 超时“有解/无解”分支通过模拟求解器返回状态验证，未以耗尽墙钟时间作真实超时验收。
- 完整年度MILP性能、真实浏览器视觉/交互验收、新云任务恢复尚未验收。
- 供冷、管网、多节点、空间选址、故障备用、生命周期评价等范围见模型说明与路线，不属于v0.1已实现能力。


后续v0.2结果见[v0.2验证记录](v02_validation.md)：97项测试通过，含本页原58项。
