import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pes21_player_migration import (
    build_active_appearances,
    build_active_snapshot,
    choose_canonical,
    choose_stats_variant,
    identity_fingerprint,
    merge_identity_with_stats,
    names_compatible,
    normalize_name,
    patch_verified_player,
    pes21_playing_style,
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
        "Overall": 70,
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
                "JapaneseName": "サディオ マネ",
                "ClubShirt": "S. MANÉ",
                "NationalShirt": "MANÉ",
                "Country2": 2,
                "NationalCaps": 99,
                "PlayingStyle": 22,
                "MagneticFeet": True,
                "VisionaryPass": True,
                "LongReachTackle": True,
                "Fortress": True,
                "MazingRun": True,
                "Celebration1": 72,
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
        self.assertEqual(read_bits(result, 155, 5), 13)
        self.assertEqual(read_bits(result, 500, 1), 1)  # Magnetic Feet fallback
        self.assertEqual(read_bits(result, 487, 1), 1)  # Visionary Pass fallback
        self.assertEqual(read_bits(result, 492, 1), 1)  # Long Reach Tackle fallback
        self.assertEqual(read_bits(result, 517, 1), 1)  # Fortress fallback
        self.assertEqual(read_bits(result, 531, 1), 1)
        self.assertEqual(read_bits(result, 242, 8), 72)
        self.assertEqual(read_bits(result, 233, 9), 1)
        self.assertEqual(read_bits(result, 224, 9), 2)
        self.assertEqual(result[23], 99)
        self.assertEqual(result[129:190].split(b"\0", 1)[0].decode(), "S. MANÉ")

    def test_playing_style_fallback_matches_pesdatabase_converter(self):
        self.assertEqual(pes21_playing_style(13), 1)
        self.assertEqual(pes21_playing_style(22), 13)
        self.assertEqual(pes21_playing_style(20), 20)
        self.assertEqual(pes21_playing_style(99), 0)

    def test_ef26_appearance_payload_is_rekeyed_without_donor_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "ef-appearance.bin"
            destination = root / "PlayerAppearance.bin"
            payload = bytes(range(56))
            source.write_bytes((123456789).to_bytes(8, "little") + payload)
            report = build_active_appearances(
                source,
                destination,
                {77: {"source_card_id": 123456789}},
                {77: {"native_player_id": 9001}},
                {77},
            )
            self.assertEqual(report["active_rows"], 1)
            self.assertEqual(
                destination.read_bytes(),
                (9001).to_bytes(4, "little") + payload,
            )

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

    def test_base_identity_and_highest_overall_gameplay_are_separate(self):
        base = player(108_662, 108_662, "Frenkie de Jong", 108)
        base.update({"Country": 224, "Height": 181, "Position": 5,
                     "CMF": 2, "DMF": 2, "CB": 2,
                     "Overall": 75, "BallControl": 85, "PlayingStyle": 20})
        dream = player(52_788_637_837_430, 108_662, "Frenkie de Jong", 108)
        dream.update({"Country": 999, "Height": 180, "Position": 1,
                      "CMF": 0, "DMF": 0, "CB": 3,
                      "Overall": 90, "BallControl": 91, "PlayingStyle": 15})
        source = {
            "version": "eF26_v551",
            "players": [base, dream],
            "teams": {},
            "assigns": [],
        }
        view = source_view(source)
        stats = choose_stats_variant(108_662, view)
        merged = merge_identity_with_stats(base, stats)
        self.assertEqual(stats["Id"], dream["Id"])
        self.assertEqual(merged["Id"], base["Id"])
        self.assertEqual(merged["Name"], base["Name"])
        self.assertEqual(merged["Country"], 224)
        self.assertEqual(merged["Height"], 181)
        self.assertEqual(merged["Overall"], 90)
        self.assertEqual(merged["Position"], 5)
        self.assertEqual(merged["CMF"], 2)
        self.assertEqual(merged["DMF"], 2)
        self.assertEqual(merged["CB"], 2)
        self.assertEqual(merged["BallControl"], 91)
        self.assertEqual(merged["PlayingStyle"], 20)

    def test_direct_card_wins_only_an_equal_overall_tie(self):
        direct = player(500, 500, "Tie Player", 1)
        direct["Overall"] = 85
        alternate = player(9_000, 500, "Tie Player", 1, card_type=3)
        alternate["Overall"] = 85
        stronger = player(10_000, 500, "Tie Player", 1, card_type=3)
        stronger["Overall"] = 86
        view = source_view({"version": "test", "players": [direct, alternate],
                            "teams": {}, "assigns": []})
        self.assertEqual(choose_stats_variant(500, view)["Id"], 500)
        view = source_view({"version": "test", "players": [direct, alternate, stronger],
                            "teams": {}, "assigns": []})
        self.assertEqual(choose_stats_variant(500, view)["Id"], 10_000)

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
