#!/usr/bin/env python3
"""Materialize an audited eFootballDB plan into a detached local candidate.

Never edits the input CPK, old master database, registry, saves or runtime.
Existing player records and asset ownership remain byte-identical. New players
use unreferenced physical rows, fresh asset-safe IDs and neutral portraits.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sqlite3
import struct
from pathlib import Path

from build_fl26_cup_catalog import decoded_member, index_cpk
from convert_efootball10_players import read_bits
from efootballdb_player_import import validate_api_enum_encoding, web_player_to_source
from efootballdb_reconcile import source_identity
from generate_pesdb_runtime_rosters import _choose_balanced_xi_with_score
from native_lineup import balanced_roster_order, validate_formation_phases
from pes21_player_migration import (
    PES21_POSITION_BITS, encode_pes21_wesys, identity_fingerprint, normalize_name,
    patch_verified_player, protected_face_ids, table_raw,
)
from pesdb import parse_pes21_assignments, parse_player_records, split_records
from sync_efootballdb_rosters import (
    assemble_plan, digest, json_bytes, local_output, read_json, write_json,
)


PREFIX = "common/etc/pesdb/"
FIXED_PLAYER_COUNT = 43074


def read_tables(cpk: Path) -> dict[str, bytes]:
    index, offset = index_cpk(cpk)
    return {Path(name).name: decoded_member(cpk, index, offset, name)
            for name in index if name.endswith(".bin") and
            name.startswith((PREFIX, "common/etc/appearance/"))}


def fixed_ids(raw: bytes, width: int, offsets: tuple[int, ...]) -> set[int]:
    if len(raw) % width:
        raise ValueError("partial fixed-size native table")
    return {struct.unpack_from("<I", raw, start + offset)[0]
            for start in range(0, len(raw), width) for offset in offsets}


def allocate_players(tables: dict, historical: dict, identities: dict,
                     new_sources: dict, face_ids: set[int]) -> list[dict]:
    current_ids = fixed_ids(tables["Player.bin"], 312, (8,))
    historical_ids = fixed_ids(historical["Player.bin"], 312, (8,))
    reserved = set(face_ids)
    for person in identities.values():
        reserved.add(person["native_player_id"])
        reserved.add(int(person["registry"].get("physical_source_id", person["native_player_id"])))
    # Conservative protection also covers undocumented PESDB tables: never
    # consume a row whose ID occurs as an aligned word in another native table.
    for table_set in (tables, historical):
        for name, raw in table_set.items():
            if name in ("Player.bin", "InstallVersionPlayer.bin", "PlayerDeleteList.bin"):
                continue
            reserved.update(value[0] for value in struct.iter_unpack("<I", raw[:len(raw) // 4 * 4]))
    deleted = fixed_ids(tables["PlayerDeleteList.bin"], 4, (0,))
    clean = sorted(current_ids - reserved, key=lambda value: (value not in deleted, value))
    if len(clean) < len(new_sources):
        raise ValueError(f"only {len(clean)} unreferenced rows for {len(new_sources)} new players")
    # Commentary/face lookup can still refer to a historical native ID even if
    # that row has since been renamed. A fresh ID must avoid BOTH ID sets.
    unsafe_ids = current_ids | historical_ids | reserved
    candidate_id = max(current_ids | historical_ids | face_ids |
                       {row["native_player_id"] for row in identities.values()}) + 1
    result = []
    for physical_id, base_id in zip(clean, sorted(new_sources)):
        native_id = base_id
        if native_id in unsafe_ids:
            while candidate_id in unsafe_ids:
                candidate_id += 1
            native_id = candidate_id
            candidate_id += 1
        if not 0 < native_id < 0x80000000:
            raise ValueError("new native ID exceeds the supported positive namespace")
        unsafe_ids.add(native_id)
        result.append({"base_id": base_id, "native_player_id": native_id,
                       "physical_source_id": physical_id,
                       "face_owner_id": None, "commentary_owner_id": None,
                       "portrait_asset_id": native_id, "portrait_status": "neutral_placeholder"})
    return result


def patch_player_tables(tables: dict, allocations: list[dict], new_sources: dict) -> dict:
    rows = {struct.unpack_from("<I", row, 8)[0]: row
            for row in split_records(tables["Player.bin"], 312, "Player.bin")}
    if len(rows) != FIXED_PLAYER_COUNT:
        raise ValueError("baseline player table does not have 43,074 unique rows")
    remap = {}
    for allocation in allocations:
        old, new = allocation["physical_source_id"], allocation["native_player_id"]
        if old in remap or old not in rows or new in rows:
            raise ValueError("invalid or colliding clean-row allocation")
        template = rows.pop(old)
        rows[new] = patch_verified_player(template, new_sources[allocation["base_id"]], new)
        remap[old] = new
    versions = [(remap.get(player_id, player_id), version)
                for player_id, version in struct.iter_unpack("<II", tables["InstallVersionPlayer.bin"])]
    versions.sort(key=lambda row: (row[1], row[0]))
    if len(versions) != len(rows) or {row[0] for row in versions} != set(rows):
        raise ValueError("Player/InstallVersion row sets differ")
    retired = set(remap) | set(remap.values())
    deleted = sorted(fixed_ids(tables["PlayerDeleteList.bin"], 4, (0,)) - retired)
    return {
        "Player.bin": b"".join(rows[key] for key in sorted(rows)),
        "InstallVersionPlayer.bin": b"".join(struct.pack("<II", *row) for row in versions),
        "PlayerDeleteList.bin": b"".join(struct.pack("<I", value) for value in deleted),
    }


def native_shapes(tables: dict) -> tuple[dict, dict]:
    tactics = {}
    for tactic_id, team_id, _flags in struct.iter_unpack("<III", tables["Tactics.bin"]):
        tactics.setdefault(team_id, []).append(tactic_id)
    phases = {}
    for tactic_id, role, packed in struct.iter_unpack("<III", tables["TacticsFormation.bin"]):
        if (packed >> 20) & 3:
            continue
        slot = (packed >> 16) & 15
        if not (slot < 11 and 0 <= role <= 12):
            raise ValueError("invalid native formation slot/role")
        slots = phases.setdefault(tactic_id, {})
        if slot in slots:
            raise ValueError("duplicate default formation slot")
        slots[slot] = {"role": role, "depth": packed & 255, "width": (packed >> 8) & 255}
    shapes = {}
    for team_id, tactic_ids in tactics.items():
        slots = phases.get(tactic_ids[0], {})
        if set(slots) == set(range(11)):
            shapes[team_id] = [slots[index] for index in range(11)]
    return shapes, tactics


def arrange_rosters(plan: dict, catalog: dict, tactics: dict, native: dict,
                    baseline_tables: dict, ratings: dict,
                    repair_team_ids: set[int] | None = None) -> tuple[dict, dict]:
    repair_team_ids = repair_team_ids or set()
    shapes, _ = native_shapes(baseline_tables)
    old_rosters = parse_pes21_assignments(baseline_tables["PlayerAssignment.bin"])
    result, selected_shapes = {}, {}
    web_ids = set(plan["updated_team_ids"])
    outgoing_ids = {row["team_id"] for row in plan["local_outgoing"]}
    for team in catalog["teams"]:
        team_id, physical_id = int(team["team_id"]), int(team["physical_team_id"])
        if physical_id not in shapes:
            raise ValueError(f"no complete native formation for team {team_id}")
        roster = copy.deepcopy(plan["final_rosters"][str(team_id)])
        if team_id in web_ids:
            strategies = tactics["teams"][str(team_id)]["strategies"]
            strategy = next((row for row in strategies if row["strategy"] == 0), None)
            if strategy is None:
                raise ValueError(f"team {team_id} lacks a primary web strategy")
            shape = [{key: row[key] for key in ("role", "depth", "width")} for row in strategy["slots"]]
            if [row["base_id"] for row in roster[:11]] != [row["preferred_base_id"] for row in strategy["slots"]]:
                raise ValueError(f"team {team_id} lost the exact web starting XI")
        else:
            shape = shapes[physical_id]
        if team_id in repair_team_ids and team_id not in web_ids:
            order = balanced_roster_order([r["native_player_id"] for r in roster],
                                         [s["role"] for s in shape], native, ratings)
            roster = [roster[i] for i in order]
        elif team_id in outgoing_ids:
            candidates = []
            for member in roster:
                native_id = member["native_player_id"]
                record = native[native_id]
                familiarity = tuple(read_bits(record, bit, 2) for bit in PES21_POSITION_BITS.values())
                position = read_bits(record, 434, 4)
                candidates.append((native_id, ratings.get(native_id, 40), position, familiarity))
            preferences = [row.player_id for row in old_rosters[physical_id][:11]]
            first, bench, _ = _choose_balanced_xi_with_score(
                candidates, [slot["role"] for slot in shape], preferences)
            # Keep surviving bench order; only holes in the XI need refilling.
            picked = set(first)
            roster = [roster[index] for index in first + [i for i in range(len(roster)) if i not in picked]]
        for order, row in enumerate(roster):
            row["order"] = order
        if not 18 <= len(roster) <= 40 or len({r["native_player_id"] for r in roster}) != len(roster):
            raise ValueError(f"invalid final roster for team {team_id}")
        for slot, member in zip(shape, roster[:11], strict=True):
            position = read_bits(native[member["native_player_id"]], 434, 4)
            if team_id in web_ids | outgoing_ids | repair_team_ids and (slot["role"] == 0) != (position == 0):
                raise ValueError(f"keeper/outfield crossing in team {team_id}")
        result[team_id] = roster
        selected_shapes[team_id] = shape
    return result, selected_shapes


def patch_assignments_and_shapes(tables: dict, catalog: dict, rosters: dict,
                                shapes: dict, web_ids: set[int], outgoing_ids: set[int],
                                repair_team_ids: set[int] | None = None) -> dict:
    physical = {int(row["team_id"]): int(row["physical_team_id"]) for row in catalog["teams"]}
    changed_ids = web_ids | outgoing_ids | (repair_team_ids or set())
    changed_teams = {physical[team_id] for team_id in changed_ids}
    original = list(struct.iter_unpack("<IIII", tables["PlayerAssignment.bin"]))
    records = [row for row in original if row[2] not in changed_teams]
    next_id = max(row[0] for row in original) + 1
    for team_id in sorted(changed_ids):
        for order, member in enumerate(rosters[team_id]):
            shirt = member["shirt_number"]
            if not 0 <= shirt <= 255:
                raise ValueError("shirt number exceeds native byte")
            records.append((next_id, member["native_player_id"], physical[team_id], (order << 8) | shirt))
            next_id += 1
    if len({row[0] for row in records}) != len(records):
        raise ValueError("duplicate assignment record ID")
    _, tactics_by_team = native_shapes(tables)
    selected = {tactic_id: shapes[team_id] for team_id in web_ids
                for tactic_id in tactics_by_team[physical[team_id]]}
    formations = []
    # Existing native phase/strategy contract uses one starting order. Keep the
    # exact primary web shape across native phases, as in the proven importer.
    for tactic_id, role, packed in struct.iter_unpack("<III", tables["TacticsFormation.bin"]):
        if tactic_id in selected:
            slot = (packed >> 16) & 15
            if slot >= 11:
                raise ValueError("invalid non-default native formation slot")
            shape = selected[tactic_id][slot]
            role = shape["role"]
            packed = (packed & 0xffff0000) | (shape["width"] << 8) | shape["depth"]
        formations.append((tactic_id, role, packed))
    return {"PlayerAssignment.bin": b"".join(struct.pack("<IIII", *row) for row in records),
            "TacticsFormation.bin": b"".join(struct.pack("<III", *row) for row in formations)}


def identity_state(identities: dict, plan: dict, allocations: list, sources: dict, native: dict) -> dict:
    result = copy.deepcopy(identities)
    for row in plan["players"]:
        if row["status"] != "promote_fl26_identity":
            continue
        person = result.pop(row["previous_key"])
        person.update(key=row["key"], base_id=row["base_id"],
                      previous_keys=[row["previous_key"]],
                      asset_fingerprint=person["fingerprint"])
        # Keep the FL26 provenance fingerprint as the asset owner proof; the
        # new BaseId mapping is an alias to the same native person, not a copy.
        result[row["key"]] = person
    for allocation in allocations:
        base, native_id = allocation["base_id"], allocation["native_player_id"]
        source = sources[base]
        key = f"ef:{base}"
        result[key] = {**source_identity(source), "key": key,
            "native_player_id": native_id, "status": "active", "native_present": True,
            "aliases": [normalize_name(source["Name"])], "fingerprint": identity_fingerprint(source),
            "registry": {**allocation, "source_card_id": source["Id"],
                         "canonical_name": source["Name"], "ef_base_id": base}}
    rostered = {row["key"] for roster in plan["final_rosters"].values() for row in roster}
    for key, person in result.items():
        if key in rostered and person["status"] != "active":
            if not person.get("native_identity_verified", False):
                raise ValueError(f"retired identity cannot be reactivated without native proof: {key}")
            person["previous_status"] = person["status"]
            person["status"] = "active"
        native_id = person["native_player_id"]
        person["native_sha256"] = digest(native[native_id]) if native_id in native else None
        if not person["native_sha256"] and person["status"] == "active":
            raise ValueError(f"active canonical identity missing from staged native table: {key}")
    return {"schema_version": 1, "generator": "tools/stage_efootballdb_update.py",
            "collection_snapshot_id": plan["collection_snapshot_id"], "identities": result}


def write_database(path: Path, catalog: dict, state: dict, rosters: dict,
                   shapes: dict, sources: dict, report: dict) -> None:
    """Separate transactional catalog with one identity and several memberships."""
    db = sqlite3.connect(path)
    try:
        db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE players(identity_key TEXT PRIMARY KEY, base_id INTEGER UNIQUE,
                native_id INTEGER NOT NULL UNIQUE, name TEXT NOT NULL,
                fingerprint TEXT NOT NULL, native_sha256 TEXT, identity_json TEXT NOT NULL);
            CREATE TABLE aliases(alias TEXT PRIMARY KEY, identity_key TEXT NOT NULL REFERENCES players);
            CREATE TABLE teams(team_id INTEGER PRIMARY KEY, physical_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL, kind TEXT NOT NULL, category TEXT NOT NULL);
            CREATE TABLE team_rosters(team_id INTEGER NOT NULL REFERENCES teams,
                roster_order INTEGER NOT NULL, identity_key TEXT NOT NULL REFERENCES players,
                shirt INTEGER NOT NULL CHECK(shirt BETWEEN 0 AND 255),
                PRIMARY KEY(team_id, roster_order), UNIQUE(team_id, identity_key));
            CREATE TABLE starting_lineups(team_id INTEGER NOT NULL REFERENCES teams,
                slot INTEGER NOT NULL CHECK(slot BETWEEN 0 AND 10),
                identity_key TEXT NOT NULL REFERENCES players, role INTEGER NOT NULL,
                depth INTEGER NOT NULL, width INTEGER NOT NULL, PRIMARY KEY(team_id,slot));
            CREATE TABLE new_player_stats(base_id INTEGER PRIMARY KEY REFERENCES players(base_id),
                source_json TEXT NOT NULL);
            CREATE TABLE changes(event_id INTEGER PRIMARY KEY, event_json TEXT NOT NULL);
            CREATE VIEW v_team_rosters AS SELECT t.name AS team,p.name AS player,p.base_id,p.native_id,
                t.kind,r.roster_order,r.shirt FROM team_rosters r JOIN teams t USING(team_id)
                JOIN players p USING(identity_key);
        """)
        with db:
            for key, value in {"schema_version": "1", "stage": "hardware_validation_pending",
                               "collection_snapshot_id": report["collection_snapshot_id"],
                               "existing_player_records": "byte_identical"}.items():
                db.execute("INSERT INTO metadata VALUES(?,?)", (key, value))
            for key, person in sorted(state["identities"].items()):
                db.execute("INSERT INTO players VALUES(?,?,?,?,?,?,?)", (
                    key, person["base_id"], person["native_player_id"], person["name"],
                    person["fingerprint"], person["native_sha256"], json_bytes(person).decode()))
                for alias in person.get("previous_keys", []):
                    db.execute("INSERT INTO aliases VALUES(?,?)", (alias, key))
            for team in sorted(catalog["teams"], key=lambda row: int(row["team_id"])):
                team_id = int(team["team_id"])
                db.execute("INSERT INTO teams VALUES(?,?,?,?,?)", (team_id, int(team["physical_team_id"]),
                    team["display_name"], team["kind"], team["category"]))
                for order, row in enumerate(rosters[team_id]):
                    db.execute("INSERT INTO team_rosters VALUES(?,?,?,?)", (team_id, order, row["key"], row["shirt_number"]))
                for slot, shape in enumerate(shapes[team_id]):
                    db.execute("INSERT INTO starting_lineups VALUES(?,?,?,?,?,?)", (team_id, slot,
                        rosters[team_id][slot]["key"], shape["role"], shape["depth"], shape["width"]))
            for base, source in sources.items():
                db.execute("INSERT INTO new_player_stats VALUES(?,?)", (base, json_bytes(source).decode()))
            for number, event in enumerate(report["transfers"]):
                db.execute("INSERT INTO changes VALUES(?,?)", (number, json_bytes(event).decode()))
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("staged database integrity/foreign-key failure")
    finally:
        db.close()


