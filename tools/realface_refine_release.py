"""Merge validated per-player repairs into an immutable mobile face release."""
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
import zipfile

from realface_batch import command, key_of, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_mobile import cooked_counts
from realface_pipeline import sha
from realface_refine import baseline, HERE, REFINE_CODE
from realface_surface_patch import FACE, hash_tree


def permitted_changes(rows):
    names = set()
    for row in rows:
        native = str(row['native_player_id'])
        if row['refine_face']:
            names |= {FACE+native+'_face'+s for s in ('.uasset', '.uexp')}
        if row['refine_hair']:
            names |= {FACE+native+'_hair'+s for s in ('.uasset', '.uexp')}
            names |= {FACE+native+'_hair_parts_color_tablet'+s for s in ('.uasset', '.uexp', '.ubulk')}
    return names


def check_preservation(before, after, allowed):
    if set(before) != set(after) or not allowed <= set(before):
        raise ValueError('Asset coverage changed outside the verified release')
    changed = {name for name in before if before[name] != after[name]}
    if not changed <= allowed:
        raise ValueError('An unapproved material, texture or mesh was modified')
    return sorted(changed)


def package(config):
    report, owners = baseline(config)
    work = Path(config['work_dir'])
    plan, rows = read(work/'plan.json'), read(work/'verify-report.json')
    planned = {r['base_id']:r for r in plan['players']}
    if len(rows) != len(planned) or {r['base_id'] for r in rows} != set(planned):
        raise ValueError('Every selected repair must pass cooked verification before release')
    code = {name:sha(HERE/name) for name in REFINE_CODE}
    for row in rows:
        expected = planned[row['base_id']]
        if (row['status'] not in ('validated', 'validated_cached') or
                any(row[k] != expected[k] for k in ('native_player_id','fingerprint','cache_key','refine_face','refine_hair')) or
                row['recipe_source_sha256'] != code):
            raise ValueError('Repair identity, code or validation is stale')
        if (not valid_prepared_cache(Path(row['folder']), row['cache_key']) or
                not valid_cache(Path(row['cooked_folder']), row['cooked_cache_key'])):
            raise ValueError('A prepared or cooked repair cache changed')
        cooked_counts(read(Path(row['cooked_folder'])/'verification.json'))
    label = config.get('release_label', 'v37')
    if not re.fullmatch(r'v[0-9]+', label): raise ValueError('Invalid release label')
    recipe = dict(baseline_pak=sha(config['baseline_pak']),
                  baseline_verification=sha(config['baseline_verification']),
                  identity_state=sha(config['identity_state']),
                  repairs=[(r['base_id'],r['cooked_cache_key']) for r in sorted(rows,key=lambda r:r['base_id'])],
                  plan=key_of(plan), code=code, release_code=sha(Path(__file__)), label=label)
    key = key_of(recipe)
    job = work/'builds'/key[:16]
    latest_path = work/'latest.json'
    if latest_path.exists():
        latest = read(latest_path)
        prior = Path(latest['release']).resolve().parent
        if latest['key'] == key and prior.is_relative_to((work/'builds').resolve()): job = prior
    if (job/'complete.json').exists():
        stamp = read(job/'complete.json')
        if stamp['key'] != key or hash_tree(job/'release') != stamp['release_hashes']:
            raise ValueError('Cached release changed')
        print(json.dumps(dict(status='verified_cached', release=str(job/'release'))), flush=True)
        return job/'release'
    if job.exists(): job = work/'builds'/(key[:16]+'-retry-'+uuid.uuid4().hex[:8])
    job.mkdir(parents=True)
    write(job/'recipe.json', recipe)
    stage = job/'stage'
    command([config['repak'], 'unpack', config['baseline_pak'], '-o', stage], job/'baseline-unpack.log')
    if hash_tree(stage) != report['asset_hashes']:
        raise ValueError('Unpacked baseline differs from verified asset hashes')
    allowed = permitted_changes(rows)
    for row in rows:
        assets = Path(row['cooked_folder'])/'assets'
        for name in permitted_changes([row]):
            shutil.copy2(assets/Path(name).name, stage/name)
    hashes = hash_tree(stage)
    changed = check_preservation(report['asset_hashes'], hashes, allowed)
    repaired = {r['base_id']:r for r in rows}
    projections = {r['base_id']:r for r in read(work/'baseline-surface-audit.json')}
    players = []
    for original in report['players']:
        player = dict(original, status='baseline_retained_pending_device',
                      geometry_byte_identical=True, refined_face=False, refined_hair=False,
                      baseline_projection=projections[original['base_id']])
        row = repaired.get(original['base_id'])
        if row:
            folder = Path(row['folder'])
            proof = read(folder/'simplification.json')
            verified = read(Path(row['cooked_folder'])/'verification.json')
            counts = cooked_counts(verified)
            if counts['triangles'] != proof['total_triangles']:
                raise ValueError('Prepared/cooked triangle counts differ')
            player.update(counts, face_triangles=proof['face']['total'], hair_triangles=proof['hair']['total'],
                          refined_face=row['refine_face'], refined_hair=row['refine_hair'],
                          status='refined_validated_pending_device', geometry_byte_identical=False)
            if row['refine_face']:
                player.update(surface_projection=read(folder/'surface-projection.json'),
                              skin_features=read(folder/'skin-feature-locks.json'),
                              skin_error=proof['face']['roles']['skin']['error'],
                              normal_transfer=verified['parts']['face']['components']['skin']['normal_transfer'])
            if row['refine_hair']: player['hair_projection'] = read(folder/'hair-projection.json')
        players.append(player)
    release = job/'release'
    pak = release/'update/PesMobile/Content/Paks'/('PesMobile-Barca-MU-Faces-Mobile-'+label+'-Android_ETC1_P.pak')
    pak.parent.mkdir(parents=True)
    response = job/'pak-response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n', encoding='utf-8')
    command([config['unrealpak'], pak, '-Create='+str(response), '-compress'], job/'package.log')
    command([config['unrealpak'], pak, '-Test'], job/'package-test.log')
    command([config['repak'], 'unpack', pak, '-o', job/'roundtrip'], job/'roundtrip.log')
    if hash_tree(job/'roundtrip') != hashes: raise ValueError('PAK roundtrip hashes differ')
    verification = dict(version='Mobile '+label+' refined faces and compact hair', players=players,
                        asset_hashes=hashes, pak_sha256=sha(pak), pak_bytes=pak.stat().st_size,
                        source_pak_sha256=report['pak_sha256'], budget=dict(max_head_triangles=2000,max_sections=2),
                        changed_assets=changed, preserved_assets=len(hashes)-len(changed),
                        face_colour_and_materials_byte_identical=True, neutral_normal_preserved=True,
                        unpack_hashes_match=True, hardware_accepted=False, runtime_code_changed=False)
    write(release/'VERIFICATION.json', verification)
    write(release/'PLAYER-STATUS.json', players)
    outside = read(Path(config['baseline_verification']).parent/'OUTSIDE-CANDIDATE.json')
    write(release/'OUTSIDE-CANDIDATE.json', outside)
    fields = ['base_id','native_player_id','name','status','refined_face','refined_hair',
              'face_triangles','hair_triangles','triangles','vertices','sections']
    with (release/'PLAYER-STATUS.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(sorted(players,key=lambda p:p['name']))
    (release/'INSTALL.txt').write_text(
        'FootballNX Mobile '+label+' - wajah dan rambut ringan Barca/MU\n\n'
        f'{len(players)} kepala; {sum(p["refined_face"] for p in players)} wajah dan '
        f'{sum(p["refined_hair"] for p in players)} rambut diperbaiki.\n'
        'Maksimal 2.000 segitiga, dua material per kepala. Normal map netral v36 dipertahankan.\n'
        'Daftar lengkap: PLAYER-STATUS.csv. Identitas di luar kandidat: OUTSIDE-CANDIDATE.json.\n\n'
        'Tutup game, pindahkan PAK real face v36/v35/v34/v24/Barcelona/Yamal/Raphinha lama\n'
        'ke luar Paks untuk rollback, lalu salin ISI folder update ke SD:/switch/pes21_nx/.\n'
        'Gunakan hanya satu PAK wajah kandidat. NRO, CPK dan OBB tetap memakai versi sekarang.\n\n'
        'Belum diuji di Switch. Tes Barca vs MU, DAY/NIGHT, operan dekat kamera,\n'
        'dan close-up bibir/mata/leher serta rambut Gordon pada selebrasi/replay.\n'
        'Rollback: keluarkan PAK ini lalu pulihkan PAK sebelumnya.\n', encoding='utf-8')
    (release/'SHA256SUMS.txt').write_text(sha(pak)+'  '+pak.relative_to(release).as_posix()+'\n')
    archive = release/('FootballNX-Mobile-'+label+'-Barca-MU.zip')
    members = sorted(p for p in release.rglob('*') if p.is_file())
    root = 'FootballNX-Mobile-'+label+'/'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for p in members: bundle.write(p, root+p.relative_to(release).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() or hashlib.sha256(bundle.read(root+pak.relative_to(release).as_posix())).hexdigest() != sha(pak):
            raise ValueError('ZIP integrity or embedded PAK hash differs')
    write(release/'ARCHIVE.json', dict(file=archive.name, bytes=archive.stat().st_size, sha256=sha(archive)))
    write(job/'complete.json', dict(key=key, release_hashes=hash_tree(release)))
    write(latest_path, dict(key=key, release=str(release)))
    print(json.dumps(dict(release=str(release), players=len(players), repaired=len(rows),
                          triangles_max=max(p['triangles'] for p in players), pak_sha256=sha(pak))), flush=True)
    return release
