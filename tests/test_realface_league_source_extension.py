from dataclasses import dataclass
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_league_source_extension as extension
from realface_batch_inventory import write


@dataclass
class Source:
    player_id:int
    name:str


def test_extension_requires_current_owner_documented_alias_and_real_parts(tmp_path,monkeypatch):
    owner=dict(base_id=10,native_player_id=900,fingerprint='current',name='Ivan Player',
               status='active',country=1,height=180,age=25,foot=0,position=0,registry={})
    path=tmp_path/'identity.json';write(path,dict(identities={'ef:10':owner}))
    bio=dict(country=1,height=180,age=25,foot=0,position=0,row_sha256='original-row')
    source=Source(10,'Pichu Player')
    parts={10:{'Asset/model/character/face/real/10/face.fpk':{},
               'Asset/model/character/face/real/10/face_bsm_alp.ftex':{}}}
    def index(paths,bios):
        bios[10]=bio
        return {10:source},parts,[]
    monkeypatch.setattr(extension,'source_index',index)
    alias=dict(base_id=10,names=['Ivan Player','Pichu Player'],note='Documented nickname',
               evidence=['https://club.example/ivan-pichu'])
    scope=dict(unresolved=[owner]);config=dict(identity_state=str(path),cpks=[])
    result=extension.source_inventory(config,scope,[alias])['players'][0]
    assert result['native_player_id']==900 and result['fingerprint']=='current'
    assert result['source_player']['player_id']==10 and result['status']=='source_ready'
    assert not result['source_identity_evidence']['runtime_identity_changed']
    source.name='Unrelated Player'
    with pytest.raises(ValueError,match='no longer matches'):
        extension.source_inventory(config,scope,[alias])
    source.name='Pichu Player';parts[10]={}
    with pytest.raises(ValueError,match='no longer matches'):
        extension.source_inventory(config,scope,[alias])
    with pytest.raises(ValueError,match='identity changed'):
        extension.source_inventory(config,dict(unresolved=[dict(owner,fingerprint='old')]),[alias])
