from __future__ import annotations

import unittest

from tools.research_epic_stage_balanced import StagePolicy, markdown, stage_action


class EpicStageBalancedTest(unittest.TestCase):
    def test_shared_gs_threshold_cannot_stop_a_plus3_path_that_already_passed_plus0(self):
        shared = StagePolicy("baseline", (30, 18), (30, 18))
        features = {"effective_gs": 18.0, "hit_target": False, "current_valid": 2, "feasible_valid": 4, "slot_limited_three": False, "category_tier": 0, "probability": 1.0, "conversion_value": 0.0}

        self.assertEqual(stage_action(shared, 0, features), "cautious_continue")
        self.assertEqual(stage_action(shared, 3, features), "cautious_continue")

    def test_stage_specific_gs_and_hit_rules_can_stop_at_plus3(self):
        policy = StagePolicy("hit", (30, 18), (34, 22), use_hit=True)
        missed = {"effective_gs": 23.0, "hit_target": False, "current_valid": 3, "feasible_valid": 4, "slot_limited_three": False, "category_tier": 0, "probability": 1.0, "conversion_value": 0.0}

        self.assertEqual(stage_action(policy, 3, missed), "stop")

    def test_markdown_reads_the_primary_scenario_from_the_scenario_table(self):
        data = {
            "summary": {
                "primary_scenario": "formal_only/baili_marginal_low/baseline",
                "scenarios": {"formal_only/baili_marginal_low/baseline": {
                    "order": ["B_stage_gs"],
                    "rates": {"B_stage_gs": {"interval95": [1.0, 2.0]}},
                    "ablations": {},
                }},
                "oracle": {"B_stage_gs": {"oracle_positive_recall": 1.0, "false_stop_count": 0, "total_regret": 0.0}},
                "stage_retention": [],
            },
        }
        self.assertIn("B_stage_gs", markdown(data))
