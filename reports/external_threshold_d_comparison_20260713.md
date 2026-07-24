# 外部红紫阈值表策略 D 离线对比

D 仅为离线候选。A/B/C 读取冻结的 22 速研究分片；D 在独立目录确定性重放相同 seed、装备与随机种子。未修改正式策略、lambda、Heroic 正式策略、评分、跳值表或 GUI。

研究 lambda：`0.0022851391`，仅用于前瞻 Oracle 口径备案，未写回正式配置。

## 主口径

每联合批次为 85 维度裂缝体力、1 Epic、85/23.81 Heroic、0.425 下级石与 127,500 金币。红紫装备资源流合并后仅做一次圣女 3-7 金币/经验瓶颈补充。

## curve_baseline/baili_marginal_low/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212692, 0.217597] |
| C_category_probability | [0.209179, 0.214626] |
| A_current_review | [0.196239, 0.201446] |
| D_epic_only_base | [0.160231, 0.162312] |
| D_full | [0.108020, 0.111382] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.107417, -0.103470] |
| D_epic_only_base - B_global_current_gs | [-0.055622, -0.052124] |
| B_global_current_gs - C_category_probability | [0.002842, 0.003642] |

## curve_baseline/baili_marginal_low/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225657, 0.231371] |
| C_category_probability | [0.221703, 0.227862] |
| A_current_review | [0.208145, 0.214024] |
| D_epic_only_base | [0.169457, 0.172130] |
| D_full | [0.106441, 0.110259] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.122263, -0.118064] |
| D_epic_only_base - B_global_current_gs | [-0.059553, -0.055887] |
| B_global_current_gs - C_category_probability | [0.003340, 0.004122] |

## curve_baseline/baili_marginal_low/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238179, 0.244724] |
| C_category_probability | [0.233811, 0.240715] |
| A_current_review | [0.219680, 0.226261] |
| D_epic_only_base | [0.178468, 0.181749] |
| D_full | [0.105157, 0.109351] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.136452, -0.131943] |
| D_epic_only_base - B_global_current_gs | [-0.063263, -0.059422] |
| B_global_current_gs - C_category_probability | [0.003806, 0.004572] |

## curve_baseline/all_stop/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| A_current_review | [0.144151, 0.147777] |
| D_epic_only_all_stop | [0.120181, 0.121741] |
| D_full | [0.108020, 0.111382] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.049742, -0.044625] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037456, -0.034390] |
| B_global_current_gs - C_category_probability | [0.000462, 0.001370] |

## curve_baseline/all_stop/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| A_current_review | [0.144151, 0.147777] |
| D_epic_only_all_stop | [0.120181, 0.121741] |
| D_full | [0.106441, 0.110259] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.051291, -0.045776] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037456, -0.034390] |
| B_global_current_gs - C_category_probability | [0.000462, 0.001370] |

## curve_baseline/all_stop/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| A_current_review | [0.144151, 0.147777] |
| D_epic_only_all_stop | [0.120181, 0.121741] |
| D_full | [0.105157, 0.109351] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.052555, -0.046705] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037456, -0.034390] |
| B_global_current_gs - C_category_probability | [0.000462, 0.001370] |

## tier2_low/baili_marginal_low/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212671, 0.217590] |
| C_category_probability | [0.209158, 0.214620] |
| A_current_review | [0.196220, 0.201441] |
| D_epic_only_base | [0.160187, 0.162284] |
| D_full | [0.107563, 0.110709] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.108043, -0.103946] |
| D_epic_only_base - B_global_current_gs | [-0.055654, -0.052136] |
| B_global_current_gs - C_category_probability | [0.002842, 0.003641] |

## tier2_low/baili_marginal_low/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225638, 0.231363] |
| C_category_probability | [0.221683, 0.227856] |
| A_current_review | [0.208127, 0.214018] |
| D_epic_only_base | [0.169415, 0.172102] |
| D_full | [0.105940, 0.109504] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.122978, -0.118578] |
| D_epic_only_base - B_global_current_gs | [-0.059583, -0.055901] |
| B_global_current_gs - C_category_probability | [0.003340, 0.004121] |

