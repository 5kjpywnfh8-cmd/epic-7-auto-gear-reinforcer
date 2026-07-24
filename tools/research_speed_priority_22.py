"""Offline recalibration study for the highest-priority 22-speed route.

This tool is deliberately separate from released policy and roll tables.  It
uses STOVE's normal-Epic speed probabilities and the user-confirmed normal-
Heroic mirror profile only while replaying research trajectories.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_simulator import (
    CHECKPOINTS, RollProfile, STAT_TYPE_BY_KEY, clone_gear, generate_missing_substat,
    is_new_substat_event, reforge_gear, roll_value,
)
from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.models import RollHit, Stat, round1
from src.e7_enhance.score_engine import official_score_for_stats, speed_value
from src.e7_enhance.resource_model import DEFAULT_CONVERSION_GOLD_COST, calibration_for_rank, material_pool_for_slot
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE, _gear_from_item, _source_rank_gears, _terminal_metrics,
    formal_followup_action, paired_rift_gear, simulate_strategy_path, summarize_incremental_cost,
)
from tools.external_threshold_strategy import output_effective_gs, terminal_indicators
from tools.research_riftslash_saint_pool import FLOW_FIELDS, _flow_for_outcome, _empty_flow, explicit_batch_resource_pool
from tools.speed_priority_rolls import speed_roll_distribution, sample_speed_roll


SPEED_CANDIDATES = {
    "speed_current_exact": {"description": "released rank-specific speed route"},
    "speed_hit_chain": {"description": "speed hit at every node"},
    "speed_reachable_22": {"description": "continue only while 22 remains reachable"},
    "speed_probability_cost": {"description": "22 probability against next-node cost"},
    "speed_epic_d_reference": {"description": "external D speed threshold reference"},
    "speed_heroic_d_reference": {"description": "external D speed threshold reference"},
}
SPEED_BINS = (22, 23, 24, 25, 27)
CURRENT_INITIAL_SPEED_THRESHOLDS = {
    ("normal_85", "Epic"): 2,
    ("rift_85", "Epic"): 2,
    ("normal_85", "Heroic"): 4,
}
SCHEMA_VERSION = 3


def joint_candidate_plans() -> dict[str, dict[str, str]]:
    """Return explicit normal Epic/Heroic route combinations for aggregation."""
    plans = {
        "speed_current_exact": {
            "normal_epic": "speed_current_exact",
            "normal_heroic": "speed_current_exact",
        },
        "current_epic2_reachable_heroic4": {
            "normal_epic": "speed_current_exact",
            "normal_heroic": "speed_reachable_22_heroic4",
        },
    }
    for heroic_threshold in (2, 3, 4):
        plans[f"reachable_epic2_heroic{heroic_threshold}"] = {
            "normal_epic": "speed_reachable_22_epic2",
            "normal_heroic": f"speed_reachable_22_heroic{heroic_threshold}",
        }
    return plans


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _speed_stat(gear):
    return next((stat for stat in gear.substats if stat.key == "spd"), None)


def _current_initial_threshold(gear, item_source: str) -> int:
    try:
        return CURRENT_INITIAL_SPEED_THRESHOLDS[(item_source, gear.rank)]
    except KeyError as error:
        raise ValueError(f"unsupported released speed route: {item_source} / {gear.rank}") from error


def _last_hit_speed(gear, checkpoint: int) -> bool:
    return bool(gear.roll_history and gear.roll_history[-1].enhance == checkpoint and gear.roll_history[-1].type == "Speed")


def _formal_fallback_action(gear, item_source: str) -> bool:
    """Read the released follow-up when available; retain its conservative fallback."""
    try:
        return formal_followup_action(gear, item_source)
    except KeyError:
        return advise_gear(gear, item_source=item_source)["summary"]["recommendation"] != "stop"


def _speed_increment_profile(gear, item_source: str, rare_speed_rolls_removed: bool) -> tuple[tuple[int, float], ...]:
    return speed_roll_distribution(item_source, gear.rank, rare_speed_rolls_removed=rare_speed_rolls_removed)


def _max_future_speed(gear, item_source: str, rare_speed_rolls_removed: bool) -> int:
    speed = _speed_stat(gear)
    if speed is None:
        return 0
    remaining = sum(checkpoint > gear.enhance for checkpoint in CHECKPOINTS)
    maximum = max(value for value, _ in _speed_increment_profile(gear, item_source, rare_speed_rolls_removed))
    # The terminal reforge bonus is included conservatively; the exact table
    # is intentionally left in the released simulator and used at terminal.
    return int(speed.normalized_value + remaining * maximum + 4)


def _reachable_probability(gear, item_source: str, rare_speed_rolls_removed: bool) -> float:
    speed = _speed_stat(gear)
    if speed is None:
        return 0.0
    states = {int(speed.normalized_value): 1.0}
    profile = _speed_increment_profile(gear, item_source, rare_speed_rolls_removed)
    for checkpoint in CHECKPOINTS:
        if checkpoint <= gear.enhance:
            continue
        hit_probability = 1.0 / len(gear.substats)
        next_states: dict[int, float] = defaultdict(float)
        for value, probability in states.items():
            next_states[value] += probability * (1.0 - hit_probability)
            for delta, delta_probability in profile:
                next_states[value + delta] += probability * hit_probability * delta_probability
        states = next_states
    return sum(probability for value, probability in states.items() if value + 4 >= 22)


def speed_action(
    candidate: str,
    gear,
    item_source: str,
    initial_threshold: int,
    *,
    rare_speed_rolls_removed: bool = False,
) -> str:
    """Return a research-only action from observable current state."""
    speed = _speed_stat(gear)
    if gear.slot == "boot" or speed is None:
        return "stop"
    checkpoint = gear.enhance
    if candidate == "speed_current_exact":
        if checkpoint == 0:
            return "continue" if speed.normalized_value >= _current_initial_threshold(gear, item_source) else "stop"
        if checkpoint >= 15:
            return "stop"
        if checkpoint == 3:
            return "continue" if _last_hit_speed(gear, 3) else "stop"
        return "continue" if _formal_fallback_action(gear, item_source) else "stop"
    if checkpoint == 0:
        return "continue" if speed.normalized_value >= initial_threshold else "stop"
    if checkpoint >= 15:
        return "stop"
    if candidate == "speed_hit_chain":
        return "continue" if _last_hit_speed(gear, checkpoint) else "stop"
    if candidate == "speed_reachable_22":
        return "continue" if _max_future_speed(gear, item_source, rare_speed_rolls_removed) >= 22 else "stop"
    if candidate == "speed_probability_cost":
        probability = _reachable_probability(gear, item_source, rare_speed_rolls_removed)
        cost = summarize_incremental_cost(gear.slot, gear.rank, checkpoint, next(point for point in CHECKPOINTS if point > checkpoint))["net_stamina"]
        return "continue" if probability * 22.0 >= max(0.2, cost * 0.14) else "stop"
    if candidate == "speed_epic_d_reference":
        thresholds = {0: 2, 3: 3, 6: 5, 9: 9}
        return "continue" if gear.rank == "Epic" and speed.normalized_value >= thresholds.get(checkpoint, 999) else "stop"
    if candidate == "speed_heroic_d_reference":
        thresholds = {0: 2, 3: 3, 6: 5, 9: 10}
        return "continue" if gear.rank == "Heroic" and speed.normalized_value >= thresholds.get(checkpoint, 999) else "stop"
    raise ValueError(f"unknown speed candidate: {candidate}")


def _enhance_to_checkpoint(gear, checkpoint: int, item_source: str, rng: random.Random, rare_speed_rolls_removed: bool):
    if is_new_substat_event(gear.rank, checkpoint) and len(gear.substats) < 4:
        return replace(gear, enhance=checkpoint, substats=gear.substats + [generate_missing_substat(rng, gear, item_source)])
    if not gear.substats:
        return replace(gear, enhance=checkpoint)
    index = rng.randrange(len(gear.substats))
    hit = gear.substats[index]
    profile = RollProfile(gear.roll_level or gear.level, gear.rank, item_source)
    delta = sample_speed_roll(rng, item_source, gear.rank, rare_speed_rolls_removed=rare_speed_rolls_removed) if hit.key == "spd" else roll_value(rng, profile, hit.key)
    updated = replace(hit, value=round1(hit.normalized_value + delta), rolls=hit.rolls + 1)
    substats = list(gear.substats)
    substats[index] = updated
    history = list(gear.roll_history) + [RollHit(checkpoint, updated.type, delta)]
    return replace(gear, enhance=checkpoint, substats=substats, roll_history=history)


def simulate_speed_paths(gear, item_source: str, runs: int, rng: random.Random, *, rare_speed_rolls_removed: bool = False) -> list[dict[int, Any]]:
    paths = []
    for _ in range(runs):
        current = clone_gear(gear)
        path = {current.enhance: current}
        for checkpoint in CHECKPOINTS:
            if checkpoint > current.enhance:
                current = _enhance_to_checkpoint(current, checkpoint, item_source, rng, rare_speed_rolls_removed)
                path[checkpoint] = current
        paths.append(path)
    return paths


def _run_path(path, candidate: str, item_source: str, threshold: int, rare: bool, final_terminal: dict[str, Any]) -> dict[str, Any]:
    current = min(path)
    actions, reached, hits = {}, [current], {checkpoint: 0.0 for checkpoint in CHECKPOINTS[:-1]}
    while current < 15:
        state = path[current]
        action = speed_action(candidate, state, item_source, threshold, rare_speed_rolls_removed=rare)
        actions[current] = action
        if current and _last_hit_speed(state, current):
            hits[current] = 1.0
        if action == "stop":
            break
        current = next(checkpoint for checkpoint in CHECKPOINTS if checkpoint > current)
        reached.append(current)
    final_speed = float(final_terminal["final_speed"]) if current == 15 else 0.0
    return {"stop": current, "actions": actions, "reached": reached, "hits": hits, "speed": final_speed, "terminal": final_terminal if current == 15 else None}


def _empty_row() -> dict[str, Any]:
    return {
        "paths": 0,
        "reached": {str(x): 0.0 for x in CHECKPOINTS},
        "stop": {str(x): 0.0 for x in CHECKPOINTS},
        "speed_hits": {str(x): 0.0 for x in CHECKPOINTS[:-1]},
        "speed_bins": {"22": 0.0, "23": 0.0, "24": 0.0, "25": 0.0, "27+": 0.0},
        "terminal_indicators": {"native_heirloom": 0.0, "converted_heirloom": 0.0, "output60": 0.0},
        "flow": _empty_flow(),
    }


def conditional_rate_row(row: dict[str, Any]) -> dict[str, Any]:
    """Summarize already-owned speed embryos without any acquisition stamina."""
    paths = max(1.0, row["paths"])
    flow = {field: row["flow"][field] / paths for field in FLOW_FIELDS}
    pool = explicit_batch_resource_pool(
        source_gold=0.0, source_lower_stones=0.0,
        powder_base_exp=flow["powder_units"] * 100, lower_stone_units=flow["lower_stone_units"],
        material_gold=flow["material_gold"], conversion_gold=flow["conversion_gold"],
        sell_gold=flow["sell_gold"], sell_exp=flow["sell_exp_adjusted"],
        material_scarcity_exp=flow["material_exp_adjusted"], lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
    )
    bins = {name: row["speed_bins"][name] / paths for name in row["speed_bins"]}
    incremental_stamina = float(pool["saint_supplement_stamina"])
    return {
        "paths": paths,
        "speed_bins_per_embryo": bins,
        "22_per_100_speed_embryos": 100.0 * bins["22"],
        "incremental_stamina_per_22": incremental_stamina / bins["22"] if bins["22"] else None,
        "22_per_100_incremental_stamina": 100.0 * bins["22"] / incremental_stamina if incremental_stamina else None,
        "acquisition_stamina": 0.0,
        "incremental_total_stamina": incremental_stamina,
        "formal_value_per_embryo": flow["value_sum"],
        "terminal_indicators_per_embryo": {
            key: value / paths for key, value in row["terminal_indicators"].items()
        },
        "node_reached_rate": {key: value / paths for key, value in row["reached"].items()},
        "node_stop_rate": {key: value / paths for key, value in row["stop"].items()},
        "node_speed_hit_rate": {key: value / paths for key, value in row["speed_hits"].items()},
        "flow_per_embryo": flow,
    }


def candidate_entries_for(gear, item_source: str) -> tuple[tuple[str, str, int], ...]:
    """List research candidates valid for one quality/source without weakening Epic=2."""
    entries: list[tuple[str, str, int]] = [
        ("speed_current_exact", "speed_current_exact", _current_initial_threshold(gear, item_source)),
    ]
    if gear.rank == "Epic":
        entries.extend([
            ("speed_hit_chain_epic2", "speed_hit_chain", 2),
            ("speed_reachable_22_epic2", "speed_reachable_22", 2),
            ("speed_probability_cost_epic2", "speed_probability_cost", 2),
            ("speed_epic_d_reference", "speed_epic_d_reference", 2),
        ])
    elif gear.rank == "Heroic":
        for threshold in (2, 3, 4):
            entries.extend([
                (f"speed_hit_chain_heroic{threshold}", "speed_hit_chain", threshold),
                (f"speed_reachable_22_heroic{threshold}", "speed_reachable_22", threshold),
                (f"speed_probability_cost_heroic{threshold}", "speed_probability_cost", threshold),
            ])
        entries.append(("speed_heroic_d_reference", "speed_heroic_d_reference", 4))
    else:
        raise ValueError(f"unsupported speed-study rank: {gear.rank}")
    return tuple(entries)


def _shard(gear, item_source: str, runs: int, random_seed: int, rare: bool) -> dict[str, Any]:
    entries = candidate_entries_for(gear, item_source)
    rows = {name: _empty_row() for name, _candidate, _threshold in entries}
    paths = simulate_speed_paths(gear, item_source, runs, random.Random(random_seed), rare_speed_rolls_removed=rare)
    for path in paths:
        # Every candidate sees the same complete trajectory.  Score its +15
        # state once; stopped paths do not need a fictitious terminal score.
        final_terminal = _terminal_metrics(path[15], item_source)
        for name, candidate, threshold in entries:
            result = _run_path(path, candidate, item_source, threshold, rare, final_terminal)
            row = rows[name]
            row["paths"] += 1
            for checkpoint in result["reached"]:
                row["reached"][str(checkpoint)] += 1
            row["stop"][str(result["stop"])] += 1
            for checkpoint, hit in result["hits"].items():
                row["speed_hits"][str(checkpoint)] += hit
            if result["stop"] == 15:
                speed = result["speed"]
                for cut in SPEED_BINS:
                    if speed >= cut:
                        row["speed_bins"]["27+" if cut == 27 else str(cut)] += 1
                final = reforge_gear(path[15])
                indicators = terminal_indicators(
                    native_total_gs=float(final_terminal["official_substat_gs"]),
                    converted_total_gs=float(final_terminal["converted_official_substat_gs"]),
                    speed=speed,
                    output_gs=output_effective_gs(final),
                )
                for key, value in indicators.items():
                    if key != "speed22":
                        row["terminal_indicators"][key] += value
            terminal = result["terminal"] or {"final_speed": 0.0}
            flow = _flow_for_outcome(
                gear,
                {"start_checkpoint": min(path), "stop_checkpoint": result["stop"], "net_stamina": 0.0},
                bool(result["stop"] == 15 and terminal.get("conversion_needed")),
                terminal,
            )
            for field in FLOW_FIELDS:
                row["flow"][field] += flow[field]
    return {"paths": runs, "candidates": rows}


def _path(resume: Path, group: str, seed: int, index: int, chunk: int, rare: bool) -> Path:
    suffix = "rare-removed" if rare else "official"
    return resume / suffix / "shards" / group / f"seed-{seed}" / f"gear-{index:04d}-chunk-{chunk:03d}.json"


def _valid(path: Path) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("schema_version") == SCHEMA_VERSION
    except (OSError, ValueError):
        return False


def _job(job: dict[str, Any]) -> dict[str, Any]:
    payload = _shard(job["gear"], job["item_source"], job["runs"], job["random_seed"], job["rare"])
    payload.update({key: job[key] for key in ("group", "seed", "index", "chunk", "runs")})
    payload["schema_version"] = SCHEMA_VERSION
    return payload


def _seed_value(seed: int, group: str, index: int, chunk: int) -> int:
    group_offset = {"normal_epic": 0, "normal_heroic": 100_003, "rift_epic": 200_003}[group]
    return seed * 1_000_003 + group_offset + index * 1_009 + chunk * 37


def _speed_gears(source: dict[str, Any], rank: str):
    return [gear for gear in _source_rank_gears(source, rank) if gear.slot != "boot" and _speed_stat(gear) is not None]


def run(source: Path, resume: Path, seeds: list[int], runs_per_seed: int, chunk_runs: int, workers: int, rare: bool) -> dict[str, Any]:
    if runs_per_seed % chunk_runs:
        raise ValueError("runs-per-seed must be divisible by chunk-runs")
    payload = json.loads(source.read_text(encoding="utf-8"))
    normal_epic = _speed_gears(payload, "Epic")
    normal_heroic = _speed_gears(payload, "Heroic")
    groups = {"normal_epic": (normal_epic, "normal_85"), "normal_heroic": (normal_heroic, "normal_85"), "rift_epic": ([paired_rift_gear(gear) for gear in normal_epic], "rift_85")}
    jobs, skipped = [], 0
    for group, (gears, item_source) in groups.items():
        for seed in seeds:
            for index, gear in enumerate(gears):
                for chunk in range(runs_per_seed // chunk_runs):
                    path = _path(resume, group, seed, index, chunk, rare)
                    if _valid(path):
                        skipped += 1
                    else:
                        jobs.append({"group": group, "gear": gear, "item_source": item_source, "seed": seed, "index": index, "chunk": chunk, "runs": chunk_runs, "random_seed": _seed_value(seed, group, index, chunk), "rare": rare, "path": str(path)})
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for job, result in zip(jobs, executor.map(_job, jobs)):
            _atomic_json(Path(job["path"]), result)
    return {"groups": {key: len(value[0]) for key, value in groups.items()}, "execution": {"scheduled_shards": len(jobs), "skipped_shards": skipped, "runtime_seconds": time.monotonic() - started}, "seeds": seeds, "runs_per_gear": runs_per_seed * len(seeds), "rare_speed_rolls_removed": rare, "resume_dir": str(resume), "summary": summarize(resume, seeds, rare)}


def _merge_row(target: dict[str, Any], source: dict[str, Any]) -> None:
    target["paths"] += source["paths"]
    for key in ("reached", "stop", "speed_hits", "speed_bins", "terminal_indicators"):
        for name, value in source[key].items():
            target[key][name] += value
    for field in FLOW_FIELDS:
        target["flow"][field] += source["flow"][field]


def _ci(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [values[0] if values else 0.0, values[0] if values else 0.0]
    half = 2.776 * stdev(values) / sqrt(len(values)) if len(values) == 5 else 1.96 * stdev(values) / sqrt(len(values))
    center = mean(values)
    return [center - half, center + half]


def summarize(resume: Path, seeds: list[int], rare: bool) -> dict[str, Any]:
    suffix = "rare-removed" if rare else "official"
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        by_group: dict[str, dict[str, Any]] = {}
        for group in ("normal_epic", "normal_heroic", "rift_epic"):
            rows: dict[str, Any] = {}
            for path in (resume / suffix / "shards" / group / f"seed-{seed}").glob("*.json"):
                for key, row in json.loads(path.read_text(encoding="utf-8"))["candidates"].items():
                    target = rows.setdefault(key, _empty_row())
                    _merge_row(target, row)
            by_group[group] = {key: conditional_rate_row(row) for key, row in rows.items() if row["paths"]}
        per_seed[str(seed)] = by_group
    candidates = sorted({key for seed in per_seed.values() for group in seed.values() for key in group})
    grouped: dict[str, Any] = {}
    for group in ("normal_epic", "normal_heroic", "rift_epic"):
        grouped[group] = {}
        for key in candidates:
            values = [per_seed[str(seed)].get(group, {}).get(key, {}).get("22_per_100_incremental_stamina") for seed in seeds]
            values = [value for value in values if value is not None]
            if values:
                seed_rows = [per_seed[str(seed)][group][key] for seed in seeds if key in per_seed[str(seed)].get(group, {})]
                stamina_per_22 = [
                    row["incremental_stamina_per_22"]
                    for row in seed_rows
                    if row["incremental_stamina_per_22"] is not None
                ]
                grouped[group][key] = {
                    "22_per_100_incremental_stamina": mean(values),
                    "interval95": _ci(values),
                    "22_per_100_speed_embryos": mean(row["22_per_100_speed_embryos"] for row in seed_rows),
                    "incremental_stamina_per_22": mean(stamina_per_22) if stamina_per_22 else None,
                    "incremental_total_stamina": mean(row["incremental_total_stamina"] for row in seed_rows),
                    "formal_value_per_embryo": mean(row["formal_value_per_embryo"] for row in seed_rows),
                    "terminal_indicators_per_embryo": {
                        indicator: mean(row["terminal_indicators_per_embryo"][indicator] for row in seed_rows)
                        for indicator in ("native_heirloom", "converted_heirloom", "output60")
                    },
                }
    paired = {}
    for group, values in grouped.items():
        reference = "speed_current_exact"
        for key in values:
            if key == reference:
                continue
            pairs = []
            for seed in seeds:
                left = per_seed[str(seed)].get(group, {}).get(key, {})
                right = per_seed[str(seed)].get(group, {}).get(reference, {})
                left_rate = left.get("22_per_100_incremental_stamina")
                right_rate = right.get("22_per_100_incremental_stamina")
                if left_rate is not None and right_rate is not None:
                    pairs.append(left_rate - right_rate)
            if pairs:
                formal_deltas = [
                    per_seed[str(seed)][group][key]["formal_value_per_embryo"]
                    - per_seed[str(seed)][group][reference]["formal_value_per_embryo"]
                    for seed in seeds
                    if key in per_seed[str(seed)].get(group, {}) and reference in per_seed[str(seed)].get(group, {})
                ]
                indicator_deltas = {}
                for indicator in ("native_heirloom", "converted_heirloom", "output60"):
                    values_for_indicator = [
                        per_seed[str(seed)][group][key]["terminal_indicators_per_embryo"][indicator]
                        - per_seed[str(seed)][group][reference]["terminal_indicators_per_embryo"][indicator]
                        for seed in seeds
                        if key in per_seed[str(seed)].get(group, {}) and reference in per_seed[str(seed)].get(group, {})
                    ]
                    indicator_deltas[indicator] = {"mean": mean(values_for_indicator), "interval95": _ci(values_for_indicator)}
                paired[f"{group}:{key}-speed_current_exact"] = {
                    "mean": mean(pairs),
                    "interval95": _ci(pairs),
                    "formal_value_per_embryo_delta": {"mean": mean(formal_deltas), "interval95": _ci(formal_deltas)},
                    "terminal_indicator_deltas": indicator_deltas,
                }
    joint_plans = {
        name: {
            "status": "conditional_components_only",
            "members": members,
            "reason": "缺少自然初始速度与掉落权重，不得将条件胚子合并为副本产量。",
        }
        for name, members in joint_candidate_plans().items()
    }
    return {
        "probability_profile": "rare_speed_rolls_removed" if rare else "official_stove_epic_user_confirmed_heroic",
        "per_seed": per_seed,
        "groups": grouped,
        "paired_vs_current_exact": paired,
        "joint_conditional_plans": joint_plans,
        "full_pool_efficiency": {
            "status": "not_estimated",
            "reason": "输入已筛选为已获得的速度胚子，且缺少自然初始速度/掉落权重与固定非速度分支。",
        },
    }


def markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# 22速优先路线口径修正研究", "",
        "- normal_85 Epic 强化速度概率来自 STOVE 官方表：2/3/4 各 33.223%，5 为 0.332%。",
        "- normal_85 Heroic 强化速度概率来自用户确认规则：1 为 0.332%，2/3/4 各 33.223%，无 5 速。",
        "- rift_85 Epic 使用既有独立异界表；没有套用 normal_85 分布。",
        "- 本报告只用于离线研究，未修改正式跳值表、策略、lambda 或 GUI。",
        "- 输入仅为已获得的非鞋速度胚子；所有数值均为边际强化口径，不代表副本掉落产量。", "",
        "## 执行", "",
        f"- 轨迹：{result['runs_per_gear']} / 件；seed：{', '.join(map(str, result['seeds']))}。",
        f"- 样本：normal Epic {result['groups']['normal_epic']}，normal Heroic {result['groups']['normal_heroic']}，rift Epic {result['groups']['rift_epic']}。",
        f"- 概率视图：{summary['probability_profile']}。旧 `riftslash_saint_pool_22speed_*` 的 0.7% 尾部结果已失效，未被读取或合并。", "",
        "## 条件边际效率", "", "| 来源 | 候选 | 22速/100速度胚子 | 22速/100增量体力 | 95%区间 | 每22速增量体力 | 原生75+ | 转换75+ | 输出60 |", "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group, values in summary["groups"].items():
        for candidate, value in sorted(values.items()):
            low, high = value["interval95"]
            per_22 = value["incremental_stamina_per_22"]
            per_22_text = f"{per_22:.3f}" if per_22 is not None else "N/A"
            indicators = value["terminal_indicators_per_embryo"]
            lines.append(f"| {group} | {candidate} | {value['22_per_100_speed_embryos']:.6f} | {value['22_per_100_incremental_stamina']:.6f} | [{low:.6f}, {high:.6f}] | {per_22_text} | {indicators['native_heirloom']:.6f} | {indicators['converted_heirloom']:.6f} | {indicators['output60']:.6f} |")
    lines.extend(["", "## 相对真实当前路线的同seed成对差", "", "| 对比 | 22速/100增量体力差 | 95%区间 | 正式价值差/胚子 | 原生75+差/胚子 | 转换75+差/胚子 | 输出60差/胚子 |", "|---|---:|---:|---:|---:|---:|---:|"])
    for candidate, value in sorted(summary["paired_vs_current_exact"].items()):
        low, high = value["interval95"]
        indicators = value["terminal_indicator_deltas"]
        lines.append(f"| {candidate} | {value['mean']:.6f} | [{low:.6f}, {high:.6f}] | {value['formal_value_per_embryo_delta']['mean']:.6f} | {indicators['native_heirloom']['mean']:.6f} | {indicators['converted_heirloom']['mean']:.6f} | {indicators['output60']['mean']:.6f} |")
    lines.extend(["", "## 品质独立联合组合", ""])
    for name, plan in summary["joint_conditional_plans"].items():
        members = ", ".join(f"{group}={candidate}" for group, candidate in plan["members"].items())
        lines.append(f"- `{name}`：{members}。{plan['reason']}")
    lines.extend(["", "## 完整装备池效率", "", f"- 状态：`{summary['full_pool_efficiency']['status']}`。{summary['full_pool_efficiency']['reason']}", "", "## 限制", "", "- JSON保留各节点到达率、停止率、速度命中率、22/23/24/25/27+分布、正式价值、原生75+、转换75+、输出60和完整资源流。", "- 未取得自然初始速度与掉落权重前，不得将条件胚子指标称为每100总体力副本产量，也不得合并为联合批次排名。"])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline 22-speed priority research")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "speed_priority_22_methodology_v3_resume_20260713")
    parser.add_argument("--seeds", default="20260712,20260713,20260714,20260715,20260716")
    parser.add_argument("--runs-per-seed", type=int, default=5000)
    parser.add_argument("--chunk-runs", type=int, default=500)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rare-speed-rolls-removed", action="store_true")
    args = parser.parse_args()
    seeds = [int(value) for value in args.seeds.split(",")]
    if len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be unique")
    result = run(args.source, args.resume_dir, seeds, args.runs_per_seed, args.chunk_runs, args.workers, args.rare_speed_rolls_removed)
    result["probability_sources"] = {"normal_epic": "STOVE official probability table", "normal_heroic": "user-confirmed project rule", "rift_epic": "existing independent rift table"}
    suffix = "rare_removed" if args.rare_speed_rolls_removed else "official"
    _atomic_json(ROOT / "reports" / f"speed_priority_22_methodology_v3_{suffix}_20260713.json", result)
    (ROOT / "reports" / f"speed_priority_22_methodology_v3_{suffix}_20260713.md").write_text(markdown(result), encoding="utf-8")


if __name__ == "__main__":
    main()
