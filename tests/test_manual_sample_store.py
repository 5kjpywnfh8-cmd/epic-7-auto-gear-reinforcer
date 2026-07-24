import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from src.e7_enhance.gui_support import build_gear_dict, load_gear_file
from src.e7_enhance.manual_sample_store import ManualSampleStore


class ManualSampleStoreTest(unittest.TestCase):
    def setUp(self):
        self.form = load_gear_file(Path("建议结果/14.json"))

    def test_import_persists_suggestion_and_exports_csv_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            store = ManualSampleStore(records_path)
            form = deepcopy(self.form)
            form["instance_id"] = "ingame-csv-test"

            first = store.import_forms([form], "export.json")
            second = store.import_forms([form], "export.json")

            self.assertEqual(first.imported, 1)
            self.assertEqual(second.duplicates, 1)
            snapshots = store.list_snapshots()
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0]["summary_view"]["recommendation"], "cautious_continue")
            self.assertEqual(snapshots[0]["summary_view"]["target_profile"], "输出")
            self.assertIn("debug", snapshots[0]["suggestion"])

            with store.csv_path.open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["工具建议"], "谨慎继续")
            self.assertEqual(row["目标体系"], "输出")
            self.assertEqual(row["装备实例编号"], "ingame-csv-test")
            self.assertEqual(row["当前重铸前有效 GS"], "24.0")
            self.assertEqual(row["终局预期有效 GS（未转换）"], "52.2")
            self.assertEqual(row["终局预期有效 GS（按转换满值）"], "64.3")
            self.assertEqual(row["终局 75+ 未来可期门槛"], "75.0")
            self.assertTrue(row["未转换终局 75+ 未来可期概率"])
            self.assertTrue(row["满值转换后终局 75+ 未来可期概率"])
            self.assertEqual(row["当前终局目标"], "正式体系")
            self.assertTrue(row["副属性1"])

    def test_same_code_different_instance_ids_do_not_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManualSampleStore(Path(tmp) / "records.json")
            first = deepcopy(self.form)
            first["code"] = "same-type-code"
            first["instance_id"] = "ingame-1"
            second = deepcopy(first)
            second["instance_id"] = "ingame-2"

            result = store.import_forms([first, second], "export.json")

            self.assertEqual(result.imported, 2)
            snapshots = store.list_snapshots()
            self.assertEqual(len(snapshots), 2)
            self.assertNotEqual(snapshots[0]["sample_id"], snapshots[1]["sample_id"])

    def test_reimport_refreshes_legacy_snapshot_missing_candidate_gs(self):
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            form = deepcopy(self.form)
            form["instance_id"] = "ingame-refresh-test"
            store = ManualSampleStore(records_path)
            store.import_forms([form], "export.json")
            snapshot = store._data["records"][0]["snapshots"][0]
            snapshot["debug_view"]["lightweight_basis"]["候选体系评估"][0].pop("当前重铸前有效 GS（按候选体系）", None)
            records_path.write_text(json.dumps(store._data, ensure_ascii=False), encoding="utf-8")

            reloaded = ManualSampleStore(records_path)
            result = reloaded.import_forms([form], "export.json")
            refreshed = reloaded.list_snapshots()[0]

            self.assertEqual(result.duplicates, 1)
            self.assertEqual(
                refreshed["debug_view"]["lightweight_basis"]["候选体系评估"][0]["当前重铸前有效 GS（按候选体系）"],
                24.0,
            )

    def test_same_instance_id_keeps_later_enhancement_as_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManualSampleStore(Path(tmp) / "records.json")
            early = deepcopy(self.form)
            early["code"] = "type-code"
            early["instance_id"] = "ingame-1"
            later = deepcopy(early)
            later["enhance"] = 6
            later["substats"][0]["rolls"] = 3

            result = store.import_forms([early, later], "export.json")

            self.assertEqual(result.imported, 2)
            snapshots = store.list_snapshots()
            self.assertEqual(len(snapshots), 2)
            self.assertEqual({item["sample_id"] for item in snapshots}, {snapshots[0]["sample_id"]})

    def test_same_instance_id_and_state_is_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManualSampleStore(Path(tmp) / "records.json")
            form = deepcopy(self.form)
            form["instance_id"] = "ingame-1"

            first = store.import_forms([form], "export.json")
            second = store.import_forms([form], "export.json")

            self.assertEqual(first.imported, 1)
            self.assertEqual(second.duplicates, 1)
            self.assertEqual(len(store.list_snapshots()), 1)

    def test_existing_snapshot_joins_acceptance_batch_without_overwriting_original_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            form = deepcopy(self.form)
            form["instance_id"] = "ingame-batch-test"
            store = ManualSampleStore(directory / "records.json")
            first = store.import_forms([form], "original_fribbels.json")
            subset = {
                "acceptance_subset": {
                    "batch_id": "heroic_resource_fallback_20260712",
                    "batch_name": "Heroic 资源回退验收（2026-07-12）",
                    "purpose": "检查基础策略回退",
                    "source_file": "original_fribbels.json",
                    "selection_rule": "测试子集",
                    "tags": ["紫装", "资源回退"],
                },
                "items": [build_gear_dict(form)],
            }
            subset_path = directory / "heroic_subset.json"
            subset_path.write_text(json.dumps(subset, ensure_ascii=False), encoding="utf-8")

            joined = store.import_path(subset_path)
            duplicate = store.import_path(subset_path)
            snapshot = store.list_snapshots()[0]

            self.assertEqual(first.imported, 1)
            self.assertEqual(joined.imported, 0)
            self.assertEqual(joined.existing_added_to_batch, 1)
            self.assertEqual(duplicate.duplicates, 1)
            self.assertEqual(len(store.list_snapshots()), 1)
            self.assertEqual(snapshot["source_file"], "original_fribbels.json")
            self.assertEqual(snapshot["original_source_files"], ["original_fribbels.json"])
            self.assertIn("heroic_resource_fallback_20260712", snapshot["acceptance_batch_ids"])
            self.assertEqual(len(snapshot["acceptance_batch_ids"]), 2)
            self.assertEqual(snapshot["gear"]["itemSource"], "normal_85")
            self.assertEqual(store.list_batches()["heroic_resource_fallback_20260712"]["batch_name"], "Heroic 资源回退验收（2026-07-12）")
            with store.csv_path.open(encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["原始数据来源"], "original_fribbels.json")
            self.assertIn("Heroic 资源回退验收（2026-07-12）", row["验收批次"])
            self.assertIn("检查基础策略回退", row["批次用途"])
            self.assertIn("紫装", row["批次标签"])

    def test_legacy_records_migrate_to_compatible_batches_without_losing_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            form = deepcopy(self.form)
            form["instance_id"] = "ingame-legacy-batch"
            store = ManualSampleStore(records_path)
            store.import_forms([form], "legacy_source.json")
            snapshot = store._data["records"][0]["snapshots"][0]
            snapshot["human_review"] = {"decision": "continue", "consistency": "一致", "reason": "", "note": "保留"}
            snapshot["review_status"] = "reviewed"
            sample_id = store._data["records"][0]["sample_id"]
            snapshot_id = snapshot["snapshot_id"]
            snapshot.pop("acceptance_batch_ids", None)
            snapshot.pop("original_source_files", None)
            store._data.pop("batches", None)
            store._data["version"] = 2
            records_path.write_text(json.dumps(store._data, ensure_ascii=False), encoding="utf-8")

            migrated = ManualSampleStore(records_path)
            saved = migrated.list_snapshots()[0]

            self.assertEqual(saved["human_review"]["decision"], "continue")
            self.assertEqual(saved["human_review"]["note"], "保留")
            self.assertEqual(saved["review_status"], "reviewed")
            self.assertEqual(saved["sample_id"], sample_id)
            self.assertEqual(saved["snapshot_id"], snapshot_id)
            self.assertEqual(saved["original_source_files"], ["legacy_source.json"])
            self.assertEqual(len(saved["acceptance_batch_ids"]), 1)
            self.assertEqual(len(migrated.list_batches()), 1)

    def test_missing_instance_id_only_deduplicates_identical_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManualSampleStore(Path(tmp) / "records.json")
            early = deepcopy(self.form)
            early["code"] = "same-type-code"
            early["instance_id"] = ""
            later = deepcopy(early)
            later["enhance"] = 6
            later["substats"][0]["rolls"] = 3

            result = store.import_forms([early, later, early], "export.json")

            self.assertEqual(result.imported, 2)
            self.assertEqual(result.duplicates, 1)
            snapshots = store.list_snapshots()
            self.assertEqual(len(snapshots), 2)
            self.assertNotEqual(snapshots[0]["sample_id"], snapshots[1]["sample_id"])

    def test_real_fribbels_subset_creates_425_samples_and_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManualSampleStore(Path(tmp) / "records.json")

            result = store.import_path(Path("samples/real_acceptance_fribbels_20260610_plus0_plus3.json"))

            self.assertEqual(result.imported, 425)
            self.assertEqual(result.errors, [])
            snapshots = store.list_snapshots()
            self.assertEqual(len(snapshots), 425)
            self.assertEqual(len({item["sample_id"] for item in snapshots}), 425)
            self.assertEqual(len({item["gear"].get("instanceId") for item in snapshots}), 425)

    def test_heroic_acceptance_subset_adds_batch_membership_without_new_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ManualSampleStore(Path(tmp) / "records.json")
            original = store.import_path(Path("samples/real_acceptance_fribbels_20260610_plus0_plus3.json"))
            heroic = store.import_path(Path("samples/heroic_resource_fallback_acceptance_20260712.json"))
            snapshots = store.list_snapshots()
            heroic_members = [
                snapshot for snapshot in snapshots
                if "heroic_resource_fallback_20260712" in snapshot["acceptance_batch_ids"]
            ]

            self.assertEqual(original.imported, 425)
            self.assertEqual(heroic.imported, 0)
            self.assertEqual(heroic.existing_added_to_batch, 16)
            self.assertEqual(len(snapshots), 425)
            self.assertEqual(len(heroic_members), 16)
            self.assertTrue(all(snapshot["source_file"] == "real_acceptance_fribbels_20260610_plus0_plus3.json" for snapshot in heroic_members))

    def test_legacy_code_grouped_records_are_rejected_for_safe_reimport(self):
        legacy_payload = {
            "version": 1,
            "records": [
                {
                    "sample_id": "sample-legacy",
                    "identity_key": "code:ecp6n",
                    "source_file": "old.json",
                    "snapshots": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            records_path = Path(tmp) / "records.json"
            records_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "旧版按 code 归并"):
                ManualSampleStore(records_path)

    def test_review_survives_reload_and_invalid_batch_item_does_not_block_valid_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            records_path = directory / "records.json"
            valid = build_gear_dict(self.form)
            invalid = deepcopy(valid)
            invalid["itemSource"] = "rift_85"
            invalid["rank"] = "Heroic"
            import_path = directory / "batch.json"
            import_path.write_text(json.dumps({"items": [valid, invalid]}), encoding="utf-8")

            store = ManualSampleStore(records_path)
            result = store.import_path(import_path)
            snapshot = store.list_snapshots()[0]
            store.update_review(
                snapshot["sample_id"],
                snapshot["snapshot_id"],
                decision="continue",
                consistency="不完全一致",
                reason="目标体系错误",
                note="人工复核备注",
            )

            reloaded = ManualSampleStore(records_path)
            saved = reloaded.list_snapshots()[0]
            self.assertEqual(result.imported, 1)
            self.assertEqual(len(result.errors), 1)
            self.assertEqual(saved["human_review"]["decision"], "continue")
            self.assertEqual(saved["human_review"]["note"], "人工复核备注")

    def test_import_path_accepts_single_collection_and_saved_suggestion_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            gear = build_gear_dict(self.form)
            paths = {
                "single.json": gear,
                "collection.json": {"equipment": [gear]},
                "suggestion.json": {"gear": gear, "suggestion": {"summary": {}}},
            }
            store = ManualSampleStore(directory / "records.json")
            results = []
            for name, payload in paths.items():
                path = directory / name
                path.write_text(json.dumps(payload), encoding="utf-8")
                results.append(store.import_path(path))

            self.assertEqual(results[0].imported, 1)
            self.assertEqual(results[1].existing_added_to_batch, 1)
            self.assertEqual(results[2].existing_added_to_batch, 1)
            self.assertEqual(len(store.list_snapshots()), 1)


if __name__ == "__main__":
    unittest.main()
