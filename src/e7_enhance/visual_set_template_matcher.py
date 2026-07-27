"""Offline set-icon candidate anchors for the local visual recognizer seam.

This module only compares injected in-memory local PNG samples with the
already-audited local icon bundle.  It neither captures frames nor confirms an
equipment field.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
import zlib

from .visual_adapter import VisualFrame
from .visual_adb_recognition import _decode_png
from .visual_platform import RegionSample
from .visual_templates import SetIconTemplate, load_set_icon_templates


SET_ICON_MATCH_THRESHOLD = 0.98
SET_ICON_CANDIDATE_REGION_NAMES = (
    "set_icon",
    "set_icon_1",
    "set_icon_2",
    "set_icon_3",
    "set_icon_wide_red",
    "set_icon_tight_red",
    "set_icon_inner_red",
)
# The nearest-neighbor scale set is intentionally small and fixed.  It permits
# only deterministic icon-size drift; interpolation, rotation, and crop
# guessing remain rejected.
ALLOWED_TEMPLATE_SCALES = (0.5, 1.0, 2.0)
_COARSE_MASK_SAMPLES = 12
_COARSE_STEP = 2
_FULL_CANDIDATES = 8


class LocalSetIconTemplateRecognizer:
    """Compare explicit set-icon crops and expose at most one trusted anchor."""

    def __init__(
        self,
        *,
        template_loader: Callable[[], Mapping[str, SetIconTemplate]] = load_set_icon_templates,
    ) -> None:
        if not callable(template_loader):
            raise TypeError("set icon template loader must be callable")
        self._template_loader = template_loader
        self._threshold = SET_ICON_MATCH_THRESHOLD
        self._last_candidate_results: tuple[Mapping[str, Any], ...] = ()

    @property
    def last_candidate_results(self) -> tuple[Mapping[str, Any], ...]:
        """Return the most recent per-crop comparison audit without evidence semantics."""
        return tuple(dict(result) for result in self._last_candidate_results)

    def recognize(
        self, frame: VisualFrame, regions: Mapping[str, RegionSample]
    ) -> Sequence[Mapping[str, Any]]:
        """Return a sole high-confidence candidate, or no anchors at all."""
        self._last_candidate_results = ()
        if not isinstance(frame, VisualFrame) or not isinstance(regions, Mapping):
            return []
        samples = _candidate_samples(regions)
        if samples is None:
            return []
        try:
            templates = self._template_loader()
        except Exception:
            self._last_candidate_results = _rejected_candidates(samples, "template_bundle_invalid")
            return []
        decoded_templates = _decode_templates(templates)
        if decoded_templates is None:
            self._last_candidate_results = _rejected_candidates(samples, "template_png_invalid")
            return []

        results = [
            _compare_candidate(sample, frame.viewport, decoded_templates, self._threshold)
            for sample in samples
        ]
        if any(result["rejection_reason"] in {"invalid_region", "invalid_png"} for result in results):
            for result in results:
                if result["rejection_reason"] is None:
                    result["rejection_reason"] = "candidate_input_invalid"
            self._last_candidate_results = tuple(dict(result) for result in results)
            return []
        qualified = [result for result in results if result["rejection_reason"] is None]
        if len(qualified) != 1:
            if len(qualified) > 1:
                for result in qualified:
                    result["rejection_reason"] = "multiple_high_confidence_candidates"
            self._last_candidate_results = tuple(dict(result) for result in results)
            return []
        best = qualified[0]
        self._last_candidate_results = tuple(dict(result) for result in results)
        return [{
            "name": f"set_icon:{best['candidate_id']}",
            "candidate_id": best["candidate_id"],
            "region": best["region"],
            "score": best["score"],
            "threshold": self._threshold,
            "bright_ratio": best["bright_ratio"],
            "anchor_bounds": best["anchor_bounds"],
            "template_scale": best["template_scale"],
            "preprocess": "rgba_nearest_neighbor",
            "candidate_results": [dict(result) for result in self._last_candidate_results],
        }]


def _candidate_samples(regions: Mapping[str, RegionSample]) -> tuple[RegionSample, ...] | None:
    if any(
        isinstance(name, str)
        and name.startswith("set_icon")
        and name not in SET_ICON_CANDIDATE_REGION_NAMES
        for name in regions
    ):
        return None
    explicit = tuple(regions.get(name) for name in SET_ICON_CANDIDATE_REGION_NAMES if name in regions)
    if explicit:
        if any(not isinstance(sample, RegionSample) for sample in explicit):
            return None
        return explicit
    legacy = regions.get("set_anchor") or regions.get("set")
    return (legacy,) if isinstance(legacy, RegionSample) else ()


def _rejected_candidates(samples: Sequence[RegionSample], reason: str) -> tuple[Mapping[str, Any], ...]:
    return tuple({
        "region": sample.region.name,
        "pixel_bounds": _bounds(sample),
        "score": None,
        "unique": False,
        "rejection_reason": reason,
    } for sample in samples)


def _decode_templates(
    templates: Mapping[str, SetIconTemplate],
) -> tuple[tuple[str, tuple[int, int, tuple[tuple[int, int, int, int], ...]]], ...] | None:
    if not isinstance(templates, Mapping) or not templates:
        return None
    decoded: list[tuple[str, tuple[int, int, tuple[tuple[int, int, int, int], ...]]]] = []
    for identifier, template in templates.items():
        if not isinstance(identifier, str) or not isinstance(template, SetIconTemplate):
            return None
        try:
            decoded.append((identifier, _decode_template_pixels(Path(template.path).read_bytes())))
        except Exception:
            return None
    return tuple(decoded)


def _compare_candidate(
    sample: RegionSample,
    viewport: tuple[int, int],
    templates: Sequence[tuple[str, tuple[int, int, tuple[tuple[int, int, int, int], ...]]]],
    threshold: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "region": sample.region.name,
        "pixel_bounds": _bounds(sample),
        "score": None,
        "unique": False,
        "rejection_reason": None,
    }
    if not _sample_matches_bounds(sample, viewport):
        result["rejection_reason"] = "invalid_region"
        return result
    try:
        sample_pixels = _decode_pixels(sample.payload)
    except Exception:
        result["rejection_reason"] = "invalid_png"
        return result
    if sample_pixels[:2] != _region_size(sample):
        result["rejection_reason"] = "invalid_region"
        return result
    matches: list[tuple[str, tuple[float, float, bool, int, int, int, int, float]]] = []
    for identifier, template in templates:
        matched = _best_match(sample_pixels, template)
        if matched is not None:
            matches.append((identifier, matched))
    if not matches:
        result["rejection_reason"] = "no_template_match"
        return result
    best_score = max(match[1][0] for match in matches)
    best = [(identifier, matched) for identifier, matched in matches if matched[0] == best_score]
    identifier, match = best[0]
    score, bright_ratio, ambiguous, left, top, width, height, scale = match
    result.update({
        "candidate_id": identifier,
        "score": round(score, 6),
        "bright_ratio": round(bright_ratio, 6),
        "anchor_bounds": {"left": left, "top": top, "right": left + width, "bottom": top + height},
        "template_scale": scale,
    })
    if len(best) != 1 or ambiguous:
        result["rejection_reason"] = "ambiguous_template_match"
        return result
    result["unique"] = True
    if score < threshold:
        result["rejection_reason"] = "low_confidence"
    elif bright_ratio <= 0:
        result["rejection_reason"] = "not_visible"
    return result


def _bounds(sample: RegionSample) -> dict[str, int]:
    left, top, right, bottom = sample.region.pixel_bounds
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _sample_matches_bounds(sample: RegionSample, viewport: tuple[int, int]) -> bool:
    if not isinstance(sample.payload, bytes) or not sample.payload:
        return False
    left, top, right, bottom = sample.region.pixel_bounds
    width, height = viewport
    return (
        isinstance(width, int)
        and isinstance(height, int)
        and 0 <= left < right <= width
        and 0 <= top < bottom <= height
    )


def _region_size(sample: RegionSample) -> tuple[int, int]:
    left, top, right, bottom = sample.region.pixel_bounds
    return right - left, bottom - top


def _decode_pixels(payload: bytes) -> tuple[int, int, tuple[tuple[int, int, int, int], ...]]:
    decoded = _decode_png(payload)
    pixels: list[tuple[int, int, int, int]] = []
    channels = decoded.channels
    for row in decoded.rows:
        for offset in range(0, len(row), channels):
            values = row[offset:offset + channels]
            if decoded.color_type == 0:
                pixels.append((values[0], values[0], values[0], 255))
            elif decoded.color_type == 2:
                pixels.append((values[0], values[1], values[2], 255))
            elif decoded.color_type == 4:
                pixels.append((values[0], values[0], values[0], values[1]))
            else:
                pixels.append((values[0], values[1], values[2], values[3]))
    return decoded.width, decoded.height, tuple(pixels)


def _decode_template_pixels(payload: bytes) -> tuple[int, int, tuple[tuple[int, int, int, int], ...]]:
    """Decode the first complete upstream PNG while retaining manifest hash checks."""
    stream = _first_png_stream(payload)
    try:
        return _decode_pixels(stream)
    except Exception:
        return _decode_indexed_template_pixels(stream)


def _first_png_stream(payload: bytes) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    if not isinstance(payload, bytes) or not payload.startswith(signature):
        raise ValueError("PNG signature is missing")
    offset = len(signature)
    while offset + 12 <= len(payload):
        length = int.from_bytes(payload[offset:offset + 4], "big")
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if data_end > len(payload) or crc_end > len(payload):
            raise ValueError("PNG chunk is truncated")
        kind = payload[offset + 4:data_start]
        data = payload[data_start:data_end]
        expected_crc = int.from_bytes(payload[data_end:crc_end], "big")
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG chunk checksum is invalid")
        if kind == b"IEND":
            if length != 0:
                raise ValueError("PNG IEND is invalid")
            return payload[:crc_end]
        offset = crc_end
    raise ValueError("PNG IEND is missing")


def _decode_indexed_template_pixels(payload: bytes) -> tuple[int, int, tuple[tuple[int, int, int, int], ...]]:
    """Decode the audited 8-bit palette PNGs used by the local set bundle."""
    signature = b"\x89PNG\r\n\x1a\n"
    if not payload.startswith(signature):
        raise ValueError("PNG signature is missing")
    offset = len(signature)
    ihdr: bytes | None = None
    palette: bytes | None = None
    transparency = b""
    idat: list[bytes] = []
    while offset + 12 <= len(payload):
        length = int.from_bytes(payload[offset:offset + 4], "big")
        kind = payload[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        crc_end = end + 4
        if crc_end > len(payload):
            raise ValueError("PNG chunk is truncated")
        data = payload[start:end]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != int.from_bytes(payload[end:crc_end], "big"):
            raise ValueError("PNG chunk checksum is invalid")
        if kind == b"IHDR":
            ihdr = data
        elif kind == b"PLTE":
            palette = data
        elif kind == b"tRNS":
            transparency = data
        elif kind == b"IDAT":
            idat.append(data)
        offset = crc_end
        if kind == b"IEND":
            break
    if ihdr is None or len(ihdr) != 13 or palette is None:
        raise ValueError("indexed PNG metadata is incomplete")
    width = int.from_bytes(ihdr[0:4], "big")
    height = int.from_bytes(ihdr[4:8], "big")
    bit_depth, color_type, compression, filter_method, interlace = ihdr[8:]
    if (
        width <= 0 or height <= 0 or bit_depth != 8 or color_type != 3
        or (compression, filter_method, interlace) != (0, 0, 0)
        or len(palette) == 0 or len(palette) % 3 != 0
    ):
        raise ValueError("indexed PNG format is unsupported")
    try:
        encoded = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise ValueError("indexed PNG pixel stream is invalid") from exc
    if len(encoded) != (width + 1) * height:
        raise ValueError("indexed PNG pixel stream length is invalid")
    rows: list[bytes] = []
    previous = bytearray(width)
    cursor = 0
    for _ in range(height):
        filter_type = encoded[cursor]
        source = encoded[cursor + 1:cursor + width + 1]
        cursor += width + 1
        row = bytearray(width)
        for index, value in enumerate(source):
            left = row[index - 1] if index else 0
            up = previous[index]
            upper_left = previous[index - 1] if index else 0
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
                raise ValueError("indexed PNG row filter is unsupported")
            row[index] = (value + predictor) & 0xFF
        rows.append(bytes(row))
        previous = row
    colors = [tuple(palette[index:index + 3]) for index in range(0, len(palette), 3)]
    pixels: list[tuple[int, int, int, int]] = []
    for row in rows:
        for index in row:
            if index >= len(colors):
                raise ValueError("indexed PNG palette index is invalid")
            red, green, blue = colors[index]
            pixels.append((red, green, blue, transparency[index] if index < len(transparency) else 255))
    return width, height, tuple(pixels)


def _paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
    return (left, up, upper_left)[distances.index(min(distances))]


def _best_match(
    sample: tuple[int, int, tuple[tuple[int, int, int, int], ...]],
    template: tuple[int, int, tuple[tuple[int, int, int, int], ...]],
) -> tuple[float, float, bool, int, int, int, int, float] | None:
    sample_width, sample_height, sample_pixels = sample
    template_width, template_height, _ = template
    all_scores: list[tuple[float, float, int, int, int, int, float]] = []
    for scale in ALLOWED_TEMPLATE_SCALES:
        scaled = _scale_template(template, scale)
        if scaled is None:
            continue
        width, height, pixels = scaled
        if width > sample_width or height > sample_height:
            continue
        mask = [
            (index % width, index // width, pixel)
            for index, pixel in enumerate(pixels)
            if pixel[3] >= 32
        ]
        if len(mask) < _COARSE_MASK_SAMPLES:
            continue
        coarse_step = max(1, len(mask) // _COARSE_MASK_SAMPLES)
        coarse_mask = mask[::coarse_step][:_COARSE_MASK_SAMPLES]
        positions = _coarse_positions(sample_width - width, sample_height - height)
        scored = sorted(
            ((_score(sample_pixels, sample_width, x, y, coarse_mask), x, y) for x, y in positions),
            reverse=True,
        )[:_FULL_CANDIDATES]
        full_positions = {
            (x + dx, y + dy)
            for _, x, y in scored
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if 0 <= x + dx <= sample_width - width and 0 <= y + dy <= sample_height - height
        }
        all_scores.extend(
            (
                _score(sample_pixels, sample_width, x, y, mask),
                _bright_ratio(sample_pixels, sample_width, x, y, width, height),
                x,
                y,
                width,
                height,
                scale,
            )
            for x, y in full_positions
        )
    if not all_scores:
        return None
    best_score = max(score for score, *_ in all_scores)
    best = [entry for entry in all_scores if entry[0] == best_score]
    if len(best) != 1:
        score, bright_ratio, left, top, width, height, scale = best[0]
        return score, bright_ratio, True, left, top, width, height, scale
    return (*best[0][:2], False, *best[0][2:])


def _scale_template(
    template: tuple[int, int, tuple[tuple[int, int, int, int], ...]], scale: float
) -> tuple[int, int, tuple[tuple[int, int, int, int], ...]] | None:
    width, height, pixels = template
    if scale not in ALLOWED_TEMPLATE_SCALES:
        return None
    scaled_width, scaled_height = round(width * scale), round(height * scale)
    if scaled_width <= 0 or scaled_height <= 0:
        return None
    return (
        scaled_width,
        scaled_height,
        tuple(
            pixels[min(height - 1, int(y / scale)) * width + min(width - 1, int(x / scale))]
            for y in range(scaled_height)
            for x in range(scaled_width)
        ),
    )


def _coarse_positions(max_x: int, max_y: int) -> tuple[tuple[int, int], ...]:
    xs = sorted(set(range(0, max_x + 1, _COARSE_STEP)) | {max_x})
    ys = sorted(set(range(0, max_y + 1, _COARSE_STEP)) | {max_y})
    return tuple((x, y) for y in ys for x in xs)


def _score(
    sample_pixels: tuple[tuple[int, int, int, int], ...],
    sample_width: int,
    left: int,
    top: int,
    mask: Sequence[tuple[int, int, tuple[int, int, int, int]]],
) -> float:
    total = 0
    for x, y, template_pixel in mask:
        sample_pixel = sample_pixels[(top + y) * sample_width + left + x]
        total += abs(sample_pixel[0] - template_pixel[0])
        total += abs(sample_pixel[1] - template_pixel[1])
        total += abs(sample_pixel[2] - template_pixel[2])
    return 1 - total / (len(mask) * 3 * 255)


def _bright_ratio(
    pixels: tuple[tuple[int, int, int, int], ...],
    width: int,
    left: int,
    top: int,
    template_width: int,
    template_height: int,
) -> float:
    values = [
        pixels[y * width + x]
        for y in range(top, top + template_height)
        for x in range(left, left + template_width)
    ]
    visible = [pixel for pixel in values if pixel[3] >= 32]
    if not visible:
        return 0.0
    return sum((red + green + blue) / 3 >= 32 for red, green, blue, _ in visible) / len(visible)
