from __future__ import annotations

import unittest

from src.e7_enhance.visual_adapter import (
    FrameCaptureError,
    PlatformFrameSource,
    PlatformWindow,
    StableFrameCollector,
    StableFrames,
    VisualAdapterSampler,
    VisualFrame,
)
from src.e7_enhance.visual_platform import (
    CallbackRegionExtractor,
    LocalRecognitionError,
    LocalRecognitionEvidenceParser,
    LazyWindowsReadOnlyBackend,
    PaddleLinesOcrRecognizer,
    WindowsCaptureConfig,
)
from src.e7_enhance.visual_runtime import SamplingRequest


PNG_BYTES = b"\x89PNG\r\n\x1a\nfixture"


def frame(payload=PNG_BYTES):
    return VisualFrame.from_bytes(
        source="fake-platform:fixture-window",
        payload=payload,
        viewport=(1600, 900),
        captured_at="2026-07-26T10:00:00+08:00",
    )


class FakeWindowsDriver:
    def __init__(self, *, window=PlatformWindow("fixture-window", "fake-platform"), payload=PNG_BYTES):
        self.window = window
        self.payload = payload
        self.calls = []

    def locate_window(self, config):
        self.calls.append(("locate", config.window_title))
        return self.window

    def client_viewport(self, window):
        self.calls.append(("viewport", window.identifier))
        return (1600, 900)

    def capture_png(self, window):
        self.calls.append(("capture", window.identifier))
        return self.payload


