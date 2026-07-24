"""Offline validation for single-item manual enhancement evidence.

This module intentionally does not import the policy, score, DP, or simulator
modules.  A verified record means only that the supplied evidence package is
internally consistent; it is not a strategy or automation result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


MIN_OCR_CONFIDENCE = 0.98
EXPECTED_PLAYER_DATA_SHA256 = "3d74e2d69147d5a1053f0ebccc217ed2c64842fa2ce91cce6413e5fea364185b"
EXPECTED_READER_RESULT_SHA256 = "3831f40814c015166794bf44fbd55d153668532d549e612aff431c24e42f900b"
EXPECTED_SNAPSHOT_ID = "20260722_132045"
OPERATION_SCHEMA = "single_item_confirmation.operation/1.0"
SUMMARY_SCHEMA = "single_item_confirmation.offline_summary/1.0"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _json_value(value: Any) -> Any:
    """Make numeric comparisons and output stable for integer-like floats."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _stat_list(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    result = []
    for stat in value:
        if not isinstance(stat, dict) or not isinstance(stat.get("type"), str):
            return None
        stat_value = _number(stat.get("value"))
        if stat_value is None:
            return None
        result.append({"type": stat["type"], "value": _json_value(stat_value)})
    return result


def _main_stat(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not isinstance(value.get("type"), str):
        return None
    stat_value = _number(value.get("value"))
    if stat_value is None:
        return None
    return {"type": value["type"], "value": _json_value(stat_value)}


def _state_from_visible_fields(fields: Any) -> dict[str, Any] | None:
    if not isinstance(fields, dict):
        return None
    level = _integer(fields.get("level"))
    enhance = _integer(fields.get("enhance"))
    gear_score = _number(fields.get("gear_score"))
    main = _main_stat(fields.get("main"))
    substats = _stat_list(fields.get("substats"))
    if (
        not isinstance(fields.get("set"), str)
        or not isinstance(fields.get("slot"), str)
        or not isinstance(fields.get("rank"), str)
        or level is None
        or enhance is None
        or gear_score is None
        or main is None
        or substats is None
    ):
        return None
    return {
        "set": fields["set"],
        "slot": fields["slot"],
        "rank": fields["rank"],
        "level": level,
        "enhance": enhance,
        "main": main,
        "substats": substats,
        "gear_score": _json_value(gear_score),
    }


def _state_from_after(after: Any) -> dict[str, Any] | None:
    if not isinstance(after, dict):
        return None
    enhance = _integer(after.get("enhance"))
    gear_score = _number(after.get("gear_score"))
    main = _main_stat(after.get("main"))
    substats = _stat_list(after.get("substats"))
    if enhance is None or gear_score is None or main is None or substats is None:
        return None
    return {
        "enhance": enhance,
        "main": main,
        "substats": substats,
        "gear_score": _json_value(gear_score),
    }


def _stat_map(stats: list[dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    result: dict[str, dict[str, Any]] = {}
    for stat in stats:
        stat_type = stat["type"]
        if stat_type in result:
            return None
        result[stat_type] = stat
    return result


def _attribute_changes(baseline: dict[str, Any] | None, actual: dict[str, Any] | None) -> list[dict[str, Any]]:
    if baseline is None or actual is None:
        return []
    changes: list[dict[str, Any]] = []
    if baseline["main"]["type"] == actual["main"]["type"] and baseline["main"]["value"] != actual["main"]["value"]:
        changes.append({"field": "main.value", "type": baseline["main"]["type"], "before": baseline["main"]["value"], "after": actual["main"]["value"]})
    baseline_substats = _stat_map(baseline["substats"])
    actual_substats = _stat_map(actual["substats"])
    if baseline_substats is not None and actual_substats is not None:
        for stat_type in baseline_substats:
            if stat_type in actual_substats and baseline_substats[stat_type]["value"] != actual_substats[stat_type]["value"]:
                changes.append({"field": f"substats[{stat_type}].value", "type": stat_type, "before": baseline_substats[stat_type]["value"], "after": actual_substats[stat_type]["value"]})
    if baseline["gear_score"] != actual["gear_score"]:
        changes.append({"field": "gear_score", "before": baseline["gear_score"], "after": actual["gear_score"]})
    return changes


def _display_path(path: Path) -> str:
    return path.as_posix()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, "file_not_found"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "json_root_is_not_object"
    return value, None


def _resolve_pairing_path(manifest_path: Path, manifest: dict[str, Any]) -> Path | None:
    trusted_reference = manifest.get("trusted_reference")
    if not isinstance(trusted_reference, dict):
        return None
    raw_path = trusted_reference.get("pairing_output")
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else manifest_path.parent / path


def _extract_pair_record(pairing: dict[str, Any], instance_id: str) -> tuple[dict[str, Any] | None, str | None]:
    records = pairing.get("records")
    if not isinstance(records, list):
        return None, "pairing_records_missing"
    matching = [record for record in records if isinstance(record, dict) and record.get("instanceId") == instance_id]
    if len(matching) != 1:
        return None, "pairing_instance_not_unique"
    return matching[0], None


def _check_resources(manifest: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    authorization = manifest.get("authorization")
    before = manifest.get("before")
    after = manifest.get("after")
    if not isinstance(authorization, dict) or not isinstance(before, dict) or not isinstance(after, dict):
        reasons.append("authorization_or_resource_sections_missing")
        return {"within_limits": False}
    limits = authorization.get("resource_limits")
    allowed = authorization.get("allowed_material_sources")
    selected = before.get("selected_materials")
    actual_delta = after.get("material_selection_delta")
    pending_delta = after.get("pending_material_delta_after_operation")
    if not isinstance(limits, dict) or not isinstance(allowed, list) or not isinstance(selected, dict) or not isinstance(actual_delta, dict) or not isinstance(pending_delta, dict):
        reasons.append("resource_limit_or_material_evidence_missing")
        return {"within_limits": False}

    selected_out: dict[str, Any] = {}
    actual_out: dict[str, Any] = {}
    limit_out: dict[str, Any] = {}
    within_limits = True
    # Gold is shown in the material preview but is accounted for separately
    # by the before/after wallet evidence below.
    material_keys = (set(selected) | set(actual_delta) | set(pending_delta)) - {"gold"}
    for material in sorted(material_keys):
        selected_value = _number(selected.get(material, 0))
        actual_value = _number(actual_delta.get(material, 0))
        pending_value = _number(pending_delta.get(material, 0))
        limit_value = _number(limits.get(material, 0))
        selected_out[material] = _json_value(selected_value) if selected_value is not None else selected.get(material)
        actual_out[material] = _json_value(actual_value) if actual_value is not None else actual_delta.get(material)
        limit_out[material] = _json_value(limit_value) if limit_value is not None else limits.get(material)
        if selected_value is None or actual_value is None or pending_value is None or limit_value is None:
            reasons.append(f"invalid_material_value:{material}")
            within_limits = False
            continue
        if material not in allowed and max(selected_value, actual_value) > 0:
            reasons.append(f"material_source_not_allowed:{material}")
            within_limits = False
        if selected_value < 0 or actual_value < 0 or pending_value < 0 or limit_value < 0:
            reasons.append(f"negative_material_value:{material}")
            within_limits = False
        if selected_value > limit_value or actual_value > limit_value:
            reasons.append(f"material_limit_exceeded:{material}")
            within_limits = False
        if actual_value != selected_value:
            reasons.append(f"material_delta_does_not_match_selection:{material}")
            within_limits = False
        if pending_value != 0:
            reasons.append(f"pending_material_delta:{material}")
            within_limits = False

    gold = after.get("gold")
    gold_limit = _number(limits.get("gold"))
    gold_before = _number(gold.get("before")) if isinstance(gold, dict) else None
    gold_after = _number(gold.get("after")) if isinstance(gold, dict) else None
    gold_consumed = _number(gold.get("consumed")) if isinstance(gold, dict) else None
    if gold_limit is None or gold_before is None or gold_after is None or gold_consumed is None:
        reasons.append("gold_evidence_missing_or_invalid")
        within_limits = False
    else:
        if gold_before < 0 or gold_after < 0 or gold_consumed < 0:
            reasons.append("negative_gold_value")
            within_limits = False
        if gold_before - gold_after != gold_consumed:
            reasons.append("gold_delta_does_not_match")
            within_limits = False
        if gold_consumed > gold_limit:
            reasons.append("gold_limit_exceeded")
            within_limits = False
        selected_gold = _number(selected.get("gold", 0))
        if selected_gold is None or selected_gold < 0 or selected_gold != gold_consumed:
            reasons.append("gold_preview_does_not_match_consumption")
            within_limits = False

    return {
        "authorized_limits": {key: _json_value(_number(value)) if _number(value) is not None else value for key, value in sorted(limits.items())},
        "allowed_material_sources": list(allowed),
        "selected_materials": selected_out,
        "actual_material_delta": actual_out,
        "gold": {
            "before": _json_value(gold_before) if gold_before is not None else None,
            "after": _json_value(gold_after) if gold_after is not None else None,
            "consumed": _json_value(gold_consumed) if gold_consumed is not None else None,
            "authorized_limit": _json_value(gold_limit) if gold_limit is not None else None,
        },
        "within_limits": within_limits,
    }


def validate_operation_manifest(manifest_path: Path | str) -> dict[str, Any]:
    """Validate one operation manifest and return a fail-closed report record."""
    manifest_path = Path(manifest_path)
    manifest, load_error = _load_json(manifest_path)
    if load_error:
        return {
            "source_manifest": _display_path(manifest_path),
            "status": "fail_closed",
            "fail_closed_reasons": [load_error],
        }
    assert manifest is not None
    reasons: list[str] = []
    checks: dict[str, bool] = {}
    checks["schema_version"] = manifest.get("schema_version") == OPERATION_SCHEMA
    if not checks["schema_version"]:
        reasons.append("unsupported_operation_schema")
    checks["operation_status_completed"] = str(manifest.get("status", "")).startswith("completed_")
    if not checks["operation_status_completed"]:
        reasons.append("operation_not_completed")

    target = manifest.get("target")
    pre_gate = manifest.get("pre_operation_gate")
    authorization = manifest.get("authorization")
    trusted = manifest.get("trusted_reference")
    if not isinstance(target, dict) or not isinstance(pre_gate, dict) or not isinstance(authorization, dict) or not isinstance(trusted, dict):
        reasons.append("required_manifest_sections_missing")
        target = target if isinstance(target, dict) else {}
        pre_gate = pre_gate if isinstance(pre_gate, dict) else {}
        authorization = authorization if isinstance(authorization, dict) else {}
        trusted = trusted if isinstance(trusted, dict) else {}

    checks["device_gate"] = pre_gate.get("unique_device_count") == 1 and pre_gate.get("other_device_status_count") == 0 and pre_gate.get("device_address_persisted") is False
    if not checks["device_gate"]:
        reasons.append("device_gate_failed")
    checks["page_gate"] = pre_gate.get("page_type") == "enhance_equipment" and pre_gate.get("target_equipment_visible") is True
    if not checks["page_gate"]:
        reasons.append("enhance_page_or_target_visibility_failed")
    minimum_confidence = _number(pre_gate.get("minimum_ocr_confidence"))
    checks["ocr_confidence_gate"] = minimum_confidence is not None and minimum_confidence >= MIN_OCR_CONFIDENCE
    if not checks["ocr_confidence_gate"]:
        reasons.append("ocr_confidence_below_threshold")
    checks["pairing_candidate_gate"] = pre_gate.get("candidate_count") == 1
    if not checks["pairing_candidate_gate"]:
        reasons.append("pairing_candidate_not_unique")
    checks["advice_hash_gate"] = pre_gate.get("advice_hash_matched") is True
    if not checks["advice_hash_gate"]:
        reasons.append("advice_hash_mismatch")
    checks["snapshot_gate"] = pre_gate.get("trusted_snapshot_hash_gate_passed") is True
    if not checks["snapshot_gate"]:
        reasons.append("trusted_snapshot_gate_failed")
    checks["operation_authorization"] = authorization.get("operation_authorized") is True
    if not checks["operation_authorization"]:
        reasons.append("operation_not_authorized")

    checks["trusted_snapshot_identity"] = (
        trusted.get("snapshot_id") == EXPECTED_SNAPSHOT_ID
        and str(trusted.get("player_data_sha256", "")).lower() == EXPECTED_PLAYER_DATA_SHA256
        and str(trusted.get("reader_result_sha256", "")).lower() == EXPECTED_READER_RESULT_SHA256
    )
    if not checks["trusted_snapshot_identity"]:
        reasons.append("trusted_snapshot_identity_mismatch")

    instance_id = target.get("pairer_instanceId")
    review_checkpoint = _integer(target.get("review_checkpoint"))
    if not isinstance(instance_id, str) or not instance_id:
        reasons.append("pairer_instance_id_missing")
        instance_id = ""
    if review_checkpoint is None:
        reasons.append("review_checkpoint_missing")
        review_checkpoint = -1

    pairing_path = _resolve_pairing_path(manifest_path, manifest)
    pairing = None
    pair_record = None
    pairing_error = None
    if pairing_path is None:
        pairing_error = "pairing_output_reference_missing"
    else:
        pairing, pairing_error = _load_json(pairing_path)
    if pairing_error:
        reasons.append(pairing_error)
    if pairing is not None:
        pair_record, pair_record_error = _extract_pair_record(pairing, instance_id)
        if pair_record_error:
            reasons.append(pair_record_error)
        checks["pairing_file_gate"] = pairing.get("pairing_gate", {}).get("status") == "passed_for_read_only_shadow" if isinstance(pairing.get("pairing_gate"), dict) else False
        if not checks["pairing_file_gate"]:
            reasons.append("pairing_file_gate_failed")
    else:
        checks["pairing_file_gate"] = False

    baseline = None
    if pair_record is not None:
        baseline = _state_from_visible_fields(pair_record.get("visible_fields"))
        if baseline is None:
            reasons.append("baseline_fields_invalid")
        if pair_record.get("match_status") != "matched" or pair_record.get("candidate_count") != 1:
            reasons.append("pair_record_not_unique_match")
        if pair_record.get("instanceId") != instance_id:
            reasons.append("pair_record_instance_mismatch")
        ocr_shadow = pair_record.get("ocr_shadow")
        advice_comparison = ocr_shadow.get("advice_comparison") if isinstance(ocr_shadow, dict) else None
        checks["pair_advice_hash_gate"] = isinstance(advice_comparison, dict) and advice_comparison.get("matched") is True
        if not checks["pair_advice_hash_gate"]:
            reasons.append("pair_advice_hash_mismatch")
        pair_reference = pairing.get("reference") if pairing else None
        checks["pair_snapshot_identity"] = isinstance(pair_reference, dict) and str(pair_reference.get("sha256", "")).lower() == EXPECTED_PLAYER_DATA_SHA256 and str(pair_reference.get("reader_result_sha256", "")).lower() == EXPECTED_READER_RESULT_SHA256
        if not checks["pair_snapshot_identity"]:
            reasons.append("pairing_snapshot_identity_mismatch")
    else:
        checks["pair_advice_hash_gate"] = False
        checks["pair_snapshot_identity"] = False

    actual = _state_from_after(manifest.get("after"))
    if actual is None:
        reasons.append("after_fields_invalid")
    target_fields = {
        "set": target.get("set"),
        "slot": target.get("slot"),
        "rank": target.get("rank"),
        "level": target.get("level"),
        "enhance": target.get("enhance_before"),
    }
    checks["target_matches_baseline"] = baseline is not None and all(target_fields[key] == baseline[key] for key in target_fields)
    if not checks["target_matches_baseline"]:
        reasons.append("target_does_not_match_pairing_baseline")
    checks["checkpoint_reached"] = actual is not None and actual.get("enhance") == review_checkpoint
    if not checks["checkpoint_reached"]:
        reasons.append("review_checkpoint_not_reached")

    shadow_advice = pre_gate.get("shadow_advice") if isinstance(pre_gate.get("shadow_advice"), dict) else {}
    checks["shadow_checkpoint_matches"] = shadow_advice.get("next_check_at") == review_checkpoint
    if not checks["shadow_checkpoint_matches"]:
        reasons.append("shadow_advice_checkpoint_mismatch")

    actions = manifest.get("actions")
    checks["single_action_gate"] = (
        isinstance(actions, list)
        and len(actions) == 1
        and isinstance(actions[0], dict)
        and actions[0].get("sequence") == 1
        and actions[0].get("click_count") == 1
        and actions[0].get("target") == "enhance_button"
        and actions[0].get("result") == "accepted"
    )
    if not checks["single_action_gate"]:
        reasons.append("single_authorized_enhance_action_gate_failed")
    stop_reason = manifest.get("stop_reason")
    checks["stop_reason_gate"] = isinstance(stop_reason, str) and "review_checkpoint" in stop_reason and "no further operation" in stop_reason
    if not checks["stop_reason_gate"]:
        reasons.append("stop_reason_does_not_prove_immediate_stop")

    changes = _attribute_changes(baseline, actual)
    if baseline is not None and actual is not None:
        baseline_substats = _stat_map(baseline["substats"])
        actual_substats = _stat_map(actual["substats"])
        checks["attribute_types_unchanged"] = baseline["main"]["type"] == actual["main"]["type"] and baseline_substats is not None and actual_substats is not None and set(baseline_substats) == set(actual_substats)
        if not checks["attribute_types_unchanged"]:
            reasons.append("attribute_types_changed_or_duplicated")
        checks["attribute_change_observed"] = any(change["field"] != "gear_score" for change in changes)
        if not checks["attribute_change_observed"]:
            reasons.append("no_attribute_change_observed")
    else:
        checks["attribute_types_unchanged"] = False
        checks["attribute_change_observed"] = False

    resources = _check_resources(manifest, reasons)
    checks["resource_gate"] = resources.get("within_limits") is True
    if not checks["resource_gate"] and "resource_limit_or_material_evidence_missing" not in reasons:
        reasons.append("resource_gate_failed")

    # Preserve first occurrence while keeping the report readable.
    reasons = list(dict.fromkeys(reasons))
    return {
        "source_manifest": _display_path(manifest_path),
        "status": "verified" if not reasons else "fail_closed",
        "target": {
            "batch": target.get("batch"),
            "instance_id": instance_id or None,
            "level": target.get("level"),
            "slot": target.get("slot"),
            "set": target.get("set"),
            "rank": target.get("rank"),
            "enhance_before": target.get("enhance_before"),
            "review_checkpoint": review_checkpoint if review_checkpoint >= 0 else None,
        },
        "baseline": baseline,
        "actual": actual,
        "attribute_changes": changes,
        "shadow_advice": shadow_advice,
        "checkpoint": {
            "requested": review_checkpoint if review_checkpoint >= 0 else None,
            "reached": actual.get("enhance") if actual is not None else None,
            "matches": checks["checkpoint_reached"],
        },
        "resources": resources,
        "stop_reason": stop_reason,
        "checks": checks,
        "fail_closed_reasons": reasons,
        "formal_strategy_modified": False,
    }


def discover_operation_manifests(root: Path | str) -> list[Path]:
    root = Path(root)
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("operation_manifest.json") if path.is_file())


def summarize_manifests(paths: Iterable[Path | str]) -> dict[str, Any]:
    manifest_paths = sorted({Path(path) for path in paths})
    records = [validate_operation_manifest(path) for path in manifest_paths]
    verified_count = sum(record.get("status") == "verified" for record in records)
    fail_closed_count = len(records) - verified_count
    return {
        "schema_version": SUMMARY_SCHEMA,
        "scope": "offline_read_only_single_item_confirmation_evidence",
        "formal_strategy_modified": False,
        "manifest_count": len(records),
        "verified_count": verified_count,
        "fail_closed_count": fail_closed_count,
        "status": "verified" if records and fail_closed_count == 0 else "fail_closed",
        "records": records,
    }


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value if value is not None else "-")


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 单件人工确认强化结果离线汇总",
        "",
        f"- 汇总状态：`{summary.get('status', 'fail_closed')}`",
        f"- 操作包数量：`{summary.get('manifest_count', 0)}`",
        f"- 证据内部一致：`{summary.get('verified_count', 0)}`",
        f"- fail closed：`{summary.get('fail_closed_count', 0)}`",
        "- 范围：仅离线校验操作证据，不代表正式策略、DP、评分或自动化发布结论。",
        "- 正式策略是否修改：`false`",
        "",
        "## 记录",
        "",
    ]
    records = summary.get("records") or []
    if not records:
        lines.append("没有发现 `operation_manifest.json`。")
        return "\n".join(lines) + "\n"
    for index, record in enumerate(records, 1):
        target = record.get("target") or {}
        lines.extend([
            f"### {index}. batch {target.get('batch') or '-'} / {target.get('instance_id') or '-'}",
            "",
            f"- 状态：`{record.get('status', 'fail_closed')}`",
            f"- 装备：{target.get('level') or '-'}级 {target.get('set') or '-'} {target.get('slot') or '-'}，`{target.get('rank') or '-'}`",
            f"- 复核节点：`+{target.get('enhance_before') if target.get('enhance_before') is not None else '-'} -> +{target.get('review_checkpoint') if target.get('review_checkpoint') is not None else '-'}`",
            f"- 影子建议：`{_text(record.get('shadow_advice') or {})}`",
            f"- 资源闸门：`{_text((record.get('resources') or {}).get('within_limits'))}`，消耗：`{_text(record.get('resources') or {})}`",
            f"- 停止原因：`{record.get('stop_reason') or '-'}`",
            "",
            "| 字段 | 基线 | 实际结果 |",
            "| --- | --- | --- |",
        ])
        baseline = record.get("baseline") or {}
        actual = record.get("actual") or {}
        lines.extend([
            f"| 强化等级 | {_text(baseline.get('enhance'))} | {_text(actual.get('enhance'))} |",
            f"| 主属性 | {_text(baseline.get('main'))} | {_text(actual.get('main'))} |",
            f"| 副属性 | {_text(baseline.get('substats'))} | {_text(actual.get('substats'))} |",
            f"| 装备分数 | {_text(baseline.get('gear_score'))} | {_text(actual.get('gear_score'))} |",
            "",
            f"- 变化字段：`{_text(record.get('attribute_changes') or [])}`",
            f"- 关键检查：`{_text(record.get('checks') or {})}`",
            f"- fail-closed 原因：`{_text(record.get('fail_closed_reasons') or [])}`",
            "",
        ])
    return "\n".join(lines)


def write_summary(summary: dict[str, Any], output_json: Path | str, output_markdown: Path | str) -> None:
    output_json = Path(output_json)
    output_markdown = Path(output_markdown)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_markdown.write_text(render_markdown(summary), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线校验单件人工确认强化操作证据")
    parser.add_argument("--input", action="append", type=Path, help="operation_manifest.json，可重复")
    parser.add_argument("--root", type=Path, help="递归发现 operation_manifest.json 的目录")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args(argv)
    paths: list[Path] = list(args.input or [])
    if args.root:
        paths.extend(discover_operation_manifests(args.root))
    if not paths:
        parser.error("至少提供 --input 或 --root")
    summary = summarize_manifests(paths)
    write_summary(summary, args.output_json, args.output_md)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
