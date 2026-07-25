from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .rules import PERCENT_STAT_KEYS, RANK_ALIASES, SET_ALIASES, SET_CODE_TO_NAME, SLOT_ALIASES, STAT_TYPE_TO_KEY


SLOT_FORBIDDEN_SUBSTAT_KEYS = {
    "weapon": {"defFlat", "defPct"},
    "armor": {"atkFlat", "atkPct"},
}
MAIN_STAT_KEYS_BY_SLOT = {
    "weapon": {"atkFlat"},
    "helm": {"hpFlat"},
    "armor": {"defFlat"},
    "neck": {"atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "crit", "cdmg"},
    "ring": {"atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "eff", "res"},
    "boot": {"atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "spd"},
}
ALLOWED_RANKS_BY_ITEM_SOURCE = {
    "normal_85": {"Heroic", "Epic"},
    "rift_85": {"Epic"},
}
SUPPORTED_EQUIPMENT_LEVELS = {85, 90}
SUPPORTED_ENHANCEMENT_CHECKPOINTS = {0, 3, 6, 9, 12, 15}
SUPPORTED_STAT_KEYS = frozenset(STAT_TYPE_TO_KEY.values())


def stat_key(value: str | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    return STAT_TYPE_TO_KEY.get(raw, raw)


def normalize_stat_value(key: str, value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if key in PERCENT_STAT_KEYS and 0 < abs(number) < 1:
        return number * 100
    return number


def round1(value: float) -> float:
    return round(float(value) + 1e-9, 1)


def normalize_set(value: str | None) -> str:
    raw = str(value or "").strip()
    return SET_ALIASES.get(raw, raw)


def normalize_slot(value: str | None) -> str:
    raw = str(value or "").strip()
    return SLOT_ALIASES.get(raw, raw.lower())


def normalize_rank(value: str | None) -> str:
    raw = str(value or "").strip()
    return RANK_ALIASES.get(raw, raw or "Epic")


@dataclass(frozen=True)
class Stat:
    type: str
    value: float
    rolls: int = 0
    modified: bool = False

    @property
    def key(self) -> str:
        return stat_key(self.type)

    @property
    def normalized_value(self) -> float:
        return normalize_stat_value(self.key, self.value)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Stat":
        return cls(
            type=str(data.get("type") or data.get("key") or ""),
            value=normalize_stat_value(stat_key(data.get("type") or data.get("key")), data.get("value")),
            rolls=int(data.get("rolls") or 0),
            modified=bool(data.get("modified") or False),
        )


@dataclass(frozen=True)
class RollHit:
    enhance: int
    type: str
    value: float = 0

    @property
    def key(self) -> str:
        return stat_key(self.type)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RollHit":
        return cls(
            enhance=int(data.get("enhance") or data.get("level") or 0),
            type=str(data.get("type") or data.get("key") or data.get("stat") or ""),
            value=normalize_stat_value(stat_key(data.get("type") or data.get("key") or data.get("stat")), data.get("value") or data.get("delta") or 0),
        )


@dataclass(frozen=True)
class Gear:
    set: str
    slot: str
    main_stat: Stat
    enhance: int = 0
    level: int = 85
    rank: str = "Epic"
    substats: list[Stat] = field(default_factory=list)
    roll_history: list[RollHit] = field(default_factory=list)
    code: str = ""
    reforge_eligible: bool = False
    roll_level: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Gear":
        main = data.get("mainStat") or data.get("main") or {}
        main_type = main.get("type") if isinstance(main, dict) else data.get("mainType")
        main_value = main.get("value") if isinstance(main, dict) else data.get("mainValue", 0)
        return cls(
            set=normalize_set(data.get("set") or data.get("setCode") or data.get("set_code")),
            slot=normalize_slot(data.get("slot") or data.get("type") or data.get("gear")),
            main_stat=Stat.from_dict({"type": main_type, "value": main_value}),
            enhance=max(0, min(15, int(data.get("enhance") or data.get("enhanceLevel") or 0))),
            level=int(data.get("level") or 85),
            rank=normalize_rank(data.get("rank")),
            substats=[Stat.from_dict(item) for item in data.get("substats", [])],
            roll_history=[RollHit.from_dict(item) for item in data.get("rollHistory", [])],
            code=str(data.get("code") or ""),
            reforge_eligible=bool(data.get("reforgeEligible") or data.get("reforge_eligible") or False),
            roll_level=int(data.get("rollLevel") or data.get("roll_level") or data.get("level") or 85),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "set": self.set,
            "slot": self.slot,
            "mainStat": {"type": self.main_stat.type, "value": self.main_stat.value},
            "enhance": self.enhance,
            "level": self.level,
            "rank": self.rank,
            "substats": [{"type": s.type, "value": s.value, "rolls": s.rolls, "modified": s.modified} for s in self.substats],
            "rollHistory": [{"enhance": h.enhance, "type": h.type, "value": h.value} for h in self.roll_history],
            "code": self.code,
            "reforgeEligible": self.reforge_eligible,
            "rollLevel": self.roll_level or self.level,
        }


def invalid_substat_keys(gear: Gear) -> set[str]:
    forbidden = set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(gear.slot, set()))
    forbidden.add(gear.main_stat.key)
    return {stat.key for stat in gear.substats if stat.key in forbidden}


def validate_gear_substats(gear: Gear) -> None:
    if len(gear.substats) > 4:
        raise ValueError("Gear may have at most four substats")
    expected_count = 4 if gear.rank == "Epic" or gear.level == 90 or gear.enhance >= 12 else 3
    if len(gear.substats) != expected_count:
        raise ValueError(f"{gear.rank} gear must have {expected_count} substats at +{gear.enhance}")
    unknown_keys = sorted({stat.key for stat in gear.substats if stat.key not in SUPPORTED_STAT_KEYS})
    if unknown_keys:
        raise ValueError(f"Unknown substats: {', '.join(unknown_keys)}")
    invalid_keys = invalid_substat_keys(gear)
    if invalid_keys:
        raise ValueError(f"Invalid substats for {gear.slot}: {', '.join(sorted(invalid_keys))}")

    keys = [stat.key for stat in gear.substats]
    duplicates = sorted({key for key in keys if key and keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate substats: {', '.join(duplicates)}")


def validate_gear_structure(gear: Gear) -> None:
    if gear.set not in SET_CODE_TO_NAME:
        raise ValueError(f"Unknown gear set: {gear.set or '<empty>'}")
    if gear.level not in SUPPORTED_EQUIPMENT_LEVELS:
        raise ValueError(f"Unsupported equipment level: {gear.level}")
    if gear.enhance not in SUPPORTED_ENHANCEMENT_CHECKPOINTS:
        raise ValueError(f"Unsupported enhancement checkpoint: +{gear.enhance}")
    allowed_main = MAIN_STAT_KEYS_BY_SLOT.get(gear.slot)
    if allowed_main is None:
        raise ValueError(f"Unknown gear slot: {gear.slot}")
    if gear.main_stat.key not in allowed_main:
        raise ValueError(f"Invalid main stat for {gear.slot}: {gear.main_stat.key}")
    validate_gear_substats(gear)


def validate_source_rank(rank: str, item_source: str) -> None:
    allowed_ranks = ALLOWED_RANKS_BY_ITEM_SOURCE.get(item_source)
    if allowed_ranks is None:
        raise ValueError(f"Unknown item source: {item_source}")
    if rank not in allowed_ranks:
        allowed = ", ".join(sorted(allowed_ranks))
        raise ValueError(f"{item_source} only supports {allowed} rank, got {rank}")


def validate_gear_source_rank(gear: Gear, item_source: str) -> None:
    validate_source_rank(gear.rank, item_source)
