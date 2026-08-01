# 纯视觉装备列表页 OCR 字段映射与卡片模板资产准备任务说明

## 目标

为列表页生产 OCR/模板读取器提供可审计的字段映射、卡片版式参考和模板/指纹资产，使现有本地 PaddleOCR 引擎核心可以安全复用于列表卡片，而不把详情页解析器直接套用到不同版式。

## 范围

- 盘点已存在的本地 PaddleOCR 模型缓存，固定一个 ASCII 缓存根路径并记录完整性。
- 定义列表卡片各字段的局部区域、OCR 原始 token 到规范值的映射、字段顺序和置信度来源。
- 定义列表页标题/排序锚点和候选卡片视觉指纹/模板 manifest；模板必须有来源、版本、视口和校验值。
- 仅用离线参考资产和合成 fixture 验证；参考资产不构成当前 MuMu 页面证据。

## 禁止操作

- 禁止 ADB、真实截图、实时 OCR、输入、点击、导航、强化、选材、确认和资源消耗。
- 禁止联网、模型下载、使用人工字段冒充 OCR 输出、使用详情页截图冒充列表页模板或把套装图标单独冒充整卡模板。
- 禁止降低 `0.98` 门槛、放宽固定区域、动态搜索或隐式回退测试 reader。

## 已知可复用部分

- 本地 PaddleOCR 包和模型文件已存在：`D:\VScode\cultivation\e7_ocr_cache` 与用户目录缓存均通过只读路径盘点可见。
- `ocr_paddle.py` 的引擎初始化、中文文本清理、数值和属性词归一化可抽取为列表专用适配层。
- `visual_list_png_source.py`、`RegisteredListPageLocalRecognizer` 和生产装配入口已提供固定区域、内存 PNG 和 fail-closed 接口。

## 仍需提供/审定的输入

1. 列表卡片字段布局参考：部位、品质、等级、强化、套装、主属性、副属性和分数各自的局部区域或明确字段顺序。
2. OCR 字段映射：中文/符号 token 到规范值的白名单、百分号/数值规则及字段冲突处理。
3. 列表页标题、排序按钮和候选卡片的模板/指纹资产 manifest，包含版本、来源、视口、SHA-256 和 `>=0.98` 阈值。
4. 可离线审计的参考 PNG/crop；其只用于资产验证，不得写成当前真实页面证据。

## 执行步骤

1. 审核模型缓存与依赖，不联网、不下载。
2. 审定字段映射和固定 crop manifest。
3. 用现有 PaddleOCR 引擎核心实现列表专用内存 reader；用审定模板实现标题/排序/卡片指纹 reader。
4. 接入 `build_production_list_page_pipeline`，覆盖正常、低置信度、字段冲突、模板缺失和视口漂移回归。
5. 主 agent 审阅后，另建新的真实三帧只读校准任务并重新授权。

## 当前状态

`offline_list_field_mapping_and_card_template_build_in_progress_20260801`

## 已完成的离线准备（2026-08-01）

- 从历史 `before_page.png` 提取列表网格、代表性卡片、第二行卡片和右侧详情面板参考 crop，并写入 `assets/visual/list_reference/manifest.json`。
- 额外提取了主属性/副属性/套装图标候选 crop；生命值主属性以及防御%、速度、效果抗性%、效果命中%的四个副属性图标可与同一历史详情面板交叉核对，但仍只属于参考资产。
- 参考资产均标记为 `reference_only`，不能替代当前 MuMu 页面证据；套装图标 manifest 仍只覆盖套装图标，不是整卡模板。
- 本轮未连接 ADB、未截图、未运行实时 OCR、未输入、未点击或导航。

## 武器列表参考资产补充（2026-08-01）

