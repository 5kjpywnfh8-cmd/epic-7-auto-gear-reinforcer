"""Frozen, offline audit for safe Epic +0/+3 early stopping candidates.

This study deliberately does not modify production policy.  It treats a stop
as admissible only when a shallow current-state cover survives a separately
frozen exact-DP validation set with *zero* clear-positive false stops.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.models import Gear
from tools.epic_non_speed_dp_oracle_audit import NUMERIC_ZERO_TOLERANCE, collect_audit_cases, oracle_for_gear
from tools.epic_non_speed_early_policy_pareto import _features, _speed_hard_route
from tools.research_epic_stage_balanced import StagePolicy, stage_action, stage_features

STUDY_ID = "epic_high_confidence_stop_20260714"
SCHEMA_VERSION = 1
# 64x the solver's displayed zero tolerance covers summation/display noise
# without being fitted to any candidate result.  It is frozen before Oracle
# labels are inspected.
EPSILON = NUMERIC_ZERO_TOLERANCE * 64
VALIDATION_HASH_CUTOFF = 10  # 10/16 fingerprints are development; 6/16 frozen.
MIN_VALIDATION_CASES_PER_NODE = 24


@dataclass(frozen=True)
class SafeStopRule:
    """Necessary current-state conditions, not an Oracle-action classifier."""

    checkpoint: int
    effective_gs_max: float
    current_valid_max: int
    terminal_probability_max: float
    conversion_value_max: float


# These rules are intentionally conservative and were written before this
# study's Oracle pass.  They use only data already available at the current
# checkpoint; neither instance IDs nor future rolls are inputs.
SAFE_STOP_RULES = {
    0: SafeStopRule(0, 8.0, 1, 0.002, 3.0),
    3: SafeStopRule(3, 14.0, 1, 0.002, 3.0),
}
GLOBAL_B = StagePolicy("B_global_current_gs", (30, 18), (30, 18))
STAGE_B = StagePolicy(
    "B_stage_conversion", (30, 18), (34, 22),
    use_hit=True, use_structure=True, use_category=True,
    use_probability=True, use_conversion=True,
)
STRATEGIES = ("current_formal", "B_global_current_gs", "B_stage_conversion", "safe_negative_cover")


def _speed_value(gear: Gear) -> float:
    return float(next((stat.normalized_value for stat in gear.substats if stat.key == "spd"), 0.0))


def in_scope(gear: Gear, raw: dict[str, Any]) -> bool:
    return (
        gear.rank == "Epic"
        and gear.enhance in SAFE_STOP_RULES
        and gear.slot != "Boots"
        and str(raw.get("itemSource") or "normal_85") == "normal_85"
        and _speed_value(gear) < 2
        and not _speed_hard_route(gear)
    )


def split_name(sample_id: str) -> str:
    bucket = int(hashlib.sha256(sample_id.encode("utf-8")).hexdigest()[0], 16)
    return "development" if bucket < VALIDATION_HASH_CUTOFF else "frozen_validation"


def current_action(gear: Gear, raw: dict[str, Any]) -> str:
    recommendation = str(advise_gear(
        gear, item_source="normal_85", gear_source=str(raw.get("gearSource") or ""),
    )["summary"]["recommendation"])
    return "stop" if recommendation == "stop" else "continue"


def safe_negative_action(features: dict[str, Any]) -> str:
    rule = SAFE_STOP_RULES[int(features["checkpoint"])]
    safe_stop = (
        float(features["effective_gs"]) <= rule.effective_gs_max
        and int(features["current_valid"]) <= rule.current_valid_max
        and float(features["probability"]) <= rule.terminal_probability_max
        and float(features["conversion_value"]) <= rule.conversion_value_max
    )
    return "stop" if safe_stop else "continue"


def strategy_actions(gear: Gear, raw: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    features = stage_features(gear)
    # Keep a simple field name in the artifact, independent of old stage tool.
    features["checkpoint"] = int(gear.enhance)
    return {
        "current_formal": current_action(gear, raw),
        "B_global_current_gs": "stop" if stage_action(GLOBAL_B, gear.enhance, features) == "stop" else "continue",
        "B_stage_conversion": "stop" if stage_action(STAGE_B, gear.enhance, features) == "stop" else "continue",
        "safe_negative_cover": safe_negative_action(features),
    }, features


def oracle_label(margin: float) -> str:
    if margin > EPSILON:
        return "clear_positive"
    if margin < -EPSILON:
        return "clear_negative"
    return "boundary"


def _case_from_snapshot(payload: tuple[str, dict[str, Any]]) -> dict[str, Any] | None:
    sample_id, snapshot = payload
    raw = snapshot.get("gear") or {}
    gear = Gear.from_dict(raw)
    if not in_scope(gear, raw):
        return None
    actions, features = strategy_actions(gear, raw)
    oracle = oracle_for_gear(gear)
    margin = float(oracle["utility_margin"])
    return {
        "sample_id": sample_id,
        "snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "fingerprint": str(snapshot.get("fingerprint") or ""),
        "partition": split_name(sample_id),
        "source_batches": list(snapshot.get("acceptance_batch_ids") or []),
        "review_status": str(snapshot.get("review_status") or "pending"),
        "gear": gear.to_dict(),
        "features": {
            key: features.get(key) for key in (
                "checkpoint", "category", "effective_gs", "current_valid", "feasible_valid",
                "slot_limited_three", "hit_target", "probability", "conversion_legal", "conversion_value",
            )
        },
        "actions": actions,
        "oracle": oracle,
        "oracle_label": oracle_label(margin),
    }


def _historical_instance_ids(data: dict[str, Any]) -> set[str]:
    linked = collect_audit_cases(records_payload=data)
    return {str(row["instance_id"]) for row in linked["included"]}


def load_population(records_path: Path) -> tuple[list[dict[str, Any]], int]:
    data = json.loads(records_path.read_text(encoding="utf-8"))
    historical_ids = _historical_instance_ids(data)
    rows: list[dict[str, Any]] = []
    excluded_historical = 0
    for sample_id, snapshot in (
        (str(record.get("sample_id") or ""), snapshot)
        for record in data.get("records") or []
        for snapshot in record.get("snapshots") or []
    ):
        raw = snapshot.get("gear") or {}
        if str(raw.get("instanceId") or "") in historical_ids:
            excluded_historical += 1
            continue
        gear = Gear.from_dict(raw)
        if not in_scope(gear, raw):
            continue
        actions, features = strategy_actions(gear, raw)
        rows.append({
            "sample_id": sample_id,
            "snapshot_id": str(snapshot.get("snapshot_id") or ""),
            "partition": split_name(sample_id),
            "actions": actions,
            "features": {"checkpoint": int(gear.enhance)},
        })
    return rows, excluded_historical


def load_cases(records_path: Path, *, workers: int = 1) -> list[dict[str, Any]]:
    data = json.loads(records_path.read_text(encoding="utf-8"))
    historical_ids = _historical_instance_ids(data)
    payloads = [
        (str(record.get("sample_id") or ""), snapshot)
        for record in data.get("records") or []
        for snapshot in record.get("snapshots") or []
        if str((snapshot.get("gear") or {}).get("instanceId") or "") not in historical_ids
    ]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            rows = [row for row in executor.map(_case_from_snapshot, payloads) if row is not None]
    else:
        rows = [row for row in map(_case_from_snapshot, payloads) if row is not None]
    return sorted(rows, key=lambda row: (row["sample_id"], row["snapshot_id"]))


def _metrics(rows: Iterable[dict[str, Any]], strategy: str) -> dict[str, Any]:
    rows = list(rows)
    clear_positive = [row for row in rows if row["oracle_label"] == "clear_positive"]
    clear_negative = [row for row in rows if row["oracle_label"] == "clear_negative"]
    boundary = [row for row in rows if row["oracle_label"] == "boundary"]
    stopped = [row for row in rows if row["actions"][strategy] == "stop"]
    false_stops = [row for row in clear_positive if row["actions"][strategy] == "stop"]
    false_continues = [row for row in clear_negative if row["actions"][strategy] != "stop"]
    regret = sum(
        max(0.0, float(row["oracle"]["utility_margin"]))
        if row["actions"][strategy] == "stop" else max(0.0, -float(row["oracle"]["utility_margin"]))
        for row in rows if row["oracle_label"] != "boundary"
    )
    saved = sum(float(row["oracle"]["forced_continue_stamina"]) for row in stopped)
    return {
        "sample_count": len(rows),
        "continue_count": len(rows) - len(stopped),
        "stop_count": len(stopped),
        "continue_rate": (len(rows) - len(stopped)) / len(rows) if rows else 0.0,
        "stop_rate": len(stopped) / len(rows) if rows else 0.0,
        "clear_positive_count": len(clear_positive),
        "clear_negative_count": len(clear_negative),
        "boundary_count": len(boundary),
        "clear_positive_false_stop_count": len(false_stops),
        "clear_positive_recall": 1.0 - len(false_stops) / len(clear_positive) if clear_positive else 1.0,
        "clear_negative_false_continue_count": len(false_continues),
        "total_regret": regret,
        "saved_next_node_stamina": saved,
        "mean_saved_next_node_stamina": saved / len(rows) if rows else 0.0,
    }


def summarize(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for partition in ("development", "frozen_validation"):
        result[partition] = {}
        for checkpoint in (0, 3):
            subset = [row for row in cases if row["partition"] == partition and row["features"]["checkpoint"] == checkpoint]
            result[partition][f"plus{checkpoint}"] = {strategy: _metrics(subset, strategy) for strategy in STRATEGIES}
    return result


def release_gate(summary: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    for checkpoint in (0, 3):
        metrics = summary["frozen_validation"][f"plus{checkpoint}"]["safe_negative_cover"]
        baseline = summary["frozen_validation"][f"plus{checkpoint}"]["current_formal"]
        if metrics["sample_count"] < MIN_VALIDATION_CASES_PER_NODE:
            reasons.append(f"+{checkpoint} 冻结验证仅 {metrics['sample_count']} 件，低于预定义最小 {MIN_VALIDATION_CASES_PER_NODE} 件。")
        if metrics["clear_positive_false_stop_count"]:
            reasons.append(f"+{checkpoint} 存在 {metrics['clear_positive_false_stop_count']} 件明确正效用误停。")
        if metrics["total_regret"] > baseline["total_regret"] + EPSILON:
            reasons.append(f"+{checkpoint} 总 regret 高于当前正式策略。")
        if metrics["mean_saved_next_node_stamina"] <= 0:
            reasons.append(f"+{checkpoint} 未降低平均下一节点强化资源。")
    # A five-seed joint-pool comparison is only meaningful after the per-item
    # safety gates pass.  Running it for a failed candidate would manufacture
    # a population conclusion from a four-item +3 validation slice.
    return {
        "passed": not reasons,
        "decision": "可建立新48件盲测批次" if not reasons else "不创建48件批次，正式Epic策略保持不变",
        "reasons": reasons,
        "joint_pool": {
            "status": "not_run_precondition_failed",
            "required_design": "5 independent seeds; Rift Epic/Heroic joint batch plus Saint 3-7 bottleneck; fixed Heroic base fallback + M1.",
            "reason": "每个节点的冻结 Oracle 安全闸门必须先通过；当前 +3 独立样本不足，不能将条件生成或旧盲测补作验证。",
            "per_100k_formal_baili": None,
            "per_100k_native_75": None,
            "per_100k_speed22": None,
            "rift_stamina": None,
            "saint_stamina": None,
            "source_cycles": None,
        },
    }


def _population_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for partition in ("development", "frozen_validation"):
        result[partition] = {}
        for checkpoint in (0, 3):
            subset = [row for row in rows if row["partition"] == partition and row["features"]["checkpoint"] == checkpoint]
            result[partition][f"plus{checkpoint}"] = {
                "sample_count": len(subset),
                "strategy_stop_counts": {key: sum(row["actions"][key] == "stop" for row in subset) for key in STRATEGIES},
            }
    return result


def run(records_path: Path, *, workers: int = 1) -> dict[str, Any]:
    population_rows, historical_excluded = load_population(records_path)
    population = _population_counts(population_rows)
    insufficient = [
        f"+{checkpoint} 冻结验证仅 {population['frozen_validation'][f'plus{checkpoint}']['sample_count']} 件，低于预定义最小 {MIN_VALIDATION_CASES_PER_NODE} 件。"
        for checkpoint in (0, 3)
        if population["frozen_validation"][f"plus{checkpoint}"]["sample_count"] < MIN_VALIDATION_CASES_PER_NODE
    ]
    if insufficient:
        return {
            "study": STUDY_ID,
            "schema_version": SCHEMA_VERSION,
            "frozen_before_oracle": {
                "epsilon": EPSILON,
                "epsilon_basis": "64 * exact DP NUMERIC_ZERO_TOLERANCE; numerical summation/display cushion, not candidate-tuned",
                "partition": "SHA256(sample_id) first hex < 10 => development, otherwise frozen_validation",
                "minimum_validation_cases_per_node": MIN_VALIDATION_CASES_PER_NODE,
                "safe_stop_rules": {str(key): rule.__dict__ for key, rule in SAFE_STOP_RULES.items()},
                "excluded": "old 0/48 batch, all old resume shards and prediction hashes; synthetic coverage is not loaded",
                "frozen_scope": "normal_85 Epic non-boot +0/+3, initial speed <2, excluding speed hard route; +6+ formal DP, Heroic base fallback+M1, rift and all production rules unchanged",
            },
            "data_isolation": {"records_path": str(records_path.relative_to(ROOT)), "training_and_validation": "deterministic record-level split; no instance ID is a feature", "historical_oracle_and_blind_instances_excluded": historical_excluded},
            "preflight_population": population,
            "summary": None,
            "release_gate": {
                "passed": False,
                "decision": "不创建48件批次，正式Epic策略保持不变",
                "reasons": insufficient,
                "joint_pool": {"status": "not_run_precondition_failed", "reason": "样本量预检未通过；未执行 Oracle 或五 seed 联合资源池，避免以不足的 +3 样本制造结论。"},
            },
            "cases": [],
        }
    cases = load_cases(records_path, workers=workers)
    summary = summarize(cases)
    return {
        "study": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "frozen_before_oracle": {
            "epsilon": EPSILON,
            "epsilon_basis": "64 * exact DP NUMERIC_ZERO_TOLERANCE; numerical summation/display cushion, not candidate-tuned",
            "partition": "SHA256(sample_id) first hex < 10 => development, otherwise frozen_validation",
            "minimum_validation_cases_per_node": MIN_VALIDATION_CASES_PER_NODE,
            "safe_stop_rules": {str(key): rule.__dict__ for key, rule in SAFE_STOP_RULES.items()},
            "excluded": "old 0/48 batch, all old resume shards and prediction hashes; synthetic coverage is not loaded",
            "frozen_scope": "normal_85 Epic non-boot +0/+3, initial speed <2, excluding speed hard route; +6+ formal DP, Heroic base fallback+M1, rift and all production rules unchanged",
        },
        "data_isolation": {
            "records_path": str(records_path.relative_to(ROOT)),
            "training_and_validation": "deterministic record-level split; no instance ID is a feature",
            "historical_note": "Records predate this study; the frozen split tests the candidate but is not a prospective player-drop cohort.",
            "historical_oracle_and_blind_instances_excluded": historical_excluded,
        },
        "summary": summary,
        "release_gate": release_gate(summary),
        "cases": cases,
    }


def _cell(metrics: dict[str, Any]) -> str:
    return f"{metrics['sample_count']} / {metrics['continue_rate']:.1%} / {metrics['stop_rate']:.1%} / {metrics['clear_positive_recall']:.1%} / {metrics['clear_positive_false_stop_count']} / {metrics['boundary_count']} / {metrics['total_regret']:.6f}"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Epic 非速度 +0/+3 高置信度止损研究（2026-07-14）", "",
        "## 结论", "",
        f"- {data['release_gate']['decision']}。",
        "- 本轮没有修改正式策略、跳值、DP、评分、资源、转换、Heroic M1、rift、GUI、OCR、ADB 或 Airtest。",
        f"- epsilon 固定为 `{data['frozen_before_oracle']['epsilon']:.2e}`；仅 utility 大于 epsilon 才算明确正效用，明确正效用误停必须为 0。",
        "- `safe_negative_cover` 是“当前谨慎继续，只有四个当前状态必要条件同时满足才停止”的覆盖层，不使用实例 ID、人工标签或 Oracle 动作作为输入。", "",
        "## 数据与隔离", "",
        "- 真实范围按样本记录 SHA256 分为开发与冻结验证；条件生成样本未加载。旧 0/48 前瞻批次、旧 resume 与预测哈希均未读取。",
        "- 历史样本只能用于离线风险审计；即使本轮闸门通过，也仍需新建、独立导入的 48 件前瞻盲测。", "",
        "## 节点结果", "",
        "表格列为：样本数 / 继续率 / 停止率 / 明确正效用召回 / 明确正效用误停 / 边界数 / 总 regret。", "",
    ]
    if data["summary"] is None:
        lines.extend(["## 样本量预检", "", "| 分区 | 节点 | 样本数 | 当前正式停止数 | 旧B_global停止数 | 旧B_stage停止数 | 新覆盖层停止数 |", "|---|---|---:|---:|---:|---:|---:|"])
        for partition in ("development", "frozen_validation"):
            for checkpoint in (0, 3):
                row = data["preflight_population"][partition][f"plus{checkpoint}"]
                stops = row["strategy_stop_counts"]
                lines.append(f"| {partition} | +{checkpoint} | {row['sample_count']} | {stops['current_formal']} | {stops['B_global_current_gs']} | {stops['B_stage_conversion']} | {stops['safe_negative_cover']} |")
        lines.extend(["", "- 样本量预检失败发生在 Oracle 之前：因此没有 Oracle 召回、误停、regret，也没有每10万体力产量。将这些未计算项目填零会造成错误结论。", ""])
    else:
        for partition in ("development", "frozen_validation"):
            lines.extend([f"### {partition}", "", "| 节点 | 当前正式 | 旧 B_global | 旧 B_stage_conversion | 新安全覆盖层 |", "|---|---|---|---|---|"])
            for checkpoint in (0, 3):
                row = data["summary"][partition][f"plus{checkpoint}"]
                lines.append(f"| +{checkpoint} | {_cell(row['current_formal'])} | {_cell(row['B_global_current_gs'])} | {_cell(row['B_stage_conversion'])} | {_cell(row['safe_negative_cover'])} |")
            lines.append("")
    gate = data["release_gate"]
    lines.extend(["## 发布闸门", ""])
    for reason in gate["reasons"] or ["全部 per-item 闸门已通过，仍需执行五 seed 联合资源池后才可创建新批次。"]:
        lines.append(f"- {reason}")
    lines.extend([
        "", "## 联合资源池", "",
        "- 状态：未运行。联合资源池要求五个独立 seed、维度裂缝 Epic/Heroic 联合批次、圣女3-7瓶颈补充，并冻结 Heroic 基础回退+M1。",
        "- 原因：+0/+3 每个节点必须先有足够的冻结 Oracle 样本并实现零明确正效用误停；本轮不能用仅 4 件的 +3 样本、历史盲测或合成覆盖强行推导每十万体力的正式百里分、75+、22+、裂缝/圣女体力和循环数。", "",
        "## 规则", "",
        "| 节点 | 有效GS不高于 | 当前有效词条不超过 | 终局正式达标概率不高于 | 合法转换价值不高于 |", "|---|---:|---:|---:|---:|",
    ])
    for point, rule in SAFE_STOP_RULES.items():
        lines.append(f"| +{point} | {rule.effective_gs_max:g} | {rule.current_valid_max} | {rule.terminal_probability_max:.3f} | {rule.conversion_value_max:g} |")
    if data["summary"] is None:
        lines.extend(["", "同名 JSON 只保存预检分割、规则与停止计数；本轮没有逐件 Oracle 结果。", ""])
    else:
        lines.extend(["", "逐件 Oracle、特征、节点成本、动作与分割见同名 JSON。", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a frozen high-confidence Epic stop cover.")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / f"{STUDY_ID}.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / f"{STUDY_ID}.md")
    args = parser.parse_args(argv)
    data = run(args.records, workers=max(1, args.workers))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
