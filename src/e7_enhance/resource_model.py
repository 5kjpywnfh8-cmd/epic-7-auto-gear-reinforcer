from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from typing import Any

from .models import round1


CHECKPOINTS = (0, 3, 6, 9, 12, 15)
POWDER_EXP = 100
POWDER_GOLD = 1600
LOWER_ENHANCE_STONE_EXP = 1500
LOWER_ENHANCE_STONE_USE_GOLD = 14400
GOOD_PROBABILITY = 0.055
GREAT_PROBABILITY = 0.055
PET_ENHANCE_EXP_MULTIPLIER = 1.066
EXPECTED_ENHANCE_EXP_MULTIPLIER = 1.15395
DEFAULT_CONVERSION_GOLD_COST = 100000

# Good and Great are mutually exclusive. Pet bonus is applied after either result.
ENHANCE_EXP_OUTCOMES = (
    (0.89, 1.0 * PET_ENHANCE_EXP_MULTIPLIER),
    (GOOD_PROBABILITY, 1.5 * PET_ENHANCE_EXP_MULTIPLIER),
    (GREAT_PROBABILITY, 2.0 * PET_ENHANCE_EXP_MULTIPLIER),
)

RED_LEVEL_EXP = {
    1: 525,
    2: 656,
    3: 788,
    4: 1050,
    5: 1575,
    6: 2100,
    7: 2887,
    8: 3675,
    9: 4463,
    10: 5512,
    11: 7708,
    12: 8925,
    13: 11025,
    14: 13912,
    15: 17850,
}
PURPLE_LEVEL_EXP = {
    1: 473,
    2: 590,
    3: 709,
    4: 945,
    5: 1417,
    6: 1890,
    7: 2599,
    8: 3308,
    9: 4016,
    10: 4961,
    11: 6379,
    12: 8032,
    13: 9923,
    14: 12521,
    15: 16065,
}


@dataclass(frozen=True)
class ResourceAmount:
    gold: float = 0
    enhance_exp: float = 0

    def __add__(self, other: "ResourceAmount") -> "ResourceAmount":
        return ResourceAmount(gold=self.gold + other.gold, enhance_exp=self.enhance_exp + other.enhance_exp)

    def __sub__(self, other: "ResourceAmount") -> "ResourceAmount":
        return ResourceAmount(gold=self.gold - other.gold, enhance_exp=self.enhance_exp - other.enhance_exp)


@dataclass(frozen=True)
class MaterialCost:
    nominal_exp: float
    powder_units: float
    lower_stone_units: float
    powder_base_exp: float
    lower_stone_base_exp: float
    gross_base_material_exp: float
    expected_returned_powder_exp: float
    net_base_material_exp: float
    expected_effective_exp: float
    powder_gold: float
    lower_stone_gold: float

    @property
    def expected_input_base_exp(self) -> float:
        return self.gross_base_material_exp

    @property
    def gold(self) -> float:
        return self.powder_gold + self.lower_stone_gold

    @property
    def resource_amount(self) -> ResourceAmount:
        return ResourceAmount(gold=self.gold, enhance_exp=self.net_base_material_exp)

    def __add__(self, other: "MaterialCost") -> "MaterialCost":
        return MaterialCost(
            nominal_exp=self.nominal_exp + other.nominal_exp,
            powder_units=self.powder_units + other.powder_units,
            lower_stone_units=self.lower_stone_units + other.lower_stone_units,
            powder_base_exp=self.powder_base_exp + other.powder_base_exp,
            lower_stone_base_exp=self.lower_stone_base_exp + other.lower_stone_base_exp,
            gross_base_material_exp=self.gross_base_material_exp + other.gross_base_material_exp,
            expected_returned_powder_exp=self.expected_returned_powder_exp + other.expected_returned_powder_exp,
            net_base_material_exp=self.net_base_material_exp + other.net_base_material_exp,
            expected_effective_exp=self.expected_effective_exp + other.expected_effective_exp,
            powder_gold=self.powder_gold + other.powder_gold,
            lower_stone_gold=self.lower_stone_gold + other.lower_stone_gold,
        )


