#!/usr/bin/env python3
"""Run the whole pipeline on three tiny synthetic datasets in a few minutes, to check the scripts and the builds.

usage: run_smoke.py [--pr-source DIR --pr-build DIR] [--upstream-source DIR --upstream-build DIR] [--work DIR]

Each synthetic dataset takes the name of a real one (so every script runs unchanged) but holds 20,000 weakly
clustered vectors of dimension 48 (dbpedia), 32 (cohere) or 24 (laion, stored as float16 like the real LAION base),
200 calibration and 200 held-out queries, and for dbpedia 128 fresh queries. The steps after the download are the real
ones: prepare_workload.py, the helper builds, build_indexes.py, calibrate_ef.py, every recalibrate.py phase including a
timing run (1 and 8 threads, started on any machine load), cv_margin.py and make_report_assets.py. About 5 minutes.
Without the build arguments the trees of scripts/build_vsag.py (work/builds/<role>) are used. Output: smoke/work.
The numbers mean nothing; the run checks that every stage works and that the outputs fit together.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

PACKAGE = Path(__file__).resolve().parent.parent
SCRIPTS = PACKAGE / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import prepare_workload  # noqa: E402

DIMS = {'dbpedia': 48, 'cohere': 32, 'laion': 24}


def make_data(work, ds, dim, seed):
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(200, dim))
    labels = rng.integers(0, 200, size=20000 + 528)
    vectors = centres[labels] + rng.normal(size=(len(labels), dim))
    base, queries = vectors[:20000], vectors[20000:]
    folder = work / 'data' / ds
    folder.mkdir(parents=True, exist_ok=True)
    np.save(folder / 'vectors.npy', base.astype('<f2' if ds == 'laion' else '<f4'))
    with (folder / 'tests.jsonl').open('w') as stream:
        for q in queries[:400]:
            stream.write(json.dumps(dict(query=[float(x) for x in q.astype('<f4')], conditions=None)) + '\n')
    (folder / 'rows.json').write_text(json.dumps(dict(calibration=list(range(200)), validation=list(range(200, 400)))))
    create = json.loads((PACKAGE / 'frozen' / 'index' / f'{ds}.json').read_text())
    create['dim'] = dim
    create['index_param']['build_thread_count'] = 4
    (folder / 'create.json').write_text(json.dumps(create, indent=2))
    return queries[400:].astype('<f4')


def write_config(work, args):
    lines = [f'[paths]\nwork = "{work}"\n', '[libraries]\nquality = "pr"\ntiming_candidate = "pr"\n'
             'timing_reference = "upstream"\n']
    for role in ['pr', 'upstream']:
        source, build = getattr(args, f'{role}_source'), getattr(args, f'{role}_build')
        lines.append(f'[libraries.{role}]')
        if source and build:
            lines += [f'source = "{source}"', f'build = "{build}"', f'lib = "{Path(build) / "src"}"']
        else:
            lines += [f'source = "{PACKAGE / "work" / "builds" / role / "src"}"',
                      f'build = "{PACKAGE / "work" / "builds" / role / "build-release"}"',
                      f'lib = "{PACKAGE / "work" / "builds" / role / "build-release" / "src"}"']
        lines.append(f'helpers = "{work / "builds" / role / "helpers"}"\n')
    lines.append(f'[selection]\nfixed_points = "{work / "run" / "fixed-points.json"}"\n')
    lines.append('[quality]\ncpus = [0, 1, 2]\nprocesses = { dbpedia = 2, cohere = 2, laion = 2 }\n')
    lines.append('[index]\ncpus = "0-3"\n')
    for ds, dim in DIMS.items():
        lines.append(f'[datasets.{ds}]\ndim = {dim}\ncreate = "{work / "data" / ds / "create.json"}"\n')
    path = work / 'config.toml'
    path.write_text('\n'.join(lines))
    return path


def step(name, command, env):
    print(f'=== {name}', flush=True)
    with open(env['SMOKE_LOG'], 'a') as log:
        log.write(f'=== {name}: {" ".join(str(c) for c in command)}\n')
        log.flush()
        subprocess.run([str(c) for c in command], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for role in ['pr', 'upstream']:
        parser.add_argument(f'--{role}-source', type=Path)
        parser.add_argument(f'--{role}-build', type=Path)
    parser.add_argument('--work', type=Path, default=PACKAGE / 'smoke' / 'work')
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    fresh = {}
    for i, (ds, dim) in enumerate(DIMS.items()):
        fresh[ds] = make_data(work, ds, dim, 20261115 + i)
    config_path = write_config(work, args)
    env = dict(os.environ, REPRO_CONFIG=str(config_path), SMOKE_LOG=str(work / 'smoke.log'))
    py = sys.executable

    print('=== prepare inputs', flush=True)
    (work / 'inputs').mkdir()
    for ds in DIMS:
        prepare_workload.run(work / 'data' / ds / 'vectors.npy', work / 'data' / ds / 'tests.jsonl',
                             work / 'data' / ds / 'rows.json', work / 'inputs' / ds)
    base = np.load(work / 'data' / 'dbpedia' / 'vectors.npy')
    ids, distances = prepare_workload.exact_cosine(base, fresh['dbpedia'])
    prepare_workload.write_split(work / 'inputs' / 'dbpedia' / 'fresh.hdf5', fresh['dbpedia'], ids, distances)

    step('helpers', [py, SCRIPTS / 'build_vsag.py', '--helpers-only'], env)
    step('indexes', [py, SCRIPTS / 'build_indexes.py'], env)
    step('fixed ef', [py, SCRIPTS / 'calibrate_ef.py'], env)
    for phase in ['alpha', 'validate', 'fresh', 'validate-cm', 'fresh-cm', 'default-check', 'report']:
        step(phase, [py, SCRIPTS / 'recalibrate.py', phase], env)
    step('margin', [py, SCRIPTS / 'cv_margin.py', work / 'run' / 'quality' / 'pr', work / 'run' / 'cv_margin.json'], env)
    step('timing', [py, SCRIPTS / 'recalibrate.py', 'timing', '--force'], env)
    step('report assets', [py, SCRIPTS / 'make_report_assets.py', '--timing', work / 'run' / 'timing-results',
                           '--summary', work / 'run' / 'summary-pr.json', '--out', work / 'report', '--keep-noisy'], env)

    summary = json.loads((work / 'run' / 'summary-pr.json').read_text())
    default = json.loads((work / 'run' / 'default-check-pr.json').read_text())
    batches = json.loads((work / 'run' / 'timing-results' / 'batches.json').read_text())
    early = sum(p['rule_cm_alpha'] is not None for p in summary['points'])
    print(json.dumps(dict(points=len(summary['points']), with_early_stop=early,
                          default_alpha_identical=f"{default['identical']}/{default['checked']}",
                          timing_batch_rows=len(batches),
                          report_rows=sum(1 for _ in open(work / 'report' / 'data' / 'points.csv')) - 1), indent=1))


if __name__ == '__main__':
    main()
