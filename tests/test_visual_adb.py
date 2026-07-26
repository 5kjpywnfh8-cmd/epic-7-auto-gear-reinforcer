from __future__ import annotations

import unittest
from unittest.mock import patch
import subprocess
import zlib

from src.e7_enhance.visual_adapter import (
    CallbackEvidenceParser,
    FrameCaptureError,
    FrameTimestampError,
    PlatformFrameSource,
    StableFrameCollector,
    UnstableFrameError,
    VisualAdapterSampler,
)
from src.e7_enhance.visual_adb import (
    AdbDeviceDiscoveryError,
    AdbFrameError,
    AdbCommandTransport,
    AdbScreencapBackend,
    discover_single_device,
    parse_png_viewport,
    validate_png_content,
)
from src.e7_enhance.visual_runtime import SamplingRequest, VisualEvidence


def png(width=1600, height=900, payload=b"fixture"):
    def chunk(kind, data):
        return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")

    seed = payload[0] if payload else 1
    row = b"\x00" + bytes((seed, seed, seed)) * width
    pixels = zlib.compress(row * height)
    return b"\x89PNG\r\n\x1a\n" + chunk(
        b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    ) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


class FakeAdbTransport:
    def __init__(self, devices=None, frames=()):
        self.devices = devices or "List of devices attached\nemulator-5554 device product:MuMu\n"
        self.frames = list(frames)
        self.calls = []
        self.error = None

    def devices_long(self):
        self.calls.append("devices -l")
        if self.error:
            raise self.error
        return self.devices

    def exec_out_screencap_png(self, serial):
        self.calls.append(("exec-out screencap -p", serial))
        if self.error:
            raise self.error
        return self.frames.pop(0)


def evidence_for(request, frames):
    return VisualEvidence.from_mapping({
        "schema_version": "e7_enhance.visual_evidence/1.0",
        "operation_id": request.operation_id,
        "sample_id": "adb-sample-001",
        "captured_at": frames.captured_at,
        "phase": request.phase,
        "expected_node": request.expected_node,
        "page": {"page_type": "enhance_equipment", "is_unambiguous": True, "target_visible": True, "page_signature": "a" * 64},
        "stability": {"sample_count": frames.sample_count, "stable_count": frames.stable_count, "poll_interval_ms": 1, "timeout_ms": 3, "frame_hashes": list(frames.frame_hashes)},
        "anchors": [],
        "target": {},
        "resource_preview": {},
        "sampler": {"adapter": "fake_adb", "template_set": "none", "version": "1"},
    })


class AdbDiscoveryTest(unittest.TestCase):
    def test_only_one_automatically_discovered_device_is_accepted(self):
        transport = FakeAdbTransport()

        serial = discover_single_device(transport)

        self.assertEqual(serial, "emulator-5554")
        self.assertEqual(transport.calls, ["devices -l"])

    def test_unavailable_multiple_and_non_device_states_fail_closed(self):
        cases = (
            "List of devices attached\n",
            "List of devices attached\none offline\n",
            "List of devices attached\none device\ntwo device\n",
            "not an adb device listing",
        )
        for listing in cases:
            with self.subTest(listing=listing):
                with self.assertRaises(AdbDeviceDiscoveryError):
                    discover_single_device(FakeAdbTransport(devices=listing))

        with self.assertRaises(AdbDeviceDiscoveryError):
            discover_single_device(FakeAdbTransport(devices="List of devices attached\n192.168.1.10:5555 device\n"))

    def test_subprocess_transport_can_construct_only_readonly_device_and_screencap_commands(self):
        command_results = [
            subprocess.CompletedProcess([], 0, b"List of devices attached\nemulator-5554 device\n", b""),
            subprocess.CompletedProcess([], 0, png(), b""),
        ]
        with patch("src.e7_enhance.visual_adb.subprocess.run", side_effect=command_results) as run:
            transport = AdbCommandTransport("C:/fixture/adb.exe")
            self.assertEqual(transport.devices_long(), "List of devices attached\nemulator-5554 device\n")
            self.assertEqual(transport.exec_out_screencap_png("emulator-5554"), png())

        self.assertEqual(run.call_args_list[0].args[0], ["C:\\fixture\\adb.exe", "devices", "-l"])
        self.assertEqual(run.call_args_list[1].args[0], ["C:\\fixture\\adb.exe", "-s", "emulator-5554", "exec-out", "screencap", "-p"])


