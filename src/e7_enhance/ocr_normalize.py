"""Fail-closed normalization of externally supplied OCR text for stage 1."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from time import perf_counter
from typing import Any

from .enhance_policy import advise_gear
from .gui_support import DEFAULT_GEAR_SOURCE, build_gear_dict
from .models import Gear, validate_gear_source_rank, validate_gear_structure
from .rules import RANK_ALIASES, SET_ALIASES, SLOT_ALIASES, STAT_TYPE_TO_KEY


OCR_RESULT_SCHEMA_VERSION = 1
MIN_FIELD_CONFIDENCE = 0.98
_STAT_ALIASES = {
    **STAT_TYPE_TO_KEY,
    "攻击力": "atkFlat", "攻击力%": "atkPct", "攻击%": "atkPct",
    "防御力": "defFlat", "防御力%": "defPct", "防御%": "defPct",
    "生命力": "hpFlat", "生命力%": "hpPct", "生命%": "hpPct",
    "速度": "spd", "暴率": "crit", "爆率": "crit", "暴击": "crit", "爆伤": "cdmg",
    "效果命中": "eff", "命中": "eff", "效果抗性": "res", "抵抗": "res",
    "속도": "spd", "치명확률": "crit", "치명피해": "cdmg", "효과적중": "eff", "효과저항": "res",
}
_CANONICAL_TYPES = {
    "atkFlat": "Attack", "atkPct": "AttackPercent", "defFlat": "Defense", "defPct": "DefensePercent",
    "hpFlat": "Health", "hpPct": "HealthPercent", "spd": "Speed", "crit": "CriticalHitChancePercent",
    "cdmg": "CriticalHitDamagePercent", "eff": "EffectivenessPercent", "res": "EffectResistancePercent",
}


def _clean(value: Any) -> str:
    source = "" if value is None else str(value)
    return re.sub(r"\s+", "", source.replace("％", "%").replace("＋", "+").strip())


def _alias(value: Any, aliases: dict[str, str]) -> str | None:
    text = _clean(value)
    return aliases.get(text) or aliases.get(str(value or "").strip())


def _number(value: Any) -> float | None:
    match = re.fullmatch(r"[+]?([0-9]+(?:\.[0-9]+)?)%?", _clean(value))
    return float(match.group(1)) if match else None


def _integer(value: Any) -> int | None:
    parsed = _number(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


def _field(raw: Any, name: str, parser) -> tuple[dict, Any, list[str]]:
    data = raw if isinstance(raw, dict) else {"text": raw}
    confidence = float(data.get("confidence", 0) or 0)
    source_value = data.get("normalized")
    if source_value is None:
        source_value = data.get("text") if data.get("text") is not None else data.get("raw_text")
    normalized = parser(source_value)
    errors = []
    if confidence < MIN_FIELD_CONFIDENCE:
        errors.append(f"low_confidence:{name}")
    if normalized is None:
        errors.append(f"unrecognized:{name}")
    return {
        "raw_text": str(data.get("raw_text") or data.get("text") or ""), "normalized": normalized,
        "candidates": list(data.get("candidates") or []), "confidence": confidence,
        "accepted": not errors,
    }, normalized, errors


def stable_advice_hash(advice: dict) -> str:
    encoded = json.dumps(advice, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_shadow_gear(ocr_gear: dict[str, Any], reference_gear: dict[str, Any]) -> dict[str, Any]:
    """Use a uniquely paired item as the strategy input after OCR passes.

    A +0 screenshot shows the raw main-stat value, while the formal strategy
    consumes the normalized item value and roll metadata.  Pairing supplies
    those non-visible representation details; the OCR fields remain available
    separately in the result for audit.
    """
    if not isinstance(ocr_gear, dict) or not isinstance(reference_gear, dict):
        raise ValueError("shadow projection requires OCR and reference gear")
    for key in ("set", "slot", "rank", "level", "enhance"):
        if ocr_gear.get(key) != reference_gear.get(key):
            raise ValueError(f"shadow_visible_mismatch:{key}")
    ocr_main = ocr_gear.get("mainStat") or {}
    reference_main = reference_gear.get("mainStat") or {}
    if ocr_main.get("type") != reference_main.get("type"):
        raise ValueError("shadow_visible_mismatch:mainStat.type")
    if int(ocr_gear.get("enhance", 0)) != 0 and ocr_main.get("value") != reference_main.get("value"):
        raise ValueError("shadow_visible_mismatch:mainStat.value")
    ocr_substats = sorted((row.get("type"), row.get("value")) for row in ocr_gear.get("substats") or [])
    reference_substats = sorted((row.get("type"), row.get("value")) for row in reference_gear.get("substats") or [])
    if ocr_substats != reference_substats:
        raise ValueError("shadow_visible_mismatch:substats")
    return deepcopy(reference_gear)


def normalize_ocr_payload(
    payload: dict[str, Any],
    capture: dict,
    regions: dict | None = None,
    reference_gear: dict[str, Any] | None = None,
) -> dict:
    """Build a schema-stable read-only result. Unknown fields always reject."""
    started = perf_counter()
    if isinstance(payload.get("fields"), dict):
        source = {**payload, **payload["fields"]}
    else:
        source = payload
    errors: list[str] = []
    fields: dict[str, Any] = {}
    field_specs = {
        "set": (SET_ALIASES, None), "slot": (SLOT_ALIASES, None), "rank": (RANK_ALIASES, None),
        "enhance": (None, _integer), "level": (None, _integer),
    }
    values: dict[str, Any] = {}
    for name, (aliases, parser) in field_specs.items():
        parser = parser or (lambda value, aliases=aliases: _alias(value, aliases))
        fields[name], values[name], item_errors = _field(source.get(name), name, parser)
        errors.extend(item_errors)

    raw_main = source.get("mainStat") if isinstance(source.get("mainStat"), dict) else {}
    main_type, main_key, item_errors = _field(raw_main.get("type"), "mainStat.type", lambda value: _alias(value, _STAT_ALIASES))
    main_value, main_number, value_errors = _field(raw_main.get("value"), "mainStat.value", _number)
    fields["mainStat"] = {"type": main_type, "value": main_value}
    errors.extend(item_errors + value_errors)

    normalized_substats = []
    field_substats = []
    raw_substats = source.get("substats") if isinstance(source.get("substats"), list) else []
    for index, raw_stat in enumerate(raw_substats):
        raw_stat = raw_stat if isinstance(raw_stat, dict) else {}
        stat_type, stat_key, item_errors = _field(raw_stat.get("type"), f"substats[{index}].type", lambda value: _alias(value, _STAT_ALIASES))
        stat_value, number, value_errors = _field(raw_stat.get("value"), f"substats[{index}].value", _number)
        errors.extend(item_errors + value_errors)
        rolls = raw_stat.get("rolls")
        roll_value = 0
        stat = {"type": stat_type, "value": stat_value}
        if rolls is not None:
            roll_field, roll_value, roll_errors = _field(rolls, f"substats[{index}].rolls", _integer)
            stat["rolls"] = roll_field
            errors.extend(roll_errors)
        field_substats.append(stat)
        normalized_substats.append({"type": _CANONICAL_TYPES.get(stat_key), "value": number, "rolls": roll_value})
    fields["substats"] = field_substats

    gear_data = None
    advice_hash = None
    if not errors:
        form = {
            "set": values["set"], "slot": values["slot"], "rank": values["rank"],
            "enhance": values["enhance"], "level": values["level"],
            "main_type": _CANONICAL_TYPES.get(main_key), "main_value": main_number,
            "substats": normalized_substats, "item_source": str(source.get("itemSource") or "normal_85"),
            "gear_source": str(source.get("gearSource") or DEFAULT_GEAR_SOURCE),
            "instance_id": str(source.get("instanceId") or ""), "code": str(source.get("code") or ""),
        }
        try:
            gear_data = build_gear_dict(form)
            gear = Gear.from_dict(gear_data)
            validate_gear_structure(gear)
            validate_gear_source_rank(gear, form["item_source"])
            advice_hash = stable_advice_hash(advise_gear(gear, item_source=form["item_source"], gear_source=form["gear_source"]))
        except (TypeError, ValueError) as error:
            errors.append(f"gear_validation_failed:{error}")
            gear_data = None
    ocr_gear = gear_data
    projection = None
    if not errors and reference_gear is not None:
        try:
            gear_data = project_shadow_gear(ocr_gear, reference_gear)
            projected_gear = Gear.from_dict(gear_data)
            advice_hash = stable_advice_hash(
                advise_gear(
                    projected_gear,
                    item_source=str(source.get("itemSource") or "normal_85"),
                    gear_source=str(source.get("gearSource") or DEFAULT_GEAR_SOURCE),
                )
            )
            projection = {"status": "passed", "source": "same_batch_unique_reference"}
        except (TypeError, ValueError) as error:
            errors.append(f"shadow_projection_failed:{error}")
            gear_data = None
            projection = {"status": "rejected", "source": "same_batch_unique_reference", "reason": str(error)}
    return {
        "schema_version": OCR_RESULT_SCHEMA_VERSION, "mode": "read_only_shadow", "capture": dict(capture),
        "regions": dict(regions or {}), "fields": fields, "ocr_gear": ocr_gear,
        "gear": gear_data, "shadow_projection": projection, "advice_hash": advice_hash,
        "accepted": not errors, "rejection_reasons": errors,
        "ocr_elapsed_ms": round((perf_counter() - started) * 1000, 3),
        "retries": max(0, int(payload.get("retries", 0) or 0)), "click_performed": False,
    }


def compare_shadow_advice(result: dict, reference_gear: dict) -> dict:
    if not result.get("accepted") or not isinstance(result.get("gear"), dict):
        return {"comparable": False, "matched": False, "reason": "ocr_result_rejected"}
    item_source = str(reference_gear.get("itemSource") or "normal_85")
    gear_source = str(reference_gear.get("gearSource") or DEFAULT_GEAR_SOURCE)
    reference_hash = stable_advice_hash(advise_gear(Gear.from_dict(reference_gear), item_source=item_source, gear_source=gear_source))
    return {"comparable": True, "matched": result.get("advice_hash") == reference_hash, "ocr_advice_hash": result.get("advice_hash"), "reference_advice_hash": reference_hash}
