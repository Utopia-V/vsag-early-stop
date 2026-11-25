#!/usr/bin/env python3
"""Alpha recalibration for HGraph distance early stop (2026-10-22).

Re-selects alpha on the 18 FP32 points (DBpedia, Cohere, LAION; k=10/100; R=0.80/0.90/0.95) at query coverage
C = 0.90 / 0.95 / 0.99 with the rule approved on 2026-10-22, then checks every candidate configuration on the held-out
queries and, for DBpedia, on 2048 fresh queries (used once before, only at k100/R95).

Ten-dataset copy (more-datasets/scripts/; provenance/more-datasets/recalibrate.py.diff lists the changes against the copy
the run used), generalised from scripts/recalibrate.py: datasets come
from the registry in config.toml (dimension, metric); recall uses the library's squared L2 for l2 datasets and angular
distance for cosine ones; RECAL_TIERS restricts the coverage tiers of one run directory (RECAL_RUN); quality processes
take CPUs from RECAL_CPUS / config; default-check and timing take dataset names; timing writes one directory per
dataset; the Markdown report of the original is replaced by scripts/tables.py. Every selection and verdict rule below
is unchanged. Tier numbers are internal names: tier 0.99 calibrates the fixed ef at 99.5% (C_cal) and checks held-out
coverage against 0.99; tiers 0.98 / 0.90 / 0.80 calibrate at 99% / 95% / 90%, and their held-out "quality_pass" and
"status" fields compare against the tier number itself (0.98 / 0.90 / 0.80), not a calibration level: no table uses
them (headline.py prints counts without a verdict at these levels).

Reproduction-package version: the script that produced the delivered quality and timing numbers, with the paths of
the original machine replaced by config.toml (scripts/config.py). The phases that installed libraries into the
original run directory (prepare, add-lib) and recorded the amendment (amend) are replaced by scripts/build_vsag.py and
the frozen protocol in frozen/protocol.json. provenance/recalibrate.diff lists every change.

Protocol (frozen/protocol.json, written before any selection):
- C_cal = (1+C)/2. Fixed ef per point and tier is reused from earlier calibrations on the same calibration queries:
  C=0.99 from runs/final-validation-20260912 (calibrated in runs/final-development-20260911), C=0.90/0.95 from
  runs/early-stop-v3-coverage-c90-c95-20261013. Fixed is re-run at that ef to get per-query recalls.
- Alpha grid: 1.00-1.30 step 0.01, 1.32-1.60 step 0.02, 1.65 1.70 1.75 1.80 1.85 1.90 2.00, plus the old grid values
  1.225 and 1.31875 so that the earlier choices are measured on the same data.
- Rule C (selected): on the calibration queries at the fixed ef, the alpha with the fewest mean distance computations
  such that it and every larger grid alpha satisfy (a) coverage >= C_cal and (b) mean paired recall loss vs fixed plus
  two standard errors <= 0.5 points (per-query loss = fixed recall - alpha recall on the same query; SE = sample sd /
  sqrt(n)). Ties: larger alpha. If ef <= 1.25 k the point stays fixed (the rebased library skips early stop there).
  If no alpha qualifies, fixed.
- Comparison only: rule B = rule C without the two-SE margin; old = the alpha recorded by the earlier campaigns;
  default = 1.5 at k=10, 1.15 at k=100 (the rebased library's default; skipped where ef <= 1.25 k).
- Held-out check: a configuration passes when fixed reaches C and the early-stop configuration reaches C with mean
  recall loss <= 0.5 points.
- Recall: distance-based, as in the earlier campaigns (an ID is a hit when its exact angular distance is within 2e-6 of
  the k-th true neighbour's).

Amendment (2026-10-22, after the first held-out run): rule C+m = smallest grid alpha >= 1 + (alpha_C - 1)(1 + m),
m = 0.05 at C=0.90/0.95 and 0.25 at C=0.99, chosen by cross-validation on the calibration queries (cv_margin.py).

usage: recalibrate.py [--lib ROLE] alpha [ds ...] | validate [ds ...] | fresh | validate-cm [ds ...] | fresh-cm |
                      default-check | compare-libs ROLE_A ROLE_B | timing [CANDIDATE REFERENCE] [--force] |
                      timing-report | report
"""
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time

import h5py
import numpy as np

import config

CFG = config.load()
RUN = Path(os.environ.get('RECAL_RUN', CFG['run']))
NATIVE_RECALL = CFG['native_recall']
FIXED_POINTS = CFG['fixed_points']
DATASETS = CFG['datasets']
TIERS = CFG['tiers']
KS = [10, 100]
RS = [0.80, 0.90, 0.95]
# 0.80 and 0.98 (C_cal 0.90 and 0.99) were added in this run: calibration levels 0.90 / 0.99 in the mentor's terms.
CS = {0.80: 0.90, 0.90: 0.95, 0.95: 0.975, 0.98: 0.99, 0.99: 0.995}
LOSS = 0.005
Z = 2.0
AUTO_OFF_RATIO = 1.25
DEFAULT_ALPHA = {10: 1.5, 100: 1.15}
# Amendment (2026-10-22, after the first held-out run): rule C+m puts a margin on top of the rule C alpha. m was chosen
# by cross-validation on the calibration queries only (scripts/cv_margin.py); see protocol.json "amendments".
MARGIN = CFG['margins']
QUALITY_CPUS = CFG['quality_cpus']
THREADS = CFG['timing_threads']
AFFINITY = CFG['timing_affinity']
REPEATS = 4
ORDERS = [['ref', 'on'], ['on', 'ref'], ['ref', 'on'], ['on', 'ref']]
ENV = {'OPENBLAS_NUM_THREADS': '1'}
TIMING_ENV = {'OPENBLAS_NUM_THREADS': '1', 'OMP_PROC_BIND': 'close', 'OMP_PLACES': 'cores'}


def make_grid():
    values = [round(1.0 + 0.01 * i, 2) for i in range(31)]
    values += [round(1.32 + 0.02 * i, 2) for i in range(15)]
    values += [1.65, 1.70, 1.75, 1.80, 1.85, 1.90, 2.00, 1.225, 1.31875]
    values = sorted(set(values))
    native = [struct.unpack('<f', struct.pack('<f', v))[0] for v in values]
    assert len(set(native)) == len(native), 'float32-equivalent alphas in the grid'
    return values


ALPHAS = make_grid()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def label(k, R, C=None):
    return (f'c{int(round(C * 100))}-' if C is not None else '') + f'k{k}-r{int(round(R * 100))}'


def create_path(ds, k):
    return DATASETS[ds]['create']  # the same create parameters at k=10 and k=100


def qdir(lib, ds):
    return RUN / 'quality' / lib / ds


def params(ef, a):
    if a is None:
        return {'hgraph': {'ef_search': ef}}
    return {'hgraph': {'ef_search': ef, 'early_stop': {'type': 'distance', 'alpha': a}}}


def alpha_name(ef, a):
    return f'ef{ef}-fixed' if a is None else f'ef{ef}-a{a:.5f}'


