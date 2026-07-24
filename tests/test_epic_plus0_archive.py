from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.e7_enhance import epic_plus0_archive as archive


def _item(instance_id: str, *, slot: str = "Weapon", speed: int = 0, enhance: int = 0, rank: str = "Epic", source: str = "normal_85") -> dict:
    return {
        "id": instance_id,
        "ingameId": instance_id,
        "gear": slot,
        "rank": rank,
        "set": "AttackSet",
        "level": 85,
        "enhance": enhance,
        "main": {"type": "Attack", "value": 500},
        "substats": [
            {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
            {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
            {"type": "AttackPercent", "value": 8, "rolls": 1},
            {"type": "Speed", "value": speed, "rolls": 1},
        ],
        "itemSource": source,
    }


class EpicPlus0ArchiveTest(unittest.TestCase):
    def _payload(self, items: list[dict]) -> dict:
        return {
            "source_kind": "full_fribbels_export",
            "source_file_sha256": "export-hash",
            "exported_at": "2026-07-19T12:01:00+08:00",
            "items": items,
        }

    def test_archive_keeps_boots_and_speed_route_with_holdout_flag(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "archive.json"
            result = archive.ingest_export(
                path,
                self._payload([_item("normal"), _item("boot", slot="Boots"), _item("speed", speed=2)]),
                known={"instance_ids": set(), "fingerprints": set()},
                minimum_exported_at="2026-07-18T12:00:00+08:00",
            )
            self.assertEqual(result["accepted"], 3)
            data = json.loads(path.read_text(encoding="utf-8"))
            flags = {row["instance_id"]: row["flags"] for row in data["items"]}
            self.assertTrue(flags["normal"]["holdout_candidate"])
            self.assertTrue(flags["boot"]["boots"])
            self.assertTrue(flags["speed"]["speed_hard_route"])
            self.assertNotIn("action", json.dumps(data))
            self.assertNotIn("efficiency", json.dumps(data))

    def test_archive_excludes_old_scope_and_deduplicates(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "archive.json"
            payload = self._payload([_item("fresh"), _item("old", enhance=3), _item("heroic", rank="Heroic")])
            first = archive.ingest_export(path, payload, known={"instance_ids": {"known"}, "fingerprints": set()}, minimum_exported_at="2026-07-18T12:00:00+08:00")
            second = archive.ingest_export(path, payload, known={"instance_ids": set(), "fingerprints": set()}, minimum_exported_at="2026-07-18T12:00:00+08:00")
            self.assertEqual(first["accepted"], 1)
            self.assertEqual(second["accepted"], 0)
            self.assertEqual(archive.progress(path)["accepted"], 1)

    def test_archive_rejects_pre_freeze_export(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "archive.json"
            payload = self._payload([_item("old-export")])
            payload["exported_at"] = "2026-07-18T11:59:00+08:00"
            with self.assertRaisesRegex(ValueError, "archive boundary"):
                archive.ingest_export(path, payload, known={"instance_ids": set(), "fingerprints": set()}, minimum_exported_at="2026-07-18T12:00:00+08:00")


if __name__ == "__main__":
    unittest.main()
