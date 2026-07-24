"""Offline normal_85 Heroic +0 speed-threshold study.

This is intentionally isolated from released policy.  It evaluates the full
Epic/Heroic riftslash batch, including non-speed gear and boots, and reports
the separate 22-speed and formal-category outcomes per 100,000 total stamina.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from dataclasses import replace
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.calibration import candidate_policies, should_continue
from src.e7_enhance.enhance_simulator import (
    CHECKPOINTS, RANDOM_SLOTS, STAT_POOL, STAT_TYPE_BY_KEY, RollProfile,
    clone_gear, is_new_substat_event, reforge_gear, roll_range,
)
from src.e7_enhance.models import Gear, RollHit, Stat, SLOT_FORBIDDEN_SUBSTAT_KEYS
from src.e7_enhance.resource_model import calibration_for_rank
from src.e7_enhance.rules import SET_CODE_TO_NAME
from src.e7_enhance.score_engine import evaluate_gear, full_category_diagnostics, official_score_for_stats, speed_value
from src.e7_enhance.modification_values import modification_max_value
from tools.epic_non_speed_early_policy_pareto import (
    _gear_after_max_conversion, _terminal_metrics,
)
from tools.external_threshold_strategy import output_effective_gs, terminal_indicators
from tools.research_riftslash_saint_pool import FLOW_FIELDS, _empty_flow, _flow_for_outcome, explicit_batch_resource_pool
from tools.speed_priority_rolls import sample_speed_roll, speed_roll_distribution


SCHEMA_VERSION = 2
HEROIC_PER_EPIC = 85.0 / 23.81
TWO_PIECE_SETS = frozenset({
    "set_cri", "set_max_hp", "set_def", "set_immune", "set_penetrate",
    "set_torrent", "set_acc", "set_res",
})
PRIMARY_ELIGIBLE_SETS = TWO_PIECE_SETS | {"set_speed"}
SPEED_BINS = (22, 23, 24, 25, 27)
FORMAL_CATEGORIES = ("输出", "输出(必爆)", "抗坦", "纯肉", "命坦", "双效", "半肉(血防)", "半肉(通用)", "半肉(白字)")
CANDIDATES = {
    "H4_current": {"threshold": 4, "scope": "all"},
    "H3_speed_2pc": {"threshold": 3, "scope": "primary"},
    "H2_speed_2pc": {"threshold": 2, "scope": "primary"},
    "H3_all_sets": {"threshold": 3, "scope": "all"},
    "H2_all_sets": {"threshold": 2, "scope": "all"},
    "H3_speed_2pc_debuff_sensitivity": {"threshold": 3, "scope": "primary_debuff"},
    "H2_speed_2pc_debuff_sensitivity": {"threshold": 2, "scope": "primary_debuff"},
}

# The official table describes reinforcement events, not starting values.  The
# proxy mode deliberately labels it as a sensitivity rather than evidence.
OFFICIAL_ROLL_DISTRIBUTIONS = {
    "atkFlat": tuple((value, 0.05662 if value in {33, 46} else 0.07353) for value in range(33, 47)),
    "defFlat": tuple((value, 0.00143 if value == 35 else 0.14265) for value in range(28, 36)),
    "hpFlat": tuple((value, 0.01133 if value in {157, 202} else 0.02221) for value in range(157, 203)),
    "atkPct": tuple((value, 0.2) for value in range(4, 9)),
    "defPct": tuple((value, 0.2) for value in range(4, 9)),
    "hpPct": tuple((value, 0.2) for value in range(4, 9)),
    "eff": tuple((value, 0.2) for value in range(4, 9)),
    "res": tuple((value, 0.2) for value in range(4, 9)),
    "crit": tuple((value, 1 / 3) for value in range(3, 6)),
    "cdmg": tuple((value, 0.25) for value in range(4, 8)),
}


def _speed_stat(gear: Gear) -> Stat | None:
    return next((stat for stat in gear.substats if stat.key == "spd"), None)


def _last_hit_speed(gear: Gear, checkpoint: int) -> bool:
    return bool(gear.roll_history and gear.roll_history[-1].enhance == checkpoint and gear.roll_history[-1].key == "spd")


def _candidate_applies(candidate: str, set_code: str) -> bool:
    scope = CANDIDATES[candidate]["scope"]
    if scope == "all":
        return True
    if scope == "primary":
        return set_code in PRIMARY_ELIGIBLE_SETS
    return set_code in PRIMARY_ELIGIBLE_SETS or set_code == "set_debuff"


def candidate_action(candidate: str, gear: Gear) -> str:
    """Only override the authorized Heroic +0 two/three-speed strata."""
    speed = _speed_stat(gear)
    if candidate == "H4_current" or gear.rank != "Heroic" or gear.slot == "boot" or speed is None:
        return "released"
    if gear.enhance == 0:
        if (
            _candidate_applies(candidate, gear.set)
            and speed.normalized_value in {2, 3}
            and speed.normalized_value >= CANDIDATES[candidate]["threshold"]
        ):
            return "continue"
        return "released"
    return "released"


def _sample_discrete(rng: random.Random, distribution: tuple[tuple[int, float], ...]) -> int:
    threshold = rng.random()
    cumulative = 0.0
    for value, probability in distribution:
        cumulative += probability
        if threshold < cumulative:
            return value
    return distribution[-1][0]


def _initial_value(rng: random.Random, key: str, rank: str, initial_mode: str) -> int:
    if initial_mode == "legacy_initial_uniform":
        if key == "spd":
            return rng.randint(1, 4) if rank == "Heroic" else rng.randint(2, 5)
        low, high = roll_range(RollProfile(85, rank, "normal_85"), key)
        return rng.randint(low, high)
    if initial_mode == "roll_distribution_as_initial_proxy":
        if key == "spd":
            return _sample_discrete(rng, speed_roll_distribution("normal_85", rank))
        return _sample_discrete(rng, OFFICIAL_ROLL_DISTRIBUTIONS[key])
    raise ValueError(f"unknown initial mode: {initial_mode}")


def generate_full_pool_gear(set_code: str, rank: str, rng: random.Random, initial_mode: str) -> Gear:
    """Draw one legal normal-85 gear without conditioning on speed or slot."""
    if set_code not in SET_CODE_TO_NAME or rank not in {"Epic", "Heroic"}:
        raise ValueError("unsupported conditional set or rank")
    slot = rng.choice(RANDOM_SLOTS)
    main_keys = {
        "weapon": ("atkFlat",), "helm": ("hpFlat",), "armor": ("defFlat",),
        "neck": ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "crit", "cdmg"),
        "ring": ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "eff", "res"),
        "boot": ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "spd"),
    }[slot]
    main_key = rng.choice(main_keys)
    forbidden = set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(slot, set())) | {main_key}
    available = [key for key in STAT_POOL if key not in forbidden]
    sub_keys = rng.sample(available, 4 if rank == "Epic" else 3)
    return Gear(
        set=set_code, slot=slot, main_stat=Stat(STAT_TYPE_BY_KEY[main_key], 0),
        enhance=0, level=85, rank=rank,
        substats=[Stat(STAT_TYPE_BY_KEY[key], _initial_value(rng, key, rank, initial_mode), rolls=1) for key in sub_keys],
        code=f"full-pool:{set_code}:{rank}", reforge_eligible=True, roll_level=85,
    )


def full_pool_coverage(set_code: str, *, count: int, seed: int, initial_mode: str) -> dict[str, int]:
    rng = random.Random(seed)
    result = {"Epic": 0, "Heroic": 0, "boots": 0, "without_speed": 0}
    for rank in ("Epic", "Heroic"):
        for _ in range(count):
            gear = generate_full_pool_gear(set_code, rank, rng, initial_mode)
            result[rank] += 1
            result["boots"] += int(gear.slot == "boot")
            result["without_speed"] += int(_speed_stat(gear) is None)
    return result


def _roll_value(rng: random.Random, key: str, rank: str) -> int:
    if key == "spd":
        return sample_speed_roll(rng, "normal_85", rank)
    return _sample_discrete(rng, OFFICIAL_ROLL_DISTRIBUTIONS[key])


def _enhance_path(gear: Gear, rng: random.Random, initial_mode: str) -> dict[int, Gear]:
    current = clone_gear(gear)
    path = {0: current}
    for checkpoint in CHECKPOINTS[1:]:
        if is_new_substat_event(current.rank, checkpoint) and len(current.substats) < 4:
            existing = {stat.key for stat in current.substats} | {current.main_stat.key} | set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(current.slot, set()))
            key = rng.choice([key for key in STAT_POOL if key not in existing])
            current = replace(current, enhance=checkpoint, substats=current.substats + [Stat(STAT_TYPE_BY_KEY[key], _initial_value(rng, key, current.rank, initial_mode), rolls=1)])
        else:
            index = rng.randrange(len(current.substats))
            stat = current.substats[index]
            updated = replace(stat, value=stat.normalized_value + _roll_value(rng, stat.key, current.rank), rolls=stat.rolls + 1)
            substats = list(current.substats)
            substats[index] = updated
            current = replace(current, enhance=checkpoint, substats=substats, roll_history=current.roll_history + [RollHit(checkpoint, updated.type, updated.normalized_value - stat.normalized_value)])
        path[checkpoint] = current
    return path


def _heroic_base_fallback(gear: Gear) -> bool:
    """The published no-lambda Heroic fallback, kept separate from UI wording."""
    policy = next(policy for policy in candidate_policies() if policy.name == "baili_marginal_low")
    return bool(should_continue(gear, policy, "normal_85"))


def _released_action(gear: Gear) -> str:
    """Use released decision semantics without inventing an unpublished lambda."""
    if gear.rank == "Heroic" and gear.enhance >= 6:
        return "continue" if _heroic_base_fallback(gear) else "stop"
    # Epic intentionally keeps the configured DP default. Heroic +0/+3 keeps
    # its released lightweight route; `cautious_continue` means advance to the
    # next review node only, never that every future node is accepted.
    kwargs: dict[str, Any] = {"item_source": "normal_85"}
    if gear.rank == "Heroic":
        kwargs["enable_dp_assist"] = False
    recommendation = advise_gear(gear, **kwargs)["summary"]["recommendation"]
    return "continue" if recommendation in {"continue", "cautious_continue"} else "stop"


def _run_path(path: dict[int, Gear], candidate: str) -> dict[str, Any]:
    current = 0
    reached = [0]
    actions: dict[int, str] = {}
    while current < 15:
        state = path[current]
        action = "released" if candidate == "__released__" else candidate_action(candidate, state)
        if action == "released":
            action = _released_action(state)
        actions[current] = action
        if action == "stop":
            break
        current = next(point for point in CHECKPOINTS if point > current)
        reached.append(current)
    # `_flow_for_outcome` retains this legacy field for diagnostics only; the
    # explicit joint resource pool below settles the authoritative cost.
    return {"start_checkpoint": 0, "stop_checkpoint": current, "reached": reached, "actions": actions, "net_stamina": 0.0}


def _matrix_path(initial_speed: int, set_code: str, slot: str, hit_speed: bool, increment: int, fallback: str) -> dict[int, Gear]:
    main = "spd" if slot == "boot" else "atkFlat"
    supporting = [Stat("AttackPercent", 8 if fallback == "continue" else 4, rolls=1), Stat("CriticalHitChancePercent", 5 if fallback == "continue" else 3, rolls=1)]
    if fallback == "stop":
        supporting = [Stat("EffectivenessPercent", 4, rolls=1), Stat("EffectResistancePercent", 4, rolls=1)]
    speed = Stat("Speed", initial_speed, rolls=1)
    substats = [speed, *supporting] if slot != "boot" else [*supporting, Stat("HealthPercent", 4, rolls=1)]
    base = Gear(set_code, slot, Stat(STAT_TYPE_BY_KEY[main], 0), enhance=0, rank="Heroic", level=85, substats=substats, reforge_eligible=True)
    path = {0: base}
    current = base
    for checkpoint in (3, 6, 9, 12, 15):
        stats = list(current.substats)
        history = list(current.roll_history)
        if checkpoint == 3:
            if hit_speed and slot != "boot":
                stats[0] = replace(stats[0], value=stats[0].normalized_value + increment, rolls=2)
                history.append(RollHit(3, "Speed", increment))
            else:
                stats[1] = replace(stats[1], value=stats[1].normalized_value + increment, rolls=2)
                history.append(RollHit(3, stats[1].type, increment))
        current = replace(current, enhance=checkpoint, substats=stats, roll_history=history)
        path[checkpoint] = current
    return path


def action_equivalence_matrix() -> list[dict[str, Any]]:
    """Enumerate the policy-facing Heroic speed states without random rolls."""
    rows: list[dict[str, Any]] = []
    candidates = ("H4_current", "H3_speed_2pc", "H2_speed_2pc", "H3_all_sets", "H2_all_sets")
    for speed in (1, 2, 3, 4):
        for set_code in ("set_speed", "set_cri", "set_att", "set_debuff"):
            for slot in ("weapon", "boot"):
                for hit_speed in (False, True):
                    for increment in (1, 2, 3, 4):
                        for fallback in ("continue", "stop"):
                            path = _matrix_path(speed, set_code, slot, hit_speed, increment, fallback)
                            state_id = f"s{speed}:{set_code}:{slot}:hit{int(hit_speed)}:r{increment}:{fallback}"
                            for candidate in candidates:
                                override = candidate_action(candidate, path[0])
                                label = "continue" if override == "continue" else advise_gear(path[0], item_source="normal_85", enable_dp_assist=False)["summary"]["recommendation"]
                                outcome = _run_path(path, candidate)
                                rows.append({
                                    "state_id": state_id, "candidate": candidate,
                                    "speed_route_label": "research_override" if override == "continue" else "released",
                                    "label": label,
                                    "binary_actions": ["enhance" if outcome["actions"][point] == "continue" else "stop" for point in sorted(outcome["actions"])],
                                    "stop_checkpoint": outcome["stop_checkpoint"],
                                })
    return rows


def terminal_bucket(terminal: dict[str, Any]) -> dict[str, Any]:
    """Choose native OR conversion once; a conversion never creates a second item."""
    if terminal.get("formal"):
        value, mode = float(terminal.get("formal_value") or 0), "native"
    elif terminal.get("conversion"):
        value, mode = float(terminal.get("converted_formal_value") or 0), "converted"
    else:
        value, mode = 0.0, "unmatched"
    return {"formal_piece_count": int(value > 0), "total_baili": value, "mode": mode}


def action_equivalence_gate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Close the threshold study when candidates only rename the same actions."""
    by_state: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    labels: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_state[str(row["state_id"])].add(tuple(row["binary_actions"]))
        labels[str(row["state_id"])].add(str(row["label"]))
    differences = [state for state, actions in by_state.items() if len(actions) > 1]
    label_only = [state for state in by_state if len(by_state[state]) == 1 and len(labels[state]) > 1]
    status = "binary_action_difference_found" if differences else "no_binary_action_difference_under_current_policy"
    return {
        "status": status,
        "binary_difference_states": differences,
        "label_only_difference_states": label_only,
        "schedule_rare_event_expansion": bool(differences),
    }


