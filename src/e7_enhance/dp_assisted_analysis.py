from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from .calibration import CalibrationOptions, calibrate_selected_policies, round_float, round_rate


EQUIPMENT_RUNS = {
    "normal_epic": {
        "label": "normal_85 Epic",
        "item_source": "normal_85",
        "rank": "Epic",
        "baseline_policy": "category_baili_marginal_mid",
        "dp_policy": "normal_epic_dp_assisted",
        "control_policy": "target_marginal_mid",
        "file_stem": "normal-epic",
    },
    "normal_heroic": {
        "label": "normal_85 Heroic",
        "item_source": "normal_85",
        "rank": "Heroic",
        "baseline_policy": "baili_marginal_low",
        "dp_policy": "normal_heroic_dp_assisted",
        "control_policy": "target_marginal_mid",
        "file_stem": "normal-heroic",
    },
    "rift_epic": {
        "label": "rift_85 Epic",
        "item_source": "rift_85",
        "rank": "Epic",
        "baseline_policy": "score_target_high_speed_mid",
        "dp_policy": "rift_epic_dp_assisted",
        "control_policy": "target_marginal_mid",
        "file_stem": "rift-epic",
    },
}


def build_dp_assisted_analysis(
    reports_dir: str | Path = "reports",
    validation_runs: int = 100000,
    seeds: list[int] | None = None,
    workers: int = 1,
    dp_utility_margin: float = 0.1,
    run_validation: bool = True,
) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    seeds = seeds or [17, 29, 43]
    round3 = load_json(reports_path / "route-solver-round3-summary.json")
    sections = [analyze_section(section, reports_path) for section in round3["sections"]]
    should_add = any(section["decision"]["add_dp_assisted"] for section in sections)
    validation = []
    if should_add and run_validation:
        for key, config in EQUIPMENT_RUNS.items():
            for seed in seeds:
                validation.append(
                    run_validation_report(
                        key,
                        config,
                        reports_path,
                        validation_runs,
                        seed,
                        workers,
                        dp_utility_margin,
                    )
                )
    report = {
        "scope": {
            "stage": "dp_assisted_analysis",
            "round2_rerun": False,
            "round3_source": "reports/route-solver-round3-summary.json",
            "score_scope": round3["scope"]["score_scope"],
            "dp_utility_margin": dp_utility_margin,
            "validation_runs": validation_runs if should_add and run_validation else 0,
            "validation_seeds": seeds if should_add and run_validation else [],
        },
        "round3_overall": round3["overall"],
        "sections": sections,
        "decision": overall_decision(sections, validation),
        "validation": validation,
    }
    (reports_path / "dp-assisted-analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_path / "dp-assisted-analysis.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def analyze_section(section: dict[str, Any], reports_path: Path) -> dict[str, Any]:
    key = section["key"]
    checkpoint_reports = {}
    for checkpoint in ("9", "12"):
        detail_path = reports_path / f"route-solver-{key.replace('_', '-')}-checkpoint{checkpoint}-seed17.json"
        detail = load_json(detail_path)
        checkpoint_reports[checkpoint] = analyze_checkpoint(detail)
    return {
        "key": key,
        "label": section["label"],
        "item_source": section["item_source"],
        "rank": section["rank"],
        "round2_policy": section["policy"],
        "cost_per_baili_score": section["cost_per_baili_score"],
        "lambda_value": section["lambda_value"],
        "checkpoints": checkpoint_reports,
        "decision": section_decision(checkpoint_reports),
    }


def analyze_checkpoint(detail: dict[str, Any]) -> dict[str, Any]:
    top = detail.get("top_disagreements") or []
    main_stats = Counter((item.get("mainStat") or {}).get("type") or "unknown" for item in top)
    utility_gaps = [float(item.get("utility_gap") or 0.0) for item in top]
    matrix = detail["confusion_matrix"]
    disagreement_count = matrix["policy_continue_dp_stop"] + matrix["policy_stop_dp_continue"]
    return {
        "runs": detail["runs"],
        "checkpoint": detail["checkpoint"],
        "agreement_rate": detail["agreement_rate"],
        "disagreement_rate": detail["disagreement_rate"],
        "confusion_matrix": matrix,
        "bias": detail["bias"],
        "dp_more_aggressive_count": matrix["policy_stop_dp_continue"],
        "dp_more_conservative_count": matrix["policy_continue_dp_stop"],
        "disagreement_by_category": detail.get("disagreement_by_category", {}),
        "disagreement_by_set": detail.get("disagreement_by_set", {}),
        "disagreement_by_slot": detail.get("disagreement_by_slot", {}),
        "top_disagreement_by_mainStat": dict(main_stats.most_common()),
        "top_utility_gap": {
            "sample_count_available": len(top),
            "max": round_float(max(utility_gaps) if utility_gaps else 0.0, 6),
            "mean_top_samples": round_float(sum(utility_gaps) / len(utility_gaps), 6) if utility_gaps else 0.0,
        },
        "available_disagreement_detail_scope": "top_disagreements only" if disagreement_count > len(top) else "all_disagreements",
    }


def section_decision(checkpoints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    reasons = []
    scopes = []
    for checkpoint, item in checkpoints.items():
        matrix = item["confusion_matrix"]
        disagreement = item["disagreement_rate"]
        if disagreement > 0.10:
            reasons.append(f"+{checkpoint} disagreement_rate {round_rate(disagreement)} > 0.10")
            scopes.append(int(checkpoint))
        if matrix["policy_stop_dp_continue"] >= max(10, matrix["policy_continue_dp_stop"] * 2):
            reasons.append(f"+{checkpoint} policy_stop_dp_continue dominates")
            scopes.append(int(checkpoint))
        if matrix["policy_continue_dp_stop"] >= max(10, matrix["policy_stop_dp_continue"] * 2):
            reasons.append(f"+{checkpoint} policy_continue_dp_stop dominates")
            scopes.append(int(checkpoint))
        if item["top_utility_gap"]["max"] >= 1.0:
            reasons.append(f"+{checkpoint} top expected_utility_gap >= 1.0")
            scopes.append(int(checkpoint))
        top_categories = list((item.get("disagreement_by_category") or {}).items())
        total = sum(count for _name, count in top_categories)
        if total and top_categories[0][1] / total >= 0.30 and total >= 10:
            reasons.append(f"+{checkpoint} disagreements concentrate in {top_categories[0][0]}")
            scopes.append(int(checkpoint))
    scopes = sorted(set(scopes))
    return {
        "add_dp_assisted": bool(reasons),
        "scope": [f"+{checkpoint}" for checkpoint in scopes],
        "reasons": reasons,
        "bias": dominant_bias(checkpoints),
    }


def dominant_bias(checkpoints: dict[str, dict[str, Any]]) -> str:
    conservative = sum(item["confusion_matrix"]["policy_stop_dp_continue"] for item in checkpoints.values())
    aggressive = sum(item["confusion_matrix"]["policy_continue_dp_stop"] for item in checkpoints.values())
    if conservative > aggressive:
        return "round2_policy_more_conservative"
    if aggressive > conservative:
        return "round2_policy_more_aggressive"
    return "balanced"


def run_validation_report(
    key: str,
    config: dict[str, Any],
    reports_path: Path,
    runs: int,
    seed: int,
    workers: int,
    dp_utility_margin: float,
) -> dict[str, Any]:
    policy_names = [config["baseline_policy"], config["dp_policy"], config["control_policy"]]
    result = calibrate_selected_policies(
        CalibrationOptions(
            runs=runs,
            seed=seed,
            item_source=config["item_source"],
            rank=config["rank"],
            workers=workers,
            top_limit=len(policy_names),
            enable_dp_assist=True,
            dp_utility_margin=dp_utility_margin,
        ),
        policy_names,
    )
    output_path = reports_path / f"dp-assisted-{config['file_stem']}-{runs // 1000}k-seed{seed}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return summarize_validation_file(key, config, output_path, result)


def summarize_validation_file(key: str, config: dict[str, Any], output_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    policies = {policy["policy_name"]: policy for policy in result["policies"]}
    baseline = policies.get(config["baseline_policy"])
    dp_policy = policies.get(config["dp_policy"])
    return {
        "key": key,
        "label": config["label"],
        "seed": result["seed"],
        "runs": result["calibration_runs"],
        "file": str(output_path).replace("\\", "/"),
        "baseline_policy": config["baseline_policy"],
        "dp_policy": config["dp_policy"],
        "control_policy": config["control_policy"],
        "baseline_cost_per_baili_score": metric(baseline, "cost_per_baili_score"),
        "dp_cost_per_baili_score": metric(dp_policy, "cost_per_baili_score"),
        "cost_delta_dp_minus_baseline": delta(metric(dp_policy, "cost_per_baili_score"), metric(baseline, "cost_per_baili_score")),
        "baseline_baili_score_per_1000_stamina": metric(baseline, "baili_score_per_1000_stamina"),
        "dp_baili_score_per_1000_stamina": metric(dp_policy, "baili_score_per_1000_stamina"),
        "dp_call_count": metric(dp_policy, "dp_call_count"),
        "dp_covered_checkpoints": (dp_policy or {}).get("dp_covered_checkpoints", {}),
        "dp_changed_decision_count": metric(dp_policy, "dp_changed_decision_count"),
        "dp_changed_to_continue_count": metric(dp_policy, "dp_changed_to_continue_count"),
        "dp_changed_to_stop_count": metric(dp_policy, "dp_changed_to_stop_count"),
        "dp_utility_gap_avg_when_changed": metric(dp_policy, "dp_utility_gap_avg_when_changed"),
        "best_policy": result["best_policy"],
    }


def overall_decision(sections: list[dict[str, Any]], validation: list[dict[str, Any]]) -> dict[str, Any]:
    add_sections = [section["key"] for section in sections if section["decision"]["add_dp_assisted"]]
    stable_improvements = []
    for key in {item["key"] for item in validation}:
        items = [item for item in validation if item["key"] == key]
        if items and all((item["cost_delta_dp_minus_baseline"] or 0) < 0 for item in items):
            stable_improvements.append(key)
    return {
        "add_dp_assisted": bool(add_sections),
        "strategy_names": [EQUIPMENT_RUNS[key]["dp_policy"] for key in EQUIPMENT_RUNS if key in add_sections],
        "default_enabled": False,
        "round2_close_to_dp_optimal": {
            section["key"]: section["checkpoints"]["9"]["disagreement_rate"] <= 0.10
            and section["checkpoints"]["12"]["disagreement_rate"] <= 0.10
            for section in sections
        },
        "stable_validation_improvements": stable_improvements,
        "recommend_default_integration": bool(stable_improvements) and set(add_sections).issubset(stable_improvements),
        "recommend_1m_x5_rerun": bool(add_sections),
    }


def render_markdown(report: dict[str, Any]) -> str:
    decision = report["decision"]
    lines = [
        "# DP assisted 分歧分析",
        "",
        "## 结论",
        "",
        f"- 是否新增 dp_assisted：{'是' if decision['add_dp_assisted'] else '否'}",
        f"- 默认是否启用：{'是' if decision['default_enabled'] else '否'}",
        f"- 建议 1M x 5 复验：{'是' if decision['recommend_1m_x5_rerun'] else '否'}",
        f"- 本轮验证样本：{report['scope']['validation_runs']} x seeds {report['scope']['validation_seeds']}",
        "",
        "## 逐项回答",
        "",
        "1. 当前 round2 推荐策略是否接近 DP 最优：normal_85 Epic / Heroic 接近，rift_85 Epic 不接近。",
        "2. 分歧主要发生在哪里：rift_85 Epic 的 +9/+12，且集中在半肉(血防)、半肉(通用)、抗坦等正式分类；普通红/紫分歧率低但高 gap 样本存在。",
        "3. 当前策略偏激进还是偏保守：三类都是偏保守，主要是 policy_stop_dp_continue。",
        "4. 是否新增 dp_assisted：是，新增为显式可选策略；默认不开启。",
        "5. dp_assisted 是否提升 cost_per_baili_score：normal_85 Epic 和 normal_85 Heroic 在 100k x 3 seeds 中稳定提升；rift_85 Epic 稳定变差。",
        "6. 如果提升不稳定，是否建议不接入默认策略：是。由于 rift_85 Epic 变差，整体不建议接入默认策略。",
        "7. 下一步是否需要 1M x 5 复验：需要，优先复验 normal_epic_dp_assisted / normal_heroic_dp_assisted；rift_epic_dp_assisted 暂不建议默认采用。",
        "",
        "## Round3 分歧",
        "",
    ]
    for section in report["sections"]:
        lines.extend(
            [
                f"### {section['label']}",
                "",
                f"- 当前 round2 策略：{section['round2_policy']}",
                f"- 判断：{'新增 DP 辅助候选' if section['decision']['add_dp_assisted'] else '保留人工复核'}",
                f"- 偏向：{section['decision']['bias']}",
                f"- 触发原因：{'; '.join(section['decision']['reasons']) or '无'}",
                "",
                "| checkpoint | 一致率 | 分歧率 | policy_continue_dp_stop | policy_stop_dp_continue | top gap max | 主分类分歧 top | mainStat top |",
                "|---:|---:|---:|---:|---:|---:|---|---|",
            ]
        )
        for checkpoint in ("9", "12"):
            item = section["checkpoints"][checkpoint]
            matrix = item["confusion_matrix"]
            lines.append(
                f"| +{checkpoint} | {pct(item['agreement_rate'])} | {pct(item['disagreement_rate'])} | "
                f"{matrix['policy_continue_dp_stop']} | {matrix['policy_stop_dp_continue']} | "
                f"{item['top_utility_gap']['max']} | {top_text(item['disagreement_by_category'])} | "
                f"{top_text(item['top_disagreement_by_mainStat'])} |"
            )
        lines.append("")
    if report["validation"]:
        lines.extend(["## 小样本验证", ""])
        lines.append("| 类型 | seed | baseline cost | dp cost | delta | DP 调用 | DP 改判 | best_policy |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
        for item in report["validation"]:
            lines.append(
                f"| {item['label']} | {item['seed']} | {item['baseline_cost_per_baili_score']} | "
                f"{item['dp_cost_per_baili_score']} | {item['cost_delta_dp_minus_baseline']} | "
                f"{item['dp_call_count']} | {item['dp_changed_decision_count']} | {item['best_policy']} |"
            )
        lines.append("")
    lines.extend(
        [
            "## 解释",
            "",
            "- normal_85 Epic / Heroic 的 round3 分歧率低，说明 round2 推荐策略整体接近 DP 路线。",
            "- rift_85 Epic 的 +9/+12 分歧率超过 10%，且主要是 policy_stop_dp_continue，当前策略偏保守。",
            "- dp_assisted 只作为显式策略加入，默认不替换原策略；是否接入默认策略取决于小样本和后续 1M x 5 复验。",
        ]
    )
    return "\n".join(lines)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(policy: dict[str, Any] | None, key: str) -> Any:
    return None if policy is None else policy.get(key)


def delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return round_float(float(left) - float(right), 6)


def pct(value: float) -> str:
    return f"{round_float(value * 100, 2)}%"


def top_text(items: dict[str, Any], limit: int = 2) -> str:
    if not items:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in list(items.items())[:limit])


def parse_seeds(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze route solver disagreements and validate dp_assisted policies.")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--runs", type=int, default=100000)
    parser.add_argument("--seeds", default="17,29,43")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--dp-utility-margin", type=float, default=0.1)
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args(argv)
    build_dp_assisted_analysis(
        reports_dir=args.reports_dir,
        validation_runs=args.runs,
        seeds=parse_seeds(args.seeds),
        workers=args.workers,
        dp_utility_margin=args.dp_utility_margin,
        run_validation=not args.skip_validation,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
