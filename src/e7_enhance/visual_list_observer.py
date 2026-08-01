"""Fail-closed in-memory PNG observation bridge for equipment list pages.

The bridge consumes a caller-provided stable frame set or list-page sampling
batch, a fixed local region registry, and an injected local recognizer.  It has
no capture, OCR, input, navigation, or device capability.  In particular,
candidates can only use pre-registered card regions, so recognition cannot
expand its scope at runtime or derive click targets.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from datetime import datetime
from typing import Callable
from typing import Any, Mapping, Protocol

from .visual_adapter import StableFrames, VisualFrame
from .visual_adb import AdbFrameError, validate_png_content
from .visual_adb_recognition import InMemoryPngRegionExtractor, PngRegionRecognitionError
from .visual_platform import LocalRegion
from .visual_list_parser import (
    REQUIRED_REGIONS,
    EquipmentListVisualParser,
    ListPageParseResult,
)
from .visual_runtime import MODE, VERIFICATION


CARD_REGION_PREFIX = "candidate_card:"


@dataclass(frozen=True)
class ListPageSampleFrames:
    """Exactly three list-page frames with provenance checks but no hash lock.

    List rendering noise may legitimately change PNG bytes.  Visual field
    stability is established by :class:`InMemoryPngListPageObserver` after
    local recognition, while this batch retains source, viewport and timing
    checks at collection time.
    """

    frames: tuple[VisualFrame, ...]

    def __post_init__(self) -> None:
        if len(self.frames) != 3:
            raise ValueError("list-page sampling requires exactly three frames")
        if any(not isinstance(frame, VisualFrame) for frame in self.frames):
            raise TypeError("list-page sampling contains an invalid frame")
        if len({frame.viewport for frame in self.frames}) != 1:
            raise ValueError("list-page viewport changed during collection")
        if len({frame.source for frame in self.frames}) != 1:
            raise ValueError("list-page frame source changed during collection")
        timestamps = tuple(_timestamp(frame.captured_at) for frame in self.frames)
        if any(later < earlier for earlier, later in zip(timestamps, timestamps[1:])):
            raise ValueError("list-page frame timestamps moved backwards")

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


class ListPageSampleFrameCollector:
    """Collect one fixed three-frame list-page batch without retries."""

    def __init__(self, capture: Callable[[], VisualFrame] | Any | None = None) -> None:
        if capture is not None and not callable(capture) and not callable(getattr(capture, "capture", None)):
            raise TypeError("list-page frame source must provide capture")
        self._capture = capture

    def collect(self, source: Any | None = None) -> ListPageSampleFrames:
        capture = self._capture if source is None else source
        if capture is None:
            raise TypeError("list-page frame source must provide capture")
        callback = capture if callable(capture) else capture.capture
        frames = []
        for _ in range(3):
            frame = callback()
            if not isinstance(frame, VisualFrame):
                raise TypeError("list-page frame source returned an invalid frame")
            frames.append(frame)
        return ListPageSampleFrames(tuple(frames))


# Descriptive aliases kept for callers that name the list-page batch directly.
ListPageSamplingBatch = ListPageSampleFrames
ListPageFrameCollector = ListPageSampleFrameCollector


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("list-page frame timestamp must be timezone-aware")
    return parsed


@dataclass(frozen=True)
class RegisteredListRegion:
    """One caller-approved normalized local area; it is not a screen coordinate."""

    name: str
    bounds: Mapping[str, float]

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip() or not _valid_bounds(self.bounds):
            raise ValueError("registered list region is invalid")


@dataclass(frozen=True)
class RegisteredListPageRegions:
    """The complete fixed local scope available to one list-page recognizer."""

    regions: tuple[RegisteredListRegion, ...]
    viewport: tuple[int, int] | None = None
    schema_version: str | None = None

    def __post_init__(self) -> None:
        names = [region.name for region in self.regions if isinstance(region, RegisteredListRegion)]
        if len(names) != len(self.regions) or len(set(names)) != len(names):
            raise ValueError("registered list regions must be unique")
        if not all(name in names for name in REQUIRED_REGIONS):
            raise ValueError("required list regions are missing")
        if not any(name.startswith(CARD_REGION_PREFIX) for name in names):
            raise ValueError("at least one fixed candidate card region is required")
        if self.viewport is not None and (
            not isinstance(self.viewport, tuple)
            or len(self.viewport) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in self.viewport)
        ):
            raise ValueError("registered list viewport is invalid")
        if self.schema_version is not None and (
            not isinstance(self.schema_version, str) or not self.schema_version.strip()
        ):
            raise ValueError("registered list schema version is invalid")
        candidate_bounds = self.by_name("candidate_list_region").bounds
        if not all(
            _inside(region.bounds, candidate_bounds)
            for region in self.regions
            if region.name.startswith(CARD_REGION_PREFIX)
        ):
            raise ValueError("candidate card regions must be inside the candidate list region")

    def by_name(self, name: str) -> RegisteredListRegion:
        matches = [region for region in self.regions if region.name == name]
        if len(matches) != 1:
            raise KeyError(name)
        return matches[0]

    @property
    def recognizer_regions(self) -> Mapping[str, Mapping[str, float]]:
        return {region.name: dict(region.bounds) for region in self.regions}


class ListPageLocalRecognizer(Protocol):
    """Injected local-only recognizer for the fixed region registry."""

    def observe(self, frame: VisualFrame, regions: Mapping[str, Mapping[str, float]]) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class LocalPngCrop:
    """One fixed registered crop delivered to an injected local reader."""

    name: str
    normalized_bounds: Mapping[str, float]
    pixel_bounds: tuple[int, int, int, int]
    payload: bytes


class LocalPngRegionReader(Protocol):
    """Read one already-cropped PNG without owning capture or OCR runtime."""

    def read(self, frame: VisualFrame, crop: LocalPngCrop) -> Mapping[str, Any]:
        ...


class InMemoryPngListPageLocalObservationSource:
    """Convert registered in-memory PNG crops into recognizer ``local_regions``.

    Every registered area must have one explicit reader.  The source computes
    pixel bounds from the registry and frame viewport, crops in memory, and
    returns only the versioned observation envelope expected by
    ``RegisteredListPageLocalRecognizer``.
    """

    def __init__(
        self,
        registry: RegisteredListPageRegions,
        readers: Mapping[str, LocalPngRegionReader],
        *,
        extractor: InMemoryPngRegionExtractor | None = None,
    ) -> None:
        if not isinstance(registry, RegisteredListPageRegions):
            raise TypeError("a registered list-page region registry is required")
        if registry.viewport is None or registry.schema_version is None:
            raise ValueError("a versioned list-page registry with a viewport is required")
        if not isinstance(readers, Mapping) or set(readers) != set(registry.recognizer_regions):
            raise ValueError("one reader is required for every registered list region")
        if any(not callable(getattr(reader, "read", None)) and not callable(reader) for reader in readers.values()):
            raise TypeError("each list region reader must provide read or be callable")
        if extractor is not None and not callable(getattr(extractor, "extract", None)):
            raise TypeError("PNG region extractor must provide extract")
        self._registry = registry
        self._readers = dict(readers)
        self._extractor = extractor or InMemoryPngRegionExtractor()

    def observe(self, frame: VisualFrame, regions: Mapping[str, Mapping[str, float]]) -> Mapping[str, Any]:
        if not isinstance(frame, VisualFrame) or self._registry.viewport != frame.viewport:
            raise ListPageLocalRecognitionError("unknown_list_viewport")
        if not _same_registered_regions(regions, self._registry.recognizer_regions):
            raise ListPageLocalRecognitionError("local_list_region_not_registered")

        local_regions: dict[str, Mapping[str, Any]] = {}
        for registered in self._registry.regions:
            crop = self._crop(frame, registered)
            try:
                result = self._read(registered.name, frame, crop)
            except ListPageLocalRecognitionError:
                raise
            except Exception as exc:
                raise ListPageLocalRecognitionError("local_list_reader_failed") from exc
            if not isinstance(result, Mapping):
                raise ListPageLocalRecognitionError("local_list_reader_invalid")
            local_regions[registered.name] = dict(result)
        return {
            "schema_version": self._registry.schema_version,
            "viewport": self._registry.viewport,
            "local_regions": local_regions,
        }

    def _crop(self, frame: VisualFrame, registered: RegisteredListRegion) -> LocalPngCrop:
        width, height = frame.viewport
        bounds = registered.bounds
        pixels = tuple(round(float(bounds[name]) * dimension) for name, dimension in zip(
            ("left", "top", "right", "bottom"), (width, height, width, height)
        ))
        if not (0 <= pixels[0] < pixels[2] <= width and 0 <= pixels[1] < pixels[3] <= height):
            raise ListPageLocalRecognitionError("local_list_region_out_of_bounds")
        region = LocalRegion(registered.name, dict(bounds), pixels)
        try:
            payload = self._extractor.extract(frame, region)
        except PngRegionRecognitionError as exc:
            raise ListPageLocalRecognitionError("local_list_crop_failed") from exc
        except Exception as exc:
            raise ListPageLocalRecognitionError("local_list_crop_failed") from exc
        if not isinstance(payload, bytes) or not payload:
            raise ListPageLocalRecognitionError("local_list_crop_invalid")
        return LocalPngCrop(registered.name, dict(bounds), pixels, payload)

    def _read(self, name: str, frame: VisualFrame, crop: LocalPngCrop) -> Mapping[str, Any]:
        reader = self._readers[name]
        if callable(getattr(reader, "read", None)):
            return reader.read(frame, crop)
        return reader(frame, crop)


def _same_registered_regions(actual: Any, expected: Mapping[str, Mapping[str, float]]) -> bool:
    if not isinstance(actual, Mapping) or set(actual) != set(expected):
        return False
    return all(isinstance(actual[name], Mapping) and dict(actual[name]) == dict(bounds) for name, bounds in expected.items())


class ListPageLocalRecognitionError(RuntimeError):
    """A known local-only recognition rejection that must not be retried."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class InMemoryPngListPageObserver:
    """Build controlled parser input from verified PNG samples and observations."""

    def __init__(
        self,
        regions: RegisteredListPageRegions,
        recognizer: ListPageLocalRecognizer,
        *,
        parser: EquipmentListVisualParser | None = None,
    ) -> None:
        if not isinstance(regions, RegisteredListPageRegions):
            raise TypeError("registered list regions are required")
        if not callable(getattr(recognizer, "observe", None)):
            raise TypeError("local list recognizer must provide observe")
        self._regions = regions
        self._recognizer = recognizer
        self._parser = parser or EquipmentListVisualParser()

    def parse(
        self,
        operation_id: str,
        frames: StableFrames | ListPageSampleFrames,
        expected_fields: Mapping[str, Any],
    ) -> ListPageParseResult:
        """Return parser evidence only after all PNG and local-scope checks pass."""

        try:
            observations = self._build_observations(operation_id, frames)
        except _ObservationError as exc:
            return _failed(exc.reason)
        parsed = [self._parser.parse(observation, expected_fields) for observation in observations]
        for result in parsed:
            if not result.passed:
                return result
        signatures = [_visual_field_signature(observation) for observation in observations]
        if len(set(signatures)) != 1:
            return _failed("visual_fields_not_stable")
        final = parsed[-1]
        if final.evidence is None:
            return _failed("visual_fields_stability_evidence_missing")
        stability = dict(final.evidence.stability)
        stability["visual_fields_stable"] = True
        return replace(final, evidence=replace(final.evidence, stability=stability))

    def _build_observations(
        self,
        operation_id: str,
        frames: StableFrames | ListPageSampleFrames,
    ) -> list[Mapping[str, Any]]:
        if not isinstance(frames, (StableFrames, ListPageSampleFrames)):
            raise _ObservationError("stable_frames_not_confirmed")
        if self._regions.viewport is not None and frames.viewport != self._regions.viewport:
            raise _ObservationError("unknown_list_viewport")
        for frame in frames.frames:
            try:
                if validate_png_content(frame.payload, frame.viewport) is not True:
                    raise _ObservationError("empty_or_black_frame")
            except AdbFrameError as exc:
                raise _ObservationError("invalid_memory_png") from exc
        observations: list[Mapping[str, Any]] = []
        frame_batch = frames.frames if isinstance(frames, ListPageSampleFrames) else (frames.frames[-1],)
        for frame in frame_batch:
            try:
                recognized = self._recognizer.observe(frame, self._regions.recognizer_regions)
            except ListPageLocalRecognitionError as exc:
                raise _ObservationError(exc.reason) from exc
            except Exception as exc:
                raise _ObservationError("local_list_recognition_failed") from exc
            if not isinstance(recognized, Mapping):
                raise _ObservationError("local_list_recognition_invalid")
            region_scores = recognized.get("region_scores")
            if not isinstance(region_scores, Mapping):
                raise _ObservationError("registered_region_scores_missing")
            regions = []
            for name in REQUIRED_REGIONS:
                score = region_scores.get(name)
                if not isinstance(score, Mapping):
                    raise _ObservationError("registered_region_scores_missing")
                regions.append({
                    "name": name,
                    "bounds": dict(self._regions.by_name(name).bounds),
                    "score": score.get("score"),
                    "threshold": score.get("threshold"),
                })
            observations.append({
                "operation_id": operation_id,
                "captured_at": frames.captured_at,
                "page_signature": sha256(frame.payload).hexdigest(),
                "viewport": frames.viewport,
                "stability": {
                    "sample_count": frames.sample_count,
                    "stable_count": frames.stable_count,
                    "frame_hashes": list(frames.frame_hashes),
                },
                "anchors": recognized.get("anchors"),
                "regions": regions,
                "visible_bounds": dict(self._regions.by_name("candidate_list_region").bounds),
                "scroll_state": recognized.get("scroll_state"),
                "page_boundary": recognized.get("page_boundary"),
                "candidates": self._registered_candidates(recognized.get("candidates")),
            })
        return observations

    def _registered_candidates(self, candidates: Any) -> list[dict[str, Any]]:
        if not isinstance(candidates, list):
            raise _ObservationError("local_candidates_missing")
        result: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise _ObservationError("local_candidate_invalid")
            region_name = candidate.get("region")
            if not isinstance(region_name, str) or not region_name.startswith(CARD_REGION_PREFIX):
                raise _ObservationError("candidate_region_not_registered")
            try:
                bounds = self._regions.by_name(region_name).bounds
            except KeyError as exc:
                raise _ObservationError("candidate_region_not_registered") from exc
            result.append({
                "candidate_id": candidate.get("candidate_id"),
                "visual_fingerprint": candidate.get("visual_fingerprint"),
                "bounds": dict(bounds),
                "field_observations": candidate.get("field_observations"),
            })
        return result


