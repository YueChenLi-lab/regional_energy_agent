"""Reproducible real-data acquisition/conversion commands, separate from demo."""
import json
from pathlib import Path

import httpx

from .adapters import (Artifact, ImportQualityError, MeterSelection, PUBLISHER, PUBLISHER_VERSION,
                       fetch_energydetective, fetch_zenodo_energydetective, import_energydetective, sha256_file)
from .agent import EnergyAgent
from .data import case_label, validate_inputs
from .quality import save_quality
from .real_case import ElectricCaseParameters, build_electric_task, export_import, load_hourly_tariff
from .schemas import RunState, Source


def register_import_commands(commands):
    replay = commands.add_parser("data-replay", help="校验随代码附带的许可真实案例，离线重新优化（不发网络请求）")
    replay.add_argument("--bundle", type=Path, default=Path("examples/shanghai_168h"))
    replay.add_argument("--budget", type=float)
    replay.add_argument("--output", type=Path, default=Path("outputs/real_replay"))
    fetch = commands.add_parser("data-fetch", help="显式联网获取发布方固定版本CSV与说明，默认仅离线校验缓存")
    fetch.add_argument("--dataset", choices=["test", "reference"], default="test")
    fetch.add_argument("--provider", choices=["zenodo", "github"], default="zenodo")
    fetch.add_argument("--cache", type=Path, default=Path("data_cache/raw"))
    fetch.add_argument("--online", action="store_true")
    convert = commands.add_parser("data-import", help="EnergyDetective实际格式→质量报告与电侧任务")
    convert.add_argument("--records", type=Path, help="已下载的原始CSV；不提供时从缓存加载")
    convert.add_argument("--dataset", choices=["test", "reference"], default="test")
    convert.add_argument("--provider", choices=["zenodo", "github"], default="zenodo")
    convert.add_argument("--building", default="test", help="test或reference文件中的实际BuildingID")
    convert.add_argument("--meters", default="Q", help="Q、W或Q,W；后者需显式确认边界")
    convert.add_argument("--acknowledge-category-sum", action="store_true")
    convert.add_argument("--timestamp-position", choices=["start", "end"], required=True)
    convert.add_argument("--acknowledge-time-assumption", action="store_true")
    convert.add_argument("--artificial-fixture", action="store_true", help="明确标记人工格式样本，不作为真实数据验收")
    convert.add_argument("--start", help="所需北京时间区间起点；不指定时选择首个质量合格连续窗口")
    convert.add_argument("--hours", type=int, default=168)
    convert.add_argument("--parameters", type=Path, help="明确标记的人为情景参数JSON")
    convert.add_argument("--budget", type=float, help="初始新增设备预算，元")
    convert.add_argument("--with-solar", action="store_true", help="尝试NASA缓存/显式联网；失败时保留基线并列明未完成")
    convert.add_argument("--cache", type=Path, default=Path("data_cache/raw"))
    convert.add_argument("--online", action="store_true")
    convert.add_argument("--tariff-csv", type=Path)
    convert.add_argument("--price-description", help="逐时价格的地区/年份/用户类别/费用范围及是否假设")
    convert.add_argument("--output", type=Path, default=Path("outputs/imported"))
    convert.add_argument("--run", action="store_true", help="导入校验后调用原Agent实际优化与导出")


