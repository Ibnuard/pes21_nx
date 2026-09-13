"""Exercise the production result action resolver across match phases."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from test_gameplan_editor import function

ROOT = Path(__file__).resolve().parents[1]

PRELUDE = r"""
#include <stdint.h>
#include <assert.h>
static uint32_t match_result_final_seen, exhibition_settings_extra_time;
static uint32_t exhibition_settings_penalties, match_result_extra_time_started;
static uint32_t match_result_half_menu_seen;
static uint32_t home, away, stub_phase;
static int pes_controller_pause_score(uint32_t side, uint32_t *out) {
  *out = side ? away : home; return 1;
}
static uint32_t match_result_current_phase(void) { return stub_phase; }
"""


def harness(hooks, body):
    enums = "\n".join(re.findall(
        r"enum\s*\{\s*(?:MATCH_RESULT_(?:SURFACE|ACTION|PAGE)_|MATCH_PHASE_)"
        r".*?\};", hooks, re.S))
    return (PRELUDE + enums + "\n"
            + function(hooks, "match_result_action_list")
            + function(hooks, "match_result_interval_surface")
            + body)


def build_and_run(case, source):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "result.c"
        path.write_text(source)
        exe = Path(tmp) / "result.exe"
        subprocess.run([case, str(path), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


class ResultFlowTests(unittest.TestCase):
    def setUp(self):
        self.compiler = shutil.which("gcc")
        if not self.compiler:
            self.skipTest("gcc unavailable")
        self.hooks = (ROOT / "source/ue4_hooks.c").read_text()

    def test_phase_actions(self):
        body = r"""
int main(void) {
  uint32_t a[4];
  stub_phase = MATCH_PHASE_INVALID;
  for (int final = 0; final < 2; ++final)
    for (int et = 0; et < 2; ++et)
      for (int pk = 0; pk < 2; ++pk) {
        match_result_final_seen=final;
        exhibition_settings_extra_time=et;
        exhibition_settings_penalties=pk;
        assert(match_result_action_list(MATCH_RESULT_SURFACE_HALF_STATS,a)==1);
        assert(a[0]==MATCH_RESULT_ACTION_NEXT);
        assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_STATS,a)==1);
        assert(a[0]==MATCH_RESULT_ACTION_NEXT);
        assert(match_result_action_list(MATCH_RESULT_SURFACE_HALF_MENU,a)==3);
        assert(a[0]==MATCH_RESULT_ACTION_GAME_PLAN && a[1]==MATCH_RESULT_ACTION_NEXT);
        assert(a[2]==MATCH_RESULT_ACTION_BACK_TO_MENU);
      }
  match_result_final_seen=0;
  exhibition_settings_extra_time=1;
  exhibition_settings_penalties=1;
  assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==3);
  assert(a[0]==MATCH_RESULT_ACTION_GAME_PLAN && a[1]==MATCH_RESULT_ACTION_OVERTIME);
  match_result_extra_time_started=1;
  assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==2);
  assert(a[0]==MATCH_RESULT_ACTION_PENALTIES);
  match_result_final_seen=1;
  assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==1);
  assert(a[0]==MATCH_RESULT_ACTION_BACK_TO_MENU);
  match_result_final_seen=0; home=1; away=0;
  assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==1);
  assert(a[0]==MATCH_RESULT_ACTION_BACK_TO_MENU);
  return 0;
}
"""
        build_and_run(self.compiler, harness(self.hooks, body))

    def test_full_time_cards_follow_live_phase(self):
        # The live phase names the continuation, so the card row must ignore the
        # exhibition settings and the scoreline once the registry is readable.
        body = r"""
