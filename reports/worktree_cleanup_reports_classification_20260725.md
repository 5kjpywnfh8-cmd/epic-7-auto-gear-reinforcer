# 顶层报告分类清单（2026-07-25）

## 审阅证据

- 审阅范围是当前未跟踪的 `reports/` 顶层文件，共 `225` 个，`108157699` 字节；不含已忽略的深层生成分片。
- 分类由 `gpt-5.6-terra + high` 只读完成，主 agent 复算文件数、总大小、集合 SHA-256、JSON 解析和敏感模式扫描。
- A、B、C、D 四类互斥且并集完整覆盖 225 个文件，缺失和额外均为 `0`。

## 分类摘要

| 类别 | 文件数 | 字节数 | 集合 SHA-256 | 处置 |
| --- | ---: | ---: | --- | --- |
| A 权威研究摘要和 manifest | 76 | 45922614 | `c349de7165acecfcf20ee6e6bb19c31ef40471ab7087410c4dccddee5077025f` | 分 Markdown 摘要、JSON manifest 提交 |
| B 可再生成原始输出和日志 | 98 | 40156240 | `288b4132eeeba733afec1a68ed085f6b684795f0f93a1f251b26e7a698849107` | 按精确路径加入 `.gitignore`，不删除 |
| C 私人或真实操作/研究数据 | 49 | 22063344 | `c932a3aa7c6c1caaf03556a7e8af1908a1edd7a0319ced4f255e06472f41d97f` | 保持本地，等待新的精确外传授权 |
| D 含本地路径或真实库存来源 | 2 | 15501 | `896e5108f2fb3b776b4f801176f2a74d100a1153c5c525be08a195593e9b9659` | 脱敏前不提交、不改写 |

### A 类验证

- 76 个文件中 22 个 JSON 全部通过解析。
- 具体 IPv4 端点、绝对本地路径、PCAP、外部服务 URL、API key、secret、password、token 模式命中为 `0`。
- A 类 Markdown 摘要作为第一组提交；22 个 JSON manifest 在下一组单独提交。

### C 类精确路径

```text
reports/epic_exact_plus3_candidate_20260717.json
reports/epic_exact_plus3_development_20260717.json
reports/epic_exact_plus3_development_20260717.md
reports/epic_exact_plus3_joint_pool_20260717.json
reports/epic_exact_plus3_joint_pool_20260717.md
reports/epic_exact_plus3_validation_20260717.json
reports/epic_exact_plus3_validation_20260717.md
reports/epic_high_confidence_stop_20260714.json
reports/epic_high_confidence_stop_20260714.md
reports/epic_output_8_13_tank_10_17_holdout_validation_20260719.json
reports/epic_output_8_13_tank_10_17_holdout_validation_20260719.md
reports/epic_output_8_13_tank_10_17_release_20260720.md
reports/epic_plus3_prospective_collection_20260714.md
reports/manual-acceptance-early-speed-gamble-20260711.md
reports/manual-acceptance-first-batch-20260711.md
reports/manual-acceptance-future75-20260711.md
reports/ocr_raw_backpack_epic_20260722.json
reports/ocr_stage1_backpack_batch_003_pairing_20260722.md
reports/ocr_stage1_backpack_batch_004_ocr_shadow_20260722.md
reports/ocr_stage1_backpack_batch_005_detail_20260722.md
reports/ocr_stage1_backpack_batch_005_reader_20260722.md
reports/ocr_stage1_backpack_batch_005_shadow_20260722.md
reports/ocr_stage1_backpack_batch_006_pairing_20260722.md
reports/ocr_stage1_backpack_batch_007_shadow_20260722.md
reports/ocr_stage1_backpack_batch_008_shadow_20260722.md
reports/ocr_stage1_backpack_batch_009_shadow_20260722.md
reports/ocr_stage1_backpack_batch_010_shadow_20260722.md
reports/ocr_stage1_backpack_batch_011_shadow_20260722.md
reports/ocr_stage1_backpack_batch_012_shadow_20260722.md
reports/ocr_stage1_backpack_batch_013_shadow_20260722.md
reports/ocr_stage1_backpack_batch_014_shadow_20260722.md
reports/ocr_stage1_backpack_batch_015_shadow_20260722.md
reports/ocr_stage1_backpack_batch_016_shadow_20260722.md
reports/ocr_stage1_backpack_batch_017_shadow_20260722.md
reports/ocr_stage1_backpack_batch_018_shadow_20260722.md
reports/ocr_stage1_backpack_batch_019_shadow_20260722.md
reports/ocr_stage1_backpack_batch_020_shadow_20260722.md
reports/ocr_stage1_backpack_batch_021_shadow_20260722.md
reports/ocr_stage1_backpack_batch_022_shadow_20260722.md
reports/ocr_stage1_backpack_batch_023_shadow_20260722.md
reports/ocr_stage1_backpack_batch_024_shadow_20260723.md
reports/ocr_stage1_backpack_batch_025_shadow_20260723.md
reports/ocr_stage1_backpack_batch_026_shadow_20260723.md
reports/ocr_stage1_backpack_batch_027_shadow_20260723.md
reports/ocr_stage1_backpack_priority_20260722.md
reports/ocr_stage1_batch_001_pairing_20260721.md
reports/ocr_stage1_manual_review_packet_20260723.md
reports/single_item_confirmation_summary_20260723.json
reports/single_item_confirmation_summary_20260723.md
```

### D 类精确路径

```text
reports/calibration-strategy-summary.md
reports/reforged_inventory_set_weights_20260718.json
```

## 其他私人待决组

| 路径范围 | 文件数 | 字节数 | 集合 SHA-256 |
| --- | ---: | ---: | --- |
| `manual_acceptance/` 未跟踪文件 | 276 | 197821247 | 按目录/相对路径排序的组清单见任务记录 |
| 剩余真实或实例样本 | 7 | 3041714 | `5665f35b588fb08fa517893925120168331312ca712324e277bff37a4ead2a04` |
| 根目录 5 个待决文件 | 5 | 379353 | `e1e764f95463ca62d720a26fe689698dc76ba66133327bb32bafb4507c8fd39c` |

`manual_acceptance` 未跟踪文件按目录统计为：根目录 28 个、`mumu/` 28 个、`ocr_stage1/` 203 个、`single_item_confirmation/` 17 个。它们包含截图、PCAP、日志、PID、OCR 证据和操作记录，不能整体忽略或未经新授权推送。

## 停止条件

- C、D、私人样本、根目录内容分叉副本和含本地连接标识的历史任务说明均不纳入 A/B 提交。
- B 只允许精确路径忽略，不删除原始文件；任何分类边界变化都必须重新盘点并同步任务说明、总计划。
