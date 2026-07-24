# 已重铸库存套装权重绝对成本扩样与旧口径桥接

本报告将旧 `799.2` Epic-only 常量和当前 `85 体力 Epic/Heroic 联合线路`逐层拆开。套装权重只代表库存保留需求，不代表自然掉率；R50 分片与报告保持只读。

## 执行状态

- 新阶段：`r400`；完成分片：`760/760`。
- 旧 799.2 桥接状态：`historical_constant_not_reproduced`。
- 绝对成本区间为按独立 seed/block 聚类的正值约束 bootstrap；下界不会为负。

## 五层桥接（当前正式策略）

| 层级 | 口径 | 体力/百里分 95%区间 | 正式百里分/10万体力 | 裂缝/圣女体力 | cluster ESS | 最大cluster贡献 |
|---|---|---:|---:|---:|---:|---:|
| `published_epic_replay` | 发布 Epic-only 回放（19套等权） | 612.60 [586.55, 642.11] | 163.24 | 0.00/100000.00 | 19.77 | 0.058 |
| `epic_inventory_weighted` | 仅换库存需求权重 | 488.26 [461.68, 519.06] | 204.81 | 0.00/100000.00 | 19.57 | 0.066 |
| `joint_source_epic_value_only` | 加入85体力来源，仅计Epic价值 | 1695.71 [1565.19, 1843.75] | 58.97 | 83501.95/16498.05 | 19.31 | 0.072 |
| `joint_source_all_stop_heroic` | 加入Heroic成本/回收，Heroic全停 | 1695.71 [1565.19, 1843.75] | 58.97 | 83501.95/16498.05 | 19.31 | 0.072 |
| `joint_source_released_heroic` | 完整联合线路，Heroic已发布M1 | 8564.05 [7861.09, 9312.08] | 11.68 | 14327.51/85672.49 | 19.30 | 0.070 |

### Terminal Value Definition Diagnostic

Inventory-weighted historical terminal-score numerator: `488.26` stamina/Baili.  With the same historical resource denominator but the current formal-value numerator: `591.20` stamina/Baili (95% [548.30, 639.86]).

桥接解释顺序：第一、二层的差异只来自套装需求权重；第二、三层的差异来自把装备获得与圣女补充纳入分母；第三、四、五层的差异来自 Heroic 的联合产出及其全停或 M1 强化流。五层均使用同一批 Epic/Heroic 条件生成路径，22速不折算进正式百里分。

## 候选对照（完整联合线路）

| 套装需求场景 | 策略 | 体力/百里分 95%区间 | 百里分/10万体力 | 稳定状态 |
|---|---|---:|---:|---|
| `uniform_observed_sets` | `current_formal` | 11559.98 [10918.81, 12262.21] | 8.65 | paired delta/100=0.000000 [0.000000, 0.000000]; `absolute_cost_stable` |
| `uniform_observed_sets` | `global_12_17` | 11463.68 [10828.44, 12160.10] | 8.72 | paired delta/100=0.000073 [0.000068, 0.000077]; `absolute_cost_stable` |
| `uniform_observed_sets` | `output_8_13_tank_10_17` | 11506.08 [10867.97, 12205.16] | 8.69 | paired delta/100=0.000041 [0.000038, 0.000043]; `absolute_cost_stable` |
| `uniform_observed_sets` | `output_8_13_tank_12_17` | 11501.82 [10863.80, 12200.66] | 8.69 | paired delta/100=0.000044 [0.000041, 0.000047]; `absolute_cost_stable` |
| `reforged_inventory_all` | `current_formal` | 8564.05 [7861.09, 9312.08] | 11.68 | paired delta/100=0.000000 [0.000000, 0.000000]; `absolute_cost_stable` |
| `reforged_inventory_all` | `global_12_17` | 8500.05 [7803.53, 9242.05] | 11.76 | paired delta/100=0.000088 [0.000081, 0.000095]; `absolute_cost_stable` |
| `reforged_inventory_all` | `output_8_13_tank_10_17` | 8527.95 [7828.25, 9272.37] | 11.73 | paired delta/100=0.000049 [0.000045, 0.000053]; `absolute_cost_stable` |
| `reforged_inventory_all` | `output_8_13_tank_12_17` | 8525.08 [7825.75, 9269.25] | 11.73 | paired delta/100=0.000053 [0.000049, 0.000058]; `absolute_cost_stable` |

## 结论状态

- 本轮不冻结候选、不启动或读取 128 件 holdout，也未修改正式策略、DP、资源模型、评分、跳值表、GUI、OCR 或自动化。
- 只有完整联合线路的绝对成本相对半宽不超过 10% 时，才允许把该结果作为可发布常量讨论；候选的成对差异仍须单独按共同随机路径解释。