def terminal_formal_gs(final: Gear, *, strategy_terminal: dict[str, Any] | None = None) -> dict[str, Any]:
    """Separate native, best legal mod-reachable, and paid strategy formal GS."""
    native = evaluate_gear(final)
    native_gs = float(native.retention.score) if native.retention.rule_matched else 0.0
    best_gs = native_gs
    best_category = native.retention.category if native.retention.rule_matched else None
    existing = {stat.key for stat in final.substats} | {final.main_stat.key}
    forbidden = set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(final.slot, set()))
    for source_index, source in enumerate(final.substats):
        if not 0 < source.rolls <= 2:
            continue
        for target_key in STAT_POOL:
            if target_key in existing or target_key in forbidden:
                continue
            converted = list(final.substats)
            converted[source_index] = Stat(STAT_TYPE_BY_KEY[target_key], modification_max_value(target_key, source.rolls), rolls=source.rolls)
            evaluation = evaluate_gear(replace(final, substats=converted))
            if evaluation.retention.rule_matched and float(evaluation.retention.score) > best_gs:
                best_gs = float(evaluation.retention.score)
                best_category = evaluation.retention.category
    strategy_gs = native_gs
    strategy_conversion_gold = 0.0
    if strategy_terminal and strategy_terminal.get("conversion"):
        strategy_gs = float(strategy_terminal.get("converted_formal_value") or 0.0)
        strategy_conversion_gold = 100000.0 if strategy_terminal.get("conversion_needed") else 0.0
    return {
        "native_formal_gs": native_gs,
        "conversion_reachable_formal_gs": best_gs,
        "conversion_reachable_category": best_category,
        "strategy_formal_gs": strategy_gs,
        "strategy_conversion_gold": strategy_conversion_gold,
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "paths": 0.0, "flow": _empty_flow(), "reached": {str(point): 0.0 for point in CHECKPOINTS},
        "stopped": {str(point): 0.0 for point in CHECKPOINTS},
        "speed_bins": {str(point): 0.0 for point in SPEED_BINS},
        "speed_by_group": {group: {str(point): 0.0 for point in SPEED_BINS} for group in ("speed_set", "two_piece", "other")},
        "formal_baili": {category: 0.0 for category in FORMAL_CATEGORIES},
        "formal_pieces": {category: 0.0 for category in FORMAL_CATEGORIES},
        "native_formal_baili": {category: 0.0 for category in FORMAL_CATEGORIES},
        "conversion_reachable_baili": {category: 0.0 for category in FORMAL_CATEGORIES},
        "unmatched": 0.0, "native75": 0.0, "converted75": 0.0, "output60": 0.0,
    }


