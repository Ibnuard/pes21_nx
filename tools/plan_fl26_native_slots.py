#!/usr/bin/env python3
"""Allocate detached FL26 Bundesliga team/player slots without patching an OBB.

The plan is based on the Indonesia candidate registry and the original mobile
tables.  Donor rows must be absent from live eFootball identities, faces,
assignments and auxiliary player references.  Team donors must be fictional
4000-series entries outside both the selector and competition membership.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_fl26_cup_catalog import competition_members, decoded_member, index_cpk
from pes21_player_migration import (
    fixed_u32_ids,
    load_player_rows,
    protected_face_ids,
)
from pesdb import parse_team_records


ROOT = Path(__file__).resolve().parents[1]
EXISTING_BUNDESLIGA_SLOTS = {127: 127, 128: 128, 126: 175}


def choose_team_slots(bundesliga: list[int], physical_rows: set[int],
                      active_physical: set[int], competition_membership: set[int]) -> dict[int, int]:
    for logical, physical in EXISTING_BUNDESLIGA_SLOTS.items():
        if logical not in bundesliga or physical not in physical_rows:
            raise ValueError(f"verified existing Bundesliga slot missing: {logical}/{physical}")
    donors = sorted(
        value for value in physical_rows
        if 4000 <= value <= 4046
        and value not in active_physical
        and value not in competition_membership
    )
    needed = [value for value in bundesliga if value not in EXISTING_BUNDESLIGA_SLOTS]
    if len(donors) < len(needed):
        raise ValueError(f"only {len(donors)} inactive fictional team slots for {len(needed)} clubs")
    result = dict(EXISTING_BUNDESLIGA_SLOTS)
    result.update(zip(needed, donors, strict=False))
    if len(result) != len(bundesliga) or len(set(result.values())) != len(result):
        raise RuntimeError("Bundesliga physical team slots are not one-to-one")
    return result


def clean_player_slots(table_dir: Path, face_inventory: Path,
                       registry: dict) -> list[int]:
    _, by_id = load_player_rows(table_dir / "Player.bin")
    occupied = {
        int(row["physical_source_id"])
        for row in registry["players"]
    } | {
        int(row["native_player_id"])
        for row in registry["players"]
    }
    faces = protected_face_ids(face_inventory)
    assignments = fixed_u32_ids(table_dir / "PlayerAssignment.bin", 16, (4,))
    special = fixed_u32_ids(table_dir / "SpecialPlayerAssignment.bin", 8, (0,))
    appearance = fixed_u32_ids(table_dir / "PlayerAppearance.bin", 60, (0,))
    boots = fixed_u32_ids(table_dir / "BootsList.bin", 8, (0,))
    weekly_path = table_dir / "PlayerWeekly.bin"
    weekly = fixed_u32_ids(weekly_path, 8, (0, 4)) if weekly_path.is_file() else set()
    deleted = fixed_u32_ids(table_dir / "PlayerDeleteList.bin", 4, (0,))
    excluded = occupied | faces | assignments | special | appearance | boots | weekly
    slots = sorted(value for value in by_id if value not in excluded)
    slots.sort(key=lambda value: (value not in deleted, value))
    return slots


def make_plan(identity_plan: dict, registry: dict, catalog: dict,
              dt200: Path, table_dir: Path, face_inventory: Path) -> dict:
    bundesliga = [int(value) for value in identity_plan["bundesliga_team_ids"]]
    index, base = index_cpk(dt200)
    teams = parse_team_records(
        decoded_member(dt200, index, base, "common/etc/pesdb/Team.bin"),
        "pes21",
    )
    competitions = competition_members(
        decoded_member(dt200, index, base,
                       "common/etc/pesdb/CompetitionEntry.bin")
    )
    competition_ids = {value for entries in competitions.values() for value in entries}
    active_physical = {int(row["physical_team_id"]) for row in catalog["teams"]}
    slots = choose_team_slots(bundesliga, set(teams), active_physical, competition_ids)
    new_players = [row for row in identity_plan["players"]
                   if row["status"] == "new_fl26_identity" and row["portrait_available"]]
    available = clean_player_slots(table_dir, face_inventory, registry)
    if len(available) < len(new_players):
        raise ValueError(f"only {len(available)} clean player rows for {len(new_players)} imports")
    allocations = [
        {
            "source_key": row["source_key"],
            "fl26_player_id": int(row["fl26_player_id"]),
            "fingerprint": row["fingerprint"],
            "native_player_id": available[index],
            "physical_source_id": available[index],
            "portrait_source_id": int(row["fl26_player_id"]),
            "commentary_owner_id": None,
            "face_owner_id": None,
        }
        for index, row in enumerate(sorted(new_players, key=lambda row: int(row["fl26_player_id"])))
    ]
    missing_portraits = [row for row in identity_plan["players"]
                         if not row["portrait_available"]]
    reviews = [row for row in identity_plan["players"]
               if row["status"] == "review_identity"]
    return {
        "schema_version": 1,
        "status": "allocation_only_not_playable",
        "team_slots": [
            {"logical_team_id": team_id, "physical_team_id": slots[team_id],
             "existing": team_id in EXISTING_BUNDESLIGA_SLOTS}
            for team_id in bundesliga
        ],
        "player_slots": allocations,
        "held_identity_review_ids": [int(row["fl26_player_id"]) for row in reviews],
        "held_missing_portrait_ids": [int(row["fl26_player_id"])
                                      for row in missing_portraits],
        "counts": {
            "bundesliga_teams": len(slots),
            "new_team_slots": len(slots) - len(EXISTING_BUNDESLIGA_SLOTS),
            "new_player_slots": len(allocations),
            "held_identity_reviews": len(reviews),
            "held_missing_portraits": len(missing_portraits),
            "remaining_clean_player_slots": len(available) - len(allocations),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-plan", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-identity-plan.json")
    parser.add_argument("--registry", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work/player-registry-candidate.json")
    parser.add_argument("--catalog", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work/exhibition_team_catalog_migration.json")
    parser.add_argument("--dt200", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work/base/dt200_mobile_all.cpk")
    parser.add_argument("--table-dir", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work/base/tables")
    parser.add_argument("--face-inventory", type=Path,
                        default=ROOT / "local-debug/indonesia-player-migration-work/face-ids.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents:
        raise ValueError("native slot plan output must stay in local-debug")
    result = make_plan(
        json.loads(args.identity_plan.read_text(encoding="utf-8")),
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.catalog.read_text(encoding="utf-8")),
        args.dt200, args.table_dir, args.face_inventory,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"output": str(output), **result["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
