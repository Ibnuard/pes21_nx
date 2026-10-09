"""Synthetic geometry only; these tests do not need extracted game assets."""
import json
import math
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_reference import (barycentric, load_reference, mix_weights,
                                socket_target_x, socket_target_z)


def reference_file(tmp_path):
    raw, views, accessors = bytearray(), [], []
    def attribute(rows, fmt, component, kind):
        start = len(raw)
        for row in rows:
            raw.extend(struct.pack('<'+fmt*len(row), *row))
        views.append(dict(buffer=0, byteOffset=start, byteLength=len(raw)-start))
        accessors.append(dict(bufferView=len(views)-1, componentType=component,
                              count=len(rows), type=kind))
        return len(accessors)-1
    attrs = {
        'POSITION':attribute([(0,0,0),(1,0,0),(0,1,0)],'f',5126,'VEC3'),
        'NORMAL':attribute([(0,0,1)]*3,'f',5126,'VEC3'),
        'TEXCOORD_0':attribute([(0,0),(1,0),(0,1)],'f',5126,'VEC2'),
        'JOINTS_0':attribute([(0,0,0,0)]*3,'B',5121,'VEC4'),
        'WEIGHTS_0':attribute([(1,0,0,0)]*3,'f',5126,'VEC4'),
    }
    indices = attribute([(0,),(1,),(2,)],'H',5123,'SCALAR')
    doc = dict(nodes=[dict(mesh=0,skin=0),dict(name='root')],skins=[dict(joints=[1])],
               meshes=[dict(primitives=[dict(attributes=attrs,indices=indices)])],
               buffers=[dict(uri='mesh.bin',byteLength=len(raw))],bufferViews=views,accessors=accessors)
    (tmp_path/'mesh.bin').write_bytes(raw)
    path = tmp_path/'mesh.gltf'
    path.write_text(json.dumps(doc))
    return path, doc


def test_native_basis_winding_and_uv(tmp_path):
    path, _ = reference_file(tmp_path)
    mesh = load_reference(path)
    assert mesh['vertices'] == [(0,0,0),(100,0,0),(0,0,100)]
    assert mesh['normals'] == [(0,1,0)]*3
    assert mesh['faces'] == [(2,1,0)]
    assert mesh['uv'] == [(0,0),(1,0),(0,1)]
    assert mesh['weights'] == [{'root':1}]*3


@pytest.mark.parametrize('failure', ['transform','truncated','view_overrun','escape','nonfinite'])
def test_reject_unsafe_or_ambiguous_reference(tmp_path, failure):
    path, doc = reference_file(tmp_path)
    if failure == 'transform':
        doc['nodes'][0]['translation'] = [0,1,0]
    elif failure == 'truncated':
        doc['buffers'][0]['byteLength'] += 1
    elif failure == 'view_overrun':
        doc['accessors'][0]['count'] += 1
    elif failure == 'escape':
        doc['buffers'][0]['uri'] = '../outside.bin'
    else:
        data = bytearray((tmp_path/'mesh.bin').read_bytes())
        struct.pack_into('<f',data,0,math.nan)
        (tmp_path/'mesh.bin').write_bytes(data)
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        load_reference(path)


def test_barycentric_surface_and_weight_interpolation():
    assert barycentric((.25,.25,0),[(0,0,0),(1,0,0),(0,1,0)]) == [.5,.25,.25]
    weights = mix_weights({'neck':1}, {'head':.5,'neck':.5}, .5)
    assert weights == {'neck':.75,'head':.25}
    with pytest.raises(ValueError, match='Degenerate'):
        barycentric((0,0,0),[(0,0,0)]*3)


def test_weights_stay_within_mobile_influence_limit():
    weights = mix_weights({'a':.4,'b':.3,'c':.2,'d':.1},
                          {'e':.4,'f':.3,'g':.2,'h':.1}, .5)
    assert len(weights) == 4
    assert set(weights) == {'a','b','e','f'}
    assert sum(weights.values()) == pytest.approx(1)


@pytest.mark.parametrize('weights', [{}, {'a':-1,'b':2}, {'a':math.nan}, {'a':.2}])
def test_invalid_weights_fail_closed(weights):
    with pytest.raises(ValueError):
        mix_weights(weights, {'a':1}, .5)


def test_asymmetric_socket_needs_outward_correction_not_copied_gaze():
    # The accepted negative-X eye is slightly outside its aperture centre.
    # The opposite aperture is offset outward, so equal mirrored globe
    # positions would still look inward there. Matching world gaze is worse.
    x = socket_target_x(-3.05, [-4,-2,-3], [2,4.4,3.2])
    assert x == pytest.approx(3.26)
    assert x > 3.05
    assert socket_target_x(3.05, [2,4,3], [-4.4,-2,-3.2]) == pytest.approx(-3.26)


def test_higher_eyelid_requires_higher_pupil_despite_equal_world_height():
    z = socket_target_z(10, [9.6,10.6,10.1], [9.9,10.7,10.3])
    assert z == pytest.approx(10.22)
    assert (z-10.3)/.8 == pytest.approx((10-10.1)/1)


@pytest.mark.parametrize('opening', [[2,2,2], [2,4,5], [2,4,math.nan]])
def test_invalid_apertures_refused(opening):
    with pytest.raises(ValueError):
        socket_target_x(-3, [-4,-2,-3], opening)
