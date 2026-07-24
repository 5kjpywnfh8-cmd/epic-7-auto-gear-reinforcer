import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.e7_enhance.resource_model import calibration_for_rank, joint_source_batch_metadata
from tools.epic_non_speed_early_policy_pareto import _gear_from_item
from tools.research_riftslash_joint_batch import _atomic_json, _scenario_rates, collect_jobs, summarize


ROOT = Path(__file__).resolve().parents[1]


class RiftslashJointBatchResearchTest(unittest.TestCase):
    def test_collect_jobs_is_resumable_and_keeps_rank_seed_chunk_identity(self):
        source = json.loads((ROOT / "samples" / "real_acceptance_fribbels_20260610_plus0_plus3.json").read_text(encoding="utf-8"))
        epic = _gear_from_item(next(item for item in source["items"] if item["rank"] == "Epic" and item["enhance"] == 0))
        heroic = _gear_from_item(next(item for item in source["items"] if item["rank"] == "Heroic" and item["enhance"] == 0))
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            jobs, state = collect_jobs(resume_dir=root, seeds=[1, 2], epic_gears=[epic], heroic_gears=[heroic], runs_per_seed=10, chunk_runs=5)
            self.assertEqual(state["scheduled_shards"], 8)
            first = jobs[0]
            _atomic_json(Path(first["path"]), {"status": "complete", "paths": 5})
            remaining, resumed = collect_jobs(resume_dir=root, seeds=[1, 2], epic_gears=[epic], heroic_gears=[heroic], runs_per_seed=10, chunk_runs=5)
            self.assertEqual(resumed["existing_complete_shards"], 1)
            self.assertEqual(len(remaining), 7)

    def test_joint_rate_uses_one_batch_cost_and_raw_sums(self):
        batch = joint_source_batch_metadata("riftslash_20_buff", "Epic", calibration_for_rank("Epic"))
        epic = {"paths": 10, "A": {"value_sum": 10.0, "stamina_sum": 20.0, "terminal_formal_count": 1}}
        heroic = {"paths": 20, "baili_marginal_low": {"value_sum": 4.0, "stamina_sum": 8.0, "terminal_formal_count": 1}, "all_stop": {"value_sum": 0.0, "stamina_sum": 0.0, "terminal_formal_count": 0}}
        rates = _scenario_rates(epic, heroic, batch)
        expected_yield = batch["expected_output_by_rank"]["Heroic"]
        expected = 100 * (10 + expected_yield * 10 / 20 * 4) / (10 * batch["net_batch_acquisition_stamina"] + 20 + expected_yield * 10 / 20 * 8)
        self.assertAlmostEqual(rates["baili_marginal_low/baseline"]["A"], expected)