class _ObservationError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _visual_field_signature(observation: Mapping[str, Any]) -> tuple[Any, ...]:
    """Normalize visual identity while excluding confidence/hash noise."""

    anchors = tuple(sorted(
        tuple(sorted((key, _freeze(value)) for key, value in anchor.items() if key not in {"score", "threshold"}))
        for anchor in observation.get("anchors", ())
        if isinstance(anchor, Mapping)
    ))
    boundary = observation.get("page_boundary")
    normalized_boundary = tuple(sorted(boundary.items())) if isinstance(boundary, Mapping) else None
    candidates = []
    for candidate in observation.get("candidates", ()):
        if not isinstance(candidate, Mapping):
            continue
        fields = []
        for field in candidate.get("field_observations", ()):
            if isinstance(field, Mapping):
                fields.append((field.get("name"), _freeze(field.get("value"))))
        candidates.append((
            candidate.get("candidate_id"),
            candidate.get("visual_fingerprint"),
            _freeze(candidate.get("bounds")),
            tuple(sorted(fields)),
        ))
    return (
        anchors,
        observation.get("scroll_state"),
        normalized_boundary,
        tuple(sorted(candidates, key=repr)),
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _valid_bounds(value: Mapping[str, float]) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        left, top, right, bottom = (float(value[name]) for name in ("left", "top", "right", "bottom"))
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= left < right <= 1 and 0 <= top < bottom <= 1


def _inside(inner: Mapping[str, float], outer: Mapping[str, float]) -> bool:
    return all(float(outer[name]) <= float(inner[name]) for name in ("left", "top")) and all(
        float(inner[name]) <= float(outer[name]) for name in ("right", "bottom")
    )


def _failed(reason: str) -> ListPageParseResult:
    return ListPageParseResult("fail_closed", MODE, VERIFICATION, (reason,))
