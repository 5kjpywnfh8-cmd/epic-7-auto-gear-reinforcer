# 维度裂缝与圣女材料联合资源池复核

主分母为 `85 维度裂缝体力 + 一次圣女 3-7 瓶颈补充体力`。圣女仅是金币/基础强化经验机会成本基线，不被视为下级石实际掉落来源。

研究规模：5 个独立 seed、每件 5000 条轨迹；本轮新跑分片 3790 个。

| 口径 | 分母 |
|---|---|
| 旧标量信用 | `80.607613 + 各路径独立瓶颈体力` |
| 显式本批资源池 | `85 + max(汇总金币缺口/金币产率, 汇总经验缺口/经验产率)` |
| 长期跨批 | 显式本批分母减去未使用来源石的经验机会价值；本轮仅在石头盈余时不同 |

## 固定来源

| 项目 | 每联合批次 |
|---|---:|
| 维度裂缝体力 | 85 |
| Epic | 1 |
| Heroic | 3.569929 (estimated) |
| 下级石 | 0.425 |
| 来源金币 | 127500 |

## 场景排序

| Heroic / 产出率 | 口径 | 第一名 | 第一名-第二名 95% CI |
|---|---|---|---:|
| curve_baseline/baili_marginal_low/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.003012, 0.003797] |
| curve_baseline/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.002842, 0.003642] |
| curve_baseline/baili_marginal_low/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.002842, 0.003642] |
| curve_baseline/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.002842, 0.003642] |
| curve_baseline/baili_marginal_low/baseline | old_scalar_credit | B_global_current_gs | [0.003500, 0.004266] |
| curve_baseline/baili_marginal_low/baseline | explicit_batch_gold_on | B_global_current_gs | [0.003340, 0.004122] |
| curve_baseline/baili_marginal_low/baseline | explicit_long_cross_batch | B_global_current_gs | [0.003340, 0.004122] |
| curve_baseline/baili_marginal_low/baseline | explicit_batch_gold_off | B_global_current_gs | [0.003340, 0.004122] |
| curve_baseline/baili_marginal_low/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.003954, 0.004705] |
| curve_baseline/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.003806, 0.004572] |
| curve_baseline/baili_marginal_low/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.003806, 0.004572] |
| curve_baseline/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.003806, 0.004572] |
| curve_baseline/all_stop/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.000664, 0.001557] |
| curve_baseline/all_stop/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/baseline | old_scalar_credit | B_global_current_gs | [0.000664, 0.001557] |
| curve_baseline/all_stop/baseline | explicit_batch_gold_on | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/baseline | explicit_long_cross_batch | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/baseline | explicit_batch_gold_off | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.000664, 0.001557] |
| curve_baseline/all_stop/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000462, 0.001370] |
| curve_baseline/all_stop/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000462, 0.001370] |
| tier2_low/baili_marginal_low/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.003012, 0.003796] |
| tier2_low/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.002842, 0.003641] |
| tier2_low/baili_marginal_low/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.002842, 0.003641] |
| tier2_low/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.002842, 0.003641] |
| tier2_low/baili_marginal_low/baseline | old_scalar_credit | B_global_current_gs | [0.003500, 0.004265] |
| tier2_low/baili_marginal_low/baseline | explicit_batch_gold_on | B_global_current_gs | [0.003340, 0.004121] |
| tier2_low/baili_marginal_low/baseline | explicit_long_cross_batch | B_global_current_gs | [0.003340, 0.004121] |
| tier2_low/baili_marginal_low/baseline | explicit_batch_gold_off | B_global_current_gs | [0.003340, 0.004121] |
| tier2_low/baili_marginal_low/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.003954, 0.004704] |
| tier2_low/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.003806, 0.004571] |
| tier2_low/baili_marginal_low/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.003806, 0.004571] |
| tier2_low/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.003806, 0.004571] |
| tier2_low/all_stop/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.000664, 0.001556] |
| tier2_low/all_stop/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/baseline | old_scalar_credit | B_global_current_gs | [0.000664, 0.001556] |
| tier2_low/all_stop/baseline | explicit_batch_gold_on | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/baseline | explicit_long_cross_batch | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/baseline | explicit_batch_gold_off | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.000664, 0.001556] |
| tier2_low/all_stop/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000462, 0.001369] |
| tier2_low/all_stop/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000462, 0.001369] |
| tier2_mid/baili_marginal_low/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.003012, 0.003823] |
| tier2_mid/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.002840, 0.003668] |
| tier2_mid/baili_marginal_low/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.002840, 0.003668] |
| tier2_mid/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.002840, 0.003668] |
| tier2_mid/baili_marginal_low/baseline | old_scalar_credit | B_global_current_gs | [0.003501, 0.004294] |
| tier2_mid/baili_marginal_low/baseline | explicit_batch_gold_on | B_global_current_gs | [0.003340, 0.004149] |
| tier2_mid/baili_marginal_low/baseline | explicit_long_cross_batch | B_global_current_gs | [0.003340, 0.004149] |
| tier2_mid/baili_marginal_low/baseline | explicit_batch_gold_off | B_global_current_gs | [0.003340, 0.004149] |
| tier2_mid/baili_marginal_low/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.003956, 0.004734] |
| tier2_mid/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.003807, 0.004600] |
| tier2_mid/baili_marginal_low/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.003807, 0.004600] |
| tier2_mid/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.003807, 0.004600] |
| tier2_mid/all_stop/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.000658, 0.001578] |
| tier2_mid/all_stop/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/baseline | old_scalar_credit | B_global_current_gs | [0.000658, 0.001578] |
| tier2_mid/all_stop/baseline | explicit_batch_gold_on | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/baseline | explicit_long_cross_batch | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/baseline | explicit_batch_gold_off | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.000658, 0.001578] |
| tier2_mid/all_stop/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000455, 0.001390] |
| tier2_mid/all_stop/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000455, 0.001390] |
| tier2_high/baili_marginal_low/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.003011, 0.003837] |
| tier2_high/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.002840, 0.003681] |
| tier2_high/baili_marginal_low/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.002840, 0.003681] |
| tier2_high/baili_marginal_low/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.002840, 0.003681] |
| tier2_high/baili_marginal_low/baseline | old_scalar_credit | B_global_current_gs | [0.003501, 0.004308] |
| tier2_high/baili_marginal_low/baseline | explicit_batch_gold_on | B_global_current_gs | [0.003340, 0.004163] |
| tier2_high/baili_marginal_low/baseline | explicit_long_cross_batch | B_global_current_gs | [0.003340, 0.004163] |
| tier2_high/baili_marginal_low/baseline | explicit_batch_gold_off | B_global_current_gs | [0.003340, 0.004163] |
| tier2_high/baili_marginal_low/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.003957, 0.004749] |
| tier2_high/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.003807, 0.004615] |
| tier2_high/baili_marginal_low/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.003807, 0.004615] |
| tier2_high/baili_marginal_low/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.003807, 0.004615] |
| tier2_high/all_stop/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.000655, 0.001588] |
| tier2_high/all_stop/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/baseline | old_scalar_credit | B_global_current_gs | [0.000655, 0.001588] |
| tier2_high/all_stop/baseline | explicit_batch_gold_on | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/baseline | explicit_long_cross_batch | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/baseline | explicit_batch_gold_off | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.000655, 0.001588] |
| tier2_high/all_stop/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000452, 0.001400] |
| tier2_high/all_stop/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000452, 0.001400] |

