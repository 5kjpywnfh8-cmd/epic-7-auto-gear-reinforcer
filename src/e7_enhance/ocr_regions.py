"""Normalized, read-only OCR regions for a single equipment detail page."""

from __future__ import annotations

from typing import Iterable


OCR_REGION_SCHEMA_VERSION = 1


def _region(name: str, left: float, top: float, right: float, bottom: float) -> dict:
    return {"name": name, "bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}


DEFAULT_EQUIPMENT_REGIONS = (
    _region("detail_header_anchor", 0.60, 0.07, 0.97, 0.16),
    _region("slot", 0.60, 0.08, 0.97, 0.16),
    _region("rank", 0.60, 0.08, 0.97, 0.16),
    _region("set", 0.63984375, 0.76, 0.95, 0.86),
    _region("set_anchor", 0.63984375, 0.76, 0.95, 0.86),
    _region("enhance", 0.63984375, 0.16, 0.95, 0.25),
    _region("enhance_anchor", 0.63984375, 0.16, 0.95, 0.25),
    _region("level", 0.60, 0.16, 0.97, 0.25),
    _region("main", 0.60, 0.25, 0.97, 0.42),
    _region("substats", 0.60, 0.42, 0.97, 0.73),
    _region("detail_score_anchor", 0.60, 0.73, 0.97, 0.82),
)


def validate_regions(regions: Iterable[dict]) -> list[str]:
    """Validate normalized read-only rectangles; this is not a click map."""
    errors: list[str] = []
    seen: set[str] = set()
    for region in regions:
        name = str(region.get("name") or "").strip()
        bounds = region.get("bounds") if isinstance(region.get("bounds"), dict) else {}
        if not name or name in seen:
            errors.append(f"invalid_region_name:{name or 'missing'}")
        seen.add(name)
        try:
            left, top, right, bottom = (float(bounds[key]) for key in ("left", "top", "right", "bottom"))
        except (KeyError, TypeError, ValueError):
            errors.append(f"invalid_region_bounds:{name or 'missing'}")
            continue
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            errors.append(f"out_of_bounds_region:{name}")
    return errors


def equipment_regions() -> dict:
    regions = [dict(region, bounds=dict(region["bounds"])) for region in DEFAULT_EQUIPMENT_REGIONS]
    return {
        "schema_version": OCR_REGION_SCHEMA_VERSION,
        "template": "equipment_detail_normalized_v1",
        "regions": regions,
        "validation_errors": validate_regions(regions),
        "click_coordinates": None,
    }
