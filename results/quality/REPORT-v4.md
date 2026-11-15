# Alpha recalibration with a loss margin (rule C, amended to rule C+m), 2026-10-22

Library for all quality runs: v4 (v3 = f83e1910 Release, the build behind the v3 numbers). Same 18 FP32 points, calibration queries (DBpedia 1270, Cohere 398, LAION 395) and held-out queries (DBpedia 1815, Cohere 601, LAION 53) as before. Fixed ef per point and tier is reused from the earlier calibrations (fixed-points.json).

**How often the held-out queries have been looked at.** They were used once before this campaign, to evaluate the earlier alpha choices. This campaign looked at them (and at the DBpedia fresh queries) once for rules C, B, old and default, and a second time for rule C+m, so they have now been looked at twice here and three times overall. None of these checks is untouched validation.

Rule C: on the calibration queries, the alpha with the fewest distance computations such that it and every larger grid alpha keep coverage >= C_cal = (1+C)/2 and keep the mean recall loss plus two standard errors within 0.5 points; fixed where ef <= 1.25 k. Rule B drops the two-standard-error margin. "Old" is the alpha the earlier campaign recorded (September freeze for C=0.99, 2026-10-13 run for C=0.90/0.95). Default: 1.5 at k=10, 1.15 at k=100. A held-out configuration passes when fixed reaches C and early stop reaches C with mean loss <= 0.5 points. Savings are mean distance computations vs fixed ef on the held-out queries.

**Amendment (2026-10-22, protocol.json "amendments").** The first held-out run showed that at C=0.99 the coverage side had no margin: on the calibration queries the fixed ef sits exactly at C_cal, so rule C picks the smallest alpha that happened to add zero calibration failures (DBpedia k100-r95 then added 7 held-out failures against a slack of 5). Rule C+m takes the rule C alpha and uses the smallest grid alpha >= 1 + (alpha_C - 1)(1 + m), with m = 0.05 at C=0.90/0.95 and m = 0.25 at C=0.99; points fixed or auto-off under rule C stay so. m was chosen by cross-validation on the calibration queries only (source/cv_margin.py: 300 random 2/3 vs 1/3 splits per point, rule C on the 2/3, margin applied, checked on the other third; the smallest m with mean failure probability <= 2.5% per tier: C=0.90 3.9% -> 0.8%, C=0.95 4.0% -> 0.8%, C=0.99 12.1% -> 2.1% at m=0.25), before the second look at the held-out sets, and was not changed after it.

## C = 0.90 (calibrated at 0.95)

### Rule C+m (m = 0.05)

| point | ef | C+m alpha (rule C) | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | held-out loss | pass | rule C saving | old saving |
|---|---:|---:|---:|---|---|---:|---|---|---|
| dbpedia k10-r80 | 51 | 1.24 (1.22) | 1.8% | 0.00 / 0.00 pt | 95.21% -> 95.15% | 0.02 pt | yes | 1.22: 2.3% | 1.225: 2.2% |
| dbpedia k10-r90 | 83 | 1.24 (1.22) | 4.5% | 0.02 / 0.04 pt | 93.99% -> 93.88% | 0.04 pt | yes | 1.22: 5.7% | 1.225: 5.4% |
| dbpedia k10-r95 | 236 | 1.4 (1.38) | 4.1% | 0.00 / 0.00 pt | 93.99% -> 93.88% | 0.01 pt | yes | 1.38: 4.8% | 1.5: 2.3% |
| dbpedia k100-r80 | 108 | - |  |  | 95.54% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1.02: 0.0% |
| dbpedia k100-r90 | 202 | 1.05 (1.04) | 3.8% | 0.06 / 0.08 pt | 95.32% -> 95.32% | 0.06 pt | yes | 1.04: 8.1% | 1.04: 8.1% |
| dbpedia k100-r95 | 328 | 1.08 (1.07) | 7.2% | 0.04 / 0.05 pt | 94.93% -> 94.93% | 0.04 pt | yes | 1.07: 11.2% | 1.08: 7.2% |
| cohere k10-r80 | 44 | 1.15 (1.14) | 7.6% | 0.18 / 0.31 pt | 95.51% -> 95.17% | 0.33 pt | yes | 1.14: 9.2% | 1.15: 7.6% |
| cohere k10-r90 | 85 | 1.24 (1.225) | 7.3% | 0.03 / 0.08 pt | 95.51% -> 95.17% | 0.20 pt | yes | 1.225: 8.8% | 1.225: 8.8% |
| cohere k10-r95 | 189 | 1.38 (1.36) | 5.6% | 0.00 / 0.00 pt | 93.68% -> 92.85% | 0.10 pt | yes | 1.36: 6.6% | 1.5: 2.0% |
| cohere k100-r80 | 100 | - |  |  | 93.18% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 2: 0.0% |
| cohere k100-r90 | 216 | 1.06 (1.05) | 4.9% | 0.11 / 0.14 pt | 95.17% -> 95.17% | 0.11 pt | yes | 1.05: 9.9% | 1.06: 4.9% |
| cohere k100-r95 | 338 | 1.09 (1.08) | 8.7% | 0.09 / 0.12 pt | 93.34% -> 93.34% | 0.09 pt | yes | 1.08: 13.5% | 1.08: 13.5% |
| laion k10-r80 | 39 | 1.13 (1.12) | 9.2% | 0.10 / 0.26 pt | 96.23% -> 96.23% | 0.00 pt | yes | 1.12: 12.1% | 1.12: 12.1% |
| laion k10-r90 | 75 | 1.18 (1.17) | 16.8% | 0.08 / 0.16 pt | 94.34% -> 94.34% | 0.19 pt | yes | 1.17: 18.6% | 1.2: 13.3% |
| laion k10-r95 | 146 | 1.3 (1.28) | 13.7% | 0.00 / 0.00 pt | 94.34% -> 94.34% | 0.00 pt | yes | 1.28: 16.3% | 1.3: 13.7% |
| laion k100-r80 | 100 | - |  |  | 92.45% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1: 0.0% |
| laion k100-r90 | 157 | 1.04 (1.03) | 5.5% | 0.07 / 0.10 pt | 94.34% -> 94.34% | 0.06 pt | yes | 1.03: 9.0% | 1.04: 5.5% |
| laion k100-r95 | 247 | 1.07 (1.06) | 12.3% | 0.07 / 0.10 pt | 98.11% -> 98.11% | 0.04 pt | yes | 1.06: 15.7% | 1.06: 15.7% |