## 全部 Epic 候选价值率

### curve_baseline/baili_marginal_low/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.210958, 0.215836] |
| C_category_probability | [0.207290, 0.212695] |
| H_gs_stamina_efficiency | [0.207010, 0.212408] |
| I_high_recall_efficiency | [0.206738, 0.212093] |
| J_structure_conversion | [0.205940, 0.211364] |
| A_current_review | [0.194535, 0.199702] |
| G_category_slot_probability | [0.188325, 0.191846] |
| D_category_slot_gs | [0.187718, 0.191360] |
| E_category_slot_main | [0.187718, 0.191360] |
| F_category_current_gs | [0.187718, 0.191360] |

### curve_baseline/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212692, 0.217597] |
| C_category_probability | [0.209179, 0.214626] |
| H_gs_stamina_efficiency | [0.208896, 0.214338] |
| I_high_recall_efficiency | [0.208617, 0.214014] |
| J_structure_conversion | [0.207786, 0.213253] |
| A_current_review | [0.196239, 0.201446] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### curve_baseline/baili_marginal_low/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212692, 0.217597] |
| C_category_probability | [0.209179, 0.214626] |
| H_gs_stamina_efficiency | [0.208896, 0.214338] |
| I_high_recall_efficiency | [0.208617, 0.214014] |
| J_structure_conversion | [0.207786, 0.213253] |
| A_current_review | [0.196239, 0.201446] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### curve_baseline/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212692, 0.217597] |
| C_category_probability | [0.209179, 0.214626] |
| H_gs_stamina_efficiency | [0.208896, 0.214338] |
| I_high_recall_efficiency | [0.208617, 0.214014] |
| J_structure_conversion | [0.207786, 0.213253] |
| A_current_review | [0.196239, 0.201446] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### curve_baseline/baili_marginal_low/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.223767, 0.229455] |
| C_category_probability | [0.219669, 0.225787] |
| H_gs_stamina_efficiency | [0.219349, 0.225461] |
| I_high_recall_efficiency | [0.219059, 0.225124] |
| J_structure_conversion | [0.218211, 0.224342] |
| A_current_review | [0.206305, 0.212144] |
| G_category_slot_probability | [0.202225, 0.206680] |
| D_category_slot_gs | [0.201575, 0.206136] |
| E_category_slot_main | [0.201575, 0.206136] |
| F_category_current_gs | [0.201575, 0.206136] |

### curve_baseline/baili_marginal_low/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225657, 0.231371] |
| C_category_probability | [0.221703, 0.227862] |
| H_gs_stamina_efficiency | [0.221380, 0.227535] |
| I_high_recall_efficiency | [0.221082, 0.227189] |
| J_structure_conversion | [0.220201, 0.226374] |
| A_current_review | [0.208145, 0.214024] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### curve_baseline/baili_marginal_low/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225657, 0.231371] |
| C_category_probability | [0.221703, 0.227862] |
| H_gs_stamina_efficiency | [0.221380, 0.227535] |
| I_high_recall_efficiency | [0.221082, 0.227189] |
| J_structure_conversion | [0.220201, 0.226374] |
| A_current_review | [0.208145, 0.214024] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### curve_baseline/baili_marginal_low/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225657, 0.231371] |
| C_category_probability | [0.221703, 0.227862] |
| H_gs_stamina_efficiency | [0.221380, 0.227535] |
| I_high_recall_efficiency | [0.221082, 0.227189] |
| J_structure_conversion | [0.220201, 0.226374] |
| A_current_review | [0.208145, 0.214024] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### curve_baseline/baili_marginal_low/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.236131, 0.242650] |
| C_category_probability | [0.231630, 0.238492] |
| H_gs_stamina_efficiency | [0.231272, 0.238130] |
| I_high_recall_efficiency | [0.230967, 0.237773] |
| J_structure_conversion | [0.230072, 0.236939] |
| A_current_review | [0.217702, 0.224243] |
| G_category_slot_probability | [0.215619, 0.221022] |
| D_category_slot_gs | [0.214929, 0.220426] |
| E_category_slot_main | [0.214929, 0.220426] |
| F_category_current_gs | [0.214929, 0.220426] |

