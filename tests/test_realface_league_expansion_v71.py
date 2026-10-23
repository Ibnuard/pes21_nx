"""Initialize one new dense owner without relabelling or recooking the old one."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_league_expansion as expansion
from test_realface_dense_source_proof import fixture,write


def test_expansion_keeps_old_cook_and_scopes_extra_clubs(tmp_path,monkeypatch):
    config,row,binding,owner=fixture(tmp_path,monkeypatch)
    root=tmp_path/'new';dense=root/'dense';dense.mkdir(parents=True)
    old=tmp_path/'old';old.mkdir()
    owner['team_ids']=[110]
    write(dense/'inventory.local.json',dict(players=[owner]))
    write(root/'DENSE-STAGE-STATUS.json',dict(state='completed'))
    write(dense/'prepare-report.json',[dict(base_id=123,native_player_id=7,name='Own Player',status='prepared',
        folder=binding['dense_source']['folder'],cache_key='prepared-key')])
    retained=dict(base_id=99,native_player_id=99,fingerprint='old-fingerprint',name='Retained',team_ids=[100],status='preserved_verified')
    identity=write(tmp_path/'identities.json',dict(identities={str(p['base_id']):dict(p,status='active') for p in (owner,retained)}))
    catalog=write(tmp_path/'catalog.json',dict(categories=[dict(key=k,team_ids=[i]) for k,i in
        [('english_league',100),('spanish_league',108),('ligue_1',110),('serie_a',310)]],
        teams=[dict(team_id=i,physical_team_id=i+1000) for i in (100,108,110,310,5738,18961)]))
    selector=write(tmp_path/'selector.json',{})
    dense_config=dict(work_dir=str(dense),categories=['ligue_1','serie_a'],team_ids=[5738,18961],
        identity_state=identity,catalog=catalog,selector=selector)
    dc=write(dense/'config.local.json',dense_config)
    old_profile=dict(retained,profile=str(old/'unused-original.json'),input_hashes={})
    old_config=dict(work_dir=str(old),categories=['english_league','spanish_league'],
        source_profiles=write(old/'sources.json',[old_profile]),source_verification=write(old/'proof.json',dict(players=[retained])))
    oc=write(old/'config.local.json',old_config)
    old_cook=dict(retained,status='validated_cached',cooked_folder='immutable-old-cook',cooked_cache_key='old-key',triangles=4900)
    write(old/'prepare-report.json',[dict(old_cook,status='prepared_cached')])
    old_bytes=Path(write(old/'verify-report.json',[old_cook])).read_bytes()
    monkeypatch.setattr(expansion,'valid_prepared_cache',lambda path,key:True)
    monkeypatch.setattr(expansion.league,'local_output',lambda path:Path(path))
    result=expansion.initialize(dc,oc,tmp_path/'budget')
    assert result['retained_cooked']==1 and result['new_dense_sources']==1 and result['teams']==6
    assert Path(old/'verify-report.json').read_bytes()==old_bytes
    assert json.loads((tmp_path/'budget/verify-report.json').read_text())==[old_cook]
    output=json.loads((tmp_path/'budget/config.local.json').read_text())
    assert output['accepted_head_count']==1 and output['source_preparation_policy']==expansion.DENSE_POLICY
    assert not result['final_budget_acceptance'] and not result['cosmetic_review_blocks_release']
    with pytest.raises(ValueError,match='already exists'):
        expansion.initialize(dc,oc,tmp_path/'budget')


def test_active_dense_stage_is_not_consumed(tmp_path):
    dense=tmp_path/'dense';dense.mkdir()
    write(tmp_path/'DENSE-STAGE-STATUS.json',dict(state='running'))
    config=write(tmp_path/'config.json',dict(work_dir=str(dense)))
    accepted=write(tmp_path/'accepted.json',{})
    with pytest.raises(ValueError,match='owned dense stage'):
        expansion.initialize(config,accepted,tmp_path/'budget')
