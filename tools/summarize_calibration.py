from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


REPORT = Path("reports/calibration-strategy-summary.md")
JSON_OUT = Path("reports/calibration-strategy-summary.json")
SEEDS = [17, 29, 43]
SOURCES = {
    "normal_epic": "普通 85 红装",
    "normal_heroic": "普通 85 紫装",
    "rift_epic": "85 红色异界装备",
}
COMMANDS = {
    "smoke": "& 'C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe' main.py calibrate --runs 1000 --seed 17 --item-source normal_85 --rank Epic --workers 1 --debug",
    "phase1": "& 'C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe' main.py calibrate --runs 100000 --seed <17|29|43> --item-source normal_85 --rank Epic --workers 16 --debug",
    "phase2_normal": "& 'C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe' main.py calibrate --runs 100000 --seed <17|29|43> --item-source normal_85 --rank Epic --workers 16 --top 44 --debug",
    "phase2_heroic": "& 'C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe' main.py calibrate --runs 100000 --seed <17|29|43> --item-source normal_85 --rank Heroic --workers 16 --top 44 --debug",
    "phase2_rift": "& 'C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe' main.py calibrate --runs 100000 --seed <17|29|43> --item-source rift_85 --rank Epic --workers 16 --top 44 --debug",
}


def main() -> None:
    aggregates = {label: aggregate_source(label) for label in SOURCES}
    phase1_top5 = [row["policy_name"] for row in aggregates["normal_epic"][:5]]
    selected = phase1_top5
    summary = {
        "phase1_top5": phase1_top5,
        "phase1_top3": phase1_top5[:3],
        "sources": aggregates,
    }
    JSON_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(render_report(aggregates, selected), encoding="utf-8")
    print(REPORT)
    print(JSON_OUT)
    print("phase1_top5=", phase1_top5)
    for label, rows in aggregates.items():
        print(label, rows[0]["policy_name"], rows[0]["cost_per_target_score_avg"], rows[0]["rank_by_seed"])


def load_source(label: str) -> list[tuple[int, dict[str, Any]]]:
    runs = []
    for seed in SEEDS:
        path = Path(f"reports/phase2-{label}-100k-seed{seed}.json")
        runs.append((seed, json.loads(path.read_text(encoding="utf-8-sig"))))
    return runs


