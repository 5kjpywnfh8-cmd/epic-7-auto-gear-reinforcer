"""Create a reviewable, read-only pairing manifest for OCR stage-1 batch 001."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.e7_enhance.ocr_capture import capture_from_file


DEFAULT_BATCH = ROOT / "manual_acceptance" / "ocr_stage1" / "batch_001"
DEFAULT_REFERENCE = Path(r"D:\VScode\E7-tools\gear_read\gear_fribbels_20260719_221033.json")
INPUT_FILENAMES = (
    "codex-clipboard-c9b93c1d-6850-4d58-9834-996cef87c18a.png", "codex-clipboard-7fd96234-5931-4c35-9695-fabeabdef968.png",
    "codex-clipboard-1b97f6d3-0e15-488e-82cb-9c890f03561e.png", "codex-clipboard-63485f39-d6f8-4034-8964-268402ed1f31.png",
    "codex-clipboard-646df2c3-1447-4323-9870-377861579fd8.png", "codex-clipboard-7183b54f-96f1-4780-90e1-3f2afac6b48e.png",
    "codex-clipboard-68d68b92-71d7-464a-9a0f-17bafdc8f045.png", "codex-clipboard-81a5eb57-48be-4dda-a70d-4ac71aaa1929.png",
    "codex-clipboard-8a81b0be-7320-468d-955e-26882ee7b30b.png", "codex-clipboard-a7f9c6a6-3843-42ce-a23d-db6ec8f9526b.png",
    "codex-clipboard-fd131bc1-93d3-43de-b3a1-176d770f4562.png", "codex-clipboard-c3500174-f8df-4d45-bb22-2c3e9ea797f0.png",
    "codex-clipboard-141be28f-4765-48af-9801-a05151b8e4f6.png", "codex-clipboard-3aa05b33-7cb7-4c1d-89d4-2f11a74a67d7.png",
)
INPUT_SHA256 = (
    "E78CB524BD7E8FE77D314178AE8CA5F72868BA2395728142865778A7B1EA44EB", "D8DB077B58F7663D6C4D37F6D8BB2F8468C8DBF96CED984AA49D61CA6479BC10",
    "A5269974C9988D31AD105F18A4C03DC20D714E3E4A5A4BCAFDCA31E60AC70136", "0760E4F30DE6DE735092796C15B6EFF6229DFB873A9ED5450C4D045649546528",
    "18BDEF32D699768A6C7E2DC1091DF0324B4C4C082ACDAA9F975A629D535E04BF", "A5269974C9988D31AD105F18A4C03DC20D714E3E4A5A4BCAFDCA31E60AC70136",
    "0E425B080A8677E2251BAED3813502C97066BD38920407A7B187050FFBED9191", "0E425B080A8677E2251BAED3813502C97066BD38920407A7B187050FFBED9191",
    "5A2A4B6A7A7700231846D6603558BB8690C0F8F584972002E6EBAA057041F3E2", "41D1AEB4A416F8514B1A66F0D3A4D722BF1B3B16292EF168C7893F04CB0B1D9D",
    "E35711E4B57AB9FB29A9E12ED07CC2AB5C76D8EB802E65EA2F212ABB63C34AC3", "A97F7760534DB2A0F9B2A9F3A8CE2898C103C958C08D35ACAC6C95C1222A036A",
    "C1BD895DA2EEA7F647AE39818B4C08E02D893C0582FD866A271106B4F41AF255", "372DB00C6D8A2EEE70517830034136C5207E109071F03BF946AFB6522FC8F499",
)


def _stats(name, value, rolls=None):
    row = {"type": name, "value": value}
    if rolls is not None:
        row["rolls"] = rolls
    return row


GROUPS = {
    "gear-001": {"page_types": {"ocr-0001": "inventory_detail", "ocr-0002": "enhance"}, "fields": {"set": "ResistSet", "slot": "Necklace", "rank": "Heroic", "level": 85, "enhance": 0, "main": _stats("CriticalHitDamagePercent", 13), "substats": [_stats("Speed", 2), _stats("CriticalHitChancePercent", 4), _stats("EffectResistancePercent", 5)]}},
    "gear-002": {"page_types": {"ocr-0003": "enhance", "ocr-0004": "inventory_detail", "ocr-0006": "enhance"}, "fields": {"set": "SpeedSet", "slot": "Armor", "rank": "Epic", "level": 85, "enhance": 0, "main": _stats("Defense", 60), "substats": [_stats("HealthPercent", 7), _stats("DefensePercent", 6), _stats("Speed", 3), _stats("EffectivenessPercent", 6)]}},
    "gear-003": {"page_types": {"ocr-0005": "inventory_detail", "ocr-0007": "enhance", "ocr-0008": "enhance"}, "fields": {"set": "SpeedSet", "slot": "Weapon", "rank": "Epic", "level": 88, "enhance": 9, "main": _stats("Attack", 288), "substats": [_stats("AttackPercent", 9), _stats("Speed", 15), _stats("CriticalHitChancePercent", 6), _stats("CriticalHitDamagePercent", 8)]}},
    "gear-004": {"page_types": {"ocr-0009": "inventory_detail", "ocr-0010": "substat_conversion"}, "fields": {"set": "HealthSet", "slot": "Helmet", "rank": "Epic", "level": 90, "enhance": 15, "main": _stats("Health", 2835), "substats": [_stats("HealthPercent", 16), _stats("Speed", 9), _stats("AttackPercent", 23), _stats("EffectResistancePercent", 17)]}},
    "gear-005": {"page_types": {"ocr-0011": "enhance"}, "fields": {"set": "ImmunitySet", "slot": "Ring", "rank": "Epic", "level": 85, "enhance": 12, "main": _stats("EffectResistancePercent", 43), "substats": [_stats("CriticalHitChancePercent", 8), _stats("EffectivenessPercent", 12), _stats("Speed", 11), _stats("AttackPercent", 7)]}},
    "gear-006": {"page_types": {"ocr-0012": "enhance"}, "fields": {"set": "RiposteSet", "slot": "Boots", "rank": "Epic", "level": 85, "enhance": 6, "main": _stats("AttackPercent", 26), "substats": [_stats("CriticalHitDamagePercent", 7), _stats("HealthPercent", 4), _stats("EffectivenessPercent", 7), _stats("CriticalHitChancePercent", 12)]}},
    "gear-007": {"page_types": {"ocr-0013": "enhance"}, "fields": {"set": "DestructionSet", "slot": "Boots", "rank": "Epic", "level": 85, "enhance": 3, "main": _stats("Speed", 12), "substats": [_stats("HealthPercent", 7), _stats("EffectResistancePercent", 12), _stats("AttackPercent", 8), _stats("DefensePercent", 6)]}},
    "gear-008": {"page_types": {"ocr-0014": "enhance"}, "fields": {"set": "RiposteSet", "slot": "Boots", "rank": "Epic", "level": 85, "enhance": 4, "main": _stats("HealthPercent", 22), "substats": [_stats("EffectivenessPercent", 4), _stats("DefensePercent", 8), _stats("Speed", 7), _stats("CriticalHitDamagePercent", 7)]}},
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n" or handle.read(4) != b"\x00\x00\x00\r" or handle.read(4) != b"IHDR":
            raise ValueError(f"Not a PNG with IHDR: {path}")
        return struct.unpack(">II", handle.read(8))


def normal_stat(stat: dict) -> tuple[str, float]:
    return str(stat.get("type")), float(stat.get("value"))


def exact_matches(items: list[dict], fields: dict) -> list[dict]:
    target_substats = sorted(normal_stat(stat) for stat in fields["substats"])
    result = []
    for item in items:
        if (
            item.get("set") != fields["set"]
            or item.get("gear") != fields["slot"]
            or any(item.get(key) != fields[key] for key in ("rank", "level", "enhance"))
        ):
            continue
        if normal_stat(item.get("main") or {}) != normal_stat(fields["main"]):
            continue
        if sorted(normal_stat(stat) for stat in item.get("substats") or []) != target_substats:
            continue
        result.append(item)
    return result


def minimal_reference(item: dict) -> dict:
    return {
        "instanceId": str(item["ingameId"]), "set": item["set"], "slot": item["gear"], "rank": item["rank"],
        "level": item["level"], "enhance": item["enhance"], "main": item["main"],
        "substats": [{key: stat[key] for key in ("type", "value", "rolls") if key in stat} for stat in item["substats"]],
    }


def group_for_screenshot(screenshot_id: str) -> tuple[str, dict]:
    for group_id, group in GROUPS.items():
        if screenshot_id in group["page_types"]:
            return group_id, group
    raise KeyError(screenshot_id)


def build_batch(batch: Path, reference_path: Path) -> dict:
    screenshots = batch / "screenshots"
    reference_dir = batch / "references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    reference_payload = json.loads(reference_path.read_text(encoding="utf-8"))
    items = list(reference_payload.get("items") or [])
    instance_ids = [str(item.get("ingameId") or "") for item in items]
    raw_count = sum(isinstance(item.get("raw"), dict) and bool(item["raw"]) for item in items)
    if not items or len(instance_ids) != len(set(instance_ids)) or raw_count != len(items):
        raise ValueError("Reference must contain non-empty, unique instance IDs and raw payloads for every item")
    reference_meta = {
        "path": str(reference_path), "sha256": file_sha256(reference_path), "byte_size": reference_path.stat().st_size,
        "modified_at": datetime.fromtimestamp(reference_path.stat().st_mtime).isoformat(timespec="seconds"), "item_count": len(items),
        "instance_id_unique_count": len(set(instance_ids)), "raw_item_count": raw_count,
    }
    matched_by_group = {group_id: exact_matches(items, group["fields"]) for group_id, group in GROUPS.items()}
    manifest_rows = []
    seen_hashes: dict[str, str] = {}
    references = []
    reference_ids: set[str] = set()
    for index in range(1, 15):
        screenshot_id = f"ocr-{index:04d}"
        image_path = screenshots / f"{screenshot_id}.png"
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        group_id, group = group_for_screenshot(screenshot_id)
        capture = capture_from_file(image_path)
        source_sha256 = INPUT_SHA256[index - 1].lower()
        if capture["sha256"] != source_sha256:
            raise ValueError(f"Persisted screenshot hash mismatch for {screenshot_id}")
        width, height = png_dimensions(image_path)
        candidates = matched_by_group[group_id]
        if len(candidates) == 1:
            status, instance_id, reason = "matched", str(candidates[0]["ingameId"]), "unique_exact_visible_field_match"
            if instance_id not in reference_ids:
                references.append(minimal_reference(candidates[0])); reference_ids.add(instance_id)
        elif candidates:
            status, instance_id, reason = "ambiguous", None, "multiple_exact_visible_field_matches"
        else:
            status, instance_id, reason = "unmatched", None, f"stale_reference_possible:no_exact_visible_field_match_in_{reference_path.stem}"
        exact_duplicate_of = seen_hashes.setdefault(capture["sha256"], screenshot_id)
        manifest_rows.append({
            "screenshot_id": screenshot_id, "input_file_name": INPUT_FILENAMES[index - 1], "input_sha256": source_sha256, "file": f"screenshots/{image_path.name}", "sha256": capture["sha256"],
            "byte_size": capture["byte_size"], "width": width, "height": height, "page_type": group["page_types"][screenshot_id],
            "same_gear_group": group_id, "exact_duplicate_of": None if exact_duplicate_of == screenshot_id else exact_duplicate_of,
            "visible_fields_source": "manual_observation_for_pairing_not_ocr", "visible_fields": group["fields"],
            "match_status": status, "instanceId": instance_id, "candidate_count": len(candidates), "match_reason": reason,
            "candidate_instance_ids": [str(candidate["ingameId"]) for candidate in candidates],
            "capture_validation": {"sha256_matches_input": True, "sha256_matches_manifest": True, "click_performed": capture["click_performed"]},
        })
    matched_ids = {row["instanceId"] for row in manifest_rows if row["match_status"] == "matched" and row["instanceId"]}
    shadow_gate = {
        "status": "pairing_insufficient_for_ocr" if len(matched_ids) < 2 else "ocr_engine_required_for_shadow",
        "unique_matched_gear_count": len(matched_ids),
        "reason": "one_unique_gear_only" if len(matched_ids) < 2 else "no_ocr_engine_configured",
    }
    manifest = {"schema_version": 1, "batch": "ocr_stage1_batch_001", "mode": "read_only_pairing_no_ocr_engine", "reference": reference_meta, "ocr_shadow_gate": shadow_gate, "records": manifest_rows}
    (reference_dir / "matched_gears.json").write_text(json.dumps({"reference": reference_meta, "matched_gears": references}, ensure_ascii=False, indent=2), encoding="utf-8")
    (batch / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(manifest, batch)
    return manifest


def write_report(manifest: dict, batch: Path) -> None:
    rows = manifest["records"]
    source_name = Path(manifest["reference"]["path"]).name
    matched = [row for row in rows if row["match_status"] == "matched"]
    gate = manifest["ocr_shadow_gate"]
    lines = ["# OCR 第一批真实截图配对与只读影子核对", "", f"- 状态：`{gate['status']}`。本报告不包含 OCR 识别、字段置信度或准确率。", f"- 真实截图：14 张；分组：8 件；当前参考快照：`{source_name}`。", f"- 唯一匹配截图数：`{len(matched)}`，独立装备数：`{gate['unique_matched_gear_count']}`；原因：`{gate['reason']}`。其余截图按严格字段匹配保留 `unmatched`/`ambiguous`，不推测 instanceId。", "", "## 逐图清单", "", "| 截图 | 页面 | 分组 | 状态 | instanceId | 候选数 | 重复 |", "|---|---|---|---|---|---:|---|"]
    for row in rows:
        lines.append(f"| {row['screenshot_id']} | {row['page_type']} | {row['same_gear_group']} | {row['match_status']} | {row['instanceId'] or '-'} | {row['candidate_count']} | {row['exact_duplicate_of'] or '-'} |")
    lines += ["", "## 边界", "", "- 可见字段来自人工目读，仅用于同件真值匹配；没有被写为 OCR 输出。", "- `ocr-0006` 与 `ocr-0003`、`ocr-0008` 与 `ocr-0007` 字节完全相同，原图均保留。", "- `ocr-0010` 是副能力转换选择页，只记录当时可见值；未把它当作转换后的新结果。", "- 不存在 OCR 引擎，本批不生成置信度、字符准确率、建议对拍或任何游戏操作。", "", "产物：[`manifest.json`](../manual_acceptance/ocr_stage1/batch_001/manifest.json)、[`matched_gears.json`](../manual_acceptance/ocr_stage1/batch_001/references/matched_gears.json)。"]
    (ROOT / "reports" / "ocr_stage1_batch_001_pairing_20260721.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    args = parser.parse_args()
    manifest = build_batch(args.batch, args.reference)
    counts = {status: sum(row["match_status"] == status for row in manifest["records"]) for status in ("matched", "ambiguous", "unmatched")}
    print(json.dumps({"records": len(manifest["records"]), "counts": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
