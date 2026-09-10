"""Independent validation of the generated square-scoreboard asset."""
from pathlib import Path
import struct
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from afp_score_layout import read_movies, placements
from afp_texture_patch import read_atlas
from build_efootball10_scoreboard_v2 import unpack_wesys, region_bounds


class SquareScoreboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT / 'local-debug/scoreboard-square-v2'
        if not (folder / 'game2dPes.bin').exists():
            raise unittest.SkipTest('Generate the local asset first')
        cls.before = unpack_wesys((folder / 'game2d-original.bin').read_bytes())
        cls.after = unpack_wesys((folder / 'game2dPes.bin').read_bytes())

    def test_only_verified_transform_bytes_changed_in_movie(self):
        before = read_movies(self.before)
        after = read_movies(self.after)
        self.assertEqual(len(before), len(after))
        for a, b in zip(before, after):
            self.assertEqual(a.name, b.name)
            if a.name != 'game2d_score':
                self.assertEqual(a.data, b.data)
                continue
            permitted = set()
            aa, bb = placements(a.data), placements(b.data)
            self.assertEqual(len(aa), len(bb))
            for r, s in zip(aa, bb):
                if r['parent'] == 28 and 'translate' in r:
                    permitted.update(range(r['translate_offset'], r['translate_offset'] + 8))
                    self.assertAlmostEqual(s['translate'][1] - r['translate'][1], 20)
                    if r['depth'] in (77, 78):
                        self.assertAlmostEqual(s['translate'][0] - r['translate'][0], 20)
            self.assertEqual(len(a.data), len(b.data))
            self.assertTrue(all(x == y or i in permitted for i, (x, y) in enumerate(zip(a.data, b.data))))

    def test_square_cells_and_solid_accent_corners(self):
        atlas, regions, _ = read_atlas(self.after)
        w, h = struct.unpack_from('>HH', atlas, 16)
        px = np.frombuffer(atlas[64:], np.uint8).reshape(h, w, 4)
        for r in regions:
            l, t, right, b = region_bounds(r)
            if r['name'] == 'game2dPes-score-plateMain':
                self.assertEqual((right-l, b-t), (404, 48))
                bar = px[t:b, l:right]
                self.assertTrue((bar[:, 78:125, 1:] == (230, 230, 0)).all())
                self.assertTrue((bar[:, 125:127, 1:] == (0, 0, 100)).all())
                self.assertTrue((bar[:, 127:174, 1:] == (230, 230, 0)).all())
            if r['name'].startswith('game2dPes-score-plateTeamColor-'):
                self.assertTrue((px[t:b, l:right, 0] == 255).all())


if __name__ == '__main__':
    unittest.main()
