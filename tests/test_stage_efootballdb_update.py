from __future__ import annotations

import copy
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import efootballdb_player_import as player_import
import stage_efootballdb_update as stage
from convert_efootball10_players import read_bits, write_bits
from pes21_player_migration import PES21_POSITION_BITS, patch_verified_player
from pesdb import parse_pes21_assignments


def web_player():
    row = {"pes_id": 500, "base_pes_id": 500, "player_name": "New Test Player",
           "nationality_a": {"country_id": 10, "pes_id": 99}, "height": 180,
           "weight": 75, "age": 20, "strong_foot": 1, "strong_hand": 0,
           "main_position": 12, "playing_style": 1, "form": 3,
           "weak_foot_usage": 5, "weak_foot_accuracy": 4, "injury_resistance": 3,
           "playing_attitude": 1, "cross_over_turn": 0}
    for key in player_import.ABILITY_FIELDS.values():
        row[key] = 70
    for field in player_import.EF_POSITION_FIELDS:
        row[field.lower()] = 2 if field == "CF" else 0
    return row


def record(player_id, position=12):
    row = bytearray(312)
    struct.pack_into("<I", row, 8, player_id)
    write_bits(row, 434, 4, position)
    write_bits(row, list(PES21_POSITION_BITS.values())[position], 2, 2)
    row[251:260] = b"Test Name"
    return bytes(row)


def minimal_tables():
    return {"Player.bin": record(10) + record(20) + record(30),
            "InstallVersionPlayer.bin": struct.pack("<IIIIII", 10, 1, 20, 0, 30, 0),
            "PlayerDeleteList.bin": struct.pack("<I", 30),
            "PlayerAssignment.bin": struct.pack("<IIII", 1, 10, 100, 1),
            "PlayerAppearance.bin": struct.pack("<I", 20) + bytes(56),
            "BootsList.bin": b"", "SpecialPlayerAssignment.bin": b""}


def test_api_fields_use_country_id_and_explicit_enum_biases():
    source = player_import.web_player_to_source(web_player())
    assert source["BaseId"] == 500 and source["Country"] == 10
    assert source["WeakFootUsage"] == 4 and source["WeakFootAccuracy"] == 3
    assert source["Form"] == 2 and source["PlayingAttitude"] == 2
    native = patch_verified_player(record(30), source, 500)
    assert read_bits(native, 454, 2) == 3
    assert read_bits(native, 233, 9) == 10
    assert read_bits(native, 514, 1) == 1
    assert struct.unpack_from("<I", native, 8)[0] == 500
    assert "Overall" not in source and "face_owner_id" not in source


def test_importer_rejects_schema_drift_instead_of_clamping_identity():
    for key, invalid in (("height", 300), ("age", 0), ("strong_foot", 2),
                         ("weak_foot_usage", 6), ("speed", None)):
        with pytest.raises(ValueError):
            player_import.web_player_to_source(dict(web_player(), **{key: invalid}))


def test_native_allocator_protects_assets_history_and_unknown_table_references():
    tables = minimal_tables()
    historical = copy.deepcopy(tables)
    historical["Player.bin"] += record(500)
    sources = {500: player_import.web_player_to_source(web_player())}
    allocation = stage.allocate_players(tables, historical, {}, sources, {20})[0]
    assert allocation["physical_source_id"] == 30
    assert allocation["native_player_id"] == 501  # 500 existed historically.
    assert allocation["face_owner_id"] is None and allocation["commentary_owner_id"] is None
    tables["UnknownPlayerReference.bin"] = struct.pack("<I", 30)
    with pytest.raises(ValueError, match="unreferenced rows"):
        stage.allocate_players(tables, historical, {}, sources, {20})


def test_player_and_version_tables_are_rebuilt_together_without_touching_existing(monkeypatch):
    monkeypatch.setattr(stage, "FIXED_PLAYER_COUNT", 3)
    tables = minimal_tables()
    sources = {500: player_import.web_player_to_source(web_player())}
    allocations = [{"physical_source_id": 30, "native_player_id": 500, "base_id": 500}]
    result = stage.patch_player_tables(tables, allocations, sources)
    ids = [struct.unpack_from("<I", row, 8)[0] for row in stage.split_records(result["Player.bin"], 312, "players")]
    assert ids == [10, 20, 500]
    assert result["Player.bin"][:624] == tables["Player.bin"][:624]
    versions = list(struct.iter_unpack("<II", result["InstallVersionPlayer.bin"]))
    assert versions == [(20, 0), (500, 0), (10, 1)]
    assert result["PlayerDeleteList.bin"] == b""
    assert stage.patch_player_tables(tables, allocations, sources) == result


