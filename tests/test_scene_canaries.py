from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SceneCanaryTests(unittest.TestCase):
    def test_referee_behavior_scenarios(self):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='pesnx-behavior-') as temp:
            exe = Path(temp) / 'behavior.exe'
            build = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                (ROOT / 'tests/test_referee_motion.c').as_posix(), '-lm', '-o', exe.as_posix()],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            test = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
            self.assertEqual(test.returncode, 0, test.stdout + test.stderr)

    def test_installers_before_executable_mapping(self):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='pesnx-boot-') as temp:
            root = Path(temp)
            exe = root / 'bootstrap.exe'
            build = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                (ROOT / 'tests/test_scene_bootstrap.c').as_posix(), '-lm', '-o', exe.as_posix()],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            for feature in ('stadium', 'referee'):
                scenarios = ['enabled', 'absent', 'missing-gate', 'missing-binding',
                             'bad-opcode', 'bad-plt']
                if feature == 'referee':
                    scenarios += ['bad-retire-plt', 'bad-preload-plt',
                                  'bad-frame-plt', 'bad-event-plt', 'bad-event-layout', 'bad-sound-plt', 'missing-animation']
                for scenario in scenarios:
                    with self.subTest(feature=feature, scenario=scenario):
                        run = root / (feature + '-' + scenario)
                        run.mkdir()
                        (run / 'Animations').mkdir()
                        if scenario != 'absent':
                            if feature == 'stadium':
                                pak = run / 'PesMobile/Content/Paks/PesMobile-Anfield-Android_ETC1_P.pak'
                                pak.parent.mkdir(parents=True)
                                pak.write_bytes(b'host presence fixture')
                            else:
                                (run / 'referee-probe.txt').write_text('PESNX_REFEREE_PROBE_V1\n')
                        test = subprocess.run([str(exe), feature, scenario], cwd=run,
                            capture_output=True, text=True, timeout=20)
                        self.assertEqual(test.returncode, 0, test.stdout + test.stderr)
            for combination in ('none','stadium','referee','both'):
                with self.subTest(weather_chain=combination):
                    run=root/('weather-'+combination);run.mkdir()
                    (run/'Animations').mkdir()
                    paks=run/'PesMobile/Content/Paks';paks.mkdir(parents=True)
                    (paks/'PesMobile-Weather-Android_ETC1_P.pak').write_bytes(b'host fixture')
                    if combination in ('stadium','both'):
                        (paks/'PesMobile-Anfield-Android_ETC1_P.pak').write_bytes(b'host fixture')
                    if combination in ('referee','both'):
                        (run/'referee-probe.txt').write_text('PESNX_REFEREE_PROBE_V1\n')
                    test=subprocess.run([str(exe),'weather',combination],cwd=run,
                        capture_output=True,text=True,timeout=20)
                    self.assertEqual(test.returncode,0,test.stdout+test.stderr)

    def test_asset_failure_selection_restore_and_model_lifetime(self):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='pesnx-scene-') as temp:
            exe = Path(temp) / 'scene.exe'
            build = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                (ROOT / 'tests/test_scene_canaries.c').as_posix(), '-lm', '-o', exe.as_posix()],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            test = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
            self.assertEqual(test.returncode, 0, test.stdout + test.stderr)

    def test_independent_animation_clock_and_clip_validation(self):
        compiler = shutil.which('gcc') or shutil.which('clang')
        if not compiler:
            self.skipTest('host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='pesnx-ref-animation-') as temp:
            exe = Path(temp) / 'animation.exe'
            build = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                (ROOT / 'tests/test_referee_animation.c').as_posix(), '-lm', '-o', exe.as_posix()],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            test = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
            self.assertEqual(test.returncode, 0, test.stdout + test.stderr)
