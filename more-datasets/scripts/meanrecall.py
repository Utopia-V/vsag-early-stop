#!/usr/bin/env python3
"""Mean-recall arm: fixed ef and early stop compared at mean-recall targets (not the coverage protocol).

usage: RECAL_RUN=work/mean-recall meanrecall.py fixed DS | alpha DS | validate DS | timing DS [--force] | report DS

Per dataset, k in {10, 100}, mean-recall target T in {0.90, 0.95, 0.99}; recall counted as in the coverage protocol
(recalibrate.Truth: distance-based, tolerance 2e-6 on the library's distance).
- fixed: the smallest ef_search whose mean recall on the calibration queries reaches T. Search as calibrate_ef.py's
  C=0.99 bisection (double from ef = k up to 8192, then integer bisection; smallest passing ef measured). Fixed-ef
  recalls already measured by calibrate_ef.py on the same queries and library are reused (work/fixed-ef cache).
- alpha: over ef in {round(ef0 * 1.1^i), i = 0..10} (ef0 = fixed ef) and the package's 55-value alpha grid, the setting
  with the fewest mean distance computations whose calibration mean recall reaches T; ties: larger alpha, then smaller
  ef. Settings with ef <= 1.25 k are not run (the library skips the rule there; they equal fixed search at that ef,
  which costs at least the baseline). If the best setting saves less than 5% of the baseline's mean distance
  computations, the point is "no early stop".
- validate: held-out mean recall of fixed (ef0) and early stop (ef*, alpha*) with standard errors (sd / sqrt(n)) and
  the paired difference; pass if early stop's held-out mean recall >= fixed's - 0.005.
- timing: reference build at ef0 against the PR build at (ef*, alpha*), 1 and 8 threads, four rotating batches,
  medians: recalibrate.timing with this plan (refuses to start when the 1-minute load is >= max_load).
Outputs: work/mean-recall/meanrecall-DS.json (per point), per-query held-out results meanrecall-validation-DS.json,
calibration per-mode results calibration-DS-k*.npz, timing in timing-DS/ and timing-summary-DS.json.
"""
import json
import math
import sys

import numpy as np

import recalibrate as r

TARGETS = [0.90, 0.95, 0.99]
EF_STEPS = 11
MIN_SAVING = 5.0
LOSS = 0.005
EF_LIMIT = 8192


def tag(k, T):
    return f'm{int(round(T * 100))}-k{k}'


class Measure:
    """Fixed-ef per-query recalls and work on the calibration queries; cached in RUN, seeded from work/fixed-ef."""

    def __init__(self, ds, k, lib, truth):
        self.ds, self.k, self.lib, self.truth = ds, k, lib, truth
        self.path = r.RUN / 'fixed-ef' / lib / f'{ds}-k{k}.json'
        self.cache, self.work = {}, {}
        if self.path.exists():
            raw = r.read(self.path)
            self.cache = {int(e): np.array(v['recalls']) for e, v in raw.items()}
            self.work = {int(e): np.array(v['dist_cmp']) for e, v in raw.items()}

    def __call__(self, efs):
        todo = sorted({e for e in efs if e not in self.cache})
        if todo:
            folder = r.qdir(self.lib, self.ds) / 'calibration'
            n = 0
            while (folder / f'k{self.k}-ef-{n:03d}').exists():
                n += 1
            modes = {r.alpha_name(e, None): (r.params(e, None), e) for e in todo}
            rows = r.run_modes(self.ds, 'calibration', self.k, modes, f'k{self.k}-ef-{n:03d}', self.lib)
            for e in todo:
                rec, dc, _ = r.summarize(self.truth, self.k, rows[r.alpha_name(e, None)])
                self.cache[e], self.work[e] = rec, dc
            r.save(self.path, {str(e): dict(recalls=self.cache[e].tolist(), dist_cmp=self.work[e].tolist())
                               for e in sorted(self.cache)})

    def passes(self, ef, T):
        return float(self.cache[ef].mean()) >= T - 1e-12


def bisect(measure, k, T):
    low, high, tested = k - 1, k, []
    while True:
        measure([high])
        tested.append(high)
        if measure.passes(high, T):
            break
        if high == EF_LIMIT:
            return None, tested
        low, high = high, min(EF_LIMIT, 2 * high)
    while high - low > 1:
        mid = (high + low) // 2
        measure([mid])
        tested.append(mid)
        if measure.passes(mid, T):
            high = mid
        else:
            low = mid
    return min(e for e in tested if measure.passes(e, T)), sorted(tested)


