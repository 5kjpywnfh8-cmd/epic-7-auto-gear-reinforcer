# 22速优先路线离线重校准（新概率）

- normal_85 Epic 强化速度概率来自 STOVE 官方表：2/3/4 各 33.223%，5 为 0.332%。
- normal_85 Heroic 强化速度概率来自用户确认规则：1 为 0.332%，2/3/4 各 33.223%，无 5 速。
- rift_85 Epic 使用既有独立异界表；没有套用 normal_85 分布。
- 本报告只用于离线研究，未修改正式跳值表、策略、lambda 或 GUI。

## 执行

- 轨迹：25000 / 件；seed：20260712, 20260713, 20260714, 20260715, 20260716。
- 样本：normal Epic 44，normal Heroic 46，rift Epic 44。
- 概率视图：official_stove_epic_user_confirmed_heroic。旧 `riftslash_saint_pool_22speed_*` 的 0.7% 尾部结果已失效，未被读取或合并。

## 分来源22速产量

| 来源 | 候选 | 22速/100总体力 | 95%区间 |
|---|---|---:|---:|
| normal_epic | speed_current | 0.000940 | [0.000878, 0.001002] |
| normal_epic | speed_epic_d_reference | 0.000000 | [0.000000, 0.000000] |
| normal_epic | speed_hit_chain | 0.001037 | [0.000971, 0.001104] |
| normal_epic | speed_hit_chain_start_3 | 0.000949 | [0.000905, 0.000994] |
| normal_epic | speed_hit_chain_start_4 | 0.000652 | [0.000619, 0.000685] |
| normal_epic | speed_probability_cost | 0.000001 | [-0.000002, 0.000004] |
| normal_epic | speed_probability_cost_start_3 | 0.000001 | [-0.000002, 0.000004] |
| normal_epic | speed_probability_cost_start_4 | 0.000001 | [-0.000002, 0.000004] |
| normal_epic | speed_reachable_22 | 0.001822 | [0.001809, 0.001834] |
| normal_epic | speed_reachable_22_start_3 | 0.001793 | [0.001768, 0.001818] |
| normal_epic | speed_reachable_22_start_4 | 0.001515 | [0.001463, 0.001566] |
| normal_heroic | speed_current | 0.000719 | [0.000683, 0.000755] |
| normal_heroic | speed_heroic_d_reference | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_hit_chain | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_hit_chain_start_3 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_hit_chain_start_4 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_probability_cost | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_probability_cost_start_3 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_probability_cost_start_4 | 0.000000 | [0.000000, 0.000000] |
| normal_heroic | speed_reachable_22 | 0.000827 | [0.000786, 0.000868] |
| normal_heroic | speed_reachable_22_start_3 | 0.000828 | [0.000785, 0.000872] |
| normal_heroic | speed_reachable_22_start_4 | 0.000672 | [0.000609, 0.000736] |
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
| speed_current | 0.001595 | [0.001523, 0.001666] |
| speed_hit_chain | 0.000753 | [0.000704, 0.000801] |
| speed_hit_chain_start_3 | 0.000695 | [0.000662, 0.000728] |
| speed_hit_chain_start_4 | 0.000575 | [0.000545, 0.000604] |
| speed_probability_cost | 0.000001 | [-0.000002, 0.000004] |
| speed_probability_cost_start_3 | 0.000001 | [-0.000002, 0.000004] |
| speed_probability_cost_start_4 | 0.000001 | [-0.000002, 0.000004] |
| speed_reachable_22 | 0.002401 | [0.002332, 0.002471] |
| speed_reachable_22_start_3 | 0.002428 | [0.002348, 0.002508] |
| speed_reachable_22_start_4 | 0.002533 | [0.002386, 0.002679] |

| 相对 speed_current | 成对差 | 95%区间 |
|---|---:|---:|
| speed_hit_chain | -0.000842 | [-0.000946, -0.000738] |
| speed_hit_chain_start_3 | -0.000899 | [-0.000989, -0.000810] |
| speed_hit_chain_start_4 | -0.001020 | [-0.001096, -0.000944] |
| speed_probability_cost | -0.001594 | [-0.001667, -0.001521] |
| speed_probability_cost_start_3 | -0.001594 | [-0.001667, -0.001521] |
| speed_probability_cost_start_4 | -0.001594 | [-0.001667, -0.001521] |
| speed_reachable_22 | 0.000807 | [0.000784, 0.000829] |
| speed_reachable_22_start_3 | 0.000834 | [0.000814, 0.000853] |
| speed_reachable_22_start_4 | 0.000938 | [0.000852, 0.001024] |

## 相对当前的同seed成对差

| 对比 | 22速/100总体力差 | 95%区间 |
|---|---:|---:|
| normal_epic:speed_epic_d_reference-speed_current | -0.000940 | [-0.001002, -0.000878] |
| normal_epic:speed_hit_chain-speed_current | 0.000097 | [-0.000004, 0.000199] |
| normal_epic:speed_hit_chain_start_3-speed_current | 0.000009 | [-0.000069, 0.000087] |
| normal_epic:speed_hit_chain_start_4-speed_current | -0.000288 | [-0.000344, -0.000232] |
| normal_epic:speed_probability_cost-speed_current | -0.000939 | [-0.001001, -0.000878] |
| normal_epic:speed_probability_cost_start_3-speed_current | -0.000939 | [-0.001001, -0.000878] |
| normal_epic:speed_probability_cost_start_4-speed_current | -0.000939 | [-0.001001, -0.000878] |
| normal_epic:speed_reachable_22-speed_current | 0.000881 | [0.000821, 0.000942] |
| normal_epic:speed_reachable_22_start_3-speed_current | 0.000853 | [0.000810, 0.000895] |
| normal_epic:speed_reachable_22_start_4-speed_current | 0.000574 | [0.000535, 0.000614] |
| normal_heroic:speed_heroic_d_reference-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_hit_chain-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_hit_chain_start_3-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_hit_chain_start_4-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_probability_cost-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_probability_cost_start_3-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_probability_cost_start_4-speed_current | -0.000719 | [-0.000755, -0.000683] |
| normal_heroic:speed_reachable_22-speed_current | 0.000108 | [0.000103, 0.000113] |
| normal_heroic:speed_reachable_22_start_3-speed_current | 0.000109 | [0.000099, 0.000119] |
| normal_heroic:speed_reachable_22_start_4-speed_current | -0.000047 | [-0.000084, -0.000010] |
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