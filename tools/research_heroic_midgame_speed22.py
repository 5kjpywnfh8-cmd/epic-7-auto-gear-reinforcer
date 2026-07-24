"""Offline normal_85 Heroic midgame 22-speed rescue study.

This study is intentionally isolated.  It reads the released Heroic fallback
at +6/+9/+12, then only rescues states the fallback would stop.  It never
changes released policy, DP, score, resource defaults, or the +0/+3 route.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
import sys
from collections import defaultdict
from dataclasses import replace
from itertools import product
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_simulator import CHECKPOINTS, SPEED_REFORGE_BONUS, STAT_POOL, STAT_TYPE_BY_KEY, reforge_bonus_value
from src.e7_enhance.models import Gear, RollHit, SLOT_FORBIDDEN_SUBSTAT_KEYS, Stat
from src.e7_enhance.rules import SET_CODE_TO_NAME
from tools.epic_balanced_prospective import terminal_one_speed_value
from tools.epic_non_speed_early_policy_pareto import (
    formal_followup_action,
    simulate_strategy_path,
    strategies,
    strategy_actions,
)
from tools.epic_non_speed_early_policy_pareto import summarize_incremental_cost
from tools.research_riftslash_saint_pool import second_tier_speed_anchors
from tools.research_heroic_speed_threshold_100k import (
    FORMAL_CATEGORIES,
    HEROIC_PER_EPIC,
    OFFICIAL_ROLL_DISTRIBUTIONS,
    PRIMARY_ELIGIBLE_SETS,
    SPEED_BINS,
    _batch_row,
    _enhance_path,
    _empty_metrics,
    _initial_value,
    _merge,
    _per100k,
    _record,
    _roll_value,
    _released_action,
    _terminal_with_category,
    generate_full_pool_gear,
)
from tools.speed_priority_rolls import speed_roll_distribution


SCHEMA_VERSION = 7
STUDY_NAME = "heroic_midgame_speed22_v7_joint_value_confirmation"
CANDIDATES = (
    "M0_current",
    "M1_reachable_22",
    "M2_p22_0_5pct",
    "M2_p22_1pct",
    "M2_p22_2pct",
    "M2_p22_5pct",
    "M2_p22_10pct",
    "M3_p22_per_stamina_0_002",
    "M3_p22_per_stamina_0_005",
    "M3_p22_per_stamina_0_01",
    "M4_speed_hit_chain",
    "M5_external_speed_reference",
)
SCOPES = ("speed_2pc", "all_sets")
P22_THRESHOLDS = {
    "M2_p22_0_5pct": 0.005, "M2_p22_1pct": 0.01, "M2_p22_2pct": 0.02,
    "M2_p22_5pct": 0.05, "M2_p22_10pct": 0.10,
}
P22_PER_STAMINA_THRESHOLDS = {
    "M3_p22_per_stamina_0_002": 0.002,
    "M3_p22_per_stamina_0_005": 0.005,
    "M3_p22_per_stamina_0_01": 0.01,
}
# The recorded external speed-only reference.  It is never mixed with GS rules.
EXTERNAL_SPEED_REFERENCE = {6: 5, 9: 10, 12: 13}
EXPECTED_ACTION_GROUPS = (
    (
        "M1_reachable_22", "M2_p22_0_5pct", "M2_p22_1pct", "M2_p22_2pct",
        "M2_p22_5pct", "M4_speed_hit_chain", "M5_external_speed_reference",
    ),
    ("M2_p22_10pct", "M3_p22_per_stamina_0_002"),
    ("M0_current", "M3_p22_per_stamina_0_005", "M3_p22_per_stamina_0_01"),
)
V7_POSITIVE_DRAWS_PER_SIGNATURE = 64
V7_FAILURE_DRAWS_PER_SIGNATURE = 2
EPIC_B_KEY = "B_global_current_gs"
COMBINED_HEROIC_KEYS = (
    "M0_current/all_sets",
    "M2_p22_10pct/all_sets",
    "M1_reachable_22/all_sets",
)
SPEED_VALUE_ANCHORS = second_tier_speed_anchors()
_ACTION_MATRIX_CACHE: dict[str, Any] | None = None


def _speed_stat(gear: Gear):
    return next((stat for stat in gear.substats if stat.key == "spd"), None)


def _last_real_speed_hit(gear: Gear) -> bool:
    return bool(
        gear.roll_history
        and gear.roll_history[-1].enhance in {3, 6, 9, 15}
        and gear.roll_history[-1].key == "spd"
    )


def _scope_applies(scope: str, gear: Gear) -> bool:
    return scope == "all_sets" or gear.set in PRIMARY_ELIGIBLE_SETS


def speed_terminal_distribution(gear: Gear, *, rare_speed_rolls_removed: bool = False) -> dict[int, float]:
    """Exact final reforged speed distribution from the observable state.

    Heroic +12 adds the fourth substat when necessary.  It is not a roll and
    cannot hit speed.  Reforge is applied exactly once after +15.
    """
    speed = _speed_stat(gear)
    if speed is None or gear.slot == "boot":
        return {}
    raw_profile = speed_roll_distribution("normal_85", "Heroic", rare_speed_rolls_removed=rare_speed_rolls_removed)
    profile_total = sum(probability for _value, probability in raw_profile)
    # The published three-decimal percentages round to 100.001%.  Normalize
    # their decimal representation before exact enumeration.
    profile = tuple((value, probability / profile_total) for value, probability in raw_profile)
    existing_count = max(len(gear.substats), 4 if gear.enhance >= 12 else len(gear.substats))
    states: dict[tuple[int, int, int], float] = {(int(speed.normalized_value), int(speed.rolls), existing_count): 1.0}
    for checkpoint in CHECKPOINTS:
        if checkpoint <= gear.enhance:
            continue
        next_states: dict[tuple[int, int, int], float] = defaultdict(float)
        for (value, rolls, count), probability in states.items():
            if checkpoint == 12 and count < 4:
                next_states[(value, rolls, count + 1)] += probability
                continue
            hit_probability = 1.0 / count
            next_states[(value, rolls, count)] += probability * (1.0 - hit_probability)
            for increment, roll_probability in profile:
                next_states[(value + increment, rolls + 1, count)] += probability * hit_probability * roll_probability
        states = next_states
    terminal: dict[int, float] = defaultdict(float)
    for (value, rolls, _count), probability in states.items():
        terminal[int(value + reforge_bonus_value("spd", rolls))] += probability
    return dict(sorted(terminal.items()))


def p22_exact(gear: Gear, *, rare_speed_rolls_removed: bool = False) -> float:
    return sum(probability for value, probability in speed_terminal_distribution(gear, rare_speed_rolls_removed=rare_speed_rolls_removed).items() if value >= 22)


def _next_node_stamina(gear: Gear) -> float:
    next_checkpoint = next((point for point in CHECKPOINTS if point > gear.enhance), None)
    if next_checkpoint is None:
        return float("inf")
    return float(summarize_incremental_cost(gear.slot, gear.rank, gear.enhance, next_checkpoint)["net_stamina"])


def candidate_action(
    candidate: str,
    gear: Gear,
    *,
    baseline_action: str,
    scope: str = "all_sets",
    item_source: str = "normal_85",
    rare_speed_rolls_removed: bool = False,
    probability: float | None = None,
) -> str:
    """Return the research action; released continues are immutable."""
    if baseline_action == "continue":
        return "continue"
    if candidate == "M0_current":
        return "stop"
    speed = _speed_stat(gear)
    if (
        item_source != "normal_85" or gear.rank != "Heroic" or gear.enhance not in {6, 9, 12}
        or gear.slot == "boot" or speed is None or not _scope_applies(scope, gear)
    ):
        return "stop"
    probability = p22_exact(gear, rare_speed_rolls_removed=rare_speed_rolls_removed) if probability is None else probability
    if probability <= 0:
        return "stop"
    if candidate == "M1_reachable_22":
        return "continue"
    if candidate in P22_THRESHOLDS:
        return "continue" if probability >= P22_THRESHOLDS[candidate] else "stop"
    if candidate in P22_PER_STAMINA_THRESHOLDS:
        return "continue" if probability / _next_node_stamina(gear) >= P22_PER_STAMINA_THRESHOLDS[candidate] else "stop"
    if candidate == "M4_speed_hit_chain":
        return "continue" if _last_real_speed_hit(gear) else "stop"
    if candidate == "M5_external_speed_reference":
        return "continue" if speed.normalized_value >= EXTERNAL_SPEED_REFERENCE[gear.enhance] else "stop"
    raise ValueError(f"unknown candidate: {candidate}")


def speed_oracle_action(gear: Gear, *, baseline_action: str, scope: str = "all_sets") -> str:
    """Compatibility alias.  M1 is reachability rescue, never an efficiency oracle."""
    return candidate_action("M1_reachable_22", gear, baseline_action=baseline_action, scope=scope)


def _matrix_path(signature: dict[str, Any], *, slot: str, set_code: str) -> dict[int, Gear]:
    """Construct the speed-only legal path fixed by one mutual signature."""
    main_key = _main_keys(slot)[0]
    available = [key for key in STAT_POOL if key not in SLOT_FORBIDDEN_SUBSTAT_KEYS.get(slot, set()) and key != main_key]
    other_keys = [key for key in available if key != "spd"][:2]
    gear = Gear(
        set_code, slot, Stat(STAT_TYPE_BY_KEY[main_key], 0), enhance=0, rank="Heroic", level=85,
        substats=[Stat("Speed", signature["initial_speed"], rolls=1)] + [Stat(STAT_TYPE_BY_KEY[key], 4, rolls=1) for key in other_keys],
        reforge_eligible=True,
    )
    path = {0: gear}
    for checkpoint, speed_hit, jump in zip((3, 6, 9), signature["history_speed_hits"], signature["history_speed_jumps"]):
        gear = _apply_legal_roll(gear, checkpoint, "spd" if speed_hit else other_keys[0], int(jump) if speed_hit else 4)
        path[checkpoint] = gear
    fourth_key = next(key for key in available if key not in {stat.key for stat in gear.substats})
    gear = replace(gear, enhance=12, substats=gear.substats + [Stat(STAT_TYPE_BY_KEY[fourth_key], 4, rolls=1)])
    path[12] = gear
    gear = _apply_legal_roll(gear, 15, "spd" if signature["plus15_speed_hit"] else other_keys[0], int(signature["plus15_speed_jump"]) if signature["plus15_speed_hit"] else 4)
    path[15] = gear
    return path


def candidate_action_equivalence_matrix() -> dict[str, Any]:
    """Exhaust all speed signatures and legal action contexts before aliasing.

    The matrix deliberately varies every legal speed signature, slot and set
    scope, then reads the actual released fallback action at each node.  It
    therefore compares complete reachable binary enhancement sequences, not
    artificial stop/continue combinations or frontend recommendation labels.
    """
    global _ACTION_MATRIX_CACHE
    if _ACTION_MATRIX_CACHE is not None:
        return _ACTION_MATRIX_CACHE
    traces: dict[str, list[tuple[tuple[int, str], ...]]] = {candidate: [] for candidate in CANDIDATES}
    seen_prefixes: set[tuple[Any, ...]] = set()
    for signature in speed_signature_strata(("set_speed",), initial_mode="legacy_initial_uniform"):
        prefix = (signature["initial_speed"], tuple(signature["history_speed_hits"]), tuple(signature["history_speed_jumps"]))
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        for slot in ("weapon", "helm", "armor", "neck", "ring"):
            for set_code in ("set_speed", "set_att"):
                path = _matrix_path(signature, slot=slot, set_code=set_code)
                probabilities = {point: p22_exact(path[point]) for point in (6, 9, 12)}
                baseline_actions = {point: _released_action(path[point]) for point in CHECKPOINTS[:-1]}
                for scope in SCOPES:
                    for candidate in CANDIDATES:
                        outcome = _run_path(path, candidate, scope, False, baseline_actions, probabilities)
                        traces[candidate].append(tuple(sorted(outcome["actions"].items())))
    groups: list[dict[str, Any]] = []
    remaining = list(CANDIDATES)
    while remaining:
        representative = remaining.pop(0)
        members = [representative]
        for candidate in list(remaining):
            if traces[candidate] == traces[representative]:
                members.append(candidate)
                remaining.remove(candidate)
        groups.append({"representative": representative, "members": members})
    observed = {frozenset(group["members"]) for group in groups}
    expected = {frozenset(group) for group in EXPECTED_ACTION_GROUPS}
    witnesses: list[dict[str, Any]] = []
    if observed != expected:
        witnesses.append({"reason": "candidate_action_groups_differ_from_expected", "observed": [sorted(group) for group in observed], "expected": [sorted(group) for group in expected]})
    _ACTION_MATRIX_CACHE = {"state_count_per_candidate": len(next(iter(traces.values()))), "groups": groups, "witnesses": witnesses}
    return _ACTION_MATRIX_CACHE


def _ess(weights: list[float]) -> float:
    total = sum(weights)
    squared = sum(weight * weight for weight in weights)
    return 0.0 if squared <= 0 else total * total / squared


def _candidate_event_summary(
    *, raw_events: dict[str, Any], weighted_rescued_22_per_100k: float,
    sample_weights: list[float], design_weights: list[float] | None = None,
) -> dict[str, Any]:
    """Keep raw events, design coverage, and positive contributions separate."""
    ess = _ess(sample_weights)
    positive_total = sum(sample_weights)
    ordered = sorted(sample_weights, reverse=True)
    return {
        "reference_name": "reachability_rescue",
        "raw_unique_rescued_22_count": len(raw_events),
        "weighted_rescued_22_per_100k": weighted_rescued_22_per_100k,
        "weighted_ess": ess,  # Compatibility alias: positive-contribution ESS.
        "positive_contribution_ess": ess,
        "design_ess": _ess(design_weights or []),
        "max_single_contribution_share": 0.0 if positive_total <= 0 else ordered[0] / positive_total,
        "top5_contribution_share": 0.0 if positive_total <= 0 else sum(ordered[:5]) / positive_total,
    }


def _marginal_per_added_22(m0: dict[str, float], candidate: dict[str, float], *, added_heroic22: float) -> dict[str, float | None]:
    """Source changes per added 22+, never a fixed 100k-total subtraction."""
    if added_heroic22 <= 0:
        return {name: None for name in (
            "saint_stamina_per_added_heroic22", "riftslash_stamina_lost_per_added_heroic22",
            "source_cycles_lost_per_added_heroic22", "strategy_gs_change_per_added_heroic22",
        )}
    return {
        "saint_stamina_per_added_heroic22": (candidate["saint_stamina"] - m0["saint_stamina"]) / added_heroic22,
        "riftslash_stamina_lost_per_added_heroic22": (m0["riftslash_stamina"] - candidate["riftslash_stamina"]) / added_heroic22,
        "source_cycles_lost_per_added_heroic22": (m0["cycles"] - candidate["cycles"]) / added_heroic22,
        "strategy_gs_change_per_added_heroic22": (candidate["strategy_gs"] - m0["strategy_gs"]) / added_heroic22,
    }


def enumerate_legal_rescue_states() -> list[dict[str, Any]]:
    """Audit only witnesses that can be constructed from legal +0 events."""
    path = _legal_heroic_speed_witness_path()
    validate_legal_rescue_witness_path(path)
    states: list[dict[str, Any]] = []
    for enhance in (6, 9, 12):
        gear = path[enhance]
        baseline = _released_action(gear)
        probability = p22_exact(gear)
        rescued = [candidate for candidate in CANDIDATES if candidate_action(candidate, gear, baseline_action=baseline, probability=probability) == "continue" and baseline == "stop"]
        if baseline == "stop" and probability > 0 and rescued:
            states.append({"node": enhance, "gear": gear, "baseline_action": baseline, "p22": probability, "rescued_candidates": rescued,
                           "path": path,
                           "legal_history": "从+0三词条依次执行+3/+6/+9速度命中；+12仅补非重复第四词条"})
    return states


def _legal_heroic_speed_witness_path() -> dict[int, Gear]:
    """Build a deterministic legal Heroic path used only by the state audit.

    The three speed rolls are real +3/+6/+9 enhancement events.  Heroic +12
    merely adds a fourth, non-duplicate substat, so its speed state is copied
    unchanged from +9.
    """
    base = Gear(
        "set_speed", "weapon", Stat("Attack", 0), enhance=0, rank="Heroic", level=85,
        substats=[Stat("Speed", 2, rolls=1), Stat("AttackPercent", 4, rolls=1), Stat("CriticalHitChancePercent", 3, rolls=1)],
        reforge_eligible=True,
    )
    path = {0: base}
    current = base
    for checkpoint in (3, 6, 9):
        current = _apply_legal_roll(current, checkpoint, "spd", 4)
        path[checkpoint] = current
    before_add = current
    current = _add_legal_fourth_substat(current, "hpPct", 4)
    path[12] = current
    speed9 = _speed_stat(before_add)
    speed12 = _speed_stat(current)
    assert speed9 is not None and speed12 is not None
    assert (speed9.normalized_value, speed9.rolls) == (speed12.normalized_value, speed12.rolls)
    current = _apply_legal_roll(current, 15, "spd", 4)
    path[15] = current
    return path


def validate_legal_rescue_witness_path(path: dict[int, Gear]) -> None:
    """Reject an audit witness that cannot arise through Heroic enhancement."""
    expected_nodes = {0, 3, 6, 9, 12, 15}
    if set(path) != expected_nodes:
        raise ValueError("witness must contain the complete +0 to +15 path")
    base = path[0]
    if base.rank != "Heroic" or base.enhance != 0 or len(base.substats) != 3:
        raise ValueError("witness must start from a Heroic +0 three-substat gear")
    if len({stat.key for stat in base.substats}) != 3 or base.main_stat.key in {stat.key for stat in base.substats}:
        raise ValueError("initial witness substats must be legal and non-duplicate")
    initial_speed = _speed_stat(base)
    if initial_speed is None:
        raise ValueError("initial witness must contain speed")
    legal_speed_rolls = {value for value, _probability in speed_roll_distribution("normal_85", "Heroic")}
    previous = base
    for checkpoint in (3, 6, 9):
        current = path[checkpoint]
        if current.enhance != checkpoint or len(current.substats) != 3:
            raise ValueError("pre-+12 witness state must retain three substats")
        if len(current.roll_history) != len(previous.roll_history) + 1:
            raise ValueError("each +3/+6/+9 event must add exactly one roll history entry")
        hit = current.roll_history[-1]
        before_speed = _speed_stat(previous)
        after_speed = _speed_stat(current)
        if before_speed is None or after_speed is None or hit.enhance != checkpoint or hit.key != "spd" or hit.value not in legal_speed_rolls:
            raise ValueError("+3/+6/+9 must contain a legal speed hit")
        if after_speed.rolls != before_speed.rolls + 1 or after_speed.normalized_value != before_speed.normalized_value + hit.value:
            raise ValueError("speed state does not match roll history")
        previous = current
    plus_nine_speed = _speed_stat(path[9])
    plus_twelve = path[12]
    plus_twelve_speed = _speed_stat(plus_twelve)
    if plus_twelve.enhance != 12 or len(plus_twelve.substats) != 4:
        raise ValueError("Heroic +12 witness must contain four substats")
    keys = {stat.key for stat in plus_twelve.substats}
    if len(keys) != 4 or plus_twelve.main_stat.key in keys:
        raise ValueError("Heroic +12 fourth substat must be legal and non-duplicate")
    if plus_nine_speed is None or plus_twelve_speed is None or (plus_nine_speed.normalized_value, plus_nine_speed.rolls) != (plus_twelve_speed.normalized_value, plus_twelve_speed.rolls):
        raise ValueError("+12 fourth-substat event must not change speed or speed rolls")
    if plus_twelve.roll_history != path[9].roll_history:
        raise ValueError("+12 fourth-substat event must not add a roll history entry")
    final = path[15]
    if final.enhance != 15 or len(final.substats) != 4 or len(final.roll_history) != len(plus_twelve.roll_history) + 1:
        raise ValueError("+15 witness must be a legal post-+12 enhancement state")


def _apply_legal_roll(gear: Gear, checkpoint: int, key: str, value: int) -> Gear:
    if checkpoint not in {3, 6, 9, 15} or gear.enhance + 3 != checkpoint:
        raise ValueError("illegal enhancement checkpoint")
    if key == "spd":
        legal_values = {roll for roll, _probability in speed_roll_distribution("normal_85", "Heroic")}
        if value not in legal_values:
            raise ValueError("illegal Heroic speed roll")
    index = next((number for number, stat in enumerate(gear.substats) if stat.key == key), None)
    if index is None:
        raise ValueError("roll target is not an existing substat")
    stat = gear.substats[index]
    updated = replace(stat, value=stat.normalized_value + value, rolls=stat.rolls + 1)
    substats = list(gear.substats)
    substats[index] = updated
    return replace(gear, enhance=checkpoint, substats=substats, roll_history=gear.roll_history + [RollHit(checkpoint, updated.type, value)])


def _add_legal_fourth_substat(gear: Gear, key: str, value: int) -> Gear:
    if gear.rank != "Heroic" or gear.enhance != 9 or len(gear.substats) != 3:
        raise ValueError("Heroic fourth-substat event requires a +9 three-substat state")
    existing = {stat.key for stat in gear.substats} | {gear.main_stat.key}
    if key in existing or key == "spd":
        raise ValueError("fourth substat must be legal and non-duplicate")
    type_by_key = {"hpPct": "HealthPercent"}
    if key not in type_by_key:
        raise ValueError("unsupported audit fourth substat")
    return replace(gear, enhance=12, substats=gear.substats + [Stat(type_by_key[key], value, rolls=1)])


def _run_path(path: dict[int, Gear], candidate: str, scope: str, rare: bool, baseline_actions: dict[int, str] | None = None, probabilities: dict[int, float] | None = None) -> dict[str, Any]:
    current = 0
    reached = [0]
    actions: dict[int, str] = {}
    rescued_nodes: list[int] = []
    baseline_naturally_reached = [0]
    baseline_current = 0
    while baseline_current < 15:
        baseline = baseline_actions[baseline_current] if baseline_actions is not None else _released_action(path[baseline_current])
        if baseline == "stop":
            break
        baseline_current = next(point for point in CHECKPOINTS if point > baseline_current)
        baseline_naturally_reached.append(baseline_current)
    if probabilities is None:
        probabilities = {} if candidate == "M0_current" else {point: p22_exact(path[point], rare_speed_rolls_removed=rare) for point in (6, 9, 12)}
    while current < 15:
        state = path[current]
        baseline = baseline_actions[current] if baseline_actions is not None else _released_action(state)
        action = candidate_action(candidate, state, baseline_action=baseline, scope=scope, rare_speed_rolls_removed=rare, probability=probabilities.get(current))
        actions[current] = action
        if baseline == "stop" and action == "continue":
            rescued_nodes.append(current)
        if action == "stop":
            break
        current = next(point for point in CHECKPOINTS if point > current)
        reached.append(current)
    return {
        "start_checkpoint": 0, "stop_checkpoint": current, "reached": reached,
        "actions": actions, "net_stamina": 0.0, "rescued_nodes": rescued_nodes,
        "first_rescue_node": rescued_nodes[0] if rescued_nodes else None,
        "later_rescue_nodes": rescued_nodes[1:],
        "baseline_naturally_reached": baseline_naturally_reached,
        "candidate_only_reached": [point for point in reached if point not in baseline_naturally_reached],
    }


def _new_row() -> dict[str, Any]:
    return {
        "metrics": _empty_metrics(),
        "base_stops": {str(point): 0.0 for point in (6, 9, 12)},
        "base_continues": {str(point): 0.0 for point in (6, 9, 12)},
        "rescued": {str(point): 0.0 for point in (6, 9, 12)},
        "rescued_then_stopped": {str(point): 0.0 for point in (6, 9, 12)},
        "first_rescue_22": {str(point): 0 for point in (6, 9, 12)},
        "raw_rescued_22_events": {},
        "weighted_rescued_22_count": 0.0,
        "stratum_weight_sum": 0.0,
        "stratum_weight_square_sum": 0.0,
    }


def _record_row(row: dict[str, Any], path: dict[int, Gear], outcome: dict[str, Any], terminal: dict[str, Any], baseline_actions: dict[int, str] | None = None, *, trajectory_id: str = "", natural_weight: float = 1.0) -> None:
    for point in (6, 9, 12):
        if point not in outcome["actions"]:
            continue
        base = baseline_actions[point] if baseline_actions is not None else _released_action(path[point])
        row["base_continues" if base == "continue" else "base_stops"][str(point)] += 1
    for point in outcome["rescued_nodes"]:
        row["rescued"][str(point)] += 1
        if outcome["stop_checkpoint"] != 15:
            row["rescued_then_stopped"][str(point)] += 1
    if outcome["rescued_nodes"] and outcome["stop_checkpoint"] == 15:
        actual_speed = _speed_stat(path[15]).normalized_value + reforge_bonus_value("spd", _speed_stat(path[15]).rolls) if _speed_stat(path[15]) else 0
        if actual_speed >= 22:
            row["raw_rescued_22_events"][trajectory_id] = 1
            row["weighted_rescued_22_count"] += natural_weight
            row["stratum_weight_sum"] += natural_weight
            row["stratum_weight_square_sum"] += natural_weight * natural_weight
            first = outcome["first_rescue_node"]
            if first is not None:
                row["first_rescue_22"][str(first)] += 1
    _record(row["metrics"], path[15], outcome, terminal)


def _merge_row(target: dict[str, Any], source: dict[str, Any]) -> None:
    target_metrics, source_metrics = target["metrics"], source["metrics"]
    from tools.research_heroic_speed_threshold_100k import _merge
    _merge(target_metrics, source_metrics)
    for name in ("base_stops", "base_continues", "rescued", "rescued_then_stopped", "first_rescue_22"):
        for key, value in source[name].items():
            target[name][key] += value
    target["raw_rescued_22_events"].update(source["raw_rescued_22_events"])
    for name in ("weighted_rescued_22_count", "stratum_weight_sum", "stratum_weight_square_sum"):
        target[name] += source[name]


def _simulate_shard(*, seed: int, runs: int, initial_mode: str, sets: tuple[str, ...], rare: bool) -> dict[str, Any]:
    rng = random.Random(seed)
    rows = {f"{candidate}/{scope}": _new_row() for candidate in CANDIDATES for scope in SCOPES}
    epic = _empty_metrics()
    strata: dict[str, int] = defaultdict(int)
    for path_index in range(runs):
        set_code = rng.choice(sets)
        heroic = generate_full_pool_gear(set_code, "Heroic", rng, initial_mode)
        heroic_path = _enhance_path(heroic, rng, initial_mode)
        terminal: dict[str, Any] | None = None
        heroic_baseline_actions = {point: _released_action(heroic_path[point]) for point in CHECKPOINTS[:-1]}
        heroic_probabilities = {point: p22_exact(heroic_path[point], rare_speed_rolls_removed=rare) for point in (6, 9, 12)}
        for point in (6, 9, 12):
            state = heroic_path[point]
            speed = _speed_stat(state)
            rescued = tuple(candidate for candidate in CANDIDATES if candidate_action(candidate, state, baseline_action=heroic_baseline_actions[point], probability=heroic_probabilities[point]) == "continue" and heroic_baseline_actions[point] == "stop")
            key = "|".join((
                initial_mode, state.set, state.slot, state.main_stat.key,
                str(point), "speed" if speed else "no_speed", str(speed.normalized_value if speed else 0),
                str(speed.rolls if speed else 0), "last_speed_hit" if _last_real_speed_hit(state) else "no_last_speed_hit",
                heroic_baseline_actions[point], ",".join(rescued) or "none",
            ))
            strata[key] += 1
        for candidate in CANDIDATES:
            for scope in SCOPES:
                key = f"{candidate}/{scope}"
                outcome = _run_path(heroic_path, candidate, scope, rare, heroic_baseline_actions, heroic_probabilities)
                if outcome["stop_checkpoint"] == 15 and terminal is None:
                    terminal = _terminal_with_category(heroic_path[15])
                _record_row(rows[key], heroic_path, outcome, terminal or {}, heroic_baseline_actions,
                            trajectory_id=f"{seed}:full_pool:{path_index}:{key}")
        # Epic is frozen and is sampled once per source batch.
        epic_gear = generate_full_pool_gear(set_code, "Epic", rng, initial_mode)
        epic_path = _enhance_path(epic_gear, rng, initial_mode)
        epic_outcome = _run_path(epic_path, "M0_current", "all_sets", rare, {point: _released_action(epic_path[point]) for point in CHECKPOINTS[:-1]})
        epic_terminal = _terminal_with_category(epic_path[15]) if epic_outcome["stop_checkpoint"] == 15 else {}
        _record(epic, epic_path[15], epic_outcome, epic_terminal)
    return {"schema_version": SCHEMA_VERSION, "study": STUDY_NAME, "seed": seed, "runs": runs, "initial_mode": initial_mode, "sets": list(sets), "rare_speed_rolls_removed": rare, "heroic": rows, "epic": epic,
            "strata": {key: {"raw_count": count, "natural_weight": count / runs} for key, count in sorted(strata.items())}}


def _main_keys(slot: str) -> tuple[str, ...]:
    return {
        "weapon": ("atkFlat",), "helm": ("hpFlat",), "armor": ("defFlat",),
        "neck": ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "crit", "cdmg"),
        "ring": ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "eff", "res"),
        "boot": ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "spd"),
    }[slot]


def _speed_non_boot_probability() -> float:
    probability = 0.0
    for slot in ("weapon", "helm", "armor", "neck", "ring"):
        main_keys = _main_keys(slot)
        for main_key in main_keys:
            available = [key for key in STAT_POOL if key not in SLOT_FORBIDDEN_SUBSTAT_KEYS.get(slot, set()) and key != main_key]
            probability += (1.0 / 6.0) * (1.0 / len(main_keys)) * (3.0 / len(available))
    return probability


def speed_signature_strata(
    sets: tuple[str, ...], *, initial_mode: str = "legacy_initial_uniform", rare: bool = False,
) -> list[dict[str, Any]]:
    """Enumerate mutually exclusive Heroic speed signatures and their mass.

    A signature fixes only the random events that determine speed: initial
    speed, each +3/+6/+9 target and speed jump, and the +15 target/jump.  The
    remaining equipment fields and non-speed outcomes are sampled inside that
    signature, preserving both resource-consuming failures and terminal wins.
    """
    if not sets:
        raise ValueError("at least one selected set is required")
    base_probability = _speed_non_boot_probability()
    speed_profile = tuple(
        (value, probability / sum(weight for _roll, weight in speed_roll_distribution("normal_85", "Heroic", rare_speed_rolls_removed=rare)) )
        for value, probability in speed_roll_distribution("normal_85", "Heroic", rare_speed_rolls_removed=rare)
    )
    result: list[dict[str, Any]] = []
    for initial_speed, initial_probability in ((value, _initial_probability("spd", value, initial_mode)) for value in (1, 2, 3, 4)):
        for history in product((False, True), repeat=3):
            jump_options = [tuple(speed_profile) if hit else ((None, 1.0),) for hit in history]
            for jumps in product(*jump_options):
                history_probability = 1.0
                history_values: list[int | None] = []
                for hit, (jump, jump_probability) in zip(history, jumps):
                    history_probability *= (1.0 / 3.0) * jump_probability if hit else 2.0 / 3.0
                    history_values.append(None if jump is None else int(jump))
                for plus15_hit, plus15_jump, plus15_probability in (
                    [(False, None, 3.0 / 4.0)]
                    + [(True, int(value), 0.25 * probability) for value, probability in speed_profile]
                ):
                    rolls = 1 + sum(history) + int(plus15_hit)
                    raw_speed = initial_speed + sum(value or 0 for value in history_values) + (plus15_jump or 0)
                    signature_id = "i{}-h{}-j{}-f{}".format(
                        initial_speed,
                        "".join("1" if hit else "0" for hit in history),
                        ".".join("-" if value is None else str(value) for value in history_values),
                        "-" if plus15_jump is None else str(plus15_jump),
                    )
                    result.append({
                        "signature_id": signature_id,
                        "initial_speed": initial_speed,
                        "history_speed_hits": list(history),
                        "history_speed_jumps": history_values,
                        "plus15_speed_hit": plus15_hit,
                        "plus15_speed_jump": plus15_jump,
                        "rare_speed_rolls_removed": rare,
                        "natural_speed_non_boot_probability": base_probability,
                        "natural_probability": base_probability * initial_probability * history_probability * plus15_probability,
                        "terminal_speed": raw_speed + reforge_bonus_value("spd", rolls),
                    })
    return result


def stratified_plan_specs(sets: tuple[str, ...], *, initial_mode: str = "legacy_initial_uniform") -> list[dict[str, Any]]:
    """Compatibility name for v6 callers; v6 contains no overlapping plans."""
    return speed_signature_strata(sets, initial_mode=initial_mode)


def _distribution_probability(distribution: tuple[tuple[int, float], ...], value: float) -> float:
    total = sum(probability for _roll, probability in distribution)
    return next((probability / total for roll, probability in distribution if roll == value), 0.0)


def _initial_probability(key: str, value: float, initial_mode: str) -> float:
    if initial_mode == "legacy_initial_uniform":
        if key == "spd":
            return 0.25 if value in {1, 2, 3, 4} else 0.0
        low = min(roll for roll, _probability in OFFICIAL_ROLL_DISTRIBUTIONS[key])
        high = max(roll for roll, _probability in OFFICIAL_ROLL_DISTRIBUTIONS[key])
        return 1.0 / (high - low + 1) if low <= value <= high else 0.0
    if initial_mode == "roll_distribution_as_initial_proxy":
        distribution = speed_roll_distribution("normal_85", "Heroic") if key == "spd" else OFFICIAL_ROLL_DISTRIBUTIONS[key]
        return _distribution_probability(distribution, value)
    raise ValueError(f"unknown initial mode: {initial_mode}")


def _roll_probability(key: str, value: float) -> float:
    distribution = speed_roll_distribution("normal_85", "Heroic") if key == "spd" else OFFICIAL_ROLL_DISTRIBUTIONS[key]
    return _distribution_probability(distribution, value)


def _initial_components(gear: Gear, initial_mode: str, sets: tuple[str, ...]) -> dict[str, Any]:
    available = [key for key in STAT_POOL if key not in SLOT_FORBIDDEN_SUBSTAT_KEYS.get(gear.slot, set()) and key != gear.main_stat.key]
    ordered_substats = 1.0 / (len(available) * (len(available) - 1) * (len(available) - 2))
    values = 1.0
    for stat in gear.substats:
        values *= _initial_probability(stat.key, stat.normalized_value, initial_mode)
    speed = _speed_stat(gear)
    return {
        "set_probability": 1.0 / len(sets),
        "slot_probability": 1.0 / 6.0,
        "main_stat_probability": 1.0 / len(_main_keys(gear.slot)),
        "initial_substat_order_probability": ordered_substats,
        "initial_speed_inclusion_probability": 3.0 / len(available) if speed is not None else 0.0,
        "initial_speed_value_probability": _initial_probability("spd", speed.normalized_value, initial_mode) if speed else 0.0,
        "initial_substat_value_probability": values,
    }


def _multiply_components(components: dict[str, Any]) -> float:
    return float(
        components["set_probability"]
        * components["slot_probability"]
        * components["main_stat_probability"]
        * components["initial_substat_order_probability"]
        * components["initial_substat_value_probability"]
        * components["history_target_probability"]
        * components["history_roll_probability"]
        * components["fourth_substat_probability"]
        * components["fourth_substat_value_probability"]
        * components["plus15_target_probability"]
        * components["plus15_roll_probability"]
    )


def _sample_speed_signature_path(
    rng: random.Random, *, signature: dict[str, Any], initial_mode: str, sets: tuple[str, ...]
) -> tuple[dict[int, Gear], dict[str, Any]]:
    """Sample conditionally inside one mutually exclusive speed signature."""
    while True:
        base = generate_full_pool_gear(rng.choice(sets), "Heroic", rng, initial_mode)
        speed = _speed_stat(base)
        if base.slot != "boot" and speed is not None and speed.normalized_value == signature["initial_speed"]:
            break
    current = base
    path = {0: current}
    history = []
    for checkpoint, speed_hit, forced_jump in zip(
        (3, 6, 9), signature["history_speed_hits"], signature["history_speed_jumps"],
    ):
        if speed_hit:
            index = next(index for index, stat in enumerate(current.substats) if stat.key == "spd")
        else:
            choices = [index for index, stat in enumerate(current.substats) if stat.key != "spd"]
            index = rng.choice(choices)
        stat = current.substats[index]
        value = int(forced_jump) if speed_hit else _roll_value(rng, stat.key, current.rank)
        updated = replace(stat, value=stat.normalized_value + value, rolls=stat.rolls + 1)
        stats = list(current.substats)
        stats[index] = updated
        current = replace(current, enhance=checkpoint, substats=stats, roll_history=current.roll_history + [RollHit(checkpoint, updated.type, value)])
        path[checkpoint] = current
        history.append({"checkpoint": checkpoint, "target": stat.key, "speed_hit": speed_hit, "jump": value})
    existing = {stat.key for stat in current.substats} | {current.main_stat.key} | set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(current.slot, set()))
    fourth_choices = [key for key in STAT_POOL if key not in existing]
    fourth_key = rng.choice(fourth_choices)
    fourth_value = _initial_value(rng, fourth_key, "Heroic", initial_mode)
    current = replace(current, enhance=12, substats=current.substats + [Stat(STAT_TYPE_BY_KEY[fourth_key], fourth_value, rolls=1)])
    path[12] = current
    if signature["plus15_speed_hit"]:
        index = next(index for index, stat in enumerate(current.substats) if stat.key == "spd")
        final_value = int(signature["plus15_speed_jump"])
    else:
        index = rng.choice([number for number, stat in enumerate(current.substats) if stat.key != "spd"])
        stat = current.substats[index]
        final_value = _roll_value(rng, stat.key, current.rank)
    stat = current.substats[index]
    updated = replace(stat, value=stat.normalized_value + final_value, rolls=stat.rolls + 1)
    stats = list(current.substats)
    stats[index] = updated
    current = replace(current, enhance=15, substats=stats, roll_history=current.roll_history + [RollHit(15, updated.type, final_value)])
    path[15] = current
    return path, {
        "speed_signature": signature["signature_id"],
        "natural_probability": signature["natural_probability"],
        "natural_probability_components": {
            "initial_speed": signature["initial_speed"],
            "history": history,
            "fourth_substat_key": fourth_key,
            "plus15_target": stat.key,
            "plus15_roll": final_value,
        },
    }


def _record_stratified_delta(
    row: dict[str, Any], *, path: dict[int, Gear], baseline: dict[str, Any], candidate: dict[str, Any],
    baseline_actions: dict[int, str], natural_weight: float, evidence: dict[str, Any], trajectory_id: str,
    terminal: dict[str, Any],
) -> None:
    candidate_terminal = terminal if candidate["stop_checkpoint"] == 15 else {}
    baseline_terminal = terminal if baseline["stop_checkpoint"] == 15 else {}
    candidate_metrics = _empty_metrics()
    baseline_metrics = _empty_metrics()
    _record(candidate_metrics, path[15], candidate, candidate_terminal)
    _record(baseline_metrics, path[15], baseline, baseline_terminal)
    # Every outcome term uses the same stratum mass.  This includes failed
    # rescues, enhancement flow, sale recovery, conversion cost, and GS.
    _merge(row["metrics"], candidate_metrics, natural_weight)
    _merge(row["metrics"], baseline_metrics, -natural_weight)
    first = candidate["first_rescue_node"]
    if first is not None:
        row["rescued"][str(first)] += natural_weight
        if candidate["stop_checkpoint"] != 15:
            row["rescued_then_stopped"][str(first)] += natural_weight
    actual_speed = _speed_stat(path[15])
    final_speed = 0.0 if actual_speed is None else actual_speed.normalized_value + reforge_bonus_value("spd", actual_speed.rolls)
    if first is not None and candidate["stop_checkpoint"] == 15 and final_speed >= 22:
        row["raw_rescued_22_events"][trajectory_id] = {
            "trajectory_id": trajectory_id, **evidence, "natural_weight": natural_weight,
            "first_rescue_node": first, "later_rescue_nodes": candidate["later_rescue_nodes"],
        }
        row["weighted_rescued_22_count"] += natural_weight
        row["stratum_weight_sum"] += natural_weight
        row["stratum_weight_square_sum"] += natural_weight * natural_weight
        row["first_rescue_22"][str(first)] += 1


def _outcome_for_record(outcome: dict[str, Any]) -> dict[str, Any]:
    """Adapt the frozen Epic research path result to the shared metrics shape."""
    return {
        "start_checkpoint": outcome["start_checkpoint"],
        "stop_checkpoint": outcome["stop_checkpoint"],
        "reached": outcome["reached_checkpoints"],
        "net_stamina": outcome["net_stamina"],
    }


def _frozen_b_epic_outcome(path: dict[int, Gear]) -> dict[str, Any]:
    """Replay the frozen B early route on this shard's existing Epic path."""
    strategy = next(item for item in strategies() if item.key == EPIC_B_KEY)
    actions: dict[tuple[Any, ...], dict[str, str]] = {}
    followup: dict[tuple[Any, ...], bool] = {}

    def signature(state: Gear) -> tuple[Any, ...]:
        return (state.slot, state.main_stat.key, state.enhance, tuple((stat.key, stat.normalized_value, stat.rolls) for stat in state.substats))

    def early(state: Gear) -> str:
        key = signature(state)
        if key not in actions:
            actions[key] = strategy_actions(state, "normal_85")
        return actions[key][EPIC_B_KEY]

    def later(state: Gear) -> bool:
        key = signature(state)
        if key not in followup:
            followup[key] = formal_followup_action(state, "normal_85")
        return followup[key]

    return _outcome_for_record(simulate_strategy_path(path, "normal_85", strategy, formal_followup=later, early_action=early))


