"""Generate explainable +0/+3 calibration rules from exact DP labels.

This command is deliberately offline.  It creates legal, full-category gear
strata, labels each state with the existing exact route solver, performs a
deterministic per-group train/holdout split, then writes only exact-group
thresholds.  Unknown groups remain ``review`` in the application.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path
from typing import Any

from src.e7_enhance.calibration import (
    dp_assisted_policies,
    expected_final_reforge_speed,
    future_hit_count,
    speed_cross_probability,
)
from src.e7_enhance.enhance_simulator import (
    RollProfile,
    STAT_TYPE_BY_KEY,
    enhance_to_checkpoint,
    roll_range,
    slot_forbidden_substats,
)
from src.e7_enhance.lightweight_calibration import calibration_group, evaluate_early_candidates, group_id, passes_continue_threshold
from src.e7_enhance.models import Gear, Stat
from src.e7_enhance.route_solver import compute_optimal_route
from src.e7_enhance.rules import CATEGORY_RULES, SET_GROUPS, VALID_STATS, speed_potential_set_eligible
from src.e7_enhance.score_engine import full_category_matches
from src.e7_enhance.strategy_defaults import DEFAULT_GEAR_SOURCE


CONFIGS = (("normal_85", "Epic"), ("normal_85", "Heroic"), ("rift_85", "Epic"))
LEFT_MAIN = {"weapon": "atkFlat", "helm": "hpFlat", "armor": "defFlat"}
SLOTS = ("weapon", "helm", "armor", "neck", "ring", "boot")
MANUAL_CASES = (
    {"path": "建议结果/07.json", "expected_action": "continue", "expected_lightweight": "continue", "name": "07 高价值多跳速度"},
    {"path": "samples/manual_acceptance/01_normal_epic_plus0.json", "expected_lightweight": "review", "name": "01 普通红 +0 复核边界"},
    {"path": "samples/manual_acceptance/04_rift_epic_plus0.json", "expected_lightweight": "review", "name": "04 异界红 +0 复核边界"},
    {"path": "建议结果/14.json", "expected_lightweight": "review", "name": "14 单条偏离转换候选"},
)


def main_key_for(rule: dict[str, Any], slot: str) -> str | None:
    if slot in LEFT_MAIN:
        return LEFT_MAIN[slot]
    allowed = rule.get("main", {}).get(slot)
    return allowed[0] if allowed else None


def valid_keys_for(rule: dict[str, Any], count: int, slot: str, main_key: str, set_code: str) -> tuple[str, ...] | None:
    forbidden = slot_forbidden_substats(slot)
    available = [key for key in VALID_STATS[rule["validGroup"]] if key != main_key and key not in forbidden]
    for keys in combinations(available, count):
        gear = Gear(set=set_code, slot=slot, main_stat=Stat(STAT_TYPE_BY_KEY[main_key], 0), rank="Epic", substats=[Stat(STAT_TYPE_BY_KEY[key], 1) for key in keys])
        if any(match["category"] == rule["category"] for match in full_category_matches(gear)):
            return keys
    return None


def legal_full_category_templates() -> list[dict[str, Any]]:
    templates = []
    for rule in CATEGORY_RULES:
        sets = sorted(SET_GROUPS[rule["setGroup"]])
        if not sets:
            continue
        for slot in SLOTS:
            main_key = main_key_for(rule, slot)
            if main_key is None:
                continue
            for count in (3, 4):
                keys = valid_keys_for(rule, count, slot, main_key, sets[0])
                if keys:
                    templates.append({"rule": rule, "set": sets[0], "slot": slot, "main_key": main_key, "keys": keys, "count": count})
    return templates


def select_templates(templates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Pick varied categories/slots for a bounded calibration run."""
    if not limit:
        return templates
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for template in templates:
        by_category[template["rule"]["category"]].append(template)
    slot_cycle = ("boot", "weapon", "helm", "armor", "neck", "ring")
    selected = []
    for index, category in enumerate(sorted(by_category)):
        options = by_category[category]
        preferred_slot = slot_cycle[index % len(slot_cycle)]
        selected.append(next((item for item in options if item["slot"] == preferred_slot), options[0]))
        if len(selected) == limit:
            break
    return selected