@dataclass(frozen=True)
class ResourceRates:
    stamina_unit: float
    gold_per_unit: float
    enhance_exp_per_unit: float

    @property
    def gold_per_stamina(self) -> float:
        return self.gold_per_unit / self.stamina_unit

    @property
    def enhance_exp_per_stamina(self) -> float:
        return self.enhance_exp_per_unit / self.stamina_unit

    @property
    def expected_enhance_exp_per_unit(self) -> float:
        return self.enhance_exp_per_unit * EXPECTED_ENHANCE_EXP_MULTIPLIER

    @property
    def expected_enhance_exp_per_stamina(self) -> float:
        return self.expected_enhance_exp_per_unit / self.stamina_unit

    def stamina_components(self, amount: ResourceAmount, material_scarcity: float = 1.0) -> dict[str, float]:
        return {
            "gold": amount.gold / self.gold_per_stamina if self.gold_per_stamina else 0.0,
            # Material costs are stored in pre-bonus powder experience. The bonus
            # has already reduced powder units before this conversion.
            "enhance_exp": (
                amount.enhance_exp / self.enhance_exp_per_stamina * material_scarcity
                if self.enhance_exp_per_stamina
                else 0.0
            ),
        }

    def stamina_equivalent(self, amount: ResourceAmount, material_scarcity: float = 1.0) -> float:
        components = self.stamina_components(amount, material_scarcity)
        return max(components.values())

    def bottleneck(self, amount: ResourceAmount) -> str:
        components = self.stamina_components(amount)
        if abs(components["gold"] - components["enhance_exp"]) < 0.05:
            return "balanced"
        return "gold" if components["gold"] > components["enhance_exp"] else "enhance_exp"


@dataclass(frozen=True)
class ResourceCalibration:
    rank: str
    gear_stamina_by_source: dict[str, float]
    default_gear_source: str | None
    rates: ResourceRates
    interval_costs: dict[int, ResourceAmount]
    interval_material_costs: dict[int, MaterialCost]
    sell_recovery: dict[int, ResourceAmount]

    def gear_stamina(self, source: str | None = None) -> float | None:
        key = source or self.default_gear_source
        if key is None:
            return None
        source_meta = GEAR_SOURCES.get(key)
        if source_meta is not None:
            gross = source_meta.gross_gear_stamina_by_rank.get(self.rank)
            if gross is not None:
                expected_clears = gross / source_meta.stamina_per_clear if source_meta.stamina_per_clear else 0.0
                return gross - source_meta.lower_stone_stamina_credit(self.rates, expected_clears)
        return self.gear_stamina_by_source.get(key)


@dataclass(frozen=True)
class GearSource:
    source_id: str
    display_name: str
    source_type: str
    stamina_per_clear: float | None
    gross_gear_stamina_by_rank: dict[str, float]
    acquisition_status: str
    gear_acquisition_includes_pet_gear: bool
    extra_lower_stone_probability: float = 0.0
    source_gold_per_clear: float = 0.0
    mapping_status: str = "confirmed"

    @property
    def expected_lower_stone_base_exp_per_clear(self) -> float:
        return self.extra_lower_stone_probability * LOWER_ENHANCE_STONE_EXP

    def lower_stone_stamina_credit(self, rates: ResourceRates, expected_clears: float = 1.0) -> float:
        """Credit source stones once; their enhancement gold remains a material cost.

        A source drop replaces only the lower-stone experience side of the
        50/50 material batch.  Its 14,400 gold use cost is still paid when the
        stone is consumed and therefore stays in node material accounting.
        """
        if self.extra_lower_stone_probability <= 0:
            return 0.0
        stone_material = ResourceAmount(enhance_exp=LOWER_ENHANCE_STONE_EXP)
        expected_stones = expected_clears * self.extra_lower_stone_probability
        return expected_stones * rates.stamina_equivalent(stone_material)


