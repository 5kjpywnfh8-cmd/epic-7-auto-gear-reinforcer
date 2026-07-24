import unittest

from tools.research_riftslash_saint_pool import explicit_batch_resource_pool, second_tier_speed_anchors


class RiftslashSaintPoolTest(unittest.TestCase):
    def test_speed_anchor_profiles_are_derived_from_formal_second_tier_and_keep_curve_floor(self):
        anchors = second_tier_speed_anchors()
        self.assertGreaterEqual(anchors["curve_baseline"], 5.0)
        self.assertLessEqual(anchors["tier2_low"], anchors["tier2_mid"])
        self.assertLessEqual(anchors["tier2_mid"], anchors["tier2_high"])
        self.assertGreater(anchors["tier2_low"], 0.0)

    def test_source_stones_offset_actual_lower_stone_demand_before_saint_deficit(self):
        result = explicit_batch_resource_pool(
            source_gold=127500,
            source_lower_stones=0.425,
            powder_base_exp=0,
            lower_stone_units=0.25,
            material_gold=10000,
            conversion_gold=0,
            sell_gold=0,
            sell_exp=0,
            material_scarcity_exp=375,
        )
        self.assertAlmostEqual(result["source_lower_stones_used"], 0.25)
        self.assertAlmostEqual(result["source_lower_stone_surplus"], 0.175)
        self.assertAlmostEqual(result["remaining_lower_stone_units"], 0.0)
        self.assertEqual(result["saint_supplement_stamina"], 0.0)
        self.assertEqual(result["total_stamina"], 85.0)

    def test_gold_and_exp_deficits_use_one_bottleneck_not_a_sum(self):
        result = explicit_batch_resource_pool(
            source_gold=0,
            source_lower_stones=0,
            powder_base_exp=0,
            lower_stone_units=0,
            material_gold=58889.177,
            conversion_gold=0,
            sell_gold=0,
            sell_exp=0,
            material_scarcity_exp=1161.1,
        )
        self.assertAlmostEqual(result["saint_gold_stamina"], 8.0)
        self.assertAlmostEqual(result["saint_exp_stamina"], 8.0)
        self.assertAlmostEqual(result["saint_supplement_stamina"], 8.0)
        self.assertAlmostEqual(result["total_stamina"], 93.0)

    def test_source_gold_is_used_once_and_conserved_before_saint_replacement(self):
        result = explicit_batch_resource_pool(
            source_gold=127500,
            source_lower_stones=0,
            powder_base_exp=0,
            lower_stone_units=0,
            material_gold=200000,
            conversion_gold=0,
            sell_gold=10000,
            sell_exp=0,
            material_scarcity_exp=0,
        )
        self.assertAlmostEqual(result["source_gold_used"], 127500)
        self.assertAlmostEqual(result["source_gold_surplus"], 0)
        self.assertAlmostEqual(result["net_gold_deficit"], 62500)
