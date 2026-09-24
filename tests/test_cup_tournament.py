"""Host-side Cup bracket and schedule-preview regression."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CupTournamentTests(unittest.TestCase):
    def test_bracket_progression_and_schedule_preview(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "cup-tournament-test.exe"
            subprocess.run(
                [
                    compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "source"),
                    str(ROOT / "tests/test_cup_tournament.c"),
                    str(ROOT / "source/cup_tournament.c"),
                    "-o", str(binary),
                ],
                check=True,
            )
            subprocess.run([str(binary)], cwd=temp, check=True)
