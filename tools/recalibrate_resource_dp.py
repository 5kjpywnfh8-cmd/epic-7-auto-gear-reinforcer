"""Recalculate DP resource constants with resumable independent random seeds."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
from typing import Any, Iterator

from src.e7_enhance.calibration import (
    CalibrationOptions,
    aggregate_resource_calibration_runs,
    calibrate_selected_policies,
    resource_calibration_publishable,
)
from src.e7_enhance.resource_model import GEAR_SOURCES


CONFIGS = {
    "normal_85_epic": ("normal_85 Epic", "normal_85", "Epic", "category_baili_marginal_mid"),
    "rift_85_epic": ("rift_85 Epic", "rift_85", "Epic", "score_target_high_speed_mid"),
    "normal_85_heroic": ("normal_85 Heroic", "normal_85", "Heroic", "baili_marginal_low"),
}


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parse_csv_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _parse_seeds(raw: str) -> list[int]:
    seeds = [int(value) for value in _parse_csv_values(raw)]
    if len(seeds) != len(set(seeds)):
        raise ValueError("重复 seed：同一批次中每个 seed 只能运行一次")
    return seeds


def _selected_configs(raw: str) -> list[tuple[str, str, str, str, str]]:
    keys = _parse_csv_values(raw)
    unknown = sorted(set(keys) - set(CONFIGS))
    if unknown:
        raise ValueError(f"未知配置：{', '.join(unknown)}")
    if not keys:
        raise ValueError("至少选择一个配置")
    return [(key, *CONFIGS[key]) for key in keys]


def _load_existing_rows(path: Path | None, config: tuple[str, str, str, str]) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    label, item_source, rank, policy_name = config
    for item in payload.get("configs", []):
        if (
            item.get("label") == label
            and item.get("item_source") == item_source
            and item.get("rank") == rank
            and item.get("policy_name") == policy_name
        ):
            return list(item.get("aggregate", {}).get("seed_results", []))
    return []


@contextmanager
def _temporary_heroic_gear_cost(gear_source: str, heroic_gear_stamina: float | None) -> Iterator[None]:
    if heroic_gear_stamina is None:
        yield
        return
    source = GEAR_SOURCES.get(gear_source)
    if source is None:
        raise ValueError(f"无法覆盖未确认来源的 Heroic 胚子成本：{gear_source}")
    prior = source
    gross_costs = dict(source.gross_gear_stamina_by_rank)
    gross_costs["Heroic"] = float(heroic_gear_stamina)
    GEAR_SOURCES[gear_source] = replace(source, gross_gear_stamina_by_rank=gross_costs)
    try:
        yield
    finally:
        GEAR_SOURCES[gear_source] = prior


def _config_payload(
    config: tuple[str, str, str, str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    label, item_source, rank, policy_name = config
    aggregate = aggregate_resource_calibration_runs(rows)
    return {
        "label": label,
        "item_source": item_source,
        "rank": rank,
        "policy_name": policy_name,
        "published": resource_calibration_publishable(aggregate, rank),
        "aggregate": aggregate,
    }


def _calibrate_seed_with_override(
    config: tuple[str, str, str, str],
    seed: int,
    runs_per_seed: int,
    gear_source: str,
    heroic_gear_stamina: float,
) -> dict[str, Any]:
    """Apply the override inside the process that performs the simulation."""
    _label, item_source, rank, policy_name = config
    with _temporary_heroic_gear_cost(gear_source, heroic_gear_stamina):
        result = calibrate_selected_policies(
            CalibrationOptions(
                runs=runs_per_seed,
                seed=seed,
                item_source=item_source,
                rank=rank,
                gear_source=gear_source,
                workers=1,
                top_limit=1,
                enable_dp_assist=False,
            ),
            [policy_name],
        )
    policy = result["policies"][0]
    return {
        "seed": seed,
        "runs": runs_per_seed,
        "total_stamina": policy["total_stamina"],
        "total_baili_score": policy["total_baili_score"],
        "successes": policy["nonzero_terminal_count"],
    }


def _payload(
    configs: list[tuple[str, str, str, str, str]],
    rows_by_key: dict[str, list[dict[str, Any]]],
    runs_per_seed: int,
    seeds: list[int],
    workers: int,
    gear_source: str,
    heroic_gear_stamina: float | None,
) -> dict[str, Any]:
    return {
        "scope": "50/50 base-exp material pool; merged numerator/denominator",
        "runs_per_seed": runs_per_seed,
        "requested_seeds": seeds,
        "workers": workers,
        "gear_source": gear_source,
        "heroic_gross_gear_stamina_override": heroic_gear_stamina,
        "configs": [_config_payload(config[1:], rows_by_key[config[0]]) for config in configs],
    }


def run_calibration(
    configs: list[tuple[str, str, str, str, str]],
    seeds: list[int],
    runs_per_seed: int,
    workers: int,
    gear_source: str,
    output: Path,
    resume_existing: Path | None = None,
    heroic_gear_stamina: float | None = None,
) -> dict[str, Any]:
    rows_by_key = {config[0]: _load_existing_rows(resume_existing, config[1:]) for config in configs}
    for key, *config in configs:
        existing_seeds = {int(row["seed"]) for row in rows_by_key[key]}
        duplicate = sorted(existing_seeds & set(seeds))
        if duplicate:
            raise ValueError(f"重复 seed：{config[0]} 已包含 {', '.join(str(seed) for seed in duplicate)}")

    if heroic_gear_stamina is not None:
        for key, label, item_source, rank, policy_name in configs:
            config = (label, item_source, rank, policy_name)
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        _calibrate_seed_with_override,
                        config,
                        seed,
                        runs_per_seed,
                        gear_source,
                        heroic_gear_stamina,
                    ): seed
                    for seed in seeds
                }
                for future in as_completed(futures):
                    rows_by_key[key].append(future.result())
                    rows_by_key[key].sort(key=lambda row: int(row["seed"]))
                    _atomic_write(output, _payload(configs, rows_by_key, runs_per_seed, seeds, workers, gear_source, heroic_gear_stamina))
    else:
        for key, label, item_source, rank, policy_name in configs:
            for seed in seeds:
                result = calibrate_selected_policies(
                    CalibrationOptions(
                        runs=runs_per_seed,
                        seed=seed,
                        item_source=item_source,
                        rank=rank,
                        gear_source=gear_source,
                        workers=workers,
                        top_limit=1,
                        enable_dp_assist=False,
                    ),
                    [policy_name],
                )
                policy = result["policies"][0]
                rows_by_key[key].append(
                    {
                        "seed": seed,
                        "runs": runs_per_seed,
                        "total_stamina": policy["total_stamina"],
                        "total_baili_score": policy["total_baili_score"],
                        "successes": policy["nonzero_terminal_count"],
                    }
                )
                # A completed seed is durable even when a later simulation fails.
                _atomic_write(output, _payload(configs, rows_by_key, runs_per_seed, seeds, workers, gear_source, heroic_gear_stamina))

    return _payload(configs, rows_by_key, runs_per_seed, seeds, workers, gear_source, heroic_gear_stamina)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-seed DP resource recalibration")
    parser.add_argument("--configs", default=",".join(CONFIGS))
    parser.add_argument("--runs-per-seed", type=int, default=10000)
    parser.add_argument("--seeds", default="20260711,20260712,20260713")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--gear-source", default="riftslash_20_buff")
    parser.add_argument("--heroic-gear-stamina", type=float)
    parser.add_argument("--resume-existing")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    resume_existing = Path(args.resume_existing) if args.resume_existing else None
    run_calibration(
        _selected_configs(args.configs),
        _parse_seeds(args.seeds),
        max(1, args.runs_per_seed),
        max(1, args.workers),
        args.gear_source,
        output,
        resume_existing,
        args.heroic_gear_stamina,
    )
    print(output)


if __name__ == "__main__":
    main()
