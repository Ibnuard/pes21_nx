"""Production calendar, transactional entry grant, club menus and notice input."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ManagerReviewV98Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('gcc'):raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='manager-review-v98-');cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.executables={}
        for dev in (0,1):
            exe=cls.root/f'review-{dev}.exe'
            result=subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                f'-DMANAGER_LEAGUE_DEV_CLOCK={dev}','-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),
                str(ROOT/'tests/test_manager_review_v98.c'),str(ROOT/'source/manager_league_motion.c'),
                str(ROOT/'source/manager_league_plan.c'),str(ROOT/'source/gameplan_preset.c'),'-lm','-pthread','-o',str(exe)],capture_output=True)
            if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
            cls.executables[dev]=exe

    def run_mode(self,mode,dev=1):
        work=self.root/f'{mode}-{dev}';work.mkdir()
        result=subprocess.run([str(self.executables[dev]),mode],cwd=work,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))

    def test_two_seasons_per_week_and_once_only_entry_grants(self):self.run_mode('calendar')
    def test_opponent_profile_readonly_plan_history_and_modal_input(self):self.run_mode('clubs')
    def test_dev_clock_after_next_league(self):self.run_mode('dev')
    def test_release_can_disable_development_clock(self):self.run_mode('dev',0)

    def test_exact_podium_rewards_and_no_repeat_credit(self):
        for position in range(1,5):
            with self.subTest(position=position):self.run_mode(f'money-{position}')

    def test_reward_recovers_once_after_interrupted_profile_write(self):
        self.run_mode('money-interrupt')
        work=self.root/'money-interrupt-1';(work/'SaveData/manager-league-profile-v2.dat.tmp').rmdir()
        result=subprocess.run([str(self.executables[1]),'money-recover'],cwd=work,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))

    def test_entry_write_failures_preserve_or_recover_exactly_one_grant(self):
        self.run_mode('entry-preflight')
        for mode,path in [('entry-save','manager-league-dummy-v2.dat.tmp'),
                          ('entry-profile','manager-league-profile-v2.dat.tmp')]:
            with self.subTest(stage=mode):
                self.run_mode(mode);work=self.root/f'{mode}-1';(work/'SaveData'/path).rmdir()
                result=subprocess.run([str(self.executables[1]),'money-recover'],cwd=work,capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))

    def test_stale_or_corrupt_wallet_journal_cannot_overwrite_newer_account(self):
        for mode in ('money-stale','money-interrupt'):
            with self.subTest(stage=mode):
                # Unique work directories also allow the separate interrupted-write test.
                work=self.root/f'reject-{mode}';work.mkdir()
                result=subprocess.run([str(self.executables[1]),mode],cwd=work,capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))
                if mode=='money-interrupt':
                    (work/'SaveData/manager-league-profile-v2.dat.tmp').rmdir()
                    path=work/'SaveData/manager-league-wallet-v98.dat';data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
                result=subprocess.run([str(self.executables[1]),'money-reject'],cwd=work,capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,(result.stdout+result.stderr).decode(errors='replace'))

if __name__=='__main__':unittest.main()
