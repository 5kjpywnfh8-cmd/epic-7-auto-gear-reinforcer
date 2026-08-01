"""Offline fail-closed contracts for list-to-enhance visual navigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol

from .visual_click import NormalizedClickTarget
from .visual_runtime import MIN_FIELD_CONFIDENCE, MODE, VERIFICATION, VisualNodeRequest, VisualNodeResult


MIN_STABLE_FRAMES = 3


@dataclass(frozen=True)
class NavigationPageEvidence:
    """One already-parsed, stable visual page sample.

    This type does not capture frames or invoke OCR.  Integrations must supply
    the stable-frame record produced by the existing visual adapter.
    """

    operation_id: str
    captured_at: str
    page_type: str
    page_signature: str
    viewport: tuple[int, int]
    stability: Mapping[str, Any]
    anchors: tuple[Mapping[str, Any], ...]
    candidates: tuple[Mapping[str, Any], ...] = ()
    target_visible: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "NavigationPageEvidence":
        if not isinstance(value, Mapping):
            raise TypeError("navigation evidence must be a mapping")
        anchors = value.get("anchors")
        candidates = value.get("candidates")
        viewport = value.get("viewport")
        return cls(
            operation_id=value.get("operation_id"),
            captured_at=value.get("captured_at"),
            page_type=value.get("page_type"),
            page_signature=value.get("page_signature"),
            viewport=tuple(viewport) if isinstance(viewport, (tuple, list)) else (),
            stability=value.get("stability"),
            anchors=tuple(anchors) if isinstance(anchors, list) else (),
            candidates=tuple(candidates) if isinstance(candidates, list) else (),
            target_visible=value.get("target_visible") is True,
        )


@dataclass(frozen=True)
class NavigationResult:
    status: str
    mode: str
    verification: str
    stop_reasons: tuple[str, ...]
    candidate_id: str | None = None
    visual_fingerprint: str | None = None
    click_target: NormalizedClickTarget | None = None

    @property
    def passed(self) -> bool:
        return self.status == "ready"


class NavigationEvidenceGate:
    """Validate list identity, button anchors, and page transitions offline."""

    def locate_unique_target(
        self,
        evidence: NavigationPageEvidence,
        expected_fields: Mapping[str, Any],
    ) -> NavigationResult:
        reasons = self._validate_page(evidence, "equipment_list")
        if not _valid_fields(expected_fields):
            reasons.append("invalid_target_fingerprint")
        matches: list[Mapping[str, Any]] = []
        for candidate in evidence.candidates:
            if self._candidate_matches(candidate, expected_fields):
                matches.append(candidate)
        if len(matches) != 1:
            reasons.append("target_not_unique")
        if reasons:
            return _failed(reasons)
        candidate = matches[0]
        return NavigationResult(
            "ready",
            MODE,
            VERIFICATION,
            (),
            candidate_id=candidate["candidate_id"],
            visual_fingerprint=candidate["visual_fingerprint"],
        )

    def derive_anchor_click(
        self,
        evidence: NavigationPageEvidence,
        *,
        required_page: str,
        anchor_name: str,
        target_visible: bool,
    ) -> NavigationResult:
        reasons = self._validate_page(evidence, required_page)
        if target_visible and evidence.target_visible is not True:
            reasons.append("target_not_visible")
        anchor = self._find_anchor(evidence.anchors, anchor_name)
        if anchor is None:
            reasons.append("button_anchor_not_confirmed")
        if reasons:
            return _failed(reasons)
        bounds = anchor["bounds"]
        return NavigationResult(
            "ready",
            MODE,
            VERIFICATION,
            (),
            click_target=NormalizedClickTarget(
                (bounds["left"] + bounds["right"]) / 2,
                (bounds["top"] + bounds["bottom"]) / 2,
            ),
        )

    def verify_transition(
        self,
        before: NavigationPageEvidence,
        after: NavigationPageEvidence,
        *,
        expected_after_page: str,
        expected_fingerprint: str | None = None,
    ) -> NavigationResult:
        reasons = self._validate_page(before, before.page_type)
        reasons.extend(self._validate_page(after, expected_after_page))
        if before.operation_id != after.operation_id:
            reasons.append("operation_mismatch")
        if not _captured_after(after.captured_at, before.captured_at):
            reasons.append("captured_at_not_increasing")
        if before.page_signature == after.page_signature:
            reasons.append("page_transition_not_observed")
        if _frame_hashes_overlap(before.stability, after.stability):
            reasons.append("stale_visual_evidence_rejected")
        if after.target_visible is not True:
            reasons.append("target_not_visible")
        if expected_fingerprint is not None and not _has_fingerprint(after.candidates, expected_fingerprint):
            reasons.append("target_identity_drift")
        return _failed(reasons) if reasons else NavigationResult("ready", MODE, VERIFICATION, ())

    @staticmethod
    def _validate_page(evidence: Any, expected_page: str) -> list[str]:
        if not isinstance(evidence, NavigationPageEvidence):
            return ["invalid_navigation_evidence"]
        reasons: list[str] = []
        if not _non_blank(evidence.operation_id) or not _timezone_aware(evidence.captured_at):
            reasons.append("invalid_navigation_evidence")
        if _normal(evidence.page_type) != _normal(expected_page) or not _is_sha256(evidence.page_signature):
            reasons.append("page_not_confirmed")
        if not _valid_viewport(evidence.viewport) or not _stable(
            evidence.stability,
            allow_list_hash_variation=_normal(evidence.page_type) == "equipmentlist",
        ):
            reasons.append("unstable_visual_state")
        if _stable_anchor_count(evidence.anchors) < 2:
            reasons.append("local_anchors_not_confirmed")
        return reasons

    @staticmethod
    def _candidate_matches(candidate: Any, expected_fields: Mapping[str, Any]) -> bool:
        if not isinstance(candidate, Mapping):
            return False
        fields = candidate.get("visible_fields")
        confidence = candidate.get("field_confidence")
        if (
            not _non_blank(candidate.get("candidate_id"))
            or not _is_sha256(candidate.get("visual_fingerprint"))
            or not isinstance(fields, Mapping)
            or not isinstance(confidence, Mapping)
        ):
            return False
        return all(
            fields.get(name) == value
            and _is_number(confidence.get(name))
            and confidence[name] >= MIN_FIELD_CONFIDENCE
            for name, value in expected_fields.items()
        )

    @staticmethod
    def _find_anchor(anchors: tuple[Mapping[str, Any], ...], name: str) -> Mapping[str, Any] | None:
        matches = []
        for anchor in anchors:
            if not isinstance(anchor, Mapping) or anchor.get("name") != name:
                continue
            bounds = anchor.get("bounds")
            score = anchor.get("score")
            threshold = anchor.get("threshold")
            if (
                _is_number(score)
                and _is_number(threshold)
                and MIN_FIELD_CONFIDENCE <= threshold <= score <= 1
                and _valid_bounds(bounds)
            ):
                matches.append(anchor)
        return matches[0] if len(matches) == 1 else None


class VisualNodeRunner(Protocol):
    def run_node(self, request: VisualNodeRequest) -> VisualNodeResult:
        ...


class VisualNodeChain:
    """Require every later node to use the accepted prior posterior ledger."""

    def __init__(self, runner: VisualNodeRunner) -> None:
        self._runner = runner
        self._operation_id: str | None = None
        self._next_node: int | None = None
        self._expected_resources: Mapping[str, int] | None = None
        self._stopped = False

    def run_node(self, request: VisualNodeRequest) -> VisualNodeResult:
        if self._stopped:
            return _failed_node("operation_chain_stopped")
        if self._operation_id is None:
            self._operation_id = request.operation_id
        elif (
            request.operation_id != self._operation_id
            or request.from_node != self._next_node
            or dict(request.resource_before) != dict(self._expected_resources or {})
        ):
            self._stopped = True
            return _failed_node("prior_posterior_ledger_mismatch")

        result = self._runner.run_node(request)
        if result.status != "completed_unverified" or result.post_action is None or result.next_node is None:
            self._stopped = True
            return result
        expected_after = result.resource_ledger.get("expected_after")
        if not _valid_resource_ledger(expected_after):
            self._stopped = True
            return _failed_node("prior_posterior_ledger_missing")
        self._next_node = result.next_node
        self._expected_resources = dict(expected_after)
        return result


def _failed(reasons: list[str]) -> NavigationResult:
    return NavigationResult("fail_closed", MODE, VERIFICATION, tuple(dict.fromkeys(reasons)))


def _failed_node(reason: str) -> VisualNodeResult:
    return VisualNodeResult("fail_closed", MODE, VERIFICATION, False, None, (reason,), {}, None, None)


def _stable(value: Any, *, allow_list_hash_variation: bool = False) -> bool:
    if not isinstance(value, Mapping):
        return False
    hashes = value.get("frame_hashes")
    return (
        value.get("sample_count") == MIN_STABLE_FRAMES
        and value.get("stable_count") == MIN_STABLE_FRAMES
        and isinstance(hashes, list)
        and len(hashes) == MIN_STABLE_FRAMES
        and (
            len(set(hashes)) == 1
            or (allow_list_hash_variation and value.get("visual_fields_stable") is True)
        )
        and all(_is_sha256(item) for item in hashes)
    )


def _frame_hashes_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_hashes = left.get("frame_hashes") if isinstance(left, Mapping) else ()
    right_hashes = right.get("frame_hashes") if isinstance(right, Mapping) else ()
    return isinstance(left_hashes, list) and isinstance(right_hashes, list) and bool(set(left_hashes) & set(right_hashes))


def _stable_anchor_count(anchors: tuple[Mapping[str, Any], ...]) -> int:
    names: set[str] = set()
    for anchor in anchors:
        if not isinstance(anchor, Mapping):
            continue
        name = anchor.get("name")
        score = anchor.get("score")
        threshold = anchor.get("threshold")
        if _non_blank(name) and name not in names and _is_number(score) and _is_number(threshold) and MIN_FIELD_CONFIDENCE <= threshold <= score <= 1:
            names.add(name)
    return len(names)


def _valid_fields(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value) and all(_non_blank(name) for name in value)


def _valid_resource_ledger(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value) and all(
        _non_blank(name) and isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0
        for name, amount in value.items()
    )


def _valid_viewport(value: Any) -> bool:
    return isinstance(value, tuple) and len(value) == 2 and all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in value
    )


def _valid_bounds(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        left, top, right, bottom = (float(value[key]) for key in ("left", "top", "right", "bottom"))
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= left < right <= 1 and 0 <= top < bottom <= 1


def _has_fingerprint(candidates: tuple[Mapping[str, Any], ...], fingerprint: str) -> bool:
    return sum(candidate.get("visual_fingerprint") == fingerprint for candidate in candidates if isinstance(candidate, Mapping)) == 1


def _captured_after(current: Any, previous: Any) -> bool:
    if not _timezone_aware(current) or not _timezone_aware(previous):
        return False
    return datetime.fromisoformat(current.replace("Z", "+00:00")) > datetime.fromisoformat(previous.replace("Z", "+00:00"))


def _timezone_aware(value: Any) -> bool:
    if not _non_blank(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.casefold())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normal(value: Any) -> str:
    return value.casefold().replace("_", "").replace("-", "").replace(" ", "") if isinstance(value, str) else ""
