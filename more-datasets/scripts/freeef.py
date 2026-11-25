#!/usr/bin/env python3
"""Free-ef arm (coverage criterion, early stop chooses its own ef): a reduction of the mean-recall arm's calibration
sweep plus one held-out run per point.

usage: RECAL_RUN=work/freeef freeef.py DS

For calibration level L = C_cal in {0.90, 0.95, 0.975, 0.99, 0.995} (tiers C = 0.80, 0.90, 0.95, 0.98, 0.99) and
each (k, R) with a fixed ef e_L (work/fixed-ef/fixed-points.json; the package's frozen file for 0.90/0.95/0.99 tiers
of dbpedia/cohere/laion):
- baseline: fixed search at e_L on the calibration queries (per-query recall and work from calibrate_ef.py's outputs);
- candidates: every (ef, alpha) mode and fixed mode of the mean-recall arm's calibration sweep
  (work/mean-recall/calibration-DS-kK.npz: ef in round(ef0 * 1.1^i), i = 0..10, for the three mean-recall ef0;
  the 55 alphas; modes with ef <= 1.25k only as fixed search);
- choice: fewest mean distance computations such that calibration coverage >= L and mean paired recall loss against
  the baseline <= 0.5 points; ties: larger alpha, then smaller ef. "no cheaper setting" if the choice does not cost
  less than the baseline. The sweep's largest ef is reported; a choice at that edge, or a level whose e_L exceeds
  it, means the sweep may be too short for that level.
- held-out: fixed at e_L and the chosen setting, side by side: coverage, mean recall loss, saved distance
  computations; and the same-ef rule C of the coverage protocol where it was run (work/c99, work/lvl, work/c90-c95).
Output: RUN/freeef-DS.json.
"""
import sys

import numpy as np

import config
import recalibrate as r

WORK = config.WORK
ORIGINAL = {'dbpedia', 'cohere', 'laion'}
TIER_RUN = {0.80: 'lvl', 0.98: 'lvl', 0.99: 'c99', 0.90: 'l95', 0.95: 'c90-c95'}


def fixed_points(ds):
    out = {}
    paths = ([config.FROZEN / 'fixed-points.json'] if ds in ORIGINAL else []) + [WORK / 'fixed-ef' / 'fixed-points.json']
    for path in paths:
        if path.exists():
            for p in r.read(path):
                key = (p['k'], round(p['R'], 2), p['C'])
                if p['dataset'] == ds and key not in out and p['ef'] is not None:
                    out[key] = p['ef']
    return out


def fixed_calibration(ds, k, ef, truth):
    """Per-query recall and work of fixed search at ef on the calibration queries, from outputs already on disk."""
    for folder in sorted((WORK / 'fixed-ef' / 'quality' / 'pr' / ds / 'calibration').glob(f'k{k}-ef-*')):
        path = folder / 'out' / f'{r.alpha_name(ef, None)}.bin'
        if path.exists():
            return r.summarize(truth, k, r.parse(path))[:2]
    for run in ['c99', 'lvl', 'c90-c95', 'mean-recall']:
        path = WORK / run / 'quality' / 'pr' / ds / f'calibration-k{k}.json'
        if path.exists():
            res = r.load(path)
            if r.alpha_name(ef, None) in res:
                return res[r.alpha_name(ef, None)][:2]
    return None


def same_ef_rule_c(ds, k, R, C):
    if ds in ORIGINAL and C in (0.90, 0.95, 0.99):
        summary = r.read(config.PACKAGE / 'results' / 'quality' / 'summary-v4.json')
        p = next((p for p in summary['points'] if p['dataset'] == ds and p['point'] == r.label(k, R, C)), None)
        c = p and p['held_out'].get('rule_c')
    else:
        path = WORK / TIER_RUN[C] / 'quality' / 'pr' / ds / f'validation-result-k{k}.json'
        c = r.read(path).get(r.label(k, R, C), {}).get('rule_c') if path.exists() else None
    return None if not c else {key: c[key] for key in ['alpha', 'coverage', 'mean_loss', 'saving_pct', 'reached']}


