"""Passive collection of real normal Epic +0 -> +3 prospective pairs.

The collector deliberately owns no enhancement decision.  A runtime/export
adapter calls :func:`record_observation` after it has observed a real game
state; the function only appends JSON evidence or an exclusion reason.
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
from typing import Any

from .enhance_policy import advise_gear, lightweight_prediction
from .models import Gear


COLLECTION_ID = "normal_85_epic_non_speed_plus3_prospective_20260714"
SCHEMA_VERSION = 1
SAMPLE_SOURCE = "prospective_runtime"
MIN_ORACLE_SCREEN_COUNT = 64
FREEZE_TARGET_COUNT = 128


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_time(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include timezone")
    return parsed.isoformat(timespec="seconds")


def normalized_fingerprint(gear: Gear) -> str:
    """Fingerprint a current state without code or instance ID."""
    payload = {
        "set": gear.set,
        "slot": gear.slot,
        "main": {"key": gear.main_stat.key, "value": gear.main_stat.normalized_value},
        "enhance": gear.enhance,
        "level": gear.level,
        "rank": gear.rank,
        "substats": sorted((stat.key, stat.normalized_value, stat.rolls, bool(stat.modified)) for stat in gear.substats),
        "roll_history": [(roll.type, roll.value) for roll in gear.roll_history],
        "reforge_eligible": bool(gear.reforge_eligible),
    }
    return sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def strategy_rule_hash() -> str:
    """Hash the released early-action implementation observed by this batch."""
    source = "\n".join((inspect.getsource(advise_gear), inspect.getsource(lightweight_prediction)))
    return sha256(source.encode("utf-8")).hexdigest()


def _instance_id(raw: dict[str, Any]) -> str:
    return str(raw.get("instanceId") or raw.get("instance_id") or raw.get("ingameId") or raw.get("id") or "").strip()


def _speed(gear: Gear) -> float:
    return float(next((stat.normalized_value for stat in gear.substats if stat.key == "spd"), 0.0))


def _scope_reason(gear: Gear, raw: dict[str, Any]) -> str | None:
    if str(raw.get("itemSource") or raw.get("item_source") or "normal_85") != "normal_85":
        return "outside_normal_85"
    if gear.rank != "Epic":
        return "outside_epic"
    if gear.slot == "boot":
        return "boots_excluded"
    if gear.enhance not in (0, 3):
        return "outside_plus0_plus3"
    return None


def _observed_formal_action(recommendation: Any) -> dict[str, str] | None:
    recommendation = str(recommendation or "")
    if recommendation not in {"continue", "cautious_continue", "stop"}:
        return None
    return {
        "recommendation": recommendation,
        "resource_action": "stop" if recommendation == "stop" else "enhance",
    }


def _roll_history(gear: Gear) -> list[dict[str, Any]]:
    return [{"type": roll.type, "value": roll.value} for roll in gear.roll_history]


def _state_snapshot(gear: Gear, raw: dict[str, Any], observed_at: str) -> dict[str, Any]:
    return {
        "observed_at": observed_at,
        "fingerprint": normalized_fingerprint(gear),
        "gear": gear.to_dict(),
        "gear_source": str(raw.get("gearSource") or raw.get("gear_source") or ""),
        "roll_history": _roll_history(gear),
        "substat_roll_counts": {stat.key: int(stat.rolls) for stat in gear.substats},
        "reforge_eligible": bool(gear.reforge_eligible),
    }


def _derive_plus3_hit(before: Gear, after: Gear) -> dict[str, Any] | None:
    """Derive the +3 target from two observed states, never from a future roll."""
    before_by_key = {stat.key: stat for stat in before.substats}
    after_by_key = {stat.key: stat for stat in after.substats}
    if set(before_by_key) != set(after_by_key):
        return None
    changes = []
    for key, after_stat in after_by_key.items():
        before_stat = before_by_key[key]
        value_delta = after_stat.normalized_value - before_stat.normalized_value
        rolls_delta = int(after_stat.rolls) - int(before_stat.rolls)
        if value_delta or rolls_delta:
            changes.append({"stat_key": key, "value_delta": value_delta, "rolls_delta": rolls_delta})
    if len(changes) != 1 or changes[0]["value_delta"] <= 0 or changes[0]["rolls_delta"] <= 0:
        return None
    return changes[0]


def _same_item(before: Gear, after: Gear, before_raw: dict[str, Any], after_raw: dict[str, Any]) -> bool:
    return (
        before.set == after.set
        and before.slot == after.slot
        and before.main_stat.key == after.main_stat.key
        and before.level == after.level
        and before.rank == after.rank
        and str(before_raw.get("itemSource") or before_raw.get("item_source") or "normal_85")
        == str(after_raw.get("itemSource") or after_raw.get("item_source") or "normal_85")
    )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _new_dataset(created_at: str) -> dict[str, Any]:
    return {
        "collection_id": COLLECTION_ID,
        "schema_version": SCHEMA_VERSION,
        "created_at": created_at,
        "sample_source": SAMPLE_SOURCE,
        "collected_blind": True,
        "policy_rule_sha256": strategy_rule_hash(),
        "scope": "normal_85 Epic non-boot; +0 initial speed absent or <2; paired with real +3 before its next decision",
        "observations": {"plus0_pending": [], "pairs": []},
        "exclusions": [],
    }


def load_dataset(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return _new_dataset(_now())
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("collection_id") != COLLECTION_ID or data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("not a compatible prospective +3 collection dataset")
    if data.get("policy_rule_sha256") != strategy_rule_hash():
        raise ValueError("released strategy hash changed; create a new prospective collection instead of mixing rules")
    return data


def _observation_indexes(data: dict[str, Any]) -> tuple[set[tuple[str, str]], dict[str, str], set[str]]:
    by_identity: set[tuple[str, str]] = set()
    fingerprint_owner: dict[str, str] = {}
    instance_ids: set[str] = set()
    for pending in data["observations"].get("plus0_pending") or []:
        instance_id, fingerprint = str(pending["instance_id"]), str(pending["plus0"]["fingerprint"])
        by_identity.add((instance_id, fingerprint)); fingerprint_owner[fingerprint] = instance_id; instance_ids.add(instance_id)
    for pair in data["observations"].get("pairs") or []:
        instance_id = str(pair["instance_id"])
        instance_ids.add(instance_id)
        for state in (pair["plus0"], pair["plus3"]):
            fingerprint = str(state["fingerprint"])
            by_identity.add((instance_id, fingerprint)); fingerprint_owner[fingerprint] = instance_id
    return by_identity, fingerprint_owner, instance_ids


def _exclude(data: dict[str, Any], *, reason: str, observed_at: str, instance_id: str = "", fingerprint: str = "") -> None:
    data["exclusions"].append({
        "reason": reason, "observed_at": observed_at, "instance_id": instance_id,
        "fingerprint": fingerprint, "sample_source": SAMPLE_SOURCE,
    })


def record_observation(path: Path, observation: dict[str, Any]) -> dict[str, Any]:
    """Passively record one real +0 or +3 observation and atomically persist it.

    A +0 observation is only a pending state.  The later +3 observation is the
    evidence that a real enhancement happened; the collector never clicks or
    asserts an ``actual_enhancement`` flag.
    """
    data = load_dataset(path)
    raw = dict(observation.get("gear") or observation.get("item") or {})
    observed_at = _parse_time(str(observation.get("observed_at") or ""))
    if str(observation.get("sample_source") or "") != SAMPLE_SOURCE:
        _exclude(data, reason="not_prospective_runtime", observed_at=observed_at)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "not_prospective_runtime"}
    try:
        gear = Gear.from_dict(raw)
    except (KeyError, TypeError, ValueError) as error:
        _exclude(data, reason=f"invalid_gear:{error}", observed_at=observed_at)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "invalid_gear"}
    instance_id = _instance_id(raw)
    fingerprint = normalized_fingerprint(gear)
    scope_reason = _scope_reason(gear, raw)
    if scope_reason:
        _exclude(data, reason=scope_reason, observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": scope_reason}
    if not instance_id:
        _exclude(data, reason="missing_instance_id", observed_at=observed_at, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "missing_instance_id"}

    identities, fingerprint_owner, _instance_ids = _observation_indexes(data)
    if (instance_id, fingerprint) in identities:
        _exclude(data, reason="duplicate_identity_and_fingerprint", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "duplicate", "reason": "duplicate_identity_and_fingerprint"}
    if fingerprint in fingerprint_owner and fingerprint_owner[fingerprint] != instance_id:
        _exclude(data, reason="duplicate_fingerprint", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "duplicate", "reason": "duplicate_fingerprint"}

    if gear.enhance == 0:
        if _speed(gear) >= 2:
            _exclude(data, reason="initial_speed_hard_route", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
            _atomic_json(Path(path), data)
            return {"status": "excluded", "reason": "initial_speed_hard_route"}
        formal = _observed_formal_action(observation.get("observed_formal_recommendation"))
        if formal is None:
            _exclude(data, reason="missing_observed_formal_recommendation", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
            _atomic_json(Path(path), data)
            return {"status": "excluded", "reason": "missing_observed_formal_recommendation"}
        if formal["resource_action"] != "enhance":
            _exclude(data, reason="formal_policy_stop", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
            _atomic_json(Path(path), data)
            return {"status": "excluded", "reason": "formal_policy_stop"}
        data["observations"]["plus0_pending"].append({
            "instance_id": instance_id,
            "sample_source": SAMPLE_SOURCE,
            "collected_blind": True,
            "policy_rule_sha256": data["policy_rule_sha256"],
            "formal_action": formal,
            "plus0": _state_snapshot(gear, raw, observed_at),
        })
        _atomic_json(Path(path), data)
        return {"status": "pending_plus0", "instance_id": instance_id, "progress": progress(data)}

    pending = next((row for row in data["observations"]["plus0_pending"] if str(row["instance_id"]) == instance_id), None)
    if pending is None:
        _exclude(data, reason="unpaired_plus3", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "unpaired_plus3"}
    before_raw = pending["plus0"]["gear"]
    before = Gear.from_dict(before_raw)
    if not _same_item(before, gear, before_raw, raw):
        _exclude(data, reason="plus0_plus3_item_mismatch", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "plus0_plus3_item_mismatch"}
    hit = _derive_plus3_hit(before, gear)
    if hit is None:
        _exclude(data, reason="missing_or_ambiguous_plus3_hit_history", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "missing_or_ambiguous_plus3_hit_history"}
    if not bool(observation.get("before_next_strategy_judgement", False)):
        _exclude(data, reason="plus3_not_before_next_strategy_judgement", observed_at=observed_at, instance_id=instance_id, fingerprint=fingerprint)
        _atomic_json(Path(path), data)
        return {"status": "excluded", "reason": "plus3_not_before_next_strategy_judgement"}

    data["observations"]["plus0_pending"].remove(pending)
    sample_id = sha256(f"{instance_id}:{pending['plus0']['fingerprint']}:{fingerprint}".encode("utf-8")).hexdigest()
    data["observations"]["pairs"].append({
        "sample_id": sample_id,
        "instance_id": instance_id,
        "sample_source": SAMPLE_SOURCE,
        "collected_blind": True,
        "policy_rule_sha256": data["policy_rule_sha256"],
        "plus0": pending["plus0"],
        "plus3": _state_snapshot(gear, raw, observed_at),
        "plus3_hit": hit,
    })
    _atomic_json(Path(path), data)
    return {"status": "paired", "sample_id": sample_id, "progress": progress(data)}


def observe_trusted_fribbels_state(
    gear_data: dict[str, Any],
    suggestion: dict[str, Any],
    *,
    dataset_path: Path | None = None,
) -> dict[str, Any]:
    """Passively observe one already-parsed full Fribbels state.

    This adapter intentionally accepts only the existing suggestion payload.
    It does not invoke ``advise_gear`` or alter the payload.  Any filesystem or
    validation failure is converted into diagnostics so the GUI suggestion
    path remains observationally transparent.
    """
    dataset_path = dataset_path or Path(__file__).resolve().parents[2] / "samples" / "epic_plus3_prospective_runtime_20260714.json"
    recommendation = ((suggestion.get("summary") or {}).get("recommendation"))
    try:
        gear = Gear.from_dict(gear_data)
        observation = {
            "gear": gear_data,
            "sample_source": SAMPLE_SOURCE,
            "observed_at": _now(),
            "observed_formal_recommendation": recommendation,
        }
        if gear.enhance == 3:
            observation["before_next_strategy_judgement"] = True
        return record_observation(dataset_path, observation)
    except Exception as error:  # Observation must never affect the suggestion path.
        return {"status": "observation_error", "reason": type(error).__name__}


def _load_and_validate_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        raise ValueError("a frozen prospective manifest is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    included = list(manifest.get("included") or [])
    development = [row for row in included if row.get("group") == "development"]
    validation = [row for row in included if row.get("group") == "frozen_validation"]
    ids = [str(row.get("sample_id") or "") for row in included]
    if len(included) != FREEZE_TARGET_COUNT or len(development) != 64 or len(validation) != 64 or len(set(ids)) != FREEZE_TARGET_COUNT:
        raise ValueError("manifest must contain one fixed 64/64 prospective split")
    return manifest


def progress(data: dict[str, Any], *, manifest_path: Path | None = None) -> dict[str, Any]:
    pairs = list(data["observations"].get("pairs") or [])
    exclusions = Counter(str(row.get("reason") or "unknown") for row in data.get("exclusions") or [])
    duplicates = sum(count for reason, count in exclusions.items() if reason.startswith("duplicate_"))
    out_of_scope = sum(count for reason, count in exclusions.items() if reason.startswith("outside_") or reason in {"boots_excluded", "initial_speed_hard_route"})
    pair_count = len(pairs)
    result = {
        "discovered_observation_count": len(pairs) * 2 + len(data["observations"].get("plus0_pending") or []) + len(data.get("exclusions") or []),
        "valid_plus0_plus3_pair_count": pair_count,
        "pending_plus0_count": len(data["observations"].get("plus0_pending") or []),
        "duplicate_count": duplicates,
        "missing_hit_history_count": exclusions["missing_or_ambiguous_plus3_hit_history"],
        "outside_scope_count": out_of_scope,
        "unpaired_plus3_count": exclusions["unpaired_plus3"],
        "remaining_to_64": max(0, MIN_ORACLE_SCREEN_COUNT - pair_count),
        "remaining_to_128": max(0, FREEZE_TARGET_COUNT - pair_count),
    }
    if manifest_path is not None and Path(manifest_path).exists():
        manifest = _load_and_validate_manifest(Path(manifest_path))
        result.update({
            "status": "manifest_frozen",
            "development_count": 64,
            "frozen_validation_count": 64,
            "manifest_id": manifest.get("manifest_id"),
        })
    elif pair_count >= FREEZE_TARGET_COUNT:
        result["status"] = "ready_to_freeze_manifest"
    else:
        # 64 is intentionally only a visible milestone.  No research action is
        # allowed until a later 128-pair manifest fixes the split.
        result["status"] = "collecting_blind"
    return result


def freeze_manifest(dataset_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Freeze exactly 128 pair groups with a deterministic, immutable split."""
    manifest_path = Path(manifest_path)
    if manifest_path.exists():
        return _load_and_validate_manifest(manifest_path)
    data = load_dataset(dataset_path)
    pairs = list(data["observations"].get("pairs") or [])
    if len(pairs) < FREEZE_TARGET_COUNT:
        raise ValueError(f"need {FREEZE_TARGET_COUNT} valid pairs before manifest freeze")
    ordered = sorted(pairs, key=lambda row: sha256(str(row["sample_id"]).encode("utf-8")).hexdigest())
    selected, not_included = ordered[:FREEZE_TARGET_COUNT], ordered[FREEZE_TARGET_COUNT:]
    data_sha = sha256(Path(dataset_path).read_bytes()).hexdigest()
    rows = []
    for index, pair in enumerate(selected):
        rows.append({
            "sample_id": pair["sample_id"],
            "group": "development" if index < 64 else "frozen_validation",
            "inclusion_reason": "valid_real_prospective_runtime_plus0_plus3_pair",
            "rule_hash": pair["policy_rule_sha256"],
            "plus0_fingerprint": pair["plus0"]["fingerprint"],
            "plus3_fingerprint": pair["plus3"]["fingerprint"],
        })
    manifest = {
        "manifest_id": f"{COLLECTION_ID}_freeze128",
        "status": "manifest_frozen",
        "frozen_at": _now(),
        "dataset_sha256": data_sha,
        "policy_rule_sha256": data["policy_rule_sha256"],
        "split_rule": "sort SHA256(sample_id), first 64 development, next 64 frozen_validation; manifest is write-once",
        "oracle_access": {
            "development": "allowed only through development_pairs_from_manifest",
            "frozen_validation": "blocked until future candidate and prediction hashes are frozen",
        },
        "included": rows,
        "not_included_pairs": [
            {
                "sample_id": pair["sample_id"],
                "reason": "outside_initial_freeze128",
                "rule_hash": pair["policy_rule_sha256"],
                "plus0_fingerprint": pair["plus0"]["fingerprint"],
                "plus3_fingerprint": pair["plus3"]["fingerprint"],
            }
            for pair in not_included
        ],
        "exclusions": list(data.get("exclusions") or []),
    }
    _atomic_json(manifest_path, manifest)
    return manifest


def development_pairs_from_manifest(dataset_path: Path, manifest_path: Path) -> list[dict[str, Any]]:
    """Return only the manifest's 64 development pairs for future Oracle work."""
    manifest = _load_and_validate_manifest(manifest_path)
    data = load_dataset(dataset_path)
    if manifest.get("policy_rule_sha256") != data.get("policy_rule_sha256"):
        raise ValueError("manifest and prospective dataset rule hashes do not match")
    by_id = {str(pair.get("sample_id") or ""): pair for pair in data["observations"].get("pairs") or []}
    ids = [str(row["sample_id"]) for row in manifest["included"] if row["group"] == "development"]
    missing = [sample_id for sample_id in ids if sample_id not in by_id]
    if missing:
        raise ValueError("manifest development pair is missing from prospective dataset")
    return [by_id[sample_id] for sample_id in ids]


def frozen_validation_pairs_from_manifest(dataset_path: Path, manifest_path: Path) -> list[dict[str, Any]]:
    """Refuse premature frozen-validation access by construction."""
    _load_and_validate_manifest(manifest_path)
    raise ValueError("frozen_validation cannot be read before candidate and prediction hashes are frozen")
