"""Frozen prospective collection protocol for the Epic balanced candidate.

This is deliberately an offline protocol.  It never changes the released
policy or writes manual labels; it only seals inputs and predictions before a
future independent review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import inspect
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.epic_non_speed_dp_oracle_audit import canonical_fingerprint
from tools.epic_non_speed_early_policy_pareto import (
    _gear_from_item,
    _speed_hard_route,
    strategies,
    strategy_actions,
)


BATCH_ID = "epic_b_balanced_prospective_20260713"
TARGET_COUNT = 48
FROZEN_CANDIDATES = ("A_current_review", "B_global_current_gs", "C_category_probability")
SOURCE_SCOPE = "normal_85 Epic +0/+3 non-speed"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _prediction_hash() -> str:
    selected = [strategy for strategy in strategies() if strategy.key in FROZEN_CANDIDATES]
    source = "\n".join(inspect.getsource(strategy.decide) for strategy in selected)
    source += "\n" + inspect.getsource(strategy_actions)
    return sha256(source.encode("utf-8")).hexdigest()


def _candidate_snapshot() -> dict[str, Any]:
    rows = []
    for strategy in strategies():
        if strategy.key in FROZEN_CANDIDATES:
            rows.append({"key": strategy.key, "label": strategy.label, "decide_source_sha256": sha256(inspect.getsource(strategy.decide).encode("utf-8")).hexdigest()})
    return {row["key"]: row for row in rows}


def _code_version() -> dict[str, str]:
    tracked = [
        ROOT / "tools" / "epic_non_speed_early_policy_pareto.py",
        ROOT / "tools" / "research_riftslash_saint_pool.py",
        ROOT / "tools" / "epic_balanced_prospective.py",
    ]
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    return {"git_head": revision, "tracked_source_sha256": sha256(b"".join(path.read_bytes() for path in tracked)).hexdigest()}


def create_batch(path: Path, *, frozen_at: str | None = None) -> dict[str, Any]:
    """Create the empty, blind batch once; an existing file is never reset."""
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    frozen_at = frozen_at or datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "batch_id": BATCH_ID,
        "status": "collecting_blind",
        "created_at": frozen_at,
        "scope": SOURCE_SCOPE,
        "progress": {"accepted": 0, "target": TARGET_COUNT},
        "frozen": {
            "candidates": _candidate_snapshot(),
            "prediction_function_sha256": _prediction_hash(),
            "code_version": _code_version(),
            "speed_hard_route_exclusion": "normal_85 Epic non-boot speed >=2 follows the released hard route and is not a prospective non-speed case",
            "resource_scope": "explicit riftslash/Saint joint resource pool; 85 stamina + one aggregate Saint bottleneck",
            "oracle": {"status": "pending_research_lambda", "manual_labels_visible": False},
        },
        "items": [],
        "exclusions": [],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def refresh_empty_freeze(path: Path, *, frozen_at: str | None = None) -> dict[str, Any]:
    """Finalize hashes only before the first import; populated batches are immutable."""
    path = Path(path)
    batch = json.loads(path.read_text(encoding="utf-8"))
    if batch.get("items"):
        raise ValueError("cannot refresh a populated prospective freeze")
    frozen_at = frozen_at or datetime.now().astimezone().isoformat(timespec="seconds")
    batch["created_at"] = frozen_at
    batch["frozen"]["candidates"] = _candidate_snapshot()
    batch["frozen"]["prediction_function_sha256"] = _prediction_hash()
    batch["frozen"]["code_version"] = _code_version()
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return batch


def identity_index(items: Iterable[dict[str, Any]]) -> dict[str, set[str]]:
    """Build a strict reference set using instance IDs first and state fingerprints."""
    ids: set[str] = set()
    fingerprints: set[str] = set()
    for item in items:
        try:
            gear = _gear_from_item(item)
        except (KeyError, TypeError, ValueError):
            continue
        instance_id = str(item.get("ingameId") or item.get("id") or item.get("instance_id") or "")
        if instance_id:
            ids.add(instance_id)
        fingerprints.add(canonical_fingerprint(gear))
    return {"instance_ids": ids, "fingerprints": fingerprints}


def _is_eligible(item: dict[str, Any]) -> tuple[bool, str, Any | None]:
    try:
        gear = _gear_from_item(item)
    except (KeyError, TypeError, ValueError) as error:
        return False, f"invalid_input:{error}", None
    if gear.level != 85 or gear.rank != "Epic" or str(item.get("itemSource") or item.get("item_source") or "normal_85") != "normal_85":
        return False, "outside_normal_85_epic_scope", None
    if gear.enhance not in (0, 3):
        return False, "outside_plus0_plus3_scope", None
    if _speed_hard_route(gear):
        return False, "speed_hard_route", None
    return True, "", gear


def _export_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("exported_at must include timezone")
    return parsed


def ingest_export(path: Path, payload: dict[str, Any], *, known: dict[str, set[str]]) -> dict[str, Any]:
    """Append eligible, post-freeze snapshots and seal A/B/C predictions.

    The payload must carry an explicit export timestamp.  File mtimes are not
    accepted as evidence of prospective collection.
    """
    path = Path(path)
    batch = json.loads(path.read_text(encoding="utf-8"))
    if batch.get("status") != "collecting_blind":
        raise ValueError(f"batch is not collecting_blind: {batch.get('status')}")
    exported_at = _export_time(str(payload.get("exported_at") or ""))
    frozen_at = _export_time(str(batch["created_at"]))
    if exported_at <= frozen_at:
        raise ValueError("export is not newer than the frozen batch")
    existing_ids = {str(row.get("instance_id") or "") for row in batch.get("items", [])}
    existing_fingerprints = {str(row.get("fingerprint") or "") for row in batch.get("items", [])}
    excluded: Counter[str] = Counter()
    accepted = 0
    for item in payload.get("items") or []:
        if len(batch["items"]) >= TARGET_COUNT:
            excluded["batch_full"] += 1
            continue
        valid, reason, gear = _is_eligible(item)
        if not valid:
            excluded[reason] += 1
            continue
        instance_id = str(item.get("ingameId") or item.get("id") or item.get("instance_id") or "")
        fingerprint = canonical_fingerprint(gear)
        if instance_id and instance_id in known["instance_ids"]:
            excluded["known_instance_id"] += 1
            continue
        if fingerprint in known["fingerprints"]:
            excluded["known_fingerprint"] += 1
            continue
        if instance_id and instance_id in existing_ids:
            excluded["batch_instance_id"] += 1
            continue
        if fingerprint in existing_fingerprints:
            excluded["batch_fingerprint"] += 1
            continue
        predictions = strategy_actions(gear, "normal_85")
        batch["items"].append({
            "instance_id": instance_id,
            "fingerprint": fingerprint,
            "exported_at": exported_at.isoformat(),
            "gear": item,
            "predictions": {key: predictions[key] for key in FROZEN_CANDIDATES},
            "oracle": {"status": "pending_research_lambda"},
        })
        accepted += 1
        existing_ids.add(instance_id)
        existing_fingerprints.add(fingerprint)
    batch["exclusions"].append({"exported_at": exported_at.isoformat(), "counts": dict(sorted(excluded.items()))})
    batch["progress"]["accepted"] = len(batch["items"])
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"accepted": accepted, "excluded_by_reason": dict(excluded), "progress": batch["progress"]}


def terminal_one_speed_value(final_speed: float, second_tier_anchor: float) -> float:
    """Research-only one-speed value; no independent value exists below 22."""
    if final_speed < 22:
        return 0.0
    # Existing curve is 5/20/50 at 22/25/27.  Preserve each higher-speed
    # increment while raising the 22-speed floor to the supplied tier-2 value.
    if final_speed >= 27:
        curve = 20 * final_speed - 490
    elif final_speed >= 25:
        curve = 10 * final_speed - 225
    else:
        curve = 5 * final_speed - 105
    return float(second_tier_anchor + max(0.0, curve - 5.0))


def lock_research_oracles(path: Path, *, lambda_value: float, cost_per_terminal_value: float) -> dict[str, Any]:
    """Freeze the research Oracle after lambda selection and before unblinding."""
    from tools.epic_non_speed_dp_oracle_audit import oracle_for_gear

    path = Path(path)
    batch = json.loads(path.read_text(encoding="utf-8"))
    if batch.get("status") != "collecting_blind":
        raise ValueError("research Oracle can only be locked while collecting_blind")
    for row in batch.get("items") or []:
        gear = _gear_from_item(row["gear"])
        row["oracle"] = oracle_for_gear(gear, lambda_value=lambda_value)
    batch["frozen"]["oracle"] = {
        "status": "locked_research_only",
        "lambda": lambda_value,
        "cost_per_terminal_value": cost_per_terminal_value,
        "manual_labels_visible": False,
    }
    path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"locked": len(batch.get("items") or []), "status": batch["frozen"]["oracle"]["status"]}


def _reference_items() -> list[dict[str, Any]]:
    payload = json.loads((ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json").read_text(encoding="utf-8"))
    blind = json.loads((ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json").read_text(encoding="utf-8"))
    return list(payload.get("items") or []) + list(blind.get("items") or [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze/import the Epic B prospective blind batch")
    parser.add_argument("--batch", type=Path, default=ROOT / "samples" / f"{BATCH_ID}.json")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--import-json", type=Path)
    args = parser.parse_args(argv)
    batch = create_batch(args.batch)
    if args.import_json:
        incoming = json.loads(args.import_json.read_text(encoding="utf-8"))
        result = ingest_export(args.batch, incoming, known=identity_index(_reference_items()))
        print(_stable_json(result))
    else:
        print(_stable_json({"batch_id": batch["batch_id"], "status": batch["status"], "progress": batch["progress"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
