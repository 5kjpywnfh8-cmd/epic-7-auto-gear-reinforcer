from __future__ import annotations

import unittest

from tools.epic_non_speed_early_policy_pareto import generate_conditional_gear, simulate_paths
from tools.external_threshold_strategy import D_THRESHOLDS, decide, simulate_path, terminal_indicators
from tools.research_external_threshold_d import aggregate_explicit_pool, frozen_heroic_outcome


class ExternalThresholdStrategyTest(unittest.TestCase):
    def test_threshold_boundaries_and_or_logic_are_literal(self):
        self.assertEqual(decide("Epic", 0, speed=2, total_official_gs=0, output_effective_gs=0), "continue")
        self.assertEqual(decide("Epic", 3, speed=0, total_official_gs=31, output_effective_gs=0), "continue")
        self.assertEqual(decide("Heroic", 6, speed=0, total_official_gs=0, output_effective_gs=30), "continue")
        self.assertEqual(decide("Heroic", 9, speed=9, total_official_gs=39.9, output_effective_gs=36.9), "stop")
        self.assertEqual(D_THRESHOLDS["Heroic"][9]["speed"], 10)

    def test_heirloom_is_native_total_gs_not_formal_category_or_speed(self):
        self.assertEqual(terminal_indicators(native_total_gs=75, converted_total_gs=70, speed=0, output_gs=0)["native_heirloom"], 1)
        self.assertEqual(terminal_indicators(native_total_gs=74.9, converted_total_gs=75, speed=22, output_gs=60)["native_heirloom"], 0)
        values = terminal_indicators(native_total_gs=74.9, converted_total_gs=75, speed=22, output_gs=60)
        self.assertEqual(values["converted_heirloom"], 1)
        self.assertEqual(values["speed22"], 1)
        self.assertEqual(values["output60"], 1)

    def test_direct_plus9_to_15_still_records_actual_plus12_arrival(self):
        gear = generate_conditional_gear("set_speed", "Epic", 7, slot="weapon")
        path = simulate_paths(gear, "normal_85", runs=1, seed=8)[0]
        result = simulate_path(path)
        # The literal D gate only checks through +9, but an accepted +9 path
        # physically enhances through +12 before reaching +15.
        if result["stop_checkpoint"] == 15:
            self.assertIn(12, result["reached_checkpoints"])

    def test_explicit_pool_uses_powder_and_all_resource_flows_once(self):
        flow = {
            "powder_units": 10.0,
            "lower_stone_units": 1.0,
            "material_gold": 200000.0,
            "conversion_gold": 100000.0,
            "sell_gold": 10000.0,
            "sell_exp_adjusted": 500.0,
            "material_exp_adjusted": 3000.0,
            "lower_stone_adjusted_exp": 1500.0,
        }
        pool = aggregate_explicit_pool(flow)
        self.assertEqual(pool["powder_base_exp"], 1000.0)
        self.assertAlmostEqual(pool["source_lower_stones_used"], 0.425)
        self.assertEqual(pool["source_gold_used"], 127500.0)

    def test_frozen_heroic_baseline_is_not_the_external_threshold_path(self):
        gear = generate_conditional_gear("set_speed", "Heroic", 9, slot="weapon")
        path = simulate_paths(gear, "normal_85", runs=1, seed=10)[0]
        outcome = frozen_heroic_outcome(path, all_stop=True)
        self.assertEqual(outcome["stop_checkpoint"], 0)
