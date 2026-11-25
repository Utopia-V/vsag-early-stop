# Wiki-all 1M 768 (l2, the metric of the cuVS bench dataset config)

Base 1000000 x 768, metric l2; queries: 10000 in the source, 10000 unique, 5000 calibration / 5000 held-out.

## Coverage protocol, fixed ef calibrated at 99.5%, check-set gate 99%, rule C+m

| dataset | calibration / check | k | R | fixed ef | alpha (rule C) | coverage fixed -> ES | mean recall loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out | >=10% QPS both |
|---|---|---:|---:|---:|---|---|---:|---:|---|---|---|---|
| wiki-all | 99.5% / 99% | 10 | 0.80 | 328 | 1.25 (1.2) | 99.56% -> 99.56% | 0.05 pt | 18.2% |  /  |  /  | pass | no |
| wiki-all | 99.5% / 99% | 10 | 0.90 | 492 | 1.3 (1.24) | 99.32% -> 99.32% | 0.02 pt | 16.5% |  /  |  /  | pass | no |
| wiki-all | 99.5% / 99% | 10 | 0.95 | 5132 | 1.85 (1.65) | 99.50% -> 99.50% | 0.00 pt | 4.0% |  /  |  /  | pass | no |
| wiki-all | 99.5% / 99% | 100 | 0.80 | 306 | 1.09 (1.07) | 99.60% -> 99.60% | 0.05 pt | 4.3% |  /  |  /  | pass | no |
| wiki-all | 99.5% / 99% | 100 | 0.90 | 496 | 1.14 (1.11) | 99.38% -> 99.38% | 0.01 pt | 4.4% |  /  |  /  | pass | no |
| wiki-all | 99.5% / 99% | 100 | 0.95 | 995 | 1.18 (1.14) | 99.26% -> 99.26% | 0.01 pt | 10.8% |  /  |  /  | pass | no |

### Calibrated at 99.5% (check-set gate 99%), by alpha rule (rule C, C+m with m = 0.10, C+m with m = 0.25)

| calibration / check | k | R | fixed ef | rule | alpha | coverage fixed -> ES | added failures | mean recall loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out |
|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|---|
| 99.5% / 99% | 10 | 0.80 | 328 | C | 1.2 | 99.56% -> 99.54% | 1 | 0.22 pt | 33.7% | +45.2% / +52.4% | -0.9% / -3.0% | pass |
| 99.5% / 99% | 10 | 0.80 | 328 | C+m 0.10 | 1.22 | 99.56% -> 99.56% | 0 | 0.13 pt | 26.4% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.80 | 328 | C+m 0.25 | 1.25 | 99.56% -> 99.56% | 0 | 0.05 pt | 18.2% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.90 | 492 | C | 1.24 | 99.32% -> 99.24% | 4 | 0.10 pt | 31.5% | +41.6% / +47.8% | +0.0% / -2.8% | pass |
| 99.5% / 99% | 10 | 0.90 | 492 | C+m 0.10 | 1.27 | 99.32% -> 99.26% | 3 | 0.05 pt | 22.9% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.90 | 492 | C+m 0.25 | 1.3 | 99.32% -> 99.32% | 0 | 0.02 pt | 16.5% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.95 | 5132 | C | 1.65 | 99.50% -> 99.50% | 0 | 0.00 pt | 12.1% | +11.6% / +14.2% | +1.3% / -0.8% | pass |
| 99.5% / 99% | 10 | 0.95 | 5132 | C+m 0.10 | 1.75 | 99.50% -> 99.50% | 0 | 0.00 pt | 7.0% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.95 | 5132 | C+m 0.25 | 1.85 | 99.50% -> 99.50% | 0 | 0.00 pt | 4.0% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.80 | 306 | C | 1.07 | 99.60% -> 99.58% | 1 | 0.25 pt | 11.4% | +9.1% / +13.3% | +1.4% / -1.4% | pass |
| 99.5% / 99% | 100 | 0.80 | 306 | C+m 0.10 | 1.08 | 99.60% -> 99.58% | 1 | 0.12 pt | 7.1% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.80 | 306 | C+m 0.25 | 1.09 | 99.60% -> 99.60% | 0 | 0.05 pt | 4.3% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.90 | 496 | C | 1.11 | 99.38% -> 99.38% | 0 | 0.08 pt | 11.8% | +10.5% / +13.8% | +1.4% / -1.1% | pass |
| 99.5% / 99% | 100 | 0.90 | 496 | C+m 0.10 | 1.13 | 99.38% -> 99.38% | 0 | 0.02 pt | 6.1% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.90 | 496 | C+m 0.25 | 1.14 | 99.38% -> 99.38% | 0 | 0.01 pt | 4.4% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.95 | 995 | C | 1.14 | 99.26% -> 99.26% | 0 | 0.07 pt | 24.6% | +28.0% / +33.3% | +0.5% / -1.7% | pass |
| 99.5% / 99% | 100 | 0.95 | 995 | C+m 0.10 | 1.16 | 99.26% -> 99.26% | 0 | 0.03 pt | 16.5% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.95 | 995 | C+m 0.25 | 1.18 | 99.26% -> 99.26% | 0 | 0.01 pt | 10.8% |  /  |  /  | pass |

