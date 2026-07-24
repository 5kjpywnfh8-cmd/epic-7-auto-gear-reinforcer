"""Independent expansion and historical-accounting bridge for the R50 study.

R50 remains a read-only historical reference.  This runner creates a new
``block/seed/set/rank`` shard tree so that absolute cost uncertainty is
estimated from independent clusters instead of from five per-seed ratios.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path
from math import sqrt
from statistics import mean, stdev
from typing import Any
import json
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from src.e7_enhance.calibration import final_success_breakdown
from src.e7_enhance.enhance_simulator import reforge_gear
from src.e7_enhance.score_engine import evaluate_gear, speed_value
from tools import research_reforged_inventory_set_weights as r50
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow, _flow
from tools.research_riftslash_saint_pool import explicit_batch_resource_pool


STUDY = "reforged_inventory_set_weight_absolute_bridge_20260718"
SCHEMA_VERSION = 2
RANKS = ("Epic", "Heroic")
DEFAULT_BLOCKS = tuple(range(1, 21))
DEFAULT_SAMPLES_PER_SET = 200
DEFAULT_RESUME_ROOT = ROOT / "reports" / "reforged_inventory_set_weight_bridge_resume_20260718"
DEFAULT_OUTPUT_ROOT = ROOT / "reports"
R50_RESUME = r50.DEFAULT_RESUME
R50_REPORT = r50.DEFAULT_REPORT
PUBLISHED_EPIC_GEAR_SOURCE = "rift_new_1_32"


def _block_seed(block: int) -> int:
    return int(sha256(f"{STUDY}|block|{block}".encode("utf-8")).hexdigest()[:16], 16)


def _stage_name(samples_per_set: int) -> str:
    return f"r{samples_per_set}"


def _code_hashes() -> dict[str, str]:
    def digest(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    return {
        "bridge_research_hash": digest(Path(__file__)),
        "r50_research_hash": digest(ROOT / "tools" / "research_reforged_inventory_set_weights.py"),
        "formal_policy_hash": digest(ROOT / "src" / "e7_enhance" / "enhance_policy.py"),
        "resource_model_hash": digest(ROOT / "src" / "e7_enhance" / "resource_model.py"),
        "mapping_hash": digest(ROOT / "tools" / "research_epic_threshold_matrix_phase_b.py"),
    }


def _input_hash(*, block: int, seed: int, set_code: str, rank: str, samples_per_set: int, hashes: dict[str, str]) -> str:
    return r50._stable_hash({
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "block": block,
        "seed": seed,
        "set_code": set_code,
        "rank": rank,
        "samples_per_set": samples_per_set,
        "rules": [rule.key for rule in r50.RULES],
        **hashes,
    })


def _shard_path(resume_root: Path, samples_per_set: int, block: int, seed: int, set_code: str, rank: str) -> Path:
    return (
        resume_root / _stage_name(samples_per_set) / f"block-{block:03d}" /
        f"seed-{seed}" / set_code / rank.lower() / "flow.json"
    )


def _valid(path: Path, expected_hash: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (
        payload.get("status") == "complete"
        and payload.get("schema_version") == SCHEMA_VERSION
        and payload.get("study") == STUDY
        and payload.get("input_hash") == expected_hash
    )


def _sample_seed(block: int, seed: int, set_code: str, rank: str, index: int, channel: str) -> int:
    return int(sha256(f"{STUDY}|{block}|{seed}|{set_code}|{rank}|{index}|{channel}".encode("utf-8")).hexdigest()[:16], 16)


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _outcome_for_rule(gear: Any, path: dict[int, Any], rule: Any, formal_cache: dict[tuple[Any, ...], str], feature_cache: dict[tuple[Any, ...], dict[str, Any]]) -> dict[str, Any]:
    def early(state: Any) -> str:
        key = r50._state_key(state)
        formal = formal_cache.get(key)
        if formal is None:
            formal = r50._formal_action(state, r50.GEAR_SOURCE)
            formal_cache[key] = formal
        features = feature_cache.get(key)
        if features is None:
            features = r50.phase_b.selected_candidate_snapshot(state)
            feature_cache[key] = features
        return r50.phase_c.action(formal, state.enhance, features, rule)

    def followup(state: Any) -> bool:
        # This is the released +6/+9/+12 policy itself.  Calling the GUI
        # adviser here would rebuild an equivalent recommendation for every
        # simulated state and does not change the binary follow-up action.
        return bool(r50.formal_followup_action(state, "normal_85"))

    return r50.simulate_strategy_path(
        path,
        "normal_85",
        r50.Strategy("inventory_weight_bridge", "offline", lambda _features: "stop"),
        early_action=early,
        formal_followup=followup,
    )


def _published_baili_score(path: dict[int, Any], outcome: dict[str, Any]) -> float:
    if int(outcome["stop_checkpoint"]) != 15:
        return 0.0
    final = reforge_gear(path[15])
    evaluation = evaluate_gear(final)
    return float(final_success_breakdown(evaluation, speed_value(final), "normal_85")["baili_score"])


def _worker(job: dict[str, Any]) -> str:
    rank = str(job["rank"])
    flows = {rule.key: _empty_flow() for rule in r50.RULES} if rank == "Epic" else {}
    legacy_scores = {rule.key: 0.0 for rule in r50.RULES} if rank == "Epic" else {}
    legacy_stamina = {rule.key: 0.0 for rule in r50.RULES} if rank == "Epic" else {}
    released_heroic = _empty_flow()
    all_stop_heroic = _empty_flow()
    for index in range(int(job["samples_per_set"])):
        gear = r50._scope_gear(
            str(job["set_code"]), rank,
            _sample_seed(int(job["block"]), int(job["seed"]), str(job["set_code"]), rank, index, "gear"),
        )
        path = r50.official_path(
            gear,
            _sample_seed(int(job["block"]), int(job["seed"]), str(job["set_code"]), rank, index, "path"),
        )
        formal_cache: dict[tuple[Any, ...], str] = {}
        feature_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        if rank == "Epic":
            for rule in r50.RULES:
                outcome = _outcome_for_rule(gear, path, rule, formal_cache, feature_cache)
                flow = _flow(gear, path, outcome)
                _add(flows[rule.key], flow)
                legacy_scores[rule.key] += _published_baili_score(path, outcome)
                legacy_stamina[rule.key] += float(flow["legacy_stamina_sum"]) + float(calibration_for_rank("Epic").gear_stamina(PUBLISHED_EPIC_GEAR_SOURCE) or 0.0)
        else:
            # Heroic is a common released-M1 component, not an Epic candidate
            # threshold.  The all-stop counterfactual shares the same gear/path.
            _add(released_heroic, r50._flow_for_rule(gear, path, r50.RULES[0], formal_cache, feature_cache))
            _add(all_stop_heroic, _flow(gear, path, r50._outcome_zero(gear)))
    payload: dict[str, Any] = {
        "status": "complete",
        "schema_version": SCHEMA_VERSION,
        "study": STUDY,
        "block": int(job["block"]),
        "seed": int(job["seed"]),
        "set_code": str(job["set_code"]),
        "rank": rank,
        "samples_per_set": int(job["samples_per_set"]),
        "input_hash": str(job["input_hash"]),
    }
    if rank == "Epic":
        payload["flows"] = flows
        payload["published_legacy_baili_score"] = legacy_scores
        payload["published_legacy_total_stamina"] = legacy_stamina
    else:
        payload["released_heroic_flow"] = released_heroic
        payload["all_stop_heroic_flow"] = all_stop_heroic
    r50._atomic_json(Path(job["path"]), payload)
    return str(job["path"])


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if workers <= 1:
        for job in jobs:
            _worker(job)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(executor.map(_worker, jobs))


def _weighted_flow(rows: dict[str, dict[str, Any]], weights: dict[str, float], rank: str, key: str) -> dict[str, float]:
    result = _empty_flow()
    for set_code, weight in weights.items():
        row = rows[set_code][rank]
        if rank == "Epic":
            flow = row["flows"][key]
        elif key == "released_heroic":
            flow = row["released_heroic_flow"]
        elif key == "all_stop_heroic":
            flow = row["all_stop_heroic_flow"]
        else:
            raise ValueError(f"unsupported Heroic flow: {key}")
        _add(result, flow, float(weight) / float(row["samples_per_set"]))
    return result


def _weighted_published_legacy(rows: dict[str, dict[str, Any]], weights: dict[str, float], rule_key: str) -> dict[str, float]:
    score = 0.0
    stamina = 0.0
    for set_code, weight in weights.items():
        row = rows[set_code]["Epic"]
        scale = float(weight) / float(row["samples_per_set"])
        score += scale * float(row["published_legacy_baili_score"][rule_key])
        stamina += scale * float(row["published_legacy_total_stamina"][rule_key])
    return {"numerator_formal_baili": score, "denominator_total_stamina": stamina}


def _pool(flow: dict[str, float]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(r50.GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
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


def _flow_sum(left: dict[str, float], right: dict[str, float], factor: float = 1.0) -> dict[str, float]:
    result = dict(left)
    _add(result, right, factor)
    return result


def _ledger(flow: dict[str, float], *, source_mode: str, numerator: float | None = None, denominator: float | None = None) -> dict[str, Any]:
    if source_mode == "legacy_epic_only":
        return {
            "numerator_formal_baili": float(flow["value_sum"] if numerator is None else numerator),
            "denominator_total_stamina": float(flow["legacy_stamina_sum"] if denominator is None else denominator),
            "rift_stamina": 0.0,
            "saint_stamina": float(flow["legacy_stamina_sum"] if denominator is None else denominator),
            "resource_boundary": "published_incremental_epic_replay",
        }
    pool = _pool(flow)
    return {
        "numerator_formal_baili": float(flow["value_sum"] if numerator is None else numerator),
        "denominator_total_stamina": float(pool["total_stamina"]),
        "rift_stamina": 85.0,
        "saint_stamina": float(pool["saint_supplement_stamina"]),
        "resource_boundary": source_mode,
        "pool": pool,
    }


LAYER_ORDER = (
    "published_epic_replay",
    "epic_inventory_weighted",
    "joint_source_epic_value_only",
    "joint_source_all_stop_heroic",
    "joint_source_released_heroic",
)
TERMINAL_VALUE_DIAGNOSTIC = "modern_terminal_value_on_published_resource"


def bridge_layers(rows: dict[str, dict[str, Any]], weights: dict[str, float], rule_key: str) -> dict[str, dict[str, Any]]:
    """Build the five task-defined ledgers from one cluster's shared paths."""
    uniform = {set_code: 1.0 / len(rows) for set_code in rows}
    epic_uniform = _weighted_flow(rows, uniform, "Epic", rule_key)
    epic_weighted = _weighted_flow(rows, weights, "Epic", rule_key)
    legacy_uniform = _weighted_published_legacy(rows, uniform, rule_key)
    legacy_weighted = _weighted_published_legacy(rows, weights, rule_key)
    heroic_stop = _weighted_flow(rows, weights, "Heroic", "all_stop_heroic")
    heroic_released = _weighted_flow(rows, weights, "Heroic", "released_heroic")
    heroic_yield = float(joint_source_batch_metadata(r50.GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))["expected_output_by_rank"]["Heroic"])
    return {
        "published_epic_replay": _ledger(
            epic_uniform,
            source_mode="legacy_epic_only",
            numerator=legacy_uniform["numerator_formal_baili"],
            denominator=legacy_uniform["denominator_total_stamina"],
        ),
        "epic_inventory_weighted": _ledger(
            epic_weighted,
            source_mode="legacy_epic_only",
            numerator=legacy_weighted["numerator_formal_baili"],
            denominator=legacy_weighted["denominator_total_stamina"],
        ),
        TERMINAL_VALUE_DIAGNOSTIC: _ledger(
            epic_weighted,
            source_mode="legacy_epic_only",
            numerator=float(epic_weighted["value_sum"]),
            denominator=legacy_weighted["denominator_total_stamina"],
        ),
        "joint_source_epic_value_only": _ledger(epic_weighted, source_mode="joint_source_epic_value_only"),
        "joint_source_all_stop_heroic": _ledger(_flow_sum(epic_weighted, heroic_stop, heroic_yield), source_mode="joint_source_all_stop_heroic"),
        "joint_source_released_heroic": _ledger(_flow_sum(epic_weighted, heroic_released, heroic_yield), source_mode="joint_source_released_heroic"),
    }


