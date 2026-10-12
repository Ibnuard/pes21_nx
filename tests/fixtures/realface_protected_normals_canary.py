"""Blender regression: degenerate shading cannot excuse visible mesh changes."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from blender_fit_eye_sockets import verify_protected
from validate_realface_fit import protected_normal_drift
from mathutils import Vector


row = dict(points=np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]),
           uv=[[(0., 0.), (1., 0.), (0., 1.)]], polygons=[(0, 1, 2)],
           weights=[{'sk_head': 1.}] * 3, materials=['skin'],
           normals=[(0., 0., 1.)] * 6, degenerate_normal_corners={3, 4, 5})
before = {'skin': row}
after = deepcopy(before)
after['skin']['normals'][3] = (0., 1., 0.)
assert verify_protected(before, after)[0]['normal_drift'] == 0


def rejects(change):
    altered = deepcopy(after)
    change(altered['skin'])
    try:
        verify_protected(before, altered)
    except ValueError:
        return
    raise AssertionError('Protected surface mutation was accepted')


rejects(lambda r: r['degenerate_normal_corners'].remove(3))
rejects(lambda r: r['normals'].__setitem__(0, (0., 1., 0.)))
rejects(lambda r: r['points'].__setitem__((0, 0), .01))
rejects(lambda r: r['weights'].__setitem__(0, {'sk_neck': 1.}))
rejects(lambda r: r['uv'][0].__setitem__(0, (.1, .1)))
rejects(lambda r: r['polygons'].__setitem__(0, (0, 2, 1)))

bad_source = deepcopy(before)
bad_source['skin']['normals'][0] = (0., 0., 0.)
try:
    verify_protected(bad_source, after)
except ValueError as error:
    assert 'nondegenerate' in str(error)
else:
    raise AssertionError('Undefined visible shading was accepted')
print('Protected normal audit: degenerate-only shading allowed; visible surface mutations rejected')

old=dict(normals=[Vector((0,0,1))]*6,loops=[0,1,2,3,4,5],degenerate_corners={3,4,5})
new=deepcopy(old);new['normals'][3]=Vector((0,1,0))
assert protected_normal_drift(old,new,set(range(6)))==0
new['degenerate_corners'].remove(3)
assert protected_normal_drift(old,new,set(range(6)))>1
new=deepcopy(old);new['normals'][0]=Vector((0,1,0))
assert protected_normal_drift(old,new,set(range(6)))>1
print('Neck round-trip: same degenerate-only exception; visible shading remains protected')
