from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.e7_enhance.mumu_player_data import (
    archive_payload,
    derive_enhance,
    enriched_items,
    validate_player_data,
    validate_same_batch_raw,
)
from tools import pair_ocr_stage1_batch_002 as pair

def item(identity="one", enhance=12, set_name="set_riposte"):
    return {"ingameId": identity, "set": set_name, "gear": "Armor", "rank": "Epic", "level": 85, "enhance": enhance, "main": {"type": "Defense", "value": 234}, "substats": [{"type": "Speed", "value": 12}, {"type": "DefensePercent", "value": 11}]}

def player(items):
    return {"schema": "epic7_tools.player_data", "schema_version": "1.2", "source": {"reader": "mumu"}, "counts": {"items": len(items)}, "completeness": {"items": True}, "captured_at": "2026-07-22T00:00:00+00:00", "items": items}

def reader(items):
    return {
        "data": {
            "items": [
                {
                    **row,
                    "raw": {"op": ["event"] * (5 + int(row.get("enhance", 0)) // 3)},
                }
                for row in items
            ]
        }
    }

FIELDS = {"set": "RiposteSet", "slot": "Armor", "rank": "Epic", "level": 85, "enhance": 13, "main": {"type": "Defense", "value": 234}, "substats": [{"type": "Speed", "value": 12}, {"type": "DefensePercent", "value": 11}]}

class MumuPlayerDataTest(unittest.TestCase):
    def test_derives_epic_and_heroic_enhance_nodes_from_op_events(self):
        for rank, initial_events in (("Epic", 5), ("Heroic", 4)):
            for enhance in (0, 3, 6, 9, 12, 15):
                raw = {"op": ["event"] * (initial_events + enhance // 3)}
                self.assertEqual(derive_enhance(rank, raw), enhance)

    def test_enriches_all_zero_snapshot_from_nonzero_raw_without_mutation(self):
        data = player([item(enhance=0)])
        raw = reader([item(enhance=12)])
        enriched = enriched_items(data, raw)
        self.assertEqual(enriched[0]["enhance"], 12)
        self.assertEqual(data["items"][0]["enhance"], 0)

    def test_rejects_schema_counts_ids_and_raw_evidence_mismatch(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            validate_player_data({})
        bad_count = player([item()]); bad_count["counts"]["items"] = 2
        with self.assertRaisesRegex(ValueError, "counts"):
            validate_player_data(bad_count)
        duplicate = player([item(), item()])
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_player_data(duplicate)
        with self.assertRaisesRegex(ValueError, "identities"):
            validate_same_batch_raw([item()], reader([item("other")]))

    def test_archive_rejects_all_zero_or_raw_enhancement_mismatch(self):
        zero = player([item(enhance=0)])
        with self.assertRaisesRegex(ValueError, "untrustworthy"):
            archive_payload(b"snapshot", zero, reader(zero["items"]))
        data = player([item()]); raw = reader([item(enhance=9)])
        with self.assertRaisesRegex(ValueError, "enhancement state"):
            archive_payload(b"snapshot", data, raw)

    def test_pairing_allows_plus13_to_plus12_and_preserves_three_states(self):
        record = {"screenshot_id": "ocr-0006", "visible_fields": FIELDS}
        self.assertEqual(pair.pair_record(record, [item()])["match_status"], "matched")
        self.assertEqual(pair.pair_record(record, [item(), item("two")])["match_status"], "ambiguous")
        self.assertEqual(pair.pair_record(record, [item(enhance=0)])["match_status"], "unmatched")
        changed = item(); changed["main"] = {"type": "Defense", "value": 235}
        self.assertEqual(pair.pair_record(record, [changed])["match_status"], "unmatched")

    def test_archive_uses_export_time_or_source_timestamp_without_mutating_input(self):
        data = player([item()]); data["export_time"] = "2026-07-22T08:00:00+08:00"
        result = archive_payload(b"snapshot", data, reader(data["items"]))
        self.assertEqual(result["exported_at"], "2026-07-22T08:00:00+08:00")
        self.assertEqual(result["items"][0]["itemSource"], "normal_85")
        self.assertNotIn("itemSource", data["items"][0])
        data.pop("export_time"); data["source"]["imported_at"] = "2026-07-22T00:00:00Z"
        self.assertEqual(archive_payload(b"snapshot", data, reader(data["items"]))["exported_at"], "2026-07-22T00:00:00+00:00")
        data["source"]["imported_at"] = "2026-07-22T00:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            archive_payload(b"snapshot", data, reader(data["items"]))

    def test_pairing_rejects_one_of_four_substats_and_cli_keeps_manifest_hash(self):
        four = item()
        four["substats"] += [{"type": "HealthPercent", "value": 7}, {"type": "EffectResistancePercent", "value": 8}]
        fields = {**FIELDS, "substats": list(four["substats"])}
        changed = {**four, "substats": [*four["substats"]]}
        changed["substats"][3] = {"type": "EffectResistancePercent", "value": 9}
        self.assertEqual(pair.pair_record({"screenshot_id": "ocr-0006", "visible_fields": fields}, [changed])["match_status"], "unmatched")
        manifest = {"schema_version": 1, "records": [{"screenshot_id": "ocr-0006", "sha256": "unchanged", "visible_fields": fields}]}
        with TemporaryDirectory() as temporary:
            root = Path(temporary); manifest_path = root / "manifest.json"; player_path = root / "player.json"; reader_path = root / "reader.json"; output_path = root / "output.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            input_data = player([four]); input_data["export_time"] = "2026-07-22T00:00:00+00:00"
            player_path.write_text(json.dumps(input_data), encoding="utf-8")
            reader_path.write_text(json.dumps(reader(input_data["items"])), encoding="utf-8")
            self.assertEqual(pair.main(["--manifest", str(manifest_path), "--player-data", str(player_path), "--reader-result", str(reader_path), "--output", str(output_path)]), 0)
            output = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(output["records"][0]["sha256"], "unchanged")
        self.assertEqual(output["records"][0]["match_status"], "matched")
        self.assertEqual(output["reference"]["raw_item_count"], 1)

if __name__ == "__main__":
    unittest.main()
