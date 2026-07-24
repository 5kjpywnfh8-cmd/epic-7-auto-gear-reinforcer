"""Two-stage offline Epic early-stop study with exact official +3 branches.

Development uses only the frozen 174 real +0 inputs.  Validation requires a
previously written candidate file and uses only the separate 99 real +0 inputs.
No production policy is imported or changed by this tool.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.models import Gear
from src.e7_enhance.calibration import DP_ASSIST_CONFIGS
from src.e7_enhance.route_solver import compute_optimal_route, marginal_net_stamina_cost
from tools.epic_non_speed_dp_oracle_audit import NUMERIC_ZERO_TOLERANCE, collect_audit_cases
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, _speed_hard_route
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_epic_stage_balanced import stage_features


STUDY_ID = "epic_exact_plus3_official_branches_20260717"
SCHEMA_VERSION = 1
EPSILON = NUMERIC_ZERO_TOLERANCE * 64
# The earlier +0 preflight compared ``gear.slot != "Boots"`` after slot
# normalization and accidentally retained 24 boots.  This study's explicit
# non-boot scope yields the corrected, independently split real population.
DEVELOPMENT_EXPECTED_COUNT = 157
FROZEN_EXPECTED_COUNT = 92
DEFAULT_RECORDS = ROOT / "manual_acceptance" / "real_sample_records.json"
DEFAULT_CANDIDATE = ROOT / "reports" / "epic_exact_plus3_candidate_20260717.json"
DEFAULT_DEVELOPMENT_JSON = ROOT / "reports" / "epic_exact_plus3_development_20260717.json"
DEFAULT_DEVELOPMENT_REPORT = ROOT / "reports" / "epic_exact_plus3_development_20260717.md"
DEFAULT_VALIDATION_JSON = ROOT / "reports" / "epic_exact_plus3_validation_20260717.json"
DEFAULT_VALIDATION_REPORT = ROOT / "reports" / "epic_exact_plus3_validation_20260717.md"
DEFAULT_RESUME_DIR = ROOT / "reports" / "epic_exact_plus3_resume_20260717"

# Frozen before inspecting the development Oracle labels.  The rule remains a
# shallow current-state conjunction and only changes continue -> stop.
RULE_GRID = {
    "effective_gs_max": (6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0),
    "current_valid_max": (0, 1, 2),
    "terminal_probability_max": (0.0, 0.002, 0.005, 0.01, 0.02, 0.04, 0.08),
    "conversion_value_max": (0.0, 3.0, 6.0, 9.0),
}


@dataclass(frozen=True)
class SafeStopRule:
    effective_gs_max: float
    current_valid_max: int
    terminal_probability_max: float
    conversion_value_max: float


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return sha256(_stable_json(value).encode("utf-8")).hexdigest()


def split_name(sample_id: str) -> str:
    return "development" if int(sha256(sample_id.encode("utf-8")).hexdigest()[0], 16) < 10 else "frozen_validation"


def oracle_label(margin: float) -> str:
    if margin > EPSILON:
        return "clear_positive"
    if margin < -EPSILON:
        return "clear_negative"
    return "boundary"


def _speed_value(gear: Gear) -> float:
    return float(next((stat.normalized_value for stat in gear.substats if stat.key == "spd"), 0.0))


def in_scope(gear: Gear, raw: dict[str, Any]) -> bool:
    return (
        gear.rank == "Epic"
        and gear.level == 85
        and gear.enhance == 0
        and gear.slot != "boot"
        and str(raw.get("itemSource") or raw.get("item_source") or "normal_85") == "normal_85"
        and _speed_value(gear) < 2
        and not _speed_hard_route(gear)
        and len(gear.substats) == 4
    )


def _historical_instance_ids(data: dict[str, Any]) -> set[str]:
    linked = collect_audit_cases(records_payload=data)
    return {str(row["instance_id"]) for row in linked["included"]}


def load_real_plus0(records_path: Path, partition: str) -> list[dict[str, Any]]:
    """Load only one partition's real +0 states; no +3 observation is needed."""
    if partition not in {"development", "frozen_validation"}:
        raise ValueError(f"unknown partition: {partition}")
    data = json.loads(Path(records_path).read_text(encoding="utf-8"))
    historical_ids = _historical_instance_ids(data)
    rows: list[dict[str, Any]] = []
    seen_instances: set[str] = set()
    for record in data.get("records") or []:
        sample_id = str(record.get("sample_id") or "")
        if not sample_id or split_name(sample_id) != partition:
            continue
        for snapshot in record.get("snapshots") or []:
            raw = dict(snapshot.get("gear") or {})
            instance_id = str(raw.get("instanceId") or raw.get("instance_id") or "")
            if not instance_id or instance_id in historical_ids or instance_id in seen_instances:
                continue
            try:
                gear = Gear.from_dict(raw)
            except (KeyError, TypeError, ValueError):
                continue
            if not in_scope(gear, raw):
                continue
            seen_instances.add(instance_id)
            rows.append({
                "sample_id": sample_id,
                "snapshot_id": str(snapshot.get("snapshot_id") or ""),
                "instance_id": instance_id,
                "gear": gear.to_dict(),
                "gear_source": str(raw.get("gearSource") or raw.get("gear_source") or ""),
            })
    return sorted(rows, key=lambda row: (row["sample_id"], row["snapshot_id"], row["instance_id"]))


