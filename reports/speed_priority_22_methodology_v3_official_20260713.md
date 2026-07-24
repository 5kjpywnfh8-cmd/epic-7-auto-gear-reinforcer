# 22速优先路线口径修正研究

- normal_85 Epic 强化速度概率来自 STOVE 官方表：2/3/4 各 33.223%，5 为 0.332%。
- normal_85 Heroic 强化速度概率来自用户确认规则：1 为 0.332%，2/3/4 各 33.223%，无 5 速。
- rift_85 Epic 使用既有独立异界表；没有套用 normal_85 分布。
- 本报告只用于离线研究，未修改正式跳值表、策略、lambda 或 GUI。
- 输入仅为已获得的非鞋速度胚子；所有数值均为边际强化口径，不代表副本掉落产量。

## 执行

- 轨迹：25000 / 件；seed：20260712, 20260713, 20260714, 20260715, 20260716。
- 样本：normal Epic 44，normal Heroic 46，rift Epic 44。
- 概率视图：official_stove_epic_user_confirmed_heroic。旧 `riftslash_saint_pool_22speed_*` 的 0.7% 尾部结果已失效，未被读取或合并。

## 条件边际效率

| 来源 | 候选 | 22速/100速度胚子 | 22速/100增量体力 | 95%区间 | 每22速增量体力 | 原生75+ | 转换75+ | 输出60 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| normal_epic | speed_current_exact | 0.094818 | 0.005983 | [0.005577, 0.006388] | 16756.124 | 0.005579 | 0.005737 | 0.009416 |
| normal_epic | speed_epic_d_reference | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_epic | speed_hit_chain_epic2 | 0.096727 | 0.011741 | [0.011007, 0.012474] | 8534.773 | 0.000182 | 0.000200 | 0.000288 |
| normal_epic | speed_probability_cost_epic2 | 0.000091 | 0.000032 | [-0.000057, 0.000121] | 622719.835 | 0.000001 | 0.000001 | 0.000000 |
| normal_epic | speed_reachable_22_epic2 | 0.234727 | 0.005351 | [0.005309, 0.005394] | 18688.089 | 0.002557 | 0.002569 | 0.001965 |
| normal_heroic | speed_current_exact | 0.068000 | 0.003154 | [0.002845, 0.003462] | 31873.076 | 0.000000 | 0.000003 | 0.000162 |
| normal_heroic | speed_heroic_d_reference | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_hit_chain_heroic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_hit_chain_heroic3 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_hit_chain_heroic4 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_probability_cost_heroic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_probability_cost_heroic3 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_probability_cost_heroic4 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| normal_heroic | speed_reachable_22_heroic2 | 0.098000 | 0.002925 | [0.002782, 0.003069] | 34227.041 | 0.000000 | 0.000001 | 0.000056 |
| normal_heroic | speed_reachable_22_heroic3 | 0.097304 | 0.002997 | [0.002841, 0.003154] | 33408.861 | 0.000000 | 0.000001 | 0.000054 |
| normal_heroic | speed_reachable_22_heroic4 | 0.068000 | 0.004204 | [0.003809, 0.004599] | 23898.596 | 0.000000 | 0.000001 | 0.000032 |
| rift_epic | speed_current_exact | 0.235545 | 0.014806 | [0.014253, 0.015359] | 6758.768 | 0.038226 | 0.036546 | 0.013563 |
| rift_epic | speed_epic_d_reference | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| rift_epic | speed_hit_chain_epic2 | 0.271636 | 0.032966 | [0.030461, 0.035472] | 3042.784 | 0.001768 | 0.001861 | 0.000340 |
| rift_epic | speed_probability_cost_epic2 | 0.000000 | 0.000000 | [0.000000, 0.000000] | N/A | 0.000000 | 0.000000 | 0.000000 |
| rift_epic | speed_reachable_22_epic2 | 0.987455 | 0.027244 | [0.026502, 0.027985] | 3671.966 | 0.020574 | 0.019849 | 0.003617 |

## 相对真实当前路线的同seed成对差

| 对比 | 22速/100增量体力差 | 95%区间 | 正式价值差/胚子 | 原生75+差/胚子 | 转换75+差/胚子 | 输出60差/胚子 |
|---|---:|---:|---:|---:|---:|---:|
| normal_epic:speed_epic_d_reference-speed_current_exact | -0.005983 | [-0.006388, -0.005577] | -0.179626 | -0.005579 | -0.005737 | -0.009416 |
| normal_epic:speed_hit_chain_epic2-speed_current_exact | 0.005758 | [0.004855, 0.006661] | -0.164055 | -0.005397 | -0.005537 | -0.009128 |
| normal_epic:speed_probability_cost_epic2-speed_current_exact | -0.005951 | [-0.006347, -0.005554] | -0.179617 | -0.005578 | -0.005736 | -0.009416 |
| normal_epic:speed_reachable_22_epic2-speed_current_exact | -0.000632 | [-0.001029, -0.000235] | -0.106678 | -0.003022 | -0.003168 | -0.007451 |
| normal_heroic:speed_heroic_d_reference-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_hit_chain_heroic2-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_hit_chain_heroic3-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_hit_chain_heroic4-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_probability_cost_heroic2-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_probability_cost_heroic3-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_probability_cost_heroic4-speed_current_exact | -0.003154 | [-0.003462, -0.002845] | -0.029747 | 0.000000 | -0.000003 | -0.000162 |
| normal_heroic:speed_reachable_22_heroic2-speed_current_exact | -0.000228 | [-0.000421, -0.000036] | -0.020067 | 0.000000 | -0.000002 | -0.000106 |
| normal_heroic:speed_reachable_22_heroic3-speed_current_exact | -0.000156 | [-0.000330, 0.000017] | -0.020101 | 0.000000 | -0.000002 | -0.000108 |
| normal_heroic:speed_reachable_22_heroic4-speed_current_exact | 0.001051 | [0.000962, 0.001139] | -0.022295 | 0.000000 | -0.000002 | -0.000130 |
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