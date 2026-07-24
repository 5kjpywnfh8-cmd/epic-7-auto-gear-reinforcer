from __future__ import annotations

import unittest

from tools.research_epic_exact_plus3 import oracle_label
from tools.research_epic_threshold_matrix import (
    T0_VALUES,
    T3_VALUES,
    ThresholdCandidate,
    _candidate_action,
    _node_gate,
    _rule,
    candidates,
)


def _metric(*, false_stops: int = 0, regret: float = 0.0, saved: float = 1.0) -> dict:
    return {
        "clear_positive_false_stop_count": false_stops,
        "total_regret": regret,
        "saved_next_node_stamina": saved,
    }


class EpicThresholdMatrixTest(unittest.TestCase):
    def test_preregistered_matrix_has_all_controlled_routes(self):
        matrix = candidates()
        self.assertEqual(len(matrix), len(T0_VALUES) * len(T3_VALUES))
        self.assertIn(ThresholdCandidate(12, 17), matrix)
        self.assertTrue(ThresholdCandidate(12, 17).is_priority_route)
        self.assertFalse(ThresholdCandidate(14, 16).is_priority_route)

    def test_only_effective_gs_threshold_changes_between_nodes(self):
        zero, three = _rule(12, 0), _rule(17, 3)
        self.assertEqual(zero.current_valid_max, three.current_valid_max)
        self.assertEqual(zero.conversion_value_max, three.conversion_value_max)
        self.assertEqual(zero.terminal_probability_max, 0.002)
        self.assertEqual(three.terminal_probability_max, 0.01)

    def test_candidate_action_uses_the_correct_node_threshold(self):
        candidate = ThresholdCandidate(12, 17)
        row = {"checkpoint": 0, "current_action": "continue", "features": {"effective_gs": 12, "current_valid": 2, "probability": 0.0, "conversion_value": 0.0}}
        self.assertEqual(_candidate_action(row, candidate), "stop")
        row["checkpoint"], row["features"]["effective_gs"] = 3, 16
        self.assertEqual(_candidate_action(row, candidate), "stop")
        row["features"]["effective_gs"] = 18
        self.assertEqual(_candidate_action(row, candidate), "continue")

    def test_node_gate_rejects_positive_false_stop_or_higher_regret(self):
        baseline = _metric(regret=2.0, saved=0.0)
        good = _metric(regret=1.0, saved=3.0)
        result = _node_gate({"plus0": {"formal": baseline, "candidate": good}, "plus3": {"formal": baseline, "candidate": good}})
        self.assertTrue(result["passed"])
        bad = _metric(false_stops=1, regret=1.0, saved=3.0)
        self.assertFalse(_node_gate({"plus0": {"formal": baseline, "candidate": bad}, "plus3": {"formal": baseline, "candidate": good}})["passed"])
