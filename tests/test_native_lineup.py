"""Synthetic native tables only; no game fixtures are required."""
import copy
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from convert_efootball10_players import write_bits
from native_lineup import balanced_roster_order, position_fit, validate_formation_phases, validate_starting_order
from pes21_player_migration import PES21_POSITION_BITS
import stage_efootballdb_update as stage


ROLES = [0, 1, 1, 3, 2, 4, 5, 8, 10, 9, 12]


def player(pid, position, alternatives=None):
    row = bytearray(312)
    struct.pack_into("<I", row, 8, pid)
    write_bits(row, 434, 4, position)
    for role, value in {position: 2, **(alternatives or {})}.items():
        write_bits(row, list(PES21_POSITION_BITS.values())[role], 2, value)
    row[251:255] = b"Test"
    return bytes(row)


def grouped_roster():
    positions = [0, 0, 0] + ROLES[1:] + [1, 1, 5, 12, 12]
    return {pid: player(pid, pos) for pid, pos in enumerate(positions, 100)}


def formations(roles=ROLES):
    tactics = struct.pack("<III", 7, 100, 0) + struct.pack("<III", 8, 100, 0)
    rows = [struct.pack("<III", tid, role, (phase << 20) | (slot << 16) | (50 << 8) | 20)
            for tid in (7, 8) for phase in range(3) for slot, role in enumerate(roles)]
    return tactics, b"".join(reversed(rows))


def test_grouped_memberships_are_not_pinned_to_starting_slots():
    records = grouped_roster()
    before = copy.deepcopy(records)
    ids = list(records)
    order = balanced_roster_order(ids, ROLES, records)
    first = [ids[i] for i in order[:11]]
    assert validate_starting_order(first, ROLES, records) == {"full": 11, "partial": 0}
    assert len(set(order)) == len(ids) and set(order) == set(range(len(ids)))
    assert order[11:] == [i for i in range(len(ids)) if i not in order[:11]]
    assert records == before
    assert order == balanced_roster_order(ids, ROLES, records)
    ordered_ids = [ids[i] for i in order]
    assert balanced_roster_order(ordered_ids, ROLES, records) == list(range(len(ids)))


def test_strict_solver_prefers_playable_partials_over_more_full_plus_an_unfamiliar_slot():
    roles = [0] + [1] * 8 + [5, 12]
    records = {1: player(1, 0), **{i: player(i, 1) for i in range(2, 10)},
               10: player(10, 8, {5: 2, 12: 1}), 11: player(11, 11, {5: 1}),
               **{i: player(i, 0) for i in range(12, 19)}}
    ids = list(records)
    order = balanced_roster_order(ids, roles, records)
    first = [ids[i] for i in order[:11]]
    assert first[-2:] == [11, 10]
    assert validate_starting_order(first, roles, records) == {"full": 9, "partial": 2}


def test_keeper_cannot_be_outfield_even_with_corrupt_familiarity():
    assert position_fit(player(1, 0, {12: 2}), 12) == -1
    assert position_fit(player(2, 12, {0: 2}), 0) == -1


def test_impossible_shape_fails_instead_of_using_defenders_as_attackers():
    records = {i: player(i, 0 if i == 1 else 1) for i in range(1, 19)}
    with pytest.raises(ValueError, match="complete position-balanced"):
        balanced_roster_order(list(records), ROLES, records)


def test_partial_rating_coverage_does_not_penalize_unscored_fl26_players():
    records = grouped_roster()
    ids = list(records)
    default = balanced_roster_order(ids, ROLES, records)
    assert default == balanced_roster_order(ids, ROLES, records, {102: 99})
    complete = {pid: 60 for pid in ids}
    complete[102] = 90
    assert ids[balanced_roster_order(ids, ROLES, records, complete)[0]] == 102


