"""Timing medians under one accepted-batch rule, for QPS, mean latency and P99 alike.

A batch is accepted when the background CPU use measured around it is at most 2 cores (the package's noise flag,
noisy_background = background > 2). For each (point, threads, arm) the medians of QPS, mean latency and P99 are taken
over accepted batches only; a change against ref is given only when both arms keep at least 2 accepted batches
(otherwise "insufficient"). The number of accepted batches of each arm is reported with every change. Arms are
compared only within one timing run (one batches.json), never across runs.
"""
import functools
import json
from pathlib import Path

import numpy as np

MIN_ACCEPTED = 2


@functools.lru_cache(maxsize=None)
def _load(target):
    return _load_run(target)


def load_run(target):
    return _load(str(target))


def _load_run(target):
    """{(point, threads): {arm: dict(qps, mean_ms, p99_ms, accepted, total)}} from target/batches.json."""
    path = Path(target) / 'batches.json'
    if not path.exists():
        return {}
    cells = {}
    for b in json.loads(path.read_text()):
        cells.setdefault((b['point'], b['threads']), {}).setdefault(b['arm'], []).append(b)
    out = {}
    for key, arms in cells.items():
        out[key] = {}
        for arm, rows in arms.items():
            ok = [b for b in rows if not b['noisy_background']]
            out[key][arm] = dict(accepted=len(ok), total=len(rows),
                                 **({m: float(np.median([b[m] for b in ok])) for m in ('qps', 'mean_ms', 'p99_ms')}
                                    if ok else {'qps': None, 'mean_ms': None, 'p99_ms': None}))
    return out


def compare(cell, arm):
    """Change of arm against ref within one run cell, or None; with absolute values and accepted counts."""
    if not cell or arm not in cell or 'ref' not in cell:
        return None
    a, f = cell[arm], cell['ref']
    out = dict(ref=f, arm=a, sufficient=a['accepted'] >= MIN_ACCEPTED and f['accepted'] >= MIN_ACCEPTED)
    if out['sufficient']:
        out.update(qps_pct=100 * (a['qps'] / f['qps'] - 1), mean_pct=100 * (a['mean_ms'] / f['mean_ms'] - 1),
                   p99_pct=100 * (a['p99_ms'] / f['p99_ms'] - 1))
    return out


def lookup(targets, point, threads, arm):
    """First run in targets (in order of preference) that timed both ref and arm at (point, threads)."""
    for target in targets:
        cell = load_run(target).get((point, threads))
        if cell and arm in cell and 'ref' in cell:
            return dict(compare(cell, arm), run=str(Path(target).name))
    return None