### curve_baseline/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238179, 0.244724] |
| C_category_probability | [0.233811, 0.240715] |
| H_gs_stamina_efficiency | [0.233451, 0.240350] |
| I_high_recall_efficiency | [0.233136, 0.239984] |
| J_structure_conversion | [0.232208, 0.239119] |
| A_current_review | [0.219680, 0.226261] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### curve_baseline/baili_marginal_low/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238179, 0.244724] |
| C_category_probability | [0.233811, 0.240715] |
| H_gs_stamina_efficiency | [0.233451, 0.240350] |
| I_high_recall_efficiency | [0.233136, 0.239984] |
| J_structure_conversion | [0.232208, 0.239119] |
| A_current_review | [0.219680, 0.226261] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### curve_baseline/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238179, 0.244724] |
| C_category_probability | [0.233811, 0.240715] |
| H_gs_stamina_efficiency | [0.233451, 0.240350] |
| I_high_recall_efficiency | [0.233136, 0.239984] |
| J_structure_conversion | [0.232208, 0.239119] |
| A_current_review | [0.219680, 0.226261] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### curve_baseline/all_stop/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154175, 0.157259] |
| C_category_probability | [0.152712, 0.156502] |
| H_gs_stamina_efficiency | [0.152630, 0.156393] |
| I_high_recall_efficiency | [0.152432, 0.156195] |
| J_structure_conversion | [0.151910, 0.155693] |
| A_current_review | [0.142972, 0.146557] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### curve_baseline/all_stop/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### curve_baseline/all_stop/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### curve_baseline/all_stop/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### curve_baseline/all_stop/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154175, 0.157259] |
| C_category_probability | [0.152712, 0.156502] |
| H_gs_stamina_efficiency | [0.152630, 0.156393] |
| I_high_recall_efficiency | [0.152432, 0.156195] |
| J_structure_conversion | [0.151910, 0.155693] |
| A_current_review | [0.142972, 0.146557] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### curve_baseline/all_stop/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### curve_baseline/all_stop/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### curve_baseline/all_stop/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### curve_baseline/all_stop/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154175, 0.157259] |
| C_category_probability | [0.152712, 0.156502] |
| H_gs_stamina_efficiency | [0.152630, 0.156393] |
| I_high_recall_efficiency | [0.152432, 0.156195] |
| J_structure_conversion | [0.151910, 0.155693] |
| A_current_review | [0.142972, 0.146557] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### curve_baseline/all_stop/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### curve_baseline/all_stop/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### curve_baseline/all_stop/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155328, 0.158440] |
| C_category_probability | [0.154051, 0.157884] |
| H_gs_stamina_efficiency | [0.153967, 0.157774] |
| I_high_recall_efficiency | [0.153761, 0.157567] |
| J_structure_conversion | [0.153205, 0.157032] |
| A_current_review | [0.144151, 0.147777] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### tier2_low/baili_marginal_low/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.210937, 0.215830] |
| C_category_probability | [0.207269, 0.212690] |
| H_gs_stamina_efficiency | [0.206989, 0.212403] |
| I_high_recall_efficiency | [0.206717, 0.212088] |
| J_structure_conversion | [0.205920, 0.211359] |
| A_current_review | [0.194516, 0.199696] |
| G_category_slot_probability | [0.188325, 0.191846] |
| D_category_slot_gs | [0.187718, 0.191360] |
| E_category_slot_main | [0.187718, 0.191360] |
| F_category_current_gs | [0.187718, 0.191360] |

### tier2_low/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212671, 0.217590] |
| C_category_probability | [0.209158, 0.214620] |
| H_gs_stamina_efficiency | [0.208875, 0.214332] |
| I_high_recall_efficiency | [0.208596, 0.214008] |
| J_structure_conversion | [0.207765, 0.213248] |
| A_current_review | [0.196220, 0.201441] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### tier2_low/baili_marginal_low/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212671, 0.217590] |
| C_category_probability | [0.209158, 0.214620] |
| H_gs_stamina_efficiency | [0.208875, 0.214332] |
| I_high_recall_efficiency | [0.208596, 0.214008] |
| J_structure_conversion | [0.207765, 0.213248] |
| A_current_review | [0.196220, 0.201441] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### tier2_low/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212671, 0.217590] |
| C_category_probability | [0.209158, 0.214620] |
| H_gs_stamina_efficiency | [0.208875, 0.214332] |
| I_high_recall_efficiency | [0.208596, 0.214008] |
| J_structure_conversion | [0.207765, 0.213248] |
| A_current_review | [0.196220, 0.201441] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### tier2_low/baili_marginal_low/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.223748, 0.229448] |
| C_category_probability | [0.219650, 0.225781] |
| H_gs_stamina_efficiency | [0.219329, 0.225455] |
| I_high_recall_efficiency | [0.219040, 0.225118] |
| J_structure_conversion | [0.218192, 0.224335] |
| A_current_review | [0.206287, 0.212138] |
| G_category_slot_probability | [0.202225, 0.206680] |
| D_category_slot_gs | [0.201575, 0.206136] |
| E_category_slot_main | [0.201575, 0.206136] |
| F_category_current_gs | [0.201575, 0.206136] |

