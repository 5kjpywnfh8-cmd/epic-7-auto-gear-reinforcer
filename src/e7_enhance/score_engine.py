from __future__ import annotations

from dataclasses import dataclass

from .models import Gear, Stat, normalize_stat_value, round1
from .rules import (
    CATEGORY_RULES,
    FORMULAS,
    OFFICIAL_SCORE_WEIGHTS,
    RATING_LABELS,
    SET_GROUPS,
    SLOT_LABELS,
    STAT_KEY_LABELS,
    VALID_STATS,
)


@dataclass(frozen=True)
class Retention:
    category: str
    score: float
    priority: int
    basis: str
    formula: str
    valid_keys: list[str]
    effective_score: float
    source_row: str = ""
    baili_tier: int = 0
    rule_matched: bool = True
    gate_reason: str = ""


@dataclass(frozen=True)
class Evaluation:
    gear: Gear
    official_score: float
    official_parts: dict[str, float]
    sub_official_score: float
    retention: Retention
    valid_profile_category: str
    valid_profile_keys: list[str]
    valid_profile_effective_score: float
    valid_profile_count: int
    rating_level: int
    rating_label: str
    valid_substats: list[str]
    invalid_substats: list[str]
    fit_status: str
    target_score: float
    target_score_source_row: str
    target_score_formula: str

    @property
    def effective_score(self) -> float:
        return self.valid_profile_effective_score

    @property
    def baili_score(self) -> float:
        return self.retention.score

    @property
    def target_profile(self) -> str:
        if self.retention.rule_matched:
            return self.retention.category
        if self.rating_level >= 4 and self.valid_profile_category != "无":
            return f"有效分保留：{self.valid_profile_category}"
        return self.retention.category


def evaluate_gear(gear: Gear) -> Evaluation:
    official_parts = official_score_parts(gear)
    official = round1(sum(official_parts.values()))
    sub_official = official_score_for_stats(gear.substats)
    retention = evaluate_retention(gear, official, sub_official)
    valid_profile = evaluate_valid_profile(gear, retention)
    level, label = rating_for(retention.score, retention.category, official, sub_official, speed_value(gear), retention.rule_matched, valid_profile["effective_score"], retention.baili_tier)
    valid_keys = set(valid_profile["valid_keys"])
    valid = [format_stat(stat) for stat in gear.substats if stat.key in valid_keys]
    invalid = [format_stat(stat) for stat in gear.substats if stat.key not in valid_keys]
    fit = fit_for(retention, len(invalid), len(valid))
    return Evaluation(
        gear=gear,
        official_score=official,
        official_parts=official_parts,
        sub_official_score=sub_official,
        retention=retention,
        valid_profile_category=valid_profile["category"],
        valid_profile_keys=valid_profile["valid_keys"],
        valid_profile_effective_score=valid_profile["effective_score"],
        valid_profile_count=valid_profile["valid_count"],
        rating_level=level,
        rating_label=label,
        valid_substats=valid,
        invalid_substats=invalid,
        fit_status=fit,
        target_score=retention.score,
        target_score_source_row=retention.source_row,
        target_score_formula=retention.formula,
    )


def official_score_parts(gear: Gear) -> dict[str, float]:
    substats = official_score_for_stats(gear.substats)
    return {
        "initial": 5.0 if gear.rank == "Epic" and gear.level >= 85 else 4.0,
        "enhance": round1((21 if 88 <= gear.level < 90 else 19) * gear.enhance / 15),
        "reforge_main": 2.0 if is_reforged_gear(gear) else 0.0,
        "substats": substats,
    }


def official_score_for_stats(substats: list[Stat], allowed_keys: set[str] | list[str] | None = None) -> float:
    allowed = set(allowed_keys) if allowed_keys else None
    total = 0.0
    for stat in substats:
        key = stat.key
        if allowed is not None and key not in allowed:
            continue
        total += normalize_stat_value(key, stat.value) * OFFICIAL_SCORE_WEIGHTS.get(key, 0)
    return round1(total)


def evaluate_valid_profile(gear: Gear, retention: Retention) -> dict:
    candidates: list[dict] = []
    speed = speed_value(gear)
    if gear.slot != "boot" and speed >= 22:
        candidates.append(valid_profile_result("一速", 1, ["spd"], official_score_for_stats(gear.substats, {"spd"}), sum(1 for stat in gear.substats if stat.key == "spd")))
    if gear.slot != "boot" and (gear.set == "set_speed" or gear.set in SET_GROUPS["speedNonSpeed"]) and speed >= 18:
        support = category_support_for_speed(gear)
        if support["valid_count"] > 0:
            candidates.append(valid_profile_result(support["category"] or "速度支撑", 2, support["valid_keys"], support["effective_score"], support["valid_count"]))
    for rule in CATEGORY_RULES:
        match = valid_rule_profile(gear, rule)
        if match:
            candidates.append(match)
    if not candidates and retention.rule_matched:
        return valid_profile_result(retention.category, retention.priority, retention.valid_keys, retention.effective_score, len(retention.valid_keys))
    if not candidates:
        return valid_profile_result("无", 99, [], 0, 0)
    candidates.sort(key=lambda item: (-item["valid_count"], -item["effective_score"], item["priority"]))
    return candidates[0]


