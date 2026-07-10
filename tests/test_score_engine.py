import unittest

from src.e7_enhance.models import Gear
from src.e7_enhance.lightweight_calibration import theoretical_category_bounds
from src.e7_enhance.score_engine import (
    evaluate_gear,
    full_category_diagnostics,
    full_category_matches,
    official_score_for_stats,
    rating_for,
)


class ScoreEngineTest(unittest.TestCase):
    def test_full_category_matches_requires_all_substats_in_one_category(self):
        output = Gear.from_dict({"set": "Critical", "slot": "Weapon", "mainStat": {"type": "Attack", "value": 525}, "enhance": 3, "rank": "Epic", "substats": [{"type": "Speed", "value": 8, "rolls": 2}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1}, {"type": "AttackPercent", "value": 8, "rolls": 1}]})
        mixed = Gear.from_dict({"set": "Critical", "slot": "Weapon", "mainStat": {"type": "Attack", "value": 525}, "enhance": 3, "rank": "Epic", "substats": [{"type": "Speed", "value": 8, "rolls": 2}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "EffectivenessPercent", "value": 7, "rolls": 1}, {"type": "AttackPercent", "value": 8, "rolls": 1}]})

        self.assertIn("输出", [item["category"] for item in full_category_matches(output)])
        self.assertEqual(full_category_matches(mixed), [])

        output_diagnostic = next(item for item in full_category_diagnostics(mixed) if item["category"] == "输出")
        self.assertTrue(output_diagnostic["set_matched"])
        self.assertTrue(output_diagnostic["main_matched"])
        self.assertTrue(output_diagnostic["special_matched"])
        self.assertFalse(output_diagnostic["full_matched"])
        self.assertIn(False, [item["matched"] for item in output_diagnostic["substats"]])

    def test_full_category_matches_uses_one_rule_for_every_supported_slot(self):
        cases = {
            "Weapon": ("Attack", ["Attack", "AttackPercent", "CriticalHitChancePercent", "CriticalHitDamagePercent"]),
            "Helmet": ("Health", ["Attack", "AttackPercent", "CriticalHitChancePercent", "CriticalHitDamagePercent"]),
            "Armor": ("Defense", ["Speed", "CriticalHitChancePercent", "CriticalHitDamagePercent"]),
            "Necklace": ("CriticalHitChancePercent", ["Attack", "AttackPercent", "CriticalHitDamagePercent", "Speed"]),
            "Ring": ("AttackPercent", ["Attack", "CriticalHitChancePercent", "CriticalHitDamagePercent", "Speed"]),
            "Boots": ("Speed", ["Attack", "AttackPercent", "CriticalHitChancePercent", "CriticalHitDamagePercent"]),
        }
        for slot, (main, substats) in cases.items():
            with self.subTest(slot=slot):
                gear = Gear.from_dict({"set": "Critical", "slot": slot, "mainStat": {"type": main, "value": 1}, "enhance": 3, "rank": "Heroic" if slot == "Armor" else "Epic", "substats": [{"type": stat, "value": 4, "rolls": 1} for stat in substats]})
                self.assertIn("输出", [item["category"] for item in full_category_matches(gear)])

    def test_theoretical_bound_uses_distinct_legal_conversion_and_missing_substat(self):
        gear = Gear.from_dict({"set": "Critical", "slot": "Weapon", "mainStat": {"type": "Attack", "value": 525}, "enhance": 3, "rank": "Heroic", "substats": [{"type": "AttackPercent", "value": 8, "rolls": 2}, {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}, {"type": "EffectivenessPercent", "value": 8, "rolls": 1}]})

        output = next(item for item in theoretical_category_bounds(gear, "normal_85") if item["category"] == "输出")

        self.assertEqual(output["current_invalid_substats"], 1)
        self.assertNotEqual(output["upper_bound_conversion_target"], output["upper_bound_missing_substat_target"])

    def test_official_substat_score_uses_user_formula_weights(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "substats": [
                    {"type": "AttackPercent", "value": 10},
                    {"type": "DefensePercent", "value": 10},
                    {"type": "HealthPercent", "value": 10},
                    {"type": "Speed", "value": 5},
                    {"type": "CriticalHitChancePercent", "value": 5},
                    {"type": "CriticalHitDamagePercent", "value": 7},
                    {"type": "Attack", "value": 39},
                    {"type": "Defense", "value": 31},
                    {"type": "Health", "value": 174},
                ],
            }
        )

        self.assertAlmostEqual(official_score_for_stats(gear.substats), 67.5)

    def test_speed_gear_enters_speed_profile(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "substats": [
                    {"type": "Speed", "value": 23},
                    {"type": "EffectivenessPercent", "value": 5},
                    {"type": "CriticalHitDamagePercent", "value": 14},
                    {"type": "DefensePercent", "value": 8},
                ],
            }
        )

        evaluation = evaluate_gear(gear)

        self.assertEqual(evaluation.target_profile, "一速")
        self.assertGreaterEqual(evaluation.baili_score, 10)
        self.assertIn("速度 23", evaluation.valid_substats)

    def test_unmatched_high_effective_score_is_capped_at_strong_keep(self):
        level, label = rating_for(
            score=0,
            category="无",
            official=82,
            sub_official=82,
            speed=0,
            matched_baili=False,
            effective=82,
            baili_tier=0,
        )

        self.assertEqual(level, 5)
        self.assertEqual(label, "5 强保留")


if __name__ == "__main__":
    unittest.main()
