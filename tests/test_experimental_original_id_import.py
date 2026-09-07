"""Focused checks for the isolated Inter Miami original-ID experiment."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EF10_DIR = ROOT / "local-debug/efootball10-audit/tables/common/etc/pesdb"
PES21_DIR = ROOT / (
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb"
)
MANIFEST = ROOT / "data/experimental_original_inter_miami.json"
TOOL = ROOT / "tools/experimental_import_ef10_original.py"


@unittest.skipUnless(
    (EF10_DIR / "Player.bin").is_file()
    and (PES21_DIR / "Player.bin").is_file(),
    "local EF10/PES21 audit tables are not available",
)
class ExperimentalOriginalIdImportTests(unittest.TestCase):
    def run_import(self, mode: str) -> tuple[dict, Path]:
        with tempfile.TemporaryDirectory(prefix="pes21-original-id-") as temporary:
            output = Path(temporary) / mode
            subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--root",
                    str(ROOT),
                    "--manifest",
                    str(MANIFEST),
                    "--mode",
                    mode,
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            report = json.loads(
                (output / "validation-report.json").read_text(encoding="utf-8")
            )
            # Copy the report data before TemporaryDirectory removes the files.
            return report, output

    def test_canary_keeps_fixed_count_and_exposes_original_id(self) -> None:
        report, _output = self.run_import("canary")
        self.assertEqual(report["team"]["ef10_team_id"], 5738)
        self.assertEqual(report["counts"]["selected_players"], 9)
        self.assertEqual(report["counts"]["original_id_players"], 1)
        self.assertTrue(report["invariants"]["player_record_count_unchanged"])
        self.assertTrue(report["invariants"]["player_assignment_byte_identical"])
        self.assertTrue(report["invariants"]["original_ids_present"])
        self.assertTrue(report["invariants"]["donor_ids_absent"])
        self.assertTrue(report["invariants"]["install_version_ids_match_player_ids"])
        self.assertTrue(report["invariants"]["strictly_monotonic_player_ids"])
        self.assertEqual(
            report["counts"]["shared_players_with_existing_pes21_memberships"], 7
        )
        canary = next(
            player for player in report["players"] if player["ef10_player_id"] == 153007
        )
        self.assertEqual(canary["target_pes21_id"], 153007)
        self.assertEqual(canary["mode"], "original_id_retired_slot")
        self.assertIsNotNone(canary["donor_pes21_id"])
        messi = next(
            row for row in report["shared_memberships"] if row["player_id"] == 7511
        )
        actions = {
            (membership["pes21_team_id"], membership["cleanup_action"])
            for membership in messi["existing_pes21_memberships"]
        }
        self.assertIn((50, "preserve_national_membership"), actions)
        self.assertIn((108, "remove_legacy_club_membership"), actions)

    def test_xi_allocates_distinct_original_ids_without_native_donors(self) -> None:
        report, _output = self.run_import("xi")
        self.assertEqual(report["counts"]["selected_players"], 11)
        self.assertEqual(report["counts"]["original_id_players"], 3)
        original_rows = [
            player
            for player in report["players"]
            if player["mode"] == "original_id_retired_slot"
        ]
        self.assertEqual(
            {int(player["target_pes21_id"]) for player in original_rows},
            {153007, 160365, 157971},
        )
        donors = [int(player["donor_pes21_id"]) for player in original_rows]
        self.assertEqual(len(donors), len(set(donors)))
        self.assertTrue(report["invariants"]["known_native_donor_references"] is False)
        self.assertTrue(report["invariants"]["donor_ids_removed_from_delete_list"])

    def test_manifest_explicitly_defers_team_integration(self) -> None:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(payload["team"]["ef10_team_id"], 5738)
        self.assertEqual(payload["team"]["pes21_physical_team_id"], 2473)
        self.assertEqual(payload["team"]["pes21_physical_team_name"], "PUNTIHUERVA")
        self.assertEqual(payload["team"]["slot_policy"], "non_selector_physical_slot")
        self.assertFalse(payload["policy"]["runtime_integration"])
        self.assertFalse(payload["policy"]["team_record_import"])


if __name__ == "__main__":
    unittest.main()