def valid_rule_profile(gear: Gear, rule: dict) -> dict | None:
    match = rule_match_info(gear, rule)
    if not match["matched"]:
        return None
    valid_keys = match["valid_keys"]
    return valid_profile_result(
        rule["category"],
        rule["priority"],
        list(valid_keys),
        official_score_for_stats(gear.substats, valid_keys),
        sum(1 for stat in gear.substats if stat.key in valid_keys),
    )


def valid_profile_result(category: str, priority: int, valid_keys: list[str], effective_score: float, valid_count: int) -> dict:
    return {
        "category": category,
        "priority": priority,
        "valid_keys": valid_keys,
        "valid_count": valid_count,
        "effective_score": round1(effective_score),
    }


def is_reforged_gear(gear: Gear) -> bool:
    return gear.level >= 90 or gear.code.endswith("_u")


def evaluate_retention(gear: Gear, official: float, sub_official: float) -> Retention:
    speed = speed_value(gear)
    if gear.slot != "boot" and speed >= 22:
        return retention_result(
            "一速",
            score_one_speed(speed),
            1,
            f"速度 {format_number(speed)} / 速度有效分 {official_score_for_stats(gear.substats, {'spd'})}",
            "一速公式 (R2)",
            ["spd"],
            official_score_for_stats(gear.substats, {"spd"}),
            "R2",
            tier_one_speed(speed),
        )
    if gear.slot != "boot" and gear.set == "set_speed" and speed >= 18:
        support = category_support_for_speed(gear)
        score = score_speed_set(sub_official)
        if score is not None and support["valid_count"] > 0:
            return retention_result(
                "速度套纯速度",
                score,
                2,
                f"速度 {format_number(speed)} / 副属性装等 {sub_official} / 支撑体系 {support['category'] or '无'} {support['valid_count']} 条",
                "速度套公式 (R3)",
                support["valid_keys"] or ["spd"],
                support["effective_score"] or official_score_for_stats(gear.substats, {"spd"}),
                "R3",
                tier_speed_set(sub_official),
            )
    if gear.slot != "boot" and gear.set in SET_GROUPS["speedNonSpeed"] and speed >= 18:
        support = category_support_for_speed(gear)
        score = score_non_speed_speed(sub_official)
        if score is not None and support["valid_count"] > 0:
            return retention_result(
                "非速度套速度装",
                score,
                3,
                f"速度 {format_number(speed)} / 副属性装等 {sub_official} / 支撑体系 {support['category'] or '无'} {support['valid_count']} 条",
                "非速度套速度公式 (R4)",
                support["valid_keys"] or ["spd"],
                support["effective_score"] or official_score_for_stats(gear.substats, {"spd"}),
                "R4",
                tier_non_speed_speed(sub_official),
            )
    for rule in CATEGORY_RULES:
        matched = evaluate_rule(gear, official, rule)
        if matched:
            return matched
    if sub_official >= 75:
        return retention_result(
            "未来可期",
            (2 / 3) * (sub_official - 73.5),
            13,
            f"副属性装等 {sub_official}",
            "2/3*(副属性装等-73.5) (R61)",
            list(STAT_KEY_LABELS.keys()),
            sub_official,
            "R61",
            tier_future(sub_official),
        )
    return Retention(
        category="淘汰/提取",
        score=0,
        priority=99,
        basis=f"游戏官方分 {official}，未达到保留体系门槛",
        formula="未命中套装属性与装等计算表",
        valid_keys=[],
        effective_score=0,
        source_row="-",
        rule_matched=False,
    )


def evaluate_rule(gear: Gear, official: float, rule: dict) -> Retention | None:
    match_info = rule_match_info(gear, rule)
    if not match_info["matched"]:
        return None
    valid_keys = match_info["valid_keys"]
    effective = official_score_for_stats(gear.substats, valid_keys)
    match = score_by_formula(effective, FORMULAS.get(rule["formula"], {}).get(gear.slot) if FORMULAS.get(rule["formula"]) else None)
    if not match:
        return None
    valid_count = sum(1 for stat in gear.substats if stat.key in valid_keys)
    return retention_result(
        rule["category"],
        match["score"],
        rule["priority"],
        f"有效分 {effective} / 有效副属性 {valid_count} 条 / 游戏官方分 {official} / 主属性 {main_rule_summary(gear.slot, rule.get('main', {}))}",
        match["formula"],
        list(valid_keys),
        effective,
        rule["sourceRow"],
        match["tier"],
    )


