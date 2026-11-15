#!/usr/bin/env python3
"""Turn the downloaded files into the HDF5 inputs of the experiments and compare them with the original inputs.

usage: prepare_inputs.py [dataset ...]

For each dataset, prepare_workload.py (the converter written for VSAG's eval tool) reads vectors.npy and tests.jsonl,
takes the calibration and held-out ("validation") query rows listed in frozen/workloads/<ds>/rows.json, and writes
work/inputs/<ds>/{base,calibration,validation}.hdf5 with exact top-100 ground truth (FP64 cosine over the FP32
vectors, ties by base row id). LAION's float16 base is widened to float32 value by value.

For DBpedia it also writes fresh.hdf5: the 2048 fresh query rows of frozen/workloads/dbpedia/fresh.json, taken from the
last parquet shard of the full 1M-row dataset, with ground truth computed the same way against the same base.

Finally every query, neighbour and distance array is hashed and compared with checksums/input-arrays.json (the arrays
of the original run). Query arrays must match exactly. Ground truth comes from a full FP64 matrix product; a different
BLAS can round its last bit differently and reorder near-tied neighbours, so a neighbour or distance mismatch is
reported, not fatal. Memory: the DBpedia ground truth holds an FP64 copy of the base (12 GB).
"""
import hashlib
import json
import sys

import h5py
import numpy as np
import pyarrow.parquet as pq

import config
import prepare_workload

DATASETS = ['dbpedia', 'cohere', 'laion']


def array_hash(value):
    little = value.astype(value.dtype.newbyteorder('<'), copy=False)
    return hashlib.sha256(np.ascontiguousarray(little).tobytes()).hexdigest()


def prepare(cfg, ds):
    out = cfg['inputs'] / ds
    if (out / 'manifest.json').exists():
        print(ds, 'inputs exist', flush=True)
        return
    frozen = config.FROZEN / 'workloads' / ds
    out.parent.mkdir(parents=True, exist_ok=True)
    prepare_workload.run(cfg['data'] / ds / 'vectors.npy', cfg['data'] / ds / 'tests.jsonl', frozen / 'rows.json', out,
                         frozen / 'source.json')
    print(ds, 'inputs written', flush=True)


def fresh_queries(parquet, base):
    """The 2048 fresh DBpedia queries, checked row by row against frozen/workloads/dbpedia/fresh.json."""
    spec = json.loads((config.FROZEN / 'workloads' / 'dbpedia' / 'fresh.json').read_text())
    column = pq.read_table(parquet, columns=[spec['source']['column']])[spec['source']['column']].combine_chunks()
    lengths = column.value_lengths().to_numpy()
    assert (lengths == base.shape[1]).all(), 'unexpected vector length in the parquet shard'
    vectors = column.flatten().to_numpy(zero_copy_only=False).reshape(len(column), base.shape[1]).astype('<f4')
    # The shard holds the last rows of the 1M-row dataset; its first rows overlap the end of the 975k base.
    start = 1_000_000 - len(vectors)
    overlap = len(base) - start
    assert 0 < overlap < len(vectors)
    assert np.array_equal(vectors[:overlap], base[start:]), 'parquet shard does not line up with the base'
    tail = vectors[overlap:]
    rows = [r['source_query_id'] - len(base) for r in spec['rows']]
    queries = np.ascontiguousarray(tail[rows])
    for row, r in zip(queries, spec['rows']):
        assert hashlib.sha256(row.tobytes()).hexdigest() == r['sha256'], r['source_query_id']
    assert hashlib.sha256(queries.tobytes()).hexdigest() == spec['selected_queries_sha256']
    return queries


def prepare_fresh(cfg):
    out = cfg['inputs'] / 'dbpedia' / 'fresh.hdf5'
    if out.exists():
        print('dbpedia fresh exists', flush=True)
        return
    spec = json.loads((config.FROZEN / 'workloads' / 'dbpedia' / 'fresh.json').read_text())
    base = np.load(cfg['data'] / 'dbpedia' / 'vectors.npy', mmap_mode='r')
    queries = fresh_queries(cfg['data'] / 'dbpedia-tail' / spec['source']['file'], base)
    ids, distances = prepare_workload.exact_cosine(np.asarray(base, dtype='<f4'), queries)
    prepare_workload.write_split(out, queries, ids, distances)
    print('dbpedia fresh written', flush=True)


def compare(cfg, datasets):
    expected = json.loads((config.PACKAGE / 'checksums' / 'input-arrays.json').read_text())['inputs']
    report = {}
    exact = True
    for key, entry in sorted(expected.items()):
        ds, role = key.split('/')
        if ds not in datasets:
            continue
        path = cfg['inputs'] / ds / f'{role}.hdf5'
        result = {}
        with h5py.File(path, 'r') as f:
            for name, want in entry['arrays'].items():
                value = f[name][:]
                same = array_hash(value) == want['sha256'] and list(value.shape) == want['shape']
                result[name] = dict(identical=same)
                exact &= same or name != 'test'
        report[key] = result
        print(key, ' '.join(f'{n}={"same" if v["identical"] else "DIFFERENT"}' for n, v in result.items()), flush=True)
    (cfg['inputs'] / 'array-check.json').write_text(json.dumps(report, indent=2) + '\n')
    if not exact:
        raise SystemExit('query arrays differ from the original inputs')


def main():
    cfg = config.load()
    datasets = sys.argv[1:] or DATASETS
    for ds in datasets:
        prepare(cfg, ds)
    if 'dbpedia' in datasets:
        prepare_fresh(cfg)
    compare(cfg, datasets)


if __name__ == '__main__':
    main()
