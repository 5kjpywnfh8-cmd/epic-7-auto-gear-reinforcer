"""Fail-closed, in-memory comparison of explicit set crop candidates."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .ocr_regions import set_crop_candidates, validate_regions
from .visual_adapter import VisualFrame
from .visual_platform import LocalRegion, RegionSample


SET_CROP_COMPARISON_THRESHOLD = 0.98


def compare_set_crop_candidates(
    frame: VisualFrame,
    *,
    region_extractor: Callable[[VisualFrame, LocalRegion], bytes],
    icon_recognizer: Callable[[VisualFrame, RegionSample], Sequence[Mapping[str, Any]]],
    text_recognizer: Callable[[VisualFrame, RegionSample], Sequence[Mapping[str, Any]]],
    candidates: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare all fixed candidates from one frame without retrying or guessing.

    Recognizers receive exactly one already-extracted local sample.  Icon rows
    must provide ``candidate_id`` and ``score``; text rows must provide
    ``normalized`` and ``confidence``.  Both channels must select exactly one
    high-confidence crop with the same value before this result is accepted.
    """
    definitions = list(set_crop_candidates() if candidates is None else candidates)
    prepared, preparation_errors = _prepare_candidates(frame, definitions)
    if preparation_errors:
        return _rejected_result(
            _invalid_candidate_rows(frame, definitions, preparation_errors),
            sorted(f"invalid_candidate:{name}" for name in preparation_errors),
        )

    samples: dict[str, RegionSample] = {}
    extraction_errors: dict[str, list[str]] = {}
    for candidate, region in prepared:
        try:
            payload = region_extractor(frame, region)
        except Exception:
            extraction_errors[candidate["name"]] = ["extraction_failed"]
            continue
        if not isinstance(payload, bytes) or not payload:
            extraction_errors[candidate["name"]] = ["invalid_crop_payload"]
            continue
        samples[candidate["name"]] = RegionSample(region, payload)
    if extraction_errors:
        return _rejected_result(
            _candidate_rows(prepared, extraction_errors),
            sorted(f"crop_rejected:{name}" for name in extraction_errors),
        )

    rows: list[dict[str, Any]] = []
    for candidate, region in prepared:
        recognizer = icon_recognizer if candidate["kind"] == "icon" else text_recognizer
        value_key = "candidate_id" if candidate["kind"] == "icon" else "normalized"
        score_key = "score" if candidate["kind"] == "icon" else "confidence"
        rows.append(_recognize_candidate(frame, candidate, region, samples[candidate["name"]], recognizer, value_key, score_key))

    icon = _select_channel(rows, "icon")
    text = _select_channel(rows, "text")
    reasons = [*icon["rejection_reasons"], *text["rejection_reasons"]]
    value = None
    if icon["accepted"] and text["accepted"]:
        if icon["value"] != text["value"]:
            reasons.append("conflicting:set")
        else:
            value = text["value"]
    else:
        reasons.append("incomplete_set_evidence")
    return {
        "schema_version": 1,
        "mode": "visual_only",
        "verification": "unverified",
        "threshold": SET_CROP_COMPARISON_THRESHOLD,
        "accepted": not reasons,
        "set": None if reasons else {"value": value, "confidence": text["confidence"]},
        "candidates": rows,
        "selection": {"icon": icon, "text": text},
        "rejection_reasons": sorted(set(reasons)),
        "click_performed": False,
    }


def _prepare_candidates(
    frame: VisualFrame, candidates: Sequence[Mapping[str, Any]]
) -> tuple[list[tuple[dict[str, Any], LocalRegion]], set[str]]:
    invalid: set[str] = set()
    definitions: list[dict[str, Any]] = []
    if not isinstance(frame, VisualFrame):
        return [], {"frame"}
    for index, source in enumerate(candidates):
        candidate = dict(source) if isinstance(source, Mapping) else {}
        name = candidate.get("name")
        if not isinstance(name, str) or not name.strip():
            invalid.add(f"index_{index}")
            continue
        definitions.append(candidate)
    invalid.update(_invalid_candidate_names(definitions))
    if invalid:
        return _resolve_valid_candidates(frame, definitions), invalid
    width, height = frame.viewport
    prepared: list[tuple[dict[str, Any], LocalRegion]] = []
    for candidate in definitions:
        bounds = candidate["bounds"]
        pixels = tuple(round(float(bounds[key]) * size) for key, size in zip(("left", "top", "right", "bottom"), (width, height, width, height)))
        if not (0 <= pixels[0] < pixels[2] <= width and 0 <= pixels[1] < pixels[3] <= height):
            invalid.add(candidate["name"])
            continue
        prepared.append((candidate, LocalRegion(candidate["name"], dict(bounds), pixels)))
    return prepared, invalid


def _resolve_valid_candidates(
    frame: VisualFrame, candidates: Sequence[Mapping[str, Any]]
) -> list[tuple[dict[str, Any], LocalRegion]]:
    width, height = frame.viewport
    prepared: list[tuple[dict[str, Any], LocalRegion]] = []
    for candidate in candidates:
        bounds = candidate.get("bounds")
        if not isinstance(bounds, Mapping):
            continue
        try:
            pixels = tuple(round(float(bounds[key]) * size) for key, size in zip(("left", "top", "right", "bottom"), (width, height, width, height)))
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= pixels[0] < pixels[2] <= width and 0 <= pixels[1] < pixels[3] <= height:
            prepared.append((dict(candidate), LocalRegion(str(candidate["name"]), dict(bounds), pixels)))
    return prepared


