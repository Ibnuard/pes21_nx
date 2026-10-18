"""Resumable two-material, strictly bounded mobile head canary.

Reuse the identity-verified offline factory and native cook validator. This
recipe never promotes heavier quality levels or changes the active runtime.
"""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import zipfile
from realface_batch import command,key_of,output_hashes,valid_prepared_cache,valid_cache
from realface_batch_inventory import read,write
from realface_pipeline import sha
from realface_lite import sources,LIMITS

HERE=Path(__file__).resolve().parent
LEVELS=[dict(face_skin=1500,eye=96,hair=380,head_cap=2000,skin_error_cm=.45),
        dict(face_skin=1500,eye=128,hair=360,head_cap=2000,skin_error_cm=.45),
        dict(face_skin=1600,eye=96,hair=280,head_cap=2000,skin_error_cm=.35),
        dict(face_skin=1500,eye=128,hair=360,head_cap=2000,skin_error_cm=.4,hair_mode='shell'),
        dict(face_skin=1600,eye=128,hair=260,head_cap=2000,skin_error_cm=.3,hair_mode='shell'),
        dict(face_skin=1600,eye=96,hair=170,head_cap=2000,skin_error_cm=.3,hair_mode='shell'),
        dict(face_skin=1600,eye=128,hair=260,head_cap=2000,skin_error_cm=.3,skin_normal_weight=0.),
        dict(face_skin=1600,eye=128,hair=260,head_cap=2000,skin_error_cm=.3,skin_normal_weight=0.,hair_mode='shell'),
        dict(face_skin=1750,eye=128,hair=110,head_cap=2000,skin_error_cm=.25,skin_normal_weight=0.,hair_mode='shell'),
        dict(face_skin=1800,eye=96,hair=100,head_cap=2000,skin_error_cm=.25,skin_normal_weight=0.,hair_mode='shell'),
        dict(face_skin=1350,eye=96,hair=550,head_cap=2000,skin_error_cm=.4,hair_mode='closed'),
        dict(face_skin=1250,eye=96,hair=650,head_cap=2000,skin_error_cm=.4,hair_mode='closed'),
        dict(face_skin=1250,eye=96,hair=650,head_cap=2000,skin_error_cm=.4,hair_mode='braids')]
for budget in LEVELS:budget.update(eye_error_cm=.06,eye_uv_weight=.1)
PROFILE_POLICY=dict(skin_materials=['mobile_opaque'],eye_material='__merged_eye_unused',
                    hair_materials=['lite_hair'],hair_skin_materials=[],opaque_eye_atlas=True,hair_texture_size=128)
# Hash geometry code and this attempt's explicit policy/budget, not the
# orchestrator itself. Adding another fallback must not rebuild accepted heads.
CODE=('blender_realface_mobile.py','realface_mobile_geometry.py',
      'blender_realface_lite.py','blender_meshopt.py','meshopt_reduce.mjs',
      'blender_fit_realface.py','blender_export_ue_fbx.py')
CODE+=('blender_realface_hair_shell.py',)
CODE+=('blender_realface_eye_cleanup.py','realface_eye_enclosure.py','realface_eye_fit.py','realface_eye_boundary.py')
CODE+=('blender_realface_skin_visibility.py',)
CODE+=('blender_realface_hair_reduce.py',)


def recipe_code(budgets=None):
    names=CODE+(('blender_realface_braids.py',) if (budgets or {}).get('hair_mode')=='braids' else ())
    return {name:sha(HERE/name) for name in names}


def selected_sources(config):
    ids=set(config['mobile_base_ids'])
    rows=[r for r in sources(config) if r['base_id'] in ids]
    if not ids or len(rows)!=len(ids):raise ValueError('Canary identities not fully covered')
    return rows


