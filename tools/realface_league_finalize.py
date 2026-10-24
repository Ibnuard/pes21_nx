"""Serial bounded hold recovery, then resumable cooked-texture preview batches.

This produces evidence for visual review, never an automatic visual approval.
No accepted head is reprocessed and no runtime file is installed or rebuilt.
"""
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import argparse
import json
import os
import time

import realface_budget_experiment as trial
from realface_batch import key_of
from realface_batch_inventory import read, write
from realface_league_balanced import (READY, VERIFIED, assert_owner, exclusive,
                                     local_output, unique, validate_head)
from realface_league_mobile import PreparationProcess
from realface_lite import sources
from realface_pipeline import sha

HERE = Path(__file__).resolve().parent


def recovery_allocation(cap, skin, locked):
    if cap not in (5000, 7000) or skin not in (3000, 2800, 2600) or type(locked) is not bool:
        raise ValueError('Only the explicit bounded recovery distributions are allowed')
    return dict(face_skin=skin, hair=cap-skin-276, hair_face_lock=locked)


def status(work, phase, prepared, verified, **extra):
    state = extra.pop('state', 'running')
    write(work/'RUN-STATUS.json', dict(policy='league-balanced-v55', phase=phase,
          state=state, pid=os.getpid(), updated_at=time.time(), workers=1,
          total_sources=max(len(prepared),len(read(work/'league-scope.json')['selected_base_ids']))
          if (work/'league-scope.json').is_file() else len(prepared), prepared_processed=len(prepared),
          prepared_statuses=dict(Counter(r['status'] for r in prepared.values())),
          verified=sum(r['status'] in VERIFIED for r in verified.values()),
          installed=False, hardware_accepted=False, **extra))


@contextmanager
def empty_recipe():
    allocation, code = trial.effective_allocation, trial.recipe_code
    def effective(config, base):
        return dict(allocation(config, base), verified_empty_hair_slot=True)
    def recipe(budget):
        result = code(budget)
        for name in ('realface_empty_slot_policy.py', 'blender_realface_empty_budget_worker.py',
                     'realface_league_finalize.py'):
            result[name] = sha(HERE/name)
        return result
    try:
        trial.effective_allocation, trial.recipe_code = effective, recipe
        yield
    finally:
        trial.effective_allocation, trial.recipe_code = allocation, code


def recover(config, prepared, verified, catalogue):
    work = Path(config['work_dir'])
    if set(prepared) != set(catalogue):
        raise ValueError('Finish the complete original league batch first')
    old_path = work/'prepare.before-recovery.json'
    if not old_path.exists():
        write(old_path, sorted(prepared.values(), key=lambda r: r['base_id']))
    attempts_path = work/'hold-recovery-report.json'
    attempts = read(attempts_path) if attempts_path.exists() else {}
    for base, old in list(sorted(prepared.items())):
        if old['status'] in READY:
            continue
        if str(base) in attempts:
            # An unchanged deterministic hold is not retried on every wakeup.
            continue
        reason = old.get('reason', '')
        empty = reason.startswith('No visible hair pixels')
        budget = reason.startswith(('Experimental complete head cap exceeded', 'Card gaps', 'Hair silhouette'))
        if not empty and not budget:
            continue
        source = catalogue[base]; assert_owner(old, source)
        profile = read(source['profile'])
        if empty and (profile.get('hair_materials') != ['rf_hair_empty'] or profile.get('hair_skin_materials')):
            attempts[str(base)] = dict(status='held_source', reason='Empty-alpha source is not a declared native empty slot')
            write(attempts_path, attempts); continue
        locked = old.get('facial_hair_policy', {}).get('locked', False)
        worker = PreparationProcess(config['blender'], HERE/(
            'blender_realface_empty_budget_worker.py' if empty else 'blender_realface_budget_worker.py'))
        tries = []
        try:
            status(work, 'recover_holds', prepared, verified, current_base_id=base, current_name=old['name'])
            for skin in (3000, 2800, 2600):
                cap = 5000 if empty else 7000
                job = dict(config, experimental_head_cap=cap, experimental_hair_policy='cards',
                           experimental_allocations={str(base): recovery_allocation(cap, skin, locked)})
                if empty:
                    with empty_recipe():
                        result = trial.prepare_one(job, source, worker)
                else:
                    result = trial.prepare_one(job, source, worker)
                tries.append({k: result.get(k) for k in ('status', 'reason', 'triangles', 'cache_key', 'folder', 'budgets')})
                if result['status'] in READY and result['triangles'] <= 7000:
                    result['facial_hair_policy'] = old.get('facial_hair_policy', {})
                    result['league_attempts'] = old.get('league_attempts', []) + tries
                    result['hold_recovery'] = dict(previous_cache_key=old['cache_key'], previous_reason=reason,
                                                    empty_slot_verified=empty, attempts=tries)
                    if result['triangles'] > 5000:
                        result['league_exception'] = dict(reason='Bounded hair redistribution after 5k hold: '+reason,
                                                          triangles=result['triangles'], attempts=tries)
                    validate_head(result); prepared[base] = result
                    write(work/'prepare-report.json', sorted(prepared.values(), key=lambda r: r['base_id']))
                    break
                if empty:
                    break  # Geometry/material proof failure is not a budget failure.
                if not result.get('reason', '').startswith(('Experimental complete head cap exceeded', 'Card gaps', 'Hair silhouette')):
                    break
            attempts[str(base)] = dict(name=old['name'], status=prepared[base]['status'], attempts=tries)
            write(attempts_path, attempts)
            print(json.dumps(dict(recovered_base_id=base, status=prepared[base]['status'],
                                  triangles=prepared[base].get('triangles')), ensure_ascii=True), flush=True)
        finally:
            worker.close()


