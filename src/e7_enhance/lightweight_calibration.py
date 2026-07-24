"""Versioned, explainable rules for the +0/+3 lightweight gate.

Rules are intentionally exact-group only.  An unseen group is never silently
assigned a global score threshold: it is sent to the +6 exact-DP review path.
The offline calibration command writes the same JSON schema used here.
"""
from __future__ import annotations

import json
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Any

from .enhance_simulator import STAT_POOL, RollProfile, reforge_bonus_value, roll_range, slot_forbidden_substats
from .modification_values import (
    MODIFICATION_MAX_VALUE_SOURCE,
    expected_terminal_modification_max_gs,
    expected_terminal_modification_max_value,
    modification_max_value,
    terminal_roll_distribution,
)
from .models import Gear, Stat, round1
from .rules import CATEGORY_RULES, FORMULAS, OFFICIAL_SCORE_WEIGHTS, STAT_KEY_LABELS, VALID_STATS
from .score_engine import category_gate, full_category_diagnostics, main_allowed


RULES_PATH = Path(__file__).with_name("lightweight_calibration_rules.json")


def main_stat_class(gear: Gear) -> str:
    key = gear.main_stat.key
    if gear.slot in {"weapon", "helm", "armor"}:
        return "left_fixed"
    return {
        "spd": "speed",
        "atkPct": "attack_percent",
        "defPct": "defense_percent",
        "hpPct": "health_percent",
        "crit": "critical_rate",
        "cdmg": "critical_damage",
        "eff": "effectiveness",
        "res": "effect_resistance",
        "atkFlat": "attack_flat",
        "defFlat": "defense_flat",
        "hpFlat": "health_flat",
    }.get(key, key)


def calibration_group(
    gear: Gear,
    item_source: str,
    set_group: str,
    category: str,
    current_valid_substat_count: int | None = None,
    feasible_valid_substat_count: int | None = None,
) -> dict[str, str]:
    return {
        "item_source": item_source,
        "rank": gear.rank,
        "slot": gear.slot,
        "main_stat_class": main_stat_class(gear),
        "set_group": set_group,
        "selected_category": category,
        "current_valid_substat_count": str(current_valid_substat_count if current_valid_substat_count is not None else 0),
        "feasible_valid_substat_count": str(feasible_valid_substat_count if feasible_valid_substat_count is not None else 0),
    }


def group_id(group: dict[str, str]) -> str:
    return "|".join(
        str(group.get(key, "0"))
        for key in (
            "item_source",
            "rank",
            "slot",
            "main_stat_class",
            "set_group",
            "selected_category",
            "current_valid_substat_count",
            "feasible_valid_substat_count",
        )
    )


@lru_cache(maxsize=1)
def calibration_rules() -> dict[str, dict[str, Any]]:
    if not RULES_PATH.exists():
        return {}
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    return {group_id(item["group"]): item for item in payload.get("rules", [])}


def calibration_rule(group: dict[str, str]) -> dict[str, Any] | None:
    return calibration_rules().get(group_id(group))


def passes_continue_threshold(rule: dict[str, Any] | None, metrics: dict[str, float | int | bool]) -> bool:
    if rule is None:
        return False
    threshold = rule.get("continue") or {}
    if not metrics.get("full_category_matched"):
        return False
    comparisons = {
        "expected_final_reforge_score_min": "expected_final_reforge_score",
        "expected_final_target_score_min": "expected_final_target_score",
        "current_effective_score_min": "current_effective_score",
        "remaining_hits_min": "remaining_hits",
        "formal_cross_tier_probability_min": "formal_cross_tier_probability",
        "terminal_reach_probability_min": "terminal_reach_probability",
        "current_valid_substat_count_min": "current_valid_substat_count",
        "feasible_valid_substat_count_min": "feasible_valid_substat_count",
        "expected_final_speed_min": "expected_final_speed",
        "speed_rolls_min": "speed_rolls",
        "speed_potential_value_min": "speed_potential_value",
    }
    numeric_matched = all(float(metrics.get(metric, 0)) >= float(value) for key, metric in comparisons.items() if (value := threshold.get(key)) is not None)
    set_eligible_required = threshold.get("speed_potential_set_eligible")
    return numeric_matched and (not set_eligible_required or bool(metrics.get("speed_potential_set_eligible")))


