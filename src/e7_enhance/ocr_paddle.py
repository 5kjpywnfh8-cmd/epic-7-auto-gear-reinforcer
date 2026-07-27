"""Read-only PaddleOCR adapter for the backpack enhancement page."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any

from .rules import SET_ALIASES, SET_DISPLAY_NAMES

OCR_PADDLE_SCHEMA_VERSION = 1
# The equipment fields live in the selected item's right-hand detail panel,
# not in the left-hand backpack grid.  These are normalized candidate bounds
# from the supplied layout reference and require a future read-only frame
# calibration before they can be treated as a confirmed production layout.
BACKPACK_DETAIL_PANEL = {
    "left": 0.60,
    "top": 0.0805555556,
    "right": 0.9703125,
    "bottom": 0.86,
}
BACKPACK_DETAIL_SET_NAME = {
    "left": 0.63984375,
    "top": 0.76,
    "right": 0.95,
    "bottom": 0.86,
}
BACKPACK_DETAIL_SET_TEXT = {
    "left": 0.715625,
    "top": 0.75,
    "right": 0.875,
    "bottom": 0.8333333333,
}
BACKPACK_DETAIL_ENHANCE_EVIDENCE = {
    "left": 0.63984375,
    "top": 0.16,
    "right": 0.95,
    "bottom": 0.25,
}

# Preserve the previous public constants and helper call sites while making
# their values point at the corrected detail-panel layout.
BACKPACK_ENHANCE_PANEL = BACKPACK_DETAIL_PANEL
BACKPACK_SET_NAME = BACKPACK_DETAIL_SET_NAME
BACKPACK_SET_TEXT = BACKPACK_DETAIL_SET_TEXT


class PaddleOcrError(RuntimeError):
    pass


_STAT_LABELS = {
    "生命值": "Health",
    "防御力": "Defense",
    "攻击力": "Attack",
    "暴击率": "CriticalHitChancePercent",
    "暴击伤害": "CriticalHitDamagePercent",
    "效果命中": "EffectivenessPercent",
    "效果抗性": "EffectResistancePercent",
    "速度": "Speed",
}
_RANKS = {"传说": "Epic", "英雄": "Heroic", "稀有": "Rare", "高级": "Good", "普通": "Normal"}
_SLOTS = {"武器": "Weapon", "头盔": "Helmet", "衣服": "Armor", "项链": "Necklace", "戒指": "Ring", "鞋子": "Boots"}
_ENHANCE_TOKEN = re.compile(r"\+([0-9]+)")
_EXPERIENCE_TOKEN = re.compile(r"exp([0-9]+)/[0-9]+", re.IGNORECASE)
_ENHANCE_REGION = "enhance"
_SET_TEXT_REGION = "set_text"
_LEGACY_SET_REGIONS = frozenset(("set_name", "set_anchor", "set"))
_PADDLE_MODEL_LAYOUT = {
    "det_model_dir": ("userprofile", ".paddleocr", "whl", "det", "ch", "ch_PP-OCRv4_det_infer"),
    "rec_model_dir": ("userprofile", ".paddleocr", "whl", "rec", "ch", "ch_PP-OCRv4_rec_infer"),
    "cls_model_dir": ("userprofile", ".paddleocr", "whl", "cls", "ch_ppocr_mobile_v2.0_cls_infer"),
}
_PADDLE_REQUIRED_MODEL_FILES = ("inference.pdmodel", "inference.pdiparams")
def _clean_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).replace("（", "(").replace("）", ")")


def _parse_number(value: object) -> float | None:
    match = re.fullmatch(r"[+]?([0-9]+(?:\.[0-9]+)?)%?", _clean_text(value).replace(",", ""))
    return float(match.group(1)) if match else None


def _field(text: str, confidence: float) -> dict[str, Any]:
    # Keep both names: ``text`` is the OCR adapter contract, while
    # ``raw_text`` is retained for the existing audit/report schema.
    return {"text": text, "raw_text": text, "confidence": confidence, "accepted": confidence >= 0.98}


def _field_from_line(text: str, confidence: float, line: dict[str, Any]) -> dict[str, Any]:
    field = _field(text, confidence)
    if "local_retry" in line:
        field["local_retry"] = dict(line["local_retry"])
    return field


def _set_display_name(value: str) -> str | None:
    name = re.sub(r"(?:套装|套)$", "", value)
    set_code = SET_ALIASES.get(name)
    return SET_DISPLAY_NAMES.get(set_code) if set_code else None


def _apply_local_retries(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use a local OCR retry only when it confirms the same stat token."""
    selected = [dict(line) for line in lines if "retry_for" not in line]
    for retry in lines:
        target = retry.get("retry_for")
        if not isinstance(target, int) or not 0 <= target < len(selected):
            continue
        original = selected[target]
        if (
            _clean_text(retry.get("text")) == _clean_text(original.get("text"))
            and float(retry.get("confidence", 0) or 0) >= 0.98
            and float(retry.get("confidence", 0) or 0) > float(original.get("confidence", 0) or 0)
        ):
            selected[target] = {
                **original,
                "confidence": float(retry["confidence"]),
                "local_retry": {
                    "text": str(retry.get("text") or ""),
                    "confidence": float(retry["confidence"]),
                },
            }
    return selected


