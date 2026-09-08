from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from import_pesdb_identity_map import rekey_snapshot  # noqa: E402
from resolve_pesdb_player_ids import (  # noqa: E402
    normalize_name,
    resolve_identities,
    sitemap_slug_name,
)


class IdentityResolutionTests(unittest.TestCase):
    def test_name_normalization_and_slug(self) -> None:
        self.assertEqual(normalize_name("Óscar Ustari"), "oscar ustari")
        self.assertEqual(
            sitemap_slug_name("https://pesdb.net/efootball/players/oscar-ustari-34430"),
            "oscar ustari",
        )

    def test_exact_name_is_review_only_until_explicitly_accepted(self) -> None:
        players = {
            9001: SimpleNamespace(name="New Player"),
            9002: SimpleNamespace(name="Shared Name"),
        }
        sitemap = {
            7001: "https://pesdb.net/efootball/players/new-player-7001",
            7002: "https://pesdb.net/efootball/players/shared-name-7002",
            7003: "https://pesdb.net/efootball/players/shared-name-7003",
        }
        payload = resolve_identities(players, sitemap, [9001, 9002])
        self.assertEqual(payload["counts"]["accepted"], 0)
        self.assertEqual(payload["rows"][0]["status"], "exact_name_unique")
        self.assertEqual(payload["rows"][1]["status"], "ambiguous_name")
        accepted = resolve_identities(
            players, sitemap, [9001], accept_exact_name=True
        )
        self.assertEqual(accepted["map"], {"9001": 7001})

    def test_direct_id_requires_matching_name(self) -> None:
        players = {
            7001: SimpleNamespace(name="Correct Name"),
            7002: SimpleNamespace(name="Old Name"),
        }
        sitemap = {
            7001: "https://pesdb.net/efootball/players/correct-name-7001",
            7002: "https://pesdb.net/efootball/players/new-name-7002",
        }
        payload = resolve_identities(players, sitemap, [7001, 7002])
        self.assertEqual(payload["counts"]["direct_id_exact"], 1)
        self.assertEqual(payload["counts"]["direct_id_name_mismatch"], 1)
        self.assertEqual(payload["map"], {"7001": 7001})

    def test_rekey_snapshot_preserves_remote_provenance(self) -> None:
        payload = rekey_snapshot(
            {9001: 7001, 9002: 7002},
            {
                "players": {
                    "7001": {"player_id": 7001, "player_name": "One", "base_stats": {}},
                },
                "failures": {"7002": "not found"},
            },
        )
        self.assertEqual(payload["counts"], {
            "requested": 2,
            "fetched": 1,
            "failed": 1,
            "verified_ability_rows": 1,
        })
        self.assertEqual(payload["players"]["9001"]["player_id"], 9001)
        self.assertEqual(payload["players"]["9001"]["pesdb_player_id"], 7001)
        self.assertEqual(payload["failures"], {"9002": "not found"})


if __name__ == "__main__":
    unittest.main()