def stop_threshold(rule: dict[str, Any] | None) -> float | None:
    if rule is None:
        return None
    value = (rule.get("stop") or {}).get("theoretical_upper_bound_lt")
    return float(value) if value is not None else None


HIGH_PRIORITY_CATEGORIES = {"输出", "输出(必爆)", "抗坦", "纯肉", "命坦"}
FUTURE_75_GS_THRESHOLD = 75.0


def future_75_metrics(
    gear: Gear,
    item_source: str,
    conversion_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project all-substat official GS and its independent 75+ probability.

    This intentionally scores every current substat, unlike a formal-category
    candidate which filters to its valid stat set.  A conversion, when one is
    already selected by the formal candidate rules, replaces the source
    substat's terminal contribution with the Greater-gem maximum.
    """
    from .calibration import cross_tier_probability, projected_reforge_score_for_keys

    all_keys = set(OFFICIAL_SCORE_WEIGHTS)
    native_expected = projected_reforge_score_for_keys(gear, item_source, all_keys)
    native_upper_bound = _total_substat_gs_upper_bound(gear, item_source)
    native_probability = 0.0 if native_upper_bound < FUTURE_75_GS_THRESHOLD else cross_tier_probability(
        gear,
        item_source,
        all_keys,
        FUTURE_75_GS_THRESHOLD,
        native_expected,
    )
    result = {
        "expected_final_total_substat_gs_native": native_expected,
        "future_75_gs_threshold": FUTURE_75_GS_THRESHOLD,
        "terminal_future_75_probability_native": native_probability,
        "future_75_theoretical_upper_bound_native": native_upper_bound,
        "expected_final_total_substat_gs_after_max_conversion": None,
        "terminal_future_75_probability_after_max_conversion": None,
        "terminal_future_75_probability": native_probability,
    }
    if not conversion_candidate or not conversion_candidate.get("is_conversion_candidate"):
        return result

    source_key = str(conversion_candidate.get("conversion_candidate_key") or "")
    target_key = str(conversion_candidate.get("conversion_target_key") or "")
    source_stat = next((stat for stat in gear.substats if stat.key == source_key), None)
    if source_stat is None or not target_key:
        return result

    source_terminal_gs = projected_reforge_score_for_keys(gear, item_source, {source_key})
    target_terminal_gs = expected_terminal_modification_max_gs(gear, source_stat, target_key)
    converted_expected = round1(native_expected - source_terminal_gs + target_terminal_gs)
    # Once converted at the terminal state, all rolls into the source stat no
    # longer contribute to its final GS.  Keep those legal hit branches in the
    # probability model as zero-value outcomes rather than treating them as
    # extra rolls into the target stat.
    converted_upper_bound = round1(native_upper_bound - source_terminal_gs + target_terminal_gs)
    converted_probability = 0.0 if converted_upper_bound < FUTURE_75_GS_THRESHOLD else cross_tier_probability(
        gear,
        item_source,
        all_keys - {source_key},
        FUTURE_75_GS_THRESHOLD,
        converted_expected,
    )
    result.update({
        "expected_final_total_substat_gs_after_max_conversion": converted_expected,
        "terminal_future_75_probability_after_max_conversion": converted_probability,
        "terminal_future_75_probability": converted_probability,
        "future_75_theoretical_upper_bound_after_max_conversion": converted_upper_bound,
    })
    return result


def _total_substat_gs_upper_bound(gear: Gear, item_source: str) -> float:
    """Return a safe upper bound for every substat's terminal official GS."""
    profile = RollProfile(gear.roll_level or gear.level, gear.rank, item_source)
    stats = list(gear.substats)
    checkpoints = [checkpoint for checkpoint in (3, 6, 9, 12, 15) if checkpoint > gear.enhance]
    substat_count = len(stats)
    roll_events = 0
    for checkpoint in checkpoints:
        if _adds_substat_at(gear.rank, checkpoint, substat_count):
            substat_count += 1
            # The yet-unknown fourth stat can only increase this upper bound;
            # use the globally strongest legal roll as a conservative proxy.
            if len(stats) < 4:
                best_key = max(OFFICIAL_SCORE_WEIGHTS, key=lambda key: roll_range(profile, key)[1] * OFFICIAL_SCORE_WEIGHTS[key])
                stats.append(Stat(best_key, roll_range(profile, best_key)[1], rolls=1))
            continue
        roll_events += 1
    if not stats:
        return 0.0

    best = 0.0
    for allocations in product(range(roll_events + 1), repeat=len(stats)):
        if sum(allocations) != roll_events:
            continue
        total = 0.0
        for stat, extra_rolls in zip(stats, allocations):
            high_roll = roll_range(profile, stat.key)[1]
            terminal_rolls = stat.rolls + extra_rolls
            value = stat.normalized_value + high_roll * extra_rolls
            if gear.level == 85:
                value += reforge_bonus_value(stat.key, terminal_rolls)
            total += value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0)
        best = max(best, total)
    return round1(best)


