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
            subprocess.run(
                [
                    compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "source"),
                    str(ROOT / "tests/test_league_frontend_flow.c"),
                    str(ROOT / "source/competition_frontend.c"),
                    str(ROOT / "source/competition_entry_draft.c"),
                    str(ROOT / "source/cup_tournament.c"),
                    str(ROOT / "source/cup_save.c"),
                    str(ROOT / "source/league_tournament.c"),
                    str(ROOT / "source/league_save.c"),
                    "-o", str(binary),
                ],
                check=True,
            )
            subprocess.run([str(binary)], cwd=temp, check=True)
