# 纯视觉装备列表页生产 OCR 模板读取器接线离线开发任务说明

## 目标

为固定 `1280x720` 装备列表页补齐生产运行时的 OCR/模板读取器装配入口，使内存 `VisualFrame` 能经由固定区域、显式注入的本地读取引擎进入 `RegisteredListPageLocalRecognizer`。本任务只完成离线接线与回归，不证明当前 MuMu 页面已匹配。

## 范围

- 新增生产装配函数或对象，显式接收 OCR 与模板读取器工厂，并连接固定区域注册、内存 PNG 观察源和列表页识别器。
- 固定 `1280x720`、注册区域、`>=0.98` 置信度、字段白名单、唯一目标和 `mode=visual_only`/`verification=unverified` 契约。
- 为正常路径、缺失读取器、读取异常、低置信度和非法区域补充离线回归。
- 允许使用合成/公开 PNG fixture；不得把 fixture、历史截图或人工字段写成真实页面证据。

## 禁止修改项

- 禁止 ADB、真实截图、OCR 模型推理、模型下载、联网、上传、窗口输入、点击、导航、强化、选材、确认和资源消耗。
- 禁止修改详情页 OCR 语义、正式策略、DP、评分、GUI、Holdout、MuMu 抓包读取器和任何真实输入后端。
- 禁止动态搜索区域、猜测坐标、自动重试、降低 `0.98` 门槛或绕过 fail-closed。

## 输入与权威口径

- 本文件、根目录 `AGENTS.md`、`e7-gear-enhance-plan.md`、现有列表页注册/解析/观察源代码与测试。
- 目标字段：武器、红装/传说、85 级、强化 `+3`、生命值套装、主属性攻击；副属性攻击 `13%`、暴击 `3%`、速度 `2`、效果抗性 `8%`；分数 `37`。
- 实际模型记录：`gpt-5.6-terra + high`；用户偏好 `gpt-5.6-luna + max` 当前协作接口不可用。

## 执行步骤

1. 只读审阅现有列表注册、PNG 观察源、识别器和测试。
2. 实现生产装配入口：没有显式 OCR/模板读取器工厂时立即 fail-closed；不得隐式创建测试假实现。
3. 让装配入口只产生 `RegisteredListPageLocalRecognizer`，不产生点击点或设备操作。
4. 使用合成/公开 fixture 验证完整三帧视觉字段链和异常闸门。
5. 运行定向列表测试、全部 `test_visual*.py`、Python 3.9 `py_compile` 和 `git diff --check`。
6. 主 agent 只读审阅代码、测试和报告后同步本任务说明与总计划。

## 产物

- 生产列表 OCR/模板读取器装配代码与离线回归测试。
- 离线验证报告。
- 本任务说明和 `e7-gear-enhance-plan.md` 的完成记录。

## 验证要求

- 正常 fixture 必须通过 `RegisteredListPageLocalRecognizer` 和 `InMemoryPngListPageObserver`。
- 缺失工厂、工厂异常、读取异常、低置信度、未知区域必须在产生证据前 fail-closed。
- 不得连接 ADB 或产生任何设备操作副作用。

## 停止条件

- 任何需要真实设备、真实 OCR 推理、网络、模型下载、动态区域或输入的要求立即停止并记录阻断。
- 任一门槛失败时保留 fail-closed，不得用 fixture 或人工字段绕过。

## 完成记录（2026-08-01）

- 新增 `src/e7_enhance/visual_list_production.py` 的显式生产装配入口；缺少或无法构造 OCR/模板读取器时 fail-closed，不创建测试假实现。
- 新增生产接线回归并覆盖三帧 PNG 哈希变化但视觉字段一致、工厂缺失/异常、非法读取器和低置信度。
- 离线报告：[reports/visual_list_production_reader_wiring_offline_20260801.md](reports/visual_list_production_reader_wiring_offline_20260801.md)。
- 全部 `test_visual*.py` `114/114`、Python 3.9 `py_compile`、`git diff --check` 均通过；未连接 ADB、未截图、未执行真实 OCR、输入、导航、点击或资源操作。

## 当前状态

`offline_production_list_reader_wiring_completed_main_reviewed_20260801`
