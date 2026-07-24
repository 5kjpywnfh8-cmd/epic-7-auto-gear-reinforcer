from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
import math
import os
import random
from typing import Any

from .enhance_simulator import (
    CHECKPOINTS,
    RollProfile,
    STAT_TYPE_BY_KEY,
    SimulationOptions,
    clone_gear,
    cost_for_outcome,
    enhance_to_checkpoint,
    expected_roll_value,
    generate_gear,
    reforge_bonus_value,
    reforge_gear,
    roll_range as roll_range_for_key,
)
from .models import Gear, Stat, round1
from .resource_model import DEFAULT_CONVERSION_GOLD_COST, ResourceAmount, calibration_for_rank, conversion_stamina_cost, material_pool_for_slot
from .rules import CATEGORY_RULES, FORMULAS, OFFICIAL_SCORE_WEIGHTS, SET_GROUPS, STAT_KEY_LABELS, VALID_STATS
from .score_engine import (
    Evaluation,
    category_support_for_speed,
    evaluate_gear,
    main_allowed,
    rule_match_info,
    score_by_formula,
    score_non_speed_speed,
    score_one_speed,
    score_speed_set,
    speed_value,
    tier_non_speed_speed,
    tier_speed_set,
)


FINAL_EFFECTIVE_SCORE_MIN = 60
FINAL_VALID_SUBSTAT_MIN = 3
FINAL_SPEED_MIN = 22
TOP_POLICY_LIMIT = 5
CONVERSION_GOLD_COST_SCENARIOS = [DEFAULT_CONVERSION_GOLD_COST]


@dataclass(frozen=True)
class CalibrationOptions:
    runs: int = 5000
    seed: int = 1
    gear_source: str = "riftslash_20_buff"
    item_source: str = "normal_85"
    rank: str = "Epic"
    workers: int = 1
    top_limit: int = TOP_POLICY_LIMIT
    enable_dp_assist: bool = False
    dp_utility_margin: float = 0.1
    route_solver_sample_limit: int | None = None


@dataclass(frozen=True)
class Policy:
    name: str
    expected_score_min: dict[int, float]
    expected_speed_min: dict[int, float]
    valid_count_min: dict[int, int]
    family: str = "grid"
    conversion_friendly: bool = True
    decision_mode: str = "threshold"
    min_marginal_value_per_stamina: dict[int, float] | None = None
    marginal_score_scope: str = "formal_baili"
    marginal_variant: str = "global"
    base_policy_name: str | None = None
    dp_lambda_value: float | None = None
    dp_utility_margin: float = 0.1
    dp_conversion_gold_cost: float = DEFAULT_CONVERSION_GOLD_COST
    dp_checkpoints: tuple[int, ...] = (0, 3, 6, 9, 12)

    def thresholds(self) -> dict[str, Any]:
        return {
            "expected_final_target_score_min": {str(key): value for key, value in self.expected_score_min.items()},
            "expected_final_reforge_score_min": {str(key): value for key, value in self.expected_score_min.items()},
            "expected_final_reforge_speed_min": {str(key): value for key, value in self.expected_speed_min.items()},
            "valid_count_min": {str(key): value for key, value in self.valid_count_min.items()},
            "conversion_friendly": self.conversion_friendly,
            "decision_mode": self.decision_mode,
            "min_marginal_value_per_stamina": {str(key): value for key, value in (self.min_marginal_value_per_stamina or {}).items()},
            "marginal_score_scope": self.marginal_score_scope,
            "marginal_variant": self.marginal_variant,
            "base_policy_name": self.base_policy_name,
            "dp_lambda_value": self.dp_lambda_value,
            "dp_utility_margin": self.dp_utility_margin,
            "dp_conversion_gold_cost": self.dp_conversion_gold_cost,
            "dp_checkpoints": list(self.dp_checkpoints),
        }


DP_ASSIST_CONFIGS = {
    ("normal_85", "Epic"): {
        "name": "normal_epic_dp_assisted",
        "base_policy_name": "category_baili_marginal_mid",
        "cost_per_baili_score": 799.2,
        "calibration": "resource-material-mix-20260712 / 30000 runs / seeds 20260711,20260712,20260713 / merged numerator-denominator",
        "family": "DP assisted",
    },
    ("rift_85", "Epic"): {
        "name": "rift_epic_dp_assisted",
        "base_policy_name": "score_target_high_speed_mid",
        "cost_per_baili_score": 332.6,
        "calibration": "resource-material-mix-20260712 / 30000 runs / seeds 20260711,20260712,20260713 / merged numerator-denominator",
        "family": "DP assisted",
    },
}


