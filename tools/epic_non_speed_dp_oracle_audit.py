"""Exact DP Oracle audit for reviewed normal_85 Epic non-speed samples.

This tool is intentionally offline-only.  It never changes published policy
thresholds, DP constants, resource defaults, roll tables, or GUI behavior.
"""
from __future__ import annotations

import argparse
from functools import partial
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from math import isclose
from pathlib import Path
from statistics import mean
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.calibration import DP_ASSIST_CONFIGS
from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.enhance_simulator import CHECKPOINTS
from src.e7_enhance.models import Gear
from src.e7_enhance.route_solver import (
    clear_route_cache,
    compute_optimal_route,
    enumerate_next_checkpoint,
    marginal_net_stamina_cost,
)
from src.e7_enhance.resource_model import calibration_for_rank
from tools.epic_non_speed_early_policy_pareto import (
    DEFAULT_BLIND_SIZE,
    GEAR_SOURCE,
    _gear_from_item,
    _speed_hard_route,
    strategies,
    strategy_actions,
    summarize_incremental_cost,
)


ACTIONS = frozenset({"continue", "cautious_continue", "stop"})
NUMERIC_ZERO_TOLERANCE = 1e-10
OLD_SOURCE_NAME = "real_acceptance_fribbels_20260610_plus0_plus3.json"
BLIND_SOURCE_NAME = "epic_non_speed_blind_acceptance_20260712.json"
DEFAULT_OLD_SOURCE = ROOT / "samples" / OLD_SOURCE_NAME
DEFAULT_BLIND_SOURCE = ROOT / "samples" / BLIND_SOURCE_NAME
DEFAULT_RECORDS = ROOT / "manual_acceptance" / "real_sample_records.json"
DEFAULT_JSON_OUTPUT = ROOT / "reports" / "epic_non_speed_dp_oracle_audit_20260712.json"
DEFAULT_MARKDOWN_OUTPUT = ROOT / "reports" / "epic_non_speed_dp_oracle_audit_20260712.md"


def canonical_fingerprint(gear: Gear) -> str:
    """Return a source-independent state fingerprint for fallback linking.

    Item code and instance ID are intentionally excluded.  The enhancement
    state contains every field that affects legal future rolls and DP value.
    Substat ordering is normalized because it is not semantically meaningful.
    """
    payload = {
        "set": gear.set,
        "slot": gear.slot,
        "main_stat": {"key": gear.main_stat.key, "value": float(gear.main_stat.normalized_value)},
        "enhance": int(gear.enhance),
        "level": int(gear.level),
        "rank": gear.rank,
        "substats": sorted(
            [
                {
                    "key": stat.key,
                    "value": float(stat.normalized_value),
                    "rolls": int(stat.rolls),
                    "modified": bool(stat.modified),
                }
                for stat in gear.substats
            ],
            key=lambda stat: (stat["key"], stat["value"], stat["rolls"], stat["modified"]),
        ),
    }
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _source_id(item: dict[str, Any]) -> str:
    return str(item.get("ingameId") or item.get("id") or "").strip()


def _snapshot_source_matches(snapshot: dict[str, Any], source_name: str) -> bool:
    names = [str(snapshot.get("source_file") or "")]
    names.extend(str(value) for value in (snapshot.get("original_source_files") or []))
    return source_name in names


def _reviewed_snapshots(records_payload: dict[str, Any], source_name: str) -> list[dict[str, Any]]:
    rows = []
    for record in records_payload.get("records") or []:
        for snapshot in record.get("snapshots") or []:
            review = snapshot.get("human_review") or {}
            decision = str(review.get("decision") or "")
            if decision not in ACTIONS or not _snapshot_source_matches(snapshot, source_name):
                continue
            rows.append({"record": record, "snapshot": snapshot, "human_action": decision})
    return rows


def _stored_current_action(snapshot: dict[str, Any]) -> str:
    recommendation = str(((snapshot.get("suggestion") or {}).get("summary") or {}).get("recommendation") or "")
    return {
        "continue": "continue",
        "review": "cautious_continue",
        "cautious_continue": "cautious_continue",
        "stop": "stop",
    }.get(recommendation, "cautious_continue")