def main():
    ds = sys.argv[1]
    lib = r.CFG['quality_library']
    cal_truth = r.Truth(r.DATASETS[ds]['calibration'], r.DATASETS[ds]['metric'])
    points = fixed_points(ds)
    out, modes = {}, {}
    for k in r.KS:
        npz = WORK / 'mean-recall' / f'calibration-{ds}-k{k}.npz'
        if not npz.exists():
            for (kk, R, C), ef in sorted(points.items()):
                if kk == k:
                    out[r.label(k, R, C)] = dict(dataset=ds, k=k, R=R, C=C, level=r.CS[C], fixed_ef=ef, chosen=None,
                                                 reason='mean-recall sweep not run for this dataset and k')
            continue
        data = np.load(npz)
        names = sorted({key.rsplit('/', 1)[0] for key in data.files})
        sweep0 = {n: (data[f'{n}/recall'], data[f'{n}/dist']) for n in names}
        max_ef = max(int(n.split('-')[0][2:]) for n in names)
        for (kk, R, C), ef in sorted(points.items()):
            if kk != k or C not in r.CS:
                continue
            L = r.CS[C]
            tag = r.label(k, R, C)
            base = fixed_calibration(ds, k, ef, cal_truth)
            if base is None:
                out[tag] = dict(dataset=ds, k=k, R=R, C=C, level=L, fixed_ef=ef, chosen=None,
                                reason='no per-query calibration result of fixed search at this ef on disk')
                print(ds, tag, 'no calibration baseline on disk', flush=True)
                continue
            b_rec, b_dc = base
            # Same-ef candidates (the fixed ef with every grid alpha, and fixed search itself) under the same rule,
            # from the coverage run's calibration results at this tier, where they exist locally.
            sweep = dict(sweep0)
            sweep[r.alpha_name(ef, None)] = (b_rec, b_dc)
            same = WORK / TIER_RUN[C] / 'quality' / 'pr' / ds / f'calibration-k{k}.json'
            same_ef_included = False
            if same.exists():
                res = r.load(same)
                for a in r.ALPHAS:
                    if r.alpha_name(ef, a) in res and ef > r.AUTO_OFF_RATIO * k:
                        sweep[r.alpha_name(ef, a)] = res[r.alpha_name(ef, a)][:2]
                        same_ef_included = True
            best = None
            for n, (rec, dc) in sweep.items():
                cov = float(np.mean(rec >= R - 1e-12))
                loss = float(np.mean(b_rec - rec))
                if cov >= L and loss <= r.LOSS:
                    e = int(n.split('-')[0][2:])
                    a = None if n.endswith('fixed') else float(n.split('-a')[1])
                    key = (float(dc.mean()), -(a or 0.0), e)
                    if best is None or key < best[0]:
                        best = (key, dict(name=n, ef=e, alpha=a, calibration_coverage=cov, calibration_loss=loss,
                                          calibration_saving_pct=100 * (1 - float(dc.mean()) / float(b_dc.mean()))))
            chosen = best[1] if best else None
            reason = None
            if chosen and (chosen['calibration_saving_pct'] <= 0 or chosen['alpha'] is None):
                # the cheapest qualifying setting is the fixed baseline or another fixed width: no early-stop pair wins
                reason = ('no improvement among the tested pairs' if chosen['calibration_saving_pct'] <= 0 else
                          'cheapest qualifying setting is plain fixed search at another width')
                chosen = dict(chosen, cheaper=False)
            out[tag] = dict(dataset=ds, k=k, R=R, C=C, level=L, fixed_ef=ef, sweep_max_ef=max_ef,
                            fixed_ef_beyond_sweep=ef > max_ef, chosen=chosen, reason=reason,
                            same_ef_candidates_included=same_ef_included,
                            chosen_at_sweep_edge=bool(chosen and chosen['ef'] == max_ef),
                            same_ef_rule_c=same_ef_rule_c(ds, k, R, C))
            if chosen and chosen.get('cheaper', True):
                modes.setdefault(k, {})[r.alpha_name(ef, None)] = (r.params(ef, None), ef)
                modes[k][chosen['name']] = (r.params(chosen['ef'], chosen['alpha']), chosen['ef'])
            print(ds, tag, 'L', L, 'ef', ef, 'chosen', None if not chosen else
                  (chosen['ef'], chosen['alpha'], round(chosen['calibration_saving_pct'], 1)), flush=True)
    val_truth = r.Truth(r.DATASETS[ds]['validation'], r.DATASETS[ds]['metric'])
    for k, m in modes.items():
        folder = r.qdir(lib, ds) / 'validation' / f'k{k}-freeef'
        if folder.exists():
            import time
            folder.rename(folder.with_name(f'{folder.name}-aborted-{int(time.time())}'))
        rows = r.run_modes(ds, 'validation', k, m, f'k{k}-freeef', lib)
        res = {n: r.summarize(val_truth, k, rr) for n, rr in rows.items()}
        for tag, p in out.items():
            c = p['chosen']
            if p['k'] != k or not c or not c.get('cheaper', True):
                continue
            f_rec, f_dc, _ = res[r.alpha_name(p['fixed_ef'], None)]
            rec, dc, _ = res[c['name']]
            p['held_out'] = dict(queries=len(f_rec), fixed_coverage=r.coverage(f_rec, p['R']),
                                 coverage=r.coverage(rec, p['R']), mean_loss=float(np.mean(f_rec - rec)),
                                 saving_pct=100 * (1 - float(dc.mean()) / float(f_dc.mean())),
                                 fixed_reached=int(np.sum(f_rec >= p['R'] - 1e-12)),
                                 reached=int(np.sum(rec >= p['R'] - 1e-12)))
    r.save(r.RUN / f'freeef-{ds}.json', out)


if __name__ == '__main__':
    main()
