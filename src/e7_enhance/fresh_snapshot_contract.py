"""Pure offline validation for fresh multi-node enhancement snapshots.

The contract accepts already-collected JSON objects only.  It neither reads a
device nor returns an executable enhancement, click, or material-selection
instruction.  File hashes bind each supplied object through canonical JSON so
callers can validate a self-contained offline evidence package without putting
private source paths or raw payloads into the resulting report.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from .mumu_player_data import derive_enhance, instance_id, validate_player_data, validate_same_batch_raw
from .ocr_backpack_pair import exact_matches


SNAPSHOT_SCHEMA = "e7_enhance.fresh_snapshot/1.0"
REPORT_SCHEMA = "e7_enhance.fresh_snapshot_report/1.0"
MIN_OCR_CONFIDENCE = 0.98
NODES = (0, 3, 6, 9, 12, 15)
REQUIRED_CONFIDENCE_FIELDS = ("set", "slot", "rank", "level", "enhance", "main", "substats")


def canonical_json_sha256(value: object) -> str:
    """Return a stable content hash for an already-parsed JSON value."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _reason(reasons: list[str], value: str) -> None:
    if value not in reasons:
        reasons.append(value)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _sha256(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.lower().strip()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        return None
    return normalized


def _safe_path_identifier(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.replace("\\", "/")
    return not (
        normalized.startswith("/")
        or ":" in normalized
        or any(part == ".." for part in normalized.split("/"))
    )


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _visible_fields(value: object, current_node: int) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    required_strings = ("set", "slot", "rank")
    if any(not isinstance(value.get(key), str) or not value[key] for key in required_strings):
        return None
    if _integer(value.get("level")) is None or _integer(value.get("enhance")) != current_node:
        return None
    main = value.get("main")
    substats = value.get("substats")
    if not isinstance(main, dict) or not isinstance(main.get("type"), str) or _number(main.get("value")) is None:
        return None
    if not isinstance(substats, list) or any(
        not isinstance(stat, dict) or not isinstance(stat.get("type"), str) or _number(stat.get("value")) is None
        for stat in substats
    ):
        return None
    fields = dict(value)
    fields["main_value_mode"] = "raw_main_stat_base_for_plus0" if current_node == 0 else "current_item_main_value"
    return fields


def _target_fingerprint(identity: str) -> str:
    return sha256(identity.encode("utf-8")).hexdigest()


def _validate_snapshot(snapshot: object) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate one package and return its sanitized record plus chain metadata."""
    reasons: list[str] = []
    value = snapshot if isinstance(snapshot, dict) else {}
    current_node = _integer(value.get("current_node"))
    previous_node = value.get("previous_node")
    expected_next_node = value.get("expected_next_node")
    if value.get("schema_version") != SNAPSHOT_SCHEMA:
        _reason(reasons, "unsupported_snapshot_schema")
    if current_node not in NODES:
        _reason(reasons, "unsupported_enhancement_node")
    expected_previous = None if current_node == 0 else current_node - 3 if current_node in NODES else None
    expected_next = None if current_node == 15 else current_node + 3 if current_node in NODES else None
    if previous_node != expected_previous or expected_next_node != expected_next:
        _reason(reasons, "invalid_declared_node_transition")

    operation_id = value.get("operation_id") if isinstance(value.get("operation_id"), str) else ""
    snapshot_id = value.get("snapshot_id") if isinstance(value.get("snapshot_id"), str) else ""
    collection_id = value.get("collection_id") if isinstance(value.get("collection_id"), str) else ""
    captured_at = _timestamp(value.get("collected_at"))
    if not operation_id or not snapshot_id or not collection_id:
        _reason(reasons, "operation_or_snapshot_identity_missing")
    if captured_at is None:
        _reason(reasons, "collection_time_missing_or_invalid")
    if value.get("source_status") != "current_same_batch_player_data":
        _reason(reasons, "source_status_not_current_same_batch")

    expected_result = "initial_snapshot" if current_node == 0 else "enhancement_completed"
    if value.get("operation_result") != expected_result:
        _reason(reasons, "operation_result_unknown_or_incompatible")

    files = value.get("files") if isinstance(value.get("files"), dict) else {}
    player_file = files.get("player_data") if isinstance(files.get("player_data"), dict) else {}
    reader_file = files.get("reader_result") if isinstance(files.get("reader_result"), dict) else {}
    player_batch = player_file.get("batch_id")
    reader_batch = reader_file.get("batch_id")
    if not isinstance(player_batch, str) or not player_batch or player_batch != reader_batch:
        _reason(reasons, "player_and_reader_not_same_batch")
    player_hash = _sha256(player_file.get("sha256"))
    reader_hash = _sha256(reader_file.get("sha256"))
    if player_hash is None or reader_hash is None:
        _reason(reasons, "snapshot_file_hash_missing_or_invalid")
    if not _safe_path_identifier(player_file.get("path_id")) or not _safe_path_identifier(reader_file.get("path_id")):
        _reason(reasons, "snapshot_path_identifier_invalid")
    player_data = value.get("player_data")
    reader_result = value.get("reader_result")
    if player_hash is not None and player_hash != canonical_json_sha256(player_data):
        _reason(reasons, "player_data_hash_mismatch")
    if reader_hash is not None and reader_hash != canonical_json_sha256(reader_result):
        _reason(reasons, "reader_result_hash_mismatch")

    target = value.get("target") if isinstance(value.get("target"), dict) else {}
    target_id = target.get("instance_id") if isinstance(target.get("instance_id"), str) else ""
    fields = _visible_fields(target.get("visible_fields"), current_node if current_node in NODES else -1)
    if not target_id:
        _reason(reasons, "target_instance_id_missing")
    if fields is None:
        _reason(reasons, "target_visible_fields_invalid")
    confidences = target.get("ocr_confidence") if isinstance(target.get("ocr_confidence"), dict) else {}
    for field in REQUIRED_CONFIDENCE_FIELDS:
        confidence = _number(confidences.get(field))
        if confidence is None or confidence < MIN_OCR_CONFIDENCE:
            _reason(reasons, "ocr_confidence_below_threshold_or_missing")
            break

    page = value.get("page") if isinstance(value.get("page"), dict) else {}
    if not (
        page.get("page_type") == "enhance_equipment"
        and page.get("is_unambiguous") is True
        and page.get("target_visible") is True
    ):
        _reason(reasons, "page_not_unambiguous_target_enhance_page")

    advice_hash = value.get("advice_hash")
    if advice_hash is not None and _sha256(advice_hash) is None:
        _reason(reasons, "current_advice_hash_invalid")

    candidates: list[str] = []
    observed_enhance: int | None = None
    try:
        items = validate_player_data(player_data)
        raw_items = validate_same_batch_raw(items, reader_result)
        raw_by_id = {instance_id(item): item["raw"] for item in raw_items}
        if fields is not None:
            candidates = [instance_id(item) for item in exact_matches(items, raw_by_id, fields)]
        target_items = [item for item in items if instance_id(item) == target_id]
        if len(target_items) != 1:
            _reason(reasons, "target_instance_not_unique_in_snapshot")
        else:
            raw = raw_by_id.get(target_id)
            observed_enhance = _integer(target_items[0].get("enhance"))
            if observed_enhance is None or raw is None or derive_enhance(target_items[0].get("rank"), raw) != current_node:
                _reason(reasons, "target_enhancement_not_proven_by_raw")
            elif observed_enhance != current_node:
                _reason(reasons, "target_enhancement_does_not_match_node")
    except (TypeError, ValueError, KeyError):
        _reason(reasons, "player_data_or_raw_evidence_invalid")
    if len(candidates) != 1:
        _reason(reasons, "pairing_candidate_not_unique")
    elif candidates[0] != target_id:
        _reason(reasons, "pairing_candidate_identity_mismatch")

    record = {
        "operation_id": operation_id or None,
        "snapshot_id": snapshot_id or None,
        "collection_id": collection_id or None,
        "current_node": current_node,
        "previous_node": previous_node,
        "expected_next_node": expected_next_node,
        "target_instance_sha256": _target_fingerprint(target_id) if target_id else None,
        "candidate_count": len(candidates),
        "observed_enhance": observed_enhance,
        "status": "verified" if not reasons else "fail_closed",
        "fail_closed_reasons": reasons,
        "continuation_recommendation": None,
    }
    metadata = {
        "operation_id": operation_id,
        "snapshot_id": snapshot_id,
        "collection_id": collection_id,
        "captured_at": captured_at,
        "current_node": current_node,
        "target_id": target_id,
        "player_hash": player_hash,
        "reader_hash": reader_hash,
        "advice_hash": _sha256(advice_hash) if advice_hash is not None else None,
    }
    return record, metadata


def validate_snapshot_contract(snapshots: Iterable[object]) -> dict[str, Any]:
    """Validate ordered node packages without performing any external action."""
    snapshot_list = list(snapshots)
    if not snapshot_list:
        return {
            "schema_version": REPORT_SCHEMA,
            "scope": "offline_fresh_snapshot_repairing_contract",
            "status": "not_ready",
            "formal_strategy_modified": False,
            "snapshot_count": 0,
            "verified_count": 0,
            "fail_closed_count": 0,
            "records": [],
        }

    records_and_metadata = [_validate_snapshot(snapshot) for snapshot in snapshot_list]
    records = [result[0] for result in records_and_metadata]
    metadata = [result[1] for result in records_and_metadata]
    seen_snapshot_ids: set[str] = set()
    seen_collection_ids: set[str] = set()
    seen_player_hashes: set[str] = set()
    seen_reader_hashes: set[str] = set()
    seen_advice_hashes: set[str] = set()
    prior = None
    for record, current in zip(records, metadata):
        reasons = record["fail_closed_reasons"]
        if prior is None and current["current_node"] != 0:
            _reason(reasons, "initial_plus0_node_missing")
        if current["snapshot_id"] in seen_snapshot_ids or current["collection_id"] in seen_collection_ids:
            _reason(reasons, "snapshot_or_collection_id_reused")
        if current["player_hash"] in seen_player_hashes or current["reader_hash"] in seen_reader_hashes:
            _reason(reasons, "prior_snapshot_file_hash_reused")
        if current["advice_hash"] is not None and current["advice_hash"] in seen_advice_hashes:
            _reason(reasons, "prior_advice_hash_reused")
        if prior is not None:
            if current["operation_id"] != prior["operation_id"]:
                _reason(reasons, "operation_id_not_continuous")
            if current["current_node"] != prior["current_node"] + 3:
                _reason(reasons, "node_sequence_jump")
            if current["target_id"] != prior["target_id"]:
                _reason(reasons, "target_instance_drift")
            if current["captured_at"] is None or prior["captured_at"] is None or current["captured_at"] <= prior["captured_at"]:
                _reason(reasons, "collection_order_not_proven")
            if prior["status"] != "verified":
                _reason(reasons, "previous_node_not_verified")
        if current["snapshot_id"]:
            seen_snapshot_ids.add(current["snapshot_id"])
        if current["collection_id"]:
            seen_collection_ids.add(current["collection_id"])
        if current["player_hash"]:
            seen_player_hashes.add(current["player_hash"])
        if current["reader_hash"]:
            seen_reader_hashes.add(current["reader_hash"])
        if current["advice_hash"]:
            seen_advice_hashes.add(current["advice_hash"])
        record["status"] = "verified" if not reasons else "fail_closed"
        prior = {**current, "status": record["status"]}

    verified_count = sum(record["status"] == "verified" for record in records)
    return {
        "schema_version": REPORT_SCHEMA,
        "scope": "offline_fresh_snapshot_repairing_contract",
        "status": "verified" if verified_count == len(records) else "fail_closed",
        "formal_strategy_modified": False,
        "snapshot_count": len(records),
        "verified_count": verified_count,
        "fail_closed_count": len(records) - verified_count,
        "records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Render a stable report that deliberately omits paths and raw evidence."""
    lines = [
        "# 多节点新鲜快照与重新配对契约验证",
        "",
        f"- 状态：`{report.get('status', 'not_ready')}`",
        f"- 快照数量：`{report.get('snapshot_count', 0)}`",
        f"- 通过契约：`{report.get('verified_count', 0)}`",
        f"- fail closed：`{report.get('fail_closed_count', 0)}`",
        "- 范围：纯离线证据校验；不生成点击、选材、资源消耗或继续强化指令。",
        "- 正式策略是否修改：`false`",
        "",
        "| 节点 | 状态 | 候选数 | 原因 |",
        "| --- | --- | ---: | --- |",
    ]
    records = report.get("records") if isinstance(report.get("records"), list) else []
    if not records:
        lines.append("| - | `not_ready` | 0 | 未提供可验证的新鲜节点快照 |")
    for record in records:
        reasons = ", ".join(record.get("fail_closed_reasons") or []) or "-"
        lines.append(
            f"| +{record.get('current_node', '-')} | `{record.get('status', 'fail_closed')}` | "
            f"{record.get('candidate_count', 0)} | `{reasons}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_report(report: dict[str, Any], output_json: Path | str, output_markdown: Path | str) -> None:
    """Write the sanitized machine- and human-readable validation report."""
    output_json = Path(output_json)
    output_markdown = Path(output_markdown)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_markdown.write_text(render_markdown(report), encoding="utf-8")
