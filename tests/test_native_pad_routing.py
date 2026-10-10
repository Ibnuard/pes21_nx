"""Execute the real P1/P2 native-unit adapter with host objects and input."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativePadRoutingTests(unittest.TestCase):
    def test_runtime_adapter(self):
        compiler = shutil.which("gcc") or shutil.which("clang")
        if not compiler:
            self.skipTest("host C compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="pesnx-pad-") as temp:
            exe = Path(temp) / "routing.exe"
            build = subprocess.run([compiler, "-std=c11", "-O1", "-Wall", "-Wextra",
                            "-Wno-unused-function", "-Wno-unused-variable",
                            (ROOT / "tests/test_native_pad_routing.c").as_posix(),
                            "-lm", "-o", exe.as_posix()], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            result = subprocess.run([str(exe)], capture_output=True,
                                    text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("native-pad routing: pass", result.stdout)
