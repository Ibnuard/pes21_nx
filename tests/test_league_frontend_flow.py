"""Host-side League settings, hub, save, and fixture handoff regression."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LeagueFrontendFlowTests(unittest.TestCase):
    def test_league_flow(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "league-frontend-test.exe"
            # Isolate the native loader type while compiling the real frontend.
            (Path(temp) / "ue4_hooks.h").write_text((ROOT / "source/ue4_hooks.h").read_text().replace(
                '#include "so_util.h"', 'typedef struct so_module so_module;'))
            shutil.copy2(ROOT / "source/competition_frontend.c", Path(temp) / "competition_frontend.c")
            clang = "clang" in subprocess.check_output([compiler, "--version"], text=True).lower()
            subprocess.run(
                [
                    compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    *(["-Wno-constant-logical-operand"] if clang else []),
                    "-I", str(Path(temp)), "-I", str(ROOT / "source"),
                    str(ROOT / "tests/test_league_frontend_flow.c"),
                    str(Path(temp) / "competition_frontend.c"),
                    str(ROOT / "source/competition_entry_draft.c"),
                    str(ROOT / "source/cup_tournament.c"),
                    str(ROOT / "source/cup_save.c"),
                    str(ROOT / "source/league_tournament.c"),
                    str(ROOT / "source/league_save.c"),
                    *[str(ROOT / "source" / name) for name in (
                        "master_league.c", "master_league_save.c", "master_league_frontend.c",
                        "master_league_catalog.c", "gameplan_preset.c")],
                    "-o", str(binary),
                ],
                check=True,
            )
            subprocess.run([str(binary)], cwd=temp, check=True)
