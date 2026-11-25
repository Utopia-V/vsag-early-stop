#!/usr/bin/env python3
"""Headline tables: rule C (no margin) at the fixed ef against the reference library, per calibration level.

usage: headline.py            -> TABLES/headline.md, TABLES/headline.json

Calibration level = the share of calibration queries that must reach R at the fixed ef. Levels and the scripts'
internal tier numbers (kept as keys of headline.json and in the field "tier"): 99.5% = tier 0.99 (the first
measurement's tier labelled "C = 0.99"; its check-set gate was 99% of held-out queries), 99% = tier 0.98, 95% = tier
0.90, 90% = tier 0.80. Every row carries calibration_coverage_target and check_coverage_target (0.99 at the 99.5%
level, null at the others, which have no check-set gate).
Per (dataset, k, R): queries reaching R for fixed and early stop on the calibration and the held-out queries (raw
counts / n), mean recall loss on the held-out queries, distance computations saved, absolute QPS and mean latency of
both arms and the changes of QPS, mean latency and P99 at 1 and 8 threads (scripts/timing_clean.py: medians over
accepted batches only, accepted-batch counts shown). Only the 99.5% level carries the first measurement's held-out
check (fixed and early stop both reach R on >= 99% of the held-out queries, loss <= 0.5 pt); the other levels show
counts without a verdict.
"Meets" = mean recall loss <= 0.5 points and at least one of: QPS +10% at 1 or 8 threads, mean latency -10% at 1 or 8
threads, P99 -10% at 1 or 8 threads (the metrics that do it are listed).
dbpedia/cohere/laion: held-out and calibration quality from the first measurement's record (summary-v4.json) at the
99.5% and 95% levels, timing from this run on the current libraries; at 99.5% also the September-freeze alphas
("Sept."). Rows of the 95% and 90% levels whose rule C saves less than 8% of the distance computations were not timed;
so were those of the 99% level.
"""
import json
import math
from pathlib import Path

import config
import recalibrate as r
import timing_clean as tc

WORK = config.WORK
OUT = config.TABLES
ORDER = ['coco-i2i', 'coco-t2i', 'wiki-all', 'dbpedia', 'cohere', 'laion', 'sift', 'deep', 'glove', 't2i', 'gist']
ORIGINAL = ('dbpedia', 'cohere', 'laion')
TIERS = [(0.99, 'Fixed ef calibrated at 99.5% (check-set gate 99%; the tier labelled "C = 0.99" until 2026-11-25)'),
         (0.98, 'Fixed ef calibrated at 99%'),
         (0.90, 'Fixed ef calibrated at 95%'),
         (0.80, 'Fixed ef calibrated at 90%')]
# calibration_coverage_target per tier is recalibrate.CS; the check-set gate exists only at the 99.5% level.
CHECK = {0.99: 0.99}
RUN_OF = {0.99: 'c99', 0.98: 'lvl', 0.80: 'lvl', 0.90: 'l95'}