def retention_result(category: str, score: float, priority: int, basis: str, formula: str, valid_keys: list[str], effective: float, source_row: str, tier: int) -> Retention:
    return Retention(
        category=category,
        score=round1(max(0, score)),
        priority=priority,
        basis=basis,
        formula=formula,
        valid_keys=valid_keys,
        effective_score=round1(effective),
        source_row=source_row,
        baili_tier=max(0, min(3, int(tier or 0))),
    )


def category_support_for_speed(gear: Gear) -> dict:
    best = {"category": "", "valid_count": 0, "valid_keys": [], "effective_score": 0.0}
    for rule in CATEGORY_RULES:
        match = rule_match_info(gear, rule, require_valid_substat=False)
        if not match["matched"]:
            continue
        valid_keys = match["valid_keys"]
        non_speed_count = sum(1 for stat in gear.substats if stat.key in valid_keys and stat.key != "spd")
        if non_speed_count <= 0:
            continue
        valid_count = sum(1 for stat in gear.substats if stat.key in valid_keys)
        effective = official_score_for_stats(gear.substats, valid_keys)
        if valid_count > best["valid_count"] or (valid_count == best["valid_count"] and effective > best["effective_score"]):
            best = {"category": rule["category"], "valid_count": valid_count, "valid_keys": list(valid_keys), "effective_score": effective}
    return best


def rule_match_info(gear: Gear, rule: dict, require_valid_substat: bool = True) -> dict:
    group = SET_GROUPS.get(rule["setGroup"], set())
    valid_keys = set(VALID_STATS.get(rule["validGroup"], []))
    if gear.set not in group:
        return {"matched": False, "valid_keys": valid_keys}
    if require_valid_substat and not any(stat.key in valid_keys for stat in gear.substats):
        return {"matched": False, "valid_keys": valid_keys}
    all_keys = {stat.key for stat in gear.substats}
    all_keys.add(gear.main_stat.key)
    if not category_gate(rule["category"], all_keys):
        return {"matched": False, "valid_keys": valid_keys}
    if rule.get("requiredAny") and not any(key in all_keys for key in rule["requiredAny"]):
        return {"matched": False, "valid_keys": valid_keys}
    if rule.get("noAtkPctWithEffRes") and "atkPct" in all_keys and any(key in all_keys for key in ("eff", "res")):
        return {"matched": False, "valid_keys": valid_keys}
    if not main_allowed(gear.slot, gear.main_stat.key, rule.get("main", {})):
        return {"matched": False, "valid_keys": valid_keys}
    return {"matched": True, "valid_keys": valid_keys}


def full_category_matches(gear: Gear) -> list[dict]:
    """Return every formal category whose full current substat set is coherent.

    This deliberately does not change official retention scoring. It is an
    early-embryo diagnostic used by the lightweight prediction layer.
    """
    return [item for item in full_category_diagnostics(gear) if item["full_matched"]]


def full_category_diagnostics(gear: Gear) -> list[dict]:
    """Explain every formal category check for early-embryo inspection.

    ``full_category_matches`` intentionally returns only coherent matches for
    callers.  The separate diagnostic list preserves failed set/main/gate and
    per-substat checks so the GUI can explain why a direction was not chosen.
    """
    diagnostics = []
    substat_keys = [stat.key for stat in gear.substats]
    all_keys = set(substat_keys)
    all_keys.add(gear.main_stat.key)
    for rule in CATEGORY_RULES:
        valid_keys = set(VALID_STATS.get(rule["validGroup"], []))
        set_matched = gear.set in SET_GROUPS.get(rule["setGroup"], set())
        has_valid_substat = any(key in valid_keys for key in substat_keys)
        gate_matched = category_gate(rule["category"], all_keys)
        required_any_matched = not rule.get("requiredAny") or any(key in all_keys for key in rule["requiredAny"])
        mutual_exclusion_matched = not rule.get("noAtkPctWithEffRes") or not (
            "atkPct" in all_keys and any(key in all_keys for key in ("eff", "res"))
        )
        main_matched = main_allowed(gear.slot, gear.main_stat.key, rule.get("main", {}))
        special_matched = gate_matched and required_any_matched and mutual_exclusion_matched
        substat_results = [
            {"stat": STAT_KEY_LABELS.get(key, key), "key": key, "matched": key in valid_keys}
            for key in substat_keys
        ]
        full = bool(set_matched and has_valid_substat and main_matched and special_matched and substat_keys and all(item["matched"] for item in substat_results))
        diagnostics.append(
            {
                "category": rule["category"],
                "priority": rule["priority"],
                "valid_keys": sorted(valid_keys),
                "set_group": rule["setGroup"],
                "source_row": rule["sourceRow"],
                "substats": substat_results,
                "set_matched": set_matched,
                "has_valid_substat": has_valid_substat,
                "main_matched": main_matched,
                "special_matched": special_matched,
                "category_gate_matched": gate_matched,
                "required_any_matched": required_any_matched,
                "mutual_exclusion_matched": mutual_exclusion_matched,
                "full_matched": full,
            }
        )
    return diagnostics


