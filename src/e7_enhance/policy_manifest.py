from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from .models import (
    ALLOWED_RANKS_BY_ITEM_SOURCE,
    MAIN_STAT_KEYS_BY_SLOT,
    SUPPORTED_ENHANCEMENT_CHECKPOINTS,
    SUPPORTED_EQUIPMENT_LEVELS,
    Gear,
    Stat,
)
from .rules import SET_CODE_TO_NAME
from .strategy_defaults import DEFAULT_GEAR_SOURCE, STRATEGY_VERSION, default_strategy_for


SCHEMA_VERSION = "e7_enhance.policy_manifest/1.0"
BEHAVIOR_INPUTS = (
    "src/e7_enhance/calibration.py",
    "src/e7_enhance/enhance_policy.py",
    "src/e7_enhance/lightweight_calibration_rules.json",
    "src/e7_enhance/models.py",
    "src/e7_enhance/modification_values.py",
    "src/e7_enhance/resource_model.py",
    "src/e7_enhance/rules.py",
    "src/e7_enhance/score_engine.py",
    "src/e7_enhance/strategy_defaults.py",
    "装备强化与评分规则审阅.md",
)


class PolicyManifestError(RuntimeError):
    pass


def build_policy_manifest(root: Path, generated_on: str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    behavior_inputs = _behavior_input_hashes(root)
    item_source_ranks = _item_source_rank_rows()
    decision_routes = _decision_routes(item_source_ranks)
    route_coverage_complete = _route_coverage_complete(item_source_ranks, decision_routes)
    unknown_set_fail_closed = _unknown_set_fail_closed()

    gaps: list[str] = []
    if not unknown_set_fail_closed:
        gaps.append("unknown_set_not_rejected_by_advise_gear")
    gaps.append("full_regression_matrix_evidence_not_attached")

    gates = {
        "behavior_inputs_hashed": len(behavior_inputs) == len(BEHAVIOR_INPUTS),
        "supported_scope_complete": item_source_ranks
        == [
            {"item_source": "normal_85", "rank": "Epic"},
            {"item_source": "normal_85", "rank": "Heroic"},
            {"item_source": "rift_85", "rank": "Epic"},
        ],
        "decision_route_coverage_complete": route_coverage_complete,
        "unknown_set_fail_closed": unknown_set_fail_closed,
        "full_regression_matrix_evidence_attached": False,
    }
    freeze_status = "ready" if all(gates.values()) else "not_ready"

    supported_inputs = {
        "item_source_ranks": item_source_ranks,
        "equipment_levels": sorted(SUPPORTED_EQUIPMENT_LEVELS),
        "enhancement_checkpoints": sorted(SUPPORTED_ENHANCEMENT_CHECKPOINTS),
        "slots": [
            {"slot": slot, "main_stats": sorted(main_stats)}
            for slot, main_stats in sorted(MAIN_STAT_KEYS_BY_SLOT.items())
        ],
        "sets": [
            {"code": code, "name": SET_CODE_TO_NAME[code]}
            for code in sorted(SET_CODE_TO_NAME)
        ],
        "default_gear_source": DEFAULT_GEAR_SOURCE,
        "unknown_input_contract": {
            "item_source": "reject",
            "rank_for_source": "reject",
            "equipment_level": "reject",
            "enhancement_checkpoint": "reject",
            "slot": "reject",
            "main_stat_for_slot": "reject",
            "substat": "reject",
            "set": "reject" if unknown_set_fail_closed else "not_rejected",
        },
    }
    core = {
        "schema_version": SCHEMA_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "freeze_status": freeze_status,
        "behavior_inputs": behavior_inputs,
        "supported_inputs": supported_inputs,
        "default_strategies": _default_strategy_rows(item_source_ranks),
        "decision_contract": {
            "entrypoint": "src.e7_enhance.enhance_policy.advise_gear",
            "summary_fields": ["recommendation", "next_check_at", "target_profile", "reasons"],
            "review_required_recommendations": ["cautious_continue", "uncertain"],
            "automation_boundary": "manifest_does_not_authorize_clicks_or_resource_consumption",
        },
        "decision_routes": decision_routes,
        "readiness": {"gates": gates, "gaps": gaps},
    }
    core_hash = _json_sha256(core)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": generated_on or date.today().isoformat(),
        "strategy_version": STRATEGY_VERSION,
        "manifest_sha256": core_hash,
        "freeze_status": freeze_status,
        "behavior_inputs": behavior_inputs,
        "supported_inputs": supported_inputs,
        "default_strategies": core["default_strategies"],
        "decision_contract": core["decision_contract"],
        "decision_routes": decision_routes,
        "readiness": core["readiness"],
    }


