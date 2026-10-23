"""Every theme must use conditional added time, with readable dynamic digits."""
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_fl26_scoreboard_profiles as profiles
from afp_score_layout import placements,read_movies
from test_scoreboard_england_v68 import colour_at,node

@pytest.fixture(scope='module')
def score():
    p=ROOT/'local-debug/scoreboard-v62/mobile.bin'
    if not p.is_file():pytest.skip('requires ignored owned Mobile UI')
    raw=p.read_bytes();assert profiles.digest(raw)==profiles.v62.MOBILE_SHA256
    return next(m.data for m in read_movies(raw) if m.name=='game2d_score')

@pytest.mark.parametrize('profile',profiles.PROFILES)
def test_all_leagues_keep_the_ordinary_plate_outside_view_and_added_time_conditional(score,profile):
    data,report=profiles.patch_score(score,profile);rows=placements(data)
    for row in rows:
        if (row['parent'],row['depth'])==(28,13) and 'translate' in row:
            x,y=row['translate'];assert x+32+48<0 and y+12+24<0
    root=node(rows,28,56)['translate'];child=node(rows,22,1)['translate']
    left,top=(a+b for a,b in zip(root,child))
    assert (left,top,left+48,top+24)==profiles.PROFILES[profile]['added_time_cell']
    for frame in range(17,41):
        assert colour_at(rows,24,3,frame)>>8==0
        assert colour_at(rows,24,1,frame)>>8==0xffffff
    assert colour_at(rows,24,1,41)&255==0
    audit=profiles.field_edit_report(score,data)
    assert audit['scripts_labels_frames_bindings_identical']
    assert len(audit['placement_flag_changes'])==1
    assert report['text_optical_y_offset_pixels']==-3

def test_england_packet_stays_equal_to_the_accepted_r2_timeline(score):
    path=ROOT/'local-debug/scoreboard-england-v68-r2/candidate/england/game2dPes-candidate.bin'
    if not path.is_file():pytest.skip('requires ignored v68-r2 candidate')
    old=next(m.data for m in read_movies(path.read_bytes()) if m.name=='game2d_score')
    assert profiles.patch_score(score,'england')[0]==old
