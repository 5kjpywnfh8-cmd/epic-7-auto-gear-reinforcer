"""Fail-closed, in-memory parsing contracts for an equipment list page.

This module deliberately accepts already-produced local observations.  It does
not capture frames, run OCR, or derive device-specific coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from .visual_navigation import NavigationPageEvidence
from .visual_runtime import MIN_FIELD_CONFIDENCE, MODE, VERIFICATION


REQUIRED_ANCHORS = ("list_header", "sort_button")
REQUIRED_REGIONS = ("list_header_region", "candidate_list_region")


@dataclass(frozen=True)
class FieldObservation:
    """One precomputed field value and its local recognition confidence."""

    name: str
    value: Any
    confidence: float


@dataclass(frozen=True)
class ListPageAnchor:
    """A named list-page anchor, represented only by its local score."""

    name: str
    score: float
    threshold: float


@dataclass(frozen=True)
class LocalRegion:
    """A normalized local region inside the current viewport."""

    name: str
    bounds: Mapping[str, float]
    score: float
    threshold: float


@dataclass(frozen=True)
class CandidateCard:
    """One visible candidate card with normalized bounds and field readings."""

    candidate_id: str
    visual_fingerprint: str
    bounds: Mapping[str, float]
    field_observations: tuple[FieldObservation, ...]


@dataclass(frozen=True)
class ListPageParseResult:
    status: str
    mode: str
    verification: str
    stop_reasons: tuple[str, ...]
    evidence: NavigationPageEvidence | None = None
    candidate_id: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "ready"


class EquipmentListVisualParser:
    """Convert explicit local list observations into navigation evidence.

    The parser treats every malformed, repeated, incomplete, or ambiguous
    observation as a terminal condition.  No click target is represented by
    this result.
    """

    def parse(self, observation: Mapping[str, Any], expected_fields: Mapping[str, Any]) -> ListPageParseResult:
        if not isinstance(observation, Mapping) or not _valid_expected_fields(expected_fields):
            return _failed("invalid_list_observation")

        reasons: list[str] = []
        anchors = observation.get("anchors")
        regions = observation.get("regions")
        visible_bounds = observation.get("visible_bounds")
        cards = observation.get("candidates")

        if not _valid_page_metadata(observation):
            reasons.append("invalid_list_observation")
        if not _valid_anchors(anchors):
            reasons.append("list_anchors_not_confirmed")
        if not _valid_regions(regions):
            reasons.append("local_regions_not_confirmed")
        if not _valid_bounds(visible_bounds):
            reasons.append("visible_boundary_not_confirmed")
        if observation.get("scroll_state") != "not_scrolled" or not _known_page_boundary(observation.get("page_boundary")):
            reasons.append("scroll_or_page_boundary_unknown")

        candidate_list_region = _find_region(regions, "candidate_list_region")
        parsed_cards, card_reasons = _parse_cards(cards, visible_bounds, candidate_list_region, expected_fields)
        reasons.extend(card_reasons)
        target_cards = [card for card in parsed_cards if _matches_expected_fields(card["visible_fields"], expected_fields)]
        if not card_reasons and len(target_cards) != 1:
            reasons.append("target_not_unique")
        if reasons:
            return _failed(*reasons)

        target = target_cards[0]
        evidence = NavigationPageEvidence.from_mapping(
            {
                "operation_id": observation["operation_id"],
                "captured_at": observation["captured_at"],
                "page_type": "equipment_list",
                "page_signature": observation["page_signature"],
                "viewport": observation["viewport"],
                "stability": observation["stability"],
                "anchors": anchors,
                "candidates": parsed_cards,
                "target_visible": True,
            }
        )
        return ListPageParseResult("ready", MODE, VERIFICATION, (), evidence, target["candidate_id"])


def _parse_cards(
    value: Any,
    visible_bounds: Any,
    candidate_list_region: Any,
    expected_fields: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        return [], ["no_visible_candidates"]
    if not _valid_bounds(visible_bounds):
        return [], ["visible_boundary_not_confirmed"]
    if not isinstance(candidate_list_region, Mapping) or not _valid_bounds(candidate_list_region.get("bounds")):
        return [], ["candidate_list_region_not_confirmed"]

    reasons: list[str] = []
    cards: list[dict[str, Any]] = []
    candidate_ids: set[str] = set()
    fingerprints: set[str] = set()
    for item in value:
        card, card_reasons = _parse_card(item, visible_bounds, candidate_list_region, expected_fields)
        reasons.extend(card_reasons)
        if card is None:
            continue
        if card["candidate_id"] in candidate_ids or card["visual_fingerprint"] in fingerprints:
            reasons.append("duplicate_candidate_detected")
        candidate_ids.add(card["candidate_id"])
        fingerprints.add(card["visual_fingerprint"])
        cards.append(card)
    return cards, reasons


def _parse_card(
    value: Any,
    visible_bounds: Mapping[str, Any],
    candidate_list_region: Mapping[str, Any],
    expected_fields: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, Mapping):
        return None, ["invalid_candidate_card"]
    candidate_id = value.get("candidate_id")
    fingerprint = value.get("visual_fingerprint")
    bounds = value.get("bounds")
    if not _non_blank(candidate_id) or not _is_sha256(fingerprint) or not _valid_bounds(bounds):
        return None, ["invalid_candidate_card"]
    if not _inside(bounds, visible_bounds):
        return None, ["candidate_outside_visible_boundary"]
    if not _inside(bounds, candidate_list_region.get("bounds")):
        return None, ["candidate_outside_candidate_list_region"]

    observations = value.get("field_observations")
    if not isinstance(observations, list):
        return None, ["candidate_fields_incomplete"]
    fields: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    for field in observations:
        if not isinstance(field, Mapping) or not _non_blank(field.get("name")) or not _is_number(field.get("confidence")):
            return None, ["candidate_fields_incomplete"]
        name = field["name"]
        if name in fields:
            return None, ["candidate_field_conflict"]
        fields[name] = field.get("value")
        confidence[name] = float(field["confidence"])
    for name in expected_fields:
        if name not in fields:
            return None, ["candidate_fields_incomplete"]
        if confidence[name] < MIN_FIELD_CONFIDENCE or confidence[name] > 1:
            return None, ["candidate_field_confidence_too_low"]
    return {
        "candidate_id": candidate_id,
        "visual_fingerprint": fingerprint,
        "visible_fields": fields,
        "field_confidence": confidence,
    }, []


def _valid_page_metadata(value: Mapping[str, Any]) -> bool:
    viewport = value.get("viewport")
    stability = value.get("stability")
    hashes = stability.get("frame_hashes") if isinstance(stability, Mapping) else None
    return (
        _non_blank(value.get("operation_id"))
        and _timezone_aware(value.get("captured_at"))
        and _is_sha256(value.get("page_signature"))
        and isinstance(viewport, (tuple, list))
        and len(viewport) == 2
        and all(isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in viewport)
        and isinstance(stability, Mapping)
        and stability.get("sample_count") == 3
        and stability.get("stable_count") == 3
        and isinstance(hashes, list)
        and len(hashes) == 3
        and all(_is_sha256(item) for item in hashes)
    )


def _valid_anchors(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    counts = {name: 0 for name in REQUIRED_ANCHORS}
    for anchor in value:
        if not isinstance(anchor, Mapping):
            return False
        name = anchor.get("name")
        score = anchor.get("score")
        threshold = anchor.get("threshold")
        if name in counts and _is_number(score) and _is_number(threshold) and MIN_FIELD_CONFIDENCE <= threshold <= score <= 1:
            counts[name] += 1
    return all(count == 1 for count in counts.values())


def _valid_regions(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    counts = {name: 0 for name in REQUIRED_REGIONS}
    for region in value:
        if not isinstance(region, Mapping):
            return False
        name = region.get("name")
        score = region.get("score")
        threshold = region.get("threshold")
        if (
            name in counts
            and _valid_bounds(region.get("bounds"))
            and _is_number(score)
            and _is_number(threshold)
            and MIN_FIELD_CONFIDENCE <= threshold <= score <= 1
        ):
            counts[name] += 1
    return all(count == 1 for count in counts.values())


def _find_region(value: Any, name: str) -> Mapping[str, Any] | None:
    if not isinstance(value, list):
        return None
    matches = [region for region in value if isinstance(region, Mapping) and region.get("name") == name]
    return matches[0] if len(matches) == 1 else None


def _known_page_boundary(value: Any) -> bool:
    return isinstance(value, Mapping) and all(isinstance(value.get(name), bool) for name in ("top_visible", "bottom_visible"))


def _valid_expected_fields(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value) and all(_non_blank(name) for name in value)


def _matches_expected_fields(fields: Mapping[str, Any], expected_fields: Mapping[str, Any]) -> bool:
    return all(fields.get(name) == expected for name, expected in expected_fields.items())


def _inside(inner: Mapping[str, Any], outer: Mapping[str, Any]) -> bool:
    return all(float(outer[name]) <= float(inner[name]) for name in ("left", "top")) and all(
        float(inner[name]) <= float(outer[name]) for name in ("right", "bottom")
    )


def _valid_bounds(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        left, top, right, bottom = (float(value[name]) for name in ("left", "top", "right", "bottom"))
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= left < right <= 1 and 0 <= top < bottom <= 1


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.casefold())


def _timezone_aware(value: Any) -> bool:
    if not _non_blank(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _failed(*reasons: str) -> ListPageParseResult:
    return ListPageParseResult("fail_closed", MODE, VERIFICATION, tuple(dict.fromkeys(reasons)))
