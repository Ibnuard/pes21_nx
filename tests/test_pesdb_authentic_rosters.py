from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from import_pesdb_authentic_rosters import (  # noqa: E402
    build_roster_snapshot,
    merge_player_snapshots,
    merge_roster_snapshot,
)
from import_pesdb_efootball import (  # noqa: E402
    parse_authentic_team_page,
    parse_authentic_team_table,
)


class AuthenticRosterTests(unittest.TestCase):
    def test_team_page_parser_deduplicates_cards_and_reads_pagination(self) -> None:
        page = """
        <span>Page 1 of 2</span>
        <a href="/efootball/authentic/players/lionel-messi-7511">one</a>
        <a href="/efootball/authentic/players/lionel-messi-7511">duplicate</a>
        <a href="/efootball/authentic/players/noah-allen-153007">two</a>
        """
        self.assertEqual(parse_authentic_team_page(page), ([7511, 153007], 2))

    def test_team_table_parser_reads_club_shirt_number(self) -> None:
        page = """
        <span>Page 1 of 1</span>
        <table><tr>
          <td data-copy-value="SS">SS</td>
          <td data-copy-value="Lionel Messi"><a href="/efootball/authentic/players/lionel-messi-7511">Lionel Messi</a></td>
          <td data-copy-value="10">10</td>
        </tr><tr>
          <td data-copy-value="GK">GK</td>
          <td data-copy-value="No Number"><a href="/efootball/authentic/players/no-number-153007">No Number</a></td>
          <td data-copy-value="">-</td>
        </tr></table>
        """
        self.assertEqual(
            parse_authentic_team_table(page),
            ([
                {"player_id": 7511, "shirt_number": 10},
                {"player_id": 153007, "shirt_number": None},
            ], 1),
        )

    def test_existing_authentic_snapshot_is_reused_without_pes21_fallback(self) -> None:
        # Patch the network-facing roster helper; player rows are supplied by
        # the existing PESDB snapshot and no binary/PES21 input exists here.
        import import_pesdb_authentic_rosters as module

        original = module.fetch_authentic_team_roster
        module.fetch_authentic_team_roster = lambda *_args, **_kwargs: [
            {"player_id": 10, "shirt_number": 7}
        ]
        try:
            payload = build_roster_snapshot(
                [126],
                existing_players={10: {"source": "authentic", "player_name": "A"}},
                standard_urls={},
                cache_dir=Path("unused"),
                timeout=1.0,
                delay=0.0,
                retries=0,
                offline=True,
            )
        finally:
            module.fetch_authentic_team_roster = original
        self.assertEqual(payload["counts"]["complete_teams"], 1)
        self.assertFalse(payload["policy"]["pes21_roster_or_value_fallback"])
        self.assertEqual(payload["teams"]["126"]["player_ids"], [10])
        self.assertEqual(payload["teams"]["126"]["shirt_numbers"], {"10": 7})

    def test_snapshot_merge_rejects_conflicting_authentic_rows(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            base = {
                "schema_version": 1,
                "source": "authentic",
                "authority": "https://pesdb.net/efootball",
                "players": {"10": {"source": "authentic", "player_name": "A"}},
            }
            first.write_text(json.dumps(base), encoding="utf-8")
            second.write_text(
                json.dumps({**base, "players": {"10": {"source": "authentic", "player_name": "B"}}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                merge_player_snapshots([first, second])

    def test_existing_roster_can_be_completed_from_extra_snapshots(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            roster = Path(directory) / "roster.json"
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            roster.write_text(
                json.dumps({
                    "schema_version": 1,
                    "source": "authentic",
                    "authority": "https://pesdb.net/efootball",
                    "teams": {"126": {"player_ids": [10, 20]}},
                    "players": {},
                    "failures": {"teams": {}, "players": {}},
                }),
                encoding="utf-8",
            )
            row = lambda name: {"source": "authentic", "player_name": name}
            first.write_text(json.dumps({"schema_version": 1, "source": "authentic", "authority": "https://pesdb.net/efootball", "players": {"10": row("A")}}), encoding="utf-8")
            second.write_text(json.dumps({"schema_version": 1, "source": "authentic", "authority": "https://pesdb.net/efootball", "players": {"20": row("B")}}), encoding="utf-8")
            result = merge_roster_snapshot(roster, player_snapshots=[first, second])
            self.assertEqual(result["counts"]["failed_players"], 0)
            self.assertTrue(result["teams"]["126"]["complete"])


if __name__ == "__main__":
    unittest.main()
