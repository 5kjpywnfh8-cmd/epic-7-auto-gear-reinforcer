from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REPORT_DIR = Path("reports")
DEFAULT_SEEDS = [17, 29, 43]
DEEP_SEEDS = [17, 29, 43, 71, 101]
DEFAULT_RUNS = [
    ("normal_epic_100k", "normal-epic", "100k", DEFAULT_SEEDS),
    ("normal_epic_1m", "normal-epic", "1m", DEEP_SEEDS),
    ("normal_heroic_1m", "normal-heroic", "1m", DEEP_SEEDS),
    ("rift_epic_1m", "rift-epic", "1m", DEEP_SEEDS),
]
REQUIRED_POLICY_NAMES = [
    "global_baili_marginal_mid",
    "baili_marginal_low",
    "baili_marginal_mid",
    "baili_marginal_high",
    "target_marginal_mid",
    "score_target_low_speed_low",
    "score_strategy_late_strict_speed_high",
    "set_group_baili_marginal_mid",
    "category_baili_marginal_mid",
    "category_set_group_baili_marginal_mid",
    "speed_set_specialized",
]
CONVERSION_COSTS = ["0", "200", "500", "1000"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize round2 baili-formal calibration reports")
    parser.add_argument("--output-json", default=str(REPORT_DIR / "baili-formal-round2-summary.json"))
    parser.add_argument("--output-md", default=str(REPORT_DIR / "baili-formal-round2-summary.md"))
    args = parser.parse_args(argv)
    summary = build_summary()
    Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.output_md).write_text(render_markdown(summary), encoding="utf-8")
    print(args.output_md)
    print(args.output_json)
    return 0


def build_summary() -> dict[str, Any]:
    runs = {}
    for key, source_label, sample_tag, seeds in DEFAULT_RUNS:
        seed_reports = load_seed_reports(source_label, sample_tag, seeds)
        if seed_reports:
            runs[key] = summarize_run_group(key, source_label, sample_tag, seed_reports)
    return {
        "scope": scope_from_runs(runs),
        "runs": runs,
        "overall_assessment": assess_runs(runs),
        "visuals": round2_visuals(),
        "real_drop_model_risk": real_drop_model_risk(),
        "required_real_drop_data": required_real_drop_data(),
    }


def load_seed_reports(source_label: str, sample_tag: str, seeds: list[int]) -> dict[int, dict[str, Any]]:
    reports: dict[int, dict[str, Any]] = {}
    for seed in seeds:
        path = REPORT_DIR / f"baili-formal-round2-{source_label}-{sample_tag}-seed{seed}.json"
        if path.exists():
            reports[seed] = json.loads(path.read_text(encoding="utf-8-sig"))
    return reports


