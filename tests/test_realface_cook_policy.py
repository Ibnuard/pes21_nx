import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_cook_policy import collapsed_triangle


def test_only_fully_collapsed_triangles_are_eligible_for_audited_removal():
    assert collapsed_triangle([[1, 2, 170], [1.000002, 2, 170], [1, 2.000003, 170]])
    assert not collapsed_triangle([[1, 2, 170], [1.000002, 2, 170], [1, 2.5, 170]])
    assert not collapsed_triangle([[0, 0, 0], [1, 0, 0], [2, 0, 0]])
    assert not collapsed_triangle([[0, 0, 0], [.00001, 0, 0], [0, .00001, 0]])


def test_invalid_corners_cannot_qualify_for_removal():
    for points in ([[0, 0, 0]] * 2, [[0, 0]] * 3,
                   [[0, 0, 0], [0, 0, 0], [float('nan'), 0, 0]]):
        with pytest.raises(ValueError, match='finite triangle'):
            collapsed_triangle(points)