def category_gate(category: str, all_keys: set[str]) -> bool:
    if category == "抗坦":
        return "res" in all_keys
    if category == "命坦":
        return "eff" in all_keys
    if category == "纯肉":
        return "eff" not in all_keys and "res" not in all_keys
    if category == "输出":
        return "crit" in all_keys
    if category == "输出(必爆)":
        return "crit" not in all_keys
    return True


def speed_value(gear: Gear) -> float:
    return sum(stat.normalized_value for stat in gear.substats if stat.key == "spd")


def score_one_speed(speed: float) -> float:
    if speed >= 27:
        return 20 * speed - 490
    if speed >= 25:
        return 10 * speed - 225
    return 5 * speed - 105


def tier_one_speed(speed: float) -> int:
    if speed >= 27:
        return 3
    if speed >= 25:
        return 2
    return 1


def score_speed_set(gs: float) -> float | None:
    if gs >= 78:
        return 4 * gs - 285
    if gs >= 73:
        return 3 * gs - 207
    if gs >= 68:
        return 2 * gs - 134
    return None


def tier_speed_set(gs: float) -> int:
    if gs >= 78:
        return 3
    if gs >= 73:
        return 2
    if gs >= 68:
        return 1
    return 0


def score_non_speed_speed(gs: float) -> float | None:
    if gs >= 75:
        return gs - 69
    if gs >= 70:
        return 0.8 * (gs - 67.5)
    return None


def tier_non_speed_speed(gs: float) -> int:
    if gs >= 75:
        return 2
    if gs >= 70:
        return 1
    return 0


def tier_future(gs: float) -> int:
    if gs >= 95:
        return 3
    if gs >= 85:
        return 2
    if gs >= 75:
        return 1
    return 0


def score_by_formula(gs: float, formulas: list[tuple[float, float, float]] | None) -> dict | None:
    if not formulas:
        return None
    for index, formula in enumerate(formulas):
        threshold, multiplier, offset = formula[:3]
        label = formula[3] if len(formula) > 3 else f"{format_number(multiplier)}*装等{format_number(offset)}"
        if gs >= threshold:
            return {"score": multiplier * gs + offset, "tier": max(1, len(formulas) - index), "formula": label}
    return None


def main_allowed(slot: str, main_key: str, rules: dict) -> bool:
    allowed = rules.get(slot)
    return True if not allowed else main_key in allowed


def main_rule_summary(slot: str, rules: dict) -> str:
    allowed = rules.get(slot)
    if not allowed:
        return "不限"
    return "/".join(STAT_KEY_LABELS.get(key, key) for key in allowed)


def rating_for(score: float, category: str, official: float, sub_official: float, speed: float, matched_baili: bool, effective: float, baili_tier: int) -> tuple[int, str]:
    level = 1
    if matched_baili:
        tier = max(1, min(3, int(baili_tier or 1)))
        level = 8 if tier >= 3 else 7 if tier >= 2 else 6
    else:
        # High tiers require a verified formal category; fallback scoring only retains candidates.
        if score >= 15 or effective >= 60:
            level = 5
        elif score >= 8 or effective >= 48:
            level = 4
        elif score > 0 or effective >= 34 or category == "未来可期":
            level = 3
        elif official >= 60 or speed >= 14 or effective >= 20:
            level = 2
    return level, RATING_LABELS[level]


def fit_for(retention: Retention, invalid_count: int, valid_count: int) -> str:
    if retention.gate_reason:
        return "有效但未入体系"
    if not retention.rule_matched and valid_count > 0:
        return "有效但未入体系"
    if not retention.rule_matched:
        return "未命中体系"
    if invalid_count > 0:
        return f"有无效副属性 {invalid_count}"
    return "主副契合"


def format_stat(stat: Stat) -> str:
    label = STAT_KEY_LABELS.get(stat.key, stat.type)
    suffix = "%" if stat.key in {"atkPct", "defPct", "hpPct", "crit", "cdmg", "eff", "res"} else ""
    return f"{label} {format_number(stat.normalized_value)}{suffix}"


def format_number(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(round1(number))
