from __future__ import annotations

import re
from pathlib import Path

TARGET_SCORE_TABLE_PATH = Path(__file__).resolve().parents[2] / "套装属性与装等计算表.md"

OFFICIAL_SCORE_WEIGHTS = {
    "atkFlat": 3.46 / 39,
    "atkPct": 1,
    "defFlat": 4.99 / 31,
    "defPct": 1,
    "hpFlat": 3.09 / 174,
    "hpPct": 1,
    "spd": 2,
    "crit": 1.6,
    "cdmg": 8 / 7,
    "eff": 1,
    "res": 1,
}

PERCENT_STAT_KEYS = {"atkPct", "defPct", "hpPct", "crit", "cdmg", "eff", "res"}

STAT_TYPE_TO_KEY = {
    "Attack": "atkFlat",
    "att": "atkFlat",
    "AttackFlat": "atkFlat",
    "AttackPercent": "atkPct",
    "Attack%": "atkPct",
    "Attack %": "atkPct",
    "att_rate": "atkPct",
    "Defense": "defFlat",
    "def": "defFlat",
    "DefenseFlat": "defFlat",
    "DefensePercent": "defPct",
    "Defense%": "defPct",
    "Defense %": "defPct",
    "def_rate": "defPct",
    "Health": "hpFlat",
    "Hp": "hpFlat",
    "HP": "hpFlat",
    "HealthFlat": "hpFlat",
    "HpFlat": "hpFlat",
    "HPFlat": "hpFlat",
    "max_hp": "hpFlat",
    "HealthPercent": "hpPct",
    "HpPercent": "hpPct",
    "HPPercent": "hpPct",
    "Health%": "hpPct",
    "HP%": "hpPct",
    "max_hp_rate": "hpPct",
    "Speed": "spd",
    "speed": "spd",
    "Spd": "spd",
    "CriticalHitChancePercent": "crit",
    "CritChance": "crit",
    "CriticalChance": "crit",
    "CritRate": "crit",
    "cri": "crit",
    "CriticalHitDamagePercent": "cdmg",
    "CritDamage": "cdmg",
    "CriticalDamage": "cdmg",
    "cri_dmg": "cdmg",
    "EffectivenessPercent": "eff",
    "Effectiveness": "eff",
    "acc": "eff",
    "EffectResistancePercent": "res",
    "EffectResistance": "res",
    "Effect Resistance": "res",
    "res": "res",
}

STAT_KEY_LABELS = {
    "atkFlat": "攻击",
    "atkPct": "攻击%",
    "defFlat": "防御",
    "defPct": "防御%",
    "hpFlat": "生命",
    "hpPct": "生命%",
    "spd": "速度",
    "crit": "暴率",
    "cdmg": "爆伤",
    "eff": "命中",
    "res": "抵抗",
}

