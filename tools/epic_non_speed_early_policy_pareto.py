"""Offline study for Epic +0/+3 non-speed early decisions.

This is deliberately experimental.  It never updates enhance_policy, DP
constants, resource defaults, or the published normal/rift rules.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from math import sqrt
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_policy import early_speed_gamble_status, policies_by_name
from src.e7_enhance.enhance_simulator import (
    CHECKPOINTS,
    RollProfile,
    STAT_POOL,
    STAT_TYPE_BY_KEY,
    clone_gear,
    cost_for_outcome,
    enhance_to_checkpoint,
    generate_stat,
    reforge_gear,
    roll_range,
)
from src.e7_enhance.gui_support import _fribbels_item_to_gear_dict
from src.e7_enhance.lightweight_calibration import (
    evaluate_early_candidates,
    expected_terminal_modification_max_value,
    future_75_metrics,
)
from src.e7_enhance.models import (
    MAIN_STAT_KEYS_BY_SLOT,
    SLOT_FORBIDDEN_SUBSTAT_KEYS,
    Gear,
    Stat,
    normalize_rank,
    normalize_set,
    normalize_slot,
    stat_key,
    validate_gear_structure,
)
from src.e7_enhance.resource_model import (
    DEFAULT_CONVERSION_GOLD_COST,
    calibration_for_rank,
    conversion_stamina_cost,
    joint_source_batch_metadata,
)
from src.e7_enhance.score_engine import evaluate_gear, official_score_for_stats, speed_value
from src.e7_enhance.calibration import base_policy_for, conversion_plan_for_gear, should_continue
from src.e7_enhance.rules import SET_CODE_TO_NAME, speed_potential_set_eligible
from src.e7_enhance.strategy_defaults import default_strategy_for


ACTIONS = frozenset({"continue", "cautious_continue", "stop"})
GEAR_SOURCE = "riftslash_20_buff"
DEFAULT_BLIND_SIZE = 24
CONDITIONAL_GENERATION_RULE = "normal_85 legal conditional generation"
HISTORICAL_HOLDOUT_SOURCE = "real_acceptance_fribbels_20260610_plus0_plus3.json"
HEROIC_YIELD_COST_SENSITIVITY = 0.20


@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    decide: Callable[[dict[str, Any]], str]


def generate_conditional_gear(
    set_code: str | None,
    rank: str,
    seed: int,
    *,
    slot: str | None = None,
    main_stat: str | None = None,
) -> Gear:
    """Generate one legal normal-85 gear state for an explicitly known set.

    This is an offline coverage helper.  It does not model drop pools or
    replace the set on a real item supplied to the policy.
    """
    if not set_code:
        raise ValueError("set_code is required for conditional generation")
    normalized_set = normalize_set(set_code)
    if normalized_set not in SET_CODE_TO_NAME:
        raise ValueError(f"unknown set_code: {set_code}")

    normalized_rank = normalize_rank(rank)
    if normalized_rank not in {"Heroic", "Epic"}:
        raise ValueError("conditional generation only supports Heroic or Epic; Rare is rejected")

    rng = random.Random(seed)
    selected_slot = normalize_slot(slot) if slot is not None else rng.choice(tuple(MAIN_STAT_KEYS_BY_SLOT))
    allowed_main = MAIN_STAT_KEYS_BY_SLOT.get(selected_slot)
    if allowed_main is None:
        raise ValueError(f"unknown slot: {slot}")
    selected_main = stat_key(main_stat) if main_stat is not None else rng.choice(tuple(sorted(allowed_main)))
    if selected_main not in allowed_main:
        raise ValueError(f"Invalid main stat for {selected_slot}: {selected_main}")

    sub_count = 3 if normalized_rank == "Heroic" else 4
    forbidden = set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(selected_slot, set())) | {selected_main}
    available = [key for key in STAT_POOL if key not in forbidden]
    if len(available) < sub_count:
        raise ValueError(f"not enough legal substats for {selected_slot}")
    profile = RollProfile(85, normalized_rank, "normal_85")
    substats = [generate_stat(rng, profile, key) for key in rng.sample(available, sub_count)]
    gear = Gear(
        set=normalized_set,
        slot=selected_slot,
        main_stat=Stat(STAT_TYPE_BY_KEY[selected_main], 0),
        enhance=0,
        level=85,
        rank=normalized_rank,
        substats=substats,
        roll_history=[],
        code=f"synthetic:conditional_set:{normalized_set}:{normalized_rank}:{selected_slot}:{selected_main}:{seed}",
        reforge_eligible=True,
        roll_level=85,
    )
    validate_gear_structure(gear)
    return gear


def conditional_gear_record(
    set_code: str | None,
    rank: str,
    seed: int,
    *,
    slot: str | None = None,
    main_stat: str | None = None,
) -> dict[str, Any]:
    """Return a generated Gear together with auditable synthetic metadata."""
    gear = generate_conditional_gear(set_code, rank, seed, slot=slot, main_stat=main_stat)
    return {
        "synthetic": True,
        "generation_mode": "conditional_set",
        "set_code": gear.set,
        "rank": gear.rank,
        "slot": gear.slot,
        "main_stat": gear.main_stat.key,
        "seed": int(seed),
        "generation_rule": CONDITIONAL_GENERATION_RULE,
        "item_source": "normal_85",
        "gear_source_reference": GEAR_SOURCE,
        "gear": gear.to_dict(),
    }


def conditional_coverage_samples(seed: int) -> list[dict[str, Any]]:
    """Create one deterministic legal sample for every set/rank/slot/main cell."""
    records = []
    sequence = 0
    for set_code in sorted(SET_CODE_TO_NAME):
        for rank in ("Heroic", "Epic"):
            for slot, mains in MAIN_STAT_KEYS_BY_SLOT.items():
                for main_stat in sorted(mains):
                    records.append(
                        conditional_gear_record(
                            set_code,
                            rank,
                            seed + sequence,
                            slot=slot,
                            main_stat=main_stat,
                        )
                    )
                    sequence += 1
    return records


def conditional_generation_summary(seed: int) -> dict[str, Any]:
    samples = conditional_coverage_samples(seed)
    by_set = {
        set_code: sum(sample["set_code"] == set_code for sample in samples)
        for set_code in sorted(SET_CODE_TO_NAME)
    }
    return {
        "interface": "generate_conditional_gear(set_code, rank, seed, slot=None, main_stat=None)",
        "item_source": "normal_85",
        "gear_source_reference": GEAR_SOURCE,
        "core_marginal_cost": "excludes acquired gear cost and set acquisition probability",
        "rough_source_reference": {
            rank: calibration_for_rank(rank).gear_stamina(GEAR_SOURCE)
            for rank in ("Heroic", "Epic")
        },
        "coverage_sample_count": len(samples),
        "coverage_by_set": by_set,
        "generation_rule": CONDITIONAL_GENERATION_RULE,
        "not_used_for": ["training_distribution", "holdout", "blind_acceptance", "published_thresholds"],
    }


def _instance_id(item: dict[str, Any]) -> str:
    return str(item.get("ingameId") or item.get("id") or "")


def _gear_from_item(item: dict[str, Any]) -> Gear:
    instance_id = _instance_id(item)
    return replace(Gear.from_dict(_fribbels_item_to_gear_dict(item)), code=f"instance:{instance_id}")


def _reviewed_epic_cases(records_payload: dict[str, Any]) -> list[dict[str, Any]]:
    cases = []
    for record in records_payload.get("records") or []:
        for snapshot in record.get("snapshots") or []:
            gear_data = snapshot.get("gear") or {}
            review = snapshot.get("human_review") or {}
            decision = str(review.get("decision") or "")
            original_sources = set(snapshot.get("original_source_files") or [snapshot.get("source_file") or ""])
            if (
                HISTORICAL_HOLDOUT_SOURCE in original_sources
                and
                gear_data.get("rank") == "Epic"
                and int(gear_data.get("enhance", -1)) in (0, 3)
                and decision in ACTIONS
            ):
                gear = replace(Gear.from_dict(gear_data), code=f"instance:{gear_data.get('instanceId')}")
                cases.append({
                    "instance_id": str(gear_data.get("instanceId") or ""),
                    "gear": gear,
                    "human": decision,
                    "snapshot_id": snapshot.get("snapshot_id"),
                })
    cases.sort(key=lambda item: (item["instance_id"], item["gear"].enhance))
    return cases


def _speed_hard_route(gear: Gear) -> bool:
    speed_stat = next((stat for stat in gear.substats if stat.key == "spd"), None)
    return bool(early_speed_gamble_status(gear, speed_stat)["continue_route"])


def _right_flat_main(gear: Gear) -> bool:
    return gear.slot in {"neck", "ring", "boot"} and gear.main_stat.key in {"atkFlat", "defFlat", "hpFlat"}


def _stratified_blind(rows: list[dict[str, Any]], count: int, seed: int) -> list[dict[str, Any]]:
    """Select a fixed blind set without inspecting manual labels or outcomes."""
    buckets: dict[tuple[str, bool, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        gear = row["gear"]
        buckets[(gear.slot, _right_flat_main(gear), speed_value(gear) > 0)].append(row)
    rng = random.Random(seed)
    for values in buckets.values():
        values.sort(key=lambda row: row["instance_id"])
        rng.shuffle(values)
    selected: list[dict[str, Any]] = []
    keys = sorted(buckets)
    while len(selected) < min(count, len(rows)) and any(buckets.values()):
        for key in keys:
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].pop())
    return sorted(selected, key=lambda row: row["instance_id"])


def build_partition(
    source_payload: dict[str, Any],
    records_payload: dict[str, Any],
    *,
    blind_size: int = DEFAULT_BLIND_SIZE,
    seed: int = 20260712,
) -> dict[str, Any]:
    """Freeze reviewed instances, speed hard routes, and a blind Epic set."""
    holdout = _reviewed_epic_cases(records_payload)
    holdout_ids = {row["instance_id"] for row in holdout}
    candidates = []
    for item in source_payload.get("items") or []:
        if item.get("rank") != "Epic" or int(item.get("enhance", -1)) != 0:
            continue
        instance_id = _instance_id(item)
        if not instance_id or instance_id in holdout_ids:
            continue
        gear = _gear_from_item(item)
        candidates.append({"instance_id": instance_id, "gear": gear, "item": item, "speed_hard": _speed_hard_route(gear)})
    speed_hard = [row for row in candidates if row["speed_hard"]]
    non_speed = [row for row in candidates if not row["speed_hard"]]
    blind = _stratified_blind(non_speed, blind_size, seed)
    blind_ids = {row["instance_id"] for row in blind}
    training = [row for row in non_speed if row["instance_id"] not in blind_ids]
    training.sort(key=lambda row: row["instance_id"])
    return {
        "training": training,
        "blind": blind,
        "holdout": holdout,
        "speed_hard": sorted(speed_hard, key=lambda row: row["instance_id"]),
        "training_ids": {row["instance_id"] for row in training},
        "blind_ids": blind_ids,
        "holdout_ids": holdout_ids,
        "speed_hard_ids": {row["instance_id"] for row in speed_hard},
    }


def paired_rift_gear(gear: Gear) -> Gear:
    """Map a normal state by value quantile into a separately legal rift state."""
    normal_profile = RollProfile(gear.roll_level or gear.level, "Epic", "normal_85")
    rift_profile = RollProfile(gear.roll_level or gear.level, "Epic", "rift_85")
    mapped = []
    for stat in gear.substats:
        normal_low, normal_high = roll_range(normal_profile, stat.key)
        rift_low, rift_high = roll_range(rift_profile, stat.key)
        if normal_high == normal_low:
            quantile = 0.5
        else:
            quantile = min(1.0, max(0.0, (stat.normalized_value - normal_low) / (normal_high - normal_low)))
        value = round(rift_low + quantile * (rift_high - rift_low))
        mapped.append(Stat(type=stat.type, value=value, rolls=stat.rolls, modified=stat.modified))
    return replace(gear, substats=mapped, code=f"rift-paired:{gear.code}")


def simulate_paths(gear: Gear, item_source: str, runs: int, seed: int) -> list[dict[int, Gear]]:
    rng = random.Random(seed)
    paths = []
    for _ in range(runs):
        current = clone_gear(gear)
        path = {current.enhance: current}
        for checkpoint in CHECKPOINTS:
            if checkpoint <= current.enhance:
                continue
            current, _ = enhance_to_checkpoint(current, checkpoint, item_source, rng)
            path[checkpoint] = current
        paths.append(path)
    return paths


def summarize_incremental_cost(slot: str, rank: str, start_checkpoint: int, stop_checkpoint: int) -> dict[str, float]:
    start = cost_for_outcome(start_checkpoint, False, False, GEAR_SOURCE, rank, slot)
    stop = cost_for_outcome(stop_checkpoint, False, False, GEAR_SOURCE, rank, slot)
    calibration = calibration_for_rank(rank)
    spent_gold = sum(
        calibration.interval_costs[checkpoint].gold
        for checkpoint in CHECKPOINTS
        if start_checkpoint < checkpoint <= stop_checkpoint
    )
    recovered_gold = calibration.sell_recovery[stop_checkpoint].gold - calibration.sell_recovery[start_checkpoint].gold
    return {
        "gear_acquisition_stamina": 0.0,
        "upgrade_stamina": float(stop["upgrade_stamina"]) - float(start["upgrade_stamina"]),
        "sell_recovery_stamina": float(stop["sell_recovery_stamina"]) - float(start["sell_recovery_stamina"]),
        "net_stamina": float(stop["total_stamina"]) - float(start["total_stamina"]),
        "net_gold": float(spent_gold - recovered_gold),
    }


def riftslash_joint_batch_metadata() -> dict[str, Any]:
    """Describe one shared riftslash source batch without allocating it twice.

    The existing per-rank figures are valid conditional acquisition references,
    but an Epic and its Heroic co-products came from the same riftslash runs.
    Joint studies therefore pay the source batch exactly once.
    """
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    heroic_yield = float(batch["expected_output_by_rank"].get("Heroic") or 0.0)
    if heroic_yield <= 0:
        raise ValueError("riftslash Epic/Heroic acquisition figures are required for joint batch research")
    return {
        "gear_source": GEAR_SOURCE,
        "batch_basis": "one expected Epic acquisition interval",
        "gross_batch_acquisition_stamina": float(batch["gross_batch_acquisition_stamina"]),
        "net_batch_acquisition_stamina": float(batch["net_batch_acquisition_stamina"]),
        "net_batch_acquisition_basis": "resource_model.joint_source_batch_metadata",
        "epic_expected_per_batch": float(batch["expected_output_by_rank"].get("Epic") or 0.0),
        "heroic_gross_stamina_per_item": float(batch["gross_batch_acquisition_stamina"]) / heroic_yield,
        "heroic_expected_per_batch": heroic_yield,
        "heroic_yield_confirmed": False,
        "heroic_yield_status": "estimated from Heroic 23.81 gross stamina per item",
        "heroic_yield_cost_sensitivity": HEROIC_YIELD_COST_SENSITIVITY,
        "source_pet_gear_included": bool(batch["source_pet_gear_included"]),
        "source_lower_stone_credit_accounting": batch["source_credit_accounting"],
        "resource_model_batch": batch,
    }


def _joint_candidate_order(results: dict[str, dict[str, float]]) -> list[str]:
    return sorted(
        results,
        key=lambda key: (-float(results[key]["full_chain_formal_value_per_100_stamina"]), key),
    )


def riftslash_joint_batch_metrics(
    epic_results: dict[str, dict[str, float]],
    heroic_baseline: dict[str, float],
    heroic_stop: dict[str, float],
) -> dict[str, Any]:
    """Combine Epic candidates with fixed Heroic co-product policies.

    No Heroic policy is tuned here.  The Heroic baseline and all-stop case are
    parallel sensitivity inputs.  Source stamina and source lower-stone credit
    are represented once by ``net_batch_acquisition_stamina``.
    """
    metadata = riftslash_joint_batch_metadata()
    baseline_key = "A_current_review" if "A_current_review" in epic_results else next(iter(epic_results), None)
    if baseline_key is None:
        return {
            "metadata": metadata,
            "heroic_current_baseline": {},
            "heroic_all_stop": {},
            "epic_candidate_order_stable": True,
        }

    yield_scenarios = {
        "heroic_yield_low_20pct": 1.0 + HEROIC_YIELD_COST_SENSITIVITY,
        "heroic_yield_baseline": 1.0,
        "heroic_yield_high_20pct": 1.0 - HEROIC_YIELD_COST_SENSITIVITY,
    }
    policies = {
        "heroic_current_baseline": heroic_baseline,
        "heroic_all_stop": heroic_stop,
    }
    orders: list[list[str]] = []
    policy_results: dict[str, Any] = {}
    for policy_key, heroic in policies.items():
        scenario_results: dict[str, Any] = {}
        for scenario_key, heroic_cost_factor in yield_scenarios.items():
            heroic_yield = metadata["gross_batch_acquisition_stamina"] / (
                metadata["heroic_gross_stamina_per_item"] * heroic_cost_factor
            )
            results: dict[str, dict[str, float]] = {}
            for key, epic in epic_results.items():
                epic_value = float(epic.get("expected_terminal_formal_value_at_15") or 0.0)
                epic_stamina = float(epic.get("average_incremental_stamina") or 0.0)
                heroic_value = float(heroic.get("expected_terminal_formal_value_at_15") or 0.0)
                heroic_stamina = float(heroic.get("average_incremental_stamina") or 0.0)
                total_value = epic_value + heroic_yield * heroic_value
                total_stamina = metadata["net_batch_acquisition_stamina"] + epic_stamina + heroic_yield * heroic_stamina
                results[key] = {
                    "epic_expected_terminal_formal_value": epic_value,
                    "heroic_expected_terminal_formal_value": heroic_value,
                    "heroic_expected_per_batch": heroic_yield,
                    "batch_acquisition_stamina": metadata["net_batch_acquisition_stamina"],
                    "epic_incremental_stamina": epic_stamina,
                    "heroic_incremental_stamina": heroic_stamina,
                    "total_terminal_formal_value_per_batch": total_value,
                    "total_stamina_per_batch": total_stamina,
                    "full_chain_formal_value_per_100_stamina": 100 * total_value / total_stamina if total_stamina else 0.0,
                }
            baseline = results[baseline_key]
            for key, result in results.items():
                result["epic_value_delta_vs_current"] = result["epic_expected_terminal_formal_value"] - baseline["epic_expected_terminal_formal_value"]
                result["epic_stamina_delta_vs_current"] = result["epic_incremental_stamina"] - baseline["epic_incremental_stamina"]
                result["joint_value_rate_delta_vs_current"] = (
                    result["full_chain_formal_value_per_100_stamina"]
                    - baseline["full_chain_formal_value_per_100_stamina"]
                )
            order = _joint_candidate_order(results)
            orders.append(order)
            scenario_results[scenario_key] = {
                "heroic_cost_factor": heroic_cost_factor,
                "heroic_expected_per_batch": heroic_yield,
                "results": results,
                "candidate_order": order,
            }
        policy_results[policy_key] = scenario_results

    candidate_rank_range: dict[str, dict[str, int | bool]] = {}
    for key in epic_results:
        ranks = [order.index(key) + 1 for order in orders]
        candidate_rank_range[key] = {
            "best_rank": min(ranks),
            "worst_rank": max(ranks),
            "stable": min(ranks) == max(ranks),
        }
    return {
        "metadata": metadata,
        **policy_results,
        "candidate_rank_range_across_heroic_scenarios": candidate_rank_range,
        "epic_candidate_order_stable": all(item["stable"] for item in candidate_rank_range.values()),
    }


def _features(gear: Gear, item_source: str) -> dict[str, Any]:
    candidates = evaluate_early_candidates(gear, item_source)
    eligible = next((row for row in candidates if row["qualified"]), None)
    candidate = eligible or next(
        (row for row in candidates if row["formal_terminal_formula_available"] and row["current_valid_substat_count"] >= 2),
        None,
    )
    future = future_75_metrics(gear, item_source, candidate)
    evaluation = evaluate_gear(gear)
    probability = float(candidate.get("terminal_reach_probability") or 0.0) if candidate else 0.0
    current_valid = int(candidate.get("current_valid_substat_count") or 0) if candidate else 0
    feasible_valid = int(candidate.get("feasible_valid_substat_count") or 0) if candidate else 0
    return {
        "candidate": candidate,
        "category": candidate.get("category") if candidate else "未命中",
        "probability": probability,
        "future75_probability": float(future["terminal_future_75_probability"]),
        "current_valid": current_valid,
        "feasible_valid": feasible_valid,
        "full_four": bool(eligible and current_valid == 4),
        "three_conversion": bool(candidate and current_valid >= 3 and candidate.get("is_conversion_candidate")),
        "slot_limited_three": bool(candidate and candidate.get("slot_limited_three_valid_path")),
        "effective_gs": float(evaluation.effective_score),
        "official_gs": float(official_score_for_stats(gear.substats)),
        "formal_low_gs": float(candidate.get("formal_terminal_gs_threshold") or 0.0) if candidate else 0.0,
        "current_target_gs_ratio": (
            float(evaluation.effective_score) / float(candidate.get("formal_terminal_gs_threshold") or 1.0)
            if candidate else 0.0
        ),
        "white_right": _right_flat_main(gear),
    }


def _tier(value: float, continue_at: float, review_at: float) -> str:
    if value >= continue_at:
        return "continue"
    if value >= review_at:
        return "cautious_continue"
    return "stop"


def _category_action(features: dict[str, Any]) -> str:
    thresholds = {
        "输出": (0.12, 0.035), "输出(必爆)": (0.12, 0.035),
        "抗坦": (0.10, 0.030), "纯肉": (0.08, 0.025), "命坦": (0.10, 0.030),
        "双效": (0.16, 0.070), "半肉(血防)": (0.16, 0.070),
        "半肉(通用)": (0.16, 0.070), "半肉(白字)": (0.16, 0.070),
    }
    return _tier(features["probability"], *thresholds.get(features["category"], (0.18, 0.08)))


def _category_slot_gs_action(features: dict[str, Any]) -> str:
    """Use the documented category x slot low-tier GS target, never a global GS."""
    if not features["formal_low_gs"] or features["current_valid"] < 2:
        return "stop"
    ratio = features["current_target_gs_ratio"]
    if features["slot_limited_three"]:
        return _tier(ratio, 0.42, 0.26)
    return _tier(ratio, 0.48, 0.30)


def _category_slot_probability_action(features: dict[str, Any]) -> str:
    base = _category_slot_gs_action(features)
    if base == "stop" or features["probability"] < 0.015:
        return "stop"
    if base == "continue" and features["probability"] >= 0.08:
        return "continue"
    return "cautious_continue"


def _gs_efficiency_action(features: dict[str, Any]) -> str:
    # A study-only proxy: expected threshold GS per next-node stamina, not a released threshold.
    expected_gs = features["probability"] * features["formal_low_gs"]
    if expected_gs >= 5.0 and features["current_valid"] >= 3:
        return "continue"
    if expected_gs >= 1.8 and features["current_valid"] >= 2:
        return "cautious_continue"
    return "stop"


def _structural_action(features: dict[str, Any]) -> str:
    if features["full_four"] and features["feasible_valid"] >= 4:
        return "continue"
    if features["current_valid"] >= 3 or features["slot_limited_three"]:
        return "cautious_continue"
    return "stop"


def strategies() -> list[Strategy]:
    return [
        Strategy("A_current_review", "A 当前全部谨慎继续", lambda _: "cautious_continue"),
        Strategy("B_global_current_gs", "B 全局当前有效 GS 分层（对照）", lambda f: _tier(f["effective_gs"], 30.0, 18.0)),
        Strategy("C_category_probability", "C 分类终局达标概率", _category_action),
        Strategy("D_category_slot_gs", "D 分类×部位低档 GS", _category_slot_gs_action),
        Strategy("E_category_slot_main", "E 分类×部位×主属性限制", lambda f: "stop" if f["white_right"] and (f["current_valid"] < 3 or f["current_target_gs_ratio"] < 0.30) else _category_slot_gs_action(f)),
        Strategy("F_category_current_gs", "F 分类低档 GS 加当前目标 GS", lambda f: "continue" if _category_slot_gs_action(f) == "continue" and f["effective_gs"] >= 28 else "cautious_continue" if _category_slot_gs_action(f) != "stop" and f["effective_gs"] >= 16 else "stop"),
        Strategy("G_category_slot_probability", "G 分类×部位 GS 与终局概率混合", _category_slot_probability_action),
        Strategy("H_gs_stamina_efficiency", "H 预期终局 GS/下一节点体力", _gs_efficiency_action),
        Strategy("I_high_recall_efficiency", "I 高召回约束下 GS 效率", lambda f: "continue" if _gs_efficiency_action(f) == "continue" and f["probability"] >= 0.04 else "cautious_continue" if f["probability"] >= 0.02 and f["current_valid"] >= 2 else "stop"),
        Strategy("J_structure_conversion", "J 可行词条与合法转换", lambda f: "continue" if f["full_four"] else "cautious_continue" if f["three_conversion"] or f["slot_limited_three"] else "stop"),
    ]


def strategy_actions(gear: Gear, item_source: str) -> dict[str, str]:
    speed_hard = _speed_hard_route(gear)
    features = _features(gear, item_source)
    actions = {}
    for strategy in strategies():
        action = "continue" if speed_hard else strategy.decide(features)
        if action not in ACTIONS:
            raise ValueError(f"invalid action from {strategy.key}: {action}")
        actions[strategy.key] = action
    return actions


def _gear_after_max_conversion(gear: Gear, conversion: dict[str, Any]) -> Gear:
    candidate = conversion.get("conversion_candidate") or {}
    target_key = str(conversion.get("conversion_target_stat") or "")
    source = next(
        (stat for stat in gear.substats if stat.key == candidate.get("key") and stat.rolls == candidate.get("rolls")),
        None,
    )
    if source is None or not target_key:
        return gear
    converted_value = expected_terminal_modification_max_value(gear, source, target_key)
    converted_type = STAT_TYPE_BY_KEY.get(target_key, target_key)
    converted = []
    replaced = False
    for stat in gear.substats:
        if not replaced and stat is source:
            converted.append(Stat(converted_type, converted_value, rolls=stat.rolls, modified=True))
            replaced = True
        else:
            converted.append(stat)
    return replace(gear, substats=converted)


def _terminal_metrics(gear: Gear, item_source: str) -> dict[str, Any]:
    final = reforge_gear(gear)
    evaluation = evaluate_gear(final)
    native_formal = bool(evaluation.retention.rule_matched)
    conversion = conversion_plan_for_gear(final, item_source, evaluation)
    converted_gear = _gear_after_max_conversion(final, conversion) if conversion.get("conversion_needed") else final
    converted_evaluation = evaluate_gear(converted_gear)
    conversion_formal = bool(not native_formal and conversion.get("conversion_needed") and converted_evaluation.retention.rule_matched)
    speed_success = final.slot != "boot" and speed_value(final) >= 22
    gs75 = official_score_for_stats(final.substats) >= 75
    high_value = native_formal or gs75 or speed_success or conversion_formal
    speed_stat = next((stat for stat in final.substats if stat.key == "spd"), None)
    final_speed = speed_value(final)
    speed_potential = 0.0
    if speed_stat and speed_stat.rolls > 1 and (speed_potential_set_eligible(final.set) or final_speed >= 20):
        speed_potential = final_speed * (speed_stat.rolls - 1)
    formal_value = float(evaluation.retention.score)
    formal_or_speed = max(formal_value, speed_potential)
    converted_formal_value = float(converted_evaluation.retention.score)
    converted_terminal_value = max(converted_formal_value, speed_potential)
    return {
        "formal": native_formal,
        "gs75": gs75,
        "speed": speed_success,
        "conversion": conversion_formal,
        "conversion_needed": conversion_formal and not native_formal,
        "high_value": high_value,
        "target_effective_gs": float(evaluation.effective_score),
        "official_substat_gs": float(official_score_for_stats(final.substats)),
        "converted_official_substat_gs": float(official_score_for_stats(converted_gear.substats)),
        "formal_value": formal_value,
        "converted_formal_value": converted_formal_value,
        "speed_potential_value": speed_potential,
        "final_speed": final_speed,
        "formal_or_speed_value": formal_or_speed,
        "converted_target_effective_gs": float(converted_evaluation.effective_score),
        "converted_terminal_value": converted_terminal_value,
    }


def _terminal_formal_value(terminal: dict[str, Any]) -> float:
    if terminal["conversion"]:
        return float(terminal["converted_formal_value"])
    return float(terminal["formal_value"]) if terminal["formal"] else 0.0


def formal_followup_action(gear: Gear, item_source: str) -> bool:
    """Apply the configured formal follow-up policy at +6/+9/+12 without changing it."""
    default = default_strategy_for(item_source=item_source, rank=gear.rank, gear_source=GEAR_SOURCE)
    policy = policies_by_name(item_source, gear.rank)[default.policy_name]
    return bool(should_continue(gear, base_policy_for(policy), item_source))


def simulate_strategy_path(
    path: dict[int, Gear],
    item_source: str,
    strategy: Strategy,
    *,
    formal_followup: Callable[[Gear], bool] | None = None,
    early_action: Callable[[Gear], str] | None = None,
) -> dict[str, Any]:
    """Run one complete path with next-node semantics and stop-node recovery."""
    start = min(path)
    current = start
    actions: dict[int, str] = {}
    reached = [current]
    formal_followup = formal_followup or (lambda state: formal_followup_action(state, item_source))
    while current < 15:
        state = path[current]
        if current in (0, 3):
            if early_action:
                action = early_action(state)
            elif _speed_hard_route(state):
                action = "continue"
            else:
                action = strategy_actions(state, item_source).get(strategy.key, strategy.decide(_features(state, item_source)))
        else:
            action = "continue" if formal_followup(state) else "stop"
        actions[current] = action
        if action == "stop":
            break
        next_point = next(point for point in CHECKPOINTS if point > current)
        current = next_point
        reached.append(current)
    stop = current
    costs = summarize_incremental_cost(path[start].slot, path[start].rank, start, stop)
    return {
        "start_checkpoint": start,
        "stop_checkpoint": stop,
        "actions": actions,
        "reached_checkpoints": reached,
        "net_stamina": costs["net_stamina"],
        "net_gold": costs["net_gold"],
        "costs": costs,
    }


def _heroic_base_action(gear: Gear, item_source: str) -> str:
    default = default_strategy_for(item_source=item_source, rank="Heroic", gear_source=GEAR_SOURCE)
    policy = policies_by_name(item_source, "Heroic")[default.policy_name]
    return "continue" if should_continue(gear, policy, item_source) else "stop"


def heroic_fixed_baseline_summary(
    gears: Iterable[Gear],
    item_source: str,
    *,
    runs: int,
    seed: int,
    stop_all: bool = False,
) -> dict[str, Any]:
    """Evaluate the fixed, unpublished-lambda Heroic fallback for joint research."""
    default = default_strategy_for(item_source=item_source, rank="Heroic", gear_source=GEAR_SOURCE)
    gear_list = list(gears)
    total_paths = 0
    total_stamina = total_gold = total_value = 0.0
    converted_paths = terminal_paths = 0
    placeholder = Strategy("heroic_fixed", "Heroic 固定基础回退", lambda _: "stop")
    for index, gear in enumerate(gear_list):
        if gear.rank != "Heroic":
            raise ValueError("heroic_fixed_baseline_summary only accepts Heroic gears")
        paths = simulate_paths(gear, item_source, runs, seed + index * 100003)
        for path in paths:
            action = (lambda _: "stop") if stop_all else (lambda state: _heroic_base_action(state, item_source))
            outcome = simulate_strategy_path(
                path,
                item_source,
                placeholder,
                formal_followup=lambda state: _heroic_base_action(state, item_source) == "continue",
                early_action=action,
            )
            stop = outcome["stop_checkpoint"]
            terminal = _terminal_metrics(path[stop], item_source)
            conversion_needed = bool(stop == 15 and terminal["conversion_needed"])
            conversion_stamina = conversion_stamina_cost(DEFAULT_CONVERSION_GOLD_COST, calibration_for_rank("Heroic")) if conversion_needed else 0.0
            total_paths += 1
            total_stamina += float(outcome["net_stamina"]) + conversion_stamina
            total_gold += float(outcome["net_gold"]) + (DEFAULT_CONVERSION_GOLD_COST if conversion_needed else 0.0)
            if stop == 15:
                terminal_paths += 1
                total_value += _terminal_formal_value(terminal)
                converted_paths += int(conversion_needed)
    divisor = total_paths or 1
    return {
        "rank": "Heroic",
        "policy_name": default.policy_name if not stop_all else "all_stop_sensitivity",
        "resource_calibration_status": default.resource_calibration_status,
        "dp_enabled": False,
        "stop_all": stop_all,
        "source_gear_count": len(gear_list),
        "sample_paths": total_paths,
        "average_incremental_stamina": total_stamina / divisor,
        "average_incremental_gold": total_gold / divisor,
        "expected_terminal_formal_value_at_15": total_value / divisor,
        "terminal_reach_rate": terminal_paths / divisor,
        "conversion_path_rate": converted_paths / divisor,
        "cost_accounting": "post-current-node upgrade, stop recovery, and legal conversion only; source acquisition is batch-level",
    }


def _signature(gear: Gear) -> tuple[Any, ...]:
    return (gear.slot, gear.main_stat.key, gear.enhance, tuple((stat.key, stat.normalized_value, stat.rolls) for stat in gear.substats))


def _empty_row(strategy: Strategy) -> dict[str, Any]:
    return {
        "label": strategy.label,
        "total": 0,
        "actions0": Counter(), "actions3": Counter(), "reached": Counter(), "stopped": Counter(),
        "stamina": 0.0, "gold": 0.0,
        "formal": 0, "gs75": 0, "speed": 0, "conversion": 0, "high_value": 0,
        "target_effective_gs": 0.0, "official_substat_gs": 0.0,
        "formal_value": 0.0, "speed_potential_value": 0.0,
        "formal_or_speed_value": 0.0, "converted_terminal_value": 0.0,
        "terminal_formal_value_at_15": 0.0,
        "target_effective_gs_delta": 0.0, "terminal_value_delta": 0.0,
        "interval_stamina": Counter(), "interval_gold": Counter(), "interval_transitions": Counter(),
        "by_slot": {},
        "by_main": {},
        "by_category": {},
        "segments": Counter(),
    }


def _add_breakdown(row: dict[str, Any], group: str, key: str, stamina: float, high: bool, terminal: dict[str, Any]) -> None:
    bucket = row[group].setdefault(key, Counter())
    bucket["total"] += 1
    bucket["stamina"] += stamina
    bucket["high_value"] += int(high)
    bucket["target_effective_gs"] += terminal["target_effective_gs"]
    bucket["formal_or_speed_value"] += terminal["formal_or_speed_value"]


def _evaluate_one_gear(gear: Gear, item_source: str, runs: int, seed: int) -> dict[str, Any]:
    strategy_list = strategies()
    rows = {strategy.key: _empty_row(strategy) for strategy in strategy_list}
    paths = simulate_paths(gear, item_source, runs, seed)
    action_cache: dict[tuple[Any, ...], dict[str, str]] = {}
    followup_cache: dict[tuple[Any, ...], bool] = {}
    terminal_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    category_cache: dict[tuple[Any, ...], str] = {}
    calibration = calibration_for_rank("Epic")
    conversion_stamina = conversion_stamina_cost(DEFAULT_CONVERSION_GOLD_COST, calibration)
    for path in paths:
        start_signature = _signature(path[0])
        current_terminal = terminal_cache.get(start_signature)
        if current_terminal is None:
            current_terminal = _terminal_metrics(path[0], item_source)
            terminal_cache[start_signature] = current_terminal
        category = category_cache.get(start_signature)
        if category is None:
            category = str(_features(path[0], item_source)["category"])
            category_cache[start_signature] = category

        def cached_early_action(state: Gear, strategy_key: str) -> str:
            signature = _signature(state)
            actions = action_cache.get(signature)
            if actions is None:
                actions = strategy_actions(state, item_source)
                action_cache[signature] = actions
            return actions[strategy_key]

        def cached_formal_followup(state: Gear) -> bool:
            signature = _signature(state)
            decision = followup_cache.get(signature)
            if decision is None:
                decision = formal_followup_action(state, item_source)
                followup_cache[signature] = decision
            return decision

        start_hard = _speed_hard_route(path[0])
        plus3_hard = _speed_hard_route(path[3])
        segment = "速度硬路线" if start_hard else "速度命中后进入硬路线" if plus3_hard else "原生非速度+3"
        for strategy in strategy_list:
            outcome = simulate_strategy_path(
                path,
                item_source,
                strategy,
                formal_followup=cached_formal_followup,
                early_action=lambda state, key=strategy.key: cached_early_action(state, key),
            )
            stop = outcome["stop_checkpoint"]
            stop_signature = _signature(path[stop])
            terminal = terminal_cache.get(stop_signature)
            if terminal is None:
                terminal = _terminal_metrics(path[stop], item_source)
                terminal_cache[stop_signature] = terminal
            extra_stamina = conversion_stamina if stop == 15 and terminal["conversion_needed"] else 0.0
            extra_gold = DEFAULT_CONVERSION_GOLD_COST if stop == 15 and terminal["conversion_needed"] else 0.0
            stamina = outcome["net_stamina"] + extra_stamina
            gold = outcome["net_gold"] + extra_gold
            row = rows[strategy.key]
            row["total"] += 1
            row["actions0"][outcome["actions"].get(0, "stop")] += 1
            if 3 in outcome["actions"]:
                row["actions3"][outcome["actions"][3]] += 1
            row["stopped"][stop] += 1
            for point in outcome["reached_checkpoints"]:
                row["reached"][point] += 1
            reached = outcome["reached_checkpoints"]
            for previous, point in zip(reached, reached[1:]):
                interval = summarize_incremental_cost(gear.slot, "Epic", previous, point)
                row["interval_stamina"][point] += interval["net_stamina"]
                row["interval_gold"][point] += interval["net_gold"]
                row["interval_transitions"][point] += 1
            if stop == 15:
                for metric in ("formal", "gs75", "speed", "conversion", "high_value"):
                    row[metric] += int(terminal[metric])
                row["terminal_formal_value_at_15"] += _terminal_formal_value(terminal)
            row["stamina"] += stamina
            row["gold"] += gold
            for metric in ("target_effective_gs", "official_substat_gs", "formal_value", "speed_potential_value", "formal_or_speed_value", "converted_terminal_value"):
                row[metric] += terminal[metric]
            row["target_effective_gs_delta"] += terminal["target_effective_gs"] - current_terminal["target_effective_gs"]
            row["terminal_value_delta"] += terminal["formal_or_speed_value"] - current_terminal["formal_or_speed_value"]
            row["segments"][segment] += 1
            _add_breakdown(row, "by_slot", gear.slot, stamina, stop == 15 and terminal["high_value"], terminal)
            _add_breakdown(row, "by_main", gear.main_stat.key, stamina, stop == 15 and terminal["high_value"], terminal)
            _add_breakdown(row, "by_category", str(category), stamina, stop == 15 and terminal["high_value"], terminal)
    return rows


def _merge_rows(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in (
        "total", "stamina", "gold", "formal", "gs75", "speed", "conversion", "high_value",
        "target_effective_gs", "official_substat_gs", "formal_value", "speed_potential_value",
        "formal_or_speed_value", "converted_terminal_value", "terminal_formal_value_at_15", "target_effective_gs_delta", "terminal_value_delta",
    ):
        target[field] += source[field]
    for field in ("actions0", "actions3", "reached", "stopped", "segments", "interval_stamina", "interval_gold", "interval_transitions"):
        target[field].update(source[field])
    for group in ("by_slot", "by_main", "by_category"):
        for key, value in source[group].items():
            target[group].setdefault(key, Counter()).update(value)


def _finalize_breakdown(source: dict[str, Counter]) -> dict[str, Any]:
    return {
        key: {
            "paths": value["total"],
            "average_incremental_stamina": value["stamina"] / value["total"] if value["total"] else 0.0,
            "high_value_rate": value["high_value"] / value["total"] if value["total"] else 0.0,
            "expected_terminal_target_gs": value["target_effective_gs"] / value["total"] if value["total"] else 0.0,
            "expected_terminal_formal_or_speed_value": value["formal_or_speed_value"] / value["total"] if value["total"] else 0.0,
        }
        for key, value in sorted(source.items())
    }


def _wilson(successes: int, total: int) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    z = 1.96
    p = successes / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    half = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return [max(0.0, center - half), min(1.0, center + half)]


def _finalize_row(row: dict[str, Any]) -> dict[str, Any]:
    total = row["total"] or 1
    def rate(metric: str) -> float:
        return row[metric] / total
    average_stamina = row["stamina"] / total
    average_gold = row["gold"] / total
    target_gs_delta = row["target_effective_gs_delta"] / total
    terminal_value_delta = row["terminal_value_delta"] / total
    interval_costs = {
        str(point): {
            "conditional_average_stamina": row["interval_stamina"][point] / row["interval_transitions"][point] if row["interval_transitions"][point] else 0.0,
            "conditional_average_gold": row["interval_gold"][point] / row["interval_transitions"][point] if row["interval_transitions"][point] else 0.0,
            "transition_rate": row["interval_transitions"][point] / total,
        }
        for point in CHECKPOINTS[1:]
    }
    return {
        "label": row["label"],
        "sample_paths": row["total"],
        "actions_plus0": {action: row["actions0"][action] / total for action in ACTIONS},
        "actions_plus3": {action: row["actions3"][action] / total for action in ACTIONS},
        "reached_checkpoints": {str(point): row["reached"][point] / total for point in CHECKPOINTS},
        "stopped_at_checkpoints": {str(point): row["stopped"][point] / total for point in CHECKPOINTS},
        "average_incremental_stamina": average_stamina,
        "average_incremental_gold": average_gold,
        "next_node_costs": interval_costs,
        "actual_end_to_end_cost": {"stamina": average_stamina, "gold": average_gold},
        "formal_success_rate": rate("formal"), "formal_success_wilson95": _wilson(row["formal"], total),
        "terminal_gs75_rate": rate("gs75"), "terminal_gs75_wilson95": _wilson(row["gs75"], total),
        "speed_success_rate": rate("speed"), "speed_success_wilson95": _wilson(row["speed"], total),
        "conversion_success_rate": rate("conversion"), "conversion_success_wilson95": _wilson(row["conversion"], total),
        "high_value_success_rate": rate("high_value"), "high_value_wilson95": _wilson(row["high_value"], total),
        "stamina_per_high_value_success": row["stamina"] / row["high_value"] if row["high_value"] else None,
        "expected_terminal_target_gs": row["target_effective_gs"] / total,
        "expected_terminal_official_substat_gs": row["official_substat_gs"] / total,
        "expected_terminal_formal_value": row["formal_value"] / total,
        "expected_terminal_formal_value_at_15": row["terminal_formal_value_at_15"] / total,
        "expected_terminal_speed_potential_value": row["speed_potential_value"] / total,
        "expected_terminal_formal_or_speed_value": row["formal_or_speed_value"] / total,
        "expected_terminal_converted_value": row["converted_terminal_value"] / total,
        "expected_terminal_target_gs_delta_vs_current_stop": target_gs_delta,
        "expected_terminal_value_delta_vs_current_stop": terminal_value_delta,
        "expected_target_gs_per_100_stamina": 100 * target_gs_delta / average_stamina if average_stamina else 0.0,
        "stamina_per_expected_target_gs": average_stamina / target_gs_delta if target_gs_delta > 0 else None,
        "expected_formal_value_per_100_stamina": 100 * terminal_value_delta / average_stamina if average_stamina else 0.0,
        "terminal_value_delta_per_gold": terminal_value_delta / average_gold if average_gold else 0.0,
        "by_slot": _finalize_breakdown(row["by_slot"]),
        "by_main_stat": _finalize_breakdown(row["by_main"]),
        "by_category": _finalize_breakdown(row["by_category"]),
        "segments": dict(row["segments"]),
    }


def _evaluate_job(args: tuple[Gear, str, int, int]) -> dict[str, Any]:
    return _evaluate_one_gear(*args)


def evaluate_strategies(gears: Iterable[Gear], item_source: str, runs: int, seed: int, workers: int = 1) -> dict[str, Any]:
    strategy_list = strategies()
    merged = {strategy.key: _empty_row(strategy) for strategy in strategy_list}
    jobs = [(gear, item_source, runs, seed + index * 100003) for index, gear in enumerate(gears)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for output in executor.map(_evaluate_job, jobs):
                for key, row in output.items():
                    _merge_rows(merged[key], row)
    else:
        for output in map(_evaluate_job, jobs):
            for key, row in output.items():
                _merge_rows(merged[key], row)
    return {key: _finalize_row(row) for key, row in merged.items()}


def _pareto_frontier(results: dict[str, Any]) -> list[str]:
    keys = list(results)
    return [
        key for key in keys
        if not any(
            other != key
            and results[other]["average_incremental_stamina"] <= results[key]["average_incremental_stamina"]
            and results[other]["expected_target_gs_per_100_stamina"] >= results[key]["expected_target_gs_per_100_stamina"]
            and results[other]["high_value_success_rate"] >= results[key]["high_value_success_rate"]
            and (
                results[other]["average_incremental_stamina"] < results[key]["average_incremental_stamina"]
                or results[other]["expected_target_gs_per_100_stamina"] > results[key]["expected_target_gs_per_100_stamina"]
                or results[other]["high_value_success_rate"] > results[key]["high_value_success_rate"]
            )
            for other in keys
        )
    ]


def _recommendations(results: dict[str, Any], frontier: list[str]) -> dict[str, str]:
    baseline = results["A_current_review"]
    candidates = frontier or list(results)
    recall = lambda key: results[key]["high_value_success_rate"] / baseline["high_value_success_rate"] if baseline["high_value_success_rate"] else 0.0
    resource = min((key for key in candidates if recall(key) >= 0.50), key=lambda key: results[key]["average_incremental_stamina"], default=min(candidates, key=lambda key: results[key]["average_incremental_stamina"]))
    high = max(candidates, key=lambda key: (recall(key), -results[key]["average_incremental_stamina"]))
    balanced_candidates = [key for key in candidates if key not in {resource, high} and recall(key) >= 0.70]
    balanced = min(balanced_candidates, key=lambda key: results[key]["average_incremental_stamina"], default=max(
        (key for key in candidates if key not in {resource, high}),
        key=lambda key: recall(key) - 0.35 * (results[key]["average_incremental_stamina"] / max(1.0, baseline["average_incremental_stamina"])),
        default=high,
    ))
    efficiency = max(
        (key for key in candidates if recall(key) >= 0.50),
        key=lambda key: results[key]["expected_target_gs_per_100_stamina"],
        default=high,
    )
    category_slot = "G_category_slot_probability" if "G_category_slot_probability" in results else balanced
    return {
        "省资源": resource,
        "平衡": balanced,
        "高召回": high,
        "GS/体力效率最高": efficiency,
        "分类×部位混合": category_slot,
    }


def _distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gears = [row["gear"] for row in rows]
    return {
        "count": len(gears),
        "slot": dict(Counter(gear.slot for gear in gears)),
        "main_stat": dict(Counter(gear.main_stat.key for gear in gears)),
        "speed_substat": sum(any(stat.key == "spd" for stat in gear.substats) for gear in gears),
        "mean_current_official_gs": mean(official_score_for_stats(gear.substats) for gear in gears) if gears else 0.0,
    }


def _source_rank_gears(source_payload: dict[str, Any], rank: str) -> list[Gear]:
    gears = []
    for item in source_payload.get("items") or []:
        if item.get("rank") != rank or int(item.get("enhance", -1)) != 0:
            continue
        gear = _gear_from_item(item)
        if gear.level == 85 and gear.rank == rank:
            gears.append(gear)
    return gears


def _joint_epic_inputs(
    non_speed: dict[str, dict[str, Any]],
    speed_hard: dict[str, dict[str, Any]],
    non_speed_count: int,
    speed_hard_count: int,
) -> dict[str, dict[str, float]]:
    """Blend fixed speed-route output with each non-speed Epic candidate."""
    total = non_speed_count + speed_hard_count
    if total <= 0:
        return {}
    inputs = {}
    for key, row in non_speed.items():
        fixed = speed_hard.get(key, {})
        inputs[key] = {
            "expected_terminal_formal_value_at_15": (
                non_speed_count * float(row["expected_terminal_formal_value_at_15"])
                + speed_hard_count * float(fixed.get("expected_terminal_formal_value_at_15") or 0.0)
            ) / total,
            "average_incremental_stamina": (
                non_speed_count * float(row["average_incremental_stamina"])
                + speed_hard_count * float(fixed.get("average_incremental_stamina") or 0.0)
            ) / total,
        }
    return inputs


def _category_slot_threshold_matrix(rows: list[dict[str, Any]], item_source: str) -> list[dict[str, Any]]:
    """Observed study groups and their 6.4 low-tier GS target, not published rules."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        features = _features(row["gear"], item_source)
        candidate = features["candidate"]
        if not candidate or not features["formal_low_gs"]:
            continue
        key = (str(features["category"]), row["gear"].slot, row["gear"].main_stat.key)
        groups[key].append(features)
    return [
        {
            "category": category,
            "slot": slot,
            "main_stat": main_stat,
            "sample_count": len(values),
            "low_tier_terminal_gs": values[0]["formal_low_gs"],
            "mean_current_target_gs": round(mean(value["effective_gs"] for value in values), 3),
            "mean_current_ratio_to_low_tier": round(mean(value["current_target_gs_ratio"] for value in values), 4),
            "mean_feasible_valid_substats": round(mean(value["feasible_valid"] for value in values), 3),
            "slot_limited_three_path": any(value["slot_limited_three"] for value in values),
        }
        for (category, slot, main_stat), values in sorted(groups.items())
    ]


