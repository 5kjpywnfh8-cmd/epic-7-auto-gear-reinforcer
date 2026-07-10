from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import json
import random
from pathlib import Path
from typing import Any

from .calibration import (
    candidate_policies,
    checkpoint_for,
    conversion_plan_for_gear,
    final_success_breakdown,
    gear_after_conversion,
    is_formal_baili_source_row,
    seed_for_index,
    should_continue,
)
from .enhance_simulator import (
    CHECKPOINTS,
    RollProfile,
    STAT_POOL,
    STAT_TYPE_BY_KEY,
    SimulationOptions,
    enhance_to_checkpoint,
    generate_gear,
    reforge_gear,
    recovery_for_rank,
    roll_range,
    is_new_substat_event,
    slot_forbidden_substats,
)
from .models import Gear, RollHit, Stat, round1, validate_gear_source_rank, validate_gear_structure
from .resource_model import RED_EPIC_CALIBRATION
from .rules import speed_potential_set_eligible
from .score_engine import evaluate_gear, speed_value


DEFAULT_ROUND2_SUMMARY = Path("reports/baili-formal-round2-summary.json")
FORMAL_SCORE_SCOPE = "R2-R58 formal baili score; R61 future is auxiliary only"
DEFAULT_SEED = 17
DEFAULT_RUNS = 1000
REPORT_CONFIGS = (
    {
        "key": "normal_epic",
        "summary_run_key": "normal_epic_1m",
        "label": "normal_85 Epic",
        "item_source": "normal_85",
        "rank": "Epic",
        "policy": "category_baili_marginal_mid",
        "runs": DEFAULT_RUNS,
    },
    {
        "key": "normal_heroic",
        "summary_run_key": "normal_heroic_1m",
        "label": "normal_85 Heroic",
        "item_source": "normal_85",
        "rank": "Heroic",
        "policy": "baili_marginal_low",
        "runs": DEFAULT_RUNS,
    },
    {
        "key": "rift_epic",
        "summary_run_key": "rift_epic_1m",
        "label": "rift_85 Epic",
        "item_source": "rift_85",
        "rank": "Epic",
        "policy": None,
        "runs": DEFAULT_RUNS,
    },
)


@dataclass(frozen=True)
class RouteResult:
    action: str
    checkpoint: int
    next_checkpoint: int | None
    stop_utility: float
    continue_utility: float | None
    expected_utility: float
    expected_formal_baili_score: float
    expected_terminal_value: float
    expected_terminal_speed: float
    expected_speed_rolls: float
    speed_potential_set_eligible: bool
    speed_potential_threshold_blocked_probability: float
    expected_speed_potential_value: float
    expected_incremental_stamina: float
    best_target_category: str
    best_source_row: str
    conversion_needed_probability: float
    terminal_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "checkpoint": self.checkpoint,
            "next_checkpoint": self.next_checkpoint,
            "stop_utility": round_float(self.stop_utility, 6),
            "continue_utility": round_float(self.continue_utility, 6) if self.continue_utility is not None else None,
            "expected_utility": round_float(self.expected_utility, 6),
            "expected_formal_baili_score": round1(self.expected_formal_baili_score),
            "expected_terminal_value": round1(self.expected_terminal_value),
            "expected_terminal_speed": round1(self.expected_terminal_speed),
            "expected_speed_rolls": round1(self.expected_speed_rolls),
            "speed_potential_set_eligible": self.speed_potential_set_eligible,
            "speed_potential_threshold_blocked_probability": round_rate(self.speed_potential_threshold_blocked_probability),
            "expected_speed_potential_value": round1(self.expected_speed_potential_value),
            "expected_incremental_stamina": round1(self.expected_incremental_stamina),
            "best_target_category": self.best_target_category,
            "best_source_row": self.best_source_row,
            "conversion_needed_probability": round_rate(self.conversion_needed_probability),
            "terminal_count": self.terminal_count,
        }