## tier2_low/baili_marginal_low/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238161, 0.244715] |
| C_category_probability | [0.233793, 0.240707] |
| A_current_review | [0.219663, 0.226254] |
| D_epic_only_base | [0.178427, 0.181721] |
| D_full | [0.104620, 0.108528] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.137244, -0.132485] |
| D_epic_only_base - B_global_current_gs | [-0.063292, -0.059437] |
| B_global_current_gs - C_category_probability | [0.003806, 0.004571] |

## tier2_low/all_stop/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| A_current_review | [0.144125, 0.147777] |
| D_epic_only_all_stop | [0.120141, 0.121707] |
| D_full | [0.107563, 0.110709] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.050221, -0.045245] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037495, -0.034396] |
| B_global_current_gs - C_category_probability | [0.000462, 0.001369] |

## tier2_low/all_stop/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| A_current_review | [0.144125, 0.147777] |
| D_epic_only_all_stop | [0.120141, 0.121707] |
| D_full | [0.105940, 0.109504] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.051816, -0.046478] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037495, -0.034396] |
| B_global_current_gs - C_category_probability | [0.000462, 0.001369] |

## tier2_low/all_stop/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| A_current_review | [0.144125, 0.147777] |
| D_epic_only_all_stop | [0.120141, 0.121707] |
| D_full | [0.104620, 0.108528] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.053117, -0.047474] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037495, -0.034396] |
| B_global_current_gs - C_category_probability | [0.000462, 0.001369] |

## tier2_mid/baili_marginal_low/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213454, 0.218322] |
| C_category_probability | [0.209928, 0.215339] |
| A_current_review | [0.196944, 0.202112] |
| D_epic_only_base | [0.161258, 0.163339] |
| D_full | [0.110981, 0.115015] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.104816, -0.100963] |
| D_epic_only_base - B_global_current_gs | [-0.055346, -0.051832] |
| B_global_current_gs - C_category_probability | [0.002840, 0.003668] |

## tier2_mid/baili_marginal_low/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226444, 0.232142] |
| C_category_probability | [0.222478, 0.228619] |
| A_current_review | [0.208875, 0.214731] |
| D_epic_only_base | [0.170498, 0.173186] |
| D_full | [0.109641, 0.114223] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.119366, -0.115355] |
| D_epic_only_base - B_global_current_gs | [-0.059292, -0.055611] |
| B_global_current_gs - C_category_probability | [0.003340, 0.004149] |

## tier2_mid/baili_marginal_low/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238993, 0.245538] |
| C_category_probability | [0.234612, 0.241511] |
| A_current_review | [0.220435, 0.227006] |
| D_epic_only_base | [0.179524, 0.182830] |
| D_full | [0.108551, 0.113583] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.133305, -0.129092] |
| D_epic_only_base - B_global_current_gs | [-0.063017, -0.059159] |
| B_global_current_gs - C_category_probability | [0.003807, 0.004600] |

## tier2_mid/all_stop/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| A_current_review | [0.144758, 0.148257] |
| D_epic_only_all_stop | [0.121168, 0.122634] |
| D_full | [0.110981, 0.115015] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.047276, -0.041672] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037110, -0.034032] |
| B_global_current_gs - C_category_probability | [0.000455, 0.001390] |

## tier2_mid/all_stop/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| A_current_review | [0.144758, 0.148257] |
| D_epic_only_all_stop | [0.121168, 0.122634] |
| D_full | [0.109641, 0.114223] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.048585, -0.042495] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037110, -0.034032] |
| B_global_current_gs - C_category_probability | [0.000455, 0.001390] |

## tier2_mid/all_stop/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| A_current_review | [0.144758, 0.148257] |
| D_epic_only_all_stop | [0.121168, 0.122634] |
| D_full | [0.108551, 0.113583] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.049652, -0.043158] |
| D_epic_only_all_stop - B_global_current_gs | [-0.037110, -0.034032] |
| B_global_current_gs - C_category_probability | [0.000455, 0.001390] |

