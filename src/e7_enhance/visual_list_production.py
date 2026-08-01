"""Production assembly for the read-only equipment-list visual pipeline.

The assembly is deliberately lazy and dependency-injected.  It wires a
platform frame source to the fixed three-frame list observer, but never
constructs an OCR engine, loads templates, emits coordinates, or performs
input on its own.  Missing factories are terminal instead of falling back to
test readers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .visual_adapter import FrameSource
from .visual_list_observer import (
    InMemoryPngListPageObserver,
    ListPageParseResult,
    ListPageSampleFrameCollector,
    RegisteredListPageRegions,
)
from .visual_list_png_source import (
    InMemoryPngListPageObservationSource,
)
from .visual_list_recognizer import (
    RegisteredListPageLocalRecognizer,
    equipment_list_region_registry,
)
from .visual_adb_recognition import InMemoryPngRegionExtractor
from .visual_list_assets import (
    CARD_TEMPLATE_MANIFEST,
    FIELD_MAPPING_MANIFEST,
    ListPageAssetError,
    build_audited_card_template_reader,
    load_card_fingerprint_templates,
    load_list_field_mapping,
)


class ProductionListPageReaderUnavailable(RuntimeError):
    """The production reader boundary is not configured or failed to build."""


ReaderFactory = Callable[[], Any]


@dataclass(frozen=True)
class ProductionListPagePipeline:
    """A fully assembled, read-only list-page observation pipeline."""

    frame_source: FrameSource
    collector: ListPageSampleFrameCollector
    observer: InMemoryPngListPageObserver
    registry: RegisteredListPageRegions

    def observe(
        self,
        operation_id: str,
        expected_fields: Mapping[str, Any],
    ) -> ListPageParseResult:
        """Collect one fixed batch and parse it without retries or side effects."""

        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("list-page operation id is required")
        if not isinstance(expected_fields, Mapping) or not expected_fields:
            raise ValueError("list-page expected fields are required")
        try:
            frames = self.collector.collect(self.frame_source)
        except Exception as exc:
            return _failed("list_page_frame_collection_failed", exc)
        return self.observer.parse(operation_id, frames, expected_fields)


def build_production_list_page_pipeline(
    frame_source: FrameSource,
    *,
    ocr_reader_factory: ReaderFactory | None,
    template_reader_factory: ReaderFactory | None,
    registry: RegisteredListPageRegions | None = None,
    extractor: InMemoryPngRegionExtractor | None = None,
) -> ProductionListPagePipeline:
    """Assemble the fixed list-page pipeline from explicit production readers.

    Factories are required so engine construction remains outside the visual
    contract and can be audited/configured by the application.  The function
    never supplies a fixture or a default OCR/template implementation.
    """

    if not callable(getattr(frame_source, "capture", None)):
        raise TypeError("production list frame source must provide capture")
    if not callable(ocr_reader_factory) or not callable(template_reader_factory):
        raise ProductionListPageReaderUnavailable("production list OCR and template factories are required")
    selected_registry = registry or equipment_list_region_registry()
    if not isinstance(selected_registry, RegisteredListPageRegions):
        raise TypeError("production list registry is invalid")
    ocr_reader = _create_reader(ocr_reader_factory, "OCR")
    template_reader = _create_reader(template_reader_factory, "template")
    source = InMemoryPngListPageObservationSource(
        selected_registry,
        ocr_reader,
        template_reader,
        extractor=extractor,
    )
    recognizer = RegisteredListPageLocalRecognizer(selected_registry, source)
    observer = InMemoryPngListPageObserver(selected_registry, recognizer)
    return ProductionListPagePipeline(
        frame_source=frame_source,
        collector=ListPageSampleFrameCollector(frame_source.capture),
        observer=observer,
        registry=selected_registry,
    )


def build_production_list_page_pipeline_from_assets(
    frame_source: FrameSource,
    *,
    ocr_reader_factory: ReaderFactory | None,
    field_mapping_manifest: str | None = None,
    card_template_manifest: str | None = None,
    registry: RegisteredListPageRegions | None = None,
    extractor: InMemoryPngRegionExtractor | None = None,
) -> ProductionListPagePipeline:
    """Assemble production readers only after both audited asset bundles load.

    The current manifests intentionally remain incomplete, so this boundary
    raises ``ProductionListPageReaderUnavailable`` before any frame capture.
    """

    try:
        load_list_field_mapping(field_mapping_manifest or FIELD_MAPPING_MANIFEST)
        template_manifest = card_template_manifest or CARD_TEMPLATE_MANIFEST
        # Validate the complete template bundle (hash, viewport, threshold)
        # eagerly so an asset defect surfaces with its audit detail instead of
        # being masked by a generic reader-construction failure.
        load_card_fingerprint_templates(template_manifest)
        template_factory = lambda: build_audited_card_template_reader(template_manifest)
    except ListPageAssetError as exc:
        raise ProductionListPageReaderUnavailable(str(exc)) from exc
    return build_production_list_page_pipeline(
        frame_source,
        ocr_reader_factory=ocr_reader_factory,
        template_reader_factory=template_factory,
        registry=registry,
        extractor=extractor,
    )


def _create_reader(factory: ReaderFactory, label: str) -> Any:
    try:
        reader = factory()
    except Exception as exc:
        raise ProductionListPageReaderUnavailable(f"production list {label} reader construction failed") from exc
    if reader is None:
        raise ProductionListPageReaderUnavailable(f"production list {label} reader is unavailable")
    if label == "OCR" and not _supports(reader, ("read_ocr", "read")):
        raise ProductionListPageReaderUnavailable("production list OCR reader has no read method")
    if label == "template" and not _supports(reader, ("match_template", "match", "read")):
        raise ProductionListPageReaderUnavailable("production list template reader has no match method")
    return reader


def _supports(reader: Any, method_names: tuple[str, ...]) -> bool:
    return any(callable(getattr(reader, name, None)) for name in method_names)


def _failed(reason: str, error: Exception) -> ListPageParseResult:
    return ListPageParseResult(
        "fail_closed",
        "visual_only",
        "unverified",
        (reason, type(error).__name__),
    )


__all__ = [
    "ProductionListPagePipeline",
    "ProductionListPageReaderUnavailable",
    "build_production_list_page_pipeline",
    "build_production_list_page_pipeline_from_assets",
]