def summarize_run_group(key: str, source_label: str, sample_tag: str, seed_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    by_seed = [summarize_seed(seed, report) for seed, report in sorted(seed_reports.items())]
    policies = aggregate_policies(seed_reports)
    return {
        "key": key,
        "source_label": source_label,
        "sample_tag": sample_tag,
        "files": [f"reports/baili-formal-round2-{source_label}-{sample_tag}-seed{seed}.json" for seed in sorted(seed_reports)],
        "by_seed": by_seed,
        "policy_aggregate": policies,
        "top5_by_mean_cost": sorted(policies.values(), key=policy_aggregate_sort_key)[:5],
        "required_policy_comparison": [policies[name] for name in REQUIRED_POLICY_NAMES if name in policies],
        "rank_stability": rank_stability(seed_reports),
        "conversion_cost_sensitivity": conversion_cost_sensitivity(seed_reports),
        "field_coverage": field_coverage(next(iter(seed_reports.values()))["policies"][0]),
    }


def summarize_seed(seed: int, report: dict[str, Any]) -> dict[str, Any]:
    policy = report["policies"][0]
    return {
        "seed": seed,
        "best_policy": report.get("best_policy"),
        "ranking_metric": report.get("ranking_metric"),
        "main_score_scope": (report.get("success_definition") or {}).get("main_score_scope"),
        **policy_summary(policy),
        "future_score": (policy.get("target_score_by_category") or {}).get("未来可期", 0),
    }


def policy_summary(policy: dict[str, Any]) -> dict[str, Any]:
    stop = policy.get("stop_rate_by_checkpoint") or {}
    return {
        "policy_name": policy.get("policy_name"),
        "cost_per_baili_score": policy.get("cost_per_baili_score"),
        "baili_score_per_1000_stamina": policy.get("baili_score_per_1000_stamina"),
        "target_score_per_1000_stamina": policy.get("target_score_per_1000_stamina"),
        "cost_per_target_score": policy.get("cost_per_target_score"),
        "success_rate": policy.get("success_rate"),
        "native_success_rate": policy.get("native_success_rate"),
        "rescued_success_rate": policy.get("rescued_success_rate"),
        "conversion_needed_rate": policy.get("conversion_needed_rate"),
        "stop_plus12": stop.get("12"),
        "finish_plus15": stop.get("15"),
        "conversion_needed_count": policy.get("conversion_needed_count"),
    }


def aggregate_policies(seed_reports: dict[int, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows_by_name: dict[str, list[tuple[int, int, dict[str, Any]]]] = {}
    for seed, report in seed_reports.items():
        for rank, policy in enumerate(report.get("policies", []), 1):
            rows_by_name.setdefault(policy.get("policy_name"), []).append((seed, rank, policy))
    aggregates = {}
    for name, rows in rows_by_name.items():
        policies = [row[2] for row in rows]
        ranks = [row[1] for row in rows]
        aggregates[name] = {
            "policy_name": name,
            "seed_count": len(rows),
            "rank_by_seed": {str(seed): rank for seed, rank, _ in rows},
            "avg_rank": round_float(mean(ranks), 3),
            "cost_per_baili_score": metric_stats(policies, "cost_per_baili_score"),
            "baili_score_per_1000_stamina": metric_stats(policies, "baili_score_per_1000_stamina"),
            "success_rate": metric_stats(policies, "success_rate"),
            "native_success_rate": metric_stats(policies, "native_success_rate"),
            "rescued_success_rate": metric_stats(policies, "rescued_success_rate"),
            "conversion_needed_rate": metric_stats(policies, "conversion_needed_rate"),
            "stop_plus12": metric_stats([{"stop_plus12": (policy.get("stop_rate_by_checkpoint") or {}).get("12")} for policy in policies], "stop_plus12"),
            "finish_plus15": metric_stats([{"finish_plus15": (policy.get("stop_rate_by_checkpoint") or {}).get("15")} for policy in policies], "finish_plus15"),
            "baili_score_by_set": sum_numeric_dicts(policy.get("baili_score_by_set") or {} for policy in policies),
            "success_count_by_set": sum_numeric_dicts(policy.get("success_count_by_set") or {} for policy in policies),
            "conversion_target_stat_distribution": sum_numeric_dicts(policy.get("conversion_target_stat_distribution") or {} for policy in policies),
            "target_score_by_category": sum_numeric_dicts(policy.get("target_score_by_category") or {} for policy in policies),
        }
    return aggregates


def metric_stats(rows: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return {"mean": None, "stddev": None, "ci95": None}
    stddev = pstdev(values) if len(values) > 1 else 0.0
    ci95 = 1.96 * stddev / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return {"mean": round_float(mean(values), 4), "stddev": round_float(stddev, 4), "ci95": round_float(ci95, 4)}


def rank_stability(seed_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    best_by_seed = {str(seed): report.get("best_policy") for seed, report in sorted(seed_reports.items())}
    consensus = len(set(best_by_seed.values())) == 1 if best_by_seed else False
    return {
        "best_policy_by_seed": best_by_seed,
        "best_policy_consensus": next(iter(best_by_seed.values())) if consensus else None,
        "consensus": consensus,
    }


def conversion_cost_sensitivity(seed_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for cost in CONVERSION_COSTS:
        best_by_seed = {}
        for seed, report in sorted(seed_reports.items()):
            best_policy = None
            best_cost = None
            for policy in report.get("policies", []):
                efficiency = (policy.get("rescued_baili_efficiency_with_configured_conversion_cost") or {}).get(cost) or {}
                cost_value = efficiency.get("cost_per_baili_score")
                if cost_value is not None and (best_cost is None or cost_value < best_cost):
                    best_cost = cost_value
                    best_policy = policy.get("policy_name")
            best_by_seed[str(seed)] = {"policy_name": best_policy, "cost_per_baili_score": best_cost}
        result[cost] = {
            "best_by_seed": best_by_seed,
            "consensus": len({item["policy_name"] for item in best_by_seed.values()}) == 1 if best_by_seed else False,
        }
    return result


def field_coverage(policy: dict[str, Any]) -> dict[str, bool]:
    fields = [
        "cost_per_baili_score",
        "baili_score_per_1000_stamina",
        "target_score_per_1000_stamina",
        "cost_per_target_score",
        "native_success_rate",
        "rescued_success_rate",
        "conversion_needed_rate",
        "success_count_by_category",
        "baili_tier_rate",
        "stop_rate_by_checkpoint",
        "total_stamina_avg",
        "upgrade_stamina_avg",
        "gear_acquisition_stamina_avg",
        "sell_recovery_avg",
        "baili_score_by_set",
        "cost_per_baili_score_by_set",
        "success_count_by_set",
        "stop_rate_by_set",
        "category_by_set_matrix",
        "native_baili_efficiency",
        "rescued_baili_efficiency_without_conversion_cost",
        "rescued_baili_efficiency_with_configured_conversion_cost",
        "conversion_cost",
        "conversion_needed_count",
        "conversion_target_stat_distribution",
    ]
    return {field: field in policy for field in fields}


def scope_from_runs(runs: dict[str, Any]) -> dict[str, Any]:
    for run in runs.values():
        if run["by_seed"]:
            first = run["by_seed"][0]
            return {
                "ranking_metric": first["ranking_metric"],
                "main_score_scope": first["main_score_scope"],
            }
    return {}


def assess_runs(runs: dict[str, Any]) -> dict[str, Any]:
    normal = runs.get("normal_epic_100k")
    deep = runs.get("normal_epic_1m")
    if not normal and not deep:
        return {"normal_epic_100k_direction": "missing"}
    decisive = deep or normal
    top = decisive["top5_by_mean_cost"][0]
    baseline = decisive["policy_aggregate"].get("baili_marginal_mid")
    target_old = decisive["policy_aggregate"].get("target_marginal_mid")
    heroic = runs.get("normal_heroic_1m")
    rift = runs.get("rift_epic_1m")
    heroic_top = heroic["top5_by_mean_cost"][0] if heroic else None
    heroic_estimated_successes = None
    if heroic_top:
        heroic_estimated_successes = (heroic_top["success_rate"]["mean"] or 0) * sample_count(heroic["sample_tag"])
    return {
        "normal_epic_100k_best": normal["top5_by_mean_cost"][0]["policy_name"] if normal else None,
        "normal_epic_1m_best": deep["top5_by_mean_cost"][0]["policy_name"] if deep else None,
        "normal_epic_1m_consensus": deep["rank_stability"]["best_policy_consensus"] if deep else None,
        "normal_heroic_1m_best": heroic_top["policy_name"] if heroic_top else None,
        "normal_heroic_1m_consensus": heroic["rank_stability"]["best_policy_consensus"] if heroic else None,
        "normal_heroic_estimated_successes_per_seed": round_float(heroic_estimated_successes, 1) if heroic_estimated_successes is not None else None,
        "normal_heroic_recommend_3m": bool(heroic_estimated_successes is not None and heroic_estimated_successes < 50),
        "rift_epic_1m_best": rift["top5_by_mean_cost"][0]["policy_name"] if rift else None,
        "rift_epic_1m_consensus": rift["rank_stability"]["best_policy_consensus"] if rift else None,
        "normal_epic_decisive_sample": decisive["key"],
        "normal_epic_100k_direction": "set_group_improved" if (normal and normal["top5_by_mean_cost"][0]["policy_name"] != "baili_marginal_mid") else "global_baseline_still_best",
        "normal_epic_1m_direction": "set_group_improved" if (deep and top["policy_name"] != "baili_marginal_mid") else "global_baseline_still_best" if deep else None,
        "baseline_baili_marginal_mid_cost_mean": (baseline or {}).get("cost_per_baili_score", {}).get("mean"),
        "target_marginal_mid_cost_mean": (target_old or {}).get("cost_per_baili_score", {}).get("mean"),
        "recommend_continue_to_1m": top["cost_per_baili_score"]["mean"] is not None,
        "recommend_continue_to_heroic": bool(deep and deep["rank_stability"]["consensus"]),
    }


def real_drop_model_risk() -> str:
    return "当前模拟器按代码内置随机胚子分布生成装备，尚未用真实游戏掉落分布校正；报告结论只能视为策略相对效率验证，不是最终实测掉落效率。"


def required_real_drop_data() -> list[str]:
    return [
        "set 分布",
        "slot 分布",
        "rank 分布",
        "mainStat 分布",
        "substat 组合分布",
        "红装 / 紫装出现率",
        "各副属性初始值分布",
        "装备出售回收的实测数据",
        "强化资源与金币来源实测数据",
    ]


def round2_visuals() -> dict[str, str]:
    return {
        "single_policy_png": "reports/visual/baili-formal-round2-normal-epic-1m-seed17-category_baili_marginal_mid.png",
        "single_policy_html": "reports/visual/baili-formal-round2-normal-epic-1m-seed17-category_baili_marginal_mid.html",
        "aggregate_best_single_png": "reports/visual/baili-formal-round2-best-single-policy.png",
        "aggregate_best_single_html": "reports/visual/baili-formal-round2-best-single-policy.html",
        "top5_compare_png": "reports/visual/baili-formal-round2-normal-epic-1m-seed17-top5-compare.png",
        "top5_compare_html": "reports/visual/baili-formal-round2-normal-epic-1m-seed17-top5-compare.html",
        "set_contribution_png": "reports/visual/baili-formal-round2-set-contribution.png",
        "set_contribution_html": "reports/visual/baili-formal-round2-set-contribution.html",
        "equipment_type_compare_png": "reports/visual/baili-formal-round2-equipment-type-compare.png",
        "equipment_type_compare_html": "reports/visual/baili-formal-round2-equipment-type-compare.html",
        "round2_index_html": "reports/visual/round2-index.html",
    }


def sample_count(sample_tag: str) -> int:
    if sample_tag.endswith("m"):
        return int(float(sample_tag[:-1]) * 1_000_000)
    if sample_tag.endswith("k"):
        return int(float(sample_tag[:-1]) * 1_000)
    return 0


def policy_aggregate_sort_key(policy: dict[str, Any]) -> tuple[float, float]:
    cost = policy["cost_per_baili_score"]["mean"]
    rank = policy["avg_rank"]
    return (float("inf") if cost is None else float(cost), float(rank))


def sum_numeric_dicts(dicts: Any) -> dict[str, float]:
    result: dict[str, float] = {}
    for items in dicts:
        for key, value in items.items():
            result[key] = result.get(key, 0.0) + float(value or 0)
    return {key: round_float(value, 1) for key, value in sorted(result.items())}


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 第二轮 R2-R58 正式百里策略验证报告",
        "",
        "## 结论",
        "",
        f"- ranking_metric：`{summary.get('scope', {}).get('ranking_metric')}`",
        f"- main_score_scope：`{summary.get('scope', {}).get('main_score_scope')}`",
        f"- 普通 85 红装 100k×3 最优：`{summary['overall_assessment'].get('normal_epic_100k_best')}`。",
        f"- 普通 85 红装 1M×5 最优：`{summary['overall_assessment'].get('normal_epic_1m_best')}`。",
        f"- 1M×5 第一名一致性：`{summary['overall_assessment'].get('normal_epic_1m_consensus')}`。",
        f"- 普通 85 紫装 1M×5 最优：`{summary['overall_assessment'].get('normal_heroic_1m_best')}`；估计每 seed 成功件约 `{summary['overall_assessment'].get('normal_heroic_estimated_successes_per_seed')}`，是否建议 3M×5：`{summary['overall_assessment'].get('normal_heroic_recommend_3m')}`。",
        f"- 异界 85 红装 1M×5 最优：`{summary['overall_assessment'].get('rift_epic_1m_best')}`。",
        f"- 方向判断：`{summary['overall_assessment'].get('normal_epic_100k_direction')}`。",
        f"- 是否建议进入紫装验证：`{summary['overall_assessment'].get('recommend_continue_to_heroic')}`。",
        "",
    ]
    for run in summary["runs"].values():
        lines.extend(render_run_group(run))
    lines.extend(
        [
            "## 可视化交付",
            "",
        ]
    )
    for label, path in summary["visuals"].items():
        lines.append(f"- {label}: `{path}`")
    lines.extend(
        [
            "",
            "## 转换石成本敏感性",
            "",
        ]
    )
    for run in summary["runs"].values():
        lines.append(f"### {run['key']}")
        for cost, item in run["conversion_cost_sensitivity"].items():
            winners = ", ".join(f"seed{seed}: `{row['policy_name']}` ({fmt(row['cost_per_baili_score'])})" for seed, row in item["best_by_seed"].items())
            lines.append(f"- conversion_cost={cost}: {winners}")
        lines.append("")
    lines.extend(
        [
            "## 真实掉落模型风险",
            "",
            f"- {summary['real_drop_model_risk']}",
            "- 后续校正需要数据：",
        ]
    )
    lines.extend(f"  - {item}" for item in summary["required_real_drop_data"])
    return "\n".join(lines) + "\n"


def render_run_group(run: dict[str, Any]) -> list[str]:
    lines = [
        f"## {run['key']}",
        "",
        "### seed 结果",
        "",
        "| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | R61主收益 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in run["by_seed"]:
        lines.append(
            f"| {row['seed']} | `{row['best_policy']}` | {fmt(row['baili_score_per_1000_stamina'])} | {fmt(row['cost_per_baili_score'])} | "
            f"{pct(row['success_rate'])} | {pct(row['native_success_rate'])} | {pct(row['rescued_success_rate'])} | {pct(row['conversion_needed_rate'])} | {fmt(row['future_score'])} |"
        )
    lines.extend(
        [
            "",
            "### Top5 均值排序",
            "",
            "| rank | policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 平均seed排名 |",
            "|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    for index, policy in enumerate(run["top5_by_mean_cost"], 1):
        cost = policy["cost_per_baili_score"]
        baili = policy["baili_score_per_1000_stamina"]
        lines.append(
            f"| {index} | `{policy['policy_name']}` | {fmt(cost['mean'])} | {fmt(cost['stddev'])} | {fmt(cost['ci95'])} | {fmt(baili['mean'])} | {fmt(policy['avg_rank'])} |"
        )
    lines.extend(
        [
            "",
            "### 指定策略对照",
            "",
            "| policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 成功率 mean | +12停 | +15完成 | seed排名 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for policy in run["required_policy_comparison"]:
        cost = policy["cost_per_baili_score"]
        lines.append(
            f"| `{policy['policy_name']}` | {fmt(cost['mean'])} | {fmt(cost['stddev'])} | {fmt(cost['ci95'])} | "
            f"{fmt(policy['baili_score_per_1000_stamina']['mean'])} | {pct(policy['success_rate']['mean'])} | "
            f"{pct(policy['stop_plus12']['mean'])} | {pct(policy['finish_plus15']['mean'])} | {policy['rank_by_seed']} |"
        )
    lines.append("")
    return lines


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"


def round_float(value: float, digits: int) -> float:
    return round(float(value) + 1e-12, digits)


if __name__ == "__main__":
    raise SystemExit(main())
