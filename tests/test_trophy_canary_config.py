"""Host regression for opt-in identity; no game assets or runtime hooks."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_exact_marker_and_independently_measured_file_identity(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    executable = tmp_path / "trophy-config.exe"
    build = subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "source"),
                            str(ROOT / "tests/test_trophy_canary_config.c"), "-o", str(executable)],
                           capture_output=True, text=True, timeout=30)
    assert build.returncode == 0, build.stdout + build.stderr
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "trophy marker identity: pass"
