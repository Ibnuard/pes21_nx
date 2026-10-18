"""Serial, identity-preserving facial-hair repair of an audited 6k team trial.

Only heads with at least 20 source triangles touching the forward facial-hair
region are retried. Existing face allocations are retained. Failed repairs
stay held; unchanged validated heads reuse their explicit cooked provenance.
"""
import argparse
import json
from pathlib import Path

import realface_budget_experiment as trial
from realface_batch import valid_prepared_cache
from realface_batch_inventory import read,write
from realface_league_mobile import PreparationProcess
from realface_lite import sources
from realface_pipeline import sha


def facial_hair_count(data):
    p,tri=data['positions'],data['indices']
    if len(p)%3 or len(tri)%3:
        raise ValueError('Invalid native-space hair request')
    marked={i for i in range(len(p)//3) if p[i*3+2]<170. and
            p[i*3+1]>5. and abs(p[i*3])<9.}
    return sum(any(i in marked for i in tri[j:j+3]) for j in range(0,len(tri),3))


def merge_rows(original,repairs,verified):
    owners={r['base_id']:r for r in original}
    if len(owners)!=len(original) or len({r['base_id'] for r in repairs})!=len(repairs):
        raise ValueError('Duplicate head identity')
    replacements={r['base_id']:r for r in repairs}
    proofs={r['base_id']:r for r in verified}
    if not replacements.keys()<=owners.keys():
        raise ValueError('Repair is outside the original cohort')
    result=[]
    for old in original:
        base=old['base_id']
        if base in replacements:
            new=replacements[base]
            if any(new[k]!=old[k] for k in ('native_player_id','fingerprint')):
                raise ValueError('Repair changed player identity')
            result.append(new)
        elif old['status'] in ('prepared','prepared_cached'):
            proof=proofs[base]
            if (proof['status'] not in ('validated','validated_cached') or
                    any(proof[k]!=old[k] for k in ('native_player_id','fingerprint','cache_key'))):
                raise ValueError('Unchanged head lacks matching cooked validation')
            result.append(dict(old,reuse_cooked={k:proof[k] for k in ('cooked_folder','cooked_cache_key')}))
        else:
            result.append(old)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-config',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--repair-cap',type=int,choices=(6000,7000),default=6000)
    p.add_argument('--reuse-prepared-repairs',type=Path)
    a=p.parse_args()
    original_config=read(a.baseline_config)
    origin=Path(original_config['work_dir']).resolve()
    output=a.output.resolve();work=output/str(a.repair_cap)
    if (not output.is_relative_to(trial.ROOT/'local-debug') or output==trial.ROOT/'local-debug'
            or output==origin.parent or original_config.get('experimental_head_cap')!=6000
            or original_config.get('experimental_teams')!=[100,108]):
        raise ValueError('Use a separate ignored Barca/MU 6k repair output')
    original=read(origin/'prepare-report.json')
    verified=read(origin/'verify-report.json')
    selected=[]
    for row in original:
        if row['status'] not in ('prepared','prepared_cached'):
            continue
        folder=Path(row['folder'])
        if not valid_prepared_cache(folder,row['cache_key']):
            raise ValueError('Baseline preparation changed')
        request=folder/'lite_hair-meshopt.json'
        count=facial_hair_count(read(request)) if request.exists() else 0
        if count>=20:
            selected.append((row,count))
    config=dict(original_config,work_dir=str(work),cache_dir=str(output/'cache'),
                experimental_hair_policy='face_locked_cards',experimental_head_cap=a.repair_cap)
    write(work/'config.local.json',config)
    write(output/'team-scope.json',read(origin.parent/'team-scope.json'))
    catalog={r['base_id']:r for r in sources(config)}
    worker=PreparationProcess(config['blender'],trial.HERE/'blender_realface_budget_worker.py')
    allocation=trial.allocation
    previous={r['base_id']:r for r in read(a.reuse_prepared_repairs)} if a.reuse_prepared_repairs else {}
    results=[]
    try:
        for old,count in selected:
            prior=previous.get(old['base_id'])
            if (prior and prior['status'] in ('prepared','prepared_cached') and
                    prior.get('facial_hair_repair',{}).get('source_cache_key')==old['cache_key'] and
                    all(prior[k]==old[k] for k in ('native_player_id','fingerprint')) and
                    prior['budgets'].get('hair_face_lock') and prior['budgets'].get('hair_error_cm')==.45 and
                    prior['budgets'].get('hair_uv_weight')==.5 and
                    all(prior['budgets'].get(k)==v for k,v in old['budgets'].items() if k!='head_cap') and
                    prior['budgets']['head_cap']<=a.repair_cap and
                    valid_prepared_cache(Path(prior['folder']),prior['cache_key'])):
                trial.validate_preparation(read(Path(prior['folder'])/'simplification.json'),
                    read(Path(prior['folder'])/'hair-projection.json'),a.repair_cap)
                result=dict(prior,status='prepared_cached',reused_bounded_repair=True)
            else:
                trial.allocation=lambda cap,budget=old['budgets']:dict(budget,head_cap=a.repair_cap)
                result=trial.prepare_one(config,catalog[old['base_id']],worker)
            result['facial_hair_repair']=dict(source_cache_key=old['cache_key'],source_region_triangles=count)
            results.append(result)
            write(work/'hair-repair-report.json',results)
            print(json.dumps(dict(completed=len(results),total=len(selected),base_id=result['base_id'],
                status=result['status'],triangles=result.get('triangles'),reason=result.get('reason'))),flush=True)
    finally:
        trial.allocation=allocation;worker.close()
    merged=merge_rows(original,results,verified)
    write(work/'prepare-report.json',merged)
    write(work/'repair-provenance.json',dict(
        baseline_prepare_sha256=sha(origin/'prepare-report.json'),
        baseline_verify_sha256=sha(origin/'verify-report.json'),
        repaired=[r['base_id'] for r in results],source_region_minimum_triangles=20,
        maximum_complete_head_triangles=a.repair_cap,
        held_repairs_use_native_fallback=True,hardware_accepted=False))
    print(json.dumps(dict(prepared=sum(r['status'] in ('prepared','prepared_cached') for r in merged),
        held=sum(r['status']=='held_geometry' for r in merged))),flush=True)


if __name__=='__main__':main()
