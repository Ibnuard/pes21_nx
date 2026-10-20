"""Read-only source availability audit; never assigns an unresolved face donor.

Recheck the local archive index and same-BaseId biography separately from the
already pinned conversion cohort. Reports stay in the ignored output tree.
"""
import argparse
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from realface_batch_inventory import read,write,source_index
from realface_league_balanced import local_output
from realface_source_identity import match_base_fingerprint,name_relation
from realface_pipeline import sha


def audit(config):
    work=local_output(config['work_dir'])
    scope=read(work/'league-scope.json')
    identities=read(config['identity_state'])['identities']
    owners={r['base_id']:r for r in identities.values() if r.get('status')=='active'}
    biographies={}
    players,members,archives=source_index(config['cpks'],biographies)
    rows=[]
    for old in scope['unresolved']:
        base=old['base_id'];owner=owners[base]
        if any(owner[k]!=old[k] for k in ('native_player_id','fingerprint')):
            raise ValueError('Unresolved roster ownership changed: '+str(base))
        candidate=players.get(base);bio=biographies.get(base)
        names=sorted(members.get(base,{}))
        required={suffix:any(n.lower().endswith(suffix) for n in names)
                  for suffix in ('/face.fpk','/face_bsm_alp.ftex')}
        evidence=match_base_fingerprint(owner,candidate,bio) if candidate else None
        record=dict(old,source_player=asdict(candidate) if candidate else None,
                    source_biography=bio,source_members=names,required_parts=required,
                    verified_base_fingerprint=evidence,
                    same_numeric_id_is_identity_proof=False,installed=False)
        if candidate and bio:
            record['comparison']=dict(name_relation=name_relation(owner['name'],candidate.name),
                country_match=owner['country']==bio['country'],height_delta=bio['height']-owner['height'],
                age_delta=bio['age']-owner['age'],foot_match=bio['foot']==owner['foot'],
                goalkeeper_class_match=(bio['position']==0)==(owner['position']==0))
        record['audit_status']=('new_verified_source_requires_preparation' if evidence and all(required.values()) else
                                'verified_identity_source_parts_absent' if evidence else
                                'unverified_identity_source_parts_present' if all(required.values()) else
                                'unverified_identity_source_parts_absent')
        rows.append(record)
    report=dict(policy='read_only_unresolved_base_fingerprint_audit_v1',
                scope_sha256=sha(work/'league-scope.json'),
                identity_state_sha256=sha(config['identity_state']),archives=archives,
                counts=dict(Counter(r['audit_status'] for r in rows)),players=rows,
                assignments_changed=False,donor_assets_selected=False)
    write(work/'UNRESOLVED-SOURCE-AUDIT.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    result=audit(read(parser.parse_args().config))
    print(result['counts'])
