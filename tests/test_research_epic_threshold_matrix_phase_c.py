from __future__ import annotations

import unittest

from tools.research_epic_threshold_matrix_phase_c import RULES, candidate_hash


class PhaseCMappingRepairRulesTest(unittest.TestCase):
    def test_pure_tank_control_rules_keep_corrected_output_protection_fixed(self):
        tank_rules = [rule for rule in RULES if rule.release_class == "tank_control_variable"]
        self.assertEqual(len(tank_rules), 9)
        self.assertEqual(
            {rule.overrides["pure_output"] for rule in tank_rules},
            {(8, 13)},
        )
        self.assertEqual(
            {rule.overrides["pure_tank"] for rule in tank_rules},
            {(t0, t3) for t0 in (8, 10, 12) for t3 in (13, 15, 17)},
        )

    def test_mapping_repair_candidates_have_unique_new_hashes(self):
        hashes = [candidate_hash(rule) for rule in RULES]
        self.assertEqual(len(hashes), len(set(hashes)))
        self.assertNotIn("balanced_output_m4", [rule.key for rule in RULES if rule.release_class == "tank_control_variable"])
