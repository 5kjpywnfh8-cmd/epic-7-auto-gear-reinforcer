# 第二轮 R2-R58 正式百里策略验证报告

## 结论

- ranking_metric：`cost_per_baili_score`
- main_score_scope：`R2-R58 formal baili score; R61 future is auxiliary only`
- 普通 85 红装 100k×3 最优：`category_baili_marginal_mid`。
- 普通 85 红装 1M×5 最优：`category_baili_marginal_mid`。
- 1M×5 第一名一致性：`category_baili_marginal_mid`。
- 普通 85 紫装 1M×5 最优：`baili_marginal_low`；估计每 seed 成功件约 `100.0`，是否建议 3M×5：`False`。
- 异界 85 红装 1M×5 最优：`score_target_high_speed_mid`。
- 方向判断：`set_group_improved`。
- 是否建议进入紫装验证：`True`。

## normal_epic_100k

### seed 结果

| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | R61主收益 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | `category_set_group_baili_marginal_mid` | 1.1 | 925.4 | 0.65% | 0.38% | 0.27% | 0.35% | 0 |
| 29 | `category_baili_marginal_mid` | 1.1 | 922.4 | 0.71% | 0.40% | 0.31% | 0.40% | 0 |
| 43 | `category_baili_marginal_mid` | 1.1 | 913.4 | 0.66% | 0.39% | 0.27% | 0.34% | 0 |

### Top5 均值排序

| rank | policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 平均seed排名 |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `category_baili_marginal_mid` | 920.4667 | 5.1648 | 5.8446 | 1.1 | 1.333 |
| 2 | `baili_marginal_mid` | 924.6667 | 6.7795 | 7.6718 | 1.1 | 2.333 |
| 3 | `global_baili_marginal_mid` | 924.6667 | 6.7795 | 7.6718 | 1.1 | 3.333 |
| 4 | `category_set_group_baili_marginal_mid` | 928.6667 | 2.3113 | 2.6155 | 1.1 | 3 |
| 5 | `set_group_baili_marginal_mid` | 934.2667 | 1.7461 | 1.9759 | 1.1 | 5 |

### 指定策略对照

| policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 成功率 mean | +12停 | +15完成 | seed排名 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `global_baili_marginal_mid` | 924.6667 | 6.7795 | 7.6718 | 1.1 | 0.68% | 0.26% | 0.81% | {'17': 4, '29': 3, '43': 3} |
| `baili_marginal_low` | 1013.1667 | 10.4081 | 11.7779 | 1 | 0.81% | 0.30% | 1.01% | {'17': 9, '29': 9, '43': 9} |
| `baili_marginal_mid` | 924.6667 | 6.7795 | 7.6718 | 1.1 | 0.68% | 0.26% | 0.81% | {'17': 3, '29': 2, '43': 2} |
| `baili_marginal_high` | 979.3 | 5.2466 | 5.9371 | 1 | 0.45% | 0.21% | 0.52% | {'17': 7, '29': 7, '43': 7} |
| `target_marginal_mid` | 996.1667 | 7.5155 | 8.5045 | 1 | 0.69% | 0.34% | 0.86% | {'17': 8, '29': 8, '43': 8} |
| `score_target_low_speed_low` | 3171.4 | 35.6415 | 40.3322 | 0.3 | 0.94% | 0.41% | 1.07% | {'17': 10, '29': 10, '43': 11} |
| `score_strategy_late_strict_speed_high` | 8504.3 | 721.1305 | 816.0359 | 0.1 | 0.10% | 0.11% | 0.10% | {'17': 26, '29': 26, '43': 26} |
| `set_group_baili_marginal_mid` | 934.2667 | 1.7461 | 1.9759 | 1.1 | 0.65% | 0.26% | 0.78% | {'17': 5, '29': 5, '43': 5} |
| `category_baili_marginal_mid` | 920.4667 | 5.1648 | 5.8446 | 1.1 | 0.69% | 0.28% | 0.83% | {'17': 2, '29': 1, '43': 1} |
| `category_set_group_baili_marginal_mid` | 928.6667 | 2.3113 | 2.6155 | 1.1 | 0.63% | 0.26% | 0.76% | {'17': 1, '29': 4, '43': 4} |
| `speed_set_specialized` | 966.3333 | 1.5628 | 1.7684 | 1 | 0.54% | 0.25% | 0.63% | {'17': 6, '29': 6, '43': 6} |

## normal_epic_1m

### seed 结果

| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | R61主收益 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | `category_baili_marginal_mid` | 1.1 | 929.4 | 0.70% | 0.41% | 0.29% | 0.37% | 0 |
| 29 | `category_baili_marginal_mid` | 1.1 | 944.5 | 0.69% | 0.41% | 0.28% | 0.36% | 0 |
| 43 | `category_baili_marginal_mid` | 1.1 | 929.5 | 0.69% | 0.41% | 0.28% | 0.36% | 0 |
| 71 | `category_baili_marginal_mid` | 1.1 | 917.6 | 0.71% | 0.42% | 0.29% | 0.38% | 0 |
| 101 | `category_baili_marginal_mid` | 1.1 | 943.1 | 0.70% | 0.42% | 0.29% | 0.37% | 0 |

### Top5 均值排序

| rank | policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 平均seed排名 |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `category_baili_marginal_mid` | 932.82 | 9.9646 | 8.7344 | 1.1 | 1 |
| 2 | `baili_marginal_mid` | 938.3 | 10.5868 | 9.2797 | 1.1 | 2.2 |
| 3 | `global_baili_marginal_mid` | 938.3 | 10.5868 | 9.2797 | 1.1 | 3.2 |
| 4 | `category_set_group_baili_marginal_mid` | 939.18 | 10.8722 | 9.5299 | 1.1 | 3.6 |
| 5 | `set_group_baili_marginal_mid` | 945.04 | 10.3739 | 9.0931 | 1.06 | 5 |

### 指定策略对照

| policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 成功率 mean | +12停 | +15完成 | seed排名 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `global_baili_marginal_mid` | 938.3 | 10.5868 | 9.2797 | 1.1 | 0.68% | 0.28% | 0.82% | {'17': 4, '29': 3, '43': 3, '71': 3, '101': 3} |
| `baili_marginal_low` | 1011.86 | 8.5043 | 7.4543 | 1 | 0.83% | 0.30% | 1.03% | {'17': 9, '29': 9, '43': 9, '71': 9, '101': 8} |
| `baili_marginal_mid` | 938.3 | 10.5868 | 9.2797 | 1.1 | 0.68% | 0.28% | 0.82% | {'17': 3, '29': 2, '43': 2, '71': 2, '101': 2} |
| `baili_marginal_high` | 997.66 | 17.772 | 15.5778 | 1 | 0.45% | 0.22% | 0.53% | {'17': 7, '29': 7, '43': 7, '71': 7, '101': 7} |
| `target_marginal_mid` | 1010.08 | 11.8136 | 10.3551 | 1 | 0.70% | 0.35% | 0.87% | {'17': 8, '29': 8, '43': 8, '71': 8, '101': 9} |
| `score_target_low_speed_low` | 3121.72 | 16.638 | 14.5838 | 0.3 | 0.97% | 0.40% | 1.09% | {'17': 10, '29': 10, '43': 10, '71': 10, '101': 10} |
| `score_strategy_late_strict_speed_high` | 8961.6 | 389.8857 | 341.7499 | 0.1 | 0.09% | 0.11% | 0.10% | {'17': 26, '29': 26, '43': 26, '71': 26, '101': 26} |
| `set_group_baili_marginal_mid` | 945.04 | 10.3739 | 9.0931 | 1.06 | 0.66% | 0.28% | 0.79% | {'17': 5, '29': 5, '43': 5, '71': 5, '101': 5} |
| `category_baili_marginal_mid` | 932.82 | 9.9646 | 8.7344 | 1.1 | 0.70% | 0.29% | 0.84% | {'17': 1, '29': 1, '43': 1, '71': 1, '101': 1} |
| `category_set_group_baili_marginal_mid` | 939.18 | 10.8722 | 9.5299 | 1.1 | 0.64% | 0.27% | 0.77% | {'17': 2, '29': 4, '43': 4, '71': 4, '101': 4} |
| `speed_set_specialized` | 980.74 | 12.6082 | 11.0516 | 1 | 0.54% | 0.25% | 0.64% | {'17': 6, '29': 6, '43': 6, '71': 6, '101': 6} |

## normal_heroic_1m

### seed 结果

| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | R61主收益 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | `baili_marginal_low` | 0 | 23905.2 | 0.01% | 0.00% | 0.00% | 0.00% | 0 |
| 29 | `baili_marginal_low` | 0.1 | 19786.1 | 0.01% | 0.00% | 0.00% | 0.00% | 0 |
| 43 | `baili_marginal_low` | 0 | 24937.3 | 0.01% | 0.00% | 0.00% | 0.00% | 0 |
| 71 | `baili_marginal_low` | 0 | 23043.2 | 0.01% | 0.00% | 0.00% | 0.00% | 0 |
| 101 | `baili_marginal_low` | 0 | 22523 | 0.01% | 0.00% | 0.00% | 0.00% | 0 |

