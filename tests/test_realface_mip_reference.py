from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import numpy as np
import pytest
from realface_mip_reference import (match_destination_coverage,alpha_reference_chain,
                                    bilinear,lod_for_triangle,masked_raster,reference_error)


def test_destination_measurement_recovers_representable_lost_mask():
    raw=np.array([[60,30],[20,10]],np.uint8)
    candidate,proof=match_destination_coverage(raw,.25)
    assert np.mean(candidate>=85)==.25 and proof['absolute_error']==0
    assert np.mean(raw>=85)==0


def test_uniform_mip_does_not_force_nonempty_to_satisfy_a_gate():
    raw=np.full((4,4),30,np.uint8)
    candidate,proof=match_destination_coverage(raw,.05)
    assert not np.any(candidate>=85)
    assert proof['absolute_error']==.05


def test_empty_alpha_stays_empty():
    raw=np.zeros((4,4),np.uint8)
    candidate,proof=match_destination_coverage(raw,.2)
    assert np.array_equal(raw,candidate) and proof['measured']==0


def test_zero_target_does_not_retain_an_opaque_uniform_reference():
    candidate,proof=match_destination_coverage(np.full((4,4),255,np.uint8),0.)
    assert not np.any(candidate>=85) and proof['absolute_error']==0


def test_base_and_zero_texels_stay_exact():
    base=np.array([[0,255],[0,90]],np.uint8);tiny=np.array([[0,25],[50,75]],np.uint8)
    chain,_=alpha_reference_chain([base,tiny])
    assert np.array_equal(chain[0],base)
    assert chain[1][0,0]==0


@pytest.mark.parametrize('target',[-.1,1.1])
def test_invalid_target_rejected(target):
    with pytest.raises(ValueError):match_destination_coverage(np.ones((2,2),np.uint8),target)


def test_periodic_bilinear_and_centers():
    a=np.array([[0,100],[200,255]],np.uint8)
    assert bilinear(a,np.array([.25,.25]))==0
    assert bilinear(a,np.array([.75,.25]))==100
    assert bilinear(a,np.array([1.75,.25]))==100
    assert bilinear(a,np.array([.5,.5]))==138.75


def test_orthographic_lod_tracks_screen_footprint():
    uv=np.array([[0.,0.],[1.,0.],[0.,1.]])
    p=uv*32
    assert abs(lod_for_triangle(p,uv,(128,128))-2)<1e-9
    assert abs(lod_for_triangle(p*2,uv,(128,128))-1)<1e-9


def test_skin_occludes_hair_and_explicit_reference_ignores_lod():
    p=np.array([[0.,0.,1.],[1.,0.,1.],[0.,1.,1.]])
    t=np.array([[0,1,2]]);uv=np.array([[[0.,0.],[1.,0.],[0.,1.]]]);basis=np.eye(3)
    chain=[np.full((128,128),255,np.uint8),np.zeros((64,64),np.uint8)]
    empty=np.full((4,4),-np.inf)
    live,_=masked_raster(p,t,uv,chain,basis,([0,0],[1,1]),4,empty,explicit_base=True)
    masked,_=masked_raster(p,t,uv,chain,basis,([0,0],[1,1]),4,empty)
    occluded,_=masked_raster(p,t,uv,chain,basis,([0,0],[1,1]),4,np.full((4,4),2.),explicit_base=True)
    assert live.sum()>0 and masked.sum()==0 and occluded.sum()==0


def test_reference_error_penalizes_added_pixels():
    reference=np.array([[1.,0.],[0.,0.]])
    assert reference_error(reference.astype(bool),reference)['normalized_absolute_error']==0
    assert reference_error(np.ones((2,2),bool),reference)['normalized_absolute_error']==3


def test_equal_atlas_coverage_can_have_different_visible_head_coverage():
    p=np.array([[0.,0.,1.],[1.,0.,1.],[0.,1.,1.]])
    triangles=np.array([[0,1,2]])
    uv=np.array([[[.65,.65],[.68,.65],[.65,.68]]])
    used=np.zeros((4,4),np.uint8);used[2,2]=255
    unused=np.zeros((4,4),np.uint8);unused[0,0]=255
    assert np.mean(used>=85)==np.mean(unused>=85)
    args=(np.eye(3),([0,0],[1,1]),4,np.full((4,4),-np.inf))
    a,_=masked_raster(p,triangles,uv,[used],*args,explicit_base=True)
    b,_=masked_raster(p,triangles,uv,[unused],*args,explicit_base=True)
    assert a.sum()>0 and b.sum()==0
