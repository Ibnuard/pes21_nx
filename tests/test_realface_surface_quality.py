import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_surface_quality import audit, feature_locks, needs_refinement, unique_triangle_offsets, collapsed_skin_marker
from realface_hair_envelope import solid_scalp_mask


def test_discarded_reverse_faces_cannot_cancel_retained_surface_normals():
    indices = [0, 1, 2, 2, 1, 0, 0, 0, 1, 2, 1, 3]
    directions = np.array([[0, 0, 1]] * 3 + [[0, 0, -1]] * 6 + [[0, 1, 1]] * 3)
    retained = list(unique_triangle_offsets(indices))
    assert retained == [0, 9]
    normals = np.zeros((4, 3))
    for start in retained:
        for corner in range(3):
            normals[indices[start+corner]] += directions[start+corner]
    assert normals[0] == pytest.approx([0, 0, 1])
    assert np.all(normals[:, 2] > 0)
    with pytest.raises(ValueError, match='Incomplete triangle'):
        list(unique_triangle_offsets([0, 1]))


def test_collapsed_marker_filter_preserves_visible_or_differently_skinned_faces():
    weights=[((3,1.),)]*3
    collapsed=np.array([[0,0,0],[.000002,0,0],[0,.000002,0]])+[1.,5.,171.]
    assert collapsed_skin_marker(collapsed,weights)
    assert not collapsed_skin_marker([[0,0,0],[.001,0,0],[0,.001,0]],weights)
    assert not collapsed_skin_marker(collapsed,[weights[0],weights[0],((4,1.),)])


def test_projection_detects_uv_stretch_on_an_unchanged_flat_surface():
    # Geometry stays in precisely the same plane after removing the centre.
    # Its non-affine UV is the only feature a positional error test would miss.
    p = [[-6, 10, 158], [6, 10, 158], [6, 10, 175], [-6, 10, 175], [0, 10, 166]]
    uv = [[0, 0], [1, 0], [1, 1], [0, 1], [.1, .8]]
    original = [0, 1, 4, 1, 2, 4, 2, 3, 4, 3, 0, 4]
    request = dict(positions=p, uv=uv, indices=original)
    unchanged = audit(request, original, size=40)
    assert unchanged['mouth_uv_p95_max'] == pytest.approx(0)
    stretched = audit(request, [0, 1, 2, 0, 2, 3], size=40)
    assert needs_refinement(stretched)
    assert stretched['mouth_uv_p95_max'] > 10
    assert max(v['regions']['face']['depth_p95_cm'] for v in stretched['views']) < 1e-10


def test_feature_policy_keeps_neck_boundary_but_frees_interior_budget():
    p = np.array([[x, 10, z] for z in [149, 152, 154, 158, 164, 170, 175] for x in [-3, 0, 3]])
    # A forward nose anchor defines the lower mouth window.
    p[16, 1] = 11
    tri = []
    for row in range(6):
        for col in range(2):
            a = row*3+col
            tri += [[a, a+1, a+3], [a+1, a+4, a+3]]
    uv = np.tile([.5, .5], (len(p), 1))
    locks = (p[:, 2] < 155).astype(int)
    texture = np.ones((8, 8, 4))
    actual, proof = feature_locks(p, tri, uv, locks, texture)
    assert actual[0] == actual[1] == actual[2] == 1
    assert actual[3] == actual[5] == 1
    assert actual[4] == actual[7] == 0
    assert proof['neck_boundary_vertices_locked'] < proof['neck_vertices_locked_before']
    assert proof['mouth_crease_anchors'] == 0


def test_solid_scalp_fills_strand_gaps_without_extending_the_hairline():
    alpha = np.zeros((10, 8))
    alpha[2:6, 1:7] = 1
    alpha[3:5, 3:5] = 0
    alpha[7, 3] = 1
    solid = solid_scalp_mask(alpha)
    assert solid[:6, 1:7].all()
    assert solid[:8, 3].all()
    assert not solid[8:].any()
    assert not solid[:, [0, 7]].any()
    assert solid_scalp_mask(solid) == pytest.approx(solid)
    with pytest.raises(ValueError):
        solid_scalp_mask(np.zeros((10, 8)))
