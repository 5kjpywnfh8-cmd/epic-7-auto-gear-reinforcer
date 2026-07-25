import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.policy_manifest import (
    BEHAVIOR_INPUTS,
    PolicyManifestError,
    REGRESSION_EVIDENCE_PATH,
    REGRESSION_EXECUTION_INPUTS,
    REGRESSION_TEST_INPUTS,
    build_policy_manifest,
    write_policy_manifest,
)
from src.e7_enhance.strategy_defaults import STRATEGY_VERSION


ROOT = Path(__file__).resolve().parents[1]


class PolicyManifestTest(unittest.TestCase):
    def test_manifest_records_supported_scope_and_all_readiness_gates(self):
        manifest = build_policy_manifest(ROOT, generated_on="2026-07-25")

        self.assertEqual(manifest["schema_version"], "e7_enhance.policy_manifest/1.0")
        self.assertEqual(manifest["strategy_version"], STRATEGY_VERSION)
        self.assertEqual(manifest["freeze_status"], "ready")
        self.assertEqual(manifest["readiness"]["gaps"], [])
        self.assertTrue(all(manifest["readiness"]["gates"].values()))
        self.assertEqual(manifest["regression_evidence"]["status"], "attached_verified")
        self.assertEqual(manifest["supported_inputs"]["enhancement_checkpoints"], [0, 3, 6, 9, 12, 15])
        self.assertEqual(
            {(row["item_source"], row["rank"]) for row in manifest["supported_inputs"]["item_source_ranks"]},
            {("normal_85", "Epic"), ("normal_85", "Heroic"), ("rift_85", "Epic")},
        )

    def test_epic_early_stop_details_expand_all_frozen_groups_and_joint_checks(self):
        manifest = build_policy_manifest(ROOT, generated_on="2026-07-25")
        details = manifest["policy_details"]["epic_non_speed_early_stop"]

        self.assertEqual(details["candidate_key"], "output_8_13_tank_10_17")
        self.assertEqual(details["scope"]["checkpoints"], [0, 3])
        self.assertEqual(details["scope"]["excluded_slots"], ["boot"])
        self.assertEqual(details["scope"]["initial_speed"], "lt_2")
        self.assertTrue(details["activation"]["require_all"])
        self.assertEqual(
            [row["system_group"] for row in details["threshold_groups"]],
            ["pure_output", "pure_tank", "default"],
        )
        self.assertEqual(
            [row["effective_gs_max"] for row in details["threshold_groups"]],
            [{"0": 8.0, "3": 13.0}, {"0": 10.0, "3": 17.0}, {"0": 12.0, "3": 17.0}],
        )
        self.assertIn("unknown_candidate", details["threshold_groups"][2]["categories"])
        self.assertEqual(details["unknown_set_contract"], "rejected_before_candidate_evaluation")

        early_routes = [
            row
            for row in manifest["decision_routes"]
            if row["item_source"] == "normal_85"
            and row["rank"] == "Epic"
            and row["checkpoint"] in (0, 3)
        ]
        self.assertTrue(all(row["policy_detail_ref"] == "epic_non_speed_early_stop" for row in early_routes))

    def test_manifest_hash_is_stable_across_generation_dates(self):
        first = build_policy_manifest(ROOT, generated_on="2026-07-25")
        second = build_policy_manifest(ROOT, generated_on="2026-07-26")

        self.assertNotEqual(first["generated_on"], second["generated_on"])
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])

    def test_behavior_input_change_changes_manifest_hash(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative_path in BEHAVIOR_INPUTS:
                source = ROOT / relative_path
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            first = build_policy_manifest(root, generated_on="2026-07-25")
            changed_path = root / BEHAVIOR_INPUTS[0]
            changed_path.write_bytes(changed_path.read_bytes() + b"\n")
            second = build_policy_manifest(root, generated_on="2026-07-25")

        self.assertNotEqual(first["manifest_sha256"], second["manifest_sha256"])

    def test_route_matrix_has_unique_complete_coverage(self):
        manifest = build_policy_manifest(ROOT, generated_on="2026-07-25")
        routes = manifest["decision_routes"]
        route_keys = {
            (row["item_source"], row["rank"], row["checkpoint"], row["segment"])
            for row in routes
        }

        self.assertEqual(len(routes), 21)
        self.assertEqual(len(route_keys), len(routes))
        for item_source, rank in (("normal_85", "Epic"), ("normal_85", "Heroic"), ("rift_85", "Epic")):
            for checkpoint in (0, 3, 6, 9, 12, 15):
                self.assertTrue(
                    any(
                        row["item_source"] == item_source
                        and row["rank"] == rank
                        and row["checkpoint"] == checkpoint
                        for row in routes
                    )
                )
        for checkpoint in (6, 9, 12):
            heroic = [
                row
                for row in routes
                if row["item_source"] == "normal_85"
                and row["rank"] == "Heroic"
                and row["checkpoint"] == checkpoint
            ]
            self.assertEqual({row["segment"] for row in heroic}, {"non_boot_with_speed", "fallback"})
            self.assertEqual(
                {row["owner"] for row in heroic},
                {"heroic_speed22_rescue", "baseline_policy"},
            )

    def test_behavior_input_hashes_match_files(self):
        manifest = build_policy_manifest(ROOT, generated_on="2026-07-25")

        self.assertEqual([row["path"] for row in manifest["behavior_inputs"]], sorted(BEHAVIOR_INPUTS))
        for row in manifest["behavior_inputs"]:
            expected = hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
            self.assertEqual(row["sha256"], expected)

    def test_write_policy_manifest_outputs_parseable_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            json_path = output_root / "manifest.json"
            markdown_path = output_root / "manifest.md"

            manifest = write_policy_manifest(
                ROOT,
                json_path=json_path,
                markdown_path=markdown_path,
                generated_on="2026-07-25",
            )

            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(parsed, manifest)
        self.assertIn(manifest["manifest_sha256"], markdown)
        self.assertIn("`ready`", markdown)
        self.assertIn("| `pure_output` | `输出、输出(必爆)` | 8 | 13 |", markdown)
        self.assertIn("完整回归矩阵证据", markdown)

    def test_missing_regression_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative_path in BEHAVIOR_INPUTS:
                source = ROOT / relative_path
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            manifest = build_policy_manifest(root, generated_on="2026-07-25")

        self.assertEqual(manifest["freeze_status"], "not_ready")
        self.assertFalse(manifest["readiness"]["gates"]["full_regression_matrix_evidence_attached"])
        self.assertIn("full_regression_matrix_evidence_not_attached", manifest["readiness"]["gaps"])

    def test_non_object_regression_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for relative_path in BEHAVIOR_INPUTS:
                source = ROOT / relative_path
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            evidence_path = root / REGRESSION_EVIDENCE_PATH
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text("[]\n", encoding="utf-8")

            manifest = build_policy_manifest(root, generated_on="2026-07-25")

        self.assertEqual(manifest["freeze_status"], "not_ready")
        self.assertEqual(manifest["regression_evidence"]["status"], "invalid")
        self.assertEqual(manifest["regression_evidence"]["reasons"], ["evidence_root_not_object"])

    def test_regression_test_input_hash_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            required_paths = set(BEHAVIOR_INPUTS) | set(REGRESSION_TEST_INPUTS) | set(REGRESSION_EXECUTION_INPUTS)
            required_paths.add(REGRESSION_EVIDENCE_PATH)
            for relative_path in required_paths:
                source = ROOT / relative_path
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            changed_path = root / REGRESSION_TEST_INPUTS[0]
            changed_path.write_bytes(changed_path.read_bytes() + b"\n")

            manifest = build_policy_manifest(root, generated_on="2026-07-25")

        self.assertEqual(manifest["freeze_status"], "not_ready")
        self.assertEqual(manifest["regression_evidence"]["status"], "invalid")
        self.assertFalse(manifest["readiness"]["gates"]["full_regression_matrix_evidence_attached"])

    def test_missing_behavior_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaisesRegex(PolicyManifestError, "Missing behavior input"):
                build_policy_manifest(root, generated_on="2026-07-25")


if __name__ == "__main__":
    unittest.main()
