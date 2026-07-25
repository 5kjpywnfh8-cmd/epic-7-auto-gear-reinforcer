"""Shared deterministic evidence helpers for offline budget planner validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from src.e7_enhance.offline_budget_planner import MATERIALS


EXPECTED_FIVE_SEGMENT_ROUTE = ((0, 3), (3, 6), (6, 9), (9, 12), (12, 15))


@dataclass(frozen=True)
class BoundaryInput:
    value: int
    primary_label: str
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "primary_label": self.primary_label,
            "aliases": list(self.aliases),
        }


def independent_boundary_values(planned: int) -> tuple[BoundaryInput, ...]:
    """Return unique integer inputs while retaining duplicate labels as aliases."""
    if not isinstance(planned, int) or isinstance(planned, bool) or planned < 0:
        raise ValueError("planned must be a non-negative integer")
    candidates = (
        ("zero", 0),
        ("planned_minus_one", max(0, planned - 1)),
        ("planned", planned),
        ("planned_plus_one", planned + 1),
    )
    labels_by_value: dict[int, list[str]] = {}
    for label, value in candidates:
        labels_by_value.setdefault(value, []).append(label)
    return tuple(
        BoundaryInput(value=value, primary_label=labels[0], aliases=tuple(labels[1:]))
        for value, labels in labels_by_value.items()
    )


def canonical_request_json(request: Mapping[str, Any]) -> str:
    """Return stable canonical JSON for global full-request deduplication."""
    if not isinstance(request, Mapping):
        raise ValueError("request must be a mapping")
    return json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def success_result_violations(
    result: Any,
    request: Mapping[str, Any],
) -> tuple[str, ...]:
    """Validate a successful five-segment result against its complete request."""
    violations: list[str] = []
    if not getattr(result, "success", False):
        return ("result_not_success",)

    requested_pool = request.get("material_pool")
    allowed_value = request.get("allowed_materials")
    if not isinstance(requested_pool, str):
        violations.append("invalid_request_material_pool")
    if not isinstance(allowed_value, (list, tuple)) or not all(
        isinstance(material, str) for material in allowed_value
    ) or len(allowed_value) != len(set(allowed_value)):
        violations.append("invalid_request_allowed_materials")
        allowed_materials: tuple[str, ...] = ()
    else:
        allowed_materials = tuple(allowed_value)
    allowed_set = set(allowed_materials)
    for material in allowed_materials:
        definition = MATERIALS.get(material)
        if definition is None:
            violations.append(f"unknown_allowed_material:{material}")
        elif definition.material_pool != requested_pool:
            violations.append(f"allowed_material_pool_mismatch:{material}")

    if getattr(result, "material_pool", None) != requested_pool:
        violations.append("result_material_pool_mismatch")
    if getattr(result, "mode", None) != "validated_against_hard_limits":
        violations.append("unexpected_result_mode")

    inventory = request.get("inventory")
    if not isinstance(inventory, Mapping):
        violations.append("invalid_request_inventory")
        inventory = {}
    segment_limits = request.get("segment_hard_limits")
    if not isinstance(segment_limits, Mapping):
        violations.append("invalid_request_segment_hard_limits")
        segment_limits = {}
    cumulative_limit = request.get("cumulative_hard_limits")
    if not isinstance(cumulative_limit, Mapping):
        violations.append("invalid_request_cumulative_hard_limits")
        cumulative_limit = {}

    def material_map(value: Any, location: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            violations.append(f"invalid_materials_mapping:{location}")
            return {}
        if set(value) != allowed_set:
            violations.append(f"material_keys_mismatch:{location}")
        for material, quantity in value.items():
            if not isinstance(material, str) or material not in MATERIALS:
                violations.append(f"unknown_material:{location}:{material}")
            elif MATERIALS[material].material_pool != requested_pool:
                violations.append(f"material_pool_mismatch:{location}:{material}")
            if not _non_negative_int(quantity):
                violations.append(f"invalid_material_quantity:{location}:{material}")
        return value

    def consumption_materials(value: Any, location: str) -> Mapping[str, Any]:
        if value is None:
            violations.append(f"missing_consumption:{location}")
            return {}
        return material_map(getattr(value, "materials", None), location)

    segments = tuple(getattr(result, "segments", ()) or ())
    if len(segments) != len(EXPECTED_FIVE_SEGMENT_ROUTE):
        violations.append("segment_count_not_five")
    route = tuple(
        (getattr(segment, "from_checkpoint", None), getattr(segment, "to_checkpoint", None))
        for segment in segments
    )
    if route != EXPECTED_FIVE_SEGMENT_ROUTE:
        violations.append("route_not_standard_0_to_15")
    endpoints = tuple(endpoint for _, endpoint in route)
    if len(endpoints) != len(set(endpoints)):
        violations.append("duplicate_segment_endpoint")

    cumulative_expected = getattr(result, "cumulative_expected_consumption", None)
    cumulative_suggested = getattr(result, "cumulative_suggested_hard_limit", None)
    cumulative_applied = getattr(result, "cumulative_applied_hard_limit", None)
    cumulative_materials = consumption_materials(cumulative_expected, "cumulative_expected.materials")
    consumption_materials(cumulative_suggested, "cumulative_suggested.materials")
    consumption_materials(cumulative_applied, "cumulative_applied.materials")
    cumulative_gold = getattr(cumulative_expected, "gold", None)
    cumulative_limit_gold = cumulative_limit.get("gold")
    cumulative_limit_materials = cumulative_limit.get("materials")
    if not _non_negative_int(cumulative_limit_gold):
        violations.append("invalid_request_cumulative_gold_limit")
    if not isinstance(cumulative_limit_materials, Mapping):
        violations.append("invalid_request_cumulative_material_limits")
        cumulative_limit_materials = {}
    if not _non_negative_int(cumulative_gold) or (
        _non_negative_int(cumulative_limit_gold) and cumulative_gold > cumulative_limit_gold
    ):
        violations.append("cumulative_gold_limit")
    for material in allowed_materials:
        quantity = cumulative_materials.get(material)
        if not _non_negative_int(quantity):
            violations.append(f"missing_cumulative_material:{material}")
            continue
        inventory_quantity = inventory.get(material)
        limit_quantity = cumulative_limit_materials.get(material)
        if not _non_negative_int(inventory_quantity) or quantity > inventory_quantity:
            violations.append(f"inventory_limit:{material}")
        if not _non_negative_int(limit_quantity) or quantity > limit_quantity:
            violations.append(f"cumulative_material_limit:{material}")

    segment_material_totals = {material: 0 for material in allowed_materials}
    segment_gold_total = 0
    for index, segment in enumerate(segments):
        endpoint = str(getattr(segment, "to_checkpoint", ""))
        limit = segment_limits.get(endpoint)
        if not isinstance(limit, Mapping):
            violations.append(f"missing_segment_limit:{endpoint}")
            continue
        limit_materials = limit.get("materials")
        if not isinstance(limit_materials, Mapping):
            violations.append(f"invalid_segment_material_limit:{endpoint}")
            limit_materials = {}
        limit_gold = limit.get("gold")
        gold = getattr(segment, "gold", None)
        if not _non_negative_int(gold) or not _non_negative_int(limit_gold) or gold > limit_gold:
            violations.append(f"segment_gold_limit:{endpoint}")
        else:
            segment_gold_total += gold
        materials = material_map(getattr(segment, "materials", None), f"segments[{index}].materials")
        consumption_materials(
            getattr(segment, "suggested_hard_limit", None),
            f"segments[{index}].suggested_hard_limit.materials",
        )
        consumption_materials(
            getattr(segment, "applied_hard_limit", None),
            f"segments[{index}].applied_hard_limit.materials",
        )
        for material in allowed_materials:
            quantity = materials.get(material)
            if not _non_negative_int(quantity):
                violations.append(f"missing_segment_material:{endpoint}:{material}")
                continue
            segment_material_totals[material] += quantity
            limit_quantity = limit_materials.get(material)
            if not _non_negative_int(limit_quantity) or quantity > limit_quantity:
                violations.append(f"segment_material_limit:{endpoint}:{material}")

    if _non_negative_int(cumulative_gold) and segment_gold_total != cumulative_gold:
        violations.append("segment_gold_total_mismatch")
    for material in allowed_materials:
        quantity = cumulative_materials.get(material)
        if _non_negative_int(quantity) and segment_material_totals[material] != quantity:
            violations.append(f"segment_material_total_mismatch:{material}")
    return tuple(violations)


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
