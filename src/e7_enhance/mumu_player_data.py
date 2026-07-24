"""Validation and raw-evidence adaptation for MuMu player-data snapshots."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any

PLAYER_DATA_SCHEMA = "epic7_tools.player_data"
PLAYER_DATA_SCHEMA_VERSION = "1.2"

MAX_OP_COUNTS = {"Normal": 5, "Good": 6, "Rare": 7, "Heroic": 8, "Epic": 9}
OP_OFFSETS = {"Normal": 0, "Good": 1, "Rare": 2, "Heroic": 3, "Epic": 4}


def instance_id(item: dict[str, Any]) -> str:
    return str(
        item.get("ingameId")
        or item.get("instanceId")
        or item.get("instance_id")
        or item.get("id")
        or ""
    ).strip()


def validate_player_data(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("player_data must be an object")
    if payload.get("schema") != PLAYER_DATA_SCHEMA:
        raise ValueError("unsupported player_data schema")
    if str(payload.get("schema_version")) != PLAYER_DATA_SCHEMA_VERSION:
        raise ValueError("unsupported player_data schema_version")
    if not isinstance(payload.get("source"), (str, dict)) or not payload["source"]:
        raise ValueError("player_data source is required")
    counts = payload.get("counts")
    completeness = payload.get("completeness")
    items = payload.get("items")
    if not isinstance(counts, dict) or not isinstance(completeness, dict) or not isinstance(items, list) or not items:
        raise ValueError("player_data requires counts, completeness, and non-empty items")
    count_key = "items" if "items" in counts else "equipment" if "equipment" in counts else None
    if count_key is None or int(counts[count_key]) != len(items):
        raise ValueError("player_data counts do not match items")
    complete = completeness.get("items", completeness.get("equipment", completeness.get("complete")))
    if isinstance(complete, dict):
        complete = complete.get("complete", complete.get("is_complete"))
    if complete is not True:
        raise ValueError("player_data completeness must mark items complete")
    if any(not isinstance(item, dict) for item in items):
        raise ValueError("player_data items must be objects")
    identities = [instance_id(item) for item in items]
    if any(not identity for identity in identities) or len(set(identities)) != len(identities):
        raise ValueError("player_data items require non-empty unique instance IDs")
    return items


def validate_same_batch_raw(items: list[dict[str, Any]], reader_result: object) -> list[dict[str, Any]]:
    data = reader_result.get("data") if isinstance(reader_result, dict) else None
    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list) or not raw_items or any(not isinstance(item, dict) for item in raw_items):
        raise ValueError("reader_result.data.items is required")
    expected_ids = {instance_id(item) for item in items}
    raw_ids = [instance_id(item) for item in raw_items]
    if any(not identity for identity in raw_ids) or len(set(raw_ids)) != len(raw_ids) or set(raw_ids) != expected_ids:
        raise ValueError("reader_result identities do not match player_data")
    if any(not isinstance(item.get("raw"), dict) or not item["raw"] for item in raw_items):
        raise ValueError("reader_result raw evidence is incomplete")
    return raw_items


def _exported_at(player_data: dict[str, Any]) -> str:
    source = player_data.get("source")
    source = source if isinstance(source, dict) else {}
    for value in (player_data.get("export_time"), source.get("imported_at"), source.get("captured_at")):
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("player_data export_time must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ValueError("player_data export_time must include timezone")
        return parsed.isoformat(timespec="seconds")
    raise ValueError("player_data requires export_time or source timestamp")


def derive_enhance(rank: object, raw: object) -> int:
    if not isinstance(raw, dict) or not isinstance(raw.get("op"), list):
        raise ValueError("raw evidence requires op event list")
    name = str(rank)
    if name not in MAX_OP_COUNTS:
        raise ValueError("raw enhancement evidence has unsupported rank")
    count = min(len(raw["op"]) - 1, MAX_OP_COUNTS[name])
    return max((count - OP_OFFSETS[name]) * 3, 0)


def enriched_items(player_data: object, reader_result: object) -> list[dict[str, Any]]:
    items = validate_player_data(player_data)
    raw_items = validate_same_batch_raw(items, reader_result)
    raw_by_id = {instance_id(item): item for item in raw_items}
    derived = {
        instance_id(item): derive_enhance(item.get("rank"), raw_by_id[instance_id(item)]["raw"])
        for item in items
    }
    observed = {instance_id(item): int(item.get("enhance", 0)) for item in items}
    if all(value == 0 for value in observed.values()) and not any(value != 0 for value in derived.values()):
        raise ValueError("player_data enhancement state is untrustworthy: raw also derives all +0")
    if any(value != 0 for value in observed.values()):
        mismatches = [identity for identity, value in observed.items() if value != derived[identity]]
        if mismatches:
            raise ValueError("player_data enhancement state does not match raw evidence")
    result = []
    for item in items:
        copied = dict(item)
        copied["enhance"] = derived[instance_id(item)]
        copied.setdefault("itemSource", "normal_85")
        result.append(copied)
    return result


def archive_payload(source_bytes: bytes, player_data: object, reader_result: object) -> dict[str, Any]:
    if not isinstance(player_data, dict):
        raise ValueError("player_data must be an object")
    items = enriched_items(player_data, reader_result)
    return {
        "source_kind": "full_fribbels_export",
        "source_container": "epic7_tools_player_data_1_2",
        "source_file_sha256": sha256(source_bytes).hexdigest(),
        "exported_at": _exported_at(player_data),
        "items": items,
    }