def handle_import_command(args) -> int:
    try:
        if args.command == "data-replay":
            from .replay import load_case_bundle
            from .agent import revise_task
            from .schemas import RunResult, TaskPatch
            task = load_case_bundle(args.bundle)
            previous = None
            if args.budget is not None:
                previous = RunResult.model_validate_json((args.bundle/"result.json").read_text(encoding="utf-8"))
                task = revise_task(task,TaskPatch(budget_yuan=args.budget),previous.run_id)
            result = EnergyAgent(args.output).run(task,previous=previous)
            print(case_label(result.task),f"run_id={result.run_id} 输入版本={result.input_version} 状态={result.state}")
            if result.comparison:
                print(result.comparison.explanation)
            print(json.dumps({s.candidate.candidate_id:s.validation.metrics.model_dump() if s.validation.metrics else {"status":s.dispatch.status} for s in result.scenarios},ensure_ascii=False,indent=2))
            print(json.dumps(result.files,ensure_ascii=False,indent=2))
            return 0 if result.state == RunState.COMPLETED else 2
        if args.command == "data-fetch":
            fetcher = fetch_zenodo_energydetective if args.provider == "zenodo" else fetch_energydetective
            path, artifact, documentation = fetcher(args.dataset, args.cache, offline=not args.online)
            print(json.dumps({"status": "cached", "path": str(path), "artifact": artifact.model_dump(mode="json"),
                              "documentation": documentation.model_dump(mode="json"), "redistribution": "以已核实来源许可为准；Zenodo CC BY 4.0需署名和标注改动，GitHub未单独声明许可"}, ensure_ascii=False, indent=2))
            return 0
        directory = args.output
        if directory.exists() and any(directory.iterdir()):
            print("输出目录已非空；请另选目录以保留此前结果，不覆盖已有文件。")
            return 2
        directory.mkdir(parents=True, exist_ok=True)
        artifact = documentation = None
        path = args.records
        if path is None:
            fetcher = fetch_zenodo_energydetective if args.provider == "zenodo" else fetch_energydetective
            path, artifact, documentation = fetcher(args.dataset, args.cache, offline=not args.online)
        selection = MeterSelection(building=args.building, meters=args.meters.split(","),
            timestamp_position=args.timestamp_position, acknowledge_category_sum=args.acknowledge_category_sum,
            timestamp_assumption_acknowledged=args.acknowledge_time_assumption,
            data_kind="artificial_fixture" if args.artificial_fixture else "published")
        load = import_energydetective(path, selection, start=args.start, hours=args.hours,
            artifact=artifact, documentation=documentation)
        config = json.loads(args.parameters.read_text(encoding="utf-8")) if args.parameters else {}
        if args.budget is not None:
            config["budget_yuan"] = args.budget
        if args.with_solar:
            config["include_solar"] = True
        parameters = ElectricCaseParameters.model_validate(config)
        prices = price_source = None
        if args.tariff_csv:
            if not args.price_description:
                raise ValueError("逐时价格需同时填写--price-description的地区/年份/用户类别与费用边界")
            prices = load_hourly_tariff(args.tariff_csv, load.frame.timestamp)
            price_source = Source(source_id="custom-hourly-price", name="用户提供逐时电价（真实性由来源声明承担）", category="user",
                units={"electricity_price": "元/kWh"}, processing=["按原负荷小时严格对齐，不自动填充"], conditions=args.price_description,
                artifacts=[Artifact(url="用户本地文件（原发布链接未知）", filename=args.tariff_csv.name, sha256=sha256_file(args.tariff_csv))])
        task = build_electric_task(load, parameters, cache_dir=args.cache, offline=not args.online,
            hourly_prices=prices, price_source=price_source)
        paths = export_import(load, task, directory)
        checked = validate_inputs(task)
        print(f"{case_label(task)}；{len(load.frame)}小时；{load.boundary}")
        print("能量核对：", load.audit.model_dump_json())
        print("质量报告与标准化任务：", json.dumps(paths,ensure_ascii=False))
        print("待补项：", json.dumps([i.model_dump() for i in checked.issues],ensure_ascii=False))
        if task.case_context.pending:
            print("未完成/待核实：", "；".join(task.case_context.pending))
        if args.run:
            result = EnergyAgent(directory/"runs").run(task)
            print(f"run_id={result.run_id} 输入版本={result.input_version} 状态={result.state}")
            if result.comparison:
                print(result.comparison.explanation)
            for scenario in result.scenarios:
                metric = scenario.validation.metrics
                print(scenario.candidate.candidate_id, scenario.dispatch.status,
                    f"新增投资={scenario.investment_yuan:.2f}元",
                    f"运行费={metric.operating_cost_yuan:.2f}元；排放={metric.emissions_kg:.2f}kg{task.emission_species}" if metric else "；".join(scenario.dispatch.reasons))
            print(json.dumps(result.files,ensure_ascii=False,indent=2))
            return 0 if result.state == RunState.COMPLETED else 2
        return 0 if checked.ready else 2
    except (OSError, ValueError, httpx.HTTPError) as exc:
        error = {"status": "import_failed", "error_type": type(exc).__name__, "message": str(exc)}
        if args.command == "data-import":
            args.output.mkdir(parents=True, exist_ok=True)
            if isinstance(exc, ImportQualityError):
                for i,report in enumerate(exc.reports):
                    save_quality(report, args.output, f"quality_failed_{i}")
            (args.output/"import_error.json").write_text(json.dumps(error,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(error,ensure_ascii=False,indent=2))
        return 2