def _terminal_unified_value(terminal: dict[str, Any], outcome: dict[str, Any], anchor: float) -> float:
    if outcome["stop_checkpoint"] != 15:
        return 0.0
    return max(
        float(terminal.get("strategy_formal_gs") or 0.0),
        terminal_one_speed_value(float(terminal.get("final_speed") or 0.0), anchor),
    )


def _empty_anchor_values() -> dict[str, float]:
    return {name: 0.0 for name in SPEED_VALUE_ANCHORS}


def _allocate_signature_draws(signatures: list[dict[str, Any]], targeted_runs: int) -> list[int]:
    """Give every mutually exclusive stratum coverage before variance allocation."""
    if targeted_runs < len(signatures):
        raise ValueError("targeted_runs must cover every mutually exclusive speed signature")
    remaining = targeted_runs - len(signatures)
    mass = sum(float(item["natural_probability"]) for item in signatures)
    shares = [remaining * float(item["natural_probability"]) / mass for item in signatures]
    draws = [1 + int(value) for value in shares]
    for index in sorted(range(len(signatures)), key=lambda number: (shares[number] % 1.0, signatures[number]["signature_id"]), reverse=True)[:remaining - sum(int(value) for value in shares)]:
        draws[index] += 1
    return draws


def freeze_v7_allocation(signatures: list[dict[str, Any]]) -> dict[str, Any]:
    """Freeze the variance-oriented v7 quota before reading any formal seed.

    v6 established the 21 exact 22+ terminal signatures.  They receive a
    fixed conditional sample quota to control their within-signature variance.
    Every remaining signature still receives two samples so failed rescue
    paths contribute their actual material, sale, and conversion costs.
    """
    strata = []
    for signature in sorted(signatures, key=lambda item: item["signature_id"]):
        positive = int(signature["terminal_speed"]) >= 22
        strata.append({
            "signature_id": signature["signature_id"],
            "terminal_speed": signature["terminal_speed"],
            "natural_probability": signature["natural_probability"],
            "allocation_class": "terminal_22_plus" if positive else "failure_cost",
            "draws": V7_POSITIVE_DRAWS_PER_SIGNATURE if positive else V7_FAILURE_DRAWS_PER_SIGNATURE,
        })
    return {
        "method": "v6_design_only_terminal_signature_variance_quota",
        "positive_draws_per_signature": V7_POSITIVE_DRAWS_PER_SIGNATURE,
        "failure_draws_per_signature": V7_FAILURE_DRAWS_PER_SIGNATURE,
        "targeted_runs": sum(item["draws"] for item in strata),
        "strata": strata,
    }


