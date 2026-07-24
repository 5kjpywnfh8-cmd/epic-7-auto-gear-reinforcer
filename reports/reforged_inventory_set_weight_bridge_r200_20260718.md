# 已重铸库存套装权重绝对成本扩样与旧口径桥接

本报告将旧 `799.2` Epic-only 常量和当前 `85 体力 Epic/Heroic 联合线路`逐层拆开。套装权重只代表库存保留需求，不代表自然掉率；R50 分片与报告保持只读。

## 执行状态

- 新阶段：`r200`；完成分片：`760/760`。
- 旧 799.2 桥接状态：`historical_constant_not_reproduced`。
- 绝对成本区间为按独立 seed/block 聚类的正值约束 bootstrap；下界不会为负。

## 五层桥接（当前正式策略）

| 层级 | 口径 | 体力/百里分 95%区间 | 正式百里分/10万体力 | 裂缝/圣女体力 | cluster ESS | 最大cluster贡献 |
|---|---|---:|---:|---:|---:|---:|
| `published_epic_replay` | 发布 Epic-only 回放（19套等权） | 630.87 [593.41, 675.06] | 158.51 | 0.00/100000.00 | 19.52 | 0.065 |
| `epic_inventory_weighted` | 仅换库存需求权重 | 511.63 [465.88, 562.02] | 195.46 | 0.00/100000.00 | 18.91 | 0.086 |
| `joint_source_epic_value_only` | 加入85体力来源，仅计Epic价值 | 1793.73 [1593.08, 2052.95] | 55.75 | 83552.58/16447.42 | 18.39 | 0.078 |
| `joint_source_all_stop_heroic` | 加入Heroic成本/回收，Heroic全停 | 1793.73 [1593.08, 2052.95] | 55.75 | 83552.58/16447.42 | 18.39 | 0.078 |
| `joint_source_released_heroic` | 完整联合线路，Heroic已发布M1 | 9189.89 [8304.86, 10297.62] | 10.88 | 14324.70/85675.30 | 18.86 | 0.073 |

桥接解释顺序：第一、二层的差异只来自套装需求权重；第二、三层的差异来自把装备获得与圣女补充纳入分母；第三、四、五层的差异来自 Heroic 的联合产出及其全停或 M1 强化流。五层均使用同一批 Epic/Heroic 条件生成路径，22速不折算进正式百里分。

## 候选对照（完整联合线路）

| 套装需求场景 | 策略 | 体力/百里分 95%区间 | 百里分/10万体力 | 稳定状态 |
|---|---|---:|---:|---|
| `uniform_observed_sets` | `current_formal` | 11757.57 [11028.06, 12590.30] | 8.51 | `absolute_cost_stable` |
| `uniform_observed_sets` | `global_12_17` | 11659.64 [10935.53, 12485.57] | 8.58 | `absolute_cost_stable` |
| `uniform_observed_sets` | `output_8_13_tank_10_17` | 11702.75 [10976.13, 12532.23] | 8.54 | `absolute_cost_stable` |
| `uniform_observed_sets` | `output_8_13_tank_12_17` | 11698.36 [10971.95, 12527.43] | 8.55 | `absolute_cost_stable` |
| `reforged_inventory_all` | `current_formal` | 9189.89 [8304.86, 10297.62] | 10.88 | `absolute_cost_unstable` |
| `reforged_inventory_all` | `global_12_17` | 9121.35 [8243.33, 10221.33] | 10.96 | `absolute_cost_unstable` |
| `reforged_inventory_all` | `output_8_13_tank_10_17` | 9150.96 [8270.13, 10254.23] | 10.93 | `absolute_cost_unstable` |
| `reforged_inventory_all` | `output_8_13_tank_12_17` | 9148.05 [8267.53, 10250.97] | 10.93 | `absolute_cost_unstable` |

## 结论状态

- 本轮不冻结候选、不启动或读取 128 件 holdout，也未修改正式策略、DP、资源模型、评分、跳值表、GUI、OCR 或自动化。
- 只有完整联合线路的绝对成本相对半宽不超过 10% 时，才允许把该结果作为可发布常量讨论；候选的成对差异仍须单独按共同随机路径解释。
