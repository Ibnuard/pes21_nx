"""Integrity checks for the generated Exhibition team catalog."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from exhibition_team_catalog import load_catalog, parse_master_rosters  # noqa: E402
from generate_exhibition_team_catalog import render_team_include  # noqa: E402


CATALOG_PATH = ROOT / "data" / "exhibition_team_catalog.json"
TEAM_INCLUDE_PATH = ROOT / "source" / "exhibition_teams_generated.inc"
ROSTER_INCLUDE_PATH = (
    ROOT / "source" / "exhibition_rosters_pes21_generated.inc"
)
EF10_ROSTER_INCLUDE_PATH = ROOT / "source" / "exhibition_rosters_ef10.inc"
LEGACY_CLEANUP_PATH = ROOT / "data" / "exhibition_legacy_player_cleanup.json"
BADGE_ATLAS_PATH = ROOT / "source" / "badge_atlas.h"
BADGE_ATLAS_BINARY_PATH = ROOT / "data" / "badge_atlas.bin"
UE4_HOOKS_PATH = ROOT / "source" / "ue4_hooks.c"
LEGACY_TEAM_IDS = {59, 115, 127, 133, 134, 135}


def parse_uint_array(source: str, symbol: str) -> list[int]:
    match = re.search(
        rf"static const uint(?:32|8)_t {re.escape(symbol)}\[\] = \{{(.*?)\n\}};",
        source,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"generated array not found: {symbol}")
    return [int(value) for value in re.findall(r"\b(\d+)u?\b", match.group(1))]


class ExhibitionTeamCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog(CATALOG_PATH)
        cls.teams = cls.catalog["teams"]
        cls.categories = cls.catalog["categories"]
        cls.team_by_id = {int(team["team_id"]): team for team in cls.teams}
        cls.cleanup = json.loads(LEGACY_CLEANUP_PATH.read_text(encoding="utf-8"))

    def test_expected_safe_catalog_shape(self) -> None:
        counts = self.catalog["counts"]
        self.assertEqual(counts["safe_shared_teams"], 464)
        self.assertEqual(counts["legacy_teams"], 6)
        self.assertEqual(counts["selector_teams"], 470)
        self.assertEqual(counts["categories"], 31)
        self.assertEqual(counts["badge_slots"], 502)

        legacy = {
            int(team["team_id"])
            for team in self.teams
            if team["roster_source"] == "legacy_manual"
        }
        native = {
            int(team["team_id"])
            for team in self.teams
            if team["roster_source"] == "pes21_native"
        }
        self.assertEqual(legacy, LEGACY_TEAM_IDS)
        self.assertEqual(len(native), 464)
        self.assertFalse(legacy & native)
        self.assertTrue(
            all(team["conversion_eligible"] == (int(team["team_id"]) in native)
                for team in self.teams)
        )
        for team in self.teams:
            team_id = int(team["team_id"])
            if team_id in native:
                self.assertGreaterEqual(team["ef10_player_count"], 18)
                self.assertGreaterEqual(team["pes21_player_count"], 18)
                self.assertLessEqual(team["pes21_player_count"], 40)
                self.assertTrue(team["has_ef10_tactics"])
                self.assertTrue(team["has_pes21_tactics"])
                self.assertEqual(team["name_source"], "ef10")
            else:
                self.assertEqual(team["name_source"], "pes21_legacy")
                self.assertTrue(team["has_pes21_tactics"])

    def test_every_team_has_one_ordered_category_membership(self) -> None:
        flattened: list[int] = []
        for category_index, category in enumerate(self.categories):
            self.assertTrue(category["team_ids"])
            self.assertEqual(category["badge_slot"], 471 + category_index)
            for category_position, raw_team_id in enumerate(category["team_ids"]):
                team_id = int(raw_team_id)
                team = self.team_by_id[team_id]
                flattened.append(team_id)
                self.assertEqual(team["category"], category["key"])
                self.assertEqual(team["category_index"], category_index)
                self.assertEqual(team["category_position"], category_position)
                self.assertEqual(team["kind"], category["kind"])

        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(set(flattened), set(self.team_by_id))

    def test_names_and_badge_slots_are_runtime_safe(self) -> None:
        team_ids = [int(team["team_id"]) for team in self.teams]
        self.assertEqual(team_ids, sorted(team_ids))
        self.assertEqual(
            [int(team["badge_slot"]) for team in self.teams],
            list(range(1, 471)),
        )

        all_slots = [int(team["badge_slot"]) for team in self.teams]
        all_slots.extend(int(category["badge_slot"]) for category in self.categories)
        self.assertEqual(sorted(all_slots), list(range(1, 502)))
        for entry in [*self.teams, *self.categories]:
            badge_source = Path(str(entry["badge_source"]))
            self.assertFalse(badge_source.is_absolute())
            self.assertNotIn("..", badge_source.parts)
        for team in self.teams:
            display_name = str(team["display_name"])
            self.assertTrue(display_name)
            self.assertTrue(display_name.isascii())
            self.assertEqual(display_name, display_name.upper())

    def test_generated_team_tables_match_manifest(self) -> None:
        expected = render_team_include(self.catalog).rstrip() + "\n"
        self.assertEqual(TEAM_INCLUDE_PATH.read_text(encoding="utf-8"), expected)

    def test_native_roster_offsets_and_membership(self) -> None:
        source = ROSTER_INCLUDE_PATH.read_text(encoding="utf-8")
        self.assertIn(
            f"// Catalog content ID: {self.catalog['content_id']}", source
        )
        self.assertIn(
            f"// Legacy cleanup content ID: {self.cleanup['content_id']}", source
        )
        player_ids = parse_uint_array(source, "exhibition_pes21_player_ids")
        shirt_numbers = parse_uint_array(
            source, "exhibition_pes21_shirt_numbers"
        )
        self.assertEqual(len(player_ids), len(shirt_numbers))

        entries = [
            tuple(int(value) for value in match)
            for match in re.findall(
                r"\{(\d+)u, exhibition_pes21_player_ids \+ (\d+)u, "
                r"exhibition_pes21_shirt_numbers \+ (\d+)u, (\d+)u\}",
                source,
            )
        ]
        native_team_ids = [
            int(team["team_id"])
            for team in self.teams
            if team["roster_source"] == "pes21_native"
        ]
        cleanup_team_ids = {
            int(row["fallback_team_id"]) for row in self.cleanup["removals"]
        }
        expected_team_ids = sorted(set(native_team_ids) | cleanup_team_ids)
        self.assertEqual([entry[0] for entry in entries], expected_team_ids)

        removals_by_team: dict[int, set[int]] = {}
        for row in self.cleanup["removals"]:
            removals_by_team.setdefault(int(row["fallback_team_id"]), set()).add(
                int(row["player_id"])
            )

        expected_offset = 0
        for team_id, player_offset, shirt_offset, count in entries:
            self.assertEqual(player_offset, expected_offset)
            self.assertEqual(shirt_offset, expected_offset)
            self.assertGreaterEqual(count, 18)
            self.assertLessEqual(count, 40)
            self.assertEqual(
                count,
                self.team_by_id[team_id]["pes21_player_count"]
                - len(removals_by_team.get(team_id, set())),
            )
            roster = player_ids[player_offset : player_offset + count]
            self.assertEqual(len(roster), count)
            self.assertEqual(len(roster), len(set(roster)))
            self.assertTrue(all(player_id > 0 for player_id in roster))
            self.assertFalse(set(roster) & removals_by_team.get(team_id, set()))
            expected_offset += count
        self.assertEqual(expected_offset, len(player_ids))

    def test_legacy_cleanup_manifest_is_safe_and_applied(self) -> None:
        canonical = {
            key: value for key, value in self.cleanup.items() if key != "content_id"
        }
        expected_content_id = hashlib.sha256(
            json.dumps(
                canonical, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()[:16]
        self.assertEqual(self.cleanup["content_id"], expected_content_id)
        self.assertEqual(self.cleanup["catalog_content_id"], self.catalog["content_id"])
        self.assertTrue(self.cleanup["policy"]["preserve_national_team_membership"])

        counts = self.cleanup["counts"]
        self.assertEqual(counts["active_ef10_teams"], 99)
        self.assertEqual(counts["active_ef10_clubs"], 43)
        self.assertEqual(counts["affected_fallback_clubs"], 136)
        self.assertEqual(counts["removed_legacy_memberships"], 299)
        self.assertGreaterEqual(counts["minimum_cleaned_roster"], 18)

        removals = self.cleanup["removals"]
        pairs = {
            (int(row["fallback_team_id"]), int(row["player_id"]))
            for row in removals
        }
        self.assertEqual(len(pairs), len(removals))
        self.assertTrue(
            all(
                self.team_by_id[int(row["fallback_team_id"])]["kind"] == "club"
                and self.team_by_id[int(row["destination_team_id"])]["kind"]
                == "club"
                and row["match"] == "shared_player_id"
                for row in removals
            )
        )
        self.assertIn((127, 40002), pairs)
        lewandowski = next(
            row
            for row in removals
            if int(row["fallback_team_id"]) == 127
            and int(row["player_id"]) == 40002
        )
        self.assertEqual(int(lewandowski["destination_team_id"]), 108)

        ef10_source = EF10_ROSTER_INCLUDE_PATH.read_text(encoding="utf-8")
        barcelona_players = parse_uint_array(
            ef10_source, "exhibition_ef10_barcelona_players"
        )
        self.assertIn(40002, barcelona_players)
        self.assertTrue(
            all(
                row["action"] == "review_only"
                and int(row["pes21_player_id"])
                != int(row["active_ef10_player_id"])
                for row in self.cleanup["name_only_review"]
            )
        )

    def test_effective_club_rosters_have_unique_player_ids(self) -> None:
        source = ROSTER_INCLUDE_PATH.read_text(encoding="utf-8")
        player_ids = parse_uint_array(source, "exhibition_pes21_player_ids")
        entries = [
            tuple(int(value) for value in match)
            for match in re.findall(
                r"\{(\d+)u, exhibition_pes21_player_ids \+ (\d+)u, "
                r"exhibition_pes21_shirt_numbers \+ (\d+)u, (\d+)u\}",
                source,
            )
        ]
        fallback_rosters = {
            team_id: player_ids[offset : offset + count]
            for team_id, offset, _shirt_offset, count in entries
        }
        ef10_rosters = {
            team_id: players
            for team_id, (players, _shirts) in parse_master_rosters(
                EF10_ROSTER_INCLUDE_PATH, "exhibition_ef10_master_rosters"
            ).items()
        }
        club_team_ids = {
            int(team["team_id"]) for team in self.teams if team["kind"] == "club"
        }

        owner_by_player: dict[int, int] = {}
        for team_id in sorted(club_team_ids):
            roster = ef10_rosters.get(team_id, fallback_rosters.get(team_id, []))
            self.assertTrue(roster, f"club {team_id} has no effective roster")
            for player_id in roster:
                self.assertNotIn(
                    player_id,
                    owner_by_player,
                    f"player {player_id} belongs to clubs "
                    f"{owner_by_player.get(player_id)} and {team_id}",
                )
                owner_by_player[player_id] = team_id

    def test_badge_atlas_metadata_matches_catalog(self) -> None:
        with BADGE_ATLAS_PATH.open("r", encoding="ascii") as source:
            header = source.read(8192)
        self.assertIn(
            f'#define BADGE_ATLAS_CONTENT_ID "{self.catalog["content_id"]}"',
            header,
        )
        definitions = {
            name: int(value)
            for name, value in re.findall(
                r"#define (BADGE_(?:CELL_SIZE|ATLAS_(?:COLS|SLOTS|ROWS))) (\d+)",
                header,
            )
        }
        self.assertEqual(definitions["BADGE_CELL_SIZE"], 128)
        self.assertEqual(definitions["BADGE_ATLAS_COLS"], 16)
        self.assertEqual(definitions["BADGE_ATLAS_SLOTS"], 502)
        self.assertEqual(definitions["BADGE_ATLAS_ROWS"], 32)
        self.assertIn("extern const uint8_t badge_atlas_bin[];", header)
        self.assertIn("#define badge_atlas_rgba8 badge_atlas_bin", header)

        binary = BADGE_ATLAS_BINARY_PATH.read_bytes()
        expected_size = 128 * 128 * 16 * 32 * 4
        self.assertEqual(len(binary), expected_size)
        self.assertEqual(binary[: 128 * 128 * 4], bytes(128 * 128 * 4))

    def test_runtime_consumes_generated_catalog_and_roster_priority(self) -> None:
        source = UE4_HOOKS_PATH.read_text(encoding="utf-8")
        self.assertIn('#include "exhibition_team_catalog.h"', source)
        self.assertIn(
            '#include "exhibition_rosters_pes21_generated.inc"', source
        )
        self.assertIn("return exhibition_team_catalog_name(team_id);", source)
        self.assertIn("return exhibition_team_catalog_badge(team_id);", source)
        self.assertIn("exhibition_team_categories[index].badge_slot", source)
        self.assertIn("exhibition_team_catalog_find(team_id) && roster", source)
        self.assertNotIn("static const uint32_t exhibition_category_english", source)
        self.assertNotIn("case 173u: return 153u;", source)

        ef10_lookup = source.index("sizeof(exhibition_ef10_master_rosters)")
        pes21_lookup = source.index("sizeof(exhibition_pes21_master_rosters)")
        manual_lookup = source.index("sizeof(exhibition_master_rosters)")
        self.assertLess(ef10_lookup, pes21_lookup)
        self.assertLess(pes21_lookup, manual_lookup)

    def test_catalog_generator_is_reproducible_when_sources_exist(self) -> None:
        required = [
            ROOT / "local-debug/efootball10-audit/tables/common/etc/pesdb/Team.bin",
            ROOT / "local-debug/efootball10-audit/tables/common/etc/pesdb/Player.bin",
            ROOT
            / "local-debug/efootball10-audit/tables/common/etc/pesdb/PlayerAssignment.bin",
            ROOT
            / "local-debug/efootball10-audit/tables/common/etc/pesdb/CategoryTeamList.bin",
            ROOT
            / "local-debug/efootball10-audit/compare/new_dt200_mobile_all.cpk/common/etc/pesdb/Tactics.bin",
            ROOT
            / "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb/Team.bin",
            ROOT
            / "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb/Player.bin",
            ROOT
            / "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb/PlayerAssignment.bin",
            ROOT
            / "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb/Tactics.bin",
            ROOT / "local-debug/cpk-emblem-check/common/render/symbol",
        ]
        if not all(path.exists() for path in required):
            self.skipTest("ignored local PES database sources are unavailable")
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "generate_legacy_player_cleanup.py"),
                "--check",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "generate_exhibition_team_catalog.py"),
                "--check",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        symbol_root = ROOT / "local-debug/cpk-emblem-check/common/render/symbol"
        for entry in [*self.teams, *self.categories]:
            self.assertTrue((symbol_root / entry["badge_source"]).is_file())


if __name__ == "__main__":
    unittest.main()
