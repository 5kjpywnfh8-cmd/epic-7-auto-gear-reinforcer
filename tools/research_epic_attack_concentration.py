"""Exact offline study for attack-concentration rescue candidates.

This is deliberately independent from the health v4 study.  It keeps the
released policy immutable, binds every rescue decision to the selected formal
candidate at that node, and persists only attack-study shards.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_simulator import (
    STAT_POOL,
    reforge_bonus_value,
    reforge_gear,
    slot_forbidden_substats,
)
from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from src.e7_enhance.rules import CATEGORY_RULES, OFFICIAL_SCORE_WEIGHTS, VALID_STATS
from tools import research_epic_concentration_rescue_exact as health_v4
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, _heroic_base_action, _source_rank_gears, formal_followup_action, summarize_incremental_cost
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_epic_concentration_rescue import EXTERNAL_SOURCE, inventory_thresholds
from tools.research_epic_exact_plus3 import _formal_action, load_real_plus0
from tools.research_riftslash_saint_pool import YIELD_VARIATIONS, _t95, explicit_batch_resource_pool


STUDY = "epic_attack_concentration_exact_v1_20260721"
SCHEMA_VERSION = 1
SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
CHECKPOINTS = (0, 3, 6, 9, 12, 15)
RESCUE_NODES = (6, 9, 12)
ATTACK_KEYS = frozenset({"atkPct", "atkFlat"})
ATTACK_ALLOWED_CATEGORIES = frozenset({"输出", "输出(必爆)", "半肉(通用)", "半肉(白字)"})
FROZEN_THRESHOLDS = (("p90", 0.90, 23.00), ("p95", 0.95, 26.99), ("p975", 0.975, 32.00))
DEFAULT_RECORDS = ROOT / "manual_acceptance" / "real_sample_records.json"
DEFAULT_SOURCE = ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json"
DEFAULT_EXTERNAL = EXTERNAL_SOURCE
DEFAULT_RESUME = ROOT / "reports" / "epic_attack_concentration_exact_resume_20260721"
DEFAULT_JSON = ROOT / "reports" / "epic_attack_concentration_exact_20260721.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_attack_concentration_exact_20260721.md"
ESTIMATOR_HASH = sha256(Path(__file__).read_bytes()).hexdigest()
_DIST_CACHE: dict[tuple[str, str], tuple[tuple[int, float], ...]] = {}
_MAX_INCREMENT_CACHE: dict[tuple[str, tuple[str, ...]], float] = {}


@dataclass(frozen=True)
class AttackCandidate:
    label: str
    quantile: float
    threshold: float
    mode: str

    @property
    def key(self) -> str:
        return f"attack_{self.label}_{self.mode}"

    @property
    def probability_floor(self) -> float:
        return 0.10 if self.mode == "balanced" else 0.0


def candidates() -> tuple[AttackCandidate, ...]:
    rows: list[AttackCandidate] = []
    for label, quantile, threshold in FROZEN_THRESHOLDS:
        rows.append(AttackCandidate(label, quantile, threshold, "balanced"))
        rows.append(AttackCandidate(label, quantile, threshold, "reachable_reference"))
    return tuple(rows)


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _roll_distribution(rank: str, key: str) -> tuple[tuple[int, float], ...]:
    cache_key = (rank, key)
    if cache_key not in _DIST_CACHE:
        _DIST_CACHE[cache_key] = health_v4._roll_distribution(rank, key)
    return _DIST_CACHE[cache_key]


def _normalize_attack_keys(keys: Any) -> tuple[str, ...]:
    return tuple(sorted(set(str(key) for key in (keys or ()) if str(key) in ATTACK_KEYS)))


def _state_signature(state: Gear) -> tuple[Any, ...]:
    return (
        state.enhance,
        state.rank,
        state.level,
        state.slot,
        state.main_stat.key,
        tuple((stat.key, stat.normalized_value, stat.rolls) for stat in state.substats),
    )


@dataclass(frozen=True)
class AttackContext:
    category: str
    source_row: str
    set_group: str
    valid_group: str
    valid_keys: tuple[str, ...]
    attack_valid_keys: tuple[str, ...]
    compatible: bool
    reason: str

    @property
    def cache_key(self) -> tuple[Any, ...]:
        return (
            self.category,
            self.source_row,
            self.set_group,
            self.valid_group,
            self.valid_keys,
            self.attack_valid_keys,
            self.compatible,
        )


def _rule_for_category(category: str) -> dict[str, Any] | None:
    matches = [rule for rule in CATEGORY_RULES if str(rule.get("category")) == category]
    return matches[0] if len(matches) == 1 else None


def _attack_context_from_snapshot(snapshot: dict[str, Any]) -> AttackContext:
    category = str(snapshot.get("category") or "unknown")
    selected = snapshot.get("candidate") or {}
    rule = _rule_for_category(category)
    source_row = str(selected.get("source_row") or selected.get("sourceRow") or "")
    set_group = str(selected.get("set_group") or selected.get("setGroup") or "")
    valid_group = str(rule.get("validGroup") or "") if rule else ""
    valid_keys = tuple(sorted(VALID_STATS.get(valid_group, []))) if rule else ()
    attack_valid_keys = tuple(sorted(set(valid_keys) & ATTACK_KEYS))
    reasons = list(selected.get("rejection_reasons") or [])
    rule_matches = bool(
        rule
        and category == str(selected.get("category") or category)
        and source_row == str(rule.get("sourceRow") or "")
        and set_group == str(rule.get("setGroup") or "")
    )
    compatible = bool(
        category in ATTACK_ALLOWED_CATEGORIES
        and bool(selected.get("qualified"))
        and not reasons
        and rule_matches
        and attack_valid_keys
    )
    return AttackContext(
        category=category,
        source_row=source_row,
        set_group=set_group,
        valid_group=valid_group,
        valid_keys=valid_keys,
        attack_valid_keys=attack_valid_keys,
        compatible=compatible,
        reason="compatible" if compatible else "selected_candidate_rule_or_attack_keys_not_compatible",
    )


def _context_dict(context: AttackContext) -> dict[str, Any]:
    return {
        "compatible": context.compatible,
        "category": context.category,
        "source_row": context.source_row,
        "set_group": context.set_group,
        "valid_group": context.valid_group,
        "valid_keys": list(context.valid_keys),
        "attack_valid_keys": list(context.attack_valid_keys),
        "reason": context.reason,
        "cache_key": list(context.cache_key),
    }


def attack_compatibility_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Fail closed unless the selected formal candidate permits attack keys."""
    return _context_dict(_attack_context_from_snapshot(snapshot))


