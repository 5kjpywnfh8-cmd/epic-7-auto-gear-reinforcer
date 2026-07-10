import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 is not installed")
class GuiAppSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        from src.e7_enhance.gui_app import GearEnhanceWindow

        window = GearEnhanceWindow()
        window.show()
        self.app.processEvents()
        return window

    def test_main_window_can_be_created_offscreen(self):
        from src.e7_enhance.gui_support import load_gear_file

        window = self.make_window()
        try:
            self.assertEqual(window.windowTitle(), "第七史诗装备强化判断工具")
            self.assertGreaterEqual(window.minimumWidth(), 1024)
            self.assertGreaterEqual(window.minimumHeight(), 680)
            initial_size = window.size()
            self.assertFalse(window.ocr_button.isEnabled())
            self.assertFalse(window.airtest_button.isEnabled())
            self.assertFalse(window.debug_details.isVisible())
            window.set_form(load_gear_file(Path("samples/gear.json")))
            self.assertEqual(window.set_combo.currentText(), "速度")
            self.assertEqual(window.slot_combo.currentText(), "武器")
            self.assertEqual(window.main_combo.currentText(), "攻击")
            self.assertEqual(window.rank_combo.currentText(), "史诗")
            self.assertEqual(window.substat_table.cellWidget(0, 0).currentText(), "速度")
            self.assertEqual(window.form_data()["set"], "Speed")
            self.assertEqual(window.reforge_status_label.text(), "85级默认可重铸")
            window.run_suggest()
            self.assertEqual(window.size(), initial_size)
            self.assertIsNotNone(window.current_result)
            self.assertNotEqual(window.recommendation_label.text(), "-")
            self.assertNotEqual(window.target_label.text(), "-")
            self.assertIn("策略版本", window.debug_details.toPlainText())
            window.item_source_combo.setCurrentIndex(window.item_source_combo.findData("rift_85"))
            self.assertEqual(window.item_source_combo.currentText(), "异界 85（仅红装）")
            self.assertEqual(window.rank_combo.currentData(), "Epic")
            self.assertFalse(window.rank_combo.isEnabled())
            self.assertEqual(window.form_data()["rank"], "Epic")
            self.assertIn("验收强化回放", window.replay_button.text())
            window.load_forms_from_path(Path("samples/manual_acceptance_gears.json"))
            self.assertGreaterEqual(len(window.sample_forms), 20)
            window.set_form(window.sample_forms[14])
            self.assertEqual(
                [window.substat_table.item(row, 2).text() for row in range(4)],
                ["2", "2", "1", "1"],
            )
            first_set = window.set_combo.currentText()
            window.next_sample()
            self.assertEqual(window.sample_index, 1)
            self.assertNotEqual(window.sample_counter_label.text(), "1 / 1")
            self.assertTrue(window.set_combo.currentText() or first_set)
            self.assertIsNotNone(window.current_result)
            self.assertNotEqual(window.recommendation_label.text(), "-")
        finally:
            window.close()
            self.app.processEvents()

    def test_long_debug_keeps_window_and_splitter_stable_with_internal_scroll(self):
        from PySide6.QtWidgets import QPlainTextEdit

        from src.e7_enhance.gui_support import build_gear_dict, load_gear_file, suggest_from_form

        window = self.make_window()
        try:
            form = load_gear_file(Path("建议结果/07.json"))
            result = suggest_from_form(form)
            dp = result["debug"]["dp_assist"]
            dp["lightweight_basis"] = {
                "decision_reason": "很长的决策依据" * 300,
                "calibration_group": {"selected_category": "输出" * 100},
                "full_category_matches": [{"category": "输出", "diagnostics": "完整分类诊断" * 120}],
            }
            initial_window_size = window.size()
            initial_splitter_sizes = window.main_splitter.sizes()

            window.render_result(result, build_gear_dict(form))
            window.debug_box.setChecked(True)
            self.app.processEvents()

            self.assertEqual(window.size(), initial_window_size)
            self.assertEqual(window.main_splitter.sizes(), initial_splitter_sizes)
            self.assertIsInstance(window.debug_details, QPlainTextEdit)
            self.assertTrue(window.debug_details.isVisible())
            self.assertGreater(window.debug_details.verticalScrollBar().maximum(), 0)
            self.assertEqual(window.debug_details.horizontalScrollBar().maximum(), 0)
            details = window.debug_details.toPlainText()
            self.assertIn("轻量预测决策依据", details)
            self.assertNotIn("lightweight_basis", details)
            self.assertNotIn("calibration_group", details)
        finally:
            window.close()
            self.app.processEvents()

    def test_left_substats_and_suggest_button_remain_accessible_without_horizontal_scroll(self):
        window = self.make_window()
        try:
            self.assertGreaterEqual(window.main_splitter.widget(0).minimumWidth(), 460)
            self.assertTrue(window.suggest_button.isVisible())
            self.assertTrue(all(window.substat_table.cellWidget(row, 0).isVisible() for row in range(4)))
            self.assertEqual(window.substat_table.horizontalScrollBar().maximum(), 0)
            self.assertGreater(window.substat_table.columnWidth(0), window.substat_table.columnWidth(2))
            self.assertGreater(window.main_splitter.sizes()[0], 0)
            self.assertGreater(window.main_splitter.sizes()[1], 0)
        finally:
            window.close()
            self.app.processEvents()

    def test_sample_switch_and_debug_toggle_do_not_resize_window(self):
        window = self.make_window()
        try:
            initial_window_size = window.size()
            initial_splitter_sizes = window.main_splitter.sizes()
            window.load_forms_from_path(Path("samples/manual_acceptance_gears.json"))
            for _ in range(len(window.sample_forms) - 1):
                window.next_sample()
                self.app.processEvents()
                self.assertEqual(window.size(), initial_window_size)
                self.assertEqual(window.main_splitter.sizes(), initial_splitter_sizes)
            window.load_forms_from_path(Path("建议结果/07.json"))
            window.debug_box.setChecked(True)
            window.debug_box.setChecked(False)
            self.app.processEvents()

            self.assertEqual(window.size(), initial_window_size)
            self.assertEqual(window.main_splitter.sizes(), initial_splitter_sizes)
            self.assertEqual(window.recommendation_label.text(), "继续")
            self.assertIn("调试详情", window.debug_box.title())
        finally:
            window.close()
            self.app.processEvents()

    def test_invalid_import_shows_error_without_changing_layout(self):
        window = self.make_window()
        try:
            initial_window_size = window.size()
            initial_splitter_sizes = window.main_splitter.sizes()
            invalid_path = Path("samples/manual_acceptance/06_invalid_rift_heroic.json")
            with patch(
                "src.e7_enhance.gui_app.QFileDialog.getOpenFileName",
                return_value=(str(invalid_path), "JSON Files (*.json)"),
            ), patch("src.e7_enhance.gui_app.QMessageBox.warning") as warning:
                window.import_gear()

            self.app.processEvents()
            warning.assert_called_once()
            self.assertEqual(window.size(), initial_window_size)
            self.assertEqual(window.main_splitter.sizes(), initial_splitter_sizes)
        finally:
            window.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
