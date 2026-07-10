from __future__ import annotations

from dataclasses import replace
from typing import Any

from .enhance_policy import advise_gear
from .enhance_simulator import RollProfile, STAT_TYPE_BY_KEY, is_new_substat_event, roll_range
from .models import Gear, RollHit, Stat, round1, stat_key, validate_gear_source_rank, validate_gear_structure


class AcceptanceReplay:
    """In-memory deterministic replay backed by the production roll table."""

    def __init__(self, gear: Gear, item_source: str, path: list[dict[str, Any]]) -> None:
        validate_gear_structure(gear)
        validate_gear_source_rank(gear, item_source)
        self.initial_gear = gear
        self.gear = gear
        self.item_source = item_source
        self.path = list(path)
        self.index = 0

    def reset(self) -> dict[str, Any]:
        self.gear = self.initial_gear
        self.index = 0
        return self.snapshot(None)

    def next(self) -> dict[str, Any]:
        if self.index >= len(self.path):
            raise ValueError("回放路径已结束。")
        before_substats = self.gear.to_dict()["substats"]
        event = self.path[self.index]
        checkpoint = int(event.get("enhance", -1))
        if checkpoint != self.gear.enhance + 3:
            raise ValueError("回放强化节点必须是当前等级后的下一个 +3 节点。")
        key = stat_key(str(event.get("type") or ""))
        value = float(event.get("value", 0))
        low, high = roll_range(RollProfile(self.gear.roll_level or self.gear.level, self.gear.rank, self.item_source), key)
        if value < low or value > high or value != int(value):
            raise ValueError(f"回放跳值必须在 {low}~{high} 之间。")
        stats = list(self.gear.substats)
        new_stat = is_new_substat_event(self.gear.rank, checkpoint) and len(stats) < 4
        index = next((i for i, stat in enumerate(stats) if stat.key == key), None)
        if new_stat:
            if index is not None or key == self.gear.main_stat.key:
                raise ValueError("补词条不能与主属性或已有副属性重复。")
            stats.append(Stat(STAT_TYPE_BY_KEY[key], value, rolls=1))
        else:
            if index is None:
                raise ValueError("本次强化必须命中已有副属性。")
            stat = stats[index]
            stats[index] = replace(stat, value=round1(stat.normalized_value + value), rolls=stat.rolls + 1)
        candidate = replace(
            self.gear,
            enhance=checkpoint,
            substats=stats,
            roll_history=list(self.gear.roll_history) + [RollHit(checkpoint, STAT_TYPE_BY_KEY[key], value)],
        )
        validate_gear_structure(candidate)
        self.gear = candidate
        self.index += 1
        snapshot = self.snapshot({"enhance": checkpoint, "type": STAT_TYPE_BY_KEY[key], "value": value})
        snapshot["before_substats"] = before_substats
        return snapshot

    def snapshot(self, event: dict[str, Any] | None) -> dict[str, Any]:
        return {"gear": self.gear, "event": event, "remaining": len(self.path) - self.index, "suggestion": advise_gear(self.gear, self.item_source)}
