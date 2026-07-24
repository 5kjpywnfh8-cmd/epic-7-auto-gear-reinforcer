from __future__ import annotations

import unittest

from tools.research_epic_high_confidence_stop import EPSILON, SAFE_STOP_RULES, oracle_label, safe_negative_action


class EpicHighConfidenceStopTest(unittest.TestCase):
    def test_epsilon_is_fixed_from_solver_numeric_tolerance(self):
        self.assertGreater(EPSILON, 0.0)
        self.assertEqual(oracle_label(EPSILON), "boundary")
        self.assertEqual(oracle_label(EPSILON * 1.01), "clear_positive")

    def test_safe_cover_requires_every_frozen_negative_condition(self):
        rule = SAFE_STOP_RULES[3]
        base = {
            "checkpoint": 3, "effective_gs": rule.effective_gs_max,
            "current_valid": rule.current_valid_max, "probability": rule.terminal_probability_max,
            "conversion_value": rule.conversion_value_max,
        }
        self.assertEqual(safe_negative_action(base), "stop")
        for key, value in (("effective_gs", rule.effective_gs_max + 0.01), ("current_valid", 2), ("probability", rule.terminal_probability_max + 0.0001), ("conversion_value", rule.conversion_value_max + 0.01)):
            changed = dict(base); changed[key] = value
            self.assertEqual(safe_negative_action(changed), "continue", key)

    def test_plus0_and_plus3_use_independent_frozen_rules(self):
        self.assertNotEqual(SAFE_STOP_RULES[0], SAFE_STOP_RULES[3])
