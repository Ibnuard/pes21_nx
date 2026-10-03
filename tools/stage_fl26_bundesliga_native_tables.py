#!/usr/bin/env python3
"""Stage identity-safe Bundesliga/Indonesia PES21 tables in local-debug.

This produces *tables only*, not a playable OBB or release. FL26-only players
copy PES21-format source records into verified clean native slots. Existing
eFootball BaseIds keep their native records, and club transfers remove the old
club assignment while preserving national-team membership.
"""

from __future__ import annotations

import argparse
import collections
import json
import shutil
import struct
from pathlib import Path

from build_fl26_cup_catalog import decoded_member, index_cpk
from pes21_player_migration import (
    load_tactic_roles,
    patch_canary_tables,
    pes21_player_id,
    table_raw,
    write_table_like,
)
from pesdb import (
    PES21_PLAYER_RECORD_SIZE,
    PES21_TEAM_RECORD_SIZE,
    parse_pes21_assignments,
    parse_player_ids,
    parse_team_records,
    split_records,
)


ROOT = Path(__file__).resolve().parents[1]
PESDB_PREFIX = "common/etc/pesdb/"


def patch_football_tables(
    output: Path, generated: Path, base_cpk: Path, fl26_cpk: Path,
    identity_plan: dict, slot_plan: dict, registry: dict, catalog: dict,
) -> dict:
    base_index, base_offset = index_cpk(base_cpk)
    pc_index, pc_offset = index_cpk(fl26_cpk)

    def mobile(name: str) -> bytes:
        return decoded_member(base_cpk, base_index, base_offset, PESDB_PREFIX + name)

    def pc(name: str) -> bytes:
        return decoded_member(fl26_cpk, pc_index, pc_offset, PESDB_PREFIX + name)

    rows = {int(row["fl26_player_id"]): row for row in identity_plan["players"]}
    allocated = {int(row["fl26_player_id"]): int(row["native_player_id"])
                 for row in slot_plan["player_slots"]}
    registry_by_base = {int(row["ef_base_id"]): row for row in registry["players"]}
    roster_native = {}
    for player_id, row in rows.items():
        if row["status"] == "review_identity" or not row["portrait_available"]:
            continue
        if row["status"] == "reuse_ef_base_id":
            native_id = int(registry_by_base[int(row["base_id"])]["native_player_id"])
            if native_id != int(row["native_player_id"]):
                raise ValueError(f"native BaseId changed for FL26 player {player_id}")
        else:
            native_id = allocated[player_id]
        roster_native[player_id] = native_id
    if len(allocated) != sum(row["status"] == "new_fl26_identity"
                             and row["portrait_available"] for row in rows.values()):
        raise ValueError("FL26 allocation does not cover exactly the new identities")

    source_players = {
        pes21_player_id(row): row
        for row in split_records(pc("Player.bin"), PES21_PLAYER_RECORD_SIZE,
                                 "FL26 Player.bin")
    }
    native_players = {
        pes21_player_id(row): row
        for row in split_records(table_raw(generated / "Player.bin"),
                                 PES21_PLAYER_RECORD_SIZE, "mobile Player.bin")
    }
    original_player_ids = set(native_players)
    for pc_id, native_id in allocated.items():
        if native_id not in native_players or pc_id not in source_players:
            raise ValueError(f"missing donor/source player {pc_id}/{native_id}")
        row = bytearray(source_players[pc_id])
        struct.pack_into("<I", row, 8, native_id)
        native_players[native_id] = bytes(row)
    player_payload = b"".join(native_players[player_id]
                              for player_id in sorted(native_players))
    if (len(native_players) != 43_074 or set(native_players) != original_player_ids
            or parse_player_ids(player_payload, "pes21") != original_player_ids):
        raise RuntimeError("FL26 player overlay changed the fixed native ID set")
    write_table_like(generated / "Player.bin", output / "Player.bin", player_payload)

    delete_raw = table_raw(generated / "PlayerDeleteList.bin")
    deleted = [struct.unpack_from("<I", delete_raw, offset)[0]
               for offset in range(0, len(delete_raw), 4)]
    deleted = sorted(value for value in deleted if value not in set(allocated.values()))
    write_table_like(generated / "PlayerDeleteList.bin", output / "PlayerDeleteList.bin",
                     b"".join(struct.pack("<I", value) for value in deleted))

    pc_team_raw = pc("Team.bin")
    pc_teams = {struct.unpack_from("<I", row, 8)[0]: row
                for row in split_records(pc_team_raw, PES21_TEAM_RECORD_SIZE,
                                         "FL26 Team.bin")}
    mobile_team_raw = mobile("Team.bin")
    native_teams = {struct.unpack_from("<I", row, 8)[0]: row
                    for row in split_records(mobile_team_raw, PES21_TEAM_RECORD_SIZE,
                                             "mobile Team.bin")}
    original_team_ids = set(native_teams)
    teams = {int(row["logical_team_id"]): int(row["physical_team_id"])
             for row in slot_plan["team_slots"]}
    teams[5750] = 1164
    for pc_id, physical_id in teams.items():
        if physical_id not in native_teams or pc_id not in pc_teams:
            raise ValueError(f"missing native/source team {pc_id}/{physical_id}")
        row = bytearray(pc_teams[pc_id])
        struct.pack_into("<I", row, 8, physical_id)
        if row[84] != 15:
            raise ValueError(f"FL26 team {pc_id} lacks the expected real-kit flag")
        native_teams[physical_id] = bytes(row)
    team_payload = b"".join(native_teams[team_id] for team_id in sorted(native_teams))
    if set(parse_team_records(team_payload, "pes21")) != original_team_ids:
        raise RuntimeError("FL26 team overlay changed the fixed native team ID set")
    from pes21_player_migration import encode_pes21_wesys
    (output / "Team.bin").write_bytes(encode_pes21_wesys(team_payload))

    pc_assignments = parse_pes21_assignments(pc("PlayerAssignment.bin"))
    catalog_by_id = {int(row["team_id"]): row for row in catalog["teams"]}
    physical_clubs = {int(row["physical_team_id"]) for row in catalog["teams"]
                      if row["kind"] == "club"}
    new_bundesliga_physical = set(teams.values()) - {1164}
    transfer_from: dict[int, set[int]] = collections.defaultdict(set)
    for pc_id, native_id in roster_native.items():
        row = rows[pc_id]
        if row["status"] != "reuse_ef_base_id":
            continue
        for previous_id in row["existing_team_ids"]:
            previous = catalog_by_id.get(int(previous_id))
            if (previous and previous["kind"] == "club"
                    and int(previous_id) not in row["bundesliga_team_ids"]):
                transfer_from[int(previous["physical_team_id"])].add(native_id)

    source_assignments = table_raw(generated / "PlayerAssignment.bin")
    assigned = [struct.unpack_from("<IIII", source_assignments, offset)
                for offset in range(0, len(source_assignments), 16)]
    assigned = [row for row in assigned
                if row[2] not in new_bundesliga_physical
                and not (row[2] in physical_clubs
                         and row[1] in transfer_from.get(row[2], set()))]
    previous_count = len(assigned)
    next_id = max(row[0] for row in assigned) + 1
    per_team = {}
    for logical_id in identity_plan["bundesliga_team_ids"]:
        physical_id = teams[int(logical_id)]
        roster = [row for row in pc_assignments[int(logical_id)]
                  if int(row.player_id) in roster_native]
        if not 18 <= len(roster) <= 40:
            raise ValueError(f"Bundesliga club {logical_id} has {len(roster)} players")
        per_team[int(logical_id)] = len(roster)
        for order, row in enumerate(roster):
            assigned.append((next_id, roster_native[int(row.player_id)], physical_id,
                             (order << 8) | (int(row.shirt) & 0xFF)))
            next_id += 1
    if len({row[0] for row in assigned}) != len(assigned):
        raise RuntimeError("duplicate native assignment record ID")
    if any(row[1] not in native_players for row in assigned):
        raise RuntimeError("assignment references missing native player")
    by_team = collections.Counter(row[2] for row in assigned)
    for row in catalog["teams"]:
        physical_id = int(row["physical_team_id"])
        if by_team[physical_id] < 18:
            raise RuntimeError(f"active club/nation {physical_id} fell below 18 players")
    write_table_like(
        generated / "PlayerAssignment.bin", output / "PlayerAssignment.bin",
        b"".join(struct.pack("<IIII", *row) for row in assigned),
    )

    # Israel's physical slot is retained, but its native Europe membership is
    # moved to the AFC Asia Cup; no old Israel Team.bin/roster remains.
    competition = bytearray(mobile("CompetitionEntry.bin"))
    moved = 0
    for offset in range(0, len(competition), 12):
        team_id, _entry_id, packed = struct.unpack_from("<III", competition, offset)
        if team_id == 1164 and packed & 0xFF == 28:
            struct.pack_into("<I", competition, offset + 8, (packed & ~0xFF) | 35)
            moved += 1
    if moved != 1:
        raise RuntimeError(f"expected one Israel Europe entry, got {moved}")
    (output / "CompetitionEntry.bin").write_bytes(
        encode_pes21_wesys(bytes(competition)))

    report = {
        "schema_version": 1,
        "status": "native_tables_staged_not_packaged",
        "teams_replaced": len(teams),
        "players_imported": len(allocated),
        "existing_players_reused": sum(row["status"] == "reuse_ef_base_id"
                                       and row["portrait_available"] for row in rows.values()),
        "old_club_memberships_removed": sum(len(ids) for ids in transfer_from.values()),
        "club_roster_counts": per_team,
        "assignments_added": len(assigned) - previous_count,
        "held_identity_review_ids": slot_plan["held_identity_review_ids"],
        "held_missing_portrait_ids": slot_plan["held_missing_portrait_ids"],
        "pending": ["FL26 kits/crests", "dt241 portraits", "paired CPK/NRO",
                    "native tactics review", "hardware validation"],
    }
    (output.parent / "native-table-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--work", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work")
    parser.add_argument("--identity-plan", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-identity-plan.json")
    parser.add_argument("--slot-plan", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-native")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents or output.exists():
        raise ValueError("output must be a new directory inside local-debug")
    work = args.work.resolve()
    snapshot = json.loads((work / "active-snapshot.json").read_text(encoding="utf-8"))
    registry = json.loads((work / "player-registry-candidate.json").read_text(
        encoding="utf-8"))
    catalog = json.loads((work / "exhibition_team_catalog_migration.json").read_text(
        encoding="utf-8"))
    identity = json.loads(args.identity_plan.read_text(encoding="utf-8"))
    slots = json.loads(args.slot_plan.read_text(encoding="utf-8"))
    output.mkdir(parents=True)
    players = {int(row["base_id"]): row for row in snapshot["players"]}
    physical = {int(row["ef_team_id"]): int(row["physical_team_id"])
                for row in snapshot["teams"]}
    roles, _ = load_tactic_roles(work / "base/tables/Tactics.bin",
                                 work / "base/tables/TacticsFormation.bin", physical)
    ordered = [
        {**row,
         "native_formation_roles": roles[int(row["physical_team_id"])],
         "formation_roles": roles[int(row["physical_team_id"])]}
        for row in snapshot["teams"]
    ]
    _, base_report = patch_canary_tables(
        snapshot=snapshot, registry=registry, canary_teams=ordered,
        output=output / "ef-base-tables", table_dir=work / "base/tables",
        full_rebuild=True,
        appearance_source=ROOT / "local-inputs/pes21-player-migration/eF26_v551/ef-appearance.bin",
    )
    target = output / "tables"
    target.mkdir()
    for source in (output / "ef-base-tables").iterdir():
        shutil.copy2(source, target / source.name)
    report = patch_football_tables(
        target, output / "ef-base-tables",
        work / "base/dt200_mobile_all.cpk",
        args.fl26_root / "download/data_s2526c.cpk",
        identity, slots, registry, catalog,
    )
    report["ef_base_table_player_rows"] = base_report["player_rows"]
    report["ef_base_table_assignments"] = base_report["assignments_inserted"]
    report["ef_base_lineup_teams"] = len(ordered)
    report["lineup_policy"] = "source_assignment_order; native_roles_preserved"
    (output / "native-table-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status": report["status"],
                      "teams_replaced": report["teams_replaced"],
                      "players_imported": report["players_imported"],
                      "existing_players_reused": report["existing_players_reused"],
                      "assignments_added": report["assignments_added"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
