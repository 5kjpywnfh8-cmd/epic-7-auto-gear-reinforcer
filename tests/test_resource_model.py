import unittest

from src.e7_enhance.resource_model import (
    DEFAULT_CONVERSION_GOLD_COST,
    EXPECTED_ENHANCE_EXP_MULTIPLIER,
    PURPLE_HEROIC_CALIBRATION,
    RED_EPIC_CALIBRATION,
    ResourceAmount,
    conversion_stamina_cost,
    gear_source_metadata,
    joint_source_batch_metadata,
    material_cost_for_level,
    marginal_material_stamina_cost,
    red_epic_resource_table,
    resource_snapshot,
)
from src.e7_enhance.enhance_simulator import cost_for_outcome


class ResourceModelTest(unittest.TestCase):
    def test_default_baseline_uses_saint_3_7_and_powder_expected_exp(self):
        table = red_epic_resource_table()
        snapshot = resource_snapshot(3)

        self.assertEqual(table["gear_source"], "riftslash_20_buff")
        self.assertEqual(table["rates"]["gold_per_8_stamina"], 58889.177)
        self.assertEqual(table["rates"]["base_enhance_exp_per_8_stamina"], 1161.1)
        self.assertAlmostEqual(EXPECTED_ENHANCE_EXP_MULTIPLIER, 1.15395, places=5)
        self.assertAlmostEqual(table["rates"]["expected_enhance_exp_per_8_stamina"], 1339.851345, places=6)

        # The latest +1..+3 Epic requirements are 525 + 656 + 788.
        self.assertEqual(snapshot["nominal_enhance_exp"], 1969.0)
        self.assertEqual(snapshot["powder_units"], 9.0)
        self.assertAlmostEqual(snapshot["lower_stone_units"], 0.6, places=6)
        self.assertEqual(snapshot["consumed_gold"], 23040.0)
        self.assertEqual(snapshot["material_mix_base_exp_ratio"], {"powder": 0.5, "lower_stone": 0.5})
        self.assertEqual(snapshot["base_exp_granularity"], 100)
        self.assertAlmostEqual(snapshot["expected_returned_powder_exp"], 143.0, places=6)
        self.assertAlmostEqual(snapshot["consumed_enhance_exp"], 1657.0, places=6)

    def test_material_pool_mixes_powder_and_lower_stones_by_base_exp_contribution(self):
        # 3,450 nominal experience needs 3,000 base input at the published
        # Good/Great/pet expectation.  The long-run pool is exactly 1,500
        # stone experience plus 1,500 powder experience.
        material = material_cost_for_level(3450)

        self.assertEqual(material.expected_input_base_exp, 3000.0)
        self.assertEqual(material.lower_stone_units, 1.0)
        self.assertEqual(material.powder_units, 15.0)
        self.assertEqual(material.lower_stone_base_exp, 1500.0)
        self.assertEqual(material.powder_base_exp, 1500.0)
        self.assertEqual(material.gold, 38400.0)

    def test_non_batch_node_preserves_fifty_fifty_expected_base_exp_mix(self):
        material = material_cost_for_level(1969)

        self.assertEqual(material.expected_input_base_exp, 1800.0)
        self.assertEqual(material.gross_base_material_exp, 1800.0)
        self.assertAlmostEqual(material.powder_base_exp, material.lower_stone_base_exp, places=6)
        self.assertEqual(material.powder_units, 9.0)
        self.assertAlmostEqual(material.lower_stone_units, 0.6, places=6)
        self.assertEqual(material.gold, 23040.0)

    def test_good_great_and_pet_reduce_input_exp_but_not_each_material_gold_price(self):
        material = material_cost_for_level(1969)

        self.assertAlmostEqual(material.expected_effective_exp, 1800 * EXPECTED_ENHANCE_EXP_MULTIPLIER, places=6)
        self.assertEqual(material.powder_gold, 14400.0)
        self.assertEqual(material.lower_stone_gold, 8640.0)
        self.assertEqual(material.gold, material.powder_gold + material.lower_stone_gold)

    def test_heroic_uses_its_own_step_cost_and_recovery_without_invented_drop_rate(self):
        snapshot = resource_snapshot(3, PURPLE_HEROIC_CALIBRATION)

        # The latest +1..+3 Heroic requirements are 473 + 590 + 709.
        self.assertEqual(snapshot["nominal_enhance_exp"], 1772.0)
        self.assertEqual(snapshot["powder_units"], 9.0)
        self.assertAlmostEqual(snapshot["lower_stone_units"], 0.6, places=6)
        self.assertEqual(snapshot["sell_recovered_gold"], 15315.0)
        self.assertEqual(snapshot["sell_recovered_enhance_exp"], 1300.0)
        self.assertAlmostEqual(snapshot["consumed_enhance_exp"], 1646.0, places=6)
        self.assertEqual(snapshot["gear_acquisition_stamina"], None)
        self.assertEqual(snapshot["acquisition_status"], "unconfirmed")

    def test_conversion_cost_is_100k_gold_through_the_resource_model(self):
        expected = RED_EPIC_CALIBRATION.rates.stamina_equivalent(ResourceAmount(gold=100000))

        self.assertEqual(DEFAULT_CONVERSION_GOLD_COST, 100000)
        self.assertAlmostEqual(conversion_stamina_cost(), expected, places=6)

    def test_gold_and_enhance_exp_are_joint_output_bottleneck_cost(self):
        snapshot = resource_snapshot(12)

        self.assertEqual(snapshot["bottleneck"], "enhance_exp")
        self.assertEqual(snapshot["net_gold"], 423755.0)
        self.assertEqual(snapshot["net_enhance_exp"], 13439.0)
        self.assertEqual(snapshot["upgrade_stamina_equivalent"], 92.6)

    def test_plus_12_to_15_marginal_cost_uses_bottleneck_not_sum(self):
        snapshot = resource_snapshot(12)
        marginal = snapshot["marginal_next"]

        self.assertEqual(marginal["to"], 15)
        self.assertEqual(marginal["bottleneck"], "enhance_exp")
        self.assertEqual(marginal["net_gold"], 476160.0)
        self.assertEqual(marginal["net_enhance_exp"], 13490.5)
        self.assertEqual(marginal["stamina_equivalent"], 92.9)

    def test_table_includes_red_gear_acquisition_source_from_image(self):
        table = red_epic_resource_table("rift_hunt")

        self.assertEqual(table["gear_source"], "rift_hunt")
        self.assertEqual(table["checkpoints"][0]["gear_acquisition_stamina"], 50.2)

    def test_confirmed_source_metadata_records_pet_stone_expectations_without_duplicate_pet_gear(self):
        rift = gear_source_metadata("riftslash_20_buff")
        hunt = gear_source_metadata("hunt_buff_craft_heroic")
        collapse = gear_source_metadata("rift_collapse")

        self.assertEqual(rift["source_type"], "dimension_rift")
        self.assertTrue(rift["gear_acquisition_includes_pet_gear"])
        self.assertEqual(rift["extra_lower_stone_probability"], 0.20)
        self.assertEqual(rift["expected_lower_stones_for_100_clears"], 20.0)
        self.assertEqual(rift["expected_lower_stone_base_exp_for_100_clears"], 30000.0)
        self.assertEqual(hunt["extra_lower_stone_probability"], 0.11)
        self.assertEqual(hunt["expected_lower_stones_for_100_clears"], 11.0)
        self.assertEqual(hunt["expected_lower_stone_base_exp_for_100_clears"], 16500.0)
        self.assertEqual(collapse["extra_lower_stone_probability"], 0.11)
        self.assertEqual(collapse["expected_lower_stones_for_100_clears"], 11.0)
        self.assertEqual(collapse["expected_lower_stone_base_exp_for_100_clears"], 16500.0)

    def test_source_credit_accounts_for_lower_stone_gold_and_keeps_legacy_ids_unconfirmed(self):
        source = gear_source_metadata("riftslash_20_buff")
        legacy = gear_source_metadata("rift_new_1_32")

        self.assertEqual(source["lower_stone_use_gold"], 14400)
        self.assertGreater(source["by_rank"]["Epic"]["pet_lower_stone_stamina_credit"], 0)
        self.assertEqual(source["per_rank_acquisition_scope"], "conditional_reference_only_not_for_joint_batch_denominator")
        self.assertLess(source["by_rank"]["Epic"]["net_gear_acquisition_stamina"], 85.0)
        self.assertEqual(source["pet_stone_accounting"], "acquisition_only")
        self.assertEqual(legacy["mapping_status"], "unconfirmed")
        self.assertEqual(legacy["extra_lower_stone_probability"], 0.0)

    def test_riftslash_joint_batch_scales_stones_by_expected_clears_without_recrediting_use_gold(self):
        batch = joint_source_batch_metadata("riftslash_20_buff", "Epic")
        source = gear_source_metadata("riftslash_20_buff")

        self.assertAlmostEqual(batch["expected_clears"], 85.0 / 40.0)
        self.assertAlmostEqual(batch["expected_lower_stone_units"], (85.0 / 40.0) * 0.20)
        self.assertAlmostEqual(
            batch["lower_stone_credit_stamina"],
            (85.0 / 40.0) * 0.20 * 1500 / (1161.1 / 8.0),
        )
        self.assertAlmostEqual(batch["net_batch_acquisition_stamina"], 85.0 - batch["lower_stone_credit_stamina"])
        self.assertAlmostEqual(source["by_rank"]["Epic"]["net_gear_acquisition_stamina"], batch["net_batch_acquisition_stamina"], places=1)
        self.assertEqual(batch["lower_stone_use_gold_accounting"], "preserved_in_enhancement_material_cost")

    def test_riftslash_joint_batch_reports_confirmed_source_gold_once(self):
        batch = joint_source_batch_metadata("riftslash_20_buff", "Epic")
        self.assertEqual(batch["source_gold_per_clear"], 60000)
        self.assertAlmostEqual(batch["expected_source_gold_per_batch"], (85.0 / 40.0) * 60000)
        self.assertEqual(batch["source_gold_accounting"], "once_per_joint_batch_resource_pool")

    def test_pet_stone_credit_is_only_at_acquisition_and_is_not_good_great_adjusted_at_drop_time(self):
        rift = gear_source_metadata("riftslash_20_buff")
        with_acquisition = cost_for_outcome(3, False, True, "riftslash_20_buff", "Epic", "weapon")
        post_acquisition = cost_for_outcome(3, False, False, "riftslash_20_buff", "Epic", "weapon")
        legacy_post_acquisition = cost_for_outcome(3, False, False, "rift_new_1_32", "Epic", "weapon")

        self.assertEqual(rift["expected_lower_stone_base_exp_per_clear"], 300.0)
        self.assertEqual(rift["lower_stone_use_gold"], 14400)
        self.assertLess(with_acquisition["gear_acquisition_stamina"], 85.0)
        self.assertEqual(post_acquisition["total_stamina"], legacy_post_acquisition["total_stamina"])
        snapshot = resource_snapshot(3, RED_EPIC_CALIBRATION, "riftslash_20_buff")
        self.assertEqual(snapshot["lower_stone_gold"], 8640.0)

    def test_accessory_material_opportunity_cost_is_13_times_common_without_changing_nominal_costs(self):
        weapon = marginal_material_stamina_cost(0, 3, "Epic", "weapon")
        neck = marginal_material_stamina_cost(0, 3, "Epic", "neck")

        self.assertAlmostEqual(neck, weapon * 1.3, places=6)
        self.assertEqual(resource_snapshot(3, RED_EPIC_CALIBRATION, slot="weapon")["nominal_enhance_exp"], 1969.0)
        self.assertEqual(resource_snapshot(3, RED_EPIC_CALIBRATION, slot="neck")["nominal_enhance_exp"], 1969.0)


if __name__ == "__main__":
    unittest.main()
