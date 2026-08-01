# 第五次真实列表页视觉字段只读校准前置失败报告

日期：2026-08-01
实际模型：`gpt-5.6-terra + high`（用户偏好的 `gpt-5.6-luna + max` 当前协作接口不可用）

## 结论

本次用户批准的一次性真实只读校准在 ADB 前置接口审阅阶段 fail-closed：列表页没有可执行的生产 OCR/模板读取器接线，无法从真实 PNG 生成视觉字段签名。因此没有设备接触，也没有形成当前 MuMu 页面证据。

## 核对证据

- `equipment_list_region_registry()` 提供固定 `1280x720` 区域注册。
- `RegisteredListPageLocalRecognizer` 和 `InMemoryPngListPageObservationSource` 只消费调用方注入的读取器。
- `ListPagePngOcrReader`、`ListPagePngTemplateReader` 仅为协议；实际实例只出现在测试假实现中，未发现生产运行时创建、真实 OCR 引擎适配或模板目录加载调用者。
- 视觉字段稳定性新契约仍保持：三帧来源/视口/时间、页面锚点、滚动边界、候选身份/指纹/槽位及字段值签名逐帧一致，字段置信度 `>=0.98`；PNG 哈希仅作审计元数据。

## 执行边界

未运行 `C:\Program Files\Netease\MuMu Player 12\shell\adb.exe devices -l`，未执行 `screencap`、真实 OCR/模板识别、截图落盘、重试、输入、点击、滑动、按键、导航、强化、选材、确认、资源消耗、联网、上传或模型下载。

## 状态与下一步

状态：`real_list_readonly_calibration_fail_closed_missing_production_list_reader_20260801`。

先建立独立离线任务完成生产列表 OCR/模板读取器接线与回归，再重新建任务说明并取得新的、一次性的真实三帧只读授权；本次授权不可复用。真实校准通过后仍需另建任务并重新授权点击/导航。