| arm | points passing | of which with early stop | early stop fails | fixed fails |
|---|---:|---:|---:|---:|
| rule c | 18 of 18 | 15 | 0 | 0 |
| rule cm | 18 of 18 | 15 | 0 | 0 |
| rule b | 17 of 18 | 14 | 1 | 0 |
| old | 18 of 18 | 18 | 0 | 0 |
| default | 18 of 18 | 15 | 0 | 0 |

### Rule C (first held-out run)

| point | ef | rule C alpha | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | held-out loss | pass | rule B | old | default |
|---|---:|---:|---:|---|---|---:|---|---|---|---|
| dbpedia k10-r80 | 51 | 1.22 | 2.3% | 0.01 / 0.02 pt | 95.21% -> 95.15% | 0.03 pt | yes | 1.22: 2.3% | 1.225: 2.2% | 1.5: 0.4% |
| dbpedia k10-r90 | 83 | 1.22 | 5.7% | 0.02 / 0.05 pt | 93.99% -> 93.88% | 0.04 pt | yes | 1.22: 5.7% | 1.225: 5.4% | 1.5: 0.8% |
| dbpedia k10-r95 | 236 | 1.38 | 4.8% | 0.00 / 0.00 pt | 93.99% -> 93.88% | 0.01 pt | yes | 1.38: 4.8% | 1.5: 2.3% | 1.5: 2.3% |
| dbpedia k100-r80 | 108 | - |  |  | 95.54% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1.02: 0.0% | - |
| dbpedia k100-r90 | 202 | 1.04 | 8.1% | 0.23 / 0.26 pt | 95.32% -> 95.26% | 0.20 pt | yes | 1.04: 8.1% | 1.04: 8.1% | 1.15: 0.1% |
| dbpedia k100-r95 | 328 | 1.07 | 11.2% | 0.10 / 0.13 pt | 94.93% -> 94.77% | 0.09 pt | yes | 1.07: 11.2% | 1.08: 7.2% | 1.15: 0.7% |
| cohere k10-r80 | 44 | 1.14 | 9.2% | 0.23 / 0.38 pt | 95.51% -> 95.17% | 0.45 pt | yes | 1.13: 11.3% (fails) | 1.15: 7.6% | 1.5: 0.2% |
| cohere k10-r90 | 85 | 1.225 | 8.8% | 0.10 / 0.22 pt | 95.51% -> 95.17% | 0.23 pt | yes | 1.225: 8.8% | 1.225: 8.8% | 1.5: 0.6% |
| cohere k10-r95 | 189 | 1.36 | 6.6% | 0.00 / 0.00 pt | 93.68% -> 92.85% | 0.10 pt | yes | 1.36: 6.6% | 1.5: 2.0% | 1.5: 2.0% |
| cohere k100-r80 | 100 | - |  |  | 93.18% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 2: 0.0% | - |
| cohere k100-r90 | 216 | 1.05 | 9.9% | 0.27 / 0.33 pt | 95.17% -> 95.17% | 0.34 pt | yes | 1.05: 9.9% | 1.06: 4.9% | 1.15: 0.0% |
| cohere k100-r95 | 338 | 1.08 | 13.5% | 0.21 / 0.26 pt | 93.34% -> 92.85% | 0.19 pt | yes | 1.08: 13.5% | 1.08: 13.5% | 1.15: 0.5% |
| laion k10-r80 | 39 | 1.12 | 12.1% | 0.23 / 0.42 pt | 96.23% -> 96.23% | 0.19 pt | yes | 1.12: 12.1% | 1.12: 12.1% | 1.5: 0.2% |
| laion k10-r90 | 75 | 1.17 | 18.6% | 0.10 / 0.20 pt | 94.34% -> 94.34% | 0.38 pt | yes | 1.17: 18.6% | 1.2: 13.3% | 1.5: 0.8% |
| laion k10-r95 | 146 | 1.28 | 16.3% | 0.00 / 0.00 pt | 94.34% -> 94.34% | 0.00 pt | yes | 1.28: 16.3% | 1.3: 13.7% | 1.5: 2.7% |
| laion k100-r80 | 100 | - |  |  | 92.45% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1: 0.0% | - |
| laion k100-r90 | 157 | 1.03 | 9.0% | 0.22 / 0.27 pt | 94.34% -> 94.34% | 0.09 pt | yes | 1.03: 9.0% | 1.04: 5.5% | 1.15: 0.5% |
| laion k100-r95 | 247 | 1.06 | 15.7% | 0.16 / 0.21 pt | 98.11% -> 98.11% | 0.06 pt | yes | 1.06: 15.7% | 1.06: 15.7% | 1.15: 2.3% |

