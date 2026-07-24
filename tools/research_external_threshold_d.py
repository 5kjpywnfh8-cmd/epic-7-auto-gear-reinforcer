"""Paired offline study for frozen external threshold-table candidate D.

This tool never changes released policy, lambda, scoring, rule tables, or GUI.
It deterministically replays only D into a dedicated shard directory and reads
the frozen A/B/C 22-speed study shards as immutable baselines.
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

from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    Strategy,
    _heroic_base_action,
    _source_rank_gears,
    _terminal_metrics,
    build_partition,
    simulate_paths,
    simulate_strategy_path,
    summarize_incremental_cost,
)
from tools.external_threshold_strategy import output_effective_gs, simulate_path
from tools.research_riftslash_saint_pool import (
    FLOW_FIELDS,
    HEROIC_POLICIES,
    SPEED_VALUE_FIELDS,
    YIELD_VARIATIONS,
    _atomic_json,
    _flow_for_outcome,
    _mean_batch,
    _sum_seed,
    _t95,
    explicit_batch_resource_pool,
)

SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
ABC = ("A_current_review", "B_global_current_gs", "C_category_probability")
D_FULL = "D_full"
D_EPIC_BASE = "D_epic_only_base"
D_EPIC_STOP = "D_epic_only_all_stop"
FROZEN_RESUME_DIR = ROOT / "reports" / "riftslash_saint_pool_22speed_resume_20260713"
RESEARCH_LAMBDA = 0.0022851391
CHECKPOINTS = (0, 3, 6, 9, 12, 15)
EXTRA_FIELDS = (
    "native_heirloom", "converted_heirloom", "speed22", "output60",
    "formal_value_sum", "terminal_count", "stop_cost_sum",
) + tuple(f"reach_{point}" for point in CHECKPOINTS) + tuple(f"stop_{point}" for point in CHECKPOINTS)
D_FLOW_FIELDS = FLOW_FIELDS + EXTRA_FIELDS


def _empty_flow() -> dict[str, float]:
    return {field: 0.0 for field in D_FLOW_FIELDS}


def _signature(state: Any) -> tuple[Any, ...]:
    return (state.slot, state.main_stat.key, state.enhance, tuple((s.key, s.normalized_value, s.rolls) for s in state.substats))


def d_path_outcome(path: dict[int, Any]) -> dict[str, Any]:
    """D's literal gate, with full +9 -> +15 material cost."""
    outcome = simulate_path(path)
    start, stop = min(path), int(outcome["stop_checkpoint"])
    costs = summarize_incremental_cost(path[start].slot, path[start].rank, start, stop)
    return {
        **outcome,
        "start_checkpoint": start,
        "net_stamina": costs["net_stamina"],
        "net_gold": costs["net_gold"],
        "costs": costs,
    }


def frozen_heroic_outcome(path: dict[int, Any], *, all_stop: bool) -> dict[str, Any]:
    """Test seam for the published Heroic fallback; it never calls D."""
    fixed = Strategy("heroic_fixed", "Heroic fixed fallback", lambda _: "stop")
    return simulate_strategy_path(
        path,
        "normal_85",
        fixed,
        formal_followup=(lambda _: False) if all_stop else (lambda state: _heroic_base_action(state, "normal_85") == "continue"),
        early_action=(lambda _: "stop") if all_stop else (lambda state: _heroic_base_action(state, "normal_85")),
    )


def _d_flow(gear: Any, path: dict[int, Any]) -> dict[str, float]:
    outcome = d_path_outcome(path)
    stop = int(outcome["stop_checkpoint"])
    terminal = _terminal_metrics(path[stop], "normal_85")
    conversion = bool(stop == 15 and terminal["conversion_needed"])
    flow = dict(_flow_for_outcome(gear, outcome, conversion, terminal))
    final = path[stop]
    flow.update({
        "native_heirloom": float(stop == 15 and terminal["official_substat_gs"] >= 75),
        "converted_heirloom": float(stop == 15 and terminal["converted_official_substat_gs"] >= 75),
        "speed22": float(stop == 15 and terminal["final_speed"] >= 22),
        "output60": float(stop == 15 and output_effective_gs(final) >= 60),
        "formal_value_sum": float(terminal["formal_value"] if stop == 15 else 0.0),
        "terminal_count": float(stop == 15),
        "stop_cost_sum": float(outcome["net_stamina"]),
    })
    reached = set(outcome["reached_checkpoints"])
    for point in CHECKPOINTS:
        flow[f"reach_{point}"] = float(point in reached)
        flow[f"stop_{point}"] = float(stop == point)
    return flow