def holdout_matrix(holdout: list[dict[str, Any]], strategy: Strategy) -> dict[str, Any]:
    matrix = {tool: {human: 0 for human in ACTIONS} for tool in ACTIONS}
    speed_rows = 0
    corrected_continue = corrected_stop = retained = baseline_consistent = baseline_consistent_retained = 0
    for row in holdout:
        gear, human = row["gear"], row["human"]
        hard = _speed_hard_route(gear)
        tool = "continue" if hard else strategy.decide(_features(gear, "normal_85"))
        current_tool = "continue" if hard else "cautious_continue"
        matrix[tool][human] += 1
        speed_rows += int(hard)
        if current_tool == human:
            baseline_consistent += 1
            baseline_consistent_retained += int(tool == human)
        if current_tool == "cautious_continue" and human == "continue" and tool == "continue":
            corrected_continue += 1
        if current_tool == "cautious_continue" and human == "stop" and tool == "stop":
            corrected_stop += 1
        if tool == human:
            retained += 1
    total = sum(sum(row.values()) for row in matrix.values())
    return {
        "matrix": matrix,
        "accuracy": retained / total if total else 0.0,
        "human_continue_matched": corrected_continue,
        "human_stop_corrected": corrected_stop,
        "consistent_retained": retained,
        "baseline_consistent": baseline_consistent,
        "baseline_consistent_retained": baseline_consistent_retained,
        "speed_hard_rows": speed_rows,
    }