Held-out, rule C: 15 early-stop points pass, 0 fail because of early stop, 0 stay fixed (no alpha qualifies), 3 stay fixed (ef <= 1.25k), 0 fail because the fixed baseline misses C. Early-stop failures with rule B: 1; old alphas: 0; default alphas: 0.

## C = 0.95 (calibrated at 0.975)

### Rule C+m (m = 0.05)

| point | ef | C+m alpha (rule C) | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | held-out loss | pass | rule C saving | old saving |
|---|---:|---:|---:|---|---|---:|---|---|---|
| dbpedia k10-r80 | 72 | 1.24 (1.22) | 3.6% | 0.01 / 0.02 pt | 97.47% -> 97.41% | 0.04 pt | yes | 1.22: 4.5% | 1.225: 4.3% |
| dbpedia k10-r90 | 127 | 1.27 (1.25) | 6.0% | 0.02 / 0.05 pt | 96.80% -> 96.75% | 0.02 pt | yes | 1.25: 7.5% | 1.3: 4.5% |
| dbpedia k10-r95 | 394 | 1.4 (1.38) | 7.1% | 0.00 / 0.00 pt | 96.53% -> 96.42% | 0.01 pt | yes | 1.38: 8.3% | 1.5: 3.6% |
| dbpedia k100-r80 | 137 | 1.03 (1.02) | 0.7% | 0.01 / 0.02 pt | 97.80% -> 97.80% | 0.02 pt | yes | 1.02: 3.1% | 1.02: 3.1% |
| dbpedia k100-r90 | 261 | 1.06 (1.05) | 7.7% | 0.09 / 0.11 pt | 97.80% -> 97.80% | 0.10 pt | yes | 1.05: 13.6% | 1.06: 7.7% |
| dbpedia k100-r95 | 408 | 1.09 (1.08) | 9.8% | 0.04 / 0.05 pt | 97.41% -> 97.30% | 0.05 pt | yes | 1.08: 14.4% | 1.08: 14.4% |
| cohere k10-r80 | 64 | 1.18 (1.17) | 9.9% | 0.20 / 0.36 pt | 97.00% -> 96.84% | 0.33 pt | yes | 1.17: 11.7% | 1.15: 16.6% (fails) |
| cohere k10-r90 | 113 | 1.28 (1.26) | 7.2% | 0.05 / 0.12 pt | 97.17% -> 96.84% | 0.18 pt | yes | 1.26: 9.1% | 1.3: 5.8% |
| cohere k10-r95 | 531 | 1.42 (1.4) | 12.4% | 0.00 / 0.00 pt | 98.00% -> 97.34% | 0.08 pt | yes | 1.4: 14.7% | 1.5: 6.8% |
| cohere k100-r80 | 123 | - |  |  | 95.84% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1.02: 0.0% |
| cohere k100-r90 | 253 | 1.07 (1.06) | 6.5% | 0.09 / 0.13 pt | 97.00% -> 97.00% | 0.08 pt | yes | 1.06: 11.6% | 1.06: 11.6% |
| cohere k100-r95 | 448 | 1.09 (1.08) | 20.7% | 0.20 / 0.25 pt | 96.67% -> 96.67% | 0.24 pt | yes | 1.08: 27.5% | 1.08: 27.5% |
| laion k10-r80 | 60 | 1.15 (1.14) | 17.1% | 0.10 / 0.20 pt | 96.23% -> 96.23% | 0.38 pt | yes | 1.14: 19.9% | 1.15: 17.1% |
| laion k10-r90 | 156 | 1.18 (1.17) | 39.4% | 0.20 / 0.34 pt | 98.11% -> 98.11% | 0.38 pt | yes | 1.17: 42.3% (fails) | 1.2: 33.2% |
| laion k10-r95 | 265 | 1.3 (1.28) | 25.1% | 0.00 / 0.00 pt | 96.23% -> 96.23% | 0.00 pt | yes | 1.28: 28.9% | 1.3: 25.1% |
| laion k100-r80 | 114 | - |  |  | 96.23% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1.02: 0.0% |
| laion k100-r90 | 189 | 1.05 (1.04) | 8.8% | 0.09 / 0.13 pt | 96.23% -> 96.23% | 0.04 pt | yes | 1.04: 13.3% | 1.04: 13.3% |
| laion k100-r95 | 361 | 1.08 (1.07) | 23.8% | 0.15 / 0.20 pt | 98.11% -> 98.11% | 0.09 pt | yes | 1.07: 27.9% | 1.08: 23.8% |