_ROUTE_CACHE: dict[tuple[str, str, str, str, bool, float, float], RouteResult] = {}
_CACHE_HITS = 0
_CACHE_MISSES = 0


def compute_optimal_route(
    gear: Gear,
    lambda_value: float,
    conversion_cost: float = 0,
    item_source: str = "normal_85",
    gear_source: str = "rift_new_1_32",
    rank: str | None = None,
) -> dict[str, Any]:
    validate_gear_structure(gear)
    validate_gear_source_rank(gear, item_source)
    allow_speed_momentum = checkpoint_for(gear.enhance) < 15
    result = _solve_state(
        gear,
        item_source,
        gear_source,
        rank or gear.rank,
        float(lambda_value),
        float(conversion_cost),
        allow_speed_momentum,
    )
    return result.to_dict()


def route_cache_info() -> dict[str, int]:
    return {"size": len(_ROUTE_CACHE), "hits": _CACHE_HITS, "misses": _CACHE_MISSES}


def clear_route_cache() -> None:
    global _CACHE_HITS, _CACHE_MISSES
    _ROUTE_CACHE.clear()
    _CACHE_HITS = 0
    _CACHE_MISSES = 0


def _solve_state(
    gear: Gear,
    item_source: str,
    gear_source: str,
    rank: str,
    lambda_value: float,
    conversion_cost: float,
    allow_speed_momentum: bool,
) -> RouteResult:
    global _CACHE_HITS, _CACHE_MISSES
    checkpoint = checkpoint_for(gear.enhance)
    cache_key = (
        gear_state_key(gear),
        item_source,
        gear_source,
        rank,
        allow_speed_momentum,
        round(lambda_value, 10),
        round(conversion_cost, 4),
    )
    cached = _ROUTE_CACHE.get(cache_key)
    if cached is not None:
        _CACHE_HITS += 1
        return cached
    _CACHE_MISSES += 1

    if checkpoint >= 15:
        result = terminal_route_result(gear, item_source, lambda_value, conversion_cost, allow_speed_momentum)
        _ROUTE_CACHE[cache_key] = result
        return result

    next_checkpoint = next(point for point in CHECKPOINTS if point > checkpoint)
    stop_utility = 0.0
    marginal_cost = marginal_net_stamina_cost(checkpoint, next_checkpoint, rank)
    outcomes = enumerate_next_checkpoint(gear, next_checkpoint, item_source)
    expected_score = 0.0
    expected_terminal_value = 0.0
    expected_terminal_speed = 0.0
    expected_speed_rolls = 0.0
    threshold_blocked_probability = 0.0
    expected_speed_potential_value = 0.0
    expected_stamina_after = 0.0
    expected_utility_after = 0.0
    conversion_probability = 0.0
    terminal_count = 0
    category_score: dict[str, float] = defaultdict(float)
    source_score: dict[str, float] = defaultdict(float)

    for child, probability in outcomes:
        child_result = _solve_state(child, item_source, gear_source, rank, lambda_value, conversion_cost, allow_speed_momentum)
        expected_score += probability * child_result.expected_formal_baili_score
        expected_terminal_value += probability * child_result.expected_terminal_value
        expected_terminal_speed += probability * child_result.expected_terminal_speed
        expected_speed_rolls += probability * child_result.expected_speed_rolls
        threshold_blocked_probability += probability * child_result.speed_potential_threshold_blocked_probability
        expected_speed_potential_value += probability * child_result.expected_speed_potential_value
        expected_stamina_after += probability * child_result.expected_incremental_stamina
        expected_utility_after += probability * child_result.expected_utility
        conversion_probability += probability * child_result.conversion_needed_probability
        terminal_count += child_result.terminal_count
        category_score[child_result.best_target_category] += probability * child_result.expected_terminal_value
        source_score[child_result.best_source_row] += probability * child_result.expected_terminal_value

    continue_stamina = marginal_cost + expected_stamina_after
    continue_utility = expected_utility_after - lambda_value * marginal_cost
    if continue_utility > stop_utility:
        result = RouteResult(
            action="continue",
            checkpoint=checkpoint,
            next_checkpoint=next_checkpoint,
            stop_utility=stop_utility,
            continue_utility=continue_utility,
            expected_utility=continue_utility,
            expected_formal_baili_score=expected_score,
            expected_terminal_value=expected_terminal_value,
            expected_terminal_speed=expected_terminal_speed,
            expected_speed_rolls=expected_speed_rolls,
            speed_potential_set_eligible=speed_potential_set_eligible(gear.set),
            speed_potential_threshold_blocked_probability=threshold_blocked_probability,
            expected_speed_potential_value=expected_speed_potential_value,
            expected_incremental_stamina=continue_stamina,
            best_target_category=best_key(category_score),
            best_source_row=best_key(source_score),
            conversion_needed_probability=conversion_probability,
            terminal_count=max(1, terminal_count),
        )
    else:
        result = RouteResult(
            action="stop",
            checkpoint=checkpoint,
            next_checkpoint=next_checkpoint,
            stop_utility=stop_utility,
            continue_utility=continue_utility,
            expected_utility=stop_utility,
            expected_formal_baili_score=0.0,
            expected_terminal_value=0.0,
            expected_terminal_speed=expected_terminal_speed,
            expected_speed_rolls=expected_speed_rolls,
            speed_potential_set_eligible=speed_potential_set_eligible(gear.set),
            speed_potential_threshold_blocked_probability=threshold_blocked_probability,
            expected_speed_potential_value=expected_speed_potential_value,
            expected_incremental_stamina=0.0,
            best_target_category="stop",
            best_source_row="-",
            conversion_needed_probability=0.0,
            terminal_count=max(1, terminal_count),
        )
    _ROUTE_CACHE[cache_key] = result
    return result


