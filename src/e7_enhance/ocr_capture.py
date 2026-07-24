"""Read-only screenshot provenance helpers.

This module intentionally never captures a device or window.  Stage 1 only
accepts a user-provided image file and records enough provenance for a later
shadow comparison.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from time import perf_counter


OCR_CAPTURE_SCHEMA_VERSION = 1


def capture_from_file(path: str | Path, *, retries: int = 0) -> dict:
    """Return immutable provenance for an imported screenshot.

    No ADB, window lookup, OCR engine, or clicking is performed here.
    """
    started = perf_counter()
    image_path = Path(path)
    payload = image_path.read_bytes()
    return {
        "schema_version": OCR_CAPTURE_SCHEMA_VERSION,
        "mode": "read_only_import",
        "source": "user_imported_file",
        "path": str(image_path),
        "sha256": sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "capture_elapsed_ms": round((perf_counter() - started) * 1000, 3),
        "retries": max(0, int(retries)),
        "click_performed": False,
    }


def capture_from_bytes(payload: bytes, *, source: str = "synthetic_fixture", retries: int = 0) -> dict:
    """Create test-only provenance without pretending a screen was captured."""
    started = perf_counter()
    return {
        "schema_version": OCR_CAPTURE_SCHEMA_VERSION,
        "mode": "read_only_import",
        "source": str(source),
        "path": None,
        "sha256": sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "capture_elapsed_ms": round((perf_counter() - started) * 1000, 3),
        "retries": max(0, int(retries)),
        "click_performed": False,
    }