### Top5 均值排序

| rank | policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 平均seed排名 |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `baili_marginal_low` | 22838.96 | 1732.1315 | 1518.2802 | 0.02 | 1 |
| 2 | `category_baili_marginal_mid` | 30164.52 | 1547.103 | 1356.0955 | 0 | 2.2 |
| 3 | `set_group_baili_marginal_mid` | 32148.36 | 2487.024 | 2179.9726 | 0 | 3.6 |
| 4 | `baili_marginal_mid` | 33322.94 | 2700.1586 | 2366.7933 | 0 | 4.4 |
| 5 | `global_baili_marginal_mid` | 33322.94 | 2700.1586 | 2366.7933 | 0 | 5.4 |

### 指定策略对照

| policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 成功率 mean | +12停 | +15完成 | seed排名 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `global_baili_marginal_mid` | 33322.94 | 2700.1586 | 2366.7933 | 0 | 0.00% | 0.09% | 0.00% | {'17': 6, '29': 4, '43': 6, '71': 5, '101': 6} |
| `baili_marginal_low` | 22838.96 | 1732.1315 | 1518.2802 | 0.02 | 0.01% | 0.11% | 0.01% | {'17': 1, '29': 1, '43': 1, '71': 1, '101': 1} |
| `baili_marginal_mid` | 33322.94 | 2700.1586 | 2366.7933 | 0 | 0.00% | 0.09% | 0.00% | {'17': 5, '29': 3, '43': 5, '71': 4, '101': 5} |
| `baili_marginal_high` | 64894.58 | 11821.7142 | 10362.1894 | 0 | 0.00% | 0.07% | 0.00% | {'17': 9, '29': 9, '43': 9, '71': 9, '101': 9} |
| `target_marginal_mid` | 33322.94 | 2700.1586 | 2366.7933 | 0 | 0.00% | 0.09% | 0.00% | {'17': 7, '29': 5, '43': 7, '71': 6, '101': 7} |
| `score_target_low_speed_low` | 190097.58 | 13836.1582 | 12127.9274 | 0 | 0.02% | 0.24% | 0.02% | {'17': 13, '29': 10, '43': 13, '71': 13, '101': 13} |
| `score_strategy_late_strict_speed_high` | 12460890.2 | 0 | 0 | 0 | 0.00% | 0.02% | 0.00% | {'17': 26, '29': 26, '43': 26, '71': 26, '101': 24} |
| `set_group_baili_marginal_mid` | 32148.36 | 2487.024 | 2179.9726 | 0 | 0.00% | 0.09% | 0.00% | {'17': 2, '29': 6, '43': 4, '71': 3, '101': 3} |
| `category_baili_marginal_mid` | 30164.52 | 1547.103 | 1356.0955 | 0 | 0.00% | 0.09% | 0.00% | {'17': 3, '29': 2, '43': 2, '71': 2, '101': 2} |
| `category_set_group_baili_marginal_mid` | 33606.82 | 1849.1347 | 1620.8381 | 0 | 0.00% | 0.09% | 0.00% | {'17': 4, '29': 7, '43': 3, '71': 7, '101': 4} |
| `speed_set_specialized` | 44644.42 | 4575.1556 | 4010.3007 | 0 | 0.00% | 0.08% | 0.00% | {'17': 8, '29': 8, '43': 8, '71': 8, '101': 8} |

## rift_epic_1m

### seed 结果

| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | R61主收益 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | `score_target_high_speed_low` | 2.4 | 411.1 | 2.50% | 1.83% | 0.67% | 1.10% | 0 |
| 29 | `score_target_high_speed_low` | 2.4 | 413.3 | 2.52% | 1.85% | 0.67% | 1.10% | 0 |
| 43 | `score_target_high_speed_mid` | 2.4 | 411.6 | 2.52% | 1.85% | 0.68% | 1.12% | 0 |
| 71 | `score_target_high_speed_low` | 2.4 | 409.7 | 2.52% | 1.83% | 0.69% | 1.13% | 0 |
| 101 | `score_target_high_speed_low` | 2.4 | 412.7 | 2.54% | 1.87% | 0.67% | 1.11% | 0 |

### Top5 均值排序

