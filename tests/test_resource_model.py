import unittest

from src.e7_enhance.resource_model import red_epic_resource_table, resource_snapshot


class ResourceModelTest(unittest.TestCase):
    def test_gold_and_enhance_exp_are_joint_output_bottleneck_cost(self):
        snapshot = resource_snapshot(12)

        self.assertEqual(snapshot["bottleneck"], "enhance_exp")
        self.assertEqual(snapshot["net_gold"], 312075.0)
        self.assertEqual(snapshot["net_enhance_exp"], 20325.0)
        self.assertEqual(snapshot["upgrade_stamina_equivalent"], 813.0)

    def test_plus_12_to_15_marginal_cost_uses_bottleneck_not_sum(self):
        snapshot = resource_snapshot(12)
        marginal = snapshot["marginal_next"]

        self.assertEqual(marginal["to"], 15)
        self.assertEqual(marginal["bottleneck"], "enhance_exp")
        self.assertEqual(marginal["net_gold"], 356000.0)
        self.assertEqual(marginal["net_enhance_exp"], 21992.0)
        self.assertEqual(marginal["stamina_equivalent"], 879.7)

    def test_table_includes_red_gear_acquisition_source_from_image(self):
        table = red_epic_resource_table("rift_hunt")

        self.assertEqual(table["gear_source"], "rift_hunt")
        self.assertEqual(table["checkpoints"][0]["gear_acquisition_stamina"], 50.2)


if __name__ == "__main__":
    unittest.main()
