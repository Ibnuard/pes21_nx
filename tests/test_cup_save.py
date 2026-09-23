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
