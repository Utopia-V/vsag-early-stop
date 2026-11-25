#!/usr/bin/env python3
"""Completeness and consistency audit of the run, judged by expected rows and outputs, not by queue logs.

usage: check.py   -> tables/check.json and a printed list of missing rows with reasons

Expected rows: every (dataset, tier, k, R) for tiers 0.99, 0.98, 0.90, 0.80 (originals: 0.98, 0.80 from this run, 0.99
and 0.90 from the package record) and the timing that the plan asks for: tier 0.99 every point with a rule C alpha;
tiers 0.98 / 0.90 / 0.80 every point where rule C saves >= 8% on the held-out queries.
Consistency: fixed search at the same ef on the same queries must give identical per-query recall and work in every
run that measured it (calibrate_ef caches, the alpha phases of c99 / lvl / l95, the held-out runs, the gap cache).
"""
import json
from pathlib import Path

import numpy as np

import config
import recalibrate as r
import timing_clean as tc

WORK = config.WORK
ORIGINAL = ('dbpedia', 'cohere', 'laion')
NEW = ['coco-i2i', 'coco-t2i', 'wiki-all', 'sift', 'deep', 'glove', 'gist', 't2i']
RUN_OF = {0.99: 'c99', 0.98: 'lvl', 0.80: 'lvl', 0.90: 'l95'}


def read(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def fixed_points():
    p = read(WORK / 'fixed-ef' / 'fixed-points.json') or []
    return {(x['dataset'], x['k'], round(x['R'], 2), x['C']): x['ef'] for x in p}


def consistency(ds):
    """Compare fixed-search per-query recall/work across all places that hold the same ef and query set."""
    seen, bad, compared = {}, [], 0
    for role in ['calibration', 'validation']:
        sources = []
        for run in ['c99', 'lvl', 'l95', 'c90-c95']:
            for k in r.KS:
                path = WORK / run / 'quality' / 'pr' / ds / f'{role}-k{k}.json'
                if role == 'calibration':
                    path = WORK / run / 'quality' / 'pr' / ds / f'calibration-k{k}.json'
                if path.exists():
                    for name, v in read(path).items():
                        if name.endswith('-fixed'):
                            sources.append((f'{run}/{path.name}', k, int(name.split('-')[0][2:]), np.array(v['recalls']),
                                            np.array(v['dist_cmp'])))
        if role == 'validation':
            for k in r.KS:
                path = WORK / 'gap' / f'gapcache-{ds}-k{k}.npz'
                if path.exists():
                    data = np.load(path)
                    for n in {x.split('/')[0] for x in data.files}:
                        sources.append((path.name, k, int(n[2:]), data[f'{n}/recall'], data[f'{n}/dist']))
        if role == 'calibration':
            for k in r.KS:
                path = WORK / 'fixed-ef' / 'fixed-ef' / 'pr' / f'{ds}-k{k}.json'
                if path.exists():
                    for e, v in read(path).items():
                        sources.append((f'fixed-ef cache {path.name}', k, int(e), np.array(v), None))
        for src, k, ef, rec, dc in sources:
            key = (role, k, ef)
            if key in seen:
                compared += 1
                s0, rec0, dc0 = seen[key]
                same_work = dc is None or dc0 is None or np.array_equal(dc, dc0)
                if dc0 is None and dc is not None:
                    seen[key] = (src, rec, dc)
                if not (np.array_equal(rec, rec0) and same_work):
                    bad.append(dict(role=role, k=k, ef=ef, a=s0, b=src))
            else:
                seen[key] = (src, rec, dc)
    return dict(compared=compared, mismatches=bad)


def main():
    fp = fixed_points()
    missing, timing_missing = [], []
    for ds in NEW + list(ORIGINAL):
        if ds not in config.load()['datasets']:
            continue
        for C in [0.99, 0.98, 0.90, 0.80]:
            if ds in ORIGINAL and C in (0.99, 0.90):
                continue
            summary = read(WORK / RUN_OF[C] / f'summary-pr-{ds}.json')
            have = {(p['k'], round(p['R'], 2)): p for p in (summary or {}).get('points', []) if p['C'] == C}
            for k in r.KS:
                for R in r.RS:
                    if (k, R) in have:
                        p = have[(k, R)]
                        c = p['held_out'].get('rule_c')
                        need = c is not None and (C == 0.99 or c['saving_pct'] >= 8)
                        if need:
                            s = f'-c{int(round(C * 100))}'
                            runs = ([WORK / 'c99' / f'timing-{ds}{s}', WORK / 'c99' / f'timing-{ds}'] if C == 0.99
                                    else [WORK / RUN_OF[C] / f'timing-{ds}{s}'])
                            if not all(tc.lookup(runs, p['point'], th, 'rulec') for th in (1, 8)):
                                timing_missing.append(dict(dataset=ds, tier=C, k=k, R=R, reason='timing not run yet'))
                        continue
                    ef = fp.get((ds, k, R, C), 'absent')
                    if ef is None:
                        why = 'fixed search reaches C_cal at no tried ef <= 8192 on the calibration queries'
                    elif ef == 'absent':
                        why = 'fixed ef not calibrated yet (stage not run)'
                    else:
                        why = 'fixed ef calibrated; alpha/held-out stages not run yet'
                    missing.append(dict(dataset=ds, tier=C, k=k, R=R, reason=why))
    cons = {ds: consistency(ds) for ds in NEW + list(ORIGINAL) if ds in config.load()['datasets']}
    out = dict(missing_quality_rows=missing, missing_timing=timing_missing, consistency=cons)
    (config.TABLES / 'check.json').write_text(json.dumps(out, indent=1) + '\n')
    for m in missing:
        print('missing', m)
    for m in timing_missing:
        print('timing missing', m)
    for ds, c in cons.items():
        print('consistency', ds, c['compared'], 'comparisons', len(c['mismatches']), 'mismatches')


if __name__ == '__main__':
    main()
