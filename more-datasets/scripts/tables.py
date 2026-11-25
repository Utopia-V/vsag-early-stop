#!/usr/bin/env python3
"""Tables from the quality summaries and timing summaries: tables/DS.md and tables/points.json.

usage: tables.py DS [DS ...]

Labels: a calibration level is the share of calibration queries that must reach R at the fixed ef; the scripts'
internal tier numbers map to it as 0.99 -> 99.5% (check-set gate 99%), 0.98 -> 99%, 0.95 -> 97.5% (gate 95%),
0.90 -> 95%, 0.80 -> 90%. Exported rows (points.json) carry calibration_coverage_target and check_coverage_target.
Coverage protocol (c99/, c90-c95/ under the run directory): one row per (k, R, tier) with the rule C+m alpha (margins
transferred from the first measurement); QPS and P99 changes are PR build with that alpha against the reference build
at the fixed ef (medians over accepted batches). The
default-alpha rows use the PR build with early_stop and no alpha. Diagnostics per C=0.99 point from the calibration
queries at the fixed ef: ef/k; the share of queries for which alpha 1.00 already returns the fixed search's recall;
per query, the work (distance computations) of the smallest grid alpha that returns the fixed search's recall,
relative to the fixed search's work (median and quartiles): how much earlier than the fixed search the query
already holds a result set of its final quality, along the rule's own path.
Mean-recall arm (work/mean-recall) in its own table.
"""
import json
import lzma
import sys
from pathlib import Path

import numpy as np

import config
import recalibrate as r

LEVEL = {0.99: '99.5%', 0.98: '99%', 0.95: '97.5%', 0.90: '95%', 0.80: '90%'}
GATE = {0.99: '99%', 0.95: '95%'}  # check-set gate of the first measurement's tiers in these tables
GATE_VALUE = {0.99: 0.99, 0.95: 0.95}


def level(C):
    """Calibration level, with the check-set gate where the table applies one (e.g. '99.5% / 99%')."""
    return LEVEL[C] + (f' / {GATE[C]}' if C in GATE else '')

WORK = config.WORK
OUT = config.TABLES


