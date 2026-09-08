from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from apply_pesdb_efootball import (  # noqa: E402
    apply_snapshot,
    load_snapshot,
    load_snapshots,
    set_player_name,
)
from convert_efootball10_players import (  # noqa: E402
    PES21_ABILITY_BITS,
    load_pesdb_snapshot,
    pes21_abilities,
    pes21_name,
    pes21_player_id,
    validate_pesdb_release_coverage,
)


def make_row(player_id: int) -> bytes:
    row = bytearray(312)
    row[8:12] = player_id.to_bytes(4, "little")
    return bytes(row)


def player_payload(player_id: int) -> dict:
    return {
        "player_id": player_id,
        "player_name": "Test Player",
        "source": "authentic",
        "primary_position_index": 12,
        "base_overall": 87,
        "base_stats": {name: 75 for name in PES21_ABILITY_BITS},
        "unsupported_target_fields": ["player_skills", "stronger_foot"],
    }


class ApplyPesdbTests(unittest.TestCase):
    def test_only_mapped_target_row_changes_and_round_trips(self) -> None:
        first = make_row(100)
        second = make_row(200)
        patched, report = apply_snapshot(
            first + second,
            {7511: player_payload(7511)},
            {7511: 200},
        )
        self.assertEqual(report["applied"], 1)
        self.assertEqual(patched[:312], first)
        changed = patched[312:624]
        self.assertEqual(pes21_player_id(changed), 200)
        self.assertEqual(pes21_name(changed), "Test Player")
        self.assertEqual(set(pes21_abilities(changed).values()), {75})

    def test_unmapped_missing_target_is_reported_not_fabricated(self) -> None:
        patched, report = apply_snapshot(
            make_row(100),
            {7511: player_payload(7511)},
            {},
        )
        self.assertEqual(patched, make_row(100))
        self.assertEqual(report["applied"], 0)
        self.assertEqual(report["skipped_players"][0]["reason"], "target_missing")

    def test_name_is_bounded_to_target_field(self) -> None:
        row = make_row(100)
        named = set_player_name(row, "X" * 100)
        self.assertEqual(len(named), 312)
        self.assertEqual(len(named[251:312].split(b"\0", 1)[0]), 60)

    def test_release_gate_rejects_partial_or_non_authentic_snapshot(self) -> None:
        snapshot = {7511: player_payload(7511)}
        with self.assertRaises(RuntimeError):
            validate_pesdb_release_coverage(
                snapshot, {7511, 4522}, source="authentic"
            )
        with self.assertRaises(RuntimeError):
            validate_pesdb_release_coverage(
                snapshot, {7511}, source="standard"
            )
        validate_pesdb_release_coverage(snapshot, {7511}, source="authentic")

    def test_loader_can_require_authentic_efootball_source(self) -> None:
        payload = {
            "schema_version": 1,
            "source": "standard",
            "authority": "https://pesdb.net/efootball",
            "players": {"7511": player_payload(7511)},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(path, require_authentic=True)

    def test_loader_rejects_mixed_snapshot_sources(self) -> None:
        payload = {
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "players": {
                "7511": {**player_payload(7511), "source": "standard"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(path)

    def test_converter_loader_requires_pesdb_authority_and_source_ids(self) -> None:
        payload = {
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "players": {
                "7511": {
                    **player_payload(7511),
                    "source_player_id": 7511,
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn(7511, load_pesdb_snapshot(path))
            payload["players"]["7511"]["source_player_id"] = 4522
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_pesdb_snapshot(path)

    def test_authentic_snapshots_merge_and_conflicts_fail_closed(self) -> None:
        first = {
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "players": {"10": player_payload(10)},
        }
        second = {
            "schema_version": 1,
            "source": "authentic",
            "authority": "https://pesdb.net/efootball",
            "players": {"20": player_payload(20)},
        }
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.json"
            second_path = Path(directory) / "second.json"
            first_path.write_text(json.dumps(first), encoding="utf-8")
            second_path.write_text(json.dumps(second), encoding="utf-8")
            self.assertEqual(
                set(load_snapshots([first_path, second_path], require_authentic=True)),
                {10, 20},
            )
            second["players"]["10"] = {
                **player_payload(10),
                "player_name": "Conflicting Identity",
            }
            second_path.write_text(json.dumps(second), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshots([first_path, second_path], require_authentic=True)


if __name__ == "__main__":
    unittest.main()