def ordered_levels(row,previous=None):
    """Retry a known allocation first, while revalidating all newly made bytes."""
    order=list(range(len(LEVELS)))
    if not previous or any(previous.get(k)!=row[k] for k in ('base_id','native_player_id','fingerprint')):
        return [(i,LEVELS[i]) for i in order]
    if previous.get('status') in ('prepared','prepared_cached') and previous.get('budgets') in LEVELS:
        first=LEVELS.index(previous['budgets']);order.remove(first);order.insert(0,first)
    elif previous.get('status')=='held_geometry':
        tried={a['level'] for a in previous.get('attempts',[])}
        order=[i for i in order if i not in tried]+[i for i in order if i in tried]
    return [(i,LEVELS[i]) for i in order]


def prepare_one(config,row,previous=None):
    profile=read(row['profile'])
    if profile['native_player_id']!=row['native_player_id'] or profile.get('hair_skin_materials'):
        raise ValueError('Unsupported identity or skin carried in the hair mesh')
    base_code=recipe_code()
    files={str(HERE/name):digest for name,digest in base_code.items()}
    for name,digest in row['input_hashes'].items():
        if sha(name)!=digest:raise ValueError('Pinned source changed: '+name)
        files[name]=digest
    for name in ('native_rig','cooked_rig','meshoptimizer'):files[config[name]]=sha(config[name])
    limits=dict(LIMITS,hair={})
    attempts=[]
    for level,budgets in ordered_levels(row,previous):
        source_code=recipe_code(budgets)
        attempt_files=dict(files,**{str(HERE/name):digest for name,digest in source_code.items()})
        key=key_of(dict(files=attempt_files,profile=profile,ue_policy=PROFILE_POLICY,budgets=budgets,limits=limits,fingerprint=row['fingerprint']))
        folder=Path(config['cache_dir'])/'mobile-jobs'/(str(row['base_id'])+'-'+key[:16])
        entry={k:row[k] for k in ('base_id','native_player_id','fingerprint','name')}
        entry.update(folder=str(folder),cache_key=key,quality_level=level,budgets=budgets,recipe_source_sha256=source_code)
        if valid_prepared_cache(folder,key):return dict(entry,status='prepared_cached')
        if (folder/'held.json').exists():attempts.append(read(folder/'held.json'));continue
        folder.mkdir(parents=True,exist_ok=True)
        job=dict(entry,source_profile=profile,native_rig=config['native_rig'],cooked_rig=config['cooked_rig'],
                 limits=limits,node=config['node'],meshoptimizer=config['meshoptimizer'],mobile_v35=True)
        write(folder/'job.json',job)
        try:
            script=HERE/('blender_realface_braids.py' if budgets.get('hair_mode')=='braids' else 'blender_realface_lite.py')
            command([config['blender'],'--background','--threads','2','--python-exit-code','1',
                     '--python',script,'--',folder/'job.json'],folder/'prepare.log')
            proof=read(folder/'simplification.json')
            if proof['total_triangles']>2000:raise ValueError('Strict mobile head ceiling exceeded')
            ue=dict(profile,face_fbx=str(folder/'face.fbx'),hair_fbx=str(folder/'hair.fbx'),
                    face_texture=str(folder/'opaque-atlas.png'))
            ue.update(PROFILE_POLICY)
            ue.pop('report',None);write(folder/'ue-profile.json',ue)
            if (folder/'hair-shell.png').exists():
                ue['hair_texture']=str(folder/'hair-shell.png');write(folder/'ue-profile.json',ue)
            write(folder/'recipe.json',dict(eye={},source=row,mobile_v35=True))
            write(folder/'complete.json',dict(cache_key=key,outputs=output_hashes(folder)))
            return dict(entry,status='prepared',triangles=proof['total_triangles'])
        except Exception as error:
            log=(folder/'prepare.log').read_text(errors='replace') if (folder/'prepare.log').exists() else ''
            reason=next((line for line in log.splitlines() if line.startswith(('ValueError:','RuntimeError:'))),str(error))
            held=dict(level=level,reason=reason);write(folder/'held.json',held);attempts.append(held)
            if reason.startswith(('ValueError: Aperture eye','ValueError: Eye shape','ValueError: Eye cleanup')):
                break  # Changing the triangle budget cannot repair an eye fit.
    return dict(entry,status='held_geometry',attempts=attempts)


