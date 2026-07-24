from __future__ import annotations

import unittest

from tools import validate_epic_balanced_holdout as validator


class ValidateEpicBalancedHoldoutTest(unittest.TestCase):
    def test_selected_candidate_is_the_frozen_rule(self):
        rule = validator._candidate_rule()
        self.assertEqual(rule.key, validator.CANDIDATE_KEY)
        self.assertEqual(rule.default, (12, 17))
        self.assertEqual(rule.overrides["pure_output"], (8, 13))
        self.assertEqual(rule.overrides["pure_tank"], (10, 17))

    def test_metric_counts_clear_positive_false_stops(self):
        rows = [{
            "instance_id": "a",
            "features": {"system_group": "pure_output"},
            "current_formal_action": "stop",
            "candidate_action": "stop",
            "oracle": {"label": "clear_positive", "action": "continue", "utility_margin": 0.2},
            "plus3_branches": [],
        }]
        result = validator.metrics(rows, candidate_key="candidate", checkpoint=0)
        self.assertEqual(result["clear_positive_false_stop_count"], 1)
        self.assertEqual(result["clear_positive_recall"], 0.0)
        self.assertAlmostEqual(result["utility_regret"], 0.2)

    def test_high_loss_false_stop_uses_preregistered_margin(self):
        rows = [{
            "instance_id": "a",
            "features": {"system_group": "pure_output"},
            "current_formal_action": "stop",
            "candidate_action": "stop",
            "oracle": {"label": "clear_positive", "action": "continue", "utility_margin": 0.01},
            "plus3_branches": [],
        }]
        result = validator.metrics(rows, candidate_key="candidate", checkpoint=0)
        self.assertEqual(result["high_loss_false_stop_count"], 1)


if __name__ == "__main__":
    unittest.main()