### tier2_low/baili_marginal_low/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225638, 0.231363] |
| C_category_probability | [0.221683, 0.227856] |
| H_gs_stamina_efficiency | [0.221361, 0.227528] |
| I_high_recall_efficiency | [0.221063, 0.227182] |
| J_structure_conversion | [0.220182, 0.226368] |
| A_current_review | [0.208127, 0.214018] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### tier2_low/baili_marginal_low/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225638, 0.231363] |
| C_category_probability | [0.221683, 0.227856] |
| H_gs_stamina_efficiency | [0.221361, 0.227528] |
| I_high_recall_efficiency | [0.221063, 0.227182] |
| J_structure_conversion | [0.220182, 0.226368] |
| A_current_review | [0.208127, 0.214018] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### tier2_low/baili_marginal_low/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225638, 0.231363] |
| C_category_probability | [0.221683, 0.227856] |
| H_gs_stamina_efficiency | [0.221361, 0.227528] |
| I_high_recall_efficiency | [0.221063, 0.227182] |
| J_structure_conversion | [0.220182, 0.226368] |
| A_current_review | [0.208127, 0.214018] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### tier2_low/baili_marginal_low/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.236114, 0.242642] |
| C_category_probability | [0.231612, 0.238485] |
| H_gs_stamina_efficiency | [0.231255, 0.238123] |
| I_high_recall_efficiency | [0.230949, 0.237766] |
| J_structure_conversion | [0.230054, 0.236932] |
| A_current_review | [0.217685, 0.224236] |
| G_category_slot_probability | [0.215619, 0.221022] |
| D_category_slot_gs | [0.214929, 0.220426] |
| E_category_slot_main | [0.214929, 0.220426] |
| F_category_current_gs | [0.214929, 0.220426] |

### tier2_low/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238161, 0.244715] |
| C_category_probability | [0.233793, 0.240707] |
| H_gs_stamina_efficiency | [0.233432, 0.240343] |
| I_high_recall_efficiency | [0.233118, 0.239976] |
| J_structure_conversion | [0.232190, 0.239111] |
| A_current_review | [0.219663, 0.226254] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### tier2_low/baili_marginal_low/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238161, 0.244715] |
| C_category_probability | [0.233793, 0.240707] |
| H_gs_stamina_efficiency | [0.233432, 0.240343] |
| I_high_recall_efficiency | [0.233118, 0.239976] |
| J_structure_conversion | [0.232190, 0.239111] |
| A_current_review | [0.219663, 0.226254] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### tier2_low/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238161, 0.244715] |
| C_category_probability | [0.233793, 0.240707] |
| H_gs_stamina_efficiency | [0.233432, 0.240343] |
| I_high_recall_efficiency | [0.233118, 0.239976] |
| J_structure_conversion | [0.232190, 0.239111] |
| A_current_review | [0.219663, 0.226254] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### tier2_low/all_stop/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154146, 0.157260] |
| C_category_probability | [0.152683, 0.156502] |
| H_gs_stamina_efficiency | [0.152601, 0.156393] |
| I_high_recall_efficiency | [0.152403, 0.156195] |
| J_structure_conversion | [0.151882, 0.155693] |
| A_current_review | [0.142946, 0.146557] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### tier2_low/all_stop/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### tier2_low/all_stop/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### tier2_low/all_stop/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### tier2_low/all_stop/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154146, 0.157260] |
| C_category_probability | [0.152683, 0.156502] |
| H_gs_stamina_efficiency | [0.152601, 0.156393] |
| I_high_recall_efficiency | [0.152403, 0.156195] |
| J_structure_conversion | [0.151882, 0.155693] |
| A_current_review | [0.142946, 0.146557] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### tier2_low/all_stop/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### tier2_low/all_stop/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### tier2_low/all_stop/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### tier2_low/all_stop/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154146, 0.157260] |
| C_category_probability | [0.152683, 0.156502] |
| H_gs_stamina_efficiency | [0.152601, 0.156393] |
| I_high_recall_efficiency | [0.152403, 0.156195] |
| J_structure_conversion | [0.151882, 0.155693] |
| A_current_review | [0.142946, 0.146557] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### tier2_low/all_stop/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### tier2_low/all_stop/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### tier2_low/all_stop/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155298, 0.158440] |
| C_category_probability | [0.154022, 0.157884] |
| H_gs_stamina_efficiency | [0.153939, 0.157774] |
| I_high_recall_efficiency | [0.153732, 0.157568] |
| J_structure_conversion | [0.153177, 0.157032] |
| A_current_review | [0.144125, 0.147777] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### tier2_mid/baili_marginal_low/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.211712, 0.216557] |
| C_category_probability | [0.208032, 0.213402] |
| H_gs_stamina_efficiency | [0.207747, 0.213115] |
| I_high_recall_efficiency | [0.207475, 0.212798] |
| J_structure_conversion | [0.206680, 0.212063] |
| A_current_review | [0.195233, 0.200362] |
| G_category_slot_probability | [0.189093, 0.192587] |
| D_category_slot_gs | [0.188491, 0.192095] |
| E_category_slot_main | [0.188491, 0.192095] |
| F_category_current_gs | [0.188491, 0.192095] |

### tier2_mid/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213454, 0.218322] |
| C_category_probability | [0.209928, 0.215339] |
| H_gs_stamina_efficiency | [0.209641, 0.215050] |
| I_high_recall_efficiency | [0.209360, 0.214724] |
| J_structure_conversion | [0.208533, 0.213957] |
| A_current_review | [0.196944, 0.202112] |
| G_category_slot_probability | [0.190512, 0.194016] |
| D_category_slot_gs | [0.189886, 0.193503] |
| E_category_slot_main | [0.189886, 0.193503] |
| F_category_current_gs | [0.189886, 0.193503] |

### tier2_mid/baili_marginal_low/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213454, 0.218322] |
| C_category_probability | [0.209928, 0.215339] |
| H_gs_stamina_efficiency | [0.209641, 0.215050] |
| I_high_recall_efficiency | [0.209360, 0.214724] |
| J_structure_conversion | [0.208533, 0.213957] |
| A_current_review | [0.196944, 0.202112] |
| G_category_slot_probability | [0.190512, 0.194016] |
| D_category_slot_gs | [0.189886, 0.193503] |
| E_category_slot_main | [0.189886, 0.193503] |
| F_category_current_gs | [0.189886, 0.193503] |

### tier2_mid/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213454, 0.218322] |
| C_category_probability | [0.209928, 0.215339] |
| H_gs_stamina_efficiency | [0.209641, 0.215050] |
| I_high_recall_efficiency | [0.209360, 0.214724] |
| J_structure_conversion | [0.208533, 0.213957] |
| A_current_review | [0.196944, 0.202112] |
| G_category_slot_probability | [0.190512, 0.194016] |
| D_category_slot_gs | [0.189886, 0.193503] |
| E_category_slot_main | [0.189886, 0.193503] |
| F_category_current_gs | [0.189886, 0.193503] |

