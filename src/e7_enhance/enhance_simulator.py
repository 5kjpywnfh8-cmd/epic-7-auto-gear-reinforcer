from __future__ import annotations

from dataclasses import dataclass, replace
import random
from typing import Any

from .enhance_policy import advise_gear
from .models import ALLOWED_RANKS_BY_ITEM_SOURCE, Gear, RollHit, SLOT_FORBIDDEN_SUBSTAT_KEYS, Stat, round1, validate_source_rank
from .resource_model import ResourceAmount, calibration_for_rank, cumulative_cost, material_pool_for_slot
from .rules import OFFICIAL_SCORE_WEIGHTS, SET_GROUPS
from .score_engine import evaluate_gear, official_score_for_stats, speed_value


CHECKPOINTS = (0, 3, 6, 9, 12, 15)
STAT_POOL = ("atkPct", "defPct", "hpPct", "eff", "res", "spd", "crit", "cdmg", "atkFlat", "defFlat", "hpFlat")
PERCENT_KEYS = {"atkPct", "defPct", "hpPct", "eff", "res"}
PLAIN_REFORGE_BONUS = {0: 0, 1: 1, 2: 3, 3: 4, 4: 5, 5: 7, 6: 8}
CDMG_REFORGE_BONUS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 6, 6: 7}
SPEED_REFORGE_BONUS = {0: 0, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 4}
FLAT_REFORGE_BONUS = {"atkFlat": 11, "defFlat": 9, "hpFlat": 56}

BASE_ROLL_RANGES = {
    "normal_85": {
        "spd": (2, 4),
        "crit": (3, 5),
        "cdmg": (4, 7),
        "atkPct": (4, 8),
        "defPct": (4, 8),
        "hpPct": (4, 8),
        "eff": (4, 8),
        "res": (4, 8),
        "atkFlat": (33, 47),
        "defFlat": (28, 35),
        "hpFlat": (158, 203),
    },
    "rift_85": {
        "spd": (3, 4),
        "crit": (4, 5),
        "cdmg": (5, 7),
        "atkPct": (6, 8),
        "defPct": (6, 8),
        "hpPct": (6, 8),
        "eff": (6, 8),
        "res": (6, 8),
        "atkFlat": (40, 47),
        "defFlat": (33, 35),
        "hpFlat": (178, 203),
    },
}


@dataclass(frozen=True)
class RollProfile:
    level: int
    rank: str
    item_source: str


# Current data covers level-85 gear and its level-90 reforged form, which
# shares the original roll table. The complete profile key prevents source
# alone from selecting a roll range when new data arrives.
ROLL_RANGES = {
    RollProfile(level, rank, item_source): ranges
    for level in (85, 90)
    for item_source, ranks in ALLOWED_RANKS_BY_ITEM_SOURCE.items()
    for rank in ranks
    for ranges in (BASE_ROLL_RANGES[item_source],)
}

STAT_TYPE_BY_KEY = {
    "atkPct": "AttackPercent",
    "defPct": "DefensePercent",
    "hpPct": "HealthPercent",
    "eff": "EffectivenessPercent",
    "res": "EffectResistancePercent",
    "spd": "Speed",
    "crit": "CriticalHitChancePercent",
    "cdmg": "CriticalHitDamagePercent",
    "atkFlat": "Attack",
    "defFlat": "Defense",
    "hpFlat": "Health",
}

RANDOM_SETS = tuple(sorted(set().union(*SET_GROUPS.values())))
RANDOM_SLOTS = ("weapon", "helm", "armor", "neck", "ring", "boot")


class SimulationOptions:
    def __init__(
        self,
        runs: int = 5000,
        seed: int = 1,
        gear_source: str = "riftslash_20_buff",
        item_source: str = "normal_85",
        rank: str = "Epic",
        level: int = 85,
        stop_at_checkpoint: int | None = None,
        strategy: str = "full",
    ) -> None:
        self.runs = max(1, int(runs))
        self.seed = int(seed)
        self.gear_source = gear_source
        self.item_source = item_source
        self.rank = rank
        self.level = int(level)
        self.stop_at_checkpoint = stop_at_checkpoint
        self.strategy = strategy


def expected_roll_value(profile: RollProfile, key: str) -> float:
    low, high = roll_range(profile, key)
    return (low + high) / 2


