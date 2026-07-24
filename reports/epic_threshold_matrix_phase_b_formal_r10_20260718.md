# Epic Threshold Matrix Phase B Formal R10

This is the candidate-consistent formal `runs=10` study. The prior `runs=1` output is `pilot_not_for_release` and is not used for ranking or release.

Phase A remains the immutable `global_uniform_phase_a` historical comparison; Phase B corrects the selected-candidate effective-GS consistency issue. No production policy is changed.

## Global References

| route | +0 false stops | +3 false stops | +0/+3 false probability mass | +0/+3 utility loss | +0/+3 regret | publish gate |
|---|---:|---:|---:|---:|---:|---|
| t0_10_t3_14_global_p0 | 0 | 16 | 0.800000 | 0.004881 | 1.745724 | blocked |
| t0_12_t3_17_global_p0 | 2 | 34 | 3.700000 | 0.044772 | 1.435395 | blocked |

## System One-Factor Rows

Each row changes only one system group; delta=0 is the corrected global 10/14 reference for that group.

| group | delta | +0 false stops | +3 false stops | utility loss | publish gate |
|---|---:|---:|---:|---:|---|
| pure_output | -2 | 0 | 2 | 0.001424 | blocked |
| pure_output | +0 | 0 | 16 | 0.004881 | blocked |
| pure_output | +2 | 0 | 36 | 0.042477 | blocked |
| pure_tank | -2 | 0 | 16 | 0.004881 | blocked |
| pure_tank | +0 | 0 | 16 | 0.004881 | blocked |
| pure_tank | +2 | 2 | 14 | 0.007176 | blocked |
| bruiser | -2 | 0 | 16 | 0.004881 | blocked |
| bruiser | +0 | 0 | 16 | 0.004881 | blocked |
| bruiser | +2 | 0 | 16 | 0.004881 | blocked |
| dual | -2 | 0 | 16 | 0.004881 | blocked |
| dual | +0 | 0 | 16 | 0.004881 | blocked |
| dual | +2 | 0 | 16 | 0.004881 | blocked |

## Joint Pool

All 15 global rows and all system one-factor rows are compared offline. Publication gates do not remove rows from this section.

