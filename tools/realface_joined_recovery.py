"""Incremental recovery of held league heads, preserving the shipped baseline.

Reuse only identity- and hash-verified mobile geometry. Hair already modelled
as a closed surface keeps its source texture. Joined alpha volumes can receive
offline source relief; no runtime materials, vertices, or shaders are added.
Every result is still a visual hold until explicitly screened and cooked.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess

from PIL import Image
from realface_batch import command, key_of, output_hashes, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_progress import indexed, owner_matches
from realface_native_hair_cards import composite_ok
from realface_native_hair_trial import CODE as NATIVE_CODE, HERE
from realface_pipeline import sha

CODE = tuple(sorted(set(NATIVE_CODE) | {
    'realface_joined_recovery.py', 'blender_realface_joined_recovery.py',
    'blender_realface_joined_scalp_worker.py',
    'blender_realface_source_quality.py', 'blender_realface_hair_rebake.py'}))


def eligible(face, owner, included):
    return (face.get('base_id') not in included and not face.get('reuse_cooked')
            and face.get('status') in ('prepared', 'prepared_cached')
            and owner_matches(face, owner))


def tool_snapshot(config):
    result = {}
    for key in ('blender', 'native_rig', 'cooked_rig', 'fast_raster'):
        if not config.get(key):
            continue
        path = Path(config[key]); before = path.stat()
        digest = sha(path); after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Tool changed during fingerprinting')
        result[key] = dict(path=str(path), size=after.st_size, mtime_ns=after.st_mtime_ns, sha256=digest)
    return result


def check_tools(snapshot):
    for item in snapshot.values():
        stat = Path(item['path']).stat()
        if (stat.st_size, stat.st_mtime_ns) != (item['size'], item['mtime_ns']):
            raise ValueError('Tool changed during batch; rerun with fresh fingerprints')


def prepare_one(config, face, owner, work, mode, tools=None):
    tools = tools or tool_snapshot(config)
    check_tools(tools)
    base = Path(face['folder'])
    if not valid_prepared_cache(base, face['cache_key']):
        raise ValueError('Canonical prepared head bytes changed: ' + str(face['base_id']))
    for path, digest in owner['input_hashes'].items():
        if sha(path) != digest:
            raise ValueError('Verified source bytes changed: ' + path)
    source = read(owner['profile'])
    if source['native_player_id'] != owner['native_player_id']:
        raise ValueError('Source profile identity differs')
    profile = read(base / 'ue-profile.json')
    proof = read(base / 'simplification.json')
    projection = read(base / 'hair-projection.json')
    counts = [proof[p]['total'] for p in ('face', 'hair')]
    if (not 0 < sum(counts) <= 2000 or
            any(proof[p]['sections'] != 1 for p in ('face', 'hair'))):
        raise ValueError('Prepared head violates triangle/section limits')
    code = {name: sha(HERE / name) for name in CODE}
    key = key_of(dict(owner={k: owner[k] for k in ('base_id', 'native_player_id', 'fingerprint')},
                      source=owner['input_hashes'], face=face['cache_key'], code=code, mode=mode,
                      tools={k: v['sha256'] for k, v in tools.items()}))
    out = work / (str(face['base_id']) + '-' + key[:16])
    entry = {k: owner[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')}
    entry.update(folder=str(out), cache_key=key, source_face_key=face['cache_key'],
                 recipe_source_sha256=code, source_folder=str(base), recovery_mode=mode,
                 triangles=sum(counts), quality_level=face.get('quality_level', 0),
                 budgets=dict(face['budgets'], head_cap=2000))
    if (out / 'complete.json').exists():
        if not valid_prepared_cache(out, key):
            raise ValueError('Recovery cache changed; original proof is immutable')
    elif (out / 'failure.json').exists():
        failure = read(out / 'failure.json')
        if failure['cache_key'] != key:
            raise ValueError('Failure provenance differs')
        return dict(entry, status='held_conversion', reason=failure['reason'], cached=True)
    else:
        out.mkdir(parents=True, exist_ok=True)
        for part in ('face', 'hair'):
            shutil.copy2(base / (part + '.fbx'), out / (part + '.fbx'))
        shutil.copy2(base / 'opaque-atlas.png', out / 'opaque-atlas.png')
        # Cooked validation needs the original face geometry/UV evidence, not
        # merely a boolean copied from an earlier summary.
        for path in base.glob('*.json'):
            if path.name not in ('complete.json', 'held.json', 'job.json', 'ue-profile.json',
                                 'recipe.json', 'simplification.json'):
                shutil.copy2(path, out / path.name)
        texture = out / 'hair-shell.png'
        with Image.open(profile['hair_texture']) as image:
            image.convert('RGBA').resize((128, 128), Image.Resampling.LANCZOS).save(texture)
        joined = projection.get('method', {}).get('mode') in (
            'joined_source_alpha_volume', 'split_radial_surface')
        bake = (joined and mode == 'source_relief') or mode == 'joined_scalp'
        if bake:
            shutil.copy2(source['hair_fbx'], out / 'input-hair.fbx')
            write(out / 'job.json', dict(folder=str(out), source_profile=source,
                                         base_id=owner['base_id'], face_folder=str(base),
                                         face_triangles=counts[0], hair_budget=2000-counts[0],
                                         fast_raster=config.get('fast_raster'),
                                         **{k: config[k] for k in ('native_rig', 'cooked_rig')}))
            try:
                command([config['blender'], '--background', '--threads', '1', '--python-exit-code', '1',
                         '--python', HERE / ('blender_realface_joined_scalp_worker.py' if mode == 'joined_scalp'
                                            else 'blender_realface_joined_recovery.py'), '--', out / 'job.json'],
                        out / 'relief.log')
            except subprocess.CalledProcessError:
                log = (out / 'relief.log').read_text(encoding='utf-8', errors='replace')
                reason = next((line for line in reversed(log.splitlines())
                               if line.startswith(('ValueError:', 'RuntimeError:'))), 'Relief bake failed')
                write(out / 'failure.json', dict(cache_key=key, reason=reason))
                return dict(entry, status='held_conversion', reason=reason)
        preserved = ('face.fbx',) if mode == 'joined_scalp' else ('face.fbx', 'hair.fbx', 'opaque-atlas.png')
        if any(sha(out / name) != sha(base / name) for name in preserved):
            raise ValueError('Recovery must preserve face, hair mesh, and face texture byte-for-byte')
        if {name: sha(HERE / name) for name in CODE} != code:
            raise ValueError('Recovery recipe changed while running')
        check_tools(tools)
        write(out / 'ue-profile.json', dict(profile, face_fbx=str(out / 'face.fbx'),
              hair_fbx=str(out / 'hair.fbx'), face_texture=str(out / 'opaque-atlas.png'),
              hair_texture=str(texture)))
        write(out / 'recipe.json', dict(eye={}, source=owner, mobile_v35=True,
                                       joined_recovery=True, source_face_key=face['cache_key']))
        if mode == 'joined_scalp':
            result = read(out / 'joined-scalp-proof.json')
            proof = dict(proof, hair=dict(total=result['hair_triangles'], sections=1),
                         total_triangles=result['total_triangles'])
        write(out / 'simplification.json', proof)
        write(out / 'joined-recovery-proof.json', dict(source_folder=str(base), source_key=face['cache_key'],
              preserved_sha256={n: sha(base / n) for n in preserved},
              triangles=proof['total_triangles'], sections=2, hair_mode=projection.get('method', {}).get('mode'),
              offline_relief_baked=bake, runtime_lights_added=0, material_sections_added=0,
              visual_approved=False, hardware_profiled=False))
        write(out / 'QUALITY-HOLD.json', dict(approved=False, reason='Recovered head needs visual/cooked review'))
        write(out / 'complete.json', dict(cache_key=key, outputs=output_hashes(out)))
    if mode == 'joined_scalp':
        projection = read(out / 'joined-scalp-proof.json')['composite_scalp_projection']
        entry['triangles'] = read(out / 'simplification.json')['total_triangles']
    passed = composite_ok(projection)
    return dict(entry, status='candidate_visual_hold' if passed else 'held_composite_geometry',
                composite_geometry_pass=passed)


def prepare(config, faces, baseline, work, players=(), workers=2, mode='source_relief'):
    work = Path(work).resolve()
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Recovery requires a dedicated ignored directory')
    owners = indexed(read(config['source_profiles']), 'sources')
    included = {r['base_id'] for r in read(baseline)['players_in_package']}
    rows = [r for r in read(faces) if eligible(r, owners.get(r['base_id'], {}), included)
            and (not players or r['base_id'] in players)]
    work.mkdir(parents=True, exist_ok=True)
    write(work / 'config.local.json', config)
    write(work / 'inputs.json', dict(face_report=str(Path(faces).resolve()), face_report_sha256=sha(faces),
          baseline=str(Path(baseline).resolve()), baseline_sha256=sha(baseline),
          selected=[r['base_id'] for r in rows], mode=mode))
    tools = tool_snapshot(config)
    write(work / 'tool-fingerprints.json', tools)
    def one(row):
        return prepare_one(config, row, owners[row['base_id']], work / 'heads', mode, tools)
    result = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(one, rows):
            result.append(row)
            write(work / 'trial-report.json', result)
            print(dict(base_id=row['base_id'], status=row['status'], completed=len(result), total=len(rows)), flush=True)
    check_tools(tools)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--face-report', required=True)
    p.add_argument('--baseline', required=True); p.add_argument('--work-dir', required=True)
    p.add_argument('--player', type=int, action='append', default=[])
    p.add_argument('--workers', type=int, choices=(1, 2), default=2)
    p.add_argument('--mode', choices=('source_relief', 'preserved_surface', 'joined_scalp'), default='joined_scalp')
    a = p.parse_args()
    prepare(read(a.config), a.face_report, a.baseline, a.work_dir, a.player, a.workers, a.mode)
