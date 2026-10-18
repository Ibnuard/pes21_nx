"""Expand the v37 mobile policy to every identity-verified league source.

Persistent, bounded Blender workers amortize startup. Each deterministic
attempt and failure is fingerprinted; reruns reuse verified work. No source
head or active installation is overwritten and no heavy fallback is allowed.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import threading
import uuid

from realface_batch import key_of, output_hashes, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_lite import LIMITS, sources
from realface_mobile import CODE, PROFILE_POLICY, cooked_counts
from realface_pipeline import sha

HERE = Path(__file__).resolve().parent
RECIPE_CODE = CODE+('realface_surface_quality.py', 'realface_hair_envelope.py',
                    'blender_realface_league_worker.py', 'realface_fast_raster.py', 'realface_raster.c')


def allocations():
    result = []
    # Spend most geometry on the face. Try joined hair first, bounded closing
    # second; difficult existing solid/braided shapes have explicit fallbacks.
    for skin, eye, hair in ((1600,128,260), (1500,128,360), (1700,96,190),
                            (1500,96,380), (1750,128,110)):
        for solid in (True, False):
            result.append(dict(face_skin=skin, eye=eye, hair=hair, hair_mode='shell', solid_scalp=solid))
    for skin, eye, hair, mode in ((1500,128,360,'cards'), (1600,128,260,'cards'),
                                 (1300,128,550,'closed'), (1200,128,650,'closed'),
                                 (1200,128,650,'braids')):
        result.append(dict(face_skin=skin, eye=eye, hair=hair, hair_mode=mode))
    for row in result:
        row.update(head_cap=2000, skin_error_cm=.45, eye_error_cm=.06, eye_uv_weight=.1,
                   skin_uv_weight=10., skin_normal_weight=.1, skin_feature_policy=True)
    return result


def recipe_code(budget):
    names = RECIPE_CODE+(('blender_realface_braids.py',) if budget.get('hair_mode')=='braids' else ())
    if budget.get('eye_recovery'):
        names+=('blender_realface_eye_recovery.py','blender_realface_league_recovery_worker.py')
    if budget.get('normal_export_recovery'):
        names+=('blender_realface_normal_export.py','blender_realface_normal_worker.py')
    if budget.get('league_recovery'):
        names+=('blender_realface_league_recovery_worker.py',)
    if budget.get('face_detail'):
        names+=('blender_realface_scalp_detail_worker.py','blender_realface_source_quality.py')
    if budget.get('source_eye'):
        names+=('blender_realface_source_quality.py','blender_realface_source_worker.py',
                'blender_realface_eye_visibility.py',
                'blender_realface_eye_aperture_recovery.py',
                'blender_realface_hair_clearance.py','blender_realface_hair_rebake.py',
                'blender_realface_face_rebake.py')
    if budget.get('source_eye_policy')=='original_lod':
        names+=('blender_realface_eye_lod_worker.py',)
    if budget.get('source_eye_policy')=='scalp_original_lod':
        names+=('blender_realface_scalp_eye_lod_worker.py',)
    if budget.get('native_seam_alias'):
        names+=('realface_seam_alias.py','blender_realface_seam_worker.py')
    if budget.get('skin_marker_cleanup'):
        names+=('realface_skin_markers.py','blender_realface_marker_worker.py')
    if budget.get('hair_mode')=='alpha_volume':
        names+=('blender_realface_hair_volume.py','blender_realface_volume_worker.py')
    return {name:sha(HERE/name) for name in names}


class PreparationProcess:
    def __init__(self, blender, script=None):
        self.blender, self.process, self.jobs = blender, None, 0
        self.script=script or HERE/'blender_realface_league_worker.py'

    def __call__(self, profile, log):
        from blender_realface_league_worker import PREFIX
        if self.process is None or self.process.poll() is not None or self.jobs >= 24:
            self.close()
            self.process = subprocess.Popen([self.blender, '--background', '--threads', '2',
                '--python-exit-code','1','--python',str(self.script)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding='utf-8',errors='replace',bufsize=1)
            self.jobs = 0
        token = uuid.uuid4().hex
        self.process.stdin.write(json.dumps(dict(token=token,profile=str(profile)))+'\n')
        self.process.stdin.flush(); self.jobs += 1
        with Path(log).open('w',encoding='utf-8') as stream:
            for line in self.process.stdout:
                stream.write(line)
                if line.startswith(PREFIX):
                    result = json.loads(line[len(PREFIX):])
                    if result['token'] != token: raise ValueError('Mismatched preparation response')
                    if not result['ok']: raise ValueError(result['reason'])
                    return
        raise RuntimeError('Blender exited without preparation completion')

    def close(self):
        process, self.process = self.process, None
        if process is None: return
        try:
            if process.poll() is None:
                process.stdin.close()
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate(); process.wait(timeout=10)
        finally:
            if process.stdin and not process.stdin.closed: process.stdin.close()
            if process.stdout: process.stdout.close()


def inherited(config, expected):
    """Pin the accepted v37 release, then reuse only its actual verified heads."""
    report = read(config['inherit_verification'])
    if sha(config['inherit_pak']) != report['pak_sha256']:
        raise ValueError('Inherited v37 PAK changed')
    rows = {r['base_id']:r for r in read(config['inherit_identity_report'])}
    rows.update({r['base_id']:r for r in read(config['inherit_refined_report'])})
    if set(rows) != {p['base_id'] for p in report['players']}:
        raise ValueError('Inherited identity coverage differs')
    accepted = {p['base_id']:p for p in report['players']}
    result = {}
    for base,row in rows.items():
        owner = expected[base]
        if any(row[k] != owner[k] for k in ('native_player_id','fingerprint')):
            raise ValueError('Inherited owner differs')
        if (row['status'] not in ('validated','validated_cached') or
                not valid_cache(Path(row['cooked_folder']),row['cooked_cache_key']) or
                not valid_prepared_cache(Path(row['folder']),row['cache_key'])):
            raise ValueError('Inherited verified cache changed')
        counts = cooked_counts(read(Path(row['cooked_folder'])/'verification.json'))
        if counts['triangles'] != accepted[base]['triangles']:
            raise ValueError('Inherited cooked head differs from accepted v37')
        # Keep the old verified engine key explicitly, rather than pretending
        # an accepted historical recipe was generated by current code.
        previous = {k:row[k] for k in ('cooked_folder','cooked_cache_key')}
        result[base] = dict(row, status='prepared_cached', reuse_cooked=previous,
            triangles=counts['triangles'], inherited_release_sha256=report['pak_sha256'])
    return result


def prepare_one(config, row, worker, previous=None):
    profile = read(row['profile'])
    if profile['native_player_id'] != row['native_player_id'] or profile.get('hair_skin_materials'):
        return dict(row,status='held_source_layout',quality_level=-1,reason='Skin in source hair requires repartition')
    for path,digest in row['input_hashes'].items():
        if sha(path)!=digest: raise ValueError('Pinned original source changed: '+path)
    limits = dict(LIMITS,hair={})
    tool_hashes = {k:sha(config[k]) for k in ('native_rig','cooked_rig','meshoptimizer')}
    if config.get('fast_raster'): tool_hashes['fast_raster']=sha(config['fast_raster'])
    available = list(config.get('allocation_overrides',{}).get(str(row['base_id']),allocations()))
    if not available:raise ValueError('Player has no permitted triangle allocation')
    budgets = available[:]
    if previous and previous.get('status') in ('prepared','prepared_cached'):
        old = previous['budgets']
        if old in budgets: budgets.remove(old); budgets.insert(0,old)
    attempts = []
    face_failures = {}
    eye_failures = {}
    for budget in budgets:
        code = recipe_code(budget)
        key = key_of(dict(source=row['input_hashes'],owner={k:row[k] for k in
            ('base_id','native_player_id','fingerprint')},code=code,tools=tool_hashes,
            profile=profile,policy=PROFILE_POLICY,budgets=budget,limits=limits))
        folder = Path(config['cache_dir'])/'league-jobs'/(str(row['base_id'])+'-'+key[:16])
        entry = {k:row[k] for k in ('base_id','native_player_id','fingerprint','name')}
        entry.update(folder=str(folder),cache_key=key,budgets=budget,quality_level=available.index(budget),
                     recipe_source_sha256=code)
        if valid_prepared_cache(folder,key):
            return dict(entry,status='prepared_cached',triangles=read(folder/'simplification.json')['total_triangles'])
        if (folder/'held.json').exists():
            failure=read(folder/'held.json');attempts.append(failure)
            continue
        face_key=key_of({k:v for k,v in budget.items() if k not in ('hair','hair_mode','solid_scalp')})
        eye_policy=(bool(budget.get('eye_recovery')),bool(budget.get('source_eye')),
                    budget.get('source_eye_policy'),budget['eye'] if budget.get('source_eye') else None)
        if eye_policy in eye_failures:
            failure=dict(level=entry['quality_level'],reason=eye_failures[eye_policy],identical_eye_attempt=True)
            write(folder/'held.json',failure);attempts.append(failure)
            continue
        if face_key in face_failures:
            failure=dict(level=entry['quality_level'],reason=face_failures[face_key],identical_face_attempt=True)
            write(folder/'held.json',failure);attempts.append(failure)
            continue
        folder.mkdir(parents=True,exist_ok=True)
        job = dict(entry,source_profile=profile,native_rig=config['native_rig'],cooked_rig=config['cooked_rig'],
                   limits=limits,node=config['node'],meshoptimizer=config['meshoptimizer'],mobile_v35=True,
                   fast_raster=config.get('fast_raster'))
        write(folder/'job.json',job)
        try:
            worker(folder/'job.json',folder/'prepare.log')
            if recipe_code(budget)!=code:
                raise ValueError('Geometry code changed while Blender was running; retry with a fresh worker')
            proof = read(folder/'simplification.json')
            if not 0<proof['total_triangles']<=2000: raise ValueError('Strict complete head cap exceeded')
            projection=read(folder/'hair-projection.json')
            if projection['method']['mode']=='visible_cards' and projection['missing_coverage_max']>.12:
                raise ValueError('Card gaps require joined hair')
            ue = dict(profile,face_fbx=str(folder/'face.fbx'),hair_fbx=str(folder/'hair.fbx'),
                      face_texture=str(folder/'opaque-atlas.png'),**PROFILE_POLICY)
            if budget.get('source_eye') or budget.get('face_detail'):ue['face_texture_size']=256
            if (folder/'hair-shell.png').exists(): ue['hair_texture']=str(folder/'hair-shell.png')
            ue.pop('report',None);write(folder/'ue-profile.json',ue)
            write(folder/'recipe.json',dict(eye={},source=row,mobile_v35=True,league_v38=True))
            write(folder/'complete.json',dict(cache_key=key,outputs=output_hashes(folder)))
            return dict(entry,status='prepared',triangles=proof['total_triangles'])
        except Exception as error:
            failure = dict(level=entry['quality_level'],reason=str(error))
            write(folder/'held.json',failure);attempts.append(failure)
            if str(error).startswith(('Surface quality held face/','Visible face UV','Cannot locate',
                                      'Face exceeds complete head cap','Skin normal transfer',
                                      'Cannot transfer a valid source skin normal')):
                face_failures[face_key]=str(error)
            print(json.dumps(dict(attempt_held=row['base_id'],level=entry['quality_level'],reason=str(error)[:140])),flush=True)
            if str(error).startswith(('Aperture eye','Aperture recovery','Eye shape','Eye cleanup','Pupil lies','Recovered pupil',
                                      'Visible source eye exceeds','Source eye exceeds')):
                eye_failures[eye_policy]=str(error)
    return dict(entry,status='held_geometry',attempts=attempts)


def prepare(config, selected, workers):
    work = Path(config['work_dir']);expected={r['base_id']:r for r in sources(config)}
    write(work/'scope.json',dict(target=len(expected),categories=config['categories'],
        source_verification_sha256=sha(config['source_verification']),source_profiles_sha256=sha(config['source_profiles'])))
    path=work/'prepare-report.json';saved={r['base_id']:r for r in read(path)} if path.exists() else {}
    saved.update(inherited(config,expected));write(path,sorted(saved.values(),key=lambda r:r['base_id']))
    rows=[r for r in expected.values() if (not selected or r['base_id'] in selected) and not saved.get(r['base_id'],{}).get('reuse_cooked')]
    run_id=uuid.uuid4().hex
    write(work/'prepare-running.json',dict(run_id=run_id,selected_base_ids=[r['base_id'] for r in rows]))
    print(json.dumps(dict(inherited=51,pending=len(rows),target=len(expected))),flush=True)
    local=threading.local();processes=[];lock=threading.Lock()
    def one(row):
        if not hasattr(local,'worker'):
            local.worker=PreparationProcess(config['blender'])
            with lock: processes.append(local.worker)
        return prepare_one(config,row,local.worker,saved.get(row['base_id']))
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for n,future in enumerate(as_completed([pool.submit(one,r) for r in rows]),1):
                row=future.result();saved[row['base_id']]=row
                write(path,sorted(saved.values(),key=lambda r:r['base_id']))
                print(json.dumps(dict(done=n,total=len(rows),base_id=row['base_id'],name=row['name'],
                    status=row['status'],triangles=row.get('triangles'),level=row['quality_level'])),flush=True)
    finally:
        for process in processes: process.close()
    write(work/'prepare-complete.json',dict(run_id=run_id,processed=len(rows),
        counts=dict(Counter(saved[r['base_id']]['status'] for r in rows))))
    return saved


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','cook','verify','status','package'))
    parser.add_argument('--config',required=True)
    parser.add_argument('--player',action='append',type=int,default=[])
    parser.add_argument('--workers',type=int,default=4,choices=range(1,5))
    args=parser.parse_args();config=read(args.config)
    for name in ('work_dir','cache_dir'):
        path=Path(config[name]).resolve()
        if not any(path.is_relative_to(HERE.parent/d) and path!=HERE.parent/d for d in ('local-debug','local-inputs')):
            raise ValueError('Dedicated ignored output directory required')
    if args.phase=='prepare': prepare(config,set(args.player),args.workers)
    elif args.phase=='cook':
        from realface_batch_release import cook
        cook(config,set(args.player))
    elif args.phase=='verify':
        from realface_batch_release import verify
        verify(config,args.workers)
    elif args.phase=='status':
        for stage in ('prepare','cook','verify'):
            p=Path(config['work_dir'])/(stage+'-report.json')
            if p.exists(): print(stage,dict(Counter(r['status'] for r in read(p))))
    else:
        from realface_league_mobile_release import package
        package(config)


if __name__=='__main__': main()
