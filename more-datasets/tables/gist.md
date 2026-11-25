# GIST-960 (l2)

Base 1000000 x 960, metric l2; queries: 1000 in the source, 998 unique, 499 calibration / 499 held-out.

## Coverage protocol, fixed ef calibrated at 99.5%, check-set gate 99%, rule C+m

| dataset | calibration / check | k | R | fixed ef | alpha (rule C) | coverage fixed -> ES | mean recall loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out | >=10% QPS both |
|---|---|---:|---:|---:|---|---|---:|---:|---|---|---|---|
| gist | 99.5% / 99% | 10 | 0.80 | 548 | 1.25 (1.2) | 98.60% -> 98.60% | 0.02 pt | 8.4% |  /  |  /  | fixed misses the check-set gate on held-out | no |
| gist | 99.5% / 99% | 10 | 0.90 | 1418 | 1.28 (1.22) | 98.40% -> 98.40% | 0.02 pt | 14.7% |  /  |  /  | fixed misses the check-set gate on held-out | no |
| gist | 99.5% / 99% | 100 | 0.80 | 581 | 1.12 (1.09) | 99.00% -> 99.00% | 0.02 pt | 3.3% |  /  |  /  | fixed misses the check-set gate on held-out | no |
| gist | 99.5% / 99% | 100 | 0.90 | 1368 | 1.15 (1.12) | 99.00% -> 99.00% | 0.05 pt | 9.5% |  /  |  /  | fixed misses the check-set gate on held-out | no |
| gist | 99.5% / 99% | 100 | 0.95 | 2997 | 1.19 (1.15) | 98.40% -> 98.40% | 0.03 pt | 14.6% |  /  |  /  | fixed misses the check-set gate on held-out | no |

### Calibrated at 99.5% (check-set gate 99%), by alpha rule (rule C, C+m with m = 0.10, C+m with m = 0.25)

| calibration / check | k | R | fixed ef | rule | alpha | coverage fixed -> ES | added failures | mean recall loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out |
|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|---|
| 99.5% / 99% | 10 | 0.80 | 548 | C | 1.2 | 98.60% -> 98.40% | 1 | 0.22 pt | 17.8% | +22.6% / +21.8% | -1.0% / -0.2% | fixed misses the gate |
| 99.5% / 99% | 10 | 0.80 | 548 | C+m 0.10 | 1.22 | 98.60% -> 98.40% | 1 | 0.06 pt | 12.7% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 10 | 0.80 | 548 | C+m 0.25 | 1.25 | 98.60% -> 98.60% | 0 | 0.02 pt | 8.4% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 10 | 0.90 | 1418 | C | 1.22 | 98.40% -> 98.00% | 2 | 0.12 pt | 32.1% | +47.5% / +47.4% | -1.2% / -0.6% | fixed misses the gate |
| 99.5% / 99% | 10 | 0.90 | 1418 | C+m 0.10 | 1.25 | 98.40% -> 98.20% | 1 | 0.04 pt | 21.3% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 10 | 0.90 | 1418 | C+m 0.25 | 1.28 | 98.40% -> 98.40% | 0 | 0.02 pt | 14.7% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 100 | 0.80 | 581 | C | 1.09 | 99.00% -> 99.00% | 0 | 0.26 pt | 9.8% | +9.1% / +10.9% | +0.8% / -0.4% | fixed misses the gate |
| 99.5% / 99% | 100 | 0.80 | 581 | C+m 0.10 | 1.1 | 99.00% -> 99.00% | 0 | 0.11 pt | 6.5% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 100 | 0.80 | 581 | C+m 0.25 | 1.12 | 99.00% -> 99.00% | 0 | 0.02 pt | 3.3% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 100 | 0.90 | 1368 | C | 1.12 | 99.00% -> 99.00% | 0 | 0.30 pt | 21.6% | +26.6% / +27.5% | -0.3% / -1.2% | fixed misses the gate |
| 99.5% / 99% | 100 | 0.90 | 1368 | C+m 0.10 | 1.14 | 99.00% -> 99.00% | 0 | 0.10 pt | 12.3% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 100 | 0.90 | 1368 | C+m 0.25 | 1.15 | 99.00% -> 99.00% | 0 | 0.05 pt | 9.5% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 100 | 0.95 | 2997 | C | 1.15 | 98.40% -> 98.00% | 2 | 0.25 pt | 32.3% | +47.1% / +47.9% | -1.5% / -2.1% | fixed misses the gate |
| 99.5% / 99% | 100 | 0.95 | 2997 | C+m 0.10 | 1.17 | 98.40% -> 98.40% | 0 | 0.10 pt | 21.6% |  /  |  /  | fixed misses the gate |
| 99.5% / 99% | 100 | 0.95 | 2997 | C+m 0.25 | 1.19 | 98.40% -> 98.40% | 0 | 0.03 pt | 14.6% |  /  |  /  | fixed misses the gate |