SET_ALIASES = {
    "set_acc": "set_acc",
    "HitSet": "set_acc",
    "Hit": "set_acc",
    "命中": "set_acc",
    "效命": "set_acc",
    "set_att": "set_att",
    "AttackSet": "set_att",
    "Attack": "set_att",
    "攻击": "set_att",
    "set_counter": "set_counter",
    "CounterSet": "set_counter",
    "Counter": "set_counter",
    "反击": "set_counter",
    "set_cri_dmg": "set_cri_dmg",
    "DestructionSet": "set_cri_dmg",
    "Destruction": "set_cri_dmg",
    "爆伤": "set_cri_dmg",
    "set_cri": "set_cri",
    "CriticalSet": "set_cri",
    "Critical": "set_cri",
    "暴击": "set_cri",
    "set_def": "set_def",
    "DefenseSet": "set_def",
    "Defense": "set_def",
    "防御": "set_def",
    "防": "set_def",
    "set_immune": "set_immune",
    "ImmunitySet": "set_immune",
    "Immunity": "set_immune",
    "免疫": "set_immune",
    "set_max_hp": "set_max_hp",
    "HealthSet": "set_max_hp",
    "Health": "set_max_hp",
    "生命": "set_max_hp",
    "血": "set_max_hp",
    "set_penetrate": "set_penetrate",
    "PenetrationSet": "set_penetrate",
    "Penetration": "set_penetrate",
    "贯穿": "set_penetrate",
    "set_res": "set_res",
    "ResistSet": "set_res",
    "Resist": "set_res",
    "抵抗": "set_res",
    "效抗": "set_res",
    "set_speed": "set_speed",
    "SpeedSet": "set_speed",
    "Speed": "set_speed",
    "速度": "set_speed",
    "set_vampire": "set_vampire",
    "LifestealSet": "set_vampire",
    "Lifesteal": "set_vampire",
    "吸血": "set_vampire",
    "set_shield": "set_shield",
    "ProtectionSet": "set_shield",
    "Protection": "set_shield",
    "ShieldSet": "set_shield",
    "守护": "set_shield",
    "set_torrent": "set_torrent",
    "TorrentSet": "set_torrent",
    "Torrent": "set_torrent",
    "激流": "set_torrent",
    "set_scar": "set_scar",
    "InjurySet": "set_scar",
    "Injury": "set_scar",
    "伤口": "set_scar",
    "set_riposte": "set_riposte",
    "RiposteSet": "set_riposte",
    "Riposte": "set_riposte",
    "回击": "set_riposte",
    "set_opener": "set_opener",
    "OpenerSet": "set_opener",
    "Opener": "set_opener",
    "开战": "set_opener",
    "set_chase": "set_chase",
    "ChaseSet": "set_chase",
    "Chase": "set_chase",
    "追加": "set_chase",
    "set_rage": "set_rage",
    "RageSet": "set_rage",
    "Rage": "set_rage",
    "全力": "set_rage",
    "set_debuff": "set_debuff",
    "DebuffSet": "set_debuff",
    "Debuff": "set_debuff",
    "弱化": "set_debuff",
    "set_revenant": "set_revenant",
    "RevenantSet": "set_revenant",
    "ReversalSet": "set_revenant",
    "Revenant": "set_revenant",
    "逆袭": "set_revenant",
}

SET_CODE_TO_NAME = {
    "set_acc": "命中",
    "set_att": "攻击",
    "set_counter": "反击",
    "set_cri_dmg": "爆伤",
    "set_cri": "暴击",
    "set_def": "防御",
    "set_immune": "免疫",
    "set_max_hp": "生命",
    "set_penetrate": "贯穿",
    "set_res": "抵抗",
    "set_speed": "速度",
    "set_vampire": "吸血",
    "set_shield": "守护",
    "set_torrent": "激流",
    "set_scar": "伤口",
    "set_riposte": "回击",
    "set_opener": "开战",
    "set_chase": "追加",
    "set_rage": "全力",
    "set_debuff": "弱化",
    "set_revenant": "逆袭",
}

# OCR and import adapters use these established external names while all
# policy code continues to compare the canonical ``set_*`` code.
SET_DISPLAY_NAMES = {
    code: next(alias for alias, target in SET_ALIASES.items() if target == code and alias.endswith("Set"))
    for code in SET_CODE_TO_NAME
}

SLOT_ALIASES = {
    "weapon": "weapon",
    "Weapon": "weapon",
    "weapons": "weapon",
    "武器": "weapon",
    "helm": "helm",
    "helmet": "helm",
    "Helmet": "helm",
    "Head": "helm",
    "头盔": "helm",
    "armor": "armor",
    "Armor": "armor",
    "chest": "armor",
    "body": "armor",
    "衣服": "armor",
    "neck": "neck",
    "Necklace": "neck",
    "necklace": "neck",
    "项链": "neck",
    "ring": "ring",
    "Ring": "ring",
    "戒指": "ring",
    "boot": "boot",
    "Boots": "boot",
    "boots": "boot",
    "shoe": "boot",
    "鞋子": "boot",
}

SLOT_LABELS = {
    "weapon": "武器",
    "helm": "头盔",
    "armor": "衣服",
    "neck": "项链",
    "ring": "戒指",
    "boot": "鞋子",
}

RANK_ALIASES = {
    "Epic": "Epic",
    "传说": "Epic",
    "Heroic": "Heroic",
    "英雄": "Heroic",
    "Rare": "Rare",
    "稀有": "Rare",
    "Good": "Good",
    "高级": "Good",
    "Normal": "Normal",
    "普通": "Normal",
}

