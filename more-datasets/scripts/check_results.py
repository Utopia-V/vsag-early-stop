#!/usr/bin/env python3
"""Recompute the ten-dataset measurement's derived numbers from the per-query and per-batch records, without searching.

usage: check_results.py [--keep DIR]

Unpacks more-datasets/results/*.tar.xz twice: once as shipped (the reference) and once as a working copy from which
every file listed below as recomputed is deleted first, so that each later step can only read recomputed files.
1. Archive integrity: every archive member against its SHA256 in more-datasets/checksums/originals.sha256.
2. Fixed ef: calibrate_ef.py reruns its bisection and grid procedures on the cached per-query recalls of every
   tested ef (fixed-ef/fixed-ef/pr/*.json), which answer every probe, so no search runs. fixed-points.json and
   fixed-ef-calibration.json are compared with the shipped files.
3. Alpha selection and held-out verdicts per run directory: c99 (tier 0.99 = calibrated at 99.5%), lvl (tiers 0.98 and
   0.80 = 99% and 90%), l95 (tier 0.90 = 95%). Rule C and rule B with per-alpha statistics from calibration-k*.json;
   held-out verdicts of every arm from validation-k*.json; at c99 also rule C+m (m = 0.25) and m = 0.10 from
   validation-cm-k*.json / validation-m10-k*.json; then recalibrate.py's report phase writes summary-pr-DS.json.
4. Timing: timing-summary-*.json recomputed from batches.json by recalibrate.timing_report; the timing plans checked
   against the selections (every timed rule C alpha and fixed ef is the selected one; the rule C plans of the 99%,
   95% and 90% levels hold exactly the points saving >= 8% of the distance computations on the held-out queries, the
   99.5% plans every point with a rule C alpha).
5. Gap: gap.py reruns on its cached per-query held-out results (gap/gapcache-*.npz) and gap-DS.json is compared.
6. Tables: headline.py, tables.py and check.py regenerate headline.md/json, the per-dataset tables, points.json and
   check.json from the recomputed files and the timing batches; compared with more-datasets/tables/.
Every comparison is byte for byte. Not recomputed (no search output or index is shipped): default-check-pr-*.json,
the free-ef arm (freeef/freeef-*.json) and the mean-recall arm (mean-recall/meanrecall-*.json, fixed-*.json); their
tables are regenerated from the shipped records and their timing medians from the batches.
Finally the counts of points meeting the requirement are printed per calibration level and dataset.
Exit status 0 when everything matches.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent.parent
RESULTS = HERE / 'results'
TABLES = HERE / 'tables'
ARCHIVES = ['c99', 'lvl', 'l95', 'fixed-ef', 'gap', 'orig', 'freeef', 'mean-recall']
NEW = ['coco-i2i', 'coco-t2i', 'wiki-all', 'sift', 'deep', 'glove', 'gist']
ORIGINAL = ['dbpedia', 'cohere', 'laion']
# run directory -> (tiers of its quality run, datasets)
RUNS = {'c99': ('0.99', NEW), 'lvl': ('0.80,0.98', NEW + ORIGINAL), 'l95': ('0.90', NEW)}
# Tiers calibrated per dataset in the original run (several invocations of calibrate_ef.py, merged).
CAL_TIERS = {'0.80,0.90,0.95,0.98,0.99': ['coco-i2i', 'coco-t2i', 'sift'],
             '0.80,0.90,0.98,0.99': ['wiki-all', 'deep', 'glove', 'gist'],
             '0.80,0.98': ORIGINAL}
failures = []


def check(name, ok, detail=''):
    print(f'{"ok  " if ok else "FAIL"} {name}' + (f'  {detail}' if detail else ''), flush=True)
    if not ok:
        failures.append(name)
    return ok


def same(a, b):
    return Path(a).exists() and Path(b).exists() and Path(a).read_bytes() == Path(b).read_bytes()


def derived(rel):
    """Files of the working copy that the check recomputes (deleted before recomputing)."""
    name = rel.rsplit('/', 1)[-1]
    if rel in ('fixed-ef/fixed-points.json', 'fixed-ef/fixed-ef-calibration.json'):
        return True
    top = rel.split('/', 1)[0]
    if top in RUNS and '/quality/' in rel:
        return name.startswith('selection-') or '-result-' in name
    if top in RUNS and name.startswith('summary-pr-'):
        return True
    if name.startswith('timing-summary-') and (HERE_WORK / rel.replace('timing-summary-', 'timing-', 1)[:-5]
                                               / 'batches.json').exists():
        return True
    return top == 'gap' and name.startswith('gap-') and name.endswith('.json')


HERE_WORK = None


# ---------------------------------------------------------------- steps run in a subprocess (own env, own imports)

def step_fixed(root):
    import calibrate_ef
    import recalibrate as r
    for tiers, names in CAL_TIERS.items():
        env_tiers = [float(t) for t in tiers.split(',')]
        r.TIERS[:] = env_tiers
        sys.argv = ['calibrate_ef.py', *names]
        stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            calibrate_ef.main()
        finally:
            sys.stdout.close()
            sys.stdout = stdout
    for name in ['fixed-points.json', 'fixed-ef-calibration.json']:
        check(f'fixed-ef/{name} recomputed from the cached per-query recalls',
              same(root / 'work' / 'fixed-ef' / name, root / 'shipped' / 'fixed-ef' / name))


def step_quality(root, run):
    import numpy as np
    import recalibrate as r
    tiers, names = RUNS[run]
    points = r.fixed_points()
    shipped = root / 'shipped' / run / 'quality' / 'pr'
    for ds in names:
        q = r.qdir('pr', ds)
        out = []
        for k in r.KS:
            results = r.load(q / f'calibration-k{k}.json')
            selection = {}
            for (d, kk, R, C), point in sorted(points.items()):
                if d == ds and kk == k:
                    selection[r.label(k, R, C)] = r.select(results, ds, k, R, C, point)
            r.save(q / f'selection-k{k}.json', selection)
            files = [f'selection-k{k}.json']
            base = r.load(q / f'validation-k{k}.json')
            r.save(q / f'validation-result-k{k}.json', quiet(r.held_out, ds, k, 'validation', selection, base))
            files.append(f'validation-result-k{k}.json')
            if run == 'c99':
                margins = dict(r.MARGIN)
                for suffix, margin in [('cm', None), ('m10', 0.10)]:
                    if not (q / f'validation-{suffix}-k{k}.json').exists():  # m = 0.10 was not run for every dataset
                        continue
                    if margin is not None:
                        r.MARGIN = {C: margin for C in margins}
                    chosen, _ = r.cm_choice(selection)
                    r.save(q / f'selection-{suffix}-k{k}.json', chosen)
                    rows = r.load(q / f'validation-{suffix}-k{k}.json')
                    repeated = sorted(n for n in rows if n in base)
                    assert all(np.array_equal(rows[n][0], base[n][0]) and np.array_equal(rows[n][1], base[n][1])
                               for n in repeated), (ds, k, suffix)
                    verdicts = quiet(r.held_out_cm, ds, 'validation', selection, chosen, base, rows)
                    r.save(q / f'validation-{suffix}-result-k{k}.json',
                           dict(repeated_modes_identical=repeated, results=verdicts))
                    files += [f'selection-{suffix}-k{k}.json', f'validation-{suffix}-result-k{k}.json']
                    r.MARGIN = margins
            out += [(name, same(q / name, shipped / ds / name)) for name in files]
        bad = [name for name, ok in out if not ok]
        check(f'{run} {ds}: {len(out)} selection and held-out files recomputed', not bad, ', '.join(bad))
        quiet(r.report, 'pr', [ds])
        check(f'{run}/summary-pr-{ds}.json regenerated',
              same(r.RUN / f'summary-pr-{ds}.json', root / 'shipped' / run / f'summary-pr-{ds}.json'))


def step_timing(root):
    import recalibrate as r
    work = root / 'work'
    n = 0
    bad = []
    for target in sorted(work.glob('*/timing-*')):
        if not (target / 'batches.json').exists():
            continue
        quiet(r.timing_report, target.name, target)
        name = target.name.replace('timing-', 'timing-summary-', 1) + '.json'
        n += 1
        if not same(target.parent / name, root / 'shipped' / target.parent.name / name):
            bad.append(f'{target.parent.name}/{name}')
    check(f'{n} timing-summary files recomputed from batches.json', not bad, ', '.join(bad))
    # The timing plans against the selections.
    summary_v4 = {(p['dataset'], p['point']): p for p in
                  json.loads((r.config.PACKAGE / 'results' / 'quality' / 'summary-v4.json').read_text())['points']}
    problems, plans = [], 0
    for plan_path in sorted(work.glob('*/timing-*/plan.json')):
        run, target = plan_path.parent.parent.name, plan_path.parent.name
        plan = json.loads(plan_path.read_text())
        plans += 1
        for key, arms in plan.items():
            ds, k = key.rsplit('-k', 1)
            for point, params in arms.get('rulec', {}).items():
                if run == 'orig':
                    p = summary_v4[(ds, point)]
                    ef, alpha = p['fixed_ef'], p['rule_c_alpha']
                else:
                    sel = json.loads((work / run / 'quality' / 'pr' / ds / f'selection-k{k}.json').read_text())[point]
                    ef, alpha = sel['fixed_ef'], sel['rule_c']
                h = params['hgraph']
                if h['ef_search'] != ef or abs(h['early_stop']['alpha'] - alpha) > 1e-12 or \
                        arms['ref'][point]['hgraph']['ef_search'] != ef:
                    problems.append(f'{run}/{target} {point}')
        # Screen of the rule C plans: lvl_timing.py / orig_timing.py.
        suffix = target.rsplit('-c', 1)[-1] if target.rsplit('-', 1)[-1].startswith('c') else None
        want = None
        if run in ('lvl', 'l95', 'c99') and suffix and suffix.isdigit():
            tier = int(suffix) / 100
            ds = target[len('timing-'):-len(f'-c{suffix}')]
            minimum = 0.0 if tier == 0.99 else 8.0
            want = set()
            for k in (10, 100):
                held = json.loads((work / run / 'quality' / 'pr' / ds / f'validation-result-k{k}.json').read_text())
                want |= {(k, t) for t, h in held.items() if h['C'] == tier and h.get('rule_c')
                         and h['rule_c']['saving_pct'] >= minimum}
        elif run == 'orig':  # orig_timing.py: every rule C point at 0.99, points saving >= 8% at 0.90
            tier = int(suffix) / 100 if suffix and suffix.isdigit() else 0.99
            ds = target[len('timing-'):] if tier == 0.99 else target[len('timing-'):-len(f'-c{suffix}')]
            want = {(p['k'], p['point']) for (d, _), p in summary_v4.items() if d == ds and p['C'] == tier
                    and p['held_out'].get('rule_c') and (tier == 0.99 or p['held_out']['rule_c']['saving_pct'] >= 8.0)}
        if want is not None:
            have = {(int(key.rsplit('-k', 1)[1]), t) for key, arms in plan.items() for t in arms.get('rulec', {})}
            if want != have:
                problems.append(f'{run}/{target}: plan {sorted(have)} vs screen {sorted(want)}')
    check(f'{plans} timing plans use the selected fixed ef and rule C alpha, and follow the stated screen',
          not problems, '; '.join(problems[:5]))


def step_gap(root):
    import gap
    # gap.py was run for nine datasets (not GloVe); a run needs no search when its cache holds every width.
    names = [ds for ds in NEW + ORIGINAL if (root / 'shipped' / 'gap' / f'gap-{ds}.json').exists()]
    sys.argv = ['gap.py', *names]
    quiet(gap.main)
    bad = [ds for ds in names if not same(root / 'work' / 'gap' / f'gap-{ds}.json',
                                          root / 'shipped' / 'gap' / f'gap-{ds}.json')]
    check(f'gap-DS.json of {len(names)} datasets recomputed from the cached held-out results', not bad, ', '.join(bad))


def step_tables(root):
    import check as audit
    import headline
    import tables
    quiet(headline.main)
    sys.argv = ['tables.py', *NEW, *ORIGINAL]
    quiet(tables.main)
    quiet(audit.main)
    out = root / 'tables'
    names = sorted(p.name for p in TABLES.iterdir())
    bad = [n for n in names if not same(out / n, TABLES / n)]
    extra = sorted(set(p.name for p in out.iterdir()) - set(names))
    check(f'{len(names)} tables regenerated (headline.md/json, per-dataset tables, points.json, check.json)',
          not bad and not extra, ', '.join(bad + [f'not shipped: {x}' for x in extra]))
    counts(json.loads((out / 'headline.json').read_text()))


def counts(headline):
    """Points meeting the requirement / points, (distinct R among them), per calibration level and dataset."""
    levels = [('0.99', '99.5%'), ('0.98', '99%'), ('0.9', '95%'), ('0.8', '90%')]
    order = ['wiki-all', 'coco-i2i', 'coco-t2i', 'dbpedia', 'cohere', 'laion', 'deep', 'glove', 'gist', 'sift']
    print('\nrule C, points meeting the requirement / points (distinct R), by calibration level:')
    print(f'{"dataset":10s}' + ''.join(f'{name:>14s}' for _, name in levels))
    for ds in order:
        cells = []
        for key, _ in levels:
            rows = [x for x in headline[key] if x['dataset'] == ds and x['alpha_rule'] == 'rule C']
            ok = [x for x in rows if x.get('meets')]
            cells.append(f'{len(ok)}/{len(rows)} ({len({x["R"] for x in ok})})')
        print(f'{ds:10s}' + ''.join(f'{c:>14s}' for c in cells))


def quiet(function, *args):
    stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        return function(*args)
    finally:
        sys.stdout.close()
        sys.stdout = stdout


def run_step(root, step, run=None, env=None):
    env = dict(os.environ, REPRO_CONFIG=str(root / 'config.toml'), **(env or {}))
    command = [sys.executable, __file__, '--step', step, '--root', str(root)] + (['--run', run] if run else [])
    result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stdout.write(result.stdout)
    sys.stdout.flush()
    for line in result.stdout.splitlines():
        if line.startswith('FAIL'):
            failures.append(line[5:])
    if result.returncode and not any(line.startswith('FAIL') for line in result.stdout.splitlines()):
        failures.append(f'step {step} {run or ""} exited with {result.returncode}')
        print(f'FAIL step {step} {run or ""} exited with {result.returncode}')


def write_config(root):
    text = (HERE / 'config.example.toml').read_text()
    for old, new in [('work = "../work/more-datasets"', f'work = "{root / "work"}"'),
                     ('tables = "../work/more-datasets/tables"', f'tables = "{root / "tables"}"'),
                     ('fixed_points = "../work/more-datasets/fixed-ef/fixed-points.json"',
                      f'fixed_points = "{root / "work" / "fixed-ef" / "fixed-points.json"}"')]:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    # Nothing else of a rerun's work directory is read: point it at a directory that does not exist.
    text = text.replace('"../work/', f'"{root / "absent"}/').replace('"../frozen/', f'"{HERE.parent / "frozen"}/')
    (root / 'config.toml').write_text(text)


def main():
    global HERE_WORK
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--keep', type=Path, help='keep the recomputed files in this new directory')
    parser.add_argument('--step', help=argparse.SUPPRESS)
    parser.add_argument('--root', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--run', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.step:
        steps = dict(fixed=step_fixed, quality=lambda root: step_quality(root, args.run), timing=step_timing,
                     gap=step_gap, tables=step_tables)
        steps[args.step](args.root)
        sys.exit(1 if failures else 0)

    root = Path(tempfile.mkdtemp(prefix='repro-check-more-')) if args.keep is None else args.keep
    root.mkdir(parents=True, exist_ok=args.keep is None)
    # 1. archive integrity
    expected = {}
    for line in (HERE / 'checksums' / 'originals.sha256').read_text().splitlines():
        digest, member = line.split()[:2]
        expected[member] = digest
    seen, bad = 0, []
    for name in ARCHIVES:
        with tarfile.open(RESULTS / f'{name}.tar.xz') as tar:
            for member in tar.getmembers():
                if member.isfile():
                    seen += 1
                    key = f'{name}.tar.xz:{member.name}'
                    if hashlib.sha256(tar.extractfile(member).read()).hexdigest() != expected.get(key):
                        bad.append(key)
            tar.extractall(root / 'shipped', filter='data')
            tar.extractall(root / 'work', filter='data')
    check(f'{seen} archive members match checksums/originals.sha256 ({len(expected)} listed)',
          not bad and seen == len(expected), ', '.join(bad[:5]))
    HERE_WORK = root / 'work'
    removed = 0
    for path in sorted(HERE_WORK.rglob('*')):
        if path.is_file() and derived(str(path.relative_to(HERE_WORK))):
            path.unlink()
            removed += 1
    print(f'     {removed} derived files removed from the working copy before recomputing', flush=True)
    (root / 'tables').mkdir()
    write_config(root)

    # 2-6
    run_step(root, 'fixed', env=dict(RECAL_RUN=str(root / 'work' / 'fixed-ef'),
                                     RECAL_TIERS='0.80,0.90,0.95,0.98,0.99'))
    for run, (tiers, _) in RUNS.items():
        run_step(root, 'quality', run, env=dict(RECAL_RUN=str(root / 'work' / run), RECAL_TIERS=tiers))
    run_step(root, 'timing', env=dict(RECAL_RUN=str(root / 'work' / 'c99')))
    run_step(root, 'gap', env=dict(RECAL_RUN=str(root / 'work' / 'gap'), RECAL_TIERS='0.80,0.90,0.95,0.98,0.99'))
    run_step(root, 'tables')

    keep = args.keep is not None or failures
    print(f'\n{len(failures)} failed' if failures else '\nall checks passed', f'(work files in {root})' if keep else '')
    if not keep:
        shutil.rmtree(root)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
