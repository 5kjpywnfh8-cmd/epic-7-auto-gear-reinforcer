# DP assisted 分歧分析

## 结论

- 是否新增 dp_assisted：是
- 默认是否启用：否
- 建议 1M x 5 复验：是
- 本轮验证样本：100000 x seeds [17, 29, 43]

## 逐项回答

1. 当前 round2 推荐策略是否接近 DP 最优：normal_85 Epic / Heroic 接近，rift_85 Epic 不接近。
2. 分歧主要发生在哪里：rift_85 Epic 的 +9/+12，且集中在半肉(血防)、半肉(通用)、抗坦等正式分类；普通红/紫分歧率低但高 gap 样本存在。
3. 当前策略偏激进还是偏保守：三类都是偏保守，主要是 policy_stop_dp_continue。
4. 是否新增 dp_assisted：是，新增为显式可选策略；默认不开启。
5. dp_assisted 是否提升 cost_per_baili_score：normal_85 Epic 和 normal_85 Heroic 在 100k x 3 seeds 中稳定提升；rift_85 Epic 稳定变差。
6. 如果提升不稳定，是否建议不接入默认策略：是。由于 rift_85 Epic 变差，整体不建议接入默认策略。
7. 下一步是否需要 1M x 5 复验：需要，优先复验 normal_epic_dp_assisted / normal_heroic_dp_assisted；rift_epic_dp_assisted 暂不建议默认采用。

## Round3 分歧

### normal_85 Epic

- 当前 round2 策略：category_baili_marginal_mid
- 判断：新增 DP 辅助候选
- 偏向：round2_policy_more_conservative
- 触发原因：+9 policy_stop_dp_continue dominates; +9 top expected_utility_gap >= 1.0; +12 policy_stop_dp_continue dominates; +12 top expected_utility_gap >= 1.0

| checkpoint | 一致率 | 分歧率 | policy_continue_dp_stop | policy_stop_dp_continue | top gap max | 主分类分歧 top | mainStat top |
|---:|---:|---:|---:|---:|---:|---|---|
| +9 | 96.8% | 3.2% | 0 | 32 | 4.685075 | 半肉(血防)=9, 抗坦=7 | Attack=7, Defense=5 |
| +12 | 96.4% | 3.6% | 2 | 34 | 5.6928 | 半肉(血防)=10, 输出=8 | Attack=10, Health=4 |

### normal_85 Heroic

- 当前 round2 策略：baili_marginal_low
- 判断：新增 DP 辅助候选
- 偏向：round2_policy_more_conservative
- 触发原因：+9 policy_stop_dp_continue dominates; +12 top expected_utility_gap >= 1.0

| checkpoint | 一致率 | 分歧率 | policy_continue_dp_stop | policy_stop_dp_continue | top gap max | 主分类分歧 top | mainStat top |
|---:|---:|---:|---:|---:|---:|---|---|
| +9 | 98.6% | 1.4% | 0 | 14 | 0.401397 | 纯肉=4, 抗坦=3 | Attack=4, HealthPercent=2 |
| +12 | 99.3% | 0.7% | 0 | 7 | 2.459662 | 半肉(血防)=3, 一速=2 | Health=1, Attack=1 |

### rift_85 Epic

- 当前 round2 策略：score_target_high_speed_mid
- 判断：新增 DP 辅助候选
- 偏向：round2_policy_more_conservative
- 触发原因：+9 disagreement_rate 0.127 > 0.10; +9 policy_stop_dp_continue dominates; +9 top expected_utility_gap >= 1.0; +12 disagreement_rate 0.154 > 0.10; +12 policy_stop_dp_continue dominates; +12 top expected_utility_gap >= 1.0

| checkpoint | 一致率 | 分歧率 | policy_continue_dp_stop | policy_stop_dp_continue | top gap max | 主分类分歧 top | mainStat top |
|---:|---:|---:|---:|---:|---:|---|---|
| +9 | 87.3% | 12.7% | 0 | 127 | 8.322746 | 半肉(血防)=38, 半肉(通用)=27 | Attack=7, Health=5 |
| +12 | 84.6% | 15.4% | 0 | 154 | 10.179861 | 半肉(血防)=42, 半肉(通用)=32 | Attack=10, Defense=3 |

## 小样本验证

| 类型 | seed | baseline cost | dp cost | delta | DP 调用 | DP 改判 | best_policy |
|---|---:|---:|---:|---:|---:|---:|---|
| normal_85 Epic | 17 | 925.6 | 828.4 | -97.2 | 5590 | 2019 | normal_epic_dp_assisted |
| normal_85 Epic | 29 | 922.4 | 819.9 | -102.5 | 5762 | 2152 | normal_epic_dp_assisted |
| normal_85 Epic | 43 | 913.4 | 821.2 | -92.2 | 5494 | 2029 | normal_epic_dp_assisted |
| normal_85 Heroic | 17 | 16900.7 | 4979.0 | -11921.7 | 772 | 213 | normal_heroic_dp_assisted |
| normal_85 Heroic | 29 | 15098.5 | 4856.8 | -10241.7 | 736 | 201 | normal_heroic_dp_assisted |
| normal_85 Heroic | 43 | 13184.4 | 4785.8 | -8398.6 | 760 | 189 | normal_heroic_dp_assisted |
| rift_85 Epic | 17 | 419.4 | 435.2 | 15.8 | 10940 | 2815 | score_target_high_speed_mid |
| rift_85 Epic | 29 | 414.8 | 427.9 | 13.1 | 10934 | 2834 | score_target_high_speed_mid |
| rift_85 Epic | 43 | 412.5 | 429.9 | 17.4 | 10948 | 2900 | score_target_high_speed_mid |

## 解释

- normal_85 Epic / Heroic 的 round3 分歧率低，说明 round2 推荐策略整体接近 DP 路线。
- rift_85 Epic 的 +9/+12 分歧率超过 10%，且主要是 policy_stop_dp_continue，当前策略偏保守。
- dp_assisted 只作为显式策略加入，默认不替换原策略；是否接入默认策略取决于小样本和后续 1M x 5 复验。
