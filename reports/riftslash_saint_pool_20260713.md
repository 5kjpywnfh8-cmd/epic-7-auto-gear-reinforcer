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
| all_stop/baseline | old_scalar_credit | B_global_current_gs | [0.000666, 0.001550] |
| all_stop/baseline | explicit_batch_gold_on | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/baseline | explicit_long_cross_batch | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/baseline | explicit_batch_gold_off | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.000666, 0.001550] |
| all_stop/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.000666, 0.001550] |
| all_stop/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.000464, 0.001364] |
| all_stop/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.000464, 0.001364] |
| baili_marginal_low/baseline | old_scalar_credit | B_global_current_gs | [0.003502, 0.004260] |
| baili_marginal_low/baseline | explicit_batch_gold_on | B_global_current_gs | [0.003342, 0.004116] |
| baili_marginal_low/baseline | explicit_long_cross_batch | B_global_current_gs | [0.003342, 0.004116] |
| baili_marginal_low/baseline | explicit_batch_gold_off | B_global_current_gs | [0.003342, 0.004116] |
| baili_marginal_low/yield_minus_20pct | old_scalar_credit | B_global_current_gs | [0.003014, 0.003790] |
| baili_marginal_low/yield_minus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.002844, 0.003635] |
| baili_marginal_low/yield_minus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.002844, 0.003635] |
| baili_marginal_low/yield_minus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.002844, 0.003635] |
| baili_marginal_low/yield_plus_20pct | old_scalar_credit | B_global_current_gs | [0.003957, 0.004699] |
| baili_marginal_low/yield_plus_20pct | explicit_batch_gold_on | B_global_current_gs | [0.003808, 0.004566] |
| baili_marginal_low/yield_plus_20pct | explicit_long_cross_batch | B_global_current_gs | [0.003808, 0.004566] |
| baili_marginal_low/yield_plus_20pct | explicit_batch_gold_off | B_global_current_gs | [0.003808, 0.004566] |

## 全部 Epic 候选价值率

### all_stop/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154006, 0.157313] |
| C_category_probability | [0.152547, 0.156556] |
| H_gs_stamina_efficiency | [0.152465, 0.156447] |
| I_high_recall_efficiency | [0.152267, 0.156250] |
| J_structure_conversion | [0.151748, 0.155745] |
| A_current_review | [0.142820, 0.146606] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### all_stop/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### all_stop/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### all_stop/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### all_stop/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154006, 0.157313] |
| C_category_probability | [0.152547, 0.156556] |
| H_gs_stamina_efficiency | [0.152465, 0.156447] |
| I_high_recall_efficiency | [0.152267, 0.156250] |
| J_structure_conversion | [0.151748, 0.155745] |
| A_current_review | [0.142820, 0.146606] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### all_stop/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### all_stop/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### all_stop/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### all_stop/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.154006, 0.157313] |
| C_category_probability | [0.152547, 0.156556] |
| H_gs_stamina_efficiency | [0.152465, 0.156447] |
| I_high_recall_efficiency | [0.152267, 0.156250] |
| J_structure_conversion | [0.151748, 0.155745] |
| A_current_review | [0.142820, 0.146606] |
| G_category_slot_probability | [0.125752, 0.128356] |
| D_category_slot_gs | [0.125449, 0.128055] |
| E_category_slot_main | [0.125449, 0.128055] |
| F_category_current_gs | [0.125449, 0.128055] |

### all_stop/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### all_stop/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.126652, 0.129270] |
| D_category_slot_gs | [0.126319, 0.128941] |
| E_category_slot_main | [0.126319, 0.128941] |
| F_category_current_gs | [0.126319, 0.128941] |

### all_stop/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.155157, 0.158494] |
| C_category_probability | [0.153885, 0.157938] |
| H_gs_stamina_efficiency | [0.153801, 0.157829] |
| I_high_recall_efficiency | [0.153595, 0.157622] |
| J_structure_conversion | [0.153042, 0.157084] |
| A_current_review | [0.143998, 0.147826] |
| G_category_slot_probability | [0.125254, 0.127903] |
| D_category_slot_gs | [0.125136, 0.127780] |
| E_category_slot_main | [0.125136, 0.127780] |
| F_category_current_gs | [0.125136, 0.127780] |