def by_policy(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {policy["policy_name"]: policy for policy in data["policies"]}


def aggregate_source(label: str) -> list[dict[str, Any]]:
    runs = load_source(label)
    policies = sorted(by_policy(runs[0][1]))
    rows = []
    for name in policies:
        items = [by_policy(data)[name] for _, data in runs]
        cost_values = [item["cost_per_target_score"] for item in items if item.get("cost_per_target_score") is not None]
        ranks = []
        for _, data in runs:
            names = [policy["policy_name"] for policy in data["policies"]]
            ranks.append(names.index(name) + 1)
        score_by_category = sum_dict(items, "target_score_by_category")
        rows.append(
            {
                "policy_name": name,
                "policy_family": items[0].get("policy_family"),
                "thresholds": items[0]["thresholds"],
                "rank_by_seed": ranks,
                "avg_rank": round(mean(ranks), 2),
                "cost_per_target_score_avg": round(mean(cost_values), 1) if cost_values else None,
                "cost_per_target_score_std": round(pstdev(cost_values), 1) if len(cost_values) > 1 else 0.0,
                "cost_per_success_avg": avg_metric(items, "cost_per_success"),
                "success_rate_avg": avg_metric(items, "success_rate"),
                "native_success_rate_avg": avg_metric(items, "native_success_rate"),
                "rescued_success_rate_avg": avg_metric(items, "rescued_success_rate"),
                "conversion_needed_rate_avg": avg_metric(items, "conversion_needed_rate"),
                "marginal_value_per_stamina_avg": avg_metric(items, "marginal_value_per_stamina_avg"),
                "marginal_expected_gain_avg": avg_metric(items, "marginal_expected_gain_avg"),
                "marginal_cross_tier_probability_avg": avg_metric(items, "marginal_cross_tier_probability_avg"),
                "target_score_per_1000_stamina_avg": avg_metric(items, "target_score_per_1000_stamina"),
                "total_stamina_avg": avg_metric(items, "total_stamina_avg"),
                "stop_rate_by_checkpoint_avg": avg_rates(items, "stop_rate_by_checkpoint"),
                "target_score_by_category": score_by_category,
                "target_score_share_by_category": share_from_score(score_by_category),
            }
        )
    rows.sort(key=lambda row: (float("inf") if row["cost_per_target_score_avg"] is None else row["cost_per_target_score_avg"], row["avg_rank"]))
    return rows


def avg_metric(items: list[dict[str, Any]], key: str) -> float | None:
    values = [item[key] for item in items if item.get(key) is not None]
    return round(sum(values) / len(values), 4) if values else None


def avg_rates(items: list[dict[str, Any]], key: str) -> dict[str, float]:
    keys = sorted({subkey for item in items for subkey in item.get(key, {})})
    return {subkey: round(mean([item.get(key, {}).get(subkey, 0.0) for item in items]), 4) for subkey in keys}


def sum_dict(items: list[dict[str, Any]], key: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in items:
        for subkey, value in item.get(key, {}).items():
            result[subkey] = result.get(subkey, 0.0) + float(value)
    return dict(sorted((subkey, round(value, 1)) for subkey, value in result.items()))


def share_from_score(score_by_category: dict[str, float]) -> dict[str, float]:
    total = sum(score_by_category.values())
    if not total:
        return {}
    return dict(sorted((key, round(value / total, 4)) for key, value in score_by_category.items()))


def render_report(aggregates: dict[str, list[dict[str, Any]]], selected: list[str]) -> str:
    lines = [
        "# 第七史诗装备强化策略自动校准报告",
        "",
        "## 策略预判",
        "",
        "- 早期宽松：+0/+3 不看目标分，主要保留方向和未来速度；预期成功率高，但 +9 消耗会明显增加。",
        "- 均衡：+6 开始要求预计最终目标分，预期成本和成品率折中。",
        "- +6 收紧：在 +6 淘汰更多胚子，预期降低强化浪费，但可能错过后续补救。",
        "- +9/+12 严格：高边际成本节点收紧，预期单件成功质量高，但成功率低，样本波动更大。",
        "- 转换友好：允许一个 rolls<=2 的无效词条按转换补救计入，预期提升综合目标分效率，但当前未计转换石体力成本。",
        "",
        "## 五类预设策略门槛与普通红装表现",
        "",
        "| 策略族 | 策略 | 门槛/模式 | 每目标分体力 | 成功率 | 转换需求率 | 边际收益/体力 | 跨档概率 | seed排名 |",
        "|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    preset_rows = [row for row in aggregates["normal_epic"] if row["policy_name"].startswith("score_strategy_")]
    preset_rows.sort(key=lambda row: ["早期宽松", "均衡", "+6 收紧", "+9/+12 严格", "转换友好"].index(row["policy_family"]))
    for row in preset_rows:
        lines.append(
            f"| {row['policy_family']} | `{row['policy_name']}` | {threshold_text(row['thresholds'])} | "
            f"{fmt(row['cost_per_target_score_avg'])} | {fmt_pct(row['success_rate_avg'])} | "
            f"{fmt_pct(row['conversion_needed_rate_avg'])} | {fmt(row['marginal_value_per_stamina_avg'])} | "
            f"{fmt_pct(row['marginal_cross_tier_probability_avg'])} | {'/'.join(map(str, row['rank_by_seed']))} |"
        )
    lines.extend(
        [
            "",
        "## 实际命令",
        "",
        ]
    )
    for name, command in COMMANDS.items():
        lines.append(f"- `{name}`: `{command}`")
    lines.extend(
        [
            "",
            "## 阶段 1：普通 85 红装前 5 策略",
            "",
            "| 排名 | 策略 | 策略族 | 每目标分体力 | 每千体力目标分 | 每成功体力 | 成功率 | 原生率 | 补救率 | 转换需求率 | 边际收益/体力 | 跨档概率 | seed排名 |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for index, row in enumerate(aggregates["normal_epic"][:5], 1):
        lines.append(
            f"| {index} | `{row['policy_name']}` | {row['policy_family']} | {fmt(row['cost_per_target_score_avg'])} | {fmt(row['target_score_per_1000_stamina_avg'])} | "
            f"{fmt(row['cost_per_success_avg'])} | {fmt_pct(row['success_rate_avg'])} | {fmt_pct(row['native_success_rate_avg'])} | "
            f"{fmt_pct(row['rescued_success_rate_avg'])} | {fmt_pct(row['conversion_needed_rate_avg'])} | {fmt(row['marginal_value_per_stamina_avg'])} | "
            f"{fmt_pct(row['marginal_cross_tier_probability_avg'])} | {'/'.join(map(str, row['rank_by_seed']))} |"
        )
    lines.extend(
        [
            "",
            "阶段 1 判断：前三名稳定为 `score_target_low_speed_low/mid/high`；第一名三个 seed 都是 `score_target_low_speed_low`。`score_target_high_*` 在个别 seed 因少量高分样本进入前列，但成功率约 0.1%，波动风险更高。",
            "",
            "## 阶段 2：阶段 1 候选跨来源对比",
        ]
    )
    for label, title in SOURCES.items():
        rows_by_name = {row["policy_name"]: row for row in aggregates[label]}
        lines.extend(
            [
                "",
                f"### {title}",
                "| 策略 | 每目标分体力 | 每千体力目标分 | 每成功体力 | 成功率 | 原生率 | 补救率 | 转换需求率 | 边际收益/体力 | 跨档概率 | +0停 | +6停 | +9停 | +12停 | +15完成 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for name in selected:
            row = rows_by_name[name]
            stop = row["stop_rate_by_checkpoint_avg"]
            lines.append(
                f"| `{name}` | {fmt(row['cost_per_target_score_avg'])} | {fmt(row['target_score_per_1000_stamina_avg'])} | {fmt(row['cost_per_success_avg'])} | {fmt_pct(row['success_rate_avg'])} | "
                f"{fmt_pct(row['native_success_rate_avg'])} | {fmt_pct(row['rescued_success_rate_avg'])} | {fmt_pct(row['conversion_needed_rate_avg'])} | "
                f"{fmt(row['marginal_value_per_stamina_avg'])} | {fmt_pct(row['marginal_cross_tier_probability_avg'])} | "
                f"{fmt_pct(stop.get('0'))} | {fmt_pct(stop.get('6'))} | {fmt_pct(stop.get('9'))} | {fmt_pct(stop.get('12'))} | {fmt_pct(stop.get('15'))} |"
            )
        best = aggregates[label][0]
        main_share = sorted(rows_by_name[selected[0]]["target_score_share_by_category"].items(), key=lambda item: item[1], reverse=True)[:6]
        lines.append("")
        lines.append(f"- 本来源平均最优：`{best['policy_name']}`，每目标分体力 `{best['cost_per_target_score_avg']}`，seed 排名 `{best['rank_by_seed']}`。")
        lines.append("- 推荐候选的主要目标分来源：" + "，".join([f"{key} {value * 100:.1f}%" for key, value in main_share]))
    lines.extend(
        [
            "",
            "## 推荐门槛",
            "",
        ]
    )
    for label, title in SOURCES.items():
        best = aggregates[label][0]
        lines.append(f"- {title}：推荐 `{best['policy_name']}`。门槛：{threshold_text(best['thresholds'])}。")
    lines.extend(
        [
            "",
            "综合建议：普通红装先用 `score_target_low_speed_low`；紫装按每目标分也是 `score_target_low_speed_low`，但成功率极低，实战可单独用更宽的 `score_target_open_speed_low` 换更多补救件；异界按效率推荐 `score_target_high_speed_mid/low`，因为高跳值足以支撑更严格门槛。",
            "",
            "## 风险和后续",
            "",
            "- 每组 100000 样本，普通红装第一名稳定；紫装成功率太低，排序仍有随机波动。",
            "- 转换石成本未计入体力，所以转换友好策略的效率是上限估计。",
            "- 当前目标分完全来自 `套装属性与装等计算表.md`，但随机胚子生成仍是均匀模型，尚未按真实副属性掉落分布校正。",
            "- OCR、ADB、真实强化点击未覆盖。",
            "",
            "## 改动文件",
            "",
            "- `src/e7_enhance/calibration.py`：新增策略族、体系目标分贡献、全策略输出上限。",
            "- `src/e7_enhance/cli.py`：新增 `calibrate --top`。",
            "- `tests/test_calibration.py`：覆盖策略族、体系贡献字段和 `top_limit`。",
            "- `tools/summarize_calibration.py`：生成聚合策略报告。",
        ]
    )
    return "\n".join(lines) + "\n"


def threshold_text(thresholds: dict[str, Any]) -> str:
    target = thresholds["expected_final_target_score_min"]
    speed = thresholds["expected_final_reforge_speed_min"]
    valid = thresholds["valid_count_min"]
    return " / ".join([f"+{checkpoint}:目标分≥{target[checkpoint]},速≥{speed[checkpoint]},有效≥{valid[checkpoint]}" for checkpoint in ["0", "3", "6", "9", "12"]])


def fmt(value: Any) -> str:
    return "-" if value is None else str(value)


def fmt_pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.2f}%"


if __name__ == "__main__":
    main()