def _d_shard(gear: Any, runs: int, random_seed: int) -> dict[str, Any]:
    totals = _empty_flow()
    for path in simulate_paths(gear, "normal_85", runs, random_seed):
        row = _d_flow(gear, path)
        for field in D_FLOW_FIELDS:
            totals[field] += row[field]
    return {"paths": float(runs), "candidates": {"D": totals}}


def _random_seed(seed: int, rank: str, gear_index: int, chunk_index: int) -> int:
    # Exactly the frozen study's deterministic derivation.
    return seed * 1_000_003 + (0 if rank == "Epic" else 500_003) + gear_index * 1_009 + chunk_index * 37


def _shard_path(resume_dir: Path, rank: str, seed: int, gear_index: int, chunk: int) -> Path:
    return resume_dir / "shards" / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}-chunk-{chunk:03d}.json"


def _valid(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("status") == "complete" and payload.get("schema_version") == 1 and payload.get("candidate_scope") == "D_only"
    except (OSError, ValueError):
        return False


def _job_worker(job: dict[str, Any]) -> dict[str, Any]:
    payload = _d_shard(job["gear"], job["runs"], job["random_seed"])
    payload.update({key: job[key] for key in ("seed", "rank", "gear_index", "chunk_index", "chunk_count", "runs")})
    payload.update({"status": "complete", "schema_version": 1, "candidate_scope": "D_only"})
    return payload


def _jobs(resume_dir: Path, seeds: tuple[int, ...], epic: list[Any], heroic: list[Any], runs_per_seed: int, chunk_runs: int) -> tuple[list[dict[str, Any]], int]:
    if runs_per_seed % chunk_runs:
        raise ValueError("runs_per_seed must be divisible by chunk_runs")
    jobs: list[dict[str, Any]] = []
    skipped = 0
    chunk_count = runs_per_seed // chunk_runs
    for rank, gears in (("Epic", epic), ("Heroic", heroic)):
        for seed in seeds:
            for gear_index, gear in enumerate(gears):
                for chunk_index in range(chunk_count):
                    path = _shard_path(resume_dir, rank, seed, gear_index, chunk_index)
                    if _valid(path):
                        skipped += 1
                        continue
                    jobs.append({
                        "rank": rank, "seed": seed, "gear": gear, "gear_index": gear_index,
                        "chunk_index": chunk_index, "chunk_count": chunk_count, "runs": chunk_runs,
                        "random_seed": _random_seed(seed, rank, gear_index, chunk_index), "path": str(path),
                    })
    return jobs, skipped


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if not jobs:
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for job, payload in zip(jobs, executor.map(_job_worker, jobs)):
            _atomic_json(Path(job["path"]), payload)


def _sum_d_seed(resume_dir: Path, rank: str, seed: int) -> dict[str, Any]:
    total = {"paths": 0.0, "D": _empty_flow()}
    directory = resume_dir / "shards" / rank.lower() / f"seed-{seed}"
    for path in directory.glob("*.json"):
        if not _valid(path):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        total["paths"] += float(payload["paths"])
        row = payload["candidates"]["D"]
        for field in D_FLOW_FIELDS:
            total["D"][field] += float(row[field])
    return total


def aggregate_explicit_pool(flow: dict[str, float]) -> dict[str, Any]:
    """Settle one 85-stamina Epic+Heroic batch exactly once."""
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


def _combine(epic: dict[str, Any], heroic: dict[str, Any], heroic_yield: float) -> dict[str, float]:
    result: dict[str, float] = {}
    for field in D_FLOW_FIELDS:
        result[field] = float(epic[field]) / float(epic["_paths"]) + heroic_yield * float(heroic[field]) / float(heroic["_paths"])
    return result


def _pack_flow(flow: dict[str, float], *, value_field: str) -> dict[str, Any]:
    pool = aggregate_explicit_pool(flow)
    formal = float(flow["value_sum"])
    value = float(flow[value_field])
    total = float(pool["total_stamina"])
    metrics = {key: float(flow[key]) for key in ("native_heirloom", "converted_heirloom", "speed22", "output60", "formal_value_sum", "terminal_count")}
    return {
        "flow": flow,
        "pool": pool,
        "formal_value": formal,
        "value_with_22_speed": value,
        "total_stamina": total,
        "formal_rate_per_100_stamina": 100 * formal / total if total else 0.0,
        "value_rate_per_100_stamina": 100 * value / total if total else 0.0,
        "per_100_batches": {key: 100 * value for key, value in metrics.items()},
        "per_100k_stamina": {key: 100000 * value / total if total else 0.0 for key, value in metrics.items()},
        "reach_rate": {str(point): flow[f"reach_{point}"] for point in CHECKPOINTS},
        "stop_rate": {str(point): flow[f"stop_{point}"] for point in CHECKPOINTS},
        "average_stop_cost": float(flow["stop_cost_sum"]),
    }


def _with_paths(flow: dict[str, float], paths: float) -> dict[str, float]:
    result = dict(flow)
    result["_paths"] = paths
    # Frozen A/B/C shards do not need the extra D-only yield indicators for
    # ranking.  They are reconstructed for reporting where possible below.
    for field in EXTRA_FIELDS:
        result.setdefault(field, 0.0)
    return result


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values) if values else 0.0
    if len(values) < 2:
        return {"mean": center, "interval95": [center, center], "seed_stddev": 0.0}
    deviation = stdev(values)
    half = _t95(len(values)) * deviation / sqrt(len(values))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": deviation}


