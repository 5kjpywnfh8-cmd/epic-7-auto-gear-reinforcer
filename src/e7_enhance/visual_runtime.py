"""Offline fail-closed validation for structured visual enhancement evidence.

The module accepts already-parsed evidence only.  It deliberately contains no
device, OCR, network, snapshot, or game integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol


MODE = "visual_only"
VERIFICATION = "unverified"
MIN_STABLE_FRAMES = 3
MIN_FIELD_CONFIDENCE = 0.98


@dataclass(frozen=True)
class VisualEvidence:
    """A parsed visual sample whose source remains outside this module."""

    schema_version: str
    operation_id: str
    sample_id: str
    captured_at: str
    phase: str
    expected_node: int
    page: Mapping[str, Any]
    stability: Mapping[str, Any]
    anchors: tuple[Mapping[str, Any], ...]
    target: Mapping[str, Any]
    resource_preview: Mapping[str, Any]
    sampler: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "VisualEvidence":
        if not isinstance(value, Mapping):
            raise TypeError("visual evidence must be a mapping")
        anchors = value.get("anchors")
        return cls(
            schema_version=value.get("schema_version"),
            operation_id=value.get("operation_id"),
            sample_id=value.get("sample_id"),
            captured_at=value.get("captured_at"),
            phase=value.get("phase"),
            expected_node=value.get("expected_node"),
            page=value.get("page"),
            stability=value.get("stability"),
            anchors=tuple(anchors) if isinstance(anchors, list) else (),
            target=value.get("target"),
            resource_preview=value.get("resource_preview"),
            sampler=value.get("sampler"),
        )


@dataclass(frozen=True)
class ExpectedVisualState:
    """The state that one visual sample must prove before progressing."""

    node: int
    phase: str
    visual_fingerprint: str | None = None
    visible_fields: Mapping[str, Any] | None = None
    resource_values: Mapping[str, int] | None = None
    operation_id: str | None = None


@dataclass(frozen=True)
class VisualGateResult:
    status: str
    mode: str
    verification: str
    stop_reasons: tuple[str, ...]
    evidence_summary: Mapping[str, Any]

    @property
    def passed(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "verification": self.verification,
            "stop_reasons": list(self.stop_reasons),
            "evidence_summary": dict(self.evidence_summary),
        }


class VisualEvidenceGate:
    """Validate visual-only evidence without claiming server-side confirmation."""

    def evaluate(self, evidence: VisualEvidence, expected: ExpectedVisualState) -> VisualGateResult:
        reasons: list[str] = []
        if not isinstance(evidence, VisualEvidence) or not isinstance(expected, ExpectedVisualState):
            return self._failed(("invalid_visual_evidence",), {})

        if evidence.schema_version != "e7_enhance.visual_evidence/1.0":
            reasons.append("unsupported_visual_evidence_schema")
        if not _non_blank(evidence.operation_id) or not _non_blank(evidence.sample_id):
            reasons.append("missing_visual_evidence_identity")
        if expected.operation_id is not None and evidence.operation_id != expected.operation_id:
            reasons.append("operation_mismatch")
        if not _timezone_aware(evidence.captured_at):
            reasons.append("invalid_captured_at")
        if evidence.phase != expected.phase:
            reasons.append("phase_mismatch")
        if not _is_node(evidence.expected_node) or evidence.expected_node != expected.node:
            reasons.append("node_mismatch")

        self._validate_page(evidence.page, reasons)
        self._validate_stability(evidence.stability, reasons)
        self._validate_anchors(evidence.anchors, reasons)
        self._validate_target(evidence.target, expected, reasons)
        self._validate_resources(evidence.resource_preview, expected, reasons)
        self._validate_sampler(evidence.sampler, reasons)

        summary = {
            "operation_id": evidence.operation_id,
            "sample_id": evidence.sample_id,
            "phase": evidence.phase,
            "node": evidence.expected_node,
            "frame_hashes": list(evidence.stability.get("frame_hashes", ()))
            if isinstance(evidence.stability, Mapping)
            else [],
            "visual_fingerprint": evidence.target.get("visual_fingerprint")
            if isinstance(evidence.target, Mapping)
            else None,
        }
        if reasons:
            return self._failed(tuple(dict.fromkeys(reasons)), summary)
        return VisualGateResult("ready", MODE, VERIFICATION, (), summary)

    @staticmethod
    def _failed(reasons: tuple[str, ...], summary: Mapping[str, Any]) -> VisualGateResult:
        return VisualGateResult("fail_closed", MODE, VERIFICATION, reasons, summary)

    @staticmethod
    def _validate_page(page: Any, reasons: list[str]) -> None:
        if not isinstance(page, Mapping):
            reasons.append("page_not_confirmed")
            return
        if (
            _normal(page.get("page_type")) != "enhanceequipment"
            or page.get("is_unambiguous") is not True
            or page.get("target_visible") is not True
            or not _is_sha256(page.get("page_signature"))
        ):
            reasons.append("page_not_confirmed")

    @staticmethod
    def _validate_stability(stability: Any, reasons: list[str]) -> None:
        if not isinstance(stability, Mapping):
            reasons.append("unstable_visual_state")
            return
        sample_count = stability.get("sample_count")
        stable_count = stability.get("stable_count")
        hashes = stability.get("frame_hashes")
        if (
            not _is_positive_int(sample_count)
            or not _is_positive_int(stable_count)
            or sample_count < MIN_STABLE_FRAMES
            or stable_count < MIN_STABLE_FRAMES
            or stable_count > sample_count
            or not isinstance(hashes, list)
            or len(hashes) != sample_count
            or any(not _is_sha256(frame_hash) for frame_hash in hashes)
            or not _is_positive_int(stability.get("poll_interval_ms"))
            or not _is_positive_int(stability.get("timeout_ms"))
        ):
            reasons.append("unstable_visual_state")

    @staticmethod
    def _validate_anchors(anchors: tuple[Mapping[str, Any], ...], reasons: list[str]) -> None:
        names: set[str] = set()
        stable_anchor_count = 0
        for anchor in anchors:
            if not isinstance(anchor, Mapping):
                continue
            name = anchor.get("name")
            score = anchor.get("score")
            threshold = anchor.get("threshold")
            bright_ratio = anchor.get("bright_ratio")
            if (
                _non_blank(name)
                and name not in names
                and _is_unit_interval(score)
                and _is_unit_interval(threshold)
                and _is_unit_interval(bright_ratio)
                and score >= threshold
                and bright_ratio > 0
            ):
                names.add(name)
                stable_anchor_count += 1
        if stable_anchor_count < 2:
            reasons.append("local_anchors_not_confirmed")

    @staticmethod
    def _validate_target(target: Any, expected: ExpectedVisualState, reasons: list[str]) -> None:
        if not isinstance(target, Mapping):
            reasons.append("target_not_unique")
            return
        if target.get("candidate_count") != 1 or not _is_nonnegative_int(target.get("candidate_count")):
            reasons.append("target_not_unique")
        fields = target.get("visible_fields")
        confidence = target.get("field_confidence")
        if not isinstance(fields, Mapping) or not fields or not isinstance(confidence, Mapping):
            reasons.append("ocr_confidence_below_threshold")
        else:
            if set(fields) != set(confidence) or any(
                not _is_number(confidence.get(name)) or confidence[name] < MIN_FIELD_CONFIDENCE
                for name in fields
            ):
                reasons.append("ocr_confidence_below_threshold")
            if expected.visible_fields and any(fields.get(name) != value for name, value in expected.visible_fields.items()):
                reasons.append("target_identity_drift")
        fingerprint = target.get("visual_fingerprint")
        if not _is_sha256(fingerprint) or (
            expected.visual_fingerprint is not None and fingerprint != expected.visual_fingerprint
        ):
            reasons.append("target_identity_drift")

    @staticmethod
    def _validate_resources(preview: Any, expected: ExpectedVisualState, reasons: list[str]) -> None:
        if not isinstance(preview, Mapping) or preview.get("visible") is not True:
            reasons.append("resource_reconciliation_failed")
            return
        materials = preview.get("materials")
        gold = preview.get("gold")
        if not isinstance(materials, Mapping) or not _is_nonnegative_int(gold) or any(
            not _is_nonnegative_int(amount) for amount in materials.values()
        ):
            reasons.append("resource_reconciliation_failed")
            return
        if expected.resource_values:
            expected_materials = set(expected.resource_values) - {"gold"}
            if expected_materials and set(materials) != expected_materials:
                reasons.append("resource_reconciliation_failed")
            observed = dict(materials)
            observed["gold"] = gold
            if any(observed.get(name) != value for name, value in expected.resource_values.items()):
                reasons.append("resource_reconciliation_failed")

    @staticmethod
    def _validate_sampler(sampler: Any, reasons: list[str]) -> None:
        if not isinstance(sampler, Mapping) or any(
            not _non_blank(sampler.get(name)) for name in ("adapter", "template_set", "version")
        ):
            reasons.append("invalid_sampler_metadata")


@dataclass(frozen=True)
class SamplingRequest:
    operation_id: str
    phase: str
    expected_node: int


class VisualSampler(Protocol):
    """Produces parsed evidence; device and OCR adapters remain external."""

    def capture(self, request: SamplingRequest) -> VisualEvidence:
        ...


class VisualClickExecutor(Protocol):
    """The sole action seam for a separately-authorized single node."""

    def click_enhance(self) -> None:
        ...


@dataclass(frozen=True)
class VisualNodeRequest:
    operation_id: str
    from_node: int
    to_node: int
    visual_fingerprint: str
    visible_fields: Mapping[str, Any]
    resource_before: Mapping[str, int]
    planned_cost: Mapping[str, int]
    action_authorized: bool = False


@dataclass(frozen=True)
class VisualNodeResult:
    status: str
    mode: str
    verification: str
    click_sent: bool
    next_node: int | None
    stop_reasons: tuple[str, ...]
    resource_ledger: Mapping[str, Mapping[str, int]]
    pre_action: VisualGateResult | None
    post_action: VisualGateResult | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "verification": self.verification,
            "click_sent": self.click_sent,
            "next_node": self.next_node,
            "stop_reasons": list(self.stop_reasons),
            "resource_ledger": {name: dict(values) for name, values in self.resource_ledger.items()},
            "pre_action": self.pre_action.to_dict() if self.pre_action else None,
            "post_action": self.post_action.to_dict() if self.post_action else None,
        }


class VisualOnlyEnhanceExecutor:
    """Run exactly one visual node: pre-action, one action, post-action, stop."""

    def __init__(
        self,
        sampler: VisualSampler,
        click_executor: VisualClickExecutor,
        evidence_gate: VisualEvidenceGate | None = None,
    ) -> None:
        self._sampler = sampler
        self._click_executor = click_executor
        self._evidence_gate = evidence_gate or VisualEvidenceGate()
        self._attempted_nodes: set[tuple[str, int, int]] = set()
        self._seen_sample_ids: set[str] = set()
        self._seen_frame_hashes: set[str] = set()

    def run_node(self, request: VisualNodeRequest) -> VisualNodeResult:
        request_reasons, ledger = self._validate_request(request)
        if request_reasons:
            return self._failed(request_reasons, False, ledger)

        attempt_key = (request.operation_id, request.from_node, request.to_node)
        if attempt_key in self._attempted_nodes:
            return self._failed(("single_action_already_attempted",), False, ledger)

        pre_evidence, pre_capture_reason = self._capture(request, "pre_action", request.from_node)
        if pre_capture_reason:
            return self._failed((pre_capture_reason,), False, ledger)
        if self._is_stale(pre_evidence):
            return self._failed(("stale_visual_evidence_rejected",), False, ledger)
        pre_result = self._evidence_gate.evaluate(
            pre_evidence,
            self._expected(request, "pre_action", request.from_node, request.resource_before),
        )
        if not pre_result.passed:
            return self._failed(pre_result.stop_reasons, False, ledger, pre_result=pre_result)
        self._record_evidence(pre_evidence)

        # Record before invoking the action so an exception cannot enable a retry.
        self._attempted_nodes.add(attempt_key)
        try:
            self._click_executor.click_enhance()
        except Exception:
            return self._failed(("unknown_result",), True, ledger, pre_result=pre_result)

        post_evidence, post_capture_reason = self._capture(request, "post_action", request.to_node)
        if post_capture_reason:
            return self._failed(("unknown_result", post_capture_reason), True, ledger, pre_result=pre_result)
        if self._is_stale(post_evidence):
            return self._failed(
                ("unknown_result", "stale_visual_evidence_rejected"),
                True,
                ledger,
                pre_result=pre_result,
            )
        if not _captured_after(post_evidence.captured_at, pre_evidence.captured_at):
            return self._failed(
                ("unknown_result", "captured_at_not_increasing"),
                True,
                ledger,
                pre_result=pre_result,
            )
        post_result = self._evidence_gate.evaluate(
            post_evidence,
            self._expected(request, "post_action", request.to_node, ledger["expected_after"]),
        )
        if not post_result.passed:
            return self._failed(
                ("unknown_result",) + post_result.stop_reasons,
                True,
                ledger,
                pre_result=pre_result,
                post_result=post_result,
            )
        self._record_evidence(post_evidence)
        return VisualNodeResult(
            status="completed_unverified",
            mode=MODE,
            verification=VERIFICATION,
            click_sent=True,
            next_node=request.to_node,
            stop_reasons=(),
            resource_ledger=ledger,
            pre_action=pre_result,
            post_action=post_result,
        )

    def _capture(
        self, request: VisualNodeRequest, phase: str, node: int
    ) -> tuple[VisualEvidence | None, str | None]:
        try:
            evidence = self._sampler.capture(SamplingRequest(request.operation_id, phase, node))
        except Exception:
            return None, "sample_capture_failed"
        if isinstance(evidence, Mapping):
            try:
                evidence = VisualEvidence.from_mapping(evidence)
            except (TypeError, ValueError):
                return None, "invalid_visual_evidence"
        if not isinstance(evidence, VisualEvidence):
            return None, "invalid_visual_evidence"
        return evidence, None

    def _is_stale(self, evidence: VisualEvidence) -> bool:
        frame_hashes = evidence.stability.get("frame_hashes", ()) if isinstance(evidence.stability, Mapping) else ()
        return evidence.sample_id in self._seen_sample_ids or (
            isinstance(frame_hashes, list) and bool(set(frame_hashes) & self._seen_frame_hashes)
        )

    def _record_evidence(self, evidence: VisualEvidence) -> None:
        self._seen_sample_ids.add(evidence.sample_id)
        if isinstance(evidence.stability, Mapping):
            frame_hashes = evidence.stability.get("frame_hashes", ())
            if isinstance(frame_hashes, list):
                self._seen_frame_hashes.update(frame_hashes)

    @staticmethod
    def _expected(
        request: VisualNodeRequest,
        phase: str,
        node: int,
        resources: Mapping[str, int],
    ) -> ExpectedVisualState:
        return ExpectedVisualState(
            node=node,
            phase=phase,
            visual_fingerprint=request.visual_fingerprint,
            visible_fields=request.visible_fields,
            resource_values=resources,
            operation_id=request.operation_id,
        )

    @staticmethod
    def _validate_request(
        request: Any,
    ) -> tuple[tuple[str, ...], Mapping[str, Mapping[str, int]]]:
        if not isinstance(request, VisualNodeRequest):
            return ("invalid_node_request",), {}
        reasons: list[str] = []
        if request.action_authorized is not True:
            reasons.append("single_action_not_authorized")
        if not _non_blank(request.operation_id) or not _is_sha256(request.visual_fingerprint):
            reasons.append("invalid_node_request")
        if not _is_valid_next_node(request.from_node, request.to_node):
            reasons.append("node_sequence_jump")
        if not isinstance(request.visible_fields, Mapping) or not request.visible_fields:
            reasons.append("invalid_node_request")
        if not _valid_resources(request.resource_before) or not _valid_resources(request.planned_cost):
            reasons.append("invalid_resource_ledger")
            return tuple(dict.fromkeys(reasons)), {}
        before = dict(request.resource_before)
        cost = dict(request.planned_cost)
        if set(before) != set(cost) or any(cost[name] > before[name] for name in before):
            reasons.append("visual_budget_exceeded")
        after = {name: before[name] - cost[name] for name in before}
        return tuple(dict.fromkeys(reasons)), {
            "before": before,
            "planned": cost,
            "expected_after": after,
        }

    @staticmethod
    def _failed(
        reasons: tuple[str, ...],
        click_sent: bool,
        ledger: Mapping[str, Mapping[str, int]],
        pre_result: VisualGateResult | None = None,
        post_result: VisualGateResult | None = None,
    ) -> VisualNodeResult:
        return VisualNodeResult(
            status="fail_closed",
            mode=MODE,
            verification=VERIFICATION,
            click_sent=click_sent,
            next_node=None,
            stop_reasons=tuple(dict.fromkeys(reasons)),
            resource_ledger=ledger,
            pre_action=pre_result,
            post_action=post_result,
        )


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timezone_aware(value: Any) -> bool:
    if not _non_blank(value):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _is_node(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_unit_interval(value: Any) -> bool:
    return _is_number(value) and 0 <= value <= 1


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.casefold())


def _captured_after(current: Any, previous: Any) -> bool:
    if not _timezone_aware(current) or not _timezone_aware(previous):
        return False
    current_dt = datetime.fromisoformat(current.replace("Z", "+00:00"))
    previous_dt = datetime.fromisoformat(previous.replace("Z", "+00:00"))
    return current_dt > previous_dt


def _is_valid_next_node(from_node: Any, to_node: Any) -> bool:
    nodes = (0, 3, 6, 9, 12, 15)
    return (
        _is_node(from_node)
        and _is_node(to_node)
        and from_node in nodes
        and to_node in nodes
        and nodes.index(to_node) == nodes.index(from_node) + 1
    )


def _valid_resources(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value) and all(
        isinstance(name, str) and _is_nonnegative_int(amount) for name, amount in value.items()
    )


def _normal(value: Any) -> str:
    return value.casefold().replace("_", "").replace("-", "").replace(" ", "") if isinstance(value, str) else ""
