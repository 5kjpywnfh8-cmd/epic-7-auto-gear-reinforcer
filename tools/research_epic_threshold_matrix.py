"""Controlled Epic non-speed +0/+3 effective-GS threshold matrix study.

This is an offline-only companion to ``research_epic_exact_plus3``.  It uses
the same real development +0 cohort and the same official discrete +3 branch
enumerator, but freezes a pre-registered T0/T3 matrix instead of selecting a
rule from the data.  Production policies are inputs only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
import sys
import tempfile
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    Strategy,
    _source_rank_gears,
    formal_followup_action,
    simulate_paths,
    simulate_strategy_path,
)
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_epic_exact_plus3 import (
    DEVELOPMENT_EXPECTED_COUNT,
    EPSILON,
    SafeStopRule,
    _evaluate_state,
    _formal_action,
    _parse_rule,
    _shard_input_hash,
    _shard_path,
    _valid_shard as _valid_exact_shard,
    _state_payload,
    _feature_view,
    action_for_rule,
    evaluate_cached,
    load_real_plus0,
    plus0_states,
    weighted_metrics,
)
from tools.research_epic_exact_plus3_joint_pool import _flow, _heroic_shard
from tools.research_riftslash_saint_pool import YIELD_VARIATIONS, _t95, explicit_batch_resource_pool


STUDY_ID = "epic_non_speed_plus0_plus3_threshold_matrix_20260717"
SCHEMA_VERSION = 1
SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
T0_VALUES = (10, 12, 14)
T3_VALUES = (14, 16, 17, 18, 20)
CURRENT_KEY = "current_formal"
DEFAULT_RECORDS = ROOT / "manual_acceptance" / "real_sample_records.json"
DEFAULT_SOURCE = ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json"
DEFAULT_RESUME = ROOT / "reports" / "epic_threshold_matrix_resume_20260717"
DEFAULT_JSON = ROOT / "reports" / "epic_threshold_matrix_20260717.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_threshold_matrix_20260717.md"
EXACT_DEVELOPMENT_RESUME = ROOT / "reports" / "epic_exact_plus3_resume_20260717"


@dataclass(frozen=True)
class ThresholdCandidate:
    t0: int
    t3: int

    @property
    def key(self) -> str:
        return f"t0_{self.t0}_t3_{self.t3}"

    @property
    def is_priority_route(self) -> bool:
        return self.t3 >= self.t0 + 4


def candidates() -> tuple[ThresholdCandidate, ...]:
    return tuple(ThresholdCandidate(t0, t3) for t0 in T0_VALUES for t3 in T3_VALUES)


def _rule(threshold: int, checkpoint: int) -> SafeStopRule:
    """Only the effective-GS ceiling varies; all other pre-registered terms freeze."""
    return SafeStopRule(
        effective_gs_max=float(threshold),
        current_valid_max=2,
        terminal_probability_max=0.002 if checkpoint == 0 else 0.01,
        conversion_value_max=0.0,
    )


def _candidate_action(row: dict[str, Any], candidate: ThresholdCandidate | None) -> str:
    if candidate is None:
        return str(row["current_action"])
    threshold = candidate.t0 if int(row["checkpoint"]) == 0 else candidate.t3
    return action_for_rule(str(row["current_action"]), row["features"], _rule(threshold, int(row["checkpoint"])))


def _all_plus3_states(base_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enumerate once; each matrix route later filters exactly these weighted branches."""
    states: list[dict[str, Any]] = []
    for base in base_rows:
        gear = Gear.from_dict(base["gear"])
        if _formal_action(gear, str(base["gear_source"])) == "stop":
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


def _plus3_for_candidate(rows: Iterable[dict[str, Any]], candidate: ThresholdCandidate) -> list[dict[str, Any]]:
    result = []
    rule0 = _rule(candidate.t0, 0)
    for row in rows:
        # The base state is stored in the row metadata only indirectly.  The
        # initial action is deterministic from the matching +0 evaluation and
        # added by ``prepare_development_rows`` below.
        if str(row["plus0_candidate_actions"][candidate.key]) != "stop":
            result.append(row)
    return result


