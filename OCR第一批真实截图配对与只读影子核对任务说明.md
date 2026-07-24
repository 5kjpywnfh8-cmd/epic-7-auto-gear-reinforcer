# OCR 第一批真实截图配对与只读影子核对任务说明

> 状态（2026-07-21）：`ready_for_pairing`。本文件是本轮唯一权威来源。用户已提供 14 张真实游戏截图；本轮只建立可复查语料、匹配同期装备真值并完成只读核对准备，不代表已经具备 OCR 准确率，也不授权任何游戏操作。

## 目标

1. 将临时目录中的 14 张原始 PNG 持久化到项目内匿名批次目录，保留原始字节和 SHA-256。
2. 对截图按实际装备和页面类型分组，识别重复截图，但不删除任何原始输入。
3. 只读匹配 `D:\VScode\E7-tools\gear_read\gear_fribbels_20260719_221033.json` 中的同件装备，生成 `screenshot_id -> instanceId -> reference_file` manifest。
4. 为后续 OCR 引擎建立字段级人工真值和区域核对材料；当前没有 OCR 引擎时，不得报告 OCR 准确率。

## 输入

### 截图

- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-c9b93c1d-6850-4d58-9834-996cef87c18a.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-7fd96234-5931-4c35-9695-fabeabdef968.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-1b97f6d3-0e15-488e-82cb-9c890f03561e.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-63485f39-d6f8-4034-8964-268402ed1f31.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-646df2c3-1447-4323-9870-377861579fd8.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-7183b54f-96f1-4780-90e1-3f2afac6b48e.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-68d68b92-71d7-464a-9a0f-17bafdc8f045.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-81a5eb57-48be-4dda-a70d-4ac71aaa1929.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-8a81b0be-7320-468d-955e-26882ee7b30b.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-a7f9c6a6-3843-42ce-a23d-db6ec8f9526b.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-fd131bc1-93d3-43de-b3a1-176d770f4562.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-c3500174-f8df-4d45-bb22-2c3e9ea797f0.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-141be28f-4765-48af-9801-a05151b8e4f6.png`
- `C:\Users\orangine\AppData\Local\Temp\codex-clipboard-3aa05b33-7cb7-4c1d-89d4-2f11a74a67d7.png`

### 结构化参考

- 只读源：`D:\VScode\E7-tools\gear_read\gear_fribbels_20260719_221033.json`。
- 必须记录源文件 SHA-256、字节数和修改时间。
- 只允许把成功匹配装备的最小必要字段写入项目 `references/`；不得复制英雄、账号资源、整份原始响应或无关装备。

## 权威匹配口径

- 优先使用截图可见的套装、部位、品质、等级、强化等级、主属性、副属性名称与数值做联合匹配。
- `instanceId` 只能来自 Fribbels JSON，不能从截图推测或自行生成。
- 只有唯一候选且所有截图可见字段一致时标记 `matched`。
- 多个候选无法排除时标记 `ambiguous`；没有候选时标记 `unmatched`；参考快照早于截图而导致强化等级或数值变化时标记 `stale_reference_possible`，不得强配。
- 同一装备的详情页、强化页、副能力转换页可以共用同一 `instanceId`，但每张截图必须保留独立 SHA-256、页面类型和可见字段。
- 字节完全相同的截图标记 `exact_duplicate_of`；画面不同但同一装备标记 `same_gear_group`，不得删除原图。
- 副能力转换页面只记录当前可见装备值和页面类型；未确认转换完成时，不得当作转换后结果。

## 执行步骤

1. 创建 `manual_acceptance/ocr_stage1/batch_001/screenshots/` 与 `references/`。
2. 以 `ocr-0001.png` 至 `ocr-0014.png` 持久化原始字节，并生成输入文件名、持久化文件名、SHA-256、尺寸和页面类型清单。
3. 解析 Fribbels JSON 的装备数组和 `raw` 字段，建立规范化匹配索引；不得修改源 JSON。
4. 对每张截图人工读取可见字段，并按本文件口径匹配。匹配过程必须保留候选数与拒绝原因。
5. 生成最小化 `references/matched_gears.json`、`manifest.json` 和人类可读报告。
6. 使用现有 `ocr_capture` 读取持久化图片，核对 SHA-256 与 `click_performed=false`。没有真实 OCR 引擎时只生成“语料已配对/未配对”的状态，不伪造识别置信度或准确率。
7. 如为完成稳定、可复跑的配对需要新增小型只读工具或测试，可以实现；代码任务由 `gpt-5.6-terra + high` 子 agent 执行。

## 产物

- `manual_acceptance/ocr_stage1/batch_001/screenshots/ocr-0001.png` 至 `ocr-0014.png`
- `manual_acceptance/ocr_stage1/batch_001/references/matched_gears.json`
- `manual_acceptance/ocr_stage1/batch_001/manifest.json`
- `reports/ocr_stage1_batch_001_pairing_20260721.md`
- 如新增可复跑工具或测试，放在现有 `tools/`、`tests/` 目录，并在报告中链接。
- 完成后回写本任务说明、`OCR自动强化实施路线与第一阶段只读识别任务说明.md`、`强化策略V1收口与GUI延期任务说明.md` 和 `e7-gear-enhance-plan.md`。

## 禁止修改项

- 不修改正式策略、DP、评分、资源模型、跳值表、转换规则或 `next_check_at`。
- 不修改 GUI 业务逻辑，不安装 OCR/Airtest/ADB 新依赖，不打开或控制模拟器。
- 不点击、不强化、不出售、不转换装备，不消耗游戏资源。
- 不把人工目读字段冒充 OCR 输出，不以本批截图反向调整策略门槛。

## 验证要求

- 14 个输入与 14 个持久化文件 SHA-256 逐一相同。
- manifest 中每张截图恰有一条记录，状态只能为 `matched`、`ambiguous` 或 `unmatched`；可附加 `stale_reference_possible` 原因。
- 每个 `matched` 记录的所有可见字段与最小参考记录一致，且 `instanceId` 在源 JSON 中唯一存在。
- 最小参考文件不包含无关账号数据。
- `ocr_capture` 对全部持久化图片报告 `click_performed=false`，哈希与 manifest 一致。
- 新增代码时运行相应定向测试与语法检查；无代码变更时至少校验 JSON 可解析、文件计数、哈希和 `git diff --check`。

## 停止条件

- 任一源文件缺失或无法读取时停止，并记录缺失项。
- Fribbels 快照不能唯一匹配时保留截图并标记，不请求用猜测补齐。
- 本批完成标准是“持久化、分组、真值匹配与可复查报告完成”；不要求也不得声称 OCR 引擎准确率通过。

## 完成记录（2026-07-21）

- 实际执行模型：`gpt-5.6-terra + high`。未安装依赖、联网、ADB/Airtest、启动模拟器、点击或消耗游戏资源。
- 14 张输入已持久化至 `manual_acceptance/ocr_stage1/batch_001/screenshots/`；每张 SHA-256、尺寸、页面类型、同装备组和重复关系均写入 [manifest.json](manual_acceptance/ocr_stage1/batch_001/manifest.json)。`ocr-0006=ocr-0003`、`ocr-0008=ocr-0007` 为字节完全重复，原图均保留。
- 八个装备组中，`ocr-0009/ocr-0010` 唯一匹配同期 Fribbels `instanceId=2565468393`；`ocr-0010` 是未确认完成的副能力转换选择页，仅记录当时可见值。其余十二张在 2026-07-19 参考快照中均无完整候选，状态为 `unmatched` 且原因 `stale_reference_possible`，没有强配或猜测。
- 最小参考文件：[matched_gears.json](manual_acceptance/ocr_stage1/batch_001/references/matched_gears.json) 只含该一件装备的必要字段，不含 `raw`、英雄、账号资源或整份原始响应。人类报告：[ocr_stage1_batch_001_pairing_20260721.md](reports/ocr_stage1_batch_001_pairing_20260721.md)。
- 可复跑工具：[pair_ocr_stage1_batch.py](tools/pair_ocr_stage1_batch.py)；回归：[test_pair_ocr_stage1_batch.py](tests/test_pair_ocr_stage1_batch.py)。配对器只读图片/参考 JSON，并经 `ocr_capture` 复核 `click_performed=false`。
- 验证：定向 8 项、语法检查、14 条 JSON/哈希/无点击/最小参考检查通过。当前状态：`paired_reference_waiting_for_ocr_engine`；本批没有 OCR 原文、置信度或准确率，也未产生建议对拍结论。下一步需另建任务接入 OCR 引擎后，对同件配对语料做只读字段级影子核对。

## 最新快照复配覆盖（2026-07-21）

- 本文使用的旧 2026-07-19 快照结果已由[最新同账号快照复配任务](OCR第一批真实截图与最新同账号快照复配及影子验证任务说明.md)覆盖。当前 manifest 与最小参考使用 2026-07-21 同账号快照。
- 最新结果仍只匹配 `ocr-0009/0010 -> 2565468393`，两张属于同一装备；当前应以 `pairing_insufficient_for_ocr` 为准，不得把本节的旧状态解释为可执行 OCR 影子验证。
