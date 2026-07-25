import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.policy_manifest import (
    BEHAVIOR_INPUTS,
    PolicyManifestError,
    build_policy_manifest,
    write_policy_manifest,
)
from src.e7_enhance.strategy_defaults import STRATEGY_VERSION


ROOT = Path(__file__).resolve().parents[1]


class PolicyManifestTest(unittest.TestCase):
    def test_manifest_records_supported_scope_and_current_readiness_gap(self):
        manifest = build_policy_manifest(ROOT, generated_on="2026-07-25")

        self.assertEqual(manifest["schema_version"], "e7_enhance.policy_manifest/1.0")
        self.assertEqual(manifest["strategy_version"], STRATEGY_VERSION)
        self.assertEqual(manifest["freeze_status"], "not_ready")
        self.assertIn("unknown_set_not_rejected_by_advise_gear", manifest["readiness"]["gaps"])
        self.assertFalse(manifest["readiness"]["gates"]["unknown_set_fail_closed"])
        self.assertEqual(manifest["supported_inputs"]["enhancement_checkpoints"], [0, 3, 6, 9, 12, 15])
        self.assertEqual(
            {(row["item_source"], row["rank"]) for row in manifest["supported_inputs"]["item_source_ranks"]},
            {("normal_85", "Epic"), ("normal_85", "Heroic"), ("rift_85", "Epic")},
        )

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
        self.assertIn("`not_ready`", markdown)

    def test_missing_behavior_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            with self.assertRaisesRegex(PolicyManifestError, "Missing behavior input"):
                build_policy_manifest(root, generated_on="2026-07-25")


if __name__ == "__main__":
    unittest.main()