def make_gear(template: dict[str, Any], item_source: str, rank: str, checkpoint: int, sample_index: int, rng: random.Random) -> Gear:
    profile = RollProfile(85, rank, item_source)
    keys = template["keys"]
    if rank == "Heroic":
        keys = keys[:3]
    values = []
    for key in keys:
        low, high = roll_range(profile, key)
        values.append(Stat(STAT_TYPE_BY_KEY[key], rng.randint(low, high), rolls=1))
    gear = Gear(
        set=template["set"],
        slot=template["slot"],
        main_stat=Stat(STAT_TYPE_BY_KEY[template["main_key"]], 0),
        enhance=0,
        level=85,
        rank=rank,
        substats=values,
        reforge_eligible=True,
    )
    if checkpoint:
        # The fixed seeded RNG preserves a reproducible legal hit path.
        gear, _ = enhance_to_checkpoint(gear, checkpoint, item_source, rng)
    return gear


def feature_row(gear: Gear, item_source: str, category: str) -> dict[str, Any]:
    candidate = next(item for item in evaluate_early_candidates(gear, item_source) if item["category"] == category)
    speed_stat = next((stat for stat in gear.substats if stat.key == "spd"), None)
    expected_speed = expected_final_reforge_speed(gear, item_source)
    remaining_hits = future_hit_count(gear)
    expected_speed_rolls = round((speed_stat.rolls + remaining_hits / len(gear.substats)) if speed_stat else 0, 1)
    set_eligible = speed_potential_set_eligible(gear.set)
    speed_probability = 0.0 if speed_stat is None else 1.0 if set_eligible else speed_cross_probability(gear, item_source, 20, expected_speed)
    speed_potential = expected_speed * (expected_speed_rolls - 1) if speed_stat and expected_speed_rolls > 1 and (set_eligible or expected_speed >= 20) else 0.0
    group = calibration_group(
        gear,
        item_source,
        candidate["set_group"],
        category,
        candidate["current_valid_substat_count"],
        candidate["feasible_valid_substat_count"],
    )
    return {
        "group": group,
        "group_id": group_id(group),
        "category": category,
        "set_group": candidate["set_group"],
        "expected_final_reforge_score": candidate["expected_final_gs"],
        "expected_final_target_score": candidate["expected_terminal_value"],
        "current_effective_score": candidate["current_reforged_gs"],
        "remaining_hits": remaining_hits,
        "formal_cross_tier_probability": candidate["terminal_reach_probability"],
        "terminal_reach_probability": candidate["terminal_reach_probability"],
        "current_valid_substat_count": candidate["current_valid_substat_count"],
        "feasible_valid_substat_count": candidate["feasible_valid_substat_count"],
        "expected_final_speed": expected_speed,
        "speed": speed_stat.normalized_value if speed_stat else 0.0,
        "speed_rolls": speed_stat.rolls if speed_stat else 0,
        "speed_potential_value": round(speed_potential, 1),
        "speed_potential_set_eligible": set_eligible,
        "speed_main_boot": gear.slot == "boot" and gear.main_stat.key == "spd",
        "multi_roll_speed": bool(speed_stat and speed_stat.rolls >= 2),
    }


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * probability))]


MIN_TRAIN_SAMPLES = 8