def cook_missing(config, prepared, verified):
    import realface_batch_release as factory
    from realface_budget_cook import resume_import_chunk
    work = Path(config['work_dir'])
    rows = [r for b, r in sorted(prepared.items()) if r['status'] in READY and
            (b not in verified or verified[b]['status'] not in VERIFIED)]
    for start in range(0, len(rows), 12):
        chunk = rows[start:start+12]
        batch = work/'recovery-batches'/key_of([r['cache_key'] for r in chunk])[:16]
        job = dict(config, work_dir=str(batch))
        write(batch/'config.local.json', job); write(batch/'prepare-report.json', chunk)
        status(work, 'recover_cook', prepared, verified, current_batch=len(chunk))
        original = factory.import_chunk
        try:
            factory.import_chunk = resume_import_chunk
            factory.cook(job)
        finally:
            factory.import_chunk = original
        status(work, 'recover_verify', prepared, verified, current_batch=len(chunk))
        for result in factory.verify(job, workers=1):
            if result['status'] in VERIFIED:
                validate_head(result)
            verified[result['base_id']] = result
            write(work/'verify-report.json', sorted(verified.values(), key=lambda r: r['base_id']))
    failed = [b for b,r in prepared.items() if r['status'] in READY and
              (b not in verified or verified[b]['status'] not in VERIFIED)]
    if failed:
        raise RuntimeError('Prepared heads still lack independent cook validation: '+str(sorted(failed)))


def preview(config, prepared, verified):
    from realface_preview_process import PreviewProcess
    with PreviewProcess(config['blender']) as worker:
        return preview_batches(config,prepared,verified,worker)


def preview_batches(config, prepared, verified, worker):
    from realface_league_preview import preview as render
    from realface_preview_cache import index_views, seed_views
    work = Path(config['work_dir'])
    rows = [r for _, r in sorted(verified.items()) if r['status'] in VERIFIED]
    cached_views = index_views(work/'review', rows, sha(HERE/'blender_preview_realface.py'))
    diagnostic={108525,113677,113911,118657,124266,124855}&{r['base_id'] for r in rows}
    if diagnostic:
        status(work,'preview_source_comparison',prepared,verified,current_batch=len(diagnostic))
        for stage in ('source','prepared'):
            render(config,stage=stage,selected=diagnostic,limit=len(diagnostic),views=('front',),
                   output=work/'texture-diagnostic'/stage,render_worker=worker)
    plan = [('front', rows, ('front',))]
    critical = [r for r in rows if r.get('league_exception') or r.get('facial_hair_policy', {}).get('locked') or
                r.get('budgets', {}).get('hair_face_lock')]
    plan.append(('detail', critical, ('front', 'left', 'right', 'above')))
    manifest = []
    for kind, heads, views in plan:
        for start in range(0, len(heads), 12):
            chunk = heads[start:start+12]
            key = key_of(dict(keys=[(r['cache_key'], r['cooked_cache_key']) for r in chunk], views=views,
                              renderer=sha(HERE/'blender_preview_realface.py'),
                              preview_tool=sha(HERE/'realface_league_preview.py')))[:16]
            output = work/'review'/kind/key
            complete = output/'PREVIEW-COMPLETE.json'
            good = False
            if complete.is_file():
                stamp = read(complete)
                good = all(Path(p).is_file() and sha(p) == digest for p, digest in stamp['hashes'].items())
            status(work, 'preview_'+kind, prepared, verified,
                   preview_completed_heads=start, preview_total_heads=len(heads))
            if not good:
                seed_views(output, chunk, views, cached_views)
                render(config, stage='cooked', selected={r['base_id'] for r in chunk},
                       limit=len(chunk), views=views, output=output,render_worker=worker)
                files = [p for p in output.iterdir() if p.suffix in ('.png', '.json') and p != complete]
                write(complete, dict(hashes={str(p.resolve()): sha(p) for p in files}))
            provenance = read(output/'PROVENANCE.json')
            for row in chunk:
                for view in views:
                    image = output/(str(row['base_id'])+'-'+view+'.png')
                    manifest.append(dict(base_id=row['base_id'], path=str(image.resolve()), sha256=sha(image), view=view))
            print(json.dumps(dict(preview_kind=kind, completed=min(start+12, len(heads)), total=len(heads),
                                  sheets=provenance['sheets'])), flush=True)
    write(work/'PREVIEW-INDEX.json', dict(images=manifest, prepared_sha256=sha(work/'prepare-report.json'),
          verified_sha256=sha(work/'verify-report.json'), offline_only=True, visual_review_complete=False))
    status(work, 'awaiting_visual_review', prepared, verified, preview_images=len(manifest), state='awaiting_review')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--from-phase', choices=('recover', 'preview'), default='recover')
    args = parser.parse_args(); config = read(args.config); work = local_output(config['work_dir'])
    with exclusive(work):
        for path, expected in config['pinned_inputs'].items():
            if sha(path) != expected:
                raise ValueError('Pinned league input changed')
        catalogue = unique(sources(config), 'finalizer sources')
        prepared = unique(read(work/'prepare-report.json'), 'finalizer preparations')
        verified = unique(read(work/'verify-report.json'), 'finalizer verification')
        if set(prepared) != set(catalogue):
            raise ValueError('Complete main batch required')
        try:
            if args.from_phase == 'recover':
                recover(config, prepared, verified, catalogue)
                cook_missing(config, prepared, verified)
            preview(config, prepared, verified)
        except Exception as error:
            write(work/'RUN-STATUS.json', dict(phase='finalize', state='failed', pid=os.getpid(),
                  reason=str(error), updated_at=time.time(), installed=False, hardware_accepted=False))
            raise


if __name__ == '__main__':
    main()
