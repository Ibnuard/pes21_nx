from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORE = ['master_league.c', 'master_league_save.c', 'gameplan_preset.c',
        'league_tournament.c', 'cup_tournament.c']

class MasterLeagueTests(unittest.TestCase):
    def test_world_career(self):
        cc=shutil.which('gcc')
        if not cc:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'world-tests.exe'
            subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',
                '-I',str(ROOT/'source'),'-I',str(ROOT/'tests'),str(ROOT/'tests/test_master_league_world.c'),
                *[str(ROOT/'source'/name) for name in CORE],'-o',str(binary)],check=True)
            subprocess.run([str(binary)],cwd=temp,check=True,timeout=60)

    def test_optional_local_paired_catalog(self):
        catalog=ROOT/'local-debug/master-league-v1/master_league_catalog_generated.inc'
        leagues=ROOT/'local-debug/fl26-league-curated-v3/fl26_league_catalog_generated.h'
        cc=shutil.which('gcc')
        if not cc or not catalog.is_file() or not leagues.is_file():
            self.skipTest('Optional paired career metadata/compiler unavailable; regenerate locally')
        with tempfile.TemporaryDirectory() as temp:
            binary=Path(temp)/'career-local-tests.exe'
            shutil.copy2(leagues, Path(temp)/'local_leagues.h')
            shutil.copy2(catalog, Path(temp)/'local_career.inc')
            shutil.copytree(ROOT/'source', Path(temp)/'source')
            shutil.copy2(ROOT/'tests/test_master_league_local.c', Path(temp)/'local_test.c')
            subprocess.run([cc,'-O2','-std=c11','-Wall','-Wextra','-Werror',
                '-Isource','-I.','-include','local_leagues.h',
                '-DML_CATALOG_INCLUDE=<local_career.inc>', 'local_test.c',
                'source/master_league_catalog.c',
                *['source/'+name for name in CORE],'-o',binary.name],cwd=temp,check=True)
            subprocess.run([str(binary)],cwd=temp,check=True,timeout=60)

    def test_career_frontend(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / 'career-ui-tests.exe'
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I', str(ROOT/'source'), str(ROOT/'tests/test_master_league_frontend.c'),
                str(ROOT/'source/master_league_frontend.c'),
                *[str(ROOT/'source'/name) for name in CORE], '-o', str(binary)], check=True)
            subprocess.run([str(binary)], cwd=temp, check=True, timeout=60)

    def test_career_core(self):
        cc = shutil.which('gcc')
        if not cc:
            self.skipTest('Host C compiler unavailable')
        with tempfile.TemporaryDirectory() as temp:
            binary = Path(temp) / 'career-tests.exe'
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-I', str(ROOT/'source'), str(ROOT/'tests/test_master_league.c'),
                *[str(ROOT/'source'/name) for name in CORE], '-o', str(binary)], check=True)
            subprocess.run([str(binary)], cwd=temp, check=True, timeout=60)

if __name__ == '__main__':
    unittest.main()