| calibration / check | rule | points evaluated | pass | pass with >=10% QPS at 1t and 8t | failing points (queries short of the gate) |
|---|---|---:|---:|---:|---|
| 99.5% / 99% | C | 6 | 6 | 5 | - |
| 99.5% / 99% | C+m 0.10 | 6 | 6 | 0 | - |
| 99.5% / 99% | C+m 0.25 | 6 | 6 | 0 | - |

Points not evaluated: none.

### Default alpha (early_stop without alpha: 1.5 at k = 10, 1.15 at k = 100), calibrated at 99.5% (check-set gate 99%)

| calibration / check | k | R | fixed ef | alpha | coverage fixed -> default | mean recall loss | dist. comp. saved | held-out | QPS 1t / 8t | P99 1t / 8t |
|---|---:|---:|---:|---:|---|---:|---:|---|---|---|
| 99.5% / 99% | 10 | 0.80 | 328 | 1.5 | 99.56% -> 99.56% | 0.00 pt | 1.2% | pass |  /  |  /  |
| 99.5% / 99% | 10 | 0.90 | 492 | 1.5 | 99.32% -> 99.32% | 0.00 pt | 2.2% | pass |  /  |  /  |
| 99.5% / 99% | 10 | 0.95 | 5132 | 1.5 | 99.50% -> 99.48% | 0.00 pt | 29.5% | pass |  /  |  /  |
| 99.5% / 99% | 100 | 0.80 | 306 | 1.15 | 99.60% -> 99.60% | 0.00 pt | 0.3% | pass |  /  |  /  |
| 99.5% / 99% | 100 | 0.90 | 496 | 1.15 | 99.38% -> 99.38% | 0.01 pt | 3.2% | pass |  /  |  /  |
| 99.5% / 99% | 100 | 0.95 | 995 | 1.15 | 99.26% -> 99.26% | 0.04 pt | 20.2% | pass |  /  |  /  |

### Diagnostics on the calibration queries at the fixed ef, calibrated at 99.5%

| calibration / check | k | R | ef / k | fixed mean dist. comp. | queries with final recall at alpha 1.00 | work at alpha 1.00 / fixed | per-query work to final recall / fixed: median (q25-q75) |
|---|---:|---:|---:|---:|---:|---:|---|
| 99.5% / 99% | 10 | 0.80 | 32.80 | 4830 | 10.7% | 0.08 | 0.20 (0.13-0.33) |
| 99.5% / 99% | 10 | 0.90 | 49.20 | 6700 | 10.5% | 0.06 | 0.15 (0.09-0.25) |
| 99.5% / 99% | 10 | 0.95 | 513.20 | 43835 | 10.4% | 0.01 | 0.02 (0.01-0.04) |
| 99.5% / 99% | 100 | 0.80 | 3.06 | 4568 | 5.2% | 0.41 | 0.84 (0.67-0.97) |
| 99.5% / 99% | 100 | 0.90 | 4.96 | 6744 | 4.6% | 0.28 | 0.69 (0.50-0.88) |
| 99.5% / 99% | 100 | 0.95 | 9.95 | 11825 | 4.4% | 0.16 | 0.44 (0.30-0.67) |

Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.

## Fixed ef vs per-query ideal width (held-out queries; distance computations)

