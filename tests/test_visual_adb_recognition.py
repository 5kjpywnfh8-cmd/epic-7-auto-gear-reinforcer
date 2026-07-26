from __future__ import annotations

import unittest
import zlib

from src.e7_enhance.visual_adb import parse_png_viewport
from src.e7_enhance.visual_adb import AdbScreencapBackend
from src.e7_enhance.visual_adapter import EvidenceParseError, PlatformFrameSource, VisualAdapterSampler, VisualFrame
from src.e7_enhance.visual_platform import LocalRegion
from src.e7_enhance.visual_adb_recognition import (
    AdbLocalRecognitionEvidenceParser,
    InMemoryPngRegionExtractor,
    PaddleLineSourceRecognizer,
    PngRegionRecognitionError,
)
from src.e7_enhance.visual_runtime import ExpectedVisualState, SamplingRequest, VisualEvidenceGate


def png(width=100, height=100, seed=25):
    def chunk(kind, data):
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    row = b"\x00" + bytes((seed, seed, seed)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def oversized_png(width=100_000, height=1_000):
    def chunk(kind, data):
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        + chunk(b"IDAT", zlib.compress(b""))
        + chunk(b"IEND", b"")
    )


def frame(payload=None, viewport=(100, 100)):
    return VisualFrame.from_bytes(
        source="adb_screencap:offline-device",
        payload=payload or png(),
        viewport=viewport,
        captured_at="2026-07-26T10:00:00+08:00",
    )


