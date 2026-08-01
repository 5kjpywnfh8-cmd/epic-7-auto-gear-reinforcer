from __future__ import annotations

import copy
import unittest
import zlib

from src.e7_enhance.visual_adapter import StableFrames, VisualFrame
from src.e7_enhance.visual_list_observer import InMemoryPngListPageObserver
from src.e7_enhance.visual_list_recognizer import (
    LIST_PAGE_REGION_SCHEMA_VERSION,
    LIST_PAGE_VIEWPORT,
    RegisteredListPageLocalRecognizer,
    equipment_list_region_registry,
)


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


def _png(width=1280, height=720, seed=25):
    def chunk(kind, data):
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    row = b"\x00" + bytes((seed, seed, seed)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def _frames(viewport=LIST_PAGE_VIEWPORT):
    frame = VisualFrame.from_bytes(
        source="public-synthetic-list-page-fixture",
        payload=_png(*viewport),
        viewport=viewport,
        captured_at="2026-07-30T10:00:00+08:00",
    )
    return StableFrames((frame, frame, frame))


def _sha(character):
    return character * 64


def _candidate():
    return {
        "candidate_id": "synthetic-candidate-001",
        "visual_fingerprint": _sha("a"),
        "field_observations": [
            {"name": name, "value": value, "confidence": 0.99}
            for name, value in TARGET.items()
        ],
    }


def _observation():
    return {
        "schema_version": LIST_PAGE_REGION_SCHEMA_VERSION,
        "viewport": LIST_PAGE_VIEWPORT,
        "local_regions": {
            "list_header_region": {
                "score": {"score": 0.99, "threshold": 0.98},
                "anchors": [
                    {"name": "list_header", "score": 0.99, "threshold": 0.98},
                    {"name": "sort_button", "score": 0.99, "threshold": 0.98},
                ],
            },
            "candidate_list_region": {
                "score": {"score": 0.99, "threshold": 0.98},
                "scroll_state": "not_scrolled",
                "page_boundary": {"top_visible": True, "bottom_visible": False},
            },
            "candidate_card:1": {"candidate": _candidate()},
            "candidate_card:2": {"candidate": None},
            "candidate_card:3": {"candidate": None},
            "candidate_card:4": {"candidate": None},
            "candidate_card:5": {"candidate": None},
            "candidate_card:6": {"candidate": None},
            "candidate_card:7": {"candidate": None},
            "candidate_card:8": {"candidate": None},
            "candidate_card:9": {"candidate": None},
            "candidate_card:10": {"candidate": None},
            "candidate_card:11": {"candidate": None},
            "candidate_card:12": {"candidate": None},
            "candidate_card:13": {"candidate": None},
            "candidate_card:14": {"candidate": None},
            "candidate_card:15": {"candidate": None},
            "candidate_card:16": {"candidate": None},
            "candidate_card:17": {"candidate": None},
            "candidate_card:18": {"candidate": None},
            "candidate_card:19": {"candidate": None},
            "candidate_card:20": {"candidate": None},
        },
    }


class SyntheticObservationSource:
    def __init__(self, observation):
        self.observation = observation
        self.calls = []

    def observe(self, frame, regions):
        self.calls.append((frame, regions))
        return copy.deepcopy(self.observation)


class RaisingObservationSource:
    def observe(self, frame, regions):
        raise RuntimeError("synthetic source failure")


class RegisteredListPageLocalRecognizerTest(unittest.TestCase):
    def setUp(self):
        self.registry = equipment_list_region_registry()

    def _parse(self, observation=None, frames=None):
        source = SyntheticObservationSource(observation or _observation())
        recognizer = RegisteredListPageLocalRecognizer(self.registry, source)
        result = InMemoryPngListPageObserver(self.registry, recognizer).parse(
            "public-synthetic-list-operation", frames or _frames(), TARGET
        )
        return result, source

    def test_fixed_registry_is_versioned_and_drives_the_in_memory_observer(self):
        result, source = self._parse()

        self.assertTrue(result.passed)
        self.assertEqual(self.registry.viewport, LIST_PAGE_VIEWPORT)
        self.assertEqual(self.registry.schema_version, LIST_PAGE_REGION_SCHEMA_VERSION)
        self.assertEqual(result.candidate_id, "synthetic-candidate-001")
        self.assertEqual(len(source.calls), 1)
        self.assertEqual(set(source.calls[0][1]), set(self.registry.recognizer_regions))

    def test_unknown_viewport_stops_before_the_injected_source(self):
        result, source = self._parse(frames=_frames((100, 100)))

        self.assertEqual(result.stop_reasons, ("unknown_list_viewport",))
        self.assertEqual(source.calls, [])
        self.assertIsNone(result.evidence)

    def test_unregistered_region_low_confidence_and_unknown_boundary_fail_closed(self):
        unregistered = _observation()
        unregistered["local_regions"]["candidate_card:unknown"] = {"candidate": None}
        low_confidence = _observation()
        low_confidence["local_regions"]["candidate_list_region"]["score"]["score"] = 0.979
        boundary = _observation()
        boundary["local_regions"]["candidate_list_region"]["page_boundary"] = {"top_visible": True}
        unknown_scroll = _observation()
        unknown_scroll["local_regions"]["candidate_list_region"]["scroll_state"] = "unknown"

        for observation, reason in (
            (unregistered, "local_list_region_not_registered"),
            (low_confidence, "local_list_confidence_too_low"),
            (boundary, "scroll_or_page_boundary_unknown"),
            (unknown_scroll, "scroll_or_page_boundary_unknown"),
        ):
            with self.subTest(reason=reason):
                result, _ = self._parse(observation)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_conflicting_or_unknown_candidate_fields_fail_closed(self):
        conflict = _observation()
        conflict["local_regions"]["candidate_card:1"]["candidate"]["field_observations"].append(
            {"name": "slot", "value": "Armor", "confidence": 0.99}
        )
        unknown = _observation()
        unknown["local_regions"]["candidate_card:1"]["candidate"]["field_observations"][0]["name"] = "unknown_field"

        for observation, reason in ((conflict, "candidate_field_conflict"), (unknown, "local_list_token_unknown")):
            with self.subTest(reason=reason):
                result, _ = self._parse(observation)
                self.assertEqual(result.status, "fail_closed")
                self.assertIn(reason, result.stop_reasons)
                self.assertIsNone(result.evidence)

    def test_source_exception_stops_before_navigation_evidence(self):
        recognizer = RegisteredListPageLocalRecognizer(self.registry, RaisingObservationSource())
        result = InMemoryPngListPageObserver(self.registry, recognizer).parse(
            "public-synthetic-list-operation", _frames(), TARGET
        )

        self.assertEqual(result.stop_reasons, ("local_list_observation_failed",))
        self.assertIsNone(result.evidence)


if __name__ == "__main__":
    unittest.main()
