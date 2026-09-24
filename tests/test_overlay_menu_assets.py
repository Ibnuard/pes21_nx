"""Regression checks for the embedded custom-menu PNG upload path."""

from pathlib import Path
import re
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (ROOT / "source/overlay.c").read_text(encoding="utf-8")


class OverlayMenuAssetsTests(unittest.TestCase):
    def test_cup_ornament_fits_decoder_pixel_budget(self):
        png = (ROOT / "data/cup_hub_header_ornament.bin").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(png[12:16], b"IHDR")
        width, height = struct.unpack_from(">II", png, 16)
        self.assertEqual(png[25], 6)  # RGBA: transparent header background.
        self.assertGreaterEqual(width, 1024)
        self.assertLessEqual(max(width, height), 4096)
        self.assertLessEqual(width * height, 2048 * 2048)
        decoder = re.search(
            r"static int decode_png_memory\(.*?\n\}", OVERLAY, re.S
        ).group(0)
        self.assertIn("image.width > 4096u", decoder)
        self.assertIn("image.height > 4096u", decoder)
        self.assertIn(
            "(uint64_t)image.width * image.height > 2048u * 2048u", decoder
        )

    def test_failed_optional_asset_does_not_retry_all_uploads_per_frame(self):
        prepare = re.search(
            r"static void prepare_main_menu_assets\(int active\) \{.*?\n\}",
            OVERLAY,
            re.S,
        ).group(0)
        self.assertIn("if (!active || gl.main_menu_uploaded)", prepare)
        self.assertIn("gl.main_menu_uploaded = 1;", prepare)
        self.assertNotRegex(
            prepare, r"if \(uploaded\)\s*gl\.main_menu_uploaded = 1;"
        )
        self.assertIn("gl.cup_hub_header_ornament_uploaded =", prepare)
        self.assertIn("if (gl.cup_hub_header_ornament_uploaded)", OVERLAY)


if __name__ == "__main__":
    unittest.main()