def _formal_action(gear: Gear, gear_source: str) -> str:
    recommendation = str(advise_gear(gear, item_source="normal_85", gear_source=gear_source)["summary"]["recommendation"])
    return "stop" if recommendation == "stop" else "continue"


def _state_payload(base: dict[str, Any], *, checkpoint: int, probability: float, gear: Gear, branch: dict[str, Any] | None = None) -> dict[str, Any]:
    suffix = "base" if branch is None else f"t{branch['target_index']}:d{branch['delta']}"
    return {
        "state_id": f"{base['sample_id']}:{base['snapshot_id']}:{suffix}",
        "sample_id": base["sample_id"],
        "snapshot_id": base["snapshot_id"],
        "instance_id": base["instance_id"],
        "checkpoint": checkpoint,
        "weight": float(probability),
        "gear": gear.to_dict(),
        "gear_source": base["gear_source"],
        "branch": branch,
    }


def plus0_states(base_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_state_payload(row, checkpoint=0, probability=1.0, gear=Gear.from_dict(row["gear"])) for row in base_rows]


def plus3_states(base_rows: Iterable[dict[str, Any]], plus0_rule: SafeStopRule | None) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for base in base_rows:
        gear = Gear.from_dict(base["gear"])
        # +3 exists only along the candidate's +0 continue path.
        current = _formal_action(gear, base["gear_source"])
        feature = _feature_view(gear)
        if action_for_rule(current, feature, plus0_rule) == "stop":
            continue
        for branch in enumerate_normal_epic_plus3(gear):
            states.append(_state_payload(
                base,
                checkpoint=3,
                probability=branch.probability,
                gear=branch.gear,
                branch={"target_index": branch.target_index, "target_key": branch.target_key, "delta": branch.delta},
            ))
    return states


def _feature_view(gear: Gear) -> dict[str, Any]:
    raw = stage_features(gear)
    return {
        "effective_gs": float(raw["effective_gs"]),
        "current_valid": int(raw["current_valid"]),
        "probability": float(raw["probability"]),
        "conversion_value": float(raw["conversion_value"]),
        "category": str(raw.get("category") or "未命中"),
    }


def _evaluate_state(state: dict[str, Any]) -> dict[str, Any]:
    gear = Gear.from_dict(state["gear"])
    lambda_value = 1.0 / float(DP_ASSIST_CONFIGS[("normal_85", "Epic")]["cost_per_baili_score"])
    route = compute_optimal_route(
        gear,
        lambda_value,
        item_source="normal_85",
        gear_source=GEAR_SOURCE,
        rank="Epic",
    )
    next_checkpoint = int(route["next_checkpoint"])
    margin = float(route["continue_utility"]) - float(route["stop_utility"])
    oracle = {
        "oracle_type": "exact_dp_route_once",
        "utility_margin": margin,
        "next_checkpoint": next_checkpoint,
        # This study measures the saved decision commitment: the next actual
        # enhancement node, not a speculative forced full path.
        "forced_continue_stamina": marginal_net_stamina_cost(gear.enhance, next_checkpoint, gear.rank, gear.slot),
    }
    return {
        **state,
        "features": _feature_view(gear),
        "current_action": _formal_action(gear, str(state["gear_source"])),
        "oracle": oracle,
        "oracle_label": oracle_label(float(oracle["utility_margin"])),
    }