def _adds_substat_at(rank: str, checkpoint: int, substat_count: int) -> bool:
    if substat_count >= 4:
        return False
    if rank == "Heroic":
        return checkpoint == 12
    if rank == "Rare":
        return checkpoint in {3, 6}
    return False


def evaluate_early_candidates(gear: Gear, item_source: str) -> list[dict[str, Any]]:
    """Evaluate formal end-state candidates without running route DP.

    Conversion candidates use the Fribbels Greater-gem 100%-quality maximum
    after terminal enhancement.  They remain conservative review routes until
    a published complete-category calibration rule permits auto-continue.
    """
    from .calibration import (
        cross_tier_probability,
        formula_score_for_effective,
        projected_reforge_score_for_keys,
    )

    profile = RollProfile(gear.roll_level or gear.level, gear.rank, item_source)
    bounds = {
        (item["category"], item["set_group"]): item
        for item in theoretical_category_bounds(gear, item_source)
    }
    existing_keys = {stat.key for stat in gear.substats}
    existing_keys.add(gear.main_stat.key)
    available_keys = set(STAT_POOL) - existing_keys - slot_forbidden_substats(gear.slot)
    missing_slots = max(0, 4 - len(gear.substats))
    candidates = []

    for rule in CATEGORY_RULES:
        valid_keys = set(VALID_STATS.get(rule["validGroup"], []))
        matched = [stat for stat in gear.substats if stat.key in valid_keys]
        unmatched = [stat for stat in gear.substats if stat.key not in valid_keys]
        candidate_keys = {stat.key for stat in matched}
        candidate_keys.add(gear.main_stat.key)
        special_matched = _candidate_special_conditions_matched(rule, candidate_keys)
        formulas = (FORMULAS.get(rule["formula"], {}) or {}).get(gear.slot)
        set_matched = gear.set in set(rule_set_group(rule))
        main_matched = main_allowed(gear.slot, gear.main_stat.key, rule.get("main", {}))
        conversion = _conversion_candidate(gear, item_source, valid_keys, unmatched, available_keys)
        legal_valid_keys = valid_keys - {gear.main_stat.key} - slot_forbidden_substats(gear.slot)
        max_legal_valid_count = len(legal_valid_keys)
        slot_limited_three_valid_path = len(matched) >= 3 and len(matched) >= max_legal_valid_count
        feasible_count = len(matched) + min(missing_slots, len(valid_keys & available_keys))
        if conversion["eligible"]:
            feasible_count += 1
        feasible_count = min(max_legal_valid_count, feasible_count)
        formal_candidate = bool(set_matched and main_matched and special_matched and formulas)
        all_current_substats_matched = bool(gear.substats) and not unmatched
        qualified = bool(
            formal_candidate
            and len(matched) >= 3
            and (all_current_substats_matched or conversion["eligible"] or slot_limited_three_valid_path)
        )
        current_pre_reforge_gs = _current_pre_reforge_gs(matched)
        current_final_gs = _current_reforged_gs(gear, matched)
        expected_final_gs_native = projected_reforge_score_for_keys(gear, item_source, valid_keys) if formulas else 0.0
        threshold = min(formula[0] for formula in formulas) if formulas else None
        native_reach_probability = (
            cross_tier_probability(gear, item_source, valid_keys, threshold, expected_final_gs_native)
            if threshold is not None
            else 0.0
        )
        conversion_max_gs_gain = 0.0
        conversion_max_value = None
        conversion_roll_distribution = None
        expected_final_gs_after_max_conversion = None
        if conversion["eligible"]:
            candidate_stat = unmatched[0]
            target_key = conversion["target_key"]
            conversion_max_value = expected_terminal_modification_max_value(gear, candidate_stat, target_key)
            conversion_max_gs_gain = expected_terminal_modification_max_gs(gear, candidate_stat, target_key)
            conversion_roll_distribution = terminal_roll_distribution(gear, candidate_stat)
            expected_final_gs_after_max_conversion = round1(expected_final_gs_native + conversion_max_gs_gain)
        expected_final_gs = expected_final_gs_after_max_conversion if expected_final_gs_after_max_conversion is not None else expected_final_gs_native
        reach_probability = (
            cross_tier_probability(gear, item_source, valid_keys, threshold, expected_final_gs)
            if threshold is not None
            else 0.0
        )
        bound = bounds.get((rule["category"], rule["setGroup"]), {})
        rejection_reasons = _candidate_rejection_reasons(
            set_matched,
            main_matched,
            special_matched,
            formulas,
            matched,
            unmatched,
            conversion,
            slot_limited_three_valid_path,
        )
        candidates.append(
            {
                "category": rule["category"],
                "priority": rule["priority"],
                "priority_layer": "高优先级" if rule["category"] in HIGH_PRIORITY_CATEGORIES else "低优先级",
                "set_group": rule["setGroup"],
                "source_row": rule["sourceRow"],
                "matched_substats": [STAT_KEY_LABELS.get(stat.key, stat.key) for stat in matched],
                "unmatched_substats": [STAT_KEY_LABELS.get(stat.key, stat.key) for stat in unmatched],
                "current_valid_substat_count": len(matched),
                "feasible_valid_substat_count": feasible_count,
                "max_legal_valid_substat_count": max_legal_valid_count,
                "slot_limited_three_valid_path": slot_limited_three_valid_path,
                "all_current_substats_matched": all_current_substats_matched,
                "is_conversion_candidate": conversion["eligible"],
                "conversion_candidate": conversion["stat"],
                "conversion_candidate_key": conversion["stat_key"],
                "conversion_target_stat": conversion["target"],
                "conversion_target_key": conversion["target_key"],
                "formal_terminal_formula_available": bool(formulas),
                "formal_terminal_gs_threshold": threshold,
                "current_pre_reforge_gs": current_pre_reforge_gs,
                "current_reforged_gs": current_final_gs,
                "expected_final_gs_native": expected_final_gs_native,
                "conversion_max_gs_gain": conversion_max_gs_gain,
                "conversion_max_value": conversion_max_value,
                "conversion_max_value_source": MODIFICATION_MAX_VALUE_SOURCE if conversion["eligible"] else None,
                "conversion_terminal_roll_distribution": conversion_roll_distribution,
                "expected_final_gs_after_max_conversion": expected_final_gs_after_max_conversion,
                "expected_final_gs": expected_final_gs,
                "terminal_reach_probability_native": native_reach_probability,
                "terminal_reach_probability": reach_probability,
                "theoretical_lower_bound": bound.get("theoretical_lower_bound", current_final_gs),
                "theoretical_upper_bound": bound.get("theoretical_upper_bound", expected_final_gs),
                "qualified": qualified,
                "rejection_reasons": rejection_reasons,
                "expected_terminal_value": formula_score_for_effective(expected_final_gs, formulas) if formulas else 0.0,
            }
        )

    candidates.sort(
        key=lambda item: (
            not item["qualified"],
            item["priority_layer"] != "高优先级",
            -item["terminal_reach_probability"],
            item["priority"],
        )
    )
    return candidates


