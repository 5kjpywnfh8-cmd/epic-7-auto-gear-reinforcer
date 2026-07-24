"""Offline-only speed-roll probability profiles for the 22-speed study.

This module intentionally does not change the released simulator's roll
tables.  The normal-85 Epic profile is transcribed from the STOVE probability
table; the Heroic profile is the user-confirmed project rule.  Rift remains
independent and uses its existing rift roll range for this study.
"""
from __future__ import annotations

import random

from src.e7_enhance.enhance_simulator import RollProfile, roll_range


STOVE_NORMAL_EPIC_SPEED = ((2, 0.33223), (3, 0.33223), (4, 0.33223), (5, 0.00332))
USER_CONFIRMED_NORMAL_HEROIC_SPEED = ((1, 0.00332), (2, 0.33223), (3, 0.33223), (4, 0.33223))


def speed_roll_distribution(
    item_source: str,
    rank: str,
    *,
    rare_speed_rolls_removed: bool = False,
) -> tuple[tuple[int, float], ...]:
    """Return the study-only discrete speed-jump distribution.

    ``rare_speed_rolls_removed`` is a sensitivity view, never the primary
    profile.  It removes only the known rare endpoint and re-normalizes the
    remaining legal values.
    """
    if item_source == "normal_85":
        if rank == "Epic":
            values = STOVE_NORMAL_EPIC_SPEED
        elif rank == "Heroic":
            values = USER_CONFIRMED_NORMAL_HEROIC_SPEED
        else:
            raise ValueError(f"unsupported normal_85 rank: {rank}")
        if rare_speed_rolls_removed:
            values = tuple((value, probability) for value, probability in values if probability > 0.01)
            total = sum(probability for _, probability in values)
            return tuple((value, probability / total) for value, probability in values)
        return values

    if item_source == "rift_85":
        if rank != "Epic":
            raise ValueError("Heroic is not supported for rift_85")
        low, high = roll_range(RollProfile(85, "Epic", "rift_85"), "spd")
        values = tuple(range(low, high + 1))
        return tuple((value, 1.0 / len(values)) for value in values)

    raise ValueError(f"unsupported item source: {item_source}")


def sample_speed_roll(
    rng: random.Random,
    item_source: str,
    rank: str,
    *,
    rare_speed_rolls_removed: bool = False,
) -> int:
    """Sample one speed reinforcement event from the isolated profile."""
    threshold = rng.random()
    cumulative = 0.0
    distribution = speed_roll_distribution(
        item_source,
        rank,
        rare_speed_rolls_removed=rare_speed_rolls_removed,
    )
    for value, probability in distribution:
        cumulative += probability
        if threshold < cumulative:
            return value
    # The official decimal display sums to 0.999? after rounding.  The small
    # residual belongs to the final listed outcome rather than disappearing.
    return distribution[-1][0]
