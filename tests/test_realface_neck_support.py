from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_neck_support import supported_seam_moves


def patch():
    points=np.array([[0,0,0],[0,0,0],[1,0,0],[0,0,1],[-1,0,0],[0,0,-1]],float)
    faces=[(0,2,3),(1,3,4),(1,4,5),(0,5,2)]
    fitted=points.copy();fitted[2:]+=[0,.3,0]
    return points,fitted,faces,set(range(2,6)),[0,1]


def test_uv_aliases_share_one_supported_move_without_chaining():
    p,f,t,c,u=patch()
    result=supported_seam_moves(p,f,t,c,u,1.21)
    assert len(result)==1 and result[0]['indices']==[0,1]
    assert result[0]['delta_cm']==pytest.approx([0,.3,0])
    assert result[0]['minimum_triangle_normal_cosine']==pytest.approx(1)
    assert np.all(p[:2]==f[:2])  # The helper reports moves without editing input.


def test_unverified_or_incoherent_support_cannot_authorize_a_move():
    p,f,t,c,u=patch()
    with pytest.raises(ValueError,match='fully fitted'):
        supported_seam_moves(p,f,t,c-{2},u,1.21)
    f[2]+=[0,2,0]
    with pytest.raises(ValueError,match='coherent bounded'):
        supported_seam_moves(p,f,t,c,u,1.21)
    p,f,t,c,u=patch()
    with pytest.raises(ValueError,match='coherent bounded'):
        supported_seam_moves(p,f,t,c,u,.1)
    with pytest.raises(ValueError,match='four distinct'):
        supported_seam_moves(p,f,t[:2],c,u,1.21)


def test_folded_and_nonfinite_support_are_rejected():
    p,f,t,c,u=patch();p*=.3;f*=.3;f[2,0]=-.03
    with pytest.raises(ValueError,match='fold or collapse'):
        supported_seam_moves(p,f,t,c,u,1.21)
    p,f,t,c,u=patch();f[2,0]=np.nan
    with pytest.raises(ValueError,match='finite'):
        supported_seam_moves(p,f,t,c,u,1.21)


def test_adjacent_unresolved_points_use_verified_boundary_without_chaining():
    p=np.array([[-.15,0,0],[.15,0,0],[-1,0,0],[0,0,1],[1,0,0],[0,0,-1]],float)
    faces=[(0,2,3),(0,3,1),(1,3,4),(1,4,5),(1,5,0),(0,5,2)]
    fitted=p.copy();fitted[2:]+=[0,.3,0]
    result=supported_seam_moves(p,fitted,faces,{2,3,4,5},[0,1],1.21)
    assert result[0]['indices']==[0,1]
    assert result[0]['support_indices']==[2,3,4,5]
    assert result[0]['delta_cm']==pytest.approx([0,.3,0])
