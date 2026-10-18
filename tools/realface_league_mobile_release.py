"""Assemble verified two-section league heads with the accepted neutral material."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from realface_batch import command, key_of, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_lite import sources
from realface_mobile import PROFILE_POLICY, cooked_counts
from realface_pipeline import sha
from realface_surface_patch import BASE, FACE, GAME, PARENT, NEW_PARENT, NEW_NORMAL, asset_names, hash_tree, patch_names


def validate_rows(rows, expected, inherited, current_code):
    if (len(rows)!=len(expected) or {r['base_id'] for r in rows}!=set(expected) or
            len({r['native_player_id'] for r in rows})!=len(rows)):
        raise ValueError('Every available league source must be present exactly once')
    for row in rows:
        source=expected[row['base_id']]
        if any(row[k]!=source[k] for k in ('native_player_id','fingerprint')):
            raise ValueError('League face ownership changed')
        if row['status'] not in ('validated','validated_cached'):
            raise ValueError('Unverified league head blocks packaging')
        if row['base_id'] in inherited:
            accepted=inherited[row['base_id']]
            if any(row[k]!=accepted[k] for k in ('cache_key','cooked_cache_key','inherited_release_sha256')):
                raise ValueError('Inherited verified recipe changed')
        elif row['recipe_source_sha256']!=current_code(row['budgets']):
            raise ValueError('New league head has stale geometry code')


def package(config):
    from realface_league_mobile import inherited, recipe_code
    work=Path(config['work_dir']);rows=read(work/'verify-report.json')
    if (work/'QUALITY-HOLD.json').exists():
        raise ValueError('League visual regression unresolved; see QUALITY-HOLD.json')
    expected={r['base_id']:r for r in sources(config)}
    carried=inherited(config,expected)
    validate_rows(rows,expected,carried,recipe_code)
    source=read(config['source_verification']);baseline=read(config['inherit_verification'])
    recipe=dict(verification=sha(work/'verify-report.json'),source=sha(config['source_verification']),
                inherited=baseline['pak_sha256'],code=sha(__file__),label=config['release_label'])
    key=key_of(recipe);job=work/'releases'/key[:16];release=job/'release'
    stamp=job/'complete.json'
    if stamp.exists():
        if read(stamp).get('key')!=key or hash_tree(release)!=read(stamp)['release_hashes']:
            raise ValueError('Cached release bytes changed')
        print(json.dumps(dict(status='verified_cached',release=str(release))),flush=True)
        return release
    job.mkdir(parents=True,exist_ok=True);write(job/'recipe.json',recipe)
    original=job/'inherited'
    if not original.exists():
        command([config['repak'],'unpack',config['inherit_pak'],'-o',original],job/'inherit-unpack.log')
    if hash_tree(original)!=baseline['asset_hashes']:
        raise ValueError('Inherited PAK assets differ')
    stage=job/'stage';private={BASE+NEW_PARENT+s for s in ('.uasset','.uexp')} | {
        BASE+NEW_NORMAL+s for s in ('.uasset','.uexp','.ubulk')}
    for name in private:
        dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original/name,dest)
    template=(stage/BASE/(NEW_PARENT+'.uasset')).read_bytes()
    old_players={p['base_id']:p for p in baseline['players']}
    memberships={p['base_id']:p for p in source['players']}
    players=[];hashes={n:sha(stage/n) for n in private};relinked={}
    for index,row in enumerate(rows,1):
        prepared=Path(row['folder']);cache=Path(row['cooked_folder'])
        if (not valid_cache(cache,row['cooked_cache_key']) or
                not valid_prepared_cache(prepared,row['cache_key'])):
            raise ValueError('Verified league cache changed: '+str(row['base_id']))
        proof=read(cache/'verification.json');counts=cooked_counts(proof)
        names=asset_names(row['native_player_id'])
        if row['base_id'] in carried:
            info=dict(old_players[row['base_id']],inherited_v37=True)
            for name in names:
                dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original/name,dest)
        else:
            profile=read(prepared/'ue-profile.json')
            if any(profile.get(k)!=v for k,v in PROFILE_POLICY.items()):
                raise ValueError('League material policy differs')
            if {p.name for p in (cache/'assets').iterdir()}!={Path(n).name for n in names}:
                raise ValueError('Unexpected shared / extra material payload')
            for name in names:
                dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(cache/'assets'/Path(name).name,dest)
            name=FACE+'face_'+str(row['native_player_id'])+'.uasset'
            relinked[name]=patch_names(cache/'assets'/Path(name).name,stage/name,
                {PARENT:NEW_PARENT,GAME+PARENT:GAME+NEW_PARENT},template)
            info=dict(face_triangles=proof['parts']['face']['components']['skin']['triangles'],
                      hair_triangles=proof['parts']['hair']['components']['hair']['triangles'],
                      hair_projection=read(prepared/'hair-projection.json'),
                      face_projection=read(prepared/'surface-projection.json'),inherited_v37=False)
        if counts['triangles']!=info['face_triangles']+info['hair_triangles']:
            raise ValueError('Packaged counts differ from independently cooked buffers')
        info.update({k:row[k] for k in ('base_id','native_player_id','fingerprint','name')})
        info.update(counts,status='validated_pending_device',material=NEW_PARENT,
                    team_ids=memberships[row['base_id']]['team_ids'])
        players.append(info);hashes.update({n:sha(stage/n) for n in names})
        if index%100==0: print(json.dumps(dict(packaged_heads=index,total=len(rows))),flush=True)
    if hash_tree(stage)!=hashes: raise ValueError('Unexpected package payload')
    label=config['release_label'];pak=release/'update/PesMobile/Content/Paks'/(
        'PesMobile-League-Faces-Mobile-'+label+'-Android_ETC1_P.pak')
    pak.parent.mkdir(parents=True,exist_ok=True)
    response=job/'pak-response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n',encoding='utf-8')
    command([config['unrealpak'],pak,'-Create='+str(response),'-compress'],job/'package.log')
    command([config['unrealpak'],pak,'-Test'],job/'package-test.log')
    command([config['repak'],'unpack',pak,'-o',job/'roundtrip'],job/'roundtrip.log')
    if hash_tree(job/'roundtrip')!=hashes: raise ValueError('Independent league PAK roundtrip failed')
    outside=[p for p in source['players'] if p['base_id'] not in expected]
    teams=[]
    for team in source['teams']:
        covered=sum(team['team_id'] in p['team_ids'] for p in players)
        missing=sum(team['team_id'] in p.get('team_ids',[]) for p in outside)
        teams.append(dict(team,covered=covered,outside=missing,total=covered+missing))
    report=dict(version='Mobile '+label+' English/Spanish leagues',players=players,teams=teams,
        asset_hashes=hashes,pak_sha256=sha(pak),pak_bytes=pak.stat().st_size,
        budget=dict(max_head_triangles=2000,max_sections=2),source=recipe,
        inherited_heads_byte_identical=len(carried),neutral_material_byte_identical_to_v37=True,
        relinked_headers=relinked,unpack_hashes_match=True,hardware_accepted=False,runtime_code_changed=False)
    write(release/'VERIFICATION.json',report);write(release/'PLAYER-STATUS.json',players)
    write(release/'OUTSIDE-CANDIDATE.json',outside);write(release/'TEAM-STATUS.json',teams)
    for filename,data,fields in (
        ('PLAYER-STATUS.csv',players,['base_id','native_player_id','name','team_ids','status','face_triangles','hair_triangles','triangles','sections','inherited_v37']),
        ('OUTSIDE-CANDIDATE.csv',outside,['base_id','native_player_id','name','team_ids','status']),
        ('TEAM-STATUS.csv',teams,['team_id','name','category','covered','outside','total'])):
        with (release/filename).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(data)
    (release/'INSTALL.txt').write_text(
        'FootballNX Mobile '+label+' - Liga Inggris dan Spanyol\n\n'
        f'{len(players)} real face terverifikasi, maksimal 2.000 segitiga dan dua material per kepala.\n'
        'Wajah diprioritaskan; rambut rumit disederhanakan dengan menjaga bentuk dan cakupan.\n'
        'Perbaikan normal wajah v36/v37 disertakan. Hasil 51 pemain Barca/MU v37 dipertahankan.\n'
        f'{len(outside)} pemain belum punya sumber terverifikasi; lihat OUTSIDE-CANDIDATE.csv.\n'
        'Daftar seluruh hasil: PLAYER-STATUS.csv; cakupan tiap tim: TEAM-STATUS.csv.\n\n'
        'Saat game ditutup, pindahkan SEMUA PAK real face lama (v24/v34/v35/v36/v37/Barcelona/\n'
        'Yamal/Raphinha) ke luar folder Paks. Simpan untuk rollback. Pakai satu PAK wajah ini.\n'
        'Salin ISI folder update ke SD:/switch/pes21_nx/. NRO/CPK/stadion tetap digunakan.\n'
        'Belum diuji di Switch. Uji operan dekat kamera DAY/NIGHT dan close-up selebrasi.\n'
        'Rollback: keluarkan PAK ini dan pulihkan PAK wajah sebelumnya.\n',encoding='utf-8')
    (release/'SHA256SUMS.txt').write_text(sha(pak)+'  '+pak.relative_to(release).as_posix()+'\n')
    archive=release/('FootballNX-Mobile-'+label+'-League.zip');members=list(release.rglob('*'))
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for p in members:
            if p.is_file(): bundle.write(p,'FootballNX-Mobile-'+label+'/'+p.relative_to(release).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if (bundle.testzip() is not None or hashlib.sha256(bundle.read('FootballNX-Mobile-'+label+'/'+
                pak.relative_to(release).as_posix())).hexdigest()!=sha(pak)):
            raise ValueError('Archive CRC or embedded PAK hash failed')
    write(release/'ARCHIVE.json',dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive)))
    write(stamp,dict(key=key,release_hashes=hash_tree(release)))
    write(work/'latest.json',dict(key=key,release=str(release)))
    print(json.dumps(dict(release=str(release),players=len(players),outside=len(outside),pak_sha256=sha(pak))),flush=True)
    return release
