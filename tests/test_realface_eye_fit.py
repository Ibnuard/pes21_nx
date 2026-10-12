import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_eye_fit import sphere,fit_socket,fit_source_globe,pupil_position,rotation_between,radial_atlas_pupil,verified_source_pair


def test_source_globe_fallback_uses_measured_geometry_and_rejects_bad_reference():
    points=globe();pupil=np.array([3,15.45,170])
    source=globe(center=(3.1,14.2,170.4),radius=1.4)
    fitted,rotation,report=fit_source_globe(points,pupil,source)
    center,radius,_=sphere(fitted)
    assert center==pytest.approx([3.1,14.2,170.4])
    assert radius==pytest.approx(1.4)
    assert report['method']=='own_source_eyeball_geometry'
    with pytest.raises(ValueError,match='outside the head'):
        fit_source_globe(points,pupil,globe(center=(3,5,170)))


def test_explicit_source_control_aliases_do_not_accept_unknown_roots():
    targets={'sk_head','sk_neck'}
    assert _mobile_bone_name('RightLowMiddleEyebrow',targets)=='sk_head'
    assert _mobile_bone_name('RightLowEyelid',targets)=='sk_head'
    assert _mobile_bone_name('d_scm_02_l',targets)=='sk_neck'
    with pytest.raises(ValueError,match='no mobile skeleton mapping'):
        _mobile_bone_name('Group',targets)
from extract_team_realfaces import safe_member,write_once
from export_pes_fmdl_gltf import _mobile_bone_name


def globe(center=(3,14,170),radius=1.45):
    return np.asarray([np.asarray(center)+radius*np.array([
        math.sin(a)*math.cos(b),math.cos(a),math.sin(a)*math.sin(b)])
        for a in np.linspace(.05,2.5,15) for b in np.linspace(0,2*math.pi,24,endpoint=False)])


def test_source_pair_can_size_small_template_but_single_or_oversized_globe_cannot():
    pair=dict(negative_x=globe((-3.3,13.8,170),1.6),positive_x=globe((3.35,13.4,170),1.74))
    assert verified_source_pair(pair)
    small=globe((3,14,170),1.3);pupil=np.array([3,15.3,170])
    with pytest.raises(ValueError,match='excessive template'):
        fit_source_globe(small,pupil,pair['positive_x'])
    result,_,report=fit_source_globe(small,pupil,pair['positive_x'],measured_pair=verified_source_pair(pair))
    assert sphere(result)[1]==pytest.approx(1.74)
    assert report['source_pair_size_verified']
    assert not verified_source_pair(dict(positive_x=pair['positive_x']))
    assert not verified_source_pair(dict(pair,positive_x=globe((3.35,13.4,170),1.95)))
    assert not verified_source_pair(dict(pair,positive_x=globe((3.35,13.4,172),1.74)))


def rim(center,radius=1.45):
    rows=[]
    for t in np.linspace(0,2*math.pi,24,endpoint=False):
        x,z=1.1*math.cos(t),.45*math.sin(t)
        rows.append(np.asarray(center)+[x,math.sqrt(radius*radius-x*x-z*z),z])
    return rows


def test_each_face_places_eyes_from_its_own_opening():
    original=np.array([3.,14.,170.]);points=globe(original)
    pupil=original+np.array([.15,math.sqrt(1.45**2-.15**2),0])
    for target in ([3.2,14.1,170.25],[2.8,13.9,169.7]):
        fitted,rotation,report=fit_socket(points,pupil,rim(target))
        center,radius,error=sphere(fitted)
        assert center==pytest.approx(target,abs=1e-8)
        assert radius==pytest.approx(1.45)
        assert rotation@rotation.T==pytest.approx(np.eye(3),abs=1e-8)
        assert report['pupil_after_cm'][0]==pytest.approx(target[0])
        assert report['pupil_after_cm'][2]==pytest.approx(target[2])
        assert error<1e-10


def test_asymmetric_eye_positions_are_not_mirrored_blindly():
    for source,target in [([-3,14,170],[-3.1,14.2,169.8]),([3,14,170],[2.9,14.1,170.3])]:
        _,_,report=fit_socket(globe(source),np.asarray(source)+[0,1.45,0],rim(target))
        assert report['target_center_cm']==pytest.approx(target)


def test_measured_skin_depth_keeps_globe_inside_uneven_lid_without_rescaling():
    opening=np.asarray(rim([3,14,170]))
    opening[:6,1]-=.3
    points=globe();pupil=[3,15.45,170]
    _,_,helper=fit_socket(points,pupil,opening)
    fitted,_,skin=fit_socket(points,pupil,opening,skin_surface=True)
    assert skin['target_center_cm'][1]==pytest.approx(13.7)
    assert helper['target_center_cm'][1]==pytest.approx(14.)
    assert skin['depth_clearance_cm']==pytest.approx(.3)
    assert sphere(fitted)[1]==pytest.approx(1.45)
    assert skin['pupil_after_cm'][0]==pytest.approx(3.)
    assert skin['pupil_after_cm'][2]==pytest.approx(170.)
    assert skin['depth_policy']=='skin_enclosure_quantile_15'


