"""Strict local-only recognizer and fixed registry for equipment-list pages.

The recognizer deliberately consumes a caller-injected collection of already
localized observations.  It does not decode images, invoke an OCR engine,
capture a frame, infer a new region, or expose a click coordinate.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .visual_adapter import VisualFrame
from .visual_list_observer import (
    ListPageLocalRecognitionError,
    RegisteredListPageRegions,
    RegisteredListRegion,
)
from .visual_list_parser import REQUIRED_ANCHORS, REQUIRED_REGIONS
from .visual_runtime import MIN_FIELD_CONFIDENCE


LIST_PAGE_REGION_SCHEMA_VERSION = "e7_enhance.equipment_list_regions/1"
LIST_PAGE_VIEWPORT = (1280, 720)
_CARD_REGION_PREFIX = "candidate_card:"
_FIELD_NAMES = frozenset((
    "slot", "rank", "level", "enhance", "set", "main", "substats", "gear_score",
))


class ListPageLocalObservationSource(Protocol):
    """Supplies one already-read observation per registered local region."""

    def observe(
        self, frame: VisualFrame, regions: Mapping[str, Mapping[str, float]]
    ) -> Mapping[str, Any]:
        ...


def equipment_list_region_registry() -> RegisteredListPageRegions:
    """Return the sole provisional, versioned list-page read scope.

    These normalized bounds are a fixed local read manifest, not a click map
    and not evidence that the live game currently matches this viewport.  A
    separately authorized calibration must confirm the manifest before use
    with a real frame.
    """

    return RegisteredListPageRegions(
        (
            RegisteredListRegion("list_header_region", {"left": 0.05, "top": 0.04, "right": 0.95, "bottom": 0.18}),
            RegisteredListRegion("candidate_list_region", {"left": 0.05, "top": 0.18, "right": 0.95, "bottom": 0.94}),
            RegisteredListRegion("candidate_card:1", {"left": 0.08, "top": 0.22, "right": 0.48, "bottom": 0.44}),
            RegisteredListRegion("candidate_card:2", {"left": 0.52, "top": 0.22, "right": 0.92, "bottom": 0.44}),
            RegisteredListRegion("candidate_card:3", {"left": 0.08, "top": 0.48, "right": 0.48, "bottom": 0.70}),
            RegisteredListRegion("candidate_card:4", {"left": 0.52, "top": 0.48, "right": 0.92, "bottom": 0.70}),
            RegisteredListRegion("candidate_card:5", {"left": 0.08, "top": 0.74, "right": 0.48, "bottom": 0.92}),
            RegisteredListRegion("candidate_card:6", {"left": 0.52, "top": 0.74, "right": 0.92, "bottom": 0.92}),
        ),
        viewport=LIST_PAGE_VIEWPORT,
        schema_version=LIST_PAGE_REGION_SCHEMA_VERSION,
    )


class RegisteredListPageLocalRecognizer:
    """Adapt exactly one constrained local observation batch to list evidence."""

    def __init__(self, registry: RegisteredListPageRegions, source: ListPageLocalObservationSource) -> None:
        if not isinstance(registry, RegisteredListPageRegions):
            raise TypeError("a registered list-page region registry is required")
        if registry.viewport is None or registry.schema_version is None:
            raise ValueError("a versioned list-page registry with a viewport is required")
        if not callable(getattr(source, "observe", None)):
            raise TypeError("local observation source must provide observe")
        self._registry = registry
        self._source = source

    def observe(self, frame: VisualFrame, regions: Mapping[str, Mapping[str, float]]) -> Mapping[str, Any]:
        if not isinstance(frame, VisualFrame) or frame.viewport != self._registry.viewport:
            raise ListPageLocalRecognitionError("unknown_list_viewport")
        if not _same_regions(regions, self._registry.recognizer_regions):
            raise ListPageLocalRecognitionError("local_list_region_not_registered")
        try:
            observed = self._source.observe(frame, regions)
        except ListPageLocalRecognitionError:
            raise
        except Exception as exc:
            raise ListPageLocalRecognitionError("local_list_observation_failed") from exc
        return self._parse(observed)

    def _parse(self, observed: Any) -> Mapping[str, Any]:
        if not isinstance(observed, Mapping) or set(observed) != {"schema_version", "viewport", "local_regions"}:
            raise ListPageLocalRecognitionError("local_list_observation_invalid")
        if observed.get("schema_version") != self._registry.schema_version:
            raise ListPageLocalRecognitionError("local_list_schema_unknown")
        if tuple(observed.get("viewport", ())) != self._registry.viewport:
            raise ListPageLocalRecognitionError("unknown_list_viewport")
        local_regions = observed.get("local_regions")
        expected_names = set(self._registry.recognizer_regions)
        if not isinstance(local_regions, Mapping) or set(local_regions) != expected_names:
            raise ListPageLocalRecognitionError("local_list_region_not_registered")

        header = _mapping(local_regions, "list_header_region")
        candidate_list = _mapping(local_regions, "candidate_list_region")
        _require_exact_keys(header, {"score", "anchors"})
        _require_exact_keys(candidate_list, {"score", "scroll_state", "page_boundary"})
        header_score = _score(header["score"])
        candidate_list_score = _score(candidate_list["score"])
        anchors = _anchors(header["anchors"])
        scroll_state = candidate_list["scroll_state"]
        if scroll_state != "not_scrolled":
            raise ListPageLocalRecognitionError("scroll_or_page_boundary_unknown")
        page_boundary = candidate_list["page_boundary"]
        if not _page_boundary(page_boundary):
            raise ListPageLocalRecognitionError("scroll_or_page_boundary_unknown")

        candidates = []
        for name in sorted(expected_names):
            if not name.startswith(_CARD_REGION_PREFIX):
                continue
            local_card = _mapping(local_regions, name)
            _require_exact_keys(local_card, {"candidate"})
            candidate = local_card["candidate"]
            if candidate is None:
                continue
            candidates.append(_candidate(candidate, name))
        return {
            "anchors": anchors,
            "region_scores": {
                "list_header_region": header_score,
                "candidate_list_region": candidate_list_score,
            },
            "scroll_state": scroll_state,
            "page_boundary": dict(page_boundary),
            "candidates": candidates,
        }


def _same_regions(actual: Any, expected: Mapping[str, Mapping[str, float]]) -> bool:
    if not isinstance(actual, Mapping) or set(actual) != set(expected):
        return False
    return all(
        isinstance(actual[name], Mapping) and dict(actual[name]) == dict(bounds)
        for name, bounds in expected.items()
    )


def _mapping(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    result = value.get(name)
    if not isinstance(result, Mapping):
        raise ListPageLocalRecognitionError("local_list_observation_invalid")
    return result


def _require_exact_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise ListPageLocalRecognitionError("local_list_token_unknown")


def _score(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"score", "threshold"}:
        raise ListPageLocalRecognitionError("local_list_observation_invalid")
    score, threshold = value.get("score"), value.get("threshold")
    if not _confidence(score) or not _confidence(threshold) or float(score) < float(threshold):
        raise ListPageLocalRecognitionError("local_list_confidence_too_low")
    return {"score": float(score), "threshold": float(threshold)}


def _anchors(value: Any) -> list[dict[str, float | str]]:
    if not isinstance(value, list) or len(value) != len(REQUIRED_ANCHORS):
        raise ListPageLocalRecognitionError("list_anchors_not_confirmed")
    result = []
    names = set()
    for anchor in value:
        if not isinstance(anchor, Mapping) or set(anchor) != {"name", "score", "threshold"}:
            raise ListPageLocalRecognitionError("local_list_token_unknown")
        name = anchor.get("name")
        if name not in REQUIRED_ANCHORS or name in names:
            raise ListPageLocalRecognitionError("list_anchors_not_confirmed")
        names.add(name)
        score = _score({"score": anchor.get("score"), "threshold": anchor.get("threshold")})
        result.append({"name": name, **score})
    return result


def _page_boundary(value: Any) -> bool:
    return isinstance(value, Mapping) and set(value) == {"top_visible", "bottom_visible"} and all(
        isinstance(value[name], bool) for name in ("top_visible", "bottom_visible")
    )


def _candidate(value: Any, region: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"candidate_id", "visual_fingerprint", "field_observations"}:
        raise ListPageLocalRecognitionError("local_list_token_unknown")
    candidate_id = value.get("candidate_id")
    fingerprint = value.get("visual_fingerprint")
    if not isinstance(candidate_id, str) or not candidate_id.strip() or not _sha256(fingerprint):
        raise ListPageLocalRecognitionError("local_candidate_invalid")
    fields = value.get("field_observations")
    if not isinstance(fields, list):
        raise ListPageLocalRecognitionError("candidate_fields_incomplete")
    names = set()
    parsed = []
    for field in fields:
        if not isinstance(field, Mapping) or set(field) != {"name", "value", "confidence"}:
            raise ListPageLocalRecognitionError("local_list_token_unknown")
        name = field.get("name")
        if name not in _FIELD_NAMES:
            raise ListPageLocalRecognitionError("local_list_token_unknown")
        if name in names:
            raise ListPageLocalRecognitionError("candidate_field_conflict")
        if not _confidence(field.get("confidence")):
            raise ListPageLocalRecognitionError("candidate_field_confidence_too_low")
        names.add(name)
        parsed.append({"name": name, "value": field.get("value"), "confidence": float(field["confidence"])})
    if len(fields) != len(_FIELD_NAMES) or names != _FIELD_NAMES:
        raise ListPageLocalRecognitionError("candidate_fields_incomplete")
    return {
        "candidate_id": candidate_id,
        "region": region,
        "visual_fingerprint": fingerprint,
        "field_observations": parsed,
    }


def _confidence(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and MIN_FIELD_CONFIDENCE <= float(value) <= 1


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.casefold())
