from __future__ import annotations

import copy
import unittest

from tools import research_reforged_inventory_set_weight_r400_audit as audit
from tools import research_reforged_inventory_set_weights as r50


class R400ClosureAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.weights = r50.derive_weights()

    def test_r50_actual_shards_are_loaded_as_five_read_only_clusters(self):
        clusters = audit.load_r50_clusters(self.weights)
        self.assertEqual(len(clusters), 5)
        self.assertEqual({row["source"] for row in clusters}, {"r50"})
        self.assertEqual({row["cluster_id"] for row in clusters}, {f"r50-seed-{seed}" for seed in r50.SEEDS})

    def test_r200_is_not_read_when_closing_r400(self):
        clusters = audit.load_r400_clusters(self.weights)
        self.assertEqual(len(clusters), 20)
        self.assertEqual({row["source"] for row in clusters}, {"r400"})
        self.assertFalse(any("r200" in str(row) for row in clusters))

    def test_r800_is_read_as_its_own_cumulative_stage(self):
        clusters = audit.load_r800_clusters(self.weights)
        self.assertEqual(len(clusters), 20)
        self.assertEqual({row["source"] for row in clusters}, {"r800"})

    def test_missing_or_hash_mismatched_r50_shard_is_rejected(self):
        clusters = audit.load_r50_clusters(self.weights)
        damaged = copy.deepcopy(clusters[0])
        damaged["rows"][next(iter(damaged["rows"]))]["Epic"]["input_hash"] = "not-frozen"
        with self.assertRaisesRegex(ValueError, "R50"):
            audit.validate_r50_cluster(damaged, self.weights)

    def test_top4_and_terminal_metrics_are_written_for_every_rule(self):
        data = audit.summarize(
            audit.load_r50_clusters(self.weights),
            audit.load_r400_clusters(self.weights),
            self.weights,
        )
        top4 = data["scenarios"]["top4_equal"]["rules"]
        self.assertEqual(set(top4), {rule.key for rule in r50.RULES})
        for row in top4.values():
            for metric in ("native_heirloom_per_100k", "converted_heirloom_per_100k", "speed22_per_100k"):
                self.assertIn(metric, row)
                self.assertGreaterEqual(row[metric], 0.0)
        self.assertIn("top4_equal", audit.markdown(data))

    def test_merged_inventory_cost_uses_all_twenty_five_clusters_and_positive_interval(self):
        data = audit.summarize(
            audit.load_r50_clusters(self.weights),
            audit.load_r400_clusters(self.weights),
            self.weights,
        )
        current = data["scenarios"]["reforged_inventory_all"]["rules"]["current_formal"]
        self.assertEqual(current["absolute_cost"]["cluster_count"], 25)
        self.assertGreaterEqual(current["absolute_cost"]["interval95"][0], 0.0)

    def test_unequal_cluster_mass_uses_weighted_ratio_and_r50_share(self):
        ledgers = [
            {"source": "r50", "sample_mass": 50, "numerator_formal_baili": 2.0, "denominator_total_stamina": 20.0, "rift_stamina": 5.0, "saint_stamina": 15.0, "native_heirloom": 1.0, "converted_heirloom": 2.0, "speed22": 3.0},
            {"source": "r800", "sample_mass": 800, "numerator_formal_baili": 10.0, "denominator_total_stamina": 50.0, "rift_stamina": 12.5, "saint_stamina": 37.5, "native_heirloom": 4.0, "converted_heirloom": 5.0, "speed22": 6.0},
        ]
        result = audit._aggregate(ledgers)
        self.assertAlmostEqual(result["absolute_cost"]["mean"], 41000.0 / 8100.0)
        self.assertAlmostEqual(result["sample_mass_by_source"]["r50"] / result["total_sample_mass"], 50.0 / 850.0)

    def test_r50_r800_stratified_bootstrap_and_100k_conservation(self):
        data = audit.summarize(audit.load_r50_clusters(self.weights), audit.load_r800_clusters(self.weights), self.weights)
        for scenario in data["scenarios"].values():
            for row in scenario["rules"].values():
                self.assertEqual(row["absolute_cost"]["method"], "source_stratified_clustered_positive_bootstrap")
                self.assertEqual(row["absolute_cost"]["bootstrap_strata"], {"r50": 5, "r800": 20})
                self.assertAlmostEqual(row["rift_stamina_per_100k"] + row["saint_stamina_per_100k"], 100000.0, places=7)
        current = data["scenarios"]["reforged_inventory_all"]["rules"]["current_formal"]
        self.assertAlmostEqual(current["sample_mass_by_source"]["r50"] / current["total_sample_mass"], 250.0 / 16250.0)

    def test_cycles_and_terminal_metrics_are_mass_scaled(self):
        ledgers = [
            {"source": "r50", "sample_mass": 50, "numerator_formal_baili": 2.0, "denominator_total_stamina": 20.0, "rift_stamina": 5.0, "saint_stamina": 15.0, "native_heirloom": 1.0, "converted_heirloom": 2.0, "speed22": 3.0},
            {"source": "r800", "sample_mass": 800, "numerator_formal_baili": 10.0, "denominator_total_stamina": 50.0, "rift_stamina": 12.5, "saint_stamina": 37.5, "native_heirloom": 4.0, "converted_heirloom": 5.0, "speed22": 6.0},
        ]
        result = audit._aggregate(ledgers)
        self.assertAlmostEqual(result["cycles_per_100k"], 100000.0 * 850.0 / 41000.0)
        self.assertAlmostEqual(result["speed22_per_100k"], 100000.0 * (50.0 * 3.0 + 800.0 * 6.0) / 41000.0)
        self.assertNotAlmostEqual(result["rift_stamina_per_100k"], 100000.0 * 2.0 * (5.0 + 12.5) / (20.0 + 50.0))


if __name__ == "__main__":
    unittest.main()
