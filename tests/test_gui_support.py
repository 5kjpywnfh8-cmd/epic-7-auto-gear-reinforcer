import json
import tempfile
import unittest
from pathlib import Path

from src.e7_enhance.airtest_adapter import NullAirtestAdapter
from src.e7_enhance.gui_support import (
    DEFAULT_GEAR_FORM,
    build_gear_dict,
    format_debug_details,
    load_gear_collection,
    debug_view_model,
    load_gear_file,
    save_gear_file,
    save_suggestion_file,
    suggest_from_form,
    summary_view_model,
)
from src.e7_enhance.cli import load_single_gear


class GuiSupportTest(unittest.TestCase):
    def test_debug_details_are_chinese_and_preserve_full_category_diagnostics(self):
        form = load_gear_file(Path("建议结果/07.json"))
        result = suggest_from_form(form)

        details = format_debug_details(result, build_gear_dict(form))

        self.assertIn("完整分类诊断", details)
        self.assertIn("强化命中分析", details)
        self.assertIn("当前装备输入", details)
        for internal_identifier in (
            "lightweight_basis",
            "calibration_group",
            "full_category_diagnostics",
            "weapon",
            "atkPct",
            "CriticalHitChancePercent",
        ):
            self.assertNotIn(internal_identifier, details)

    def test_debug_details_explain_early_conversion_candidates_in_chinese(self):
        form = load_gear_file(Path("建议结果/14.json"))
        result = suggest_from_form(form)

        details = format_debug_details(result, build_gear_dict(form))

        self.assertIn("候选体系评估", details)
        self.assertIn("输出", details)
        self.assertIn("唯一未命中且可转换候选", details)
        self.assertIn("终局低档 GS 门槛", details)
        self.assertIn("终局达标概率", details)
        self.assertIn("高优先级候选按终局达标概率排序", details)
        self.assertIn("低优先级候选不能覆盖合格高优先级候选", details)
        self.assertNotIn("candidate_evaluations", details)
        self.assertNotIn("terminal_reach_probability", details)

    def test_form_can_load_sample_and_get_concise_suggestion(self):
        form = load_gear_file(Path("samples/gear.json"))

        self.assertEqual(form["set"], "Speed")
        self.assertEqual(form["slot"], "Weapon")

        result = suggest_from_form(form)
        summary = summary_view_model(result)
        debug = debug_view_model(result)

        self.assertIn(summary["recommendation"], {"stop", "continue", "cautious_continue", "keep", "convert", "uncertain"})
        self.assertIn("target_profile", summary)
        self.assertIsInstance(summary["reasons"], list)
        self.assertEqual(debug["strategy_version"], "baili-formal-dp-v1")
        self.assertEqual(debug["strategy_name"], "normal_epic_dp_assisted")
        self.assertIn("dp_decision", debug)
        self.assertIn("lightweight_decision", debug)
        self.assertIn("dp_utility", debug)
        self.assertIn("dp_override_applied", debug)
        self.assertIn("baili_score", debug)
        self.assertIn("target_score", debug)
        for key in (
            "official_score",
            "effective_score",
            "rating_level",
            "rating_semantics",
            "fit_status",
            "valid_substats",
            "invalid_substats",
            "roll_hit_analysis",
        ):
            self.assertIn(key, debug)

    def test_single_speed_hit_epic_gear_continues(self):
        form = load_gear_file(Path("1跳速度.json"))

        result = suggest_from_form(form)
        summary = summary_view_model(result)
        debug = debug_view_model(result)

        self.assertEqual(summary["recommendation"], "continue")
        self.assertEqual(debug["strategy_name"], "normal_epic_dp_assisted")
        self.assertEqual(debug["dp_decision"], "continue")
        self.assertIsNone(debug["lightweight_decision"])
        self.assertIsNotNone(debug["dp_utility"])
        self.assertNotEqual(debug["dp_best_target_category"], "stop")
        self.assertEqual(debug["valid_substats"], ["速度 7", "生命% 8%", "防御% 5%", "抵抗 4%"])
        self.assertEqual(
            debug["roll_hit_analysis"],
            [{"enhance": None, "stat": "速度", "value": None, "valid": True, "inferred": True, "hit_count": 1}],
        )
        for key in (
            "dp_expected_final_speed",
            "dp_expected_speed_rolls",
            "dp_speed_potential_set_eligible",
            "dp_speed_potential_threshold_blocked_probability",
            "dp_expected_speed_potential_value",
        ):
            self.assertIn(key, result["debug"]["dp_assist"])

    def test_form_builds_gear_json_and_saves_result(self):
        form = dict(DEFAULT_GEAR_FORM)
        form.update(
            {
                "set": "Speed",
                "slot": "Weapon",
                "main_type": "Attack",
                "main_value": 525,
                "enhance": 12,
                "level": 85,
                "rank": "Epic",
                "reforge_eligible": True,
                "substats": [
                    {"type": "Speed", "value": 18, "rolls": 4},
                    {"type": "HealthPercent", "value": 5, "rolls": 1},
                    {"type": "AttackPercent", "value": 9, "rolls": 2},
                    {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
                ],
            }
        )

        gear = build_gear_dict(form)
        result = suggest_from_form(form)

        with tempfile.TemporaryDirectory() as tmp:
            gear_path = Path(tmp) / "gear.json"
            result_path = Path(tmp) / "suggestion.json"
            save_gear_file(gear_path, form)
            save_suggestion_file(result_path, form, result)

            saved_gear = json.loads(gear_path.read_text(encoding="utf-8"))
            saved_result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(saved_gear["mainStat"]["type"], gear["mainStat"]["type"])
        self.assertTrue(saved_gear["reforgeEligible"])
        self.assertEqual(saved_gear["itemSource"], "normal_85")
        self.assertEqual(saved_result["gear"]["set"], "Speed")
        self.assertIn("summary", saved_result["suggestion"])
        self.assertIn("debug", saved_result["suggestion"])
        self.assertIn("summary_view", saved_result)
        self.assertIn("debug_view", saved_result)
        self.assertNotIn("lightweight_full_category_diagnostics", saved_result["debug_view"])
        self.assertIn("manual_review", saved_result)
        self.assertIn("人工判断", saved_result["manual_review"])

    def test_acceptance_batch_sample_has_20_to_50_items(self):
        forms = load_gear_collection(Path("samples/manual_acceptance_gears.json"))

        self.assertGreaterEqual(len(forms), 20)
        self.assertLessEqual(len(forms), 50)
        self.assertEqual(forms[0]["item_source"], "normal_85")
        self.assertIn(forms[0]["rank"], {"Epic", "Heroic"})

    def test_acceptance_samples_follow_substat_slot_rules(self):
        forms = load_gear_collection(Path("samples/manual_acceptance_gears.json"))
        forbidden_by_slot = {
            "Weapon": {"Attack", "Defense", "DefensePercent"},
            "Helmet": {"Health"},
            "Armor": {"Attack", "AttackPercent", "Defense"},
        }

        for form in forms:
            substat_types = {substat["type"] for substat in form["substats"] if substat["type"]}
            if form["slot"] in {"Necklace", "Ring", "Boots"}:
                self.assertNotIn(form["main_type"], substat_types)
            self.assertFalse(forbidden_by_slot.get(form["slot"], set()) & substat_types)

    def test_acceptance_samples_include_visible_enhance_counts(self):
        forms = load_gear_collection(Path("samples/manual_acceptance_gears.json"))

        for form in forms:
            for substat in form["substats"]:
                if substat["type"]:
                    self.assertGreaterEqual(substat["rolls"], 1)

        self.assertEqual([substat["rolls"] for substat in forms[14]["substats"]], [2, 2, 1, 1])

    def test_strategy_rejects_invalid_slot_substat_combination(self):
        form = dict(DEFAULT_GEAR_FORM)
        form["substats"] = [
            {"type": "Attack", "value": 50, "rolls": 1},
            {"type": "Speed", "value": 4, "rolls": 1},
            {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
            {"type": "HealthPercent", "value": 8, "rolls": 1},
        ]

        with self.assertRaisesRegex(ValueError, "Invalid substats"):
            suggest_from_form(form)

    def test_json_import_rejects_rift_heroic(self):
        data = {
            "itemSource": "rift_85",
            "set": "Speed",
            "slot": "Helmet",
            "mainStat": {"type": "Health", "value": 2700},
            "enhance": 0,
            "level": 85,
            "rank": "Heroic",
            "substats": [
                {"type": "Speed", "value": 3, "rolls": 1},
                {"type": "HealthPercent", "value": 8, "rolls": 1},
                {"type": "DefensePercent", "value": 5, "rolls": 1},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rift-heroic.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "rift_85 only supports Epic"):
                load_gear_file(path)

    def test_cli_json_import_rejects_rift_heroic(self):
        data = {
            "itemSource": "rift_85",
            "set": "Speed",
            "slot": "Helmet",
            "mainStat": {"type": "Health", "value": 2700},
            "enhance": 0,
            "level": 85,
            "rank": "Heroic",
            "substats": [
                {"type": "Speed", "value": 3, "rolls": 1},
                {"type": "HealthPercent", "value": 8, "rolls": 1},
                {"type": "DefensePercent", "value": 5, "rolls": 1},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rift-heroic.json"
            path.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "rift_85 only supports Epic"):
                load_single_gear(str(path))

    def test_85_legacy_reforge_flag_is_normalized_when_loading_and_saving(self):
        gear_data = {
            "set": "SpeedSet",
            "slot": "Weapon",
            "mainStat": {"type": "Attack", "value": 525},
            "enhance": 12,
            "level": 85,
            "rank": "Epic",
            "reforgeEligible": False,
            "substats": [
                {"type": "Speed", "value": 12, "rolls": 3},
                {"type": "HealthPercent", "value": 8, "rolls": 2},
                {"type": "CriticalHitChancePercent", "value": 8, "rolls": 2},
                {"type": "EffectResistancePercent", "value": 8, "rolls": 2},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "legacy.json"
            saved = Path(tmp) / "saved.json"
            source.write_text(json.dumps(gear_data), encoding="utf-8")

            form = load_gear_file(source)
            save_gear_file(saved, form)

            self.assertTrue(form["reforge_eligible"])
            self.assertTrue(json.loads(saved.read_text(encoding="utf-8"))["reforgeEligible"])

    def test_normalized_acceptance_samples_have_expected_import_results(self):
        root = Path("samples/manual_acceptance")
        expected = {
            "01_normal_epic_plus0.json": ("lightweight_prediction", "cautious_continue"),
            "02_normal_epic_plus3.json": ("lightweight_prediction", "cautious_continue"),
            "03_normal_epic_plus6_speed.json": ("exact_dp", "continue"),
            "04_rift_epic_plus0.json": ("lightweight_prediction", "cautious_continue"),
            "05_legacy_reforge_false.json": ("lightweight_prediction", "cautious_continue"),
            "07_high_speed_early.json": ("lightweight_prediction", "continue"),
            "08_normal_heroic_plus9_replay.json": ("exact_dp", "continue"),
            "09_speed_boot_output_full.json": ("lightweight_prediction", "continue"),
            "10_speed_boot_tank_full.json": ("lightweight_prediction", "continue"),
            "11_attack_boot_with_speed.json": ("lightweight_prediction", "cautious_continue"),
            "12_attack_boot_output_no_speed.json": ("lightweight_prediction", "cautious_continue"),
            "13_health_boot_tank_no_speed.json": ("lightweight_prediction", "cautious_continue"),
            "14_mixed_categories_no_full_match.json": ("lightweight_prediction", "cautious_continue"),
        }
        for name, (mode, recommendation) in expected.items():
            with self.subTest(name=name):
                form = load_gear_file(root / name)
                result = suggest_from_form(form)
                self.assertEqual(result["debug"]["dp_assist"]["decision_mode"], mode)
                self.assertEqual(result["summary"]["recommendation"], recommendation)
        with self.assertRaisesRegex(ValueError, "rift_85 only supports Epic"):
            load_gear_file(root / "06_invalid_rift_heroic.json")

    def test_saved_result_package_07_is_high_confidence_early_continue(self):
        form = load_gear_file(Path("建议结果/07.json"))
        result = suggest_from_form(form)
        debug = debug_view_model(result)

        self.assertEqual(result["debug"]["dp_assist"]["decision_mode"], "lightweight_prediction")
        self.assertEqual(result["summary"]["recommendation"], "continue")
        self.assertEqual(result["debug"]["dp_assist"]["lightweight_basis"]["valid_substat_count"], 4)
        self.assertEqual(debug["dp_decision"], "未运行精确 DP")
        self.assertEqual(debug["lightweight_decision"], "轻量预测：继续")
        self.assertIn("命中的完整分类", debug["lightweight_basis"])

    def test_manual_record_template_has_required_columns(self):
        path = Path("manual_acceptance/manual_test_records.csv")
        header = path.read_text(encoding="utf-8").splitlines()[0].split(",")

        for column in [
            "装备来源",
            "品质",
            "强化等级",
            "套装",
            "部位",
            "主属性",
            "副属性",
            "工具建议",
            "人工判断",
            "是否一致",
            "分歧原因",
            "备注",
        ]:
            self.assertIn(column, header)

    def test_null_airtest_adapter_is_disabled_and_does_not_click(self):
        adapter = NullAirtestAdapter()

        self.assertFalse(adapter.is_available())
        self.assertEqual(adapter.status(), "Airtest adapter disabled in v1")
        with self.assertRaises(NotImplementedError):
            adapter.click_enhance()


if __name__ == "__main__":
    unittest.main()
