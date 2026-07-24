"""Regression coverage for the frozen Epic balanced prospective protocol."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "epic_balanced_prospective.py"
SPEC = importlib.util.spec_from_file_location("epic_balanced_prospective", TOOL_PATH)
assert SPEC and SPEC.loader
prospective = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = prospective
SPEC.loader.exec_module(prospective)


def _item(instance_id: str, *, enhance: int = 0, speed: int = 0, attack_pct: int = 8) -> dict:
    substats = [
        {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
        {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
        {"type": "AttackPercent", "value": attack_pct, "rolls": 1},
        {"type": "HealthPercent", "value": 6, "rolls": 1},
    ]
    if speed:
        substats[3] = {"type": "Speed", "value": speed, "rolls": 1}
    return {
        "id": instance_id, "ingameId": instance_id, "gear": "Weapon", "rank": "Epic",
        "set": "AttackSet", "level": 85, "enhance": enhance,
        "main": {"type": "Attack", "value": 500}, "substats": substats,
        "itemSource": "normal_85",
    }


class EpicBalancedProspectiveTest(unittest.TestCase):
    def test_new_batch_starts_blind_and_freezes_a_b_c_without_human_fields(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "batch.json"
            batch = prospective.create_batch(path, frozen_at="2026-07-13T12:00:00+08:00")
            self.assertEqual(batch["status"], "collecting_blind")
            self.assertEqual(batch["progress"], {"accepted": 0, "target": 48})
            self.assertEqual(set(batch["frozen"]["candidates"]), {"A_current_review", "B_global_current_gs", "C_category_probability"})
            self.assertIn("prediction_function_sha256", batch["frozen"])
            self.assertNotIn("human_review", json.dumps(batch, ensure_ascii=False))

    def test_import_requires_post_freeze_legal_non_speed_item_and_deduplicates_known_and_batch(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "batch.json"
            batch = prospective.create_batch(path, frozen_at="2026-07-13T12:00:00+08:00")
            known = prospective.identity_index([_item("old-item")])
            result = prospective.ingest_export(
                path, {"exported_at": "2026-07-13T12:01:00+08:00", "items": [_item("fresh", attack_pct=9), _item("old-item"), _item("speed", speed=2)]},
                known=known,
            )
            self.assertEqual(result["accepted"], 1)
            self.assertEqual(result["excluded_by_reason"]["known_instance_id"], 1)
            self.assertEqual(result["excluded_by_reason"]["speed_hard_route"], 1)
            locked = json.loads(path.read_text(encoding="utf-8"))
            row = locked["items"][0]
            self.assertEqual(set(row["predictions"]), {"A_current_review", "B_global_current_gs", "C_category_probability"})
            self.assertNotIn("human_review", row)
            duplicate = prospective.ingest_export(path, {"exported_at": "2026-07-13T12:02:00+08:00", "items": [_item("fresh", attack_pct=9)]}, known=known)
            self.assertEqual(duplicate["accepted"], 0)
            self.assertEqual(duplicate["excluded_by_reason"]["batch_instance_id"], 1)

    def test_speed_value_starts_at_22_and_is_never_below_second_tier_anchor(self):
        self.assertEqual(prospective.terminal_one_speed_value(21, 42), 0)
        self.assertEqual(prospective.terminal_one_speed_value(22, 42), 42)
        self.assertGreater(prospective.terminal_one_speed_value(25, 42), 42)
        self.assertGreater(prospective.terminal_one_speed_value(27, 42), prospective.terminal_one_speed_value(25, 42))

    def test_research_oracle_lock_does_not_require_or_expose_manual_labels(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "batch.json"
            prospective.create_batch(path, frozen_at="2026-07-13T12:00:00+08:00")
            result = prospective.lock_research_oracles(path, lambda_value=0.001, cost_per_terminal_value=1000)
            self.assertEqual(result, {"locked": 0, "status": "locked_research_only"})
            batch = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(batch["frozen"]["oracle"]["manual_labels_visible"])


if __name__ == "__main__":
    unittest.main()
