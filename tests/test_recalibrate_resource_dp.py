import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOL = importlib.import_module("tools.recalibrate_resource_dp")
TOOL_PATH = Path(TOOL.__file__).resolve()


def policy_result(seed: int) -> dict:
    return {
        "policies": [
            {
                "total_stamina": float(seed * 100),
                "total_baili_score": 10.0,
                "nonzero_terminal_count": 1,
            }
        ]
    }


class RecalibrateResourceDpToolTest(unittest.TestCase):
    def run_main(self, *args: str) -> None:
        with patch.object(sys, "argv", [str(TOOL_PATH), *args]):
            TOOL.main()

    def test_configs_limits_output_to_requested_heroic_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "heroic.json"
            with patch.object(TOOL, "calibrate_selected_policies", side_effect=lambda options, _policies: policy_result(options.seed)):
                self.run_main("--configs", "normal_85_heroic", "--seeds", "101", "--output", str(output))

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([item["label"] for item in payload["configs"]], ["normal_85 Heroic"])
            self.assertEqual(payload["configs"][0]["aggregate"]["seed_results"][0]["seed"], 101)

    def test_resume_preserves_existing_seed_and_rejects_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "heroic.json"
            output.write_text(
                json.dumps(
                    {
                        "configs": [
                            {
                                "label": "normal_85 Heroic",
                                "item_source": "normal_85",
                                "rank": "Heroic",
                                "policy_name": "baili_marginal_low",
                                "aggregate": {"seed_results": [{"seed": 101, "runs": 10, "total_stamina": 100.0, "total_baili_score": 10.0, "nonzero_terminal_count": 1}]},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(TOOL, "calibrate_selected_policies", side_effect=lambda options, _policies: policy_result(options.seed)):
                self.run_main("--configs", "normal_85_heroic", "--seeds", "102", "--resume-existing", str(output), "--output", str(output))

            payload = json.loads(output.read_text(encoding="utf-8"))
            seeds = [row["seed"] for row in payload["configs"][0]["aggregate"]["seed_results"]]
            self.assertEqual(seeds, [101, 102])
            with self.assertRaisesRegex(ValueError, "重复 seed"):
                self.run_main("--configs", "normal_85_heroic", "--seeds", "102", "--resume-existing", str(output), "--output", str(output))

    def test_writes_completed_seed_before_later_seed_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "heroic.json"

            def simulate(options, _policies):
                if options.seed == 202:
                    raise RuntimeError("second seed failed")
                return policy_result(options.seed)

            with patch.object(TOOL, "calibrate_selected_policies", side_effect=simulate):
                with self.assertRaisesRegex(RuntimeError, "second seed failed"):
                    self.run_main("--configs", "normal_85_heroic", "--seeds", "201,202", "--output", str(output))

            payload = json.loads(output.read_text(encoding="utf-8"))
            rows = payload["configs"][0]["aggregate"]["seed_results"]
            self.assertEqual([row["seed"] for row in rows], [201])

    def test_heroic_cost_override_reaches_multi_process_simulation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline = Path(temp_dir) / "baseline.json"
            discounted = Path(temp_dir) / "discounted.json"
            configs = TOOL._selected_configs("normal_85_heroic")
            TOOL.run_calibration(configs, [17], 2000, 2, "riftslash_20_buff", baseline)
            TOOL.run_calibration(configs, [17], 2000, 2, "riftslash_20_buff", discounted, heroic_gear_stamina=0.0)

            baseline_cost = json.loads(baseline.read_text(encoding="utf-8"))["configs"][0]["aggregate"]["total_stamina"]
            discounted_cost = json.loads(discounted.read_text(encoding="utf-8"))["configs"][0]["aggregate"]["total_stamina"]
            self.assertLess(discounted_cost, baseline_cost)


if __name__ == "__main__":
    unittest.main()
