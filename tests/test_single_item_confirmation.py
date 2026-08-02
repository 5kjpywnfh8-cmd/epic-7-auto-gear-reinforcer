from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.single_item_confirmation import (
    discover_operation_manifests,
    render_markdown,
    summarize_manifests,
    validate_operation_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
OPERATION = ROOT / "manual_acceptance/single_item_confirmation/operation_004_plus3_20260723_153606/operation_manifest.json"
OPERATION_013 = ROOT / "manual_acceptance/single_item_confirmation/operation_013_plus3_20260724_112042/operation_manifest.json"
PAIRING = ROOT / "manual_acceptance/single_item_confirmation/preflight_20260723_102914/pair_batch_004.json"


class SingleItemConfirmationTest(unittest.TestCase):
    def test_completed_operation_is_verified_against_pairing_baseline(self):
        result = validate_operation_manifest(OPERATION)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["target"]["batch"], "004")
        self.assertEqual(result["target"]["instance_id"], "4181490939")
        self.assertEqual(result["baseline"]["gear_score"], 27)
        self.assertEqual(result["actual"]["gear_score"], 37)
        self.assertEqual(result["checkpoint"], {"requested": 3, "reached": 3, "matches": True})
        self.assertEqual(result["resources"]["gold"]["consumed"], 17600)
        self.assertTrue(result["resources"]["within_limits"])
        self.assertIn("substats[AttackPercent].value", {item["field"] for item in result["attribute_changes"]})
        self.assertFalse(result["formal_strategy_modified"])

    def test_hash_mismatch_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            operation_dir = base / "operation"
            pairing_dir = base / "preflight"
            operation_dir.mkdir()
            pairing_dir.mkdir()
            manifest = json.loads(OPERATION.read_text(encoding="utf-8"))
            manifest["trusted_reference"]["player_data_sha256"] = "bad-hash"
            manifest["trusted_reference"]["pairing_output"] = "../preflight/pair.json"
            (operation_dir / "operation_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (pairing_dir / "pair.json").write_text(PAIRING.read_text(encoding="utf-8"), encoding="utf-8")

            result = validate_operation_manifest(operation_dir / "operation_manifest.json")

        self.assertEqual(result["status"], "fail_closed")
        self.assertIn("trusted_snapshot_identity_mismatch", result["fail_closed_reasons"])

    def test_resource_limit_mismatch_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            operation_dir = base / "operation"
            pairing_dir = base / "preflight"
            operation_dir.mkdir()
            pairing_dir.mkdir()
            manifest = json.loads(OPERATION.read_text(encoding="utf-8"))
            manifest["trusted_reference"]["pairing_output"] = "../preflight/pair.json"
            manifest["authorization"]["resource_limits"]["gold"] = 17599
            (operation_dir / "operation_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (pairing_dir / "pair.json").write_text(PAIRING.read_text(encoding="utf-8"), encoding="utf-8")

            result = validate_operation_manifest(operation_dir / "operation_manifest.json")

        self.assertEqual(result["status"], "fail_closed")
        self.assertIn("gold_limit_exceeded", result["fail_closed_reasons"])

    def test_aggregate_and_markdown_keep_scope_officially_read_only(self):
        summary = summarize_manifests([OPERATION, OPERATION_013])

        self.assertEqual(summary["status"], "verified")
        self.assertEqual(summary["verified_count"], 2)
        self.assertFalse(summary["formal_strategy_modified"])
        markdown = render_markdown(summary)
        self.assertIn("不代表正式策略、DP、评分或自动化发布结论", markdown)
        self.assertIn("batch 004", markdown)
        self.assertIn("batch 013", markdown)

    def test_discovery_only_returns_operation_manifests(self):
        paths = discover_operation_manifests(ROOT / "manual_acceptance/single_item_confirmation")

        self.assertEqual(paths, [OPERATION, OPERATION_013])


if __name__ == "__main__":
    unittest.main()