def validate_tables(before: dict, after: dict, allocations: list, catalog: dict,
                    rosters: dict, plan: dict, repair_team_ids: set[int] | None = None) -> dict:
    repair_team_ids = repair_team_ids or set()
    old_players = {struct.unpack_from("<I", r, 8)[0]: r for r in split_records(before["Player.bin"], 312, "old players")}
    players = parse_player_records(after["Player.bin"], "pes21")
    rows = {struct.unpack_from("<I", r, 8)[0]: r for r in split_records(after["Player.bin"], 312, "new players")}
    replaced = {row["physical_source_id"] for row in allocations}
    if len(players) != FIXED_PLAYER_COUNT:
        raise ValueError("fixed player count changed")
    if any(rows.get(key) != row for key, row in old_players.items() if key not in replaced):
        raise ValueError("an existing player record was modified")
    assignments = parse_pes21_assignments(after["PlayerAssignment.bin"])
    if any(row.player_id not in players for entries in assignments.values() for row in entries):
        raise ValueError("dangling native assignment reference")
    changed = set(plan["updated_team_ids"]) | {row["team_id"] for row in plan["local_outgoing"]} | repair_team_ids
    physical_changed = {int(row["physical_team_id"]) for row in catalog["teams"] if int(row["team_id"]) in changed}
    old_assignments = parse_pes21_assignments(before["PlayerAssignment.bin"])
    old_shapes, _ = native_shapes(before)
    baseline_warnings = []
    lineup_checks = {}
    for physical_id in old_assignments:
        if physical_id not in physical_changed and assignments.get(physical_id) != old_assignments[physical_id]:
            raise ValueError("an unrelated native roster was modified")
    for team in catalog["teams"]:
        logical, physical = int(team["team_id"]), int(team["physical_team_id"])
        expected = [(row["native_player_id"], row["shirt_number"]) for row in rosters[logical]]
        actual = [(row.player_id, row.shirt) for row in assignments[physical]]
        if expected != actual:
            raise ValueError(f"native and canonical roster disagree: {logical}")
        if logical in repair_team_ids:
            lineup_checks[logical] = validate_formation_phases(
                after["Tactics.bin"], after["TacticsFormation.bin"], physical,
                [r.player_id for r in assignments[physical][:11]], rows)
        if logical not in changed and any((shape["role"] == 0) != (players[row.player_id].position == 0)
                for shape, row in zip(old_shapes[physical], assignments[physical][:11])):
            baseline_warnings.append(logical)
    return {"fixed_player_rows": len(players), "existing_records_unchanged": len(old_players) - len(replaced),
            "new_players": len(allocations), "rosters_verified": len(catalog["teams"]),
            "unrelated_rosters_unchanged": True, "assignment_references_valid": True,
            "lineup_role_checks": lineup_checks,
            "unchanged_baseline_lineup_warning_team_ids": baseline_warnings}


