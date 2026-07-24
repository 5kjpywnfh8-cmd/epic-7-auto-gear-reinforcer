"""Phase B: candidate-consistent Epic +0/+3 threshold research.

Phase A reports remain immutable.  This module owns a new schema and resume
directory, repairs the feature-system mismatch, and compares every candidate
offline.  It never writes production policy settings.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import research_epic_threshold_matrix as phase_a
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, Strategy, _source_rank_gears, formal_followup_action, simulate_paths, simulate_strategy_path
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.research_epic_exact_plus3 import SafeStopRule, _formal_action, action_for_rule, load_real_plus0
from src.e7_enhance.lightweight_calibration import evaluate_early_candidates
from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow
from tools.research_epic_exact_plus3_joint_pool import _flow, _heroic_shard
from tools.research_riftslash_saint_pool import YIELD_VARIATIONS, _t95, explicit_batch_resource_pool


STUDY_ID = "epic_threshold_matrix_phase_b_candidate_consistent_20260717"
SCHEMA_VERSION = 2
SEEDS = phase_a.SEEDS
CURRENT_KEY = "current_formal"
GLOBAL_T0 = (10, 12, 14)
GLOBAL_T3 = (14, 16, 17, 18, 20)
SYSTEM_GROUPS = ("pure_output", "pure_tank", "bruiser", "dual")
FORMAL_CATEGORY_GROUPS = {
    "输出": "pure_output",
    "输出(必爆)": "pure_output",
    "抗坦": "pure_tank",
    "纯肉": "pure_tank",
    "命坦": "pure_tank",
    "双效": "dual",
    "半肉(血防)": "bruiser",
    "半肉(通用)": "bruiser",
    "半肉(白字)": "bruiser",
}
_SNAPSHOT_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}
PILOT_RESUME = ROOT / "reports" / "epic_threshold_matrix_phase_b_resume_20260717"
DEFAULT_RESUME = ROOT / "reports" / "epic_threshold_matrix_phase_b_formal_r10_resume_20260718"
DEFAULT_JSON = ROOT / "reports" / "epic_threshold_matrix_phase_b_formal_r10_20260718.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_threshold_matrix_phase_b_formal_r10_20260718.md"
JOINT_SCHEMA_VERSION = 2
JOINT_DIRECTORY = "joint_v2"
HEROIC_SHARED_KEY = "shared_m1"


@dataclass(frozen=True)
class Candidate:
    t0: int
    t3: int
    system_group: str = "global"
    delta: int = 0

    @property
    def key(self) -> str:
        return f"t0_{self.t0}_t3_{self.t3}_{self.system_group}_{self.delta:+d}".replace("+", "p").replace("-", "m")


def candidates() -> tuple[Candidate, ...]:
    global_rows = [Candidate(t0, t3) for t0 in GLOBAL_T0 for t3 in GLOBAL_T3]
    grouped = [Candidate(10, 14, group, delta) for group in SYSTEM_GROUPS for delta in (-2, 0, 2)]
    return tuple(global_rows + grouped)


def system_group(category: str) -> str:
    """Map only exact formal category names; unknown spellings stay auditable."""
    return FORMAL_CATEGORY_GROUPS.get(category, "unknown")


def selected_candidate_snapshot(gear: Gear) -> dict[str, Any]:
    signature = (gear.slot, gear.main_stat.key, gear.enhance, tuple((stat.key, stat.normalized_value, stat.rolls) for stat in gear.substats))
    cached = _SNAPSHOT_CACHE.get(signature)
    if cached is not None:
        return cached
    rows = evaluate_early_candidates(gear, "normal_85")
    selected = next((row for row in rows if row["qualified"]), None)
    if selected is None:
        selected = next((row for row in rows if row["formal_terminal_formula_available"] and row["current_valid_substat_count"] >= 2), None)
    if selected is None:
        value = {"category": "unknown", "system_group": "unknown", "effective_gs": 0.0, "current_valid": 0, "probability": 0.0, "conversion_value": 0.0, "candidate": None}
        _SNAPSHOT_CACHE[signature] = value
        return value
    value = {
        "category": str(selected["category"]),
        "system_group": system_group(str(selected["category"])),
        # All four values below intentionally come from this exact candidate.
        "effective_gs": float(selected["current_pre_reforge_gs"]),
        "current_valid": int(selected["current_valid_substat_count"]),
        "probability": float(selected["terminal_reach_probability"]),
        "conversion_value": float(selected.get("conversion_max_value") or 0.0),
        "candidate": selected,
    }
    _SNAPSHOT_CACHE[signature] = value
    return value


def _threshold(candidate: Candidate, checkpoint: int, features: dict[str, Any]) -> int:
    base = candidate.t0 if checkpoint == 0 else candidate.t3
    return base + candidate.delta if candidate.system_group != "global" and features["system_group"] == candidate.system_group else base


def action(current_action: str, checkpoint: int, features: dict[str, Any], candidate: Candidate | None) -> str:
    if candidate is None or current_action == "stop":
        return current_action
    rule = SafeStopRule(float(_threshold(candidate, checkpoint, features)), 2, 0.002 if checkpoint == 0 else 0.01, 0.0)
    return action_for_rule(current_action, features, rule)


def _annotate(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        item["features"] = selected_candidate_snapshot(Gear.from_dict(item["gear"]))
        out.append(item)
    return out


def metrics(rows: Iterable[dict[str, Any]], candidate: Candidate | None) -> dict[str, Any]:
    rows = list(rows)
    total = sum(float(row["weight"]) for row in rows)
    stopped = [(row, action(str(row["current_action"]), int(row["checkpoint"]), row["features"], candidate)) for row in rows]
    false = [(row, act) for row, act in stopped if act == "stop" and row["oracle_label"] == "clear_positive"]
    regret = sum(float(row["weight"]) * (max(0.0, float(row["oracle"]["utility_margin"])) if act == "stop" else max(0.0, -float(row["oracle"]["utility_margin"]))) for row, act in stopped)
    positive_weight = sum(float(row["weight"]) for row in rows if row["oracle_label"] == "clear_positive")
    false_weight = sum(float(row["weight"]) for row, _ in false)
    return {
        "state_weight": total,
        "stopped_weight": sum(float(row["weight"]) for row, act in stopped if act == "stop"),
        "clear_positive_false_stop_count": len(false),
        "clear_positive_false_stop_probability_mass": false_weight,
        "clear_positive_false_stop_utility_loss": sum(float(row["weight"]) * float(row["oracle"]["utility_margin"]) for row, _ in false),
        "clear_positive_recall": 1.0 - false_weight / positive_weight if positive_weight else 1.0,
        "total_regret": regret,
        "saved_next_node_stamina": sum(float(row["weight"]) * float(row["oracle"]["forced_continue_stamina"]) for row, act in stopped if act == "stop"),
    }


def prepare(records: Path, resume: Path, workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    # New resume is mandatory.  Exact oracle labels are recomputed here rather
    # than reading Phase A matrix shards.
    phase_a.STUDY_ID = STUDY_ID
    phase_a.SCHEMA_VERSION = SCHEMA_VERSION
    base = load_real_plus0(records, "development")
    plus0_states = phase_a.plus0_states(base)
    plus0, r0 = phase_a.evaluate_cached(plus0_states, resume_dir=resume, partition="phase_b", node="plus0_candidate_consistent", workers=workers)
    all3 = phase_a._all_plus3_states(base)
    # Individual branch groups make every Phase B result resumable.
    all3 = [{**row, "sample_id": f"{row['sample_id']}:{row['state_id']}"} for row in all3]
    plus3, r3 = phase_a.evaluate_cached(all3, resume_dir=resume, partition="phase_b", node="plus3_candidate_consistent", workers=workers)
    return _annotate(plus0), _annotate(plus3), {"plus0": r0, "plus3": r3, "base_count": len(base)}


def matrix(plus0: list[dict[str, Any]], plus3: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for candidate in candidates():
        m0 = metrics(plus0, candidate)
        passed_ids = {row["instance_id"] for row in plus0 if action(str(row["current_action"]), 0, row["features"], candidate) != "stop"}
        m3 = metrics([row for row in plus3 if row["instance_id"] in passed_ids], candidate)
        result[candidate.key] = {"candidate": asdict(candidate), "plus0": m0, "plus3": m3, "publication_gate": m0["clear_positive_false_stop_count"] == 0 and m3["clear_positive_false_stop_count"] == 0}
    return result


def _gear_action(gear: Gear, candidate: Candidate | None) -> str:
    current = _formal_action(gear, GEAR_SOURCE)
    return action(current, gear.enhance, selected_candidate_snapshot(gear), candidate)


def _outcome_zero() -> dict[str, Any]:
    return {"start_checkpoint": 0, "stop_checkpoint": 0, "net_stamina": 0.0, "net_gold": 0.0, "costs": {}}


def _epic_flow(gear: Gear, candidates_: tuple[Candidate, ...], runs: int, seed: int) -> dict[str, Any]:
    keys = (CURRENT_KEY,) + tuple(item.key for item in candidates_)
    totals = {key: _empty_flow() for key in keys}
    for branch_index, branch in enumerate(enumerate_normal_epic_plus3(gear)):
        base_to_three = _flow(gear, {0: gear, 3: branch.gear}, {"start_checkpoint": 0, "stop_checkpoint": 3, "net_stamina": 0.0, "net_gold": 0.0, "costs": {}})
        formal_at_three = _gear_action(branch.gear, None)
        later_flows: list[dict[str, float]] = []
        if formal_at_three != "stop":
            for path in simulate_paths(branch.gear, "normal_85", runs, seed * 1_000_003 + branch_index * 1009):
                outcome = simulate_strategy_path(path, "normal_85", Strategy("phase_b", "offline", lambda _f: "stop"), early_action=lambda _state: formal_at_three, formal_followup=lambda state: formal_followup_action(state, "normal_85"))
                later_flows.append(_flow(branch.gear, path, outcome))
        for candidate in (None,) + candidates_:
            key = CURRENT_KEY if candidate is None else candidate.key
            if _gear_action(gear, candidate) == "stop":
                phase_a._add(totals[key], _flow(gear, {0: gear}, _outcome_zero()), float(branch.probability)); continue
            phase_a._add(totals[key], base_to_three, float(branch.probability))
            if _gear_action(branch.gear, candidate) == "stop":
                continue
            for flow in later_flows:
                phase_a._add(totals[key], flow, float(branch.probability) / runs)
    return {"paths": 1.0, "candidates": totals}


def _source_hash(*paths: Path) -> str:
    return _stable_hash({str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths})


def _base_hashes() -> dict[str, str]:
    return {
        "base_builder_hash": sha256(Path(__file__).read_bytes()).hexdigest(),
        "formal_policy_hash": _source_hash(ROOT / "tools" / "epic_non_speed_early_policy_pareto.py", ROOT / "src" / "e7_enhance" / "enhance_policy.py", ROOT / "src" / "e7_enhance" / "strategy_defaults.py"),
        "roll_table_hash": _source_hash(ROOT / "tools" / "epic_plus3_exact_branches.py"),
        "resource_model_hash": _source_hash(ROOT / "src" / "e7_enhance" / "resource_model.py", ROOT / "src" / "e7_enhance" / "calibration.py"),
    }


def _base_path(resume: Path, rank: str, seed: int, gear_index: int) -> Path:
    return resume / JOINT_DIRECTORY / "base" / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}.json"


def _base_input_hash(*, rank: str, seed: int, gear: Gear, runs: int, hashes: dict[str, str]) -> str:
    return _stable_hash({"study": STUDY_ID, "joint_schema_version": JOINT_SCHEMA_VERSION, "rank": rank, "seed": seed, "gear": gear.to_dict(), "runs": runs, **hashes})


def _valid_base_shard(path: Path, *, rank: str, seed: int, gear_index: int, input_hash: str, hashes: dict[str, str]) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        payload.get("status") == "complete" and payload.get("schema_version") == JOINT_SCHEMA_VERSION
        and payload.get("rank") == rank and payload.get("seed") == seed and payload.get("gear_index") == gear_index
        and payload.get("input_hash") == input_hash and all(payload.get(key) == value for key, value in hashes.items())
    )


def _build_epic_base(gear: Gear, runs: int, seed: int) -> dict[str, Any]:
    """The only location that simulates +3 onward formal paths for an Epic gear/seed."""
    branches: list[dict[str, Any]] = []
    start_formal_action = _formal_action(gear, GEAR_SOURCE)
    start_features = selected_candidate_snapshot(gear)
    for branch_index, branch in enumerate(enumerate_normal_epic_plus3(gear)):
        base_to_three = _flow(gear, {0: gear, 3: branch.gear}, {"start_checkpoint": 0, "stop_checkpoint": 3, "net_stamina": 0.0, "net_gold": 0.0, "costs": {}})
        formal_at_three = _formal_action(branch.gear, GEAR_SOURCE)
        branch_features = selected_candidate_snapshot(branch.gear)
        later_flows: list[dict[str, float]] = []
        if formal_at_three != "stop":
            for path in simulate_paths(branch.gear, "normal_85", runs, seed * 1_000_003 + branch_index * 1009):
                outcome = simulate_strategy_path(path, "normal_85", Strategy("phase_b", "offline", lambda _f: "stop"), early_action=lambda _state: formal_at_three, formal_followup=lambda state: formal_followup_action(state, "normal_85"))
                later_flows.append(_flow(branch.gear, path, outcome))
        branches.append({"probability": float(branch.probability), "gear": branch.gear.to_dict(), "formal_action": formal_at_three, "features": branch_features, "base_to_three": base_to_three, "later_flows": later_flows})
    return {"paths": 1.0, "start_formal_action": start_formal_action, "start_features": start_features, "branches": branches}


def _epic_flow_from_base(gear: Gear, candidate: Candidate | None, base: dict[str, Any], runs: int) -> dict[str, float]:
    total = _empty_flow()
    action0 = action(str(base["start_formal_action"]), 0, base["start_features"], candidate)
    for branch in base["branches"]:
        probability = float(branch["probability"])
        if action0 == "stop":
            phase_a._add(total, _flow(gear, {0: gear}, _outcome_zero()), probability)
            continue
        phase_a._add(total, branch["base_to_three"], probability)
        if action(str(branch["formal_action"]), 3, branch["features"], candidate) == "stop":
            continue
        for flow in branch["later_flows"]:
            phase_a._add(total, flow, probability / runs)
    return total


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _candidate_hash(key: str, candidate: Candidate | None) -> str:
    return _stable_hash({"study": STUDY_ID, "joint_schema_version": JOINT_SCHEMA_VERSION, "key": key, "candidate": asdict(candidate) if candidate else None})


def _joint_path(resume: Path, candidate_key: str, rank: str, seed: int, gear_index: int) -> Path:
    return resume / JOINT_DIRECTORY / candidate_key / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}.json"


def _joint_input_hash(*, candidate_key: str, candidate_hash: str, rank: str, seed: int, gear: Gear, runs: int) -> str:
    return _stable_hash({
        "study": STUDY_ID,
        "joint_schema_version": JOINT_SCHEMA_VERSION,
        "candidate_key": candidate_key,
        "candidate_hash": candidate_hash,
        "rank": rank,
        "seed": seed,
        "gear": gear.to_dict(),
        "runs": runs,
        "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "official_plus3_branch_model": "enumerate_normal_epic_plus3_probability_weighted",
        "heroic_component": "released_m1",
    })


def _valid_joint_shard(path: Path, *, candidate_hash: str, input_hash: str, seed: int, rank: str, gear_index: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        payload.get("status") == "complete"
        and payload.get("schema_version") == JOINT_SCHEMA_VERSION
        and payload.get("candidate_hash") == candidate_hash
        and payload.get("input_hash") == input_hash
        and payload.get("seed") == seed
        and payload.get("rank") == rank
        and payload.get("gear_index") == gear_index
    )


def _joint_worker(job: dict[str, Any]) -> list[str]:
    """Generate common Epic paths once, but persist one independently-valid shard per candidate."""
    entries: list[dict[str, Any]] = job["entries"]
    started = time.monotonic()
    base_path = Path(job["base_path"])
    base_hit = _valid_base_shard(base_path, rank=job["rank"], seed=job["seed"], gear_index=job["gear_index"], input_hash=job["base_input_hash"], hashes=job["base_hashes"])
    if base_hit:
        base = json.loads(base_path.read_text(encoding="utf-8"))["base"]
    elif job["rank"] == "Epic":
        base = _build_epic_base(job["gear"], job["runs"], job["seed"])
    else:
        base = {"paths": 1.0, "flow": _heroic_shard(job["gear"], job["runs"], job["seed"])["policies"]["released_m1"]}
    if not base_hit:
        _atomic_json(base_path, {"status": "complete", "schema_version": JOINT_SCHEMA_VERSION, "study": STUDY_ID, "rank": job["rank"], "seed": job["seed"], "gear_index": job["gear_index"], "input_hash": job["base_input_hash"], **job["base_hashes"], "base": base})
    if job["rank"] == "Epic":
        flows = {entry["candidate_key"]: _epic_flow_from_base(job["gear"], Candidate(**entry["candidate"]) if entry["candidate"] is not None else None, base, job["runs"]) for entry in entries}
    else:
        flows = {HEROIC_SHARED_KEY: base["flow"]}
    elapsed = time.monotonic() - started
    written: list[str] = []
    for entry in entries:
        candidate_key = entry["candidate_key"]
        payload = {
            "status": "complete",
            "schema_version": JOINT_SCHEMA_VERSION,
            "study": STUDY_ID,
            "candidate_key": candidate_key,
            "candidate_hash": entry["candidate_hash"],
            "input_hash": entry["input_hash"],
            "seed": entry["seed"],
            "rank": entry["rank"],
            "gear_index": entry["gear_index"],
            "runs": job["runs"],
            "paths": 1.0,
            "flow": flows[candidate_key],
            "base_cache_hit": base_hit,
            "base_elapsed_seconds": elapsed,
        }
        _atomic_json(Path(entry["path"]), payload)
        written.append(str(entry["path"]))
    return written


def _run_joint_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if not jobs:
        return
    grouped: dict[tuple[str, int, int], dict[str, Any]] = {}
    for entry in jobs:
        key = (entry["rank"], entry["seed"], entry["gear_index"])
        grouped.setdefault(key, {"rank": entry["rank"], "seed": entry["seed"], "gear_index": entry["gear_index"], "gear": entry["gear"], "runs": entry["runs"], "base_path": entry["base_path"], "base_hashes": entry["base_hashes"], "base_input_hash": entry["base_input_hash"], "entries": []})["entries"].append(entry)
    workloads = list(grouped.values())
    if workers == 1:
        for job in workloads:
            _joint_worker(job)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(executor.map(_joint_worker, workloads))


def _parse_csv(value: str | None, *, allowed: set[str] | None = None) -> set[str] | None:
    if value is None:
        return None
    parsed = {item.strip() for item in value.split(",") if item.strip()}
    if allowed is not None and not parsed <= allowed:
        unknown = ", ".join(sorted(parsed - allowed))
        raise ValueError(f"unknown selection: {unknown}")
    return parsed


def _joint_expected(
    matrix_: dict[str, Any], base: list[Gear], heroic: list[Gear], *, runs: int,
) -> tuple[dict[tuple[str, str, int, int], dict[str, Any]], list[dict[str, Any]]]:
    candidates_by_key = {key: Candidate(**row["candidate"]) for key, row in matrix_.items()}
    base_hashes = _base_hashes()
    candidate_specs: list[tuple[str, Candidate | None, str, list[Gear]]] = [(CURRENT_KEY, None, "Epic", base)]
    candidate_specs.extend((key, candidate, "Epic", base) for key, candidate in candidates_by_key.items())
    # Heroic M1 is intentionally a single shared component, not recomputed once per Epic candidate.
    candidate_specs.append((HEROIC_SHARED_KEY, None, "Heroic", heroic))
    expected: dict[tuple[str, str, int, int], dict[str, Any]] = {}
    jobs: list[dict[str, Any]] = []
    for candidate_key, candidate, rank, gears in candidate_specs:
        candidate_hash = _candidate_hash(candidate_key, candidate)
        for seed in SEEDS:
            for gear_index, gear in enumerate(gears):
                input_hash = _joint_input_hash(candidate_key=candidate_key, candidate_hash=candidate_hash, rank=rank, seed=seed, gear=gear, runs=runs)
                base_input_hash = _base_input_hash(rank=rank, seed=seed, gear=gear, runs=runs, hashes=base_hashes)
                expected[(candidate_key, rank, seed, gear_index)] = {
                    "candidate_key": candidate_key,
                    "candidate": asdict(candidate) if candidate else None,
                    "candidate_hash": candidate_hash,
                    "input_hash": input_hash,
                    "rank": rank,
                    "seed": seed,
                    "gear_index": gear_index,
                    "gear": gear,
                    "base_hashes": base_hashes,
                    "base_input_hash": base_input_hash,
                }
    return expected, jobs


def _select_joint_jobs(
    expected: dict[tuple[str, str, int, int], dict[str, Any]], resume: Path, *, runs: int,
    selected_candidates: set[str] | None, selected_seeds: set[int] | None, selected_ranks: set[str] | None,
    gear_start: int | None, gear_end: int | None, shard_start: int | None, shard_end: int | None,
) -> tuple[list[dict[str, Any]], int]:
    missing: list[dict[str, Any]] = []
    skipped = 0
    for item in expected.values():
        path = _joint_path(resume, item["candidate_key"], item["rank"], item["seed"], item["gear_index"])
        if _valid_joint_shard(path, candidate_hash=item["candidate_hash"], input_hash=item["input_hash"], seed=item["seed"], rank=item["rank"], gear_index=item["gear_index"]):
            skipped += 1
            continue
        missing.append({**item, "runs": runs, "path": str(path), "base_path": str(_base_path(resume, item["rank"], item["seed"], item["gear_index"]))})
    filtered = [
        job for job in missing
        if (selected_candidates is None or job["candidate_key"] in selected_candidates)
        and (selected_seeds is None or job["seed"] in selected_seeds)
        and (selected_ranks is None or job["rank"] in selected_ranks)
        and (gear_start is None or job["gear_index"] >= gear_start)
        and (gear_end is None or job["gear_index"] <= gear_end)
    ]
    if shard_start is not None or shard_end is not None:
        first = 0 if shard_start is None else shard_start
        last = len(filtered) - 1 if shard_end is None else shard_end
        filtered = filtered[first:last + 1]
    return filtered, skipped


def _sum_joint_seed(
    resume: Path, expected: dict[tuple[str, str, int, int], dict[str, Any]], *, candidate_key: str, rank: str, seed: int,
) -> dict[str, Any]:
    total = _empty_flow()
    count = 0
    selected = [item for item in expected.values() if item["candidate_key"] == candidate_key and item["rank"] == rank and item["seed"] == seed]
    for item in selected:
        path = _joint_path(resume, candidate_key, rank, seed, item["gear_index"])
        if not _valid_joint_shard(path, candidate_hash=item["candidate_hash"], input_hash=item["input_hash"], seed=seed, rank=rank, gear_index=item["gear_index"]):
            raise RuntimeError(f"incomplete Phase B joint shard: {path}")
        flow = json.loads(path.read_text(encoding="utf-8"))["flow"]
        phase_a._add(total, flow)
        count += 1
    return {"flow": total, "paths": count}


def _joint_complete(resume: Path, expected: dict[tuple[str, str, int, int], dict[str, Any]]) -> bool:
    return all(
        _valid_joint_shard(
            _joint_path(resume, item["candidate_key"], item["rank"], item["seed"], item["gear_index"]),
            candidate_hash=item["candidate_hash"], input_hash=item["input_hash"], seed=item["seed"], rank=item["rank"], gear_index=item["gear_index"],
        )
        for item in expected.values()
    )


def _flow_summary(
    matrix_: dict[str, Any], records: Path, source: Path, resume: Path, *, runs: int, workers: int,
    selected_candidates: set[str] | None = None, selected_seeds: set[int] | None = None, selected_ranks: set[str] | None = None,
    gear_start: int | None = None, gear_end: int | None = None, shard_start: int | None = None, shard_end: int | None = None,
) -> dict[str, Any]:
    base = [Gear.from_dict(row["gear"]) for row in load_real_plus0(records, "development")]
    heroic = _source_rank_gears(json.loads(source.read_text(encoding="utf-8")), "Heroic")
    expected, _ = _joint_expected(matrix_, base, heroic, runs=runs)
    jobs, skipped = _select_joint_jobs(
        expected, resume, runs=runs, selected_candidates=selected_candidates, selected_seeds=selected_seeds,
        selected_ranks=selected_ranks, gear_start=gear_start, gear_end=gear_end, shard_start=shard_start, shard_end=shard_end,
    )
    _run_joint_jobs(jobs, workers)
    execution = {"expected_shards": len(expected), "scheduled_shards": len(jobs), "existing_complete_shards": skipped, "complete": _joint_complete(resume, expected), "resume_dir": str((resume / JOINT_DIRECTORY).resolve().relative_to(ROOT))}
    if not execution["complete"]:
        return {"complete": False, "execution": execution}
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    per_seed: dict[str, Any] = {}
    all_keys = (CURRENT_KEY,) + tuple(matrix_)
    for seed in SEEDS:
        heroic_total = _sum_joint_seed(resume, expected, candidate_key=HEROIC_SHARED_KEY, rank="Heroic", seed=seed)
        per_seed[str(seed)] = {}
        for yield_name, multiplier in YIELD_VARIATIONS.items():
            per_seed[str(seed)][yield_name] = {}
            for key in all_keys:
                epic_total = _sum_joint_seed(resume, expected, candidate_key=key, rank="Epic", seed=seed)
                merged = {
                    field: float(epic_total["flow"][field]) / epic_total["paths"] + float(batch["expected_output_by_rank"]["Heroic"]) * float(multiplier) * float(heroic_total["flow"][field]) / heroic_total["paths"]
                    for field in FLOW_WITH_METRICS
                }
                pool = explicit_batch_resource_pool(source_gold=float(batch["expected_source_gold_per_batch"]), source_lower_stones=float(batch["expected_lower_stone_units"]), powder_base_exp=merged["powder_units"] * 100, lower_stone_units=merged["lower_stone_units"], material_gold=merged["material_gold"], conversion_gold=merged["conversion_gold"], sell_gold=merged["sell_gold"], sell_exp=merged["sell_exp_adjusted"], material_scarcity_exp=merged["material_exp_adjusted"], lower_stone_adjusted_exp=merged["lower_stone_adjusted_exp"])
                total = float(pool["total_stamina"])
                cycles = 100000 / total
                accounting = {"total_stamina_positive": total >= 85.0, "stamina_partition_error": abs((cycles * 85.0) + (cycles * float(pool["saint_supplement_stamina"])) - 100000.0)}
                per_seed[str(seed)][yield_name][key] = {"formal_rate_per_100": 100 * merged["value_sum"] / total, "per_100k": {field: cycles * merged[field] for field in FLOW_WITH_METRICS}, "rift_stamina_per_100k": cycles * 85, "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]), "cycles_per_100k": cycles, "resource_pool": pool, "accounting": accounting}
    return {"complete": True, "execution": execution, "batch": batch, "per_seed": per_seed}


def _ci(values: list[float]) -> dict[str, Any]:
    from math import sqrt
    from statistics import mean, stdev
    center=mean(values); half=_t95(len(values))*stdev(values)/sqrt(len(values)) if len(values)>1 else 0.0
    return {"mean":center,"interval95":[center-half,center+half]}


def summarize_joint(per_seed: dict[str, Any], matrix_: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for yield_name in YIELD_VARIATIONS:
        baseline = [per_seed[str(seed)][yield_name][CURRENT_KEY]["formal_rate_per_100"] for seed in SEEDS]
        rows: dict[str, Any] = {}
        for key in (CURRENT_KEY,) + tuple(matrix_):
            values = [per_seed[str(seed)][yield_name][key]["formal_rate_per_100"] for seed in SEEDS]
            per_100k = {
                field: _ci([per_seed[str(seed)][yield_name][key]["per_100k"][field] for seed in SEEDS])
                for field in FLOW_WITH_METRICS
            }
            rift = _ci([per_seed[str(seed)][yield_name][key]["rift_stamina_per_100k"] for seed in SEEDS])
            saint = _ci([per_seed[str(seed)][yield_name][key]["saint_stamina_per_100k"] for seed in SEEDS])
            cycles = _ci([per_seed[str(seed)][yield_name][key]["cycles_per_100k"] for seed in SEEDS])
            errors = [per_seed[str(seed)][yield_name][key]["accounting"]["stamina_partition_error"] for seed in SEEDS]
            rows[key] = {
                "formal_rate_per_100": _ci(values),
                "candidate_minus_current": _ci([value - baseline_value for value, baseline_value in zip(values, baseline)]),
                "per_100k": per_100k,
                "rift_stamina_per_100k": rift,
                "saint_stamina_per_100k": saint,
                "cycles_per_100k": cycles,
                "max_stamina_partition_error": max(errors),
            }
        order = sorted(rows, key=lambda key: (-float(rows[key]["formal_rate_per_100"]["mean"]), key))
        out[yield_name] = {"ranking": order, "rows": rows}
    return out


def markdown(data: dict[str, Any]) -> str:
    lines=["# Epic Threshold Matrix Phase B Formal R10", "", "This is the candidate-consistent formal `runs=10` study. The prior `runs=1` output is `pilot_not_for_release` and is not used for ranking or release.", "", "Phase A remains the immutable `global_uniform_phase_a` historical comparison; Phase B corrects the selected-candidate effective-GS consistency issue. No production policy is changed.", "", "## Global References", "", "| route | +0 false stops | +3 false stops | +0/+3 false probability mass | +0/+3 utility loss | +0/+3 regret | publish gate |", "|---|---:|---:|---:|---:|---:|---|"]
    for c in (Candidate(10,14),Candidate(12,17)):
        row=data["matrix"][c.key]; a,b=row["plus0"],row["plus3"]
        lines.append(f"| {c.key} | {a['clear_positive_false_stop_count']} | {b['clear_positive_false_stop_count']} | {a['clear_positive_false_stop_probability_mass']+b['clear_positive_false_stop_probability_mass']:.6f} | {a['clear_positive_false_stop_utility_loss']+b['clear_positive_false_stop_utility_loss']:.6f} | {a['total_regret']+b['total_regret']:.6f} | {'pass' if row['publication_gate'] else 'blocked'} |")
    lines.extend(["", "## System One-Factor Rows", "", "Each row changes only one system group; delta=0 is the corrected global 10/14 reference for that group.", "", "| group | delta | +0 false stops | +3 false stops | utility loss | publish gate |", "|---|---:|---:|---:|---:|---|"])
    for group in SYSTEM_GROUPS:
        for delta in (-2,0,2):
            row=data["matrix"][Candidate(10,14,group,delta).key];a,b=row["plus0"],row["plus3"]
            lines.append(f"| {group} | {delta:+d} | {a['clear_positive_false_stop_count']} | {b['clear_positive_false_stop_count']} | {a['clear_positive_false_stop_utility_loss']+b['clear_positive_false_stop_utility_loss']:.6f} | {'pass' if row['publication_gate'] else 'blocked'} |")
    lines.extend(["", "## Joint Pool", "", "All 15 global rows and all system one-factor rows are compared offline. Publication gates do not remove rows from this section.", "", "| Heroic yield | route | value / 100 stamina delta 95% CI |", "|---|---|---:|"])
    for name, summary in data["joint_summary"].items():
        for key in summary["ranking"]:
            item=summary["rows"][key]
            ci=item["candidate_minus_current"]["interval95"]
            lines.append(f"| {name} | {key} | [{ci[0]:.6f}, {ci[1]:.6f}] |")
    baseline_summary = data["joint_summary"]["baseline"]["rows"]
    lines.extend(["", "## Per 100,000 Total Stamina", "", "| route | formal value | native 75+ | converted 75+ | 22+ | Rift stamina | Saint 3-7 stamina | cycles |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for key in (CURRENT_KEY, Candidate(10,14).key, Candidate(12,17).key):
        row=baseline_summary[key];m=row["per_100k"];lines.append(f"| {key} | {m['value_sum']['mean']:.3f} | {m['native_heirloom']['mean']:.3f} | {m['converted_heirloom']['mean']:.3f} | {m['speed22']['mean']:.3f} | {row['rift_stamina_per_100k']['mean']:.3f} | {row['saint_stamina_per_100k']['mean']:.3f} | {row['cycles_per_100k']['mean']:.3f} |")
    lines.extend(["", "All per-100,000 values above are five-seed means. Their component 95% intervals and every candidate's ranking are retained in the JSON.", "", "## Status", "", "- Candidate and code hashes are frozen in the JSON only after every expected joint shard is present.", "- New holdout collection remains paused. No candidate is released."])
    return "\n".join(lines)+"\n"


def run(
    records: Path, source: Path, resume: Path, runs: int, workers: int, *, node_resume: Path = PILOT_RESUME,
    selected_candidates: set[str] | None = None, selected_seeds: set[int] | None = None, selected_ranks: set[str] | None = None,
    gear_start: int | None = None, gear_end: int | None = None, shard_start: int | None = None, shard_end: int | None = None,
) -> dict[str, Any]:
    plus0, plus3, prep=prepare(records,node_resume,workers)
    matrix_=matrix(plus0,plus3)
    joint = _flow_summary(
        matrix_, records, source, resume, runs=runs, workers=workers, selected_candidates=selected_candidates,
        selected_seeds=selected_seeds, selected_ranks=selected_ranks, gear_start=gear_start, gear_end=gear_end,
        shard_start=shard_start, shard_end=shard_end,
    )
    base = {"study":STUDY_ID,"schema_version":SCHEMA_VERSION,"data_isolation":{"development_only":True,"old_phase_a_report_reused":False,"holdout_collection":"paused"},"preparation":prep,"matrix":matrix_,"joint_execution":joint["execution"]}
    if not joint["complete"]:
        return {**base, "complete": False}
    freeze={
        "phase_a_reference":"global_uniform_phase_a", "study":STUDY_ID, "schema_version":SCHEMA_VERSION,
        "candidate_keys":list(matrix_), "candidate_hashes":{key:_candidate_hash(key, Candidate(**row["candidate"])) for key,row in matrix_.items()},
        "current_candidate_hash":_candidate_hash(CURRENT_KEY, None), "heroic_shared_candidate_hash":_candidate_hash(HEROIC_SHARED_KEY, None),
        "code_sha256":sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    return {**base,"complete":True,"batch":joint["batch"],"per_seed":joint["per_seed"],"joint_summary":summarize_joint(joint["per_seed"],matrix_),"freeze":freeze}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--records",type=Path,default=ROOT/"manual_acceptance"/"real_sample_records.json")
    parser.add_argument("--source",type=Path,default=ROOT/"samples"/"real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--resume-dir",type=Path,default=DEFAULT_RESUME)
    parser.add_argument("--node-resume-dir",type=Path,default=PILOT_RESUME, help="read-only exact +0/+3 node cache; never used for joint shards")
    parser.add_argument("--runs",type=int,default=10)
    parser.add_argument("--workers",type=int,default=12)
    parser.add_argument("--candidates", help="comma-separated candidate keys; only schedules matching missing Epic shards")
    parser.add_argument("--seeds", help="comma-separated subset of the five frozen seeds")
    parser.add_argument("--ranks", help="comma-separated Epic and/or Heroic")
    parser.add_argument("--gear-start", type=int)
    parser.add_argument("--gear-end", type=int)
    parser.add_argument("--shard-start", type=int, help="zero-based slice start after other filters")
    parser.add_argument("--shard-end", type=int, help="zero-based slice end after other filters")
    parser.add_argument("--max-shards", type=int, help="cap this invocation after other filters; use repeated invocations to resume")
    parser.add_argument("--json-output",type=Path,default=DEFAULT_JSON)
    parser.add_argument("--markdown-output",type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args()
    candidate_keys = {CURRENT_KEY, HEROIC_SHARED_KEY, *(candidate.key for candidate in candidates())}
    selected_candidates = _parse_csv(args.candidates, allowed=candidate_keys)
    selected_seed_text = _parse_csv(args.seeds)
    selected_seeds = {int(value) for value in selected_seed_text} if selected_seed_text is not None else None
    if selected_seeds is not None and not selected_seeds <= set(SEEDS):
        raise ValueError("--seeds must be selected from the five frozen seeds")
    selected_ranks = _parse_csv(args.ranks, allowed={"Epic", "Heroic"})
    if args.max_shards is not None and args.max_shards < 1:
        raise ValueError("--max-shards must be positive")
    effective_shard_end = args.shard_end
    if args.max_shards is not None:
        cap_end = (args.shard_start or 0) + args.max_shards - 1
        effective_shard_end = min(effective_shard_end, cap_end) if effective_shard_end is not None else cap_end
    data=run(args.records,args.source,args.resume_dir,max(1,args.runs),max(1,args.workers),node_resume=args.node_resume_dir,selected_candidates=selected_candidates,selected_seeds=selected_seeds,selected_ranks=selected_ranks,gear_start=args.gear_start,gear_end=args.gear_end,shard_start=args.shard_start,shard_end=effective_shard_end)
    if not data["complete"]:
        print(json.dumps({"complete":False,"execution":data["joint_execution"]},ensure_ascii=False))
        return
    _atomic_json(args.json_output,data)
    args.markdown_output.write_text(markdown(data),encoding="utf-8")
    print(json.dumps({"complete":True,"json":str(args.json_output),"report":str(args.markdown_output),"execution":data["joint_execution"]},ensure_ascii=False))


if __name__ == "__main__": main()