SET_GROUPS = {
    "speedNonSpeed": {"set_cri", "set_max_hp", "set_def", "set_immune", "set_penetrate", "set_torrent", "set_acc", "set_res"},
    "output": {"set_speed", "set_cri_dmg", "set_cri", "set_penetrate", "set_torrent", "set_counter", "set_vampire", "set_immune", "set_riposte", "set_opener"},
    "critless": {"set_speed", "set_cri_dmg", "set_penetrate", "set_torrent", "set_immune", "set_riposte"},
    "tankRes": {"set_speed", "set_max_hp", "set_def", "set_res", "set_shield", "set_counter", "set_immune", "set_revenant", "set_opener", "set_chase"},
    "pureTank": {"set_speed", "set_max_hp", "set_def", "set_shield", "set_immune", "set_revenant", "set_opener"},
    "hitTank": {"set_speed", "set_max_hp", "set_def", "set_acc", "set_immune", "set_chase"},
    "dual": {"set_speed", "set_max_hp", "set_def", "set_acc", "set_res", "set_counter", "set_immune"},
    "bruiserHpDef": {"set_max_hp", "set_def", "set_speed", "set_cri_dmg", "set_counter", "set_scar", "set_immune", "set_penetrate", "set_chase"},
    "bruiser": {"set_max_hp", "set_def", "set_speed", "set_cri", "set_cri_dmg", "set_counter", "set_scar", "set_vampire", "set_immune", "set_penetrate", "set_riposte"},
    "bruiserFlat": {"set_max_hp", "set_def", "set_speed", "set_counter", "set_immune", "set_opener", "set_chase"},
}

VALID_STATS = {
    "speedOnly": ["spd"],
    "output": ["atkPct", "atkFlat", "crit", "cdmg", "spd"],
    "critless": ["atkPct", "atkFlat", "cdmg", "spd"],
    "tankRes": ["hpPct", "hpFlat", "defPct", "defFlat", "spd", "res"],
    "pureTank": ["hpPct", "hpFlat", "defPct", "defFlat", "spd"],
    "hitTank": ["hpPct", "hpFlat", "defPct", "defFlat", "spd", "eff"],
    "dual": ["spd", "hpPct", "defPct", "defFlat", "res", "eff", "atkPct"],
    "bruiserHpDef": ["crit", "cdmg", "spd", "hpPct", "defPct", "defFlat"],
    "bruiser": ["atkPct", "crit", "cdmg", "spd", "hpPct", "defPct", "defFlat"],
    "bruiserFlat": ["atkPct", "atkFlat", "spd", "hpPct", "hpFlat", "defPct", "defFlat"],
}

FORMULAS = {
    "output": {
        "weapon": [(78, 3, -220), (75, 2, -142), (70, 1.4, -97)],
        "helm": [(78, 3, -220), (75, 2, -142), (70, 1.4, -97)],
        "armor": [(73, 3, -203), (69, 2, -130), (64, 1.4, -88.6)],
        "neck": [(74, 4, -280), (71, 2.5, -169), (66, 1.5, -98)],
        "ring": [(74, 4, -280), (71, 2.5, -169), (66, 1.5, -98)],
        "boot": [(74, 4, -277.5), (71, 2.5, -166.5), (65, 1.5, -95.5)],
    },
    "critless": {
        "weapon": [(72, 5, -340.5), (68, 2.5, -160.5), (63, 1.5, -92.5)],
        "helm": [(75, 5, -355.5), (71, 2.5, -168), (66, 1.5, -97)],
        "armor": None,
        "neck": [(66, 5, -310.5), (63, 3, -178.5), (59, 2, -115.5)],
        "ring": [(66, 5, -310.5), (63, 3, -178.5), (59, 2, -115.5)],
        "boot": [(66, 5, -310.5), (63, 3, -178.5), (59, 2, -115.5)],
    },
    "tankRes": {
        "weapon": [(74, 3, -204), (70, 2, -130), (64, 1.5, -95)],
        "helm": [(79, 3, -221), (76, 2, -142), (70, 1.5, -104)],
        "armor": [(79, 3, -221), (76, 2, -142), (70, 1.5, -104)],
        "neck": [(74, 3, -203), (70, 2, -129), (64, 1.5, -94)],
        "ring": [(74, 3, -203), (70, 2, -129), (64, 1.5, -94)],
        "boot": [(74, 3, -203), (70, 2, -129), (64, 1.5, -94)],
    },
    "pureTank": {
        "weapon": None,
        "helm": [(74, 3.5, -237), (68, 2, -126), (63, 1.8, -112.4)],
        "armor": [(74, 3.5, -237), (68, 2, -126), (63, 1.8, -112.4)],
        "neck": [(70, 5, -321), (64, 3, -181), (58, 1.5, -85)],
        "ring": [(68, 5, -319), (64, 2.5, -149), (58, 1.5, -85)],
        "boot": [(68, 5, -319), (64, 2.5, -149), (58, 1.5, -85)],
    },
    "dual": {
        "weapon": [(75, 2, -146), (72, 1, -71)],
        "helm": [(75, 2, -146), (72, 1, -71)],
        "armor": [(75, 2, -146), (72, 1, -71)],
        "neck": [(75, 2, -146), (72, 1, -71)],
        "ring": [(75, 2, -146), (72, 1, -71)],
        "boot": [(75, 2, -146), (72, 1, -71)],
    },
    "bruiserHpDef": {
        "weapon": [(77, 3, -221), (74, 2, -144), (71, 1, -70)],
        "helm": [(77, 3, -221), (74, 2, -144), (71, 1, -70)],
        "armor": [(77, 3, -221), (74, 2, -144), (71, 1, -70)],
        "neck": [(77, 4, -295), (74, 2, -141), (68, 1, -67)],
        "ring": [(77, 4, -295), (74, 2, -141), (68, 1, -67)],
        "boot": [(77, 4, -295), (74, 2, -141), (68, 1, -67)],
    },
    "bruiserFlat": {
        "weapon": [(74, 3, -204), (70, 2, -130), (65, 1.5, -95)],
        "helm": [(79, 3, -221), (76, 2, -142), (71, 1.5, -104)],
        "armor": [(74, 3, -204), (70, 2, -130), (65, 1.5, -95)],
        "neck": [(74, 4, -280), (71, 2.5, -169), (67, 1.5, -98)],
        "ring": [(74, 4, -280), (71, 2.5, -169), (67, 1.5, -98)],
        "boot": [(74, 4, -280), (71, 2.5, -169), (67, 1.5, -98)],
    },
}

