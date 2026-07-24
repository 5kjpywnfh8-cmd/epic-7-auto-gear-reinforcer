from __future__ import annotations

import unittest

from src.e7_enhance.ocr_backpack_pair import exact_matches, pair_manifest


FIELDS = {
    "set": "ShieldSet",
    "slot": "Boots",
    "rank": "Rare",
    "level": 85,
    "enhance": 0,
    "main": {"type": "Health", "value": 540},
    "main_value_mode": "raw_main_stat_base_for_plus0",
    "substats": [
        {"type": "EffectivenessPercent", "value": 6},
        {"type": "HealthPercent", "value": 5},
    ],
}


def item(identity: str = "4183341691") -> dict:
    return {
        "ingameId": identity,
        "set": "set_shield",
        "gear": "Boots",
        "rank": "Rare",
        "level": 85,
        "enhance": 0,
        "main": {"type": "Health", "value": 2700},
        "substats": [
            {"type": "EffectivenessPercent", "value": 6},
            {"type": "HealthPercent", "value": 5},
        ],
    }


def player(items: list[dict]) -> dict:
    return {
        "schema": "epic7_tools.player_data",
        "schema_version": "1.2",
        "source": {"reader": "mumu"},
        "counts": {"items": len(items)},
        "completeness": {"items": True},
        "items": items,
    }


def reader(items: list[dict]) -> dict:
    return {
        "data": {
            "items": [
                {
                    **row,
                    "raw": {
                        "op": [["max_hp", 540], ["acc", 0.06], ["max_hp_rate", 0.05]] + [["roll", 0]] * (int(row.get("enhance", 0)) // 3),
                        "mainStatBaseValue": 540,
                        "mainStatValue": 2700,
                    },
                }
                for row in items
            ]
        }
    }


class OcrBackpackPairTest(unittest.TestCase):
    def test_injury_set_display_name_matches_canonical_set_code(self):
        row = item()
        row["set"] = "set_scar"
        fields = {**FIELDS, "set": "InjurySet"}
        raw = reader([row])["data"]["items"][0]["raw"]
        self.assertEqual(exact_matches([row], {row["ingameId"]: raw}, fields), [row])

    def test_injury_set_matches_through_formal_aliases_and_unknown_set_rejects(self):
        row = item()
        row["set"] = "set_scar"
        fields = {**FIELDS, "set": "InjurySet"}
        raw = reader([row])["data"]["items"][0]["raw"]
        self.assertEqual(exact_matches([row], {row["ingameId"]: raw}, fields), [row])
        self.assertEqual(exact_matches([row], {row["ingameId"]: raw}, {**fields, "set": "UnknownSet"}), [])

    def test_matches_plus0_visible_main_against_raw_base_value(self):
        row = item()
        self.assertEqual([candidate["ingameId"] for candidate in exact_matches([row], {row["ingameId"]: reader([row])["data"]["items"][0]["raw"]}, FIELDS)], ["4183341691"])

    def test_rejects_substat_or_raw_main_mismatch(self):
        row = item()
        raw = reader([row])["data"]["items"][0]["raw"]
        changed = {**row, "substats": [*row["substats"]]}
        changed["substats"][1] = {"type": "HealthPercent", "value": 6}
        self.assertEqual(exact_matches([changed], {row["ingameId"]: raw}, FIELDS), [])
        self.assertEqual(exact_matches([row], {row["ingameId"]: {**raw, "mainStatBaseValue": 541}}, FIELDS), [])

    def test_converts_fractional_percent_raw_main_to_visible_percent(self):
        row = item()
        fields = {**FIELDS, "main": {"type": "HealthPercent", "value": 12}}
        row["main"] = {"type": "HealthPercent", "value": 60}
        raw = {"mainStatBaseValue": 0.12}
        self.assertEqual(exact_matches([row], {row["ingameId"]: raw}, fields)[0]["ingameId"], "4183341691")

    def test_pair_manifest_preserves_read_only_gate_and_unique_identity(self):
        row = item()
        background = item("background")
        background["enhance"] = 15
        manifest = {"records": [{"screenshot_id": "backpack-0001", "visible_fields": FIELDS}]}
        output = pair_manifest(
            manifest,
            player([row, background]),
            reader([row, background]),
            player_data_path="player.json",
            reader_result_path="reader.json",
            player_data_bytes=b"player",
            reader_result_bytes=b"reader",
        )
        self.assertEqual(output["records"][0]["instanceId"], "4183341691")
        self.assertFalse(output["records"][0]["click_performed"])
        self.assertEqual(output["pairing_gate"]["status"], "passed_for_read_only_shadow")
        self.assertEqual(output["advice_gate"], {"status": "unsupported_rank", "matched_ranks": ["Rare"]})


if __name__ == "__main__":
    unittest.main()