def attack_compatibility(state: Gear) -> dict[str, Any]:
    return attack_compatibility_from_snapshot(phase_b.selected_candidate_snapshot(state))


def _attack_concentration(gear: Gear, attack_valid_keys: Any = ATTACK_KEYS) -> float:
    keys = set(_normalize_attack_keys(attack_valid_keys))
    return round(
        sum(stat.normalized_value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0) for stat in gear.substats if stat.key in keys),
        4,
    )


def _initial_attack_state(gear: Gear, attack_valid_keys: Any) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...], float]:
    keys = _normalize_attack_keys(attack_valid_keys)
    all_keys = tuple(sorted(stat.key for stat in gear.substats))
    rolls = tuple(sorted((stat.key, stat.rolls) for stat in gear.substats if stat.key in keys))
    return all_keys, rolls, _attack_concentration(reforge_gear(gear), keys)


def _available_new_keys(all_keys: tuple[str, ...], slot: str, main_key: str) -> tuple[str, ...]:
    blocked = set(all_keys) | {main_key} | slot_forbidden_substats(slot)
    return tuple(key for key in STAT_POOL if key not in blocked)


def _max_attack_increment(rank: str, attack_valid_keys: tuple[str, ...]) -> float:
    cache_key = (rank, attack_valid_keys)
    if cache_key not in _MAX_INCREMENT_CACHE:
        values: list[float] = []
        for key in attack_valid_keys:
            weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
            maximum = max(delta for delta, _probability in _roll_distribution(rank, key))
            values.extend(
                weight * round(reforge_bonus_value(key, rolls + 1) - reforge_bonus_value(key, rolls) + maximum, 4)
                for rolls in range(6)
            )
        _MAX_INCREMENT_CACHE[cache_key] = max(values, default=0.0)
    return _MAX_INCREMENT_CACHE[cache_key]


def _attack_upper_bound(
    rank: str,
    slot: str,
    main_key: str,
    checkpoint: int,
    all_keys: tuple[str, ...],
    attack_rolls: tuple[tuple[str, int], ...],
    concentration: float,
    attack_valid_keys: tuple[str, ...],
) -> float:
    """Loose optimistic bound; it may overestimate but never prune success."""
    bound = concentration
    current = checkpoint
    keys = tuple(all_keys)
    rolls = tuple(attack_rolls)
    while current < 15:
        next_checkpoint = next(point for point in CHECKPOINTS if point > current)
        if next_checkpoint == 12 and rank == "Heroic" and len(keys) < 4:
            available = _available_new_keys(keys, slot, main_key)
            choices: list[tuple[float, str]] = []
            for key in attack_valid_keys:
                if key in available:
                    maximum = max(delta for delta, _probability in _roll_distribution(rank, key))
                    choices.append((OFFICIAL_SCORE_WEIGHTS.get(key, 0.0) * round(maximum + reforge_bonus_value(key, 1), 4), key))
            if choices:
                gain, key = max(choices)
                bound += gain
                keys = tuple(sorted((*keys, key)))
                rolls = tuple(sorted((*rolls, (key, 1))))
            else:
                keys = tuple(sorted((*keys, "__non_attack_fourth__")))
        else:
            bound += _max_attack_increment(rank, attack_valid_keys)
        current = next_checkpoint
    return bound


def _exact_attack_probability_pruned(gear: Gear, threshold: float, attack_valid_keys: tuple[str, ...]) -> float:
    all_keys, initial_rolls, initial_concentration = _initial_attack_state(gear, attack_valid_keys)
    pending: dict[tuple[int, tuple[str, ...], tuple[tuple[str, int], ...], float], float] = {
        (gear.enhance, all_keys, initial_rolls, initial_concentration): 1.0
    }
    success = 0.0
    while pending:
        (checkpoint, keys, current_rolls, concentration), probability = pending.popitem()
        if concentration >= threshold:
            success += probability
            continue
        if _attack_upper_bound(gear.rank, gear.slot, gear.main_stat.key, checkpoint, keys, current_rolls, concentration, attack_valid_keys) < threshold:
            continue
        if checkpoint >= 15:
            continue
        next_checkpoint = next(point for point in CHECKPOINTS if point > checkpoint)
        if next_checkpoint == 12 and gear.rank == "Heroic" and len(keys) < 4:
            available = _available_new_keys(keys, gear.slot, gear.main_stat.key)
            key_probability = 1.0 / len(available)
            non_attack = sum(key not in set(attack_valid_keys) for key in available)
            if non_attack:
                state_key = (next_checkpoint, tuple(sorted((*keys, "__non_attack_fourth__"))), current_rolls, concentration)
                pending[state_key] = pending.get(state_key, 0.0) + probability * non_attack * key_probability
            for key in attack_valid_keys:
                if key not in available:
                    continue
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    updated = tuple(sorted((*current_rolls, (key, 1))))
                    value = round(concentration + OFFICIAL_SCORE_WEIGHTS.get(key, 0.0) * round(delta + reforge_bonus_value(key, 1), 4), 4)
                    state_key = (next_checkpoint, tuple(sorted((*keys, key))), updated, value)
                    pending[state_key] = pending.get(state_key, 0.0) + probability * key_probability * roll_probability
        else:
            count = len(keys)
            non_attack = count - len(current_rolls)
            if non_attack:
                state_key = (next_checkpoint, keys, current_rolls, concentration)
                pending[state_key] = pending.get(state_key, 0.0) + probability * non_attack / count
            for index, (key, roll_count) in enumerate(current_rolls):
                bonus = reforge_bonus_value(key, roll_count + 1) - reforge_bonus_value(key, roll_count)
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    updated_rows = list(current_rolls)
                    updated_rows[index] = (key, roll_count + 1)
                    value = round(concentration + OFFICIAL_SCORE_WEIGHTS.get(key, 0.0) * round(delta + bonus, 4), 4)
                    state_key = (next_checkpoint, keys, tuple(sorted(updated_rows)), value)
                    pending[state_key] = pending.get(state_key, 0.0) + probability * roll_probability / count
    return success


