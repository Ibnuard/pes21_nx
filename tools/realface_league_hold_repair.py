"""Bounded serial retries for source-verified heads held by hair reduction.

Only the hair reducer's search error/UV weighting changes. Source vertices,
facial-hair locks, native identity, skin recipe and final projection gates do
not change. Every new recipe is separately hashed; old successes are reused.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import json

import realface_budget_experiment as trial
from realface_batch import key_of
from realface_batch_inventory import read, write
from realface_league_balanced import READY, assert_owner, exclusive, local_output, unique, validate_head
from realface_league_finalize import cook_missing, preview, recovery_allocation, status
from realface_league_mobile import PreparationProcess
from realface_lite import sources
from realface_pipeline import sha

HERE = Path(__file__).resolve().parent
SEARCHES = ((.65, .25), (.90, .10), (1.25, .10))


@contextmanager
def hair_search(error, uv_weight):
    if (error, uv_weight) not in SEARCHES:
        raise ValueError('Only bounded hair searches are supported')
    allocation, code = trial.effective_allocation, trial.recipe_code
    def effective(config, base):
        result = allocation(config, base)
        result.update(hair_error_cm=error, hair_uv_weight=uv_weight)
        return result
    def recipe(budget):
        return dict(code(budget), **{Path(__file__).name: sha(__file__)})
    try:
        trial.effective_allocation, trial.recipe_code = effective, recipe
        yield
    finally:
        trial.effective_allocation, trial.recipe_code = allocation, code


def repair(config, prepared, verified, catalogue):
    work = Path(config['work_dir'])
    path = work/'final-hold-repair-report.json'
    records = read(path) if path.exists() else {}
    before = work/'prepare.before-final-hold-repair.json'
    if not before.exists():
        write(before, sorted(prepared.values(), key=lambda r: r['base_id']))
    for base, old in list(sorted(prepared.items())):
        if old['status'] in READY or not old.get('reason', '').startswith('Experimental complete head cap exceeded'):
            continue
        source = catalogue[base]; assert_owner(old, source)
        worker = PreparationProcess(config['blender'], HERE/'blender_realface_budget_worker.py')
        attempts = records.setdefault(str(base), {})
        try:
            for error, weight in SEARCHES:
                for cap, skin in ((5000, 3000), (7000, 3000), (7000, 2600)):
                    spec = dict(cap=cap, skin=skin, hair_error_cm=error, hair_uv_weight=weight,
                                source_key=old['cache_key'], code=sha(__file__))
                    key = key_of(spec)
                    if key in attempts:
                        # A process may stop after saving the successful cache
                        # record but before publishing the global report.
                        cached = attempts[key]['result']
                        if cached['status'] in READY:
                            result = cached
                        else:
                            continue
                    else:
                        status(work, 'final_hair_repair', prepared, verified, current_base_id=base,
                               current_name=old['name'], search=spec)
                        job = dict(config, experimental_head_cap=cap, experimental_hair_policy='cards',
                                   experimental_allocations={str(base): recovery_allocation(
                                       cap, skin, old.get('facial_hair_policy', {}).get('locked', False))})
                        with hair_search(error, weight):
                            result = trial.prepare_one(job, source, worker)
                        if any(s in result.get('reason','').lower() for s in
                               ('blender exited','allocate memory','bad_alloc','paging file','broken pipe')):
                            (Path(result['folder'])/'held.json').unlink(missing_ok=True)
                            raise RuntimeError('Transient repair worker failure: '+result['reason'])
                        attempts[key] = dict(spec=spec, result=result)
                        write(path, records)
                    print(json.dumps(dict(base_id=base, phase='final_hair_repair', status=result['status'],
                                          triangles=result.get('triangles'), reason=result.get('reason'))), flush=True)
                    if result['status'] in READY:
                        result['facial_hair_policy'] = old.get('facial_hair_policy', {})
                        result['league_attempts'] = old.get('league_attempts', [])
                        result['final_hold_repair'] = dict(previous_cache_key=old['cache_key'], search=spec,
                            quality_thresholds_unchanged=True, facial_hair_locks_preserved=True)
                        if result['triangles'] > 5000:
                            result['league_exception'] = dict(reason='Bounded hair search after complete-head hold',
                                                              triangles=result['triangles'], search=spec)
                        validate_head(result); prepared[base] = result
                        write(work/'prepare-report.json', sorted(prepared.values(), key=lambda r: r['base_id']))
                        break
                if prepared[base]['status'] in READY:
                    break
        finally:
            worker.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(); config = read(args.config); work = local_output(config['work_dir'])
    with exclusive(work):
        for path, digest in config['pinned_inputs'].items():
            if sha(path) != digest:
                raise ValueError('Pinned league input changed')
        catalogue = unique(sources(config), 'repair source identities')
        prepared = unique(read(work/'prepare-report.json'), 'repair preparations')
        verified = unique(read(work/'verify-report.json'), 'repair verifications')
        if set(prepared) != set(catalogue):
            raise ValueError('Complete pinned scope required')
        try:
            repair(config, prepared, verified, catalogue)
            from realface_league_slot_repair import repair_slots
            repair_slots(config, prepared, verified, catalogue)
            from realface_league_outlier_repair import repair_outliers
            repair_outliers(config, prepared, verified, catalogue)
            if not args.prepare_only:
                cook_missing(config, prepared, verified)
                preview(config, prepared, verified)
            else:
                status(work,'final_holds_prepared',prepared,verified,state='awaiting_cook')
        except Exception as error:
            status(work,'completion_failed',prepared,verified,state='failed',reason=str(error))
            raise


if __name__ == '__main__':
    main()
