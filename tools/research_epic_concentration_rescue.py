"""Offline rescue study for extreme attack/health concentration.

This module is deliberately separate from the released policy.  It evaluates
only one-way ``stop -> continue`` rescues at +6/+9/+12, using official
discrete reinforcement values and the existing joint Epic/Heroic resource
pool.  It never reads holdout labels or writes production configuration.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_simulator import reforge_gear
from src.e7_enhance.models import Gear, RollHit, Stat
from src.e7_enhance.rules import OFFICIAL_SCORE_WEIGHTS
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools import research_reforged_inventory_set_weights as official
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, _heroic_base_action, _source_rank_gears, _terminal_metrics, formal_followup_action, summarize_incremental_cost
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_epic_exact_plus3 import _formal_action, load_real_plus0
from tools.research_epic_exact_plus3_joint_pool import _flow
from tools.research_riftslash_saint_pool import YIELD_VARIATIONS, _t95, explicit_batch_resource_pool


STUDY = "epic_concentration_rescue_v1_20260720"
SCHEMA_VERSION = 1
SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
CHECKPOINTS = (0, 3, 6, 9, 12, 15)
RESCUE_NODES = (6, 9, 12)
QUANTILES = (0.90, 0.95, 0.975)
ATTRIBUTES = ("attack", "health", "or")
DEFAULT_RECORDS = ROOT / "manual_acceptance" / "real_sample_records.json"
DEFAULT_SOURCE = ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json"
EXTERNAL_SOURCE = Path(r"D:\VScode\E7-tools\gear_data\0橙U子0\json\gear_fribbels_20260610_182000.json")
EXPECTED_EXTERNAL_SHA256 = "2BB32F384FBE3D926F5274D50AB24DC8766C2AF87AA1ABC0B6946A47EEAE1DB7"
DEFAULT_JSON = ROOT / "reports" / "epic_concentration_rescue_20260720.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_concentration_rescue_20260720.md"


@dataclass(frozen=True)
class Candidate:
    attribute: str
    quantile: float
    mode: str
    attack_threshold: float
    health_threshold: float

    @property
    def key(self) -> str:
        q = {0.90: "p90", 0.95: "p95", 0.975: "p975"}[self.quantile]
        return f"{self.attribute}_{q}_{self.mode}"


def _stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 4)


def _concentration_value(gear: Gear, attribute: str) -> float:
    keys = {"attack": {"atkPct", "atkFlat"}, "health": {"hpPct", "hpFlat"}}[attribute]
    return round(sum(stat.normalized_value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0) for stat in gear.substats if stat.key in keys), 4)


def inventory_thresholds(path: Path = EXTERNAL_SOURCE) -> dict[str, Any]:
    digest = sha256(path.read_bytes()).hexdigest().upper()
    if digest != EXPECTED_EXTERNAL_SHA256:
        raise RuntimeError(f"external inventory hash changed: {digest}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = {"attack": [], "health": []}
    counts = {"Epic": 0, "Heroic": 0}
    for item in payload.get("items") or []:
        if int(item.get("level", -1)) != 90 or int(item.get("enhance", -1)) != 15:
            continue
        rank = str(item.get("rank") or "")
        if rank not in counts:
            continue
        gear = Gear.from_dict(item)
        counts[rank] += 1
        values["attack"].append(_concentration_value(gear, "attack"))
        values["health"].append(_concentration_value(gear, "health"))
    thresholds = {
        attribute: {str(q): _percentile(rows, q) for q in QUANTILES}
        for attribute, rows in values.items()
    }
    return {
        "source": str(path),
        "sha256": digest,
        "filter": {"level": 90, "enhance": 15, "ranks": ["Epic", "Heroic"]},
        "counts": counts,
        "value_counts": {key: len(row) for key, row in values.items()},
        "quantiles": thresholds,
        "definition": "副属性集中GS；攻击=atkPct+atkFlat官方GS，生命=hpPct+hpFlat官方GS；不含主属性/套装/英雄面板",
    }


def build_candidates(thresholds: dict[str, Any]) -> tuple[Candidate, ...]:
    rows: list[Candidate] = []
    for mode in ("balanced", "aggressive"):
        for quantile in QUANTILES:
            attack = float(thresholds["quantiles"]["attack"][str(quantile)])
            health = float(thresholds["quantiles"]["health"][str(quantile)])
            rows.extend([
                Candidate("attack", quantile, mode, attack, health),
                Candidate("health", quantile, mode, attack, health),
                Candidate("or", quantile, mode, attack, health),
            ])
    return tuple(rows)


def _compatible(gear: Gear, attribute: str) -> bool:
    group = phase_b.selected_candidate_snapshot(gear).get("system_group")
    if attribute == "attack":
        return group in {"pure_output", "bruiser"}
    if attribute == "health":
        return group in {"pure_tank", "bruiser"}
    return _compatible(gear, "attack") or _compatible(gear, "health")


def _target_hit(gear: Gear, candidate: Candidate) -> bool:
    attack = _concentration_value(gear, "attack") >= candidate.attack_threshold
    health = _concentration_value(gear, "health") >= candidate.health_threshold
    if candidate.attribute == "attack":
        return attack
    if candidate.attribute == "health":
        return health
    return attack or health


def _candidate_applies(gear: Gear, candidate: Candidate) -> bool:
    if candidate.attribute == "or":
        return _compatible(gear, "or")
    return _compatible(gear, candidate.attribute)


def _official_paths(gear: Gear, runs: int, seed: int) -> list[dict[int, Gear]]:
    paths: list[dict[int, Gear]] = []
    for index in range(runs):
        rng = random.Random(seed + index * 100003)
        current = gear
        path = {current.enhance: current}
        for checkpoint in CHECKPOINTS:
            if checkpoint <= current.enhance:
                continue
            if checkpoint == 12 and current.rank == "Heroic" and len(current.substats) < 4:
                current = replace(current, enhance=12, substats=current.substats + [official._new_official_substat(rng, current)])
            else:
                index_hit = rng.randrange(len(current.substats))
                hit = current.substats[index_hit]
                delta = official._draw_roll(rng, current.rank, hit.key)
                updated = Stat(hit.type, hit.normalized_value + delta, rolls=hit.rolls + 1, modified=hit.modified)
                substats = list(current.substats)
                substats[index_hit] = updated
                current = replace(current, enhance=checkpoint, substats=substats, roll_history=list(current.roll_history) + [RollHit(checkpoint, updated.type, delta)])
            path[checkpoint] = current
        paths.append(path)
    return paths


def _zero_outcome(gear: Gear) -> dict[str, Any]:
    costs = summarize_incremental_cost(gear.slot, gear.rank, gear.enhance, gear.enhance)
    return {"start_checkpoint": gear.enhance, "stop_checkpoint": gear.enhance, "net_stamina": costs["net_stamina"], "net_gold": costs["net_gold"], "costs": costs, "actions": {gear.enhance: "stop"}, "reached_checkpoints": [gear.enhance]}


def _baseline_action(state: Gear) -> str:
    if state.enhance in (0, 3):
        return _formal_action(state, GEAR_SOURCE)
    if state.rank == "Heroic":
        return _heroic_base_action(state, "normal_85")
    return "continue" if formal_followup_action(state, "normal_85") else "stop"


def _cached_action(state: Gear, action_cache: dict[tuple[Any, ...], str]) -> str:
    signature = _state_signature(state)
    if signature not in action_cache:
        action_cache[signature] = _baseline_action(state)
    return action_cache[signature]


def _state_signature(state: Gear) -> tuple[Any, ...]:
    return (state.enhance, state.rank, state.slot, state.main_stat.key, tuple((stat.key, stat.normalized_value, stat.rolls) for stat in state.substats))


def _terminal_values(state: Gear, runs: int, seed: int, cache: dict[tuple[Any, ...], tuple[tuple[float, float], ...]]) -> tuple[tuple[float, float], ...]:
    signature = (_state_signature(state), runs, seed)
    if signature in cache:
        return cache[signature]
    paths = _official_paths(state, runs, seed)
    result = tuple((_concentration_value(reforge_gear(path[15]), "attack"), _concentration_value(reforge_gear(path[15]), "health")) for path in paths)
    cache[signature] = result
    return result


def _probability(state: Gear, candidate: Candidate, runs: int, seed: int, cache: dict[tuple[Any, ...], tuple[tuple[float, float], ...]]) -> float:
    if not _candidate_applies(state, candidate):
        return 0.0
    values = _terminal_values(state, runs, seed, cache)
    if not values:
        return 0.0
    attack_probability = sum(attack >= candidate.attack_threshold for attack, _health in values) / len(values)
    health_probability = sum(health >= candidate.health_threshold for _attack, health in values) / len(values)
    if candidate.attribute == "attack":
        return attack_probability
    if candidate.attribute == "health":
        return health_probability
    return sum(attack >= candidate.attack_threshold or health >= candidate.health_threshold for attack, health in values) / len(values)


def _should_rescue(state: Gear, candidate: Candidate, probability_runs: int, seed: int, cache: dict[tuple[Any, ...], tuple[tuple[float, float], ...]], action_cache: dict[tuple[Any, ...], str]) -> tuple[bool, float]:
    if state.enhance not in RESCUE_NODES or _cached_action(state, action_cache) != "stop":
        return False, 0.0
    probability = _probability(state, candidate, probability_runs, seed, cache)
    threshold = 0.10 if candidate.mode == "balanced" else 0.0
    return probability >= threshold if candidate.mode == "balanced" else probability > threshold, probability


def _outcome(path: dict[int, Gear], candidate: Candidate | None, probability_runs: int, probability_seed: int, cache: dict[tuple[Any, ...], tuple[tuple[float, float], ...]], action_cache: dict[tuple[Any, ...], str]) -> tuple[dict[str, Any], dict[str, Any]]:
    start = min(path)
    current = start
    actions: dict[int, str] = {}
    rescues: list[dict[str, Any]] = []
    while current < 15:
        state = path[current]
        baseline = _cached_action(state, action_cache)
        action = baseline
        probability = 0.0
        if candidate is not None and current in RESCUE_NODES and baseline == "stop":
            rescued, probability = _should_rescue(state, candidate, probability_runs, probability_seed + current * 7919, cache, action_cache)
            if rescued:
                action = "continue"
                rescues.append({"checkpoint": current, "probability": probability})
        actions[current] = action
        if action == "stop":
            break
        current = next(point for point in CHECKPOINTS if point > current)
    outcome = {"start_checkpoint": start, "stop_checkpoint": current, "actions": actions, "reached_checkpoints": [point for point in CHECKPOINTS if start <= point <= current], "net_stamina": 0.0, "net_gold": 0.0, "costs": {}}
    costs = summarize_incremental_cost(path[start].slot, path[start].rank, start, current)
    outcome["net_stamina"] = costs["net_stamina"]
    outcome["net_gold"] = costs["net_gold"]
    outcome["costs"] = costs
    return outcome, {"rescues": rescues, "first_rescue_node": rescues[0]["checkpoint"] if rescues else None}


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _new_stats() -> dict[str, Any]:
    return {"rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "first_rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "paths": 0.0, "target_high": 0.0, "incremental_target_high": 0.0, "by_set": {}, "by_slot": {}, "by_rank": {"Epic": 0.0, "Heroic": 0.0}}


def _accumulate_stats(stats: dict[str, Any], gear: Gear, candidate: Candidate, path: dict[int, Gear], candidate_outcome: dict[str, Any], rescue: dict[str, Any], baseline_high: bool, factor: float) -> None:
    stats["paths"] += factor
    for row in rescue["rescues"]:
        stats["rescue_nodes"][str(row["checkpoint"])] += factor
    if rescue["first_rescue_node"] is not None:
        stats["first_rescue_nodes"][str(rescue["first_rescue_node"])] += factor
    if candidate_outcome["stop_checkpoint"] == 15:
        high = _target_hit(reforge_gear(path[15]), candidate)
        stats["target_high"] += factor * float(high)
        stats["incremental_target_high"] += factor * (float(high) - float(baseline_high))
    stats["by_set"][gear.set] = stats["by_set"].get(gear.set, 0.0) + factor * float(rescue["rescues"] != [])
    stats["by_slot"][gear.slot] = stats["by_slot"].get(gear.slot, 0.0) + factor * float(rescue["rescues"] != [])
    stats["by_rank"][gear.rank] += factor * float(rescue["rescues"] != [])


def _run_rank(gears: list[Gear], rank: str, seed: int, runs: int, probability_runs: int, candidates: tuple[Candidate, ...]) -> dict[str, Any]:
    flows = {"current_formal": _empty_flow(), **{candidate.key: _empty_flow() for candidate in candidates}}
    stats = {"current_formal": _new_stats(), **{candidate.key: _new_stats() for candidate in candidates}}
    probability_cache: dict[tuple[Any, ...], tuple[tuple[float, float], ...]] = {}
    action_cache: dict[tuple[Any, ...], str] = {}
    for gear_index, gear in enumerate(gears):
        branch_rows: list[tuple[Gear | None, float]] = [(None, 1.0)]
        if rank == "Epic":
            branch_rows = [(branch.gear, float(branch.probability)) for branch in enumerate_normal_epic_plus3(gear)]
        for branch_index, branch in enumerate(branch_rows):
            start_gear = gear if branch[0] is None else branch[0]
            branch_probability = branch[1]
            paths = _official_paths(start_gear, runs, seed + gear_index * 100003 + branch_index * 1009)
            for path_index, path in enumerate(paths):
                baseline, baseline_info = _outcome(path, None, probability_runs, seed, probability_cache, action_cache)
                baseline_flow = _flow(start_gear, path, baseline)
                _add(flows["current_formal"], baseline_flow, branch_probability / runs)
                for candidate in candidates:
                    outcome, info = _outcome(path, candidate, probability_runs, seed + path_index * 17, probability_cache, action_cache)
                    _add(flows[candidate.key], _flow(start_gear, path, outcome), branch_probability / runs)
                    baseline_high = baseline["stop_checkpoint"] == 15 and _target_hit(reforge_gear(path[15]), candidate)
                    _accumulate_stats(stats[candidate.key], start_gear, candidate, path, outcome, info, baseline_high, branch_probability / runs)
    return {"flows": flows, "stats": stats, "paths": float(len(gears))}


def _merge_rank_rows(epic: dict[str, Any], heroic: dict[str, Any], candidate_keys: list[str]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    result: dict[str, Any] = {}
    keys = ["current_formal", *candidate_keys]
    for key in keys:
        merged = {field: epic["flows"][key][field] / epic["paths"] + float(batch["expected_output_by_rank"]["Heroic"]) * heroic["flows"][key][field] / heroic["paths"] for field in FLOW_WITH_METRICS}
        pool = explicit_batch_resource_pool(source_gold=float(batch["expected_source_gold_per_batch"]), source_lower_stones=float(batch["expected_lower_stone_units"]), powder_base_exp=merged["powder_units"] * 100.0, lower_stone_units=merged["lower_stone_units"], material_gold=merged["material_gold"], conversion_gold=merged["conversion_gold"], sell_gold=merged["sell_gold"], sell_exp=merged["sell_exp_adjusted"], material_scarcity_exp=merged["material_exp_adjusted"], lower_stone_adjusted_exp=merged["lower_stone_adjusted_exp"])
        total = float(pool["total_stamina"])
        cycles = 100000.0 / total
        result[key] = {"flow": merged, "resource_pool": pool, "formal_baili_per_100": 100.0 * merged["value_sum"] / total, "per_100k": {field: cycles * merged[field] for field in FLOW_WITH_METRICS}, "rift_stamina_per_100k": cycles * 85.0, "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]), "cycles_per_100k": cycles, "stamina_per_baili": total / merged["value_sum"] if merged["value_sum"] else None, "by_rank": {"Epic": {field: epic["flows"][key][field] / epic["paths"] for field in FLOW_WITH_METRICS}, "Heroic": {field: float(batch["expected_output_by_rank"]["Heroic"]) * heroic["flows"][key][field] / heroic["paths"] for field in FLOW_WITH_METRICS}}}
    return result


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values) if values else 0.0
    half = _t95(len(values)) * stdev(values) / sqrt(len(values)) if len(values) > 1 else 0.0
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": stdev(values) if len(values) > 1 else 0.0}


def _summarize(per_seed: dict[str, Any], seeds: tuple[int, ...], candidates: tuple[Candidate, ...]) -> tuple[dict[str, Any], dict[str, Any]]:
    keys = ["current_formal", *(candidate.key for candidate in candidates)]
    summary: dict[str, Any] = {}
    for key in keys:
        rows = [per_seed[str(seed)]["merged"][key] for seed in seeds]
        baseline_rows = [per_seed[str(seed)]["merged"]["current_formal"] for seed in seeds]
        summary[key] = {
            "formal_baili_per_100": _ci([row["formal_baili_per_100"] for row in rows]),
            "paired_formal_delta_per_100": _ci([row["formal_baili_per_100"] - base["formal_baili_per_100"] for row, base in zip(rows, baseline_rows)]),
            "stamina_per_baili": _ci([row["stamina_per_baili"] for row in rows if row["stamina_per_baili"] is not None]),
            "per_100k": {field: _ci([row["per_100k"][field] for row in rows]) for field in FLOW_WITH_METRICS},
            "rift_stamina_per_100k": _ci([row["rift_stamina_per_100k"] for row in rows]),
            "saint_stamina_per_100k": _ci([row["saint_stamina_per_100k"] for row in rows]),
            "cycles_per_100k": _ci([row["cycles_per_100k"] for row in rows]),
            "by_rank_per_batch": {rank: {field: _ci([row["by_rank"][rank][field] for row in rows]) for field in FLOW_WITH_METRICS} for rank in ("Epic", "Heroic")},
        }
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    heroic_yield = float(batch["expected_output_by_rank"]["Heroic"])
    concentration: dict[str, Any] = {}
    for candidate in candidates:
        key = candidate.key
        rows = []
        for seed in seeds:
            e = per_seed[str(seed)]["epic_stats"][key]
            h = per_seed[str(seed)]["heroic_stats"][key]
            rows.append({
                "target_high": e["target_high"] / e["paths"] + heroic_yield * h["target_high"] / h["paths"],
                "incremental_target_high": e["incremental_target_high"] / e["paths"] + heroic_yield * h["incremental_target_high"] / h["paths"],
                "rescue_nodes": {str(node): e["rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES},
                "first_rescue_nodes": {str(node): e["first_rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["first_rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES},
                "by_rank": {"Epic": e["by_rank"]["Epic"] / e["paths"], "Heroic": heroic_yield * h["by_rank"]["Heroic"] / h["paths"]},
                "by_set": {"Epic": e["by_set"], "Heroic": h["by_set"]},
                "by_slot": {"Epic": e["by_slot"], "Heroic": h["by_slot"]},
            })
        concentration[key] = {
            "target_high_per_batch": _ci([row["target_high"] for row in rows]),
            "incremental_target_high_per_batch": _ci([row["incremental_target_high"] for row in rows]),
            "incremental_target_high_per_100k": _ci([row["incremental_target_high"] * 100000.0 / per_seed[str(seed)]["merged"][key]["resource_pool"]["total_stamina"] for row, seed in zip(rows, seeds)]),
            "rescue_nodes_per_batch": {str(node): _ci([row["rescue_nodes"][str(node)] for row in rows]) for node in RESCUE_NODES},
            "first_rescue_nodes_per_batch": {str(node): _ci([row["first_rescue_nodes"][str(node)] for row in rows]) for node in RESCUE_NODES},
            "by_rank": {rank: _ci([row["by_rank"][rank] for row in rows]) for rank in ("Epic", "Heroic")},
            "coverage": {
                "nonzero_seed_count": sum(any(row["by_rank"][rank] > 0 for rank in ("Epic", "Heroic")) for row in rows),
                "set_count": len({set_code for row in rows for rank in row["by_set"].values() for set_code, count in rank.items() if count > 0}),
                "slot_count": len({slot for row in rows for rank in row["by_slot"].values() for slot, count in rank.items() if count > 0}),
            },
        }
    return summary, concentration


def run(*, records: Path, source: Path, external: Path, seeds: tuple[int, ...], runs: int, probability_runs: int) -> dict[str, Any]:
    thresholds = inventory_thresholds(external)
    candidates = build_candidates(thresholds)
    epic_rows = load_real_plus0(records, "development")
    epic = [Gear.from_dict(row["gear"]) for row in epic_rows]
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    heroic = _source_rank_gears(source_payload, "Heroic")
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        epic_result = _run_rank(epic, "Epic", seed, runs, probability_runs, candidates)
        heroic_result = _run_rank(heroic, "Heroic", seed, runs, probability_runs, candidates)
        merged = _merge_rank_rows(epic_result, heroic_result, [candidate.key for candidate in candidates])
        per_seed[str(seed)] = {"merged": merged, "epic_stats": epic_result["stats"], "heroic_stats": heroic_result["stats"], "epic_paths": epic_result["paths"], "heroic_paths": heroic_result["paths"]}
    summary: dict[str, Any] = {}
    baseline_key = "current_formal"
    candidate_keys = [candidate.key for candidate in candidates]
    for key in [baseline_key, *candidate_keys]:
        rows = [per_seed[str(seed)]["merged"][key] for seed in seeds]
        baseline_rows = [per_seed[str(seed)]["merged"][baseline_key] for seed in seeds]
        summary[key] = {"formal_baili_per_100": _ci([row["formal_baili_per_100"] for row in rows]), "paired_formal_delta_per_100": _ci([row["formal_baili_per_100"] - base["formal_baili_per_100"] for row, base in zip(rows, baseline_rows)]), "stamina_per_baili": _ci([row["stamina_per_baili"] for row in rows if row["stamina_per_baili"] is not None]), "per_100k": {field: _ci([row["per_100k"][field] for row in rows]) for field in FLOW_WITH_METRICS}, "rift_stamina_per_100k": _ci([row["rift_stamina_per_100k"] for row in rows]), "saint_stamina_per_100k": _ci([row["saint_stamina_per_100k"] for row in rows]), "cycles_per_100k": _ci([row["cycles_per_100k"] for row in rows]), "by_rank_per_batch": {rank: {field: _ci([row["by_rank"][rank][field] for row in rows]) for field in FLOW_WITH_METRICS} for rank in ("Epic", "Heroic")}}
    concentration_summary: dict[str, Any] = {}
    for candidate in candidates:
        key = candidate.key
        rows = []
        for seed in seeds:
            e = per_seed[str(seed)]["epic_stats"][key]
            h = per_seed[str(seed)]["heroic_stats"][key]
            b = float(joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))["expected_output_by_rank"]["Heroic"])
            rows.append({"target_high": e["target_high"] / e["paths"] + b * h["target_high"] / h["paths"], "incremental_target_high": e["incremental_target_high"] / e["paths"] + b * h["incremental_target_high"] / h["paths"], "rescue_nodes": {str(node): e["rescue_nodes"][str(node)] / e["paths"] + b * h["rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}, "first_rescue_nodes": {str(node): e["first_rescue_nodes"][str(node)] / e["paths"] + b * h["first_rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}, "by_rank": {"Epic": e["by_rank"]["Epic"] / e["paths"], "Heroic": b * h["by_rank"]["Heroic"] / h["paths"]}, "by_set": {"Epic": e["by_set"], "Heroic": h["by_set"]}, "by_slot": {"Epic": e["by_slot"], "Heroic": h["by_slot"]}})
        concentration_summary[key] = {"target_high_per_batch": _ci([row["target_high"] for row in rows]), "incremental_target_high_per_batch": _ci([row["incremental_target_high"] for row in rows]), "incremental_target_high_per_100k": _ci([row["incremental_target_high"] * 100000.0 / per_seed[str(seed)]["merged"][key]["resource_pool"]["total_stamina"] for row, seed in zip(rows, seeds)]), "rescue_nodes_per_batch": {str(node): _ci([row["rescue_nodes"][str(node)] for row in rows]) for node in RESCUE_NODES}, "first_rescue_nodes_per_batch": {str(node): _ci([row["first_rescue_nodes"][str(node)] for row in rows]) for node in RESCUE_NODES}, "by_rank": {rank: _ci([row["by_rank"][rank] for row in rows]) for rank in ("Epic", "Heroic")}, "coverage": {"nonzero_seed_count": sum(any(row["by_rank"][rank] > 0 for rank in ("Epic", "Heroic")) for row in rows), "set_count": len({set_code for row in rows for rank in row["by_set"].values() for set_code, count in rank.items() if count > 0}), "slot_count": len({slot for row in rows for rank in row["by_slot"].values() for slot, count in rank.items() if count > 0})}}
    summary, concentration_summary = _summarize(per_seed, seeds, candidates)
    return {"study": STUDY, "schema_version": SCHEMA_VERSION, "scope": "offline_only_no_holdout_no_production_change", "baseline": "baili-formal-dp-v1-epic-balanced", "data": {"records": str(records), "source": str(source), "epic_development_count": len(epic), "heroic_source_count": len(heroic), "holdout_read": False}, "thresholds": thresholds, "candidates": [{**asdict(candidate), "key": candidate.key} for candidate in candidates], "runs": {"seeds": list(seeds), "paths_per_gear": runs, "probability_paths_per_state": probability_runs, "official_discrete_rolls": True}, "per_seed": per_seed, "summary": summary, "concentration": concentration_summary, "release_gate": {"status": "not_evaluated_for_release_until_user_review", "rules": ["5 seed nonzero contribution", "paired total value CI lower > 0", "formal Baili loss explicit", "multi-set/slot/rank coverage"]}, "freeze": "not_frozen_debug_only"}


def merge_seed_files(paths: list[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one seed result is required")
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    first = payloads[0]
    candidates = tuple(Candidate(**{key: row[key] for key in ("attribute", "quantile", "mode", "attack_threshold", "health_threshold")}) for row in first["candidates"])
    seeds = tuple(int(payload["runs"]["seeds"][0]) for payload in payloads)
    per_seed = {str(seed): payload["per_seed"][str(seed)] for seed, payload in zip(seeds, payloads)}
    summary, concentration = _summarize(per_seed, seeds, candidates)
    return {**first, "runs": {**first["runs"], "seeds": list(seeds)}, "per_seed": per_seed, "summary": summary, "concentration": concentration, "source_seed_files": [str(path) for path in paths], "precision_status": "five_seed_runs10_probability4; balanced/aggressive probability resolution remains coarse", "release_gate": {"status": "blocked_insufficient_probability_resolution_and_no_release", "reasons": ["probability_paths_per_state=4 cannot distinguish P>0 from P>=10% in all nonzero states", "not a production candidate"]}}


def _fmt(metric: dict[str, Any], digits: int = 4) -> str:
    lo, hi = metric["interval95"]
    return f"{metric['mean']:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def markdown(data: dict[str, Any]) -> str:
    baseline = data["summary"]["current_formal"]
    precision = data.get("precision_status", f"paths_per_gear={data['runs']['paths_per_gear']}, probability_paths_per_state={data['runs']['probability_paths_per_state']}")
    lines = ["# 超高攻击/生命集中属性救回离线研究", "", "本报告以已发布 `baili-formal-dp-v1-epic-balanced` 为基线，仅研究 `+6/+9/+12` 基线停止状态的单向救回。未读取 Holdout，未修改正式策略、DP、资源模型、GUI、OCR 或自动化。", "", f"- 研究精度：`{precision}`。", f"- 当前状态：`{data.get('release_gate', {}).get('status', 'offline_only')}`；绝对效率必须结合区间阅读，不能把本报告数值写入正式常量。", "", "## 输入与阈值", "", f"- 外部重铸库存 SHA-256：`{data['thresholds']['sha256']}`；Epic {data['thresholds']['counts']['Epic']}、Heroic {data['thresholds']['counts']['Heroic']} 件。", "- 攻击集中 GS=atkPct+atkFlat 官方 GS；生命集中 GS=hpPct+hpFlat 官方 GS；固定值使用正式官方权重。", "", "| 属性 | P90 | P95 | P97.5 |", "|---|---:|---:|---:|"]
    for attribute in ("attack", "health"):
        q = data["thresholds"]["quantiles"][attribute]
        lines.append(f"| {attribute} | {q['0.9']:.2f} | {q['0.95']:.2f} | {q['0.975']:.2f} |")
    lines.extend(["", "## 每 100,000 总体力（主场景为 Heroic 基线产出）", "", "| 候选 | 正式百里分 | 相对基线/100体力 | 原生75+ | 转换75+ | 22速 | 新增集中属性件 | 每件新增所需体力 | +6/+9/+12救回 | 裂缝体力 | 圣女体力 |", "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"])
    for candidate in data["candidates"]:
        key = candidate["key"]
        row = data["summary"][key]
        concentration = data["concentration"][key]
        delta = row["paired_formal_delta_per_100"]
        produced = concentration["incremental_target_high_per_100k"]
        cost = None if produced["mean"] <= 0 else 100000.0 / produced["mean"]
        rescue = ", ".join(f"+{node}:{data['concentration'][key]['rescue_nodes_per_batch'][str(node)]['mean']:.4f}" for node in RESCUE_NODES)
        lines.append(f"| {key} | {_fmt(row['per_100k']['value_sum'])} | {_fmt(delta, 6)} | {_fmt(row['per_100k']['native_heirloom'], 3)} | {_fmt(row['per_100k']['converted_heirloom'], 3)} | {_fmt(row['per_100k']['speed22'], 3)} | {_fmt(produced, 4)} | {'-' if cost is None else f'{cost:.1f}'} | {rescue} | {_fmt(row['rift_stamina_per_100k'], 1)} | {_fmt(row['saint_stamina_per_100k'], 1)} |")
    lines.extend(["", "## 节点、品质与覆盖", "", "- `+6/+9/+12救回` 为每联合批次的加权救回次数；首次救回节点另保存在原始 JSON。", "- JSON 保留 Epic/Heroic 的集中属性产量、资源流、套装和部位贡献；候选必须同时覆盖多个套装与部位，不能由单一事件支撑。", "", "| 候选（balanced） | Epic新增/批 | Heroic新增/批 | 覆盖套装 | 覆盖部位 |", "|---|---:|---:|---:|---:|"])
    for candidate in data["candidates"]:
        if candidate["mode"] != "balanced":
            continue
        key = candidate["key"]
        concentration = data["concentration"][key]
        lines.append(f"| {key} | {_fmt(concentration['by_rank']['Epic'], 4)} | {_fmt(concentration['by_rank']['Heroic'], 4)} | {concentration['coverage']['set_count']} | {concentration['coverage']['slot_count']} |")
    lines.extend(["", "## 强化资源变化（每10万总体力）", "", "| 候选 | 粉尘 | 下等强化石 | 强化金币 | 转换金币 | 出售回收金币 |", "|---|---:|---:|---:|---:|---:|"])
    for candidate in data["candidates"]:
        if candidate["mode"] != "balanced":
            continue
        key = candidate["key"]
        row = data["summary"][key]["per_100k"]
        lines.append(f"| {key} | {_fmt(row['powder_units'], 1)} | {_fmt(row['lower_stone_units'], 1)} | {_fmt(row['material_gold'], 0)} | {_fmt(row['conversion_gold'], 0)} | {_fmt(row['sell_gold'], 0)} |")
    lines.extend(["", "## 基线与发布状态", "", f"- 基线正式百里分：{_fmt(baseline['per_100k']['value_sum'])}/10万总体力；每点百里分体力：{_fmt(baseline['stamina_per_baili'], 1)}。", "- 所有候选仍为离线 debug 结果；必须在用户确认风险档位后，另建独立发布任务，不能自动写入正式策略。", "- `aggressive` 仅为 P>0 敏感性；本轮概率路径数为4，无法区分非零概率与10%概率，故 aggressive 与 balanced 相同，不能据此发布。", "- OR 行只作组合敏感性，不得替代攻击、生命独立发布结论。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--external", type=Path, default=EXTERNAL_SOURCE)
    parser.add_argument("--seeds", default=','.join(map(str, SEEDS)))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--probability-runs", type=int, default=32)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--merge-seed-files", nargs="*", type=Path)
    args = parser.parse_args()
    if args.merge_seed_files:
        data = merge_seed_files(args.merge_seed_files)
        args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.report_output.write_text(markdown(data) + "\n", encoding="utf-8")
        print(json.dumps({"json": str(args.json_output), "report": str(args.report_output), "seeds": data["runs"]["seeds"]}, ensure_ascii=False))
        return 0
    seeds = tuple(int(value.strip()) for value in args.seeds.split(',') if value.strip())
    data = run(records=args.records, source=args.source, external=args.external, seeds=seeds, runs=max(1, args.runs), probability_runs=max(1, args.probability_runs))
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_output.write_text(markdown(data) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(args.json_output), "report": str(args.report_output), "seeds": list(seeds)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
