"""Settings delivery and repeated-match state; no game data required."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeWeatherTests(unittest.TestCase):
    def test_native_handoff_and_snapshot_boundaries(self):
        cc = shutil.which('gcc') or shutil.which('clang')
        if not cc:
            self.skipTest('host C compiler unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / 'weather.exe'
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            (ROOT/'tests/test_native_weather.c').as_posix(), '-o', exe.as_posix()], check=True)
            subprocess.run([str(exe)], check=True, timeout=10)

    def test_scene_and_scoreboard_lifetime(self):
        cc = shutil.which('gcc') or shutil.which('clang')
        if not cc:
            self.skipTest('host C compiler unavailable')
        for name in ('weather_scene', 'scoreboard_runtime'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                exe=Path(tmp)/(name+'.exe')
                subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',
                    (ROOT/('tests/test_'+name+'.c')).as_posix(),'-lm','-o',exe.as_posix()],check=True)
                subprocess.run([str(exe)],cwd=tmp,check=True,timeout=10)
