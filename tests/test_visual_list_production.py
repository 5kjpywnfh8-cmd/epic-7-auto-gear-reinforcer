from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zlib
from pathlib import Path

from src.e7_enhance.visual_adapter import CallbackFrameSource, VisualFrame
from src.e7_enhance.visual_list_production import (
    ProductionListPagePipeline,
    ProductionListPageReaderUnavailable,
    build_production_list_page_pipeline,
    build_production_list_page_pipeline_from_assets,
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


def _frame(seed=25, viewport=None):
    viewport = viewport or LIST_PAGE_VIEWPORT
    return VisualFrame.from_bytes(
        source="production-list-fixture",
        payload=_png(width=viewport[0], height=viewport[1], seed=seed),
        viewport=viewport,
        captured_at="2026-08-01T10:00:00+08:00",
    )


def _complete_field_mapping():
    fields = ("slot", "rank", "level", "enhance", "set", "main", "substats", "gear_score")
    tokens = {
        "slot": "武器", "rank": "传说", "level": "85", "enhance": "+3",
        "set": "生命套装", "main": "攻击力", "substats": "攻击%", "gear_score": "37",
    }
    normalized = {
        "slot": "Weapon", "rank": "Epic", "level": 85, "enhance": 3,
        "set": "HealthSet", "main": "Attack", "substats": "AttackPercent", "gear_score": 37,
    }
    return [
        {
            "field": field,
            "token": tokens[field],
            "normalized": normalized[field],
            "confidence": 0.99,
            "source": "audited_fixture",
            "status": "audited",
        }
        for field in fields
    ]


def _write_complete_fixture_assets(root):
    """Write audited-complete field mapping and full-card template manifests.

    The card template content is exactly the ``candidate_card:1`` crop of a
    fixed synthetic frame, so the production template reader finds a unique
    audited match during a normal observation pass.
    """
    from src.e7_enhance.visual_adb_recognition import InMemoryPngRegionExtractor
    from src.e7_enhance.visual_platform import LocalRegion

    root = Path(root)
    mapping_path = root / "field_mapping_manifest.json"
    mapping_path.write_text(json.dumps({
        "schema_version": 1,
        "asset_kind": "equipment_list_field_mapping",
        "status": "audited_complete",
        "mappings": _complete_field_mapping(),
    }, ensure_ascii=False), encoding="utf-8")

    frame = _frame(seed=25)
    registry = equipment_list_region_registry()
    region = registry.by_name("candidate_card:1")
    width, height = LIST_PAGE_VIEWPORT
    left, top, right, bottom = (
        round(float(region.bounds[key]) * dimension)
        for key, dimension in zip(("left", "top", "right", "bottom"), (width, height, width, height))
    )
    crop = InMemoryPngRegionExtractor().extract(
        frame, LocalRegion(region.name, dict(region.bounds), (left, top, right, bottom))
    )
    card_path = root / "card.png"
    card_path.write_bytes(crop)
    template_path = root / "card_fingerprint_manifest.json"
    template_path.write_text(json.dumps({
        "schema_version": 1,
        "asset_kind": "equipment_list_card_fingerprint",
        "status": "audited_complete",
        "template_scope": "full_card",
        "templates": [{
            "id": "fixture_card",
            "file": "card.png",
            "sha256": hashlib.sha256(crop).hexdigest(),
            "viewport": [right - left, bottom - top],
            "threshold": 0.98,
            "status": "audited",
        }],
    }), encoding="utf-8")
    return mapping_path, template_path


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
    records.update({f"candidate_card:{index}": {"candidate": None} for index in range(2, 21)})
    records["candidate_card:1"] = {
        "candidate_id": "production-candidate-001",
        "field_observations": _fields(),
    }
    return records


class FixtureOcrReader(ListPagePngOcrReader):
    def __init__(self, records=None):
        self.records = records if records is not None else _records()

    def read_ocr(self, region_name, crop_png):
        return copy.deepcopy(self.records[region_name])


class FixtureTemplateReader(ListPagePngTemplateReader):
    def match_template(self, region_name, crop_png):
        return {"visual_fingerprint": "a" * 64, "score": {"score": 0.99, "threshold": 0.98}}


class ProductionListPageAssetsPipelineTest(unittest.TestCase):
    """Regression for the asset-gated production assembly entry point.

    The repository manifests intentionally stay ``incomplete``/``missing``, so
    the default entry point must fail closed before any frame capture.  The
    fixture manifests below prove the wiring itself is sound when both audited
    bundles are present.
    """

    def test_repository_manifests_fail_closed_before_frame_capture(self):
        with self.assertRaises(ProductionListPageReaderUnavailable) as error:
            build_production_list_page_pipeline_from_assets(
                CallbackFrameSource(lambda: _frame()),
                ocr_reader_factory=FixtureOcrReader,
            )
        self.assertTrue(str(error.exception))

    def test_complete_fixture_manifests_parse_a_normal_observation_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, template_path = _write_complete_fixture_assets(Path(directory))
            pipeline = build_production_list_page_pipeline_from_assets(
                CallbackFrameSource(lambda: _frame(seed=25)),
                ocr_reader_factory=FixtureOcrReader,
                field_mapping_manifest=str(mapping_path),
                card_template_manifest=str(template_path),
            )
            self.assertIsInstance(pipeline, ProductionListPagePipeline)
            result = pipeline.observe("asset-gated-normal", TARGET)
            self.assertTrue(result.passed)
            self.assertEqual(result.candidate_id, "production-candidate-001")

    def test_field_mapping_missing_a_required_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, template_path = _write_complete_fixture_assets(Path(directory))
            raw = json.loads(mapping_path.read_text(encoding="utf-8"))
            raw["mappings"] = [entry for entry in raw["mappings"] if entry["field"] != "gear_score"]
            mapping_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ProductionListPageReaderUnavailable) as error:
                build_production_list_page_pipeline_from_assets(
                    CallbackFrameSource(lambda: _frame()),
                    ocr_reader_factory=FixtureOcrReader,
                    field_mapping_manifest=str(mapping_path),
                    card_template_manifest=str(template_path),
                )
            self.assertIn("does not cover", str(error.exception))

    def test_low_confidence_ocr_fails_closed_through_assets_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, template_path = _write_complete_fixture_assets(Path(directory))

            def low_ocr_factory():
                low = copy.deepcopy(_records())
                low["candidate_list_region"]["score"]["score"] = 0.979
                return FixtureOcrReader(low)

            pipeline = build_production_list_page_pipeline_from_assets(
                CallbackFrameSource(lambda: _frame(seed=25)),
                ocr_reader_factory=low_ocr_factory,
                field_mapping_manifest=str(mapping_path),
                card_template_manifest=str(template_path),
            )
            result = pipeline.observe("asset-gated-low-confidence", TARGET)
            self.assertEqual(result.status, "fail_closed")
            self.assertIn("local_list_confidence_too_low", result.stop_reasons)

    def test_conflicting_fields_fail_closed_through_assets_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, template_path = _write_complete_fixture_assets(Path(directory))

            def conflict_ocr_factory():
                conflict = copy.deepcopy(_records())
                conflict["candidate_card:1"]["field_observations"].append(
                    {"name": "slot", "value": "Armor", "confidence": 0.99}
                )
                return FixtureOcrReader(conflict)

            pipeline = build_production_list_page_pipeline_from_assets(
                CallbackFrameSource(lambda: _frame(seed=25)),
                ocr_reader_factory=conflict_ocr_factory,
                field_mapping_manifest=str(mapping_path),
                card_template_manifest=str(template_path),
            )
            result = pipeline.observe("asset-gated-conflict", TARGET)
            self.assertEqual(result.status, "fail_closed")
            self.assertIn("candidate_fields_incomplete", result.stop_reasons)

    def test_card_template_hash_mismatch_fails_closed_through_assets_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, template_path = _write_complete_fixture_assets(Path(directory))
            raw = json.loads(template_path.read_text(encoding="utf-8"))
            raw["templates"][0]["sha256"] = hashlib.sha256(b"tampered").hexdigest()
            template_path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ProductionListPageReaderUnavailable) as error:
                build_production_list_page_pipeline_from_assets(
                    CallbackFrameSource(lambda: _frame()),
                    ocr_reader_factory=FixtureOcrReader,
                    field_mapping_manifest=str(mapping_path),
                    card_template_manifest=str(template_path),
                )
            self.assertIn("hash mismatch", str(error.exception))

    def test_viewport_drift_fails_closed_through_assets_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            mapping_path, template_path = _write_complete_fixture_assets(Path(directory))
            drifted = _frame(seed=25, viewport=(1000, 700))
            pipeline = build_production_list_page_pipeline_from_assets(
                CallbackFrameSource(lambda: drifted),
                ocr_reader_factory=FixtureOcrReader,
                field_mapping_manifest=str(mapping_path),
                card_template_manifest=str(template_path),
            )
            result = pipeline.observe("asset-gated-viewport-drift", TARGET)
            self.assertEqual(result.status, "fail_closed")
            self.assertIn("unknown_list_viewport", result.stop_reasons)


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
