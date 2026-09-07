"""Checks for the isolated Inter Miami original-ID CPK canary boundary."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_inter_miami_original_canary.py"
ARTIFACT = ROOT / "local-debug" / "efootball10-original-inter-miami-canary"
PACKAGE_REPORT = ARTIFACT / "cpk" / "canary-package-validation.json"


class InterMiamiCanaryPackagingTests(unittest.TestCase):
    def test_preflight_accepts_only_matching_source_cpk(self):
        required = (
            ARTIFACT / "validation-report.json",
            ARTIFACT / "cpk-replacement-manifest.json",
            ROOT
            / "local-debug"
            / "efootball10-audit"
            / "old-cpk"
            / "dt200_mobile_all.cpk",
        )
        if not all(path.is_file() for path in required):
            self.skipTest("local Inter Miami canary inputs are unavailable")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["check"], "pass")
        self.assertEqual(payload["preflight"]["member_count"], 2435)
        self.assertEqual(
            payload["preflight"]["replaced_members"],
            [
                "common/etc/pesdb/InstallVersionPlayer.bin",
                "common/etc/pesdb/Player.bin",
                "common/etc/pesdb/PlayerDeleteList.bin",
            ],
        )

    def test_canary_report_is_not_a_release_integration(self):
        if not PACKAGE_REPORT.is_file():
            self.skipTest("local Inter Miami canary report is unavailable")
        payload = json.loads(PACKAGE_REPORT.read_text(encoding="utf-8"))
        self.assertFalse(payload["runtime_integration"])
        self.assertFalse(payload["team_record_import"])
        self.assertFalse(payload["stable_release_tree_touched"])
        self.assertEqual(payload["output"]["unrelated_members_byte_identical"], 2432)
        self.assertFalse(payload["rollback"]["release_obb_modified"])


if __name__ == "__main__":
    unittest.main()
