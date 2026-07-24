import json
import tempfile
from pathlib import Path
import unittest

from src.e7_enhance.models import Gear
from src.e7_enhance.route_solver import (
    clear_route_cache,
    compute_optimal_route,
    main as route_solver_main,
    route_cache_info,
)


LAMBDA = 1 / 932.82


class RouteSolverTest(unittest.TestCase):
    def setUp(self):
        clear_route_cache()

    def test_plus12_without_formal_baili_upside_stops(self):
        gear = Gear.from_dict(
            {
                "set": "AttackSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "reforgeEligible": True,
                "substats": [
                    {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                    {"type": "EffectivenessPercent", "value": 8, "rolls": 1},
                    {"type": "Health", "value": 180, "rolls": 1},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        route = compute_optimal_route(gear, LAMBDA, item_source="normal_85")

        self.assertEqual(route["action"], "stop")
        self.assertLess(route["continue_utility"], 0)
        self.assertEqual(route["expected_formal_baili_score"], 0.0)

    def test_plus12_with_high_formal_baili_cross_probability_continues(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "reforgeEligible": True,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 5},
                    {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                    {"type": "CriticalHitDamagePercent", "value": 14, "rolls": 2},
                    {"type": "AttackPercent", "value": 12, "rolls": 2},
                ],
            }
        )

        route = compute_optimal_route(gear, LAMBDA, item_source="normal_85")

        self.assertEqual(route["action"], "continue")
        self.assertGreater(route["continue_utility"], 0)
        self.assertEqual(route["best_source_row"], "R2")
        self.assertGreater(route["expected_formal_baili_score"], 0)

    def test_r61_future_score_is_not_dp_utility(self):
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

        route = compute_optimal_route(gear, LAMBDA, item_source="normal_85")

        self.assertEqual(route["action"], "terminal")
        self.assertEqual(route["expected_formal_baili_score"], 0.0)
        self.assertEqual(route["expected_utility"], 0.0)

    def test_85_terminal_route_ignores_legacy_reforge_eligibility(self):
        base = {
            "set": "Attack",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 15,
            "level": 85,
            "rank": "Epic",
            "substats": [
                {"type": "Speed", "value": 18, "rolls": 5},
                {"type": "HealthPercent", "value": 4, "rolls": 1},
                {"type": "AttackPercent", "value": 4, "rolls": 1},
                {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
            ],
        }
        not_eligible = Gear.from_dict(base)
        eligible = Gear.from_dict({**base, "reforgeEligible": True})

        without_reforge = compute_optimal_route(not_eligible, LAMBDA, item_source="normal_85")
        with_reforge = compute_optimal_route(eligible, LAMBDA, item_source="normal_85")

        self.assertEqual(without_reforge, with_reforge)

    def test_dp_entry_rejects_unsupported_equipment_level(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 86,
                "rank": "Epic",
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 5},
                    {"type": "HealthPercent", "value": 4, "rolls": 1},
                    {"type": "CriticalHitChancePercent", "value": 4, "rolls": 1},
                    {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                ],
            }
        )

        with self.assertRaisesRegex(ValueError, "Unsupported equipment level"):
            compute_optimal_route(gear, LAMBDA, item_source="normal_85")

    def test_90_terminal_route_does_not_reforge_twice(self):
        base = {
            "set": "SpeedSet",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 15,
            "level": 90,
            "rank": "Epic",
            "substats": [
                {"type": "Speed", "value": 22, "rolls": 5},
                {"type": "HealthPercent", "value": 4, "rolls": 1},
                {"type": "AttackPercent", "value": 4, "rolls": 1},
                {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
            ],
        }

        without_legacy_flag = compute_optimal_route(Gear.from_dict(base), LAMBDA, item_source="normal_85")
        with_legacy_flag = compute_optimal_route(Gear.from_dict({**base, "reforgeEligible": True}), LAMBDA, item_source="normal_85")

        self.assertEqual(without_legacy_flag, with_legacy_flag)

    def test_speed_potential_uses_central_set_eligibility_and_threshold(self):
        def route_for(set_name: str, speed: int, rolls: int) -> dict:
            gear = Gear.from_dict(
                {
                    "set": set_name,
                    "slot": "Weapon",
                    "mainStat": {"type": "Attack", "value": 525},
                    "enhance": 12,
                    "level": 85,
                    "rank": "Epic",
                    "substats": [
                        {"type": "Speed", "value": speed, "rolls": rolls},
                        {"type": "HealthPercent", "value": 4, "rolls": 1},
                        {"type": "AttackPercent", "value": 4, "rolls": 1},
                        {"type": "EffectResistancePercent", "value": 4, "rolls": 1},
                    ],
                }
            )
            return compute_optimal_route(gear, LAMBDA, item_source="normal_85")

        for set_name in ("SpeedSet", "CriticalSet", "DebuffSet"):
            route = route_for(set_name, speed=8, rolls=2)
            with self.subTest(set_name=set_name):
                self.assertTrue(route["speed_potential_set_eligible"])
                self.assertEqual(route["speed_potential_threshold_blocked_probability"], 0.0)
                self.assertGreater(route["expected_speed_potential_value"], 0.0)

        blocked = route_for("AttackSet", speed=8, rolls=2)
        allowed = route_for("AttackSet", speed=18, rolls=5)
        self.assertFalse(blocked["speed_potential_set_eligible"])
        self.assertGreater(blocked["speed_potential_threshold_blocked_probability"], 0.0)
        self.assertEqual(blocked["expected_speed_potential_value"], 0.0)
        self.assertGreater(allowed["expected_terminal_speed"], 20)
        self.assertGreater(allowed["expected_speed_potential_value"], 0.0)

    def test_conversion_crossing_formal_rule_has_higher_utility(self):
        convertible = Gear.from_dict(
            {
                "set": "SpeedSet",
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
        not_convertible = Gear.from_dict(
            {
                **convertible.to_dict(),
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 14, "rolls": 3},
                    {"type": "CriticalHitDamagePercent", "value": 24, "rolls": 4},
                    {"type": "EffectResistancePercent", "value": 20, "rolls": 3},
                ],
            }
        )

        rescued = compute_optimal_route(convertible, LAMBDA, item_source="normal_85")
        failed = compute_optimal_route(not_convertible, LAMBDA, item_source="normal_85")

        self.assertGreater(rescued["expected_utility"], failed["expected_utility"])
        self.assertGreater(rescued["expected_formal_baili_score"], 0)
        self.assertEqual(rescued["conversion_needed_probability"], 1.0)
        self.assertEqual(failed["expected_formal_baili_score"], 0.0)

    def test_default_conversion_cost_is_gold_backed_in_route_debug(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
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

        route = compute_optimal_route(gear, LAMBDA, item_source="normal_85")

        self.assertEqual(route["conversion_cost_gold"], 100000)
        self.assertGreater(route["conversion_cost_stamina"], 0)

    def test_same_gear_state_hits_cache(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 5},
                    {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                    {"type": "CriticalHitDamagePercent", "value": 14, "rolls": 2},
                    {"type": "AttackPercent", "value": 12, "rolls": 2},
                ],
            }
        )

        first = compute_optimal_route(gear, LAMBDA, item_source="normal_85")
        before = route_cache_info()
        second = compute_optimal_route(gear, LAMBDA, item_source="normal_85")
        after = route_cache_info()

        self.assertEqual(first, second)
        self.assertGreater(after["hits"], before["hits"])

    def test_rift_epic_route_uses_its_own_roll_distribution(self):
        gear = Gear.from_dict(
            {
                "set": "SpeedSet",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 12,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 10, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 10, "rolls": 2},
                    {"type": "CriticalHitDamagePercent", "value": 14, "rolls": 2},
                    {"type": "AttackPercent", "value": 12, "rolls": 2},
                ],
            }
        )

        normal = compute_optimal_route(gear, LAMBDA, item_source="normal_85")
        rift = compute_optimal_route(gear, LAMBDA, item_source="rift_85")

        self.assertNotEqual(normal["expected_terminal_value"], rift["expected_terminal_value"])

    def test_route_solver_cli_generates_json_and_markdown_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            status = route_solver_main(["--runs", "3", "--seed", "17", "--reports-dir", str(output)])

            self.assertEqual(status, 0)
            summary_json = output / "route-solver-round3-summary.json"
            summary_md = output / "route-solver-round3-summary.md"
            self.assertTrue(summary_json.exists())
            self.assertTrue(summary_md.exists())
            data = json.loads(summary_json.read_text(encoding="utf-8"))
            self.assertEqual(data["scope"]["score_scope"], "R2-R58 formal baili score; R61 future is auxiliary only")
            self.assertFalse(data["scope"]["round2_rerun"])
        self.assertEqual(len(data["sections"]), 2)


if __name__ == "__main__":
    unittest.main()
