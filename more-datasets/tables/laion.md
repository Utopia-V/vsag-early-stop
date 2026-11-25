# LAION 1M (cosine), original index

Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.

## Fixed ef vs per-query ideal width (held-out queries; distance computations)

gap = mean distance computations at the fixed ef / mean over queries of the distance computations at the query's smallest width in {round(k 1.1^i) <= fixed ef} U {fixed ef} that reaches R; a query that no tested width up to the fixed ef brings to R is charged the fixed ef's work. Rule C recovers = (fixed work - rule C work) / (fixed work - ideal work), shown only where rule C passes its check (loss <= 0.5 pt and early stop reaching R on >= ceil(L n) held-out queries, L = 0.99 at the 99.5% level, else the calibration level).

| k | R | calibration level | fixed ef | gap (distance computations) | rule C alpha | rule C recovers | no tested width up to the fixed ef reaches R | per-query ideal width: median / p90 / p99 |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 10 | 0.80 | 99.5% | 612 | 13.33 | 1.18 | check fails | 0 of 53 | 10 / 23 / 92 |
| 10 | 0.80 | 99% | 147 | 4.36 | 1.17 | check fails | 0 of 53 | 10 / 23 / 92 |
| 10 | 0.80 | 97.5% | 60 | 2.37 | 1.14 | check fails | 2 of 53 | 10 / 23 / 60 |
| 10 | 0.80 | 95% | 39 | 1.82 | 1.12 | 27% | 2 of 53 | 10 / 23 / 39 |
| 10 | 0.80 | 90% | 28 | 1.51 | 1.12 | 10% | 3 of 53 | 10 / 23 / 28 |
| 10 | 0.90 | 99.5% | 684 | 11.94 | 1.21 | 73% | 0 of 53 | 10 / 28 / 197 |
| 10 | 0.90 | 99% | 525 | 9.68 | 1.21 | 69% | 0 of 53 | 10 / 28 / 197 |
| 10 | 0.90 | 97.5% | 156 | 4.00 | 1.17 | check fails | 1 of 53 | 10 / 28 / 137 |
| 10 | 0.90 | 95% | 75 | 2.53 | 1.17 | check fails | 3 of 53 | 10 / 28 / 75 |
| 10 | 0.90 | 90% | 46 | 1.89 | 1.17 | 15% | 4 of 53 | 10 / 28 / 46 |
| 10 | 0.95 | 99.5% | 5999 | 42.18 | 1.3 | 88% | 0 of 53 | 16 / 92 / 579 |
| 10 | 0.95 | 99% | 3556 | 27.63 | 1.3 | 82% | 0 of 53 | 16 / 92 / 579 |
| 10 | 0.95 | 97.5% | 265 | 4.13 | 1.28 | check fails | 2 of 53 | 16 / 92 / 265 |
| 10 | 0.95 | 95% | 146 | 2.84 | 1.28 | check fails | 3 of 53 | 16 / 92 / 146 |
| 10 | 0.95 | 90% | 88 | 2.18 | 1.25 | check fails | 6 of 53 | 16 / 84 / 88 |
| 100 | 0.80 | 99.5% | 500 | 3.45 | 1.07 | 59% | 0 of 53 | 100 / 100 / 121 |
| 100 | 0.80 | 99% | 146 | 1.32 | 1.03 | 23% | 0 of 53 | 100 / 100 / 121 |
| 100 | 0.80 | 97.5% | 114 | 1.10 | - | - | 2 of 53 | 100 / 100 / 114 |
| 100 | 0.80 | 95% | 100 | 1.00 | - | - | 4 of 53 | 100 / 100 / 100 |
| 100 | 0.80 | 90% | 100 | 1.00 | - | - | 4 of 53 | 100 / 100 / 100 |
| 100 | 0.90 | 99.5% | 676 | 4.07 | 1.08 | 65% | 0 of 53 | 100 / 119 / 248 |
| 100 | 0.90 | 99% | 303 | 2.16 | 1.06 | 46% | 0 of 53 | 100 / 119 / 248 |
| 100 | 0.90 | 97.5% | 189 | 1.53 | 1.04 | check fails | 2 of 53 | 100 / 119 / 189 |
| 100 | 0.90 | 95% | 157 | 1.34 | 1.03 | check fails | 3 of 53 | 100 / 119 / 157 |
| 100 | 0.90 | 90% | 119 | 1.11 | - | - | 5 of 53 | 100 / 117 / 119 |
| 100 | 0.95 | 99.5% | 2283 | 9.79 | 1.12 | 78% | 0 of 53 | 100 / 143 / 365 |
| 100 | 0.95 | 99% | 684 | 3.74 | 1.09 | 60% | 0 of 53 | 100 / 143 / 365 |
| 100 | 0.95 | 97.5% | 361 | 2.30 | 1.07 | 49% | 1 of 53 | 100 / 143 / 296 |
| 100 | 0.95 | 95% | 247 | 1.73 | 1.06 | 37% | 1 of 53 | 100 / 143 / 241 |
| 100 | 0.95 | 90% | 179 | 1.39 | 1.05 | 24% | 3 of 53 | 100 / 143 / 179 |

