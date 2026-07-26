"""Offline set-icon candidate anchors for the local visual recognizer seam.

This module only compares injected in-memory local PNG samples with the
already-audited local icon bundle.  It neither captures frames nor confirms an
equipment field.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .visual_adapter import VisualFrame
from .visual_adb_recognition import _decode_png
from .visual_platform import RegionSample
from .visual_templates import SetIconTemplate, load_set_icon_templates


SET_ICON_MATCH_THRESHOLD = 0.98
ALLOWED_TEMPLATE_SCALES = (1.0,)
_COARSE_MASK_SAMPLES = 12
_COARSE_STEP = 2
_FULL_CANDIDATES = 8


class LocalSetIconTemplateRecognizer:
    """Provide one fail-closed set-icon candidate through ``LocalTemplateRecognizer``."""

    def __init__(
        self,
        *,
        template_loader: Callable[[], Mapping[str, SetIconTemplate]] = load_set_icon_templates,
    ) -> None:
        if not callable(template_loader):
            raise TypeError("set icon template loader must be callable")
        self._template_loader = template_loader
        self._threshold = SET_ICON_MATCH_THRESHOLD

    def recognize(
        self, frame: VisualFrame, regions: Mapping[str, RegionSample]
    ) -> Sequence[Mapping[str, Any]]:
        """Return a sole high-confidence candidate, or no anchors at all."""
        if not isinstance(frame, VisualFrame) or not isinstance(regions, Mapping):
            return []
        sample = regions.get("set_anchor") or regions.get("set")
        if not isinstance(sample, RegionSample) or not _sample_matches_bounds(sample, frame.viewport):
            return []
        try:
            templates = self._template_loader()
            sample_pixels = _decode_pixels(sample.payload)
        except Exception:
            return []
        if (
            not isinstance(templates, Mapping)
            or not templates
            or not sample_pixels
            or sample_pixels[:2] != _region_size(sample)
        ):
            return []

        candidates: list[tuple[str, float, float]] = []
        for identifier, template in templates.items():
            if not isinstance(identifier, str) or not isinstance(template, SetIconTemplate):
                return []
            try:
                pixels = _decode_pixels(Path(template.path).read_bytes())
                result = _best_match(sample_pixels, pixels)
            except Exception:
                return []
            if result is not None:
                score, bright_ratio, ambiguous = result
                if ambiguous:
                    return []
                if score >= self._threshold and bright_ratio > 0:
                    candidates.append((identifier, score, bright_ratio))
        if not candidates:
            return []
        candidates.sort(key=lambda item: (-item[1], item[0]))
        best = candidates[0]
        if len(candidates) > 1 and candidates[1][1] == best[1]:
            return []
        return [{
            "name": f"set_icon:{best[0]}",
            "candidate_id": best[0],
            "score": round(best[1], 6),
            "threshold": self._threshold,
            "bright_ratio": round(best[2], 6),
        }]


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


def _best_match(
    sample: tuple[int, int, tuple[tuple[int, int, int, int], ...]],
    template: tuple[int, int, tuple[tuple[int, int, int, int], ...]],
) -> tuple[float, float, bool] | None:
    sample_width, sample_height, sample_pixels = sample
    template_width, template_height, template_pixels = template
    if 1.0 not in ALLOWED_TEMPLATE_SCALES or template_width > sample_width or template_height > sample_height:
        return None
    mask = [
        (index % template_width, index // template_width, pixel)
        for index, pixel in enumerate(template_pixels)
        if pixel[3] >= 32
    ]
    if len(mask) < _COARSE_MASK_SAMPLES:
        return None
    coarse_step = max(1, len(mask) // _COARSE_MASK_SAMPLES)
    coarse_mask = mask[::coarse_step][:_COARSE_MASK_SAMPLES]
    positions = _coarse_positions(sample_width - template_width, sample_height - template_height)
    scored = sorted(
        ((_score(sample_pixels, sample_width, x, y, coarse_mask), x, y) for x, y in positions),
        reverse=True,
    )[:_FULL_CANDIDATES]
    if not scored:
        return None
    full_positions = {
        (x + dx, y + dy)
        for _, x, y in scored
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if 0 <= x + dx <= sample_width - template_width and 0 <= y + dy <= sample_height - template_height
    }
    full_scores = [
        (
            _score(sample_pixels, sample_width, x, y, mask),
            _bright_ratio(sample_pixels, sample_width, x, y, template_width, template_height),
            x,
            y,
        )
        for x, y in full_positions
    ]
    if not full_scores:
        return None
    best_score = max(score for score, _, _, _ in full_scores)
    best = [entry for entry in full_scores if entry[0] == best_score]
    if len(best) != 1:
        return best[0][0], best[0][1], True
    return best[0][0], best[0][1], False


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
