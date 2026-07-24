"""Read-only pairing for batch 002 against validated schema 1.2 player data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.mumu_player_data import enriched_items, instance_id, validate_same_batch_raw

DEFAULT_BATCH = ROOT / "manual_acceptance" / "ocr_stage1" / "batch_002"
SET_ALIASES = {"set_riposte": "RiposteSet"}

def _stat(stat: dict[str, Any]) -> tuple[str, float]:
    return str(stat.get("type")), float(stat.get("value"))

def _set_name(value: object) -> str:
    return SET_ALIASES.get(str(value), str(value))

def exact_matches(items: list[dict[str, Any]], fields: dict[str, Any]) -> list[dict[str, Any]]:
    expected_substats = sorted(_stat(stat) for stat in fields["substats"])
    expected_enhance = int(fields["enhance"]) // 3 * 3
    result = []
    for item in items:
        if (_set_name(item.get("set")) != fields["set"] or (item.get("gear") or item.get("slot")) != fields["slot"]
                or any(item.get(key) != fields[key] for key in ("rank", "level")) or int(item.get("enhance", -1)) != expected_enhance):
            continue
        if _stat(item.get("main") or {}) == _stat(fields["main"]) and sorted(_stat(stat) for stat in item.get("substats") or []) == expected_substats:
            result.append(item)
    return result

def pair_record(record: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = exact_matches(items, record["visible_fields"])
    status = "matched" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
    return {"screenshot_id": record["screenshot_id"], "match_status": status, "instanceId": instance_id(candidates[0]) if status == "matched" else None, "candidate_count": len(candidates), "candidate_instance_ids": [instance_id(item) for item in candidates], "click_performed": False}

def pair_batch(manifest: dict[str, Any], player_data: object, reader_result: object) -> list[dict[str, Any]]:
    items = enriched_items(player_data, reader_result)
    return [pair_record(record, items) for record in manifest.get("records") or []]

def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def build_output(manifest: dict[str, Any], player_data: object, reader_result: object) -> dict[str, Any]:
    items = enriched_items(player_data, reader_result)
    raw_items = validate_same_batch_raw(items, reader_result)
    matches = {row["screenshot_id"]: pair_record(row, items) for row in manifest.get("records") or []}
    records = [{**row, **matches[row["screenshot_id"]]} for row in manifest.get("records") or []]
    matched_ids = {row["instanceId"] for row in records if row["match_status"] == "matched"}
    reference = {
        **(manifest.get("reference") or {}),
        "source_schema": "epic7_tools.player_data/1.2",
        "item_count": len(items),
        "instance_id_unique_count": len({instance_id(item) for item in items}),
        "raw_item_count": len(raw_items),
        "raw_evidence_complete": True,
    }
    gate = {
        "status": "ocr_engine_required_for_shadow" if len(matched_ids) >= 2 else "pairing_insufficient_for_ocr",
        "unique_matched_gear_count": len(matched_ids),
        "reason": "no_ocr_engine_configured" if len(matched_ids) >= 2 else "no_unique_candidate",
    }
    return {**manifest, "mode": "read_only_same_batch_pairing", "reference": reference, "ocr_shadow_gate": gate, "records": records}

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--player-data", type=Path, required=True)
    parser.add_argument("--reader-result", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    manifest_path = args.manifest or args.batch / "manifest.json"
    output_path = args.output or manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    player_bytes = args.player_data.read_bytes()
    reader_bytes = args.reader_result.read_bytes()
    player_data = json.loads(player_bytes)
    reader_result = json.loads(reader_bytes)
    manifest["reference"] = {
        **(manifest.get("reference") or {}),
        "path": str(args.player_data),
        "sha256": hashlib.sha256(player_bytes).hexdigest(),
        "status": "current_same_batch_player_data",
        "reader_result_path": str(args.reader_result),
        "reader_result_sha256": hashlib.sha256(reader_bytes).hexdigest(),
    }
    output = build_output(manifest, player_data, reader_result)
    _atomic_json(output_path, output)
    print(json.dumps({"output": str(output_path), "records": len(output["records"])}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
