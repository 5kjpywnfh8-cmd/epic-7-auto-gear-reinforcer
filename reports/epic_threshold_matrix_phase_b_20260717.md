# Epic Threshold Matrix Phase B

Candidate-consistent offline research. Phase A is preserved as `global_uniform_phase_a`; no production policy is changed.

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
| yield_minus_20pct | t0_14_t3_20_global_p0 | [0.000490, 0.001038] |
| yield_minus_20pct | t0_14_t3_18_global_p0 | [0.000475, 0.001006] |
| yield_minus_20pct | t0_14_t3_17_global_p0 | [0.000472, 0.001001] |
| yield_minus_20pct | t0_14_t3_16_global_p0 | [0.000470, 0.000996] |
| yield_minus_20pct | t0_14_t3_14_global_p0 | [0.000424, 0.000898] |
| yield_minus_20pct | t0_12_t3_20_global_p0 | [0.000412, 0.000872] |
| yield_minus_20pct | t0_10_t3_20_global_p0 | [0.000380, 0.000806] |
| yield_minus_20pct | t0_12_t3_18_global_p0 | [0.000352, 0.000745] |
| yield_minus_20pct | t0_12_t3_17_global_p0 | [0.000330, 0.000698] |
| yield_minus_20pct | t0_12_t3_16_global_p0 | [0.000320, 0.000678] |
| yield_minus_20pct | t0_10_t3_18_global_p0 | [0.000295, 0.000624] |
| yield_minus_20pct | t0_12_t3_14_global_p0 | [0.000273, 0.000578] |
| yield_minus_20pct | t0_10_t3_17_global_p0 | [0.000262, 0.000555] |
| yield_minus_20pct | t0_10_t3_14_pure_output_p2 | [0.000256, 0.000543] |
| yield_minus_20pct | t0_10_t3_16_global_p0 | [0.000239, 0.000506] |
| yield_minus_20pct | t0_10_t3_14_pure_tank_p2 | [0.000234, 0.000497] |
| yield_minus_20pct | t0_10_t3_14_bruiser_m2 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_bruiser_p0 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_bruiser_p2 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_dual_m2 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_dual_p0 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_dual_p2 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_global_p0 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_pure_output_p0 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_pure_tank_p0 | [0.000173, 0.000366] |
| yield_minus_20pct | t0_10_t3_14_pure_tank_m2 | [0.000159, 0.000336] |
| yield_minus_20pct | t0_10_t3_14_pure_output_m2 | [0.000085, 0.000181] |
| yield_minus_20pct | current_formal | [0.000000, 0.000000] |
| baseline | t0_14_t3_20_global_p0 | [0.000355, 0.000797] |
| baseline | t0_14_t3_18_global_p0 | [0.000344, 0.000772] |
| baseline | t0_14_t3_17_global_p0 | [0.000342, 0.000768] |
| baseline | t0_14_t3_16_global_p0 | [0.000340, 0.000764] |
| baseline | t0_14_t3_14_global_p0 | [0.000307, 0.000689] |
| baseline | t0_12_t3_20_global_p0 | [0.000298, 0.000670] |
| baseline | t0_10_t3_20_global_p0 | [0.000276, 0.000618] |
| baseline | t0_12_t3_18_global_p0 | [0.000255, 0.000572] |
| baseline | t0_12_t3_17_global_p0 | [0.000239, 0.000536] |
| baseline | t0_12_t3_16_global_p0 | [0.000232, 0.000521] |
| baseline | t0_10_t3_18_global_p0 | [0.000214, 0.000480] |
| baseline | t0_12_t3_14_global_p0 | [0.000198, 0.000444] |
| baseline | t0_10_t3_17_global_p0 | [0.000190, 0.000426] |
| baseline | t0_10_t3_14_pure_output_p2 | [0.000186, 0.000417] |
| baseline | t0_10_t3_16_global_p0 | [0.000173, 0.000389] |
| baseline | t0_10_t3_14_pure_tank_p2 | [0.000170, 0.000382] |
| baseline | t0_10_t3_14_bruiser_m2 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_bruiser_p0 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_bruiser_p2 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_dual_m2 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_dual_p0 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_dual_p2 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_global_p0 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_pure_output_p0 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_pure_tank_p0 | [0.000125, 0.000282] |
| baseline | t0_10_t3_14_pure_tank_m2 | [0.000115, 0.000259] |
| baseline | t0_10_t3_14_pure_output_m2 | [0.000062, 0.000139] |
| baseline | current_formal | [0.000000, 0.000000] |
| yield_plus_20pct | t0_14_t3_20_global_p0 | [0.000266, 0.000637] |
| yield_plus_20pct | t0_14_t3_18_global_p0 | [0.000258, 0.000617] |
| yield_plus_20pct | t0_14_t3_17_global_p0 | [0.000256, 0.000614] |
| yield_plus_20pct | t0_14_t3_16_global_p0 | [0.000255, 0.000611] |
| yield_plus_20pct | t0_14_t3_14_global_p0 | [0.000230, 0.000551] |
| yield_plus_20pct | t0_12_t3_20_global_p0 | [0.000224, 0.000535] |
| yield_plus_20pct | t0_10_t3_20_global_p0 | [0.000206, 0.000494] |
| yield_plus_20pct | t0_12_t3_18_global_p0 | [0.000191, 0.000457] |
| yield_plus_20pct | t0_12_t3_17_global_p0 | [0.000179, 0.000429] |
| yield_plus_20pct | t0_12_t3_16_global_p0 | [0.000174, 0.000416] |
| yield_plus_20pct | t0_10_t3_18_global_p0 | [0.000160, 0.000384] |
| yield_plus_20pct | t0_12_t3_14_global_p0 | [0.000148, 0.000355] |
| yield_plus_20pct | t0_10_t3_17_global_p0 | [0.000142, 0.000341] |
| yield_plus_20pct | t0_10_t3_14_pure_output_p2 | [0.000139, 0.000334] |
| yield_plus_20pct | t0_10_t3_16_global_p0 | [0.000130, 0.000311] |
| yield_plus_20pct | t0_10_t3_14_pure_tank_p2 | [0.000127, 0.000305] |
| yield_plus_20pct | t0_10_t3_14_bruiser_m2 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_bruiser_p0 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_bruiser_p2 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_dual_m2 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_dual_p0 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_dual_p2 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_global_p0 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_pure_output_p0 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_pure_tank_p0 | [0.000094, 0.000225] |
| yield_plus_20pct | t0_10_t3_14_pure_tank_m2 | [0.000086, 0.000207] |
| yield_plus_20pct | t0_10_t3_14_pure_output_m2 | [0.000046, 0.000111] |
| yield_plus_20pct | current_formal | [0.000000, 0.000000] |

## Per 100,000 Total Stamina

| route | formal value | native 75+ | converted 75+ | 22+ | Rift stamina | Saint 3-7 stamina | cycles |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_formal | 31.386 | 0.669 | 1.267 | 0.000 | 24809.949 | 75190.051 | 291.882 |
| t0_10_t3_14_global_p0 | 31.590 | 0.674 | 1.275 | 0.000 | 24971.319 | 75028.681 | 293.780 |
| t0_12_t3_17_global_p0 | 31.774 | 0.678 | 1.283 | 0.000 | 25117.254 | 74882.746 | 295.497 |

All per-100,000 values above are five-seed means. Their component 95% intervals and every candidate's ranking are retained in the JSON.

## Status

- Candidate and code hashes are frozen in the JSON only after every expected joint shard is present.
- New holdout collection remains paused. No candidate is released.
