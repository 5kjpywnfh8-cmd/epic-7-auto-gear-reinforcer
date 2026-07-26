# 纯视觉真实 ADB 只读探针校正与局部识别复验任务说明

## 目标

修复上一个真实只读 ADB 复验中探针内容校验回调的 wiring 错误，并在新的单次授权窗口内验证 ADB PNG、局部裁剪和可用的本地 PaddleOCR/模板识别。结果只能标记 `mode=visual_only`、`verification=unverified`，不得表述为服务器确认、底层装备状态或强化成功。

## 唯一权威来源

本文件是本轮唯一权威任务来源。ADB 帧源继承《纯视觉 ADB 截图与受控点击迁移任务说明.md》；局部识别协议继承《纯视觉 ADB 局部模板与 PaddleOCR 只读识别任务说明.md》；前次停止记录见《纯视觉真实 ADB 局部识别只读复验任务说明.md》；字段和 `0.98` 门槛以现有视觉/OCR模块为准。

## 范围

1. 只修正一次性只读探针的内存内容校验回调：回调必须在定义后再传给 `AdbScreencapBackend`，使用 `PIL.Image.open(io.BytesIO(payload)).convert("RGB")` 检查像素极值，拒绝无法解码或全黑内容；不得修改正式运行时代码、ADB 帧源或 OCR 门槛。
2. 在批准的 ASCII 工作区缓存中以全新 Python 3.9.2 进程导入 `paddle` 与 `paddleocr`；只检查本地模型是否已经存在，不安装依赖、不联网、不下载模型。
3. 运行官方 MuMu `adb.exe devices -l`，只接受自动发现且状态为 `device` 的唯一设备。
4. 只执行一次由自动发现设备派生的 `exec-out screencap -p`；PNG 只在内存中验证结构、CRC、视口、非黑屏、哈希和装备区域裁剪，不保存截图。
5. 仅当本地 OCR 模型已存在且不触发下载时，才在同一内存 PNG 上执行一次局部模板/PaddleOCR 识别；否则在模型闸门处停止并记录原因。

## 明确禁止

- 禁止 ADB `input tap`、`swipe`、`keyevent`，禁止页面导航、点击、强化、选材、重启游戏和资源消耗。
- 禁止 Fribbels、PCAP、TCP、`player_data.json`、底层装备读取器、外部上传和截图落盘。
- 禁止自动重试、第二次截图、全屏盲识别、硬编码点击坐标、降低稳定帧/视口/区域/`0.98` 门槛或把视觉结果写成服务器确认。
- 不修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout、自动化规则或既有 ADB 生产代码。
- 不读取、恢复、暂存或上传私人归档；不得触碰或删除 `refs/heads/main - 副本`；不得使用 `git add -A`。

## 输入与执行步骤

1. 完整阅读本文件、`AGENTS.md`、`e7-gear-enhance-plan.md` 和前置纯视觉任务说明。
2. 在新 Python 进程中运行 ASCII 缓存导入闸门，输出版本和退出码；导入失败立即停止，不执行 ADB。
3. 只读检查批准缓存目录下是否存在可用 OCR 模型文件；模型不存在时停止，不构造会联网下载的引擎。
4. 运行一次官方 `adb.exe devices -l`；设备不是唯一 `device` 时停止且不重试。
5. 定义完整的 `_nonblack(payload, viewport)` 回调后，构造 `AdbScreencapBackend` 并执行一次 `PlatformFrameSource.capture()`；禁止再次调用 ADB 截图。
6. 对内存 PNG 运行现有区域清单和 `InMemoryPngRegionExtractor`；区域越界、PNG 解码、视口或内容校验失败立即停止。
7. 模型可用时执行一次局部模板/PaddleOCR，维持所有字段 `>=0.98`，绑定 `VisualEvidence`；任一锚点、字段、置信度或矛盾条件失败立即停止。
8. 运行离线定向测试、语法检查和 `git diff --check`；精确审阅差异，只提交本任务文档和总计划。

## 产物

- 一次新的真实只读探针复验元数据（设备、视口、PNG 字节数/哈希、区域尺寸、停止原因；不包含截图）。
- 若模型闸门通过，则附局部模板/OCR `VisualEvidence` 元数据；否则明确记录模型阻断。
- 本文件和 `e7-gear-enhance-plan.md` 的状态、验证结果、未完成项、风险和下一步。

## 验证要求

- 真实 ADB 截图调用最多一次；fake/offline 测试与真实结果分开报告。
- 任何失败必须 fail-closed，保留异常类型和退出码；不得以猜测代替 OCR 证据。
- 结果必须保持 `mode=visual_only`、`verification=unverified`。
- 执行模型记录为 `gpt-5.6-terra + high`；若不可用如实记录替代模型。

## 停止条件

- 文档未完整阅读、依赖导入失败、模型不可用、设备不唯一、截图/PNG/视口/非黑屏/区域失败、低置信度、字段矛盾或任何需要联网/下载/输入的步骤发生时停止，不重试。
- 探针回调自身异常也必须停止，不得再次调用 ADB；需另建任务后才可修复并重新授权。

## 当前状态

`probe_validator_corrected_model_cache_missing_fail_closed_20260726`

## 模型记录

本轮按用户要求使用 `gpt-5.6-terra + high`；不下载模型、不联网。

## 本轮执行记录

- 依赖闸门通过：全新 Python 3.9.2 进程在批准的 ASCII 工作区缓存中导入 `paddle 2.6.2` 和 `paddleocr 2.10.0`，退出码 `0`。
- 模型检查结果：批准缓存目录递归文件数为 `0`，候选 `.pdmodel`/`.pdiparams`/模型目录文件数为 `0`；未构造 OCR 引擎，未联网，未下载模型。
- 按本任务“模型不存在即停止”条件，本轮没有调用 `adb devices -l`，没有调用 `exec-out screencap -p`，没有截图、局部裁剪、模板识别、OCR、证据生成或任何游戏操作。
- 前次 `_nonblack` 未定义问题已通过本轮探针定义方案完成离线校正，但由于模型闸门未通过，未进行真实截图验证；不存在新的 ADB 重试。

## 未完成项与风险

- 未获得新的真实 ADB 帧或局部视觉证据，不能声称页面、目标装备或字段识别成功。
- 下一步必须另行创建/更新任务说明并取得明确授权，允许提供已存在的本地 PaddleOCR 模型或受控下载模型；未获授权前不得联网、下载或调用 ADB。
