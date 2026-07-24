# Epic non-speed +0/+3 threshold matrix (2026-07-17)

## Scope

- Development-only: 157 real +0 items and probability-weighted official +3 branches.
- Old frozen validation is not read. A new independent +0 holdout is required after this matrix freezes.
- Production policy, DP, roll table, resource model, GUI, and automation remain unchanged.

## Node Matrix

| Route | Priority route | +0 stop rate | +3 stop rate conditional on reach | +0 positive false stops | +3 positive false stops | +0/+3 regret | Next-node stamina saved | Node gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| t0_10_t3_14 | yes | 19.11% | 10.77% | 0 | 0 | 0.254144/1.108004 | 252.738 | pass |
| t0_10_t3_16 | yes | 19.11% | 15.90% | 0 | 12 | 0.254144/1.046229 | 326.571 | blocked |
| t0_10_t3_17 | yes | 19.11% | 18.48% | 0 | 16 | 0.254144/1.006781 | 364.796 | blocked |
| t0_10_t3_18 | yes | 19.11% | 22.35% | 0 | 20 | 0.254144/0.944561 | 422.683 | blocked |
| t0_10_t3_20 | yes | 19.11% | 30.18% | 0 | 61 | 0.254144/0.916560 | 538.815 | blocked |
| t0_12_t3_14 | no | 31.21% | 6.36% | 2 | 0 | 0.209196/0.950065 | 247.086 | blocked |
| t0_12_t3_16 | yes | 31.21% | 9.17% | 2 | 12 | 0.209196/0.938679 | 280.648 | blocked |
| t0_12_t3_17 | yes | 31.21% | 10.00% | 2 | 16 | 0.209196/0.933802 | 291.245 | blocked |
| t0_12_t3_18 | yes | 31.21% | 12.57% | 2 | 20 | 0.209196/0.901901 | 324.447 | blocked |
| t0_12_t3_20 | yes | 31.21% | 17.90% | 2 | 46 | 0.209196/0.897489 | 392.292 | blocked |
| t0_14_t3_14 | no | 43.31% | 0.00% | 8 | 0 | 0.316785/0.813061 | 330.555 | blocked |
| t0_14_t3_16 | no | 43.31% | 2.36% | 8 | 12 | 0.316785/0.813909 | 353.033 | blocked |
| t0_14_t3_17 | no | 43.31% | 2.64% | 8 | 14 | 0.316785/0.816742 | 355.709 | blocked |
| t0_14_t3_18 | yes | 43.31% | 2.87% | 8 | 16 | 0.316785/0.820414 | 357.849 | blocked |
| t0_14_t3_20 | yes | 43.31% | 4.04% | 8 | 24 | 0.316785/0.846350 | 369.088 | blocked |

## Controlled Comparisons

- Fixed T0=12: compare T3=16/17/18/20 on identical real items and official +3 branches.
- Fixed T3=18: compare T0=10/12/14 on identical real items and official +3 branches.

### Fixed T0=12

| T3 | +0 positive false stops | +3 positive false stops | +0/+3 positive recall | Node gate |
|---:|---:|---:|---:|---|
| 16 | 2 | 12 | 96.15%/98.45% | blocked |
| 17 | 2 | 16 | 96.15%/97.93% | blocked |
| 18 | 2 | 20 | 96.15%/97.42% | blocked |
| 20 | 2 | 46 | 96.15%/93.44% | blocked |

### Fixed T3=18

| T0 | +0 positive false stops | +3 positive false stops | +0/+3 positive recall | Node gate |
|---:|---:|---:|---:|---|
| 10 | 0 | 20 | 100.00%/97.47% | blocked |
| 12 | 2 | 20 | 96.15%/97.42% | blocked |
| 14 | 8 | 16 | 84.62%/97.79% | blocked |

### Requested T0=12 / T3=17

- Node gate: blocked.
- Clear-positive false stops: +0=2, +3=16.
- It is intentionally excluded from the joint pool because the study protocol forbids running a failed node candidate there.

## Five-Seed Joint Pool

Only node-gated routes are included. All differences use identical items, official +3 branches, five seeds, Heroic M1, and the explicit Rift/Saint pool.

| Heroic yield | Route | Formal value / 100 stamina difference 95% CI |
|---|---|---:|
| yield_minus_20pct | t0_10_t3_14 | [0.000597, 0.000931] |
| baseline | t0_10_t3_14 | [0.000492, 0.000798] |
| yield_plus_20pct | t0_10_t3_14 | [0.000418, 0.000698] |

## Example Per 100,000 Total Stamina

First shared seed with baseline Heroic yield. Absolute values are conditional on the development non-speed Epic cohort, not account-wide drop rates.

| Route | Formal value | Native 75+ | Converted 75+ | 22+ | Output 60 | Rift stamina | Saint 3-7 stamina | Cycles |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| current_formal | 81.864 | 0.582 | 0.995 | 2.774 | 0.020 | 24019.149 | 75980.851 | 282.578 |
| t0_10_t3_14 | 82.621 | 0.588 | 1.004 | 2.800 | 0.020 | 24241.088 | 75758.912 | 285.189 |

## Release Status

- Matrix and risk tiers are frozen by the recorded freeze SHA-256.
- A new independent real +0 holdout (minimum 48; 64 recommended) is required before any policy release.
- This study does not modify the released Epic policy.
