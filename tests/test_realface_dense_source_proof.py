"""Dense source admission proves ownership without claiming an independent cook."""
import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import realface_dense_source_proof as proof
import realface_lite


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf8')
    return str(path)


def fixture(tmp_path, monkeypatch):
    owner = dict(base_id=123, native_player_id=7, fingerprint='canonical', status='source_ready',
        name='Own Player', source_player={'player_id': 123},
        source_identity_evidence=dict(policy='base_id_name_biography_v1', base_id=123,
            canonical_fingerprint='canonical', source_row_sha256='biography'))
    folder=tmp_path/'dense'; folder.mkdir()
    profile={k:owner[k] for k in ('base_id','native_player_id','fingerprint')}
    for key in ('face_fbx','hair_fbx','face_texture','hair_texture','native_eye_texture'):
        path=folder/key; path.write_bytes(key.encode()); profile[key]=str(path)
    path=folder/'ue-profile.json'; write(path, profile)
    row=dict(profile=str(path), name=owner['name'], **{k:owner[k] for k in ('base_id','native_player_id','fingerprint')})
    row['input_hashes']={name:proof.sha(name) for name in [str(path)]+[profile[k] for k in
        ('face_fbx','hair_fbx','face_texture','hair_texture','native_eye_texture')]}
    inventory=tmp_path/'inventory.json';write(inventory,dict(players=[owner]))
    config=dict(source_preparation_policy=proof.POLICY,dense_inventory=str(inventory))
    accepted=dict(row,status='dense_source_verified',dense_source=dict(inventory_sha256=proof.sha(inventory),
        inventory_row_key=proof.key_of(owner),folder=str(folder),cache_key='prepared-key'))
    monkeypatch.setattr(proof,'valid_prepared_cache',lambda folder,key:key=='prepared-key')
    return config,row,accepted,owner


def test_dense_source_is_explicit_and_payload_bound(tmp_path,monkeypatch):
    config,row,accepted,_=fixture(tmp_path,monkeypatch)
    assert proof.validate(config,row,accepted)
    with pytest.raises(ValueError,match='Explicit'):
        proof.validate(dict(config,source_preparation_policy=''),row,accepted)
    Path(next(n for n in row['input_hashes'] if n.endswith('hair_fbx'))).write_bytes(b'changed')
    with pytest.raises(ValueError,match='payload changed'):
        proof.validate(config,row,accepted)


@pytest.mark.parametrize('change', ['native','fingerprint','numeric_donor','weak_evidence','row_binding','cache'])
def test_dense_source_rejects_reused_slot_and_weak_evidence(tmp_path,monkeypatch,change):
    config,row,accepted,owner=fixture(tmp_path,monkeypatch)
    if change=='native': row['native_player_id']=8
    elif change=='fingerprint': row['fingerprint']='different'
    elif change=='numeric_donor': owner['source_player']['player_id']=456
    elif change=='weak_evidence': owner['source_identity_evidence']['policy']='verified_name_country'
    elif change=='row_binding': accepted['dense_source']['inventory_row_key']='wrong'
    else: accepted['dense_source']['cache_key']='wrong'
    if change in ('numeric_donor','weak_evidence'):
        write(Path(config['dense_inventory']),dict(players=[owner]))
        accepted['dense_source']['inventory_sha256']=proof.sha(config['dense_inventory'])
        accepted['dense_source']['inventory_row_key']=proof.key_of(owner)
    with pytest.raises(ValueError): proof.validate(config,row,accepted)


def test_historical_sources_do_not_admit_dense_status_by_default(tmp_path,monkeypatch):
    config,row,accepted,owner=fixture(tmp_path,monkeypatch)
    config['source_profiles']=write(tmp_path/'profiles.json',[row])
    config['source_verification']=write(tmp_path/'verification.json',dict(players=[accepted]))
    config['identity_state']=write(tmp_path/'identity.json',dict(identities={'123':dict(owner,status='active')}))
    assert len(realface_lite.sources(config))==1
    del config['source_preparation_policy']
    with pytest.raises(ValueError,match='exactly once'): realface_lite.sources(config)


@pytest.mark.parametrize('alias,height,foot,allowed',[(False,7,1,True),(True,2,0,True),(True,7,0,False),(True,2,1,False),(False,16,0,False)])
def test_explicit_biography_variance_policy_is_direct_base_bound(tmp_path,monkeypatch,alias,height,foot,allowed):
    config,row,accepted,owner=fixture(tmp_path,monkeypatch)
    owner.pop('source_identity_evidence')
    owner.update(identity_status='verified_name_country')
    owner['source_player']=dict(player_id=456 if alias else 123,name='Own Player')
    canonical=dict(owner,status='active',country=204,height=180,age=25,foot=0,position=9)
    config['identity_state']=write(tmp_path/'identity.json',dict(identities={'123':canonical}))
    write(Path(config['dense_inventory']),dict(players=[owner]))
    bio=dict(source_player_id=owner['source_player']['player_id'],name='Own Player',country=204,height=180+height,age=25,
        foot=foot,position=9,row_sha256='a'*64,archive='own-source.cpk',player_table_sha256='b'*64)
    supplement=dict(inventory_sha256=proof.sha(config['dense_inventory']),players=[dict(base_id=123,native_player_id=7,
        fingerprint='canonical',source=bio)],archives=[dict(path='own-source.cpk',player_table_sha256='b'*64)])
    config['source_identity_supplement']=write(tmp_path/'supplement.json',supplement)
    if allowed:
        evidence=proof.identity_evidence(config,owner)
        assert evidence['direct_base_id'] is (not alias)
        assert evidence['height_delta_cm']==height and evidence['same_foot'] is (foot==0)
    else:
        with pytest.raises(ValueError):proof.identity_evidence(config,owner)