int main(void) {
  uint32_t a[4];
  for (int et = 0; et < 2; ++et)
    for (int pk = 0; pk < 2; ++pk)
      for (int drawn = 0; drawn < 2; ++drawn) {
        exhibition_settings_extra_time=et;
        exhibition_settings_penalties=pk;
        match_result_final_seen=0;
        match_result_extra_time_started=0;
        home = 1; away = drawn ? 1 : 0;

        stub_phase = MATCH_PHASE_EX_TIME;
        assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==3);
        assert(a[0]==MATCH_RESULT_ACTION_GAME_PLAN);
        assert(a[1]==MATCH_RESULT_ACTION_OVERTIME);
        assert(a[2]==MATCH_RESULT_ACTION_BACK_TO_MENU);

        stub_phase = MATCH_PHASE_PREV_PKMATCH;
        assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==2);
        assert(a[0]==MATCH_RESULT_ACTION_PENALTIES);
        assert(a[1]==MATCH_RESULT_ACTION_BACK_TO_MENU);

        // Whistle after overtime or penalties: the game is simply over.
        stub_phase = MATCH_PHASE_END;
        assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==1);
        assert(a[0]==MATCH_RESULT_ACTION_BACK_TO_MENU);

        // A final result outranks any phase.
        match_result_final_seen=1;
        stub_phase = MATCH_PHASE_EX_TIME;
        assert(match_result_action_list(MATCH_RESULT_SURFACE_FULL_MENU,a)==1);
        assert(a[0]==MATCH_RESULT_ACTION_BACK_TO_MENU);
      }
  return 0;
}
"""
        build_and_run(self.compiler, harness(self.hooks, body))

    def test_interval_surface_follows_phase(self):
        # MatchResultMainMenuHalfTime hosts every break in play. Only HALFTIME
        # and EX_INTERVAL resume the same segment; the rest are full time.
        body = r"""
