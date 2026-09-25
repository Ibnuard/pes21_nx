"""Check Cup's alternating on-disk saves without Switch game payloads."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CupSaveTests(unittest.TestCase):
    def test_save_load_and_interrupted_copy(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        source = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "cup_save.h"
int main(void) {
  CupSaveState state, loaded;
  memset(&state, 0, sizeof(state));
  state.game_time = 5u;
  assert(!cup_save_read(0u, &loaded));
  assert(cup_save_write(0u, &state));
  assert(cup_save_read(0u, &loaded) && loaded.game_time == 5u);
  state.game_time = 10u;
  assert(cup_save_write(0u, &state));
  assert(cup_save_read(0u, &loaded) && loaded.game_time == 10u);
  FILE *file = fopen("SaveData/footballnx_cup_1_b.bin", "wb");
  assert(file && fwrite("bad", 1, 3, file) == 3 && fclose(file) == 0);
  assert(cup_save_read(0u, &loaded) && loaded.game_time == 5u);
  assert(!cup_save_read(1u, &loaded));
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            program = folder / "cup-save.c"
            binary = folder / "cup-save.exe"
            program.write_text(source, encoding="utf-8")
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "source"), str(program),
                            str(ROOT / "source/cup_save.c"), "-o", str(binary)],
                           check=True)
            subprocess.run([str(binary)], cwd=folder, check=True)

    def test_version_one_save_migrates_without_losing_bracket(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        source = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "cup_save.h"
typedef struct {
  uint32_t home, away, winner;
  uint8_t home_goals, away_goals, complete, simulated;
} OldFixture;
typedef struct {
  OldFixture fixtures[5][16];
  uint8_t history_round[31], history_index[31];
  uint32_t seed, team_count, bracket_size, round_count, active_round;
  uint32_t human_count, human_teams[8], history_count, champion;
} OldTournament;
typedef struct {
  uint32_t cup_select, player_count, team_count, com_level, match_mode;
  uint32_t game_time, extra_time, max_substitutions;
  uint32_t tournament_valid, first_match_started;
  CompetitionEntryDraft draft;
  OldTournament tournament;
} OldState;
typedef struct {
  uint32_t magic, version, size, sequence, checksum;
} Header;
static uint32_t checksum(const void *input, size_t length) {
  const uint8_t *bytes = (const uint8_t *)input;
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < length; i++) {
    hash ^= bytes[i]; hash *= 16777619u;
  }
  return hash;
}
int main(void) {
  assert(mkdir("SaveData", 0777) == 0);
  OldState old = {0};
  old.player_count = old.draft.player_count = 1u;
  old.team_count = old.draft.team_count = old.tournament.team_count = 4u;
  old.com_level = 3u; old.game_time = 5u;
  old.match_mode = 1u; /* legacy knockout */
  old.extra_time = 1u; old.max_substitutions = 5u;
  old.tournament_valid = 1u;
  old.tournament.bracket_size = 4u;
  old.tournament.round_count = 2u;
  old.tournament.fixtures[0][0].home = 101u;
  old.tournament.fixtures[0][0].away = 102u;
  old.tournament.fixtures[0][0].home_goals = 2u;
  old.tournament.fixtures[0][0].complete = 1u;
  old.tournament.fixtures[0][0].winner = 101u;
  Header header = {0x32584346u, 1u, sizeof(old), 7u,
                   checksum(&old, sizeof(old))};
  FILE *file = fopen("SaveData/footballnx_cup_1_a.bin", "wb");
  assert(file);
  assert(fwrite(&header, 1, sizeof(header), file) == sizeof(header));
  assert(fwrite(&old, 1, sizeof(old), file) == sizeof(old));
  assert(fclose(file) == 0);
  CupSaveState state;
  assert(cup_save_read(0u, &state));
  assert(state.game_time == 5u && state.injuries && state.var_enabled);
  assert(state.cup_select == 6u); /* old custom Cup moves to final choice */
  assert(!state.home_away && !state.third_place);
  assert(state.tournament.fixtures[0][0].winner == 101u);
  assert(cup_save_write(0u, &state));
  memset(&state, 0, sizeof(state));
  assert(cup_save_read(0u, &state));
  assert(state.tournament.fixtures[0][0].home_goals == 2u);
  old.match_mode = 0u; /* untouched legacy Home Away selection */
  old.tournament.fixtures[0][0].complete = 0u;
  old.tournament.fixtures[0][0].winner = 0u;
  header.checksum = checksum(&old, sizeof(old));
  file = fopen("SaveData/footballnx_cup_2_a.bin", "wb");
  assert(file);
  assert(fwrite(&header, 1, sizeof(header), file) == sizeof(header));
  assert(fwrite(&old, 1, sizeof(old), file) == sizeof(old));
  assert(fclose(file) == 0);
  assert(cup_save_read(1u, &state));
  assert(state.home_away && state.tournament.home_away);
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            program = folder / "cup-save-v1.c"
            binary = folder / "cup-save-v1.exe"
            program.write_text(source, encoding="utf-8")
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "source"), str(program),
                            str(ROOT / "source/cup_save.c"), "-o", str(binary)],
                           check=True)
            subprocess.run([str(binary)], cwd=folder, check=True)

    def test_version_two_selector_migrates_to_seven_cups(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        source = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include "cup_save.h"
typedef struct { uint32_t magic, version, size, sequence, checksum; } Header;
static uint32_t checksum(const void *input, size_t length) {
  const uint8_t *bytes = (const uint8_t *)input;
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < length; i++) {
    hash ^= bytes[i]; hash *= 16777619u;
  }
  return hash;
}
static void old_save(uint32_t slot, uint32_t old_selector) {
  CupSaveState old = {0};
  old.cup_select = old_selector;
  Header header = {0x32584346u, 2u, sizeof(old), 1u,
                   checksum(&old, sizeof(old))};
  char path[64];
  snprintf(path, sizeof(path), "SaveData/footballnx_cup_%u_a.bin", slot + 1u);
  FILE *file = fopen(path, "wb");
  assert(file);
  assert(fwrite(&header, 1, sizeof(header), file) == sizeof(header));
  assert(fwrite(&old, 1, sizeof(old), file) == sizeof(old));
  assert(fclose(file) == 0);
}
int main(void) {
  assert(mkdir("SaveData", 0777) == 0);
  old_save(0u, 1u); /* FA Cup */
  old_save(1u, 3u); /* Copa del Rey */
  old_save(2u, 9u); /* Retired Copa Chile remains a playable custom Cup */
  CupSaveState state;
  assert(cup_save_read(0u, &state) && state.cup_select == 0u);
  assert(cup_save_read(1u, &state) && state.cup_select == 1u);
  assert(cup_save_read(2u, &state) && state.cup_select == 6u);
  assert(cup_save_write(2u, &state));
  assert(cup_save_read(2u, &state) && state.cup_select == 6u);
  return 0;
}
"""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            program = folder / "cup-save-v2.c"
            binary = folder / "cup-save-v2.exe"
            program.write_text(source, encoding="utf-8")
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "source"), str(program),
                            str(ROOT / "source/cup_save.c"), "-o", str(binary)],
                           check=True)
            subprocess.run([str(binary)], cwd=folder, check=True)
