import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_cook_policy import collapsed_triangle, audited_triangle_drop


def test_only_fully_collapsed_triangles_are_eligible_for_audited_removal():
    assert collapsed_triangle([[1, 2, 170], [1.000002, 2, 170], [1, 2.000003, 170]])
    assert not collapsed_triangle([[1, 2, 170], [1.000002, 2, 170], [1, 2.5, 170]])
    assert not collapsed_triangle([[0, 0, 0], [1, 0, 0], [2, 0, 0]])
    assert not collapsed_triangle([[0, 0, 0], [.00001, 0, 0], [0, .00001, 0]])
    assert collapsed_triangle([[1,2,170], [1,2,170], [1,7,170]])
    assert not collapsed_triangle([[1,2,170], [1.00000001,2,170], [1,7,170]])


def test_invalid_corners_cannot_qualify_for_removal():
    for points in ([[0, 0, 0]] * 2, [[0, 0]] * 3,
                   [[0, 0, 0], [0, 0, 0], [float('nan'), 0, 0]]):
        with pytest.raises(ValueError, match='finite triangle'):
            collapsed_triangle(points)


def test_retained_collapses_are_valid_but_unexplained_drops_are_not():
    assert audited_triangle_drop(5066, 5066, 2) == 0
    assert audited_triangle_drop(5066, 5064, 2) == 2
    for counts in ((7671, 7669, 0), (5066, 5065, 2), (10, 11, 0), (10, 1, 11)):
        with pytest.raises(ValueError):
            audited_triangle_drop(*counts)