| arm | points passing | of which with early stop | early stop fails | fixed fails |
|---|---:|---:|---:|---:|
| rule c | 17 of 18 | 15 | 1 | 0 |
| rule cm | 18 of 18 | 16 | 0 | 0 |
| rule b | 16 of 18 | 14 | 2 | 0 |
| old | 17 of 18 | 17 | 1 | 0 |
| default | 18 of 18 | 16 | 0 | 0 |

### Rule C (first held-out run)

| point | ef | rule C alpha | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | held-out loss | pass | rule B | old | default |
|---|---:|---:|---:|---|---|---:|---|---|---|---|
| dbpedia k10-r80 | 72 | 1.22 | 4.5% | 0.02 / 0.04 pt | 97.47% -> 97.41% | 0.04 pt | yes | 1.22: 4.5% | 1.225: 4.3% | 1.5: 0.7% |
| dbpedia k10-r90 | 127 | 1.25 | 7.5% | 0.02 / 0.05 pt | 96.80% -> 96.69% | 0.04 pt | yes | 1.25: 7.5% | 1.3: 4.5% | 1.5: 1.3% |
| dbpedia k10-r95 | 394 | 1.38 | 8.3% | 0.00 / 0.00 pt | 96.53% -> 96.42% | 0.01 pt | yes | 1.38: 8.3% | 1.5: 3.6% | 1.5: 3.6% |
| dbpedia k100-r80 | 137 | 1.02 | 3.1% | 0.15 / 0.18 pt | 97.80% -> 97.80% | 0.15 pt | yes | 1.02: 3.1% | 1.02: 3.1% | 1.15: 0.0% |
| dbpedia k100-r90 | 261 | 1.05 | 13.6% | 0.26 / 0.29 pt | 97.80% -> 97.80% | 0.28 pt | yes | 1.05: 13.6% | 1.06: 7.7% | 1.15: 0.3% |
| dbpedia k100-r95 | 408 | 1.08 | 14.4% | 0.08 / 0.10 pt | 97.41% -> 97.30% | 0.11 pt | yes | 1.08: 14.4% | 1.08: 14.4% | 1.15: 1.4% |
| cohere k10-r80 | 64 | 1.17 | 11.7% | 0.28 / 0.46 pt | 97.00% -> 96.67% | 0.40 pt | yes | 1.15: 16.6% (fails) | 1.15: 16.6% (fails) | 1.5: 0.4% |
| cohere k10-r90 | 113 | 1.26 | 9.1% | 0.08 / 0.16 pt | 97.17% -> 96.84% | 0.22 pt | yes | 1.26: 9.1% | 1.3: 5.8% | 1.5: 0.9% |
| cohere k10-r95 | 531 | 1.4 | 14.7% | 0.00 / 0.00 pt | 98.00% -> 97.34% | 0.08 pt | yes | 1.4: 14.7% | 1.5: 6.8% | 1.5: 6.8% |
| cohere k100-r80 | 123 | - |  |  | 95.84% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1.02: 0.0% | - |
| cohere k100-r90 | 253 | 1.06 | 11.6% | 0.24 / 0.30 pt | 97.00% -> 96.84% | 0.28 pt | yes | 1.06: 11.6% | 1.06: 11.6% | 1.15: 0.1% |
| cohere k100-r95 | 448 | 1.08 | 27.5% | 0.40 / 0.48 pt | 96.67% -> 95.84% | 0.43 pt | yes | 1.08: 27.5% | 1.08: 27.5% | 1.15: 2.1% |
| laion k10-r80 | 60 | 1.14 | 19.9% | 0.18 / 0.31 pt | 96.23% -> 96.23% | 0.38 pt | yes | 1.14: 19.9% | 1.15: 17.1% | 1.5: 0.6% |
| laion k10-r90 | 156 | 1.17 | 42.3% | 0.25 / 0.41 pt | 98.11% -> 98.11% | 0.57 pt | NO (early stop) | 1.17: 42.3% (fails) | 1.2: 33.2% | 1.5: 3.1% |
| laion k10-r95 | 265 | 1.28 | 28.9% | 0.00 / 0.00 pt | 96.23% -> 96.23% | 0.00 pt | yes | 1.28: 28.9% | 1.3: 25.1% | 1.5: 8.0% |
| laion k100-r80 | 114 | - |  |  | 96.23% (fixed only) |  | fixed (auto off (ef <= 1.25k)) | - | 1.02: 0.0% | - |
| laion k100-r90 | 189 | 1.04 | 13.3% | 0.24 / 0.29 pt | 96.23% -> 96.23% | 0.23 pt | yes | 1.04: 13.3% | 1.04: 13.3% | 1.15: 0.8% |
| laion k100-r95 | 361 | 1.07 | 27.9% | 0.22 / 0.27 pt | 98.11% -> 98.11% | 0.13 pt | yes | 1.07: 27.9% | 1.08: 23.8% | 1.15: 7.9% |