## tier2_high/baili_marginal_low/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213831, 0.218693] |
| C_category_probability | [0.210301, 0.215703] |
| A_current_review | [0.197295, 0.202451] |
| D_epic_only_base | [0.161763, 0.163865] |
| D_full | [0.112448, 0.116847] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.103539, -0.099690] |
| D_epic_only_base - B_global_current_gs | [-0.055209, -0.051687] |
| B_global_current_gs - C_category_probability | [0.002840, 0.003681] |

## tier2_high/baili_marginal_low/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226833, 0.232537] |
| C_category_probability | [0.222862, 0.229004] |
| A_current_review | [0.209237, 0.215091] |
| D_epic_only_base | [0.171010, 0.173725] |
| D_full | [0.111227, 0.116220] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.117945, -0.113978] |
| D_epic_only_base - B_global_current_gs | [-0.059163, -0.055472] |
| B_global_current_gs - C_category_probability | [0.003340, 0.004163] |

## tier2_high/baili_marginal_low/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.239395, 0.245954] |
| C_category_probability | [0.235009, 0.241918] |
| A_current_review | [0.220809, 0.227386] |
| D_epic_only_base | [0.180043, 0.183382] |
| D_full | [0.110235, 0.115713] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.131760, -0.127641] |
| D_epic_only_base - B_global_current_gs | [-0.062895, -0.059028] |
| B_global_current_gs - C_category_probability | [0.003807, 0.004615] |

## tier2_high/all_stop/yield_minus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| A_current_review | [0.145061, 0.148502] |
| D_epic_only_all_stop | [0.121656, 0.123089] |
| D_full | [0.112448, 0.116847] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.046057, -0.040186] |
| D_epic_only_all_stop - B_global_current_gs | [-0.036939, -0.033854] |
| B_global_current_gs - C_category_probability | [0.000452, 0.001400] |

## tier2_high/all_stop/baseline

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| A_current_review | [0.145061, 0.148502] |
| D_epic_only_all_stop | [0.121656, 0.123089] |
| D_full | [0.111227, 0.116220] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.047246, -0.040844] |
| D_epic_only_all_stop - B_global_current_gs | [-0.036939, -0.033854] |
| B_global_current_gs - C_category_probability | [0.000452, 0.001400] |

## tier2_high/all_stop/yield_plus_20pct

| 候选 | 含22速价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| A_current_review | [0.145061, 0.148502] |
| D_epic_only_all_stop | [0.121656, 0.123089] |
| D_full | [0.110235, 0.115713] |

| 成对差值 | 95% CI |
|---|---:|
| D_full - B_global_current_gs | [-0.048216, -0.041373] |
| D_epic_only_all_stop - B_global_current_gs | [-0.036939, -0.033854] |
| B_global_current_gs - C_category_probability | [0.000452, 0.001400] |

## 主场景资源与终局产出

主场景为 `curve_baseline/baili_marginal_low/baseline`。数值为五个 seed 的每联合批次均值；每批固定支付 85 维度裂缝体力，再按一次圣女瓶颈补充。

| 候选 | 含22速价值/100体力 | 正式价值/100体力 | 总体力/批 | 粉末单位/批 | 下级石需求/批 | 材料+转换-出售金币/批 | 圣女补充体力/批 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B_global_current_gs | 0.228514 | 0.228460 | 104.278 | 48.376 | 3.225 | 117142.30 | 19.278 |
| C_category_probability | 0.224783 | 0.224731 | 108.575 | 56.574 | 3.772 | 131846.52 | 23.575 |
| A_current_review | 0.211085 | 0.211037 | 116.110 | 71.872 | 4.791 | 159828.39 | 31.110 |
| D_epic_only_base | 0.170794 | 0.170717 | 156.135 | 135.782 | 9.052 | 334364.67 | 71.135 |
| D_full | 0.108350 | 0.107243 | 305.818 | 458.518 | 30.568 | 1123002.35 | 220.818 |