### tier2_mid/baili_marginal_low/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.224546, 0.230221] |
| C_category_probability | [0.220436, 0.226537] |
| H_gs_stamina_efficiency | [0.220111, 0.226211] |
| I_high_recall_efficiency | [0.219821, 0.225872] |
| J_structure_conversion | [0.218976, 0.225083] |
| A_current_review | [0.207027, 0.212845] |
| G_category_slot_probability | [0.203019, 0.207468] |
| D_category_slot_gs | [0.202374, 0.206919] |
| E_category_slot_main | [0.202374, 0.206919] |
| F_category_current_gs | [0.202374, 0.206919] |

### tier2_mid/baili_marginal_low/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226444, 0.232142] |
| C_category_probability | [0.222478, 0.228619] |
| H_gs_stamina_efficiency | [0.222150, 0.228290] |
| I_high_recall_efficiency | [0.221852, 0.227942] |
| J_structure_conversion | [0.220974, 0.227121] |
| A_current_review | [0.208875, 0.214731] |
| G_category_slot_probability | [0.204585, 0.209043] |
| D_category_slot_gs | [0.203917, 0.208473] |
| E_category_slot_main | [0.203917, 0.208473] |
| F_category_current_gs | [0.203917, 0.208473] |

### tier2_mid/baili_marginal_low/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226444, 0.232142] |
| C_category_probability | [0.222478, 0.228619] |
| H_gs_stamina_efficiency | [0.222150, 0.228290] |
| I_high_recall_efficiency | [0.221852, 0.227942] |
| J_structure_conversion | [0.220974, 0.227121] |
| A_current_review | [0.208875, 0.214731] |
| G_category_slot_probability | [0.204585, 0.209043] |
| D_category_slot_gs | [0.203917, 0.208473] |
| E_category_slot_main | [0.203917, 0.208473] |
| F_category_current_gs | [0.203917, 0.208473] |

### tier2_mid/baili_marginal_low/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226444, 0.232142] |
| C_category_probability | [0.222478, 0.228619] |
| H_gs_stamina_efficiency | [0.222150, 0.228290] |
| I_high_recall_efficiency | [0.221852, 0.227942] |
| J_structure_conversion | [0.220974, 0.227121] |
| A_current_review | [0.208875, 0.214731] |
| G_category_slot_probability | [0.204585, 0.209043] |
| D_category_slot_gs | [0.203917, 0.208473] |
| E_category_slot_main | [0.203917, 0.208473] |
| F_category_current_gs | [0.203917, 0.208473] |

### tier2_mid/baili_marginal_low/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.236936, 0.243459] |
| C_category_probability | [0.232422, 0.239283] |
| H_gs_stamina_efficiency | [0.232061, 0.238920] |
| I_high_recall_efficiency | [0.231753, 0.238561] |
| J_structure_conversion | [0.230862, 0.237721] |
| A_current_review | [0.218449, 0.224982] |
| G_category_slot_probability | [0.216440, 0.221854] |
| D_category_slot_gs | [0.215755, 0.221252] |
| E_category_slot_main | [0.215755, 0.221252] |
| F_category_current_gs | [0.215755, 0.221252] |

### tier2_mid/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238993, 0.245538] |
| C_category_probability | [0.234612, 0.241511] |
| H_gs_stamina_efficiency | [0.234247, 0.241146] |
| I_high_recall_efficiency | [0.233931, 0.240777] |
| J_structure_conversion | [0.233007, 0.239906] |
| A_current_review | [0.220435, 0.227006] |
| G_category_slot_probability | [0.218158, 0.223580] |
| D_category_slot_gs | [0.217451, 0.222958] |
| E_category_slot_main | [0.217451, 0.222958] |
| F_category_current_gs | [0.217451, 0.222958] |

### tier2_mid/baili_marginal_low/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238993, 0.245538] |
| C_category_probability | [0.234612, 0.241511] |
| H_gs_stamina_efficiency | [0.234247, 0.241146] |
| I_high_recall_efficiency | [0.233931, 0.240777] |
| J_structure_conversion | [0.233007, 0.239906] |
| A_current_review | [0.220435, 0.227006] |
| G_category_slot_probability | [0.218158, 0.223580] |
| D_category_slot_gs | [0.217451, 0.222958] |
| E_category_slot_main | [0.217451, 0.222958] |
| F_category_current_gs | [0.217451, 0.222958] |

### tier2_mid/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238993, 0.245538] |
| C_category_probability | [0.234612, 0.241511] |
| H_gs_stamina_efficiency | [0.234247, 0.241146] |
| I_high_recall_efficiency | [0.233931, 0.240777] |
| J_structure_conversion | [0.233007, 0.239906] |
| A_current_review | [0.220435, 0.227006] |
| G_category_slot_probability | [0.218158, 0.223580] |
| D_category_slot_gs | [0.217451, 0.222958] |
| E_category_slot_main | [0.217451, 0.222958] |
| F_category_current_gs | [0.217451, 0.222958] |

### tier2_mid/all_stop/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154841, 0.157761] |
| C_category_probability | [0.153352, 0.157015] |
| H_gs_stamina_efficiency | [0.153267, 0.156904] |
| I_high_recall_efficiency | [0.153069, 0.156704] |
| J_structure_conversion | [0.152549, 0.156199] |
| A_current_review | [0.143573, 0.147033] |
| G_category_slot_probability | [0.126404, 0.128888] |
| D_category_slot_gs | [0.126102, 0.128588] |
| E_category_slot_main | [0.126102, 0.128588] |
| F_category_current_gs | [0.126102, 0.128588] |

