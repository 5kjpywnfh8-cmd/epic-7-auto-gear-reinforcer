"""Released M1 22-speed reachability rescue for normal Heroic gear.

This module deliberately owns the small, audited probability model instead of
depending on an offline research tool.  It is a one-way override: a released
base-policy continue can never be turned into a stop.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Gear


AUTHORIZED_CHECKPOINTS = frozenset((6, 9, 12))
SCOPE_DESCRIPTION = (
    "仅普通85紫装、非鞋、已有速度副属性的+6/+9/+12；"
    "仅在百里边际低档基础策略停止时，以P22>0救回继续"
)

# Official published Heroic speed distribution.  The displayed percentages
# total 100.001% after decimal conversion, so enumeration normalizes them.
_HEROIC_SPEED_ROLLS = ((1, 0.00332), (2, 0.33223), (3, 0.33223), (4, 0.33223))
_SPEED_REFORGE_BONUS = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 4}
_FUTURE_CHECKPOINTS = (3, 6, 9, 12, 15)


def p22_exact(gear: Gear) -> float:
    """Return exact probability of reaching 22+ reforged speed from *gear*."""
    speed = _speed_stat(gear)
    if speed is None or gear.slot == "boot":
        return 0.0

    total = sum(probability for _value, probability in _HEROIC_SPEED_ROLLS)
    profile = tuple((value, probability / total) for value, probability in _HEROIC_SPEED_ROLLS)
    count = max(len(gear.substats), 4 if gear.enhance >= 12 else len(gear.substats))
    states: dict[tuple[int, int, int], float] = {
        (int(speed.normalized_value), int(speed.rolls), count): 1.0,
    }
    for checkpoint in _FUTURE_CHECKPOINTS:
        if checkpoint <= gear.enhance:
            continue
        next_states: dict[tuple[int, int, int], float] = defaultdict(float)
        for (value, rolls, stat_count), probability in states.items():
            # Heroic +12 supplies the fourth substat. It is not a roll.
            if checkpoint == 12 and stat_count < 4:
                next_states[(value, rolls, stat_count + 1)] += probability
                continue
            hit_probability = 1.0 / stat_count
            next_states[(value, rolls, stat_count)] += probability * (1.0 - hit_probability)
            for increment, roll_probability in profile:
                next_states[(value + increment, rolls + 1, stat_count)] += (
                    probability * hit_probability * roll_probability
                )
        states = next_states

    return sum(
        probability
        for (value, rolls, _count), probability in states.items()
        if value + _SPEED_REFORGE_BONUS.get(max(0, min(6, rolls)), 0) >= 22
    )


def rescue_decision(gear: Gear, *, item_source: str, baseline_continue: bool) -> dict:
    """Describe whether M1 changes a base-policy action for this observable state."""
    checkpoint = int(gear.enhance)
    speed = _speed_stat(gear)
    applies = bool(
        item_source == "normal_85"
        and gear.rank == "Heroic"
        and checkpoint in AUTHORIZED_CHECKPOINTS
        and gear.slot != "boot"
        and speed is not None
    )
    probability = p22_exact(gear) if applies else 0.0
    rescued = bool(applies and not baseline_continue and probability > 0.0)
    if not applies:
        reason = "不在M1正式适用范围"
    elif baseline_continue:
        reason = "基础策略已继续，M1不得覆盖为停止"
    elif probability <= 0.0:
        reason = "精确P22=0，维持基础策略停止"
    else:
        reason = "基础策略停止且精确P22>0，M1可达性救回"
    return {
        "applies": applies,
        "scope": SCOPE_DESCRIPTION,
        "checkpoint": checkpoint,
        "p22": probability,
        "baseline_action": "continue" if baseline_continue else "stop",
        "action": "continue" if (baseline_continue or rescued) else "stop",
        "rescued": rescued,
        "reason": reason,
    }


def _speed_stat(gear: Gear):
    return next((stat for stat in gear.substats if stat.key == "spd"), None)
