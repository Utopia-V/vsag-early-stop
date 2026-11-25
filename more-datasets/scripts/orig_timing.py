#!/usr/bin/env python3
"""Time the original campaign's C = 0.99 rule C alphas on its three datasets with the current two libraries.

usage: RECAL_RUN=work/orig orig_timing.py DS [--force]

Points: at tier 0.99 (calibrated at 99.5%) every point of results/quality/summary-v4.json with a held-out rule C
result (all 18, LAION k10 R0.80 included although rule C fails its loss check there); at tier 0.90 (ORIG_TIER=0.90,
calibrated at 95%) the points where rule C saves at least 8% of the distance computations on the held-out queries.
Arms: ref = reference build at the fixed ef; rulec = PR build with the rule C alpha; sept = PR build with the
September-freeze alpha (tier 0.99 only).
Original indexes and held-out queries (config.toml), held-out quality not rerun. recalibrate.timing does the rest
(load check, four rotating batches, 1 and 8 threads, medians).
"""
import os
import sys

import config
import recalibrate as r


def main():
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv
    ds = args[0]
    tier = float(os.environ.get('ORIG_TIER', '0.99'))
    # September freeze alphas (runs/final-validation-20260912), recorded as old_alpha of the C = 0.99 points.
    global SEPT
    SEPT = {f"c99-k{p['k']}-r{int(round(p['R'] * 100))}": p['old_alpha']
            for p in r.read(config.FROZEN / 'fixed-points.json') if p['dataset'] == ds and p['C'] == 0.99}
    summary = r.read(config.PACKAGE / 'results' / 'quality' / 'summary-v4.json')
    plan = {}
    for p in summary['points']:
        if p['dataset'] != ds or p['C'] != tier:
            continue
        c = p['held_out'].get('rule_c')
        # Tier 0.99: every point with a rule C alpha. Tier 0.90 (calibrated at 95%): points saving >= 8%.
        if not c or (tier != 0.99 and c['saving_pct'] < 8.0):
            continue
        arms = plan.setdefault((ds, p['k']), {'ref': {}, 'rulec': {}} | ({'sept': {}} if tier == 0.99 else {}))
        arms['ref'][p['point']] = r.params(p['fixed_ef'], None)
        arms['rulec'][p['point']] = r.params(p['fixed_ef'], p['rule_c_alpha'])
        if tier == 0.99 and SEPT.get(p['point']):
            arms['sept'][p['point']] = r.params(p['fixed_ef'], SEPT[p['point']])
    print(ds, {f'k{k}': sorted(a['ref']) for (_, k), a in plan.items()}, flush=True)
    suffix = '' if tier == 0.99 else f'-c{int(round(tier * 100))}'
    if not plan:
        r.save(r.RUN / f'timing-summary-{ds}{suffix}.json', dict(results=[], note='no point to time'))
        return
    r.timing(r.CFG['timing_candidate'], r.CFG['timing_reference'], r.CFG['quality_library'], ds, force,
             plan=plan, target=r.RUN / f'timing-{ds}{suffix}')


if __name__ == '__main__':
    main()
