"""Read config.toml (or config.example.toml) and resolve every path the scripts use.

Relative paths in the config file are taken relative to the directory of that file. The environment variable
REPRO_CONFIG selects another config file.
"""
import os
from pathlib import Path
import tomllib

PACKAGE = Path(__file__).resolve().parent.parent
FROZEN = PACKAGE / 'frozen'
DIMS = {'dbpedia': 1536, 'cohere': 768, 'laion': 512}


def load(path=None):
    path = path or os.environ.get('REPRO_CONFIG')
    if path is None:
        path = PACKAGE / 'config.toml'
        if not path.exists():
            path = PACKAGE / 'config.example.toml'
    path = Path(path).resolve()
    raw = tomllib.loads(path.read_text())
    base = path.parent

    def resolve(value):
        value = Path(value).expanduser()
        return value if value.is_absolute() else base / value

    paths = raw.get('paths', {})
    work = resolve(paths.get('work', 'work'))
    cfg = dict(file=path, work=work)
    for name in ['data', 'inputs', 'indexes', 'run', 'builds']:
        cfg[name] = resolve(paths[name]) if name in paths else work / name

    datasets = {}
    for ds, dim in DIMS.items():
        override = raw.get('datasets', {}).get(ds, {})
        d = dict(dim=int(override.get('dim', dim)),
                 create=resolve(override.get('create', FROZEN / 'index' / f'{ds}.json')),
                 index=resolve(override.get('index', cfg['indexes'] / ds / 'hgraph.index')),
                 calibration=resolve(override.get('calibration', cfg['inputs'] / ds / 'calibration.hdf5')),
                 validation=resolve(override.get('validation', cfg['inputs'] / ds / 'validation.hdf5')))
        if ds == 'dbpedia':
            d['fresh'] = resolve(override.get('fresh', cfg['inputs'] / ds / 'fresh.hdf5'))
        datasets[ds] = d
    cfg['datasets'] = datasets

    libraries = {}
    for role, value in raw.get('libraries', {}).items():
        if not isinstance(value, dict):
            continue
        build = cfg['builds'] / role
        libraries[role] = dict(commit=value.get('commit'),
                               source=resolve(value.get('source', build / 'src')),
                               build=resolve(value.get('build', build / 'build-release')),
                               lib=resolve(value.get('lib', build / 'build-release' / 'src')),
                               helpers=resolve(value.get('helpers', build / 'helpers')))
    cfg['libraries'] = libraries
    roles = raw.get('libraries', {})
    cfg['quality_library'] = roles.get('quality', 'pr')
    cfg['timing_candidate'] = roles.get('timing_candidate', 'pr')
    cfg['timing_reference'] = roles.get('timing_reference', 'upstream')
    cfg['native_recall'] = resolve(raw.get('quality', {}).get(
        'native_recall', libraries.get(cfg['quality_library'], {}).get('helpers', cfg['builds']) / 'native_recall.so'))

    selection = raw.get('selection', {})
    cfg['fixed_points'] = resolve(selection.get('fixed_points', FROZEN / 'fixed-points.json'))
    cfg['margins'] = {float(c): float(m) for c, m in
                      selection.get('margins', {'0.90': 0.05, '0.95': 0.05, '0.99': 0.25}).items()}

    quality = raw.get('quality', {})
    cfg['quality_cpus'] = [int(c) for c in quality.get('cpus', list(range(0, 8)) + list(range(16, 24)))]
    cfg['processes'] = {ds: int(n) for ds, n in quality.get('processes', {'dbpedia': 5, 'cohere': 6,
                                                                          'laion': 6}).items()}

    timing = raw.get('timing', {})
    cfg['timing_threads'] = [int(t) for t in timing.get('threads', [1, 8])]
    cfg['timing_affinity'] = {int(t): str(a) for t, a in timing.get('affinity', {'1': '8', '8': '8-15'}).items()}
    cfg['timing_output'] = timing.get('output', 'timing-results')
    cfg['timing_max_load'] = float(timing.get('max_load', 2.0))

    index = raw.get('index', {})
    cfg['build_cpus'] = str(index.get('cpus', '0-11'))
    return cfg
