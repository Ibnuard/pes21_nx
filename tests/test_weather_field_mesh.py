"""Budget, phase encoding and bounds of authored precipitation; no game input."""
import math
from pathlib import Path
import sys
import struct
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from weather_field_mesh import field, write, HEIGHT, PHASES


class WeatherFieldTests(unittest.TestCase):
    def test_budget_and_rigid_motion_inside_bounds(self):
        for snow, count in ((False, 768), (True, 640)):
            with self.subTest(snow=snow):
                vertices, uv, faces = field(snow)
                self.assertEqual(len(vertices), count * 8)
                self.assertEqual(len(faces), count * 4)
                self.assertLessEqual(len(faces), 3072)
                self.assertTrue(all(0 <= i < len(vertices) for f in faces for i in f))
                period = 6 if snow else 1
                for i in range(0, len(vertices), 8):
                    # Quantize as the imported half-float UV buffer does. A
                    # drop's corners must retain one phase at all sample times.
                    u = [struct.unpack('e', struct.pack('e', t[0]))[0] for t in uv[i:i + 8]]
                    phases = {(math.floor(x) + .5) / PHASES for x in u}
                    self.assertEqual(len(phases), 1)
                    phase = phases.pop()
                    center_z = sum(v[2] for v in vertices[i:i + 8]) / 8
                    self.assertAlmostEqual(center_z, phase * HEIGHT)
                    for time in (0, .37, 1.9, 5.7, 23.99, 24.37):
                        fall = ((phase - time / period) % 1 - phase) * HEIGHT
                        z = [v[2] + fall for v in vertices[i:i + 8]]
                        self.assertGreater(min(z), -80)
                        self.assertLess(max(z), HEIGHT + 80)
                        # Rigid quads cannot stretch across the wrap plane.
                        self.assertAlmostEqual(max(z) - min(z), 18 if snow else 72)
                    self.assertAlmostEqual((phase - .37 / period) % 1,
                                           (phase - 24.37 / period) % 1)

    def test_reproducible_obj_has_no_external_material_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a.obj', Path(temp) / 'b.obj'
            self.assertEqual(write(a), write(b))
            self.assertEqual(a.read_bytes(), b.read_bytes())
            self.assertNotIn('mtllib', a.read_text())
