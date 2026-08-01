from __future__ import annotations

import copy
import unittest
import zlib

from src.e7_enhance.visual_adapter import StableFrames, VisualFrame
from src.e7_enhance.visual_list_observer import (
    InMemoryPngListPageLocalObservationSource,
)
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


def png(width=1280, height=720, seed=25):
    def chunk(kind, data):
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    row = b"\x00" + bytes((seed, seed, seed)) * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00") + chunk(b"IDAT", zlib.compress(row * height)) + chunk(b"IEND", b"")


def frames():
    frame = VisualFrame.from_bytes(
        source="public-synthetic-list-page",
        payload=png(),
        viewport=LIST_PAGE_VIEWPORT,
        captured_at="2026-07-31T10:00:00+08:00",
    )
    return StableFrames((frame, frame, frame))


def sha(value):
    return value * 64


def candidate():
    return {
        "candidate_id": "synthetic-candidate-001",
        "visual_fingerprint": sha("a"),
        "field_observations": [
            {"name": name, "value": value, "confidence": 0.99} for name, value in TARGET.items()
        ],
    }


def local_values():
    values = {
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
    }
    values.update({f"candidate_card:{index}": {"candidate": candidate() if index == 1 else None} for index in range(1, 21)})
    return values


class RecordingReader:
    def __init__(self, value):
        self.value = value
        self.crops = []

    def read(self, frame, crop):
        self.crops.append(crop)
        self.value = self.value
        return copy.deepcopy(self.value)


class PngListPageLocalObservationSourceTest(unittest.TestCase):
    def setUp(self):
        self.registry = equipment_list_region_registry()
        self.readers = {
            name: RecordingReader(value)
            for name, value in local_values().items()
        }

    def test_memory_crops_and_injected_readers_feed_registered_recognizer(self):
        source = InMemoryPngListPageLocalObservationSource(self.registry, self.readers)
        recognizer = RegisteredListPageLocalRecognizer(self.registry, source)
        from src.e7_enhance.visual_list_observer import InMemoryPngListPageObserver

        result = InMemoryPngListPageObserver(self.registry, recognizer).parse(
            "synthetic-local-source", frames(), TARGET
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.candidate_id, "synthetic-candidate-001")
        self.assertEqual(len(self.readers["list_header_region"].crops), 1)
        self.assertEqual(self.readers["list_header_region"].crops[0].pixel_bounds, (64, 14, 1216, 65))
        self.assertEqual(self.readers["list_header_region"].crops[0].payload[:8], b"\x89PNG\r\n\x1a\n")

    def test_reader_failure_and_unknown_viewport_stop_before_evidence(self):
        class BrokenReader:
            def read(self, frame, crop):
                raise RuntimeError("reader failed")

        self.readers["candidate_card:1"] = BrokenReader()
        source = InMemoryPngListPageLocalObservationSource(self.registry, self.readers)
        recognizer = RegisteredListPageLocalRecognizer(self.registry, source)
        from src.e7_enhance.visual_list_observer import InMemoryPngListPageObserver

        result = InMemoryPngListPageObserver(self.registry, recognizer).parse("broken", frames(), TARGET)
        self.assertEqual(result.stop_reasons, ("local_list_reader_failed",))
        self.assertIsNone(result.evidence)

        result = InMemoryPngListPageObserver(self.registry, recognizer).parse(
            "wrong-viewport", StableFrames((VisualFrame.from_bytes(source="fixture", payload=png(100, 100), viewport=(100, 100), captured_at="2026-07-31T10:00:00+08:00"),) * 3), TARGET
        )
        self.assertEqual(result.stop_reasons, ("unknown_list_viewport",))

    def test_reader_results_must_be_mappings_and_reader_set_is_exact(self):
        self.readers["candidate_card:1"] = lambda frame, crop: None
        source = InMemoryPngListPageLocalObservationSource(self.registry, self.readers)
        recognizer = RegisteredListPageLocalRecognizer(self.registry, source)
        from src.e7_enhance.visual_list_observer import InMemoryPngListPageObserver

        result = InMemoryPngListPageObserver(self.registry, recognizer).parse("invalid", frames(), TARGET)
        self.assertEqual(result.stop_reasons, ("local_list_reader_invalid",))
        with self.assertRaises(ValueError):
            InMemoryPngListPageLocalObservationSource(self.registry, {"list_header_region": self.readers["list_header_region"]})


if __name__ == "__main__":
    unittest.main()
