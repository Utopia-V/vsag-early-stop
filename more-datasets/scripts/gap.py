#!/usr/bin/env python3
"""Fixed ef against the per-query ideal width, in distance computations, on the held-out queries, at every tier.

usage: RECAL_RUN=work/gap gap.py DS [DS ...]

One width grid per (dataset, k), the same for every tier: G_k = {round(k * 1.1^i)} up to the largest fixed ef of any
tier of that (dataset, k), plus every tier's fixed ef. Fixed search is run on the held-out queries at every width in
G_k (cached in RUN/gapcache-DS-kK.npz; cached widths are not rerun). For tier C with fixed ef e_C:
- a query's ideal width is the smallest width in {round(k * 1.1^i) <= e_C} U {e_C} that reaches R (recall as in the coverage
  protocol); a query that no tested width up to e_C brings to R is charged the work at e_C and counted;
- gap = mean distance computations at e_C / mean distance computations at the ideal widths (1.00 when e_C = k);
- rule C recovered share = (work at e_C - work of rule C) / (work at e_C - ideal work), shown only where rule C
  passes its quality check: mean recall loss <= 0.5 points and early stop reaching R on at least ceil(L * n) held-out
  queries, L = 0.99 for tier 0.99, 0.975 for tier 0.95, and the literal level 0.90 / 0.95 / 0.99 for tiers
  0.80 / 0.90 / 0.98.
The candidate set of a tier depends only on k and its own e_C, not on which other tiers or files exist.
Rows only for tiers whose rule C was evaluated (package record or a quality run here), so that a fixed ef calibrated
later for another arm (97.5% for the free-ef arm of three datasets) does not add a row or a width to the cache.
Fixed efs: work/fixed-ef/fixed-points.json; for dbpedia/cohere/laion tiers 0.90/0.95/0.99 the package's frozen file
(rule C from its record). Output: RUN/gap-DS.json.
"""
import math
import sys

import numpy as np

import config
import recalibrate as r

WORK = config.WORK
ORIGINAL = {'dbpedia', 'cohere', 'laion'}
LEVEL = {0.80: 0.90, 0.90: 0.95, 0.95: 0.975, 0.98: 0.99, 0.99: 0.99}
RUN_OF = {0.99: 'c99', 0.98: 'lvl', 0.80: 'lvl', 0.90: 'l95', 0.95: 'c90-c95'}


def fixed_points(ds):
    out = {}
    paths = ([config.FROZEN / 'fixed-points.json'] if ds in ORIGINAL else []) + [WORK / 'fixed-ef' / 'fixed-points.json']
    for path in paths:
        if path.exists():
            for p in r.read(path):
                key = (p['k'], round(p['R'], 2), p['C'])
                if p['dataset'] == ds and key not in out:
                    out[key] = p['ef']
    return out


def rule_c(ds, k, R, C):
    if ds in ORIGINAL and C in (0.90, 0.95, 0.99):
        summary = r.read(config.PACKAGE / 'results' / 'quality' / 'summary-v4.json')
        p = next((p for p in summary['points'] if p['dataset'] == ds and p['point'] == r.label(k, R, C)), None)
        return p and p['held_out'].get('rule_c')
    path = WORK / RUN_OF[C] / 'quality' / 'pr' / ds / f'validation-result-k{k}.json'
    return r.read(path).get(r.label(k, R, C), {}).get('rule_c') if path.exists() else None


def evaluated(ds, k, C):
    if ds in ORIGINAL and C in (0.90, 0.95, 0.99):
        return True
    return C in RUN_OF and (WORK / RUN_OF[C] / 'quality' / 'pr' / ds / f'validation-result-k{k}.json').exists()


