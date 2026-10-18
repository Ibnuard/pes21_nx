import sys
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_skin_markers import marker_triangles


def test_only_isolated_microscopic_cluster_is_removed():
    positions=np.array([[0,0,0],[1,0,0],[0,1,0],
                        [0,0,2],[.005,0,2],[0,.005,2]])
    removed,proof=marker_triangles(positions,[[0,1,2],[3,4,5]],[(('head',1.),)]*6)
    assert removed==[1]
    assert proof[0]['extent_cm']<.01


def test_tiny_face_attached_to_real_feature_is_preserved():
    positions=[[0,0,0],[1,0,0],[0,1,0],[.005,0,0],[0,.005,0]]
    assert marker_triangles(positions,[[0,1,2],[0,3,4]],[(('head',1.),)]*5)[0]==[]


def test_animation_discontinuity_and_long_thin_features_are_preserved():
    p=[[0,0,0],[.005,0,0],[0,.005,0]]
    assert marker_triangles(p,[[0,1,2]],[(('head',1.),),(('neck',1.),),(('head',1.),)])[0]==[]
    assert marker_triangles([[0,0,0],[.2,0,0],[.1,.0001,0]],[[0,1,2]],[(('head',1.),)]*3)[0]==[]
