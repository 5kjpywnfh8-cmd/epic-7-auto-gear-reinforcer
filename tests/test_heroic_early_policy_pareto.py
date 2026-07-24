import json
from pathlib import Path
import unittest

from tools.heroic_early_policy_pareto import (
    build_partition,
    simulate_paths,
    summarize_incremental_cost,
)
from src.e7_enhance.gui_support import _fribbels_item_to_gear_dict
from src.e7_enhance.models import Gear


ROOT = Path(__file__).resolve().parents[1]


class HeroicEarlyPolicyParetoToolTest(unittest.TestCase):
    def test_partition_keeps_heroic_holdout_instances_out_of_training(self):
        source = json.loads((ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json").read_text(encoding="utf-8"))
        records = json.loads((ROOT / "manual_acceptance" / "real_sample_records.json").read_text(encoding="utf-8"))

        training, holdout = build_partition(source, records)

        self.assertEqual(len(holdout), 16)
        self.assertEqual(len(training), 64)
        self.assertFalse({gear.code for gear in training} & {gear.code for gear in holdout})

    def test_same_seed_produces_identical_heroic_paths_and_plus12_adds_substat(self):
        source = json.loads((ROOT / "samples" / "heroic_resource_fallback_acceptance_20260712.json").read_text(encoding="utf-8"))
        gear = Gear.from_dict(_fribbels_item_to_gear_dict(source["items"][0]))

        first = simulate_paths(gear, runs=12, seed=20260712)
        second = simulate_paths(gear, runs=12, seed=20260712)

        self.assertEqual(first, second)
        self.assertTrue(all(len(path[12].substats) == 4 for path in first))
        self.assertTrue(all(len(path[12].roll_history) == 3 for path in first))

    def test_incremental_cost_excludes_embryo_cost_and_applies_accessory_scarcity(self):
        common = summarize_incremental_cost("weapon", start_checkpoint=0, stop_checkpoint=3)
        accessory = summarize_incremental_cost("neck", start_checkpoint=0, stop_checkpoint=3)

        self.assertEqual(common["gear_acquisition_stamina"], 0.0)
        self.assertGreater(accessory["upgrade_stamina"], common["upgrade_stamina"])
        self.assertGreater(common["sell_recovery_stamina"], 0.0)


if __name__ == "__main__":
    unittest.main()