def aggregate_resource_calibration_runs(run_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate resource calibration by raw numerator and denominator.

    A seed's ratio is diagnostic only.  Publication uses the merged stamina and
    formal Baili score so sparse Heroic seeds cannot be given equal weight.
    """
    rows = []
    for item in run_results:
        stamina = float(item.get("total_stamina") or 0.0)
        score = float(item.get("total_baili_score") or 0.0)
        successes = int(item.get("successes") or item.get("nonzero_terminal_count") or 0)
        rows.append(
            {
                "seed": item.get("seed"),
                "runs": int(item.get("runs") or item.get("calibration_runs") or 0),
                "total_stamina": stamina,
                "total_baili_score": score,
                "nonzero_terminal_count": successes,
                "cost_per_baili_score": stamina / score if score else None,
            }
        )
    total_stamina = sum(item["total_stamina"] for item in rows)
    total_baili_score = sum(item["total_baili_score"] for item in rows)
    seed_costs = [float(item["cost_per_baili_score"]) for item in rows if item["cost_per_baili_score"] is not None]
    mean_cost = sum(seed_costs) / len(seed_costs) if seed_costs else None
    if len(seed_costs) > 1 and mean_cost is not None:
        variance = sum((value - mean_cost) ** 2 for value in seed_costs) / (len(seed_costs) - 1)
        ci_half_width = 1.96 * math.sqrt(variance / len(seed_costs))
    else:
        ci_half_width = None
    merged_cost = total_stamina / total_baili_score if total_baili_score else None
    latter_rows = rows[len(rows) // 2 :] if len(rows) >= 2 else []
    latter_stamina = sum(item["total_stamina"] for item in latter_rows)
    latter_baili_score = sum(item["total_baili_score"] for item in latter_rows)
    latter_cost = latter_stamina / latter_baili_score if latter_baili_score else None
    latter_relative_deviation = abs(latter_cost / merged_cost - 1) if latter_cost is not None and merged_cost else None
    return {
        "seed_results": rows,
        "total_runs": sum(item["runs"] for item in rows),
        "total_stamina": total_stamina,
        "total_baili_score": total_baili_score,
        "nonzero_terminal_count": sum(item["nonzero_terminal_count"] for item in rows),
        "cost_per_baili_score": merged_cost,
        "lambda_value": 1 / merged_cost if merged_cost else None,
        "seed_cost_mean": mean_cost,
        "seed_cost_ci95_half_width": ci_half_width,
        "seed_cost_ci95_relative_half_width": (ci_half_width / mean_cost) if ci_half_width is not None and mean_cost else None,
        "latter_half_cost_per_baili_score": latter_cost,
        "latter_half_relative_deviation": latter_relative_deviation,
    }


def resource_calibration_publishable(aggregate: dict[str, Any], rank: str) -> bool:
    if not aggregate.get("cost_per_baili_score"):
        return False
    if rank == "Heroic" and int(aggregate.get("nonzero_terminal_count") or 0) < 200:
        return False
    relative_half_width = aggregate.get("seed_cost_ci95_relative_half_width")
    latter_half_deviation = aggregate.get("latter_half_relative_deviation")
    return (
        relative_half_width is not None
        and relative_half_width <= 0.10
        and latter_half_deviation is not None
        and latter_half_deviation <= 0.10
    )


def candidate_policies(
    include_dp_assist: bool = False,
    item_source: str | None = None,
    rank: str | None = None,
    dp_utility_margin: float = 0.1,
) -> list[Policy]:
    marginal_profiles = [
        Policy(
            "baili_marginal_low",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "百里边际收益",
            True,
            "marginal",
            {0: 0.0008, 3: 0.0010, 6: 0.0012, 9: 0.0018, 12: 0.0024},
        ),
        Policy(
            "baili_marginal_mid",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "百里边际收益",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
        ),
        Policy(
            "global_baili_marginal_mid",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "全局百里边际baseline",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
            "formal_baili",
            "global",
        ),
        Policy(
            "baili_marginal_high",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "百里边际收益",
            True,
            "marginal",
            {0: 0.0018, 3: 0.0022, 6: 0.0028, 9: 0.0038, 12: 0.0050},
        ),
        Policy(
            "target_marginal_mid",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "旧target边际对照",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
            "target_with_future",
        ),
        Policy(
            "set_group_baili_marginal_mid",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "套装组百里边际",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
            "formal_baili",
            "set_group",
        ),
        Policy(
            "category_baili_marginal_mid",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "分类百里边际",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
            "formal_baili",
            "category",
        ),
        Policy(
            "category_set_group_baili_marginal_mid",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "分类×套装组百里边际",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
            "formal_baili",
            "category_set_group",
        ),
        Policy(
            "speed_set_specialized",
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
            {0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
            "速度套专项百里边际",
            True,
            "marginal",
            {0: 0.0012, 3: 0.0015, 6: 0.0018, 9: 0.0026, 12: 0.0034},
            "formal_baili",
            "speed_set_specialized",
        ),
    ]
    strategy_profiles = [
        Policy(
            "score_strategy_early_loose_speed_low",
            {0: 0, 3: 0, 6: 0, 9: 2, 12: 5},
            {0: 13, 3: 15, 6: 17, 9: 19, 12: 20},
            {0: 2, 3: 2, 6: 2, 9: 3, 12: 3},
            "早期宽松",
            True,
        ),
        Policy(
            "score_strategy_balanced_speed_mid",
            {0: 0, 3: 0, 6: 1, 9: 3, 12: 6},
            {0: 14, 3: 16, 6: 18, 9: 20, 12: 21},
            {0: 2, 3: 2, 6: 3, 9: 3, 12: 3},
            "均衡",
            True,
        ),
        Policy(
            "score_strategy_plus6_tight_speed_mid",
            {0: 0, 3: 0, 6: 2, 9: 5, 12: 8},
            {0: 14, 3: 16, 6: 18, 9: 20, 12: 21},
            {0: 2, 3: 2, 6: 3, 9: 3, 12: 3},
            "+6 收紧",
            True,
        ),
        Policy(
            "score_strategy_late_strict_speed_high",
            {0: 0, 3: 0, 6: 1, 9: 6, 12: 10},
            {0: 15, 3: 17, 6: 19, 9: 21, 12: 22},
            {0: 2, 3: 2, 6: 3, 9: 3, 12: 3},
            "+9/+12 严格",
            True,
        ),
        Policy(
            "score_strategy_conversion_friendly_speed_low",
            {0: 0, 3: 0, 6: 0, 9: 2, 12: 4},
            {0: 13, 3: 15, 6: 17, 9: 19, 12: 20},
            {0: 2, 3: 2, 6: 2, 9: 2, 12: 2},
            "转换友好",
            True,
        ),
    ]
    score_profiles = {
        "score_target_open": {0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
        "score_target_low": {0: 0, 3: 0, 6: 0, 9: 1, 12: 2},
        "score_target_mid": {0: 0, 3: 0, 6: 1, 9: 3, 12: 5},
        "score_target_high": {0: 0, 3: 1, 6: 2, 9: 5, 12: 8},
        "score_low": {0: 32, 3: 38, 6: 45, 9: 52, 12: 58},
        "score_mid": {0: 35, 3: 41, 6: 48, 9: 55, 12: 60},
        "score_high": {0: 38, 3: 44, 6: 51, 9: 58, 12: 62},
        "score_baili_low": {0: 40, 3: 46, 6: 53, 9: 60, 12: 64},
        "score_baili_mid": {0: 42, 3: 49, 6: 56, 9: 63, 12: 66},
        "score_baili_high": {0: 44, 3: 52, 6: 59, 9: 66, 12: 68},
        "score_baili_elite": {0: 46, 3: 55, 6: 63, 9: 70, 12: 72},
        "score_baili_god": {0: 48, 3: 58, 6: 66, 9: 73, 12: 75},
        "score_baili_extreme": {0: 50, 3: 61, 6: 69, 9: 76, 12: 78},
    }
    speed_profiles = {
        "speed_low": {0: 13, 3: 15, 6: 17, 9: 19, 12: 20},
        "speed_mid": {0: 14, 3: 16, 6: 18, 9: 20, 12: 21},
        "speed_high": {0: 15, 3: 17, 6: 19, 9: 21, 12: 22},
    }
    valid_count_min = {0: 2, 3: 2, 6: 3, 9: 3, 12: 3}
    grid_profiles = [
        Policy(f"{score_name}_{speed_name}", score_min, speed_min, valid_count_min, "网格搜索", True)
        for score_name, score_min in score_profiles.items()
        for speed_name, speed_min in speed_profiles.items()
    ]
    policies = marginal_profiles + strategy_profiles + grid_profiles
    if include_dp_assist:
        policies.extend(dp_assisted_policies(item_source, rank, dp_utility_margin))
    return policies


def dp_assisted_policies(
    item_source: str | None = None,
    rank: str | None = None,
    dp_utility_margin: float = 0.1,
) -> list[Policy]:
    configs = []
    for (source, item_rank), config in DP_ASSIST_CONFIGS.items():
        if item_source is not None and source != item_source:
            continue
        if rank is not None and item_rank != rank:
            continue
        configs.append((source, item_rank, config))
    policies = []
    for _source, _rank, config in configs:
        cost = float(config["cost_per_baili_score"])
        policies.append(
            Policy(
                name=str(config["name"]),
                expected_score_min={0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
                expected_speed_min={0: 0, 3: 0, 6: 0, 9: 0, 12: 0},
                valid_count_min={0: 1, 3: 1, 6: 1, 9: 1, 12: 1},
                family=str(config["family"]),
                conversion_friendly=True,
                decision_mode="dp_assisted",
                min_marginal_value_per_stamina=None,
                marginal_score_scope="formal_baili",
                marginal_variant="global",
                base_policy_name=str(config["base_policy_name"]),
                dp_lambda_value=1 / cost if cost else 0.0,
                dp_utility_margin=dp_utility_margin,
                dp_conversion_gold_cost=DEFAULT_CONVERSION_GOLD_COST,
                dp_checkpoints=(0, 3, 6, 9, 12),
            )
        )
    return policies


def calibrate_policies(options: CalibrationOptions | None = None) -> dict[str, Any]:
    options = options or CalibrationOptions()
    policies = policies_for_options(options)
    return calibrate_policy_set(options, policies)


def calibrate_selected_policies(options: CalibrationOptions, policy_names: list[str]) -> dict[str, Any]:
    available = {policy.name: policy for policy in policies_for_options(options)}
    missing = [name for name in policy_names if name not in available]
    if missing:
        raise KeyError(f"unknown policies: {', '.join(missing)}")
    return calibrate_policy_set(options, [available[name] for name in policy_names])


def policies_for_options(options: CalibrationOptions) -> list[Policy]:
    return candidate_policies(
        include_dp_assist=options.enable_dp_assist,
        item_source=options.item_source,
        rank=options.rank,
        dp_utility_margin=options.dp_utility_margin,
    )


def calibrate_policy_set(options: CalibrationOptions, policies: list[Policy]) -> dict[str, Any]:
    accumulators = {policy.name: new_policy_accumulator(policy) for policy in policies}
    runs = max(1, int(options.runs))
    workers = worker_count(options.workers)
    if workers <= 1 or runs < 2000:
        chunk_accumulators = calibrate_policy_range(0, runs, options, policies)
        merge_all_policy_accumulators(accumulators, chunk_accumulators)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(calibrate_policy_range, start, end, options, policies)
                for start, end in calibration_chunks(runs, workers)
            ]
            for future in as_completed(futures):
                merge_all_policy_accumulators(accumulators, future.result())
    results = [finalize_policy_accumulator(accumulators[policy.name]) for policy in policies]
    results.sort(key=policy_sort_key)
    top_limit = max(1, int(options.top_limit or TOP_POLICY_LIMIT))
    top_results = results[:top_limit]
    return {
        "calibration_runs": runs,
        "seed": options.seed,
        "gear_source": options.gear_source,
        "item_source": options.item_source,
        "rank": options.rank,
        "workers": workers,
        "enable_dp_assist": options.enable_dp_assist,
        "dp_utility_margin": options.dp_utility_margin,
        "route_solver_sample_limit": options.route_solver_sample_limit,
        "candidate_policy_count": len(policies),
        "strategy_families": sorted({policy.family for policy in policies}),
        "best_policy": top_results[0]["policy_name"] if top_results else None,
        "ranking_metric": "cost_per_baili_score",
        "success_definition": {
            "source": "套装属性与装等计算表.md",
            "main_score_scope": "R2-R58 formal baili score; R61 future is auxiliary only",
            "conversion_gold_cost": DEFAULT_CONVERSION_GOLD_COST,
        },
        "policies": top_results,
    }


def calibrate_policy_range(start: int, end: int, options: CalibrationOptions, policies: list[Policy]) -> dict[str, dict[str, Any]]:
    accumulators = {policy.name: new_policy_accumulator(policy) for policy in policies}
    for index in range(start, end):
        seed = seed_for_index(options.seed, index)
        rng = random.Random(seed)
        base = generate_gear(rng, SimulationOptions(seed=seed, item_source=options.item_source, rank=options.rank))
        trace = build_full_trace(base, options, rng)
        for policy in policies:
            update_policy_accumulator(accumulators[policy.name], simulate_policy_from_trace(trace, policy, options, index))
    return accumulators


def calibration_chunks(runs: int, workers: int) -> list[tuple[int, int]]:
    chunk_size = max(1000, min(50000, runs // max(1, workers * 8) or 1000))
    return [(start, min(runs, start + chunk_size)) for start in range(0, runs, chunk_size)]


def seed_for_index(seed: int, index: int) -> int:
    return ((int(seed) + 1) * 1_000_003 + (index + 1) * 9_176_291) % (2**31 - 1) or 1


def worker_count(value: int) -> int:
    if value and value > 0:
        return int(value)
    return max(1, (os.cpu_count() or 1) - 1)


def summarize_policy(policy: Policy, options: CalibrationOptions, seeds: list[int]) -> dict[str, Any]:
    outcomes = []
    for seed in seeds:
        rng = random.Random(seed)
        base = generate_gear(rng, SimulationOptions(seed=seed, item_source=options.item_source, rank=options.rank))
        outcomes.append(simulate_policy_one(base, policy, options, rng))
    return summarize_policy_outcomes(policy, outcomes)


def build_full_trace(base: Gear, options: CalibrationOptions, rng: random.Random) -> dict[int, dict[str, Any]]:
    gear = clone_gear(base)
    trace = {0: checkpoint_state(gear, None, options)}
    for checkpoint in CHECKPOINTS:
        if checkpoint == 0:
            continue
        gear, hit_valid = enhance_to_checkpoint(gear, checkpoint, options.item_source, rng)
        trace[checkpoint] = checkpoint_state(gear, hit_valid, options)
    return trace


def checkpoint_state(gear: Gear, hit_valid: bool | None, options: CalibrationOptions) -> dict[str, Any]:
    score_info = expected_final_reforge_score(gear, options.item_source)
    evaluation = evaluate_gear(gear)
    final_gear = reforge_gear(gear)
    final_eval = evaluate_gear(final_gear)
    final_speed = speed_value(final_gear)
    conversion_plan = conversion_plan_for_gear(final_gear, options.item_source, final_eval)
    success_info = final_success_breakdown(final_eval, final_speed, options.item_source, conversion_plan)
    marginal = marginal_decision_for_gear(gear, options.item_source, options.gear_source, options.rank, evaluation, score_info)
    target_marginal = marginal_decision_for_gear(
        gear,
        options.item_source,
        options.gear_source,
        options.rank,
        evaluation,
        score_info,
        score_scope="target_with_future",
    )
    return {
        "gear": gear,
        "hit_valid": hit_valid,
        "expected_final_reforge_score": score_info["expected_final_reforge_score"],
        "expected_final_target_score": expected_final_target_score(gear, options.item_source, score_info, evaluation),
        "expected_final_reforge_speed": expected_final_reforge_speed(gear, options.item_source),
        "valid_profile_count": evaluation.valid_profile_count,
        "valid_count_after_conversion": valid_profile_count_after_conversion(evaluation, score_info["conversion"]),
        "reforge_score": final_eval.effective_score,
        "converted_effective_score": success_info["converted_effective_score"],
        "native_baili_score": success_info["native_baili_score"],
        "native_target_score": success_info["native_target_score"],
        "rescued_target_score": success_info["rescued_target_score"],
        "target_score": success_info["target_score"],
        "baili_score": success_info["baili_score"],
        "baili_tier": success_info["baili_tier"],
        "reforge_speed": final_speed,
        "speed_target": final_speed >= FINAL_SPEED_MIN and final_gear.slot != "boot",
        "conversion_needed": conversion_plan["conversion_needed"],
        "conversion_target_stat": conversion_plan["conversion_target_stat"],
        "success": success_info["final_success"],
        "native_success": success_info["native_success"],
        "rescued_success": success_info["rescued_success"],
        "target_category": success_info["target_category"],
        "marginal_decision": marginal,
        "target_marginal_decision": target_marginal,
    }


def simulate_policy_from_trace(
    trace: dict[int, dict[str, Any]],
    policy: Policy,
    options: CalibrationOptions,
    sample_index: int | None = None,
) -> dict[str, Any]:
    active_policy = policy_for_sample(policy, options, sample_index)
    valid_hits = 0
    invalid_hits = 0
    dp_stats = new_dp_stats()
    stopped = False
    stop_checkpoint = 0

    decision = continuation_decision_state(trace[0], active_policy, options)
    merge_dp_stats(dp_stats, decision)
    if not decision["continue"]:
        stopped = True

    if not stopped:
        for checkpoint in CHECKPOINTS:
            if checkpoint == 0:
                continue
            state = trace[checkpoint]
            if state["hit_valid"] is True:
                valid_hits += 1
            elif state["hit_valid"] is False:
                invalid_hits += 1
            stop_checkpoint = checkpoint
            if checkpoint >= 15:
                break
            decision = continuation_decision_state(state, active_policy, options)
            merge_dp_stats(dp_stats, decision)
            if not decision["continue"]:
                stopped = True
                break

    state = trace[stop_checkpoint]
    marginal = policy_marginal_decision(state, active_policy)
    success = (not stopped) and bool(state["success"])
    costs = cost_for_outcome(stop_checkpoint, success, True, options.gear_source, options.rank, state["gear"].slot)
    return {
        "set": state["gear"].set,
        "success": success,
        "stop_checkpoint": stop_checkpoint,
        "total_stamina": costs["total_stamina"],
        "gear_acquisition_stamina": costs["gear_acquisition_stamina"],
        "upgrade_stamina": costs["upgrade_stamina"],
        "sell_recovery_stamina": costs["sell_recovery_stamina"],
        "reforge_score": state["reforge_score"],
        "converted_effective_score": state["converted_effective_score"] if success else 0.0,
        "native_target_score": state["native_target_score"] if success and state["native_success"] else 0.0,
        "rescued_target_score": state["rescued_target_score"] if success and state["rescued_success"] else 0.0,
        "target_score": state["target_score"] if success else 0.0,
        "native_baili_score": state["native_baili_score"] if success else 0.0,
        "baili_score": state["baili_score"] if success else 0.0,
        "baili_tier": state["baili_tier"] if success else 0,
        "reforge_speed": state["reforge_speed"],
        "speed_target": bool(state["speed_target"]) and success,
        "conversion_needed": bool(state["conversion_needed"]) and success,
        "conversion_target_stat": state["conversion_target_stat"] if success and state["conversion_needed"] else None,
        "native_success": bool(state["native_success"]) and success,
        "rescued_success": bool(state["rescued_success"]) and success,
        "target_category": state["target_category"] if success else "未成功",
        "marginal_value_per_stamina": marginal["best_value_per_stamina"],
        "marginal_expected_gain": marginal["best_expected_gain"],
        "marginal_cross_tier_probability": marginal["best_cross_tier_probability"],
        "valid_hits": valid_hits,
        "invalid_hits": invalid_hits,
        "hit_count": valid_hits + invalid_hits,
        **dp_stats,
    }


def policy_for_sample(policy: Policy, options: CalibrationOptions, sample_index: int | None) -> Policy:
    if policy.decision_mode != "dp_assisted":
        return policy
    limit = options.route_solver_sample_limit
    if limit is None or sample_index is None or sample_index < limit:
        return policy
    return base_policy_for(policy)


def should_continue_state(state: dict[str, Any], policy: Policy, options: CalibrationOptions | None = None) -> bool:
    return bool(continuation_decision_state(state, policy, options)["continue"])


def continuation_decision_state(state: dict[str, Any], policy: Policy, options: CalibrationOptions | None = None) -> dict[str, Any]:
    gear = state["gear"]
    checkpoint = checkpoint_for(gear.enhance)
    if policy.decision_mode == "dp_assisted":
        options = options or CalibrationOptions(item_source="rift_85" if policy.name.startswith("rift_") else "normal_85", rank=gear.rank)
        return dp_assisted_decision_state(state, policy, options)
    if policy.decision_mode == "marginal":
        return decision_payload(should_continue_marginal(policy_marginal_decision(state, policy), policy, checkpoint))
    if gear.slot != "boot" and state["expected_final_reforge_speed"] >= policy.expected_speed_min.get(checkpoint, 99):
        return decision_payload(True)
    valid_count = state["valid_count_after_conversion"] if policy.conversion_friendly else state["valid_profile_count"]
    return decision_payload(
        state["expected_final_target_score"] >= policy.expected_score_min.get(checkpoint, 99)
        and valid_count >= policy.valid_count_min.get(checkpoint, 99)
    )


def dp_assisted_decision_state(state: dict[str, Any], policy: Policy, options: CalibrationOptions) -> dict[str, Any]:
    base_policy = base_policy_for(policy)
    base_decision = continuation_decision_state(state, base_policy, options)
    checkpoint = checkpoint_for(state["gear"].enhance)
    if checkpoint not in policy.dp_checkpoints or checkpoint >= 15:
        return base_decision
    from .route_solver import compute_optimal_route

    route = compute_optimal_route(
        state["gear"],
        lambda_value=policy.dp_lambda_value or 0.0,
        conversion_gold_cost=policy.dp_conversion_gold_cost,
        item_source=options.item_source,
        gear_source=options.gear_source,
        rank=options.rank,
    )
    dp_continue = route["action"] == "continue"
    continue_utility = float(route["continue_utility"] or 0.0)
    utility_gap = abs(continue_utility)
    changed = dp_continue != base_decision["continue"]
    return {
        "continue": dp_continue,
        "baseline_continue": base_decision["continue"],
        "dp_continue": dp_continue,
        "dp_action": route["action"],
        "dp_expected_utility": route.get("expected_utility"),
        "dp_continue_utility": route.get("continue_utility"),
        "dp_expected_formal_baili_score": route.get("expected_formal_baili_score"),
        "dp_expected_terminal_value": route.get("expected_terminal_value"),
        "dp_expected_final_speed": route.get("expected_terminal_speed"),
        "dp_expected_speed_rolls": route.get("expected_speed_rolls"),
        "dp_speed_potential_set_eligible": route.get("speed_potential_set_eligible"),
        "dp_speed_potential_threshold_blocked_probability": route.get("speed_potential_threshold_blocked_probability"),
        "dp_expected_speed_potential_value": route.get("expected_speed_potential_value"),
        "dp_expected_incremental_stamina": route.get("expected_incremental_stamina"),
        "dp_best_target_category": route.get("best_target_category"),
        "dp_best_source_row": route.get("best_source_row"),
        "dp_utility_gap": utility_gap,
        "dp_margin": policy.dp_utility_margin,
        "dp_overrode_baseline": changed,
        "dp_call_count": 1,
        "dp_changed_decision_count": 1 if changed else 0,
        "dp_changed_to_continue_count": 1 if changed and dp_continue else 0,
        "dp_changed_to_stop_count": 1 if changed and not dp_continue else 0,
        "dp_utility_gap_sum": utility_gap if changed else 0.0,
        "dp_continue_utility_sum": continue_utility,
        "dp_policy_continue_dp_stop_count": 1 if base_decision["continue"] and not dp_continue else 0,
        "dp_policy_stop_dp_continue_count": 1 if (not base_decision["continue"]) and dp_continue else 0,
        "dp_covered_checkpoints": {str(checkpoint): 1},
        "dp_changed_by_checkpoint": {str(checkpoint): 1} if changed else {},
    }


def base_policy_for(policy: Policy) -> Policy:
    policies = {item.name: item for item in candidate_policies()}
    if not policy.base_policy_name or policy.base_policy_name not in policies:
        raise KeyError(f"unknown base policy for {policy.name}: {policy.base_policy_name}")
    return policies[policy.base_policy_name]


def decision_payload(value: bool) -> dict[str, Any]:
    payload = new_dp_stats()
    payload["continue"] = bool(value)
    return payload


def new_dp_stats() -> dict[str, Any]:
    return {
        "dp_call_count": 0,
        "dp_changed_decision_count": 0,
        "dp_changed_to_continue_count": 0,
        "dp_changed_to_stop_count": 0,
        "dp_utility_gap_sum": 0.0,
        "dp_continue_utility_sum": 0.0,
        "dp_policy_continue_dp_stop_count": 0,
        "dp_policy_stop_dp_continue_count": 0,
        "dp_covered_checkpoints": {},
        "dp_changed_by_checkpoint": {},
    }


def merge_dp_stats(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in (
        "dp_call_count",
        "dp_changed_decision_count",
        "dp_changed_to_continue_count",
        "dp_changed_to_stop_count",
        "dp_policy_continue_dp_stop_count",
        "dp_policy_stop_dp_continue_count",
    ):
        target[key] += int(source.get(key, 0))
    for key in ("dp_utility_gap_sum", "dp_continue_utility_sum"):
        target[key] += float(source.get(key, 0.0))
    for checkpoint, count in (source.get("dp_covered_checkpoints") or {}).items():
        target["dp_covered_checkpoints"][checkpoint] = target["dp_covered_checkpoints"].get(checkpoint, 0) + int(count)
    for checkpoint, count in (source.get("dp_changed_by_checkpoint") or {}).items():
        target["dp_changed_by_checkpoint"][checkpoint] = target["dp_changed_by_checkpoint"].get(checkpoint, 0) + int(count)


def simulate_policy_one(base: Gear, policy: Policy, options: CalibrationOptions, rng: random.Random) -> dict[str, Any]:
    gear = clone_gear(base)
    valid_hits = 0
    invalid_hits = 0
    stopped = False
    stop_checkpoint = 0

    if not should_continue(gear, policy, options.item_source):
        stopped = True

    if not stopped:
        for checkpoint in CHECKPOINTS:
            if checkpoint == 0:
                continue
            gear, hit_valid = enhance_to_checkpoint(gear, checkpoint, options.item_source, rng)
            if hit_valid is True:
                valid_hits += 1
            elif hit_valid is False:
                invalid_hits += 1
            stop_checkpoint = checkpoint
            if checkpoint >= 15:
                break
            if not should_continue(gear, policy, options.item_source):
                stopped = True
                break

    final_gear = reforge_gear(gear)
    final_eval = evaluate_gear(final_gear)
    final_speed = speed_value(final_gear)
    conversion_plan = conversion_plan_for_gear(final_gear, options.item_source, final_eval)
    success_info = final_success_breakdown(final_eval, final_speed, options.item_source, conversion_plan)
    success = not stopped and success_info["final_success"]
    costs = cost_for_outcome(stop_checkpoint, success, True, options.gear_source, options.rank, gear.slot)
    marginal = marginal_decision_for_gear(gear, options.item_source, options.gear_source, options.rank, score_scope=policy.marginal_score_scope)
    return {
        "set": final_gear.set,
        "success": success,
        "stop_checkpoint": stop_checkpoint,
        "total_stamina": costs["total_stamina"],
        "gear_acquisition_stamina": costs["gear_acquisition_stamina"],
        "upgrade_stamina": costs["upgrade_stamina"],
        "sell_recovery_stamina": costs["sell_recovery_stamina"],
        "reforge_score": final_eval.effective_score,
        "converted_effective_score": success_info["converted_effective_score"] if success else 0.0,
        "native_target_score": success_info["native_target_score"] if success and success_info["native_success"] else 0.0,
        "rescued_target_score": success_info["rescued_target_score"] if success and success_info["rescued_success"] else 0.0,
        "target_score": success_info["target_score"] if success else 0.0,
        "native_baili_score": success_info["native_baili_score"] if success else 0.0,
        "baili_score": success_info["baili_score"] if success else 0.0,
        "baili_tier": success_info["baili_tier"] if success else 0,
        "reforge_speed": final_speed,
        "speed_target": final_speed >= FINAL_SPEED_MIN and final_gear.slot != "boot",
        "conversion_needed": conversion_plan["conversion_needed"] and success,
        "conversion_target_stat": conversion_plan["conversion_target_stat"] if conversion_plan["conversion_needed"] and success else None,
        "native_success": success_info["native_success"] and success,
        "rescued_success": success_info["rescued_success"] and success,
        "target_category": success_info["target_category"] if success else "未成功",
        "marginal_value_per_stamina": marginal["best_value_per_stamina"],
        "marginal_expected_gain": marginal["best_expected_gain"],
        "marginal_cross_tier_probability": marginal["best_cross_tier_probability"],
        "valid_hits": valid_hits,
        "invalid_hits": invalid_hits,
        "hit_count": valid_hits + invalid_hits,
        **new_dp_stats(),
    }


def should_continue(gear: Gear, policy: Policy, item_source: str) -> bool:
    checkpoint = checkpoint_for(gear.enhance)
    if policy.decision_mode == "dp_assisted":
        options = CalibrationOptions(item_source=item_source, rank=gear.rank)
        state = checkpoint_state(gear, None, options)
        return bool(dp_assisted_decision_state(state, policy, options)["continue"])
    score_info = expected_final_reforge_score(gear, item_source)
    projected_speed = expected_final_reforge_speed(gear, item_source)
    evaluation = evaluate_gear(gear)
    if policy.decision_mode == "marginal":
        decision = marginal_decision_for_gear(gear, item_source, None, None, evaluation, score_info, score_scope=policy.marginal_score_scope)
        return should_continue_marginal(decision, policy, checkpoint)
    valid_count = (
        valid_profile_count_after_conversion(evaluation, score_info["conversion"])
        if policy.conversion_friendly
        else evaluation.valid_profile_count
    )
    if gear.slot != "boot" and projected_speed >= policy.expected_speed_min.get(checkpoint, 99):
        return True
    return (
        expected_final_target_score(gear, item_source, score_info, evaluation) >= policy.expected_score_min.get(checkpoint, 99)
        and valid_count >= policy.valid_count_min.get(checkpoint, 99)
    )


def should_continue_marginal(decision: dict[str, Any], policy: Policy, checkpoint: int) -> bool:
    if checkpoint >= 15:
        return False
    threshold = effective_marginal_threshold(decision, policy, checkpoint)
    return decision["best_value_per_stamina"] >= threshold


def effective_marginal_threshold(decision: dict[str, Any], policy: Policy, checkpoint: int) -> float:
    minimums = policy.min_marginal_value_per_stamina or {}
    base = minimums.get(checkpoint, 0.0)
    return round_float(base * marginal_threshold_multiplier(decision, policy, checkpoint), 6)


def marginal_threshold_multiplier(decision: dict[str, Any], policy: Policy, checkpoint: int) -> float:
    variant = policy.marginal_variant
    if variant == "global":
        return 1.0
    set_group = decision.get("best_set_group") or "generic"
    category_group = decision.get("best_category_group") or category_group_for_category(decision.get("best_category"))
    matched = set_group_category_match(set_group, category_group)
    if variant == "set_group":
        return 0.92 if matched else 1.18
    if variant == "category":
        if category_group == "speed":
            return 0.9 if checkpoint <= 6 else 1.0
        if category_group in {"output", "tank", "dual", "bruiser"}:
            return 0.95
        return 1.2
    if variant == "category_set_group":
        if matched:
            return 0.85 if checkpoint <= 6 else 0.92
        return 1.25
    if variant == "speed_set_specialized":
        if set_group == "speed" and category_group == "speed":
            return {0: 0.72, 3: 0.78, 6: 0.88, 9: 0.95, 12: 1.05}.get(checkpoint, 1.0)
        return 1.3
    return 1.0


def policy_marginal_decision(state: dict[str, Any], policy: Policy) -> dict[str, Any]:
    if policy.marginal_score_scope == "target_with_future":
        return state.get("target_marginal_decision") or state["marginal_decision"]
    return state["marginal_decision"]


def set_group_for_set(set_code: str) -> str:
    if set_code == "set_speed":
        return "speed"
    if set_code in (SET_GROUPS.get("output", set()) | SET_GROUPS.get("critless", set())):
        return "output"
    if set_code in (
        SET_GROUPS.get("tankRes", set())
        | SET_GROUPS.get("pureTank", set())
        | SET_GROUPS.get("hitTank", set())
    ):
        return "tank"
    if set_code in SET_GROUPS.get("dual", set()):
        return "dual"
    if set_code in (
        SET_GROUPS.get("bruiserHpDef", set())
        | SET_GROUPS.get("bruiser", set())
        | SET_GROUPS.get("bruiserFlat", set())
    ):
        return "bruiser"
    return "generic"


def category_group_for_category(category: str | None) -> str:
    category = str(category or "")
    if category in {"一速", "速度套纯速度", "非速度套速度装"}:
        return "speed"
    if category.startswith("输出"):
        return "output"
    if category in {"抗坦", "纯肉", "命坦"}:
        return "tank"
    if category == "双效":
        return "dual"
    if category.startswith("半肉"):
        return "bruiser"
    return "generic"


def set_group_category_match(set_group: str, category_group: str) -> bool:
    if set_group == "speed" and category_group in {"speed", "output", "tank", "dual", "bruiser"}:
        return True
    return set_group == category_group and set_group != "generic"


def marginal_decision_for_gear(
    gear: Gear,
    item_source: str,
    gear_source: str | None = None,
    rank: str | None = None,
    evaluation: Evaluation | None = None,
    score_info: dict[str, Any] | None = None,
    score_scope: str = "formal_baili",
) -> dict[str, Any]:
    checkpoint = checkpoint_for(gear.enhance)
    next_checkpoint = next((point for point in CHECKPOINTS if point > checkpoint), None)
    if next_checkpoint is None:
        return empty_marginal_decision(checkpoint, None)
    evaluation = evaluation or evaluate_gear(gear)
    score_info = score_info or expected_final_reforge_score(gear, item_source, evaluation)
    marginal_cost = marginal_stamina_cost(checkpoint, next_checkpoint, gear_source, rank or gear.rank, gear.slot)
    candidates = marginal_candidates_for_gear(gear, item_source, evaluation, score_info, include_future=score_scope == "target_with_future")
    for candidate in candidates:
        candidate["value_per_stamina"] = round_float(candidate["expected_gain"] / marginal_cost, 6) if marginal_cost else 0.0
    candidates.sort(key=lambda item: (-item["value_per_stamina"], -item["expected_gain"], -item["cross_tier_probability"]))
    best = candidates[0] if candidates else marginal_no_candidate()
    return {
        "checkpoint": checkpoint,
        "next_checkpoint": next_checkpoint,
        "marginal_stamina_cost": round1(marginal_cost),
        "best_category": best["category"],
        "best_set_group": best["set_group"],
        "best_category_group": best["category_group"],
        "best_value_per_stamina": best["value_per_stamina"],
        "best_expected_gain": best["expected_gain"],
        "best_cross_tier_probability": best["cross_tier_probability"],
        "best_current_tier": best["current_tier"],
        "best_expected_final_tier": best["expected_final_tier"],
        "best_next_tier_distance": best["next_tier_distance"],
        "best_conversion_tier_delta": best["conversion_tier_delta"],
        "candidates": candidates,
    }


def marginal_candidates_for_gear(
    gear: Gear,
    item_source: str,
    evaluation: Evaluation,
    score_info: dict[str, Any],
    include_future: bool = False,
) -> list[dict[str, Any]]:
    candidates = []
    if gear.slot != "boot" and any(stat.key == "spd" for stat in gear.substats):
        candidates.append(speed_marginal_candidate(gear, item_source))
        speed_set_candidate = speed_set_marginal_candidate(gear, item_source, speed_set=True)
        if speed_set_candidate:
            candidates.append(speed_set_candidate)
        non_speed_set_candidate = speed_set_marginal_candidate(gear, item_source, speed_set=False)
        if non_speed_set_candidate:
            candidates.append(non_speed_set_candidate)
    for rule in CATEGORY_RULES:
        candidate = rule_marginal_candidate(gear, item_source, evaluation, score_info, rule)
        if candidate:
            candidates.append(candidate)
    if include_future:
        future_candidate = future_marginal_candidate(gear, item_source)
        if future_candidate:
            candidates.append(future_candidate)
    return candidates


def rule_marginal_candidate(
    gear: Gear,
    item_source: str,
    evaluation: Evaluation,
    score_info: dict[str, Any],
    rule: dict[str, Any],
) -> dict[str, Any] | None:
    group = SET_GROUPS.get(rule["setGroup"], set())
    valid_keys = set(VALID_STATS.get(rule["validGroup"], []))
    if gear.set not in group:
        return None
    all_keys = {stat.key for stat in gear.substats}
    all_keys.add(gear.main_stat.key)
    if not category_rule_compatible(gear, rule, all_keys, valid_keys):
        return None
    slot_formulas = formula_for_rule_slot(rule, gear.slot)
    if not slot_formulas:
        return None
    current_effective = official_score_for_candidate(gear, valid_keys)
    projected_effective = projected_reforge_score_for_keys(gear, item_source, valid_keys)
    conversion = conversion_plan_for_keys(
        gear,
        item_source,
        valid_keys,
        slot_formulas,
        current_effective,
        projected_effective,
    )
    converted_effective = round1(current_effective + conversion["conversion_expected_gain"])
    projected_converted_effective = round1(projected_effective + conversion["conversion_expected_gain"])
    current_tier = tier_for_effective(current_effective, slot_formulas)
    projected_tier = tier_for_effective(projected_effective, slot_formulas)
    converted_tier = tier_for_effective(converted_effective, slot_formulas)
    projected_converted_tier = tier_for_effective(projected_converted_effective, slot_formulas)
    current_score = formula_score_for_effective(current_effective, slot_formulas)
    projected_score = formula_score_for_effective(projected_effective, slot_formulas)
    projected_converted_score = formula_score_for_effective(projected_converted_effective, slot_formulas)
    next_threshold = next_tier_threshold(current_effective, slot_formulas)
    distance = max(0.0, round1((next_threshold or current_effective) - current_effective)) if next_threshold is not None else 0.0
    probability = cross_tier_probability(gear, item_source, valid_keys, next_threshold, max(projected_effective, projected_converted_effective))
    next_tier_score = formula_score_for_effective(next_threshold, slot_formulas) if next_threshold is not None else projected_score
    expected_target = max(projected_score, projected_converted_score, next_tier_score)
    expected_gain = round1(max(0.0, expected_target - current_score) * probability)
    return {
        "category": rule["category"],
        "set_group": set_group_for_set(gear.set),
        "category_group": category_group_for_category(rule["category"]),
        "source_row": rule.get("sourceRow", ""),
        "current_tier": current_tier,
        "expected_final_tier": max(projected_tier, projected_converted_tier),
        "current_target_score": round1(current_score),
        "expected_final_target_score": round1(expected_target),
        "next_tier_distance": distance,
        "cross_tier_probability": probability,
        "expected_gain": expected_gain,
        "conversion_needed": conversion["conversion_needed"],
        "conversion_target_stat": conversion["conversion_target_stat"],
        "conversion_tier_delta": conversion["conversion_tier_delta"],
        "projected_conversion_tier_delta": conversion["projected_conversion_tier_delta"],
        "conversion_cross_tier_gain": conversion["projected_conversion_tier_delta"],
        "conversion_score_gain": conversion["conversion_expected_gain"],
        "value_per_stamina": 0.0,
    }


def speed_marginal_candidate(gear: Gear, item_source: str) -> dict[str, Any]:
    speed = speed_value(gear)
    projected_speed = expected_final_reforge_speed(gear, item_source)
    current_tier = speed_tier(speed)
    projected_tier = speed_tier(projected_speed)
    current_score = score_one_speed(speed) if speed >= FINAL_SPEED_MIN else 0.0
    projected_score = score_one_speed(projected_speed) if projected_speed >= FINAL_SPEED_MIN else 0.0
    next_threshold = next_speed_threshold(speed)
    distance = max(0.0, round1((next_threshold or speed) - speed)) if next_threshold is not None else 0.0
    probability = speed_cross_probability(gear, item_source, next_threshold, projected_speed)
    next_tier_score = score_one_speed(next_threshold) if next_threshold is not None and next_threshold >= FINAL_SPEED_MIN else projected_score
    return {
        "category": "一速",
        "set_group": set_group_for_set(gear.set),
        "category_group": "speed",
        "source_row": "R2",
        "current_tier": current_tier,
        "expected_final_tier": projected_tier,
        "current_target_score": round1(current_score),
        "expected_final_target_score": round1(projected_score),
        "next_tier_distance": distance,
        "cross_tier_probability": probability,
        "expected_gain": round1(max(0.0, max(projected_score, next_tier_score) - current_score) * probability),
        "conversion_needed": False,
        "conversion_target_stat": None,
        "conversion_tier_delta": 0,
        "projected_conversion_tier_delta": 0,
        "value_per_stamina": 0.0,
    }


def speed_set_marginal_candidate(gear: Gear, item_source: str, speed_set: bool) -> dict[str, Any] | None:
    if gear.slot == "boot":
        return None
    if speed_set and gear.set != "set_speed":
        return None
    if not speed_set and gear.set not in SET_GROUPS["speedNonSpeed"]:
        return None
    support = category_support_for_speed(gear)
    if support["valid_count"] <= 0:
        return None
    speed = speed_value(gear)
    projected_speed = expected_final_reforge_speed(gear, item_source)
    current_score_input = official_score_for_candidate(gear, set(STAT_KEY_LABELS.keys()))
    projected_score_input = projected_reforge_score_for_keys(gear, item_source, set(STAT_KEY_LABELS.keys()))
    formulas = speed_set_formulas(speed_set)
    conversion = conversion_plan_for_keys(
        gear,
        item_source,
        set(support["valid_keys"]),
        formulas,
        current_score_input,
        projected_score_input,
    )
    converted_input = round1(current_score_input + conversion["conversion_expected_gain"])
    projected_converted_input = round1(projected_score_input + conversion["conversion_expected_gain"])
    current_tier = speed_set_tier(current_score_input, speed_set) if speed >= 18 else 0
    projected_tier = speed_set_tier(projected_score_input, speed_set) if projected_speed >= 18 else 0
    converted_tier = speed_set_tier(converted_input, speed_set) if speed >= 18 else 0
    projected_converted_tier = speed_set_tier(projected_converted_input, speed_set) if projected_speed >= 18 else 0
    current_score = speed_set_score(current_score_input, speed_set) if speed >= 18 else 0.0
    projected_score = speed_set_score(projected_score_input, speed_set) if projected_speed >= 18 else 0.0
    projected_converted_score = speed_set_score(projected_converted_input, speed_set) if projected_speed >= 18 else 0.0
    next_threshold = next_tier_threshold(current_score_input, formulas)
    score_distance = max(0.0, round1((next_threshold or current_score_input) - current_score_input)) if next_threshold is not None else 0.0
    speed_distance = max(0.0, round1(18 - speed))
    probability = min(
        speed_cross_probability(gear, item_source, 18, projected_speed),
        cross_tier_probability(gear, item_source, set(STAT_KEY_LABELS.keys()), next_threshold, max(projected_score_input, projected_converted_input)),
    )
    next_tier_score = speed_set_score(next_threshold, speed_set) if next_threshold is not None else projected_score
    expected_target = max(projected_score, projected_converted_score, next_tier_score)
    category = "速度套纯速度" if speed_set else "非速度套速度装"
    return {
        "category": category,
        "set_group": set_group_for_set(gear.set),
        "category_group": "speed",
        "source_row": "R3" if speed_set else "R4",
        "current_tier": current_tier,
        "expected_final_tier": max(projected_tier, projected_converted_tier),
        "current_target_score": round1(current_score),
        "expected_final_target_score": round1(expected_target),
        "next_tier_distance": max(score_distance, speed_distance),
        "cross_tier_probability": probability,
        "expected_gain": round1(max(0.0, expected_target - current_score) * probability),
        "conversion_needed": conversion["conversion_needed"],
        "conversion_target_stat": conversion["conversion_target_stat"],
        "conversion_tier_delta": conversion["conversion_tier_delta"],
        "projected_conversion_tier_delta": conversion["projected_conversion_tier_delta"],
        "conversion_cross_tier_gain": conversion["projected_conversion_tier_delta"],
        "conversion_score_gain": conversion["conversion_expected_gain"],
        "value_per_stamina": 0.0,
    }


def future_marginal_candidate(gear: Gear, item_source: str) -> dict[str, Any] | None:
    valid_keys = set(STAT_KEY_LABELS.keys())
    current_effective = official_score_for_candidate(gear, valid_keys)
    projected_effective = projected_reforge_score_for_keys(gear, item_source, valid_keys)
    formulas = future_formulas()
    current_tier = tier_for_effective(current_effective, formulas)
    projected_tier = tier_for_effective(projected_effective, formulas)
    current_score = formula_score_for_effective(current_effective, formulas)
    projected_score = formula_score_for_effective(projected_effective, formulas)
    next_threshold = next_tier_threshold(current_effective, formulas)
    if next_threshold is None and projected_score <= 0:
        return None
    distance = max(0.0, round1((next_threshold or current_effective) - current_effective)) if next_threshold is not None else 0.0
    probability = cross_tier_probability(gear, item_source, valid_keys, next_threshold, projected_effective)
    next_tier_score = formula_score_for_effective(next_threshold, formulas) if next_threshold is not None else projected_score
    expected_target = max(projected_score, next_tier_score)
    return {
        "category": "未来可期",
        "set_group": set_group_for_set(gear.set),
        "category_group": "generic",
        "source_row": "R61",
        "current_tier": current_tier,
        "expected_final_tier": projected_tier,
        "current_target_score": round1(current_score),
        "expected_final_target_score": round1(expected_target),
        "next_tier_distance": distance,
        "cross_tier_probability": probability,
        "expected_gain": round1(max(0.0, expected_target - current_score) * probability),
        "conversion_needed": False,
        "conversion_target_stat": None,
        "conversion_tier_delta": 0,
        "projected_conversion_tier_delta": 0,
        "conversion_cross_tier_gain": 0,
        "conversion_score_gain": 0.0,
        "value_per_stamina": 0.0,
    }


def speed_set_formulas(speed_set: bool) -> list[tuple[float, float, float]]:
    if speed_set:
        return [(78, 4, -285), (73, 3, -207), (68, 2, -134)]
    return [(75, 1, -69), (70, 0.8, -54)]


def speed_set_score(score_input: float | None, speed_set: bool) -> float:
    if score_input is None:
        return 0.0
    score = score_speed_set(score_input) if speed_set else score_non_speed_speed(score_input)
    return round1(score) if score is not None else 0.0


def speed_set_tier(score_input: float, speed_set: bool) -> int:
    return tier_speed_set(score_input) if speed_set else tier_non_speed_speed(score_input)


def future_formulas() -> list[tuple[float, float, float, str]]:
    return [(95, 2 / 3, -49, "2/3*(装等-73.5)"), (85, 2 / 3, -49, "2/3*(装等-73.5)"), (75, 2 / 3, -49, "2/3*(装等-73.5)")]


def category_rule_compatible(gear: Gear, rule: dict[str, Any], all_keys: set[str], valid_keys: set[str]) -> bool:
    return bool(rule_match_info(gear, rule)["matched"])


def formula_for_rule_slot(rule: dict[str, Any], slot: str) -> list[tuple] | None:
    formulas = FORMULAS.get(rule["formula"], {}) if FORMULAS.get(rule["formula"]) else {}
    return formulas.get(slot) if isinstance(formulas, dict) else None


def official_score_for_candidate(gear: Gear, valid_keys: set[str]) -> float:
    total = 0.0
    for stat in gear.substats:
        if stat.key in valid_keys:
            total += stat.normalized_value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0)
    return round1(total)


def projected_reforge_score_for_keys(gear: Gear, item_source: str, valid_keys: set[str]) -> float:
    if not gear.substats:
        return 0.0
    future_hits = future_hit_count(gear)
    share = future_hits / len(gear.substats)
    total = 0.0
    for stat in gear.substats:
        if stat.key not in valid_keys:
            continue
        expected_rolls = stat.rolls + share
        value = stat.normalized_value + expected_roll_value(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), stat.key) * share
        value += expected_reforge_bonus(stat.key, expected_rolls, gear)
        total += value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0)
    return round1(total)


def conversion_plan_for_keys(
    gear: Gear,
    item_source: str,
    valid_keys: set[str],
    formulas: list[tuple] | None = None,
    current_effective: float | None = None,
    projected_effective: float | None = None,
) -> dict[str, Any]:
    existing_keys = {stat.key for stat in gear.substats}
    existing_keys.add(gear.main_stat.key)
    target_keys = sorted(key for key in valid_keys if key not in existing_keys)
    candidates = [stat for stat in gear.substats if stat.key not in valid_keys and 0 < stat.rolls <= 2]
    best: dict[str, Any] | None = None
    base_current = official_score_for_candidate(gear, valid_keys) if current_effective is None else current_effective
    base_projected = projected_reforge_score_for_keys(gear, item_source, valid_keys) if projected_effective is None else projected_effective
    current_tier = tier_for_effective(base_current, formulas) if formulas else 0
    projected_tier = tier_for_effective(base_projected, formulas) if formulas else 0
    for candidate in candidates:
        for target_key in target_keys:
            gain = expected_converted_score_gain(target_key, candidate.rolls, item_source, gear)
            converted_tier = tier_for_effective(base_current + gain, formulas) if formulas else 0
            projected_converted_tier = tier_for_effective(base_projected + gain, formulas) if formulas else 0
            option = {
                "conversion_needed": True,
                "conversion_candidate": stat_debug(candidate),
                "conversion_target_stat": target_key,
                "conversion_expected_gain": round1(gain),
                "conversion_tier_delta": max(0, converted_tier - current_tier),
                "projected_conversion_tier_delta": max(0, projected_converted_tier - projected_tier),
            }
            option_rank = (
                option["projected_conversion_tier_delta"],
                option["conversion_tier_delta"],
                option["conversion_expected_gain"],
            )
            best_rank = (
                best["projected_conversion_tier_delta"],
                best["conversion_tier_delta"],
                best["conversion_expected_gain"],
            ) if best else None
            if best is None or option_rank > best_rank:
                best = {
                    **option,
                }
    if best:
        return best
    return {
        "conversion_needed": False,
        "conversion_candidate": None,
        "conversion_target_stat": None,
        "conversion_expected_gain": 0.0,
        "conversion_tier_delta": 0,
        "projected_conversion_tier_delta": 0,
    }


def tier_for_effective(effective_score: float, formulas: list[tuple]) -> int:
    for index, formula in enumerate(formulas):
        threshold = formula[0]
        if effective_score >= threshold:
            return max(1, len(formulas) - index)
    return 0


def formula_score_for_effective(effective_score: float, formulas: list[tuple]) -> float:
    match = score_by_formula(effective_score, formulas)
    return round1(match["score"]) if match else 0.0


def next_tier_threshold(effective_score: float, formulas: list[tuple]) -> float | None:
    thresholds = sorted({formula[0] for formula in formulas})
    for threshold in thresholds:
        if effective_score < threshold:
            return threshold
    return None


def cross_tier_probability(gear: Gear, item_source: str, valid_keys: set[str], threshold: float | None, projected_effective: float | None = None) -> float:
    current = official_score_for_candidate(gear, valid_keys)
    if threshold is None or current >= threshold:
        return 1.0
    increments = roll_increment_moments(gear, item_source, valid_keys)
    return probability_reaches_threshold(projected_effective if projected_effective is not None else current, threshold, future_hit_count(gear), increments)


def speed_cross_probability(gear: Gear, item_source: str, threshold: float | None, projected_speed: float | None = None) -> float:
    current = speed_value(gear)
    if threshold is None or current >= threshold:
        return 1.0
    increments = roll_increment_moments(gear, item_source, {"spd"}, raw_value=True)
    return probability_reaches_threshold(projected_speed if projected_speed is not None else current, threshold, future_hit_count(gear), increments)


def roll_increment_moments(gear: Gear, item_source: str, valid_keys: set[str], raw_value: bool = False) -> tuple[float, float]:
    if not gear.substats:
        return (0.0, 0.0)
    stat_means = []
    stat_second_moments = []
    for stat in gear.substats:
        if stat.key not in valid_keys:
            stat_means.append(0.0)
            stat_second_moments.append(0.0)
            continue
        low, high = roll_range_for_key(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), stat.key)
        weight = 1.0 if raw_value else OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0.0)
        rolls = [value * weight for value in range(low, high + 1)]
        stat_mean = sum(rolls) / len(rolls)
        stat_second = sum(value * value for value in rolls) / len(rolls)
        stat_means.append(stat_mean)
        stat_second_moments.append(stat_second)
    if not stat_means:
        return (0.0, 0.0)
    mean = sum(stat_means) / len(stat_means)
    second_moment = sum(stat_second_moments) / len(stat_second_moments)
    variance = max(0.0, second_moment - mean * mean)
    return (mean, variance)


def probability_reaches_threshold(projected_mean: float, threshold: float, future_hits: int, increments: tuple[float, float]) -> float:
    if future_hits <= 0:
        return 1.0 if projected_mean >= threshold else 0.0
    _, variance = increments
    if projected_mean >= threshold and variance == 0:
        return 1.0
    if variance == 0:
        return 0.0
    stddev = math.sqrt(variance * future_hits)
    z = (threshold - projected_mean) / stddev
    probability = 1 - normal_cdf(z)
    return round_rate(max(0.0, min(1.0, probability)))


def normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


def speed_tier(speed: float) -> int:
    if speed >= 27:
        return 3
    if speed >= 25:
        return 2
    if speed >= FINAL_SPEED_MIN:
        return 1
    return 0


def next_speed_threshold(speed: float) -> float | None:
    for threshold in (FINAL_SPEED_MIN, 25, 27):
        if speed < threshold:
            return threshold
    return None


def marginal_stamina_cost(
    current_checkpoint: int,
    next_checkpoint: int,
    gear_source: str | None,
    rank: str,
    slot: str | None = None,
) -> float:
    # Source credit is applied at acquisition only, so it cancels from a
    # next-node decision. This path only prices the material pool it consumes.
    calibration = calibration_for_rank(rank)
    _pool, scarcity = material_pool_for_slot(slot)
    interval = calibration.interval_costs[next_checkpoint]
    current_recovery = calibration.sell_recovery.get(current_checkpoint, ResourceAmount())
    next_recovery = calibration.sell_recovery.get(next_checkpoint, ResourceAmount())
    lost_recovery = current_recovery - next_recovery
    return max(0.1, calibration.rates.stamina_equivalent(interval + lost_recovery, scarcity))


def empty_marginal_decision(checkpoint: int, next_checkpoint: int | None) -> dict[str, Any]:
    return {
        "checkpoint": checkpoint,
        "next_checkpoint": next_checkpoint,
        "marginal_stamina_cost": 0.0,
        "best_category": "无",
        "best_value_per_stamina": 0.0,
        "best_expected_gain": 0.0,
        "best_cross_tier_probability": 0.0,
        "best_current_tier": 0,
        "best_expected_final_tier": 0,
        "best_next_tier_distance": 0.0,
        "best_conversion_tier_delta": 0,
        "candidates": [],
    }


def marginal_no_candidate() -> dict[str, Any]:
    return {
        "category": "无",
        "set_group": "generic",
        "category_group": "generic",
        "source_row": "",
        "current_tier": 0,
        "expected_final_tier": 0,
        "current_target_score": 0.0,
        "expected_final_target_score": 0.0,
        "next_tier_distance": 0.0,
        "cross_tier_probability": 0.0,
        "expected_gain": 0.0,
        "conversion_needed": False,
        "conversion_target_stat": None,
        "conversion_tier_delta": 0,
        "projected_conversion_tier_delta": 0,
        "value_per_stamina": 0.0,
    }


def dynamic_expected_score_min(gear: Gear, policy: Policy) -> float:
    checkpoint = checkpoint_for(gear.enhance)
    policy_min = policy.expected_score_min.get(checkpoint, 99)
    floor = profile_baili_score_floor(gear)
    return min(policy_min, floor) if floor is not None else policy_min


def profile_baili_score_floor(gear: Gear) -> float | None:
    for source_rows in baili_rule_order_for(gear):
        for source_row in source_rows:
            floor = baili_floor_for_rule(gear, source_row)
            if floor is not None:
                return floor
    return None


def baili_rule_order_for(gear: Gear) -> list[list[str]]:
    keys = {stat.key for stat in gear.substats}
    keys.add(gear.main_stat.key)
    output_rows = ["R5-R10"] if "crit" in keys else ["R11-R16", "R5-R10"]
    tank_rows = ["R17-R22"] if "res" in keys else ["R29-R34"] if "eff" in keys else ["R23-R28", "R17-R22"]
    return [
        output_rows,
        tank_rows,
        ["R35-R40"],
        ["R41-R46", "R47-R52", "R53-R58"],
    ]


def baili_floor_for_rule(gear: Gear, source_row: str) -> float | None:
    all_keys = {stat.key for stat in gear.substats}
    all_keys.add(gear.main_stat.key)
    for rule in CATEGORY_RULES:
        if rule.get("sourceRow") != source_row:
            continue
        group = SET_GROUPS.get(rule["setGroup"], set())
        valid_keys = set(VALID_STATS.get(rule["validGroup"], []))
        if gear.set not in group:
            continue
        if not any(stat.key in valid_keys for stat in gear.substats):
            continue
        if rule.get("requiredAny") and not any(key in all_keys for key in rule["requiredAny"]):
            continue
        if rule.get("noAtkPctWithEffRes") and "atkPct" in all_keys and any(key in all_keys for key in ("eff", "res")):
            continue
        if not main_allowed(gear.slot, gear.main_stat.key, rule.get("main", {})):
            continue
        formulas = FORMULAS.get(rule["formula"], {}) if FORMULAS.get(rule["formula"]) else {}
        slot_formulas = formulas.get(gear.slot) if isinstance(formulas, dict) else None
        if slot_formulas:
            return min(item[0] for item in slot_formulas)
    return None


def expected_final_reforge_score(gear: Gear, item_source: str, evaluation: Evaluation | None = None) -> dict[str, Any]:
    evaluation = evaluation or evaluate_gear(gear)
    raw_score = raw_expected_final_reforge_score(gear, item_source, evaluation)
    conversion = conversion_plan_for_gear(gear, item_source, evaluation)
    return {
        "expected_final_reforge_score": round1(raw_score + conversion["conversion_expected_gain"]),
        "raw_expected_final_reforge_score": raw_score,
        "conversion_expected_gain": conversion["conversion_expected_gain"],
        "conversion_candidate": conversion["conversion_candidate"],
        "conversion_target_stat": conversion["conversion_target_stat"],
        "conversion_needed": conversion["conversion_needed"],
        "conversion": conversion,
    }


def expected_final_target_score(
    gear: Gear,
    item_source: str,
    score_info: dict[str, Any] | None = None,
    evaluation: Evaluation | None = None,
) -> float:
    evaluation = evaluation or evaluate_gear(gear)
    score_info = score_info or expected_final_reforge_score(gear, item_source, evaluation)
    projected_effective = score_info["expected_final_reforge_score"]
    projected_speed = expected_final_reforge_speed(gear, item_source)
    return projected_target_score(evaluation, projected_effective, projected_speed)


def projected_target_score(evaluation: Evaluation, effective_score: float, speed: float) -> float:
    gear = evaluation.gear
    if gear.slot != "boot" and speed >= FINAL_SPEED_MIN:
        return round1(score_one_speed(speed))
    category = evaluation.retention.category if is_formal_baili_source_row(evaluation.target_score_source_row) else evaluation.valid_profile_category
    match = target_score_for_category(category, gear.slot, effective_score)
    return round1(match["score"]) if match else 0.0


def target_score_for_category(category: str, slot: str, effective_score: float) -> dict[str, Any] | None:
    for rule in CATEGORY_RULES:
        if rule["category"] != category:
            continue
        formulas = FORMULAS.get(rule["formula"], {}) if FORMULAS.get(rule["formula"]) else {}
        slot_formulas = formulas.get(slot) if isinstance(formulas, dict) else None
        return score_by_formula(effective_score, slot_formulas)
    return None


def raw_expected_final_reforge_score(gear: Gear, item_source: str, evaluation: Evaluation) -> float:
    valid_keys = set(evaluation.valid_profile_keys)
    if not valid_keys:
        return 0.0
    future_hits = future_hit_count(gear)
    if not gear.substats:
        return 0.0
    share = future_hits / len(gear.substats)
    total = 0.0
    for stat in gear.substats:
        if stat.key not in valid_keys:
            continue
        expected_rolls = stat.rolls + share
        value = stat.normalized_value + expected_roll_value(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), stat.key) * share
        value += expected_reforge_bonus(stat.key, expected_rolls, gear)
        total += value * OFFICIAL_SCORE_WEIGHTS.get(stat.key, 0)
    return round1(total)


def expected_final_reforge_speed(gear: Gear, item_source: str) -> float:
    speed_stats = [stat for stat in gear.substats if stat.key == "spd"]
    if gear.slot == "boot" or not speed_stats:
        return 0.0
    stat = speed_stats[0]
    share = future_hit_count(gear) / max(1, len(gear.substats))
    expected_rolls = stat.rolls + share
    value = stat.normalized_value + expected_roll_value(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), "spd") * share
    value += expected_reforge_bonus("spd", expected_rolls, gear)
    return round1(value)


def conversion_plan_for_gear(gear: Gear, item_source: str, evaluation: Evaluation | None = None) -> dict[str, Any]:
    evaluation = evaluation or evaluate_gear(gear)
    valid_keys = set(evaluation.valid_profile_keys)
    existing_keys = {stat.key for stat in gear.substats}
    existing_keys.add(gear.main_stat.key)
    target_keys = sorted(key for key in valid_keys if key not in existing_keys)
    candidates = [stat for stat in gear.substats if stat.key not in valid_keys and 0 < stat.rolls <= 2]
    best: dict[str, Any] | None = None
    for candidate in candidates:
        for target_key in target_keys:
            gain = expected_converted_score_gain(target_key, candidate.rolls, item_source, gear)
            if best is None or gain > best["conversion_expected_gain"]:
                best = {
                    "conversion_needed": True,
                    "conversion_candidate": stat_debug(candidate),
                    "conversion_target_stat": target_key,
                    "conversion_expected_gain": round1(gain),
                }
    if best:
        return best
    return {
        "conversion_needed": False,
        "conversion_candidate": None,
        "conversion_target_stat": None,
        "conversion_expected_gain": 0.0,
    }


def expected_converted_score_gain(target_key: str, rolls: int, item_source: str, gear: Gear) -> float:
    value = expected_roll_value(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), target_key) * rolls
    value += reforge_bonus_value(target_key, rolls)
    return value * OFFICIAL_SCORE_WEIGHTS.get(target_key, 0)


def is_successful_final_with_conversion(
    evaluation: Evaluation,
    speed: float,
    item_source: str,
    conversion: dict[str, Any] | None = None,
) -> bool:
    gear = evaluation.gear
    conversion = conversion or conversion_plan_for_gear(gear, item_source, evaluation)
    if is_successful_final_native(evaluation, speed):
        return True
    if not conversion.get("conversion_needed"):
        return False
    converted = evaluate_gear(gear_after_conversion(gear, conversion))
    return is_successful_final_native(converted, speed_value(converted.gear))


def is_successful_final_native(evaluation: Evaluation, speed: float) -> bool:
    if evaluation.gear.slot != "boot" and speed >= FINAL_SPEED_MIN:
        return True
    return is_formal_baili_source_row(evaluation.target_score_source_row) and evaluation.target_score > 0


def final_success_breakdown(
    evaluation: Evaluation,
    speed: float,
    item_source: str,
    conversion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conversion = conversion or conversion_plan_for_gear(evaluation.gear, item_source, evaluation)
    native_success = is_successful_final_native(evaluation, speed)
    converted_evaluation = evaluate_gear(gear_after_conversion(evaluation.gear, conversion)) if (not native_success and conversion.get("conversion_needed")) else evaluation
    converted_speed = speed_value(converted_evaluation.gear)
    final_success = native_success or is_successful_final_native(converted_evaluation, converted_speed)
    rescued_success = final_success and not native_success
    converted_effective_score = converted_evaluation.effective_score if rescued_success else round1(evaluation.effective_score + conversion["conversion_expected_gain"])
    native_baili_score = evaluation.baili_score if native_success and evaluation.retention.rule_matched else 0.0
    native_target_score = evaluation.target_score if native_success else 0.0
    rescued_target_score = converted_evaluation.target_score if rescued_success else 0.0
    target_score = native_target_score if native_success else rescued_target_score
    baili_score = target_score if final_success else 0.0
    target_category = final_target_category(evaluation if native_success else converted_evaluation, speed if native_success else converted_speed) if final_success else "未成功"
    return {
        "native_success": native_success,
        "rescued_success": rescued_success,
        "final_success": final_success,
        "converted_effective_score": converted_effective_score if final_success else 0.0,
        "native_baili_score": native_baili_score,
        "native_target_score": native_target_score,
        "rescued_target_score": rescued_target_score,
        "target_score": target_score,
        "baili_score": baili_score,
        "target_category": target_category,
        "baili_tier": evaluation.retention.baili_tier if native_baili_score > 0 else 0,
    }


def converted_target_score(evaluation: Evaluation, speed: float, conversion: dict[str, Any]) -> float:
    if is_successful_final_native(evaluation, speed):
        return evaluation.target_score
    if not conversion.get("conversion_needed"):
        return 0.0
    converted = evaluate_gear(gear_after_conversion(evaluation.gear, conversion))
    converted_speed = speed_value(converted.gear)
    return converted.target_score if is_successful_final_native(converted, converted_speed) else 0.0


def gear_after_conversion(gear: Gear, conversion: dict[str, Any]) -> Gear:
    if not conversion.get("conversion_needed"):
        return gear
    candidate = conversion.get("conversion_candidate") or {}
    target_key = conversion.get("conversion_target_stat")
    if not target_key:
        return gear
    weight = OFFICIAL_SCORE_WEIGHTS.get(target_key, 0)
    if not weight:
        return gear
    converted_value = round1(conversion.get("conversion_expected_gain", 0.0) / weight)
    converted_type = STAT_TYPE_BY_KEY.get(target_key, target_key)
    replaced = False
    substats: list[Stat] = []
    for stat in gear.substats:
        if not replaced and stat.key == candidate.get("key") and stat.rolls == candidate.get("rolls"):
            substats.append(Stat(converted_type, converted_value, rolls=stat.rolls, modified=True))
            replaced = True
        else:
            substats.append(stat)
    return replace(gear, substats=substats) if replaced else gear


def valid_profile_count_after_conversion(evaluation: Evaluation, conversion: dict[str, Any]) -> int:
    return evaluation.valid_profile_count + (1 if conversion.get("conversion_needed") else 0)


def final_target_category(evaluation: Evaluation, speed: float) -> str:
    if evaluation.gear.slot != "boot" and speed >= FINAL_SPEED_MIN:
        return "一速"
    if is_formal_baili_source_row(evaluation.target_score_source_row):
        return evaluation.retention.category
    return evaluation.valid_profile_category


def is_formal_baili_source_row(source_row: str) -> bool:
    numbers = []
    for part in str(source_row or "").replace("R", "").split("-"):
        try:
            numbers.append(int(part))
        except ValueError:
            continue
    return bool(numbers) and min(numbers) >= 2 and max(numbers) <= 58


def expected_reforge_bonus(key: str, rolls: float, gear: Gear | None = None) -> float:
    if gear is not None and gear.level >= 90:
        return 0.0
    lower = int(rolls)
    upper = lower + 1
    fraction = rolls - lower
    lower_bonus = reforge_bonus_value(key, lower)
    upper_bonus = reforge_bonus_value(key, upper)
    return lower_bonus + (upper_bonus - lower_bonus) * fraction


def summarize_policy_outcomes(policy: Policy, outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    accumulator = new_policy_accumulator(policy)
    for outcome in outcomes:
        update_policy_accumulator(accumulator, outcome)
    return finalize_policy_accumulator(accumulator)


def new_policy_accumulator(policy: Policy) -> dict[str, Any]:
    return {
        "policy": policy,
        "runs": 0,
        "successes": 0,
        "native_successes": 0,
        "rescued_successes": 0,
        "total_stamina": 0.0,
        "total_baili_score": 0.0,
        "total_native_baili_score": 0.0,
        "total_native_target_score": 0.0,
        "total_rescued_target_score": 0.0,
        "total_target_score": 0.0,
        "total_rescued_converted_effective_score": 0.0,
        "total_final_converted_effective_score": 0.0,
        "total_gear_acquisition_stamina": 0.0,
        "total_upgrade_stamina": 0.0,
        "total_sell_recovery_stamina": 0.0,
        "total_reforge_score": 0.0,
        "total_reforge_speed": 0.0,
        "speed_targets": 0,
        "conversion_needed": 0,
        "total_marginal_value_per_stamina": 0.0,
        "total_marginal_expected_gain": 0.0,
        "total_marginal_cross_tier_probability": 0.0,
        "valid_hits": 0,
        "hit_count": 0,
        "stop_counts": {str(point): 0 for point in CHECKPOINTS},
        "baili_tier_counts": {str(point): 0 for point in (0, 1, 2, 3)},
        "target_score_by_category": {},
        "success_counts_by_category": {},
        "baili_score_by_set": {},
        "stamina_by_set": {},
        "run_counts_by_set": {},
        "success_counts_by_set": {},
        "stop_counts_by_set": {},
        "category_by_set_matrix": {},
        "conversion_target_stat_counts": {},
        "dp_call_count": 0,
        "dp_changed_decision_count": 0,
        "dp_changed_to_continue_count": 0,
        "dp_changed_to_stop_count": 0,
        "dp_utility_gap_sum": 0.0,
        "dp_continue_utility_sum": 0.0,
        "dp_policy_continue_dp_stop_count": 0,
        "dp_policy_stop_dp_continue_count": 0,
        "dp_covered_checkpoints": {},
        "dp_changed_by_checkpoint": {},
    }


def update_policy_accumulator(accumulator: dict[str, Any], outcome: dict[str, Any]) -> None:
    accumulator["runs"] += 1
    accumulator["successes"] += 1 if outcome["success"] else 0
    accumulator["native_successes"] += 1 if outcome["native_success"] else 0
    accumulator["rescued_successes"] += 1 if outcome["rescued_success"] else 0
    accumulator["total_stamina"] += outcome["total_stamina"]
    accumulator["total_baili_score"] += outcome["baili_score"]
    accumulator["total_native_baili_score"] += outcome["native_baili_score"]
    accumulator["total_native_target_score"] += outcome["native_target_score"]
    accumulator["total_rescued_target_score"] += outcome["rescued_target_score"]
    accumulator["total_target_score"] += outcome["target_score"]
    accumulator["total_rescued_converted_effective_score"] += outcome["converted_effective_score"] if outcome["rescued_success"] else 0.0
    accumulator["total_final_converted_effective_score"] += outcome["converted_effective_score"] if outcome["success"] else 0.0
    accumulator["total_gear_acquisition_stamina"] += outcome["gear_acquisition_stamina"]
    accumulator["total_upgrade_stamina"] += outcome["upgrade_stamina"]
    accumulator["total_sell_recovery_stamina"] += outcome["sell_recovery_stamina"]
    accumulator["total_reforge_score"] += outcome["reforge_score"]
    accumulator["total_reforge_speed"] += outcome["reforge_speed"]
    accumulator["speed_targets"] += 1 if outcome["speed_target"] else 0
    accumulator["conversion_needed"] += 1 if outcome["conversion_needed"] else 0
    accumulator["total_marginal_value_per_stamina"] += outcome["marginal_value_per_stamina"]
    accumulator["total_marginal_expected_gain"] += outcome["marginal_expected_gain"]
    accumulator["total_marginal_cross_tier_probability"] += outcome["marginal_cross_tier_probability"]
    accumulator["valid_hits"] += outcome["valid_hits"]
    accumulator["hit_count"] += outcome["hit_count"]
    accumulator["stop_counts"][str(outcome["stop_checkpoint"])] += 1
    accumulator["baili_tier_counts"][str(outcome["baili_tier"])] += 1
    set_code = outcome.get("set") or "unknown"
    accumulator["stamina_by_set"][set_code] = accumulator["stamina_by_set"].get(set_code, 0.0) + outcome["total_stamina"]
    accumulator["run_counts_by_set"][set_code] = accumulator["run_counts_by_set"].get(set_code, 0) + 1
    set_stops = accumulator["stop_counts_by_set"].setdefault(set_code, {str(point): 0 for point in CHECKPOINTS})
    set_stops[str(outcome["stop_checkpoint"])] += 1
    if outcome["conversion_needed"] and outcome.get("conversion_target_stat"):
        target_stat = outcome["conversion_target_stat"]
        accumulator["conversion_target_stat_counts"][target_stat] = accumulator["conversion_target_stat_counts"].get(target_stat, 0) + 1
    for key in (
        "dp_call_count",
        "dp_changed_decision_count",
        "dp_changed_to_continue_count",
        "dp_changed_to_stop_count",
        "dp_policy_continue_dp_stop_count",
        "dp_policy_stop_dp_continue_count",
    ):
        accumulator[key] += int(outcome.get(key, 0))
    for key in ("dp_utility_gap_sum", "dp_continue_utility_sum"):
        accumulator[key] += float(outcome.get(key, 0.0))
    for checkpoint, count in (outcome.get("dp_covered_checkpoints") or {}).items():
        accumulator["dp_covered_checkpoints"][checkpoint] = accumulator["dp_covered_checkpoints"].get(checkpoint, 0) + int(count)
    for checkpoint, count in (outcome.get("dp_changed_by_checkpoint") or {}).items():
        accumulator["dp_changed_by_checkpoint"][checkpoint] = accumulator["dp_changed_by_checkpoint"].get(checkpoint, 0) + int(count)
    if outcome["success"]:
        category = outcome["target_category"]
        accumulator["target_score_by_category"][category] = accumulator["target_score_by_category"].get(category, 0.0) + outcome["target_score"]
        accumulator["success_counts_by_category"][category] = accumulator["success_counts_by_category"].get(category, 0) + 1
        accumulator["baili_score_by_set"][set_code] = accumulator["baili_score_by_set"].get(set_code, 0.0) + outcome["baili_score"]
        accumulator["success_counts_by_set"][set_code] = accumulator["success_counts_by_set"].get(set_code, 0) + 1
        set_matrix = accumulator["category_by_set_matrix"].setdefault(set_code, {})
        set_matrix[category] = set_matrix.get(category, 0.0) + outcome["target_score"]


def merge_all_policy_accumulators(target: dict[str, dict[str, Any]], source: dict[str, dict[str, Any]]) -> None:
    for policy_name, source_accumulator in source.items():
        merge_policy_accumulator(target[policy_name], source_accumulator)


def merge_policy_accumulator(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in (
        "runs",
        "successes",
        "native_successes",
        "rescued_successes",
        "total_stamina",
        "total_baili_score",
        "total_native_baili_score",
        "total_native_target_score",
        "total_rescued_target_score",
        "total_target_score",
        "total_rescued_converted_effective_score",
        "total_final_converted_effective_score",
        "total_gear_acquisition_stamina",
        "total_upgrade_stamina",
        "total_sell_recovery_stamina",
        "total_reforge_score",
        "total_reforge_speed",
        "speed_targets",
        "conversion_needed",
        "total_marginal_value_per_stamina",
        "total_marginal_expected_gain",
        "total_marginal_cross_tier_probability",
        "valid_hits",
        "hit_count",
        "dp_call_count",
        "dp_changed_decision_count",
        "dp_changed_to_continue_count",
        "dp_changed_to_stop_count",
        "dp_utility_gap_sum",
        "dp_continue_utility_sum",
        "dp_policy_continue_dp_stop_count",
        "dp_policy_stop_dp_continue_count",
    ):
        target[key] += source[key]
    for key, value in source["stop_counts"].items():
        target["stop_counts"][key] += value
    for key, value in source["baili_tier_counts"].items():
        target["baili_tier_counts"][key] += value
    merge_numeric_dict(target["target_score_by_category"], source["target_score_by_category"])
    merge_numeric_dict(target["success_counts_by_category"], source["success_counts_by_category"])
    merge_numeric_dict(target["baili_score_by_set"], source["baili_score_by_set"])
    merge_numeric_dict(target["stamina_by_set"], source["stamina_by_set"])
    merge_numeric_dict(target["run_counts_by_set"], source["run_counts_by_set"])
    merge_numeric_dict(target["success_counts_by_set"], source["success_counts_by_set"])
    merge_nested_numeric_dict(target["stop_counts_by_set"], source["stop_counts_by_set"])
    merge_nested_numeric_dict(target["category_by_set_matrix"], source["category_by_set_matrix"])
    merge_numeric_dict(target["conversion_target_stat_counts"], source["conversion_target_stat_counts"])
    merge_numeric_dict(target["dp_covered_checkpoints"], source["dp_covered_checkpoints"])
    merge_numeric_dict(target["dp_changed_by_checkpoint"], source["dp_changed_by_checkpoint"])


def finalize_policy_accumulator(accumulator: dict[str, Any]) -> dict[str, Any]:
    policy = accumulator["policy"]
    runs = accumulator["runs"]
    successes = accumulator["successes"]
    native_successes = accumulator["native_successes"]
    rescued_successes = accumulator["rescued_successes"]
    total_stamina = accumulator["total_stamina"]
    total_baili_score = accumulator["total_baili_score"]
    total_native_baili_score = accumulator["total_native_baili_score"]
    total_native_target_score = accumulator["total_native_target_score"]
    total_rescued_target_score = accumulator["total_rescued_target_score"]
    total_target_score = accumulator["total_target_score"]
    total_rescued_converted_effective_score = accumulator["total_rescued_converted_effective_score"]
    total_final_converted_effective_score = accumulator["total_final_converted_effective_score"]
    final_value = total_native_baili_score + total_rescued_converted_effective_score
    conversion_needed = accumulator["conversion_needed"]
    stop_counts = accumulator["stop_counts"]
    baili_tier_counts = accumulator["baili_tier_counts"]
    hit_count = accumulator["hit_count"]
    valid_hits = accumulator["valid_hits"]
    dp_calls = accumulator["dp_call_count"]
    dp_changes = accumulator["dp_changed_decision_count"]
    return {
        "policy_name": policy.name,
        "policy_family": policy.family,
        "thresholds": policy.thresholds(),
        "success_rate": round_rate(successes / runs),
        "final_success_rate": round_rate(successes / runs),
        "native_success_rate": round_rate(native_successes / runs),
        "rescued_success_rate": round_rate(rescued_successes / runs),
        "cost_per_success": round1(total_stamina / successes) if successes else None,
        "cost_per_final_success": round1(total_stamina / successes) if successes else None,
        "cost_per_native_success": round1(total_stamina / native_successes) if native_successes else None,
        "cost_per_rescued_success": round1(total_stamina / rescued_successes) if rescued_successes else None,
        "total_baili_score": round1(total_baili_score),
        "total_stamina": total_stamina,
        "nonzero_terminal_count": successes,
        "total_native_baili_score": round1(total_native_baili_score),
        "native_target_score": round1(total_native_target_score),
        "rescued_target_score": round1(total_rescued_target_score),
        "target_score": round1(total_target_score),
        "target_score_per_1000_stamina": round1(total_target_score * 1000 / total_stamina) if total_stamina else 0.0,
        "cost_per_target_score": round1(total_stamina / total_target_score) if total_target_score else None,
        "baili_score_per_1000_stamina": round1(total_baili_score * 1000 / total_stamina) if total_stamina else 0.0,
        "cost_per_baili_score": round1(total_stamina / total_baili_score) if total_baili_score else None,
        "cost_per_native_baili_score": round1(total_stamina / total_native_baili_score) if total_native_baili_score else None,
        "avg_success_baili_score": round1(total_baili_score / successes) if successes else 0.0,
        "rescued_converted_effective_score": round1(total_rescued_converted_effective_score),
        "final_converted_effective_score": round1(total_final_converted_effective_score),
        "converted_effective_score_per_1000_stamina": round1(total_final_converted_effective_score * 1000 / total_stamina) if total_stamina else 0.0,
        "cost_per_converted_effective_score": round1(total_stamina / total_final_converted_effective_score) if total_final_converted_effective_score else None,
        "final_value": round1(final_value),
        "final_value_per_1000_stamina": round1(final_value * 1000 / total_stamina) if total_stamina else 0.0,
        "cost_per_final_value": round1(total_stamina / final_value) if final_value else None,
        "final_score": round1(total_final_converted_effective_score),
        "final_score_per_1000_stamina": round1(total_final_converted_effective_score * 1000 / total_stamina) if total_stamina else 0.0,
        "cost_per_final_score": round1(total_stamina / total_final_converted_effective_score) if total_final_converted_effective_score else None,
        "baili_tier_rate": {key: round_rate(value / runs) for key, value in baili_tier_counts.items()},
        "target_score_by_category": round_numeric_dict(accumulator["target_score_by_category"]),
        "target_score_share_by_category": share_dict(accumulator["target_score_by_category"], total_target_score),
        "success_count_by_category": dict(sorted(accumulator["success_counts_by_category"].items())),
        "baili_score_by_set": round_numeric_dict(accumulator["baili_score_by_set"]),
        "cost_per_baili_score_by_set": cost_per_score_by_set(accumulator["stamina_by_set"], accumulator["baili_score_by_set"]),
        "success_count_by_set": dict(sorted(accumulator["success_counts_by_set"].items())),
        "stop_rate_by_set": stop_rate_by_set(accumulator["stop_counts_by_set"], accumulator["run_counts_by_set"]),
        "category_by_set_matrix": round_nested_numeric_dict(accumulator["category_by_set_matrix"]),
        "conversion_needed_count": conversion_needed,
        "conversion_target_stat_distribution": dict(sorted(accumulator["conversion_target_stat_counts"].items())),
        "conversion_gold_cost": CONVERSION_GOLD_COST_SCENARIOS,
        "native_baili_efficiency": efficiency_summary(total_native_baili_score, total_stamina),
        "rescued_baili_efficiency_without_conversion_cost": efficiency_summary(total_baili_score, total_stamina),
        "rescued_baili_efficiency_with_conversion_gold_cost": {
            str(cost): efficiency_summary(total_baili_score, total_stamina + conversion_needed * conversion_stamina_cost(cost))
            for cost in CONVERSION_GOLD_COST_SCENARIOS
        },
        "total_stamina_avg": round1(total_stamina / runs) if runs else 0.0,
        "gear_acquisition_stamina_avg": round1(accumulator["total_gear_acquisition_stamina"] / runs) if runs else 0.0,
        "upgrade_stamina_avg": round1(accumulator["total_upgrade_stamina"] / runs) if runs else 0.0,
        "sell_recovery_avg": round1(accumulator["total_sell_recovery_stamina"] / runs) if runs else 0.0,
        "stop_rate_by_checkpoint": {key: round_rate(value / runs) for key, value in stop_counts.items()},
        "expected_reforge_score_avg": round1(accumulator["total_reforge_score"] / runs) if runs else 0.0,
        "expected_reforge_speed_avg": round1(accumulator["total_reforge_speed"] / runs) if runs else 0.0,
        "speed_target_rate": round_rate(accumulator["speed_targets"] / runs) if runs else 0.0,
        "conversion_needed_rate": round_rate(accumulator["conversion_needed"] / runs) if runs else 0.0,
        "marginal_value_per_stamina_avg": round_float(accumulator["total_marginal_value_per_stamina"] / runs, 6) if runs else 0.0,
        "marginal_expected_gain_avg": round_float(accumulator["total_marginal_expected_gain"] / runs, 6) if runs else 0.0,
        "marginal_cross_tier_probability_avg": round_rate(accumulator["total_marginal_cross_tier_probability"] / runs) if runs else 0.0,
        "valid_hit_rate": round_rate(valid_hits / hit_count) if hit_count else 0.0,
        "invalid_hit_rate": round_rate(1 - valid_hits / hit_count) if hit_count else 0.0,
        "dp_call_count": dp_calls,
        "dp_covered_checkpoints": dict(sorted(accumulator["dp_covered_checkpoints"].items())),
        "dp_changed_by_checkpoint": dict(sorted(accumulator["dp_changed_by_checkpoint"].items())),
        "dp_changed_decision_count": dp_changes,
        "dp_changed_decision_rate": round_rate(dp_changes / dp_calls) if dp_calls else 0.0,
        "dp_changed_to_continue_count": accumulator["dp_changed_to_continue_count"],
        "dp_changed_to_stop_count": accumulator["dp_changed_to_stop_count"],
        "dp_policy_continue_dp_stop_count": accumulator["dp_policy_continue_dp_stop_count"],
        "dp_policy_stop_dp_continue_count": accumulator["dp_policy_stop_dp_continue_count"],
        "dp_utility_gap_avg_when_changed": round_float(accumulator["dp_utility_gap_sum"] / dp_changes, 6) if dp_changes else 0.0,
        "dp_continue_utility_avg": round_float(accumulator["dp_continue_utility_sum"] / dp_calls, 6) if dp_calls else 0.0,
    }


def render_calibration_summary(result: dict[str, Any]) -> str:
    lines = [
        "强化门槛校准",
        f"样本数：{result['calibration_runs']}",
        f"装备来源：{result['item_source']} / {result['gear_source']} / {result['rank']}",
        f"候选策略数：{result['candidate_policy_count']}",
        f"推荐策略：{result['best_policy']}",
        f"成品线：重铸后命中 {result['success_definition']['source']} 且目标评分 > 0",
        "",
        "策略对比（前 5）：",
    ]
    for policy in result["policies"]:
        cost = policy["cost_per_success"] if policy["cost_per_success"] is not None else "无成功样本"
        lines.append(
            f"- {policy['policy_name']}: 成功率 {round1(policy['success_rate'] * 100)}%, "
            f"每件成功成本 {cost} 体力, 平均消耗 {policy['total_stamina_avg']} 体力, "
            f"转换需求 {round1(policy['conversion_needed_rate'] * 100)}%, "
            f"每目标分成本 {policy['cost_per_target_score']}"
        )
    best = result["policies"][0] if result["policies"] else None
    if best:
        lines.append("")
        lines.append("推荐门槛：")
        for checkpoint, threshold in best["thresholds"]["expected_final_reforge_score_min"].items():
            speed = best["thresholds"]["expected_final_reforge_speed_min"][checkpoint]
            valid = best["thresholds"]["valid_count_min"][checkpoint]
            lines.append(f"- +{checkpoint}: 预计 +15 后重铸目标分 >= {threshold} 且有效副属性 >= {valid}，或预计 +15 后重铸速度 >= {speed}")
    return "\n".join(lines)


def policy_sort_key(item: dict[str, Any]) -> tuple[float, float]:
    cost = item["cost_per_baili_score"]
    if cost is None:
        return (float("inf"), -item["success_rate"])
    return (float(cost), -item["baili_score_per_1000_stamina"])


def merge_numeric_dict(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def merge_nested_numeric_dict(target: dict[str, dict[str, Any]], source: dict[str, dict[str, Any]]) -> None:
    for key, values in source.items():
        nested = target.setdefault(key, {})
        merge_numeric_dict(nested, values)


def round_numeric_dict(items: dict[str, Any]) -> dict[str, float]:
    return {key: round1(value) for key, value in sorted(items.items())}


def round_nested_numeric_dict(items: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {key: round_numeric_dict(value) for key, value in sorted(items.items())}


def cost_per_score_by_set(stamina_by_set: dict[str, float], score_by_set: dict[str, float]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for set_code, stamina in sorted(stamina_by_set.items()):
        score = score_by_set.get(set_code, 0.0)
        result[set_code] = round1(stamina / score) if score else None
    return result


def stop_rate_by_set(stop_counts_by_set: dict[str, dict[str, int]], run_counts_by_set: dict[str, int]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for set_code, counts in sorted(stop_counts_by_set.items()):
        runs = run_counts_by_set.get(set_code, 0)
        result[set_code] = {checkpoint: round_rate(value / runs) if runs else 0.0 for checkpoint, value in sorted(counts.items())}
    return result


def efficiency_summary(score: float, stamina: float) -> dict[str, float | None]:
    return {
        "baili_score_per_1000_stamina": round1(score * 1000 / stamina) if stamina else 0.0,
        "cost_per_baili_score": round1(stamina / score) if score else None,
    }


def share_dict(items: dict[str, Any], total: float) -> dict[str, float]:
    if not total:
        return {}
    return {key: round_rate(value / total) for key, value in sorted(items.items())}


def future_hit_count(gear: Gear) -> int:
    return max(0, (15 - checkpoint_for(gear.enhance)) // 3)


def checkpoint_for(enhance: int) -> int:
    for point in reversed(CHECKPOINTS):
        if enhance >= point:
            return point
    return 0


def stat_debug(stat: Stat) -> dict[str, Any]:
    return {"type": stat.type, "key": stat.key, "value": stat.normalized_value, "rolls": stat.rolls}


def avg(items: list[dict[str, Any]], key: str) -> float:
    return round1(sum(float(item[key]) for item in items) / len(items)) if items else 0.0


def round_rate(value: float) -> float:
    return round(float(value) + 1e-12, 4)


def round_float(value: float, digits: int) -> float:
    return round(float(value) + 1e-12, digits)


def project_reforge_score(gear: Gear, item_source: str) -> float:
    return expected_final_reforge_score(gear, item_source)["expected_final_reforge_score"]


def project_reforge_speed(gear: Gear, item_source: str) -> float:
    return expected_final_reforge_speed(gear, item_source)
