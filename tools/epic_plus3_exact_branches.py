"""Offline exact normal-Epic +0 -> +3 branches from the STOVE roll table.

This module is deliberately separate from the released simulator.  It models
only the first +3 reinforcement of an already observed real +0 Epic item.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Iterable, TypeVar

from src.e7_enhance.models import Gear, RollHit, round1


# STOVE's displayed probabilities are rounded.  Normalize each stat's local
# profile rather than treating the tiny display residual as a missing branch.
_RAW_NORMAL_EPIC_PLUS3_ROLLS: dict[str, tuple[tuple[int, float], ...]] = {
    "atkFlat": ((33, 0.06103), *tuple((value, 0.07353) for value in range(34, 46)), (46, 0.05662)),
    "defFlat": (*tuple((value, 0.14265) for value in range(28, 35)), (35, 0.00143)),
    "hpFlat": ((157, 0.01133), *tuple((value, 0.02221) for value in range(158, 202)), (202, 0.01133)),
    "atkPct": tuple((value, 0.2) for value in range(4, 9)),
    "defPct": tuple((value, 0.2) for value in range(4, 9)),
    "hpPct": tuple((value, 0.2) for value in range(4, 9)),
    "eff": tuple((value, 0.2) for value in range(4, 9)),
    "res": tuple((value, 0.2) for value in range(4, 9)),
    "spd": ((2, 0.33223), (3, 0.33223), (4, 0.33223), (5, 0.00332)),
    "crit": tuple((value, 1.0 / 3.0) for value in range(3, 6)),
    "cdmg": tuple((value, 0.25) for value in range(4, 8)),
}


def official_plus3_distribution(stat_key: str) -> tuple[tuple[int, float], ...]:
    """Return the normalized STOVE normal-85 Epic reinforcement distribution."""
    try:
        values = _RAW_NORMAL_EPIC_PLUS3_ROLLS[stat_key]
    except KeyError as error:
        raise ValueError(f"unsupported normal Epic +3 stat: {stat_key}") from error
    total = sum(probability for _value, probability in values)
    if total <= 0:
        raise ValueError(f"invalid probability profile for {stat_key}")
    return tuple((value, probability / total) for value, probability in values)


@dataclass(frozen=True)
class Plus3Branch:
    """One exact next state conditional on a real +0 Epic item."""

    gear: Gear
    probability: float
    target_index: int
    target_key: str
    delta: int


def enumerate_normal_epic_plus3(gear: Gear) -> tuple[Plus3Branch, ...]:
    """Enumerate all legal +3 outcomes using the existing equal-target rule.

    ``装备强化与评分规则审阅.md`` records the project rule that an existing
    substat event chooses each of the current ``n`` substats with probability
    ``1/n``.  Epic +0 equipment therefore uses one quarter per target.
    """
    if gear.rank != "Epic" or gear.level not in {85, 90} or gear.enhance != 0:
        raise ValueError("exact +3 branches require an Epic level-85/90 +0 gear")
    if len(gear.substats) != 4:
        raise ValueError("Epic +0 exact +3 branches require exactly four substats")

    target_probability = 1.0 / len(gear.substats)
    branches: list[Plus3Branch] = []
    for index, stat in enumerate(gear.substats):
        for delta, roll_probability in official_plus3_distribution(stat.key):
            updated = replace(stat, value=round1(stat.normalized_value + delta), rolls=stat.rolls + 1)
            substats = list(gear.substats)
            substats[index] = updated
            advanced = replace(
                gear,
                enhance=3,
                substats=substats,
                roll_history=list(gear.roll_history) + [RollHit(3, updated.type, delta)],
            )
            branches.append(Plus3Branch(
                gear=advanced,
                probability=target_probability * roll_probability,
                target_index=index,
                target_key=stat.key,
                delta=delta,
            ))
    total = sum(branch.probability for branch in branches)
    if abs(total - 1.0) > 1e-12:
        raise AssertionError(f"normal Epic +3 branch probability must sum to 1, got {total}")
    return tuple(branches)


T = TypeVar("T", int, float)


def weighted_sum(branches: Iterable[Plus3Branch], value: Callable[[Plus3Branch], T]) -> float:
    """Evaluate an exact branch expectation without treating outcomes equally."""
    return sum(float(branch.probability) * float(value(branch)) for branch in branches)
