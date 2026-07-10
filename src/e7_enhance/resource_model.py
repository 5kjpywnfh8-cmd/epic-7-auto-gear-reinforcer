from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import round1


CHECKPOINTS = (0, 3, 6, 9, 12, 15)


@dataclass(frozen=True)
class ResourceAmount:
    gold: float = 0
    enhance_exp: float = 0

    def __add__(self, other: "ResourceAmount") -> "ResourceAmount":
        return ResourceAmount(
            gold=self.gold + other.gold,
            enhance_exp=self.enhance_exp + other.enhance_exp,
        )

    def __sub__(self, other: "ResourceAmount") -> "ResourceAmount":
        return ResourceAmount(
            gold=self.gold - other.gold,
            enhance_exp=self.enhance_exp - other.enhance_exp,
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

    def stamina_equivalent(self, amount: ResourceAmount) -> float:
        gold_stamina = amount.gold / self.gold_per_stamina if self.gold_per_stamina else 0
        exp_stamina = amount.enhance_exp / self.enhance_exp_per_stamina if self.enhance_exp_per_stamina else 0
        return max(gold_stamina, exp_stamina)

    def bottleneck(self, amount: ResourceAmount) -> str:
        gold_stamina = amount.gold / self.gold_per_stamina if self.gold_per_stamina else 0
        exp_stamina = amount.enhance_exp / self.enhance_exp_per_stamina if self.enhance_exp_per_stamina else 0
        if abs(gold_stamina - exp_stamina) < 0.05:
            return "balanced"
        return "gold" if gold_stamina > exp_stamina else "enhance_exp"


@dataclass(frozen=True)
class ResourceCalibration:
    rank: str
    gear_stamina_by_source: dict[str, float]
    default_gear_source: str
    rates: ResourceRates
    interval_costs: dict[int, ResourceAmount]
    sell_recovery: dict[int, ResourceAmount]

    def gear_stamina(self, source: str | None = None) -> float:
        key = source or self.default_gear_source
        if key not in self.gear_stamina_by_source:
            available = ", ".join(sorted(self.gear_stamina_by_source))
            raise KeyError(f"unknown gear stamina source: {key}; available: {available}")
        return self.gear_stamina_by_source[key]


RED_EPIC_CALIBRATION = ResourceCalibration(
    rank="Epic",
    gear_stamina_by_source={
        "rift_new_1_32": 13.64,
        "rift_hunt_1_32": 23.44,
        "rift_new_1_10": 25.37,
        "rift_hunt_1_10": 37.71,
        "rift_new": 41.67,
        "rift_hunt": 50.2,
        "riftslash_20_buff": 85.08,
        "riftslash": 93.6,
        "side_story_100_hunt_buff": 103.08,
        "hunt_100_buff": 117.46,
        "side_story_50_hunt_buff": 123.67,
        "hunt_50_buff": 144.97,
        "side_story_hunt_buff": 154.54,
        "hunt_no_buff": 189.29,
    },
    default_gear_source="rift_new_1_32",
    rates=ResourceRates(
        stamina_unit=8,
        gold_per_unit=11450 + 1000 + 60000,
        enhance_exp_per_unit=200,
    ),
    interval_costs={
        3: ResourceAmount(gold=17600, enhance_exp=1982 - 13),
        6: ResourceAmount(gold=46400, enhance_exp=4780 - 68 + 13),
        9: ResourceAmount(gold=92800, enhance_exp=10960),
        12: ResourceAmount(gold=180800, enhance_exp=21571),
        15: ResourceAmount(gold=356000, enhance_exp=42792),
    },
    sell_recovery={
        0: ResourceAmount(gold=0, enhance_exp=0),
        3: ResourceAmount(gold=25525, enhance_exp=1300),
        6: ResourceAmount(gold=25525, enhance_exp=3700),
        9: ResourceAmount(gold=25525, enhance_exp=11300),
        12: ResourceAmount(gold=25525, enhance_exp=18900),
        15: ResourceAmount(gold=25525, enhance_exp=39700),
    },
)


def cumulative_cost(calibration: ResourceCalibration, enhance: int) -> ResourceAmount:
    total = ResourceAmount()
    for checkpoint in CHECKPOINTS:
        if checkpoint == 0:
            continue
        if checkpoint > enhance:
            break
        total += calibration.interval_costs[checkpoint]
    return total


def resource_snapshot(
    enhance: int,
    calibration: ResourceCalibration = RED_EPIC_CALIBRATION,
    gear_source: str | None = None,
) -> dict[str, Any]:
    if enhance not in CHECKPOINTS:
        raise ValueError(f"enhance must be one of {CHECKPOINTS}")

    acquisition_stamina = calibration.gear_stamina(gear_source)
    consumed = cumulative_cost(calibration, enhance)
    recovery = calibration.sell_recovery.get(enhance, ResourceAmount())
    net = consumed - recovery
    upgrade_stamina = calibration.rates.stamina_equivalent(net)
    total_stamina = acquisition_stamina + upgrade_stamina

    next_checkpoint = next((value for value in CHECKPOINTS if value > enhance), None)
    marginal_next = None
    if next_checkpoint is not None:
        next_consumed = cumulative_cost(calibration, next_checkpoint)
        next_recovery = calibration.sell_recovery.get(next_checkpoint, ResourceAmount())
        next_net = next_consumed - next_recovery
        marginal = next_net - net
        marginal_next = {
            "to": next_checkpoint,
            "net_gold": round1(marginal.gold),
            "net_enhance_exp": round1(marginal.enhance_exp),
            "stamina_equivalent": round1(calibration.rates.stamina_equivalent(marginal)),
            "bottleneck": calibration.rates.bottleneck(marginal),
        }

    return {
        "enhance": enhance,
        "gear_acquisition_stamina": round1(acquisition_stamina),
        "consumed_gold": round1(consumed.gold),
        "consumed_enhance_exp": round1(consumed.enhance_exp),
        "sell_recovered_gold": round1(recovery.gold),
        "sell_recovered_enhance_exp": round1(recovery.enhance_exp),
        "net_gold": round1(net.gold),
        "net_enhance_exp": round1(net.enhance_exp),
        "upgrade_stamina_equivalent": round1(upgrade_stamina),
        "total_stamina_equivalent": round1(total_stamina),
        "bottleneck": calibration.rates.bottleneck(net),
        "marginal_next": marginal_next,
    }


def red_epic_resource_table(gear_source: str | None = None) -> dict[str, Any]:
    calibration = RED_EPIC_CALIBRATION
    return {
        "rank": calibration.rank,
        "gear_source": gear_source or calibration.default_gear_source,
        "rates": {
            "gold_per_8_stamina": calibration.rates.gold_per_unit,
            "enhance_exp_per_8_stamina": calibration.rates.enhance_exp_per_unit,
            "gold_per_stamina": round1(calibration.rates.gold_per_stamina),
            "enhance_exp_per_stamina": round1(calibration.rates.enhance_exp_per_stamina),
        },
        "checkpoints": [resource_snapshot(value, calibration, gear_source) for value in CHECKPOINTS],
        "gear_stamina_options": calibration.gear_stamina_by_source,
    }


def render_resource_table(table: dict[str, Any]) -> str:
    lines = [
        f"资源模型：红装 / {table['rank']}",
        f"红装获取来源：{table['gear_source']}",
        (
            "资源产出："
            f"{table['rates']['gold_per_8_stamina']} 金币/8体力，"
            f"{table['rates']['enhance_exp_per_8_stamina']} 强化经验/8体力"
        ),
        "",
        "| 节点 | 总体力等价 | 强化净体力 | 瓶颈 | 净金币 | 净强化经验 | 继续到下一节点边际体力 |",
        "|---:|---:|---:|---|---:|---:|---:|",
    ]
    for item in table["checkpoints"]:
        marginal = item.get("marginal_next")
        marginal_text = "-" if marginal is None else f"+{marginal['to']}：{marginal['stamina_equivalent']}"
        lines.append(
            f"| +{item['enhance']} | "
            f"{item['total_stamina_equivalent']} | "
            f"{item['upgrade_stamina_equivalent']} | "
            f"{item['bottleneck']} | "
            f"{item['net_gold']} | "
            f"{item['net_enhance_exp']} | "
            f"{marginal_text} |"
        )
    lines.extend(
        [
            "",
            "说明：总体力等价 = 获取红装体力 + 强化资源净体力。",
            "金币和强化经验由同一笔 8 体力共同产出，强化资源净体力按瓶颈资源折算；出售回收会抵扣已投入成本。",
        ]
    )
    return "\n".join(lines)
