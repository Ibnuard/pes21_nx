from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_vertex_audit import match_vertices


def test_duplicate_seams_match_one_complete_tuple():
    source=[(0,0,0)]*2000;uv=[{(0,0)}]*2000;weights=[{'head':1.}]*2000
    errors,st,bones=match_vertices([(0,0,.00001)],[(0,0)],[{'head':1.}],source,uv,weights,.03)
    assert errors==pytest.approx([.00001]) and st==[0] and bones==[0]


def test_uv_and_weights_cannot_come_from_different_seam_vertices():
    with pytest.raises(ValueError,match='matching source'):
        match_vertices([(0,0,0)],[(0,0)],[{'head':1.}],[(0,0,0)]*2,
            [{(0,0)},{(.5,.5)}],[{'chest':1.},{'head':1.}],.03)


def test_position_and_nonfinite_fail_even_when_uv_and_weights_match():
    for point in ((1,0,0),(float('nan'),0,0)):
        with pytest.raises(ValueError):
            match_vertices([point],[(0,0)],[{'head':1.}],[(0,0,0)],[{(0,0)}],[{'head':1.}],.03)
