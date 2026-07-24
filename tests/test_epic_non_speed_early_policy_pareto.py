import json
import inspect
from pathlib import Path
import unittest

from tools.epic_non_speed_early_policy_pareto import (
    ACTIONS,
    Strategy,
    build_partition,
    conditional_gear_record,
    paired_rift_gear,
    evaluate_strategies,
    generate_conditional_gear,
    heroic_fixed_baseline_summary,
    riftslash_joint_batch_metadata,
    riftslash_joint_batch_metrics,
    simulate_strategy_path,
    simulate_paths,
    strategy_actions,
    summarize_incremental_cost,
)


ROOT = Path(__file__).resolve().parents[1]


class EpicNonSpeedEarlyPolicyParetoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(
            (ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json").read_text(encoding="utf-8")
        )
        cls.records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))

    def test_partition_freezes_reviewed_holdout_and_excludes_speed_hard_route_from_training(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)

        self.assertEqual(len(partition["holdout"]), 22)
        self.assertEqual(len(partition["blind"]), 24)
        self.assertFalse(partition["training_ids"] & partition["holdout_ids"])
        self.assertFalse(partition["training_ids"] & partition["blind_ids"])
        self.assertFalse(partition["blind_ids"] & partition["holdout_ids"])
        self.assertTrue(partition["speed_hard_ids"])
        self.assertTrue(all(not item["speed_hard"] for item in partition["training"]))

    def test_epic_paths_are_seed_stable_and_have_five_existing_substat_events(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)
        gear = partition["training"][0]["gear"]

        first = simulate_paths(gear, "normal_85", runs=12, seed=20260712)
        second = simulate_paths(gear, "normal_85", runs=12, seed=20260712)

        self.assertEqual(first, second)
        self.assertTrue(all(len(path[15].roll_history) == 5 for path in first))

    def test_rift_pair_is_legal_and_uses_distinct_source_ranges(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)
        normal = partition["training"][0]["gear"]
        rift = paired_rift_gear(normal)

        self.assertEqual(rift.rank, "Epic")
        self.assertEqual(rift.slot, normal.slot)
        self.assertNotEqual(rift.code, normal.code)
        self.assertEqual(len(rift.substats), len(normal.substats))

    def test_candidate_strategies_return_only_three_actions_and_keep_speed_outside_non_speed_training(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)
        actions = strategy_actions(partition["training"][0]["gear"], "normal_85")

        self.assertGreaterEqual(len(actions), 10)
        self.assertTrue(all(action in ACTIONS for action in actions.values()))

    def test_incremental_cost_excludes_embryo_cost_and_accessory_cost_is_higher(self):
        common = summarize_incremental_cost("weapon", "Epic", 0, 3)
        accessory = summarize_incremental_cost("neck", "Epic", 0, 3)

        self.assertEqual(common["gear_acquisition_stamina"], 0.0)
        self.assertGreater(accessory["upgrade_stamina"], common["upgrade_stamina"])
        self.assertGreater(common["sell_recovery_stamina"], 0.0)

    def test_cautious_action_only_reaches_next_node_and_uses_that_stop_recovery(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)
        gear = partition["training"][0]["gear"]
        path = simulate_paths(gear, "normal_85", runs=1, seed=20260712)[0]
        cautious = Strategy("test_cautious", "test", lambda _: "cautious_continue")

        result = simulate_strategy_path(
            path,
            "normal_85",
            cautious,
            formal_followup=lambda _: False,
        )

        self.assertEqual(result["stop_checkpoint"], 6)
        self.assertEqual(result["actions"][0], "cautious_continue")
        self.assertEqual(result["actions"][3], "cautious_continue")
        self.assertEqual(
            result["net_stamina"],
            summarize_incremental_cost(gear.slot, "Epic", 0, 6)["net_stamina"],
        )

    def test_later_formal_policy_is_rechecked_at_each_reached_checkpoint(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)
        gear = partition["training"][0]["gear"]
        path = simulate_paths(gear, "normal_85", runs=1, seed=20260712)[0]
        always_continue = Strategy("test_continue", "test", lambda _: "continue")
        checked = []

        result = simulate_strategy_path(
            path,
            "normal_85",
            always_continue,
            formal_followup=lambda state: checked.append(state.enhance) or True,
        )

        self.assertEqual(result["stop_checkpoint"], 15)
        self.assertEqual(checked, [6, 9, 12])
        self.assertEqual(result["reached_checkpoints"], [0, 3, 6, 9, 12, 15])

    def test_result_reports_next_node_and_continuous_value_efficiency_separately(self):
        partition = build_partition(self.source, self.records, blind_size=24, seed=20260712)
        result = evaluate_strategies([partition["training"][0]["gear"]], "normal_85", runs=2, seed=20260712)
        row = result["A_current_review"]

        self.assertEqual(row["actual_end_to_end_cost"]["stamina"], row["average_incremental_stamina"])
        self.assertIn("3", row["next_node_costs"])
        self.assertIn("6", row["next_node_costs"])
        self.assertIn("expected_terminal_target_gs", row)
        self.assertIn("expected_target_gs_per_100_stamina", row)
        self.assertNotIn("gear_acquisition_stamina", row["actual_end_to_end_cost"])

    def test_conditional_generation_requires_explicit_known_set(self):
        with self.assertRaisesRegex(ValueError, "set_code"):
            generate_conditional_gear(None, "Epic", 20260712)
        with self.assertRaisesRegex(ValueError, "unknown set_code"):
            generate_conditional_gear("not_a_set", "Epic", 20260712)

    def test_conditional_generation_is_seed_stable_and_preserves_set(self):
        first = generate_conditional_gear("set_speed", "Epic", 20260712, slot="ring", main_stat="atkPct")
        second = generate_conditional_gear("set_speed", "Epic", 20260712, slot="ring", main_stat="atkPct")

        self.assertEqual(first, second)
        self.assertEqual(first.set, "set_speed")
        self.assertEqual(first.rank, "Epic")
        self.assertEqual(first.slot, "ring")
        self.assertEqual(first.main_stat.key, "atkPct")
        self.assertEqual(len(first.substats), 4)
        self.assertNotIn(first.main_stat.key, {stat.key for stat in first.substats})
        self.assertEqual(len({stat.key for stat in first.substats}), 4)

    def test_conditional_generation_enforces_slot_rules_rank_and_metadata(self):
        heroic = generate_conditional_gear("set_def", "Heroic", 7, slot="armor")
        self.assertEqual(heroic.main_stat.key, "defFlat")
        self.assertEqual(len(heroic.substats), 3)
        self.assertNotIn("atkFlat", {stat.key for stat in heroic.substats})
        self.assertNotIn("atkPct", {stat.key for stat in heroic.substats})
        with self.assertRaisesRegex(ValueError, "Rare"):
            generate_conditional_gear("set_def", "Rare", 7)
        with self.assertRaisesRegex(ValueError, "Invalid main stat"):
            generate_conditional_gear("set_def", "Epic", 7, slot="weapon", main_stat="hpPct")

        record = conditional_gear_record("set_def", "Heroic", 7, slot="armor")
        self.assertTrue(record["synthetic"])
        self.assertEqual(record["generation_mode"], "conditional_set")
        self.assertEqual(record["set_code"], "set_def")
        self.assertEqual(record["generation_rule"], "normal_85 legal conditional generation")

    def test_conditional_set_does_not_change_marginal_enhancement_cost(self):
        speed = generate_conditional_gear("set_speed", "Epic", 9, slot="neck", main_stat="crit")
        defense = generate_conditional_gear("set_def", "Epic", 9, slot="neck", main_stat="crit")
        self.assertNotEqual(speed.set, defense.set)
        self.assertEqual(
            summarize_incremental_cost(speed.slot, speed.rank, 0, 3),
            summarize_incremental_cost(defense.slot, defense.rank, 0, 3),
        )

    def test_conditional_generation_uses_left_fixed_and_right_legal_main_stats(self):
        self.assertEqual(generate_conditional_gear("set_att", "Epic", 1, slot="weapon").main_stat.key, "atkFlat")
        self.assertEqual(generate_conditional_gear("set_att", "Epic", 1, slot="helm").main_stat.key, "hpFlat")
        self.assertEqual(generate_conditional_gear("set_att", "Epic", 1, slot="armor").main_stat.key, "defFlat")
        self.assertIn(generate_conditional_gear("set_att", "Epic", 1, slot="neck").main_stat.key, {"atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "crit", "cdmg"})
        self.assertIn(generate_conditional_gear("set_att", "Epic", 1, slot="ring").main_stat.key, {"atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "eff", "res"})
        self.assertIn(generate_conditional_gear("set_att", "Epic", 1, slot="boot").main_stat.key, {"atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "spd"})

    def test_path_simulation_preserves_explicit_set_without_selected_sets(self):
        gear = generate_conditional_gear("set_counter", "Epic", 12, slot="weapon")
        path = simulate_paths(gear, "normal_85", runs=1, seed=21)[0]

        self.assertTrue(all(state.set == "set_counter" for state in path.values()))
        self.assertNotIn("selected_sets", inspect.signature(generate_conditional_gear).parameters)

    def test_riftslash_joint_batch_uses_one_source_cost_and_heroic_yield_sensitivity(self):
        metadata = riftslash_joint_batch_metadata()

        self.assertEqual(metadata["epic_expected_per_batch"], 1.0)
        self.assertAlmostEqual(metadata["heroic_expected_per_batch"], 85.0 / 23.81)
        self.assertAlmostEqual(metadata["net_batch_acquisition_stamina"], 80.608, places=3)
        self.assertFalse(metadata["heroic_yield_confirmed"])

        epic = {
            "A_current_review": {
                "expected_terminal_formal_value_at_15": 10.0,
                "average_incremental_stamina": 5.0,
            },
            "C_category_probability": {
                "expected_terminal_formal_value_at_15": 12.0,
                "average_incremental_stamina": 8.0,
            },
        }
        heroic_baseline = {
            "expected_terminal_formal_value_at_15": 2.0,
            "average_incremental_stamina": 3.0,
        }
        heroic_stop = {
            "expected_terminal_formal_value_at_15": 0.0,
            "average_incremental_stamina": 0.0,
        }

        joint = riftslash_joint_batch_metrics(epic, heroic_baseline, heroic_stop)
        baseline = joint["heroic_current_baseline"]["heroic_yield_baseline"]["results"]["A_current_review"]
        expected_cost = metadata["net_batch_acquisition_stamina"] + 5.0 + (85.0 / 23.81) * 3.0

        self.assertAlmostEqual(baseline["total_stamina_per_batch"], expected_cost)
        self.assertNotAlmostEqual(baseline["total_stamina_per_batch"], metadata["net_batch_acquisition_stamina"] + 5.0 + (85.0 / 23.81) * (3.0 + 22.5))
        self.assertLess(
            joint["heroic_current_baseline"]["heroic_yield_low_20pct"]["heroic_expected_per_batch"],
            joint["heroic_current_baseline"]["heroic_yield_high_20pct"]["heroic_expected_per_batch"],
        )

    def test_heroic_fixed_baseline_does_not_enable_dp(self):
        heroic = generate_conditional_gear("set_def", "Heroic", 99, slot="armor")

        baseline = heroic_fixed_baseline_summary([heroic], "normal_85", runs=1, seed=20260712)
        stopped = heroic_fixed_baseline_summary([heroic], "normal_85", runs=1, seed=20260712, stop_all=True)

        self.assertEqual(baseline["policy_name"], "baili_marginal_low")
        self.assertEqual(baseline["resource_calibration_status"], "unpublished")
        self.assertFalse(baseline["dp_enabled"])
        self.assertTrue(stopped["stop_all"])
        self.assertEqual(stopped["expected_terminal_formal_value_at_15"], 0.0)


if __name__ == "__main__":
    unittest.main()
