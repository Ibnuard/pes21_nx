"""Ten real-minute fixtures and lossless legacy/weekly archive lifecycle."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ManagerTimingV96Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('gcc'):raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='manager-timing-v96-')
        cls.addClassCleanup(cls.temp.cleanup);cls.root=Path(cls.temp.name);cls.exe=cls.root/'timing.exe'
        result=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
            '-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),str(ROOT/'tests/test_manager_timing_v96.c'),
            str(ROOT/'source/manager_league_motion.c'),str(ROOT/'source/manager_league_plan.c'),
            str(ROOT/'source/gameplan_preset.c'),'-lm','-pthread','-o',str(cls.exe)],capture_output=True)
        if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))

    def run_mode(self,mode,work):
        result=subprocess.run([str(self.exe),mode],cwd=work,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))

    def test_ten_minutes_many_events_late_join_half_time_and_no_overlap(self):
        work=self.root/'new';work.mkdir();self.run_mode('new',work)

    def test_goalless_first_fixture_preview_selects_another_scoring_broadcast(self):
        out=self.root/'goalless-preview'
        code=('import sys;sys.path.insert(0,sys.argv[1]);import preview_manager_league_dummy as p;'
              'p.DRIVER=p.DRIVER.replace("out->tv_sec=1793015700","out->tv_sec=1793015720")'
              '.replace("assert(first_goal);","assert(first_goal && goal_fixture>0);");'
              'sys.argv=["preview",sys.argv[2],"--geometry-only","--animate-broadcast"];p.main()')
        result=subprocess.run([sys.executable,'-c',code,str(ROOT/'tools'),str(out)],capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))
        self.assertTrue((out/'30-live-goal.json').is_file())
        self.assertTrue((out/'motion-goal-45.json').is_file())

    def test_read_only_v1_import_preserves_all_results_timestamps_and_events(self):
        work=self.root/'legacy';work.mkdir();self.run_mode('legacy',work)
        original=work/'SaveData/manager-league-dummy-v1.dat';before=original.read_bytes()
        self.run_mode('import',work);self.assertEqual(before,original.read_bytes())
        v2=work/'SaveData/manager-league-dummy-v2.dat';after=v2.read_bytes()
        self.run_mode('import',work);self.assertEqual(after,v2.read_bytes())

    def test_next_week_keeps_archived_roster_names_and_replays(self):
        work=self.root/'next';work.mkdir();self.run_mode('rollover',work)

    def test_legacy_user_can_start_ten_minute_week_without_resetting_account(self):
        work=self.root/'legacy-next';work.mkdir();self.run_mode('legacy',work)
        original=work/'SaveData/manager-league-dummy-v1.dat';before=hashlib.sha256(original.read_bytes()).hexdigest()
        self.run_mode('rollover-legacy',work)
        self.assertEqual(before,hashlib.sha256(original.read_bytes()).hexdigest())

    def test_interrupted_rollover_recovers_same_prepared_week_in_new_process(self):
        for mode,path in [('interrupt','manager-league-dummy-v2.dat.tmp'),('interrupt-profile','manager-league-profile-v2.dat.tmp')]:
            with self.subTest(stage=mode):
                work=self.root/mode;work.mkdir();self.run_mode(mode,work)
                (work/'SaveData'/path).rmdir()
                pending=(work/'SaveData/manager-league-transition-v2.dat').read_bytes()
                self.run_mode('recover',work)
                self.assertTrue(pending)
                self.assertTrue((work/'SaveData/manager-league-week-0001.dat').is_file())

if __name__=='__main__':unittest.main()
