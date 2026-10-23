"""Compact native fields and event-lifecycle invariants, with optional owned UI."""
from pathlib import Path
import struct
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_fl26_scoreboard_profiles as profiles
from afp_score_layout import read_movies,placements

@pytest.fixture
def mobile():
    path=ROOT/'local-debug/scoreboard-v62/mobile.bin'
    if not path.is_file():
        pytest.skip('requires ignored owned Mobile game2dPes.bin; no proprietary fixture is restored')
    data=path.read_bytes()
    assert profiles.digest(data)==profiles.v62.MOBILE_SHA256
    return data

@pytest.mark.parametrize('profile',profiles.PROFILES)
def test_native_score_fields_fit_compact_cells_for_all_authored_frames(mobile,profile):
    score=next(m for m in read_movies(mobile) if m.name=='game2d_score')
    changed,report=profiles.patch_score(score.data,profile)
    assert report['fields_inside_separate_cells']
    assert report['checked_placement_updates']>=60
    assert report['clock_minute_states']==[1,2,3]
    proof=profiles.field_edit_report(score.data,changed)
    assert proof['scripts_labels_frames_bindings_identical']
    assert not proof['scripts_labels_frames_bindings_flags_identical']
    assert proof['edits'] and not proof['pc_animation_imported']
    # The independent verifier must reject a field moved across its boundary.
    bad=bytearray(changed)
    row=next(r for r in placements(changed) if r['parent']==28 and r['depth']==63 and 'translate_offset' in r)
    struct.pack_into('<i',bad,row['translate_offset'],20000)
    with pytest.raises(ValueError,match='leaves profile cell'):
        profiles.verify_geometry(placements(bad),profiles.PROFILES[profile])

@pytest.mark.parametrize('event',['game2d_memberChange','game2d_goal','game2d_card'])
def test_complete_event_timeline_translates_without_changing_native_motion(mobile,event):
    movie=next(m for m in read_movies(mobile) if m.name==event)
    changed=profiles.patch_event(movie.data,66)
    before,after=placements(movie.data),placements(changed)
    root=next(r for r in before if r['parent'] is None and r.get('name')=='main')['source']
    moved=0
    for old,new in zip(before,after):
        if old['parent']==root and 'translate' in old:
            assert new['translate']==(old['translate'][0],old['translate'][1]+66)
            moved+=1
        else:
            assert new==old
    assert moved
    report=profiles.field_edit_report(movie.data,changed)
    assert report['scripts_labels_frames_bindings_flags_identical']
    assert all(e['field']=='translate' for e in report['edits'])

def test_spain_size_and_each_profile_reserve_separate_auxiliary_event_bands():
    assert profiles.PROFILES['spain']['size']==(164,88)
    assert len({p['layout'] for p in profiles.PROFILES.values()})==4
    assert {p['key'] for p in profiles.PROFILES.values()}=={9,10,11,12}
    for spec in profiles.PROFILES.values():
        bottom=32+spec['size'][1]
        assert bottom+38<bottom+40
        assert spec['clock_cell'][3]<=20+spec['size'][1]

def test_wrong_owned_revision_fails_before_any_atlas_or_movie_edit():
    with pytest.raises(ValueError,match='pinned owned revision'):
        profiles.build_profile(b'invalid Mobile',b'invalid PC','spain')

def test_england_native_name_boxes_center_in_their_own_cells():
    spec=profiles.PROFILES['england']
    for point,cell in zip(spec['names'],spec['name_cells']):
        native_box_center=point[0]+spec.get('name_width',60)*profiles.SCALE/2
        assert native_box_center==(cell[0]+cell[2])/2