def read(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def timing_runs(ds, C):
    s = f'-c{int(round(C * 100))}'
    if ds in ORIGINAL and C in (0.99, 0.90):
        return [WORK / 'orig' / f'timing-{ds}{"" if C == 0.99 else s}']
    if C == 0.99:
        return [WORK / 'c99' / f'timing-{ds}{s}', WORK / 'c99' / f'timing-{ds}']
    return [WORK / RUN_OF[C] / f'timing-{ds}{s}']


def quality(ds, C):
    """[(point dict, held-out dict, {key: calibration stats})] for the tier."""
    if ds in ORIGINAL and C in (0.99, 0.90):
        summary = read(config.PACKAGE / 'results' / 'quality' / 'summary-v4.json')
        out = []
        for p in summary['points']:
            if p['dataset'] == ds and p['C'] == C:
                n = p['calibration_queries']
                cal = {'fixed': p['calibration_fixed']['reached']}
                for key, ck in [('rule_c', 'rule_c_calibration'), ('old', 'old_calibration')]:
                    if p.get(ck):
                        cal[key] = int(round(p[ck]['coverage'] * n))
                out.append((p, p['held_out'], cal, n))
        return out
    summary = read(WORK / RUN_OF[C] / f'summary-pr-{ds}.json')
    if not summary:
        return []
    out = []
    for p in summary['points']:
        if p['C'] != C:
            continue
        sel = read(WORK / RUN_OF[C] / 'quality' / 'pr' / ds / f'selection-k{p["k"]}.json')[p['point']]
        cand = {c['alpha']: c for c in sel['candidates']}
        cal = {'fixed': sel['fixed']['reached']}
        if p['rule_c_alpha'] is not None:
            cal['rule_c'] = cand[p['rule_c_alpha']]['reached']
        out.append((p, p['held_out'], cal, sel['queries']))
    return out


def meets(loss_pt, t):
    if loss_pt is None or loss_pt > 100 * r.LOSS:
        return []
    out = []
    for th in (1, 8):
        x = t.get(th)
        if not x or not x['sufficient']:
            continue
        if x['qps_pct'] >= 10:
            out.append(f'QPS {th}t')
        if x['mean_pct'] <= -10:
            out.append(f'mean {th}t')
        if x['p99_pct'] <= -10:
            out.append(f'P99 {th}t')
    return out


def rows_for(ds, C):
    rows = []
    runs = timing_runs(ds, C)
    for p, h, cal, ncal in sorted(quality(ds, C), key=lambda x: (x[0]['k'], x[0]['R'])):
        arms = [('rule C', 'rule_c', 'rulec')] + ([('Sept.', 'old', 'sept')] if ds in ORIGINAL and C == 0.99 else [])
        for label, key, arm in arms:
            e = h.get(key)
            row = dict(dataset=ds, tier=C, C_cal=r.CS[C], calibration_coverage_target=r.CS[C],
                       check_coverage_target=CHECK.get(C), k=p['k'], R=p['R'], fixed_ef=p['fixed_ef'], alpha_rule=label,
                       auto_off=p['auto_off'], n_cal=ncal, n_held=h['queries'], cal_fixed=cal['fixed'],
                       held_fixed=h['fixed']['reached'], alpha=None if e is None else e['alpha'])
            if e is not None:
                t = {th: tc.lookup(runs, p['point'], th, arm) for th in (1, 8)}
                row.update(cal_es=cal.get(key), held_es=e['reached'], loss_pt=100 * e['mean_loss'],
                           saving_pct=e['saving_pct'], timing=t)
                if C == 0.99:
                    row['package_check'] = bool(h['fixed']['reached'] >= math.ceil(0.99 * h['queries'] - 1e-9) and
                                                e['reached'] >= math.ceil(0.99 * h['queries'] - 1e-9) and
                                                e['mean_loss'] <= r.LOSS)
                row['meets'] = meets(row['loss_pt'], t)
                row['timed'] = any(t.values())
            rows.append(row)
    return rows


def pct(x):
    return '' if x is None else f'{x:+.1f}%'


def tcell(t, saving=None, tier=None):
    if not t:
        why = ' (saving < 8%, outside the timing plan)' if tier != 0.99 and saving is not None and saving < 8 else ''
        return 'not timed' + why, '', '', ''
    if not t['sufficient']:
        return f"insufficient accepted batches ({t['ref']['accepted']}/{t['arm']['accepted']})", '', '', ''
    return (f"{t['ref']['qps']:.0f} -> {t['arm']['qps']:.0f} ({pct(t['qps_pct'])})",
            f"{t['ref']['mean_ms']:.3f} -> {t['arm']['mean_ms']:.3f} ms ({pct(t['mean_pct'])})",
            pct(t['p99_pct']), f"{t['ref']['accepted']}/{t['arm']['accepted']}")


def md_row(x):
    head = f"| {x['dataset']} | {x['k']} | {x['R']:.2f} | {x['fixed_ef']} | {x['alpha_rule']} | "
    if x['alpha'] is None:
        why = 'skipped: ef <= 1.25k' if x['auto_off'] else 'no alpha qualifies'
        return head + (f"- ({why}) | {x['cal_fixed']}/{x['n_cal']} / - | {x['held_fixed']}/{x['n_held']} / - |"
                       + ' |' * 9)
    t1, t8 = tcell(x['timing'][1], x['saving_pct'], x['tier']), tcell(x['timing'][8], x['saving_pct'], x['tier'])
    verdict = ('yes: ' + ', '.join(x['meets'])) if x['meets'] else ('no' if x['timed'] else
                                                                    'no timing' if x['saving_pct'] < 8 and x['tier'] != 0.99
                                                                    else 'timing pending')
    check = '' if 'package_check' not in x else (' pass' if x['package_check'] else ' fail')
    cal_es = '' if x.get('cal_es') is None else x['cal_es']
    return head + (f"{x['alpha']:g} | {x['cal_fixed']}/{x['n_cal']} / {cal_es}/{x['n_cal']} | "
                   f"{x['held_fixed']}/{x['n_held']} / {x['held_es']}/{x['n_held']}{check} | {x['loss_pt']:.2f} pt | "
                   f"{x['saving_pct']:.1f}% | {t1[0]} | {t8[0]} | {t1[1]} | {t8[1]} | {t1[2]} / {t8[2]} | "
                   f"{t1[3]} ; {t8[3]} | {verdict} |")


HEADER = ('| dataset | k | R | fixed ef | alpha rule | alpha | calibration reaching R: fixed / ES | held-out reaching R: '
          'fixed / ES | mean recall loss | dist. comp. saved | QPS 1t: fixed -> ES | QPS 8t | mean latency 1t | '
          'mean latency 8t | P99 change 1t / 8t | accepted batches ref/ES 1t ; 8t | meets (any metric >= 10%, loss <= 0.5 pt) |')
RULE = '|---|---:|---:|---:|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|'


def main():
    OUT.mkdir(exist_ok=True)
    datasets = [d for d in ORDER if d in config.load()['datasets']]
    lines = ['# Rule C (no margin) at the fixed ef against the reference library', '',
             'PR build b98e87ab vs main 4a9c99ba; 1 thread on CPU 8, 8 threads on CPUs 8-15; four rotating batches per '
             'arm; medians over accepted batches (background CPU <= 2 cores). dbpedia/cohere/laion: quality from the '
             'first measurement\'s record, timing from this run. At the 99.5% level "pass/fail" after the held-out '
             'counts is the first measurement\'s check (both reach R on >= 99% of held-out queries, loss <= 0.5 pt); '
             'the other levels carry no verdict. Rows saving less than 8% of the distance computations at the 99%, '
             '95% and 90% levels were not timed and count as not meeting the requirement.', '']
    out = {}
    for C, title in TIERS:
        rows = [x for ds in datasets for x in rows_for(ds, C)]
        out[str(C)] = rows
        if not rows:
            continue
        counts = []
        for ds in datasets:
            mine = [x for x in rows if x['dataset'] == ds and x['alpha_rule'] == 'rule C']
            if mine:
                ok = [x for x in mine if x.get('meets')]
                counts.append(f"{ds} {len(ok)}/{len(mine)} points, {len({x['R'] for x in ok})} distinct R "
                              f"({sum(1 for x in mine if x.get('timed'))} timed)")
        lines += [f'## {title}', '', 'Points meeting the requirement with rule C: ' + '; '.join(counts) + '.', '',
                  HEADER, RULE] + [md_row(x) for x in rows] + ['']
    (OUT / 'headline.md').write_text('\n'.join(lines) + '\n')
    (OUT / 'headline.json').write_text(json.dumps(out, indent=1) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