Held-out, rule C: 15 early-stop points pass, 1 fail because of early stop, 0 stay fixed (no alpha qualifies), 2 stay fixed (ef <= 1.25k), 0 fail because the fixed baseline misses C. Early-stop failures with rule B: 2; old alphas: 1; default alphas: 0.

## C = 0.99 (calibrated at 0.995)

### Rule C+m (m = 0.25)

| point | ef | C+m alpha (rule C) | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | held-out loss | pass | rule C saving | old saving |
|---|---:|---:|---:|---|---|---:|---|---|---|
| dbpedia k10-r80 | 153 | 1.28 (1.22) | 7.0% | 0.02 / 0.04 pt | 99.06% -> 99.06% | 0.02 pt | yes | 1.22: 14.2% | 1.225: 13.3% |
| dbpedia k10-r90 | 291 | 1.4 (1.31875) | 5.2% | 0.00 / 0.00 pt | 98.90% -> 98.90% | 0.01 pt | NO (fixed fails) | 1.31875: 10.1% | - |
| dbpedia k10-r95 | 1719 | 1.54 (1.42) | 10.0% | 0.00 / 0.00 pt | 99.17% -> 99.17% | 0.00 pt | yes | 1.42: 21.2% | 1.5: 12.8% |
| dbpedia k100-r80 | 214 | 1.05 (1.04) | 5.4% | 0.10 / 0.12 pt | 99.56% -> 99.56% | 0.08 pt | yes | 1.04: 11.0% | 1.04: 11.0% |
| dbpedia k100-r90 | 331 | 1.08 (1.06) | 7.4% | 0.04 / 0.05 pt | 99.06% -> 99.06% | 0.04 pt | yes | 1.06: 18.0% | 1.06: 18.0% |
| dbpedia k100-r95 | 675 | 1.1 (1.08) | 23.5% | 0.09 / 0.11 pt | 99.28% -> 99.17% | 0.08 pt | yes | 1.08: 37.6% (fails) | 1.12: 13.7% |
| cohere k10-r80 | 115 | 1.27 (1.21) | 8.3% | 0.08 / 0.16 pt | 98.84% -> 98.84% | 0.22 pt | NO (fixed fails) | 1.21: 17.4% | 1.225: 14.3% |
| cohere k10-r90 | 172 | 1.34 (1.26) | 7.1% | 0.03 / 0.08 pt | 99.17% -> 99.00% | 0.12 pt | yes | 1.26: 16.4% (fails) | 1.3: 10.4% (fails) |
| cohere k10-r95 | 3118 | 1.85 (1.65) | 3.7% | 0.00 / 0.00 pt | 99.17% -> 99.17% | 0.00 pt | yes | 1.65: 11.6% | - |
| cohere k100-r80 | 159 | 1.04 (1.03) | 2.1% | 0.10 / 0.14 pt | 98.50% -> 98.50% | 0.06 pt | NO (fixed fails) | 1.03: 6.7% | - |
| cohere k100-r90 | 381 | 1.1 (1.08) | 8.9% | 0.08 / 0.11 pt | 100.00% -> 100.00% | 0.07 pt | yes | 1.08: 19.2% | 1.08: 19.2% |
| cohere k100-r95 | 814 | 1.13 (1.1) | 24.2% | 0.12 / 0.15 pt | 99.67% -> 99.67% | 0.09 pt | yes | 1.1: 42.3% | 1.15: 15.0% |
| laion k10-r80 | 612 | 1.225 (1.18) | 61.4% | 0.08 / 0.16 pt | 100.00% -> 100.00% | 0.00 pt | yes | 1.18: 73.7% (fails) | 1.5: 19.4% |
| laion k10-r90 | 684 | 1.27 (1.21) | 54.6% | 0.03 / 0.08 pt | 100.00% -> 100.00% | 0.00 pt | yes | 1.21: 67.3% | 1.5: 20.9% |
| laion k10-r95 | 5999 | 1.38 (1.3) | 73.1% | 0.00 / 0.00 pt | 100.00% -> 100.00% | 0.00 pt | yes | 1.3: 86.0% | 2: 25.5% |
| laion k100-r80 | 500 | 1.09 (1.07) | 32.5% | 0.15 / 0.19 pt | 100.00% -> 100.00% | 0.06 pt | yes | 1.07: 41.8% | 1.15: 14.5% |
| laion k100-r90 | 676 | 1.1 (1.08) | 39.5% | 0.12 / 0.16 pt | 100.00% -> 100.00% | 0.04 pt | yes | 1.08: 49.2% | 1.15: 22.8% |
| laion k100-r95 | 2283 | 1.15 (1.12) | 60.0% | 0.03 / 0.05 pt | 100.00% -> 100.00% | 0.04 pt | yes | 1.12: 70.2% | 1.31875: 23.0% |

