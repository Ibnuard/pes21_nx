from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LeagueTournamentTests(unittest.TestCase):
    def test_schedule_and_knockout_progression(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / "league-tournament-test.exe"
            subprocess.run([
                compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "source"),
                str(ROOT / "tests/test_league_tournament.c"),
                str(ROOT / "source/league_tournament.c"),
                str(ROOT / "source/cup_tournament.c"),
                "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], cwd=temp, check=True)


if __name__ == "__main__":
    unittest.main()