### tier2_mid/all_stop/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.127309, 0.129807] |
| D_category_slot_gs | [0.126976, 0.129477] |
| E_category_slot_main | [0.126976, 0.129477] |
| F_category_current_gs | [0.126976, 0.129477] |

### tier2_mid/all_stop/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.127309, 0.129807] |
| D_category_slot_gs | [0.126976, 0.129477] |
| E_category_slot_main | [0.126976, 0.129477] |
| F_category_current_gs | [0.126976, 0.129477] |

### tier2_mid/all_stop/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.125904, 0.128434] |
| D_category_slot_gs | [0.125786, 0.128312] |
| E_category_slot_main | [0.125786, 0.128312] |
| F_category_current_gs | [0.125786, 0.128312] |

### tier2_mid/all_stop/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154841, 0.157761] |
| C_category_probability | [0.153352, 0.157015] |
| H_gs_stamina_efficiency | [0.153267, 0.156904] |
| I_high_recall_efficiency | [0.153069, 0.156704] |
| J_structure_conversion | [0.152549, 0.156199] |
| A_current_review | [0.143573, 0.147033] |
| G_category_slot_probability | [0.126404, 0.128888] |
| D_category_slot_gs | [0.126102, 0.128588] |
| E_category_slot_main | [0.126102, 0.128588] |
| F_category_current_gs | [0.126102, 0.128588] |

### tier2_mid/all_stop/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.127309, 0.129807] |
| D_category_slot_gs | [0.126976, 0.129477] |
| E_category_slot_main | [0.126976, 0.129477] |
| F_category_current_gs | [0.126976, 0.129477] |

### tier2_mid/all_stop/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.127309, 0.129807] |
| D_category_slot_gs | [0.126976, 0.129477] |
| E_category_slot_main | [0.126976, 0.129477] |
| F_category_current_gs | [0.126976, 0.129477] |

### tier2_mid/all_stop/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.125904, 0.128434] |
| D_category_slot_gs | [0.125786, 0.128312] |
| E_category_slot_main | [0.125786, 0.128312] |
| F_category_current_gs | [0.125786, 0.128312] |

### tier2_mid/all_stop/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154841, 0.157761] |
| C_category_probability | [0.153352, 0.157015] |
| H_gs_stamina_efficiency | [0.153267, 0.156904] |
| I_high_recall_efficiency | [0.153069, 0.156704] |
| J_structure_conversion | [0.152549, 0.156199] |
| A_current_review | [0.143573, 0.147033] |
| G_category_slot_probability | [0.126404, 0.128888] |
| D_category_slot_gs | [0.126102, 0.128588] |
| E_category_slot_main | [0.126102, 0.128588] |
| F_category_current_gs | [0.126102, 0.128588] |

### tier2_mid/all_stop/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.127309, 0.129807] |
| D_category_slot_gs | [0.126976, 0.129477] |
| E_category_slot_main | [0.126976, 0.129477] |
| F_category_current_gs | [0.126976, 0.129477] |

### tier2_mid/all_stop/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.127309, 0.129807] |
| D_category_slot_gs | [0.126976, 0.129477] |
| E_category_slot_main | [0.126976, 0.129477] |
| F_category_current_gs | [0.126976, 0.129477] |

### tier2_mid/all_stop/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155999, 0.158945] |
| C_category_probability | [0.154697, 0.158402] |
| H_gs_stamina_efficiency | [0.154611, 0.158290] |
| I_high_recall_efficiency | [0.154404, 0.158081] |
| J_structure_conversion | [0.153850, 0.157542] |
| A_current_review | [0.144758, 0.148257] |
| G_category_slot_probability | [0.125904, 0.128434] |
| D_category_slot_gs | [0.125786, 0.128312] |
| E_category_slot_main | [0.125786, 0.128312] |
| F_category_current_gs | [0.125786, 0.128312] |

### tier2_high/baili_marginal_low/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212086, 0.216925] |
| C_category_probability | [0.208401, 0.213763] |
| H_gs_stamina_efficiency | [0.208114, 0.213475] |
| I_high_recall_efficiency | [0.207841, 0.213157] |
| J_structure_conversion | [0.207048, 0.212419] |
| A_current_review | [0.195580, 0.200699] |
| G_category_slot_probability | [0.189471, 0.192963] |
| D_category_slot_gs | [0.188872, 0.192468] |
| E_category_slot_main | [0.188872, 0.192468] |
| F_category_current_gs | [0.188872, 0.192468] |

### tier2_high/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213831, 0.218693] |
| C_category_probability | [0.210301, 0.215703] |
| H_gs_stamina_efficiency | [0.210012, 0.215413] |
| I_high_recall_efficiency | [0.209730, 0.215086] |
| J_structure_conversion | [0.208905, 0.214316] |
| A_current_review | [0.197295, 0.202451] |
| G_category_slot_probability | [0.190894, 0.194394] |
| D_category_slot_gs | [0.190271, 0.193877] |
| E_category_slot_main | [0.190271, 0.193877] |
| F_category_current_gs | [0.190271, 0.193877] |

### tier2_high/baili_marginal_low/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213831, 0.218693] |
| C_category_probability | [0.210301, 0.215703] |
| H_gs_stamina_efficiency | [0.210012, 0.215413] |
| I_high_recall_efficiency | [0.209730, 0.215086] |
| J_structure_conversion | [0.208905, 0.214316] |
| A_current_review | [0.197295, 0.202451] |
| G_category_slot_probability | [0.190894, 0.194394] |
| D_category_slot_gs | [0.190271, 0.193877] |
| E_category_slot_main | [0.190271, 0.193877] |
| F_category_current_gs | [0.190271, 0.193877] |