CATEGORY_RULES = [
    {"category": "输出", "priority": 4, "setGroup": "output", "validGroup": "output", "formula": "output", "main": {"neck": ["crit", "cdmg"], "ring": ["atkPct"], "boot": ["spd", "atkPct"]}, "sourceRow": "R5-R10"},
    {"category": "输出(必爆)", "priority": 5, "setGroup": "critless", "validGroup": "critless", "formula": "critless", "main": {"neck": ["cdmg"], "ring": ["atkPct"], "boot": ["spd", "atkPct"]}, "sourceRow": "R11-R16"},
    {"category": "抗坦", "priority": 6, "setGroup": "tankRes", "validGroup": "tankRes", "formula": "tankRes", "main": {"neck": ["hpPct", "defPct"], "ring": ["hpPct", "defPct", "res"], "boot": ["hpPct", "defPct", "spd"]}, "sourceRow": "R17-R22"},
    {"category": "纯肉", "priority": 7, "setGroup": "pureTank", "validGroup": "pureTank", "formula": "pureTank", "main": {"neck": ["hpPct"], "ring": ["hpPct"], "boot": ["hpPct", "spd"]}, "sourceRow": "R23-R28"},
    {"category": "命坦", "priority": 8, "setGroup": "hitTank", "validGroup": "hitTank", "formula": "tankRes", "main": {"neck": ["hpPct", "defPct"], "ring": ["hpPct", "defPct", "eff"], "boot": ["spd"]}, "sourceRow": "R29-R34"},
    {"category": "双效", "priority": 9, "setGroup": "dual", "validGroup": "dual", "formula": "dual", "requiredAny": ["eff", "res"], "noAtkPctWithEffRes": True, "main": {"neck": ["hpPct", "defPct", "atkPct"], "ring": ["hpPct", "defPct", "atkPct", "res", "eff"], "boot": ["spd"]}, "sourceRow": "R35-R40"},
    {"category": "半肉(血防)", "priority": 10, "setGroup": "bruiserHpDef", "validGroup": "bruiserHpDef", "formula": "bruiserHpDef", "main": {"neck": ["crit", "cdmg"], "ring": ["hpPct", "defPct"], "boot": ["spd"]}, "sourceRow": "R41-R46"},
    {"category": "半肉(通用)", "priority": 11, "setGroup": "bruiser", "validGroup": "bruiser", "formula": "dual", "main": {"neck": ["crit", "cdmg"], "ring": ["hpPct", "defPct", "atkPct"], "boot": ["spd"]}, "sourceRow": "R47-R52"},
    {"category": "半肉(白字)", "priority": 12, "setGroup": "bruiserFlat", "validGroup": "bruiserFlat", "formula": "bruiserFlat", "main": {"neck": ["defPct", "hpPct", "atkPct"], "ring": ["hpPct", "defPct", "atkPct"], "boot": ["spd"]}, "sourceRow": "R53-R58"},
]