def terminal_route_result(
    gear: Gear,
    item_source: str,
    lambda_value: float,
    conversion_cost: float,
    allow_speed_momentum: bool,
) -> RouteResult:
    final_gear = gear if gear.level >= 90 else reforge_gear(gear)
    evaluation = evaluate_gear(final_gear)
    breakdown = final_success_breakdown(evaluation, speed_value(final_gear), item_source)
    formal_score = float(breakdown["baili_score"]) if is_formal_terminal_success(breakdown, evaluation) else 0.0
    speed_info = speed_potential_info(final_gear)
    terminal_value, terminal_category = terminal_value_for(evaluation, formal_score, allow_speed_momentum, speed_info)
    conversion_needed = bool(breakdown["rescued_success"])
    source_row = evaluation.target_score_source_row
    if conversion_needed and formal_score > 0:
        conversion = conversion_plan_for_gear(final_gear, item_source, evaluation)
        converted_evaluation = evaluate_gear(gear_after_conversion(final_gear, conversion))
        source_row = converted_evaluation.target_score_source_row
    stamina = float(conversion_cost) if conversion_needed else 0.0
    utility = terminal_value - lambda_value * stamina
    return RouteResult(
        action="terminal",
        checkpoint=15,
        next_checkpoint=None,
        stop_utility=utility,
        continue_utility=None,
        expected_utility=utility,
        expected_formal_baili_score=formal_score,
        expected_terminal_value=terminal_value,
        expected_terminal_speed=speed_info["terminal_speed"],
        expected_speed_rolls=speed_info["speed_rolls"],
        speed_potential_set_eligible=speed_info["set_eligible"],
        speed_potential_threshold_blocked_probability=1.0 if speed_info["threshold_blocked"] else 0.0,
        expected_speed_potential_value=speed_info["value"],
        expected_incremental_stamina=stamina,
        best_target_category=breakdown["target_category"] if formal_score > 0 else terminal_category,
        best_source_row=source_row if formal_score > 0 else "terminal-speed-momentum" if terminal_category == "速度潜力" else "-",
        conversion_needed_probability=1.0 if conversion_needed and terminal_value > 0 else 0.0,
        terminal_count=1,
    )