gap = mean distance computations at the fixed ef / mean over queries of the distance computations at the query's smallest width in {round(k 1.1^i) <= fixed ef} U {fixed ef} that reaches R; a query that no tested width up to the fixed ef brings to R is charged the fixed ef's work. Rule C recovers = (fixed work - rule C work) / (fixed work - ideal work), shown only where rule C passes its check (loss <= 0.5 pt and early stop reaching R on >= ceil(L n) held-out queries, L = 0.99 at the 99.5% level, else the calibration level).

| k | R | calibration level | fixed ef | gap (distance computations) | rule C alpha | rule C recovers | no tested width up to the fixed ef reaches R | per-query ideal width: median / p90 / p99 |
|---:|---:|---|---:|---:|---:|---:|---:|---|
| 10 | 0.80 | 99.5% | 328 | 6.49 | 1.2 | 40% | 22 of 5000 | 12 / 51 / 211 |
| 10 | 0.80 | 99% | 214 | 4.68 | 1.19 | 31% | 44 of 5000 | 12 / 51 / 211 |
| 10 | 0.80 | 95% | 71 | 2.14 | 1.15 | 15% | 241 of 5000 | 12 / 51 / 71 |
| 10 | 0.80 | 90% | 47 | 1.67 | 1.12 | check fails | 496 of 5000 | 12 / 47 / 47 |
| 10 | 0.90 | 99.5% | 492 | 6.95 | 1.24 | 37% | 34 of 5000 | 19 / 81 / 340 |
| 10 | 0.90 | 99% | 339 | 5.23 | 1.24 | check fails | 49 of 5000 | 19 / 81 / 339 |
| 10 | 0.90 | 95% | 119 | 2.47 | 1.2 | 14% | 244 of 5000 | 19 / 81 / 119 |
| 10 | 0.90 | 90% | 73 | 1.83 | 1.16 | check fails | 529 of 5000 | 19 / 73 / 73 |
| 10 | 0.95 | 99.5% | 5132 | 22.88 | 1.65 | 13% | 25 of 5000 | 38 / 192 / 1719 |
| 10 | 0.95 | 99% | 1943 | 11.43 | 1.5 | 14% | 43 of 5000 | 38 / 192 / 1719 |
| 10 | 0.95 | 95% | 327 | 3.26 | 1.42 | check fails | 250 of 5000 | 38 / 192 / 327 |
| 10 | 0.95 | 90% | 189 | 2.32 | 1.34 | 4% | 477 of 5000 | 38 / 189 / 189 |
| 100 | 0.80 | 99.5% | 306 | 2.32 | 1.07 | 20% | 20 of 5000 | 100 / 100 / 236 |
| 100 | 0.80 | 99% | 231 | 1.86 | 1.05 | 22% | 44 of 5000 | 100 / 100 / 231 |
| 100 | 0.80 | 95% | 126 | 1.17 | 1.02 | 6% | 239 of 5000 | 100 / 100 / 126 |
| 100 | 0.80 | 90% | 100 | 1.00 | - | - | 463 of 5000 | 100 / 100 / 100 |
| 100 | 0.90 | 99.5% | 496 | 2.92 | 1.11 | 18% | 31 of 5000 | 100 / 195 / 418 |
| 100 | 0.90 | 99% | 409 | 2.51 | 1.09 | check fails | 53 of 5000 | 100 / 195 / 409 |
| 100 | 0.90 | 95% | 230 | 1.63 | 1.06 | check fails | 259 of 5000 | 100 / 195 / 230 |
| 100 | 0.90 | 90% | 177 | 1.37 | 1.07 | check fails | 503 of 5000 | 100 / 177 / 177 |
| 100 | 0.95 | 99.5% | 995 | 3.93 | 1.14 | 33% | 37 of 5000 | 121 / 314 / 814 |
| 100 | 0.95 | 99% | 739 | 3.12 | 1.12 | check fails | 59 of 5000 | 121 / 314 / 739 |
| 100 | 0.95 | 95% | 392 | 1.95 | 1.1 | check fails | 251 of 5000 | 121 / 314 / 392 |
| 100 | 0.95 | 90% | 296 | 1.61 | 1.09 | 10% | 478 of 5000 | 121 / 296 / 296 |

