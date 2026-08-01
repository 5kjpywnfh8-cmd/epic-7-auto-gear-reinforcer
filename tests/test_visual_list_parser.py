from __future__ import annotations

import copy
import unittest

from src.e7_enhance.visual_list_parser import EquipmentListVisualParser
from src.e7_enhance.visual_navigation import NavigationEvidenceGate
from src.e7_enhance.visual_runtime import MODE, VERIFICATION


TARGET = {
    "slot": "Weapon",
    "rank": "Epic",
    "level": 85,
    "enhance": 3,
    "set": "HealthSet",
    "main": {"type": "Attack", "value": 100},
    "substats": (
        ("AttackPercent", 13),
        ("CriticalHitChancePercent", 3),
        ("Speed", 2),
        ("EffectResistancePercent", 8),
    ),
    "gear_score": 37,
}


def sha(character: str) -> str:
    return character * 64


def card(candidate_id="candidate-001", fingerprint="c", **field_overrides):
    fields = {**TARGET, **field_overrides}
    return {
        "candidate_id": candidate_id,
        "visual_fingerprint": sha(fingerprint),
        "bounds": {"left": 0.10, "top": 0.25, "right": 0.40, "bottom": 0.55},
        "field_observations": [
            {"name": name, "value": value, "confidence": 0.99} for name, value in fields.items()
        ],
    }


def observation(**overrides):
    value = {
        "operation_id": "offline-fixture-operation",
        "captured_at": "2026-07-29T10:00:00+08:00",
        "page_signature": sha("a"),
        "viewport": (1280, 720),
        "stability": {"sample_count": 3, "stable_count": 3, "frame_hashes": [sha("b")] * 3},
        "anchors": [
            {"name": "list_header", "score": 0.99, "threshold": 0.98},
            {"name": "sort_button", "score": 0.99, "threshold": 0.98},
        ],
        "regions": [
            {
                "name": "list_header_region",
                "bounds": {"left": 0.05, "top": 0.05, "right": 0.95, "bottom": 0.20},
                "score": 0.99,
                "threshold": 0.98,
            },
            {
                "name": "candidate_list_region",
                "bounds": {"left": 0.05, "top": 0.20, "right": 0.95, "bottom": 0.95},
                "score": 0.99,
                "threshold": 0.98,
            },
        ],
        "visible_bounds": {"left": 0.05, "top": 0.20, "right": 0.95, "bottom": 0.95},
        "scroll_state": "not_scrolled",
        "page_boundary": {"top_visible": True, "bottom_visible": False},
        "candidates": [card()],
    }
    value.update(overrides)
    return value


class EquipmentListVisualParserTest(unittest.TestCase):
    def setUp(self):
        self.parser = EquipmentListVisualParser()

    def test_unique_target_constructs_auditable_navigation_evidence(self):
        result = self.parser.parse(observation(), TARGET)

        self.assertTrue(result.passed)
        self.assertEqual((result.mode, result.verification), (MODE, VERIFICATION))
        self.assertEqual(result.candidate_id, "candidate-001")
        self.assertEqual(result.evidence.page_type, "equipment_list")
        self.assertTrue(result.evidence.target_visible)
        navigation_result = NavigationEvidenceGate().locate_unique_target(result.evidence, TARGET)
        self.assertTrue(navigation_result.passed)
        self.assertIsNone(navigation_result.click_target)

    def test_low_confidence_or_missing_field_fails_before_evidence_construction(self):
        low_confidence = observation()
        low_confidence["candidates"][0]["field_observations"][0]["confidence"] = 0.979
        missing_field = observation()
        missing_field["candidates"][0]["field_observations"] = missing_field["candidates"][0]["field_observations"][1:]

        for value, reason in ((low_confidence, "candidate_field_confidence_too_low"), (missing_field, "candidate_fields_incomplete")):
            with self.subTest(reason=reason):
                result = self.parser.parse(value, TARGET)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_duplicate_cards_and_conflicting_card_fields_fail_closed(self):
        duplicate = observation(candidates=[card(), card("candidate-002", "c")])
        conflicting = observation()
        conflicting["candidates"][0]["field_observations"].append(
            {"name": "slot", "value": "Armor", "confidence": 0.99}
        )

        for value, reason in ((duplicate, "duplicate_candidate_detected"), (conflicting, "candidate_field_conflict")):
            with self.subTest(reason=reason):
                result = self.parser.parse(value, TARGET)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_similar_card_requires_exactly_one_target(self):
        similar = card("candidate-002", "d", gear_score=36)
        result = self.parser.parse(observation(candidates=[card(), similar]), TARGET)

        self.assertTrue(result.passed)
        self.assertEqual(result.candidate_id, "candidate-001")
        self.assertEqual(len(result.evidence.candidates), 2)

    def test_target_match_uses_expected_field_subset(self):
        candidate_with_extra_field = card()
        candidate_with_extra_field["field_observations"].append(
            {"name": "display_label", "value": "fixture only", "confidence": 0.99}
        )

        result = self.parser.parse(observation(candidates=[candidate_with_extra_field]), TARGET)

        self.assertTrue(result.passed)
        self.assertEqual(result.candidate_id, "candidate-001")

    def test_outside_card_unknown_scroll_and_missing_anchor_fail_closed(self):
        outside = observation()
        outside["candidates"][0]["bounds"]["bottom"] = 0.96
        outside_candidate_region = observation()
        outside_candidate_region["regions"][1]["bounds"]["right"] = 0.35
        unknown_scroll = observation(scroll_state="unknown")
        missing_anchor = observation(anchors=observation()["anchors"][:1])

        for value, reason in (
            (outside, "candidate_outside_visible_boundary"),
            (outside_candidate_region, "candidate_outside_candidate_list_region"),
            (unknown_scroll, "scroll_or_page_boundary_unknown"),
            (missing_anchor, "list_anchors_not_confirmed"),
        ):
            with self.subTest(reason=reason):
                result = self.parser.parse(value, TARGET)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_duplicate_required_anchor_or_invalid_page_boundary_fails_closed(self):
        duplicate_anchor = observation()
        duplicate_anchor["anchors"].append(copy.deepcopy(duplicate_anchor["anchors"][0]))
        unknown_boundary = observation(page_boundary={"top_visible": True})

        for value, reason in ((duplicate_anchor, "list_anchors_not_confirmed"), (unknown_boundary, "scroll_or_page_boundary_unknown")):
            with self.subTest(reason=reason):
                result = self.parser.parse(value, TARGET)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)

    def test_invalid_candidate_list_region_bounds_fails_closed_without_exception(self):
        invalid_region = observation()
        invalid_region["regions"][1].pop("bounds")

        result = self.parser.parse(invalid_region, TARGET)

        self.assertEqual(result.status, "fail_closed")
        self.assertIn("local_regions_not_confirmed", result.stop_reasons)
        self.assertIn("candidate_list_region_not_confirmed", result.stop_reasons)
        self.assertIsNone(result.evidence)


if __name__ == "__main__":
    unittest.main()
