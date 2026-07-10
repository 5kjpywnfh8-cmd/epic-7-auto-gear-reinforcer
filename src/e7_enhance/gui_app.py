from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from .airtest_adapter import NullAirtestAdapter
from .gui_support import (
    DEFAULT_GEAR_FORM,
    build_gear_dict,
    format_debug_details,
    load_gear_file,
    load_gear_collection,
    save_gear_file,
    save_suggestion_file,
    suggest_from_form,
    summary_view_model,
)
from .acceptance_replay import AcceptanceReplay
from .models import Gear

try:
    from PySide6.QtCore import Qt
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
            self.sample_forms: list[dict[str, Any]] = []
            self.sample_index = 0
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

        def load_forms_from_path(self, path: Path) -> None:
            try:
                forms = load_gear_collection(path)
            except json.JSONDecodeError:
                # Saved single-result packages retain the existing tolerant loader path.
                forms = [load_gear_file(path)]
            self.sample_forms = forms
            self.sample_index = 0
            self.set_form(forms[0])
            self.run_suggest()
            self.update_sample_controls()

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
                "rollHistory": [],
                "item_source": combo_value(self.item_source_combo),
                "reforge_eligible": self.level_spin.value() == 85,
            }

        def import_gear(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "导入装备 JSON", "", "JSON Files (*.json);;All Files (*)")
            if not path:
                return
            try:
                self.load_forms_from_path(Path(path))
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
                self.render_result(self.current_result, gear_data)
            except Exception as exc:
                QMessageBox.warning(self, "判断失败", chinese_error(str(exc)))

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


def run_gui(argv: list[str] | None = None) -> int:
    if QApplication is None:
        raise SystemExit("PySide6 is not installed. Install PySide6 to launch the desktop GUI.")
    app = QApplication.instance() or QApplication(argv or sys.argv)
    window = GearEnhanceWindow()
    window.show()
    return app.exec()
