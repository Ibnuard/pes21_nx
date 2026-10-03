#!/usr/bin/env python3
"""Preflight FL26 Bundesliga and Indonesia without modifying the runtime.

FL26 membership, crests and kits are local inputs.  The committed eFootball
catalog/registry determine whether a team can actually be played on Switch.
The JSON report contains IDs and counts only, never extracted game payloads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_fl26_cup_catalog import (
    competition_keys,
    competition_members,
    decoded_member,
    index_cpk,
)
from pesdb import parse_pes21_assignments, parse_team_records


ROOT = Path(__file__).resolve().parents[1]
BUNDESLIGA_ID = 39
INDONESIA_ID = 5750
ISRAEL_ID = 1164
REQUIRED_KITS = ("1st", "2nd", "GK1st")


def load_member(path: Path, name: str) -> bytes:
    index, base = index_cpk(path)
    return decoded_member(path, index, base, name)


def inspect(
    fl26_root: Path,
    catalog: dict,
    registry: dict,
    ef_source: dict,
) -> dict:
    season = fl26_root / "download/data_s2526.cpk"
    latest = fl26_root / "download/data_s2526c.cpk"
    symbols = fl26_root / "Data/dt15_x64.cpk"
    if not all(path.is_file() for path in (season, latest, symbols)):
        raise FileNotFoundError("FL26 season, latest update, or symbol archive missing")

    names = competition_keys(load_member(season, "common/etc/pesdb/Competition.bin"))
    memberships = competition_members(
        load_member(latest, "common/etc/pesdb/CompetitionEntry.bin")
    )
    if names.get(BUNDESLIGA_ID) != "GERMANY_D1_LEAGUE":
        raise ValueError("FL26 competition 39 is not Bundesliga")
    bundesliga = memberships.get(BUNDESLIGA_ID, [])
    if len(bundesliga) != 18 or len(set(bundesliga)) != 18:
        raise ValueError("FL26 Bundesliga must contain 18 distinct clubs")

    teams = parse_team_records(
        load_member(latest, "common/etc/pesdb/Team.bin"), "pes21"
    )
    assignments = parse_pes21_assignments(
        load_member(latest, "common/etc/pesdb/PlayerAssignment.bin")
    )
    symbols_index, _ = index_cpk(symbols)
    kit_indexes = [
        index_cpk(path)[0]
        for path in (
            fl26_root / "Data/dt34_g4.cpk",
            *(fl26_root / f"download/data_s2526{suffix}.cpk"
              for suffix in ("a", "b", "c")),
        )
        if path.is_file()
    ]
    catalog_teams = {int(row["team_id"]): row for row in catalog["teams"]}
    registry_ids = {int(row["ef_base_id"]) for row in registry["players"]}
    source_teams = ef_source["teams"]
    source_rosters: dict[int, set[int]] = {}
    for row in ef_source["assigns"]:
        source_rosters.setdefault(int(row["TeamId"]), set()).add(int(row["PlayerId"]))

    def team_row(team_id: int) -> dict:
        if team_id not in teams:
            raise ValueError(f"FL26 Team.bin missing team {team_id}")
        crest = f"common/render/symbol/flag/e_{team_id:06d}_r_l.png"
        kits = {
            kind: any(
                f"common/character0/model/character/uniform/team/"
                f"{team_id}/{team_id}_DEF_{kind}_realUni.bin" in index
                for index in kit_indexes
            )
            for kind in REQUIRED_KITS
        }
        active = catalog_teams.get(team_id)
        source_count = len(source_rosters.get(team_id, ()))
        return {
            "team_id": team_id,
            "name": teams[team_id].name,
            "fl26_roster_count": len(assignments.get(team_id, ())),
            "ef26_team_present": str(team_id) in source_teams,
            "ef26_assignment_count": source_count,
            "active_selector_category": active["category"] if active else None,
            "active_physical_team_id": int(active["physical_team_id"]) if active else None,
            "crest_present": crest in symbols_index,
            "required_kits_present": all(kits.values()),
            "missing_kits": [key for key, present in kits.items() if not present],
        }

    clubs = [team_row(team_id) for team_id in bundesliga]
    indonesia = team_row(INDONESIA_ID)
    indonesia["replacement_physical_team_id"] = ISRAEL_ID
    indonesia["registered_base_id_count"] = len(
        registry_ids & {
            int(card["BaseId"])
            for card in ef_source["players"]
            if int(card["Id"]) in source_rosters.get(INDONESIA_ID, set())
        }
    )
    indonesia["israel_currently_playable"] = ISRAEL_ID in catalog_teams
    return {
        "schema_version": 1,
        "source": "local SP Football Life 2026 and locked eF26 registry",
        "bundesliga": {
            "competition_id": BUNDESLIGA_ID,
            "member_count": len(clubs),
            "clubs": clubs,
            "ready_in_current_selector": sum(
                row["active_selector_category"] == "german_teams" for row in clubs
            ),
            "ef26_rosters_at_least_18": sum(
                row["ef26_assignment_count"] >= 18 for row in clubs
            ),
        },
        "indonesia": indonesia,
        "release_ready": False,
        "release_blockers": [
            "New teams require unique native slots, eFootball BaseId migration, "
            "native Team.bin/assignment/tactics patches and paired OBB/NRO validation.",
            "Israel cannot be renamed to Indonesia while retaining its roster or kit.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--catalog", type=Path,
                        default=ROOT / "data/exhibition_team_catalog_migration.json")
    parser.add_argument("--registry", type=Path,
                        default=ROOT / "data/pes21_player_registry.json")
    parser.add_argument("--ef-source", type=Path,
                        default=ROOT / "local-inputs/pes21-player-migration/eF26_v551/source-db.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-team-expansion-audit.json")
    args = parser.parse_args()
    result = inspect(
        args.fl26_root,
        json.loads(args.catalog.read_text(encoding="utf-8")),
        json.loads(args.registry.read_text(encoding="utf-8")),
        json.loads(args.ef_source.read_text(encoding="utf-8")),
    )
    if ROOT not in args.output.resolve().parents:
        raise ValueError("output must stay inside the project workspace")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "bundesliga_members": result["bundesliga"]["member_count"],
        "bundesliga_ready_in_selector": result["bundesliga"]["ready_in_current_selector"],
        "bundesliga_ef26_rosters": result["bundesliga"]["ef26_rosters_at_least_18"],
        "indonesia_ef26_assignments": result["indonesia"]["ef26_assignment_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
