"""Palette conversion uses synthetic pixels; no proprietary fixture required."""
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from build_stadium_perimeter import WEIGHTS, linear, warm_apron


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


if __name__ == '__main__':
    unittest.main()
