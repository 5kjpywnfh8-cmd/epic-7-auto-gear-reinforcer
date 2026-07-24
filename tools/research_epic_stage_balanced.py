"""Offline ablation of separate +0/+3 balanced Epic candidates.

This is research only.  It does not alter released policy, lambda, scoring,
rules, GUI, existing resume directories, or the frozen prospective batch.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_simulator import CHECKPOINTS
from src.e7_enhance.lightweight_calibration import STAT_KEY_LABELS
from src.e7_enhance.models import stat_key
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, METRIC_FIELDS, _flow
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    _features,
    _gear_from_item,
    _heroic_base_action,
    _source_rank_gears,
    _speed_hard_route,
    build_partition,
    formal_followup_action,
    simulate_paths,
    summarize_incremental_cost,
)
from tools.epic_non_speed_dp_oracle_audit import collect_audit_cases
from tools.research_external_threshold_d import RESEARCH_LAMBDA, _random_seed
from tools.research_riftslash_saint_pool import (
    HEROIC_POLICIES,
    SPEED_VALUE_FIELDS,
    YIELD_VARIATIONS,
    _atomic_json,
    _t95,
    explicit_batch_resource_pool,
)

SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
STAGE_KEYS = (
    "B_global_current_gs", "B_stage_gs", "B_stage_hit", "B_stage_structure",
    "B_stage_category", "B_stage_probability", "B_stage_conversion",
)
ABC_METRICS_RESUME = ROOT / "reports" / "abc_terminal_metrics_resume_20260713"
ORACLE_REPORT = ROOT / "reports" / "epic_non_speed_dp_oracle_research_lambda_20260713.json"
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class StagePolicy:
    key: str
    plus0: tuple[float, float]
    plus3: tuple[float, float]
    use_hit: bool = False
    use_structure: bool = False
    use_category: bool = False
    use_probability: bool = False
    use_conversion: bool = False


# The grid is frozen in the result JSON.  The selected pair is calibrated per
# checkpoint: +0 remains the inexpensive broad screen, while +3 is stricter
# because the next step costs roughly four times as much.
CALIBRATION_GRID = {
    "plus0": {"continue": [28, 30, 32], "review": [16, 18, 20]},
    "plus3": {"continue": [30, 32, 34, 36], "review": [20, 22, 24, 26]},
    "selection": {"plus0": [30, 18], "plus3": [34, 22], "criterion": "separate-stage common-trajectory ablation; retain only stable incremental gains"},
}


POLICIES = (
    StagePolicy("B_global_current_gs", (30, 18), (30, 18)),
    StagePolicy("B_stage_gs", (30, 18), (34, 22)),
    StagePolicy("B_stage_hit", (30, 18), (34, 22), use_hit=True),
    StagePolicy("B_stage_structure", (30, 18), (34, 22), use_hit=True, use_structure=True),
    StagePolicy("B_stage_category", (30, 18), (34, 22), use_hit=True, use_structure=True, use_category=True),
    StagePolicy("B_stage_probability", (30, 18), (34, 22), use_hit=True, use_structure=True, use_category=True, use_probability=True),
    StagePolicy("B_stage_conversion", (30, 18), (34, 22), use_hit=True, use_structure=True, use_category=True, use_probability=True, use_conversion=True),
)


def _downgrade(action: str) -> str:
    return "cautious_continue" if action == "continue" else "stop"


def stage_action(policy: StagePolicy, checkpoint: int, features: dict[str, Any]) -> str:
    """Pure current-state action.  No prior screenshot or future result is used."""
    continue_at, review_at = policy.plus0 if checkpoint == 0 else policy.plus3
    score = float(features["effective_gs"])
    action = "continue" if score >= continue_at else "cautious_continue" if score >= review_at else "stop"
    if checkpoint != 3:
        return action
    if policy.use_hit and not bool(features["hit_target"]):
        action = _downgrade(action)
    if policy.use_structure:
        if int(features["current_valid"]) < 2:
            action = "stop"
        elif int(features["current_valid"]) < 3 and not bool(features["slot_limited_three"]):
            action = _downgrade(action)
        elif int(features["feasible_valid"]) < int(features["current_valid"]):
            action = _downgrade(action)
    if policy.use_category:
        tier = int(features["category_tier"])
        if tier >= 2:
            action = _downgrade(action)
        elif tier == 1 and action == "continue":
            action = "cautious_continue"
    if policy.use_probability:
        probability = float(features["probability"])
        if probability < 0.015:
            action = "stop"
        elif probability < 0.040 and action == "continue":
            action = "cautious_continue"
    if policy.use_conversion and action == "stop":
        # A conversion only earns a review when a legal max conversion has
        # positive terminal value after its explicit 100k-gold cost exists.
        if bool(features["conversion_legal"]) and float(features["conversion_value"]) >= 6.0:
            action = "cautious_continue"
    return action


def _category_tier(category: str) -> int:
    if category in {"输出", "抗坦", "纯肉", "命坦"}:
        return 0
    if category == "双效":
        return 2
    return 1


def stage_features(gear: Any) -> dict[str, Any]:
    features = dict(_features(gear, "normal_85"))
    candidate = features.get("candidate") or {}
    hit_target = False
    if gear.enhance == 3 and gear.roll_history:
        hit_key = stat_key(gear.roll_history[-1].type)
        matched = set(candidate.get("matched_substats") or [])
        hit_target = STAT_KEY_LABELS.get(hit_key, hit_key) in matched
    features.update({
        "hit_target": hit_target,
        "category_tier": _category_tier(str(features.get("category") or "")),
        "conversion_legal": bool(candidate.get("is_conversion_candidate")),
        "conversion_value": float(candidate.get("conversion_max_value") or 0.0),
    })
    return features


def _outcome(path: dict[int, Any], policy: StagePolicy) -> dict[str, Any]:
    start = min(path)
    current = start
    reached = [current]
    actions: dict[int, str] = {}
    while current < 15:
        state = path[current]
        if current in (0, 3):
            action = "continue" if _speed_hard_route(state) else stage_action(policy, current, stage_features(state))
        else:
            action = "continue" if formal_followup_action(state, "normal_85") else "stop"
        actions[current] = action
        if action == "stop":
            break
        current = next(point for point in CHECKPOINTS if point > current)
        reached.append(current)
    costs = summarize_incremental_cost(path[start].slot, path[start].rank, start, current)
    return {"start_checkpoint": start, "stop_checkpoint": current, "actions": actions, "reached_checkpoints": reached, "net_stamina": costs["net_stamina"], "net_gold": costs["net_gold"], "costs": costs}


def _empty_flow() -> dict[str, float]:
    return {field: 0.0 for field in FLOW_WITH_METRICS}


def _shard(gear: Any, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {policy.key: _empty_flow() for policy in POLICIES}
    for path in simulate_paths(gear, "normal_85", runs, random_seed):
        for policy in POLICIES:
            row = _flow(gear, path, _outcome(path, policy))
            for field in FLOW_WITH_METRICS:
                totals[policy.key][field] += row[field]
    return {"paths": float(runs), "candidates": totals}


def _path(resume: Path, seed: int, gear_index: int, chunk: int) -> Path:
    return resume / "shards" / f"seed-{seed}" / f"gear-{gear_index:04d}-chunk-{chunk:03d}.json"


def _valid(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("status") == "complete" and payload.get("schema_version") == SCHEMA_VERSION and payload.get("scope") == "epic_stage_balanced"
    except (OSError, ValueError):
        return False


def _worker(job: dict[str, Any]) -> dict[str, Any]:
    payload = _shard(job["gear"], job["runs"], job["random_seed"])
    payload.update({key: job[key] for key in ("seed", "gear_index", "chunk_index", "runs")})
    payload.update({"status": "complete", "schema_version": SCHEMA_VERSION, "scope": "epic_stage_balanced"})
    return payload


def _jobs(resume: Path, gears: list[Any], runs_per_seed: int, chunk_runs: int) -> tuple[list[dict[str, Any]], int]:
    if runs_per_seed % chunk_runs:
        raise ValueError("runs_per_seed must be divisible by chunk_runs")
    jobs: list[dict[str, Any]] = []
    skipped = 0
    for seed in SEEDS:
        for gear_index, gear in enumerate(gears):
            for chunk in range(runs_per_seed // chunk_runs):
                path = _path(resume, seed, gear_index, chunk)
                if _valid(path):
                    skipped += 1
                    continue
                jobs.append({"seed": seed, "gear": gear, "gear_index": gear_index, "chunk_index": chunk, "runs": chunk_runs, "random_seed": _random_seed(seed, "Epic", gear_index, chunk), "path": str(path)})
    return jobs, skipped


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if not jobs:
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for job, payload in zip(jobs, executor.map(_worker, jobs)):
            _atomic_json(Path(job["path"]), payload)


def _sum_epic(resume: Path, seed: int) -> dict[str, Any]:
    total: dict[str, Any] = {"paths": 0.0, **{key: _empty_flow() for key in STAGE_KEYS}}
    for path in (resume / "shards" / f"seed-{seed}").glob("*.json"):
        if not _valid(path):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        total["paths"] += float(payload["paths"])
        for key, row in payload["candidates"].items():
            for field in FLOW_WITH_METRICS:
                total[key][field] += float(row[field])
    return total


def _sum_heroic(seed: int) -> dict[str, Any]:
    # Read the already completed terminal-metrics replay, never run Heroic.
    directory = ABC_METRICS_RESUME / "shards" / "heroic" / f"seed-{seed}"
    total: dict[str, Any] = {"paths": 0.0, **{policy: _empty_flow() for policy in HEROIC_POLICIES}}
    for path in directory.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("candidate_scope") != "ABC_terminal_metrics":
            continue
        total["paths"] += float(payload["paths"])
        for policy, row in payload["policies"].items():
            for field in FLOW_WITH_METRICS:
                total[policy][field] += float(row[field])
    return total


def _combine(epic: dict[str, float], epic_paths: float, heroic: dict[str, float], heroic_paths: float, yield_count: float) -> dict[str, float]:
    return {field: float(epic[field]) / epic_paths + yield_count * float(heroic[field]) / heroic_paths for field in FLOW_WITH_METRICS}


def _pool(flow: dict[str, float]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    return explicit_batch_resource_pool(
        source_gold=float(batch["expected_source_gold_per_batch"]), source_lower_stones=float(batch["expected_lower_stone_units"]),
        powder_base_exp=flow["powder_units"] * 100, lower_stone_units=flow["lower_stone_units"], material_gold=flow["material_gold"],
        conversion_gold=flow["conversion_gold"], sell_gold=flow["sell_gold"], sell_exp=flow["sell_exp_adjusted"],
        material_scarcity_exp=flow["material_exp_adjusted"], lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
    )


def _pack(flow: dict[str, float], value_field: str) -> dict[str, Any]:
    pool = _pool(flow)
    total = float(pool["total_stamina"])
    return {
        "flow": flow, "pool": pool, "total_stamina": total,
        "value": float(flow[value_field]), "value_rate": 100 * float(flow[value_field]) / total if total else 0.0,
        "formal_value": float(flow["value_sum"]), "formal_rate": 100 * float(flow["value_sum"]) / total if total else 0.0,
        "per_100_batches": {field: 100 * float(flow[field]) for field in METRIC_FIELDS},
        "per_100k_stamina": {field: 100000 * float(flow[field]) / total if total else 0.0 for field in METRIC_FIELDS},
    }


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values)
    if len(values) < 2:
        return {"mean": center, "interval95": [center, center]}
    half = _t95(len(values)) * stdev(values) / sqrt(len(values))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": stdev(values)}


def _oracle_metrics() -> dict[str, Any]:
    oracle = json.loads(ORACLE_REPORT.read_text(encoding="utf-8"))
    rows = collect_audit_cases(records_payload=json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))) ["included"]
    by_id = {str(row["instance_id"]): row["gear"] for row in rows}
    output: dict[str, Any] = {}
    for policy in POLICIES:
        regrets: list[float] = []
        false_stop = false_enhance = 0
        missed_value = 0.0
        positive = recalled = 0
        for item in oracle["cases"]:
            gear = by_id.get(str(item["instance_id"]))
            if gear is None:
                continue
            action = stage_action(policy, gear.enhance, stage_features(gear))
            enhance = action != "stop"
            margin = float(item["oracle"]["utility_margin"])
            oracle_enhance = str(item["oracle"]["action"]) != "stop"
            if oracle_enhance:
                positive += 1
                recalled += int(enhance)
            regret = 0.0
            if enhance and not oracle_enhance:
                false_enhance += 1; regret = -margin
            elif not enhance and oracle_enhance:
                false_stop += 1; regret = margin; missed_value += float(item["oracle"]["expected_terminal_value"])
            regrets.append(max(0.0, regret))
        ordered = sorted(regrets)
        p90 = ordered[round((len(ordered) - 1) * .9)] if ordered else 0.0
        output[policy.key] = {"false_stop_count": false_stop, "false_enhance_count": false_enhance, "oracle_positive_recall": recalled / positive if positive else 1.0, "total_regret": sum(regrets), "p90_regret": p90, "max_regret": max(regrets, default=0.0), "missed_terminal_value": missed_value, "sample_count": len(regrets), "non_independent": True}
    return output


def summarize(resume: Path) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    for seed in SEEDS:
        epic, heroic = _sum_epic(resume, seed), _sum_heroic(seed)
        if not epic["paths"] or not heroic["paths"]:
            raise ValueError(f"incomplete shard set for seed {seed}")
        per_seed[str(seed)] = {}
        # This study is intentionally non-speed only. Speed hard-route gear
        # and the old max(formal, speed-value) aggregate belong to the separate
        # 22-speed calibration and must not decide this candidate.
        for heroic_policy in HEROIC_POLICIES:
            for yield_name, multiplier in YIELD_VARIATIONS.items():
                    scenario = f"formal_only/{heroic_policy}/{yield_name}"
                    yield_count = 85.0 / 23.81 * multiplier
                    per_seed[str(seed)][scenario] = {
                        key: _pack(_combine(epic[key], epic["paths"], heroic[heroic_policy], heroic["paths"], yield_count), "value_sum")
                        for key in STAGE_KEYS
                    }
    summary: dict[str, Any] = {}
    for scenario in next(iter(per_seed.values())):
        rates = {key: [per_seed[str(seed)][scenario][key]["value_rate"] for seed in SEEDS] for key in STAGE_KEYS}
        ablations = {}
        for index in range(1, len(STAGE_KEYS)):
            current, previous = STAGE_KEYS[index], STAGE_KEYS[index - 1]
            ablations[f"{current} - {previous}"] = _ci([a - b for a, b in zip(rates[current], rates[previous])])
        summary[scenario] = {"rates": {key: _ci(values) for key, values in rates.items()}, "order": sorted(STAGE_KEYS, key=lambda key: -mean(rates[key])), "ablations": ablations}
    primary = "formal_only/baili_marginal_low/baseline"
    stable = []
    for index in range(1, len(STAGE_KEYS)):
        key = STAGE_KEYS[index]
        intervals = [summary[scenario]["ablations"][f"{key} - {STAGE_KEYS[index - 1]}"]["interval95"] for scenario in summary]
        stable.append({"stage": key, "retained": all(interval[0] > 0 for interval in intervals), "intervals": intervals})
    return {"per_seed": per_seed, "scenarios": summary, "oracle": _oracle_metrics(), "primary_scenario": primary, "stage_retention": stable}


def markdown(data: dict[str, Any]) -> str:
    primary = data["summary"]["scenarios"][data["summary"]["primary_scenario"]]
    lines = ["# Epic 分节点多因素均衡策略研究", "", "仅离线研究。+0/+3 分开决策；速度硬路线与 +6/+9/+12 正式后续策略保持不变。", "", "## 主场景", "", "| 候选 | 含22速价值率/100体力 95% CI | Oracle召回 | 误停 | 总regret |", "|---|---:|---:|---:|---:|"]
    lines = [
        "# Epic \u5206\u8282\u70b9\u591a\u56e0\u7d20\u5747\u8861\u7b56\u7565\u7814\u7a76",
        "",
        "\u4ec5\u79bb\u7ebf\u7814\u7a76\u3002+0/+3 \u5206\u5f00\u51b3\u7b56\uff1b\u672c\u62a5\u544a\u4ec5\u5bf9\u975e\u901f\u5ea6\u6b63\u5f0f\u4f53\u7cfb\u4ef7\u503c\u6392\u5e8f\uff0c22\u901f\u4e13\u9879\u53e6\u884c\u7814\u7a76\u3002",
        "",
        "## \u4e3b\u573a\u666f",
        "",
        "| \u5019\u9009 | \u6b63\u5f0f\u4f53\u7cfb\u4ef7\u503c\u7387/100\u4f53\u529b 95% CI | Oracle\u53ec\u56de | \u8bef\u505c | \u603b regret |",
        "|---|---:|---:|---:|---:|",
    ]
    for key in primary["order"]:
        ci, oracle = primary["rates"][key]["interval95"], data["summary"]["oracle"][key]
        lines.append(f"| {key} | [{ci[0]:.6f}, {ci[1]:.6f}] | {oracle['oracle_positive_recall']:.2%} | {oracle['false_stop_count']} | {oracle['total_regret']:.6f} |")
    lines.extend(["", "## 逐级消融", "", "| 新增因素 | 相对前一层成对95% CI | 跨敏感性保留 |", "|---|---:|---|"])
    retain = {row["stage"]: row["retained"] for row in data["summary"]["stage_retention"]}
    for pair, ci in primary["ablations"].items():
        stage = pair.split(" - ")[0]
        interval = ci["interval95"]
        lines.append(f"| {pair} | [{interval[0]:.6f}, {interval[1]:.6f}] | {'是' if retain[stage] else '否'} |")
    lines.extend(["", "## 产量护栏", "", "原生75+、转换75+、22速、输出60保留为独立产量字段，未相加为训练分数。D 的传家宝和速度单目标优势只作为高投入对照，不等同于综合价值效率。", "", "## 冻结与限制", "", f"- 研究lambda：`{RESEARCH_LAMBDA}`，仅用于已审核45件 Oracle 风险复核，非独立验证。", "- 旧 B 前瞻批次保持 `collecting_blind 0/48`；本报告不创建或替代批次。", "- 只有跨 Heroic 背景、产出率和22速锚点均稳定的新增因素才具备进入后续前瞻门槛的资格。", ""])
    return "\n".join(lines)


def run(source: Path, records: Path, resume: Path, *, runs_per_seed: int, chunk_runs: int, workers: int) -> dict[str, Any]:
    source_data, records_data = json.loads(source.read_text(encoding="utf-8")), json.loads(records.read_text(encoding="utf-8"))
    partition = build_partition(source_data, records_data, blind_size=24, seed=20260712)
    gears = [row["gear"] for row in partition["training"]]
    jobs, skipped = _jobs(resume, gears, runs_per_seed, chunk_runs)
    started = time.monotonic(); _run_jobs(jobs, workers)
    return {"study": "epic_stage_balanced", "seeds": list(SEEDS), "runs_per_gear": runs_per_seed * len(SEEDS), "calibration_grid": CALIBRATION_GRID, "policies": [policy.__dict__ for policy in POLICIES], "execution": {"scheduled_shards": len(jobs), "skipped_shards": skipped, "runtime_seconds": time.monotonic() - started}, "summary": summarize(resume)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Research separate +0/+3 Epic balanced candidates")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "epic_stage_balanced_non_speed_resume_20260713")
    parser.add_argument("--runs-per-seed", type=int, default=1000)
    parser.add_argument("--chunk-runs", type=int, default=500)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "epic_stage_balanced_20260713.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "epic_stage_balanced_20260713.md")
    args = parser.parse_args()
    data = run(args.source, args.records, args.resume_dir, runs_per_seed=args.runs_per_seed, chunk_runs=args.chunk_runs, workers=args.workers)
    _atomic_json(args.json_output, data)
    args.markdown_output.write_text(markdown(data), encoding="utf-8")


if __name__ == "__main__":
    main()
