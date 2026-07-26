# 纯视觉真实 ADB 模型就绪局部 OCR 只读复验任务说明

## 目标

使用已准备好的本地 PaddleOCR 模型，对当前 MuMu 窗口执行一次真实、只读、内存内的 ADB PNG 局部识别，确认依赖、设备发现、PNG 校验、装备详情区域裁剪和 PaddleOCR 行解析能够运行。结果只能标记 `mode=visual_only`、`verification=unverified`，不得表述为服务器确认、底层装备状态或强化结果。

## 唯一权威来源

本文件是本轮唯一权威任务来源。ADB 帧源继承《纯视觉 ADB 截图与受控点击迁移任务说明.md》；局部区域、模板和字段门槛继承《纯视觉 ADB 局部模板与 PaddleOCR 只读识别任务说明.md》；模型缓存继承《纯视觉 PaddleOCR 模型受控下载与本地引擎复验任务说明.md》。

## 授权范围

用户已批准进入下一步。本轮仅覆盖：

- 自动发现唯一 MuMu `device`；
- 只执行一次 `exec-out screencap -p`；
- 在内存中校验 PNG、视口、非黑屏、帧哈希和装备详情局部区域；
- 在同一内存局部 PNG 上调用已缓存的 PaddleOCR，并复用现有行解析和 `0.98` 字段门槛。

## 明确禁止

- 禁止 ADB `input tap`、`swipe`、`keyevent`，禁止页面导航、点击、强化、选材、重启和资源消耗；
- 禁止 Fribbels、PCAP、TCP、`player_data.json`、底层读取器、外部上传和截图落盘；
- 禁止自动重试、第二次截图、全屏盲识别、降低 `0.98` 门槛或把单帧结果写成稳定帧/服务器确认；
- 禁止修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout、自动化规则和既有 ADB/Windows 生产代码；
- 禁止触碰 `refs/heads/main - 副本`、私人归档和 `git add -A`。

## 执行步骤

1. 在全新 Python 3.9.2 进程中配置批准 ASCII 缓存，导入 `paddle`、`paddleocr` 并确认本地模型文件齐全；导入失败立即停止。
2. 运行官方 MuMu `adb.exe devices -l`，只接受自动发现且状态为 `device` 的唯一设备；否则停止且不重试。
3. 定义完整 `_nonblack(payload, viewport)` 回调后，执行一次 `PlatformFrameSource(AdbScreencapBackend).capture()`；PNG 只在内存中校验，不保存。
4. 使用 `InMemoryPngRegionExtractor` 解析 `equipment_regions()`，检查区域边界并生成内存局部 PNG；区域失败立即停止。
5. 在局部 PNG 上调用一次 PaddleOCR，转换为现有 `parse_backpack_enhance_lines()` 的行格式；缺失字段、矛盾、低于 `0.98` 或页面不匹配均 fail-closed。
6. 仅报告真实单帧局部 OCR 元数据。由于本轮禁止第二次截图，不得把单帧结果包装为 `StableFrames` 或完整 `VisualEvidence` 稳定证据；稳定帧/证据闭环另行授权。
7. 运行相关离线测试、语法检查和 `git diff --check`，精确审阅差异，仅提交本任务说明和总计划。

## 产物

- 依赖和模型闸门结果；
- 唯一设备、一次 PNG 的视口/字节数/哈希、局部区域尺寸；
- PaddleOCR 行数、字段解析结果或 fail-closed 原因（不含截图内容）；
- 本文件与 `e7-gear-enhance-plan.md` 的完成项、验证结果、未完成项、风险和下一步。

## 停止条件

依赖、模型、设备、PNG、视口、非黑屏、区域、OCR、字段或置信度任一环节失败立即停止，不重试；任何需要第二次截图、稳定帧、点击或游戏操作的步骤另行授权。

## 验证要求

- fake/offline 测试与真实单帧结果分开报告；
- 执行模型记录为 `gpt-5.6-terra + high`；
- 结果继续保持 `mode=visual_only`、`verification=unverified`。

## 当前状态

`real_adb_single_frame_local_ocr_completed_fail_closed_20260726`

## 执行记录

- 执行模型：`gpt-5.6-terra + high`；Python `3.9.2`；`paddle 2.6.2`；`paddleocr 2.10.0`。
- 本地模型闸门通过：缓存中检测、识别和分类模型文件齐全；PaddleOCR 构造和一次局部 `ocr()` 调用均使用本地模型，未触发下载。
- 官方 MuMu ADB 自动发现唯一设备 `emulator-5554`（状态 `device`）；未使用固定 IP/端口。
- 只执行一次 `exec-out screencap -p`，PNG 仅在内存中校验：帧源 `adb_screencap:emulator-5554`，视口 `1280x720`，PNG `858918` 字节，帧 SHA-256 `5df31a9f02817c90c7e7e636489c338415411c5f65650906fc2c8e29e5b1fef2`。
- 装备详情规范局部裁剪在内存中通过：视口 `1152x533`，`701013` 字节；未落盘截图。
- PaddleOCR 返回 `92` 行。解析得到部分可识别字段（英雄武器、85、攻击力 100、暴击率 5%、攻击力 8%），但结果被 fail-closed 拒绝，原因：`unrecognized:set`、`missing:enhance`、`low_confidence:substats[2]`（该字段置信度 `0.927478`）。
- 未调用第二次 ADB 截图，未执行模板点击、页面导航、ADB 输入、强化、选材、重启、资源消耗、底层读取、外部上传或稳定帧/`VisualEvidence` 包装。

## 结论、风险与下一步

- 本轮证明真实 ADB 单帧、内存局部裁剪和本地 PaddleOCR 可运行；不证明当前页面是目标装备详情页，也不证明字段或服务器状态。
- 当前屏幕疑似包含背包列表/多个装备文本，且目标详情所需套装与强化字段未形成完整高置信度证据；按门槛不能继续任何自动化操作。
- 下一步需用户将游戏停留在目标装备详情页后，另行创建并授权一次新的单帧识别；若要证明稳定帧和完整 `VisualEvidence`，还需单独授权多帧采样任务。当前任务不重试。
