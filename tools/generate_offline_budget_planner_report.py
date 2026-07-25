"""Generate deterministic public validation evidence for the offline budget planner."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.e7_enhance.offline_budget_planner import BudgetPlanningRequest, plan_budget
from src.e7_enhance.resource_model import (
    LOWER_ENHANCE_STONE_EXP,
    LOWER_ENHANCE_STONE_USE_GOLD,
    POWDER_EXP,
    POWDER_GOLD,
    UPPER_ENHANCE_STONE_EXP,
    UPPER_ENHANCE_STONE_USE_GOLD,
)
from tools.offline_budget_planner_validation_support import (
    canonical_request_json,
    independent_boundary_values,
    success_result_violations,
)


MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "high"
VALIDATION_DATE = "2026-07-25"


def _common_request(current: int, target: int) -> dict[str, Any]:
    return {
        "material_pool": "common",
        "rarity": "Epic",
        "current_checkpoint": current,
        "target_checkpoint": target,
        "allowed_materials": ["powder", "lower_enhance_stone", "upper_enhance_stone"],
        "inventory": {"powder": 1000, "lower_enhance_stone": 100, "upper_enhance_stone": 100},
        "material_priority": ["upper_enhance_stone", "lower_enhance_stone", "powder"],
    }


def _accessory_request(current: int, target: int) -> dict[str, Any]:
    return {
        "material_pool": "accessory",
        "rarity": "Epic",
        "current_checkpoint": current,
        "target_checkpoint": target,
        "allowed_materials": ["accessory_powder", "accessory_lower_enhance_stone", "accessory_upper_enhance_stone"],
        "inventory": {"accessory_powder": 1000, "accessory_lower_enhance_stone": 100, "accessory_upper_enhance_stone": 100},
        "material_priority": ["accessory_upper_enhance_stone", "accessory_lower_enhance_stone", "accessory_powder"],
    }


def _limits_from_result(result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            str(segment.to_checkpoint): {
                "materials": dict(segment.materials),
                "gold": segment.gold,
            }
            for segment in result.segments
        },
        {
            "materials": dict(result.cumulative_expected_consumption.materials),
            "gold": result.cumulative_expected_consumption.gold,
        },
    )


def _five_segment_bounded_matrix(reference_request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    proposal = plan_budget(BudgetPlanningRequest.from_dict(reference_request))
    assert proposal.success and proposal.mode == "proposal_only"
    base_segments, base_cumulative = _limits_from_result(proposal)
    base_inventory = {
        material: quantity + 1 for material, quantity in base_cumulative["materials"].items()
    }
    outcomes = []
    violations = []
    boundary_catalog = []
    raw_label_candidate_count = 0
    local_alias_count = 0
    dimension_stats: dict[str, dict[str, int]] = {}
    unique_requests: dict[str, dict[str, Any]] = {}

    def run_case(
        dimension: str,
        scope: str,
        boundary: Any,
        material: str,
        inventory: dict[str, int],
        segment_limits: dict[str, Any],
        cumulative_limit: dict[str, Any],
    ) -> None:
        request = {
            **reference_request,
            "inventory": inventory,
            "segment_hard_limits": segment_limits,
            "cumulative_hard_limits": cumulative_limit,
        }
        result = plan_budget(BudgetPlanningRequest.from_dict(request))
        case = {
            "dimension": dimension,
            "scope": scope,
            "material": material,
            "boundary": boundary.primary_label,
            "aliases": list(boundary.aliases),
            "value": boundary.value,
            "planner_success": result.success,
            "failure_code": result.failure_code,
        }
        canonical_request = canonical_request_json(request)
        request_sha256 = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        coverage_case_index = len(outcomes)
        case["request_sha256"] = request_sha256
        stats = dimension_stats.setdefault(
            dimension,
            {
                "coverage_case_count": 0,
                "coverage_success_count": 0,
                "coverage_fail_closed_count": 0,
                "violation_case_count": 0,
                "invariant_violation_count": 0,
            },
        )
        stats["coverage_case_count"] += 1
        case_violations = (
            success_result_violations(result, request) if result.success else ()
        )
        outcome_signature = json.dumps(
            {
                "planner_result": result.to_dict(),
                "violations": list(case_violations),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        unique_record = unique_requests.get(canonical_request)
        if unique_record is None:
            status = (
                "success"
                if result.success and not case_violations
                else "violation"
                if case_violations
                else "fail_closed"
            )
            unique_record = {
                "canonical_request": json.loads(canonical_request),
                "request_sha256": request_sha256,
                "first_coverage_case_index": coverage_case_index,
                "coverage_case_count": 1,
                "status": status,
                "planner_success": result.success,
                "failure_code": result.failure_code,
                "violations": list(case_violations),
                "_outcome_signature": outcome_signature,
            }
            unique_requests[canonical_request] = unique_record
        else:
            unique_record["coverage_case_count"] += 1
            case["duplicate_request"] = True
            if unique_record["_outcome_signature"] != outcome_signature:
                case_violations = tuple(case_violations) + ("duplicate_request_result_mismatch",)
                unique_record["status"] = "violation"
                unique_record["violations"].append("duplicate_request_result_mismatch")
        case["global_unique_request_index"] = list(unique_requests).index(canonical_request)
        case["success"] = result.success and not case_violations
        case["violations"] = list(case_violations)
        outcomes.append(case)
        if not result.success:
            stats["coverage_fail_closed_count"] += 1
            assert result.mode == "not_planned" and result.failure_code
        if case_violations:
            stats["violation_case_count"] += 1
            stats["invariant_violation_count"] += len(case_violations)
            violations.extend({**case, "violation": violation} for violation in case_violations)
        elif result.success:
            stats["coverage_success_count"] += 1

    def boundaries_for(dimension: str, scope: str, material: str, planned: int) -> tuple[Any, ...]:
        nonlocal raw_label_candidate_count, local_alias_count
        boundaries = independent_boundary_values(planned)
        boundary_catalog.append(
            {
                "dimension": dimension,
                "scope": scope,
                "material": material,
                "planned_value": planned,
                "independent_inputs": [boundary.to_dict() for boundary in boundaries],
            }
        )
        raw_label_candidate_count += sum(1 + len(boundary.aliases) for boundary in boundaries)
        local_alias_count += sum(len(boundary.aliases) for boundary in boundaries)
        return boundaries

    for segment in proposal.segments:
        endpoint = str(segment.to_checkpoint)
        for material in reference_request["allowed_materials"]:
            dimension = "segment_material_hard_limit"
            scope = f"to_checkpoint_{endpoint}"
            for boundary in boundaries_for(dimension, scope, material, segment.materials[material]):
                segment_limits = json.loads(json.dumps(base_segments))
                segment_limits[endpoint]["materials"][material] = boundary.value
                run_case(
                    dimension,
                    scope,
                    boundary,
                    material,
                    dict(base_inventory),
                    segment_limits,
                    json.loads(json.dumps(base_cumulative)),
                )

    for material in reference_request["allowed_materials"]:
        dimension = "cumulative_material_hard_limit"
        scope = "full_route_0_to_15"
        for boundary in boundaries_for(dimension, scope, material, base_cumulative["materials"][material]):
            cumulative_limit = json.loads(json.dumps(base_cumulative))
            cumulative_limit["materials"][material] = boundary.value
            run_case(
                dimension,
                scope,
                boundary,
                material,
                dict(base_inventory),
                json.loads(json.dumps(base_segments)),
                cumulative_limit,
            )

    for material in reference_request["allowed_materials"]:
        dimension = "inventory_material"
        scope = "full_route_0_to_15"
        for boundary in boundaries_for(dimension, scope, material, base_cumulative["materials"][material]):
            inventory = dict(base_inventory)
            inventory[material] = boundary.value
            run_case(
                dimension,
                scope,
                boundary,
                material,
                inventory,
                json.loads(json.dumps(base_segments)),
                json.loads(json.dumps(base_cumulative)),
            )

    assert raw_label_candidate_count == len(outcomes) + local_alias_count
    assert not violations
    canonical_outcomes = json.dumps(outcomes, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    global_unique_request_catalog = []
    for record in unique_requests.values():
        global_unique_request_catalog.append(
            {key: value for key, value in record.items() if not key.startswith("_")}
        )
    coverage_success_count = sum(1 for outcome in outcomes if outcome["success"])
    coverage_fail_closed_count = sum(1 for outcome in outcomes if not outcome["planner_success"])
    coverage_violation_case_count = sum(
        1 for outcome in outcomes if outcome["planner_success"] and not outcome["success"]
    )
    unique_success_count = sum(record["status"] == "success" for record in global_unique_request_catalog)
    unique_fail_closed_count = sum(record["status"] == "fail_closed" for record in global_unique_request_catalog)
    unique_violation_case_count = sum(record["status"] == "violation" for record in global_unique_request_catalog)
    assert coverage_success_count + coverage_fail_closed_count + coverage_violation_case_count == len(outcomes)
    assert unique_success_count + unique_fail_closed_count + unique_violation_case_count == len(global_unique_request_catalog)
    summary = {
        "coverage_dimensions": dimension_stats,
        "boundary_catalog": boundary_catalog,
        "raw_label_candidate_count": raw_label_candidate_count,
        "local_alias_count": local_alias_count,
        "coverage_case_count": len(outcomes),
        "global_unique_request_count": len(global_unique_request_catalog),
        "duplicate_request_case_count": len(outcomes) - len(global_unique_request_catalog),
        "coverage_results": {
            "success_count": coverage_success_count,
            "fail_closed_count": coverage_fail_closed_count,
            "violation_case_count": coverage_violation_case_count,
            "invariant_violation_count": len(violations),
        },
        "unique_request_results": {
            "success_count": unique_success_count,
            "fail_closed_count": unique_fail_closed_count,
            "violation_case_count": unique_violation_case_count,
        },
        "global_unique_request_catalog": global_unique_request_catalog,
        "coverage_case_catalog": outcomes,
        "coverage_axes": {
            "segment_endpoints": [3, 6, 9, 12, 15],
            "materials": list(reference_request["allowed_materials"]),
            "boundary_labels": ["zero", "planned_minus_one", "planned", "planned_plus_one"],
        },
        "invariant_violation_count": len(violations),
        "outcomes_sha256": hashlib.sha256(canonical_outcomes.encode("utf-8")).hexdigest(),
    }
    exact_request = {
        **reference_request,
        "inventory": dict(base_cumulative["materials"]),
        "segment_hard_limits": base_segments,
        "cumulative_hard_limits": base_cumulative,
    }
    exact = plan_budget(BudgetPlanningRequest.from_dict(exact_request))
    assert exact.success and exact.mode == "validated_against_hard_limits"
    return proposal.to_dict(), exact.to_dict(), summary


def build_validation_payload() -> dict[str, Any]:
    intervals = ((0, 3), (3, 6), (6, 9), (9, 12), (12, 15))
    common = []
    accessory = []
    for current, target in intervals:
        common_result = plan_budget(BudgetPlanningRequest.from_dict(_common_request(current, target)))
        accessory_result = plan_budget(BudgetPlanningRequest.from_dict(_accessory_request(current, target)))
        assert common_result.success
        assert accessory_result.success
        common.append(common_result.to_dict())
        accessory.append(accessory_result.to_dict())
    five_segment_proposal, five_segment_validated, bounded_matrix = _five_segment_bounded_matrix(
        _common_request(0, 15)
    )
    accessory_five_segment_proposal, accessory_five_segment_validated, accessory_bounded_matrix = (
        _five_segment_bounded_matrix(_accessory_request(0, 15))
    )
    return {
        "report_type": "offline_budget_planner_validation",
        "validation_date": VALIDATION_DATE,
        "implementation_model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "rules_version": common[0]["rules_version"],
        "public_evidence": {
            "common_materials": {
                "powder": {"base_experience": POWDER_EXP, "gold_per_unit": POWDER_GOLD},
                "lower_enhance_stone": {
                    "base_experience": LOWER_ENHANCE_STONE_EXP,
                    "gold_per_unit": LOWER_ENHANCE_STONE_USE_GOLD,
                },
                "upper_enhance_stone": {
                    "base_experience": UPPER_ENHANCE_STONE_EXP,
                    "gold_per_unit": UPPER_ENHANCE_STONE_USE_GOLD,
                },
                "source": "src/e7_enhance/resource_model.py",
                "planning_interpretation": "floor(base_experience * 1166 / 1000) reaches each checkpoint requirement",
            },
            "checkpoint_requirements": {
                "source": "src/e7_enhance/resource_model.py RED_LEVEL_EXP/PURPLE_LEVEL_EXP",
                "scope": "published per-level requirements aggregated only across standard adjacent checkpoints",
            },
        },
        "fail_closed_gaps": [
            "cross-pool material identifiers, inventory keys, and hard-limit keys are rejected",
            "unknown or unsupported material identifiers are rejected",
            "Good/Great remains a resource-model expectation layer, not an execution input",
        ],
        "objective_order": common[0]["objective_order"],
        "common_adjacent_checkpoint_results": common,
        "accessory_adjacent_checkpoint_results": accessory,
        "five_segment_reference_proposal": five_segment_proposal,
        "five_segment_exact_limit_result": five_segment_validated,
        "five_segment_bounded_matrix": bounded_matrix,
        "accessory_five_segment_reference_proposal": accessory_five_segment_proposal,
        "accessory_five_segment_exact_limit_result": accessory_five_segment_validated,
        "accessory_five_segment_bounded_matrix": accessory_bounded_matrix,
        "operation_authorization": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 自动预算与硬上限离线规划器验证报告",
        "",
        f"- 验证日期：`{payload['validation_date']}`",
        f"- 实际模型：`{payload['implementation_model']}`",
        f"- Reasoning effort：`{payload['reasoning_effort']}`",
        f"- 规则版本：`{payload['rules_version']}`",
        "- 范围：纯 Python 离线整数规划；未读取私人数据，未接触 GUI、OCR、ADB、MuMu 或游戏资源。",
        "- 操作授权：`false`。本报告不构成材料选择、资源消耗或点击授权。",
        "",
        "## 可证明输入",
        "",
        f"- 普通材料：粉末 `{payload['public_evidence']['common_materials']['powder']['base_experience']}` 基础经验、"
        f"`{payload['public_evidence']['common_materials']['powder']['gold_per_unit']}` 金币；下级强化石 "
        f"`{payload['public_evidence']['common_materials']['lower_enhance_stone']['base_experience']}` 基础经验、"
        f"`{payload['public_evidence']['common_materials']['lower_enhance_stone']['gold_per_unit']}` 金币；上级强化石 "
        f"`{payload['public_evidence']['common_materials']['upper_enhance_stone']['base_experience']}` 基础经验、"
        f"`{payload['public_evidence']['common_materials']['upper_enhance_stone']['gold_per_unit']}` 金币。",
        "- 节点需求：仅聚合已跟踪 `RED_LEVEL_EXP` / `PURPLE_LEVEL_EXP` 的标准相邻节点。",
        "- 成功计划按 `floor(基础经验 * 1166 / 1000)` 保证足额；Good/Great 仅属于资源模型期望层。",
        "",
        "## 相邻节点验证",
        "",
        "| 材料池 | 节点 | 结果 | 说明 |",
        "|---|---|---|---|",
    ]
    for result in payload["common_adjacent_checkpoint_results"]:
        segment = result["segments"][0]
        lines.append(
            f"| common | +{segment['from_checkpoint']} -> +{segment['to_checkpoint']} | success | "
            f"需求 {segment['required_experience']}，基础 {segment['provided_base_experience']}，页面 {segment['provided_page_effective_experience']}，"
            f"页面溢出 {segment['page_effective_experience_overflow']}，计划金币 {segment['gold']} |"
        )
    for result in payload["accessory_adjacent_checkpoint_results"]:
        segment = result["segments"][0]
        lines.append(
            f"| accessory | +{segment['from_checkpoint']} -> +{segment['to_checkpoint']} | success | "
            f"需求 {segment['required_experience']}，基础 {segment['provided_base_experience']}，页面 {segment['provided_page_effective_experience']}，"
            f"页面溢出 {segment['page_effective_experience_overflow']}，计划金币 {segment['gold']} |"
        )
    matrix = payload["five_segment_bounded_matrix"]
    lines.extend(
        [
            "",
            "## 五段有界矩阵",
            "",
            f"- 覆盖案例数：`{matrix['coverage_case_count']}`；全局唯一完整请求数："
            f"`{matrix['global_unique_request_count']}`；重复请求案例数：`{matrix['duplicate_request_case_count']}`。",
            f"- 原始边界标签候选：`{matrix['raw_label_candidate_count']}`；本地 alias/duplicate："
            f"`{matrix['local_alias_count']}`（不计入覆盖案例）。",
            f"- 覆盖结果：成功 `{matrix['coverage_results']['success_count']}`；"
            f"fail closed `{matrix['coverage_results']['fail_closed_count']}`；"
            f"违规案例 `{matrix['coverage_results']['violation_case_count']}`。",
            f"- 全局唯一请求结果：成功 `{matrix['unique_request_results']['success_count']}`；"
            f"fail closed `{matrix['unique_request_results']['fail_closed_count']}`；"
            f"违规请求 `{matrix['unique_request_results']['violation_case_count']}`。",
            f"- 结果摘要 SHA-256：`{matrix['outcomes_sha256']}`。",
            "- 覆盖节点：`+3/+6/+9/+12/+15`；材料：`powder`、`lower_enhance_stone`、`upper_enhance_stone`；"
            "边界值：`0`、`计划值-1`、`计划值`、`计划值+1`（非负化）。",
            "- 边界值按实际非负整数去重；重复标签作为 `aliases` 写入 JSON 的 `boundary_catalog`，"
            "不会重复执行或计入覆盖案例，也不计为全局唯一请求。",
            "",
            "| 覆盖维度 | 覆盖案例 | 成功 | fail closed | 违规案例 | 违规项 |",
            "|---|---:|---:|---:|---:|---:|",
            *(
                f"| {dimension} | {stats['coverage_case_count']} | {stats['coverage_success_count']} | "
                f"{stats['coverage_fail_closed_count']} | {stats['violation_case_count']} | "
                f"{stats['invariant_violation_count']} |"
                for dimension, stats in sorted(matrix["coverage_dimensions"].items())
            ),
            "",
            f"- 覆盖维度合计：五段分段材料上限 `{matrix['coverage_dimensions']['segment_material_hard_limit']['coverage_case_count']}`；"
            f"累计材料上限 `{matrix['coverage_dimensions']['cumulative_material_hard_limit']['coverage_case_count']}`；"
            f"材料库存 `{matrix['coverage_dimensions']['inventory_material']['coverage_case_count']}`。",
            "- 分段/累计金币不足仍由定向测试覆盖；覆盖案例和全局唯一请求均是有界证据，不是无界证明。",
            "",
            "## 已验证不变量",
            "",
            "- 每个计为成功的矩阵结果都必须恰好包含五段，路线严格为 "
            "`0->3->6->9->12->15`，且分段端点唯一。",
            "- 每个计为成功的矩阵结果中，结果材料池与请求一致，所有材料容器键集合精确匹配允许材料，"
            "且每种材料和金币均未超过库存、分段硬上限及累计硬上限；"
            "分段汇总必须等于累计结果。",
            "- 材料组合只来自允许集合且属于正确材料池。",
            "- 目标排序固定为：最小金币、最小页面有效经验溢出、最少材料数、用户材料优先级。",
            "- 同一请求的规范化 JSON 字节级稳定。",
            "- 跨池、未知材料、库存/硬上限/预览不一致均 fail closed；上级石与饰品材料按已验证离散常量规划。",
            "- 只有完整分段与完整累计硬上限同时提供并通过时，结果模式才为 `validated_against_hard_limits`。",
            "",
            "## 阻断与风险",
            "",
            "- 饰品和普通材料池常量相同但材料 ID、库存与硬上限严格隔离；报告不验证实时库存。",
            "- 传说强化石仍不在支持范围，任何未知材料请求仍返回 fail closed。",
            "- 离线预算器不验证实时页面、真实库存或实际消耗，也不实现点击前拦截、状态机或节点后新鲜快照。",
        ]
    )
    accessory_matrix = payload["accessory_five_segment_bounded_matrix"]
    accessory_materials = ", ".join(accessory_matrix["coverage_axes"]["materials"])
    lines.extend(
        [
            "",
            "## 饰品五段有界矩阵",
            "",
            f"- 覆盖节点：`+3/+6/+9/+12/+15`；材料：`{accessory_materials}`。",
            f"- 覆盖案例：`{accessory_matrix['coverage_case_count']}`；全局唯一请求："
            f"`{accessory_matrix['global_unique_request_count']}`；重复案例："
            f"`{accessory_matrix['duplicate_request_case_count']}`。",
            f"- 覆盖结果：成功 `{accessory_matrix['coverage_results']['success_count']}`；"
            f"fail closed `{accessory_matrix['coverage_results']['fail_closed_count']}`；"
            f"违规 `{accessory_matrix['coverage_results']['violation_case_count']}`。",
            "| 覆盖维度 | 覆盖案例 | 成功 | fail closed | 违规案例 | 违规项 |",
            "|---|---:|---:|---:|---:|---:|",
            *(
                f"| {dimension} | {stats['coverage_case_count']} | {stats['coverage_success_count']} | "
                f"{stats['coverage_fail_closed_count']} | {stats['violation_case_count']} | "
                f"{stats['invariant_violation_count']} |"
                for dimension, stats in sorted(accessory_matrix["coverage_dimensions"].items())
            ),
            f"- 分段材料硬上限 `{accessory_matrix['coverage_dimensions']['segment_material_hard_limit']['coverage_case_count']}`；"
            f"累计材料硬上限 `{accessory_matrix['coverage_dimensions']['cumulative_material_hard_limit']['coverage_case_count']}`；"
            f"库存 `{accessory_matrix['coverage_dimensions']['inventory_material']['coverage_case_count']}`。",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate offline budget planner validation evidence")
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    args = parser.parse_args(argv)
    payload = build_validation_payload()
    json_path = Path(args.json_output)
    markdown_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
