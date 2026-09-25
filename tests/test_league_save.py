from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LeagueSaveTests(unittest.TestCase):
    def test_v1_to_v2_scorer_migration(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp)
            (destination / "SaveData").mkdir()
            binary = destination / "league-save-test.exe"
            subprocess.run([
                compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-I", str(ROOT / "source"),
                str(ROOT / "tests/test_league_save.c"),
                str(ROOT / "source/league_save.c"),
                "-o", str(binary),
            ], check=True)
            subprocess.run([str(binary)], cwd=destination, check=True)


if __name__ == "__main__":
    unittest.main()
