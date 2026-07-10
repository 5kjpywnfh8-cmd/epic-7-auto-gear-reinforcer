# PySide6 桌面主程序 v1 计划

## 范围

- 使用 PySide6 做桌面主程序。
- 复用现有 `enhance_policy.advise_gear`，不迁移评分、DP、模拟算法。
- 第一版只做 JSON/手动录入/建议展示/保存。
- OCR、截图识别、Airtest 自动点击只预留入口，不进入主流程。

## 主入口

- `python gui.py`
- `python main.py gui`

GUI 依赖放在 `requirements-gui.txt`。

## 模块划分

- `src/e7_enhance/gui_app.py`
  - PySide6 主窗体。
  - 装备字段编辑。
  - 导入/保存 JSON。
  - 调用建议并展示前台和 debug。
  - 截图/OCR、Airtest 按钮禁用。
- `src/e7_enhance/gui_support.py`
  - 纯 Python 表单数据转换。
  - 调用 `advise_gear`。
  - 前台 summary 和 debug view model。
  - 保存装备和建议结果。
- `src/e7_enhance/airtest_adapter.py`
  - Airtest adapter 协议。
  - `NullAirtestAdapter` 第一版禁用，不导入 Airtest，不点击。

## v1 验收

- 示例 `samples/gear.json` 可导入并生成建议。
- UI 表单可手动编辑套装、部位、主属性、强化等级、等级、品质、副属性。
- 前台只展示建议、下一检查点、目标体系、关键理由。
- debug 折叠面板展示 strategy、DP、百里分和目标分字段。
- 可保存当前装备 JSON 和建议结果 JSON。
- 不接 OCR/ADB/Airtest 点击。
- 单元测试和 GUI smoke 通过。
