import unittest

from src.e7_enhance.dp_assisted_analysis import section_decision


class DpAssistedAnalysisTest(unittest.TestCase):
    def test_low_disagreement_does_not_enable_dp_assisted(self):
        checkpoints = {
            "9": checkpoint(0.02, 0, 2, 0.2),
            "12": checkpoint(0.03, 1, 2, 0.3),
        }

        decision = section_decision(checkpoints)

        self.assertFalse(decision["add_dp_assisted"])

    def test_high_disagreement_enables_dp_assisted(self):
        checkpoints = {
            "9": checkpoint(0.12, 0, 12, 0.8),
            "12": checkpoint(0.03, 0, 3, 0.2),
        }

        decision = section_decision(checkpoints)

        self.assertTrue(decision["add_dp_assisted"])
        self.assertIn("+9", decision["scope"])
        self.assertEqual(decision["bias"], "round2_policy_more_conservative")

    def test_large_utility_gap_enables_dp_assisted_review(self):
        checkpoints = {
            "9": checkpoint(0.02, 0, 2, 1.5),
            "12": checkpoint(0.01, 0, 1, 0.2),
        }

        decision = section_decision(checkpoints)

        self.assertTrue(decision["add_dp_assisted"])
        self.assertTrue(any("top expected_utility_gap" in reason for reason in decision["reasons"]))


def checkpoint(disagreement_rate, policy_continue_dp_stop, policy_stop_dp_continue, top_gap):
    return {
        "disagreement_rate": disagreement_rate,
        "confusion_matrix": {
            "both_continue": 0,
            "both_stop": 100,
            "policy_continue_dp_stop": policy_continue_dp_stop,
            "policy_stop_dp_continue": policy_stop_dp_continue,
        },
        "top_utility_gap": {"max": top_gap},
        "disagreement_by_category": {"输出": policy_continue_dp_stop + policy_stop_dp_continue},
    }


if __name__ == "__main__":
    unittest.main()
