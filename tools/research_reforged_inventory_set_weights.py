"""Offline inventory-demand weighting study for Epic non-speed early rules.

The external Fribbels export is read only to derive a set-code histogram.  It
never supplies simulated substats, drop rates, or production policy inputs.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from hashlib import sha256
from math import sqrt
from pathlib import Path
from statistics import mean, stdev
from typing import Any
import json
import os
import random
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.models import Gear, RollHit, Stat, round1
from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools import research_epic_threshold_matrix_phase_c as phase_c
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow, _flow
from tools.epic_non_speed_early_policy_pareto import (
    GEAR_SOURCE,
    Strategy,
    conditional_gear_record,
    formal_followup_action,
    generate_conditional_gear,
    simulate_strategy_path,
    summarize_incremental_cost,
)
from tools.epic_plus3_exact_branches import official_plus3_distribution
from tools.research_epic_exact_plus3 import _formal_action
from tools.research_riftslash_saint_pool import _t95, explicit_batch_resource_pool


STUDY = "reforged_inventory_set_weight_baili_efficiency_20260718"
SCHEMA_VERSION = 1
SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
EXTERNAL_SOURCE = Path(r"D:\VScode\E7-tools\gear_data\0橙U子0\json\gear_fribbels_20260610_182000.json")
EXPECTED_SOURCE_SHA256 = "2BB32F384FBE3D926F5274D50AB24DC8766C2AF87AA1ABC0B6946A47EEAE1DB7"
EXPECTED_COUNTS = {
    "set_speed": 235, "set_cri_dmg": 98, "set_immune": 63, "set_max_hp": 63,
    "set_torrent": 50, "set_counter": 42, "set_penetrate": 34, "set_chase": 27,
    "set_acc": 26, "set_cri": 25, "set_opener": 22, "set_shield": 22,
    "set_res": 17, "set_riposte": 12, "set_rage": 8, "set_revenant": 8,
    "set_def": 6, "set_vampire": 6, "set_att": 1,
}
TOP4 = ("set_speed", "set_cri_dmg", "set_immune", "set_max_hp")
RANKS = ("Epic", "Heroic")
DEFAULT_RESUME = ROOT / "reports" / "reforged_inventory_set_weight_resume_20260718"
DEFAULT_WEIGHTS = ROOT / "reports" / "reforged_inventory_set_weights_20260718.json"
DEFAULT_JSON = ROOT / "reports" / "reforged_inventory_set_weight_efficiency_20260718.json"
DEFAULT_REPORT = ROOT / "reports" / "reforged_inventory_set_weight_efficiency_20260718.md"

RULES = tuple(rule for rule in phase_c.RULES if rule.key in {
    "current_formal", "global_12_17", "output_8_13_tank_10_17", "output_8_13_tank_12_17",
})


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_sha256(path: Path = EXTERNAL_SOURCE) -> str:
    return sha256(path.read_bytes()).hexdigest().upper()


def _item_rank(item: dict[str, Any], raw: dict[str, Any]) -> str | None:
    value = item.get("rank") or item.get("grade") or raw.get("rank") or raw.get("grade")
    text = str(value or "").strip().lower()
    if text in {"epic", "5", "5.0"}:
        return "Epic"
    if text in {"heroic", "4", "4.0"}:
        return "Heroic"
    return None


def derive_weights(path: Path = EXTERNAL_SOURCE) -> dict[str, Any]:
    actual_hash = source_sha256(path)
    if actual_hash != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(f"external Fribbels source hash changed: {actual_hash}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = {"all": {}, "Epic": {}, "Heroic": {}}
    total_by_rank = {"Epic": 0, "Heroic": 0}
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
        level = item.get("level", raw.get("level"))
        enhance = item.get("enhance", raw.get("enhance"))
        if int(level or -1) != 90 or int(enhance or -1) != 15:
            continue
        set_code = raw.get("f")
        rank = _item_rank(item, raw)
        if not isinstance(set_code, str) or rank not in RANKS:
            continue
        counts["all"][set_code] = counts["all"].get(set_code, 0) + 1
        counts[rank][set_code] = counts[rank].get(set_code, 0) + 1
        total_by_rank[rank] += 1
    if counts["all"] != EXPECTED_COUNTS or total_by_rank != {"Epic": 616, "Heroic": 149}:
        raise RuntimeError("external Fribbels derived count differs from the frozen task inventory")
    observed = tuple(sorted(counts["all"]))
    def normalized(values: dict[str, int]) -> dict[str, float]:
        total = sum(values.values())
        return {code: value / total for code, value in sorted(values.items())} if total else {}
    scenarios = {
        "uniform_observed_sets": {code: 1.0 / len(observed) for code in observed},
        "reforged_inventory_all": normalized(counts["all"]),
        "reforged_inventory_epic": normalized(counts["Epic"]),
        "reforged_inventory_heroic": normalized(counts["Heroic"]),
        "top4_equal": {code: 0.25 for code in TOP4},
    }
    return {
        "source_path": str(path), "source_sha256": actual_hash, "filter": {"level": 90, "enhance": 15, "set_field": "items[*].raw.f"},
        "counts": counts, "rank_totals": total_by_rank, "observed_sets": list(observed), "scenarios": scenarios,
        "semantics": "post-selection inventory demand weights only; not natural set drop rates",
    }


def _distribution(rank: str, stat_key: str) -> tuple[tuple[int, float], ...]:
    if rank == "Heroic" and stat_key == "spd":
        raw = ((1, 0.00332), (2, 0.33223), (3, 0.33223), (4, 0.33223))
        total = sum(probability for _value, probability in raw)
        return tuple((value, probability / total) for value, probability in raw)
    return official_plus3_distribution(stat_key)


def _draw_roll(rng: random.Random, rank: str, stat_key: str) -> int:
    point = rng.random()
    cumulative = 0.0
    distribution = _distribution(rank, stat_key)
    for value, probability in distribution:
        cumulative += probability
        if point <= cumulative:
            return value
    return distribution[-1][0]


def _scope_gear(set_code: str, rank: str, seed: int) -> Gear:
    rng = random.Random(seed)
    for _attempt in range(10000):
        slot = rng.choice(("weapon", "helm", "armor", "neck", "ring"))
        gear = generate_conditional_gear(set_code, rank, rng.randrange(2**63), slot=slot)
        if all(stat.key != "spd" for stat in gear.substats):
            return gear
    raise RuntimeError("could not generate a non-speed non-boot conditional gear")


def _new_official_substat(rng: random.Random, gear: Gear) -> Stat:
    from src.e7_enhance.enhance_simulator import STAT_POOL, STAT_TYPE_BY_KEY, slot_forbidden_substats
    blocked = {gear.main_stat.key, *(stat.key for stat in gear.substats), *slot_forbidden_substats(gear.slot)}
    choices = [key for key in STAT_POOL if key not in blocked]
    if not choices:
        raise RuntimeError("no legal +12 fourth substat")
    key = rng.choice(choices)
    return Stat(STAT_TYPE_BY_KEY[key], _draw_roll(rng, gear.rank, key), rolls=1)


def official_path(gear: Gear, seed: int) -> dict[int, Gear]:
    """Sample one legal path with STOVE discrete reinforcement values."""
    rng = random.Random(seed)
    current = gear
    path = {0: current}
    for checkpoint in (3, 6, 9, 12, 15):
        if checkpoint == 12 and len(current.substats) < 4:
            current = Gear(
                set=current.set, slot=current.slot, main_stat=current.main_stat, enhance=12, level=current.level,
                rank=current.rank, substats=current.substats + [_new_official_substat(rng, current)],
                roll_history=list(current.roll_history), code=current.code, reforge_eligible=current.reforge_eligible,
                roll_level=current.roll_level,
            )
        else:
            index = rng.randrange(len(current.substats))
            hit = current.substats[index]
            delta = _draw_roll(rng, current.rank, hit.key)
            updated = Stat(hit.type, round1(hit.normalized_value + delta), rolls=hit.rolls + 1, modified=hit.modified)
            substats = list(current.substats)
            substats[index] = updated
            current = Gear(
                set=current.set, slot=current.slot, main_stat=current.main_stat, enhance=checkpoint, level=current.level,
                rank=current.rank, substats=substats,
                roll_history=list(current.roll_history) + [RollHit(checkpoint, updated.type, delta)], code=current.code,
                reforge_eligible=current.reforge_eligible, roll_level=current.roll_level,
            )
        path[checkpoint] = current
    return path


def _outcome_zero(gear: Gear) -> dict[str, Any]:
    costs = summarize_incremental_cost(gear.slot, gear.rank, 0, 0)
    return {"start_checkpoint": 0, "stop_checkpoint": 0, "net_stamina": costs["net_stamina"], "net_gold": costs["net_gold"], "costs": costs}


def _state_key(state: Gear) -> tuple[Any, ...]:
    return (state.enhance, state.slot, state.main_stat.key, tuple((stat.key, stat.normalized_value, stat.rolls) for stat in state.substats))


def _flow_for_rule(gear: Gear, path: dict[int, Gear], rule: phase_c.Rule, formal_cache: dict[tuple[Any, ...], str], feature_cache: dict[tuple[Any, ...], dict[str, Any]]) -> dict[str, float]:
    def early(state: Gear) -> str:
        key = _state_key(state)
        formal = formal_cache.get(key)
        if formal is None:
            formal = _formal_action(state, GEAR_SOURCE)
            formal_cache[key] = formal
        features = feature_cache.get(key)
        if features is None:
            features = phase_b.selected_candidate_snapshot(state)
            feature_cache[key] = features
        return phase_c.action(formal, state.enhance, features, rule)

    def followup(state: Gear) -> bool:
        key = _state_key(state)
        formal = formal_cache.get(key)
        if formal is None:
            formal = _formal_action(state, GEAR_SOURCE)
            formal_cache[key] = formal
        return formal != "stop"

    outcome = simulate_strategy_path(
        path,
        "normal_85",
        Strategy("inventory_weight", "offline", lambda _features: "stop"),
        early_action=early,
        # Reuse the released GUI-facing formal decision at every later node.
        # ``formal_followup_action`` assumes an offline base-policy registry
        # that is not available for the released baili_marginal_low policy.
        formal_followup=followup,
    )
    return _flow(gear, path, outcome)


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _empty_by_rule() -> dict[str, dict[str, float]]:
    return {rule.key: _empty_flow() for rule in RULES}


def _sample_seed(set_code: str, rank: str, seed: int, index: int, channel: str) -> int:
    return int(sha256(f"{STUDY}|{set_code}|{rank}|{seed}|{index}|{channel}".encode("utf-8")).hexdigest()[:16], 16)


def _worker(job: dict[str, Any]) -> str:
    flows = _empty_by_rule()
    groups = {rule.key: {} for rule in RULES}
    formal_events = {rule.key: 0 for rule in RULES}
    for index in range(int(job["samples_per_set"])):
        gear = _scope_gear(job["set_code"], job["rank"], _sample_seed(job["set_code"], job["rank"], job["seed"], index, "gear"))
        path = official_path(gear, _sample_seed(job["set_code"], job["rank"], job["seed"], index, "path"))
        group = str(phase_b.selected_candidate_snapshot(gear)["system_group"])
        formal_cache: dict[tuple[Any, ...], str] = {}
        feature_cache: dict[tuple[Any, ...], dict[str, Any]] = {}
        for rule in RULES:
            flow = _flow_for_rule(gear, path, rule, formal_cache, feature_cache)
            _add(flows[rule.key], flow)
            group_flow = groups[rule.key].setdefault(group, _empty_flow())
            _add(group_flow, flow)
            formal_events[rule.key] += int(flow["value_sum"] > 0.0)
    payload = {
        "status": "complete", "schema_version": SCHEMA_VERSION, "study": STUDY,
        "set_code": job["set_code"], "rank": job["rank"], "seed": job["seed"],
        "samples_per_set": job["samples_per_set"], "input_hash": job["input_hash"],
        "flows": flows, "system_flows": groups, "formal_value_nonzero_events": formal_events,
    }
    _atomic_json(Path(job["path"]), payload)
    return str(job["path"])


def _shard_path(resume: Path, set_code: str, rank: str, seed: int) -> Path:
    return resume / set_code / rank.lower() / f"seed-{seed}.json"


def _code_hashes() -> dict[str, str]:
    def digest(path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()
    return {
        "research_hash": digest(Path(__file__)),
        "official_roll_hash": digest(ROOT / "tools" / "epic_plus3_exact_branches.py"),
        "formal_policy_hash": digest(ROOT / "src" / "e7_enhance" / "enhance_policy.py"),
        "resource_model_hash": digest(ROOT / "src" / "e7_enhance" / "resource_model.py"),
        "mapping_hash": digest(ROOT / "tools" / "research_epic_threshold_matrix_phase_b.py"),
    }


def _input_hash(set_code: str, rank: str, seed: int, samples: int, hashes: dict[str, str]) -> str:
    return _stable_hash({"study": STUDY, "schema_version": SCHEMA_VERSION, "set_code": set_code, "rank": rank, "seed": seed, "samples_per_set": samples, "rules": [asdict(rule) for rule in RULES], **hashes})


def _valid(path: Path, expected: str) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return payload.get("status") == "complete" and payload.get("schema_version") == SCHEMA_VERSION and payload.get("input_hash") == expected


def _run_jobs(jobs: list[dict[str, Any]], workers: int) -> None:
    if workers <= 1:
        for job in jobs:
            _worker(job)
        return
    with ProcessPoolExecutor(max_workers=workers) as executor:
        list(executor.map(_worker, jobs))


def _weighted(flow_rows: dict[str, dict[str, Any]], weights: dict[str, float], rank: str, rule_key: str) -> tuple[dict[str, float], dict[str, Any]]:
    total = _empty_flow()
    system = {}
    detail = {}
    for set_code, weight in weights.items():
        row = flow_rows[set_code][rank]
        mean_flow = {field: mean(row[str(seed)]["flows"][rule_key][field] for seed in SEEDS) / row[str(SEEDS[0])]["samples_per_set"] for field in FLOW_WITH_METRICS}
        _add(total, mean_flow, weight)
        detail[set_code] = {"weight": weight, "value_sum": weight * mean_flow["value_sum"], "resource_inputs": {field: weight * mean_flow[field] for field in ("powder_units", "lower_stone_units", "material_gold", "conversion_gold", "sell_gold", "material_exp_adjusted")}}
        for group, group_flow in row[str(SEEDS[0])]["system_flows"][rule_key].items():
            target = system.setdefault(group, _empty_flow())
            for field in FLOW_WITH_METRICS:
                values = [row[str(seed)]["system_flows"][rule_key].get(group, _empty_flow())[field] / row[str(seed)]["samples_per_set"] for seed in SEEDS]
                target[field] += weight * mean(values)
    return total, {"by_set": detail, "by_system": system}


def _pool(flow: dict[str, float]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    return explicit_batch_resource_pool(
        source_gold=float(batch["expected_source_gold_per_batch"]), source_lower_stones=float(batch["expected_lower_stone_units"]),
        powder_base_exp=float(flow["powder_units"]) * 100.0, lower_stone_units=float(flow["lower_stone_units"]),
        material_gold=float(flow["material_gold"]), conversion_gold=float(flow["conversion_gold"]), sell_gold=float(flow["sell_gold"]),
        sell_exp=float(flow["sell_exp_adjusted"]), material_scarcity_exp=float(flow["material_exp_adjusted"]), lower_stone_adjusted_exp=float(flow["lower_stone_adjusted_exp"]),
    )


def _ci(values: list[float]) -> dict[str, Any]:
    middle = mean(values)
    half = _t95(len(values)) * stdev(values) / sqrt(len(values)) if len(values) > 1 else 0.0
    return {"mean": middle, "interval95": [middle - half, middle + half], "relative_half_width": half / abs(middle) if middle else None}


def _seed_production(flow_by_rank: dict[str, dict[str, float]]) -> dict[str, Any]:
    batch = joint_source_batch_metadata(GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
    heroic_yield = float(batch["expected_output_by_rank"]["Heroic"])
    merged = {field: flow_by_rank["Epic"][field] + heroic_yield * flow_by_rank["Heroic"][field] for field in FLOW_WITH_METRICS}
    pool = _pool(merged)
    total = float(pool["total_stamina"])
    baili = merged["value_sum"]
    cycles = 100000.0 / total
    return {
        "flow_per_batch": merged, "pool": pool, "total_stamina_per_batch": total,
        "stamina_per_baili": total / baili if baili else None,
        "formal_baili_per_100k": cycles * baili,
        "per_100k": {field: cycles * merged[field] for field in ("native_heirloom", "converted_heirloom", "speed22", "output60")},
        "rift_stamina_per_100k": cycles * 85.0,
        "saint_stamina_per_100k": cycles * float(pool["saint_supplement_stamina"]),
        "cycles_per_100k": cycles,
        "by_rank_flow_per_batch": {"Epic": flow_by_rank["Epic"], "Heroic": {field: heroic_yield * flow_by_rank["Heroic"][field] for field in FLOW_WITH_METRICS}},
    }


def run(*, resume: Path, samples_per_set: int, workers: int, selected_sets: set[str] | None = None, selected_seeds: set[int] | None = None) -> dict[str, Any]:
    weights = derive_weights()
    _atomic_json(DEFAULT_WEIGHTS, weights)
    hashes = _code_hashes()
    jobs = []
    reused = 0
    rows: dict[str, dict[str, dict[str, Any]]] = {set_code: {rank: {} for rank in RANKS} for set_code in weights["observed_sets"]}
    for set_code in weights["observed_sets"]:
        for rank in RANKS:
            for seed in SEEDS:
                expected = _input_hash(set_code, rank, seed, samples_per_set, hashes)
                path = _shard_path(resume, set_code, rank, seed)
                if _valid(path, expected):
                    reused += 1
                else:
                    jobs.append({"set_code": set_code, "rank": rank, "seed": seed, "samples_per_set": samples_per_set, "input_hash": expected, "path": str(path)})
    filtered = [job for job in jobs if (selected_sets is None or job["set_code"] in selected_sets) and (selected_seeds is None or job["seed"] in selected_seeds)]
    _run_jobs(filtered, workers)
    missing = []
    for set_code in weights["observed_sets"]:
        for rank in RANKS:
            for seed in SEEDS:
                expected = _input_hash(set_code, rank, seed, samples_per_set, hashes)
                path = _shard_path(resume, set_code, rank, seed)
                if not _valid(path, expected):
                    missing.append(str(path))
                    continue
                rows[set_code][rank][str(seed)] = json.loads(path.read_text(encoding="utf-8"))
    execution = {"expected_shards": len(weights["observed_sets"]) * len(RANKS) * len(SEEDS), "existing_complete_shards": reused, "scheduled_shards": len(filtered), "missing_shards": len(missing), "resume": str(resume)}
    if missing:
        return {"study": STUDY, "complete": False, "execution": execution, "weights": weights}

    scenarios: dict[str, Any] = {}
    for scenario_name, scenario_weights in weights["scenarios"].items():
        scenarios[scenario_name] = {"per_seed": {}, "summary": {}, "contributions": {}}
        for rule in RULES:
            values = []
            per_seed = {}
            for seed in SEEDS:
                by_rank = {}
                for rank in RANKS:
                    total = _empty_flow()
                    for set_code, weight in scenario_weights.items():
                        shard = rows[set_code][rank][str(seed)]
                        for field in FLOW_WITH_METRICS:
                            total[field] += weight * float(shard["flows"][rule.key][field]) / float(shard["samples_per_set"])
                    by_rank[rank] = total
                production = _seed_production(by_rank)
                per_seed[str(seed)] = production
                values.append(production)
            current_values = None
            scenarios[scenario_name]["per_seed"][rule.key] = per_seed
            scenarios[scenario_name]["summary"][rule.key] = {
                "formal_baili_per_100k": _ci([value["formal_baili_per_100k"] for value in values]),
                "stamina_per_baili": _ci([float(value["stamina_per_baili"]) for value in values]),
                "rift_stamina_per_100k": _ci([value["rift_stamina_per_100k"] for value in values]),
                "saint_stamina_per_100k": _ci([value["saint_stamina_per_100k"] for value in values]),
                "cycles_per_100k": _ci([value["cycles_per_100k"] for value in values]),
                "native_heirloom_per_100k": _ci([value["per_100k"]["native_heirloom"] for value in values]),
                "converted_heirloom_per_100k": _ci([value["per_100k"]["converted_heirloom"] for value in values]),
                "speed22_per_100k": _ci([value["per_100k"]["speed22"] for value in values]),
                "output60_per_100k": _ci([value["per_100k"]["output60"] for value in values]),
                "absolute_cost_unstable": _ci([float(value["stamina_per_baili"]) for value in values])["relative_half_width"] > 0.10,
            }
        baseline = scenarios[scenario_name]["per_seed"]["current_formal"]
        for rule in RULES:
            values = scenarios[scenario_name]["per_seed"][rule.key]
            scenarios[scenario_name]["summary"][rule.key]["paired_baili_delta_vs_current"] = _ci([values[str(seed)]["formal_baili_per_100k"] - baseline[str(seed)]["formal_baili_per_100k"] for seed in SEEDS])
        for rule in RULES:
            by_rank, contribution = _weighted(rows, scenario_weights, "Epic", rule.key)
            _heroic, heroic_contribution = _weighted(rows, scenario_weights, "Heroic", rule.key)
            scenarios[scenario_name]["contributions"][rule.key] = {"epic_weighted_flow": by_rank, "epic_set_and_system": contribution, "heroic_set_and_system": heroic_contribution, "denominator_note": "Rift source is fixed at 85 per batch; Saint is a joint bottleneck computed from the complete weighted flow, so it is not additively attributed to individual sets."}

    audit = {}
    for scenario_name in ("uniform_observed_sets", "reforged_inventory_all"):
        current = scenarios[scenario_name]["summary"]["current_formal"]["stamina_per_baili"]
        audit[scenario_name] = {
            "dp_comparable_sum_total_stamina_div_sum_formal_baili": current,
            "released_epic_dp_799_2_difference": current["mean"] - 799.2,
            "user_memory_700_difference": current["mean"] - 700.0,
            "invalid_phase_c_1451_45_difference": current["mean"] - 1451.45,
            "scope": "fixed 85-stamina joint Epic/Heroic batch plus Saint supplement, sell recovery and legal conversion; 22 speed excluded from formal baili numerator",
        }
    return {"study": STUDY, "schema_version": SCHEMA_VERSION, "complete": True, "execution": execution, "weights": weights, "hashes": hashes, "samples_per_set": samples_per_set, "rules": [{**asdict(rule), "candidate_hash": phase_c.candidate_hash(rule)} for rule in RULES], "scenarios": scenarios, "historical_metric_audit": audit, "freeze": "not_frozen_no_holdout"}


def _fmt(metric: dict[str, Any], digits: int = 2) -> str:
    return f"{metric['mean']:.{digits}f} [{metric['interval95'][0]:.{digits}f}, {metric['interval95'][1]:.{digits}f}]"


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# 已重铸库存套装权重与百里分体力效率对比",
        "",
        "库存权重只描述账号保留/需求，不推算自然掉率，不改变固定85体力维度裂缝联合来源批次或Epic/Heroic联合产出。所有强化事件使用本研究器的STOVE离散采样；22速独立报告，未折算为正式百里分。",
        "",
        "## 输入与覆盖",
        "",
        f"- 外部文件SHA-256：`{data['weights']['source_sha256']}`；重铸筛选结果：Epic {data['weights']['rank_totals']['Epic']}、Heroic {data['weights']['rank_totals']['Heroic']}，合计765。",
        f"- 原子覆盖：{data['execution']['expected_shards']} 个 set×rank×seed 分片，每分片 {data['samples_per_set']} 个条件合法非速度胚子。",
        "- 绝对值条件于本轮合法胚子生成模型；候选差值使用同套装、同品质、同seed的共同随机路径。",
        "",
    ]
    for scenario_name, scenario in data['scenarios'].items():
        lines.extend([f"## {scenario_name}", "", "| 策略 | 正式百里分/10万体力 | 每点百里分总体力 | 相对当前百里分增量/10万体力95%CI | 裂缝体力 | 圣女3-7体力 | 循环数 | 原生75+ | 转换75+ | 22速 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
        for rule in RULES:
            row = scenario['summary'][rule.key]
            lines.append(f"| {rule.key} | {_fmt(row['formal_baili_per_100k'])} | {_fmt(row['stamina_per_baili'])} | {_fmt(row['paired_baili_delta_vs_current'])} | {_fmt(row['rift_stamina_per_100k'])} | {_fmt(row['saint_stamina_per_100k'])} | {_fmt(row['cycles_per_100k'])} | {_fmt(row['native_heirloom_per_100k'], 3)} | {_fmt(row['converted_heirloom_per_100k'], 3)} | {_fmt(row['speed22_per_100k'], 3)} |")
        lines.append("")
    lines.extend(["## 与旧口径审计", "", "| 场景 | 本轮DP可比每点体力 | 相对799.2 | 相对约700 | 相对失效Phase C 1451.45 |", "|---|---:|---:|---:|---:|"])
    for name, row in data['historical_metric_audit'].items():
        metric = row['dp_comparable_sum_total_stamina_div_sum_formal_baili']
        lines.append(f"| {name} | {_fmt(metric)} | {row['released_epic_dp_799_2_difference']:.2f} | {row['user_memory_700_difference']:.2f} | {row['invalid_phase_c_1451_45_difference']:.2f} |")
    lines.extend(["", "799.2是发布Epic DP历史常量，约700是用户记忆值，1451.45来自已失效的旧Phase C；三者不默认与本轮同口径。只有本轮DP可比列使用相同的联合来源、Saint补充、出售回收、转换成本和正式百里分分子。", "", "## 状态", "", "- 本轮不冻结候选、不启动或读取holdout，也未修改正式策略、DP、资源模型、评分、跳值表、GUI或自动化。", "- 若任一场景的每点体力95%相对半宽大于10%，JSON会标记absolute_cost_unstable，不得据此写发布常量。"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-dir", type=Path, default=DEFAULT_RESUME)
    parser.add_argument("--samples-per-set", type=int, default=50)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--sets", help="comma-separated set-code slice")
    parser.add_argument("--seeds", help="comma-separated seed slice")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    selected_sets = {item.strip() for item in args.sets.split(',') if item.strip()} if args.sets else None
    selected_seeds = {int(item.strip()) for item in args.seeds.split(',') if item.strip()} if args.seeds else None
    data = run(resume=args.resume_dir, samples_per_set=max(1, args.samples_per_set), workers=max(1, args.workers), selected_sets=selected_sets, selected_seeds=selected_seeds)
    if not data['complete']:
        print(json.dumps({"complete": False, "execution": data['execution']}, ensure_ascii=False))
        return
    _atomic_json(args.json_output, data)
    args.report_output.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"complete": True, "json": str(args.json_output), "report": str(args.report_output), "execution": data['execution']}, ensure_ascii=False))


if __name__ == "__main__":
    main()
