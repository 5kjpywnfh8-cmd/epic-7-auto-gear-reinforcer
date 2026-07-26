from __future__ import annotations

import unittest

from src.e7_enhance.ocr_regions import set_crop_candidates
from src.e7_enhance.set_crop_comparison import compare_set_crop_candidates
from src.e7_enhance.visual_adapter import VisualFrame


class SetCropComparisonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = VisualFrame.from_bytes(
            source="offline-fixture",
            payload=b"synthetic-set-crop-frame",
            viewport=(1280, 720),
            captured_at="2026-07-27T10:00:00+08:00",
        )

    def _extractor(self, calls: list[str]):
        def extract(frame, region):
            self.assertIs(frame, self.frame)
            calls.append(region.name)
            return region.name.encode("ascii")
        return extract

    def test_fixed_candidates_are_auditable_and_compared_from_one_frame(self):
        calls: list[str] = []

        def icon(_, sample):
            return [{"candidate_id": "SpeedSet", "score": 0.999}] if sample.region.name == "set_icon_tight_red" else [{"candidate_id": "SpeedSet", "score": 0.5}]

        def text(_, sample):
            return [{"normalized": "SpeedSet", "confidence": 0.999}] if sample.region.name == "set_text_compact_red" else [{"normalized": "SpeedSet", "confidence": 0.5}]

        result = compare_set_crop_candidates(
            self.frame,
            region_extractor=self._extractor(calls),
            icon_recognizer=icon,
            text_recognizer=text,
        )

        self.assertTrue(result["accepted"], result["rejection_reasons"])
        self.assertEqual(result["mode"], "visual_only")
        self.assertEqual(result["verification"], "unverified")
        self.assertFalse(result["click_performed"])
        self.assertEqual(calls, [candidate["name"] for candidate in set_crop_candidates()])
        self.assertEqual(result["selection"]["icon"]["candidate"], "set_icon_tight_red")
        self.assertEqual(result["selection"]["text"]["candidate"], "set_text_compact_red")
        self.assertEqual(result["set"], {"value": "SpeedSet", "confidence": 0.999})
        bounds = {row["name"]: row["pixel_bounds"] for row in result["candidates"]}
        self.assertEqual(bounds["set_icon_wide_red"], {"left": 870, "top": 536, "right": 930, "bottom": 600})
        self.assertEqual(bounds["set_icon_tight_red"], {"left": 875, "top": 540, "right": 925, "bottom": 596})
        self.assertEqual(bounds["set_text_wide_red"], {"left": 916, "top": 540, "right": 1120, "bottom": 600})
        self.assertEqual(bounds["set_text_compact_red"], {"left": 916, "top": 544, "right": 1034, "bottom": 592})

    def test_out_of_bounds_candidate_rejects_before_extracting_any_crop(self):
        candidates = set_crop_candidates()
        candidates[0]["bounds"]["left"] = -0.01
        calls: list[str] = []

        result = compare_set_crop_candidates(
            self.frame,
            region_extractor=self._extractor(calls),
            icon_recognizer=lambda *_: [],
            text_recognizer=lambda *_: [],
            candidates=candidates,
        )

        self.assertFalse(result["accepted"])
        self.assertIn("invalid_candidate:set_icon_wide_red", result["rejection_reasons"])
        self.assertEqual(calls, [])
        self.assertEqual(len(result["candidates"]), 4)
        self.assertEqual(result["candidates"][0]["pixel_bounds"]["left"], -13)
        self.assertEqual(result["candidates"][0]["rejection_reasons"], ["invalid_candidate_bounds"])

    def test_duplicate_best_crop_and_low_confidence_text_both_fail_closed(self):
        def icon(_, sample):
            return [{"candidate_id": "SpeedSet", "score": 0.999}]

        duplicate = compare_set_crop_candidates(
            self.frame,
            region_extractor=self._extractor([]),
            icon_recognizer=icon,
            text_recognizer=lambda *_: [{"normalized": "SpeedSet", "confidence": 0.999}],
        )
        self.assertFalse(duplicate["accepted"])
        self.assertIn("non_unique_crop:icon", duplicate["rejection_reasons"])

        low_confidence = compare_set_crop_candidates(
            self.frame,
            region_extractor=self._extractor([]),
            icon_recognizer=icon,
            text_recognizer=lambda *_: [{"normalized": "SpeedSet", "confidence": 0.979}],
        )
        self.assertFalse(low_confidence["accepted"])
        self.assertIn("missing_crop:text", low_confidence["rejection_reasons"])
        self.assertIn("incomplete_set_evidence", low_confidence["rejection_reasons"])

    def test_channel_value_conflict_rejects_without_inference(self):
        result = compare_set_crop_candidates(
            self.frame,
            region_extractor=self._extractor([]),
            icon_recognizer=lambda _, sample: [{"candidate_id": "SpeedSet", "score": 0.999}] if sample.region.name == "set_icon_tight_red" else [{"candidate_id": "SpeedSet", "score": 0.5}],
            text_recognizer=lambda _, sample: [{"normalized": "InjurySet", "confidence": 0.999}] if sample.region.name == "set_text_compact_red" else [{"normalized": "InjurySet", "confidence": 0.5}],
        )

        self.assertFalse(result["accepted"])
        self.assertIn("conflicting:set", result["rejection_reasons"])
        self.assertIsNone(result["set"])


if __name__ == "__main__":
    unittest.main()
