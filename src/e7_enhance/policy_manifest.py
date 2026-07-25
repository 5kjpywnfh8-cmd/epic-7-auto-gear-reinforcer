from __future__ import annotations

import argparse
import ast
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .models import (
    ALLOWED_RANKS_BY_ITEM_SOURCE,
    MAIN_STAT_KEYS_BY_SLOT,
    SUPPORTED_ENHANCEMENT_CHECKPOINTS,
    SUPPORTED_EQUIPMENT_LEVELS,
    Gear,
    Stat,
)
from .rules import SET_CODE_TO_NAME
from .strategy_defaults import DEFAULT_GEAR_SOURCE, STRATEGY_VERSION, default_strategy_for


SCHEMA_VERSION = "e7_enhance.policy_manifest/1.0"
BEHAVIOR_INPUTS = (
    "src/e7_enhance/calibration.py",
    "src/e7_enhance/enhance_policy.py",
    "src/e7_enhance/epic_early_stop.py",
    "src/e7_enhance/lightweight_calibration.py",
    "src/e7_enhance/lightweight_calibration_rules.json",
    "src/e7_enhance/models.py",
    "src/e7_enhance/modification_values.py",
    "src/e7_enhance/resource_model.py",
    "src/e7_enhance/rules.py",
    "src/e7_enhance/score_engine.py",
    "src/e7_enhance/strategy_defaults.py",
    "装备强化与评分规则审阅.md",
)
REGRESSION_EVIDENCE_SCHEMA = "e7_enhance.policy_regression_evidence/1.0"
REGRESSION_EVIDENCE_PATH = "reports/policy_v1_regression_evidence_20260725.json"
REGRESSION_EXECUTION_INPUTS = (
    "tools/capture_policy_v1_regression_evidence.py",
)
REGRESSION_TEST_INPUTS = (
    "tests/test_calibration.py",
    "tests/test_enhance_policy.py",
    "tests/test_epic_early_stop.py",
    "tests/test_heroic_speed22_rescue.py",
    "tests/test_research_epic_exact_plus3_joint_pool.py",
    "tests/test_resource_model.py",
    "tests/test_route_solver.py",
    "tests/test_score_engine.py",
    "tests/test_strategy_defaults.py",
)
REGRESSION_DIMENSIONS = {
    "item_source_ranks": [
        {"item_source": "normal_85", "rank": "Epic"},
        {"item_source": "normal_85", "rank": "Heroic"},
        {"item_source": "rift_85", "rank": "Epic"},
    ],
    "enhancement_checkpoints": [0, 3, 6, 9, 12, 15],
    "slot_segments": ["boot", "non_boot"],
    "route_boundaries": [
        "conversion",
        "epic_non_speed_early_stop",
        "heroic_speed22_rescue_m1",
        "speed_hard_route",
        "stop_recovery",
        "terminal_summary",
        "unknown_set_rejection",
    ],
}
REGRESSION_REQUIREMENTS = (
    {
        "id": "normal_epic_early_checkpoints",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_normal_epic_plus_3_all_valid_uses_lightweight_prediction_before_plus6_dp",
            "tests/test_epic_early_stop.py::EpicEarlyStopTest::test_policy_wiring_stops_and_uses_each_immediate_checkpoint",
        ],
    },
    {
        "id": "normal_epic_middle_checkpoints",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_normal_epic_dp_covers_plus6_and_later_checkpoints",
            "tests/test_calibration.py::CalibrationTest::test_dp_assisted_calls_route_solver_at_all_pre_final_checkpoints",
        ],
    },
    {
        "id": "terminal_checkpoint",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_plus_15_uses_final_disposition_without_dp",
        ],
    },
    {
        "id": "normal_heroic_fallback",
        "test_ids": [
            "tests/test_strategy_defaults.py::StrategyDefaultsTest::test_normal_heroic_falls_back_to_non_dp_strategy_until_resource_calibration_is_published",
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_normal_heroic_debug_explains_unpublished_resource_calibration_fallback",
        ],
    },
    {
        "id": "rift_epic_route",
        "test_ids": [
            "tests/test_strategy_defaults.py::StrategyDefaultsTest::test_rift_epic_defaults_to_dp_assisted",
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_rift_epic_default_uses_dp_assist",
        ],
    },
    {
        "id": "boot_boundary",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_speed_main_boot_full_output_category_continues_without_speed_substat",
            "tests/test_epic_early_stop.py::EpicEarlyStopTest::test_scope_excludes_other_routes",
        ],
    },
    {
        "id": "speed_hard_route",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_epic_non_boot_initial_speed_two_uses_hard_early_speed_route_for_both_sources",
        ],
    },
    {
        "id": "heroic_speed22_rescue_m1",
        "test_ids": [
            "tests/test_heroic_speed22_rescue.py::HeroicSpeed22RescueTest::test_legal_plus12_fourteen_speed_four_rolls_is_rescued_and_debugged",
        ],
    },
    {
        "id": "stop_recovery",
        "test_ids": [
            "tests/test_research_epic_exact_plus3_joint_pool.py::ExactPlus3JointPoolTest::test_interval_outcome_preserves_start_and_stop",
        ],
    },
    {
        "id": "conversion_boundary",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_plus3_conversion_candidate_uses_terminal_max_modification_gs",
            "tests/test_route_solver.py::RouteSolverTest::test_conversion_crossing_formal_rule_has_higher_utility",
        ],
    },
    {
        "id": "epic_early_system_groups",
        "test_ids": [
            "tests/test_epic_early_stop.py::EpicEarlyStopTest::test_exact_category_mapping_and_thresholds_are_frozen",
            "tests/test_epic_early_stop.py::EpicEarlyStopTest::test_stop_requires_every_frozen_condition",
        ],
    },
    {
        "id": "unknown_set_rejection",
        "test_ids": [
            "tests/test_enhance_policy.py::EnhancePolicyTest::test_strategy_rejects_unknown_set",
        ],
    },
    {
        "id": "score_and_resource_boundaries",
        "test_ids": [
            "tests/test_score_engine.py::ScoreEngineTest::test_theoretical_bound_uses_distinct_legal_conversion_and_missing_substat",
            "tests/test_resource_model.py::ResourceModelTest::test_plus_12_to_15_marginal_cost_uses_bottleneck_not_sum",
        ],
    },
)


