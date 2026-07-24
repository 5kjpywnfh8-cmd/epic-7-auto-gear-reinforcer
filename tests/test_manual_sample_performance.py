import importlib.util
import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


@unittest.skipIf(importlib.util.find_spec("PySide6") is None, "PySide6 is not installed")
class ManualSamplePerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls):
        # Offscreen Qt can otherwise defer native widget destruction to process
        # shutdown, which intermittently aborts this isolated performance file.
        cls.app.closeAllWindows()
        cls.app.processEvents()

    def test_425_item_import_keeps_qt_heartbeat_running(self):
        """实际 425 件导入期间，Qt 事件循环必须持续处理心跳。"""
        from PySide6.QtCore import QEventLoop, QTimer

        from src.e7_enhance.gui_app import RealSampleManagerDialog

        source = Path("samples/real_acceptance_fribbels_20260610_plus0_plus3.json")
        self.assertTrue(source.exists())
        with tempfile.TemporaryDirectory() as tmp:
            dialog = RealSampleManagerDialog(None, Path(tmp) / "records.json")
            heartbeat = {"active": False, "count": 0}
            timer = QTimer()
            timer.setInterval(2)
            timer.timeout.connect(lambda: heartbeat.__setitem__("count", heartbeat["count"] + int(heartbeat["active"])))
            loop = QEventLoop()

            def finish_when_imported():
                done = len(dialog.store.list_snapshots()) == 425 and not bool(getattr(dialog, "is_busy", False))
                if done:
                    heartbeat["active"] = False
                    loop.quit()
                else:
                    QTimer.singleShot(2, finish_when_imported)

            def start_import():
                heartbeat["active"] = True
                dialog.import_records()
                self.assertTrue(dialog.is_busy)
                self.assertFalse(dialog.import_records_button.isEnabled())
                finish_when_imported()

            with patch(
                "src.e7_enhance.gui_app.QFileDialog.getOpenFileName",
                return_value=(str(source), "JSON Files (*.json)"),
            ), patch("src.e7_enhance.gui_app.QMessageBox.information"):
                timer.start()
                QTimer.singleShot(20, start_import)
                loop.exec()
            timer.stop()
            dialog.close()
            dialog.deleteLater()
            timer.deleteLater()
            loop.deleteLater()
            self.app.processEvents()

        self.assertGreater(
            heartbeat["count"],
            0,
            "导入期间 Qt 事件循环未能处理心跳，窗口会表现为无响应。",
        )

    def test_individual_enhance_filters_are_strict(self):
        from src.e7_enhance.gui_app import RealSampleManagerDialog, set_combo_text
        from src.e7_enhance.gui_support import load_gear_file

        form = load_gear_file(Path("建议结果/14.json"))
        forms = []
        for enhance in (0, 3, 6, 9, 12, 15):
            item = deepcopy(form)
            item["enhance"] = enhance
            item["instance_id"] = f"filter-{enhance}"
            forms.append(item)
        with tempfile.TemporaryDirectory() as tmp:
            dialog = RealSampleManagerDialog(None, Path(tmp) / "records.json")
            try:
                result = dialog.store.import_forms(forms, "filters.json")
                self.assertEqual(result.imported, 6)
                for enhance in (0, 3, 6, 9, 12, 15):
                    set_combo_text(dialog.enhance_filter, f"enhance:{enhance}")
                    dialog.refresh_records()
                    self.assertEqual(dialog.record_table.rowCount(), 1)
                    self.assertEqual(dialog._snapshots[0]["gear"]["enhance"], enhance)
                set_combo_text(dialog.enhance_filter, "unfinished")
                dialog.refresh_records()
                self.assertEqual(dialog.record_table.rowCount(), 5)
            finally:
                dialog.close()
                dialog.deleteLater()
                self.app.processEvents()

    def test_acceptance_batch_filter_keeps_existing_filters(self):
        from src.e7_enhance.gui_app import RealSampleManagerDialog, set_combo_text
        from src.e7_enhance.gui_support import load_gear_file

        form = load_gear_file(Path("建议结果/14.json"))
        form["instance_id"] = "batch-filter-gear"
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            dialog = RealSampleManagerDialog(None, directory / "records.json")
            try:
                dialog.store.import_forms([form], "original.json")
                payload = {
                    "acceptance_subset": {
                        "batch_id": "batch-heroic",
                        "batch_name": "Heroic 回退验收",
                        "purpose": "测试筛选",
                        "source_file": "original.json",
                        "selection_rule": "测试",
                        "tags": ["紫装"],
                    },
                    "items": [dialog.store.list_snapshots()[0]["gear"]],
                }
                subset = directory / "subset.json"
                subset.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                dialog.store.import_path(subset)
                dialog.refresh_records()

                set_combo_text(dialog.enhance_filter, "all")
                set_combo_text(dialog.acceptance_batch_filter, "batch-heroic")
                self.assertEqual(dialog.record_table.rowCount(), 1)
                set_combo_text(dialog.enhance_filter, "enhance:3")
                self.assertEqual(dialog.record_table.rowCount(), 1)
                set_combo_text(dialog.rank_filter, "Heroic")
                self.assertEqual(dialog.record_table.rowCount(), 0)
            finally:
                dialog.close()
                dialog.deleteLater()
                self.app.processEvents()

    def test_heroic_batch_filter_shows_16_without_hiding_original_batch(self):
        from src.e7_enhance.gui_app import RealSampleManagerDialog, set_combo_text

        with tempfile.TemporaryDirectory() as tmp:
            dialog = RealSampleManagerDialog(None, Path(tmp) / "records.json")
            try:
                original = dialog.store.import_path(Path("samples/real_acceptance_fribbels_20260610_plus0_plus3.json"))
                dialog.store.import_path(Path("samples/heroic_resource_fallback_acceptance_20260712.json"))
                dialog.refresh_records()
                set_combo_text(dialog.enhance_filter, "all")
                set_combo_text(dialog.acceptance_batch_filter, "heroic_resource_fallback_20260712")
                self.assertEqual(dialog.record_table.rowCount(), 16)
                set_combo_text(dialog.acceptance_batch_filter, original.batch_id)
                self.assertEqual(dialog.record_table.rowCount(), 425)
            finally:
                dialog.close()
                dialog.deleteLater()
                self.app.processEvents()

    def test_425_item_review_save_keeps_qt_heartbeat_and_updates_one_row(self):
        from PySide6.QtCore import QEventLoop, QTimer
        from src.e7_enhance.gui_app import RealSampleManagerDialog, set_combo_text

        source = Path("samples/real_acceptance_fribbels_20260610_plus0_plus3.json")
        with tempfile.TemporaryDirectory() as tmp:
            dialog = RealSampleManagerDialog(None, Path(tmp) / "records.json")
            try:
                dialog.store.import_path(source)
                dialog.refresh_records()
                dialog.record_table.selectRow(0)
                self.app.processEvents()
                set_combo_text(dialog.human_decision_combo, "continue")
                refresh_calls = {"count": 0}
                original_refresh = dialog.refresh_records

                def counted_refresh():
                    refresh_calls["count"] += 1
                    original_refresh()

                dialog.refresh_records = counted_refresh
                heartbeat = {"active": True, "count": 0}
                timer = QTimer()
                timer.setInterval(2)
                timer.timeout.connect(lambda: heartbeat.__setitem__("count", heartbeat["count"] + int(heartbeat["active"])))
                loop = QEventLoop()

                timer.start()
                dialog.save_review()
                self.assertTrue(dialog.is_busy)
                self.assertFalse(dialog.save_review_button.isEnabled())
                thread = dialog._task_thread
                self.assertIsNotNone(thread)
                timeout = QTimer()
                timeout.setSingleShot(True)
                timeout.timeout.connect(loop.quit)
                thread.finished.connect(loop.quit)
                timeout.start(10_000)
                loop.exec()
                timeout.stop()
                heartbeat["active"] = False
                timer.stop()

                self.assertFalse(dialog.is_busy, "人工记录后台线程未在10秒内完成")
                self.assertGreater(heartbeat["count"], 0)
                self.assertEqual(refresh_calls["count"], 0)
                self.assertEqual(dialog.record_table.item(0, 8).text(), "continue")
                self.assertEqual(dialog.store.list_snapshots()[0]["human_review"]["decision"], "continue")
            finally:
                dialog.close()
                dialog.deleteLater()
                timer.deleteLater()
                timeout.deleteLater()
                loop.deleteLater()
                from PySide6.QtCore import QCoreApplication, QEvent

                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                self.app.processEvents()
