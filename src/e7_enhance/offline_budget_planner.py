"""Deterministic, offline integer material plans for enhancement checkpoints.

This module deliberately does not reuse the expected-value material quantities
from :mod:`resource_model`.  It only imports the published per-level experience
requirements and uses a conservative base-experience threshold, so a successful
plan is an integer plan that is sufficient even without Good/Great or pet bonus.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from math import ceil
from typing import Any, Mapping, Sequence

from .resource_model import (
    CHECKPOINTS,
    LOWER_ENHANCE_STONE_EXP,
    LOWER_ENHANCE_STONE_USE_GOLD,
    POWDER_EXP,
    POWDER_GOLD,
    PURPLE_LEVEL_EXP,
    RED_LEVEL_EXP,
)


RULES_VERSION = "offline_budget_planner/v1"
OBJECTIVE_ORDER = (
    "minimum_gold",
    "minimum_base_experience_overflow",
    "minimum_material_count",
    "material_priority",
)


@dataclass(frozen=True)
class MaterialDefinition:
    material_id: str
    material_pool: str
    base_experience: int | None
    gold_per_unit: int | None
    support_status: str
    reason: str | None = None


MATERIALS: dict[str, MaterialDefinition] = {
    "powder": MaterialDefinition("powder", "common", POWDER_EXP, POWDER_GOLD, "supported"),
    "lower_enhance_stone": MaterialDefinition(
        "lower_enhance_stone",
        "common",
        LOWER_ENHANCE_STONE_EXP,
        LOWER_ENHANCE_STONE_USE_GOLD,
        "supported",
    ),
    "upper_enhance_stone": MaterialDefinition(
        "upper_enhance_stone",
        "common",
        None,
        None,
        "unsupported",
        "no published discrete experience and gold model",
    ),
    "accessory_powder": MaterialDefinition(
        "accessory_powder",
        "accessory",
        None,
        None,
        "unsupported",
        "no publicly tracked discrete accessory material model",
    ),
    "accessory_lower_enhance_stone": MaterialDefinition(
        "accessory_lower_enhance_stone",
        "accessory",
        None,
        None,
        "unsupported",
        "no publicly tracked discrete accessory material model",
    ),
    "accessory_upper_enhance_stone": MaterialDefinition(
        "accessory_upper_enhance_stone",
        "accessory",
        None,
        None,
        "unsupported",
        "no published discrete accessory material model",
    ),
}


@dataclass(frozen=True)
class HardLimits:
    materials: tuple[tuple[str, Any], ...]
    gold: Any

    @classmethod
    def from_dict(cls, payload: Any) -> "HardLimits":
        if not isinstance(payload, Mapping):
            return cls(materials=(("__invalid_hard_limits__", payload),), gold=None)
        materials = payload.get("materials")
        pairs = _mapping_pairs(materials) if isinstance(materials, Mapping) else (("__invalid_material_limits__", materials),)
        return cls(materials=pairs, gold=payload.get("gold"))


@dataclass(frozen=True)
class BudgetPlanningRequest:
    material_pool: Any
    rarity: Any
    current_checkpoint: Any
    target_checkpoint: Any
    allowed_materials: tuple[Any, ...]
    inventory: tuple[tuple[str, Any], ...]
    material_priority: tuple[Any, ...]
    segment_hard_limits: tuple[tuple[Any, HardLimits], ...] = ()
    cumulative_hard_limits: HardLimits | None = None
    preview_base_experience: tuple[tuple[Any, Any], ...] = ()
    segment_hard_limits_provided: bool = False
    cumulative_hard_limits_provided: bool = False
    preview_base_experience_provided: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BudgetPlanningRequest":
        segment_limits = payload.get("segment_hard_limits")
        preview = payload.get("preview_base_experience")
        allowed = payload.get("allowed_materials", ())
        priority = payload.get("material_priority", ())
        return cls(
            material_pool=payload.get("material_pool"),
            rarity=payload.get("rarity"),
            current_checkpoint=payload.get("current_checkpoint"),
            target_checkpoint=payload.get("target_checkpoint"),
            allowed_materials=tuple(allowed) if isinstance(allowed, Sequence) and not isinstance(allowed, str) else ("__invalid_allowed_materials__",),
            inventory=_mapping_pairs(payload.get("inventory")) if isinstance(payload.get("inventory"), Mapping) else (("__invalid_inventory__", payload.get("inventory")),),
            material_priority=tuple(priority) if isinstance(priority, Sequence) and not isinstance(priority, str) else ("__invalid_material_priority__",),
            segment_hard_limits=(
                tuple(
                    (checkpoint, HardLimits.from_dict(limit))
                    for checkpoint, limit in _checkpoint_pairs(segment_limits)
                )
                if isinstance(segment_limits, Mapping)
                else ((None, HardLimits.from_dict(segment_limits)),)
            )
            if "segment_hard_limits" in payload
            else (),
            cumulative_hard_limits=HardLimits.from_dict(payload["cumulative_hard_limits"])
            if "cumulative_hard_limits" in payload
            else None,
            preview_base_experience=(
                _checkpoint_pairs(preview) if isinstance(preview, Mapping) else ((None, preview),)
            )
            if "preview_base_experience" in payload
            else (),
            segment_hard_limits_provided="segment_hard_limits" in payload,
            cumulative_hard_limits_provided="cumulative_hard_limits" in payload,
            preview_base_experience_provided="preview_base_experience" in payload,
        )


@dataclass(frozen=True)
class Consumption:
    materials: dict[str, int]
    gold: int

    def to_dict(self) -> dict[str, Any]:
        return {"materials": dict(sorted(self.materials.items())), "gold": self.gold}


@dataclass(frozen=True)
class SegmentPlan:
    from_checkpoint: int
    to_checkpoint: int
    required_base_experience: int
    preview_base_experience: int | None
    materials: dict[str, int]
    provided_base_experience: int
    experience_overflow: int
    gold: int
    suggested_hard_limit: Consumption
    applied_hard_limit: Consumption | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_checkpoint": self.from_checkpoint,
            "to_checkpoint": self.to_checkpoint,
            "required_base_experience": self.required_base_experience,
            "preview_base_experience": self.preview_base_experience,
            "materials": dict(sorted(self.materials.items())),
            "provided_base_experience": self.provided_base_experience,
            "experience_overflow": self.experience_overflow,
            "gold": self.gold,
            "suggested_hard_limit": self.suggested_hard_limit.to_dict(),
            "applied_hard_limit": self.applied_hard_limit.to_dict() if self.applied_hard_limit else None,
        }


@dataclass(frozen=True)
class BudgetPlanResult:
    rules_version: str
    success: bool
    mode: str
    material_pool: str | None
    rarity: str | None
    objective_order: tuple[str, ...]
    segments: tuple[SegmentPlan, ...]
    cumulative_expected_consumption: Consumption | None
    cumulative_suggested_hard_limit: Consumption | None
    cumulative_applied_hard_limit: Consumption | None
    hard_limit_check: str
    failure_code: str | None = None
    failure_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_version": self.rules_version,
            "success": self.success,
            "mode": self.mode,
            "material_pool": self.material_pool,
            "rarity": self.rarity,
            "objective_order": list(self.objective_order),
            "segments": [segment.to_dict() for segment in self.segments],
            "cumulative_expected_consumption": self.cumulative_expected_consumption.to_dict()
            if self.cumulative_expected_consumption
            else None,
            "cumulative_suggested_hard_limit": self.cumulative_suggested_hard_limit.to_dict()
            if self.cumulative_suggested_hard_limit
            else None,
            "cumulative_applied_hard_limit": self.cumulative_applied_hard_limit.to_dict()
            if self.cumulative_applied_hard_limit
            else None,
            "hard_limit_check": self.hard_limit_check,
            "failure": {"code": self.failure_code, "detail": self.failure_detail}
            if self.failure_code
            else None,
        }


@dataclass(frozen=True)
class _Candidate:
    materials: tuple[int, ...]
    provided_base_experience: int
    gold: int


@dataclass(frozen=True)
class _ValidatedRequest:
    material_pool: str
    rarity: str
    current_checkpoint: int
    target_checkpoint: int
    allowed_materials: tuple[str, ...]
    material_priority: tuple[str, ...]
    inventory: dict[str, int]
    segment_hard_limits: dict[int, Consumption]
    cumulative_hard_limits: Consumption | None
    preview_base_experience: dict[int, int]
    hard_limits_supplied: bool


def plan_budget(request: BudgetPlanningRequest) -> BudgetPlanResult:
    """Return a deterministic plan or a structured fail-closed result."""
    validated, failure = _validate_request(request)
    if failure is not None:
        return failure
    assert validated is not None

    intervals = _intervals(validated.current_checkpoint, validated.target_checkpoint)
    requirements = [_interval_requirement(validated.rarity, checkpoint) for _, checkpoint in intervals]
    for (_, checkpoint), requirement in zip(intervals, requirements):
        preview = validated.preview_base_experience.get(checkpoint)
        if preview is not None and preview != requirement:
            return _failure(
                "preview_requirement_mismatch",
                f"checkpoint {checkpoint} preview {preview} does not match published requirement {requirement}",
                validated,
            )

    material_order = tuple(sorted(validated.allowed_materials))
    definitions = tuple(MATERIALS[material] for material in material_order)
    states: dict[tuple[int, ...], tuple[int, tuple[_Candidate, ...]]] = {
        tuple(0 for _ in material_order): (0, ())
    }
    for index, ((from_checkpoint, to_checkpoint), requirement) in enumerate(zip(intervals, requirements)):
        segment_limit = validated.segment_hard_limits.get(to_checkpoint)
        candidates = _segment_candidates(
            requirement,
            definitions,
            material_order,
            validated.inventory,
            segment_limit,
        )
        next_states: dict[tuple[int, ...], tuple[int, tuple[_Candidate, ...]]] = {}
        for used_materials, (used_overflow, path) in sorted(states.items()):
            for candidate in candidates:
                total_materials = tuple(left + right for left, right in zip(used_materials, candidate.materials))
                total_gold = _gold_for_counts(total_materials, definitions)
                if not _within_inventory(total_materials, material_order, validated.inventory):
                    continue
                if validated.cumulative_hard_limits and not _within_limit(
                    total_materials,
                    total_gold,
                    material_order,
                    validated.cumulative_hard_limits,
                ):
                    continue
                candidate_value = (used_overflow + candidate.provided_base_experience - requirement, path + (candidate,))
                existing = next_states.get(total_materials)
                if existing is None or _state_key(candidate_value, material_order) < _state_key(existing, material_order):
                    next_states[total_materials] = candidate_value
        if not next_states:
            return _failure(
                "no_feasible_integer_combination",
                f"no integer material combination can safely reach {from_checkpoint}->{to_checkpoint}",
                validated,
            )
        states = next_states

    total_materials, (total_overflow, chosen_path) = min(
        states.items(),
        key=lambda item: _final_key(item[0], item[1][0], definitions, material_order, validated.material_priority),
    )
    del total_overflow
    segments = tuple(
        _to_segment_plan(
            interval,
            requirement,
            candidate,
            material_order,
            validated.segment_hard_limits.get(interval[1]),
            validated.preview_base_experience.get(interval[1]),
        )
        for interval, requirement, candidate in zip(intervals, requirements, chosen_path)
    )
    cumulative = Consumption(_counts_dict(total_materials, material_order), _gold_for_counts(total_materials, definitions))
    applied = validated.cumulative_hard_limits
    return BudgetPlanResult(
        rules_version=RULES_VERSION,
        success=True,
        mode="validated_against_hard_limits" if validated.hard_limits_supplied else "proposal_only",
        material_pool=validated.material_pool,
        rarity=validated.rarity,
        objective_order=OBJECTIVE_ORDER,
        segments=segments,
        cumulative_expected_consumption=cumulative,
        cumulative_suggested_hard_limit=cumulative,
        cumulative_applied_hard_limit=applied,
        hard_limit_check="passed" if validated.hard_limits_supplied else "not_provided",
    )


def canonical_json(result: BudgetPlanResult) -> str:
    """Render a byte-stable JSON value without relying on process state."""
    return json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def render_markdown(result: BudgetPlanResult) -> str:
    """Render a readable report without adding execution authorization language."""
    data = result.to_dict()
    lines = ["# 离线预算与硬上限规划结果", "", f"- 规则版本：`{data['rules_version']}`", f"- 状态：`{'success' if result.success else 'fail_closed'}`", f"- 模式：`{data['mode']}`"]
    if not result.success:
        lines.extend(
            [
                f"- 失败原因：`{_markdown_safe(result.failure_code)}`",
                f"- 详情：{_markdown_safe(result.failure_detail)}",
            ]
        )
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"- 材料池：`{result.material_pool}`",
            f"- 品质：`{result.rarity}`",
            f"- 排序：`{' -> '.join(result.objective_order)}`",
            f"- 硬上限核对：`{result.hard_limit_check}`",
            "",
            "| 分段 | 需求基础经验 | 投入基础经验 | 溢出 | 材料 | 金币 |",
            "|---|---:|---:|---:|---|---:|",
        ]
    )
    for segment in result.segments:
        materials = ", ".join(f"{name}={quantity}" for name, quantity in sorted(segment.materials.items()))
        lines.append(
            f"| +{segment.from_checkpoint} -> +{segment.to_checkpoint} | {segment.required_base_experience} | "
            f"{segment.provided_base_experience} | {segment.experience_overflow} | {materials} | {segment.gold} |"
        )
    assert result.cumulative_expected_consumption is not None
    lines.extend(
        [
            "",
            f"- 累计预计消耗：材料 `{result.cumulative_expected_consumption.materials}`；金币 `{result.cumulative_expected_consumption.gold}`。",
            f"- 累计建议硬上限：材料 `{result.cumulative_suggested_hard_limit.materials}`；金币 `{result.cumulative_suggested_hard_limit.gold}`。",
            "- 本结果仅为离线计算，不构成材料选择、资源消耗或实际操作授权。",
        ]
    )
    return "\n".join(lines) + "\n"


def _mapping_pairs(value: Mapping[Any, Any] | None) -> tuple[tuple[Any, Any], ...]:
    if value is None:
        return ()
    return tuple(sorted(value.items(), key=lambda item: str(item[0])))


def _checkpoint_pairs(value: Mapping[Any, Any]) -> tuple[tuple[Any, Any], ...]:
    pairs = []
    for checkpoint, item in _mapping_pairs(value):
        if isinstance(checkpoint, str) and checkpoint.isdigit():
            pairs.append((int(checkpoint), item))
        else:
            pairs.append((checkpoint, item))
    return tuple(pairs)


def _markdown_safe(value: Any) -> str:
    normalized = " ".join(str(value if value is not None else "").splitlines())
    escaped = escape(normalized, quote=True).replace("\\", "\\\\")
    for character in ("|", "`", "[", "]", "*", "_"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _validate_request(request: BudgetPlanningRequest) -> tuple[_ValidatedRequest | None, BudgetPlanResult | None]:
    if not isinstance(request, BudgetPlanningRequest):
        return None, _failure("invalid_request", "request must be BudgetPlanningRequest")
    if request.material_pool not in {"common", "accessory"}:
        return None, _failure("invalid_material_pool", "material_pool must be common or accessory", request)
    if request.rarity not in {"Epic", "Heroic"}:
        return None, _failure("invalid_rarity", "rarity must be Epic or Heroic", request)
    if request.current_checkpoint not in CHECKPOINTS or request.target_checkpoint not in CHECKPOINTS:
        return None, _failure("invalid_checkpoint", "checkpoints must be standard checkpoints", request)
    if request.target_checkpoint <= request.current_checkpoint:
        return None, _failure("invalid_checkpoint_order", "target checkpoint must be greater than current checkpoint", request)
    if not request.allowed_materials:
        return None, _failure("empty_allowed_materials", "allowed_materials must not be empty", request)
    if not _unique_strings(request.allowed_materials):
        return None, _failure("invalid_allowed_materials", "allowed_materials must be unique material identifiers", request)
    allowed = tuple(request.allowed_materials)
    owners = [MATERIALS[material].material_pool for material in allowed if material in MATERIALS]
    if any(owner != request.material_pool for owner in owners):
        return None, _failure("material_pool_mismatch", "allowed material belongs to a different material pool", request)
    for material in allowed:
        definition = MATERIALS.get(material)
        if definition is None or definition.support_status != "supported":
            return None, _failure("unsupported_material", f"{material}: {definition.reason if definition else 'unknown material'}", request)
    if not _unique_strings(request.material_priority) or set(request.material_priority) != set(allowed):
        return None, _failure("invalid_material_priority", "priority must contain each allowed material exactly once", request)
    inventory, inventory_error = _quantity_map(request.inventory, "inventory")
    if inventory_error or set(inventory) != set(allowed):
        return None, _failure("invalid_inventory", inventory_error or "inventory must cover exactly the allowed materials", request)
    segment_provided = request.segment_hard_limits_provided or bool(request.segment_hard_limits)
    cumulative_provided = request.cumulative_hard_limits_provided or request.cumulative_hard_limits is not None
    preview_provided = request.preview_base_experience_provided or bool(request.preview_base_experience)
    if segment_provided != cumulative_provided:
        return None, _failure(
            "incomplete_hard_limits",
            "segment and cumulative hard limits must be provided together",
            request,
        )
    intervals = _intervals(request.current_checkpoint, request.target_checkpoint)
    segment_limits, segment_error = _segment_limits(
        request.segment_hard_limits,
        allowed,
        intervals,
        required=segment_provided,
    )
    if segment_error:
        return None, _failure("incomplete_hard_limits", segment_error, request)
    cumulative, cumulative_error = _limit_to_consumption(request.cumulative_hard_limits, allowed)
    if cumulative_error:
        return None, _failure("incomplete_hard_limits", cumulative_error, request)
    preview, preview_error = _preview_map(
        request.preview_base_experience,
        intervals,
        required=preview_provided,
    )
    if preview_error:
        return None, _failure("preview_requirement_mismatch", preview_error, request)
    return (
        _ValidatedRequest(
            material_pool=request.material_pool,
            rarity=request.rarity,
            current_checkpoint=request.current_checkpoint,
            target_checkpoint=request.target_checkpoint,
            allowed_materials=allowed,
            material_priority=tuple(request.material_priority),
            inventory=inventory,
            segment_hard_limits=segment_limits,
            cumulative_hard_limits=cumulative,
            preview_base_experience=preview,
            hard_limits_supplied=segment_provided and cumulative_provided,
        ),
        None,
    )


def _unique_strings(values: Sequence[Any]) -> bool:
    return all(isinstance(value, str) for value in values) and len(values) == len(set(values))


def _quantity_map(pairs: Sequence[tuple[Any, Any]], label: str) -> tuple[dict[str, int], str | None]:
    values: dict[str, int] = {}
    for material, quantity in pairs:
        if not isinstance(material, str) or material in values:
            return {}, f"{label} material identifiers must be unique strings"
        if not _non_negative_int(quantity):
            return {}, f"{label} quantities must be non-negative integers"
        values[material] = quantity
    return values, None


def _limit_to_consumption(limit: HardLimits | None, allowed: Sequence[str]) -> tuple[Consumption | None, str | None]:
    if limit is None:
        return None, None
    materials, error = _quantity_map(limit.materials, "hard limit")
    if error:
        return None, error
    if set(materials) != set(allowed):
        return None, "hard limit materials must cover exactly the allowed materials"
    if not _non_negative_int(limit.gold):
        return None, "hard limit gold must be a non-negative integer"
    return Consumption(dict(sorted(materials.items())), limit.gold), None


def _segment_limits(
    pairs: Sequence[tuple[Any, HardLimits]],
    allowed: Sequence[str],
    intervals: Sequence[tuple[int, int]],
    required: bool = False,
) -> tuple[dict[int, Consumption], str | None]:
    if not pairs:
        if required:
            return {}, "segment hard limits must cover every planned segment"
        return {}, None
    limits: dict[int, Consumption] = {}
    expected = {to_checkpoint for _, to_checkpoint in intervals}
    for checkpoint, limit in pairs:
        if not _non_negative_int(checkpoint) or checkpoint in limits:
            return {}, "segment hard limit checkpoints must be unique standard checkpoints"
        parsed, error = _limit_to_consumption(limit, allowed)
        if error:
            return {}, error
        assert parsed is not None
        limits[checkpoint] = parsed
    if set(limits) != expected:
        return {}, "segment hard limits must cover exactly the planned segment endpoints"
    return limits, None


def _preview_map(
    pairs: Sequence[tuple[Any, Any]],
    intervals: Sequence[tuple[int, int]],
    required: bool = False,
) -> tuple[dict[int, int], str | None]:
    if not pairs:
        if required:
            return {}, "preview requirements must cover every planned segment"
        return {}, None
    preview: dict[int, int] = {}
    expected = {to_checkpoint for _, to_checkpoint in intervals}
    for checkpoint, requirement in pairs:
        if not _non_negative_int(checkpoint) or checkpoint in preview or not _non_negative_int(requirement):
            return {}, "preview requirements must use unique checkpoint and non-negative integer values"
        preview[checkpoint] = requirement
    if set(preview) != expected:
        return {}, "preview requirements must cover exactly the planned segment endpoints"
    return preview, None


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _intervals(current: int, target: int) -> tuple[tuple[int, int], ...]:
    start = CHECKPOINTS.index(current)
    end = CHECKPOINTS.index(target)
    return tuple((CHECKPOINTS[index], CHECKPOINTS[index + 1]) for index in range(start, end))


def _interval_requirement(rarity: str, endpoint: int) -> int:
    values = RED_LEVEL_EXP if rarity == "Epic" else PURPLE_LEVEL_EXP
    start = 1 if endpoint == 3 else endpoint - 2
    return sum(values[level] for level in range(start, endpoint + 1))


def _segment_candidates(
    requirement: int,
    definitions: Sequence[MaterialDefinition],
    material_order: Sequence[str],
    inventory: Mapping[str, int],
    hard_limit: Consumption | None,
) -> tuple[_Candidate, ...]:
    if len(definitions) == 1:
        definition = definitions[0]
        assert definition.base_experience is not None
        count = ceil(requirement / definition.base_experience)
        counts = (count,)
        gold = _gold_for_counts(counts, definitions)
        if _within_inventory(counts, material_order, inventory) and (
            hard_limit is None or _within_limit(counts, gold, material_order, hard_limit)
        ):
            return (_Candidate(counts, count * definition.base_experience, gold),)
        return ()

    # The current public discrete catalog has exactly two supported materials.
    # For a fixed count of the first, the least count of the second that reaches
    # the target dominates every larger second count: all costs are positive and
    # all constraints are upper bounds. This is equivalent to the full bounded
    # grid while keeping +15 plans tractable.
    first, second = definitions
    assert first.base_experience is not None and second.base_experience is not None
    first_upper = min(inventory[material_order[0]], ceil(requirement / first.base_experience))
    if hard_limit is not None:
        first_upper = min(first_upper, hard_limit.materials[material_order[0]])
    candidates = []
    for first_count in range(first_upper + 1):
        remaining = max(0, requirement - first_count * first.base_experience)
        second_count = ceil(remaining / second.base_experience)
        counts = (first_count, second_count)
        if not _within_inventory(counts, material_order, inventory):
            continue
        gold = _gold_for_counts(counts, definitions)
        if hard_limit is not None and not _within_limit(counts, gold, material_order, hard_limit):
            continue
        experience = first_count * first.base_experience + second_count * second.base_experience
        candidates.append(_Candidate(counts, experience, gold))
    return tuple(sorted(candidates, key=lambda item: (item.gold, item.provided_base_experience - requirement, sum(item.materials), item.materials)))


def _gold_for_counts(counts: Sequence[int], definitions: Sequence[MaterialDefinition]) -> int:
    return sum(count * int(definition.gold_per_unit or 0) for count, definition in zip(counts, definitions))


def _within_inventory(counts: Sequence[int], material_order: Sequence[str], inventory: Mapping[str, int]) -> bool:
    return all(count <= inventory[material] for material, count in zip(material_order, counts))


def _within_limit(counts: Sequence[int], gold: int, material_order: Sequence[str], limit: Consumption) -> bool:
    return gold <= limit.gold and all(count <= limit.materials[material] for material, count in zip(material_order, counts))


def _state_key(state: tuple[int, tuple[_Candidate, ...]], material_order: Sequence[str]) -> tuple[Any, ...]:
    overflow, path = state
    return overflow, tuple(candidate.materials for candidate in path), tuple(material_order)


def _final_key(
    counts: Sequence[int],
    overflow: int,
    definitions: Sequence[MaterialDefinition],
    material_order: Sequence[str],
    priority: Sequence[str],
) -> tuple[Any, ...]:
    quantities = _counts_dict(counts, material_order)
    priority_key = tuple(-quantities[material] for material in priority)
    return _gold_for_counts(counts, definitions), overflow, sum(counts), priority_key


def _counts_dict(counts: Sequence[int], material_order: Sequence[str]) -> dict[str, int]:
    return {material: count for material, count in sorted(zip(material_order, counts))}


def _to_segment_plan(
    interval: tuple[int, int],
    requirement: int,
    candidate: _Candidate,
    material_order: Sequence[str],
    hard_limit: Consumption | None,
    preview: int | None,
) -> SegmentPlan:
    consumption = Consumption(_counts_dict(candidate.materials, material_order), candidate.gold)
    return SegmentPlan(
        from_checkpoint=interval[0],
        to_checkpoint=interval[1],
        required_base_experience=requirement,
        preview_base_experience=preview,
        materials=consumption.materials,
        provided_base_experience=candidate.provided_base_experience,
        experience_overflow=candidate.provided_base_experience - requirement,
        gold=candidate.gold,
        suggested_hard_limit=consumption,
        applied_hard_limit=hard_limit,
    )


def _failure(code: str, detail: str, request: _ValidatedRequest | BudgetPlanningRequest | None = None) -> BudgetPlanResult:
    material_pool = request.material_pool if isinstance(request, (_ValidatedRequest, BudgetPlanningRequest)) else None
    rarity = request.rarity if isinstance(request, (_ValidatedRequest, BudgetPlanningRequest)) else None
    applied_limit = request.cumulative_hard_limits if isinstance(request, _ValidatedRequest) else None
    return BudgetPlanResult(
        rules_version=RULES_VERSION,
        success=False,
        mode="not_planned",
        material_pool=material_pool if isinstance(material_pool, str) else None,
        rarity=rarity if isinstance(rarity, str) else None,
        objective_order=OBJECTIVE_ORDER,
        segments=(),
        cumulative_expected_consumption=None,
        cumulative_suggested_hard_limit=None,
        cumulative_applied_hard_limit=applied_limit,
        hard_limit_check="not_checked",
        failure_code=code,
        failure_detail=detail,
    )