| rank | policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 平均seed排名 |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `score_target_high_speed_mid` | 411.68 | 1.2592 | 1.1037 | 2.4 | 1.8 |
| 2 | `score_target_high_speed_low` | 411.7 | 1.2586 | 1.1032 | 2.4 | 1.2 |
| 3 | `score_target_high_speed_high` | 411.78 | 1.2592 | 1.1037 | 2.4 | 3 |
| 4 | `baili_marginal_high` | 416.44 | 1.0012 | 0.8776 | 2.4 | 4 |
| 5 | `speed_set_specialized` | 427.92 | 1.0534 | 0.9233 | 2.3 | 5 |

### 指定策略对照

| policy | 体力/百里 mean | stddev | 95% CI | 百里/千体 mean | 成功率 mean | +12停 | +15完成 | seed排名 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `global_baili_marginal_mid` | 439.14 | 0.9952 | 0.8723 | 2.3 | 9.12% | 1.91% | 10.40% | {'17': 9, '29': 9, '43': 9, '71': 9, '101': 9} |
| `baili_marginal_low` | 457.24 | 0.9952 | 0.8723 | 2.2 | 10.33% | 1.92% | 11.93% | {'17': 11, '29': 11, '43': 11, '71': 11, '101': 11} |
| `baili_marginal_mid` | 439.14 | 0.9952 | 0.8723 | 2.3 | 9.12% | 1.91% | 10.40% | {'17': 8, '29': 8, '43': 8, '71': 8, '101': 8} |
| `baili_marginal_high` | 416.44 | 1.0012 | 0.8776 | 2.4 | 7.04% | 1.87% | 7.89% | {'17': 4, '29': 4, '43': 4, '71': 4, '101': 4} |
| `target_marginal_mid` | 531.48 | 1.3819 | 1.2113 | 1.9 | 9.70% | 5.56% | 13.24% | {'17': 16, '29': 16, '43': 16, '71': 16, '101': 16} |
| `score_target_low_speed_low` | 544.58 | 0.9988 | 0.8755 | 1.8 | 11.61% | 2.27% | 13.36% | {'17': 18, '29': 18, '43': 18, '71': 18, '101': 18} |
| `score_strategy_late_strict_speed_high` | 607.74 | 2.985 | 2.6165 | 1.62 | 2.35% | 1.90% | 2.55% | {'17': 23, '29': 23, '43': 23, '71': 23, '101': 23} |
| `set_group_baili_marginal_mid` | 437.26 | 1.0346 | 0.9069 | 2.3 | 8.61% | 1.95% | 9.75% | {'17': 7, '29': 7, '43': 7, '71': 7, '101': 7} |
| `category_baili_marginal_mid` | 439.36 | 1.048 | 0.9187 | 2.3 | 9.29% | 1.95% | 10.60% | {'17': 10, '29': 10, '43': 10, '71': 10, '101': 10} |
| `category_set_group_baili_marginal_mid` | 431.5 | 1.0218 | 0.8956 | 2.3 | 8.43% | 1.96% | 9.56% | {'17': 6, '29': 6, '43': 6, '71': 6, '101': 6} |
| `speed_set_specialized` | 427.92 | 1.0534 | 0.9233 | 2.3 | 7.83% | 2.04% | 8.84% | {'17': 5, '29': 5, '43': 5, '71': 5, '101': 5} |

## 可视化交付

- single_policy_png: `reports/visual/baili-formal-round2-normal-epic-1m-seed17-category_baili_marginal_mid.png`
- single_policy_html: `reports/visual/baili-formal-round2-normal-epic-1m-seed17-category_baili_marginal_mid.html`
- aggregate_best_single_png: `reports/visual/baili-formal-round2-best-single-policy.png`
- aggregate_best_single_html: `reports/visual/baili-formal-round2-best-single-policy.html`
- top5_compare_png: `reports/visual/baili-formal-round2-normal-epic-1m-seed17-top5-compare.png`
- top5_compare_html: `reports/visual/baili-formal-round2-normal-epic-1m-seed17-top5-compare.html`
- set_contribution_png: `reports/visual/baili-formal-round2-set-contribution.png`
- set_contribution_html: `reports/visual/baili-formal-round2-set-contribution.html`
- equipment_type_compare_png: `reports/visual/baili-formal-round2-equipment-type-compare.png`
- equipment_type_compare_html: `reports/visual/baili-formal-round2-equipment-type-compare.html`
- round2_index_html: `reports/visual/round2-index.html`

## 转换石成本敏感性

