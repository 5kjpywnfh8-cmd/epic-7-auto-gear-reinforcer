# 真实列表页区域注册校准与整卡指纹模板登记报告

## 结论

`equipment_list_region_registry()` 已按真实列表网格校准（5 行 × 4 列 = 20 张候选卡片区域），`candidate_card:13` 精确对位目标卡片（x143-313, y451-568）；`card_fingerprint_manifest.json` 从 `missing` 升级为 `audited_complete`，登记按运行时编码重建的整卡指纹模板，三帧 SHA-256 命中验证通过（score 1.0）。生产入口因 `field_mapping_manifest.json` 仍 `incomplete` 继续 fail-closed。

## 采集与稳定性

- 授权一次性三帧只读采集：官方 MuMu ADB 唯一设备 `emulator-5554`，三次 `exec-out screencap -p` 均 `1280x720`。
- 帧 SHA-256：`bf0e6890…`/`ba0166c4…`/`51c6b5ff…`。
- 目标卡片区域（x143-313, y451-568）与详情面板区域（x820-1280, y300-480）三帧逐像素 mean_diff=0.00；列表头部 0.03（顶栏数字/时钟）。目标卡片 raw 像素 digest `13531f05…` 与 2026-08-01 早前采集的已存整卡完全一致，确认同一布局同一目标。

## 网格校准

以分数（gear score）锚点为最可靠证据（OCR 置信 ≥0.99）：

- 分数行 y：155.5/283.8/413/541.5/670 → 行间距 128.5 → 行顶 y=65/193/322/451/580，行高 117。
- 分数列 x：179.3/349.7/521.7/692 → 列间距 ~170 → 列左 x=143/313/483/653，列宽 170。
- 目标卡片（行4 列1）亮边框 x143-144/312-313、y450-451/567-568 与推算完全吻合。

`equipment_list_region_registry()` 更新：

- `list_header_region`：{left:0.05, top:0.02, right:0.95, bottom:0.09}（像素 64,14,1216,65）。
- `candidate_list_region`：{left:0.05, top:0.08, right:0.95, bottom:0.98}。
- `candidate_card:1..20`：5 行 × 4 列网格，`candidate_card:13` = 目标卡片（x143-313, y451-568）。

## 整卡指纹模板

- **哈希口径差异（根因）**：已存 `capture_20260801/target_card_full_20260801.png` 为 PIL 编码 PNG（sha256 `acf1d02e…`）；运行时 `InMemoryPngRegionExtractor` 输出 filter-0 zlib 编码 PNG。两者字节不同，导致此前指纹无法命中。本轮按运行时编码重建资产。
- 新模板资产：`assets/visual/list_reference/target_card_full_20260801_runtime.png`（170×117），PNG sha256 `99efe5c27e3b4af207f0e5f037de901f8da1ccfd706160540330b31e5fc8d72e`。
- `card_fingerprint_manifest.json`：`audited_complete` / `full_card`，单模板 `weapon_target_card_20260801`（viewport [170,117]，threshold 0.98）。
- **命中验证**：三帧在 `candidate_card:13` 区域经 `InMemoryPngRegionExtractor` 的 crop SHA-256 均为 `99efe5c2…`；`ManifestCardFingerprintReader.match_template` 返回 `visual_fingerprint=99efe5c2…, score=1.0, threshold=0.98`，唯一命中。

## 验证结果

- `test_visual_list*.py`：46/46 通过（含更新后的资产/装配/观测回归）。
- `test_visual*.py`：126/126 通过。
- Python 3.9 `py_compile`：退出码 0。
- `git diff --check`：退出码 0（仅既有 LF/CRLF 警告）。

## 真实设备边界

未发送输入、未点击、未滚动、未导航、未进入详情/强化页、未选材、未确认、未消耗资源；未重试、未追加采样、未联网、未上传或下载模型。一次性只读授权已使用且不可复用。

## 剩余阻断与下一步

1. `field_mapping_manifest.json` 仍 `incomplete`：攻击%/暴击率%/效果抗性% 列表卡片图标语义无可靠证据，生产 OCR reader 仍不可配置 → `build_production_list_page_pipeline_from_assets` 继续在 frame capture 前 fail-closed（正确行为）。
2. 真实三帧只读校准（生产 reader 就绪后）仍属后续任务，需另建任务说明并重新取得一次性只读授权；该校准不包含点击或导航。
3. 下一步建议：待字段语义审定后，运行生产装配 + 真实三帧只读校准验证完整链路。