def _enhance_evidence(lines: list[dict[str, Any]], normalized: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    """Accept one explicit enhancement-local token, never inferred page context."""
    direct = [
        (index, int(match.group(1)))
        for index, text in enumerate(normalized)
        if lines[index].get("region") == _ENHANCE_REGION and (match := _ENHANCE_TOKEN.fullmatch(text))
    ]
    experience = [
        (index, int(match.group(1)))
        for index, text in enumerate(normalized)
        if lines[index].get("region") == _ENHANCE_REGION and (match := _EXPERIENCE_TOKEN.fullmatch(text))
    ]
    if len(direct) > 1 or len(experience) > 1:
        return None, "conflicting:enhance_evidence"
    if direct:
        index, value = direct[0]
        return (
            _field(normalized[index], float(lines[index].get("confidence", 0) or 0))
            | {"normalized": value, "source": "enhance_local"},
            None,
        )
    if experience and experience[0][1] == 0:
        index = experience[0][0]
        return (
            _field(normalized[index], float(lines[index].get("confidence", 0) or 0))
            | {"normalized": 0, "source": "enhance_local_experience_bar"},
            None,
        )
    if experience:
        return None, "unrecognized:enhance_from_experience_bar"
    return None, "missing:enhance"


def parse_backpack_enhance_lines(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse only stable labels from OCR lines; missing fields reject closed."""
    lines = _apply_local_retries(lines)
    normalized = [_clean_text(line.get("text")) for line in lines]
    confidences = [float(line.get("confidence", 0) or 0) for line in lines]
    errors: list[str] = []
    fields: dict[str, Any] = {}

    title_index = next((index for index, text in enumerate(normalized) if any(text.startswith(rank) for rank in _RANKS)), None)
    if title_index is None:
        errors.append("unrecognized:rank_slot")
    else:
        title = normalized[title_index]
        rank = next((value for key, value in _RANKS.items() if title.startswith(key)), None)
        slot = next((value for key, value in _SLOTS.items() if title.endswith(key)), None)
        if rank is None or slot is None:
            errors.append("unrecognized:rank_slot")
        else:
            fields["rank"] = _field(title, confidences[title_index]) | {"normalized": rank}
            fields["slot"] = _field(title, confidences[title_index]) | {"normalized": slot}

    level_index = next((index for index, text in enumerate(normalized) if text == "85"), None)
    if level_index is None:
        errors.append("unrecognized:level")
    else:
        fields["level"] = _field(normalized[level_index], confidences[level_index]) | {"normalized": 85}

    set_candidates = [index for index, text in enumerate(normalized) if "套装" in text]
    local_set_candidates = [
        index for index in set_candidates
        if lines[index].get("region") == _SET_TEXT_REGION or lines[index].get("region") in _LEGACY_SET_REGIONS
    ]
    if local_set_candidates:
        set_candidates = local_set_candidates
    elif any("region" in lines[index] for index in set_candidates):
        # A supplied local OCR crop must be one of the approved set crops.
        # Do not fall back to a broad panel line when that evidence is absent.
        set_candidates = []
    set_values = {
        value for index in set_candidates
        if (value := _set_display_name(re.sub(r"\(\d+/\d+\)$", "", normalized[index]))) is not None
    }
    set_index = max(set_candidates, key=lambda index: confidences[index]) if set_candidates else None
    if len(set_values) > 1:
        errors.append("conflicting:set")
    elif set_index is None:
        errors.append("unrecognized:set")
    else:
        set_text = re.sub(r"\(\d+/\d+\)$", "", normalized[set_index])
        set_value = _set_display_name(set_text)
        if set_value is None:
            errors.append("unrecognized:set")
        else:
            region = lines[set_index].get("region")
            source = (
                "set_text_local" if region == _SET_TEXT_REGION
                else "set_text_legacy_region" if region in _LEGACY_SET_REGIONS
                else "set_text_legacy_unscoped"
            )
            fields["set"] = _field(normalized[set_index], confidences[set_index]) | {
                "normalized": set_value,
                "source": source,
            }

    enhance, enhance_error = _enhance_evidence(lines, normalized)
    if enhance is None:
        errors.append(str(enhance_error))
    else:
        fields["enhance"] = enhance

    score_index = next((index for index, text in enumerate(normalized) if text == "装备分数"), None)
    stat_start = next((index for index, text in enumerate(normalized) if text in _STAT_LABELS), None)
    if stat_start is None:
        errors.append("unrecognized:main_and_substats")
    else:
        stat_end = score_index if score_index is not None else len(normalized)
        pairs: list[tuple[str, float, str, str, float, float, dict[str, Any], dict[str, Any]]] = []
        index = stat_start
        while index + 1 < stat_end:
            label = normalized[index]
            value_text = normalized[index + 1]
            stat_type = _STAT_LABELS.get(label)
            value = _parse_number(value_text)
            if stat_type is not None and value is not None:
                if label in {"生命值", "防御力", "攻击力"} and value_text.endswith("%"):
                    stat_type = f"{stat_type}Percent"
                pairs.append((
                    stat_type,
                    value,
                    label,
                    value_text,
                    confidences[index],
                    min(confidences[index], confidences[index + 1]),
                    lines[index],
                    lines[index + 1],
                ))
                index += 2
            else:
                index += 1
        if not pairs:
            errors.append("unrecognized:main_and_substats")
        else:
            main_type, main_value, main_text, main_value_text, main_conf, main_pair_conf, main_line, main_value_line = pairs[0]
            fields["mainStat"] = {
                "type": _field_from_line(main_text, main_conf, main_line) | {"normalized": main_type},
                "value": _field_from_line(main_value_text, main_pair_conf, main_value_line) | {"normalized": main_value},
            }
            fields["substats"] = [
                {"type": _field_from_line(label_text, type_conf, label_line) | {"normalized": stat_type},
                 "value": _field_from_line(value_text, value_conf, value_line) | {"normalized": stat_value}}
                for stat_type, stat_value, label_text, value_text, type_conf, value_conf, label_line, value_line in pairs[1:]
            ]

    if score_index is None or score_index + 1 >= len(normalized) or _parse_number(normalized[score_index + 1]) is None:
        errors.append("unrecognized:gear_score")
    else:
        fields["gear_score"] = _field(normalized[score_index + 1], confidences[score_index + 1]) | {"normalized": int(_parse_number(normalized[score_index + 1]))}

    for name, value in fields.items():
        if name in {"rank", "slot", "set", "level", "enhance", "gear_score"} and not value.get("accepted", True):
            errors.append(f"low_confidence:{name}")
        if name == "mainStat":
            if not value["type"].get("accepted") or not value["value"].get("accepted"):
                errors.append("low_confidence:mainStat")
        if name == "substats":
            for index, stat in enumerate(value):
                if not stat["type"].get("accepted") or not stat["value"].get("accepted"):
                    errors.append(f"low_confidence:substats[{index}]")
    return {"fields": fields, "accepted": not errors, "rejection_reasons": sorted(set(errors))}


def _configure_cache(cache_root: Path) -> Path:
    cache_root = Path(cache_root).resolve()
    if not cache_root.is_dir() or not str(cache_root).isascii():
        raise PaddleOcrError("PaddleOCR cache path must be ASCII on Windows")
    user_profile = cache_root / "userprofile"
    if not user_profile.is_dir():
        raise PaddleOcrError("PaddleOCR cache user profile is missing")
    return user_profile


def _paddle_model_directories(cache_root: Path) -> dict[str, str]:
    """Return only audited local PaddleOCR model paths under one ASCII cache root."""
    root = Path(cache_root).resolve()
    _configure_cache(root)
    directories: dict[str, str] = {}
    for parameter, relative_path in _PADDLE_MODEL_LAYOUT.items():
        directory = root.joinpath(*relative_path).resolve()
        try:
            directory.relative_to(root)
        except ValueError as exc:
            raise PaddleOcrError("PaddleOCR model path escapes the approved cache root") from exc
        if not directory.is_dir() or not all((directory / name).is_file() for name in _PADDLE_REQUIRED_MODEL_FILES):
            raise PaddleOcrError(f"PaddleOCR cached model is missing:{parameter}")
        directories[parameter] = str(directory)
    return directories


def _paddle_engine_kwargs(cache_root: Path) -> dict[str, Any]:
    """Fix both engine version and all model directories to the approved cache."""
    return {
        "lang": "ch",
        "ocr_version": "PP-OCRv4",
        "use_angle_cls": False,
        "show_log": False,
        **_paddle_model_directories(cache_root),
    }


def _validate_detail_viewport(width: int, height: int) -> None:
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise PaddleOcrError("backpack detail viewport is invalid")
    # The calibrated detail layout is landscape 16:9.  A rotated or materially
    # drifted viewport would otherwise produce a plausible but wrong crop.
    if width <= height or abs((width / height) - (16 / 9)) > 0.02:
        raise PaddleOcrError("backpack detail viewport is not a supported landscape layout")


def _crop_bounds(width: int, height: int) -> tuple[int, int, int, int]:
    _validate_detail_viewport(width, height)
    left = round(width * BACKPACK_DETAIL_PANEL["left"])
    top = round(height * BACKPACK_DETAIL_PANEL["top"])
    right = round(width * BACKPACK_DETAIL_PANEL["right"])
    bottom = round(height * BACKPACK_DETAIL_PANEL["bottom"])
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise PaddleOcrError("backpack enhancement crop is outside image bounds")
    return left, top, right, bottom


def _set_bounds(width: int, height: int) -> tuple[int, int, int, int]:
    _validate_detail_viewport(width, height)
    left = round(width * BACKPACK_DETAIL_SET_NAME["left"])
    top = round(height * BACKPACK_DETAIL_SET_NAME["top"])
    right = round(width * BACKPACK_DETAIL_SET_NAME["right"])
    bottom = round(height * BACKPACK_DETAIL_SET_NAME["bottom"])
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise PaddleOcrError("backpack set-name crop is outside image bounds")
    return left, top, right, bottom


def _set_text_bounds(width: int, height: int) -> tuple[int, int, int, int]:
    _validate_detail_viewport(width, height)
    left = round(width * BACKPACK_DETAIL_SET_TEXT["left"])
    top = round(height * BACKPACK_DETAIL_SET_TEXT["top"])
    right = round(width * BACKPACK_DETAIL_SET_TEXT["right"])
    bottom = round(height * BACKPACK_DETAIL_SET_TEXT["bottom"])
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise PaddleOcrError("backpack set-text crop is outside image bounds")
    return left, top, right, bottom


def _enhance_bounds(width: int, height: int) -> tuple[int, int, int, int]:
    _validate_detail_viewport(width, height)
    left = round(width * BACKPACK_DETAIL_ENHANCE_EVIDENCE["left"])
    top = round(height * BACKPACK_DETAIL_ENHANCE_EVIDENCE["top"])
    right = round(width * BACKPACK_DETAIL_ENHANCE_EVIDENCE["right"])
    bottom = round(height * BACKPACK_DETAIL_ENHANCE_EVIDENCE["bottom"])
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise PaddleOcrError("backpack enhance-evidence crop is outside image bounds")
    return left, top, right, bottom


def _local_stat_retry(
    engine: Any,
    image: Any,
    box: object,
    *,
    np: Any,
    Image: Any,
    ImageEnhance: Any,
) -> tuple[str, float] | None:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        points = [(float(point[0]), float(point[1])) for point in box]
    except (IndexError, TypeError, ValueError):
        return None
    left = max(0, int(min(point[0] for point in points)) - 8)
    top = max(0, int(min(point[1] for point in points)) - 8)
    right = min(image.width, int(max(point[0] for point in points)) + 8)
    bottom = min(image.height, int(max(point[1] for point in points)) + 8)
    if left >= right or top >= bottom:
        return None
    retry = image.crop((left, top, right, bottom)).resize(
        (max(1, (right - left) * 4), max(1, (bottom - top) * 4)),
        Image.Resampling.LANCZOS,
    )
    retry = ImageEnhance.Contrast(retry).enhance(1.25)
    rows = engine.ocr(np.asarray(retry), cls=False)[0] or []
    candidates = [
        (str(row[1][0]), float(row[1][1]))
        for row in rows
        if isinstance(row, (list, tuple)) and len(row) == 2
        and isinstance(row[1], (list, tuple)) and len(row[1]) == 2
    ]
    return max(candidates, key=lambda item: item[1]) if candidates else None


def recognize_backpack_enhance(image_path: Path, *, cache_root: Path) -> dict[str, Any]:
    """Recognize text in a backpack enhancement screenshot without side effects."""
    image_path = Path(image_path)
    source_bytes = image_path.read_bytes()
    try:
        import numpy as np
        from PIL import Image, ImageEnhance
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise PaddleOcrError("PaddleOCR dependencies are not installed") from exc

    with Image.open(image_path) as source:
        source = source.convert("RGB")
        source_dimensions = source.size
        bounds = _crop_bounds(*source_dimensions)
        set_bounds = _set_bounds(*source_dimensions)
        set_text_bounds = _set_text_bounds(*source_dimensions)
        enhance_bounds = _enhance_bounds(*source_dimensions)
        try:
            engine = PaddleOCR(**_paddle_engine_kwargs(Path(cache_root)))
        except PaddleOcrError:
            raise
        except Exception as exc:
            raise PaddleOcrError("PaddleOCR engine initialization failed") from exc
        result_lines = []
        crop = source.crop(bounds).resize(
            (max(1, (bounds[2] - bounds[0]) * 2), max(1, (bounds[3] - bounds[1]) * 2)),
            Image.Resampling.LANCZOS,
        )
        crop = ImageEnhance.Contrast(crop).enhance(1.15)
        detail_result = engine.ocr(np.asarray(crop), cls=False)[0] or []
        result_lines.append(("right_detail_panel", crop.size, detail_result))
        set_crop = source.crop(set_text_bounds).resize(
            (max(1, (set_text_bounds[2] - set_text_bounds[0]) * 6), max(1, (set_text_bounds[3] - set_text_bounds[1]) * 6)),
            Image.Resampling.LANCZOS,
        )
        set_crop = ImageEnhance.Contrast(set_crop).enhance(1.15)
        result_lines.append((_SET_TEXT_REGION, set_crop.size, engine.ocr(np.asarray(set_crop), cls=False)[0] or []))
        enhance_crop = source.crop(enhance_bounds).resize(
            (max(1, (enhance_bounds[2] - enhance_bounds[0]) * 6), max(1, (enhance_bounds[3] - enhance_bounds[1]) * 6)),
            Image.Resampling.LANCZOS,
        )
        enhance_crop = ImageEnhance.Contrast(enhance_crop).enhance(1.15)
        result_lines.append((_ENHANCE_REGION, enhance_crop.size, engine.ocr(np.asarray(enhance_crop), cls=False)[0] or []))

    lines = []
    for region, crop_size, result in result_lines:
        for row in result:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                continue
            box, text_score = row
            if not isinstance(text_score, (list, tuple)) or len(text_score) != 2:
                continue
            lines.append({
                "region": region,
                "crop_size": {"width": crop_size[0], "height": crop_size[1]},
                "box": box,
                "text": str(text_score[0]),
                "confidence": round(float(text_score[1]), 6),
            })
    # Retry only low-confidence substat labels and numbers from their own crop.
    # The parser accepts a retry only when it confirms the original token and
    # independently clears the unchanged global confidence threshold.
    for index, line in enumerate(list(lines)):
        if line["region"] != "right_detail_panel" or line["confidence"] >= 0.98:
            continue
        if _clean_text(line["text"]) not in _STAT_LABELS and _parse_number(line["text"]) is None:
            continue
        retry = _local_stat_retry(
            engine, crop, line["box"], np=np, Image=Image, ImageEnhance=ImageEnhance,
        )
        if retry is not None:
            text, confidence = retry
            lines.append({
                "region": "substat_local_retry",
                "text": text,
                "confidence": round(confidence, 6),
                "retry_for": index,
            })
    parsed = parse_backpack_enhance_lines(lines)
    return {
        "schema_version": OCR_PADDLE_SCHEMA_VERSION,
        "mode": "read_only_raw_text",
        "engine": "paddleocr",
        "engine_version": "2.10.0",
        "model_language": "ch",
        "source_path": str(image_path),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_size": len(source_bytes),
        "source_dimensions": {"width": source_dimensions[0], "height": source_dimensions[1]},
        "crop_bounds": {"left": bounds[0], "top": bounds[1], "right": bounds[2], "bottom": bounds[3]},
        "set_bounds": {
            "left": set_bounds[0], "top": set_bounds[1],
            "right": set_bounds[2], "bottom": set_bounds[3],
        },
        "set_text_bounds": {
            "left": set_text_bounds[0], "top": set_text_bounds[1],
            "right": set_text_bounds[2], "bottom": set_text_bounds[3],
        },
        "enhance_bounds": {"left": enhance_bounds[0], "top": enhance_bounds[1], "right": enhance_bounds[2], "bottom": enhance_bounds[3]},
        "experience_context": "enhance_local_crop",
        "lines": lines,
        "parsed": parsed,
        "click_performed": False,
    }