| arm | points passing | of which with early stop | early stop fails | fixed fails |
|---|---:|---:|---:|---:|
| rule c | 12 of 18 | 12 | 3 | 3 |
| rule cm | 15 of 18 | 15 | 0 | 3 |
| rule b | 12 of 18 | 12 | 3 | 3 |
| old | 14 of 18 | 13 | 1 | 3 |
| default | 14 of 18 | 14 | 1 | 3 |

### Rule C (first held-out run)

| point | ef | rule C alpha | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | held-out loss | pass | rule B | old | default |
|---|---:|---:|---:|---|---|---:|---|---|---|---|
| dbpedia k10-r80 | 153 | 1.22 | 14.2% | 0.06 / 0.11 pt | 99.06% -> 99.01% | 0.06 pt | yes | 1.22: 14.2% | 1.225: 13.3% | 1.5: 1.6% |
| dbpedia k10-r90 | 291 | 1.31875 | 10.1% | 0.01 / 0.02 pt | 98.90% -> 98.84% | 0.02 pt | NO (fixed fails) | 1.31875: 10.1% | - | 1.5: 2.8% |
| dbpedia k10-r95 | 1719 | 1.42 | 21.2% | 0.00 / 0.00 pt | 99.17% -> 99.01% | 0.02 pt | yes | 1.42: 21.2% | 1.5: 12.8% | 1.5: 12.8% |
| dbpedia k100-r80 | 214 | 1.04 | 11.0% | 0.33 / 0.37 pt | 99.56% -> 99.50% | 0.30 pt | yes | 1.04: 11.0% | 1.04: 11.0% | 1.15: 0.1% |
| dbpedia k100-r90 | 331 | 1.06 | 18.0% | 0.26 / 0.29 pt | 99.06% -> 99.01% | 0.26 pt | yes | 1.06: 18.0% | 1.06: 18.0% | 1.15: 0.7% |
| dbpedia k100-r95 | 675 | 1.08 | 37.6% | 0.29 / 0.32 pt | 99.28% -> 98.90% | 0.32 pt | NO (early stop) | 1.08: 37.6% (fails) | 1.12: 13.7% | 1.15: 6.2% |
| cohere k10-r80 | 115 | 1.21 | 17.4% | 0.25 / 0.44 pt | 98.84% -> 98.84% | 0.38 pt | NO (fixed fails) | 1.18: 26.0% | 1.225: 14.3% | 1.5: 0.9% |
| cohere k10-r90 | 172 | 1.26 | 16.4% | 0.15 / 0.27 pt | 99.17% -> 98.84% | 0.30 pt | NO (early stop) | 1.26: 16.4% (fails) | 1.3: 10.4% (fails) | 1.5: 1.7% |
| cohere k10-r95 | 3118 | 1.65 | 11.6% | 0.00 / 0.00 pt | 99.17% -> 99.17% | 0.00 pt | yes | 1.65: 11.6% | - | 1.5: 29.4% (fails) |
| cohere k100-r80 | 159 | 1.03 | 6.7% | 0.36 / 0.44 pt | 98.50% -> 98.50% | 0.36 pt | NO (fixed fails) | 1.03: 6.7% | - | 1.15: 0.0% |
| cohere k100-r90 | 381 | 1.08 | 19.2% | 0.29 / 0.35 pt | 100.00% -> 100.00% | 0.29 pt | yes | 1.08: 19.2% | 1.08: 19.2% | 1.15: 0.9% |
| cohere k100-r95 | 814 | 1.1 | 42.3% | 0.40 / 0.47 pt | 99.67% -> 99.50% | 0.36 pt | yes | 1.1: 42.3% | 1.15: 15.0% | 1.15: 15.0% |
| laion k10-r80 | 612 | 1.18 | 73.7% | 0.25 / 0.41 pt | 100.00% -> 100.00% | 0.57 pt | NO (early stop) | 1.17: 76.2% (fails) | 1.5: 19.4% | 1.5: 19.4% |
| laion k10-r90 | 684 | 1.21 | 67.3% | 0.18 / 0.31 pt | 100.00% -> 100.00% | 0.00 pt | yes | 1.21: 67.3% | 1.5: 20.9% | 1.5: 20.9% |
| laion k10-r95 | 5999 | 1.3 | 86.0% | 0.00 / 0.00 pt | 100.00% -> 100.00% | 0.00 pt | yes | 1.3: 86.0% | 2: 25.5% | 1.5: 59.5% |
| laion k100-r80 | 500 | 1.07 | 41.8% | 0.38 / 0.45 pt | 100.00% -> 100.00% | 0.13 pt | yes | 1.07: 41.8% | 1.15: 14.5% | 1.15: 14.5% |
| laion k100-r90 | 676 | 1.08 | 49.2% | 0.33 / 0.40 pt | 100.00% -> 100.00% | 0.09 pt | yes | 1.07: 53.8% | 1.15: 22.8% | 1.15: 22.8% |
| laion k100-r95 | 2283 | 1.12 | 70.2% | 0.10 / 0.14 pt | 100.00% -> 100.00% | 0.06 pt | yes | 1.12: 70.2% | 1.31875: 23.0% | 1.15: 60.0% |

