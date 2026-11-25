#!/usr/bin/env python3
"""Run one stage of one dataset; every step is skipped when its output exists, so a rerun resumes.

usage: pipeline.py STAGE DS

Tier numbers are the scripts' internal names of the calibration levels: tier 0.99 = fixed ef calibrated at 99.5%
(check-set gate 99%, as in the first measurement), 0.98 = calibrated at 99%, 0.90 = calibrated at 95%, 0.80 =
calibrated at 90%. Run directories are under the config's [paths] work.
  c99-quality   fixed ef at tier 0.99 (calibrate_ef.py, bisection), then recalibrate.py alpha, validate, validate-cm,
                validate-m10, default-check, report in c99/
  lvl-quality   fixed ef at tiers 0.80 and 0.98 (bisection), then alpha, validate, report in lvl/ (rule C only)
  l95-quality   fixed ef at tier 0.90 (grid and refinement as the first measurement's 0.95 tier), then alpha,
                validate, report in l95/ (rule C only)
  c99-timing    recalibrate.py timing in c99/: ref, rule C+m, rule C, C+m with m = 0.10, off, default
  c99r-timing   lvl_timing.py at tier 0.99: rule C against the reference library at every point with a rule C alpha
  lvl99-timing, lvl90-timing, l95-timing
                lvl_timing.py at tiers 0.98, 0.80, 0.90: rule C against the reference library at the points where
                rule C saves at least 8% of the distance computations on the held-out queries
  orig-timing   orig_timing.py: the three original datasets, tier 0.99, rule C and September alphas from the first
                measurement's record, timed with this measurement's libraries (orig/)
  o95-timing    orig_timing.py at tier 0.90 of the original datasets (points saving at least 8%)
  gap           gap.py: fixed ef against the per-query ideal width, held-out queries, every tier (gap/)
  mr-quality, mr-timing      meanrecall.py: the mean-recall arm (mean-recall/)
  free-quality, free-timing  freeef.py / freeef_timing.py: early stop choosing its own ef (freeef/)
  low-quality, low-timing    tiers 0.90/0.95 with rule C+m in c90-c95/ (defined, not run in this measurement)
Timing stages wait until the 1-minute load average is below 2, then recalibrate.timing applies its own check.
A step interrupted half-way leaves a search folder behind; it is moved to WORK/aborted/ before the step is redone.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import config

PY = sys.executable
S = config.HERE / 'scripts'
WORK = config.WORK
MAX_LOAD = 2.0


def run(env, *args):
    print('+', ' '.join(f'{k}={v}' for k, v in env.items()), *args, flush=True)
    subprocess.run([PY, *map(str, args)], env=dict(os.environ, **env), check=True, cwd=config.HERE)


def clear(*paths):
    for p in paths:
        if p.exists():
            dest = WORK / 'aborted' / f'{p.relative_to(WORK)}'.replace('/', '__') / time.strftime('%Y%m%d-%H%M%S')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), dest)
            print('moved partial output', p, '->', dest, flush=True)


def quality(ds, rundir, tiers, default_check, base_env, margin=True):
    env = dict(base_env, RECAL_RUN=str(WORK / rundir), RECAL_TIERS=tiers)
    q = WORK / rundir / 'quality' / 'pr' / ds
    steps = [('alpha', q / 'selection-k100.json', [q / 'calibration' / f'k{k}-alpha' for k in (10, 100)]),
             ('validate', q / 'validation-result-k100.json', [q / 'validation' / f'k{k}-validation' for k in (10, 100)]),
             ('validate-cm', q / 'validation-cm-result-k100.json',
              [q / 'validation' / f'k{k}-validation-cm' for k in (10, 100)])][:3 if margin else 2]
    if default_check:  # the C = 0.99 run: also rule C+m with m = 0.10, then the default-alpha check
        steps.append(('validate-m10', q / 'validation-m10-result-k100.json',
                      [q / 'validation' / f'k{k}-validation-m10' for k in (10, 100)]))
        steps.append(('default-check', WORK / rundir / f'default-check-pr-{ds}.json',
                      [q / role / f'k{k}-{role}-noalpha' for role in ('calibration', 'validation') for k in (10, 100)]))
    for phase, done, partial in steps:
        if done.exists():
            print(ds, rundir, phase, 'done', flush=True)
            continue
        clear(*partial)
        run(env, S / 'recalibrate.py', phase, ds)
    run(env, S / 'recalibrate.py', 'report', ds)


def wait_quiet():
    while True:
        load1 = float(Path('/proc/loadavg').read_text().split()[0])
        if load1 < MAX_LOAD:
            return
        print(time.strftime('%H:%M:%S'), 'waiting for a quiet machine, load', load1, flush=True)
        time.sleep(30)


def timing(env, script, phase_args, target, summary):
    if summary.exists():
        print('timing done', summary, flush=True)
        return
    clear(target)
    wait_quiet()
    run(env, script, *phase_args)


def main():
    stage, ds = sys.argv[1], sys.argv[2]
    cpus = os.environ.get('RECAL_CPUS')
    base_env = dict(RECAL_CPUS=cpus) if cpus else {}
    if stage == 'c99-quality':
        run(dict(base_env, RECAL_RUN=str(WORK / 'fixed-ef'), RECAL_TIERS='0.99'), S / 'calibrate_ef.py', ds)
        quality(ds, 'c99', '0.99', True, base_env)
    elif stage == 'c99-timing':
        timing(dict(RECAL_RUN=str(WORK / 'c99'), RECAL_TIERS='0.99'), S / 'recalibrate.py', ['timing', ds],
               WORK / 'c99' / f'timing-{ds}', WORK / 'c99' / f'timing-summary-{ds}.json')
    elif stage == 'mr-quality':
        env = dict(base_env, RECAL_RUN=str(WORK / 'mean-recall'))
        mr = WORK / 'mean-recall'
        q = mr / 'quality' / 'pr' / ds
        run(env, S / 'meanrecall.py', 'fixed', ds)
        if not (mr / f'calibration-{ds}-k100.npz').exists():
            clear(*[q / 'calibration' / f'k{k}-meanrecall' for k in (10, 100)
                    if not (mr / f'calibration-{ds}-k{k}.npz').exists()])
        run(env, S / 'meanrecall.py', 'alpha', ds)
        if not (mr / f'meanrecall-validation-{ds}.json').exists():
            clear(*[q / 'validation' / f'k{k}-meanrecall-validation' for k in (10, 100)])
            run(env, S / 'meanrecall.py', 'validate', ds)
    elif stage == 'mr-timing':
        timing(dict(RECAL_RUN=str(WORK / 'mean-recall')), S / 'meanrecall.py', ['timing', ds],
               WORK / 'mean-recall' / f'timing-{ds}', WORK / 'mean-recall' / f'timing-summary-{ds}.json')
    elif stage == 'orig-timing':
        timing(dict(RECAL_RUN=str(WORK / 'orig')), S / 'orig_timing.py', [ds],
               WORK / 'orig' / f'timing-{ds}', WORK / 'orig' / f'timing-summary-{ds}.json')
    elif stage == 'lvl-quality':  # calibration levels 0.90 and 0.99 (tiers 0.80, 0.98): rule C only
        run(dict(base_env, RECAL_RUN=str(WORK / 'fixed-ef'), RECAL_TIERS='0.80,0.98'), S / 'calibrate_ef.py', ds)
        quality(ds, 'lvl', '0.80,0.98', False, base_env, margin=False)
    elif stage == 'l95-quality':  # calibration level 0.95 (tier 0.90), rule C only
        run(dict(base_env, RECAL_RUN=str(WORK / 'fixed-ef'), RECAL_TIERS='0.90'), S / 'calibrate_ef.py', ds)
        quality(ds, 'l95', '0.90', False, base_env, margin=False)
    elif stage in ('lvl99-timing', 'lvl90-timing', 'l95-timing', 'c99r-timing'):
        # c99r: tier 0.99 (C_cal 0.995), rule C against the reference library at every point with a rule C alpha.
        rundir, tier = {'lvl99-timing': ('lvl', '0.98'), 'lvl90-timing': ('lvl', '0.80'), 'l95-timing': ('l95', '0.90'),
                        'c99r-timing': ('c99', '0.99')}[stage]
        suffix = f'c{int(round(float(tier) * 100))}'
        tiers = {'lvl': '0.80,0.98', 'l95': '0.90', 'c99': '0.99'}[rundir]
        timing(dict(RECAL_RUN=str(WORK / rundir), RECAL_TIERS=tiers, TIME_TIER=tier,
                    MIN_SAVING='0' if stage == 'c99r-timing' else '8'),
               S / 'lvl_timing.py', [ds], WORK / rundir / f'timing-{ds}-{suffix}',
               WORK / rundir / f'timing-summary-{ds}-{suffix}.json')
    elif stage == 'o95-timing':  # original datasets, tier 0.90 (level 0.95), rule C from the package's record
        timing(dict(RECAL_RUN=str(WORK / 'orig'), ORIG_TIER='0.90'), S / 'orig_timing.py', [ds],
               WORK / 'orig' / f'timing-{ds}-c90', WORK / 'orig' / f'timing-summary-{ds}-c90.json')
    elif stage == 'free-quality':  # free-ef arm: fixed efs of every level, then a reduction of the mean-recall sweep
        tiers = '0.80,0.98' if ds in ('dbpedia', 'cohere', 'laion') else '0.80,0.90,0.95,0.98,0.99'
        run(dict(base_env, RECAL_RUN=str(WORK / 'fixed-ef'), RECAL_TIERS=tiers), S / 'calibrate_ef.py', ds)
        if not (WORK / 'freeef' / f'freeef-{ds}.json').exists():
            run(dict(base_env, RECAL_RUN=str(WORK / 'freeef')), S / 'freeef.py', ds)
    elif stage == 'free-timing':
        timing(dict(RECAL_RUN=str(WORK / 'freeef')), S / 'freeef_timing.py', [ds],
               WORK / 'freeef' / f'timing-{ds}', WORK / 'freeef' / f'timing-summary-{ds}.json')
    elif stage == 'gap':
        run(dict(base_env, RECAL_RUN=str(WORK / 'gap')), S / 'gap.py', ds)
    elif stage == 'low-quality':
        run(dict(base_env, RECAL_RUN=str(WORK / 'fixed-ef'), RECAL_TIERS='0.90,0.95,0.99'), S / 'calibrate_ef.py', ds)
        quality(ds, 'c90-c95', '0.90,0.95', False, base_env)
    elif stage == 'low-timing':
        timing(dict(RECAL_RUN=str(WORK / 'c90-c95'), RECAL_TIERS='0.90,0.95'), S / 'recalibrate.py', ['timing', ds],
               WORK / 'c90-c95' / f'timing-{ds}', WORK / 'c90-c95' / f'timing-summary-{ds}.json')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