def material_cost_for_level(nominal_exp: float) -> MaterialCost:
    # The material pool is mixed by base experience contribution: half powder,
    # half lower stones.  Node accounting remains on the 100-exp grid; stone
    # quantities are expected fractional units and reconcile in the long run.
    gross = ceil(nominal_exp / (POWDER_EXP * EXPECTED_ENHANCE_EXP_MULTIPLIER)) * POWDER_EXP
    powder_base_exp = gross / 2
    lower_stone_base_exp = gross / 2
    powder_units = powder_base_exp / POWDER_EXP
    lower_stone_units = lower_stone_base_exp / LOWER_ENHANCE_STONE_EXP
    expected_return = 0.0
    for probability, multiplier in ENHANCE_EXP_OUTCOMES:
        overflow = max(0.0, gross * multiplier - nominal_exp)
        expected_return += probability * floor(overflow / POWDER_EXP) * POWDER_EXP
    return MaterialCost(
        nominal_exp=float(nominal_exp),
        powder_units=powder_units,
        lower_stone_units=lower_stone_units,
        powder_base_exp=powder_base_exp,
        lower_stone_base_exp=lower_stone_base_exp,
        gross_base_material_exp=float(gross),
        expected_returned_powder_exp=expected_return,
        net_base_material_exp=gross - expected_return,
        expected_effective_exp=gross * EXPECTED_ENHANCE_EXP_MULTIPLIER,
        powder_gold=float(powder_units * POWDER_GOLD),
        lower_stone_gold=float(lower_stone_units * LOWER_ENHANCE_STONE_USE_GOLD),
    )