### baili_marginal_low/baseline / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.223682, 0.229435] |
| C_category_probability | [0.219577, 0.225777] |
| H_gs_stamina_efficiency | [0.219257, 0.225452] |
| I_high_recall_efficiency | [0.218967, 0.225115] |
| J_structure_conversion | [0.218120, 0.224331] |
| A_current_review | [0.206219, 0.212134] |
| G_category_slot_probability | [0.202225, 0.206680] |
| D_category_slot_gs | [0.201575, 0.206136] |
| E_category_slot_main | [0.201575, 0.206136] |
| F_category_current_gs | [0.201575, 0.206136] |

### baili_marginal_low/baseline / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225571, 0.231350] |
| C_category_probability | [0.221610, 0.227853] |
| H_gs_stamina_efficiency | [0.221287, 0.227525] |
| I_high_recall_efficiency | [0.220989, 0.227180] |
| J_structure_conversion | [0.220110, 0.226364] |
| A_current_review | [0.208059, 0.214015] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### baili_marginal_low/baseline / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225571, 0.231350] |
| C_category_probability | [0.221610, 0.227853] |
| H_gs_stamina_efficiency | [0.221287, 0.227525] |
| I_high_recall_efficiency | [0.220989, 0.227180] |
| J_structure_conversion | [0.220110, 0.226364] |
| A_current_review | [0.208059, 0.214015] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### baili_marginal_low/baseline / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.225571, 0.231350] |
| C_category_probability | [0.221610, 0.227853] |
| H_gs_stamina_efficiency | [0.221287, 0.227525] |
| I_high_recall_efficiency | [0.220989, 0.227180] |
| J_structure_conversion | [0.220110, 0.226364] |
| A_current_review | [0.208059, 0.214015] |
| G_category_slot_probability | [0.203784, 0.208250] |
| D_category_slot_gs | [0.203111, 0.207686] |
| E_category_slot_main | [0.203111, 0.207686] |
| F_category_current_gs | [0.203111, 0.207686] |

### baili_marginal_low/yield_minus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.210860, 0.215826] |
| C_category_probability | [0.207186, 0.212695] |
| H_gs_stamina_efficiency | [0.206906, 0.212409] |
| I_high_recall_efficiency | [0.206634, 0.212094] |
| J_structure_conversion | [0.205839, 0.211364] |
| A_current_review | [0.194439, 0.199701] |
| G_category_slot_probability | [0.188325, 0.191846] |
| D_category_slot_gs | [0.187718, 0.191360] |
| E_category_slot_main | [0.187718, 0.191360] |
| F_category_current_gs | [0.187718, 0.191360] |

### baili_marginal_low/yield_minus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212594, 0.217586] |
| C_category_probability | [0.209074, 0.214626] |
| H_gs_stamina_efficiency | [0.208792, 0.214338] |
| I_high_recall_efficiency | [0.208512, 0.214015] |
| J_structure_conversion | [0.207683, 0.213252] |
| A_current_review | [0.196142, 0.201446] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### baili_marginal_low/yield_minus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212594, 0.217586] |
| C_category_probability | [0.209074, 0.214626] |
| H_gs_stamina_efficiency | [0.208792, 0.214338] |
| I_high_recall_efficiency | [0.208512, 0.214015] |
| J_structure_conversion | [0.207683, 0.213252] |
| A_current_review | [0.196142, 0.201446] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### baili_marginal_low/yield_minus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.212594, 0.217586] |
| C_category_probability | [0.209074, 0.214626] |
| H_gs_stamina_efficiency | [0.208792, 0.214338] |
| I_high_recall_efficiency | [0.208512, 0.214015] |
| J_structure_conversion | [0.207683, 0.213252] |
| A_current_review | [0.196142, 0.201446] |
| G_category_slot_probability | [0.189738, 0.193270] |
| D_category_slot_gs | [0.189108, 0.192763] |
| E_category_slot_main | [0.189108, 0.192763] |
| F_category_current_gs | [0.189108, 0.192763] |

