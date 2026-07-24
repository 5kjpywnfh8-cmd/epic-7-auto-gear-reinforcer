import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.e7_enhance.models import Gear, Stat
from src.e7_enhance.rules import OFFICIAL_SCORE_WEIGHTS
from tools.research_epic_attack_concentration import (
    ATTACK_KEYS,
    SCHEMA_VERSION,
    STUDY,
    AttackCandidate,
    _attack_concentration,
    _gear_hash,
    _outcome,
    _valid_shard,
    attack_compatibility,
    attack_compatibility_from_snapshot,
    exact_attack_distribution,
    exact_attack_probability,
)


def _gear(*, rank="Epic", enhance=12, attack=20.0, attack_rolls=3, flat_attack=None, substats=4):
    rows = [
        Stat("AttackPercent", attack, rolls=attack_rolls),
        *([Stat("Attack", flat_attack, rolls=1)] if flat_attack is not None else []),
        Stat("CriticalHitChancePercent", 5, rolls=1),
        Stat("EffectivenessPercent", 5, rolls=1),
        Stat("HealthPercent", 5, rolls=1),
    ]
    return Gear(
        set="set_speed",
        slot="neck",
        main_stat=Stat("CriticalHitChancePercent", 0),
        enhance=enhance,
        level=85,
        rank=rank,
        substats=rows[:substats],
        reforge_eligible=True,
    )


def _snapshot(category, set_group, source_row, *, qualified=True):
    return {
        "category": category,
        "candidate": {
            "category": category,
            "qualified": qualified,
            "rejection_reasons": [],
            "set_group": set_group,
            "source_row": source_row,
        },
    }


