# 纯视觉装备列表页内存 PNG 局部观测器离线开发任务说明

## 目标

补齐稳定 `VisualFrame` / `StableFrames` 到装备列表页局部观测的纯内存、离线接线，使既有 `EquipmentListVisualParser` 可接收受控生成的列表页锚点、局部区域、可见边界、候选卡片与字段观测。

该任务是“自动选中目标装备并进入强化界面”的真实导航前置，不实现或执行任何真实点击、页面跳转或强化操作。

## 范围

- 仅修改 `src/e7_enhance` 中直接用于列表页内存 PNG 局部观测的最小模块、对应公开/合成 fixture 测试，以及本任务说明和总计划。
- 输入限定为调用方已提供的内存 PNG、已验证稳定帧元数据和明确注册的局部区域/识别器；输出必须可传给 `EquipmentListVisualParser`。
- 目标期望指纹为：武器、红装/传说、85 级、`+3`、生命值套装、攻击主属性、攻击力 `13%`、暴击率 `3%`、速度 `2`、效果抗性 `8%`、装备分数 `37`。

## 禁止修改项

- 禁止 ADB、真实截图、真实 OCR 推理、窗口输入、导航、点击、强化、选材、确认、资源消耗、底层读取、上传和模型下载。
- 禁止全屏盲 OCR、硬编码真实屏幕坐标、动态扩展识别区域、自动重试或把用户描述/fixture 写成真实页面视觉证据。
- 禁止修改正式策略、DP、评分、资源模型、GUI、既有详情页 OCR 语义、OCR 门槛、Holdout、真实帧源或自动化后端。

## 输入与权威口径

- 本文件是本轮唯一权威任务来源；同时遵守根目录 `AGENTS.md` 与 `e7-gear-enhance-plan.md`。
- 用户本轮批准的“下一步”仅覆盖本离线开发任务，不构成 ADB、截图、输入、导航、点击、强化或资源操作授权。
- 所有输出固定为 `mode=visual_only`、`verification=unverified`；锚点和目标期望字段逐项必须唯一且 `>=0.98`，任一不确定性均 fail-closed。

## 执行步骤

1. 只读审阅 `visual_adapter`、列表解析器、详情页局部识别器与现有测试，确定可复用的稳定帧/局部识别边界。
2. 定义受控的内存 PNG 局部观测器：只能从固定、已注册的列表页局部区域产生锚点、候选列表边界、可见边界、候选卡片和字段观测；不得产生点击点。
3. 接入 `EquipmentListVisualParser`，并保留详情页识别器及真实 ADB 行为不变。
4. 用合成/公开 fixture 覆盖正常唯一目标、低置信度、缺失/越界局部区域、未知滚动状态、重复候选、字段缺失或冲突、稳定帧不一致和空/黑帧；所有失败都必须在产生 `NavigationPageEvidence` 前终止。
5. 运行定向测试、相关视觉测试、Python 3.9 语法检查和 `git diff --check`，同步本任务说明、被覆盖的只读校准任务说明和总计划。

## 产物

- 纯内存列表页局部观测器及公开/合成测试。
- 受控的 `EquipmentListVisualParser` 输入构造路径；不包含真实坐标、设备发现、帧捕获或输入后端。
- 本任务说明和总计划中的完成记录、验证结果与下一步。

## 验证要求

- 只有稳定帧记录、局部锚点、区域边界、候选可见性、字段观察、唯一性与全部 `>=0.98` 条件同时通过时，才可形成 `NavigationPageEvidence`。
- 输入缺失、帧不稳定、空/黑帧、锚点/区域无效、低置信度、候选或字段重复/冲突、未知滚动边界均必须 fail-closed。
- 测试不得依赖当前 MuMu 页面、真实截图或真实 OCR 结果。

## 停止条件

- 需要 ADB、真实截图、真实 OCR、窗口输入、导航、点击、强化、选材、确认、资源操作、全屏 OCR、坐标猜测或额外模型时立即停止，并另建任务。
- 实现会修改详情页 OCR 语义、真实帧采集、自动化后端或正式策略时立即停止。