def positive_cluster_ratio(clusters: list[dict[str, Any]], *, bootstrap_seed: int = 20260718, draws: int = 4000) -> dict[str, Any]:
    """Ratio of sums with a seed/block clustered, non-negative bootstrap CI."""
    usable = [row for row in clusters if row["numerator_formal_baili"] > 0 and row["denominator_total_stamina"] >= 0]
    numerator = sum(float(row["numerator_formal_baili"]) for row in usable)
    denominator = sum(float(row["denominator_total_stamina"]) for row in usable)
    if not usable or numerator <= 0 or denominator < 0:
        return {"mean": None, "interval95": None, "relative_half_width": None, "cluster_count": len(usable), "ess": 0.0, "max_cluster_share": None, "method": "clustered_positive_bootstrap", "status": "no_positive_baili"}
    rng = random.Random(bootstrap_seed)
    ratios = []
    for _ in range(draws):
        sampled = [usable[rng.randrange(len(usable))] for _ in usable]
        sampled_numerator = sum(float(row["numerator_formal_baili"]) for row in sampled)
        sampled_denominator = sum(float(row["denominator_total_stamina"]) for row in sampled)
        if sampled_numerator > 0 and sampled_denominator >= 0:
            ratios.append(sampled_denominator / sampled_numerator)
    ratios.sort()
    lower = max(0.0, ratios[int(0.025 * (len(ratios) - 1))])
    upper = ratios[int(0.975 * (len(ratios) - 1))]
    values = [float(row["numerator_formal_baili"]) for row in usable]
    ess = numerator * numerator / sum(value * value for value in values)
    estimate = denominator / numerator
    return {
        "mean": estimate,
        "interval95": [lower, upper],
        "relative_half_width": (upper - lower) / (2.0 * estimate) if estimate else None,
        "cluster_count": len(usable),
        "ess": ess,
        "max_cluster_share": max(values) / numerator,
        "method": "clustered_positive_bootstrap",
        "status": "ok",
    }