def prepare(config,players,workers):
    work=Path(config['work_dir']);path=work/'prepare-report.json'
    saved={r['base_id']:r for r in read(path)} if path.exists() else {}
    rows=[r for r in selected_sources(config) if not players or r['base_id'] in players]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i,future in enumerate(as_completed([pool.submit(prepare_one,config,r,saved.get(r['base_id'])) for r in rows]),1):
            result=future.result();saved[result['base_id']]=result
            write(path,sorted(saved.values(),key=lambda r:r['base_id']))
            print(json.dumps(dict(done=i,total=len(rows),base_id=result['base_id'],status=result['status'],
                                  triangles=result.get('triangles'),attempts=result.get('attempts'))),flush=True)


def cooked_counts(proof):
    face=proof['parts']['face']['components'];hair=proof['parts']['hair']['components']
    if set(face)!={'skin'} or set(hair)!={'hair'}:
        raise ValueError('Cooked head must contain one opaque and one masked section')
    triangles=sum(p['triangles'] for p in list(face.values())+list(hair.values()))
    vertices=sum(p['cooked_vertices'] for p in list(face.values())+list(hair.values()))
    if not 0<triangles<=2000:raise ValueError('Cooked mobile head exceeds 2,000 triangles')
    return dict(triangles=triangles,vertices=vertices,sections=2)


def status(config):
    """Cheap coverage report; stale script revisions never count as finished."""
    from collections import Counter
    work=Path(config['work_dir'])
    def report(name):
        path=work/(name+'-report.json')
        return {r['base_id']:r for r in read(path)} if path.exists() else {}
    prepared=report('prepare');verified=report('verify');output=[]
    for source in selected_sources(config):
        row={k:source[k] for k in ('base_id','native_player_id','name')};row['status']='pending'
        p=prepared.get(row['base_id'],{})
        if p.get('recipe_source_sha256')==recipe_code(p.get('budgets')):
            row['status']=p['status']
            if p['status'] in ('prepared','prepared_cached'):
                row['triangles']=read(Path(p['folder'])/'simplification.json')['total_triangles']
                v=verified.get(row['base_id'],{})
                if v.get('cache_key')==p['cache_key']:row['status']=v['status']
            elif p.get('attempts'):row['reason']=p['attempts'][-1]['reason'].split(': {')[0]
        output.append(row)
    result=dict(counts=dict(Counter(row['status'] for row in output)),target=len(output),players=output)
    write(work/'status.json',result)
    print(json.dumps(dict(target=result['target'],counts=result['counts'],held=[p for p in output if p['status'].startswith('held')]),ensure_ascii=True),flush=True)
    return result