def exact_attack_distribution(gear: Gear, attack_valid_keys: Any = ATTACK_KEYS) -> tuple[tuple[float, float], ...]:
    """Full exact distribution used for independent small-state regression tests."""
    valid_keys = _normalize_attack_keys(attack_valid_keys)
    all_keys, initial_rolls, initial_concentration = _initial_attack_state(gear, valid_keys)
    pending: dict[tuple[int, tuple[str, ...], tuple[tuple[str, int], ...], float], float] = {
        (gear.enhance, all_keys, initial_rolls, initial_concentration): 1.0
    }
    terminal: dict[float, float] = {}
    while pending:
        (checkpoint, keys, current_rolls, concentration), probability = pending.popitem()
        if checkpoint >= 15:
            terminal[round(concentration, 4)] = terminal.get(round(concentration, 4), 0.0) + probability
            continue
        next_checkpoint = next(point for point in CHECKPOINTS if point > checkpoint)
        next_mass: dict[tuple[int, tuple[str, ...], tuple[tuple[str, int], ...], float], float] = {}
        if next_checkpoint == 12 and gear.rank == "Heroic" and len(keys) < 4:
            available = _available_new_keys(keys, gear.slot, gear.main_stat.key)
            key_probability = 1.0 / len(available)
            non_attack = sum(key not in set(valid_keys) for key in available)
            if non_attack:
                state_key = (next_checkpoint, tuple(sorted((*keys, "__non_attack_fourth__"))), current_rolls, concentration)
                next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * non_attack * key_probability
            for key in valid_keys:
                if key not in available:
                    continue
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    value = round(concentration + OFFICIAL_SCORE_WEIGHTS.get(key, 0.0) * round(delta + reforge_bonus_value(key, 1), 4), 4)
                    state_key = (next_checkpoint, tuple(sorted((*keys, key))), tuple(sorted((*current_rolls, (key, 1)))), value)
                    next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * key_probability * roll_probability
        else:
            count = len(keys)
            non_attack = count - len(current_rolls)
            if non_attack:
                state_key = (next_checkpoint, keys, current_rolls, concentration)
                next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * non_attack / count
            for index, (key, roll_count) in enumerate(current_rolls):
                bonus = reforge_bonus_value(key, roll_count + 1) - reforge_bonus_value(key, roll_count)
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    rows = list(current_rolls)
                    rows[index] = (key, roll_count + 1)
                    value = round(concentration + OFFICIAL_SCORE_WEIGHTS.get(key, 0.0) * round(delta + bonus, 4), 4)
                    state_key = (next_checkpoint, keys, tuple(sorted(rows)), value)
                    next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * roll_probability / count
        for state_key, mass in next_mass.items():
            pending[state_key] = pending.get(state_key, 0.0) + mass
    total = sum(terminal.values())
    if not total or abs(total - 1.0) > 1e-9:
        raise AssertionError(f"exact attack mass does not sum to one: {total}")
    return tuple(sorted((value, probability / total) for value, probability in terminal.items()))


def exact_attack_probability(
    gear: Gear,
    threshold: float,
    cache: dict[tuple[Any, ...], float] | None = None,
    attack_valid_keys: Any = ATTACK_KEYS,
    context_key: Any = None,
) -> float:
    valid_keys = _normalize_attack_keys(attack_valid_keys)
    cache = cache if cache is not None else {}
    key = (_state_signature(gear), round(float(threshold), 6), valid_keys, context_key)
    if key not in cache:
        cache[key] = _exact_attack_probability_pruned(gear, threshold, valid_keys)
    return float(cache[key])


def _baseline_action(state: Gear) -> str:
    if state.enhance in (0, 3):
        return _formal_action(state, GEAR_SOURCE)
    if state.rank == "Heroic":
        return _heroic_base_action(state, "normal_85")
    return "continue" if formal_followup_action(state, "normal_85") else "stop"


def _outcome(
    path: dict[int, Gear],
    candidate: AttackCandidate | None,
    probability_cache: dict[tuple[Any, ...], float],
) -> tuple[dict[str, Any], dict[str, Any]]:
    start = min(path)
    current = start
    actions: dict[int, str] = {}
    rescues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    while current < 15:
        state = path[current]
        baseline = _baseline_action(state)
        action = baseline
        if candidate and current in RESCUE_NODES and baseline == "stop":
            context = attack_compatibility(state)
            probability = 0.0
            if context["compatible"]:
                probability = exact_attack_probability(
                    state,
                    candidate.threshold,
                    probability_cache,
                    context["attack_valid_keys"],
                    context_key=(candidate.key, tuple(context["cache_key"])),
                )
            rescued = bool(context["compatible"] and probability >= candidate.probability_floor and probability > 0.0)
            checks.append({
                "checkpoint": current,
                "probability": probability,
                "compatible": context,
                "rescued": rescued,
                "candidate": candidate.key,
            })
            if rescued:
                action = "continue"
                rescues.append({"checkpoint": current, "probability": probability, "context": context})
        actions[current] = action
        if action == "stop":
            break
        current = next(point for point in CHECKPOINTS if point > current)
    costs = summarize_incremental_cost(path[start].slot, path[start].rank, start, current)
    return (
        {
            "start_checkpoint": start,
            "stop_checkpoint": current,
            "actions": actions,
            "reached_checkpoints": [point for point in CHECKPOINTS if start <= point <= current],
            "net_stamina": costs["net_stamina"],
            "net_gold": costs["net_gold"],
            "costs": costs,
        },
        {
            "rescues": rescues,
            "probability_checks": checks,
            "first_rescue_node": rescues[0]["checkpoint"] if rescues else None,
            # The candidate only upgrades stop -> continue, so this is a
            # deterministic proof that it creates no new stop action.
            "candidate_induced_stops": 0.0,
        },
    )


