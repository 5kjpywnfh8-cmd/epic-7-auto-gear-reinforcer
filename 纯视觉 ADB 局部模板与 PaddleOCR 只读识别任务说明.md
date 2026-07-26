# 纯视觉 ADB 局部模板与 PaddleOCR 只读识别任务说明

## 目标

在已完成的只读 ADB PNG 帧源和离线视觉运行时之上，接入装备详情页的局部区域裁剪、模板锚点识别和 PaddleOCR 行解析适配。结果只生成带来源、帧哈希、视口、时间戳和字段置信度的 `VisualEvidence`，保持 `mode=visual_only`、`verification=unverified`，不得把视觉结果表述为服务器确认。

## 唯一权威来源

本文件是本阶段唯一权威任务来源。ADB 设备发现、PNG 校验和禁止操作继承《纯视觉 ADB 截图与受控点击迁移任务说明.md》；证据状态机继承《纯视觉运行时接线实现任务说明.md》；区域和 OCR 规范继承 `src/e7_enhance/ocr_regions.py`、`ocr_paddle.py`、`ocr_normalize.py` 及 `0.98` 字段置信度门槛。

## 范围

1. 新增或扩展一个纯 Python、依赖注入的 ADB 视觉识别适配层：接收 `VisualFrame` 的 PNG 字节，在内存中解析视口并裁剪 `equipment_regions()` 的规范化区域。
2. 接入局部模板识别器和 PaddleOCR 行源协议，复用 `parse_backpack_enhance_lines()` 与既有字段规范化，不降低、绕过或重定义 `MIN_FIELD_CONFIDENCE = 0.98`。
3. 将模板锚点、局部 OCR 字段、目标指纹、稳定帧 provenance 和资源预览绑定到现有 `VisualEvidence`，所有异常统一 fail-closed 且不自动重试。
4. 补充 fake PNG、区域越界、PNG 解码失败、锚点缺失、低置信度、字段矛盾和完整 `AdbScreencapBackend -> StableFrameCollector -> VisualAdapterSampler -> VisualEvidence` 离线公开测试。
5. 在离线实现和定向测试通过后，可进行一次只读 ADB 截图/局部识别预检；预检只在内存处理，不落盘、不上传、不导航、不发送输入。若依赖、设备、页面锚点或字段门槛不满足，立即停止，不重试。

## 明确禁止

- 禁止 `adb input tap`、`swipe`、`keyevent`，禁止页面导航、点击、强化、选材、重启游戏和资源消耗。
- 禁止 Fribbels、PCAP、TCP 载荷、`player_data.json`、底层装备读取器和任何外部上传。
- 禁止修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout、自动化规则、MuMu 底层读取器和 ADB 设备发现策略。
- 禁止把私人截图写入磁盘、测试夹具或归档；禁止读取、恢复、暂存或上传私人归档；不得触碰 `refs/heads/main - 副本`。
- 禁止引入隐式重试、全屏盲识别、硬编码点击坐标或把视觉字段当作服务端确认。

## 输入与执行步骤

1. 完整阅读本文件、`AGENTS.md`、`e7-gear-enhance-plan.md` 及前置 ADB/运行时任务说明，并只读审阅相关实现和公开测试。
2. 先冻结兼容接口，再实现内存 PNG 区域提取、模板识别和 Paddle 行源适配；不得改变已有帧源和状态机语义。
3. 增加 fake/offline 回归，覆盖成功链路及所有 fail-closed 条件；运行定向测试、语法检查和 `git diff --check`。
4. 精确审阅 diff，只暂存本任务文件和本任务代码/测试文件，提交并推送当前分支；不得使用 `git add -A`。
5. 仅在前置条件全部通过后执行一次定向真实只读预检：先自动发现唯一 `device`，再以内存 PNG 做局部裁剪和识别；不保存截图、不上传、不点击。

## 产物

- ADB PNG 内存局部裁剪与识别适配器。
- 模板/PaddleOCR 注入协议和 `VisualEvidence` 绑定结果。
- 离线公开测试、定向验证记录和本文件/总计划状态记录。

## 验证要求