def simulate_stratified_shard(
    *, seed: int, common_runs: int, targeted_runs: int | None, initial_mode: str, sets: tuple[str, ...], rare: bool
) -> dict[str, Any]:
    """Combine a natural public pool with exact-mass, disjoint speed strata."""
    if common_runs <= 0:
        raise ValueError("common_runs must be positive")
    rng = random.Random(seed)
    baseline = _new_row()
    epic = _empty_metrics()
    epic_by_policy = {EPIC_B_KEY: _empty_metrics()}
    epic_anchor_values = {EPIC_B_KEY: _empty_anchor_values()}
    baseline_heroic_anchor_values = _empty_anchor_values()
    for _path_index in range(common_runs):
        set_code = rng.choice(sets)
        heroic_path = _enhance_path(generate_full_pool_gear(set_code, "Heroic", rng, initial_mode), rng, initial_mode)
        actions = {point: _released_action(heroic_path[point]) for point in CHECKPOINTS[:-1]}
        outcome = _run_path(heroic_path, "M0_current", "all_sets", rare, actions)
        terminal = _terminal_with_category(heroic_path[15]) if outcome["stop_checkpoint"] == 15 else {}
        _record_row(baseline, heroic_path, outcome, terminal, actions, trajectory_id=f"{seed}:common:{_path_index}")
        for name, anchor in SPEED_VALUE_ANCHORS.items():
            baseline_heroic_anchor_values[name] += _terminal_unified_value(terminal, outcome, anchor)
        epic_path = _enhance_path(generate_full_pool_gear(set_code, "Epic", rng, initial_mode), rng, initial_mode)
        epic_actions = {point: _released_action(epic_path[point]) for point in CHECKPOINTS[:-1]}
        epic_outcome = _run_path(epic_path, "M0_current", "all_sets", rare, epic_actions)
        epic_terminal = _terminal_with_category(epic_path[15])
        _record(epic, epic_path[15], epic_outcome, epic_terminal if epic_outcome["stop_checkpoint"] == 15 else {})
        b_outcome = _frozen_b_epic_outcome(epic_path)
        _record(epic_by_policy[EPIC_B_KEY], epic_path[15], b_outcome, epic_terminal if b_outcome["stop_checkpoint"] == 15 else {})
        for name, anchor in SPEED_VALUE_ANCHORS.items():
            epic_anchor_values[EPIC_B_KEY][name] += _terminal_unified_value(epic_terminal, b_outcome, anchor)
    matrix = candidate_action_equivalence_matrix()
    if matrix["witnesses"]:
        raise ValueError(f"candidate action matrix is not equivalent: {matrix['witnesses']}")
    groups = matrix["groups"]
    representatives = tuple(group["representative"] for group in groups)
    rows = {f"{candidate}/{scope}": copy.deepcopy(baseline) for candidate in representatives for scope in SCOPES}
    heroic_anchor_values = {key: dict(baseline_heroic_anchor_values) for key in rows}
    for key, row in rows.items():
        if not key.startswith("M0_current/"):
            row["raw_rescued_22_events"] = {}
            row["weighted_rescued_22_count"] = 0.0
            row["stratum_weight_sum"] = 0.0
            row["stratum_weight_square_sum"] = 0.0
            row["first_rescue_22"] = {str(point): 0 for point in (6, 9, 12)}
    signatures = speed_signature_strata(sets, initial_mode=initial_mode, rare=rare)
    allocation = freeze_v7_allocation(signatures)
    if targeted_runs is not None and targeted_runs != allocation["targeted_runs"]:
        raise ValueError("v7 uses the frozen allocation; targeted_runs must be omitted or match it")
    targeted_runs = allocation["targeted_runs"]
    allocation_by_id = {item["signature_id"]: item for item in allocation["strata"]}
    draws = [allocation_by_id[item["signature_id"]]["draws"] for item in signatures]
    strata = {
        item["signature_id"]: {
            **item, "raw_draws": 0, "rescued_success_count": 0, "rescued_failure_count": 0,
            "weighted_rescued_22": 0.0, "weighted_delta_abs": 0.0,
            "rescued_by_candidate": defaultdict(int), "candidate_contributions": defaultdict(
                lambda: {"raw_rescues": 0, "raw_22": 0, "weighted_22": 0.0, "weight_square": 0.0}
            ),
        }
        for item in signatures
    }
    design_weights: list[float] = []
    for signature, draws_for_signature in zip(signatures, draws):
        item = strata[signature["signature_id"]]
        natural_weight = common_runs * float(signature["natural_probability"]) / draws_for_signature
        for local_index in range(draws_for_signature):
            item["raw_draws"] += 1
            design_weights.append(natural_weight / common_runs)
            path, evidence = _sample_speed_signature_path(rng, signature=signature, initial_mode=initial_mode, sets=sets)
            actions = {point: _released_action(path[point]) for point in CHECKPOINTS[:-1]}
            probabilities = {point: p22_exact(path[point], rare_speed_rolls_removed=rare) for point in (6, 9, 12)}
            final_speed_stat = _speed_stat(path[15])
            final_speed = 0.0 if final_speed_stat is None else final_speed_stat.normalized_value + reforge_bonus_value("spd", final_speed_stat.rolls)
            baseline_outcome = _run_path(path, "M0_current", "all_sets", rare, actions, probabilities)
            path_terminal = _terminal_with_category(path[15])
            any_rescue = False
            for candidate in representatives:
                for scope in SCOPES:
                    key = f"{candidate}/{scope}"
                    outcome = _run_path(path, candidate, scope, rare, actions, probabilities)
                    if outcome["first_rescue_node"] is None:
                        continue
                    any_rescue = True
                    item["rescued_by_candidate"][key] += 1
                    contribution = item["candidate_contributions"][key]
                    contribution["raw_rescues"] += 1
                    if final_speed >= 22:
                        contribution["raw_22"] += 1
                        contribution["weighted_22"] += natural_weight
                        contribution["weight_square"] += natural_weight * natural_weight
                    trajectory_id = f"{seed}:signature:{signature['signature_id']}:{local_index}:{key}"
                    _record_stratified_delta(
                        rows[key], path=path, baseline=baseline_outcome, candidate=outcome, baseline_actions=actions,
                        natural_weight=natural_weight, evidence=evidence, trajectory_id=trajectory_id, terminal=path_terminal,
                    )
                    for name, anchor in SPEED_VALUE_ANCHORS.items():
                        heroic_anchor_values[key][name] += natural_weight * (
                            _terminal_unified_value(path_terminal if outcome["stop_checkpoint"] == 15 else {}, outcome, anchor)
                            - _terminal_unified_value(path_terminal if baseline_outcome["stop_checkpoint"] == 15 else {}, baseline_outcome, anchor)
                        )
            if any_rescue:
                item["weighted_delta_abs"] += natural_weight
                if final_speed >= 22:
                    item["rescued_success_count"] += 1
                    item["weighted_rescued_22"] += natural_weight
                else:
                    item["rescued_failure_count"] += 1
    return {
        "schema_version": SCHEMA_VERSION, "study": STUDY_NAME, "sampling_mode": "mutually_exclusive_speed_signature_strata",
        "seed": seed, "initial_mode": initial_mode, "sets": list(sets), "rare_speed_rolls_removed": rare,
        "common_pool": {"runs": common_runs, "sampling": "full_natural_pool"},
        "targeted_pool": {
            "runs": targeted_runs, "sampling": "exact_mass_mutually_exclusive_speed_signatures",
            "natural_mass": sum(float(item["natural_probability"]) for item in signatures), "design_weights": design_weights,
            "allocation": allocation,
        },
        "runs": common_runs, "baseline_heroic": baseline, "heroic": rows, "epic": epic,
        "epic_by_policy": epic_by_policy, "epic_anchor_values": epic_anchor_values,
        "heroic_anchor_values": heroic_anchor_values, "strata": strata,
        "candidate_action_matrix": matrix, "candidate_groups": groups,
    }


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def _shard_path(resume_dir: Path, initial_mode: str, rare: bool, seed: int) -> Path:
    probability = "rare_removed" if rare else "official"
    return resume_dir / probability / initial_mode / f"seed-{seed}.json"


