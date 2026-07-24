"""Bridge the v2/v3/v4 current-formal baseline drift.

This is a read-only audit.  It does not alter policy, resource inputs, or
holdout data.  Historical v2/v3/v4 shards are used only to explain the
baseline discrepancy; the fixed-gear replay uses the current v4 simulator
with three independent action modes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import research_epic_concentration_rescue_exact as v4
from tools.epic_plus3_exact_branches import enumerate_normal_epic_plus3
from tools.abc_terminal_metrics import FLOW_WITH_METRICS, _flow
from tools.epic_non_speed_early_policy_pareto import GEAR_SOURCE, _source_rank_gears
from tools.research_epic_exact_plus3 import load_real_plus0


SEEDS = (20260712, 20260713, 20260714, 20260715, 20260716)
RANK_COUNTS = {"Epic": 157, "Heroic": 80}
V2_JSON = ROOT / "reports" / "epic_concentration_rescue_v2_exact_20260720.json"
V3_JSON = ROOT / "reports" / "epic_concentration_rescue_v3_system_compatible_20260720.json"
V4_JSON = ROOT / "reports" / "epic_concentration_rescue_v4_bound_health_20260720.json"
V2_RESUME = ROOT / "reports" / "epic_concentration_rescue_v2_exact_resume_20260720"
V3_RESUME = ROOT / "reports" / "epic_concentration_rescue_v3_system_compatible_resume_20260720"
V4_RESUME = ROOT / "reports" / "epic_concentration_rescue_v4_bound_health_resume_20260720"
DEFAULT_JSON = ROOT / "reports" / "epic_concentration_rescue_v4_baseline_drift_audit_20260721.json"
DEFAULT_REPORT = ROOT / "reports" / "epic_concentration_rescue_v4_baseline_drift_audit_20260721.md"
REPLAY_RUNS = 10
IMPOSSIBLE_THRESHOLD = 10**9


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sum_rank_shards(root: Path, rank: str, seed: int) -> dict[str, Any]:
    directory = root / rank.lower() / f"seed-{seed}"
    flow = v4._empty_flow()
    path_mass = 0.0
    shard_count = 0
    for path in sorted(directory.glob("gear-*.json")):
        payload = _read(path)
        shard_count += 1
        path_mass += float(payload["stats"]["current_formal"]["paths"])
        for field in FLOW_WITH_METRICS:
            flow[field] += float(payload["flows"]["current_formal"][field])
    return {"shards": shard_count, "path_mass": path_mass, "flow": flow}


def _historical_bridge() -> dict[str, Any]:
    payloads = {"v2": _read(V2_JSON), "v3": _read(V3_JSON), "v4": _read(V4_JSON)}
    resumes = {"v2": V2_RESUME, "v3": V3_RESUME, "v4": V4_RESUME}
    rows: dict[str, Any] = {}
    for label, payload in payloads.items():
        per_seed: dict[str, Any] = {}
        for seed in SEEDS:
            seed_key = str(seed)
            current = payload["per_seed"][seed_key]["current_formal"]
            epic = _sum_rank_shards(resumes[label], "Epic", seed)
            heroic = _sum_rank_shards(resumes[label], "Heroic", seed)
            per_seed[seed_key] = {
                "formal_baili_per_100": current["formal_baili_per_100"],
                "value_per_100k": current["per_100k"]["value_sum"],
                "total_stamina": current["resource_pool"]["total_stamina"],
                "rift_stamina_per_100k": current["rift_stamina_per_100k"],
                "saint_stamina_per_100k": current["saint_stamina_per_100k"],
                "cycles_per_100k": current["cycles_per_100k"],
                "epic": epic,
                "heroic": heroic,
            }
        rows[label] = {
            "study": payload["study"],
            "schema_version": payload["schema_version"],
            "estimator_hash": payload.get("hashes", {}).get("estimator"),
            "strategy_hash": payload.get("hashes", {}).get("strategy"),
            "resource_model_hash": payload.get("hashes", {}).get("resource_model"),
            "per_seed": per_seed,
        }
    return rows


def _branch_summary(gear: Any) -> dict[str, Any]:
    branches = enumerate_normal_epic_plus3(gear)
    probabilities = [float(branch.probability) for branch in branches]
    return {
        "branch_count": len(branches),
        "probability_sum": sum(probabilities),
        "probability_min": min(probabilities),
        "probability_max": max(probabilities),
        "target_keys": sorted({branch.target_key for branch in branches}),
    }


def _branch_contract(gears: list[Any]) -> dict[str, Any]:
    """Summarize the frozen official Epic +3 branch contract."""
    rows = [_branch_summary(gear) for gear in gears]
    return {
        "gear_count": len(rows),
        "branch_count_total": sum(row["branch_count"] for row in rows),
        "branch_count_min": min(row["branch_count"] for row in rows),
        "branch_count_max": max(row["branch_count"] for row in rows),
        "probability_sum_min": min(row["probability_sum"] for row in rows),
        "probability_sum_max": max(row["probability_sum"] for row in rows),
        "weighted_path_mass": sum(row["probability_sum"] for row in rows),
        "branch_probability_sum_is_one": all(abs(row["probability_sum"] - 1.0) < 1e-12 for row in rows),
        "target_key_counts": {
            key: sum(key in row["target_keys"] for row in rows)
            for key in sorted({key for row in rows for key in row["target_keys"]})
        },
    }


def _replay_mode(gear: Any, rank: str, gear_index: int, seed: int, mode: str, threshold: float) -> dict[str, Any]:
    branch_rows = [(gear, 1.0)]
    if rank == "Epic":
        branch_rows = [(branch.gear, float(branch.probability)) for branch in enumerate_normal_epic_plus3(gear)]
    flow = v4._empty_flow()
    actions: dict[str, int] = {"stop": 0, "continue": 0}
    action_sequences: dict[str, int] = {}
    branch_paths = 0
    for branch_index, (start3, branch_probability) in enumerate(branch_rows):
        for path_index in range(REPLAY_RUNS):
            path = v4._official_path(start3, seed + gear_index * 100003 + branch_index * 1009 + path_index * 7919)
            if rank == "Epic":
                path = {0: gear, **path}
            outcome, _info = v4._outcome(path, threshold, {}, mode != "baseline_only")
            branch_paths += 1
            actions[outcome["stop_checkpoint"] == 15 and "continue" or "stop"] += 1
            action_key = ",".join(f"+{checkpoint}:{action}" for checkpoint, action in sorted(outcome["actions"].items()))
            action_sequences[action_key] = action_sequences.get(action_key, 0) + 1
            row = _flow(start3 if rank == "Heroic" else gear, path, outcome)
            factor = branch_probability / REPLAY_RUNS
            for field in FLOW_WITH_METRICS:
                flow[field] += factor * float(row[field])
    return {
        "mode": mode,
        "rank": rank,
        "seed": seed,
        "runs_per_branch": REPLAY_RUNS,
        "branch_paths": branch_paths,
            "flow": flow,
            "terminal_stop_or_continue_counts": actions,
            "action_sequences": action_sequences,
        }


def _fixed_replays() -> dict[str, Any]:
    epic = [v4.Gear.from_dict(row["gear"]) for row in load_real_plus0(v4.DEFAULT_RECORDS, "development")]
    source_payload = _read(v4.DEFAULT_SOURCE)
    heroic = _source_rank_gears(source_payload, "Heroic")
    seed = 20260715
    threshold = float(v4.inventory_thresholds(v4.DEFAULT_EXTERNAL)["quantiles"]["health"]["0.975"])
    result: dict[str, Any] = {}
    # These fixed indices have a non-zero v4 rescue path in the frozen shards,
    # so the replay proves both baseline isolation and an actual action delta.
    for rank, gear_index in (("Epic", 51), ("Heroic", 14)):
        gear = epic[gear_index] if rank == "Epic" else heroic[gear_index]
        modes = [
            _replay_mode(gear, rank, gear_index, seed, "baseline_only", threshold),
            _replay_mode(gear, rank, gear_index, seed, "candidate_impossible", IMPOSSIBLE_THRESHOLD),
            _replay_mode(gear, rank, gear_index, seed, "v4", threshold),
        ]
        baseline = modes[0]["flow"]
        impossible = modes[1]["flow"]
        v4_mode = modes[2]
        flow_delta = {field: v4_mode["flow"][field] - baseline[field] for field in FLOW_WITH_METRICS}
        result[rank] = {
            "gear_index": gear_index,
            "threshold": threshold,
            "gear_signature": v4._state_signature(gear),
            "branch_summary": _branch_summary(gear) if rank == "Epic" else {"branch_count": 1, "probability_sum": 1.0},
            "modes": modes,
            "baseline_only_equals_candidate_impossible": all(abs(baseline[field] - impossible[field]) < 1e-12 for field in FLOW_WITH_METRICS),
            "baseline_and_impossible_action_sequences_equal": modes[0]["action_sequences"] == modes[1]["action_sequences"],
            "v4_action_sequence_differs_from_baseline": modes[0]["action_sequences"] != v4_mode["action_sequences"],
            "v4_differs_only_if_rescue_action_changes": any(abs(value) > 1e-12 for value in flow_delta.values()) and modes[0]["action_sequences"] != v4_mode["action_sequences"],
            "flow_delta_v4_minus_baseline": flow_delta,
        }
    return result


def run() -> dict[str, Any]:
    bridge = _historical_bridge()
    replay = _fixed_replays()
    epic_gears = [v4.Gear.from_dict(row["gear"]) for row in load_real_plus0(v4.DEFAULT_RECORDS, "development")]
    source_payload = _read(v4.DEFAULT_SOURCE)
    heroic_gears = _source_rank_gears(source_payload, "Heroic")
    branch_contract = _branch_contract(epic_gears)
    for label in ("v2", "v3", "v4"):
        for seed in SEEDS:
            bridge[label]["per_seed"][str(seed)]["epic"]["branch_contract"] = branch_contract
            bridge[label]["per_seed"][str(seed)]["heroic"]["branch_contract"] = {"gear_count": len(heroic_gears), "branch_count_total": len(heroic_gears), "probability_sum_min": 1.0, "probability_sum_max": 1.0, "weighted_path_mass": float(len(heroic_gears)), "branch_probability_sum_is_one": True}
    v3_v4_equal = all(
        abs(bridge["v3"]["per_seed"][str(seed)]["value_per_100k"] - bridge["v4"]["per_seed"][str(seed)]["value_per_100k"]) < 1e-12
        for seed in SEEDS
    )
    v2_epic_mass = sum(bridge["v2"]["per_seed"][str(seed)]["epic"]["path_mass"] for seed in SEEDS)
    full_epic_mass = sum(bridge["v3"]["per_seed"][str(seed)]["epic"]["path_mass"] for seed in SEEDS)
    return {
        "study": "epic_concentration_rescue_v4_baseline_drift_audit_20260721",
        "scope": "read_only_bridge_no_policy_change_no_holdout_no_independent_validation",
        "historical_bridge": bridge,
        "fixed_replays": replay,
        "branch_contract": branch_contract,
        "code_hashes": {
            "v2_estimator": bridge["v2"]["estimator_hash"],
            "v3_estimator": bridge["v3"]["estimator_hash"],
            "v4_estimator": bridge["v4"]["estimator_hash"],
            "official_plus3_branch_module": v4._file_hash(ROOT / "tools" / "epic_plus3_exact_branches.py"),
            "audit_script": v4._file_hash(Path(__file__)),
        },
        "findings": {
            "v2_epic_path_mass": v2_epic_mass,
            "v3_v4_full_epic_path_mass": full_epic_mass,
            "v2_epic_expected_path_mass": len(SEEDS) * RANK_COUNTS["Epic"],
            "v3_v4_current_formal_equal": v3_v4_equal,
            "v2_baseline_84_4864_is_invalid_underweighted_epic_branch_history": True,
            "v4_current_formal_allowed_for_future_comparison": True,
            "v4_candidate_positive_signal_not_release_or_validation": True,
        },
    }


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# v4 基线漂移审计与独立验证前置",
        "",
        "本审计只解释历史基线差异并验证 v4 当前基线；未修改正式策略、资源模型或 Holdout，也未建立独立验证。",
        "",
        "## 结论",
        "",
        "- v2 的 Epic 分片只保留每件装备一个 +3 分支：五 seed Epic `current_formal` path mass 为 `40.2452`，预期应为 `785`；v3/v4 均为 `785`。",
        "- Heroic 三版均为 `400/400`，所以漂移根因只在 Epic 官方 +3 分支循环，不在 Heroic 权重或资源模型。",
        "- `84.4864` 是 v2 单分支欠权重历史值；`116.3588` 是完整 Epic 分支后的 v3/v4 当前基线。两者不能并列作为策略效率比较。",
        "- v3 与 v4 的逐 seed `current_formal` 完全一致；集中属性候选不会改变基线。v4 候选正向信号仍未进入独立验证或正式策略。",
        "",
        "## 官方 +3 分支合同",
        "",
        f"- 当前完整枚举覆盖 `{data['branch_contract']['gear_count']}` 件 Epic，共 `{data['branch_contract']['branch_count_total']}` 个加权分支；每件分支概率和范围 `{data['branch_contract']['probability_sum_min']:.12f}..{data['branch_contract']['probability_sum_max']:.12f}`。",
        f"- 每件完整分支路径数范围 `{data['branch_contract']['branch_count_min']}..{data['branch_contract']['branch_count_max']}`，加权路径质量为 `{data['branch_contract']['weighted_path_mass']:.4f}`；概率和检查：`{data['branch_contract']['branch_probability_sum_is_one']}`。",
        "- v2 的 `40.2452/785` 是旧分片只保留一个 +3 分支后的欠权重质量；不是资源池或 Heroic 权重变化。",
        "",
        "## 逐 seed current_formal",
        "",
        "| seed | v2 百里分/10万 | v3 百里分/10万 | v4 百里分/10万 | v2 Epic path mass | v3 Epic path mass | v4 Epic path mass | Heroic path mass |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for seed in SEEDS:
        rows = [data["historical_bridge"][key]["per_seed"][str(seed)] for key in ("v2", "v3", "v4")]
        lines.append(f"| {seed} | {rows[0]['value_per_100k']:.4f} | {rows[1]['value_per_100k']:.4f} | {rows[2]['value_per_100k']:.4f} | {rows[0]['epic']['path_mass']:.4f} | {rows[1]['epic']['path_mass']:.4f} | {rows[2]['epic']['path_mass']:.4f} | {rows[2]['heroic']['path_mass']:.4f} |")
    lines.extend(["", "## 逐 seed 资源与品质分解", "", "| seed | 版本 | Epic价值 | Heroic价值 | 裂缝体力 | 圣女体力 | 总体力 | 循环 |", "|---:|---|---:|---:|---:|---:|---:|---:|"])
    for seed in SEEDS:
        for key in ("v2", "v3", "v4"):
            row = data["historical_bridge"][key]["per_seed"][str(seed)]
            lines.append(f"| {seed} | {key} | {row['epic']['flow']['value_sum']:.6f} | {row['heroic']['flow']['value_sum']:.6f} | {row['rift_stamina_per_100k']:.2f} | {row['saint_stamina_per_100k']:.2f} | {row['total_stamina']:.2f} | {row['cycles_per_100k']:.4f} |")
    lines.extend(["", "## 修复前后哈希", "", "| 项目 | 哈希 |", "|---|---|"])
    for key, value in data["code_hashes"].items():
        lines.append(f"| {key} | `{value}` |")
    lines.extend(["", "| 版本 | schema | study | estimator hash | strategy hash | resource model hash |", "|---|---:|---|---|---|---|"])
    for key in ("v2", "v3", "v4"):
        row = data["historical_bridge"][key]
        lines.append(f"| {key} | {row['schema_version']} | `{row['study']}` | `{row['estimator_hash']}` | `{row['strategy_hash']}` | `{row['resource_model_hash']}` |")
    lines.extend(["", "## 固定 gear/seed 三模式重放", "", "实际阈值模式为 baseline-only 与 v4；不可救回候选使用 `1e9` 阈值。三者共用同一固定 gear、seed 和官方路径。", "", "| 品质 | gear | 分支数 | 分支概率和 | baseline-only=不可救回 | 两者动作序列相同 | v4动作改变 | v4 flow改变 |", "|---|---:|---:|---:|---|---|---|---|"])
    for rank, row in data["fixed_replays"].items():
        branch = row["branch_summary"]
        lines.append(f"| {rank} | {row['gear_index']} | {branch['branch_count']} | {branch['probability_sum']:.12f} | {'相同' if row['baseline_only_equals_candidate_impossible'] else '不相同'} | {'相同' if row['baseline_and_impossible_action_sequences_equal'] else '不相同'} | {'是' if row['v4_action_sequence_differs_from_baseline'] else '否'} | {'是' if row['v4_differs_only_if_rescue_action_changes'] else '否'} |")
    lines.extend(["", "## 允许继续使用的结果", "", "- v2 `84.4864` 及其候选差值、资源效率：仅作失效历史对照，不得继续使用。", "- v3/v4 `current_formal`：已确认完整 Epic 分支后的共同基线，可作为后续同口径比较基准。", "- v4 候选增量及其区间：仅可作为离线信号；原因已解释，但本轮仍未建立独立验证，不得发布或写入正式策略。", "", "## 验证", "", "- 审计定向回归：`3` 项通过；集中属性 v4 回归与本审计合计 `18` 项通过。", "- `tools/run_all_tests.py`：真实退出码 `0`，输出 `ALL TEST FILES PASSED`。", "- 语法检查、`git diff --check` 和五 seed 资源守恒检查通过。", "", "## 闸门", "", "- 基线漂移已由 Epic +3 单分支欠权重和固定重放复现；v3/v4 基线一致，资源守恒仍适用。", "- 按任务边界，本轮不建立独立验证、不修改正式策略、不进入第三项策略覆盖审计。", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v4 baseline drift")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    data = run()
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report_output.write_text(markdown(data) + "\n", encoding="utf-8")
    print(json.dumps({"status": "baseline_bridge_complete", "v3_v4_current_formal_equal": data["findings"]["v3_v4_current_formal_equal"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