| calibration / check | rule | points evaluated | pass | pass with >=10% QPS at 1t and 8t | failing points (queries short of the gate) |
|---|---|---:|---:|---:|---|
| 99.5% / 99% | C | 5 | 0 | 0 | - |
| 99.5% / 99% | C+m 0.10 | 5 | 0 | 0 | - |
| 99.5% / 99% | C+m 0.25 | 5 | 0 | 0 | - |

Points not evaluated: k10 R0.95 (fixed search reaches R on 494 of 499 calibration queries at ef 8192; calibrating at 99.5% needs 497).

### Default alpha (early_stop without alpha: 1.5 at k = 10, 1.15 at k = 100), calibrated at 99.5% (check-set gate 99%)

| calibration / check | k | R | fixed ef | alpha | coverage fixed -> default | mean recall loss | dist. comp. saved | held-out | QPS 1t / 8t | P99 1t / 8t |
|---|---:|---:|---:|---:|---|---:|---:|---|---|---|
| 99.5% / 99% | 10 | 0.80 | 548 | 1.5 | 98.60% -> 98.60% | 0.00 pt | 0.8% | fixed_fails |  /  |  /  |
| 99.5% / 99% | 10 | 0.90 | 1418 | 1.5 | 98.40% -> 98.40% | 0.00 pt | 2.3% | fixed_fails |  /  |  /  |
| 99.5% / 99% | 100 | 0.80 | 581 | 1.15 | 99.00% -> 99.00% | 0.00 pt | 1.3% | fixed_fails |  /  |  /  |
| 99.5% / 99% | 100 | 0.90 | 1368 | 1.15 | 99.00% -> 99.00% | 0.05 pt | 9.5% | fixed_fails |  /  |  /  |
| 99.5% / 99% | 100 | 0.95 | 2997 | 1.15 | 98.40% -> 98.00% | 0.25 pt | 32.3% | fixed_fails |  /  |  /  |

### Diagnostics on the calibration queries at the fixed ef, calibrated at 99.5%

| calibration / check | k | R | ef / k | fixed mean dist. comp. | queries with final recall at alpha 1.00 | work at alpha 1.00 / fixed | per-query work to final recall / fixed: median (q25-q75) |
|---|---:|---:|---:|---:|---:|---:|---|
| 99.5% / 99% | 10 | 0.80 | 54.80 | 9563 | 3.0% | 0.05 | 0.31 (0.18-0.55) |
| 99.5% / 99% | 10 | 0.90 | 141.80 | 20137 | 3.0% | 0.02 | 0.17 (0.09-0.30) |
| 99.5% / 99% | 100 | 0.80 | 5.81 | 10022 | 0.8% | 0.23 | 0.93 (0.75-1.00) |
| 99.5% / 99% | 100 | 0.90 | 13.68 | 19593 | 0.8% | 0.12 | 0.73 (0.48-0.91) |
| 99.5% / 99% | 100 | 0.95 | 29.97 | 35156 | 0.8% | 0.07 | 0.49 (0.29-0.75) |

Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.

