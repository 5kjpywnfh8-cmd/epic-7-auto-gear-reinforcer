"""High-resolution offline study for the health P97.5 rescue candidate.

This module is deliberately separate from the released policy and from the
old p4 study.  It keeps the frozen 157 Epic / 80 Heroic cohorts and five
seeds, uses ten common official-roll main paths per gear, and computes the
probability of a health-concentration target with an exact state DP.  The
terminal value metrics use the same paired main paths for baseline and rescue.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from hashlib import sha256
import json
import os
from pathlib import Path
from statistics import mean, stdev
from math import sqrt
import random
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_simulator import (
    STAT_POOL,
    STAT_TYPE_BY_KEY,
    reforge_bonus_value,
    reforge_gear,
    slot_forbidden_substats,
)
from src.e7_enhance.models import Gear, RollHit, Stat, round1
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools import research_reforged_inventory_set_weights as official
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow, _flow
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    _heroic_base_action,
    _source_rank_gears,
    formal_followup_action,
    summarize_incremental_cost,
)
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_epic_concentration_rescue import (
    EXTERNAL_SOURCE,
    _compatible,
    _concentration_value,
    inventory_thresholds,
)
from tools.research_epic_exact_plus3 import _formal_action, load_real_plus0
from tools.research_riftslash_saint_pool import _t95, explicit_batch_resource_pool
from src.e7_enhance.rules import CATEGORY_RULES, OFFICIAL_SCORE_WEIGHTS
from src.e7_enhance.rules import VALID_STATS


STUDY = "epic_concentration_rescue_v4_bound_health_20260720"
SCHEMA_VERSION = 4
SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
CHECKPOINTS = (0, 3, 6, 9, 12, 15)
RESCUE_NODES = (6, 9, 12)
HEALTH_THRESHOLD_QUANTILE = 0.975
DEFAULT_RECORDS = ROOT / "manual_acceptance" / "real_sample_records.json"
DEFAULT_SOURCE = ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json"
DEFAULT_EXTERNAL = EXTERNAL_SOURCE
DEFAULT_RESUME = ROOT / "reports" / "epic_concentration_rescue_v4_bound_health_resume_20260720"
DEFAULT_JSON = ROOT / "reports" / "epic_concentration_rescue_v4_bound_health_20260720.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_concentration_rescue_v4_bound_health_20260720.md"
CANDIDATE_KEY = "health_p975_balanced"
HEALTH_ALLOWED_CATEGORIES = frozenset({"抗坦", "纯肉", "命坦", "半肉(血防)", "半肉(通用)", "半肉(白字)"})
DEFAULT_HEALTH_KEYS = frozenset({"hpPct", "hpFlat"})
ATTACK_ALLOWED_CATEGORIES = frozenset({"输出", "输出(必爆)", "半肉(血防)", "半肉(通用)", "半肉(白字)"})
_DIST_CACHE: dict[tuple[str, str], tuple[tuple[int, float], ...]] = {}
_MAX_INCREMENT_CACHE: dict[tuple[str, tuple[str, ...]], float] = {}
ESTIMATOR_HASH = sha256(Path(__file__).read_bytes()).hexdigest()


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _roll_distribution(rank: str, key: str) -> tuple[tuple[int, float], ...]:
    cache_key = (rank, key)
    if cache_key not in _DIST_CACHE:
        _DIST_CACHE[cache_key] = official._distribution(rank, key)
    return _DIST_CACHE[cache_key]


def _normalize_keys(keys: Any) -> tuple[str, ...]:
    return tuple(sorted(set(str(key) for key in (keys or ()) if str(key) in {"hpPct", "hpFlat"})))


def _max_health_increment(rank: str, health_valid_keys: tuple[str, ...]) -> float:
    cache_key = (rank, tuple(health_valid_keys))
    if cache_key not in _MAX_INCREMENT_CACHE:
        values = []
        for key in health_valid_keys:
            weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
            maximum = max(delta for delta, _probability in _roll_distribution(rank, key))
            values.extend(weight * round1(maximum + reforge_bonus_value(key, rolls + 1) - reforge_bonus_value(key, rolls)) for rolls in range(6))
        _MAX_INCREMENT_CACHE[cache_key] = max(values, default=0.0)
    return _MAX_INCREMENT_CACHE[cache_key]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _state_signature(state: Gear) -> tuple[Any, ...]:
    return (
        state.enhance, state.rank, state.level, state.slot, state.main_stat.key,
        tuple((stat.key, stat.normalized_value, stat.rolls) for stat in state.substats),
    )


@dataclass(frozen=True)
class ConcentrationContext:
    category: str
    source_row: str
    set_group: str
    valid_group: str
    valid_keys: tuple[str, ...]
    health_valid_keys: tuple[str, ...]
    compatible: bool
    reason: str

    @property
    def cache_key(self) -> tuple[Any, ...]:
        return (self.category, self.source_row, self.set_group, self.valid_group, self.valid_keys, self.health_valid_keys, self.compatible)


def _rule_for_category(category: str) -> dict[str, Any] | None:
    matches = [rule for rule in CATEGORY_RULES if str(rule.get("category")) == category]
    return matches[0] if len(matches) == 1 else None


def _context_from_snapshot(snapshot: dict[str, Any], attribute: str) -> ConcentrationContext:
    category = str(snapshot.get("category") or "unknown")
    candidate = snapshot.get("candidate") or {}
    rule = _rule_for_category(category)
    source_row = str(candidate.get("source_row") or candidate.get("sourceRow") or "")
    set_group = str(candidate.get("set_group") or candidate.get("setGroup") or "")
    valid_group = str(rule.get("validGroup") or "") if rule else ""
    valid_keys = tuple(sorted(VALID_STATS.get(valid_group, []))) if rule else ()
    health_valid_keys = _normalize_keys(valid_keys)
    allowed = HEALTH_ALLOWED_CATEGORIES if attribute == "health" else ATTACK_ALLOWED_CATEGORIES
    target_keys = {"hpPct", "hpFlat"} if attribute == "health" else {"atkPct", "atkFlat"}
    target_valid_keys = tuple(sorted(set(valid_keys) & target_keys))
    reasons = list(candidate.get("rejection_reasons") or [])
    qualified = bool(candidate.get("qualified"))
    rule_matches_candidate = bool(
        rule
        and source_row == str(rule.get("sourceRow") or "")
        and set_group == str(rule.get("setGroup") or "")
        and str(candidate.get("category") or category) == category
    )
    compatible = bool(category in allowed and qualified and not reasons and rule_matches_candidate and target_valid_keys)
    return ConcentrationContext(
        category=category,
        source_row=source_row,
        set_group=set_group,
        valid_group=valid_group,
        valid_keys=valid_keys,
        health_valid_keys=health_valid_keys if attribute == "health" else (),
        compatible=compatible,
        reason="compatible" if compatible else "selected_candidate_rule_or_attribute_not_compatible",
    )


def _context_dict(context: ConcentrationContext, attribute: str) -> dict[str, Any]:
    return {
        "compatible": context.compatible,
        "category": context.category,
        "source_row": context.source_row,
        "set_group": context.set_group,
        "valid_group": context.valid_group,
        "valid_keys": list(context.valid_keys),
        "health_valid_keys": list(context.health_valid_keys),
        "attribute": attribute,
        "reason": context.reason,
        "cache_key": list(context.cache_key),
    }


def health_compatibility_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate health concentration against the exact selected candidate rule."""
    return _context_dict(_context_from_snapshot(snapshot, "health"), "health")


