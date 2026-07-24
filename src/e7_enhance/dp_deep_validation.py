from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import math
from pathlib import Path
import random
from typing import Any

from .calibration import (
    CalibrationOptions,
    build_full_trace,
    candidate_policies,
    calibration_chunks,
    finalize_policy_accumulator,
    merge_policy_accumulator,
    new_policy_accumulator,
    round_float,
    round_rate,
    seed_for_index,
    simulate_policy_from_trace,
    update_policy_accumulator,
    worker_count,
)
from .enhance_simulator import SimulationOptions, generate_gear
from .models import round1


DEEP_RUNS = {
    "normal_epic": {
        "label": "normal_85 Epic",
        "item_source": "normal_85",
        "rank": "Epic",
        "baseline_policy": "category_baili_marginal_mid",
        "dp_policy": "normal_epic_dp_assisted",
        "file_stem": "normal-epic",
    },
}


def run_deep_validation(
    reports_dir: str | Path = "reports",
    runs: int = 1_000_000,
    seeds: list[int] | None = None,
    workers: int = 1,
    dp_utility_margin: float = 0.1,
) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    seeds = seeds or [17, 29, 43, 71, 101]
    sections = []
    for key, config in DEEP_RUNS.items():
        seed_results = []
        for seed in seeds:
            seed_results.append(
                run_deep_seed(
                    key=key,
                    config=config,
                    reports_path=reports_path,
                    runs=runs,
                    seed=seed,
                    workers=workers,
                    dp_utility_margin=dp_utility_margin,
                )
            )
        sections.append(summarize_section(key, config, seed_results))
    report = {
        "scope": {
            "stage": "dp_assisted_deep_validation",
            "runs_per_seed": runs,
            "seeds": seeds,
            "workers": worker_count(workers),
            "dp_utility_margin": dp_utility_margin,
            "excluded": ["rift_85 Epic", "OCR", "ADB", "real click automation"],
        },
        "sections": sections,
        "overall": overall_decision(sections),
    }
    (reports_path / "dp-assisted-deep-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_path / "dp-assisted-deep-validation.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def run_deep_seed(
    key: str,
    config: dict[str, Any],
    reports_path: Path,
    runs: int,
    seed: int,
    workers: int,
    dp_utility_margin: float,
) -> dict[str, Any]:
    options = CalibrationOptions(
        runs=runs,
        seed=seed,
        item_source=config["item_source"],
        rank=config["rank"],
        workers=workers,
        top_limit=2,
        enable_dp_assist=True,
        dp_utility_margin=dp_utility_margin,
    )
    policies = policy_pair(config)
    worker_total = worker_count(workers)
    if worker_total <= 1 or runs < 2000:
        result = deep_range(0, runs, options, policies)
    else:
        result = new_deep_result(policies)
        with ProcessPoolExecutor(max_workers=worker_total) as executor:
            futures = [
                executor.submit(deep_range, start, end, options, policies)
                for start, end in calibration_chunks(runs, worker_total)
            ]
            for future in as_completed(futures):
                merge_deep_result(result, future.result())
    detail = finalize_deep_result(key, config, options, result)
    output_path = reports_path / f"dp-assisted-deep-{config['file_stem']}-{runs // 1_000_000}m-seed{seed}.json"
    output_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    return summarize_seed_detail(output_path, detail)


def policy_pair(config: dict[str, Any]):
    policies = {policy.name: policy for policy in candidate_policies(include_dp_assist=True, item_source=config["item_source"], rank=config["rank"])}
    return [policies[config["baseline_policy"]], policies[config["dp_policy"]]]


def deep_range(start: int, end: int, options: CalibrationOptions, policies: list[Any]) -> dict[str, Any]:
    result = new_deep_result(policies)
    baseline, dp_policy = policies
    for index in range(start, end):
        seed = seed_for_index(options.seed, index)
        rng = random.Random(seed)
        base = generate_gear(rng, SimulationOptions(seed=seed, item_source=options.item_source, rank=options.rank))
        trace = build_full_trace(base, options, rng)
        baseline_outcome = simulate_policy_from_trace(trace, baseline, options, index)
        dp_outcome = simulate_policy_from_trace(trace, dp_policy, options, index)
        update_policy_accumulator(result["accumulators"][baseline.name], baseline_outcome)
        update_policy_accumulator(result["accumulators"][dp_policy.name], dp_outcome)
        update_pair_stats(result["pair_stats"], baseline_outcome, dp_outcome)
    return result


def new_deep_result(policies: list[Any]) -> dict[str, Any]:
    return {
        "accumulators": {policy.name: new_policy_accumulator(policy) for policy in policies},
        "pair_stats": new_pair_stats(),
    }


def new_pair_stats() -> dict[str, Any]:
    return {
        "samples": 0,
        "dp_changed_samples": 0,
        "dp_changed_improved_baili_samples": 0,
        "dp_changed_lowered_baili_samples": 0,
        "dp_changed_same_baili_samples": 0,
        "dp_changed_total_baili_delta": 0.0,
        "dp_changed_total_stamina_delta": 0.0,
        "dp_changed_success_gain_samples": 0,
        "dp_changed_success_loss_samples": 0,
        "dp_changed_success_same_samples": 0,
        "dp_changed_by_checkpoint": {},
    }


def update_pair_stats(stats: dict[str, Any], baseline: dict[str, Any], dp: dict[str, Any]) -> None:
    stats["samples"] += 1
    if int(dp.get("dp_changed_decision_count") or 0) <= 0:
        return
    stats["dp_changed_samples"] += 1
    baili_delta = float(dp.get("baili_score") or 0.0) - float(baseline.get("baili_score") or 0.0)
    stamina_delta = float(dp.get("total_stamina") or 0.0) - float(baseline.get("total_stamina") or 0.0)
    stats["dp_changed_total_baili_delta"] += baili_delta
    stats["dp_changed_total_stamina_delta"] += stamina_delta
    if baili_delta > 0:
        stats["dp_changed_improved_baili_samples"] += 1
    elif baili_delta < 0:
        stats["dp_changed_lowered_baili_samples"] += 1
    else:
        stats["dp_changed_same_baili_samples"] += 1
    if bool(dp.get("success")) and not bool(baseline.get("success")):
        stats["dp_changed_success_gain_samples"] += 1
    elif bool(baseline.get("success")) and not bool(dp.get("success")):
        stats["dp_changed_success_loss_samples"] += 1
    else:
        stats["dp_changed_success_same_samples"] += 1
    for checkpoint, count in (dp.get("dp_changed_by_checkpoint") or {}).items():
        stats["dp_changed_by_checkpoint"][checkpoint] = stats["dp_changed_by_checkpoint"].get(checkpoint, 0) + int(count)


def merge_deep_result(target: dict[str, Any], source: dict[str, Any]) -> None:
    for name, accumulator in source["accumulators"].items():
        merge_policy_accumulator(target["accumulators"][name], accumulator)
    merge_pair_stats(target["pair_stats"], source["pair_stats"])


def merge_pair_stats(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in (
        "samples",
        "dp_changed_samples",
        "dp_changed_improved_baili_samples",
        "dp_changed_lowered_baili_samples",
        "dp_changed_same_baili_samples",
        "dp_changed_total_baili_delta",
        "dp_changed_total_stamina_delta",
        "dp_changed_success_gain_samples",
        "dp_changed_success_loss_samples",
        "dp_changed_success_same_samples",
    ):
        target[key] += source[key]
    for checkpoint, count in source["dp_changed_by_checkpoint"].items():
        target["dp_changed_by_checkpoint"][checkpoint] = target["dp_changed_by_checkpoint"].get(checkpoint, 0) + count


def finalize_deep_result(key: str, config: dict[str, Any], options: CalibrationOptions, result: dict[str, Any]) -> dict[str, Any]:
    policies = [finalize_policy_accumulator(accumulator) for accumulator in result["accumulators"].values()]
    policies.sort(key=lambda item: 0 if item["policy_name"] == config["baseline_policy"] else 1)
    baseline = next(item for item in policies if item["policy_name"] == config["baseline_policy"])
    dp_policy = next(item for item in policies if item["policy_name"] == config["dp_policy"])
    return {
        "key": key,
        "label": config["label"],
        "calibration_runs": options.runs,
        "seed": options.seed,
        "item_source": config["item_source"],
        "rank": config["rank"],
        "baseline_policy": config["baseline_policy"],
        "dp_policy": config["dp_policy"],
        "best_policy": best_policy_name(baseline, dp_policy),
        "policies": policies,
        "comparison": seed_comparison(baseline, dp_policy, result["pair_stats"]),
    }


def seed_comparison(baseline: dict[str, Any], dp_policy: dict[str, Any], pair_stats: dict[str, Any]) -> dict[str, Any]:
    cost_delta = none_delta(dp_policy.get("cost_per_baili_score"), baseline.get("cost_per_baili_score"))
    score_delta = none_delta(dp_policy.get("baili_score_per_1000_stamina"), baseline.get("baili_score_per_1000_stamina"))
    return {
        "cost_per_baili_score_delta": cost_delta,
        "baili_score_per_1000_stamina_delta": score_delta,
        "dp_better_by_cost": cost_delta is not None and cost_delta < 0,
        "dp_better_by_score_rate": score_delta is not None and score_delta > 0,
        "dp_changed_sample_stats": format_pair_stats(pair_stats),
        "stop_rate_delta_by_checkpoint": dict_delta(dp_policy["stop_rate_by_checkpoint"], baseline["stop_rate_by_checkpoint"]),
        "baili_tier_rate_delta": dict_delta(dp_policy["baili_tier_rate"], baseline["baili_tier_rate"]),
        "category_contribution_delta": dict_delta(dp_policy["target_score_by_category"], baseline["target_score_by_category"]),
        "set_contribution_delta": dict_delta(dp_policy["baili_score_by_set"], baseline["baili_score_by_set"]),
    }


def format_pair_stats(stats: dict[str, Any]) -> dict[str, Any]:
    changed = stats["dp_changed_samples"]
    return {
        "samples": stats["samples"],
        "dp_changed_samples": changed,
        "dp_changed_sample_rate": round_rate(changed / stats["samples"]) if stats["samples"] else 0.0,
        "improved_baili_samples": stats["dp_changed_improved_baili_samples"],
        "lowered_baili_samples": stats["dp_changed_lowered_baili_samples"],
        "same_baili_samples": stats["dp_changed_same_baili_samples"],
        "success_gain_samples": stats["dp_changed_success_gain_samples"],
        "success_loss_samples": stats["dp_changed_success_loss_samples"],
        "success_same_samples": stats["dp_changed_success_same_samples"],
        "total_baili_delta": round1(stats["dp_changed_total_baili_delta"]),
        "total_stamina_delta": round1(stats["dp_changed_total_stamina_delta"]),
        "changed_by_checkpoint": dict(sorted(stats["dp_changed_by_checkpoint"].items())),
    }


def summarize_seed_detail(output_path: Path, detail: dict[str, Any]) -> dict[str, Any]:
    policies = {policy["policy_name"]: policy for policy in detail["policies"]}
    baseline = policies[detail["baseline_policy"]]
    dp_policy = policies[detail["dp_policy"]]
    return {
        "key": detail["key"],
        "label": detail["label"],
        "seed": detail["seed"],
        "runs": detail["calibration_runs"],
        "file": str(output_path).replace("\\", "/"),
        "baseline_policy": detail["baseline_policy"],
        "dp_policy": detail["dp_policy"],
        "best_policy": detail["best_policy"],
        "baseline_cost_per_baili_score": baseline["cost_per_baili_score"],
        "dp_cost_per_baili_score": dp_policy["cost_per_baili_score"],
        "cost_per_baili_score_delta": detail["comparison"]["cost_per_baili_score_delta"],
        "baseline_baili_score_per_1000_stamina": baseline["baili_score_per_1000_stamina"],
        "dp_baili_score_per_1000_stamina": dp_policy["baili_score_per_1000_stamina"],
        "baili_score_per_1000_stamina_delta": detail["comparison"]["baili_score_per_1000_stamina_delta"],
        "baseline_native_success_rate": baseline["native_success_rate"],
        "dp_native_success_rate": dp_policy["native_success_rate"],
        "baseline_rescued_success_rate": baseline["rescued_success_rate"],
        "dp_rescued_success_rate": dp_policy["rescued_success_rate"],
        "baseline_conversion_needed_rate": baseline["conversion_needed_rate"],
        "dp_conversion_needed_rate": dp_policy["conversion_needed_rate"],
        "baseline_stop_rate_by_checkpoint": baseline["stop_rate_by_checkpoint"],
        "dp_stop_rate_by_checkpoint": dp_policy["stop_rate_by_checkpoint"],
        "baseline_baili_tier_rate": baseline["baili_tier_rate"],
        "dp_baili_tier_rate": dp_policy["baili_tier_rate"],
        "dp_call_count": dp_policy["dp_call_count"],
        "dp_changed_decision_count": dp_policy["dp_changed_decision_count"],
        "dp_changed_to_continue_count": dp_policy["dp_changed_to_continue_count"],
        "dp_changed_to_stop_count": dp_policy["dp_changed_to_stop_count"],
        "dp_covered_checkpoints": dp_policy["dp_covered_checkpoints"],
        "dp_changed_by_checkpoint": dp_policy["dp_changed_by_checkpoint"],
        "dp_changed_sample_stats": detail["comparison"]["dp_changed_sample_stats"],
        "category_contribution_delta": detail["comparison"]["category_contribution_delta"],
        "set_contribution_delta": detail["comparison"]["set_contribution_delta"],
    }


def summarize_section(key: str, config: dict[str, Any], seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_costs = [item["baseline_cost_per_baili_score"] for item in seed_results]
    dp_costs = [item["dp_cost_per_baili_score"] for item in seed_results]
    baseline_rates = [item["baseline_baili_score_per_1000_stamina"] for item in seed_results]
    dp_rates = [item["dp_baili_score_per_1000_stamina"] for item in seed_results]
    return {
        "key": key,
        "label": config["label"],
        "baseline_policy": config["baseline_policy"],
        "dp_policy": config["dp_policy"],
        "seed_results": seed_results,
        "statistics": {
            "baseline_cost_per_baili_score": sample_stats(baseline_costs),
            "dp_cost_per_baili_score": sample_stats(dp_costs),
            "baseline_baili_score_per_1000_stamina": sample_stats(baseline_rates),
            "dp_baili_score_per_1000_stamina": sample_stats(dp_rates),
            "cost_delta_dp_minus_baseline": sample_stats([item["cost_per_baili_score_delta"] for item in seed_results]),
            "score_rate_delta_dp_minus_baseline": sample_stats([item["baili_score_per_1000_stamina_delta"] for item in seed_results]),
        },
        "seed_rank_stability": seed_rank_stability(seed_results),
        "aggregate_deltas": aggregate_deltas(seed_results),
        "recommendation": recommendation_for(seed_results, baseline_costs, dp_costs),
    }


def sample_stats(values: list[float | None]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    count = len(clean)
    mean = sum(clean) / count if count else None
    std = math.sqrt(sum((value - mean) ** 2 for value in clean) / (count - 1)) if count > 1 and mean is not None else 0.0
    t95 = 2.776 if count == 5 else 1.96
    margin = t95 * std / math.sqrt(count) if count and mean is not None else 0.0
    return {
        "count": count,
        "mean": round_float(mean, 6) if mean is not None else None,
        "stddev": round_float(std, 6),
        "ci95_low": round_float(mean - margin, 6) if mean is not None else None,
        "ci95_high": round_float(mean + margin, 6) if mean is not None else None,
        "values": [round_float(value, 6) if value is not None else None for value in values],
    }


def seed_rank_stability(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    dp_wins = [item for item in seed_results if item["cost_per_baili_score_delta"] is not None and item["cost_per_baili_score_delta"] < 0]
    return {
        "dp_wins": len(dp_wins),
        "baseline_wins": len(seed_results) - len(dp_wins),
        "seed_count": len(seed_results),
        "dp_win_rate": round_rate(len(dp_wins) / len(seed_results)) if seed_results else 0.0,
        "best_policy_by_seed": {str(item["seed"]): item["best_policy"] for item in seed_results},
        "stable": len(dp_wins) == len(seed_results),
    }


def aggregate_deltas(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "category_contribution_delta": aggregate_dicts([item["category_contribution_delta"] for item in seed_results]),
        "set_contribution_delta": aggregate_dicts([item["set_contribution_delta"] for item in seed_results]),
        "dp_changed_samples": sum(item["dp_changed_sample_stats"]["dp_changed_samples"] for item in seed_results),
        "dp_changed_improved_baili_samples": sum(item["dp_changed_sample_stats"]["improved_baili_samples"] for item in seed_results),
        "dp_changed_lowered_baili_samples": sum(item["dp_changed_sample_stats"]["lowered_baili_samples"] for item in seed_results),
        "dp_changed_same_baili_samples": sum(item["dp_changed_sample_stats"]["same_baili_samples"] for item in seed_results),
        "dp_changed_by_checkpoint": aggregate_dicts([item["dp_changed_sample_stats"]["changed_by_checkpoint"] for item in seed_results]),
    }


def recommendation_for(seed_results: list[dict[str, Any]], baseline_costs: list[float | None], dp_costs: list[float | None]) -> dict[str, Any]:
    baseline_stats = sample_stats(baseline_costs)
    dp_stats = sample_stats(dp_costs)
    all_dp_better = all(item["cost_per_baili_score_delta"] is not None and item["cost_per_baili_score_delta"] < 0 for item in seed_results)
    ci_no_overlap = (
        dp_stats["ci95_high"] is not None
        and baseline_stats["ci95_low"] is not None
        and dp_stats["ci95_high"] < baseline_stats["ci95_low"]
    )
    mean_better = dp_stats["mean"] is not None and baseline_stats["mean"] is not None and dp_stats["mean"] < baseline_stats["mean"]
    if mean_better and ci_no_overlap and all_dp_better:
        action = "switch_default"
    elif mean_better and all_dp_better:
        action = "keep_optional_until_more_validation"
    else:
        action = "keep_baseline"
    return {
        "action": action,
        "mean_better": mean_better,
        "all_seeds_better": all_dp_better,
        "ci95_non_overlapping": ci_no_overlap,
    }


def overall_decision(sections: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "normal_85_epic_default": sections[0]["recommendation"]["action"],
        "normal_85_heroic_default": sections[1]["recommendation"]["action"],
        "rift_85_epic_default": "keep_round2_policy",
        "needs_larger_sample": any(section["recommendation"]["action"] == "keep_optional_until_more_validation" for section in sections),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DP assisted 1M x 5 deep validation",
        "",
        "## 结论",
        "",
        f"- normal_85 Epic：{report['overall']['normal_85_epic_default']}",
        f"- normal_85 Heroic：{report['overall']['normal_85_heroic_default']}",
        "- rift_85 Epic：keep_round2_policy，本轮未重跑",
        f"- 是否需要更大样本：{'是' if report['overall']['needs_larger_sample'] else '否'}",
        "",
    ]
    for section in report["sections"]:
        lines.extend(render_section(section))
    return "\n".join(lines)


def render_section(section: dict[str, Any]) -> list[str]:
    stats = section["statistics"]
    rec = section["recommendation"]
    lines = [
        f"## {section['label']}",
        "",
        f"- baseline：{section['baseline_policy']}",
        f"- dp_assisted：{section['dp_policy']}",
        f"- 建议：{rec['action']}",
        f"- seed rank stability：DP wins {section['seed_rank_stability']['dp_wins']}/{section['seed_rank_stability']['seed_count']}, stable={section['seed_rank_stability']['stable']}",
        f"- cost mean：baseline {stats['baseline_cost_per_baili_score']['mean']} vs DP {stats['dp_cost_per_baili_score']['mean']}",
        f"- cost 95% CI：baseline [{stats['baseline_cost_per_baili_score']['ci95_low']}, {stats['baseline_cost_per_baili_score']['ci95_high']}] vs DP [{stats['dp_cost_per_baili_score']['ci95_low']}, {stats['dp_cost_per_baili_score']['ci95_high']}]",
        f"- baili / 1000 stamina mean：baseline {stats['baseline_baili_score_per_1000_stamina']['mean']} vs DP {stats['dp_baili_score_per_1000_stamina']['mean']}",
        "",
        "| seed | baseline cost | DP cost | delta | baseline score/1000 | DP score/1000 | DP calls | DP changes | +9/+12 changes | native/rescued DP | conversion DP |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|",
    ]
    for item in section["seed_results"]:
        checkpoint_text = "/".join(f"+{key}:{value}" for key, value in item["dp_changed_sample_stats"]["changed_by_checkpoint"].items())
        lines.append(
            f"| {item['seed']} | {item['baseline_cost_per_baili_score']} | {item['dp_cost_per_baili_score']} | "
            f"{item['cost_per_baili_score_delta']} | {item['baseline_baili_score_per_1000_stamina']} | "
            f"{item['dp_baili_score_per_1000_stamina']} | {item['dp_call_count']} | {item['dp_changed_decision_count']} | "
            f"{checkpoint_text} | {item['dp_native_success_rate']}/{item['dp_rescued_success_rate']} | {item['dp_conversion_needed_rate']} |"
        )
    aggregate = section["aggregate_deltas"]
    lines.extend(
        [
            "",
            f"- DP 改判样本：{aggregate['dp_changed_samples']}",
            f"- 改判后百里分提升/降低/持平：{aggregate['dp_changed_improved_baili_samples']} / {aggregate['dp_changed_lowered_baili_samples']} / {aggregate['dp_changed_same_baili_samples']}",
            f"- +9 / +12 改判次数：{aggregate['dp_changed_by_checkpoint']}",
            f"- 分类贡献变化 top：{top_delta_text(aggregate['category_contribution_delta'])}",
            f"- 套装贡献变化 top：{top_delta_text(aggregate['set_contribution_delta'])}",
            "",
        ]
    )
    return lines


def best_policy_name(baseline: dict[str, Any], dp_policy: dict[str, Any]) -> str:
    baseline_cost = baseline.get("cost_per_baili_score")
    dp_cost = dp_policy.get("cost_per_baili_score")
    if dp_cost is not None and (baseline_cost is None or dp_cost < baseline_cost):
        return dp_policy["policy_name"]
    return baseline["policy_name"]


def none_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return round_float(float(left) - float(right), 6)


def dict_delta(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    keys = sorted(set(left) | set(right))
    return {key: round_float(float(left.get(key, 0.0)) - float(right.get(key, 0.0)), 6) for key in keys}


def aggregate_dicts(items: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in items:
        for key, value in item.items():
            result[key] = result.get(key, 0.0) + float(value)
    return {key: round_float(value, 6) for key, value in sorted(result.items())}


def top_delta_text(items: dict[str, float], limit: int = 5) -> str:
    ranked = sorted(items.items(), key=lambda item: abs(item[1]), reverse=True)[:limit]
    return ", ".join(f"{key}={value}" for key, value in ranked) if ranked else "-"


def parse_seeds(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run normal-only 1M x 5 dp_assisted deep validation.")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--runs", type=int, default=1_000_000)
    parser.add_argument("--seeds", default="17,29,43,71,101")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--dp-utility-margin", type=float, default=0.1)
    args = parser.parse_args(argv)
    run_deep_validation(
        reports_dir=args.reports_dir,
        runs=args.runs,
        seeds=parse_seeds(args.seeds),
        workers=args.workers,
        dp_utility_margin=args.dp_utility_margin,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