- 用户进入武器列表后批准一次性只读采集；已生成 `assets/visual/list_reference/weapon_capture_manifest_20260801.json` 及四个固定 crop。
- 右侧详情参考交叉确认了武器主属性攻击力、生命值、速度、暴击伤害和分数的列表版式；仍不能证明当前目标装备。
- 当前仍缺攻击%、暴击率%、效果抗性图标的可靠语义映射和整卡视觉指纹模板。
- 武器参考卡片已额外提取攻击主属性、生命值、速度和暴击伤害图标，并在武器采集 manifest 中记录来源与 SHA-256；这些仍是参考资产，不代表当前目标命中。

## 停止条件

- 缺少字段语义映射、模板来源、校验值或当前页面复核前，保持生产读取器缺失的 fail-closed 状态，不生成默认模板或人工通过结果。

## 模型记录

用户偏好 `gpt-5.6-luna + max`；当前接口不可用 Luna，后续实际执行模型记录为 `gpt-5.6-terra + high`。

## 继续执行记录（2026-08-01）

- 用户要求继续处理第七次真实校准的生产 reader 阻断；本轮重新进入离线资产和接线开发。
- 本轮只补齐可审计的列表字段白名单/规范化映射、模板 manifest/指纹读取器和生产工厂接线；禁止 ADB、真实截图、实时 OCR、输入、点击、导航、强化、选材、确认、资源消耗、联网、上传和模型下载。
- 攻击%、暴击率%、效果抗性和整卡指纹若没有可靠参考证据，必须保持未知并 fail-closed，不得用用户描述或历史 crop 伪造通过结果。

## 本轮离线接线结果（2026-08-01）

- 新增 `assets/visual/list_reference/field_mapping_manifest.json` 与 `card_fingerprint_manifest.json`；二者分别明确为 `incomplete` 和 `missing`，不会作为生产放行资产。
- 新增 `src/e7_enhance/visual_list_assets.py`，对字段 token 的 schema、状态、来源、置信度和整卡模板的 schema、作用域、SHA-256、视口与阈值进行严格验证；未知 token、非审定 mapping、图标替代整卡或缺失模板均 fail-closed。
- `build_production_list_page_pipeline_from_assets` 已在进入 frame capture 前验证两类资产；当前会抛出 `ProductionListPageReaderUnavailable`，不构造真实 OCR/模板 reader。
- 定向验证：资产回归 4/4；完整列表视觉 discover `117/117`；Python 3.9 编译退出码 `0`；`git diff --check` 退出码 `0`。详见[离线接线报告](reports/visual_list_assets_offline_build_20260801.md)。
- 本轮未连接 ADB、未读取真实截图、未运行实时 OCR、未输入、未点击、未导航、未强化、未选材、未确认、未消耗资源、未联网、未上传或下载模型。实际模型为 `gpt-5.6-terra + high`。

## 主 agent 审阅补强（2026-08-01）

- 补充 `REQUIRED_LIST_FIELDS` 校验，字段 manifest 即使声明 `audited_complete` 也必须覆盖 `slot`、`rank`、`level`、`enhance`、`set`、`main`、`substats`、`gear_score` 八个列表字段；未知字段和缺字段均 fail-closed。
- 复验：`python -B -m unittest discover -s tests -p 'test_visual_list*.py'` 为 `39/39`；Python 3.9 `py_compile` 退出码 `0`；`git diff --check` 退出码 `0`（仅既有换行警告）。

## 当前状态

`offline_list_assets_wired_fail_closed_waiting_reliable_semantics_and_full_card_templates_20260801`

## 合并收口后新会话交接记录（2026-08-01）

- 会话 `019fa96f-...` 的视觉列表页产物已并入当前工作区并提交（commit `265785b`，79 个文件：7 源码、8 测试、31 资产、10 报告、22 任务说明、`CLAUDE.md`）。详见[合并收口任务说明](纯视觉列表页会话产物合并收口任务说明.md)。
- 项目根已建立 `CLAUDE.md`（AGENTS.md 全文镜像），新 CC 会话启动即自动加载完整项目规则；AGENTS.md 为权威源，改动必须同步两处。
- 本轮由新 Claude Code 会话继续执行本文档：在既有离线基础上推进，目标是补齐并审定攻击%、暴击率%、效果抗性的可靠字段语义映射，以及完整的整卡视觉指纹模板，并将生产 OCR/模板 reader 工厂接线至 `build_production_list_page_pipeline`。
- 未完成任务不改变：真实三帧只读校准、点击装备进入强化界面均未授权、未执行，须另建任务说明并重新取得一次性只读授权。
- 交接指令由用户手动复制到新会话；本文档为唯一权威来源，聊天内容不能替代或扩大范围。