def _valid(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("schema_version") == SCHEMA_VERSION and data.get("study") == STUDY_NAME
    except (OSError, ValueError):
        return False


def _ci(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [values[0] if values else 0.0, values[0] if values else 0.0]
    multiplier = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776}.get(len(values), 1.96)
    half = multiplier * stdev(values) / sqrt(len(values))
    return [mean(values) - half, mean(values) + half]


def _row_per100k(epic: dict[str, Any], heroic: dict[str, Any], runs: float) -> dict[str, Any]:
    combined, pool = _batch_row(epic, heroic["metrics"], HEROIC_PER_EPIC)
    row = _per100k(combined, pool)
    cycles = row["ledger"]["cycles"]
    row["rescue_nodes"] = {name: {point: value / runs * HEROIC_PER_EPIC * cycles for point, value in heroic[name].items()} for name in ("base_stops", "base_continues", "rescued", "rescued_then_stopped")}
    row["weighted_rescued_22_per_100k"] = heroic["weighted_rescued_22_count"] / runs * HEROIC_PER_EPIC * cycles
    row["by_source"] = {
        "normal_heroic": {
            "speed": {threshold: heroic["metrics"]["speed_bins"][str(threshold)] / runs * HEROIC_PER_EPIC * cycles for threshold in SPEED_BINS},
            "native_formal_gs": sum(heroic["metrics"]["native_formal_baili"].values()) / runs * HEROIC_PER_EPIC * cycles,
            "conversion_reachable_formal_gs": sum(heroic["metrics"]["conversion_reachable_baili"].values()) / runs * HEROIC_PER_EPIC * cycles,
            "strategy_formal_gs": sum(heroic["metrics"]["formal_baili"].values()) / runs * HEROIC_PER_EPIC * cycles,
        },
        "normal_epic": {
            "speed": {threshold: epic["speed_bins"][str(threshold)] / runs * cycles for threshold in SPEED_BINS},
            "native_formal_gs": sum(epic["native_formal_baili"].values()) / runs * cycles,
            "conversion_reachable_formal_gs": sum(epic["conversion_reachable_baili"].values()) / runs * cycles,
            "strategy_formal_gs": sum(epic["formal_baili"].values()) / runs * cycles,
        },
    }
    return row


def _b_joint_row_per100k(
    *, epic: dict[str, Any], heroic: dict[str, Any], epic_anchor_values: dict[str, float],
    heroic_anchor_values: dict[str, float], runs: float,
) -> dict[str, Any]:
    """Settle frozen B and one Heroic candidate through the same source batch."""
    row = _row_per100k(epic, heroic, runs)
    batch_stamina = float(row["pool"]["total_stamina"])
    cycles = float(row["ledger"]["cycles"])
    rates: dict[str, float] = {}
    totals: dict[str, float] = {}
    for name in SPEED_VALUE_ANCHORS:
        per_batch = (float(epic_anchor_values[name]) + HEROIC_PER_EPIC * float(heroic_anchor_values[name])) / runs
        totals[name] = per_batch * cycles
        rates[name] = 100.0 * per_batch / batch_stamina if batch_stamina else 0.0
    row["unified_terminal_value_per_100_stamina"] = rates
    row["unified_terminal_value_per_100k"] = totals
    row["epic_22_absolute_status"] = "not_estimated" if float(row["by_source"]["normal_epic"]["speed"][22]) == 0.0 else "observed_only"
    return row


def _summarize(resume_dir: Path, seeds: list[int], initial_mode: str, rare: bool) -> dict[str, Any]:
    seed_rows: dict[str, dict[str, Any]] = {}
    b_joint_per_seed: dict[str, dict[str, Any]] = {}
    keys = [f"{candidate}/{scope}" for candidate in CANDIDATES for scope in SCOPES]
    payloads: dict[str, dict[str, Any]] = {}
    for seed in seeds:
        payload = json.loads(_shard_path(resume_dir, initial_mode, rare, seed).read_text(encoding="utf-8"))
        payloads[str(seed)] = payload
        aliases = {member: group["representative"] for group in payload["candidate_groups"] for member in group["members"]}
        seed_rows[str(seed)] = {
            key: _row_per100k(payload["epic"], payload["heroic"][f"{aliases[key.split('/', 1)[0]]}/{key.split('/', 1)[1]}"], payload["runs"])
            for key in keys
        }
        b_joint_per_seed[str(seed)] = {
            key: _b_joint_row_per100k(
                epic=payload["epic_by_policy"][EPIC_B_KEY],
                heroic=payload["heroic"][f"{aliases[key.split('/', 1)[0]]}/{key.split('/', 1)[1]}"],
                epic_anchor_values=payload["epic_anchor_values"][EPIC_B_KEY],
                heroic_anchor_values=payload["heroic_anchor_values"][f"{aliases[key.split('/', 1)[0]]}/{key.split('/', 1)[1]}"],
                runs=payload["runs"],
            )
            for key in COMBINED_HEROIC_KEYS
        }
    candidates: dict[str, Any] = {}
    baseline_key = "M0_current/all_sets"
    for key in keys:
        rows = [seed_rows[str(seed)][key] for seed in seeds]
        base = [seed_rows[str(seed)][baseline_key] for seed in seeds]
        delta22 = [left["speed"][22] - right["speed"][22] for left, right in zip(rows, base)]
        gs_delta = [left["strategy_total_baili"] - right["strategy_total_baili"] for left, right in zip(rows, base)]
        raw_events: dict[str, int] = {}
        raw_weights: list[float] = []
        design_weights: list[float] = []
        nonzero_seeds = 0
        for seed in seeds:
            payload = payloads[str(seed)]
            aliases = {member: group["representative"] for group in payload["candidate_groups"] for member in group["members"]}
            candidate, scope = key.split("/", 1)
            source = payload["heroic"][f"{aliases[candidate]}/{scope}"]
            raw_events.update(source["raw_rescued_22_events"])
            events = list(source["raw_rescued_22_events"].values())
            nonzero_seeds += int(bool(events))
            raw_weights.extend(float(event.get("natural_weight", 1.0)) if isinstance(event, dict) else 1.0 for event in events)
            design_weights.extend(float(weight) for weight in payloads[str(seed)]["targeted_pool"]["design_weights"])
        mean_row = rows[0].copy()
        for name in ("speed", "ledger", "nodes", "rescue_nodes", "by_source"):
            mean_row[name] = _mean_nested([row[name] for row in rows])
        for name in ("strategy_total_baili", "native_total_baili", "conversion_reachable_total_baili", "native75", "converted75", "output60", "weighted_rescued_22_per_100k"):
            mean_row[name] = mean(float(row[name]) for row in rows)
        mean_row["event_evidence"] = _candidate_event_summary(
            raw_events=raw_events,
            weighted_rescued_22_per_100k=mean_row["weighted_rescued_22_per_100k"],
            sample_weights=raw_weights,
            design_weights=design_weights,
        )
        mean_row["event_evidence"]["nonzero_difference_seed_count"] = nonzero_seeds
        def _max_seed_share(values: list[float]) -> float:
            total = sum(abs(value) for value in values)
            return 0.0 if total <= 0 else max(abs(value) for value in values) / total
        saint_delta = [left["ledger"]["saint_stamina"] - right["ledger"]["saint_stamina"] for left, right in zip(rows, base)]
        mean_row["delta_vs_m0"] = {
            "heroic22": mean(delta22), "heroic22_interval95": _ci(delta22),
            "strategy_gs": mean(gs_delta), "strategy_gs_interval95": _ci(gs_delta),
            "max_seed_share": {
                "heroic22": _max_seed_share(delta22),
                "strategy_gs": _max_seed_share(gs_delta),
                "saint_stamina": _max_seed_share(saint_delta),
            },
            "per_added_heroic22": _marginal_per_added_22(
                {"saint_stamina": mean(row["ledger"]["saint_stamina"] for row in base), "riftslash_stamina": mean(row["ledger"]["riftslash_stamina"] for row in base), "cycles": mean(row["ledger"]["cycles"] for row in base), "strategy_gs": mean(row["strategy_total_baili"] for row in base)},
                {"saint_stamina": mean(row["ledger"]["saint_stamina"] for row in rows), "riftslash_stamina": mean(row["ledger"]["riftslash_stamina"] for row in rows), "cycles": mean(row["ledger"]["cycles"] for row in rows), "strategy_gs": mean(row["strategy_total_baili"] for row in rows)},
                added_heroic22=mean(delta22),
            ),
        }
        candidates[key] = mean_row
    b_joint_candidates: dict[str, Any] = {}
    for key in COMBINED_HEROIC_KEYS:
        rows = [b_joint_per_seed[str(seed)][key] for seed in seeds]
        baseline_rows = [b_joint_per_seed[str(seed)][baseline_key] for seed in seeds]
        mean_row = rows[0].copy()
        for name in ("speed", "ledger", "nodes", "rescue_nodes", "by_source", "unified_terminal_value_per_100_stamina", "unified_terminal_value_per_100k"):
            mean_row[name] = _mean_nested([row[name] for row in rows])
        for name in ("strategy_total_baili", "native_total_baili", "conversion_reachable_total_baili", "native75", "converted75", "output60"):
            mean_row[name] = mean(float(row[name]) for row in rows)
        heroic22_values = [row["by_source"]["normal_heroic"]["speed"][22] - base["by_source"]["normal_heroic"]["speed"][22] for row, base in zip(rows, baseline_rows)]
        mean_row["heroic22_delta_vs_m0"] = {"mean": mean(heroic22_values), "interval95": _ci(heroic22_values)}
        mean_row["delta_vs_b_m0"] = {
            "strategy_gs": mean(row["strategy_total_baili"] - base["strategy_total_baili"] for row, base in zip(rows, baseline_rows)),
            "native75": mean(row["native75"] - base["native75"] for row, base in zip(rows, baseline_rows)),
            "converted75": mean(row["converted75"] - base["converted75"] for row, base in zip(rows, baseline_rows)),
            "output60": mean(row["output60"] - base["output60"] for row, base in zip(rows, baseline_rows)),
            "saint_stamina": mean(row["ledger"]["saint_stamina"] - base["ledger"]["saint_stamina"] for row, base in zip(rows, baseline_rows)),
            "riftslash_stamina": mean(row["ledger"]["riftslash_stamina"] - base["ledger"]["riftslash_stamina"] for row, base in zip(rows, baseline_rows)),
            "source_cycles": mean(row["ledger"]["cycles"] - base["ledger"]["cycles"] for row, base in zip(rows, baseline_rows)),
        }
        b_joint_candidates[key] = mean_row
    b_joint_pairs: dict[str, dict[str, list[float]]] = {}
    for left, right in (("M2_p22_10pct/all_sets", baseline_key), ("M1_reachable_22/all_sets", baseline_key), ("M1_reachable_22/all_sets", "M2_p22_10pct/all_sets")):
        label = f"B+{left.split('/', 1)[0]} - B+{right.split('/', 1)[0]}"
        b_joint_pairs[label] = {
            anchor: _ci([
                b_joint_per_seed[str(seed)][left]["unified_terminal_value_per_100_stamina"][anchor]
                - b_joint_per_seed[str(seed)][right]["unified_terminal_value_per_100_stamina"][anchor]
                for seed in seeds
            ])
            for anchor in SPEED_VALUE_ANCHORS
        }
    return {
        "per_seed": seed_rows,
        "candidates": candidates,
        "b_joint": {"epic_policy": EPIC_B_KEY, "per_seed": b_joint_per_seed, "candidates": b_joint_candidates, "paired_intervals": b_joint_pairs},
        "stratification": {
            "strata_by_seed": {seed: payload["strata"] for seed, payload in payloads.items()},
            "common_pool_runs_by_seed": {seed: payload["common_pool"]["runs"] for seed, payload in payloads.items()},
            "targeted_pool_runs_by_seed": {seed: payload["targeted_pool"]["runs"] for seed, payload in payloads.items()},
            "allocation_by_seed": {seed: payload["targeted_pool"]["allocation"] for seed, payload in payloads.items()},
            "candidate_groups": next(iter(payloads.values()))["candidate_groups"],
        },
    }


def _mean_nested(values: list[Any]) -> Any:
    if isinstance(values[0], dict):
        return {key: _mean_nested([value[key] for value in values]) for key in values[0]}
    return mean(values) if isinstance(values[0], (int, float)) else values[0]


def run(*, resume_dir: Path, seeds: list[int], runs_per_seed: int, sets: tuple[str, ...], initial_mode: str, rare_speed_rolls_removed: bool, targeted_runs_per_seed: int | None = None) -> dict[str, Any]:
    scheduled = skipped = 0
    for seed in seeds:
        path = _shard_path(resume_dir, initial_mode, rare_speed_rolls_removed, seed)
        if _valid(path):
            skipped += 1
            continue
        _atomic_json(path, simulate_stratified_shard(seed=seed, common_runs=runs_per_seed, targeted_runs=targeted_runs_per_seed, initial_mode=initial_mode, sets=sets, rare=rare_speed_rolls_removed))
        scheduled += 1
    return {"execution": {"scheduled_shards": scheduled, "skipped_shards": skipped}, "summary": _summarize(resume_dir, seeds, initial_mode, rare_speed_rolls_removed)}


def _render(report: dict[str, Any]) -> str:
    official = report["official"]["summary"]["candidates"]
    proxy = report["initial_proxy"]["summary"]["candidates"]
    lines = [
        "# Heroic 紫装中后期 22速可达性路线研究", "",
        "本研究仅研究 `normal_85 Heroic` 非鞋已有速度副属性的 `+6/+9/+12` 救回；+0/+3、Epic、正式策略、DP、跳值表、资源默认值与前瞻批次均未修改。", "",
        "## 结论", "",
        f"- 验证闸门：`{report['gate']['status']}`。{report['gate']['reason']}",
        "- 所有候选先读取 `baili_marginal_low` 的当前二元动作；基线继续一律继续，只有基线停止且终局 P22>0 的授权 Heroic 状态才可能救回。", "",
        "- `M1_reachable_22/all_sets` 是只最大化22+件数的速度 Oracle：它救回全部 P22>0 的授权状态。它不作为发布规则，其余候选与它比较资源和正式GS代价。", "",
        "## 每十万总体力（官方强化概率主模型）", "",
        "| 候选/范围 | Heroic 22+ | 联合22+ | 距速度Oracle | 原生正式GS | 满值转换可达GS | 实际策略GS | 75+ | 转换75+ | 输出60 | 救回22有效事件 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in official.items():
        evidence = row["event_evidence"]
        lines.append(f"| {key} | {row['by_source']['normal_heroic']['speed'][22]:.3f} | {row['speed'][22]:.3f} | {row['native_total_baili']:.2f} | {row['conversion_reachable_total_baili']:.2f} | {row['strategy_total_baili']:.2f} | {row['native75']:.3f} | {row['converted75']:.3f} | {row['output60']:.3f} | {evidence['raw_unique_rescued_22_count']} | {evidence['weighted_ess']:.1f} |")
    lines.extend(["", "## 节点与账本（M0）", ""])
    m0 = official["M0_current/all_sets"]
    ledger = m0["ledger"]
    lines.append(f"- 每十万总体力：维度裂缝 {ledger['riftslash_stamina']:.1f}（{ledger['riftslash_clears']:.1f}次）、圣女3-7 {ledger['saint_stamina']:.1f}（{ledger['saint_clears']:.1f}次）、循环 {ledger['cycles']:.2f}；合计 {ledger['total_stamina']:.1f}。")
    lines.append("- Heroic基线停止：" + "；".join(f"+{point}={value:.2f}" for point, value in m0["rescue_nodes"]["base_stops"].items()) + "。")
    lines.append("- M0节点停止：" + "；".join(f"+{point}={value:.2f}" for point, value in m0["nodes"]["stopped"].items()) + "。")
    lines.extend(["", "## 候选救回与交换（相对M0）", "", "| 候选/范围 | +6救回 | +9救回 | +12救回 | Heroic22+变化（95%CI） | 实际策略GS变化（95%CI） | 每多1件22+额外总体力 |", "|---|---:|---:|---:|---:|---:|---:|"])
    for key, row in official.items():
        if key.startswith("M0_"):
            continue
        delta = row["delta_vs_m0"]
        low, high = delta["heroic22_interval95"]
        gs_low, gs_high = delta["strategy_gs_interval95"]
        stamina = delta["per_added_heroic22"]["saint_stamina_per_added_heroic22"]
        stamina_text = "不适用" if stamina is None else f"{stamina:.2f}"
        rescued = row["rescue_nodes"]["rescued"]
        lines.append(f"| {key} | {rescued['6']:.3f} | {rescued['9']:.3f} | {rescued['12']:.3f} | {delta['heroic22']:.3f} [{low:.3f}, {high:.3f}] | {delta['strategy_gs']:.2f} [{gs_low:.2f}, {gs_high:.2f}] | {stamina_text} |")
    lines.extend(["", "## 稀有端点移除敏感性", "", "| 候选/范围 | 官方22+ | 移除1速端点22+ | 差异 |", "|---|---:|---:|---:|"])
    for key, row in official.items():
        lines.append(f"| {key} | {row['speed'][22]:.3f} | {proxy[key]['speed'][22]:.3f} | {proxy[key]['speed'][22] - row['speed'][22]:.3f} |")
    lines.extend(["", "## 口径", "", "- P22为精确枚举：Heroic速度跳值 `1=0.332%，2/3/4=33.223%，无5`；+12只补第4条；+15仍是一次强化事件；重铸速度仅在终局加一次。", "- 初始值同时保存合法均匀与强化分布代理两种视图；它们是敏感性，不宣称为官方自然掉率。", "- 完整池包含无速度装备、鞋子和固定基线分支；它们共同分摊每个85体力批次一次来源成本。未使用历史51/53库存筛选比例。", "- 22速与正式GS分开报告；转换可达GS、实际承担10万金币转换成本的策略GS和原生GS各自只计一次。", ""])
    return "\n".join(lines)


def _render(report: dict[str, Any]) -> str:
    """v2 report: raw gate evidence and weighted production stay separate."""
    official = report["official"]["summary"]["candidates"]
    rare = report["rare_endpoint_removed"]["summary"]["candidates"]
    proxy = report["initial_proxy"]["summary"]["candidates"]
    lines = [
        "# Heroic 中后期 22 速差异分层研究",
        "",
        f"- 验证闸门：`{report['gate']['status']}`。{report['gate']['reason']}",
        "- M1 是可达性全救回参考（reachability_rescue），不是速度效率 Oracle，也不是发布规则。",
        "- 每十万加权产量、原始唯一事件和 ESS 分别统计；200 事件闸门只使用原始唯一事件。",
        "",
        "## 每十万总体力",
        "",
        "|候选/范围|Heroic 22+|联合 22+|原生正式 GS|满值转换可达 GS|策略 GS|原始救回22+|ESS|",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in official.items():
        evidence = row["event_evidence"]
        lines.append(f"|{key}|{row['by_source']['normal_heroic']['speed'][22]:.4f}|{row['speed'][22]:.4f}|{row['native_total_baili']:.2f}|{row['conversion_reachable_total_baili']:.2f}|{row['strategy_total_baili']:.2f}|{evidence['raw_unique_rescued_22_count']}|{evidence['weighted_ess']:.1f}|")
    lines.extend(["", "## 相对 M0 的边际变化", "", "|候选/范围|Heroic22+变化 (95% CI)|每新增1件22+圣女体力|损失裂缝体力|损失循环|策略GS变化|", "|---|---:|---:|---:|---:|---:|"])
    for key, row in official.items():
        if key.startswith("M0_"):
            continue
        delta = row["delta_vs_m0"]
        tradeoff = delta["per_added_heroic22"]
        metrics = [tradeoff[name] for name in ("saint_stamina_per_added_heroic22", "riftslash_stamina_lost_per_added_heroic22", "source_cycles_lost_per_added_heroic22", "strategy_gs_change_per_added_heroic22")]
        values = ["不适用" if value is None else f"{value:.4f}" for value in metrics]
        low, high = delta["heroic22_interval95"]
        lines.append(f"|{key}|{delta['heroic22']:.4f} [{low:.4f}, {high:.4f}]|" + "|".join(values) + "|")
    lines.extend(["", "## 概率与初始值敏感性", "", "|候选/范围|官方概率22+|移除稀有端点22+|初始跳值代理22+|", "|---|---:|---:|---:|"])
    for key, row in official.items():
        lines.append(f"|{key}|{row['speed'][22]:.4f}|{rare[key]['speed'][22]:.4f}|{proxy[key]['speed'][22]:.4f}|")
    return "\n".join(lines)


def _render_v4(report: dict[str, Any]) -> str:
    official = report["official"]["summary"]["candidates"]
    proxy = report["initial_proxy"]["summary"]["candidates"]
    rare = report["rare_endpoint_removed"]["summary"]["candidates"]
    stratification = report["official"]["summary"]["stratification"]
    lines = [
        "# Heroic 中后期 22速自然权重差异分层研究",
        "",
        f"- 闸门：`{report['gate']['status']}`。{report['gate']['reason']}",
        "- M1 仅为可达性全救回参考（reachability_rescue），未实现资源效率 Oracle。",
        "- 公共完整池保留 Epic、鞋子、无速度与 M0 全部路径的资源和正式 GS；定向层只估计救回造成的增量。",
        "",
        "## 分层抽样",
        "",
        f"- 公共池每 seed 路径数：{stratification['common_pool_runs_by_seed']}",
        f"- 定向池每 seed 路径数：{stratification['targeted_pool_runs_by_seed']}",
        "- 定向 proposal：非鞋且初始含速度，再将 +3/+6/+9 的八种速度命中模式等概率抽样；+12 第四词条和 +15 命中/跳值均保持自然抽样，故包含终局成功与失败分支。",
        "- 每个事件保存 trajectory_id、自然概率完整分解、proposal 概率及真实 importance weight；不同候选的同一底层轨迹不跨候选合并。",
        "",
        "## 官方概率主模型",
        "",
        "|候选/范围|Heroic22+/10万体力|联合22+/10万体力|原生正式GS|满值转换可达GS|实际策略GS|原始救回22|ESS|非零seed|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in official.items():
        evidence = row["event_evidence"]
        lines.append(
            f"|{key}|{row['by_source']['normal_heroic']['speed'][22]:.4f}|{row['speed'][22]:.4f}|"
            f"{row['native_total_baili']:.2f}|{row['conversion_reachable_total_baili']:.2f}|{row['strategy_total_baili']:.2f}|"
            f"{evidence['raw_unique_rescued_22_count']}|{evidence['weighted_ess']:.2f}|{evidence['nonzero_difference_seed_count']}|"
        )
    lines.extend(["", "## 初始值口径", "", "|候选/范围|合法均匀 Heroic22+|强化概率代理 Heroic22+|", "|---|---:|---:|"])
    for key, row in official.items():
        lines.append(f"|{key}|{row['by_source']['normal_heroic']['speed'][22]:.4f}|{proxy[key]['by_source']['normal_heroic']['speed'][22]:.4f}|")
    lines.extend(["", "## 稀有1速端点敏感性", "", "|候选/范围|官方Heroic22+|移除1速端点Heroic22+|", "|---|---:|---:|"])
    for key, row in official.items():
        lines.append(f"|{key}|{row['by_source']['normal_heroic']['speed'][22]:.4f}|{rare[key]['by_source']['normal_heroic']['speed'][22]:.4f}|")
    baseline = official["M0_current/all_sets"]
    lines.extend(["", "## 75+ 与输出60变化", "", "|候选/范围|原生75+变化|转换75+变化|输出60变化|", "|---|---:|---:|---:|"])
    for key, row in official.items():
        if key.startswith("M0_"):
            continue
        lines.append(f"|{key}|{row['native75'] - baseline['native75']:.4f}|{row['converted75'] - baseline['converted75']:.4f}|{row['output60'] - baseline['output60']:.4f}|")
    lines.extend(["", "## 相对M0边际变化", "", "|候选/范围|Heroic22+差值95%CI|每新增1件22+圣女体力|损失维度裂缝体力|损失循环|策略GS变化|", "|---|---:|---:|---:|---:|---:|"])
    for key, row in official.items():
        if key.startswith("M0_"):
            continue
        delta = row["delta_vs_m0"]
        tradeoff = delta["per_added_heroic22"]
        low, high = delta["heroic22_interval95"]
        values = [tradeoff[name] for name in ("saint_stamina_per_added_heroic22", "riftslash_stamina_lost_per_added_heroic22", "source_cycles_lost_per_added_heroic22", "strategy_gs_change_per_added_heroic22")]
        text = ["不适用" if value is None else f"{value:.4f}" for value in values]
        lines.append(f"|{key}|{delta['heroic22']:.4f} [{low:.4f}, {high:.4f}]|" + "|".join(text) + "|")
    return "\n".join(lines) + "\n"


def _render_v7(report: dict[str, Any]) -> str:
    summary = report["official"]["summary"]
    combined = summary["b_joint"]
    rows = combined["candidates"]
    baseline_key = "M0_current/all_sets"
    baseline = rows[baseline_key]

    def interval(left: str, right: str, field) -> list[float]:
        return _ci([field(combined["per_seed"][str(seed)][left]) - field(combined["per_seed"][str(seed)][right]) for seed in report["seeds"]])

    choices = (
        ("维持当前", baseline_key, "M0"),
        ("均衡档", "M2_p22_10pct/all_sets", "P22 >= 10%"),
        ("激进档", "M1_reachable_22/all_sets", "P22 > 0"),
    )
    lines = [
        "# Heroic 中后期 22 速 v7 人工确认准备",
        "",
        "本报告的分母固定为每 `100,000` 总体力：维度裂缝的一次红紫联合产出，加上圣女3-7补足同一批次的金币与强化经验。正式策略、跳值表、lambda、评分、DP、GUI 和前瞻批次均未修改。",
        "",
        f"## 离线闸门\n\n- 状态：`{report['gate']['status']}`。{report['gate']['reason']}",
        "- 当前统计通过只表示可以进行人工确认，不表示策略已经发布。22速优先级单列，不折算进正式体系百里分。",
        "",
        "## 红紫联合绝对基线（B + Heroic M0）",
        "",
        f"- 维度裂缝：`{baseline['ledger']['riftslash_stamina']:.3f}` 体力 / `{baseline['ledger']['riftslash_clears']:.3f}` 次；圣女3-7：`{baseline['ledger']['saint_stamina']:.3f}` 体力 / `{baseline['ledger']['saint_clears']:.3f}` 次；来源循环：`{baseline['ledger']['cycles']:.6f}`。",
        f"- 期望装备：Epic `{baseline['ledger']['expected_epic']:.3f}` 件、Heroic `{baseline['ledger']['expected_heroic']:.3f}` 件；红紫联合策略GS `{baseline['strategy_total_baili']:.6f}`、原生75+ `{baseline['native75']:.6f}`、转换75+ `{baseline['converted75']:.6f}`、输出60 `{baseline['output60']:.6f}`。",
        "- Epic 公共池在本轮未观测到22+，因此红紫联合绝对22+为 `not_estimated`；下表只显示紫装候选相对M0新增的22+，绝不把它写成联合绝对产量。",
        "",
        "## 三档人工确认对比",
        "",
        "|档位|候选|统一终局价值/100体力（curve_baseline）|紫装22+新增/10万总体力（95% CI）|联合策略GS变化|原生75+变化|转换75+变化|输出60变化|维度裂缝/圣女体力|来源循环变化|",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, key, candidate in choices:
        row = rows[key]
        delta = row["delta_vs_b_m0"]
        hero = row["heroic22_delta_vs_m0"]
        lines.append(
            f"|{label}|B + {candidate}|{row['unified_terminal_value_per_100_stamina']['curve_baseline']:.6f}|"
            f"{hero['mean']:.6f} [{hero['interval95'][0]:.6f}, {hero['interval95'][1]:.6f}]|"
            f"{delta['strategy_gs']:.6f}|{delta['native75']:.6f}|{delta['converted75']:.6f}|{delta['output60']:.6f}|"
            f"{row['ledger']['riftslash_stamina']:.3f} / {row['ledger']['saint_stamina']:.3f}|{delta['source_cycles']:.6f}|"
        )
    lines.extend([
        "",
        "均衡档仅救回终局22+概率至少10%的状态；激进档救回任何仍可达到22+的状态。此处不替用户选择，人工确认只能在三档中选择其一。",
        "",
        "## 同池统一终局价值成对区间",
        "",
        "B早期筛选和Heroic中后期救回在同一条Epic公共轨迹、同一Heroic公共池、同一显式资源池上结算。以下为每100体力的逐seed成对95%区间：",
        "",
        "|成对比较|curve_baseline|第二档低|第二档中|第二档高|",
        "|---|---:|---:|---:|---:|",
    ])
    for pair, anchors in combined["paired_intervals"].items():
        lines.append("|" + pair + "|" + "|".join(f"[{anchors[name][0]:.6f}, {anchors[name][1]:.6f}]" for name in SPEED_VALUE_ANCHORS) + "|")
    lines.extend([
        "",
        "## 分层与可追溯性",
        "",
        "- Heroic差异层使用2,500个互斥速度签名；每个签名的成功与失败成本均按精确自然质量汇总。",
        "- B固定为 `B_global_current_gs`，未改动其规则；M0、M2、M1共享同一来源、轨迹和资源账本。",
        "- 原始事件、ESS、每签名质量和逐seed原始结果保存在同名JSON中；v3--v6分片未读取。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Heroic midgame 22-speed rescue research")
    parser.add_argument("--sets", default="set_speed,set_cri,set_att,set_max_hp")
    parser.add_argument("--seeds", default="20260724,20260725,20260726,20260727,20260728")
    parser.add_argument("--runs-per-seed", type=int, default=128)
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "heroic_midgame_speed22_v7_formal_resume_20260714")
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "heroic_midgame_speed22_v7_formal_20260714.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "heroic_midgame_speed22_v7_formal_20260714.md")
    args = parser.parse_args()
    sets = tuple(value.strip() for value in args.sets.split(",") if value.strip())
    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    if not sets or len(seeds) != len(set(seeds)) or any(value not in SET_CODE_TO_NAME for value in sets):
        raise ValueError("invalid sets or duplicate seeds")
    action_matrix = candidate_action_equivalence_matrix()
    if action_matrix["witnesses"]:
        raise ValueError(f"cannot freeze v7 allocation: {action_matrix['witnesses']}")
    official = run(resume_dir=args.resume_dir, seeds=seeds, runs_per_seed=args.runs_per_seed, targeted_runs_per_seed=None, sets=sets, initial_mode="legacy_initial_uniform", rare_speed_rolls_removed=False)
    rare_removed = run(resume_dir=args.resume_dir, seeds=seeds, runs_per_seed=args.runs_per_seed, targeted_runs_per_seed=None, sets=sets, initial_mode="legacy_initial_uniform", rare_speed_rolls_removed=True)
    initial_proxy = run(resume_dir=args.resume_dir, seeds=seeds, runs_per_seed=args.runs_per_seed, targeted_runs_per_seed=None, sets=sets, initial_mode="roll_distribution_as_initial_proxy", rare_speed_rolls_removed=False)
    def passes_gate(row: dict[str, Any]) -> bool:
        evidence = row["event_evidence"]
        interval = row["delta_vs_m0"]["heroic22_interval95"]
        return (
            evidence["raw_unique_rescued_22_count"] >= 200
            and evidence["positive_contribution_ess"] >= 100
            and evidence["nonzero_difference_seed_count"] >= 5
            and len(interval) == 2
            and evidence["max_single_contribution_share"] <= 0.05
            and (interval[0] > 0.0 or interval[1] < 0.0)
            and all(value <= 0.5 for value in row["delta_vs_m0"]["max_seed_share"].values())
        )
    representatives = {group["representative"] for group in action_matrix["groups"]}
    eligible = [key for key, row in official["summary"]["candidates"].items() if key.split("/", 1)[0] in representatives - {"M0_current"} and passes_gate(row) and passes_gate(initial_proxy["summary"]["candidates"][key])]
    gate = {"status": "offline_gate_not_met" if not eligible else "offline_statistical_gate_passed_pending_full_suite", "eligible_candidates": eligible, "reason": "Each initial-value model independently requires >=200 candidate-specific raw rescued Heroic22 events, positive-contribution ESS>=100, >=5 nonzero seeds, a paired 95% interval excluding zero, max single contribution <=5%, and no resource/GS/22+ single-seed dominance. A successful full test suite is still required before human confirmation; this offline result cannot publish a strategy or prospective batch."}
    report = {"schema_version": SCHEMA_VERSION, "study": STUDY_NAME, "sets": sets, "seeds": seeds, "runs_per_seed": args.runs_per_seed, "targeted_runs_per_seed": None, "official": official, "rare_endpoint_removed": rare_removed, "initial_proxy": initial_proxy, "action_matrix": action_matrix, "gate": gate, "old_shards": "v3_v4_v5_v6_v7_not_read", "scope": "normal_85 Heroic midgame rescue; Epic frozen; B is replayed only for same-pool human confirmation"}
    _atomic_json(args.json_output, report)
    args.markdown_output.write_text(_render_v7(report), encoding="utf-8")


if __name__ == "__main__":
    main()
