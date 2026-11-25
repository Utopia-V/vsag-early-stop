# GloVe-100 (cosine)

Base 1183514 x 100, metric cosine; queries: 10000 in the source, 10000 unique, 5000 calibration / 5000 held-out.

## Coverage protocol, fixed ef calibrated at 99.5%, check-set gate 99%, rule C+m

| dataset | calibration / check | k | R | fixed ef | alpha (rule C) | coverage fixed -> ES | mean recall loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out | >=10% QPS both |
|---|---|---:|---:|---:|---|---|---:|---:|---|---|---|---|
| glove | 99.5% / 99% | 10 | 0.80 | 2644 | 1.36 (1.28) | 99.46% -> 99.46% | 0.01 pt | 31.1% |  /  |  /  | pass | no |
| glove | 99.5% / 99% | 10 | 0.90 | 5762 | 1.44 (1.34) | 99.66% -> 99.66% | 0.00 pt | 30.3% |  /  |  /  | pass | no |
| glove | 99.5% / 99% | 100 | 0.80 | 2589 | 1.2 (1.16) | 99.22% -> 99.22% | 0.05 pt | 20.7% |  /  |  /  | pass | no |
| glove | 99.5% / 99% | 100 | 0.90 | 5238 | 1.24 (1.19) | 99.30% -> 99.30% | 0.03 pt | 25.4% |  /  |  /  | pass | no |

### Calibrated at 99.5% (check-set gate 99%), by alpha rule (rule C, C+m with m = 0.10, C+m with m = 0.25)

| calibration / check | k | R | fixed ef | rule | alpha | coverage fixed -> ES | added failures | mean recall loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out |
|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|---|
| 99.5% / 99% | 10 | 0.80 | 2644 | C | 1.28 | 99.46% -> 99.46% | 0 | 0.17 pt | 50.7% | +90.2% / +95.9% | +1.0% / -1.0% | pass |
| 99.5% / 99% | 10 | 0.80 | 2644 | C+m 0.10 | 1.31875 | 99.46% -> 99.46% | 0 | 0.05 pt | 39.5% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.80 | 2644 | C+m 0.25 | 1.36 | 99.46% -> 99.46% | 0 | 0.01 pt | 31.1% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.90 | 5762 | C | 1.34 | 99.66% -> 99.66% | 0 | 0.04 pt | 48.8% | +86.9% / +89.7% | +0.7% / -0.1% | pass |
| 99.5% / 99% | 10 | 0.90 | 5762 | C+m 0.10 | 1.38 | 99.66% -> 99.66% | 0 | 0.02 pt | 40.0% |  /  |  /  | pass |
| 99.5% / 99% | 10 | 0.90 | 5762 | C+m 0.25 | 1.44 | 99.66% -> 99.66% | 0 | 0.00 pt | 30.3% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.80 | 2589 | C | 1.16 | 99.22% -> 99.22% | 0 | 0.45 pt | 36.4% | +48.8% / +52.3% | +1.8% / -0.1% | pass |
| 99.5% / 99% | 100 | 0.80 | 2589 | C+m 0.10 | 1.18 | 99.22% -> 99.22% | 0 | 0.14 pt | 27.1% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.80 | 2589 | C+m 0.25 | 1.2 | 99.22% -> 99.22% | 0 | 0.05 pt | 20.7% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.90 | 5238 | C | 1.19 | 99.30% -> 99.30% | 0 | 0.33 pt | 44.0% | +67.4% / +70.9% | +1.0% / -0.2% | pass |
| 99.5% / 99% | 100 | 0.90 | 5238 | C+m 0.10 | 1.21 | 99.30% -> 99.30% | 0 | 0.12 pt | 34.9% |  /  |  /  | pass |
| 99.5% / 99% | 100 | 0.90 | 5238 | C+m 0.25 | 1.24 | 99.30% -> 99.30% | 0 | 0.03 pt | 25.4% |  /  |  /  | pass |

| calibration / check | rule | points evaluated | pass | pass with >=10% QPS at 1t and 8t | failing points (queries short of the gate) |
|---|---|---:|---:|---:|---|
| 99.5% / 99% | C | 4 | 4 | 4 | - |
| 99.5% / 99% | C+m 0.10 | 4 | 4 | 0 | - |
| 99.5% / 99% | C+m 0.25 | 4 | 4 | 0 | - |

Points not evaluated: k10 R0.95 (fixed search reaches R on 4898 of 5000 calibration queries at ef 8192; calibrating at 99.5% needs 4975), k100 R0.95 (fixed search reaches R on 4950 of 5000 calibration queries at ef 8192; calibrating at 99.5% needs 4975).

### Default alpha (early_stop without alpha: 1.5 at k = 10, 1.15 at k = 100), calibrated at 99.5% (check-set gate 99%)

| calibration / check | k | R | fixed ef | alpha | coverage fixed -> default | mean recall loss | dist. comp. saved | held-out | QPS 1t / 8t | P99 1t / 8t |
|---|---:|---:|---:|---:|---|---:|---:|---|---|---|
| 99.5% / 99% | 10 | 0.80 | 2644 | 1.5 | 99.46% -> 99.46% | 0.00 pt | 15.8% | pass |  /  |  /  |
| 99.5% / 99% | 10 | 0.90 | 5762 | 1.5 | 99.66% -> 99.66% | 0.00 pt | 23.6% | pass |  /  |  /  |
| 99.5% / 99% | 100 | 0.80 | 2589 | 1.15 | 99.22% -> 99.22% | 0.83 pt | 42.6% | early_stop_fails |  /  |  /  |
| 99.5% / 99% | 100 | 0.90 | 5238 | 1.15 | 99.30% -> 91.40% | 2.23 pt | 68.1% | early_stop_fails |  /  |  /  |

### Diagnostics on the calibration queries at the fixed ef, calibrated at 99.5%

| calibration / check | k | R | ef / k | fixed mean dist. comp. | queries with final recall at alpha 1.00 | work at alpha 1.00 / fixed | per-query work to final recall / fixed: median (q25-q75) |
|---|---:|---:|---:|---:|---:|---:|---|
| 99.5% / 99% | 10 | 0.80 | 264.40 | 45123 | 10.3% | 0.01 | 0.06 (0.02-0.24) |
| 99.5% / 99% | 10 | 0.90 | 576.20 | 88060 | 10.3% | 0.01 | 0.03 (0.01-0.14) |
| 99.5% / 99% | 100 | 0.80 | 25.89 | 44307 | 4.6% | 0.06 | 0.63 (0.20-0.95) |
| 99.5% / 99% | 100 | 0.90 | 52.38 | 81220 | 4.6% | 0.03 | 0.43 (0.11-0.87) |

Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.