## 当前状态

`offline_memory_png_list_observer_development_completed_main_reviewed_20260730`

## 模型记录

用户偏好 `gpt-5.6-luna + max`；当前协作接口未提供 Luna。本任务实际执行模型按项目规定记录为 `gpt-5.6-terra + high`。

## 阶段初始化记录（2026-07-30）

- 用户确认总体目标是自动选中该唯一装备并受控进入强化界面，并批准执行当前下一步。
- 该批准被严格限定为本文件的离线接线；没有运行 ADB、截图、OCR、输入、导航、点击、强化、选材、确认、资源消耗、底层读取、上传或下载。
- 完成后必须重新创建并取得一次新的真实列表页三帧只读校准授权；真实点击还需在其后另建任务并单独授权。

## 完成记录（2026-07-30）

- 新增 `src/e7_enhance/visual_list_observer.py` 与 `tests/test_visual_list_observer.py`。观测器仅接收已验证的 `StableFrames`、调用方注册的归一化局部区域和注入式局部识别结果；它不含设备发现、帧捕获、OCR 推理、真实坐标、点击点或输入后端。
- 页面签名、视口、时间与稳定记录直接由内存帧派生；锚点、局部区域置信度、可见边界、候选和字段再受控传给既有 `EquipmentListVisualParser`。候选必须引用预注册且位于列表区域内的卡片区域，不能由识别结果动态扩大范围。
- 合成 PNG 覆盖唯一目标、低置信度、缺失区域分数、未知滚动、重复候选、字段缺失、未注册候选区域、空/黑帧、无效 PNG 与稳定帧哈希不一致；所有失败均在产生 `NavigationPageEvidence` 前 fail-closed。
- 本轮实际执行模型为 `gpt-5.6-terra + high`，因协作接口未提供用户偏好的 `gpt-5.6-luna + max`。未执行 ADB、真实截图、真实 OCR、输入、导航、点击、强化、选材、确认、资源操作、底层读取、上传或下载。

## 验证结果

- `C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe -m unittest discover -s tests -p 'test_visual_list_observer.py' -v`：`5/5` 通过，退出码 `0`。
- `C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe -m unittest discover -s tests -p 'test_visual_list_parser.py' -v`：`8/8` 通过，退出码 `0`。
- `C:\\Users\\orangine\\AppData\\Local\\Programs\\Python\\Python39\\python.exe -m unittest discover -s tests -p 'test_visual*.py' -v`：`93/93` 通过，退出码 `0`。
- Python 3.9 `py_compile`（观测器及其测试、列表解析器及其测试）：退出码 `0`。`git diff --check`：退出码 `0`，仅有既有 `e7-gear-enhance-plan.md` LF/CRLF 警告。

## 剩余风险与下一步

- 公开/合成 fixture 仅验证离线契约，不构成当前 MuMu 页面、目标唯一性或字段识别的真实证据。
- 原真实三帧只读校准任务的失败状态已被本离线开发完成记录覆盖，但旧授权不可复用。若继续，必须先新建并取得一次新的真实列表页三帧只读校准授权；该授权仍不包括输入、导航、点击或资源操作。

## 主 agent 审阅（2026-07-30）

- 主 agent 已只读审阅观测器和测试：注册区域是唯一候选范围来源，识别器不能提供裸点击坐标或扩张区域；稳定 PNG、局部区域分数、候选区域绑定和列表解析器的既有闸门均在构造证据前生效。
- 主 agent 复跑 `test_visual*.py`：`93/93` 通过，退出码 `0`；复跑 Python 3.9 `py_compile` 与 `git diff --check` 均为退出码 `0`，后者仅有既有计划文件 LF/CRLF 警告。
- 审阅和复验期间未运行 ADB、真实截图、OCR、输入、导航、点击、强化、选材、确认或资源操作。结论仅为离线前置完成；尚未创建真实校准任务，也未获得新的真实只读授权。
