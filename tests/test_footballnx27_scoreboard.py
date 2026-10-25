"""Own-brand skin: retain native bindings and unrelated game/UI bytes."""
from pathlib import Path
import struct
import sys
import unittest

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_footballnx27_scoreboard as nx
from afp_score_layout import placements, read_movies
from afp_texture_patch import read_atlas
from build_efootball10_scoreboard_v2 import region_bounds


class InputGuardTests(unittest.TestCase):
    def test_rejects_unknown_mobile_source(self):
        with self.assertRaisesRegex(ValueError, "pinned"):
            nx.build(b"different Mobile revision", Image.new("RGBA", (1, 1)))


class NativeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = ROOT / "local-debug/scoreboard-v62/mobile.bin"
        if not fixture.is_file():
            raise unittest.SkipTest("requires optional ignored accepted Mobile UI fixture")
        cls.before = fixture.read_bytes()
        cls.after, cls.packet, cls.plate, cls.report = nx.build(
            cls.before, Image.open(ROOT / "data/main_menu_brand.bin"))

    def test_packet_binds_both_source_and_target(self):
        magic, source_size, size, source_hash, target_hash = nx.HEADER.unpack_from(self.packet)
        self.assertEqual(magic, b"NXSB01\0\0")
        self.assertEqual((source_size, source_hash), (len(nx.txp(self.before)), nx.checksum(nx.txp(self.before))))
        self.assertEqual((size, target_hash), (len(self.packet) - 32, nx.checksum(self.packet[32:])))

    def test_native_inventory_and_unrelated_movies_are_exact(self):
        for old, new in zip(read_movies(self.before), read_movies(self.after)):
            self.assertEqual((old.name, old.info, old.size), (new.name, new.info, new.size))
            if old.name != "game2d_score":
                self.assertEqual(old.data, new.data)
        self.assertTrue(self.report["native_movie"]["scripts_labels_frames_bindings_identical"])

    def test_rgb_only_clock_recolour_preserves_native_glyph_coverage(self):
        atlas, regions, _ = read_atlas(self.before)
        other, after_regions, _ = read_atlas(self.after)
        width, height = struct.unpack_from(">HH", atlas, 16)
        a = np.frombuffer(atlas[64:], np.uint8).reshape(height, width, 4)
        b = np.frombuffer(other[64:], np.uint8).reshape(height, width, 4)
        for old, new in zip(regions, after_regions):
            if old["name"].startswith("game2dPes-score-plateTeamColor-"):
                l, t, r, bottom = region_bounds(new)
                self.assertEqual((r-l, bottom-t), (4, 14))
                continue
            if old["name"] == "game2dPes-score-plateTime":
                l, t, r, bottom = region_bounds(new)
                self.assertEqual((r-l, bottom-t), (60, 32))
                continue
            self.assertEqual(old, new)
            l, t, r, bottom = region_bounds(old)
            if old["name"].startswith("MatchPlate-texFont-"):
                np.testing.assert_array_equal(a[t:bottom, l:r, 0], b[t:bottom, l:r, 0])
            elif old["name"] != "game2dPes-score-plateMain":
                np.testing.assert_array_equal(a[t:bottom, l:r], b[t:bottom, l:r])

    def test_native_score_and_name_opacity_fades_are_exact(self):
        old = placements(next(m.data for m in read_movies(self.before) if m.name == "game2d_score"))
        new = placements(next(m.data for m in read_movies(self.after) if m.name == "game2d_score"))
        for a, b in zip(old, new):
            self.assertEqual((a["frame"], a["parent"], a["depth"], a.get("name")),
                             (b["frame"], b["parent"], b["depth"], b.get("name")))
            if a["parent"] == 28 and a["depth"] in nx.CELLS and "mult8" in a:
                self.assertEqual(int(a["mult8"][0]) & 255, int(b["mult8"][0]) & 255)
        self.assertEqual(self.report["native_movie"]["clock_minute_states"], [1, 2, 3])
        self.assertEqual(self.report["native_movie"]["kit_bounds"],
                         [(8, 30, 12, 58), (244, 30, 248, 58)])

    def test_added_time_plate_gives_native_plus_glyph_room(self):
        rows = placements(next(m.data for m in read_movies(self.after) if m.name == "game2d_score"))
        initial = {(r["parent"], r["depth"]): r for r in rows if r["frame"] == 0}
        root = initial[(28, 56)]["translate"]
        image = initial[(22, 1)]["translate"]
        self.assertEqual(tuple(a+b for a, b in zip(root, image)), nx.ADDED[:2])
        contents = initial[(24, 3)]["translate"]
        plus = initial[(23, 1)]["translate"]
        left, top = (a+b+c for a, b, c in zip(root, contents, plus))
        self.assertEqual((left, top), (263, 78))
        self.assertGreaterEqual(top - nx.ADDED[1], 4)
        self.assertGreaterEqual(nx.ADDED[3] - (top + 24), 4)
        self.assertEqual(self.report["conditional_plate_pixels"], [60, 32])


if __name__ == "__main__":
    unittest.main()