## 离线证据复核与生产装配接线回归（2026-08-01）

- 本轮对既有离线参考资产做了证据复核，结论仍为证据不足，`field_mapping_manifest.json` 与 `card_fingerprint_manifest.json` 保持 `incomplete`/`missing`，生产入口维持 fail-closed：
  - 本地 PaddleOCR 引擎（`D:\VScode\cultivation\e7_ocr_cache`，PP-OCRv4）离线 OCR 目标卡片 crop 只读到数值 token（`85`/`160`/`13%`/`3%`/`2`/`8%`/`37`），属性类型靠图标视觉识别，目标卡片上攻击%、暴击率%、效果抗性% 三个图标的可靠语义参考仍缺失；详情面板 OCR 文字证据（攻击力 `13%`、暴击率 `3%`、效果抗性 `8%`）只确认详情页版式字段语义，不能替代列表卡片图标语义。
  - 整卡指纹模板只能来自历史 `reference_only` crop，任务明确禁止把历史截图或参考 crop 当作生产模板；故 `card_fingerprint_manifest.json` 继续 `missing`。
- 补齐 `build_production_list_page_pipeline_from_assets` 的回归测试（此前零覆盖）：完整 fixture 双 manifest 正常装配并 parse、仓库 manifest 在 frame capture 前 fail-closed、缺必需字段 fail-closed、低置信度 OCR fail-closed、字段冲突 fail-closed、模板哈希不匹配 fail-closed、视口漂移 fail-closed。
- 改进 `visual_list_production.py`：在 `build_production_list_page_pipeline_from_assets` 中对整卡模板 bundle 做**急切校验**（`load_card_fingerprint_templates`），使哈希/视口/阈值缺陷以原始审计细节透传，而不是被通用 `reader construction failed` 掩盖。
- 验证：`test_visual*.py` `126/126`（原 117 + 新增 9）、Python 3.9 `py_compile` 退出码 `0`、`git diff --check` 退出码 `0`（仅既有 LF/CRLF 警告）。
- 本轮未连接 ADB、未读取真实帧、未运行实时 OCR、未输入、未点击、未导航、未强化、未选材、未确认、未消耗资源、未联网、未上传或下载模型。实际执行模型为 `gpt-5.6-terra + high`（用户偏好 `gpt-5.6-luna + max` 当前接口不可用）。
- 停止条件不变：缺字段语义、模板来源或校验值时保持 fail-closed。当前状态：`offline_evidence_reviewed_production_assembly_wired_fail_closed_waiting_reliable_semantics_and_full_card_templates_20260801`。下一步只能先取得可靠字段语义与整卡模板，再另建任务说明并重新取得一次性只读授权。

## 主 agent 审阅通过（2026-08-01）

- 主 agent 已只读审阅本轮代码改动、9 个资产装配回归和[离线证据复核与装配接线回归报告](reports/visual_list_assets_evidence_and_assembly_regression_20260801.md)，确认：
  - 两个 manifest 继续 `incomplete`/`missing`，生产入口 frame capture 前 fail-closed，`0.98` 门槛未降低，无默认模板或人工通过结果。
  - 生产装配接线契约正确：OCR reader 工厂由调用方显式注入、字段映射作审计 gate、模板 reader 由 asset bundle 构造、缺陷原始细节透传。
  - 五类回归（正常/低置信度/字段冲突/模板缺失/视口漂移）覆盖并通过；未发现以历史截图、参考 crop 或测试 fixture 冒充生产证据。