def _set_group(set_code: str) -> str:
    return "speed_set" if set_code == "set_speed" else "two_piece" if set_code in TWO_PIECE_SETS else "other"


def _record(metrics: dict[str, Any], gear: Gear, outcome: dict[str, Any], terminal: dict[str, Any]) -> None:
    metrics["paths"] += 1
    for point in outcome["reached"]:
        metrics["reached"][str(point)] += 1
    stop = outcome["stop_checkpoint"]
    metrics["stopped"][str(stop)] += 1
    if stop != 15:
        flow = _flow_for_outcome(gear, outcome, False, {})
    else:
        flow = _flow_for_outcome(gear, outcome, bool(terminal.get("conversion_needed")), terminal)
        final = reforge_gear(gear)  # overwritten immediately below by path terminal in caller
    for field in FLOW_FIELDS:
        metrics["flow"][field] += flow[field]
    if stop != 15:
        return
    final = terminal["final_gear"]
    speed = speed_value(final) if final.slot != "boot" else 0.0
    group = _set_group(final.set)
    for threshold in SPEED_BINS:
        if speed >= threshold:
            metrics["speed_bins"][str(threshold)] += 1
            metrics["speed_by_group"][group][str(threshold)] += 1
    bucket = terminal_bucket(terminal)
    native_category = terminal.get("native_category")
    converted_category = terminal.get("converted_category")
    if terminal["native_formal_gs"] > 0 and native_category in FORMAL_CATEGORIES:
        metrics["native_formal_baili"][native_category] += terminal["native_formal_gs"]
    if terminal["conversion_reachable_formal_gs"] > 0 and converted_category in FORMAL_CATEGORIES:
        metrics["conversion_reachable_baili"][converted_category] += terminal["conversion_reachable_formal_gs"]
    category = native_category if bucket["mode"] == "native" else converted_category
    if bucket["formal_piece_count"] and category in FORMAL_CATEGORIES:
        metrics["formal_pieces"][category] += 1
        metrics["formal_baili"][category] += bucket["total_baili"]
    else:
        metrics["unmatched"] += 1
    indicators = terminal_indicators(
        native_total_gs=float(terminal["official_substat_gs"]),
        converted_total_gs=float(terminal["converted_official_substat_gs"]), speed=speed,
        output_gs=output_effective_gs(final),
    )
    metrics["native75"] += indicators["native_heirloom"]
    metrics["converted75"] += indicators["converted_heirloom"]
    metrics["output60"] += indicators["output60"]


