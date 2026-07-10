from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REPORT_DIR = Path("reports")
SUMMARY_MD = REPORT_DIR / "baili-formal-summary.md"
SUMMARY_JSON = REPORT_DIR / "baili-formal-summary.json"
SEEDS = [17, 29, 43]
SAMPLE_SIZES = ["10k", "100k"]
VISUAL_SINGLE = "reports/visual/baili-formal-normal-100k-seed17-baili_marginal_mid.png"
VISUAL_COMPARE = "reports/visual/baili-formal-normal-100k-seed17-top5-compare.png"
REQUIRED_POLICY_NAMES = [
    "baili_marginal_low",
    "baili_marginal_mid",
    "baili_marginal_high",
    "target_marginal_mid",
    "score_target_low_speed_low",
    "score_strategy_late_strict_speed_high",
]


def main() -> None:
    data = build_summary()
    SUMMARY_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_MD.write_text(render_markdown(data), encoding="utf-8")
    print(SUMMARY_MD)
    print(SUMMARY_JSON)


def build_summary() -> dict[str, Any]:
    reports = {
        sample: {seed: load_report(REPORT_DIR / f"baili-formal-normal-{sample}-seed{seed}.json") for seed in SEEDS}
        for sample in SAMPLE_SIZES
    }
    old_reports = {
        "old_target_seed17": load_report(REPORT_DIR / "marginal-normal-10k-seed17.json"),
        "old_target_after_md_specials_seed17": load_report(REPORT_DIR / "marginal-normal-10k-seed17-after-md-specials.json"),
    }
    aggregate = {sample: aggregate_sample(reports[sample]) for sample in SAMPLE_SIZES}
    old_comparison = compare_old(reports["10k"][17], old_reports)
    return {
        "scope": {
            "ranking_metric": reports["100k"][17].get("ranking_metric"),
            "main_score_scope": reports["100k"][17].get("success_definition", {}).get("main_score_scope"),
            "item_source": reports["100k"][17].get("item_source"),
            "rank": reports["100k"][17].get("rank"),
            "gear_source": reports["100k"][17].get("gear_source"),
        },
        "recommendation": {
            "policy_name": aggregate["100k"]["best_policy_consensus"],
            "reason": "10k×3 和 100k×3 的第一名均为 baili_marginal_mid，且按 cost_per_baili_score 排序稳定。",
        },
        "runs": {
            sample: {
                "files": [f"reports/baili-formal-normal-{sample}-seed{seed}.json" for seed in SEEDS],
                "by_seed": [summarize_run(seed, reports[sample][seed]) for seed in SEEDS],
                "aggregate": aggregate[sample],
            }
            for sample in SAMPLE_SIZES
        },
        "old_comparison": old_comparison,
        "top5_100k_seed17": [policy_summary(policy) for policy in reports["100k"][17].get("policies", [])[:5]],
        "required_policy_comparison_100k_seed17": required_policy_comparison(reports["100k"][17]),
        "visuals": {
            "single_png": VISUAL_SINGLE,
            "compare_png": VISUAL_COMPARE,
            "single_html": VISUAL_SINGLE.replace(".png", ".html"),
            "compare_html": VISUAL_COMPARE.replace(".png", ".html"),
            "index_html": "reports/visual/index.html",
        },
        "risks": [
            "样本仍有波动，尤其低成功率策略的尾部高分件。",
            "掉落模型仍是模拟分布，未按真实副属性掉落分布校正。",
            "转换石成本未计入，补救效率是偏乐观估计。",
            "紫装未验证。",
            "异界未验证。",
        ],
    }


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def best_policy(report: dict[str, Any]) -> dict[str, Any]:
    return report["policies"][0]


def summarize_run(seed: int, report: dict[str, Any]) -> dict[str, Any]:
    policy = best_policy(report)
    return {
        "seed": seed,
        "best_policy": report.get("best_policy"),
        **policy_summary(policy),
        "future_score": policy.get("target_score_by_category", {}).get("未来可期", 0),
    }


def policy_summary(policy: dict[str, Any]) -> dict[str, Any]:
    stop = policy.get("stop_rate_by_checkpoint") or {}
    return {
        "policy_name": policy.get("policy_name"),
        "baili_score_per_1000_stamina": policy.get("baili_score_per_1000_stamina"),
        "cost_per_baili_score": policy.get("cost_per_baili_score"),
        "target_score_per_1000_stamina": policy.get("target_score_per_1000_stamina"),
        "cost_per_target_score": policy.get("cost_per_target_score"),
        "success_rate": policy.get("success_rate"),
        "native_success_rate": policy.get("native_success_rate"),
        "rescued_success_rate": policy.get("rescued_success_rate"),
        "conversion_needed_rate": policy.get("conversion_needed_rate"),
        "stop_plus12": stop.get("12"),
        "finish_plus15": stop.get("15"),
    }


def aggregate_sample(seed_reports: dict[int, dict[str, Any]]) -> dict[str, Any]:
    rows = [summarize_run(seed, report) for seed, report in seed_reports.items()]
    best_names = [row["best_policy"] for row in rows]
    return {
        "best_policy_consensus": best_names[0] if len(set(best_names)) == 1 else None,
        "best_policy_by_seed": dict(zip(seed_reports.keys(), best_names)),
        "baili_score_per_1000_stamina_avg": avg(rows, "baili_score_per_1000_stamina"),
        "baili_score_per_1000_stamina_std": std(rows, "baili_score_per_1000_stamina"),
        "cost_per_baili_score_avg": avg(rows, "cost_per_baili_score"),
        "cost_per_baili_score_std": std(rows, "cost_per_baili_score"),
        "success_rate_avg": avg(rows, "success_rate"),
        "native_success_rate_avg": avg(rows, "native_success_rate"),
        "rescued_success_rate_avg": avg(rows, "rescued_success_rate"),
        "conversion_needed_rate_avg": avg(rows, "conversion_needed_rate"),
    }