class AttackConcentrationExactStudyTests(unittest.TestCase):
    def test_compatibility_fails_closed_for_non_attack_systems_and_bruiser_hpdef(self):
        cases = {
            "输出": ("output", "R5-R10", True),
            "输出(必爆)": ("critless", "R11-R16", True),
            "半肉(通用)": ("bruiser", "R47-R52", True),
            "半肉(白字)": ("bruiserFlat", "R53-R58", True),
            "半肉(血防)": ("bruiserHpDef", "R41-R46", False),
            "纯肉": ("pureTank", "R23-R28", False),
            "双效": ("dual", "R35-R40", False),
            "unknown": ("output", "R5-R10", False),
        }
        for category, (set_group, source_row, expected) in cases.items():
            result = attack_compatibility_from_snapshot(_snapshot(category, set_group, source_row))
            self.assertEqual(result["compatible"], expected, category)

    def test_compatibility_binds_source_row_and_selected_valid_attack_keys(self):
        mismatch = attack_compatibility_from_snapshot(_snapshot("输出", "output", "R11-R16"))
        self.assertFalse(mismatch["compatible"])
        result = attack_compatibility_from_snapshot(_snapshot("半肉(白字)", "bruiserFlat", "R53-R58"))
        self.assertTrue(result["compatible"])
        self.assertEqual(result["attack_valid_keys"], ["atkFlat", "atkPct"])
        output = attack_compatibility_from_snapshot(_snapshot("输出", "output", "R5-R10"))
        self.assertEqual(output["attack_valid_keys"], ["atkFlat", "atkPct"])

    def test_node_compatibility_is_recomputed_from_current_selected_candidate(self):
        state = _gear(enhance=6)
        snapshots = iter((
            _snapshot("纯肉", "pureTank", "R23-R28"),
            _snapshot("输出", "output", "R5-R10"),
        ))
        with patch("tools.research_epic_attack_concentration.phase_b.selected_candidate_snapshot", side_effect=lambda _state: next(snapshots)):
            self.assertFalse(attack_compatibility(state)["compatible"])
            self.assertTrue(attack_compatibility(state)["compatible"])

    def test_attack_concentration_uses_official_flat_weight_not_raw_addition(self):
        gear = _gear(enhance=15, attack=8.0, attack_rolls=1, flat_attack=39.0)
        expected = 8.0 * OFFICIAL_SCORE_WEIGHTS["atkPct"] + 39.0 * OFFICIAL_SCORE_WEIGHTS["atkFlat"]
        self.assertAlmostEqual(_attack_concentration(gear, ATTACK_KEYS), expected)
        self.assertNotEqual(_attack_concentration(gear, ATTACK_KEYS), 47.0)

    def test_exact_probability_matches_full_distribution_and_has_low_probability_tail(self):
        gear = _gear(enhance=12, attack=20.0, attack_rolls=3, flat_attack=39.0)
        distribution = exact_attack_distribution(gear)
        self.assertAlmostEqual(sum(probability for _value, probability in distribution), 1.0, places=12)
        threshold = next(value for value, _probability in reversed(distribution) if 0.0 < sum(p for final, p in distribution if final >= value) < 0.10)
        expected = sum(probability for value, probability in distribution if value >= threshold)
        self.assertGreater(expected, 0.0)
        self.assertLess(expected, 0.10)
        self.assertAlmostEqual(exact_attack_probability(gear, threshold), expected, places=12)

    def test_heroic_plus12_adds_new_fourth_stat_before_plus15_and_invalid_key_still_dilutes(self):
        gear = _gear(rank="Heroic", enhance=9, attack=20.0, attack_rolls=3, flat_attack=None, substats=3)
        distribution = exact_attack_distribution(gear, ("atkPct",))
        self.assertAlmostEqual(sum(probability for _value, probability in distribution), 1.0, places=12)
        self.assertGreater(len(distribution), 1)
        # A non-attack fourth stat remains a legal branch and leaves a
        # probability mass at the initial reforge value.
        minimum, probability = distribution[0]
        self.assertGreater(probability, 0.0)
        self.assertGreater(minimum, 0.0)

    def test_invalid_flat_attack_does_not_score_but_still_occupies_a_future_hit_slot(self):
        gear = _gear(enhance=12, attack=20.0, attack_rolls=3, flat_attack=39.0)
        distribution = exact_attack_distribution(gear, ("atkPct",))
        initial = _attack_concentration(gear, ("atkPct",))
        # The reforge value has to be used for the actual terminal mass.
        terminal_initial = exact_attack_distribution(_gear(enhance=15, attack=20.0, attack_rolls=3, flat_attack=39.0), ("atkPct",))[0][0]
        self.assertNotEqual(initial, terminal_initial)
        unchanged_probability = sum(probability for value, probability in distribution if value == terminal_initial)
        self.assertAlmostEqual(unchanged_probability, 0.75, places=12)

    def test_plus15_has_no_future_roll_and_reforge_is_applied_once(self):
        gear = _gear(enhance=15, attack=20.0, attack_rolls=3, flat_attack=39.0)
        distribution = exact_attack_distribution(gear)
        self.assertEqual(len(distribution), 1)
        value, probability = distribution[0]
        self.assertEqual(probability, 1.0)
        self.assertGreater(value, _attack_concentration(gear, ATTACK_KEYS))

    def test_balanced_rescues_at_ten_percent_and_reference_is_not_a_release_mode(self):
        state = _gear(enhance=6)
        path = {6: state, 9: state, 12: state, 15: state}
        candidate = AttackCandidate("p90", 0.90, 23.0, "balanced")
        context = {"compatible": True, "category": "输出", "attack_valid_keys": ["atkPct"], "cache_key": ["输出", "R5-R10", "output", "output", ["atkPct"], ["atkPct"], True]}
        with patch("tools.research_epic_attack_concentration._baseline_action", return_value="stop"), \
             patch("tools.research_epic_attack_concentration.attack_compatibility", return_value=context), \
             patch("tools.research_epic_attack_concentration.exact_attack_probability", return_value=0.10):
            outcome, info = _outcome(path, candidate, {})
        self.assertEqual(outcome["stop_checkpoint"], 15)
        self.assertEqual(info["first_rescue_node"], 6)
        self.assertEqual(info["candidate_induced_stops"], 0.0)

    def test_p_gte_ten_and_p_gt_zero_have_different_actions_at_five_percent(self):
        state = _gear(enhance=6)
        path = {6: state, 9: state, 12: state, 15: state}
        context = {"compatible": True, "category": "输出", "attack_valid_keys": ["atkPct"], "cache_key": ["输出", "R5-R10", "output", "output", ["atkPct"], ["atkPct"], True]}
        with patch("tools.research_epic_attack_concentration._baseline_action", return_value="stop"), \
             patch("tools.research_epic_attack_concentration.attack_compatibility", return_value=context), \
             patch("tools.research_epic_attack_concentration.exact_attack_probability", return_value=0.05):
            balanced, _ = _outcome(path, AttackCandidate("p90", 0.90, 23.0, "balanced"), {})
            reference, _ = _outcome(path, AttackCandidate("p90", 0.90, 23.0, "reachable_reference"), {})
        self.assertEqual(balanced["stop_checkpoint"], 6)
        self.assertEqual(reference["stop_checkpoint"], 15)

    def test_old_or_wrong_shards_are_rejected_by_independent_schema_hash(self):
        gear = _gear()
        candidate = AttackCandidate("p90", 0.90, 23.0, "balanced")
        expected = _gear_hash(gear, "Epic", 20260712, 1, (candidate,), "external")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.json"
            path.write_text('{"status":"complete","study":"epic_concentration_rescue_v4_bound_health_20260720","schema_version":4}', encoding="utf-8")
            self.assertFalse(_valid_shard(path, expected, "Epic", 20260712, 0))
        self.assertEqual(STUDY, "epic_attack_concentration_exact_v1_20260721")
        self.assertEqual(SCHEMA_VERSION, 1)


if __name__ == "__main__":
    unittest.main()
