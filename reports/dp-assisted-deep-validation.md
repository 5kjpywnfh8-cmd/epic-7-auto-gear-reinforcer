# DP assisted 1M x 5 deep validation

## 结论

- normal_85 Epic：switch_default
- normal_85 Heroic：switch_default
- rift_85 Epic：keep_round2_policy，本轮未重跑
- 是否需要更大样本：否

## normal_85 Epic

- baseline：category_baili_marginal_mid
- dp_assisted：normal_epic_dp_assisted
- 建议：switch_default
- seed rank stability：DP wins 5/5, stable=True
- cost mean：baseline 932.82 vs DP 817.24
- cost 95% CI：baseline [918.989111, 946.650889] vs DP [812.191342, 822.288658]
- baili / 1000 stamina mean：baseline 1.1 vs DP 1.2

| seed | baseline cost | DP cost | delta | baseline score/1000 | DP score/1000 | DP calls | DP changes | +9/+12 changes | native/rescued DP | conversion DP |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| 17 | 929.4 | 819.0 | -110.4 | 1.1 | 1.2 | 56954 | 20836 | +12:8368/+9:12468 | 0.0058/0.009 | 0.01 |
| 29 | 944.5 | 823.3 | -121.2 | 1.1 | 1.2 | 56952 | 21054 | +12:8416/+9:12638 | 0.0057/0.0091 | 0.01 |
| 43 | 929.5 | 814.3 | -115.2 | 1.1 | 1.2 | 56577 | 20765 | +12:8259/+9:12506 | 0.0057/0.009 | 0.01 |
| 71 | 917.6 | 813.1 | -104.5 | 1.1 | 1.2 | 56900 | 20738 | +12:8253/+9:12485 | 0.0058/0.0091 | 0.0101 |
| 101 | 943.1 | 816.5 | -126.6 | 1.1 | 1.2 | 57021 | 20929 | +12:8311/+9:12618 | 0.0059/0.0091 | 0.0101 |

- DP 改判样本：72614
- 改判后百里分提升/降低/持平：40274 / 976 / 31364
- +9 / +12 改判次数：{'12': 41607.0, '9': 62715.0}
- 分类贡献变化 top：抗坦=60265.2, 输出=35991.2, 半肉(血防)=34139.2, 命坦=32130.9, 半肉(白字)=13419.6
- 套装贡献变化 top：set_chase=19558.9, set_opener=19118.9, set_speed=18606.0, set_immune=18431.1, set_max_hp=15900.9

## normal_85 Heroic

- baseline：baili_marginal_low
- dp_assisted：normal_heroic_dp_assisted
- 建议：switch_default
- seed rank stability：DP wins 5/5, stable=True
- cost mean：baseline 22838.96 vs DP 5864.86
- cost 95% CI：baseline [20434.761502, 25243.158498] vs DP [5592.000542, 6137.719458]
- baili / 1000 stamina mean：baseline 0.02 vs DP 0.2

| seed | baseline cost | DP cost | delta | baseline score/1000 | DP score/1000 | DP calls | DP changes | +9/+12 changes | native/rescued DP | conversion DP |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| 17 | 23905.2 | 5984.5 | -17920.7 | 0.0 | 0.2 | 7720 | 2041 | +12:1160/+9:881 | 0.0001/0.0004 | 0.0004 |
| 29 | 19786.1 | 5521.0 | -14265.1 | 0.1 | 0.2 | 7594 | 1967 | +12:1115/+9:852 | 0.0001/0.0004 | 0.0004 |
| 43 | 24937.3 | 5852.8 | -19084.5 | 0.0 | 0.2 | 7596 | 1956 | +12:1110/+9:846 | 0.0001/0.0004 | 0.0004 |
| 71 | 23043.2 | 6110.7 | -16932.5 | 0.0 | 0.2 | 7617 | 1967 | +12:1111/+9:856 | 0.0001/0.0004 | 0.0004 |
| 101 | 22523.0 | 5855.3 | -16667.7 | 0.0 | 0.2 | 7564 | 1968 | +12:1130/+9:838 | 0.0001/0.0004 | 0.0004 |

- DP 改判样本：7287
- 改判后百里分提升/降低/持平：2143 / 0 / 5144
- +9 / +12 改判次数：{'12': 5626.0, '9': 4273.0}
- 分类贡献变化 top：抗坦=2084.6, 输出=1924.7, 命坦=1181.8, 纯肉=1063.3, 一速=365.0
- 套装贡献变化 top：set_opener=888.8, set_speed=731.9, set_immune=633.1, set_revenant=595.8, set_chase=594.1
