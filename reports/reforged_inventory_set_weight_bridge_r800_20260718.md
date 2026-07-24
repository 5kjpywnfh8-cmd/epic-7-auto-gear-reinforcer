# 已重铸库存套装权重绝对成本扩样与旧口径桥接

本报告将旧 `799.2` Epic-only 常量和当前 `85 体力 Epic/Heroic 联合线路`逐层拆开。套装权重只代表库存保留需求，不代表自然掉率；R50 分片与报告保持只读。

## 执行状态

- 新阶段：`r800`；完成分片：`760/760`。
- 旧 799.2 桥接状态：`historical_constant_not_reproduced`。
- 绝对成本区间为按独立 seed/block 聚类的正值约束 bootstrap；下界不会为负。

## 五层桥接（当前正式策略）

| 层级 | 口径 | 体力/百里分 95%区间 | 正式百里分/10万体力 | 裂缝/圣女体力 | cluster ESS | 最大cluster贡献 |
|---|---|---:|---:|---:|---:|---:|
| `published_epic_replay` | 发布 Epic-only 回放（19套等权） | 615.91 [592.63, 643.10] | 162.36 | 0.00/100000.00 | 19.80 | 0.058 |
| `epic_inventory_weighted` | 仅换库存需求权重 | 480.71 [454.44, 510.33] | 208.03 | 0.00/100000.00 | 19.60 | 0.066 |
| `joint_source_epic_value_only` | 加入85体力来源，仅计Epic价值 | 1659.35 [1529.39, 1804.87] | 60.26 | 83421.39/16578.61 | 19.29 | 0.073 |
| `joint_source_all_stop_heroic` | 加入Heroic成本/回收，Heroic全停 | 1659.35 [1529.39, 1804.87] | 60.26 | 83421.39/16578.61 | 19.29 | 0.073 |
| `joint_source_released_heroic` | 完整联合线路，Heroic已发布M1 | 8507.19 [7910.44, 9131.16] | 11.75 | 14327.58/85672.42 | 19.47 | 0.068 |

### Terminal Value Definition Diagnostic

Inventory-weighted historical terminal-score numerator: `480.71` stamina/Baili.  With the same historical resource denominator but the current formal-value numerator: `579.48` stamina/Baili (95% [535.72, 628.06]).

桥接解释顺序：第一、二层的差异只来自套装需求权重；第二、三层的差异来自把装备获得与圣女补充纳入分母；第三、四、五层的差异来自 Heroic 的联合产出及其全停或 M1 强化流。五层均使用同一批 Epic/Heroic 条件生成路径，22速不折算进正式百里分。

## 候选对照（完整联合线路）

| 套装需求场景 | 策略 | 体力/百里分 95%区间 | 百里分/10万体力 | 稳定状态 |
|---|---|---:|---:|---|
| `uniform_observed_sets` | `current_formal` | 11557.98 [11006.82, 12206.23] | 8.65 | paired delta/100=0.000000 [0.000000, 0.000000]; `absolute_cost_stable` |
| `uniform_observed_sets` | `global_12_17` | 11461.84 [10915.44, 12105.03] | 8.72 | paired delta/100=0.000073 [0.000069, 0.000077]; `absolute_cost_stable` |
| `uniform_observed_sets` | `output_8_13_tank_10_17` | 11504.23 [10955.52, 12149.70] | 8.69 | paired delta/100=0.000040 [0.000038, 0.000043]; `absolute_cost_stable` |
| `uniform_observed_sets` | `output_8_13_tank_12_17` | 11499.92 [10951.35, 12145.14] | 8.70 | paired delta/100=0.000044 [0.000041, 0.000046]; `absolute_cost_stable` |
| `reforged_inventory_all` | `current_formal` | 8507.19 [7910.44, 9131.16] | 11.75 | paired delta/100=0.000000 [0.000000, 0.000000]; `absolute_cost_stable` |
| `reforged_inventory_all` | `global_12_17` | 8443.86 [7851.71, 9063.03] | 11.84 | paired delta/100=0.000088 [0.000082, 0.000094]; `absolute_cost_stable` |
| `reforged_inventory_all` | `output_8_13_tank_10_17` | 8471.51 [7877.28, 9092.78] | 11.80 | paired delta/100=0.000049 [0.000046, 0.000053]; `absolute_cost_stable` |
| `reforged_inventory_all` | `output_8_13_tank_12_17` | 8468.66 [7874.59, 9089.77] | 11.81 | paired delta/100=0.000053 [0.000050, 0.000057]; `absolute_cost_stable` |

## 结论状态

- 本轮不冻结候选、不启动或读取 128 件 holdout，也未修改正式策略、DP、资源模型、评分、跳值表、GUI、OCR 或自动化。
- 只有完整联合线路的绝对成本相对半宽不超过 10% 时，才允许把该结果作为可发布常量讨论；候选的成对差异仍须单独按共同随机路径解释。