def write_policy_manifest(
    root: Path,
    *,
    json_path: Path,
    markdown_path: Path,
    generated_on: str | None = None,
) -> dict[str, Any]:
    manifest = build_policy_manifest(root, generated_on=generated_on)
    json_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    markdown_text = render_policy_manifest_markdown(manifest)
    _atomic_write(Path(json_path), json_text)
    _atomic_write(Path(markdown_path), markdown_text)
    return manifest


def render_policy_manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# 策略 V1 冻结清单与覆盖矩阵",
        "",
        f"- 生成日期：`{manifest['generated_on']}`",
        f"- 策略版本：`{manifest['strategy_version']}`",
        f"- 核心 manifest SHA-256：`{manifest['manifest_sha256']}`",
        f"- 冻结状态：`{manifest['freeze_status']}`",
        "- 本清单只读，不授权模拟器输入、自动点击或资源消耗。",
        "",
        "## 默认策略",
        "",
        "| 来源 | 品质 | 策略 | DP | 资源校准 |",
        "|---|---|---|---:|---|",
    ]
    for row in manifest["default_strategies"]:
        lines.append(
            f"| `{row['item_source']}` | `{row['rank']}` | `{row['policy_name']}` | "
            f"{'是' if row['enable_dp_assist'] else '否'} | `{row['resource_calibration_status']}` |"
        )
    lines.extend(
        [
            "",
            "## 决策路由",
            "",
            "| 来源 | 品质 | 节点 | 分段 | 所有者 |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in manifest["decision_routes"]:
        lines.append(
            f"| `{row['item_source']}` | `{row['rank']}` | +{row['checkpoint']} | "
            f"`{row['segment']}` | `{row['owner']}` |"
        )
    lines.extend(["", "## 冻结闸门", ""])
    for name, passed in manifest["readiness"]["gates"].items():
        lines.append(f"- `{name}`：`{'passed' if passed else 'failed'}`")
    lines.extend(["", "## 未满足项", ""])
    if manifest["readiness"]["gaps"]:
        lines.extend(f"- `{gap}`" for gap in manifest["readiness"]["gaps"])
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 行为输入",
            "",
            "| 文件 | 字节 | SHA-256 |",
            "|---|---:|---|",
        ]
    )
    for row in manifest["behavior_inputs"]:
        lines.append(f"| `{row['path']}` | {row['bytes']} | `{row['sha256']}` |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="导出策略 V1 冻结清单与覆盖矩阵")
    parser.add_argument("--root", type=Path, default=repository_root)
    parser.add_argument("--json", type=Path, default=repository_root / "reports" / "policy_v1_manifest_20260725.json")
    parser.add_argument("--markdown", type=Path, default=repository_root / "reports" / "policy_v1_manifest_20260725.md")
    parser.add_argument("--generated-on", default=date.today().isoformat())
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = write_policy_manifest(
            args.root,
            json_path=args.json,
            markdown_path=args.markdown,
            generated_on=args.generated_on,
        )
    except (OSError, PolicyManifestError, ValueError) as exc:
        parser.error(str(exc))
    print(args.json)
    print(args.markdown)
    print(f"freeze_status={manifest['freeze_status']}")
    print(f"manifest_sha256={manifest['manifest_sha256']}")
    return 2 if args.require_ready and manifest["freeze_status"] != "ready" else 0


def _behavior_input_hashes(root: Path) -> list[dict[str, Any]]:
    rows = []
    for relative_path in sorted(BEHAVIOR_INPUTS):
        path = root / relative_path
        if not path.is_file():
            raise PolicyManifestError(f"Missing behavior input: {relative_path}")
        content = path.read_bytes()
        rows.append(
            {
                "path": relative_path.replace("\\", "/"),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows


def _item_source_rank_rows() -> list[dict[str, str]]:
    return [
        {"item_source": item_source, "rank": rank}
        for item_source, ranks in sorted(ALLOWED_RANKS_BY_ITEM_SOURCE.items())
        for rank in sorted(ranks)
    ]


def _default_strategy_rows(item_source_ranks: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for scope in item_source_ranks:
        strategy = default_strategy_for(
            scope["item_source"],
            scope["rank"],
            DEFAULT_GEAR_SOURCE,
        )
        rows.append(
            {
                "item_source": scope["item_source"],
                "rank": scope["rank"],
                "gear_source": strategy.gear_source,
                "policy_name": strategy.policy_name,
                "enable_dp_assist": strategy.enable_dp_assist,
                "resource_calibration_status": strategy.resource_calibration_status,
            }
        )
    return rows


def _decision_routes(item_source_ranks: list[dict[str, str]]) -> list[dict[str, Any]]:
    routes = []
    for scope in item_source_ranks:
        item_source = scope["item_source"]
        rank = scope["rank"]
        for checkpoint in sorted(SUPPORTED_ENHANCEMENT_CHECKPOINTS):
            if checkpoint == 15:
                routes.append(_route(item_source, rank, checkpoint, "all", "terminal_summary"))
            elif checkpoint in (0, 3):
                routes.append(_route(item_source, rank, checkpoint, "all", "lightweight_prediction"))
            elif item_source == "normal_85" and rank == "Heroic":
                routes.append(_route(item_source, rank, checkpoint, "non_boot_with_speed", "heroic_speed22_rescue"))
                routes.append(_route(item_source, rank, checkpoint, "fallback", "baseline_policy"))
            else:
                routes.append(_route(item_source, rank, checkpoint, "all", "exact_dp"))
    return routes


def _route(item_source: str, rank: str, checkpoint: int, segment: str, owner: str) -> dict[str, Any]:
    return {
        "item_source": item_source,
        "rank": rank,
        "checkpoint": checkpoint,
        "segment": segment,
        "owner": owner,
        "output_contract": "summary.recommendation + summary.next_check_at",
    }


def _route_coverage_complete(item_source_ranks: list[dict[str, str]], routes: list[dict[str, Any]]) -> bool:
    route_keys = {
        (row["item_source"], row["rank"], row["checkpoint"], row["segment"])
        for row in routes
    }
    if len(route_keys) != len(routes):
        return False
    return all(
        any(
            row["item_source"] == scope["item_source"]
            and row["rank"] == scope["rank"]
            and row["checkpoint"] == checkpoint
            for row in routes
        )
        for scope in item_source_ranks
        for checkpoint in SUPPORTED_ENHANCEMENT_CHECKPOINTS
    )


def _unknown_set_fail_closed() -> bool:
    from .enhance_policy import advise_gear

    unknown_set_gear = Gear(
        set="set_policy_manifest_unknown",
        slot="weapon",
        main_stat=Stat("atkFlat", 500),
        enhance=15,
        level=85,
        rank="Epic",
        substats=[
            Stat("hpPct", 8),
            Stat("spd", 4),
            Stat("crit", 5),
            Stat("cdmg", 7),
        ],
    )
    try:
        advise_gear(unknown_set_gear, item_source="normal_85")
    except ValueError:
        return True
    return False


def _json_sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
