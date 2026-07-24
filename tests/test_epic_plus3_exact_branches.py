from __future__ import annotations

import unittest

from src.e7_enhance.models import Gear
from tools.epic_plus3_exact_branches import (
    enumerate_normal_epic_plus3,
    official_plus3_distribution,
    weighted_sum,
)


def _gear() -> Gear:
    return Gear.from_dict({
        "set": "Speed",
        "slot": "Weapon",
        "mainStat": {"type": "Attack", "value": 500},
        "enhance": 0,
        "level": 85,
        "rank": "Epic",
        "substats": [
            {"type": "Attack", "value": 33, "rolls": 1},
            {"type": "AttackPercent", "value": 4, "rolls": 1},
            {"type": "Speed", "value": 2, "rolls": 1},
            {"type": "CriticalHitChancePercent", "value": 3, "rolls": 1},
        ],
        "rollHistory": [],
        "instanceId": "exact-plus3-test",
        "itemSource": "normal_85",
    })


class EpicPlus3ExactBranchesTest(unittest.TestCase):
    def test_every_official_profile_is_normalized(self):
        for key in ("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "eff", "res", "spd", "crit", "cdmg"):
            self.assertAlmostEqual(sum(probability for _value, probability in official_plus3_distribution(key)), 1.0, places=12, msg=key)

    def test_flat_attack_endpoints_have_distinct_official_probabilities(self):
        distribution = dict(official_plus3_distribution("atkFlat"))
        self.assertNotEqual(distribution[33], distribution[46])
        self.assertGreater(distribution[33], distribution[46])

    def test_flat_health_uses_official_endpoints(self):
        distribution = dict(official_plus3_distribution("hpFlat"))
        self.assertEqual(min(distribution), 157)
        self.assertEqual(max(distribution), 202)
        self.assertLess(distribution[157], distribution[158])

    def test_four_targets_times_discrete_rolls_have_unit_probability(self):
        branches = enumerate_normal_epic_plus3(_gear())
        self.assertEqual(len(branches), 14 + 5 + 4 + 3)
        self.assertAlmostEqual(sum(branch.probability for branch in branches), 1.0, places=12)

    def test_branch_updates_only_the_selected_stat_and_history(self):
        branch = next(row for row in enumerate_normal_epic_plus3(_gear()) if row.target_key == "atkFlat" and row.delta == 33)
        self.assertEqual(branch.gear.enhance, 3)
        self.assertEqual(branch.gear.substats[0].normalized_value, 66)
        self.assertEqual(branch.gear.substats[0].rolls, 2)
        self.assertEqual(branch.gear.substats[1].normalized_value, 4)
        self.assertEqual(branch.gear.roll_history[-1].enhance, 3)
        self.assertEqual(branch.gear.roll_history[-1].value, 33)

    def test_weighted_sum_matches_a_hand_calculated_target_probability(self):
        branches = enumerate_normal_epic_plus3(_gear())
        attack_target_probability = weighted_sum(branches, lambda branch: 1.0 if branch.target_key == "atkFlat" else 0.0)
        self.assertAlmostEqual(attack_target_probability, 0.25, places=12)
