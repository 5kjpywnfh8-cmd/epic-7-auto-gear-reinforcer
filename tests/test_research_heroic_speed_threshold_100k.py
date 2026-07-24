from __future__ import annotations

import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from src.e7_enhance.models import Gear, RollHit, Stat
from tools.research_heroic_speed_threshold_100k import (
    CANDIDATES,
    aggregate_four_sets,
    candidate_action,
    full_pool_coverage,
    per_100k_ledger,
    run,
    terminal_bucket,
    _run_path,
    _released_action,
    action_equivalence_gate,
    terminal_formal_gs,
)


def heroic(speed: int | None, *, set_code: str = "set_speed", slot: str = "weapon", enhance: int = 0, hit_speed: bool = False) -> Gear:
    keys = [Stat("AttackPercent", 4), Stat("CriticalHitChancePercent", 3)]
    if speed is not None:
        keys.append(Stat("Speed", speed))
    else:
        keys.append(Stat("HealthPercent", 4))
    history = [RollHit(3, "Speed", 2)] if hit_speed else []
    return Gear(set_code, slot, Stat("Attack", 0), enhance=enhance, rank="Heroic", level=85, substats=keys, roll_history=history, reforge_eligible=True)


class HeroicSpeedThreshold100kTest(unittest.TestCase):
    def test_label_only_difference_closes_gate_without_rare_event_schedule(self):
        matrix = [
            {"state_id": "speed2", "candidate": "H4_current", "label": "cautious_continue", "binary_actions": ["enhance", "enhance", "stop"]},
            {"state_id": "speed2", "candidate": "H2_all_sets", "label": "continue", "binary_actions": ["enhance", "enhance", "stop"]},
        ]
        gate = action_equivalence_gate(matrix)
        self.assertEqual(gate["status"], "no_binary_action_difference_under_current_policy")
        self.assertFalse(gate["schedule_rare_event_expansion"])

    def test_reachable_conversion_can_improve_native_formal_without_strategy_cost(self):
        gear = Gear(
            "set_speed", "weapon", Stat("Attack", 0), enhance=15, rank="Epic", level=90,
            substats=[Stat("Speed", 20, rolls=4), Stat("AttackPercent", 15, rolls=2), Stat("CriticalHitChancePercent", 10, rolls=1), Stat("EffectivenessPercent", 4, rolls=2)],
            reforge_eligible=True,
        )
        values = terminal_formal_gs(gear)
        self.assertGreater(values["conversion_reachable_formal_gs"], values["native_formal_gs"])
        self.assertEqual(values["strategy_conversion_gold"], 0.0)
    def test_h4_matches_released_route_at_every_checkpoint(self):
        path = {point: heroic(2, enhance=point) for point in (0, 3, 6, 9, 12, 15)}
        with patch("tools.research_heroic_speed_threshold_100k._released_action", return_value="continue"):
            self.assertEqual(_run_path(path, "H4_current"), _run_path(path, "__released__"))

    def test_epic_released_route_does_not_disable_published_dp(self):
        epic = replace(heroic(2, enhance=6), rank="Epic")
        with patch("tools.research_heroic_speed_threshold_100k.advise_gear", return_value={"summary": {"recommendation": "stop"}}) as advice:
            self.assertEqual(_released_action(epic), "stop")
        self.assertNotIn("enable_dp_assist", advice.call_args.kwargs)

    def test_heroic_uses_base_fallback_at_plus_six_not_cautious_to_fifteen(self):
        path = {point: heroic(4, enhance=point) for point in (0, 3, 6, 9, 12, 15)}
        with patch("tools.research_heroic_speed_threshold_100k.advise_gear", return_value={"summary": {"recommendation": "cautious_continue"}}), patch(
            "tools.research_heroic_speed_threshold_100k._heroic_base_fallback", return_value=False
        ):
            outcome = _run_path(path, "__released__")
        self.assertEqual(outcome["stop_checkpoint"], 6)
        self.assertEqual(outcome["actions"][6], "stop")

    def test_lowered_candidates_only_override_authorized_heroic_initial_two_or_three_speed(self):
        self.assertEqual(candidate_action("H2_all_sets", heroic(1)), "released")
        self.assertEqual(candidate_action("H2_all_sets", heroic(4)), "released")
        self.assertEqual(candidate_action("H2_all_sets", heroic(2)), "continue")
        self.assertEqual(candidate_action("H3_all_sets", heroic(2)), "released")
        self.assertEqual(candidate_action("H3_all_sets", heroic(3)), "continue")
    def test_h4_current_has_no_research_override(self):
        self.assertEqual(candidate_action("H4_current", heroic(2)), "released")
        self.assertEqual(candidate_action("H4_current", heroic(3)), "released")
        self.assertEqual(candidate_action("H4_current", heroic(4)), "released")

    def test_speed_and_confirmed_two_piece_sets_are_the_only_main_lowered_sets(self):
        self.assertEqual(candidate_action("H2_speed_2pc", heroic(2, set_code="set_speed")), "continue")
        self.assertEqual(candidate_action("H2_speed_2pc", heroic(2, set_code="set_cri")), "continue")
        self.assertEqual(candidate_action("H2_speed_2pc", heroic(2, set_code="set_att")), "released")
        self.assertEqual(candidate_action("H3_speed_2pc", heroic(2)), "released")
        self.assertEqual(candidate_action("H3_speed_2pc", heroic(3)), "continue")

    def test_all_sets_and_debuff_sensitivity_are_explicitly_separate(self):
        self.assertEqual(candidate_action("H2_all_sets", heroic(2, set_code="set_att")), "continue")
        self.assertEqual(candidate_action("H3_all_sets", heroic(2, set_code="set_att")), "released")
        self.assertEqual(candidate_action("H2_speed_2pc", heroic(2, set_code="set_debuff")), "released")
        self.assertEqual(candidate_action("H2_speed_2pc_debuff_sensitivity", heroic(2, set_code="set_debuff")), "continue")

    def test_epic_boot_and_no_speed_are_never_changed_by_heroic_candidate(self):
        epic = replace(heroic(2), rank="Epic")
        self.assertEqual(candidate_action("H2_all_sets", epic), "released")
        self.assertEqual(candidate_action("H2_all_sets", heroic(2, slot="boot")), "released")
        self.assertEqual(candidate_action("H2_all_sets", heroic(None)), "released")

    def test_plus_three_always_releases_to_the_same_formal_route(self):
        self.assertEqual(candidate_action("H2_all_sets", heroic(2, enhance=3, hit_speed=True)), "released")
        self.assertEqual(candidate_action("H2_all_sets", heroic(2, enhance=3)), "released")
        self.assertEqual(candidate_action("H2_all_sets", heroic(2, enhance=6)), "released")

    def test_full_pool_has_both_ranks_boots_and_no_speed(self):
        coverage = full_pool_coverage("set_speed", count=400, seed=7, initial_mode="legacy_initial_uniform")
        self.assertGreater(coverage["Epic"], 0)
        self.assertGreater(coverage["Heroic"], 0)
        self.assertGreater(coverage["boots"], 0)
        self.assertGreater(coverage["without_speed"], 0)

    def test_one_batch_resources_and_100k_ledger_conserve_total_stamina(self):
        ledger = per_100k_ledger({"saint_supplement_stamina": 15.0})
        self.assertAlmostEqual(ledger["riftslash_stamina"] + ledger["saint_stamina"], 100000.0)
        self.assertEqual(ledger["source_gold_batches"], ledger["cycles"])
        self.assertEqual(ledger["source_lower_stone_batches"], ledger["cycles"])

    def test_four_set_aggregate_is_arithmetic_mean(self):
        rows = [{"metric": value} for value in (1.0, 2.0, 3.0, 4.0)]
        self.assertEqual(aggregate_four_sets(rows)["metric"], 2.5)

    def test_terminal_bucket_selects_once_and_conversion_is_not_extra_piece(self):
        native = terminal_bucket({"formal": True, "formal_value": 70, "conversion": True, "converted_formal_value": 80})
        converted = terminal_bucket({"formal": False, "formal_value": 0, "conversion": True, "converted_formal_value": 80})
        self.assertEqual(native["formal_piece_count"], 1)
        self.assertEqual(native["total_baili"], 70)
        self.assertEqual(converted["formal_piece_count"], 1)
        self.assertEqual(converted["total_baili"], 80)

    def test_fixed_seed_resume_does_not_add_shards(self):
        with tempfile.TemporaryDirectory() as directory:
            resume = Path(directory) / "resume"
            first = run("set_speed", resume, [101], runs_per_seed=8, initial_mode="legacy_initial_uniform")
            second = run("set_speed", resume, [101], runs_per_seed=8, initial_mode="legacy_initial_uniform")
        self.assertGreater(first["execution"]["scheduled_shards"], 0)
        self.assertEqual(second["execution"]["scheduled_shards"], 0)
        self.assertEqual(second["execution"]["skipped_shards"], first["execution"]["scheduled_shards"])


if __name__ == "__main__":
    unittest.main()