def test_every_phase_is_validated_by_encoded_slot_and_missing_phases_fail():
    records = grouped_roster()
    ids = list(records)
    first = [ids[i] for i in balanced_roster_order(ids, ROLES, records)[:11]]
    tactics, shape = formations()
    assert len(validate_formation_phases(tactics, shape, 100, first, records)) == 6
    broken = bytearray(shape)
    struct.pack_into("<I", broken, 4, 1)  # Second tactic, phase 2, CF slot -> CB.
    with pytest.raises(ValueError, match="unfamiliar"):
        validate_formation_phases(tactics, bytes(broken), 100, first, records)
    with pytest.raises(ValueError, match="incomplete"):
        validate_formation_phases(tactics, shape[12:], 100, first, records)


@pytest.mark.parametrize("outgoing", [False, True])
def test_explicit_retained_repair_reorders_all_slots_not_just_departed_starters(outgoing):
    records = grouped_roster()
    ids = list(records)
    tactics, shape = formations()
    assignment = b"".join(struct.pack("<IIII", i + 1, pid, 100, (i << 8) | (i + 1))
                           for i, pid in enumerate(ids))
    tables = {"Tactics.bin": tactics, "TacticsFormation.bin": shape, "PlayerAssignment.bin": assignment}
    members = [{"native_player_id": pid, "shirt_number": i + 1, "key": f"ef:{pid}"}
               for i, pid in enumerate(ids)]
    plan = {"updated_team_ids": [], "local_outgoing": [{"team_id": 100}] if outgoing else [],
            "final_rosters": {"100": members}}
    catalog = {"teams": [{"team_id": 100, "physical_team_id": 100, "category": "german_teams"}]}
    untouched = copy.deepcopy(plan)
    rosters, shapes = stage.arrange_rosters(plan, catalog, {}, records, tables, {}, {100})
    changed = stage.patch_assignments_and_shapes(tables, catalog, rosters, shapes, set(), set(), {100})
    assert changed["TacticsFormation.bin"] == shape
    native = stage.parse_pes21_assignments(changed["PlayerAssignment.bin"])[100]
    assert [r.player_id for r in native] == [r["native_player_id"] for r in rosters[100]]
    assert {r.player_id: r.shirt for r in native} == {r["native_player_id"]: r["shirt_number"] for r in members}
    assert len(validate_formation_phases(tactics, shape, 100, [r.player_id for r in native[:11]], records)) == 6
    assert plan == untouched


def test_web_starting_eleven_is_preserved_in_explicit_repair_scope():
    records = grouped_roster()
    ids = list(records)
    order = balanced_roster_order(ids, ROLES, records)
    ordered = [ids[i] for i in order]
    # Prefer another valid keeper from the bench, deliberately not the solver's choice.
    alternate = next(i for i, pid in enumerate(ordered) if pid == 102)
    ordered[0], ordered[alternate] = ordered[alternate], ordered[0]
    tactics, shape = formations()
    tables = {"Tactics.bin": tactics, "TacticsFormation.bin": shape,
              "PlayerAssignment.bin": b"".join(struct.pack("<IIII", i + 1, pid, 100, i << 8)
                                              for i, pid in enumerate(ids))}
    plan = {"updated_team_ids": [100], "local_outgoing": [], "final_rosters": {"100": [
        {"native_player_id": pid, "base_id": pid, "shirt_number": i + 1} for i, pid in enumerate(ordered)]}}
    web = {"teams": {"100": {"strategies": [{"strategy": 0, "slots": [
        {"role": role, "depth": 20, "width": 50, "preferred_base_id": ordered[i]}
        for i, role in enumerate(ROLES)]}]}}}
    catalog = {"teams": [{"team_id": 100, "physical_team_id": 100}]}
    rosters, _ = stage.arrange_rosters(plan, catalog, web, records, tables, {}, {100})
    assert [r["native_player_id"] for r in rosters[100]] == ordered


def test_repair_scope_is_explicit_and_unknown_categories_fail():
    catalog = {"teams": [{"team_id": 1, "category": "german_teams"},
                         {"team_id": 2, "category": "english_teams"}]}
    assert stage.lineup_repair_scope(catalog, []) == set()
    assert stage.lineup_repair_scope(catalog, ["german_teams"]) == {1}
    with pytest.raises(ValueError, match="unknown"):
        stage.lineup_repair_scope(catalog, ["typo"])
