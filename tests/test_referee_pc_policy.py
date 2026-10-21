from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_pc_referee_target_constraints():
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler unavailable")
    with tempfile.TemporaryDirectory(prefix="pesnx-referee-pc-") as directory:
        executable = Path(directory) / "policy.exe"
        build = subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
             (ROOT / "tests/test_referee_pc_policy.c").as_posix(), "-lm", "-o",
             executable.as_posix()], capture_output=True, text=True, timeout=60)
        assert build.returncode == 0, build.stdout + build.stderr
        test = subprocess.run([str(executable)], capture_output=True,
                              text=True, timeout=20)
        assert test.returncode == 0, test.stdout + test.stderr
