import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.e7_enhance.models import Gear, RollHit, Stat
from tools.research_heroic_midgame_speed22 import (
    CANDIDATES,
    COMBINED_HEROIC_KEYS,
    SCHEMA_VERSION,
    candidate_action,
    p22_exact,
    speed_oracle_action,
    speed_terminal_distribution,
    _valid,
    _candidate_event_summary,
    _marginal_per_added_22,
    _record_row,
    _new_row,
    _run_path,
    _terminal_with_category,
    candidate_action_equivalence_matrix,
    enumerate_legal_rescue_states,
    freeze_v7_allocation,
    stratified_plan_specs,
    speed_signature_strata,
    simulate_stratified_shard,
    run,
    validate_legal_rescue_witness_path,
)


def heroic_speed(*, enhance=6, speed=10, rolls=2, substats=3, slot="weapon", set_code="set_speed", last_hit=False):
    stats = [Stat("Speed", speed, rolls=rolls)]
    stats.extend(Stat(key, 4, rolls=1) for key in ("AttackPercent", "CriticalHitChancePercent", "HealthPercent")[:substats - 1])
    history = [RollHit(enhance, "Speed", 3)] if last_hit and enhance in {3, 6, 9, 15} else []
    return Gear(set_code, slot, Stat("Attack", 0), enhance=enhance, rank="Heroic", level=85, substats=stats, roll_history=history, reforge_eligible=True)


