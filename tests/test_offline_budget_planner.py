import unittest
import io
import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path

from src.e7_enhance.cli import main
from src.e7_enhance.offline_budget_planner import (
    BudgetPlanningRequest,
    Consumption,
    canonical_json,
    plan_budget,
    render_markdown,
)
from src.e7_enhance.resource_model import (
    LOWER_ENHANCE_STONE_EXP,
    LOWER_ENHANCE_STONE_USE_GOLD,
    POWDER_EXP,
    POWDER_GOLD,
    UPPER_ENHANCE_STONE_EXP,
    UPPER_ENHANCE_STONE_USE_GOLD,
    page_effective_experience,
)
from tools.offline_budget_planner_validation_support import (
    canonical_request_json,
    independent_boundary_values,
    success_result_violations,
)
from tools.generate_offline_budget_planner_report import (
    build_validation_payload,
    render_markdown as render_validation_markdown,
)


def request_payload(**overrides):
    payload = {
        "material_pool": "common",
        "rarity": "Epic",
        "current_checkpoint": 0,
        "target_checkpoint": 3,
        "allowed_materials": ["powder", "lower_enhance_stone"],
        "inventory": {"powder": 500, "lower_enhance_stone": 50},
        "material_priority": ["lower_enhance_stone", "powder"],
    }
    payload.update(overrides)
    return payload


