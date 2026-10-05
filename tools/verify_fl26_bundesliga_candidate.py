#!/usr/bin/env python3
"""Verify the paired local Bundesliga/Indonesia CPK/NRO structure.

Passing this check is not a substitute for a Switch hardware match test.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path

from build_fl26_cup_catalog import competition_members, decoded_member, index_cpk
from cleanse_playable_categories import RETIRED
from native_lineup import validate_formation_phases
from pesdb import parse_pes21_assignments, parse_player_ids, parse_team_records, split_records
from prepare_loose_cpk import verify as verify_loose


ROOT = Path(__file__).resolve().parents[1]


def check(candidate: Path, selector_dir: Path, slot_plan: dict,
          portrait_report: dict, nro_path: Path | None = None,
          curated_dir: Path | None = None) -> dict:
    catalog = json.loads((selector_dir / "exhibition_team_catalog_migration.json")
                         .read_text(encoding="utf-8"))
    rows = catalog["teams"]
    team_ids = [int(row["team_id"]) for row in rows]
    badges = [int(row["badge_slot"]) for row in rows]
    if (len(rows) != 459 or len(set(team_ids)) != 459
            or len(set(badges)) != 459 or 1164 in team_ids
            or sum(row["category"] == "german_teams" for row in rows) != 18):
        raise ValueError("selector team/category/badge invariant failed")
    physical = [int(row["physical_team_id"]) for row in slot_plan["team_slots"]]
    if len(physical) != 18 or len(set(physical)) != 18:
        raise ValueError("native team slot plan is not one-to-one")
    bundle = candidate / "LooseCpk"
    archives = {}
    for label in ("dt120", "dt200", "dt240", "dt241"):
        path = bundle / f"{label}_mobile_all.cpk"
        index, base = index_cpk(path)
        archives[label] = (path, index, base)
    dt200, db_index, db_base = archives["dt200"]

    def database(name: str) -> bytes:
        return decoded_member(dt200, db_index, db_base,
                              f"common/etc/pesdb/{name}")

    teams = parse_team_records(database("Team.bin"), "pes21")
    assignments = parse_pes21_assignments(database("PlayerAssignment.bin"))
    players = parse_player_ids(database("Player.bin"), "pes21")
    native_players = {struct.unpack_from("<I", r, 8)[0]: r for r in
                      split_records(database("Player.bin"), 312, "native players")}
    tactics, formations = database("Tactics.bin"), database("TacticsFormation.bin")
    competitions = competition_members(database("CompetitionEntry.bin"))
    if teams[1164].name.casefold() != "indonesia" or len(assignments[1164]) != 26:
        raise ValueError("Indonesia did not fully replace the native Israel team")
    if 1164 in competitions[28] or 1164 not in competitions[35]:
        raise ValueError("Indonesia retains Israel's Europe competition entry")
    if len(players) != 43_074:
        raise ValueError("fixed Player.bin row count changed")
    rosters = {team_id: len(assignments[team_id]) for team_id in physical}
    if any(not 18 <= count <= 40 for count in rosters.values()):
        raise ValueError("a Bundesliga native roster is not playable")
    if any(row.player_id not in players for rows in assignments.values()
           for row in rows):
        raise ValueError("a native assignment references a missing player")
    lineup_checks = {team_id: validate_formation_phases(tactics, formations, team_id,
        [row.player_id for row in assignments[team_id][:11]], native_players) for team_id in physical}

    for physical_id in [*physical, 1164]:
        for kind in ("1st", "2nd", "GK1st"):
            member = (f"common/etc/uniform/team/{physical_id}/"
                      f"{physical_id}_DEF_{kind}_realUni.bin")
            if member not in db_index:
                raise ValueError(f"native kit descriptor missing: {member}")
        for suffix in ("p1", "p2", "g1"):
            member = ("Models/character/Uniform16/D/"
                      f"u{physical_id:04d}{suffix}.png")
            if member not in archives["dt120"][1]:
                raise ValueError(f"native kit texture missing: {member}")
        for suffix in ("", "_l", "_s"):
            member = ("common/render/symbol/flag/"
                      f"e_{physical_id:06d}_r{suffix}.png")
            if member not in archives["dt240"][1]:
                raise ValueError(f"native crest missing: {member}")
    portrait_ids = [int(row["native_player_id"])
                    for row in portrait_report["portraits"]]
    if len(portrait_ids) != 376 or len(set(portrait_ids)) != 376:
        raise ValueError("FL26 portrait manifest differs from curated player plan")
    missing_portraits = [value for value in portrait_ids
                         if f"common/player/{value}.png" not in archives["dt241"][1]]
    if missing_portraits:
        raise ValueError(f"native portraits missing: {missing_portraits[:10]}")

    nro = (nro_path or candidate / "pes21_nx.nro").read_bytes()
    atlas = (selector_dir / "badge_atlas.bin").read_bytes()
    probe_offset = len(atlas) // 3
    found = nro.find(atlas[probe_offset:probe_offset + 65536])
    atlas_offset = found - probe_offset
    loose = verify_loose(candidate)
    roster_probe = struct.pack(
        "<8I", *(row.player_id for row in assignments[physical[0]][:8]))
    scorer_include = (selector_dir / "league_scorer_pool_generated.inc").read_text(
        encoding="utf-8")
    scorer_pairs = [
        (int(scorer_id), int(portrait))
        for scorer_id, portrait in re.findall(
            r'\{(\d+)u, (\d+)u, "', scorer_include)
        if int(scorer_id) & 0x80000000
    ]
    scorer_report = json.loads((selector_dir / "league-scorer-pool-report.json")
                               .read_text(encoding="utf-8"))
    if (not scorer_pairs or scorer_report["teams"] != 459
            or scorer_report["teams_with_custom_scorers"] != 18):
        raise ValueError("Bundesliga League scorer pool is incomplete")
    scorer_probe = struct.pack("<II", *scorer_pairs[0])
    if (found < 0 or nro[atlas_offset:atlas_offset + len(atlas)] != atlas
            or b"BUNDESLIGA" not in nro or b"INDONESIA" not in nro
            or loose["build_id"].encode("ascii") not in nro
            or roster_probe not in nro or scorer_probe not in nro):
        raise ValueError("NRO does not contain the matching selector atlas/labels")
    curated_summary = {}
    if curated_dir:
        curated = json.loads((curated_dir / "exhibition_team_catalog_migration.json")
                             .read_text(encoding="utf-8"))
        current = {int(row["team_id"]): row for row in curated["teams"]}
        original = {int(row["team_id"]): row for row in rows}
        if (len(current) != 394 or len(curated["categories"]) != 27 or
                not set(current) < set(original) or
                RETIRED.intersection(row["key"] for row in curated["categories"])):
            raise ValueError("curated selector did not remove exactly the retired sections")
        for team_id, team in current.items():
            base = original[team_id]
            if (team["badge_slot"] != base["badge_slot"] or
                    team["physical_team_id"] != base["physical_team_id"]):
                raise ValueError(f"curated selector remapped team {team_id}")
        include = (curated_dir / "exhibition_teams_migration_generated.inc")
        include_header = include.read_text(encoding="utf-8")[:240]
        if f"Paired loose CPK build ID: {loose['build_id']}" not in include_header:
            raise ValueError("curated selector has a different parent CPK ID")
        for label in ("BELGIAN LEAGUE", "SWISS LEAGUE", "OTHER EUROPE",
                      "BRAZIL SERIE B", "COLOMBIAN LEAGUE", "J2 LEAGUE"):
            if label.encode("ascii") in nro:
                raise ValueError(f"removed category is still in NRO: {label}")
        leagues = json.loads((curated_dir / "fl26_league_catalog.json")
                              .read_text(encoding="utf-8"))
        if (leagues["catalog_content_id"] != curated["content_id"] or
                {22, 23, 128, 137, 69}.intersection(
                    row["competition_id"] for row in leagues["leagues"]) or
                not any(row["competition_id"] == 39 and len(row["team_ids"]) == 18
                        for row in leagues["leagues"])):
            raise ValueError("curated League Type pool does not match selector")
        curated_summary = {"curated_selector_teams": len(current),
                           "curated_categories": len(curated["categories"]),
                           "curated_league_presets": len(leagues["leagues"]) - 1,
                           "retired_sections_absent_from_nro": True}
    return {
        "schema_version": 1,
        "status": "structural_pass_hardware_pending",
        "selector_teams": len(rows),
        "bundesliga_teams": len(physical),
        "bundesliga_roster_min": min(rosters.values()),
        "bundesliga_roster_max": max(rosters.values()),
        "bundesliga_lineup_role_checks": lineup_checks,
        "indonesia_players": len(assignments[1164]),
        "native_players": len(players),
        "fl26_portraits": len(portrait_ids),
        "kits_and_crests": len(physical) + 1,
        "atlas_embedded_exactly": True,
        "roster_and_build_id_embedded": True,
        "league_scorer_pool_embedded": True,
        "loose_build_id": loose["build_id"],
        **curated_summary,
        "pending": "Switch hardware gameplan, match, visuals and save/load",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-paired-v2")
    parser.add_argument("--selector", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-selector-v2")
    parser.add_argument("--slots", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--portraits", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-portraits-v2/report.json")
    parser.add_argument("--nro", type=Path,
                        help="separately built NRO paired with candidate LooseCpk")
    parser.add_argument("--curated-selector", type=Path,
                        help="curated local selector and League manifest used for this NRO")
    parser.add_argument("--report-output", type=Path,
                        help="write validation report outside the CPK candidate")
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    if (ROOT / "local-debug").resolve() not in candidate.parents:
        raise ValueError("candidate must be inside local-debug")
    report = check(
        candidate, args.selector.resolve(),
        json.loads(args.slots.read_text(encoding="utf-8")),
        json.loads(args.portraits.read_text(encoding="utf-8")),
        args.nro.resolve() if args.nro else None,
        args.curated_selector.resolve() if args.curated_selector else None,
    )
    (args.report_output or candidate / "structural-validation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
