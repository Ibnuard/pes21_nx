"""Extend the pinned league cohort with explicitly verified original sources.

Reuses original dense conversions only, never old reduced/rejected heads.
The existing ten documented aliases retain their native ID/fingerprint.
Source manifests are new ignored files; historical manifests stay immutable.
"""
import argparse
from pathlib import Path

from realface_batch import valid_prepared_cache
from realface_batch_inventory import read,write,source_index
from realface_league_balanced import exclusive,local_output,scope_for,unique,assert_owner
from realface_lite import sources
from realface_source_recovery import match_alias
from realface_recovered_sources_mobile import owners_from_prepared
from realface_pipeline import sha

ROOT=Path(__file__).resolve().parents[1]


def source_inventory(config,scope,aliases):
    biographies={}
    players,members,archives=source_index(config['cpks'],biographies)
    identities=read(config['identity_state'])['identities']
    owners={r['base_id']:r for r in identities.values() if r.get('status')=='active'}
    unresolved={r['base_id']:r for r in scope['unresolved']}
    result=[]
    for alias in aliases:
        base=alias['base_id']
        if base not in unresolved:
            continue
        owner=owners[base];assert_owner(owner,unresolved[base])
        p=players.get(base)
        from dataclasses import asdict
        candidate=asdict(p) if p else None
        evidence=match_alias(owner,candidate,biographies.get(base),alias)
        parts=members.get(base,{})
        if not evidence or not all(any(n.lower().endswith(s) for n in parts)
                                  for s in ('/face.fpk','/face_bsm_alp.ftex')):
            raise ValueError('Documented source alias no longer matches: '+str(base))
        result.append(dict(unresolved[base],registry=owner.get('registry',{}),status='source_ready',
                           source_player=candidate,source_members=parts,source_identity_evidence=evidence))
    return dict(players=result,archives=archives)


def dense_sources(config,inventory):
    original=ROOT/'local-inputs/realface-cache-v1/jobs'
    result=[]
    for row in inventory['players']:
        matches=[]
        for folder in original.glob(str(row['base_id'])+'-*'):
            if not (folder/'complete.json').is_file() or not (folder/'ue-profile.json').is_file():
                continue
            profile=read(folder/'ue-profile.json')
            if any(profile.get(k)!=row[k] for k in ('base_id','native_player_id','fingerprint')):
                continue
            stamp=read(folder/'complete.json')
            if valid_prepared_cache(folder,stamp['cache_key']):
                matches.append(dict(row,folder=str(folder),cache_key=stamp['cache_key'],status='prepared_cached'))
        if len(matches)!=1:
            raise ValueError('Expected one immutable original dense conversion: '+str(row['base_id']))
        result.extend(owners_from_prepared(inventory,matches))
    return result


def extend(config_path):
    config_path=Path(config_path).resolve();config=read(config_path)
    work=local_output(config['work_dir']);folder=work/'source-extension'
    complete=folder/'PROMOTED.json'
    with exclusive(work):
        if complete.exists():
            proof=read(complete)
            if any(sha(p)!=digest for p,digest in proof['outputs'].items()):
                raise ValueError('Source extension changed after promotion')
            return proof
        original=folder/'original-config.json'
        if not original.exists():
            # The saved original also permits recovery from an interruption
            # between scope/config publication while the process lock is held.
            write(original,config)
        else:
            config=read(original)
        for path,digest in config['pinned_inputs'].items():
            if sha(path)!=digest:
                raise ValueError('Pinned original input changed')
        old_sources=sources(config)
        old_scope=scope_for(config,unique(old_sources,'original sources'))
        aliases=read(ROOT/'data/realface-source-aliases-v1.json')['aliases']
        inv=source_inventory(config,old_scope,aliases)
        added=dense_sources(config,inv)
        if len(added)!=10:
            raise ValueError('The explicit ten-alias extension must be complete')
        combined=old_sources+added
        unique(combined,'extended sources')
        write(folder/'inventory.local.json',inv)
        profiles=folder/'sources.local.json';write(profiles,combined)
        verification=read(config['source_verification'])
        added_by_id={r['base_id']:r for r in added}
        inv_by_id={r['base_id']:r for r in inv['players']}
        for row in verification['players']:
            if row['base_id'] in added_by_id:
                source=inv_by_id[row['base_id']];assert_owner(row,source)
                row.update(status='source_ready_verified',source_identity_evidence=source['source_identity_evidence'])
        verification['source_extension']=dict(policy='explicit_alias_dense_source_extension_v55',
            original_verification_sha256=sha(config['source_verification']),
            aliases_sha256=sha(ROOT/'data/realface-source-aliases-v1.json'),
            added_base_ids=sorted(added_by_id),source_only_no_new_cooked_acceptance=True)
        verified=folder/'source-verification.json';write(verified,verification)
        new=dict(config,source_profiles=str(profiles),source_verification=str(verified))
        new['pinned_inputs']=dict(config['pinned_inputs'],**{str(p.resolve()):sha(p) for p in
            (profiles,verified,ROOT/'data/realface-source-aliases-v1.json',folder/'inventory.local.json',original)})
        scope=scope_for(new,unique(sources(new),'extended source identities'))
        if scope['roster_count']!=old_scope['roster_count'] or scope['source_count']!=907:
            raise ValueError('Source extension must preserve roster and include exactly 907 originals')
        write(folder/'extended-scope.json',scope);write(folder/'extended-config.json',new)
        write(work/'league-scope.json',scope);write(config_path,new)
        proof=dict(added_base_ids=sorted(added_by_id),source_count=scope['source_count'],
            previous_source_count=old_scope['source_count'],runtime_identity_changed=False,
            outputs={str(p.resolve()):sha(p) for p in (profiles,verified,folder/'inventory.local.json',
                folder/'extended-scope.json',folder/'extended-config.json',original,config_path,work/'league-scope.json')})
        write(complete,proof)
        return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True)
    print(extend(parser.parse_args().config))
