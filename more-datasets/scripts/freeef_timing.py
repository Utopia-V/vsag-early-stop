#!/usr/bin/env python3
"""Timing of the free-ef arm: reference build at the level's fixed ef against the PR build at the chosen (ef, alpha),
only where the choice saves at least 8% of the distance computations on the held-out queries.

usage: RECAL_RUN=work/freeef freeef_timing.py DS [--force]
"""
import sys

import recalibrate as r

MIN_SAVING = 8.0


def main():
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv
    ds = args[0]
    sel = r.read(r.RUN / f'freeef-{ds}.json')
    plan = {}
    for tag, p in sel.items():
        h, c = p.get('held_out'), p['chosen']
        if h and h['saving_pct'] >= MIN_SAVING:
            arms = plan.setdefault((ds, p['k']), {'ref': {}, 'on': {}})
            arms['ref'][tag] = r.params(p['fixed_ef'], None)
            arms['on'][tag] = r.params(c['ef'], c['alpha'])
    if not plan:
        r.save(r.RUN / f'timing-summary-{ds}.json', dict(results=[], note='no point where the free-ef choice saves >= 8%'))
        print(ds, 'nothing to time')
        return
    r.timing(r.CFG['timing_candidate'], r.CFG['timing_reference'], r.CFG['quality_library'], ds, force,
             plan=plan, target=r.RUN / f'timing-{ds}')


if __name__ == '__main__':
    main()