def _exclude(reason: str, *, cohort: str, source_name: str, detail: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "cohort": cohort,
        "source_name": source_name,
        "reason": reason,
        "detail": detail,
        "snapshot_id": (snapshot or {}).get("snapshot_id"),
        "snapshot_fingerprint": (snapshot or {}).get("fingerprint"),
    }


def link_source_items(
    source_payload: dict[str, Any],
    records_payload: dict[str, Any],
    *,
    cohort: str,
    source_name: str,
    frozen_predictions: dict[str, dict[str, str]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Link reviewed snapshots to source items by ID, then by canonical state.

    Fallback fingerprints must map to exactly one source item.  Ambiguous or
    missing matches remain visible in ``excluded`` rather than being guessed.
    """
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    outside_scope: list[dict[str, Any]] = []
    source_by_id: dict[str, dict[str, Any]] = {}
    source_by_fp: dict[str, list[dict[str, Any]]] = {}
    for item in source_payload.get("items") or []:
        item_id = _source_id(item)
        try:
            gear = _gear_from_item(item)
        except Exception as exc:
            excluded.append(_exclude("invalid_source_item", cohort=cohort, source_name=source_name, detail=str(exc)))
            continue
        if not item_id:
            excluded.append(_exclude("source_missing_instance_id", cohort=cohort, source_name=source_name, detail=gear.code))
            continue
        if item_id in source_by_id:
            excluded.append(_exclude("duplicate_source_instance_id", cohort=cohort, source_name=source_name, detail=item_id))
            continue
        source_row = {"instance_id": item_id, "gear": gear, "item": item}
        source_by_id[item_id] = source_row
        source_by_fp.setdefault(canonical_fingerprint(gear), []).append(source_row)

    # A duplicate source fingerprint cannot safely be used for a snapshot that
    # lost its instance ID.  Surface it even when no review snapshot references it.
    for fingerprint, rows in source_by_fp.items():
        if len(rows) > 1:
            excluded.append(_exclude(
                "source_fingerprint_not_unique", cohort=cohort, source_name=source_name,
                detail=f"{fingerprint}: {','.join(row['instance_id'] for row in rows)}",
            ))

    linked_ids: set[str] = set()
    for review_row in _reviewed_snapshots(records_payload, source_name):
        snapshot = review_row["snapshot"]
        try:
            snapshot_gear = Gear.from_dict(snapshot.get("gear") or {})
        except Exception as exc:
            excluded.append(_exclude("invalid_review_snapshot", cohort=cohort, source_name=source_name, detail=str(exc), snapshot=snapshot))
            continue
        if snapshot_gear.rank != "Epic" or snapshot_gear.level != 85 or snapshot_gear.enhance not in (0, 3):
            outside_scope.append(_exclude(
                "outside_epic_early_audit_scope", cohort=cohort, source_name=source_name,
                detail=f"rank={snapshot_gear.rank},level={snapshot_gear.level},enhance={snapshot_gear.enhance}", snapshot=snapshot,
            ))
            continue
        snapshot_instance_id = str((snapshot.get("gear") or {}).get("instanceId") or "").strip()
        source_row = source_by_id.get(snapshot_instance_id)
        link_method = "instance_id" if source_row is not None else ""
        if source_row is None:
            matches = source_by_fp.get(canonical_fingerprint(snapshot_gear), [])
            if len(matches) == 1:
                source_row = matches[0]
                link_method = "canonical_fingerprint"
            else:
                reason = "source_fingerprint_not_unique" if len(matches) > 1 else "source_fingerprint_not_found"
                excluded.append(_exclude(reason, cohort=cohort, source_name=source_name, detail=canonical_fingerprint(snapshot_gear), snapshot=snapshot))
                continue
        if source_row["instance_id"] in linked_ids:
            excluded.append(_exclude("multiple_review_snapshots_for_source", cohort=cohort, source_name=source_name, detail=source_row["instance_id"], snapshot=snapshot))
            continue
        linked_ids.add(source_row["instance_id"])
        gear = source_row["gear"]
        if gear.rank != "Epic" or gear.level != 85 or gear.enhance not in (0, 3):
            excluded.append(_exclude("not_normal_85_epic_early_state", cohort=cohort, source_name=source_name, detail=source_row["instance_id"], snapshot=snapshot))
            continue
        if _speed_hard_route(gear):
            excluded.append(_exclude("speed_hard_route", cohort=cohort, source_name=source_name, detail=source_row["instance_id"], snapshot=snapshot))
            continue
        frozen = (frozen_predictions or {}).get(source_row["instance_id"])
        derived = strategy_actions(gear, "normal_85")
        candidate_actions = dict(frozen or derived)
        missing = sorted(strategy.key for strategy in strategies() if strategy.key not in candidate_actions)
        if missing:
            excluded.append(_exclude("frozen_candidate_missing", cohort=cohort, source_name=source_name, detail=",".join(missing), snapshot=snapshot))
            continue
        recomputed = _advice_action(gear)
        included.append({
            "cohort": cohort,
            "source_name": source_name,
            "instance_id": source_row["instance_id"],
            "source_code": str(source_row["item"].get("code") or ""),
            "gear": gear,
            "link_method": link_method,
            "source_fingerprint": canonical_fingerprint(gear),
            "snapshot_fingerprint": str(snapshot.get("fingerprint") or ""),
            "snapshot_id": str(snapshot.get("snapshot_id") or ""),
            "human_action": review_row["human_action"],
            "stored_current_action": _stored_current_action(snapshot),
            "recomputed_current_action": recomputed,
            "current_action": _stored_current_action(snapshot),
            "candidate_actions": candidate_actions,
            "candidate_action_source": "frozen_blind_payload" if frozen else "frozen_strategy_definition",
            "candidate_drift": {
                key: {"frozen": candidate_actions[key], "recomputed": derived[key]}
                for key in candidate_actions if candidate_actions[key] != derived[key]
            },
        })
    included.sort(key=lambda row: (row["cohort"], row["instance_id"]))
    return {"included": included, "excluded": excluded, "outside_scope": outside_scope}


def _advice_action(gear: Gear) -> str:
    recommendation = str(advise_gear(gear, item_source="normal_85", gear_source=GEAR_SOURCE)["summary"]["recommendation"])
    return {
        "continue": "continue",
        "review": "cautious_continue",
        "cautious_continue": "cautious_continue",
        "stop": "stop",
    }[recommendation]


def _blind_prediction_map(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in payload.get("strategy_predictions") or []:
        instance_id = str(row.get("instance_id") or "")
        actions = row.get("actions") or {}
        if instance_id and instance_id not in result and all(action in ACTIONS for action in actions.values()):
            result[instance_id] = {str(key): str(value) for key, value in actions.items()}
    return result


def collect_audit_cases(
    *,
    old_source_path: Path = DEFAULT_OLD_SOURCE,
    blind_source_path: Path = DEFAULT_BLIND_SOURCE,
    records_payload: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    old_payload = json.loads(Path(old_source_path).read_text(encoding="utf-8"))
    blind_payload = json.loads(Path(blind_source_path).read_text(encoding="utf-8"))
    old = link_source_items(old_payload, records_payload, cohort="old_holdout", source_name=Path(old_source_path).name)
    blind = link_source_items(
        blind_payload,
        records_payload,
        cohort="blind",
        source_name=Path(blind_source_path).name,
        frozen_predictions=_blind_prediction_map(blind_payload),
    )
    return {
        "included": old["included"] + blind["included"],
        "excluded": old["excluded"] + blind["excluded"],
        "outside_scope": old["outside_scope"] + blind["outside_scope"],
    }


def _forced_continue_metrics(gear: Gear, lambda_value: float) -> dict[str, float]:
    """Recover the value of taking one next node when root Oracle stops.

    ``compute_optimal_route`` intentionally reports zero path cost for an
    immediate stop.  Candidate regret needs the alternate, forced first-node
    branch, followed by the same exact Oracle at every child state.
    """
    checkpoint = gear.enhance
    next_checkpoint = next(point for point in CHECKPOINTS if point > checkpoint)
    marginal = marginal_net_stamina_cost(checkpoint, next_checkpoint, gear.rank, gear.slot)
    expected = {
        "utility_after": 0.0,
        "formal_baili": 0.0,
        "terminal_value": 0.0,
        "terminal_speed": 0.0,
        "speed_rolls": 0.0,
        "speed_potential": 0.0,
        "stamina_after": 0.0,
        "conversion_probability": 0.0,
        "speed_threshold_blocked_probability": 0.0,
    }
    for child, probability in enumerate_next_checkpoint(gear, next_checkpoint, "normal_85"):
        child_route = compute_optimal_route(
            child,
            lambda_value,
            item_source="normal_85",
            gear_source=GEAR_SOURCE,
            rank="Epic",
        )
        expected["utility_after"] += probability * float(child_route["expected_utility"])
        expected["formal_baili"] += probability * float(child_route["expected_formal_baili_score"])
        expected["terminal_value"] += probability * float(child_route["expected_terminal_value"])
        expected["terminal_speed"] += probability * float(child_route["expected_terminal_speed"])
        expected["speed_rolls"] += probability * float(child_route["expected_speed_rolls"])
        expected["speed_potential"] += probability * float(child_route["expected_speed_potential_value"])
        expected["stamina_after"] += probability * float(child_route["expected_incremental_stamina"])
        expected["conversion_probability"] += probability * float(child_route["conversion_needed_probability"])
        expected["speed_threshold_blocked_probability"] += probability * float(child_route["speed_potential_threshold_blocked_probability"])
    return {
        "continue_utility": expected["utility_after"] - lambda_value * marginal,
        "forced_continue_stamina": marginal + expected["stamina_after"],
        "expected_formal_baili_score": expected["formal_baili"],
        "expected_terminal_value": expected["terminal_value"],
        "expected_terminal_speed": expected["terminal_speed"],
        "expected_speed_rolls": expected["speed_rolls"],
        "expected_speed_potential_value": expected["speed_potential"],
        "conversion_needed_probability": expected["conversion_probability"],
        "speed_threshold_blocked_probability": expected["speed_threshold_blocked_probability"],
    }


def oracle_for_gear(gear: Gear, *, lambda_value: float | None = None) -> dict[str, Any]:
    """Calculate exact normal Epic DP action and its forced-next alternative."""
    lambda_value = lambda_value if lambda_value is not None else 1.0 / float(DP_ASSIST_CONFIGS[("normal_85", "Epic")]["cost_per_baili_score"])
    route = compute_optimal_route(
        gear,
        lambda_value,
        item_source="normal_85",
        gear_source=GEAR_SOURCE,
        rank="Epic",
    )
    forced = _forced_continue_metrics(gear, lambda_value)
    stop_utility = float(route["stop_utility"])
    # The solver compares full-precision RouteResult values before converting
    # them to the JSON payload.  Preserve that action; the payload margin is
    # only a rounded audit display value.
    margin = float(route["continue_utility"]) - stop_utility
    uncertain = abs(margin) <= NUMERIC_ZERO_TOLERANCE
    action = "cautious_continue" if uncertain else ("continue" if route["action"] == "continue" else "stop")
    next_cost = summarize_incremental_cost(gear.slot, gear.rank, gear.enhance, int(route["next_checkpoint"]))
    calibration = calibration_for_rank(gear.rank)
    recovery = calibration.sell_recovery[gear.enhance]
    return {
        "oracle_type": "exact_enumeration",
        "action": action,
        "resource_action": "enhance" if action != "stop" else "stop",
        "stop_utility": stop_utility,
        "continue_utility": forced["continue_utility"],
        "utility_margin": margin,
        "numeric_zero_tolerance": NUMERIC_ZERO_TOLERANCE,
        "review_reason": "数值零点容差内" if uncertain else None,
        "next_checkpoint": int(route["next_checkpoint"]),
        "next_node_incremental_cost": next_cost,
        "forced_continue_stamina": forced["forced_continue_stamina"],
        "expected_formal_baili_score": forced["expected_formal_baili_score"],
        "expected_terminal_value": forced["expected_terminal_value"],
        "expected_terminal_speed": forced["expected_terminal_speed"],
        "expected_speed_rolls": forced["expected_speed_rolls"],
        "expected_speed_potential_value": forced["expected_speed_potential_value"],
        "speed_potential_set_eligible": bool(route["speed_potential_set_eligible"]),
        "speed_potential_threshold_blocked_probability": forced["speed_threshold_blocked_probability"],
        "conversion_needed_probability": forced["conversion_needed_probability"],
        "conversion_cost_gold": float(route["conversion_cost_gold"]),
        "conversion_cost_stamina": float(route["conversion_cost_stamina"]),
        "immediate_stop_recovery": {"gold": float(recovery.gold), "enhance_exp": float(recovery.enhance_exp)},
        "optimal_path": {
            "type": "contingent_exact_dp_tree",
            "first_action": action,
            "first_checkpoint": gear.enhance,
            "next_checkpoint": int(route["next_checkpoint"]),
            "future_policy": "每个后继合法状态继续复用同一精确 DP；不是单一固定强化路径。",
            "terminal_state_count": int(route["terminal_count"]),
            "best_target_category": str(route["best_target_category"]),
            "best_source_row": str(route["best_source_row"]),
        },
    }


def _audit_case(row: dict[str, Any], lambda_value: float | None = None) -> dict[str, Any]:
    clear_route_cache()
    gear = row["gear"] if isinstance(row["gear"], Gear) else Gear.from_dict(row["gear"])
    oracle = oracle_for_gear(gear, lambda_value=lambda_value)
    return {
        **{key: value for key, value in row.items() if key != "gear"},
        "gear": gear.to_dict(),
        "oracle": oracle,
    }


def _resource_action(action: str) -> bool:
    return action != "stop"


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _action_for(row: dict[str, Any], strategy_key: str) -> str:
    if strategy_key == "current_policy":
        return str(row["current_action"])
    return str(row["candidate_actions"][strategy_key])


def compare_actions(rows: Iterable[dict[str, Any]], strategy_key: str) -> dict[str, Any]:
    rows = list(rows)
    regret_values: list[float] = []
    false_enhance = false_stop = review_count = 0
    wasted_stamina = missed_terminal_value = 0.0
    binary_match = tri_match = human_binary_match = human_tri_match = 0
    enhanced_stamina = enhanced_terminal_value = 0.0
    for row in rows:
        action = _action_for(row, strategy_key)
        oracle = row["oracle"]
        oracle_action = str(oracle["action"])
        enhance = _resource_action(action)
        oracle_enhance = _resource_action(oracle_action)
        margin = float(oracle["utility_margin"])
        regret = 0.0
        if enhance and not oracle_enhance:
            false_enhance += 1
            regret = -margin
            wasted_stamina += float(oracle["forced_continue_stamina"])
        elif not enhance and oracle_enhance:
            false_stop += 1
            regret = margin
            missed_terminal_value += float(oracle["expected_terminal_value"])
        if action == "cautious_continue":
            review_count += 1
        binary_match += int(enhance == oracle_enhance)
        tri_match += int(action == oracle_action)
        human = str(row.get("human_action") or "")
        human_binary_match += int(bool(human) and enhance == _resource_action(human))
        human_tri_match += int(bool(human) and action == human)
        if enhance:
            enhanced_stamina += float(oracle["forced_continue_stamina"])
            enhanced_terminal_value += float(oracle["expected_terminal_value"])
        regret_values.append(max(0.0, regret))
    total = len(rows)
    oracle_positive = [row for row in rows if _resource_action(str(row["oracle"]["action"]))]
    recalled = sum(_resource_action(_action_for(row, strategy_key)) for row in oracle_positive)
    return {
        "sample_count": total,
        "binary_action_accuracy": binary_match / total if total else 0.0,
        "tri_action_accuracy": tri_match / total if total else 0.0,
        "total_utility_regret": sum(regret_values),
        "mean_utility_regret": mean(regret_values) if regret_values else 0.0,
        "p90_utility_regret": _percentile(regret_values, 0.9),
        "max_utility_regret": max(regret_values, default=0.0),
        "false_enhance_count": false_enhance,
        "wasted_incremental_stamina": wasted_stamina,
        "false_stop_count": false_stop,
        "missed_expected_terminal_value": missed_terminal_value,
        "oracle_positive_recall": recalled / len(oracle_positive) if oracle_positive else 1.0,
        "expected_terminal_value_per_100_stamina": 100 * enhanced_terminal_value / enhanced_stamina if enhanced_stamina else 0.0,
        "human_binary_agreement": human_binary_match / total if total else 0.0,
        "human_tri_agreement": human_tri_match / total if total else 0.0,
        "manual_review_coverage": review_count / total if total else 0.0,
    }


def _manual_vs_oracle(row: dict[str, Any]) -> str:
    oracle_action = str(row["oracle"]["action"])
    human = str(row["human_action"])
    if oracle_action == "cautious_continue":
        return "DP 边界不确定"
    if _resource_action(human) and not _resource_action(oracle_action):
        return "人工偏激进但 DP 负效用"
    if not _resource_action(human) and _resource_action(oracle_action):
        return "人工偏保守但 DP 正效用"
    return "人工与 DP 资源动作一致"


def _compact_case(row: dict[str, Any]) -> dict[str, Any]:
    gear = row["gear"]
    oracle = row["oracle"]
    return {
        "instance_id": row["instance_id"],
        "cohort": row["cohort"],
        "link_method": row["link_method"],
        "source_fingerprint": row["source_fingerprint"],
        "snapshot_fingerprint": row["snapshot_fingerprint"],
        "slot": gear["slot"],
        "main_stat": gear["mainStat"]["type"],
        "enhance": gear["enhance"],
        "set": gear["set"],
        "human_action": row["human_action"],
        "current_action": row["current_action"],
        "recomputed_current_action": row["recomputed_current_action"],
        "candidate_actions": row["candidate_actions"],
        "candidate_action_source": row["candidate_action_source"],
        "candidate_drift": row["candidate_drift"],
        "oracle": oracle,
        "manual_vs_oracle": _manual_vs_oracle(row),
    }


def run_audit(
    *,
    old_source_path: Path = DEFAULT_OLD_SOURCE,
    blind_source_path: Path = DEFAULT_BLIND_SOURCE,
    records_path: Path = DEFAULT_RECORDS,
    workers: int = 1,
    lambda_value: float | None = None,
) -> dict[str, Any]:
    records = json.loads(Path(records_path).read_text(encoding="utf-8"))
    linked = collect_audit_cases(
        old_source_path=old_source_path,
        blind_source_path=blind_source_path,
        records_payload=records,
    )
    source_rows = linked["included"]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            rows = list(executor.map(partial(_audit_case, lambda_value=lambda_value), source_rows))
    else:
        rows = [_audit_case(row, lambda_value) for row in source_rows]
    rows.sort(key=lambda row: (row["cohort"], row["instance_id"]))
    candidate_keys = ["current_policy"] + [strategy.key for strategy in strategies()]
    comparisons = {key: compare_actions(rows, key) for key in candidate_keys}
    partitions = {
        "old_holdout": [row for row in rows if row["cohort"] == "old_holdout"],
        "blind": [row for row in rows if row["cohort"] == "blind"],
    }
    per_cohort = {
        cohort: {key: compare_actions(group, key) for key in candidate_keys}
        for cohort, group in partitions.items()
    }
    config = DP_ASSIST_CONFIGS[("normal_85", "Epic")]
    effective_lambda = lambda_value if lambda_value is not None else 1.0 / float(config["cost_per_baili_score"])
    return {
        "metadata": {
            "scope": "normal_85 Epic +0/+3 non-speed exact DP Oracle audit",
            "oracle_type": "exact discrete enumeration through +15",
            "item_source": "normal_85",
            "rank": "Epic",
            "lambda": effective_lambda,
            "cost_per_baili_score": 1.0 / effective_lambda,
            "resource_calibration": config["calibration"],
            "gear_source": GEAR_SOURCE,
            "acquisition_cost": "excluded as sunk from current-item continue/stop utility",
            "conversion_gold_cost": 100000,
            "numeric_zero_tolerance": NUMERIC_ZERO_TOLERANCE,
            "candidate_keys": candidate_keys,
            "blind_size_contract": DEFAULT_BLIND_SIZE,
        },
        "linkage": {
            "included_count": len(rows),
            "excluded_count": len(linked["excluded"]),
            "excluded": linked["excluded"],
            "outside_scope_count": len(linked["outside_scope"]),
            "outside_scope": linked["outside_scope"],
            "rules": {
                "primary": "source ingameId/id",
                "fallback": "canonical state fingerprint without item code/instance ID",
                "duplicate_handling": "ambiguous fingerprints are reported and excluded; never first-match by array order",
            },
        },
        "comparisons": comparisons,
        "comparisons_by_cohort": per_cohort,
        "publication_decision": publication_decision(comparisons),
        "manual_vs_oracle": {
            label: sum(1 for row in rows if _manual_vs_oracle(row) == label)
            for label in ("人工偏保守但 DP 正效用", "人工偏激进但 DP 负效用", "DP 边界不确定", "人工与 DP 资源动作一致")
        },
        "cases": [_compact_case(row) for row in rows],
    }


def publication_decision(comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Keep the release gate explicit instead of selecting by human agreement."""
    baseline = comparisons["current_policy"]
    global_gs = comparisons["B_global_current_gs"]
    category_probability = comparisons["C_category_probability"]
    return {
        "create_formal_strategy_task": False,
        "decision": "不建立正式策略修改任务",
        "evidence": [
            f"B 的人工动作一致率为 {global_gs['human_binary_agreement']:.2%}，但有 {global_gs['false_stop_count']} 件 Oracle 正效用误停，total regret={global_gs['total_utility_regret']:.4f}。",
            f"C 的 total regret={category_probability['total_utility_regret']:.4f}，仅比当前策略 {baseline['total_utility_regret']:.4f} 高，但仍有 {category_probability['false_stop_count']} 件误停。",
            "46 件均已读取人工标签，只能用于审计，不能作为候选调整后的独立发布验证。",
        ],
        "required_before_any_candidate_change": "从剩余真实 normal_85 Epic 冻结至少 48 件新独立验证批次，再读取人工标签。",
    }


def markdown_report(data: dict[str, Any]) -> str:
    metadata = data["metadata"]
    lines = [
        "# Epic 非速度早期策略精确 DP 审计（2026-07-12）",
        "",
        "## 结论",
        "",
        "- 人工标签是玩家资源偏好与风险验收，不是单件边际强化效用的唯一真值；本报告以精确 DP utility margin 判定资源动作，并把人工作为第二套对照。",
        f"- 目标 46 件中纳入 {data['linkage']['included_count']} 件，按规则单列排除 {data['linkage']['excluded_count']} 件速度硬路线、非法或无法唯一关联记录；另有 {data['linkage']['outside_scope_count']} 件同源历史审核记录不属于 Epic +0/+3 目标集合。",
        "- Oracle 为 normal_85 Epic 独立跳值表的精确离散枚举；没有使用 Monte Carlo、人工标签或装备获取成本。",
        f"- 已发布成本系数：{metadata['cost_per_baili_score']:.1f} 体力/百里分，lambda={metadata['lambda']:.10f}。",
        "- `continue` 和 `cautious_continue` 在资源动作上都表示强化至下一节点；只有数值零点容差内的 Oracle 才标为人工复核。",
        f"- 发布结论：{data['publication_decision']['decision']}。",
        "",
        "## 稳定关联与排除",
        "",
        "- 主关联：源文件 `ingameId/id`；盲测导入后缺失实例 ID 的记录，用规范化装备状态指纹关联。",
        "- 指纹包含套装、部位、主属性、强化等级、装备等级、品质与排序后的副属性值/跳数；排除 code 与实例 ID。重复指纹直接报告并排除。",
        f"- 已纳入：old holdout {len([row for row in data['cases'] if row['cohort'] == 'old_holdout'])} 件；blind {len([row for row in data['cases'] if row['cohort'] == 'blind'])} 件。",
        "",
        "## 候选与 Oracle",
        "",
        "| 策略 | 二元动作一致 | 总 regret | P90 regret | 误强化/浪费体力 | 误停/损失终局价值 | Oracle 正效用召回 | 终局价值/100体力 | 人工三分类一致 | 人工复核 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {"current_policy": "当前正式策略", **{strategy.key: strategy.label for strategy in strategies()}}
    for key in metadata["candidate_keys"]:
        value = data["comparisons"][key]
        lines.append(
            f"| {labels[key]} | {value['binary_action_accuracy']:.2%} | {value['total_utility_regret']:.4f} | "
            f"{value['p90_utility_regret']:.4f} | {value['false_enhance_count']}/{value['wasted_incremental_stamina']:.2f} | "
            f"{value['false_stop_count']}/{value['missed_expected_terminal_value']:.2f} | {value['oracle_positive_recall']:.2%} | "
            f"{value['expected_terminal_value_per_100_stamina']:.3f} | {value['human_tri_agreement']:.2%} | {value['manual_review_coverage']:.2%} |"
        )
    lines.extend([
        "",
        "## 人工与 Oracle 分歧",
        "",
    ])
    for label, count in data["manual_vs_oracle"].items():
        lines.append(f"- {label}：{count} 件")
    lines.extend(["", "## 发布闸门", ""])
    for evidence in data["publication_decision"]["evidence"]:
        lines.append(f"- {evidence}")
    lines.append(f"- 后续要求：{data['publication_decision']['required_before_any_candidate_change']}")
    lines.extend([
        "",
        "## 逐件结果",
        "",
        "| 实例 ID | 批次 | 关联 | + | Oracle 动作 | margin | 下一节点体力 | 终局价值 | 当前 | B | C | 人工 | 对照 |",
        "|---|---|---|---:|---|---:|---:|---:|---|---|---|---|---|",
    ])
    for row in data["cases"]:
        oracle = row["oracle"]
        lines.append(
            f"| {row['instance_id']} | {row['cohort']} | {row['link_method']} | {row['enhance']} | {oracle['action']} | "
            f"{oracle['utility_margin']:.6f} | {oracle['next_node_incremental_cost']['net_stamina']:.2f} | "
            f"{oracle['expected_terminal_value']:.3f} | {row['current_action']} | "
            f"{row['candidate_actions']['B_global_current_gs']} | {row['candidate_actions']['C_category_probability']} | "
            f"{row['human_action']} | {row['manual_vs_oracle']} |"
        )
    lines.extend([
        "",
        "## 口径",
        "",
        "- 即时停止 utility 规范化为 0；当前出售/回收值是两条路径共同的沉没状态，不在差值中重复扣除。继续路径的节点净成本已包含之后停止时的出售/回收差额。",
        "- `forced_continue_stamina` 是“候选要求强化到下一节点、其后回到 Oracle”的端到端期望增量体力；它用于误强化成本与 regret 统计。",
        "- 终局正式价值、速度潜力和合法满值转换价值均来自 Oracle 终局枚举；转换成本为一次 100,000 金币并已折算进入 utility。",
        "- 这 46 件均已有人看过，不能再作为调整候选后的独立发布验证。若要改变任何候选门槛，须先从剩余真实 normal_85 Epic 冻结至少 48 件新验证样本。",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit reviewed Epic non-speed samples against exact DP Oracle.")
    parser.add_argument("--old-source", type=Path, default=DEFAULT_OLD_SOURCE)
    parser.add_argument("--blind-source", type=Path, default=DEFAULT_BLIND_SOURCE)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    args = parser.parse_args(argv)
    data = run_audit(
        old_source_path=args.old_source,
        blind_source_path=args.blind_source,
        records_path=args.records,
        workers=max(1, args.workers),
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown_report(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
