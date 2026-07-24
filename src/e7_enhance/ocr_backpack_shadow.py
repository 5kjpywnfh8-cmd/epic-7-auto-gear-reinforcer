"""Read-only OCR shadow finalization for a uniquely paired backpack item."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from .models import Gear
from .mumu_player_data import enriched_items, instance_id, validate_same_batch_raw
from .ocr_backpack_pair import pair_manifest
from .ocr_normalize import compare_shadow_advice, normalize_ocr_payload, stable_advice_hash
from .enhance_policy import advise_gear


def canonical_reference(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a same-batch player item to the formal Gear representation."""
    result = Gear.from_dict(item).to_dict()
    result["instanceId"] = str(item.get("instanceId") or item.get("ingameId") or "")
    result["itemSource"] = str(item.get("itemSource") or "normal_85")
    result["gearSource"] = str(item.get("gearSource") or "normal_85")
    return result


def finalize_shadow(
    manifest: dict[str, Any],
    ocr_payload: dict[str, Any],
    player_data: object,
    reader_result: object,
    *,
    player_data_path: str,
    reader_result_path: str,
    player_data_bytes: bytes,
    reader_result_bytes: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pair, normalize and compare one OCR record without side effects."""
    paired = pair_manifest(
        manifest,
        player_data,
        reader_result,
        player_data_path=player_data_path,
        reader_result_path=reader_result_path,
        player_data_bytes=player_data_bytes,
        reader_result_bytes=reader_result_bytes,
    )
    items = enriched_items(player_data, reader_result)
    validate_same_batch_raw(items, reader_result)
    by_id = {instance_id(item): item for item in items}
    source_name = Path(str(ocr_payload.get("source_path") or "")).name
    record = next(
        (row for row in paired.get("records") or []
         if row.get("match_status") == "matched" and Path(str(row.get("file") or "")).name == source_name),
        None,
    )
    if record is None:
        raise ValueError(f"OCR screenshot is not a uniquely paired record: {source_name}")
    item = by_id.get(str(record.get("instanceId") or ""))
    if item is None:
        raise ValueError("paired instance is missing from same-batch item set")
    reference_gear = canonical_reference(item)
    capture = {
        "source_path": ocr_payload.get("source_path"),
        "source_sha256": ocr_payload.get("source_sha256"),
        "source_size": ocr_payload.get("source_size"),
        "source_dimensions": ocr_payload.get("source_dimensions"),
    }
    regions = {
        "crop_bounds": ocr_payload.get("crop_bounds"),
        "set_bounds": ocr_payload.get("set_bounds"),
        "experience_context": ocr_payload.get("experience_context"),
    }
    parsed_payload = dict(ocr_payload.get("parsed") or {})
    parsed_fields = dict(parsed_payload.get("fields") or {})
    parsed_fields.update({
        "itemSource": reference_gear.get("itemSource") or "normal_85",
        "gearSource": reference_gear.get("gearSource") or "normal_85",
        "instanceId": reference_gear.get("instanceId") or "",
    })
    parsed_payload["fields"] = parsed_fields
    normalized = normalize_ocr_payload(
        parsed_payload,
        capture,
        regions,
        reference_gear=reference_gear,
    )
    comparison = compare_shadow_advice(normalized, reference_gear)
    reference_advice = advise_gear(
        Gear.from_dict(reference_gear),
        item_source=str(reference_gear.get("itemSource") or "normal_85"),
        gear_source=str(reference_gear.get("gearSource") or "normal_85"),
    )
    record["ocr_shadow"] = {
        "accepted": bool(normalized.get("accepted")),
        "rejection_reasons": list(normalized.get("rejection_reasons") or []),
        "strategy_input_source": (normalized.get("shadow_projection") or {}).get("source"),
        "advice_hash": normalized.get("advice_hash"),
        "advice_comparison": comparison,
        "click_performed": False,
    }
    paired["ocr_gate"] = {
        "status": "passed_read_only_shadow_insufficient_samples" if normalized.get("accepted") and comparison.get("matched") else "rejected_ocr_shadow",
        "minimum_field_confidence": 0.98,
        "raw_result": "ocr_raw.json",
        "raw_result_sha256": sha256(ocr_payload.get("_raw_bytes", b"")).hexdigest() if isinstance(ocr_payload.get("_raw_bytes"), bytes) else None,
        "accepted_sample_count": 1 if normalized.get("accepted") and comparison.get("matched") else 0,
        "minimum_independent_samples": 10,
        "rejection_reasons": list(normalized.get("rejection_reasons") or []),
        "click_performed": False,
    }
    shadow = {
        "schema_version": 1,
        "mode": "read_only_backpack_ocr_shadow",
        "batch": paired.get("batch"),
        "screenshot_id": record.get("screenshot_id"),
        "instanceId": record.get("instanceId"),
        "ocr": normalized,
        "advice_comparison": comparison,
        "reference_advice_hash": stable_advice_hash(reference_advice),
        "reference_advice_summary": reference_advice.get("summary"),
        "click_performed": False,
    }
    return paired, shadow
