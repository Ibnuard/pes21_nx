from pathlib import Path
import sys
import json
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_import_cache as cache
from realface_pipeline import sha


def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(cache,'importer_key',lambda config:'compiler')
    source=tmp_path/'source';source.mkdir()
    profile=dict(native_player_id=7,fingerprint='locked',face_fbx='face.fbx',report=str(tmp_path/'report.json'))
    path=tmp_path/'profile.json';path.write_text(json.dumps(profile))
    for name in cache.allowed_names(7):(source/name).write_bytes(name.encode())
    prior=dict(base_id=5,native_player_id=7,prepared_key='prepared',profile_key=cache.profile_key(profile),
               assets={n:sha(source/n) for n in cache.allowed_names(7)},report=dict(player=7,status='imported',parts={'face':{},'hair':{}}))
    manifest=tmp_path/'receipt.json';manifest.write_text(json.dumps(dict(importer_key='compiler',assets_root=str(source),players=[prior])))
    config=dict(reuse_imported_manifest=str(manifest));row=dict(base_id=5,native_player_id=7,cache_key='prepared',ue_profile=str(path))
    return config,row,source,manifest


def test_completed_import_is_reused_only_with_same_profile_and_asset_bytes(tmp_path,monkeypatch):
    c,r,source,m=fixture(tmp_path,monkeypatch)
    assert cache.restore(c,[r],tmp_path/'project')==1 and r['restored_import']
    (source/'7_face.uasset').write_bytes(b'changed')
    with pytest.raises(ValueError,match='asset changed'):cache.restore(c,[r],tmp_path/'other')


def test_changed_recipe_is_reimported_and_wrong_identity_or_compiler_rejected(tmp_path,monkeypatch):
    c,r,source,m=fixture(tmp_path,monkeypatch)
    assert cache.restore(c,[dict(r,cache_key='new')],tmp_path/'project')==0
    with pytest.raises(ValueError,match='identity'):
        cache.restore(c,[dict(r,native_player_id=8)],tmp_path/'project')
    monkeypatch.setattr(cache,'importer_key',lambda config:'different')
    with pytest.raises(ValueError,match='compiler'):cache.restore(c,[r],tmp_path/'project')


def test_capture_cannot_stamp_an_unknown_compiler_onto_old_imports(tmp_path,monkeypatch):
    monkeypatch.setattr(cache,'importer_key',lambda config:'current')
    with pytest.raises(ValueError,match='compiler provenance'):
        cache.capture({},[],tmp_path/'unknown-build',tmp_path/'receipt.json')
