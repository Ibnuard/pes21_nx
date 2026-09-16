import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pes21_player_migration import (
    build_active_snapshot,
    choose_canonical,
    identity_fingerprint,
    names_compatible,
    normalize_name,
    patch_verified_player,
    protected_face_ids,
    source_view,
)
from convert_efootball10_players import (
    pes21_abilities,
    pes21_name,
    pes21_player_position,
    read_bits,
)


def player(card_id, base_id, name, club_id, *, card_type=0):
    return {
        "Id": card_id,
        "BaseId": base_id,
        "Name": name,
        "ClubId": club_id,
        "CardType": card_type,
        "Country": 1,
        "Age": 25,
        "Height": 180,
        "Foot": True,
        "Position": 12,
    }


class PlayerMigrationTests(unittest.TestCase):
    def test_name_normalization_is_accent_and_punctuation_stable(self):
        self.assertEqual(normalize_name("Sadio Mané"), "sadiomane")
        self.assertEqual(normalize_name("Sadio Mane"), "sadiomane")
        self.assertTrue(names_compatible("S. MANÉ", "Sadio Mané"))
        self.assertFalse(names_compatible("Lamine Yamal", "Pedri González"))

    def test_fingerprint_is_deterministic(self):
        row = player(100, 100, "Player One", 1)
        self.assertEqual(identity_fingerprint(row), identity_fingerprint(dict(row)))

    def test_fingerprint_ignores_normal_age_progression(self):
        row = player(100, 100, "Player One", 1)
        older = dict(row, Age=26)
        self.assertEqual(identity_fingerprint(row), identity_fingerprint(older))

    def test_player_output_uses_full_ef26_canonical_name(self):
        source = player(57_304, 57_304, "Sadio Mané", 18_961)
        source.update(
            {
                "Weight": 81,
                "Age": 34,
                "RWF": 2,
                "SS": 1,
                "OffensiveAwareness": 77,
                "WeakFootUsage": 2,
                "WeakFootAccuracy": 3,
                "Form": 5,
                "InjuryResistance": 2,
                "Reputation": 7,
                "PlayingAttitude": 3,
            }
        )
        result = patch_verified_player(bytes(312), source, 57_304)
        self.assertEqual(pes21_name(result), "Sadio Mané")
        self.assertEqual(pes21_player_position(result), 12)
        self.assertEqual(read_bits(result, 476, 2), 2)
        self.assertEqual(read_bits(result, 478, 2), 1)
        self.assertEqual(read_bits(result, 216, 8) + 100, 180)
        self.assertEqual(read_bits(result, 256, 7) + 30, 81)
        self.assertEqual(read_bits(result, 408, 6) + 15, 34)
        self.assertEqual(read_bits(result, 454, 2) + 1, 2)
        self.assertEqual(read_bits(result, 462, 2) + 1, 3)
        self.assertEqual(read_bits(result, 438, 3) + 1, 5)
        self.assertEqual(pes21_abilities(result)["offensive_awareness"], 77)

    def test_locked_face_inventory_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / "face-ids.json"
            inventory.write_text(
                json.dumps({"count": 2, "ids": [4522, 7511]}),
                encoding="utf-8",
            )
            self.assertEqual(protected_face_ids(inventory), {4522, 7511})
            inventory.write_text(
                json.dumps({"count": 3, "ids": [4522, 7511]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "duplicate or invalid"):
                protected_face_ids(inventory)

    def test_real_club_identity_wins_over_fake_national_alias(self):
        fake = player(8_445_912, 57_304, "Évrard Allegret", 38)
        real = player(16_834_520, 57_304, "Sadio Mané", 18_961)
        source = {
            "version": "eF26_v551",
            "players": [fake, real],
            "teams": {
                "38": {"Id": 38, "NameEnglish": "Senegal", "NationalTeam": True, "Licensed": False},
                "18961": {"Id": 18961, "NameEnglish": "Al Nassr FC", "NationalTeam": False, "Licensed": True},
            },
            "assigns": [],
        }
        view = source_view(source)
        chosen, resolution = choose_canonical(
            57_304,
            [(fake, view.teams_by_id[38]), (real, view.teams_by_id[18_961])],
            view,
        )
        self.assertEqual(chosen["Name"], "Sadio Mané")
        self.assertEqual(resolution["aliases"], ["Évrard Allegret"])

    def test_two_real_club_identities_fail_closed(self):
        first = player(100, 77, "First Player", 1)
        second = player(200, 77, "Second Player", 2)
        source = {
            "version": "eF26_v551",
            "players": [first, second],
            "teams": {
                "1": {"Id": 1, "NameEnglish": "One", "NationalTeam": False, "Licensed": True},
                "2": {"Id": 2, "NameEnglish": "Two", "NationalTeam": False, "Licensed": True},
            },
            "assigns": [],
        }
        view = source_view(source)
        with self.assertRaisesRegex(RuntimeError, "multiple club identities"):
            choose_canonical(
                77,
                [(first, view.teams_by_id[1]), (second, view.teams_by_id[2])],
                view,
            )

    def test_team_scope_excludes_missing_and_short_rosters(self):
        players = [player(index, index, f"P{index}", 1) for index in range(1, 19)]
        players += [player(100 + index, 100 + index, f"Q{index}", 2) for index in range(17)]
        assigns = [
            {"PlayerId": row["Id"], "TeamId": row["ClubId"], "ShirtNumber": 1, "PositionId": 0, "Captain": False}
            for row in players
        ]
        source = {
            "version": "eF26_v551",
            "players": players,
            "teams": {
                "1": {"Id": 1, "NameEnglish": "Valid", "NationalTeam": False, "Licensed": True},
                "2": {"Id": 2, "NameEnglish": "Short", "NationalTeam": False, "Licensed": True},
            },
            "assigns": assigns,
        }
        catalog = {
            "teams": [
                {"team_id": 1, "display_name": "VALID", "kind": "club"},
                {"team_id": 2, "display_name": "SHORT", "kind": "club"},
                {"team_id": 3, "display_name": "MISSING", "kind": "club"},
            ]
        }
        config = {
            "minimum_players": 18,
            "maximum_players": 40,
            "policy": {},
        }
        result = build_active_snapshot(source, catalog, config)
        self.assertEqual(result["counts"]["active_teams"], 1)
        self.assertEqual(result["counts"]["excluded_teams"], 2)
        self.assertEqual(result["counts"]["active_players"], 18)


if __name__ == "__main__":
    unittest.main()
