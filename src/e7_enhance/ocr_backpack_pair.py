"""Strict same-batch pairing for backpack OCR screenshots."""
from __future__ import annotations

from hashlib import sha256
from typing import Any

from .mumu_player_data import enriched_items, instance_id, validate_same_batch_raw
from .rules import SET_ALIASES


def _set_code(value: object) -> str | None:
    return SET_ALIASES.get(str(value))


def _stat(stat: dict[str, Any]) -> tuple[str, float]:
    return str(stat.get("type")), float(stat.get("value"))


def _visible_main_matches(
    item: dict[str, Any],
    raw: dict[str, Any],
    fields: dict[str, Any],
) -> bool:
    expected = _stat(fields["main"])
    if str((item.get("main") or {}).get("type")) != expected[0]:
        return False
    mode = fields.get("main_value_mode")
    if mode == "current_item_main_value":
        current_main = _stat(item.get("main") or {})
        return current_main == expected
    if mode != "raw_main_stat_base_for_plus0" or int(fields["enhance"]) != 0:
        raise ValueError("unsupported backpack main-value matching mode")
    value = raw.get("mainStatBaseValue")
    if not isinstance(value, (int, float)):
        return False
    value = float(value)
    if expected[0].endswith("Percent") and abs(value) <= 1:
        value *= 100
    return value == expected[1]


def exact_matches(
    items: list[dict[str, Any]],
    raw_by_id: dict[str, dict[str, Any]],
    fields: dict[str, Any],
) -> list[dict[str, Any]]:
    expected_substats = sorted(_stat(stat) for stat in fields["substats"])
    expected_enhance = int(fields["enhance"]) // 3 * 3
    expected_set = _set_code(fields["set"])
    if expected_set is None:
        return []
    result = []
    for item in items:
        identity = instance_id(item)
        raw = raw_by_id.get(identity)
        if not isinstance(raw, dict):
            continue
        if (
            _set_code(item.get("set")) != expected_set
            or (item.get("gear") or item.get("slot")) != fields["slot"]
            or item.get("rank") != fields["rank"]
            or int(item.get("level", -1)) != int(fields["level"])
            or int(item.get("enhance", -1)) != expected_enhance
        ):
            continue
        if not _visible_main_matches(item, raw, fields):
            continue
        if sorted(_stat(stat) for stat in item.get("substats") or []) != expected_substats:
            continue
        result.append(item)
    return result


def pair_manifest(
    manifest: dict[str, Any],
    player_data: object,
    reader_result: object,
    *,
    player_data_path: str,
    reader_result_path: str,
    player_data_bytes: bytes,
    reader_result_bytes: bytes,
) -> dict[str, Any]:
    items = enriched_items(player_data, reader_result)
    raw_items = validate_same_batch_raw(items, reader_result)
    raw_by_id = {instance_id(item): item["raw"] for item in raw_items}
    records = []
    for record in manifest.get("records") or []:
        candidates = exact_matches(items, raw_by_id, record["visible_fields"])
        status = "matched" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
        records.append({
            **record,
            "match_status": status,
            "instanceId": instance_id(candidates[0]) if status == "matched" else None,
            "candidate_count": len(candidates),
            "candidate_instance_ids": [instance_id(item) for item in candidates],
            "match_reason": "all_visible_fields_and_raw_plus0_main_value_match" if status == "matched" else "no_unique_candidate",
            "click_performed": False,
        })
    matched_ids = {record["instanceId"] for record in records if record["match_status"] == "matched"}
    matched_ranks = sorted({
        str(item.get("rank")) for item in items if instance_id(item) in matched_ids
    })
    if not matched_ids:
        advice_gate = {"status": "pairing_not_passed", "matched_ranks": matched_ranks}
    elif any(rank not in {"Epic", "Heroic"} for rank in matched_ranks):
        advice_gate = {"status": "unsupported_rank", "matched_ranks": matched_ranks}
    else:
        advice_gate = {"status": "ready_for_ocr_engine", "matched_ranks": matched_ranks}
    reference = {
        "path": player_data_path,
        "sha256": sha256(player_data_bytes).hexdigest(),
        "reader_result_path": reader_result_path,
        "reader_result_sha256": sha256(reader_result_bytes).hexdigest(),
        "source_schema": "epic7_tools.player_data/1.2",
        "item_count": len(items),
        "instance_id_unique_count": len({instance_id(item) for item in items}),
        "raw_item_count": len(raw_items),
        "raw_evidence_complete": True,
        "status": "current_same_batch_player_data",
    }
    return {
        **manifest,
        "mode": "read_only_backpack_same_batch_pairing",
        "reference": reference,
        "pairing_gate": {
            "status": "passed_for_read_only_shadow" if matched_ids else "pairing_insufficient_for_ocr",
            "unique_matched_gear_count": len(matched_ids),
        },
        "advice_gate": advice_gate,
        "records": records,
    }
