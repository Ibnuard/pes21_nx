"""Regression guards for the full-page custom main menu."""

from pathlib import Path
import re
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class CustomMainMenuTests(unittest.TestCase):
    def test_confirm_does_not_require_native_touch_dispatch(self):
        shim = (ROOT / "source/android_shim.c").read_text(encoding="utf-8")
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        tap = shim.split("static void append_menu_controller_tap(", 1)[1].split(
            "static void append_menu_controller_back(", 1)[0]
        self.assertIn("!pes_controller_start_prompt(NULL, NULL)", tap)
        self.assertIn("if (a_pressed)\n      pes_controller_menu_tap(0.0f, 0.0f);\n    return;", tap)
        self.assertIn("pes_main_menu_focus_index() + 1u", hooks)
        self.assertIn("&main_menu_confirm_pending, 0, __ATOMIC_ACQ_REL", hooks)
        self.assertIn("main_menu_activate_choice(menu_confirm - 1u)", hooks)

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

    def test_cpk_splash_handoff_and_title_page_are_custom_full_frames(self):
        overlay = (ROOT / "source/overlay.c").read_text(encoding="utf-8")
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        self.assertIn("pes_controller_startup_transition_active()", overlay)
        self.assertIn("startup_transition_background_quad", overlay)
        self.assertIn("gl.bind_sampler(0, 0)", overlay)
        self.assertIn("update_title_portrait_cycle", overlay)
        self.assertIn('"PRESS"', overlay)
        self.assertIn('"TO START"', overlay)
        self.assertIn('"ANDROSWITCH PROJECT 2026"', overlay)
        self.assertIn("startup_transition_active", hooks)
        self.assertIn('"Intro/MenuIntroKonamiLogo"', hooks)
        self.assertIn('"Intro/MenuIntroPreTitle"', hooks)
        # Image quads must stay out of the monochrome font batch; otherwise
        # the font atlas is stretched across the title as vertical stripes.
        self.assertLess(
            overlay.index("const int generic_text_end_quad = quads;"),
            overlay.index("if (startup_transition) {"),
        )
        self.assertGreaterEqual(
            hooks.count("&startup_transition_active, 1, __ATOMIC_RELEASE"), 3
        )

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

        brand = Image.open(ROOT / "data" / "main_menu_brand.bin")
        self.assertEqual(brand.mode, "RGBA")
        self.assertEqual(brand.getchannel("A").getextrema(), (0, 255))
        self.assertLessEqual(brand.width, 1120)
        self.assertLessEqual(brand.height, 480)
        self.assertGreater(brand.width / brand.height, 2.5)
        self.assertLess(brand.width / brand.height, 2.8)
        self.assertEqual(brand.getpixel((504, 318))[:3], (239, 255, 0))
        self.assertEqual(brand.getpixel((420, 340))[:3], (255, 38, 112))
        self.assertEqual(brand.getpixel((100, 100))[:3], (255, 255, 255))

        with Image.open(
            ROOT / "art" / "main_menu" / "androswitch-boot-splash-v3.png"
        ) as authored_splash:
            self.assertEqual(authored_splash.size, (1920, 1080))

    def test_two_player_general_settings_omits_com_level(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        overlay = (ROOT / "source/overlay.c").read_text(encoding="utf-8")
        self.assertIn(
            "PES_MATCH_SETTINGS_COUNT - exhibition_match_settings_first_index()",
            hooks,
        )
        self.assertIn(
            "index + exhibition_match_settings_first_index()",
            hooks,
        )
        self.assertNotIn('"COM LEVEL", "MATCH TIME"', hooks)
        self.assertIn("pes_controller_custom_match_settings_count()", overlay)

    def test_player_cursor_is_not_configurable_and_stays_hidden(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        header = (ROOT / "source/ue4_hooks.h").read_text(encoding="utf-8")
        config = (ROOT / "source/config.c").read_text(encoding="utf-8")
        self.assertIn("#define PES_MATCH_SETTINGS_COUNT 4u", header)
        self.assertNotIn("PLAYER CURSOR", hooks)
        self.assertNotIn("player_cursor_show", hooks)
        self.assertNotIn("player_cursor_show", config)
        self.assertIn("const int show = 0;", hooks)


if __name__ == "__main__":
    unittest.main()
