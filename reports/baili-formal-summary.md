# R2-R58 正式分类百里分优先策略校准报告

## 结论

- 推荐策略：`baili_marginal_mid`。
- 新版确实提升的是正式百里分效率，不是只提高泛用 target_score。
- R61 未来可期未进入新版主收益；旧报告中 R61 会抬高 target_score，是旧策略误导点。
- 普通 85 红装 10k×3 稳定后已扩大到 100k×3，三组 100k 第一名一致。

## 口径核对

- ranking_metric：`cost_per_baili_score`
- main_score_scope：`R2-R58 formal baili score; R61 future is auxiliary only`
- item_source / rank：`normal_85 / Epic`

## 普通 85 红装 10k×3

| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | 未来可期主收益 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | `baili_marginal_mid` | 0.9 | 1126.3 | 0.63% | 0.38% | 0.25% | 0.31% | 0 |
| 29 | `baili_marginal_mid` | 1.2 | 807.2 | 0.74% | 0.36% | 0.38% | 0.51% | 0 |
| 43 | `baili_marginal_mid` | 1.1 | 892.1 | 0.66% | 0.37% | 0.29% | 0.36% | 0 |

- 平均百里/千体：`1.0667`，标准差 `0.1247`。
- 平均体力/百里：`941.8667`，标准差 `134.9413`。
- 第一名一致性：`baili_marginal_mid`。

## 普通 85 红装 100k×3

| seed | best_policy | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | 转换需求 | 未来可期主收益 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 17 | `baili_marginal_mid` | 1.1 | 923.5 | 0.69% | 0.41% | 0.28% | 0.36% | 0 |
| 29 | `baili_marginal_mid` | 1.1 | 930 | 0.69% | 0.39% | 0.30% | 0.40% | 0 |
| 43 | `baili_marginal_mid` | 1.1 | 913.2 | 0.65% | 0.38% | 0.27% | 0.34% | 0 |

- 平均百里/千体：`1.1`，标准差 `0`。
- 平均体力/百里：`922.2333`，标准差 `6.9168`。
- 第一名一致性：`baili_marginal_mid`。

## 旧报告对比（seed17 10k）

| 报告 | ranking_metric | 策略 | 百里/千体 | 体力/百里 | target/千体 | 体力/target | 未来可期贡献 |
|---|---|---|---:|---:|---:|---:|---:|
| new_baili_formal_seed17 | `cost_per_baili_score` | `baili_marginal_mid` | 0.9 | 1126.3 | 0.9 | 1126.3 | 0 |
| old_target_seed17 | `cost_per_target_score` | `score_marginal_value_mid_speed_dynamic` | 0.4 | 2363.3 | 0.8 | 1223.8 | 8.8 |
| old_target_after_md_specials_seed17 | `cost_per_target_score` | `score_marginal_value_mid_speed_dynamic` | 0.4 | 2414.5 | 0.8 | 1296.4 | 25.1 |

## 100k seed17 Top5

| 排名 | 策略 | 百里/千体 | 体力/百里 | 成功率 | 原生 | 补救 | +12停 | +15完成 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `baili_marginal_mid` | 1.1 | 923.5 | 0.69% | 0.41% | 0.28% | 0.28% | 0.82% |
| 2 | `baili_marginal_high` | 1 | 977.5 | 0.46% | 0.30% | 0.16% | 0.24% | 0.53% |
| 3 | `target_marginal_mid` | 1 | 997.3 | 0.70% | 0.41% | 0.29% | 0.35% | 0.87% |
| 4 | `baili_marginal_low` | 1 | 1022.8 | 0.82% | 0.48% | 0.34% | 0.31% | 1.01% |
| 5 | `score_target_low_speed_low` | 0.3 | 3174.1 | 0.96% | 0.50% | 0.46% | 0.40% | 1.08% |

## 指定策略对照（100k seed17）

| 策略 | 百里/千体 | 体力/百里 | target/千体 | 成功率 | +12停 | +15完成 |
|---|---:|---:|---:|---:|---:|---:|
| `baili_marginal_low` | 1 | 1022.8 | 1 | 0.82% | 0.31% | 1.01% |
| `baili_marginal_mid` | 1.1 | 923.5 | 1.1 | 0.69% | 0.28% | 0.82% |
| `baili_marginal_high` | 1 | 977.5 | 1 | 0.46% | 0.24% | 0.53% |
| `target_marginal_mid` | 1 | 997.3 | 1 | 0.70% | 0.35% | 0.87% |
| `score_target_low_speed_low` | 0.3 | 3174.1 | 0.3 | 0.96% | 0.40% | 1.08% |
| `score_strategy_late_strict_speed_high` | 0.1 | 9151.8 | 0.1 | 0.10% | 0.12% | 0.10% |

## 可视化

- 单策略审核图：`reports/visual/baili-formal-normal-100k-seed17-baili_marginal_mid.png`
- top5 对比图：`reports/visual/baili-formal-normal-100k-seed17-top5-compare.png`
- HTML 索引：`reports/visual/index.html`

## 剩余风险

- 样本仍有波动，尤其低成功率策略的尾部高分件。
- 掉落模型仍是模拟分布，未按真实副属性掉落分布校正。
- 转换石成本未计入，补救效率是偏乐观估计。
- 紫装未验证。
- 异界未验证。