def lineup_repair_scope(catalog: dict, categories: list[str]) -> set[int]:
    """Explicit opt-in scope; missing/typo category must not silently do nothing."""
    available = {team["category"] for team in catalog["teams"]}
    unknown = set(categories) - available
    if unknown:
        raise ValueError(f"unknown lineup repair categories: {sorted(unknown)}")
    return {int(team["team_id"]) for team in catalog["teams"] if team["category"] in categories}


def load_verified_plan(path: Path) -> tuple[dict, dict, argparse.Namespace]:
    report = read_json(path)
    if report["status"] != "ready_to_stage":
        raise ValueError("plan still contains blocking identity/source errors")
    values = {}
    for key, entry in report["inputs"].items():
        source = Path(entry["path"])
        if digest(source.read_bytes()) != entry["sha256"]:
            raise ValueError(f"plan input changed after reconciliation: {key}")
        values[key] = source.parent if key in ("collection", "profiles") else source
    values.setdefault("profiles", None)
    values.setdefault("fl26_slots", None)
    values.update(keep_unavailable=report["policies"]["keep_unavailable_local_teams"],
                  keep_identity_teams=report["policies"]["keep_identity_review_teams"],
                  allow_retained_outgoing=report["policies"]["allow_retained_outgoing"])
    args = argparse.Namespace(**values)
    rebuilt, context = assemble_plan(args)
    if rebuilt != report:
        raise ValueError("plan differs from offline reconciliation; regenerate/review it before staging")
    return report, context, args


