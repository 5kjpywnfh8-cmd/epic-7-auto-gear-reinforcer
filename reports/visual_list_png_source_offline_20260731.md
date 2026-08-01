# 纯视觉装备列表页内存局部 OCR 观察源离线验证报告

日期：2026-07-31

## 范围

本报告只记录固定 `1280x720` 合成 PNG 的内存裁切、显式 OCR/模板读取器适配和列表解析器回归。结果标记为 `mode=visual_only`、`verification=unverified`，不代表当前 MuMu 页面证据。

## 结果

- `InMemoryPngListPageLocalObservationSource`：3/3 通过，覆盖固定区域裁切、读取器异常、未知视口和非 mapping 结果。
- `InMemoryPngListPageObservationSource`：4/4 通过，覆盖唯一目标端到端解析、无效 PNG/未知区域、低置信度、字段冲突和模板分数低于 `0.98`。
- 列表相关视觉测试：25/25 通过。
- 全部 `test_visual*.py`：105/105 通过。
- Python 3.9 `py_compile`：全部视觉模块和视觉测试退出码 `0`。
- `git diff --check`：退出码 `0`；仅有既有总计划 LF/CRLF 转换提示。

## 约束核对

- 适配器只接收 `VisualFrame` 内存 PNG 和版本化固定区域注册；不捕获帧、不搜索区域、不产生点击点或输入动作。
- OCR/模板读取结果在进入 `RegisteredListPageLocalRecognizer` 前经过固定字段、锚点、边界、指纹、唯一性和 `>=0.98` 检查；失败即 fail-closed。
- 本轮未执行 ADB、设备发现、真实截图、真实 OCR 推理、窗口输入、页面导航、点击、强化、选材、确认、资源消耗、底层读取、联网、上传或模型下载。

## 未完成项

合成 fixture 不能证明真实列表页布局、OCR 结果、模板分数或目标唯一性。后续必须新建真实列表页三帧只读校准任务并重新取得明确只读授权；列表选中、进入强化界面和后续点击仍需独立任务及新鲜后验。
