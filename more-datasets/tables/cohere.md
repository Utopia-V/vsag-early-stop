# Cohere 1M (cosine), original index

Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.

## Fixed ef vs per-query ideal width (held-out queries; distance computations)

gap = mean distance computations at the fixed ef / mean over queries of the distance computations at the query's smallest width in {round(k 1.1^i) <= fixed ef} U {fixed ef} that reaches R; a query that no tested width up to the fixed ef brings to R is charged the fixed ef's work. Rule C recovers = (fixed work - rule C work) / (fixed work - ideal work), shown only where rule C passes its check (loss <= 0.5 pt and early stop reaching R on >= ceil(L n) held-out queries, L = 0.99 at the 99.5% level, else the calibration level).

| k | R | calibration level | fixed ef | gap (distance computations) | rule C alpha | rule C recovers | no tested width up to the fixed ef reaches R | per-query ideal width: median / p90 / p99 |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 10 | 0.80 | 99.5% | 115 | 3.77 | 1.21 | check fails | 7 of 601 | 10 / 29 / 115 |
| 10 | 0.80 | 99% | 84 | 2.96 | 1.19 | check fails | 12 of 601 | 10 / 29 / 84 |
| 10 | 0.80 | 97.5% | 64 | 2.43 | 1.17 | check fails | 18 of 601 | 10 / 29 / 64 |
| 10 | 0.80 | 95% | 44 | 1.88 | 1.14 | 20% | 27 of 601 | 10 / 29 / 44 |
| 10 | 0.80 | 90% | 31 | 1.52 | 1.11 | check fails | 43 of 601 | 10 / 29 / 31 |
| 10 | 0.90 | 99.5% | 172 | 4.22 | 1.26 | check fails | 5 of 601 | 13 / 51 / 172 |
| 10 | 0.90 | 99% | 160 | 3.99 | 1.26 | check fails | 7 of 601 | 13 / 51 / 160 |
| 10 | 0.90 | 97.5% | 113 | 3.05 | 1.26 | check fails | 17 of 601 | 13 / 51 / 113 |
| 10 | 0.90 | 95% | 85 | 2.48 | 1.225 | 15% | 27 of 601 | 13 / 51 / 85 |
| 10 | 0.90 | 90% | 51 | 1.78 | 1.14 | check fails | 57 of 601 | 13 / 51 / 51 |
| 10 | 0.95 | 99.5% | 3118 | 22.41 | 1.65 | 12% | 5 of 601 | 26 / 144 / 802 |
| 10 | 0.95 | 99% | 1135 | 10.82 | 1.4 | check fails | 6 of 601 | 26 / 144 / 802 |
| 10 | 0.95 | 97.5% | 531 | 6.04 | 1.4 | check fails | 12 of 601 | 26 / 144 / 531 |
| 10 | 0.95 | 95% | 189 | 2.88 | 1.36 | check fails | 38 of 601 | 26 / 144 / 189 |
| 10 | 0.95 | 90% | 132 | 2.28 | 1.3 | check fails | 63 of 601 | 26 / 132 / 132 |
| 100 | 0.80 | 99.5% | 159 | 1.44 | 1.03 | check fails | 9 of 601 | 100 / 100 / 159 |
| 100 | 0.80 | 99% | 155 | 1.41 | 1.03 | check fails | 9 of 601 | 100 / 100 / 155 |
| 100 | 0.80 | 97.5% | 123 | 1.17 | - | - | 25 of 601 | 100 / 100 / 123 |
| 100 | 0.80 | 95% | 100 | 1.00 | - | - | 41 of 601 | 100 / 100 / 100 |
| 100 | 0.80 | 90% | 100 | 1.00 | - | - | 41 of 601 | 100 / 100 / 100 |
| 100 | 0.90 | 99.5% | 381 | 2.63 | 1.08 | 31% | 0 of 601 | 100 / 177 / 314 |
| 100 | 0.90 | 99% | 298 | 2.14 | 1.07 | check fails | 9 of 601 | 100 / 177 / 298 |
| 100 | 0.90 | 97.5% | 253 | 1.88 | 1.06 | check fails | 18 of 601 | 100 / 177 / 253 |
| 100 | 0.90 | 95% | 216 | 1.66 | 1.05 | 25% | 29 of 601 | 100 / 177 / 216 |
| 100 | 0.90 | 90% | 152 | 1.29 | 1.03 | check fails | 74 of 601 | 100 / 152 / 152 |
| 100 | 0.95 | 99.5% | 814 | 3.84 | 1.1 | 57% | 2 of 601 | 121 / 285 / 612 |
| 100 | 0.95 | 99% | 517 | 2.64 | 1.09 | check fails | 12 of 601 | 121 / 285 / 517 |
| 100 | 0.95 | 97.5% | 448 | 2.36 | 1.08 | check fails | 20 of 601 | 121 / 285 / 448 |
| 100 | 0.95 | 95% | 338 | 1.91 | 1.08 | check fails | 40 of 601 | 121 / 285 / 338 |
| 100 | 0.95 | 90% | 274 | 1.65 | 1.08 | check fails | 62 of 601 | 121 / 274 / 274 |

## First measurement, fixed ef calibrated at 99.5% (check-set gate 99%): rule C alphas (no margin) and the September-freeze alphas, timed now

Held-out quality from repro-package results/quality/summary-v4.json (not rerun); timing: current PR build against current main at the same fixed ef.

| calibration / check | k | R | fixed ef | rule | alpha | held-out coverage fixed -> ES | loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---|
| 99.5% / 99% | 10 | 0.80 | 115 | C | 1.21 | 98.84% -> 98.84% | 0.38 pt | 17.4% | +16.5% / +18.1% | +0.6% / -4.3% |
| 99.5% / 99% | 10 | 0.80 | 115 | Sept. | 1.225 | 98.84% -> 98.84% | 0.32 pt | 14.3% | +13.1% / +14.2% | -0.1% / -2.4% |
| 99.5% / 99% | 10 | 0.90 | 172 | C | 1.26 | 99.17% -> 98.84% | 0.30 pt | 16.4% | +16.6% / +17.6% | -0.2% / -2.8% |
| 99.5% / 99% | 10 | 0.90 | 172 | Sept. | 1.3 | 99.17% -> 98.84% | 0.18 pt | 10.4% | +9.9% / +10.2% | -0.1% / -0.3% |
| 99.5% / 99% | 10 | 0.95 | 3118 | C | 1.65 | 99.17% -> 99.17% | 0.00 pt | 11.6% | +13.3% / +13.4% | -0.9% / -0.7% |
| 99.5% / 99% | 100 | 0.80 | 159 | C | 1.03 | 98.50% -> 98.50% | 0.36 pt | 6.7% | +4.1% / +6.8% | +0.8% / -4.8% |
| 99.5% / 99% | 100 | 0.90 | 381 | C | 1.08 | 100.00% -> 100.00% | 0.29 pt | 19.2% | +22.7% / +26.5% | -0.3% / -4.4% |
| 99.5% / 99% | 100 | 0.90 | 381 | Sept. | 1.08 | 100.00% -> 100.00% | 0.29 pt | 19.2% | +23.2% / +26.6% | -0.1% / -4.0% |
| 99.5% / 99% | 100 | 0.95 | 814 | C | 1.1 | 99.67% -> 99.50% | 0.36 pt | 42.3% | +73.3% / +89.2% | -1.1% / -4.9% |
| 99.5% / 99% | 100 | 0.95 | 814 | Sept. | 1.15 | 99.67% -> 99.67% | 0.04 pt | 15.0% | +17.9% / +19.5% | -0.9% / -0.8% |