def _terminal_with_category(final_85: Gear) -> dict[str, Any]:
    terminal = _terminal_metrics(final_85, "normal_85")
    final = reforge_gear(final_85)
    evaluation = evaluate_gear(final)
    gs = terminal_formal_gs(final, strategy_terminal=terminal)
    terminal.update(gs)
    native_category = evaluation.retention.category if gs["native_formal_gs"] > 0 else None
    converted_category = gs["conversion_reachable_category"]
    terminal["native_category"] = native_category if native_category in FORMAL_CATEGORIES else None
    terminal["converted_category"] = converted_category if converted_category in FORMAL_CATEGORIES else None
    terminal["unclassified_warning"] = bool(
        (terminal.get("formal") and terminal["native_category"] is None)
        or (terminal.get("conversion") and terminal["converted_category"] is None)
    )
    terminal["final_gear"] = final
    return terminal


def _merge(target: dict[str, Any], source: dict[str, Any], weight: float = 1.0) -> None:
    target["paths"] += source["paths"] * weight
    for field in FLOW_FIELDS:
        target["flow"][field] += source["flow"][field] * weight
    for name in ("reached", "stopped", "speed_bins", "formal_baili", "formal_pieces", "native_formal_baili", "conversion_reachable_baili"):
        for key, value in source[name].items():
            target[name][key] += value * weight
    for group, bins in source["speed_by_group"].items():
        for key, value in bins.items():
            target["speed_by_group"][group][key] += value * weight
    for name in ("unmatched", "native75", "converted75", "output60"):
        target[name] += source[name] * weight


