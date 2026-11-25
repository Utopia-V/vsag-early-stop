#!/usr/bin/env python3
"""Write the HDF5 inputs of one dataset: base, calibration and held-out ("validation") queries with exact ground truth.

usage: prepare.py DATASET [DATASET ...]

Source files (data only, opened with h5py/numpy) are under the config's [paths] data directory, where download.py
puts them. For each dataset:
- base: the "train" rows as FP32 (Deep: the first 1,000,000 rows; t2i: the 1,000,000 rows of the .fbin file);
- queries: the "test" rows (t2i: the .fbin query file). Queries with identical FP32 content (+/- zero canonicalised)
  keep only their first occurrence. The remaining source rows are permuted with numpy default_rng(SEED); the first
  half (floor) is calibration, the rest held-out. Rows and content hashes are recorded in manifest.json.
- ground truth: exact FP64 scan over the FP32 vectors the index holds, top 100, ties by base row id.
  cosine: as repro-package prepare_workload.exact_cosine (distance = float32(1 - FP64 cosine)).
  l2: FP64 squared Euclidean distance (the library's L2 metric is squared L2), float32 stored.
  The files' own neighbours are ignored.
Outputs go to a temporary directory renamed on completion, so a rerun resumes by skipping finished datasets.
Finally the new manifest is compared with the frozen one of the original run (more-datasets/frozen/inputs/DS/
manifest.json.xz): the base array, the query rows of each role and their content hashes must be identical; the ground
truth comes from a full FP64 matrix product, where another BLAS can round the last bit differently and reorder
near-tied neighbours, so a neighbour or distance mismatch is reported, not fatal.
"""
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone

import h5py
import numpy as np

import config

