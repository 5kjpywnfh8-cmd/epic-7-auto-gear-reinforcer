import unittest

from src.e7_enhance.models import Gear
from src.e7_enhance.rules import CATEGORY_RULES, SET_ALIASES, SET_GROUPS, TARGET_SCORE_TABLE_PATH
from src.e7_enhance.score_engine import evaluate_gear


class TargetScoreTableTest(unittest.TestCase):
    def test_new_rage_and_debuff_sets_are_loaded_into_their_documented_groups(self):
        self.assertEqual(SET_ALIASES["全力"], "set_rage")
        self.assertEqual(SET_ALIASES["弱化"], "set_debuff")
        self.assertIn("set_rage", SET_GROUPS["output"])
        self.assertIn("set_rage", SET_GROUPS["critless"])
        self.assertIn("set_rage", SET_GROUPS["bruiserHpDef"])
        self.assertIn("set_debuff", SET_GROUPS["hitTank"])

    def test_rules_are_loaded_from_md_score_table(self):
        sources = {rule["sourceRow"] for rule in CATEGORY_RULES}
        categories = {rule["category"] for rule in CATEGORY_RULES}

        self.assertTrue(TARGET_SCORE_TABLE_PATH.name.endswith(".md"))
        self.assertIn("R5-R10", sources)
        self.assertIn("R11-R16", sources)
        self.assertIn("R17-R22", sources)
        self.assertIn("R23-R28", sources)
        self.assertIn("R29-R34", sources)
        self.assertIn("R35-R40", sources)
        self.assertIn("R41-R46", sources)
        self.assertIn("R47-R52", sources)
        self.assertIn("R53-R58", sources)
        self.assertIn("输出", categories)
        self.assertIn("纯肉", categories)
        self.assertIn("双效", categories)

    def test_target_score_comes_from_md_formula_not_effective_score_floor(self):
        gear = Gear.from_dict(
            {
                "set": "HealthSet",
                "slot": "Ring",
                "mainStat": {"type": "HealthPercent", "value": 60},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "HealthPercent", "value": 40, "rolls": 5},
                    {"type": "DefensePercent", "value": 18, "rolls": 3},
                    {"type": "Speed", "value": 8, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        evaluation = evaluate_gear(gear)

        self.assertEqual(evaluation.target_profile, "纯肉")
        self.assertEqual(evaluation.target_score_source_row, "R23-R28")
        self.assertEqual(evaluation.target_score_formula, "5*装等-319")
        self.assertEqual(evaluation.target_score, 51)
        self.assertEqual(evaluation.target_score, evaluation.baili_score)
        self.assertGreater(evaluation.effective_score, 0)

    def test_critless_armor_has_no_target_score(self):
        gear = Gear.from_dict(
            {
                "set": "DestructionSet",
                "slot": "Armor",
                "mainStat": {"type": "Defense", "value": 300},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "AttackPercent", "value": 30, "rolls": 4},
                    {"type": "CriticalHitDamagePercent", "value": 32, "rolls": 5},
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "HealthPercent", "value": 10, "rolls": 1},
                ],
            }
        )

        evaluation = evaluate_gear(gear)

        self.assertNotEqual(evaluation.target_profile, "输出(必爆)")
        self.assertNotEqual(evaluation.target_score_source_row, "R11-R16")

    def test_one_speed_only_scores_non_boot_speed_thresholds(self):
        weapon = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 22, "rolls": 5},
                    {"type": "HealthPercent", "value": 8, "rolls": 1},
                ],
            }
        )
        boot = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Boot",
                "mainStat": {"type": "Speed", "value": 45},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 25, "rolls": 5},
                    {"type": "HealthPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        self.assertEqual(evaluate_gear(weapon).target_score_source_row, "R2")
        self.assertNotEqual(evaluate_gear(boot).target_score_source_row, "R2")

    def test_speed_set_speed_piece_requires_non_speed_support_profile(self):
        speed_only = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                ],
            }
        )
        supported = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 20, "rolls": 3},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                ],
            }
        )

        self.assertNotEqual(evaluate_gear(speed_only).target_score_source_row, "R3")
        self.assertEqual(evaluate_gear(supported).target_score_source_row, "R3")

    def test_non_speed_set_speed_piece_uses_r4_when_supported(self):
        gear = Gear.from_dict(
            {
                "set": "CriticalSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 20, "rolls": 3},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                ],
            }
        )

        self.assertEqual(evaluate_gear(gear).target_score_source_row, "R4")

    def test_future_score_is_md_fallback_when_no_category_matches(self):
        gear = Gear.from_dict(
            {
                "set": "UnknownSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 20, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 14, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 25, "rolls": 4},
                    {"type": "AttackPercent", "value": 10, "rolls": 2},
                ],
            }
        )

        evaluation = evaluate_gear(gear)

        self.assertEqual(evaluation.target_profile, "未来可期")
        self.assertEqual(evaluation.target_score_source_row, "R61")

    def test_output_and_critless_output_are_mutually_exclusive(self):
        critless = Gear.from_dict(
            {
                "set": "DestructionSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "AttackPercent", "value": 30, "rolls": 4},
                    {"type": "CriticalHitDamagePercent", "value": 32, "rolls": 5},
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "HealthPercent", "value": 10, "rolls": 1},
                ],
            }
        )
        output = Gear.from_dict(
            {
                "set": "DestructionSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "AttackPercent", "value": 30, "rolls": 4},
                    {"type": "CriticalHitChancePercent", "value": 15, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 32, "rolls": 5},
                    {"type": "Speed", "value": 10, "rolls": 2},
                ],
            }
        )

        self.assertEqual(evaluate_gear(critless).target_score_source_row, "R11-R16")
        self.assertEqual(evaluate_gear(output).target_score_source_row, "R5-R10")

    def test_dual_effect_excludes_attack_percent_with_eff_or_res(self):
        dual = Gear.from_dict(
            {
                "set": "CounterSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "EffectivenessPercent", "value": 30, "rolls": 4},
                    {"type": "HealthPercent", "value": 20, "rolls": 3},
                    {"type": "DefensePercent", "value": 20, "rolls": 3},
                    {"type": "Speed", "value": 8, "rolls": 2},
                ],
            }
        )
        blocked = Gear.from_dict(
            {
                "set": "CounterSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 90,
                "rank": "Epic",
                "substats": [
                    {"type": "EffectivenessPercent", "value": 30, "rolls": 4},
                    {"type": "AttackPercent", "value": 20, "rolls": 3},
                    {"type": "DefensePercent", "value": 20, "rolls": 3},
                    {"type": "Speed", "value": 8, "rolls": 2},
                ],
            }
        )

        self.assertEqual(evaluate_gear(dual).target_score_source_row, "R35-R40")
        self.assertNotEqual(evaluate_gear(blocked).target_score_source_row, "R35-R40")


if __name__ == "__main__":
    unittest.main()
