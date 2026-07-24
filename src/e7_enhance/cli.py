from __future__ import annotations

import argparse
import json
from pathlib import Path

from .calibration import CalibrationOptions, calibrate_policies, render_calibration_summary
from .enhance_policy import advise_gear
from .enhance_simulator import SimulationOptions, render_simulation_summary, simulate_drops, simulate_gear
from .models import Gear, validate_gear_source_rank, validate_gear_structure
from .reporter import render_batch_markdown, render_result
from .resource_model import red_epic_resource_table, render_resource_table
from .score_engine import evaluate_gear
from .strategy_defaults import DEFAULT_GEAR_SOURCE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Epic Seven gear enhancement advisor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("gui")

    for name in ("score", "suggest"):
        command = subparsers.add_parser(name)
        command.add_argument("--input", required=True)
        command.add_argument("--item-source", choices=["normal_85", "rift_85"])
        command.add_argument("--gear-source")
        command.add_argument("--disable-dp-assist", action="store_true")
        command.add_argument("--debug", action="store_true")

    batch = subparsers.add_parser("batch")
    batch.add_argument("--input", required=True)
    batch.add_argument("--output")
    batch.add_argument("--item-source", choices=["normal_85", "rift_85"], default="normal_85")
    batch.add_argument("--gear-source", default=DEFAULT_GEAR_SOURCE)
    batch.add_argument("--disable-dp-assist", action="store_true")
    batch.add_argument("--debug", action="store_true")

    resource = subparsers.add_parser("resource")
    resource.add_argument("--gear-source", default=None)
    resource.add_argument("--debug", action="store_true")

    simulate = subparsers.add_parser("simulate")
    simulate.add_argument("--input")
    simulate.add_argument("--runs", type=int, default=5000)
    simulate.add_argument("--seed", type=int, default=1)
    simulate.add_argument("--item-source", choices=["normal_85", "rift_85"], default="normal_85")
    simulate.add_argument("--gear-source", default=DEFAULT_GEAR_SOURCE)
    simulate.add_argument("--rank", choices=["Epic", "Heroic"], default="Epic")
    simulate.add_argument("--strategy", choices=["full", "current"], default="full")
    simulate.add_argument("--stop-at-checkpoint", type=int, choices=[0, 3, 6, 9, 12, 15])
    simulate.add_argument("--debug", action="store_true")

    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--runs", type=int, default=5000)
    calibrate.add_argument("--seed", type=int, default=1)
    calibrate.add_argument("--item-source", choices=["normal_85", "rift_85"], default="normal_85")
    calibrate.add_argument("--gear-source", default=DEFAULT_GEAR_SOURCE)
    calibrate.add_argument("--rank", choices=["Epic", "Heroic"], default="Epic")
    calibrate.add_argument("--workers", type=int, default=1)
    calibrate.add_argument("--top", type=int, default=5)
    calibrate.add_argument("--enable-dp-assist", action="store_true")
    calibrate.add_argument("--dp-utility-margin", type=float, default=0.1)
    calibrate.add_argument("--route-solver-sample-limit", type=int)
    calibrate.add_argument("--debug", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "gui":
        from .gui_app import run_gui

        return run_gui()

    if args.command == "score":
        gear, _, _ = load_single_gear(args.input)
        evaluation = evaluate_gear(gear)
        result = {
            "summary": {
                "recommendation": "keep" if evaluation.rating_level >= 5 else "uncertain",
                "next_check_at": None,
                "target_profile": evaluation.target_profile,
                "reasons": [evaluation.rating_label, evaluation.fit_status],
            },
            "debug": {
                "official_score": evaluation.official_score,
                "effective_score": evaluation.effective_score,
                "baili_score": evaluation.baili_score,
                "target_score": evaluation.target_score,
                "target_score_source_row": evaluation.target_score_source_row,
                "target_score_formula": evaluation.target_score_formula,
                "rating_level": evaluation.rating_label,
                "fit_status": evaluation.fit_status,
                "valid_substats": evaluation.valid_substats,
                "invalid_substats": evaluation.invalid_substats,
            },
        }
        print(render_result(result, debug=True if args.debug else False))
        return 0

    if args.command == "suggest":
        gear, saved_item_source, saved_gear_source = load_single_gear(args.input)
        print(
            render_result(
                advise_gear(
                    gear,
                    item_source=args.item_source or saved_item_source,
                    gear_source=args.gear_source or saved_gear_source,
                    enable_dp_assist=False if args.disable_dp_assist else None,
                ),
                debug=args.debug,
            )
        )
        return 0

    if args.command == "batch":
        data = load_json(args.input)
        items = data.get("items") or data.get("gears") if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise SystemExit("batch input must be a list or contain items/gears")
        results = [
            advise_gear(
                Gear.from_dict(item),
                item_source=args.item_source,
                gear_source=args.gear_source,
                enable_dp_assist=False if args.disable_dp_assist else None,
            )
            for item in items
        ]
        output = json.dumps(results, ensure_ascii=False, indent=2) if args.debug else render_batch_markdown(results)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
        else:
            print(output)
        return 0

    if args.command == "resource":
        table = red_epic_resource_table(args.gear_source)
        print(json.dumps(table, ensure_ascii=False, indent=2) if args.debug else render_resource_table(table))
        return 0

    if args.command == "simulate":
        options = SimulationOptions(
            runs=args.runs,
            seed=args.seed,
            gear_source=args.gear_source,
            item_source=args.item_source,
            rank=args.rank,
            stop_at_checkpoint=args.stop_at_checkpoint,
            strategy=args.strategy,
        )
        if args.input:
            gear, _, _ = load_single_gear(args.input)
            result = simulate_gear(gear, options)
        else:
            result = simulate_drops(options)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.debug else render_simulation_summary(result))
        return 0

    if args.command == "calibrate":
        result = calibrate_policies(
            CalibrationOptions(
                runs=args.runs,
                seed=args.seed,
                gear_source=args.gear_source,
                item_source=args.item_source,
                rank=args.rank,
                workers=args.workers,
                top_limit=args.top,
                enable_dp_assist=args.enable_dp_assist,
                dp_utility_margin=args.dp_utility_margin,
                route_solver_sample_limit=args.route_solver_sample_limit,
            )
        )
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.debug else render_calibration_summary(result))
        return 0

    return 1


def load_json(path: str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"), strict=False)


def load_single_gear(path: str) -> tuple[Gear, str, str]:
    """Load either a bare gear payload or a GUI-saved suggestion payload."""
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("gear input must be an object")
    gear_data = data.get("gear") if isinstance(data.get("gear"), dict) else data
    strategy = ((data.get("suggestion") or {}).get("debug") or {}).get("default_strategy") or {}
    item_source = data.get("item_source") or data.get("itemSource") or strategy.get("item_source") or gear_data.get("item_source") or gear_data.get("itemSource") or "normal_85"
    gear_source = data.get("gear_source") or data.get("gearSource") or strategy.get("gear_source") or gear_data.get("gear_source") or gear_data.get("gearSource") or DEFAULT_GEAR_SOURCE
    gear = Gear.from_dict(gear_data)
    validate_gear_structure(gear)
    validate_gear_source_rank(gear, str(item_source))
    return gear, str(item_source), str(gear_source)