def main():
    lib = r.CFG['quality_library']
    for ds in sys.argv[1:]:
        truth = None  # loaded only when a width is not in the cache yet (a cached run needs no inputs)
        points = fixed_points(ds)
        out = {}
        for k in r.KS:
            # Only calibration levels whose rule C was evaluated (the package record or a quality run of this
            # measurement): a fixed ef calibrated for another arm alone (97.5% of three new datasets, calibrated for the
            # free-ef arm after this script ran) gets no row. A level's row depends only on k and its own fixed ef.
            mine = {(R, C): ef for (kk, R, C), ef in points.items() if kk == k and ef is not None and evaluated(ds, k, C)}
            if not mine:
                continue
            top = max(mine.values())
            base = sorted({int(round(k * 1.1 ** i)) for i in range(400) if round(k * 1.1 ** i) <= top})
            grid = sorted(set(base) | set(mine.values()))
            cache_path = r.RUN / f'gapcache-{ds}-k{k}.npz'
            cache = {}
            if cache_path.exists():
                data = np.load(cache_path)
                efs = {int(n.split('/')[0][2:]) for n in data.files}
                cache = {e: (data[f'ef{e}/recall'], data[f'ef{e}/dist']) for e in efs}
            todo = [e for e in grid if e not in cache]
            if todo:
                truth = truth or r.Truth(r.DATASETS[ds]['validation'], r.DATASETS[ds]['metric'])
                n = 0
                while (r.qdir(lib, ds) / 'validation' / f'k{k}-gap-{n:03d}').exists():
                    n += 1
                rows = r.run_modes(ds, 'validation', k, {r.alpha_name(e, None): (r.params(e, None), e) for e in todo},
                                   f'k{k}-gap-{n:03d}', lib)
                for e in todo:
                    rec, dc, _ = r.summarize(truth, k, rows[r.alpha_name(e, None)])
                    cache[e] = (rec, dc)
                np.savez_compressed(cache_path, **{f'ef{e}/{x}': v for e, (rec, dc) in cache.items()
                                                   for x, v in [('recall', rec), ('dist', dc)]})
            for (R, C), ef in sorted(mine.items()):
                cand = sorted({g for g in base if g <= ef} | {ef})
                rec = np.array([cache[g][0] for g in cand])
                dc = np.array([cache[g][1] for g in cand], dtype=float)
                ok = rec >= R - 1e-12
                reached = ok.any(axis=0)
                nq = rec.shape[1]
                ideal = np.where(reached, dc[ok.argmax(axis=0), np.arange(nq)], dc[-1])
                ideal_ef = np.where(reached, np.array(cand)[ok.argmax(axis=0)], ef)
                fixed = float(dc[-1].mean())
                c = rule_c(ds, k, R, C)
                share, check = None, None
                if c is not None:
                    need = math.ceil(LEVEL[C] * nq - 1e-9)
                    check = bool(c['mean_loss'] <= r.LOSS and c['reached'] >= need)
                    if check and fixed > ideal.mean():
                        share = (fixed - c['mean_dist_cmp']) / (fixed - float(ideal.mean()))
                out[r.label(k, R, C)] = dict(
                    dataset=ds, k=k, R=R, C=C, C_cal=r.CS.get(C), fixed_ef=ef, widths_tested=len(cand), queries=int(nq),
                    fixed_mean_dist_cmp=fixed, ideal_mean_dist_cmp=float(ideal.mean()), gap=fixed / float(ideal.mean()),
                    fixed_reached=int(ok[-1].sum()),
                    no_tested_width_up_to_fixed_ef_reaches_R=int((~reached).sum()),
                    ideal_ef_quantiles={str(q): float(np.quantile(ideal_ef, q)) for q in (0.5, 0.9, 0.99)},
                    rule_c=None if c is None else dict(alpha=c['alpha'], mean_dist_cmp=c['mean_dist_cmp'],
                                                       reached=c['reached'], mean_loss=c['mean_loss']),
                    rule_c_check=check, rule_c_recovered_share=share)
                print(ds, r.label(k, R, C), 'ef', ef, 'gap', round(fixed / float(ideal.mean()), 2), 'share',
                      None if share is None else round(share, 2), flush=True)
        r.save(r.RUN / f'gap-{ds}.json', out)


if __name__ == '__main__':
    main()