class FakeTemplateRecognizer:
    def recognize(self, frame_value, regions):
        return [
            {"name": "back_arrow", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
            {"name": "help_icon", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.2},
        ]


def paddle_lines(set_confidence=0.999):
    return [
        {"text": "85", "confidence": 0.999}, {"text": "传说武器", "confidence": 0.999},
        {"text": "攻击力", "confidence": 0.999}, {"text": "100", "confidence": 0.999},
        {"text": "生命值", "confidence": 0.999}, {"text": "4%", "confidence": 0.999},
        {"text": "暴击伤害", "confidence": 0.999}, {"text": "4%", "confidence": 0.999},
        {"text": "暴击率", "confidence": 0.999}, {"text": "5%", "confidence": 0.999},
        {"text": "速度", "confidence": 0.999}, {"text": "2", "confidence": 0.999},
        {"text": "装备分数", "confidence": 0.999}, {"text": "25", "confidence": 0.999},
        {"text": "爆伤套装(0/4)", "confidence": set_confidence}, {"text": "exp0/525", "confidence": 0.999},
    ]


class LazyWindowsBackendTest(unittest.TestCase):
    def test_constructing_is_lazy_and_fake_driver_produces_only_png_frame_metadata(self):
        calls = []
        driver = FakeWindowsDriver()
        backend = LazyWindowsReadOnlyBackend(
            WindowsCaptureConfig(window_title="Epic Seven", source="fake-platform"),
            lambda: calls.append("constructed") or driver,
            timestamp_factory=lambda: "2026-07-26T10:00:00+08:00",
        )

        self.assertEqual(calls, [])
        self.assertEqual(driver.calls, [])

        captured = PlatformFrameSource(backend).capture()

        self.assertEqual(calls, ["constructed"])
        self.assertEqual(captured.payload, PNG_BYTES)
        self.assertEqual(captured.source, "fake-platform:fixture-window")
        self.assertEqual(captured.viewport, (1600, 900))
        self.assertEqual(driver.calls, [
            ("locate", "Epic Seven"),
            ("viewport", "fixture-window"),
            ("capture", "fixture-window"),
        ])

    def test_missing_driver_window_and_non_png_payload_fail_closed(self):
        unavailable = LazyWindowsReadOnlyBackend(WindowsCaptureConfig(window_title="Epic Seven"))
        with self.assertRaises(FrameCaptureError):
            PlatformFrameSource(unavailable).capture()

        missing_window = FakeWindowsDriver(window=None)
        backend = LazyWindowsReadOnlyBackend(WindowsCaptureConfig(window_title="Epic Seven"), lambda: missing_window)
        with self.assertRaises(Exception):
            PlatformFrameSource(backend).capture()

        non_png = FakeWindowsDriver(payload=b"not-a-png")
        backend = LazyWindowsReadOnlyBackend(WindowsCaptureConfig(window_title="Epic Seven"), lambda: non_png)
        with self.assertRaises(Exception):
            PlatformFrameSource(backend).capture()


class LocalRecognitionEvidenceParserTest(unittest.TestCase):
    def _parser(self, *, set_confidence=0.999, region_provider=None):
        kwargs = {
            "region_extractor": CallbackRegionExtractor(lambda frame_value, region: b"crop:" + region.name.encode("ascii")),
            "template_recognizer": FakeTemplateRecognizer(),
            "ocr_recognizer": PaddleLinesOcrRecognizer(lambda frame_value, regions: paddle_lines(set_confidence)),
            "resource_preview": {"visible": True, "materials": {}, "gold": 0},
        }
        if region_provider is not None:
            kwargs["region_provider"] = region_provider
        return LocalRecognitionEvidenceParser(
            **kwargs,
        )

    def test_binds_stable_frame_provenance_regions_and_existing_paddle_confidence_to_evidence(self):
        stable_frames = StableFrames((frame(), frame(), frame()))

        evidence = self._parser().parse(SamplingRequest("operation-001", "pre_action", 0), stable_frames)

        self.assertEqual(evidence.captured_at, "2026-07-26T10:00:00+08:00")
        self.assertEqual(evidence.page["page_signature"], frame().frame_hash)
        self.assertEqual(evidence.stability["frame_hashes"], [frame().frame_hash] * 3)
        self.assertEqual(evidence.sampler["source"], "fake-platform:fixture-window")
        self.assertEqual(evidence.sampler["viewport"], {"width": 1600, "height": 900})
        self.assertEqual(evidence.target["visible_fields"]["enhance"], 0)
        self.assertEqual(evidence.target["visible_fields"]["mainStat"], {"type": "Attack", "value": 100.0})
        self.assertEqual(len(evidence.target["visible_fields"]["substats"]), 4)
        self.assertGreaterEqual(evidence.target["field_confidence"]["set"], 0.98)

    def test_invalid_region_definition_low_ocr_confidence_and_missing_templates_fail_closed(self):
        invalid_regions = lambda: {
            "schema_version": 1,
            "template": "invalid",
            "regions": [{"name": "bad", "bounds": {"left": -0.1, "top": 0, "right": 1, "bottom": 1}}],
            "validation_errors": [],
        }
        with self.assertRaises(LocalRecognitionError):
            self._parser(region_provider=invalid_regions).parse(
                SamplingRequest("operation-001", "pre_action", 0), StableFrames((frame(), frame(), frame()))
            )
        with self.assertRaises(LocalRecognitionError):
            self._parser(set_confidence=0.97).parse(
                SamplingRequest("operation-001", "pre_action", 0), StableFrames((frame(), frame(), frame()))
            )

        class MissingTemplateRecognizer:
            def recognize(self, frame_value, regions):
                return []

        parser = LocalRecognitionEvidenceParser(
            CallbackRegionExtractor(lambda frame_value, region: b"crop"),
            MissingTemplateRecognizer(),
            PaddleLinesOcrRecognizer(lambda frame_value, regions: paddle_lines()),
        )
        with self.assertRaises(LocalRecognitionError):
            parser.parse(SamplingRequest("operation-001", "pre_action", 0), StableFrames((frame(), frame(), frame())))

    def test_platform_source_and_local_parser_bind_through_visual_sampler(self):
        driver = FakeWindowsDriver()
        backend = LazyWindowsReadOnlyBackend(
            WindowsCaptureConfig(window_title="Epic Seven", source="fake-platform"),
            lambda: driver,
            timestamp_factory=lambda: "2026-07-26T10:00:00+08:00",
        )
        sampler = VisualAdapterSampler(
            PlatformFrameSource(backend),
            self._parser(),
            collector=StableFrameCollector(),
        )

        evidence = sampler.capture(SamplingRequest("operation-001", "pre_action", 0))

        self.assertEqual(evidence.sampler["adapter"], "local_visual_platform")
        self.assertEqual(evidence.target["visible_fields"]["slot"], "Weapon")
        self.assertEqual(evidence.stability["sample_count"], 3)


if __name__ == "__main__":
    unittest.main()
