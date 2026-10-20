from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_realface_unresolved as audit
from realface_batch_inventory import read,write
from realface_pipeline import sha


@dataclass
class Candidate:
    player_id:int
    name:str
    nationality_code:int=1
    position:int=12


def test_existing_parts_are_not_identity_evidence_and_audit_never_assigns(tmp_path,monkeypatch):
    owner=dict(base_id=10,native_player_id=900,fingerprint='owned',name='First Player',
               status='active',country=1,height=180,age=25,foot=0,position=12)
    identity=tmp_path/'identity.json';write(identity,dict(identities={'10':owner}))
    scope=tmp_path/'league-scope.json';write(scope,dict(unresolved=[dict(owner)]))
    original=(sha(identity),sha(scope))
    bio=dict(country=1,height=180,age=25,foot=0,position=12,row_sha256='source')
    parts={10:{'Asset/model/character/face/real/10/face.fpk':{},
               'Asset/model/character/face/real/10/face_bsm_alp.ftex':{}}}
    def index(paths,bios):
        bios[10]=bio
        return {10:Candidate(10,'Other Player')},parts,[]
    monkeypatch.setattr(audit,'source_index',index)
    monkeypatch.setattr(audit,'local_output',lambda path:Path(path))
    config=dict(work_dir=str(tmp_path),identity_state=str(identity),cpks=[])
    result=audit.audit(config)
    assert result['counts']=={'unverified_identity_source_parts_present':1}
    assert result['players'][0]['verified_base_fingerprint'] is None
    assert not result['donor_assets_selected'] and not result['assignments_changed']
    assert (sha(identity),sha(scope))==original
    parts[10]={}
    def verified_index(paths,bios):
        bios[10]=bio
        return {10:Candidate(10,'First Player')},parts,[]
    monkeypatch.setattr(audit,'source_index',verified_index)
    result=audit.audit(config)
    assert result['counts']=={'verified_identity_source_parts_absent':1}
    assert read(tmp_path/'UNRESOLVED-SOURCE-AUDIT.json')['players'][0]['verified_base_fingerprint']
