"""Resumable riftslash Epic/Heroic joint-batch stability study.

This is an offline research tool.  It reads the released policies but never
writes policy rules, DP lambdas, score rules, or GUI state.
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

from src.e7_enhance.resource_model import DEFAULT_CONVERSION_GOLD_COST, calibration_for_rank, conversion_stamina_cost, joint_source_batch_metadata
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    Strategy,
    _heroic_base_action,
    _source_rank_gears,
    _speed_hard_route,
    _terminal_formal_value,
    _terminal_metrics,
    build_partition,
    formal_followup_action,
    simulate_paths,
    simulate_strategy_path,
    strategies,
    strategy_actions,
)


HEROIC_YIELD_VARIATIONS = {"yield_minus_20pct": 0.8, "baseline": 1.0, "yield_plus_20pct": 1.2}
HEROIC_POLICIES = ("baili_marginal_low", "all_stop")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _valid_shard(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("status") == "complete" and int(payload.get("paths") or 0) > 0
    except (OSError, ValueError, TypeError):
        return False


def _shard_path(resume_dir: Path, rank: str, seed: int, gear_index: int, chunk_index: int) -> Path:
    return resume_dir / "shards" / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}-chunk-{chunk_index:03d}.json"


def _terminal_value(terminal: dict[str, Any]) -> float:
    """The joint study uses only formal category value as its numerator.

    A speed override is intentionally absent until a >=22 speed calibration is
    separately evidenced.  This excludes GS75 and multi-category counts too.
    """
    return _terminal_formal_value(terminal)


def _epic_shard(gear, item_source: str, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {strategy.key: {"value_sum": 0.0, "stamina_sum": 0.0, "terminal_formal_count": 0} for strategy in strategies()}
    conversion_stamina = conversion_stamina_cost(DEFAULT_CONVERSION_GOLD_COST, calibration_for_rank("Epic"))
    paths = simulate_paths(gear, item_source, runs, random_seed)
    early_cache: dict[tuple, dict[str, str]] = {}
    followup_cache: dict[tuple, bool] = {}
    terminal_cache: dict[tuple, dict[str, Any]] = {}
    signature = lambda state: (state.slot, state.main_stat.key, state.enhance, tuple((s.key, s.normalized_value, s.rolls) for s in state.substats))
    for path in paths:
        def early_action(state, key: str) -> str:
            key_state = signature(state)
            actions = early_cache.get(key_state)
            if actions is None:
                actions = strategy_actions(state, item_source)
                early_cache[key_state] = actions
            return actions[key]

        def followup(state) -> bool:
            key_state = signature(state)
            if key_state not in followup_cache:
                followup_cache[key_state] = formal_followup_action(state, item_source)
            return followup_cache[key_state]

        for strategy in strategies():
            outcome = simulate_strategy_path(path, item_source, strategy, formal_followup=followup, early_action=lambda state, key=strategy.key: early_action(state, key))
            stop = outcome["stop_checkpoint"]
            terminal_key = signature(path[stop])
            terminal = terminal_cache.get(terminal_key)
            if terminal is None:
                terminal = _terminal_metrics(path[stop], item_source)
                terminal_cache[terminal_key] = terminal
            conversion = conversion_stamina if stop == 15 and terminal["conversion_needed"] else 0.0
            bucket = totals[strategy.key]
            bucket["stamina_sum"] += float(outcome["net_stamina"]) + conversion
            if stop == 15:
                value = _terminal_value(terminal)
                bucket["value_sum"] += value
                bucket["terminal_formal_count"] += int(value > 0)
    return {"rank": "Epic", "paths": len(paths), "candidates": totals}


def _heroic_shard(gear, item_source: str, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {policy: {"value_sum": 0.0, "stamina_sum": 0.0, "terminal_formal_count": 0} for policy in HEROIC_POLICIES}
    conversion_stamina = conversion_stamina_cost(DEFAULT_CONVERSION_GOLD_COST, calibration_for_rank("Heroic"))
    paths = simulate_paths(gear, item_source, runs, random_seed)
    fixed = Strategy("heroic_fixed", "Heroic fixed fallback", lambda _: "stop")
    terminal_cache: dict[tuple, dict[str, Any]] = {}
    signature = lambda state: (state.slot, state.main_stat.key, state.enhance, tuple((s.key, s.normalized_value, s.rolls) for s in state.substats))
    for path in paths:
        for policy in HEROIC_POLICIES:
            all_stop = policy == "all_stop"
            outcome = simulate_strategy_path(
                path,
                item_source,
                fixed,
                formal_followup=(lambda state: False) if all_stop else (lambda state: _heroic_base_action(state, item_source) == "continue"),
                early_action=(lambda state: "stop") if all_stop else (lambda state: _heroic_base_action(state, item_source)),
            )
            stop = outcome["stop_checkpoint"]
            terminal_key = signature(path[stop])
            terminal = terminal_cache.get(terminal_key)
            if terminal is None:
                terminal = _terminal_metrics(path[stop], item_source)
                terminal_cache[terminal_key] = terminal
            conversion = conversion_stamina if stop == 15 and terminal["conversion_needed"] else 0.0
            bucket = totals[policy]
            bucket["stamina_sum"] += float(outcome["net_stamina"]) + conversion
            if stop == 15:
                value = _terminal_value(terminal)
                bucket["value_sum"] += value
                bucket["terminal_formal_count"] += int(value > 0)
    return {"rank": "Heroic", "paths": len(paths), "policies": totals}


def _run_job(job: dict[str, Any]) -> dict[str, Any]:
    if job["rank"] == "Epic":
        payload = _epic_shard(job["gear"], "normal_85", job["runs"], job["random_seed"])
    else:
        payload = _heroic_shard(job["gear"], "normal_85", job["runs"], job["random_seed"])
    payload.update({key: job[key] for key in ("seed", "gear_index", "chunk_index", "chunk_count", "runs")})
    payload["status"] = "complete"
    return payload


def _random_seed(seed: int, rank: str, gear_index: int, chunk_index: int) -> int:
    return seed * 1_000_003 + (0 if rank == "Epic" else 500_003) + gear_index * 1_009 + chunk_index * 37


def collect_jobs(
    *, resume_dir: Path, seeds: list[int], epic_gears: list[Any], heroic_gears: list[Any], runs_per_seed: int, chunk_runs: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if runs_per_seed % chunk_runs:
        raise ValueError("runs_per_seed must be divisible by chunk_runs for deterministic coverage")
    jobs: list[dict[str, Any]] = []
    skipped = 0
    chunks = runs_per_seed // chunk_runs
    for rank, gears in (("Epic", epic_gears), ("Heroic", heroic_gears)):
        for seed in seeds:
            for gear_index, gear in enumerate(gears):
                for chunk_index in range(chunks):
                    path = _shard_path(resume_dir, rank, seed, gear_index, chunk_index)
                    if _valid_shard(path):
                        skipped += 1
                        continue
                    jobs.append({
                        "rank": rank, "seed": seed, "gear": gear, "gear_index": gear_index,
                        "chunk_index": chunk_index, "runs": chunk_runs,
                        "random_seed": _random_seed(seed, rank, gear_index, chunk_index), "path": str(path), "chunk_count": chunks,
                    })
    return jobs, {"existing_complete_shards": skipped, "scheduled_shards": len(jobs), "chunks_per_seed_per_gear": chunks}


def execute_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for job, payload in zip(jobs, executor.map(_run_job, jobs)):
                _atomic_json(Path(job["path"]), payload)
    else:
        for job in jobs:
            _atomic_json(Path(job["path"]), _run_job(job))


def _sum_seed(resume_dir: Path, rank: str, seed: int, chunk_half: int | None = None) -> dict[str, Any]:
    total: dict[str, Any] = {"paths": 0}
    for path in sorted((resume_dir / "shards" / rank.lower() / f"seed-{seed}").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "complete":
            continue
        if chunk_half is not None:
            in_first_half = int(payload["chunk_index"]) < int(payload["chunk_count"]) / 2
            if in_first_half != (chunk_half == 0):
                continue
        total["paths"] += int(payload["paths"])
        source = payload["candidates"] if rank == "Epic" else payload["policies"]
        for key, row in source.items():
            target = total.setdefault(key, {"value_sum": 0.0, "stamina_sum": 0.0, "terminal_formal_count": 0})
            for field in target:
                target[field] += row[field]
    return total


def _t95(n: int) -> float:
    values = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}
    return values.get(n, 1.96)


def _ci(samples: list[float]) -> dict[str, float | list[float]]:
    center = mean(samples) if samples else 0.0
    if len(samples) < 2:
        return {"mean": center, "interval95": [center, center], "seed_stddev": 0.0}
    half = _t95(len(samples)) * stdev(samples) / sqrt(len(samples))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": stdev(samples)}


def _scenario_components(epic: dict[str, Any], heroic: dict[str, Any], batch: dict[str, Any]) -> dict[str, dict[str, dict[str, float]]]:
    epic_paths = float(epic["paths"] or 1)
    heroic_paths = float(heroic["paths"] or 1)
    result: dict[str, dict[str, dict[str, float]]] = {}
    for policy in HEROIC_POLICIES:
        for yield_name, multiplier in HEROIC_YIELD_VARIATIONS.items():
            yield_per_batch = float(batch["expected_output_by_rank"]["Heroic"]) * multiplier
            heroic_weight = yield_per_batch * epic_paths / heroic_paths
            scenario = f"{policy}/{yield_name}"
            result[scenario] = {}
            for key, values in epic.items():
                if key == "paths":
                    continue
                numerator = float(values["value_sum"]) + heroic_weight * float(heroic[policy]["value_sum"])
                denominator = epic_paths * float(batch["net_batch_acquisition_stamina"]) + float(values["stamina_sum"]) + heroic_weight * float(heroic[policy]["stamina_sum"])
                result[scenario][key] = {
                    "rate": 100.0 * numerator / denominator if denominator else 0.0,
                    "numerator": numerator,
                    "denominator": denominator,
                    "nonzero_formal_terminal_count": float(values["terminal_formal_count"]) + heroic_weight * float(heroic[policy]["terminal_formal_count"]),
                }
    return result


def _scenario_rates(epic: dict[str, Any], heroic: dict[str, Any], batch: dict[str, Any]) -> dict[str, dict[str, float]]:
    return {
        scenario: {key: value["rate"] for key, value in rows.items()}
        for scenario, rows in _scenario_components(epic, heroic, batch).items()
    }


def summarize(resume_dir: Path, seeds: list[int], batch: dict[str, Any]) -> dict[str, Any]:
    per_seed = {}
    components_by_seed = {}
    halves = {"first": {}, "second": {}}
    for seed in seeds:
        components = _scenario_components(_sum_seed(resume_dir, "Epic", seed), _sum_seed(resume_dir, "Heroic", seed), batch)
        components_by_seed[str(seed)] = components
        per_seed[str(seed)] = {scenario: {key: value["rate"] for key, value in rows.items()} for scenario, rows in components.items()}
        for label, half in (("first", 0), ("second", 1)):
            half_components = _scenario_components(_sum_seed(resume_dir, "Epic", seed, half), _sum_seed(resume_dir, "Heroic", seed, half), batch)
            halves[label][str(seed)] = {scenario: {key: value["rate"] for key, value in rows.items()} for scenario, rows in half_components.items()}
    scenarios = sorted(next(iter(per_seed.values())).keys()) if per_seed else []
    candidate_keys = [strategy.key for strategy in strategies()]
    aggregate: dict[str, Any] = {}
    stable = True
    for scenario in scenarios:
        rates = {key: [per_seed[str(seed)][scenario][key] for seed in seeds] for key in candidate_keys}
        numerators = {key: [components_by_seed[str(seed)][scenario][key]["numerator"] for seed in seeds] for key in candidate_keys}
        denominators = {key: [components_by_seed[str(seed)][scenario][key]["denominator"] for seed in seeds] for key in candidate_keys}
        nonzero = {key: [components_by_seed[str(seed)][scenario][key]["nonzero_formal_terminal_count"] for seed in seeds] for key in candidate_keys}
        epic_value_deltas = {
            key: [
                (_sum_seed(resume_dir, "Epic", seed)[key]["value_sum"] - _sum_seed(resume_dir, "Epic", seed)["A_current_review"]["value_sum"])
                / max(1, _sum_seed(resume_dir, "Epic", seed)["paths"])
                for seed in seeds
            ]
            for key in candidate_keys
        }
        epic_stamina_deltas = {
            key: [
                (_sum_seed(resume_dir, "Epic", seed)[key]["stamina_sum"] - _sum_seed(resume_dir, "Epic", seed)["A_current_review"]["stamina_sum"])
                / max(1, _sum_seed(resume_dir, "Epic", seed)["paths"])
                for seed in seeds
            ]
            for key in candidate_keys
        }
        order = sorted(candidate_keys, key=lambda key: (-mean(rates[key]), key))
        pairwise: dict[str, Any] = {}
        for index, left in enumerate(candidate_keys):
            for right in candidate_keys[index + 1:]:
                pairwise[f"{left} - {right}"] = _ci([a - b for a, b in zip(rates[left], rates[right])])
        leader, second = order[:2]
        leader_difference = _ci([a - b for a, b in zip(rates[leader], rates[second])])
        stable = stable and leader_difference["interval95"][0] > 0
        aggregate[scenario] = {
            "candidate_value_rate_per_100_stamina": {key: _ci(values) for key, values in rates.items()},
            "numerator_ci": {key: _ci(values) for key, values in numerators.items()},
            "denominator_ci": {key: _ci(values) for key, values in denominators.items()},
            "nonzero_formal_terminal_count_ci": {key: _ci(values) for key, values in nonzero.items()},
            "epic_incremental_value_vs_current_per_batch_ci": {key: _ci(values) for key, values in epic_value_deltas.items()},
            "epic_incremental_stamina_vs_current_per_batch_ci": {key: _ci(values) for key, values in epic_stamina_deltas.items()},
            "order": order,
            "leader_vs_second": {"pair": f"{leader} - {second}", **leader_difference},
            "pairwise_differences": pairwise,
            "leader_first_half_rate": _ci([halves["first"][str(seed)][scenario][leader] for seed in seeds]),
            "leader_second_half_rate": _ci([halves["second"][str(seed)][scenario][leader] for seed in seeds]),
            "ranking_stable": leader_difference["interval95"][0] > 0,
        }
    leaders = {row["order"][0] for row in aggregate.values()} if aggregate else set()
    stable = stable and len(leaders) == 1 and len(seeds) >= 2
    return {"per_seed_rates": per_seed, "scenarios": aggregate, "same_leader_all_scenarios": len(leaders) == 1, "independent_seed_count": len(seeds), "stable_for_48_validation": stable, "leader": next(iter(leaders)) if len(leaders) == 1 else None}


def report(data: dict[str, Any]) -> str:
    batch = data["joint_batch"]
    lines = [
        "# 维度裂缝联合批次成本与排序稳定性复核", "",
        "## 成本复核", "",
        "- 旧 `82.9`：单件来源路径把 0.20 个石头当作整件 Epic 的来源信用，漏乘 85/40 次结算。",
        "- 旧 `83.7`：联合工具硬编码的历史值，未与资源模型同步。",
        f"- 采用值：`{batch['net_batch_acquisition_stamina']:.6f}` 体力/联合批次。公式：`85 - (85/40 × 0.20 × 1500) / (1161.1/8)`。",
        "- 14,400 金币仍只在石头实际用于强化时计入材料成本；来源石信用未在强化端再次抵扣。",
        "- Epic/Heroic 同批次只计一次 85 毛体力和一次来源石信用；Heroic 期望产出为 85/23.81，且标记为 estimated。", "",
        "| 路径 | 石头结算数 | 来源石信用（体力） | 净成本（体力） | 状态 |", "|---|---:|---:|---:|---|",
        "| 旧单件路径 | 0.20 | 2.067 | 82.933 | 漏乘批次结算次数，已修复 |",
        "| 旧联合工具 | 历史硬编码 | - | 83.700 | 已删除，不能再使用 |",
        f"| 联合批次接口 | {batch['expected_lower_stone_units']:.3f} | {batch['lower_stone_credit_stamina']:.6f} | {batch['net_batch_acquisition_stamina']:.6f} | 唯一采用值 |", "",
        "## 研究口径", "",
        f"- 独立 seeds：{', '.join(map(str, data['seeds']))}；每件轨迹：{data['runs_per_gear']}；分片：{data['execution']['complete_shards']}；断点续跑跳过：{data['execution']['existing_complete_shards']}。",
        "- 分子仅为正式体系终局价值（含合法满值转换）；不使用 GS75、多体系数量或未校准速度价值。速度仅保留 >=22 才可未来单独校准的资格，本轮无该映射。",
        "- Heroic 固定 baili_marginal_low、dp_enabled=false，并同轨迹给出 all_stop 敏感性；不修改 Heroic 策略或 lambda。", "",
        "## 场景结果", "",
        "| 场景 | 第一名 | 第一名-第二名 95% CI | 前半/后半价值率 | 稳定 |",
        "|---|---|---:|---:|---|",
    ]
    for scenario, summary in data["summary"]["scenarios"].items():
        ci = summary["leader_vs_second"]["interval95"]
        first = summary["leader_first_half_rate"]["mean"]
        second = summary["leader_second_half_rate"]["mean"]
        lines.append(f"| {scenario} | {summary['order'][0]} | [{ci[0]:.6f}, {ci[1]:.6f}] | {first:.6f}/{second:.6f} | {'是' if summary['ranking_stable'] else '否'} |")
        lines.extend(["", f"### {scenario} 全部候选", "", "| 候选 | 价值率/100体力 95% CI | 分子 95% CI | 分母 95% CI | Epic 增量价值/批次 95% CI | Epic 增量体力/批次 95% CI | 非零正式终局 95% CI |", "|---|---:|---:|---:|---:|---:|---:|"])
        for candidate in summary["order"]:
            rate = summary["candidate_value_rate_per_100_stamina"][candidate]["interval95"]
            numerator = summary["numerator_ci"][candidate]["interval95"]
            denominator = summary["denominator_ci"][candidate]["interval95"]
            epic_value = summary["epic_incremental_value_vs_current_per_batch_ci"][candidate]["interval95"]
            epic_stamina = summary["epic_incremental_stamina_vs_current_per_batch_ci"][candidate]["interval95"]
            nonzero = summary["nonzero_formal_terminal_count_ci"][candidate]["interval95"]
            lines.append(f"| {candidate} | [{rate[0]:.6f}, {rate[1]:.6f}] | [{numerator[0]:.3f}, {numerator[1]:.3f}] | [{denominator[0]:.3f}, {denominator[1]:.3f}] | [{epic_value[0]:.6f}, {epic_value[1]:.6f}] | [{epic_stamina[0]:.6f}, {epic_stamina[1]:.6f}] | [{nonzero[0]:.2f}, {nonzero[1]:.2f}] |")
    conclusion = "允许进入 48 件独立验证" if data["summary"]["stable_for_48_validation"] else "不允许进入 48 件验证：独立 seed 不足、候选排序跨零或不同敏感性场景第一名不一致"
    lines.extend(["", "## 结论", "", f"- {conclusion}。", "- 成本口径已变化；已发布 Epic/Heroic lambda 需要另行重校准，本任务未覆盖也未写回。", ""])
    return "\n".join(lines)


def run_study(source_path: Path, records_path: Path, *, resume_dir: Path, seeds: list[int], runs_per_seed: int, chunk_runs: int, workers: int) -> dict[str, Any]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    records = json.loads(records_path.read_text(encoding="utf-8"))
    partition = build_partition(source, records, blind_size=24, seed=20260712)
    epic_gears = [row["gear"] for row in partition["training"]] + [row["gear"] for row in partition["speed_hard"]]
    heroic_gears = _source_rank_gears(source, "Heroic")
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    jobs, execution = collect_jobs(resume_dir=resume_dir, seeds=seeds, epic_gears=epic_gears, heroic_gears=heroic_gears, runs_per_seed=runs_per_seed, chunk_runs=chunk_runs)
    started = time.monotonic()
    execute_jobs(jobs, workers)
    execution["scheduled_runtime_seconds"] = time.monotonic() - started
    execution["complete_shards"] = execution["existing_complete_shards"] + execution["scheduled_shards"]
    return {
        "study_status": "research_not_for_release",
        "joint_batch": batch,
        "seeds": seeds,
        "runs_per_seed": runs_per_seed,
        "runs_per_gear": runs_per_seed * len(seeds),
        "epic_gear_count": len(epic_gears),
        "heroic_gear_count": len(heroic_gears),
        "execution": execution,
        "summary": summarize(resume_dir, seeds, batch),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumable riftslash joint-batch stability study")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "riftslash_joint_batch_resume_20260712")
    parser.add_argument("--seeds", default="20260712,20260713,20260714,20260715,20260716")
    parser.add_argument("--runs-per-seed", type=int, default=1000)
    parser.add_argument("--chunk-runs", type=int, default=250)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "riftslash_joint_batch_stability_20260712.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "riftslash_joint_batch_stability_20260712.md")
    args = parser.parse_args()
    seeds = [int(token) for token in args.seeds.split(",") if token.strip()]
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    data = run_study(args.source, args.records, resume_dir=args.resume_dir, seeds=seeds, runs_per_seed=args.runs_per_seed, chunk_runs=args.chunk_runs, workers=max(1, args.workers))
    if args.json_output.exists():
        try:
            previous = json.loads(args.json_output.read_text(encoding="utf-8"))
            previous_execution = previous.get("execution", {})
            previous_runtime = previous_execution.get("previous_completed_runtime_seconds") or previous_execution.get("scheduled_runtime_seconds")
            if previous_runtime:
                data["execution"]["previous_completed_runtime_seconds"] = previous_runtime
        except (OSError, ValueError, TypeError):
            pass
    _atomic_json(args.json_output, data)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(report(data), encoding="utf-8")


if __name__ == "__main__":
    main()