def _shard(set_code: str, seed: int, runs: int, initial_mode: str) -> dict[str, Any]:
    rng = random.Random(seed)
    rows = {candidate: {"Epic": _empty_metrics(), "Heroic": _empty_metrics()} for candidate in CANDIDATES}
    for _ in range(runs):
        for rank in ("Epic", "Heroic"):
            base = generate_full_pool_gear(set_code, rank, rng, initial_mode)
            path = _enhance_path(base, rng, initial_mode)
            terminal = _terminal_with_category(path[15])
            released = _run_path(path, "__released__")
            for candidate in CANDIDATES:
                # Epic is intentionally frozen.  Most Heroic full-pool draws
                # are also unchanged (no speed, boots, or non-eligible set).
                if rank == "Epic" or candidate_action(candidate, path[0]) == "released":
                    outcome = released
                else:
                    outcome = _run_path(path, candidate)
                _record(rows[candidate][rank], path[15], outcome, terminal)
    return {"schema_version": SCHEMA_VERSION, "set_code": set_code, "seed": seed, "runs": runs, "initial_mode": initial_mode, "rows": rows}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _shard_path(resume: Path, set_code: str, initial_mode: str, seed: int) -> Path:
    return resume / initial_mode / set_code / f"seed-{seed}.json"


def _valid(path: Path) -> bool:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("schema_version") == SCHEMA_VERSION
    except (OSError, ValueError):
        return False


def per_100k_ledger(pool: dict[str, float]) -> dict[str, float]:
    cycle_total = 85.0 + float(pool["saint_supplement_stamina"])
    cycles = 100000.0 / cycle_total
    riftslash = cycles * 85.0
    saint = cycles * float(pool["saint_supplement_stamina"])
    return {
        "cycles": cycles, "riftslash_stamina": riftslash, "saint_stamina": saint,
        "total_stamina": riftslash + saint, "riftslash_clears": riftslash / 40.0,
        "saint_clears": saint / 8.0, "source_gold_batches": cycles,
        "source_lower_stone_batches": cycles,
        "expected_epic": cycles, "expected_heroic": cycles * HEROIC_PER_EPIC,
    }


def _batch_row(epic: dict[str, Any], heroic: dict[str, Any], heroic_yield: float = HEROIC_PER_EPIC) -> tuple[dict[str, Any], dict[str, float]]:
    combined = _empty_metrics()
    _merge(combined, epic, 1 / max(1.0, epic["paths"]))
    _merge(combined, heroic, heroic_yield / max(1.0, heroic["paths"]))
    flow = combined["flow"]
    pool = explicit_batch_resource_pool(
        source_gold=127500.0, source_lower_stones=0.425,
        powder_base_exp=flow["powder_units"] * 100, lower_stone_units=flow["lower_stone_units"],
        material_gold=flow["material_gold"], conversion_gold=flow["conversion_gold"],
        sell_gold=flow["sell_gold"], sell_exp=flow["sell_exp_adjusted"],
        material_scarcity_exp=flow["material_exp_adjusted"], lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
    )
    return combined, pool


def _per100k(metrics: dict[str, Any], pool: dict[str, float]) -> dict[str, Any]:
    ledger = per_100k_ledger(pool)
    factor = ledger["cycles"]
    formal = {category: metrics["formal_baili"][category] * factor for category in FORMAL_CATEGORIES}
    native_formal = {category: metrics["native_formal_baili"][category] * factor for category in FORMAL_CATEGORIES}
    conversion_reachable = {category: metrics["conversion_reachable_baili"][category] * factor for category in FORMAL_CATEGORIES}
    return {
        "ledger": ledger,
        "speed": {threshold: metrics["speed_bins"][str(threshold)] * factor for threshold in SPEED_BINS},
        "speed_by_group": {group: {threshold: bins[str(threshold)] * factor for threshold in SPEED_BINS} for group, bins in metrics["speed_by_group"].items()},
        "formal_baili": formal, "strategy_total_baili": sum(formal.values()), "total_baili": sum(formal.values()),
        "native_formal_baili": native_formal, "native_total_baili": sum(native_formal.values()),
        "conversion_reachable_baili": conversion_reachable, "conversion_reachable_total_baili": sum(conversion_reachable.values()),
        "formal_pieces": {category: metrics["formal_pieces"][category] * factor for category in FORMAL_CATEGORIES},
        "native75": metrics["native75"] * factor, "converted75": metrics["converted75"] * factor,
        "output60": metrics["output60"] * factor,
        "nodes": {"reached": {point: value * factor for point, value in metrics["reached"].items()}, "stopped": {point: value * factor for point, value in metrics["stopped"].items()}},
        "pool": pool,
    }


