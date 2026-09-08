from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from plan_ef10_famous_team_imports import (  # noqa: E402
    asset_candidates,
    load_pesdb_identity_map,
    load_pesdb_rosters,
    load_pesdb_snapshot,
    map_pesdb_roster_to_targets,
    pesdb_roster_coverage,
)
from convert_efootball10_players import PES21_ABILITY_BITS  # noqa: E402


MANIFEST = ROOT / "data" / "ef10_famous_team_imports.json"


class FamousTeamManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_curated_and_release_enabled(self) -> None:
        self.assertEqual(self.payload["schema_version"], 1)
        self.assertTrue(self.payload["policy"]["allow_runtime_integration"])
        self.assertEqual(
            self.payload["policy"]["player_value_source"],
            "https://pesdb.net/efootball (Authentic mode)",
        )
        teams = self.payload["teams"]
        self.assertGreaterEqual(len(teams), 8)
        ids = [int(row["ef10_team_id"]) for row in teams]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(126, ids)
        self.assertIn(18961, ids)
        self.assertIn(1264, ids)
        self.assertNotIn(5738, ids)  # Inter Miami is already the stable canary path.

    def test_physical_slots_are_unique_and_priorities_contiguous(self) -> None:
        teams = self.payload["teams"]
        priorities = sorted(int(row["priority"]) for row in teams)
        self.assertEqual(priorities, list(range(1, len(teams) + 1)))
        slots = [int(row["physical_team_id"]) for row in teams if row["physical_team_id"] is not None]
        self.assertEqual(len(slots), len(set(slots)))

    def test_asset_contract_requires_badge_and_three_uniforms(self) -> None:
        paths = asset_candidates(Path("assets"), 126)
        self.assertGreaterEqual(len(paths["badge"]), 2)
        self.assertEqual(len(paths["uniform"]), 3)
        self.assertTrue(all("126_DEF_" in path.name for path in paths["uniform"]))

    def test_pesdb_coverage_is_a_fail_closed_release_gate(self) -> None:
        identity = load_pesdb_identity_map({
            "schema_version": 1,
            "authority": "https://pesdb.net/efootball",
            "policy": {"pesdb_only": True, "pes21_values_allowed": False},
            "map": {"10": 10},
        })
        snapshot = load_pesdb_snapshot({
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "players": {
                "10": {
                    "source": "authentic",
                    "base_stats": {name: 75 for name in PES21_ABILITY_BITS},
                }
            },
        })
        coverage = pesdb_roster_coverage([10, 20], identity, snapshot)
        self.assertFalse(coverage["identity_complete"])
        self.assertFalse(coverage["authentic_snapshot_complete"])
        self.assertEqual(coverage["missing_identity_player_ids"], [20])
        self.assertEqual(coverage["missing_snapshot_player_ids"], [20])

    def test_pes21_or_standard_values_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_pesdb_identity_map({
                "schema_version": 1,
                "authority": "https://pesdb.net/efootball",
                "policy": {"pesdb_only": True, "pes21_values_allowed": True},
                "map": {},
            })
        with self.assertRaises(ValueError):
            load_pesdb_snapshot({
                "schema_version": 1,
                "source": "standard",
                "authority": "https://pesdb.net/efootball",
                "players": {},
            })

    def test_current_roster_requires_authentic_pesdb_values(self) -> None:
        payload = {
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "policy": {
                "pesdb_rosters_only": True,
                "pesdb_player_values_only": True,
                "pes21_roster_or_value_fallback": False,
            },
            "teams": {
                "126": {
                    "pesdb_team_id": 126,
                    "player_ids": [10],
                    "player_count": 1,
                    "complete": True,
                }
            },
            "players": {
                "10": {
                    "player_id": 10,
                    "source": "authentic",
                    "base_stats": {name: 70 for name in PES21_ABILITY_BITS},
                }
            },
        }
        teams, players = load_pesdb_rosters(payload)
        self.assertTrue(teams[126]["complete"])
        self.assertIn(10, players)
        payload["policy"]["pes21_roster_or_value_fallback"] = True
        with self.assertRaises(ValueError):
            load_pesdb_rosters(payload)

    def test_current_pesdb_ids_map_only_to_reviewed_physical_slots(self) -> None:
        coverage = map_pesdb_roster_to_targets(
            [10, 20, 30],
            target_ids={10, 700},
            identity_map={200: 20},
            target_map={200: 700},
        )
        self.assertFalse(coverage["complete"])
        self.assertEqual(coverage["mapped_players"], 2)
        self.assertEqual(coverage["missing_target_player_ids"], [30])

    def test_pesdb_keyed_target_map_is_checked_before_legacy_identity(self) -> None:
        coverage = map_pesdb_roster_to_targets(
            [9001],
            target_ids={7001, 9001},
            identity_map={1234: 9001},
            target_map={9001: 7001},
        )
        self.assertTrue(coverage["complete"])
        self.assertEqual(coverage["map"][0]["target_player_id"], 7001)
        self.assertEqual(coverage["map"][0]["mode"], "reviewed_pesdb_target_map")
        self.assertEqual(coverage["reviewed_pesdb_target_maps"], 1)


if __name__ == "__main__":
    unittest.main()