def evaluate_states(states: list[dict[str, Any]], workers: int) -> list[dict[str, Any]]:
    if workers > 1 and len(states) > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            rows = list(executor.map(_evaluate_state, states))
    else:
        rows = [_evaluate_state(state) for state in states]
    return sorted(rows, key=lambda row: row["state_id"])


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _shard_input_hash(states: list[dict[str, Any]]) -> str:
    return _sha(states)


def _shard_path(resume_dir: Path, partition: str, node: str, sample_id: str) -> Path:
    return resume_dir / partition / node / f"{sha256(sample_id.encode('utf-8')).hexdigest()}.json"


def _valid_shard(path: Path, *, partition: str, node: str, input_hash: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        payload.get("status") == "complete"
        and payload.get("study") == STUDY_ID
        and payload.get("schema_version") == SCHEMA_VERSION
        and payload.get("partition") == partition
        and payload.get("node") == node
        and payload.get("input_sha256") == input_hash
        and isinstance(payload.get("rows"), list)
    )


def _evaluate_shard(job: dict[str, Any]) -> str:
    rows = [_evaluate_state(state) for state in job["states"]]
    payload = {
        "status": "complete",
        "study": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "partition": job["partition"],
        "node": job["node"],
        "sample_id": job["sample_id"],
        "input_sha256": job["input_hash"],
        "rows": rows,
    }
    _atomic_json(Path(job["path"]), payload)
    return str(job["path"])


def evaluate_cached(
    states: list[dict[str, Any]],
    *,
    resume_dir: Path,
    partition: str,
    node: str,
    workers: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Evaluate whole real-item groups atomically so an interrupted run resumes."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for state in states:
        groups.setdefault(str(state["sample_id"]), []).append(state)
    paths: dict[str, tuple[Path, str]] = {}
    jobs: list[dict[str, Any]] = []
    reused = 0
    for sample_id, group in sorted(groups.items()):
        group = sorted(group, key=lambda row: row["state_id"])
        input_hash = _shard_input_hash(group)
        path = _shard_path(resume_dir, partition, node, sample_id)
        paths[sample_id] = (path, input_hash)
        if _valid_shard(path, partition=partition, node=node, input_hash=input_hash):
            reused += 1
            continue
        jobs.append({
            "states": group,
            "partition": partition,
            "node": node,
            "sample_id": sample_id,
            "input_hash": input_hash,
            "path": str(path),
        })
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_evaluate_shard, jobs))
    else:
        for job in jobs:
            _evaluate_shard(job)
    rows: list[dict[str, Any]] = []
    for sample_id, (path, input_hash) in sorted(paths.items()):
        if not _valid_shard(path, partition=partition, node=node, input_hash=input_hash):
            raise RuntimeError(f"missing or invalid exact-DP shard for {sample_id}")
        rows.extend(json.loads(path.read_text(encoding="utf-8"))["rows"])
    return sorted(rows, key=lambda row: row["state_id"]), {"groups": len(groups), "reused": reused, "computed": len(jobs)}


def action_for_rule(current_action: str, features: dict[str, Any], rule: SafeStopRule | None) -> str:
    """A candidate may only add a stop to a released continue decision."""
    if current_action == "stop" or rule is None:
        return current_action
    if (
        float(features["effective_gs"]) <= rule.effective_gs_max
        and int(features["current_valid"]) <= rule.current_valid_max
        and float(features["probability"]) <= rule.terminal_probability_max
        and float(features["conversion_value"]) <= rule.conversion_value_max
    ):
        return "stop"
    return current_action