def terminal_value_for(
    evaluation: Any,
    formal_score: float,
    allow_speed_momentum: bool,
    speed_info: dict[str, Any],
) -> tuple[float, str]:
    speed_value_score = speed_info["value"] if allow_speed_momentum else 0.0
    if formal_score >= speed_value_score and formal_score > 0:
        return formal_score, evaluation.retention.category
    if speed_value_score > 0:
        return speed_value_score, "速度潜力"
    return 0.0, "none"


def speed_potential_info(gear: Gear) -> dict[str, Any]:
    speed_stats = [stat for stat in gear.substats if stat.key == "spd"]
    terminal_speed = speed_value(gear)
    speed_rolls = speed_stats[0].rolls if speed_stats else 0
    set_eligible = speed_potential_set_eligible(gear.set)
    threshold_blocked = bool(speed_rolls > 1 and not set_eligible and terminal_speed < 20)
    value = terminal_speed * (speed_rolls - 1) if speed_rolls > 1 and (set_eligible or terminal_speed >= 20) else 0.0
    return {
        "terminal_speed": terminal_speed,
        "speed_rolls": speed_rolls,
        "set_eligible": set_eligible,
        "threshold_blocked": threshold_blocked,
        "value": round1(value),
    }


def is_formal_terminal_success(breakdown: dict[str, Any], evaluation: Any) -> bool:
    if not breakdown["final_success"]:
        return False
    if breakdown["native_success"]:
        return is_formal_baili_source_row(evaluation.target_score_source_row)
    return breakdown["baili_score"] > 0


def enumerate_next_checkpoint(gear: Gear, next_checkpoint: int, item_source: str) -> list[tuple[Gear, float]]:
    if is_new_substat_event(gear.rank, next_checkpoint) and len(gear.substats) < 4:
        outcomes = missing_substat_outcomes(gear, next_checkpoint, item_source)
    else:
        outcomes = roll_outcomes(gear, next_checkpoint, item_source)
    return combine_duplicate_outcomes(outcomes)


def roll_outcomes(gear: Gear, next_checkpoint: int, item_source: str) -> list[tuple[Gear, float]]:
    if not gear.substats:
        return [(replace(gear, enhance=next_checkpoint), 1.0)]
    outcomes: list[tuple[Gear, float]] = []
    stat_probability = 1.0 / len(gear.substats)
    for index, stat in enumerate(gear.substats):
        low, high = roll_range(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), stat.key)
        value_probability = stat_probability / (high - low + 1)
        for delta in range(low, high + 1):
            updated = replace(stat, value=round1(stat.normalized_value + delta), rolls=stat.rolls + 1)
            substats = list(gear.substats)
            substats[index] = updated
            history = list(gear.roll_history) + [RollHit(next_checkpoint, updated.type, delta)]
            outcomes.append((replace(gear, enhance=next_checkpoint, substats=substats, roll_history=history), value_probability))
    return outcomes


def missing_substat_outcomes(gear: Gear, next_checkpoint: int, item_source: str) -> list[tuple[Gear, float]]:
    existing = {stat.key for stat in gear.substats}
    existing.add(gear.main_stat.key)
    available = [key for key in STAT_POOL if key not in existing and key not in slot_forbidden_substats(gear.slot)]
    if not available:
        return [(replace(gear, enhance=next_checkpoint), 1.0)]
    outcomes: list[tuple[Gear, float]] = []
    key_probability = 1.0 / len(available)
    for key in available:
        low, high = roll_range(RollProfile(gear.roll_level or gear.level, gear.rank, item_source), key)
        value_probability = key_probability / (high - low + 1)
        for value in range(low, high + 1):
            substat = Stat(STAT_TYPE_BY_KEY[key], value, rolls=1)
            outcomes.append((replace(gear, enhance=next_checkpoint, substats=list(gear.substats) + [substat]), value_probability))
    return outcomes


