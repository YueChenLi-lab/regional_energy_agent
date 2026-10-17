"""Verify a licensed, captured external-data case and replay it without network."""
import hashlib
import json
from pathlib import Path

import numpy as np

from .adapters import MeterSelection, import_energydetective
from .data import validate_inputs
from .schemas import TaskRequest
from .solar import SolarSettings, estimate_pv, parse_nasa_hourly


def load_case_bundle(directory: str | Path) -> TaskRequest:
    root = Path(directory).resolve()
    manifest = json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "regional-energy-case-v1":
        raise ValueError("未支持的案例包版本")
    required = {"records.csv", "nasa_power_response.json", "task.json", "parameters.json", "source_manifest.json", "result.json"}
    if not required <= set(manifest.get("files",{})):
        raise ValueError("案例包未列出必要文件校验值")
    for relative, checksum in manifest["files"].items():
        path = (root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("案例包路径无效或缺少文件：" + relative)
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise ValueError("案例包校验失败：" + relative)
    task = TaskRequest.model_validate_json((root/"task.json").read_text(encoding="utf-8"))
    checked = validate_inputs(task)
    if not checked.ready:
        raise ValueError("案例任务不完整：" + checked.model_dump_json())
    provenance = json.loads((root/"source_manifest.json").read_text(encoding="utf-8"))
    load = import_energydetective(root/"records.csv",MeterSelection.model_validate(provenance["selection"]),
        start=task.data.timestamps[0].isoformat(),hours=len(task.data.timestamps))
    if list(load.frame.timestamp) != task.data.timestamps or not np.allclose(load.frame.electric_load_kw,task.data.electric_load_kw,atol=1e-8,rtol=0):
        raise ValueError("原始许可子集转换后与任务用电不符")
    settings = SolarSettings.model_validate(json.loads((root/"parameters.json").read_text(encoding="utf-8"))["solar"])
    weather = parse_nasa_hourly(root/"nasa_power_response.json",task.data.timestamps,settings)
    pv = estimate_pv(weather,settings)
    if not np.allclose(pv,task.data.pv_per_kw,atol=1e-10,rtol=0):
        raise ValueError("原资源重新估算与案例PV出力不符")
    return task
