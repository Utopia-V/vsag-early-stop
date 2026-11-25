#!/usr/bin/env python3
"""Find the fixed ef of every (dataset, k, R, C): the smallest ef whose calibration coverage reaches C_cal = (1+C)/2.

usage: calibrate_ef.py [--lib ROLE] [dataset ...]

Ten-dataset copy: datasets from the registry, recall by the dataset's metric, no frozen "old" alphas (the new
datasets have none). With RECAL_TIERS=0.99 only the C=0.99 bisection runs; a later run with all tiers reuses every
measured ef from the on-disk cache. Run with RECAL_RUN=WORK/fixed-ef (WORK = [paths] work of more-datasets/config.toml).
Tiers 0.80 and 0.98 (calibrated at 90% and 99%) use the bisection of C=0.99; tier 0.90 (95%) uses the grid with
refinement of the first measurement's C=0.90/0.95 tiers, whose refinement step can exceed 1 (up to 21 here, GloVe), so
the selected ef is the smallest passing ef tested, not necessarily the smallest passing integer.

Coverage is the fraction of calibration queries whose recall@k reaches R, with the same recall as the alpha phases
(recalibrate.Truth). The frozen values came from two procedures, reproduced here as they were run:
- C=0.99 (method "bisect", run.py of 2026-09-11 with VSAG's eval_performance): start at ef=k and double until the
  coverage passes (limit 8192), then bisect on integers between the last failing and the first passing ef; the result
  is the smallest passing ef measured for that point. At all 18 frozen points ef-1 was measured and failed.
- C=0.90/0.95 (method "grid", coverage.py of 2026-10-13 with multi_signature): measure the grid round(k * 1.1^i) up to
  1.2 times the largest C=0.99 ef of the same dataset and k; take the first passing grid value and the grid value
  below it, measure at most 24 evenly spaced values between them and take the first passing one. Where the step was
  2 or 3 (9 of the 36 frozen points), the exact smallest integer may lie 1-2 lower.
Coverage is not assumed monotone in ef; every tested ef is kept.

Output in the run directory: fixed-points.json (format of frozen/fixed-points.json; the "old" comparison alphas are
copied from the frozen file, the ef values are new) and fixed-ef-calibration.json (every tested ef and the number of
queries reaching R, format of results/fixed-ef/calibration-records.json). Search outputs go to
quality/<lib>/<ds>/calibration/k<k>-ef-NNN like those of the alpha phases.
"""
import fcntl
import math
import sys

import numpy as np

import config
import recalibrate as r

EF_LIMIT = 8192


class Measure:
    """Fixed-ef recalls on the calibration queries of one (dataset, k), cached on disk so a rerun resumes."""

    def __init__(self, ds, k, lib, truth):
        self.ds, self.k, self.lib, self.truth = ds, k, lib, truth
        self.path = r.RUN / 'fixed-ef' / lib / f'{ds}-k{k}.json'
        self.cache = {}
        if self.path.exists():
            self.cache = {int(e): np.array(v) for e, v in r.read(self.path).items()}

    def __call__(self, efs):
        todo = sorted({e for e in efs if e not in self.cache})
        if todo:
            folder = r.qdir(self.lib, self.ds) / 'calibration'
            n = 0
            while (folder / f'k{self.k}-ef-{n:03d}').exists():
                n += 1
            modes = {r.alpha_name(e, None): (r.params(e, None), e) for e in todo}
            rows = r.run_modes(self.ds, 'calibration', self.k, modes, f'k{self.k}-ef-{n:03d}', self.lib)
            if callable(self.truth):  # load the ground truth only when a search has to be scored
                self.truth = self.truth()
            for e in todo:
                self.cache[e] = r.summarize(self.truth, self.k, rows[r.alpha_name(e, None)])[0]
            r.save(self.path, {str(e): v.tolist() for e, v in sorted(self.cache.items())})
        return {e: self.cache[e] for e in efs}

    def reached(self, ef, R):
        return int(np.sum(self.cache[ef] >= R - 1e-12))

    def passes(self, ef, R, cal):
        return r.coverage(self.cache[ef], R) >= cal


def bisect(measure, k, Rs, cal):
    """run.py calibrate_ef for several R at once: each point follows its own sequence; searches are batched."""
    state = {R: dict(low=k - 1, high=k, phase='double', tested=[]) for R in Rs}
    while True:
        want = {}
        for R, s in state.items():
            if s['phase'] == 'double':
                want[R] = s['high']
            elif s['phase'] == 'bisect' and s['high'] - s['low'] > 1:
                want[R] = (s['high'] + s['low']) // 2
            elif s['phase'] == 'bisect':
                s['phase'] = 'done'
        if not want:
            break
        measure(want.values())
        for R, ef in want.items():
            s = state[R]
            if ef not in s['tested']:
                s['tested'].append(ef)
            ok = measure.passes(ef, R, cal)
            if s['phase'] == 'double':
                if ok:
                    s['phase'] = 'bisect'
                elif s['high'] == EF_LIMIT:
                    s['phase'] = 'failed'
                else:
                    s['low'], s['high'] = s['high'], min(EF_LIMIT, s['high'] * 2)
            elif ok:
                s['high'] = ef
            else:
                s['low'] = ef
    out = {}
    for R, s in state.items():
        passing = [e for e in s['tested'] if measure.passes(e, R, cal)]
        out[R] = dict(fixed_ef=min(passing) if s['phase'] == 'done' else None, tested=sorted(s['tested']))
    return out


