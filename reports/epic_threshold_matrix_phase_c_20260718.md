# Epic Threshold Matrix Phase C

Phase C only re-aggregates completed Phase B formal runs=10 base shards. No new formal paths, production policy changes, or holdout were used.

## Efficiency And Risk Pareto

| candidate | gain vs current /100 stamina | retains global12/17 gain | positive false-stop probability mass | status |
|---|---:|---:|---:|---|
| current_formal | 0.000000 | 0.00% | 0.000000 | reference |
| global_10_14 | 0.000425 | 52.52% | 0.800000 | conservative_history |
| global_12_17 | 0.000810 | 100.00% | 3.700000 | balanced_reference |
| global_14_18 | 0.001165 | 143.91% | 8.000000 | aggressive_reference |
| balanced_output_m2 | 0.000681 | 84.14% | 3.700000 | user_review |
| balanced_output_m4 | 0.000515 | 63.58% | 2.200000 | user_review |
| balanced_high_priority_m2 | 0.000541 | 66.80% | 1.800000 | user_review |

## Node Risk

| candidate | +0 stop rate | +0 false stops | +3 stop rate | +3 false branches | +3 false mass | utility loss | regret | saved stamina |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| current_formal | 0.00% | 0 | 0.00% | 0 | 0.000000 | 0.000000 | 2.150206 | 0.000 |
| global_10_14 | 3.82% | 0 | 14.31% | 16 | 0.800000 | 0.004881 | 1.745724 | 273.552 |
| global_12_17 | 16.56% | 2 | 17.00% | 34 | 1.700000 | 0.044772 | 1.435395 | 337.846 |
| global_14_18 | 35.67% | 7 | 8.50% | 20 | 1.000000 | 0.190656 | 1.275458 | 259.084 |
| balanced_output_m2 | 11.46% | 2 | 17.07% | 34 | 1.700000 | 0.044772 | 1.562561 | 336.199 |
| balanced_output_m4 | 8.92% | 2 | 12.01% | 4 | 0.200000 | 0.005320 | 1.665712 | 250.961 |
| balanced_high_priority_m2 | 4.46% | 0 | 18.68% | 36 | 1.800000 | 0.042477 | 1.680325 | 353.342 |

## Status

- Offline ranking and release gates are intentionally separate.
- No balanced candidate is selected automatically; user confirmation is required before hashing or new stratified holdout design.
