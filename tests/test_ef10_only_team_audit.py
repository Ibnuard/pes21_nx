from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_JSON = ROOT / "data" / "exhibition_ef10_only_teams.json"
AUDIT_REPORT = ROOT / "EFOOTBALL10_ONLY_TEAMS.md"


class Ef10OnlyTeamAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        cls.rows = cls.payload["teams"]
        cls.by_id = {int(row["ef10_team_id"]): row for row in cls.rows}

    def test_generated_outputs_are_current(self) -> None:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "audit_ef10_only_teams.py"),
                "--check",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_content_id_and_inventory_counts(self) -> None:
        canonical = {
            key: value for key, value in self.payload.items() if key != "content_id"
        }
        expected = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()[:16]
        self.assertEqual(self.payload["content_id"], expected)
        self.assertEqual(self.payload["counts"]["ef10_only_raw_ids"], 451)
        self.assertEqual(self.payload["counts"]["configured_club_ef10_only"], 221)
        self.assertEqual(self.payload["counts"]["configured_national_ef10_only"], 109)
        self.assertEqual(self.payload["counts"]["alias_candidates"], 35)
        self.assertEqual(self.payload["counts"]["alias_review"], 4)
        self.assertEqual(self.payload["counts"]["surrogate_required"], 412)

    def test_inventory_is_sorted_and_unique(self) -> None:
        ids = [int(row["ef10_team_id"]) for row in self.rows]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(self.payload["policy"]["no_runtime_integration"])
        self.assertTrue(
            all(
                row["classification"]
                in {"alias_candidate", "alias_review", "surrogate_required"}
                for row in self.rows
            )
        )

    def test_focus_team_classification(self) -> None:
        inter_miami = self.by_id[5738]
        self.assertEqual(inter_miami["ef10_name"], "Miami BP")
        self.assertEqual(inter_miami["classification"], "surrogate_required")
        self.assertEqual(inter_miami["ef10_roster_count"], 27)
        self.assertEqual(inter_miami["direct_shared_player_count"], 8)
        self.assertEqual(inter_miami["candidate_pes21_teams"], [])

        al_nassr = self.by_id[18961]
        self.assertEqual(al_nassr["classification"], "alias_candidate")
        self.assertEqual(
            al_nassr["candidate_pes21_teams"],
            [{"pes21_team_id": 68113, "pes21_name": "AL NASSR"}],
        )
        self.assertEqual(al_nassr["direct_shared_player_count"], 0)

        shanghai = self.by_id[21557]
        self.assertEqual(shanghai["classification"], "alias_review")
        self.assertEqual(
            [entry["pes21_team_id"] for entry in shanghai["candidate_pes21_teams"]],
            [5173, 70709],
        )

    def test_report_contains_no_runtime_claim(self) -> None:
        report = AUDIT_REPORT.read_text(encoding="utf-8")
        self.assertIn("No runtime selector or database files are changed", report)
        self.assertIn("Miami BP", report)
        self.assertIn("Al Nassr FC", report)


if __name__ == "__main__":
    unittest.main()
