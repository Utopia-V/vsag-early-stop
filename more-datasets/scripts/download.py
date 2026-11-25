#!/usr/bin/env python3
"""Download the seven new public datasets of the ten-dataset measurement and check their SHA256.

usage: download.py [DATASET ...] [--remove-archives]

Sources and hashes are in more-datasets/frozen/sources.json (recorded from the files the original run read):
- GIST-960, SIFT-128, GloVe-100 and Deep-96 (HDF5 with train/test arrays) from https://ann-benchmarks.com/;
- COCO-I2I and COCO-T2I (512-d, FP16, HDF5) from the v0.1.3 release of github.com/fabiocarrara/str-encoders;
- Wiki-all 1M (768-d, fbin) from the RAPIDS archive wiki_all_1M.tar; only base.1M.fbin and queries.fbin are kept.
Every file is checked against its recorded SHA256; a mismatch stops the script. The hash of the Wiki-all archive was
not recorded, so its size is checked and the two members are checked by hash. Downloads resume with curl -C -.
Layout: DATA/<file> as named in sources.json (DATA = [paths] data of more-datasets/config.toml), about 12 GB.
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


def fetch(url, dest, sha=None, size=None):
    if dest.exists() and ((sha and digest(dest) == sha) or (not sha and dest.stat().st_size == size)):
        print('ok', dest.name, flush=True)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['curl', '-L', '--fail', '--retry', '5', '-C', '-', '-o', str(dest), url], check=True)
    if size is not None and dest.stat().st_size != size:
        raise SystemExit(f'{dest}: {dest.stat().st_size} bytes, expected {size}')
    if sha is not None and digest(dest) != sha:
        raise SystemExit(f'{dest}: sha256 {digest(dest)}, expected {sha}')
    print('ok', dest.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('datasets', nargs='*')
    parser.add_argument('--remove-archives', action='store_true', help='delete the Wiki-all archive after unpacking')
    args = parser.parse_args()
    data = config.load()['data']
    sources = json.loads((config.HERE / 'frozen' / 'sources.json').read_text())
    for ds in args.datasets or list(sources):
        entry = sources[ds]
        if 'archive' not in entry:
            for f in entry['files']:
                fetch(f['url'], data / f['file'], f['sha256'], f['bytes'])
            continue
        files = entry['files']
        if all((data / f['file']).exists() and digest(data / f['file']) == f['sha256'] for f in files):
            print('ok', ds, ' '.join(f['file'] for f in files), flush=True)
            continue
        archive = entry['archive']
        target = data / archive['file']
        fetch(archive['url'], target, archive['sha256'], archive['bytes'])
        folder = data / Path(files[0]['file']).parent
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(['tar', '-xf', str(target), '-C', str(folder), *[f['archive_member'] for f in files]], check=True)
        for f in files:
            value = digest(data / f['file'])
            if value != f['sha256']:
                raise SystemExit(f'{data / f["file"]}: sha256 {value}, expected {f["sha256"]}')
        print('ok', ds, ' '.join(f['file'] for f in files), flush=True)
        if args.remove_archives:
            target.unlink()


if __name__ == '__main__':
    main()
