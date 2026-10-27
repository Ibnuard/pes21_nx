"""Independent cooked/source corner binding, including UV and duplicate errors."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_stadium_preserved_faces import match_source_triangles


@pytest.mark.parametrize('damage', ['none', 'missing', 'position', 'uv', 'duplicate'])
def test_round_trip_binds_positions_to_their_original_uvs(damage):
    triangle = np.array([[-1., 1., 45.], [1., 1., 45.], [1., 1., 45.2]])
    uv = np.array([[0., .2], [1., .2], [1., .8]])
    order = [2, 0, 1]
    cooked = [(triangle[order].copy(), uv[order].copy())]
    if damage == 'missing':
        cooked = []
    if damage == 'position':
        cooked[0][0][0, 1] += .0001
    if damage == 'uv':
        cooked[0][1][0, 1] += .01
    if damage == 'duplicate':
        cooked *= 2
    report = match_source_triangles([(triangle, uv)], cooked)
    assert report['passed'] == (damage == 'none')
    assert report['matched_triangles'] == (1 if damage == 'none' else 0)


def test_float_round_trip_across_a_spatial_cell_boundary_is_retained():
    triangle = np.array([[1.0004999, 1., 45.], [2., 1., 45.], [2., 1., 45.2]])
    uv = np.array([[0., .2], [1., .2], [1., .8]])
    actual = triangle.copy();actual[0, 0] = 1.0005001
    report = match_source_triangles([(triangle, uv)], [(actual, uv)])
    assert report['passed'] and report['maximum_position_error_m'] < .000001


@pytest.mark.parametrize('source_v', [0., 1./262144, .2])
def test_exporter_subnormal_representation_does_not_relax_other_uvs(source_v):
    triangle = np.array([[-1., 1., 45.], [1., 1., 45.], [1., 1., 45.2]])
    uv = np.array([[0., source_v], [1., .2], [1., .8]])
    actual = uv.copy();actual[0, 1] = 1./32768+source_v*.5
    report = match_source_triangles([(triangle, uv)], [(triangle, actual)])
    assert report['passed'] == (source_v < 1./16384)
    assert report['subnormal_uv_export_components'] == (1 if source_v < 1./16384 else 0)
