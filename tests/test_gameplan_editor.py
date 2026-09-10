"""Run the production editor functions on the host with native-engine stubs."""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"\b" + name + r"\([^;{}]*\)\s*\{", source)
    if match is None:
        raise AssertionError(f"Missing definition: {name}")
    start = source.rfind("\n", 0, match.start()) + 1
    end = source.index("\n}", match.end()) + 2
    return source[start:end]


def struct(source, name):
    return re.search(r"typedef struct \{[^}]*\} " + name + ";", source).group()


class GameplanEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            raise unittest.SkipTest("Host C compiler required")
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        header = (ROOT / "source/ue4_hooks.h").read_text(encoding="utf-8")
        shim = (ROOT / "source/android_shim.c").read_text(encoding="utf-8")
        overlay = (ROOT / "source/overlay.c").read_text(encoding="utf-8")
        cls.temp = tempfile.TemporaryDirectory(prefix="pes-gameplan-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = Path(cls.temp.name) / "gameplan-test.exe"
        native_declarations = hooks[
            hooks.index("static void (*match_squad_data_set_formation)"):
            hooks.index("static uint32_t (*match_squad_data_get_team_power)")
        ]
        presets = hooks[
            hooks.index("static const PrematchFormationPreset prematch_formation_presets"):
            hooks.index("static void prematch_gameplan_reset_side")
        ]
        definitions = "\n".join(
            line for line in (header + "\n" + hooks).splitlines()
            if re.match(r"#define (PES_PAUSE_INPUT_|PES_PREMATCH_|PES_GAMEPLAN_BUTTON_|"
                        r"PREMATCH_GAMEPLAN_(MAX_PLAYERS|NO_SELECTION))", line)
        )
        source = "\n".join([
            "#include <stdint.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
            "#include <string.h>\n#include <math.h>\n#include <assert.h>",
            definitions,
            *[struct(hooks, name) for name in (
                "TmpdbFormationValue", "TmpdbMatchPlanSettingsValue",
                "PrematchGameplanPlayer", "PrematchGameplanSide",
                "PrematchFormationPreset")],
            presets, native_declarations,
            "static PrematchGameplanSide exhibition_gameplan_sides[2];\n"
            "static uint32_t exhibition_gameplan_custom_action[2];\n"
            "static uint32_t exhibition_gameplan_raw_buttons[2];\n"
            "static int32_t exhibition_gameplan_raw_axis_x[2], exhibition_gameplan_raw_axis_y[2];\n"
            "static uint64_t exhibition_gameplan_portrait_retry_tick[2];\n"
            "static uint64_t mock_now;\n"
            "static uint64_t armGetSystemTick(void) { return mock_now; }\n"
            "static uint64_t armTicksToNs(uint64_t t) { return t; }\n"
            "static int pes_controller_custom_prematch_gameplan_active(void) { return 1; }\n"
            "static int pes_controller_exhibition_single_controller_mode(void) { return 0; }\n"
            "static void prematch_gameplan_load_portraits(uint32_t s) { (void)s; }\n"
            "static void live_gameplan_poll_portraits(void) {}\n"
            "static int pes_controller_gameplan_bench_locked(uint32_t side, uint32_t index) {return 0;}\n"
            "#define debugPrintf(...) ((void)0)",
            *[function(hooks, name) for name in (
                "main_menu_2p_team_selector_grade_half_steps",
                "prematch_gameplan_nth_player", "prematch_gameplan_nth_player_const",
                "prematch_gameplan_layout_lane", "prematch_gameplan_reset_side",
                "prematch_gameplan_build_formation_label", "prematch_gameplan_detect_preset")],
            (ROOT / "tests/gameplan_editor_stubs.inc").read_text(),
            *[function(hooks, name) for name in (
                "prematch_gameplan_save_and_refresh", "prematch_gameplan_store_formation",
                "prematch_gameplan_zone_role", "prematch_gameplan_reset_default", "prematch_gameplan_cycle_role",
                "prematch_gameplan_apply_preset", "prematch_gameplan_drag_field",
                "prematch_gameplan_finish_drag", "prematch_gameplan_swap_field",
                "prematch_gameplan_move_field", "prematch_gameplan_process_substitute",
                "prematch_gameplan_process_formation", "exhibition_gameplan_process_pending",
                "pes_controller_custom_prematch_gameplan_input",
                "pes_controller_custom_prematch_gameplan_formation_picker_active",
                "pes_controller_custom_prematch_gameplan_formation_row_count",
                "pes_controller_custom_prematch_gameplan_formation_scroll",
                "pes_controller_custom_prematch_gameplan_formation_option_active",
                "pes_controller_custom_prematch_gameplan_pad_event")],
            "typedef uint64_t u64;\n"
            "typedef struct { int32_t x, y; } HidAnalogStickState;\n"
            "#define JOYSTICK_MAX 32767\n"
            "enum { HidNpadButton_A=1, HidNpadButton_B=2, HidNpadButton_X=4,\n"
            "HidNpadButton_Y=8, HidNpadButton_Left=16, HidNpadButton_Up=32,\n"
            "HidNpadButton_Right=64, HidNpadButton_Down=128 };",
            re.search(r"typedef enum \{[^}]*\} ControllerProfile;", shim).group(),
            *[function(shim, name) for name in (
                "controller_profile_map_stick", "controller_profile_map_buttons",
                "controller_profile_menu_buttons", "normalize_stick")],
            "typedef float GLfloat;\nstatic int screen_width=1280, screen_height=720;\n"
            '#include "efootball_font_atlas.h"',
            *[function(overlay, name) for name in (
                "measure_efootball_line", "emit_efootball_line",
                "emit_efootball_name_line", "gameplan_name_focus_seconds")],
            "static uint32_t kickoff_loading_armed, main_menu_2p_transition_kind, main_menu_2p_transition_active;\n"
            "enum { MAIN_MENU_2P_TRANSITION_NONE=0, MAIN_MENU_2P_TRANSITION_VS=2 };",
            function(hooks, "kickoff_loading_reveal"),
            (ROOT / "tests/gameplan_editor_cases.inc").read_text(),
        ])
        cfile = Path(cls.temp.name) / "gameplan-test.c"
        cfile.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror=incompatible-pointer-types",
             "-I", str(ROOT / "source"),
             str(cfile), "-lm", "-o", str(cls.exe)],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_case(self, case):
        result = subprocess.run([str(self.exe), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_tap_selects_without_leaving_field_and_swaps_starters(self):
        self.run_case("tap")

    def test_hold_moves_native_coordinates_and_preserves_other_tactics(self):
        self.run_case("drag")

    def test_dpad_drag_is_time_based_and_clamped(self):
        self.run_case("dpad")

    def test_latched_edges_survive_repeated_polls_and_page_entry(self):
        self.run_case("edges")

    def test_role_changes_field_player_only_and_keeps_one_goalkeeper(self):
        self.run_case("role")

    def test_all_presets_apply_and_cycle_with_correct_roles(self):
        self.run_case("presets")

    def test_horizontal_joycon_buttons_and_stick_use_same_editor_actions(self):
        self.run_case("profiles")

    def test_name_marquee_keeps_font_size_and_clips_inside_glyph_uvs(self):
        self.run_case("names")

    def test_club_stars_follow_visible_average_monotonically(self):
        self.run_case("ratings")

    def test_zone_roles_and_reset_default(self):
        self.run_case("zones")

    def test_compact_formation_scroll_and_active_selection(self):
        self.run_case("popup")

    def test_loading_reveal_is_one_shot_and_preserves_other_transitions(self):
        self.run_case("loading")


if __name__ == "__main__":
    unittest.main()
