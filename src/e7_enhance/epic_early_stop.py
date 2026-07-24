from __future__ import annotations

from typing import Any, Iterable

from .lightweight_calibration import evaluate_early_candidates
from .models import Gear


CANDIDATE_KEY = "output_8_13_tank_10_17"
RULE_VERSION = "epic-early-stop-v1-20260720"
DEFAULT_THRESHOLDS = {0: 12.0, 3: 17.0}
SYSTEM_THRESHOLDS = {
    "pure_output": {0: 8.0, 3: 13.0},
    "pure_tank": {0: 10.0, 3: 17.0},
}
TERMINAL_PROBABILITY_MAX = {0: 0.002, 3: 0.01}
CURRENT_VALID_MAX = 2
CONVERSION_VALUE_MAX = 0.0

CATEGORY_SYSTEM_GROUPS = {
    "输出": "pure_output",
    "输出(必爆)": "pure_output",
    "抗坦": "pure_tank",
    "纯肉": "pure_tank",
    "命坦": "pure_tank",
    "双效": "dual",
    "半肉(血防)": "bruiser",
    "半肉(通用)": "bruiser",
    "半肉(白字)": "bruiser",
}


def system_group(category: str) -> str:
    return CATEGORY_SYSTEM_GROUPS.get(str(category), "unknown")


def selected_candidate_features(candidates: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(candidates)
    selected = next((row for row in rows if row.get("qualified")), None)
    if selected is None:
        selected = next(
            (
                row
                for row in rows
                if row.get("formal_terminal_formula_available")
                and int(row.get("current_valid_substat_count") or 0) >= 2
            ),
            None,
        )
    if selected is None:
        return {
            "category": "unknown",
            "system_group": "unknown",
            "effective_gs": 0.0,
            "current_valid": 0,
            "probability": 0.0,
            "conversion_value": 0.0,
            "conversion_gs_gain": 0.0,
        }
    category = str(selected.get("category") or "unknown")
    return {
        "category": category,
        "system_group": system_group(category),
        "effective_gs": float(selected.get("current_pre_reforge_gs") or 0.0),
        "current_valid": int(selected.get("current_valid_substat_count") or 0),
        "probability": float(selected.get("terminal_reach_probability") or 0.0),
        "conversion_value": float(selected.get("conversion_max_value") or 0.0),
        "conversion_gs_gain": float(selected.get("conversion_max_gs_gain") or 0.0),
    }


def threshold_for(checkpoint: int, group: str) -> float:
    return SYSTEM_THRESHOLDS.get(group, DEFAULT_THRESHOLDS)[checkpoint]


def candidate_action(baseline_action: str, checkpoint: int, features: dict[str, Any]) -> str:
    if baseline_action == "stop":
        return "stop"
    checks = _stop_checks(checkpoint, features)
    return "stop" if all(checks.values()) else "continue"


def released_early_stop_decision(
    gear: Gear,
    *,
    item_source: str,
    baseline_action: str,
    candidates: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    eligible, scope_reason = _scope(gear, item_source)
    debug: dict[str, Any] = {
        "candidate_key": CANDIDATE_KEY,
        "rule_version": RULE_VERSION,
        "eligible": eligible,
        "scope_reason": scope_reason,
        "checkpoint": gear.enhance,
        "baseline_action": baseline_action,
        "final_action": baseline_action,
        "added_stop": False,
        "category": None,
        "system_group": None,
        "threshold": None,
        "terminal_probability_max": None,
        "features": None,
        "checks": None,
        "reason": scope_reason,
    }
    if not eligible:
        return debug

    rows = list(candidates) if candidates is not None else evaluate_early_candidates(gear, item_source)
    features = selected_candidate_features(rows)
    threshold = threshold_for(gear.enhance, str(features["system_group"]))
    checks = _stop_checks(gear.enhance, features)
    final_action = candidate_action(baseline_action, gear.enhance, features)
    added_stop = baseline_action != "stop" and final_action == "stop"
    reason = (
        f"{CANDIDATE_KEY} 在 +{gear.enhance} 命中 {features['system_group']} 止损门槛 {threshold:g}"
        if added_stop
        else "未同时满足正式候选的 GS、有效词条、终局概率和转换价值止损条件"
    )
    debug.update(
        {
            "final_action": final_action,
            "added_stop": added_stop,
            "category": features["category"],
            "system_group": features["system_group"],
            "threshold": threshold,
            "terminal_probability_max": TERMINAL_PROBABILITY_MAX[gear.enhance],
            "features": features,
            "checks": checks,
            "reason": reason,
        }
    )
    return debug


def _stop_checks(checkpoint: int, features: dict[str, Any]) -> dict[str, bool]:
    group = str(features.get("system_group") or "unknown")
    return {
        "effective_gs_lte_threshold": float(features.get("effective_gs") or 0.0) <= threshold_for(checkpoint, group),
        "current_valid_lte_max": int(features.get("current_valid") or 0) <= CURRENT_VALID_MAX,
        "terminal_probability_lte_max": float(features.get("probability") or 0.0) <= TERMINAL_PROBABILITY_MAX[checkpoint],
        "conversion_value_lte_max": _conversion_gate_value(features) <= CONVERSION_VALUE_MAX,
    }


def _conversion_gate_value(features: dict[str, Any]) -> float:
    if "conversion_gs_gain" in features:
        return float(features.get("conversion_gs_gain") or 0.0)
    return float(features.get("conversion_value") or 0.0)


def _scope(gear: Gear, item_source: str) -> tuple[bool, str]:
    speed = next((stat.normalized_value for stat in gear.substats if stat.key == "spd"), 0.0)
    if item_source != "normal_85":
        return False, "仅适用 normal_85"
    if gear.rank != "Epic" or gear.level != 85:
        return False, "仅适用 85 级 Epic"
    if gear.slot == "boot":
        return False, "鞋子不适用 Epic 非速度早期止损"
    if gear.enhance not in (0, 3):
        return False, "仅适用 +0/+3"
    if speed >= 2:
        return False, "初速 >=2 使用已发布速度硬路线"
    return True, "命中 normal_85 Epic 非鞋非速度 +0/+3 范围"