def combine_duplicate_outcomes(outcomes: list[tuple[Gear, float]]) -> list[tuple[Gear, float]]:
    combined: dict[str, tuple[Gear, float]] = {}
    for gear, probability in outcomes:
        key = gear_state_key(gear)
        if key in combined:
            existing, current_probability = combined[key]
            combined[key] = (existing, current_probability + probability)
        else:
            combined[key] = (gear, probability)
    return list(combined.values())


def marginal_net_stamina_cost(current_checkpoint: int, next_checkpoint: int, rank: str) -> float:
    calibration = RED_EPIC_CALIBRATION
    interval = calibration.interval_costs[next_checkpoint]
    current_recovery = recovery_for_rank(calibration.sell_recovery.get(current_checkpoint), rank)
    next_recovery = recovery_for_rank(calibration.sell_recovery.get(next_checkpoint), rank)
    lost_recovery = current_recovery - next_recovery
    return max(0.0, calibration.rates.stamina_equivalent(interval + lost_recovery))


def load_round2_recommendations(path: str | Path = DEFAULT_ROUND2_SUMMARY) -> tuple[dict[str, dict[str, Any]], list[str]]:
    summary_path = Path(path)
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    risks = validate_round2_seed_files(data, summary_path.parent.parent if summary_path.parent.name == "reports" else Path("."))
    recommendations: dict[str, dict[str, Any]] = {}
    for config in REPORT_CONFIGS:
        run = data["runs"][config["summary_run_key"]]
        policy_name = config["policy"] or first_policy_by_mean_cost(run)
        aggregate = run["policy_aggregate"][policy_name]
        cost = mean_metric(aggregate["cost_per_baili_score"])
        recommendations[config["key"]] = {
            **config,
            "policy": policy_name,
            "cost_per_baili_score": cost,
            "lambda_value": 1 / cost if cost else 0.0,
            "summary_run_key": config["summary_run_key"],
        }
    return recommendations, risks


def validate_round2_seed_files(data: dict[str, Any], base: Path) -> list[str]:
    risks = []
    for run_key, run in data.get("runs", {}).items():
        for file_name in run.get("files", []):
            path = base / file_name
            if not path.exists():
                risks.append(f"{run_key}: missing seed file {file_name}")
                continue
            if path.stat().st_size <= 0:
                risks.append(f"{run_key}: empty seed file {file_name}")
                continue
            try:
                json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception as exc:  # pragma: no cover - defensive report field
                risks.append(f"{run_key}: unreadable seed file {file_name}: {exc}")
    return risks


def first_policy_by_mean_cost(run: dict[str, Any]) -> str:
    items = list(run.get("policy_aggregate", {}).values())
    items.sort(key=lambda item: mean_metric(item.get("cost_per_baili_score")) or float("inf"))
    return items[0]["policy_name"]


def mean_metric(value: Any) -> float | None:
    if isinstance(value, dict):
        return float(value["mean"]) if value.get("mean") is not None else None
    return float(value) if value is not None else None


def replay_checkpoint_gears(
    checkpoint: int,
    runs: int,
    seed: int,
    item_source: str,
    rank: str,
) -> list[Gear]:
    gears = []
    for index in range(runs):
        item_seed = seed_for_index(seed, index)
        rng = random.Random(item_seed)
        gear = generate_gear(rng, SimulationOptions(seed=item_seed, item_source=item_source, rank=rank))
        for next_checkpoint in CHECKPOINTS:
            if next_checkpoint == 0:
                continue
            if next_checkpoint > checkpoint:
                break
            gear, _ = enhance_to_checkpoint(gear, next_checkpoint, item_source, rng)
        gears.append(gear)
    return gears


