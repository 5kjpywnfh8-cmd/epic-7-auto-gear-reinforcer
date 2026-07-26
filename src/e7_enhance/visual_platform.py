"""Read-only Windows and local-recognition seams for visual evidence.

No platform driver, screen capture library, or OCR engine is imported here.
Those capabilities must be supplied explicitly by a later authorized caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping, Protocol, Sequence

from .ocr_normalize import MIN_FIELD_CONFIDENCE
from .ocr_paddle import parse_backpack_enhance_lines
from .ocr_regions import equipment_regions, validate_regions
from .visual_adapter import PlatformWindow, StableFrames, VisualFrame
from .visual_runtime import SamplingRequest, VisualEvidence


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REQUIRED_VISIBLE_FIELDS = ("set", "slot", "rank", "enhance", "level", "mainStat", "substats")


class VisualPlatformError(RuntimeError):
    """Base error for a platform input that must fail closed."""


class WindowsBackendUnavailableError(VisualPlatformError):
    """No explicitly supplied Windows read-only driver is available."""


class WindowsCaptureError(VisualPlatformError):
    """The injected Windows driver failed or returned an invalid PNG frame."""


class LocalRecognitionError(VisualPlatformError):
    """A local region, template, OCR result, or evidence binding is invalid."""


@dataclass(frozen=True)
class WindowsCaptureConfig:
    """Read-only target selection; no activation or input settings exist here."""

    window_title: str
    source: str = "windows_read_only"
    window_class: str | None = None
    process_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.window_title, str) or not self.window_title.strip():
            raise ValueError("window_title is required")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source is required")
        if self.window_class is not None and (not isinstance(self.window_class, str) or not self.window_class.strip()):
            raise ValueError("window_class must be a non-empty string when supplied")
        if self.process_id is not None and (
            isinstance(self.process_id, bool) or not isinstance(self.process_id, int) or self.process_id <= 0
        ):
            raise ValueError("process_id must be a positive integer when supplied")


class WindowsReadOnlyDriver(Protocol):
    """Injectable Windows driver with no activation, movement, or input methods."""

    def locate_window(self, config: WindowsCaptureConfig) -> PlatformWindow | None:
        ...

    def client_viewport(self, window: PlatformWindow) -> tuple[int, int]:
        ...

    def capture_png(self, window: PlatformWindow) -> bytes:
        ...


class LazyWindowsReadOnlyBackend:
    """Lazily construct an injected read-only Windows driver on first use.

    A missing factory is terminal and intentionally does not attempt imports,
    dependency installation, window startup, or device discovery.
    """

    def __init__(
        self,
        config: WindowsCaptureConfig,
        driver_factory: Callable[[], WindowsReadOnlyDriver] | None = None,
        *,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(config, WindowsCaptureConfig):
            raise TypeError("config must be WindowsCaptureConfig")
        if driver_factory is not None and not callable(driver_factory):
            raise TypeError("driver_factory must be callable")
        if timestamp_factory is not None and not callable(timestamp_factory):
            raise TypeError("timestamp_factory must be callable")
        self._config = config
        self._driver_factory = driver_factory
        self._timestamp_factory = timestamp_factory or _utc_timestamp
        self._driver: WindowsReadOnlyDriver | None = None
        self._factory_attempted = False

    def locate_window(self) -> PlatformWindow | None:
        try:
            return self._get_driver().locate_window(self._config)
        except WindowsBackendUnavailableError:
            raise
        except Exception as exc:
            raise WindowsCaptureError("read-only window lookup failed") from exc

    def viewport_size(self, window: PlatformWindow) -> tuple[int, int]:
        try:
            return self._get_driver().client_viewport(window)
        except WindowsBackendUnavailableError:
            raise
        except Exception as exc:
            raise WindowsCaptureError("read-only viewport lookup failed") from exc

    def capture_frame(self, window: PlatformWindow) -> bytes:
        try:
            payload = self._get_driver().capture_png(window)
        except WindowsBackendUnavailableError:
            raise
        except Exception as exc:
            raise WindowsCaptureError("read-only PNG capture failed") from exc
        if not isinstance(payload, bytes) or not payload.startswith(PNG_SIGNATURE):
            raise WindowsCaptureError("read-only capture did not return PNG bytes")
        return payload

    def captured_at(self) -> str:
        if self._timestamp_factory is None:
            raise WindowsBackendUnavailableError("timestamp factory is not configured")
        try:
            value = self._timestamp_factory()
        except Exception as exc:
            raise WindowsCaptureError("read-only capture timestamp failed") from exc
        if not isinstance(value, str) or not value.strip():
            raise WindowsCaptureError("read-only capture timestamp is invalid")
        return value

    def _get_driver(self) -> WindowsReadOnlyDriver:
        if self._driver is not None:
            return self._driver
        if self._factory_attempted:
            raise WindowsBackendUnavailableError("read-only Windows driver construction already failed")
        self._factory_attempted = True
        if self._driver_factory is None:
            raise WindowsBackendUnavailableError("read-only Windows driver is not configured")
        try:
            driver = self._driver_factory()
        except Exception as exc:
            raise WindowsBackendUnavailableError("read-only Windows driver construction failed") from exc
        if driver is None:
            raise WindowsBackendUnavailableError("read-only Windows driver is unavailable")
        self._driver = driver
        return driver


@dataclass(frozen=True)
class LocalRegion:
    """A validated normalized region resolved against one frame viewport."""

    name: str
    normalized_bounds: Mapping[str, float]
    pixel_bounds: tuple[int, int, int, int]


@dataclass(frozen=True)
class RegionSample:
    """Read-only payload for one local region supplied by an injected extractor."""

    region: LocalRegion
    payload: bytes


class RegionExtractor(Protocol):
    """Extract an already-authorized local crop without performing OCR or input."""

    def extract(self, frame: VisualFrame, region: LocalRegion) -> bytes:
        ...


class LocalTemplateRecognizer(Protocol):
    """Return local template evidence for the supplied region samples."""

    def recognize(self, frame: VisualFrame, regions: Mapping[str, RegionSample]) -> Sequence[Mapping[str, Any]]:
        ...


class LocalOcrRecognizer(Protocol):
    """Return an accepted/rejected OCR parse without invoking a fixed engine."""

    def recognize(self, frame: VisualFrame, regions: Mapping[str, RegionSample]) -> Mapping[str, Any]:
        ...


class CallbackRegionExtractor:
    """Adapter for an injected local-crop callback used by offline tests or a future driver."""

    def __init__(self, callback: Callable[[VisualFrame, LocalRegion], bytes]) -> None:
        if not callable(callback):
            raise TypeError("region extractor callback must be callable")
        self._callback = callback

    def extract(self, frame: VisualFrame, region: LocalRegion) -> bytes:
        return self._callback(frame, region)


class PaddleLinesOcrRecognizer:
    """Reuse the existing read-only Paddle line parser through an injected line source."""

    def __init__(self, line_source: Callable[[VisualFrame, Mapping[str, RegionSample]], list[dict[str, Any]]]) -> None:
        if not callable(line_source):
            raise TypeError("Paddle line source must be callable")
        self._line_source = line_source

    def recognize(self, frame: VisualFrame, regions: Mapping[str, RegionSample]) -> Mapping[str, Any]:
        lines = self._line_source(frame, regions)
        if not isinstance(lines, list):
            raise LocalRecognitionError("Paddle line source must return a list")
        return parse_backpack_enhance_lines(lines)


class LocalRecognitionEvidenceParser:
    """Bind stable frame provenance and existing local OCR rules to visual evidence."""

    def __init__(
        self,
        region_extractor: RegionExtractor,
        template_recognizer: LocalTemplateRecognizer,
        ocr_recognizer: LocalOcrRecognizer,
        *,
        region_provider: Callable[[], Mapping[str, Any]] = equipment_regions,
        resource_preview: Mapping[str, Any] | None = None,
    ) -> None:
        self._region_extractor = region_extractor
        self._template_recognizer = template_recognizer
        self._ocr_recognizer = ocr_recognizer
        self._region_provider = region_provider
        self._resource_preview = dict(resource_preview or {})

    def parse(self, request: SamplingRequest, frames: StableFrames) -> VisualEvidence:
        if not isinstance(request, SamplingRequest) or not isinstance(frames, StableFrames):
            raise LocalRecognitionError("request and stable frame record are required")
        frame = frames.frames[-1]
        manifest = self._read_manifest()
        regions = _resolve_regions(frame.viewport, manifest)
        samples = self._extract_regions(frame, regions)
        anchors = self._recognize_templates(frame, samples)
        visible_fields, confidence = self._recognize_fields(frame, samples)
        fingerprint = _fingerprint(samples, visible_fields)
        sample_id = sha256(
            f"{request.operation_id}|{request.phase}|{request.expected_node}|{frame.frame_hash}".encode("utf-8")
        ).hexdigest()
        return VisualEvidence(
            schema_version="e7_enhance.visual_evidence/1.0",
            operation_id=request.operation_id,
            sample_id=sample_id,
            captured_at=frames.captured_at,
            phase=request.phase,
            expected_node=request.expected_node,
            page={
                "page_type": "enhance_equipment",
                "is_unambiguous": True,
                "target_visible": True,
                "page_signature": frame.frame_hash,
            },
            stability={
                "sample_count": frames.sample_count,
                "stable_count": frames.stable_count,
                "poll_interval_ms": 1,
                "timeout_ms": frames.sample_count,
                "frame_hashes": list(frames.frame_hashes),
            },
            anchors=tuple(anchors),
            target={
                "visible_fields": visible_fields,
                "field_confidence": confidence,
                "candidate_count": 1,
                "visual_fingerprint": fingerprint,
            },
            resource_preview=dict(self._resource_preview),
            sampler={
                "adapter": "local_visual_platform",
                "template_set": str(manifest.get("template") or "equipment_detail_normalized_v1"),
                "version": str(manifest.get("schema_version") or "1"),
                "source": frame.source,
                "viewport": {"width": frame.viewport[0], "height": frame.viewport[1]},
            },
        )

    def _read_manifest(self) -> Mapping[str, Any]:
        try:
            manifest = self._region_provider()
        except Exception as exc:
            raise LocalRecognitionError("equipment region manifest is unavailable") from exc
        if not isinstance(manifest, Mapping) or not isinstance(manifest.get("regions"), list):
            raise LocalRecognitionError("equipment region manifest is invalid")
        errors = list(manifest.get("validation_errors") or []) + validate_regions(manifest["regions"])
        if errors:
            raise LocalRecognitionError("equipment region manifest is out of bounds")
        return manifest

    def _extract_regions(
        self, frame: VisualFrame, regions: Sequence[LocalRegion]
    ) -> Mapping[str, RegionSample]:
        samples: dict[str, RegionSample] = {}
        for region in regions:
            try:
                payload = self._region_extractor.extract(frame, region)
            except Exception as exc:
                raise LocalRecognitionError(f"local region extraction failed:{region.name}") from exc
            if not isinstance(payload, bytes) or not payload:
                raise LocalRecognitionError(f"local region payload is invalid:{region.name}")
            samples[region.name] = RegionSample(region, payload)
        return samples

    def _recognize_templates(
        self, frame: VisualFrame, regions: Mapping[str, RegionSample]
    ) -> list[Mapping[str, Any]]:
        try:
            anchors = self._template_recognizer.recognize(frame, regions)
        except Exception as exc:
            raise LocalRecognitionError("local template recognition failed") from exc
        if not isinstance(anchors, Sequence) or isinstance(anchors, (str, bytes)):
            raise LocalRecognitionError("local template recognition is invalid")
        names: set[str] = set()
        accepted: list[Mapping[str, Any]] = []
        for anchor in anchors:
            if not isinstance(anchor, Mapping):
                continue
            name = anchor.get("name")
            score = anchor.get("score")
            threshold = anchor.get("threshold")
            bright_ratio = anchor.get("bright_ratio")
            if (
                isinstance(name, str)
                and name.strip()
                and name not in names
                and _unit(score)
                and _unit(threshold)
                and _unit(bright_ratio)
                and score >= threshold
                and bright_ratio > 0
            ):
                names.add(name)
                accepted.append(dict(anchor))
        if len(accepted) < 2:
            raise LocalRecognitionError("local page templates are not uniquely confirmed")
        return accepted

    def _recognize_fields(
        self, frame: VisualFrame, regions: Mapping[str, RegionSample]
    ) -> tuple[dict[str, Any], dict[str, float]]:
        try:
            parsed = self._ocr_recognizer.recognize(frame, regions)
        except Exception as exc:
            raise LocalRecognitionError("local OCR recognition failed") from exc
        if not isinstance(parsed, Mapping) or parsed.get("accepted") is not True:
            raise LocalRecognitionError("local OCR result is rejected")
        fields = parsed.get("fields")
        if not isinstance(fields, Mapping):
            raise LocalRecognitionError("local OCR fields are invalid")
        visible: dict[str, Any] = {}
        confidence: dict[str, float] = {}
        for name in REQUIRED_VISIBLE_FIELDS:
            value = fields.get(name)
            normalized, score = _normalized_field(value, name)
            if normalized is None or not _number(score) or score < MIN_FIELD_CONFIDENCE:
                raise LocalRecognitionError(f"local OCR confidence is below threshold:{name}")
            visible[name] = normalized
            confidence[name] = float(score)
        return visible, confidence


def _resolve_regions(viewport: tuple[int, int], manifest: Mapping[str, Any]) -> list[LocalRegion]:
    if (
        not isinstance(viewport, tuple)
        or len(viewport) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in viewport)
    ):
        raise LocalRecognitionError("frame viewport is invalid")
    width, height = viewport
    resolved: list[LocalRegion] = []
    for definition in manifest["regions"]:
        bounds = definition["bounds"]
        left, top, right, bottom = (float(bounds[key]) for key in ("left", "top", "right", "bottom"))
        pixels = (round(left * width), round(top * height), round(right * width), round(bottom * height))
        if not (0 <= pixels[0] < pixels[2] <= width and 0 <= pixels[1] < pixels[3] <= height):
            raise LocalRecognitionError(f"local region is outside viewport:{definition['name']}")
        resolved.append(LocalRegion(str(definition["name"]), dict(bounds), pixels))
    return resolved


def _fingerprint(regions: Mapping[str, RegionSample], fields: Mapping[str, Any]) -> str:
    material = {
        "regions": {name: sha256(sample.payload).hexdigest() for name, sample in sorted(regions.items())},
        "fields": dict(sorted(fields.items())),
    }
    return sha256(json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unit(value: object) -> bool:
    return _number(value) and 0 <= value <= 1


def _normalized_field(value: object, name: str) -> tuple[Any, float | None]:
    if name == "mainStat":
        if not isinstance(value, Mapping):
            return None, None
        stat_type = value.get("type")
        stat_value = value.get("value")
        if not _accepted_stat_part(stat_type) or not _accepted_stat_part(stat_value):
            return None, None
        normalized = {"type": stat_type["normalized"], "value": stat_value["normalized"]}
        return normalized, min(float(stat_type["confidence"]), float(stat_value["confidence"]))
    if name == "substats":
        if not isinstance(value, list) or not value:
            return None, None
        normalized: list[dict[str, Any]] = []
        scores: list[float] = []
        for item in value:
            if not isinstance(item, Mapping):
                return None, None
            stat_type = item.get("type")
            stat_value = item.get("value")
            if not _accepted_stat_part(stat_type) or not _accepted_stat_part(stat_value):
                return None, None
            normalized.append({"type": stat_type["normalized"], "value": stat_value["normalized"]})
            scores.extend((float(stat_type["confidence"]), float(stat_value["confidence"])))
        return normalized, min(scores)
    if not isinstance(value, Mapping) or value.get("accepted") is not True:
        return None, None
    return value.get("normalized"), value.get("confidence")


def _accepted_stat_part(value: object) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("accepted") is True
        and value.get("normalized") is not None
        and _number(value.get("confidence"))
        and float(value["confidence"]) >= MIN_FIELD_CONFIDENCE
    )


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
