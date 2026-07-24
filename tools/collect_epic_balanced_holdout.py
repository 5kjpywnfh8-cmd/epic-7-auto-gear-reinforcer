"""CLI for the independent Epic balanced +0 blind holdout collection."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance import epic_balanced_holdout as holdout
from src.e7_enhance.gui_support import is_fribbels_export


DEFAULT_FREEZE = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_freeze_20260718.json"
DEFAULT_COLLECTION = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_collection_20260718.json"
DEFAULT_MANIFEST = ROOT / "samples" / "epic_output_8_13_tank_10_17_holdout_manifest_20260718.json"


def _normalize_export_time(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("complete Fribbels export requires export_time")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise ValueError("Fribbels export_time must use YYYY-MM-DD HH:MM:SS or ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone(timedelta(hours=8)))
    return parsed.isoformat(timespec="seconds")


def _trusted_player_snapshot_time(payload: dict) -> str:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("source") != "fribbels_mumu_reader":
        raise ValueError("holdout intake requires a complete Fribbels export or trusted player snapshot")
    imported_at = str(metadata.get("imported_at") or "").strip()
    try:
        parsed = datetime.fromisoformat(imported_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("trusted player snapshot imported_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("trusted player snapshot imported_at must include timezone")

    items = payload.get("items")
    equipment = payload.get("equipment")
    if not isinstance(items, list) or not isinstance(equipment, list):
        raise ValueError("trusted player snapshot requires items and equipment lists")
    try:
        expected_count = int(metadata.get("item_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("trusted player snapshot requires numeric item_count") from exc
    if expected_count != len(items) or expected_count != len(equipment):
        raise ValueError("trusted player snapshot item_count does not match items/equipment")
    required = {"id", "ingameId", "gear", "rank", "set", "level", "enhance", "main", "substats", "raw"}
    if not items or any(not isinstance(item, dict) or not required.issubset(item) or not isinstance(item.get("raw"), dict) for item in items):
        raise ValueError("trusted player snapshot contains incomplete Fribbels items")
    item_ids = {str(item["ingameId"]) for item in items}
    equipment_ids = {str(item.get("ingameId") or "") for item in equipment if isinstance(item, dict)}
    if item_ids != equipment_ids:
        raise ValueError("trusted player snapshot items/equipment identities do not match")
    return parsed.isoformat(timespec="seconds")


def _prepare_payload(source_bytes: bytes) -> dict:
    payload = json.loads(source_bytes.decode("utf-8"))
    if is_fribbels_export(payload):
        exported_at = _normalize_export_time(payload.get("export_time"))
        source_container = "fribbels_export"
    elif isinstance(payload, dict):
        exported_at = _trusted_player_snapshot_time(payload)
        source_container = "fribbels_mumu_player_snapshot"
    else:
        raise ValueError("holdout intake requires a complete Fribbels export or trusted player snapshot")
    for item in payload["items"]:
        if not item.get("itemSource") and not item.get("item_source"):
            item["itemSource"] = "normal_85"
    payload["source_kind"] = "full_fribbels_export"
    payload["source_container"] = source_container
    payload["source_file_sha256"] = sha256(source_bytes).hexdigest()
    payload["exported_at"] = exported_at
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect only blind +0 snapshots for the frozen Epic balanced holdout")
    parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--collection", type=Path, default=DEFAULT_COLLECTION)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--import-json", type=Path)
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args(argv)

    freeze = holdout.freeze_candidate(args.freeze)
    holdout.create_collection(args.collection, freeze)
    if args.import_json:
        source_bytes = args.import_json.read_bytes()
        incoming = _prepare_payload(source_bytes)
        result = holdout.ingest_export(
            args.collection,
            incoming,
            freeze=freeze,
            known=holdout.historical_identity_index(),
            manifest_path=args.manifest,
        )
    else:
        result = holdout.progress(args.collection)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
