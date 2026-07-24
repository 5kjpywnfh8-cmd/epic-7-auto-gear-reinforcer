import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from src.e7_enhance.models import Gear, Stat
from tools.research_epic_concentration_rescue_exact import (
    CANDIDATE_KEY,
    SCHEMA_VERSION,
    STUDY,
    _empty_stats,
    _fmt,
    _health_state,
    _next_states,
    _merge_seed,
    _outcome,
    _gear_hash,
    _valid_shard,
    exact_health_distribution,
    exact_health_probability,
    attack_compatibility_from_snapshot,
)
from tools.abc_terminal_metrics import _empty_flow

from tools.research_epic_concentration_rescue_exact import (
    health_compatibility_from_snapshot,
    health_compatibility,
)


def _gear(*, rank="Epic", enhance=12, health=25, health_rolls=3, health_flat=None, substats=4):
    rows = [
        Stat("HealthPercent", health, rolls=health_rolls),
        *([Stat("Health", health_flat, rolls=1)] if health_flat is not None else []),
        Stat("AttackPercent", 30, rolls=1),
        Stat("CriticalHitChancePercent", 5, rolls=1),
        Stat("EffectivenessPercent", 5, rolls=1),
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


def _candidate_snapshot(category, set_group, source_row, *, qualified=True):
    return {"category": category, "candidate": {"category": category, "qualified": qualified, "rejection_reasons": [], "set_group": set_group, "source_row": source_row}}


class ExactConcentrationStudyTests(unittest.TestCase):
    def test_health_compatibility_fails_closed_for_output_dual_and_unknown(self):
        for category in ("输出", "输出(必爆)", "双效", "一速", "unknown", "未登记"):
            snapshot = _candidate_snapshot(category, "pureTank", "R23-R28")
            result = health_compatibility_from_snapshot(snapshot)
            self.assertFalse(result["compatible"], category)

    def test_health_compatibility_uses_selected_valid_keys_and_hpflat_contract(self):
        pure_tank = health_compatibility_from_snapshot(_candidate_snapshot("半肉(血防)", "bruiserHpDef", "R41-R46"))
        flat_bruiser = health_compatibility_from_snapshot(_candidate_snapshot("半肉(白字)", "bruiserFlat", "R53-R58"))
        self.assertTrue(pure_tank["compatible"])
        self.assertIn("hpPct", pure_tank["health_valid_keys"])
        self.assertNotIn("hpFlat", pure_tank["health_valid_keys"])
        self.assertTrue(flat_bruiser["compatible"])
        self.assertIn("hpFlat", flat_bruiser["health_valid_keys"])

    def test_health_compatibility_recomputes_for_current_node_snapshot(self):
        state = _gear(enhance=6)
        snapshots = iter((
            _candidate_snapshot("输出", "output", "R5-R10"),
            _candidate_snapshot("纯肉", "pureTank", "R23-R28"),
        ))
        with patch("tools.research_epic_concentration_rescue_exact.phase_b.selected_candidate_snapshot", side_effect=lambda _state: next(snapshots)):
            self.assertFalse(health_compatibility(state)["compatible"])
        self.assertTrue(health_compatibility(state)["compatible"])

    def test_category_rule_source_row_and_valid_group_must_match(self):
        mismatch = _candidate_snapshot("半肉(血防)", "bruiser", "R41-R46")
        wrong_source = _candidate_snapshot("半肉(血防)", "bruiserHpDef", "R47-R52")
        self.assertFalse(health_compatibility_from_snapshot(mismatch)["compatible"])
        self.assertFalse(health_compatibility_from_snapshot(wrong_source)["compatible"])
        attack = attack_compatibility_from_snapshot(_candidate_snapshot("输出", "output", "R5-R10"))
        self.assertTrue(attack["compatible"])
        self.assertEqual(attack["valid_group"], "output")

    def test_node_compatibility_is_checked_before_probability(self):
        state = _gear(enhance=6)
        calls = []
        with patch("tools.research_epic_concentration_rescue_exact._baseline_action", side_effect=lambda _state: "stop"), \
             patch("tools.research_epic_concentration_rescue_exact.health_compatibility", side_effect=lambda _state: calls.append("compatibility") or {"compatible": True, "category": "纯肉", "health_valid_keys": ["hpPct"], "cache_key": ["纯肉", "R23-R28", "pureTank", "pureTank", ["hpPct", "hpFlat", "defPct", "defFlat", "spd"], ["hpPct"], True]}), \
             patch("tools.research_epic_concentration_rescue_exact.exact_health_probability", side_effect=lambda *_args, **_kwargs: calls.append("probability") or 1.0):
            outcome, info = _outcome({6: state, 9: state, 12: state, 15: state}, 37.7363, {}, True)
        self.assertEqual(calls[:2], ["compatibility", "probability"])
        self.assertEqual(outcome["stop_checkpoint"], 15)
        self.assertEqual(info["first_rescue_node"], 6)

    def test_incompatible_node_cannot_rescue_even_with_probability_one(self):
        state = _gear(enhance=6)
        with patch("tools.research_epic_concentration_rescue_exact._baseline_action", return_value="stop"), \
             patch("tools.research_epic_concentration_rescue_exact.health_compatibility", return_value={"compatible": False, "category": "输出", "health_valid_keys": [], "cache_key": ["输出", "R5-R10", "output", "output", [], [], False]}), \
             patch("tools.research_epic_concentration_rescue_exact.exact_health_probability", return_value=1.0):
            outcome, info = _outcome({6: state}, 37.7363, {}, True)
        self.assertEqual(outcome["stop_checkpoint"], 6)
        self.assertEqual(info["rescues"], [])

    def test_probability_between_zero_and_ten_percent_does_not_rescue(self):
        state = _gear(enhance=6)
        path = {6: state, 9: state, 12: state, 15: state}
        with patch("tools.research_epic_concentration_rescue_exact._baseline_action", return_value="stop"), \
             patch("tools.research_epic_concentration_rescue_exact.health_compatibility", return_value={"compatible": True, "category": "纯肉", "health_valid_keys": ["hpPct"], "cache_key": ["纯肉", "R23-R28", "pureTank", "pureTank", ["hpPct", "hpFlat", "defPct", "defFlat", "spd"], ["hpPct"], True]}), \
             patch("tools.research_epic_concentration_rescue_exact.exact_health_probability", return_value=0.05):
            outcome, info = _outcome(path, 37.7363, {}, True)
        self.assertEqual(outcome["stop_checkpoint"], 6)
        self.assertEqual(info["rescues"], [])

    def test_joint_seed_merge_conserves_one_hundred_thousand_stamina(self):
        empty_flow = _empty_flow()
        empty_stats = _empty_stats()
        empty_stats["paths"] = 1.0
        aggregate = {
            "paths": 1.0,
            "flows": {"current_formal": dict(empty_flow), CANDIDATE_KEY: dict(empty_flow)},
            "stats": {"current_formal": dict(empty_stats), CANDIDATE_KEY: dict(empty_stats)},
        }
        with patch(
            "tools.research_epic_concentration_rescue_exact.joint_source_batch_metadata",
            return_value={
                "expected_output_by_rank": {"Heroic": 1.0},
                "expected_source_gold_per_batch": 0.0,
                "expected_lower_stone_units": 0.0,
            },
        ), patch(
            "tools.research_epic_concentration_rescue_exact.explicit_batch_resource_pool",
            return_value={"total_stamina": 100.0, "saint_supplement_stamina": 15.0},
        ):
            result = _merge_seed(20260712, aggregate, aggregate)
        for row in result.values():
            self.assertAlmostEqual(row["rift_stamina_per_100k"] + row["saint_stamina_per_100k"], 100000.0)

    def test_nonnegative_format_clamps_only_display_lower_bound(self):
        metric = {"mean": 0.5, "interval95": [-0.25, 1.25]}
        self.assertEqual(_fmt(metric, 2, nonnegative=True), "0.50 [0.00, 1.25]")

    def test_probability_mass_is_exact_and_distinguishes_zero_to_ten_percent(self):
        gear = _gear(health=25, health_rolls=3)
        distribution = exact_health_distribution(gear)
        self.assertAlmostEqual(sum(probability for _value, probability in distribution), 1.0, places=12)
        exact = sum(probability for value, probability in distribution if value >= 37.7363)
        self.assertAlmostEqual(exact_health_probability(gear, 37.7363), exact, places=12)
        self.assertGreater(exact, 0.0)
        self.assertLess(exact, 0.10)

    def test_invalid_hpflat_cannot_make_bruiser_health_target(self):
        gear = _gear(enhance=15, health=0.0, health_rolls=0, health_flat=100.0)
        cache = {}
        all_keys = exact_health_probability(gear, 1.0, cache, health_valid_keys=("hpPct", "hpFlat"), context_key=("all",))
        pct_only = exact_health_probability(gear, 1.0, cache, health_valid_keys=("hpPct",), context_key=("pct",))
        self.assertEqual(all_keys, 1.0)
        self.assertEqual(pct_only, 0.0)
        self.assertEqual(len(cache), 2)

    def test_invalid_hpflat_remains_a_heroic_hit_slot(self):
        gear = _gear(rank="Heroic", enhance=9, health=25.0, health_rolls=3, health_flat=None, substats=3)
        state = _health_state(gear, ("hpPct",))
        branches = _next_states(state)
        flat_branches = [branch for branch in branches if "hpFlat" in branch[0].all_keys]
        self.assertTrue(flat_branches)
        for next_state, _probability in flat_branches:
            self.assertNotIn("hpFlat", next_state.health_entries)

    def test_heroic_plus12_adds_fourth_substat_before_plus15(self):
        gear = _gear(rank="Heroic", substats=3)
        distribution = exact_health_distribution(gear)
        self.assertAlmostEqual(sum(probability for _value, probability in distribution), 1.0, places=12)
        self.assertGreater(len(distribution), 1)

    def test_plus15_has_no_future_hit_and_reforge_is_applied_once(self):
        gear = _gear(enhance=15, health=25, health_rolls=3)
        distribution = exact_health_distribution(gear)
        self.assertEqual(len(distribution), 1)
        value, probability = distribution[0]
        self.assertEqual(probability, 1.0)
        self.assertGreater(value, 25 * 0.8)

    def test_new_schema_and_resume_hash_reject_old_or_wrong_shard(self):
        gear = _gear()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shard.json"
            path.write_text('{"status":"complete","schema_version":1}', encoding="utf-8")
            self.assertFalse(_valid_shard(path, _gear_hash(gear, "Epic", 20260712, 10, 37.7363), "Epic", 20260712, 0))
        self.assertEqual(SCHEMA_VERSION, 4)
        self.assertEqual(STUDY, "epic_concentration_rescue_v4_bound_health_20260720")
        self.assertEqual(CANDIDATE_KEY, "health_p975_balanced")


if __name__ == "__main__":
    unittest.main()