def _terminal_attack_hit(path: dict[int, Gear], outcome: dict[str, Any], threshold: float) -> bool:
    if int(outcome["stop_checkpoint"]) != 15:
        return False
    context = attack_compatibility(path[15])
    return bool(
        context["compatible"]
        and _attack_concentration(reforge_gear(path[15]), context["attack_valid_keys"]) >= threshold
    )


def _empty_stats() -> dict[str, Any]:
    return {
        "paths": 0.0,
        "target_high": 0.0,
        "incremental_target_high": 0.0,
        "probability_queries": 0.0,
        "probability_nonzero": 0.0,
        "probability_between_zero_ten": 0.0,
        "probability_unique_states": 0.0,
        "candidate_induced_stops": 0.0,
        "rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES},
        "first_rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES},
        "by_rank": {"Epic": 0.0, "Heroic": 0.0},
        "by_set": {},
        "by_slot": {},
        "by_category": {},
    }


def _add_flow(target: dict[str, float], source: dict[str, float], factor: float) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _add_stats(
    stats: dict[str, Any],
    gear: Gear,
    outcome: dict[str, Any],
    info: dict[str, Any],
    baseline_high: bool,
    final_high: bool,
    factor: float,
) -> None:
    stats["paths"] += factor
    stats["candidate_induced_stops"] += factor * float(info["candidate_induced_stops"])
    for row in info["probability_checks"]:
        stats["probability_queries"] += factor
        probability = float(row["probability"])
        if probability > 0:
            stats["probability_nonzero"] += factor
        if 0.0 < probability < 0.10:
            stats["probability_between_zero_ten"] += factor
        category = str(row["compatible"].get("category") or "unknown")
        bucket = stats["by_category"].setdefault(
            category,
            {"natural_quality": 0.0, "baseline_stop_quality": 0.0, "filtered": 0.0, "rescue": 0.0},
        )
        bucket["natural_quality"] += factor
        bucket["baseline_stop_quality"] += factor
        if not row["compatible"]["compatible"]:
            bucket["filtered"] += factor
        if row["rescued"]:
            bucket["rescue"] += factor
    for row in info["rescues"]:
        stats["rescue_nodes"][str(row["checkpoint"])] += factor
    if info["first_rescue_node"] is not None:
        stats["first_rescue_nodes"][str(info["first_rescue_node"])] += factor
    if outcome["stop_checkpoint"] == 15:
        stats["target_high"] += factor * float(final_high)
        stats["incremental_target_high"] += factor * float(final_high - baseline_high)
    rescued = float(bool(info["rescues"]))
    stats["by_rank"][gear.rank] += factor * rescued
    stats["by_set"][gear.set] = stats["by_set"].get(gear.set, 0.0) + factor * rescued
    stats["by_slot"][gear.slot] = stats["by_slot"].get(gear.slot, 0.0) + factor * rescued


def _candidate_fingerprint(rows: tuple[AttackCandidate, ...]) -> list[dict[str, Any]]:
    return [
        {"key": row.key, "quantile": row.quantile, "threshold": row.threshold, "mode": row.mode, "probability_floor": row.probability_floor}
        for row in rows
    ]


def _gear_shard(
    gear: Gear,
    rank: str,
    seed: int,
    gear_index: int,
    runs: int,
    candidate_rows: tuple[AttackCandidate, ...],
    input_hash: str,
) -> dict[str, Any]:
    keys = ("current_formal",) + tuple(row.key for row in candidate_rows)
    flows = {key: _empty_flow() for key in keys}
    stats = {key: _empty_stats() for key in keys}
    probability_cache: dict[tuple[Any, ...], float] = {}
    branches: list[tuple[Gear, float]] = [(gear, 1.0)]
    if rank == "Epic":
        branches = [(branch.gear, float(branch.probability)) for branch in enumerate_normal_epic_plus3(gear)]
    for branch_index, (start_state, branch_probability) in enumerate(branches):
        for path_index in range(runs):
            path = health_v4._official_path(start_state, seed + gear_index * 100003 + branch_index * 1009 + path_index * 7919)
            if rank == "Epic":
                path = {0: gear, **path}
            factor = branch_probability / runs
            baseline, _baseline_info = _outcome(path, None, probability_cache)
            _add_flow(flows["current_formal"], health_v4._flow(start_state if rank == "Heroic" else gear, path, baseline), factor)
            stats["current_formal"]["paths"] += factor
            for candidate in candidate_rows:
                outcome, info = _outcome(path, candidate, probability_cache)
                _add_flow(flows[candidate.key], health_v4._flow(start_state if rank == "Heroic" else gear, path, outcome), factor)
                baseline_high = _terminal_attack_hit(path, baseline, candidate.threshold)
                final_high = _terminal_attack_hit(path, outcome, candidate.threshold)
                _add_stats(stats[candidate.key], gear, outcome, info, baseline_high, final_high, factor)
    for candidate in candidate_rows:
        stats[candidate.key]["probability_unique_states"] = float(len(probability_cache))
    return {
        "status": "complete",
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "rank": rank,
        "seed": seed,
        "gear_index": gear_index,
        "input_hash": input_hash,
        "estimator_hash": ESTIMATOR_HASH,
        "flows": flows,
        "stats": stats,
        "paths": 1.0,
    }


def _shard_path(resume: Path, rank: str, seed: int, gear_index: int) -> Path:
    return resume / "attack_v1" / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}.json"


def _gear_hash(
    gear: Gear,
    rank: str,
    seed: int,
    runs: int,
    candidate_rows: tuple[AttackCandidate, ...],
    external_sha256: str,
) -> str:
    return _hash(
        {
            "study": STUDY,
            "schema_version": SCHEMA_VERSION,
            "estimator_hash": ESTIMATOR_HASH,
            "v4_dependency_hash": _file_hash(ROOT / "tools" / "research_epic_concentration_rescue_exact.py"),
            "gear": gear.to_dict(),
            "rank": rank,
            "seed": seed,
            "runs": runs,
            "candidates": _candidate_fingerprint(candidate_rows),
            "external_sha256": external_sha256,
        }
    )