def _scenario_rows(
    frozen_epic: dict[str, Any], frozen_heroic: dict[str, Any], d_epic: dict[str, Any], d_heroic: dict[str, Any],
    *, heroic_policy: str, yield_multiplier: float, speed_field: str,
) -> dict[str, dict[str, Any]]:
    heroic_yield = 85.0 / 23.81 * yield_multiplier
    rows: dict[str, dict[str, Any]] = {}
    for candidate in ABC:
        flow = _combine(_with_paths(frozen_epic[candidate], frozen_epic["paths"]), _with_paths(frozen_heroic[heroic_policy], frozen_heroic["paths"]), heroic_yield)
        rows[candidate] = _pack_flow(flow, value_field=speed_field)
    d_epic_flow = _with_paths(d_epic["D"], d_epic["paths"])
    d_heroic_flow = _with_paths(d_heroic["D"], d_heroic["paths"])
    base_heroic = _with_paths(frozen_heroic[heroic_policy], frozen_heroic["paths"])
    rows[D_EPIC_BASE if heroic_policy == "baili_marginal_low" else D_EPIC_STOP] = _pack_flow(_combine(d_epic_flow, base_heroic, heroic_yield), value_field=speed_field)
    rows[D_FULL] = _pack_flow(_combine(d_epic_flow, d_heroic_flow, heroic_yield), value_field=speed_field)
    return rows


