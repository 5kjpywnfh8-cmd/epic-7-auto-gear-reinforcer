# 自动预算与硬上限离线规划器验证报告

- 验证日期：`2026-07-25`
- 实际模型：`gpt-5.6-terra`
- Reasoning effort：`high`
- 规则版本：`offline_budget_planner/v1`
- 范围：纯 Python 离线整数规划；未读取私人数据，未接触 GUI、OCR、ADB、MuMu 或游戏资源。
- 操作授权：`false`。本报告不构成材料选择、资源消耗或点击授权。

## 可证明输入

- 普通材料：粉末 `100` 基础经验、`1600` 金币；下级强化石 `1500` 基础经验、`14400` 金币。
- 节点需求：仅聚合已跟踪 `RED_LEVEL_EXP` / `PURPLE_LEVEL_EXP` 的标准相邻节点。
- 成功计划按基础经验保证足额，不把 Good/Great、宠物加成、期望值或分数材料当作实际执行规则。

## 相邻节点验证

| 材料池 | 节点 | 结果 | 说明 |
|---|---|---|---|
| common | +0 -> +3 | success | 需求 1969，计划金币 22400 |
| common | +3 -> +6 | success | 需求 4725，计划金币 48000 |
| common | +6 -> +9 | success | 需求 11025，计划金币 110400 |
| common | +9 -> +12 | success | 需求 22145，计划金币 216000 |
| common | +12 -> +15 | success | 需求 42787，计划金币 416000 |
| accessory | 标准相邻节点 | fail closed | `unsupported_material` |
| accessory | 标准相邻节点 | fail closed | `unsupported_material` |
| accessory | 标准相邻节点 | fail closed | `unsupported_material` |
| accessory | 标准相邻节点 | fail closed | `unsupported_material` |
| accessory | 标准相邻节点 | fail closed | `unsupported_material` |

## 五段有界矩阵

- 覆盖案例数：`53`；全局唯一完整请求数：`40`；重复请求案例数：`13`。
- 原始边界标签候选：`56`；本地 alias/duplicate：`3`（不计入覆盖案例）。
- 覆盖结果：成功 `28`；fail closed `25`；违规案例 `0`。
- 全局唯一请求结果：成功 `15`；fail closed `25`；违规请求 `0`。
- 结果摘要 SHA-256：`6aebb1a94c0e8d66bbfded5d9e9b1a0e06dd8a7f90d430d5b5d1619cdd5194d0`。
- 覆盖节点：`+3/+6/+9/+12/+15`；材料：`powder`、`lower_enhance_stone`；边界值：`0`、`计划值-1`、`计划值`、`计划值+1`（非负化）。
- 边界值按实际非负整数去重；重复标签作为 `aliases` 写入 JSON 的 `boundary_catalog`，不会重复执行或计入覆盖案例，也不计为全局唯一请求。

| 覆盖维度 | 覆盖案例 | 成功 | fail closed | 违规案例 | 违规项 |
|---|---:|---:|---:|---:|---:|
| cumulative_material_hard_limit | 8 | 4 | 4 | 0 | 0 |
| inventory_material | 8 | 4 | 4 | 0 | 0 |
| segment_material_hard_limit | 37 | 20 | 17 | 0 | 0 |

- 覆盖维度合计：五段分段材料上限 `37`；累计材料上限 `8`；材料库存 `8`。
- 分段/累计金币不足仍由定向测试覆盖；覆盖案例和全局唯一请求均是有界证据，不是无界证明。

## 已验证不变量

- 每个计为成功的矩阵结果都必须恰好包含五段，路线严格为 `0->3->6->9->12->15`，且分段端点唯一。
- 每个计为成功的矩阵结果中，结果材料池与请求一致，所有材料容器键集合精确匹配允许材料，且每种材料和金币均未超过库存、分段硬上限及累计硬上限；分段汇总必须等于累计结果。
- 材料组合只来自允许集合且属于正确材料池。
- 目标排序固定为：最小金币、最小基础经验溢出、最少材料数、用户材料优先级。
- 同一请求的规范化 JSON 字节级稳定。
- 上级强化石、跨池材料、未发布饰品离散规则、库存/硬上限/预览不一致均 fail closed。
- 只有完整分段与完整累计硬上限同时提供并通过时，结果模式才为 `validated_against_hard_limits`。

## 阻断与风险

- 饰品材料的真实离散经验和金币常量未在公开可复跑输入中得到证明，因此该材料池只能拒绝，不能生成执行计划。
- 上级强化石没有已发布离散模型，任何允许请求仍返回 `unsupported_material`。
- 离线预算器不验证实时页面、真实库存或实际消耗，也不实现点击前拦截、状态机或节点后新鲜快照。
