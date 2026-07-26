# 纯视觉 OCR 依赖审计与真实局部识别只读复验任务说明

## 目标

审计本地纯视觉 OCR 运行条件，并在依赖完整且页面/设备前置条件满足时执行一次真实只读 ADB 局部识别复验。结果只能作为 `mode=visual_only`、`verification=unverified` 的视觉证据，不能表述为服务器确认、装备底层数据或强化成功。

## 唯一权威来源

本文件是本阶段唯一权威任务来源。代码和字段口径继承《纯视觉 ADB 局部模板与 PaddleOCR 只读识别任务说明.md》、`src/e7_enhance/visual_adb_recognition.py`、`src/e7_enhance/ocr_paddle.py` 及现有 `0.98` 字段置信度门槛。

## 范围

1. 只读检查 `PIL`、`paddleocr`、`paddle` 的模块可见性、版本和导入副作用；核对 requirements 声明与当前解释器是否一致。
2. 不安装依赖、不联网、不修改环境变量以外的系统状态，不下载模型，不启动 OCR 服务。
3. 仅当依赖审计通过时，执行一次 MuMu 官方 ADB 自动发现和一次 `exec-out screencap -p`；截图只在内存中完成 PNG 校验、局部裁剪、模板/OCR 识别，不保存、不上传。
4. 复用现有 ADB 帧源、稳定帧、区域清单、模板/Paddle 适配器和 `0.98` 门槛；任一前置或识别条件失败立即停止，不重试。

## 明确禁止

- 禁止安装包、联网下载、上传数据、调用 Fribbels/PCAP/TCP/`player_data.json` 或底层读取器。
- 禁止 ADB `input tap`、`swipe`、`keyevent`，禁止页面导航、点击、强化、选材、重启游戏和资源消耗。
- 禁止截图落盘、私人归档读写、外部传输或修改正式策略、DP、评分、资源模型、GUI、OCR 门槛、Holdout 和自动化规则。
- 不得把缺少依赖、页面不匹配、低置信度或字段矛盾转化为猜测结果；统一 fail-closed。

## 执行步骤

1. 完整阅读本文件、`AGENTS.md`、`e7-gear-enhance-plan.md` 及前置纯视觉任务说明。
2. 在当前 Python 解释器中只读审计三个 OCR 依赖，记录导入结果、版本和失败原因；不触发安装或模型下载。
3. 依赖不齐全时停止，不执行真实截图；依赖齐全时先运行 `adb.exe devices -l`，只接受唯一 `device`，再执行一次 `exec-out screencap -p` 并以内存证据运行局部识别。
4. 运行相关公开测试、语法检查和 `git diff --check`；精确审阅 diff，只提交本任务文档与必要报告/代码。

## 验证要求

- 报告必须区分依赖审计、fake/offline、真实只读预检和未完成项。
- 真实预检不得保存截图、上传数据或发送任何输入；设备、PNG、视口、稳定帧、区域、模板锚点和字段置信度任一失败即停止。
- 真实 OCR 字段必须全部满足既有 `0.98` 门槛，结果继续标记 `mode=visual_only`、`verification=unverified`。
- 执行模型记录为 `gpt-5.6-terra + high`；如实际不可用必须如实记录替代模型。

## 停止条件

- 依赖缺失、导入异常、模型不可用、设备不唯一、页面不匹配或任何低置信度/字段矛盾时停止，不重试。
- 任何需要安装、联网、点击、导航或资源操作的步骤超出本任务，必须另行授权。

## 当前状态

`dependency_audit_failed_import_fail_closed_20260726`

## 审计结果

- 当前默认 Python `3.13.13`：`PIL`、`paddleocr`、`paddle` 均不可见。
- 项目配置 Python `3.9.2`（`C:\Users\orangine\AppData\Local\Programs\Python\Python39\python.exe`）：`PIL 11.3.0` 可导入；`paddleocr` 可发现但导入因访问 `C:\Users\orangine\.cache\paddle` 返回 `PermissionError: [WinError 5]`；`paddle` 可发现但导入因 `AttributeError: partially initialized module 'paddle' has no attribute 'tensor'` 失败。
- 本次审计未安装依赖、未联网、未下载模型、未修改游戏环境，未执行 ADB、截图、OCR、点击或页面导航。

## 未完成项与下一步

- 依赖导入闸门未通过，真实局部识别复验未开始；不能把当前结果写成页面、目标装备或字段识别成功。
- 下一步需另建“纯视觉 OCR 运行环境修复与依赖复验”任务，明确授权后再处理 Python 3.9 的 Paddle 缓存权限和 Paddle 初始化问题；本任务不自行修复、不安装、不联网。
