from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.e7_enhance.fresh_snapshot_contract import (
    MIN_OCR_CONFIDENCE,
    SNAPSHOT_SCHEMA,
    canonical_json_sha256,
    render_markdown,
    validate_snapshot_contract,
    write_report,
)


def _item(identity: str, node: int) -> dict:
    return {
        "ingameId": identity,
        "set": "set_shield",
        "gear": "Boots",
        "rank": "Rare",
        "level": 85,
        "enhance": node,
        "main": {"type": "Health", "value": 540 if node == 0 else 2700},
        "substats": [
            {"type": "EffectivenessPercent", "value": 6},
            {"type": "HealthPercent", "value": 5},
        ],
    }


def _player(items: list[dict]) -> dict:
    return {
        "schema": "epic7_tools.player_data",
        "schema_version": "1.2",
        "source": {"reader": "synthetic"},
        "counts": {"items": len(items)},
        "completeness": {"items": True},
        "items": items,
    }


def _reader(items: list[dict]) -> dict:
    return {
        "data": {
            "items": [
                {
                    **item,
                    "raw": {
                        "op": ["event"] * (3 + item["enhance"] // 3),
                        "mainStatBaseValue": 540,
                    },
                }
                for item in items
            ]
        }
    }


def snapshot(node: int, identity: str = "target", operation_id: str = "operation-001") -> dict:
    item = _item(identity, node)
    player_data = _player([item])
    reader_result = _reader([item])
    visible_main = {"type": "Health", "value": 540 if node == 0 else 2700}
    return {
        "schema_version": SNAPSHOT_SCHEMA,
        "operation_id": operation_id,
        "previous_node": None if node == 0 else node - 3,
        "current_node": node,
        "expected_next_node": None if node == 15 else node + 3,
        "snapshot_id": f"snapshot-{node}",
        "collection_id": f"collection-{node}",
        "collected_at": f"2026-07-25T00:{node:02d}:00+00:00",
        "source_status": "current_same_batch_player_data",
        "operation_result": "initial_snapshot" if node == 0 else "enhancement_completed",
        "files": {
            "player_data": {
                "path_id": f"synthetic/{node}/player_data.json",
                "batch_id": f"batch-{node}",
                "sha256": canonical_json_sha256(player_data),
            },
            "reader_result": {
                "path_id": f"synthetic/{node}/reader_result.json",
                "batch_id": f"batch-{node}",
                "sha256": canonical_json_sha256(reader_result),
            },
        },
        "player_data": player_data,
        "reader_result": reader_result,
        "page": {
            "page_type": "enhance_equipment",
            "is_unambiguous": True,
            "target_visible": True,
        },
        "target": {
            "instance_id": identity,
            "visible_fields": {
                "set": "ShieldSet",
                "slot": "Boots",
                "rank": "Rare",
                "level": 85,
                "enhance": node,
                "main": visible_main,
                "substats": item["substats"],
            },
            "ocr_confidence": {
                "set": MIN_OCR_CONFIDENCE,
                "slot": MIN_OCR_CONFIDENCE,
                "rank": MIN_OCR_CONFIDENCE,
                "level": MIN_OCR_CONFIDENCE,
                "enhance": MIN_OCR_CONFIDENCE,
                "main": MIN_OCR_CONFIDENCE,
                "substats": MIN_OCR_CONFIDENCE,
            },
        },
        "advice_hash": canonical_json_sha256({"node": node, "kind": "synthetic"}),
    }


def snapshots() -> list[dict]:
    return [snapshot(node) for node in (0, 3, 6, 9, 12, 15)]


class FreshSnapshotContractTest(unittest.TestCase):
    def assert_fail_closed_without_continuation(self, report: dict) -> None:
        self.assertEqual(report["status"], "fail_closed")
        for record in report["records"]:
            if record["status"] == "fail_closed":
                self.assertIsNone(record["continuation_recommendation"])

    def test_full_standard_node_sequence_is_verified_and_non_executable(self):
        report = validate_snapshot_contract(snapshots())

        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["verified_count"], 6)
        self.assertEqual([record["current_node"] for record in report["records"]], [0, 3, 6, 9, 12, 15])
        self.assertTrue(all(record["continuation_recommendation"] is None for record in report["records"]))
        self.assertFalse(report["formal_strategy_modified"])

    def test_nonzero_node_cannot_start_a_snapshot_chain(self):
        for node in (3, 6, 15):
            report = validate_snapshot_contract([snapshot(node)])
            self.assert_fail_closed_without_continuation(report)
            self.assertIn("initial_plus0_node_missing", report["records"][0]["fail_closed_reasons"])

    def test_zero_and_multiple_pairing_candidates_fail_closed(self):
        zero = snapshot(0)
        zero["target"]["visible_fields"]["main"]["value"] = 541
        multiple = snapshot(0)
        duplicate = _item("other", 0)
        multiple["player_data"] = _player([_item("target", 0), duplicate])
        multiple["reader_result"] = _reader(multiple["player_data"]["items"])
        multiple["player_data"]["counts"]["items"] = 2
        multiple["files"]["player_data"]["sha256"] = canonical_json_sha256(multiple["player_data"])
        multiple["files"]["reader_result"]["sha256"] = canonical_json_sha256(multiple["reader_result"])

        for value in (zero, multiple):
            report = validate_snapshot_contract([value])
            record = report["records"][0]
            self.assert_fail_closed_without_continuation(report)
            self.assertIn("pairing_candidate_not_unique", record["fail_closed_reasons"])

    def test_page_and_confidence_gates_fail_closed(self):
        bad_page = snapshot(0)
        bad_page["page"]["is_unambiguous"] = False
        low_confidence = snapshot(0)
        low_confidence["target"]["ocr_confidence"]["main"] = 0.97

        page_report = validate_snapshot_contract([bad_page])
        confidence_report = validate_snapshot_contract([low_confidence])
        self.assert_fail_closed_without_continuation(page_report)
        self.assert_fail_closed_without_continuation(confidence_report)
        self.assertIn("page_not_unambiguous_target_enhance_page", page_report["records"][0]["fail_closed_reasons"])
        self.assertIn("ocr_confidence_below_threshold_or_missing", confidence_report["records"][0]["fail_closed_reasons"])

    def test_cross_batch_and_hash_mismatch_fail_closed(self):
        cross_batch = snapshot(0)
        cross_batch["files"]["reader_result"]["batch_id"] = "other-batch"
        hash_mismatch = snapshot(0)
        hash_mismatch["files"]["player_data"]["sha256"] = "0" * 64

        batch_report = validate_snapshot_contract([cross_batch])
        hash_report = validate_snapshot_contract([hash_mismatch])
        self.assert_fail_closed_without_continuation(batch_report)
        self.assert_fail_closed_without_continuation(hash_report)
        self.assertIn("player_and_reader_not_same_batch", batch_report["records"][0]["fail_closed_reasons"])
        self.assertIn("player_data_hash_mismatch", hash_report["records"][0]["fail_closed_reasons"])

    def test_reused_snapshot_and_advice_evidence_fail_closed(self):
        repeated_snapshot = snapshots()[:2]
        repeated_snapshot[1]["snapshot_id"] = repeated_snapshot[0]["snapshot_id"]
        repeated_snapshot[1]["collection_id"] = repeated_snapshot[0]["collection_id"]
        repeated_snapshot[1]["advice_hash"] = repeated_snapshot[0]["advice_hash"]
        report = validate_snapshot_contract(repeated_snapshot)

        self.assert_fail_closed_without_continuation(report)
        self.assertIn("snapshot_or_collection_id_reused", report["records"][1]["fail_closed_reasons"])
        self.assertIn("prior_advice_hash_reused", report["records"][1]["fail_closed_reasons"])

    def test_reused_file_hash_and_node_jump_fail_closed(self):
        values = snapshots()[:2]
        values[1]["files"]["player_data"]["sha256"] = values[0]["files"]["player_data"]["sha256"]
        values[1]["files"]["reader_result"]["sha256"] = values[0]["files"]["reader_result"]["sha256"]
        report = validate_snapshot_contract(values)
        self.assert_fail_closed_without_continuation(report)
        self.assertIn("prior_snapshot_file_hash_reused", report["records"][1]["fail_closed_reasons"])

        jump = [snapshot(0), snapshot(6)]
        report = validate_snapshot_contract(jump)
        self.assert_fail_closed_without_continuation(report)
        self.assertIn("node_sequence_jump", report["records"][1]["fail_closed_reasons"])

    def test_instance_drift_and_unknown_result_fail_closed(self):
        drift = [snapshot(0), snapshot(3, identity="other")]
        report = validate_snapshot_contract(drift)
        self.assert_fail_closed_without_continuation(report)
        self.assertIn("target_instance_drift", report["records"][1]["fail_closed_reasons"])

        unknown = snapshot(3)
        unknown["operation_result"] = "unknown"
        report = validate_snapshot_contract([snapshot(0), unknown])
        self.assert_fail_closed_without_continuation(report)
        self.assertIn("operation_result_unknown_or_incompatible", report["records"][1]["fail_closed_reasons"])

        previous_unknown = snapshot(0)
        previous_unknown["operation_result"] = "unknown"
        report = validate_snapshot_contract([previous_unknown, snapshot(3)])
        self.assert_fail_closed_without_continuation(report)
        self.assertIn("previous_node_not_verified", report["records"][1]["fail_closed_reasons"])

    def test_empty_input_is_not_ready_and_report_is_stable_and_sanitized(self):
        report = validate_snapshot_contract([])
        self.assertEqual(report["status"], "not_ready")
        markdown = render_markdown(report)
        self.assertIn("未提供可验证的新鲜节点快照", markdown)
        self.assertNotIn("synthetic/", markdown)

        with TemporaryDirectory() as temporary:
            output_json = Path(temporary) / "report.json"
            output_md = Path(temporary) / "report.md"
            write_report(report, output_json, output_md)
            first = output_json.read_text(encoding="utf-8")
            write_report(report, output_json, output_md)
            self.assertEqual(first, output_json.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(first), report)


if __name__ == "__main__":
    unittest.main()
