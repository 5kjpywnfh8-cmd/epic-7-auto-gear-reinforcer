import hashlib
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.ocr_capture import capture_from_bytes, capture_from_file
from src.e7_enhance.ocr_normalize import compare_shadow_advice, normalize_ocr_payload, project_shadow_gear
from src.e7_enhance.ocr_regions import equipment_regions, validate_regions


def token(text, confidence=0.995, candidates=None):
    return {"text": text, "confidence": confidence, "candidates": candidates or [text]}


def valid_payload():
    return {
        "set": token("速度"), "slot": token("Weapon"), "rank": token("传说"),
        "enhance": token("+0"), "level": token("85"),
        "mainStat": {"type": token("攻击力"), "value": token("525")},
        "substats": [
            {"type": token("Attack %"), "value": token(" 8 ％ "), "rolls": token("1")},
            {"type": token("暴率"), "value": token("5%"), "rolls": token("1")},
            {"type": token("速度"), "value": token("4"), "rolls": token("1")},
            {"type": token("效果命中"), "value": token("7%"), "rolls": token("1")},
        ],
        "itemSource": "normal_85", "gearSource": "normal_85", "instanceId": "synthetic-1",
    }


class OcrStageOneReadOnlyTest(unittest.TestCase):
    def test_capture_hash_and_file_import_are_read_only(self):
        payload = b"synthetic-screenshot-fixture"
        capture = capture_from_bytes(payload)
        self.assertEqual(capture["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertFalse(capture["click_performed"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.png"
            path.write_bytes(payload)
            self.assertEqual(capture_from_file(path)["sha256"], capture["sha256"])

    def test_default_regions_are_normalized_and_have_no_click_coordinates(self):
        regions = equipment_regions()
        self.assertEqual(regions["validation_errors"], [])
        self.assertIsNone(regions["click_coordinates"])
        self.assertEqual(validate_regions([{"name": "bad", "bounds": {"left": -0.1, "top": 0, "right": 1, "bottom": 1}}]), ["out_of_bounds_region:bad"])

    def test_normalizes_chinese_english_aliases_and_numeric_noise(self):
        result = normalize_ocr_payload(valid_payload(), capture_from_bytes(b"fixture"), equipment_regions())
        self.assertTrue(result["accepted"], result["rejection_reasons"])
        self.assertEqual(result["gear"]["set"], "set_speed")
        self.assertEqual(result["gear"]["slot"], "weapon")
        self.assertEqual(result["gear"]["rank"], "Epic")
        self.assertEqual(result["gear"]["substats"][0]["type"], "AttackPercent")
        self.assertEqual(result["gear"]["substats"][0]["value"], 8.0)
        self.assertTrue(result["advice_hash"])
        self.assertFalse(result["click_performed"])

    def test_unknown_or_low_confidence_fields_fail_closed(self):
        unknown = valid_payload()
        unknown["set"] = token("未知套装")
        result = normalize_ocr_payload(unknown, capture_from_bytes(b"unknown"))
        self.assertFalse(result["accepted"])
        self.assertIn("unrecognized:set", result["rejection_reasons"])
        self.assertIsNone(result["gear"])

        low_confidence = valid_payload()
        low_confidence["substats"][0]["value"] = token("8%", confidence=0.7)
        result = normalize_ocr_payload(low_confidence, capture_from_bytes(b"low"))
        self.assertFalse(result["accepted"])
        self.assertIn("low_confidence:substats[0].value", result["rejection_reasons"])

    def test_schema_preserves_raw_candidates_confidence_and_advice_comparison(self):
        result = normalize_ocr_payload(valid_payload(), capture_from_bytes(b"schema"), equipment_regions())
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["fields"]["set"]["raw_text"], "速度")
        self.assertEqual(result["fields"]["set"]["candidates"], ["速度"])
        self.assertGreaterEqual(result["fields"]["set"]["confidence"], 0.98)
        comparison = compare_shadow_advice(result, result["gear"])
        self.assertTrue(comparison["comparable"])
        self.assertTrue(comparison["matched"])

    def test_adapter_fields_accept_normalized_zero_and_preserve_raw_text(self):
        payload = valid_payload()
        payload["enhance"] = {
            "text": "exp0/525",
            "raw_text": "exp0/525",
            "normalized": 0,
            "confidence": 0.995,
        }
        result = normalize_ocr_payload(payload, capture_from_bytes(b"normalized-zero"))
        self.assertTrue(result["accepted"], result["rejection_reasons"])
        self.assertEqual(result["gear"]["enhance"], 0)
        self.assertEqual(result["fields"]["enhance"]["raw_text"], "exp0/525")

    def test_rejected_output_never_computes_shadow_advice(self):
        payload = valid_payload()
        payload["slot"] = token("unknown-slot")
        result = normalize_ocr_payload(payload, capture_from_bytes(b"reject"))
        comparison = compare_shadow_advice(result, valid_payload())
        self.assertFalse(comparison["comparable"])
        self.assertEqual(comparison["reason"], "ocr_result_rejected")

    def test_plus0_shadow_projection_uses_reference_representation(self):
        payload = valid_payload()
        result = normalize_ocr_payload(payload, capture_from_bytes(b"projection"))
        reference = {**result["gear"], "mainStat": {"type": "Attack", "value": 525}}
        projected = project_shadow_gear(result["gear"], reference)
        self.assertEqual(projected["mainStat"]["value"], 525)
        self.assertEqual(projected["enhance"], 0)

        payload["mainStat"]["value"] = token("100")
        shadow = normalize_ocr_payload(
            payload,
            capture_from_bytes(b"projected-advice"),
            reference_gear=reference,
        )
        comparison = compare_shadow_advice(shadow, reference)
        self.assertTrue(shadow["accepted"], shadow["rejection_reasons"])
        self.assertEqual(shadow["ocr_gear"]["mainStat"]["value"], 100)
        self.assertEqual(shadow["gear"]["mainStat"]["value"], 525)
        self.assertTrue(comparison["matched"])


if __name__ == "__main__":
    unittest.main()