def _matching_old_plus3_rows(states: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Read only predecessor shards whose full input hash still matches."""
    node = f"plus3-{_stable_sha(asdict(_rule(10, 0)))[:16]}"
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in states:
        groups.setdefault(str(row["sample_id"]), []).append(row)
    matched: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    matched_groups = 0
    for sample_id, group in sorted(groups.items()):
        group = sorted(group, key=lambda row: row["state_id"])
        path = _shard_path(EXACT_DEVELOPMENT_RESUME, "development", node, sample_id)
        input_hash = _shard_input_hash(group)
        if _valid_exact_shard(path, partition="development", node=node, input_hash=input_hash):
            matched.extend(json.loads(path.read_text(encoding="utf-8"))["rows"])
            matched_groups += 1
        else:
            pending.extend(group)
    return matched, pending, matched_groups


def _candidate_metrics(plus0: list[dict[str, Any]], plus3_all: list[dict[str, Any]], candidate: ThresholdCandidate) -> dict[str, Any]:
    plus0_rule = _rule(candidate.t0, 0)
    plus3_rule = _rule(candidate.t3, 3)
    plus3 = _plus3_for_candidate(plus3_all, candidate)
    plus0_metrics = weighted_metrics(plus0, plus0_rule)
    plus3_metrics = weighted_metrics(plus3, plus3_rule)
    plus3_metrics["unconditional_stopped_weight_per_plus0"] = plus3_metrics["stopped_weight"] / plus0_metrics["state_weight"]
    plus3_metrics["unconditional_probability_mass_per_plus0"] = plus3_metrics["state_weight"] / plus0_metrics["state_weight"]
    return {"plus0": plus0_metrics, "plus3": plus3_metrics}


def _node_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    for node in ("plus0", "plus3"):
        row = metrics[node]
        formal = row["formal"]
        candidate = row["candidate"]
        if candidate["clear_positive_false_stop_count"]:
            reasons.append(f"{node} clear-positive false stops={candidate['clear_positive_false_stop_count']}")
        if candidate["total_regret"] > formal["total_regret"] + EPSILON:
            reasons.append(f"{node} regret exceeds matched formal route")
        if candidate["saved_next_node_stamina"] <= 0:
            reasons.append(f"{node} saves no next-node stamina")
    return {"passed": not reasons, "reasons": reasons}


def prepare_development_rows(records: Path, resume_dir: Path, workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    base = load_real_plus0(records, "development")
    if len(base) != DEVELOPMENT_EXPECTED_COUNT:
        raise ValueError(f"expected {DEVELOPMENT_EXPECTED_COUNT} development items, got {len(base)}")
    # These exact-DP labels are immutable raw development calculations from
    # the immediately preceding official-branch study.  Reusing them avoids
    # recomputing the same 157 inputs and never reads its frozen partition.
    plus0, plus0_resume = evaluate_cached(
        plus0_states(base), resume_dir=EXACT_DEVELOPMENT_RESUME, partition="development", node="plus0", workers=workers,
    )
    actions = {
        candidate.key: {
            row["instance_id"]: _candidate_action(row, candidate)
            for row in plus0
        }
        for candidate in candidates()
    }
    all_states = _all_plus3_states(base)
    # The predecessor's selected +0 rule is exactly the frozen T0=10 row.
    # Reuse only that raw development branch evaluation, then calculate the
    # additional branches exposed by T0=12/14 in this study's own cache.
    old_key = ThresholdCandidate(10, 14).key
    old_states = [row for row in all_states if actions[old_key][str(row["instance_id"])] != "stop"]
    old_plus3, mismatched_old_states, matched_old_groups = _matching_old_plus3_rows(old_states)
    additional_states = [row for row in all_states if actions[old_key][str(row["instance_id"])] == "stop"]
    # A +3 DP evaluation can be materially slower than +0.  Cache each new
    # official branch independently so a 120-second host interruption still
    # preserves completed exact branches for the next run.
    pending_states = mismatched_old_states + additional_states
    additional_jobs = [{**row, "sample_id": f"{row['sample_id']}:{row['state_id']}"} for row in pending_states]
    additional_plus3, additional_resume = evaluate_cached(
        additional_jobs, resume_dir=resume_dir, partition="development_only", node="plus3_t0_above_10", workers=workers,
    )
    plus3 = old_plus3 + additional_plus3
    plus3_resume = {"reused_t0_10_matched_groups": matched_old_groups, "new_or_mismatched_states": additional_resume}
    for row in plus3:
        row["plus0_candidate_actions"] = {key: actions[key][str(row["instance_id"])] for key in actions}
    return plus0, plus3, {"base_count": len(base), "plus0": plus0_resume, "plus3": plus3_resume}


def node_matrix(plus0: list[dict[str, Any]], plus3_all: list[dict[str, Any]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    formal0 = weighted_metrics(plus0, None)
    for candidate in candidates():
        plus3 = _plus3_for_candidate(plus3_all, candidate)
        formal3 = weighted_metrics(plus3, None)
        candidate_metrics = _candidate_metrics(plus0, plus3_all, candidate)
        metrics = {
            "plus0": {"formal": formal0, "candidate": candidate_metrics["plus0"]},
            "plus3": {"formal": formal3, "candidate": candidate_metrics["plus3"]},
        }
        results[candidate.key] = {
            "candidate": asdict(candidate),
            "priority_route": candidate.is_priority_route,
            "metrics": metrics,
            "node_gate": _node_gate(metrics),
        }
    return results


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _stable_sha(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _path(resume: Path, rank: str, seed: int, index: int) -> Path:
    return resume / "joint_v1" / rank.lower() / f"seed-{seed}" / f"gear-{index:04d}.json"


def _valid_shard(path: Path, input_hash: str) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return data.get("status") == "complete" and data.get("schema_version") == SCHEMA_VERSION and data.get("input_hash") == input_hash


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _outcome_zero(gear: Gear) -> dict[str, Any]:
    return {"start_checkpoint": 0, "stop_checkpoint": 0, "net_stamina": 0.0, "net_gold": 0.0, "costs": {}}


def _early_action_for_gear(gear: Gear, candidate: ThresholdCandidate | None) -> str:
    current = _formal_action(gear, GEAR_SOURCE)
    if candidate is None:
        return current
    checkpoint = int(gear.enhance)
    threshold = candidate.t0 if checkpoint == 0 else candidate.t3
    return action_for_rule(current, _feature_view(gear), _rule(threshold, checkpoint))


def _epic_joint_shard(gear: Gear, matrix: tuple[ThresholdCandidate, ...], runs: int, seed: int) -> dict[str, Any]:
    keys = (CURRENT_KEY,) + tuple(candidate.key for candidate in matrix)
    totals = {key: _empty_flow() for key in keys}
    if _early_action_for_gear(gear, None) == "stop":
        base = _flow(gear, {0: gear}, _outcome_zero(gear))
        for key in keys:
            _add(totals[key], base)
        return {"paths": 1.0, "candidates": totals}
    branches = enumerate_normal_epic_plus3(gear)
    for branch_index, branch in enumerate(branches):
        common_paths = simulate_paths(branch.gear, "normal_85", runs, seed * 1_000_003 + branch_index * 1009)
        for candidate in (None,) + matrix:
            key = CURRENT_KEY if candidate is None else candidate.key
            if _early_action_for_gear(gear, candidate) == "stop":
                _add(totals[key], _flow(gear, {0: gear}, _outcome_zero(gear)), float(branch.probability))
                continue
            if _early_action_for_gear(branch.gear, candidate) == "stop":
                outcome = {"start_checkpoint": 0, "stop_checkpoint": 3, "net_stamina": 0.0, "net_gold": 0.0, "costs": {}}
                _add(totals[key], _flow(gear, {0: gear, 3: branch.gear}, outcome), float(branch.probability))
                continue
            for path in common_paths:
                outcome = simulate_strategy_path(
                    path,
                    "normal_85",
                    Strategy("threshold_matrix", "offline matrix", lambda _features: "stop"),
                    early_action=lambda state, frozen=candidate: _early_action_for_gear(state, frozen),
                    formal_followup=lambda state: formal_followup_action(state, "normal_85"),
                )
                _add(totals[key], _flow(branch.gear, path, outcome), float(branch.probability) / runs)
    return {"paths": 1.0, "candidates": totals}


def _worker(job: dict[str, Any]) -> str:
    if job["rank"] == "Epic":
        payload = _epic_joint_shard(job["gear"], tuple(ThresholdCandidate(**row) for row in job["matrix"]), job["runs"], job["seed"])
    else:
        payload = _heroic_shard(job["gear"], job["runs"], job["seed"])
    payload.update({key: job[key] for key in ("rank", "seed", "index", "input_hash")})
    payload.update({"status": "complete", "schema_version": SCHEMA_VERSION})
    _atomic_json(Path(job["path"]), payload)
    return str(job["path"])


def _input_hash(gear: Gear, rank: str, matrix: tuple[ThresholdCandidate, ...], runs: int) -> str:
    return _stable_sha({"study": STUDY_ID, "schema": SCHEMA_VERSION, "gear": gear.to_dict(), "rank": rank, "matrix": [asdict(row) for row in matrix], "runs": runs})


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if not jobs:
        return
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            list(executor.map(_worker, jobs))
    else:
        for job in jobs:
            _worker(job)


def _sum_seed(resume: Path, rank: str, seed: int, expected: dict[int, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"paths": 0.0}
    for index, input_hash in expected.items():
        path = _path(resume, rank, seed, index)
        if not _valid_shard(path, input_hash):
            raise RuntimeError(f"incomplete matrix joint shard: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        result["paths"] += float(payload["paths"])
        rows = payload["candidates"] if rank == "Epic" else payload["policies"]
        for key, flow in rows.items():
            target = result.setdefault(key, _empty_flow())
            _add(target, flow)
    return result


def _combine(epic: dict[str, Any], heroic: dict[str, Any], heroic_yield: float, key: str) -> dict[str, float]:
    return {
        field: float(epic[key][field]) / float(epic["paths"]) + heroic_yield * float(heroic["released_m1"][field]) / float(heroic["paths"])
        for field in FLOW_WITH_METRICS
    }


def _pool(flow: dict[str, float], batch: dict[str, Any]) -> dict[str, Any]:
    return explicit_batch_resource_pool(
        source_gold=float(batch["expected_source_gold_per_batch"]),
        source_lower_stones=float(batch["expected_lower_stone_units"]),
        powder_base_exp=flow["powder_units"] * 100,
        lower_stone_units=flow["lower_stone_units"],
        material_gold=flow["material_gold"],
        conversion_gold=flow["conversion_gold"],
        sell_gold=flow["sell_gold"],
        sell_exp=flow["sell_exp_adjusted"],
        material_scarcity_exp=flow["material_exp_adjusted"],
        lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
    )


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values)
    if len(values) < 2:
        return {"mean": center, "interval95": [center, center]}
    half = _t95(len(values)) * stdev(values) / sqrt(len(values))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": stdev(values)}


def joint_pool(matrix: tuple[ThresholdCandidate, ...], source: Path, resume: Path, runs: int, workers: int) -> dict[str, Any]:
    """Run all node-gated candidates on common exact branches and common seeds."""
    base = load_real_plus0(DEFAULT_RECORDS, "development")
    epic = [Gear.from_dict(row["gear"]) for row in base]
    heroic = _source_rank_gears(json.loads(source.read_text(encoding="utf-8")), "Heroic")
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    expected: dict[str, dict[int, dict[int, str]]] = {"Epic": {}, "Heroic": {}}
    jobs: list[dict[str, Any]] = []
    serialized_matrix = [asdict(row) for row in matrix]
    for rank, gears in (("Epic", epic), ("Heroic", heroic)):
        for seed in SEEDS:
            hashes: dict[int, str] = {}
            for index, gear in enumerate(gears):
                input_hash = _input_hash(gear, rank, matrix, runs)
                hashes[index] = input_hash
                path = _path(resume, rank, seed, index)
                if not _valid_shard(path, input_hash):
                    jobs.append({"rank": rank, "seed": seed, "index": index, "gear": gear, "runs": runs, "matrix": serialized_matrix, "input_hash": input_hash, "path": str(path)})
            expected[rank][seed] = hashes
    _run_jobs(jobs, workers)
    keys = (CURRENT_KEY,) + tuple(candidate.key for candidate in matrix)
    per_seed: dict[str, Any] = {}
    for seed in SEEDS:
        epic_sum = _sum_seed(resume, "Epic", seed, expected["Epic"][seed])
        heroic_sum = _sum_seed(resume, "Heroic", seed, expected["Heroic"][seed])
        per_seed[str(seed)] = {}
        for yield_name, multiplier in YIELD_VARIATIONS.items():
            heroic_yield = float(batch["expected_output_by_rank"]["Heroic"]) * float(multiplier)
            per_seed[str(seed)][yield_name] = {}
            for key in keys:
                flow = _combine(epic_sum, heroic_sum, heroic_yield, key)
                resource = _pool(flow, batch)
                total = float(resource["total_stamina"])
                cycles = 100000.0 / total
                per_seed[str(seed)][yield_name][key] = {
                    "formal_rate_per_100": 100.0 * flow["value_sum"] / total,
                    "per_100k": {field: cycles * flow[field] for field in FLOW_WITH_METRICS},
                    "rift_stamina_per_100k": cycles * 85.0,
                    "saint_stamina_per_100k": cycles * float(resource["saint_supplement_stamina"]),
                    "source_cycles_per_100k": cycles,
                }
    summary: dict[str, Any] = {}
    for yield_name in YIELD_VARIATIONS:
        summary[yield_name] = {}
        current = [per_seed[str(seed)][yield_name][CURRENT_KEY]["formal_rate_per_100"] for seed in SEEDS]
        for candidate in matrix:
            values = [per_seed[str(seed)][yield_name][candidate.key]["formal_rate_per_100"] for seed in SEEDS]
            summary[yield_name][candidate.key] = {
                "candidate_rate": _ci(values),
                "candidate_minus_current": _ci([value - baseline for value, baseline in zip(values, current)]),
            }
    return {
        "scope": "conditional on the 157 real normal_85 Epic non-boot non-speed development +0 cohort; Heroic M1 is a common component",
        "seeds": list(SEEDS), "runs_per_official_plus3_branch": runs,
        "matrix": [asdict(row) for row in matrix],
        "cohort": {"epic_development_count": len(epic), "heroic_source_count": len(heroic)},
        "execution": {"scheduled_shards": len(jobs), "resume_dir": str(resume.resolve().relative_to(ROOT))},
        "per_seed": per_seed, "summary": summary,
    }


def _freeze_payload(matrix: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "study": STUDY_ID,
        "schema_version": SCHEMA_VERSION,
        "scope": "development-only; old frozen validation was not read",
        "matrix": [asdict(candidate) for candidate in candidates()],
        "fixed_terms": {"current_valid_max": 2, "plus0_terminal_probability_max": 0.002, "plus3_terminal_probability_max": 0.01, "conversion_value_max": 0.0},
        "node_gated_candidates": [key for key, row in matrix.items() if row["node_gate"]["passed"]],
    }
    return {**payload, "freeze_sha256": _stable_sha(payload)}


def report(data: dict[str, Any]) -> str:
    lines = [
        "# Epic non-speed +0/+3 threshold matrix (2026-07-17)", "",
        "## Scope", "",
        "- Development-only: 157 real +0 items and probability-weighted official +3 branches.",
        "- Old frozen validation is not read. A new independent +0 holdout is required after this matrix freezes.",
        "- Production policy, DP, roll table, resource model, GUI, and automation remain unchanged.", "",
        "## Node Matrix", "",
        "| Route | Priority route | +0 stop rate | +3 stop rate conditional on reach | +0 positive false stops | +3 positive false stops | +0/+3 regret | Next-node stamina saved | Node gate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for key, row in data["node_matrix"].items():
        m0, m3 = row["metrics"]["plus0"]["candidate"], row["metrics"]["plus3"]["candidate"]
        total0 = m0["state_weight"] or 1.0
        total3 = m3["state_weight"] or 1.0
        status = "pass" if row["node_gate"]["passed"] else "blocked"
        lines.append(f"| {key} | {'yes' if row['priority_route'] else 'no'} | {m0['stopped_weight']/total0:.2%} | {m3['stopped_weight']/total3:.2%} | {m0['clear_positive_false_stop_count']} | {m3['clear_positive_false_stop_count']} | {m0['total_regret']:.6f}/{m3['total_regret']:.6f} | {m0['saved_next_node_stamina'] + m3['saved_next_node_stamina']:.3f} | {status} |")
    lines.extend(["", "## Controlled Comparisons", "", "- Fixed T0=12: compare T3=16/17/18/20 on identical real items and official +3 branches.", "- Fixed T3=18: compare T0=10/12/14 on identical real items and official +3 branches."])
    lines.extend(["", "### Fixed T0=12", "", "| T3 | +0 positive false stops | +3 positive false stops | +0/+3 positive recall | Node gate |", "|---:|---:|---:|---:|---|"])
    for t3 in (16, 17, 18, 20):
        row = data["node_matrix"][ThresholdCandidate(12, t3).key]
        m0, m3 = row["metrics"]["plus0"]["candidate"], row["metrics"]["plus3"]["candidate"]
        lines.append(f"| {t3} | {m0['clear_positive_false_stop_count']} | {m3['clear_positive_false_stop_count']} | {m0['clear_positive_recall']:.2%}/{m3['clear_positive_recall']:.2%} | {'pass' if row['node_gate']['passed'] else 'blocked'} |")
    lines.extend(["", "### Fixed T3=18", "", "| T0 | +0 positive false stops | +3 positive false stops | +0/+3 positive recall | Node gate |", "|---:|---:|---:|---:|---|"])
    for t0 in (10, 12, 14):
        row = data["node_matrix"][ThresholdCandidate(t0, 18).key]
        m0, m3 = row["metrics"]["plus0"]["candidate"], row["metrics"]["plus3"]["candidate"]
        lines.append(f"| {t0} | {m0['clear_positive_false_stop_count']} | {m3['clear_positive_false_stop_count']} | {m0['clear_positive_recall']:.2%}/{m3['clear_positive_recall']:.2%} | {'pass' if row['node_gate']['passed'] else 'blocked'} |")
    focus = data["node_matrix"][ThresholdCandidate(12, 17).key]
    focus0, focus3 = focus["metrics"]["plus0"]["candidate"], focus["metrics"]["plus3"]["candidate"]
    lines.extend(["", "### Requested T0=12 / T3=17", "", f"- Node gate: {'pass' if focus['node_gate']['passed'] else 'blocked'}.", f"- Clear-positive false stops: +0={focus0['clear_positive_false_stop_count']}, +3={focus3['clear_positive_false_stop_count']}.", "- It is intentionally excluded from the joint pool because the study protocol forbids running a failed node candidate there."])
    if data["joint_pool"]["status"] != "completed":
        lines.extend(["", "## Joint Pool", "", f"- Not run: {data['joint_pool']['status']}. Only node-gated routes may enter the five-seed pool."])
        return "\n".join(lines) + "\n"
    lines.extend(["", "## Five-Seed Joint Pool", "", "Only node-gated routes are included. All differences use identical items, official +3 branches, five seeds, Heroic M1, and the explicit Rift/Saint pool.", "", "| Heroic yield | Route | Formal value / 100 stamina difference 95% CI |", "|---|---|---:|"])
    for yield_name, values in data["joint_pool"]["result"]["summary"].items():
        for candidate in data["joint_pool"]["result"]["matrix"]:
            key = ThresholdCandidate(**candidate).key
            ci = values[key]["candidate_minus_current"]["interval95"]
            lines.append(f"| {yield_name} | {key} | [{ci[0]:.6f}, {ci[1]:.6f}] |")
    first = data["joint_pool"]["result"]["per_seed"][str(SEEDS[0])]["baseline"]
    lines.extend(["", "## Example Per 100,000 Total Stamina", "", "First shared seed with baseline Heroic yield. Absolute values are conditional on the development non-speed Epic cohort, not account-wide drop rates.", "", "| Route | Formal value | Native 75+ | Converted 75+ | 22+ | Output 60 | Rift stamina | Saint 3-7 stamina | Cycles |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for key in (CURRENT_KEY,) + tuple(ThresholdCandidate(**row).key for row in data["joint_pool"]["result"]["matrix"]):
        row = first[key]
        metric = row["per_100k"]
        lines.append(f"| {key} | {metric['value_sum']:.3f} | {metric['native_heirloom']:.3f} | {metric['converted_heirloom']:.3f} | {metric['speed22']:.3f} | {metric['output60']:.3f} | {row['rift_stamina_per_100k']:.3f} | {row['saint_stamina_per_100k']:.3f} | {row['source_cycles_per_100k']:.3f} |")
    lines.extend(["", "## Release Status", "", "- Matrix and risk tiers are frozen by the recorded freeze SHA-256.", "- A new independent real +0 holdout (minimum 48; 64 recommended) is required before any policy release.", "- This study does not modify the released Epic policy."])
    return "\n".join(lines) + "\n"

def run(records: Path, source: Path, resume: Path, runs: int, workers: int) -> dict[str, Any]:
    plus0, plus3, preparation = prepare_development_rows(records, resume, workers)
    matrix = node_matrix(plus0, plus3)
    freeze = _freeze_payload(matrix)
    gated = tuple(ThresholdCandidate(**row["candidate"]) for row in matrix.values() if row["node_gate"]["passed"])
    joint: dict[str, Any]
    if gated:
        joint = {"status": "completed", "result": joint_pool(gated, source, resume, runs, workers)}
    else:
        joint = {"status": "not_run_no_candidate_passed_node_gate"}
    return {
        "study": STUDY_ID, "schema_version": SCHEMA_VERSION,
        "data_isolation": {"development_real_plus0_count": len(plus0), "old_frozen_validation_read": False, "future_holdout_required": 48},
        "probability_model": {"plus3": "STOVE official discrete distribution, probability weighted", "target_selection": "one quarter per existing Epic +0 substat", "downstream": "frozen formal Epic DP from +6"},
        "preparation": preparation, "node_matrix": matrix, "freeze": freeze, "joint_pool": joint,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact official +3 controlled T0/T3 matrix study")
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--resume-dir", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    data = run(args.records, args.source, args.resume_dir, max(1, args.runs), max(1, args.workers))
    _atomic_json(args.json_output, data)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(report(data), encoding="utf-8")
    print(json.dumps({"json": str(args.json_output), "report": str(args.markdown_output), "joint_status": data["joint_pool"]["status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
