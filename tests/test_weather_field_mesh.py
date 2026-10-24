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
    def test_world_field_spans_both_pitch_halves_without_more_active_geometry(self):
        for snow in (False,True):
            vertices,uv,faces=field(snow=snow,light=True,world=True)
            self.assertEqual(len(vertices),2048)
            self.assertEqual(len(faces),1024)
            centers=[tuple(sum(v[j] for v in vertices[i:i+8])/8 for j in range(3)) for i in range(0,len(vertices),8)]
            self.assertLess(min(v[0] for v in centers),-5000)
            self.assertGreater(max(v[0] for v in centers),5000)
            self.assertLess(min(v[1] for v in centers),-3200)
            self.assertGreater(max(v[1] for v in centers),3200)
            quadrants=[sum((v[0]>0)==x and (v[1]>0)==y for v in centers) for x in (False,True) for y in (False,True)]
            self.assertTrue(all(n>40 for n in quadrants))
            self.assertEqual((vertices,uv,faces),field(snow=snow,light=True,world=True))
        with self.assertRaises(ValueError):field(world=True)

    def test_light_rain_is_a_bounded_thin_field(self):
        vertices,uv,faces=field(light=True)
        self.assertEqual(len(vertices),2048)
        self.assertEqual(len(faces),1024)
        self.assertEqual(field(light=True),(vertices,uv,faces))
        for i in range(0,len(vertices),8):
            drop=vertices[i:i+8]
            self.assertAlmostEqual(max(v[2] for v in drop)-min(v[2] for v in drop),32)
            self.assertLess(max(v[0] for v in drop)-min(v[0] for v in drop),6)

    def test_light_snow_is_small_slow_and_wraps_without_stretching(self):
        vertices,uv,faces=field(snow=True,light=True)
        self.assertEqual(len(vertices),2048)
        self.assertEqual(len(faces),1024)
        self.assertEqual(field(snow=True,light=True),(vertices,uv,faces))
        for i in range(0,len(vertices),8):
            flake=vertices[i:i+8]
            self.assertAlmostEqual(max(v[2] for v in flake)-min(v[2] for v in flake),6)
            u=[struct.unpack('e',struct.pack('e',t[0]))[0] for t in uv[i:i+8]]
            phases={(math.floor(x)+.5)/PHASES for x in u}
            self.assertEqual(len(phases),1)
            phase=phases.pop()
            for time in (0,.37,11.99,12.01,23.99,24.37):
                fall=((phase-time/12)%1-phase)*HEIGHT
                z=[v[2]+fall for v in flake]
                self.assertGreater(min(z),-80)
                self.assertLess(max(z),HEIGHT+80)
                self.assertAlmostEqual(max(z)-min(z),6)
            self.assertAlmostEqual((phase-.37/12)%1,(phase-24.37/12)%1)

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