def grid(measure, k, Rs, tiers, cap):
    """coverage.py grid + fine."""
    efs = sorted({int(round(k * 1.1 ** i)) for i in range(0, 200) if k * 1.1 ** i <= cap})
    measure(efs)
    brackets = {}
    for R in Rs:
        for C in tiers:
            cal = r.CS[C]
            passing = [e for e in efs if measure.passes(e, R, cal)]
            if not passing:  # unresolvable within the grid: reported, not evaluated
                brackets[(R, C)] = None
                continue
            first = passing[0]
            below = max([e for e in efs if e < first], default=k - 1)
            step = max(1, -(-(first - below) // 24))
            brackets[(R, C)] = sorted(set(list(range(below + step, first, step)) + [first]))
    measure(sorted({e for values in brackets.values() if values for e in values}))
    out = {}
    for (R, C), values in brackets.items():
        if values is None:
            out[(R, C)] = dict(fixed_ef=None, grid=efs, bracket=None, tested=efs)
            continue
        ef = next(e for e in values if measure.passes(e, R, r.CS[C]))
        out[(R, C)] = dict(fixed_ef=ef, grid=efs, bracket=values, tested=sorted(set(efs) | set(values)))
    return out


def main():
    args = sys.argv[1:]
    lib = r.CFG['quality_library']
    if args[:1] == ['--lib']:
        lib, args = args[1], args[2:]
    datasets = args or list(r.DATASETS)
    out_points = r.RUN / 'fixed-points.json'
    records_path = r.RUN / 'fixed-ef-calibration.json'
    points = {(p['dataset'], p['k'], round(p['R'], 2), p['C']): p for p in r.read(out_points)} \
        if out_points.exists() else {}
    records = {(p['dataset'], p['k'], round(p['R'], 2), p['C']): p for p in r.read(records_path)['points']} \
        if records_path.exists() else {}
    for ds in datasets:
        def truth(ds=ds):
            return r.Truth(r.DATASETS[ds]['calibration'], r.DATASETS[ds]['metric'])
        for k in r.KS:
            measure = Measure(ds, k, lib, truth)
            # C = 0.99 is needed for itself and for the grid cap of 0.90/0.95; a run with only tiers 0.80/0.98 skips it.
            c99 = bisect(measure, k, r.RS, r.CS[0.99]) if {0.90, 0.95, 0.99} & set(r.TIERS) else {}
            for R, result in c99.items():
                records[(ds, k, R, 0.99)] = dict(dataset=ds, k=k, R=R, C=0.99, C_cal=r.CS[0.99], method='bisect',
                                                 fixed_ef=result['fixed_ef'],
                                                 tested=[dict(ef=e, reached=measure.reached(e, R),
                                                              queries=len(measure.cache[e])) for e in result['tested']])
            # A point whose fixed search cannot reach C_cal at any ef <= 8192 keeps fixed_ef None and is reported as
            # unresolvable (the package asserted here; on its three datasets this never happened).
            cap = math.ceil(1.2 * max([v['fixed_ef'] or EF_LIMIT for v in c99.values()] or [0]))
            # Tiers 0.80 and 0.98 (added in this run): the same bisection as C = 0.99, at their own C_cal.
            for C in [c for c in [0.80, 0.98] if c in r.TIERS]:
                for R, result in bisect(measure, k, r.RS, r.CS[C]).items():
                    records[(ds, k, R, C)] = dict(dataset=ds, k=k, R=R, C=C, C_cal=r.CS[C], method='bisect',
                                                  fixed_ef=result['fixed_ef'],
                                                  tested=[dict(ef=e, reached=measure.reached(e, R),
                                                               queries=len(measure.cache[e])) for e in result['tested']])
            low = [C for C in [0.90, 0.95] if C in r.TIERS]
            for (R, C), result in (grid(measure, k, r.RS, low, cap).items() if low else []):
                records[(ds, k, R, C)] = dict(dataset=ds, k=k, R=R, C=C, C_cal=r.CS[C], method='grid',
                                              fixed_ef=result['fixed_ef'], grid=result['grid'], bracket=result['bracket'],
                                              tested=[dict(ef=e, reached=measure.reached(e, R),
                                                           queries=len(measure.cache[e])) for e in result['tested']])
            for (d, kk, R, C), rec in records.items():
                if d == ds and kk == k:
                    points[(d, kk, R, C)] = dict(dataset=d, k=kk, R=R, C=C, ef=rec['fixed_ef'],
                                                 ef_source=f'calibrate_ef.py ({rec["method"]}, library {lib})',
                                                 old_alpha=None, old_rule=None)
                    print(ds, r.label(kk, R, C), 'ef', rec['fixed_ef'], flush=True)
            # Several datasets may be calibrated by concurrent processes: merge under a lock, newest entries win.
            with open(r.RUN / '.fixed-points.lock', 'a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                if out_points.exists():
                    points = {**{(p['dataset'], p['k'], round(p['R'], 2), p['C']): p for p in r.read(out_points)},
                              **{key: v for key, v in points.items() if key[0] == ds}}
                if records_path.exists():
                    records = {**{(p['dataset'], p['k'], round(p['R'], 2), p['C']): p
                                  for p in r.read(records_path)['points']},
                               **{key: v for key, v in records.items() if key[0] == ds}}
                r.save(out_points, [points[key] for key in sorted(points)])
                order = {d: i for i, d in enumerate(r.DATASETS)}
                r.save(records_path, dict(library=lib, points=[records[key] for key in sorted(
                    records, key=lambda x: (x[3], order[x[0]], x[1], x[2]))]))


if __name__ == '__main__':
    main()
