import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from convert_efootball10_players import encode_pes21_wesys  # noqa: E402
from generate_pesdb_runtime_rosters import generate  # noqa: E402


class PesdbRuntimeRosterTests(unittest.TestCase):
    def build_fixture(self, directory: Path) -> dict[str, Path]:
        player_ids = list(range(1001, 1012))
        positions = [2, 12, 1, 2, 1, 8, 12, 0, 1, 10, 4]
        overalls = [74, 74, 76, 82, 81, 76, 89, 87, 86, 85, 84]
        roster = {
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "policy": {
                "pesdb_rosters_only": True,
                "pesdb_player_values_only": True,
                "pes21_roster_or_value_fallback": False,
            },
            "teams": {
                "100": {
                    "complete": True,
                    "player_count": len(player_ids),
                    "player_ids": player_ids,
                    "shirt_numbers": {
                        str(player_id): index + 1
                        for index, player_id in enumerate(player_ids)
                    },
                }
            },
            "players": {
                str(player_id): {
                    "source": "authentic",
                    "player_id": player_id,
                    "base_overall": overalls[index],
                    "primary_position_index": positions[index],
                }
                for index, player_id in enumerate(player_ids)
            },
        }
        target_map = {
            "authority": "https://pesdb.net/efootball",
            "policy": {"pesdb_only": True, "pes21_values_allowed": False},
            "map": {str(player_id): player_id for player_id in player_ids},
        }
        cleanup = {
            "pesdb_authoritative_team_ids": [100],
            "pesdb_only": True,
            "unresolved_pesdb_memberships": 0,
        }
        physical = {
            "teams": [
                {"team_id": 1, "physical_team_id": 1, "kind": "national"},
                {"team_id": 100, "physical_team_id": 100, "kind": "club"},
            ]
        }
        rows = []
        for player_id in player_ids:
            row = bytearray(312)
            struct.pack_into("<I", row, 8, player_id)
            rows.append(bytes(row))

        paths = {
            "rosters_path": directory / "rosters.json",
            "target_map_path": directory / "target-map.json",
            "player_path": directory / "Player.bin",
            "cleanup_report_path": directory / "cleanup.json",
            "physical_team_map_path": directory / "physical.json",
            "output_path": directory / "generated.inc",
            "report_path": directory / "generated.md",
            "metadata_output_path": directory / "generated.json",
        }
        paths["rosters_path"].write_text(json.dumps(roster), encoding="utf-8")
        paths["target_map_path"].write_text(
            json.dumps(target_map), encoding="utf-8"
        )
        paths["cleanup_report_path"].write_text(
            json.dumps(cleanup), encoding="utf-8"
        )
        paths["physical_team_map_path"].write_text(
            json.dumps(physical), encoding="utf-8"
        )
        paths["player_path"].write_bytes(encode_pes21_wesys(b"".join(rows)))
        return paths

    def test_check_validates_without_rewriting_generated_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pesdb-runtime-roster-") as value:
            paths = self.build_fixture(Path(value))
            metadata = generate(**paths)
            self.assertEqual(metadata["team_count"], 1)
            self.assertEqual(metadata["mapped_player_count"], 11)
            self.assertEqual(metadata["authoritative_rating_count"], 11)
            self.assertTrue(metadata["position_balanced_starting_xi"])
            self.assertEqual(metadata["catalog_club_count"], 1)
            self.assertTrue(metadata["preserve_national_team_membership"])

            generated = paths["output_path"].read_text(encoding="ascii")
            club_ids = [
                int(value)
                for value in re.findall(
                    r"(\d+)u",
                    re.search(
                        r"exhibition_pesdb_club_team_ids\[\] = \{(.*?)\n\};",
                        generated,
                        re.DOTALL,
                    ).group(1),
                )
            ]
            owners = {
                int(player_id): int(team_id)
                for player_id, team_id in re.findall(
                    r"\{(\d+)u, (\d+)u\}", generated
                )
            }
            self.assertEqual(club_ids, [100])
            self.assertEqual(
                owners, {player_id: 100 for player_id in range(1001, 1012)}
            )
            machine = json.loads(
                paths["metadata_output_path"].read_text(encoding="ascii")
            )
            team = machine["teams"]["100"]
            self.assertEqual(team["ordered_target_ids"][0], 1008)
            self.assertEqual(team["starting_positions"][0], 0)
            self.assertEqual(team["formation_roles"][0], 0)
            self.assertGreaterEqual(team["team_rating"]["overall"], 70)
            self.assertIn(
                "static const ExhibitionPesdbPlayerRating "
                "exhibition_pesdb_player_ratings[]",
                generated,
            )
            self.assertIn(
                "static const ExhibitionPesdbTeamRating "
                "exhibition_pesdb_team_ratings[]",
                generated,
            )
            generate(**paths, check=True)
            self.assertEqual(
                paths["output_path"].read_text(encoding="ascii"), generated
            )

            paths["output_path"].write_text("stale\n", encoding="ascii")
            with self.assertRaisesRegex(RuntimeError, "stale"):
                generate(**paths, check=True)
            self.assertEqual(
                paths["output_path"].read_text(encoding="ascii"), "stale\n"
            )

    def test_runtime_prefers_pesdb_before_all_legacy_rosters(self) -> None:
        hooks = (ROOT / "source" / "ue4_hooks.c").read_text(encoding="utf-8")
        start = hooks.index("static const ExhibitionMasterRoster *exhibition_find_roster")
        end = hooks.index("static int exhibition_is_valid_team", start)
        lookup = hooks[start:end]
        pesdb = lookup.index("exhibition_pesdb_master_rosters")
        inter_miami = lookup.index("experimental_inter_miami_roster")
        ef10 = lookup.index("exhibition_ef10_master_rosters")
        pes21 = lookup.index("exhibition_pes21_master_rosters")
        manual = lookup.index("exhibition_master_rosters")
        self.assertLess(pesdb, inter_miami)
        self.assertLess(inter_miami, ef10)
        self.assertLess(ef10, pes21)
        self.assertLess(pes21, manual)


if __name__ == "__main__":
    unittest.main()