class PolicyManifestError(RuntimeError):
    pass


def build_policy_manifest(root: Path, generated_on: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    behavior_inputs = _behavior_input_hashes(root)
    item_source_ranks = _item_source_rank_rows()
    decision_routes = _decision_routes(item_source_ranks)
    route_coverage_complete = _route_coverage_complete(item_source_ranks, decision_routes)
    unknown_set_fail_closed = _unknown_set_fail_closed()
    regression_evidence_attached, regression_evidence = _regression_evidence_attachment(root, behavior_inputs)
    policy_details = {"epic_non_speed_early_stop": _epic_early_stop_details()}

    gaps: list[str] = []
    if not unknown_set_fail_closed:
        gaps.append("unknown_set_not_rejected_by_advise_gear")
    if not regression_evidence_attached:
        gaps.append("full_regression_matrix_evidence_not_attached")

    gates = {
        "behavior_inputs_hashed": len(behavior_inputs) == len(BEHAVIOR_INPUTS),
        "supported_scope_complete": item_source_ranks
        == [
            {"item_source": "normal_85", "rank": "Epic"},
            {"item_source": "normal_85", "rank": "Heroic"},
            {"item_source": "rift_85", "rank": "Epic"},
        ],
        "decision_route_coverage_complete": route_coverage_complete,
        "unknown_set_fail_closed": unknown_set_fail_closed,
        "full_regression_matrix_evidence_attached": regression_evidence_attached,
    }
    freeze_status = "ready" if all(gates.values()) else "not_ready"

    supported_inputs = {
        "item_source_ranks": item_source_ranks,
        "equipment_levels": sorted(SUPPORTED_EQUIPMENT_LEVELS),
        "enhancement_checkpoints": sorted(SUPPORTED_ENHANCEMENT_CHECKPOINTS),
        "slots": [
            {"slot": slot, "main_stats": sorted(main_stats)}
            for slot, main_stats in sorted(MAIN_STAT_KEYS_BY_SLOT.items())
        ],
        "sets": [
            {"code": code, "name": SET_CODE_TO_NAME[code]}
            for code in sorted(SET_CODE_TO_NAME)
        ],
        "default_gear_source": DEFAULT_GEAR_SOURCE,
        "unknown_input_contract": {
            "item_source": "reject",
            "rank_for_source": "reject",
            "equipment_level": "reject",
            "enhancement_checkpoint": "reject",
            "slot": "reject",
            "main_stat_for_slot": "reject",
            "substat": "reject",
            "set": "reject" if unknown_set_fail_closed else "not_rejected",
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "freeze_status": freeze_status,
        "behavior_inputs": behavior_inputs,
        "supported_inputs": supported_inputs,
        "default_strategies": _default_strategy_rows(item_source_ranks),
        "decision_contract": {
            "entrypoint": "src.e7_enhance.enhance_policy.advise_gear",
            "summary_fields": ["recommendation", "next_check_at", "target_profile", "reasons"],
            "review_required_recommendations": ["cautious_continue", "uncertain"],
            "automation_boundary": "manifest_does_not_authorize_clicks_or_resource_consumption",
        },
        "decision_routes": decision_routes,
        "policy_details": policy_details,
        "regression_evidence": regression_evidence,
        "readiness": {"gates": gates, "gaps": gaps},
    }
    core_hash = _json_sha256(core)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": generated_on or date.today().isoformat(),
        "strategy_version": STRATEGY_VERSION,
        "manifest_sha256": core_hash,
        "freeze_status": freeze_status,
        "behavior_inputs": behavior_inputs,
        "supported_inputs": supported_inputs,
        "default_strategies": core["default_strategies"],
        "decision_contract": core["decision_contract"],
        "decision_routes": decision_routes,
        "policy_details": policy_details,
        "regression_evidence": regression_evidence,
        "readiness": core["readiness"],
    }


def write_policy_manifest(
    root: Path,
    *,
    json_path: Path,
    markdown_path: Path,
    generated_on: str | None = None,
) -> dict[str, Any]:
    manifest = build_policy_manifest(root, generated_on=generated_on)
    json_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    markdown_text = render_policy_manifest_markdown(manifest)
    _atomic_write(Path(json_path), json_text)
    _atomic_write(Path(markdown_path), markdown_text)
    return manifest


def render_policy_manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# 策略 V1 冻结清单与覆盖矩阵",
        "",
        f"- 生成日期：`{manifest['generated_on']}`",
        f"- 策略版本：`{manifest['strategy_version']}`",
        f"- 核心 manifest SHA-256：`{manifest['manifest_sha256']}`",
        f"- 冻结状态：`{manifest['freeze_status']}`",
        "- 本清单只读，不授权模拟器输入、自动点击或资源消耗。",
        "",
        "## 默认策略",
        "",
        "| 来源 | 品质 | 策略 | DP | 资源校准 |",
        "|---|---|---|---:|---|",
    ]
    for row in manifest["default_strategies"]:
        lines.append(
            f"| `{row['item_source']}` | `{row['rank']}` | `{row['policy_name']}` | "
            f"{'是' if row['enable_dp_assist'] else '否'} | `{row['resource_calibration_status']}` |"
        )
    lines.extend(
        [
            "",
            "## 决策路由",
            "",
            "| 来源 | 品质 | 节点 | 分段 | 所有者 | 内部规则 |",
            "|---|---|---:|---|---|---|",
        ]
    )
    for row in manifest["decision_routes"]:
        lines.append(
            f"| `{row['item_source']}` | `{row['rank']}` | +{row['checkpoint']} | "
            f"`{row['segment']}` | `{row['owner']}` | "
            f"`{row.get('policy_detail_ref') or '-'}` |"
        )
    details = manifest["policy_details"]["epic_non_speed_early_stop"]
    lines.extend(
        [
            "",
            "## Epic 非速度 +0/+3 内部规则",
            "",
            f"- 候选：`{details['candidate_key']}`；规则版本：`{details['rule_version']}`。",
            "- 范围：`normal_85 Epic`、85 级、非鞋、初速 `<2`、`+0/+3`。未知套装在候选评估前拒绝。",
            "- 只有当前有效 GS、有效词条数、终局概率和转换 GS 改善四项条件同时满足时才新增停止；基础策略已停止时保持停止。",
            "",
            "| 分组 | 类别 | +0 有效 GS 上限 | +3 有效 GS 上限 |",
            "|---|---|---:|---:|",
        ]
    )
    for row in details["threshold_groups"]:
        categories = "、".join(row["display_categories"])
        lines.append(
            f"| `{row['system_group']}` | `{categories}` | "
            f"{row['effective_gs_max']['0']:g} | {row['effective_gs_max']['3']:g} |"
        )
    activation = details["activation"]
    lines.extend(
        [
            "",
            f"- 有效词条数上限：`{activation['current_valid_substat_count_max']}`。",
            f"- 终局概率上限：`+0={activation['terminal_reach_probability_max']['0']}`、"
            f"`+3={activation['terminal_reach_probability_max']['3']}`。",
            f"- 转换 GS 改善上限：`{activation['conversion_max_gs_gain_max']}`。",
            "",
            "## 完整回归矩阵证据",
            "",
            f"- 状态：`{manifest['regression_evidence']['status']}`。",
            f"- 路径：`{manifest['regression_evidence']['path']}`。",
        ]
    )
    if manifest["regression_evidence"].get("sha256"):
        lines.append(f"- 文件 SHA-256：`{manifest['regression_evidence']['sha256']}`。")
    if manifest["regression_evidence"].get("tests_run") is not None:
        lines.append(
            f"- 测试文件：`{manifest['regression_evidence']['test_files']}`；"
            f"测试数：`{manifest['regression_evidence']['tests_run']}`；"
            f"覆盖要求：`{manifest['regression_evidence']['requirements_passed']}`。"
        )
    for reason in manifest["regression_evidence"].get("reasons", []):
        lines.append(f"- 拒绝原因：`{reason}`。")
    lines.extend(["", "## 冻结闸门", ""])
    for name, passed in manifest["readiness"]["gates"].items():
        lines.append(f"- `{name}`：`{'passed' if passed else 'failed'}`")
    lines.extend(["", "## 未满足项", ""])
    if manifest["readiness"]["gaps"]:
        lines.extend(f"- `{gap}`" for gap in manifest["readiness"]["gaps"])
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 行为输入",
            "",
            "| 文件 | 字节 | SHA-256 |",
            "|---|---:|---|",
        ]
    )
    for row in manifest["behavior_inputs"]:
        lines.append(f"| `{row['path']}` | {row['bytes']} | `{row['sha256']}` |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="导出策略 V1 冻结清单与覆盖矩阵")
    parser.add_argument("--root", type=Path, default=repository_root)
    parser.add_argument("--json", type=Path, default=repository_root / "reports" / "policy_v1_manifest_20260725.json")
    parser.add_argument("--markdown", type=Path, default=repository_root / "reports" / "policy_v1_manifest_20260725.md")
    parser.add_argument("--generated-on", default=date.today().isoformat())
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = write_policy_manifest(
            args.root,
            json_path=args.json,
            markdown_path=args.markdown,
            generated_on=args.generated_on,
        )
    except (OSError, PolicyManifestError, ValueError) as exc:
        parser.error(str(exc))
    print(args.json)
    print(args.markdown)
    print(f"freeze_status={manifest['freeze_status']}")
    print(f"manifest_sha256={manifest['manifest_sha256']}")
    return 2 if args.require_ready and manifest["freeze_status"] != "ready" else 0


def _behavior_input_hashes(root: Path) -> list[dict[str, Any]]:
    rows = []
    for relative_path in sorted(BEHAVIOR_INPUTS):
        path = root / relative_path
        if not path.is_file():
            raise PolicyManifestError(f"Missing behavior input: {relative_path}")
        content = path.read_bytes()
        rows.append(
            {
                "path": relative_path.replace("\\", "/"),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows


def _item_source_rank_rows() -> list[dict[str, str]]:
    return [
        {"item_source": item_source, "rank": rank}
        for item_source, ranks in sorted(ALLOWED_RANKS_BY_ITEM_SOURCE.items())
        for rank in sorted(ranks)
    ]


def _default_strategy_rows(item_source_ranks: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for scope in item_source_ranks:
        strategy = default_strategy_for(
            scope["item_source"],
            scope["rank"],
            DEFAULT_GEAR_SOURCE,
        )
        rows.append(
            {
                "item_source": scope["item_source"],
                "rank": scope["rank"],
                "gear_source": strategy.gear_source,
                "policy_name": strategy.policy_name,
                "enable_dp_assist": strategy.enable_dp_assist,
                "resource_calibration_status": strategy.resource_calibration_status,
            }
        )
    return rows


def _decision_routes(item_source_ranks: list[dict[str, str]]) -> list[dict[str, Any]]:
    routes = []
    for scope in item_source_ranks:
        item_source = scope["item_source"]
        rank = scope["rank"]
        for checkpoint in sorted(SUPPORTED_ENHANCEMENT_CHECKPOINTS):
            if checkpoint == 15:
                routes.append(_route(item_source, rank, checkpoint, "all", "terminal_summary"))
            elif checkpoint in (0, 3):
                detail_ref = (
                    "epic_non_speed_early_stop"
                    if item_source == "normal_85" and rank == "Epic"
                    else None
                )
                routes.append(
                    _route(
                        item_source,
                        rank,
                        checkpoint,
                        "all",
                        "lightweight_prediction",
                        policy_detail_ref=detail_ref,
                    )
                )
            elif item_source == "normal_85" and rank == "Heroic":
                routes.append(_route(item_source, rank, checkpoint, "non_boot_with_speed", "heroic_speed22_rescue"))
                routes.append(_route(item_source, rank, checkpoint, "fallback", "baseline_policy"))
            else:
                routes.append(_route(item_source, rank, checkpoint, "all", "exact_dp"))
    return routes


def _route(
    item_source: str,
    rank: str,
    checkpoint: int,
    segment: str,
    owner: str,
    *,
    policy_detail_ref: str | None = None,
) -> dict[str, Any]:
    route = {
        "item_source": item_source,
        "rank": rank,
        "checkpoint": checkpoint,
        "segment": segment,
        "owner": owner,
        "output_contract": "summary.recommendation + summary.next_check_at",
    }
    if policy_detail_ref is not None:
        route["policy_detail_ref"] = policy_detail_ref
    return route


def _route_coverage_complete(item_source_ranks: list[dict[str, str]], routes: list[dict[str, Any]]) -> bool:
    route_keys = {
        (row["item_source"], row["rank"], row["checkpoint"], row["segment"])
        for row in routes
    }
    if len(route_keys) != len(routes):
        return False
    return all(
        any(
            row["item_source"] == scope["item_source"]
            and row["rank"] == scope["rank"]
            and row["checkpoint"] == checkpoint
            for row in routes
        )
        for scope in item_source_ranks
        for checkpoint in SUPPORTED_ENHANCEMENT_CHECKPOINTS
    )


def _epic_early_stop_details() -> dict[str, Any]:
    from .epic_early_stop import (
        CANDIDATE_KEY,
        CATEGORY_SYSTEM_GROUPS,
        CONVERSION_VALUE_MAX,
        CURRENT_VALID_MAX,
        DEFAULT_THRESHOLDS,
        RULE_VERSION,
        SYSTEM_THRESHOLDS,
        TERMINAL_PROBABILITY_MAX,
    )

    grouped_categories = {
        group: [category for category, mapped_group in CATEGORY_SYSTEM_GROUPS.items() if mapped_group == group]
        for group in ("pure_output", "pure_tank")
    }
    default_categories = [
        category
        for category, group in CATEGORY_SYSTEM_GROUPS.items()
        if group not in SYSTEM_THRESHOLDS
    ]
    threshold_groups = [
        {
            "system_group": "pure_output",
            "categories": grouped_categories["pure_output"],
            "display_categories": grouped_categories["pure_output"],
            "effective_gs_max": {str(node): float(value) for node, value in sorted(SYSTEM_THRESHOLDS["pure_output"].items())},
        },
        {
            "system_group": "pure_tank",
            "categories": grouped_categories["pure_tank"],
            "display_categories": grouped_categories["pure_tank"],
            "effective_gs_max": {str(node): float(value) for node, value in sorted(SYSTEM_THRESHOLDS["pure_tank"].items())},
        },
        {
            "system_group": "default",
            "categories": [*default_categories, "unknown_candidate"],
            "display_categories": [*default_categories, "未知候选分组"],
            "effective_gs_max": {str(node): float(value) for node, value in sorted(DEFAULT_THRESHOLDS.items())},
        },
    ]
    return {
        "candidate_key": CANDIDATE_KEY,
        "rule_version": RULE_VERSION,
        "scope": {
            "item_source": "normal_85",
            "rank": "Epic",
            "equipment_level": 85,
            "checkpoints": [0, 3],
            "excluded_slots": ["boot"],
            "initial_speed": "lt_2",
        },
        "threshold_groups": threshold_groups,
        "activation": {
            "require_all": True,
            "effective_gs_max": "threshold_groups[].effective_gs_max",
            "current_valid_substat_count_max": CURRENT_VALID_MAX,
            "terminal_reach_probability_max": {
                str(node): value for node, value in sorted(TERMINAL_PROBABILITY_MAX.items())
            },
            "conversion_max_gs_gain_max": CONVERSION_VALUE_MAX,
            "baseline_stop_preserved": True,
        },
        "unknown_candidate_group_contract": "uses_default_threshold_only_after_known_set_validation",
        "unknown_set_contract": "rejected_before_candidate_evaluation",
    }


def build_regression_evidence(
    root: Path,
    *,
    test_runs: Sequence[dict[str, Any]],
    generated_on: str | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    normalized_runs = sorted(
        (
            {
                "path": str(row["path"]).replace("\\", "/"),
                "commands": [list(command) for command in row["commands"]],
                "exit_code": int(row["exit_code"]),
                "tests_run": int(row["tests_run"]),
                "duration_seconds": round(float(row["duration_seconds"]), 3),
                "output_sha256": str(row["output_sha256"]),
            }
            for row in test_runs
        ),
        key=lambda row: row["path"],
    )
    run_by_path = {row["path"]: row for row in normalized_runs}
    coverage_requirements = []
    for requirement in REGRESSION_REQUIREMENTS:
        references_exist = all(_test_reference_exists(root, test_id) for test_id in requirement["test_ids"])
        referenced_paths = {test_id.split("::", 1)[0] for test_id in requirement["test_ids"]}
        tests_passed = all(
            path in run_by_path
            and run_by_path[path]["exit_code"] == 0
            and run_by_path[path]["tests_run"] > 0
            for path in referenced_paths
        )
        coverage_requirements.append(
            {
                "id": requirement["id"],
                "test_ids": list(requirement["test_ids"]),
                "passed": references_exist and tests_passed,
            }
        )

    expected_paths = sorted(REGRESSION_TEST_INPUTS)
    complete_test_run_set = sorted(run_by_path) == expected_paths
    all_test_runs_passed = complete_test_run_set and all(
        row["exit_code"] == 0 and row["tests_run"] > 0 for row in normalized_runs
    )
    all_requirements_passed = all(row["passed"] for row in coverage_requirements)
    status = "passed" if all_test_runs_passed and all_requirements_passed else "failed"
    core = {
        "schema_version": REGRESSION_EVIDENCE_SCHEMA,
        "strategy_version": STRATEGY_VERSION,
        "status": status,
        "scope": "policy_v1_required_regression_matrix",
        "behavior_inputs": _behavior_input_hashes(root),
        "test_inputs": _file_hash_rows(root, REGRESSION_TEST_INPUTS),
        "execution_inputs": _file_hash_rows(root, REGRESSION_EXECUTION_INPUTS),
        "coverage_dimensions": REGRESSION_DIMENSIONS,
        "coverage_requirements": coverage_requirements,
        "test_runs": normalized_runs,
        "summary": {
            "test_files": len(normalized_runs),
            "tests_run": sum(row["tests_run"] for row in normalized_runs),
            "requirements_passed": sum(row["passed"] for row in coverage_requirements),
            "requirements_total": len(coverage_requirements),
            "all_test_runs_passed": all_test_runs_passed,
            "all_requirements_passed": all_requirements_passed,
        },
    }
    return {
        "schema_version": REGRESSION_EVIDENCE_SCHEMA,
        "generated_on": generated_on or date.today().isoformat(),
        "evidence_sha256": _json_sha256(core),
        **{key: value for key, value in core.items() if key != "schema_version"},
    }


def write_regression_evidence(
    root: Path,
    *,
    test_runs: Sequence[dict[str, Any]],
    json_path: Path,
    generated_on: str | None = None,
) -> dict[str, Any]:
    evidence = build_regression_evidence(root, test_runs=test_runs, generated_on=generated_on)
    _atomic_write(Path(json_path), json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    return evidence


def _regression_evidence_attachment(
    root: Path,
    behavior_inputs: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    relative_path = REGRESSION_EVIDENCE_PATH
    path = root / relative_path
    if not path.is_file():
        return False, {"path": relative_path, "status": "missing", "reasons": ["evidence_file_missing"]}

    raw = path.read_bytes()
    try:
        evidence = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False, {
            "path": relative_path,
            "status": "invalid",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "reasons": ["evidence_json_invalid"],
        }
    if not isinstance(evidence, dict):
        return False, {
            "path": relative_path,
            "status": "invalid",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "reasons": ["evidence_root_not_object"],
        }

    reasons = []
    core = {key: value for key, value in evidence.items() if key not in {"generated_on", "evidence_sha256"}}
    if evidence.get("schema_version") != REGRESSION_EVIDENCE_SCHEMA:
        reasons.append("evidence_schema_mismatch")
    if evidence.get("strategy_version") != STRATEGY_VERSION:
        reasons.append("evidence_strategy_version_mismatch")
    if evidence.get("evidence_sha256") != _json_sha256(core):
        reasons.append("evidence_core_hash_mismatch")
    if evidence.get("status") != "passed":
        reasons.append("evidence_status_not_passed")
    if evidence.get("behavior_inputs") != behavior_inputs:
        reasons.append("evidence_behavior_input_hash_mismatch")
    try:
        expected_test_inputs = _file_hash_rows(root, REGRESSION_TEST_INPUTS)
        expected_execution_inputs = _file_hash_rows(root, REGRESSION_EXECUTION_INPUTS)
    except PolicyManifestError:
        reasons.append("evidence_input_missing")
        expected_test_inputs = None
        expected_execution_inputs = None
    if evidence.get("test_inputs") != expected_test_inputs:
        reasons.append("evidence_test_input_hash_mismatch")
    if evidence.get("execution_inputs") != expected_execution_inputs:
        reasons.append("evidence_execution_input_hash_mismatch")
    if evidence.get("coverage_dimensions") != REGRESSION_DIMENSIONS:
        reasons.append("evidence_coverage_dimensions_mismatch")

    expected_requirements = [
        {"id": row["id"], "test_ids": list(row["test_ids"]), "passed": True}
        for row in REGRESSION_REQUIREMENTS
    ]
    if evidence.get("coverage_requirements") != expected_requirements:
        reasons.append("evidence_coverage_requirements_incomplete")
    test_runs = evidence.get("test_runs") or []
    if not isinstance(test_runs, list) or not all(isinstance(row, dict) for row in test_runs):
        reasons.append("evidence_test_runs_invalid")
    elif sorted(row.get("path") or "" for row in test_runs) != sorted(REGRESSION_TEST_INPUTS):
        reasons.append("evidence_test_run_set_mismatch")
    elif any(row.get("exit_code") != 0 or int(row.get("tests_run") or 0) <= 0 for row in test_runs):
        reasons.append("evidence_test_run_failed")

    summary = evidence.get("summary") or {}
    if not isinstance(summary, dict):
        reasons.append("evidence_summary_invalid")
        summary = {}
    elif not summary.get("all_test_runs_passed") or not summary.get("all_requirements_passed"):
        reasons.append("evidence_summary_not_passed")
    attachment = {
        "path": relative_path,
        "status": "attached_verified" if not reasons else "invalid",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "evidence_sha256": evidence.get("evidence_sha256"),
        "generated_on": evidence.get("generated_on"),
        "test_files": summary.get("test_files"),
        "tests_run": summary.get("tests_run"),
        "requirements_passed": summary.get("requirements_passed"),
        "requirements_total": summary.get("requirements_total"),
    }
    if reasons:
        attachment["reasons"] = sorted(set(reasons))
    return not reasons, attachment


def _file_hash_rows(root: Path, relative_paths: Sequence[str]) -> list[dict[str, Any]]:
    rows = []
    for relative_path in sorted(relative_paths):
        path = root / relative_path
        if not path.is_file():
            raise PolicyManifestError(f"Missing evidence input: {relative_path}")
        content = path.read_bytes()
        rows.append(
            {
                "path": relative_path.replace("\\", "/"),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows


def _test_reference_exists(root: Path, test_id: str) -> bool:
    parts = test_id.split("::")
    if len(parts) != 3:
        return False
    relative_path, class_name, method_name = parts
    path = root / relative_path
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return False
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name
                for child in node.body
            )
    return False


def _unknown_set_fail_closed() -> bool:
    from .enhance_policy import advise_gear

    unknown_set_gear = Gear(
        set="set_policy_manifest_unknown",
        slot="weapon",
        main_stat=Stat("atkFlat", 500),
        enhance=15,
        level=85,
        rank="Epic",
        substats=[
            Stat("hpPct", 8),
            Stat("spd", 4),
            Stat("crit", 5),
            Stat("cdmg", 7),
        ],
    )
    try:
        advise_gear(unknown_set_gear, item_source="normal_85")
    except ValueError:
        return True
    return False


def _json_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