def roll_range(profile: RollProfile, key: str) -> tuple[int, int]:
    table = ROLL_RANGES.get(profile)
    if table is None:
        raise ValueError(f"unsupported roll profile: {profile}")
    if key not in table:
        raise ValueError(f"unknown stat key for roll table: {key}")
    return table[key]


def roll_value(rng: random.Random, profile: RollProfile, key: str) -> int:
    low, high = roll_range(profile, key)
    return rng.randint(low, high)


def simulate_drops(options: SimulationOptions | None = None) -> dict[str, Any]:
    options = options or SimulationOptions()
    rng = random.Random(options.seed)
    outcomes = [simulate_one(generate_gear(rng, options), options, rng, count_acquisition=True) for _ in range(options.runs)]
    return summarize_outcomes(outcomes, options)


def simulate_gear(gear: Gear, options: SimulationOptions | None = None) -> dict[str, Any]:
    options = options or SimulationOptions()
    rng = random.Random(options.seed)
    base = normalize_starting_gear(gear)
    outcomes = [simulate_one(base, options, rng, count_acquisition=True) for _ in range(options.runs)]
    return summarize_outcomes(outcomes, options)


def simulate_one(base: Gear, options: SimulationOptions, rng: random.Random, count_acquisition: bool) -> dict[str, Any]:
    gear = clone_gear(base)
    valid_hits = 0
    invalid_hits = 0
    stopped = False
    stop_checkpoint = nearest_checkpoint(gear.enhance)

    if options.stop_at_checkpoint == 0:
        stopped = True

    if not stopped:
        for checkpoint in CHECKPOINTS:
            if checkpoint <= gear.enhance:
                continue
            gear, hit_valid = enhance_to_checkpoint(gear, checkpoint, options.item_source, rng)
            if hit_valid is True:
                valid_hits += 1
            elif hit_valid is False:
                invalid_hits += 1
            stop_checkpoint = checkpoint

            if checkpoint >= 15:
                break
            if options.stop_at_checkpoint == checkpoint:
                stopped = True
                break
            if options.strategy == "current" and advise_gear(gear)["summary"]["recommendation"] == "stop":
                stopped = True
                break

    final_gear = reforge_gear(gear)
    final_eval = evaluate_gear(final_gear)
    final_speed = speed_value(final_gear)
    success = not stopped and is_successful_final(final_eval, final_speed)
    costs = cost_for_outcome(stop_checkpoint, success, count_acquisition, options.gear_source, options.rank, gear.slot)
    total_hits = valid_hits + invalid_hits

    return {
        "success": success,
        "stop_checkpoint": stop_checkpoint,
        "gear_acquisition_stamina": costs["gear_acquisition_stamina"],
        "upgrade_stamina": costs["upgrade_stamina"],
        "sell_recovery_stamina": costs["sell_recovery_stamina"],
        "total_stamina": costs["total_stamina"],
        "missing_recovery_data": costs["missing_recovery_data"],
        "missing_acquisition_data": costs["missing_acquisition_data"],
        "reforge_score": final_eval.effective_score,
        "reforge_speed": final_speed,
        "speed_target": final_speed >= 22 and final_gear.slot != "boot",
        "valid_hits": valid_hits,
        "invalid_hits": invalid_hits,
        "hit_count": total_hits,
    }


def enhance_to_checkpoint(gear: Gear, checkpoint: int, item_source: str, rng: random.Random) -> tuple[Gear, bool | None]:
    if is_new_substat_event(gear.rank, checkpoint) and len(gear.substats) < 4:
        next_stat = generate_missing_substat(rng, gear, item_source)
        return replace(gear, enhance=checkpoint, substats=gear.substats + [next_stat]), False

    if not gear.substats:
        return replace(gear, enhance=checkpoint), None

    before_eval = evaluate_gear(gear)
    valid_keys = set(before_eval.valid_profile_keys)
    index = rng.randrange(len(gear.substats))
    hit = gear.substats[index]
    key = hit.key
    delta = roll_value(rng, RollProfile(gear.roll_level or gear.level, gear.rank, item_source), key)
    updated = replace(hit, value=round1(hit.normalized_value + delta), rolls=hit.rolls + 1)
    substats = list(gear.substats)
    substats[index] = updated
    history = list(gear.roll_history) + [RollHit(checkpoint, updated.type, delta)]
    return replace(gear, enhance=checkpoint, substats=substats, roll_history=history), key in valid_keys