### D 的可重放终局计数

D 专用分片保存了 75+、转换后75+、22速、输出GS>=60与节点。冻结 A/B/C 分片在研究开始前没有保存这些原始计数，故不能在不重跑 A/B/C 的前提下反推；报告只使用其已冻结的价值和完整资源账本作排序。

| 候选/背景 | 原生75+/100批 | 转换后75+/100批 | 22速/100批 | 输出GS>=60/100批 | 原生75+每件总体力 |
|---|---:|---:|---:|---:|---:|
| D_full | 1.7748 | 1.6363 | 0.2741 | 0.2563 | 17231.06 |
| D_epic_only_base | 1.7712 | 1.6318 | 0.0349 | 0.2563 | 8815.05 |

### D 节点到达与止损

| D候选/背景 | +0 | +3 | +6 | +9 | +12 | +15 | 平均止损成本/批 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D_full 到达 | 4.5699 | 3.2661 | 3.0105 | 2.0146 | 1.0748 | 1.0748 | 225.7927 |
| D_full 停止 | 1.3039 | 0.2556 | 0.9959 | 0.9398 | 0.0000 | 1.0748 | - |
| D_epic_only_base 到达 | 1.0000 | 0.5886 | 0.4619 | 0.3659 | 0.3010 | 0.3010 | 67.6045 |
| D_epic_only_base 停止 | 0.4114 | 0.1267 | 0.0960 | 0.0649 | 0.0000 | 0.3010 | - |

### 每100,000总体力 D 产出

| 候选/背景 | 原生75+ | 转换后75+ | 22速 | 输出GS>=60 |
|---|---:|---:|---:|---:|
| D_full | 5.8035 | 5.3507 | 0.8963 | 0.8379 |
| D_epic_only_base | 11.3442 | 10.4515 | 0.2236 | 1.6412 |
## 说明

- `D_full`：Epic、Heroic 均执行截图阈值。
- `D_epic_only_base` / `D_epic_only_all_stop`：只替换 Epic，Heroic 分别使用冻结基础回退/全停背景；不与 D_full 混为同一策略结论。
- D 原始 JSON 对每个 seed 保存原生75+、转换后75+、22速、输出有效GS>=60和节点；冻结 A/B/C 分片不具备这些历史字段，不能诚实反推。
- 配对区间按同一 seed、装备和确定性公共轨迹的价值率差计算，不使用独立候选区间代替。
<!-- terminal-production:start -->
## 终局产量补全

本章节仅补解释性产量统计。A/B/C 使用冻结策略哈希、同一装备、5个 seed、每件5,000轨迹和相同 random_seed 派生确定性重放；D 直接读取既有 D 专用分片。未重新评估排序或发布判断。

主场景为 Heroic 基础回退、基线 Heroic 产出。每联合批次固定为 1 Epic + 85/23.81 Heroic（estimated），资源分母为 85 维度裂缝体力加一次圣女瓶颈补充。

| 候选 | 原生75+/100批 | 转换75+/100批 | 22速/100批 | 输出60/100批 | 总体力/批 |
|---|---:|---:|---:|---:|---:|
| A_current_review | 0.4030 | 0.5493 | 0.0204 | 0.2529 | 116.110 |
| B_global_current_gs | 0.3987 | 0.5454 | 0.0198 | 0.2529 | 104.278 |
| C_category_probability | 0.3994 | 0.5458 | 0.0203 | 0.2498 | 108.575 |
| D_full | 1.7748 | 1.6363 | 0.2741 | 0.2563 | 305.818 |
| D_epic_only_base | 1.7721 | 1.6363 | 0.0412 | 0.2563 | 156.135 |