def _blind_payload(partition: dict[str, Any], seed: int) -> dict[str, Any]:
    return {
        "items": [row["item"] for row in partition["blind"]],
        "strategy_predictions": [
            {
                "instance_id": row["instance_id"],
                "actions": strategy_actions(row["gear"], "normal_85"),
            }
            for row in partition["blind"]
        ],
        "heroes": [],
        "acceptance_subset": {
            "batch_id": "epic_non_speed_blind_20260712",
            "batch_name": "Epic 非速度早期策略盲测（2026-07-12）",
            "purpose": "冻结后验证 Epic 非速度 +0 三分类候选，不用于门槛选择。",
            "selection_rule": "按部位、右三白字主属性和速度副属性分层固定抽取；速度硬路线已剥离。",
            "seed": seed,
        },
    }


def _resource_scopes() -> dict[str, Any]:
    return {
        "decision_efficiency": {
            "gear_acquisition_cost": "excluded as sunk",
            "includes": ["post-current-node upgrade materials", "stop-node sale recovery", "accessory 1.3 material scarcity", "legal +15 conversion gold"],
        },
        "full_chain_efficiency": {
            "normal_85": {
                "status": "riftslash_joint_batch_research_only",
                "reason": "uses one shared riftslash Epic/Heroic source batch; it is not written back as a per-item source",
            },
            "rift_85": {
                "status": "sensitivity_only",
                "reason": "rift acquisition gross cost is unconfirmed; no fixed conclusion is published",
            },
        },
    }