def fixed(ds, lib):
    truth = r.Truth(r.DATASETS[ds]['calibration'], r.DATASETS[ds]['metric'])
    out_path = r.RUN / f'fixed-{ds}.json'
    out = r.read(out_path) if out_path.exists() else {}
    for k in r.KS:
        measure = Measure(ds, k, lib, truth)
        # Measurements of the coverage calibration on the same queries and library (recall and work of fixed search).
        seed = r.config.WORK / 'fixed-ef' / 'quality' / lib / ds / 'calibration'
        for folder in sorted(seed.glob(f'k{k}-ef-*')):
            for path in sorted((folder / 'out').glob('ef*-fixed.bin')):
                ef = int(path.stem.split('-')[0][2:])
                if ef not in measure.cache:
                    rec, dc, _ = r.summarize(truth, k, r.parse(path))
                    measure.cache[ef], measure.work[ef] = rec, dc
        for T in TARGETS:
            ef, tested = bisect(measure, k, T)
            assert ef is not None, (ds, k, T)
            out[tag(k, T)] = dict(dataset=ds, k=k, T=T, fixed_ef=ef, tested=tested,
                                  calibration_mean_recall={str(e): float(measure.cache[e].mean()) for e in tested})
            print(ds, tag(k, T), 'fixed ef', ef, flush=True)
        r.save(measure.path, {str(e): dict(recalls=measure.cache[e].tolist(), dist_cmp=measure.work[e].tolist())
                              for e in sorted(measure.cache)})
    r.save(out_path, out)


def ef_grid(ef0):
    return sorted({int(round(ef0 * 1.1 ** i)) for i in range(EF_STEPS)})


def alpha(ds, lib):
    truth = r.Truth(r.DATASETS[ds]['calibration'], r.DATASETS[ds]['metric'])
    points = r.read(r.RUN / f'fixed-{ds}.json')
    result = {}
    for k in r.KS:
        mine = {t: p for t, p in points.items() if p['k'] == k}
        efs = sorted({e for p in mine.values() for e in ef_grid(p['fixed_ef'])})
        modes = {}
        for ef in efs:
            modes[r.alpha_name(ef, None)] = (r.params(ef, None), ef)
            if ef > r.AUTO_OFF_RATIO * k:
                for a in r.ALPHAS:
                    modes[r.alpha_name(ef, a)] = (r.params(ef, a), ef)
        npz = r.RUN / f'calibration-{ds}-k{k}.npz'
        if npz.exists():
            data = np.load(npz)
            results = {n: (data[f'{n}/recall'], data[f'{n}/dist']) for n in modes}
        else:
            rows = r.run_modes(ds, 'calibration', k, modes, f'k{k}-meanrecall', lib)
            results = {}
            for n, rr in rows.items():
                rec, dc, _ = r.summarize(truth, k, rr)
                results[n] = (rec, dc)
            np.savez_compressed(npz, **{f'{n}/{x}': v for n, (rec, dc) in results.items()
                                        for x, v in [('recall', rec), ('dist', dc)]})
        for t, p in sorted(mine.items()):
            ef0, T = p['fixed_ef'], p['T']
            f_rec, f_dc = results[r.alpha_name(ef0, None)]
            base_dc = float(f_dc.mean())
            cands = []
            for ef in ef_grid(ef0):
                if ef <= r.AUTO_OFF_RATIO * k:
                    continue
                for a in r.ALPHAS:
                    rec, dc = results[r.alpha_name(ef, a)]
                    if float(rec.mean()) >= T - 1e-12:
                        cands.append(dict(ef=ef, alpha=a, mean_recall=float(rec.mean()), mean_dist_cmp=float(dc.mean()),
                                          saving_pct=100 * (1 - float(dc.mean()) / base_dc)))
            best = min(cands, key=lambda c: (c['mean_dist_cmp'], -c['alpha'], c['ef'])) if cands else None
            chosen = best if best is not None and best['saving_pct'] >= MIN_SAVING else None
            result[t] = dict(p, auto_off_at_fixed_ef=ef0 <= r.AUTO_OFF_RATIO * k, ef_grid=ef_grid(ef0),
                             calibration_fixed=dict(mean_recall=float(f_rec.mean()), mean_dist_cmp=base_dc),
                             best=best, chosen=chosen, qualifying_settings=len(cands),
                             status='early_stop' if chosen else 'no early stop')
            print(ds, t, 'ef0', ef0, 'best', None if best is None else (best['ef'], best['alpha'],
                  round(best['saving_pct'], 1)), result[t]['status'], flush=True)
    r.save(r.RUN / f'meanrecall-{ds}.json', result)


