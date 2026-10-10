"""Regression checks for the embedded custom-menu PNG upload path."""

from pathlib import Path
import re
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (ROOT / "source/overlay.c").read_text(encoding="utf-8")


class OverlayMenuAssetsTests(unittest.TestCase):
    def test_switch_button_sprites_are_high_resolution_and_packaged(self):
        buttons = {
            "a": "A_Button", "b": "B_Button", "x": "X_Button",
            "y": "Y_Button", "l": "L_Button", "zl": "ZL_Button",
            "zr": "ZR_Button", "sl": "SL_Button", "sr": "SR_Button",
            "ls": "LeftStick_Default_CORE", "rs": "RightStick_Default_CORE",
            "right": "Directional_Button_Right",
            "up": "Directional_Button_Up",
            "down": "Directional_Button_Down",
            "left": "Directional_Button_Left",
        }
        for key, name in buttons.items():
            with self.subTest(key=key):
                png = (ROOT / f"art/SwitchButton/{name}.png").read_bytes()
                self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack_from(">II", png, 16), (80, 80))
                data_name = (
                    f"main_menu_button_{key}.bin" if key in ("a", "b")
                    else f"switch_button_{key}.bin"
                )
                self.assertEqual(png, (ROOT / "data" / data_name).read_bytes())

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

    def test_shared_custom_page_images_use_minification_filters(self):
        atlas = re.search(r"static void atlas_ready\(void\) \{.*?\n\}", OVERLAY, re.S).group(0)
        badge = atlas[
            atlas.index("glBindTexture(GL_TEXTURE_2D, gl.badge_tex);"):
            atlas.index("glBindTexture(GL_TEXTURE_2D, gl.team_rating_star_tex);")
        ]
        self.assertIn("GL_LINEAR_MIPMAP_LINEAR", badge)
        portrait = OVERLAY[
            OVERLAY.index("static void prepare_gameplan_portraits("):
            OVERLAY.index("static GLuint gameplan_portrait_texture(")
        ]
        self.assertIn("use_mipmaps ? GL_LINEAR_MIPMAP_LINEAR : GL_LINEAR", portrait)
        self.assertIn("if (use_mipmaps)\n            glGenerateMipmap(GL_TEXTURE_2D);", portrait)
        self.assertIn(
            "glBindTexture(GL_TEXTURE_2D, gl.team_select_bg_tex);\n"
            "  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER,\n"
            "                  GL_LINEAR_MIPMAP_LINEAR);",
            atlas,
        )
        uniform = re.search(
            r"static void prepare_uniform_thumbnail_preview\(int active\) \{.*?\n\}",
            OVERLAY, re.S,
        ).group(0)
        self.assertIn("use_mipmaps ? GL_LINEAR_MIPMAP_LINEAR : GL_LINEAR", uniform)

    def test_cup_and_league_settings_keep_full_height_scrollable_rows(self):
        settings = OVERLAY[
            OVERLAY.index("} else if (custom_hub_settings_popup) {"):
            OVERLAY.index("const float panel_x = 0.17f * (float)screen_width;",
                          OVERLAY.index("} else if (custom_hub_settings_popup) {")) + 2000
        ]
        self.assertIn("max_visible = cup_settings_popup ? 4u : 5u", settings)
        self.assertIn("row_h = 0.082f", settings)
        self.assertIn("cup_settings_popup ? 0.102f : 0.108f", settings)
        self.assertIn("value_h = 0.058f", settings)


if __name__ == "__main__":
    unittest.main()
