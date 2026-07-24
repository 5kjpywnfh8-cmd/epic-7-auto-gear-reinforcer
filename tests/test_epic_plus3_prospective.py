from __future__ import annotations

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.e7_enhance.enhance_policy import advise_gear
from src.e7_enhance.epic_plus3_prospective import (
    FREEZE_TARGET_COUNT,
    SAMPLE_SOURCE,
    _atomic_json,
    _new_dataset,
    freeze_manifest,
    load_dataset,
    progress,
    record_observation,
)
from src.e7_enhance.models import Gear


class EpicPlus3ProspectiveTest(unittest.TestCase):
    def _gear(self, *, instance_id: str = "runtime-1", enhance: int = 0, speed: int = 1, slot: str = "Weapon") -> dict:
        substats = [
            {"type": "HealthPercent", "value": 8, "rolls": 1},
            {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
            {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
            {"type": "Speed", "value": speed, "rolls": 1},
        ]
        if enhance == 3:
            substats[1] = {"type": "CriticalHitChancePercent", "value": 9, "rolls": 2}
        return {
            "set": "Speed", "slot": slot, "mainStat": {"type": "Attack", "value": 500},
            "enhance": enhance, "level": 85, "rank": "Epic", "substats": substats,
            "rollHistory": ([] if not enhance else [{"enhance": 3, "type": "CriticalHitChancePercent", "value": 4}]),
            "instanceId": instance_id, "reforgeEligible": True,
            "itemSource": "normal_85", "gearSource": "riftslash_20_buff",
        }

    def _event(self, gear: dict, **extra: object) -> dict:
        return {
            "gear": gear, "observed_at": "2026-07-14T12:00:00+08:00",
            "sample_source": SAMPLE_SOURCE, **extra,
        }

    def test_plus0_and_plus3_pair_and_preserve_hit_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collector.json"
            plus0 = self._gear()
            first = record_observation(path, self._event(plus0, observed_formal_recommendation="cautious_continue"))
            second = record_observation(path, self._event(self._gear(enhance=3), before_next_strategy_judgement=True))
            data = load_dataset(path)

            self.assertEqual(first["status"], "pending_plus0")
            self.assertEqual(second["status"], "paired")
            pair = data["observations"]["pairs"][0]
            self.assertEqual(pair["plus3_hit"]["stat_key"], "crit")
            self.assertEqual(pair["plus3_hit"]["value_delta"], 4)
            self.assertTrue(pair["collected_blind"])
            self.assertEqual(pair["sample_source"], SAMPLE_SOURCE)

    def test_scope_filter_rejects_boots_and_speed_hard_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collector.json"
            boots = self._gear(slot="Boots")
            fast = self._gear(instance_id="runtime-2", speed=2)
            self.assertEqual(record_observation(path, self._event(boots, observed_formal_recommendation="cautious_continue"))["reason"], "boots_excluded")
            self.assertEqual(record_observation(path, self._event(fast, observed_formal_recommendation="cautious_continue"))["reason"], "initial_speed_hard_route")

    def test_dual_dedup_and_atomic_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collector.json"
            event = self._event(self._gear(), observed_formal_recommendation="cautious_continue")
            self.assertEqual(record_observation(path, event)["status"], "pending_plus0")
            self.assertEqual(record_observation(path, event)["status"], "duplicate")
            self.assertEqual(load_dataset(path)["observations"]["plus0_pending"][0]["instance_id"], "runtime-1")
            self.assertEqual(record_observation(path, self._event(self._gear(enhance=3), before_next_strategy_judgement=True))["status"], "paired")
            self.assertEqual(progress(load_dataset(path))["valid_plus0_plus3_pair_count"], 1)

    def test_old_samples_are_excluded_from_prospective_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collector.json"
            result = record_observation(path, {"gear": self._gear(), "observed_at": "2026-07-14T12:00:00+08:00", "sample_source": "manual_import", "observed_formal_recommendation": "cautious_continue"})
            self.assertEqual(result["reason"], "not_prospective_runtime")
            self.assertFalse(load_dataset(path)["observations"]["pairs"])

    def test_manifest_hash_split_is_fixed_at_64_each(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dataset_path, manifest_path = directory / "collector.json", directory / "manifest.json"
            data = _new_dataset("2026-07-14T12:00:00+08:00")
            data["observations"]["pairs"] = [
                {"sample_id": f"sample-{index:03d}", "policy_rule_sha256": data["policy_rule_sha256"], "plus0": {"fingerprint": f"p0-{index}"}, "plus3": {"fingerprint": f"p3-{index}"}}
                for index in range(FREEZE_TARGET_COUNT)
            ]
            _atomic_json(dataset_path, data)
            first = freeze_manifest(dataset_path, manifest_path)
            second = freeze_manifest(dataset_path, manifest_path)
            self.assertEqual(first, second)
            self.assertEqual(len(first["included"]), FREEZE_TARGET_COUNT)
            self.assertEqual(sum(row["group"] == "development" for row in first["included"]), 64)
            self.assertEqual(sum(row["group"] == "frozen_validation" for row in first["included"]), 64)

    def test_64_to_127_pairs_stay_collecting_blind_and_cannot_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dataset_path, manifest_path = directory / "collector.json", directory / "manifest.json"
            data = _new_dataset("2026-07-14T12:00:00+08:00")
            data["observations"]["pairs"] = [
                {"sample_id": f"sample-{index:03d}", "policy_rule_sha256": data["policy_rule_sha256"], "plus0": {"fingerprint": f"p0-{index}"}, "plus3": {"fingerprint": f"p3-{index}"}}
                for index in range(64)
            ]
            _atomic_json(dataset_path, data)
            self.assertEqual(progress(load_dataset(dataset_path))["status"], "collecting_blind")
            with self.assertRaisesRegex(ValueError, "need 128"):
                freeze_manifest(dataset_path, manifest_path)

    def test_manifest_excludes_overflow_and_only_development_reader_is_available(self):
        from src.e7_enhance.epic_plus3_prospective import development_pairs_from_manifest, frozen_validation_pairs_from_manifest

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dataset_path, manifest_path = directory / "collector.json", directory / "manifest.json"
            data = _new_dataset("2026-07-14T12:00:00+08:00")
            data["observations"]["pairs"] = [
                {"sample_id": f"sample-{index:03d}", "policy_rule_sha256": data["policy_rule_sha256"], "plus0": {"fingerprint": f"p0-{index}"}, "plus3": {"fingerprint": f"p3-{index}"}}
                for index in range(FREEZE_TARGET_COUNT + 3)
            ]
            _atomic_json(dataset_path, data)
            self.assertEqual(progress(load_dataset(dataset_path))["status"], "ready_to_freeze_manifest")
            manifest = freeze_manifest(dataset_path, manifest_path)
            development = development_pairs_from_manifest(dataset_path, manifest_path)
            self.assertEqual(len(development), 64)
            self.assertEqual(len(manifest["not_included_pairs"]), 3)
            self.assertTrue(all(row["sample_id"] in {item["sample_id"] for item in manifest["included"]} for row in development))
            with self.assertRaisesRegex(ValueError, "candidate and prediction hashes"):
                frozen_validation_pairs_from_manifest(dataset_path, manifest_path)

    def test_passive_collector_does_not_change_formal_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = self._gear()
            before = advise_gear(Gear.from_dict(raw), item_source="normal_85", gear_source=raw["gearSource"])["summary"]["recommendation"]
            record_observation(Path(tmp) / "collector.json", self._event(raw, observed_formal_recommendation="cautious_continue"))
            after = advise_gear(Gear.from_dict(raw), item_source="normal_85", gear_source=raw["gearSource"])["summary"]["recommendation"]
            self.assertEqual(before, after)

    def test_plus0_never_requires_or_records_a_fabricated_actual_enhancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collector.json"
            result = record_observation(path, self._event(self._gear(), observed_formal_recommendation="cautious_continue"))
            pending = load_dataset(path)["observations"]["plus0_pending"][0]
            self.assertEqual(result["status"], "pending_plus0")
            self.assertNotIn("actual_enhancement", pending)

    def test_trusted_fribbels_adapter_is_passive_and_pairs_after_real_plus3(self):
        from src.e7_enhance.epic_plus3_prospective import observe_trusted_fribbels_state

        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "collector.json"
            suggestion = {"summary": {"recommendation": "cautious_continue", "next_check_at": 3}, "debug": {"dp_assist": {"decision_mode": "lightweight_prediction"}}}
            first = observe_trusted_fribbels_state(self._gear(), suggestion, dataset_path=dataset)
            second = observe_trusted_fribbels_state(self._gear(enhance=3), suggestion, dataset_path=dataset)
            self.assertEqual(first["status"], "pending_plus0")
            self.assertEqual(second["status"], "paired")

    def test_adapter_write_failure_does_not_change_suggestion_or_raise(self):
        from src.e7_enhance.epic_plus3_prospective import observe_trusted_fribbels_state

        suggestion = {"summary": {"recommendation": "cautious_continue", "next_check_at": 3}, "debug": {"dp_assist": {"decision_mode": "lightweight_prediction"}}}
        original = json.loads(json.dumps(suggestion))
        with patch("src.e7_enhance.epic_plus3_prospective.record_observation", side_effect=OSError("disk unavailable")):
            result = observe_trusted_fribbels_state(self._gear(), suggestion, dataset_path=Path("unused.json"))
        self.assertEqual(result["status"], "observation_error")
        self.assertEqual(suggestion, original)


if __name__ == "__main__":
    unittest.main()