def compare_policy_with_dp(
    gears: list[Gear],
    policy_name: str,
    lambda_value: float,
    item_source: str,
    rank: str,
    conversion_cost: float,
) -> dict[str, Any]:
    policies = {policy.name: policy for policy in candidate_policies()}
    if policy_name not in policies:
        raise KeyError(f"unknown policy: {policy_name}")
    policy = policies[policy_name]
    matrix = Counter()
    disagreements = []
    disagreement_by_category = Counter()
    disagreement_by_set = Counter()
    disagreement_by_slot = Counter()

    for index, gear in enumerate(gears):
        policy_continue = should_continue(gear, policy, item_source)
        route = compute_optimal_route(gear, lambda_value, conversion_cost, item_source, rank=rank)
        dp_continue = route["action"] == "continue"
        key = confusion_key(policy_continue, dp_continue)
        matrix[key] += 1
        if policy_continue != dp_continue:
            disagreement_by_category[route["best_target_category"]] += 1
            disagreement_by_set[gear.set] += 1
            disagreement_by_slot[gear.slot] += 1
            disagreements.append(disagreement_record(index, gear, policy_continue, dp_continue, route))

    total = len(gears)
    disagreement_count = matrix["policy_continue_dp_stop"] + matrix["policy_stop_dp_continue"]
    return {
        "runs": total,
        "policy_name": policy_name,
        "lambda_value": lambda_value,
        "conversion_cost": conversion_cost,
        "confusion_matrix": {
            "both_continue": matrix["both_continue"],
            "both_stop": matrix["both_stop"],
            "policy_continue_dp_stop": matrix["policy_continue_dp_stop"],
            "policy_stop_dp_continue": matrix["policy_stop_dp_continue"],
        },
        "agreement_rate": round_rate((matrix["both_continue"] + matrix["both_stop"]) / total) if total else 0.0,
        "disagreement_rate": round_rate(disagreement_count / total) if total else 0.0,
        "bias": bias_label(matrix),
        "disagreement_by_category": dict(disagreement_by_category.most_common()),
        "disagreement_by_set": dict(disagreement_by_set.most_common()),
        "disagreement_by_slot": dict(disagreement_by_slot.most_common()),
        "top_disagreements": sorted(disagreements, key=lambda item: item["utility_gap"], reverse=True)[:20],
    }


def disagreement_record(index: int, gear: Gear, policy_continue: bool, dp_continue: bool, route: dict[str, Any]) -> dict[str, Any]:
    continue_utility = route["continue_utility"] if route["continue_utility"] is not None else route["expected_utility"]
    utility_gap = abs(float(continue_utility or 0.0))
    return {
        "sample_index": index,
        "gear": gear.to_dict(),
        "checkpoint": checkpoint_for(gear.enhance),
        "policy_decision": "continue" if policy_continue else "stop",
        "dp_decision": "continue" if dp_continue else "stop",
        "expected_formal_baili_score": route["expected_formal_baili_score"],
        "expected_incremental_stamina": route["expected_incremental_stamina"],
        "expected_utility": route["expected_utility"],
        "continue_utility": route["continue_utility"],
        "utility_gap": round_float(utility_gap, 6),
        "best_target_category": route["best_target_category"],
        "best_source_row": route["best_source_row"],
        "conversion_needed_probability": route["conversion_needed_probability"],
        "set": gear.set,
        "slot": gear.slot,
        "mainStat": {"type": gear.main_stat.type, "value": gear.main_stat.value},
        "substats": [{"type": stat.type, "value": stat.value, "rolls": stat.rolls} for stat in gear.substats],
    }


def confusion_key(policy_continue: bool, dp_continue: bool) -> str:
    if policy_continue and dp_continue:
        return "both_continue"
    if not policy_continue and not dp_continue:
        return "both_stop"
    if policy_continue and not dp_continue:
        return "policy_continue_dp_stop"
    return "policy_stop_dp_continue"


def bias_label(matrix: Counter) -> str:
    aggressive = matrix["policy_continue_dp_stop"]
    conservative = matrix["policy_stop_dp_continue"]
    if aggressive > conservative:
        return "policy_more_aggressive"
    if conservative > aggressive:
        return "policy_more_conservative"
    return "balanced_or_no_clear_bias"


