"""Audited, offline assets for the equipment-list visual reader.

This module owns only manifest validation and deterministic in-memory template
matching.  It never captures a frame, invokes OCR, performs network access, or
emits a click coordinate.  Incomplete manifests intentionally fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


LIST_ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets" / "visual" / "list_reference"
FIELD_MAPPING_MANIFEST = LIST_ASSET_ROOT / "field_mapping_manifest.json"
CARD_TEMPLATE_MANIFEST = LIST_ASSET_ROOT / "card_fingerprint_manifest.json"
MIN_TEMPLATE_CONFIDENCE = 0.98
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_LIST_FIELDS = frozenset((
    "slot", "rank", "level", "enhance", "set", "main", "substats", "gear_score",
))


class ListPageAssetError(RuntimeError):
    """Raised when list-page assets are absent, incomplete, or tampered with."""


@dataclass(frozen=True)
class ListFieldMapping:
    """One explicitly audited OCR token mapping."""

    field: str
    token: str
    normalized: Any
    confidence: float
    source: str


@dataclass(frozen=True)
class CardFingerprintTemplate:
    """One complete-card template verified against its manifest hash."""

    identifier: str
    path: Path
    sha256: str
    viewport: tuple[int, int]
    threshold: float


def load_list_field_mapping(manifest_path: str | Path | None = None) -> Mapping[tuple[str, str], ListFieldMapping]:
    """Load the complete field mapping, rejecting any pending semantic token."""

    path = Path(manifest_path) if manifest_path is not None else FIELD_MAPPING_MANIFEST
    raw = _read_json(path, "field mapping manifest")
    if raw.get("schema_version") != 1 or raw.get("asset_kind") != "equipment_list_field_mapping":
        raise ListPageAssetError("field mapping manifest schema is unsupported")
    if raw.get("status") != "audited_complete":
        raise ListPageAssetError("list field mapping is not complete")
    entries = raw.get("mappings")
    if not isinstance(entries, list) or not entries:
        raise ListPageAssetError("field mapping manifest has no mappings")
    result: dict[tuple[str, str], ListFieldMapping] = {}
    fields: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"field", "token", "normalized", "confidence", "source", "status"}:
            raise ListPageAssetError("field mapping entry is invalid")
        if entry["status"] != "audited" or not _non_blank(entry["field"]) or not _non_blank(entry["token"]):
            raise ListPageAssetError("field mapping entry is not audited")
        confidence = entry["confidence"]
        if not _confidence(confidence) or float(confidence) < MIN_TEMPLATE_CONFIDENCE:
            raise ListPageAssetError("field mapping confidence is below threshold")
        source = entry["source"]
        if not _non_blank(source):
            raise ListPageAssetError("field mapping provenance is missing")
        key = (str(entry["field"]), str(entry["token"]))
        if key in result:
            raise ListPageAssetError("duplicate field mapping entry")
        if key[0] not in REQUIRED_LIST_FIELDS:
            raise ListPageAssetError("field mapping contains an unknown list field")
        fields.add(key[0])
        result[key] = ListFieldMapping(key[0], key[1], entry["normalized"], float(confidence), str(source))
    if fields != REQUIRED_LIST_FIELDS:
        raise ListPageAssetError("field mapping does not cover all required list fields")
    return dict(sorted(result.items()))


def normalize_list_field_token(
    mapping: Mapping[tuple[str, str], ListFieldMapping],
    field: str,
    token: str,
) -> Any:
    """Normalize one token only when an audited mapping exists."""

    if not isinstance(mapping, Mapping) or not _non_blank(field) or not _non_blank(token):
        raise ListPageAssetError("list field token is invalid")
    entry = mapping.get((field, token))
    if not isinstance(entry, ListFieldMapping) or entry.field != field or entry.token != token:
        raise ListPageAssetError(f"list field token is not audited:{field}:{token}")
    if entry.confidence < MIN_TEMPLATE_CONFIDENCE:
        raise ListPageAssetError("list field token confidence is below threshold")
    return entry.normalized


def load_card_fingerprint_templates(manifest_path: str | Path | None = None) -> Mapping[str, CardFingerprintTemplate]:
    """Load complete-card templates only; icon-only manifests are rejected."""

    path = Path(manifest_path) if manifest_path is not None else CARD_TEMPLATE_MANIFEST
    raw = _read_json(path, "card fingerprint manifest")
    if raw.get("schema_version") != 1 or raw.get("asset_kind") != "equipment_list_card_fingerprint":
        raise ListPageAssetError("card fingerprint manifest schema is unsupported")
    if raw.get("status") != "audited_complete" or raw.get("template_scope") != "full_card":
        raise ListPageAssetError("complete card fingerprint templates are unavailable")
    entries = raw.get("templates")
    if not isinstance(entries, list) or not entries:
        raise ListPageAssetError("card fingerprint manifest has no templates")
    root = path.resolve().parent
    result: dict[str, CardFingerprintTemplate] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or set(entry) != {"id", "file", "sha256", "viewport", "threshold", "status"}:
            raise ListPageAssetError("card fingerprint entry is invalid")
        identifier = entry["id"]
        if not _non_blank(identifier) or entry["status"] != "audited":
            raise ListPageAssetError("card fingerprint entry is not audited")
        filename = entry["file"]
        expected_sha = str(entry["sha256"]).lower()
        viewport = entry["viewport"]
        threshold = entry["threshold"]
        if not _non_blank(filename) or not _SHA256.fullmatch(expected_sha):
            raise ListPageAssetError("card fingerprint hash metadata is invalid")
        if not isinstance(viewport, list) or len(viewport) != 2 or any(not isinstance(value, int) or value <= 0 for value in viewport):
            raise ListPageAssetError("card fingerprint viewport is invalid")
        if not _confidence(threshold) or float(threshold) < MIN_TEMPLATE_CONFIDENCE:
            raise ListPageAssetError("card fingerprint threshold is below minimum")
        asset = (root / str(filename)).resolve()
        if asset.parent != root:
            raise ListPageAssetError("card fingerprint path escapes manifest root")
        try:
            payload = asset.read_bytes()
        except OSError as exc:
            raise ListPageAssetError("card fingerprint asset is unavailable") from exc
        if hashlib.sha256(payload).hexdigest() != expected_sha:
            raise ListPageAssetError("card fingerprint hash mismatch")
        if identifier in result:
            raise ListPageAssetError("duplicate card fingerprint identifier")
        result[str(identifier)] = CardFingerprintTemplate(str(identifier), asset, expected_sha, tuple(viewport), float(threshold))
    return dict(sorted(result.items()))


class ManifestCardFingerprintReader:
    """Exact, deterministic reader for an audited full-card template bundle."""

    def __init__(self, templates: Mapping[str, CardFingerprintTemplate]) -> None:
        if not isinstance(templates, Mapping) or not templates:
            raise ListPageAssetError("card fingerprint templates are required")
        self._templates = dict(templates)

    def match_template(self, region_name: str, crop_png: bytes) -> Mapping[str, Any]:
        if not isinstance(region_name, str) or not isinstance(crop_png, bytes):
            raise ListPageAssetError("card fingerprint input is invalid")
        digest = hashlib.sha256(crop_png).hexdigest()
        matches = [template for template in self._templates.values() if template.sha256 == digest]
        if len(matches) != 1:
            raise ListPageAssetError("card fingerprint is not a unique audited match")
        template = matches[0]
        return {"visual_fingerprint": digest, "score": {"score": 1.0, "threshold": template.threshold}}


def build_audited_card_template_reader(
    manifest_path: str | Path | None = None,
) -> ManifestCardFingerprintReader:
    return ManifestCardFingerprintReader(load_card_fingerprint_templates(manifest_path))


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ListPageAssetError(f"{label} cannot be read") from exc
    if not isinstance(raw, Mapping):
        raise ListPageAssetError(f"{label} must be an object")
    return raw


def _non_blank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _confidence(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= float(value) <= 1


__all__ = [
    "CARD_TEMPLATE_MANIFEST",
    "FIELD_MAPPING_MANIFEST",
    "CardFingerprintTemplate",
    "ListFieldMapping",
    "ListPageAssetError",
    "ManifestCardFingerprintReader",
    "REQUIRED_LIST_FIELDS",
    "build_audited_card_template_reader",
    "load_card_fingerprint_templates",
    "load_list_field_mapping",
    "normalize_list_field_token",
]
