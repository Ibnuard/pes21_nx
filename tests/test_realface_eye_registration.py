from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_eye_registration import register_pair
from test_realface_eye_fit import globe,rim


def pair(delta):
    centers=[np.array([-3,14,170]),np.array([3,14,170])]
    return np.concatenate([globe(c) for c in centers]),dict(zip(
        ['negative_x','positive_x'],[rim(c+delta) for c in centers]))


def test_shared_head_offset_preserves_interocular_spacing():
    delta=np.array([.1,.8,1.6]);points,guides=pair(delta)
    actual,report=register_pair(points,guides)
    assert actual==pytest.approx(delta,abs=1e-7)
    assert report['method']=='paired_head_frame_translation'
    for side in (-1,1):
        before=points[points[:,0]*side>0]
        assert (before[0]-before[1])==pytest.approx((before+actual)[0]-(before+actual)[1])


def test_supported_placement_and_bad_guide_are_not_silently_repositioned():
    points,guides=pair(np.array([0,.2,.1]))
    assert register_pair(points,guides)[0]==pytest.approx([0,0,0])
    for delta in ([0,-8,0],[0,0,5],[2,0,0]):
        points,guides=pair(np.array(delta))
        with pytest.raises(ValueError):register_pair(points,guides)
    points,guides=pair(np.array([0,0,2]))
    guides['positive_x']=np.asarray(guides['positive_x'])+[0,2,0]
    with pytest.raises(ValueError,match='consistent eye pair'):
        register_pair(points,guides)


def test_higher_skin_frame_requires_tightly_agreeing_measured_sockets():
    points,guides=pair(np.array([0,.1,3.3]))
    with pytest.raises(ValueError,match='exceeds bounds'):register_pair(points,guides)
    shift,_=register_pair(points,guides,skin_surface=True)
    assert shift==pytest.approx([0,.1,3.3])
    guides['positive_x']=np.asarray(guides['positive_x'])+[.8,0,0]
    with pytest.raises(ValueError,match='exceeds bounds'):
        register_pair(points,guides,skin_surface=True)