- 既有 ADB、视觉适配器、运行时、点击器、采样器和 OCR 公开测试不回归。
- 区域必须在当前帧视口内且稳定；PNG 无法解码、帧来源/视口漂移、模板少于两个、锚点分数或亮度不达标、任一字段低于 `0.98`、字段不完整或矛盾均停止。
- 离线验证必须报告真实退出码；真实预检必须与 fake/offline 结果分开报告，不得写成服务器或强化成功。
- 执行模型记录为用户指定的 `gpt-5.6-terra + high`；若实际不可用必须如实记录替代模型。

## 停止条件

- 文档未完整创建/阅读、接口不兼容或测试未通过时，停止，不连接设备。
- 任一真实只读前置条件失败时，停止且不重试，不执行任何输入或游戏操作。
- 受控点击仍不属于本任务；必须另建任务说明并取得单独明确授权。

## 当前状态

`implementation_verified_offline_real_readonly_ocr_blocked_dependencies_20260726`

## 完成项与验证记录

- 新增 `src/e7_enhance/visual_adb_recognition.py`：在内存中解码受信任的 ADB PNG、按规范化装备区域裁剪并重新编码局部 PNG；接入局部模板识别器、PaddleOCR 行源和既有 `parse_backpack_enhance_lines()`。
- 识别适配器只接受 `adb_screencap:` 稳定帧，绑定来源、视口、帧哈希、时间戳、模板锚点、字段置信度和视觉指纹；输出继续由 `VisualEvidence` 固定为 `mode=visual_only`、`verification=unverified`。
- PNG 结构/CRC/像素流校验复用 ADB 帧源口径；局部解码拒绝视口不一致、区域越界、非法过滤器、损坏像素流和超过 `40,000,000` 像素的输入。OCR 重试标记、低于 `0.98` 的字段和标量字段矛盾均 fail-closed。
- 新增 `tests/test_visual_adb_recognition.py`，覆盖内存裁剪、坏 PNG/视口/越界/超大输入、唯一设备稳定帧到模板/Paddle 行解析的完整证据链、缺失模板、低置信度、字段冲突和禁止重试。
- 定向测试 `tests.test_visual_adb`、`tests.test_visual_adb_recognition`、`tests.test_visual_platform`、`tests.test_visual_runtime`、`tests.test_visual_adapter`、`tests.test_visual_click`、`tests.test_visual_sampling`、`tests.test_ocr_paddle`、`tests.test_ocr_stage1_readonly`、`tests.test_ocr_backpack_pair`：`70/70`，退出码 `0`。
- Python 3 语法检查通过；目标文件 `git diff --check` 通过。执行模型记录为 `gpt-5.6-terra + high`。

## 真实只读预检结果

- 按任务说明先自动发现 MuMu 官方 ADB 唯一设备 `emulator-5554`（状态 `device`），随后只执行一次 `exec-out screencap -p`。
- 截图仅在内存中校验和裁剪：视口 `1280x720`，PNG `878846` 字节，帧哈希 `3b2c7ebd307f59bcb9194f48601e45a002db932f726bccfbbf1f8c3e00187f9e`，内容校验通过；装备局部探针裁剪视口 `1152x533`、`723030` 字节。
- 未保存截图、未上传、未执行 OCR、未导航、未发送 ADB 输入、未点击、未强化、未选材、未重启、未消耗资源、未读取底层数据。

## 未完成项与风险

- 当前开发环境缺少 `PIL`、`paddleocr` 和 `paddle`，真实局部 PaddleOCR/模板识别按 fail-closed 停止；本轮不能声称真实页面、目标装备或字段识别成功。
- 模板识别器和 PaddleOCR 行源仍是依赖注入协议；安装并审计本地只读依赖后，需另建或明确授权一次真实只读识别复验，仍不得点击。
- 受控 ADB 点击、页面导航、强化、选材和资源操作不属于本任务，必须另建任务说明并取得单独明确授权。

## 下一步

先解决并审计本地只读 OCR 依赖（不得在本任务隐式联网或修改游戏环境），再创建“真实 ADB 局部识别只读复验”任务说明；在 OCR 真实证据通过前保持自动化停止，不进入受控点击。
