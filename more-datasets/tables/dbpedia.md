# DBpedia-OpenAI 975k (cosine), original index

Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.

## Fixed ef vs per-query ideal width (held-out queries; distance computations)

gap = mean distance computations at the fixed ef / mean over queries of the distance computations at the query's smallest width in {round(k 1.1^i) <= fixed ef} U {fixed ef} that reaches R; a query that no tested width up to the fixed ef brings to R is charged the fixed ef's work. Rule C recovers = (fixed work - rule C work) / (fixed work - ideal work), shown only where rule C passes its check (loss <= 0.5 pt and early stop reaching R on >= ceil(L n) held-out queries, L = 0.99 at the 99.5% level, else the calibration level).

| k | R | calibration level | fixed ef | gap (distance computations) | rule C alpha | rule C recovers | no tested width up to the fixed ef reaches R | per-query ideal width: median / p90 / p99 |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 10 | 0.80 | 99.5% | 153 | 4.48 | 1.22 | 18% | 17 of 1815 | 10 / 35 / 142 |
| 10 | 0.80 | 99% | 101 | 3.27 | 1.22 | check fails | 28 of 1815 | 10 / 35 / 101 |
| 10 | 0.80 | 97.5% | 72 | 2.55 | 1.22 | check fails | 46 of 1815 | 10 / 35 / 72 |
| 10 | 0.80 | 95% | 51 | 2.02 | 1.22 | 5% | 87 of 1815 | 10 / 35 / 51 |
| 10 | 0.80 | 90% | 34 | 1.59 | 1.1 | check fails | 181 of 1815 | 10 / 34 / 34 |
| 10 | 0.90 | 99.5% | 291 | 5.82 | 1.31875 | check fails | 20 of 1815 | 12 / 56 / 291 |
| 10 | 0.90 | 99% | 214 | 4.62 | 1.31875 | check fails | 26 of 1815 | 12 / 56 / 214 |
| 10 | 0.90 | 97.5% | 127 | 3.18 | 1.25 | check fails | 58 of 1815 | 12 / 56 / 127 |
| 10 | 0.90 | 95% | 83 | 2.38 | 1.22 | check fails | 109 of 1815 | 12 / 56 / 83 |
| 10 | 0.90 | 90% | 52 | 1.79 | 1.14 | check fails | 186 of 1815 | 12 / 52 / 52 |
| 10 | 0.95 | 99.5% | 1719 | 12.54 | 1.42 | 23% | 15 of 1815 | 24 / 144 / 1291 |
| 10 | 0.95 | 99% | 1095 | 9.11 | 1.38 | check fails | 23 of 1815 | 24 / 144 / 1095 |
| 10 | 0.95 | 97.5% | 394 | 4.56 | 1.38 | check fails | 63 of 1815 | 24 / 144 / 394 |
| 10 | 0.95 | 95% | 236 | 3.30 | 1.38 | check fails | 109 of 1815 | 24 / 144 / 236 |
| 10 | 0.95 | 90% | 130 | 2.31 | 1.31875 | check fails | 184 of 1815 | 24 / 130 / 130 |
| 100 | 0.80 | 99.5% | 214 | 1.81 | 1.04 | 25% | 8 of 1815 | 100 / 100 / 195 |
| 100 | 0.80 | 99% | 173 | 1.53 | 1.03 | check fails | 21 of 1815 | 100 / 100 / 173 |
| 100 | 0.80 | 97.5% | 137 | 1.27 | 1.02 | 14% | 40 of 1815 | 100 / 100 / 137 |
| 100 | 0.80 | 95% | 108 | 1.06 | - | - | 81 of 1815 | 100 / 100 / 108 |
| 100 | 0.80 | 90% | 100 | 1.00 | - | - | 105 of 1815 | 100 / 100 / 100 |
| 100 | 0.90 | 99.5% | 331 | 2.30 | 1.06 | 32% | 17 of 1815 | 100 / 161 / 329 |
| 100 | 0.90 | 99% | 296 | 2.10 | 1.06 | check fails | 23 of 1815 | 100 / 161 / 296 |
| 100 | 0.90 | 97.5% | 261 | 1.91 | 1.05 | 29% | 40 of 1815 | 100 / 161 / 261 |
| 100 | 0.90 | 95% | 202 | 1.57 | 1.04 | 22% | 85 of 1815 | 100 / 161 / 202 |
| 100 | 0.90 | 90% | 151 | 1.29 | 1.03 | 10% | 178 of 1815 | 100 / 151 / 151 |
| 100 | 0.95 | 99.5% | 675 | 3.28 | 1.08 | check fails | 13 of 1815 | 100 / 259 / 612 |
| 100 | 0.95 | 99% | 596 | 2.98 | 1.08 | check fails | 19 of 1815 | 100 / 259 / 596 |
| 100 | 0.95 | 97.5% | 408 | 2.23 | 1.08 | check fails | 47 of 1815 | 100 / 259 / 408 |
| 100 | 0.95 | 95% | 328 | 1.90 | 1.07 | check fails | 91 of 1815 | 100 / 259 / 328 |
| 100 | 0.95 | 90% | 248 | 1.58 | 1.06 | 17% | 172 of 1815 | 100 / 248 / 248 |

