"""Optional offline integration checks; proprietary inputs stay local/ignored.

Set PESNX_WEB_CANDIDATE to an audited candidate produced by the staging tool.
No download, runtime mutation, or fixture restoration is performed by tests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_fl26_cup_catalog import decoded_member, index_cpk
from efootballdb_reconcile import native_baseline
from stage_efootballdb_update import read_tables
from sync_efootballdb_rosters import assemble_plan, load_collection
from native_lineup import validate_formation_phases
from pesdb import parse_pes21_assignments, split_records


@pytest.fixture(scope="module")
def candidate():
    folder = os.environ.get("PESNX_WEB_CANDIDATE")
    if not folder:
        pytest.skip("requires ignored local candidate: set PESNX_WEB_CANDIDATE")
    path = Path(folder)
    def read(name):
        return json.loads((path / name).read_text(encoding="utf-8"))
    return path, read("stage-report.json"), read("transfer-plan.json"), read("identity-state.json")


def test_reconcile_same_snapshot_is_idempotent(candidate):
    path, _report, prior, state = candidate
    values = {key: Path(entry["path"]) for key, entry in prior["inputs"].items()}
    for key in ("profiles", "collection"):
        if key in values:
            values[key] = values[key].parent
    values.update(registry=path / "identity-state.json",
                  native_cpk=path / "LooseCpk/dt200_mobile_all.cpk",
                  profiles=values.get("profiles"), fl26_slots=None,
                  keep_unavailable=True, keep_identity_teams=True, allow_retained_outgoing=True)
    repeated, context = assemble_plan(argparse.Namespace(**values))
    assert repeated["status"] == "ready_to_stage"
    assert repeated["counts"]["new_players_to_import"] == 0
    assert repeated["counts"]["transfer_events"] == 0
    assert repeated["counts"]["local_teams_with_verified_outgoing"] == 0
    differed = set(repeated["updated_team_ids"]) ^ set(prior["updated_team_ids"])
    assert not differed, {
        "teams": [r for r in repeated["retained_teams"] if r["team_id"] in differed],
        "reviews": [r for r in repeated["identity_reviews"] if differed & set(r["team_ids"])],
    }
    assert {key: p["native_player_id"] for key, p in context["identities"].items()} == {
        key: p["native_player_id"] for key, p in state["identities"].items()}


def test_native_exact_web_lineups_and_formation_phases(candidate):
    path, report, plan, state = candidate
    collection = Path(plan["inputs"]["collection"]["path"]).parent
    _manifest, catalog, web = load_collection(collection, require_complete=False)
    _players, assignments = native_baseline(path / "LooseCpk/dt200_mobile_all.cpk")
    tables = read_tables(path / "LooseCpk/dt200_mobile_all.cpk")
    physical = {int(t["team_id"]): int(t["physical_team_id"]) for t in catalog["teams"]}
    shapes = {}
    for team_id in plan["updated_team_ids"]:
        team = web[team_id]
        primary = next(row for row in team["strategies"] if row["strategy"] == 0)
        expected = [state["identities"][f"ef:{s['preferred_base_id']}"]["native_player_id"]
                    for s in primary["slots"]]
        assert [row.player_id for row in assignments[physical[team_id]][:11]] == expected
        shapes[physical[team_id]] = primary["slots"]
    tactics = {tid: physical_id for tid, physical_id, _ in struct.iter_unpack("<III", tables["Tactics.bin"])}
    checked_teams = set()
    for tactic, role, packed in struct.iter_unpack("<III", tables["TacticsFormation.bin"]):
        physical_id = tactics[tactic]
        if physical_id in shapes:
            expected = shapes[physical_id][(packed >> 16) & 15]
            assert (role, packed & 255, (packed >> 8) & 255) == (
                expected["role"], expected["depth"], expected["width"])
            checked_teams.add(physical_id)
    assert len(checked_teams) == report["counts"]["web_teams"]


def test_new_players_use_placeholder_portraits_and_unique_database_identity(candidate):
    path, report, _plan, state = candidate
    allocations = json.loads((path / "allocations.json").read_text(encoding="utf-8"))
    archive = path / "LooseCpk/dt241_mobile_all.cpk"
    index, offset = index_cpk(archive)
    neutral = (path / "portraits/neutral.png").read_bytes()
    for row in allocations:
        native_id = row["native_player_id"]
        assert row["face_owner_id"] is None and row["commentary_owner_id"] is None
        assert decoded_member(archive, index, offset, f"common/player/{native_id}.png") == neutral
    db = sqlite3.connect((path / "roster-master.db").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT COUNT(*) FROM players").fetchone()[0] == len(state["identities"])
        assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == report["counts"]["playable_teams"]
        assert db.execute("SELECT COUNT(*) FROM new_player_stats").fetchone()[0] == len(allocations)
        assert db.execute("SELECT team_id FROM team_rosters GROUP BY team_id HAVING COUNT(*) NOT BETWEEN 18 AND 40").fetchall() == []
    finally:
        db.close()


def test_repaired_lineups_agree_in_every_phase_database_include_and_nro(candidate):
    path, report, _plan, _state = candidate
    scope = set(report.get("lineup_repair", {}).get("validated_team_ids", []))
    if not scope:
        pytest.skip("candidate does not request explicit local lineup repair")
    catalog = json.loads((path / "selector/catalog.json").read_text(encoding="utf-8"))
    teams = {int(t["team_id"]): t for t in catalog["teams"]}
    if report["lineup_repair"]["categories"] == ["german_teams"]:
        assert len(scope) == 18
        assert scope == {tid for tid, t in teams.items() if t["category"] == "german_teams"}
    tables = read_tables(path / "LooseCpk/dt200_mobile_all.cpk")
    players = {struct.unpack_from("<I", r, 8)[0]: r for r in split_records(tables["Player.bin"], 312, "players")}
    assignments = parse_pes21_assignments(tables["PlayerAssignment.bin"])
    include = (path / "selector/exhibition_rosters_migration_canary_generated.inc").read_text(encoding="utf-8")
    embedded_ids = {int(tid): list(map(int, re.findall(r"(\d+)u", values))) for tid, values in re.findall(
        r"exhibition_migration_team_(\d+)_players\[\] = \{(.*?)\};", include, re.S)}
    nro = (path / "pes21_nx.nro").read_bytes()
    assert nro[16:20] == b"NRO0" and report["build_id"].encode() in nro
    db = sqlite3.connect((path / "roster-master.db").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for tid in sorted(scope):
            physical = int(teams[tid]["physical_team_id"])
            native_ids = [r.player_id for r in assignments[physical]]
            checks = validate_formation_phases(tables["Tactics.bin"], tables["TacticsFormation.bin"],
                                              physical, native_ids[:11], players)
            assert checks == report["checks"]["lineup_role_checks"][str(tid)]
            assert all(c["full"] + c["partial"] == 11 for c in checks)
            assert embedded_ids[tid] == native_ids
            assert struct.pack("<" + "I" * len(native_ids), *native_ids) in nro
            saved = db.execute("SELECT p.native_id FROM starting_lineups s JOIN players p USING(identity_key) "
                               "WHERE team_id=? ORDER BY slot", (tid,)).fetchall()
            assert [r[0] for r in saved] == native_ids[:11]
    finally:
        db.close()


def test_lineup_fix_preserves_prior_transfers_identity_assets_and_other_teams(candidate):
    path, report, _plan, state = candidate
    reference = os.environ.get("PESNX_WEB_LINEUP_BASELINE")
    if not reference:
        pytest.skip("set PESNX_WEB_LINEUP_BASELINE to compare the previous paired transfer candidate")
    previous = Path(reference)
    old_state = json.loads((previous / "identity-state.json").read_text(encoding="utf-8"))
    assert state["identities"] == old_state["identities"]
    old = read_tables(previous / "LooseCpk/dt200_mobile_all.cpk")
    new = read_tables(path / "LooseCpk/dt200_mobile_all.cpk")
    assert set(old) == set(new)
    for table in old:
        if table != "PlayerAssignment.bin":
            assert old[table] == new[table], table
    before, after = [parse_pes21_assignments(t["PlayerAssignment.bin"]) for t in (old, new)]
    catalog = json.loads((path / "selector/catalog.json").read_text(encoding="utf-8"))
    physical = {int(t["team_id"]): int(t["physical_team_id"]) for t in catalog["teams"]}
    repaired = {physical[t] for t in report["lineup_repair"]["rebalanced_local_team_ids"]}
    assert before.keys() == after.keys()
    for team in before:
        assert {p.player_id: p.shirt for p in before[team]} == {p.player_id: p.shirt for p in after[team]}
        if team not in repaired:
            assert before[team] == after[team], team
    # Includes all untouched team assets, portraits, kits, and UI archives.
    import hashlib
    for archive in (previous / "LooseCpk").glob("*.cpk"):
        if archive.name != "dt200_mobile_all.cpk":
            with archive.open("rb") as source, (path / "LooseCpk" / archive.name).open("rb") as target:
                assert hashlib.file_digest(source, "sha256").digest() == hashlib.file_digest(target, "sha256").digest(), archive.name