## First measurement, fixed ef calibrated at 99.5% (check-set gate 99%): rule C alphas (no margin) and the September-freeze alphas, timed now

Held-out quality from repro-package results/quality/summary-v4.json (not rerun); timing: current PR build against current main at the same fixed ef.

| calibration / check | k | R | fixed ef | rule | alpha | held-out coverage fixed -> ES | loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---|
| 99.5% / 99% | 10 | 0.80 | 612 | C | 1.18 | 100.00% -> 100.00% | 0.57 pt | 73.7% | +212.8% / +255.5% | -21.5% / -30.0% |
| 99.5% / 99% | 10 | 0.80 | 612 | Sept. | 1.5 | 100.00% -> 100.00% | 0.00 pt | 19.4% | +20.9% / +22.9% | +1.1% / -1.4% |
| 99.5% / 99% | 10 | 0.90 | 684 | C | 1.21 | 100.00% -> 100.00% | 0.00 pt | 67.3% | +163.1% / +190.9% | +0.1% / -7.6% |
| 99.5% / 99% | 10 | 0.90 | 684 | Sept. | 1.5 | 100.00% -> 100.00% | 0.00 pt | 20.9% | +23.2% / +25.6% | +0.9% / -1.8% |
| 99.5% / 99% | 10 | 0.95 | 5999 | C | 1.3 | 100.00% -> 100.00% | 0.00 pt | 86.0% | +474.9% / +528.9% | -41.2% / -47.0% |
| 99.5% / 99% | 10 | 0.95 | 5999 | Sept. | 2 | 100.00% -> 100.00% | 0.00 pt | 25.5% | +30.6% / +32.6% | +1.0% / -0.6% |
| 99.5% / 99% | 100 | 0.80 | 500 | C | 1.07 | 100.00% -> 100.00% | 0.13 pt | 41.8% | +56.3% / +66.5% | -9.0% / -14.2% |
| 99.5% / 99% | 100 | 0.80 | 500 | Sept. | 1.15 | 100.00% -> 100.00% | 0.00 pt | 14.5% | +13.3% / +15.6% | +1.9% / -1.2% |
| 99.5% / 99% | 100 | 0.90 | 676 | C | 1.08 | 100.00% -> 100.00% | 0.09 pt | 49.2% | +75.5% / +89.3% | -9.9% / -16.9% |
| 99.5% / 99% | 100 | 0.90 | 676 | Sept. | 1.15 | 100.00% -> 100.00% | 0.00 pt | 22.8% | +24.2% / +28.2% | +1.6% / -1.9% |
| 99.5% / 99% | 100 | 0.95 | 2283 | C | 1.12 | 100.00% -> 100.00% | 0.06 pt | 70.2% | +171.2% / +201.9% | -24.7% / -33.1% |
| 99.5% / 99% | 100 | 0.95 | 2283 | Sept. | 1.31875 | 100.00% -> 100.00% | 0.00 pt | 23.0% | +25.7% / +28.4% | +1.5% / -2.2% |

