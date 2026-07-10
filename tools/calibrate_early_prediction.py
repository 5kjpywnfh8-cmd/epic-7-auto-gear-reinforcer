"""Compare the +0/+3 lightweight filter with the exact route solver.

This is intentionally offline-only. It uses deterministic generated gear and the
same level/source/rank combinations supported by the production advisor.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

from src.e7_enhance.calibration import dp_assisted_policies
from src.e7_enhance.enhance_policy import lightweight_prediction
from src.e7_enhance.enhance_simulator import SimulationOptions, enhance_to_checkpoint, generate_gear
from src.e7_enhance.route_solver import clear_route_cache, compute_optimal_route


CONFIGS = (("normal_85", "Epic"), ("normal_85", "Heroic"), ("rift_85", "Epic"))


def run(samples_per_checkpoint: int, seed: int) -> dict:
    rng = random.Random(seed)
    rows: list[dict] = []
    total_light_seconds = 0.0
    total_dp_seconds = 0.0
    clear_route_cache()
    for item_source, rank in CONFIGS:
        policy = dp_assisted_policies(item_source, rank)[0]
        for checkpoint in (0, 3):
            for _ in range(samples_per_checkpoint):
                gear = generate_gear(rng, SimulationOptions(item_source=item_source, rank=rank))
                if checkpoint:
                    gear, _ = enhance_to_checkpoint(gear, checkpoint, item_source, rng)
                started = time.perf_counter()
                light = lightweight_prediction(gear, item_source, "rift_new_1_32")
                total_light_seconds += time.perf_counter() - started
                started = time.perf_counter()
                exact = compute_optimal_route(
                    gear,
                    lambda_value=policy.dp_lambda_value or 0.0,
                    conversion_cost=policy.dp_conversion_cost,
                    item_source=item_source,
                    gear_source="rift_new_1_32",
                    rank=rank,
                )
                total_dp_seconds += time.perf_counter() - started
                rows.append(
                    {
                        "item_source": item_source,
                        "rank": rank,
                        "checkpoint": checkpoint,
                        "light_action": light["action"],
                        "exact_action": exact["action"],
                        "light_terminal_value": light["terminal_value"],
                        "expected_final_score": light["basis"]["expected_final_reforge_score"],
                        "expected_final_speed": light["basis"]["expected_final_speed"],
                        "speed_threshold_probability": light["basis"]["speed_threshold_probability"],
                        "formal_cross_tier_probability": light["basis"]["formal_cross_tier_probability"],
                    }
                )
    by_bucket: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['item_source']}:{row['rank']}:+{row['checkpoint']}"] .append(row)
    for key, bucket in sorted(grouped.items()):
        matrix = Counter(f"{item['light_action']}->{item['exact_action']}" for item in bucket)
        by_bucket[key] = {"samples": len(bucket), "decision_matrix": dict(sorted(matrix.items()))}
    high_speed_stops = [
        row for row in rows
        if row["light_action"] == "stop"
        and (row["expected_final_speed"] >= 14 or row["speed_threshold_probability"] >= 0.2)
    ]
    return {
        "scope": {"checkpoints": [0, 3], "configs": [list(config) for config in CONFIGS], "seed": seed, "samples_per_checkpoint": samples_per_checkpoint},
        "rule": {
            "review_when": "speed rolls >=2, expected speed >=14, 20-speed probability >=0.2, speed potential >=16, expected effective score >=48, formal cross-tier probability >=0.2",
            "stop_when": "none of the review signals is present",
        },
        "performance": {
            "samples": len(rows),
            "lightweight_total_seconds": round(total_light_seconds, 6),
            "exact_dp_total_seconds": round(total_dp_seconds, 6),
            "speedup": round(total_dp_seconds / total_light_seconds, 1) if total_light_seconds else None,
        },
        "by_bucket": by_bucket,
        "high_speed_direct_stop_count": len(high_speed_stops),
        "rows": rows,
    }


def render(report: dict) -> str:
    lines = [
        "# +0/+3 轻量预测校准报告",
        "",
        f"- 固定种子：{report['scope']['seed']}",
        f"- 每组合样本：{report['scope']['samples_per_checkpoint']}",
        f"- 总样本：{report['performance']['samples']}",
        f"- 轻量预测耗时：{report['performance']['lightweight_total_seconds']} 秒",
        f"- 精确 DP 耗时：{report['performance']['exact_dp_total_seconds']} 秒",
        f"- 耗时倍率：{report['performance']['speedup']}x",
        f"- 临界/高速度直接停止：{report['high_speed_direct_stop_count']}",
        "",
        "规则：" + report["rule"]["review_when"],
        "",
        "| 分层 | 样本 | 轻量 -> 精确 DP |",
        "|---|---:|---|",
    ]
    for key, value in report["by_bucket"].items():
        matrix = ", ".join(f"{name}={count}" for name, count in value["decision_matrix"].items()) or "-"
        lines.append(f"| {key} | {value['samples']} | {matrix} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--reports-dir", default="reports")
    args = parser.parse_args()
    report = run(args.samples, args.seed)
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "early-lightweight-calibration.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (reports_dir / "early-lightweight-calibration.md").write_text(render(report), encoding="utf-8")
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