int main(void) {
  const uint32_t half = MATCH_RESULT_SURFACE_HALF_MENU;
  const uint32_t full = MATCH_RESULT_SURFACE_FULL_MENU;
  stub_phase = MATCH_PHASE_HALFTIME;
  assert(match_result_interval_surface(half, full) == half);
  stub_phase = MATCH_PHASE_EX_INTERVAL;
  assert(match_result_interval_surface(half, full) == half);
  stub_phase = MATCH_PHASE_EX_TIME;
  assert(match_result_interval_surface(half, full) == full);
  stub_phase = MATCH_PHASE_PREV_PKMATCH;
  assert(match_result_interval_surface(half, full) == full);
  stub_phase = MATCH_PHASE_PKMATCH;
  assert(match_result_interval_surface(half, full) == full);
  stub_phase = MATCH_PHASE_END;
  assert(match_result_interval_surface(half, full) == full);
  // Unreadable registry falls back to the half-menu latch.
  stub_phase = MATCH_PHASE_INVALID;
  match_result_half_menu_seen = 0;
  assert(match_result_interval_surface(half, full) == half);
  match_result_half_menu_seen = 1;
  assert(match_result_interval_surface(half, full) == full);
  return 0;
}
"""
        build_and_run(self.compiler, harness(self.hooks, body))

    def test_phase_read_walks_native_chain(self):
        # match2D::Utility::Function::GetPhaseStartMinute reads the phase
        # through these exact offsets; every link is null-checked.
        reader = function(self.hooks, "match_result_current_phase")
        self.assertIn("0x4f0", reader)
        self.assertIn("0x1168", reader)
        self.assertIn("match_global_registry_get_instance", reader)

    def test_native_dispatch_follows_owning_page(self):
        # A full-time card row drawn over MatchResultMainMenuHalfTime must still
        # call that class's own methods, so routing keys off the page.
        dispatch = function(self.hooks, "match_result_process_controller_input")
        self.assertIn("match_result_page", dispatch)
        self.assertNotIn("surface != MATCH_RESULT_SURFACE_FULL_MENU", dispatch)
        self.assertNotIn("surface == MATCH_RESULT_SURFACE_HALF_MENU", dispatch)
        event = function(self.hooks, "match_result_dispatch_event")
        self.assertIn("MATCH_RESULT_PAGE_INTERVAL", event)

    def test_helper_row_matches_card_label(self):
        # The card reads "TOP TO MENU"; the helper row must advertise the same
        # wording or B silently goes unmentioned.
        overlay = (ROOT / "source/overlay.c").read_text()
        self.assertIn('"TOP TO MENU") == 0', overlay)
        self.assertNotIn('"BACK TO MENU") == 0', overlay)

    def test_no_double_dispatch_or_legacy_modal(self):
        dispatch = function(self.hooks, "match_result_process_controller_input")
        self.assertNotIn("MATCH_POSTMATCH_PAGE_GAMEPLAN", dispatch)
        self.assertIn('match_result_dispatch_event(window, "plan")', dispatch)
        self.assertIn("match_stats_footer_touch(window, 0u)", dispatch)
        shim = (ROOT / "source/android_shim.c").read_text()
        self.assertRegex(shim, r"if \(a_pressed && play_until_ms <= now_ms &&\s*!result_skin")
    def test_handoff_blocks_page_rearm_and_input(self):
        # A confirmed card hands the flow over. Until the next page announces
        # itself, no update hook may re-arm the outgoing surface and no input may
        # be consumed, otherwise the stock event leaks or the flow strands.
        hooks = self.hooks
        for name in ("pes_match_result_half_update_entry",
                     "pes_match_team_stats_update_entry"):
            body = function(hooks, name)
            self.assertIn("match_result_handoff_active()", body, name)
            self.assertIn("match_result_exit_requested", body, name)
        # Input arriving mid-handoff belongs to no page.
        dispatch = function(hooks, "match_result_process_controller_input")
        self.assertIn("match_result_handoff_active()", dispatch)
        # The final menu honours the same latch.
        final = function(hooks, "pes_match_result_update")
        self.assertIn("match_result_handoff_active()", final)
        # Every dispatched action arms the latch.
        self.assertIn("__atomic_store_n(&match_result_handoff_tick, armGetSystemTick()",
                      dispatch)
        # A newly constructed page takes ownership back.
        for name in ("pes_match_result_full_entry", "pes_match_result_half_entry",
                     "pes_match_stats_init"):
            self.assertIn("match_result_clear_handoff()", function(hooks, name), name)

    def test_handoff_window_is_bounded(self):
        # The latch must self-heal: a page that never announces itself cannot be
        # allowed to disable the skin permanently.
        body = function(self.hooks, "match_result_handoff_active")
        self.assertIn("3000000000ULL", body)
        self.assertIn("__atomic_store_n(&match_result_handoff_tick, 0", body)

    def test_top_menu_keeps_cover_and_uses_accepted_branch(self):
        # Top to Menu from a result surface must not tear its own skin down
        # before leaving, or the bare match scene shows through.
        dispatch = function(self.hooks, "match_result_process_controller_input")
        _, _, rest = dispatch.partition(
            "if (chosen == MATCH_RESULT_ACTION_BACK_TO_MENU) {")
        branch = rest.split("return;")[0]
        self.assertIn("match_pause_go_top_menu(window)", branch)
        self.assertIn("pause_top_menu_transition_tick", branch)
        self.assertNotIn("match_result_skin_ready, 0", branch)
        self.assertNotIn("MATCH_RESULT_SURFACE_NONE", branch)
        # The result cover owns the Top Menu handoff, released by the Match page
        # rebuild rather than a fixed delay.
        cover = function(self.hooks, "pes_controller_match_result_transition")
        self.assertIn("pause_top_menu_transition_tick", cover)
        self.assertIn("match_result_exit_requested", cover)

    def test_shim_holds_input_during_handoff(self):
        shim = (ROOT / "source/android_shim.c").read_text()
        self.assertIn("pes_controller_match_result_handoff()", shim)
        self.assertIn("result_context && !result_handoff", shim)
        self.assertIn("!result_skin && !result_handoff && !result_context", shim)
        header = (ROOT / "source/ue4_hooks.h").read_text()
        self.assertIn("uint32_t pes_controller_match_result_handoff(void);", header)


if __name__ == "__main__":
    unittest.main()

