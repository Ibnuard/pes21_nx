import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_budget_cook import completed_imports


def test_resume_requires_matching_owner_and_all_saved_imports(tmp_path):
    profile = tmp_path/'profile.json'
    report = tmp_path/'report.json'
    profile.write_text(json.dumps(dict(native_player_id=12, opaque_eye_atlas=True,
                                       report=str(report))))
    report.write_text(json.dumps(dict(status='imported', player=12,
                                      parts=dict(face={}, hair={}))))
    folder = tmp_path/'Content/Assets/character/RealFace'
    folder.mkdir(parents=True)
    assert completed_imports(tmp_path, [profile]) is None
    for name in ('12_face', '12_hair', '12_face_tablet', '12_hair_parts_color_tablet', 'face_12'):
        (folder/(name+'.uasset')).write_bytes(b'saved import fixture')
    assert len(completed_imports(tmp_path, [profile])) == 6
    report.write_text(json.dumps(dict(status='imported', player=13,
                                      parts=dict(face={}, hair={}))))
    assert completed_imports(tmp_path, [profile]) is None


def test_partial_batch_cannot_skip_editor(tmp_path):
    profile = tmp_path/'profile.json'
    profile.write_text(json.dumps(dict(native_player_id=12, opaque_eye_atlas=True,
                                       report=str(tmp_path/'absent.json'))))
    assert completed_imports(tmp_path, [profile]) is None
    assert completed_imports(tmp_path, []) is None
