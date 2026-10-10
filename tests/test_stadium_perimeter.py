"""Palette and concourse conversion use synthetic data, no game fixtures."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_stadium_perimeter import WEIGHTS, linear, warm_apron

from tools.stadium_perimeter import outside_field, perimeter_meshes


class PerimeterTests(unittest.TestCase):
    def test_warm_palette_preserves_grain_order_alpha_and_attenuates_light(self):
        pixels = np.array([[[g//2, g, g//4, i*17] for i, g in enumerate(range(24, 216, 12))]], dtype=np.uint8)
        result = np.asarray(warm_apron(Image.fromarray(pixels)))
        np.testing.assert_array_equal(result[:, :, 3], pixels[:, :, 3])
        self.assertTrue(np.all(result[:, :, 0] >= result[:, :, 1]))
        self.assertTrue(np.all(result[:, :, 1] > result[:, :, 2]))
        before = linear(pixels[:, :, :3]) @ WEIGHTS
        after = linear(result[:, :, :3]) @ WEIGHTS
        np.testing.assert_allclose(after / before, .8, atol=.025)
        self.assertTrue(np.all(np.diff(after[0]) > 0))
        self.assertEqual(warm_apron(Image.new('RGBA', (4, 4), (0, 0, 0, 73))).getpixel((0, 0)), (0, 0, 0, 73))


def test_field_separation_rejects_triangles_crossing_the_pitch():
    assert outside_field([(54, 0, -4), (54, 0, 4), (62, 0, 4)])
    assert outside_field([(-12, 0, 36), (12, 0, 36), (12, 0, 40)])
    # All vertices outside is insufficient when the interior crosses the pitch.
    assert not outside_field([(-60, 0, -40), (60, 0, -40), (0, 0, 40)])
    assert not outside_field([(53, 0, 0), (56, 0, 2), (56, 0, -2)])


def test_only_shallow_concrete_surfaces_are_restored():
    def mesh(texture, height):
        vertices = [NS(position=NS(x=x, y=height, z=z))
                    for x, z in ((54, -4), (54, 4), (62, 4))]
        return NS(vertices=vertices, faces=[NS(vertices=vertices)],
                  materialInstance=NS(textures=[('Base_Tex_SRGB', NS(filename=texture))]))
    floor = mesh('st004_cncr001_bsm.tga', 0)
    model = NS(meshes=[floor, mesh('st004_turf001_bsm.tga', 0),
                      mesh('st004_cncr001_bsm.tga', 4)])
    selected = perimeter_meshes(model)
    assert len(selected) == 1 and selected[0] is not floor
    assert selected[0].faces == floor.faces
    assert len(model.meshes) == 3


if __name__ == '__main__':
    unittest.main()