### normal_epic_100k
- conversion_cost=0: seed17: `category_set_group_baili_marginal_mid` (925.4), seed29: `category_baili_marginal_mid` (922.4), seed43: `category_baili_marginal_mid` (913.4)
- conversion_cost=200: seed17: `category_set_group_baili_marginal_mid` (938.7), seed29: `category_baili_marginal_mid` (936.9), seed43: `category_baili_marginal_mid` (926.1)
- conversion_cost=500: seed17: `category_set_group_baili_marginal_mid` (958.8), seed29: `category_baili_marginal_mid` (958.7), seed43: `category_baili_marginal_mid` (945.1)
- conversion_cost=1000: seed17: `category_set_group_baili_marginal_mid` (992.2), seed29: `category_baili_marginal_mid` (995.1), seed43: `category_baili_marginal_mid` (976.9)

### normal_epic_1m
- conversion_cost=0: seed17: `category_baili_marginal_mid` (929.4), seed29: `category_baili_marginal_mid` (944.5), seed43: `category_baili_marginal_mid` (929.5), seed71: `category_baili_marginal_mid` (917.6), seed101: `category_baili_marginal_mid` (943.1)
- conversion_cost=200: seed17: `category_baili_marginal_mid` (943.1), seed29: `category_baili_marginal_mid` (957.9), seed43: `category_baili_marginal_mid` (942.7), seed71: `category_baili_marginal_mid` (931), seed101: `category_baili_marginal_mid` (956.6)
- conversion_cost=500: seed17: `category_baili_marginal_mid` (963.5), seed29: `category_baili_marginal_mid` (978), seed43: `category_baili_marginal_mid` (962.5), seed71: `category_baili_marginal_mid` (951.2), seed101: `category_baili_marginal_mid` (976.9)
- conversion_cost=1000: seed17: `category_baili_marginal_mid` (997.5), seed29: `category_baili_marginal_mid` (1011.6), seed43: `category_baili_marginal_mid` (995.6), seed71: `category_baili_marginal_mid` (984.9), seed101: `category_baili_marginal_mid` (1010.7)

### normal_heroic_1m
- conversion_cost=0: seed17: `baili_marginal_low` (23905.2), seed29: `baili_marginal_low` (19786.1), seed43: `baili_marginal_low` (24937.3), seed71: `baili_marginal_low` (23043.2), seed101: `baili_marginal_low` (22523)
- conversion_cost=200: seed17: `baili_marginal_low` (23926.3), seed29: `baili_marginal_low` (19805), seed43: `baili_marginal_low` (24960.6), seed71: `baili_marginal_low` (23065.2), seed101: `baili_marginal_low` (22547.3)
- conversion_cost=500: seed17: `baili_marginal_low` (23957.9), seed29: `baili_marginal_low` (19833.4), seed43: `baili_marginal_low` (24995.5), seed71: `baili_marginal_low` (23098.3), seed101: `baili_marginal_low` (22583.6)
- conversion_cost=1000: seed17: `baili_marginal_low` (24010.7), seed29: `baili_marginal_low` (19880.7), seed43: `baili_marginal_low` (25053.8), seed71: `baili_marginal_low` (23153.5), seed101: `baili_marginal_low` (22644.1)

### rift_epic_1m
- conversion_cost=0: seed17: `score_target_high_speed_low` (411.1), seed29: `score_target_high_speed_low` (413.3), seed43: `score_target_high_speed_mid` (411.6), seed71: `score_target_high_speed_low` (409.7), seed101: `score_target_high_speed_low` (412.7)
- conversion_cost=200: seed17: `score_target_high_speed_low` (417.9), seed29: `score_target_high_speed_low` (420.1), seed43: `score_target_high_speed_mid` (418.5), seed71: `score_target_high_speed_low` (416.6), seed101: `score_target_high_speed_low` (419.5)
- conversion_cost=500: seed17: `score_target_high_speed_low` (428), seed29: `score_target_high_speed_low` (430.3), seed43: `score_target_high_speed_mid` (428.8), seed71: `score_target_high_speed_low` (427), seed101: `score_target_high_speed_low` (429.8)
- conversion_cost=1000: seed17: `score_target_high_speed_low` (445), seed29: `score_target_high_speed_low` (447.3), seed43: `score_target_high_speed_mid` (445.9), seed71: `score_target_high_speed_low` (444.2), seed101: `score_target_high_speed_low` (446.8)

## 真实掉落模型风险

- 当前模拟器按代码内置随机胚子分布生成装备，尚未用真实游戏掉落分布校正；报告结论只能视为策略相对效率验证，不是最终实测掉落效率。
- 后续校正需要数据：
  - set 分布
  - slot 分布
  - rank 分布
  - mainStat 分布
  - substat 组合分布
  - 红装 / 紫装出现率
  - 各副属性初始值分布
  - 装备出售回收的实测数据
  - 强化资源与金币来源实测数据
