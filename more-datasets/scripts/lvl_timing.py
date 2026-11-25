#!/usr/bin/env python3
"""Timing at calibration levels 0.90 and 0.99 (tiers 0.80, 0.98): reference build at the fixed ef against the PR build
with the rule C alpha, only at points where rule C saves at least 8% of the distance computations on the held-out
queries. recalibrate.timing does the rest (load check, four rotating batches, 1 and 8 threads, medians).

usage: RECAL_RUN=work/lvl RECAL_TIERS=0.80,0.98 TIME_TIER=0.98 lvl_timing.py DS [--force]
Also used for level 0.95 (RECAL_RUN=work/l95, TIME_TIER=0.90). Output: RUN/timing-DS-cXX/ and
RUN/timing-summary-DS-cXX.json, XX = 100 * TIME_TIER.
"""
import os
import sys

import recalibrate as r

MIN_SAVING = float(os.environ.get('MIN_SAVING', '8.0'))  # 0 for the tier-0.99 headline: every rule C point
TIER = float(os.environ['TIME_TIER'])
SUFFIX = f'c{int(round(TIER * 100))}'


def main():
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv
    ds = args[0]
    plan = {}
    for k in r.KS:
        held = r.read(r.qdir(r.CFG['quality_library'], ds) / f'validation-result-k{k}.json')
        for tag, h in held.items():
            c = h.get('rule_c')
            if h['C'] == TIER and c and c['saving_pct'] >= MIN_SAVING:
                arms = plan.setdefault((ds, k), {'ref': {}, 'rulec': {}})
                arms['ref'][tag] = r.params(h['fixed_ef'], None)
                arms['rulec'][tag] = r.params(h['fixed_ef'], c['alpha'])
    if not plan:
        r.save(r.RUN / f'timing-summary-{ds}-{SUFFIX}.json', dict(results=[], note='no point where rule C saves >= 8%'))
        print(ds, 'nothing to time')
        return
    r.timing(r.CFG['timing_candidate'], r.CFG['timing_reference'], r.CFG['quality_library'], ds, force,
             plan=plan, target=r.RUN / f'timing-{ds}-{SUFFIX}')


if __name__ == '__main__':
    main()
