"""Real dummy C logic, new-process persistence, and actual native UI geometry."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ManagerLeagueDummyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('gcc'):raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='manager-dummy-tests-')
        cls.addClassCleanup(cls.temp.cleanup);cls.work=Path(cls.temp.name)
        cls.exe=cls.work/'dummy-test.exe'
        subprocess.run(['gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
            '-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),str(ROOT/'tests/test_manager_league_dummy.c'),
            str(ROOT/'source/manager_league_dummy.c'),str(ROOT/'source/manager_league_motion.c'),str(ROOT/'source/manager_league_plan.c'),str(ROOT/'source/gameplan_preset.c'),'-lm','-pthread','-o',str(cls.exe)],check=True,capture_output=True)

    def test_full_flow_and_new_process_reloads_identical_archive(self):
        work=self.work/'flow';work.mkdir()
        ran=subprocess.run([str(self.exe),'flow'],cwd=work,capture_output=True,timeout=20)
        self.assertEqual(ran.returncode,0,(ran.stdout+ran.stderr).decode(errors='replace'))
        save=work/'SaveData/manager-league-dummy-v2.dat';before=save.read_bytes()
        subprocess.run([str(self.exe),'reload'],cwd=work,check=True,capture_output=True,timeout=20)
        self.assertEqual(before,save.read_bytes())
        profile=(work/'SaveData/manager-league-profile-v2.dat').read_bytes()
        self.assertNotIn(b'Secret-Password-27',profile)

    def test_failed_purchase_preserves_wallet_and_save(self):
        work=self.work/'shopfail';work.mkdir()
        subprocess.run([str(self.exe),'shopfail'],cwd=work,check=True,capture_output=True,timeout=20)

    def test_medium_and_jumbo_fixed_draws_without_replacement(self):
        for tier in (1,2):
            with self.subTest(tier=tier):
                work=self.work/f'tier{tier}';work.mkdir()
                subprocess.run([str(self.exe),f'tier{tier}'],cwd=work,check=True,capture_output=True,timeout=20)

    def test_invalid_local_save_is_preserved_without_reroll(self):
        work=self.work/'corrupt';work.mkdir();(work/'SaveData').mkdir()
        save=work/'SaveData/manager-league-dummy-v1.dat';save.write_bytes(b'invalid original dummy save')
        before=hashlib.sha256(save.read_bytes()).hexdigest()
        subprocess.run([str(self.exe),'corrupt'],cwd=work,check=True,capture_output=True,timeout=20)
        self.assertEqual(before,hashlib.sha256(save.read_bytes()).hexdigest())

    def test_actual_switch_renderer_pages_and_vertex_budget(self):
        out=self.work/'previews'
        subprocess.run([sys.executable,str(ROOT/'tools/preview_manager_league_dummy.py'),str(out),'--geometry-only','--animate-shop'],
            cwd=ROOT,check=True,capture_output=True,timeout=60)
        expected={'01-registration','02-league-selection','03-club-selection','04-account','05-tutorial','06-dashboard','10-standings','12-team-info','19-player-shop','20-pack-pool','21-pack-result','30-live-goal','31-live-save','32-live-substitution','33-replay','40-week-schedule','40a-week-preparation','40b-week-match-days','40c-week-result'}
        frames={p.stem:json.loads(p.read_text()) for p in out.glob('*.json') if p.name!='PROVENANCE.json'}
        self.assertTrue(expected<=frames.keys())
        repeat=self.work/'repeat-previews'
        subprocess.run([sys.executable,str(ROOT/'tools/preview_manager_league_dummy.py'),str(repeat),'--geometry-only','--animate-shop'],
            cwd=ROOT,check=True,capture_output=True,timeout=60)
        for name,draws in frames.items():
            with self.subTest(page=name):
                self.assertEqual(draws,json.loads((repeat/(name+'.json')).read_text()))
                if name.startswith('motion-open'):
                    for draw in draws:
                        if draw['texture']>=200000:
                            # A revealed portrait keeps its square dimensions
                            # throughout the flip: contents cannot be squeezed.
                            xs=draw['vertices'][0::4];ys=draw['vertices'][1::4]
                            self.assertAlmostEqual(max(xs)-min(xs),.154,places=5)
                            self.assertAlmostEqual(max(ys)-min(ys),.274,places=5)
                self.assertLess(len(draws),384)
                self.assertLess(sum(len(d['vertices'])//24 for d in draws),4096)
                for draw in draws:
                    v=draw['vertices']
                    for i in range(0,len(v),4):
                        self.assertLessEqual(abs(v[i]),1.002)
                        self.assertLessEqual(abs(v[i+1]),1.002)

if __name__=='__main__':unittest.main()
