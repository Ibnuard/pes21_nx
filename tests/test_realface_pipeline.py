import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_pipeline import identify,plan,cached_outputs_valid,sha,cache_key


def identity():
    profile = dict(base_id=7,native_player_id=100,fingerprint='player-seven',source_status='missing')
    registry = {'players':[dict(ef_base_id=7,native_player_id=100,fingerprint='player-seven',status='active',canonical_name='Synthetic') ]}
    return profile,registry


def test_missing_source_is_skipped_but_not_an_identity_bypass(tmp_path):
    profile,registry = identity()
    path=tmp_path/'registry.json';path.write_text(json.dumps(registry))
    manifest=dict(registry=str(path),players=[profile])
    assert plan(manifest)[0]['status']=='skipped_missing_source'
    profile['fingerprint']='donor'
    with pytest.raises(ValueError,match='fingerprint'):
        plan(manifest)


def test_reused_native_slot_and_duplicate_base_id_rejected(tmp_path):
    profile,registry = identity()
    registry['players'].append(dict(registry['players'][0],ef_base_id=8))
    with pytest.raises(ValueError,match='Multiple owners'):
        identify(profile,registry)
    registry['players'].pop()
    path=tmp_path/'registry.json';path.write_text(json.dumps(registry))
    with pytest.raises(ValueError,match='Duplicate BaseId'):
        plan(dict(registry=str(path),players=[profile,dict(profile)]))


def test_resume_requires_all_valid_artifact_hashes(tmp_path):
    folder=tmp_path/'job';candidate=folder/'candidate';candidate.mkdir(parents=True)
    names=('face.fbx','fit-report.json','roundtrip-pose-report.json','motion-samples.json','reference-fit.blend')
    for name in names:(candidate/name).write_bytes(name.encode())
    report=dict(cache_key='expected',outputs={name:sha(candidate/name) for name in names})
    path=folder/'complete.json';path.write_text(json.dumps(report))
    assert cached_outputs_valid(folder,'expected')
    assert not cached_outputs_valid(folder,'changed-input')
    (candidate/'face.fbx').write_bytes(b'modified-output')
    assert not cached_outputs_valid(folder,'expected')
    report['outputs']={};path.write_text(json.dumps(report))
    assert not cached_outputs_valid(folder,'expected')


def test_reference_binary_change_invalidates_cache(tmp_path):
    profile,_=identity()
    for name in ('face_fbx','native_rig','cooked_rig'):
        path=tmp_path/name;path.write_bytes(b'synthetic')
        profile[name]=str(path)
    binary=tmp_path/'mesh.bin';binary.write_bytes(b'before')
    for name in ('native_face','native_body'):
        path=tmp_path/(name+'.gltf');path.write_text(json.dumps({'buffers':[{'uri':'mesh.bin'}]}))
        profile[name]=str(path)
    before=cache_key(profile)
    assert before==cache_key(dict(profile,output='ignored-destination'))
    binary.write_bytes(b'after')
    assert before!=cache_key(profile)
