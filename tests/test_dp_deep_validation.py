import unittest

from src.e7_enhance.dp_deep_validation import DEEP_RUNS, recommendation_for, sample_stats


class DpDeepValidationTest(unittest.TestCase):
    def test_deep_validation_scope_uses_only_published_dp_resource_calibrations(self):
        self.assertEqual(set(DEEP_RUNS), {"normal_epic"})

    def test_recommendation_switches_when_dp_ci_is_better(self):
        seed_results = [
            {"cost_per_baili_score_delta": -100},
            {"cost_per_baili_score_delta": -110},
            {"cost_per_baili_score_delta": -120},
            {"cost_per_baili_score_delta": -90},
            {"cost_per_baili_score_delta": -105},
        ]

        recommendation = recommendation_for(seed_results, [930, 940, 935, 925, 945], [810, 815, 820, 812, 818])

        self.assertEqual(recommendation["action"], "switch_default")
        self.assertTrue(recommendation["ci95_non_overlapping"])

    def test_sample_stats_reports_95_ci(self):
        stats = sample_stats([1, 2, 3, 4, 5])

        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["mean"], 3.0)
        self.assertLess(stats["ci95_low"], stats["mean"])
        self.assertGreater(stats["ci95_high"], stats["mean"])


if __name__ == "__main__":
    unittest.main()
