import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "pair_ocr_stage1_batch.py"
SPEC = importlib.util.spec_from_file_location("pair_ocr_stage1_batch", MODULE_PATH)
PAIR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PAIR)


class PairOcrStageOneBatchTest(unittest.TestCase):
    def test_manual_fields_keep_effect_resistance_distinct_from_effectiveness(self):
        first = PAIR.GROUPS["gear-001"]["fields"]
        ring = PAIR.GROUPS["gear-005"]["fields"]
        self.assertEqual(first["substats"][2]["type"], "EffectResistancePercent")
        self.assertEqual(ring["main"]["type"], "EffectResistancePercent")
        self.assertEqual(ring["substats"][1]["type"], "EffectivenessPercent")
        self.assertEqual(PAIR.GROUPS["gear-007"]["fields"]["substats"][1]["type"], "EffectResistancePercent")
        self.assertEqual(PAIR.GROUPS["gear-006"]["fields"]["substats"][2]["type"], "EffectivenessPercent")
        self.assertEqual(PAIR.GROUPS["gear-008"]["fields"]["substats"][0]["type"], "EffectivenessPercent")

    def test_exact_match_uses_fribbels_gear_against_manual_slot(self):
        fields = PAIR.GROUPS["gear-004"]["fields"]
        matching = {"set": "HealthSet", "gear": "Helmet", "rank": "Epic", "level": 90, "enhance": 15, "main": {"type": "Health", "value": 2835}, "substats": fields["substats"]}
        self.assertEqual(PAIR.exact_matches([matching], fields), [matching])
        self.assertEqual(PAIR.exact_matches([{**matching, "gear": "Armor"}], fields), [])


if __name__ == "__main__":
    unittest.main()
