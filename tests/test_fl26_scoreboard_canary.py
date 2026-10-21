"""Host field/atlas safety checks; optional owned fixtures are never restored."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import shutil
import subprocess
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_fl26_scoreboard_canary as canary
from afp_score_layout import read_movies, placements, strings
from afp_texture_patch import lzss_encode
from fl26_scoreboard_crop import decode_ranges, crop_rgba, MAX_CROP_BYTES


def texture_container(pixels, width, height, pixel_format="11221015"):
    header = bytearray(64)
    header[:4] = b"TXDT"
    struct.pack_into(">HH", header, 16, width, height)
    header[20:24] = bytes.fromhex(pixel_format)
    raw = bytes(header) + pixels
    packed = lzss_encode(raw, candidate_limit=4)
    data = bytearray(120)
    data[:4] = b"TXP2"
    struct.pack_into(">III", data, 20, 4, 1, 108)
    struct.pack_into(">III", data, 108, 0, len(packed) + 8, 120)
    data += struct.pack(">II", len(raw), len(packed)) + packed
    # The declared envelope deliberately excludes the referenced pixel tail.
    struct.pack_into(">I", data, 12, 120)
    return bytes(data)


class SparseAtlasSafety(unittest.TestCase):
    def test_sparse_window_matches_selected_repeated_and_overlapping_lzss_data(self):
        data = (b"abcdef" * 3000 + bytes(range(255))) * 3
        ranges = [(0, 7), (4090, 4105), (18000, 18040), (len(data) - 40, len(data))]
        packed = lzss_encode(data, candidate_limit=8)
        self.assertEqual(decode_ranges(packed, len(data), ranges),
                         b"".join(data[a:b] for a, b in ranges))

    def test_empty_overlapping_outside_and_oversized_selection_fail(self):
        for ranges in ([], [(2, 1)], [(0, 8), (7, 9)], [(0, 11)]):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                decode_ranges(b"", 10, ranges)
        with self.assertRaisesRegex(ValueError, "pixel budget"):
            decode_ranges(b"", MAX_CROP_BYTES + 1, [(0, MAX_CROP_BYTES + 1)])

    def test_truncated_control_literal_and_match_fail(self):
        for data in (b"", b"\1", b"\0\1"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_ranges(data, 4, [(0, 4)])

    def test_crop_resolves_complete_payload_even_beyond_declared_envelope(self):
        pixels = bytes((255, 12, 34, 56, 128, 70, 80, 90,
                        64, 20, 30, 40, 255, 100, 110, 120))
        image, report = crop_rgba(texture_container(pixels, 2, 2), 0, (1, 0, 2, 2))
        self.assertEqual(list(image.getdata()), [(70, 80, 90, 128), (100, 110, 120, 255)])
        self.assertEqual(report["retained_pixel_bytes"], 8)
        self.assertFalse(report["full_atlas_allocated"])
        self.assertEqual(report["decoder_window_bytes"], 4096)

    def test_unsupported_pixel_format_and_crop_bounds_fail(self):
        for data, rect in ((texture_container(b"\0" * 16, 2, 2, "1122101a"), (0, 0, 1, 1)),
                           (texture_container(b"\0" * 16, 2, 2), (-1, 0, 1, 1))):
            with self.assertRaises(ValueError):
                crop_rgba(data, 0, rect)


class CorrectedReferenceGeometry(unittest.TestCase):
    def test_full_rectangular_panel_uses_white_mark_red_top_and_white_lower_left(self):
        source = Image.new("RGBA", (240, 126), (0, 1, 26, 255))
        for x in range(25, 50):
            for y in range(8, 52):
                source.putpixel((x, y), (255, 65, 65, 255))
        panel, report = canary.make_panel(source)
        self.assertEqual(panel.size, (246, 132))
        self.assertEqual(panel.getextrema()[3], (255, 255))
        self.assertEqual(panel.getpixel((2, 2)), (*canary.RED, 255))
        self.assertEqual(panel.getpixel((52, 33)), (255, 255, 255, 255))
        self.assertEqual(panel.getpixel((2, 131)), (255, 255, 255, 255))
        self.assertEqual(panel.getpixel((120, 131)), (*canary.NAVY, 255))
        self.assertEqual(panel.getpixel((240, 131)), (255, 255, 255, 255))
        self.assertFalse(report["top_clock"])
        self.assertFalse(report["stepped_notch"])

    def test_missing_owned_league_mark_fails(self):
        with self.assertRaisesRegex(ValueError, "mask is missing"):
            canary.make_panel(Image.new("RGBA", (240, 126), "navy"))


class OptionalOwnedMobileFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / "local-debug/scoreboard-v62/mobile.bin"
        if not path.is_file():
            raise unittest.SkipTest("requires ignored owned Mobile UI fixture regenerated under local-debug/scoreboard-v62")
        cls.data = path.read_bytes()
        if hashlib.sha256(cls.data).hexdigest() != canary.MOBILE_SHA256:
            raise unittest.SkipTest("ignored Mobile fixture differs from pinned canary baseline")
        cls.score = next(m for m in read_movies(cls.data) if m.name == "game2d_score")

    def test_canary_changes_only_declared_verified_fields(self):
        modified, report = canary.patch_movie(self.score.data)
        allowed = set()
        for edit in report["edits"]:
            before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
            start = edit["offset"]
            self.assertEqual(self.score.data[start:start + len(before)], before)
            self.assertEqual(modified[start:start + len(after)], after)
            allowed.update(range(start, start + len(after)))
        self.assertEqual(len(modified), len(self.score.data))
        self.assertGreater(len(allowed), 500)
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in
                            enumerate(zip(self.score.data, modified))))
        self.assertEqual(strings(modified), strings(self.score.data))
        before, after = placements(self.score.data), placements(modified)
        for a, b in zip(before, after):
            for field in ("parent", "depth", "frame", "flags", "source", "name", "object_id"):
                self.assertEqual(a.get(field), b.get(field))
        final = {r["name"]: r for r in after if r["parent"] == 28 and r["frame"] == 0 and "name" in r}
        self.assertEqual(final["teamName_home"]["translate"][0], final["teamName_away"]["translate"][0])
        self.assertEqual(final["teamName_away"]["translate"][1] - final["teamName_home"]["translate"][1], 66)
        self.assertEqual(final["time_set"]["translate"], final["losstime_progress_set"]["translate"])
        geometry = report["field_geometry"]
        self.assertTrue(geometry["fields_inside_separate_cells"])
        self.assertEqual(geometry["clock_minute_states"], [1, 2, 3])

    def test_native_clock_glyphs_cannot_overflow_into_name_column(self):
        modified, _ = canary.patch_movie(self.score.data)
        rows = placements(modified)
        for row in rows:
            if row["parent"] == 28 and row["depth"] == 77 and row["frame"] == 0:
                row["translate"] = (100, 103)
        with self.assertRaisesRegex(ValueError, "leaves its reference cell"):
            canary.verify_field_geometry(rows)

    def test_repack_rejects_live_region_overlap(self):
        previous = canary.ATLAS_DESTINATION
        try:
            canary.ATLAS_DESTINATION = (0, 0)
            with self.assertRaisesRegex(ValueError, "overlaps"):
                canary.repack_plate(self.data, Image.new("RGBA", (246, 132)))
        finally:
            canary.ATLAS_DESTINATION = previous

    def test_built_canary_reports_unverified_and_preserves_other_movies(self):
        output = ROOT / "local-debug/scoreboard-v62/spain-canary"
        if not (output / "validation.json").is_file():
            self.skipTest("requires the separate ignored canary build")
        report = json.loads((output / "validation.json").read_text())
        packet = (output / "c11-spain-canary.nxsb").read_bytes()
        self.assertFalse(report["device_validated"])
        self.assertFalse(report["production_mutated"])
        self.assertFalse(report["native_timeline"]["pc_animation_imported"])
        self.assertLessEqual(len(packet), 2_000_000)
        self.assertEqual(hashlib.sha256(packet).hexdigest(), report["packet_sha256"])
        self.assertEqual(report["design"]["reference_sha256"], canary.DESIGN_REFERENCE_SHA256)
        self.assertEqual(report["design"]["column_edges"], [0, 105, 180, 246])
        self.assertTrue(report["native_timeline"]["field_geometry"]["fields_inside_separate_cells"])
        for before, after in zip(read_movies(self.data), read_movies((output / "game2dPes-spain-canary.bin").read_bytes())):
            self.assertEqual(before.info, after.info)
            if before.name != "game2d_score":
                self.assertEqual(before.data, after.data)

    def test_actual_packet_is_admitted_by_current_c_runtime_parser(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        packet = ROOT / "local-debug/scoreboard-v62/spain-canary/c11-spain-canary.nxsb"
        if not compiler or not packet.is_file():
            self.skipTest("requires a host C compiler and the ignored separate Spain canary")
        mobile = ROOT / "local-debug/scoreboard-v62/mobile.bin"
        with tempfile.TemporaryDirectory(prefix="payload-host-", dir=mobile.parent) as temp:
            executable = Path(temp) / "scoreboard-payload-test.exe"
            subprocess.run([compiler, "-std=c11", (ROOT / "tests/test_fl26_scoreboard_payload.c").as_posix(),
                            "-o", executable.as_posix()], check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable), mobile.as_posix(), packet.as_posix()],
                                    check=True, capture_output=True, text=True)
        self.assertIn(f"current scoreboard_payload admits c11: {packet.stat().st_size - 32} target bytes", result.stdout)


if __name__ == "__main__":
    unittest.main()
