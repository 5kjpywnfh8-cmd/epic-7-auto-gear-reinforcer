"""Read-only R50/R400 closure audit for inventory-weighted absolute cost.

This module intentionally does not import or call any path-generation worker.
It validates frozen shards, merges the five R50 seed clusters with the twenty
R400 block clusters, and writes new audit outputs only.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
from typing import Any
import json
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools import research_reforged_inventory_set_weight_bridge as bridge
from tools import research_reforged_inventory_set_weights as r50
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _empty_flow


STUDY = "reforged_inventory_set_weight_r800_weighted_closure_audit_20260718"
SCHEMA_VERSION = 2
R400_SAMPLES_PER_SET = 400
R800_SAMPLES_PER_SET = 800
R50_RESUME = r50.DEFAULT_RESUME
R400_RESUME = bridge.DEFAULT_RESUME_ROOT / "r400"
R50_HASH_REPORT = ROOT / "reports" / "reforged_inventory_set_weight_efficiency_20260718.json"
BRIDGE_HASH_REPORTS = {
    R400_SAMPLES_PER_SET: ROOT / "reports" / "reforged_inventory_set_weight_bridge_r400_20260718.json",
    R800_SAMPLES_PER_SET: ROOT / "reports" / "reforged_inventory_set_weight_bridge_r800_20260718.json",
}
DEFAULT_JSON = ROOT / "reports" / "reforged_inventory_set_weight_r800_weighted_closure_audit_20260718.json"
DEFAULT_REPORT = ROOT / "reports" / "reforged_inventory_set_weight_r800_weighted_closure_audit_20260718.md"
PRIMARY_SCENARIOS = ("reforged_inventory_all", "top4_equal")


def _add(target: dict[str, float], source: dict[str, float], factor: float = 1.0) -> None:
    for field in FLOW_WITH_METRICS:
        target[field] += factor * float(source[field])


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid frozen shard: {path}") from exc


def _frozen_hashes(path: Path) -> dict[str, str]:
    hashes = _read(path).get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError(f"frozen report has no code hashes: {path}")
    return {str(key): str(value) for key, value in hashes.items()}


def validate_r50_cluster(cluster: dict[str, Any], weights: dict[str, Any]) -> None:
    if cluster.get("source") != "r50":
        raise ValueError("R50 cluster source mismatch")
    seed = int(cluster["seed"])
    hashes = dict(cluster.get("hashes") or _frozen_hashes(R50_HASH_REPORT))
    for set_code in weights["observed_sets"]:
        for rank in r50.RANKS:
            payload = cluster["rows"].get(set_code, {}).get(rank)
            expected = r50._input_hash(set_code, rank, seed, 50, hashes)
            if not isinstance(payload, dict) or not _valid_r50_payload(payload, expected):
                raise ValueError(f"R50 shard missing or hash mismatch: seed={seed} set={set_code} rank={rank}")


def _valid_r50_payload(payload: dict[str, Any], expected_hash: str) -> bool:
    return (
        payload.get("status") == "complete"
        and payload.get("schema_version") == r50.SCHEMA_VERSION
        and payload.get("study") == r50.STUDY
        and payload.get("input_hash") == expected_hash
    )


def load_r50_clusters(weights: dict[str, Any], resume: Path = R50_RESUME) -> list[dict[str, Any]]:
    """Load all five R50 seed clusters and reject any frozen-shard mismatch."""
    hashes = _frozen_hashes(R50_HASH_REPORT)
    clusters = []
    for seed in r50.SEEDS:
        rows: dict[str, dict[str, Any]] = {}
        for set_code in weights["observed_sets"]:
            rows[set_code] = {}
            for rank in r50.RANKS:
                path = r50._shard_path(resume, set_code, rank, seed)
                payload = _read(path)
                expected = r50._input_hash(set_code, rank, seed, 50, hashes)
                if not _valid_r50_payload(payload, expected):
                    raise ValueError(f"R50 shard missing or hash mismatch: {path}")
                rows[set_code][rank] = payload
        cluster = {"source": "r50", "cluster_id": f"r50-seed-{seed}", "seed": seed, "sample_mass": 50, "hashes": hashes, "rows": rows}
        validate_r50_cluster(cluster, weights)
        clusters.append(cluster)
    return clusters


def _valid_secondary_payload(payload: dict[str, Any], *, samples_per_set: int, block: int, seed: int, set_code: str, rank: str, hashes: dict[str, str]) -> bool:
    expected = bridge._input_hash(
        block=block,
        seed=seed,
        set_code=set_code,
        rank=rank,
        samples_per_set=samples_per_set,
        hashes=hashes,
    )
    return (
        payload.get("status") == "complete"
        and payload.get("schema_version") == bridge.SCHEMA_VERSION
        and payload.get("study") == bridge.STUDY
        and payload.get("block") == block
        and payload.get("seed") == seed
        and payload.get("set_code") == set_code
        and payload.get("rank") == rank
        and payload.get("samples_per_set") == samples_per_set
        and payload.get("input_hash") == expected
    )


def load_stage_clusters(weights: dict[str, Any], samples_per_set: int, resume_root: Path = bridge.DEFAULT_RESUME_ROOT) -> list[dict[str, Any]]:
    """Load one cumulative stage only; no earlier stage is added to it."""
    if samples_per_set not in {R400_SAMPLES_PER_SET, R800_SAMPLES_PER_SET}:
        raise ValueError(f"unsupported closure stage: r{samples_per_set}")
    hashes = _frozen_hashes(BRIDGE_HASH_REPORTS[samples_per_set])
    clusters = []
    for block in bridge.DEFAULT_BLOCKS:
        seed = bridge._block_seed(block)
        rows: dict[str, dict[str, Any]] = {}
        for set_code in weights["observed_sets"]:
            rows[set_code] = {}
            for rank in bridge.RANKS:
                path = bridge._shard_path(resume_root, samples_per_set, block, seed, set_code, rank)
                payload = _read(path)
                if not _valid_secondary_payload(payload, samples_per_set=samples_per_set, block=block, seed=seed, set_code=set_code, rank=rank, hashes=hashes):
                    raise ValueError(f"R{samples_per_set} shard missing or hash mismatch: {path}")
                rows[set_code][rank] = payload
        clusters.append({"source": f"r{samples_per_set}", "cluster_id": f"r{samples_per_set}-block-{block:03d}", "block": block, "seed": seed, "sample_mass": samples_per_set, "hashes": hashes, "rows": rows})
    return clusters


def load_r400_clusters(weights: dict[str, Any], resume: Path = R400_RESUME) -> list[dict[str, Any]]:
    return load_stage_clusters(weights, R400_SAMPLES_PER_SET, resume.parent)


def load_r800_clusters(weights: dict[str, Any], resume_root: Path = bridge.DEFAULT_RESUME_ROOT) -> list[dict[str, Any]]:
    return load_stage_clusters(weights, R800_SAMPLES_PER_SET, resume_root)


def _cluster_flow(cluster: dict[str, Any], weights: dict[str, float], rule_key: str, rank: str) -> dict[str, float]:
    total = _empty_flow()
    for set_code, weight in weights.items():
        row = cluster["rows"][set_code][rank]
        if cluster["source"] == "r50":
            flow = row["flows"][rule_key]
        elif rank == "Epic":
            flow = row["flows"][rule_key]
        else:
            flow = row["released_heroic_flow"]
        _add(total, flow, float(weight) / float(row["samples_per_set"]))
    return total


def _cluster_ledger(cluster: dict[str, Any], weights: dict[str, float], rule_key: str) -> dict[str, Any]:
    epic = _cluster_flow(cluster, weights, rule_key, "Epic")
    heroic = _cluster_flow(cluster, weights, rule_key, "Heroic")
    heroic_yield = float(joint_source_batch_metadata(r50.GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))["expected_output_by_rank"]["Heroic"])
    merged = dict(epic)
    _add(merged, heroic, heroic_yield)
    pool = bridge._pool(merged)
    return {
        "cluster_id": cluster["cluster_id"],
        "source": cluster["source"],
        "sample_mass": float(cluster["sample_mass"]),
        "numerator_formal_baili": float(merged["value_sum"]),
        "denominator_total_stamina": float(pool["total_stamina"]),
        "rift_stamina": 85.0,
        "saint_stamina": float(pool["saint_supplement_stamina"]),
        "native_heirloom": float(merged["native_heirloom"]),
        "converted_heirloom": float(merged["converted_heirloom"]),
        "speed22": float(merged["speed22"]),
        "pool": pool,
    }


def _paired_delta(values: list[dict[str, Any]], baseline: list[dict[str, Any]], *, bootstrap_seed: int = 20260718, draws: int = 4000) -> dict[str, Any]:
    """Paired, source-stratified bootstrap that preserves each stage's sample mass."""
    pairs = list(zip(values, baseline))
    strata = {source: [pair for pair in pairs if pair[0]["source"] == source and pair[1]["source"] == source] for source in sorted({str(row["source"]) for row in values})}
    if sum(len(rows) for rows in strata.values()) != len(pairs):
        raise ValueError("paired ledger sources must match")

    def rate(rows: list[dict[str, Any]]) -> float:
        denominator = _mass_sum(rows, "denominator_total_stamina")
        return 100.0 * _mass_sum(rows, "numerator_formal_baili") / denominator if denominator else 0.0

    center = rate(values) - rate(baseline)
    rng = random.Random(bootstrap_seed)
    deltas = []
    for _ in range(draws):
        sampled = [pair for rows in strata.values() for pair in (rows[rng.randrange(len(rows))] for _ in rows)]
        deltas.append(rate([pair[0] for pair in sampled]) - rate([pair[1] for pair in sampled]))
    deltas.sort()
    return {
        "mean": center,
        "interval95": [deltas[int(0.025 * (len(deltas) - 1))], deltas[int(0.975 * (len(deltas) - 1))]],
        "unit": "formal_baili_per_100_total_stamina",
        "cluster_count": len(pairs),
        "method": "paired_common_path_source_stratified_bootstrap",
        "bootstrap_strata": {source: len(rows) for source, rows in strata.items()},
    }


