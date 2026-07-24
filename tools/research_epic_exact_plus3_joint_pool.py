"""Five-seed conditional joint pool replay for the frozen exact +3 candidate."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
from statistics import mean, stdev
from math import sqrt
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.models import Gear
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow, _flow
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, Strategy, _source_rank_gears, formal_followup_action, simulate_paths, simulate_strategy_path, summarize_incremental_cost
from tools.research_epic_exact_plus3 import _feature_view, _parse_rule, action_for_rule, load_real_plus0
from tools.research_riftslash_saint_pool import HEROIC_POLICIES, YIELD_VARIATIONS, _t95, explicit_batch_resource_pool


SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
SCHEMA_VERSION = 1
CANDIDATES = ("current_formal", "exact_safe_stop")
DEFAULT_CANDIDATE = ROOT / "reports" / "epic_exact_plus3_candidate_20260717.json"
DEFAULT_SOURCE = ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json"
DEFAULT_RESUME = ROOT / "reports" / "epic_exact_plus3_joint_pool_resume_20260717"
DEFAULT_JSON = ROOT / "reports" / "epic_exact_plus3_joint_pool_20260717.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_exact_plus3_joint_pool_20260717.md"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _action(gear: Gear, *, rule: Any | None) -> str:
    recommendation = str(advise_gear(gear, item_source="normal_85", gear_source=GEAR_SOURCE)["summary"]["recommendation"])
    current = "stop" if recommendation == "stop" else "continue"
    return action_for_rule(current, _feature_view(gear), rule)


def _outcome_at(start: int, stop: int, gear: Gear) -> dict[str, Any]:
    costs = summarize_incremental_cost(gear.slot, gear.rank, start, stop)
    return {"start_checkpoint": start, "stop_checkpoint": stop, "net_stamina": costs["net_stamina"], "net_gold": costs["net_gold"], "costs": costs}


def _epic_shard(gear: Gear, plus0_rule: Any | None, plus3_rule: Any | None, runs: int, seed: int) -> dict[str, Any]:
    totals = {key: _empty_flow() for key in CANDIDATES}
    rules = {"current_formal": (None, None), "exact_safe_stop": (plus0_rule, plus3_rule)}
    for key, (rule0, rule3) in rules.items():
        if _action(gear, rule=rule0) == "stop":
            _add(totals[key], _flow(gear, {0: gear}, _outcome_at(0, 0, gear)))
            continue
        for branch_index, branch in enumerate(enumerate_normal_epic_plus3(gear)):
            probability = float(branch.probability)
            # Account for +0 -> +3 once before replaying later common paths.
            _add(totals[key], _flow(gear, {0: gear, 3: branch.gear}, _outcome_at(0, 3, gear)), probability)
            paths = simulate_paths(branch.gear, "normal_85", runs, seed * 1_000_003 + branch_index * 1009)
            for path in paths:
                outcome = simulate_strategy_path(
                    path,
                    "normal_85",
                    Strategy("exact_safe_stop", "frozen exact stop", lambda _features: "stop"),
                    early_action=lambda state, current_rule=rule3: _action(state, rule=current_rule),
                    formal_followup=lambda state: formal_followup_action(state, "normal_85"),
                )
                _add(totals[key], _flow(branch.gear, path, outcome), probability / runs)
    return {"paths": 1.0, "candidates": totals}


def _heroic_shard(gear: Gear, runs: int, seed: int) -> dict[str, Any]:
    total = _empty_flow()
    fixed = Strategy("heroic_m1", "released Heroic M1", lambda _features: "stop")
    for path in simulate_paths(gear, "normal_85", runs, seed):
        outcome = simulate_strategy_path(
            path,
            "normal_85",
            fixed,
            early_action=lambda state: _action(state, rule=None),
            formal_followup=lambda state: _action(state, rule=None) != "stop",
        )
        _add(total, _flow(gear, path, outcome), 1.0 / runs)
    return {"paths": 1.0, "policies": {"released_m1": total}}


def _path(resume: Path, rank: str, seed: int, index: int) -> Path:
    return resume / rank.lower() / f"seed-{seed}" / f"gear-{index:04d}.json"


def _valid(path: Path, expected_hash: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return payload.get("status") == "complete" and payload.get("schema_version") == SCHEMA_VERSION and payload.get("input_hash") == expected_hash


def _worker(job: dict[str, Any]) -> str:
    payload = _epic_shard(job["gear"], job["plus0_rule"], job["plus3_rule"], job["runs"], job["seed"]) if job["rank"] == "Epic" else _heroic_shard(job["gear"], job["runs"], job["seed"])
    payload.update({key: job[key] for key in ("rank", "seed", "index", "input_hash")})
    payload.update({"status": "complete", "schema_version": SCHEMA_VERSION})
    _atomic_json(Path(job["path"]), payload)
    return str(job["path"])


def _gear_hash(gear: Gear, candidate_hash: str, runs: int, rank: str) -> str:
    return __import__("hashlib").sha256(json.dumps({"gear": gear.to_dict(), "candidate": candidate_hash, "runs": runs, "rank": rank}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if not jobs:
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(executor.map(_worker, jobs))


def _sum_seed(resume: Path, rank: str, seed: int, expected: dict[int, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"paths": 0.0}
    for index, input_hash in expected.items():
        path = _path(resume, rank, seed, index)
        if not _valid(path, input_hash):
            raise RuntimeError(f"incomplete joint shard: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        result["paths"] += float(payload["paths"])
        rows = payload["candidates"] if rank == "Epic" else payload["policies"]
        for key, flow in rows.items():
            target = result.setdefault(key, _empty_flow())
            _add(target, flow)
    return result


def _combine(epic: dict[str, Any], heroic: dict[str, Any], heroic_yield: float, candidate: str) -> dict[str, float]:
    return {
        field: float(epic[candidate][field]) / float(epic["paths"]) + heroic_yield * float(heroic["released_m1"][field]) / float(heroic["paths"])
        for field in FLOW_WITH_METRICS
    }


def _pool(flow: dict[str, float], batch: dict[str, Any]) -> dict[str, Any]:
    return explicit_batch_resource_pool(
        source_gold=float(batch["expected_source_gold_per_batch"]),
        source_lower_stones=float(batch["expected_lower_stone_units"]),
        powder_base_exp=flow["powder_units"] * 100,
        lower_stone_units=flow["lower_stone_units"],
        material_gold=flow["material_gold"], conversion_gold=flow["conversion_gold"], sell_gold=flow["sell_gold"],
        sell_exp=flow["sell_exp_adjusted"], material_scarcity_exp=flow["material_exp_adjusted"], lower_stone_adjusted_exp=flow["lower_stone_adjusted_exp"],
    )


def _ci(values: list[float]) -> dict[str, Any]:
    center = mean(values)
    if len(values) < 2:
        return {"mean": center, "interval95": [center, center]}
    half = _t95(len(values)) * stdev(values) / sqrt(len(values))
    return {"mean": center, "interval95": [center - half, center + half], "seed_stddev": stdev(values)}


def _report_resume_path(resume: Path) -> str:
    resolved = resume.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def run(candidate_path: Path, source_path: Path, resume: Path, *, runs: int, workers: int) -> dict[str, Any]:
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_hash = str(candidate["candidate_sha256"])
    plus0_rule, plus3_rule = _parse_rule(candidate["rules"]["plus0"]), _parse_rule(candidate["rules"]["plus3"])
    epic_rows = load_real_plus0(ROOT / "manual_acceptance" / "real_sample_records.json", "development") + load_real_plus0(ROOT / "manual_acceptance" / "real_sample_records.json", "frozen_validation")
    epic = [Gear.from_dict(row["gear"]) for row in epic_rows]
    source = json.loads(source_path.read_text(encoding="utf-8"))
    heroic = _source_rank_gears(source, "Heroic")
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    expected: dict[str, dict[int, dict[int, str]]] = {"Epic": {}, "Heroic": {}}
    jobs: list[dict[str, Any]] = []
    for rank, gears in (("Epic", epic), ("Heroic", heroic)):
        for seed in SEEDS:
            by_index: dict[int, str] = {}
            for index, gear in enumerate(gears):
                input_hash = _gear_hash(gear, candidate_hash, runs, rank)
                by_index[index] = input_hash
                path = _path(resume, rank, seed, index)
                if _valid(path, input_hash):
                    continue
                jobs.append({"rank": rank, "seed": seed, "index": index, "gear": gear, "runs": runs, "plus0_rule": plus0_rule, "plus3_rule": plus3_rule, "input_hash": input_hash, "path": str(path)})
            expected[rank][seed] = by_index
    _run_jobs(jobs, workers)
    per_seed: dict[str, Any] = {}
    for seed in SEEDS:
        epic_sum = _sum_seed(resume, "Epic", seed, expected["Epic"][seed])
        heroic_sum = _sum_seed(resume, "Heroic", seed, expected["Heroic"][seed])
        per_seed[str(seed)] = {}
        for yield_name, multiplier in YIELD_VARIATIONS.items():
            heroic_yield = float(batch["expected_output_by_rank"]["Heroic"]) * float(multiplier)
            per_seed[str(seed)][yield_name] = {}
            for key in CANDIDATES:
                flow = _combine(epic_sum, heroic_sum, heroic_yield, key)
                pool = _pool(flow, batch)
                total = float(pool["total_stamina"])
                cycles = 100000.0 / total
                per_seed[str(seed)][yield_name][key] = {
                    "flow": flow, "pool": pool, "total_stamina": total,
                    "formal_rate_per_100": 100.0 * flow["value_sum"] / total,
                    "per_100k": {field: cycles * flow[field] for field in FLOW_WITH_METRICS},
                    "rift_stamina_per_100k": cycles * 85.0,
                    "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]),
                    "source_cycles_per_100k": cycles,
                }
    summary: dict[str, Any] = {}
    for yield_name in YIELD_VARIATIONS:
        rates = {key: [per_seed[str(seed)][yield_name][key]["formal_rate_per_100"] for seed in SEEDS] for key in CANDIDATES}
        difference = [candidate_rate - current_rate for candidate_rate, current_rate in zip(rates["exact_safe_stop"], rates["current_formal"])]
        summary[yield_name] = {"rates": {key: _ci(values) for key, values in rates.items()}, "candidate_minus_current": _ci(difference), "improves": _ci(difference)["interval95"][0] > 0}
    return {
        "study": "epic_exact_plus3_joint_pool_20260717", "schema_version": SCHEMA_VERSION,
        "scope": "conditional real normal_85 Epic non-boot non-speed +0 cohort; Heroic released M1 common component",
        "candidate_sha256": candidate_hash, "seeds": list(SEEDS), "runs_per_official_plus3_branch": runs,
        "cohort": {"epic_real_plus0_count": len(epic), "heroic_source_count": len(heroic), "warning": "Absolute per-100k values are conditional on the real non-speed Epic cohort, not an account-wide dungeon drop-rate estimate."},
        "batch": batch, "execution": {"scheduled_shards": len(jobs), "resume_dir": _report_resume_path(resume)}, "per_seed": per_seed, "summary": summary,
    }


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Epic 官方+3分支联合资源池（2026-07-17）", "",
        "本报告比较冻结的安全止损候选与当前正式策略。Epic首段使用官方离散+3分支，Heroic使用已发布M1作为共享资源池组件。", "",
        "## 限制", "",
        "- 绝对每10万体力指标条件于真实非鞋、非速度Epic +0样本，不代表账号全副本掉落总规划。", "- 两策略的差值使用同一批真实胚子、同一Heroic路径和五个共同seed。", "",
    ]
    for yield_name, row in data["summary"].items():
        lines.extend([f"## Heroic产出：{yield_name}", "", "| 策略 | 正式体系价值率/100体力 95% CI |", "|---|---:|"])
        for key in CANDIDATES:
            ci = row["rates"][key]["interval95"]
            lines.append(f"| {key} | [{ci[0]:.6f}, {ci[1]:.6f}] |")
        ci = row["candidate_minus_current"]["interval95"]
        lines.append(f"- 候选-当前成对95% CI：[{ci[0]:.6f}, {ci[1]:.6f}]。")
    first = data["per_seed"][str(SEEDS[0])]["baseline"]
    lines.extend(["", "## 每10万总体力示例（首个seed、Heroic基线产出）", "", "| 策略 | 正式体系百里分 | 原生75+ | 转换75+ | 22速 | 输出60 | 维度裂缝体力 | 圣女3-7体力 | 循环 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for key in CANDIDATES:
        row = first[key]
        metric = row["per_100k"]
        lines.append(f"| {key} | {metric['value_sum']:.3f} | {metric.get('native_heirloom', 0):.3f} | {metric.get('converted_heirloom', 0):.3f} | {metric.get('speed22', 0):.3f} | {metric.get('output60', 0):.3f} | {row['rift_stamina_per_100k']:.3f} | {row['saint_stamina_per_100k']:.3f} | {row['source_cycles_per_100k']:.3f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Five-seed joint pool replay for exact Epic +3 candidate")
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--resume-dir", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    data = run(args.candidate, args.source, args.resume_dir, runs=max(1, args.runs), workers=max(1, args.workers))
    _atomic_json(args.json_output, data)
    args.markdown_output.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"json": str(args.json_output), "report": str(args.markdown_output), "scheduled": data["execution"]["scheduled_shards"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
