"""Independent blind collection for the frozen Epic +0/+3 balanced candidate.

This module intentionally does not import the legacy +0/+3 pair collector and
does not evaluate policy actions, Oracle labels, or efficiency during intake.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable

from tools.epic_non_speed_dp_oracle_audit import canonical_fingerprint
from tools.epic_non_speed_early_policy_pareto import _gear_from_item, _speed_hard_route
from tools import research_epic_threshold_matrix_phase_b as phase_b
from tools import research_epic_threshold_matrix_phase_c as phase_c


ROOT = Path(__file__).resolve().parents[2]
FREEZE_ID = "epic_output_8_13_tank_10_17_holdout_freeze_20260718"
COLLECTION_ID = "epic_output_8_13_tank_10_17_holdout_20260718"
TARGET_COUNT = 128
DEVELOPMENT_COUNT = 64
FROZEN_VALIDATION_COUNT = 64
RULE = {
    "key": "output_8_13_tank_10_17",
    "thresholds": {
        "default": {"plus0": 12, "plus3": 17},
        "pure_output": {"plus0": 8, "plus3": 13},
        "pure_tank": {"plus0": 10, "plus3": 17},
    },
    "scope": "normal_85 Epic non-boots initial_speed<2 at +0/+3 only",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _hash_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("exported_at must include timezone")
    return parsed


def _candidate_hash() -> str:
    return _sha256_bytes(_stable_json({
        "rule": RULE,
        "phase_b_schema": phase_b.JOINT_SCHEMA_VERSION,
        "phase_c_schema": phase_c.SCHEMA_VERSION,
        "mapping_version": phase_c.MAPPING_VERSION,
        "action_sources": {
            "phase_b": _sha256_bytes(inspect.getsource(phase_b.action).encode("utf-8")),
            "phase_c": _sha256_bytes(inspect.getsource(phase_c.action).encode("utf-8")),
        },
    }).encode("utf-8"))


def _frozen_hashes() -> dict[str, str]:
    files = {
        "phase_b_research": ROOT / "tools" / "research_epic_threshold_matrix_phase_b.py",
        "phase_c_research": ROOT / "tools" / "research_epic_threshold_matrix_phase_c.py",
        "plus3_official_probability": ROOT / "tools" / "epic_plus3_exact_branches.py",
        "formal_epic_dp": ROOT / "src" / "e7_enhance" / "dp_assisted_analysis.py",
        "resource_model": ROOT / "src" / "e7_enhance" / "resource_model.py",
        "score_engine": ROOT / "src" / "e7_enhance" / "score_engine.py",
    }
    return {name: _hash_path(path) for name, path in files.items()}


def _freeze_payload(frozen_at: str) -> dict[str, Any]:
    return {
        "freeze_id": FREEZE_ID,
        "schema_version": 1,
        "status": "candidate_frozen",
        "frozen_at": frozen_at,
        "candidate": {**RULE, "candidate_hash": _candidate_hash()},
        "frozen_hashes": _frozen_hashes(),
        "holdout_protocol": {
            "target": TARGET_COUNT,
            "manifest_split": {"development": DEVELOPMENT_COUNT, "frozen_validation": FROZEN_VALIDATION_COUNT},
            "state_machine": ["collecting_blind", "ready_for_frozen_validation", "validation_complete"],
            "no_early_stop": "0--127 only exposes progress and exclusion reasons; 64 does not freeze or permit validation reads",
            "inclusion": "normal_85 Epic non-boots +0 initial_speed<2 with four substats, post-freeze full Fribbels export, stable instanceId and normalized fingerprint",
            "exclusion": "all historical Phase A/B/C, Oracle, blind, prospective, synthetic, duplicate, Heroic, rift, boots, speed-route and enhanced records",
        },
        "validation_gates": {
            "plus0_clear_positive_recall_min": 0.95,
            "plus3_weighted_clear_positive_recall_min": 0.99,
            "pure_output_plus0_clear_positive_false_stop": 0,
            "candidate_regret_not_above_current": True,
            "max_false_stop_utility_margin": 0.01,
            "joint_value_ci_lower_gt_zero": True,
            "heroic_yield_sensitivity_ci_lower_gt_zero": True,
        },
    }


def freeze_candidate(path: Path, *, frozen_at: str | None = None) -> dict[str, Any]:
    """Write the candidate freeze once; existing freezes are immutable."""
    path = Path(path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("freeze_id") != FREEZE_ID or payload.get("status") != "candidate_frozen":
            raise ValueError("existing file is not this holdout candidate freeze")
        return payload
    payload = _freeze_payload(frozen_at or _now())
    _atomic_json(path, payload)
    return payload


def _freeze_sha(freeze: dict[str, Any]) -> str:
    return _sha256_bytes(_stable_json(freeze).encode("utf-8"))


def create_collection(path: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    """Create an independent blind-only collection state, never a pair dataset."""
    path = Path(path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("collection_id") != COLLECTION_ID:
            raise ValueError("existing collection belongs to a different holdout protocol")
        if payload.get("freeze_sha256") != _freeze_sha(freeze):
            raise ValueError("collection freeze does not match the candidate freeze")
        return payload
    payload = {
        "collection_id": COLLECTION_ID,
        "schema_version": 1,
        "status": "collecting_blind",
        "freeze_sha256": _freeze_sha(freeze),
        "created_at": _now(),
        "progress": {"accepted": 0, "target": TARGET_COUNT},
        "snapshots": [],
        "exclusion_log": [],
        "manifest": None,
    }
    _atomic_json(path, payload)
    return payload


def _instance_id(item: dict[str, Any]) -> str:
    return str(item.get("ingameId") or item.get("instanceId") or item.get("id") or item.get("instance_id") or "")


def _eligible(item: dict[str, Any]) -> tuple[bool, str, Any | None]:
    try:
        gear = _gear_from_item(item)
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"invalid_fribbels_item:{exc}", None
    if not _instance_id(item):
        return False, "missing_instance_id", None
    if gear.rank != "Epic" or gear.level != 85 or str(item.get("itemSource") or item.get("item_source") or "") != "normal_85":
        return False, "outside_normal_85_epic_scope", None
    if gear.enhance != 0:
        return False, "not_plus0", None
    if str(gear.slot).lower() in {"boots", "boot", "shoes", "shoe"}:
        return False, "boots", None
    if len(gear.substats) != 4:
        return False, "missing_four_substats", None
    if _speed_hard_route(gear):
        return False, "speed_hard_route", None
    return True, "", gear


def identity_index(items: Iterable[dict[str, Any]]) -> dict[str, set[str]]:
    ids: set[str] = set()
    fingerprints: set[str] = set()
    for item in items:
        try:
            gear = _gear_from_item(item)
        except (KeyError, TypeError, ValueError):
            continue
        instance_id = _instance_id(item)
        if instance_id:
            ids.add(instance_id)
        fingerprints.add(canonical_fingerprint(gear))
    return {"instance_ids": ids, "fingerprints": fingerprints}


def _walk_items(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if {"rank", "level"}.issubset(value) and ("substats" in value or "subStats" in value):
            yield value
        for child in value.values():
            yield from _walk_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_items(child)


def historical_identity_index() -> dict[str, set[str]]:
    """Build the historical exclusion index without reading the new holdout."""
    references = (
        ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json",
        ROOT / "samples" / "epic_non_speed_blind_acceptance_20260712.json",
        ROOT / "samples" / "epic_b_balanced_prospective_20260713.json",
        ROOT / "manual_acceptance" / "real_sample_records.json",
    )
    items: list[dict[str, Any]] = []
    for path in references:
        if not path.exists():
            continue
        try:
            items.extend(_walk_items(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return identity_index(items)


def _manifest_source_hash(collection: dict[str, Any]) -> str:
    return _sha256_bytes(_stable_json({
        "collection_id": collection["collection_id"],
        "freeze_sha256": collection["freeze_sha256"],
        "snapshots": collection["snapshots"],
        "exclusion_log": collection["exclusion_log"],
    }).encode("utf-8"))


def _build_manifest(collection: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source_collection_id") != COLLECTION_ID or manifest.get("collection_sha256") != _manifest_source_hash(collection):
            raise ValueError("existing manifest does not match this frozen collection")
        return manifest
    snapshots = list(collection["snapshots"])
    if len(snapshots) != TARGET_COUNT:
        raise ValueError("need exactly 128 blind snapshots before manifest freeze")
    ordered = sorted(snapshots, key=lambda row: _sha256_bytes(str(row["sample_id"]).encode("utf-8")))
    included = []
    for index, snapshot in enumerate(ordered):
        included.append({
            "sample_id": snapshot["sample_id"],
            "instance_id": snapshot["instance_id"],
            "fingerprint": snapshot["fingerprint"],
            "source_exported_at": snapshot["exported_at"],
            "group": "development" if index < DEVELOPMENT_COUNT else "frozen_validation",
        })
    manifest = {
        "manifest_id": f"{COLLECTION_ID}_manifest128",
        "schema_version": 1,
        "status": "immutable_64_64_manifest",
        "source_collection_id": COLLECTION_ID,
        "collection_sha256": _manifest_source_hash(collection),
        "freeze_sha256": collection["freeze_sha256"],
        "split_rule": "sort SHA256(sample_id); first 64 development, final 64 frozen_validation",
        "included": included,
        "exclusion_log": collection["exclusion_log"],
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def ingest_export(path: Path, payload: dict[str, Any], *, freeze: dict[str, Any], known: dict[str, set[str]], manifest_path: Path | None = None) -> dict[str, Any]:
    """Append only legal post-freeze +0 snapshots without calculating outcomes."""
    path = Path(path)
    collection = create_collection(path, freeze)
    if collection["status"] != "collecting_blind":
        raise ValueError(f"collection is not collecting_blind: {collection['status']}")
    current_freeze = _freeze_payload(str(freeze["frozen_at"]))
    if _freeze_sha(current_freeze) != _freeze_sha(freeze):
        collection["status"] = "closed_hash_mismatch"
        _atomic_json(path, collection)
        raise ValueError("candidate freeze hashes changed; collection is closed and requires a new holdout batch")
    if payload.get("source_kind") != "full_fribbels_export" or not payload.get("source_file_sha256"):
        raise ValueError("holdout intake requires a hashed full_fribbels_export payload")
    exported_at = _parse_time(str(payload.get("exported_at") or ""))
    if exported_at <= _parse_time(str(freeze["frozen_at"])):
        raise ValueError("export is not newer than the candidate freeze")
    existing_ids = {str(row["instance_id"]) for row in collection["snapshots"]}
    existing_fingerprints = {str(row["fingerprint"]) for row in collection["snapshots"]}
    exclusions: Counter[str] = Counter()
    accepted = 0
    for item in payload.get("items") or payload.get("equipment") or []:
        if len(collection["snapshots"]) >= TARGET_COUNT:
            exclusions["batch_full"] += 1
            continue
        valid, reason, gear = _eligible(item)
        if not valid:
            exclusions[reason] += 1
            continue
        instance_id = _instance_id(item)
        fingerprint = canonical_fingerprint(gear)
        if instance_id in known["instance_ids"]:
            exclusions["known_instance_id"] += 1
            continue
        if fingerprint in known["fingerprints"]:
            exclusions["known_fingerprint"] += 1
            continue
        if instance_id in existing_ids:
            exclusions["batch_instance_id"] += 1
            continue
        if fingerprint in existing_fingerprints:
            exclusions["batch_fingerprint"] += 1
            continue
        sample_id = _sha256_bytes(_stable_json({"instance_id": instance_id, "fingerprint": fingerprint, "exported_at": exported_at.isoformat()}).encode("utf-8"))
        collection["snapshots"].append({"sample_id": sample_id, "instance_id": instance_id, "fingerprint": fingerprint, "exported_at": exported_at.isoformat(), "source_file_sha256": str(payload["source_file_sha256"]), "gear": item})
        existing_ids.add(instance_id)
        existing_fingerprints.add(fingerprint)
        accepted += 1
    collection["exclusion_log"].append({"exported_at": exported_at.isoformat(), "counts": dict(sorted(exclusions.items()))})
    collection["progress"]["accepted"] = len(collection["snapshots"])
    if len(collection["snapshots"]) == TARGET_COUNT:
        manifest_path = Path(manifest_path) if manifest_path is not None else path.with_name(f"{COLLECTION_ID}_manifest.json")
        manifest = _build_manifest(collection, manifest_path)
        collection["manifest"] = {"path": str(manifest_path), "sha256": _sha256_bytes(_stable_json(manifest).encode("utf-8"))}
        collection["status"] = "ready_for_frozen_validation"
    _atomic_json(path, collection)
    return {"accepted": accepted, "excluded_by_reason": dict(exclusions), "status": collection["status"], "progress": progress_from_data(collection)}


def progress_from_data(collection: dict[str, Any]) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    for row in collection.get("exclusion_log") or []:
        totals.update(row.get("counts") or {})
    accepted = int(collection["progress"]["accepted"])
    return {"status": collection["status"], "accepted": accepted, "target": TARGET_COUNT, "remaining": max(0, TARGET_COUNT - accepted), "excluded_by_reason": dict(sorted(totals.items()))}


def progress(path: Path) -> dict[str, Any]:
    return progress_from_data(json.loads(Path(path).read_text(encoding="utf-8")))


def validation_manifest(collection_path: Path, manifest_path: Path) -> dict[str, Any]:
    collection = json.loads(Path(collection_path).read_text(encoding="utf-8"))
    if collection.get("status") == "collecting_blind":
        raise ValueError("collection is collecting_blind; need 128 snapshots before manifest freeze")
    if collection.get("status") != "ready_for_frozen_validation":
        raise ValueError("collection is not ready for frozen validation")
    return _build_manifest(collection, Path(manifest_path))


def validation_inputs(collection_path: Path, manifest_path: Path) -> list[dict[str, Any]]:
    """Permit future validation only after a valid 128-item manifest exists."""
    manifest = validation_manifest(collection_path, manifest_path)
    collection = json.loads(Path(collection_path).read_text(encoding="utf-8"))
    by_id = {row["sample_id"]: row for row in collection["snapshots"]}
    development_ids = [row["sample_id"] for row in manifest["included"] if row["group"] == "development"]
    return [by_id[sample_id] for sample_id in development_ids]
