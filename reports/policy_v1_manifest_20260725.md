# 策略 V1 冻结清单与覆盖矩阵

- 生成日期：`2026-07-25`
- 策略版本：`baili-formal-dp-v1-epic-balanced`
- 核心 manifest SHA-256：`050041e19c7626d20deb73e95e2894ce48a5c0e7cd685a4ae471914d7d97423b`
- 冻结状态：`ready`
- 本清单只读，不授权模拟器输入、自动点击或资源消耗。

## 默认策略

| 来源 | 品质 | 策略 | DP | 资源校准 |
|---|---|---|---:|---|
| `normal_85` | `Epic` | `normal_epic_dp_assisted` | 是 | `published` |
| `normal_85` | `Heroic` | `baili_marginal_low` | 否 | `unpublished` |
| `rift_85` | `Epic` | `rift_epic_dp_assisted` | 是 | `published` |

## 决策路由

| 来源 | 品质 | 节点 | 分段 | 所有者 | 内部规则 |
|---|---|---:|---|---|---|
| `normal_85` | `Epic` | +0 | `all` | `lightweight_prediction` | `epic_non_speed_early_stop` |
| `normal_85` | `Epic` | +3 | `all` | `lightweight_prediction` | `epic_non_speed_early_stop` |
| `normal_85` | `Epic` | +6 | `all` | `exact_dp` | `-` |
| `normal_85` | `Epic` | +9 | `all` | `exact_dp` | `-` |
| `normal_85` | `Epic` | +12 | `all` | `exact_dp` | `-` |
| `normal_85` | `Epic` | +15 | `all` | `terminal_summary` | `-` |
| `normal_85` | `Heroic` | +0 | `all` | `lightweight_prediction` | `-` |
| `normal_85` | `Heroic` | +3 | `all` | `lightweight_prediction` | `-` |
| `normal_85` | `Heroic` | +6 | `non_boot_with_speed` | `heroic_speed22_rescue` | `-` |
| `normal_85` | `Heroic` | +6 | `fallback` | `baseline_policy` | `-` |
| `normal_85` | `Heroic` | +9 | `non_boot_with_speed` | `heroic_speed22_rescue` | `-` |
| `normal_85` | `Heroic` | +9 | `fallback` | `baseline_policy` | `-` |
| `normal_85` | `Heroic` | +12 | `non_boot_with_speed` | `heroic_speed22_rescue` | `-` |
| `normal_85` | `Heroic` | +12 | `fallback` | `baseline_policy` | `-` |
| `normal_85` | `Heroic` | +15 | `all` | `terminal_summary` | `-` |
| `rift_85` | `Epic` | +0 | `all` | `lightweight_prediction` | `-` |
| `rift_85` | `Epic` | +3 | `all` | `lightweight_prediction` | `-` |
| `rift_85` | `Epic` | +6 | `all` | `exact_dp` | `-` |
| `rift_85` | `Epic` | +9 | `all` | `exact_dp` | `-` |
| `rift_85` | `Epic` | +12 | `all` | `exact_dp` | `-` |
| `rift_85` | `Epic` | +15 | `all` | `terminal_summary` | `-` |

## Epic 非速度 +0/+3 内部规则

- 候选：`output_8_13_tank_10_17`；规则版本：`epic-early-stop-v1-20260720`。
- 范围：`normal_85 Epic`、85 级、非鞋、初速 `<2`、`+0/+3`。未知套装在候选评估前拒绝。
- 只有当前有效 GS、有效词条数、终局概率和转换 GS 改善四项条件同时满足时才新增停止；基础策略已停止时保持停止。

| 分组 | 类别 | +0 有效 GS 上限 | +3 有效 GS 上限 |
|---|---|---:|---:|
| `pure_output` | `输出、输出(必爆)` | 8 | 13 |
| `pure_tank` | `抗坦、纯肉、命坦` | 10 | 17 |
| `default` | `双效、半肉(血防)、半肉(通用)、半肉(白字)、未知候选分组` | 12 | 17 |

- 有效词条数上限：`2`。
- 终局概率上限：`+0=0.002`、`+3=0.01`。
- 转换 GS 改善上限：`0.0`。

## 完整回归矩阵证据

- 状态：`attached_verified`。
- 路径：`reports/policy_v1_regression_evidence_20260725.json`。
- 文件 SHA-256：`892817868b18cc0e6b73a554c3c1eb68e2d4fd228aa98d8fa5342cd4eb1c9b70`。
- 测试文件：`9`；测试数：`123`；覆盖要求：`13`。

## 冻结闸门

- `behavior_inputs_hashed`：`passed`
- `supported_scope_complete`：`passed`
- `decision_route_coverage_complete`：`passed`
- `unknown_set_fail_closed`：`passed`
- `full_regression_matrix_evidence_attached`：`passed`

## 未满足项

- 无。

## 行为输入

| 文件 | 字节 | SHA-256 |
|---|---:|---|
| `src/e7_enhance/calibration.py` | 101519 | `b21e266e52619e3b64f778f5f2ad24769d0bd5c03766fe9e8063b83ccb75ff1b` |
| `src/e7_enhance/enhance_policy.py` | 33757 | `76420af1f696fefe59954fb958c0ef19d8d0918a8bb0ecc03e56ef63f697cf8a` |
| `src/e7_enhance/epic_early_stop.py` | 6048 | `6184b9e0b64a4f35c28a432cb05b3aa6d2ee004162f7ef28defde41c7ad96a07` |
| `src/e7_enhance/lightweight_calibration.py` | 24642 | `d928925cdae73b5f94cb5d6bb7fdc51bf5326011603d7a2865c1ee12506b7048` |
| `src/e7_enhance/lightweight_calibration_rules.json` | 89 | `28ce1a0a0a04aa81e3d3b34a6d74f122e27b4bcd51703fbd2a2358954960476d` |
| `src/e7_enhance/models.py` | 7831 | `03348c94cffaa93f49b01de54516a4947363b6d338ce3831caba7bdf49d1abd5` |
| `src/e7_enhance/modification_values.py` | 3065 | `5ad20051c73d314927a91af42145c326f261a324bf439eef033878def78f0be5` |
| `src/e7_enhance/resource_model.py` | 26812 | `e91e14a4e8620a662593384bd56bb813734f9f2aaddfb71ce34900e1fa427ef6` |
| `src/e7_enhance/rules.py` | 21937 | `98e3bd77c1c08d6608b599288c948559366790e0206bb2dd280943710cd2004e` |
| `src/e7_enhance/score_engine.py` | 19580 | `e546acf80cf899ef3d6c4a567bfdf5b00cbacc7fe00682a71cbef845b2f472fe` |
| `src/e7_enhance/strategy_defaults.py` | 2061 | `e179533b50410cd2bfc8045f47605ce4d01f206b028b5aeaf4408ed67fddf893` |
| `装备强化与评分规则审阅.md` | 16126 | `91bc665ac305e838bd51a75ba5793705a172f26f2b1a3b9cf64250ea2ccb7996` |
