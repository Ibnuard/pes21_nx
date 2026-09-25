"""Exercise the Cup/League final-result score bridge with host-side stubs."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_gameplan_editor import function


ROOT = Path(__file__).resolve().parents[1]


class CupResultWiringTests(unittest.TestCase):
    def test_only_completed_competition_result_is_recorded(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        source = r"""
#include <assert.h>
#include <stdint.h>
#define MATCH_RESULT_PAGE_FINAL 3u
#define MATCH_PHASE_END 10u
static uint32_t match_result_page, match_result_final_seen;
static uint32_t phase, cup_active, league_active, scores_ready = 1u, calls;
static uint32_t league_calls;
static uint32_t recorded_home, recorded_away;
static int competition_frontend_cup_match_active(void) { return cup_active; }
static int competition_frontend_league_match_active(void) { return league_active; }
static uint32_t match_result_current_phase(void) { return phase; }
static int pes_controller_pause_score(uint32_t side, uint32_t *value) {
  if (!scores_ready) return 0;
  *value = side ? 1u : 2u;
  return 1;
}
static void competition_frontend_cup_match_result(uint32_t home, uint32_t away) {
  ++calls; recorded_home = home; recorded_away = away;
}
static void match_result_record_league_score(uint32_t home, uint32_t away) {
  ++league_calls; recorded_home = home; recorded_away = away;
}
"""
        source += function(hooks, "match_result_competition_finished") + "\n"
        source += function(hooks, "match_result_record_competition_score") + "\n"
        source += r"""
int main(void) {
  match_result_page = MATCH_RESULT_PAGE_FINAL;
  phase = MATCH_PHASE_END;
  match_result_record_competition_score();
  assert(calls == 0u);
  cup_active = 1u;
  phase = 0u;
  match_result_record_competition_score();
  assert(calls == 0u);
  match_result_final_seen = 1u;
  scores_ready = 0u;
  match_result_record_competition_score();
  assert(calls == 0u);
  scores_ready = 1u;
  match_result_record_competition_score();
  assert(calls == 1u && recorded_home == 2u && recorded_away == 1u);
  match_result_page = 2u;
  match_result_record_competition_score();
  assert(calls == 1u);
  match_result_page = MATCH_RESULT_PAGE_FINAL;
  cup_active = 0u;
  league_active = 1u;
  match_result_record_competition_score();
  assert(calls == 1u && league_calls == 1u);
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cup-result.c"
            binary = Path(temp) / "cup-result.exe"
            path.write_text(source, encoding="utf-8")
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            str(path), "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