def _invalid_candidate_names(candidates: Sequence[Mapping[str, Any]]) -> set[str]:
    invalid = {
        error.rsplit(":", 1)[-1]
        for error in validate_regions(candidates)
    }
    names: set[str] = set()
    for candidate in candidates:
        name = str(candidate.get("name") or "missing")
        if name in names:
            invalid.add(name)
        names.add(name)
        if candidate.get("kind") not in {"icon", "text"}:
            invalid.add(name)
        if not isinstance(candidate.get("preprocess"), str) or not candidate["preprocess"]:
            invalid.add(name)
    return invalid


def _recognize_candidate(
    frame: VisualFrame,
    candidate: Mapping[str, Any],
    region: LocalRegion,
    sample: RegionSample,
    recognizer: Callable[[VisualFrame, RegionSample], Sequence[Mapping[str, Any]]],
    value_key: str,
    score_key: str,
) -> dict[str, Any]:
    row = _candidate_row(candidate, region)
    try:
        matches = recognizer(frame, sample)
    except Exception:
        row["rejection_reasons"] = ["recognition_failed"]
        return row
    if not isinstance(matches, Sequence) or isinstance(matches, (str, bytes)):
        row["rejection_reasons"] = ["invalid_recognition_result"]
        return row
    accepted_matches: list[tuple[str, float]] = []
    scores: list[float] = []
    for match in matches:
        if not isinstance(match, Mapping):
            row["rejection_reasons"] = ["invalid_recognition_result"]
            return row
        value = match.get(value_key)
        score = match.get(score_key)
        if not isinstance(value, str) or not value.strip() or not _unit(score):
            row["rejection_reasons"] = ["invalid_recognition_result"]
            return row
        scores.append(float(score))
        if score >= SET_CROP_COMPARISON_THRESHOLD:
            accepted_matches.append((value, float(score)))
    row["confidence"] = max(scores, default=0.0)
    if not matches:
        row["rejection_reasons"] = ["missing_match"]
    elif not accepted_matches:
        row["rejection_reasons"] = ["low_confidence"]
    elif len(accepted_matches) != 1:
        row["rejection_reasons"] = ["non_unique_match"]
    else:
        row["value"], row["confidence"] = accepted_matches[0]
        row["unique"] = True
    return row


def _candidate_rows(
    prepared: Sequence[tuple[dict[str, Any], LocalRegion]], errors: Mapping[str, Sequence[str]]
) -> list[dict[str, Any]]:
    return [
        _candidate_row(candidate, region) | {"rejection_reasons": list(errors.get(candidate["name"], ("not_evaluated",)))}
        for candidate, region in prepared
    ]


def _invalid_candidate_rows(
    frame: VisualFrame, candidates: Sequence[Mapping[str, Any]], invalid: set[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    width, height = frame.viewport
    for index, source in enumerate(candidates):
        candidate = dict(source) if isinstance(source, Mapping) else {}
        name = str(candidate.get("name") or f"index_{index}")
        bounds = candidate.get("bounds")
        pixels = None
        if isinstance(bounds, Mapping):
            try:
                pixels = tuple(
                    round(float(bounds[key]) * size)
                    for key, size in zip(("left", "top", "right", "bottom"), (width, height, width, height))
                )
            except (KeyError, TypeError, ValueError):
                pixels = None
        rows.append({
            "name": name,
            "kind": candidate.get("kind"),
            "normalized_bounds": dict(bounds) if isinstance(bounds, Mapping) else None,
            "pixel_bounds": None if pixels is None else {
                "left": pixels[0], "top": pixels[1], "right": pixels[2], "bottom": pixels[3],
            },
            "preprocess": candidate.get("preprocess"),
            "confidence": 0.0,
            "unique": False,
            "value": None,
            "rejection_reasons": ["invalid_candidate_bounds"] if name in invalid else ["not_evaluated"],
        })
    return rows


def _candidate_row(candidate: Mapping[str, Any], region: LocalRegion) -> dict[str, Any]:
    left, top, right, bottom = region.pixel_bounds
    return {
        "name": candidate["name"],
        "kind": candidate["kind"],
        "normalized_bounds": dict(candidate["bounds"]),
        "pixel_bounds": {"left": left, "top": top, "right": right, "bottom": bottom},
        "preprocess": candidate["preprocess"],
        "confidence": 0.0,
        "unique": False,
        "value": None,
        "rejection_reasons": [],
    }


def _select_channel(rows: Sequence[Mapping[str, Any]], kind: str) -> dict[str, Any]:
    passing = [row for row in rows if row["kind"] == kind and row["unique"]]
    if len(passing) != 1:
        return {
            "accepted": False,
            "candidate": None,
            "value": None,
            "confidence": 0.0,
            "rejection_reasons": [f"non_unique_crop:{kind}" if len(passing) > 1 else f"missing_crop:{kind}"],
        }
    selected = passing[0]
    return {
        "accepted": True,
        "candidate": selected["name"],
        "value": selected["value"],
        "confidence": selected["confidence"],
        "rejection_reasons": [],
    }


def _rejected_result(rows: Sequence[Mapping[str, Any]], reasons: Sequence[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mode": "visual_only",
        "verification": "unverified",
        "threshold": SET_CROP_COMPARISON_THRESHOLD,
        "accepted": False,
        "set": None,
        "candidates": list(rows),
        "selection": {},
        "rejection_reasons": list(reasons),
        "click_performed": False,
    }


def _unit(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= float(value) <= 1
