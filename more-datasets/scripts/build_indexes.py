#!/usr/bin/env python3
"""Build the HGraph index of each named dataset (FP32, max_degree 32, ef_construction 500, no reorder, 12 build
threads, the dataset's metric) with the quality library, and record its SHA256.

usage: build_indexes.py [--cpus LIST] DATASET [DATASET ...]

Writes indexes/DS/create.json (config.toml [index] param plus dim and metric), indexes/DS/hgraph.index (via a
temporary file, so an interrupted build is redone) and indexes/DS/build.json. As repro-package build_indexes.py.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time

import config


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    cfg = config.load()
    args = sys.argv[1:]
    cpus = cfg['build_cpus']
    if args[:1] == ['--cpus']:
        cpus, args = args[1], args[2:]
    lib = cfg['libraries'][cfg['quality_library']]
    for ds in args:
        d = cfg['datasets'][ds]
        if d['index'].exists():
            print(ds, 'index exists', flush=True)
            continue
        d['index'].parent.mkdir(parents=True, exist_ok=True)
        create = dict(dim=d['dim'], dtype='float32', metric_type=d['metric'], index_param=cfg['index_param'])
        d['create'].write_text(json.dumps(create, indent=2) + '\n')
        tmp = d['index'].with_suffix('.index.tmp')
        env = dict(os.environ, LD_LIBRARY_PATH=str(lib['lib']), OMP_PROC_BIND='false')
        env.pop('OMP_PLACES', None)
        command = ['taskset', '-c', cpus, str(lib['helpers'] / 'build_index'), str(d['create']),
                   str(cfg['inputs'] / ds / 'base.hdf5'), str(tmp)]
        t0 = time.monotonic()
        with (d['index'].parent / 'build.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        seconds = time.monotonic() - t0
        os.rename(tmp, d['index'])
        record = dict(command=command, library=cfg['quality_library'], seconds=seconds,
                      index_sha256=digest(d['index']), create=create,
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        (d['index'].parent / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
        print(ds, f'built in {seconds:.0f} s', record['index_sha256'], flush=True)


if __name__ == '__main__':
    main()