class HeroicMidgameSpeed22Test(unittest.TestCase):
    def test_candidates_are_midgame_only_and_do_not_reopen_h2_h3(self):
        for checkpoint in (0, 3):
            gear = heroic_speed(enhance=checkpoint)
            for candidate in CANDIDATES:
                self.assertEqual(candidate_action(candidate, gear, baseline_action="stop"), "stop")

    def test_only_normal_heroic_non_boot_existing_speed_can_be_rescued(self):
        base = heroic_speed(speed=18, rolls=3)
        self.assertEqual(candidate_action("M1_reachable_22", base, baseline_action="stop"), "continue")
        self.assertEqual(candidate_action("M1_reachable_22", heroic_speed(speed=18, rolls=3, slot="boot"), baseline_action="stop"), "stop")
        self.assertEqual(candidate_action("M1_reachable_22", heroic_speed(speed=18, rolls=3, set_code="set_att"), baseline_action="stop", item_source="rift_85"), "stop")

    def test_candidate_never_stops_baseline_continue(self):
        gear = heroic_speed(speed=1, rolls=1)
        for candidate in CANDIDATES:
            self.assertEqual(candidate_action(candidate, gear, baseline_action="continue"), "continue")
        self.assertEqual(speed_oracle_action(gear, baseline_action="continue"), "continue")

    def test_plus_twelve_adds_fourth_substat_not_speed_hit(self):
        gear = heroic_speed(enhance=12, speed=18, rolls=3, substats=3)
        distribution = speed_terminal_distribution(gear)
        # Only +15 can hit existing speed: 1/4.  Reforge has been applied once.
        self.assertAlmostEqual(p22_exact(gear), 0.25, places=8)
        self.assertEqual(sorted(distribution), [20, 22, 23, 24, 25])
        self.assertEqual(candidate_action("M4_speed_hit_chain", gear, baseline_action="stop"), "stop")

    def test_exact_probability_handles_impossible_and_certain_boundaries(self):
        self.assertEqual(p22_exact(heroic_speed(enhance=12, speed=12, rolls=1, substats=3)), 0.0)
        self.assertEqual(p22_exact(heroic_speed(enhance=12, speed=22, rolls=4, substats=4)), 1.0)

    def test_external_reference_is_speed_only_and_still_requires_reachability(self):
        self.assertEqual(candidate_action("M5_external_speed_reference", heroic_speed(speed=11, rolls=2), baseline_action="stop"), "continue")
        self.assertEqual(candidate_action("M5_external_speed_reference", heroic_speed(speed=4, rolls=2), baseline_action="stop"), "stop")

    def test_reachable_candidate_has_real_binary_rescues_at_each_authorized_node(self):
        states = {
            6: heroic_speed(enhance=6, speed=12, rolls=3),
            9: heroic_speed(enhance=9, speed=15, rolls=4),
            12: heroic_speed(enhance=12, speed=18, rolls=3, substats=3),
        }
        for checkpoint, gear in states.items():
            self.assertGreater(p22_exact(gear), 0.0, checkpoint)
            self.assertEqual(candidate_action("M0_current", gear, baseline_action="stop"), "stop")
            self.assertEqual(candidate_action("M1_reachable_22", gear, baseline_action="stop"), "continue")

    def test_new_resume_schema_rejects_old_threshold_study_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.json"
            path.write_text(json.dumps({"schema_version": 2, "study": "heroic_speed_threshold_100k"}), encoding="utf-8")
            self.assertFalse(_valid(path))

    def test_reachability_reference_is_not_named_as_speed_efficiency_oracle(self):
        summary = _candidate_event_summary(
            raw_events={"seed-1/a": 1, "seed-2/b": 1},
            weighted_rescued_22_per_100k=0.25,
            sample_weights=[0.5, 0.5],
        )
        self.assertEqual(summary["reference_name"], "reachability_rescue")
        self.assertNotIn("oracle", summary["reference_name"])
        self.assertEqual(summary["raw_unique_rescued_22_count"], 2)
        self.assertEqual(summary["weighted_rescued_22_per_100k"], 0.25)
        self.assertEqual(summary["weighted_ess"], 2.0)

    def test_weighted_event_ess_uses_importance_weights_not_raw_event_count(self):
        summary = _candidate_event_summary(
            raw_events={"a": 1, "b": 1},
            weighted_rescued_22_per_100k=0.25,
            sample_weights=[100.0, 1.0],
        )
        self.assertEqual(summary["raw_unique_rescued_22_count"], 2)
        self.assertLess(summary["weighted_ess"], 1.1)

    def test_marginal_cost_uses_source_ledger_not_fixed_100k_subtraction(self):
        m0 = {"saint_stamina": 60.0, "riftslash_stamina": 40.0, "cycles": 1.0, "strategy_gs": 10.0}
        candidate = {"saint_stamina": 75.0, "riftslash_stamina": 30.0, "cycles": 0.75, "strategy_gs": 8.0}
        change = _marginal_per_added_22(m0, candidate, added_heroic22=3.0)
        self.assertEqual(change["saint_stamina_per_added_heroic22"], 5.0)
        self.assertEqual(change["riftslash_stamina_lost_per_added_heroic22"], 10.0 / 3.0)
        self.assertEqual(change["source_cycles_lost_per_added_heroic22"], 1.0 / 12.0)
        self.assertEqual(change["strategy_gs_change_per_added_heroic22"], -2.0 / 3.0)
        self.assertNotIn("total_stamina", change)

    def test_legal_rescue_state_scan_finds_reachable_binary_difference(self):
        states = enumerate_legal_rescue_states()
        self.assertTrue(states)
        self.assertTrue(all(state["baseline_action"] == "stop" for state in states))
        self.assertTrue(all(state["p22"] > 0.0 for state in states))
        self.assertTrue(any("M1_reachable_22" in state["rescued_candidates"] for state in states))

    def test_legal_witness_is_built_from_zero_with_real_speed_history_and_fourth_substat(self):
        state = next(item for item in enumerate_legal_rescue_states() if item["node"] == 12)
        path = state["path"]
        self.assertEqual(sorted(path), [0, 3, 6, 9, 12, 15])
        self.assertEqual(len(path[0].substats), 3)
        self.assertEqual(len(path[9].substats), 3)
        self.assertEqual(len(path[12].substats), 4)
        self.assertEqual([hit.enhance for hit in path[12].roll_history], [3, 6, 9])
        self.assertEqual([hit.key for hit in path[12].roll_history[:3]], ["spd", "spd", "spd"])
        self.assertEqual([hit.value for hit in path[12].roll_history[:3]], [4, 4, 4])
        speed9 = next(stat for stat in path[9].substats if stat.key == "spd")
        speed12 = next(stat for stat in path[12].substats if stat.key == "spd")
        self.assertEqual((speed9.normalized_value, speed9.rolls), (14, 4))
        self.assertEqual((speed12.normalized_value, speed12.rolls), (14, 4))
        self.assertEqual(len({stat.key for stat in path[12].substats}), 4)

    def test_first_rescue_prevents_plus_twelve_from_being_marked_as_m0_natural_or_double_counted(self):
        state = next(item for item in enumerate_legal_rescue_states() if item["node"] == 12)
        path = state["path"]
        baseline_actions = {point: "continue" for point in (0, 3, 6)} | {9: "stop", 12: "stop", 15: "stop"}
        outcome = _run_path(path, "M1_reachable_22", "all_sets", False, baseline_actions)
        self.assertEqual(outcome["first_rescue_node"], 9)
        self.assertEqual(outcome["later_rescue_nodes"], [12])
        self.assertNotIn(12, outcome["baseline_naturally_reached"])
        self.assertIn(12, outcome["candidate_only_reached"])
        row = _new_row()
        terminal = _terminal_with_category(path[15])
        _record_row(row, path, outcome, terminal, baseline_actions, trajectory_id="legal-path")
        self.assertEqual(row["first_rescue_22"]["9"], 1)
        self.assertEqual(row["first_rescue_22"]["12"], 0)
        self.assertEqual(len(row["raw_rescued_22_events"]), 1)

    def test_legal_audit_rejects_three_substat_plus_twelve_witness(self):
        state = next(item for item in enumerate_legal_rescue_states() if item["node"] == 12)
        invalid_path = dict(state["path"])
        invalid_path[12] = replace(invalid_path[12], substats=invalid_path[9].substats)
        with self.assertRaisesRegex(ValueError, "four substats"):
            validate_legal_rescue_witness_path(invalid_path)

    def test_v7_speed_signatures_are_mutually_exclusive_and_preserve_all_natural_mass(self):
        signatures = speed_signature_strata(("set_speed", "set_cri", "set_att", "set_max_hp"))
        self.assertEqual(SCHEMA_VERSION, 7)
        self.assertGreater(len(signatures), 100)
        self.assertEqual(len({signature["signature_id"] for signature in signatures}), len(signatures))
        self.assertAlmostEqual(
            sum(signature["natural_probability"] for signature in signatures),
            signatures[0]["natural_speed_non_boot_probability"],
            places=12,
        )
        self.assertTrue(all("proposal_probability" not in signature for signature in signatures))

    def test_v7_action_matrix_derives_the_expected_complete_action_equivalence_groups(self):
        matrix = candidate_action_equivalence_matrix()
        groups = {frozenset(group["members"]) for group in matrix["groups"]}
        self.assertIn(frozenset((
            "M1_reachable_22", "M2_p22_0_5pct", "M2_p22_1pct", "M2_p22_2pct",
            "M2_p22_5pct", "M4_speed_hit_chain", "M5_external_speed_reference",
        )), groups)
        self.assertIn(frozenset(("M2_p22_10pct", "M3_p22_per_stamina_0_002")), groups)
        self.assertIn(frozenset(("M0_current", "M3_p22_per_stamina_0_005", "M3_p22_per_stamina_0_01")), groups)
        self.assertFalse(matrix["witnesses"])

    def test_v7_frozen_allocation_raises_22_plus_signature_draws_but_keeps_failure_cost_draws(self):
        signatures = speed_signature_strata(("set_speed", "set_cri", "set_att", "set_max_hp"))
        allocation = freeze_v7_allocation(signatures)
        positive = [item for item in allocation["strata"] if item["terminal_speed"] >= 22]
        failures = [item for item in allocation["strata"] if item["terminal_speed"] < 22 and item["draws"] > 0]
        self.assertEqual(len(positive), 21)
        self.assertTrue(all(item["draws"] >= allocation["positive_draws_per_signature"] for item in positive))
        self.assertTrue(failures)
        self.assertTrue(all(item["draws"] >= allocation["failure_draws_per_signature"] for item in failures))
        self.assertEqual(sum(item["draws"] for item in allocation["strata"]), allocation["targeted_runs"])

    def test_v6_signature_mass_respects_initial_value_model(self):
        legacy = speed_signature_strata(("set_speed",), initial_mode="legacy_initial_uniform")
        proxy = speed_signature_strata(("set_speed",), initial_mode="roll_distribution_as_initial_proxy")
        legacy_speed_two = sum(item["natural_probability"] for item in legacy if item["initial_speed"] == 2)
        proxy_speed_two = sum(item["natural_probability"] for item in proxy if item["initial_speed"] == 2)
        self.assertNotEqual(legacy_speed_two, proxy_speed_two)

    def test_v7_stratified_shard_applies_one_natural_weight_to_failure_cost_and_success_output(self):
        payload = simulate_stratified_shard(
            seed=901, common_runs=8, targeted_runs=None,
            initial_mode="legacy_initial_uniform", sets=("set_speed", "set_cri", "set_att", "set_max_hp"), rare=False,
        )
        self.assertEqual(payload["sampling_mode"], "mutually_exclusive_speed_signature_strata")
        self.assertEqual(payload["common_pool"]["runs"], 8)
        self.assertGreater(payload["targeted_pool"]["runs"], 2500)
        self.assertGreater(payload["epic"]["paths"], 0)
        self.assertGreater(payload["baseline_heroic"]["metrics"]["paths"], 0)
        self.assertEqual(sum(plan["raw_draws"] for plan in payload["strata"].values()), payload["targeted_pool"]["runs"])
        self.assertAlmostEqual(sum(plan["natural_probability"] for plan in payload["strata"].values()), payload["targeted_pool"]["natural_mass"], places=12)
        candidate_events = payload["heroic"]["M1_reachable_22/all_sets"]["raw_rescued_22_events"]
        self.assertTrue(candidate_events)
        for trajectory_id, evidence in candidate_events.items():
            self.assertEqual(trajectory_id, evidence["trajectory_id"])
            self.assertGreater(evidence["natural_weight"], 0.0)
            self.assertIn("speed_signature", evidence)
        # Some rescues fail to reach 22.  Their weighted resource/GS delta is
        # retained even though they contribute no rescued-22 event.
        failed = payload["strata"][next(key for key, item in payload["strata"].items() if item["rescued_failure_count"] > 0)]
        self.assertGreater(failed["weighted_delta_abs"], 0.0)

    def test_v7_resume_deduplicates_seed_shard_and_rejects_all_pre_v7_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            resume = Path(directory)
            arguments = dict(
                resume_dir=resume, seeds=[919], runs_per_seed=4, targeted_runs_per_seed=None,
                sets=("set_speed", "set_cri", "set_att", "set_max_hp"),
                initial_mode="legacy_initial_uniform", rare_speed_rolls_removed=False,
            )
            first = run(**arguments)
            second = run(**arguments)
            self.assertEqual(first["execution"]["scheduled_shards"], 1)
            self.assertEqual(second["execution"]["skipped_shards"], 1)
            candidates = first["summary"]["candidates"]
            m0 = candidates["M0_current/all_sets"]
            m1 = candidates["M1_reachable_22/all_sets"]
            self.assertAlmostEqual(
                m1["speed"][22] - m0["speed"][22],
                m1["weighted_rescued_22_per_100k"],
                places=10,
            )
            combined = first["summary"]["b_joint"]
            self.assertEqual(combined["epic_policy"], "B_global_current_gs")
            self.assertEqual(set(combined["candidates"]), set(COMBINED_HEROIC_KEYS))
            self.assertIn("curve_baseline", combined["candidates"]["M0_current/all_sets"]["unified_terminal_value_per_100_stamina"])
            shard = resume / "official" / "legacy_initial_uniform" / "seed-919.json"
            payload = json.loads(shard.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
            for version in (3, 4, 5, 6, 7):
                payload.update({"schema_version": version, "study": f"heroic_midgame_speed22_v{version}_stratified"})
                shard.write_text(json.dumps(payload), encoding="utf-8")
                self.assertFalse(_valid(shard))


if __name__ == "__main__":
    unittest.main()
