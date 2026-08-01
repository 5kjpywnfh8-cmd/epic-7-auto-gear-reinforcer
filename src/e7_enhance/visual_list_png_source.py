"""In-memory fixed-region OCR/template source for equipment list pages.

The source owns only the local PNG-to-observation boundary.  OCR and template
engines are explicit injected readers, so this module never captures a frame,
searches for a region, emits coordinates, or performs input.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .visual_adapter import VisualFrame
from .visual_adb_recognition import InMemoryPngRegionExtractor
from .visual_list_observer import CARD_REGION_PREFIX, ListPageLocalRecognitionError, RegisteredListPageRegions
from .visual_runtime import MIN_FIELD_CONFIDENCE
from .visual_platform import LocalRegion


_ANCHOR_NAMES = frozenset(("list_header", "sort_button"))
_FIELD_NAMES = frozenset((
    "slot", "rank", "level", "enhance", "set", "main", "substats", "gear_score",
))


class ListPagePngOcrReader(Protocol):
    """Read one already-cropped fixed local region in process memory."""

    def read_ocr(self, region_name: str, crop_png: bytes) -> Mapping[str, Any]:
        ...


class ListPagePngTemplateReader(Protocol):
    """Match one already-cropped candidate card against local templates."""

    def match_template(self, region_name: str, crop_png: bytes) -> Mapping[str, Any]:
        ...


class InMemoryPngListPageObservationSource:
    """Produce the registered list-page observation schema from PNG crops.

    The OCR reader returns only region-local records:

    * ``list_header_region``: ``score`` and the two named ``anchors``;
    * ``candidate_list_region``: ``score``, ``scroll_state`` and
      ``page_boundary``;
    * a populated ``candidate_card:*``: ``candidate_id`` and complete
      ``field_observations``; an empty card returns ``{"candidate": None}``.

    The template reader is called only for populated cards and returns a
    ``visual_fingerprint`` plus a confidence ``score``.  The source combines
    these local results into the strict schema consumed by
    :class:`RegisteredListPageLocalRecognizer`.
    """

    def __init__(
        self,
        registry: RegisteredListPageRegions,
        ocr_reader: ListPagePngOcrReader,
        template_reader: ListPagePngTemplateReader,
        *,
        extractor: InMemoryPngRegionExtractor | None = None,
    ) -> None:
        if not isinstance(registry, RegisteredListPageRegions):
            raise TypeError("a registered list-page region registry is required")
        if registry.viewport is None or registry.schema_version is None:
            raise ValueError("a versioned list-page registry with a viewport is required")
        if not _reader_callable(ocr_reader, ("read_ocr", "read")):
            raise TypeError("list-page OCR reader must provide read_ocr")
        if not _reader_callable(template_reader, ("match_template", "match", "read")):
            raise TypeError("list-page template reader must provide match_template")
        if extractor is not None and not callable(getattr(extractor, "extract", None)):
            raise TypeError("PNG region extractor must provide extract")
        self._registry = registry
        self._ocr_reader = ocr_reader
        self._template_reader = template_reader
        self._extractor = extractor or InMemoryPngRegionExtractor()

    def observe(
        self,
        frame: VisualFrame,
        regions: Mapping[str, Mapping[str, float]],
    ) -> Mapping[str, Any]:
        if not isinstance(frame, VisualFrame) or frame.viewport != self._registry.viewport:
            raise ListPageLocalRecognitionError("unknown_list_viewport")
        if not _same_regions(regions, self._registry.recognizer_regions):
            raise ListPageLocalRecognitionError("local_list_region_not_registered")

        crops: dict[str, bytes] = {}
        for region in self._registry.regions:
            try:
                local = _local_region(region.name, region.bounds, frame.viewport)
                crops[region.name] = self._extractor.extract(frame, local)
            except ListPageLocalRecognitionError:
                raise
            except Exception as exc:
                raise ListPageLocalRecognitionError("invalid_memory_png") from exc

        try:
            local_regions = self._read_regions(crops)
        except ListPageLocalRecognitionError:
            raise
        except Exception as exc:
            raise ListPageLocalRecognitionError("local_list_png_observation_failed") from exc
        return {
            "schema_version": self._registry.schema_version,
            "viewport": self._registry.viewport,
            "local_regions": local_regions,
        }

    def _read_regions(self, crops: Mapping[str, bytes]) -> dict[str, dict[str, Any]]:
        names = set(self._registry.recognizer_regions)
        header = _ocr(self._ocr_reader, "list_header_region", crops["list_header_region"])
        _require_exact_keys(header, {"score", "anchors"})
        candidate_list = _ocr(self._ocr_reader, "candidate_list_region", crops["candidate_list_region"])
        _require_exact_keys(candidate_list, {"score", "scroll_state", "page_boundary"})

        local_regions: dict[str, dict[str, Any]] = {
            "list_header_region": {
                "score": _score(header["score"]),
                "anchors": _anchors(header["anchors"]),
            },
            "candidate_list_region": {
                "score": _score(candidate_list["score"]),
                "scroll_state": candidate_list["scroll_state"],
                "page_boundary": _page_boundary(candidate_list["page_boundary"]),
            },
        }
        if local_regions["candidate_list_region"]["scroll_state"] != "not_scrolled":
            raise ListPageLocalRecognitionError("scroll_or_page_boundary_unknown")

        for name in sorted(names):
            if not name.startswith(CARD_REGION_PREFIX):
                continue
            card = _ocr(self._ocr_reader, name, crops[name])
            if set(card) == {"candidate"}:
                if card["candidate"] is not None:
                    raise ListPageLocalRecognitionError("local_list_token_unknown")
                local_regions[name] = {"candidate": None}
                continue
            _require_exact_keys(card, {"candidate_id", "field_observations"})
            candidate_id = card["candidate_id"]
            if not isinstance(candidate_id, str) or not candidate_id.strip():
                raise ListPageLocalRecognitionError("local_candidate_invalid")
            fields = _fields(card["field_observations"])
            template = _template(self._template_reader, name, crops[name])
            _require_exact_keys(template, {"visual_fingerprint", "score"})
            _score(template["score"])
            fingerprint = template["visual_fingerprint"]
            if not _sha256(fingerprint):
                raise ListPageLocalRecognitionError("local_candidate_invalid")
            local_regions[name] = {
                "candidate": {
                    "candidate_id": candidate_id,
                    "visual_fingerprint": fingerprint,
                    "field_observations": fields,
                }
            }
        if set(local_regions) != names:
            raise ListPageLocalRecognitionError("local_list_region_not_registered")
        return local_regions


# Keep a descriptive alias for callers that use the protocol's full name.
InMemoryPngListPageLocalObservationSource = InMemoryPngListPageObservationSource


def _reader_callable(reader: Any, names: tuple[str, ...]) -> bool:
    return any(callable(getattr(reader, name, None)) for name in names)


def _ocr(reader: Any, name: str, crop: bytes) -> Mapping[str, Any]:
    value = _invoke(reader, ("read_ocr", "read"), name, crop, "local_list_ocr_failed")
    if not isinstance(value, Mapping):
        raise ListPageLocalRecognitionError("local_list_ocr_invalid")
    return value


def _template(reader: Any, name: str, crop: bytes) -> Mapping[str, Any]:
    value = _invoke(reader, ("match_template", "match", "read"), name, crop, "local_list_template_failed")
    if not isinstance(value, Mapping):
        raise ListPageLocalRecognitionError("local_list_template_invalid")
    return value


def _invoke(reader: Any, names: tuple[str, ...], region_name: str, crop: bytes, reason: str) -> Any:
    for name in names:
        callback = getattr(reader, name, None)
        if callable(callback):
            try:
                return callback(region_name, crop)
            except ListPageLocalRecognitionError:
                raise
            except Exception as exc:
                raise ListPageLocalRecognitionError(reason) from exc
    raise ListPageLocalRecognitionError(reason)


def _same_regions(actual: Any, expected: Mapping[str, Mapping[str, float]]) -> bool:
    if not isinstance(actual, Mapping) or set(actual) != set(expected):
        return False
    return all(isinstance(actual[name], Mapping) and dict(actual[name]) == dict(bounds) for name, bounds in expected.items())


def _local_region(name: str, bounds: Mapping[str, float], viewport: tuple[int, int]) -> LocalRegion:
    if not isinstance(bounds, Mapping):
        raise ListPageLocalRecognitionError("local_list_region_not_registered")
    try:
        left, top, right, bottom = (float(bounds[key]) for key in ("left", "top", "right", "bottom"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ListPageLocalRecognitionError("local_list_region_not_registered") from exc
    width, height = viewport
    pixel_bounds = (round(width * left), round(height * top), round(width * right), round(height * bottom))
    if not (0 <= pixel_bounds[0] < pixel_bounds[2] <= width and 0 <= pixel_bounds[1] < pixel_bounds[3] <= height):
        raise ListPageLocalRecognitionError("local_list_region_not_registered")
    return LocalRegion(name, dict(bounds), pixel_bounds)


def _require_exact_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise ListPageLocalRecognitionError("local_list_token_unknown")


def _score(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"score", "threshold"}:
        raise ListPageLocalRecognitionError("local_list_confidence_invalid")
    score, threshold = value["score"], value["threshold"]
    if not _confidence(score) or not _confidence(threshold) or float(score) < float(threshold):
        raise ListPageLocalRecognitionError("local_list_confidence_too_low")
    return {"score": float(score), "threshold": float(threshold)}


def _anchors(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(_ANCHOR_NAMES):
        raise ListPageLocalRecognitionError("list_anchors_not_confirmed")
    names: set[str] = set()
    result: list[dict[str, Any]] = []
    for anchor in value:
        if not isinstance(anchor, Mapping) or set(anchor) != {"name", "score", "threshold"}:
            raise ListPageLocalRecognitionError("local_list_token_unknown")
        name = anchor["name"]
        if name not in _ANCHOR_NAMES or name in names:
            raise ListPageLocalRecognitionError("list_anchors_not_confirmed")
        score = _score({"score": anchor["score"], "threshold": anchor["threshold"]})
        names.add(name)
        result.append({"name": name, **score})
    if names != _ANCHOR_NAMES:
        raise ListPageLocalRecognitionError("list_anchors_not_confirmed")
    return result


def _page_boundary(value: Any) -> dict[str, bool]:
    if not isinstance(value, Mapping) or set(value) != {"top_visible", "bottom_visible"}:
        raise ListPageLocalRecognitionError("scroll_or_page_boundary_unknown")
    if not all(isinstance(value[name], bool) for name in ("top_visible", "bottom_visible")):
        raise ListPageLocalRecognitionError("scroll_or_page_boundary_unknown")
    return {"top_visible": value["top_visible"], "bottom_visible": value["bottom_visible"]}


def _fields(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(_FIELD_NAMES):
        raise ListPageLocalRecognitionError("candidate_fields_incomplete")
    names: set[str] = set()
    result: list[dict[str, Any]] = []
    for field in value:
        if not isinstance(field, Mapping) or set(field) != {"name", "value", "confidence"}:
            raise ListPageLocalRecognitionError("local_list_token_unknown")
        name = field["name"]
        if name not in _FIELD_NAMES:
            raise ListPageLocalRecognitionError("local_list_token_unknown")
        if name in names:
            raise ListPageLocalRecognitionError("candidate_field_conflict")
        if not _confidence(field["confidence"]):
            raise ListPageLocalRecognitionError("candidate_field_confidence_too_low")
        names.add(name)
        result.append({"name": name, "value": field["value"], "confidence": float(field["confidence"])})
    if names != _FIELD_NAMES:
        raise ListPageLocalRecognitionError("candidate_fields_incomplete")
    return result


def _confidence(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and MIN_FIELD_CONFIDENCE <= float(value) <= 1
    )


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value.casefold())
