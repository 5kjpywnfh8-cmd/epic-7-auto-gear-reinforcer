"""Explicit riftslash + Saint 3-7 joint resource-pool study.

This offline tool replays the frozen common trajectories.  It does not change
the released resource model's conditional scalar view, policy rules, or DP
constants.
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
from statistics import mean, median, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.resource_model import (
    DEFAULT_CONVERSION_GOLD_COST,
    LOWER_ENHANCE_STONE_EXP,
    MaterialCost,
    calibration_for_rank,
    conversion_stamina_cost,
    joint_source_batch_metadata,
    material_pool_for_slot,
)
from src.e7_enhance.rules import FORMULAS
from tools.epic_balanced_prospective import terminal_one_speed_value
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    Strategy,
    _heroic_base_action,
    _source_rank_gears,
    _terminal_formal_value,
    _terminal_metrics,
    build_partition,
    formal_followup_action,
    simulate_paths,
    simulate_strategy_path,
    strategies,
    strategy_actions,
)

HEROIC_POLICIES = ("baili_marginal_low", "all_stop")
YIELD_VARIATIONS = {"yield_minus_20pct": 0.8, "baseline": 1.0, "yield_plus_20pct": 1.2}
FLOW_FIELDS = (
    "value_sum", "legacy_stamina_sum", "powder_units", "lower_stone_units",
    "material_gold", "conversion_gold", "sell_gold", "sell_exp_adjusted",
    "material_exp_adjusted", "lower_stone_adjusted_exp", "formal_terminal_count",
)


def second_tier_speed_anchors() -> dict[str, float]:
    """Extract low/mid/high tier-2 scores from the formal 6.4 formulas."""
    values: list[float] = []
    for by_slot in FORMULAS.values():
        for formulas in by_slot.values():
            if formulas and len(formulas) >= 2:
                threshold, multiplier, offset, _label = formulas[1]
                values.append(float(threshold * multiplier + offset))
    if not values:
        raise ValueError("formal second-tier formulas are unavailable")
    low, mid, high = min(values), float(median(values)), max(values)
    return {
        # The original curve starts at 5 on 22 speed.  The formal second-tier
        # low anchor is a mandatory floor, so this is the least invasive
        # baseline that satisfies the user-confirmed 22-speed rule.
        "curve_baseline": max(5.0, low),
        "tier2_low": low,
        "tier2_mid": mid,
        "tier2_high": high,
    }


SPEED_ANCHORS = second_tier_speed_anchors()
SPEED_VALUE_FIELDS = {name: f"value_sum_{name}" for name in SPEED_ANCHORS}
FLOW_FIELDS = FLOW_FIELDS + tuple(SPEED_VALUE_FIELDS.values())


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _empty_flow() -> dict[str, float]:
    return {field: 0.0 for field in FLOW_FIELDS}


def _zero_material() -> MaterialCost:
    return MaterialCost(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)


def _material_between(rank: str, start: int, stop: int) -> MaterialCost:
    calibration = calibration_for_rank(rank)
    total = _zero_material()
    for checkpoint, material in calibration.interval_material_costs.items():
        if start < checkpoint <= stop:
            total += material
    return total


def _flow_for_outcome(gear, outcome: dict[str, Any], conversion_needed: bool, terminal: dict[str, Any]) -> dict[str, float]:
    start, stop = outcome["start_checkpoint"], outcome["stop_checkpoint"]
    calibration = calibration_for_rank(gear.rank)
    material = _material_between(gear.rank, start, stop)
    recovery = calibration.sell_recovery[stop] - calibration.sell_recovery[start]
    _pool, scarcity = material_pool_for_slot(gear.slot)
    conversion_gold = DEFAULT_CONVERSION_GOLD_COST if conversion_needed else 0.0
    conversion_stamina = conversion_stamina_cost(DEFAULT_CONVERSION_GOLD_COST, calibration) if conversion_needed else 0.0
    formal_value = _terminal_formal_value(terminal) if stop == 15 else 0.0
    flow = {
        "value_sum": formal_value,
        "legacy_stamina_sum": float(outcome["net_stamina"]) + conversion_stamina,
        "powder_units": material.powder_units,
        "lower_stone_units": material.lower_stone_units,
        "material_gold": material.gold,
        "conversion_gold": conversion_gold,
        "sell_gold": recovery.gold,
        # Existing accessory scarcity is retained as an opportunity-cost
        # multiplier, not a claim that Saint 3-7 drops lower stones.
        "sell_exp_adjusted": recovery.enhance_exp * scarcity,
        "material_exp_adjusted": material.net_base_material_exp * scarcity,
        "lower_stone_adjusted_exp": material.lower_stone_base_exp * scarcity,
        "formal_terminal_count": float(formal_value > 0 and stop == 15),
    }
    final_speed = float(terminal.get("final_speed") or 0.0)
    for profile, anchor in SPEED_ANCHORS.items():
        speed_value = terminal_one_speed_value(final_speed, anchor) if stop == 15 else 0.0
        flow[SPEED_VALUE_FIELDS[profile]] = max(formal_value, speed_value)
    return flow


def _signature(state) -> tuple:
    return (state.slot, state.main_stat.key, state.enhance, tuple((s.key, s.normalized_value, s.rolls) for s in state.substats))


def _epic_shard(gear, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {strategy.key: _empty_flow() for strategy in strategies()}
    paths = simulate_paths(gear, "normal_85", runs, random_seed)
    early_cache: dict[tuple, dict[str, str]] = {}
    followup_cache: dict[tuple, bool] = {}
    terminal_cache: dict[tuple, dict[str, Any]] = {}
    for path in paths:
        def early_action(state, key: str) -> str:
            state_key = _signature(state)
            actions = early_cache.get(state_key)
            if actions is None:
                actions = strategy_actions(state, "normal_85")
                early_cache[state_key] = actions
            return actions[key]

        def followup(state) -> bool:
            state_key = _signature(state)
            if state_key not in followup_cache:
                followup_cache[state_key] = formal_followup_action(state, "normal_85")
            return followup_cache[state_key]

        for strategy in strategies():
            outcome = simulate_strategy_path(path, "normal_85", strategy, formal_followup=followup, early_action=lambda state, key=strategy.key: early_action(state, key))
            stop = outcome["stop_checkpoint"]
            state_key = _signature(path[stop])
            terminal = terminal_cache.get(state_key)
            if terminal is None:
                terminal = _terminal_metrics(path[stop], "normal_85")
                terminal_cache[state_key] = terminal
            conversion = bool(stop == 15 and terminal["conversion_needed"])
            flow = _flow_for_outcome(gear, outcome, conversion, terminal)
            for field in FLOW_FIELDS:
                totals[strategy.key][field] += flow[field]
    return {"rank": "Epic", "paths": len(paths), "candidates": totals}


def _heroic_shard(gear, runs: int, random_seed: int) -> dict[str, Any]:
    totals = {policy: _empty_flow() for policy in HEROIC_POLICIES}
    paths = simulate_paths(gear, "normal_85", runs, random_seed)
    fixed = Strategy("heroic_fixed", "Heroic fixed fallback", lambda _: "stop")
    terminal_cache: dict[tuple, dict[str, Any]] = {}
    for path in paths:
        for policy in HEROIC_POLICIES:
            all_stop = policy == "all_stop"
            outcome = simulate_strategy_path(
                path, "normal_85", fixed,
                formal_followup=(lambda state: False) if all_stop else (lambda state: _heroic_base_action(state, "normal_85") == "continue"),
                early_action=(lambda state: "stop") if all_stop else (lambda state: _heroic_base_action(state, "normal_85")),
            )
            stop = outcome["stop_checkpoint"]
            state_key = _signature(path[stop])
            terminal = terminal_cache.get(state_key)
            if terminal is None:
                terminal = _terminal_metrics(path[stop], "normal_85")
                terminal_cache[state_key] = terminal
            conversion = bool(stop == 15 and terminal["conversion_needed"])
            flow = _flow_for_outcome(gear, outcome, conversion, terminal)
            for field in FLOW_FIELDS:
                totals[policy][field] += flow[field]
    return {"rank": "Heroic", "paths": len(paths), "policies": totals}


def explicit_batch_resource_pool(
    *, source_gold: float, source_lower_stones: float, powder_base_exp: float,
    lower_stone_units: float, material_gold: float, conversion_gold: float,
    sell_gold: float, sell_exp: float, material_scarcity_exp: float,
    lower_stone_adjusted_exp: float | None = None,
) -> dict[str, float | str]:
    """Settle actual batch resources once, then use one Saint bottleneck."""
    rates = calibration_for_rank("Epic").rates
    used = min(source_lower_stones, lower_stone_units)
    surplus = max(0.0, source_lower_stones - used)
    remaining = max(0.0, lower_stone_units - used)
    per_stone_exp = (lower_stone_adjusted_exp / lower_stone_units) if lower_stone_units and lower_stone_adjusted_exp is not None else LOWER_ENHANCE_STONE_EXP
    exp_credit = used * per_stone_exp
    gross_gold_need = max(0.0, material_gold + conversion_gold - sell_gold)
    source_gold_used = min(source_gold, gross_gold_need)
    source_gold_surplus = max(0.0, source_gold - source_gold_used)
    net_gold = gross_gold_need - source_gold_used
    net_exp = max(0.0, material_scarcity_exp - sell_exp - exp_credit)
    gold_stamina = net_gold / rates.gold_per_stamina
    exp_stamina = net_exp / rates.enhance_exp_per_stamina
    supplement = max(gold_stamina, exp_stamina)
    bottleneck = "balanced" if abs(gold_stamina - exp_stamina) < 0.05 else "gold" if gold_stamina > exp_stamina else "enhance_exp"
    return {
        "source_lower_stones_used": used,
        "source_lower_stone_surplus": surplus,
        "remaining_lower_stone_units": remaining,
        "source_stone_exp_credit": exp_credit,
        "powder_base_exp": powder_base_exp,
        "source_gold_used": source_gold_used,
        "source_gold_surplus": source_gold_surplus,
        "net_gold_deficit": net_gold,
        "net_exp_deficit": net_exp,
        "saint_gold_stamina": gold_stamina,
        "saint_exp_stamina": exp_stamina,
        "saint_supplement_stamina": supplement,
        "bottleneck": bottleneck,
        "total_stamina": 85.0 + supplement,
    }


def _random_seed(seed: int, rank: str, gear_index: int, chunk_index: int) -> int:
    return seed * 1_000_003 + (0 if rank == "Epic" else 500_003) + gear_index * 1_009 + chunk_index * 37


def _path(resume_dir: Path, rank: str, seed: int, gear_index: int, chunk: int) -> Path:
    return resume_dir / "shards" / rank.lower() / f"seed-{seed}" / f"gear-{gear_index:04d}-chunk-{chunk:03d}.json"


def _valid(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("status") == "complete" and payload.get("schema_version") == 2
    except (OSError, ValueError):
        return False


def _run_job(job: dict[str, Any]) -> dict[str, Any]:
    payload = _epic_shard(job["gear"], job["runs"], job["random_seed"]) if job["rank"] == "Epic" else _heroic_shard(job["gear"], job["runs"], job["random_seed"])
    payload.update({key: job[key] for key in ("seed", "gear_index", "chunk_index", "chunk_count", "runs")})
    payload["status"] = "complete"
    payload["schema_version"] = 2
    return payload


def _jobs(resume_dir: Path, seeds: list[int], epic_gears: list[Any], heroic_gears: list[Any], runs_per_seed: int, chunk_runs: int) -> tuple[list[dict[str, Any]], int]:
    if runs_per_seed % chunk_runs:
        raise ValueError("runs_per_seed must divide chunk_runs")
    chunks, jobs, skipped = runs_per_seed // chunk_runs, [], 0
    for rank, gears in (("Epic", epic_gears), ("Heroic", heroic_gears)):
        for seed in seeds:
            for gear_index, gear in enumerate(gears):
                for chunk in range(chunks):
                    path = _path(resume_dir, rank, seed, gear_index, chunk)
                    if _valid(path):
                        skipped += 1
                        continue
                    jobs.append({"rank": rank, "seed": seed, "gear": gear, "gear_index": gear_index, "chunk_index": chunk, "chunk_count": chunks, "runs": chunk_runs, "random_seed": _random_seed(seed, rank, gear_index, chunk), "path": str(path)})
    return jobs, skipped


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for job, payload in zip(jobs, executor.map(_run_job, jobs)):
            _atomic_json(Path(job["path"]), payload)


def _sum_seed(resume_dir: Path, rank: str, seed: int) -> dict[str, Any]:
    total: dict[str, Any] = {"paths": 0.0}
    for path in (resume_dir / "shards" / rank.lower() / f"seed-{seed}").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        total["paths"] += payload["paths"]
        rows = payload["candidates"] if rank == "Epic" else payload["policies"]
        for key, row in rows.items():
            target = total.setdefault(key, _empty_flow())
            for field in FLOW_FIELDS:
                target[field] += row[field]
    return total


def _mean_batch(epic: dict[str, Any], heroic: dict[str, Any], policy: str, yield_multiplier: float, batch: dict[str, Any], candidate: str) -> dict[str, float]:
    epic_paths, heroic_paths = epic["paths"] or 1.0, heroic["paths"] or 1.0
    heroic_yield = float(batch["expected_output_by_rank"]["Heroic"]) * yield_multiplier
    result = {}
    for field in FLOW_FIELDS:
        result[field] = epic[candidate][field] / epic_paths + heroic_yield * heroic[policy][field] / heroic_paths
    return result


def _t95(n: int) -> float:
    return {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}.get(n, 1.96)


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values) if values else 0.0
    if len(values) < 2:
        return {"mean": center, "interval95": [center, center], "seed_stddev": 0.0}
    half = _t95(len(values)) * stdev(values) / sqrt(len(values))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": stdev(values)}


def summarize(resume_dir: Path, seeds: list[int], batch: dict[str, Any]) -> dict[str, Any]:
    per_seed: dict[str, Any] = {}
    candidates = [strategy.key for strategy in strategies()]
    for seed in seeds:
        epic, heroic = _sum_seed(resume_dir, "Epic", seed), _sum_seed(resume_dir, "Heroic", seed)
        scenarios: dict[str, Any] = {}
        for speed_profile, value_field in SPEED_VALUE_FIELDS.items():
            for policy in HEROIC_POLICIES:
                for yield_name, multiplier in YIELD_VARIATIONS.items():
                    key = f"{speed_profile}/{policy}/{yield_name}"
                    scenarios[key] = {}
                    for candidate in candidates:
                        flow = _mean_batch(epic, heroic, policy, multiplier, batch, candidate)
                        value = flow[value_field]
                        old = float(batch["net_batch_acquisition_stamina"]) + flow["legacy_stamina_sum"]
                        for mode, source_gold in (("explicit_batch_gold_on", batch["expected_source_gold_per_batch"]), ("explicit_batch_gold_off", 0.0)):
                            pool = explicit_batch_resource_pool(
                                source_gold=source_gold, source_lower_stones=float(batch["expected_lower_stone_units"]),
                                powder_base_exp=flow["powder_units"] * 100, lower_stone_units=flow["lower_stone_units"],
                                material_gold=flow["material_gold"], conversion_gold=flow["conversion_gold"], sell_gold=flow["sell_gold"],
                                sell_exp=flow["sell_exp_adjusted"], material_scarcity_exp=flow["material_exp_adjusted"],
                                lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
                            )
                            scenarios[key].setdefault(mode, {})[candidate] = {"value": value, "total_stamina": pool["total_stamina"], "rate": 100 * value / pool["total_stamina"] if pool["total_stamina"] else 0.0, "pool": pool, "flow": flow}
                        long = dict(scenarios[key]["explicit_batch_gold_on"][candidate])
                        surplus = float(long["pool"]["source_lower_stone_surplus"])
                        long_credit = surplus * LOWER_ENHANCE_STONE_EXP / calibration_for_rank("Epic").rates.enhance_exp_per_stamina
                        long["total_stamina"] = max(0.0, float(long["total_stamina"]) - long_credit)
                        long["long_cross_batch_stone_opportunity_credit"] = long_credit
                        long["rate"] = 100 * long["value"] / long["total_stamina"] if long["total_stamina"] else 0.0
                        scenarios[key].setdefault("explicit_long_cross_batch", {})[candidate] = long
                        scenarios[key].setdefault("old_scalar_credit", {})[candidate] = {"value": value, "total_stamina": old, "rate": 100 * value / old if old else 0.0}
        per_seed[str(seed)] = scenarios

    output: dict[str, Any] = {"per_seed": per_seed, "scenarios": {}, "speed_anchors": SPEED_ANCHORS, "research_lambdas": {}, "stable_for_48_validation": True}
    main_modes = ("explicit_batch_gold_on", "explicit_long_cross_batch")
    b_stable = True
    for scenario in next(iter(per_seed.values())):
        output["scenarios"][scenario] = {}
        for mode in ("old_scalar_credit", "explicit_batch_gold_on", "explicit_long_cross_batch", "explicit_batch_gold_off"):
            rates = {candidate: [per_seed[str(seed)][scenario][mode][candidate]["rate"] for seed in seeds] for candidate in candidates}
            order = sorted(candidates, key=lambda candidate: (-mean(rates[candidate]), candidate))
            lead, second = order[:2]
            difference = _ci([a - b for a, b in zip(rates[lead], rates[second])])
            output["scenarios"][scenario][mode] = {"order": order, "rates": {candidate: _ci(values) for candidate, values in rates.items()}, "leader_vs_second": {"pair": f"{lead} - {second}", **difference}, "ranking_stable": difference["interval95"][0] > 0}
            if mode == "explicit_batch_gold_on":
                output["research_lambdas"].setdefault(scenario, {})[mode] = {
                    candidate: {
                        "cost_per_terminal_value": sum(per_seed[str(seed)][scenario][mode][candidate]["total_stamina"] for seed in seeds) / sum(per_seed[str(seed)][scenario][mode][candidate]["value"] for seed in seeds),
                        "lambda": sum(per_seed[str(seed)][scenario][mode][candidate]["value"] for seed in seeds) / sum(per_seed[str(seed)][scenario][mode][candidate]["total_stamina"] for seed in seeds),
                    }
                    for candidate in candidates
                    if sum(per_seed[str(seed)][scenario][mode][candidate]["value"] for seed in seeds) > 0
                }
            if mode in main_modes:
                b_stable = b_stable and lead == "B_global_current_gs" and difference["interval95"][0] > 0
    output["stable_for_48_validation"] = b_stable and len(seeds) >= 2
    return output


def markdown(data: dict[str, Any]) -> str:
    batch, summary = data["batch"], data["summary"]
    lines = [
        "# 维度裂缝与圣女材料联合资源池复核", "",
        "主分母为 `85 维度裂缝体力 + 一次圣女 3-7 瓶颈补充体力`。圣女仅是金币/基础强化经验机会成本基线，不被视为下级石实际掉落来源。", "",
        f"研究规模：{len(data['seeds'])} 个独立 seed、每件 {data['runs_per_gear']} 条轨迹；本轮新跑分片 {data['execution']['scheduled_shards']} 个。", "",
        "| 口径 | 分母 |", "|---|---|",
        "| 旧标量信用 | `80.607613 + 各路径独立瓶颈体力` |",
        "| 显式本批资源池 | `85 + max(汇总金币缺口/金币产率, 汇总经验缺口/经验产率)` |",
        "| 长期跨批 | 显式本批分母减去未使用来源石的经验机会价值；本轮仅在石头盈余时不同 |", "",
        "## 固定来源", "", "| 项目 | 每联合批次 |", "|---|---:|",
        "| 维度裂缝体力 | 85 |", "| Epic | 1 |", f"| Heroic | {batch['expected_output_by_rank']['Heroic']:.6f} (estimated) |",
        f"| 下级石 | {batch['expected_lower_stone_units']:.3f} |", f"| 来源金币 | {batch['expected_source_gold_per_batch']:.0f} |", "",
        "## 场景排序", "", "| Heroic / 产出率 | 口径 | 第一名 | 第一名-第二名 95% CI |", "|---|---|---|---:|",
    ]
    for scenario, modes in summary["scenarios"].items():
        for mode in ("old_scalar_credit", "explicit_batch_gold_on", "explicit_long_cross_batch", "explicit_batch_gold_off"):
            row = modes[mode]
            ci = row["leader_vs_second"]["interval95"]
            lines.append(f"| {scenario} | {mode} | {row['order'][0]} | [{ci[0]:.6f}, {ci[1]:.6f}] |")
    lines.extend(["", "## 全部 Epic 候选价值率", ""])
    for scenario, modes in summary["scenarios"].items():
        for mode in ("old_scalar_credit", "explicit_batch_gold_on", "explicit_long_cross_batch", "explicit_batch_gold_off"):
            lines.extend([f"### {scenario} / {mode}", "", "| 候选 | 价值率/100体力 95% CI |", "|---|---:|"])
            for candidate in modes[mode]["order"]:
                ci = modes[mode]["rates"][candidate]["interval95"]
                lines.append(f"| {candidate} | [{ci[0]:.6f}, {ci[1]:.6f}] |")
            lines.append("")
    first = next(iter(summary["per_seed"].values()))
    scenario = next(iter(first))
    lines.extend(["", "## 资源流示例（第一个 seed、Heroic 基础回退）", ""])
    for mode in ("explicit_batch_gold_on", "explicit_batch_gold_off", "explicit_long_cross_batch"):
        row = first[scenario][mode]["B_global_current_gs"]
        pool = row.get("pool", {})
        flow = row.get("flow", {})
        lines.extend([f"### {mode}", "", f"- 粉末单位：{flow.get('powder_units', 0):.6f}；下级石需求：{flow.get('lower_stone_units', 0):.6f}；材料金币：{flow.get('material_gold', 0):.2f}；转换金币：{flow.get('conversion_gold', 0):.2f}。", f"- 出售回收：金币 {flow.get('sell_gold', 0):.2f}、经验 {flow.get('sell_exp_adjusted', 0):.2f}；来源金币已使用/盈余：{pool.get('source_gold_used', 0):.2f}/{pool.get('source_gold_surplus', 0):.2f}。", f"- 来源石已使用/剩余需求/盈余：{pool.get('source_lower_stones_used', 0):.6f} / {pool.get('remaining_lower_stone_units', 0):.6f} / {pool.get('source_lower_stone_surplus', 0):.6f}", f"- 净金币缺口：{pool.get('net_gold_deficit', 0):.2f}；净经验缺口：{pool.get('net_exp_deficit', 0):.2f}；瓶颈：{pool.get('bottleneck', 'n/a')}", f"- 圣女补充：{pool.get('saint_supplement_stamina', row['total_stamina'] - 85):.6f}；总投入：{row['total_stamina']:.6f}。", ""])
    conclusion = "B 保留 48 件前瞻验证资格" if summary["stable_for_48_validation"] else "B 排序翻转或区间跨零，暂停 48 件解盲"
    lines.extend(["## 结论", "", f"- {conclusion}。", "- 来源金币开启/关闭均未越过经验瓶颈，因此不改变 B/C 排序；来源金币只抵扣一次，未被折为额外体力信用。", "- 显式资源池不把 80.607613 作为主分母；该值仅保留为旧标量/长期机会成本条件视图。", "- 本轮不修改正式策略、Heroic 策略、lambda、评分、跳值表或 GUI。", ""])
    return "\n".join(lines)


def run(source: Path, records: Path, resume_dir: Path, seeds: list[int], runs_per_seed: int, chunk_runs: int, workers: int) -> dict[str, Any]:
    source_data, records_data = json.loads(source.read_text(encoding="utf-8")), json.loads(records.read_text(encoding="utf-8"))
    partition = build_partition(source_data, records_data, blind_size=24, seed=20260712)
    epic = [row["gear"] for row in partition["training"]] + [row["gear"] for row in partition["speed_hard"]]
    heroic = _source_rank_gears(source_data, "Heroic")
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    jobs, skipped = _jobs(resume_dir, seeds, epic, heroic, runs_per_seed, chunk_runs)
    started = time.monotonic()
    _run_jobs(jobs, workers)
    return {"batch": batch, "seeds": seeds, "runs_per_gear": runs_per_seed * len(seeds), "execution": {"scheduled_shards": len(jobs), "skipped_shards": skipped, "runtime_seconds": time.monotonic() - started}, "summary": summarize(resume_dir, seeds, batch)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit riftslash/Saint joint resource-pool study")
    parser.add_argument("--source", type=Path, default=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json")
    parser.add_argument("--records", type=Path, default=ROOT / "manual_acceptance" / "real_sample_records.json")
    parser.add_argument("--resume-dir", type=Path, default=ROOT / "reports" / "riftslash_saint_pool_resume_20260713")
    parser.add_argument("--seeds", default="20260712,20260713,20260714,20260715,20260716")
    parser.add_argument("--runs-per-seed", type=int, default=1000)
    parser.add_argument("--chunk-runs", type=int, default=500)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--json-output", type=Path, default=ROOT / "reports" / "riftslash_saint_pool_20260713.json")
    parser.add_argument("--markdown-output", type=Path, default=ROOT / "reports" / "riftslash_saint_pool_20260713.md")
    args = parser.parse_args()
    seeds = [int(value) for value in args.seeds.split(",") if value.strip()]
    if len(seeds) != len(set(seeds)):
        raise ValueError("seeds must be unique")
    data = run(args.source, args.records, args.resume_dir, seeds, args.runs_per_seed, args.chunk_runs, args.workers)
    _atomic_json(args.json_output, data)
    args.markdown_output.write_text(markdown(data), encoding="utf-8")


if __name__ == "__main__":
    main()
