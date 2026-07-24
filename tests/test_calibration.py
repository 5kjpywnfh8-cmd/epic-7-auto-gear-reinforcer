import unittest
from unittest.mock import patch

from src.e7_enhance.calibration import (
    DP_ASSIST_CONFIGS,
    CalibrationOptions,
    aggregate_resource_calibration_runs,
    calibrate_selected_policies,
    calibrate_policies,
    candidate_policies,
    checkpoint_state,
    continuation_decision_state,
    conversion_plan_for_keys,
    conversion_plan_for_gear,
    dp_assisted_policies,
    dynamic_expected_score_min,
    effective_marginal_threshold,
    expected_final_reforge_score,
    expected_final_reforge_speed,
    final_success_breakdown,
    is_successful_final_with_conversion,
    marginal_decision_for_gear,
    policy_sort_key,
    resource_calibration_publishable,
)
from src.e7_enhance.models import Gear
from src.e7_enhance.score_engine import evaluate_gear


class CalibrationTest(unittest.TestCase):
    def test_dp_assist_uses_current_resource_baseline_only_for_published_ranks(self):
        self.assertEqual(DP_ASSIST_CONFIGS[("normal_85", "Epic")]["cost_per_baili_score"], 799.2)
        self.assertEqual(DP_ASSIST_CONFIGS[("rift_85", "Epic")]["cost_per_baili_score"], 332.6)
        self.assertNotIn(("normal_85", "Heroic"), DP_ASSIST_CONFIGS)

    def test_resource_calibration_aggregates_raw_numerator_and_denominator_not_seed_ratios(self):
        result = aggregate_resource_calibration_runs(
            [
                {"seed": 1, "total_stamina": 100.0, "total_baili_score": 20.0, "successes": 2},
                {"seed": 2, "total_stamina": 300.0, "total_baili_score": 30.0, "successes": 3},
            ]
        )

        self.assertEqual(result["total_stamina"], 400.0)
        self.assertEqual(result["total_baili_score"], 50.0)
        self.assertEqual(result["nonzero_terminal_count"], 5)
        self.assertEqual(result["cost_per_baili_score"], 8.0)
        self.assertNotEqual(result["cost_per_baili_score"], (5.0 + 10.0) / 2)

    def test_resource_calibration_rejects_large_latter_half_drift(self):
        aggregate = aggregate_resource_calibration_runs(
            [
                {"seed": 1, "total_stamina": 1000.0, "total_baili_score": 100.0, "successes": 100},
                {"seed": 2, "total_stamina": 1000.0, "total_baili_score": 200.0, "successes": 100},
                {"seed": 3, "total_stamina": 1000.0, "total_baili_score": 200.0, "successes": 100},
            ]
        )

        self.assertGreater(aggregate["latter_half_relative_deviation"], 0.10)
        self.assertFalse(resource_calibration_publishable(aggregate, "Epic"))

    def test_candidate_policies_are_stage_threshold_search_grid(self):
        policies = candidate_policies()

        self.assertGreater(len(policies), 3)
        self.assertTrue(all(policy.name for policy in policies))
        self.assertTrue(any(policy.decision_mode == "marginal" for policy in policies))
        self.assertGreaterEqual(len({policy.family for policy in policies}), 5)
        self.assertLessEqual(min(policy.expected_score_min[12] for policy in policies), 58)
        self.assertGreaterEqual(max(policy.expected_score_min[12] for policy in policies), 68)

    def test_candidate_policies_include_named_baili_and_legacy_controls(self):
        policies = {policy.name: policy for policy in candidate_policies()}

        self.assertIn("global_baili_marginal_mid", policies)
        self.assertEqual(policies["global_baili_marginal_mid"].decision_mode, "marginal")
        self.assertEqual(policies["global_baili_marginal_mid"].marginal_variant, "global")

        for name in ("baili_marginal_low", "baili_marginal_mid", "baili_marginal_high"):
            self.assertIn(name, policies)
            self.assertEqual(policies[name].decision_mode, "marginal")
            self.assertEqual(policies[name].marginal_score_scope, "formal_baili")

        self.assertIn("target_marginal_mid", policies)
        self.assertEqual(policies["target_marginal_mid"].decision_mode, "marginal")
        self.assertEqual(policies["target_marginal_mid"].marginal_score_scope, "target_with_future")
        self.assertIn("score_target_low_speed_low", policies)
        self.assertIn("score_strategy_late_strict_speed_high", policies)

    def test_candidate_policies_include_set_group_optimized_strategies(self):
        policies = {policy.name: policy for policy in candidate_policies()}

        expected = {
            "set_group_baili_marginal_mid": "set_group",
            "category_baili_marginal_mid": "category",
            "category_set_group_baili_marginal_mid": "category_set_group",
            "speed_set_specialized": "speed_set_specialized",
        }
        for name, variant in expected.items():
            self.assertIn(name, policies)
            self.assertEqual(policies[name].decision_mode, "marginal")
            self.assertEqual(policies[name].marginal_variant, variant)
            self.assertEqual(policies[name].marginal_score_scope, "formal_baili")

    def test_expected_final_reforge_score_uses_rift_roll_expectation(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 13, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        normal = expected_final_reforge_score(gear, "normal_85")["expected_final_reforge_score"]
        rift = expected_final_reforge_score(gear, "rift_85")["expected_final_reforge_score"]

        self.assertGreaterEqual(rift, normal)

    def test_85_reforge_projection_ignores_legacy_eligibility(self):
        base = {
            "set": "Speed",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 9,
            "level": 85,
            "rank": "Epic",
            "substats": [
                {"type": "Speed", "value": 10, "rolls": 3},
                {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                {"type": "CriticalHitDamagePercent", "value": 14, "rolls": 2},
                {"type": "AttackPercent", "value": 12, "rolls": 2},
            ],
        }
        without_legacy_flag = Gear.from_dict(base)
        with_legacy_flag = Gear.from_dict({**base, "reforgeEligible": True})

        self.assertEqual(
            expected_final_reforge_score(without_legacy_flag, "normal_85"),
            expected_final_reforge_score(with_legacy_flag, "normal_85"),
        )
        self.assertEqual(
            expected_final_reforge_speed(without_legacy_flag, "normal_85"),
            expected_final_reforge_speed(with_legacy_flag, "normal_85"),
        )

    def test_expected_final_reforge_speed_uses_final_speed_target_not_current_gate(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 13, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        self.assertGreater(expected_final_reforge_speed(gear, "normal_85"), 13)

    def test_one_roll_invalid_substat_can_be_conversion_candidate(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "rank": "Epic",
                "level": 90,
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 12, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 18, "rolls": 3},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                ],
            }
        )

        plan = conversion_plan_for_gear(gear, "normal_85")

        self.assertTrue(plan["conversion_needed"])
        self.assertEqual(plan["conversion_candidate"]["key"], "res")
        self.assertLessEqual(plan["conversion_candidate"]["rolls"], 2)
        self.assertIn(plan["conversion_target_stat"], {"atkPct", "atkFlat"})
        self.assertGreater(plan["conversion_expected_gain"], 0)
        if plan["conversion_target_stat"] == "atkPct":
            self.assertEqual(plan["conversion_expected_gain"], 7)

    def test_two_hit_invalid_substat_is_not_conversion_candidate(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "rank": "Epic",
                "level": 90,
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 12, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 18, "rolls": 3},
                    {"type": "EffectResistancePercent", "value": 20, "rolls": 3},
                ],
            }
        )

        self.assertFalse(conversion_plan_for_gear(gear, "normal_85")["conversion_needed"])

    def test_success_line_allows_strong_keep_with_conversion_below_baili(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "rank": "Epic",
                "level": 90,
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 14, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 24, "rolls": 4},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                ],
            }
        )
        evaluation = evaluate_gear(gear)

        self.assertTrue(is_successful_final_with_conversion(evaluation, speed=10, item_source="normal_85"))

    def test_dynamic_threshold_uses_profile_baili_floor_for_pure_tank(self):
        policy = next(item for item in candidate_policies() if item.name == "score_baili_elite_speed_low")
        gear = Gear.from_dict(
            {
                "set": "HealthSet",
                "slot": "Ring",
                "mainStat": {"type": "HealthPercent", "value": 60},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "HealthPercent", "value": 22, "rolls": 4},
                    {"type": "DefensePercent", "value": 18, "rolls": 3},
                    {"type": "Speed", "value": 8, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                ],
            }
        )

        self.assertEqual(dynamic_expected_score_min(gear, policy), 58)

    def test_dynamic_threshold_applies_to_other_baili_profiles(self):
        policy = next(item for item in candidate_policies() if item.name == "score_baili_elite_speed_low")
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 18, "rolls": 3},
                    {"type": "Speed", "value": 8, "rolls": 2},
                    {"type": "HealthPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        self.assertEqual(dynamic_expected_score_min(gear, policy), 63)

    def test_policy_sort_uses_formal_baili_efficiency(self):
        better_baili = {
            "cost_per_baili_score": 100,
            "baili_score_per_1000_stamina": 10,
            "cost_per_target_score": 200,
            "target_score_per_1000_stamina": 5,
            "success_rate": 0.01,
        }
        better_target_only = {
            "cost_per_baili_score": 120,
            "baili_score_per_1000_stamina": 8,
            "cost_per_target_score": 50,
            "target_score_per_1000_stamina": 20,
            "success_rate": 0.02,
        }

        self.assertLess(policy_sort_key(better_baili), policy_sort_key(better_target_only))

    def test_future_only_piece_is_auxiliary_not_formal_success(self):
        gear = Gear.from_dict(
            {
                "set": "AttackSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 20, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 14, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 25, "rolls": 4},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                ],
            }
        )
        evaluation = evaluate_gear(gear)

        self.assertEqual(evaluation.target_score_source_row, "R61")
        breakdown = final_success_breakdown(evaluation, speed=20, item_source="normal_85")
        self.assertFalse(breakdown["final_success"])
        self.assertEqual(breakdown["native_baili_score"], 0.0)
        self.assertEqual(breakdown["target_score"], 0.0)

    def test_marginal_decision_reports_tier_probability_and_cost(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                    {"type": "CriticalHitChancePercent", "value": 12, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 18, "rolls": 3},
                    {"type": "Speed", "value": 8, "rolls": 2},
                ],
            }
        )

        decision = marginal_decision_for_gear(gear, "normal_85")

        self.assertEqual(decision["checkpoint"], 9)
        self.assertEqual(decision["next_checkpoint"], 12)
        self.assertGreater(decision["marginal_stamina_cost"], 0)
        self.assertGreaterEqual(decision["best_value_per_stamina"], 0)
        self.assertGreaterEqual(decision["best_cross_tier_probability"], 0)
        self.assertLessEqual(decision["best_cross_tier_probability"], 1)
        self.assertIn("current_tier", decision["candidates"][0])
        self.assertIn("next_tier_distance", decision["candidates"][0])
        self.assertIn("conversion_tier_delta", decision["candidates"][0])

    def test_marginal_candidates_include_formal_speed_rows_but_not_future(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 20, "rolls": 3},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                ],
            }
        )

        rows = {candidate["source_row"] for candidate in marginal_decision_for_gear(gear, "normal_85")["candidates"]}

        self.assertIn("R2", rows)
        self.assertIn("R3", rows)
        self.assertNotIn("R61", rows)

    def test_candidate_policies_do_not_enable_dp_assist_by_default(self):
        policies = {policy.name: policy for policy in candidate_policies()}

        self.assertNotIn("rift_epic_dp_assisted", policies)

    def test_candidate_policies_can_include_scoped_dp_assist(self):
        policies = {policy.name: policy for policy in candidate_policies(include_dp_assist=True, item_source="rift_85", rank="Epic")}

        self.assertIn("rift_epic_dp_assisted", policies)
        self.assertEqual(policies["rift_epic_dp_assisted"].decision_mode, "dp_assisted")
        self.assertEqual(policies["rift_epic_dp_assisted"].base_policy_name, "score_target_high_speed_mid")
        self.assertEqual(policies["rift_epic_dp_assisted"].dp_checkpoints, (0, 3, 6, 9, 12))

    def test_dp_assisted_calls_route_solver_at_all_pre_final_checkpoints(self):
        policy = dp_assisted_policies("normal_85", "Epic")[0]
        options = CalibrationOptions(item_source="normal_85", rank="Epic", enable_dp_assist=True)
        plus6 = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 6,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 3},
                    {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                    {"type": "CriticalHitDamagePercent", "value": 14, "rolls": 2},
                    {"type": "AttackPercent", "value": 12, "rolls": 2},
                ],
            }
        )
        plus9 = Gear.from_dict({**plus6.to_dict(), "enhance": 9})

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            mocked.return_value = {
                "action": "continue",
                "continue_utility": 1.0,
                "expected_utility": 1.0,
            }
            plus6_decision = continuation_decision_state(checkpoint_state(plus6, None, options), policy, options)
            plus9_decision = continuation_decision_state(checkpoint_state(plus9, None, options), policy, options)

        self.assertEqual(plus6_decision["dp_call_count"], 1)
        self.assertIn("6", plus6_decision["dp_covered_checkpoints"])
        self.assertEqual(plus9_decision["dp_call_count"], 1)
        self.assertIn("9", plus9_decision["dp_covered_checkpoints"])

    def test_enable_dp_assist_false_keeps_calibration_policy_set_unchanged(self):
        result = calibrate_policies(CalibrationOptions(runs=50, seed=3, item_source="rift_85", rank="Epic", top_limit=50))

        names = {policy["policy_name"] for policy in result["policies"]}
        self.assertNotIn("rift_epic_dp_assisted", names)
        self.assertEqual(result["enable_dp_assist"], False)
        self.assertTrue(all(policy["dp_call_count"] == 0 for policy in result["policies"]))

    def test_route_solver_sample_limit_can_disable_dp_calls(self):
        result = calibrate_selected_policies(
            CalibrationOptions(
                runs=50,
                seed=3,
                item_source="rift_85",
                rank="Epic",
                top_limit=1,
                enable_dp_assist=True,
                route_solver_sample_limit=0,
            ),
            ["rift_epic_dp_assisted"],
        )

        self.assertEqual(result["policies"][0]["dp_call_count"], 0)

    def test_marginal_candidates_report_required_fields_at_each_checkpoint(self):
        required = {
            "category",
            "source_row",
            "current_tier",
            "expected_final_tier",
            "current_target_score",
            "expected_final_target_score",
            "next_tier_distance",
            "cross_tier_probability",
            "expected_gain",
            "conversion_needed",
            "conversion_target_stat",
            "conversion_tier_delta",
            "projected_conversion_tier_delta",
            "value_per_stamina",
        }
        for enhance in (0, 3, 6, 9, 12):
            gear = Gear.from_dict(
                {
                    "set": "SpeedSet",
                    "slot": "Weapon",
                    "mainStat": {"type": "Attack", "value": 525},
                    "enhance": enhance,
                    "rank": "Epic",
                    "level": 85,
                    "substats": [
                        {"type": "Speed", "value": 18, "rolls": 4},
                        {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                        {"type": "CriticalHitDamagePercent", "value": 20, "rolls": 3},
                        {"type": "AttackPercent", "value": 20, "rolls": 3},
                    ],
                }
            )

            decision = marginal_decision_for_gear(gear, "normal_85")
            rows = {candidate["source_row"] for candidate in decision["candidates"]}

            self.assertGreater(decision["marginal_stamina_cost"], 0)
            self.assertIn("R2", rows)
            self.assertIn("R3", rows)
            if enhance in (0, 3):
                self.assertNotIn("R61", rows)
            for candidate in decision["candidates"]:
                self.assertTrue(required.issubset(candidate), f"{enhance}: {candidate}")
                self.assertGreaterEqual(candidate["cross_tier_probability"], 0)
                self.assertLessEqual(candidate["cross_tier_probability"], 1)

    def test_marginal_non_speed_set_speed_piece_uses_r4_when_supported(self):
        gear = Gear.from_dict(
            {
                "set": "CriticalSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 20, "rolls": 3},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                ],
            }
        )

        rows = {candidate["source_row"] for candidate in marginal_decision_for_gear(gear, "normal_85")["candidates"]}

        self.assertIn("R4", rows)

    def test_marginal_speed_set_candidate_rejects_speed_only_support(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                ],
            }
        )

        rows = {candidate["source_row"] for candidate in marginal_decision_for_gear(gear, "normal_85")["candidates"]}

        self.assertIn("R2", rows)
        self.assertNotIn("R3", rows)
        self.assertNotIn("R4", rows)

    def test_set_group_variant_keeps_formal_scope_and_adjusts_threshold_by_set_category(self):
        policies = {policy.name: policy for policy in candidate_policies()}
        global_policy = policies["global_baili_marginal_mid"]
        specialized = policies["category_set_group_baili_marginal_mid"]
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 20, "rolls": 3},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                ],
            }
        )
        decision = marginal_decision_for_gear(gear, "normal_85")

        self.assertEqual(decision["best_category_group"], "speed")
        self.assertEqual(decision["best_set_group"], "speed")
        self.assertLess(
            effective_marginal_threshold(decision, specialized, 9),
            effective_marginal_threshold(decision, global_policy, 9),
        )
        rows = {candidate["source_row"] for candidate in decision["candidates"]}
        self.assertNotIn("R61", rows)

    def test_conversion_plan_reports_cross_tier_gain(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 15, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                ],
            }
        )

        plan = conversion_plan_for_keys(
            gear,
            "normal_85",
            {"spd", "crit", "atkPct"},
            [(50, 1, 0)],
            current_effective=44,
            projected_effective=44,
        )

        self.assertTrue(plan["conversion_needed"])
        self.assertEqual(plan["conversion_tier_delta"], 1)
        self.assertEqual(plan["projected_conversion_tier_delta"], 1)

    def test_calibration_ranks_policies_by_formal_baili_efficiency(self):
        result = calibrate_policies(CalibrationOptions(runs=250, seed=5, item_source="normal_85"))

        self.assertEqual(result["calibration_runs"], 250)
        self.assertEqual(result["seed"], 5)
        self.assertEqual(result["item_source"], "normal_85")
        self.assertEqual(result["ranking_metric"], "cost_per_baili_score")
        self.assertGreaterEqual(result["candidate_policy_count"], 5)
        self.assertIn("转换友好", result["strategy_families"])
        self.assertLessEqual(len(result["policies"]), 5)
        costs = [item["cost_per_baili_score"] for item in result["policies"] if item["cost_per_baili_score"] is not None]
        self.assertEqual(costs, sorted(costs))
        self.assertEqual(result["best_policy"], result["policies"][0]["policy_name"])
        self.assertEqual(result["success_definition"]["source"], "套装属性与装等计算表.md")
        self.assertEqual(
            result["success_definition"]["main_score_scope"],
            "R2-R58 formal baili score; R61 future is auxiliary only",
        )
        self.assertIn("thresholds", result["policies"][0])
        self.assertIn("expected_final_reforge_speed_min", result["policies"][0]["thresholds"])
        self.assertIn("stop_rate_by_checkpoint", result["policies"][0])
        self.assertIn("conversion_needed_rate", result["policies"][0])
        self.assertIn("baili_score_per_1000_stamina", result["policies"][0])
        self.assertIn("avg_success_baili_score", result["policies"][0])
        self.assertIn("baili_tier_rate", result["policies"][0])
        self.assertIn("native_success_rate", result["policies"][0])
        self.assertIn("rescued_success_rate", result["policies"][0])
        self.assertIn("final_success_rate", result["policies"][0])
        self.assertIn("cost_per_final_success", result["policies"][0])
        self.assertIn("cost_per_native_success", result["policies"][0])
        self.assertIn("cost_per_rescued_success", result["policies"][0])
        self.assertIn("cost_per_native_baili_score", result["policies"][0])
        self.assertIn("converted_effective_score_per_1000_stamina", result["policies"][0])
        self.assertIn("final_score", result["policies"][0])
        self.assertIn("final_score_per_1000_stamina", result["policies"][0])
        self.assertIn("cost_per_final_score", result["policies"][0])
        self.assertIn("native_target_score", result["policies"][0])
        self.assertIn("rescued_target_score", result["policies"][0])
        self.assertIn("target_score", result["policies"][0])
        self.assertIn("target_score_per_1000_stamina", result["policies"][0])
        self.assertIn("cost_per_target_score", result["policies"][0])
        self.assertIn("policy_family", result["policies"][0])
        self.assertIn("target_score_by_category", result["policies"][0])
        self.assertIn("target_score_share_by_category", result["policies"][0])
        self.assertIn("success_count_by_category", result["policies"][0])
        self.assertIn("baili_score_by_set", result["policies"][0])
        self.assertIn("cost_per_baili_score_by_set", result["policies"][0])
        self.assertIn("success_count_by_set", result["policies"][0])
        self.assertIn("stop_rate_by_set", result["policies"][0])
        self.assertIn("category_by_set_matrix", result["policies"][0])
        self.assertIn("native_baili_efficiency", result["policies"][0])
        self.assertIn("rescued_baili_efficiency_without_conversion_cost", result["policies"][0])
        self.assertIn("rescued_baili_efficiency_with_conversion_gold_cost", result["policies"][0])
        self.assertIn("conversion_gold_cost", result["policies"][0])
        self.assertIn("conversion_needed_count", result["policies"][0])
        self.assertIn("conversion_target_stat_distribution", result["policies"][0])
        self.assertIn("marginal_value_per_stamina_avg", result["policies"][0])
        self.assertIn("marginal_expected_gain_avg", result["policies"][0])
        self.assertIn("marginal_cross_tier_probability_avg", result["policies"][0])
        self.assertAlmostEqual(
            result["policies"][0]["final_success_rate"],
            result["policies"][0]["native_success_rate"] + result["policies"][0]["rescued_success_rate"],
            places=4,
        )

    def test_worker_option_keeps_small_calibration_deterministic(self):
        single = calibrate_policies(CalibrationOptions(runs=250, seed=7, item_source="normal_85", workers=1))
        parallel = calibrate_policies(CalibrationOptions(runs=250, seed=7, item_source="normal_85", workers=2))

        self.assertEqual(parallel["workers"], 2)
        self.assertEqual(single["best_policy"], parallel["best_policy"])
        self.assertEqual(single["policies"][0]["cost_per_baili_score"], parallel["policies"][0]["cost_per_baili_score"])

    def test_top_limit_can_return_full_policy_table(self):
        result = calibrate_policies(CalibrationOptions(runs=50, seed=9, item_source="normal_85", top_limit=10))

        self.assertEqual(len(result["policies"]), 10)

    def test_conversion_cost_uses_the_fixed_gold_baseline(self):
        result = calibrate_policies(CalibrationOptions(runs=250, seed=11, item_source="normal_85", top_limit=20))
        policy = result["policies"][0]

        self.assertEqual(policy["conversion_gold_cost"], [100000])
        self.assertEqual(
            sorted(policy["rescued_baili_efficiency_with_conversion_gold_cost"]),
            ["100000"],
        )


if __name__ == "__main__":
    unittest.main()
