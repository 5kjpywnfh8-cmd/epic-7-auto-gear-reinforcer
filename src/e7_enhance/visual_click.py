"""Fail-closed, dependency-injected visual click execution.

This module translates a normalized point into the current viewport and hands
one click to an external backend.  It deliberately has no desktop, emulator,
ADB, OCR, or screenshot dependency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


class VisualClickError(RuntimeError):
    """Base error for a click that was refused or whose result is unknown."""


class ClickAuthorizationError(VisualClickError):
    """The caller did not explicitly authorize the single action."""


class ClickAlreadyAttemptedError(VisualClickError):
    """A second action was requested for the same click executor."""


class ClickTargetError(VisualClickError):
    """The target or current viewport could not be validated."""


class ClickResultUnknownError(VisualClickError):
    """The backend failed after the click attempt was committed."""


class WindowClickBackend(Protocol):
    """Minimal external window backend required by the click executor."""

    def viewport_size(self) -> tuple[int, int]:
        ...

    def click(self, x: int, y: int) -> None:
        ...


@dataclass(frozen=True)
class NormalizedClickTarget:
    """A click point expressed as fractions of the active viewport."""

    x: float
    y: float


@dataclass(frozen=True)
class ClickRecord:
    """The pixel point selected immediately before the backend call."""

    x: int
    y: int
    viewport_width: int
    viewport_height: int


class NormalizedClickExecutor:
    """Execute at most one explicitly-authorized click through a backend.

    The attempt flag is committed before calling the backend.  Therefore a
    backend exception cannot be followed by an automatic retry, and callers
    must treat the result as unknown until a fresh visual sample resolves it.
    """

    def __init__(
        self,
        backend: WindowClickBackend,
        target: NormalizedClickTarget,
        *,
        action_authorized: bool = False,
    ) -> None:
        self._backend = backend
        self._target = target
        self._action_authorized = action_authorized
        self._attempted = False
        self._last_click: ClickRecord | None = None

    @property
    def attempted(self) -> bool:
        return self._attempted

    @property
    def last_click(self) -> ClickRecord | None:
        return self._last_click

    def click_enhance(self) -> None:
        """Commit and perform one click, or fail closed without retry."""

        if self._attempted:
            raise ClickAlreadyAttemptedError("enhance click already attempted")

        # Commit before any backend interaction.  Every failure after this
        # point is intentionally terminal for this executor instance.
        self._attempted = True
        if self._action_authorized is not True:
            raise ClickAuthorizationError("single enhance click is not authorized")

        record = self._resolve_target()
        self._last_click = record
        try:
            self._backend.click(record.x, record.y)
        except Exception as exc:
            raise ClickResultUnknownError("window click result is unknown") from exc

    def _resolve_target(self) -> ClickRecord:
        _validate_target(self._target)
        try:
            viewport = self._backend.viewport_size()
        except Exception as exc:
            raise ClickTargetError("viewport size is unavailable") from exc
        width, height = _validate_viewport(viewport)
        return ClickRecord(
            x=round(self._target.x * (width - 1)),
            y=round(self._target.y * (height - 1)),
            viewport_width=width,
            viewport_height=height,
        )


def _validate_target(target: NormalizedClickTarget) -> None:
    if not isinstance(target, NormalizedClickTarget):
        raise ClickTargetError("click target must be normalized")
    for value in (target.x, target.y):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ClickTargetError("normalized click target must be finite and within [0, 1]")
        try:
            normalized = float(value)
        except (OverflowError, ValueError):
            raise ClickTargetError("normalized click target must be finite and within [0, 1]")
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ClickTargetError("normalized click target must be finite and within [0, 1]")


def _validate_viewport(viewport: object) -> tuple[int, int]:
    if (
        not isinstance(viewport, tuple)
        or len(viewport) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in viewport)
    ):
        raise ClickTargetError("viewport size must be a positive integer pair")
    return viewport