### tier2_high/baili_marginal_low/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.213831, 0.218693] |
| C_category_probability | [0.210301, 0.215703] |
| H_gs_stamina_efficiency | [0.210012, 0.215413] |
| I_high_recall_efficiency | [0.209730, 0.215086] |
| J_structure_conversion | [0.208905, 0.214316] |
| A_current_review | [0.197295, 0.202451] |
| G_category_slot_probability | [0.190894, 0.194394] |
| D_category_slot_gs | [0.190271, 0.193877] |
| E_category_slot_main | [0.190271, 0.193877] |
| F_category_current_gs | [0.190271, 0.193877] |

### tier2_high/baili_marginal_low/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.224932, 0.230613] |
| C_category_probability | [0.220816, 0.226920] |
| H_gs_stamina_efficiency | [0.220489, 0.226593] |
| I_high_recall_efficiency | [0.220199, 0.226253] |
| J_structure_conversion | [0.219356, 0.225461] |
| A_current_review | [0.207386, 0.213203] |
| G_category_slot_probability | [0.203410, 0.207869] |
| D_category_slot_gs | [0.202767, 0.207316] |
| E_category_slot_main | [0.202767, 0.207316] |
| F_category_current_gs | [0.202767, 0.207316] |

### tier2_high/baili_marginal_low/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226833, 0.232537] |
| C_category_probability | [0.222862, 0.229004] |
| H_gs_stamina_efficiency | [0.222533, 0.228675] |
| I_high_recall_efficiency | [0.222234, 0.228326] |
| J_structure_conversion | [0.221358, 0.227502] |
| A_current_review | [0.209237, 0.215091] |
| G_category_slot_probability | [0.204980, 0.209446] |
| D_category_slot_gs | [0.204314, 0.208873] |
| E_category_slot_main | [0.204314, 0.208873] |
| F_category_current_gs | [0.204314, 0.208873] |

### tier2_high/baili_marginal_low/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226833, 0.232537] |
| C_category_probability | [0.222862, 0.229004] |
| H_gs_stamina_efficiency | [0.222533, 0.228675] |
| I_high_recall_efficiency | [0.222234, 0.228326] |
| J_structure_conversion | [0.221358, 0.227502] |
| A_current_review | [0.209237, 0.215091] |
| G_category_slot_probability | [0.204980, 0.209446] |
| D_category_slot_gs | [0.204314, 0.208873] |
| E_category_slot_main | [0.204314, 0.208873] |
| F_category_current_gs | [0.204314, 0.208873] |

### tier2_high/baili_marginal_low/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.226833, 0.232537] |
| C_category_probability | [0.222862, 0.229004] |
| H_gs_stamina_efficiency | [0.222533, 0.228675] |
| I_high_recall_efficiency | [0.222234, 0.228326] |
| J_structure_conversion | [0.221358, 0.227502] |
| A_current_review | [0.209237, 0.215091] |
| G_category_slot_probability | [0.204980, 0.209446] |
| D_category_slot_gs | [0.204314, 0.208873] |
| E_category_slot_main | [0.204314, 0.208873] |
| F_category_current_gs | [0.204314, 0.208873] |

### tier2_high/baili_marginal_low/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.237334, 0.243872] |
| C_category_probability | [0.232815, 0.239687] |
| H_gs_stamina_efficiency | [0.232451, 0.239323] |
| I_high_recall_efficiency | [0.232143, 0.238963] |
| J_structure_conversion | [0.231253, 0.238119] |
| A_current_review | [0.218819, 0.225360] |
| G_category_slot_probability | [0.216845, 0.222276] |
| D_category_slot_gs | [0.216162, 0.221671] |
| E_category_slot_main | [0.216162, 0.221671] |
| F_category_current_gs | [0.216162, 0.221671] |

### tier2_high/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.239395, 0.245954] |
| C_category_probability | [0.235009, 0.241918] |
| H_gs_stamina_efficiency | [0.234642, 0.241552] |
| I_high_recall_efficiency | [0.234326, 0.241183] |
| J_structure_conversion | [0.233403, 0.240308] |
| A_current_review | [0.220809, 0.227386] |
| G_category_slot_probability | [0.218567, 0.224005] |
| D_category_slot_gs | [0.217862, 0.223380] |
| E_category_slot_main | [0.217862, 0.223380] |
| F_category_current_gs | [0.217862, 0.223380] |

### tier2_high/baili_marginal_low/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.239395, 0.245954] |
| C_category_probability | [0.235009, 0.241918] |
| H_gs_stamina_efficiency | [0.234642, 0.241552] |
| I_high_recall_efficiency | [0.234326, 0.241183] |
| J_structure_conversion | [0.233403, 0.240308] |
| A_current_review | [0.220809, 0.227386] |
| G_category_slot_probability | [0.218567, 0.224005] |
| D_category_slot_gs | [0.217862, 0.223380] |
| E_category_slot_main | [0.217862, 0.223380] |
| F_category_current_gs | [0.217862, 0.223380] |

### tier2_high/baili_marginal_low/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.239395, 0.245954] |
| C_category_probability | [0.235009, 0.241918] |
| H_gs_stamina_efficiency | [0.234642, 0.241552] |
| I_high_recall_efficiency | [0.234326, 0.241183] |
| J_structure_conversion | [0.233403, 0.240308] |
| A_current_review | [0.220809, 0.227386] |
| G_category_slot_probability | [0.218567, 0.224005] |
| D_category_slot_gs | [0.217862, 0.223380] |
| E_category_slot_main | [0.217862, 0.223380] |
| F_category_current_gs | [0.217862, 0.223380] |

### tier2_high/all_stop/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155174, 0.158018] |
| C_category_probability | [0.153672, 0.157277] |
| H_gs_stamina_efficiency | [0.153587, 0.157165] |
| I_high_recall_efficiency | [0.153388, 0.156964] |
| J_structure_conversion | [0.152869, 0.156457] |
| A_current_review | [0.143874, 0.147276] |
| G_category_slot_probability | [0.126729, 0.129156] |
| D_category_slot_gs | [0.126426, 0.128856] |
| E_category_slot_main | [0.126426, 0.128856] |
| F_category_current_gs | [0.126426, 0.128856] |

