"""Host-only final/result policy: no proprietary fixtures or scene activation."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_fresh_final_gate_and_backend_success_latch():
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    with tempfile.TemporaryDirectory(prefix="pesnx-ceremony-policy-") as temp:
        binary = Path(temp) / "ceremony-policy.exe"
        build = subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-I", str(ROOT / "source"),
             str(ROOT / "tests/test_fixdemo_ceremony_policy.c"),
             "-o", str(binary)],
            capture_output=True, text=True, timeout=30,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