def run_round3_report(
    summary_path: str | Path = DEFAULT_ROUND2_SUMMARY,
    reports_dir: str | Path = "reports",
    runs: int = DEFAULT_RUNS,
    seed: int = DEFAULT_SEED,
    conversion_cost: float = 0,
) -> dict[str, Any]:
    recommendations, risks = load_round2_recommendations(summary_path)
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    sections = []
    for key, recommendation in recommendations.items():
        config_runs = min(int(runs), int(recommendation.get("runs") or runs))
        checkpoint_results = {}
        for checkpoint in (9, 12):
            clear_route_cache()
            gears = replay_checkpoint_gears(
                checkpoint=checkpoint,
                runs=config_runs,
                seed=seed,
                item_source=recommendation["item_source"],
                rank=recommendation["rank"],
            )
            comparison = compare_policy_with_dp(
                gears,
                recommendation["policy"],
                recommendation["lambda_value"],
                recommendation["item_source"],
                recommendation["rank"],
                conversion_cost,
            )
            comparison["checkpoint"] = checkpoint
            comparison["cache"] = route_cache_info()
            checkpoint_results[str(checkpoint)] = comparison
            detail_path = reports_path / f"route-solver-{key.replace('_', '-')}-checkpoint{checkpoint}-seed{seed}.json"
            detail_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
        sections.append(
            {
                "key": key,
                "label": recommendation["label"],
                "item_source": recommendation["item_source"],
                "rank": recommendation["rank"],
                "policy": recommendation["policy"],
                "cost_per_baili_score": recommendation["cost_per_baili_score"],
                "lambda_value": recommendation["lambda_value"],
                "checkpoints": checkpoint_results,
                "recommendation": route_recommendation(checkpoint_results),
            }
        )

    report = {
        "scope": {
            "stage": "round3_route_solver",
            "score_scope": FORMAL_SCORE_SCOPE,
            "ranking_lambda": "lambda_value = 1 / round2 cost_per_baili_score",
            "round2_rerun": False,
            "calibration_rerun": False,
            "conversion_cost": conversion_cost,
        },
        "seed": seed,
        "runs_per_checkpoint": runs,
        "round2_risks": risks,
        "sections": sections,
        "overall": overall_recommendation(sections),
    }
    (reports_path / "route-solver-round3-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_path / "route-solver-round3-summary.md").write_text(render_round3_markdown(report), encoding="utf-8")
    return report


def route_recommendation(checkpoints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    max_disagreement = max((item["disagreement_rate"] for item in checkpoints.values()), default=0.0)
    plus12 = checkpoints.get("12", {})
    enter_next = (
        max_disagreement > 0.10
        or plus12.get("disagreement_rate", 0.0) > 0.10
        or any(item["top_disagreements"] and item["top_disagreements"][0]["utility_gap"] >= 1.0 for item in checkpoints.values())
    )
    if not enter_next:
        action = "keep_current_policy"
        reason = "DP disagreement is below the round3 replacement threshold."
    else:
        action = "consider_dp_assisted"
        reason = "DP disagreement or utility gap meets the round3 review threshold."
    replace_scope = "none"
    if enter_next:
        replace_scope = "plus12_only" if plus12.get("disagreement_rate", 0.0) >= checkpoints.get("9", {}).get("disagreement_rate", 0.0) else "plus9_and_plus12"
    return {"action": action, "replace_scope": replace_scope, "reason": reason}


def overall_recommendation(sections: list[dict[str, Any]]) -> dict[str, Any]:
    max_rate = max((checkpoint["disagreement_rate"] for section in sections for checkpoint in section["checkpoints"].values()), default=0.0)
    should_design = any(section["recommendation"]["action"] == "consider_dp_assisted" for section in sections)
    return {
        "max_disagreement_rate": max_rate,
        "dp_assisted_recommended": should_design,
        "conclusion": (
            "Design dp_assisted for the flagged checkpoint(s)."
            if should_design
            else "Current round2 policies are close to DP route optimum; keep DP as review tooling for now."
        ),
        "needs_100k_or_1m_validation": should_design,
    }


def render_round3_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Round3 强化路线精确复核",
        "",
        f"- 评分范围：{report['scope']['score_scope']}",
        f"- 样本：每类每 checkpoint {report['runs_per_checkpoint']} 件，seed={report['seed']}",
        f"- round2 大样本重跑：{report['scope']['round2_rerun']}",
        f"- conversion_cost：{report['scope']['conversion_cost']}",
        "",
        "## 总结",
        "",
        f"- 最大分歧率：{round1(report['overall']['max_disagreement_rate'] * 100)}%",
        f"- 是否建议进入 dp_assisted：{'是' if report['overall']['dp_assisted_recommended'] else '否'}",
        f"- 结论：{report['overall']['conclusion']}",
        "",
    ]
    if report["round2_risks"]:
        lines.extend(["## round2 文件风险", ""])
        lines.extend(f"- {risk}" for risk in report["round2_risks"])
        lines.append("")
    for section in report["sections"]:
        lines.extend(
            [
                f"## {section['label']}",
                "",
                f"- 当前策略：{section['policy']}",
                f"- cost_per_baili_score：{section['cost_per_baili_score']}",
                f"- lambda：{round_float(section['lambda_value'], 8)}",
                f"- 建议：{section['recommendation']['action']} / {section['recommendation']['replace_scope']}",
                "",
                "| checkpoint | 一致率 | 分歧率 | both_continue | both_stop | policy_continue_dp_stop | policy_stop_dp_continue | 偏向 |",
                "|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
        )
        for checkpoint in ("9", "12"):
            item = section["checkpoints"][checkpoint]
            matrix = item["confusion_matrix"]
            lines.append(
                f"| +{checkpoint} | {round1(item['agreement_rate'] * 100)}% | {round1(item['disagreement_rate'] * 100)}% | "
                f"{matrix['both_continue']} | {matrix['both_stop']} | {matrix['policy_continue_dp_stop']} | "
                f"{matrix['policy_stop_dp_continue']} | {item['bias']} |"
            )
        lines.extend(["", "分歧集中："])
        for checkpoint in ("9", "12"):
            item = section["checkpoints"][checkpoint]
            lines.append(
                f"- +{checkpoint}: 分类 {top_counter_text(item['disagreement_by_category'])}; "
                f"套装 {top_counter_text(item['disagreement_by_set'])}; 部位 {top_counter_text(item['disagreement_by_slot'])}"
            )
        lines.append("")
    return "\n".join(lines)


def top_counter_text(items: dict[str, int], limit: int = 3) -> str:
    if not items:
        return "无明显分歧"
    return ", ".join(f"{key}={value}" for key, value in list(items.items())[:limit])


def gear_state_key(gear: Gear) -> str:
    payload = {
        "set": gear.set,
        "slot": gear.slot,
        "main": [gear.main_stat.key, round1(gear.main_stat.normalized_value)],
        "enhance": checkpoint_for(gear.enhance),
        "level": gear.level,
        "roll_level": gear.roll_level,
        "rank": gear.rank,
        "reforge_eligible": gear.reforge_eligible,
        "substats": sorted([stat.key, round1(stat.normalized_value), int(stat.rolls), bool(stat.modified)] for stat in gear.substats),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def best_key(scores: dict[str, float]) -> str:
    if not scores:
        return "none"
    return max(scores.items(), key=lambda item: (item[1], item[0]))[0]


def round_rate(value: float) -> float:
    return round(float(value) + 1e-12, 4)


def round_float(value: float | None, digits: int) -> float:
    return round(float(value or 0.0) + 1e-12, digits)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Round3 DP route solver for Epic Seven gear enhancement.")
    parser.add_argument("--summary", default=str(DEFAULT_ROUND2_SUMMARY))
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--conversion-cost", type=float, default=0)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    report = run_round3_report(args.summary, args.reports_dir, args.runs, args.seed, args.conversion_cost)
    if args.debug:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_round3_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
