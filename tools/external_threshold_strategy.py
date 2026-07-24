"""Frozen external red/purple threshold-table candidate D (offline only)."""
from __future__ import annotations

from src.e7_enhance.rules import CATEGORY_RULES
from src.e7_enhance.score_engine import official_score_for_stats, speed_value, valid_rule_profile


D_THRESHOLDS = {
    "Epic": {0: {"speed": 2, "total": 25, "output": 19}, 3: {"speed": 3, "total": 31, "output": 24}, 6: {"speed": 5, "total": 37, "output": 30}, 9: {"speed": 9, "total": 43, "output": 37}},
    "Heroic": {0: {"speed": 2, "total": 22, "output": 19}, 3: {"speed": 3, "total": 28, "output": 24}, 6: {"speed": 5, "total": 34, "output": 30}, 9: {"speed": 10, "total": 40, "output": 37}},
}


def output_effective_gs(gear) -> float:
    """Only the legal ordinary-output rule; never substitute critless/best profile."""
    output_rule = next(rule for rule in CATEGORY_RULES if rule["category"] == "输出")
    profile = valid_rule_profile(gear, output_rule)
    return float(profile["effective_score"]) if profile else 0.0


def metrics(gear) -> dict[str, float]:
    return {"speed": float(speed_value(gear)), "total_official_gs": float(official_score_for_stats(gear.substats)), "output_effective_gs": output_effective_gs(gear)}


def decide(rank: str, checkpoint: int, *, speed: float, total_official_gs: float, output_effective_gs: float) -> str:
    threshold = D_THRESHOLDS[rank][checkpoint]
    return "continue" if speed >= threshold["speed"] or total_official_gs >= threshold["total"] or output_effective_gs >= threshold["output"] else "stop"


def action_for_gear(gear, checkpoint: int | None = None) -> str:
    checkpoint = gear.enhance if checkpoint is None else checkpoint
    values = metrics(gear)
    return decide(gear.rank, checkpoint, **values)


def terminal_indicators(*, native_total_gs: float, converted_total_gs: float, speed: float, output_gs: float) -> dict[str, int]:
    return {"native_heirloom": int(native_total_gs >= 75), "converted_heirloom": int(converted_total_gs >= 75), "speed22": int(speed >= 22), "output60": int(output_gs >= 60)}


def simulate_path(path: dict[int, object]) -> dict[str, object]:
    """Literal D path: node gates through +9, then direct +15 without +12 gate."""
    current = min(path)
    reached = [current]
    actions: dict[int, str] = {}
    while current < 15:
        state = path[current]
        action = action_for_gear(state, current)
        actions[current] = action
        if action == "stop":
            break
        if current == 9:
            # There is no +12 review gate in D, but enhancement still passes
            # through +12 and must therefore be counted as reached.
            reached.extend((12, 15))
            current = 15
        else:
            current += 3
            reached.append(current)
    return {"stop_checkpoint": current, "actions": actions, "reached_checkpoints": reached}