## Fixed ef vs per-query ideal width (held-out queries; distance computations)

gap = mean distance computations at the fixed ef / mean over queries of the distance computations at the query's smallest width in {round(k 1.1^i) <= fixed ef} U {fixed ef} that reaches R; a query that no tested width up to the fixed ef brings to R is charged the fixed ef's work. Rule C recovers = (fixed work - rule C work) / (fixed work - ideal work), shown only where rule C passes its check (loss <= 0.5 pt and early stop reaching R on >= ceil(L n) held-out queries, L = 0.99 at the 99.5% level, else the calibration level).

| k | R | calibration level | fixed ef | gap (distance computations) | rule C alpha | rule C recovers | no tested width up to the fixed ef reaches R | per-query ideal width: median / p90 / p99 |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 10 | 0.80 | 99.5% | 548 | 4.76 | 1.2 | check fails | 7 of 499 | 42 / 192 / 548 |
| 10 | 0.80 | 99% | 467 | 4.23 | 1.19 | check fails | 9 of 499 | 42 / 192 / 467 |
| 10 | 0.80 | 95% | 214 | 2.43 | 1.17 | check fails | 40 of 499 | 42 / 192 / 214 |
| 10 | 0.80 | 90% | 150 | 1.96 | 1.16 | check fails | 66 of 499 | 42 / 150 / 150 |
| 10 | 0.90 | 99.5% | 1418 | 6.06 | 1.22 | check fails | 8 of 499 | 74 / 340 / 1418 |
| 10 | 0.90 | 99% | 932 | 4.57 | 1.21 | check fails | 13 of 499 | 74 / 340 / 932 |
| 10 | 0.90 | 95% | 465 | 2.90 | 1.2 | check fails | 33 of 499 | 74 / 340 / 465 |
| 10 | 0.90 | 90% | 284 | 2.16 | 1.2 | check fails | 58 of 499 | 74 / 284 / 284 |
| 10 | 0.95 | 95% | 1411 | 3.51 | 1.31875 | check fails | 34 of 499 | 144 / 882 / 1411 |
| 10 | 0.95 | 90% | 735 | 2.45 | 1.31875 | check fails | 60 of 499 | 144 / 735 / 735 |
| 100 | 0.80 | 99.5% | 581 | 2.58 | 1.09 | check fails | 5 of 499 | 133 / 345 / 581 |
| 100 | 0.80 | 99% | 529 | 2.40 | 1.09 | check fails | 7 of 499 | 133 / 345 / 529 |
| 100 | 0.80 | 95% | 340 | 1.73 | 1.07 | check fails | 40 of 499 | 133 / 340 / 340 |
| 100 | 0.80 | 90% | 271 | 1.50 | 1.06 | check fails | 77 of 499 | 133 / 271 / 271 |
| 100 | 0.90 | 99.5% | 1368 | 3.12 | 1.12 | check fails | 5 of 499 | 236 / 673 / 1368 |
| 100 | 0.90 | 99% | 1199 | 2.83 | 1.12 | check fails | 6 of 499 | 236 / 673 / 1199 |
| 100 | 0.90 | 95% | 739 | 2.00 | 1.11 | check fails | 27 of 499 | 236 / 673 / 739 |
| 100 | 0.90 | 90% | 557 | 1.68 | 1.09 | check fails | 68 of 499 | 236 / 557 / 557 |
| 100 | 0.95 | 99.5% | 2997 | 3.58 | 1.15 | check fails | 8 of 499 | 380 / 1192 / 2997 |
| 100 | 0.95 | 99% | 2399 | 3.08 | 1.15 | check fails | 13 of 499 | 380 / 1192 / 2399 |
| 100 | 0.95 | 95% | 1365 | 2.14 | 1.14 | check fails | 37 of 499 | 380 / 1192 / 1365 |
| 100 | 0.95 | 90% | 975 | 1.76 | 1.12 | check fails | 70 of 499 | 380 / 975 / 975 |

