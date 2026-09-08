from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from plan_pesdb_target_map import allocate_target_map  # noqa: E402


def row(player_id: int, position: int) -> bytes:
    data = bytearray(312)
    struct.pack_into("<I", data, 8, player_id)
    # Registered position is bits 18..21 of the word at offset 52.
    struct.pack_into("<I", data, 52, position << 18)
    data[251] = ord("X")
    return bytes(data)


class PesdbTargetMapTests(unittest.TestCase):
    def test_existing_target_is_reserved_from_new_donor_allocation(self) -> None:
        snapshot = {
            1001: {"player_name": "Mapped", "primary_position_index": 1},
            1002: {"player_name": "New", "primary_position_index": 1},
        }
        result = allocate_target_map(
            snapshot,
            target_rows={5001: row(5001, 1), 5002: row(5002, 1)},
            deleted_ids={5001, 5002},
            referenced_ids=set(),
            existing_map={1001: 5001},
        )
        self.assertEqual(result["map"]["1001"], 5001)
        self.assertEqual(result["map"]["1002"], 5002)

    def test_invalid_existing_target_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            allocate_target_map(
                {1001: {"player_name": "Mapped", "primary_position_index": 1}},
                target_rows={5001: row(5001, 1)},
                deleted_ids={5001},
                referenced_ids=set(),
                existing_map={1001: 9999},
            )

    def test_duplicate_existing_targets_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            allocate_target_map(
                {
                    1001: {"player_name": "One", "primary_position_index": 1},
                    1002: {"player_name": "Two", "primary_position_index": 1},
                },
                target_rows={5001: row(5001, 1)},
                deleted_ids={5001},
                referenced_ids=set(),
                existing_map={1001: 5001, 1002: 5001},
            )


if __name__ == "__main__":
    unittest.main()
