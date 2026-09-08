from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from clean_pes21_memberships import (  # noqa: E402
    build_pesdb_authoritative_owners,
    clean_assignments,
    load_pesdb_rosters,
    load_retired_player_ids,
    load_target_map,
    load_target_maps,
)


def row(assignment_id: int, player_id: int, team_id: int) -> bytes:
    return struct.pack("<IIII", assignment_id, player_id, team_id, 0)


class CleanupTests(unittest.TestCase):
    def test_pesdb_owner_resolution_uses_current_ids_and_holds_back_unintegrated_teams(self) -> None:
        owners, sources, unresolved, memberships, integrated, held_back = build_pesdb_authoritative_owners(
            pesdb_rosters={100: [10], 9999: [20]},
            catalog={"teams": [{"team_id": 100, "kind": "club"}]},
            physical_team_map={},
            pes21_player_ids={10, 20},
            target_map={},
        )
        self.assertEqual(owners, {10: 100})
        self.assertEqual(integrated, {100})
        self.assertEqual(held_back, {9999})
        self.assertEqual(unresolved, [])
        self.assertEqual(memberships, {100: {10}})

    def test_pesdb_owner_resolution_uses_physical_alias(self) -> None:
        owners, _sources, unresolved, memberships, integrated, held_back = build_pesdb_authoritative_owners(
            pesdb_rosters={5738: [10]},
            catalog={"teams": []},
            physical_team_map={5738: 2473},
            pes21_player_ids={10},
            target_map={},
        )
        self.assertEqual(owners, {10: 2473})
        self.assertEqual(integrated, {5738})
        self.assertEqual(held_back, set())
        self.assertEqual(unresolved, [])
        self.assertEqual(memberships, {2473: {10}})

    def test_current_pesdb_roster_removes_old_members_without_new_owner(self) -> None:
        raw = b"".join([row(1, 10, 100), row(2, 11, 100)])
        patched, report = clean_assignments(
            raw,
            owners={10: 100},
            known_club_ids={100},
            replaced_club_ids={100},
            authoritative_memberships={100: {10}},
            minimum_players=1,
        )
        self.assertEqual(report["removed_memberships"], 1)
        self.assertEqual(struct.unpack("<IIII", patched)[1], 10)
        self.assertEqual(report["removed"][0]["reason"], "stale_replaced_club_membership")
    def test_stale_club_membership_is_removed_and_national_is_preserved(self) -> None:
        raw = b"".join(
            [
                row(1, 10, 100),  # authoritative club owner
                row(2, 10, 200),  # stale club duplicate
                row(3, 10, 900),  # national/unknown; must remain
                row(4, 11, 200),
            ]
        )
        patched, report = clean_assignments(
            raw,
            owners={10: 100},
            known_club_ids={100, 200},
            minimum_players=1,
        )
        self.assertEqual(report["removed_memberships"], 1)
        self.assertEqual(
            [struct.unpack("<IIII", patched[offset : offset + 16])[2] for offset in range(0, len(patched), 16)],
            [100, 900, 200],
        )

    def test_cleanup_fails_if_minimum_roster_would_be_broken(self) -> None:
        raw = b"".join([row(1, 10, 100), row(2, 10, 200)])
        with self.assertRaises(RuntimeError):
            clean_assignments(raw, owners={10: 100}, known_club_ids={100, 200}, minimum_players=2)

    def test_unknown_team_ids_are_untouched(self) -> None:
        raw = row(1, 10, 999)
        patched, report = clean_assignments(raw, owners={10: 100}, known_club_ids={100}, minimum_players=1)
        self.assertEqual(patched, raw)
        self.assertEqual(report["removed_memberships"], 0)

    def test_retired_donor_membership_is_removed_explicitly(self) -> None:
        raw = b"".join([row(1, 141578, 200), row(2, 12, 200), row(3, 13, 200), row(4, 141578, 900)])
        patched, report = clean_assignments(
            raw,
            owners={12: 200, 13: 200},
            known_club_ids={100, 200},
            minimum_players=1,
            retired_player_ids={141578},
        )
        self.assertEqual(report["retired_donor_memberships_removed"], 1)
        self.assertEqual(len(patched), 48)

    def test_retired_donor_is_removed_from_stale_club(self) -> None:
        raw = b"".join([row(1, 141578, 200), row(2, 12, 200)])
        patched, report = clean_assignments(
            raw,
            owners={12: 200},
            known_club_ids={100, 200},
            minimum_players=1,
            retired_player_ids={141578},
        )
        self.assertEqual(report["retired_donor_memberships_removed"], 1)
        self.assertEqual(len(patched), 16)

    def test_retired_donor_is_removed_from_protected_club(self) -> None:
        raw = b"".join(
            [
                row(1, 141578, 100),
                row(2, 12, 100),
                row(3, 13, 100),
            ]
        )
        patched, report = clean_assignments(
            raw,
            owners={12: 100, 13: 100},
            known_club_ids={100},
            minimum_players=2,
            retired_player_ids={141578},
        )
        self.assertEqual(report["retired_donor_memberships_removed"], 1)
        self.assertEqual(
            [
                struct.unpack("<IIII", patched[offset : offset + 16])[1]
                for offset in range(0, len(patched), 16)
            ],
            [12, 13],
        )

    def test_stale_membership_is_removed_from_another_active_club(self) -> None:
        raw = b"".join(
            [
                row(1, 10, 100),
                row(2, 11, 100),
                row(3, 10, 200),
                row(4, 12, 200),
            ]
        )
        patched, report = clean_assignments(
            raw,
            owners={10: 200, 11: 100, 12: 200},
            known_club_ids={100, 200},
            minimum_players=1,
        )
        self.assertEqual(report["removed_memberships"], 1)
        self.assertEqual(
            [
                (struct.unpack("<IIII", patched[offset : offset + 16])[1:3])
                for offset in range(0, len(patched), 16)
            ],
            [(11, 100), (10, 200), (12, 200)],
        )

    def test_runtime_replaced_club_may_drop_below_native_minimum(self) -> None:
        raw = b"".join([row(1, 10, 100), row(2, 11, 100)])
        patched, report = clean_assignments(
            raw,
            owners={10: 200, 11: 200},
            known_club_ids={100, 200},
            replaced_club_ids={100, 200},
            minimum_players=18,
        )
        self.assertEqual(patched, b"")
        self.assertEqual(report["removed_memberships"], 2)
        self.assertEqual(report["authoritative_replacement_clubs"], 1)
        self.assertEqual(report["minimum_players_after_cleanup"], 0)
        self.assertEqual(report["minimum_native_rows_in_replaced_clubs"], 0)

    def test_retired_sources_are_excluded_before_target_collision_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "target-map.json"
            path.write_text(
                json.dumps({"map": {"141578": 166137, "166137": 166137}}),
                encoding="utf-8",
            )
            self.assertEqual(
                load_target_map(path, excluded_source_ids={141578}),
                {166137: 166137},
            )

    def test_multiple_conversion_maps_merge_without_pes21_identity_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "surrogates.json"
            second = Path(directory) / "originals.json"
            first.write_text(
                json.dumps({"map": {"9001": 7001}}),
                encoding="utf-8",
            )
            second.write_text(
                json.dumps({"map": {"9002": 9002}}),
                encoding="utf-8",
            )
            self.assertEqual(
                load_target_maps([first, second]),
                {9001: 7001, 9002: 9002},
            )


if __name__ == "__main__":
    unittest.main()
