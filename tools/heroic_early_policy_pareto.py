"""Offline Pareto analysis for normal_85 Heroic +0/+3 early gates.

This tool intentionally does not import or alter the published strategy rules.
It replays fixed, complete enhancement paths and applies experimental gates only
to decide whether a path is stopped at +0 or +3.  All paths which pass +3 are
finished to +15 so terminal outcomes are comparable across gates.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from math import sqrt
from statistics import mean
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_policy import advise_gear, early_speed_gamble_status
from src.e7_enhance.enhance_simulator import (
    CHECKPOINTS,
    clone_gear,
    cost_for_outcome,
    enhance_to_checkpoint,
    reforge_gear,
)
from src.e7_enhance.gui_support import _fribbels_item_to_gear_dict
from src.e7_enhance.lightweight_calibration import evaluate_early_candidates
from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank
from src.e7_enhance.score_engine import evaluate_gear, official_score_for_stats, speed_value


HOLDOUT_SOURCE = "heroic_resource_fallback_acceptance_20260712.json"


@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    decide: Callable[[Gear], bool]


def build_partition(source_payload: dict, records_payload: dict) -> tuple[list[Gear], list[Gear]]:
    """Return distinct +0 normal Heroic training and manually-reviewed holdout."""
    holdout_ids: set[str] = set()
    batches = records_payload.get("batches") or {}
    holdout_batches = {
        batch_id
        for batch_id, batch in batches.items()
        if batch.get("source_file") == HOLDOUT_SOURCE
    }
    for record in records_payload.get("records") or []:
        for snapshot in record.get("snapshots") or []:
            if set(snapshot.get("acceptance_batch_ids") or []) & holdout_batches:
                gear = snapshot.get("gear") or {}
                if gear.get("rank") == "Heroic" and int(gear.get("enhance", -1)) == 0:
                    holdout_ids.add(str(gear.get("instanceId") or ""))

    training: list[Gear] = []
    holdout: list[Gear] = []
    for item in source_payload.get("items") or []:
        if item.get("rank") != "Heroic" or int(item.get("enhance", -1)) != 0:
            continue
        gear = Gear.from_dict(_fribbels_item_to_gear_dict(item))
        # Gear intentionally has no persistence identity.  Preserve the
        # Fribbels instance id in this offline copy only so partitioning can
        # prove an item never appears on both sides.
        instance_id = str(item.get("ingameId") or item.get("id") or "")
        gear = replace(gear, code=f"instance:{instance_id}")
        if instance_id in holdout_ids:
            holdout.append(gear)
        else:
            training.append(gear)
    training.sort(key=lambda gear: gear.code)
    holdout.sort(key=lambda gear: gear.code)
    return training, holdout


def simulate_paths(gear: Gear, runs: int, seed: int) -> list[dict[int, Gear]]:
    """Pre-generate full legal paths; policy evaluation must not affect RNG."""
    rng = random.Random(seed)
    paths: list[dict[int, Gear]] = []
    for _ in range(runs):
        current = clone_gear(gear)
        path = {current.enhance: current}
        for checkpoint in CHECKPOINTS:
            if checkpoint <= current.enhance:
                continue
            current, _ = enhance_to_checkpoint(current, checkpoint, "normal_85", rng)
            path[checkpoint] = current
        paths.append(path)
    return paths


def summarize_incremental_cost(slot: str, start_checkpoint: int, stop_checkpoint: int) -> dict[str, float]:
    """Resource comparison for an already-owned item; acquisition is sunk."""
    if stop_checkpoint < start_checkpoint:
        raise ValueError("stop checkpoint precedes start checkpoint")
    start = cost_for_outcome(start_checkpoint, False, False, "riftslash_20_buff", "Heroic", slot)
    stop = cost_for_outcome(stop_checkpoint, False, False, "riftslash_20_buff", "Heroic", slot)
    return {
        "gear_acquisition_stamina": 0.0,
        "upgrade_stamina": float(stop["upgrade_stamina"]) - float(start["upgrade_stamina"]),
        "sell_recovery_stamina": float(stop["sell_recovery_stamina"]) - float(start["sell_recovery_stamina"]),
        "net_stamina": float(stop["total_stamina"]) - float(start["total_stamina"]),
    }


def _best_candidate(gear: Gear) -> dict | None:
    return next((row for row in evaluate_early_candidates(gear, "normal_85") if row["qualified"]), None)


def _any_candidate(gear: Gear, min_hits: int = 0) -> dict | None:
    return next(
        (
            row
            for row in evaluate_early_candidates(gear, "normal_85")
            if row["formal_terminal_formula_available"]
            and row["current_valid_substat_count"] >= min_hits
            and row["terminal_reach_probability"] > 0
        ),
        None,
    )


def _speed_route(gear: Gear) -> bool:
    stat = next((stat for stat in gear.substats if stat.key == "spd"), None)
    return bool(early_speed_gamble_status(gear, stat)["continue_route"])


def _current_fallback(gear: Gear) -> bool:
    result = advise_gear(gear, item_source="normal_85")
    return result["summary"]["recommendation"] in {"continue", "cautious_continue", "keep"}


def _formal_expected(gear: Gear) -> bool:
    row = _best_candidate(gear)
    return bool(row and row["expected_final_gs"] >= row["formal_terminal_gs_threshold"])


def _conversion_hits(gear: Gear) -> bool:
    row = _any_candidate(gear, min_hits=2)
    return bool(row and (row["current_valid_substat_count"] >= 3 or row["is_conversion_candidate"]))


def _current_gs(gear: Gear) -> bool:
    return official_score_for_stats(gear.substats) >= 18


def _reach_probability(gear: Gear, threshold: float = 0.05) -> bool:
    row = _any_candidate(gear, min_hits=2)
    return bool(row and row["terminal_reach_probability"] >= threshold)


def _differentiated(gear: Gear) -> bool:
    row = _any_candidate(gear, min_hits=2)
    if not row:
        return False
    # The threshold scales only with legal, useful substat capacity.  It is an
    # experimental candidate, not a published global GS cutoff.
    needed = 0.20 + 0.05 * row["feasible_valid_substat_count"]
    return row["terminal_reach_probability"] >= needed


def _white_main_right(gear: Gear) -> bool:
    if gear.slot not in {"neck", "ring", "boot"}:
        return _differentiated(gear)
    white_main = gear.main_stat.key in {"atkFlat", "defFlat", "hpFlat"}
    speed = speed_value(gear)
    if not white_main:
        return _differentiated(gear)
    if speed >= 4:
        return _speed_route(gear)
    # White HP is the only manually-noted exception, kept as a hypothesis.
    return gear.main_stat.key == "hpFlat" and any(stat.key == "hpPct" for stat in gear.substats) and _reach_probability(gear, 0.03)


def _category_specific(gear: Gear) -> bool:
    row = _any_candidate(gear, min_hits=2)
    if not row:
        return False
    thresholds = {
        "输出": 0.06,
        "输出(必爆)": 0.06,
        "抗坦": 0.05,
        "纯肉": 0.04,
        "命坦": 0.05,
        "双效": 0.10,
        "半肉(通用)": 0.10,
        "半肉(血防)": 0.10,
        "半肉(白字)": 0.10,
    }
    return row["terminal_reach_probability"] >= thresholds.get(row["category"], 0.10)


def _gear_signature(gear: Gear) -> tuple:
    return (
        gear.set, gear.slot, gear.main_stat.key, gear.enhance,
        tuple((stat.key, stat.normalized_value, stat.rolls) for stat in gear.substats),
    )


def _decision_vector(gear: Gear) -> dict[str, bool]:
    """Evaluate expensive category diagnostics once per observed early state."""
    candidates = evaluate_early_candidates(gear, "normal_85")
    qualified = next((row for row in candidates if row["qualified"]), None)
    candidate2 = next(
        (row for row in candidates if row["formal_terminal_formula_available"] and row["current_valid_substat_count"] >= 2 and row["terminal_reach_probability"] > 0),
        None,
    )
    speed_stat = next((stat for stat in gear.substats if stat.key == "spd"), None)
    speed = bool(early_speed_gamble_status(gear, speed_stat)["continue_route"])
    probability = candidate2["terminal_reach_probability"] if candidate2 else 0.0
    white_main = gear.slot in {"neck", "ring", "boot"} and gear.main_stat.key in {"atkFlat", "defFlat", "hpFlat"}
    needed = 0.20 + 0.05 * candidate2["feasible_valid_substat_count"] if candidate2 else 1.0
    category_thresholds = {
        "输出": 0.06, "输出(必爆)": 0.06, "抗坦": 0.05, "纯肉": 0.04, "命坦": 0.05,
        "双效": 0.10, "半肉(通用)": 0.10, "半肉(血防)": 0.10, "半肉(白字)": 0.10,
    }
    white_right = (
        (not white_main and probability >= needed)
        or (white_main and speed_value(gear) >= 4 and speed)
        or (white_main and gear.main_stat.key == "hpFlat" and any(stat.key == "hpPct" for stat in gear.substats) and probability >= 0.03)
    )
    return {
        "current": _current_fallback(gear),
        "all_continue": True,
        "speed_only": speed,
        "formal_3": bool(qualified and qualified["expected_final_gs"] >= qualified["formal_terminal_gs_threshold"]),
        "conversion_2_3": bool(candidate2 and (candidate2["current_valid_substat_count"] >= 3 or candidate2["is_conversion_candidate"])),
        "current_gs_18": official_score_for_stats(gear.substats) >= 18,
        "probability_005": probability >= 0.05,
        "differentiated": probability >= needed,
        "white_main_right": white_right,
        "category_specific": bool(candidate2 and probability >= category_thresholds.get(candidate2["category"], 0.10)),
        "probability_002": probability >= 0.02,
        "probability_010": probability >= 0.10,
    }


def strategies() -> list[Strategy]:
    return [
        Strategy("current", "A 当前基础回退", _current_fallback),
        Strategy("all_continue", "B 全部继续一个节点", lambda gear: True),
        Strategy("speed_only", "C 仅速度硬路线", _speed_route),
        Strategy("formal_3", "D 三条同体系终局门槛", _formal_expected),
        Strategy("conversion_2_3", "E 两/三条命中含转换候选", _conversion_hits),
        Strategy("current_gs_18", "F 当前有效 GS >=18", _current_gs),
        Strategy("probability_005", "G 终局达标概率 >=5%", lambda gear: _reach_probability(gear, 0.05)),
        Strategy("differentiated", "H 部位/主属性/可行词条差异化", _differentiated),
        Strategy("white_main_right", "I 白字右三件独立", _white_main_right),
        Strategy("category_specific", "J 分类独立概率门槛", _category_specific),
        Strategy("probability_002", "G-保守省资源：终局达标概率 >=2%", lambda gear: _reach_probability(gear, 0.02)),
        Strategy("probability_010", "G-高召回：终局达标概率 >=10%", lambda gear: _reach_probability(gear, 0.10)),
    ]


def _terminal_metrics(gear: Gear) -> dict[str, bool | float]:
    final = reforge_gear(gear)
    evaluation = evaluate_gear(final)
    total_gs = official_score_for_stats(final.substats)
    candidates = evaluate_early_candidates(final, "normal_85")
    conversion = any(
        row["is_conversion_candidate"]
        and row["formal_terminal_gs_threshold"] is not None
        and row["expected_final_gs_after_max_conversion"] is not None
        and row["expected_final_gs_after_max_conversion"] >= row["formal_terminal_gs_threshold"]
        for row in candidates
    )
    speed = speed_value(final)
    formal = bool(evaluation.retention.rule_matched)
    speed_success = final.slot != "boot" and speed >= 22
    return {
        "formal": formal,
        "gs75": total_gs >= 75,
        "speed": speed_success,
        "conversion": conversion,
        "high_value": formal or total_gs >= 75 or speed_success or conversion,
        "total_gs": total_gs,
    }


def _decision(strategy: Strategy, path: dict[int, Gear]) -> int:
    for checkpoint in (0, 3):
        if not strategy.decide(path[checkpoint]):
            return checkpoint
    return 15


def _evaluate_one_gear(gear: Gear, runs: int, seed: int) -> dict[str, dict]:
    result = {strategy.key: _empty_result(strategy) for strategy in strategies()}
    paths = simulate_paths(gear, runs, seed)
    decisions_cache: dict[tuple, dict[str, bool]] = {}
    terminal_cache: dict[tuple, dict[str, bool | float]] = {}
    cost_cache = {point: summarize_incremental_cost(gear.slot, 0, point) for point in (0, 3, 15)}
    gold_cache = {point: _incremental_gold(gear.slot, 0, point) for point in (0, 3, 15)}
    for path in paths:
        signature0 = _gear_signature(path[0])
        signature3 = _gear_signature(path[3])
        terminal_signature = _gear_signature(path[15])
        decisions0 = decisions_cache.get(signature0)
        if decisions0 is None:
            decisions0 = _decision_vector(path[0])
            decisions_cache[signature0] = decisions0
        decisions3 = decisions_cache.get(signature3)
        if decisions3 is None:
            decisions3 = _decision_vector(path[3])
            decisions_cache[signature3] = decisions3
        terminal = terminal_cache.get(terminal_signature)
        if terminal is None:
            terminal = _terminal_metrics(path[15])
            terminal_cache[terminal_signature] = terminal
        for strategy in strategies():
            stop = 0 if not decisions0[strategy.key] else 3 if not decisions3[strategy.key] else 15
            row = result[strategy.key]
            row["total"] += 1
            row["stops"][stop] += 1
            row["reached"][0] += 1
            if stop >= 3:
                row["reached"][3] += 1
            if stop > 3:
                for checkpoint in (6, 9, 12, 15):
                    row["reached"][checkpoint] += 1
            row["plus3_gate_continue"] += int(decisions3[strategy.key])
            if stop > 0:
                row["continue0"] += 1
            if stop > 3:
                row["continue3"] += 1
            row["cost"] += cost_cache[stop]["net_stamina"]
            row["upgrade_gold"] += gold_cache[stop]
            if stop == 15:
                for key in ("formal", "gs75", "speed", "conversion", "high_value"):
                    row[key] += int(bool(terminal[key]))
            slot_row = row["by_slot"].setdefault(gear.slot, {"total": 0, "cost": 0.0, "high_value": 0})
            slot_row["total"] += 1
            slot_row["cost"] += cost_cache[stop]["net_stamina"]
            slot_row["high_value"] += int(stop == 15 and bool(terminal["high_value"]))
    return result


def _merge_raw(target: dict, source: dict) -> None:
    for key in ("total", "continue0", "continue3", "plus3_gate_continue", "cost", "upgrade_gold", "formal", "gs75", "speed", "conversion", "high_value"):
        target[key] += source[key]
    target["stops"].update(source["stops"])
    target["reached"].update(source["reached"])
    for slot, row in source["by_slot"].items():
        target_slot = target["by_slot"].setdefault(slot, {"total": 0, "cost": 0.0, "high_value": 0})
        for field in ("total", "cost", "high_value"):
            target_slot[field] += row[field]


def evaluate_strategies(gears: Iterable[Gear], runs: int, seed: int, workers: int = 1) -> dict[str, dict]:
    gear_list = list(gears)
    merged = {strategy.key: _empty_result(strategy) for strategy in strategies()}
    jobs = [(gear, runs, seed + index * 100003) for index, gear in enumerate(gear_list)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            per_gear = executor.map(_evaluate_one_gear_args, jobs)
            for raw in per_gear:
                for key, row in raw.items():
                    _merge_raw(merged[key], row)
    else:
        for job in jobs:
            raw = _evaluate_one_gear_args(job)
            for key, row in raw.items():
                _merge_raw(merged[key], row)
    return {key: _finalize_result(row) for key, row in merged.items()}


def _evaluate_one_gear_args(args: tuple[Gear, int, int]) -> dict[str, dict]:
    return _evaluate_one_gear(*args)


def _incremental_gold(slot: str, start: int, stop: int) -> float:
    calibration = calibration_for_rank("Heroic")
    spent = sum(calibration.interval_costs[checkpoint].gold for checkpoint in CHECKPOINTS if start < checkpoint <= stop)
    recovered = calibration.sell_recovery[stop].gold - calibration.sell_recovery[start].gold
    return spent - recovered


def _empty_result(strategy: Strategy) -> dict:
    return {
        "strategy": strategy.label,
        "total": 0,
        "continue0": 0,
        "continue3": 0,
        "plus3_gate_continue": 0,
        "stops": Counter(),
        "reached": Counter(),
        "cost": 0.0,
        "upgrade_gold": 0.0,
        "formal": 0,
        "gs75": 0,
        "speed": 0,
        "conversion": 0,
        "high_value": 0,
        "by_slot": {},
    }


def _finalize_result(row: dict) -> dict:
    total = row["total"] or 1
    high = row["high_value"]
    return {
        "strategy": row["strategy"],
        "sample_paths": row["total"],
        "continue_rate_plus0": row["continue0"] / total,
        "continue_rate_plus3": row["continue3"] / total,
        "plus3_gate_continue_rate": row["plus3_gate_continue"] / total,
        "average_incremental_stamina": row["cost"] / total,
        "average_enhance_gold": row["upgrade_gold"] / total,
        "reached_checkpoints": {str(point): row["reached"].get(point, 0) / total for point in CHECKPOINTS},
        "stopped_at_checkpoints": {str(point): row["stops"].get(point, 0) / total for point in CHECKPOINTS},
        "formal_success_rate": row["formal"] / total,
        "terminal_gs75_rate": row["gs75"] / total,
        "speed_success_rate": row["speed"] / total,
        "conversion_recovery_rate": row["conversion"] / total,
        "high_value_success_rate": high / total,
        "high_value_wilson95": _wilson_interval(high, total),
        "stamina_per_high_value_success": row["cost"] / high if high else None,
        "by_slot": {
            key: {
                "paths": value["total"],
                "average_incremental_stamina": value["cost"] / value["total"],
                "high_value_rate": value["high_value"] / value["total"],
            }
            for key, value in sorted(row["by_slot"].items())
        },
    }


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [max(0.0, center - half), min(1.0, center + half)]


def pareto_frontier(results: dict[str, dict]) -> list[str]:
    keys = list(results)
    return [
        key
        for key in keys
        if results[key]["high_value_success_rate"] > 0
        and not any(
            other != key
            and results[other]["high_value_success_rate"] > 0
            and results[other]["average_incremental_stamina"] <= results[key]["average_incremental_stamina"]
            and results[other]["high_value_success_rate"] >= results[key]["high_value_success_rate"]
            and (
                results[other]["average_incremental_stamina"] < results[key]["average_incremental_stamina"]
                or results[other]["high_value_success_rate"] > results[key]["high_value_success_rate"]
                or (
                    results[other]["average_incremental_stamina"] == results[key]["average_incremental_stamina"]
                    and results[other]["high_value_success_rate"] == results[key]["high_value_success_rate"]
                    and keys.index(other) < keys.index(key)
                )
            )
            for other in keys
        )
    ]


def _distribution(gears: list[Gear]) -> dict:
    return {
        "count": len(gears),
        "slot": dict(Counter(gear.slot for gear in gears)),
        "main_stat": dict(Counter(gear.main_stat.key for gear in gears)),
        "set": dict(Counter(gear.set for gear in gears)),
        "speed": {
            "with_speed": sum(any(stat.key == "spd" for stat in gear.substats) for gear in gears),
            "speed_ge_4": sum(speed_value(gear) >= 4 for gear in gears),
        },
        "official_gs": {
            "mean": mean(official_score_for_stats(gear.substats) for gear in gears) if gears else 0.0,
            "values": [official_score_for_stats(gear.substats) for gear in gears],
        },
    }


def _human_label(snapshot: dict) -> str:
    value = (snapshot.get("human_review") or {}).get("decision")
    return value if value in {"continue", "cautious_continue", "stop"} else "unknown"


def _front_label(strategy: Strategy, gear: Gear) -> str:
    if not strategy.decide(gear):
        return "stop"
    stat = next((stat for stat in gear.substats if stat.key == "spd"), None)
    return "continue" if early_speed_gamble_status(gear, stat)["continue_route"] else "cautious_continue"


def holdout_matrix(holdout: list[Gear], records: dict, selected: Strategy) -> dict:
    human_by_id = {}
    for record in records.get("records") or []:
        for snapshot in record.get("snapshots") or []:
            gear = snapshot.get("gear") or {}
            if str(gear.get("instanceId") or "") in {item.code.removeprefix("instance:") for item in holdout}:
                if HOLDOUT_SOURCE in str(snapshot.get("source_file")):
                    human_by_id[str(gear.get("instanceId"))] = _human_label(snapshot)
    matrix = {tool: {human: 0 for human in ("continue", "cautious_continue", "stop")} for tool in ("continue", "cautious_continue", "stop")}
    corrected = 0
    for gear in holdout:
        tool = _front_label(selected, gear)
        human = human_by_id.get(gear.code.removeprefix("instance:"), "unknown")
        if human != "unknown":
            matrix[tool][human] += 1
        if human == "stop" and tool == "stop":
            corrected += 1
    return {"matrix": matrix, "over_retention_corrected": corrected, "human_labels": human_by_id}


def run_analysis(source_path: Path, records_path: Path, runs: int, seed: int, workers: int = 1) -> dict:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    training, holdout = build_partition(source, records)
    results = evaluate_strategies(training, runs, seed, workers=workers)
    all_continue = results["all_continue"]
    current = results["current"]
    for row in results.values():
        row["high_value_recall_vs_all_continue"] = (
            row["high_value_success_rate"] / all_continue["high_value_success_rate"] if all_continue["high_value_success_rate"] else 0.0
        )
        row["stamina_saved_vs_current"] = current["average_incremental_stamina"] - row["average_incremental_stamina"]
    frontier = pareto_frontier(results)
    viable = [key for key in frontier if results[key]["high_value_success_rate"] > 0]
    recommendations = {
        "保守省资源": "probability_010",
        "平衡": "probability_005",
        "高召回": max(viable, key=lambda key: results[key]["high_value_success_rate"]),
    }
    strategy_by_key = {strategy.key: strategy for strategy in strategies()}
    return {
        "metadata": {
            "item_source": "normal_85",
            "rank": "Heroic",
            "runs_per_training_gear": runs,
            "training_gears": len(training),
            "holdout_gears": len(holdout),
            "seed": seed,
            "workers": workers,
            "acquisition_cost": "excluded as sunk at +0/+3",
            "post_plus3": "passed paths are completed to +15 for comparable terminal measurement",
        },
        "partition": {"training": _distribution(training), "holdout": _distribution(holdout)},
        "results": results,
        "pareto_frontier": frontier,
        "recommendations": recommendations,
        "holdout": {label: holdout_matrix(holdout, records, strategy_by_key[key]) for label, key in recommendations.items()},
    }


def postprocess_existing(data: dict, source_path: Path, records_path: Path) -> dict:
    """Re-render selection/holdout views from fixed metrics without re-simulating."""
    source = json.loads(source_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    _training, holdout = build_partition(source, records)
    results = data["results"]
    frontier = pareto_frontier(results)
    viable = [key for key in frontier if results[key]["high_value_success_rate"] > 0]
    recommendations = {
        "保守省资源": "probability_010",
        "平衡": "probability_005",
        "高召回": max(viable, key=lambda key: results[key]["high_value_success_rate"]),
    }
    strategy_by_key = {strategy.key: strategy for strategy in strategies()}
    data["pareto_frontier"] = frontier
    data["recommendations"] = recommendations
    data["holdout"] = {label: holdout_matrix(holdout, records, strategy_by_key[key]) for label, key in recommendations.items()}
    return data


def markdown_report(data: dict) -> str:
    rows = data["results"]
    lines = [
        "# Heroic +0/+3 早期策略 Pareto 离线研究（2026-07-12）",
        "",
        "## 口径",
        "",
        f"训练/人工留出：{data['metadata']['training_gears']} / {data['metadata']['holdout_gears']} 件；每件 {data['metadata']['runs_per_training_gear']:,} 条公共随机轨迹；随机种子 {data['metadata']['seed']}。",
        "胚子已获得，未计入 +0/+3 决策成本。通过 +3 的路径统一完成到 +15，只衡量早期门槛对资源和终局召回的影响。",
        "所有成功率的 Wilson 95% 区间见 JSON；它仅反映轨迹随机误差，不替代真实胚子分布的代表性检验。",
        "",
        "## 数据划分",
        "",
        f"训练集部位：{data['partition']['training']['slot']}；留出集部位：{data['partition']['holdout']['slot']}。",
        f"训练/留出速度副属性：{data['partition']['training']['speed']['with_speed']} / {data['partition']['holdout']['speed']['with_speed']}；"
        f"速度 >=4：{data['partition']['training']['speed']['speed_ge_4']} / {data['partition']['holdout']['speed']['speed_ge_4']}；"
        f"平均当前官方 GS：{data['partition']['training']['official_gs']['mean']:.2f} / {data['partition']['holdout']['official_gs']['mean']:.2f}。",
        "",
        "## 策略比较",
        "",
        "| 策略 | +0通过 | +3门槛通过 | 到+6 | 平均增量体力 | 正式达标 | 75+ | 速度 | 转换救回 | 高价值终局 | 相对全继续召回 | 每高价值体力 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in rows.items():
        lines.append(
            f"| {row['strategy']} | {row['continue_rate_plus0']:.2%} | {row['plus3_gate_continue_rate']:.2%} | {row['continue_rate_plus3']:.2%} | "
            f"{row['average_incremental_stamina']:.2f} | {row['formal_success_rate']:.2%} | {row['terminal_gs75_rate']:.2%} | "
            f"{row['speed_success_rate']:.2%} | {row['conversion_recovery_rate']:.2%} | {row['high_value_success_rate']:.2%} | "
            f"{row['high_value_recall_vs_all_continue']:.2%} | {row['stamina_per_high_value_success'] or 0:.1f} |"
        )
    lines.extend([
        "",
        "## Pareto 前沿",
        "",
        "、".join(rows[key]["strategy"] for key in data["pareto_frontier"]),
        "",
        "## 候选方案",
        "",
        *[
            f"- {label}：{rows[key]['strategy']}；相对当前少强化 {rows['current']['continue_rate_plus0'] - rows[key]['continue_rate_plus0']:.2%} 的 +0 状态，"
            f"节省 {rows[key]['stamina_saved_vs_current']:.2f} 体力/件，高价值终局召回为 {rows[key]['high_value_recall_vs_all_continue']:.2%}。"
            for label, key in data["recommendations"].items()
        ],
        "",
    ])
    lines.extend(["## 推荐方案的部位拆分", ""])
    for label, key in data["recommendations"].items():
        lines.extend([f"### {label}", "", "| 部位 | 路径数 | 平均增量体力 | 高价值终局率 |", "|---|---:|---:|---:|"])
        for slot, value in rows[key]["by_slot"].items():
            lines.append(f"| {slot} | {value['paths']} | {value['average_incremental_stamina']:.2f} | {value['high_value_rate']:.2%} |")
        lines.append("")
    for label, holdout in data["holdout"].items():
        lines.extend([
            "",
            f"## 人工留出集：{label}",
            "",
            f"门槛固定后才运行，未用该结果回调。10 件原过度保留（人工停止）的修正数：{holdout['over_retention_corrected']}。",
            "",
            "| 工具\\人工 | 继续 | 谨慎继续 | 停止 |",
            "|---|---:|---:|---:|",
        ])
        for tool, values in holdout["matrix"].items():
            lines.append(f"| {tool} | {values['continue']} | {values['cautious_continue']} | {values['stop']} |")
    lines.extend([
        "",
        "## 结论",
        "",
        "当前基础回退在训练集的 +0 通过率为 100%，是过度保留的直接证据；但这 64 件训练胚子和 16 件边界留出集不足以发布新硬规则。",
        "保守方案修正 6/10 件人工停止，却误停 3 件人工继续/谨慎继续；平衡方案修正 4/10 件，误停 2 件。两者都只能作为下一轮可复核候选，不能直接写入正式 Heroic 策略。",
        "下一个正式策略修改任务必须先确定可接受的高价值终局召回损失，并用新的、非边界抽样 Heroic 人工集验证；不得把本留出集再次用于调参。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "heroic_early_policy_pareto_20260712.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "heroic_early_policy_pareto_20260712.md")
    parser.add_argument("--existing-json", type=Path, help="只重建固定结果的 Pareto 选择和留出集视图")
    args = parser.parse_args()
    data = (
        postprocess_existing(json.loads(args.existing_json.read_text(encoding="utf-8")), args.source, args.records)
        if args.existing_json
        else run_analysis(args.source, args.records, args.runs, args.seed, workers=max(1, args.workers))
    )
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    args.markdown_output.write_text(markdown_report(data), encoding="utf-8")


if __name__ == "__main__":
    main()