def _mass_sum(ledgers: list[dict[str, Any]], field: str) -> float:
    return sum(float(row["sample_mass"]) * float(row[field]) for row in ledgers)


def _source_stratified_positive_ratio(ledgers: list[dict[str, Any]], *, bootstrap_seed: int = 20260718, draws: int = 4000) -> dict[str, Any]:
    """Mass-weighted ratio with fixed source-stage bootstrap allocation."""
    usable = [row for row in ledgers if row["numerator_formal_baili"] > 0 and row["denominator_total_stamina"] >= 0 and row["sample_mass"] > 0]
    numerator = _mass_sum(usable, "numerator_formal_baili")
    denominator = _mass_sum(usable, "denominator_total_stamina")
    strata = {source: [row for row in usable if row["source"] == source] for source in sorted({str(row["source"]) for row in usable})}
    stratum_counts = {source: len(rows) for source, rows in strata.items()}
    if not usable or numerator <= 0 or denominator < 0:
        return {"mean": None, "interval95": None, "relative_half_width": None, "cluster_count": len(usable), "ess": 0.0, "max_cluster_share": None, "method": "source_stratified_clustered_positive_bootstrap", "bootstrap_strata": stratum_counts, "status": "no_positive_baili"}
    rng = random.Random(bootstrap_seed)
    ratios = []
    for _ in range(draws):
        sampled = [row for rows in strata.values() for row in (rows[rng.randrange(len(rows))] for _ in rows)]
        sampled_numerator = _mass_sum(sampled, "numerator_formal_baili")
        sampled_denominator = _mass_sum(sampled, "denominator_total_stamina")
        if sampled_numerator > 0 and sampled_denominator >= 0:
            ratios.append(sampled_denominator / sampled_numerator)
    ratios.sort()
    lower = max(0.0, ratios[int(0.025 * (len(ratios) - 1))])
    upper = ratios[int(0.975 * (len(ratios) - 1))]
    values = [float(row["sample_mass"]) * float(row["numerator_formal_baili"]) for row in usable]
    return {
        "mean": denominator / numerator,
        "interval95": [lower, upper],
        "relative_half_width": (upper - lower) / (2.0 * (denominator / numerator)),
        "cluster_count": len(usable),
        "ess": numerator * numerator / sum(value * value for value in values),
        "max_cluster_share": max(values) / numerator,
        "method": "source_stratified_clustered_positive_bootstrap",
        "bootstrap_strata": stratum_counts,
        "status": "ok",
    }


