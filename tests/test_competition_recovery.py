"""Exercise real Cup/League input, result and save failure/retry paths."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CompetitionRecoveryTests(unittest.TestCase):
    def test_recovery(self):
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            (work / "ue4_hooks.h").write_text((ROOT / "source/ue4_hooks.h").read_text().replace(
                '#include "so_util.h"', 'typedef struct so_module so_module;'))
            shutil.copy2(ROOT / "source/competition_frontend.c", work / "competition_frontend.c")
            binary = work / "recovery.exe"
            core = ["competition_entry_draft.c", "cup_tournament.c", "cup_save.c",
                    "league_tournament.c", "league_save.c", "master_league.c",
                    "master_league_save.c", "master_league_frontend.c", "manager_league_dummy.c", "manager_league_client.c", "manager_league_online.c", "manager_online_json.c", "manager_online_http.c", "loading_popup.c", "manager_league_motion.c", "manager_league_plan.c",
                    "master_league_catalog.c", "gameplan_preset.c"]
            clang = "clang" in subprocess.check_output([compiler, "--version"], text=True).lower()
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                *(["-Wno-constant-logical-operand"] if clang else []),
                "-I", str(work), "-I", str(ROOT / "source"),
                str(ROOT / "tests/test_competition_recovery.c"), str(work / "competition_frontend.c"),
                *[str(ROOT / "source" / name) for name in core], "-o", str(binary)], check=True)
            subprocess.run([str(binary)], cwd=work, check=True, timeout=30)
