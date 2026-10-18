"""Prepare alias-recovered sources under the same strict mobile surface gates."""
import argparse
from pathlib import Path

from realface_batch import valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_mobile import PreparationProcess, allocations, prepare_one, HERE
from realface_pipeline import sha


def owners_from_prepared(inventory, prepared):
    identities = {r['base_id']: r for r in inventory['players']}
    owners = []
    for row in prepared:
        source = identities[row['base_id']]
        if source['status'] != 'source_ready' or not source.get('source_identity_evidence'):
            raise ValueError('Recovered source lacks explicit identity evidence')
        if row['status'] not in ('prepared', 'prepared_cached'):
            continue
        folder = Path(row['folder'])
        if not valid_prepared_cache(folder, row['cache_key']):
            raise ValueError('Recovered source cache changed')
        profile_path = folder / 'ue-profile.json'; profile = read(profile_path)
        if any(profile.get(k) != source[k] for k in ('base_id', 'native_player_id', 'fingerprint')):
            raise ValueError('Recovered FBX profile differs from canonical owner')
        paths = [profile_path] + [Path(profile[k]) for k in
                                  ('face_fbx', 'hair_fbx', 'face_texture', 'hair_texture', 'native_eye_texture')]
        owners.append(dict({k: source[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')},
                           profile=str(profile_path), input_hashes={str(p): sha(p) for p in paths},
                           source_identity_evidence=source['source_identity_evidence']))
    return owners


def prepare(config, owners, work):
    work = Path(work).resolve()
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Recovered sources require a dedicated ignored directory')
    # Preserve seam aliases and source normals. Additional retries redistribute
    # the same 2,000-triangle allowance; facial distance/UV gates never relax.
    budgets = [dict(b, native_seam_alias=True, normal_export_recovery=True) for b in allocations()]
    for uv in (3., 1.):
        for skin, eye, hair in ((1500, 128, 360), (1600, 128, 260), (1400, 192, 400), (1750, 128, 110)):
            budgets.append(dict(budgets[0], face_skin=skin, eye=eye, hair=hair, skin_uv_weight=uv,
                                hair_mode='shell', solid_scalp=True, eye_recovery=True))
    cfg = dict(config, work_dir=str(work), source_profiles=str(work / 'sources.local.json'),
               allocation_overrides={str(r['base_id']): budgets for r in owners})
    write(work / 'sources.local.json', owners); write(work / 'config.local.json', cfg)
    worker = PreparationProcess(cfg['blender'], HERE / 'blender_realface_seam_worker.py')
    saved = {}
    if (work / 'prepare-report.json').exists():
        saved = {r['base_id']: r for r in read(work / 'prepare-report.json')}
    try:
        for owner in owners:
            row = prepare_one(cfg, owner, worker, saved.get(owner['base_id']))
            saved[row['base_id']] = row
            write(work / 'prepare-report.json', sorted(saved.values(), key=lambda r: r['base_id']))
            print(dict(base_id=row['base_id'], status=row['status'], triangles=row.get('triangles')), flush=True)
    finally:
        worker.close()
    return list(saved.values())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--inventory', required=True)
    p.add_argument('--prepared', required=True); p.add_argument('--work-dir', required=True)
    a = p.parse_args()
    owners = owners_from_prepared(read(a.inventory), read(a.prepared))
    prepare(read(a.config), owners, a.work_dir)
