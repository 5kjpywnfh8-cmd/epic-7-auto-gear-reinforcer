"""Read-only ADB screenshot source for the visual evidence pipeline.

This module deliberately exposes no ADB input, navigation, package, network,
or data-reading operation.  It only discovers one attached device and obtains
in-memory PNG bytes from ``exec-out screencap -p``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Callable, Protocol
import zlib

from .visual_adapter import PlatformWindow


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class AdbReadOnlyError(RuntimeError):
    """Base error for a read-only ADB precondition that must stop."""


class AdbDeviceDiscoveryError(AdbReadOnlyError):
    """No unique automatically discovered ADB device is available."""


class AdbFrameError(AdbReadOnlyError):
    """A screenshot is invalid, changed unexpectedly, or cannot be inspected."""


class AdbReadOnlyTransport(Protocol):
    """The only ADB operations permitted to the screenshot frame source."""

    def devices_long(self) -> str:
        ...

    def exec_out_screencap_png(self, serial: str) -> bytes:
        ...


class AdbCommandTransport:
    """Explicit subprocess transport containing only the two read-only commands."""

    def __init__(self, adb_path: str | Path, *, timeout_seconds: int = 20) -> None:
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be a positive integer")
        self._adb_path = str(Path(adb_path))
        self._timeout_seconds = timeout_seconds

    def devices_long(self) -> str:
        completed = self._run("devices", "-l")
        try:
            return completed.stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AdbDeviceDiscoveryError("ADB device listing is not UTF-8") from exc

    def exec_out_screencap_png(self, serial: str) -> bytes:
        if not isinstance(serial, str) or not serial.strip():
            raise AdbDeviceDiscoveryError("ADB serial is invalid")
        if _is_forbidden_network_serial(serial):
            raise AdbDeviceDiscoveryError("explicit 192.168.x.x:5555 serials are forbidden")
        return self._run("-s", serial, "exec-out", "screencap", "-p").stdout

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        try:
            completed = subprocess.run(
                [self._adb_path, *arguments],
                check=False,
                capture_output=True,
                timeout=self._timeout_seconds,
            )
        except OSError as exc:
            raise AdbReadOnlyError("ADB read-only command could not start") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbReadOnlyError("ADB read-only command timed out") from exc
        if completed.returncode != 0:
            raise AdbReadOnlyError("ADB read-only command failed")
        return completed


def discover_single_device(transport: AdbReadOnlyTransport) -> str:
    """Accept exactly one automatically discovered device in state ``device``."""

    try:
        listing = transport.devices_long()
    except AdbReadOnlyError:
        raise
    except Exception as exc:
        raise AdbDeviceDiscoveryError("ADB device discovery failed") from exc
    if not isinstance(listing, str):
        raise AdbDeviceDiscoveryError("ADB device listing is invalid")
    lines = [line.strip() for line in listing.splitlines()]
    if not lines or lines[0] != "List of devices attached":
        raise AdbDeviceDiscoveryError("ADB device listing header is invalid")
    devices: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line:
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            raise AdbDeviceDiscoveryError("ADB device listing row is invalid")
        devices.append((parts[0], parts[1]))
    if len(devices) != 1 or devices[0][1] != "device":
        raise AdbDeviceDiscoveryError("ADB requires exactly one device-state device")
    if _is_forbidden_network_serial(devices[0][0]):
        raise AdbDeviceDiscoveryError("explicit 192.168.x.x:5555 serials are forbidden")
    return devices[0][0]


class AdbScreencapBackend:
    """Adapt a unique ADB device into the existing ``PlatformFrameSource`` seam."""

    def __init__(
        self,
        transport: AdbReadOnlyTransport,
        *,
        source: str = "adb_screencap",
        content_validator: Callable[[bytes, tuple[int, int]], bool] | None = None,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(source, str) or not source.strip():
            raise ValueError("ADB frame source label is required")
        if content_validator is not None and not callable(content_validator):
            raise TypeError("ADB PNG content validator must be callable")
        if timestamp_factory is not None and not callable(timestamp_factory):
            raise TypeError("timestamp_factory must be callable")
        self._transport = transport
        self._source = source
        self._content_validator = content_validator
        self._timestamp_factory = timestamp_factory or _utc_timestamp
        self._selected: PlatformWindow | None = None
        self._pending: tuple[str, bytes, tuple[int, int]] | None = None
        self._expected_viewport: tuple[int, int] | None = None

    def locate_window(self) -> PlatformWindow:
        serial = discover_single_device(self._transport)
        window = PlatformWindow(serial, self._source)
        if self._selected is not None and self._selected != window:
            raise AdbDeviceDiscoveryError("ADB device identity changed during capture")
        self._selected = window
        return window

    def viewport_size(self, window: PlatformWindow) -> tuple[int, int]:
        self._validate_window(window)
        if self._pending is not None:
            raise AdbFrameError("ADB screenshot capture is already pending")
        payload = self._capture_png(window.identifier)
        viewport = parse_png_viewport(payload)
        self._validate_content(payload, viewport)
        if self._expected_viewport is None:
            self._expected_viewport = viewport
        elif viewport != self._expected_viewport:
            raise AdbFrameError("ADB screenshot viewport or rotation changed")
        self._pending = (window.identifier, payload, viewport)
        return viewport

    def capture_frame(self, window: PlatformWindow) -> bytes:
        self._validate_window(window)
        if self._pending is None or self._pending[0] != window.identifier:
            raise AdbFrameError("ADB screenshot must be sampled before frame delivery")
        _, payload, _ = self._pending
        self._pending = None
        return payload

    def captured_at(self) -> str:
        try:
            value = self._timestamp_factory()
        except Exception as exc:
            raise AdbFrameError("ADB screenshot timestamp failed") from exc
        if not isinstance(value, str) or not value.strip():
            raise AdbFrameError("ADB screenshot timestamp is invalid")
        return value

    def _validate_window(self, window: PlatformWindow) -> None:
        if not isinstance(window, PlatformWindow) or self._selected != window:
            raise AdbDeviceDiscoveryError("ADB frame source identity is invalid")

    def _capture_png(self, serial: str) -> bytes:
        try:
            payload = self._transport.exec_out_screencap_png(serial)
        except AdbReadOnlyError:
            raise
        except Exception as exc:
            raise AdbFrameError("ADB screencap command failed") from exc
        if not isinstance(payload, bytes) or not payload:
            raise AdbFrameError("ADB screencap returned no PNG bytes")
        return payload

    def _validate_content(self, payload: bytes, viewport: tuple[int, int]) -> None:
        if not validate_png_content(payload, viewport):
            raise AdbFrameError("ADB screenshot content is rejected")
        if self._content_validator is None:
            return
        try:
            acceptable = self._content_validator(payload, viewport)
        except Exception as exc:
            raise AdbFrameError("ADB screenshot content validation failed") from exc
        if acceptable is not True:
            raise AdbFrameError("ADB screenshot content is rejected")


def parse_png_viewport(payload: bytes) -> tuple[int, int]:
    """Validate PNG chunk framing and return the IHDR pixel dimensions."""

    if not isinstance(payload, bytes) or not payload.startswith(PNG_SIGNATURE):
        raise AdbFrameError("ADB screencap is not a PNG")
    offset = len(PNG_SIGNATURE)
    chunks: list[bytes] = []
    viewport: tuple[int, int] | None = None
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise AdbFrameError("ADB PNG is truncated")
        length = int.from_bytes(payload[offset:offset + 4], "big")
        chunk_type = payload[offset + 4:offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if data_end > len(payload) or crc_end > len(payload):
            raise AdbFrameError("ADB PNG chunk is truncated")
        data = payload[data_start:data_end]
        expected_crc = int.from_bytes(payload[data_end:crc_end], "big")
        if zlib.crc32(chunk_type + data) & 0xFFFFFFFF != expected_crc:
            raise AdbFrameError("ADB PNG chunk checksum is invalid")
        chunks.append(chunk_type)
        if chunk_type == b"IHDR":
            if viewport is not None or length != 13:
                raise AdbFrameError("ADB PNG IHDR is invalid")
            width = int.from_bytes(data[0:4], "big")
            height = int.from_bytes(data[4:8], "big")
            if width <= 0 or height <= 0:
                raise AdbFrameError("ADB PNG viewport is invalid")
            viewport = (width, height)
        if chunk_type == b"IEND":
            if length != 0 or crc_end != len(payload):
                raise AdbFrameError("ADB PNG end marker is invalid")
            break
        offset = crc_end
    if viewport is None or chunks[:1] != [b"IHDR"] or b"IDAT" not in chunks or chunks[-1:] != [b"IEND"]:
        raise AdbFrameError("ADB PNG structure is invalid")
    return viewport


def validate_png_content(payload: bytes, viewport: tuple[int, int]) -> bool:
    """Decode an 8-bit non-interlaced screenshot and reject an all-black frame."""

    if parse_png_viewport(payload) != viewport:
        raise AdbFrameError("ADB PNG viewport does not match decoded content")
    ihdr: bytes | None = None
    idat: list[bytes] = []
    for chunk_type, data in _png_chunks(payload):
        if chunk_type == b"IHDR":
            ihdr = data
        elif chunk_type == b"IDAT":
            idat.append(data)
    if ihdr is None or len(ihdr) != 13:
        raise AdbFrameError("ADB PNG IHDR is unavailable")
    width, height = viewport
    bit_depth = ihdr[8]
    color_type = ihdr[9]
    if bit_depth != 8 or color_type not in (0, 2, 4, 6) or ihdr[10:] != b"\x00\x00\x00":
        raise AdbFrameError("ADB PNG format is unsupported")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    row_bytes = width * channels
    if row_bytes <= 0 or height <= 0 or width * height > 40_000_000:
        raise AdbFrameError("ADB PNG dimensions are unsafe")
    try:
        decoded = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise AdbFrameError("ADB PNG pixel stream is invalid") from exc
    if len(decoded) != (row_bytes + 1) * height:
        raise AdbFrameError("ADB PNG pixel stream length is invalid")
    previous = bytearray(row_bytes)
    visible_pixels = 0
    offset = 0
    for _ in range(height):
        filter_type = decoded[offset]
        encoded = decoded[offset + 1:offset + 1 + row_bytes]
        offset += row_bytes + 1
        row = bytearray(row_bytes)
        for index, value in enumerate(encoded):
            left = row[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = _paeth(left, up, upper_left)
            else:
                raise AdbFrameError("ADB PNG row filter is invalid")
            row[index] = (value + predictor) & 0xFF
        if color_type in (0, 4):
            visible_pixels += sum(1 for index in range(0, row_bytes, channels) if row[index] != 0)
        else:
            visible_pixels += sum(
                1
                for index in range(0, row_bytes, channels)
                if row[index] != 0 or row[index + 1] != 0 or row[index + 2] != 0
            )
        previous = row
    return visible_pixels >= max(1, width * height // 1000)


def _png_chunks(payload: bytes):
    offset = len(PNG_SIGNATURE)
    while offset < len(payload):
        length = int.from_bytes(payload[offset:offset + 4], "big")
        chunk_type = payload[offset + 4:offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(payload):
            raise AdbFrameError("ADB PNG chunk is truncated")
        yield chunk_type, payload[data_start:data_end]
        if chunk_type == b"IEND":
            return
        offset = crc_end


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def _is_forbidden_network_serial(serial: str) -> bool:
    prefix, separator, port = serial.partition(":")
    if not separator or port != "5555":
        return False
    octets = prefix.split(".")
    return len(octets) == 4 and octets[0] == "192" and all(octet.isdigit() for octet in octets[1:])


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