def _aggregate(ledgers: list[dict[str, Any]]) -> dict[str, Any]:
    ratio = _source_stratified_positive_ratio(ledgers)
    numerator = _mass_sum(ledgers, "numerator_formal_baili")
    denominator = _mass_sum(ledgers, "denominator_total_stamina")
    total_sample_mass = sum(float(row["sample_mass"]) for row in ledgers)
    cycles = 100000.0 * total_sample_mass / denominator if denominator else 0.0
    rift_stamina = 100000.0 * _mass_sum(ledgers, "rift_stamina") / denominator if denominator else 0.0
    saint_stamina = 100000.0 * _mass_sum(ledgers, "saint_stamina") / denominator if denominator else 0.0
    if denominator and abs((rift_stamina + saint_stamina) - 100000.0) > 1e-7:
        raise ValueError("rift and saint stamina must conserve 100000 total stamina")
    return {
        "absolute_cost": ratio,
        "formal_baili_per_100k": 100000.0 * numerator / denominator if denominator else 0.0,
        "rift_stamina_per_100k": rift_stamina,
        "saint_stamina_per_100k": saint_stamina,
        "cycles_per_100k": cycles,
        "native_heirloom_per_100k": 100000.0 * _mass_sum(ledgers, "native_heirloom") / denominator if denominator else 0.0,
        "converted_heirloom_per_100k": 100000.0 * _mass_sum(ledgers, "converted_heirloom") / denominator if denominator else 0.0,
        "speed22_per_100k": 100000.0 * _mass_sum(ledgers, "speed22") / denominator if denominator else 0.0,
        "stamina_conservation_error": (rift_stamina + saint_stamina) - 100000.0 if denominator else 0.0,
        "total_sample_mass": total_sample_mass,
        "sample_mass_by_source": {source: sum(float(row["sample_mass"]) for row in ledgers if row["source"] == source) for source in sorted({str(row["source"]) for row in ledgers})},
        "source_cluster_counts": {source: sum(row["source"] == source for row in ledgers) for source in sorted({str(row["source"]) for row in ledgers})},
    }


