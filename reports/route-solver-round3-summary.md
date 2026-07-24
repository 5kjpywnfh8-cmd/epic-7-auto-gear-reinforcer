# Round3 强化路线精确复核

- 评分范围：R2-R58 formal baili score; R61 future is auxiliary only
- 样本：每类每 checkpoint 1000 件，seed=17
- round2 大样本重跑：False
- conversion_cost：0

## 总结

- 最大分歧率：15.4%
- 是否建议进入 dp_assisted：是
- 结论：Design dp_assisted for the flagged checkpoint(s).

## normal_85 Epic

- 当前策略：category_baili_marginal_mid
- cost_per_baili_score：932.82
- lambda：0.00107202
- 建议：consider_dp_assisted / plus12_only

| checkpoint | 一致率 | 分歧率 | both_continue | both_stop | policy_continue_dp_stop | policy_stop_dp_continue | 偏向 |
|---:|---:|---:|---:|---:|---:|---:|---|
| +9 | 96.8% | 3.2% | 5 | 963 | 0 | 32 | policy_more_conservative |
| +12 | 96.4% | 3.6% | 8 | 956 | 2 | 34 | policy_more_conservative |

分歧集中：
- +9: 分类 半肉(血防)=9, 抗坦=7, 输出=6; 套装 set_def=6, set_penetrate=4, set_cri=3; 部位 armor=9, weapon=8, helm=7
- +12: 分类 半肉(血防)=10, 输出=8, 抗坦=5; 套装 set_speed=4, set_def=4, set_cri=3; 部位 weapon=16, armor=6, helm=5

## normal_85 Heroic

- 当前策略：baili_marginal_low
- cost_per_baili_score：22838.96
- lambda：4.378e-05
- 建议：consider_dp_assisted / plus9_and_plus12

| checkpoint | 一致率 | 分歧率 | both_continue | both_stop | policy_continue_dp_stop | policy_stop_dp_continue | 偏向 |
|---:|---:|---:|---:|---:|---:|---:|---|
| +9 | 98.6% | 1.4% | 1 | 985 | 0 | 14 | policy_more_conservative |
| +12 | 99.3% | 0.7% | 0 | 993 | 0 | 7 | policy_more_conservative |

分歧集中：
- +9: 分类 纯肉=4, 抗坦=3, 命坦=2; 套装 set_shield=3, set_opener=2, set_chase=1; 部位 weapon=4, ring=4, helm=2
- +12: 分类 半肉(血防)=3, 一速=2, 命坦=2; 套装 set_rage=2, set_speed=2, set_def=1; 部位 ring=2, armor=1, weapon=1

## rift_85 Epic

- 当前策略：score_target_high_speed_mid
- cost_per_baili_score：411.68
- lambda：0.00242907
- 建议：consider_dp_assisted / plus12_only

| checkpoint | 一致率 | 分歧率 | both_continue | both_stop | policy_continue_dp_stop | policy_stop_dp_continue | 偏向 |
|---:|---:|---:|---:|---:|---:|---:|---|
| +9 | 87.3% | 12.7% | 57 | 816 | 0 | 127 | policy_more_conservative |
| +12 | 84.6% | 15.4% | 52 | 794 | 0 | 154 | policy_more_conservative |

分歧集中：
- +9: 分类 半肉(血防)=38, 半肉(通用)=27, 抗坦=20; 套装 set_speed=18, set_immune=12, set_def=11; 部位 weapon=41, helm=25, armor=24
- +12: 分类 半肉(血防)=42, 半肉(通用)=32, 抗坦=32; 套装 set_speed=22, set_immune=16, set_counter=12; 部位 weapon=42, armor=31, helm=27
