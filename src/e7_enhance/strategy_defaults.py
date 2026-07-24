from __future__ import annotations

from dataclasses import dataclass


STRATEGY_VERSION = "baili-formal-dp-v1-epic-balanced"
DEFAULT_GEAR_SOURCE = "riftslash_20_buff"


@dataclass(frozen=True)
class StrategyDefault:
    item_source: str
    rank: str
    gear_source: str
    policy_name: str
    enable_dp_assist: bool
    strategy_version: str = STRATEGY_VERSION
    resource_calibration_status: str = "published"


STRATEGY_DEFAULTS: dict[tuple[str, str, str], StrategyDefault] = {
    ("normal_85", "Epic", DEFAULT_GEAR_SOURCE): StrategyDefault(
        item_source="normal_85",
        rank="Epic",
        gear_source=DEFAULT_GEAR_SOURCE,
        policy_name="normal_epic_dp_assisted",
        enable_dp_assist=True,
    ),
    ("rift_85", "Epic", DEFAULT_GEAR_SOURCE): StrategyDefault(
        item_source="rift_85",
        rank="Epic",
        gear_source=DEFAULT_GEAR_SOURCE,
        policy_name="rift_epic_dp_assisted",
        enable_dp_assist=True,
    ),
}


def default_strategy_for(item_source: str, rank: str, gear_source: str = DEFAULT_GEAR_SOURCE) -> StrategyDefault:
    key = (item_source, rank, gear_source)
    if key in STRATEGY_DEFAULTS:
        return STRATEGY_DEFAULTS[key]
    fallback_key = (item_source, rank, DEFAULT_GEAR_SOURCE)
    if fallback_key in STRATEGY_DEFAULTS:
        fallback = STRATEGY_DEFAULTS[fallback_key]
        return StrategyDefault(
            item_source=fallback.item_source,
            rank=fallback.rank,
            gear_source=gear_source,
            policy_name=fallback.policy_name,
            enable_dp_assist=fallback.enable_dp_assist,
            resource_calibration_status=fallback.resource_calibration_status,
        )
    return StrategyDefault(
        item_source=item_source,
        rank=rank,
        gear_source=gear_source,
        policy_name="baili_marginal_low" if rank == "Heroic" else "category_baili_marginal_mid",
        enable_dp_assist=False,
        resource_calibration_status="unpublished" if (item_source, rank) == ("normal_85", "Heroic") else "not_required",
    )
