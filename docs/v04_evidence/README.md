# v0.4 反事实修复证据

`summary.json` / `summary.md` 是第二次实际离线验收汇总；各 `*_repair.json` / `*_report.md` 包含范围、精度、原始状态、全部试探轨迹、独立校验和来源。`annual_first_limited_*` 单独保留首次全年实际超时可行见证，不把它伪装成已证明最优。

`*_request.json.gz` 保存完整实际授权输入（含确认基准）；`*_baseline_verification.json.gz` 是搜索预算内原任务复核；`*_witness.json.gz` 是对应路径最后采用的实际逐时RunResult。使用Python标准库解压，例如：

```python
import gzip, hashlib, json
from pathlib import Path

root = Path('docs/v04_evidence')
for item in json.loads((root/'archive_manifest.json').read_text(encoding='utf-8')):
    raw = gzip.decompress((root/item['archive']).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == item['raw_sha256']
    run_or_request = json.loads(raw)
```

`archive_manifest.json` 中的source是当时产物位置与获取线索，不承诺该内部路径在另一台机器上存在；文件下载请使用本目录的归档。解压SHA与repair.json中基准/见证文件SHA可交叉核对。

中间试探的完整逐时文件不全量归档，全部状态、数值、哈希及任务指纹仍在repair.json；给定请求可复现算法和独立重算。若要采用路径，请按 [方法文档](../counterfactual_method.md) 在本机新目录生成完整请求/运行文件，不能直接指望旧云端路径可写或存在。

6/24/168小时是人工合成数据；8760小时为上海Q实测＋仿真供热、NASA估算PV与人为参数的混合研究情景。来源与许可沿用 [上海全年数据说明](../../examples/shanghai_2017/README.md)，保留发布方EnergyDetective及NASA POWER归属，不声称这些是全楼实测供热或实测光伏。
