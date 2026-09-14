"""Contracts for the all-region national-team kit candidate."""

import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/national_team_kit_overrides.json"
CATALOG = ROOT / "data/exhibition_team_catalog.json"
PACK = ROOT / "local-debug/national-team-all-kits-v2"


class NationalTeamKitTests(unittest.TestCase):
    def test_manifest_is_generated_and_covers_every_national_team(self):
        subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_national_team_kit_manifest.py"), "--check"],
            cwd=ROOT,
            check=True,
        )
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        expected = {int(row["physical_team_id"]) for row in catalog["teams"] if row["kind"] == "national"}
        teams = [team for region in manifest["leagues"] for team in region["teams"]]
        self.assertEqual({int(team["team_id"]) for team in teams}, expected)
        self.assertEqual(len(teams), 89)
        self.assertTrue(all(team["team_bin_policy"] == "preserve_existing" for team in teams))
        self.assertEqual(
            Counter(region["key"] for region in manifest["leagues"] for _ in region["teams"]),
            Counter(
                {
                    "national_europe": 42,
                    "national_africa": 14,
                    "national_north_america": 6,
                    "national_south_america": 10,
                    "national_asia_oceania": 17,
                }
            ),
        )

    @unittest.skipUnless((PACK / "asset-report.json").is_file(), "local proprietary kit pack unavailable")
    def test_local_candidate_converted_all_kits_without_missing_slots(self):
        report = json.loads((PACK / "asset-report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["teams"]), 89)
        self.assertEqual(report["pending_native_slots"], [])
        self.assertEqual(Counter(row["status"] for row in report["teams"]), {"converted": 89})
        self.assertEqual(sum(len(row["kits"]) for row in report["teams"]), 267)
        self.assertTrue(all(len(row["kits"]) == 3 for row in report["teams"]))

    @unittest.skipUnless((PACK / "validation-report.json").is_file(), "local proprietary kit pack unavailable")
    def test_local_candidate_only_replaces_expected_outer_payloads(self):
        report = json.loads((PACK / "validation-report.json").read_text(encoding="utf-8"))
        self.assertEqual(
            report["obb"]["changed_members"],
            ["Expansion/dt120_mobile_all.cpk", "Expansion/dt200_mobile_all.cpk"],
        )
        self.assertEqual(report["obb"]["unrelated_members_byte_identical"], 22)
        self.assertEqual(report["obb"]["size"], 1410308096)


if __name__ == "__main__":
    unittest.main()
