"""Paid-pack recovery, current ranking, match sections and real tape details."""
from pathlib import Path
import shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]

class ManagerReviewV99Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('gcc'):raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='manager-review-v99-');cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.exe=cls.root/'review.exe'
        result=subprocess.run(['gcc','-std=c11','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
            '-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),str(ROOT/'tests/test_manager_review_v99.c'),
            str(ROOT/'source/manager_league_motion.c'),str(ROOT/'source/manager_league_plan.c'),
            str(ROOT/'source/gameplan_preset.c'),'-lm','-pthread','-o',str(cls.exe)],capture_output=True)
        if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
    def run_mode(self,mode,work=None):
        if work is None:work=self.root/mode;work.mkdir()
        r=subprocess.run([str(self.exe),mode],cwd=work,capture_output=True,timeout=60)
        self.assertEqual(r.returncode,0,(r.stdout+r.stderr).decode(errors='replace'));return work
    def test_charge_at_open_then_select_without_second_debit(self):self.run_mode('flow')
    def test_pending_pack_finishes_even_after_matchday_and_reward(self):self.run_mode('pending-prize')
    def test_failed_purchase_never_debits_wallet(self):self.run_mode('debit-fail')
    def test_new_process_resumes_same_paid_pool_and_selection(self):self.run_mode('recover-paid',self.run_mode('paid-exit'))
    def test_interrupted_journal_rotation_resumes_paid_selection(self):
        work=self.root/'rotation';work.mkdir();self.run_mode('paid-exit',work)
        journal=work/'SaveData/manager-league-pack-v99.dat';journal.replace(journal.with_suffix('.dat.bak'))
        self.run_mode('recover-paid',work)
    def test_corrupt_paid_journal_preserves_wallet_and_collection(self):
        work=self.root/'corrupt-paid';work.mkdir();self.run_mode('paid-exit',work)
        journal=work/'SaveData/manager-league-pack-v99.dat';content=bytearray(journal.read_bytes());content[40]^=1;journal.write_bytes(content)
        before={p.name:p.read_bytes() for p in (work/'SaveData').glob('*.dat')}
        self.run_mode('recover-corrupt',work)
        self.assertEqual(before,{p.name:p.read_bytes() for p in (work/'SaveData').glob('*.dat')})
    def test_interrupted_debit_and_grant_recover_once(self):
        for action in ('debit','grant'):
            with self.subTest(stage=action):
                work=self.run_mode(action+'-interrupt');(work/'SaveData/manager-league-profile-v2.dat.tmp').rmdir()
                self.run_mode('recover-'+action,work)
    def test_ranking_resets_on_fortnight_boundary_and_champions_survive(self):self.run_mode('ranking')
    def test_live_scheduled_and_ended_are_separate_ordered_sections(self):self.run_mode('schedule')
    def test_touchline_uses_elapsed_tape_and_keeps_live_playing(self):self.run_mode('touchline')
    def test_new_passes_link_actual_carriers_and_receivers(self):self.run_mode('passes')

if __name__=='__main__':unittest.main()