- 上条 `offline_evidence_reviewed_production_assembly_wired_fail_closed_waiting_reliable_semantics_and_full_card_templates_20260801` 已被本记录覆盖为 `offline_evidence_reviewed_and_assembly_wired_main_reviewed_20260801`。
- 真实列表页仍不可用；下一步必须取得可靠攻击%、暴击率%、效果抗性图标语义与完整整卡指纹模板，再另建任务说明并重新取得一次性只读授权（仍不包含点击或导航）。

## 真实整卡采集与图标语义复核（2026-08-01）

- 用户授权真实三帧只读采集后执行：官方 MuMu ADB 发现唯一 `emulator-5554`，三次 `exec-out screencap -p` 均为 `1280x720`；目标卡片区域与右侧详情面板区域三帧像素完全一致，页面稳定。
- 详情面板 OCR 高置信确认目标装备真值（`传说武器`/`攻击力 160`/`攻击力 13%`/`暴击率 3%`/`速度 2`/`效果抗性 8%`/`装备分数 37`/`生命值套装`/`85`/`+3`）；列表卡片副属性数值顺序（13%/3%/2/8%）与详情面板文字标签完全对齐，确认为同一件选中装备。
- 提取三帧一致的整卡 crop（170x117）保存为 `assets/visual/list_reference/capture_20260801/target_card_full_20260801.png`（`reference_only`）。
- 复核结论：字段语义与整卡指纹两项阻断仍成立，两个 manifest 继续 `incomplete`/`missing`：
  - 列表卡片图标（约 9-16px）与详情面板图标模板匹配分数低于 `0.98`（NCC/IoU 约 0.05-0.62），不是同一套可匹配渲染；攻击%/暴击率%/效果抗性% 图标语义仍无可靠证据。
  - 注册区域 `candidate_card:1`（512x160）与真实列表卡片（170x117）不匹配，整卡指纹无法在当前注册区域下命中。
- 本轮真实采集未输入、未点击、未导航、未强化、未消耗资源、未联网；结果继续 `mode=visual_only`、`verification=unverified`、fail-closed。

## 真实三帧区域校准与整卡指纹登记（2026-08-01）

- 用户批准一次性三帧只读采集后执行：官方 MuMu ADB 唯一 emulator-5554，三次 exec-out screencap -p 均 1280x720；目标卡片区域与详情面板区域三帧逐像素一致（mean_diff=0.00），页面稳定。
- 依据分数锚点（OCR 置信 >=0.99）离线确定列表网格：5 行（行顶 y=65/193/322/451/580，行高 117）x 4 列（列左 x=143/313/483/653，列宽 170）；目标卡片位于行 4 列 1（x143-313, y451-568）。
- equipment_list_region_registry() 从假设 2x3 网格（6 卡）校准为真实 4x5 网格（20 卡），candidate_card:13 精确对位目标卡片；list_header_region 与 candidate_list_region 同步更新。
- 哈希口径修复：已存整卡 crop 为 PIL 编码（sha256 cf1d02e...），与运行时 InMemoryPngRegionExtractor 的 filter-0 zlib 编码不一致；按运行时编码重建 	arget_card_full_20260801_runtime.png（sha256 99efe5c2...），card_fingerprint_manifest.json 升级 udited_complete 并登记模板。
- 命中验证：三帧在 candidate_card:13 区域 crop SHA-256 均为 99efe5c2...，ManifestCardFingerprintReader.match_template 返回 score 1.0 / threshold 0.98。
- 验证：	est_visual_list*.py 46/46、	est_visual*.py 126/126、py_compile 0、git diff --check 0。
- 详细结果见[区域校准与指纹登记报告](reports/visual_list_region_calibration_and_fingerprint_20260801.md) 与[区域校准任务说明](纯视觉真实列表页区域注册校准任务说明.md)。
- 未改变结论：ield_mapping_manifest.json 仍 incomplete（攻击%/暴击率%/效果抗性% 图标语义无可靠证据），生产入口继续 fail-closed；真实三帧只读校准仍待另建任务与重新授权。