def fixed_points():
    """{(ds, k, R, C): ef, its source, and the alpha chosen for that point by the earlier campaign}.

    Read from the frozen fixed-points.json (or the output of calibrate_ef.py, see config.toml [selection])."""
    out = {}
    for p in read(FIXED_POINTS):
        if p['ef'] is None:  # fixed search cannot reach C_cal at ef <= 8192 (calibrate_ef.py): not evaluated
            continue
        out[(p['dataset'], p['k'], round(p['R'], 2), p['C'])] = dict(
            ef=p['ef'], ef_source=p['ef_source'], old_alpha=p['old_alpha'], old_rule=p['old_rule'])
    out = {key: v for key, v in out.items() if key[0] in DATASETS and key[1] in KS and key[3] in TIERS}
    for ds in {key[0] for key in out}:
        assert sum(key[0] == ds for key in out) <= len(KS) * len(RS) * len(TIERS), ds
    return out


def library_dir(role):
    """Directory holding libvsag.so of a library role (config.toml [libraries.ROLE])."""
    return CFG['libraries'][role]['lib']


def helper(role, name):
    path = CFG['libraries'][role]['helpers'] / name
    assert path.exists(), f'no {name} helper for library {role} (run scripts/build_vsag.py)'
    return path


class Truth:
    def __init__(self, path, metric):
        with h5py.File(path, 'r') as f:
            self.queries = np.ascontiguousarray(f['test'][:], dtype=np.float32)
            self.gt = f['neighbors'][:]
            self.base = np.ascontiguousarray(f['train'][:], dtype=np.float32)
        # cosine: angular distance as in the package; l2: the library's squared L2 (its L2 metric is squared).
        lib = ctypes.CDLL(str(NATIVE_RECALL))
        native = lib.angular_distances if metric == 'cosine' else lib.l2sqr_distances
        native.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_uint64] * 2 + [ctypes.c_void_p]
        native.restype = None
        self.native = native
        self.thresholds = {}
        self.cache = {}  # many alphas return the same result list for a query; recall depends only on (query, IDs)

    def distances(self, qi, ids):
        query = self.queries[qi]
        ids = np.ascontiguousarray(ids, dtype=np.int64)
        result = np.empty(len(ids), dtype=np.float32)
        self.native(self.base.ctypes.data, query.ctypes.data, ids.ctypes.data, len(ids), len(query), result.ctypes.data)
        return result.astype(np.float64)

    def threshold(self, qi, k):
        key = (qi, k)
        if key not in self.thresholds:
            self.thresholds[key] = float(max(self.distances(qi, self.gt[qi, :k])))
        return self.thresholds[key]

    def recall(self, qi, k, ids):
        if len(ids) == 0:
            return 0.0
        key = (qi, k, ids.tobytes())
        if key not in self.cache:
            self.cache[key] = int(np.count_nonzero(self.distances(qi, ids) <= self.threshold(qi, k) + 2e-6)) / k
        return self.cache[key]


def parse(path):
    raw = Path(path).read_bytes()
    n, k, dim = struct.unpack_from('<3Q', raw, 0)
    offset = 24
    rows = []
    for _ in range(n):
        count, dist_cmp, hops, stops, reorder = struct.unpack_from('<5Q', raw, offset)
        offset += 40
        ids = np.frombuffer(raw, dtype='<i8', count=count, offset=offset).copy()
        offset += 12 * count
        rows.append((ids, dist_cmp, stops))
    assert offset == len(raw)
    return rows


def run_modes(ds, role, k, modes, tag, lib):
    """modes: {name: (params, cost)}; split over single-threaded processes (one CPU each, nice 19). {name: rows}."""
    d = DATASETS[ds]
    folder = qdir(lib, ds) / role / tag
    folder.mkdir(parents=True, exist_ok=False)
    for name, (p, _) in modes.items():
        save(folder / 'params' / f'{name}.json', p)
    chunks = [[] for _ in range(min(d['processes'], len(modes)))]
    loads = [0.0] * len(chunks)
    for name, (_, cost) in sorted(modes.items(), key=lambda item: -item[1][1]):
        i = int(np.argmin(loads))
        chunks[i].append(name)
        loads[i] += cost
    env = dict(os.environ, **ENV)
    env['LD_LIBRARY_PATH'] = str(library_dir(lib))
    for key in ['OMP_PROC_BIND', 'OMP_PLACES']:
        env.pop(key, None)
    processes = []
    for i, names in enumerate(chunks):
        plan = folder / f'plan-{i}.txt'
        plan.write_text(''.join(f'{n} {folder / "params" / (n + ".json")}\n' for n in names))
        log = (folder / f'run-{i}.log').open('w')
        command = ['nice', '-n', '19', 'taskset', '-c', str(QUALITY_CPUS[i % len(QUALITY_CPUS)]),
                   str(helper(lib, 'multi_signature')),
                   str(d['index']), str(d[role]), str(create_path(ds, k)), str(plan), str(folder / 'out'), str(k)]
        processes.append((subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT), log, command))
    for process, log, command in processes:
        code = process.wait()
        log.close()
        if code:
            raise RuntimeError(f'{command} exited with {code}')
    return {name: parse(folder / 'out' / f'{name}.bin') for name in modes}


def summarize(truth, k, rows):
    recalls = np.array([truth.recall(i, k, ids) for i, (ids, _, _) in enumerate(rows)])
    dist = np.array([dc for _, dc, _ in rows], dtype=np.float64)
    stops = int(sum(s for _, _, s in rows))
    return recalls, dist, stops


def coverage(recalls, R):
    return float(np.mean(recalls >= R - 1e-12))


def store(path, results):
    save(path, {name: dict(recalls=r.tolist(), dist_cmp=d.tolist(), stops=s) for name, (r, d, s) in results.items()})


def load(path):
    return {name: (np.array(v['recalls']), np.array(v['dist_cmp']), v['stops']) for name, v in read(path).items()}


