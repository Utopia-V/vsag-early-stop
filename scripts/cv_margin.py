#!/usr/bin/env python3
"""Choose the rule C+m margin m by cross-validation on the calibration queries only (no held-out data).

usage: cv_margin.py QUALITY_DIR [OUTPUT_JSON]

QUALITY_DIR is quality/<lib> of a run (it holds <ds>/calibration-k*.json and <ds>/selection-k*.json from the alpha
phase). For every point with early stop: 300 random 2/3 vs 1/3 splits of its calibration queries; rule C on the 2/3;
alpha raised by margin m; failure on the other third = added failures above C_cal - C, or mean recall loss above
0.5 points. The chosen m per tier is the smallest margin whose mean failure probability over the tier's points is at
most 2.5%. The delivered margins (0.05 at C=0.90 and 0.95, 0.25 at C=0.99) came from this script on the calibration
outputs of 2026-10-22; results/margin/ holds its output.

The computation is the original script's (seed 20261022); only the input and output paths became arguments and the
chosen m is printed.
"""
import json, math, re, sys
import numpy as np
R = sys.argv[1]
rng = np.random.default_rng(20261022)
MARGINS = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.33, 0.5]
REPS = 300
rows = []
for ds in ["dbpedia", "cohere", "laion"]:
    for k in [10, 100]:
        cal = json.load(open(f"{R}/{ds}/calibration-k{k}.json"))
        sel = json.load(open(f"{R}/{ds}/selection-k{k}.json"))
        for name, p in sel.items():
            if p.get("auto_off"): continue
            ef, Rt, C, Ccal = p["fixed_ef"], p["R"], p["C"], p["C_cal"]
            fx = cal[f"ef{ef}-fixed"]; r0 = np.array(fx["recalls"]); d0 = np.array(fx["dist_cmp"], float)
            alphas = sorted(float(m.group(1)) for key in cal if (m := re.fullmatch(rf"ef{ef}-a([\d.]+)", key)))
            ra = np.array([cal[f"ef{ef}-a{a:.5f}"]["recalls"] for a in alphas])      # [A, n]
            da = np.array([cal[f"ef{ef}-a{a:.5f}"]["dist_cmp"] for a in alphas], float)
            n = len(r0); tol = 1e-9
            pass0 = r0 >= Rt - tol; passa = ra >= Rt - tol
            def boundary(idx):
                m = len(idx)
                cov_ok = passa[:, idx].sum(1) >= math.ceil(Ccal * m - 1e-9)
                loss = r0[idx][None, :] - ra[:, idx]
                mu = loss.mean(1); se = loss.std(1, ddof=1) / math.sqrt(m)
                ok = cov_ok & (mu + 2 * se <= 0.005 + 1e-12)
                # smallest alpha such that it and all larger pass
                good = np.flip(np.cumprod(np.flip(ok)).astype(bool))
                return alphas[int(np.argmax(good))] if good.any() else None
            out = {m: dict(added=[], loss=[], save=[], fail=[], none=0) for m in MARGINS}
            for _ in range(REPS):
                perm = rng.permutation(n); s = perm[: 2 * n // 3]; t = perm[2 * n // 3:]
                ab = boundary(s)
                for m in MARGINS:
                    if ab is None: out[m]["none"] += 1; continue
                    target = 1 + (ab - 1) * (1 + m)
                    j = next((i for i, a in enumerate(alphas) if a >= target - 1e-9), len(alphas) - 1)
                    added = (pass0[t] & ~passa[j, t]).mean()
                    out[m]["added"].append(added); out[m]["loss"].append((r0[t] - ra[j, t]).mean())
                    out[m]["save"].append(1 - da[j, t].mean() / d0[t].mean())
                    out[m]["fail"].append(added > (Ccal - C) + 1e-12 or (r0[t] - ra[j, t]).mean() > 0.005 + 1e-12)
            slack = Ccal - C
            row = dict(point=f"{ds} {name}", n=n, slack=slack, full_boundary=boundary(np.arange(n)))
            for m in MARGINS:
                a = np.array(out[m]["added"]); l = np.array(out[m]["loss"]); sv = np.array(out[m]["save"])
                row[m] = dict(added_over_slack=float(a.mean() / slack) if len(a) else None,
                              p_exceed=float((a > slack).mean()) if len(a) else None,
                              p_loss=float((l > 0.005).mean()) if len(l) else None,
                              save=float(sv.mean()) if len(sv) else None,
                              p_fail=float(np.mean(out[m]["fail"])) if len(out[m]["fail"]) else None)
            rows.append(row)
json.dump(rows, open(sys.argv[2] if len(sys.argv) > 2 else "cv_margin.json", "w"), indent=1)
for C in ["c90", "c95", "c99"]:
    sub = [r for r in rows if f" {C}-" in r["point"]]
    print(f"== {C}: {len(sub)} points")
    for m in MARGINS:
        pf = [r[m]["p_fail"] for r in sub if r[m]["p_fail"] is not None]
        sv = [r[m]["save"] for r in sub if r[m]["save"] is not None]
        print(f"  margin {m:4.2f}: P(fail on held-out third) mean {np.mean(pf):.3f} max {np.max(pf):.3f} points>10% {sum(p>0.10 for p in pf)} | saving mean {np.mean(sv)*100:5.1f}%")
for C in ["c90", "c95", "c99"]:
    sub = [r for r in rows if f" {C}-" in r["point"]]
    chosen = next((m for m in MARGINS if np.mean([r[m]["p_fail"] for r in sub if r[m]["p_fail"] is not None]) <= 0.025), None)
    print(f"chosen margin {C}: {chosen}", file=sys.stderr)