def synthesize_rule(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows or rows[0]["current_valid_substat_count"] != 4:
        return None
    positives = [row for row in rows if row["dp_action"] == "continue"]
    if len(rows) < MIN_TRAIN_SAMPLES or len(positives) < MIN_TRAIN_SAMPLES:
        return None
    if any(row["expected_final_target_score"] <= 0 for row in positives):
        return None
    # Conservative lower envelope: only conditions shared by observed DP-
    # continue rows permit automatic continuation.  Stopping remains stricter.
    return {
        "group": positives[0]["group"],
        "support": {"train": len(rows), "dp_continue": len(positives), "dp_stop": len(rows) - len(positives), "minimum_train_samples": MIN_TRAIN_SAMPLES},
        "continue": {
            "expected_final_reforge_score_min": round(percentile([row["expected_final_reforge_score"] for row in positives], 0.25), 1),
            "expected_final_target_score_min": round(percentile([row["expected_final_target_score"] for row in positives], 0.25), 1),
            "current_effective_score_min": round(percentile([row["current_effective_score"] for row in positives], 0.25), 1),
            "remaining_hits_min": int(min(row["remaining_hits"] for row in positives)),
            "formal_cross_tier_probability_min": round(percentile([row["formal_cross_tier_probability"] for row in positives], 0.25), 4),
            "terminal_reach_probability_min": round(percentile([row["terminal_reach_probability"] for row in positives], 0.25), 4),
            "current_valid_substat_count_min": 4,
            "feasible_valid_substat_count_min": int(min(row["feasible_valid_substat_count"] for row in positives)),
            "expected_final_speed_min": round(percentile([row["expected_final_speed"] for row in positives], 0.25), 1),
            "speed_rolls_min": int(min(row["speed_rolls"] for row in positives)),
            "speed_potential_value_min": round(percentile([row["speed_potential_value"] for row in positives], 0.25), 1),
            "speed_potential_set_eligible": all(row["speed_potential_set_eligible"] for row in positives),
        },
        # The application only checks this after it has already established
        # that no complete category and no speed protection route remain.
        "stop": {"theoretical_upper_bound_lt": 0.0},
    }


def label(gear: Gear, item_source: str, rank: str) -> dict[str, Any]:
    policy = dp_assisted_policies(item_source, rank)[0]
    route = compute_optimal_route(gear, policy.dp_lambda_value or 0.0, policy.dp_conversion_cost, item_source, rank=rank)
    return {
        "dp_action": route["action"],
        "dp_expected_utility": route["expected_utility"],
        "dp_continue_utility": route["continue_utility"],
        "dp_expected_terminal_value": route["expected_terminal_value"],
        "dp_best_target_category": route["best_target_category"],
    }


def label_job(job: tuple[Gear, str, str]) -> dict[str, Any]:
    return label(*job)


def selected_manual_feature(case: dict[str, Any]) -> dict[str, Any] | None:
    data = json.loads(Path(case["path"]).read_text(encoding="utf-8"), strict=False)
    gear_data = data.get("gear") if isinstance(data.get("gear"), dict) else data
    gear = Gear.from_dict(gear_data)
    item_source = str(data.get("itemSource") or gear_data.get("itemSource") or "normal_85")
    candidates = evaluate_early_candidates(gear, item_source)
    selected = next((item for item in candidates if item["qualified"]), None)
    if selected is None:
        return None
    return feature_row(gear, item_source, selected["category"])


def add_manual_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manual_rows = []
    constraints = []
    for case in MANUAL_CASES:
        feature = selected_manual_feature(case)
        if feature and case.get("expected_lightweight"):
            constraints.append({"name": case["name"], "expected_lightweight": case["expected_lightweight"], "feature": feature})
        if "expected_action" not in case:
            manual_rows.append({"name": case["name"], "expected_lightweight": case.get("expected_lightweight"), "exact_action": None, "passed": True})
            continue
        data = json.loads(Path(case["path"]).read_text(encoding="utf-8"), strict=False)
        gear = Gear.from_dict(data["gear"])
        exact = label(gear, "normal_85", gear.rank)
        manual_rows.append({"name": case["name"], "expected_action": case["expected_action"], "expected_lightweight": case.get("expected_lightweight"), "exact_action": exact["dp_action"], "passed": case["expected_action"] == exact["dp_action"]})
    return manual_rows, constraints


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# +0/+3 候选体系轻量预测校准报告",
        "",
        f"- 版本：{report['version']}",
        f"- 随机种子：{report['seed']}",
        f"- 精确 DP 标注样本：{report['sample_count']}",
        f"- 训练/保留集：{report['train_count']} / {report['holdout_count']}",
        f"- 覆盖范围：{report['scope']}",
        f"- 精确 DP 并行进程：{report['workers']}",
        f"- 已发布自动继续规则：{report['published_rule_count']}",
        "- 分组键包含来源、品质、部位、主属性约束、体系、套装组、当前有效副属性数和可行有效副属性数。",
        "- 未覆盖分组在产品中固定为‘待 +6 精确复核’，不回退到全局阈值。",
        "",
        "## 保留集结果",
        "",
        "| 分组 | 可校准样本 | 硬例外样本 | 直接决策一致率 | 复核延后率 | 误继续率 | 误停止率 | 轻量停止而 DP 继续 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, item in report["holdout_metrics"].items():
        lines.append(f"| `{key}` | {item['count']} | {item['hard_exception_count']} | {item['direct_agreement']} | {item['review_defer_rate']} | {item['false_continue_rate']} | {item['false_stop_rate']} | {item['false_stop_dp_continue_rate']} |")
    lines.extend(["", "## 速度专项", "", json.dumps(report["speed_metrics"], ensure_ascii=False, indent=2), "", "## 人工硬回归", "", json.dumps(report["manual_cases"], ensure_ascii=False, indent=2)])
    return "\n".join(lines) + "\n"


def run(samples_per_group: int, seed: int, max_groups: int = 0, workers: int = 1) -> tuple[dict[str, Any], dict[str, Any]]:
    rng = random.Random(seed)
    all_templates = legal_full_category_templates()
    prepared_rows: list[tuple[dict[str, Any], Gear, str, str]] = []
    for item_source, rank in CONFIGS:
        expected_count = 3 if rank == "Heroic" else 4
        templates = select_templates([item for item in all_templates if len(item["keys"]) == expected_count], max_groups)
        for template in templates:
            for checkpoint in (0, 3):
                for index in range(samples_per_group):
                    gear = make_gear(template, item_source, rank, checkpoint, index, rng)
                    category = template["rule"]["category"]
                    if not any(match["category"] == category for match in full_category_matches(gear)):
                        continue
                    row = feature_row(gear, item_source, category)
                    row["checkpoint"] = checkpoint
                    row["split"] = "holdout" if index % 3 == 2 else "train"
                    prepared_rows.append((row, gear, item_source, rank))
    jobs = [(gear, item_source, rank) for _row, gear, item_source, rank in prepared_rows]
    if workers > 1 and jobs:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            labels = list(executor.map(label_job, jobs))
    else:
        labels = [label_job(job) for job in jobs]
    rows = []
    for (row, _gear, _item_source, _rank), exact in zip(prepared_rows, labels):
        row.update(exact)
        rows.append(row)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["group_id"]].append(row)
    rules = []
    rejected_rules = []
    for group, group_rows in grouped.items():
        rule = synthesize_rule([row for row in group_rows if row["split"] == "train"])
        if rule is None:
            continue
        holdout = [row for row in group_rows if row["split"] == "holdout"]
        if not holdout:
            rejected_rules.append({"group": group, "reason": "缺少保留集"})
            continue
        false_continue = [row for row in holdout if passes_continue_threshold(rule, {**row, "full_category_matched": True}) and row["dp_action"] == "stop"]
        if false_continue:
            rejected_rules.append({"group": group, "reason": "保留集存在误继续", "count": len(false_continue)})
            continue
        rules.append(rule)
    manual_cases, manual_constraints = add_manual_cases()
    filtered_rules = []
    for rule in rules:
        conflicts = [
            constraint
            for constraint in manual_constraints
            if constraint["feature"]["group_id"] == group_id(rule["group"])
            and constraint["expected_lightweight"] != "continue"
            and passes_continue_threshold(rule, {**constraint["feature"], "full_category_matched": True})
        ]
        if conflicts:
            rejected_rules.append({"group": group_id(rule["group"]), "reason": "人工复核边界会被误继续", "cases": [item["name"] for item in conflicts]})
            continue
        filtered_rules.append(rule)
    rules = filtered_rules
    rules_payload = {"version": "full-category-dp-calibration-v1", "seed": seed, "rules": rules}
    rule_map = {group_id(rule["group"]): rule for rule in rules}
    metrics: dict[str, dict[str, Any]] = {}
    speed = Counter({
        "multi_roll_samples": 0,
        "multi_roll_review_dp_continue": 0,
        "speed_main_boot_samples": 0,
        "speed_main_boot_continue": 0,
    })
    for constraint in manual_constraints:
        feature = constraint["feature"]
        if feature["multi_roll_speed"]:
            speed["manual_multi_roll_samples"] += 1
            if constraint["expected_lightweight"] == "continue":
                speed["manual_multi_roll_continue"] += 1
    for group, group_rows in sorted(grouped.items()):
        holdout = [row for row in group_rows if row["split"] == "holdout"]
        if not holdout:
            continue
        rule = rule_map.get(group)
        predictions = []
        hard_exception_count = 0
        for row in holdout:
            special_speed_boot = bool(row["speed_main_boot"])
            speed_route = bool(row["multi_roll_speed"] and row["speed_potential_set_eligible"] and row["category"] in {"输出", "输出(必爆)"})
            predicted = "continue" if special_speed_boot or speed_route or passes_continue_threshold(rule, {**row, "full_category_matched": True}) else "review"
            if row["multi_roll_speed"]:
                speed["multi_roll_samples"] += 1
                if predicted == "review" and row["dp_action"] == "continue":
                    speed["multi_roll_review_dp_continue"] += 1
            if row["speed_main_boot"]:
                speed["speed_main_boot_samples"] += 1
                if predicted == "continue":
                    speed["speed_main_boot_continue"] += 1
                if row["dp_action"] == "stop":
                    speed["speed_main_boot_hard_exception_dp_stop"] += 1
                hard_exception_count += 1
                continue
            predictions.append((predicted, row["dp_action"]))
        count = len(predictions)
        metrics[group] = {
            "count": count,
            "hard_exception_count": hard_exception_count,
            "direct_agreement": round(sum(predicted == actual for predicted, actual in predictions) / count, 4) if count else None,
            "review_defer_rate": round(sum(predicted == "review" and actual == "continue" for predicted, actual in predictions) / count, 4) if count else None,
            "false_continue_rate": round(sum(predicted == "continue" and actual == "stop" for predicted, actual in predictions) / count, 4) if count else 0.0,
            "false_stop_rate": 0.0,
            "false_stop_dp_continue_rate": 0.0,
        }
    report = {
        "version": "full-category-dp-calibration-v1",
        "seed": seed,
        "samples_per_group": samples_per_group,
        "workers": workers,
        "scope": "all legal category/slot templates" if not max_groups else f"{max_groups} category/slot-stratified templates per rank shape (targeted run)",
        "sample_count": len(rows),
        "train_count": sum(row["split"] == "train" for row in rows),
        "holdout_count": sum(row["split"] == "holdout" for row in rows),
        "template_count": (max_groups * 2 if max_groups else len(all_templates)),
        "sample_distribution": {key: len(value) for key, value in sorted(grouped.items())},
        "holdout_metrics": metrics,
        "speed_metrics": dict(speed),
        "rejected_rules": rejected_rules,
        "published_rule_count": len(rules),
        "manual_cases": manual_cases,
    }
    return report, rules_payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-per-group", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260712)
    parser.add_argument("--max-groups", type=int, default=0, help="0 covers all legal category/slot templates")
    parser.add_argument("--workers", type=int, default=1, help="exact-DP worker processes; use 1 for lowest resource usage")
    parser.add_argument("--output", default="reports/full-category-lightweight-calibration.json")
    parser.add_argument("--markdown-output", default="reports/full-category-lightweight-calibration.md")
    parser.add_argument("--rules-output", default="src/e7_enhance/lightweight_calibration_rules.json")
    args = parser.parse_args()
    report, rules = run(max(1, args.samples_per_group), args.seed, args.max_groups, max(1, args.workers))
    for raw_path, payload in ((args.output, report), (args.rules_output, rules)):
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = Path(args.markdown_output)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(report_markdown(report), encoding="utf-8")
    print(json.dumps({"report": args.output, "markdown": args.markdown_output, "rules": args.rules_output, "sample_count": report["sample_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
