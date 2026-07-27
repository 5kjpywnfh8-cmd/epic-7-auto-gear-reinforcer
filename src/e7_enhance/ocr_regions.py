"""Normalized, read-only OCR regions for a single equipment detail page."""

from __future__ import annotations

from typing import Iterable


OCR_REGION_SCHEMA_VERSION = 2


def _region(name: str, left: float, top: float, right: float, bottom: float) -> dict:
    return {"name": name, "bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}


DEFAULT_EQUIPMENT_REGIONS = (
    _region("detail_header_anchor", 0.60, 0.07, 0.97, 0.16),
    _region("slot", 0.60, 0.08, 0.97, 0.16),
    _region("rank", 0.60, 0.08, 0.97, 0.16),
    _region("set", 0.63984375, 0.76, 0.95, 0.86),
    _region("set_anchor", 0.63984375, 0.76, 0.95, 0.86),
    # These are independent candidate crops.  The icon is template evidence;
    # the text crop is the only local PaddleOCR entry for the set field.
    _region("set_icon", 0.63984375, 0.7638888889, 0.703125, 0.8555555556),
    _region("set_text", 0.715625, 0.75, 0.875, 0.8333333333),
    _region("enhance", 0.63984375, 0.16, 0.95, 0.25),
    _region("enhance_anchor", 0.63984375, 0.16, 0.95, 0.25),
    _region("level", 0.60, 0.16, 0.97, 0.25),
    _region("main", 0.60, 0.25, 0.97, 0.42),
    _region("substats", 0.60, 0.42, 0.97, 0.73),
    _region("detail_score_anchor", 0.60, 0.73, 0.97, 0.82),
)

# Candidate crops are intentionally separate from the default parser manifest.
# The offline comparer consumes every one from the same supplied frame; adding
# them to the default manifest would silently change the live parser contract.
SET_CROP_CANDIDATES = (
    {
        "name": "set_icon_wide_red",
        "kind": "icon",
        "bounds": {"left": 0.6796875, "top": 0.7444444444, "right": 0.7265625, "bottom": 0.8333333333},
        "preprocess": "rgba_nearest_neighbor",
    },
    {
        "name": "set_icon_tight_red",
        "kind": "icon",
        "bounds": {"left": 0.68359375, "top": 0.75, "right": 0.72265625, "bottom": 0.8277777778},
        "preprocess": "rgba_nearest_neighbor",
    },
    {
        "name": "set_icon_inner_red",
        "kind": "icon",
        "bounds": {"left": 0.6875, "top": 0.7569444444, "right": 0.71875, "bottom": 0.8208333333},
        "preprocess": "rgba_nearest_neighbor",
    },
    {
        "name": "set_text_wide_red",
        "kind": "text",
        "bounds": {"left": 0.715625, "top": 0.75, "right": 0.875, "bottom": 0.8333333333},
        "preprocess": "paddle_lanczos_contrast_1_15",
    },
    {
        "name": "set_text_compact_red",
        "kind": "text",
        "bounds": {"left": 0.715625, "top": 0.7555555556, "right": 0.8078125, "bottom": 0.8222222222},
        "preprocess": "paddle_lanczos_contrast_1_15",
    },
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


def set_crop_candidates() -> list[dict]:
    """Return independent, fixed crop plans for offline set comparison."""
    candidates = [
        {**candidate, "bounds": dict(candidate["bounds"])}
        for candidate in SET_CROP_CANDIDATES
    ]
    errors = validate_regions(candidates)
    names = {candidate["name"] for candidate in candidates}
    for candidate in candidates:
        if candidate["kind"] not in {"icon", "text"}:
            errors.append(f"invalid_set_crop_kind:{candidate['name']}")
        if not isinstance(candidate["preprocess"], str) or not candidate["preprocess"]:
            errors.append(f"invalid_set_crop_preprocess:{candidate['name']}")
    if {"icon", "text"} != {candidate["kind"] for candidate in candidates}:
        errors.append("incomplete_set_crop_kinds")
    if len(names) != len(candidates):
        errors.append("duplicate_set_crop_name")
    if errors:
        raise ValueError("invalid set crop candidates:" + ",".join(errors))
    return candidates


def equipment_regions() -> dict:
    regions = [dict(region, bounds=dict(region["bounds"])) for region in DEFAULT_EQUIPMENT_REGIONS]
    return {
        "schema_version": OCR_REGION_SCHEMA_VERSION,
        "template": "equipment_detail_normalized_v2",
        "regions": regions,
        "validation_errors": validate_regions(regions),
        "click_coordinates": None,
    }
