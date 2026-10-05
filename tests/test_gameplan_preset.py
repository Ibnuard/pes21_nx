"""Exercise per-team three-slot presets without Switch or proprietary files."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GameplanPresetTests(unittest.TestCase):
    def test_storage_and_corrupt_copy_fallback(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("host C compiler required")
        with tempfile.TemporaryDirectory(prefix="pes-gameplan-preset-") as work:
            executable = Path(work) / "gameplan-preset-test.exe"
            subprocess.run(
                [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", str(ROOT / "source"),
                 str(ROOT / "source/gameplan_preset.c"),
                 str(ROOT / "tests/test_gameplan_preset.c"),
                 "-o", str(executable)],
                check=True, capture_output=True, text=True)
            subprocess.run([str(executable)], cwd=work, check=True,
                           capture_output=True, text=True)