def mean_se(x):
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x)))


def validate(ds, lib):
    truth = r.Truth(r.DATASETS[ds]['validation'], r.DATASETS[ds]['metric'])
    sel = r.read(r.RUN / f'meanrecall-{ds}.json')
    per_query = {}
    for k in r.KS:
        mine = {t: p for t, p in sel.items() if p['k'] == k}
        modes = {}
        for p in mine.values():
            modes[r.alpha_name(p['fixed_ef'], None)] = (r.params(p['fixed_ef'], None), p['fixed_ef'])
            if p['chosen']:
                c = p['chosen']
                modes[r.alpha_name(c['ef'], c['alpha'])] = (r.params(c['ef'], c['alpha']), c['ef'])
        rows = r.run_modes(ds, 'validation', k, modes, f'k{k}-meanrecall-validation', lib)
        res = {n: r.summarize(truth, k, rr) for n, rr in rows.items()}
        for n, (rec, dc, stops) in res.items():
            per_query[f'k{k}/{n}'] = dict(recalls=rec.tolist(), dist_cmp=dc.tolist(), stops=stops)
        for t, p in mine.items():
            f_rec, f_dc, _ = res[r.alpha_name(p['fixed_ef'], None)]
            h = dict(queries=len(f_rec), fixed=dict(zip(['mean_recall', 'se'], mean_se(f_rec)),
                                                    mean_dist_cmp=float(f_dc.mean())))
            if p['chosen']:
                c = p['chosen']
                rec, dc, stops = res[r.alpha_name(c['ef'], c['alpha'])]
                diff = f_rec - rec
                h['early_stop'] = dict(zip(['mean_recall', 'se'], mean_se(rec)), mean_dist_cmp=float(dc.mean()),
                                       saving_pct=100 * (1 - float(dc.mean()) / float(f_dc.mean())), stops=stops,
                                       loss=float(diff.mean()), loss_se=mean_se(diff)[1])
                h['pass'] = bool(h['early_stop']['mean_recall'] >= h['fixed']['mean_recall'] - LOSS - 1e-12)
            p['held_out'] = h
            print(ds, t, 'held-out fixed', round(h['fixed']['mean_recall'], 4),
                  'ES', None if 'early_stop' not in h else (round(h['early_stop']['mean_recall'], 4),
                                                             round(h['early_stop']['saving_pct'], 1), h['pass']),
                  flush=True)
    r.save(r.RUN / f'meanrecall-{ds}.json', sel)
    r.save(r.RUN / f'meanrecall-validation-{ds}.json', per_query)


def timing(ds, force):
    sel = r.read(r.RUN / f'meanrecall-{ds}.json')
    plan = {}
    for k in r.KS:
        arms = {'ref': {}, 'on': {}}
        for t, p in sel.items():
            if p['k'] == k and p['chosen']:
                arms['ref'][t] = r.params(p['fixed_ef'], None)
                arms['on'][t] = r.params(p['chosen']['ef'], p['chosen']['alpha'])
        if arms['on']:
            plan[(ds, k)] = arms
    if not plan:
        print(ds, 'no early-stop point to time')
        r.save(r.RUN / f'timing-summary-{ds}.json', dict(results=[], note='no mean-recall point chose early stop'))
        return
    r.timing(r.CFG['timing_candidate'], r.CFG['timing_reference'], r.CFG['quality_library'], ds, force,
             plan=plan, target=r.RUN / f'timing-{ds}')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv
    phase, ds = args[0], args[1]
    lib = r.CFG['quality_library']
    dict(fixed=lambda: fixed(ds, lib), alpha=lambda: alpha(ds, lib), validate=lambda: validate(ds, lib),
         timing=lambda: timing(ds, force))[phase]()
