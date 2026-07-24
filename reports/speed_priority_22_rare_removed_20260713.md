# 22速优先路线离线重校准（新概率）

- normal_85 Epic 强化速度概率来自 STOVE 官方表：2/3/4 各 33.223%，5 为 0.332%。
- normal_85 Heroic 强化速度概率来自用户确认规则：1 为 0.332%，2/3/4 各 33.223%，无 5 速。
- rift_85 Epic 使用既有独立异界表；没有套用 normal_85 分布。
- 本报告只用于离线研究，未修改正式跳值表、策略、lambda 或 GUI。

## 执行

- 轨迹：25000 / 件；seed：20260712, 20260713, 20260714, 20260715, 20260716。
- 样本：normal Epic 44，normal Heroic 46，rift Epic 44。
- 概率视图：rare_speed_rolls_removed。旧 `riftslash_saint_pool_22speed_*` 的 0.7% 尾部结果已失效，未被读取或合并。

## 分来源22速产量

| 来源 | 候选 | 22速/100总体力 | 95%区间 |
|---|---|---:|---:|
| normal_epic | speed_current | 0.000915 | [0.000850, 0.000981] |
| normal_epic | speed_epic_d_reference | 0.000000 | [0.000000, 0.000000] |
| normal_epic | speed_hit_chain | 0.001027 | [0.000964, 0.001089] |
| normal_epic | speed_hit_chain_start_3 | 0.000939 | [0.000896, 0.000983] |
| normal_epic | speed_hit_chain_start_4 | 0.000646 | [0.000607, 0.000685] |
| normal_epic | speed_probability_cost | 0.000000 | [0.000000, 0.000000] |
| normal_epic | speed_probability_cost_start_3 | 0.000000 | [0.000000, 0.000000] |
| normal_epic | speed_probability_cost_start_4 | 0.000000 | [0.000000, 0.000000] |
| normal_epic | speed_reachable_22 | 0.002061 | [0.002033, 0.002088] |
| normal_epic | speed_reachable_22_start_3 | 0.002008 | [0.001962, 0.002054] |
| normal_epic | speed_reachable_22_start_4 | 0.001632 | [0.001579, 0.001684] |
| normal_heroic | speed_current | 0.000726 | [0.000685, 0.000767] |
| normal_heroic | speed_heroic_d_reference | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_hit_chain | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_hit_chain_start_3 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_hit_chain_start_4 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_probability_cost | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_probability_cost_start_3 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_probability_cost_start_4 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_reachable_22 | 0.000835 | [0.000788, 0.000881] |
| normal_heroic | speed_reachable_22_start_3 | 0.000836 | [0.000786, 0.000886] |
| normal_heroic | speed_reachable_22_start_4 | 0.000678 | [0.000610, 0.000745] |
| rift_epic | speed_current | 0.002334 | [0.002243, 0.002425] |
| rift_epic | speed_epic_d_reference | 0.000000 | [0.000000, 0.000000] |
| rift_epic | speed_hit_chain | 0.002913 | [0.002688, 0.003139] |
| rift_epic | speed_hit_chain_start_3 | 0.002913 | [0.002688, 0.003139] |
| rift_epic | speed_hit_chain_start_4 | 0.002518 | [0.002268, 0.002768] |
| rift_epic | speed_probability_cost | 0.000000 | [0.000000, 0.000000] |
| rift_epic | speed_probability_cost_start_3 | 0.000000 | [0.000000, 0.000000] |
| rift_epic | speed_probability_cost_start_4 | 0.000000 | [0.000000, 0.000000] |
| rift_epic | speed_reachable_22 | 0.008144 | [0.007927, 0.008362] |
| rift_epic | speed_reachable_22_start_3 | 0.008144 | [0.007927, 0.008362] |
| rift_epic | speed_reachable_22_start_4 | 0.007591 | [0.007324, 0.007859] |

## 联合 normal Epic/Heroic 批次

| 候选 | 22速/100总体力 | 95%区间 |
|---|---:|---:|
| speed_current | 0.001598 | [0.001514, 0.001682] |
| speed_hit_chain | 0.000745 | [0.000699, 0.000790] |
| speed_hit_chain_start_3 | 0.000688 | [0.000656, 0.000720] |
| speed_hit_chain_start_4 | 0.000569 | [0.000535, 0.000604] |
| speed_probability_cost | 0.000000 | [0.000000, 0.000000] |
| speed_probability_cost_start_3 | 0.000000 | [0.000000, 0.000000] |
| speed_probability_cost_start_4 | 0.000000 | [0.000000, 0.000000] |
| speed_reachable_22 | 0.002576 | [0.002478, 0.002675] |
| speed_reachable_22_start_3 | 0.002592 | [0.002481, 0.002702] |
| speed_reachable_22_start_4 | 0.002686 | [0.002508, 0.002863] |

