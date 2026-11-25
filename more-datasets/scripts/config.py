"""Read more-datasets/config.toml (or config.example.toml) and resolve every path the ten-dataset scripts use.

Generalised copy of scripts/config.py: the datasets come from a registry ([datasets.NAME] in the config file) with
dimension and metric instead of the three hard-wired cosine datasets. A new dataset's inputs live in
INPUTS/NAME/{base,calibration,validation}.hdf5 (prepare.py), its create parameters in INDEXES/NAME/create.json and its
index in INDEXES/NAME/hgraph.index (build_indexes.py); the three original datasets point at the inputs and indexes of
the first measurement. Relative paths in the config file are taken relative to the directory of that file.
Environment: REPRO_CONFIG selects another config file; RECAL_RUN selects the run directory of one stage (as in
scripts/recalibrate.py); RECAL_CPUS (taskset list, e.g. "0-7,16-23") overrides the CPUs of the quality processes for
one invocation; RECAL_TIERS (e.g. "0.99" or "0.80,0.98") restricts the coverage tiers.
"""
import os
from pathlib import Path
import tomllib

HERE = Path(__file__).resolve().parent.parent      # more-datasets/
PACKAGE = HERE.parent                               # the package root
FROZEN = PACKAGE / 'frozen'                         # frozen files of the first measurement (three original datasets)
MANIFESTS = HERE / 'frozen' / 'inputs'              # input manifests of the seven new datasets (NAME/manifest.json.xz)


def cpu_list(text):
    out = []
    for part in str(text).split(','):
        if '-' in part:
            a, b = part.split('-')
            out += list(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return out


def config_path(path=None):
    path = path or os.environ.get('REPRO_CONFIG')
    if path is None:
        path = HERE / 'config.toml'
        if not path.exists():
            path = HERE / 'config.example.toml'
    return Path(path).resolve()


def load(path=None):
    path = config_path(path)
    raw = tomllib.loads(path.read_text())
    base = path.parent

    def resolve(value):
        value = Path(value).expanduser()
        return value if value.is_absolute() else base / value

    paths = raw.get('paths', {})
    cfg = dict(file=path)
    work = resolve(paths.get('work', '../work/more-datasets'))
    cfg['work'] = work
    for name, default in [('data', '../work/data'), ('inputs', '../work/inputs'), ('indexes', '../work/indexes'),
                          ('builds', '../work/builds/more-datasets')]:
        cfg[name] = resolve(paths.get(name, default))
    cfg['tables'] = resolve(paths['tables']) if 'tables' in paths else work / 'tables'
    cfg['run'] = resolve(paths['run']) if 'run' in paths else work / 'c99'

    quality = raw.get('quality', {})
    datasets = {}
    for ds, d in raw['datasets'].items():
        # create/index/calibration/validation may point at existing files (the three original datasets).
        datasets[ds] = dict(dim=int(d['dim']), metric=d['metric'], source=d.get('source'), label=d.get('label', ds),
                            create=resolve(d.get('create', cfg['indexes'] / ds / 'create.json')),
                            index=resolve(d.get('index', cfg['indexes'] / ds / 'hgraph.index')),
                            calibration=resolve(d.get('calibration', cfg['inputs'] / ds / 'calibration.hdf5')),
                            validation=resolve(d.get('validation', cfg['inputs'] / ds / 'validation.hdf5')),
                            processes=int(d.get('processes', 8)))
    cfg['datasets'] = datasets
    cfg['raw_datasets'] = raw['datasets']

    libraries = {}
    for role, value in raw.get('libraries', {}).items():
        if not isinstance(value, dict):
            continue
        build = cfg['builds'] / role
        libraries[role] = dict(commit=value.get('commit'),
                               source=resolve(value.get('source', build / 'src')),
                               build=resolve(value.get('build', build / 'build-release')),
                               helpers=resolve(value.get('helpers', build / 'helpers')))
        libraries[role]['lib'] = resolve(value.get('lib', libraries[role]['build'] / 'src'))
    cfg['libraries'] = libraries
    roles = raw.get('libraries', {})
    cfg['quality_library'] = roles.get('quality', 'pr')
    cfg['timing_candidate'] = roles.get('timing_candidate', 'pr')
    cfg['timing_reference'] = roles.get('timing_reference', 'ref')
    cfg['helpers'] = {role: lib['helpers'] for role, lib in libraries.items()}
    cfg['native_recall'] = libraries.get(cfg['quality_library'], {}).get('helpers', cfg['builds']) / 'native_recall.so'

    selection = raw.get('selection', {})
    cfg['fixed_points'] = resolve(selection.get('fixed_points', work / 'fixed-ef' / 'fixed-points.json'))
    cfg['margins'] = {float(c): float(m) for c, m in
                      selection.get('margins', {'0.90': 0.05, '0.95': 0.05, '0.99': 0.25}).items()}
    tiers = os.environ.get('RECAL_TIERS') or selection.get('tiers')
    cfg['tiers'] = sorted(float(t) for t in str(tiers).split(',')) if tiers else [0.90, 0.95, 0.99]

    cpus = os.environ.get('RECAL_CPUS') or quality.get('cpus', '0-7,16-31')
    cfg['quality_cpus'] = cpu_list(cpus)

    timing = raw.get('timing', {})
    cfg['timing_threads'] = [int(t) for t in timing.get('threads', [1, 8])]
    cfg['timing_affinity'] = {int(t): str(a) for t, a in timing.get('affinity', {'1': '8', '8': '8-15'}).items()}
    cfg['timing_max_load'] = float(timing.get('max_load', 2.0))

    index = raw.get('index', {})
    cfg['build_cpus'] = str(index.get('cpus', '0-7,16-19'))
    cfg['index_param'] = index.get('param', {})
    return cfg


_CFG = load()
WORK = _CFG['work']        # run outputs: c99/, lvl/, l95/, fixed-ef/, gap/, orig/, freeef/, mean-recall/
TABLES = _CFG['tables']    # headline.md/json, per-dataset tables, points.json, check.json
