"""Frozen Holdout validation for the selected Epic early policy candidate.

The tool reads only the immutable candidate freeze, collection and 64/64
manifest. Development and frozen-validation cohorts are evaluated separately;
no result is fed back into candidate thresholds or production configuration.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.calibration import DP_ASSIST_CONFIGS
from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from src.e7_enhance.route_solver import compute_optimal_route
from src.e7_enhance import epic_balanced_holdout as holdout
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools import research_epic_threshold_matrix_phase_c as phase_c
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow
from tools.epic_non_speed_dp_oracle_audit import NUMERIC_ZERO_TOLERANCE
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, _speed_hard_route, _source_rank_gears
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_riftslash_saint_pool import YIELD_VARIATIONS, explicit_batch_resource_pool


FREEZE = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_freeze_20260718.json"
COLLECTION = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_collection_20260718.json"
MANIFEST = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_manifest_20260718.json"
SOURCE = ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json"
FORMAL_PHASE_B_REPORT = ROOT / "reports" / "epic_threshold_matrix_phase_b_formal_r10_20260718.json"
RESUME = ROOT / "reports" / "epic_output_8_13_tank_10_17_holdout_validation_resume_20260719"
JSON_OUTPUT = ROOT / "reports" / "epic_output_8_13_tank_10_17_holdout_validation_20260719.json"
REPORT_OUTPUT = ROOT / "reports" / "epic_output_8_13_tank_10_17_holdout_validation_20260719.md"
CURRENT_KEY = "current_formal"
CANDIDATE_KEY = "output_8_13_tank_10_17"
RUNS = 10
EPSILON = NUMERIC_ZERO_TOLERANCE * 64
HIGH_LOSS_MARGIN = 0.01


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _candidate_rule() -> phase_c.Rule:
    matches = [rule for rule in phase_c.RULES if rule.key == CANDIDATE_KEY]
    if len(matches) != 1:
        raise RuntimeError(f"frozen candidate not found: {CANDIDATE_KEY}")
    return matches[0]


def audit_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    freeze = _read(FREEZE)
    collection = _read(COLLECTION)
    manifest = _read(MANIFEST)
    if freeze.get("status") != "candidate_frozen" or freeze.get("candidate", {}).get("key") != CANDIDATE_KEY:
        raise RuntimeError("candidate freeze does not match the selected Holdout candidate")
    if holdout._candidate_hash() != freeze["candidate"]["candidate_hash"]:
        raise RuntimeError("candidate hash drifted after freeze")
    if holdout._freeze_sha(freeze) != collection.get("freeze_sha256"):
        raise RuntimeError("collection freeze hash mismatch")
    if collection.get("status") != "ready_for_frozen_validation":
        raise RuntimeError(f"collection is not ready for validation: {collection.get('status')}")
    if manifest.get("status") != "immutable_64_64_manifest" or manifest.get("freeze_sha256") != holdout._freeze_sha(freeze):
        raise RuntimeError("manifest is not an immutable match for the candidate freeze")
    if manifest.get("collection_sha256") != holdout._manifest_source_hash(collection):
        raise RuntimeError("manifest source collection hash mismatch")
    included = list(manifest.get("included") or [])
    if len(included) != 128:
        raise RuntimeError(f"manifest item count is not 128: {len(included)}")
    groups = Counter(str(row.get("group")) for row in included)
    if groups != Counter({"development": 64, "frozen_validation": 64}):
        raise RuntimeError(f"manifest is not 64/64: {dict(groups)}")
    sample_ids = [str(row.get("sample_id")) for row in included]
    if len(set(sample_ids)) != 128:
        raise RuntimeError("manifest contains duplicate sample IDs")
    by_id = {str(row["sample_id"]): row for row in collection.get("snapshots") or []}
    if set(sample_ids) != set(by_id):
        raise RuntimeError("manifest and collection sample IDs differ")
    current_hashes = holdout._frozen_hashes()
    if current_hashes != freeze.get("frozen_hashes"):
        raise RuntimeError("frozen implementation hashes drifted")
    return freeze, collection, manifest, {"groups": dict(groups), "sample_count": len(sample_ids), "frozen_hashes": current_hashes}


def load_partition(collection: dict[str, Any], manifest: dict[str, Any], partition: str) -> list[dict[str, Any]]:
    by_id = {str(row["sample_id"]): row for row in collection["snapshots"]}
    rows: list[dict[str, Any]] = []
    for entry in manifest["included"]:
        if entry["group"] != partition:
            continue
        snapshot = by_id[str(entry["sample_id"])]
        raw = dict(snapshot["gear"])
        gear = Gear.from_dict(raw)
        if not (
            gear.rank == "Epic" and gear.level == 85 and gear.enhance == 0 and gear.slot != "boot"
            and str(raw.get("itemSource") or raw.get("item_source") or "") == "normal_85"
            and len(gear.substats) == 4 and not _speed_hard_route(gear)
        ):
            raise RuntimeError(f"manifest item is outside frozen scope: {snapshot['instance_id']}")
        rows.append({
            "sample_id": str(snapshot["sample_id"]),
            "instance_id": str(snapshot["instance_id"]),
            "fingerprint": str(snapshot["fingerprint"]),
            "exported_at": str(snapshot["exported_at"]),
            "gear": gear.to_dict(),
        })
    return sorted(rows, key=lambda row: (row["sample_id"], row["instance_id"]))


def _oracle(gear: Gear) -> dict[str, Any]:
    lambda_value = 1.0 / float(DP_ASSIST_CONFIGS[("normal_85", "Epic")]["cost_per_baili_score"])
    route = compute_optimal_route(gear, lambda_value, item_source="normal_85", gear_source=GEAR_SOURCE, rank="Epic")
    margin = float(route["continue_utility"]) - float(route["stop_utility"])
    label = "clear_positive" if margin > EPSILON else "clear_negative" if margin < -EPSILON else "boundary"
    return {
        "oracle_type": "exact_dp_route_once",
        "action": "continue" if margin > EPSILON else "stop",
        "label": label,
        "utility_margin": margin,
        "next_checkpoint": int(route["next_checkpoint"]),
        "stop_utility": float(route["stop_utility"]),
        "continue_utility": float(route["continue_utility"]),
    }


def _formal_action(gear: Gear) -> str:
    return phase_b._formal_action(gear, GEAR_SOURCE)


def _action(gear: Gear, rule: phase_c.Rule | None) -> str:
    formal = _formal_action(gear)
    if rule is None:
        return formal
    return phase_c.action(formal, gear.enhance, phase_b.selected_candidate_snapshot(gear), rule)


def _features(gear: Gear) -> dict[str, Any]:
    return phase_b.selected_candidate_snapshot(gear)


def _branch_rows(base: dict[str, Any]) -> list[dict[str, Any]]:
    gear = Gear.from_dict(base["gear"])
    rows: list[dict[str, Any]] = []
    for branch_index, branch in enumerate(enumerate_normal_epic_plus3(gear)):
        branch_gear = branch.gear
        rows.append({
            "branch_index": branch_index,
            "target_index": int(branch.target_index),
            "target_key": str(branch.target_key),
            "delta": int(branch.delta),
            "probability": float(branch.probability),
            "gear": branch_gear.to_dict(),
            "features": _features(branch_gear),
            "current_action": _action(branch_gear, None),
            "candidate_action": _action(branch_gear, _candidate_rule()),
            "oracle": _oracle(branch_gear),
        })
    probability_sum = sum(float(row["probability"]) for row in rows)
    if abs(probability_sum - 1.0) > 1e-10:
        raise RuntimeError(f"official +3 probability does not sum to 1: {probability_sum}")
    return rows


def evaluate_item(row: dict[str, Any]) -> dict[str, Any]:
    gear = Gear.from_dict(row["gear"])
    return {
        **row,
        "features": _features(gear),
        "formal_action": _formal_action(gear),
        "current_action": _action(gear, None),
        "candidate_action": _action(gear, _candidate_rule()),
        "oracle": _oracle(gear),
        "plus3_branches": _branch_rows(row),
    }


def _evaluation_shard_path(partition: str, sample_id: str) -> Path:
    return RESUME / "evaluated" / partition / f"{sha256(sample_id.encode('utf-8')).hexdigest()}.json"


def _evaluation_input_hash(row: dict[str, Any], partition: str) -> str:
    return _sha({
        "study": "epic_balanced_holdout_validation_20260719",
        "partition": partition,
        "sample_id": row["sample_id"],
        "gear": row["gear"],
        "candidate_hash": holdout._candidate_hash(),
    })


def evaluate_partition(rows: list[dict[str, Any]], partition: str, workers: int) -> list[dict[str, Any]]:
    evaluated: dict[str, dict[str, Any]] = {}
    jobs: list[dict[str, Any]] = []
    for row in rows:
        sample_id = str(row["sample_id"])
        path = _evaluation_shard_path(partition, sample_id)
        expected_hash = _evaluation_input_hash(row, partition)
        if path.exists():
            payload = _read(path)
            if payload.get("status") == "complete" and payload.get("input_hash") == expected_hash:
                evaluated[sample_id] = payload
                continue
        jobs.append({**row, "input_hash": expected_hash})

    def save(job: dict[str, Any], result: dict[str, Any]) -> None:
        sample_id = str(job["sample_id"])
        payload = {"status": "complete", "schema_version": 1, "input_hash": job["input_hash"], **result}
        _write_json(_evaluation_shard_path(partition, sample_id), payload)
        evaluated[sample_id] = payload

    if workers > 1 and jobs:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(evaluate_item, job): job for job in jobs}
            for future in as_completed(futures):
                save(futures[future], future.result())
    else:
        for job in jobs:
            save(job, evaluate_item(job))
    return sorted(evaluated.values(), key=lambda row: row["sample_id"])


def _binary(action: str) -> bool:
    return str(action) != "stop"


def _metric_rows(rows: list[dict[str, Any]], *, candidate_key: str, checkpoint: int) -> list[dict[str, Any]]:
    action_field = "current_action" if candidate_key == CURRENT_KEY else "candidate_action"
    if checkpoint == 0:
        return [{"weight": 1.0, "action": row[action_field], "oracle": row["oracle"], "features": row["features"], "instance_id": row["instance_id"]} for row in rows]
    output: list[dict[str, Any]] = []
    for row in rows:
        if not _binary(row[action_field]):
            continue
        for branch in row["plus3_branches"]:
            branch_action = branch["current_action"] if candidate_key == CURRENT_KEY else branch["candidate_action"]
            output.append({"weight": float(branch["probability"]), "action": branch_action, "oracle": branch["oracle"], "features": branch["features"], "instance_id": row["instance_id"]})
    return output


def metrics(rows: list[dict[str, Any]], *, candidate_key: str, checkpoint: int) -> dict[str, Any]:
    states = _metric_rows(rows, candidate_key=candidate_key, checkpoint=checkpoint)
    positive_weight = sum(float(s["weight"]) for s in states if s["oracle"]["label"] == "clear_positive")
    false_stops = [s for s in states if s["oracle"]["label"] == "clear_positive" and not _binary(s["action"])]
    false_enhances = [s for s in states if s["oracle"]["label"] == "clear_negative" and _binary(s["action"])]
    regret = 0.0
    for state in states:
        margin = float(state["oracle"]["utility_margin"])
        if state["oracle"]["label"] == "boundary":
            continue
        if _binary(state["action"]) != _binary(state["oracle"]["action"]):
            regret += float(state["weight"]) * abs(margin)
    false_stop_by_group = Counter(str(s["features"].get("system_group", "unknown")) for s in false_stops)
    return {
        "state_count": len(states),
        "state_weight": sum(float(s["weight"]) for s in states),
        "clear_positive_weight": positive_weight,
        "clear_positive_false_stop_count": len(false_stops),
        "clear_positive_false_stop_probability_mass": sum(float(s["weight"]) for s in false_stops),
        "clear_positive_recall": 1.0 - sum(float(s["weight"]) for s in false_stops) / positive_weight if positive_weight else 1.0,
        "false_enhance_count": len(false_enhances),
        "false_enhance_probability_mass": sum(float(s["weight"]) for s in false_enhances),
        "high_loss_false_stop_count": sum(float(s["oracle"]["utility_margin"]) >= HIGH_LOSS_MARGIN for s in false_stops),
        "utility_regret": regret,
        "system_group_counts": dict(sorted(Counter(str(s["features"].get("system_group", "unknown")) for s in states).items())),
        "clear_positive_false_stop_by_system_group": dict(sorted(false_stop_by_group.items())),
    }


def partition_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"sample_count": len(rows), "system_group_counts": dict(sorted(Counter(str(r["features"].get("system_group", "unknown")) for r in rows).items()))}
    for key in (CURRENT_KEY, CANDIDATE_KEY):
        result[key] = {str(checkpoint): metrics(rows, candidate_key=key, checkpoint=checkpoint) for checkpoint in (0, 3)}
    return result


def _add_flow(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _flow_for_candidate(gear: Gear, base: dict[str, Any], rule: phase_c.Rule | None, runs: int) -> dict[str, float]:
    total = _empty_flow()
    if rule is None:
        return phase_b._epic_flow_from_base(gear, None, base, runs)
    action0 = phase_c.action(str(base["start_formal_action"]), 0, base["start_features"], rule)
    for branch in base["branches"]:
        probability = float(branch["probability"])
        if action0 == "stop":
            _add_flow(total, phase_b._flow(gear, {0: gear}, phase_b._outcome_zero()), probability)
            continue
        _add_flow(total, branch["base_to_three"], probability)
        if phase_c.action(str(branch["formal_action"]), 3, branch["features"], rule) == "stop":
            continue
        for flow in branch["later_flows"]:
            _add_flow(total, flow, probability / runs)
    return total


def _flow_job(job: dict[str, Any]) -> dict[str, Any]:
    gear = Gear.from_dict(job["gear"])
    base = phase_b._build_epic_base(gear, RUNS, int(job["seed"]))
    rule = _candidate_rule()
    return {
        "sample_id": job["sample_id"],
        "seed": int(job["seed"]),
        "current": _flow_for_candidate(gear, base, None, RUNS),
        "candidate": _flow_for_candidate(gear, base, rule, RUNS),
    }


def _flow_shard_path(partition: str, seed: int, sample_id: str) -> Path:
    return RESUME / partition / f"seed-{seed}" / f"{sha256(sample_id.encode('utf-8')).hexdigest()}.json"


def _flow_input_hash(row: dict[str, Any], seed: int) -> str:
    return _sha({"study": "epic_balanced_holdout_validation_20260719", "partition": row["partition"], "seed": seed, "sample_id": row["sample_id"], "gear": row["gear"], "runs": RUNS, "candidate_hash": holdout._candidate_hash()})


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_flows(rows: list[dict[str, Any]], partition: str, workers: int) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    shards: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        row["partition"] = partition
        for seed in phase_b.SEEDS:
            path = _flow_shard_path(partition, seed, row["sample_id"])
            expected_hash = _flow_input_hash(row, seed)
            if path.exists():
                payload = _read(path)
                if payload.get("status") == "complete" and payload.get("input_hash") == expected_hash:
                    shards[(row["sample_id"], seed)] = payload
                    continue
            jobs.append({"sample_id": row["sample_id"], "gear": row["gear"], "seed": seed, "input_hash": expected_hash})
    if workers > 1 and jobs:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_flow_job, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                result = future.result()
                payload = {"status": "complete", "schema_version": 1, "input_hash": job["input_hash"], **result}
                _write_json(_flow_shard_path(partition, int(job["seed"]), job["sample_id"]), payload)
                shards[(job["sample_id"], int(job["seed"]))] = payload
    else:
        for job in jobs:
            result = _flow_job(job)
            payload = {"status": "complete", "schema_version": 1, "input_hash": job["input_hash"], **result}
            _write_json(_flow_shard_path(partition, int(job["seed"]), job["sample_id"]), payload)
            shards[(job["sample_id"], int(job["seed"]))] = payload
    return {"scheduled": len(jobs), "reused": len(rows) * len(phase_b.SEEDS) - len(jobs), "shards": shards}


def _formal_joint_input_hash(item: dict[str, Any], code_sha256: str) -> str:
    return phase_b._stable_hash({
        "study": phase_b.STUDY_ID,
        "joint_schema_version": phase_b.JOINT_SCHEMA_VERSION,
        "candidate_key": item["candidate_key"],
        "candidate_hash": item["candidate_hash"],
        "rank": item["rank"],
        "seed": item["seed"],
        "gear": item["gear"].to_dict(),
        "runs": RUNS,
        "code_sha256": code_sha256,
        "official_plus3_branch_model": "enumerate_normal_epic_plus3_probability_weighted",
        "heroic_component": "released_m1",
    })


def _load_shared_heroic() -> dict[int, dict[str, float]]:
    source_payload = _read(SOURCE)
    heroic = _source_rank_gears(source_payload, "Heroic")
    expected, _ = phase_b._joint_expected({}, [], heroic, runs=RUNS)
    formal_report = _read(FORMAL_PHASE_B_REPORT)
    formal_code_sha256 = str(formal_report.get("freeze", {}).get("code_sha256") or "")
    if not formal_code_sha256:
        raise RuntimeError("formal Phase B report has no frozen code hash")
    result: dict[int, dict[str, float]] = {}
    for seed in phase_b.SEEDS:
        total = _empty_flow()
        selected = [item for item in expected.values() if item["candidate_key"] == phase_b.HEROIC_SHARED_KEY and item["rank"] == "Heroic" and item["seed"] == seed]
        for item in selected:
            path = phase_b._joint_path(phase_b.DEFAULT_RESUME, phase_b.HEROIC_SHARED_KEY, "Heroic", seed, item["gear_index"])
            payload = _read(path)
            expected_input_hashes = {item["input_hash"], _formal_joint_input_hash(item, formal_code_sha256)}
            if (
                payload.get("status") != "complete"
                or payload.get("schema_version") != phase_b.JOINT_SCHEMA_VERSION
                or payload.get("candidate_hash") != item["candidate_hash"]
                or payload.get("input_hash") not in expected_input_hashes
                or payload.get("seed") != seed
                or payload.get("rank") != "Heroic"
                or payload.get("gear_index") != item["gear_index"]
            ):
                raise RuntimeError(f"invalid Phase B formal Heroic shard: {path}")
            _add_flow(total, payload["flow"])
        if len(selected) != len(heroic):
            raise RuntimeError(f"unexpected Phase B formal Heroic shard count: {len(selected)}")
        result[seed] = {field: float(total[field]) / float(len(selected)) for field in FLOW_WITH_METRICS}
    return result


def _joint_summary(rows: list[dict[str, Any]], flow_data: dict[str, Any]) -> dict[str, Any]:
    heroic = _load_shared_heroic()
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    output: dict[str, Any] = {"batch": batch, "per_seed": {}, "ci": {}}
    for seed in phase_b.SEEDS:
        output["per_seed"][str(seed)] = {}
        for yield_name, multiplier in YIELD_VARIATIONS.items():
            output["per_seed"][str(seed)][yield_name] = {}
            for key in (CURRENT_KEY, CANDIDATE_KEY):
                epic = _empty_flow()
                for row in rows:
                    _add_flow(epic, flow_data[(row["sample_id"], seed)]["current" if key == CURRENT_KEY else "candidate"], 1.0 / len(rows))
                merged = {field: epic[field] + float(batch["expected_output_by_rank"]["Heroic"]) * float(multiplier) * heroic[seed][field] for field in FLOW_WITH_METRICS}
                pool = explicit_batch_resource_pool(source_gold=float(batch["expected_source_gold_per_batch"]), source_lower_stones=float(batch["expected_lower_stone_units"]), powder_base_exp=merged["powder_units"] * 100, lower_stone_units=merged["lower_stone_units"], material_gold=merged["material_gold"], conversion_gold=merged["conversion_gold"], sell_gold=merged["sell_gold"], sell_exp=merged["sell_exp_adjusted"], material_scarcity_exp=merged["material_exp_adjusted"], lower_stone_adjusted_exp=merged["lower_stone_adjusted_exp"])
                total = float(pool["total_stamina"])
                cycles = 100000.0 / total
                output["per_seed"][str(seed)][yield_name][key] = {
                    "formal_rate_per_100": 100.0 * merged["value_sum"] / total,
                    "per_100k": {field: cycles * merged[field] for field in FLOW_WITH_METRICS},
                    "rift_stamina_per_100k": cycles * 85.0,
                    "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]),
                    "cycles_per_100k": cycles,
                    "resource_pool": pool,
                }
    for yield_name in YIELD_VARIATIONS:
        output["ci"][yield_name] = {}
        for key in (CURRENT_KEY, CANDIDATE_KEY):
            rates = [output["per_seed"][str(seed)][yield_name][key]["formal_rate_per_100"] for seed in phase_b.SEEDS]
            output["ci"][yield_name][key] = {
                "formal_rate_per_100": phase_b._ci(rates),
                "per_100k": {field: phase_b._ci([output["per_seed"][str(seed)][yield_name][key]["per_100k"][field] for seed in phase_b.SEEDS]) for field in FLOW_WITH_METRICS},
                "rift_stamina_per_100k": phase_b._ci([output["per_seed"][str(seed)][yield_name][key]["rift_stamina_per_100k"] for seed in phase_b.SEEDS]),
                "saint_stamina_per_100k": phase_b._ci([output["per_seed"][str(seed)][yield_name][key]["saint_stamina_per_100k"] for seed in phase_b.SEEDS]),
                "cycles_per_100k": phase_b._ci([output["per_seed"][str(seed)][yield_name][key]["cycles_per_100k"] for seed in phase_b.SEEDS]),
            }
        diff = [output["per_seed"][str(seed)][yield_name][CANDIDATE_KEY]["formal_rate_per_100"] - output["per_seed"][str(seed)][yield_name][CURRENT_KEY]["formal_rate_per_100"] for seed in phase_b.SEEDS]
        output["ci"][yield_name]["candidate_minus_current"] = {"formal_rate_per_100": phase_b._ci(diff), "positive": phase_b._ci(diff)["interval95"][0] > 0}
    return output


def gate_summary(partitions: dict[str, Any], joint: dict[str, Any], freeze: dict[str, Any]) -> dict[str, Any]:
    frozen = partitions["frozen_validation"]
    candidate = {"plus0": frozen[CANDIDATE_KEY]["0"], "plus3": frozen[CANDIDATE_KEY]["3"]}
    current = {"plus0": frozen[CURRENT_KEY]["0"], "plus3": frozen[CURRENT_KEY]["3"]}
    value_pass = all(joint["ci"][name]["candidate_minus_current"]["positive"] for name in YIELD_VARIATIONS)
    gates = {
        "data_isolation_and_hashes": True,
        "plus0_clear_positive_recall_ge_95pct": candidate["plus0"]["clear_positive_recall"] >= float(freeze["validation_gates"]["plus0_clear_positive_recall_min"]),
        "plus3_weighted_clear_positive_recall_ge_99pct": candidate["plus3"]["clear_positive_recall"] >= float(freeze["validation_gates"]["plus3_weighted_clear_positive_recall_min"]),
        "pure_output_plus0_false_stop_zero": frozen[CANDIDATE_KEY]["0"].get("clear_positive_false_stop_by_system_group", {}).get("pure_output", 0) == 0,
        "candidate_regret_not_above_current": candidate["plus0"]["utility_regret"] + candidate["plus3"]["utility_regret"] <= current["plus0"]["utility_regret"] + current["plus3"]["utility_regret"] + 1e-12,
        "no_high_loss_false_stop": candidate["plus0"]["high_loss_false_stop_count"] + candidate["plus3"]["high_loss_false_stop_count"] == 0,
        "joint_value_ci_lower_gt_zero": value_pass,
        "heroic_yield_sensitivity_ci_lower_gt_zero": value_pass,
    }
    return {"gates": gates, "passed": all(gates.values()), "frozen_candidate": candidate, "frozen_current": current}


def markdown(data: dict[str, Any]) -> str:
    gates = data["gate_summary"]
    lines = [
        "# Epic 非速度均衡候选 Holdout 验证",
        "",
        "候选固定为 `output_8_13_tank_10_17`，本报告只读取冻结候选和不可变 64/64 manifest；未调参、未修改正式策略、未读取人工标签。",
        "",
        f"状态：`{'validation_passed_pending_user_release' if gates['passed'] else 'validation_failed_keep_current_formal'}`",
        "",
        "## 输入隔离",
        "",
        f"- development：{data['partitions']['development']['sample_count']} 件；frozen_validation：{data['partitions']['frozen_validation']['sample_count']} 件。",
        f"- manifest：`{data['integrity']['sample_count']} 件，64/64`；冻结哈希和 collection 哈希均通过。",
        "",
        "## 预注册闸门（仅 frozen_validation）",
        "",
        "| 闸门 | 结果 |",
        "|---|---|",
    ]
    for key, value in gates["gates"].items():
        lines.append(f"| `{key}` | {'通过' if value else '失败'} |")
    lines.extend(["", "## 逐节点指标", "", "| 分区 | 策略 | +0召回 | +0误停 | +3加权召回 | +3误停 | regret |", "|---|---|---:|---:|---:|---:|---:|"])
    for partition in ("development", "frozen_validation"):
        rows = data["partitions"][partition]
        for key, label in ((CURRENT_KEY, "当前正式"), (CANDIDATE_KEY, "Holdout候选")):
            m0, m3 = rows[key]["0"], rows[key]["3"]
            lines.append(f"| {partition} | {label} | {m0['clear_positive_recall']:.2%} | {m0['clear_positive_false_stop_count']} | {m3['clear_positive_recall']:.2%} | {m3['clear_positive_false_stop_count']} | {m0['utility_regret'] + m3['utility_regret']:.6f} |")
    lines.extend(["", "## 每 100,000 总体力（frozen_validation 分布条件）", "", "| Heroic产出 | 策略 | 正式百里分 | 原生75+ | 转换75+ | 22速 | 裂缝体力 | 圣女体力 | 循环 | 候选-当前正式百里分成对95%区间 |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for yield_name in YIELD_VARIATIONS:
        ci = data["joint"]["ci"][yield_name]
        for key, label in ((CURRENT_KEY, "当前正式"), (CANDIDATE_KEY, "Holdout候选")):
            row = ci[key]
            per_100k = row["per_100k"]
            lines.append(f"| {yield_name} | {label} | {per_100k['value_sum']['mean']:.3f} | {per_100k['native_heirloom']['mean']:.3f} | {per_100k['converted_heirloom']['mean']:.3f} | {per_100k['speed22']['mean']:.3f} | {row['rift_stamina_per_100k']['mean']:.2f} | {row['saint_stamina_per_100k']['mean']:.2f} | {row['cycles_per_100k']['mean']:.3f} | - |")
        diff = ci["candidate_minus_current"]["formal_rate_per_100"]["interval95"]
        lines.append(f"| {yield_name} | 候选-当前 | [{diff[0] * 1000:.3f}, {diff[1] * 1000:.3f}] | - | - | - | - | - | - | 每10万总体力正式百里分 |")
    lines.extend(["", "> 注：本表的正式百里分、原生75+、转换75+和22速均为每10万总体力产量；绝对值条件于本 Holdout 样本分布。该 Holdout 排除了速度硬路线、鞋子及非目标来源，不能解释为账号自然掉落全局效率。", "", "## 结论", "", "- development 只用于预注册诊断，未用于修改候选。", "- 只有 frozen_validation 闸门全部通过时才允许用户确认发布；失败则维持当前正式策略。", "- 绝对产量条件于本 Holdout 样本分布，不能解释为账号自然掉落全局效率。"])
    return "\n".join(lines) + "\n"


def run(*, workers: int = 4) -> dict[str, Any]:
    freeze, collection, manifest, integrity = audit_inputs()
    result_partitions: dict[str, Any] = {}
    all_rows: dict[str, list[dict[str, Any]]] = {}
    flow_data: dict[str, Any] = {}
    for partition in ("development", "frozen_validation"):
        rows = load_partition(collection, manifest, partition)
        evaluated = evaluate_partition(rows, partition, workers)
        result_partitions[partition] = {**partition_metrics(evaluated), "items": evaluated}
        all_rows[partition] = evaluated
        flow_result = run_flows(evaluated, partition, workers)
        for key, value in flow_result["shards"].items():
            flow_data[key] = value
    frozen_joint = _joint_summary(all_rows["frozen_validation"], flow_data)
    partitions_for_gate = {partition: {key: result_partitions[partition][key] for key in (CURRENT_KEY, CANDIDATE_KEY)} for partition in result_partitions}
    gate = gate_summary(partitions_for_gate, frozen_joint, freeze)
    return {
        "study": "epic_balanced_holdout_validation_20260719",
        "schema_version": 1,
        "complete": True,
        "candidate": freeze["candidate"],
        "freeze": freeze,
        "manifest": {"manifest_id": manifest["manifest_id"], "status": manifest["status"], "split_rule": manifest["split_rule"]},
        "integrity": integrity,
        "partitions": result_partitions,
        "joint": frozen_joint,
        "gate_summary": gate,
        "data_isolation": {"development_used_for_tuning": False, "frozen_validation_read_once": True, "production_strategy_modified": False, "gui_or_ocr_modified": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the frozen Epic balanced Holdout candidate")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=REPORT_OUTPUT)
    args = parser.parse_args()
    data = run(workers=max(1, int(args.workers)))
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"json": str(args.json_output), "report": str(args.markdown_output), "passed": data["gate_summary"]["passed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
