"""Audited offline visual templates for equipment set icons.

The loader is deliberately filesystem-only.  The manifest records the public
source for provenance, but no runtime path performs network access or template
matching.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
import zlib

from .visual_adb import PNG_SIGNATURE, parse_png_viewport


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "assets" / "visual" / "set_icons" / "fribbels"
TEMPLATE_MANIFEST = TEMPLATE_ROOT / "manifest.json"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BLOB_SHA = re.compile(r"^[0-9a-f]{40}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[a-z0-9_]+$")
_REPOSITORY = "fribbels/Fribbels-Epic-7-Optimizer"


class VisualTemplateError(RuntimeError):
    """A template set cannot be trusted as a complete offline bundle."""


@dataclass(frozen=True)
class SetIconTemplate:
    """One verified local set icon and its immutable provenance metadata."""

    identifier: str
    path: Path
    source_url: str
    source_blob_sha: str
    sha256: str
    viewport: tuple[int, int]
    byte_size: int


def load_set_icon_templates(
    manifest_path: str | Path | None = None,
) -> Mapping[str, SetIconTemplate]:
    """Load and verify the complete Fribbels set-icon bundle from disk.

    The function intentionally validates every entry before returning any
    mapping.  A missing or altered icon therefore cannot silently produce a
    partially trusted template set.
    """

    manifest = Path(manifest_path) if manifest_path is not None else TEMPLATE_MANIFEST
    manifest = manifest.resolve()
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VisualTemplateError("set icon manifest cannot be read") from exc
    if not isinstance(raw, Mapping):
        raise VisualTemplateError("set icon manifest must be an object")
    if raw.get("schema_version") != 1 or raw.get("template_set") != "fribbels_set_icons_v1":
        raise VisualTemplateError("set icon manifest schema is unsupported")
    commit = str(raw.get("commit") or "")
    if raw.get("repository") != _REPOSITORY or not _COMMIT.fullmatch(commit):
        raise VisualTemplateError("set icon manifest source is not fixed")
    entries = raw.get("templates")
    if not isinstance(entries, list) or not entries:
        raise VisualTemplateError("set icon manifest has no templates")

    root = manifest.parent.resolve()
    verified: dict[str, SetIconTemplate] = {}
    for entry in entries:
        item = _verify_entry(entry, root, commit)
        if item.identifier in verified:
            raise VisualTemplateError(f"duplicate set icon identifier:{item.identifier}")
        verified[item.identifier] = item
    if "hit" not in verified:
        raise VisualTemplateError("set icon bundle is missing the required hit template")
    return dict(sorted(verified.items()))


def _verify_entry(entry: Any, root: Path, commit: str) -> SetIconTemplate:
    if not isinstance(entry, Mapping):
        raise VisualTemplateError("set icon manifest entry is invalid")
    identifier = str(entry.get("id") or "")
    filename = str(entry.get("filename") or "")
    if not _IDENTIFIER.fullmatch(identifier) or filename != f"set{identifier}.png":
        raise VisualTemplateError("set icon identifier or filename is invalid")
    path = (root / filename).resolve()
    if path.parent != root or path.name != filename:
        raise VisualTemplateError(f"set icon path escapes manifest root:{identifier}")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise VisualTemplateError(f"set icon file is unavailable:{identifier}") from exc
    expected_sha = str(entry.get("sha256") or "").lower()
    blob_sha = str(entry.get("source_blob_sha") or "").lower()
    if not _SHA256.fullmatch(expected_sha) or not _BLOB_SHA.fullmatch(blob_sha):
        raise VisualTemplateError(f"set icon hash metadata is invalid:{identifier}")
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha:
        raise VisualTemplateError(f"set icon hash mismatch:{identifier}")
    try:
        # A subset of the upstream files contains an opaque source-asset
        # suffix after the first valid PNG IEND marker.  Validate the complete
        # first PNG, while retaining the exact upstream bytes for hash checks.
        viewport = parse_png_viewport(payload[:_first_png_end(payload)])
    except Exception as exc:
        raise VisualTemplateError(f"set icon PNG is invalid:{identifier}") from exc
    expected_viewport = (entry.get("width"), entry.get("height"))
    if expected_viewport != viewport or entry.get("bytes") != len(payload):
        raise VisualTemplateError(f"set icon dimensions or size mismatch:{identifier}")
    source_url = str(entry.get("source_url") or "")
    expected_url = f"https://raw.githubusercontent.com/{_REPOSITORY}/{commit}/app/assets/{filename}"
    if source_url != expected_url:
        raise VisualTemplateError(f"set icon source URL is invalid:{identifier}")
    return SetIconTemplate(
        identifier=identifier,
        path=path,
        source_url=source_url,
        source_blob_sha=blob_sha,
        sha256=actual_sha,
        viewport=viewport,
        byte_size=len(payload),
    )


def _first_png_end(payload: bytes) -> int:
    """Return the end of the first PNG stream, rejecting malformed chunks."""

    if not isinstance(payload, bytes) or not payload.startswith(PNG_SIGNATURE):
        raise ValueError("PNG signature is missing")
    offset = len(PNG_SIGNATURE)
    while offset + 12 <= len(payload):
        length = int.from_bytes(payload[offset:offset + 4], "big")
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if data_end > len(payload) or crc_end > len(payload):
            raise ValueError("PNG chunk is truncated")
        kind = payload[offset + 4:offset + 8]
        data = payload[data_start:data_end]
        expected = int.from_bytes(payload[data_end:crc_end], "big")
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected:
            raise ValueError("PNG chunk checksum is invalid")
        if kind == b"IEND":
            if length != 0:
                raise ValueError("PNG IEND is invalid")
            return crc_end
        offset = crc_end
    raise ValueError("PNG IEND is missing")