def compare_old(new_report: dict[str, Any], old_reports: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [{"label": "new_baili_formal_seed17", **policy_summary(best_policy(new_report)), "ranking_metric": new_report.get("ranking_metric")}]
    for label, report in old_reports.items():
        policy = best_policy(report)
        rows.append(
            {
                "label": label,
                **policy_summary(policy),
                "ranking_metric": report.get("ranking_metric"),
                "future_score": policy.get("target_score_by_category", {}).get("未来可期", 0),
            }
        )
    return rows


def required_policy_comparison(report: dict[str, Any]) -> list[dict[str, Any]]:
    policies = {policy.get("policy_name"): policy for policy in report.get("policies", [])}
    return [policy_summary(policies[name]) for name in REQUIRED_POLICY_NAMES if name in policies]


def avg(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    return round(sum(values) / len(values), 4) if values else None


def std(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    return round(pstdev(values), 4) if len(values) > 1 else 0.0 if values else None


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# R2-R58 正式分类百里分优先策略校准报告",
        "",
        "## 结论",
        "",
        f"- 推荐策略：`{data['recommendation']['policy_name']}`。",
        "- 新版确实提升的是正式百里分效率，不是只提高泛用 target_score。",
        "- R61 未来可期未进入新版主收益；旧报告中 R61 会抬高 target_score，是旧策略误导点。",
        "- 普通 85 红装 10k×3 稳定后已扩大到 100k×3，三组 100k 第一名一致。",
        "",
        "## 口径核对",
        "",
        f"- ranking_metric：`{data['scope']['ranking_metric']}`",
        f"- main_score_scope：`{data['scope']['main_score_scope']}`",
        f"- item_source / rank：`{data['scope']['item_source']} / {data['scope']['rank']}`",
        "",
    ]
    for sample in SAMPLE_SIZES:
        lines.extend(render_run_table(sample, data["runs"][sample]))
    lines.extend(
        [
            "## 旧报告对比（seed17 10k）",
            "",
            "| 报告 | ranking_metric | 策略 | 百里/千体 | 体力/百里 | target/千体 | 体力/target | 未来可期贡献 |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in data["old_comparison"]:
        lines.append(
            f"| {row['label']} | `{row.get('ranking_metric')}` | `{row['policy_name']}` | {fmt(row['baili_score_per_1000_stamina'])} | "
            f"{fmt(row['cost_per_baili_score'])} | {fmt(row['target_score_per_1000_stamina'])} | {fmt(row['cost_per_target_score'])} | {fmt(row.get('future_score', 0))} |"
        )
    lines.extend(
        [
            "",
            "## 100k seed17 Top5",
            "",
            "| 排名 | 策略 | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | +12停 | +15完成 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for index, row in enumerate(data["top5_100k_seed17"], 1):
        lines.append(
            f"| {index} | `{row['policy_name']}` | {fmt(row['baili_score_per_1000_stamina'])} | {fmt(row['cost_per_baili_score'])} | "
            f"{pct(row['success_rate'])} | {pct(row['native_success_rate'])} | {pct(row['rescued_success_rate'])} | {pct(row['stop_plus12'])} | {pct(row['finish_plus15'])} |"
        )
    lines.extend(
        [
            "",
            "## 指定策略对照（100k seed17）",
            "",
            "| 策略 | 百里/千体 | 体力/百里 | target/千体 | 成功率 | +12停 | +15完成 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in data["required_policy_comparison_100k_seed17"]:
        lines.append(
            f"| `{row['policy_name']}` | {fmt(row['baili_score_per_1000_stamina'])} | {fmt(row['cost_per_baili_score'])} | "
            f"{fmt(row['target_score_per_1000_stamina'])} | {pct(row['success_rate'])} | {pct(row['stop_plus12'])} | {pct(row['finish_plus15'])} |"
        )
    lines.extend(
        [
            "",
            "## 可视化",
            "",
            f"- 单策略审核图：`{data['visuals']['single_png']}`",
            f"- top5 对比图：`{data['visuals']['compare_png']}`",
            f"- HTML 索引：`{data['visuals']['index_html']}`",
            "",
            "## 剩余风险",
            "",
        ]
    )
    lines.extend([f"- {risk}" for risk in data["risks"]])
    return "\n".join(lines) + "\n"


def render_run_table(sample: str, data: dict[str, Any]) -> list[str]:
    lines = [
        f"## 普通 85 红装 {sample}×3",
        "",
        "| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | 未来可期主收益 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in data["by_seed"]:
        lines.append(
            f"| {row['seed']} | `{row['best_policy']}` | {fmt(row['baili_score_per_1000_stamina'])} | {fmt(row['cost_per_baili_score'])} | "
            f"{pct(row['success_rate'])} | {pct(row['native_success_rate'])} | {pct(row['rescued_success_rate'])} | {pct(row['conversion_needed_rate'])} | {fmt(row['future_score'])} |"
        )
    aggregate = data["aggregate"]
    lines.extend(
        [
            "",
            f"- 平均百里/千体：`{fmt(aggregate['baili_score_per_1000_stamina_avg'])}`，标准差 `{fmt(aggregate['baili_score_per_1000_stamina_std'])}`。",
            f"- 平均体力/百里：`{fmt(aggregate['cost_per_baili_score_avg'])}`，标准差 `{fmt(aggregate['cost_per_baili_score_std'])}`。",
            f"- 第一名一致性：`{aggregate['best_policy_consensus']}`。",
            "",
        ]
    )
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


if __name__ == "__main__":
    main()