def _aggregate_layer(clusters: list[dict[str, Any]]) -> dict[str, Any]:
    ratio = positive_cluster_ratio(clusters)
    if ratio["mean"] is None:
        return {**ratio, "formal_baili_per_100k": None, "rift_stamina_per_100k": None, "saint_stamina_per_100k": None, "cycles_per_100k": None, "absolute_cost_unstable": True}
    numerator = sum(float(row["numerator_formal_baili"]) for row in clusters)
    denominator = sum(float(row["denominator_total_stamina"]) for row in clusters)
    rift = sum(float(row["rift_stamina"]) for row in clusters)
    saint = sum(float(row["saint_stamina"]) for row in clusters)
    cycles = 100000.0 / denominator
    return {
        **ratio,
        "formal_baili_per_100k": 100000.0 * numerator / denominator,
        "rift_stamina_per_100k": cycles * rift,
        "saint_stamina_per_100k": cycles * saint,
        "cycles_per_100k": cycles * len(clusters),
        "absolute_cost_unstable": bool(ratio["relative_half_width"] is None or ratio["relative_half_width"] > 0.10),
    }


def _paired_rate_delta(values: list[float], baseline: list[float]) -> dict[str, Any]:
    deltas = [value - reference for value, reference in zip(values, baseline)]
    center = mean(deltas)
    half = r50._t95(len(deltas)) * stdev(deltas) / sqrt(len(deltas)) if len(deltas) > 1 else 0.0
    return {
        "mean": center,
        "interval95": [center - half, center + half],
        "unit": "formal_baili_per_100_total_stamina",
        "cluster_count": len(deltas),
        "method": "paired_common_path_t95",
    }


