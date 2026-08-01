# 装备列表页生产 OCR/模板引擎实例接线离线审阅（2026-08-01）

## 结论

本轮在离线范围内保持生产读取器缺失的 fail-closed 状态，未新增伪造的 OCR/模板实例，也未进入真实校准。

## 审阅结果

- `build_production_list_page_pipeline` 已要求调用方显式提供 OCR 与模板读取器工厂；缺失、构造异常或接口不完整会抛出 `ProductionListPageReaderUnavailable`。
- `ListPagePngOcrReader` / `ListPagePngTemplateReader` 与固定区域、内存 PNG 观察源和 `RegisteredListPageLocalRecognizer` 的接线已存在，并由公开/合成 fixture 覆盖。
- `src/e7_enhance/ocr_paddle.py` 的现有 PaddleOCR 适配器绑定的是详情页强化文本区域（`enhance`、`set_text` 等），没有装备列表页卡片字段映射，不能作为列表页生产 OCR 实例。
- 本地 PaddleOCR 包及模型缓存已存在，能够复用通用引擎核心；阻断不在通用模型二进制，而在列表页专用字段映射、卡片版式参考和模板/指纹资产缺失。
- `assets/visual/set_icons/fribbels/manifest.json` 及其 PNG 仅是套装图标资产，没有列表卡片视觉指纹模板、卡片字段 OCR 版式或经审定的列表页模板分数配置。
- 因此当前没有可审计的本地列表 OCR/模板引擎实例；把测试 reader、人工字段或套装图标 matcher 接入生产入口会违反本任务禁止项。

## 验证与阻断

- 仅进行源码与本地资产只读审阅；未连接 ADB、未截图、未运行真实 OCR、未联网、未下载模型、未输入或点击。
- 阻断：缺少可审计的列表页 OCR 模型/字段映射和候选卡片模板资产。按照任务停止条件，本轮不新增生产实例，不宣称真实列表页可用。

## 下一步

必须另建[列表页 OCR 字段映射与卡片模板资产准备任务](../纯视觉装备列表页OCR字段映射与卡片模板资产准备任务说明.md)，先提供经审计的列表卡片字段映射、版式参考和卡片视觉指纹模板资产；在资产完整前，生产 pipeline 继续按显式依赖缺失 fail-closed。