def attack_compatibility_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Expose the same rule binding for the future attack study."""
    return _context_dict(_context_from_snapshot(snapshot, "attack"), "attack")


def health_compatibility(state: Gear) -> dict[str, Any]:
    """Evaluate compatibility at the current node, never at +0 only."""
    return health_compatibility_from_snapshot(phase_b.selected_candidate_snapshot(state))


def _official_path(gear: Gear, seed: int) -> dict[int, Gear]:
    """Sample one common main path with the frozen official discrete tables."""
    rng = random.Random(seed)
    current = gear
    path = {current.enhance: current}
    for checkpoint in CHECKPOINTS:
        if checkpoint <= current.enhance:
            continue
        if checkpoint == 12 and current.rank == "Heroic" and len(current.substats) < 4:
            current = replace(
                current,
                enhance=12,
                substats=current.substats + [official._new_official_substat(rng, current)],
            )
        else:
            index = rng.randrange(len(current.substats))
            hit = current.substats[index]
            delta = official._draw_roll(rng, current.rank, hit.key)
            updated = replace(hit, value=round1(hit.normalized_value + delta), rolls=hit.rolls + 1)
            substats = list(current.substats)
            substats[index] = updated
            current = replace(
                current,
                enhance=checkpoint,
                substats=substats,
                roll_history=list(current.roll_history) + [RollHit(checkpoint, updated.type, delta)],
            )
        path[checkpoint] = current
    return path


@dataclass(frozen=True)
class HealthState:
    checkpoint: int
    rank: str
    level: int
    slot: str
    main_key: str
    all_keys: tuple[str, ...]
    health_valid_keys: tuple[str, ...]
    health_entries: tuple[tuple[str, float, int], ...]


def _health_state(gear: Gear, health_valid_keys: Any = DEFAULT_HEALTH_KEYS) -> HealthState:
    valid_keys = _normalize_keys(health_valid_keys)
    return HealthState(
        checkpoint=gear.enhance,
        rank=gear.rank,
        level=gear.level,
        slot=gear.slot,
        main_key=gear.main_stat.key,
        all_keys=tuple(sorted(stat.key for stat in gear.substats)),
        health_valid_keys=valid_keys,
        health_entries=tuple(sorted(
            (stat.key, stat.normalized_value, stat.rolls)
            for stat in gear.substats if stat.key in valid_keys
        )),
    )


def _health_concentration(state: HealthState) -> float:
    total = 0.0
    for key, value, rolls in state.health_entries:
        total += OFFICIAL_SCORE_WEIGHTS.get(key, 0.0) * round1(value + reforge_bonus_value(key, rolls))
    return round(total, 4)


def _available_new_keys(state: HealthState) -> tuple[str, ...]:
    blocked = set(state.all_keys) | {state.main_key} | slot_forbidden_substats(state.slot)
    return tuple(key for key in STAT_POOL if key not in blocked)


def _add_health_entry(entries: tuple[tuple[str, float, int], ...], key: str, value: float, rolls: int) -> tuple[tuple[str, float, int], ...]:
    return tuple(sorted((*entries, (key, round1(value), rolls))))


def _replace_health_entry(entries: tuple[tuple[str, float, int], ...], index: int, value: float, rolls: int) -> tuple[tuple[str, float, int], ...]:
    rows = list(entries)
    key = rows[index][0]
    rows[index] = (key, round1(value), rolls)
    return tuple(sorted(rows))


def _next_states(state: HealthState) -> tuple[tuple[HealthState, float], ...]:
    if state.checkpoint >= 15:
        return ()
    checkpoint = next(point for point in CHECKPOINTS if point > state.checkpoint)
    if checkpoint == 12 and state.rank == "Heroic" and len(state.all_keys) < 4:
        available = _available_new_keys(state)
        if not available:
            raise ValueError("Heroic +12 has no legal fourth substat")
        rows: list[tuple[HealthState, float]] = []
        key_probability = 1.0 / len(available)
        for key in available:
            for delta, roll_probability in official._distribution(state.rank, key):
                entries = state.health_entries
                if key in state.health_valid_keys:
                    entries = _add_health_entry(entries, key, delta, 1)
                rows.append((replace(state, checkpoint=checkpoint, all_keys=tuple(sorted((*state.all_keys, key))), health_entries=entries), key_probability * roll_probability))
        return tuple(rows)

    count = len(state.all_keys)
    if count <= 0:
        return ((replace(state, checkpoint=checkpoint), 1.0),)
    rows = []
    non_health = count - len(state.health_entries)
    if non_health:
        rows.append((replace(state, checkpoint=checkpoint), non_health / count))
    for index, (key, value, rolls) in enumerate(state.health_entries):
        for delta, roll_probability in official._distribution(state.rank, key):
            rows.append((replace(state, checkpoint=checkpoint, health_entries=_replace_health_entry(state.health_entries, index, value + delta, rolls + 1)), roll_probability / count))
    return tuple(rows)


def exact_health_distribution(gear: Gear, health_valid_keys: Any = DEFAULT_HEALTH_KEYS) -> tuple[tuple[float, float], ...]:
    """Return the exact official probability mass of final health concentration."""
    # Track only concentration and health roll counts.  Reforge bonuses are
    # additive by roll count, so non-health values never need to be enumerated.
    valid_keys = _normalize_keys(health_valid_keys)
    initial = _health_state(gear, valid_keys)
    initial_concentration = _concentration_value_for_keys(reforge_gear(gear), valid_keys)
    health_rolls = tuple((key, rolls) for key, _value, rolls in initial.health_entries)
    pending: dict[tuple[int, tuple[str, ...], tuple[tuple[str, int], ...], float], float] = {
        (initial.checkpoint, initial.all_keys, health_rolls, initial_concentration): 1.0
    }
    terminal: dict[float, float] = {}
    while pending:
        (checkpoint, all_keys, current_health_rolls, concentration), probability = pending.popitem()
        if checkpoint >= 15:
            value = round(concentration, 4)
            terminal[value] = terminal.get(value, 0.0) + probability
            continue
        next_checkpoint = next(point for point in CHECKPOINTS if point > checkpoint)
        next_mass: dict[tuple[int, tuple[str, ...], tuple[tuple[str, int], ...], float], float] = {}
        if next_checkpoint == 12 and gear.rank == "Heroic" and len(all_keys) < 4:
            blocked = set(all_keys) | {gear.main_stat.key} | slot_forbidden_substats(gear.slot)
            available = tuple(key for key in STAT_POOL if key not in blocked)
            key_probability = 1.0 / len(available)
            non_health = sum(key not in set(valid_keys) for key in available)
            if non_health:
                key = tuple(sorted((*all_keys, "__non_health_fourth__")))
                # The sentinel is only used to retain the substat count; it is
                # never a legal stat and is discarded after +12.
                state_key = (next_checkpoint, key, current_health_rolls, concentration)
                next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * non_health * key_probability
            for key in valid_keys:
                if key not in available:
                    continue
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    new_key = tuple(sorted((*all_keys, key)))
                    weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
                    new_concentration = round(concentration + weight * round1(delta + reforge_bonus_value(key, 1)), 4)
                    updated_rolls = tuple(sorted((*current_health_rolls, (key, 1))))
                    state_key = (next_checkpoint, new_key, updated_rolls, new_concentration)
                    next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * key_probability * roll_probability
        else:
            count = len(all_keys)
            non_health = count - len(current_health_rolls)
            if non_health:
                state_key = (next_checkpoint, all_keys, current_health_rolls, concentration)
                next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * non_health / count
            for index, (key, rolls) in enumerate(current_health_rolls):
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
                    incremental_bonus = reforge_bonus_value(key, rolls + 1) - reforge_bonus_value(key, rolls)
                    new_concentration = round(concentration + weight * round1(delta + incremental_bonus), 4)
                    updated_rolls = list(current_health_rolls)
                    updated_rolls[index] = (key, rolls + 1)
                    state_key = (next_checkpoint, all_keys, tuple(sorted(updated_rolls)), new_concentration)
                    next_mass[state_key] = next_mass.get(state_key, 0.0) + probability * roll_probability / count
        for state_key, mass in next_mass.items():
            # The sentinel represents any non-health fourth stat.  Its key is
            # retained only to make later target probabilities use four slots.
            pending[state_key] = pending.get(state_key, 0.0) + mass
    total = sum(terminal.values())
    if not total or abs(total - 1.0) > 1e-9:
        raise AssertionError(f"exact health mass does not sum to one: {total}")
    return tuple(sorted((value, probability / total) for value, probability in terminal.items()))


def _health_upper_bound(rank: str, slot: str, main_key: str, checkpoint: int, all_keys: tuple[str, ...], health_rolls: tuple[tuple[str, int], ...], concentration: float, health_valid_keys: tuple[str, ...]) -> float:
    """A safe optimistic bound used to prune impossible tail states."""
    bound = concentration
    current = checkpoint
    keys = tuple(all_keys)
    rolls = tuple(health_rolls)
    while current < 15:
        next_checkpoint = next(point for point in CHECKPOINTS if point > current)
        if next_checkpoint == 12 and rank == "Heroic" and len(keys) < 4:
            available = tuple(key for key in STAT_POOL if key not in (set(keys) | {main_key} | slot_forbidden_substats(slot)))
            additions = []
            for key in health_valid_keys:
                if key in available:
                    weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
                    maximum = max(delta for delta, _probability in _roll_distribution(rank, key))
                    additions.append(weight * round1(maximum + reforge_bonus_value(key, 1)))
            bound += max([0.0, *additions])
            if additions:
                key = ("hpPct" if additions[0] >= additions[-1] else "hpFlat")
                keys = tuple(sorted((*keys, key)))
                rolls = tuple(sorted((*rolls, (key, 1))))
            else:
                keys = tuple(sorted((*keys, "__non_health_fourth__")))
        else:
            # Use the best legal health key and every possible prior roll
            # count.  This is deliberately loose but never underestimates a
            # future branch, which keeps pruning mathematically safe.
            bound += _max_health_increment(rank, health_valid_keys)
        current = next_checkpoint
    return bound


def _exact_health_probability_pruned(gear: Gear, threshold: float, health_valid_keys: tuple[str, ...]) -> float:
    initial = _health_state(gear, health_valid_keys)
    initial_concentration = _concentration_value_for_keys(reforge_gear(gear), health_valid_keys)
    initial_rolls = tuple((key, rolls) for key, _value, rolls in initial.health_entries)
    pending: dict[tuple[int, tuple[str, ...], tuple[tuple[str, int], ...], float], float] = {
        (initial.checkpoint, initial.all_keys, initial_rolls, initial_concentration): 1.0
    }
    success = 0.0
    while pending:
        (checkpoint, all_keys, current_health_rolls, concentration), probability = pending.popitem()
        if concentration >= threshold:
            success += probability
            continue
        if _health_upper_bound(gear.rank, gear.slot, gear.main_stat.key, checkpoint, all_keys, current_health_rolls, concentration, health_valid_keys) < threshold:
            continue
        if checkpoint >= 15:
            continue
        next_checkpoint = next(point for point in CHECKPOINTS if point > checkpoint)
        if next_checkpoint == 12 and gear.rank == "Heroic" and len(all_keys) < 4:
            blocked = set(all_keys) | {gear.main_stat.key} | slot_forbidden_substats(gear.slot)
            available = tuple(key for key in STAT_POOL if key not in blocked)
            key_probability = 1.0 / len(available)
            non_health = sum(key not in set(health_valid_keys) for key in available)
            if non_health:
                state_key = (next_checkpoint, tuple(sorted((*all_keys, "__non_health_fourth__"))), current_health_rolls, concentration)
                pending[state_key] = pending.get(state_key, 0.0) + probability * non_health * key_probability
            for key in health_valid_keys:
                if key not in available:
                    continue
                weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    new_concentration = round(concentration + weight * round1(delta + reforge_bonus_value(key, 1)), 4)
                    state_key = (next_checkpoint, tuple(sorted((*all_keys, key))), tuple(sorted((*current_health_rolls, (key, 1)))), new_concentration)
                    pending[state_key] = pending.get(state_key, 0.0) + probability * key_probability * roll_probability
        else:
            count = len(all_keys)
            non_health = count - len(current_health_rolls)
            if non_health:
                state_key = (next_checkpoint, all_keys, current_health_rolls, concentration)
                pending[state_key] = pending.get(state_key, 0.0) + probability * non_health / count
            for index, (key, roll_count) in enumerate(current_health_rolls):
                weight = OFFICIAL_SCORE_WEIGHTS.get(key, 0.0)
                bonus = reforge_bonus_value(key, roll_count + 1) - reforge_bonus_value(key, roll_count)
                for delta, roll_probability in _roll_distribution(gear.rank, key):
                    new_concentration = round(concentration + weight * round1(delta + bonus), 4)
                    updated_rolls = list(current_health_rolls)
                    updated_rolls[index] = (key, roll_count + 1)
                    state_key = (next_checkpoint, all_keys, tuple(sorted(updated_rolls)), new_concentration)
                    pending[state_key] = pending.get(state_key, 0.0) + probability * roll_probability / count
    return success


def exact_health_probability(gear: Gear, threshold: float, cache: dict[tuple[Any, ...], float] | None = None, health_valid_keys: Any = DEFAULT_HEALTH_KEYS, context_key: Any = None) -> float:
    valid_keys = _normalize_keys(health_valid_keys)
    cache = cache if cache is not None else {}
    key = (_state_signature(gear), round(float(threshold), 6), valid_keys, context_key)
    if key not in cache:
        cache[key] = _exact_health_probability_pruned(gear, threshold, valid_keys)
    return float(cache[key])


def _concentration_value_for_keys(gear: Gear, valid_keys: Any) -> float:
    keys = set(str(key) for key in (valid_keys or ()))
    return round(sum(
        stat.normalized_value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0)
        for stat in gear.substats if stat.key in keys
    ), 4)


def _baseline_action(state: Gear) -> str:
    if state.enhance in (0, 3):
        return _formal_action(state, GEAR_SOURCE)
    if state.rank == "Heroic":
        return _heroic_base_action(state, "normal_85")
    return "continue" if formal_followup_action(state, "normal_85") else "stop"


def _outcome(path: dict[int, Gear], threshold: float, probability_cache: dict[tuple[Any, ...], float], candidate: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    start = min(path)
    current = start
    actions: dict[int, str] = {}
    rescues: list[dict[str, Any]] = []
    probability_checks: list[dict[str, Any]] = []
    rescue_context: dict[str, Any] | None = None
    while current < 15:
        state = path[current]
        baseline = _baseline_action(state)
        action = baseline
        probability = 0.0
        if candidate and current in RESCUE_NODES and baseline == "stop":
            compatibility = health_compatibility(state)
            # v3 is retained only as a historical diagnostic.  v4 binds the
            # selected rule and valid keys before using its probability.
            v3_probability = exact_health_probability(state, threshold, probability_cache, DEFAULT_HEALTH_KEYS, context_key=("v3_legacy",))
            v3_rescued = v3_probability >= 0.10
            probability = 0.0
            if compatibility["compatible"]:
                probability = exact_health_probability(
                    state,
                    threshold,
                    probability_cache,
                    compatibility["health_valid_keys"],
                    context_key=tuple(compatibility["cache_key"]),
                )
            v4_rescued = compatibility["compatible"] and probability >= 0.10
            probability_checks.append({"checkpoint": current, "probability": probability, "v3_probability": v3_probability, "compatibility": compatibility, "v3_rescued": v3_rescued, "v4_rescued": v4_rescued})
            if v4_rescued:
                action = "continue"
                rescue_context = compatibility
                rescues.append({"checkpoint": current, "probability": probability, "context": compatibility})
        actions[current] = action
        if action == "stop":
            break
        current = next(point for point in CHECKPOINTS if point > current)
    costs = summarize_incremental_cost(path[start].slot, path[start].rank, start, current)
    return (
        {"start_checkpoint": start, "stop_checkpoint": current, "actions": actions, "reached_checkpoints": [point for point in CHECKPOINTS if start <= point <= current], "net_stamina": costs["net_stamina"], "net_gold": costs["net_gold"], "costs": costs},
        {"rescues": rescues, "probability_checks": probability_checks, "first_rescue_node": rescues[0]["checkpoint"] if rescues else None, "terminal_health_valid_keys": rescue_context["health_valid_keys"] if rescue_context else []},
    )


def _empty_stats() -> dict[str, Any]:
    return {"paths": 0.0, "rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "first_rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "v3_invalid_key_rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "v3_incompatible_rescue_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "v4_filtered_nodes": {str(node): 0.0 for node in RESCUE_NODES}, "target_high": 0.0, "incremental_target_high": 0.0, "probability_queries": 0.0, "probability_nonzero": 0.0, "probability_between_zero_ten": 0.0, "probability_unique_states": 0.0, "v3_invalid_key_rescue": 0.0, "v3_incompatible_rescue": 0.0, "v4_filtered": 0.0, "by_rank": {"Epic": 0.0, "Heroic": 0.0}, "by_set": {}, "by_slot": {}, "by_category": {}}


def _add_flow(target: dict[str, float], source: dict[str, float], factor: float) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _add_stats(stats: dict[str, Any], gear: Gear, candidate_outcome: dict[str, Any], info: dict[str, Any], baseline_high: bool, final_high: bool, factor: float) -> None:
    stats["paths"] += factor
    for row in info["probability_checks"]:
        stats["probability_queries"] += factor
        if row["probability"] > 0:
            stats["probability_nonzero"] += factor
        if 0.0 < row["probability"] < 0.10:
            stats["probability_between_zero_ten"] += factor
        category = str(row["compatibility"].get("category") or "unknown")
        bucket = stats["by_category"].setdefault(category, {"natural_quality": 0.0, "baseline_stop_quality": 0.0, "v3_invalid_key_rescue": 0.0, "v3_incompatible_rescue": 0.0, "v4_filtered": 0.0, "v4_rescue": 0.0})
        bucket["natural_quality"] += factor
        bucket["baseline_stop_quality"] += factor
        if not row["compatibility"]["compatible"]:
            stats["v4_filtered"] += factor
            stats["v4_filtered_nodes"][str(row["checkpoint"])] += factor
            bucket["v4_filtered"] += factor
        if row["v3_rescued"] and row["compatibility"]["compatible"] and not row["v4_rescued"]:
            stats["v3_invalid_key_rescue"] += factor
            stats["v3_invalid_key_rescue_nodes"][str(row["checkpoint"])] += factor
            bucket["v3_invalid_key_rescue"] += factor
        if row["v3_rescued"] and not row["compatibility"]["compatible"]:
            stats["v3_incompatible_rescue"] += factor
            stats["v3_incompatible_rescue_nodes"][str(row["checkpoint"])] += factor
            bucket["v3_incompatible_rescue"] += factor
        if row["v4_rescued"]:
            bucket["v4_rescue"] += factor
    for row in info["rescues"]:
        stats["rescue_nodes"][str(row["checkpoint"])] += factor
    if info["first_rescue_node"] is not None:
        stats["first_rescue_nodes"][str(info["first_rescue_node"])] += factor
    if candidate_outcome["stop_checkpoint"] == 15:
        stats["target_high"] += factor * float(final_high)
        stats["incremental_target_high"] += factor * float(final_high - baseline_high)
    stats["by_rank"][gear.rank] += factor * float(info["rescues"] != [])
    stats["by_set"][gear.set] = stats["by_set"].get(gear.set, 0.0) + factor * float(info["rescues"] != [])
    stats["by_slot"][gear.slot] = stats["by_slot"].get(gear.slot, 0.0) + factor * float(info["rescues"] != [])


def _gear_shard(gear: Gear, rank: str, seed: int, gear_index: int, runs: int, threshold: float) -> dict[str, Any]:
    flows = {"current_formal": _empty_flow(), CANDIDATE_KEY: _empty_flow()}
    stats = {"current_formal": _empty_stats(), CANDIDATE_KEY: _empty_stats()}
    probability_cache: dict[tuple[Any, ...], float] = {}
    branch_rows: list[tuple[Gear, float]] = [(gear, 1.0)]
    if rank == "Epic":
        branch_rows = [(branch.gear, float(branch.probability)) for branch in enumerate_normal_epic_plus3(gear)]
    for branch_index, (start3, branch_probability) in enumerate(branch_rows):
        paths = [_official_path(start3, seed + gear_index * 100003 + branch_index * 1009 + path_index * 7919) for path_index in range(runs)]
        for path_index, path in enumerate(paths):
            if rank == "Epic":
                path = {0: gear, **path}
            baseline, baseline_info = _outcome(path, threshold, probability_cache, False)
            candidate, candidate_info = _outcome(path, threshold, probability_cache, True)
            factor = branch_probability / runs
            _add_flow(flows["current_formal"], _flow(start3 if rank == "Heroic" else gear, path, baseline), factor)
            _add_flow(flows[CANDIDATE_KEY], _flow(start3 if rank == "Heroic" else gear, path, candidate), factor)
            terminal_keys = candidate_info["terminal_health_valid_keys"]
            baseline_high = baseline["stop_checkpoint"] == 15 and bool(terminal_keys) and _concentration_value_for_keys(reforge_gear(path[15]), terminal_keys) >= threshold
            final_high = candidate["stop_checkpoint"] == 15 and bool(terminal_keys) and _concentration_value_for_keys(reforge_gear(path[15]), terminal_keys) >= threshold
            _add_stats(stats[CANDIDATE_KEY], gear, candidate, candidate_info, baseline_high, final_high, factor)
            stats["current_formal"]["paths"] += factor
    stats[CANDIDATE_KEY]["probability_unique_states"] = float(len(probability_cache))
    return {"status": "complete", "schema_version": SCHEMA_VERSION, "study": STUDY, "rank": rank, "seed": seed, "gear_index": gear_index, "input_hash": _gear_hash(gear, rank, seed, runs, threshold), "estimator_hash": ESTIMATOR_HASH, "flows": flows, "stats": stats, "paths": 1.0}


def _shard_path(resume: Path, rank: str, seed: int, gear_index: int) -> Path:
    return resume / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}.json"


def _valid_shard(path: Path, expected_hash: str, rank: str, seed: int, gear_index: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return payload.get("status") == "complete" and payload.get("schema_version") == SCHEMA_VERSION and payload.get("study") == STUDY and payload.get("estimator_hash") == ESTIMATOR_HASH and payload.get("rank") == rank and int(payload.get("seed", -1)) == seed and int(payload.get("gear_index", -1)) == gear_index and payload.get("input_hash") == expected_hash


def _worker(job: dict[str, Any]) -> str:
    gear = Gear.from_dict(job["gear"])
    payload = _gear_shard(gear, job["rank"], int(job["seed"]), int(job["gear_index"]), int(job["runs"]), float(job["threshold"]))
    _atomic_json(Path(job["path"]), payload)
    return job["path"]


def _gear_hash(gear: Gear, rank: str, seed: int, runs: int, threshold: float) -> str:
    return _hash({"study": STUDY, "schema_version": SCHEMA_VERSION, "estimator_hash": ESTIMATOR_HASH, "gear": gear.to_dict(), "rank": rank, "seed": seed, "runs": runs, "threshold": threshold})


def _sum_shards(resume: Path, rank: str, seed: int, gears: list[Gear], runs: int, threshold: float) -> dict[str, Any]:
    total = {"paths": 0.0, "flows": {"current_formal": _empty_flow(), CANDIDATE_KEY: _empty_flow()}, "stats": {"current_formal": _empty_stats(), CANDIDATE_KEY: _empty_stats()}}
    for index, gear in enumerate(gears):
        path = _shard_path(resume, rank, seed, index)
        if not _valid_shard(path, _gear_hash(gear, rank, seed, runs, threshold), rank, seed, index):
            raise RuntimeError(f"missing or invalid shard: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        total["paths"] += float(payload["paths"])
        for key in total["flows"]:
            for field in FLOW_WITH_METRICS:
                total["flows"][key][field] += float(payload["flows"][key][field])
        for key in total["stats"]:
            for field in ("paths", "target_high", "incremental_target_high", "probability_queries", "probability_nonzero", "probability_between_zero_ten", "probability_unique_states", "v3_invalid_key_rescue", "v3_incompatible_rescue", "v4_filtered"):
                total["stats"][key][field] += float(payload["stats"][key][field])
            for node in RESCUE_NODES:
                total["stats"][key]["rescue_nodes"][str(node)] += float(payload["stats"][key]["rescue_nodes"][str(node)])
                total["stats"][key]["first_rescue_nodes"][str(node)] += float(payload["stats"][key]["first_rescue_nodes"][str(node)])
                total["stats"][key]["v3_invalid_key_rescue_nodes"][str(node)] += float(payload["stats"][key]["v3_invalid_key_rescue_nodes"][str(node)])
                total["stats"][key]["v3_incompatible_rescue_nodes"][str(node)] += float(payload["stats"][key]["v3_incompatible_rescue_nodes"][str(node)])
                total["stats"][key]["v4_filtered_nodes"][str(node)] += float(payload["stats"][key]["v4_filtered_nodes"][str(node)])
            for field in ("by_rank", "by_set", "by_slot"):
                for name, value in payload["stats"][key][field].items():
                    total["stats"][key][field][name] = total["stats"][key][field].get(name, 0.0) + float(value)
            for name, row in payload["stats"][key]["by_category"].items():
                bucket = total["stats"][key]["by_category"].setdefault(name, {"natural_quality": 0.0, "baseline_stop_quality": 0.0, "v3_invalid_key_rescue": 0.0, "v3_incompatible_rescue": 0.0, "v4_filtered": 0.0, "v4_rescue": 0.0})
                for field in bucket:
                    bucket[field] += float(row[field])
    return total


def _ci(values: list[float], nonnegative: bool = False) -> dict[str, Any]:
    center = mean(values) if values else 0.0
    half = _t95(len(values)) * stdev(values) / sqrt(len(values)) if len(values) > 1 else 0.0
    lower = center - half
    if nonnegative:
        lower = max(0.0, lower)
    return {"mean": center, "interval95": [lower, center + half], "seed_stddev": stdev(values) if len(values) > 1 else 0.0}


def _merge_seed(seed: int, epic: dict[str, Any], heroic: dict[str, Any]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    heroic_yield = float(batch["expected_output_by_rank"]["Heroic"])
    merged: dict[str, Any] = {}
    for key in ("current_formal", CANDIDATE_KEY):
        flow = {field: epic["flows"][key][field] / epic["paths"] + heroic_yield * heroic["flows"][key][field] / heroic["paths"] for field in FLOW_WITH_METRICS}
        pool = explicit_batch_resource_pool(source_gold=float(batch["expected_source_gold_per_batch"]), source_lower_stones=float(batch["expected_lower_stone_units"]), powder_base_exp=flow["powder_units"] * 100.0, lower_stone_units=flow["lower_stone_units"], material_gold=flow["material_gold"], conversion_gold=flow["conversion_gold"], sell_gold=flow["sell_gold"], sell_exp=flow["sell_exp_adjusted"], material_scarcity_exp=flow["material_exp_adjusted"], lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"])
        total = float(pool["total_stamina"])
        cycles = 100000.0 / total
        merged[key] = {"flow": flow, "resource_pool": pool, "formal_baili_per_100": 100.0 * flow["value_sum"] / total, "per_100k": {field: cycles * flow[field] for field in FLOW_WITH_METRICS}, "rift_stamina_per_100k": cycles * 85.0, "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]), "cycles_per_100k": cycles, "stamina_per_baili": total / flow["value_sum"] if flow["value_sum"] else None}
    for key in ("current_formal", CANDIDATE_KEY):
        e = epic["stats"][key]
        h = heroic["stats"][key]
        merged[key]["stats"] = {"target_high_per_batch": e["target_high"] / e["paths"] + heroic_yield * h["target_high"] / h["paths"], "incremental_target_high_per_batch": e["incremental_target_high"] / e["paths"] + heroic_yield * h["incremental_target_high"] / h["paths"], "rescue_nodes_per_batch": {str(node): e["rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}, "first_rescue_nodes_per_batch": {str(node): e["first_rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["first_rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}, "probability_queries": e["probability_queries"] / e["paths"] + heroic_yield * h["probability_queries"] / h["paths"], "probability_nonzero": e["probability_nonzero"] / e["paths"] + heroic_yield * h["probability_nonzero"] / h["paths"], "probability_between_zero_ten": e["probability_between_zero_ten"] / e["paths"] + heroic_yield * h["probability_between_zero_ten"] / h["paths"], "probability_unique_states": e["probability_unique_states"] / e["paths"] + heroic_yield * h["probability_unique_states"] / h["paths"], "by_rank": {"Epic": e["by_rank"]["Epic"] / e["paths"], "Heroic": heroic_yield * h["by_rank"]["Heroic"] / h["paths"]}, "coverage": {"set_count": len({name for name, value in {**e["by_set"], **h["by_set"]}.items() if value > 0}), "slot_count": len({name for name, value in {**e["by_slot"], **h["by_slot"]}.items() if value > 0})}}
    for key in ("current_formal", CANDIDATE_KEY):
        e = epic["stats"][key]
        h = heroic["stats"][key]
        stats = merged[key]["stats"]
        stats["incremental_target_high_per_100k"] = stats["incremental_target_high_per_batch"] * merged[key]["cycles_per_100k"]
        stats["v3_invalid_key_rescue_per_batch"] = e["v3_invalid_key_rescue"] / e["paths"] + heroic_yield * h["v3_invalid_key_rescue"] / h["paths"]
        stats["v3_incompatible_rescue_per_batch"] = e["v3_incompatible_rescue"] / e["paths"] + heroic_yield * h["v3_incompatible_rescue"] / h["paths"]
        stats["v4_filtered_per_batch"] = e["v4_filtered"] / e["paths"] + heroic_yield * h["v4_filtered"] / h["paths"]
        stats["v3_invalid_key_rescue_nodes_per_batch"] = {str(node): e["v3_invalid_key_rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["v3_invalid_key_rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}
        stats["v3_incompatible_rescue_nodes_per_batch"] = {str(node): e["v3_incompatible_rescue_nodes"][str(node)] / e["paths"] + heroic_yield * h["v3_incompatible_rescue_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}
        stats["v4_filtered_nodes_per_batch"] = {str(node): e["v4_filtered_nodes"][str(node)] / e["paths"] + heroic_yield * h["v4_filtered_nodes"][str(node)] / h["paths"] for node in RESCUE_NODES}
        categories = set(e["by_category"]) | set(h["by_category"])
        stats["by_category"] = {}
        for category in sorted(categories):
            er = e["by_category"].get(category, {})
            hr = h["by_category"].get(category, {})
            stats["by_category"][category] = {field: er.get(field, 0.0) / e["paths"] + heroic_yield * hr.get(field, 0.0) / h["paths"] for field in ("natural_quality", "baseline_stop_quality", "v3_invalid_key_rescue", "v3_incompatible_rescue", "v4_filtered", "v4_rescue")}
    return merged


def _summarize(per_seed: dict[str, Any], seeds: tuple[int, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("current_formal", CANDIDATE_KEY):
        rows = [per_seed[str(seed)][key] for seed in seeds]
        base = [per_seed[str(seed)]["current_formal"] for seed in seeds]
        result[key] = {"formal_baili_per_100": _ci([row["formal_baili_per_100"] for row in rows]), "paired_formal_delta_per_100": _ci([row["formal_baili_per_100"] - row0["formal_baili_per_100"] for row, row0 in zip(rows, base)]), "paired_formal_delta_per_100k": _ci([row["per_100k"]["value_sum"] - row0["per_100k"]["value_sum"] for row, row0 in zip(rows, base)]), "stamina_per_baili": _ci([row["stamina_per_baili"] for row in rows if row["stamina_per_baili"] is not None]), "per_100k": {field: _ci([row["per_100k"][field] for row in rows], nonnegative=True) for field in FLOW_WITH_METRICS}, "rift_stamina_per_100k": _ci([row["rift_stamina_per_100k"] for row in rows], nonnegative=True), "saint_stamina_per_100k": _ci([row["saint_stamina_per_100k"] for row in rows], nonnegative=True), "cycles_per_100k": _ci([row["cycles_per_100k"] for row in rows], nonnegative=True), "stats": {field: _ci([row["stats"][field] for row in rows], nonnegative=True) for field in ("target_high_per_batch", "incremental_target_high_per_batch", "probability_queries", "probability_nonzero", "probability_between_zero_ten", "probability_unique_states")}, "rescue_nodes_per_batch": {str(node): _ci([row["stats"]["rescue_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES}, "first_rescue_nodes_per_batch": {str(node): _ci([row["stats"]["first_rescue_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES}}
    for key in ("current_formal", CANDIDATE_KEY):
        rows = [per_seed[str(seed)][key] for seed in seeds]
        stats = result[key]["stats"]
        stats["incremental_target_high_per_100k"] = _ci([row["stats"]["incremental_target_high_per_100k"] for row in rows], nonnegative=True)
        stats["v3_invalid_key_rescue_per_batch"] = _ci([row["stats"]["v3_invalid_key_rescue_per_batch"] for row in rows], nonnegative=True)
        stats["v3_incompatible_rescue_per_batch"] = _ci([row["stats"]["v3_incompatible_rescue_per_batch"] for row in rows], nonnegative=True)
        stats["v4_filtered_per_batch"] = _ci([row["stats"]["v4_filtered_per_batch"] for row in rows], nonnegative=True)
        stats["v3_invalid_key_rescue_nodes_per_batch"] = {str(node): _ci([row["stats"]["v3_invalid_key_rescue_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES}
        stats["v3_incompatible_rescue_nodes_per_batch"] = {str(node): _ci([row["stats"]["v3_incompatible_rescue_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES}
        stats["v4_filtered_nodes_per_batch"] = {str(node): _ci([row["stats"]["v4_filtered_nodes_per_batch"][str(node)] for row in rows], nonnegative=True) for node in RESCUE_NODES}
        categories = sorted({category for row in rows for category in row["stats"]["by_category"]})
        stats["by_category"] = {category: {field: _ci([row["stats"]["by_category"].get(category, {}).get(field, 0.0) for row in rows], nonnegative=True) for field in ("natural_quality", "baseline_stop_quality", "v3_invalid_key_rescue", "v3_incompatible_rescue", "v4_filtered", "v4_rescue")} for category in categories}
    return result


def run(*, records: Path = DEFAULT_RECORDS, source: Path = DEFAULT_SOURCE, external: Path = DEFAULT_EXTERNAL, resume: Path = DEFAULT_RESUME, seeds: tuple[int, ...] = SEEDS, runs: int = 10, workers: int = 1, max_shards: int | None = None) -> dict[str, Any]:
    thresholds = inventory_thresholds(external)
    threshold = float(thresholds["quantiles"]["health"][str(HEALTH_THRESHOLD_QUANTILE)])
    epic = [Gear.from_dict(row["gear"]) for row in load_real_plus0(records, "development")]
    source_payload = json.loads(source.read_text(encoding="utf-8"))
    heroic = _source_rank_gears(source_payload, "Heroic")
    jobs: list[dict[str, Any]] = []
    reused = 0
    for seed in seeds:
        for rank, gears in (("Epic", epic), ("Heroic", heroic)):
            for index, gear in enumerate(gears):
                path = _shard_path(resume, rank, seed, index)
                expected = _gear_hash(gear, rank, seed, runs, threshold)
                if _valid_shard(path, expected, rank, seed, index):
                    reused += 1
                    continue
                jobs.append({"gear": gear.to_dict(), "rank": rank, "seed": seed, "gear_index": index, "runs": runs, "threshold": threshold, "path": str(path)})
    scheduled = len(jobs)
    if max_shards is not None:
        jobs = jobs[:max(0, max_shards)]
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_worker, jobs))
    else:
        for job in jobs:
            _worker(job)
    completed = reused + len(jobs)
    expected_count = len(seeds) * (len(epic) + len(heroic))
    data: dict[str, Any] = {"study": STUDY, "schema_version": SCHEMA_VERSION, "scope": "offline_only_no_holdout_no_production_change", "baseline": "baili-formal-dp-v1-epic-balanced", "candidate": CANDIDATE_KEY, "data": {"records": str(records), "source": str(source), "external": str(external), "epic_development_count": len(epic), "heroic_source_count": len(heroic), "holdout_read": False}, "threshold": {"attribute": "health", "quantile": HEALTH_THRESHOLD_QUANTILE, "value": threshold, "inventory": thresholds}, "compatibility": {"allowed_categories": sorted(HEALTH_ALLOWED_CATEGORIES), "rejected_categories": ["输出", "输出(必爆)", "双效", "一速", "unknown"], "uses_selected_candidate_snapshot": True, "binds_category_rules": True, "binds_source_row": True, "binds_valid_group": True, "binds_health_valid_keys": True, "v3_reused": False}, "hashes": {"estimator": ESTIMATOR_HASH, "input_records": _file_hash(records), "input_source": _file_hash(source), "external_inventory": thresholds["sha256"], "strategy": _hash({"enhance_policy": _file_hash(ROOT / "src" / "e7_enhance" / "enhance_policy.py"), "strategy_defaults": _file_hash(ROOT / "src" / "e7_enhance" / "strategy_defaults.py")}), "official_rolls": _hash({"plus3": _file_hash(ROOT / "tools" / "epic_plus3_exact_branches.py"), "distributions": _file_hash(ROOT / "tools" / "research_reforged_inventory_set_weights.py")}), "resource_model": _file_hash(ROOT / "src" / "e7_enhance" / "resource_model.py"), "compatibility_contract": _hash({"allowed_categories": sorted(HEALTH_ALLOWED_CATEGORIES), "category_rules": CATEGORY_RULES, "valid_stats": {key: sorted(VALID_STATS.get(key, [])) for key in ("tankRes", "pureTank", "hitTank", "bruiserHpDef", "bruiser", "bruiserFlat")}})}, "runs": {"seeds": list(seeds), "paths_per_gear": runs, "official_probability_method": "exact_state_mass_dp_bound_to_selected_rule_keys", "terminal_value_method": "common_official_roll_main_paths", "old_v2_reused": False, "old_v3_reused": False}, "resume": {"path": str(resume), "schema_version": SCHEMA_VERSION, "scheduled_shards": scheduled, "completed_shards": completed, "expected_shards": expected_count, "reused_shards": reused}, "precision": {"official_discrete_rolls": True, "exact_probability": True, "probability_threshold": 0.10, "heroic_plus12_adds_fourth_substat_only": True, "reforge_once": True, "unique_probability_states_are_recorded_per_gear": True, "invalid_health_keys_consume_hit_slots": True, "cache_key_includes_selected_rule_context": True}}
    if completed < expected_count:
        data["release_gate"] = {"status": "incomplete_shards", "reasons": ["all seed/rank/gear shards must complete before formal aggregation"]}
        return data
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        ep = _sum_shards(resume, "Epic", seed, epic, runs, threshold)
        he = _sum_shards(resume, "Heroic", seed, heroic, runs, threshold)
        per_seed[str(seed)] = _merge_seed(seed, ep, he)
    data["per_seed"] = per_seed
    data["summary"] = _summarize(per_seed, seeds)
    delta = data["summary"][CANDIDATE_KEY]["paired_formal_delta_per_100"]["interval95"]
    if delta[1] < 0:
        gate_status = "health_p975_balanced_offline_rejected"
    elif delta[0] > 0:
        gate_status = "health_p975_balanced_positive_requires_independent_validation"
    else:
        gate_status = "health_p975_balanced_precision_fixed_effect_unresolved"
    data["release_gate"] = {"status": gate_status, "candidate": CANDIDATE_KEY, "paired_delta_per_100_interval95": delta, "formal_strategy_change": False, "holdout_read": False, "strategy_audit_started": False}
    return data


def _fmt(metric: dict[str, Any], digits: int = 4, nonnegative: bool = False) -> str:
    lo, hi = metric["interval95"]
    if nonnegative:
        lo = max(0.0, lo)
    return f"{metric['mean']:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def markdown(data: dict[str, Any]) -> str:
    lines = ["# 超高攻击/生命集中属性有效词条绑定与 v4 重算", "", "本报告只比较正式 `current_formal` 与把同一个 selected candidate 的 CATEGORY_RULES、sourceRow、validGroup、有效生命词条、概率 DP、剪枝、缓存键和终局命中完整绑定后的 `health_p975_balanced`。v2/v3 分片、区间与结论均只作失效历史对照。", "", f"- 状态：`{data['release_gate']['status']}`。", f"- 新 schema：`{data['schema_version']}`；v2/v3 schema、resume 与结果未复用。", f"- 分片：`{data['resume']['completed_shards']}/{data['resume']['expected_shards']}`；调度 `{data['resume']['scheduled_shards']}`。", "", "## 概率方法", "", "- 终局生命集中概率使用官方离散跳值的状态级精确概率质量 DP，且缓存键包含 selected candidate 规则上下文和 health_valid_keys。", "- 每个 `+6/+9/+12` 节点先读取当前 selected candidate，按 exact category 唯一定位 CATEGORY_RULES 并校验 sourceRow/setGroup，再读取 validGroup 的 VALID_STATS。", "- 不认可的生命词条不贡献集中 GS，但仍保留在 all_keys 中，作为未来强化命中槽位稀释概率；Heroic `+12` 新增的无效生命词条同样如此。", "- Heroic `+12` 只新增第四副属性；已有三条副属性不会在该节点重复命中。", "- 终局命中、剪枝上界和初始集中值使用同一 health_valid_keys；重铸仅计一次。", f"- 生命 P97.5 阈值：`{data['threshold']['value']:.4f}`；v4 兼容节点且 `P(终局生命集中 GS >= 阈值) >= 10%` 才救回。", ""]
    if "summary" not in data:
        lines.extend(["## 当前进度", "", "分片尚未全部完成，因此没有正式聚合结果；不能据此判断候选优劣。", ""])
        return "\n".join(lines)
    lines.extend(["## 每 100,000 总体力", "", "| 方案 | 正式百里分 | 体力/百里分 | 新增生命集中件 | 每件体力 | 原生75+ | 转换75+ | 22速 | 裂缝体力 | 圣女体力 | 循环 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for key, label in (("current_formal", "current_formal"), (CANDIDATE_KEY, CANDIDATE_KEY)):
        row = data["summary"][key]
        concentration = row["stats"]["incremental_target_high_per_batch"] if key == CANDIDATE_KEY else {"mean": 0.0, "interval95": [0.0, 0.0]}
        resource_total = data["per_seed"][str(data["runs"]["seeds"][0])][key]["resource_pool"]["total_stamina"]
        added_per_100k = row["stats"]["incremental_target_high_per_100k"]["mean"] if key == CANDIDATE_KEY else 0.0
        added_cost = 100000.0 / added_per_100k if added_per_100k > 0 else None
        if key == CANDIDATE_KEY:
            concentration_metric = row["stats"]["incremental_target_high_per_100k"]
            added_display = _fmt(concentration_metric, 4, True)
        else:
            added_display = "0.0000"
        lines.append(f"| {label} | {_fmt(row['per_100k']['value_sum'])} | {_fmt(row['stamina_per_baili'], 1)} | {added_display} | {'-' if added_cost is None else f'{added_cost:.1f}'} | {_fmt(row['per_100k']['native_heirloom'], 3, True)} | {_fmt(row['per_100k']['converted_heirloom'], 3, True)} | {_fmt(row['per_100k']['speed22'], 3, True)} | {_fmt(row['rift_stamina_per_100k'], 1, True)} | {_fmt(row['saint_stamina_per_100k'], 1, True)} | {_fmt(row['cycles_per_100k'], 2, True)} |")
    candidate = data["summary"][CANDIDATE_KEY]
    base = data["summary"]["current_formal"]
    unique_states = candidate["stats"].get("probability_unique_states", {}).get("mean")
    unique_text = "未持久化" if unique_states is None else f"{unique_states:.1f}"
    category_lines = ["", "## 体系兼容质量", "", "| 正式分类 | 自然状态质量 | 基线停止质量 | v3无效词条额外救回 | v3不兼容额外救回 | v4过滤质量 | v4实际救回质量 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for category, metrics in sorted(candidate["stats"].get("by_category", {}).items()):
        category_lines.append(f"| {category} | {_fmt(metrics['natural_quality'], 4, True)} | {_fmt(metrics['baseline_stop_quality'], 4, True)} | {_fmt(metrics['v3_invalid_key_rescue'], 4, True)} | {_fmt(metrics['v3_incompatible_rescue'], 4, True)} | {_fmt(metrics['v4_filtered'], 4, True)} | {_fmt(metrics['v4_rescue'], 4, True)} |")
    lines.extend(["", "## 候选相对基线", "", f"- 正式百里分差（每 100 体力）：`{_fmt(candidate['paired_formal_delta_per_100'], 6)}`。", f"- 正式百里分差（每 100,000 总体力）：`{_fmt(candidate['paired_formal_delta_per_100k'], 4)}`。", f"- 救回节点（每联合批次）：+6 `{_fmt(candidate['rescue_nodes_per_batch']['6'], 4, True)}`，+9 `{_fmt(candidate['rescue_nodes_per_batch']['9'], 4, True)}`，+12 `{_fmt(candidate['rescue_nodes_per_batch']['12'], 4, True)}`。", f"- 概率查询平均每批 `{candidate['stats']['probability_queries']['mean']:.4f}` 个状态；唯一状态数 `{unique_text}`；其中 `0<P<10%` 的 v4 自然质量为 `{candidate['stats']['probability_between_zero_ten']['mean']:.4f}`。", f"- v3因无效生命词条额外救回质量 `{_fmt(candidate['stats']['v3_invalid_key_rescue_per_batch'], 4, True)}`；v3不兼容额外救回质量 `{_fmt(candidate['stats']['v3_incompatible_rescue_per_batch'], 4, True)}`；v4过滤质量 `{_fmt(candidate['stats']['v4_filtered_per_batch'], 4, True)}`。", f"- 相对基线的资源变化：体力/百里分 `{candidate['stamina_per_baili']['mean'] - base['stamina_per_baili']['mean']:+.1f}`；圣女体力/10万 `{candidate['saint_stamina_per_100k']['mean'] - base['saint_stamina_per_100k']['mean']:+.1f}`。", *category_lines, "", "## v2/v3历史对照", "", "- v2因未执行体系兼容过滤而失效；v3虽执行了兼容布尔判断，但未将有效生命词条绑定到DP、剪枝、缓存和终局命中。v2/v3分片、差值和正向区间不作为v4输入或结论。", "", "## 闸门", "", f"- 五 seed 成对 95% 区间：`{candidate['paired_formal_delta_per_100']['interval95']}`。", "- 区间上界小于 0 才能淘汰 v4 候选；跨 0 表示效能未决；下界大于 0 才能另建独立验证任务。", f"- 当前结论：`{data['release_gate']['status']}`；本轮不进入独立验证设计或第三项策略覆盖审计。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exact health P97.5 rescue study")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--external", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--resume", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-shards", type=int)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    seeds = tuple(int(value.strip()) for value in args.seeds.split(",") if value.strip())
    data = run(records=args.records, source=args.source, external=args.external, resume=args.resume, seeds=seeds, runs=max(1, args.runs), workers=max(1, args.workers), max_shards=args.max_shards)
    _atomic_json(args.json_output, data)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(markdown(data) + "\n", encoding="utf-8")
    print(json.dumps({"status": data["release_gate"]["status"], "scheduled_shards": data["resume"]["scheduled_shards"], "completed_shards": data["resume"]["completed_shards"], "expected_shards": data["resume"]["expected_shards"]}, ensure_ascii=False))
    return 0 if data["resume"]["completed_shards"] == data["resume"]["expected_shards"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