def read(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else None


def pct(x, d=1):
    return '' if x is None else f'{x:+.{d}f}%'


def timing_cells(summary):
    """{(point, threads): result}"""
    if not summary:
        return {}
    return {(x['point'], x['threads']): x for x in summary['results']}


def speed(runs, point, arm):
    """Changes against ref from scripts/timing_clean.py (accepted batches only); None when not timed or insufficient."""
    import timing_clean as tc
    out = {}
    for t in (1, 8):
        x = tc.lookup(runs, point, t, arm)
        out[t] = x if x and x['sufficient'] else None
    return out


def verdict(p):
    h = p['held_out']
    e = h.get('rule_cm')
    if not h['fixed']['quality_pass']:
        return 'fixed misses the check-set gate on held-out'
    if e is None:
        return 'skipped: ef <= 1.25k' if p['auto_off'] else 'no alpha qualifies on calibration (fixed)'
    if e['status'] == 'pass':
        return 'pass'
    why = []
    if e['coverage'] < p['C']:
        why.append(f"coverage {e['coverage']:.2%} < check-set gate")
    if e['mean_loss'] > r.LOSS:
        why.append(f"loss {100 * e['mean_loss']:.2f} pt > 0.5")
    return 'early stop fails: ' + ', '.join(why)


def diagnostics(ds, p):
    path = WORK / 'c99' / 'quality' / 'pr' / ds / f'calibration-k{p["k"]}.json'
    res = DIAG_CACHE.setdefault(path, read(path))
    if res is None:
        return None
    ef = p['fixed_ef']
    f = res[r.alpha_name(ef, None)]
    f_rec, f_dc = np.array(f['recalls']), np.array(f['dist_cmp'])
    recs = np.array([res[r.alpha_name(ef, a)]['recalls'] for a in r.ALPHAS])
    dcs = np.array([res[r.alpha_name(ef, a)]['dist_cmp'] for a in r.ALPHAS], dtype=float)
    ok = recs >= f_rec[None, :] - 1e-12
    first = ok.argmax(axis=0)  # smallest alpha reaching the fixed recall (alpha 2.0 or fixed always does in practice)
    reach = np.where(ok.any(axis=0), dcs[first, np.arange(len(f_rec))], f_dc) / f_dc
    return dict(ef_over_k=ef / p['k'], fixed_mean_dist_cmp=float(f_dc.mean()),
                alpha1_same_recall=float(ok[0].mean()),
                alpha1_work_ratio=float(dcs[0].mean() / f_dc.mean()),
                work_to_final_recall_median=float(np.median(reach)),
                work_to_final_recall_q25=float(np.quantile(reach, .25)),
                work_to_final_recall_q75=float(np.quantile(reach, .75)))


DIAG_CACHE = {}
UNRESOLVED = {}


def unresolved():
    """Points of the 99.5% level whose fixed search cannot reach it at ef <= 8192 on the calibration queries."""
    recs = read(WORK / 'fixed-ef' / 'fixed-ef-calibration.json') or {'points': []}
    for p in recs['points']:
        if p['C'] in (0.80, 0.90, 0.98) and p['fixed_ef'] is None:
            UNRESOLVED_LVL.setdefault(p['dataset'], []).append(f"C {p['C']:.2f} k{p['k']} R{p['R']:.2f} (fixed search "
                                                               "cannot reach C_cal at ef <= 8192)")
        if p['C'] == 0.99 and p['fixed_ef'] is None:
            last = max(p['tested'], key=lambda t: t['ef'])
            UNRESOLVED.setdefault(p['dataset'], []).append(dict(
                k=p['k'], R=p['R'], why=f"fixed search reaches R on {last['reached']} of {last['queries']} calibration "
                                        f"queries at ef {last['ef']}; calibrating at 99.5% needs "
                                        f"{int(np.ceil(0.995 * last['queries'] - 1e-9))}"))


def gap_lines(ds):
    g = read(WORK / 'gap' / f'gap-{ds}.json')
    if not g:
        return []
    lines = ['## Fixed ef vs per-query ideal width (held-out queries; distance computations)', '',
             'gap = mean distance computations at the fixed ef / mean over queries of the distance computations at the '
             "query's smallest width in {round(k 1.1^i) <= fixed ef} U {fixed ef} that reaches R; a query that no tested "
             "width up to the fixed ef brings to R is charged the fixed ef's work. Rule C recovers = (fixed work - rule C "
             'work) / (fixed work - ideal work), shown only where rule C passes its check (loss <= 0.5 pt and early stop '
             'reaching R on >= ceil(L n) held-out queries, L = 0.99 at the 99.5% level, else the calibration level).', '',
             '| k | R | calibration level | fixed ef | gap (distance computations) | rule C alpha | rule C recovers | '
             'no tested width up to the fixed ef reaches R | per-query ideal width: median / p90 / p99 |',
             '|---:|---:|---|---:|---:|---:|---:|---:|---|']
    for tag, x in sorted(g.items(), key=lambda kv: (kv[1]['k'], kv[1]['R'], -kv[1]['C'])):
        q = x['ideal_ef_quantiles']
        rc = x['rule_c']
        share = ('-' if rc is None else 'check fails' if not x['rule_c_check'] else
                 '-' if x['rule_c_recovered_share'] is None else format(x['rule_c_recovered_share'], '.0%'))
        lines.append(f"| {x['k']} | {x['R']:.2f} | {LEVEL[x['C']]} | {x['fixed_ef']} | {x['gap']:.2f} | "
                     f"{'-' if rc is None else format(rc['alpha'], 'g')} | {share} | "
                     f"{x['no_tested_width_up_to_fixed_ef_reaches_R']} of {x['queries']} | "
                     f"{q['0.5']:.0f} / {q['0.9']:.0f} / {q['0.99']:.0f} |")
    return lines + ['']


UNRESOLVED_LVL = {}


def level_lines(ds):
    """The tables of every calibration level are in headline.md (scripts/headline.py)."""
    return ['Rule C at every calibration level (99.5%, 99%, 95%, 90%): see headline.md.', '']


def free_lines(ds):
    """Free-ef arm: early stop chooses (ef, alpha) under the coverage criterion."""
    sel = read(WORK / 'freeef' / f'freeef-{ds}.json')
    if not sel:
        return []
    import timing_clean as tc
    runs = [WORK / 'freeef' / f'timing-{ds}']
    lines = ['## Pair selection (early stop picks its own ef and alpha; coverage >= the calibration level and mean loss '
             'vs the fixed baseline <= 0.5 pt on calibration, fewest distance computations; same-ef candidates included '
             "where the level's calibration results exist locally)", '',
             '| calibration level | k | R | fixed ef | chosen ef, alpha | held-out reaching R: fixed / chosen | loss | saved | '
             'same-ef rule C: alpha, coverage, loss, saved | QPS 1t / 8t | mean latency 1t / 8t | P99 1t / 8t | note |',
             '|---|---:|---:|---:|---|---|---:|---:|---|---|---|---|---|']
    for tag, p in sorted(sel.items(), key=lambda kv: (-kv[1]['level'], kv[1]['k'], kv[1]['R'])):
        c, h, rc = p.get('chosen'), p.get('held_out'), p.get('same_ef_rule_c')
        note = []
        if p.get('reason'):
            note.append(p['reason'])
        elif c is None:
            note.append('no tested setting meets coverage >= the calibration level and loss <= 0.5 pt')
        if p.get('fixed_ef_beyond_sweep'):
            note.append(f"fixed ef above the sweep's largest ef {p['sweep_max_ef']}")
        if p.get('chosen_at_sweep_edge'):
            note.append('choice at the sweep edge')
        chosen = '-' if not c else f"{c['ef']}, {'fixed' if c['alpha'] is None else format(c['alpha'], 'g')}"
        rc_cell = '-' if not rc else (f"{rc['alpha']:g}, {rc['coverage']:.2%}, {100 * rc['mean_loss']:.2f} pt, "
                                      f"{rc['saving_pct']:.1f}%")
        body = (f"{h['fixed_reached']}/{h['queries']} / {h['reached']}/{h['queries']} | {100 * h['mean_loss']:.2f} pt | "
                f"{h['saving_pct']:.1f}%") if h else ' | | '
        t = {th: tc.lookup(runs, tag, th, 'on') for th in (1, 8)}
        def cell(m):
            return ' / '.join('' if not t[th] or not t[th]['sufficient'] else pct(t[th][f'{m}_pct']) for th in (1, 8))
        lines.append(f"| {LEVEL[p['C']]} | {p['k']} | {p['R']:.2f} | {p['fixed_ef']} | {chosen} | {body} | "
                     f"{rc_cell} | {cell('qps')} | {cell('mean')} | {cell('p99')} | {'; '.join(note)} |")
    return lines + ['']


def orig_lines(ds):
    t = read(WORK / 'orig' / f'timing-summary-{ds}.json')
    if not t:
        return []
    cells = [WORK / 'orig' / f'timing-{ds}']
    summary = read(config.PACKAGE / 'results' / 'quality' / 'summary-v4.json')
    lines = ['## First measurement, fixed ef calibrated at 99.5% (check-set gate 99%): rule C alphas (no margin) and '
             'the September-freeze alphas, timed now', '',
             'Held-out quality from repro-package results/quality/summary-v4.json (not rerun); timing: current PR build '
             'against current main at the same fixed ef.', '',
             '| calibration / check | k | R | fixed ef | rule | alpha | held-out coverage fixed -> ES | loss | dist. comp. saved | QPS 1t / 8t | '
             'P99 1t / 8t |', '|---|---:|---:|---:|---|---:|---|---:|---:|---|---|']
    for p in summary['points']:
        if p['dataset'] != ds or p['C'] != 0.99:
            continue
        for rule, key, arm in [('C', 'rule_c', 'rulec'), ('Sept.', 'old', 'sept')]:
            e = p['held_out'].get(key)
            if e is None:
                continue
            sp = speed(cells, p['point'], arm)
            lines.append(f"| {level(0.99)} | {p['k']} | {p['R']:.2f} | {p['fixed_ef']} | {rule} | {e['alpha']:g} | "
                         f"{p['held_out']['fixed']['coverage']:.2%} -> {e['coverage']:.2%} | {100 * e['mean_loss']:.2f} pt | "
                         f"{e['saving_pct']:.1f}% | {pct(sp[1] and sp[1]['qps_pct'])} / {pct(sp[8] and sp[8]['qps_pct'])} | "
                         f"{pct(sp[1] and sp[1]['p99_pct'])} / {pct(sp[8] and sp[8]['p99_pct'])} |")
    return lines + ['']


def coverage_rows(ds, rundir):
    summary = read(WORK / rundir / f'summary-pr-{ds}.json')
    if summary is None:
        return []
    cells = [WORK / rundir / f'timing-{ds}', WORK / rundir / f'timing-{ds}-c99']
    rows = []
    for p in summary['points']:
        e = p['held_out'].get('rule_cm')
        on = speed(cells, p['point'], 'on')
        d = p['held_out'].get('default')
        dft = speed(cells, p['point'], 'default')
        off = speed(cells, p['point'], 'off')
        row = dict(dataset=ds, k=p['k'], R=p['R'], C=p['C'], calibration_coverage_target=r.CS[p['C']],
                   check_coverage_target=GATE_VALUE.get(p['C']), point=p['point'], fixed_ef=p['fixed_ef'],
                   alpha=None if e is None else e['alpha'], rule_c_alpha=p['rule_c_alpha'],
                   held_out_queries=p['held_out']['queries'], calibration_queries=p['calibration_queries'],
                   coverage_fixed=p['held_out']['fixed']['coverage'],
                   coverage_es=None if e is None else e['coverage'],
                   mean_loss_pt=None if e is None else 100 * e['mean_loss'],
                   saving_pct=None if e is None else e['saving_pct'],
                   qps_pct={t: None if on[t] is None else on[t]['qps_pct'] for t in on},
                   p99_pct={t: None if on[t] is None else on[t]['p99_pct'] for t in on},
                   mean_latency_pct={t: None if on[t] is None else on[t]['mean_pct'] for t in on},
                   verdict=verdict(p),
                   default=None if d is None else dict(
                       alpha=d['alpha'], coverage=d['coverage'], mean_loss_pt=100 * d['mean_loss'],
                       saving_pct=d['saving_pct'], status=d['status'],
                       qps_pct={t: None if dft[t] is None else dft[t]['qps_pct'] for t in dft},
                       p99_pct={t: None if dft[t] is None else dft[t]['p99_pct'] for t in dft}),
                   off_qps_pct={t: None if off[t] is None else off[t]['qps_pct'] for t in off},
                   )
        row['gain10_both'] = (row['verdict'] == 'pass' and all(v is not None and v >= 10 for v in row['qps_pct'].values()))
        if p['C'] == 0.99:
            need = int(np.ceil(p['C'] * p['held_out']['queries'] - 1e-9))
            row['need_reached'] = need
            row['fixed_reached'] = p['held_out']['fixed']['reached']
            rules = {}
            for rule, key, arm in [('C', 'rule_c', 'rulec'), ('C+m 0.10', 'rule_m10', 'm10'), ('C+m 0.25', 'rule_cm', 'on')]:
                e = p['held_out'].get(key)
                sp = speed(cells, p['point'], arm)
                if e is None:
                    rules[rule] = None
                    continue
                passed = bool(p['held_out']['fixed']['quality_pass'] and e['coverage'] >= p['C'] and e['mean_loss'] <= r.LOSS)
                rules[rule] = dict(alpha=e['alpha'], coverage=e['coverage'], reached=e['reached'],
                                   added_failures=row['fixed_reached'] - e['reached'],
                                   short_of_C_by=max(0, need - e['reached']), mean_loss_pt=100 * e['mean_loss'],
                                   saving_pct=e['saving_pct'], passed=passed,
                                   qps_pct={t: None if sp[t] is None else sp[t]['qps_pct'] for t in sp},
                                   p99_pct={t: None if sp[t] is None else sp[t]['p99_pct'] for t in sp})
                rules[rule]['gain10_both'] = passed and all(v is not None and v >= 10 for v in rules[rule]['qps_pct'].values())
            row['rules'] = rules
        if p['C'] == 0.99:
            row['diagnostics'] = diagnostics(ds, p)
        rows.append(row)
    return rows


def mean_recall_rows(ds):
    sel = read(WORK / 'mean-recall' / f'meanrecall-{ds}.json')
    if sel is None:
        return []
    cells = [WORK / 'mean-recall' / f'timing-{ds}']
    rows = []
    for t, p in sorted(sel.items(), key=lambda x: (x[1]['k'], x[1]['T'])):
        h = p.get('held_out')
        on = speed(cells, t, 'on')
        c = p['chosen']
        rows.append(dict(dataset=ds, point=t, k=p['k'], T=p['T'], fixed_ef=p['fixed_ef'],
                         ef=None if c is None else c['ef'], alpha=None if c is None else c['alpha'],
                         calibration_saving_pct=None if c is None else c['saving_pct'],
                         best_saving_pct=None if p['best'] is None else p['best']['saving_pct'],
                         best=p['best'], auto_off_at_fixed_ef=p['auto_off_at_fixed_ef'], status=p['status'],
                         held_out=h,
                         qps_pct={x: None if on[x] is None else on[x]['qps_pct'] for x in on},
                         p99_pct={x: None if on[x] is None else on[x]['p99_pct'] for x in on}))
    return rows


def manifest(ds):
    """The dataset's input manifest: the one prepare.py wrote, else the frozen copy shipped with the package."""
    m = read(config.load()['inputs'] / ds / 'manifest.json')
    frozen = config.MANIFESTS / ds / 'manifest.json.xz'
    if m is None and frozen.exists():
        m = json.loads(lzma.decompress(frozen.read_bytes()))
    return m


def f2(x, fmt):
    return '' if x is None else format(x, fmt)


def markdown(ds, cov, mr):
    label = config.load()['datasets'][ds]['label']
    lines = [f'# {label}', '']
    m = manifest(ds)
    if m:
        roles = m['queries']['rows']
        n_cal, n_val = len(roles['calibration']), len(roles['validation'])
        lines += [f"Base {m['base']['shape'][0]} x {m['base']['shape'][1]}, metric {m['metric']}; queries: "
                  f"{m['queries']['source_rows']} in the source, {m['queries']['unique']} unique, {n_cal} calibration / "
                  f"{n_val} held-out." + (' Fewer than 200 held-out queries: a 99% check-set gate allows at most '
                                          f'{n_val - int(np.ceil(0.99 * n_val - 1e-9))} held-out misses and is poorly resolved.'
                                          if n_val < 200 else ''), '']
    for C in (0.99, 0.95, 0.90):
        sel = [x for x in cov if x['C'] == C]
        if not sel:
            continue
        lines += [f'## Coverage protocol, fixed ef calibrated at {LEVEL[C]}' +
                  (f', check-set gate {GATE[C]}' if C in GATE else '') + ', rule C+m', '',
                  '| dataset | calibration / check | k | R | fixed ef | alpha (rule C) | coverage fixed -> ES | mean recall loss | '
                  'dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out | >=10% QPS both |',
                  '|---|---|---:|---:|---:|---|---|---:|---:|---|---|---|---|']
        for x in sel:
            a = '-' if x['alpha'] is None else f"{x['alpha']:g} ({x['rule_c_alpha']:g})"
            cov_cell = (f"{x['coverage_fixed']:.2%}" if x['coverage_es'] is None else
                        f"{x['coverage_fixed']:.2%} -> {x['coverage_es']:.2%}")
            lines.append(f"| {ds} | {level(x['C'])} | {x['k']} | {x['R']:.2f} | {x['fixed_ef']} | {a} | {cov_cell} | "
                         f"{f2(x['mean_loss_pt'], '.2f')}{'' if x['mean_loss_pt'] is None else ' pt'} | "
                         f"{f2(x['saving_pct'], '.1f')}{'' if x['saving_pct'] is None else '%'} | "
                         f"{pct(x['qps_pct'][1])} / {pct(x['qps_pct'][8])} | {pct(x['p99_pct'][1])} / {pct(x['p99_pct'][8])} | "
                         f"{x['verdict']} | {'yes' if x['gain10_both'] else 'no'} |")
        lines.append('')
        if C == 0.99:
            lines += ['### Calibrated at 99.5% (check-set gate 99%), by alpha rule (rule C, C+m with m = 0.10, C+m with '
                      'm = 0.25)', '',
                      '| calibration / check | k | R | fixed ef | rule | alpha | coverage fixed -> ES | added failures | mean recall loss | '
                      'dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | held-out |',
                      '|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|---|']
            for x in sel:
                for rule, e in (x.get('rules') or {}).items():
                    if e is None:
                        lines.append(f"| {level(0.99)} | {x['k']} | {x['R']:.2f} | {x['fixed_ef']} | {rule} | - | | | | | | | {x['verdict']} |")
                        continue
                    status = 'pass' if e['passed'] else (
                        'fixed misses the gate' if x['verdict'] == 'fixed misses the check-set gate on held-out' else
                        'fails' + (f", {e['short_of_C_by']} queries short of the gate" if e['short_of_C_by'] else '') +
                        (', loss > 0.5 pt' if e['mean_loss_pt'] > 100 * r.LOSS else ''))
                    lines.append(f"| {level(0.99)} | {x['k']} | {x['R']:.2f} | {x['fixed_ef']} | {rule} | {e['alpha']:g} | "
                                 f"{x['coverage_fixed']:.2%} -> {e['coverage']:.2%} | {e['added_failures']} | "
                                 f"{e['mean_loss_pt']:.2f} pt | {e['saving_pct']:.1f}% | {pct(e['qps_pct'][1])} / "
                                 f"{pct(e['qps_pct'][8])} | {pct(e['p99_pct'][1])} / {pct(e['p99_pct'][8])} | {status} |")
            lines += ['', '| calibration / check | rule | points evaluated | pass | pass with >=10% QPS at 1t and 8t | failing points (queries short of the gate) |',
                      '|---|---|---:|---:|---:|---|']
            for rule in ['C', 'C+m 0.10', 'C+m 0.25']:
                ev = [x for x in sel if (x.get('rules') or {}).get(rule)]
                fails = [f"k{x['k']} R{x['R']:.2f} ({x['rules'][rule]['short_of_C_by']}"
                         f"{', loss ' + format(x['rules'][rule]['mean_loss_pt'], '.2f') + ' pt' if x['rules'][rule]['mean_loss_pt'] > 100 * r.LOSS else ''})"
                         for x in ev if not x['rules'][rule]['passed'] and x['verdict'] != 'fixed misses the check-set gate on held-out']
                lines.append(f"| {level(0.99)} | {rule} | {len(ev)} | {sum(x['rules'][rule]['passed'] for x in ev)} | "
                             f"{sum(x['rules'][rule]['gain10_both'] for x in ev)} | {', '.join(fails) or '-'} |")
            lines += ['', 'Points not evaluated: ' + (', '.join(f"k{u['k']} R{u['R']:.2f} ({u['why']})" for u in UNRESOLVED.get(ds, []))
                                                    or 'none') + '.', '']
            lines += ['### Default alpha (early_stop without alpha: 1.5 at k = 10, 1.15 at k = 100), calibrated at '
                      '99.5% (check-set gate 99%)', '',
                      '| calibration / check | k | R | fixed ef | alpha | coverage fixed -> default | mean recall loss | dist. comp. saved | '
                      'held-out | QPS 1t / 8t | P99 1t / 8t |', '|---|---:|---:|---:|---:|---|---:|---:|---|---|---|']
            for x in sel:
                d = x['default']
                if d is None:
                    lines.append(f"| {level(0.99)} | {x['k']} | {x['R']:.2f} | {x['fixed_ef']} | - | skipped (ef <= 1.25k) | | | | | |")
                    continue
                lines.append(f"| {level(0.99)} | {x['k']} | {x['R']:.2f} | {x['fixed_ef']} | {d['alpha']:g} | {x['coverage_fixed']:.2%} -> "
                             f"{d['coverage']:.2%} | {d['mean_loss_pt']:.2f} pt | {d['saving_pct']:.1f}% | {d['status']} | "
                             f"{pct(d['qps_pct'][1])} / {pct(d['qps_pct'][8])} | {pct(d['p99_pct'][1])} / {pct(d['p99_pct'][8])} |")
            offs = [x for x in sel if any(v is not None for v in x['off_qps_pct'].values())]
            if offs:
                lines += ['', '| PR build without early_stop vs reference (fixed ef calibrated at 99.5%), QPS | 1t | 8t |',
                      '|---|---:|---:|']
                for x in offs:
                    lines.append(f"| k{x['k']} R{x['R']:.2f} ef {x['fixed_ef']} | {pct(x['off_qps_pct'][1])} | "
                                 f"{pct(x['off_qps_pct'][8])} |")
            lines += ['', '### Diagnostics on the calibration queries at the fixed ef, calibrated at 99.5%', '',
                      '| calibration / check | k | R | ef / k | fixed mean dist. comp. | queries with final recall at alpha 1.00 | work at alpha 1.00 / '
                      'fixed | per-query work to final recall / fixed: median (q25-q75) |', '|---|---:|---:|---:|---:|---:|---:|---|']
            for x in sel:
                g = x.get('diagnostics')
                if g:
                    lines.append(f"| {level(0.99)} | {x['k']} | {x['R']:.2f} | {g['ef_over_k']:.2f} | {g['fixed_mean_dist_cmp']:.0f} | "
                                 f"{g['alpha1_same_recall']:.1%} | {g['alpha1_work_ratio']:.2f} | "
                                 f"{g['work_to_final_recall_median']:.2f} ({g['work_to_final_recall_q25']:.2f}-"
                                 f"{g['work_to_final_recall_q75']:.2f}) |")
            lines.append('')
    lines += level_lines(ds) + free_lines(ds) + gap_lines(ds) + orig_lines(ds)
    if mr:
        lines += ['## Mean-recall arm (not the coverage protocol)', '',
                  '| k | mean-recall target T | fixed ef | chosen ef, alpha | cal. saving (best) | held-out mean recall fixed '
                  '(SE) | early stop (SE) | loss | dist. comp. saved | QPS 1t / 8t | P99 1t / 8t | relative check (ES >= '
                  'fixed - 0.5 pt) | held-out mean >= T: fixed / ES |',
                  '|---:|---:|---:|---|---|---|---|---:|---:|---|---|---|---|']
        for x in mr:
            h = x['held_out'] or {}
            fx = h.get('fixed')
            es = h.get('early_stop')
            best = '' if x['best_saving_pct'] is None else f"{x['best_saving_pct']:.1f}%"
            chosen = 'no early stop' if x['ef'] is None else f"{x['ef']}, {x['alpha']:g}"
            lines.append(
                f"| {x['k']} | {x['T']:.2f} | {x['fixed_ef']} | "
                f"{chosen} | "
                f"{'' if x['calibration_saving_pct'] is None else format(x['calibration_saving_pct'], '.1f') + '%'} ({best}) | "
                f"{'' if fx is None else format(fx['mean_recall'], '.4f') + ' (' + format(fx['se'], '.4f') + ')'} | "
                f"{'' if es is None else format(es['mean_recall'], '.4f') + ' (' + format(es['se'], '.4f') + ')'} | "
                f"{'' if es is None else format(100 * es['loss'], '.2f') + ' pt'} | "
                f"{'' if es is None else format(es['saving_pct'], '.1f') + '%'} | "
                f"{pct(x['qps_pct'][1])} / {pct(x['qps_pct'][8])} | {pct(x['p99_pct'][1])} / {pct(x['p99_pct'][8])} | "
                f"{'' if es is None else ('pass' if h['pass'] else 'fails')} | "
                f"{'' if fx is None else ('yes' if fx['mean_recall'] >= x['T'] else 'no')} / "
                f"{'' if es is None else ('yes' if es['mean_recall'] >= x['T'] else 'no')} |")
        lines.append('')
    return '\n'.join(lines) + '\n'


def main():
    OUT.mkdir(exist_ok=True)
    unresolved()
    allpoints = read(OUT / 'points.json') or {}
    for ds in sys.argv[1:]:
        cov = coverage_rows(ds, 'c99') + coverage_rows(ds, 'c90-c95')
        mr = mean_recall_rows(ds)
        (OUT / f'{ds}.md').write_text(markdown(ds, cov, mr))
        allpoints[ds] = dict(coverage=cov, mean_recall=mr)
        print((OUT / f'{ds}.md').read_text())
    (OUT / 'points.json').write_text(json.dumps(allpoints, indent=1) + '\n')


if __name__ == '__main__':
    main()
