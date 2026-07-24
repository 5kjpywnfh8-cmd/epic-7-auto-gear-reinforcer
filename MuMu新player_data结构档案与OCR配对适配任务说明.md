# MuMu 新 player_data 结构档案与 OCR 配对适配任务说明

## 目标

让项目只读接收新读取器生成的 `epic7_tools.player_data` schema 1.2，在不修改原始文件的前提下导入真实 `+0` 档案，并用同批原始 `raw` 证据重新配对 batch 002 的仓库详情截图 `ocr-0006`。

## 范围

- 为真实 `+0` 档案入口增加新标准 `player_data.json` 的严格验证与转换。
- 新增或扩展 batch 002 只读配对工具，支持 `warehouse_detail`、强化等级 `+13 -> +12` 阶梯匹配及同批 `raw` 完整性校验。
- 增加最小定向回归测试。
- 运行本轮真实档案导入和 `ocr-0006` 配对。

## 禁止修改项

- 不修改正式策略、DP、资源模型、评分、跳值、GUI、OCR 自动点击、Airtest、自动化或 Holdout。
- 不强化、出售、转换装备，不消耗游戏资源。
- 不修改外部 `player_data.json`、`reader_result.json`、PCAP 或 Fribbels 原始响应。
- 不把缺少唯一候选的截图强配，不猜测 `instanceId`。
- 不扩大 batch 001 历史语料或混合 `warehouse_detail` 与 `backpack_detail` 统计。

## 输入与权威口径

- 标准快照：`D:\VScode\Epic-7-tools.v1.2\data\players\mumu_live\current\player_data.json`。
- 标准快照 SHA-256：`FBC7C69160356C1679473D6A3FC4E38ED87F15A1A4ED0DAE29C20A19DD9D821E`，字节数 `2,589,289`。
- 读取时间：`2026-07-21T16:06:56Z`，本地批次 `20260722_000656`。
- 同批原始证据：`imports/20260722_000656/mumu_capture.pcap` 与 `fribbels_raw_response.json`。
- 同批不可变证据：`snapshots/20260722_000656/player_data.json` 与 `reader_result.json`。
- 标准快照装备 `2668`、英雄 `387`；实例 ID `2668/2668` 唯一。标准 `items` 为规范化字段；同批 `reader_result.data.items` 的 `raw` 为 `2668/2668` 完整。
- 已确认新读取器把全部 `enhance` 错写为 `0`；外部目录因当前沙箱写权限无法由子 agent 修复。项目适配不得信任该字段，必须从同批不可变 `raw.op` 与品质推导强化节点。
- 强化节点推导固定为：品质最大事件数 Normal/Good/Rare/Heroic/Epic=`5/6/7/8/9`，初始偏移=`0/1/2/3/4`，`enhance=max((min(len(op)-1,max_count)-offset)*3,0)`。该公式只生成 `0/3/6/9/12/15` 节点，游戏 `+13/+14` 归一到 `+12`。
- 截图：`manual_acceptance/ocr_stage1/batch_002/screenshots/ocr-0006.png`，SHA-256 `a3db58cc9c2f949771e63b655a70aa91b426803166083597c404b790038a2156`，`page_type=warehouse_detail`。
- 截图可见字段与匹配规则以 `manual_acceptance/ocr_stage1/batch_002/manifest.json` 为准；只允许强化等级向下归一到三的倍数，其他字段完全一致。

## 执行步骤

1. 补失败测试：新 schema 验证、数量/身份/raw 证据错配拒绝、raw 强化节点推导、`+13 -> +12`、其他字段不一致拒绝、唯一/歧义/无候选三态。
2. 最小修改真实档案 CLI 的输入适配：复制标准 items，以同批 raw 推导值覆盖错误的 `enhance=0`，不得原地修改输入；不得放宽旧 Holdout 写入状态或修改冻结文件。
3. 实现 batch 002 只读配对器；新 schema 缺少内嵌 `raw` 时，必须校验同批 `reader_result.data.items` 的身份集合和 `raw` 完整性。
4. 运行定向测试和语法检查。
5. 只在验证通过后导入真实 `+0` 档案，并运行 `ocr-0006` 配对。
6. 更新 manifest、最小参考和人类报告；无唯一候选时保持 `unmatched`。
7. 同步本说明、MuMu/OCR 任务说明和总计划，运行 `git diff --check`。

## 执行分工

- `gpt-5.6-terra + high` 子 agent 仅实施步骤 1--4 的代码、测试和语法验证，不运行真实档案导入，不改 manifest、报告、任务说明或总计划。
- 主 agent 审阅代码后执行步骤 5--7，负责真实数据导入、实际配对、报告与全部 Markdown 同步。

## 产物

- 新 schema 输入适配代码与测试。
- batch 002 可复跑只读配对工具与测试。
- 更新后的 `manual_acceptance/ocr_stage1/batch_002/manifest.json`。
- 必要时生成 batch 002 最小参考和人类可读报告。
- 真实 `+0` 档案导入统计。

## 验证要求

- 新 schema 必须验证 `schema/schema_version/source/counts/completeness/items`、非空唯一实例 ID 和同批原始 `raw` 证据；强化节点只能从 raw 公式推导，不能使用主属性数值猜测。
- 配对不得只依赖强化等级；套装、部位、品质、等级、主属性和全部副属性必须一致。
- 原截图 SHA-256 不变，`click_performed=false`。
- Holdout 文件内容与状态不得变化。
- 定向测试、语法检查和 `git diff --check` 必须通过；全量测试仅在代码影响范围需要时运行并报告真实退出码。

## 停止条件

- 同批 `reader_result.json` 缺失、身份集合不一致或 `raw` 不完整时停止，不导入、不配对。
- 任何需要修改外部数据、安装依赖、游戏资源操作或扩大策略范围的情况停止并报告。
- 无唯一候选不是实现失败，必须以 `unmatched` 或 `ambiguous` 正常收口。

## 当前状态

`raw_evidence_bridge_authorized_in_progress`：外部读取器源修复因写权限阻断，改由项目内严格 raw 证据桥接；等待适配补强、测试、档案导入和 batch 002 重新配对。

## 外部读取器修复后的状态（2026-07-22）

- 外部读取器已由其他任务修复强化等级推导，并用同一 PCAP 离线生成批次 `20260722_011424`；标准 `player_data.json` 不再全为 `enhance=0`，兼容 `gear_fribbels.json` 也已生成。
- 项目内 raw 适配保留为严格兼容校验，不再承担当前数据的纠错主路径。定向回归覆盖 Epic/Heroic `+0/+3/+6/+9/+12/+15` 节点以及全零标准字段由非零 raw 证据恢复。
- 最新仓库配对预演仍无候选，且用户决定暂停仓库、优先背包；本任务状态改为 `adapter_validated_warehouse_pairing_paused`。真实档案正式导入与 batch 002 manifest 写入本轮均未执行。