### tier2_high/all_stop/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.127636, 0.130076] |
| D_category_slot_gs | [0.127302, 0.129747] |
| E_category_slot_main | [0.127302, 0.129747] |
| F_category_current_gs | [0.127302, 0.129747] |

### tier2_high/all_stop/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.127636, 0.130076] |
| D_category_slot_gs | [0.127302, 0.129747] |
| E_category_slot_main | [0.127302, 0.129747] |
| F_category_current_gs | [0.127302, 0.129747] |

### tier2_high/all_stop/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.126228, 0.128700] |
| D_category_slot_gs | [0.126110, 0.128579] |
| E_category_slot_main | [0.126110, 0.128579] |
| F_category_current_gs | [0.126110, 0.128579] |

### tier2_high/all_stop/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155174, 0.158018] |
| C_category_probability | [0.153672, 0.157277] |
| H_gs_stamina_efficiency | [0.153587, 0.157165] |
| I_high_recall_efficiency | [0.153388, 0.156964] |
| J_structure_conversion | [0.152869, 0.156457] |
| A_current_review | [0.143874, 0.147276] |
| G_category_slot_probability | [0.126729, 0.129156] |
| D_category_slot_gs | [0.126426, 0.128856] |
| E_category_slot_main | [0.126426, 0.128856] |
| F_category_current_gs | [0.126426, 0.128856] |

### tier2_high/all_stop/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.127636, 0.130076] |
| D_category_slot_gs | [0.127302, 0.129747] |
| E_category_slot_main | [0.127302, 0.129747] |
| F_category_current_gs | [0.127302, 0.129747] |

### tier2_high/all_stop/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.127636, 0.130076] |
| D_category_slot_gs | [0.127302, 0.129747] |
| E_category_slot_main | [0.127302, 0.129747] |
| F_category_current_gs | [0.127302, 0.129747] |

### tier2_high/all_stop/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.126228, 0.128700] |
| D_category_slot_gs | [0.126110, 0.128579] |
| E_category_slot_main | [0.126110, 0.128579] |
| F_category_current_gs | [0.126110, 0.128579] |

### tier2_high/all_stop/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155174, 0.158018] |
| C_category_probability | [0.153672, 0.157277] |
| H_gs_stamina_efficiency | [0.153587, 0.157165] |
| I_high_recall_efficiency | [0.153388, 0.156964] |
| J_structure_conversion | [0.152869, 0.156457] |
| A_current_review | [0.143874, 0.147276] |
| G_category_slot_probability | [0.126729, 0.129156] |
| D_category_slot_gs | [0.126426, 0.128856] |
| E_category_slot_main | [0.126426, 0.128856] |
| F_category_current_gs | [0.126426, 0.128856] |

### tier2_high/all_stop/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.127636, 0.130076] |
| D_category_slot_gs | [0.127302, 0.129747] |
| E_category_slot_main | [0.127302, 0.129747] |
| F_category_current_gs | [0.127302, 0.129747] |

### tier2_high/all_stop/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.127636, 0.130076] |
| D_category_slot_gs | [0.127302, 0.129747] |
| E_category_slot_main | [0.127302, 0.129747] |
| F_category_current_gs | [0.127302, 0.129747] |

### tier2_high/all_stop/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.156334, 0.159204] |
| C_category_probability | [0.155020, 0.158666] |
| H_gs_stamina_efficiency | [0.154933, 0.158552] |
| I_high_recall_efficiency | [0.154726, 0.158343] |
| J_structure_conversion | [0.154173, 0.157802] |
| A_current_review | [0.145061, 0.148502] |
| G_category_slot_probability | [0.126228, 0.128700] |
| D_category_slot_gs | [0.126110, 0.128579] |
| E_category_slot_main | [0.126110, 0.128579] |
| F_category_current_gs | [0.126110, 0.128579] |


## 资源流示例（第一个 seed、Heroic 基础回退）

### explicit_batch_gold_on

- 粉末单位：44.715712；下级石需求：2.981047；材料金币：114472.22；转换金币：2963.65。
- 出售回收：金币 9579.42、经验 5675.23；来源金币已使用/盈余：107856.46/19643.54。
- 来源石已使用/剩余需求/盈余：0.425000 / 2.556047 / 0.000000
- 净金币缺口：0.00；净经验缺口：2542.58；瓶颈：enhance_exp
- 圣女补充：17.518432；总投入：102.518432。

### explicit_batch_gold_off

- 粉末单位：44.715712；下级石需求：2.981047；材料金币：114472.22；转换金币：2963.65。
- 出售回收：金币 9579.42、经验 5675.23；来源金币已使用/盈余：0.00/0.00。
- 来源石已使用/剩余需求/盈余：0.425000 / 2.556047 / 0.000000
- 净金币缺口：107856.46；净经验缺口：2542.58；瓶颈：enhance_exp
- 圣女补充：17.518432；总投入：102.518432。

### explicit_long_cross_batch

- 粉末单位：44.715712；下级石需求：2.981047；材料金币：114472.22；转换金币：2963.65。
- 出售回收：金币 9579.42、经验 5675.23；来源金币已使用/盈余：107856.46/19643.54。
- 来源石已使用/剩余需求/盈余：0.425000 / 2.556047 / 0.000000
- 净金币缺口：0.00；净经验缺口：2542.58；瓶颈：enhance_exp
- 圣女补充：17.518432；总投入：102.518432。

## 结论

- B 保留 48 件前瞻验证资格。
- 来源金币开启/关闭均未越过经验瓶颈，因此不改变 B/C 排序；来源金币只抵扣一次，未被折为额外体力信用。
- 显式资源池不把 80.607613 作为主分母；该值仅保留为旧标量/长期机会成本条件视图。
- 本轮不修改正式策略、Heroic 策略、lambda、评分、跳值表或 GUI。
