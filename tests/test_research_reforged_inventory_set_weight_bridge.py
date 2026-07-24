from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools import research_reforged_inventory_set_weight_bridge as bridge
from tools import research_reforged_inventory_set_weights as r50


class ReforgedInventoryBridgeTest(unittest.TestCase):
    def test_external_source_filter_and_19_set_weights_are_frozen(self):
        weights = r50.derive_weights()
        self.assertEqual(weights["source_sha256"], r50.EXPECTED_SOURCE_SHA256)
        self.assertEqual(weights["rank_totals"], {"Epic": 616, "Heroic": 149})
        self.assertEqual(len(weights["observed_sets"]), 19)
        for values in weights["scenarios"].values():
            self.assertAlmostEqual(sum(values.values()), 1.0)

    def test_fixed_joint_source_batch_is_independent_of_set_weights(self):
        batch = joint_source_batch_metadata(r50.GEAR_SOURCE, "Epic", calibration_for_rank("Epic"))
        self.assertEqual(batch["gross_batch_acquisition_stamina"], 85)
        self.assertEqual(batch["expected_output_by_rank"]["Epic"], 1.0)
        self.assertGreater(batch["expected_output_by_rank"]["Heroic"], 3.0)

    def test_hash_and_path_include_block_seed_set_and_rank(self):
        hashes = bridge._code_hashes()
        seed = bridge._block_seed(1)
        left = bridge._input_hash(block=1, seed=seed, set_code="set_speed", rank="Epic", samples_per_set=2, hashes=hashes)
        right = bridge._input_hash(block=2, seed=bridge._block_seed(2), set_code="set_speed", rank="Epic", samples_per_set=2, hashes=hashes)
        self.assertNotEqual(left, right)
        path = bridge._shard_path(Path("resume"), 2, 1, seed, "set_speed", "Epic")
        self.assertIn("block-001", str(path))
        self.assertIn(f"seed-{seed}", str(path))
        self.assertIn("set_speed", str(path))
        self.assertIn("epic", str(path))

    def test_r50_resume_is_rejected_as_write_target(self):
        with self.assertRaises(ValueError):
            bridge.run(resume_root=bridge.R50_RESUME, samples_per_set=1, blocks=(1,), workers=1)

    def test_positive_cluster_bootstrap_never_returns_negative_lower_bound_and_inverse_matches(self):
        clusters = [
            {"numerator_formal_baili": 2.0, "denominator_total_stamina": 20.0},
            {"numerator_formal_baili": 4.0, "denominator_total_stamina": 40.0},
            {"numerator_formal_baili": 6.0, "denominator_total_stamina": 60.0},
        ]
        ratio = bridge.positive_cluster_ratio(clusters, draws=200)
        self.assertAlmostEqual(ratio["mean"], 10.0)
        self.assertGreaterEqual(ratio["interval95"][0], 0.0)
        self.assertAlmostEqual(100000.0 / ratio["mean"], 10000.0)

    def test_five_layer_bridge_changes_only_declared_boundary_on_handmade_rows(self):
        rows = {}
        for set_code in ("set_a", "set_b"):
            rows[set_code] = {
                "Epic": {
                    "samples_per_set": 1,
                    "flows": {rule.key: {field: 0.0 for field in bridge.FLOW_WITH_METRICS} for rule in r50.RULES},
                    "published_legacy_baili_score": {rule.key: 0.0 for rule in r50.RULES},
                    "published_legacy_total_stamina": {rule.key: 10.0 for rule in r50.RULES},
                },
                "Heroic": {"samples_per_set": 1, "released_heroic_flow": {field: 0.0 for field in bridge.FLOW_WITH_METRICS}, "all_stop_heroic_flow": {field: 0.0 for field in bridge.FLOW_WITH_METRICS}},
            }
            rows[set_code]["Epic"]["flows"]["current_formal"].update({"value_sum": 2.0 if set_code == "set_a" else 4.0, "legacy_stamina_sum": 10.0})
            rows[set_code]["Epic"]["published_legacy_baili_score"]["current_formal"] = 2.0 if set_code == "set_a" else 4.0
        layers = bridge.bridge_layers(rows, {"set_a": 0.75, "set_b": 0.25}, "current_formal")
        self.assertNotEqual(layers["published_epic_replay"]["numerator_formal_baili"], layers["epic_inventory_weighted"]["numerator_formal_baili"])
        self.assertIn(bridge.TERMINAL_VALUE_DIAGNOSTIC, layers)
        self.assertEqual(layers["joint_source_all_stop_heroic"]["numerator_formal_baili"], layers["joint_source_epic_value_only"]["numerator_formal_baili"])

    def test_paired_delta_uses_common_cluster_values(self):
        paired = bridge._paired_rate_delta([0.3, 0.4, 0.5], [0.2, 0.3, 0.4])
        self.assertAlmostEqual(paired["mean"], 0.1)
        self.assertEqual(paired["unit"], "formal_baili_per_100_total_stamina")


if __name__ == "__main__":
    unittest.main()