def interval_material_costs(level_exp: dict[int, int]) -> dict[int, MaterialCost]:
    result: dict[int, MaterialCost] = {}
    lower = 0
    for checkpoint in CHECKPOINTS:
        if checkpoint == 0:
            continue
        total = MaterialCost(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        for level in range(lower + 1, checkpoint + 1):
            total += material_cost_for_level(level_exp[level])
        result[checkpoint] = total
        lower = checkpoint
    return result


def _resource_amounts(costs: dict[int, MaterialCost]) -> dict[int, ResourceAmount]:
    return {checkpoint: cost.resource_amount for checkpoint, cost in costs.items()}


RED_INTERVAL_MATERIAL_COSTS = interval_material_costs(RED_LEVEL_EXP)
PURPLE_INTERVAL_MATERIAL_COSTS = interval_material_costs(PURPLE_LEVEL_EXP)

COMMON_RATES = ResourceRates(stamina_unit=8, gold_per_unit=58889.177, enhance_exp_per_unit=1161.1)

# Legacy IDs remain supported below, but only sources with documented activity
# mapping receive pet lower-stone credits. Their acquisition figures already
# include the pet's extra equipment drop.
GEAR_SOURCES: dict[str, GearSource] = {
    "riftslash_20_buff": GearSource(
        source_id="riftslash_20_buff",
        display_name="维度裂缝（一刀，Buff）",
        source_type="dimension_rift",
        stamina_per_clear=40,
        gross_gear_stamina_by_rank={"Epic": 85.0, "Heroic": 23.81},
        acquisition_status="Epic: confirmed; Heroic: estimated",
        gear_acquisition_includes_pet_gear=True,
        extra_lower_stone_probability=0.20,
        source_gold_per_clear=60000,
    ),
    "hunt_buff_craft_heroic": GearSource(
        source_id="hunt_buff_craft_heroic",
        display_name="讨伐 Buff 打铁",
        source_type="hunt",
        stamina_per_clear=20,
        gross_gear_stamina_by_rank={"Heroic": 65.69},
        acquisition_status="estimated",
        gear_acquisition_includes_pet_gear=True,
        extra_lower_stone_probability=0.11,
    ),
    "rift_collapse": GearSource(
        source_id="rift_collapse",
        display_name="异界之隙",
        source_type="rift_collapse",
        stamina_per_clear=160,
        gross_gear_stamina_by_rank={},
        acquisition_status="source-only; gear acquisition unconfirmed",
        gear_acquisition_includes_pet_gear=True,
        extra_lower_stone_probability=0.11,
    ),
}

LEGACY_GEAR_SOURCE_IDS = (
    "rift_new_1_32",
    "rift_hunt_1_32",
    "rift_new_1_10",
    "rift_hunt_1_10",
    "rift_new",
    "rift_hunt",
    "riftslash",
    "side_story_100_hunt_buff",
    "hunt_100_buff",
    "side_story_50_hunt_buff",
    "hunt_50_buff",
    "side_story_hunt_buff",
    "hunt_no_buff",
)

RED_EPIC_CALIBRATION = ResourceCalibration(
    rank="Epic",
    gear_stamina_by_source={
        "rift_new_1_32": 13.64,
        "rift_hunt_1_32": 23.44,
        "rift_new_1_10": 25.37,
        "rift_hunt_1_10": 37.71,
        "rift_new": 41.67,
        "rift_hunt": 50.2,
        "riftslash_20_buff": 85.0,
        "riftslash": 93.6,
        "side_story_100_hunt_buff": 103.08,
        "hunt_100_buff": 117.46,
        "side_story_50_hunt_buff": 123.67,
        "hunt_50_buff": 144.97,
        "side_story_hunt_buff": 154.54,
        "hunt_no_buff": 189.29,
    },
    default_gear_source="riftslash_20_buff",
    rates=COMMON_RATES,
    interval_costs=_resource_amounts(RED_INTERVAL_MATERIAL_COSTS),
    interval_material_costs=RED_INTERVAL_MATERIAL_COSTS,
    sell_recovery={
        0: ResourceAmount(),
        3: ResourceAmount(gold=25525, enhance_exp=1300),
        6: ResourceAmount(gold=25525, enhance_exp=3700),
        9: ResourceAmount(gold=25525, enhance_exp=11300),
        12: ResourceAmount(gold=25525, enhance_exp=18900),
        15: ResourceAmount(gold=25525, enhance_exp=39700),
    },
)

PURPLE_HEROIC_CALIBRATION = ResourceCalibration(
    rank="Heroic",
    gear_stamina_by_source={},
    default_gear_source=None,
    rates=COMMON_RATES,
    interval_costs=_resource_amounts(PURPLE_INTERVAL_MATERIAL_COSTS),
    interval_material_costs=PURPLE_INTERVAL_MATERIAL_COSTS,
    sell_recovery={
        0: ResourceAmount(),
        3: ResourceAmount(gold=15315, enhance_exp=1300),
        6: ResourceAmount(gold=15315, enhance_exp=3400),
        9: ResourceAmount(gold=15315, enhance_exp=8300),
        12: ResourceAmount(gold=15315, enhance_exp=17100),
        15: ResourceAmount(gold=15315, enhance_exp=40800),
    },
)


def calibration_for_rank(rank: str) -> ResourceCalibration:
    if rank == "Epic":
        return RED_EPIC_CALIBRATION
    if rank == "Heroic":
        return PURPLE_HEROIC_CALIBRATION
    raise ValueError(f"unsupported resource calibration rank: {rank}")


def cumulative_cost(calibration: ResourceCalibration, enhance: int) -> ResourceAmount:
    total = ResourceAmount()
    for checkpoint in CHECKPOINTS:
        if checkpoint == 0:
            continue
        if checkpoint > enhance:
            break
        total += calibration.interval_costs[checkpoint]
    return total


def cumulative_material_cost(calibration: ResourceCalibration, enhance: int) -> MaterialCost:
    total = MaterialCost(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    for checkpoint in CHECKPOINTS:
        if checkpoint == 0:
            continue
        if checkpoint > enhance:
            break
        total += calibration.interval_material_costs[checkpoint]
    return total


def conversion_stamina_cost(
    gold_cost: float = DEFAULT_CONVERSION_GOLD_COST,
    calibration: ResourceCalibration = RED_EPIC_CALIBRATION,
) -> float:
    return calibration.rates.stamina_equivalent(ResourceAmount(gold=gold_cost))


def material_pool_for_slot(slot: str | None) -> tuple[str, float]:
    if slot in {"neck", "ring"}:
        return "accessory", 1.3
    return "common", 1.0


def marginal_material_stamina_cost(current_checkpoint: int, next_checkpoint: int, rank: str, slot: str | None) -> float:
    calibration = calibration_for_rank(rank)
    if next_checkpoint not in calibration.interval_costs:
        raise ValueError(f"unsupported enhancement checkpoint: {next_checkpoint}")
    _pool, scarcity = material_pool_for_slot(slot)
    return calibration.rates.stamina_equivalent(calibration.interval_costs[next_checkpoint], scarcity)


def gear_source_metadata(source_id: str, calibration: ResourceCalibration | None = None) -> dict[str, Any]:
    source = GEAR_SOURCES.get(source_id)
    if source is None:
        source = GearSource(
            source_id=source_id,
            display_name=f"历史来源 ID：{source_id}",
            source_type="legacy_unverified",
            stamina_per_clear=None,
            gross_gear_stamina_by_rank={},
            acquisition_status="legacy value retained; mapping unconfirmed",
            gear_acquisition_includes_pet_gear=True,
            mapping_status="unconfirmed",
        )
    rates = (calibration or RED_EPIC_CALIBRATION).rates
    by_rank = {}
    for rank, gross in source.gross_gear_stamina_by_rank.items():
        expected_clears = gross / source.stamina_per_clear if source.stamina_per_clear else 0.0
        expected_stones = expected_clears * source.extra_lower_stone_probability
        credit = source.lower_stone_stamina_credit(rates, expected_clears)
        by_rank[rank] = {
            "gross_gear_acquisition_stamina": round1(gross),
            "expected_clears": expected_clears,
            "expected_lower_stone_units": expected_stones,
            "pet_lower_stone_stamina_credit": round1(credit),
            "net_gear_acquisition_stamina": round1(gross - credit),
        }
    return {
        "source_id": source.source_id,
        "display_name": source.display_name,
        "source_type": source.source_type,
        "mapping_status": source.mapping_status,
        "stamina_per_clear": source.stamina_per_clear,
        "acquisition_status": source.acquisition_status,
        "gear_acquisition_includes_pet_gear": source.gear_acquisition_includes_pet_gear,
        "extra_lower_stone_probability": source.extra_lower_stone_probability,
        "source_gold_per_clear": source.source_gold_per_clear,
        "expected_lower_stones_per_clear": source.extra_lower_stone_probability,
        "expected_lower_stone_base_exp_per_clear": source.expected_lower_stone_base_exp_per_clear,
        "expected_lower_stones_for_100_clears": source.extra_lower_stone_probability * 100,
        "expected_lower_stone_base_exp_for_100_clears": source.expected_lower_stone_base_exp_per_clear * 100,
        "lower_stone_base_exp": LOWER_ENHANCE_STONE_EXP,
        "lower_stone_use_gold": LOWER_ENHANCE_STONE_USE_GOLD,
        "pet_stone_accounting": "acquisition_only",
        "per_rank_acquisition_scope": "conditional_reference_only_not_for_joint_batch_denominator",
        "lower_stone_use_gold_accounting": "preserved_in_enhancement_material_cost",
        "by_rank": by_rank,
    }


def joint_source_batch_metadata(
    source_id: str,
    anchor_rank: str = "Epic",
    calibration: ResourceCalibration | None = None,
) -> dict[str, Any]:
    """Return one shared-source batch for multi-rank research.

    Per-rank source costs are conditional views.  A joint batch pays the
    source stamina and its lower-stone credit once, then reports expected
    output counts for all ranks from the same clears.
    """
    source = GEAR_SOURCES.get(source_id)
    if source is None or source.stamina_per_clear is None:
        raise ValueError(f"joint source batch is unavailable for {source_id}")
    gross = source.gross_gear_stamina_by_rank.get(anchor_rank)
    if gross is None:
        raise ValueError(f"joint source batch anchor rank is unavailable: {source_id}/{anchor_rank}")
    rates = (calibration or RED_EPIC_CALIBRATION).rates
    expected_clears = gross / source.stamina_per_clear
    expected_stones = expected_clears * source.extra_lower_stone_probability
    expected_source_gold = expected_clears * source.source_gold_per_clear
    credit = source.lower_stone_stamina_credit(rates, expected_clears)
    expected_output = {
        rank: gross / rank_gross
        for rank, rank_gross in source.gross_gear_stamina_by_rank.items()
        if rank_gross > 0
    }
    return {
        "source_id": source_id,
        "display_name": source.display_name,
        "anchor_rank": anchor_rank,
        "gross_batch_acquisition_stamina": gross,
        "net_batch_acquisition_stamina": gross - credit,
        "expected_clears": expected_clears,
        "expected_lower_stone_units": expected_stones,
        "source_gold_per_clear": source.source_gold_per_clear,
        "expected_source_gold_per_batch": expected_source_gold,
        "source_gold_accounting": "once_per_joint_batch_resource_pool",
        "lower_stone_credit_stamina": credit,
        "lower_stone_use_gold": LOWER_ENHANCE_STONE_USE_GOLD,
        "lower_stone_use_gold_accounting": "preserved_in_enhancement_material_cost",
        "source_pet_gear_included": source.gear_acquisition_includes_pet_gear,
        "expected_output_by_rank": expected_output,
        "heroic_output_status": "estimated" if "Heroic" in expected_output else "not_available",
        "source_credit_accounting": "once_per_joint_batch",
    }


def resource_snapshot(
    enhance: int,
    calibration: ResourceCalibration = RED_EPIC_CALIBRATION,
    gear_source: str | None = None,
    slot: str | None = None,
) -> dict[str, Any]:
    if enhance not in CHECKPOINTS:
        raise ValueError(f"enhance must be one of {CHECKPOINTS}")

    acquisition_stamina = calibration.gear_stamina(gear_source)
    material = cumulative_material_cost(calibration, enhance)
    consumed = material.resource_amount
    recovery = calibration.sell_recovery.get(enhance, ResourceAmount())
    net = consumed - recovery
    material_pool, material_scarcity = material_pool_for_slot(slot)
    components = calibration.rates.stamina_components(net, material_scarcity)
    upgrade_stamina = calibration.rates.stamina_equivalent(net, material_scarcity)
    total_stamina = None if acquisition_stamina is None else acquisition_stamina + upgrade_stamina

    next_checkpoint = next((value for value in CHECKPOINTS if value > enhance), None)
    marginal_next = None
    if next_checkpoint is not None:
        next_consumed = cumulative_cost(calibration, next_checkpoint)
        next_recovery = calibration.sell_recovery.get(next_checkpoint, ResourceAmount())
        marginal = (next_consumed - next_recovery) - net
        marginal_next = {
            "to": next_checkpoint,
            "net_gold": round1(marginal.gold),
            "net_enhance_exp": round1(marginal.enhance_exp),
            "stamina_equivalent": round1(calibration.rates.stamina_equivalent(marginal, material_scarcity)),
            "bottleneck": calibration.rates.bottleneck(marginal),
        }

    return {
        "enhance": enhance,
        "material_pool": material_pool,
        "material_scarcity_coefficient": material_scarcity,
        "material_mix_base_exp_ratio": {"powder": 0.5, "lower_stone": 0.5},
        "base_exp_granularity": POWDER_EXP,
        "expected_enhance_exp_multiplier": EXPECTED_ENHANCE_EXP_MULTIPLIER,
        "gear_source_metadata": gear_source_metadata(gear_source or calibration.default_gear_source or "unconfirmed", calibration),
        "acquisition_status": "confirmed" if acquisition_stamina is not None else "unconfirmed",
        "gear_acquisition_stamina": round1(acquisition_stamina) if acquisition_stamina is not None else None,
        "nominal_enhance_exp": round1(material.nominal_exp),
        "powder_units": material.powder_units,
        "lower_stone_units": material.lower_stone_units,
        "expected_input_base_exp": round1(material.expected_input_base_exp),
        "powder_base_exp": round1(material.powder_base_exp),
        "lower_stone_base_exp": round1(material.lower_stone_base_exp),
        "gross_base_material_exp": round1(material.gross_base_material_exp),
        "expected_returned_powder_exp": round1(material.expected_returned_powder_exp),
        "expected_effective_exp": round1(material.expected_effective_exp),
        "powder_gold": round1(material.powder_gold),
        "lower_stone_gold": round1(material.lower_stone_gold),
        "consumed_gold": round1(consumed.gold),
        "consumed_enhance_exp": round1(consumed.enhance_exp),
        "sell_recovered_gold": round1(recovery.gold),
        "sell_recovered_enhance_exp": round1(recovery.enhance_exp),
        "net_gold": round1(net.gold),
        "net_enhance_exp": round1(net.enhance_exp),
        "gold_stamina_equivalent": round1(components["gold"]),
        "enhance_exp_stamina_equivalent": round1(components["enhance_exp"]),
        "upgrade_stamina_equivalent": round1(upgrade_stamina),
        "total_stamina_equivalent": round1(total_stamina) if total_stamina is not None else None,
        "bottleneck": calibration.rates.bottleneck(net),
        "marginal_next": marginal_next,
    }


def red_epic_resource_table(gear_source: str | None = None) -> dict[str, Any]:
    calibration = RED_EPIC_CALIBRATION
    selected_source = gear_source or calibration.default_gear_source
    return {
        "rank": calibration.rank,
        "gear_source": selected_source,
        "gear_source_metadata": gear_source_metadata(selected_source or "unconfirmed", calibration),
        "rates": {
            "gold_per_8_stamina": calibration.rates.gold_per_unit,
            "base_enhance_exp_per_8_stamina": calibration.rates.enhance_exp_per_unit,
            "expected_enhance_exp_per_8_stamina": calibration.rates.expected_enhance_exp_per_unit,
            "expected_enhance_exp_multiplier": EXPECTED_ENHANCE_EXP_MULTIPLIER,
            "gold_per_stamina": round1(calibration.rates.gold_per_stamina),
            "enhance_exp_per_stamina": round1(calibration.rates.enhance_exp_per_stamina),
        },
        "checkpoints": [resource_snapshot(value, calibration, selected_source) for value in CHECKPOINTS],
        "gear_stamina_options": calibration.gear_stamina_by_source,
        "conversion_gold_cost": DEFAULT_CONVERSION_GOLD_COST,
        "conversion_stamina_cost": round1(conversion_stamina_cost(calibration=calibration)),
    }


def render_resource_table(table: dict[str, Any]) -> str:
    rates = table["rates"]
    source = table["gear_source_metadata"]
    lines = [
        f"资源模型：红装 / {table['rank']}",
        f"红装获取来源：{table['gear_source']}",
        f"来源映射：{source['display_name']} / {source['source_type']} / {source['mapping_status']}",
        f"单次体力：{source['stamina_per_clear']}；宠物装备已含：{source['gear_acquisition_includes_pet_gear']}",
        f"额外下级强化石：概率 {source['extra_lower_stone_probability']}，期望 {source['expected_lower_stones_per_clear']} 个/次，{source['expected_lower_stone_base_exp_per_clear']} 基础经验/次；使用金币 {source['lower_stone_use_gold']}",
        f"资源产出：{rates['gold_per_8_stamina']} 金币/8体力，{rates['base_enhance_exp_per_8_stamina']} 基础强化经验/8体力，{rates['expected_enhance_exp_per_8_stamina']} 期望强化经验/8体力",
        f"期望强化经验倍率：{rates['expected_enhance_exp_multiplier']}",
        f"转换成本：{table['conversion_gold_cost']} 金币（{table['conversion_stamina_cost']} 体力等价）",
        "",
        "| 节点 | 标称经验 | 粉末数 | 下级石数 | 粉/石基础经验 | 粉/石金币 | 返还粉末经验 | 净材料经验 | 净金币 | 瓶颈 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in table["checkpoints"]:
        lines.append(
            f"| +{item['enhance']} | {item['nominal_enhance_exp']} | {item['powder_units']} | {item['lower_stone_units']} | "
            f"{item['powder_base_exp']} / {item['lower_stone_base_exp']} | {item['powder_gold']} / {item['lower_stone_gold']} | "
            f"{item['expected_returned_powder_exp']} | {item['net_enhance_exp']} | {item['net_gold']} | {item['bottleneck']} |"
        )
    return "\n".join(lines)
