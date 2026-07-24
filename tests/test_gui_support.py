import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from src.e7_enhance.airtest_adapter import NullAirtestAdapter
from src.e7_enhance.gui_support import (
    DEFAULT_GEAR_FORM,
    build_gear_dict,
    format_debug_details,
    load_gear_collection,
    load_gear_collection_with_report,
    debug_view_model,
    load_gear_file,
    save_gear_file,
    save_suggestion_file,
    suggest_from_form,
    summary_view_model,
)
from src.e7_enhance.cli import load_single_gear


class GuiSupportTest(unittest.TestCase):
    @staticmethod
    def fribbels_export_payload():
        epic_substats = [
            {"type": "EffectResistancePercent", "value": 5, "rolls": 1},
            {"type": "DefensePercent", "value": 6, "rolls": 1},
            {"type": "HealthPercent", "value": 6, "rolls": 1},
            {"type": "CriticalHitChancePercent", "value": 5, "rolls": 1},
        ]
        return {
            "export_time": "2026-06-10T20:37:43",
            "item_count": 7,
            "hero_count": 0,
            "heroes": [],
            "items": [
                {
                    "id": "epic-armor",
                    "ingameId": "ingame-armor",
                    "gear": "Armor",
                    "rank": "Epic",
                    "set": "TorrentSet",
                    "level": 85,
                    "enhance": 0,
                    "main": {"type": "Defense", "value": 300},
                    "substats": epic_substats,
                    "raw": {"code": "ecd6a"},
                },
                {
                    "id": "heroic-weapon",
                    "gear": "Weapon",
                    "rank": "Heroic",
                    "set": "SpeedSet",
                    "level": 85,
                    "enhance": 0,
                    "main": {"type": "Attack", "value": 525},
                    "substats": [
                        {"type": "Speed", "value": 4, "rolls": 1},
                        {"type": "HealthPercent", "value": 7, "rolls": 1},
                        {"type": "CriticalHitChancePercent", "value": 4, "rolls": 1},
                    ],
                    "raw": {"code": "spd-w"},
                },
                {
                    "id": "epic-boots",
                    "gear": "Boots",
                    "rank": "Epic",
                    "set": "set_chase",
                    "level": 85,
                    "enhance": 3,
                    "main": {"type": "Speed", "value": 40},
                    "substats": [
                        {"type": "AttackPercent", "value": 8, "rolls": 2},
                        {"type": "CriticalHitChancePercent", "value": 4, "rolls": 1},
                        {"type": "CriticalHitDamagePercent", "value": 7, "rolls": 1},
                        {"type": "HealthPercent", "value": 6, "rolls": 1},
                    ],
                    "raw": {"code": "chase-b"},
                },
                {
                    "id": "level-78",
                    "gear": "Armor",
                    "rank": "Epic",
                    "set": "TorrentSet",
                    "level": 78,
                    "enhance": 0,
                    "main": {"type": "Defense", "value": 280},
                    "substats": epic_substats,
                    "raw": {"code": "skip-78"},
                },
                {
                    "id": "level-88",
                    "gear": "Armor",
                    "rank": "Epic",
                    "set": "TorrentSet",
                    "level": 88,
                    "enhance": 3,
                    "main": {"type": "Defense", "value": 310},
                    "substats": epic_substats,
                    "raw": {"code": "skip-88"},
                },
                {
                    "id": "plus-15",
                    "gear": "Armor",
                    "rank": "Epic",
                    "set": "TorrentSet",
                    "level": 85,
                    "enhance": 15,
                    "main": {"type": "Defense", "value": 300},
                    "substats": epic_substats,
                    "raw": {"code": "skip-15"},
                },
                {
                    "id": "rare",
                    "gear": "Armor",
                    "rank": "Rare",
                    "set": "TorrentSet",
                    "level": 85,
                    "enhance": 0,
                    "main": {"type": "Defense", "value": 300},
                    "substats": epic_substats[:2],
                    "raw": {"code": "skip-rare"},
                },
            ],
        }

    def test_fribbels_export_filters_and_normalizes_plus0_plus3_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gear_fribbels.json"
            path.write_text(json.dumps(self.fribbels_export_payload()), encoding="utf-8")

            forms, report = load_gear_collection_with_report(path)

        self.assertEqual(len(forms), 3)
        self.assertEqual(report["source_format"], "fribbels")
        self.assertEqual(report["total_items"], 7)
        self.assertEqual(report["loaded_items"], 3)
        self.assertEqual(report["skipped_items"], 4)
        self.assertEqual(
            report["skipped_by_reason"],
            {"装备等级不是85级": 2, "强化等级不是+0/+3": 1, "品质不是红装/紫装": 1},
        )
        self.assertEqual(forms[0]["set"], "Torrent")
        self.assertEqual(forms[0]["slot"], "Armor")
        self.assertEqual(forms[0]["main_type"], "Defense")
        self.assertEqual(forms[0]["code"], "ecd6a")
        self.assertEqual(forms[0]["instance_id"], "ingame-armor")
        self.assertEqual(forms[1]["rank"], "Heroic")
        self.assertEqual(forms[1]["instance_id"], "heroic-weapon")
        self.assertEqual(len([item for item in forms[1]["substats"] if item["type"]]), 3)
        self.assertEqual(forms[2]["set"], "Chase")
        self.assertEqual(forms[2]["enhance"], 3)
        self.assertEqual(forms[2]["substats"][0]["rolls"], 2)
        self.assertTrue(all(form["item_source"] == "normal_85" for form in forms))

    def test_fribbels_export_without_eligible_items_has_chinese_error(self):
        payload = self.fribbels_export_payload()
        payload["items"] = [payload["items"][3], payload["items"][5]]
        payload["item_count"] = 2
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gear_fribbels.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "没有可导入的85级.*红装或紫装"):
                load_gear_collection_with_report(path)

    def test_fribbels_set_and_slot_values_are_chinese_in_debug(self):
        for raw_set, label in (("ReversalSet", "逆袭"), ("UnitySet", "夹攻")):
            with self.subTest(raw_set=raw_set), tempfile.TemporaryDirectory() as tmp:
                payload = self.fribbels_export_payload()
                payload["items"] = [payload["items"][0]]
                payload["items"][0]["set"] = raw_set
                payload["item_count"] = 1
                path = Path(tmp) / "gear_fribbels.json"
                path.write_text(json.dumps(payload), encoding="utf-8")

                form = load_gear_collection(path)[0]
                details = format_debug_details(suggest_from_form(form), build_gear_dict(form))

                self.assertIn(label, details)
                self.assertNotIn(raw_set, details)
                self.assertNotIn("Armor", details)
                self.assertNotIn("set_", details)

    def test_native_collection_keeps_strict_import_behavior(self):
        payload = {
            "items": [
                {
                    "set": "Speed",
                    "slot": "Weapon",
                    "mainStat": {"type": "Attack", "value": 525},
                    "enhance": 0,
                    "level": 78,
                    "rank": "Epic",
                    "substats": [],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "native.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Unsupported equipment level"):
                load_gear_collection_with_report(path)

    def test_real_fribbels_acceptance_subset_has_expected_distribution(self):
        forms, report = load_gear_collection_with_report(
            Path("samples/real_acceptance_fribbels_20260610_plus0_plus3.json")
        )

        self.assertEqual(report["source_format"], "fribbels")
        self.assertEqual(report["loaded_items"], 425)
        self.assertEqual(report["skipped_items"], 0)
        self.assertEqual(
            Counter((form["enhance"], form["rank"]) for form in forms),
            Counter({(0, "Epic"): 337, (0, "Heroic"): 80, (3, "Epic"): 8}),
        )
        self.assertTrue(all(form["level"] == 85 for form in forms))
        self.assertTrue(all(form["code"] for form in forms))
        self.assertEqual(len({form["instance_id"] for form in forms}), 425)

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

    def test_debug_view_shows_native_and_max_conversion_gs_in_chinese(self):
        result = suggest_from_form(load_gear_file(Path("建议结果/14.json")))
        debug = debug_view_model(result)
        candidate = debug["lightweight_basis"]["候选体系评估"][0]
        future_75 = debug["lightweight_basis"]["终局 75+ 未来可期"]

        self.assertEqual(candidate["当前重铸前有效 GS（按候选体系）"], 24.0)
        self.assertEqual(candidate["当前重铸后有效 GS（按候选体系）"], 29.7)
        self.assertEqual(candidate["终局预期有效 GS（未转换）"], 52.2)
        self.assertEqual(candidate["终局预期有效 GS（按转换满值）"], 64.3)
        self.assertEqual(candidate["转换满值 GS 增益"], 12.1)
        self.assertEqual(candidate["转换满值来源"], "Fribbels modValues.reforged.greater upper bound (100% quality)")
        self.assertEqual(future_75["终局 75+ 未来可期门槛"], 75.0)
        self.assertEqual(future_75["当前终局目标"], "正式体系")
        self.assertIn("未转换终局 75+ 未来可期概率", future_75)
        self.assertIn("满值转换后终局 75+ 未来可期概率", future_75)

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
        self.assertEqual(debug["strategy_version"], "baili-formal-dp-v1-epic-balanced")
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
                "instance_id": "ingame-save-test",
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
            reloaded = load_gear_file(gear_path)

        self.assertEqual(saved_gear["mainStat"]["type"], gear["mainStat"]["type"])
        self.assertTrue(saved_gear["reforgeEligible"])
        self.assertEqual(saved_gear["itemSource"], "normal_85")
        self.assertEqual(gear["instanceId"], "ingame-save-test")
        self.assertEqual(saved_gear["instanceId"], "ingame-save-test")
        self.assertEqual(saved_result["gear"]["instanceId"], "ingame-save-test")
        self.assertEqual(reloaded["instance_id"], "ingame-save-test")
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
            "01_normal_epic_plus0.json": ("lightweight_prediction", "continue"),
            "02_normal_epic_plus3.json": ("lightweight_prediction", "continue"),
            "03_normal_epic_plus6_speed.json": ("exact_dp", "continue"),
            "04_rift_epic_plus0.json": ("lightweight_prediction", "continue"),
            "05_legacy_reforge_false.json": ("lightweight_prediction", "continue"),
            "07_high_speed_early.json": ("lightweight_prediction", "continue"),
            "08_normal_heroic_plus9_replay.json": ("heroic_speed22_rescue", "stop"),
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

    def test_gui_debug_shows_early_speed_gamble_hit_details_in_chinese(self):
        result = suggest_from_form(load_gear_file(Path("samples/manual_acceptance/02_normal_epic_plus3.json")))

        speed_route = debug_view_model(result)["lightweight_basis"]["早期赌速度"]

        self.assertTrue(speed_route["路线资格"])
        self.assertTrue(speed_route["是否进入速度路线"])
        self.assertTrue(speed_route["部位资格"])
        self.assertEqual(speed_route["品质初始速度阈值"], 2)
        self.assertEqual(speed_route["Epic 硬门槛"], 2)
        self.assertTrue(speed_route["+3 是否命中速度"])
        self.assertEqual(speed_route["下一检查点"], 6)

    def test_gui_debug_shows_ordinary_result_after_epic_speed_miss(self):
        result = suggest_from_form({
            "set": "Destruction",
            "slot": "Armor",
            "main_type": "Defense",
            "main_value": 300,
            "enhance": 3,
            "level": 85,
            "rank": "Epic",
            "item_source": "normal_85",
            "substats": [
                {"type": "Speed", "value": 2, "rolls": 1},
                {"type": "EffectResistancePercent", "value": 8, "rolls": 1},
                {"type": "EffectivenessPercent", "value": 8, "rolls": 1},
                {"type": "Health", "value": 180, "rolls": 2},
            ],
        })

        speed_route = debug_view_model(result)["lightweight_basis"]["早期赌速度"]

        self.assertEqual(speed_route["当前速度"], 2.0)
        self.assertEqual(speed_route["品质初始速度阈值"], 2)
        self.assertEqual(speed_route["Epic 硬门槛"], 2)
        self.assertFalse(speed_route["+3 是否命中速度"])
        self.assertFalse(speed_route["路线资格"])
        self.assertFalse(speed_route["是否进入速度路线"])
        self.assertEqual(speed_route["未命中后普通策略结果"], "谨慎继续")

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
