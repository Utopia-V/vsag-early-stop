#!/usr/bin/env python
"""Regenerate report/data/points.csv, report/tables.md and report/figures/*.{png,svg} from the result files.

usage: make_report_assets.py [--out DIR] [--timing DIR] [--summary FILE] [--keep-noisy]

Defaults: the delivered results in results/ and the package's report/ directory. --timing and --summary point to a
rerun instead (the timing-results directory of recalibrate.py timing and the summary-<lib>.json of its report phase).
This is the script that made the final report's tables and figures; in the package the input paths became arguments
and the cross-check against the superseded v3 report was dropped. Figures need a CJK font (Noto Sans CJK SC) for the
Chinese labels.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

PACKAGE = Path(__file__).resolve().parent.parent
FILES = {'summary-v4.json': PACKAGE / 'results/quality/summary-v4.json',
         'timing-results-v6/batches.json': PACKAGE / 'results/timing/v6/batches.json',
         'timing-results-v6/plan.json': PACKAGE / 'results/timing/v6/plan.json',
         'timing-summary-v6.json': PACKAGE / 'results/timing/timing-summary-v6.json'}
OUT = PACKAGE / 'report'
DATASETS = ['dbpedia', 'cohere', 'laion']
DSNAME = {'dbpedia': 'DBpedia', 'cohere': 'Cohere', 'laion': 'LAION'}
TIERS = [0.99, 0.95, 0.90]
TIER_CODE = {0.90: 'c90', 0.95: 'c95', 0.99: 'c99'}
warnings = []


def load(p):
    return json.loads(FILES[p].read_text())


def med(v):
    return float(np.median(v))


# ---------- timing: same method as recalibrate.py timing_report (median of 4 repeats, ratio of medians) ----------
def timing(exclude_noisy=True):
    rows = load('timing-results-v6/batches.json')
    if exclude_noisy:
        rows = [r for r in rows if not r['noisy_background']]
    cells = {}
    for r in rows:
        cells.setdefault((r['dataset'], r['point'], r['threads']), {}).setdefault(r['arm'], []).append(r)
    out = {}
    for key, arms in cells.items():
        m = {a: {k: med([r[k] for r in v]) for k in ['qps', 'mean_ms', 'p99_ms']} for a, v in arms.items()}
        for a, v in arms.items():
            m[a]['n'] = len(v)
            m[a]['noisy'] = 0
        out[key] = m
    if exclude_noisy:
        for r in load('timing-results-v6/batches.json'):
            if r['noisy_background']:
                out[(r['dataset'], r['point'], r['threads'])][r['arm']]['noisy'] += 1
    return out


def pct(a, b):
    return 100 * (a / b - 1)


# ---------- quality: summary-v4.json (library v4; v6 verified byte-identical by compare-v4-v6.json) ----------
def quality():
    s = load('summary-v4.json')
    return {(q['dataset'], q['point']): q for q in s['points']}


def build_rows(Q, T, plan):
    rows = []
    for tier in TIERS:
        for ds in DATASETS:
            for k in (10, 100):
                for R in (0.80, 0.90, 0.95):
                    pt = f'{TIER_CODE[tier]}-k{k}-r{int(round(R * 100))}'
                    q = Q[(ds, pt)]
                    h = q['held_out']
                    p = plan[f'{ds}-k{k}']
                    base = dict(tier=tier, dataset=ds, k=k, R=R, point=pt, fixed_ef=q['fixed_ef'])
                    fixed_ok = h['fixed']['quality_pass']
                    if q['auto_off'] or h.get('rule_cm') is None:  # auto-off, or no alpha qualified (rerun)
                        assert all('on' not in T.get((ds, pt, th), {}) for th in (1, 8))
                        for th in (1, 8):
                            rows.append({**base, 'threads': th, 'arm': 'on', 'alpha': 'auto-off' if q['auto_off'] else 'none',
                                         'cov_fixed': h['fixed']['coverage'], 'cov_es': '', 'loss_pt': '', 'saving_pct': '',
                                         'pass': 'fixed' if fixed_ok else 'fail',
                                         'reason': 'ef<=1.25k, early stop auto-off, fixed search used (not timed)' if q['auto_off'] else 'no alpha qualified on the calibration queries, fixed search used (not timed)'})
                        continue
                    cm = h['rule_cm']
                    pa = p['on'][pt]['hgraph']
                    if abs(pa['early_stop']['alpha'] - cm['alpha']) > 1e-9 or p['ref'][pt]['hgraph']['ef_search'] != q['fixed_ef']:
                        warnings.append(f'plan/summary mismatch {ds} {pt}')
                    es_ok = cm['quality_pass']
                    passed = fixed_ok and es_ok
                    reason = '' if passed else ('fixed baseline misses C on held-out' if not fixed_ok else 'early stop misses C or loss > 0.5pt')
                    arms = {'on': dict(alpha=cm['alpha'], cov_es=cm['coverage'], loss=cm['mean_loss'], sav=cm['saving_pct'], ok=passed, reason=reason),
                            'default': dict(alpha=h['default']['alpha'], cov_es=h['default']['coverage'], loss=h['default']['mean_loss'],
                                            sav=h['default']['saving_pct'], ok=fixed_ok and h['default']['quality_pass'],
                                            reason='' if fixed_ok and h['default']['quality_pass'] else ('fixed baseline misses C on held-out' if not fixed_ok else 'early stop misses C or loss > 0.5pt')),
                            'off': dict(alpha='off', cov_es=h['fixed']['coverage'], loss=0.0, sav=0.0, ok=fixed_ok, reason='' if fixed_ok else 'fixed baseline misses C on held-out')}
                    for th in (1, 8):
                        t = T[(ds, pt, th)]
                        for arm, a in arms.items():
                            if arm not in t:
                                continue
                            if arm == 'default' and 'alpha' in p['default'][pt]['hgraph']['early_stop']:
                                warnings.append(f'default arm has explicit alpha {ds} {pt}')
                            r = {**base, 'threads': th, 'arm': arm, 'alpha': a['alpha'],
                                 'cov_fixed': h['fixed']['coverage'], 'cov_es': a['cov_es'], 'loss_pt': 100 * a['loss'],
                                 'saving_pct': a['sav'],
                                 'qps_ref': t['ref']['qps'], 'qps_arm': t[arm]['qps'], 'qps_pct': pct(t[arm]['qps'], t['ref']['qps']),
                                 'mean_ms_ref': t['ref']['mean_ms'], 'mean_ms_arm': t[arm]['mean_ms'], 'mean_pct': pct(t[arm]['mean_ms'], t['ref']['mean_ms']),
                                 'p99_ms_ref': t['ref']['p99_ms'], 'p99_ms_arm': t[arm]['p99_ms'], 'p99_pct': pct(t[arm]['p99_ms'], t['ref']['p99_ms']),
                                 'repeats_ref': t['ref']['n'], 'repeats_arm': t[arm]['n'],
                                 'noisy_batches': t['ref']['noisy'] + t[arm]['noisy'],
                                 'pass': 'pass' if a['ok'] else 'fail', 'reason': a['reason']}
                            rows.append(r)
    return rows


COLS = ['tier', 'dataset', 'k', 'R', 'point', 'threads', 'arm', 'fixed_ef', 'alpha', 'cov_fixed', 'cov_es', 'loss_pt', 'saving_pct',
        'qps_ref', 'qps_arm', 'qps_pct', 'mean_ms_ref', 'mean_ms_arm', 'mean_pct', 'p99_ms_ref', 'p99_ms_arm', 'p99_pct',
        'repeats_ref', 'repeats_arm', 'noisy_batches', 'pass', 'reason']


def write_csv(rows):
    with open(OUT / 'data/points.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, COLS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({c: (f'{r[c]:.6g}' if isinstance(r.get(c), float) else r.get(c, '')) for c in COLS})


# ---------- tables ----------
def s3(x):
    """3 significant digits without exponent."""
    if x == 0:
        return '0'
    d = int(np.floor(np.log10(abs(x))))
    n = max(0, 2 - d)
    v = round(x, n)
    return f'{v:.{n}f}'


def sp(x):
    return f'{x:+.1f}%'


def fq(x):
    return f'{x:,.0f}'


def cov(x):
    return f'{100 * x:.2f}%'


def main_table(rows, tier):
    hdr = ['数据集', 'k', 'R', 'ef_search', 'alpha', '召回覆盖率 固定→早停', '平均召回损失 (pt)', '距离计算节省', '线程',
           'QPS 上游 main→早停', 'QPS 变化', '平均延迟 ms 上游 main→早停', '平均延迟变化', 'P99 ms 上游 main→早停', 'P99 变化', '结果']
    lines = ['| ' + ' | '.join(hdr) + ' |', '|' + '|'.join(['---'] * 5 + ['---:'] * 0 + ['---'] * (len(hdr) - 5)) + '|']
    for r in rows:
        if r['tier'] != tier or r['arm'] != 'on':
            continue
        res = '通过' if r['pass'] == 'pass' else (('固定搜索（auto-off）' if r['alpha'] == 'auto-off' else '固定搜索') if r['pass'] == 'fixed' else '未通过：' + ('固定基线在保留组上未达到 C' if 'fixed' in r['reason'] else '早停未达 C 或损失超 0.5 pt'))
        if r['alpha'] in ('auto-off', 'none'):
            if r['threads'] == 8:
                continue
            lines.append(f"| {DSNAME[r['dataset']]} | {r['k']} | {r['R']:.2f} | {r['fixed_ef']} | {r['alpha']} | {cov(r['cov_fixed'])} | - | - | - | - | - | - | - | - | - | {res}{'（ef ≤ 1.25k，未计时）' if r['alpha'] == 'auto-off' else '（无合格 alpha，未计时）'} |")
            continue
        lines.append(f"| {DSNAME[r['dataset']]} | {r['k']} | {r['R']:.2f} | {r['fixed_ef']} | {r['alpha']} | {cov(r['cov_fixed'])}→{cov(r['cov_es'])} | {r['loss_pt']:.2f} | {r['saving_pct']:.1f}% | {r['threads']} | "
                     f"{fq(r['qps_ref'])}→{fq(r['qps_arm'])} | {sp(r['qps_pct'])} | {s3(r['mean_ms_ref'])}→{s3(r['mean_ms_arm'])} | {sp(r['mean_pct'])} | "
                     f"{s3(r['p99_ms_ref'])}→{s3(r['p99_ms_arm'])} | {sp(r['p99_pct'])} | {res} |")
    return '\n'.join(lines)


def overhead_table(rows):
    hdr = ['数据集', '点', 'ef_search', '线程', 'QPS 上游 main→关闭早停', 'QPS 变化', '平均延迟 ms 上游 main→关闭早停', '平均延迟变化', 'P99 ms 上游 main→关闭早停', 'P99 变化']
    lines = ['| ' + ' | '.join(hdr) + ' |', '|' + '|'.join(['---'] * len(hdr)) + '|']
    for r in rows:
        if r['arm'] != 'off':
            continue
        lines.append(f"| {DSNAME[r['dataset']]} | {r['point']} | {r['fixed_ef']} | {r['threads']} | {fq(r['qps_ref'])}→{fq(r['qps_arm'])} | {sp(r['qps_pct'])} | "
                     f"{s3(r['mean_ms_ref'])}→{s3(r['mean_ms_arm'])} | {sp(r['mean_pct'])} | {s3(r['p99_ms_ref'])}→{s3(r['p99_ms_arm'])} | {sp(r['p99_pct'])} |")
    return '\n'.join(lines)


def default_table(rows):
    hdr = ['点', '数据集', 'ef_search', 'default alpha', '距离计算节省', '线程', 'QPS 变化', '平均延迟变化', 'P99 变化', '结果']
    lines = ['| ' + ' | '.join(hdr) + ' |', '|' + '|'.join(['---'] * len(hdr)) + '|']
    for r in rows:
        if r['arm'] != 'default':
            continue
        lines.append(f"| {r['point']} | {DSNAME[r['dataset']]} | {r['fixed_ef']} | {r['alpha']} | {r['saving_pct']:.1f}% | {r['threads']} | {sp(r['qps_pct'])} | {sp(r['mean_pct'])} | {sp(r['p99_pct'])} | {'通过' if r['pass']=='pass' else '未通过'} |")
    return '\n'.join(lines)


def write_tables(rows, n_noisy):
    parts = [f'<!-- generated by make_report_assets.py; 上游 main = upstream main 7ea909b3, 早停 = PR 校准 alpha (rule C+m)。QPS/延迟/P99 为 4 次重复的中位数，百分比为中位数之比。已排除 harness 标记 noisy_background 的 {n_noisy} 个批次（均为 LAION k100 8 线程 ref，outer_repeat 3），这些点的中位数取自其余 3 次重复。 -->\n']
    names = {0.99: ('C = 0.99', '全部 18 个点'), 0.95: ('C = 0.95', ''), 0.90: ('C = 0.90', '')}
    for t in TIERS:
        parts.append(f'## {names[t][0]}\n')
        parts.append(main_table(rows, t) + '\n')
    parts.append('## 关闭早停 与 上游 main 的开销（off vs ref）\n')
    parts.append(overhead_table(rows) + '\n')
    parts.append('## 默认 alpha（default arm）\n')
    parts.append(default_table(rows) + '\n')
    (OUT / 'tables.md').write_text('\n'.join(parts))


# ---------- figures ----------
C_DS = {'dbpedia': '#2a78d6', 'cohere': '#eb6834', 'laion': '#1baf7a'}   # dataviz palette slots 1-3 (validated all-pairs)
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'


def setup_font():
    names = {f.name for f in font_manager.fontManager.ttflist}
    for n in ['Noto Sans CJK SC', 'Noto Sans CJK JP', 'Noto Serif CJK SC']:
        if n in names:
            plt.rcParams['font.sans-serif'] = [n, 'DejaVu Sans']
            plt.rcParams['font.family'] = 'sans-serif'
            break
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams.update({'axes.edgecolor': INK2, 'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK})


def tint(hexc, f):
    c = np.array(matplotlib.colors.to_rgb(hexc))
    return tuple(1 - (1 - c) * f)


def save(fig, name):
    for ext in ('png', 'svg'):
        fig.savefig(OUT / f'figures/{name}.{ext}', dpi=220, facecolor='white', bbox_inches='tight')
    plt.close(fig)


def grouped(rows, metric, tier, include_fail, ylabel, title, name, refline=None, note_fail=False, sharey=False):
    sel = {}
    for r in rows:
        if r['tier'] != tier or r['arm'] != 'on' or r['alpha'] in ('auto-off', 'none'):
            continue
        if r['pass'] != 'pass' and not include_fail:
            continue
        sel.setdefault(r['dataset'], {}).setdefault((r['k'], r['R']), {})[r['threads']] = r
    counts = [len(sel[d]) for d in DATASETS]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharey=sharey, gridspec_kw={'width_ratios': counts, 'wspace': 0.12 if sharey else 0.28})
    for ax, ds in zip(axes, DATASETS):
        pts = sorted(sel[ds])
        x = np.arange(len(pts))
        w = 0.38
        for j, (th, lab, f) in enumerate([(1, '1 线程', 0.45), (8, '8 线程', 1.0)]):
            vals = [sel[ds][p][th][metric] for p in pts]
            fails = [sel[ds][p][th]['pass'] != 'pass' for p in pts]
            bars = ax.bar(x + (j - 0.5) * w, vals, w * 0.92, color=tint(C_DS[ds], f), label=lab,
                          edgecolor=[INK2 if fl else 'none' for fl in fails], linewidth=0.8)
            for b, fl in zip(bars, fails):
                if fl:
                    b.set_hatch('////')
        if refline is not None:
            ax.axhline(refline, color=INK2, lw=1, ls='--')
            ax.text(x[0] - 0.5, refline, f'+{refline}%', va='bottom', ha='left', fontsize=8, color=INK2)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([f'k{k}\nR{R:.2f}' for k, R in pts], fontsize=8)
        ax.set_title(DSNAME[ds], loc='left', fontsize=11, color=INK)
        ax.grid(axis='y', color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis='y', labelsize=8)
        lo, hi = ax.get_ylim()
        d = 1 if (hi - lo) < 8 else 0
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _, d=d: (f'{v:+.{d}f}%' if d == 0 else f'{v:+.2f}'.rstrip('0').rstrip('.') + '%') if abs(v) > 1e-9 else '0'))
    axes[0].set_ylabel(ylabel, fontsize=9)
    h = [matplotlib.patches.Patch(facecolor=tint('#52514e', 0.45), label='1 线程'), matplotlib.patches.Patch(facecolor='#52514e', label='8 线程')]
    if note_fail:
        h.append(matplotlib.patches.Patch(facecolor='white', edgecolor=INK2, hatch='////', label='未通过质量检查（固定基线在保留组上未达到 C）'))
    fig.legend(handles=h, loc='upper right', ncol=3, frameon=False, fontsize=9, bbox_to_anchor=(0.99, 1.0))
    fig.suptitle(title, x=0.01, ha='left', fontsize=12, y=1.02)
    save(fig, name)


def fig_scatter(rows):
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    mk = {0.99: 'o', 0.95: 's', 0.90: '^'}
    for r in rows:
        if r['arm'] != 'on' or r['threads'] != 8 or r['alpha'] in ('auto-off', 'none'):
            continue
        ok = r['pass'] == 'pass'
        ax.scatter(r['saving_pct'], r['qps_pct'], marker=mk[r['tier']], s=46, linewidths=1.3,
                   facecolors=C_DS[r['dataset']] if ok else 'white', edgecolors=C_DS[r['dataset']], zorder=3)
    s = np.linspace(0, 76, 200)
    ax.plot(s, 100 * (1 / (1 - s / 100) - 1), color=INK2, lw=1, ls='--', zorder=1)
    ax.text(40, 100 * (1 / (1 - .4) - 1) + 12, '耗时与距离计算次数成正比时的理论值', fontsize=8, color=INK2, rotation=0)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xlabel('距离计算节省 (%)', fontsize=9)
    ax.set_ylabel('QPS 变化 (%，8 线程，相对上游 main)', fontsize=9)
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
    for sp_ in ('top', 'right'):
        ax.spines[sp_].set_visible(False)
    h1 = [plt.Line2D([], [], marker='o', ls='', color=C_DS[d], label=DSNAME[d]) for d in DATASETS]
    h2 = [plt.Line2D([], [], marker=mk[t], ls='', color=INK2, label=f'C={t:.2f}') for t in TIERS]
    h3 = [plt.Line2D([], [], marker='o', ls='', mfc='white', mec=INK2, label='未通过质量检查')]
    ax.legend(handles=h1 + h2 + h3, frameon=False, fontsize=8, loc='upper left')
    ax.set_title('距离计算节省与 QPS 变化的关系（8 线程，所有计时点）', loc='left', fontsize=11)
    save(fig, 'fig_b_saving_vs_qps')


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--timing', type=Path, help='timing-results directory of a rerun')
    parser.add_argument('--summary', type=Path, help='summary-<lib>.json of a rerun')
    parser.add_argument('--keep-noisy', action='store_true',
                        help='keep batches flagged noisy_background (busy machine, e.g. the smoke test)')
    args = parser.parse_args()
    OUT = args.out
    if args.timing:
        FILES['timing-results-v6/batches.json'] = args.timing / 'batches.json'
        FILES['timing-results-v6/plan.json'] = args.timing / 'plan.json'
    if args.summary:
        FILES['summary-v4.json'] = args.summary
    (OUT / 'data').mkdir(parents=True, exist_ok=True)
    (OUT / 'figures').mkdir(parents=True, exist_ok=True)
    setup_font()
    T = timing(not args.keep_noisy)
    T_all = timing(False)
    Q = quality()
    plan = load('timing-results-v6/plan.json')
    rows = build_rows(Q, T, plan)
    rows_all = build_rows(Q, T_all, plan)
    n_noisy = sum(r['noisy_background'] for r in load('timing-results-v6/batches.json'))
    # reproduce timing-summary-v6.json
    ref = load('timing-summary-v6.json') if not args.timing else []
    idx = {(r['dataset'], r['point'], r['threads'], r['arm']): r for r in rows_all if r['arm'] != 'on' or r['alpha'] not in ('auto-off', 'none')}
    maxd = 0
    for e in ref:
        r = idx[(e['dataset'], e['point'], e['threads'], e['arm'])]
        maxd = max(maxd, abs(r['qps_pct'] - e['qps_pct']), abs(r['p99_pct'] - e['p99_pct']))
    print(f'timing-summary-v6.json (all batches kept): {len(ref)} entries compared, max abs diff {maxd:.3e} pct points')
    print(f'excluded noisy batches: {n_noisy}')
    for w in warnings:
        print('WARN', w)
    write_csv(rows)
    write_tables(rows, n_noisy)
    if args.timing or args.keep_noisy:
        # the header written above describes the batches excluded from the delivered run
        lines = (OUT / 'tables.md').read_text().split('\n')
        lines[0] = (f'<!-- generated by make_report_assets.py from {FILES["timing-results-v6/batches.json"].parent}; '
                    f'medians of the repeats; noisy batches {"kept" if args.keep_noisy else "excluded"}: {n_noisy} -->')
        (OUT / 'tables.md').write_text('\n'.join(lines))
    grouped(rows, 'qps_pct', 0.99, False, 'QPS 变化 (%)', 'C=0.99：QPS 相对上游 main 的变化（仅通过质量检查的点；虚线为 +10%）', 'fig_a_c99_qps', refline=10)
    fig_scatter(rows)
    grouped(rows, 'p99_pct', 0.99, True, 'P99 延迟变化 (%)', 'C=0.99：P99 延迟相对上游 main 的变化（负值为变快）', 'fig_c_c99_p99', note_fail=True, sharey=True)
    print('done; rows', len(rows))


if __name__ == '__main__':
    main()
