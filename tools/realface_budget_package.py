"""Package an explicit Barca/MU budget trial; never install or approve it.

Requires every selected head to finish independent cook verification. Failed
heads are listed as native fallbacks; they are never replaced by old damaged
heads or an unbounded dense fallback. All selected budgets remain experiments.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
import shutil
import zipfile

from realface_batch import command, key_of, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_budget_experiment import CAPS, POLICY, ROOT, validate_preparation
from realface_pipeline import sha
from realface_surface_patch import (BASE, FACE, GAME, PARENT, NEW_PARENT,
                                   NEW_NORMAL, asset_names, hash_tree, patch_names)
from audit_realface_runtime_assets import dependency_names, texture_evidence
from cooked_texture import Texture
from realface_hair_mips import protect_texture


def counts(proof, cap):
    if cap not in CAPS:
        raise ValueError('Unplanned experimental ceiling')
    face, hair = (proof['parts'][p]['components'] for p in ('face', 'hair'))
    if set(face) != {'skin'} or set(hair) != {'hair'}:
        raise ValueError('One opaque and one masked section required')
    parts = [face['skin'], hair['hair']]
    triangles = sum(p['triangles'] for p in parts)
    if not 0 < triangles <= cap:
        raise ValueError('Cooked complete head exceeds experimental ceiling')
    return dict(triangles=triangles, face_triangles=parts[0]['triangles'],
                hair_triangles=parts[1]['triangles'],
                vertices=sum(p['cooked_vertices'] for p in parts), sections=2)


def validate_cohort(scope, prepared, verified):
    if scope['teams'] != [100, 108]:
        raise ValueError('Package is limited to the explicit Barca/MU pair')
    selected = set(scope['selected_base_ids'])
    if len(prepared) != len(selected) or {r['base_id'] for r in prepared} != selected:
        raise ValueError('All selected team sources must finish preparation')
    ready = {r['base_id'] for r in prepared if r['status'] in ('prepared', 'prepared_cached')}
    if len(verified) != len(ready) or {r['base_id'] for r in verified} != ready:
        raise ValueError('Every prepared head requires a cook verification result')
    owners = {r['base_id']: r for r in prepared}
    for row in verified:
        if any(row[k] != owners[row['base_id']][k] for k in
               ('native_player_id', 'fingerprint', 'cache_key')):
            raise ValueError('Cooked head changed source identity or recipe')
    if len({r['native_player_id'] for r in prepared}) != len(prepared):
        raise ValueError('Duplicate native owner')
    return [r for r in verified if r['status'] in ('validated', 'validated_cached')]


def head_limit(row,cap):
    retained=row.get('accepted_baseline')
    if not retained:return cap
    path=Path(retained['verification'])
    if sha(path)!=retained['verification_sha256']:
        raise ValueError('Retained baseline verification changed')
    owners=[p for p in read(path) if p['base_id']==row['base_id']]
    if len(owners)!=1 or owners[0]['status'] not in ('validated','validated_cached'):
        raise ValueError('Retained head lacks baseline verification')
    old=owners[0]
    if any(row[k]!=old[k] for k in ('native_player_id','fingerprint','cache_key','cooked_folder','cooked_cache_key')):
        raise ValueError('Retained head changed original identity or cooked cache')
    total=retained['triangles']
    if type(total) is not int or total!=old['triangles'] or not cap<total<=7000:
        raise ValueError('Invalid retained original triangle count')
    return 7000


def package(config, scope, baseline_stage, baseline_verification):
    work = Path(config['work_dir']).resolve()
    if not work.is_relative_to(ROOT / 'local-debug'):
        raise ValueError('Package output must remain ignored and local')
    cap = config['experimental_head_cap']
    prepared, verified = read(work/'prepare-report.json'), read(work/'verify-report.json')
    ready = validate_cohort(scope, prepared, verified)
    if not ready:
        raise ValueError('No independently verified heads')
    baseline = read(baseline_verification)
    if scope['verification_sha256'] != sha(baseline_verification):
        raise ValueError('Scope verification differs from the selected baseline')
    owners = {p['base_id']: p for p in baseline['players']}
    stage_source = Path(baseline_stage)
    private = {BASE+NEW_PARENT+s for s in ('.uasset', '.uexp')} | {
        BASE+NEW_NORMAL+s for s in ('.uasset', '.uexp', '.ubulk')}
    for name in private:
        if sha(stage_source/name) != baseline['asset_hashes'].get(name):
            raise ValueError('Private neutral material dependency changed')
    recipe = dict(cap=cap, scope=scope, prepare_sha256=sha(work/'prepare-report.json'),
                  verify_sha256=sha(work/'verify-report.json'), code_sha256=sha(__file__),
                  hair_mip_policy='nonempty_fully_discarded_1_or_2_pixel_alpha_scale_v1',
                  hair_mip_code_sha256=sha(Path(__file__).with_name('realface_hair_mips.py')),
                  material_hashes={n:baseline['asset_hashes'][n] for n in sorted(private)})
    if config.get('experimental_release_label'):
        if not re.fullmatch(r'v46-balanced-(4500|5000)',config['experimental_release_label']):
            raise ValueError('Unsupported explicit experiment label')
        recipe['release_label']=config['experimental_release_label']
    key = key_of(recipe)
    job = work/'test-packages'/key[:16]
    if (job/'complete.json').exists():
        stamp = read(job/'complete.json')
        if stamp['key'] != key or hash_tree(job/'release') != stamp['release_hashes']:
            raise ValueError('Existing experiment release changed')
        return job/'release'
    if job.exists():
        raise ValueError('Preserve the incomplete package job for inspection: '+str(job))
    job.mkdir(parents=True)
    write(job/'recipe.json', recipe)
    stage = job/'stage'
    for name in private:
        dest = stage/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage_source/name, dest)
    template = (stage/BASE/(NEW_PARENT+'.uasset')).read_bytes()
    players = []
    for row in ready:
        folder, cooked = Path(row['folder']), Path(row['cooked_folder'])
        if not valid_prepared_cache(folder, row['cache_key']) or not valid_cache(cooked, row['cooked_cache_key']):
            raise ValueError('Prepared/cooked cache changed: '+str(row['base_id']))
        if any(row[k] != owners[row['base_id']][k] for k in ('native_player_id', 'fingerprint')):
            raise ValueError('Package owner differs from verified team scope')
        profile = read(folder/'ue-profile.json')
        if any(profile.get(k) != v for k, v in POLICY.items()):
            raise ValueError('Experiment texture/material policy changed')
        proof, projection = read(folder/'simplification.json'), read(folder/'hair-projection.json')
        limit=head_limit(row,cap)
        total = validate_preparation(proof, projection, limit)
        checked = counts(read(cooked/'verification.json'), limit)
        if row.get('accepted_baseline') and total!=row['accepted_baseline']['triangles']:
            raise ValueError('Retained head geometry differs from original')
        if total != checked['triangles']:
            raise ValueError('Prepared and cooked triangle counts differ')
        native = row['native_player_id']
        names = asset_names(native)
        if {p.name for p in (cooked/'assets').iterdir()} != {Path(n).name for n in names}:
            raise ValueError('Unexpected per-player payload')
        for name in names:
            dest = stage/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cooked/'assets'/Path(name).name, dest)
        name = FACE+f'face_{native}.uasset'
        patch_names(cooked/'assets'/Path(name).name, stage/name,
                    {PARENT:NEW_PARENT, GAME+PARENT:GAME+NEW_PARENT}, template)
        if dependency_names(stage, native):
            raise ValueError('Packaged mesh/material import declarations differ')
        mip_repair=protect_texture(stage/FACE/(str(native)+'_hair_parts_color_tablet.uexp'))
        textures = {kind:texture_evidence(Texture(stage/FACE/(str(native)+suffix+'.uexp')))
                    for kind, suffix in (('face','_face_tablet'), ('hair','_hair_parts_color_tablet'))}
        if not textures['face']['every_mip_opaque']:
            raise ValueError('Face texture has transparent pixels')
        if mip_repair['source_has_visible_hair'] and textures['hair']['fully_discarded_mips']:
            raise ValueError('Nonempty hair still contains a fully discarded mip')
        info = {k:row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')}
        info.update(checked, team_ids=owners[row['base_id']]['team_ids'],
                    status='candidate_pending_device', textures=textures,
                    geometry_changed=not bool(row.get('reuse_cooked')),
                    hair_mip_repair=mip_repair,
                    hair_projection=projection, source=read(folder/'recipe.json')['source']['input_hashes'])
        if row.get('accepted_baseline'):info['accepted_baseline']=row['accepted_baseline']
        players.append(info)
    hashes = hash_tree(stage)
    expected = private | {n for r in ready for n in asset_names(r['native_player_id'])}
    if set(hashes) != expected:
        raise ValueError('Unexpected complete package payload')
    label = f'v41-{cap//1000}k' if cap%1000==0 else 'v41-4p5k'
    label=config.get('experimental_release_label',label)
    release = job/'release'
    pak = release/'update/PesMobile/Content/Paks'/f'PesMobile-Barca-MU-Faces-{label}-TEST-Android_ETC1_P.pak'
    pak.parent.mkdir(parents=True)
    response = job/'response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n', encoding='utf-8')
    command([config['unrealpak'], pak, '-Create='+str(response), '-compress'], job/'package.log')
    command([config['unrealpak'], pak, '-Test'], job/'test.log')
    command([config['repak'], 'unpack', pak, '-o', job/'roundtrip'], job/'roundtrip.log')
    if hash_tree(job/'roundtrip') != hashes:
        raise ValueError('PAK roundtrip changed payload')
    packaged = {r['base_id'] for r in ready}
    retained_by_id={p['base_id']:p['accepted_baseline'] for p in players if p.get('accepted_baseline')}
    status_rows = []
    evidence = {r['base_id']: r for r in prepared+verified}
    for base in sorted(set(scope['selected_base_ids']) | {r['base_id'] for r in scope['unresolved']}):
        owner = owners[base]
        row = dict(base_id=base, native_player_id=owner.get('native_player_id'), name=owner['name'],
                   team_ids=owner['team_ids'], status='candidate_pending_device' if base in packaged else 'native_fallback')
        if base not in packaged:
            row['reason'] = evidence.get(base, owner).get('reason', evidence.get(base, owner).get('status'))
        elif base in retained_by_id:
            row['reason']='Retained original v41: '+retained_by_id[base]['reason']
        status_rows.append(row)
    retained=[dict(base_id=p['base_id'],name=p['name'],triangles=p['triangles'],
                   reason=p['accepted_baseline']['reason']) for p in players if p.get('accepted_baseline')]
    verification = dict(version=label, experimental_only=True,
                        budget=dict(target_head_triangles=cap,max_head_triangles=max(p['triangles'] for p in players),
                                    max_sections=2,retained_originals=retained),
                        players_in_package=players, players=status_rows, scope=scope,
                        asset_hashes=hashes, pak_sha256=sha(pak), pak_bytes=pak.stat().st_size,
                        unpack_hashes_match=True, hardware_accepted=False, runtime_code_changed=False,
                        sweet_spot_selected=False, neutral_material_hashes=recipe['material_hashes'])
    write(release/'VERIFICATION.json', verification)
    with (release/'PLAYER-STATUS.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=('base_id','native_player_id','name','team_ids','status','reason'))
        writer.writeheader(); writer.writerows(status_rows)
    with (release/'PLAYER-BUDGET.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        fields=('base_id','native_player_id','name','triangles','face_triangles','hair_triangles',
                'vertices','sections','geometry_changed','above_target_original_retained')
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for player in players:
            writer.writerow(dict({k:player[k] for k in fields[:-1]},
                                 above_target_original_retained=bool(player.get('accepted_baseline'))))
    (release/'INSTALL.txt').write_text(
        f'FootballNX Barca/MU {label} TEST: {len(players)} kandidat, {len(status_rows)-len(players)} fallback bawaan.\n'
        f'Target {cap:,} segitiga per kepala, dua section. {len(retained)} kepala asli dipertahankan; '
        f'maksimum aktual {max(p["triangles"] for p in players):,}. Belum diuji FPS/animasi Switch.\n\n'
        'Tutup game. Simpan PAK wajah sebelumnya di luar folder Paks untuk rollback.\n'
        'Gunakan tepat SATU PAK wajah tambahan. Salin isi update ke runtime pes21_nx.\n'
        'PAK ini tidak mengganti NRO/CPK/OBB/save; hanya mencakup roster Barca dan MU.\n'
        'Uji starting XI yang sama, Konami NIGHT dan DAY terpisah, operan dekat kamera,\n'
        'replay, close-up dan selebrasi. Periksa mata, pipi, leher, rambut dan tekstur.\n'
        'Simpan scene-runtime.log tiap percobaan memakai NRO diagnostik yang sama.\n'
        'Bandingkan v41-7k asli dengan kandidat ini pada NRO yang sama; jangan ubah kamera.\n'
        f'Kembali ke NRO normal setelah pengukuran. Plafon {cap:,} adalah percobaan,\n'
        'bukan hasil pengukuran sweet spot. Daftar per pemain ada di PLAYER-STATUS.csv.\n', encoding='utf-8')
    archive = release/f'FootballNX-Barca-MU-{label}-TEST.zip'
    files = [p for p in release.rglob('*') if p.is_file()]
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(files): zipped.write(path, path.relative_to(release))
    write(job/'complete.json', dict(key=key, release_hashes=hash_tree(release)))
    write(work/'latest-test.json', dict(release=str(release), zip=str(archive), zip_sha256=sha(archive)))
    return release


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--scope', required=True)
    p.add_argument('--baseline-stage', required=True)
    p.add_argument('--baseline-verification', required=True)
    a = p.parse_args()
    print(package(read(a.config), read(a.scope), a.baseline_stage, a.baseline_verification), flush=True)
