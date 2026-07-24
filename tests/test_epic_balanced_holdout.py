from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.e7_enhance import epic_balanced_holdout as holdout
from tools import collect_epic_balanced_holdout as collector


def _item(instance_id: str, *, speed: int = 0, slot: str = "Weapon", enhance: int = 0, attack_pct: int = 8) -> dict:
    return {
        "id": instance_id,
        "ingameId": instance_id,
        "gear": slot,
        "rank": "Epic",
        "set": "AttackSet",
        "level": 85,
        "enhance": enhance,
        "main": {"type": "Attack", "value": 500},
        "substats": [
            {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
            {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
            {"type": "AttackPercent", "value": attack_pct, "rolls": 1},
            {"type": "Speed", "value": speed, "rolls": 1},
        ],
        "itemSource": "normal_85",
    }


class EpicBalancedHoldoutTest(unittest.TestCase):
    @staticmethod
    def _export(items: list[dict]) -> dict:
        return {"source_kind": "full_fribbels_export", "source_file_sha256": "test-export", "exported_at": "2026-07-18T12:01:00+08:00", "items": items}

    def test_cli_rejects_native_json_instead_of_upgrading_it(self):
        with self.assertRaisesRegex(ValueError, "complete Fribbels"):
            collector._prepare_payload(json.dumps({"items": [_item("native")]}, ensure_ascii=False).encode("utf-8"))

    def test_cli_normalizes_real_fribbels_export_time_to_shanghai_iso(self):
        payload = {"export_time": "2026-07-19 12:34:56", "item_count": 1, "heroes": [], "items": [{"gear": "Weapon", "main": {}, "raw": {}}]}
        prepared = collector._prepare_payload(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(prepared["source_kind"], "full_fribbels_export")
        self.assertEqual(prepared["exported_at"], "2026-07-19T12:34:56+08:00")
        self.assertRegex(prepared["source_file_sha256"], r"^[0-9a-f]{64}$")

    def test_cli_rejects_invalid_fribbels_export_time(self):
        payload = {"export_time": "bad", "item_count": 1, "heroes": [], "items": [{"gear": "Weapon", "main": {}, "raw": {}}]}
        with self.assertRaisesRegex(ValueError, "export_time"):
            collector._prepare_payload(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    @staticmethod
    def _player_snapshot(items: list[dict], *, imported_at: str = "2026-07-18T16:54:44+08:00", item_count: int | None = None) -> dict:
        return {
            "metadata": {"source": "fribbels_mumu_reader", "imported_at": imported_at, "item_count": len(items) if item_count is None else item_count},
            "items": items,
            "equipment": list(items),
        }

    def test_cli_accepts_complete_trusted_player_snapshot_and_defaults_normal_source(self):
        item = _item("snapshot")
        item["raw"] = {"id": 1}
        prepared = collector._prepare_payload(json.dumps(self._player_snapshot([item]), ensure_ascii=False).encode("utf-8"))
        self.assertEqual(prepared["source_container"], "fribbels_mumu_player_snapshot")
        self.assertEqual(prepared["exported_at"], "2026-07-18T16:54:44+08:00")
        self.assertEqual(prepared["items"][0]["itemSource"], "normal_85")

    def test_cli_rejects_untrusted_or_incomplete_player_snapshot(self):
        item = _item("snapshot")
        item["raw"] = {"id": 1}
        cases = (
            self._player_snapshot([item], imported_at="2026-07-18T16:54:44"),
            self._player_snapshot([item], item_count=2),
            self._player_snapshot([{key: value for key, value in item.items() if key != "raw"}]),
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    collector._prepare_payload(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def test_freeze_is_write_once_and_contains_selected_candidate_and_gates(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "freeze.json"
            frozen = holdout.freeze_candidate(path, frozen_at="2026-07-18T12:00:00+08:00")
            again = holdout.freeze_candidate(path, frozen_at="2026-07-19T12:00:00+08:00")
            self.assertEqual(frozen, again)
            self.assertEqual(frozen["candidate"]["key"], "output_8_13_tank_10_17")
            self.assertEqual(frozen["candidate"]["thresholds"], {"default": {"plus0": 12, "plus3": 17}, "pure_output": {"plus0": 8, "plus3": 13}, "pure_tank": {"plus0": 10, "plus3": 17}})
            self.assertEqual(frozen["holdout_protocol"]["target"], 128)
            self.assertIn("plus3_official_probability", frozen["frozen_hashes"])

    def test_collecting_blind_deduplicates_and_hides_oracle_actions_and_efficiency(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze = holdout.freeze_candidate(root / "freeze.json", frozen_at="2026-07-18T12:00:00+08:00")
            dataset = holdout.create_collection(root / "collection.json", freeze)
            result = holdout.ingest_export(
                root / "collection.json",
                self._export([_item("fresh", attack_pct=9), _item("old"), _item("shoe", slot="Boots"), _item("speed", speed=2)]),
                freeze=freeze,
                known={"instance_ids": {"old"}, "fingerprints": set()},
            )
            self.assertEqual(result["accepted"], 1)
            self.assertEqual(result["excluded_by_reason"]["known_instance_id"], 1)
            self.assertEqual(result["excluded_by_reason"]["boots"], 1)
            self.assertEqual(result["excluded_by_reason"]["speed_hard_route"], 1)
            progress = holdout.progress(root / "collection.json")
            self.assertEqual(progress["accepted"], 1)
            self.assertNotIn("oracle", json.dumps(progress))
            self.assertNotIn("action", json.dumps(progress))
            self.assertNotIn("efficiency", json.dumps(progress))
            with self.assertRaisesRegex(ValueError, "128"):
                holdout.validation_manifest(root / "collection.json", root / "manifest.json")

    def test_64_items_remain_collecting_blind_and_cannot_read_validation_inputs(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze = holdout.freeze_candidate(root / "freeze.json", frozen_at="2026-07-18T12:00:00+08:00")
            holdout.create_collection(root / "collection.json", freeze)
            items = [_item(f"item-{index}", attack_pct=index + 10) for index in range(64)]
            holdout.ingest_export(root / "collection.json", self._export(items), freeze=freeze, known={"instance_ids": set(), "fingerprints": set()})
            self.assertEqual(holdout.progress(root / "collection.json")["status"], "collecting_blind")
            self.assertFalse((root / "manifest.json").exists())
            with self.assertRaisesRegex(ValueError, "collecting_blind"):
                holdout.validation_inputs(root / "collection.json", root / "manifest.json")

    def test_128_items_atomically_freeze_64_64_manifest_without_reusing_old_manifest(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            freeze = holdout.freeze_candidate(root / "freeze.json", frozen_at="2026-07-18T12:00:00+08:00")
            holdout.create_collection(root / "collection.json", freeze)
            items = [_item(f"item-{index}", attack_pct=index + 10) for index in range(128)]
            result = holdout.ingest_export(root / "collection.json", self._export(items), freeze=freeze, known={"instance_ids": set(), "fingerprints": set()})
            self.assertEqual(result["status"], "ready_for_frozen_validation")
            manifest_path = root / "manifest.json"
            manifest = holdout.validation_manifest(root / "collection.json", manifest_path)
            groups = [row["group"] for row in manifest["included"]]
            self.assertEqual(groups.count("development"), 64)
            self.assertEqual(groups.count("frozen_validation"), 64)
            self.assertEqual(manifest["source_collection_id"], holdout.COLLECTION_ID)
            self.assertEqual(holdout.validation_manifest(root / "collection.json", manifest_path), manifest)


if __name__ == "__main__":
    unittest.main()