def formation_tables():
    roles = [0] + [1] * 10
    tactics = struct.pack("<III", 7, 100, 0) + struct.pack("<III", 8, 101, 0)
    forms = b"".join(struct.pack("<III", tactic, role, (slot << 16) | (50 << 8) | 20)
                     for tactic in (7, 8) for slot, role in enumerate(roles))
    assignments = b"".join(struct.pack("<IIII", slot + 1, slot + 1, 100, (slot << 8) | (slot + 1))
                           for slot in range(19))
    assignments += struct.pack("<IIII", 99, 99, 101, 0)
    return {"Tactics.bin": tactics, "TacticsFormation.bin": forms, "PlayerAssignment.bin": assignments}


def test_retained_shape_refills_only_missing_starter_from_survivors():
    tables = formation_tables()
    native = {key: record(key, 0 if key == 1 else 1) for key in range(1, 20)}
    roster = [{"native_player_id": key, "shirt_number": key, "key": f"ef:{key}"}
              for key in range(1, 20) if key != 3]
    plan = {"updated_team_ids": [], "local_outgoing": [{"team_id": 100}],
            "final_rosters": {"100": roster}}
    catalog = {"teams": [{"team_id": 100, "physical_team_id": 100}]}
    result, shapes = stage.arrange_rosters(plan, catalog, {}, native, tables, {})
    assert result[100][0]["native_player_id"] == 1
    assert result[100][1]["native_player_id"] == 2
    assert result[100][2]["native_player_id"] >= 12
    assert 3 not in [row["native_player_id"] for row in result[100]]
    changed = stage.patch_assignments_and_shapes(tables, catalog, result, shapes, set(), {100})
    assert changed["TacticsFormation.bin"] == tables["TacticsFormation.bin"]
    assert parse_pes21_assignments(changed["PlayerAssignment.bin"])[101][0].player_id == 99


def test_primary_web_slots_use_encoded_native_slot_not_table_row_order():
    tables = formation_tables()
    rows = stage.split_records(tables["TacticsFormation.bin"], 12, "forms")
    tables["TacticsFormation.bin"] = b"".join(reversed(rows))
    shape = [{"role": 0 if slot == 0 else 5, "depth": slot, "width": slot + 40}
             for slot in range(11)]
    roster = [{"native_player_id": key, "shirt_number": key} for key in range(1, 20)]
    out = stage.patch_assignments_and_shapes(tables,
        {"teams": [{"team_id": 100, "physical_team_id": 100}]}, {100: roster}, {100: shape}, {100}, set())
    for tactic, role, packed in struct.iter_unpack("<III", out["TacticsFormation.bin"]):
        slot = (packed >> 16) & 15
        if tactic == 7:
            assert role == shape[slot]["role"]
            assert packed & 255 == shape[slot]["depth"]
        else:
            assert role == (0 if slot == 0 else 1)


def test_team_include_preserves_catalog_id_and_binds_new_native_build():
    catalog = {"content_id": "original-catalog", "categories": [], "teams": []}
    text = stage.paired_team_include(catalog, "0123456789abcdef")
    assert "Catalog content ID: original-catalog" in text
    assert "// Paired loose CPK build ID: 0123456789abcdef" in text.splitlines()[:4]
    with pytest.raises(ValueError):
        stage.paired_team_include(catalog, "bad-id")


def test_retired_player_is_reactivated_only_with_verified_native_owner():
    person = {"key": "ef:7", "base_id": 7, "native_player_id": 700,
              "status": "removed", "native_identity_verified": True}
    plan = {"players": [], "final_rosters": {"100": [{"key": "ef:7"}]},
            "collection_snapshot_id": "snapshot"}
    state = stage.identity_state({"ef:7": person}, plan, [], {}, {700: record(700)})
    assert state["identities"]["ef:7"]["status"] == "active"
    assert state["identities"]["ef:7"]["previous_status"] == "removed"
    assert person["status"] == "removed"
    person["native_identity_verified"] = False
    with pytest.raises(ValueError, match="without native proof"):
        stage.identity_state({"ef:7": person}, plan, [], {}, {700: record(700)})
