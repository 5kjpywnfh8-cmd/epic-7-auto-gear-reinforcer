from __future__ import annotations

import copy
import unittest
import zlib

from src.e7_enhance.visual_adapter import StableFrames, VisualFrame
from src.e7_enhance.visual_list_observer import InMemoryPngListPageObserver, ListPageSampleFrames
from src.e7_enhance.visual_list_png_source import InMemoryPngListPageObservationSource
from src.e7_enhance.visual_list_recognizer import (
    LIST_PAGE_REGION_SCHEMA_VERSION,
    LIST_PAGE_VIEWPORT,
    RegisteredListPageLocalRecognizer,
    equipment_list_region_registry,
)
from src.e7_enhance.visual_list_observer import ListPageLocalRecognitionError
from src.e7_enhance.visual_list_production import (
    ProductionListPageReaderUnavailable,
    build_production_list_page_pipeline,
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


def _frame(payload=None, viewport=LIST_PAGE_VIEWPORT):
    payload = payload or _png(*viewport)
    return VisualFrame.from_bytes(
        source="public-synthetic-list-page-fixture",
        payload=payload,
        viewport=viewport,
        captured_at="2026-07-31T10:00:00+08:00",
    )


def _fields():
    return [
        {"name": name, "value": value, "confidence": 0.99}
        for name, value in TARGET.items()
    ]


def _ocr_records():
    records = {
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
    records.update({
        f"candidate_card:{index}": {"candidate": None}
        for index in range(2, 7)
    })
    records["candidate_card:1"] = {
        "candidate_id": "synthetic-candidate-001",
        "field_observations": _fields(),
    }
    return records


class FakeOcrReader:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def read_ocr(self, region_name, crop_png):
        self.calls.append((region_name, crop_png))
        return copy.deepcopy(self.records[region_name])


class FakeTemplateReader:
    def __init__(self):
        self.calls = []

    def match_template(self, region_name, crop_png):
        self.calls.append((region_name, crop_png))
        return {
            "visual_fingerprint": "a" * 64,
            "score": {"score": 0.99, "threshold": 0.98},
        }


class SequenceFrameSource:
    def __init__(self, frames):
        self.frames = iter(frames)

    def capture(self):
        return next(self.frames)


class InMemoryPngListPageObservationSourceTest(unittest.TestCase):
    def setUp(self):
        self.registry = equipment_list_region_registry()
        self.ocr = FakeOcrReader(_ocr_records())
        self.template = FakeTemplateReader()
        self.source = InMemoryPngListPageObservationSource(self.registry, self.ocr, self.template)

    def test_production_wiring_requires_explicit_factories_and_builds_fixed_recognizer(self):
        pipeline = build_production_list_page_pipeline(
            SequenceFrameSource([_frame(_png(seed=seed)) for seed in (25, 26, 27)]),
            ocr_reader_factory=lambda: FakeOcrReader(_ocr_records()),
            template_reader_factory=lambda: FakeTemplateReader(),
        )
        result = pipeline.observe("offline-production-wiring", TARGET)
        self.assertTrue(result.passed)
        self.assertEqual(len(set(result.evidence.stability["frame_hashes"])), 3)

    def test_production_wiring_missing_or_failing_factory_is_fail_closed(self):
        for args, reason in (
            ((None, lambda: FakeTemplateReader()), "list_reader_factory_missing"),
            ((lambda: FakeOcrReader(_ocr_records()), None), "list_reader_factory_missing"),
            ((lambda: (_ for _ in ()).throw(RuntimeError("offline factory failure")), lambda: FakeTemplateReader()), "list_reader_factory_failed"),
        ):
            with self.subTest(reason=reason):
                with self.assertRaises(ProductionListPageReaderUnavailable) as error:
                    build_production_list_page_pipeline(
                        SequenceFrameSource([_frame(), _frame(), _frame()]),
                        ocr_reader_factory=args[0],
                        template_reader_factory=args[1],
                    )
                self.assertTrue(str(error.exception))

    def test_production_wiring_rejects_invalid_reader_and_preserves_local_fail_closed(self):
        with self.assertRaises(ProductionListPageReaderUnavailable):
            build_production_list_page_pipeline(
                SequenceFrameSource([_frame(), _frame(), _frame()]),
                ocr_reader_factory=lambda: object(),
                template_reader_factory=lambda: object(),
            )

        low = copy.deepcopy(_ocr_records())
        low["candidate_list_region"]["score"]["score"] = 0.979
        pipeline = build_production_list_page_pipeline(
            SequenceFrameSource([_frame(), _frame(), _frame()]),
            ocr_reader_factory=lambda: FakeOcrReader(low),
            template_reader_factory=lambda: FakeTemplateReader(),
        )
        result = pipeline.observe("offline-production-low-confidence", TARGET)
        self.assertEqual(result.status, "fail_closed")
        self.assertIn("local_list_confidence_too_low", result.stop_reasons)
    def test_fixed_crops_feed_the_strict_recognizer_and_parser(self):
        recognizer = RegisteredListPageLocalRecognizer(self.registry, self.source)
        result = InMemoryPngListPageObserver(self.registry, recognizer).parse(
            "offline-png-source-operation",
            StableFrames((_frame(), _frame(), _frame())),
            TARGET,
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.candidate_id, "synthetic-candidate-001")
        self.assertEqual({name for name, _ in self.ocr.calls}, set(self.registry.recognizer_regions))
        self.assertEqual([name for name, _ in self.template.calls], ["candidate_card:1"])
        self.assertTrue(all(isinstance(payload, bytes) and payload.startswith(b"\x89PNG") for _, payload in self.ocr.calls))

    def test_reader_never_receives_unregistered_region_or_screen_coordinates(self):
        observed = self.source.observe(_frame(), self.registry.recognizer_regions)
        self.assertEqual(set(observed), {"schema_version", "viewport", "local_regions"})
        self.assertEqual(observed["schema_version"], LIST_PAGE_REGION_SCHEMA_VERSION)
        self.assertEqual(observed["viewport"], LIST_PAGE_VIEWPORT)
        self.assertTrue(all(len(call) == 2 for call in self.ocr.calls))

    def test_invalid_png_and_unknown_region_stop_before_readers(self):
        invalid_frame = _frame(payload=b"not-a-png")
        with self.assertRaises(ListPageLocalRecognitionError) as invalid:
            self.source.observe(invalid_frame, self.registry.recognizer_regions)
        self.assertEqual(invalid.exception.reason, "invalid_memory_png")
        self.assertEqual(self.ocr.calls, [])

        altered = dict(self.registry.recognizer_regions)
        altered["unexpected"] = {"left": 0.1, "top": 0.1, "right": 0.2, "bottom": 0.2}
        with self.assertRaises(ListPageLocalRecognitionError) as unknown:
            self.source.observe(_frame(), altered)
        self.assertEqual(unknown.exception.reason, "local_list_region_not_registered")
        self.assertEqual(self.ocr.calls, [])

    def test_low_confidence_and_conflicting_fields_fail_closed(self):
        low = _ocr_records()
        low["candidate_list_region"]["score"]["score"] = 0.979
        source = InMemoryPngListPageObservationSource(self.registry, FakeOcrReader(low), self.template)
        with self.assertRaises(ListPageLocalRecognitionError) as low_error:
            source.observe(_frame(), self.registry.recognizer_regions)
        self.assertEqual(low_error.exception.reason, "local_list_confidence_too_low")

        conflict = _ocr_records()
        conflict["candidate_card:1"]["field_observations"].append(
            {"name": "slot", "value": "Armor", "confidence": 0.99}
        )
        source = InMemoryPngListPageObservationSource(self.registry, FakeOcrReader(conflict), self.template)
        with self.assertRaises(ListPageLocalRecognitionError) as conflict_error:
            source.observe(_frame(), self.registry.recognizer_regions)
        self.assertEqual(conflict_error.exception.reason, "candidate_fields_incomplete")

        class LowTemplateReader(FakeTemplateReader):
            def match_template(self, region_name, crop_png):
                return {
                    "visual_fingerprint": "a" * 64,
                    "score": {"score": 0.979, "threshold": 0.98},
                }

        source = InMemoryPngListPageObservationSource(
            self.registry, FakeOcrReader(_ocr_records()), LowTemplateReader()
        )
        with self.assertRaises(ListPageLocalRecognitionError) as template_error:
            source.observe(_frame(), self.registry.recognizer_regions)
        self.assertEqual(template_error.exception.reason, "local_list_confidence_too_low")


if __name__ == "__main__":
    unittest.main()