def weighted_metrics(rows: Iterable[dict[str, Any]], rule: SafeStopRule | None) -> dict[str, Any]:
    rows = list(rows)
    total_weight = sum(float(row["weight"]) for row in rows)
    positive = [row for row in rows if row["oracle_label"] == "clear_positive"]
    negative = [row for row in rows if row["oracle_label"] == "clear_negative"]
    boundary = [row for row in rows if row["oracle_label"] == "boundary"]
    actions = [(row, action_for_rule(str(row["current_action"]), row["features"], rule)) for row in rows]
    stopped = [(row, action) for row, action in actions if action == "stop"]
    false_stops = [row for row in positive if action_for_rule(str(row["current_action"]), row["features"], rule) == "stop"]
    false_continues = [row for row in negative if action_for_rule(str(row["current_action"]), row["features"], rule) != "stop"]
    regret = sum(
        float(row["weight"]) * (
            max(0.0, float(row["oracle"]["utility_margin"])) if action == "stop"
            else max(0.0, -float(row["oracle"]["utility_margin"]))
        )
        for row, action in actions if row["oracle_label"] != "boundary"
    )
    positive_weight = sum(float(row["weight"]) for row in positive)
    false_stop_weight = sum(float(row["weight"]) for row in false_stops)
    return {
        "raw_state_count": len(rows),
        "distinct_real_plus0_count": len({str(row["instance_id"]) for row in rows}),
        "state_weight": total_weight,
        "stopped_state_count": len(stopped),
        "stopped_weight": sum(float(row["weight"]) for row, _action in stopped),
        "continue_weight": total_weight - sum(float(row["weight"]) for row, _action in stopped),
        "clear_positive_state_count": len(positive),
        "clear_positive_weight": positive_weight,
        "clear_negative_state_count": len(negative),
        "clear_negative_weight": sum(float(row["weight"]) for row in negative),
        "boundary_state_count": len(boundary),
        "boundary_weight": sum(float(row["weight"]) for row in boundary),
        "clear_positive_false_stop_count": len(false_stops),
        "clear_positive_false_stop_weight": false_stop_weight,
        "clear_positive_recall": 1.0 - false_stop_weight / positive_weight if positive_weight else 1.0,
        "clear_negative_false_continue_weight": sum(float(row["weight"]) for row in false_continues),
        "total_regret": regret,
        "saved_next_node_stamina": sum(float(row["weight"]) * float(row["oracle"]["forced_continue_stamina"]) for row, _action in stopped),
    }


def _rules() -> Iterable[SafeStopRule]:
    for gs in RULE_GRID["effective_gs_max"]:
        for valid in RULE_GRID["current_valid_max"]:
            for probability in RULE_GRID["terminal_probability_max"]:
                for conversion in RULE_GRID["conversion_value_max"]:
                    yield SafeStopRule(gs, valid, probability, conversion)


def select_rule(development_rows: list[dict[str, Any]]) -> tuple[SafeStopRule | None, dict[str, Any]]:
    baseline = weighted_metrics(development_rows, None)
    eligible: list[tuple[SafeStopRule, dict[str, Any]]] = []
    for rule in _rules():
        metrics = weighted_metrics(development_rows, rule)
        if not metrics["stopped_weight"]:
            continue
        if metrics["clear_positive_false_stop_count"]:
            continue
        if metrics["total_regret"] > baseline["total_regret"] + EPSILON:
            continue
        eligible.append((rule, metrics))
    if not eligible:
        return None, {"selection": "no_safe_stop_rule", "baseline": baseline, "candidate": baseline}
    rule, metrics = max(
        eligible,
        key=lambda row: (row[1]["saved_next_node_stamina"], -row[1]["total_regret"], -row[0].effective_gs_max, -row[0].terminal_probability_max),
    )
    return rule, {"selection": "maximum_saved_stamina_zero_positive_false_stops", "baseline": baseline, "candidate": metrics, "eligible_rule_count": len(eligible)}


def _candidate_payload(plus0_rule: SafeStopRule | None, plus3_rule: SafeStopRule | None, development: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "study": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "epsilon": EPSILON,
        "target_selection": {"probability": 0.25, "basis": "装备强化与评分规则审阅.md: existing-substat event selects each of n current substats with probability 1/n"},
        "jump_probability_source": "STOVE装备概率资料核对记录.md; local displayed probabilities normalized per stat",
        "rule_grid": RULE_GRID,
        "rules": {"plus0": asdict(plus0_rule) if plus0_rule else None, "plus3": asdict(plus3_rule) if plus3_rule else None},
        "development_sample_ids": sorted({row["sample_id"] for row in development["plus0_rows"]}),
        "development_selection": development["selection"],
    }
    payload["candidate_sha256"] = _sha(payload)
    return payload


def _parse_rule(payload: Any) -> SafeStopRule | None:
    return SafeStopRule(**payload) if isinstance(payload, dict) else None


