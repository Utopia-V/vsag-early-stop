#!/usr/bin/env python3
"""Download the public datasets, check their SHA256 and unpack the files the experiments read.

usage: download.py [--remove-archives]

Qdrant's benchmark archives (listed in https://github.com/qdrant/vector-db-benchmark/blob/master/datasets/datasets.json)
for DBpedia OpenAI 1M, Cohere Wikipedia 1M and LAION 1M, and one parquet shard of the Hugging Face dataset
KShivendu/dbpedia-entities-openai-1M for the DBpedia fresh queries. Every file is checked against the hash recorded
in frozen/workloads; a mismatch stops the script. Downloads resume with curl -C -.
Layout: work/data/<archive>.tgz, work/data/<dataset>/{vectors.npy,tests.jsonl}, work/data/dbpedia-tail/<shard>.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import config


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def fetch(url, dest, sha):
    if dest.exists() and digest(dest) == sha:
        print('ok', dest.name, flush=True)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['curl', '-L', '--fail', '--retry', '5', '-C', '-', '-o', str(dest), url], check=True)
    value = digest(dest)
    if value != sha:
        raise SystemExit(f'{dest}: sha256 {value}, expected {sha}')
    print('ok', dest.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--remove-archives', action='store_true', help='delete each .tgz after unpacking it')
    args = parser.parse_args()
    data = config.load()['data']
    for ds in ['dbpedia', 'cohere', 'laion']:
        source = json.loads((config.FROZEN / 'workloads' / ds / 'source.json').read_text())
        folder = data / ds
        expected = {'vectors.npy': source['base']['sha256'], 'tests.jsonl': source['queries']['sha256']}
        if all((folder / name).exists() and digest(folder / name) == sha for name, sha in expected.items()):
            print('ok', ds, 'vectors.npy tests.jsonl', flush=True)
            continue
        archive = data / Path(source['archive']['url']).name
        fetch(source['archive']['url'], archive, source['archive']['sha256'])
        folder.mkdir(parents=True, exist_ok=True)
        # The archives hold vectors.npy, tests.jsonl and payloads.jsonl at the top level; payloads are not used.
        subprocess.run(['tar', '-xzf', str(archive), '-C', str(folder), 'vectors.npy', 'tests.jsonl'], check=True)
        for name, sha in expected.items():
            value = digest(folder / name)
            if value != sha:
                raise SystemExit(f'{folder / name}: sha256 {value}, expected {sha}')
        print('ok', ds, 'vectors.npy tests.jsonl', flush=True)
        if args.remove_archives:
            archive.unlink()
    fresh = json.loads((config.FROZEN / 'workloads' / 'dbpedia' / 'fresh.json').read_text())['source']
    fetch(fresh['url'], data / 'dbpedia-tail' / fresh['file'], fresh['sha256'])


if __name__ == '__main__':
    main()
