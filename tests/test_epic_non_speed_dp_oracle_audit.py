"""Regression tests for the offline Epic non-speed DP oracle audit."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "epic_non_speed_dp_oracle_audit.py"
SPEC = importlib.util.spec_from_file_location("epic_non_speed_dp_oracle_audit", TOOL_PATH)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class EpicNonSpeedDpOracleAuditTests(unittest.TestCase):
    def test_canonical_fingerprint_links_blind_snapshot_without_instance_id(self):
        blind = json.loads((ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json").read_text(encoding="utf-8"))
        records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))
        linked = audit.collect_audit_cases(
            old_source_path=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json",
            blind_source_path=ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json",
            records_payload=records,
        )
        blind_rows = [row for row in linked["included"] if row["cohort"] == "blind"]
        self.assertEqual(len(blind_rows), len(blind["items"]))
        self.assertTrue(all(row["link_method"] == "canonical_fingerprint" for row in blind_rows))
        self.assertEqual(len({row["instance_id"] for row in blind_rows}), len(blind_rows))

    def test_duplicate_canonical_fingerprint_is_reported_not_silently_selected(self):
        item = {
            "id": "one", "ingameId": "one", "gear": "Armor", "rank": "Epic", "set": "CriticalSet",
            "level": 85, "enhance": 0, "main": {"type": "Defense", "value": 300},
            "substats": [
                {"type": "HealthPercent", "value": 8, "rolls": 1},
                {"type": "DefensePercent", "value": 7, "rolls": 1},
                {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                {"type": "Health", "value": 161, "rolls": 1},
            ],
        }
        source = {"items": [item, {**item, "id": "two", "ingameId": "two"}]}
        records = {"records": []}
        linked = audit.link_source_items(source, records, cohort="blind", source_name="synthetic.json")
        self.assertEqual(linked["included"], [])
        self.assertEqual(linked["excluded"][0]["reason"], "source_fingerprint_not_unique")

    def test_out_of_scope_records_are_not_counted_as_target_exclusions(self):
        records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))
        linked = audit.collect_audit_cases(
            old_source_path=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json",
            blind_source_path=ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json",
            records_payload=records,
        )
        self.assertEqual(len(linked["included"]) + len(linked["excluded"]), 46)
        self.assertTrue(linked["outside_scope"])

    def test_candidate_comparison_uses_binary_resource_action_and_oracle_margin(self):
        rows = [{
            "oracle": {"action": "stop", "utility_margin": -2.5, "forced_continue_stamina": 3.0,
                       "expected_terminal_value": 1.0, "expected_formal_baili_score": 0.0},
            "current_action": "cautious_continue",
            "candidate_actions": {"B_global_current_gs": "stop", "C_category_probability": "continue"},
            "human_action": "stop",
        }]
        result = audit.compare_actions(rows, "C_category_probability")
        self.assertEqual(result["binary_action_accuracy"], 0.0)
        self.assertEqual(result["false_enhance_count"], 1)
        self.assertAlmostEqual(result["total_utility_regret"], 2.5)
        self.assertAlmostEqual(result["wasted_incremental_stamina"], 3.0)

    def test_speed_hard_route_is_excluded_with_reason(self):
        records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))
        linked = audit.collect_audit_cases(
            old_source_path=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json",
            blind_source_path=ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json",
            records_payload=records,
        )
        self.assertTrue(any(row["reason"] == "speed_hard_route" for row in linked["excluded"]))

    def test_audit_worker_accepts_linked_gear_object(self):
        records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))
        linked = audit.collect_audit_cases(
            old_source_path=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json",
            blind_source_path=ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json",
            records_payload=records,
        )
        self.assertIsInstance(linked["included"][0]["gear"], audit.Gear)

    def test_old_holdout_prefers_saved_instance_id_over_fingerprint(self):
        records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))
        linked = audit.collect_audit_cases(
            old_source_path=ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json",
            blind_source_path=ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json",
            records_payload=records,
        )
        old_rows = [row for row in linked["included"] if row["cohort"] == "old_holdout"]
        self.assertTrue(old_rows)
        self.assertTrue(all(row["link_method"] == "instance_id" for row in old_rows))


if __name__ == "__main__":
    unittest.main()
