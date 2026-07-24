import unittest

from tools.audit_epic_concentration_baseline_drift import (
    SEEDS,
    _branch_contract,
    _fixed_replays,
    _historical_bridge,
)
from tools.research_epic_concentration_rescue_exact import Gear
from tools.research_epic_exact_plus3 import load_real_plus0
from tools import research_epic_concentration_rescue_exact as v4
from tools.epic_non_speed_early_policy_pareto import _source_rank_gears, GEAR_SOURCE


class BaselineDriftAuditTests(unittest.TestCase):
    def test_epic_branch_contract_has_complete_probability_mass(self):
        gears = [Gear.from_dict(row["gear"]) for row in load_real_plus0(v4.DEFAULT_RECORDS, "development")]
        contract = _branch_contract(gears)
        self.assertEqual(contract["gear_count"], 157)
        self.assertTrue(contract["branch_probability_sum_is_one"])
        self.assertAlmostEqual(contract["weighted_path_mass"], 157.0, places=12)
        self.assertGreater(contract["branch_count_total"], contract["gear_count"])

    def test_fixed_replay_is_candidate_isolated_and_v4_changes_epic_action(self):
        replay = _fixed_replays()
        for row in replay.values():
            self.assertTrue(row["baseline_only_equals_candidate_impossible"])
            self.assertTrue(row["baseline_and_impossible_action_sequences_equal"])
        self.assertTrue(replay["Epic"]["v4_action_sequence_differs_from_baseline"])
        self.assertTrue(replay["Epic"]["v4_differs_only_if_rescue_action_changes"])

    def test_historical_bridge_keeps_v3_v4_baseline_and_resource_conservation(self):
        bridge = _historical_bridge()
        for seed in SEEDS:
            v3 = bridge["v3"]["per_seed"][str(seed)]
            v4 = bridge["v4"]["per_seed"][str(seed)]
            self.assertAlmostEqual(v3["value_per_100k"], v4["value_per_100k"], places=12)
            self.assertAlmostEqual(v4["rift_stamina_per_100k"] + v4["saint_stamina_per_100k"], 100000.0, places=6)
            self.assertEqual(v3["heroic"]["shards"], 80)


if __name__ == "__main__":
    unittest.main()
