from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zlib

from src.e7_enhance.visual_adapter import CallbackFrameSource, VisualAdapterSampler, VisualFrame
from src.e7_enhance.visual_adb_recognition import AdbLocalRecognitionEvidenceParser
from src.e7_enhance.visual_platform import LocalRegion, RegionSample
from src.e7_enhance.visual_set_template_matcher import LocalSetIconTemplateRecognizer
from src.e7_enhance.visual_templates import SetIconTemplate
from src.e7_enhance.visual_runtime import ExpectedVisualState, SamplingRequest, VisualEvidenceGate


def png(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    rows = b"".join(b"\x00" + pixels[offset:offset + width * 3] for offset in range(0, len(pixels), width * 3))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00") + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def patterned_png(width: int = 8, height: int = 8) -> bytes:
    return png(width, height, patterned_pixels(width, height))


def patterned_pixels(width: int, height: int) -> bytes:
    return bytes(
        value
        for y in range(height)
        for x in range(width)
        for value in (
            (255 if ((x % 8) + (y % 8)) % 2 else 32),
            (240 if (x % 8) % 3 else 64),
            (220 if (y % 8) % 3 else 96),
        )
    )


def scaled_pixels(width: int, height: int, scale: int) -> bytes:
    return bytes(
        value
        for y in range(height * scale)
        for x in range(width * scale)
        for value in (
            (255 if ((x // scale) + (y // scale)) % 2 else 32),
            (240 if (x // scale) % 3 else 64),
            (220 if (y // scale) % 3 else 96),
        )
    )


def frame() -> VisualFrame:
    return VisualFrame.from_bytes(
        source="offline-fixture",
        payload=png(16, 12, bytes((1, 1, 1)) * 16 * 12),
        viewport=(16, 12),
        captured_at="2026-07-26T10:00:00+08:00",
    )


def sample(payload: bytes, name: str = "set_anchor", bounds: tuple[int, int, int, int] = (0, 0, 8, 8)) -> RegionSample:
    return RegionSample(LocalRegion(name, {}, bounds), payload)


class LocalSetIconTemplateRecognizerTest(unittest.TestCase):
    def _template(self, directory: Path, identifier: str, payload: bytes) -> SetIconTemplate:
        path = directory / f"set{identifier}.png"
        path.write_bytes(payload)
        return SetIconTemplate(identifier, path, "offline://fixture", "0" * 40, "0" * 64, (8, 8), len(payload))

    def test_matches_unique_set_anchor_with_auditable_candidate_evidence(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            payload = patterned_png()
            template = self._template(Path(directory), "hit", payload)
            recognizer = LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template})

            anchors = recognizer.recognize(frame(), {"set_anchor": sample(payload)})

        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["name"], "set_icon:hit")
        self.assertEqual(anchors[0]["candidate_id"], "hit")
        self.assertEqual(anchors[0]["score"], 1.0)
        self.assertEqual(anchors[0]["threshold"], 0.98)
        self.assertGreater(anchors[0]["bright_ratio"], 0)

    def test_uses_set_region_when_set_anchor_is_not_available(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            payload = patterned_png()
            template = self._template(Path(directory), "hit", payload)
            recognizer = LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template})

            anchors = recognizer.recognize(frame(), {"set": sample(payload, name="set")})

        self.assertEqual(anchors[0]["candidate_id"], "hit")

    def test_nearest_neighbor_scale_and_local_anchor_are_auditable(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            template_payload = patterned_png()
            template = self._template(Path(directory), "hit", template_payload)
            pixels = bytearray(bytes((1, 1, 1)) * 20 * 18)
            icon = scaled_pixels(8, 8, 2)
            for row in range(16):
                destination = ((row + 1) * 20 + 2) * 3
                pixels[destination:destination + 16 * 3] = icon[row * 16 * 3:(row + 1) * 16 * 3]
            recognizer = LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template})

            anchors = recognizer.recognize(
                VisualFrame.from_bytes(
                    source="offline-fixture",
                    payload=png(20, 18, bytes(pixels)),
                    viewport=(20, 18),
                    captured_at="2026-07-26T10:00:00+08:00",
                ),
                {"set_anchor": sample(png(20, 18, bytes(pixels)), bounds=(0, 0, 20, 18))},
            )

        self.assertEqual(len(anchors), 1)
        self.assertEqual(anchors[0]["template_scale"], 2.0)
        self.assertEqual(anchors[0]["anchor_bounds"], {"left": 2, "top": 1, "right": 18, "bottom": 17})
        self.assertEqual(anchors[0]["preprocess"], "rgba_nearest_neighbor")

    def test_missing_templates_invalid_png_viewport_drift_and_low_score_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            payload = patterned_png()
            template = self._template(Path(directory), "hit", payload)
            blank = png(8, 8, bytes((0, 0, 0)) * 8 * 8)
            cases = (
                (LocalSetIconTemplateRecognizer(template_loader=lambda: {}), {"set_anchor": sample(payload)}),
                (LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template}), {"set_anchor": sample(b"not-a-png")}),
                (LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template}), {"set_anchor": sample(payload, bounds=(0, 0, 7, 8))}),
                (LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template}), {"set_anchor": sample(blank)}),
            )
            for recognizer, regions in cases:
                with self.subTest(regions=tuple(regions)):
                    self.assertEqual(recognizer.recognize(frame(), regions), [])

    def test_tied_best_template_candidates_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            payload = patterned_png()
            hit = self._template(Path(directory), "hit", payload)
            speed = self._template(Path(directory), "speed", payload)
            recognizer = LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": hit, "speed": speed})

            self.assertEqual(recognizer.recognize(frame(), {"set_anchor": sample(payload)}), [])

    def test_same_template_at_multiple_best_positions_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            template_payload = patterned_png()
            template = self._template(Path(directory), "hit", template_payload)
            recognizer = LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template})
            repeated = png(16, 8, patterned_pixels(16, 8))

            self.assertEqual(
                recognizer.recognize(
                    VisualFrame.from_bytes(
                        source="offline-fixture",
                        payload=png(16, 8, bytes((1, 1, 1)) * 16 * 8),
                        viewport=(16, 8),
                        captured_at="2026-07-26T10:00:00+08:00",
                    ),
                    {"set_anchor": sample(repeated, bounds=(0, 0, 16, 8))},
                ),
                [],
            )


