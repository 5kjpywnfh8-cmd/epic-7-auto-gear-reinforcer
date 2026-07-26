from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.e7_enhance.visual_adapter import (
    CallbackEvidenceParser,
    CallbackFrameSource,
    EvidenceParseError,
    FileBackedFrameSource,
    FrameCaptureError,
    FrameTimestampError,
    FrameViewportDriftError,
    StableFrameCollector,
    UnstableFrameError,
    VisualAdapterSampler,
    VisualFrame,
)
from src.e7_enhance.visual_runtime import SamplingRequest, VisualEvidence


def frame(payload=b"stable-frame", *, viewport=(1600, 900), captured_at="2026-07-26T10:00:00+08:00"):
    return VisualFrame.from_bytes(
        source="fixture:offline-frame",
        payload=payload,
        viewport=viewport,
        captured_at=captured_at,
    )


def evidence_for(request, stable_frames, **overrides):
    value = {
        "schema_version": "e7_enhance.visual_evidence/1.0",
        "operation_id": request.operation_id,
        "sample_id": "adapter-sample-001",
        "captured_at": stable_frames.captured_at,
        "phase": request.phase,
        "expected_node": request.expected_node,
        "page": {
            "page_type": "enhance_equipment",
            "is_unambiguous": True,
            "target_visible": True,
            "page_signature": "a" * 64,
        },
        "stability": {
            "sample_count": stable_frames.sample_count,
            "stable_count": stable_frames.stable_count,
            "poll_interval_ms": 1,
            "timeout_ms": 3,
            "frame_hashes": list(stable_frames.frame_hashes),
        },
        "anchors": [],
        "target": {},
        "resource_preview": {},
        "sampler": {"adapter": "offline_fixture", "template_set": "none", "version": "1"},
    }
    value.update(overrides)
    return VisualEvidence.from_mapping(value)


class ScriptedSource:
    def __init__(self, frames):
        self._frames = list(frames)
        self.calls = 0

    def capture(self):
        self.calls += 1
        item = self._frames.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class StableFrameCollectorTest(unittest.TestCase):
    def test_collects_three_identical_hashes_with_one_viewport_and_records_metadata(self):
        source = ScriptedSource([frame(), frame(), frame(captured_at="2026-07-26T10:00:01+08:00")])

        stable = StableFrameCollector().collect(source)

        self.assertEqual(source.calls, 3)
        self.assertEqual(stable.sample_count, 3)
        self.assertEqual(stable.stable_count, 3)
        self.assertEqual(stable.viewport, (1600, 900))
        self.assertEqual(stable.source, "fixture:offline-frame")
        self.assertEqual(len(stable.frame_hashes), 3)
        self.assertEqual(len(set(stable.frame_hashes)), 1)
        self.assertEqual(stable.captured_at, "2026-07-26T10:00:01+08:00")

    def test_changed_hash_and_viewport_drift_fail_closed_without_retry(self):
        with self.assertRaises(UnstableFrameError):
            StableFrameCollector().collect(ScriptedSource([frame(), frame(payload=b"changed"), frame()]))
        with self.assertRaises(FrameViewportDriftError):
            StableFrameCollector().collect(ScriptedSource([frame(), frame(viewport=(1601, 900)), frame()]))

    def test_source_exception_and_invalid_timestamp_fail_closed(self):
        source = ScriptedSource([frame(), OSError("fixture source unavailable"), frame()])
        with self.assertRaises(FrameCaptureError):
            StableFrameCollector().collect(source)
        self.assertEqual(source.calls, 2)

        with self.assertRaises(FrameTimestampError):
            VisualFrame.from_bytes(
                source="fixture:offline-frame",
                payload=b"stable-frame",
                viewport=(1600, 900),
                captured_at="not-a-timestamp",
            )

        z_frame = VisualFrame.from_bytes(
            source="fixture:offline-frame",
            payload=b"zulu-frame",
            viewport=(1600, 900),
            captured_at="2026-07-26T10:00:00Z",
        )
        self.assertEqual(z_frame.captured_at, "2026-07-26T10:00:00Z")

        with self.assertRaises(FrameCaptureError):
            VisualFrame.from_bytes(
                source="fixture:offline-frame",
                payload="not-bytes",
                viewport=(1600, 900),
                captured_at="2026-07-26T10:00:00Z",
            )

    def test_timestamp_regression_fails_closed(self):
        with self.assertRaises(FrameTimestampError):
            StableFrameCollector().collect(
                ScriptedSource(
                    [
                        frame(captured_at="2026-07-26T10:00:01+08:00"),
                        frame(captured_at="2026-07-26T10:00:00+08:00"),
                        frame(captured_at="2026-07-26T10:00:02+08:00"),
                    ]
                )
            )


class OfflineFrameSourceTest(unittest.TestCase):
    def test_callback_and_file_backed_sources_produce_hashed_offline_frames(self):
        callback_source = CallbackFrameSource(lambda: frame())
        self.assertEqual(callback_source.capture().source, "fixture:offline-frame")

        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            path.write_bytes(b"recorded-offline-frame")
            file_source = FileBackedFrameSource(
                path,
                viewport=(1600, 900),
                captured_at="2026-07-26T10:00:00+08:00",
            )
            captured = file_source.capture()

        self.assertEqual(captured.payload, b"recorded-offline-frame")
        self.assertEqual(captured.source, "file:fixture.bin")


class VisualAdapterSamplerTest(unittest.TestCase):
    def test_stable_frames_are_bound_to_visual_sampler_capture_seam(self):
        request = SamplingRequest("operation-001", "pre_action", 0)
        source = ScriptedSource([frame(), frame(), frame()])
        parser = CallbackEvidenceParser(evidence_for)

        evidence = VisualAdapterSampler(source, parser).capture(request)

        self.assertEqual(evidence.operation_id, "operation-001")
        self.assertEqual(evidence.stability["sample_count"], 3)
        self.assertEqual(evidence.stability["frame_hashes"], [frame().frame_hash] * 3)

    def test_parser_exception_or_frame_record_mismatch_fails_closed(self):
        request = SamplingRequest("operation-001", "pre_action", 0)
        parser_error = CallbackEvidenceParser(lambda request, frames: (_ for _ in ()).throw(ValueError("bad parse")))
        with self.assertRaises(EvidenceParseError):
            VisualAdapterSampler(ScriptedSource([frame(), frame(), frame()]), parser_error).capture(request)

        def mismatched_evidence(request, stable_frames):
            return evidence_for(request, stable_frames, captured_at="2026-07-26T10:00:02+08:00")

        with self.assertRaises(EvidenceParseError):
            VisualAdapterSampler(
                ScriptedSource([frame(), frame(), frame()]),
                CallbackEvidenceParser(mismatched_evidence),
            ).capture(request)


if __name__ == "__main__":
    unittest.main()