RATING_LABELS = {
    8: "8 神装",
    7: "7 极品",
    6: "6 优秀",
    5: "5 强保留",
    4: "4 可用",
    3: "3 观察",
    2: "2 提取",
    1: "1 淘汰",
}


def _load_target_score_rules_from_md() -> tuple[dict[str, set[str]], dict[str, list[str]], dict[str, dict], list[dict]]:
    rows = _read_markdown_table(TARGET_SCORE_TABLE_PATH)
    groups: dict[str, dict] = {}
    formulas: dict[str, dict] = {}
    set_groups: dict[str, set[str]] = {}
    valid_stats: dict[str, list[str]] = {}
    priority_by_type = {
        "输出": 4,
        "输出(必爆)": 5,
        "抗坦": 6,
        "纯肉": 7,
        "命坦": 8,
        "双效": 9,
        "半肉(血防)": 10,
        "半肉(通用)": 11,
        "半肉(白字)": 12,
    }
    key_by_type = {
        "输出": "output",
        "输出(必爆)": "critless",
        "抗坦": "tankRes",
        "纯肉": "pureTank",
        "命坦": "hitTank",
        "双效": "dual",
        "半肉(血防)": "bruiserHpDef",
        "半肉(通用)": "bruiser",
        "半肉(白字)": "bruiserFlat",
    }

    for row in rows:
        category = _category_from_table_type(row["类型/用途"])
        if category not in key_by_type:
            continue
        key = key_by_type[category]
        group = groups.setdefault(
            key,
            {
                "category": category,
                "priority": priority_by_type[category],
                "set_codes": set(),
                "valid_keys": set(),
                "main": {},
                "row_numbers": [],
                "requiredAny": ["eff", "res"] if category == "双效" else None,
                "noAtkPctWithEffRes": category == "双效",
            },
        )
        group["row_numbers"].append(int(row["原始行号"]))
        group["set_codes"].update(_parse_set_codes(row["套装"]))
        group["valid_keys"].update(_parse_stat_keys(row["有效属性"]))

        slot = SLOT_ALIASES.get(row["部位"], "")
        if slot:
            main = _parse_main_keys(row["主属性"])
            if main:
                group["main"][slot] = main
            slot_formulas = _parse_slot_formulas(row)
            formulas.setdefault(key, {})[slot] = slot_formulas

    rules = []
    for key, group in groups.items():
        row_numbers = sorted(group["row_numbers"])
        set_groups[key] = group["set_codes"]
        valid_stats[key] = sorted(group["valid_keys"])
        rule = {
            "category": group["category"],
            "priority": group["priority"],
            "setGroup": key,
            "validGroup": key,
            "formula": key,
            "main": group["main"],
            "sourceRow": f"R{row_numbers[0]}-R{row_numbers[-1]}",
            "loadedFrom": str(TARGET_SCORE_TABLE_PATH),
        }
        if group.get("requiredAny"):
            rule["requiredAny"] = group["requiredAny"]
        if group.get("noAtkPctWithEffRes"):
            rule["noAtkPctWithEffRes"] = True
        rules.append(rule)

    rules.sort(key=lambda item: item["priority"])
    return set_groups, valid_stats, formulas, rules


