from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .airtest_adapter import NullAirtestAdapter
from .epic_plus3_prospective import normalized_fingerprint, observe_trusted_fribbels_state
from .gui_support import (
    DEFAULT_GEAR_FORM,
    DISPLAY_VALUE_LABELS,
    build_gear_dict,
    format_debug_details,
    load_gear_file,
    load_gear_collection,
    load_gear_collection_with_report,
    save_gear_file,
    save_suggestion_file,
    suggest_from_form,
    summary_view_model,
)
from .acceptance_replay import AcceptanceReplay
from .manual_sample_store import ManualSampleStore
from .models import Gear

try:
    from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
    from PySide6.QtWidgets import (
        QApplication,
        QAbstractItemView,
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QPlainTextEdit,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - exercised when launching without optional dependency
    PYSIDE6_IMPORT_ERROR = exc
    QApplication = None
    QMainWindow = object
else:
    PYSIDE6_IMPORT_ERROR = None


SET_OPTIONS = [
    ("Speed", "速度"), ("Critical", "暴击"), ("Destruction", "暴伤"),
    ("Attack", "攻击"), ("Health", "生命"), ("Defense", "防御"),
    ("Immunity", "免疫"), ("Counter", "反击"), ("Lifesteal", "吸血"),
    ("Penetration", "穿透"), ("Torrent", "激流"), ("Resist", "抵抗"),
    ("Hit", "命中"), ("Injury", "伤口"), ("Protection", "保护"),
    ("Riposte", "回击"), ("Opener", "先手"), ("Chase", "追击"),
    ("ReversalSet", "逆袭"), ("UnitySet", "夹攻"),
]
SLOT_OPTIONS = [
    ("Weapon", "武器"), ("Helmet", "头盔"), ("Armor", "衣服"),
    ("Necklace", "项链"), ("Ring", "戒指"), ("Boots", "鞋子"),
]
RANK_OPTIONS = [("Rare", "稀有"), ("Heroic", "英雄"), ("Epic", "史诗")]
STAT_OPTIONS = [
    ("", ""), ("Speed", "速度"), ("AttackPercent", "攻击%"),
    ("DefensePercent", "防御%"), ("HealthPercent", "生命%"),
    ("EffectivenessPercent", "效果命中%"), ("EffectResistancePercent", "效果抵抗%"),
    ("CriticalHitChancePercent", "暴击率%"), ("CriticalHitDamagePercent", "暴击伤害%"),
    ("Attack", "攻击"), ("Defense", "防御"), ("Health", "生命"),
]
MAIN_STAT_OPTIONS = [
    ("Attack", "攻击"), ("Defense", "防御"), ("Health", "生命"),
    ("AttackPercent", "攻击%"), ("DefensePercent", "防御%"),
    ("HealthPercent", "生命%"), ("Speed", "速度"),
    ("EffectivenessPercent", "效果命中%"), ("EffectResistancePercent", "效果抵抗%"),
    ("CriticalHitChancePercent", "暴击率%"), ("CriticalHitDamagePercent", "暴击伤害%"),
]
ITEM_SOURCE_OPTIONS = [("normal_85", "普通 85"), ("rift_85", "异界 85（仅红装）")]


if PYSIDE6_IMPORT_ERROR is None:

    class GearEnhanceWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("第七史诗装备强化判断工具")
            self.setMinimumSize(1024, 680)
            screen = QApplication.primaryScreen()
            available = screen.availableGeometry().size() if screen else None
            width = min(1280, available.width() - 32) if available else 1280
            height = min(820, available.height() - 32) if available else 820
            self.resize(max(1024, width), max(680, height))
            self.airtest_adapter = NullAirtestAdapter()
            self.current_result: dict[str, Any] | None = None
            self.current_gear_code = ""
            self.current_instance_id = ""
            self.current_roll_history: list[dict[str, Any]] = []
            self.current_gear_source = ""
            self.sample_forms: list[dict[str, Any]] = []
            self.sample_index = 0
            self._trusted_runtime_fingerprints: set[str] = set()
            self._build_ui()
            self.set_form(DEFAULT_GEAR_FORM)

        def _build_ui(self) -> None:
            root = QWidget()
            self.setCentralWidget(root)
            layout = QVBoxLayout(root)

            toolbar = QWidget()
            toolbar_layout = QGridLayout(toolbar)
            self.import_button = QPushButton("导入装备 JSON")
            self.load_acceptance_button = QPushButton("加载验收样本")
            self.replay_button = QPushButton("验收强化回放")
            self.real_sample_manager_button = QPushButton("真实样本管理")
            self.prev_sample_button = QPushButton("上一件")
            self.next_sample_button = QPushButton("下一件")
            self.sample_counter_label = QLabel("1 / 1")
            self.save_gear_button = QPushButton("保存装备 JSON")
            self.save_result_button = QPushButton("保存建议结果")
            self.ocr_button = QPushButton("截图/OCR（预留）")
            self.ocr_button.setEnabled(False)
            self.airtest_button = QPushButton("Airtest 自动点击（预留）")
            self.airtest_button.setEnabled(False)
            for index, button in enumerate((
                self.import_button,
                self.load_acceptance_button,
                self.replay_button,
                self.prev_sample_button,
                self.next_sample_button,
                self.save_gear_button,
                self.save_result_button,
                self.ocr_button,
                self.airtest_button,
            )):
                button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                toolbar_layout.addWidget(button, index // 4, index % 4)
            toolbar_layout.addWidget(self.sample_counter_label, 2, 1)
            toolbar_layout.addWidget(self.real_sample_manager_button, 2, 2)
            for column in range(4):
                toolbar_layout.setColumnStretch(column, 1)
            layout.addWidget(toolbar)

            self.main_splitter = QSplitter(Qt.Horizontal)
            self.main_splitter.setChildrenCollapsible(False)
            self.main_splitter.setHandleWidth(8)
            layout.addWidget(self.main_splitter, 1)

            form_box = QGroupBox("装备字段")
            form_box.setMinimumWidth(480)
            form_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self.main_splitter.addWidget(form_box)
            form_layout = QVBoxLayout(form_box)

            self.form_scroll = QScrollArea()
            self.form_scroll.setWidgetResizable(True)
            self.form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.form_scroll.setFrameShape(QScrollArea.NoFrame)
            form_content = QWidget()
            self.form_scroll.setWidget(form_content)
            form_content_layout = QVBoxLayout(form_content)

            top_form = QFormLayout()
            top_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            self.set_combo = QComboBox()
            add_combo_options(self.set_combo, SET_OPTIONS)
            self.slot_combo = QComboBox()
            add_combo_options(self.slot_combo, SLOT_OPTIONS)
            self.main_combo = QComboBox()
            add_combo_options(self.main_combo, MAIN_STAT_OPTIONS)
            self.main_value = QLineEdit()
            self.enhance_spin = QSpinBox()
            self.enhance_spin.setRange(0, 15)
            self.enhance_spin.setSingleStep(3)
            self.level_spin = QSpinBox()
            self.level_spin.setRange(1, 100)
            self.rank_combo = QComboBox()
            add_combo_options(self.rank_combo, RANK_OPTIONS)
            self.item_source_combo = QComboBox()
            add_combo_options(self.item_source_combo, ITEM_SOURCE_OPTIONS)
            self.reforge_status_label = QLabel()
            top_form.addRow("套装", self.set_combo)
            top_form.addRow("部位", self.slot_combo)
            top_form.addRow("主属性", self.main_combo)
            top_form.addRow("主属性数值", self.main_value)
            top_form.addRow("强化等级", self.enhance_spin)
            top_form.addRow("装备等级", self.level_spin)
            top_form.addRow("品质", self.rank_combo)
            top_form.addRow("装备来源", self.item_source_combo)
            top_form.addRow("重铸规则", self.reforge_status_label)
            form_content_layout.addLayout(top_form)

            self.substat_table = QTableWidget(4, 3)
            self.substat_table.setHorizontalHeaderLabels(["副属性", "数值", "强化次数"])
            self.substat_table.verticalHeader().setVisible(False)
            self.substat_table.setMinimumWidth(420)
            self.substat_table.setMinimumHeight(168)
            self.substat_table.setMaximumHeight(168)
            self.substat_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.substat_table.setSizeAdjustPolicy(QAbstractItemView.AdjustIgnored)
            header = self.substat_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Fixed)
            self.substat_table.setColumnWidth(0, 210)
            self.substat_table.setColumnWidth(1, 90)
            self.substat_table.setColumnWidth(2, 100)
            form_content_layout.addWidget(QLabel("副属性"))
            form_content_layout.addWidget(self.substat_table)
            form_content_layout.addStretch(1)

            form_layout.addWidget(self.form_scroll, 1)

            self.suggest_button = QPushButton("判断")
            form_layout.addWidget(self.suggest_button)

            result_box = QGroupBox("建议")
            result_box.setMinimumWidth(480)
            result_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            self.main_splitter.addWidget(result_box)
            result_layout = QVBoxLayout(result_box)
            grid = QFormLayout()
            self.recommendation_label = QLabel("-")
            self.next_check_label = QLabel("-")
            self.target_label = QLabel("-")
            for label in (self.recommendation_label, self.next_check_label, self.target_label):
                label.setWordWrap(True)
                label.setMaximumHeight(48)
            grid.addRow("建议", self.recommendation_label)
            grid.addRow("下一检查点", self.next_check_label)
            grid.addRow("目标体系", self.target_label)
            result_layout.addLayout(grid)
            result_layout.addWidget(QLabel("关键理由"))
            self.reasons_text = QPlainTextEdit()
            self.reasons_text.setReadOnly(True)
            self.reasons_text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.reasons_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.reasons_text.setMinimumHeight(96)
            self.reasons_text.setMaximumHeight(150)
            result_layout.addWidget(self.reasons_text)

            self.debug_box = QGroupBox("调试详情")
            self.debug_box.setCheckable(True)
            self.debug_box.setChecked(False)
            debug_box_layout = QVBoxLayout(self.debug_box)
            self.debug_details = QPlainTextEdit()
            self.debug_details.setReadOnly(True)
            self.debug_details.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.debug_details.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.debug_details.setMinimumHeight(220)
            self.debug_details.setVisible(False)
            debug_box_layout.addWidget(self.debug_details)
            result_layout.addWidget(self.debug_box, 1)

            self.main_splitter.setStretchFactor(0, 1)
            self.main_splitter.setStretchFactor(1, 1)
            self.main_splitter.setSizes([560, 640])

            self.import_button.clicked.connect(self.import_gear)
            self.load_acceptance_button.clicked.connect(self.load_acceptance_samples)
            self.replay_button.clicked.connect(self.open_replay)
            self.real_sample_manager_button.clicked.connect(self.open_real_sample_manager)
            self.prev_sample_button.clicked.connect(self.prev_sample)
            self.next_sample_button.clicked.connect(self.next_sample)
            self.save_gear_button.clicked.connect(self.save_gear)
            self.save_result_button.clicked.connect(self.save_result)
            self.suggest_button.clicked.connect(self.run_suggest)
            self.debug_box.toggled.connect(self.debug_details.setVisible)
            self.item_source_combo.currentIndexChanged.connect(self.apply_item_source_constraints)
            self.level_spin.valueChanged.connect(self.update_reforge_status)
            self.update_reforge_status()
            self.update_sample_controls()

        def apply_item_source_constraints(self) -> None:
            is_rift = combo_value(self.item_source_combo) == "rift_85"
            if is_rift:
                set_combo_text(self.rank_combo, "Epic")
            self.rank_combo.setEnabled(not is_rift)

        def update_reforge_status(self) -> None:
            self.reforge_status_label.setText("85级默认可重铸" if self.level_spin.value() == 85 else "90级已完成终局")

        def set_form(self, form: dict[str, Any]) -> None:
            self.current_gear_code = str(form.get("code") or "")
            self.current_instance_id = str(form.get("instance_id") or "")
            self.current_roll_history = list(form.get("rollHistory") or [])
            self.current_gear_source = str(form.get("gear_source") or "")
            set_combo_text(self.set_combo, str(form.get("set") or "Speed"))
            set_combo_text(self.slot_combo, str(form.get("slot") or "Weapon"))
            set_combo_text(self.main_combo, str(form.get("main_type") or "Attack"))
            self.main_value.setText(format_value(form.get("main_value", 0)))
            self.enhance_spin.setValue(int(float(form.get("enhance") or 0)))
            self.level_spin.setValue(int(float(form.get("level") or 85)))
            set_combo_text(self.rank_combo, str(form.get("rank") or "Epic"))
            set_combo_text(self.item_source_combo, str(form.get("item_source") or "normal_85"))
            self.apply_item_source_constraints()
            self.update_reforge_status()
            substats = list(form.get("substats") or [])
            while len(substats) < 4:
                substats.append({"type": "", "value": 0, "rolls": 0})
            for row in range(4):
                stat = substats[row]
                combo = QComboBox()
                add_combo_options(combo, STAT_OPTIONS)
                set_combo_text(combo, str(stat.get("type") or ""))
                self.substat_table.setCellWidget(row, 0, combo)
                self.substat_table.setItem(row, 1, QTableWidgetItem(format_value(stat.get("value", 0))))
                self.substat_table.setItem(row, 2, QTableWidgetItem(str(int(float(stat.get("rolls") or 0)))))

        def load_forms_from_path(self, path: Path) -> dict[str, Any]:
            try:
                forms, report = load_gear_collection_with_report(path)
            except json.JSONDecodeError:
                # Saved single-result packages retain the existing tolerant loader path.
                forms = [load_gear_file(path)]
                report = {
                    "source_format": "native",
                    "total_items": 1,
                    "loaded_items": 1,
                    "skipped_items": 0,
                    "skipped_by_reason": {},
                }
            self.sample_forms = forms
            self._trusted_runtime_fingerprints = set()
            if report.get("source_format") == "fribbels":
                for form in forms:
                    try:
                        self._trusted_runtime_fingerprints.add(normalized_fingerprint(Gear.from_dict(build_gear_dict(form))))
                    except (KeyError, TypeError, ValueError):
                        continue
            self.sample_index = 0
            self.set_form(forms[0])
            self.run_suggest()
            self.update_sample_controls()
            return report

        def load_acceptance_samples(self) -> None:
            directory = Path(__file__).resolve().parents[2] / "samples" / "manual_acceptance"
            forms = []
            rejected = []
            for path in sorted(directory.glob("*.json")):
                try:
                    forms.append(load_gear_file(path))
                except ValueError:
                    rejected.append(path.name)
            if not forms:
                QMessageBox.warning(self, "加载失败", "验收样本中没有可导入的合法装备。")
                return
            self.sample_forms = forms
            self.sample_index = 0
            self.set_form(forms[0])
            self.run_suggest()
            self.update_sample_controls()
            if rejected:
                QMessageBox.information(self, "验收样本", f"已加载 {len(forms)} 个合法样本。{', '.join(rejected)} 用于错误态验收。")

        def open_replay(self) -> None:
            AcceptanceReplayDialog(self).exec()

        def open_real_sample_manager(self) -> None:
            records_path = Path(__file__).resolve().parents[2] / "manual_acceptance" / "real_sample_records.json"
            RealSampleManagerDialog(self, records_path).exec()

        def prev_sample(self) -> None:
            if not self.sample_forms:
                return
            self.sample_index = max(0, self.sample_index - 1)
            self.set_form(self.sample_forms[self.sample_index])
            self.run_suggest()
            self.update_sample_controls()

        def next_sample(self) -> None:
            if not self.sample_forms:
                return
            self.sample_index = min(len(self.sample_forms) - 1, self.sample_index + 1)
            self.set_form(self.sample_forms[self.sample_index])
            self.run_suggest()
            self.update_sample_controls()

        def update_sample_controls(self) -> None:
            total = len(self.sample_forms) or 1
            index = self.sample_index + 1 if self.sample_forms else 1
            self.sample_counter_label.setText(f"{index} / {total}")
            self.prev_sample_button.setEnabled(bool(self.sample_forms) and self.sample_index > 0)
            self.next_sample_button.setEnabled(bool(self.sample_forms) and self.sample_index < len(self.sample_forms) - 1)

        def form_data(self) -> dict[str, Any]:
            substats = []
            for row in range(4):
                combo = self.substat_table.cellWidget(row, 0)
                item_value = self.substat_table.item(row, 1)
                item_rolls = self.substat_table.item(row, 2)
                stat_type = combo_value(combo) if isinstance(combo, QComboBox) else ""
                substats.append(
                    {
                        "type": stat_type,
                        "value": text_number(item_value.text() if item_value else "0"),
                        "rolls": int(text_number(item_rolls.text() if item_rolls else "0")),
                    }
                )
            return {
                "set": combo_value(self.set_combo),
                "slot": combo_value(self.slot_combo),
                "main_type": combo_value(self.main_combo),
                "main_value": text_number(self.main_value.text()),
                "enhance": self.enhance_spin.value(),
                "level": self.level_spin.value(),
                "rank": combo_value(self.rank_combo),
                "substats": substats,
                "rollHistory": list(self.current_roll_history),
                "code": self.current_gear_code,
                "instance_id": self.current_instance_id,
                "item_source": combo_value(self.item_source_combo),
                "gear_source": self.current_gear_source,
                "reforge_eligible": self.level_spin.value() == 85,
            }

        def import_gear(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "导入装备 JSON", "", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
            try:
                report = self.load_forms_from_path(Path(path))
                if report.get("source_format") == "fribbels":
                    QMessageBox.information(self, "Fribbels 导入完成", collection_import_message(report))
            except Exception as exc:
                QMessageBox.warning(self, "导入失败", chinese_error(str(exc)))

        def save_gear(self) -> None:
            path, _ = QFileDialog.getSaveFileName(self, "保存装备 JSON", "gear.json", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
            try:
                save_gear_file(Path(path), self.form_data())
            except Exception as exc:
                QMessageBox.warning(self, "保存失败", chinese_error(str(exc)))

        def save_result(self) -> None:
            if self.current_result is None:
                self.run_suggest()
            path, _ = QFileDialog.getSaveFileName(self, "保存建议结果", "suggestion.json", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
            try:
                save_suggestion_file(Path(path), self.form_data(), self.current_result or {})
            except Exception as exc:
                QMessageBox.warning(self, "保存失败", chinese_error(str(exc)))

        def run_suggest(self) -> None:
            try:
                form = self.form_data()
                gear_data = build_gear_dict(form)
                self.current_result = suggest_from_form(form)
                self._observe_trusted_runtime_state(gear_data, self.current_result)
                self.render_result(self.current_result, gear_data)
            except Exception as exc:
                QMessageBox.warning(self, "判断失败", chinese_error(str(exc)))

        def _observe_trusted_runtime_state(self, gear_data: dict[str, Any], result: dict[str, Any]) -> None:
            """Observe only unchanged states from a complete Fribbels import."""
            try:
                fingerprint = normalized_fingerprint(Gear.from_dict(gear_data))
                if fingerprint in self._trusted_runtime_fingerprints:
                    observe_trusted_fribbels_state(gear_data, result)
            except Exception:
                # Observation is deliberately invisible and must never change
                # the existing suggestion/error flow.
                pass

        def render_result(self, result: dict[str, Any], gear_data: dict[str, Any] | None = None) -> None:
            summary = summary_view_model(result)
            self.recommendation_label.setText(summary["recommendation_label"])
            next_check = summary["next_check_at"]
            self.next_check_label.setText(f"+{next_check}" if next_check is not None else "-")
            self.target_label.setText(summary["target_profile"])
            self.reasons_text.setPlainText("\n".join(f"- {reason}" for reason in summary["reasons"]) or "-")
            self.debug_details.setPlainText(format_debug_details(result, gear_data or {}))


else:

    class GearEnhanceWindow:  # type: ignore[no-redef]
        def __init__(self) -> None:
            raise RuntimeError("PySide6 is required to launch the desktop GUI") from PYSIDE6_IMPORT_ERROR


if PYSIDE6_IMPORT_ERROR is None:

    class _ManualSampleTask(QObject):
        progress = Signal(str, int, int)
        finished = Signal()

        def __init__(self, kind: str, records_path: Path, payload: dict[str, Any]) -> None:
            super().__init__()
            self.kind = kind
            self.records_path = records_path
            self.payload = payload
            self.store: ManualSampleStore | None = None
            self.result: Any = None
            self.error: Exception | None = None

        @Slot()
        def run(self) -> None:
            try:
                self.store = ManualSampleStore(self.records_path)
                if self.kind == "import":
                    self.result = self.store.import_path(self.payload["path"], self.progress.emit)
                elif self.kind == "save":
                    self.result = self.store.update_review(
                        self.payload["sample_id"],
                        self.payload["snapshot_id"],
                        decision=self.payload["decision"],
                        consistency=self.payload["consistency"],
                        reason=self.payload["reason"],
                        note=self.payload["note"],
                        progress=self.progress.emit,
                    )
                else:
                    raise ValueError("未知的真实样本后台任务。")
            except Exception as exc:  # The GUI converts this into a Chinese message on its own thread.
                self.error = exc
            finally:
                self.finished.emit()

    class RealSampleManagerDialog(QDialog):
        """独立的真实装备人工验收窗口，不改变主窗口布局。"""

        def __init__(self, parent: QWidget | None = None, records_path: Path | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("真实样本管理")
            self.setMinimumSize(980, 640)
            self.resize(1180, 760)
            default_path = Path(__file__).resolve().parents[2] / "manual_acceptance" / "real_sample_records.json"
            self.store = ManualSampleStore(records_path or default_path)
            self._snapshots: list[dict[str, Any]] = []
            self._current_snapshot: dict[str, Any] | None = None
            self._task_thread: QThread | None = None
            self._task_worker: _ManualSampleTask | None = None
            self._task_kind: str | None = None
            self.last_operation_timings_ms: dict[str, float] = {}
            self._build_ui()
            self.refresh_records()

        @property
        def is_busy(self) -> bool:
            return self._task_thread is not None

        def _build_ui(self) -> None:
            layout = QVBoxLayout(self)
            filters = QHBoxLayout()
            self.import_records_button = QPushButton("导入兼容装备 JSON")
            self.enhance_filter = QComboBox()
            for enhance in (0, 3, 6, 9, 12, 15):
                self.enhance_filter.addItem(f"+{enhance}", f"enhance:{enhance}")
            self.enhance_filter.addItem("全部未满强化", "unfinished")
            self.enhance_filter.addItem("全部", "all")
            self.source_filter = self._filter_combo("全部装备来源", [("normal_85", "普通 85"), ("rift_85", "异界 85（仅红装）")])
            self.acceptance_batch_filter = QComboBox()
            self.acceptance_batch_filter.addItem("全部验收批次", "")
            self.rank_filter = self._filter_combo("全部品质", [("Epic", "红装"), ("Heroic", "紫装")])
            self.slot_filter = self._filter_combo("全部部位", [(value, label) for value, label in SLOT_OPTIONS])
            self.set_filter = self._filter_combo("全部套装", [(value, label) for value, label in SET_OPTIONS])
            self.review_filter = self._filter_combo("全部审核状态", [("pending", "待审核"), ("reviewed", "已审核")])
            self.inconsistent_filter = QComboBox()
            self.inconsistent_filter.addItem("全部一致性", False)
            self.inconsistent_filter.addItem("仅工具与人工不一致", True)
            for widget in (
                self.import_records_button, self.enhance_filter, self.source_filter, self.acceptance_batch_filter, self.rank_filter,
                self.slot_filter, self.set_filter, self.review_filter, self.inconsistent_filter,
            ):
                filters.addWidget(widget)
            layout.addLayout(filters)
            self.task_status_label = QLabel("状态：空闲")
            self.task_status_label.setWordWrap(True)
            layout.addWidget(self.task_status_label)

            content = QSplitter(Qt.Horizontal)
            self.record_table = QTableWidget(0, 10)
            self.record_table.setHorizontalHeaderLabels([
                "样本编号", "装备来源", "验收批次", "品质", "强化", "套装", "部位", "工具建议", "人工判断", "审核状态",
            ])
            self.record_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.record_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.record_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.record_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.record_table.horizontalHeader().setStretchLastSection(True)
            for column, width in enumerate((180, 112, 180, 72, 64, 76, 72, 100, 100, 82)):
                self.record_table.setColumnWidth(column, width)
            content.addWidget(self.record_table)

            self.details_text = QPlainTextEdit()
            self.details_text.setReadOnly(True)
            self.details_text.setLineWrapMode(QPlainTextEdit.WidgetWidth)
            self.details_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            content.addWidget(self.details_text)
            content.setSizes([560, 620])
            layout.addWidget(content, 1)

            review_box = QGroupBox("人工记录")
            review_layout = QGridLayout(review_box)
            self.human_decision_combo = self._filter_combo("未填写", [
                ("continue", "继续"), ("cautious_continue", "谨慎继续"), ("stop", "停止"),
                ("keep", "保留"), ("convert", "转换/过渡"), ("uncertain", "不确定"),
            ])
            self.consistency_combo = self._filter_combo("未填写", [
                ("一致", "一致"), ("不完全一致", "不完全一致"), ("不一致", "不一致"),
            ])
            self.reason_combo = self._filter_combo("未填写", [
                ("目标体系错误", "目标体系错误"), ("转换候选错误", "转换候选错误"), ("继续/停止分歧", "继续/停止分歧"),
                ("门槛不合理", "门槛不合理"), ("输入识别错误", "输入识别错误"), ("debug 不清楚", "debug 不清楚"), ("其他", "其他"),
            ])
            self.note_edit = QLineEdit()
            self.save_review_button = QPushButton("保存记录")
            review_layout.addWidget(QLabel("人工判断"), 0, 0)
            review_layout.addWidget(self.human_decision_combo, 0, 1)
            review_layout.addWidget(QLabel("一致性"), 0, 2)
            review_layout.addWidget(self.consistency_combo, 0, 3)
            review_layout.addWidget(QLabel("分歧原因"), 1, 0)
            review_layout.addWidget(self.reason_combo, 1, 1)
            review_layout.addWidget(QLabel("备注"), 1, 2)
            review_layout.addWidget(self.note_edit, 1, 3)
            review_layout.addWidget(self.save_review_button, 0, 4, 2, 1)
            review_layout.setColumnStretch(3, 1)
            layout.addWidget(review_box)

            self.import_records_button.clicked.connect(self.import_records)
            self.record_table.itemSelectionChanged.connect(self._select_current_record)
            self.save_review_button.clicked.connect(self.save_review)
            for combo in (
                self.enhance_filter, self.source_filter, self.acceptance_batch_filter, self.rank_filter, self.slot_filter,
                self.set_filter, self.review_filter, self.inconsistent_filter,
            ):
                combo.currentIndexChanged.connect(self.refresh_records)

        @staticmethod
        def _filter_combo(empty_label: str, items: list[tuple[str, str]]) -> QComboBox:
            combo = QComboBox()
            combo.addItem(empty_label, "")
            for value, label in items:
                combo.addItem(label, value)
            return combo

        def import_records(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "导入真实样本 JSON", "", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
            self._start_task("import", {"path": Path(path)})

        def _start_task(self, kind: str, payload: dict[str, Any]) -> None:
            if self.is_busy:
                return
            thread = QThread(self)
            worker = _ManualSampleTask(kind, self.store.records_path, payload)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.progress.connect(self._update_task_status)
            worker.finished.connect(thread.quit)
            thread.finished.connect(self._finish_task)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            self._task_thread = thread
            self._task_worker = worker
            self._task_kind = kind
            self._set_task_busy(True)
            self.task_status_label.setText("状态：正在导入真实样本..." if kind == "import" else "状态：正在保存人工记录...")
            thread.start()

        def _set_task_busy(self, busy: bool) -> None:
            self.import_records_button.setEnabled(not busy)
            self.save_review_button.setEnabled(not busy and self._current_snapshot is not None)

        def _update_task_status(self, stage: str, current: int, total: int) -> None:
            if total > 1:
                self.task_status_label.setText(f"状态：{stage}（{current}/{total}）")
            else:
                self.task_status_label.setText(f"状态：{stage}")

        def _finish_task(self) -> None:
            worker = self._task_worker
            kind = self._task_kind
            self._task_thread = None
            self._task_worker = None
            self._task_kind = None
            if worker is None:
                return
            if worker.error is not None:
                self.task_status_label.setText("状态：操作失败")
                QMessageBox.warning(self, "真实样本操作失败", chinese_error(str(worker.error)))
                self._set_task_busy(False)
                return
            if worker.store is not None:
                self.store = worker.store
            if kind == "import":
                result = worker.result
                self.last_operation_timings_ms = dict(result.timings_ms)
                self._refresh_acceptance_batch_filter(result.batch_id)
                self._clear_non_batch_filters()
                self.refresh_records()
                pending = sum(item.get("review_status") == "pending" for item in self._snapshots)
                self.task_status_label.setText(
                    f"状态：当前批次 {result.batch_name or '全部'}，记录 {len(self._snapshots)} 件，待审核 {pending} 件。"
                )
                message = (
                    f"新增样本 {result.imported} 件；已有样本加入批次 {result.existing_added_to_batch} 件；"
                    f"完全重复 {result.duplicates} 件。"
                )
                if result.errors:
                    message += "\n导入错误：\n" + "\n".join(result.errors)
                QMessageBox.information(self, "真实样本导入完成", message)
            elif kind == "save":
                self.last_operation_timings_ms = dict(worker.result or {})
                updated = self._snapshot_by_id(worker.payload["sample_id"], worker.payload["snapshot_id"])
                if updated is not None:
                    self._update_saved_row(updated)
                self.task_status_label.setText("状态：人工记录已保存，CSV 已更新。")
            self._set_task_busy(False)

        def refresh_records(self) -> None:
            self._refresh_acceptance_batch_filter()
            self._snapshots = [item for item in self.store.list_snapshots() if self._matches_filters(item)]
            self.record_table.setUpdatesEnabled(False)
            self.record_table.blockSignals(True)
            try:
                self.record_table.setRowCount(len(self._snapshots))
                for row, snapshot in enumerate(self._snapshots):
                    self._fill_record_row(row, snapshot)
            finally:
                self.record_table.blockSignals(False)
                self.record_table.setUpdatesEnabled(True)
            self._current_snapshot = None
            self.details_text.clear()
            self.save_review_button.setEnabled(False)
            if not self.is_busy:
                current_batch = self.acceptance_batch_filter.currentText()
                pending = sum(item.get("review_status") == "pending" for item in self._snapshots)
                self.task_status_label.setText(f"状态：当前批次 {current_batch}，记录 {len(self._snapshots)} 件，待审核 {pending} 件。")

        def _fill_record_row(self, row: int, snapshot: dict[str, Any]) -> None:
            gear = snapshot.get("gear") or {}
            summary = snapshot.get("summary_view") or {}
            review = snapshot.get("human_review") or {}
            values = [
                snapshot.get("sample_id", ""), self._display(gear.get("itemSource", "")),
                "、".join(batch.get("batch_name") or batch.get("batch_id") or "" for batch in snapshot.get("acceptance_batches") or []),
                self._display(gear.get("rank", "")), f"+{gear.get('enhance', 0)}", self._display(gear.get("set", "")),
                self._display(gear.get("slot", "")), summary.get("recommendation_label", ""), review.get("decision", ""),
                snapshot.get("review_status", "pending"),
            ]
            for column, value in enumerate(values):
                item = self.record_table.item(row, column)
                if item is None:
                    self.record_table.setItem(row, column, QTableWidgetItem(str(value)))
                else:
                    item.setText(str(value))

        @staticmethod
        def _display(value: Any) -> str:
            text = str(value or "")
            return DISPLAY_VALUE_LABELS.get(text, text)

        def _gear_view(self, gear: dict[str, Any]) -> dict[str, Any]:
            main = dict(gear.get("mainStat") or {})
            main["type"] = self._display(main.get("type"))
            substats = []
            for item in gear.get("substats") or []:
                stat = dict(item)
                stat["type"] = self._display(stat.get("type"))
                substats.append(stat)
            return {
                "套装": self._display(gear.get("set")),
                "部位": self._display(gear.get("slot")),
                "主属性": main,
                "强化等级": gear.get("enhance"),
                "装备等级": gear.get("level"),
                "品质": self._display(gear.get("rank")),
                "副属性": substats,
                "装备实例编号": gear.get("instanceId"),
                "装备类型编号": gear.get("code"),
                "装备来源": self._display(gear.get("itemSource")),
            }

        def _refresh_acceptance_batch_filter(self, select_batch_id: str | None = None) -> None:
            previous = select_batch_id if select_batch_id is not None else str(self.acceptance_batch_filter.currentData() or "")
            batches = self.store.list_batches()
            self.acceptance_batch_filter.blockSignals(True)
            try:
                self.acceptance_batch_filter.clear()
                self.acceptance_batch_filter.addItem("全部验收批次", "")
                for batch_id, batch in batches.items():
                    self.acceptance_batch_filter.addItem(str(batch.get("batch_name") or batch_id), batch_id)
                set_combo_text(self.acceptance_batch_filter, previous)
            finally:
                self.acceptance_batch_filter.blockSignals(False)

        def _clear_non_batch_filters(self) -> None:
            self.enhance_filter.blockSignals(True)
            try:
                set_combo_text(self.enhance_filter, "all")
                for combo in (self.source_filter, self.rank_filter, self.slot_filter, self.set_filter, self.review_filter, self.inconsistent_filter):
                    combo.setCurrentIndex(0)
            finally:
                self.enhance_filter.blockSignals(False)

        def _matches_filters(self, snapshot: dict[str, Any]) -> bool:
            gear = snapshot.get("gear") or {}
            enhance = int(gear.get("enhance") or 0)
            mode = self.enhance_filter.currentData()
            if isinstance(mode, str) and mode.startswith("enhance:") and enhance != int(mode.split(":", 1)[1]):
                return False
            if mode == "unfinished" and enhance >= 15:
                return False
            for combo, key in (
                (self.source_filter, "itemSource"), (self.rank_filter, "rank"),
                (self.slot_filter, "slot"), (self.set_filter, "set"),
            ):
                selected = str(combo.currentData() or "")
                if selected and gear.get(key) != selected:
                    return False
            selected_status = str(self.review_filter.currentData() or "")
            if selected_status and snapshot.get("review_status") != selected_status:
                return False
            selected_batch = str(self.acceptance_batch_filter.currentData() or "")
            if selected_batch and selected_batch not in (snapshot.get("acceptance_batch_ids") or []):
                return False
            if bool(self.inconsistent_filter.currentData()):
                review = snapshot.get("human_review") or {}
                if review.get("consistency") not in ("不完全一致", "不一致"):
                    return False
            return True

        def _select_current_record(self) -> None:
            selected = self.record_table.selectionModel().selectedRows()
            if not selected:
                return
            self._current_snapshot = self._snapshots[selected[0].row()]
            snapshot = self._current_snapshot
            review = snapshot.get("human_review") or {}
            set_combo_text(self.human_decision_combo, str(review.get("decision") or ""))
            set_combo_text(self.consistency_combo, str(review.get("consistency") or ""))
            set_combo_text(self.reason_combo, str(review.get("reason") or ""))
            self.note_edit.setText(str(review.get("note") or ""))
            self.details_text.setPlainText(json.dumps({
                "装备字段": self._gear_view(snapshot.get("gear") or {}),
                "样本来源与验收批次": {
                    "原始数据来源": snapshot.get("original_source_files") or [],
                    "所属验收批次": [
                        {
                            "验收批次": batch.get("batch_name") or batch.get("batch_id"),
                            "批次用途": batch.get("purpose") or "",
                            "覆盖标签": batch.get("tags") or [],
                        }
                        for batch in snapshot.get("acceptance_batches") or []
                    ],
                },
                "工具建议": snapshot.get("summary_view"),
                "关键调试": snapshot.get("debug_view"),
            }, ensure_ascii=False, indent=2))
            self.save_review_button.setEnabled(True)

        def save_review(self) -> None:
            if self._current_snapshot is None:
                return
            decision = str(self.human_decision_combo.currentData() or "")
            consistency = str(self.consistency_combo.currentData() or "")
            if decision and not consistency:
                recommendation = (self._current_snapshot.get("summary_view") or {}).get("recommendation")
                consistency = "一致" if decision == recommendation else "不一致"
            self._start_task("save", {
                "sample_id": self._current_snapshot["sample_id"],
                "snapshot_id": self._current_snapshot["snapshot_id"],
                "decision": decision,
                "consistency": consistency,
                "reason": str(self.reason_combo.currentData() or ""),
                "note": self.note_edit.text().strip(),
            })

        def _snapshot_by_id(self, sample_id: str, snapshot_id: str) -> dict[str, Any] | None:
            return next((item for item in self.store.list_snapshots() if item["sample_id"] == sample_id and item["snapshot_id"] == snapshot_id), None)

        def _update_saved_row(self, updated: dict[str, Any]) -> None:
            row = next((index for index, item in enumerate(self._snapshots) if item["snapshot_id"] == updated["snapshot_id"]), None)
            if row is not None and self._matches_filters(updated):
                self._snapshots[row] = updated
                self._fill_record_row(row, updated)
                self.record_table.selectRow(row)
                return
            if row is not None:
                self._snapshots.pop(row)
                self.record_table.removeRow(row)
                if self._snapshots:
                    self.record_table.selectRow(min(row, len(self._snapshots) - 1))
                else:
                    self._current_snapshot = None
                    self.details_text.clear()

        def closeEvent(self, event: Any) -> None:
            if self.is_busy:
                QMessageBox.warning(self, "真实样本管理", "后台任务正在进行，请等待完成后再关闭窗口。")
                event.ignore()
                return
            event.accept()

    class AcceptanceReplayDialog(QDialog):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setWindowTitle("验收强化回放")
            self.setMinimumSize(720, 520)
            self.resize(820, 620)
            self.replay: AcceptanceReplay | None = None
            layout = QVBoxLayout(self)
            top = QHBoxLayout()
            self.sample_combo = QComboBox()
            self.paths = sorted((Path(__file__).resolve().parents[2] / "samples" / "manual_acceptance").glob("*.json"))
            for path in self.paths:
                if "replayPath" in path.read_text(encoding="utf-8"):
                    self.sample_combo.addItem(path.name, path)
            self.load_button = QPushButton("加载样本")
            self.next_button = QPushButton("下一次强化")
            self.next_checkpoint_button = QPushButton("强化至下一检查点")
            self.reset_button = QPushButton("重置")
            self.path_button = QPushButton("查看完整路径")
            for widget in (self.sample_combo, self.load_button, self.next_button, self.next_checkpoint_button, self.reset_button, self.path_button):
                top.addWidget(widget)
            layout.addLayout(top)
            self.status = QLabel("请选择带固定路径的验收样本。")
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            self.details = QTextEdit()
            self.details.setReadOnly(True)
            layout.addWidget(self.details, 1)
            self.load_button.clicked.connect(self.load_sample)
            self.next_button.clicked.connect(self.next_step)
            self.next_checkpoint_button.clicked.connect(self.next_step)
            self.reset_button.clicked.connect(self.reset)
            self.path_button.clicked.connect(self.show_path)
            self.load_sample()

        def load_sample(self) -> None:
            path = self.sample_combo.currentData()
            if not isinstance(path, Path):
                return
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.replay = AcceptanceReplay(Gear.from_dict(data), str(data.get("itemSource") or "normal_85"), list(data.get("replayPath") or []))
                self.render(self.replay.snapshot(None))
            except Exception as exc:
                self.error(exc)

        def next_step(self) -> None:
            if self.replay is None:
                return
            try:
                self.render(self.replay.next())
            except Exception as exc:
                self.error(exc)

        def reset(self) -> None:
            if self.replay is not None:
                self.render(self.replay.reset())

        def show_path(self) -> None:
            if self.replay is not None:
                self.details.setPlainText(json.dumps(self.replay.path, ensure_ascii=False, indent=2))

        def render(self, snapshot: dict[str, Any]) -> None:
            gear = snapshot["gear"]
            result = snapshot["suggestion"]
            debug = (result.get("debug") or {}).get("dp_assist") or {}
            event = snapshot.get("event") or {}
            self.status.setText(f"当前 +{gear.enhance}；剩余 {snapshot['remaining']} 步；命中：{event.get('type', '未强化')} +{event.get('value', '')}")
            self.details.setPlainText(json.dumps({"强化前副属性": snapshot.get("before_substats") or gear.to_dict()["substats"], "强化后副属性": gear.to_dict()["substats"], "建议": result.get("summary"), "决策模式": debug.get("decision_mode"), "调试依据": debug.get("lightweight_basis") or {"效用": debug.get("dp_expected_utility")}}, ensure_ascii=False, indent=2))

        def error(self, exc: Exception) -> None:
            QMessageBox.warning(self, "回放失败", chinese_error(str(exc)))


def add_combo_options(combo: Any, options: list[tuple[str, str]]) -> None:
    for value, label in options:
        combo.addItem(label, value)


def combo_value(combo: Any) -> str:
    return str(combo.currentData() or combo.currentText())


def set_combo_text(combo: Any, value: str) -> None:
    index = combo.findData(value)
    if index < 0:
        combo.addItem(value, value)
        index = combo.findData(value)
    combo.setCurrentIndex(index)


def text_number(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number.is_integer():
        return str(int(number))
    return str(number)


def format_debug(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def chinese_error(message: str) -> str:
    replacements = {
        "rift_85 only supports Epic": "异界 85 仅支持红装（Epic）。",
        "Invalid substats": "副属性不符合该部位规则，请检查主副属性重复和部位禁用项。",
        "Duplicate substats": "副属性不能重复。",
        "Invalid main stat": "主属性不符合该部位规则。",
        "Unknown gear slot": "装备部位无效。",
        "Unsupported equipment level": "仅支持 85 级或重铸后的 90 级装备。",
        "Unsupported enhancement checkpoint": "强化等级必须为 +0、+3、+6、+9、+12 或 +15。",
        "Unknown substats": "存在无法识别的副属性，请从副属性列表中选择。",
        "Gear may have at most four substats": "副属性最多只能有四条。",
        "must have": "当前品质与强化节点的副属性条数不正确，请检查补词条节点。",
    }
    for source, target in replacements.items():
        if source in message:
            return target
    return message


def collection_import_message(report: dict[str, Any]) -> str:
    skipped = int(report.get("skipped_items") or 0)
    reasons = report.get("skipped_by_reason") or {}
    reason_text = "；".join(f"{reason} {count} 件" for reason, count in reasons.items())
    message = (
        f"已加载 {int(report.get('loaded_items') or 0)} 件85级 +0/+3 红装或紫装，"
        f"已跳过 {skipped} 件。"
    )
    if reason_text:
        message += f"\n跳过明细：{reason_text}。"
    return message


def run_gui(argv: list[str] | None = None) -> int:
    if QApplication is None:
        raise SystemExit("PySide6 is not installed. Install PySide6 to launch the desktop GUI.")
    app = QApplication.instance() or QApplication(argv or sys.argv)
    window = GearEnhanceWindow()
    window.show()
    return app.exec()
