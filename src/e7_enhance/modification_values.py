"""Fribbels conversion-gem maximum values for 85/90 reforged gear."""

from __future__ import annotations

from collections import defaultdict

from .models import Gear, Stat, round1
from .rules import OFFICIAL_SCORE_WEIGHTS


MODIFICATION_MAX_VALUE_SOURCE = "Fribbels modValues.reforged.greater upper bound (100% quality)"

# Upper endpoints of Fribbels Constants.modValues.reforged.greater.  These are
# modification-gem values, intentionally separate from equipment roll ranges.
REFORGED_GREATER_MAX_VALUES: dict[str, tuple[int, ...]] = {
    "spd": (4, 6, 8, 11, 13, 14),
    "hpFlat": (259, 448, 590, 685, 858, 995),
    "defFlat": (44, 79, 103, 116, 142, 165),
    "atkFlat": (58, 99, 134, 153, 184, 217),
    "crit": (5, 8, 11, 14, 16, 18),
    "cdmg": (8, 11, 15, 19, 22, 24),
    "atkPct": (9, 14, 18, 22, 25, 27),
    "defPct": (9, 14, 18, 22, 25, 27),
    "hpPct": (9, 14, 18, 22, 25, 27),
    "eff": (9, 14, 18, 22, 25, 27),
    "res": (9, 14, 18, 22, 25, 27),
}


def modification_max_value(key: str, rolls: int) -> float:
    values = REFORGED_GREATER_MAX_VALUES.get(key)
    if values is None:
        raise ValueError(f"unsupported modification stat: {key}")
    index = min(max(1, int(rolls)), len(values)) - 1
    return float(values[index])


def terminal_roll_distribution(gear: Gear, stat: Stat) -> dict[int, float]:
    """Return the exact final-roll distribution for one existing substat."""
    distribution: dict[int, float] = {int(stat.rolls): 1.0}
    substat_count = len(gear.substats)
    for checkpoint in (3, 6, 9, 12, 15):
        if checkpoint <= gear.enhance:
            continue
        if _adds_substat_at(gear.rank, checkpoint, substat_count):
            substat_count += 1
            continue
        next_distribution: dict[int, float] = defaultdict(float)
        hit_chance = 1 / substat_count
        for rolls, probability in distribution.items():
            next_distribution[rolls + 1] += probability * hit_chance
            next_distribution[rolls] += probability * (1 - hit_chance)
        distribution = dict(next_distribution)
    return {rolls: round(probability, 8) for rolls, probability in sorted(distribution.items())}


def expected_terminal_modification_max_value(gear: Gear, stat: Stat, target_key: str) -> float:
    return round1(_terminal_modification_max_value(gear, stat, target_key))


def expected_terminal_modification_max_gs(gear: Gear, stat: Stat, target_key: str) -> float:
    return round1(_terminal_modification_max_value(gear, stat, target_key) * OFFICIAL_SCORE_WEIGHTS.get(target_key, 0.0))


def _terminal_modification_max_value(gear: Gear, stat: Stat, target_key: str) -> float:
    return sum(probability * modification_max_value(target_key, rolls) for rolls, probability in terminal_roll_distribution(gear, stat).items())


def _adds_substat_at(rank: str, checkpoint: int, substat_count: int) -> bool:
    if substat_count >= 4:
        return False
    if rank == "Heroic":
        return checkpoint == 12
    if rank == "Rare":
        return checkpoint in {3, 6}
    return False
