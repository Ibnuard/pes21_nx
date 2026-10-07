"""Execute production pregame commits against the native 18-member/full-roster model."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]


class PrematchLineupSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            raise unittest.SkipTest("Host C compiler required")
        cls.temp = tempfile.TemporaryDirectory(prefix="pes-lineup-sync-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.exe = Path(cls.temp.name) / "lineup.exe"
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        source = "\n".join([
            (ROOT / "tests/prematch_lineup_stubs.inc").read_text(),
            *[function(hooks, name) for name in (
                "exhibition_matchplan_common_side", "exhibition_sync_prematch_lineup",
                "exhibition_save_matchplan_sides", "master_league_office_lineup_valid", "prematch_gameplan_replace_player",
                "exhibition_prepare_team_conditions")],
            (ROOT / "tests/prematch_lineup_cases.inc").read_text(),
        ])
        cfile = Path(cls.temp.name) / "lineup.c"
        cfile.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(cfile), "-o", str(cls.exe)], capture_output=True, text=True,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_case(self, name):
        result = subprocess.run([str(self.exe), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bright_to_messi_outside_registered_18_moves_full_player_not_just_hud(self):
        self.run_case("reserve")

    def test_registered_bench_swap_commits_order_and_preserves_records(self):
        self.run_case("bench")

    def test_multiple_swaps_reverse_and_repeated_save_remain_consistent(self):
        self.run_case("repeat")

    def test_home_and_away_same_team_are_isolated(self):
        self.run_case("sides")

    def test_invalid_identity_or_allocation_failure_roll_back_before_any_write(self):
        self.run_case("reject")

    def test_live_substitution_path_never_reorders_match_records(self):
        self.run_case("live")

    def test_office_substitution_validates_career_without_match_bindings(self):
        self.run_case("office")

    def test_random_conditions_are_seeded_once_per_match_and_respect_uniform_override(self):
        self.run_case("conditions")

    def test_pregame_routes_reuse_the_committed_plan(self):
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        cache = function(hooks, "main_menu_2p_prematch_hub_cache_lineups")
        refresh = function(hooks, "exhibition_refresh_selected_tmpdb")
        back = function(hooks, "prematch_gameplan_process_root")
        preset = function(hooks, "prematch_gameplan_load_preset")
        kits = function(hooks, "main_menu_2p_native_uniform_open")
        self.assertIn("matchplan_common_get_member_id(common, member)", cache)
        self.assertIn("main_menu_2p_prematch_hub_cache_lineups();", back)
        self.assertIn("prematch_gameplan_replace_player(", preset)
        self.assertIn("order < registered", preset)
        self.assertIn("exhibition_gameplan_prepare_matchplan()", kits)
        self.assertLess(refresh.index("exhibition_save_matchplan_sides(3u)"),
                        refresh.index("exhibition_install_master_roster("))
        for reset in ("exhibition_refresh_selected_tmpdb()",
                      "exhibition_matchplan_setup_tmpdb(", "matchplan_squad_load()"):
            self.assertNotIn(reset, kits)
        self.assertLess(refresh.index("exhibition_prepare_team_conditions("),
                        refresh.index("exhibition_set_team(&home_team_id"))


if __name__ == "__main__":
    unittest.main()
