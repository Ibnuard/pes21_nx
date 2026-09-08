from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from import_pesdb_efootball import (  # noqa: E402
    POSITION_NAMES,
    build_snapshot,
    canonical_content_id,
    extract_progression_json,
    normalize_player_payload,
    parse_player_page,
    parse_sitemap,
    parse_sitemap_locations,
    write_snapshot,
)


PROGRESSION = {
    "source": "authentic",
    "playerId": "7511",
    "position": 11,
    "positions": POSITION_NAMES,
    "height": 170,
    "weakFootAccuracy": 1,
    "baseOverall": 87,
    "databaseMaxOverall": 93,
    "baseStats": {
        name: 40 + (index % 50)
        for index, name in enumerate(
            (
                "offensive_awareness", "ball_control", "dribbling", "tight_possession",
                "low_pass", "lofted_pass", "finishing", "heading", "set_piece_taking",
                "curl", "speed", "acceleration", "kicking_power", "jumping",
                "physical_contact", "balance", "stamina", "defensive_awareness",
                "tackling", "aggression", "defensive_engagement", "gk_awareness",
                "gk_catching", "gk_parrying", "gk_reflexes", "gk_reach",
            )
        )
    },
    "compare": {
        "source": "authentic",
        "playerId": "7511",
        "playerName": "Lionel Messi",
        "playerUrl": "/efootball/authentic/players/lionel-messi-7511",
        "teamName": "Miami BP",
        "nationality": "Argentina",
        "attackingPlayingStyle": "Classic No. 10",
        "defensivePlayingStyle": "Basic",
        "playerSkills": ["Double Touch", "One Touch Pass"],
        "aiPlayingStyles": ["Trickster"],
        "details": {
            "weak_foot_usage": "Rarely",
            "weak_foot_accuracy": "Medium",
            "form": "Unwavering",
            "injury_resistance": "Medium",
        },
    },
}


class PesdbImporterTests(unittest.TestCase):
    def test_sitemap_parser_keeps_base_player_urls(self) -> None:
        xml = """<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
          <url><loc>https://pesdb.net/efootball/players/lionel-messi-7511</loc></url>
          <url><loc>https://pesdb.net/pes2021/players/old-7511</loc></url>
          <url><loc>https://pesdb.net/efootball/players/ronaldo-4522</loc></url>
        </urlset>"""
        self.assertEqual(
            parse_sitemap(xml),
            {
                7511: "https://pesdb.net/efootball/players/lionel-messi-7511",
                4522: "https://pesdb.net/efootball/players/ronaldo-4522",
            },
        )

    def test_sitemap_index_parser_returns_child_locations(self) -> None:
        xml = """<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">
          <sitemap><loc>https://pesdb.net/sitemaps/players-1.xml</loc></sitemap>
          <sitemap><loc>https://pesdb.net/sitemaps/players-2.xml</loc></sitemap>
        </sitemapindex>"""
        self.assertEqual(
            parse_sitemap_locations(xml),
            [
                "https://pesdb.net/sitemaps/players-1.xml",
                "https://pesdb.net/sitemaps/players-2.xml",
            ],
        )

    def test_progression_json_and_normalization_preserve_pesdb_values(self) -> None:
        page = (
            '<dl><div><dt>Stronger Foot</dt><dd>Left foot</dd></div>'
            '<div><dt>Weight</dt><dd>67 kg</dd></div></dl>'
            '<script type="application/json" id="player-progression-data">'
            + json.dumps(PROGRESSION)
            + "</script>"
        )
        self.assertEqual(extract_progression_json(page)["playerId"], "7511")
        parsed = parse_player_page(
            page,
            requested_player_id=7511,
            page_url="https://pesdb.net/efootball/authentic/players/lionel-messi-7511",
        )
        self.assertEqual(parsed["base_overall"], 87)
        self.assertEqual(parsed["primary_position"], "SS")
        self.assertEqual(parsed["base_stats"]["finishing"], PROGRESSION["baseStats"]["finishing"])
        self.assertEqual(parsed["details"]["stronger_foot"], "Left foot")
        self.assertIn("player_skills", parsed["unsupported_target_fields"])

    def test_missing_verified_stat_is_rejected(self) -> None:
        broken = json.loads(json.dumps(PROGRESSION))
        del broken["baseStats"]["finishing"]
        with self.assertRaises(ValueError):
            normalize_player_payload(broken, requested_player_id=7511)

    def test_snapshot_is_deterministic_except_fetch_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = build_snapshot(
                [7511],
                standard_urls={},
                cache_dir=Path(directory),
                offline=True,
            )
            # An offline cache miss is explicit and does not fabricate a row.
            self.assertEqual(first["counts"]["failed"], 1)
            self.assertIn("sitemap", first["failures"]["7511"])
            self.assertEqual(first["content_id"], canonical_content_id(first))
            target = Path(directory) / "snapshot.json"
            write_snapshot(target, first)
            self.assertEqual(json.loads(target.read_text())["content_id"], first["content_id"])


if __name__ == "__main__":
    unittest.main()