### baili_marginal_low/yield_plus_20pct / old_scalar_credit

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.236055, 0.242622] |
| C_category_probability | [0.231547, 0.238475] |
| H_gs_stamina_efficiency | [0.231190, 0.238113] |
| I_high_recall_efficiency | [0.230883, 0.237756] |
| J_structure_conversion | [0.229990, 0.236922] |
| A_current_review | [0.217624, 0.224226] |
| G_category_slot_probability | [0.215619, 0.221022] |
| D_category_slot_gs | [0.214929, 0.220426] |
| E_category_slot_main | [0.214929, 0.220426] |
| F_category_current_gs | [0.214929, 0.220426] |

### baili_marginal_low/yield_plus_20pct / explicit_batch_gold_on

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238102, 0.244695] |
| C_category_probability | [0.233727, 0.240697] |
| H_gs_stamina_efficiency | [0.233367, 0.240333] |
| I_high_recall_efficiency | [0.233052, 0.239967] |
| J_structure_conversion | [0.232126, 0.239101] |
| A_current_review | [0.219602, 0.226244] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### baili_marginal_low/yield_plus_20pct / explicit_long_cross_batch

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238102, 0.244695] |
| C_category_probability | [0.233727, 0.240697] |
| H_gs_stamina_efficiency | [0.233367, 0.240333] |
| I_high_recall_efficiency | [0.233052, 0.239967] |
| J_structure_conversion | [0.232126, 0.239101] |
| A_current_review | [0.219602, 0.226244] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |

### baili_marginal_low/yield_plus_20pct / explicit_batch_gold_off

| 候选 | 价值率/100体力 95% CI |
|---|---:|
| B_global_current_gs | [0.238102, 0.244695] |
| C_category_probability | [0.233727, 0.240697] |
| H_gs_stamina_efficiency | [0.233367, 0.240333] |
| I_high_recall_efficiency | [0.233052, 0.239967] |
| J_structure_conversion | [0.232126, 0.239101] |
| A_current_review | [0.219602, 0.226244] |
| G_category_slot_probability | [0.217329, 0.222744] |
| D_category_slot_gs | [0.216617, 0.222128] |
| E_category_slot_main | [0.216617, 0.222128] |
| F_category_current_gs | [0.216617, 0.222128] |


## 资源流示例（第一个 seed、Heroic 基础回退）

### explicit_batch_gold_on

- 粉末单位：30.659742；下级石需求：2.043983；材料金币：78488.94；转换金币：1685.62。
- 出售回收：金币 7939.21、经验 3931.67；来源金币已使用/盈余：72235.35/55264.65。
- 来源石已使用/剩余需求/盈余：0.425000 / 1.618983 / 0.000000
- 净金币缺口：0.00；净经验缺口：1549.33；瓶颈：enhance_exp
- 圣女补充：10.674885；总投入：95.674885。

### explicit_batch_gold_off

- 粉末单位：30.659742；下级石需求：2.043983；材料金币：78488.94；转换金币：1685.62。
- 出售回收：金币 7939.21、经验 3931.67；来源金币已使用/盈余：0.00/0.00。
- 来源石已使用/剩余需求/盈余：0.425000 / 1.618983 / 0.000000
- 净金币缺口：72235.35；净经验缺口：1549.33；瓶颈：enhance_exp
- 圣女补充：10.674885；总投入：95.674885。

### explicit_long_cross_batch

- 粉末单位：30.659742；下级石需求：2.043983；材料金币：78488.94；转换金币：1685.62。
- 出售回收：金币 7939.21、经验 3931.67；来源金币已使用/盈余：72235.35/55264.65。
- 来源石已使用/剩余需求/盈余：0.425000 / 1.618983 / 0.000000
- 净金币缺口：0.00；净经验缺口：1549.33；瓶颈：enhance_exp
- 圣女补充：10.674885；总投入：95.674885。

## 结论

- B 保留 48 件前瞻验证资格。
- 来源金币开启/关闭均未越过经验瓶颈，因此不改变 B/C 排序；来源金币只抵扣一次，未被折为额外体力信用。
- 显式资源池不把 80.607613 作为主分母；该值仅保留为旧标量/长期机会成本条件视图。
- 本轮不修改正式策略、Heroic 策略、lambda、评分、跳值表或 GUI。