def _r50_reference() -> dict[str, Any]:
    return {
        "resume": str(R50_RESUME),
        "report": str(R50_REPORT),
        "read_only": True,
        "exists": R50_RESUME.exists() and R50_REPORT.exists(),
        "note": "R50 shards and report are retained as historical reference and are never written by this runner.",
    }


def run(*, resume_root: Path, samples_per_set: int, blocks: tuple[int, ...], workers: int, selected_blocks: set[int] | None = None, selected_sets: set[str] | None = None) -> dict[str, Any]:
    if resume_root.resolve() == R50_RESUME.resolve():
        raise ValueError("bridge runner must not write into the R50 resume directory")
    if samples_per_set < 1 or not blocks or len(blocks) != len(set(blocks)):
        raise ValueError("samples_per_set must be positive and blocks must be unique")
    weights = r50.derive_weights()
    hashes = _code_hashes()
    jobs = []
    rows: dict[int, dict[str, dict[str, dict[str, Any]]]] = {block: {set_code: {rank: {} for rank in RANKS} for set_code in weights["observed_sets"]} for block in blocks}
    for block in blocks:
        seed = _block_seed(block)
        for set_code in weights["observed_sets"]:
            for rank in RANKS:
                expected = _input_hash(block=block, seed=seed, set_code=set_code, rank=rank, samples_per_set=samples_per_set, hashes=hashes)
                path = _shard_path(resume_root, samples_per_set, block, seed, set_code, rank)
                if not _valid(path, expected) and (selected_blocks is None or block in selected_blocks) and (selected_sets is None or set_code in selected_sets):
                    jobs.append({"block": block, "seed": seed, "set_code": set_code, "rank": rank, "samples_per_set": samples_per_set, "input_hash": expected, "path": str(path)})
    _run_jobs(jobs, workers)
    missing = []
    for block in blocks:
        seed = _block_seed(block)
        for set_code in weights["observed_sets"]:
            for rank in RANKS:
                expected = _input_hash(block=block, seed=seed, set_code=set_code, rank=rank, samples_per_set=samples_per_set, hashes=hashes)
                path = _shard_path(resume_root, samples_per_set, block, seed, set_code, rank)
                if not _valid(path, expected):
                    missing.append(str(path))
                else:
                    rows[block][set_code][rank] = json.loads(path.read_text(encoding="utf-8"))
    execution = {"expected_shards": len(blocks) * len(weights["observed_sets"]) * len(RANKS), "scheduled_shards": len(jobs), "missing_shards": len(missing), "resume": str(resume_root), "stage": _stage_name(samples_per_set)}
    if missing:
        return {"study": STUDY, "schema_version": SCHEMA_VERSION, "complete": False, "execution": execution, "r50_reference": _r50_reference(), "weights": weights}

    scenarios: dict[str, Any] = {}
    for scenario_name, scenario_weights in weights["scenarios"].items():
        scenario: dict[str, Any] = {"rules": {}}
        full_joint_rates: dict[str, list[float]] = {}
        for rule in r50.RULES:
            clusters_by_layer = {layer: [] for layer in (*LAYER_ORDER, TERMINAL_VALUE_DIAGNOSTIC)}
            for block in blocks:
                cluster = bridge_layers(rows[block], scenario_weights, rule.key)
                for layer in clusters_by_layer:
                    clusters_by_layer[layer].append({"block": block, "seed": _block_seed(block), **cluster[layer]})
            summary = {layer: _aggregate_layer(values) for layer, values in clusters_by_layer.items()}
            previous = None
            deltas = {}
            for layer in LAYER_ORDER:
                current = summary[layer]["mean"]
                deltas[layer] = None if previous is None or current is None else current - previous
                previous = current
            full_joint_rates[rule.key] = [
                100.0 * float(row["numerator_formal_baili"]) / float(row["denominator_total_stamina"])
                for row in clusters_by_layer["joint_source_released_heroic"]
            ]
            scenario["rules"][rule.key] = {
                "layers": {layer: summary[layer] for layer in LAYER_ORDER},
                "terminal_value_diagnostic": summary[TERMINAL_VALUE_DIAGNOSTIC],
                "layer_delta_stamina_per_baili": deltas,
            }
        baseline_rates = full_joint_rates["current_formal"]
        for rule in r50.RULES:
            scenario["rules"][rule.key]["paired_full_joint_delta_vs_current"] = (
                {"mean": 0.0, "interval95": [0.0, 0.0], "unit": "formal_baili_per_100_total_stamina", "cluster_count": len(baseline_rates), "method": "paired_common_path_t95"}
                if rule.key == "current_formal"
                else _paired_rate_delta(full_joint_rates[rule.key], baseline_rates)
            )
        scenarios[scenario_name] = scenario

    uniform_current = scenarios["uniform_observed_sets"]["rules"]["current_formal"]["layers"]
    inventory_current = scenarios["reforged_inventory_all"]["rules"]["current_formal"]["layers"]
    bridge_status = "historical_constant_not_reproduced" if uniform_current["published_epic_replay"]["mean"] is None or abs(float(uniform_current["published_epic_replay"]["mean"]) - 799.2) > 0.05 * 799.2 else "historical_constant_reproduced"
    return {
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "execution": execution,
        "hashes": hashes,
        "samples_per_set": samples_per_set,
        "blocks": list(blocks),
        "rules": [rule.key for rule in r50.RULES],
        "weights": weights,
        "r50_reference": _r50_reference(),
        "scenarios": scenarios,
        "bridge_status": bridge_status,
        "main_comparison": {
            "published_epic_replay": uniform_current["published_epic_replay"],
            "epic_inventory_weighted": inventory_current["epic_inventory_weighted"],
            TERMINAL_VALUE_DIAGNOSTIC: scenarios["reforged_inventory_all"]["rules"]["current_formal"]["terminal_value_diagnostic"],
            "joint_source_epic_value_only": inventory_current["joint_source_epic_value_only"],
            "joint_source_all_stop_heroic": inventory_current["joint_source_all_stop_heroic"],
            "joint_source_released_heroic": inventory_current["joint_source_released_heroic"],
        },
        "freeze": "not_frozen_no_holdout",
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "not estimated"
    if isinstance(value, list):
        return f"[{value[0]:.{digits}f}, {value[1]:.{digits}f}]"
    return f"{float(value):.{digits}f}"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# 已重铸库存套装权重绝对成本扩样与旧口径桥接",
        "",
        "本报告将旧 `799.2` Epic-only 常量和当前 `85 体力 Epic/Heroic 联合线路`逐层拆开。套装权重只代表库存保留需求，不代表自然掉率；R50 分片与报告保持只读。",
        "",
        "## 执行状态",
        "",
        f"- 新阶段：`{data['execution']['stage']}`；完成分片：`{data['execution']['expected_shards'] - data['execution']['missing_shards']}/{data['execution']['expected_shards']}`。",
        f"- 旧 799.2 桥接状态：`{data['bridge_status']}`。",
        "- 绝对成本区间为按独立 seed/block 聚类的正值约束 bootstrap；下界不会为负。",
        "",
        "## 五层桥接（当前正式策略）",
        "",
        "| 层级 | 口径 | 体力/百里分 95%区间 | 正式百里分/10万体力 | 裂缝/圣女体力 | cluster ESS | 最大cluster贡献 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "published_epic_replay": "发布 Epic-only 回放（19套等权）",
        "epic_inventory_weighted": "仅换库存需求权重",
        "joint_source_epic_value_only": "加入85体力来源，仅计Epic价值",
        "joint_source_all_stop_heroic": "加入Heroic成本/回收，Heroic全停",
        "joint_source_released_heroic": "完整联合线路，Heroic已发布M1",
    }
    main = data["main_comparison"]
    for layer in LAYER_ORDER:
        row = main[layer]
        lines.append(
            f"| `{layer}` | {labels[layer]} | {_fmt(row['mean'])} {_fmt(row['interval95'])} | {_fmt(row['formal_baili_per_100k'])} | {_fmt(row['rift_stamina_per_100k'])}/{_fmt(row['saint_stamina_per_100k'])} | {_fmt(row['ess'])} | {_fmt(row['max_cluster_share'], 3)} |"
        )
    diagnostic = main[TERMINAL_VALUE_DIAGNOSTIC]
    lines.extend([
        "",
        "### Terminal Value Definition Diagnostic",
        "",
        f"Inventory-weighted historical terminal-score numerator: `{_fmt(main['epic_inventory_weighted']['mean'])}` stamina/Baili.  With the same historical resource denominator but the current formal-value numerator: `{_fmt(diagnostic['mean'])}` stamina/Baili (95% {_fmt(diagnostic['interval95'])}).",
    ])
    lines.extend([
        "",
        "桥接解释顺序：第一、二层的差异只来自套装需求权重；第二、三层的差异来自把装备获得与圣女补充纳入分母；第三、四、五层的差异来自 Heroic 的联合产出及其全停或 M1 强化流。五层均使用同一批 Epic/Heroic 条件生成路径，22速不折算进正式百里分。",
        "",
        "## 候选对照（完整联合线路）",
        "",
        "| 套装需求场景 | 策略 | 体力/百里分 95%区间 | 百里分/10万体力 | 稳定状态 |",
        "|---|---|---:|---:|---|",
    ])
    for scenario_name in ("uniform_observed_sets", "reforged_inventory_all"):
        for rule in r50.RULES:
            result = data["scenarios"][scenario_name]["rules"][rule.key]
            row = result["layers"]["joint_source_released_heroic"]
            paired = result["paired_full_joint_delta_vs_current"]
            status = "absolute_cost_unstable" if row["absolute_cost_unstable"] else "absolute_cost_stable"
            lines.append(f"| `{scenario_name}` | `{rule.key}` | {_fmt(row['mean'])} {_fmt(row['interval95'])} | {_fmt(row['formal_baili_per_100k'])} | paired delta/100={_fmt(paired['mean'], 6)} {_fmt(paired['interval95'], 6)}; `{status}` |")
    lines.extend([
        "",
        "## 结论状态",
        "",
        "- 本轮不冻结候选、不启动或读取 128 件 holdout，也未修改正式策略、DP、资源模型、评分、跳值表、GUI、OCR 或自动化。",
        "- 只有完整联合线路的绝对成本相对半宽不超过 10% 时，才允许把该结果作为可发布常量讨论；候选的成对差异仍须单独按共同随机路径解释。",
    ])
    return "\n".join(lines) + "\n"


