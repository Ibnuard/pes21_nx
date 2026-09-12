"""Regression guards for the full-page custom main menu."""

from pathlib import Path
import re
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class CustomMainMenuTests(unittest.TestCase):
    def test_vertical_order_preserves_native_actions(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        self.assertRegex(
            hooks,
            r"native_to_visual\[4\]\s*=\s*\{0,\s*3,\s*1,\s*2\}",
        )
        self.assertRegex(
            hooks,
            r"visual_to_native\[4\]\s*=\s*\{0,\s*2,\s*3,\s*1\}",
        )
        self.assertIn("main_menu_visual_to_native(row)", hooks)
        self.assertIn("main_menu_native_to_visual(main_menu_focus_index)", hooks)

    def test_overlay_owns_full_frame_and_crossfades_portraits(self):
        overlay = (ROOT / "source/overlay.c").read_text(encoding="utf-8")
        self.assertIn("const int custom_main_menu =", overlay)
        self.assertIn("emit_image_rect(0, 0, screen_width, screen_height", overlay)
        self.assertIn("main_menu_background_tex", overlay)
        self.assertIn("main_menu_portrait_tex[previous]", overlay)
        self.assertIn("main_menu_portrait_tex[current]", overlay)
        self.assertIn("220000000.0f", overlay)
        self.assertIn('"EXHIBITION", "2 PLAYER", "SETTINGS", "CREDITS"', overlay)
        self.assertIn("EFOOTBALL_FONT_STENCIL", overlay)
        self.assertIn("main_menu_brand_tex", overlay)
        self.assertIn("card_x + card_w - 0.022f * screen_width", overlay)
        self.assertIn("1.0f, 0.91f, 0.02f, focus_amount", overlay)
        self.assertIn("main_menu_row_focus_amount", overlay)

    def test_embedded_png_payloads_exist_and_icons_have_alpha(self):
        names = (
            "main_menu_background.bin",
            "main_menu_icons.bin",
            "main_menu_brand.bin",
            "main_menu_portrait_exhibition.bin",
            "main_menu_portrait_2player.bin",
            "main_menu_portrait_settings.bin",
            "main_menu_portrait_credits.bin",
        )
        for name in names:
            path = ROOT / "data" / name
            with self.subTest(name=name):
                self.assertTrue(path.is_file())
                self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

        icons = Image.open(ROOT / "data" / "main_menu_icons.bin")
        self.assertEqual(icons.mode, "RGBA")
        self.assertEqual(icons.getchannel("A").getextrema(), (0, 255))


if __name__ == "__main__":
    unittest.main()