def rule_set_group(rule: dict[str, Any]) -> set[str]:
    from .rules import SET_GROUPS

    return SET_GROUPS.get(rule["setGroup"], set())


def _candidate_special_conditions_matched(rule: dict[str, Any], keys: set[str]) -> bool:
    if not category_gate(rule["category"], keys):
        return False
    if rule.get("requiredAny") and not any(key in keys for key in rule["requiredAny"]):
        return False
    return not (
        rule.get("noAtkPctWithEffRes")
        and "atkPct" in keys
        and any(key in keys for key in ("eff", "res"))
    )


def _conversion_candidate(
    gear: Gear,
    item_source: str,
    valid_keys: set[str],
    unmatched: list[Stat],
    available_keys: set[str],
) -> dict[str, Any]:
    if len(unmatched) != 1 or not 0 < unmatched[0].rolls <= 2:
        return {"eligible": False, "stat": None, "target": None, "stat_key": None, "target_key": None}
    targets = valid_keys & available_keys
    if not targets:
        return {"eligible": False, "stat": None, "target": None, "stat_key": None, "target_key": None}
    target = max(targets, key=lambda key: expected_terminal_modification_max_gs(gear, unmatched[0], key))
    return {
        "eligible": True,
        "stat": STAT_KEY_LABELS.get(unmatched[0].key, unmatched[0].key),
        "stat_key": unmatched[0].key,
        "target": STAT_KEY_LABELS.get(target, target),
        "target_key": target,
    }