def paired_team_include(catalog: dict, build_id: str) -> str:
    from generate_exhibition_team_catalog import render_team_include

    if not re.fullmatch(r"[0-9a-f]{16}", build_id):
        raise ValueError("invalid paired build ID")
    return render_team_include(catalog).replace(
        "// Do not edit manually.",
        f"// Paired loose CPK build ID: {build_id}\n// Do not edit manually.", 1)


def package_candidate(output: Path, base: Path, modified: dict, allocations: list,
                      catalog: dict, state: dict, ratings_include: Path, build_id: str) -> dict:
    from pes21_player_migration import neutral_portrait, repack_migration_cpks
    from prepare_loose_cpk import clone_full, update, verify
    from stage_fl26_league_scorer_pool import render as render_scorers
    from stage_fl26_migration_roster_include import make_include, rating_block

    portraits = output / "portraits"
    neutral_portrait(portraits / "neutral.png")
    placeholder = (portraits / "neutral.png").read_bytes()
    for row in allocations:
        (portraits / f"{row['native_player_id']}.png").write_bytes(placeholder)
    archives = output / "packed"
    archives.mkdir()
    dt200, dt241, packed = repack_migration_cpks(
        table_files={PREFIX + name: output / "tables" / name for name in modified},
        portrait_rows=allocations, portrait_dir=portraits,
        base_dt200=base / "LooseCpk/dt200_mobile_all.cpk",
        base_dt241=base / "LooseCpk/dt241_mobile_all.cpk", output=archives)
    clone_full(base, output, build_id)
    update(output, "dt200_mobile_all.cpk", dt200)
    update(output, "dt241_mobile_all.cpk", dt241)
    manifest = verify(output)
    before = verify(base)
    untouched = set(row["name"] for row in manifest["files"]) - {"dt200_mobile_all.cpk", "dt241_mobile_all.cpk"}
    if {row["name"]: row["sha256"] for row in manifest["files"] if row["name"] in untouched} != {
        row["name"]: row["sha256"] for row in before["files"] if row["name"] in untouched}:
        raise ValueError("an unrelated CPK changed")
    selector = output / "selector"
    selector.mkdir()
    (selector / "exhibition_teams_migration_generated.inc").write_text(
        paired_team_include(catalog, build_id), encoding="utf-8")
    (selector / "exhibition_rosters_migration_canary_generated.inc").write_text(
        make_include(catalog, modified["PlayerAssignment.bin"], modified["Player.bin"], build_id,
                     rating_block(ratings_include.read_text(encoding="utf-8")),
                     expected_teams=len(catalog["teams"])), encoding="utf-8")
    players = parse_player_records(modified["Player.bin"], "pes21")
    ef_players, fl_players = [], []
    for key, person in state["identities"].items():
        native_id = person["native_player_id"]
        if native_id not in players:
            continue
        if person["base_id"] is not None:
            ef_players.append({"status": "active", "native_player_id": native_id,
                               "ef_base_id": person["base_id"], "portrait_asset_id": native_id,
                               "canonical_name": person["name"]})
        else:
            fl_players.append({"native_player_id": native_id,
                               "fl26_player_id": int(key.split(":")[1]), "name": person["name"]})
    scorer_text, scorer_report = render_scorers(catalog,
        parse_pes21_assignments(modified["PlayerAssignment.bin"]),
        {key: row.position for key, row in players.items()},
        {"players": ef_players}, {"player_slots": fl_players}, expected_teams=len(catalog["teams"]))
    (selector / "league_scorer_pool_generated.inc").write_text(scorer_text, encoding="utf-8")
    write_json(selector / "catalog.json", catalog)
    # Only generated intermediate duplicates are removed, never input archives.
    for name in ("dt200_mobile_all.cpk", "dt241_mobile_all.cpk", "dt241-replaced.cpk"):
        intermediate = archives / name
        if intermediate.is_file():
            intermediate.unlink()
    return {**packed, "build_id": manifest["build_id"], "unrelated_cpks_unchanged": len(untouched),
            "scorer_pool": scorer_report, "matching_nro": "pending"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--historical-tables", required=True, type=Path)
    parser.add_argument("--face-inventory", required=True, type=Path)
    parser.add_argument("--ratings-include", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package-base", type=Path,
                        help="optionally pair dt200/dt241 with this exact verified loose runtime")
    parser.add_argument("--repair-lineup-category", action="append", default=[],
                        help="rebalance retained local XIs in this selector category; preserve exact web XIs")
    args = parser.parse_args()
    output = local_output(args.output)
    if output.exists():
        raise ValueError("candidate output must be a new directory")
    plan, context, inputs = load_verified_plan(args.plan)
    if args.package_base and (args.package_base / "LooseCpk/dt200_mobile_all.cpk").resolve() != inputs.native_cpk.resolve():
        raise ValueError("packaging base is not the audited native database")
    sources = {row["base_id"]: web_player_to_source(context["payloads"][row["base_id"]])
               for row in plan["players"] if row["apply"] and row["status"] == "new_web_player"}
    enum_report = validate_api_enum_encoding(context["profiles"], read_json(inputs.source_db))
    tables = read_tables(inputs.native_cpk)
    historical = {path.name: table_raw(path) for path in args.historical_tables.glob("*.bin")}
    required = {"Player.bin", "PlayerAssignment.bin", "PlayerAppearance.bin", "BootsList.bin", "SpecialPlayerAssignment.bin"}
    if not required <= historical.keys():
        raise ValueError("historical player and auxiliary ownership fixtures are incomplete")
    allocations = allocate_players(tables, historical, context["identities"], sources,
                                   protected_face_ids(args.face_inventory))
    modified = patch_player_tables(tables, allocations, sources)
    native = {struct.unpack_from("<I", row, 8)[0]: row
              for row in split_records(modified["Player.bin"], 312, "new players")}
    state = identity_state(context["identities"], plan, allocations, sources, native)
    for roster in plan["final_rosters"].values():
        for member in roster:
            member["native_player_id"] = state["identities"][member["key"]]["native_player_id"]
    from stage_fl26_migration_roster_include import rating_block
    block = rating_block(args.ratings_include.read_text(encoding="utf-8"))
    ratings = {int(key): int(value) for key, value in re.findall(r"\{(\d+)u,\s*(\d+),", block)}
    catalog = context["catalog"]
    repair_team_ids = lineup_repair_scope(catalog, args.repair_lineup_category)
    rosters, shapes = arrange_rosters(plan, catalog, context["tactics"], native, tables, ratings, repair_team_ids)
    modified.update(patch_assignments_and_shapes(tables, catalog, rosters, shapes,
        set(plan["updated_team_ids"]), {row["team_id"] for row in plan["local_outgoing"]}, repair_team_ids))
    checks = validate_tables(tables, {**tables, **modified}, allocations, catalog, rosters, plan, repair_team_ids)
    # Independent repeat from identical inputs catches nondeterministic native
    # writes before any candidate files are emitted.
    repeated = patch_player_tables(tables, allocations, sources)
    repeated_rosters, repeated_shapes = arrange_rosters(
        plan, catalog, context["tactics"], native, tables, ratings, repair_team_ids)
    if (repeated_rosters, repeated_shapes) != (rosters, shapes):
        raise ValueError("lineup selection is not deterministic")
    repeated.update(patch_assignments_and_shapes(tables, catalog, rosters, shapes,
        set(plan["updated_team_ids"]), {row["team_id"] for row in plan["local_outgoing"]}, repair_team_ids))
    if repeated != modified:
        raise ValueError("native table rebuild is not deterministic")
    build_id = digest(json_bytes({"collection": plan["collection_snapshot_id"],
        "tables": {name: digest(raw) for name, raw in modified.items()}}))[:16]
    state["build_id"] = build_id
    output.mkdir(parents=True)
    (output / "tables").mkdir()
    for name, raw in modified.items():
        (output / "tables" / name).write_bytes(encode_pes21_wesys(raw))
    write_json(output / "identity-state.json", state)
    write_json(output / "allocations.json", allocations)
    write_json(output / "final-rosters.json", rosters)
    write_json(output / "transfer-plan.json", plan)
    write_database(output / "roster-master.db", catalog, state, rosters, shapes, sources, plan)
    report = {"schema_version": 1, "status": "tables_and_database_staged_hardware_pending",
        "collection_snapshot_id": plan["collection_snapshot_id"], "build_id": build_id,
        "counts": plan["counts"], "checks": {**checks, "deterministic_rebuild": True},
        "lineup_repair": {"categories": sorted(set(args.repair_lineup_category)),
            "validated_team_ids": sorted(repair_team_ids),
            "rebalanced_local_team_ids": sorted(repair_team_ids - set(plan["updated_team_ids"])),
            "preserved_web_team_ids": sorted(repair_team_ids & set(plan["updated_team_ids"])),
            "policy": "primary_or_native_familiarity; unpinned_local_XI; stable_bench; unchanged_identities"},
        "enum_encoding": enum_report, "input_plan_sha256": digest(args.plan.read_bytes()),
        "new_asset_policy": "neutral_portrait_generic_native_face_no_commentary_donor",
        "existing_player_stats_assets": "preserved", "active_runtime_modified": False,
        "tables": {name: digest(raw) for name, raw in modified.items()},
        "historical_inputs": {name: digest(raw) for name, raw in historical.items()},
        "face_inventory_sha256": digest(args.face_inventory.read_bytes())}
    if args.package_base:
        report["package"] = package_candidate(output, args.package_base, modified, allocations,
                                               catalog, state, args.ratings_include, build_id)
        report["status"] = "paired_cpks_matching_nro_and_hardware_pending"
    write_json(output / "stage-report.json", report)
    print(json.dumps({"output": str(output), "status": report["status"], "build_id": build_id,
                      **checks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
