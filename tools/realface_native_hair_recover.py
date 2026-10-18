"""Recover invisible source-binding failures without rebuilding valid heads.

Cleaned sources and resulting trials use separate hash-pinned directories.
The original league reports/inputs remain intact. A combined report can be
cooked and packaged only after the full original queue has finished.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import time

from PIL import Image
from realface_batch import command, key_of, output_hashes, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_progress import indexed, owner_matches
from realface_native_hair_leagues import convert, publish
from realface_native_hair_trial import CODE, HERE, trial
from realface_pipeline import sha


CLEAN_CODE = ('realface_native_hair_recover.py', 'realface_hair_alpha_cleanup.py',
              'blender_realface_hair_alpha_cleanup.py') + CODE


def eligible(row, face):
    return (not face.get('reuse_cooked') and row.get('status') == 'held_conversion' and
            'Source card binding is outside the audited head/neck chain' in row.get('reason', ''))


def shape_variants(face_triangles):
    """Try unattempted allocations only; never change the verified face."""
    remainder = 2000 - face_triangles
    effective = min(420, remainder - 64)
    if effective < 100: return []
    variants = [(420, 2)]
    # A smaller connected base leaves more original silhouette cards. Avoid
    # trying a nominal budget that resolves to the same actual allocation.
    if effective >= 180: variants.append((150, 3))
    if remainder - 64 >= 450: variants.append((500, 3))
    return variants


def recover_shape(config, face_report, base, face, work):
    count = read(Path(face['folder']) / 'simplification.json')['face']['total']
    attempts = []; row = None
    for budget, closing in shape_variants(count):
        destination = work / 'shape-trials' / str(base) / ('bulk-' + str(budget) + '-closing-' + str(closing))
        trial(config, face_report, [base], destination, budget, 'alpha_volume', 'cycles_relief', closing)
        row = read(destination / 'trial-report.json')[0]
        attempts.append(dict(opaque_base_triangles=budget, closing_steps=closing,
                             status=row['status'], cache_key=row.get('cache_key')))
        if row['status'] == 'candidate_visual_hold': break
    return dict(row or dict(base_id=base, status='held_composite_geometry',
                           reason='No alternate hair allocation fits the unchanged face'), recovery_variants=attempts)


def clean_source(config, owner, face, work):
    if face.get('reuse_cooked') or not owner_matches(face, owner):
        raise ValueError('Source recovery requires a non-inherited, identity-matched face')
    if not valid_prepared_cache(Path(face['folder']), face['cache_key']):
        raise ValueError('Prepared face changed before source recovery')
    for path, digest in owner['input_hashes'].items():
        if sha(path) != digest: raise ValueError('Pinned original source changed')
    original = read(owner['profile'])
    code = {name: sha(HERE / name) for name in CLEAN_CODE}
    key = key_of(dict(owner=owner, profile=original, code=code, face_key=face['cache_key'],
                      tools={k: sha(config[k]) for k in ('blender', 'native_rig', 'cooked_rig')}))
    out = Path(work) / (str(owner['base_id']) + '-' + key[:16])
    if valid_cache(out, key): return read(out / 'owner.json'), None
    if (out / 'complete.json').exists(): raise ValueError('Cleaned source bytes changed')
    if (out / 'failure.json').exists():
        failure = read(out / 'failure.json')
        if failure['cache_key'] != key: raise ValueError('Cleanup failure provenance differs')
        return None, failure['reason']
    out.mkdir(parents=True, exist_ok=True)
    with Image.open(original['hair_texture']) as image:
        image.convert('RGBA').resize((128, 128), Image.Resampling.LANCZOS).save(out / 'runtime-hair.png')
    job = dict(folder=str(out.resolve()), hair_fbx=original['hair_fbx'], hair_texture=original['hair_texture'],
               native_rig=config['native_rig'], cooked_rig=config['cooked_rig'])
    write(out / 'job.json', job)
    try:
        command([config['blender'], '--background', '--threads', '1', '--python-exit-code', '1',
                 '--python', HERE / 'blender_realface_hair_alpha_cleanup.py', '--', out / 'job.json'], out / 'cleanup.log')
    except subprocess.CalledProcessError:
        log = (out / 'cleanup.log').read_text(encoding='utf-8', errors='replace')
        reason = next((s for s in reversed(log.splitlines()) if s.startswith(('ValueError:', 'RuntimeError:'))),
                      'Source cleanup failed; inspect cleanup.log')
        write(out / 'failure.json', dict(cache_key=key, reason=reason))
        return None, reason
    if {name: sha(HERE / name) for name in CLEAN_CODE} != code:
        raise ValueError('Source cleanup code changed during preparation')
    proof = read(out / 'cleanup-proof.json')
    if (proof['potentially_visible_triangles'] or proof['face_edited'] or
            not proof['exported_surface']['connectivity_uv_weights_match']):
        raise ValueError('Source cleanup did not preserve the visible original surface')
    profile = dict(original, hair_fbx=str((out / 'hair.fbx').resolve()), hair_materials=['lite_hair'],
                   source_cleanup=dict(original_profile=owner['profile'], original_hair_sha256=sha(original['hair_fbx']),
                                       proof=str((out / 'cleanup-proof.json').resolve()), code=code))
    write(out / 'source-profile.json', profile)
    hashes = dict(owner['input_hashes'])
    for name in ('hair.fbx', 'runtime-hair.png', 'cleanup-proof.json', 'source-profile.json'):
        path = (out / name).resolve(); hashes[str(path)] = sha(path)
    hashes.update({str(HERE / name): digest for name, digest in code.items()})
    result = dict(owner, profile=str((out / 'source-profile.json').resolve()), input_hashes=hashes)
    write(out / 'owner.json', result)
    write(out / 'complete.json', dict(cache_key=key, outputs=output_hashes(out)))
    return result, None


def recover(config, original_work, selected=()):
    original_work = Path(original_work).resolve()
    if not original_work.is_relative_to(HERE.parent / 'local-debug') or original_work == HERE.parent / 'local-debug':
        raise ValueError('Recovery requires an ignored league work directory')
    work = original_work / ('binding-recovery' if not selected else 'binding-recovery-selected')
    work.mkdir(parents=True, exist_ok=True)
    snapshot = read(original_work / 'coverage.json')
    if not selected and snapshot['counts'].get('native_pending', 0):
        raise ValueError('Finish the original queue before combining recovered heads')
    faces = indexed(read(original_work / 'chosen-faces.json'), 'faces')
    owners = indexed(read(config['source_profiles']), 'sources')
    rows = indexed(read(original_work / 'trial-report.json'), 'trials')
    canonical = indexed(read(Path(config['work_dir']) / 'prepare-report.json'), 'canonical')
    targets = [base for base, row in rows.items() if not faces.get(base, {}).get('reuse_cooked') and
               (eligible(row, faces.get(base, {})) or row.get('status') == 'held_composite_geometry') and
               (not selected or base in selected)]
    write(work / 'chosen-faces.json', list(faces.values()))
    write(work / 'QUALITY-HOLD.json', dict(approved=False, reason='Recovered source: appearance and device review pending'))
    results = {}; started = time.monotonic(); cleaned = {}; shapes = {}
    def checkpoint():
        write(work / 'recovery-report.json', sorted(results.values(), key=lambda r: r['base_id']))
        write(work / 'RECOVERY-STATUS.json', dict(target=len(targets), completed=len(results),
              recovered=sum(r['status'] == 'candidate_visual_hold' for r in results.values()),
              elapsed_seconds=round(time.monotonic() - started, 2), approved=False))
    for base in sorted(targets):
        result = dict(base_id=base, name=owners[base]['name'], original_key=rows[base]['cache_key'])
        if rows[base]['status'] == 'held_composite_geometry':
            shapes[base] = result
            continue
        clean, reason = clean_source(config, owners[base], faces[base], work / 'clean-sources')
        if clean:
            owners[base] = clean
            cleaned[base] = result
        else:
            result.update(status='held_source_cleanup', reason=reason)
            results[base] = result
        checkpoint()
    write(work / 'sources.local.json', list(owners.values()))
    cfg = dict(config, source_profiles=str(work / 'sources.local.json'))
    write(work / 'config.local.json', cfg)
    # The source manifest is now immutable for both workers. Each conversion
    # owns its own player/variant reports; only this coordinator publishes.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(convert, cfg, work / 'chosen-faces.json', base, work): base for base in cleaned}
        futures.update({pool.submit(recover_shape, cfg, work / 'chosen-faces.json', base, faces[base], work): base
                        for base in shapes})
        for future in as_completed(futures):
            base = futures[future]; row = future.result(); result = cleaned.get(base, shapes.get(base))
            result.update(status=row['status'], cache_key=row.get('cache_key'), reason=row.get('reason'))
            if row['status'] == 'candidate_visual_hold':
                rows[base] = dict(row, recovered_original_key=result['original_key'],
                                  recovery_source_profile=owners[base]['profile'])
            results[base] = result; checkpoint()
            print(json.dumps(dict(recovery_completed=len(results), recovery_total=len(targets), **result)), flush=True)
    original_verified = read(original_work / 'verify-report.json') if (original_work / 'verify-report.json').exists() else []
    verified = [r for r in original_verified if rows.get(r['base_id'], {}).get('cache_key') == r['cache_key']]
    write(work / 'verify-report.json', verified)
    reject = original_work / 'VISUAL-REJECT.json'
    if reject.exists(): write(work / 'VISUAL-REJECT.json', read(reject))
    publish(work, snapshot, canonical, rows, started, verified)
    return cfg, work


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--work-dir', required=True)
    p.add_argument('--player', action='append', type=int, default=[])
    a = p.parse_args(); recover(read(a.config), a.work_dir, a.player)