class AdbScreencapBackendTest(unittest.TestCase):
    def test_only_readonly_screencap_png_is_mapped_to_platform_frame_source(self):
        transport = FakeAdbTransport(frames=(png(),))
        backend = AdbScreencapBackend(
            transport,
            content_validator=lambda payload, viewport: True,
            timestamp_factory=lambda: "2026-07-26T10:00:00+08:00",
        )

        frame = PlatformFrameSource(backend).capture()

        self.assertEqual(frame.viewport, (1600, 900))
        self.assertEqual(frame.source, "adb_screencap:emulator-5554")
        self.assertEqual(transport.calls, ["devices -l", ("exec-out screencap -p", "emulator-5554")])

    def test_invalid_png_black_content_transport_error_and_rotation_fail_closed(self):
        invalid = AdbScreencapBackend(FakeAdbTransport(frames=(b"not-png",)), content_validator=lambda payload, viewport: True)
        with self.assertRaises(FrameCaptureError):
            PlatformFrameSource(invalid).capture()
        with self.assertRaises(AdbFrameError):
            parse_png_viewport(png()[:-1])

        black_payload = png(payload=b"\x00")
        self.assertFalse(validate_png_content(black_payload, (1600, 900)))

        black = AdbScreencapBackend(FakeAdbTransport(frames=(png(),)), content_validator=lambda payload, viewport: False)
        with self.assertRaises(FrameCaptureError):
            PlatformFrameSource(black).capture()

        failed_transport = FakeAdbTransport(frames=(png(),))
        failed_transport.error = OSError("offline failure")
        with self.assertRaises(FrameCaptureError):
            PlatformFrameSource(AdbScreencapBackend(failed_transport, content_validator=lambda payload, viewport: True)).capture()

        rotating = AdbScreencapBackend(
            FakeAdbTransport(frames=(png(1600, 900), png(900, 1600))),
            content_validator=lambda payload, viewport: True,
        )
        source = PlatformFrameSource(rotating)
        source.capture()
        with self.assertRaises(FrameCaptureError):
            source.capture()

        bad_timestamp = AdbScreencapBackend(
            FakeAdbTransport(frames=(png(),)),
            content_validator=lambda payload, viewport: True,
            timestamp_factory=lambda: "invalid",
        )
        with self.assertRaises(FrameTimestampError):
            PlatformFrameSource(bad_timestamp).capture()

    def test_stable_frame_collector_and_visual_adapter_sampler_accept_only_stable_adb_frames(self):
        transport = FakeAdbTransport(frames=(png(), png(), png()))
        source = PlatformFrameSource(AdbScreencapBackend(
            transport,
            content_validator=lambda payload, viewport: True,
            timestamp_factory=lambda: "2026-07-26T10:00:00+08:00",
        ))
        sampler = VisualAdapterSampler(source, CallbackEvidenceParser(evidence_for), collector=StableFrameCollector())

        evidence = sampler.capture(SamplingRequest("operation-001", "pre_action", 0))

        self.assertEqual(evidence.stability["sample_count"], 3)
        self.assertEqual(len(set(evidence.stability["frame_hashes"])), 1)

        unstable = PlatformFrameSource(AdbScreencapBackend(
            FakeAdbTransport(frames=(png(payload=b"one"), png(payload=b"two"), png(payload=b"three"))),
            content_validator=lambda payload, viewport: True,
        ))
        with self.assertRaises(UnstableFrameError):
            StableFrameCollector().collect(unstable)


if __name__ == "__main__":
    unittest.main()