def _valid_shard(path: Path, expected_hash: str, rank: str, seed: int, gear_index: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        payload.get("status") == "complete"
        and payload.get("study") == STUDY
        and payload.get("schema_version") == SCHEMA_VERSION
        and payload.get("estimator_hash") == ESTIMATOR_HASH
        and payload.get("rank") == rank
        and int(payload.get("seed", -1)) == seed
        and int(payload.get("gear_index", -1)) == gear_index
        and payload.get("input_hash") == expected_hash
    )


def _worker(job: dict[str, Any]) -> str:
    gear = Gear.from_dict(job["gear"])
    rows = tuple(AttackCandidate(**row) for row in job["candidates"])
    payload = _gear_shard(
        gear,
        str(job["rank"]),
        int(job["seed"]),
        int(job["gear_index"]),
        int(job["runs"]),
        rows,
        str(job["input_hash"]),
    )
    _atomic_json(Path(job["path"]), payload)
    return str(job["path"])


def _sum_shards(
    resume: Path,
    rank: str,
    seed: int,
    gears: list[Gear],
    runs: int,
    candidate_rows: tuple[AttackCandidate, ...],
    external_sha256: str,
) -> dict[str, Any]:
    keys = ("current_formal",) + tuple(row.key for row in candidate_rows)
    total = {"paths": 0.0, "flows": {key: _empty_flow() for key in keys}, "stats": {key: _empty_stats() for key in keys}}
    scalar_fields = (
        "paths",
        "target_high",
        "incremental_target_high",
        "probability_queries",
        "probability_nonzero",
        "probability_between_zero_ten",
        "probability_unique_states",
        "candidate_induced_stops",
    )
    for index, gear in enumerate(gears):
        path = _shard_path(resume, rank, seed, index)
        expected = _gear_hash(gear, rank, seed, runs, candidate_rows, external_sha256)
        if not _valid_shard(path, expected, rank, seed, index):
            raise RuntimeError(f"missing or invalid attack shard: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        total["paths"] += float(payload["paths"])
        for key in keys:
            for field in FLOW_WITH_METRICS:
                total["flows"][key][field] += float(payload["flows"][key][field])
            for field in scalar_fields:
                total["stats"][key][field] += float(payload["stats"][key][field])
            for node in RESCUE_NODES:
                total["stats"][key]["rescue_nodes"][str(node)] += float(payload["stats"][key]["rescue_nodes"][str(node)])
                total["stats"][key]["first_rescue_nodes"][str(node)] += float(payload["stats"][key]["first_rescue_nodes"][str(node)])
            for field in ("by_rank", "by_set", "by_slot"):
                for name, value in payload["stats"][key][field].items():
                    total["stats"][key][field][name] = total["stats"][key][field].get(name, 0.0) + float(value)
            for category, row in payload["stats"][key]["by_category"].items():
                bucket = total["stats"][key]["by_category"].setdefault(
                    category,
                    {"natural_quality": 0.0, "baseline_stop_quality": 0.0, "filtered": 0.0, "rescue": 0.0},
                )
                for field in bucket:
                    bucket[field] += float(row[field])
    return total


def _ci(values: list[float], nonnegative: bool = False) -> dict[str, Any]:
    center = mean(values) if values else 0.0
    half = _t95(len(values)) * stdev(values) / sqrt(len(values)) if len(values) > 1 else 0.0
    lower = max(0.0, center - half) if nonnegative else center - half
    return {"mean": center, "interval95": [lower, center + half], "seed_stddev": stdev(values) if len(values) > 1 else 0.0}


def _merge_seed(
    epic: dict[str, Any],
    heroic: dict[str, Any],
    candidate_rows: tuple[AttackCandidate, ...],
    yield_multiplier: float,
) -> dict[str, Any]:
    keys = ("current_formal",) + tuple(row.key for row in candidate_rows)
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    heroic_yield = float(batch["expected_output_by_rank"]["Heroic"]) * yield_multiplier
    merged: dict[str, Any] = {}
    for key in keys:
        flow = {
            field: epic["flows"][key][field] / epic["paths"] + heroic_yield * heroic["flows"][key][field] / heroic["paths"]
            for field in FLOW_WITH_METRICS
        }
        pool = explicit_batch_resource_pool(
            source_gold=float(batch["expected_source_gold_per_batch"]),
            source_lower_stones=float(batch["expected_lower_stone_units"]),
            powder_base_exp=flow["powder_units"] * 100.0,
            lower_stone_units=flow["lower_stone_units"],
            material_gold=flow["material_gold"],
            conversion_gold=flow["conversion_gold"],
            sell_gold=flow["sell_gold"],
            sell_exp=flow["sell_exp_adjusted"],
            material_scarcity_exp=flow["material_exp_adjusted"],
            lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
        )
        total_stamina = float(pool["total_stamina"])
        cycles = 100000.0 / total_stamina
        e = epic["stats"][key]
        h = heroic["stats"][key]
        stats = {
            "target_high_per_batch": e["target_high"] / e["paths"] + heroic_yield * h["target_high"] / h["paths"],
            "incremental_target_high_per_batch": e["incremental_target_high"] / e["paths"] + heroic_yield * h["incremental_target_high"] / h["paths"],
            "probability_queries": e["probability_queries"] / e["paths"] + heroic_yield * h["probability_queries"] / h["paths"],
            "probability_nonzero": e["probability_nonzero"] / e["paths"] + heroic_yield * h["probability_nonzero"] / h["paths"],
            "probability_between_zero_ten": e["probability_between_zero_ten"] / e["paths"] + heroic_yield * h["probability_between_zero_ten"] / h["paths"],
            "probability_unique_states": e["probability_unique_states"] / e["paths"] + heroic_yield * h["probability_unique_states"] / h["paths"],
            "candidate_induced_stops": e["candidate_induced_stops"] / e["paths"] + heroic_yield * h["candidate_induced_stops"] / h["paths"],
            "rescue_nodes_per_batch": {str(node): e["rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES},
            "first_rescue_nodes_per_batch": {str(node): e["first_rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["first_rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES},
        }
        stats["incremental_target_high_per_100k"] = stats["incremental_target_high_per_batch"] * cycles
        stats["by_category"] = {}
        for category in sorted(set(e["by_category"]) | set(h["by_category"])):
            er = e["by_category"].get(category, {})
            hr = h["by_category"].get(category, {})
            stats["by_category"][category] = {
                field: er.get(field, 0.0) / e["paths"] + heroic_yield * hr.get(field, 0.0) / h["paths"]
                for field in ("natural_quality", "baseline_stop_quality", "filtered", "rescue")
            }
        merged[key] = {
            "flow": flow,
            "resource_pool": pool,
            "formal_baili_per_100": 100.0 * flow["value_sum"] / total_stamina,
            "per_100k": {field: cycles * flow[field] for field in FLOW_WITH_METRICS},
            "rift_stamina_per_100k": cycles * 85.0,
            "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]),
            "cycles_per_100k": cycles,
            "stamina_per_baili": total_stamina / flow["value_sum"] if flow["value_sum"] else None,
            "stats": stats,
        }
    return merged


def _summarize(per_seed: dict[str, Any], seeds: tuple[int, ...], candidate_rows: tuple[AttackCandidate, ...]) -> dict[str, Any]:
    keys = ("current_formal",) + tuple(row.key for row in candidate_rows)
    result: dict[str, Any] = {}
    for key in keys:
        rows = [per_seed[str(seed)][key] for seed in seeds]
        baseline = [per_seed[str(seed)]["current_formal"] for seed in seeds]
        stats = {
            field: _ci([row["stats"][field] for row in rows], nonnegative=field != "incremental_target_high_per_batch")
            for field in (
                "target_high_per_batch",
                "incremental_target_high_per_batch",
                "incremental_target_high_per_100k",
                "probability_queries",
                "probability_nonzero",
                "probability_between_zero_ten",
                "probability_unique_states",
                "candidate_induced_stops",
            )
        }
        stats["by_category"] = {
            category: {
                field: _ci([row["stats"]["by_category"].get(category, {}).get(field, 0.0) for row in rows], nonnegative=True)
                for field in ("natural_quality", "baseline_stop_quality", "filtered", "rescue")
            }
            for category in sorted({category for row in rows for category in row["stats"]["by_category"]})
        }
        result[key] = {
            "formal_baili_per_100": _ci([row["formal_baili_per_100"] for row in rows]),
            "paired_formal_delta_per_100": _ci([row["formal_baili_per_100"] - base["formal_baili_per_100"] for row, base in zip(rows, baseline)]),
            "paired_formal_delta_per_100k": _ci([row["per_100k"]["value_sum"] - base["per_100k"]["value_sum"] for row, base in zip(rows, baseline)]),
            "stamina_per_baili": _ci([row["stamina_per_baili"] for row in rows if row["stamina_per_baili"] is not None]),
            "per_100k": {field: _ci([row["per_100k"][field] for row in rows], nonnegative=True) for field in FLOW_WITH_METRICS},
            "rift_stamina_per_100k": _ci([row["rift_stamina_per_100k"] for row in rows], nonnegative=True),
            "saint_stamina_per_100k": _ci([row["saint_stamina_per_100k"] for row in rows], nonnegative=True),
            "cycles_per_100k": _ci([row["cycles_per_100k"] for row in rows], nonnegative=True),
            "stats": stats,
            "rescue_nodes_per_batch": {str(node): _ci([row["stats"]["rescue_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES},
            "first_rescue_nodes_per_batch": {str(node): _ci([row["stats"]["first_rescue_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES},
        }
    return result


def _threshold_metadata(external: Path) -> dict[str, Any]:
    inventory = inventory_thresholds(external)
    raw = inventory["quantiles"]["attack"]
    frozen = {}
    for label, quantile, threshold in FROZEN_THRESHOLDS:
        observed = float(raw[str(quantile)])
        if abs(observed - threshold) > 0.01:
            raise RuntimeError(f"frozen attack threshold drifted for {label}: observed={observed}, expected={threshold}")
        frozen[label] = {"quantile": quantile, "threshold": threshold, "raw_inventory_quantile": observed}
    return {"inventory": inventory, "frozen": frozen}


def run(
    *,
    records: Path = DEFAULT_RECORDS,
    source: Path = DEFAULT_SOURCE,
    external: Path = DEFAULT_EXTERNAL,
    resume: Path = DEFAULT_RESUME,
    seeds: tuple[int, ...] = SEEDS,
    runs: int = 10,
    workers: int = 1,
    max_shards: int | None = None,
    epic_limit: int | None = None,
    heroic_limit: int | None = None,
) -> dict[str, Any]:
    threshold_metadata = _threshold_metadata(external)
    candidate_rows = candidates()
    epic = [Gear.from_dict(row["gear"]) for row in load_real_plus0(records, "development")]
    heroic = _source_rank_gears(json.loads(source.read_text(encoding="utf-8")), "Heroic")
    if epic_limit is not None:
        epic = epic[: max(0, epic_limit)]
    if heroic_limit is not None:
        heroic = heroic[: max(0, heroic_limit)]
    external_sha256 = str(threshold_metadata["inventory"]["sha256"])
    jobs: list[dict[str, Any]] = []
    reused = 0
    for seed in seeds:
        for rank, gears in (("Epic", epic), ("Heroic", heroic)):
            for index, gear in enumerate(gears):
                path = _shard_path(resume, rank, seed, index)
                input_hash = _gear_hash(gear, rank, seed, runs, candidate_rows, external_sha256)
                if _valid_shard(path, input_hash, rank, seed, index):
                    reused += 1
                    continue
                jobs.append(
                    {
                        "gear": gear.to_dict(),
                        "rank": rank,
                        "seed": seed,
                        "gear_index": index,
                        "runs": runs,
                        "candidates": [
                            {"label": row.label, "quantile": row.quantile, "threshold": row.threshold, "mode": row.mode}
                            for row in candidate_rows
                        ],
                        "input_hash": input_hash,
                        "path": str(path),
                    }
                )
    scheduled = len(jobs)
    if max_shards is not None:
        jobs = jobs[: max(0, max_shards)]
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_worker, jobs))
    else:
        for job in jobs:
            _worker(job)
    completed = reused + len(jobs)
    expected = len(seeds) * (len(epic) + len(heroic))
    data: dict[str, Any] = {
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "scope": "offline_only_no_holdout_no_production_change",
        "baseline": "baili-formal-dp-v1-epic-balanced",
        "data": {
            "records": str(records),
            "source": str(source),
            "external": str(external),
            "epic_development_count": len(epic),
            "heroic_source_count": len(heroic),
            "holdout_read": False,
        },
        "thresholds": threshold_metadata,
        "candidates": _candidate_fingerprint(candidate_rows),
        "compatibility": {
            "allowed_categories": sorted(ATTACK_ALLOWED_CATEGORIES),
            "fail_closed_categories": ["抗坦", "纯肉", "命坦", "双效", "一速", "unknown", "半肉(血防)"],
            "binds_selected_candidate_snapshot": True,
            "binds_category_rules": True,
            "binds_source_row": True,
            "binds_set_group": True,
            "binds_valid_group": True,
            "binds_attack_valid_keys": True,
        },
        "hashes": {
            "estimator": ESTIMATOR_HASH,
            "v4_dependency": _file_hash(ROOT / "tools" / "research_epic_concentration_rescue_exact.py"),
            "input_records": _file_hash(records),
            "input_source": _file_hash(source),
            "external_inventory": external_sha256,
            "strategy": _hash({
                "enhance_policy": _file_hash(ROOT / "src" / "e7_enhance" / "enhance_policy.py"),
                "strategy_defaults": _file_hash(ROOT / "src" / "e7_enhance" / "strategy_defaults.py"),
            }),
            "official_rolls": _hash({
                "plus3": _file_hash(ROOT / "tools" / "epic_plus3_exact_branches.py"),
                "distributions": _file_hash(ROOT / "tools" / "research_reforged_inventory_set_weights.py"),
            }),
            "resource_model": _file_hash(ROOT / "src" / "e7_enhance" / "resource_model.py"),
            "compatibility_contract": _hash({
                "allowed": sorted(ATTACK_ALLOWED_CATEGORIES),
                "category_rules": CATEGORY_RULES,
                "valid_stats": {key: sorted(VALID_STATS.get(key, [])) for key in ("output", "critless", "bruiser", "bruiserFlat")},
            }),
        },
        "runs": {
            "seeds": list(seeds),
            "paths_per_gear": runs,
            "official_probability_method": "exact_state_mass_dp_bound_to_selected_rule_attack_keys",
            "terminal_value_method": "common_official_roll_main_paths",
            "p_gte_10pct_candidates": [row.key for row in candidate_rows if row.mode == "balanced"],
            "p_gt_0_reference_candidates": [row.key for row in candidate_rows if row.mode == "reachable_reference"],
            "epic_limit": epic_limit,
            "heroic_limit": heroic_limit,
        },
        "resume": {
            "path": str(resume),
            "schema_version": SCHEMA_VERSION,
            "scheduled_shards": scheduled,
            "completed_shards": completed,
            "expected_shards": expected,
            "reused_shards": reused,
        },
        "precision": {
            "official_discrete_rolls": True,
            "exact_probability": True,
            "heroic_plus12_adds_fourth_substat_only": True,
            "reforge_once": True,
            "invalid_attack_keys_consume_hit_slots": True,
            "candidate_only_changes_stop_to_continue": True,
            "v2_v3_v4_health_resume_reused": False,
        },
    }
    if completed < expected:
        data["release_gate"] = {"status": "incomplete_shards", "reasons": ["all new attack-study shards must complete before aggregation"]}
        return data
    scenarios: dict[str, Any] = {}
    for scenario, multiplier in YIELD_VARIATIONS.items():
        per_seed = {}
        for seed in seeds:
            ep = _sum_shards(resume, "Epic", seed, epic, runs, candidate_rows, external_sha256)
            he = _sum_shards(resume, "Heroic", seed, heroic, runs, candidate_rows, external_sha256)
            per_seed[str(seed)] = _merge_seed(ep, he, candidate_rows, multiplier)
        scenarios[scenario] = {"heroic_yield_multiplier": multiplier, "per_seed": per_seed, "summary": _summarize(per_seed, seeds, candidate_rows)}
    data["scenarios"] = scenarios
    data["summary"] = scenarios["baseline"]["summary"]
    balanced = [row for row in candidate_rows if row.mode == "balanced"]
    gates: dict[str, Any] = {}
    for candidate in balanced:
        intervals = {
            scenario: scenarios[scenario]["summary"][candidate.key]["paired_formal_delta_per_100"]["interval95"]
            for scenario in YIELD_VARIATIONS
        }
        no_new_stops = all(
            scenarios[scenario]["summary"][candidate.key]["stats"]["candidate_induced_stops"]["interval95"][1] == 0.0
            for scenario in YIELD_VARIATIONS
        )
        gates[candidate.key] = {
            "intervals": intervals,
            "no_candidate_induced_stops": no_new_stops,
            "offline_eligible": no_new_stops and all(interval[0] > 0.0 for interval in intervals.values()),
        }
    eligible = [key for key, row in gates.items() if row["offline_eligible"]]
    base_intervals = [row["intervals"]["baseline"] for row in gates.values()]
    if eligible:
        status = "attack_balanced_candidates_positive_requires_independent_validation"
    elif base_intervals and all(interval[1] < 0.0 for interval in base_intervals):
        status = "all_attack_balanced_candidates_offline_rejected"
    else:
        status = "attack_balanced_candidates_effect_unresolved"
    data["release_gate"] = {
        "status": status,
        "balanced_candidates": gates,
        "offline_eligible_candidates": eligible,
        "formal_strategy_change": False,
        "holdout_read": False,
        "new_holdout_created": False,
    }
    return data


def _fmt(metric: dict[str, Any], digits: int = 4) -> str:
    lower, upper = metric["interval95"]
    return f"{metric['mean']:.{digits}f} [{lower:.{digits}f}, {upper:.{digits}f}]"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# 超高攻击集中属性基础策略研究",
        "",
        "本报告是独立离线研究：正式 `baili-formal-dp-v1-epic-balanced` 保持不变。攻击候选只在 `normal_85`、非鞋、非速度的 `+6/+9/+12` 基线停止节点把动作从停止改为继续；没有创建 Holdout，也没有修改自动建议。",
        "",
        f"- 状态：`{data['release_gate']['status']}`。",
        f"- 新 schema：`{data['schema_version']}`；生命 v2/v3/v4 分片、resume 和结论没有复用。",
        f"- 分片：`{data['resume']['completed_shards']}/{data['resume']['expected_shards']}`；调度 `{data['resume']['scheduled_shards']}`。",
        "",
        "## 规则与概率口径",
        "",
        "- 攻击集中 GS 只计算 `atkPct`、`atkFlat` 的官方 GS 权重；固定攻击按 `3.46/39` 换算，绝不和攻击百分比裸值直接相加。",
        "- 每个节点读取该节点的 selected candidate，并绑定 `CATEGORY_RULES`、sourceRow、setGroup、validGroup 与有效攻击词条。",
        "- 仅 `输出`、`输出(必爆)`、`半肉(通用)`、`半肉(白字)`可参与；`半肉(血防)`不含正式认可的攻击词条，因此和纯坦、双效、一速、unknown 一样拒绝。",
        "- balanced 使用 `P(终局一次重铸后攻击集中 GS 达到对应阈值) >= 10%`；`P>0` 行只是敏感性参考，不能发布。",
        "- Heroic `+12` 仅补第四副属性；无效攻击词条仍占后续命中槽位；`+15` 不再跳副属性；重铸只计一次。",
        "",
    ]
    frozen = data["thresholds"]["frozen"]
    lines.extend(["## 阈值", "", "| 档位 | 冻结攻击集中 GS 阈值 | 库存原始分位数 |", "|---|---:|---:|"])
    for label, _quantile, _threshold in FROZEN_THRESHOLDS:
        row = frozen[label]
        lines.append(f"| {label} | {row['threshold']:.2f} | {row['raw_inventory_quantile']:.4f} |")
    if "summary" not in data:
        lines.extend(["", "## 当前进度", "", "分片尚未齐全。此文件只记录已完成的原子分片，不汇总或推断正式候选优劣。", ""])
        return "\n".join(lines)
    summary = data["summary"]
    base = summary["current_formal"]
    lines.extend([
        "",
        "## 每 100,000 总体力（Heroic 基线产出）",
        "",
        "| 方案 | 正式百里分 | 体力/百里分 | 新增攻击集中件 | 每件体力 | 原生75+ | 转换75+ | 22速 | 裂缝体力 | 圣女体力 | 循环 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    keys = ("current_formal",) + tuple(row["key"] for row in data["candidates"])
    for key in keys:
        row = summary[key]
        added = row["stats"]["incremental_target_high_per_100k"] if key != "current_formal" else {"mean": 0.0, "interval95": [0.0, 0.0]}
        cost = 100000.0 / added["mean"] if added["mean"] > 0 else None
        lines.append(
            f"| {key} | {_fmt(row['per_100k']['value_sum'])} | {_fmt(row['stamina_per_baili'], 1)} | {_fmt(added, 4)} | {'-' if cost is None else f'{cost:.1f}'} | {_fmt(row['per_100k']['native_heirloom'], 3)} | {_fmt(row['per_100k']['converted_heirloom'], 3)} | {_fmt(row['per_100k']['speed22'], 3)} | {_fmt(row['rift_stamina_per_100k'], 1)} | {_fmt(row['saint_stamina_per_100k'], 1)} | {_fmt(row['cycles_per_100k'], 2)} |"
        )
    lines.extend(["", "## Balanced 五 seed 成对结论", "", "| 候选 | 主场景差/100体力 | Heroic -20% | Heroic +20% | 新增停损 | 离线闸门 |", "|---|---:|---:|---:|---:|---|"])
    for key, gate in data["release_gate"].get("balanced_candidates", {}).items():
        base_interval = {"mean": sum(gate["intervals"]["baseline"]) / 2.0, "interval95": gate["intervals"]["baseline"]}
        minus_interval = {"mean": sum(gate["intervals"]["yield_minus_20pct"]) / 2.0, "interval95": gate["intervals"]["yield_minus_20pct"]}
        plus_interval = {"mean": sum(gate["intervals"]["yield_plus_20pct"]) / 2.0, "interval95": gate["intervals"]["yield_plus_20pct"]}
        lines.append(f"| {key} | {_fmt(base_interval, 6)} | {_fmt(minus_interval, 6)} | {_fmt(plus_interval, 6)} | {'0' if gate['no_candidate_induced_stops'] else 'nonzero'} | {'通过，可另建验证' if gate['offline_eligible'] else '未通过'} |")
    lines.extend([
        "",
        "## 结论边界",
        "",
        f"- 当前状态：`{data['release_gate']['status']}`。",
        "- 即便某一 balanced 候选通过离线闸门，也只能另建独立真实 Holdout，不能直接发布或写入正式策略。",
        "- P>0 参考候选不参与发布资格判定。OCR/自动点击、真实强化和现有 Holdout 均未读取或修改。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exact attack-concentration offline study")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--external", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-shards", type=int)
    parser.add_argument("--epic-limit", type=int, help="offline smoke only; defaults to the full frozen Epic cohort")
    parser.add_argument("--heroic-limit", type=int, help="offline smoke only; defaults to the full frozen Heroic cohort")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    seeds = tuple(int(value.strip()) for value in args.seeds.split(",") if value.strip())
    data = run(
        records=args.records,
        source=args.source,
        external=args.external,
        resume=args.resume,
        seeds=seeds,
        runs=max(1, args.runs),
        workers=max(1, args.workers),
        max_shards=args.max_shards,
        epic_limit=args.epic_limit,
        heroic_limit=args.heroic_limit,
    )
    _atomic_json(args.json_output, data)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(markdown(data) + "\n", encoding="utf-8")
    print(json.dumps({"status": data["release_gate"]["status"], **data["resume"]}, ensure_ascii=False))
    return 0 if data["resume"]["completed_shards"] == data["resume"]["expected_shards"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