class _MatcherWithPageAnchor:
    def __init__(self, matcher: LocalSetIconTemplateRecognizer) -> None:
        self._matcher = matcher

    def recognize(self, frame, regions):
        return [
            *self._matcher.recognize(frame, regions),
            {"name": "detail_panel", "score": 0.99, "threshold": 0.98, "bright_ratio": 0.5},
        ]


class _FixturePaddleLines:
    def read_lines(self, frame, regions):
        return [
            {"text": "传说武器", "confidence": 0.999},
            {"text": "85", "confidence": 0.999},
            {"text": "攻击力", "confidence": 0.999}, {"text": "100", "confidence": 0.999},
            {"text": "生命值", "confidence": 0.999}, {"text": "8%", "confidence": 0.999},
            {"text": "攻击力", "confidence": 0.999}, {"text": "4%", "confidence": 0.999},
            {"text": "暴击伤害", "confidence": 0.999}, {"text": "5%", "confidence": 0.999},
            {"text": "生命值", "confidence": 0.999}, {"text": "159", "confidence": 0.999},
            {"text": "装备分数", "confidence": 0.999}, {"text": "25", "confidence": 0.999},
            {"text": "速度套装(0/4)", "confidence": 0.999},
            {"text": "exp0/525", "confidence": 0.999, "region": "enhance"},
        ]


class LocalSetIconTemplateMatcherPipelineTest(unittest.TestCase):
    def test_full_offline_pipeline_preserves_visual_only_unverified_contract(self):
        with tempfile.TemporaryDirectory(prefix="e7-set-matcher-") as directory:
            template_payload = patterned_png()
            template = LocalSetIconTemplateRecognizerTest()._template(Path(directory), "hit", template_payload)
            pixels = bytearray(bytes((1, 1, 1)) * 16 * 12)
            icon = patterned_pixels(8, 8)
            for row in range(8):
                pixels[row * 16 * 3:row * 16 * 3 + 8 * 3] = icon[row * 8 * 3:(row + 1) * 8 * 3]
            visual_frame = VisualFrame.from_bytes(
                source="adb_screencap:offline-fixture",
                payload=png(16, 12, bytes(pixels)),
                viewport=(16, 12),
                captured_at="2026-07-26T10:00:00+08:00",
            )
            matcher = LocalSetIconTemplateRecognizer(template_loader=lambda: {"hit": template})
            manifest = {
                "schema_version": 1,
                "template": "offline_fixture",
                "regions": [
                    {"name": "set_anchor", "bounds": {"left": 0, "top": 0, "right": 0.5, "bottom": 2 / 3}},
                    {"name": "detail_panel", "bounds": {"left": 0.5, "top": 0, "right": 1, "bottom": 1}},
                    {"name": "enhance", "bounds": {"left": 0.5, "top": 0, "right": 1, "bottom": 0.5}},
                ],
                "validation_errors": [],
            }
            parser = AdbLocalRecognitionEvidenceParser(
                _MatcherWithPageAnchor(matcher),
                _FixturePaddleLines(),
                region_provider=lambda: manifest,
                resource_preview={
                    "visible": True,
                    "materials": {"powder": 2, "lower_enhance_stone": 1, "upper_enhance_stone": 0},
                    "gold": 17600,
                },
            )
            sampler = VisualAdapterSampler(CallbackFrameSource(lambda: visual_frame), parser)

            evidence = sampler.capture(SamplingRequest("operation-001", "pre_action", 0))
            gate = VisualEvidenceGate().evaluate(
                evidence, ExpectedVisualState(0, "pre_action", operation_id="operation-001")
            )

        self.assertEqual(gate.status, "ready")
        self.assertEqual(gate.mode, "visual_only")
        self.assertEqual(gate.verification, "unverified")


if __name__ == "__main__":
    unittest.main()