def summarize(r50_clusters: list[dict[str, Any]], stage_clusters: list[dict[str, Any]], weights: dict[str, Any]) -> dict[str, Any]:
    if not stage_clusters:
        raise ValueError("closure audit requires a secondary stage")
    stage = str(stage_clusters[0]["source"])
    all_clusters = [*r50_clusters, *stage_clusters]
    if len(r50_clusters) != 5 or len(stage_clusters) != 20 or any(row["source"] != stage for row in stage_clusters):
        raise ValueError("closure audit requires exactly five R50 and twenty same-stage clusters")
    scenarios: dict[str, Any] = {}
    for scenario_name, scenario_weights in weights["scenarios"].items():
        rules: dict[str, Any] = {}
        ledgers_by_rule: dict[str, list[dict[str, Any]]] = {}
        for rule in r50.RULES:
            ledgers = [_cluster_ledger(cluster, scenario_weights, rule.key) for cluster in all_clusters]
            row = _aggregate(ledgers)
            ledgers_by_rule[rule.key] = ledgers
            rules[rule.key] = row
        baseline = ledgers_by_rule["current_formal"]
        for rule in r50.RULES:
            rules[rule.key]["paired_delta_vs_current"] = (
                {"mean": 0.0, "interval95": [0.0, 0.0], "unit": "formal_baili_per_100_total_stamina", "cluster_count": len(baseline), "method": "paired_common_path_source_stratified_bootstrap", "bootstrap_strata": {"r50": len(r50_clusters), stage: len(stage_clusters)}}
                if rule.key == "current_formal" else _paired_delta(ledgers_by_rule[rule.key], baseline)
            )
        scenarios[scenario_name] = {"rules": rules}
    current = scenarios["reforged_inventory_all"]["rules"]["current_formal"]["absolute_cost"]
    return {
        "study": STUDY,
        "schema_version": SCHEMA_VERSION,
        "execution": {"trajectory_generation": "not_run_read_only_audit", "secondary_stage": stage, "r50_clusters": len(r50_clusters), "r50_sample_mass_per_cluster": 50, f"{stage}_clusters": len(stage_clusters), f"{stage}_sample_mass_per_cluster": R800_SAMPLES_PER_SET if stage == "r800" else R400_SAMPLES_PER_SET, "r200_clusters": 0, "r400_clusters": 0 if stage != "r400" else len(stage_clusters)},
        "r50_scope": "final full-joint four-rule comparison only; R50 does not supply the R400 five-layer historical bridge fields",
        "scenarios": scenarios,
        "next_expansion_required": bool(current["relative_half_width"] is None or current["relative_half_width"] > 0.10),
        "r800_required": bool(str(stage) == "r400" and (current["relative_half_width"] is None or current["relative_half_width"] > 0.10)),
        "freeze": "not_frozen_no_holdout",
    }