def stats(f_rec, f_dc, rec, dc, stops, R):
    loss = f_rec - rec
    n = len(loss)
    mean = float(loss.mean())
    se = float(loss.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    return dict(coverage=coverage(rec, R), reached=int(np.sum(rec >= R - 1e-12)), mean_recall=float(rec.mean()),
                mean_loss=mean, se=se, loss_ub=mean + Z * se, mean_dist_cmp=float(dc.mean()),
                saving_pct=100 * (1 - float(dc.mean()) / float(f_dc.mean())), stops=stops)


def fixed_stats(f_rec, f_dc, R):
    return dict(coverage=coverage(f_rec, R), reached=int(np.sum(f_rec >= R - 1e-12)), mean_recall=float(f_rec.mean()),
                mean_dist_cmp=float(f_dc.mean()))


def select(results, ds, k, R, C, point):
    cal, ef = CS[C], point['ef']
    f_rec, f_dc, _ = results[alpha_name(ef, None)]
    candidates = []
    for a in ALPHAS:
        rec, dc, stops = results[alpha_name(ef, a)]
        s = stats(f_rec, f_dc, rec, dc, stops, R)
        s.update(alpha=a, qualifies_c=bool(s['coverage'] >= cal and s['loss_ub'] <= LOSS),
                 qualifies_b=bool(s['coverage'] >= cal and s['mean_loss'] <= LOSS))
        candidates.append(s)
    auto_off = ef <= AUTO_OFF_RATIO * k

    def pick(key):
        if auto_off:
            return None
        eligible = [c for i, c in enumerate(candidates) if all(x[key] for x in candidates[i:])]
        return min(eligible, key=lambda c: (c['mean_dist_cmp'], -c['alpha']))['alpha'] if eligible else None

    # Per query, a larger alpha only stops the same traversal later, so recall and work must not decrease with alpha
    # and no alpha can beat fixed. Count violations instead of assuming it.
    order = [results[alpha_name(ef, a)] for a in ALPHAS]
    recall_drops = sum(int(np.sum(nxt[0] < cur[0] - 1e-12)) for cur, nxt in zip(order, order[1:]))
    work_drops = sum(int(np.sum(nxt[1] < cur[1])) for cur, nxt in zip(order, order[1:]))
    above_fixed = sum(int(np.sum(r[0] > f_rec + 1e-12)) for r in order)
    cov = [c['coverage'] for c in candidates]
    loss = [c['mean_loss'] for c in candidates]
    return dict(dataset=ds, k=k, R=R, C=C, C_cal=cal, fixed_ef=ef, ef_source=point['ef_source'], auto_off=auto_off,
                queries=len(f_rec), fixed=fixed_stats(f_rec, f_dc, R), candidates=candidates,
                rule_c=pick('qualifies_c'), rule_b=pick('qualifies_b'), old_alpha=point['old_alpha'],
                old_rule=point['old_rule'], default_alpha=None if auto_off else DEFAULT_ALPHA[k],
                monotone=dict(per_query_recall_drops=recall_drops, per_query_work_drops=work_drops,
                              per_query_above_fixed=above_fixed,
                              coverage_drops=sum(b < a - 1e-12 for a, b in zip(cov, cov[1:])),
                              mean_loss_rises=sum(b > a + 1e-12 for a, b in zip(loss, loss[1:]))))


def alpha(ds, lib):
    truth = Truth(DATASETS[ds]['calibration'], DATASETS[ds]['metric'])
    points = fixed_points()
    for k in KS:
        mine = {key: v for key, v in points.items() if key[0] == ds and key[1] == k}
        modes = {}
        for ef in sorted({v['ef'] for v in mine.values()}):
            modes[alpha_name(ef, None)] = (params(ef, None), ef)
            for a in ALPHAS:
                modes[alpha_name(ef, a)] = (params(ef, a), ef)
        t0 = time.monotonic()
        rows = run_modes(ds, 'calibration', k, modes, f'k{k}-alpha', lib)
        print(ds, k, 'searched', len(modes), 'modes', f'{time.monotonic() - t0:.0f}s', flush=True)
        results = {name: summarize(truth, k, r) for name, r in rows.items()}
        store(qdir(lib, ds) / f'calibration-k{k}.json', results)
        selection = {}
        for (_, _, R, C), point in sorted(mine.items()):
            s = select(results, ds, k, R, C, point)
            selection[label(k, R, C)] = s
            print(ds, label(k, R, C), 'ef', s['fixed_ef'], 'C', s['rule_c'], 'B', s['rule_b'], 'old', s['old_alpha'],
                  'monotone', s['monotone'], flush=True)
        save(qdir(lib, ds) / f'selection-k{k}.json', selection)


ARMS = ['rule_c', 'rule_b', 'old', 'default']  # measured by the first held-out run (validate / fresh)
REPORT_ARMS = ['rule_c', 'rule_cm', 'rule_b', 'old', 'default']


def rule_cm(alpha_c, C):
    """Rule C+m: smallest grid alpha >= 1 + (alpha_C - 1)(1 + m); points fixed or auto-off under rule C stay so."""
    if alpha_c is None:
        return None
    target = 1 + (alpha_c - 1) * (1 + MARGIN.get(C, 0.0))  # tiers 0.80/0.98 have no margin (rule C only)
    return next((a for a in ALPHAS if a >= target - 1e-9), ALPHAS[-1])


def arm_alpha(s, arm):
    if arm == 'rule_cm':
        return rule_cm(s['rule_c'], s['C'])
    return s['old_alpha'] if arm == 'old' else s['default_alpha'] if arm == 'default' else s[arm]


def validate(ds, lib, role='validation'):
    truth = Truth(DATASETS[ds][role], DATASETS[ds]['metric'])
    for k in KS:
        selection = read(qdir(lib, ds) / f'selection-k{k}.json')
        modes = {}
        for s in selection.values():
            ef = s['fixed_ef']
            modes[alpha_name(ef, None)] = (params(ef, None), ef)
            for arm in ARMS:
                a = arm_alpha(s, arm)
                if a is not None:
                    modes[alpha_name(ef, a)] = (params(ef, a), ef)
        rows = run_modes(ds, role, k, modes, f'k{k}-{role}', lib)
        results = {name: summarize(truth, k, r) for name, r in rows.items()}
        store(qdir(lib, ds) / f'{role}-k{k}.json', results)
        save(qdir(lib, ds) / f'{role}-result-k{k}.json', held_out(ds, k, role, selection, results))


def held_out(ds, k, role, selection, results):
    """Per-point held-out verdicts from per-query results (validate; also used by check_results.py)."""
    out = {}
    for tag, s in selection.items():
        ef, R, C = s['fixed_ef'], s['R'], s['C']
        f_rec, f_dc, _ = results[alpha_name(ef, None)]
        entry = dict(dataset=ds, k=k, R=R, C=C, fixed_ef=ef, queries=len(f_rec), auto_off=s['auto_off'],
                     fixed=fixed_stats(f_rec, f_dc, R))
        entry['fixed']['quality_pass'] = bool(entry['fixed']['coverage'] >= C)
        for arm in ARMS:
            a = arm_alpha(s, arm)
            if a is None:
                entry[arm] = None
                continue
            rec, dc, stops = results[alpha_name(ef, a)]
            e = stats(f_rec, f_dc, rec, dc, stops, R)
            e.update(alpha=a, quality_pass=bool(e['coverage'] >= C and e['mean_loss'] <= LOSS))
            e['status'] = ('fixed_fails' if not entry['fixed']['quality_pass'] else
                           'pass' if e['quality_pass'] else 'early_stop_fails')
            entry[arm] = e
        c = entry['rule_c']
        entry['status'] = ('fixed_fails' if not entry['fixed']['quality_pass'] else
                           ('fixed_auto_off' if s['auto_off'] else 'fixed_fallback') if c is None else
                           'adaptive_pass' if c['quality_pass'] else 'early_stop_fails')
        out[tag] = entry
        print(ds, role, tag, entry['status'], round(entry['fixed']['coverage'], 4),
              None if c is None else (c['alpha'], round(c['coverage'], 4), round(100 * c['mean_loss'], 3),
                                      round(c['saving_pct'], 1)), flush=True)
    return out


def validate_cm(ds, lib, role='validation', suffix='cm'):
    """Amendment run: held-out check of the rule C+m alphas. Fixed per-query results come from the first run on the
    same queries; a mode that the first run already measured must reproduce it exactly.
    suffix 'm10' (this run, C=0.99 only): the same with m = 0.10 instead of the configured margin."""
    truth = Truth(DATASETS[ds][role], DATASETS[ds]['metric'])
    for k in KS:
        selection = read(qdir(lib, ds) / f'selection-k{k}.json')
        base = load(qdir(lib, ds) / f'{role}-k{k}.json')
        chosen, modes = cm_choice(selection)
        save(qdir(lib, ds) / f'selection-{suffix}-k{k}.json', chosen)
        rows = run_modes(ds, role, k, modes, f'k{k}-{role}-{suffix}', lib)
        results = {name: summarize(truth, k, r) for name, r in rows.items()}
        store(qdir(lib, ds) / f'{role}-{suffix}-k{k}.json', results)
        repeated = sorted(n for n in results if n in base)
        for n in repeated:
            assert np.array_equal(results[n][0], base[n][0]) and np.array_equal(results[n][1], base[n][1]), (ds, k, n)
        out = held_out_cm(ds, role, selection, chosen, base, results)
        save(qdir(lib, ds) / f'{role}-{suffix}-result-k{k}.json', dict(repeated_modes_identical=repeated, results=out))


def cm_choice(selection):
    """Rule C+m alpha per point and the search modes it needs (validate_cm; also used by check_results.py)."""
    chosen, modes = {}, {}
    for tag, s in selection.items():
        a = rule_cm(s['rule_c'], s['C'])
        chosen[tag] = dict(rule_c=s['rule_c'], margin=MARGIN[s['C']], alpha=a,
                           target=None if s['rule_c'] is None else 1 + (s['rule_c'] - 1) * (1 + MARGIN[s['C']]))
        if a is not None:
            modes[alpha_name(s['fixed_ef'], a)] = (params(s['fixed_ef'], a), s['fixed_ef'])
    return chosen, modes


def held_out_cm(ds, role, selection, chosen, base, results):
    """Held-out verdicts of the rule C+m alphas against the fixed results of the first held-out run."""
    out = {}
    for tag, s in selection.items():
        ef, R, C = s['fixed_ef'], s['R'], s['C']
        f_rec, f_dc, _ = base[alpha_name(ef, None)]
        a = chosen[tag]['alpha']
        if a is None:
            out[tag] = None
            continue
        rec, dc, stops = results[alpha_name(ef, a)]
        e = stats(f_rec, f_dc, rec, dc, stops, R)
        e.update(alpha=a, quality_pass=bool(e['coverage'] >= C and e['mean_loss'] <= LOSS))
        e['status'] = ('fixed_fails' if coverage(f_rec, R) < C else 'pass' if e['quality_pass'] else 'early_stop_fails')
        out[tag] = e
        print(ds, role, tag, 'C+m', a, e['status'], round(e['coverage'], 4), round(100 * e['mean_loss'], 3),
              round(e['saving_pct'], 1), flush=True)
    return out


def default_check(lib, datasets):
    """Searches with early_stop but no alpha must resolve to the k-based default (1.5 at k=10, 1.15 at k=100) and
    reproduce the explicit-alpha outputs byte for byte; where ef <= 1.25 k they must equal fixed search."""
    rows = []
    for ds in datasets:
        for role, ref_tag in [('calibration', 'alpha'), ('validation', 'validation')]:
            for k in KS:
                selection = read(qdir(lib, ds) / f'selection-k{k}.json')
                efs = sorted({s['fixed_ef'] for s in selection.values()})
                tag = f'k{k}-{role}-noalpha'
                modes = {f'ef{ef}-noalpha': ({'hgraph': {'ef_search': ef, 'early_stop': {'type': 'distance'}}}, ef)
                         for ef in efs}
                run_modes(ds, role, k, modes, tag, lib)
                for ef in efs:
                    auto = ef <= AUTO_OFF_RATIO * k
                    target = alpha_name(ef, None if auto else DEFAULT_ALPHA[k])
                    mine = qdir(lib, ds) / role / tag / 'out' / f'ef{ef}-noalpha.bin'
                    other = qdir(lib, ds) / role / f'k{k}-{ref_tag}' / 'out' / f'{target}.bin'
                    rows.append(dict(dataset=ds, role=role, k=k, ef=ef, auto_off=auto, compared_with=target,
                                     reference_exists=other.exists(),
                                     identical=other.exists() and mine.read_bytes() == other.read_bytes()))
    bad = [r for r in rows if not r['identical']]
    save(RUN / f'default-check-{lib}-{"-".join(datasets)}.json', dict(checked=len(rows), identical=len(rows) - len(bad), rows=rows))
    print('default check', len(rows), 'identical', len(rows) - len(bad))


def compare_libs(a, b):
    """Byte-compare the per-query outputs (work, IDs, distances) of two libraries on every common mode."""
    rows = []
    for ds in DATASETS:
        for out in sorted((qdir(a, ds)).glob('*/*/out/*.bin')):
            rel = out.relative_to(qdir(a, ds))
            other = qdir(b, ds) / rel
            if not other.exists():
                continue
            same = out.read_bytes() == other.read_bytes()
            row = dict(dataset=ds, file=str(rel), identical=same)
            if not same:
                x, y = parse(out), parse(other)
                row['queries_differing'] = sum(not (np.array_equal(p[0], q[0]) and p[1] == q[1]) for p, q in zip(x, y))
                # A library with the automatic skip runs plain fixed search where ef <= 1.25 k, so alpha modes there
                # are expected to differ from v3 (which applied the rule); everything else must be byte-identical.
                k = int(rel.parts[1].split('-')[0][1:])
                name = out.stem
                ef = int(name.split('-')[0][2:])
                row['expected_auto_off'] = '-a' in name and ef <= AUTO_OFF_RATIO * k
                if row['expected_auto_off']:
                    fixed = other.parent / f'ef{ef}-fixed.bin'
                    row[f'equals_fixed_in_{b}'] = fixed.exists() and other.read_bytes() == fixed.read_bytes()
            rows.append(row)
    differing = [r for r in rows if not r['identical']]
    unexpected = [r for r in differing if not (r.get('expected_auto_off') and r.get(f'equals_fixed_in_{b}'))]
    auto_off_modes = [r for r in rows if '-a' in Path(r['file']).stem and
                      int(Path(r['file']).stem.split('-')[0][2:]) <= AUTO_OFF_RATIO * int(Path(r['file']).parts[1].split('-')[0][1:])]
    save(RUN / f'compare-{a}-{b}.json', dict(
        compared=len(rows), identical=len(rows) - len(differing), differing=len(differing),
        differing_auto_off_equal_fixed=len(differing) - len(unexpected), unexpected=len(unexpected),
        auto_off_alpha_modes=len(auto_off_modes),
        auto_off_alpha_modes_identical=sum(r['identical'] for r in auto_off_modes),
        note='identical auto-off modes are ones where the rule never stopped a search in the first library either',
        unexpected_rows=unexpected, differing_rows=differing))
    print('compared', len(rows), 'differing', len(differing), 'unexpected', len(unexpected))


def host_cpu():
    values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
    return dict(busy=sum(values[:8]) - values[3] - values[4], loadavg=Path('/proc/loadavg').read_text().strip())


def timing_batch(path, expected):
    raw = Path(path).read_bytes()
    header = struct.unpack_from('<6Q', raw)
    assert header == tuple(expected), (path, header, expected)
    n, k, dim, threads, passes, inner = header
    assert len(raw) == 56 + 8 * n * passes
    seconds = struct.unpack_from('<d', raw, 48)[0]
    values = np.frombuffer(raw, dtype='<f8', offset=56).reshape(passes, n)
    assert np.isfinite(values).all() and (values > 0).all() and seconds > 0
    return dict(queries=n, threads=threads, passes=passes, execution_count=int(values.size), wall_seconds=seconds,
                qps=values.size / seconds, mean_ms=float(values.mean()),
                p99_ms=float(np.quantile(values, .99, method='linear')))


TIMING_ARMS = ['ref', 'on', 'off', 'default', 'rulec', 'm10', 'sept']
# Package orders for its four arms: each arm takes each position once over the four repeats. This run adds rulec
# (rule C alpha, no margin) and m10 (rule C+m with m = 0.10) at C = 0.99; with six arms, repeat i uses the base order
# rotated by i positions (each arm moves one position per repeat). Arms absent from a plan are dropped from the order.
_BASE_ORDER = ['ref', 'on', 'rulec', 'sept', 'm10', 'off', 'default']  # sept: September-freeze alphas (originals)
TIMING_ORDERS = [_BASE_ORDER[i:] + _BASE_ORDER[:i] for i in range(4)]
# No-overhead check (candidate library, early_stop omitted, vs the reference library): three points, both k values.
# For the new datasets: the PR build without early_stop at the C=0.99, R=0.90 point of both k (choice of this run).
OFF_POINTS = {'c99-k10-r90', 'c99-k100-r90'}


def timing_plan(quality_lib, datasets):
    """{(ds, k): {arm: {point: search parameters}}}. ref = reference library, fixed ef; on = candidate library, rule
    C+m alpha; both at every point where rule C+m picked an alpha (all tiers). off = candidate library with early_stop
    omitted at OFF_POINTS. default = candidate library with early_stop and no alpha at the C=0.99 points."""
    plan = {}
    for ds in datasets:
        for k in KS:
            selection = read(qdir(quality_lib, ds) / f'selection-k{k}.json')
            cm = read(qdir(quality_lib, ds) / f'validation-cm-result-k{k}.json')['results']
            m10_path = qdir(quality_lib, ds) / f'validation-m10-result-k{k}.json'
            m10 = read(m10_path)['results'] if m10_path.exists() else {}
            arms = {arm: {} for arm in TIMING_ARMS}
            for tag, sel in selection.items():
                ef = sel['fixed_ef']
                if cm.get(tag):
                    arms['ref'][tag] = params(ef, None)
                    arms['on'][tag] = params(ef, cm[tag]['alpha'])
                if sel['C'] == 0.99 and sel['rule_c'] is not None:
                    arms['ref'][tag] = params(ef, None)
                    arms['rulec'][tag] = params(ef, sel['rule_c'])
                if sel['C'] == 0.99 and m10.get(tag):
                    arms['ref'][tag] = params(ef, None)
                    arms['m10'][tag] = params(ef, m10[tag]['alpha'])
                if tag in OFF_POINTS:
                    arms['off'][tag] = params(ef, None)
                if sel['C'] == 0.99 and not sel['auto_off']:
                    arms['default'][tag] = {'hgraph': {'ef_search': ef, 'early_stop': {'type': 'distance'}}}
            plan[(ds, k)] = {arm: v for arm, v in arms.items() if v}
    return plan


def library_record(role):
    lib = CFG['libraries'][role]
    record = dict(commit=lib['commit'], library=dict(path=str(lib['lib'] / 'libvsag.so.1.1.0'),
                                                     sha256=digest(lib['lib'] / 'libvsag.so.1.1.0')))
    record['helpers'] = {name: dict(sha256=digest(lib['helpers'] / name)) for name in ['multi_signature', 'timing']}
    return record


def timing_target(ds):
    return RUN / f'timing-{ds}'


def timing_summary_path(ds):
    return RUN / f'timing-summary-{ds}.json'


def timing(candidate, reference, quality_lib, ds, force=False, plan=None, target=None):
    """candidate/reference are library roles from config.toml (the PR build and upstream main at its base);
    quality_lib names the library whose selections define the timed points. Refuses to start on a busy machine
    (1-minute load average at or above [timing] max_load) unless forced."""
    load1 = float(Path('/proc/loadavg').read_text().split()[0])
    if load1 >= CFG['timing_max_load'] and not force:
        raise SystemExit(f'load average {load1} is not quiet (limit {CFG["timing_max_load"]}); use --force to override')
    target = target or timing_target(ds)
    target.mkdir(parents=True, exist_ok=False)
    plan = plan or timing_plan(quality_lib, [ds])
    save(target / 'plan.json', {f'{ds}-k{k}': arms for (ds, k), arms in plan.items()})
    save(target / 'environment.json', dict(candidate=candidate, reference=reference, quality_lib=quality_lib,
         libraries={role: library_record(role) for role in [candidate, reference]},
         orders='plan arms in base order rotated by repeat', base_order=_BASE_ORDER, loadavg=Path('/proc/loadavg').read_text(),
         cpu=next((line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                   if line.startswith('model name')), None)))
    rows = []
    for (ds, k), arms in plan.items():
        with h5py.File(DATASETS[ds]['validation'], 'r') as f:
            n = f['test'].shape[0]
        passes = math.ceil(5000 / n)
        folder = target / ds / f'k{k}'
        for arm, points in arms.items():
            for tag, p in points.items():
                save(folder / 'params' / f'{tag}_{arm}.json', p)
        for threads in THREADS:
            for repeat in range(REPEATS):
                # Balanced for every plan (from 00:45 on 11-25): the plan's own arms in base order, rotated by the
                # repeat index (2 arms: AB, BA, AB, BA). Earlier stages used TIMING_ORDERS filtered to the plan's arms.
                own = [x for x in _BASE_ORDER if x in arms]
                for position, arm in enumerate(own[repeat % len(own):] + own[:repeat % len(own)]):
                    role = reference if arm == 'ref' else candidate
                    dest = folder / f't{threads}-r{repeat}-{arm}'
                    plan_file = dest.with_suffix('.plan.txt')
                    plan_file.write_text(''.join(f'{tag} {folder / "params" / (tag + "_" + arm + ".json")}\n'
                                                 for tag in arms[arm]))
                    env = dict(os.environ, **TIMING_ENV)
                    env['OMP_NUM_THREADS'] = str(threads)
                    env['LD_LIBRARY_PATH'] = str(library_dir(role))
                    command = ['taskset', '-c', AFFINITY[threads], str(helper(role, 'timing')),
                               str(DATASETS[ds]['index']), str(DATASETS[ds]['validation']), str(create_path(ds, k)),
                               str(plan_file), str(dest), str(k), str(threads), '1', str(passes)]
                    before, usage0, t0 = host_cpu(), resource.getrusage(resource.RUSAGE_CHILDREN), time.monotonic()
                    with dest.with_suffix('.log').open('w') as log:
                        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
                    elapsed = time.monotonic() - t0
                    usage1, after = resource.getrusage(resource.RUSAGE_CHILDREN), host_cpu()
                    child = usage1.ru_utime + usage1.ru_stime - usage0.ru_utime - usage0.ru_stime
                    background = max(0.0, ((after['busy'] - before['busy']) / os.sysconf('SC_CLK_TCK') - child)
                                     / elapsed)
                    for tag in arms[arm]:
                        row = timing_batch(dest / f'{tag}-r0.bin', [n, k, DATASETS[ds]['dim'], threads, passes, 0])
                        row.update(dataset=ds, point=tag, arm=arm, library=role, outer_repeat=repeat, position=position,
                                   batch_seconds=elapsed, background_cpu_cores=background,
                                   noisy_background=background > 2, loadavg_before=before['loadavg'])
                        rows.append(row)
                    save(target / 'batches.json', rows)
                    print(ds, k, f't{threads}', f'r{repeat}', arm, f'{elapsed:.0f}s', f'background={background:.2f}',
                          flush=True)
    timing_report(ds, target)


def timing_report(ds, target=None):
    """Medians of the four repeats per (point, threads, arm); each arm against ref, with and without noisy batches."""
    target = target or timing_target(ds)
    rows = read(target / 'batches.json')
    cells = {}
    for r in rows:
        cells.setdefault((r['dataset'], r['point'], r['threads']), {}).setdefault(r['arm'], []).append(r)
    out = []
    for (ds, point, threads), arms in sorted(cells.items()):
        med = {arm: {key: float(np.median([r[key] for r in v])) for key in ['qps', 'mean_ms', 'p99_ms']}
               for arm, v in arms.items()}
        item = dict(dataset=ds, point=point, threads=threads, repeats={arm: len(v) for arm, v in arms.items()},
                    medians=med, max_background_cpu_cores=max(r['background_cpu_cores'] for v in arms.values() for r in v))
        for arm in ['on', 'off', 'default', 'rulec', 'm10', 'sept']:
            if arm in med and 'ref' in med:
                clean = {x: [r['qps'] for r in arms[x] if not r['noisy_background']] for x in ['ref', arm]}
                item[f'{arm}_vs_ref'] = dict(
                    qps_pct=100 * (med[arm]['qps'] / med['ref']['qps'] - 1),
                    mean_pct=100 * (med[arm]['mean_ms'] / med['ref']['mean_ms'] - 1),
                    p99_pct=100 * (med[arm]['p99_ms'] / med['ref']['p99_ms'] - 1),
                    clean_qps_pct=(100 * (float(np.median(clean[arm])) / float(np.median(clean['ref'])) - 1)
                                   if min(len(v) for v in clean.values()) >= 2 else None))
        out.append(item)
    save(target.parent / f'{target.name.replace("timing-", "timing-summary-", 1)}.json', dict(results=out, batches=len({(r['dataset'], r['threads'], r['outer_repeat'],
                                                                       r['arm'], r['point'].split('-')[1]) for r in rows}),
                                           noisy_rows=sum(r['noisy_background'] for r in rows), rows=len(rows)))
    print('timing summary', len(out), 'cells')


def pct(value, digits=1):
    return '' if value is None else f'{value:+.{digits}f}%'


def report(lib, datasets):
    points = []
    for ds in datasets:
        for k in KS:
            selection = read(qdir(lib, ds) / f'selection-k{k}.json')
            held = read(qdir(lib, ds) / f'validation-result-k{k}.json')
            fresh_path = qdir(lib, ds) / f'fresh-result-k{k}.json'
            fresh = read(fresh_path) if fresh_path.exists() else {}
            cm = {}
            for role in ['validation', 'fresh']:
                path = qdir(lib, ds) / f'{role}-cm-result-k{k}.json'
                cm[role] = read(path)['results'] if path.exists() else {}
            for tag, s in selection.items():
                cand = {c['alpha']: c for c in s['candidates']}
                h = dict(held[tag])
                if tag in cm['validation']:
                    h['rule_cm'] = cm['validation'][tag]
                m10_path = qdir(lib, ds) / f'validation-m10-result-k{k}.json'
                if m10_path.exists() and tag in read(m10_path)['results']:
                    h['rule_m10'] = read(m10_path)['results'][tag]
                f = dict(fresh[tag]) if tag in fresh else None
                if f is not None and tag in cm['fresh']:
                    f['rule_cm'] = cm['fresh'][tag]
                item = dict(dataset=ds, point=tag, k=k, R=s['R'], C=s['C'], fixed_ef=s['fixed_ef'], auto_off=s['auto_off'],
                            monotone=s['monotone'], calibration_queries=s['queries'], calibration_fixed=s['fixed'],
                            held_out=h, fresh=f)
                for arm in REPORT_ARMS:
                    a = arm_alpha(s, arm)
                    item[f'{arm}_alpha'] = a
                    item[f'{arm}_calibration'] = None if a is None or a not in cand else {
                        key: cand[a][key] for key in ['coverage', 'mean_loss', 'se', 'loss_ub', 'saving_pct', 'stops']}
                points.append(item)
    order = {ds: i for i, ds in enumerate(DATASETS)}
    points.sort(key=lambda p: (p['C'], order[p['dataset']], p['k'], p['R']))
    per_c = {}
    for C in TIERS:
        sel = [p for p in points if p['C'] == C]
        per_c[str(C)] = {s: sum(p['held_out']['status'] == s for p in sel) for s in
                         ['adaptive_pass', 'early_stop_fails', 'fixed_fallback', 'fixed_auto_off', 'fixed_fails']}
        for arm in ['rule_b', 'old', 'default']:
            per_c[str(C)][f'{arm}_held_out_early_stop_fails'] = sum(
                (p['held_out'].get(arm) or {}).get('status') == 'early_stop_fails' for p in sel)
        # Point-level tallies per arm: an arm without an alpha runs fixed ef at that point.
        tallies = {}
        for arm in REPORT_ARMS:
            if not all(arm in p['held_out'] for p in sel):
                continue
            t = dict(points=len(sel), pass_total=0, pass_with_early_stop=0, early_stop_fails=0, fixed_fails=0)
            for p in sel:
                e = p['held_out'][arm]
                if not p['held_out']['fixed']['quality_pass']:
                    t['fixed_fails'] += 1
                elif e is None:
                    t['pass_total'] += 1
                elif e['status'] == 'pass':
                    t['pass_total'] += 1
                    t['pass_with_early_stop'] += 1
                else:
                    t['early_stop_fails'] += 1
            tallies[arm] = t
        per_c[str(C)]['tallies'] = tallies
    surprises = dict(
        non_monotone=[dict(dataset=p['dataset'], point=p['point'], **p['monotone']) for p in points
                      if any(v for v in p['monotone'].values())],
        early_stop_caused_failures=[dict(dataset=p['dataset'], point=p['point'], arm=arm, alpha=p['held_out'][arm]['alpha'],
                                         coverage=p['held_out'][arm]['coverage'], mean_loss=p['held_out'][arm]['mean_loss'])
                                    for p in points for arm in REPORT_ARMS
                                    if p['held_out'].get(arm) and p['held_out'][arm]['status'] == 'early_stop_fails'],
        margin_cost=[dict(dataset=p['dataset'], point=p['point'], rule_c=p['rule_c_alpha'], rule_b=p['rule_b_alpha'],
                          saving_c=p['held_out']['rule_c']['saving_pct'] if p['held_out']['rule_c'] else 0.0,
                          saving_b=p['held_out']['rule_b']['saving_pct'] if p['held_out']['rule_b'] else 0.0)
                     for p in points if p['rule_c_alpha'] != p['rule_b_alpha']])
    summary = dict(status='quality_complete', library=lib, points=points, per_c=per_c, surprises=surprises)
    save(RUN / f'summary-{lib}-{"-".join(datasets)}.json', summary)
    print(json.dumps(dict(per_c=per_c, surprises={k: len(v) for k, v in surprises.items()}), indent=1))


def saving(e):
    return '' if not e else f"{e['saving_pct']:.1f}%" + ('' if e['status'] in ('pass', 'fixed_fails') else ' (fails)')


def write_report(summary, path):
    pts = summary['points']
    has_cm = any('rule_cm' in p['held_out'] for p in pts)
    lines = ['# Alpha recalibration with a loss margin (rule C, amended to rule C+m), 2026-10-22', '',
             'Library for all quality runs: ' + summary['library'] + ' (v3 = f83e1910 Release, the build behind the v3 '
             'numbers). Same 18 FP32 points, calibration queries (DBpedia 1270, Cohere 398, LAION 395) and held-out '
             'queries (DBpedia 1815, Cohere 601, LAION 53) as before. Fixed ef per point and tier is reused from the '
             'earlier calibrations (fixed-points.json).', '',
             '**How often the held-out queries have been looked at.** They were used once before this campaign, to evaluate '
             'the earlier alpha choices. This campaign looked at them (and at the DBpedia fresh queries) once for rules C, '
             'B, old and default, and ' + ('a second time for rule C+m, so they have now been looked at twice here and '
             'three times overall. None of these checks is untouched validation.' if has_cm else 'that is the only look '
             'so far.'), '',
             'Rule C: on the calibration queries, the alpha with the fewest distance computations such that it and every '
             'larger grid alpha keep coverage >= C_cal = (1+C)/2 and keep the mean recall loss plus two standard errors '
             'within 0.5 points; fixed where ef <= 1.25 k. Rule B drops the two-standard-error margin. "Old" is the alpha '
             'the earlier campaign recorded (September freeze for C=0.99, 2026-10-13 run for C=0.90/0.95). Default: 1.5 at '
             'k=10, 1.15 at k=100. A held-out configuration passes when fixed reaches C and early stop reaches C with mean '
             'loss <= 0.5 points. Savings are mean distance computations vs fixed ef on the held-out queries.', '']
    if has_cm:
        lines += ['**Amendment (2026-10-22, protocol.json "amendments").** The first held-out run showed that at C=0.99 '
                  'the coverage side had no margin: on the calibration queries the fixed ef sits exactly at C_cal, so rule '
                  'C picks the smallest alpha that happened to add zero calibration failures (DBpedia k100-r95 then added '
                  '7 held-out failures against a slack of 5). Rule C+m takes the rule C alpha and uses the smallest grid '
                  'alpha >= 1 + (alpha_C - 1)(1 + m), with m = 0.05 at C=0.90/0.95 and m = 0.25 at C=0.99; points fixed '
                  'or auto-off under rule C stay so. m was chosen by cross-validation on the calibration queries only '
                  '(source/cv_margin.py: 300 random 2/3 vs 1/3 splits per point, rule C on the 2/3, margin applied, checked '
                  'on the other third; the smallest m with mean failure probability <= 2.5% per tier: C=0.90 3.9% -> 0.8%, '
                  'C=0.95 4.0% -> 0.8%, C=0.99 12.1% -> 2.1% at m=0.25), before the second look at the held-out sets, '
                  'and was not changed after it.', '']
    status_word = {'adaptive_pass': 'yes', 'early_stop_fails': 'NO (early stop)', 'fixed_fails': 'NO (fixed fails)'}
    for C in CS:
        sel = [x for x in pts if x['C'] == C]
        pc = summary['per_c'][str(C)]
        lines += [f'## C = {C:.2f} (calibrated at {CS[C]})', '']
        if has_cm:
            lines += [f'### Rule C+m (m = {MARGIN[C]})', '',
                      '| point | ef | C+m alpha (rule C) | saving | cal loss / upper bound | held-out coverage (fixed -> ES) '
                      '| held-out loss | pass | rule C saving | old saving |',
                      '|---|---:|---:|---:|---|---|---:|---|---|---|']
            for p in sel:
                h = p['held_out']
                e = h.get('rule_cm')
                name = f"{p['dataset']} {p['point'].split('-', 1)[1]}"
                if e is None:
                    why = 'auto off (ef <= 1.25k)' if p['auto_off'] else 'no alpha qualifies'
                    cells = ['-', '', '', f"{h['fixed']['coverage']:.2%} (fixed only)", '',
                             'NO (fixed fails)' if not h['fixed']['quality_pass'] else f'fixed ({why})']
                else:
                    cal = p['rule_cm_calibration']
                    cells = [f"{e['alpha']:g} ({p['rule_c_alpha']:g})", f"{e['saving_pct']:.1f}%",
                             f"{100 * cal['mean_loss']:.2f} / {100 * cal['loss_ub']:.2f} pt",
                             f"{h['fixed']['coverage']:.2%} -> {e['coverage']:.2%}", f"{100 * e['mean_loss']:.2f} pt",
                             {'pass': 'yes', 'early_stop_fails': 'NO (early stop)', 'fixed_fails': 'NO (fixed fails)'}[e['status']]]
                arms = []
                for arm in ['rule_c', 'old']:
                    x = h.get(arm)
                    arms.append('-' if x is None else f"{x['alpha']:g}: {saving(x)}")
                lines.append(f"| {name} | {p['fixed_ef']} | " + ' | '.join(cells + arms) + ' |')
            lines += ['', '| arm | points passing | of which with early stop | early stop fails | fixed fails |',
                      '|---|---:|---:|---:|---:|']
            for arm in REPORT_ARMS:
                t = pc['tallies'].get(arm)
                if t:
                    lines.append(f"| {arm.replace('_', ' ')} | {t['pass_total']} of {t['points']} | {t['pass_with_early_stop']} | "
                                 f"{t['early_stop_fails']} | {t['fixed_fails']} |")
            lines += ['', '### Rule C (first held-out run)', '']
        lines += ['| point | ef | rule C alpha | saving | cal loss / upper bound | held-out coverage (fixed -> ES) | '
                  'held-out loss | pass | rule B | old | default |',
                  '|---|---:|---:|---:|---|---|---:|---|---|---|---|']
        for p in sel:
            h = p['held_out']
            c = h['rule_c']
            name = f"{p['dataset']} {p['point'].split('-', 1)[1]}"
            if c is None:
                why = 'auto off (ef <= 1.25k)' if p['auto_off'] else 'no alpha qualifies'
                cells = ['-', '', '', f"{h['fixed']['coverage']:.2%} (fixed only)", '',
                         'fixed fails' if h['status'] == 'fixed_fails' else f'fixed ({why})']
            else:
                cal = p['rule_c_calibration']
                cells = [f"{c['alpha']:g}", f"{c['saving_pct']:.1f}%",
                         f"{100 * cal['mean_loss']:.2f} / {100 * cal['loss_ub']:.2f} pt",
                         f"{h['fixed']['coverage']:.2%} -> {c['coverage']:.2%}", f"{100 * c['mean_loss']:.2f} pt",
                         status_word[h['status']]]
            arms = []
            for arm in ['rule_b', 'old', 'default']:
                e = h.get(arm)
                arms.append('-' if e is None else f"{e['alpha']:g}: {saving(e)}")
            lines.append(f"| {name} | {p['fixed_ef']} | " + ' | '.join(cells + arms) + ' |')
        lines += ['', f"Held-out, rule C: {pc['adaptive_pass']} early-stop points pass, {pc['early_stop_fails']} fail because "
                      f"of early stop, {pc['fixed_fallback']} stay fixed (no alpha qualifies), {pc['fixed_auto_off']} stay "
                      f"fixed (ef <= 1.25k), {pc['fixed_fails']} fail because the fixed baseline misses C. Early-stop failures "
                      f"with rule B: {pc['rule_b_held_out_early_stop_fails']}; old alphas: {pc['old_held_out_early_stop_fails']}; "
                      f"default alphas: {pc['default_held_out_early_stop_fails']}.", '']
    fresh = [p for p in pts if p['fresh']]
    if fresh:
        lines += ['## DBpedia, 2048 fresh queries (used once before at k100/R95; looked at ' +
                  ('twice in this campaign)' if has_cm else 'once in this campaign)'), '',
                  '| point | ef | rule C alpha | coverage fixed -> ES | loss | saving | pass | C+m alpha: saving | default |',
                  '|---|---:|---:|---|---:|---:|---|---|---|']
        for p in fresh:
            f = p['fresh']
            c = f['rule_c']
            d = f.get('default')
            cm = f.get('rule_cm')
            cm_cell = '-' if cm is None else (f"{cm['alpha']:g}: {cm['saving_pct']:.1f}% ({cm['coverage']:.2%}, "
                                              f"{100 * cm['mean_loss']:.2f} pt, {cm['status']})")
            d_cell = '-' if d is None else f"{d['alpha']:g}: {saving(d)}"
            name = p['point']
            if c is None:
                lines.append(f"| {name} | {p['fixed_ef']} | - | {f['fixed']['coverage']:.2%} (fixed only) | | | "
                             f"{'fixed fails' if f['status'] == 'fixed_fails' else 'fixed'} | {cm_cell} | {d_cell} |")
            else:
                lines.append(f"| {name} | {p['fixed_ef']} | {c['alpha']:g} | {f['fixed']['coverage']:.2%} -> "
                             f"{c['coverage']:.2%} | {100 * c['mean_loss']:.2f} pt | {c['saving_pct']:.1f}% | "
                             f"{'yes' if f['status'] == 'adaptive_pass' else f['status']} | {cm_cell} | {d_cell} |")
        lines.append('')
    lib = summary['library']
    if lib != 'v3' and (RUN / f'compare-v3-{lib}.json').exists():
        c = read(RUN / f'compare-v3-{lib}.json')
        d = read(RUN / f'default-check-{lib}.json') if (RUN / f'default-check-{lib}.json').exists() else None
        lines += [f'## {lib} against v3', '',
                  f"- Per-query outputs (work counts, IDs, distances) of every configuration run with both libraries: "
                  f"{c['compared']} files, {c['identical']} byte-identical, {c['differing']} different. All "
                  f"{c['differing_auto_off_equal_fixed']} differences are early-stop searches with ef <= 1.25 k, which "
                  f"{lib} skips: each now equals fixed search at the same ef byte for byte ({c['unexpected']} unexpected). "
                  f"Of the {c['auto_off_alpha_modes']} early-stop searches with ef <= 1.25 k, "
                  f"{c['auto_off_alpha_modes_identical']} were already identical because the rule never stopped there.",
                  '- So every number in this report equals the v3 report except where an earlier choice used early stop '
                  'at ef <= 1.25 k (the "old" alpha at four C=0.90/0.95 k100-r80 points), which now saves nothing.']
        if d:
            lines.append(f"- Early stop requested without alpha: {d['checked']} searches (every ef, calibration and "
                         f"held-out queries) reproduce the explicit alpha 1.5 (k=10) or 1.15 (k=100) byte for byte, and "
                         f"fixed search where ef <= 1.25 k: {d['identical']} of {d['checked']} identical.")
        lines.append('')
    s = summary['surprises']
    lines += ['## Held-out failures caused by early stop', '',
              'Added failures = queries that reach R with fixed ef but not with early stop; slack = fixed reached minus the '
              'number C requires. On the calibration queries the fixed ef sits exactly at C_cal at every point, so the '
              'coverage gate there means "no added failure".', '',
              '| tier | point | arm | alpha | added failures | fixed slack | mean loss |', '|---|---|---|---:|---:|---:|---:|']
    for p in pts:
        h = p['held_out']
        need = math.ceil(p['C'] * h['queries'] - 1e-9)
        for arm in REPORT_ARMS:
            e = h.get(arm)
            if e and e['status'] == 'early_stop_fails':
                lines.append(f"| {p['C']:.2f} | {p['dataset']} {p['point'].split('-', 1)[1]} | {arm} | {e['alpha']:g} | "
                             f"{h['fixed']['reached'] - e['reached']} | {h['fixed']['reached'] - need} | "
                             f"{100 * e['mean_loss']:.2f} pt |")
    lines += ['', '## Where the two-SE margin changed the choice', '',
              '| tier | point | rule C | rule B | held-out saving C / B | held-out pass C / B |', '|---|---|---:|---:|---|---|']
    for m in s['margin_cost']:
        p = next(x for x in pts if x['dataset'] == m['dataset'] and x['point'] == m['point'])
        h = p['held_out']
        lines.append(f"| {p['C']:.2f} | {p['dataset']} {p['point'].split('-', 1)[1]} | {m['rule_c']} | {m['rule_b']} | "
                     f"{m['saving_c']:.1f}% / {m['saving_b']:.1f}% | {h['rule_c']['status']} / {h['rule_b']['status']} |")
    lines += ['']
    lines += ['## Checks', '',
              f"- Per-query monotonicity in alpha (recall and work never decrease as alpha grows; no alpha beats fixed): "
              f"{'no violations' if not s['non_monotone'] else str(len(s['non_monotone'])) + ' points with violations'}.",
              f"- Held-out failures caused by early stop (any arm): {len(s['early_stop_caused_failures'])}.",
              f"- Points where the two-SE margin changed the choice: {len(s['margin_cost'])}.", '']
    path.write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    args = sys.argv[1:]
    lib = CFG['quality_library']
    if args[:1] == ['--lib']:
        lib, args = args[1], args[2:]
    if not args:
        raise SystemExit(__doc__)
    force = '--force' in args
    args = [a for a in args if a != '--force']
    phase, names = args[0], args[1:]
    if phase == 'alpha':
        for ds in names or list(DATASETS):
            alpha(ds, lib)
    elif phase == 'validate':
        for ds in names or list(DATASETS):
            validate(ds, lib)
    elif phase == 'fresh':
        validate('dbpedia', lib, 'fresh')
    elif phase == 'default-check':
        default_check(lib, names)
    elif phase == 'validate-cm':
        for ds in names or list(DATASETS):
            validate_cm(ds, lib)
    elif phase == 'validate-m10':
        assert TIERS == [0.99]
        MARGIN = {C: 0.10 for C in MARGIN}
        for ds in names:
            validate_cm(ds, lib, suffix='m10')
    elif phase == 'fresh-cm':
        validate_cm('dbpedia', lib, 'fresh')
    elif phase == 'compare-libs':
        compare_libs(*names)
    elif phase == 'timing':
        for ds in names:
            timing(CFG['timing_candidate'], CFG['timing_reference'], lib, ds, force)
    elif phase == 'timing-report':
        for ds in names:
            timing_report(ds)
    elif phase == 'report':
        report(lib, names)
    else:
        raise SystemExit(__doc__)