def _read_markdown_table(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    table_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    header = None
    rows = []
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        if cells[0] == "原始行号":
            header = cells
            continue
        if cells[0].startswith("---") or header is None or len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _category_from_table_type(value: str) -> str:
    raw = _clean_cell(value).replace("（", "(").replace("）", ")")
    return {
        "输出(必爆)": "输出(必爆)",
        "抗坦(坦克)": "抗坦",
        "纯肉(坦克)": "纯肉",
        "命坦(双效)": "命坦",
        "半肉(血防)": "半肉(血防)",
        "半肉(白字)": "半肉(白字)",
        "半肉": "半肉(通用)",
    }.get(raw, raw)


def _parse_set_codes(value: str) -> set[str]:
    cleaned = _clean_cell(value)
    if cleaned == "全部":
        return set(SET_CODE_TO_NAME)
    return {SET_ALIASES[token] for token in _tokens(cleaned) if token in SET_ALIASES}


def _parse_stat_keys(value: str) -> set[str]:
    first_line = _clean_cell(value).split("\n", 1)[0]
    if first_line == "全部":
        return set(STAT_KEY_LABELS)
    result = set()
    for token in _tokens(first_line):
        mapped = _stat_key_from_label(token)
        if mapped:
            result.add(mapped)
    return result


def _parse_main_keys(value: str) -> list[str]:
    cleaned = _clean_cell(value)
    if not cleaned or cleaned in {"-", "不给额外计算"} or cleaned.startswith("不单独计算"):
        return []
    result = []
    for token in _tokens(cleaned.split("\n", 1)[0]):
        mapped = _stat_key_from_label(token)
        if mapped:
            result.append(mapped)
    return result


def _parse_slot_formulas(row: dict[str, str]) -> list[tuple[float, float, float, str]] | None:
    formulas = []
    for index in (1, 2, 3):
        threshold = _parse_threshold(row.get(f"档位{index}装等", ""))
        formula = _parse_formula(row.get(f"档位{index}倍率", ""))
        if threshold is not None and formula is not None:
            multiplier, offset, label = formula
            formulas.append((threshold, multiplier, offset, label))
    formulas.sort(key=lambda item: item[0], reverse=True)
    return formulas or None


def _parse_threshold(value: str) -> float | None:
    cleaned = _clean_formula_text(value)
    if not cleaned or "不给额外计算" in cleaned:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    return float(match.group(1)) if match else None


def _parse_formula(value: str) -> tuple[float, float, str] | None:
    cleaned = _clean_formula_text(value)
    if not cleaned:
        return None
    label = cleaned.replace(" ", "")
    expr = label.replace("装等", "x").replace("×", "*").replace("（", "(").replace("）", ")")
    match = re.fullmatch(r"(?:(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?\*)?x([+-]\d+(?:\.\d+)?)?", expr)
    if match:
        numerator, denominator, offset = match.groups()
        multiplier = float(numerator or 1)
        if denominator:
            multiplier /= float(denominator)
        return multiplier, float(offset or 0), label
    grouped = re.fullmatch(r"(?:(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?\*)?\(x([+-]\d+(?:\.\d+)?)\)", expr)
    if grouped:
        numerator, denominator, inner_offset = grouped.groups()
        multiplier = float(numerator or 1)
        if denominator:
            multiplier /= float(denominator)
        return multiplier, multiplier * float(inner_offset or 0), label
    return None


def _stat_key_from_label(value: str) -> str:
    return {
        "攻击": "atkFlat",
        "攻击%": "atkPct",
        "防御": "defFlat",
        "防御%": "defPct",
        "生命": "hpFlat",
        "生命%": "hpPct",
        "速度": "spd",
        "暴率": "crit",
        "爆率": "crit",
        "暴击": "crit",
        "爆伤": "cdmg",
        "命中": "eff",
        "抵抗": "res",
        "效命": "eff",
        "效抗": "res",
    }.get(value, "")


def _tokens(value: str) -> list[str]:
    cleaned = _clean_cell(value)
    return [token for token in re.split(r"[、，, \n]+", cleaned) if token]


def _clean_cell(value: str) -> str:
    return str(value or "").replace("<br>", "\n").replace("&nbsp;", " ").strip()


def _clean_formula_text(value: str) -> str:
    return _clean_cell(value).replace(" ", "").replace("×", "*")


_MD_SET_GROUPS, _MD_VALID_STATS, _MD_FORMULAS, _MD_CATEGORY_RULES = _load_target_score_rules_from_md()
SET_GROUPS.update(_MD_SET_GROUPS)
VALID_STATS.update(_MD_VALID_STATS)
FORMULAS.update(_MD_FORMULAS)
CATEGORY_RULES = _MD_CATEGORY_RULES

SPEED_POTENTIAL_UNGATED_SET_CODES = frozenset({"set_speed", "set_debuff"} | SET_GROUPS["speedNonSpeed"])


def speed_potential_set_eligible(set_code: str) -> bool:
    return set_code in SPEED_POTENTIAL_UNGATED_SET_CODES
