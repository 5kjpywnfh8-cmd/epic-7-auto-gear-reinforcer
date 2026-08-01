# 纯视觉装备列表页内存局部 OCR 观察源离线开发任务说明

## 目标

在既有固定 `1280x720` 列表页区域注册和 `RegisteredListPageLocalRecognizer` 之下，补齐“内存 PNG 固定局部裁切 -> 注入式本地 OCR/模板读取 -> 结构化局部观察值”的生产适配器，使列表页链路不再依赖 `FakeRecognizer` 或预先拼装的完整观察对象。

本任务只交付离线接口与公开/合成 fixture 回归，不证明当前 MuMu 页面已经匹配，也不授予真实三帧校准、点击或强化权限。

## 范围

- 仅修改直接服务于列表页内存局部观察源的 `src/e7_enhance` 模块、对应测试、本任务说明和 `e7-gear-enhance-plan.md`。
- 适配器只接收 `VisualFrame` 的 PNG 字节、版本化固定区域注册，以及显式注入的局部 OCR/模板读取器。
- 适配器只裁切已注册区域并生成 `schema_version`、视口、锚点、区域得分、滚动边界、候选卡片和字段观察；不生成点击点、屏幕坐标或输入动作。
- 允许使用现有内存 PNG 解码/裁切能力；不得调用 ADB、窗口后端、全屏 OCR、动态区域搜索或模型下载。
- 文本/模板读取器的返回值必须经过白名单、完整性、唯一性和 `>=0.98` 置信度校验；任一异常或不确定性均 fail-closed。

## 禁止修改项

- 禁止 ADB、真实截图、设备发现、输入、导航、点击、强化、选材、确认和资源消耗。
- 禁止修改详情页 OCR 语义、正式策略、DP、评分、资源模型、GUI、Holdout、真实帧源或自动化后端。
- 禁止把用户描述、历史截图或合成 fixture 写成当前 MuMu 真实证据。
- 禁止降低 `0.98`、绕过唯一性、滚动边界、固定区域或 `mode=visual_only` / `verification=unverified` 约束。

## 输入与权威口径

- 本文件是本轮唯一权威任务来源，同时遵守根目录 `AGENTS.md`、`e7-gear-enhance-plan.md` 以及既有列表识别器/观测器任务说明。
- 固定区域和字段白名单以 `equipment_list_region_registry()`、`RegisteredListPageLocalRecognizer` 和 `EquipmentListVisualParser` 为准。
- 目标期望指纹仅用于 fixture 断言：武器、红装/传说、85 级、`+3`、生命值套装、攻击主属性、攻击 `13%`、暴击 `3%`、速度 `2`、效果抗性 `8%`、分数 `37`。
- 所有输出继续标记 `mode=visual_only`、`verification=unverified`，并在证据生成前 fail-closed。

## 执行步骤

1. 只读审阅现有 `VisualFrame`、PNG 解码/裁切、列表注册、识别器和解析器契约。
2. 实现独立的内存局部观察源适配器：校验视口与精确注册区域，按固定区域裁切 PNG，调用显式注入的 OCR/模板读取器，并把结果转换为列表识别器所需的结构化观察。
3. 为正常唯一目标、未知视口/区域、无效 PNG、读取器异常、低置信度、未知 token、字段缺失/冲突、候选重复、滚动边界未知和空卡片补充公开/合成回归。
4. 运行定向列表测试、全部 `test_visual*.py`、Python 3.9 `py_compile` 和 `git diff --check`。
5. 由主 agent 只读审阅代码、分片和测试后，更新本说明与总计划；未通过前不得重新申请真实三帧只读校准。

## 产物

- 可实例化的内存 PNG 局部 OCR/模板观察源适配器及最小公开接口。
- 不依赖真实设备、网络、模型或落盘的合成 fixture 测试。
- 本说明、总计划中的完成/未完成项、验证结果、剩余风险和下一步。

## 验证要求

- 正常 fixture 必须由 PNG 内存裁切和注入式局部读取结果构成完整 `local_regions`，再经 `RegisteredListPageLocalRecognizer` 与 `InMemoryPngListPageObserver` 生成解析结果。
- 任一视口、区域、裁切、读取、字段、置信度、唯一性或边界失败都必须在 `NavigationPageEvidence` 前返回 fail-closed，且不产生点击点。
- 测试不得依赖当前 MuMu 页面、真实截图、网络、PaddleOCR 模型或设备。

## 停止条件

- 需要 ADB、真实帧、真实 OCR 推理、模型下载、动态坐标、输入、导航或资源操作时立即停止并另建任务。
- 无法在固定区域和显式读取器契约下保持 `>=0.98`、唯一性或 fail-closed 时，保留阻断，不得用 fixture 或人工字段绕过。

## 当前状态

`offline_memory_png_local_ocr_observation_source_development_completed_main_reviewed_20260731`

## 模型记录

用户偏好 `gpt-5.6-luna + max`；当前协作接口不可用 Luna，本轮实际执行模型按项目回退规则记录为 `gpt-5.6-terra + high`。

## 授权记录（2026-07-31）

用户明确批准“开发内存局部 OCR 观察源”。授权仅覆盖本任务离线实现和公开/合成回归，不覆盖 ADB、截图、OCR 真实推理、输入、导航、点击、强化、选材、确认或资源操作。

## 完成记录（2026-07-31）

- 新增 `src/e7_enhance/visual_list_observer.py` 中的通用 `InMemoryPngListPageLocalObservationSource`：严格校验注册表、视口和区域集合，在进程内裁切固定 PNG，并把每个 `LocalPngCrop` 交给显式读取器；读取异常、无效 PNG、未知区域和非 mapping 结果均在证据前 fail-closed。
- 新增 `src/e7_enhance/visual_list_png_source.py` 中的 `InMemoryPngListPageObservationSource` 及 OCR/模板读取器协议：OCR 负责锚点、区域边界和卡片字段，模板读取器负责卡片视觉指纹；字段、锚点、边界、指纹和模板分数均保持白名单、唯一性与 `>=0.98`。
- 新增公开/合成回归：`test_visual_list_local_source.py` 3/3、`test_visual_list_png_source.py` 4/4；正常目标通过 `RegisteredListPageLocalRecognizer` 与 `InMemoryPngListPageObserver`，异常均在 `NavigationPageEvidence` 前停止。
- 主 agent 已只读审阅实现并补充模板置信度 fail-closed 闸门；未执行 ADB、真实截图、真实 OCR 推理、输入、导航、点击、强化、选材、确认、资源操作、联网、上传或模型下载。

## 验证记录（2026-07-31）

- 列表相关视觉测试：`25/25`，退出码 `0`。
- 全部 `test_visual*.py`：`105/105`，退出码 `0`。
- Python 3.9 `py_compile`（全部 `visual*.py` 与 `test_visual*.py`）：退出码 `0`。
- `git diff --check`：退出码 `0`；仅提示既有总计划 LF/CRLF 转换。
- 详细离线结果见[验证报告](reports/visual_list_png_source_offline_20260731.md)。

## 剩余风险与下一步

- 适配器和 fixture 只证明离线接口可用，不证明当前 MuMu 列表页的真实布局、OCR 结果、模板分数或目标唯一性；当前真实列表三帧校准仍在 ADB 前 fail-closed。
- 下一步必须另建新的真实列表页三帧只读校准任务并取得一次新的明确只读授权；该授权仍不包含输入、点击、导航或资源操作。列表选中和进入强化界面仍需后续独立任务与逐次新鲜后验。
