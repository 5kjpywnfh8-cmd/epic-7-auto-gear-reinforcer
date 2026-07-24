"""Supplement frozen A/B/C studies with terminal production statistics only.

The released strategies and the existing B/D ranking are immutable inputs.
This tool deterministically replays the frozen A/B/C trajectories into a new
resume directory, while D is read from its already-completed D-only shards.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.epic_balanced_prospective import BATCH_ID, _prediction_hash
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    Strategy,
    _heroic_base_action,
    _source_rank_gears,
    _terminal_metrics,
    build_partition,
    formal_followup_action,
    simulate_paths,
    simulate_strategy_path,
    strategies,
    strategy_actions,
)
from tools.external_threshold_strategy import output_effective_gs
from tools.research_external_threshold_d import (
    ABC,
    CHECKPOINTS,
    D_EPIC_BASE,
    D_EPIC_STOP,
    D_FULL,
    D_FLOW_FIELDS,
    FROZEN_RESUME_DIR,
    RESEARCH_LAMBDA,
    _random_seed,
    _sum_d_seed,
)
from tools.research_riftslash_saint_pool import (
    FLOW_FIELDS,
    HEROIC_POLICIES,
    SPEED_VALUE_FIELDS,
    YIELD_VARIATIONS,
    _atomic_json,
    _flow_for_outcome,
    _t95,
    explicit_batch_resource_pool,
)
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata

SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
METRIC_FIELDS = ("native_heirloom", "converted_heirloom", "speed22", "output60")
FLOW_WITH_METRICS = FLOW_FIELDS + METRIC_FIELDS
FROZEN_BATCH = ROOT / "samples" / f"{BATCH_ID}.json"
D_RESUME_DIR = ROOT / "reports" / "external_threshold_d_resume_20260713"
SCHEMA_VERSION = 1


def _empty_flow() -> dict[str, float]:
    return {field: 0.0 for field in FLOW_WITH_METRICS}


def _signature(state: Any) -> tuple[Any, ...]:
    return (state.slot, state.main_stat.key, state.enhance, tuple((s.key, s.normalized_value, s.rolls) for s in state.substats))


def terminal_indicators_for_outcome(path: dict[int, Any], outcome: dict[str, Any]) -> dict[str, float]:
    """Count only actual +15 terminal states; conversion is applied in metrics."""
    if int(outcome["stop_checkpoint"]) != 15:
        return {field: 0.0 for field in METRIC_FIELDS}
    terminal = _terminal_metrics(path[15], "normal_85")
    final = path[15]
    return {
        "native_heirloom": float(terminal["official_substat_gs"] >= 75),
        # _terminal_metrics applies a legal max conversion plan before this
        # value is measured, rather than estimating a score delta.
        "converted_heirloom": float(terminal["converted_official_substat_gs"] >= 75),
        "speed22": float(final.slot != "boot" and terminal["final_speed"] >= 22),
        "output60": float(output_effective_gs(final) >= 60),
    }


def _flow(gear: Any, path: dict[int, Any], outcome: dict[str, Any]) -> dict[str, float]:
    stop = int(outcome["stop_checkpoint"])
    terminal = _terminal_metrics(path[stop], "normal_85")
    conversion = bool(stop == 15 and terminal["conversion_needed"])
    result = dict(_flow_for_outcome(gear, outcome, conversion, terminal))
    result.update(terminal_indicators_for_outcome(path, outcome))
    return result


def _epic_shard(gear: Any, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {key: _empty_flow() for key in ABC}
    early_cache: dict[tuple[Any, ...], dict[str, str]] = {}
    followup_cache: dict[tuple[Any, ...], bool] = {}
    selected = [strategy for strategy in strategies() if strategy.key in ABC]
    for path in simulate_paths(gear, "normal_85", runs, random_seed):
        def early_action(state: Any, key: str) -> str:
            state_key = _signature(state)
            actions = early_cache.get(state_key)
            if actions is None:
                actions = strategy_actions(state, "normal_85")
                early_cache[state_key] = actions
            return actions[key]

        def followup(state: Any) -> bool:
            state_key = _signature(state)
            if state_key not in followup_cache:
                followup_cache[state_key] = formal_followup_action(state, "normal_85")
            return followup_cache[state_key]

        for strategy in selected:
            outcome = simulate_strategy_path(
                path,
                "normal_85",
                strategy,
                formal_followup=followup,
                early_action=lambda state, key=strategy.key: early_action(state, key),
            )
            row = _flow(gear, path, outcome)
            for field in FLOW_WITH_METRICS:
                totals[strategy.key][field] += row[field]
    return {"paths": float(runs), "candidates": totals}


def _heroic_shard(gear: Any, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {policy: _empty_flow() for policy in HEROIC_POLICIES}
    fixed = Strategy("heroic_fixed", "Heroic fixed fallback", lambda _: "stop")
    for path in simulate_paths(gear, "normal_85", runs, random_seed):
        for policy in HEROIC_POLICIES:
            all_stop = policy == "all_stop"
            outcome = simulate_strategy_path(
                path,
                "normal_85",
                fixed,
                formal_followup=(lambda _: False) if all_stop else (lambda state: _heroic_base_action(state, "normal_85") == "continue"),
                early_action=(lambda _: "stop") if all_stop else (lambda state: _heroic_base_action(state, "normal_85")),
            )
            row = _flow(gear, path, outcome)
            for field in FLOW_WITH_METRICS:
                totals[policy][field] += row[field]
    return {"paths": float(runs), "policies": totals}


def _path(resume_dir: Path, rank: str, seed: int, gear_index: int, chunk_index: int) -> Path:
    return resume_dir / "shards" / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}-chunk-{chunk_index:03d}.json"


def _valid(path: Path, strategy_hash: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return (
            payload.get("status") == "complete"
            and payload.get("schema_version") == SCHEMA_VERSION
            and payload.get("candidate_scope") == "ABC_terminal_metrics"
            and payload.get("strategy_hash") == strategy_hash
        )
    except (OSError, ValueError):
        return False


def _worker(job: dict[str, Any]) -> dict[str, Any]:
    payload = _epic_shard(job["gear"], job["runs"], job["random_seed"]) if job["rank"] == "Epic" else _heroic_shard(job["gear"], job["runs"], job["random_seed"])
    payload.update({key: job[key] for key in ("seed", "rank", "gear_index", "chunk_index", "chunk_count", "runs", "strategy_hash")})
    payload.update({"status": "complete", "schema_version": SCHEMA_VERSION, "candidate_scope": "ABC_terminal_metrics"})
    return payload


def _jobs(resume_dir: Path, seeds: tuple[int, ...], epic: list[Any], heroic: list[Any], runs_per_seed: int, chunk_runs: int, strategy_hash: str) -> tuple[list[dict[str, Any]], int]:
    if runs_per_seed % chunk_runs:
        raise ValueError("runs_per_seed must be divisible by chunk_runs")
    jobs: list[dict[str, Any]] = []
    skipped = 0
    chunks = runs_per_seed // chunk_runs
    for rank, gears in (("Epic", epic), ("Heroic", heroic)):
        for seed in seeds:
            for gear_index, gear in enumerate(gears):
                for chunk_index in range(chunks):
                    path = _path(resume_dir, rank, seed, gear_index, chunk_index)
                    if _valid(path, strategy_hash):
                        skipped += 1
                        continue
                    jobs.append({
                        "rank": rank, "seed": seed, "gear": gear, "gear_index": gear_index,
                        "chunk_index": chunk_index, "chunk_count": chunks, "runs": chunk_runs,
                        "random_seed": _random_seed(seed, rank, gear_index, chunk_index),
                        "strategy_hash": strategy_hash, "path": str(path),
                    })
    return jobs, skipped


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if not jobs:
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for job, payload in zip(jobs, executor.map(_worker, jobs)):
            _atomic_json(Path(job["path"]), payload)


def _sum_seed(resume_dir: Path, rank: str, seed: int, strategy_hash: str) -> dict[str, Any]:
    total: dict[str, Any] = {"paths": 0.0}
    directory = resume_dir / "shards" / rank.lower() / f"seed-{seed}"
    for path in directory.glob("*.json"):
        if not _valid(path, strategy_hash):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        total["paths"] += float(payload["paths"])
        rows = payload["candidates"] if rank == "Epic" else payload["policies"]
        for key, row in rows.items():
            target = total.setdefault(key, _empty_flow())
            for field in FLOW_WITH_METRICS:
                target[field] += float(row[field])
    return total


def _with_paths(flow: dict[str, float], paths: float) -> dict[str, float]:
    result = dict(flow)
    result["_paths"] = float(paths)
    return result


def _combine(epic: dict[str, float], heroic: dict[str, float], heroic_yield: float) -> dict[str, float]:
    return {
        field: float(epic[field]) / float(epic["_paths"]) + heroic_yield * float(heroic[field]) / float(heroic["_paths"])
        for field in FLOW_WITH_METRICS
    }


def _pool(flow: dict[str, float]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    return explicit_batch_resource_pool(
        source_gold=float(batch["expected_source_gold_per_batch"]),
        source_lower_stones=float(batch["expected_lower_stone_units"]),
        powder_base_exp=float(flow["powder_units"]) * 100.0,
        lower_stone_units=float(flow["lower_stone_units"]),
        material_gold=float(flow["material_gold"]),
        conversion_gold=float(flow["conversion_gold"]),
        sell_gold=float(flow["sell_gold"]),
        sell_exp=float(flow["sell_exp_adjusted"]),
        material_scarcity_exp=float(flow["material_exp_adjusted"]),
        lower_stone_adjusted_exp=float(flow["lower_stone_adjusted_exp"]),
    )


def _production(flow: dict[str, float], epic: dict[str, float], heroic: dict[str, float], heroic_yield: float) -> dict[str, Any]:
    pool = _pool(flow)
    total = float(pool["total_stamina"])
    counts = {field: float(flow[field]) for field in METRIC_FIELDS}
    def rank_counts(row: dict[str, float], paths: float, multiplier: float) -> dict[str, float]:
        return {field: multiplier * float(row[field]) / paths for field in METRIC_FIELDS}
    return {
        "flow": flow,
        "pool": pool,
        "counts_per_batch": counts,
        "per_100_batches": {field: 100.0 * value for field, value in counts.items()},
        "per_100k_stamina": {field: 100000.0 * value / total if total else 0.0 for field, value in counts.items()},
        "stamina_per_target": {field: total / value if value else None for field, value in counts.items()},
        "by_rank_per_batch": {
            "Epic": rank_counts(epic, float(epic["_paths"]), 1.0),
            "Heroic": rank_counts(heroic, float(heroic["_paths"]), heroic_yield),
        },
        "total_stamina": total,
    }


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values) if values else 0.0
    if len(values) < 2:
        return {"mean": center, "interval95": [center, center], "seed_stddev": 0.0}
    deviation = stdev(values)
    half = _t95(len(values)) * deviation / sqrt(len(values))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": deviation}


def _validate_freeze(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "collecting_blind" or payload.get("progress", {}).get("accepted") != 0:
        raise ValueError("prospective batch must remain empty collecting_blind")
    expected = str(payload["frozen"]["prediction_function_sha256"])
    actual = _prediction_hash()
    if actual != expected:
        raise ValueError("A/B/C strategy hash differs from the frozen prospective batch")
    return expected


def _d_flow(d_seed: dict[str, Any], rank: str) -> dict[str, float]:
    row = dict(d_seed[rank]["D"])
    return {field: float(row[field]) for field in FLOW_WITH_METRICS}


def summarize(resume_dir: Path, seeds: tuple[int, ...], strategy_hash: str) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        epic = _sum_seed(resume_dir, "Epic", seed, strategy_hash)
        heroic = _sum_seed(resume_dir, "Heroic", seed, strategy_hash)
        if not epic["paths"] or not heroic["paths"]:
            raise ValueError(f"incomplete A/B/C terminal-metric shards for seed {seed}")
        d_seed = {rank: _sum_d_seed(D_RESUME_DIR, rank, seed) for rank in ("Epic", "Heroic")}
        if not d_seed["Epic"]["paths"] or not d_seed["Heroic"]["paths"]:
            raise ValueError(f"incomplete existing D shards for seed {seed}")
        per_seed[str(seed)] = {}
        d_epic = _with_paths(_d_flow(d_seed, "Epic"), d_seed["Epic"]["paths"])
        d_heroic = _with_paths(_d_flow(d_seed, "Heroic"), d_seed["Heroic"]["paths"])
        for policy in HEROIC_POLICIES:
            for yield_name, multiplier in YIELD_VARIATIONS.items():
                scenario = f"{policy}/{yield_name}"
                yield_count = 85.0 / 23.81 * multiplier
                rows: dict[str, Any] = {}
                heroic_flow = _with_paths(heroic[policy], heroic["paths"])
                for candidate in ABC:
                    epic_flow = _with_paths(epic[candidate], epic["paths"])
                    joint = _combine(epic_flow, heroic_flow, yield_count)
                    rows[candidate] = _production(joint, epic_flow, heroic_flow, yield_count)
                d_joint = _combine(d_epic, d_heroic, yield_count)
                rows[D_FULL] = _production(d_joint, d_epic, d_heroic, yield_count)
                d_epic_joint = _combine(d_epic, heroic_flow, yield_count)
                rows[D_EPIC_BASE if policy == "baili_marginal_low" else D_EPIC_STOP] = _production(d_epic_joint, d_epic, heroic_flow, yield_count)
                per_seed[str(seed)][scenario] = rows
    scenarios: dict[str, Any] = {}
    for scenario in next(iter(per_seed.values())):
        candidates = tuple(next(iter(per_seed.values()))[scenario])
        pairs = (("A_current_review", "B_global_current_gs"), ("B_global_current_gs", "C_category_probability"), (D_FULL, "B_global_current_gs"))
        if D_EPIC_BASE in candidates:
            pairs += ((D_EPIC_BASE, "B_global_current_gs"),)
        if D_EPIC_STOP in candidates:
            pairs += ((D_EPIC_STOP, "B_global_current_gs"),)
        scenarios[scenario] = {
            "candidate_means": {
                candidate: {field: _ci([per_seed[str(seed)][scenario][candidate]["counts_per_batch"][field] for seed in seeds]) for field in METRIC_FIELDS}
                for candidate in candidates
            },
            "paired_differences": {
                f"{left} - {right}": {
                    field: _ci([
                        per_seed[str(seed)][scenario][left]["counts_per_batch"][field] - per_seed[str(seed)][scenario][right]["counts_per_batch"][field]
                        for seed in seeds
                    ])
                    for field in METRIC_FIELDS
                }
                for left, right in pairs
            },
        }
    return {"per_seed": per_seed, "scenarios": scenarios}


def _main_means(data: dict[str, Any], candidate: str) -> dict[str, Any]:
    scenario = "baili_marginal_low/baseline"
    rows = [data["summary"]["per_seed"][str(seed)][scenario][candidate] for seed in data["seeds"]]
    return {
        "per_100": {field: mean(row["per_100_batches"][field] for row in rows) for field in METRIC_FIELDS},
        "per_100k": {field: mean(row["per_100k_stamina"][field] for row in rows) for field in METRIC_FIELDS},
        "stamina_per_target": {field: (mean(row["total_stamina"] for row in rows) / mean(row["counts_per_batch"][field] for row in rows) if mean(row["counts_per_batch"][field] for row in rows) else None) for field in METRIC_FIELDS},
        "by_rank": {
            rank: {field: mean(row["by_rank_per_batch"][rank][field] for row in rows) for field in METRIC_FIELDS}
            for rank in ("Epic", "Heroic")
        },
        "total_stamina": mean(row["total_stamina"] for row in rows),
    }


def markdown_section(data: dict[str, Any]) -> str:
    scenario = "baili_marginal_low/baseline"
    candidates = tuple(data["summary"]["per_seed"][str(data["seeds"][0])][scenario])
    lines = [
        "## 终局产量补全", "",
        "本章节仅补解释性产量统计。A/B/C 使用冻结策略哈希、同一装备、5个 seed、每件5,000轨迹和相同 random_seed 派生确定性重放；D 直接读取既有 D 专用分片。未重新评估排序或发布判断。", "",
        "主场景为 Heroic 基础回退、基线 Heroic 产出。每联合批次固定为 1 Epic + 85/23.81 Heroic（estimated），资源分母为 85 维度裂缝体力加一次圣女瓶颈补充。", "",
        "| 候选 | 原生75+/100批 | 转换75+/100批 | 22速/100批 | 输出60/100批 | 总体力/批 |", "|---|---:|---:|---:|---:|---:|",
    ]
    means = {candidate: _main_means(data, candidate) for candidate in candidates}
    for candidate, row in means.items():
        lines.append(f"| {candidate} | {row['per_100']['native_heirloom']:.4f} | {row['per_100']['converted_heirloom']:.4f} | {row['per_100']['speed22']:.4f} | {row['per_100']['output60']:.4f} | {row['total_stamina']:.3f} |")
    lines.extend(["", "| 候选 | 原生75+每件体力 | 转换75+每件体力 | 22速每件体力 | 输出60每件体力 |", "|---|---:|---:|---:|---:|"])
    for candidate, row in means.items():
        cells = [("-" if row["stamina_per_target"][field] is None else f"{row['stamina_per_target'][field]:.2f}") for field in METRIC_FIELDS]
        lines.append(f"| {candidate} | " + " | ".join(cells) + " |")
    lines.extend(["", "### Epic、Heroic 分项（每联合批次）", "", "| 候选 | Epic原生75+ | Heroic原生75+ | Epic转换75+ | Heroic转换75+ | Epic22速 | Heroic22速 |", "|---|---:|---:|---:|---:|---:|---:|"])
    for candidate, row in means.items():
        lines.append(f"| {candidate} | {row['by_rank']['Epic']['native_heirloom']:.5f} | {row['by_rank']['Heroic']['native_heirloom']:.5f} | {row['by_rank']['Epic']['converted_heirloom']:.5f} | {row['by_rank']['Heroic']['converted_heirloom']:.5f} | {row['by_rank']['Epic']['speed22']:.5f} | {row['by_rank']['Heroic']['speed22']:.5f} |")
    lines.extend(["", "### 每100,000总体力", "", "| 候选 | 原生75+ | 转换75+ | 22速 | 输出60 |", "|---|---:|---:|---:|---:|"])
    for candidate, row in means.items():
        lines.append(f"| {candidate} | {row['per_100k']['native_heirloom']:.4f} | {row['per_100k']['converted_heirloom']:.4f} | {row['per_100k']['speed22']:.4f} | {row['per_100k']['output60']:.4f} |")
    all_stop = "all_stop/baseline"
    all_stop_candidates = tuple(data["summary"]["per_seed"][str(data["seeds"][0])][all_stop])
    lines.extend(["", "### Heroic 全停背景对照（每100联合批次）", "", "| 候选 | 原生75+ | 转换75+ | 22速 | 输出60 | 总体力/批 |", "|---|---:|---:|---:|---:|---:|"])
    for candidate in all_stop_candidates:
        rows = [data["summary"]["per_seed"][str(seed)][all_stop][candidate] for seed in data["seeds"]]
        lines.append(
            f"| {candidate} | {mean(row['per_100_batches']['native_heirloom'] for row in rows):.4f} | "
            f"{mean(row['per_100_batches']['converted_heirloom'] for row in rows):.4f} | "
            f"{mean(row['per_100_batches']['speed22'] for row in rows):.4f} | "
            f"{mean(row['per_100_batches']['output60'] for row in rows):.4f} | {mean(row['total_stamina'] for row in rows):.3f} |"
        )
    pairs = data["summary"]["scenarios"][scenario]["paired_differences"]
    lines.extend(["", "### 相同 seed 成对差值95%区间（每联合批次）", "", "| 对比 | 原生75+ | 转换75+ | 22速 | 输出60 |", "|---|---:|---:|---:|---:|"])
    for pair, metrics in pairs.items():
        cells = [f"[{metrics[field]['interval95'][0]:.5f}, {metrics[field]['interval95'][1]:.5f}]" for field in METRIC_FIELDS]
        lines.append(f"| {pair} | " + " | ".join(cells) + " |")
    lines.extend(["", "### 解释边界", "", "- 原生75+使用重铸后全部副属性官方总GS；转换75+在合法满值转换实际应用后独立统计，二者不可相加。", "- 22速仅终局非鞋速度>=22；输出60仅合法普通输出体系有效GS>=60。", "- 产量较多不等于单位总体力效率更高；本章节不改变已冻结的 B 第一、D 淘汰与48件前瞻盲收结论。", ""])
    return "\n".join(lines)


def update_report(report: Path, section: str) -> None:
    start = "<!-- terminal-production:start -->"
    end = "<!-- terminal-production:end -->"
    current = report.read_text(encoding="utf-8") if report.exists() else "# 终局产量补全 Smoke\n"
    wrapped = f"\n{start}\n{section}\n{end}\n"
    if start in current and end in current:
        before, remainder = current.split(start, 1)
        _old, after = remainder.split(end, 1)
        report.write_text(before.rstrip() + wrapped + after.lstrip(), encoding="utf-8")
    else:
        report.write_text(current.rstrip() + wrapped, encoding="utf-8")


def run(source: Path, records: Path, resume_dir: Path, *, seeds: tuple[int, ...], runs_per_seed: int, chunk_runs: int, workers: int) -> dict[str, Any]:
    strategy_hash = _validate_freeze(FROZEN_BATCH)
    source_data = json.loads(source.read_text(encoding="utf-8"))
    records_data = json.loads(records.read_text(encoding="utf-8"))
    partition = build_partition(source_data, records_data, blind_size=24, seed=20260712)
    epic = [row["gear"] for row in partition["training"]] + [row["gear"] for row in partition["speed_hard"]]
    heroic = _source_rank_gears(source_data, "Heroic")
    jobs, skipped = _jobs(resume_dir, seeds, epic, heroic, runs_per_seed, chunk_runs, strategy_hash)
    started = time.monotonic()
    _run_jobs(jobs, workers)
    return {
        "study": "abc_terminal_metrics_supplement", "strategy_hash": strategy_hash,
        "research_lambda": RESEARCH_LAMBDA, "seeds": list(seeds), "runs_per_gear": runs_per_seed * len(seeds),
        "frozen_abc_resume_dir": str(FROZEN_RESUME_DIR), "d_resume_dir": str(D_RESUME_DIR), "resume_dir": str(resume_dir),
        "execution": {"scheduled_shards": len(jobs), "skipped_shards": skipped, "runtime_seconds": time.monotonic() - started},
        "summary": summarize(resume_dir, seeds, strategy_hash),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Supplement frozen A/B/C terminal production metrics")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "abc_terminal_metrics_resume_20260713")
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--runs-per-seed", type=int, default=1000)
    parser.add_argument("--chunk-runs", type=int, default=500)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "abc_terminal_metrics_20260713.json")
    parser.add_argument("--report", type=Path, default=ROOT / "reports" / "external_threshold_d_comparison_20260713.md")
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(",") if value.strip())
    if len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be unique")
    data = run(args.source, args.records, args.resume_dir, seeds=seeds, runs_per_seed=args.runs_per_seed, chunk_runs=args.chunk_runs, workers=args.workers)
    _atomic_json(args.json_output, data)
    update_report(args.report, markdown_section(data))


if __name__ == "__main__":
    main()
