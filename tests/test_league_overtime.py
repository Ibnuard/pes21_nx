"""Native handoff rules must honor Overtime independently of penalties."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LeagueOvertimeTests(unittest.TestCase):
    def test_frontend_handoff_rule_matrix(self):
        compiler = shutil.which('gcc')
        if not compiler:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory(prefix='league-overtime-') as temp:
            work = Path(temp)
            (work / 'ue4_hooks.h').write_text((ROOT / 'source/ue4_hooks.h').read_text().replace(
                '#include "so_util.h"', 'typedef struct so_module so_module;'))
            (work / 'league_overtime_frontend.inc').write_text((ROOT / 'source/competition_frontend.c').read_text().replace(
                '#include "ue4_hooks.h"', '#include <ue4_hooks.h>'))
            core = ['competition_entry_draft.c', 'cup_tournament.c', 'cup_save.c',
                    'league_tournament.c', 'league_save.c', 'master_league.c',
                    'master_league_save.c', 'master_league_frontend.c', 'manager_league_dummy.c',
                    'manager_league_client.c', 'manager_league_online.c', 'manager_online_json.c',
                    'manager_online_http.c', 'loading_popup.c', 'manager_league_motion.c',
                    'manager_league_plan.c', 'master_league_catalog.c', 'gameplan_preset.c']
            exe = work / 'overtime.exe'
            subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-I', str(work), '-I', str(ROOT / 'source'), '-I', str(ROOT / 'tests'),
                            str(ROOT / 'tests/test_league_overtime.c'),
                            *[str(ROOT / 'source' / name) for name in core], '-pthread', '-o', str(exe)], check=True)
            subprocess.run([str(exe)], cwd=work, check=True, timeout=30)
