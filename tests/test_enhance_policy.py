import unittest
from pathlib import Path
from unittest.mock import patch

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.gui_support import load_gear_file, suggest_from_form
from src.e7_enhance.models import Gear


class EnhancePolicyTest(unittest.TestCase):
    @staticmethod
    def _early_speed_gear(
        *,
        rank: str = "Epic",
        item_source: str = "normal_85",
        slot: str = "Armor",
        enhance: int = 0,
        speed: int = 2,
        speed_rolls: int = 1,
        output_substats: bool = False,
    ) -> tuple[Gear, str]:
        substats = (
            [
                {"type": "Speed", "value": speed, "rolls": speed_rolls},
                {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                {"type": "EffectivenessPercent", "value": 8, "rolls": 1},
            ]
            if output_substats
            else [
                {"type": "Speed", "value": speed, "rolls": speed_rolls},
                {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                {"type": "EffectivenessPercent", "value": 8, "rolls": 1},
                {"type": "Health", "value": 180, "rolls": 1},
            ]
        )
        if rank == "Heroic" and enhance == 0:
            substats = substats[:3]
        if enhance == 3 and speed_rolls == 1:
            substats[-1]["rolls"] = 2
        main_stat = {"type": "AttackPercent", "value": 65} if slot == "Boots" else {"type": "Defense", "value": 300}
        return Gear.from_dict(
            {
                "set": "Destruction",
                "slot": slot,
                "mainStat": main_stat,
                "enhance": enhance,
                "level": 85,
                "rank": rank,
                "substats": substats,
            }
        ), item_source

    def test_epic_non_boot_initial_speed_two_uses_hard_early_speed_route_for_both_sources(self):
        for item_source in ("normal_85", "rift_85"):
            with self.subTest(item_source=item_source):
                gear, source = self._early_speed_gear(item_source=item_source, speed=2)
                result = advise_gear(gear, item_source=source)
                basis = result["debug"]["dp_assist"]["lightweight_basis"]

                self.assertEqual(result["summary"]["recommendation"], "continue")
                self.assertEqual(basis["route"], "早期赌速度")
                self.assertEqual(basis["early_speed_gamble"]["rank_threshold"], 2)
                self.assertTrue(basis["early_speed_gamble"]["continue_route"])

    def test_early_speed_route_thresholds_exclude_epic_one_speed_boots_and_heroic_three_speed(self):
        cases = [
            ("Epic 速度 1", self._early_speed_gear(speed=1)),
            ("Epic 鞋子", self._early_speed_gear(slot="Boots", speed=5)),
            ("Heroic 速度 3", self._early_speed_gear(rank="Heroic", speed=3)),
            ("Heroic 速度 4", self._early_speed_gear(rank="Heroic", speed=4)),
        ]
        expected_eligible = {"Epic 速度 1": False, "Epic 鞋子": False, "Heroic 速度 3": False, "Heroic 速度 4": True}
        for label, (gear, item_source) in cases:
            with self.subTest(label=label):
                result = advise_gear(gear, item_source=item_source)
                early = result["debug"]["dp_assist"]["lightweight_basis"]["early_speed_gamble"]
                self.assertEqual(early["continue_route"], expected_eligible[label])
        heroic_gear, heroic_source = self._early_speed_gear(rank="Heroic", speed=4)
        self.assertEqual(advise_gear(heroic_gear, item_source=heroic_source)["summary"]["recommendation"], "continue")

    def test_plus3_speed_miss_exits_hard_route_and_uses_ordinary_strategy(self):
        gear, item_source = self._early_speed_gear(
            enhance=3,
            speed=2,
            speed_rolls=1,
            output_substats=True,
        )

        result = advise_gear(gear, item_source=item_source)
        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        early = basis["early_speed_gamble"]

        self.assertFalse(early["continue_route"])
        self.assertTrue(early["route_ended"])
        self.assertNotEqual(basis["route"], "早期赌速度退出")
        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")
        self.assertEqual(basis["route"], "候选体系待 +6 精确复核")
        self.assertEqual(early["fallback_recommendation"], "cautious_continue")

        no_candidate_gear, no_candidate_source = self._early_speed_gear(
            enhance=3,
            speed=2,
            speed_rolls=1,
        )
        no_candidate_result = advise_gear(no_candidate_gear, item_source=no_candidate_source)
        no_candidate_basis = no_candidate_result["debug"]["dp_assist"]["lightweight_basis"]

        self.assertIsNone(no_candidate_basis["selected_candidate"])
        self.assertEqual(no_candidate_result["summary"]["recommendation"], "cautious_continue")
        self.assertEqual(no_candidate_basis["route"], "早期保守复核")
        self.assertEqual(
            no_candidate_basis["early_speed_gamble"]["fallback_recommendation"],
            "cautious_continue",
        )

    def test_documented_acceptance_cases_define_the_early_speed_gamble_route(self):
        cases = [
            ("Epic +0 非鞋 5 速", self._early_speed_gear(slot="Armor", speed=5), "continue"),
            ("Heroic +0 项链 4 速", self._early_speed_gear(rank="Heroic", slot="Necklace", speed=4), "continue"),
            ("Heroic +0 戒指 4 速", self._early_speed_gear(rank="Heroic", slot="Ring", speed=4), "continue"),
            (
                "Epic +3 戒指未跳速度",
                self._early_speed_gear(slot="Ring", enhance=3, speed=4, speed_rolls=1, output_substats=True),
                "cautious_continue",
            ),
        ]

        for label, (gear, item_source), recommendation in cases:
            with self.subTest(label=label):
                result = advise_gear(gear, item_source=item_source)
                basis = result["debug"]["dp_assist"]["lightweight_basis"]

                self.assertEqual(result["summary"]["recommendation"], recommendation)
                self.assertIn("early_speed_gamble", basis)
                self.assertIn("slot_eligible", basis["early_speed_gamble"])
                self.assertIn("rank_threshold", basis["early_speed_gamble"])
                self.assertIn("plus3_hit_speed", basis["early_speed_gamble"])
                self.assertIn("route_end_reason", basis["early_speed_gamble"])
                self.assertIn("next_check_at", basis["early_speed_gamble"])

        first, first_source = cases[0][1]
        positive = advise_gear(first, item_source=first_source)
        self.assertEqual(positive["debug"]["dp_assist"]["lightweight_basis"]["route"], "早期赌速度")

        missed, missed_source = cases[3][1]
        missed_result = advise_gear(missed, item_source=missed_source)
        missed_speed = missed_result["debug"]["dp_assist"]["lightweight_basis"]["early_speed_gamble"]
        self.assertFalse(missed_speed["plus3_hit_speed"])
        self.assertEqual(missed_speed["route_end_reason"], "+3 未命中速度，退出早期赌速度路线")

        boot_cases = [
            ("Epic 鞋子", self._early_speed_gear(slot="Boots", speed=5)),
            ("Heroic 鞋子", self._early_speed_gear(rank="Heroic", slot="Boots", speed=4)),
        ]
        for label, (gear, item_source) in boot_cases:
            with self.subTest(label=label):
                result = advise_gear(gear, item_source=item_source)
                basis = result["debug"]["dp_assist"]["lightweight_basis"]
                self.assertNotEqual(basis["route"], "早期赌速度")
                self.assertFalse(basis["early_speed_gamble"]["slot_eligible"])
                self.assertEqual(
                    basis["early_speed_gamble"]["route_end_reason"],
                    "鞋子不适用非鞋早期赌速度路线",
                )

    def test_plus3_speed_hit_keeps_the_early_speed_gamble_route(self):
        gear = Gear.from_dict(
            {
                "set": "Destruction",
                "slot": "Armor",
                "mainStat": {"type": "Defense", "value": 300},
                "enhance": 3,
                "level": 85,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 8, "rolls": 2},
                    {"type": "Health", "value": 188, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 5, "rolls": 1},
                ],
            }
        )

        result = advise_gear(gear, item_source="normal_85")

        self.assertEqual(result["summary"]["recommendation"], "continue")
        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        self.assertEqual(basis["route"], "早期赌速度")
        self.assertTrue(basis["early_speed_gamble"]["plus3_hit_speed"])
        self.assertEqual(basis["early_speed_gamble"]["next_check_at"], 6)

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

    def test_plus3_conversion_candidate_uses_terminal_max_modification_gs(self):
        result = suggest_from_form(load_gear_file(Path("建议结果") / "14.json"))
        candidate = result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"][0]

        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")
        self.assertEqual(candidate["current_pre_reforge_gs"], 24.0)
        self.assertEqual(candidate["current_reforged_gs"], 29.7)
        self.assertEqual(candidate["expected_final_gs_native"], 52.2)
        self.assertEqual(candidate["conversion_max_gs_gain"], 12.1)
        self.assertEqual(candidate["expected_final_gs_after_max_conversion"], 64.3)
        self.assertEqual(candidate["expected_final_gs"], 64.3)
        self.assertGreater(candidate["terminal_reach_probability"], candidate["terminal_reach_probability_native"])
        self.assertEqual(candidate["conversion_max_value_source"], "Fribbels modValues.reforged.greater upper bound (100% quality)")

    def test_non_conversion_candidate_keeps_native_terminal_gs_and_probability(self):
        form = load_gear_file(Path("建议结果") / "14.json")
        form["substats"] = [dict(stat) for stat in form["substats"]]
        form["substats"][-1]["rolls"] = 3

        result = suggest_from_form(form)
        candidate = next(
            item
            for item in result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"]
            if item["category"] == "输出"
        )

        self.assertFalse(candidate["is_conversion_candidate"])
        self.assertIsNone(candidate["expected_final_gs_after_max_conversion"])
        self.assertEqual(candidate["expected_final_gs"], candidate["expected_final_gs_native"])
        self.assertEqual(candidate["terminal_reach_probability"], candidate["terminal_reach_probability_native"])

    def test_heroic_terminal_conversion_distribution_skips_plus12_fill_event(self):
        gear = Gear.from_dict({
            "set": "Critical",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 3,
            "level": 85,
            "rank": "Heroic",
            "substats": [
                {"type": "AttackPercent", "value": 12, "rolls": 2},
                {"type": "CriticalHitChancePercent", "value": 6, "rolls": 1},
                {"type": "EffectivenessPercent", "value": 5, "rolls": 1},
            ],
        })

        result = advise_gear(gear, item_source="normal_85")
        candidate = next(
            item
            for item in result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"]
            if item["category"] == "输出"
        )

        self.assertEqual(
            candidate["conversion_terminal_roll_distribution"],
            {1: 0.33333333, 2: 0.44444444, 3: 0.19444444, 4: 0.02777778},
        )
        self.assertEqual(candidate["conversion_max_value"], 11.0)
        self.assertEqual(candidate["conversion_max_gs_gain"], 12.6)

    def test_level90_current_gs_does_not_apply_reforge_bonus_twice(self):
        gear = Gear.from_dict({
            "set": "Critical",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 3,
            "level": 90,
            "rank": "Epic",
            "substats": [
                {"type": "AttackPercent", "value": 11, "rolls": 2},
                {"type": "CriticalHitChancePercent", "value": 6, "rolls": 1},
                {"type": "CriticalHitDamagePercent", "value": 8, "rolls": 1},
                {"type": "Speed", "value": 4, "rolls": 1},
            ],
        })

        result = advise_gear(gear, item_source="normal_85")
        candidate = result["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"][0]

        self.assertEqual(candidate["current_pre_reforge_gs"], candidate["current_reforged_gs"])

    def test_85_reforge_eligibility_does_not_change_max_conversion_projection(self):
        eligible = load_gear_file(Path("建议结果") / "14.json")
        legacy_false = dict(eligible)
        legacy_false["substats"] = [dict(stat) for stat in eligible["substats"]]
        legacy_false["reforge_eligible"] = False

        eligible_candidate = suggest_from_form(eligible)["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"][0]
        legacy_candidate = suggest_from_form(legacy_false)["debug"]["dp_assist"]["lightweight_basis"]["candidate_evaluations"][0]

        for key in (
            "current_pre_reforge_gs",
            "current_reforged_gs",
            "expected_final_gs_native",
            "expected_final_gs_after_max_conversion",
            "expected_final_gs",
            "terminal_reach_probability",
        ):
            self.assertEqual(eligible_candidate[key], legacy_candidate[key])

    def test_early_debug_keeps_formal_probability_separate_from_total_substat_future_75(self):
        result = suggest_from_form(load_gear_file(Path("建议结果") / "14.json"))
        basis = result["debug"]["dp_assist"]["lightweight_basis"]
        candidate = basis["selected_candidate"]

        self.assertLess(candidate["formal_terminal_gs_threshold"], 75.0)
        self.assertIn("terminal_reach_probability", candidate)
        self.assertEqual(basis["future_75_gs_threshold"], 75.0)
        self.assertIn("expected_final_total_substat_gs_native", basis)
        self.assertIn("terminal_future_75_probability_native", basis)
        self.assertIn("terminal_future_75_probability", basis)
        self.assertEqual(basis["terminal_goal_type"], "formal_category")
        self.assertEqual(basis["terminal_goal_probability"], candidate["terminal_reach_probability"])

    def test_current_total_substat_gs_at_75_has_certain_future_75_probability(self):
        gear = Gear.from_dict({
            "set": "Critical",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 3,
            "level": 85,
            "rank": "Epic",
            "substats": [
                {"type": "AttackPercent", "value": 30, "rolls": 2},
                {"type": "CriticalHitChancePercent", "value": 20, "rolls": 1},
                {"type": "CriticalHitDamagePercent", "value": 30, "rolls": 1},
                {"type": "Speed", "value": 20, "rolls": 1},
            ],
        })

        basis = advise_gear(gear, item_source="normal_85")["debug"]["dp_assist"]["lightweight_basis"]

        self.assertGreaterEqual(basis["expected_final_total_substat_gs_native"], 75.0)
        self.assertEqual(basis["terminal_future_75_probability_native"], 1.0)

    def test_low_legal_total_substat_path_has_zero_future_75_probability(self):
        gear = Gear.from_dict({
            "set": "Critical",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 3,
            "level": 85,
            "rank": "Epic",
            "substats": [
                {"type": "AttackPercent", "value": 1, "rolls": 2},
                {"type": "CriticalHitChancePercent", "value": 1, "rolls": 1},
                {"type": "CriticalHitDamagePercent", "value": 1, "rolls": 1},
                {"type": "Speed", "value": 1, "rolls": 1},
            ],
        })

        basis = advise_gear(gear, item_source="normal_85")["debug"]["dp_assist"]["lightweight_basis"]

        self.assertEqual(basis["terminal_future_75_probability_native"], 0.0)

    def test_future_75_fallback_stays_review_when_no_formal_candidate_exists(self):
        gear = Gear.from_dict({
            "set": "Critical",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 3,
            "level": 85,
            "rank": "Epic",
            "substats": [
                {"type": "EffectResistancePercent", "value": 30, "rolls": 2},
                {"type": "CriticalHitChancePercent", "value": 20, "rolls": 1},
                {"type": "CriticalHitDamagePercent", "value": 30, "rolls": 1},
                {"type": "EffectivenessPercent", "value": 30, "rolls": 1},
            ],
        })

        result = advise_gear(gear, item_source="normal_85")
        basis = result["debug"]["dp_assist"]["lightweight_basis"]

        self.assertIsNone(basis["selected_candidate"])
        self.assertEqual(basis["terminal_goal_type"], "future_75_fallback")
        self.assertEqual(basis["terminal_future_75_probability"], 1.0)
        self.assertEqual(result["summary"]["recommendation"], "cautious_continue")

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
        gear = Gear.from_dict({"set": "Critical", "slot": "Weapon", "mainStat": {"type": "Attack", "value": 525}, "enhance": 0, "level": 85, "rank": "Epic", "substats": [{"type": "AttackPercent", "value": 8, "rolls": 1}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1}, {"type": "Speed", "value": 1, "rolls": 1}]})
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

        self.assertEqual(result["summary"]["recommendation"], "continue")
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

        self.assertEqual(result["debug"]["strategy_version"], "baili-formal-dp-v1-epic-balanced")
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

    def test_normal_heroic_debug_explains_unpublished_resource_calibration_fallback(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Helmet",
                "mainStat": {"type": "Health", "value": 2700},
                "enhance": 6,
                "rank": "Heroic",
                "substats": [
                    {"type": "Speed", "value": 7, "rolls": 2},
                    {"type": "HealthPercent", "value": 8, "rolls": 1},
                    {"type": "DefensePercent", "value": 5, "rolls": 1},
                ],
            }
        )

        result = advise_gear(gear, item_source="normal_85")

        self.assertFalse(result["debug"]["default_strategy"]["enable_dp_assist"])
        self.assertEqual(result["debug"]["dp_assist"]["resource_calibration_status"], "unpublished")
        self.assertEqual(result["debug"]["dp_assist"]["resource_calibration_message"], "Heroic 资源校准未发布，已回退基础策略")

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

    def test_strategy_rejects_unknown_set(self):
        gear = Gear.from_dict(
            {
                "set": "set_future_unknown",
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
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Unknown gear set: set_future_unknown"):
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
