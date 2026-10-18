"""Adapters for files actually inspected; cached public downloads retain checksums."""
import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd
from pydantic import Field

from .quality import IntervalContract, QualityReport, inspect_series, normalize_intervals, shanghai_timestamps
from .schemas import Artifact, Model, Source

PUBLISHER_VERSION = "40a8c1a8e378155d0a3ed30f96ff5c99d4822053"
PUBLISHER = "https://github.com/XuPengResearchGroup/EnergyDetective2020"
RAW_ROOT = f"https://raw.githubusercontent.com/XuPengResearchGroup/EnergyDetective2020/{PUBLISHER_VERSION}/"
RECORD_FILES = {"test": "dataset/test_building/test_building_records.csv", "reference": "dataset/ref_building/ref_building_records.csv"}


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch_cached(url: str, cache_dir: str | Path = "data_cache/raw", *, offline: bool = True,
                 expected_sha256: str | None = None, client: httpx.Client | None = None) -> tuple[Path, Artifact]:
    """Offline by default; caches must match their manifest, never trust stale bytes."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("仅允许不带认证信息的HTTPS数据地址")
    directory = Path(cache_dir)
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    filename = Path(parsed.path).name or "response.json"
    path = directory / f"{key}_{filename}"
    metadata = directory / f"{key}.manifest.json"
    if path.exists() and metadata.exists():
        artifact = Artifact.model_validate_json(metadata.read_text(encoding="utf-8"))
        if artifact.url != url or artifact.sha256 != sha256_file(path):
            raise ValueError(f"缓存完整性校验失败：{path}；请隔离损坏缓存后重新获取")
        if expected_sha256 and artifact.sha256 != expected_sha256:
            raise ValueError("缓存与指定原文件校验值不同")
        return path, artifact
    if offline:
        raise FileNotFoundError(f"离线缓存不存在或不完整：{url}。请显式联网获取；不会用人工数据替代。")
    directory.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    http = client or httpx.Client(timeout=60, follow_redirects=True)
    temp = path.with_name(path.name + ".part")
    try:
        with http.stream("GET", url) as response:
            response.raise_for_status()
            total = 0
            digest = hashlib.sha256()
            with temp.open("wb") as file:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > 80 * 1024 * 1024:
                        raise ValueError("单个数据文件超过80MiB限制")
                    digest.update(chunk)
                    file.write(chunk)
        checksum = digest.hexdigest()
        if expected_sha256 and checksum != expected_sha256:
            raise ValueError("下载文件与指定校验值不同")
        artifact = Artifact(url=url, filename=filename, sha256=checksum, retrieved_at=datetime.now(timezone.utc))
        temp.replace(path)
        metadata.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
        return path, artifact
    finally:
        temp.unlink(missing_ok=True)
        if owns_client:
            http.close()


def fetch_energydetective(dataset: str = "test", cache_dir: str | Path = "data_cache/raw", *, offline: bool = True):
    if dataset not in RECORD_FILES:
        raise ValueError("只支持已核查的test/reference逐小时CSV")
    docs, docs_artifact = fetch_cached(RAW_ROOT + "dataset/README.md", cache_dir, offline=offline)
    path, artifact = fetch_cached(RAW_ROOT + RECORD_FILES[dataset], cache_dir, offline=offline)
    return path, artifact, docs_artifact


def fetch_zenodo_energydetective(dataset: str = "test", cache_dir: str | Path = "data_cache/raw", *, offline=True):
    """The actually inspected record/archive. Verify published MD5 AND retain SHA-256."""
    if dataset not in RECORD_FILES:
        raise ValueError("只支持已核查的test/reference CSV成员")
    record_path, _ = fetch_cached("https://zenodo.org/api/records/6590976", cache_dir, offline=offline)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("id") != 6590976:
        raise ValueError("Zenodo记录ID与固定版本不同")
    entries = [f for f in record.get("files",[]) if f.get("key") == "dataset_v2.zip"]
    if len(entries) != 1:
        raise ValueError("Zenodo记录未包含唯一已核查的dataset_v2.zip，不猜测新格式")
    entry = entries[0]
    url = entry["links"]["self"]
    if urlparse(url).hostname != "zenodo.org":
        raise ValueError("档案下载链接不是Zenodo官方域名")
    archive_path, container = fetch_cached(url, cache_dir, offline=offline)
    published_checksum = entry.get("checksum", "")
    if not published_checksum.startswith("md5:"):
        raise ValueError("本适配器未支持此发布校验算法；不跳过发布方校验")
    if "md5:" + hashlib.md5(archive_path.read_bytes()).hexdigest() != published_checksum:
        raise ValueError("Zenodo发布校验值不符；停止使用该档案")
    license_id = "CC-BY-4.0" if record.get("metadata",{}).get("license",{}).get("id") == "cc-by-4.0" else "未知"
    member = RECORD_FILES[dataset].removeprefix("dataset/")
    outputs = []
    with zipfile.ZipFile(archive_path) as archive:
        for name in (member,"README.md"):
            if archive.namelist().count(name) != 1:
                raise ValueError(f"档案成员{name}缺失或重复，不自动选择替代文件")
            info=archive.getinfo(name)
            if info.file_size > 80*1024*1024:
                raise ValueError("解压成员超出80MiB限制")
            content=archive.read(name)
            checksum=hashlib.sha256(content).hexdigest()
            dest=Path(cache_dir)/f"zenodo6590976_{checksum[:16]}_{Path(name).name}"
            if dest.exists() and sha256_file(dest) != checksum:
                raise ValueError("已提取成员与档案校验值不符；不覆盖未知改动")
            if not dest.exists():
                dest.write_bytes(content)
            artifact=Artifact(url=url,filename=Path(name).name,sha256=checksum,retrieved_at=container.retrieved_at,
                member_path=name,container_sha256=container.sha256,publisher_checksum=published_checksum,license_id=license_id)
            outputs.append((dest,artifact))
    return outputs[0][0],outputs[0][1],outputs[1][1]


class MeterSelection(Model):
    building: str
    meters: list[str] = Field(min_length=1)
    timestamp_position: str = Field(pattern=r"^(start|end)$")
    acknowledge_category_sum: bool = False
    timestamp_assumption_acknowledged: bool = False
    data_kind: Literal["published", "artificial_fixture"] = "published"


@dataclass
class ImportedLoad:
    frame: pd.DataFrame
    selected_reports: list[QualityReport]
    whole_reports: list[QualityReport]
    audit: object
    source: Source
    boundary: str
    timestamp_note: str
    selection: MeterSelection
    raw_rows: int


class ImportQualityError(ValueError):
    def __init__(self, message: str, reports: list[QualityReport]):
        super().__init__(message)
        self.reports = reports


def read_energydetective(path: str | Path, selection: MeterSelection):
    """Inspect meter categories separately. Repeated (building,time,type) never sum."""
    selection = MeterSelection.model_validate(selection)
    frame = pd.read_csv(path, dtype={"Time": str, "Type": str})
    allowed = {"Time", "Type", "Record"}
    is_reference = "BuildingID" in frame.columns
    if is_reference:
        if frame.BuildingID.isna().any():
            raise ValueError("BuildingID存在缺失，不能猜测记录属于哪栋建筑")
        allowed.add("BuildingID")
    if set(frame.columns) != allowed:
        raise ValueError("仅支持已读取的EnergyDetective列Time、Type、Record及可选BuildingID；不接受未说明测点/额外列")
    if selection.building != "test" and not is_reference:
        raise ValueError("此文件是匿名测试楼，仅可选择building=test")
    if is_reference:
        frame = frame.loc[frame.BuildingID.astype(str) == selection.building].copy()
    if frame.empty:
        raise ValueError(f"建筑 {selection.building} 没有记录")
    if len(set(selection.meters)) != len(selection.meters) or not set(selection.meters) <= {"Q", "W"}:
        raise ValueError("只支持不重复的Q/W类别；不得把汇总类别重复计入")
    if not set(frame.Type.unique()) <= {"Q", "W"}:
        raise ValueError("文件含未知测点类别，不能猜测其与Q/W的关系")
    if len(selection.meters) > 1 and not selection.acknowledge_category_sum:
        raise ValueError("Q+W仅可作为发布方类别合计，需显式确认该边界，不能称为全楼总电量；如不确定请选择单一类别")
    if not selection.timestamp_assumption_acknowledged:
        raise ValueError("发布说明未明确起点/终点与时区；需显式确认Asia/Shanghai及区间锚点假设")
    if not set(selection.meters) <= set(frame.Type.unique()):
        raise ValueError("所选Q/W类别缺少全部记录")
    # File interleaves Q/W at each time. Sorting each category is an explicit, logged operation.
    frame["timestamp"] = shanghai_timestamps(frame.Time, "Asia/Shanghai")
    return frame.sort_values(["timestamp", "Type"], kind="stable")


def import_energydetective(path: str | Path, selection: MeterSelection, *, start: str | None = None,
                           hours: int = 168, artifact: Artifact | None = None,
                           documentation: Artifact | None = None, retain_flagged_jumps: bool = False) -> ImportedLoad:
    if not isinstance(hours, int) or hours < 1:
        raise ValueError("窗口小时数必须为正整数")
    raw = read_energydetective(path, selection)
    selected = raw.loc[raw.Type.isin(selection.meters)].copy()
    whole = []
    for meter in selection.meters:
        group = selected.loc[selected.Type == meter]
        whole.append(inspect_series(group.timestamp, group.Record, step_minutes=60, timezone="Asia/Shanghai", scope=f"整份原始文件/建筑{selection.building}/{meter}"))
    if any(r.invalid_timestamps for r in whole):
        raise ImportQualityError("存在无法定位的原时间；不能假设它在所选窗口外而忽略，请先核查Time字段", whole)
    if start:
        begin = shanghai_timestamps([start], "Asia/Shanghai")[0]
        if pd.isna(begin) or begin != begin.floor("h"):
            raise ValueError("逐小时窗口起点必须为可解析的整点；不自动移动或重编号时间")
    else:
        # Prefer a fully good window. Do not renumber, drop, interpolate or alter dates.
        begin = None
        possible = selected.timestamp.dropna().drop_duplicates().sort_values()
        offset = pd.Timedelta(hours=1) if selection.timestamp_position == "end" else pd.Timedelta(0)
        for label in possible:
            candidate = label - offset
            end = candidate + pd.Timedelta(hours=hours)
            window = selected.loc[(selected.timestamp >= candidate + offset) & (selected.timestamp < end + offset)]
            reports = [inspect_series(g.timestamp, g.Record, step_minutes=60, timezone="Asia/Shanghai", scope=str(m)) for m,g in window.groupby("Type")]
            if len(reports) == len(selection.meters) and all(r.records == hours and r.valid for r in reports):
                begin = candidate
                break
        if begin is None:
            raise ImportQualityError("未找到无缺失、重复、负值、非有限值或跳变告警的连续窗口；请查看原始质量报告", whole)
    end = begin + pd.Timedelta(hours=hours)
    # When raw timestamps denote interval ends, select ends corresponding to requested starts.
    offset = pd.Timedelta(hours=1) if selection.timestamp_position == "end" else pd.Timedelta(0)
    window = selected.loc[(selected.timestamp >= begin + offset) & (selected.timestamp < end + offset)]
    reports, frames, audits = [], [], []
    for meter in selection.meters:
        group = window.loc[window.Type == meter]
        report = inspect_series(group.timestamp, group.Record, step_minutes=60, timezone="Asia/Shanghai", scope=f"所选窗口/{selection.building}/{meter}")
        reports.append(report)
        errors = [f for f in report.findings if f.severity == "error"]
        retained_warning = retain_flagged_jumps and not errors
        if (not report.valid and not retained_warning) or report.records != hours:
            raise ImportQualityError(f"{meter}窗口不合格，需完整{hours}小时。\n" + report.markdown(), whole + reports)
        contract = IntervalContract(quantity="interval_kwh", source_step_minutes=60,
            timestamp_position=selection.timestamp_position, source_timezone="Asia/Shanghai", numeric_precision=0.01)
        normalized, audit = normalize_intervals(group.timestamp, group.Record, contract)
        frames.append(normalized.set_index("timestamp").electric_load_kw)
        audits.append(audit)
    combined = pd.concat(frames, axis=1)
    if combined.isna().any().any() or len(combined) != hours:
        raise ValueError("Q/W时间未严格对齐，禁止隐式outer join后补零")
    frame = pd.DataFrame({"timestamp": combined.index, "electric_load_kw": combined.sum(axis=1).to_numpy()})
    before, after = sum(a.raw_energy_kwh for a in audits), float(frame.electric_load_kw.sum())
    audit = audits[0].model_copy(update={"raw_energy_kwh": before, "normalized_energy_kwh": after,
        "difference_kwh": after-before, "tolerance_kwh": sum(a.tolerance_kwh for a in audits),
        "source_rounding_bound_kwh": sum(a.source_rounding_bound_kwh for a in audits),
        "passed": abs(after-before) <= sum(a.tolerance_kwh for a in audits)})
    boundary = ("Q照明与插座" if selection.meters == ["Q"] else "W暖通用电" if selection.meters == ["W"] else "Q照明插座与W暖通用电的发布方类别合计")
    boundary += "；仅所选计量边界，不声称全楼总电量；无电气回路图可独立核实重叠或遗漏"
    note = f"发布方只称Time为timestamp，未明确区间锚点/时区；本次显式假设原时间为Asia/Shanghai、区间{selection.timestamp_position}；转换后为区间起点，不改历史年份"
    verified_download = artifact is not None
    artifact = artifact or Artifact(url="本地导入文件；与发布方固定版本的内容一致性未核验", filename=Path(path).name, sha256=sha256_file(path))
    if artifact.sha256 != sha256_file(path):
        raise ValueError("输入文件与来源校验值不一致")
    artificial = selection.data_kind == "artificial_fixture"
    source = Source(source_id="energydetective-load", name=("人工格式测试样本（非真实数据）" if artificial else "EnergyDetective实测用电") + f"/建筑{selection.building}/{' + '.join(selection.meters)}", region="人工样本，无真实地区" if artificial else "中国上海；匿名办公楼精确位置未知",
        time_range=f"{begin.isoformat()}至{end.isoformat()}（末端不含）", category="synthetic" if artificial else "measured", units={"raw.Record": "kWh/一小时间隔", "electric_load_kw": "kW"},
        url=PUBLISHER + "/tree/" + PUBLISHER_VERSION + "/dataset", version=PUBLISHER_VERSION if verified_download else "本地文件；远程对应版本未知",
        artifacts=[artifact] + ([documentation] if documentation else []),
        processing=[note, f"原文件建筑筛选={selection.building}；类别={selection.meters}；对每类按原时间稳定排序；检查(time,type)重复，未去重",
            "按发布方README把Record解释为每小时电量，除以1h得到区间平均kW；未缩放实测负荷，未插补、删点或填零",
            f"异常跳变策略：{'显式保留全部跳变，研究情景未经测点核实；不代表质量告警解除' if retain_flagged_jumps else '选中窗口拒绝跳变'}",
            "输入数值分辨率按0.01kWh声明用于核对，不代表已核实仪表精度；浮点长尾保留", audit.model_dump_json()],
        conditions="发布方GitHub仓库未声明许可证；本次实际读取公开文件做本地验证，未确认再分发条件，原始及逐时派生数据不提交公共仓库。Zenodo元数据尚待核实。")
    if not verified_download and not artificial:
        source.name = "用户提供EnergyDetective格式文件（声明实测，未与远程文件比对）/" + selection.building
        source.conditions = "本地导入文件，实测属性与使用权由用户声明；原发布链接、获取时间和版本一致性未核实。格式解释参考发布方文档，不声称实际从该发布页下载。"
    if verified_download and artifact.license_id == "CC-BY-4.0":
        source.url = "https://zenodo.org/records/6590976"
        source.version = "Zenodo 6590976 / DOI 10.5281/zenodo.6590976 / dataset_v2.zip"
        source.conditions = "已读取Zenodo记录metadata.license.id=cc-by-4.0；引用Xiao、Xu、Sha、Chen、Gu（2022），DOI 10.5281/zenodo.6590976，CC BY 4.0。派生数据需署名、链接许可并说明转换；本案例仅计量边界分析，不代表全楼完整计量。"
    if artificial:
        source.url = None
        source.version = "人工格式测试样本，不代表外部数据验收"
        source.conditions = "人工构造、仅用于测试；不得当成真实测量或网络获取证据"
        source.artifacts = [Artifact(url="人工生成的测试样本", filename=Path(path).name, sha256=sha256_file(path))]
    return ImportedLoad(frame, reports, whole, audit, source, boundary, note, selection, len(raw))
