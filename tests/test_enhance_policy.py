import unittest
from pathlib import Path
from unittest.mock import patch

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.gui_support import load_gear_file, suggest_from_form
from src.e7_enhance.models import Gear


class EnhancePolicyTest(unittest.TestCase):
    def test_plus3_single_offstat_keeps_output_as_first_conversion_candidate(self):
        result = suggest_from_form(load_gear_file(Path("建议结果") / "14.json"))

        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")
        self.assertEqual(result["summary"]["next_check_at"], 6)
        self.assertEqual(result["summary"]["target_profile"], "输出")
        candidates = result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"]
        self.assertEqual(candidates[0]["category"], "输出")
        self.assertTrue(candidates[0]["is_conversion_candidate"])
        self.assertEqual(candidates[0]["matched_substats"], ["攻击%", "暴率", "爆伤"])
        self.assertEqual(candidates[0]["unmatched_substats"], ["命中"])
        self.assertEqual(candidates[0]["priority_layer"], "高优先级")

    def test_speed_main_boot_full_output_category_continues_without_speed_substat(self):
        gear = Gear.from_dict({"set": "Critical", "slot": "Boots", "mainStat": {"type": "Speed", "value": 45}, "enhance": 3, "level": 85, "rank": "Epic", "substats": [{"type": "AttackPercent", "value": 8, "rolls": 2}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1}, {"type": "Attack", "value": 40, "rolls": 1}]})

        result = advise_gear(gear, item_source="normal_85")

        self.assertEqual(result["summary"]["recommendation"], "continue")
        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        self.assertEqual(basis["route"], "速度主属性鞋完整分类继续")
        self.assertEqual(basis["selected_full_category"], "输出")

    def test_speed_main_boot_rejects_speed_substat_before_lightweight_prediction(self):
        gear = Gear.from_dict({"set": "Critical", "slot": "Boots", "mainStat": {"type": "Speed", "value": 45}, "enhance": 0, "level": 85, "rank": "Epic", "substats": [{"type": "Speed", "value": 4, "rolls": 1}, {"type": "AttackPercent", "value": 4, "rolls": 1}, {"type": "CriticalHitChancePercent", "value": 3, "rolls": 1}, {"type": "CriticalHitDamagePercent", "value": 4, "rolls": 1}]})

        with self.assertRaisesRegex(ValueError, "Invalid substats for boot"):
            advise_gear(gear, item_source="normal_85")

    def test_non_speed_boot_with_speed_uses_neither_speed_protection_nor_low_speed_boot_route(self):
        gear = Gear.from_dict({"set": "Critical", "slot": "Boots", "mainStat": {"type": "AttackPercent", "value": 65}, "enhance": 3, "level": 85, "rank": "Epic", "substats": [{"type": "Speed", "value": 8, "rolls": 2}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1}, {"type": "Attack", "value": 40, "rolls": 1}]})

        result = advise_gear(gear, item_source="normal_85")

        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        self.assertNotEqual(basis["route"], "多跳速度高价值路线")
        self.assertNotEqual(basis["route"], "低速鞋完整分类继续")
        self.assertEqual(basis["speed_protection_eligible"], False)

    def test_uncalibrated_complete_category_is_review_with_group_and_bounds(self):
        gear = Gear.from_dict({"set": "Health", "slot": "Boots", "mainStat": {"type": "HealthPercent", "value": 65}, "enhance": 0, "level": 85, "rank": "Epic", "substats": [{"type": "Health", "value": 180, "rolls": 1}, {"type": "DefensePercent", "value": 5, "rolls": 1}, {"type": "Defense", "value": 30, "rolls": 1}, {"type": "EffectResistancePercent", "value": 4, "rolls": 1}]})

        result = advise_gear(gear, item_source="normal_85")

        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")
        self.assertEqual(basis["route"], "候选体系待 +6 精确复核")
        self.assertIsNotNone(basis["calibration_group"])
        self.assertIsNone(basis["calibration_thresholds"])
        self.assertGreaterEqual(basis["theoretical_upper_bound"], basis["theoretical_lower_bound"])

    def test_complete_category_uses_only_its_exact_calibration_group_threshold(self):
        gear = Gear.from_dict({"set": "Critical", "slot": "Weapon", "mainStat": {"type": "Attack", "value": 525}, "enhance": 0, "level": 85, "rank": "Epic", "substats": [{"type": "AttackPercent", "value": 8, "rolls": 1}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1}, {"type": "Speed", "value": 3, "rolls": 1}]})
        rule = {
            "group": {"item_source": "normal_85", "rank": "Epic", "slot": "weapon", "main_stat_class": "left_fixed", "set_group": "output", "selected_category": "输出"},
            "continue": {"expected_final_reforge_score_min": 1, "expected_final_target_score_min": 0, "current_effective_score_min": 1, "remaining_hits_min": 1, "formal_cross_tier_probability_min": 0},
        }

        with patch("src.e7_enhance.lightweight_calibration.calibration_rule", return_value=rule):
            result = advise_gear(gear, item_source="normal_85")

        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        self.assertEqual(result["summary"]["recommendation"], "continue")
        self.assertEqual(basis["route"], "完整分类校准继续")
        self.assertEqual(
            basis["calibration_group"],
            {**rule["group"], "current_valid_substat_count": "4", "feasible_valid_substat_count": "4"},
        )

    def test_plus0_three_matching_substats_stays_cautious_with_calibration_evidence(self):
        gear = Gear.from_dict(
            {
                "set": "Critical",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 0,
                "level": 85,
                "rank": "Heroic",
                "substats": [
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                ],
            }
        )
        rule = {"continue": {"expected_final_reforge_score_min": 1, "terminal_reach_probability_min": 0}}

        with patch("src.e7_enhance.lightweight_calibration.calibration_rule", return_value=rule):
            result = advise_gear(gear, item_source="normal_85")

        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")
        candidate = result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"][0]
        self.assertEqual(candidate["category"], "输出")
        self.assertEqual(candidate["current_valid_substat_count"], 3)

    def test_output_armor_three_legal_substats_is_a_cautious_candidate(self):
        gear = Gear.from_dict(
            {
                "set": "Critical",
                "slot": "Armor",
                "mainStat": {"type": "Defense", "value": 310},
                "enhance": 3,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 4, "rolls": 1},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 2},
                    {"type": "EffectivenessPercent", "value": 4, "rolls": 1},
                ],
            }
        )

        result = advise_gear(gear, item_source="normal_85")

        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")
        candidate = result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"][0]
        self.assertEqual(candidate["category"], "输出")
        self.assertEqual(candidate["current_valid_substat_count"], 3)
        self.assertEqual(candidate["feasible_valid_substat_count"], 3)
        self.assertTrue(candidate["qualified"])

    def test_plus_12_can_stop_when_core_direction_is_bad(self):
        gear = Gear.from_dict(
            {
                "set": "Attack",
                "slot": "Ring",
                "mainStat": {"type": "AttackPercent", "value": 65},
                "enhance": 12,
                "substats": [
                    {"type": "EffectResistancePercent", "value": 15},
                    {"type": "HealthPercent", "value": 8},
                    {"type": "Health", "value": 220},
                    {"type": "EffectivenessPercent", "value": 12},
                ],
                "rollHistory": [
                    {"enhance": 3, "type": "EffectResistancePercent", "value": 6},
                    {"enhance": 6, "type": "DefensePercent", "value": 4},
                    {"enhance": 9, "type": "Health", "value": 110},
                    {"enhance": 12, "type": "EffectivenessPercent", "value": 6},
                ],
            }
        )

        result = advise_gear(gear)

        self.assertEqual(result["summary"]["recommendation"], "stop")
        self.assertEqual(result["summary"]["next_check_at"], 15)

    def test_plus_12_good_speed_piece_can_continue_but_uses_default_strategy(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 12,
                "substats": [
                    {"type": "Speed", "value": 23},
                    {"type": "EffectivenessPercent", "value": 5},
                    {"type": "CriticalHitDamagePercent", "value": 14},
                    {"type": "HealthPercent", "value": 8},
                ],
                "rollHistory": [
                    {"enhance": 3, "type": "Speed", "value": 4},
                    {"enhance": 6, "type": "Speed", "value": 4},
                    {"enhance": 9, "type": "Speed", "value": 5},
                    {"enhance": 12, "type": "Speed", "value": 5},
                ],
            }
        )

        result = advise_gear(gear)

        self.assertEqual(result["summary"]["recommendation"], "continue")
        self.assertEqual(result["debug"]["default_strategy"]["policy_name"], "normal_epic_dp_assisted")
        self.assertTrue(result["summary"]["reasons"])

    def test_roll_hit_analysis_uses_effective_profile_when_baili_does_not_match(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "substats": [
                    {"type": "Speed", "value": 18},
                    {"type": "HealthPercent", "value": 5},
                    {"type": "AttackPercent", "value": 9},
                    {"type": "CriticalHitChancePercent", "value": 5},
                ],
                "rollHistory": [
                    {"enhance": 3, "type": "Speed", "value": 4},
                    {"enhance": 6, "type": "AttackPercent", "value": 5},
                ],
            }
        )

        result = advise_gear(gear)

        self.assertEqual(result["summary"]["recommendation"], "stop")
        self.assertTrue(all(hit["valid"] for hit in result["debug"]["roll_hit_analysis"]))

    def test_normal_epic_default_uses_dp_assist_at_plus_9(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 9, "rolls": 3},
                    {"type": "HealthPercent", "value": 15, "rolls": 2},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            mocked.return_value = {
                "action": "stop",
                "continue_utility": -2.5,
                "expected_utility": 0.0,
                "expected_formal_baili_score": 5.0,
                "expected_incremental_stamina": 1000.0,
                "best_target_category": "tank",
                "best_source_row": "R17-R22",
            }
            result = advise_gear(gear, item_source="normal_85")

        self.assertEqual(result["debug"]["strategy_version"], "baili-formal-dp-v1")
        self.assertEqual(result["debug"]["default_strategy"]["policy_name"], "normal_epic_dp_assisted")
        self.assertTrue(result["debug"]["dp_assist"]["enabled"])
        self.assertTrue(result["debug"]["dp_assist"]["overrode_baseline"])
        self.assertEqual(result["debug"]["dp_assist"]["dp_decision"], "stop")
        self.assertEqual(result["summary"]["recommendation"], "stop")

    def test_rift_epic_default_uses_dp_assist(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 9, "rolls": 3},
                    {"type": "HealthPercent", "value": 15, "rolls": 2},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            mocked.return_value = {
                "action": "continue",
                "continue_utility": 1.0,
                "expected_utility": 1.0,
                "expected_formal_baili_score": 0.0,
                "expected_terminal_value": 2.0,
                "expected_incremental_stamina": 100.0,
                "best_target_category": "可转换",
                "best_source_row": "terminal-convert",
            }
            result = advise_gear(gear, item_source="rift_85")

        mocked.assert_called_once()
        self.assertEqual(result["debug"]["default_strategy"]["policy_name"], "rift_epic_dp_assisted")
        self.assertTrue(result["debug"]["dp_assist"]["enabled"])

    def test_normal_epic_plus_6_uses_dp(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 6,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 8, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 8, "rolls": 2},
                    {"type": "CriticalHitDamagePercent", "value": 12, "rolls": 2},
                    {"type": "AttackPercent", "value": 10, "rolls": 2},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            mocked.return_value = {
                "action": "continue",
                "continue_utility": 2.5,
                "expected_utility": 2.5,
                "expected_formal_baili_score": 0.0,
                "expected_terminal_value": 3.0,
                "expected_incremental_stamina": 1000.0,
                "best_target_category": "可转换",
                "best_source_row": "-",
            }
            result = advise_gear(gear, item_source="normal_85")

        mocked.assert_called_once()
        self.assertTrue(result["debug"]["dp_assist"]["enabled"])
        self.assertEqual(result["debug"]["dp_assist"]["dp_decision"], "continue")

    def test_normal_epic_plus_3_all_valid_uses_lightweight_prediction_before_plus6_dp(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 3,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 4, "rolls": 1},
                    {"type": "HealthPercent", "value": 12, "rolls": 2},
                    {"type": "DefensePercent", "value": 5, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        result = advise_gear(gear, item_source="normal_85")

        self.assertEqual(result["debug"]["dp_assist"]["checkpoint"], 3)
        self.assertEqual(result["debug"]["dp_assist"]["decision_mode"], "lightweight_prediction")
        self.assertEqual(result["debug"]["dp_assist"]["dp_decision"], "lightweight_review")
        self.assertIsNotNone(result["debug"]["dp_assist"]["lightweight_basis"])

    def test_normal_epic_dp_covers_plus6_and_later_checkpoints(self):
        for checkpoint in (6, 9, 12):
            gear = Gear.from_dict(
                {
                    "set": "Speed",
                    "slot": "Helmet",
                    "mainStat": {"type": "Health", "value": 2700},
                    "enhance": checkpoint,
                    "rank": "Epic",
                    "substats": [
                        {"type": "Speed", "value": 4, "rolls": 1},
                        {"type": "HealthPercent", "value": 8, "rolls": 1},
                        {"type": "DefensePercent", "value": 5, "rolls": 1},
                        {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                    ],
                }
            )
            with self.subTest(checkpoint=checkpoint), patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
                mocked.return_value = {
                    "action": "continue",
                    "continue_utility": 1.0,
                    "expected_utility": 1.0,
                    "expected_formal_baili_score": 0.0,
                    "expected_terminal_value": 2.0,
                    "expected_incremental_stamina": 100.0,
                    "best_target_category": "可转换",
                    "best_source_row": "terminal-convert",
                }
                result = advise_gear(gear, item_source="normal_85")

            mocked.assert_called_once()
            self.assertEqual(result["debug"]["dp_assist"]["checkpoint"], checkpoint)
            self.assertEqual(result["debug"]["dp_assist"]["dp_decision"], "continue")
            self.assertEqual(result["debug"]["dp_assist"]["decision_mode"], "exact_dp")

    def test_plus_15_uses_final_disposition_without_dp(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 15,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 20, "rolls": 5},
                    {"type": "HealthPercent", "value": 20, "rolls": 3},
                    {"type": "DefensePercent", "value": 20, "rolls": 3},
                    {"type": "EffectResistancePercent", "value": 16, "rolls": 2},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            result = advise_gear(gear, item_source="normal_85")

        mocked.assert_not_called()
        self.assertIn(result["summary"]["recommendation"], {"keep", "convert", "stop"})
        self.assertIsNone(result["debug"]["dp_assist"]["dp_decision"])

    def test_enable_dp_assist_false_disables_normal_default(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 9,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 9, "rolls": 3},
                    {"type": "HealthPercent", "value": 15, "rolls": 2},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            result = advise_gear(gear, item_source="normal_85", enable_dp_assist=False)

        mocked.assert_not_called()
        self.assertFalse(result["debug"]["dp_assist"]["enabled"])
        self.assertFalse(result["debug"]["default_strategy"]["enable_dp_assist"])

    def test_rift_heroic_is_rejected_at_strategy_entry(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 0,
                "rank": "Heroic",
                "substats": [
                    {"type": "Speed", "value": 3, "rolls": 1},
                    {"type": "HealthPercent", "value": 8, "rolls": 1},
                    {"type": "DefensePercent", "value": 5, "rolls": 1},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "rift_85 only supports Epic"):
            advise_gear(gear, item_source="rift_85")

    def test_strategy_rejects_unsupported_equipment_level(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 12,
                "level": 86,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 12, "rolls": 3},
                    {"type": "HealthPercent", "value": 8, "rolls": 2},
                    {"type": "DefensePercent", "value": 8, "rolls": 2},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 2},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Unsupported equipment level"):
            advise_gear(gear, item_source="normal_85")

    def test_strategy_rejects_non_checkpoint_enhancement(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 1,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 3, "rolls": 1},
                    {"type": "HealthPercent", "value": 4, "rolls": 1},
                    {"type": "DefensePercent", "value": 4, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Unsupported enhancement checkpoint"):
            advise_gear(gear, item_source="normal_85")

    def test_strategy_rejects_more_than_four_substats(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 12,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 12, "rolls": 3},
                    {"type": "HealthPercent", "value": 8, "rolls": 2},
                    {"type": "DefensePercent", "value": 8, "rolls": 2},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 8, "rolls": 2},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "at most four substats"):
            advise_gear(gear, item_source="normal_85")

    def test_strategy_rejects_heroic_fourth_substat_before_plus_12(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 9,
                "level": 85,
                "rank": "Heroic",
                "substats": [
                    {"type": "Speed", "value": 12, "rolls": 3},
                    {"type": "HealthPercent", "value": 8, "rolls": 2},
                    {"type": "DefensePercent", "value": 8, "rolls": 2},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 2},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, r"Heroic gear must have 3 substats at \+9"):
            advise_gear(gear, item_source="normal_85")

    def test_strategy_rejects_unknown_substat(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 12,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 12, "rolls": 3},
                    {"type": "HealthPercent", "value": 8, "rolls": 2},
                    {"type": "DefensePercent", "value": 8, "rolls": 2},
                    {"type": "UnknownStat", "value": 8, "rolls": 2},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Unknown substats"):
            advise_gear(gear, item_source="normal_85")

    def test_85_legacy_reforge_flag_does_not_change_strategy_suggestion(self):
        base = {
            "set": "Speed",
            "slot": "Helmet",
            "mainStat": {"type": "Health", "value": 2700},
            "enhance": 6,
            "level": 85,
            "rank": "Epic",
            "substats": [
                {"type": "Speed", "value": 7, "rolls": 2},
                {"type": "HealthPercent", "value": 8, "rolls": 2},
                {"type": "DefensePercent", "value": 5, "rolls": 1},
                {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
            ],
        }

        without_legacy_flag = advise_gear(Gear.from_dict(base), item_source="normal_85")
        with_legacy_flag = advise_gear(Gear.from_dict({**base, "reforgeEligible": True}), item_source="normal_85")

        self.assertEqual(without_legacy_flag, with_legacy_flag)

    def test_plus3_uses_lightweight_prediction_without_calling_exact_dp(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 3,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 7, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 8, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 12, "rolls": 1},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            result = advise_gear(gear, item_source="normal_85")

        mocked.assert_not_called()
        debug = result["debug"]["dp_assist"]
        self.assertEqual(debug["decision_mode"], "lightweight_prediction")
        self.assertIn("expected_final_reforge_score", debug["lightweight_basis"])
        self.assertIn("speed_threshold_probability", debug["lightweight_basis"])
        self.assertEqual(result["summary"]["recommendation"], "continue")
        self.assertEqual(result["summary"]["next_check_at"], 6)

    def test_plus6_keeps_exact_dp_mode(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 6,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 3},
                    {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                    {"type": "CriticalHitDamagePercent", "value": 14, "rolls": 2},
                    {"type": "AttackPercent", "value": 12, "rolls": 2},
                ],
            }
        )

        with patch("src.e7_enhance.route_solver.compute_optimal_route") as mocked:
            mocked.return_value = {"action": "continue", "continue_utility": 1.0, "expected_utility": 1.0}
            result = advise_gear(gear, item_source="normal_85")

        mocked.assert_called_once()
        self.assertEqual(result["debug"]["dp_assist"]["decision_mode"], "exact_dp")

    def test_lightweight_prediction_reports_zero_speed_probability_without_speed_substat(self):
        gear = Gear.from_dict(
            {
                "set": "AttackSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 0,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "HealthPercent", "value": 4, "rolls": 1},
                    {"type": "CriticalHitChancePercent", "value": 3, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 4, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        result = advise_gear(gear, item_source="normal_85")

        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        self.assertEqual(basis["expected_speed_rolls"], 0)
        self.assertEqual(basis["speed_threshold_probability"], 0.0)


if __name__ == "__main__":
    unittest.main()
