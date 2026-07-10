import json
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.visualize_report import (
    FORMAL_RADAR_LABELS,
    build_visual_model,
    render_single_policy_html,
    render_top_compare_html,
    write_visualizations,
)


def sample_policy(name="baili_marginal_mid", cost=100.0):
    return {
        "policy_name": name,
        "baili_score_per_1000_stamina": 10.0,
        "cost_per_baili_score": cost,
        "target_score_per_1000_stamina": 12.5,
        "cost_per_target_score": 80.0,
        "success_rate": 0.12,
        "native_success_rate": 0.08,
        "rescued_success_rate": 0.04,
        "conversion_needed_rate": 0.03,
        "avg_success_baili_score": 9.5,
        "total_baili_score": 123.4,
        "stop_rate_by_checkpoint": {"0": 0.2, "3": 0.1, "6": 0.1, "9": 0.2, "12": 0.3, "15": 0.1},
        "target_score_by_category": {
            "输出": 10,
            "输出(必爆)": 5,
            "一速": 8,
            "速度套纯速度": 4,
            "非速度套速度装": 2,
            "抗坦": 7,
            "纯肉": 6,
            "命坦": 5,
            "双效": 3,
            "半肉(血防)": 1,
            "半肉(通用)": 2,
            "半肉(白字)": 3,
            "未来可期": 99,
        },
        "success_count_by_category": {"输出": 2, "未来可期": 5},
        "baili_tier_rate": {"0": 0.8, "1": 0.1, "2": 0.08, "3": 0.02},
    }


def sample_report():
    return {
        "calibration_runs": 100,
        "seed": 17,
        "gear_source": "rift_new_1_32",
        "item_source": "normal_85",
        "rank": "Epic",
        "best_policy": "baili_marginal_mid",
        "ranking_metric": "cost_per_baili_score",
        "success_definition": {
            "source": "套装属性与装等计算表.md",
            "main_score_scope": "R2-R58 formal baili score; R61 future is auxiliary only",
            "conversion_cost_counted": False,
        },
        "policies": [
            sample_policy("baili_marginal_mid", 100.0),
            sample_policy("baili_marginal_low", 120.0),
            sample_policy("baili_marginal_high", 140.0),
            sample_policy("target_marginal_mid", 160.0),
            sample_policy("score_target_low_speed_low", 180.0),
            sample_policy("score_strategy_late_strict_speed_high", 200.0),
        ],
    }


class VisualizeReportTest(unittest.TestCase):
    def test_visual_model_maps_formal_categories_and_excludes_future(self):
        model = build_visual_model(sample_report(), sample_report()["policies"][0])

        self.assertEqual([item["label"] for item in model["radar"]], FORMAL_RADAR_LABELS)
        values = {item["label"]: item["value"] for item in model["radar"]}
        self.assertEqual(values["输出"], 15)
        self.assertEqual(values["速度"], 6)
        self.assertEqual(values["半肉"], 6)
        self.assertNotIn("未来可期", values)
        self.assertEqual(model["auxiliary_categories"]["未来可期"], 99)

    def test_single_policy_html_handles_missing_fields(self):
        report = sample_report()
        policy = {"policy_name": "short_report", "target_score_by_category": {"未来可期": 1}}

        html = render_single_policy_html(report, policy)

        self.assertIn("百里分 / 1000体力", html)
        self.assertIn("体力 / 1百里分", html)
        self.assertIn("未来可期仅作辅助展示", html)
        self.assertIn("-", html)

    def test_top_compare_uses_first_five_ranked_policies_and_marks_best(self):
        html = render_top_compare_html(sample_report())

        self.assertIn("baili_marginal_mid", html)
        self.assertIn("best_policy", html)
        self.assertIn("score_target_low_speed_low", html)
        self.assertNotIn("score_strategy_late_strict_speed_high</td>", html)

    def test_write_visualizations_outputs_html_and_index(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            input_path = base / "baili-formal-normal-10k-seed17.json"
            input_path.write_text(json.dumps(sample_report(), ensure_ascii=False), encoding="utf-8")
            output_dir = base / "visual"

            result = write_visualizations(input_path, output_dir=output_dir, top=5)

            self.assertTrue(Path(result["single_html"]).exists())
            self.assertTrue(Path(result["compare_html"]).exists())
            self.assertTrue((output_dir / "index.html").exists())
            self.assertEqual(result["policy_name"], "baili_marginal_mid")

    def test_top_level_module_entrypoint_is_importable(self):
        from e7_enhance.visualize_report import main

        self.assertTrue(callable(main))


if __name__ == "__main__":
    unittest.main()
