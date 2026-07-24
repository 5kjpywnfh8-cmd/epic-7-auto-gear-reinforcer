"""真实人工验收样本的本地 JSON 存储与 CSV 导出。"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .gui_support import (
    DISPLAY_VALUE_LABELS,
    build_gear_dict,
    debug_view_model,
    form_from_gear_dict,
    is_fribbels_export,
    load_gear_collection_with_report,
    suggest_from_form,
    summary_view_model,
)


@dataclass
class ImportResult:
    imported: int = 0
    existing_added_to_batch: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    batch_id: str = ""
    batch_name: str = ""


ProgressCallback = Callable[[str, int, int], None]


class ManualSampleStore:
    """以 JSON 为事实来源，CSV 只用于 Excel/WPS 查看。"""

    def __init__(self, records_path: Path) -> None:
        self.records_path = Path(records_path)
        self.csv_path = self.records_path.with_suffix(".csv")
        self._data = self._load()

    def import_path(self, path: Path, progress: ProgressCallback | None = None) -> ImportResult:
        path = Path(path)
        self._report(progress, "读取 JSON", 0, 1)
        started = time.perf_counter()
        text = path.read_text(encoding="utf-8")
        read_ms = (time.perf_counter() - started) * 1000
        self._report(progress, "解析 JSON", 0, 1)
        started = time.perf_counter()
        payload = json.loads(text)
        parse_ms = (time.perf_counter() - started) * 1000
        if is_fribbels_export(payload):
            self._report(progress, "转换并校验装备", 0, 1)
            started = time.perf_counter()
            forms, _ = load_gear_collection_with_report(path)
            conversion_ms = (time.perf_counter() - started) * 1000
        else:
            self._report(progress, "转换并校验装备", 0, 1)
            started = time.perf_counter()
            forms = self._forms_from_payload(payload)
            conversion_ms = (time.perf_counter() - started) * 1000
        result = self.import_forms(
            forms,
            path.name,
            batch_metadata=self._batch_metadata_from_payload(payload, path.name),
            progress=progress,
        )
        result.timings_ms.update({
            "json_read": read_ms,
            "json_parse": parse_ms,
            "format_conversion_validation": conversion_ms,
        })
        return result

    def import_forms(
        self,
        forms: Iterable[dict[str, Any]],
        source_file: str,
        *,
        batch_metadata: dict[str, Any] | None = None,
        progress: ProgressCallback | None = None,
    ) -> ImportResult:
        forms = list(forms)
        result = ImportResult()
        batch, batch_created = self._ensure_batch(batch_metadata or self._compatibility_batch_metadata(source_file))
        result.batch_id = str(batch["batch_id"])
        result.batch_name = str(batch["batch_name"])
        original_source_file = str(batch.get("source_file") or source_file)
        changed = batch_created
        normalise_ms = 0.0
        suggestion_ms = 0.0
        total = len(forms)
        self._report(progress, "生成策略建议", 0, total)
        for index, raw_form in enumerate(forms, start=1):
            try:
                started = time.perf_counter()
                form = self._normalise_form(raw_form)
                gear = build_gear_dict(form)
                fingerprint = self._fingerprint(gear)
                normalise_ms += (time.perf_counter() - started) * 1000
                instance_id = str(form.get("instance_id") or "").strip()
                identity_key = f"instance:{instance_id}" if instance_id else f"fingerprint:{fingerprint}"
                record = self._find_record(identity_key)
                if record is None:
                    record = {
                        "sample_id": self._new_id("sample", identity_key),
                        "identity_key": identity_key,
                        "source_file": source_file,
                        "snapshots": [],
                    }
                    self._data["records"].append(record)

                if any(snapshot.get("fingerprint") == fingerprint for snapshot in record["snapshots"]):
                    snapshot = next(snapshot for snapshot in record["snapshots"] if snapshot.get("fingerprint") == fingerprint)
                    joined_batch = self._append_unique(snapshot, "acceptance_batch_ids", batch["batch_id"])
                    source_added = self._append_unique(snapshot, "original_source_files", original_source_file)
                    if joined_batch:
                        result.existing_added_to_batch += 1
                        changed = True
                    elif not source_added:
                        result.duplicates += 1
                    else:
                        changed = True
                    if self._needs_candidate_gs_refresh(snapshot):
                        started = time.perf_counter()
                        suggestion = suggest_from_form(form)
                        suggestion_ms += (time.perf_counter() - started) * 1000
                        summary = summary_view_model(suggestion)
                        snapshot["suggestion"] = suggestion
                        snapshot["summary_view"] = summary
                        snapshot["debug_view"] = debug_view_model(suggestion)
                        snapshot["updated_at"] = self._now()
                        changed = True
                    continue

                started = time.perf_counter()
                suggestion = suggest_from_form(form)
                suggestion_ms += (time.perf_counter() - started) * 1000
                now = self._now()
                summary = summary_view_model(suggestion)
                record["snapshots"].append(
                    {
                        "snapshot_id": self._new_id("snapshot", f"{record['sample_id']}:{fingerprint}"),
                        "fingerprint": fingerprint,
                        "source_file": source_file,
                        "original_source_files": [original_source_file],
                        "acceptance_batch_ids": [batch["batch_id"]],
                        "gear": gear,
                        "suggestion": suggestion,
                        "summary_view": summary,
                        "debug_view": debug_view_model(suggestion),
                        "human_review": self._initial_review(summary),
                        "review_status": "pending",
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                result.imported += 1
                changed = True
            except Exception as exc:
                result.errors.append(f"第 {index} 条：{self._chinese_error(str(exc))}")
            if index == total or index % 10 == 0:
                self._report(progress, "生成策略建议", index, total)
        result.timings_ms["normalise_deduplicate"] = normalise_ms
        result.timings_ms["suggestions"] = suggestion_ms
        if changed:
            result.timings_ms.update(self._save(progress))
        return result

    def list_snapshots(self) -> list[dict[str, Any]]:
        snapshots: list[dict[str, Any]] = []
        for record in self._data["records"]:
            for snapshot in record.get("snapshots") or []:
                original_source_files = self._string_list(
                    snapshot.get("original_source_files") or [snapshot.get("source_file") or record.get("source_file") or ""]
                )
                batch_ids = self._string_list(snapshot.get("acceptance_batch_ids"))
                snapshots.append({
                    **snapshot,
                    "sample_id": record["sample_id"],
                    "source_file": snapshot.get("source_file") or record.get("source_file") or "",
                    "original_source_files": original_source_files,
                    "acceptance_batch_ids": batch_ids,
                    "acceptance_batches": [
                        dict(self._data["batches"][batch_id])
                        for batch_id in batch_ids
                        if batch_id in self._data["batches"]
                    ],
                })
        return snapshots

    def list_batches(self) -> dict[str, dict[str, Any]]:
        return {batch_id: dict(metadata) for batch_id, metadata in self._data["batches"].items()}

    def update_review(
        self,
        sample_id: str,
        snapshot_id: str,
        *,
        decision: str,
        consistency: str,
        reason: str,
        note: str,
        progress: ProgressCallback | None = None,
    ) -> dict[str, float]:
        for record in self._data["records"]:
            if record.get("sample_id") != sample_id:
                continue
            for snapshot in record.get("snapshots") or []:
                if snapshot.get("snapshot_id") != snapshot_id:
                    continue
                snapshot["human_review"] = {
                    "decision": decision,
                    "consistency": consistency,
                    "reason": reason,
                    "note": note,
                }
                snapshot["review_status"] = "reviewed" if decision else "pending"
                snapshot["updated_at"] = self._now()
                return self._save(progress)
        raise ValueError("未找到需要保存的真实样本记录。")

    def _load(self) -> dict[str, Any]:
        if not self.records_path.exists():
            return {"version": 3, "batches": {}, "records": []}
        payload = json.loads(self.records_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            raise ValueError("真实样本记录文件格式无效。")
        if any(str(record.get("identity_key") or "").startswith("code:") for record in payload["records"]):
            raise ValueError("检测到旧版按 code 归并的真实样本记录，无法安全迁移。请备份后删除该记录文件，并从原始导出重新导入。")
        migrated = self._migrate_batch_metadata(payload)
        payload["version"] = 3
        if migrated:
            self.records_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self.records_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return payload

    def _save(self, progress: ProgressCallback | None = None) -> dict[str, float]:
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        self._report(progress, "写入 JSON", 0, 1)
        started = time.perf_counter()
        self._atomic_write(self.records_path, json.dumps(self._data, ensure_ascii=False, indent=2) + "\n")
        json_ms = (time.perf_counter() - started) * 1000
        self._report(progress, "生成 CSV", 0, 1)
        started = time.perf_counter()
        self._export_csv()
        csv_ms = (time.perf_counter() - started) * 1000
        self._report(progress, "完成", 1, 1)
        return {"json_write": json_ms, "csv_export": csv_ms}

    def _export_csv(self) -> None:
        fieldnames = [
            "样本编号", "快照编号", "来源文件", "原始数据来源", "验收批次", "批次用途", "批次标签", "装备实例编号", "装备类型编号", "装备来源", "品质", "强化等级", "套装", "部位", "主属性",
            "副属性1", "副属性1强化次数", "副属性2", "副属性2强化次数", "副属性3", "副属性3强化次数",
            "副属性4", "副属性4强化次数", "工具建议", "目标体系", "工具理由", "当前重铸前有效 GS", "当前重铸后有效 GS",
            "终局预期有效 GS（未转换）", "终局预期有效 GS（按转换满值）", "未转换正式体系低档达标概率", "正式体系低档达标概率",
            "转换满值 GS 增益", "转换满值来源", "人工判断", "一致性",
            "终局全部副属性预期 GS（未转换）", "终局全部副属性预期 GS（按转换满值）", "终局 75+ 未来可期门槛",
            "未转换终局 75+ 未来可期概率", "满值转换后终局 75+ 未来可期概率", "当前终局 75+ 未来可期概率", "当前终局目标", "当前终局目标概率",
            "分歧原因", "备注", "审核状态", "更新时间",
        ]
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", newline="", delete=False, dir=self.records_path.parent, suffix=".csv.tmp") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for snapshot in self.list_snapshots():
                writer.writerow(self._csv_row(snapshot))
            temporary = Path(handle.name)
        os.replace(temporary, self.csv_path)

    def _csv_row(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        gear = snapshot.get("gear") or {}
        main = gear.get("mainStat") or {}
        substats = list(gear.get("substats") or [])
        summary = snapshot.get("summary_view") or {}
        review = snapshot.get("human_review") or {}
        future_75 = ((snapshot.get("debug_view") or {}).get("lightweight_basis") or {}).get("终局 75+ 未来可期") or {}
        candidate = self._target_candidate_view(snapshot, summary)
        batches = list(snapshot.get("acceptance_batches") or [])
        row = {
            "样本编号": snapshot.get("sample_id", ""),
            "快照编号": snapshot.get("snapshot_id", ""),
            "来源文件": snapshot.get("source_file", ""),
            "原始数据来源": "、".join(snapshot.get("original_source_files") or []),
            "验收批次": "、".join(str(batch.get("batch_name") or batch.get("batch_id") or "") for batch in batches),
            "批次用途": "；".join(self._unique_strings(batch.get("purpose") for batch in batches)),
            "批次标签": "、".join(self._unique_strings(tag for batch in batches for tag in batch.get("tags") or [])),
            "装备实例编号": gear.get("instanceId", ""),
            "装备类型编号": gear.get("code", ""),
            "装备来源": self._display(gear.get("itemSource", "normal_85")),
            "品质": self._display(gear.get("rank", "")),
            "强化等级": gear.get("enhance", ""),
            "套装": self._display(gear.get("set", "")),
            "部位": self._display(gear.get("slot", "")),
            "主属性": f"{self._display(main.get('type', ''))} {main.get('value', '')}".strip(),
            "工具建议": summary.get("recommendation_label", ""),
            "目标体系": summary.get("target_profile", ""),
            "工具理由": "；".join(summary.get("reasons") or []),
            "当前重铸前有效 GS": candidate.get("当前重铸前有效 GS（按候选体系）", ""),
            "当前重铸后有效 GS": candidate.get("当前重铸后有效 GS（按候选体系）", ""),
            "终局预期有效 GS（未转换）": candidate.get("终局预期有效 GS（未转换）", ""),
            "终局预期有效 GS（按转换满值）": candidate.get("终局预期有效 GS（按转换满值）", ""),
            "未转换正式体系低档达标概率": candidate.get("未转换正式体系低档达标概率", ""),
            "正式体系低档达标概率": candidate.get("正式体系低档达标概率", ""),
            "转换满值 GS 增益": candidate.get("转换满值 GS 增益", ""),
            "转换满值来源": candidate.get("转换满值来源", ""),
            "终局全部副属性预期 GS（未转换）": future_75.get("终局全部副属性预期 GS（未转换）", ""),
            "终局全部副属性预期 GS（按转换满值）": future_75.get("终局全部副属性预期 GS（按转换满值）", ""),
            "终局 75+ 未来可期门槛": future_75.get("终局 75+ 未来可期门槛", ""),
            "未转换终局 75+ 未来可期概率": future_75.get("未转换终局 75+ 未来可期概率", ""),
            "满值转换后终局 75+ 未来可期概率": future_75.get("满值转换后终局 75+ 未来可期概率", ""),
            "当前终局 75+ 未来可期概率": future_75.get("当前终局 75+ 未来可期概率", ""),
            "当前终局目标": future_75.get("当前终局目标", ""),
            "当前终局目标概率": future_75.get("当前终局目标概率", ""),
            "人工判断": review.get("decision", ""),
            "一致性": review.get("consistency", ""),
            "分歧原因": review.get("reason", ""),
            "备注": review.get("note", ""),
            "审核状态": snapshot.get("review_status", "pending"),
            "更新时间": snapshot.get("updated_at", ""),
        }
        for index in range(4):
            stat = substats[index] if index < len(substats) else {}
            label = f"副属性{index + 1}"
            row[label] = f"{self._display(stat.get('type', ''))} {stat.get('value', '')}".strip()
            row[f"{label}强化次数"] = stat.get("rolls", "")
        return row

    @staticmethod
    def _target_candidate_view(snapshot: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
        basis = (snapshot.get("debug_view") or {}).get("lightweight_basis") or {}
        candidates = list(basis.get("候选体系评估") or [])
        target_profile = summary.get("target_profile")
        return next((item for item in candidates if item.get("体系") == target_profile), candidates[0] if candidates else {})

    @staticmethod
    def _needs_candidate_gs_refresh(snapshot: dict[str, Any]) -> bool:
        basis = (snapshot.get("debug_view") or {}).get("lightweight_basis") or {}
        candidates = basis.get("候选体系评估") or []
        return bool(candidates) and (
            "当前重铸前有效 GS（按候选体系）" not in candidates[0]
            or "终局 75+ 未来可期" not in basis
        )

    def _normalise_form(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("装备项必须是对象。")
        if "main_type" in payload:
            form = dict(payload)
            source = str(form.get("item_source") or "normal_85")
            form_from_gear_dict(build_gear_dict(form), item_source=source)
            return form
        source = str(payload.get("itemSource") or "normal_85")
        form = form_from_gear_dict(payload, item_source=source)
        form["item_source"] = source
        form["gear_source"] = str(payload.get("gearSource") or form.get("gear_source") or "")
        return form

    def _forms_from_payload(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            raise ValueError("导入文件必须是兼容的装备 JSON。")
        if isinstance(payload.get("gear"), dict):
            return [payload["gear"]]
        for key in ("items", "gears", "equipment"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        if "mainStat" in payload or "main" in payload or "main_type" in payload:
            return [payload]
        raise ValueError("未找到兼容的装备对象或 items/gears/equipment 集合。")

    def _batch_metadata_from_payload(self, payload: Any, source_file: str) -> dict[str, Any]:
        metadata = payload.get("acceptance_subset") if isinstance(payload, dict) else None
        if not isinstance(metadata, dict) or not str(metadata.get("batch_id") or "").strip():
            return self._compatibility_batch_metadata(source_file)
        batch_id = str(metadata["batch_id"]).strip()
        return {
            "batch_id": batch_id,
            "batch_name": str(metadata.get("batch_name") or batch_id).strip(),
            "purpose": str(metadata.get("purpose") or "").strip(),
            "source_file": str(metadata.get("source_file") or source_file).strip(),
            "selection_rule": str(metadata.get("selection_rule") or "").strip(),
            "tags": self._string_list(metadata.get("tags")),
        }

    def _compatibility_batch_metadata(self, source_file: str) -> dict[str, Any]:
        source_file = str(source_file or "未命名导入").strip() or "未命名导入"
        batch_id = self._new_id("import", source_file)
        return {
            "batch_id": batch_id,
            "batch_name": f"原始导入：{source_file}",
            "purpose": "兼容旧记录与普通导入文件的样本分组",
            "source_file": source_file,
            "selection_rule": "按导入文件名建立",
            "tags": ["原始导入"],
        }

    def _ensure_batch(self, metadata: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        batches = self._data.setdefault("batches", {})
        batch_id = str(metadata["batch_id"])
        existing = batches.get(batch_id)
        if isinstance(existing, dict):
            return existing, False
        batch = {
            "batch_id": batch_id,
            "batch_name": str(metadata.get("batch_name") or batch_id),
            "purpose": str(metadata.get("purpose") or ""),
            "source_file": str(metadata.get("source_file") or ""),
            "imported_at": self._now(),
            "selection_rule": str(metadata.get("selection_rule") or ""),
            "tags": self._string_list(metadata.get("tags")),
        }
        batches[batch_id] = batch
        return batch, True

    def _migrate_batch_metadata(self, payload: dict[str, Any]) -> bool:
        changed = payload.get("version") != 3 or not isinstance(payload.get("batches"), dict)
        if not isinstance(payload.get("batches"), dict):
            payload["batches"] = {}
        batches = payload["batches"]
        for record in payload["records"]:
            record_source = str(record.get("source_file") or "").strip()
            for snapshot in record.get("snapshots") or []:
                source_file = str(snapshot.get("source_file") or record_source).strip()
                original_sources = self._string_list(snapshot.get("original_source_files") or [source_file])
                if snapshot.get("original_source_files") != original_sources:
                    snapshot["original_source_files"] = original_sources
                    changed = True
                batch_ids = self._string_list(snapshot.get("acceptance_batch_ids"))
                if not batch_ids:
                    metadata = self._compatibility_batch_metadata(source_file)
                    batch_ids = [metadata["batch_id"]]
                    snapshot["acceptance_batch_ids"] = batch_ids
                    changed = True
                for batch_id in batch_ids:
                    if batch_id in batches:
                        continue
                    if batch_id == self._compatibility_batch_metadata(source_file)["batch_id"]:
                        metadata = self._compatibility_batch_metadata(source_file)
                    else:
                        metadata = {
                            "batch_id": batch_id,
                            "batch_name": batch_id,
                            "purpose": "从旧记录迁移的验收批次",
                            "source_file": source_file,
                            "selection_rule": "旧记录迁移",
                            "tags": ["旧记录迁移"],
                        }
                    batches[batch_id] = {
                        **metadata,
                        "imported_at": self._now(),
                        "tags": self._string_list(metadata.get("tags")),
                    }
                    changed = True
        return changed

    @staticmethod
    def _string_list(values: Any) -> list[str]:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, (list, tuple)):
            return []
        return ManualSampleStore._unique_strings(values)

    @staticmethod
    def _unique_strings(values: Iterable[Any]) -> list[str]:
        result: list[str] = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in result:
                result.append(text)
        return result

    @staticmethod
    def _append_unique(target: dict[str, Any], key: str, value: str) -> bool:
        values = ManualSampleStore._string_list(target.get(key))
        if value in values:
            target[key] = values
            return False
        values.append(value)
        target[key] = values
        return True

    def _find_record(self, identity_key: str) -> dict[str, Any] | None:
        return next((record for record in self._data["records"] if record.get("identity_key") == identity_key), None)

    @staticmethod
    def _fingerprint(gear: dict[str, Any]) -> str:
        normalised = json.dumps(gear, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()

    @staticmethod
    def _new_id(prefix: str, value: str) -> str:
        return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _initial_review(summary: dict[str, Any]) -> dict[str, str]:
        return {"decision": "", "consistency": "", "reason": "", "note": ""}

    @staticmethod
    def _display(value: Any) -> str:
        text = str(value or "")
        return DISPLAY_VALUE_LABELS.get(text, text)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)

    @staticmethod
    def _chinese_error(message: str) -> str:
        replacements = {
            "rift_85 only supports Epic": "异界 85 仅支持红装（Epic）。",
            "Invalid substats": "副属性不符合该部位规则。",
            "Duplicate substats": "副属性不能重复。",
        }
        for source, target in replacements.items():
            if source in message:
                return target
        return message

    @staticmethod
    def _report(progress: ProgressCallback | None, stage: str, current: int, total: int) -> None:
        if progress is not None:
            progress(stage, current, total)
