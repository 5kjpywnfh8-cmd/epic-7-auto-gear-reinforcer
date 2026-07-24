# 22速优先路线口径修正研究

- normal_85 Epic 强化速度概率来自 STOVE 官方表：2/3/4 各 33.223%，5 为 0.332%。
- normal_85 Heroic 强化速度概率来自用户确认规则：1 为 0.332%，2/3/4 各 33.223%，无 5 速。
- rift_85 Epic 使用既有独立异界表；没有套用 normal_85 分布。
- 本报告只用于离线研究，未修改正式跳值表、策略、lambda 或 GUI。
- 输入仅为已获得的非鞋速度胚子；所有数值均为边际强化口径，不代表副本掉落产量。

## 执行

- 轨迹：25000 / 件；seed：20260712, 20260713, 20260714, 20260715, 20260716。
- 样本：normal Epic 44，normal Heroic 46，rift Epic 44。
- 概率视图：rare_speed_rolls_removed。旧 `riftslash_saint_pool_22speed_*` 的 0.7% 尾部结果已失效，未被读取或合并。

## 条件边际效率

| 来源 | 候选 | 22速/100速度胚子 | 22速/100增量体力 | 95%区间 | 每22速增量体力 | 原生75+ | 转换75+ | 输出60 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| normal_epic | speed_current_exact | 0.092273 | 0.005841 | [0.005414, 0.006267] | 17170.429 | 0.005445 | 0.005590 | 0.009391 |
| normal_epic | speed_epic_d_reference | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_epic | speed_hit_chain_epic2 | 0.095727 | 0.011619 | [0.010935, 0.012304] | 8621.896 | 0.000174 | 0.000194 | 0.000287 |
| normal_epic | speed_probability_cost_epic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_epic | speed_reachable_22_epic2 | 0.229455 | 0.008705 | [0.008588, 0.008822] | 11488.552 | 0.001924 | 0.001938 | 0.001184 |
| normal_heroic | speed_current_exact | 0.068609 | 0.003182 | [0.002854, 0.003510] | 31608.089 | 0.000000 | 0.000003 | 0.000163 |
| normal_heroic | speed_heroic_d_reference | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_hit_chain_heroic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_hit_chain_heroic3 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_hit_chain_heroic4 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_probability_cost_heroic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_probability_cost_heroic3 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_probability_cost_heroic4 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_reachable_22_heroic2 | 0.098957 | 0.002947 | [0.002782, 0.003113] | 33984.300 | 0.000000 | 0.000001 | 0.000056 |
| normal_heroic | speed_reachable_22_heroic3 | 0.098261 | 0.003020 | [0.002839, 0.003201] | 33172.443 | 0.000000 | 0.000001 | 0.000054 |
| normal_heroic | speed_reachable_22_heroic4 | 0.068609 | 0.004231 | [0.003811, 0.004651] | 23761.079 | 0.000000 | 0.000001 | 0.000032 |
| rift_epic | speed_current_exact | 0.235545 | 0.014806 | [0.014253, 0.015359] | 6758.768 | 0.038226 | 0.036546 | 0.013563 |
| rift_epic | speed_epic_d_reference | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| rift_epic | speed_hit_chain_epic2 | 0.271636 | 0.032966 | [0.030461, 0.035472] | 3042.784 | 0.001768 | 0.001861 | 0.000340 |
| rift_epic | speed_probability_cost_epic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| rift_epic | speed_reachable_22_epic2 | 0.987455 | 0.027244 | [0.026502, 0.027985] | 3671.966 | 0.020574 | 0.019849 | 0.003617 |

## 相对真实当前路线的同seed成对差

