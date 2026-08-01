from __future__ import annotations

import copy
import unittest
import zlib

from src.e7_enhance.visual_adapter import CallbackFrameSource
from src.e7_enhance.visual_list_production import (
    ProductionListPageReaderUnavailable,
    build_production_list_page_pipeline,
)
from src.e7_enhance.visual_list_recognizer import LIST_PAGE_VIEWPORT, equipment_list_region_registry
from src.e7_enhance.visual_list_png_source import ListPagePngOcrReader, ListPagePngTemplateReader


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


def _frame(seed=25):
    from src.e7_enhance.visual_adapter import VisualFrame

    return VisualFrame.from_bytes(
        source="production-list-fixture",
        payload=_png(seed=seed),
        viewport=LIST_PAGE_VIEWPORT,
        captured_at="2026-08-01T10:00:00+08:00",
    )


def _fields():
    return [
        {"name": name, "value": value, "confidence": 0.99}
        for name, value in TARGET.items()
    ]


def _records():
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
    records.update({f"candidate_card:{index}": {"candidate": None} for index in range(2, 7)})
    records["candidate_card:1"] = {
        "candidate_id": "production-candidate-001",
        "field_observations": _fields(),
    }
    return records


class FixtureOcrReader(ListPagePngOcrReader):
    def __init__(self):
        self.records = _records()

    def read_ocr(self, region_name, crop_png):
        return copy.deepcopy(self.records[region_name])


class FixtureTemplateReader(ListPagePngTemplateReader):
    def match_template(self, region_name, crop_png):
        return {"visual_fingerprint": "a" * 64, "score": {"score": 0.99, "threshold": 0.98}}


class ProductionListPagePipelineTest(unittest.TestCase):
    def test_explicit_factories_assemble_and_parse_three_frames(self):
        frames = iter((_frame(25), _frame(26), _frame(27)))
        pipeline = build_production_list_page_pipeline(
            CallbackFrameSource(lambda: next(frames)),
            ocr_reader_factory=FixtureOcrReader,
            template_reader_factory=FixtureTemplateReader,
        )
        result = pipeline.observe("production-list-operation", TARGET)
        self.assertTrue(result.passed)
        self.assertEqual(result.candidate_id, "production-candidate-001")
        self.assertTrue(result.evidence.stability["visual_fields_stable"])
        self.assertEqual(len(result.evidence.stability["frame_hashes"]), 3)

    def test_missing_or_invalid_factory_fails_closed_before_capture(self):
        with self.assertRaises(ProductionListPageReaderUnavailable):
            build_production_list_page_pipeline(
                CallbackFrameSource(lambda: _frame()),
                ocr_reader_factory=None,
                template_reader_factory=FixtureTemplateReader,
            )
        with self.assertRaises(ProductionListPageReaderUnavailable):
            build_production_list_page_pipeline(
                CallbackFrameSource(lambda: _frame()),
                ocr_reader_factory=lambda: object(),
                template_reader_factory=FixtureTemplateReader,
            )

    def test_reader_factory_error_is_not_retried(self):
        calls = []

        def failed_factory():
            calls.append("ocr")
            raise RuntimeError("engine unavailable")

        with self.assertRaises(ProductionListPageReaderUnavailable):
            build_production_list_page_pipeline(
                CallbackFrameSource(lambda: _frame()),
                ocr_reader_factory=failed_factory,
                template_reader_factory=FixtureTemplateReader,
            )
        self.assertEqual(calls, ["ocr"])


if __name__ == "__main__":
    unittest.main()