def package(config):
    work=Path(config['work_dir']);rows=read(work/'verify-report.json')
    expected={r['base_id']:r for r in selected_sources(config)}
    if (len(rows)!=len(expected) or {r['base_id'] for r in rows}!=set(expected) or
            any(r['status'] not in ('validated','validated_cached') for r in rows)):
        raise ValueError('Each requested identity must pass cook validation before packaging')
    if any(row.get('recipe_source_sha256')!=recipe_code(row.get('budgets')) or row.get('budgets') not in LEVELS for row in rows):
        raise ValueError('Prepared batch mixes older automation revisions; rerun prepare/cook/verify')
    stage=work/'package-stage';hashes={};players=[]
    prefix='PesMobile/Content/Assets/character/RealFace/'
    for row in rows:
        if any(row[k]!=expected[row['base_id']][k] for k in ('native_player_id','fingerprint')):
            raise ValueError('Cooked owner differs from source identity')
        cache=Path(row['cooked_folder']);prepared=Path(row['folder'])
        if not valid_cache(cache,row['cooked_cache_key']) or not valid_prepared_cache(prepared,row['cache_key']):
            raise ValueError('Verified player bytes changed')
        profile=read(prepared/'ue-profile.json')
        if any(profile.get(name)!=value for name,value in PROFILE_POLICY.items()):
            raise ValueError('Prepared material policy changed')
        verification=read(cache/'verification.json')
        counts=cooked_counts(verification);native=str(row['native_player_id'])
        names={native+part+suffix for part,suffixes in (
            ('_face',('.uasset','.uexp')),('_hair',('.uasset','.uexp')),
            ('_face_tablet',('.uasset','.uexp','.ubulk')),
            ('_hair_parts_color_tablet',('.uasset','.uexp','.ubulk'))) for suffix in suffixes}
        names.update({'face_'+native+'.uasset','face_'+native+'.uexp'})
        if {p.name for p in (cache/'assets').iterdir()}!=names:
            raise ValueError('Cooked payload has unexpected shared/eye assets')
        for name in sorted(names):
            source=cache/'assets'/name;dest=stage/(prefix+name);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,dest);hashes[prefix+name]=sha(dest)
        players.append(dict(base_id=row['base_id'],native_player_id=row['native_player_id'],name=row['name'],
                            status='validated_pending_device',quality_level=row['quality_level'],
                            face_triangles=verification['parts']['face']['components']['skin']['triangles'],
                            hair_triangles=verification['parts']['hair']['components']['hair']['triangles'],
                            normal_transfer=verification['parts']['face']['components']['skin']['normal_transfer'],
                            **counts,hair_projection=read(prepared/'hair-projection.json'),
                            skin_exterior=read(prepared/'skin-exterior.json'),
                            eye_enclosure=read(prepared/'eye-enclosure.json')))
    actual={p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    if actual!=set(hashes):raise ValueError('Unexpected files in package stage')
    release=work/'release';output=release/'update/PesMobile/Content/Paks';output.mkdir(parents=True,exist_ok=True)
    pak=output/'PesMobile-Barca-MU-Faces-Mobile-v35-Android_ETC1_P.pak'
    response=work/'pak-response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n')
    command([config['unrealpak'],pak,'-Create='+str(response),'-compress'],work/'package.log')
    command([config['unrealpak'],pak,'-Test'],work/'package-test.log')
    digest=sha(pak);roundtrip=work/('roundtrip-'+digest[:16])
    if not roundtrip.exists():command([config['repak'],'unpack',pak,'-o',roundtrip],work/'roundtrip.log')
    unpacked={p.relative_to(roundtrip).as_posix():sha(p) for p in roundtrip.rglob('*') if p.is_file()}
    if hashes!=unpacked:raise ValueError('Independent PAK unpack hashes differ')
    write(release/'VERIFICATION.json',dict(version='Mobile v35 Barca/MU canary',players=players,
          asset_hashes=hashes,pak_sha256=digest,pak_bytes=pak.stat().st_size,
          hardware_accepted=False,unpack_hashes_match=True,runtime_code_changed=False))
    write(release/'PLAYER-STATUS.json',players)
    team_ids=set(config.get('mobile_team_ids',[]))
    outside=[{key:player.get(key) for key in ('base_id','native_player_id','name','status','team_ids')}
             for player in read(config['source_verification'])['players']
             if team_ids & set(player.get('team_ids',[])) and player['base_id'] not in expected]
    write(release/'OUTSIDE-CANDIDATE.json',outside)
    with (release/'OUTSIDE-CANDIDATE.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=['base_id','native_player_id','name','status','team_ids']);writer.writeheader()
        for player in outside:writer.writerow(dict(player,team_ids=';'.join(map(str,player['team_ids']))))
    fields=['base_id','native_player_id','name','status','face_triangles','hair_triangles','triangles','vertices','sections','eye_cleanup']
    with (release/'PLAYER-STATUS.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for player in sorted(players,key=lambda p:p['name']):
            row={key:player[key] for key in fields if key!='eye_cleanup'}
            row['eye_cleanup']=';'.join(sorted({eye['status'] for eye in player['eye_enclosure']['eyes']}))
            writer.writerow(row)
    (release/'INSTALL.txt').write_text(
        'FootballNX Mobile v35 - kandidat uji Barcelona / Manchester United\n\n'
        f'{len(players)} pemain, termasuk cadangan. Kepala maksimal 2.000 segitiga dan dua material.\n'
        'Wajah mempertahankan shading sumber; mata mengikuti kelopak; rambut disederhanakan.\n'
        'PLAYER-STATUS.csv / JSON berisi pemain, hitungan hasil cook, dan status pemeriksaan.\n\n'
        f'{len(outside)} identitas roster berada di luar kandidat ini; lihat OUTSIDE-CANDIDATE.csv.\n'
        'Pasang saat game ditutup:\n'
        '1. Pindahkan semua PAK real face lama (termasuk Lite v34, v24, Barcelona, Yamal, Raphinha)\n'
        '   ke luar folder Paks. Simpan untuk rollback. Gunakan hanya PAK wajah kandidat ini.\n'
        '2. Salin ISI folder update ke SD:/switch/pes21_nx/. Jangan membuat subfolder update baru.\n'
        '3. NRO v33, CPK roster/fisik/warna kulit, dan PAK stadion yang sudah dipakai tetap digunakan.\n\n'
        'Ini paket terbatas Barca/MU; klub lain menggunakan aset kepala tanpa patch.\n'
        'Belum ada konfirmasi FPS dari Switch. Bandingkan dengan tanpa PAK real face memakai tim,\n'
        'starting XI, stadion, kamera, dan quality yang sama. Uji operan bawah-tengah/dekat kamera\n'
        'pada DAY dan NIGHT, lalu periksa close-up mata, bentuk wajah, rambut dan leher.\n'
        'Untuk rollback, keluarkan PAK kandidat dan pulihkan PAK lama. Tidak ada NRO/OBB baru.\n',encoding='utf-8')
    (release/'SHA256SUMS.txt').write_text(digest+'  '+pak.relative_to(release).as_posix()+'\n')
    archive=release/'FootballNX-Mobile-v35-Barca-MU.zip'
    files=[pak]+[release/name for name in ('INSTALL.txt','VERIFICATION.json','PLAYER-STATUS.json','PLAYER-STATUS.csv',
                                         'OUTSIDE-CANDIDATE.json','OUTSIDE-CANDIDATE.csv','SHA256SUMS.txt')]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        for file in files:bundle.write(file,'FootballNX-Mobile-v35/'+file.relative_to(release).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:raise ValueError('Release archive CRC failed')
        import hashlib
        if hashlib.sha256(bundle.read('FootballNX-Mobile-v35/'+pak.relative_to(release).as_posix())).hexdigest()!=digest:
            raise ValueError('PAK bytes changed inside release archive')
    write(release/'ARCHIVE.json',dict(file=archive.name,bytes=archive.stat().st_size,sha256=sha(archive)))
    print(json.dumps(dict(pak=str(pak),archive=str(archive),players=len(players),bytes=pak.stat().st_size,sha256=digest)),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','cook','verify','package','status'])
    parser.add_argument('--config',required=True,type=Path)
    parser.add_argument('--player',action='append',type=int,default=[])
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();config=read(args.config)
    for name in ('work_dir','cache_dir'):
        path=Path(config[name]).resolve()
        if not any(path.is_relative_to(HERE.parent/d) and path!=HERE.parent/d for d in ('local-debug','local-inputs')):
            raise ValueError('Output must be a dedicated ignored directory')
    if not 1<=args.workers<=4:raise ValueError('Workers must be in 1..4')
    if args.command=='prepare':prepare(config,set(args.player),args.workers)
    elif args.command=='cook':
        from realface_batch_release import cook
        cook(config,set(args.player))
    elif args.command=='verify':
        from realface_batch_release import verify
        verify(config,args.workers)
    elif args.command=='package':package(config)
    elif args.command=='status':status(config)


if __name__=='__main__':main()
