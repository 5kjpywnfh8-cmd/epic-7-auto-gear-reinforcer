"""Fail-closed, dry-run planning from injected visual sampling evidence.

This prototype intentionally has no device, OCR, Airtest, ADB, or network
dependency.  A future integration may supply a sampler and a click executor,
but this module never invokes the executor.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Protocol


RESOURCE_KEYS = ("powder", "lower_enhance_stone", "upper_enhance_stone", "gold")
PLUS_ZERO_TO_THREE_COST = {
    "powder": 2,
    "lower_enhance_stone": 1,
    "upper_enhance_stone": 0,
    "gold": 17600,
}


class ScreenshotSampler(Protocol):
    """Provides already-parsed visual sampling evidence without device access."""

    def capture(self) -> Mapping[str, Any]:
        ...


class ClickExecutor(Protocol):
    """Reserved for a separately authorized future integration."""

    def click_enhance(self) -> None:
        ...


@dataclass(frozen=True)
class VisualSamplingDecision:
    status: str
    next_action: str | None
    dry_run: bool
    click_sent: bool
    stop_reasons: tuple[str, ...]
    resource_ledger: dict[str, dict[str, int]]
    evidence_summary: dict[str, Any]
    mode: str = "visual_only"
    verification: str = "unverified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "next_action": self.next_action,
            "dry_run": self.dry_run,
            "click_sent": self.click_sent,
            "stop_reasons": list(self.stop_reasons),
            "resource_ledger": self.resource_ledger,
            "evidence_summary": self.evidence_summary,
            "mode": self.mode,
            "verification": self.verification,
        }


class PureVisualSamplingExecutor:
    """Validate one visual sample and propose only the dry-run ``+0 -> +3`` step."""

    def __init__(
        self,
        sampler: ScreenshotSampler | None = None,
        click_executor: ClickExecutor | None = None,
    ) -> None:
        self._sampler = sampler
        # Kept only to make the future integration seam explicit.  This module
        # never reads or calls it, including for a successful dry-run decision.
        self._click_executor = click_executor

    def evaluate(self, sample: Mapping[str, Any] | None = None) -> VisualSamplingDecision:
        if sample is None:
            if self._sampler is None:
                return self._failed(("sample_not_provided",))
            try:
                sample = self._sampler.capture()
            except Exception:
                return self._failed(("sample_capture_failed",))

        if not isinstance(sample, Mapping):
            return self._failed(("invalid_sample_mapping",))

        reasons: list[str] = []
        for field in ("sample_id", "captured_at", "page", "resource_caps", "targets"):
            if field not in sample or _is_blank(sample[field]):
                reasons.append(f"missing_{field}")

        page = sample.get("page")
        if not _is_valid_enhance_page(page):
            reasons.append("page_not_unambiguous_enhance_equipment")

        targets = sample.get("targets")
        target: Mapping[str, Any] | None = None
        candidate_count = 0
        if isinstance(targets, list):
            candidate_count = len(targets)
            if candidate_count == 1 and isinstance(targets[0], Mapping):
                target = targets[0]
            else:
                reasons.append("target_not_unique")
        elif "targets" in sample:
            reasons.append("target_not_unique")

        current_node: int | None = None
        if target is not None:
            if not _matches_target(target):
                reasons.append("target_mismatch")
            current_node = target.get("enhance") if isinstance(target.get("enhance"), int) else None
            if current_node != 0:
                reasons.append("unsupported_enhancement_node")

        caps, cap_reasons = _resource_caps(sample.get("resource_caps"))
        reasons.extend(cap_reasons)
        ledger = _ledger(caps)
        if caps and any(PLUS_ZERO_TO_THREE_COST[key] > caps[key] for key in RESOURCE_KEYS):
            reasons.append("resource_cap_exceeded")

        evidence = {
            "sample_id": sample.get("sample_id") if isinstance(sample.get("sample_id"), str) else None,
            "captured_at": sample.get("captured_at") if isinstance(sample.get("captured_at"), str) else None,
            "page_kind": page.get("kind") if isinstance(page, Mapping) else None,
            "candidate_count": candidate_count,
            "current_node": current_node,
        }
        if reasons:
            return self._failed(tuple(dict.fromkeys(reasons)), ledger, evidence)

        return VisualSamplingDecision(
            status="ready",
            next_action="dry_run_propose_enhance_to_plus3",
            dry_run=True,
            click_sent=False,
            stop_reasons=(),
            resource_ledger=ledger,
            evidence_summary=evidence,
        )

    @staticmethod
    def _failed(
        reasons: tuple[str, ...],
        ledger: dict[str, dict[str, int]] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> VisualSamplingDecision:
        return VisualSamplingDecision(
            status="fail_closed",
            next_action=None,
            dry_run=True,
            click_sent=False,
            stop_reasons=reasons,
            resource_ledger=ledger or {},
            evidence_summary=evidence or {},
        )


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _is_valid_enhance_page(page: Any) -> bool:
    return (
        isinstance(page, Mapping)
        and _normal(page.get("kind")) == "enhanceequipment"
        and page.get("is_unambiguous") is True
    )


def _resource_caps(value: Any) -> tuple[dict[str, int], tuple[str, ...]]:
    if not isinstance(value, Mapping):
        return {}, ("invalid_resource_caps",)

    missing = tuple(f"missing_resource_cap_{key}" for key in RESOURCE_KEYS if key not in value)
    if missing:
        return {}, missing
    caps = {key: value[key] for key in RESOURCE_KEYS}
    if any(not isinstance(amount, int) or isinstance(amount, bool) or amount < 0 for amount in caps.values()):
        return {}, ("invalid_resource_caps",)
    return caps, ()


def _ledger(caps: dict[str, int]) -> dict[str, dict[str, int]]:
    if not caps:
        return {}
    return {
        "caps": dict(caps),
        "planned": dict(PLUS_ZERO_TO_THREE_COST),
        "remaining": {key: caps[key] - PLUS_ZERO_TO_THREE_COST[key] for key in RESOURCE_KEYS},
    }


def _matches_target(target: Mapping[str, Any]) -> bool:
    if _normal(target.get("rank")) not in {"epic", "red", "redgear", "红装"}:
        return False
    if target.get("level") != 85:
        return False
    if _normal(target.get("slot")) not in {"weapon", "武器"}:
        return False
    if _normal(target.get("set")) not in {
        "criticaldamageset",
        "criticaldamage",
        "critdamageset",
        "爆伤套",
    }:
        return False
    main = target.get("main")
    if not isinstance(main, Mapping) or _normal(main.get("type")) not in {"attack", "攻击"} or main.get("value") != 100:
        return False
    substats = target.get("substats")
    if not isinstance(substats, list):
        return False
    observed = Counter()
    for substat in substats:
        if not isinstance(substat, Mapping) or not isinstance(substat.get("value"), int):
            return False
        observed[(_canonical_stat(substat.get("type")), substat["value"])] += 1
    return observed == Counter(
        {
            ("healthpercent", 4): 1,
            ("criticalhitdamagepercent", 4): 1,
            ("criticalhitchancepercent", 5): 1,
            ("speed", 2): 1,
        }
    )


def _canonical_stat(value: Any) -> str:
    normalized = _normal(value)
    aliases = {
        "生命%": "healthpercent",
        "healthpercent": "healthpercent",
        "爆伤%": "criticalhitdamagepercent",
        "criticalhitdamagepercent": "criticalhitdamagepercent",
        "暴击%": "criticalhitchancepercent",
        "criticalhitchancepercent": "criticalhitchancepercent",
        "速度": "speed",
        "speed": "speed",
    }
    return aliases.get(normalized, normalized)


def _normal(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.casefold().replace(" ", "").replace("_", "").replace("-", "")