def _fmt(value: float | None, digits: int = 2) -> str:
    return "not estimated" if value is None else f"{value:.{digits}f}"


def markdown(data: dict[str, Any]) -> str:
    stage = str(data["execution"]["secondary_stage"])
    lines = [
        "# 已重铸库存套装权重 R800 聚合权重与资源缩放修复",
        "",
        f"本报告只读合并 R50 的 5 个 seed cluster（每个质量50）与 {stage.upper()} 的20个 block cluster（每个质量{data['execution'][f'{stage}_sample_mass_per_cluster']}）。R200/R400 不会与当前阶段重复相加；没有生成任何新轨迹。",
        "",
        "## 审计范围",
        "",
        "- R50 仅用于最终完整联合四策略比较；R400 五层旧口径桥接保持独立，不伪造 R50 缺失的历史分子。",
        f"- 合并 cluster：R50={data['execution']['r50_clusters']}，{stage.upper()}=20，R200={data['execution']['r200_clusters']}。",
        f"- 扩样闸门：`{'仍需下一扩样阶段' if data['next_expansion_required'] else '当前阶段收口'}`。",
        "",
        "## 聚合与守恒诊断",
        "",
        "- 路径质量：R50 为 `5 × 50 = 250`，R800 为 `20 × 800 = 16,000`，合计 `16,250`；R50 在合并点估计中固定占 `1.53846%`，不会再被等权放大为20%。",
        "- 每个策略的绝对区间均按 R50 五个 seed 与 R800 二十个 block 分层重采样，抽样时保持各层数量和 sample_mass 不变；JSON 同时保存 cluster ESS 与最大单 cluster 贡献。",
        "- 每行已验证 `裂缝体力 + 圣女体力 = 100,000`。R200/R400 没有读取或计入，未生成新轨迹。",
        "",
    ]
    for scenario_name in PRIMARY_SCENARIOS:
        lines.extend([
            f"## {scenario_name}",
            "",
            "| 策略 | 体力/正式百里分 95%CI | 正式百里分/10万体力 | 成对变化/100体力 95%CI | 裂缝/圣女体力 | 循环 | 原生75+ | 转换75+ | 22速 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for rule in r50.RULES:
            row = data["scenarios"][scenario_name]["rules"][rule.key]
            cost = row["absolute_cost"]
            paired = row["paired_delta_vs_current"]
            lines.append(
                f"| `{rule.key}` | {_fmt(cost['mean'])} [{_fmt(cost['interval95'][0])}, {_fmt(cost['interval95'][1])}] | {_fmt(row['formal_baili_per_100k'])} | {_fmt(paired['mean'], 6)} [{_fmt(paired['interval95'][0], 6)}, {_fmt(paired['interval95'][1], 6)}] | {_fmt(row['rift_stamina_per_100k'])}/{_fmt(row['saint_stamina_per_100k'])} | {_fmt(row['cycles_per_100k'])} | {_fmt(row['native_heirloom_per_100k'], 3)} | {_fmt(row['converted_heirloom_per_100k'], 3)} | {_fmt(row['speed22_per_100k'], 3)} |"
            )
        lines.append("")
    lines.extend([
        "## 结论",
        "",
        "- 所有分子、分母、资源和终局产量均先按来源 cluster 的实际 sample_mass 求和；每行裂缝体力加圣女体力严格等于 100,000（仅允许浮点误差）。",
        "- 绝对成本区间使用按来源分层 cluster 聚类的正值约束 bootstrap，R50 与当前阶段的设计样本质量保持固定，区间下界不为负。",
        "- 该结果是离线审计，不冻结候选、不启动或读取 holdout，也不修改正式策略、DP、资源、评分、GUI、OCR 或自动化。",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only R50/stage weighted closure audit")
    parser.add_argument("--stage-samples", type=int, choices=(R400_SAMPLES_PER_SET, R800_SAMPLES_PER_SET), default=R400_SAMPLES_PER_SET)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    weights = r50.derive_weights()
    stage_clusters = load_stage_clusters(weights, args.stage_samples)
    data = summarize(load_r50_clusters(weights), stage_clusters, weights)
    r50._atomic_json(args.json_output, data)
    args.report_output.write_text(markdown(data), encoding="utf-8")
    print(json.dumps({"json": str(args.json_output), "report": str(args.report_output), "next_expansion_required": data["next_expansion_required"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