def _source_component_per100k(metrics: dict[str, Any], *, factor: float) -> dict[str, Any]:
    """A rank-only component; it shares the joint batch denominator above."""
    formal = {category: metrics["formal_baili"][category] / max(1.0, metrics["paths"]) * factor for category in FORMAL_CATEGORIES}
    return {
        "speed": {threshold: metrics["speed_bins"][str(threshold)] / max(1.0, metrics["paths"]) * factor for threshold in SPEED_BINS},
        "total_baili": sum(formal.values()), "formal_baili": formal,
        "native75": metrics["native75"] / max(1.0, metrics["paths"]) * factor,
        "converted75": metrics["converted75"] / max(1.0, metrics["paths"]) * factor,
        "output60": metrics["output60"] / max(1.0, metrics["paths"]) * factor,
    }


def aggregate_four_sets(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    def average(values: list[Any]) -> Any:
        if isinstance(values[0], dict):
            return {key: average([value[key] for value in values]) for key in values[0]}
        if isinstance(values[0], list):
            return [average([value[index] for value in values]) for index in range(len(values[0]))]
        if isinstance(values[0], (int, float)):
            return sum(values) / len(values)
        return values[0] if all(value == values[0] for value in values) else "mixed"
    return average(rows)


def _ci(values: list[float]) -> list[float]:
    if len(values) < 2:
        return [values[0] if values else 0.0, values[0] if values else 0.0]
    multiplier = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776}.get(len(values), 1.96)
    half = multiplier * stdev(values) / sqrt(len(values))
    center = mean(values)
    return [center - half, center + half]


def _summarize_set(resume: Path, set_code: str, seeds: list[int], initial_mode: str) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        payload = json.loads(_shard_path(resume, set_code, initial_mode, seed).read_text(encoding="utf-8"))
        candidate_rows = {}
        for candidate, ranks in payload["rows"].items():
            combined, pool = _batch_row(ranks["Epic"], ranks["Heroic"])
            row = _per100k(combined, pool)
            cycles = row["ledger"]["cycles"]
            row["by_source"] = {
                "normal_epic": _source_component_per100k(ranks["Epic"], factor=cycles),
                "normal_heroic": _source_component_per100k(ranks["Heroic"], factor=cycles * HEROIC_PER_EPIC),
            }
            sensitivities = {}
            for label, multiplier in (("heroic_yield_minus20", 0.8), ("heroic_yield_plus20", 1.2)):
                adjusted, adjusted_pool = _batch_row(ranks["Epic"], ranks["Heroic"], HEROIC_PER_EPIC * multiplier)
                sensitivities[label] = _per100k(adjusted, adjusted_pool)
            row["heroic_yield_sensitivity"] = sensitivities
            candidate_rows[candidate] = row
        per_seed[str(seed)] = candidate_rows
    result: dict[str, Any] = {"set_code": set_code, "set_name": SET_CODE_TO_NAME[set_code], "per_seed": per_seed, "candidates": {}}
    for candidate in CANDIDATES:
        rows = [per_seed[str(seed)][candidate] for seed in seeds]
        result["candidates"][candidate] = aggregate_four_sets(rows)
        result["candidates"][candidate]["interval95_22"] = _ci([row["speed"][22] for row in rows])
    baseline = "H4_current"
    for candidate in CANDIDATES:
        if candidate == baseline:
            continue
        deltas = [
            per_seed[str(seed)][candidate]["speed"][22] - per_seed[str(seed)][baseline]["speed"][22]
            for seed in seeds
        ]
        gs = [
            per_seed[str(seed)][candidate]["total_baili"] - per_seed[str(seed)][baseline]["total_baili"]
            for seed in seeds
        ]
        result["candidates"][candidate]["delta_vs_h4"] = {
            "speed22": mean(deltas), "speed22_interval95": _ci(deltas),
            "total_baili": mean(gs), "total_baili_interval95": _ci(gs),
            "saint_stamina": result["candidates"][candidate]["ledger"]["saint_stamina"] - result["candidates"][baseline]["ledger"]["saint_stamina"],
            "native75": result["candidates"][candidate]["native75"] - result["candidates"][baseline]["native75"],
            "converted75": result["candidates"][candidate]["converted75"] - result["candidates"][baseline]["converted75"],
            "output60": result["candidates"][candidate]["output60"] - result["candidates"][baseline]["output60"],
        }
    return result


def run(set_code: str, resume: Path, seeds: list[int], *, runs_per_seed: int, initial_mode: str) -> dict[str, Any]:
    scheduled = skipped = 0
    for seed in seeds:
        path = _shard_path(resume, set_code, initial_mode, seed)
        if _valid(path):
            skipped += 1
            continue
        _atomic_json(path, _shard(set_code, seed, runs_per_seed, initial_mode))
        scheduled += 1
    return {"execution": {"scheduled_shards": scheduled, "skipped_shards": skipped}, "result": _summarize_set(resume, set_code, seeds, initial_mode)}