| Heroic yield | route | value / 100 stamina delta 95% CI |
|---|---|---:|
| yield_minus_20pct | t0_14_t3_20_global_p0 | [0.001100, 0.001744] |
| yield_minus_20pct | t0_14_t3_18_global_p0 | [0.001066, 0.001689] |
| yield_minus_20pct | t0_14_t3_17_global_p0 | [0.001061, 0.001681] |
| yield_minus_20pct | t0_14_t3_16_global_p0 | [0.001056, 0.001673] |
| yield_minus_20pct | t0_14_t3_14_global_p0 | [0.000951, 0.001507] |
| yield_minus_20pct | t0_12_t3_20_global_p0 | [0.000925, 0.001465] |
| yield_minus_20pct | t0_10_t3_20_global_p0 | [0.000854, 0.001353] |
| yield_minus_20pct | t0_12_t3_18_global_p0 | [0.000790, 0.001251] |
| yield_minus_20pct | t0_12_t3_17_global_p0 | [0.000740, 0.001173] |
| yield_minus_20pct | t0_12_t3_16_global_p0 | [0.000719, 0.001139] |
| yield_minus_20pct | t0_10_t3_18_global_p0 | [0.000662, 0.001049] |
| yield_minus_20pct | t0_12_t3_14_global_p0 | [0.000613, 0.000971] |
| yield_minus_20pct | t0_10_t3_17_global_p0 | [0.000588, 0.000932] |
| yield_minus_20pct | t0_10_t3_14_pure_output_p2 | [0.000576, 0.000912] |
| yield_minus_20pct | t0_10_t3_16_global_p0 | [0.000536, 0.000850] |
| yield_minus_20pct | t0_10_t3_14_pure_tank_p2 | [0.000527, 0.000834] |
| yield_minus_20pct | t0_10_t3_14_bruiser_m2 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_bruiser_p0 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_bruiser_p2 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_dual_m2 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_dual_p0 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_dual_p2 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_global_p0 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_pure_output_p0 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_pure_tank_p0 | [0.000388, 0.000615] |
| yield_minus_20pct | t0_10_t3_14_pure_tank_m2 | [0.000357, 0.000565] |
| yield_minus_20pct | t0_10_t3_14_pure_output_m2 | [0.000192, 0.000304] |
| yield_minus_20pct | current_formal | [0.000000, 0.000000] |
| baseline | t0_14_t3_20_global_p0 | [0.000898, 0.001508] |
| baseline | t0_14_t3_18_global_p0 | [0.000870, 0.001461] |
| baseline | t0_14_t3_17_global_p0 | [0.000865, 0.001454] |
| baseline | t0_14_t3_16_global_p0 | [0.000861, 0.001446] |
| baseline | t0_14_t3_14_global_p0 | [0.000776, 0.001304] |
| baseline | t0_12_t3_20_global_p0 | [0.000755, 0.001268] |
| baseline | t0_10_t3_20_global_p0 | [0.000697, 0.001171] |
| baseline | t0_12_t3_18_global_p0 | [0.000645, 0.001083] |
| baseline | t0_12_t3_17_global_p0 | [0.000604, 0.001015] |
| baseline | t0_12_t3_16_global_p0 | [0.000587, 0.000986] |
| baseline | t0_10_t3_18_global_p0 | [0.000541, 0.000908] |
| baseline | t0_12_t3_14_global_p0 | [0.000500, 0.000840] |
| baseline | t0_10_t3_17_global_p0 | [0.000480, 0.000807] |
| baseline | t0_10_t3_14_pure_output_p2 | [0.000470, 0.000790] |
| baseline | t0_10_t3_16_global_p0 | [0.000438, 0.000736] |
| baseline | t0_10_t3_14_pure_tank_p2 | [0.000430, 0.000722] |
| baseline | t0_10_t3_14_bruiser_m2 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_bruiser_p0 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_bruiser_p2 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_dual_m2 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_dual_p0 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_dual_p2 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_global_p0 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_pure_output_p0 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_pure_tank_p0 | [0.000317, 0.000533] |
| baseline | t0_10_t3_14_pure_tank_m2 | [0.000292, 0.000490] |
| baseline | t0_10_t3_14_pure_output_m2 | [0.000157, 0.000263] |
| baseline | current_formal | [0.000000, 0.000000] |
| yield_plus_20pct | t0_14_t3_20_global_p0 | [0.000755, 0.001328] |
| yield_plus_20pct | t0_14_t3_18_global_p0 | [0.000732, 0.001287] |
| yield_plus_20pct | t0_14_t3_17_global_p0 | [0.000728, 0.001280] |
| yield_plus_20pct | t0_14_t3_16_global_p0 | [0.000725, 0.001274] |
| yield_plus_20pct | t0_14_t3_14_global_p0 | [0.000654, 0.001149] |
| yield_plus_20pct | t0_12_t3_20_global_p0 | [0.000635, 0.001117] |
| yield_plus_20pct | t0_10_t3_20_global_p0 | [0.000587, 0.001032] |
| yield_plus_20pct | t0_12_t3_18_global_p0 | [0.000543, 0.000954] |
| yield_plus_20pct | t0_12_t3_17_global_p0 | [0.000509, 0.000895] |
| yield_plus_20pct | t0_12_t3_16_global_p0 | [0.000494, 0.000869] |
| yield_plus_20pct | t0_10_t3_18_global_p0 | [0.000455, 0.000800] |
| yield_plus_20pct | t0_12_t3_14_global_p0 | [0.000421, 0.000741] |
| yield_plus_20pct | t0_10_t3_17_global_p0 | [0.000405, 0.000711] |
| yield_plus_20pct | t0_10_t3_14_pure_output_p2 | [0.000396, 0.000696] |
| yield_plus_20pct | t0_10_t3_16_global_p0 | [0.000369, 0.000649] |
| yield_plus_20pct | t0_10_t3_14_pure_tank_p2 | [0.000362, 0.000637] |
| yield_plus_20pct | t0_10_t3_14_bruiser_m2 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_bruiser_p0 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_bruiser_p2 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_dual_m2 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_dual_p0 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_dual_p2 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_global_p0 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_pure_output_p0 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_pure_tank_p0 | [0.000267, 0.000470] |
| yield_plus_20pct | t0_10_t3_14_pure_tank_m2 | [0.000246, 0.000432] |
| yield_plus_20pct | t0_10_t3_14_pure_output_m2 | [0.000132, 0.000232] |
| yield_plus_20pct | current_formal | [0.000000, 0.000000] |

## Per 100,000 Total Stamina

| route | formal value | native 75+ | converted 75+ | 22+ | Rift stamina | Saint 3-7 stamina | cycles |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_formal | 68.382 | 0.532 | 0.945 | 0.249 | 23754.278 | 76245.722 | 279.462 |
| t0_10_t3_14_global_p0 | 68.807 | 0.536 | 0.951 | 0.251 | 23902.065 | 76097.935 | 281.201 |
| t0_12_t3_17_global_p0 | 69.191 | 0.539 | 0.956 | 0.252 | 24035.648 | 75964.352 | 282.772 |

All per-100,000 values above are five-seed means. Their component 95% intervals and every candidate's ranking are retained in the JSON.

## Status

- Candidate and code hashes are frozen in the JSON only after every expected joint shard is present.
- New holdout collection remains paused. No candidate is released.
