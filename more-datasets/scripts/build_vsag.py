#!/usr/bin/env python3
"""Check out VSAG at the PR head b98e87ab and at its upstream base 4a9c99ba, build both in Release, then the helpers.

usage: build_vsag.py [--roles pr ref] [--jobs N] [--helpers-only]

The ten-dataset counterpart of scripts/build_vsag.py; only the commits, the library file name (libvsag.so.1.1.0) and
the recall helper differ. For every library role in more-datasets/config.toml ([libraries.ROLE], default pr and ref):
1. a detached git worktree of https://github.com/antgroup/vsag at the role's commit (BUILDS/ROLE/src); if GitHub no
   longer serves the PR commit, the PR tree is rebuilt from vsag-patches/pr3149-b98e87ab.diff on top of the upstream
   base and checked against the PR head's tree hash;
2. a Release build of the targets vsag and hdf5 with the CMake options of the original builds (BUILDS/ROLE/
   build-release);
3. the helpers, compiled against that build (BUILDS/ROLE/helpers): native/multi_signature.cpp, native/timing.cpp and
   native/build_index.cpp of the package for every role, and more-datasets/native/native_recall.cpp (the package's
   angular_distances plus l2sqr_distances for the l2 datasets) for the role used by the quality phases.
build.json next to the helpers records the commands and the SHA256 of the library and of each helper (the original
values are in SHA256SUMS under original/libraries/pr-b98e87ab and ref-4a9c99ba).
--helpers-only skips steps 1-2 and uses the source/build trees configured in config.toml.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import config

URL = 'https://github.com/antgroup/vsag.git'
PR_REF = 'pull/3149/head'
PR_HEAD = 'b98e87abdd192ef5b3426a1fddc0266fcac73f93'
PR_TREE = '0538fc5941ae130b608a90f3d9484694532bf3c4'
UPSTREAM = '4a9c99bae6e7abfc98095f3918745b863a179381'
PATCH = config.PACKAGE / 'vsag-patches' / 'pr3149-b98e87ab.diff'
LIBRARY = 'libvsag.so.1.1.0'
CMAKE_OPTIONS = ['-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release', '-DENABLE_INTEL_MKL=OFF', '-DVSAG_USE_SYSTEM_DEPS=AUTO',
                 '-DENABLE_TESTS=ON', '-DENABLE_PYBINDS=OFF', '-DENABLE_EXAMPLES=OFF', '-DENABLE_LIBAIO=OFF',
                 '-DENABLE_TOOLS=ON', '-DENABLE_CCACHE=OFF',
                 '-DCMAKE_CXX_FLAGS=-Wno-error=stringop-overflow -Wno-error=stringop-overread']
NATIVE = config.PACKAGE / 'native'
RECALL = config.HERE / 'native' / 'native_recall.cpp'


def run(command, **kwargs):
    print('+', ' '.join(str(c) for c in command), flush=True)
    return subprocess.run([str(c) for c in command], check=True, **kwargs)


def git(*args, cwd, check=True, capture=False):
    result = subprocess.run(['git', *args], cwd=cwd, check=check, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else result.returncode


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def clone(builds):
    repo = builds / 'vsag'
    if not (repo / '.git').exists():
        builds.mkdir(parents=True, exist_ok=True)
        run(['git', 'clone', '--filter=blob:none', '--no-checkout', URL, repo])
    return repo


def has_commit(repo, sha):
    return git('cat-file', '-e', f'{sha}^{{commit}}', cwd=repo, check=False) == 0


def checkout(repo, role, commit, source):
    if (source / '.git').exists():
        head = git('rev-parse', 'HEAD', cwd=source, capture=True)
        tree = git('rev-parse', 'HEAD^{tree}', cwd=source, capture=True)
        dirty = git('status', '--porcelain', cwd=source, capture=True)
        if head == commit or (commit == PR_HEAD and dirty and git('write-tree', cwd=source, capture=True) == PR_TREE):
            return
        raise SystemExit(f'{source} exists at {head} (tree {tree}), expected {commit}')
    if not has_commit(repo, commit):
        git('fetch', 'origin', commit, cwd=repo, check=False)
    if not has_commit(repo, commit) and commit == PR_HEAD:
        git('fetch', 'origin', PR_REF, cwd=repo, check=False)
    if has_commit(repo, commit):
        run(['git', '-C', repo, 'worktree', 'add', '--detach', source, commit])
        return
    if commit != PR_HEAD:
        raise SystemExit(f'commit {commit} is not available from {URL}')
    # The PR branch may have been rebased since; rebuild its tree from the upstream base and the saved diff.
    if not has_commit(repo, UPSTREAM):
        git('fetch', 'origin', UPSTREAM, cwd=repo)
    run(['git', '-C', repo, 'worktree', 'add', '--detach', source, UPSTREAM])
    run(['git', '-C', source, 'apply', '--index', PATCH])
    tree = git('write-tree', cwd=source, capture=True)
    if tree != PR_TREE:
        raise SystemExit(f'patched tree {tree} differs from the PR head tree {PR_TREE}')
    print(f'{role}: rebuilt the PR head tree {PR_TREE} from {PATCH.name}', flush=True)


def build(source, tree, jobs):
    if not (tree / 'build.ninja').exists():
        run(['cmake', '-S', source, '-B', tree, *CMAKE_OPTIONS])
    run(['cmake', '--build', tree, '--parallel', str(jobs), '--target', 'vsag', 'hdf5'])


def helpers(role, lib_cfg, with_recall):
    source, tree, lib, out = lib_cfg['source'], lib_cfg['build'], lib_cfg['lib'], lib_cfg['helpers']
    out.mkdir(parents=True, exist_ok=True)
    hdf5 = tree / 'hdf5' / 'install'
    record = dict(role=role, commit=lib_cfg['commit'], source=str(source), build=str(tree),
                  library=dict(path=str(lib / LIBRARY), sha256=digest(lib / LIBRARY)),
                  helpers={}, built_at_utc=datetime.now(timezone.utc).isoformat())
    for name in ['multi_signature', 'timing', 'build_index']:
        command = ['c++', '-O2', '-std=c++17', '-fopenmp', NATIVE / f'{name}.cpp', f'-I{source / "include"}',
                   f'-I{hdf5 / "include"}', f'-L{lib}', '-lvsag', hdf5 / 'lib' / 'libhdf5_cpp.a',
                   hdf5 / 'lib' / 'libhdf5.a', '-lz', '-ldl', '-o', out / name]
        run(command)
        record['helpers'][name] = dict(command=[str(c) for c in command], sha256=digest(out / name))
    if with_recall:
        # The recall check reuses the library's own AVX-512 kernels (inner product for cosine, squared L2 for l2), so
        # recall is computed with the same float arithmetic as the search.
        command = ['c++', '-shared', '-fPIC', '-std=c++17', '-O3', '-Ofast', '-Wl,-z,defs', f'-I{source / "src"}',
                   RECALL, tree / 'src' / 'simd' / 'libsimd.a',
                   tree / '_deps' / 'cpuinfo-build' / 'libcpuinfo.a', '-lpthread', '-o', out / 'native_recall.so']
        run(command)
        record['helpers']['native_recall.so'] = dict(command=[str(c) for c in command],
                                                     sha256=digest(out / 'native_recall.so'))
    (out / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    print(role, 'library', record['library']['sha256'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--roles', nargs='+')
    parser.add_argument('--jobs', type=int, default=os.cpu_count())
    parser.add_argument('--helpers-only', action='store_true')
    args = parser.parse_args()
    cfg = config.load()
    roles = args.roles or list(cfg['libraries'])
    if not args.helpers_only:
        repo = clone(cfg['builds'])
        for role in roles:
            lib_cfg = cfg['libraries'][role]
            checkout(repo, role, lib_cfg['commit'], lib_cfg['source'])
            build(lib_cfg['source'], lib_cfg['build'], args.jobs)
    for role in roles:
        helpers(role, cfg['libraries'][role], role == cfg['quality_library'])


if __name__ == '__main__':
    main()
