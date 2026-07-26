"""Offline ADB-frame local recognition adapters.

This module consumes an already captured :class:`VisualFrame`.  It has no ADB
transport, device discovery, OCR-engine, click, or persistence capability.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Protocol
import zlib

from .ocr_paddle import parse_backpack_enhance_lines
from .visual_adb import PNG_SIGNATURE, parse_png_viewport
from .visual_adapter import StableFrames, VisualFrame
from .visual_platform import (
    LocalRecognitionError,
    LocalRecognitionEvidenceParser,
    LocalRegion,
    LocalTemplateRecognizer,
    RegionSample,
)
from .visual_runtime import SamplingRequest, VisualEvidence


class PngRegionRecognitionError(LocalRecognitionError):
    """A PNG payload or requested local crop cannot be safely interpreted."""


class PaddleOcrLineSource(Protocol):
    """Provides one already-read PaddleOCR line collection for local crops."""

    def read_lines(
        self, frame: VisualFrame, regions: Mapping[str, RegionSample]
    ) -> list[dict[str, Any]]:
        ...


class InMemoryPngRegionExtractor:
    """Decode and crop a normalized region wholly in process memory."""

    def extract(self, frame: VisualFrame, region: LocalRegion) -> bytes:
        if not isinstance(frame, VisualFrame) or not isinstance(region, LocalRegion):
            raise PngRegionRecognitionError("visual frame and local region are required")
        decoded = _decode_png(frame.payload)
        if (decoded.width, decoded.height) != frame.viewport:
            raise PngRegionRecognitionError("PNG viewport does not match visual frame")
        left, top, right, bottom = region.pixel_bounds
        if not (
            0 <= left < right <= decoded.width
            and 0 <= top < bottom <= decoded.height
        ):
            raise PngRegionRecognitionError("local region is outside PNG viewport")
        return _encode_png(_crop(decoded, left, top, right, bottom))


class PaddleLineSourceRecognizer:
    """Bind a single injected OCR line read to the existing Paddle parser."""

    def __init__(self, line_source: PaddleOcrLineSource) -> None:
        if not hasattr(line_source, "read_lines") or not callable(line_source.read_lines):
            raise TypeError("PaddleOCR line source must provide read_lines")
        self._line_source = line_source

    def recognize(self, frame: VisualFrame, regions: Mapping[str, RegionSample]) -> Mapping[str, Any]:
        if "enhance" not in regions or not isinstance(regions["enhance"], RegionSample):
            raise LocalRecognitionError("PaddleOCR enhance-local region is unavailable")
        try:
            lines = self._line_source.read_lines(frame, regions)
        except Exception as exc:
            raise LocalRecognitionError("PaddleOCR line source failed") from exc
        if not isinstance(lines, list) or any(not isinstance(line, dict) for line in lines):
            raise LocalRecognitionError("PaddleOCR line source is invalid")
        # The visual runtime never requests a second OCR pass.  Retry-marked
        # input would make the parser choose a replacement line implicitly.
        if any("retry_for" in line or "local_retry" in line for line in lines):
            raise LocalRecognitionError("PaddleOCR retry evidence is forbidden")
        _reject_conflicting_scalar_fields(lines)
        return parse_backpack_enhance_lines(lines)


class AdbLocalRecognitionEvidenceParser:
    """A VisualEvidence parser for read-only ADB PNG stable frames."""

    def __init__(
        self,
        template_recognizer: LocalTemplateRecognizer,
        line_source: PaddleOcrLineSource,
        *,
        region_provider=None,
        resource_preview: Mapping[str, Any] | None = None,
    ) -> None:
        parser_kwargs: dict[str, Any] = {"resource_preview": resource_preview}
        if region_provider is not None:
            parser_kwargs["region_provider"] = region_provider
        self._delegate = LocalRecognitionEvidenceParser(
            InMemoryPngRegionExtractor(),
            template_recognizer,
            PaddleLineSourceRecognizer(line_source),
            **parser_kwargs,
        )

    def parse(self, request: SamplingRequest, frames: StableFrames) -> VisualEvidence:
        if not isinstance(frames, StableFrames) or not frames.source.startswith("adb_screencap:"):
            raise LocalRecognitionError("ADB local recognition requires stable ADB frames")
        evidence = self._delegate.parse(request, frames)
        sampler = dict(evidence.sampler)
        sampler["adapter"] = "adb_local_visual_recognition"
        sampler["frame_provenance"] = {
            "source": frames.source,
            "viewport": {"width": frames.viewport[0], "height": frames.viewport[1]},
            "frame_hashes": list(frames.frame_hashes),
        }
        return replace(evidence, sampler=sampler)


class _DecodedPng:
    def __init__(self, width: int, height: int, color_type: int, rows: tuple[bytes, ...]) -> None:
        self.width = width
        self.height = height
        self.color_type = color_type
        self.rows = rows

    @property
    def channels(self) -> int:
        return {0: 1, 2: 3, 4: 2, 6: 4}[self.color_type]


def _decode_png(payload: bytes) -> _DecodedPng:
    try:
        viewport = parse_png_viewport(payload)
    except Exception as exc:
        raise PngRegionRecognitionError("PNG decode failed") from exc
    ihdr: bytes | None = None
    idat: list[bytes] = []
    for kind, data in _png_chunks(payload):
        if kind == b"IHDR":
            ihdr = data
        elif kind == b"IDAT":
            idat.append(data)
    if ihdr is None or len(ihdr) != 13:
        raise PngRegionRecognitionError("PNG header is unavailable")
    bit_depth, color_type, compression, filter_method, interlace = ihdr[8:]
    if bit_depth != 8 or color_type not in (0, 2, 4, 6) or (compression, filter_method, interlace) != (0, 0, 0):
        raise PngRegionRecognitionError("PNG format is unsupported")
    width, height = viewport
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
    row_bytes = width * channels
    if width * height > 40_000_000:
        raise PngRegionRecognitionError("PNG dimensions are unsafe")
    try:
        encoded = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise PngRegionRecognitionError("PNG pixel stream is invalid") from exc
    if len(encoded) != (row_bytes + 1) * height:
        raise PngRegionRecognitionError("PNG pixel stream length is invalid")
    rows: list[bytes] = []
    previous = bytearray(row_bytes)
    offset = 0
    for _ in range(height):
        filter_type = encoded[offset]
        source = encoded[offset + 1:offset + row_bytes + 1]
        offset += row_bytes + 1
        row = bytearray(row_bytes)
        for index, value in enumerate(source):
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
                raise PngRegionRecognitionError("PNG row filter is unsupported")
            row[index] = (value + predictor) & 0xFF
        rows.append(bytes(row))
        previous = row
    return _DecodedPng(width, height, color_type, tuple(rows))


def _crop(decoded: _DecodedPng, left: int, top: int, right: int, bottom: int) -> _DecodedPng:
    channels = decoded.channels
    return _DecodedPng(
        right - left,
        bottom - top,
        decoded.color_type,
        tuple(row[left * channels:right * channels] for row in decoded.rows[top:bottom]),
    )


def _encode_png(decoded: _DecodedPng) -> bytes:
    header = (
        decoded.width.to_bytes(4, "big")
        + decoded.height.to_bytes(4, "big")
        + bytes((8, decoded.color_type, 0, 0, 0))
    )
    pixels = zlib.compress(b"".join(b"\x00" + row for row in decoded.rows))
    return PNG_SIGNATURE + _png_chunk(b"IHDR", header) + _png_chunk(b"IDAT", pixels) + _png_chunk(b"IEND", b"")


def _png_chunks(payload: bytes):
    offset = len(PNG_SIGNATURE)
    while offset < len(payload):
        length = int.from_bytes(payload[offset:offset + 4], "big")
        kind = payload[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        yield kind, payload[start:end]
        offset = end + 4
        if kind == b"IEND":
            return


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + kind + data + (zlib.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")


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


def _reject_conflicting_scalar_fields(lines: list[dict[str, Any]]) -> None:
    candidates: dict[str, set[Any]] = {name: set() for name in ("rank", "slot", "level", "set", "enhance")}
    for line in lines:
        parsed = parse_backpack_enhance_lines([line])
        fields = parsed.get("fields")
        if not isinstance(fields, Mapping):
            continue
        for name in candidates:
            field = fields.get(name)
            if isinstance(field, Mapping) and field.get("normalized") is not None:
                candidates[name].add(field["normalized"])
    conflicting = next((name for name, values in candidates.items() if len(values) > 1), None)
    if conflicting is not None:
        raise LocalRecognitionError(f"PaddleOCR fields conflict:{conflicting}")
