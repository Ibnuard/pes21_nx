"""Offline, resumable reduction of identity-verified realface FBX inputs.

Local config extends the realface batch tool configuration with a
source_profiles manifest and an accepted source verification/PAK. No API or
model calls occur. Originals and the active runtime are never overwritten.
Failed geometry or cooked validation remains held, never silently packaged.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import subprocess
import re
import csv

from realface_batch import command, key_of, output_hashes, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_pipeline import sha, identify

HERE = Path(__file__).resolve().parent
LEVELS = [dict(face_skin=1400, eye=192, hair=800, head_cap=2500,skin_error_cm=.65),
          dict(face_skin=1700, eye=256, hair=2200, head_cap=4500,skin_error_cm=.35),
          dict(face_skin=2000, eye=320, hair=4000, head_cap=6500,skin_error_cm=.2),
          dict(face_skin=2400, eye=384, hair=6800, head_cap=10000,skin_error_cm=.12)]
# A complex skin mesh may need more of the total budget than the hair. Retry
# that allocation without increasing the maximum complete-head allowance.
LEVELS += [dict(face_skin=2000,eye=256,hair=1800,head_cap=8000,skin_error_cm=.2),
           dict(face_skin=3000,eye=320,hair=4000,head_cap=10000,skin_error_cm=.12)]
LIMITS = dict(skin=dict(max_cm=.8, p95_cm=.20, lower_neck_max_cm=.3, bounds_max_cm=.8),
              hair=dict(p95_cm=1.25, bounds_max_cm=2., reverse_max_cm=3.),
              eye=dict(max_cm=.12, p95_cm=.06, bounds_max_cm=.12))


def sources(config):
    rows = read(config['source_profiles'])
    state = read(config['identity_state'])
    registry = dict(players=[dict(ef_base_id=p['base_id'], native_player_id=p['native_player_id'],
                                 fingerprint=p['fingerprint'], status=p['status'], canonical_name=p['name'])
                             for p in state['identities'].values() if p.get('status')=='active'])
    coverage = {p['base_id']: p for p in read(config['source_verification'])['players']
                if p['status'] in ('candidate_pending_device', 'preserved_verified')}
    if len(rows) != len(coverage) or len({p['base_id'] for p in rows}) != len(rows):
        raise ValueError('Source profiles must cover each accepted identity exactly once')
    for row in rows:
        owner = identify(row, registry)
        accepted = coverage.get(row['base_id'])
        if not accepted or any(accepted[k] != row[k] for k in ('native_player_id','fingerprint')):
            raise ValueError('Accepted face identity differs: '+str(row['base_id']))
        row['name'] = owner['canonical_name']
    return rows


def prepare_one(config, row):
    profile = read(row['profile'])
    if profile['native_player_id'] != row['native_player_id']:
        raise ValueError('Prepared FBX belongs to a different native slot')
    for name, digest in row['input_hashes'].items():
        if sha(name) != digest: raise ValueError('Pinned face source changed: '+name)
    files = {str(HERE/n):sha(HERE/n) for n in
             ('blender_realface_lite.py','blender_fit_realface.py','blender_export_ue_fbx.py',
              'blender_meshopt.py','meshopt_reduce.mjs')}
    files.update({config[n]:sha(config[n]) for n in ('native_rig','cooked_rig')})
    files.update(row['input_hashes'])
    if config.get('meshoptimizer'):files[config['meshoptimizer']]=sha(config['meshoptimizer'])
    failures = []
    for level, budgets in enumerate(LEVELS):
        key = key_of(dict(files=files, profile=profile, budgets=budgets, limits=LIMITS,
                          base=row['base_id'], fingerprint=row['fingerprint']))
        folder = Path(config['cache_dir'])/'lite-jobs'/(str(row['base_id'])+'-'+key[:16])
        entry = {k:row[k] for k in ('base_id','native_player_id','fingerprint','name')}
        entry.update(folder=str(folder), cache_key=key, quality_level=level, budgets=budgets)
        if valid_prepared_cache(folder, key):
            return dict(entry, status='prepared_cached')
        folder.mkdir(parents=True, exist_ok=True)
        # A failed deterministic attempt is not repeated on a resume. Changing
        # code, inputs or policy produces a different key and a fresh attempt.
        failed = folder/'held.json'
        if failed.is_file():
            failures.append(read(failed)); continue
        job = dict(entry, source_profile=profile, native_rig=config['native_rig'],
                   cooked_rig=config['cooked_rig'], limits=LIMITS,
                   node=config.get('node'),meshoptimizer=config.get('meshoptimizer'))
        write(folder/'job.json', job)
        try:
            command([config['blender'],'--background','--threads','2','--python-exit-code','1',
                     '--python',HERE/'blender_realface_lite.py','--',folder/'job.json'], folder/'prepare.log')
            proof = read(folder/'simplification.json')
            ue = dict(profile, base_id=row['base_id'], native_player_id=row['native_player_id'],
                      fingerprint=row['fingerprint'], face_fbx=str(folder/'face.fbx'),
                      hair_fbx=str(folder/'hair.fbx'), skin_materials=['lite_skin'], eye_material='lite_eye',
                      hair_materials=['lite_hair'] if 'hair' in proof['hair']['roles'] else [],
                      hair_skin_materials=['lite_skin'] if 'skin' in proof['hair']['roles'] else [])
            ue.pop('report', None)
            write(folder/'ue-profile.json', ue)
            # The final package retains the accepted texture/material bytes.
            # These import textures serve only as local cook dependencies.
            write(folder/'recipe.json', dict(eye={}, source=row, geometry_only=True))
            write(folder/'complete.json', dict(cache_key=key, outputs=output_hashes(folder)))
            return dict(entry,status='prepared',triangles=proof['total_triangles'])
        except Exception as error:
            log = (folder/'prepare.log').read_text(errors='replace') if (folder/'prepare.log').exists() else ''
            reason = next((line for line in log.splitlines() if line.startswith(('ValueError:','RuntimeError:'))), str(error))
            failure = dict(level=level,reason=reason);write(failed,failure);failures.append(failure)
    return dict(entry,status='held_geometry',attempts=failures)


def prepare(config, selected, workers):
    rows = sources(config)
    work = Path(config['work_dir']); work.mkdir(parents=True, exist_ok=True)
    path = work/'prepare-report.json'
    saved = {r['base_id']:r for r in read(path)} if path.exists() else {}
    pending = [r for r in rows if not selected or r['base_id'] in selected]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_one,config,row):row for row in pending}
        for number,future in enumerate(as_completed(futures),1):
            result = future.result(); saved[result['base_id']] = result
            write(path,sorted(saved.values(),key=lambda r:r['base_id']))
            print(json.dumps(dict(done=number,total=len(pending),base_id=result['base_id'],
                                  status=result['status'],level=result.get('quality_level'))),flush=True)


def package(config):
    rows = read(Path(config['work_dir'])/'verify-report.json')
    coverage = sources(config)
    if (len(rows)!=len(coverage) or len({r['base_id'] for r in rows})!=len(rows)
            or len({r['native_player_id'] for r in rows})!=len(rows)
            or {r['base_id'] for r in rows} != {r['base_id'] for r in coverage}
            or any(r['status'] not in ('validated','validated_cached') for r in rows)):
        raise ValueError('All accepted players must pass independent cook validation')
    identities={r['base_id']:r for r in coverage}
    for row in rows:
        if any(row.get(field)!=identities[row['base_id']][field] for field in ('native_player_id','fingerprint')):
            raise ValueError('Verified mesh identity differs from the accepted player')
    original = read(config['source_verification'])
    if sha(config['source_pak']) != original['pak_sha256']:
        raise ValueError('Source PAK changed since accepted verification')
    print('PACKAGE_IDENTITY_VERIFIED', len(rows), flush=True)
    work = Path(config['work_dir']); stage = work/'package-stage'
    if not stage.exists():
        command([config['repak'],'unpack',config['source_pak'],'-o',stage],work/'unpack.log')
    prefix = 'PesMobile/Content/Assets/character/RealFace/'
    expected = original['asset_hashes']
    replacements = {}
    replacement_hashes = {}
    dependency_proof=work/'mesh-dependencies.json'
    dependencies=read(dependency_proof) if dependency_proof.exists() else {}
    def verify_meshes(row):
        found, digests, original_dependencies = {}, {}, {}
        cache = Path(row['cooked_folder'])
        stamp = read(cache/'complete.json')
        if stamp['cache_key'] != row['cooked_cache_key']:
            raise ValueError('Cooked provenance changed')
        for part in ('face','hair'):
            for ext in ('.uasset','.uexp'):
                name = str(row['native_player_id'])+'_'+part+ext
                source = cache/'assets'/name
                if sha(source) != stamp['outputs']['assets/'+name]:
                    raise ValueError('Cooked mesh bytes changed')
                if ext=='.uasset':
                    old=stage/(prefix+name)
                    if name not in dependencies:
                        if sha(old)!=expected[prefix+name]:
                            raise ValueError('Cannot establish original mesh dependency proof')
                        original_dependencies[name]=sorted(set(x.decode('ascii') for x in
                            re.findall(rb'/Game/[A-Za-z0-9_/]+',old.read_bytes())))
                    new=set(x.decode('ascii') for x in re.findall(rb'/Game/[A-Za-z0-9_/]+',source.read_bytes()))
                    if new-set(dependencies.get(name, original_dependencies.get(name, []))):
                        raise ValueError('Geometry replacement added an unverified material/skeleton dependency: '+name)
                found[prefix+name] = source
                digests[prefix+name] = stamp['outputs']['assets/'+name]
        return found, digests, original_dependencies
    # Bound independent file I/O; thousands of tiny assets otherwise serialize
    # filesystem latency. Workers return proofs; only this thread merges them.
    with ThreadPoolExecutor(max_workers=4) as pool:
        proofs = list(pool.map(verify_meshes, rows))
    for number, (found, digests, original_dependencies) in enumerate(proofs, 1):
        replacements.update(found); replacement_hashes.update(digests)
        dependencies.update(original_dependencies)
        if number % 100 == 0 or number == len(rows):
            print('PACKAGE_MESHES_VERIFIED', number, len(rows), flush=True)
    write(dependency_proof,dependencies)
    def stage_asset(entry):
        name, digest = entry
        target = stage/name
        if name in replacements:
            shutil.copy2(replacements[name],target)
            digest = replacement_hashes[name]
        actual = sha(target)
        if actual != digest:
            raise ValueError('Staged mesh or unmodified accepted asset changed: '+name)
        return name, actual
    hashes = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for number, (name, digest) in enumerate(pool.map(stage_asset, expected.items()), 1):
            hashes[name] = digest
            if number % 1000 == 0:
                print('PACKAGE_ASSETS_VERIFIED', number, len(expected), flush=True)
    names = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    if names != set(expected): raise ValueError('PAK payload allowlist changed')
    print('PACKAGE_PAYLOAD_VERIFIED', len(hashes), flush=True)
    release = work/'release/update/PesMobile/Content/Paks';release.mkdir(parents=True,exist_ok=True)
    pak = release/'PesMobile-League-Faces-Lite-v34-Android_ETC1_P.pak'
    response = work/'pak-response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n')
    command([config['unrealpak'],pak,'-Create='+str(response),'-compress'],work/'pack.log')
    command([config['unrealpak'],pak,'-Test'],work/'pak-test.log')
    print('PACKAGE_INTEGRITY_VERIFIED', pak.stat().st_size, flush=True)
    unpacked = work/'package-roundtrip'
    roundtrip_stamp=work/'roundtrip-pak.json'
    if unpacked.exists():
        if not roundtrip_stamp.exists() or read(roundtrip_stamp)['sha256']!=sha(pak):
            raise ValueError('Previous roundtrip belongs to another PAK; use a fresh work directory')
    else:
        command([config['repak'],'unpack',pak,'-o',unpacked],work/'roundtrip.log')
        write(roundtrip_stamp,dict(sha256=sha(pak)))
    files = [p for p in unpacked.rglob('*') if p.is_file()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = dict(pool.map(lambda p: (p.relative_to(unpacked).as_posix(),sha(p)), files))
    if actual != hashes: raise ValueError('Independent PAK roundtrip differs')
    verification = dict(original, version='Realface Lite v34',pak_sha256=sha(pak),pak_bytes=pak.stat().st_size,
                        asset_hashes=hashes,source_pak_sha256=original['pak_sha256'],
                        geometry_only_replacement=True,changed_mesh_files=len(replacements),
                        hardware_accepted=False,unpack_hashes_match=True)
    write(work/'release/VERIFICATION.json',verification)
    summarize(config,rows)
    print(json.dumps(dict(players=len(rows),pak=str(pak),sha256=sha(pak))),flush=True)


def summarize(config,rows=None):
    """Emit per-player coverage and final cooked counts for future cheap audits."""
    work=Path(config['work_dir'])
    rows=rows if rows is not None else read(work/'verify-report.json')
    baseline={}
    if config.get('source_metrics_csv'):
        path=Path(config['source_metrics_csv'])
        audit=read(config['source_audit'])
        if (sha(path)!=config['source_metrics_sha256'] or
                audit['sources']['patch']['pak_sha256']!=read(config['source_verification'])['pak_sha256']):
            raise ValueError('Original cooked geometry audit does not match the accepted PAK')
        with path.open(encoding='utf-8-sig',newline='') as stream:
            baseline={int(r['base_id']):r for r in csv.DictReader(stream)}
        if set(baseline)!={r['base_id'] for r in sources(config)}:
            raise ValueError('Original cooked geometry audit coverage differs')
    def summarize_player(row):
        item={k:row[k] for k in ('base_id','native_player_id','name','status')}
        if row['status'] in ('validated','validated_cached'):
            prepared=read(Path(row['folder'])/'simplification.json')
            cooked=read(Path(row['cooked_folder'])/'verification.json')
            item['source_fbx_triangles']=sum(r['before'] for p in ('face','hair') for r in prepared[p]['roles'].values())
            item['lite_triangles']=sum(r['triangles'] for p in cooked['parts'].values() for r in p['components'].values())
            item['lite_vertices']=sum(r['cooked_vertices'] for p in cooked['parts'].values() for r in p['components'].values())
            item['material_sections']=sum(len(p['components']) for p in cooked['parts'].values())
            item['quality_level']=row['quality_level']
            if baseline:
                old=baseline[row['base_id']]
                if int(old['native_player_id'])!=row['native_player_id']:
                    raise ValueError('Original audit native slot differs')
                for field in ('triangles','vertices','sections'):
                    item['original_pak_'+field]=int(old['total_'+field])
        else:item['reason']=row.get('reason','')
        return item
    with ThreadPoolExecutor(max_workers=4) as pool:
        output = list(pool.map(summarize_player, rows))
    release=work/'release';release.mkdir(parents=True,exist_ok=True)
    write(release/'PLAYER-STATUS.json',output)
    with (release/'PLAYER-STATUS.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=['base_id','native_player_id','name','status','original_pak_triangles',
            'source_fbx_triangles','lite_triangles','original_pak_vertices','lite_vertices',
            'original_pak_sections','material_sections','quality_level','reason']);writer.writeheader();writer.writerows(output)
    completed={r['base_id']:r for r in output}
    coverage=[]
    for old in read(config['source_verification'])['players']:
        row={k:old.get(k,'') for k in ('base_id','native_player_id','name','status')}
        row['team_ids']=';'.join(map(str,old.get('team_ids',[])))
        if row['base_id'] in completed:
            row['status']='lite_verified_pending_device' if completed[row['base_id']]['status'] in (
                'validated','validated_cached') else completed[row['base_id']]['status']
            row['lite_triangles']=completed[row['base_id']].get('lite_triangles','')
        coverage.append(row)
    with (release/'COVERAGE-STATUS.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=['base_id','native_player_id','name','team_ids','status','lite_triangles'])
        writer.writeheader();writer.writerows(sorted(coverage,key=lambda r:r['base_id']))
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','cook','verify','package','run'])
    p.add_argument('--config',required=True,type=Path)
    p.add_argument('--player',action='append',type=int,default=[])
    p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();config=read(a.config)
    root=HERE.parent
    for name in ('work_dir','cache_dir'):
        target=Path(config[name]).resolve()
        if not any(target.is_relative_to(root/d) and target!=root/d for d in ('local-inputs','local-debug')):
            raise ValueError('Outputs must stay in dedicated ignored local directories')
    if not 1<=a.workers<=4: p.error('--workers must be 1..4')
    if a.command in ('prepare','run'):prepare(config,set(a.player),a.workers)
    if a.command in ('cook','run'):
        from realface_batch_release import cook
        cook(config,set(a.player))
    if a.command in ('verify','run'):
        from realface_batch_release import verify
        verify(config,a.workers)
    if a.command in ('package','run'):package(config)


if __name__=='__main__':main()