def _current_pre_reforge_gs(stats: list[Stat]) -> float:
    return round1(sum(stat.normalized_value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0) for stat in stats))


def _current_reforged_gs(gear: Gear, stats: list[Stat]) -> float:
    return round1(
        sum(
            (stat.normalized_value + (reforge_bonus_value(stat.key, stat.rolls) if gear.level == 85 else 0))
            * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0)
            for stat in stats
        )
    )


def _candidate_rejection_reasons(
    set_matched: bool,
    main_matched: bool,
    special_matched: bool,
    formulas: list[tuple] | None,
    matched: list[Stat],
    unmatched: list[Stat],
    conversion: dict[str, Any],
    slot_limited_three_valid_path: bool,
) -> list[str]:
    reasons = []
    if not set_matched:
        reasons.append("套装不匹配")
    if not main_matched:
        reasons.append("主属性不匹配")
    if not special_matched:
        reasons.append("分类特殊条件不匹配")
    if not formulas:
        reasons.append("该分类与部位没有正式终局公式")
    if len(matched) < 3:
        reasons.append("当前命中副属性少于三条")
    if len(unmatched) > 1:
        reasons.append("未命中副属性超过一条")
    elif len(unmatched) == 1 and not conversion["eligible"] and not slot_limited_three_valid_path:
        reasons.append("唯一未命中副属性不具备转换候选资格")
    return reasons