def summarize(resume_dir: Path, seeds: tuple[int, ...]) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    for seed in seeds:
        frozen_epic = _sum_seed(FROZEN_RESUME_DIR, "Epic", seed)
        frozen_heroic = _sum_seed(FROZEN_RESUME_DIR, "Heroic", seed)
        d_epic, d_heroic = _sum_d_seed(resume_dir, "Epic", seed), _sum_d_seed(resume_dir, "Heroic", seed)
        if not d_epic["paths"] or not d_heroic["paths"]:
            raise ValueError(f"incomplete D shards for seed {seed}")
        per_seed[str(seed)] = {}
        for profile, speed_field in SPEED_VALUE_FIELDS.items():
            for policy in HEROIC_POLICIES:
                for yield_name, multiplier in YIELD_VARIATIONS.items():
                    key = f"{profile}/{policy}/{yield_name}"
                    per_seed[str(seed)][key] = _scenario_rows(frozen_epic, frozen_heroic, d_epic, d_heroic, heroic_policy=policy, yield_multiplier=multiplier, speed_field=speed_field)
    summary: dict[str, Any] = {}
    for scenario in next(iter(per_seed.values())):
        candidates = tuple(next(iter(per_seed.values()))[scenario])
        rates = {candidate: [per_seed[str(seed)][scenario][candidate]["value_rate_per_100_stamina"] for seed in seeds] for candidate in candidates}
        order = sorted(candidates, key=lambda key: (-mean(rates[key]), key))
        pairs = {}
        for left, right in ((D_FULL, "B_global_current_gs"), (D_EPIC_BASE, "B_global_current_gs"), (D_EPIC_STOP, "B_global_current_gs"), ("B_global_current_gs", "C_category_probability")):
            if left in rates and right in rates:
                pairs[f"{left} - {right}"] = _ci([a - b for a, b in zip(rates[left], rates[right])])
        summary[scenario] = {"order": order, "rates": {candidate: _ci(values) for candidate, values in rates.items()}, "paired_differences": pairs}
    return {"per_seed": per_seed, "scenarios": summary}


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# 外部红紫阈值表策略 D 离线对比", "",
        "D 仅为离线候选。A/B/C 读取冻结的 22 速研究分片；D 在独立目录确定性重放相同 seed、装备与随机种子。未修改正式策略、lambda、Heroic 正式策略、评分、跳值表或 GUI。", "",
        f"研究 lambda：`{RESEARCH_LAMBDA}`，仅用于前瞻 Oracle 口径备案，未写回正式配置。", "",
        "## 主口径", "",
        "每联合批次为 85 维度裂缝体力、1 Epic、85/23.81 Heroic、0.425 下级石与 127,500 金币。红紫装备资源流合并后仅做一次圣女 3-7 金币/经验瓶颈补充。", "",
    ]
    for scenario, row in data["summary"]["scenarios"].items():
        lines.extend([f"## {scenario}", "", "| 候选 | 含22速价值率/100体力 95% CI |", "|---|---:|"])
        for candidate in row["order"]:
            interval = row["rates"][candidate]["interval95"]
            lines.append(f"| {candidate} | [{interval[0]:.6f}, {interval[1]:.6f}] |")
        lines.extend(["", "| 成对差值 | 95% CI |", "|---|---:|"])
        for pair, value in row["paired_differences"].items():
            interval = value["interval95"]
            lines.append(f"| {pair} | [{interval[0]:.6f}, {interval[1]:.6f}] |")
        lines.append("")
    lines.extend([
        "## 主场景资源与终局产出", "",
        "主场景为 `curve_baseline/baili_marginal_low/baseline`。数值为五个 seed 的每联合批次均值；每批固定支付 85 维度裂缝体力，再按一次圣女瓶颈补充。", "",
        "| 候选 | 含22速价值/100体力 | 正式价值/100体力 | 总体力/批 | 粉末单位/批 | 下级石需求/批 | 材料+转换-出售金币/批 | 圣女补充体力/批 |", "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    main = "curve_baseline/baili_marginal_low/baseline"
    main_rows = [data["summary"]["per_seed"][str(seed)][main] for seed in data["seeds"]]
    for candidate in data["summary"]["scenarios"][main]["order"]:
        rows = [row[candidate] for row in main_rows]
        flow = {field: mean(float(row["flow"][field]) for row in rows) for field in FLOW_FIELDS}
        lines.append(
            f"| {candidate} | {mean(row['value_rate_per_100_stamina'] for row in rows):.6f} | {mean(row['formal_rate_per_100_stamina'] for row in rows):.6f} | "
            f"{mean(row['total_stamina'] for row in rows):.3f} | {flow['powder_units']:.3f} | {flow['lower_stone_units']:.3f} | "
            f"{flow['material_gold'] + flow['conversion_gold'] - flow['sell_gold']:.2f} | {mean(row['pool']['saint_supplement_stamina'] for row in rows):.3f} |"
        )
    lines.extend([
        "", "### D 的可重放终局计数", "",
        "D 专用分片保存了 75+、转换后75+、22速、输出GS>=60与节点。冻结 A/B/C 分片在研究开始前没有保存这些原始计数，故不能在不重跑 A/B/C 的前提下反推；报告只使用其已冻结的价值和完整资源账本作排序。", "",
        "| 候选/背景 | 原生75+/100批 | 转换后75+/100批 | 22速/100批 | 输出GS>=60/100批 | 原生75+每件总体力 |", "|---|---:|---:|---:|---:|---:|",
    ])
    for candidate in (D_FULL, D_EPIC_BASE):
        rows = [row[candidate] for row in main_rows]
        native = mean(row["per_100_batches"]["native_heirloom"] for row in rows)
        stamina = mean(row["total_stamina"] for row in rows)
        lines.append(
            f"| {candidate} | {native:.4f} | {mean(row['per_100_batches']['converted_heirloom'] for row in rows):.4f} | "
            f"{mean(row['per_100_batches']['speed22'] for row in rows):.4f} | {mean(row['per_100_batches']['output60'] for row in rows):.4f} | "
            f"{(100 * stamina / native) if native else float('inf'):.2f} |"
        )
    lines.extend(["", "### D 节点到达与止损", "", "| D候选/背景 | +0 | +3 | +6 | +9 | +12 | +15 | 平均止损成本/批 |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for candidate in (D_FULL, D_EPIC_BASE):
        rows = [row[candidate] for row in main_rows]
        reaches = [mean(row["reach_rate"][str(point)] for row in rows) for point in CHECKPOINTS]
        lines.append(f"| {candidate} 到达 | " + " | ".join(f"{value:.4f}" for value in reaches) + f" | {mean(row['average_stop_cost'] for row in rows):.4f} |")
        stops = [mean(row["stop_rate"][str(point)] for row in rows) for point in CHECKPOINTS]
        lines.append(f"| {candidate} 停止 | " + " | ".join(f"{value:.4f}" for value in stops) + " | - |")
    lines.extend([
        "", "### 每100,000总体力 D 产出", "",
        "| 候选/背景 | 原生75+ | 转换后75+ | 22速 | 输出GS>=60 |", "|---|---:|---:|---:|---:|",
    ])
    for candidate in (D_FULL, D_EPIC_BASE):
        rows = [row[candidate] for row in main_rows]
        lines.append(
            f"| {candidate} | {mean(row['per_100k_stamina']['native_heirloom'] for row in rows):.4f} | "
            f"{mean(row['per_100k_stamina']['converted_heirloom'] for row in rows):.4f} | "
            f"{mean(row['per_100k_stamina']['speed22'] for row in rows):.4f} | {mean(row['per_100k_stamina']['output60'] for row in rows):.4f} |"
        )
    lines.extend(["## 说明", "", "- `D_full`：Epic、Heroic 均执行截图阈值。", "- `D_epic_only_base` / `D_epic_only_all_stop`：只替换 Epic，Heroic 分别使用冻结基础回退/全停背景；不与 D_full 混为同一策略结论。", "- D 原始 JSON 对每个 seed 保存原生75+、转换后75+、22速、输出有效GS>=60和节点；冻结 A/B/C 分片不具备这些历史字段，不能诚实反推。", "- 配对区间按同一 seed、装备和确定性公共轨迹的价值率差计算，不使用独立候选区间代替。", ""])
    return "\n".join(lines)


def run(source: Path, records: Path, resume_dir: Path, *, seeds: tuple[int, ...], runs_per_seed: int, chunk_runs: int, workers: int) -> dict[str, Any]:
    source_data = json.loads(source.read_text(encoding="utf-8"))
    records_data = json.loads(records.read_text(encoding="utf-8"))
    partition = build_partition(source_data, records_data, blind_size=24, seed=20260712)
    epic = [row["gear"] for row in partition["training"]] + [row["gear"] for row in partition["speed_hard"]]
    heroic = _source_rank_gears(source_data, "Heroic")
    jobs, skipped = _jobs(resume_dir, seeds, epic, heroic, runs_per_seed, chunk_runs)
    started = time.monotonic()
    _run_jobs(jobs, workers)
    return {
        "study": "external_threshold_d", "research_lambda": RESEARCH_LAMBDA, "seeds": list(seeds),
        "runs_per_gear": runs_per_seed * len(seeds), "frozen_abc_resume_dir": str(FROZEN_RESUME_DIR),
        "d_resume_dir": str(resume_dir), "execution": {"scheduled_shards": len(jobs), "skipped_shards": skipped, "runtime_seconds": time.monotonic() - started},
        "summary": summarize(resume_dir, seeds),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired D threshold-table study")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "external_threshold_d_resume_20260713")
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--runs-per-seed", type=int, default=1000)
    parser.add_argument("--chunk-runs", type=int, default=500)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "external_threshold_d_comparison_20260713.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "external_threshold_d_comparison_20260713.md")
    args = parser.parse_args()
    seeds = tuple(int(value) for value in args.seeds.split(",") if value.strip())
    if len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be unique")
    data = run(args.source, args.records, args.resume_dir, seeds=seeds, runs_per_seed=args.runs_per_seed, chunk_runs=args.chunk_runs, workers=args.workers)
    _atomic_json(args.json_output, data)
    args.markdown_output.write_text(markdown(data), encoding="utf-8")


if __name__ == "__main__":
    main()
