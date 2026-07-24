from __future__ import annotations

import unittest
from pathlib import Path

from tools.research_epic_exact_plus3 import (
    DEVELOPMENT_EXPECTED_COUNT,
    FROZEN_EXPECTED_COUNT,
    SafeStopRule,
    action_for_rule,
    load_real_plus0,
    oracle_label,
    select_rule,
    weighted_metrics,
)


def _row(*, weight: float, margin: float, current: str = "continue", gs: float = 6.0, valid: int = 1, probability: float = 0.0, conversion: float = 0.0) -> dict:
    return {
        "weight": weight,
        "instance_id": f"item-{weight}-{margin}-{gs}",
        "current_action": current,
        "features": {"effective_gs": gs, "current_valid": valid, "probability": probability, "conversion_value": conversion},
        "oracle": {"utility_margin": margin, "forced_continue_stamina": 10.0},
        "oracle_label": oracle_label(margin),
    }


class ResearchEpicExactPlus3Test(unittest.TestCase):
    def test_rule_never_changes_a_formal_stop_to_continue(self):
        rule = SafeStopRule(20, 2, 0.1, 9)
        self.assertEqual(action_for_rule("stop", _row(weight=1, margin=-1)["features"], rule), "stop")

    def test_weighted_metrics_respect_branch_weight(self):
        rule = SafeStopRule(8, 1, 0.002, 3)
        rows = [_row(weight=0.25, margin=-2), _row(weight=0.75, margin=2, gs=20)]
        metrics = weighted_metrics(rows, rule)
        self.assertAlmostEqual(metrics["stopped_weight"], 0.25)
        self.assertEqual(metrics["clear_positive_false_stop_count"], 0)
        self.assertAlmostEqual(metrics["saved_next_node_stamina"], 2.5)

    def test_selector_rejects_rules_that_stop_a_clear_positive_state(self):
        rows = [_row(weight=1.0, margin=2.0, gs=6.0, valid=1, probability=0.0, conversion=0.0)]
        rule, selection = select_rule(rows)
        self.assertIsNone(rule)
        self.assertEqual(selection["selection"], "no_safe_stop_rule")

    def test_real_population_excludes_normalized_boots(self):
        records = Path(__file__).resolve().parents[1] / "manual_acceptance" / "real_sample_records.json"
        self.assertEqual(len(load_real_plus0(records, "development")), DEVELOPMENT_EXPECTED_COUNT)
        self.assertEqual(len(load_real_plus0(records, "frozen_validation")), FROZEN_EXPECTED_COUNT)