def generate_gear(rng: random.Random, options: SimulationOptions) -> Gear:
    validate_source_rank(options.rank, options.item_source)
    slot = rng.choice(RANDOM_SLOTS)
    main_key = random_main_key(rng, slot)
    sub_count = initial_substat_count(options.rank)
    available = [key for key in STAT_POOL if key != main_key and key not in slot_forbidden_substats(slot)]
    sub_keys = rng.sample(available, sub_count)
    profile = RollProfile(options.level, options.rank, options.item_source)
    substats = [generate_stat(rng, profile, key) for key in sub_keys]
    return Gear(
        set=rng.choice(RANDOM_SETS),
        slot=slot,
        main_stat=Stat(STAT_TYPE_BY_KEY[main_key], 0),
        enhance=0,
        level=options.level,
        rank=options.rank,
        substats=substats,
        roll_history=[],
        reforge_eligible=True,
    )


def generate_missing_substat(rng: random.Random, gear: Gear, item_source: str) -> Stat:
    existing = {stat.key for stat in gear.substats}
    existing.add(gear.main_stat.key)
    available = [key for key in STAT_POOL if key not in existing and key not in slot_forbidden_substats(gear.slot)]
    return generate_stat(rng, RollProfile(gear.roll_level or gear.level, gear.rank, item_source), rng.choice(available or list(STAT_POOL)))


def generate_stat(rng: random.Random, profile: RollProfile, key: str) -> Stat:
    return Stat(STAT_TYPE_BY_KEY[key], roll_value(rng, profile, key), rolls=1)