## First measurement, fixed ef calibrated at 99.5% (check-set gate 99%): rule C alphas (no margin) and the September-freeze alphas, timed now

Held-out quality from repro-package results/quality/summary-v4.json (not rerun); timing: current PR build against current main at the same fixed ef.

| calibration / check | k | R | fixed ef | rule | alpha | held-out coverage fixed -> ES | loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t |
|---|---:|---:|---:|---|---:|---|---:|---:|---|---|
| 99.5% / 99% | 10 | 0.80 | 153 | C | 1.22 | 99.06% -> 99.01% | 0.06 pt | 14.2% | +14.3% / +17.0% | +1.1% / -0.5% |
| 99.5% / 99% | 10 | 0.80 | 153 | Sept. | 1.225 | 99.06% -> 99.01% | 0.06 pt | 13.3% | +13.1% / +15.8% | +1.3% / -0.6% |
| 99.5% / 99% | 10 | 0.90 | 291 | C | 1.31875 | 98.90% -> 98.84% | 0.02 pt | 10.1% | +10.6% / +11.4% | +0.3% / -0.3% |
| 99.5% / 99% | 10 | 0.95 | 1719 | C | 1.42 | 99.17% -> 99.01% | 0.02 pt | 21.2% | +25.2% / +26.9% | +0.5% / -0.8% |
| 99.5% / 99% | 10 | 0.95 | 1719 | Sept. | 1.5 | 99.17% -> 99.12% | 0.01 pt | 12.8% | +13.5% / +14.7% | +0.8% / -0.4% |
| 99.5% / 99% | 100 | 0.80 | 214 | C | 1.04 | 99.56% -> 99.50% | 0.30 pt | 11.0% | +9.9% / +12.6% | +1.4% / -0.7% |
| 99.5% / 99% | 100 | 0.80 | 214 | Sept. | 1.04 | 99.56% -> 99.50% | 0.30 pt | 11.0% | +9.8% / +12.7% | +1.4% / -0.5% |
| 99.5% / 99% | 100 | 0.90 | 331 | C | 1.06 | 99.06% -> 99.01% | 0.26 pt | 18.0% | +21.0% / +22.4% | +0.3% / -0.5% |
| 99.5% / 99% | 100 | 0.90 | 331 | Sept. | 1.06 | 99.06% -> 99.01% | 0.26 pt | 18.0% | +21.0% / +22.3% | +0.5% / -0.7% |
| 99.5% / 99% | 100 | 0.95 | 675 | C | 1.08 | 99.28% -> 98.90% | 0.32 pt | 37.6% | +57.3% / +60.3% | -1.0% / -1.9% |
| 99.5% / 99% | 100 | 0.95 | 675 | Sept. | 1.12 | 99.28% -> 99.23% | 0.02 pt | 13.7% | +14.6% / +16.0% | +1.0% / -0.1% |

