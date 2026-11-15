#!/usr/bin/env python3
"""Build the three HGraph indexes (FP32, max_degree 32, ef_construction 500, cosine) and record their SHA256.

usage: build_indexes.py [dataset ...]

Runs native/build_index.cpp (row i of the base gets label i; Build, then Serialize) with the create parameters in
frozen/index/<ds>.json, pinned to the CPUs of config.toml [index] cpus; HGraph builds with 12 threads
(build_thread_count). LAION uses support_duplicate with threshold 0.0 because its base contains exact duplicates.
The original indexes took 857 s (DBpedia), 293 s (Cohere) and 234 s (LAION). The build is multithreaded, so a rebuilt
index is a different graph from the original one (SHA256 in SHA256SUMS): recalibrate the fixed ef on it.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import config


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    cfg = config.load()
    role = cfg['quality_library']
    lib = cfg['libraries'][role]
    for ds in sys.argv[1:] or ['dbpedia', 'cohere', 'laion']:
        d = cfg['datasets'][ds]
        if d['index'].exists():
            print(ds, 'index exists', d['index'], flush=True)
            continue
        d['index'].parent.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, LD_LIBRARY_PATH=str(lib['lib']), OMP_PROC_BIND='false')
        env.pop('OMP_PLACES', None)
        command = ['taskset', '-c', cfg['build_cpus'], str(lib['helpers'] / 'build_index'), str(d['create']),
                   str(d['calibration']), str(d['index'])]
        t0 = time.monotonic()
        with (d['index'].parent / 'build.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        record = dict(command=command, library=role, seconds=time.monotonic() - t0, index_sha256=digest(d['index']),
                      create=json.loads(d['create'].read_text()),
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        (d['index'].parent / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
        print(ds, f'built in {record["seconds"]:.0f} s', record['index_sha256'], flush=True)


if __name__ == '__main__':
    main()
