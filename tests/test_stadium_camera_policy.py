"""Host checks for native Stadium's acquisition-only target correction."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StadiumTargetPolicyTests(unittest.TestCase):
    def test_live_targets_lifecycle_and_other_camera_isolation(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('requires installed host gcc')
        with tempfile.TemporaryDirectory(prefix='stadium-target-policy-') as temp:
            exe = Path(temp) / ('policy.exe' if os.name == 'nt' else 'policy')
            run = subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                (ROOT/'tests/test_stadium_camera_policy.c').as_posix(), '-lm', '-o', exe.as_posix()],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            subprocess.run([str(exe)], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