Held-out, rule C: 12 early-stop points pass, 3 fail because of early stop, 0 stay fixed (no alpha qualifies), 0 stay fixed (ef <= 1.25k), 3 fail because the fixed baseline misses C. Early-stop failures with rule B: 3; old alphas: 1; default alphas: 1.

## DBpedia, 2048 fresh queries (used once before at k100/R95; looked at twice in this campaign)

| point | ef | rule C alpha | coverage fixed -> ES | loss | saving | pass | C+m alpha: saving | default |
|---|---:|---:|---|---:|---:|---|---|---|
| c90-k10-r80 | 51 | 1.22 | 93.55% -> 93.55% | 0.01 pt | 1.9% | yes | 1.24: 1.5% (93.55%, 0.01 pt, pass) | 1.5: 0.2% |
| c90-k10-r90 | 83 | 1.22 | 93.80% -> 93.75% | 0.06 pt | 5.3% | yes | 1.24: 4.0% (93.80%, 0.02 pt, pass) | 1.5: 0.6% |
| c90-k10-r95 | 236 | 1.38 | 94.19% -> 94.09% | 0.01 pt | 4.3% | yes | 1.4: 3.7% (94.09%, 0.01 pt, pass) | 1.5: 1.8% |
| c90-k100-r80 | 108 | - | 94.48% (fixed only) | | | fixed | - | - |
| c90-k100-r90 | 202 | 1.04 | 95.12% -> 95.02% | 0.22 pt | 8.1% | yes | 1.05: 3.7% (95.12%, 0.05 pt, pass) | 1.15: 0.1% |
| c90-k100-r95 | 328 | 1.07 | 93.90% -> 93.85% | 0.12 pt | 11.1% | yes | 1.08: 6.9% (93.85%, 0.05 pt, pass) | 1.15: 0.6% |
| c95-k10-r80 | 72 | 1.22 | 96.29% -> 96.24% | 0.06 pt | 4.1% | yes | 1.24: 3.1% (96.29%, 0.02 pt, pass) | 1.5: 0.5% |
| c95-k10-r90 | 127 | 1.25 | 96.78% -> 96.78% | 0.03 pt | 7.1% | yes | 1.27: 5.5% (96.78%, 0.03 pt, pass) | 1.5: 1.0% |
| c95-k10-r95 | 394 | 1.38 | 96.88% -> 96.73% | 0.01 pt | 7.6% | yes | 1.4: 6.4% (96.73%, 0.01 pt, pass) | 1.5: 3.1% |
| c95-k100-r80 | 137 | 1.02 | 97.31% -> 97.27% | 0.13 pt | 2.9% | yes | 1.03: 0.6% (97.31%, 0.01 pt, pass) | 1.15: 0.0% |
| c95-k100-r90 | 261 | 1.05 | 97.27% -> 97.22% | 0.27 pt | 13.5% | yes | 1.06: 7.6% (97.27%, 0.10 pt, pass) | 1.15: 0.2% |
| c95-k100-r95 | 408 | 1.08 | 96.78% -> 96.73% | 0.10 pt | 14.2% | yes | 1.09: 9.6% (96.78%, 0.04 pt, pass) | 1.15: 1.2% |
| c99-k10-r80 | 153 | 1.22 | 98.93% -> 98.88% | 0.11 pt | 13.7% | fixed_fails | 1.28: 6.4% (98.93%, 0.03 pt, fixed_fails) | 1.5: 1.2% |
| c99-k10-r90 | 291 | 1.31875 | 99.17% -> 99.17% | 0.03 pt | 9.6% | yes | 1.4: 4.7% (99.17%, 0.01 pt, pass) | 1.5: 2.3% |
| c99-k10-r95 | 1719 | 1.42 | 99.61% -> 99.41% | 0.02 pt | 20.6% | yes | 1.54: 9.1% (99.56%, 0.00 pt, pass) | 1.5: 11.8% |
| c99-k100-r80 | 214 | 1.04 | 99.66% -> 99.61% | 0.30 pt | 10.9% | yes | 1.05: 5.3% (99.66%, 0.08 pt, pass) | 1.15: 0.1% |
| c99-k100-r90 | 331 | 1.06 | 98.73% -> 98.73% | 0.29 pt | 17.9% | fixed_fails | 1.08: 7.2% (98.73%, 0.05 pt, fixed_fails) | 1.15: 0.6% |
| c99-k100-r95 | 675 | 1.08 | 99.41% -> 99.17% | 0.31 pt | 37.2% | yes | 1.1: 23.2% (99.41%, 0.10 pt, pass) | 1.15: 6.0% |