def random_main_key(rng: random.Random, slot: str) -> str:
    if slot == "weapon":
        return "atkFlat"
    if slot == "helm":
        return "hpFlat"
    if slot == "armor":
        return "defFlat"
    if slot == "neck":
        return rng.choice(("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "crit", "cdmg"))
    if slot == "ring":
        return rng.choice(("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "eff", "res"))
    if slot == "boot":
        return rng.choice(("atkFlat", "defFlat", "hpFlat", "atkPct", "defPct", "hpPct", "spd"))
    return "atkPct"


def slot_forbidden_substats(slot: str) -> set[str]:
    return set(SLOT_FORBIDDEN_SUBSTAT_KEYS.get(slot, set()))


def reforge_gear(gear: Gear) -> Gear:
    if gear.level != 85:
        return gear
    substats = []
    for stat in gear.substats:
        bonus = reforge_bonus_value(stat.key, stat.rolls)
        substats.append(replace(stat, value=round1(stat.normalized_value + bonus)))
    code = gear.code if gear.code.endswith("_u") else f"{gear.code or 'sim'}_u"
    return replace(gear, level=90, enhance=15, code=code, substats=substats)


def reforge_bonus_value(key: str, rolls: int) -> float:
    roll_count = max(0, min(6, int(round(rolls or 0))))
    if key in PERCENT_KEYS:
        return PLAIN_REFORGE_BONUS.get(roll_count, 0)
    if key == "crit":
        return roll_count
    if key == "cdmg":
        return CDMG_REFORGE_BONUS.get(roll_count, 0)
    if key == "spd":
        return SPEED_REFORGE_BONUS.get(roll_count, 0)
    if key in FLAT_REFORGE_BONUS:
        return FLAT_REFORGE_BONUS[key] * roll_count
    return 0


def is_successful_final(evaluation: Any, speed: float) -> bool:
    if evaluation.gear.slot != "boot" and speed >= 22:
        return True
    return evaluation.retention.rule_matched and evaluation.target_score > 0


def cost_for_outcome(
    checkpoint: int,
    success: bool,
    count_acquisition: bool,
    gear_source: str,
    rank: str,
    slot: str | None = None,
) -> dict[str, float | bool | str]:
    calibration = calibration_for_rank(rank)
    confirmed_acquisition = calibration.gear_stamina(gear_source)
    missing_acquisition = bool(count_acquisition and confirmed_acquisition is None)
    acquisition = confirmed_acquisition if count_acquisition and confirmed_acquisition is not None else 0.0
    consumed = cumulative_cost(calibration, checkpoint)
    recovery_known = checkpoint in calibration.sell_recovery
    recovery = ResourceAmount() if success or not recovery_known else calibration.sell_recovery[checkpoint]
    missing_recovery = not success and checkpoint > 0 and not recovery_known
    net = consumed - recovery
    material_pool, material_scarcity = material_pool_for_slot(slot)
    return {
        "gear_acquisition_stamina": acquisition,
        "upgrade_stamina": calibration.rates.stamina_equivalent(consumed, material_scarcity),
        "sell_recovery_stamina": calibration.rates.stamina_equivalent(recovery, material_scarcity),
        "total_stamina": acquisition + calibration.rates.stamina_equivalent(net, material_scarcity),
        "missing_recovery_data": missing_recovery,
        "missing_acquisition_data": missing_acquisition,
        "material_pool": material_pool,
        "material_scarcity_coefficient": material_scarcity,
    }


def summarize_outcomes(outcomes: list[dict[str, Any]], options: SimulationOptions) -> dict[str, Any]:
    runs = len(outcomes)
    successes = sum(1 for item in outcomes if item["success"])
    total_stamina = sum(item["total_stamina"] for item in outcomes)
    stop_counts = {str(point): 0 for point in CHECKPOINTS}
    for item in outcomes:
        stop_counts[str(item["stop_checkpoint"])] += 1
    hit_count = sum(item["hit_count"] for item in outcomes)
    valid_hits = sum(item["valid_hits"] for item in outcomes)
    invalid_hits = sum(item["invalid_hits"] for item in outcomes)
    success_rate = successes / runs
    return {
        "simulation_runs": runs,
        "gear_source": options.gear_source,
        "item_source": options.item_source,
        "strategy": options.strategy,
        "gear_acquisition_stamina_avg": avg(outcomes, "gear_acquisition_stamina"),
        "upgrade_stamina_avg": avg(outcomes, "upgrade_stamina"),
        "sell_recovery_avg": avg(outcomes, "sell_recovery_stamina"),
        "total_stamina_avg": round1(total_stamina / runs),
        "success_rate": round_rate(success_rate),
        "stop_rate_by_checkpoint": {key: round_rate(value / runs) for key, value in stop_counts.items()},
        "expected_reforge_score_avg": avg(outcomes, "reforge_score"),
        "expected_reforge_speed_avg": avg(outcomes, "reforge_speed"),
        "speed_target_rate": round_rate(sum(1 for item in outcomes if item["speed_target"]) / runs),
        "valid_hit_rate": round_rate(valid_hits / hit_count) if hit_count else 0.0,
        "invalid_hit_rate": round_rate(invalid_hits / hit_count) if hit_count else 0.0,
        "cost_per_success": round1(total_stamina / successes) if successes else None,
        "missing_recovery_data": any(item["missing_recovery_data"] for item in outcomes),
        "missing_acquisition_data": any(item["missing_acquisition_data"] for item in outcomes),
    }


def render_simulation_summary(result: dict[str, Any]) -> str:
    cost = result["cost_per_success"] if result["cost_per_success"] is not None else "无成功样本"
    lines = [
        "模拟强化校准",
        f"样本数：{result['simulation_runs']}",
        f"装备来源：{result['item_source']} / {result['gear_source']}",
        f"成功率：{round1(result['success_rate'] * 100)}%",
        f"单胚子平均总成本：{result['total_stamina_avg']} 体力",
        f"每件成功装备成本：{cost} 体力",
        f"重铸后平均有效分：{result['expected_reforge_score_avg']}",
        f"重铸后平均速度：{result['expected_reforge_speed_avg']}",
        f"速度目标率：{round1(result['speed_target_rate'] * 100)}%",
        "各节点停留率：",
    ]
    for checkpoint, rate in result["stop_rate_by_checkpoint"].items():
        lines.append(f"- +{checkpoint}: {round1(rate * 100)}%")
    return "\n".join(lines)


def avg(items: list[dict[str, Any]], key: str) -> float:
    return round1(sum(float(item[key]) for item in items) / len(items)) if items else 0.0


def round_rate(value: float) -> float:
    return round(float(value) + 1e-12, 4)


def clone_gear(gear: Gear) -> Gear:
    return Gear.from_dict(gear.to_dict())


def normalize_starting_gear(gear: Gear) -> Gear:
    if gear.enhance < 0:
        gear = replace(gear, enhance=0)
    return gear


def initial_substat_count(rank: str) -> int:
    return {"Rare": 2, "Heroic": 3, "Epic": 4}.get(rank, 4)


def is_new_substat_event(rank: str, checkpoint: int) -> bool:
    return checkpoint in {"Rare": {3, 6}, "Heroic": {12}, "Epic": set()}.get(rank, set())


def nearest_checkpoint(enhance: int) -> int:
    for point in reversed(CHECKPOINTS):
        if enhance >= point:
            return point
    return 0