class InMemoryPngRegionExtractorTest(unittest.TestCase):
    def test_crops_png_region_in_memory_with_pixel_bounds(self):
        region = LocalRegion("set", {"left": 0.1, "top": 0.2, "right": 0.4, "bottom": 0.5}, (10, 20, 40, 50))

        crop = InMemoryPngRegionExtractor().extract(frame(), region)

        self.assertEqual(parse_png_viewport(crop), (30, 30))
        self.assertTrue(crop.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_invalid_png_viewport_mismatch_and_out_of_bounds_fail_closed(self):
        region = LocalRegion("set", {"left": 0, "top": 0, "right": 1, "bottom": 1}, (0, 0, 100, 100))
        extractor = InMemoryPngRegionExtractor()
        with self.assertRaises(PngRegionRecognitionError):
            extractor.extract(frame(b"not-a-png"), region)
        with self.assertRaises(PngRegionRecognitionError):
            extractor.extract(frame(viewport=(101, 100)), region)
        with self.assertRaises(PngRegionRecognitionError):
            extractor.extract(frame(), LocalRegion("bad", {}, (0, 0, 101, 100)))

    def test_oversized_png_is_rejected_before_pixel_allocation(self):
        payload = oversized_png()
        region = LocalRegion("set", {}, (0, 0, 1, 1))

        with self.assertRaises(PngRegionRecognitionError):
            InMemoryPngRegionExtractor().extract(frame(payload, viewport=(100_000, 1_000)), region)


def accepted_lines(*, set_confidence=0.999, extra=()):
    lines = [
        {"text": "85", "confidence": 0.999}, {"text": "传说武器", "confidence": 0.999},
        {"text": "攻击力", "confidence": 0.999}, {"text": "100", "confidence": 0.999},
        {"text": "生命值", "confidence": 0.999}, {"text": "8%", "confidence": 0.999},
        {"text": "攻击力", "confidence": 0.999}, {"text": "4%", "confidence": 0.999},
        {"text": "暴击伤害", "confidence": 0.999}, {"text": "5%", "confidence": 0.999},
        {"text": "生命值", "confidence": 0.999}, {"text": "159", "confidence": 0.999},
        {"text": "装备分数", "confidence": 0.999}, {"text": "25", "confidence": 0.999},
        {"text": "速度套装(0/4)", "confidence": set_confidence}, {"text": "exp0/525", "confidence": 0.999},
    ]
    return lines + list(extra)


class FakeAdbTransport:
    def __init__(self, frames):
        self.frames = list(frames)
        self.calls = []

    def devices_long(self):
        self.calls.append("devices -l")
        return "List of devices attached\nemulator-5554 device product:MuMu\n"

    def exec_out_screencap_png(self, serial):
        self.calls.append(("exec-out screencap -p", serial))
        return self.frames.pop(0)


class FakeTemplateRecognizer:
    def __init__(self, anchors):
        self.anchors = anchors
        self.calls = 0

    def recognize(self, frame, regions):
        self.calls += 1
        self.region_names = tuple(regions)
        self.crop_viewports = {name: parse_png_viewport(sample.payload) for name, sample in regions.items()}
        return self.anchors


class FakePaddleLineSource:
    def __init__(self, lines):
        self.lines = lines
        self.calls = 0

    def read_lines(self, frame, regions):
        self.calls += 1
        self.region_names = tuple(regions)
        return self.lines


def anchors(count=2):
    values = [
        {"name": "back_arrow", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
        {"name": "help_icon", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
    ]
    return values[:count]


def adb_sampler(template, line_source):
    transport = FakeAdbTransport((png(), png(), png()))
    source = PlatformFrameSource(
        AdbScreencapBackend(
            transport,
            content_validator=lambda payload, viewport: True,
            timestamp_factory=lambda: "2026-07-26T10:00:00+08:00",
        )
    )
    parser = AdbLocalRecognitionEvidenceParser(
        template,
        line_source,
        resource_preview={
            "visible": True,
            "materials": {"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0},
            "gold": 17600,
        },
    )
    return VisualAdapterSampler(source, parser), transport


class AdbLocalRecognitionEvidenceParserTest(unittest.TestCase):
    def test_adb_stable_frame_to_local_templates_paddle_lines_and_visual_evidence(self):
        template = FakeTemplateRecognizer(anchors())
        lines = FakePaddleLineSource(accepted_lines())
        sampler, transport = adb_sampler(template, lines)

        evidence = sampler.capture(SamplingRequest("operation-001", "pre_action", 0))
        gate = VisualEvidenceGate().evaluate(
            evidence,
            ExpectedVisualState(
                node=0,
                phase="pre_action",
                visible_fields=evidence.target["visible_fields"],
                visual_fingerprint=evidence.target["visual_fingerprint"],
                resource_values={"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0, "gold": 17600},
                operation_id="operation-001",
            ),
        )

        self.assertEqual(gate.status, "ready")
        self.assertEqual(gate.mode, "visual_only")
        self.assertEqual(gate.verification, "unverified")
        self.assertEqual(evidence.sampler["adapter"], "adb_local_visual_recognition")
        self.assertEqual(evidence.sampler["frame_provenance"]["source"], "adb_screencap:emulator-5554")
        self.assertEqual(len(evidence.anchors), 2)
        self.assertTrue(all(score >= 0.98 for score in evidence.target["field_confidence"].values()))
        self.assertEqual(template.calls, 1)
        self.assertEqual(lines.calls, 1)
        self.assertEqual(set(template.region_names), {"set", "slot", "rank", "enhance", "level", "main", "substats"})
        self.assertTrue(all(width > 0 and height > 0 for width, height in template.crop_viewports.values()))
        self.assertEqual(transport.calls.count("devices -l"), 3)

    def test_missing_templates_low_confidence_and_conflicting_fields_fail_without_ocr_retry(self):
        cases = (
            (FakeTemplateRecognizer(anchors(1)), FakePaddleLineSource(accepted_lines()), "template"),
            (FakeTemplateRecognizer(anchors()), FakePaddleLineSource(accepted_lines(set_confidence=0.979)), "confidence"),
            (FakeTemplateRecognizer(anchors()), FakePaddleLineSource(accepted_lines(extra=({"text": "英雄武器", "confidence": 0.999},))), "conflict"),
        )
        for template, lines, reason in cases:
            with self.subTest(reason=reason):
                sampler, _ = adb_sampler(template, lines)
                with self.assertRaises(EvidenceParseError):
                    sampler.capture(SamplingRequest("operation-001", "pre_action", 0))
                self.assertEqual(template.calls, 1)
                self.assertEqual(lines.calls, 0 if reason == "template" else 1)

    def test_retry_marked_line_source_is_rejected_without_parser_retry(self):
        line_source = FakePaddleLineSource(accepted_lines(extra=({"text": "暴击伤害", "confidence": 0.999, "retry_for": 8},)))
        sampler, _ = adb_sampler(FakeTemplateRecognizer(anchors()), line_source)

        with self.assertRaises(EvidenceParseError):
            sampler.capture(SamplingRequest("operation-001", "pre_action", 0))

        self.assertEqual(line_source.calls, 1)


if __name__ == "__main__":
    unittest.main()
