import unittest
import random

from src.e7_enhance.enhance_simulator import (
    RollProfile,
    SimulationOptions,
    enhance_to_checkpoint,
    expected_roll_value,
    generate_gear,
    reforge_gear,
    roll_range,
    simulate_drops,
    simulate_gear,
)
from src.e7_enhance.models import Gear


class EnhanceSimulatorTest(unittest.TestCase):
    def test_normal_and_rift_roll_ranges_remain_separate(self):
        self.assertEqual(expected_roll_value(RollProfile(85, "Epic", "normal_85"), "spd"), 3)
        self.assertEqual(expected_roll_value(RollProfile(85, "Epic", "rift_85"), "spd"), 3.5)
        self.assertEqual(expected_roll_value(RollProfile(85, "Heroic", "normal_85"), "crit"), 4)
        self.assertEqual(roll_range(RollProfile(85, "Epic", "normal_85"), "hpPct"), (4, 8))
        self.assertEqual(roll_range(RollProfile(85, "Epic", "rift_85"), "hpPct"), (6, 8))
        self.assertEqual(roll_range(RollProfile(85, "Epic", "normal_85"), "hpFlat"), (158, 203))
        self.assertEqual(roll_range(RollProfile(85, "Epic", "rift_85"), "hpFlat"), (178, 203))
        with self.assertRaisesRegex(ValueError, "unsupported roll profile"):
            roll_range(RollProfile(85, "Heroic", "rift_85"), "atkPct")

    def test_each_rank_uses_its_own_substat_event_schedule(self):
        expected = {
            "Epic": [(3, 4, 1), (6, 4, 2), (9, 4, 3), (12, 4, 4), (15, 4, 5)],
            "Heroic": [(3, 3, 1), (6, 3, 2), (9, 3, 3), (12, 4, 3), (15, 4, 4)],
        }

        for rank, checkpoints in expected.items():
            with self.subTest(rank=rank):
                rng = random.Random(7)
                gear = generate_gear(rng, SimulationOptions(rank=rank, item_source="normal_85"))
                for checkpoint, substat_count, roll_count in checkpoints:
                    gear, _ = enhance_to_checkpoint(gear, checkpoint, "normal_85", rng)
                    self.assertEqual(len(gear.substats), substat_count)
                    self.assertEqual(len(gear.roll_history), roll_count)

    def test_85_gear_reforges_independent_of_legacy_eligibility(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 15,
                "level": 85,
                "rank": "Epic",
                "substats": [{"type": "Speed", "value": 10, "rolls": 2}],
            }
        )

        self.assertEqual(reforge_gear(gear).level, 90)
        eligible = Gear.from_dict({**gear.to_dict(), "reforgeEligible": True})
        self.assertEqual(reforge_gear(eligible).level, 90)
        reforged = reforge_gear(eligible)
        self.assertEqual(reforge_gear(reforged), reforged)

    def test_drop_simulation_counts_acquisition_cost_for_every_embryo(self):
        result = simulate_drops(
            SimulationOptions(
                runs=100,
                seed=7,
                gear_source="rift_new_1_32",
                item_source="normal_85",
                stop_at_checkpoint=0,
            )
        )

        self.assertEqual(result["simulation_runs"], 100)
        self.assertEqual(result["stop_rate_by_checkpoint"]["0"], 1.0)
        self.assertAlmostEqual(result["gear_acquisition_stamina_avg"], 13.6, places=1)
        self.assertAlmostEqual(result["upgrade_stamina_avg"], 0.0, places=1)
        self.assertGreater(result["total_stamina_avg"], 13.0)

    def test_heroic_gear_marks_drop_cost_unconfirmed_and_uses_own_sale_recovery(self):
        result = simulate_drops(
            SimulationOptions(
                runs=100,
                seed=7,
                gear_source="rift_new_1_32",
                item_source="normal_85",
                rank="Heroic",
                stop_at_checkpoint=3,
            )
        )

        self.assertEqual(result["stop_rate_by_checkpoint"]["3"], 1.0)
        self.assertEqual(result["gear_acquisition_stamina_avg"], 0.0)
        self.assertGreater(result["sell_recovery_avg"], 0.0)
        self.assertFalse(result["missing_recovery_data"])
        self.assertTrue(result["missing_acquisition_data"])

    def test_rift_source_has_higher_success_rate_from_same_speed_embryo(self):
        gear = Gear.from_dict(
            {
                "set": "Speed",
                "slot": "Weapon",
                "mainStat": {"type": "Attack", "value": 525},
                "enhance": 0,
                "rank": "Epic",
                "level": 85,
                "substats": [
                    {"type": "Speed", "value": 4, "rolls": 1},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                    {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                    {"type": "AttackPercent", "value": 8, "rolls": 1},
                ],
            }
        )

        normal = simulate_gear(gear, SimulationOptions(runs=800, seed=11, item_source="normal_85"))
        rift = simulate_gear(gear, SimulationOptions(runs=800, seed=11, item_source="rift_85"))

        self.assertGreaterEqual(rift["success_rate"], normal["success_rate"])
        self.assertGreater(rift["expected_reforge_speed_avg"], normal["expected_reforge_speed_avg"])


if __name__ == "__main__":
    unittest.main()
