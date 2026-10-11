import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_eye_fit import sphere,fit_socket,pupil_position,rotation_between,radial_atlas_pupil
from extract_team_realfaces import safe_member,write_once
from export_pes_fmdl_gltf import _mobile_bone_name


def globe(center=(3,14,170),radius=1.45):
    return np.asarray([np.asarray(center)+radius*np.array([
        math.sin(a)*math.cos(b),math.cos(a),math.sin(a)*math.sin(b)])
        for a in np.linspace(.05,2.5,15) for b in np.linspace(0,2*math.pi,24,endpoint=False)])


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


def test_outliers_do_not_silently_produce_candidates():
    p=globe();pupil=[3,15.45,170]
    with pytest.raises(ValueError,match='too far'):fit_socket(p,pupil,rim([3,14,174]))
    with pytest.raises(ValueError,match='non-finite'):fit_socket(p,pupil,[[math.nan,0,0]]*8)
    with pytest.raises(ValueError,match='gaze'):fit_socket(p,[4,15,170],rim([3,14,170]))
    with pytest.raises(ValueError,match='degenerate'):sphere([[i,0,0] for i in range(15)])


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
