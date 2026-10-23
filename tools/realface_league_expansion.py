"""Initialize a budget-only league extension from completed dense checkpoints.

Old independently cooked heads are retained. New dense inputs require separate
identity proof and still undergo budget reduction, engine cook and validation.
No previews, API calls, installation or visual acceptance occur here.
"""
import argparse
from collections import Counter
from pathlib import Path

from realface_batch import valid_prepared_cache, key_of
from realface_batch_inventory import read, write
from realface_pipeline import sha
from realface_dense_source_proof import POLICY as DENSE_POLICY, validate,identity_evidence
import realface_league_balanced as league
from realface_lite import sources


def initialize(dense_config, accepted_config, output):
    dense_config,accepted_config=Path(dense_config).resolve(),Path(accepted_config).resolve()
    dense,old=read(dense_config),read(accepted_config)
    dense_work=Path(dense['work_dir'])
    status=read(dense_work.parent/'DENSE-STAGE-STATUS.json')
    if status.get('state')!='completed':
        raise ValueError('Wait for the owned dense stage to complete')
    output=league.local_output(output)
    if (output/'config.local.json').exists():
        raise ValueError('Expansion config already exists; resume it')
    inventory_path=dense_work/'inventory.local.json'
    inventory=read(inventory_path)
    inventory_sha=sha(inventory_path)
    admission_config=dict(dense,source_preparation_policy=DENSE_POLICY,dense_inventory=str(inventory_path))
    supplement=dense_work.parent/'WEAK-SOURCE-BIOGRAPHY-AUDIT.json'
    if supplement.is_file():admission_config['source_identity_supplement']=str(supplement)
    prepared=league.unique(read(dense_work/'prepare-report.json'),'dense preparations')
    expected={p['base_id'] for p in inventory['players'] if p['status']=='source_ready'}
    if set(prepared)!=expected:
        raise ValueError('Dense stage has not checkpointed every selected source')
    old_work=Path(old['work_dir'])
    old_ready=league.unique(read(old_work/'verify-report.json'),'retained verification')
    if any(p['status'] not in league.VERIFIED for p in old_ready.values()):
        raise ValueError('Retained cohort must be independently cooked/validated')
    profiles=league.unique(read(old['source_profiles']),'retained profiles')
    original=read(old['source_verification'])
    owners=league.unique(original['players'],'retained roster')
    holds=[]
    for source in inventory['players']:
        base=source.get('base_id')
        if not base or not source.get('fingerprint'):
            holds.append(dict(native_player_id=source['native_player_id'],name=source['name'],reason='native identity unavailable'))
            continue
        if base in owners:
            league.assert_owner(source,owners[base])
            owners[base]['team_ids']=sorted(set(owners[base]['team_ids'])|set(source['team_ids']))
        else:
            owners[base]={k:source[k] for k in ('base_id','native_player_id','fingerprint','name','team_ids')}
            owners[base]['status']='source_hold'
        if base in profiles:
            continue
        row=prepared.get(base)
        reason=None
        evidence={}
        if source['status']!='source_ready': reason=source['status']
        else:
            try:evidence=identity_evidence(admission_config,source)
            except ValueError as error:reason=str(error)
        if not reason and row['status'] not in league.READY:reason=row.get('reason',row['status'])
        if reason:
            holds.append(dict(base_id=base,native_player_id=source['native_player_id'],name=source['name'],
                source_status=source['status'],reason=reason))
            continue
        league.assert_owner(dict(row,fingerprint=source['fingerprint']),source)
        folder=Path(row['folder']);profile=folder/'ue-profile.json'
        if not valid_prepared_cache(folder,row['cache_key']):
            raise ValueError('Dense cache changed: '+str(base))
        data=read(profile)
        paths=[str(profile)]+[data[k] for k in
            ('face_fbx','hair_fbx','face_texture','hair_texture','native_eye_texture')]
        candidate=dict(base_id=base,native_player_id=source['native_player_id'],fingerprint=source['fingerprint'],
            name=source['name'],profile=str(profile),input_hashes={p:sha(p) for p in paths})
        owner=owners[base]
        owner.update(status='dense_source_verified',source_identity_evidence=evidence,
            dense_source=dict(inventory_sha256=inventory_sha,inventory_row_key=key_of(source),
                folder=str(folder),cache_key=row['cache_key']))
        validate(admission_config,candidate,owner,inventory,inventory_sha)
        profiles[base]=candidate
    output.mkdir(parents=True,exist_ok=True)
    profile_path=output/'sources.local.json';proof_path=output/'source-verification.json'
    write(profile_path,sorted(profiles.values(),key=lambda p:p['base_id']))
    write(proof_path,dict(original,players=sorted(owners.values(),key=lambda p:p['base_id']),
        expansion=dict(policy=DENSE_POLICY,dense_inventory=str(inventory_path),
            note='Dense admission is not cook, visual or device acceptance')))
    config=dict(dense,work_dir=str(output),cache_dir=str(output/'cache'),
        source_profiles=str(profile_path),source_verification=str(proof_path),
        source_preparation_policy=DENSE_POLICY,dense_inventory=str(inventory_path),
        accepted_work=str(old_work),accepted_head_count=len(old_ready),
        categories=list(dict.fromkeys(list(old.get('categories',league.CATEGORIES))+list(dense['categories']))),
        team_ids=sorted(set(old.get('team_ids',[]))|set(dense.get('team_ids',[]))),
        policy=league.POLICY,release_label='v71-expanded-budget',release_criterion='budget-priority-v1')
    if supplement.is_file():config['source_identity_supplement']=str(supplement)
    pinned=[dense_config,accepted_config,inventory_path,dense_work/'prepare-report.json',profile_path,proof_path,
        old_work/'prepare-report.json',old_work/'verify-report.json',Path(config['identity_state']),
        Path(config['catalog']),Path(config['selector'])]
    if supplement.is_file():pinned.append(supplement)
    config['pinned_inputs']={str(p):sha(p) for p in pinned}
    # This resolves active identities and separately checks every new dense binding.
    catalogue=league.unique(sources(config),'expanded sources')
    scope=league.scope_for(config,catalogue)
    write(output/'config.local.json',config)
    write(output/'league-scope.json',scope)
    write(output/'verify-report.json',sorted(old_ready.values(),key=lambda p:p['base_id']))
    write(output/'SOURCE-HOLDS.json',dict(players=holds,counts=dict(Counter(p['reason'] for p in holds))))
    report=dict(state='ready_for_budget_reduction',retained_cooked=len(old_ready),new_dense_sources=len(catalogue)-len(old_ready),
        source_holds=len(holds),teams=len(scope['teams']),sources=len(catalogue),
        normal_target=[4500,5000],exception_ceiling=7000,cosmetic_review_blocks_release=False,
        final_budget_acceptance=False,installed=False)
    write(output/'RUN-STATUS.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dense-config',type=Path,required=True)
    parser.add_argument('--accepted-config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(initialize(args.dense_config,args.accepted_config,args.output))