| 对比 | 22速/100增量体力差 | 95%区间 | 正式价值差/胚子 | 原生75+差/胚子 | 转换75+差/胚子 | 输出60差/胚子 |
|---|---:|---:|---:|---:|---:|---:|
| normal_epic:speed_epic_d_reference-speed_current_exact | -0.005841 | [-0.006267, -0.005414] | -0.177377 | -0.005445 | -0.005590 | -0.009391 |
| normal_epic:speed_hit_chain_epic2-speed_current_exact | 0.005779 | [0.004913, 0.006644] | -0.162112 | -0.005271 | -0.005396 | -0.009104 |
| normal_epic:speed_probability_cost_epic2-speed_current_exact | -0.005841 | [-0.006267, -0.005414] | -0.177377 | -0.005445 | -0.005590 | -0.009391 |
| normal_epic:speed_reachable_22_epic2-speed_current_exact | 0.002865 | [0.002522, 0.003207] | -0.123927 | -0.003521 | -0.003652 | -0.008207 |
| normal_heroic:speed_heroic_d_reference-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_hit_chain_heroic2-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_hit_chain_heroic3-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_hit_chain_heroic4-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_probability_cost_heroic2-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_probability_cost_heroic3-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_probability_cost_heroic4-speed_current_exact | -0.003182 | [-0.003510, -0.002854] | -0.029949 | 0.000000 | -0.000003 | -0.000163 |
| normal_heroic:speed_reachable_22_heroic2-speed_current_exact | -0.000234 | [-0.000419, -0.000050] | -0.020169 | 0.000000 | -0.000002 | -0.000107 |
| normal_heroic:speed_reachable_22_heroic3-speed_current_exact | -0.000162 | [-0.000328, 0.000005] | -0.020204 | 0.000000 | -0.000002 | -0.000109 |
| normal_heroic:speed_reachable_22_heroic4-speed_current_exact | 0.001049 | [0.000955, 0.001143] | -0.022432 | 0.000000 | -0.000002 | -0.000130 |
| rift_epic:speed_epic_d_reference-speed_current_exact | -0.014806 | [-0.015359, -0.014253] | -0.514747 | -0.038226 | -0.036546 | -0.013563 |
| rift_epic:speed_hit_chain_epic2-speed_current_exact | 0.018160 | [0.015828, 0.020492] | -0.467567 | -0.036458 | -0.034685 | -0.013223 |
| rift_epic:speed_probability_cost_epic2-speed_current_exact | -0.014806 | [-0.015359, -0.014253] | -0.514747 | -0.038226 | -0.036546 | -0.013563 |
| rift_epic:speed_reachable_22_epic2-speed_current_exact | 0.012438 | [0.011884, 0.012991] | -0.235983 | -0.017653 | -0.016697 | -0.009945 |

## 品质独立联合组合

- `speed_current_exact`：normal_epic=speed_current_exact, normal_heroic=speed_current_exact。缺少自然初始速度与掉落权重，不得将条件胚子合并为副本产量。
- `current_epic2_reachable_heroic4`：normal_epic=speed_current_exact, normal_heroic=speed_reachable_22_heroic4。缺少自然初始速度与掉落权重，不得将条件胚子合并为副本产量。
- `reachable_epic2_heroic2`：normal_epic=speed_reachable_22_epic2, normal_heroic=speed_reachable_22_heroic2。缺少自然初始速度与掉落权重，不得将条件胚子合并为副本产量。
- `reachable_epic2_heroic3`：normal_epic=speed_reachable_22_epic2, normal_heroic=speed_reachable_22_heroic3。缺少自然初始速度与掉落权重，不得将条件胚子合并为副本产量。
- `reachable_epic2_heroic4`：normal_epic=speed_reachable_22_epic2, normal_heroic=speed_reachable_22_heroic4。缺少自然初始速度与掉落权重，不得将条件胚子合并为副本产量。

## 完整装备池效率

- 状态：`not_estimated`。输入已筛选为已获得的速度胚子，且缺少自然初始速度/掉落权重与固定非速度分支。

## 限制

- JSON保留各节点到达率、停止率、速度命中率、22/23/24/25/27+分布、正式价值、原生75+、转换75+、输出60和完整资源流。
- 未取得自然初始速度与掉落权重前，不得将条件胚子指标称为每100总体力副本产量，也不得合并为联合批次排名。