def _validate_candidate(candidate: dict[str, Any]) -> None:
    supplied_hash = str(candidate.get("candidate_sha256") or "")
    body = {key: value for key, value in candidate.items() if key != "candidate_sha256"}
    if candidate.get("study") != STUDY_ID or candidate.get("schema_version") != SCHEMA_VERSION or supplied_hash != _sha(body):
        raise ValueError("candidate file is incompatible or has been modified")
    if float(candidate.get("epsilon")) != EPSILON:
        raise ValueError("candidate epsilon does not match the frozen study epsilon")


def _summary(plus0_rows: list[dict[str, Any]], plus3_rows: list[dict[str, Any]], plus0_rule: SafeStopRule | None, plus3_rule: SafeStopRule | None) -> dict[str, Any]:
    return {
        "plus0": {"current_formal": weighted_metrics(plus0_rows, None), "candidate": weighted_metrics(plus0_rows, plus0_rule)},
        "plus3": {"current_formal": weighted_metrics(plus3_rows, None), "candidate": weighted_metrics(plus3_rows, plus3_rule)},
    }


def _gate(summary: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    for node in ("plus0", "plus3"):
        candidate = summary[node]["candidate"]
        baseline = summary[node]["current_formal"]
        if candidate["clear_positive_false_stop_count"]:
            reasons.append(f"{node} 存在 {candidate['clear_positive_false_stop_count']} 个明确正效用误停分支。")
        if candidate["total_regret"] > baseline["total_regret"] + EPSILON:
            reasons.append(f"{node} 总 regret 高于当前正式策略。")
        if candidate["saved_next_node_stamina"] <= 0:
            reasons.append(f"{node} 未节省下一节点强化资源。")
    return {
        "passed": not reasons,
        "decision": "允许进入五 seed 联合资源池" if not reasons else "不运行联合资源池，正式Epic策略保持不变",
        "reasons": reasons,
        "joint_pool": {"status": "pending_after_node_gate" if not reasons else "not_run_precondition_failed"},
    }


def development_run(records_path: Path, workers: int, resume_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    base = load_real_plus0(records_path, "development")
    if len(base) != DEVELOPMENT_EXPECTED_COUNT:
        raise ValueError(f"expected {DEVELOPMENT_EXPECTED_COUNT} independent development +0 items, got {len(base)}")
    plus0_rows, plus0_resume = evaluate_cached(
        plus0_states(base), resume_dir=resume_dir, partition="development", node="plus0", workers=workers,
    )
    plus0_rule, plus0_selection = select_rule(plus0_rows)
    plus3_node = f"plus3-{_sha(asdict(plus0_rule) if plus0_rule else {'rule': None})[:16]}"
    plus3_rows, plus3_resume = evaluate_cached(
        plus3_states(base, plus0_rule), resume_dir=resume_dir, partition="development", node=plus3_node, workers=workers,
    )
    plus3_rule, plus3_selection = select_rule(plus3_rows)
    development = {"plus0_rows": plus0_rows, "plus3_rows": plus3_rows, "selection": {"plus0": plus0_selection, "plus3": plus3_selection}}
    candidate = _candidate_payload(plus0_rule, plus3_rule, development)
    result = {
        "study": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "phase": "development_only",
        "data_isolation": {"partition": "development", "real_plus0_count": len(base), "frozen_validation_read": False, "old_oracle_and_blind_instances_excluded": True},
        "probability_model": {"jump_source": candidate["jump_probability_source"], "target_selection": candidate["target_selection"], "downstream_note": "Only +0->+3 is replaced by official discrete branches; released +6+ DP remains frozen."},
        "candidate": candidate,
        "summary": _summary(plus0_rows, plus3_rows, plus0_rule, plus3_rule),
        "branch_counts": {"plus0": len(plus0_rows), "plus3": len(plus3_rows), "plus3_probability_mass": sum(float(row["weight"]) for row in plus3_rows)},
        "resume": {"directory": str(resume_dir.relative_to(ROOT)), "plus0": plus0_resume, "plus3": plus3_resume},
    }
    return result, candidate


def validation_run(records_path: Path, candidate: dict[str, Any], workers: int, resume_dir: Path) -> dict[str, Any]:
    _validate_candidate(candidate)
    base = load_real_plus0(records_path, "frozen_validation")
    if len(base) != FROZEN_EXPECTED_COUNT:
        raise ValueError(f"expected {FROZEN_EXPECTED_COUNT} independent frozen +0 items, got {len(base)}")
    plus0_rule = _parse_rule((candidate.get("rules") or {}).get("plus0"))
    plus3_rule = _parse_rule((candidate.get("rules") or {}).get("plus3"))
    plus0_rows, plus0_resume = evaluate_cached(
        plus0_states(base), resume_dir=resume_dir, partition="frozen_validation", node="plus0", workers=workers,
    )
    plus3_node = f"plus3-{_sha(asdict(plus0_rule) if plus0_rule else {'rule': None})[:16]}"
    plus3_rows, plus3_resume = evaluate_cached(
        plus3_states(base, plus0_rule), resume_dir=resume_dir, partition="frozen_validation", node=plus3_node, workers=workers,
    )
    summary = _summary(plus0_rows, plus3_rows, plus0_rule, plus3_rule)
    return {
        "study": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "phase": "frozen_validation",
        "data_isolation": {"partition": "frozen_validation", "real_plus0_count": len(base), "candidate_sha256": candidate["candidate_sha256"], "candidate_was_loaded_before_frozen_oracle": True},
        "probability_model": {"jump_source": candidate["jump_probability_source"], "target_selection": candidate["target_selection"], "downstream_note": "Only +0->+3 is replaced by official discrete branches; released +6+ DP remains frozen."},
        "candidate": candidate,
        "summary": summary,
        "branch_counts": {"plus0": len(plus0_rows), "plus3": len(plus3_rows), "plus3_probability_mass": sum(float(row["weight"]) for row in plus3_rows)},
        "resume": {"directory": str(resume_dir.relative_to(ROOT)), "plus0": plus0_resume, "plus3": plus3_resume},
        "release_gate": _gate(summary),
    }


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Epic 非速度 +0/+3 官方概率精确分支研究（2026-07-17）", "",
        "## 方法", "",
        "- 使用真实 +0 装备作为胚子分布；装备已出售不影响其条件期望。",
        "- +3 是每件真实 +0 的官方概率加权合法分支，不是等权合成装备，也不是实际观察到的 +3 样本。",
        "- 仅第一段 +0->+3 使用 STOVE 离散概率；+6 以后继续使用冻结的正式 Epic DP。", "",
        "## 数据隔离", "",
        f"- 阶段：`{result['phase']}`。真实 +0 数量：`{result['data_isolation']['real_plus0_count']}`。",
        f"- {result['data_isolation']}", "",
        "## 节点结果", "",
        "| 节点 | 口径 | 实际状态数 | 权重质量 | 停止权重 | 明确正效用误停 | 正效用召回 | regret | 节省下一节点体力 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for node in ("plus0", "plus3"):
        for label in ("current_formal", "candidate"):
            metric = result["summary"][node][label]
            lines.append(
                f"| {node} | {label} | {metric['raw_state_count']} | {metric['state_weight']:.6f} | {metric['stopped_weight']:.6f} | {metric['clear_positive_false_stop_count']} | {metric['clear_positive_recall']:.2%} | {metric['total_regret']:.8f} | {metric['saved_next_node_stamina']:.4f} |"
            )
    if result["phase"] == "development_only":
        lines.extend(["", "## 候选冻结", "", f"- 候选哈希：`{result['candidate']['candidate_sha256']}`。冻结验证组尚未读取。"])
    else:
        gate = result["release_gate"]
        lines.extend(["", "## 闸门", "", f"- {gate['decision']}。"])
        lines.extend(f"- {reason}" for reason in gate["reasons"])
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact official +3 branch study for real normal Epic +0 states")
    parser.add_argument("--phase", choices=("development", "validate"), required=True)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--resume-dir", type=Path, default=DEFAULT_RESUME_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    workers = max(1, int(args.workers))
    if args.phase == "development":
        result, candidate = development_run(args.records, workers, args.resume_dir)
        _write_json(args.candidate, candidate)
        output = args.output or DEFAULT_DEVELOPMENT_JSON
        report = args.report or DEFAULT_DEVELOPMENT_REPORT
    else:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        result = validation_run(args.records, candidate, workers, args.resume_dir)
        output = args.output or DEFAULT_VALIDATION_JSON
        report = args.report or DEFAULT_VALIDATION_REPORT
    _write_json(output, result)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"output": str(output), "report": str(report), "phase": result["phase"], "candidate": str(args.candidate)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
