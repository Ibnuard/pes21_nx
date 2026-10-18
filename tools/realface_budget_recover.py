"""Reallocate a fixed trial ceiling for hair-held heads, preserving all gates.

Only failed hair coverage candidates are retried. Facial anatomy errors are
never converted into successes by changing thresholds. One persistent worker
is used; successful original preparations remain byte-identical.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import realface_budget_experiment as trial
from realface_batch_inventory import read, write
from realface_league_mobile import PreparationProcess
from realface_lite import sources


def hair_hold(row):
    return row['status'] == 'held_geometry' and row.get('reason', '').startswith(
        ('Hair silhouette held', 'Card gaps require'))


def reallocate(original, skin):
    if skin not in (3000, 2600) or original['head_cap'] != 6000:
        raise ValueError('Recovery only reallocates the explicit 6k experiment')
    return dict(original, face_skin=skin, hair=6000-skin-original['eye']-20)


def recover(config):
    if config['experimental_head_cap'] != 6000 or config.get('experimental_teams') != [100,108]:
        raise ValueError('Recovery is restricted to the Barca/MU 6k experiment')
    work = Path(config['work_dir']).resolve()
    if not work.is_relative_to(trial.ROOT/'local-debug') or work == trial.ROOT/'local-debug':
        raise ValueError('Recovery output must remain in a dedicated local-debug directory')
    rows = read(work/'prepare-report.json')
    catalog = {r['base_id']:r for r in sources(config)}
    old_allocation = trial.allocation
    worker = PreparationProcess(config['blender'], trial.HERE/'blender_realface_budget_worker.py')
    report = []
    try:
        for index, old in enumerate(rows):
            if not hair_hold(old):
                continue
            attempts = [dict(cache_key=old['cache_key'], folder=old['folder'], status=old['status'],
                             reason=old.get('reason'), budgets=old['budgets'])]
            for skin in (3000,2600):
                budget = reallocate(old_allocation(6000), skin)
                # Effective values are part of prepare_one's cache key and
                # recorded job. No production recipe or threshold is edited.
                trial.allocation = lambda cap, effective=budget: dict(effective)
                result = trial.prepare_one(config, catalog[old['base_id']], worker)
                attempts.append({k:result.get(k) for k in ('cache_key','folder','status','reason','budgets')})
                print(json.dumps(dict(base_id=old['base_id'], skin=skin,
                                      status=result['status'], triangles=result.get('triangles'))), flush=True)
                if result['status'] in ('prepared','prepared_cached'):
                    result['allocation_recovery'] = dict(original_cache_key=old['cache_key'], attempts=attempts)
                    rows[index] = result
                    write(work/'prepare-report.json', rows)
                    break
            report.append(dict(base_id=old['base_id'], name=old['name'],
                               final_status=rows[index]['status'], attempts=attempts))
            write(work/'reallocation-report.json', report)
    finally:
        trial.allocation = old_allocation
        worker.close()
    print(dict(statuses=dict(Counter(r['status'] for r in rows)),reallocated=len(report)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    args = p.parse_args()
    recover(read(args.config))