| 候选 | 原生75+每件体力 | 转换75+每件体力 | 22速每件体力 | 输出60每件体力 |
|---|---:|---:|---:|---:|
| A_current_review | 28809.14 | 21138.70 | 570256.00 | 45909.79 |
| B_global_current_gs | 26155.44 | 19119.56 | 525966.01 | 41231.26 |
| C_category_probability | 27187.58 | 19892.76 | 535003.66 | 43470.59 |
| D_full | 17231.06 | 18689.60 | 111571.11 | 119341.74 |
| D_epic_only_base | 8810.61 | 9541.97 | 379303.06 | 60929.90 |

### Epic、Heroic 分项（每联合批次）

| 候选 | Epic原生75+ | Heroic原生75+ | Epic转换75+ | Heroic转换75+ | Epic22速 | Heroic22速 |
|---|---:|---:|---:|---:|---:|---:|
| A_current_review | 0.00402 | 0.00001 | 0.00545 | 0.00004 | 0.00014 | 0.00006 |
| B_global_current_gs | 0.00398 | 0.00001 | 0.00541 | 0.00004 | 0.00014 | 0.00006 |
| C_category_probability | 0.00398 | 0.00001 | 0.00541 | 0.00004 | 0.00014 | 0.00006 |
| D_full | 0.01771 | 0.00004 | 0.01632 | 0.00004 | 0.00035 | 0.00239 |
| D_epic_only_base | 0.01771 | 0.00001 | 0.01632 | 0.00004 | 0.00035 | 0.00006 |

### 每100,000总体力

| 候选 | 原生75+ | 转换75+ | 22速 | 输出60 |
|---|---:|---:|---:|---:|
| A_current_review | 3.4711 | 4.7306 | 0.1754 | 2.1782 |
| B_global_current_gs | 3.8233 | 5.2302 | 0.1901 | 2.4253 |
| C_category_probability | 3.6781 | 5.0269 | 0.1869 | 2.3004 |
| D_full | 5.8035 | 5.3507 | 0.8963 | 0.8379 |
| D_epic_only_base | 11.3500 | 10.4800 | 0.2636 | 1.6412 |

### Heroic 全停背景对照（每100联合批次）

| 候选 | 原生75+ | 转换75+ | 22速 | 输出60 | 总体力/批 |
|---|---:|---:|---:|---:|---:|
| A_current_review | 0.4021 | 0.5448 | 0.0141 | 0.2529 | 107.460 |
| B_global_current_gs | 0.3978 | 0.5409 | 0.0136 | 0.2529 | 95.645 |
| C_category_probability | 0.3985 | 0.5413 | 0.0140 | 0.2498 | 99.905 |
| D_full | 1.7748 | 1.6363 | 0.2741 | 0.2563 | 305.818 |
| D_epic_only_all_stop | 1.7712 | 1.6318 | 0.0349 | 0.2563 | 147.512 |

### 相同 seed 成对差值95%区间（每联合批次）

| 对比 | 原生75+ | 转换75+ | 22速 | 输出60 |
|---|---:|---:|---:|---:|
| A_current_review - B_global_current_gs | [0.00002, 0.00006] | [0.00003, 0.00005] | [0.00000, 0.00001] | [0.00000, 0.00000] |
| B_global_current_gs - C_category_probability | [-0.00002, 0.00001] | [-0.00002, 0.00001] | [-0.00001, -0.00000] | [0.00002, 0.00004] |
| D_full - B_global_current_gs | [0.01358, 0.01394] | [0.01066, 0.01116] | [0.00220, 0.00288] | [0.00001, 0.00005] |
| D_epic_only_base - B_global_current_gs | [0.01355, 0.01392] | [0.01066, 0.01116] | [0.00019, 0.00024] | [0.00001, 0.00005] |

### 解释边界

- 原生75+使用重铸后全部副属性官方总GS；转换75+在合法满值转换实际应用后独立统计，二者不可相加。
- 22速仅终局非鞋速度>=22；输出60仅合法普通输出体系有效GS>=60。
- 产量较多不等于单位总体力效率更高；本章节不改变已冻结的 B 第一、D 淘汰与48件前瞻盲收结论。

<!-- terminal-production:end -->