| 相对 speed_current | 成对差 | 95%区间 |
|---|---:|---:|
| speed_hit_chain | -0.000853 | [-0.000962, -0.000744] |
| speed_hit_chain_start_3 | -0.000910 | [-0.001005, -0.000815] |
| speed_hit_chain_start_4 | -0.001029 | [-0.001112, -0.000946] |
| speed_probability_cost | -0.001598 | [-0.001682, -0.001514] |
| speed_probability_cost_start_3 | -0.001598 | [-0.001682, -0.001514] |
| speed_probability_cost_start_4 | -0.001598 | [-0.001682, -0.001514] |
| speed_reachable_22 | 0.000978 | [0.000953, 0.001003] |
| speed_reachable_22_start_3 | 0.000994 | [0.000963, 0.001024] |
| speed_reachable_22_start_4 | 0.001088 | [0.000988, 0.001187] |

## 相对当前的同seed成对差

| 对比 | 22速/100总体力差 | 95%区间 |
|---|---:|---:|
| normal_epic:speed_epic_d_reference-speed_current | -0.000915 | [-0.000981, -0.000850] |
| normal_epic:speed_hit_chain-speed_current | 0.000111 | [0.000012, 0.000211] |
| normal_epic:speed_hit_chain_start_3-speed_current | 0.000024 | [-0.000053, 0.000101] |
| normal_epic:speed_hit_chain_start_4-speed_current | -0.000269 | [-0.000327, -0.000212] |
| normal_epic:speed_probability_cost-speed_current | -0.000915 | [-0.000981, -0.000850] |
| normal_epic:speed_probability_cost_start_3-speed_current | -0.000915 | [-0.000981, -0.000850] |
| normal_epic:speed_probability_cost_start_4-speed_current | -0.000915 | [-0.000981, -0.000850] |
| normal_epic:speed_reachable_22-speed_current | 0.001145 | [0.001095, 0.001195] |
| normal_epic:speed_reachable_22_start_3-speed_current | 0.001093 | [0.001060, 0.001125] |
| normal_epic:speed_reachable_22_start_4-speed_current | 0.000716 | [0.000683, 0.000749] |
| normal_heroic:speed_heroic_d_reference-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_hit_chain-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_hit_chain_start_3-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_hit_chain_start_4-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_probability_cost-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_probability_cost_start_3-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_probability_cost_start_4-speed_current | -0.000726 | [-0.000767, -0.000685] |
| normal_heroic:speed_reachable_22-speed_current | 0.000108 | [0.000102, 0.000114] |
| normal_heroic:speed_reachable_22_start_3-speed_current | 0.000110 | [0.000099, 0.000121] |
| normal_heroic:speed_reachable_22_start_4-speed_current | -0.000048 | [-0.000082, -0.000015] |
| rift_epic:speed_epic_d_reference-speed_current | -0.002334 | [-0.002425, -0.002243] |
| rift_epic:speed_hit_chain-speed_current | 0.000579 | [0.000379, 0.000779] |
| rift_epic:speed_hit_chain_start_3-speed_current | 0.000579 | [0.000379, 0.000779] |
| rift_epic:speed_hit_chain_start_4-speed_current | 0.000184 | [-0.000014, 0.000381] |
| rift_epic:speed_probability_cost-speed_current | -0.002334 | [-0.002425, -0.002243] |
| rift_epic:speed_probability_cost_start_3-speed_current | -0.002334 | [-0.002425, -0.002243] |
| rift_epic:speed_probability_cost_start_4-speed_current | -0.002334 | [-0.002425, -0.002243] |
| rift_epic:speed_reachable_22-speed_current | 0.005810 | [0.005645, 0.005975] |
| rift_epic:speed_reachable_22_start_3-speed_current | 0.005810 | [0.005645, 0.005975] |
| rift_epic:speed_reachable_22_start_4-speed_current | 0.005257 | [0.005065, 0.005449] |

## 限制

- 当前 JSON 摘要保留各节点到达率、停止率、速度命中率、22/23/24/25/27+ 分布、完整资源流和圣女瓶颈；本 Markdown 仅压缩展示主要排序指标。
- 联合 normal Epic/Heroic 总体力与候选排序须在三类独立结论均完成后再做，不在本轮用有限速度价值覆盖正式体系价值。