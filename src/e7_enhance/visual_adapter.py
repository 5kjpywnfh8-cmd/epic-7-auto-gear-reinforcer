"""Offline-only frame sampling adapters for the visual runtime.

The module deliberately has no emulator, desktop, OCR, or input dependency.
External integrations must supply frames through ``FrameSource`` and translate
stable frame records through ``VisualEvidenceParser``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Callable, Mapping, Protocol

from .visual_runtime import SamplingRequest, VisualEvidence


MIN_STABLE_FRAMES = 3


class VisualAdapterError(RuntimeError):
    """Base error for an offline adapter result that must stop."""


class FrameCaptureError(VisualAdapterError):
    """A source did not produce one valid frame."""


class UnstableFrameError(VisualAdapterError):
    """A collection contains more than one frame hash or source."""


class FrameViewportDriftError(VisualAdapterError):
    """A collection contains more than one viewport."""


class FrameTimestampError(VisualAdapterError):
    """Frame metadata has no timezone-aware timestamp."""


class EvidenceParseError(VisualAdapterError):
    """Evidence could not be parsed or did not match its stable frame record."""


@dataclass(frozen=True)
class VisualFrame:
    """One offline frame and the metadata needed to audit its provenance."""

    source: str
    payload: bytes
    viewport: tuple[int, int]
    captured_at: str
    frame_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise FrameCaptureError("frame source is required")
        if not isinstance(self.payload, bytes) or not self.payload:
            raise FrameCaptureError("frame payload must be non-empty bytes")
        _validate_viewport(self.viewport)
        _parse_timestamp(self.captured_at)
        if self.frame_hash != sha256(self.payload).hexdigest():
            raise FrameCaptureError("frame hash does not match payload")

    @classmethod
    def from_bytes(
        cls,
        *,
        source: str,
        payload: bytes,
        viewport: tuple[int, int],
        captured_at: str,
    ) -> "VisualFrame":
        """Build a frame with the SHA-256 derived from its supplied bytes."""
        if not isinstance(payload, bytes) or not payload:
            raise FrameCaptureError("frame payload must be non-empty bytes")
        return cls(source, payload, viewport, captured_at, sha256(payload).hexdigest())


class FrameSource(Protocol):
    """Injectable source of one frame; implementations remain platform-neutral."""

    def capture(self) -> VisualFrame:
        ...


class VisualEvidenceParser(Protocol):
    """Translate stable frame metadata into runtime ``VisualEvidence``."""

    def parse(self, request: SamplingRequest, frames: "StableFrames") -> VisualEvidence | Mapping[str, object]:
        ...


@dataclass(frozen=True)
class StableFrames:
    """A verified, single-source set of byte-identical frames."""

    frames: tuple[VisualFrame, ...]

    def __post_init__(self) -> None:
        if len(self.frames) < MIN_STABLE_FRAMES:
            raise UnstableFrameError("fewer than three frames cannot prove stability")
        if any(not isinstance(frame, VisualFrame) for frame in self.frames):
            raise FrameCaptureError("stable frame collection contains an invalid frame")
        if len({frame.frame_hash for frame in self.frames}) != 1:
            raise UnstableFrameError("frame hashes changed during collection")
        if len({frame.viewport for frame in self.frames}) != 1:
            raise FrameViewportDriftError("viewport changed during collection")
        if len({frame.source for frame in self.frames}) != 1:
            raise UnstableFrameError("frame source changed during collection")
        timestamps = tuple(_parse_timestamp(frame.captured_at) for frame in self.frames)
        if any(later < earlier for earlier, later in zip(timestamps, timestamps[1:])):
            raise FrameTimestampError("frame timestamps moved backwards")

    @property
    def sample_count(self) -> int:
        return len(self.frames)

    @property
    def stable_count(self) -> int:
        return len(self.frames)

    @property
    def frame_hashes(self) -> tuple[str, ...]:
        return tuple(frame.frame_hash for frame in self.frames)

    @property
    def viewport(self) -> tuple[int, int]:
        return self.frames[0].viewport

    @property
    def source(self) -> str:
        return self.frames[0].source

    @property
    def captured_at(self) -> str:
        return self.frames[-1].captured_at


class StableFrameCollector:
    """Collect exactly one fixed-size set; no sampling retries are performed."""

    def __init__(self, sample_count: int = MIN_STABLE_FRAMES) -> None:
        if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < MIN_STABLE_FRAMES:
            raise ValueError("sample_count must be an integer of at least three")
        self._sample_count = sample_count

    def collect(self, source: FrameSource) -> StableFrames:
        frames: list[VisualFrame] = []
        for _ in range(self._sample_count):
            try:
                frame = source.capture()
            except Exception as exc:
                raise FrameCaptureError("frame source failed") from exc
            if not isinstance(frame, VisualFrame):
                raise FrameCaptureError("frame source returned an invalid frame")
            frames.append(frame)
        return StableFrames(tuple(frames))


class CallbackFrameSource:
    """Offline source backed by an injected callback returning ``VisualFrame``."""

    def __init__(self, callback: Callable[[], VisualFrame]) -> None:
        if not callable(callback):
            raise TypeError("frame callback must be callable")
        self._callback = callback

    def capture(self) -> VisualFrame:
        return self._callback()


class FileBackedFrameSource:
    """Offline fixture source that rehydrates a recorded frame from a local file."""

    def __init__(self, path: str | Path, *, viewport: tuple[int, int], captured_at: str) -> None:
        self._path = Path(path)
        _validate_viewport(viewport)
        _parse_timestamp(captured_at)
        self._viewport = viewport
        self._captured_at = captured_at

    def capture(self) -> VisualFrame:
        return VisualFrame.from_bytes(
            source=f"file:{self._path.name}",
            payload=self._path.read_bytes(),
            viewport=self._viewport,
            captured_at=self._captured_at,
        )


class CallbackEvidenceParser:
    """Evidence parser adapter for an injected, offline-only parsing callback."""

    def __init__(self, callback: Callable[[SamplingRequest, StableFrames], VisualEvidence | Mapping[str, object]]) -> None:
        if not callable(callback):
            raise TypeError("evidence parser callback must be callable")
        self._callback = callback

    def parse(self, request: SamplingRequest, frames: StableFrames) -> VisualEvidence | Mapping[str, object]:
        return self._callback(request, frames)


class VisualAdapterSampler:
    """Implement the existing runtime sampler seam from offline frame records."""

    def __init__(
        self,
        frame_source: FrameSource,
        evidence_parser: VisualEvidenceParser,
        collector: StableFrameCollector | None = None,
    ) -> None:
        self._frame_source = frame_source
        self._evidence_parser = evidence_parser
        self._collector = collector or StableFrameCollector()

    def capture(self, request: SamplingRequest) -> VisualEvidence:
        if not isinstance(request, SamplingRequest):
            raise EvidenceParseError("sampling request is invalid")
        frames = self._collector.collect(self._frame_source)
        try:
            evidence = self._evidence_parser.parse(request, frames)
        except Exception as exc:
            raise EvidenceParseError("visual evidence parsing failed") from exc
        if isinstance(evidence, Mapping):
            try:
                evidence = VisualEvidence.from_mapping(evidence)
            except (TypeError, ValueError) as exc:
                raise EvidenceParseError("parsed visual evidence is invalid") from exc
        if not isinstance(evidence, VisualEvidence):
            raise EvidenceParseError("parser did not return visual evidence")
        _validate_evidence_binding(evidence, frames)
        return evidence


def _validate_evidence_binding(evidence: VisualEvidence, frames: StableFrames) -> None:
    stability = evidence.stability
    if not isinstance(stability, Mapping):
        raise EvidenceParseError("parsed evidence has no stability record")
    if (
        evidence.captured_at != frames.captured_at
        or stability.get("sample_count") != frames.sample_count
        or stability.get("stable_count") != frames.stable_count
        or stability.get("frame_hashes") != list(frames.frame_hashes)
    ):
        raise EvidenceParseError("parsed evidence does not match stable frames")


def _validate_viewport(viewport: object) -> tuple[int, int]:
    if (
        not isinstance(viewport, tuple)
        or len(viewport) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in viewport)
    ):
        raise FrameCaptureError("viewport must be a positive integer pair")
    return viewport


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise FrameTimestampError("captured_at must be a timezone-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FrameTimestampError("captured_at must be a timezone-aware ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FrameTimestampError("captured_at must be a timezone-aware ISO timestamp")
    return parsed
