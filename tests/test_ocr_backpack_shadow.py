from __future__ import annotations

import json
import unittest

from src.e7_enhance.ocr_backpack_shadow import canonical_reference


class OcrBackpackShadowTest(unittest.TestCase):
    def test_canonical_reference_maps_player_gear_to_formal_schema(self):
        reference = canonical_reference({
            "ingameId": "sample-1", "set": "SpeedSet", "gear": "Ring", "rank": "Epic",
            "level": 85, "enhance": 0,
            "main": {"type": "HealthPercent", "value": 60},
            "substats": [{"type": "AttackPercent", "value": 6, "rolls": 1}],
        })
        self.assertEqual(reference["set"], "set_speed")
        self.assertEqual(reference["slot"], "ring")
        self.assertEqual(reference["mainStat"]["value"], 60)
        self.assertEqual(reference["instanceId"], "sample-1")


if __name__ == "__main__":
    unittest.main()
