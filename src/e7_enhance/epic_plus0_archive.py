"""Append-only archive of real post-freeze normal Epic +0 equipment.

This archive is deliberately broader than the frozen Holdout. It preserves
boots and speed-route items for later research while recording no policy label,
Oracle result, or efficiency metric.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from tools.epic_non_speed_dp_oracle_audit import canonical_fingerprint
from tools.epic_non_speed_early_policy_pareto import _gear_from_item, _speed_hard_route


ARCHIVE_ID = "normal_85_epic_plus0_real_archive_20260719"
SCHEMA_VERSION = 1
SAMPLE_SOURCE = "prospective_runtime_archive"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("exported_at must include timezone")
    return parsed


def _instance_id(item: dict[str, Any]) -> str:
    return str(item.get("ingameId") or item.get("instanceId") or item.get("id") or item.get("instance_id") or "").strip()


def _new_dataset(created_at: str, minimum_exported_at: str) -> dict[str, Any]:
    return {
        "collection_id": ARCHIVE_ID,
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "sample_source": SAMPLE_SOURCE,
        "scope": "post-freeze trusted normal_85 Epic +0; all slots and speed routes retained",
        "minimum_exported_at": minimum_exported_at,
        "progress": {"accepted": 0},
        "items": [],
        "exclusion_log": [],
    }


def load_dataset(path: Path, *, minimum_exported_at: str) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return _new_dataset(datetime.now().astimezone().isoformat(timespec="seconds"), minimum_exported_at)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("collection_id") != ARCHIVE_ID or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("not a compatible real +0 archive")
    if str(data.get("minimum_exported_at")) != str(minimum_exported_at):
        raise ValueError("archive start boundary changed; create a new archive")
    return data


def create_dataset(path: Path, *, minimum_exported_at: str) -> dict[str, Any]:
    """Create or validate the archive file without importing any items."""
    path = Path(path)
    data = load_dataset(path, minimum_exported_at=minimum_exported_at)
    if not path.exists():
        _atomic_json(path, data)
    return data


def _identity_index(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    return (
        {str(row["instance_id"]) for row in data.get("items") or []},
        {str(row["fingerprint"]) for row in data.get("items") or []},
    )


def _exclude(data: dict[str, Any], reason: str, exported_at: str, *, instance_id: str = "", fingerprint: str = "") -> None:
    data["exclusion_log"].append({
        "reason": reason,
        "exported_at": exported_at,
        "instance_id": instance_id,
        "fingerprint": fingerprint,
        "sample_source": SAMPLE_SOURCE,
    })


def _scope_flags(gear: Any) -> dict[str, bool]:
    boots = str(gear.slot).lower() in {"boot", "boots", "shoe", "shoes"}
    speed_route = bool(_speed_hard_route(gear))
    four_substats = len(gear.substats) == 4
    return {
        "boots": boots,
        "speed_hard_route": speed_route,
        "four_substats": four_substats,
        "holdout_candidate": (not boots and not speed_route and four_substats),
    }


def ingest_export(
    path: Path,
    payload: dict[str, Any],
    *,
    known: dict[str, set[str]],
    minimum_exported_at: str,
) -> dict[str, Any]:
    """Append real Epic +0 items from one trusted export without scoring them."""
    path = Path(path)
    data = load_dataset(path, minimum_exported_at=minimum_exported_at)
    if payload.get("source_kind") != "full_fribbels_export" or not payload.get("source_file_sha256"):
        raise ValueError("real +0 archive requires a hashed full_fribbels_export payload")
    exported_at = _parse_time(str(payload.get("exported_at") or ""))
    minimum_time = _parse_time(str(minimum_exported_at))
    if exported_at <= minimum_time:
        raise ValueError("export is not newer than the archive boundary")

    existing_ids, existing_fingerprints = _identity_index(data)
    exclusions: Counter[str] = Counter()
    accepted = 0
    for item in payload.get("items") or payload.get("equipment") or []:
        try:
            gear = _gear_from_item(item)
        except (KeyError, TypeError, ValueError) as exc:
            exclusions[f"invalid_item:{exc}"] += 1
            continue
        instance_id = _instance_id(item)
        fingerprint = canonical_fingerprint(gear)
        if not instance_id:
            exclusions["missing_instance_id"] += 1
            continue
        source = str(item.get("itemSource") or item.get("item_source") or "")
        if source != "normal_85" or gear.rank != "Epic" or gear.level != 85:
            exclusions["outside_normal_85_epic_scope"] += 1
            continue
        if gear.enhance != 0:
            exclusions["not_plus0"] += 1
            continue
        if instance_id in known.get("instance_ids", set()):
            exclusions["known_instance_id"] += 1
            continue
        if fingerprint in known.get("fingerprints", set()):
            exclusions["known_fingerprint"] += 1
            continue
        if instance_id in existing_ids:
            exclusions["archive_instance_id"] += 1
            continue
        if fingerprint in existing_fingerprints:
            exclusions["archive_fingerprint"] += 1
            continue
        flags = _scope_flags(gear)
        sample_id = sha256(_stable_json({
            "instance_id": instance_id,
            "fingerprint": fingerprint,
            "exported_at": exported_at.isoformat(),
        }).encode("utf-8")).hexdigest()
        data["items"].append({
            "sample_id": sample_id,
            "instance_id": instance_id,
            "fingerprint": fingerprint,
            "exported_at": exported_at.isoformat(),
            "source_file_sha256": str(payload["source_file_sha256"]),
            "flags": flags,
            "gear": item,
        })
        existing_ids.add(instance_id)
        existing_fingerprints.add(fingerprint)
        accepted += 1

    data["exclusion_log"].append({"exported_at": exported_at.isoformat(), "counts": dict(sorted(exclusions.items()))})
    data["progress"]["accepted"] = len(data["items"])
    _atomic_json(path, data)
    return {
        "accepted": accepted,
        "status": "collecting",
        "progress": progress_from_data(data),
        "excluded_by_reason": dict(sorted(exclusions.items())),
    }


def progress_from_data(data: dict[str, Any]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for row in data.get("exclusion_log") or []:
        totals.update(row.get("counts") or {})
    return {
        "status": "collecting",
        "accepted": int((data.get("progress") or {}).get("accepted", 0)),
        "excluded_by_reason": dict(sorted(totals.items())),
    }


def progress(path: Path) -> dict[str, Any]:
    return progress_from_data(json.loads(Path(path).read_text(encoding="utf-8")))


def _walk_items(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"rank", "level"}.issubset(value) and ("substats" in value or "subStats" in value):
            yield value
        for child in value.values():
            yield from _walk_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_items(child)