def theoretical_category_bounds(gear: Gear, item_source: str) -> list[dict[str, Any]]:
    """Return conservative legal lower/upper effective-score bounds by category.

    The upper bound allocates every remaining roll to the best legal stat in a
    category, may add Heroic's one missing substat, and includes deterministic
    reforge bonuses.  It is deliberately an upper bound, not a probability or
    a substitute for exact DP.
    """
    profile = RollProfile(gear.roll_level or gear.level, gear.rank, item_source)
    remaining_events = max(0, (15 - gear.enhance) // 3)
    missing_substats = max(0, 4 - len(gear.substats))
    upgrade_events = max(0, remaining_events - missing_substats)
    existing = {stat.key for stat in gear.substats}
    existing.add(gear.main_stat.key)
    available = set(STAT_POOL) - existing - slot_forbidden_substats(gear.slot)
    result = []
    for diagnostic in full_category_diagnostics(gear):
        valid_keys = set(diagnostic["valid_keys"])
        # A single already-invalid stat can still be converted at reforge; two
        # cannot be made into one formal category under the supported rules.
        invalid = [stat for stat in gear.substats if stat.key not in valid_keys]
        category_possible = bool(
            diagnostic["set_matched"]
            and diagnostic["main_matched"]
            and diagnostic["special_matched"]
            and len(invalid) <= 1
        )
        if not category_possible:
            continue
        lower = 0.0
        upper = 0.0
        conversion_target = None
        missing_substat_target = None
        for stat in gear.substats:
            if stat.key not in valid_keys:
                continue
            weight = OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0)
            lower += (stat.normalized_value + reforge_bonus_value(stat.key, stat.rolls)) * weight
            upper += (stat.normalized_value + reforge_bonus_value(stat.key, stat.rolls + upgrade_events)) * weight
        convertible = len(invalid) == 1 and 0 < invalid[0].rolls <= 2
        new_keys = valid_keys & available
        remaining_new_keys = set(new_keys)
        if convertible and new_keys:
            terminal_rolls = max(terminal_roll_distribution(gear, invalid[0]))
            best_convert = max(
                remaining_new_keys,
                key=lambda key: modification_max_value(key, terminal_rolls) * OFFICIAL_SCORE_WEIGHTS.get(key, 0.0),
            )
            upper += modification_max_value(best_convert, terminal_rolls) * OFFICIAL_SCORE_WEIGHTS.get(best_convert, 0.0)
            remaining_new_keys.remove(best_convert)
            conversion_target = best_convert
        if missing_substats and remaining_new_keys:
            best_new = max(remaining_new_keys, key=lambda key: roll_range(profile, key)[1] * OFFICIAL_SCORE_WEIGHTS.get(key, 0.0))
            high = roll_range(profile, best_new)[1]
            upper += (high + reforge_bonus_value(best_new, 1)) * OFFICIAL_SCORE_WEIGHTS.get(best_new, 0.0)
            missing_substat_target = best_new
        candidates = [stat.key for stat in gear.substats if stat.key in valid_keys]
        candidates.extend(remaining_new_keys)
        if candidates and upgrade_events:
            best_roll = max(candidates, key=lambda key: roll_range(profile, key)[1] * OFFICIAL_SCORE_WEIGHTS.get(key, 0.0))
            upper += upgrade_events * roll_range(profile, best_roll)[1] * OFFICIAL_SCORE_WEIGHTS.get(best_roll, 0.0)
        result.append(
            {
                "category": diagnostic["category"],
                "set_group": diagnostic["set_group"],
                "source_row": diagnostic["source_row"],
                "possible": category_possible,
                "current_invalid_substats": len(invalid),
                "upper_bound_conversion_target": conversion_target,
                "upper_bound_missing_substat_target": missing_substat_target,
                "theoretical_lower_bound": round1(lower),
                "theoretical_upper_bound": round1(max(lower, upper)),
            }
        )
    return result


def best_theoretical_bound(gear: Gear, item_source: str) -> dict[str, Any] | None:
    bounds = theoretical_category_bounds(gear, item_source)
    return max(bounds, key=lambda item: item["theoretical_upper_bound"], default=None)