def _parse_blocks(text: str) -> tuple[int, ...]:
    values: list[int] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start, end = (int(value) for value in item.split("-", 1))
            values.extend(range(start, end + 1))
        else:
            values.append(int(item))
    return tuple(values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand R50 with independent seed/block clusters and bridge old accounting")
    parser.add_argument("--resume-root", type=Path, default=DEFAULT_RESUME_ROOT)
    parser.add_argument("--samples-per-set", type=int, default=DEFAULT_SAMPLES_PER_SET)
    parser.add_argument("--blocks", default="1-20")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--selected-blocks")
    parser.add_argument("--sets")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    blocks = _parse_blocks(args.blocks)
    selected_blocks = set(_parse_blocks(args.selected_blocks)) if args.selected_blocks else None
    selected_sets = {value.strip() for value in args.sets.split(",") if value.strip()} if args.sets else None
    data = run(resume_root=args.resume_root, samples_per_set=args.samples_per_set, blocks=blocks, workers=max(1, args.workers), selected_blocks=selected_blocks, selected_sets=selected_sets)
    if not data["complete"]:
        print(json.dumps({"complete": False, "execution": data["execution"]}, ensure_ascii=False))
        return
    stem = f"reforged_inventory_set_weight_bridge_{_stage_name(args.samples_per_set)}_20260718"
    json_output = args.json_output or DEFAULT_OUTPUT_ROOT / f"{stem}.json"
    report_output = args.report_output or DEFAULT_OUTPUT_ROOT / f"{stem}.md"
    r50._atomic_json(json_output, data)
    report_output.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"complete": True, "json": str(json_output), "report": str(report_output), "execution": data["execution"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
