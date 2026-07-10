import unittest

from src.e7_enhance.strategy_defaults import STRATEGY_VERSION, default_strategy_for


class StrategyDefaultsTest(unittest.TestCase):
    def test_normal_epic_defaults_to_dp_assisted(self):
        strategy = default_strategy_for(item_source="normal_85", rank="Epic", gear_source="rift_new_1_32")

        self.assertEqual(STRATEGY_VERSION, "baili-formal-dp-v1")
        self.assertEqual(strategy.policy_name, "normal_epic_dp_assisted")
        self.assertTrue(strategy.enable_dp_assist)

    def test_normal_heroic_defaults_to_dp_assisted(self):
        strategy = default_strategy_for(item_source="normal_85", rank="Heroic", gear_source="rift_new_1_32")

        self.assertEqual(strategy.policy_name, "normal_heroic_dp_assisted")
        self.assertTrue(strategy.enable_dp_assist)

    def test_rift_epic_defaults_to_dp_assisted(self):
        strategy = default_strategy_for(item_source="rift_85", rank="Epic", gear_source="rift_new_1_32")

        self.assertEqual(strategy.policy_name, "rift_epic_dp_assisted")
        self.assertTrue(strategy.enable_dp_assist)


if __name__ == "__main__":
    unittest.main()
