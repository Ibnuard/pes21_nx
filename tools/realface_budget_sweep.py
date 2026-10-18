"""Serial 5k/4.5k team trials, retaining each accepted head's hair policy.

Only the selected, previously verified Barca/MU cohort is processed. Allocate
3k, 2.8k or 2.6k skin triangles, keeping eye/neck/UV/hair acceptance gates.
Reused heads and deterministic holds retain their provenance. No install.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import realface_budget_experiment as trial
from realface_batch import valid_prepared_cache,valid_cache
from realface_batch_inventory import read,write
from realface_league_mobile import PreparationProcess
from realface_lite import sources
from realface_pipeline import sha


def distribution(cap,skin,locked):
    if cap not in (4500,5000) or skin not in (3000,2800,2600):
        raise ValueError('Only bounded 4.5k/5k distributions are permitted')
    return dict(face_skin=skin,hair=cap-skin-276,hair_face_lock=bool(locked))


def retryable(row):
    return row['status']=='held_geometry' and row.get('reason','').startswith((
        'Experimental complete head cap exceeded:', 'Hair silhouette held',
        'Card gaps require', 'Complete head exceeds the explicit'))


def retain_accepted_holds(baseline_config,output,cap):
    """Keep cohort equality when a new reduction cannot pass unchanged gates.

    These are explicitly retained original heads, never a claimed 5k success.
    The packager must verify each old cache/identity/count against the pinned
    baseline report. The unreduced attempts remain separately inspectable.
    """
    baseline_config,output=Path(baseline_config).resolve(),Path(output).resolve()
    if cap not in (4500,5000) or not output.is_relative_to(trial.ROOT/'local-debug'):
        raise ValueError('Use a dedicated bounded trial output')
    baseline=read(baseline_config);origin=Path(baseline['work_dir']).resolve()
    work=output/str(cap);config=read(work/'config.local.json')
    scope=read(output/'team-scope.json')
    rows=read(work/'prepare-report.json')
    if ({r['base_id'] for r in rows}!=set(scope['selected_base_ids']) or
            baseline.get('experimental_teams')!=[100,108] or output==origin.parent):
        raise ValueError('Complete independent team preparation required')
    original={r['base_id']:r for r in read(origin/'prepare-report.json')}
    proof_path=origin/'verify-report.json';proofs={r['base_id']:r for r in read(proof_path)}
    retained=[];result=[]
    reduction_report=work/'reduction-report.json'
    if not reduction_report.exists():write(reduction_report,rows)
    for row in rows:
        old=original[row['base_id']]
        if row['status']=='held_geometry' and old['status'] in ('prepared','prepared_cached'):
            proof=proofs[old['base_id']]
            if (proof['status'] not in ('validated','validated_cached') or
                    any(proof[k]!=old[k] for k in ('native_player_id','fingerprint','cache_key')) or
                    not valid_prepared_cache(Path(old['folder']),old['cache_key']) or
                    not valid_cache(Path(proof['cooked_folder']),proof['cooked_cache_key'])):
                raise ValueError('Cannot retain unverified original: '+str(old['base_id']))
            retained.append(dict(base_id=row['base_id'],name=row['name'],
                                 triangles=old['triangles'],reason=row['reason']))
            row=dict(old,reuse_cooked={k:proof[k] for k in ('cooked_folder','cooked_cache_key')},
                     accepted_baseline=dict(verification=str(proof_path),verification_sha256=sha(proof_path),
                                            triangles=old['triangles'],reason=retained[-1]['reason']))
        elif row.get('accepted_baseline'):
            retained.append(dict(base_id=row['base_id'],name=row['name'],
                                 triangles=row['triangles'],reason=row['accepted_baseline']['reason']))
        result.append(row)
    config['experimental_release_label']=f'v46-balanced-{cap}'
    write(work/'config.local.json',config)
    write(work/'prepare-report.json',result)
    write(work/'retained-originals.json',retained)
    print(json.dumps(dict(target_cap=cap,retained=retained,cohort_unchanged=True)),flush=True)


def run(baseline_config,output,cap,selected=()):
    baseline_config,output=Path(baseline_config).resolve(),Path(output).resolve()
    if not output.is_relative_to(trial.ROOT/'local-debug'):
        raise ValueError('Use ignored local-debug output')
    original_config=read(baseline_config);origin=Path(original_config['work_dir']).resolve()
    if original_config.get('experimental_teams')!=[100,108] or output==origin.parent:
        raise ValueError('Use a separate Barca/MU trial output')
    old_rows=read(origin/'prepare-report.json')
    verified={r['base_id']:r for r in read(origin/'verify-report.json')}
    scope=read(origin.parent/'team-scope.json')
    config=trial.isolated_config(original_config,output,cap)
    # The v41 baseline mixed ordinary scalp cards and protected facial hair.
    # Applying facial-hair locks globally locks Yamal's scalp unnecessarily.
    config['experimental_hair_policy']='cards'
    config['experimental_allocations']={}
    write(output/'team-scope.json',scope)
    work=Path(config['work_dir']);write(work/'config.local.json',config)
    catalog={r['base_id']:r for r in sources(config)}
    selected=set(selected or ()) or set(scope['selected_base_ids'])
    if not selected<=set(scope['selected_base_ids']):
        raise ValueError('Player outside the pinned team scope')
    rows,attempts=[],[]
    report_path=work/'prepare-report.json'
    if report_path.exists():rows=read(report_path)
    saved={r['base_id']:r for r in rows}
    worker=PreparationProcess(config['blender'],trial.HERE/'blender_realface_budget_worker.py')
    write(output/'RUN-STATUS.json',dict(phase='prepare',cap=cap,state='running',workers=1,
          baseline_config_sha256=sha(baseline_config),installed=False,hardware_accepted=False))
    try:
        for old in old_rows:
            base=old['base_id']
            if base not in selected:continue
            if old['status'] not in ('prepared','prepared_cached'):
                saved[base]=old
                continue
            proof=verified[base]
            if (proof['status'] not in ('validated','validated_cached') or
                    any(proof[k]!=old[k] for k in ('native_player_id','fingerprint','cache_key')) or
                    not valid_prepared_cache(Path(old['folder']),old['cache_key']) or
                    not valid_cache(Path(proof['cooked_folder']),proof['cooked_cache_key'])):
                raise ValueError('Pinned accepted cache changed: '+str(base))
            if old['triangles']<=cap:
                saved[base]=dict(old,reuse_cooked={k:proof[k] for k in ('cooked_folder','cooked_cache_key')},
                                 inherited_baseline_sha256=sha(origin/'verify-report.json'))
            else:
                tries=[]
                for skin in (3000,2800,2600):
                    budget=distribution(cap,skin,old['budgets'].get('hair_face_lock',False))
                    config['experimental_allocations'][str(base)]=budget
                    new=trial.prepare_one(config,catalog[base],worker)
                    tries.append({k:new.get(k) for k in ('folder','cache_key','budgets','status','reason','triangles')})
                    print(json.dumps(dict(cap=cap,base_id=base,skin=skin,status=new['status'],
                                          triangles=new.get('triangles'),reason=new.get('reason'))),flush=True)
                    if new['status'] in ('prepared','prepared_cached') or not retryable(new):break
                new['budget_sweep']=dict(source_cache_key=old['cache_key'],attempts=tries)
                saved[base]=new;attempts.append(dict(base_id=base,attempts=tries))
            write(report_path,sorted(saved.values(),key=lambda r:r['base_id']))
            write(work/'config.local.json',config)
            write(work/'sweep-attempts.json',attempts)
    finally:
        worker.close()
    report=dict(cap=cap,selected=len(selected),processed=len(saved),
                statuses=dict(Counter(r['status'] for r in saved.values())),
                phase='prepare',state='prepared_pending_cook',workers=1,
                installed=False,hardware_accepted=False)
    write(output/'RUN-STATUS.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-config',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--cap',required=True,type=int,choices=(4500,5000))
    p.add_argument('--player',type=int,action='append')
    p.add_argument('--retain-accepted-holds',action='store_true')
    a=p.parse_args()
    if a.retain_accepted_holds:retain_accepted_holds(a.baseline_config,a.output,a.cap)
    else:run(a.baseline_config,a.output,a.cap,a.player)