SEED = 20261124
DEPTH = 100
BATCH = 64


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def array_hash(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def content_hash(query):
    canonical = np.array(query, dtype='<f4', copy=True)
    canonical[canonical == 0] = 0
    return hashlib.sha256(canonical.tobytes(order='C')).hexdigest()


def load_source(ds, d):
    """Base and query arrays from the registry entry: an ann-benchmarks style HDF5 file ("source", train/test; FP16 is
    widened value by value) or two .fbin files ("source" base, "queries" query file; 8-byte header). "base_rows"
    keeps the first rows of the base."""
    cfg = config.load()
    raw = cfg['raw_datasets'][ds]
    downloads = cfg['data']
    src = Path(raw['source'])
    src = src if src.is_absolute() else downloads / src
    rows = raw.get('base_rows')
    if src.suffix == '.fbin':
        qsrc = Path(raw['queries'])
        qsrc = qsrc if qsrc.is_absolute() else downloads / qsrc
        base = np.fromfile(src, dtype='<f4', offset=8).reshape(-1, d['dim'])
        queries = np.fromfile(qsrc, dtype='<f4', offset=8).reshape(-1, d['dim'])
        files = [src, qsrc]
        note = 'fbin files, 8-byte header skipped'
    else:
        with h5py.File(src, 'r') as f:
            base = f['train'][:rows] if rows else f['train'][:]
            queries = f['test'][:]
        files = [src]
        note = 'HDF5 train/test'
    if rows:
        base = base[:rows]
        note += f', first {rows} base rows'
    if base.dtype == np.float16:
        note += ', FP16 widened to FP32 value by value'
        assert np.array_equal(base.astype('<f4').astype(np.float16), base)
    base = np.ascontiguousarray(base, dtype='<f4')
    queries = np.ascontiguousarray(queries, dtype='<f4')
    assert base.shape[1] == d['dim'] == queries.shape[1]
    assert np.isfinite(base).all() and np.isfinite(queries).all()
    if d['metric'] == 'cosine':
        assert (np.linalg.norm(base.astype(np.float64), axis=1) > 0).all()
        assert (np.linalg.norm(queries.astype(np.float64), axis=1) > 0).all()
    return base, queries, files, note


def duplicate_stats(base):
    v = np.ascontiguousarray(base).view(np.dtype((np.void, base.shape[1] * 4))).ravel()
    _, counts = np.unique(v, return_counts=True)
    return dict(groups=int((counts > 1).sum()), rows=int(counts[counts > 1].sum()), largest=int(counts.max()))


def exact(base, queries, metric):
    """FP64 exact top DEPTH; ties by base row id. Returns ids (int64) and float32 distances."""
    b = np.array(base, dtype=np.float64, copy=True)
    q = np.array(queries, dtype=np.float64, copy=True)
    if metric == 'cosine':
        b /= np.linalg.norm(b, axis=1)[:, None]
        q /= np.linalg.norm(q, axis=1)[:, None]
    else:
        bn = np.einsum('ij,ij->i', b, b)
    ids = np.empty((len(q), DEPTH), dtype='<i8')
    dist = np.empty((len(q), DEPTH), dtype='<f4')
    for begin in range(0, len(q), BATCH):
        qq = q[begin:begin + BATCH]
        if metric == 'cosine':
            d = 1.0 - qq @ b.T
        else:
            d = bn[None, :] - 2.0 * (qq @ b.T) + np.einsum('ij,ij->i', qq, qq)[:, None]
        for offset, row in enumerate(d):
            threshold = np.partition(row, DEPTH - 1)[DEPTH - 1]
            candidates = np.flatnonzero(row <= threshold)
            order = np.lexsort((candidates, row[candidates]))[:DEPTH]
            sel = candidates[order]
            ids[begin + offset] = sel
            dist[begin + offset] = row[sel]
        if begin // BATCH % 20 == 0:
            print(json.dumps({'exact_queries_done': min(begin + BATCH, len(q)), 'total': len(q)}), flush=True)
    return ids, dist


def write_split(path, queries, ids, distances, metric):
    with h5py.File(path, 'x') as out:
        out.attrs['distance'] = np.bytes_('angular' if metric == 'cosine' else 'euclidean')
        out['train'] = h5py.ExternalLink('base.hdf5', '/train')
        out.create_dataset('test', data=queries)
        out.create_dataset('neighbors', data=ids)
        out.create_dataset('distances', data=distances)


def prepare(cfg, ds):
    d = cfg['datasets'][ds]
    final = cfg['inputs'] / ds
    if (final / 'manifest.json').exists():
        print(ds, 'inputs exist', flush=True)
        return
    tmp = cfg['inputs'] / f'.{ds}.tmp'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    base, queries, files, note = load_source(ds, d)
    hashes = [content_hash(x) for x in queries]
    seen, unique_rows, dropped = {}, [], []
    for row, h in enumerate(hashes):
        if h in seen:
            dropped.append(dict(row=row, duplicate_of=seen[h]))
        else:
            seen[h] = row
            unique_rows.append(row)
    perm = np.random.default_rng(SEED).permutation(len(unique_rows))
    ordered = [unique_rows[i] for i in perm]
    half = len(ordered) // 2
    rows = dict(calibration=sorted(ordered[:half]), validation=sorted(ordered[half:]))
    assert not ({hashes[r] for r in rows['calibration']} & {hashes[r] for r in rows['validation']})
    with h5py.File(tmp / 'base.hdf5', 'x') as out:
        out.attrs['distance'] = np.bytes_('angular' if d['metric'] == 'cosine' else 'euclidean')
        out.create_dataset('train', data=base)
    selected = rows['calibration'] + rows['validation']
    ids, dist = exact(base, queries[selected], d['metric'])
    n = len(rows['calibration'])
    write_split(tmp / 'calibration.hdf5', queries[rows['calibration']], ids[:n], dist[:n], d['metric'])
    write_split(tmp / 'validation.hdf5', queries[rows['validation']], ids[n:], dist[n:], d['metric'])
    manifest = dict(
        dataset=ds, label=d['label'], metric=d['metric'], created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=[dict(path=str(f), bytes=f.stat().st_size, sha256=file_sha256(f)) for f in files], source_note=note,
        base=dict(shape=list(base.shape), dtype='<f4', sha256=array_hash(base), exact_duplicates=duplicate_stats(base),
                  norm_range=[float(x) for x in np.percentile(np.linalg.norm(base.astype(np.float64), axis=1), [0, 50, 100])]),
        queries=dict(source_rows=len(queries), unique=len(unique_rows), duplicates_dropped=dropped,
                     split=f'numpy default_rng({SEED}).permutation over the unique rows (first occurrence kept); '
                           'first floor(n/2) calibration, rest validation; row lists sorted',
                     seed=SEED, rows=rows,
                     content_sha256={role: [hashes[r] for r in rows[role]] for role in rows}),
        ground_truth=dict(depth=DEPTH, algorithm=(
            'FP32 values to FP64; ' + ('row L2 normalisation; distance 1 - cosine' if d['metric'] == 'cosine'
                                       else 'squared L2 = |b|^2 - 2 q.b + |q|^2') +
            '; full scan; partition then lexsort(distance, base row id); float32 stored'),
            source_neighbors='ignored',
            arrays={role: dict(neighbors=array_hash(ids[s]), distances=array_hash(dist[s])) for role, s in
                    [('calibration', slice(0, n)), ('validation', slice(n, None))]}),
        versions=dict(numpy=np.__version__, h5py=h5py.__version__))
    (tmp / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if final.exists():
        shutil.rmtree(final)
    os.rename(tmp, final)
    print(ds, 'inputs written', len(rows['calibration']), len(rows['validation']), flush=True)


def compare_frozen(cfg, ds):
    """Compare the manifest just written with the frozen manifest of the original run."""
    frozen_path = config.MANIFESTS / ds / 'manifest.json.xz'
    if not frozen_path.exists():
        print(ds, 'no frozen manifest to compare with', flush=True)
        return
    frozen = json.loads(lzma.decompress(frozen_path.read_bytes()))
    mine = json.loads((cfg['inputs'] / ds / 'manifest.json').read_text())
    exact = [('base array', mine['base']['sha256'], frozen['base']['sha256']),
             ('query rows', mine['queries']['rows'], frozen['queries']['rows']),
             ('query contents', mine['queries']['content_sha256'], frozen['queries']['content_sha256'])]
    bad = [name for name, a, b in exact if a != b]
    if bad:
        raise SystemExit(f'{ds}: {", ".join(bad)} differ from the original inputs')
    gt = [f'{role} {name}' for role, arrays in frozen['ground_truth']['arrays'].items() for name in arrays
          if mine['ground_truth']['arrays'][role][name] != arrays[name]]
    print(ds, 'base and queries identical to the original inputs; ground truth',
          'identical' if not gt else 'differs in ' + ', '.join(gt) + ' (BLAS rounding; not fatal)', flush=True)


def main():
    cfg = config.load()
    for ds in sys.argv[1:]:
        prepare(cfg, ds)
        compare_frozen(cfg, ds)


if __name__ == '__main__':
    main()
