#!/usr/bin/env python3
# Copyright 2024-present the vsag project
# SPDX-License-Identifier: Apache-2.0
"""Convert unfiltered dense cosine NPY/JSONL workloads to native eval inputs."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

import h5py
import numpy as np


ROLES = ("calibration", "validation")
BASE_CHUNK_ROWS = 4096


def write_json(path, value):
    # Exclusive creation also refuses dangling symlinks.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def file_identity(path):
    """Hash a regular file and reject changes while reading it."""
    path = Path(path).absolute()
    resolved = path.resolve(strict=True)
    before = resolved.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"input must be a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError(f"file changed while opening: {path}")
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if path.resolve(strict=True) != resolved or any(
            getattr(before, field) != getattr(after, field) for field in fields):
        raise ValueError(f"file changed while hashing: {path}")
    return {"path": str(path), "resolved_path": str(resolved), "bytes": before.st_size,
            "sha256": digest.hexdigest(), "device": before.st_dev, "inode": before.st_ino,
            "mtime_ns": before.st_mtime_ns, "ctime_ns": before.st_ctime_ns}


def verify_inputs(identities):
    for name, expected in identities.items():
        if file_identity(expected["path"]) != expected:
            raise ValueError(f"input identity changed: {name}")


def load_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def load_rows(path):
    rows = load_json(path)
    if not isinstance(rows, dict) or set(rows) != set(ROLES):
        raise ValueError("rows must contain exactly calibration and validation")
    for role in ROLES:
        if not isinstance(rows[role], list) or not rows[role]:
            raise ValueError(f"{role} rows must be a nonempty ordered list")
        for row in rows[role]:
            if isinstance(row, bool) or not isinstance(row, int) or row < 0:
                raise ValueError(f"{role} source row must be a nonnegative integer")
    return rows


def content_hash(query):
    canonical = np.array(query, dtype="<f4", copy=True)
    canonical[canonical == 0] = 0  # +/- zero are the same content, not different roles.
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def valid_vectors(values, description):
    if not np.isfinite(values).all():
        raise ValueError(f"{description} contains nonfinite values")
    if np.any(np.linalg.norm(values.astype(np.float64), axis=1) == 0):
        raise ValueError(f"{description} contains a zero cosine norm")


def read_queries(path, rows, dim):
    selected = set(rows["calibration"]) | set(rows["validation"])
    queries = {}
    with path.open("rb") as stream:
        for source_row, line in enumerate(stream):
            if source_row not in selected:
                continue
            try:
                record = json.loads(line)
            except (ValueError, UnicodeError) as error:
                raise ValueError(f"invalid JSON at selected query row {source_row}") from error
            if not isinstance(record, dict):
                raise ValueError(f"query row {source_row} must be an object")
            # Public unfiltered records use missing/null (Cohere) or empty
            # arrays/objects. Do not accept false/zero as null aliases.
            conditions = record.get("conditions")
            if not (conditions is None or
                    isinstance(conditions, (list, dict)) and len(conditions) == 0):
                raise ValueError(f"query row {source_row} has unsupported filter conditions")
            value = record.get("query")
            if (not isinstance(value, list) or len(value) != dim or
                    any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in value)):
                raise ValueError(f"query row {source_row} must contain {dim} real numbers")
            try:
                with np.errstate(over="ignore", invalid="ignore"):
                    query = np.asarray(value, dtype="<f4")
            except (ValueError, OverflowError) as error:
                raise ValueError(f"invalid FP32 query row {source_row}") from error
            valid_vectors(query[None], f"query row {source_row}")
            queries[source_row] = query
    missing = selected - queries.keys()
    if missing:
        raise ValueError(f"selected query rows do not exist: {sorted(missing)}")
    arrays, mapping, role_hashes = {}, {}, {}
    for role in ROLES:
        arrays[role] = np.stack([queries[row] for row in rows[role]])
        mapping[role] = [{"source_row": row, "output_row": output_row,
                          "content_sha256": content_hash(queries[row])}
                         for output_row, row in enumerate(rows[role])]
        role_hashes[role] = {entry["content_sha256"] for entry in mapping[role]}
    if role_hashes["calibration"] & role_hashes["validation"]:
        raise ValueError("calibration and validation overlap in FP32 query content")
    return arrays, mapping, role_hashes


def check_source_manifest(source, inputs, base):
    if not isinstance(source, dict):
        raise ValueError("source manifest must be an object")
    for name in ("base", "queries"):
        expected = source.get(name)
        if not isinstance(expected, dict):
            raise ValueError(f"source manifest must contain {name}")
        sha = expected.get("sha256")
        if (not isinstance(sha, str) or len(sha) != 64 or
                any(char not in "0123456789abcdef" for char in sha)):
            raise ValueError(f"source {name}.sha256 must be a lowercase SHA256")
        if sha != inputs[name]["sha256"]:
            raise ValueError(f"source {name} SHA256 mismatch")
    shape = source["base"].get("shape")
    if (not isinstance(shape, list) or len(shape) != 2 or
            any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in shape) or
            shape != list(base.shape)):
        raise ValueError("source base shape mismatch")
    dtype = source["base"].get("dtype")
    if not isinstance(dtype, str):
        raise ValueError("source base dtype must be a NumPy dtype string")
    try:
        expected_dtype = np.dtype(dtype)
    except TypeError as error:
        raise ValueError("invalid source base dtype") from error
    if expected_dtype != base.dtype:
        raise ValueError("source base dtype mismatch")


def exact_cosine(base, queries, depth=100, batch=32):
    """Full FP64 cosine scores; ties ordered by the original zero-based base ID."""
    # A single FP64 copy avoids a redundant temporary without changing the
    # normalize/matmul/partition/lexsort numerical path.
    normalized = np.array(base, dtype=np.float64, copy=True)
    normalized /= np.linalg.norm(normalized, axis=1)[:, None]
    queries = np.array(queries, dtype=np.float64, copy=True)
    queries /= np.linalg.norm(queries, axis=1)[:, None]
    ids = np.empty((len(queries), depth), dtype="<i8")
    distances = np.empty((len(queries), depth), dtype="<f4")
    for begin in range(0, len(queries), batch):
        scores = queries[begin:begin + batch] @ normalized.T
        for offset, row in enumerate(scores):
            threshold = np.partition(row, -depth)[-depth]
            candidates = np.flatnonzero(row >= threshold)
            order = np.lexsort((candidates, -row[candidates]))[:depth]
            selected = candidates[order]
            ids[begin + offset] = selected
            distances[begin + offset] = 1.0 - row[selected]
        print(json.dumps({"exact_queries_done": min(begin + batch, len(queries)),
                          "total": len(queries)}), flush=True)
    return ids, distances


def write_base(path, base):
    with h5py.File(path, "x") as output:
        output.attrs["distance"] = np.bytes_("angular")
        output.attrs["type"] = np.bytes_("dense")
        train = output.create_dataset("train", shape=base.shape, dtype="<f4")
        for begin in range(0, len(base), BASE_CHUNK_ROWS):
            source = base[begin:begin + BASE_CHUNK_ROWS]
            converted = np.asarray(source, dtype="<f4")
            valid_vectors(converted, f"base rows starting at {begin}")
            if base.dtype.itemsize == 2:
                original = np.asarray(source, dtype="<f2").tobytes(order="C")
                restored = converted.astype("<f2").tobytes(order="C")
                if original != restored:
                    raise ValueError(f"FP16 roundtrip failed at base row {begin}")
            train[begin:begin + len(converted)] = converted


def write_split(path, queries, ids, distances):
    with h5py.File(path, "x") as output:
        output.attrs["distance"] = np.bytes_("angular")
        output.attrs["type"] = np.bytes_("dense")
        output["train"] = h5py.ExternalLink("base.hdf5", "/train")
        for name, value in (("test", queries), ("neighbors", ids), ("distances", distances)):
            output.create_dataset(name, data=value)


def run(base_path, queries_path, rows_path, output, source_manifest=None,
        truth_depth=100, query_batch=32):
    positive_integer(truth_depth, "truth depth")
    positive_integer(query_batch, "query batch")
    # Resolve the parent, never the final component: resolving a dangling
    # output symlink would silently create its target instead of refusing it.
    output = Path(output).expanduser().absolute()
    output = output.parent.resolve(strict=True) / output.name
    output.mkdir(exist_ok=False)
    try:
        paths = {"base": Path(base_path), "queries": Path(queries_path), "rows": Path(rows_path),
                 "producer": Path(__file__)}
        if source_manifest is not None:
            paths["source_manifest"] = Path(source_manifest)
        inputs = {name: file_identity(path) for name, path in paths.items()}
        write_json(output / "request.json", {
            "schema_version": 1, "inputs": inputs, "truth_depth": truth_depth,
            "query_batch": query_batch, "created_at": datetime.now(timezone.utc).isoformat()})
        rows = load_rows(paths["rows"])
        try:
            base = np.load(paths["base"], mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError, EOFError) as error:
            raise ValueError("base must be a readable float16/float32 NPY array") from error
        if (not isinstance(base, np.ndarray) or base.ndim != 2 or
                min(base.shape) <= 0 or base.dtype.kind != "f" or base.dtype.itemsize not in (2, 4)):
            raise ValueError("base must be a nonempty two-dimensional float16/float32 NPY array")
        if truth_depth > len(base):
            raise ValueError("truth depth exceeds the base row count")
        source = load_json(paths["source_manifest"]) if source_manifest is not None else None
        if source_manifest is not None:
            check_source_manifest(source, inputs, base)
        arrays, mapping, role_hashes = read_queries(paths["queries"], rows, base.shape[1])
        verify_inputs(inputs)
        write_base(output / "base.hdf5", base)
        # Use the exact FP32 values that native eval receives, including the
        # value-preserving FP16 expansion. No normalization is saved to HDF5.
        all_queries = np.concatenate([arrays[role] for role in ROLES])
        ids, distances = exact_cosine(np.asarray(base, dtype="<f4"), all_queries,
                                      truth_depth, query_batch)
        offset = 0
        for role in ROLES:
            count = len(arrays[role])
            write_split(output / f"{role}.hdf5", arrays[role], ids[offset:offset + count],
                        distances[offset:offset + count])
            offset += count
        manifest = {
            "schema_version": 1, "status": "complete", "inputs": inputs,
            "source_manifest": source,
            "versions": {"python": sys.version, "numpy": np.__version__,
                         "h5py": h5py.__version__, "hdf5": h5py.version.hdf5_version},
            "base": {"source_shape": list(base.shape), "source_dtype": base.dtype.str,
                     "stored_dtype": "<f4", "stored_normalized": False,
                     "id_semantics": "zero-based source base row; unchanged order",
                     "conversion": "value-preserving float16 expansion" if base.dtype.itemsize == 2
                     else "float32 values preserved; little-endian storage",
                     "fp16_all_values_roundtrip_verified": base.dtype.itemsize == 2},
            "ground_truth": {"metric": "cosine", "hdf5_distance": "angular",
                             "algorithm": "FP32 values converted to FP64; row L2 normalization; full matmul; partition then lexsort(-score, base row ID)",
                             "depth": truth_depth, "query_batch": query_batch,
                             "neighbors_dtype": "<i8", "distances_dtype": "<f4",
                             "distance_formula": "float32(1 - FP64 cosine score)",
                             "source_closest_ids_and_scores": "ignored"},
            "queries": {"stored_dtype": "<f4", "stored_normalized": False,
                        "content_hash_semantics": "SHA256 of C-order little-endian FP32 values; +/- zero canonicalized only for hashing",
                        "cross_role_content_overlap": 0,
                        "roles": {role: {"row_count": len(rows[role]),
                                         "unique_content_count": len(role_hashes[role]),
                                         "rows": mapping[role]} for role in ROLES}},
            "outputs": {name: file_identity(output / name) for name in
                        ("base.hdf5", "calibration.hdf5", "validation.hdf5")},
            "external_train_link": {"filename": "base.hdf5", "path": "/train"},
        }
        verify_inputs(inputs)
        write_json(output / "manifest.json", manifest)
        return manifest
    except Exception as error:
        write_json(output / "error.json", {"status": "failed", "error_type": type(error).__name__,
                                            "message": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path, help="vectors.npy")
    parser.add_argument("--queries", required=True, type=Path, help="tests.jsonl")
    parser.add_argument("--rows", required=True, type=Path, help="ordered source row lists JSON")
    parser.add_argument("--output", required=True, type=Path, help="new output directory")
    parser.add_argument("--source-manifest", type=Path, help="expected source hashes, shape and dtype")
    parser.add_argument("--truth-depth", type=int, default=100)
    parser.add_argument("--query-batch", type=int, default=32)
    args = parser.parse_args()
    try:
        run(args.base, args.queries, args.rows, args.output, args.source_manifest,
            args.truth_depth, args.query_batch)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