def test_skin_clearance_rejects_excessive_or_unstable_depth():
    opening=np.asarray(rim([3,14,170]));opening[:6,1]-=.5
    with pytest.raises(ValueError,match='excessive eye depth clearance'):
        fit_socket(globe(),[3,15.45,170],opening,skin_surface=True)
    opening[:6,1]-=.5
    with pytest.raises(ValueError,match='stable globe depth'):
        fit_socket(globe(),[3,15.45,170],opening,skin_surface=True)


def test_outliers_do_not_silently_produce_candidates():
    p=globe();pupil=[3,15.45,170]
    with pytest.raises(ValueError,match='too far'):fit_socket(p,pupil,rim([3,14,174]))
    with pytest.raises(ValueError,match='non-finite'):fit_socket(p,pupil,[[math.nan,0,0]]*8)
    with pytest.raises(ValueError,match='gaze'):fit_socket(p,[4,15,170],rim([3,14,170]))
    with pytest.raises(ValueError,match='degenerate'):sphere([[i,0,0] for i in range(15)])


def test_isolated_tear_duct_depth_fallback_preserves_globe_size():
    opening=np.asarray(rim([3,14,170]));opening[[0,12],1]-=1.5
    with pytest.raises(ValueError,match='stable globe depth'):
        fit_socket(globe(),[3,15.45,170],opening,skin_surface=True)
    fitted,_,report=fit_socket(globe(),[3,15.45,170],opening,skin_surface=True,edge_outlier_fallback=True)
    assert report['excluded_tear_duct_samples']==[0,12]
    assert sphere(fitted)[1]==pytest.approx(1.45)
    assert report['rim_depth_rms_cm']<.01
    for indices in ([6,18],[0,1,2,12]):
        bad=np.asarray(rim([3,14,170]));bad[indices,1]-=1.5
        with pytest.raises(ValueError,match='isolated tear-duct'):
            fit_socket(globe(),[3,15.45,170],bad,skin_surface=True,edge_outlier_fallback=True)


def test_uv_atlas_requires_explicit_frontmost_policy():
    points=[[0,1,0],[1,1,0],[0,1,1],[0,-1,0],[1,-1,0],[0,-1,1]]
    uv=[[0,0],[1,0],[0,1]]*2;faces=[(0,1,2),(3,4,5)]
    with pytest.raises(ValueError,match='ambiguous'):pupil_position(points,uv,faces,[.2,.3])
    assert pupil_position(points,uv,faces,[.2,.3],True)==pytest.approx([.2,1,.3])


def test_native_radial_atlas_uses_pupil_pole_not_rectangle_centre():
    points=[[3,15.5,170],[3,15.5,170],[2.5,15.3,170],[3.5,15.3,170]]
    uv=[[.88,.123],[.99,.123],[.88,.0625],[.99,.0625]]
    assert radial_atlas_pupil(points,uv)==pytest.approx([3,15.5,170])
    points[1]=[3.3,15.5,170]
    with pytest.raises(ValueError,match='unique'):radial_atlas_pupil(points,uv)


def test_invalid_landmarks_cannot_pass_angle_limits_with_nan():
    for direction in ([0,0,0],[math.nan,1,0],[1,2]):
        with pytest.raises(ValueError,match='finite and nonzero'):
            rotation_between(direction,[0,1,0])
    with pytest.raises(ValueError,match='finite positions'):
        radial_atlas_pupil([[0,math.nan,0]],[[.8,.1]])


def test_extraction_cannot_escape_or_replace_changed_inputs(tmp_path):
    for name in ('../outside','C:/outside','/outside','a/../../outside'):
        with pytest.raises(ValueError):safe_member(tmp_path,name)
    path=safe_member(tmp_path,'valid/face.bin');write_once(path,b'original')
    write_once(path,b'original')
    with pytest.raises(ValueError,match='changed'):write_once(path,b'other')


def test_extra_face_bones_map_only_to_supported_anatomy():
    targets={'sk_head','sk_shoulder_l','sk_shoulder_r'}
    assert _mobile_bone_name('dsk_ear_b_l',targets)=='sk_head'
    assert _mobile_bone_name('dsk_hair',targets)=='sk_head'
    assert _mobile_bone_name('dsk_collar_r',targets)=='sk_shoulder_r'
    with pytest.raises(ValueError):_mobile_bone_name('dsk_unknown',targets)
