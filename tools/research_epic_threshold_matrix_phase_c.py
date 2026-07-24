"""Phase B/C mapping repair replay using Phase B formal R10 base paths only.

This module intentionally never simulates a formal +3 onward path.  It reloads
the verified common-path cache, refreshes only the selected-candidate features,
and aggregates the pre-registered output and pure-tank threshold rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Iterable
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, _source_rank_gears
from tools.research_epic_exact_plus3 import load_real_plus0
from tools.research_riftslash_saint_pool import YIELD_VARIATIONS, _t95, explicit_batch_resource_pool


STUDY = "epic_threshold_matrix_phase_bc_mapping_repair_tank_review_20260718"
SCHEMA_VERSION = 3
MAPPING_VERSION = "formal_category_groups_exact_v1"
PHASE_B_RESUME = ROOT / "reports" / "epic_threshold_matrix_phase_b_formal_r10_resume_20260718"
PHASE_B_NODE_RESUME = ROOT / "reports" / "epic_threshold_matrix_phase_b_resume_20260717"
DEFAULT_JSON = ROOT / "reports" / "epic_threshold_matrix_phase_bc_mapping_repair_20260718.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_threshold_matrix_phase_bc_mapping_repair_20260718.md"
SYSTEM_GROUPS = ("pure_output", "pure_tank", "bruiser", "dual", "unknown")


@dataclass(frozen=True)
class Rule:
    key: str
    default: tuple[int, int] | None
    overrides: dict[str, tuple[int, int]]
    release_class: str
    description: str


def _tank_rule(t0: int, t3: int) -> Rule:
    return Rule(
        f"output_8_13_tank_{t0}_{t3}",
        (12, 17),
        {"pure_output": (8, 13), "pure_tank": (t0, t3)},
        "tank_control_variable",
        f"默认12/17，纯输出8/13固定保护，纯坦{t0}/{t3}",
    )


RULES = (
    Rule("current_formal", None, {}, "reference", "当前正式策略"),
    Rule("global_10_14", (10, 14), {}, "conservative_history", "全局10/14历史保守对照"),
    Rule("global_12_17", (12, 17), {}, "balanced_reference", "全局12/17均衡对照"),
    Rule("global_14_18", (14, 18), {}, "aggressive_reference", "全局14/18激进参考"),
    Rule("balanced_output_m2", (12, 17), {"pure_output": (10, 15)}, "output_replay", "默认12/17，纯输出10/15"),
    Rule("balanced_output_m4", (12, 17), {"pure_output": (8, 13)}, "output_protection", "默认12/17，纯输出8/13固定保护"),
    Rule("balanced_high_priority_m2", (12, 17), {"pure_output": (10, 15), "pure_tank": (10, 15)}, "historical_combo_replay", "默认12/17，输出/纯坦10/15"),
) + tuple(_tank_rule(t0, t3) for t0 in (8, 10, 12) for t3 in (13, 15, 17))


def _stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def candidate_hash(rule: Rule) -> str:
    return _stable_hash({
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "mapping_version": MAPPING_VERSION,
        "formal_category_groups": phase_b.FORMAL_CATEGORY_GROUPS,
        "rule": asdict(rule),
    })


def _legal_tank_gap(rule: Rule) -> bool | None:
    tank = rule.overrides.get("pure_tank")
    return None if tank is None else tank[1] >= tank[0] + 3


def _threshold(rule: Rule, checkpoint: int, features: dict[str, Any]) -> int:
    if rule.default is None:
        raise ValueError("current_formal has no threshold")
    default = rule.default[0] if checkpoint == 0 else rule.default[1]
    override = rule.overrides.get(str(features["system_group"]))
    if override is None:
        return default
    return override[0] if checkpoint == 0 else override[1]


def action(formal: str, checkpoint: int, features: dict[str, Any], rule: Rule) -> str:
    if rule.default is None or formal == "stop":
        return formal
    candidate = phase_b.Candidate(_threshold(rule, 0, features), _threshold(rule, 3, features))
    return phase_b.action(formal, checkpoint, features, candidate)


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _flow(gear: Gear, base: dict[str, Any], rule: Rule) -> dict[str, float]:
    total = _empty_flow()
    action0 = action(str(base["start_formal_action"]), 0, base["start_features"], rule)
    for branch in base["branches"]:
        probability = float(branch["probability"])
        if action0 == "stop":
            _add(total, phase_b._flow(gear, {0: gear}, phase_b._outcome_zero()), probability)
            continue
        _add(total, branch["base_to_three"], probability)
        if action(str(branch["formal_action"]), 3, branch["features"], rule) == "stop":
            continue
        later_flows = branch["later_flows"]
        if not later_flows:
            raise RuntimeError("candidate continued a cached +3 state without a formal downstream path")
        for later in later_flows:
            _add(total, later, probability / len(later_flows))
    return total


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values)
    half = _t95(len(values)) * stdev(values) / sqrt(len(values)) if len(values) > 1 else 0.0
    return {"mean": center, "interval95": [center - half, center + half]}


def _group_node_metrics(rows: Iterable[dict[str, Any]], rule: Rule, checkpoint: int) -> dict[str, Any]:
    selected = [(row, action(str(row["current_action"]), checkpoint, row["features"], rule)) for row in rows]
    total = sum(float(row["weight"]) for row, _ in selected)
    positive = [(row, result) for row, result in selected if row["oracle_label"] == "clear_positive"]
    false = [(row, result) for row, result in positive if result == "stop"]

    def summarize(items: list[tuple[dict[str, Any], str]]) -> dict[str, Any]:
        item_total = sum(float(row["weight"]) for row, _ in items)
        item_false = [(row, result) for row, result in items if result == "stop" and row["oracle_label"] == "clear_positive"]
        return {
            "state_count": len(items),
            "state_probability_mass": item_total,
            "stop_probability_mass": sum(float(row["weight"]) for row, result in items if result == "stop"),
            "clear_positive_false_stop_count": len(item_false),
            "clear_positive_false_stop_probability_mass": sum(float(row["weight"]) for row, _ in item_false),
            "utility_loss": sum(float(row["weight"]) * float(row["oracle"]["utility_margin"]) for row, _ in item_false),
            "regret": sum(float(row["weight"]) * (max(0.0, float(row["oracle"]["utility_margin"])) if result == "stop" else max(0.0, -float(row["oracle"]["utility_margin"]))) for row, result in items),
        }

    by_group = {
        group: summarize([(row, result) for row, result in selected if row["features"]["system_group"] == group])
        for group in SYSTEM_GROUPS
    }
    return {
        "state_count": len(selected),
        "state_probability_mass": total,
        "stop_rate": sum(float(row["weight"]) for row, result in selected if result == "stop") / total if total else 0.0,
        "clear_positive_false_stop_count": len(false),
        "clear_positive_false_stop_probability_mass": sum(float(row["weight"]) for row, _ in false),
        "clear_positive_recall": 1.0 - sum(float(row["weight"]) for row, _ in false) / sum(float(row["weight"]) for row, _ in positive) if positive else 1.0,
        "utility_loss": sum(float(row["weight"]) * float(row["oracle"]["utility_margin"]) for row, _ in false),
        "regret": sum(float(row["weight"]) * (max(0.0, float(row["oracle"]["utility_margin"])) if result == "stop" else max(0.0, -float(row["oracle"]["utility_margin"]))) for row, result in selected),
        "saved_next_node_stamina": sum(float(row["weight"]) * float(row["oracle"]["forced_continue_stamina"]) for row, result in selected if result == "stop"),
        "by_system_group": by_group,
    }


def _category_audit(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    groups: dict[str, int] = {}
    for row in rows:
        category = str(row["features"]["category"])
        group = str(row["features"]["system_group"])
        counts[category] = counts.get(category, 0) + 1
        groups[group] = groups.get(group, 0) + 1
        if category in phase_b.FORMAL_CATEGORY_GROUPS and group == "unknown":
            raise RuntimeError(f"formal category entered unknown: {category}")
    unknown = [{"category": name, "count": count} for name, count in sorted(counts.items()) if phase_b.system_group(name) == "unknown"]
    return {"formal_category_counts": counts, "system_group_counts": groups, "unknown_categories": unknown}


def _sample_counts(plus0: list[dict[str, Any]]) -> dict[str, Any]:
    by_group: dict[str, int] = {group: 0 for group in SYSTEM_GROUPS}
    by_group_slot: dict[str, dict[str, int]] = {group: {} for group in SYSTEM_GROUPS}
    for row in plus0:
        group = str(row["features"]["system_group"])
        slot = str(row["gear"]["slot"])
        by_group[group] = by_group.get(group, 0) + 1
        by_group_slot.setdefault(group, {})[slot] = by_group_slot.setdefault(group, {}).get(slot, 0) + 1
    return {"by_system_group": by_group, "by_system_group_and_slot": by_group_slot}


def _refresh_epic_base(payload: dict[str, Any], gear: Gear) -> dict[str, Any]:
    base = dict(payload["base"])
    base["start_features"] = phase_b.selected_candidate_snapshot(gear)
    branches = []
    for original in base["branches"]:
        branch = dict(original)
        branch["features"] = phase_b.selected_candidate_snapshot(Gear.from_dict(branch["gear"]))
        branches.append(branch)
    base["branches"] = branches
    return base


def _verified_base_payload(rank: str, seed: int, gear_index: int, gear: Gear, expected_hashes: dict[str, str]) -> dict[str, Any]:
    path = phase_b._base_path(PHASE_B_RESUME, rank, seed, gear_index)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise RuntimeError(f"missing or invalid Phase B formal base shard: {path}") from error
    if payload.get("status") != "complete" or payload.get("schema_version") != phase_b.JOINT_SCHEMA_VERSION:
        raise RuntimeError(f"incompatible Phase B formal base shard: {path}")
    if payload.get("rank") != rank or payload.get("seed") != seed or payload.get("gear_index") != gear_index:
        raise RuntimeError(f"wrong base shard identity: {path}")
    for field in ("formal_policy_hash", "roll_table_hash", "resource_model_hash"):
        if payload.get(field) != expected_hashes[field]:
            raise RuntimeError(f"Phase B base cache {field} mismatch: {path}")
    if not isinstance(payload.get("base"), dict):
        raise RuntimeError(f"Phase B base shard has no base payload: {path}")
    return payload


def _verify_base_cache(base_gears: list[Gear], heroic_gears: list[Gear]) -> dict[str, Any]:
    expected_hashes = phase_b._base_hashes()
    checked = 0
    r10_checked = 0
    for rank, gears in (("Epic", base_gears), ("Heroic", heroic_gears)):
        for seed in phase_b.SEEDS:
            for index, gear in enumerate(gears):
                _verified_base_payload(rank, seed, index, gear, expected_hashes)
                checked += 1
                candidate_path = phase_b._joint_path(PHASE_B_RESUME, phase_b.CURRENT_KEY if rank == "Epic" else phase_b.HEROIC_SHARED_KEY, rank, seed, index)
                candidate_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
                if int(candidate_payload.get("runs", -1)) != 10:
                    raise RuntimeError(f"Phase B formal cache is not runs=10: {candidate_path}")
                r10_checked += 1
    return {
        "status": "verified_reused",
        "base_shards_checked": checked,
        "runs10_candidate_shards_checked": r10_checked,
        "verified_hashes": {field: expected_hashes[field] for field in ("formal_policy_hash", "roll_table_hash", "resource_model_hash")},
        "excluded_base_builder_hash_reason": "system_group mapping changes candidate aggregation only, not the cached formal downstream path",
    }


def _summary(per_seed: dict[str, Any], rules: tuple[Rule, ...]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for yield_name in YIELD_VARIATIONS:
        current_rates = [per_seed[str(seed)][yield_name]["current_formal"]["formal_rate_per_100"] for seed in phase_b.SEEDS]
        current_baili = [per_seed[str(seed)][yield_name]["current_formal"]["per_100k"]["value_sum"] for seed in phase_b.SEEDS]
        fixed_output_tank_rates = [per_seed[str(seed)][yield_name]["balanced_output_m4"]["formal_rate_per_100"] for seed in phase_b.SEEDS]
        fixed_output_tank_baili = [per_seed[str(seed)][yield_name]["balanced_output_m4"]["per_100k"]["value_sum"] for seed in phase_b.SEEDS]
        rows: dict[str, Any] = {}
        for rule in rules:
            values = [per_seed[str(seed)][yield_name][rule.key] for seed in phase_b.SEEDS]
            baili = [value["per_100k"]["value_sum"] for value in values]
            rows[rule.key] = {
                "formal_rate_per_100": _ci([value["formal_rate_per_100"] for value in values]),
                "candidate_minus_current_rate": _ci([value["formal_rate_per_100"] - current for value, current in zip(values, current_rates)]),
                "candidate_minus_fixed_output_tank_12_17_rate": _ci([value["formal_rate_per_100"] - fixed for value, fixed in zip(values, fixed_output_tank_rates)]),
                "per_100k": {field: _ci([value["per_100k"][field] for value in values]) for field in ("value_sum", "speed22", "native_heirloom", "converted_heirloom")},
                "paired_baili_increment_vs_current": _ci([value - current for value, current in zip(baili, current_baili)]),
                "paired_baili_increment_vs_fixed_output_tank_12_17": _ci([value - fixed for value, fixed in zip(baili, fixed_output_tank_baili)]),
                "stamina_per_baili_point": _ci([100000.0 / value for value in baili]),
                "rift_stamina_per_100k": _ci([value["rift_stamina_per_100k"] for value in values]),
                "saint_stamina_per_100k": _ci([value["saint_stamina_per_100k"] for value in values]),
                "cycles_per_100k": _ci([value["cycles_per_100k"] for value in values]),
            }
        summary[yield_name] = {"ranking": sorted(rows, key=lambda key: (-rows[key]["formal_rate_per_100"]["mean"], key)), "rows": rows}
    return summary


def run() -> dict[str, Any]:
    records = ROOT / "manual_acceptance" / "real_sample_records.json"
    plus0, plus3, preparation = phase_b.prepare(records, PHASE_B_NODE_RESUME, 1)
    category_audit = _category_audit(plus0 + plus3)
    base_gears = [Gear.from_dict(row["gear"]) for row in load_real_plus0(records, "development")]
    heroic = _source_rank_gears(json.loads((ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json").read_text(encoding="utf-8")), "Heroic")
    base_cache = _verify_base_cache(base_gears, heroic)
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    node_metrics: dict[str, Any] = {}
    per_seed: dict[str, Any] = {str(seed): {} for seed in phase_b.SEEDS}

    for rule in RULES:
        pass_ids = {row["instance_id"] for row in plus0 if action(str(row["current_action"]), 0, row["features"], rule) != "stop"}
        node_metrics[rule.key] = {
            "plus0": _group_node_metrics(plus0, rule, 0),
            "plus3": _group_node_metrics([row for row in plus3 if row["instance_id"] in pass_ids], rule, 3),
            "release_class": rule.release_class,
        }

    for seed in phase_b.SEEDS:
        epic_flows = {rule.key: _empty_flow() for rule in RULES}
        heroic_total = _empty_flow()
        for index, gear in enumerate(base_gears):
            payload = _verified_base_payload("Epic", seed, index, gear, phase_b._base_hashes())
            base = _refresh_epic_base(payload, gear)
            for rule in RULES:
                _add(epic_flows[rule.key], _flow(gear, base, rule))
        for index, gear in enumerate(heroic):
            payload = _verified_base_payload("Heroic", seed, index, gear, phase_b._base_hashes())
            _add(heroic_total, payload["base"]["flow"])
        for yield_name, multiplier in YIELD_VARIATIONS.items():
            per_seed[str(seed)][yield_name] = {}
            for rule in RULES:
                merged = {
                    field: epic_flows[rule.key][field] / len(base_gears) + float(batch["expected_output_by_rank"]["Heroic"]) * float(multiplier) * heroic_total[field] / len(heroic)
                    for field in FLOW_WITH_METRICS
                }
                pool = explicit_batch_resource_pool(
                    source_gold=float(batch["expected_source_gold_per_batch"]),
                    source_lower_stones=float(batch["expected_lower_stone_units"]),
                    powder_base_exp=merged["powder_units"] * 100,
                    lower_stone_units=merged["lower_stone_units"],
                    material_gold=merged["material_gold"],
                    conversion_gold=merged["conversion_gold"],
                    sell_gold=merged["sell_gold"],
                    sell_exp=merged["sell_exp_adjusted"],
                    material_scarcity_exp=merged["material_exp_adjusted"],
                    lower_stone_adjusted_exp=merged["lower_stone_adjusted_exp"],
                )
                total = float(pool["total_stamina"])
                cycles = 100000.0 / total
                per_seed[str(seed)][yield_name][rule.key] = {
                    "formal_rate_per_100": 100.0 * merged["value_sum"] / total,
                    "per_100k": {field: cycles * merged[field] for field in FLOW_WITH_METRICS},
                    "rift_stamina_per_100k": cycles * 85.0,
                    "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]),
                    "cycles_per_100k": cycles,
                }

    summary = _summary(per_seed, RULES)
    baseline_gain = summary["baseline"]["rows"]["global_12_17"]["candidate_minus_current_rate"]["mean"]
    pareto = []
    for rule in RULES:
        p0 = node_metrics[rule.key]["plus0"]
        p3 = node_metrics[rule.key]["plus3"]
        gain = summary["baseline"]["rows"][rule.key]["candidate_minus_current_rate"]["mean"]
        pareto.append({
            "candidate": rule.key,
            "efficiency_gain_vs_current_per_100_stamina": gain,
            "global_12_17_efficiency_gain_retained": gain / baseline_gain if baseline_gain else None,
            "positive_false_stop_probability_mass": p0["clear_positive_false_stop_probability_mass"] + p3["clear_positive_false_stop_probability_mass"],
            "utility_loss": p0["utility_loss"] + p3["utility_loss"],
            "regret": p0["regret"] + p3["regret"],
            "release_class": rule.release_class,
        })
    return {
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "scope": "offline_only_no_holdout_no_production_change",
        "phase_a": "global_uniform_phase_a_historical_only",
        "supersedes_for_selection": ["epic_threshold_matrix_phase_c_20260718", "balanced_output_m4"],
        "base_cache": base_cache,
        "data_isolation": {"development_only": True, "holdout": "paused_not_read", "runs": 10},
        "preparation": preparation,
        "category_audit": category_audit,
        "development_sample_counts": _sample_counts(plus0),
        "rules": [{**asdict(rule), "candidate_hash": candidate_hash(rule), "legal_t3_gap": _legal_tank_gap(rule)} for rule in RULES],
        "node_metrics": node_metrics,
        "per_seed": per_seed,
        "summary": summary,
        "pareto": pareto,
        "freeze": "not_frozen_pending_user_confirmation",
    }


def _fmt_ci(metric: dict[str, Any], digits: int = 3) -> str:
    lo, hi = metric["interval95"]
    return f"{metric['mean']:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"


def markdown(data: dict[str, Any]) -> str:
    baseline = data["summary"]["baseline"]["rows"]
    rules = {rule["key"]: rule for rule in data["rules"]}
    lines = [
        "# Epic 非速度 Phase B/C 体系映射修复与坦克门槛复核",
        "",
        "本报告仅重聚合已验证的 Phase B formal runs=10 公共后续路径。未执行新的正式路径模拟、未读取 holdout、未修改正式策略。所有绝对产量均条件于当前开发组真实 +0 胚子分布；候选差值使用同胚子、同官方 +3 分支和同五 seed 的配对比较。",
        "",
        "## 缓存与体系审计",
        "",
        f"- 公共基础缓存：{data['base_cache']['status']}，验证 {data['base_cache']['base_shards_checked']} 个 base 分片及 {data['base_cache']['runs10_candidate_shards_checked']} 个 runs=10 对照分片。",
        "- 已验证正式路径、官方跳值表和资源模型哈希一致；仅排除会受体系映射影响的 base builder 哈希。",
        f"- 正式分类计数：{data['category_audit']['formal_category_counts']}。unknown 实际分类：{data['category_audit']['unknown_categories']}。",
        "- 旧 Phase A、Phase B 正式报告和旧 Phase C 报告均未覆盖；旧 `balanced_output_m4` 不能作为选择依据。",
        "",
        "## 开发样本",
        "",
        "| 体系组 | +0胚子数 | 按部位 |",
        "|---|---:|---|",
    ]
    counts = data["development_sample_counts"]
    for group in SYSTEM_GROUPS:
        slots = ", ".join(f"{slot}:{count}" for slot, count in sorted(counts["by_system_group_and_slot"].get(group, {}).items())) or "-"
        lines.append(f"| {group} | {counts['by_system_group'].get(group, 0)} | {slots} |")
    lines.extend([
        "",
        "## 效率与配对区间（Heroic 基线产出）",
        "",
        "| 候选 | 门槛说明 | 坦克T3>=T0+3 | 正式百里分/100体力 | 相对当前配对增量/100体力 95%CI | 每10万总体力百里分 95%CI | 每点百里分体力 95%CI |",
        "|---|---|---|---:|---:|---:|---:|",
    ])
    for rule in RULES:
        row = baseline[rule.key]
        legal = rules[rule.key]["legal_t3_gap"]
        legal_text = "-" if legal is None else ("是" if legal else "否，仅完整矩阵对照")
        lines.append(f"| {rule.key} | {rules[rule.key]['description']} | {legal_text} | {_fmt_ci(row['formal_rate_per_100'], 6)} | {_fmt_ci(row['candidate_minus_current_rate'], 6)} | {_fmt_ci(row['per_100k']['value_sum'])} | {_fmt_ci(row['stamina_per_baili_point'])} |")
    lines.extend([
        "",
        "## 每10万总体力绝对产量（Heroic 基线产出）",
        "",
        "| 候选 | 正式百里分 | 22速 | 原生75+ | 转换75+ | 裂缝体力 | 圣女3-7体力 | 循环数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for rule in RULES:
        row = baseline[rule.key]
        lines.append(f"| {rule.key} | {_fmt_ci(row['per_100k']['value_sum'])} | {_fmt_ci(row['per_100k']['speed22'])} | {_fmt_ci(row['per_100k']['native_heirloom'])} | {_fmt_ci(row['per_100k']['converted_heirloom'])} | {_fmt_ci(row['rift_stamina_per_100k'])} | {_fmt_ci(row['saint_stamina_per_100k'])} | {_fmt_ci(row['cycles_per_100k'])} |")
    lines.extend([
        "",
        "## 纯坦控制变量相对固定输出保护",
        "",
        "参考路线为 `balanced_output_m4`：默认12/17、纯输出8/13、纯坦12/17。下表直接隔离纯坦门槛变化，只有满足T3>=T0+3的行可作为优先比较。",
        "",
        "| 纯坦门槛候选 | T3>=T0+3 | 相对参考正式价值率/100体力 95%CI | 相对参考百里分/10万体力 95%CI |",
        "|---|---|---:|---:|",
    ])
    for rule in RULES:
        if rule.release_class != "tank_control_variable":
            continue
        row = baseline[rule.key]
        legal = "是" if _legal_tank_gap(rule) else "否"
        lines.append(f"| {rule.key} | {legal} | {_fmt_ci(row['candidate_minus_fixed_output_tank_12_17_rate'], 6)} | {_fmt_ci(row['paired_baili_increment_vs_fixed_output_tank_12_17'])} |")
    lines.extend([
        "",
        "## 节点误停风险",
        "",
        "下表的概率质量是 +0 的装备权重或 +3 官方分支权重；+3 只统计该候选实际放行到 +3 的状态。发布闸门另行判断，本表不提前删除候选。",
        "",
        "| 候选 | 节点 | 体系组 | 正效用误停数 | 正效用误停概率质量 | utility loss | regret |",
        "|---|---|---|---:|---:|---:|---:|",
    ])
    for rule in RULES:
        for node_name in ("plus0", "plus3"):
            node = data["node_metrics"][rule.key][node_name]
            for group in SYSTEM_GROUPS:
                group_row = node["by_system_group"][group]
                lines.append(f"| {rule.key} | {node_name} | {group} | {group_row['clear_positive_false_stop_count']} | {group_row['clear_positive_false_stop_probability_mass']:.6f} | {group_row['utility_loss']:.6f} | {group_row['regret']:.6f} |")
    lines.extend([
        "",
        "## 效率收益与风险 Pareto",
        "",
        "| 候选 | 相对当前效率收益/100体力 | 保留全局12/17收益 | 正效用误停概率质量 | utility loss | regret |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in data["pareto"]:
        retained = row["global_12_17_efficiency_gain_retained"]
        text = "-" if retained is None else f"{retained:.2%}"
        lines.append(f"| {row['candidate']} | {row['efficiency_gain_vs_current_per_100_stamina']:.6f} | {text} | {row['positive_false_stop_probability_mass']:.6f} | {row['utility_loss']:.6f} | {row['regret']:.6f} |")
    lines.extend([
        "",
        "## Heroic 产出敏感性",
        "",
        "JSON 保留每个候选在 Heroic 基线及 ±20% 产出下的完整五 seed 配对区间。报告的主表使用基线；若排序或区间在敏感性场景变化，应在用户确认前扩样。",
        "",
        "## 结论状态",
        "",
        "- 本轮只修正离线研究口径并完成纯坦控制变量比较；没有自动选择候选。",
        "- 当前纯坦 68 件仅支持 pure_tank 合组研究；半肉 21 件、双效 1 件继续回退全局12/17，不能发布独立门槛。",
        "- 用户确认候选前，不冻结 holdout 哈希、不开始收集或读取 holdout，也不改正式策略。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    data = run()
    DEFAULT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    DEFAULT_REPORT.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"json": str(DEFAULT_JSON), "report": str(DEFAULT_REPORT), "rules": len(RULES)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