## v4 against v3

- Per-query outputs (work counts, IDs, distances) of every configuration run with both libraries: 3335 files, 3258 byte-identical, 77 different. All 77 differences are early-stop searches with ef <= 1.25 k, which v4 skips: each now equals fixed search at the same ef byte for byte (0 unexpected). Of the 281 early-stop searches with ef <= 1.25 k, 204 were already identical because the rule never stopped there.
- So every number in this report equals the v3 report except where an earlier choice used early stop at ef <= 1.25 k (the "old" alpha at four C=0.90/0.95 k100-r80 points), which now saves nothing.
- Early stop requested without alpha: 108 searches (every ef, calibration and held-out queries) reproduce the explicit alpha 1.5 (k=10) or 1.15 (k=100) byte for byte, and fixed search where ef <= 1.25 k: 108 of 108 identical.

## Held-out failures caused by early stop

Added failures = queries that reach R with fixed ef but not with early stop; slack = fixed reached minus the number C requires. On the calibration queries the fixed ef sits exactly at C_cal at every point, so the coverage gate there means "no added failure".

| tier | point | arm | alpha | added failures | fixed slack | mean loss |
|---|---|---|---:|---:|---:|---:|
| 0.90 | cohere k10-r80 | rule_b | 1.13 | 3 | 33 | 0.58 pt |
| 0.95 | cohere k10-r80 | rule_b | 1.15 | 2 | 12 | 0.67 pt |
| 0.95 | cohere k10-r80 | old | 1.15 | 2 | 12 | 0.67 pt |
| 0.95 | laion k10-r90 | rule_c | 1.17 | 0 | 1 | 0.57 pt |
| 0.95 | laion k10-r90 | rule_b | 1.17 | 0 | 1 | 0.57 pt |
| 0.99 | dbpedia k100-r95 | rule_c | 1.08 | 7 | 5 | 0.32 pt |
| 0.99 | dbpedia k100-r95 | rule_b | 1.08 | 7 | 5 | 0.32 pt |
| 0.99 | cohere k10-r90 | rule_c | 1.26 | 2 | 1 | 0.30 pt |
| 0.99 | cohere k10-r90 | rule_b | 1.26 | 2 | 1 | 0.30 pt |
| 0.99 | cohere k10-r90 | old | 1.3 | 2 | 1 | 0.18 pt |
| 0.99 | cohere k10-r95 | default | 1.5 | 3 | 1 | 0.05 pt |
| 0.99 | laion k10-r80 | rule_c | 1.18 | 0 | 0 | 0.57 pt |
| 0.99 | laion k10-r80 | rule_b | 1.17 | 0 | 0 | 0.75 pt |

## Where the two-SE margin changed the choice

| tier | point | rule C | rule B | held-out saving C / B | held-out pass C / B |
|---|---|---:|---:|---|---|
| 0.90 | cohere k10-r80 | 1.14 | 1.13 | 9.2% / 11.3% | pass / early_stop_fails |
| 0.95 | cohere k10-r80 | 1.17 | 1.15 | 11.7% / 16.6% | pass / early_stop_fails |
| 0.99 | cohere k10-r80 | 1.21 | 1.18 | 17.4% / 26.0% | fixed_fails / fixed_fails |
| 0.99 | laion k10-r80 | 1.18 | 1.17 | 73.7% / 76.2% | early_stop_fails / early_stop_fails |
| 0.99 | laion k100-r90 | 1.08 | 1.07 | 49.2% / 53.8% | pass / pass |

## Checks

- Per-query monotonicity in alpha (recall and work never decrease as alpha grows; no alpha beats fixed): no violations.
- Held-out failures caused by early stop (any arm): 13.
- Points where the two-SE margin changed the choice: 5.

