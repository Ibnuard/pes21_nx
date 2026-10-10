from pathlib import Path
import math
import struct
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_crowd import read_areas, crowd_rows


def fixture():
    header = struct.pack('<14I', 1, 1, 56, *([0]*11))
    section = struct.pack('<2I6fI', 65536, 64, -10, 1, 40, 10, 8, 60, 1)
    points = (-10,1,40, -10,8,60, 10,8,60, 10,1,40)
    record = struct.pack('<I23f', 0, 2.3,.8,.8, *points, *([0]*8))
    return header+section+record


class CrowdTests(unittest.TestCase):
    def test_rows_follow_seating_rake_with_bounded_repeating_uvs(self):
        areas = read_areas(fixture())
        vertices, faces, uvs = crowd_rows(areas)
        self.assertEqual(len(faces), 24)
        self.assertEqual(len(vertices), 96)
        for face in faces:
            a,b,c,d = (vertices[i] for i in face)
            self.assertTrue(40<a[2]<60 and 1<a[1]<8)
            self.assertAlmostEqual(c[1]-b[1], 1.55)
            self.assertAlmostEqual(d[1]-a[1], 1.55)
            self.assertAlmostEqual(uvs[face[1]][0]-uvs[face[0]][0], 20/(8*1.55))
        self.assertTrue(all(math.isfinite(x) for v in vertices for x in v))

    def test_rejects_corrupt_sections_and_unbounded_density(self):
        good = fixture()
        for offset, value in [(0,2), (8,2000), (60,0), (88,999)]:
            bad = bytearray(good)
            struct.pack_into('<I',bad,offset,value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                read_areas(bad)
        with self.assertRaises(ValueError):
            read_areas(good[:-1])
        bad = bytearray(good)
        struct.pack_into('<f',bad,108,float('nan'))
        with self.assertRaises(ValueError):
            read_areas(bad)
        with self.assertRaises(ValueError):
            crowd_rows(read_areas(good),max_rows=2)
