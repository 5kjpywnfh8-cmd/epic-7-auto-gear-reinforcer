# 装备列表页离线证据复核与生产装配接线回归报告

## 结论

攻击%、暴击率%、效果抗性三个缺失字段与整卡视觉指纹模板的离线证据仍不足，`field_mapping_manifest.json` 与 `card_fingerprint_manifest.json` 继续 `incomplete`/`missing`，生产入口维持 fail-closed。本轮完成生产装配入口 `build_production_list_page_pipeline_from_assets` 的可审计接线回归（此前零覆盖）。

## 离线证据复核

- 使用本地 PaddleOCR（PP-OCRv4，缓存 `D:\VScode\cultivation\e7_ocr_cache`）离线运行参考 crop，未连接 ADB、未读取真实帧、未运行实时 OCR。
- 目标卡片 `weapon_target_card_raw_20260801.png` 只读到数值 token：`85`、`160`、`13%`、`3%`、`2`、`37`、`8%`、`+3`；属性类型靠图标视觉识别，目标卡片上攻击%、暴击率%、效果抗性% 图标的可靠语义参考仍缺失。
- 详情面板 OCR 文字证据（攻击力 `13%`、暴击率 `3%`、速度 `2`、效果抗性 `8%`、装备分数 `37`）只确认**详情页版式**的字段语义，不能替代**列表卡片**图标语义。
- 历史 before_page/武器参考卡片的副属性图标（生命值、防御%、速度、暴击伤害、效果命中等）已与同一历史详情面板交叉核对，但仍属 `reference_only`，不能作为目标卡片字段的生产证据。
- 整卡指纹模板只能来自历史 `reference_only` crop，任务明确禁止把历史截图或参考 crop 当生产模板，故 `card_fingerprint_manifest.json` 继续 `missing`。

## 变更

- `src/e7_enhance/visual_list_production.py`：`build_production_list_page_pipeline_from_assets` 在 frame capture 前对整卡模板 bundle 做**急切校验**（调用 `load_card_fingerprint_templates`），使哈希/视口/阈值缺陷以原始审计细节透传（如 `card fingerprint hash mismatch`），不再被通用 `production list template reader construction failed` 掩盖；字段映射与模板任一未达 `audited_complete` 仍抛 `ProductionListPageReaderUnavailable`。
- `tests/test_visual_list_production.py`：新增 `ProductionListPageAssetsPipelineTest` 共 9 个回归，覆盖 `build_production_list_page_pipeline_from_assets`：
  - 完整 fixture 双 manifest 正常装配并 parse（`passed`，候选 `production-candidate-001`）；
  - 仓库 manifest（incomplete/missing）在 frame capture 前 fail-closed；
  - 缺必需字段 fail-closed（`does not cover`）；
  - 低置信度 OCR fail-closed（`local_list_confidence_too_low`）；
  - 字段冲突 fail-closed（`candidate_fields_incomplete`）；
  - 模板哈希不匹配 fail-closed（`hash mismatch`）；
  - 视口漂移 fail-closed（`unknown_list_viewport`）。

## 验证

- `python -B -m unittest discover -s tests -p 'test_visual*.py'`：`126/126` 通过（原 `117` + 新增 `9`）。
- Python 3.9 `py_compile`：退出码 `0`。
- `git diff --check`：退出码 `0`，仅既有 LF/CRLF 换行警告。

## 真实设备边界

本轮未运行 ADB、未读取真实帧、未运行实时 OCR、未输入、未点击、未导航、未强化、未选材、未确认、未消耗资源、未联网、未上传或下载模型。实际执行模型为 `gpt-5.6-terra + high`（用户偏好 `gpt-5.6-luna + max` 当前接口不可用）。

## 剩余阻断

攻击%、暴击率%、效果抗性图标的可靠列表卡片语义与完整整卡视觉指纹模板仍未审定；不能把用户描述、历史截图或参考 crop 写成生产证据。补齐并审定这些资产并完成主 agent 审阅后，才可另建任务说明并重新取得一次真实三帧只读授权；校准通过仍不授权点击或导航。

## 主 agent 审阅结论（2026-08-01）

- 只读审阅本轮改动 `visual_list_production.py`（eager 模板 bundle 校验）、`test_visual_list_production.py`（9 个资产装配回归）与本文档，确认：
  - 字段映射 manifest 继续 `incomplete`、整卡指纹 manifest 继续 `missing`，生产入口在 frame capture 前 fail-closed，未降低 `0.98` 门槛、未生成默认模板或人工通过结果。
  - `build_production_list_page_pipeline_from_assets` 与 `build_production_list_page_pipeline` 的接线契约一致：OCR reader 工厂由调用方显式注入，字段映射仅作审计 gate；模板 reader 由 asset bundle 构造；缺陷以原始审计细节透传。
  - 五类回归（正常/低置信度/字段冲突/模板缺失哈希不匹配/视口漂移）均已覆盖并通过。
- 审阅未发现把历史截图、参考 crop、测试 fixture 或套装图标冒充生产证据的代码或文档；报告与任务说明均明确标注参考资产 `reference_only`、真实列表页仍不可用。
- 结论：离线范围已收口，产物可提交；真实列表页不可用结论维持不变。下一步必须取得可靠字段语义与整卡模板后，另建任务说明并重新取得一次性只读授权。
