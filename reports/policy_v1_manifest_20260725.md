# 策略 V1 冻结清单与覆盖矩阵

- 生成日期：`2026-07-25`
- 策略版本：`baili-formal-dp-v1-epic-balanced`
- 核心 manifest SHA-256：`565ecd81d9f1354129bbc91ebbd54f291c33249b83371e0be7a5f3316d6c2adb`
- 冻结状态：`not_ready`
- 本清单只读，不授权模拟器输入、自动点击或资源消耗。

## 默认策略

| 来源 | 品质 | 策略 | DP | 资源校准 |
|---|---|---|---:|---|
| `normal_85` | `Epic` | `normal_epic_dp_assisted` | 是 | `published` |
| `normal_85` | `Heroic` | `baili_marginal_low` | 否 | `unpublished` |
| `rift_85` | `Epic` | `rift_epic_dp_assisted` | 是 | `published` |

## 决策路由

| 来源 | 品质 | 节点 | 分段 | 所有者 |
|---|---|---:|---|---|
| `normal_85` | `Epic` | +0 | `all` | `lightweight_prediction` |
| `normal_85` | `Epic` | +3 | `all` | `lightweight_prediction` |
| `normal_85` | `Epic` | +6 | `all` | `exact_dp` |
| `normal_85` | `Epic` | +9 | `all` | `exact_dp` |
| `normal_85` | `Epic` | +12 | `all` | `exact_dp` |
| `normal_85` | `Epic` | +15 | `all` | `terminal_summary` |
| `normal_85` | `Heroic` | +0 | `all` | `lightweight_prediction` |
| `normal_85` | `Heroic` | +3 | `all` | `lightweight_prediction` |
| `normal_85` | `Heroic` | +6 | `non_boot_with_speed` | `heroic_speed22_rescue` |
| `normal_85` | `Heroic` | +6 | `fallback` | `baseline_policy` |
| `normal_85` | `Heroic` | +9 | `non_boot_with_speed` | `heroic_speed22_rescue` |
| `normal_85` | `Heroic` | +9 | `fallback` | `baseline_policy` |
| `normal_85` | `Heroic` | +12 | `non_boot_with_speed` | `heroic_speed22_rescue` |
| `normal_85` | `Heroic` | +12 | `fallback` | `baseline_policy` |
| `normal_85` | `Heroic` | +15 | `all` | `terminal_summary` |
| `rift_85` | `Epic` | +0 | `all` | `lightweight_prediction` |
| `rift_85` | `Epic` | +3 | `all` | `lightweight_prediction` |
| `rift_85` | `Epic` | +6 | `all` | `exact_dp` |
| `rift_85` | `Epic` | +9 | `all` | `exact_dp` |
| `rift_85` | `Epic` | +12 | `all` | `exact_dp` |
| `rift_85` | `Epic` | +15 | `all` | `terminal_summary` |

## 冻结闸门

- `behavior_inputs_hashed`：`passed`
- `supported_scope_complete`：`passed`
- `decision_route_coverage_complete`：`passed`
- `unknown_set_fail_closed`：`failed`
- `full_regression_matrix_evidence_attached`：`failed`

## 未满足项

- `unknown_set_not_rejected_by_advise_gear`
- `full_regression_matrix_evidence_not_attached`

## 行为输入

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `src/e7_enhance/calibration.py` | 101519 | `b21e266e52619e3b64f778f5f2ad24769d0bd5c03766fe9e8063b83ccb75ff1b` |
| `src/e7_enhance/enhance_policy.py` | 33757 | `76420af1f696fefe59954fb958c0ef19d8d0918a8bb0ecc03e56ef63f697cf8a` |
| `src/e7_enhance/lightweight_calibration_rules.json` | 89 | `28ce1a0a0a04aa81e3d3b34a6d74f122e27b4bcd51703fbd2a2358954960476d` |
| `src/e7_enhance/models.py` | 7701 | `ee62a5c6073c30820f72fbce704dbcb049cb18939e177c03a64fbe4a3a2db1d4` |
| `src/e7_enhance/modification_values.py` | 3065 | `5ad20051c73d314927a91af42145c326f261a324bf439eef033878def78f0be5` |
| `src/e7_enhance/resource_model.py` | 26812 | `e91e14a4e8620a662593384bd56bb813734f9f2aaddfb71ce34900e1fa427ef6` |
| `src/e7_enhance/rules.py` | 21798 | `28f84c739dd4a6910a4f0a817f80561eb3933a77bc77eadfec04994cfa32968d` |
| `src/e7_enhance/score_engine.py` | 19580 | `e546acf80cf899ef3d6c4a567bfdf5b00cbacc7fe00682a71cbef845b2f472fe` |
| `src/e7_enhance/strategy_defaults.py` | 2061 | `e179533b50410cd2bfc8045f47605ce4d01f206b028b5aeaf4408ed67fddf893` |
| `装备强化与评分规则审阅.md` | 16126 | `91bc665ac305e838bd51a75ba5793705a172f26f2b1a3b9cf64250ea2ccb7996` |