def _coverage_table() -> list[dict[str, str]]:
    return [
        {"item": "Heroic +0速度门槛、套装范围、完整联合作用池和十万体力账本", "status": "本任务直接研究"},
        {"item": "Epic>=2、+3命中速度到+6、+6后正式策略、正式分类与合法满值转换", "status": "沿用既有正式逻辑"},
        {"item": "Heroic产量±20%、弱化套资格、初始值代理分布", "status": "仅做敏感性"},
        {"item": "分类独立门槛、部位难度、三有效词条、玩家库存需求、rift_85、Heroic非速度早期策略与误停长尾", "status": "仍未覆盖"},
    ]


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# Heroic 紫装速度门槛与十万体力产量研究", "",
        "本研究未修改正式策略、跳值表、lambda、评分、DP、资源默认值、GUI 或前瞻批次。22速与正式体系百里分分开统计。", "",
        "## 结论", "",
        f"- 初始副属性数值没有直接概率证据：主视图和强化概率代理视图均已分开计算。结论状态：`{report['gate']['status']}`。",
        "- 下表按完整联合作用池换算到每十万总体现力；维度裂缝体力与圣女3-7补充体力严格相加为100,000。", "",
        "## 四套演示", "",
        f"- 演示四套：{', '.join(report['four_set_demo'])}。它只是等权算术平均示例，不是刷取建议。", "",
        "| 候选 | 22+ | 23+ | 24+ | 25+ | 27+ | 总百里分 | 圣女体力 | 维度裂缝体力 | 循环数 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    demo = report["four_set_summary"]
    for candidate, row in demo["candidates"].items():
        ledger = row["ledger"]
        lines.append(f"| {candidate} | {row['speed'][22]:.3f} | {row['speed'][23]:.3f} | {row['speed'][24]:.3f} | {row['speed'][25]:.3f} | {row['speed'][27]:.3f} | {row['total_baili']:.2f} | {ledger['saint_stamina']:.1f} | {ledger['riftslash_stamina']:.1f} | {ledger['cycles']:.2f} |")
    lines.extend(["", "## 相对H4的交换", "", "| 候选 | 22+变化（95%CI） | 总百里分变化（95%CI） | 圣女体力变化 | 原生75+变化 | 转换75+变化 | 输出60变化 |", "|---|---:|---:|---:|---:|---:|---:|"])
    for candidate, row in demo["candidates"].items():
        if candidate == "H4_current":
            continue
        delta = row["delta_vs_h4"]
        low, high = delta["speed22_interval95"]
        gs_low, gs_high = delta["total_baili_interval95"]
        lines.append(f"| {candidate} | {delta['speed22']:.3f} [{low:.3f}, {high:.3f}] | {delta['total_baili']:.2f} [{gs_low:.2f}, {gs_high:.2f}] | {delta['saint_stamina']:.1f} | {delta['native75']:.3f} | {delta['converted75']:.3f} | {delta['output60']:.3f} |")
    h4 = demo["candidates"]["H4_current"]
    lines.extend(["", "## H4资源与分来源", "", f"- H4每十万总体力：维度裂缝 {h4['ledger']['riftslash_stamina']:.1f}（{h4['ledger']['riftslash_clears']:.1f}次）、圣女3-7 {h4['ledger']['saint_stamina']:.1f}（{h4['ledger']['saint_clears']:.1f}次）、循环 {h4['ledger']['cycles']:.2f}；合计 {h4['ledger']['total_stamina']:.1f}。", f"- 每循环资源账本：来源金币127,500、来源下级石0.425、实际用石 {h4['pool']['source_lower_stones_used']:.3f}、粉末基础经验 {h4['pool']['powder_base_exp']:.1f}、材料/转换金币缺口 {h4['pool']['net_gold_deficit']:.1f}、经验缺口 {h4['pool']['net_exp_deficit']:.1f}；瓶颈为 `{h4['pool']['bottleneck']}`。", "", "| 分来源 | 22+ | 总百里分 | 原生75+ | 转换75+ | 输出60 |", "|---|---:|---:|---:|---:|---:|"])
    for source, row in h4["by_source"].items():
        lines.append(f"| {source} | {row['speed'][22]:.3f} | {row['total_baili']:.2f} | {row['native75']:.3f} | {row['converted75']:.3f} | {row['output60']:.3f} |")
    lines.extend(["", "- H4节点到达数（每十万总体力）：" + "；".join(f"+{point}={value:.2f}" for point, value in h4["nodes"]["reached"].items()) + "。", "- H4节点停止数（每十万总体力）：" + "；".join(f"+{point}={value:.2f}" for point, value in h4["nodes"]["stopped"].items()) + "。"])
    lines.extend(["", "## 单套条件结果", "", "| 套装 | 候选 | 22+ | 总百里分 | 原生75+ | 转换75+ | 输出60 |", "|---|---|---:|---:|---:|---:|---:|"])
    for set_code, result in report["sets"].items():
        for candidate, row in result["candidates"].items():
            lines.append(f"| {result['set_name']} | {candidate} | {row['speed'][22]:.3f} | {row['total_baili']:.2f} | {row['native75']:.3f} | {row['converted75']:.3f} | {row['output60']:.3f} |")
    lines.extend(["", "## 旧B缺项覆盖表", "", "| 项目 | 状态 |", "|---|---|"])
    for row in _coverage_table():
        lines.append(f"| {row['item']} | {row['status']} |")
    lines.extend(["", "## 口径与限制", "", "- 初始值主视图为合法范围均匀；代理视图把强化离散概率仅作为初始值敏感性，不能宣称为自然掉落概率。两口径的四套22+排序不同，故不可发布。", "- 释放节点调用正式分类建议的非DP基线；Heroic资源DP lambda未发布，未在离线研究中臆造替代值。Epic>=2速度硬路线与+3命中速度到+6由现有建议层保留。", "- 资源池每85体力批次只计一次127,500金币与0.425下级石；Heroic期望数为3.569929，另有±20%敏感性见JSON。", "- 每件终局装备只计入一个正式体系；转换仅替代原生结果，不重复计件。", "- 未读取库存中51/53件速度筛选比例，完整池按STOVE记录的合法部位、主属性和副属性候选等概率生成。", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Full-pool Heroic speed threshold research")
    parser.add_argument("--sets", default=",".join(sorted(SET_CODE_TO_NAME)))
    parser.add_argument("--demo-sets", default="set_speed,set_cri,set_att,set_max_hp")
    parser.add_argument("--seeds", default="20260713,20260714,20260715,20260716,20260717")
    parser.add_argument("--runs-per-seed", type=int, default=200)
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "heroic_speed_threshold_100k_baseline_v2_resume_20260713")
    parser.add_argument("--output", type=Path, default=ROOT / "reports" / "heroic_speed_threshold_100k_baseline_v2_20260713.json")
    args = parser.parse_args()
    sets = [item.strip() for item in args.sets.split(",") if item.strip()]
    demo_sets = [item.strip() for item in args.demo_sets.split(",") if item.strip()]
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
    if len(seeds) != len(set(seeds)) or any(item not in SET_CODE_TO_NAME for item in sets + demo_sets):
        raise ValueError("invalid duplicate seed or set code")
    all_results: dict[str, dict[str, Any]] = {mode: {} for mode in ("legacy_initial_uniform", "roll_distribution_as_initial_proxy")}
    execution = {mode: {"scheduled_shards": 0, "skipped_shards": 0} for mode in all_results}
    for mode in all_results:
        for set_code in sets:
            outcome = run(set_code, args.resume_dir, seeds, runs_per_seed=args.runs_per_seed, initial_mode=mode)
            all_results[mode][set_code] = outcome["result"]
            for key in execution[mode]:
                execution[mode][key] += outcome["execution"][key]
    primary = all_results["legacy_initial_uniform"]
    four_rows = [primary[set_code] for set_code in demo_sets]
    four_candidates = {candidate: aggregate_four_sets([row["candidates"][candidate] for row in four_rows]) for candidate in CANDIDATES}
    ordering = sorted(CANDIDATES, key=lambda candidate: -four_candidates[candidate]["speed"][22])
    proxy_rows = [all_results["roll_distribution_as_initial_proxy"][set_code] for set_code in demo_sets]
    proxy_candidates = {candidate: aggregate_four_sets([row["candidates"][candidate] for row in proxy_rows]) for candidate in CANDIDATES}
    proxy_ordering = sorted(CANDIDATES, key=lambda candidate: -proxy_candidates[candidate]["speed"][22])
    h4_ci_crosses = any(
        row["delta_vs_h4"]["speed22_interval95"][0] <= 0 <= row["delta_vs_h4"]["speed22_interval95"][1]
        for candidate, row in four_candidates.items() if candidate != "H4_current"
    )
    reasons = ["initial starting-value distribution is not directly evidenced", "research-only threshold; user must choose speed/GS Pareto tradeoff"]
    if ordering != proxy_ordering:
        reasons.append("two initial-value views change the 22+ candidate ordering")
    if h4_ci_crosses:
        reasons.append("20 runs per seed leaves candidate-vs-H4 22+ intervals crossing zero")
    status = "initial_distribution_blocked" if ordering != proxy_ordering else "offline_only_pending_human_confirmation"
    if h4_ci_crosses:
        status += "_and_22_ci_unresolved"
    report = {
        "schema_version": SCHEMA_VERSION, "scope": "normal_85 full Epic/Heroic riftslash pool only", "sets": primary,
        "supersedes": {"report": "heroic_speed_threshold_100k_20260713", "status": "superseded_due_to_followup_baseline_error"},
        "initial_proxy_sensitivity": all_results["roll_distribution_as_initial_proxy"], "four_set_demo": demo_sets,
        "four_set_summary": {"candidates": four_candidates, "speed22_order": ordering},
        "proxy_speed22_order": proxy_ordering, "execution": execution,
        "initial_value_evidence": "not directly evidenced; two separated sensitivity views required",
        "gate": {"status": status, "reasons": reasons},
        "old_b_coverage": _coverage_table(),
    }
    _atomic_json(args.output, report)
    args.output.with_suffix(".md").write_text(_render(report), encoding="utf-8")


if __name__ == "__main__":
    main()