def run_analysis(
    source_path: Path,
    records_path: Path,
    *,
    runs: int = 5000,
    seed: int = 20260712,
    workers: int = 1,
    blind_size: int = DEFAULT_BLIND_SIZE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    partition = build_partition(source, records, blind_size=blind_size, seed=seed)
    normal_gears = [row["gear"] for row in partition["training"]]
    speed_hard_gears = [row["gear"] for row in partition["speed_hard"]]
    heroic_gears = _source_rank_gears(source, "Heroic")
    rift_pairs = [paired_rift_gear(gear) for gear in normal_gears]
    rift_non_speed = [gear for gear in rift_pairs if not _speed_hard_route(gear)]
    normal_results = evaluate_strategies(normal_gears, "normal_85", runs, seed, workers)
    speed_hard_results = evaluate_strategies(speed_hard_gears, "normal_85", runs, seed + 701, workers) if speed_hard_gears else {}
    rift_results = evaluate_strategies(rift_non_speed, "rift_85", runs, seed, workers) if rift_non_speed else {}
    heroic_baseline = heroic_fixed_baseline_summary(heroic_gears, "normal_85", runs=runs, seed=seed + 1403)
    heroic_all_stop = heroic_fixed_baseline_summary(heroic_gears, "normal_85", runs=runs, seed=seed + 1403, stop_all=True)
    joint_epic = _joint_epic_inputs(normal_results, speed_hard_results, len(normal_gears), len(speed_hard_gears))
    joint_batch = riftslash_joint_batch_metrics(joint_epic, heroic_baseline, heroic_all_stop)
    baseline = normal_results["A_current_review"]
    for result in normal_results.values():
        result["resource_saved_vs_current"] = baseline["average_incremental_stamina"] - result["average_incremental_stamina"]
        result["gold_saved_vs_current"] = baseline["average_incremental_gold"] - result["average_incremental_gold"]
        result["high_value_recall_vs_current"] = result["high_value_success_rate"] / baseline["high_value_success_rate"] if baseline["high_value_success_rate"] else 0.0
    frontier = _pareto_frontier(normal_results)
    recommendations = _recommendations(normal_results, frontier)
    strategy_by_key = {strategy.key: strategy for strategy in strategies()}
    data = {
        "metadata": {
            "rank": "Epic", "runs_per_training_gear": runs, "seed": seed, "workers": workers,
            "acquisition_cost": "excluded as sunk at +0/+3",
            "resource_model": "50/50 powder/lower-stone, accessory scarcity 1.3, sell recovery included",
            "conversion_gold_cost": DEFAULT_CONVERSION_GOLD_COST,
            "normal_source": "normal_85", "rift_status": "synthetic legal paired states only; no published rift threshold",
            "set_handling": "real samples retain their supplied Gear.set; no set pool or selected_sets is used",
            "joint_riftslash_scope": "research-only shared Epic/Heroic batch; Epic candidates are optimized while Heroic remains fixed",
        },
        "resource_scopes": _resource_scopes(),
        "conditional_generation": conditional_generation_summary(seed),
        "partition": {
            "training": _distribution(partition["training"]), "blind": _distribution(partition["blind"]),
            "holdout": {"count": len(partition["holdout"]), "enhance": dict(Counter(row["gear"].enhance for row in partition["holdout"]))},
            "speed_hard_excluded": _distribution(partition["speed_hard"]),
            "rift_pairs_becoming_speed_hard": len(rift_pairs) - len(rift_non_speed),
            "identity_sets": {key: sorted(value) for key, value in (("training", partition["training_ids"]), ("blind", partition["blind_ids"]), ("holdout", partition["holdout_ids"]), ("speed_hard", partition["speed_hard_ids"]))},
        },
        "category_slot_thresholds": _category_slot_threshold_matrix(partition["training"], "normal_85"),
        "normal_85": {"results": normal_results, "pareto_frontier": frontier, "recommendations": recommendations},
        "riftslash_joint_batch_research": {
            "study_status": "pilot_not_for_release" if runs < 5000 else "research_not_for_release",
            "epic_development_count": len(normal_gears),
            "epic_fixed_speed_hard_count": len(speed_hard_gears),
            "heroic_source_count": len(heroic_gears),
            "heroic_baseline": heroic_baseline,
            "heroic_all_stop_sensitivity": heroic_all_stop,
            "metrics": joint_batch,
        },
        "rift_85_research_only": {"results": rift_results, "paired_non_speed_states": len(rift_non_speed)},
        "holdout": {label: holdout_matrix(partition["holdout"], strategy_by_key[key]) for label, key in recommendations.items()},
    }
    return data, _blind_payload(partition, seed)


def postprocess_existing(data: dict[str, Any], source_path: Path, records_path: Path) -> dict[str, Any]:
    """Refresh Pareto selections and frozen holdout views without re-simulation."""
    source = json.loads(source_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    partition = build_partition(
        source,
        records,
        blind_size=int(data["partition"]["blind"]["count"]),
        seed=int(data["metadata"]["seed"]),
    )
    normal = data["normal_85"]
    normal["pareto_frontier"] = _pareto_frontier(normal["results"])
    normal["recommendations"] = _recommendations(normal["results"], normal["pareto_frontier"])
    data["resource_scopes"] = _resource_scopes()
    data["metadata"]["set_handling"] = "real samples retain their supplied Gear.set; no set pool or selected_sets is used"
    data["conditional_generation"] = conditional_generation_summary(int(data["metadata"]["seed"]))
    strategy_by_key = {strategy.key: strategy for strategy in strategies()}
    data["holdout"] = {
        label: holdout_matrix(partition["holdout"], strategy_by_key[key])
        for label, key in normal["recommendations"].items()
    }
    return data


def markdown_report(data: dict[str, Any]) -> str:
    normal = data["normal_85"]
    rows = normal["results"]
    joint = data.get("riftslash_joint_batch_research")

    def interval(row: dict[str, Any], rate_key: str, interval_key: str) -> str:
        low, high = row[interval_key]
        return f"{row[rate_key]:.2%} [{low:.2%}, {high:.2%}]"

    lines = [
        "# Epic 非速度 +0/+3 早期策略 Pareto 离线研究（2026-07-12）", "",
        "## 口径", "",
        "本研究不修改正式策略。已审核 22 件全部冻结为人工 holdout；固定速度硬路线不进入非速度门槛训练。",
        f"训练/盲测/holdout/速度剥离：{data['partition']['training']['count']} / {data['partition']['blind']['count']} / {data['partition']['holdout']['count']} / {data['partition']['speed_hard_excluded']['count']} 件；每件 {data['metadata']['runs_per_training_gear']:,} 条公共完整轨迹；seed={data['metadata']['seed']}。",
        "主口径为已获得装备的强化决策效率：胚子成本为沉没成本，停止回收、50/50 材料、饰品 1.3 系数和合法满值转换 100,000 金币均按实际停止节点计入。+0/+3 的继续与谨慎继续均只到下一节点；+6/+9/+12 使用现行正式基础后续策略重新判定。",
        "辅助全链路口径未合并进主指标：本批 Fribbels 样本只有 itemSource=normal_85，没有逐件明确 gear_source，故 normal 不虚构胚子成本；rift 胚子毛成本未确认，只保留敏感性研究，均不输出固定全链路终局体力。Wilson 95% 区间仅描述模拟路径误差。", "",
        "## 已知套装条件生成", "",
        "单件强化器只接收已经获得的装备。真实样本直接保留 JSON/GUI 提供的 `Gear.set`；策略和路径模拟不会重新随机套装。本离线工具不接收 `selected_sets`，不生成四套混合掉落，也不建立套装池或账号刷取规划。",
        f"条件接口：`{data['conditional_generation']['interface']}`。已生成 {data['conditional_generation']['coverage_sample_count']} 个仅作覆盖的合法条件样本；各套装独立保存且覆盖 Heroic/Epic、六部位和所有合法主属性。",
        "条件样本标记为 `synthetic=true`、`generation_mode=conditional_set`，仅用于稀疏分类×部位×主属性×有效词条数的机制覆盖、单调性和条件概率研究，不混入真实训练分布、22 件 holdout、24 件盲测或发布门槛。",
        "核心边际强化成本把胚子和指定套装出现概率视为沉没成本；维度裂缝单件净成本仅作为来源参考。若未来只刷指定套装，普通单件成本约乘以 4 只能作为刷取规划敏感性，绝不进入 DP、自动建议或默认资源常量。",
        "",
        "## Normal 85 候选策略", "",
        "| 策略 | +0继续/谨慎/停 | +3继续/谨慎/停 | 实际端到端体力 | GS增量/100体力 | 终局目标GS | 正式或速度价值 | 高价值召回 | 节省体力 |", "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, row in rows.items():
        a0, a3 = row["actions_plus0"], row["actions_plus3"]
        lines.append(
            f"| {row['label']} | {a0['continue']:.1%}/{a0['cautious_continue']:.1%}/{a0['stop']:.1%} | {a3['continue']:.1%}/{a3['cautious_continue']:.1%}/{a3['stop']:.1%} | {row['average_incremental_stamina']:.2f} | {row['expected_target_gs_per_100_stamina']:.3f} | {row['expected_terminal_target_gs']:.2f} | {row['expected_terminal_formal_or_speed_value']:.2f} | {row['high_value_recall_vs_current']:.2%} | {row['resource_saved_vs_current']:.2f} |"
        )
    if joint:
        metrics = joint["metrics"]
        baseline_scenario = metrics["heroic_current_baseline"]["heroic_yield_baseline"]
        baseline_results = baseline_scenario["results"]
        heroic = joint["heroic_baseline"]
        all_stop = joint["heroic_all_stop_sensitivity"]
        lines.extend([
            "", "## 维度裂缝 Epic/Heroic 联合批次研究", "",
            "本节仅用于完整来源批次的离线性价比研究，不修改任何正式策略。以一批期望 1 件 Epic 的维度裂缝产出归一化，来源净获取体力只记一次；Heroic 是同时获得的副产出，禁止额外按 22.5 体力/件相加。",
            f"研究状态：`{joint['study_status']}`。",
            f"批次净获取体力 {metrics['metadata']['net_batch_acquisition_stamina']:.2f}；Heroic 期望产出 {metrics['metadata']['heroic_expected_per_batch']:.3f}（estimated，另做 ±20% 敏感性）。Epic 开发样本 {joint['epic_development_count']} 件，固定速度路线 {joint['epic_fixed_speed_hard_count']} 件，Heroic 来源样本 {joint['heroic_source_count']} 件。",
            f"固定 Heroic 基础回退：终局正式价值 {heroic['expected_terminal_formal_value_at_15']:.3f}/件，后续强化净体力 {heroic['average_incremental_stamina']:.3f}/件，DP 启用={heroic['dp_enabled']}；全停止敏感性价值 {all_stop['expected_terminal_formal_value_at_15']:.3f}/件。",
            "", "| Epic 候选 | 联合正式价值/100体力 | 每批总正式价值 | 每批总体力 | 相对当前 Epic 价值变化 | 相对当前 Epic 体力变化 | 联合价值率变化 |", "|---|---:|---:|---:|---:|---:|---:|",
        ])
        for key, result in baseline_results.items():
            lines.append(
                f"| {rows[key]['label']} | {result['full_chain_formal_value_per_100_stamina']:.3f} | "
                f"{result['total_terminal_formal_value_per_batch']:.3f} | {result['total_stamina_per_batch']:.3f} | "
                f"{result['epic_value_delta_vs_current']:.3f} | {result['epic_stamina_delta_vs_current']:.3f} | "
                f"{result['joint_value_rate_delta_vs_current']:.3f} |"
            )
        lines.extend([
            "",
            f"Heroic 基线/全停止以及 Heroic 产出率 ±20% 下，全部 Epic 候选排序{'稳定' if metrics['epic_candidate_order_stable'] else '不稳定'}。",
            "只有排序在上述 Heroic 敏感性均稳定时，Epic 候选才可进入新的 48 件独立验证；本研究不修改 Heroic 基础回退或 Heroic lambda。",
        ])
    lines.extend(["", "## 分类 × 部位 × 主属性低档 GS 表", "", "该表来自第 6.4 节正式低档 GS 目标，只展示训练中实际出现的组合；样本数不足的组合仅用于候选研究，不发布独立门槛。", "", "| 分类 | 部位 | 主属性 | 样本 | 终局低档GS | 当前目标GS均值 | 当前/低档比 | 可行有效词条 | 三条受限路径 |", "|---|---|---|---:|---:|---:|---:|---:|---|"])
    for item in data["category_slot_thresholds"]:
        lines.append(f"| {item['category']} | {item['slot']} | {item['main_stat']} | {item['sample_count']} | {item['low_tier_terminal_gs']:.1f} | {item['mean_current_target_gs']:.2f} | {item['mean_current_ratio_to_low_tier']:.3f} | {item['mean_feasible_valid_substats']:.2f} | {'是' if item['slot_limited_three_path'] else '否'} |")
    lines.extend(["", "## Pareto 前沿", "", "、".join(normal["pareto_frontier"]) or "无", "", "## 候选方案", ""])
    for label, key in normal["recommendations"].items():
        row = rows[key]
        holdout = data["holdout"][label]
        next3 = row["next_node_costs"]["3"]
        next6 = row["next_node_costs"]["6"]
        lines.append(f"- {label}：{row['label']}；+0→+3 条件体力 {next3['conditional_average_stamina']:.2f}，+3→+6 条件体力 {next6['conditional_average_stamina']:.2f}，实际端到端 {row['average_incremental_stamina']:.2f}；期望终局目标 GS {row['expected_terminal_target_gs']:.2f}，相对当前停止增量 {row['expected_terminal_target_gs_delta_vs_current_stop']:.3f}，GS/100体力 {row['expected_target_gs_per_100_stamina']:.3f}；高价值召回 {row['high_value_recall_vs_current']:.2%}，holdout 准确率 {holdout['accuracy']:.2%}。")
    lines.extend(["", "## 连续终局价值与置信区间", ""])
    lines.append("| 方案 | 正式体系达标（95% CI） | 终局 GS >=75（95% CI） | 速度价值（95% CI） | 满值转换达标（95% CI） | 高价值（95% CI） | 价值增量/金币 | 每个高价值终局体力 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for label, key in normal["recommendations"].items():
        row = rows[key]
        lines.append(
            f"| {label} | {interval(row, 'formal_success_rate', 'formal_success_wilson95')} | "
            f"{interval(row, 'terminal_gs75_rate', 'terminal_gs75_wilson95')} | "
            f"{interval(row, 'speed_success_rate', 'speed_success_wilson95')} | "
            f"{interval(row, 'conversion_success_rate', 'conversion_success_wilson95')} | "
            f"{interval(row, 'high_value_success_rate', 'high_value_wilson95')} | "
            f"{row['terminal_value_delta_per_gold']:.9f} | "
            f"{row['stamina_per_high_value_success'] if row['stamina_per_high_value_success'] is not None else '-'} |"
        )
    lines.extend(["", "## Holdout 与盲测", ""])
    for label, holdout in data["holdout"].items():
        matrix = holdout["matrix"]
        lines.extend([
            f"### {label} 三分类混淆矩阵（工具行/人工列）",
            "",
            "| 工具\\人工 | 继续 | 谨慎继续 | 停止 |",
            "|---|---:|---:|---:|",
            f"| 继续 | {matrix['continue']['continue']} | {matrix['continue']['cautious_continue']} | {matrix['continue']['stop']} |",
            f"| 谨慎继续 | {matrix['cautious_continue']['continue']} | {matrix['cautious_continue']['cautious_continue']} | {matrix['cautious_continue']['stop']} |",
            f"| 停止 | {matrix['stop']['continue']} | {matrix['stop']['cautious_continue']} | {matrix['stop']['stop']} |",
            "",
        ])
    lines.extend([
        "holdout 在门槛冻结后才运行，未反向调参。新盲测批次已另存，尚无人工标签；批次 JSON 为每件装备附带了所有冻结候选策略的三分类预测。",
        f"训练轨迹中“原生非速度 +3”为 {rows['A_current_review']['segments'].get('原生非速度+3', 0):,} 条；“+3 速度命中后进入硬路线”为 {rows['A_current_review']['segments'].get('速度命中后进入硬路线', 0):,} 条。固定速度硬路线在训练前已剥离，未计入任何非速度门槛。",
        "本批真实起始状态未产生“+3 速度未命中后退出保护”的训练轨迹；该分支仍由正式速度规则处理，非速度门槛不覆盖它。",
        f"rift_85 使用 {data['rift_85_research_only']['paired_non_speed_states']} 件合法量化映射状态独立跳值模拟；另有 {data['partition']['rift_pairs_becoming_speed_hard']} 件因 rift 初始高跳值进入固定速度路线。没有真实异界样本，任何 rift 门槛均不得发布。",
        "", "## 结论", "",
        "本报告仅提供 normal_85 Epic 的候选门槛和 Pareto 证据。只有在新盲测人工三分类完成、holdout 未出现不可接受的人工继续误停，并确认资源/召回取舍后，才可建立单独的正式策略修改任务。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Epic non-speed +0/+3 offline Pareto study")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--runs", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--blind-size", type=int, default=DEFAULT_BLIND_SIZE)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "epic_non_speed_early_policy_pareto_20260712.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "epic_non_speed_early_policy_pareto_20260712.md")
    parser.add_argument("--blind-output", type=Path, default=ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json")
    parser.add_argument("--synthetic-output", type=Path, default=ROOT / "samples" / "epic_conditional_set_coverage_20260712.json")
    parser.add_argument("--postprocess-json", type=Path)
    args = parser.parse_args()
    if args.postprocess_json:
        data = postprocess_existing(json.loads(args.postprocess_json.read_text(encoding="utf-8")), args.source, args.records)
        blind = _blind_payload(
            build_partition(
                json.loads(args.source.read_text(encoding="utf-8")),
                json.loads(args.records.read_text(encoding="utf-8")),
                blind_size=args.blind_size,
                seed=args.seed,
            ),
            args.seed,
        )
    else:
        data, blind = run_analysis(args.source, args.records, runs=max(1, args.runs), seed=args.seed, workers=max(1, args.workers), blind_size=max(1, args.blind_size))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.blind_output.parent.mkdir(parents=True, exist_ok=True)
    args.synthetic_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    args.markdown_output.write_text(markdown_report(data), encoding="utf-8")
    args.blind_output.write_text(json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8")
    args.synthetic_output.write_text(
        json.dumps({"samples": conditional_coverage_samples(args.seed)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