class OfflineBudgetPlannerTest(unittest.TestCase):
    def plan(self, **overrides):
        return plan_budget(BudgetPlanningRequest.from_dict(request_payload(**overrides)))

    def full_path_proposal(self):
        result = self.plan(target_checkpoint=15)
        self.assertTrue(result.success)
        return result

    def full_path_validated(self):
        proposal = self.full_path_proposal()
        segment_limits, cumulative_limit = self.limits_from_result(proposal)
        request = request_payload(
            target_checkpoint=15,
            inventory=dict(cumulative_limit["materials"]),
            segment_hard_limits=segment_limits,
            cumulative_hard_limits=cumulative_limit,
        )
        result = plan_budget(BudgetPlanningRequest.from_dict(request))
        self.assertTrue(result.success)
        return result, request

    @staticmethod
    def limits_from_result(result):
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

    def assert_success_within_all_limits(self, result, inventory, segment_limits, cumulative_limit):
        request = request_payload(
            target_checkpoint=15,
            inventory=inventory,
            segment_hard_limits=segment_limits,
            cumulative_hard_limits=cumulative_limit,
        )
        self.assertEqual(
            success_result_violations(result, request),
            (),
        )

    def assert_structured_fail_closed(self, result):
        self.assertFalse(result.success)
        self.assertEqual(result.mode, "not_planned")
        self.assertIsNotNone(result.failure_code)
        self.assertTrue(result.failure_detail)

    def test_boundary_values_deduplicate_integer_inputs_and_record_aliases(self):
        zero = independent_boundary_values(0)
        one = independent_boundary_values(1)
        normal = independent_boundary_values(5)

        self.assertEqual(tuple(item.value for item in zero), (0, 1))
        self.assertEqual(zero[0].primary_label, "zero")
        self.assertEqual(zero[0].aliases, ("planned_minus_one", "planned"))
        self.assertEqual(tuple(item.value for item in one), (0, 1, 2))
        self.assertEqual(one[0].aliases, ("planned_minus_one",))
        self.assertEqual(tuple(item.value for item in normal), (0, 4, 5, 6))
        self.assertTrue(all(not item.aliases for item in normal))

    def test_canonical_request_json_is_stable_for_full_request_key_order(self):
        left = request_payload(
            target_checkpoint=15,
            inventory={"powder": 10, "lower_enhance_stone": 2},
        )
        right = dict(reversed(tuple(left.items())))
        right["inventory"] = {"lower_enhance_stone": 2, "powder": 10}

        self.assertEqual(canonical_request_json(left), canonical_request_json(right))

    def test_report_matrix_separates_coverage_cases_from_global_unique_requests(self):
        payload = build_validation_payload()
        matrix = payload["five_segment_bounded_matrix"]

        self.assertGreater(matrix["raw_label_candidate_count"], 0)
        self.assertGreaterEqual(matrix["local_alias_count"], 0)
        self.assertGreater(matrix["coverage_case_count"], 0)
        self.assertGreater(matrix["global_unique_request_count"], 0)
        self.assertEqual(
            matrix["coverage_case_count"] - matrix["global_unique_request_count"],
            matrix["duplicate_request_case_count"],
        )
        coverage = matrix["coverage_results"]
        unique = matrix["unique_request_results"]
        self.assertEqual(
            coverage["success_count"]
            + coverage["fail_closed_count"]
            + coverage["violation_case_count"],
            matrix["coverage_case_count"],
        )
        self.assertEqual(
            unique["success_count"]
            + unique["fail_closed_count"]
            + unique["violation_case_count"],
            matrix["global_unique_request_count"],
        )
        catalog = matrix["global_unique_request_catalog"]
        self.assertEqual(len(catalog), matrix["global_unique_request_count"])
        self.assertEqual(
            sum(record["coverage_case_count"] for record in catalog),
            matrix["coverage_case_count"],
        )
        self.assertEqual(
            len({canonical_request_json(record["canonical_request"]) for record in catalog}),
            matrix["global_unique_request_count"],
        )
        accessory_matrix = payload["accessory_five_segment_bounded_matrix"]
        self.assertEqual(accessory_matrix["coverage_axes"]["segment_endpoints"], [3, 6, 9, 12, 15])
        self.assertTrue(
            all(material.startswith("accessory_") for material in accessory_matrix["coverage_axes"]["materials"])
        )
        self.assertEqual(
            set(accessory_matrix["coverage_dimensions"]),
            {
                "segment_material_hard_limit",
                "cumulative_material_hard_limit",
                "inventory_material",
            },
        )
        self.assertTrue(
            all(
                all(material.startswith("accessory_") for material in record["canonical_request"]["allowed_materials"])
                for record in accessory_matrix["global_unique_request_catalog"]
            )
        )
        self.assertTrue(
            all(
                case["material"].startswith("accessory_")
                for case in accessory_matrix["coverage_case_catalog"]
            )
        )
        accessory_coverage = accessory_matrix["coverage_results"]
        self.assertEqual(
            accessory_coverage["success_count"]
            + accessory_coverage["fail_closed_count"]
            + accessory_coverage["violation_case_count"],
            accessory_matrix["coverage_case_count"],
        )
        self.assertIn("饰品五段有界矩阵", render_validation_markdown(payload))

    def test_success_oracle_rejects_result_material_pool_mismatch(self):
        result, request = self.full_path_validated()

        violations = success_result_violations(
            replace(result, material_pool="accessory"),
            request,
        )

        self.assertIn("result_material_pool_mismatch", violations)

    def test_success_oracle_rejects_material_key_mutations_on_every_output_surface(self):
        result, request = self.full_path_validated()

        def mutation(base, kind):
            materials = dict(base)
            if kind == "missing":
                materials.pop("lower_enhance_stone")
            elif kind == "accessory":
                materials["accessory_powder"] = 0
            else:
                materials["unknown_material"] = 0
            return materials

        for index, original_segment in enumerate(result.segments):
            segment_surfaces = (
                ("materials", original_segment.materials),
                ("suggested_hard_limit.materials", original_segment.suggested_hard_limit.materials),
                ("applied_hard_limit.materials", original_segment.applied_hard_limit.materials),
            )
            for surface, base_materials in segment_surfaces:
                for kind in ("missing", "accessory", "unknown"):
                    with self.subTest(index=index, surface=surface, kind=kind):
                        materials = mutation(base_materials, kind)
                        if surface == "materials":
                            changed_segment = replace(original_segment, materials=materials)
                        else:
                            attribute = surface.split(".")[0]
                            changed_limit = replace(getattr(original_segment, attribute), materials=materials)
                            changed_segment = replace(original_segment, **{attribute: changed_limit})
                        segments = list(result.segments)
                        segments[index] = changed_segment
                        changed_result = replace(result, segments=tuple(segments))
                        location = f"segments[{index}].{surface}"
                        violations = success_result_violations(changed_result, request)
                        self.assertIn(f"material_keys_mismatch:{location}", violations)
                        if kind == "accessory":
                            self.assertIn(
                                f"material_pool_mismatch:{location}:accessory_powder",
                                violations,
                            )
                        elif kind == "unknown":
                            self.assertIn(
                                f"unknown_material:{location}:unknown_material",
                                violations,
                            )

        cumulative_surfaces = (
            ("cumulative_expected_consumption", "cumulative_expected.materials"),
            ("cumulative_suggested_hard_limit", "cumulative_suggested.materials"),
            ("cumulative_applied_hard_limit", "cumulative_applied.materials"),
        )
        for attribute, location in cumulative_surfaces:
            original = getattr(result, attribute)
            self.assertIsInstance(original, Consumption)
            for kind in ("missing", "accessory", "unknown"):
                with self.subTest(attribute=attribute, kind=kind):
                    changed = replace(original, materials=mutation(original.materials, kind))
                    changed_result = replace(result, **{attribute: changed})
                    violations = success_result_violations(changed_result, request)
                    self.assertIn(f"material_keys_mismatch:{location}", violations)
                    if kind == "accessory":
                        self.assertIn(
                            f"material_pool_mismatch:{location}:accessory_powder",
                            violations,
                        )
                    elif kind == "unknown":
                        self.assertIn(
                            f"unknown_material:{location}:unknown_material",
                            violations,
                        )

    def test_common_pool_plans_every_standard_adjacent_interval(self):
        for current, target in ((0, 3), (3, 6), (6, 9), (9, 12), (12, 15)):
            with self.subTest(current=current, target=target):
                result = self.plan(current_checkpoint=current, target_checkpoint=target)

                self.assertTrue(result.success)
                self.assertEqual(result.mode, "proposal_only")
                self.assertEqual(len(result.segments), 1)
                segment = result.segments[0]
                self.assertGreaterEqual(segment.provided_page_effective_experience, segment.required_base_experience)
                self.assertGreaterEqual(segment.gold, 0)
                self.assertTrue(set(segment.materials).issubset({"powder", "lower_enhance_stone"}))

    def test_accessory_pool_matches_common_rules_with_isolated_material_identifiers(self):
        for current, target in ((0, 3), (3, 6), (6, 9), (9, 12), (12, 15)):
            with self.subTest(current=current, target=target):
                result = self.plan(
                    material_pool="accessory",
                    current_checkpoint=current,
                    target_checkpoint=target,
                    allowed_materials=["accessory_powder", "accessory_lower_enhance_stone"],
                    inventory={"accessory_powder": 500, "accessory_lower_enhance_stone": 50},
                    material_priority=["accessory_lower_enhance_stone", "accessory_powder"],
                )

                common = self.plan(current_checkpoint=current, target_checkpoint=target)
                self.assertTrue(result.success)
                self.assertEqual(
                    result.segments[0].provided_base_experience,
                    common.segments[0].provided_base_experience,
                )
                self.assertEqual(
                    result.segments[0].provided_page_effective_experience,
                    common.segments[0].provided_page_effective_experience,
                )

    def test_upper_stone_is_supported_when_it_is_the_only_allowed_material(self):
        result = self.plan(
            allowed_materials=["upper_enhance_stone"],
            inventory={"upper_enhance_stone": 1},
            material_priority=["upper_enhance_stone"],
        )

        self.assertTrue(result.success)
        segment = result.segments[0]
        self.assertEqual(segment.materials, {"upper_enhance_stone": 1})
        self.assertEqual(segment.provided_base_experience, UPPER_ENHANCE_STONE_EXP)
        self.assertEqual(segment.provided_page_effective_experience, 5247)
        self.assertEqual(segment.gold, UPPER_ENHANCE_STONE_USE_GOLD)

    def test_minimum_gold_prefers_powder_over_upper_stone_when_both_are_available(self):
        result = self.plan(
            allowed_materials=["powder", "upper_enhance_stone"],
            inventory={"powder": 500, "upper_enhance_stone": 50},
            material_priority=["upper_enhance_stone", "powder"],
        )

        self.assertTrue(result.success)
        segment = result.segments[0]
        self.assertEqual(segment.materials, {"powder": 17, "upper_enhance_stone": 0})
        self.assertEqual(segment.provided_base_experience, 1700)
        self.assertEqual(segment.provided_page_effective_experience, 1982)
        self.assertEqual(segment.gold, 27200)

    def test_hard_limits_can_force_the_supported_upper_stone(self):
        limit = {
            "materials": {"powder": 0, "upper_enhance_stone": 1},
            "gold": UPPER_ENHANCE_STONE_USE_GOLD,
        }
        result = self.plan(
            allowed_materials=["powder", "upper_enhance_stone"],
            inventory={"powder": 17, "upper_enhance_stone": 1},
            material_priority=["upper_enhance_stone", "powder"],
            segment_hard_limits={"3": limit},
            cumulative_hard_limits=limit,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.segments[0].materials, {"powder": 0, "upper_enhance_stone": 1})

    def test_batch_013_page_preview_uses_integer_account_multiplier(self):
        result = self.plan(
            inventory={"powder": 2, "lower_enhance_stone": 1},
            material_priority=["lower_enhance_stone", "powder"],
        )

        self.assertTrue(result.success)
        segment = result.segments[0]
        self.assertEqual(segment.materials, {"lower_enhance_stone": 1, "powder": 2})
        self.assertEqual(segment.provided_base_experience, 1700)
        self.assertEqual(segment.provided_page_effective_experience, 1982)
        self.assertEqual(segment.gold, 17600)
        self.assertEqual(
            [page_effective_experience(value) for value in (1500, 1600, 1700)],
            [1749, 1865, 1982],
        )

    def test_three_material_pools_enforce_five_segment_hard_limits_and_isolation(self):
        for material_pool, materials in (
            ("common", ["powder", "lower_enhance_stone", "upper_enhance_stone"]),
            (
                "accessory",
                ["accessory_powder", "accessory_lower_enhance_stone", "accessory_upper_enhance_stone"],
            ),
        ):
            with self.subTest(material_pool=material_pool):
                inventory = {material: 100 for material in materials}
                result = self.plan(
                    material_pool=material_pool,
                    target_checkpoint=15,
                    allowed_materials=materials,
                    inventory=inventory,
                    material_priority=list(reversed(materials)),
                )
                self.assertTrue(result.success)
                segment_limits, cumulative_limit = self.limits_from_result(result)
                validated = self.plan(
                    material_pool=material_pool,
                    target_checkpoint=15,
                    allowed_materials=materials,
                    inventory=dict(cumulative_limit["materials"]),
                    material_priority=list(reversed(materials)),
                    segment_hard_limits=segment_limits,
                    cumulative_hard_limits=cumulative_limit,
                )
                self.assertTrue(validated.success)
                self.assertEqual(validated.mode, "validated_against_hard_limits")
                self.assertTrue(all(set(segment.materials) == set(materials) for segment in validated.segments))

    def test_cross_pool_material_fails_closed(self):
        result = self.plan(
            allowed_materials=["powder", "accessory_powder"],
            inventory={"powder": 500, "accessory_powder": 500},
            material_priority=["powder", "accessory_powder"],
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, "material_pool_mismatch")

    def test_cross_pool_inventory_and_hard_limit_keys_fail_closed(self):
        cases = (
            (
                {"inventory": {"powder": 500, "accessory_powder": 0}},
                "invalid_inventory",
            ),
            (
                {
                    "inventory": {"powder": 500},
                    "segment_hard_limits": {
                        "3": {"materials": {"accessory_powder": 0}, "gold": 999999}
                    },
                    "cumulative_hard_limits": {
                        "materials": {"accessory_powder": 0},
                        "gold": 999999,
                    },
                },
                "incomplete_hard_limits",
            ),
        )
        for overrides, expected_code in cases:
            with self.subTest(overrides=overrides):
                result = self.plan(allowed_materials=["powder"], material_priority=["powder"], **overrides)
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, expected_code)

    def test_minimum_gold_then_overflow_then_count_selects_integer_plan(self):
        result = self.plan(
            inventory={"powder": 5, "lower_enhance_stone": 1},
            material_priority=["lower_enhance_stone", "powder"],
        )

        self.assertTrue(result.success)
        segment = result.segments[0]
        self.assertEqual(segment.materials, {"lower_enhance_stone": 1, "powder": 2})
        self.assertEqual(segment.provided_base_experience, 1700)
        self.assertEqual(segment.provided_page_effective_experience, 1982)
        self.assertEqual(segment.experience_overflow, 13)
        serialized = segment.to_dict()
        self.assertEqual(serialized["page_effective_experience_overflow"], 13)
        self.assertEqual(serialized["experience_overflow"], serialized["page_effective_experience_overflow"])
        self.assertEqual(segment.gold, 17600)

    def test_complete_segment_and_cumulative_hard_limits_validate_plan(self):
        limit = {
            "materials": {"powder": 2, "lower_enhance_stone": 1},
            "gold": 17600,
        }
        result = self.plan(
            inventory={"powder": 5, "lower_enhance_stone": 1},
            segment_hard_limits={"3": limit},
            cumulative_hard_limits=limit,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.mode, "validated_against_hard_limits")
        self.assertEqual(result.hard_limit_check, "passed")
        self.assertEqual(result.cumulative_expected_consumption.materials, {"lower_enhance_stone": 1, "powder": 2})

    def test_multisegment_plan_aggregates_and_revalidates_hard_limits(self):
        proposal = self.full_path_proposal()
        segment_limits, cumulative_limit = self.limits_from_result(proposal)
        verified = self.plan(
            target_checkpoint=15,
            segment_hard_limits=segment_limits,
            cumulative_hard_limits=cumulative_limit,
        )

        self.assertTrue(verified.success)
        self.assertEqual(verified.mode, "validated_against_hard_limits")
        self.assertEqual(len(verified.segments), 5)
        self.assertEqual(
            sum(segment.gold for segment in verified.segments),
            verified.cumulative_expected_consumption.gold,
        )
        for material, total in verified.cumulative_expected_consumption.materials.items():
            self.assertEqual(total, sum(segment.materials[material] for segment in verified.segments))

    def test_invalid_segment_hard_limit_container_is_not_treated_as_absent(self):
        for invalid in (None, [], ["not", "a", "mapping"], "invalid", 7):
            with self.subTest(invalid=invalid):
                result = self.plan(segment_hard_limits=invalid)
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, "incomplete_hard_limits")

    def test_invalid_preview_container_is_not_treated_as_absent(self):
        for invalid in (None, [], ["not", "a", "mapping"], "invalid", 7, {}):
            with self.subTest(invalid=invalid):
                result = self.plan(preview_base_experience=invalid)
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, "preview_requirement_mismatch")

    def test_only_one_hard_limit_layer_is_incomplete(self):
        proposal = self.full_path_proposal()
        segment_limits, cumulative_limit = self.limits_from_result(proposal)

        for overrides in (
            {"segment_hard_limits": segment_limits},
            {"cumulative_hard_limits": cumulative_limit},
        ):
            with self.subTest(overrides=overrides):
                result = self.plan(target_checkpoint=15, **overrides)
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, "incomplete_hard_limits")

    def test_full_path_inventory_shortfall_fails_closed(self):
        result = self.plan(
            target_checkpoint=15,
            inventory={"powder": 0, "lower_enhance_stone": 0},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, "no_feasible_integer_combination")

    def test_each_full_path_segment_shortfall_fails_closed(self):
        proposal = self.full_path_proposal()
        base_segments, cumulative_limit = self.limits_from_result(proposal)

        for endpoint in (3, 6, 9, 12, 15):
            with self.subTest(endpoint=endpoint):
                segment_limits = json.loads(json.dumps(base_segments))
                segment_limits[str(endpoint)]["gold"] -= 1
                result = self.plan(
                    target_checkpoint=15,
                    segment_hard_limits=segment_limits,
                    cumulative_hard_limits=cumulative_limit,
                )
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, "no_feasible_integer_combination")

    def test_full_path_cumulative_material_and_gold_shortfalls_fail_closed(self):
        proposal = self.full_path_proposal()
        segment_limits, cumulative_limit = self.limits_from_result(proposal)
        constrained = []
        for material in ("powder", "lower_enhance_stone"):
            limit = json.loads(json.dumps(cumulative_limit))
            limit["materials"][material] = 0
            constrained.append(limit)
        gold_limit = json.loads(json.dumps(cumulative_limit))
        gold_limit["gold"] -= 1
        constrained.append(gold_limit)

        for limit in constrained:
            with self.subTest(limit=limit):
                result = self.plan(
                    target_checkpoint=15,
                    segment_hard_limits=segment_limits,
                    cumulative_hard_limits=limit,
                )
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, "no_feasible_integer_combination")

    def test_bounded_full_path_segment_material_limits_never_exceed_constraints(self):
        proposal = self.full_path_proposal()
        base_segments, base_cumulative = self.limits_from_result(proposal)
        inventory = {
            material: quantity + 1 for material, quantity in base_cumulative["materials"].items()
        }
        case_count = 0
        for segment in proposal.segments:
            endpoint = str(segment.to_checkpoint)
            for material in ("powder", "lower_enhance_stone"):
                planned = segment.materials[material]
                for boundary in independent_boundary_values(planned):
                    case_count += 1
                    with self.subTest(
                        endpoint=endpoint,
                        material=material,
                        label=boundary.primary_label,
                        aliases=boundary.aliases,
                        value=boundary.value,
                    ):
                        segment_limits = json.loads(json.dumps(base_segments))
                        segment_limits[endpoint]["materials"][material] = boundary.value
                        result = self.plan(
                            target_checkpoint=15,
                            inventory=inventory,
                            segment_hard_limits=segment_limits,
                            cumulative_hard_limits=base_cumulative,
                        )
                        if result.success:
                            self.assert_success_within_all_limits(
                                result, inventory, segment_limits, base_cumulative
                            )
                        else:
                            self.assert_structured_fail_closed(result)
        self.assertGreater(case_count, 0)

    def test_bounded_full_path_cumulative_material_limits_never_exceed_constraints(self):
        proposal = self.full_path_proposal()
        segment_limits, base_cumulative = self.limits_from_result(proposal)
        inventory = {
            material: quantity + 1 for material, quantity in base_cumulative["materials"].items()
        }
        case_count = 0
        for material in ("powder", "lower_enhance_stone"):
            planned = base_cumulative["materials"][material]
            for boundary in independent_boundary_values(planned):
                case_count += 1
                with self.subTest(
                    material=material,
                    label=boundary.primary_label,
                    aliases=boundary.aliases,
                    value=boundary.value,
                ):
                    cumulative_limit = json.loads(json.dumps(base_cumulative))
                    cumulative_limit["materials"][material] = boundary.value
                    result = self.plan(
                        target_checkpoint=15,
                        inventory=inventory,
                        segment_hard_limits=segment_limits,
                        cumulative_hard_limits=cumulative_limit,
                    )
                    if result.success:
                        self.assert_success_within_all_limits(
                            result, inventory, segment_limits, cumulative_limit
                        )
                    else:
                        self.assert_structured_fail_closed(result)
        self.assertEqual(case_count, 8)

    def test_bounded_full_path_inventory_materials_never_exceed_constraints(self):
        proposal = self.full_path_proposal()
        segment_limits, cumulative_limit = self.limits_from_result(proposal)
        generous_inventory = {
            material: quantity + 1 for material, quantity in cumulative_limit["materials"].items()
        }
        case_count = 0
        for material in ("powder", "lower_enhance_stone"):
            planned = cumulative_limit["materials"][material]
            for boundary in independent_boundary_values(planned):
                case_count += 1
                with self.subTest(
                    material=material,
                    label=boundary.primary_label,
                    aliases=boundary.aliases,
                    value=boundary.value,
                ):
                    inventory = dict(generous_inventory)
                    inventory[material] = boundary.value
                    result = self.plan(
                        target_checkpoint=15,
                        inventory=inventory,
                        segment_hard_limits=segment_limits,
                        cumulative_hard_limits=cumulative_limit,
                    )
                    if result.success:
                        self.assert_success_within_all_limits(
                            result, inventory, segment_limits, cumulative_limit
                        )
                    else:
                        self.assert_structured_fail_closed(result)
        self.assertEqual(case_count, 8)

    def test_incomplete_hard_limits_fail_closed(self):
        result = self.plan(
            cumulative_hard_limits={"materials": {"powder": 2}, "gold": 17600},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, "incomplete_hard_limits")

    def test_gold_hard_limit_shortfall_fails_closed(self):
        limit = {
            "materials": {"powder": 2, "lower_enhance_stone": 1},
            "gold": 17599,
        }
        result = self.plan(
            inventory={"powder": 5, "lower_enhance_stone": 1},
            segment_hard_limits={"3": limit},
            cumulative_hard_limits=limit,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, "no_feasible_integer_combination")

    def test_preview_requirement_mismatch_fails_closed(self):
        result = self.plan(preview_base_experience={"3": 1970})

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, "preview_requirement_mismatch")

    def test_invalid_nodes_empty_allow_list_and_priority_errors_fail_closed(self):
        cases = (
            ({"current_checkpoint": 1}, "invalid_checkpoint"),
            ({"target_checkpoint": 0}, "invalid_checkpoint_order"),
            ({"allowed_materials": []}, "empty_allowed_materials"),
            ({"material_priority": ["powder", "powder"]}, "invalid_material_priority"),
            ({"material_priority": ["powder"]}, "invalid_material_priority"),
            ({"inventory": {"powder": -1, "lower_enhance_stone": 1}}, "invalid_inventory"),
        )
        for overrides, expected_code in cases:
            with self.subTest(overrides=overrides):
                result = self.plan(**overrides)
                self.assertFalse(result.success)
                self.assertEqual(result.failure_code, expected_code)

    def test_no_feasible_integer_combination_fails_closed(self):
        result = self.plan(inventory={"powder": 1, "lower_enhance_stone": 1})

        self.assertFalse(result.success)
        self.assertEqual(result.failure_code, "no_feasible_integer_combination")

    def test_bounded_enumeration_never_exceeds_inventory_or_hard_limits(self):
        for powder in range(0, 25, 3):
            for stone in range(0, 3):
                with self.subTest(powder=powder, stone=stone):
                    inventory = {"powder": powder, "lower_enhance_stone": stone}
                    limits = {
                        "materials": dict(inventory),
                        "gold": powder * 1600 + stone * 14400,
                    }
                    result = self.plan(
                        inventory=inventory,
                        segment_hard_limits={"3": limits},
                        cumulative_hard_limits=limits,
                    )
                    if not result.success:
                        continue
                    self.assertEqual(result.mode, "validated_against_hard_limits")
                    consumption = result.cumulative_expected_consumption
                    self.assertLessEqual(consumption.gold, limits["gold"])
                    for material, quantity in consumption.materials.items():
                        self.assertLessEqual(quantity, inventory[material])
                        self.assertLessEqual(quantity, limits["materials"][material])
                        self.assertIn(material, {"powder", "lower_enhance_stone"})

    def test_candidate_compression_matches_complete_small_integer_grid(self):
        requirement = 1969
        for powder_limit in range(0, 21):
            for stone_limit in range(0, 3):
                with self.subTest(powder_limit=powder_limit, stone_limit=stone_limit):
                    candidates = []
                    for powder in range(powder_limit + 1):
                        for stone in range(stone_limit + 1):
                            base_experience = powder * POWDER_EXP + stone * LOWER_ENHANCE_STONE_EXP
                            effective_experience = page_effective_experience(base_experience)
                            if effective_experience < requirement:
                                continue
                            candidates.append(
                                (
                                    stone * LOWER_ENHANCE_STONE_USE_GOLD + powder * POWDER_GOLD,
                                    effective_experience - requirement,
                                    stone + powder,
                                    (-stone, -powder),
                                    {"lower_enhance_stone": stone, "powder": powder},
                                )
                            )
                    result = self.plan(inventory={"powder": powder_limit, "lower_enhance_stone": stone_limit})
                    if not candidates:
                        self.assertFalse(result.success)
                        continue
                    expected = min(candidates)
                    self.assertTrue(result.success)
                    self.assertEqual(result.segments[0].materials, expected[-1])

    def test_canonical_json_is_byte_stable(self):
        request = BudgetPlanningRequest.from_dict(request_payload())
        first = canonical_json(plan_budget(request))
        second = canonical_json(plan_budget(request))

        self.assertEqual(first, second)

    def test_heroic_uses_the_published_heroic_level_requirements(self):
        result = self.plan(rarity="Heroic")

        self.assertTrue(result.success)
        self.assertEqual(result.segments[0].required_base_experience, 1772)

    def test_cli_writes_canonical_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "request.json"
            json_path = root / "result.json"
            markdown_path = root / "result.md"
            input_path.write_text(json.dumps(request_payload()), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "budget-plan",
                        "--input",
                        str(input_path),
                        "--output-json",
                        str(json_path),
                        "--output-markdown",
                        str(markdown_path),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(output.getvalue().strip(), json_path.read_text(encoding="utf-8").strip())
            self.assertIn("离线预算与硬上限规划结果", markdown_path.read_text(encoding="utf-8"))

    def test_cli_returns_two_for_fail_closed_result(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            input_path = Path(temporary_directory) / "request.json"
            input_path.write_text(
                json.dumps(
                    request_payload(
                    allowed_materials=["powder", "legendary_enhance_stone"],
                    inventory={"powder": 20, "legendary_enhance_stone": 1},
                    material_priority=["legendary_enhance_stone", "powder"],
                    )
                ),
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()):
                exit_code = main(["budget-plan", "--input", str(input_path)])

        self.assertEqual(exit_code, 2)

    def test_cli_input_failures_use_stable_safe_summaries(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            missing = root / "secret-user-path.json"
            malformed = root / "malformed.json"
            wrong_shape = root / "list.json"
            malformed.write_text("{private-token", encoding="utf-8")
            wrong_shape.write_text("[]", encoding="utf-8")
            cases = (
                (missing, "input_read_error", "secret-user-path"),
                (malformed, "invalid_json", "private-token"),
                (wrong_shape, "invalid_request", "list.json"),
            )
            for path, code, forbidden in cases:
                with self.subTest(path=path):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = main(["budget-plan", "--input", str(path)])
                    payload = json.loads(output.getvalue())
                    self.assertEqual(exit_code, 2)
                    self.assertEqual(payload["failure"]["code"], code)
                    self.assertNotIn(forbidden, output.getvalue())
                    self.assertNotIn(str(path), output.getvalue())

    def test_failure_markdown_sanitizes_dynamic_detail(self):
        hostile_material = "bad\n| injected | <script>alert(1)</script> `code`"
        result = self.plan(
            allowed_materials=[hostile_material],
            inventory={hostile_material: 1},
            material_priority=[hostile_material],
        )

        markdown = render_markdown(result)
        self.assertFalse(result.success)
        self.assertNotIn("\n| injected |", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertIn("\\| injected \\|", markdown)
        self.assertIn("&lt;script&gt;", markdown)


if __name__ == "__main__":
    unittest.main()
