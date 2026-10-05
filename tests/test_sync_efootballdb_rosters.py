from __future__ import annotations

import copy
import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sync_efootballdb_rosters as sync
import efootballdb_reconcile as reconcile
from pesdb import PlayerAssignment
from pes21_player_migration import normalize_name


def catalog():
    return {
        "content_id": "test",
        "categories": [{"key": "test_league", "team_ids": [100]}],
        "teams": [{"team_id": 100, "physical_team_id": 4000,
                   "display_name": "TEST CLUB", "kind": "club",
                   "category": "test_league"}],
    }


def payload():
    return {"data": {
        "pes_id": 100, "is_national_team": 0, "english_name": "Test Club",
        "player_assignments": [{
            "order_number": slot, "shirt_number": slot + 1, "captain": int(slot == 0),
            "player": {"pes_id": 1000 + slot, "base_pes_id": 1000 + slot,
                       "player_name": f"Test Player {slot}",
                       "nationality_a": {"pes_id": 55, "country_id": 10}, "height": 180,
                       "age": 25, "strong_foot": 0,
                       "main_position": 0 if slot == 0 else 1},
        } for slot in range(18)],
        "tactics": [{"strategy_type": 0, "formations": [
            {"formation_index": 0, "sort_index": slot,
             "position_role": 0 if slot == 0 else 1, "x_coord": 3 + slot,
             "y_coord": 52} for slot in range(11)]}],
    }}


def test_scope_is_curated_selector_not_master_or_physical_ids():
    scope = sync.playable_teams(catalog())
    assert list(scope) == [100]
    assert scope[100]["physical_team_id"] == 4000
    retired = catalog()
    retired["categories"].append({"key": "j2_league", "team_ids": []})
    with pytest.raises(ValueError, match="retired"):
        sync.playable_teams(retired)


def test_scope_rejects_duplicate_native_slots_and_missing_category_members():
    broken = catalog()
    broken["teams"].append(dict(broken["teams"][0], team_id=101))
    broken["categories"][0]["team_ids"].append(101)
    with pytest.raises(ValueError, match="native team slot"):
        sync.playable_teams(broken)
    broken = catalog()
    broken["categories"][0]["team_ids"].append(101)
    with pytest.raises(ValueError, match="one-to-one"):
        sync.playable_teams(broken)


def test_normalization_preserves_base_identity_and_exact_lineup():
    raw = payload()
    raw["data"]["player_assignments"][0]["player"]["pes_id"] = 990001
    team = sync.normalize_team(raw, catalog()["teams"][0])
    assert not team["problems"]
    assert team["members"][0]["base_id"] == 1000
    assert team["members"][0]["card_id"] == 990001
    assert team["members"][0]["country"] == 10
    assert team["strategies"][0]["slots"][0]["preferred_base_id"] == 1000
    assert team["physical_team_id"] == 4000


def test_missing_or_duplicate_roster_is_not_interpreted_as_a_transfer():
    raw = payload()
    raw["data"]["player_assignments"] = []
    team = sync.normalize_team(raw, catalog()["teams"][0])
    assert "roster_count:0" in team["problems"]
    raw = payload()
    raw["data"]["player_assignments"][-1] = copy.deepcopy(raw["data"]["player_assignments"][0])
    team = sync.normalize_team(raw, catalog()["teams"][0])
    assert "duplicate_base_id" in team["problems"]
    assert "non_contiguous_assignment_order" in team["problems"]


def test_wrong_team_or_kind_is_rejected():
    raw = payload()
    raw["data"]["pes_id"] = 101
    with pytest.raises(ValueError, match="another team"):
        sync.normalize_team(raw, catalog()["teams"][0])
    raw = payload()
    raw["data"]["is_national_team"] = 1
    with pytest.raises(ValueError, match="kind"):
        sync.normalize_team(raw, catalog()["teams"][0])


def write_collection(folder, complete=True):
    (folder / "raw").mkdir()
    catalog_raw = sync.json_bytes(catalog())
    (folder / "catalog.json").write_bytes(catalog_raw)
    raw = sync.json_bytes(payload())
    (folder / "raw/100.json.gz").write_bytes(gzip.compress(raw))
    sync.write_json(folder / "collection.json", {
        "generator": sync.GENERATOR, "catalog_sha256": sync.digest(catalog_raw),
        "requested_team_ids": [100], "errors": {},
        "teams": {"100": {"sha256": sync.digest(raw)}} if complete else {},
    })


def test_all_teams_must_be_collected_before_plan(tmp_path):
    write_collection(tmp_path, complete=False)
    with pytest.raises(ValueError, match="ALL playable teams"):
        sync.load_collection(tmp_path)


def test_raw_response_and_scope_are_hash_locked(tmp_path):
    write_collection(tmp_path)
    assert len(sync.load_collection(tmp_path)[2]) == 1
    (tmp_path / "raw/100.json.gz").write_bytes(gzip.compress(b"{}"))
    with pytest.raises(ValueError, match="checksum"):
        sync.load_collection(tmp_path)


def test_collection_cannot_be_written_to_public_or_active_runtime():
    with pytest.raises(ValueError, match="local-inputs"):
        sync.local_output(sync.ROOT / "data/team-update")
    with pytest.raises(ValueError, match="local-inputs"):
        sync.local_output(sync.ROOT / "dist/pes21_nx")


def local_identity(key="ef:1000"):
    return {"key": key, "base_id": 1000 if key.startswith("ef:") else None,
            "native_player_id": 50001, "name": "Test Player 0", "country": 10,
            "height": 180, "foot": 0, "fingerprint": "locked",
            "aliases": ["testplayer0"], "status": "active"}


def observation(**changes):
    row = sync.normalize_team(payload(), catalog()["teams"][0])["members"][0]
    return dict(row, **changes)


def test_transfer_reuses_native_identity_and_asset_ownership():
    local = local_identity()
    result = reconcile.resolve_identity(1000, [observation()], {local["key"]: local}, {})
    assert result["status"] == "reuse_local"
    assert result["native_player_id"] == 50001
    assert result["fingerprint"] == "locked"
    assert result["stats_policy"] == "preserve_local"


def test_reused_number_with_changed_identity_is_held_not_reallocated():
    local = local_identity()
    result = reconcile.resolve_identity(1000, [observation(name="Someone Else")],
                                        {local["key"]: local}, {})
    assert result["status"] == "review_identity"
    assert result["reason"] == "base_id_fingerprint_mismatch"


def test_present_tombstone_stays_reserved_until_explicit_identity_review():
    local = dict(local_identity(), status="removed", native_present=True)
    result = reconcile.resolve_identity(1000, [observation()], {local["key"]: local}, {})
    assert result["status"] == "review_identity"
    assert result["reason"] == "tombstone_requires_identity_review"
    # Presence is insufficient, but matching BOTH native and web fingerprints
    # can reactivate a removed national-team member now in a valid club roster.
    local["native_identity_verified"] = True
    assert reconcile.resolve_identity(1000, [observation()], {local["key"]: local}, {})["status"] == "reuse_local"


def test_staged_identity_state_reuses_native_ids_and_fl26_aliases():
    person = dict(local_identity(), native_sha256="native-hash", previous_keys=["fl26:77"])
    state = {"schema_version": 1, "identities": {person["key"]: person}}
    native = {50001: {"native_sha256": "native-hash"}}
    identities, owners = reconcile.load_identity_state(state, native, {1000: (50001, "old")})
    assert owners == {50001: "ef:1000"}
    assert identities["ef:1000"]["previous_keys"] == ["fl26:77"]
    result = reconcile.resolve_identity(1000, [observation()], identities, {})
    assert result["status"] == "reuse_local" and result["native_player_id"] == 50001
    assert "native_present" not in person  # Loading does not mutate the frozen state.


@pytest.mark.parametrize("corruption", ["hash", "missing", "native_owner", "base", "alias", "legacy"])
def test_staged_identity_state_rejects_identity_or_asset_corruption(corruption):
    person = dict(local_identity(), native_sha256="native-hash", previous_keys=["fl26:77"])
    state = {"schema_version": 1, "identities": {person["key"]: person}}
    native = {50001: {"native_sha256": "native-hash"}, 50002: {"native_sha256": "other-hash"}}
    legacy = {1000: (50001, "old")}
    if corruption == "hash":
        native[50001]["native_sha256"] = "other-person"
    elif corruption == "missing":
        del native[50001]
    elif corruption == "base":
        person["base_id"] = 999
    elif corruption == "legacy":
        legacy[1000] = (50002, "old")
    else:
        second = dict(person, key="ef:1001", base_id=1001)
        if corruption == "alias":
            second.update(native_player_id=50002, native_sha256="other-hash")
        state["identities"][second["key"]] = second
    with pytest.raises(ValueError):
        reconcile.load_identity_state(state, native, legacy)


def test_fl26_person_can_gain_ef_base_id_without_duplicate_native_player():
    local = local_identity("fl26:77")
    result = reconcile.resolve_identity(1000, [observation()],
                                        {local["key"]: local}, {"testplayer0": [local]})
    assert result["status"] == "promote_fl26_identity"
    assert result["key"] == "ef:1000" and result["previous_key"] == "fl26:77"
    assert result["native_player_id"] == 50001


def test_same_name_with_another_base_id_is_not_silently_duplicated():
    local = local_identity("ef:999")
    result = reconcile.resolve_identity(1000, [observation()],
                                        {local["key"]: local}, {"testplayer0": [local]})
    assert result["status"] == "review_identity"


def test_new_player_uses_explicit_no_donor_policy():
    result = reconcile.resolve_identity(1000, [observation()], {}, {})
    assert result["status"] == "new_web_player"
    assert result["native_player_id"] is None
    assert result["asset_policy"] == "neutral_portrait_no_face_no_commentary"


def test_inconsistent_new_base_variants_are_held():
    result = reconcile.resolve_identity(1000, [observation(), observation(country=11)], {}, {})
    assert result["status"] == "review_identity"


def test_complete_given_family_name_reversal_is_not_a_new_identity():
    local = dict(local_identity(), name="Akira Example", aliases=["akiraexample"])
    row = observation(name="Example Akira")
    result = reconcile.resolve_identity(1000, [row], {local["key"]: local}, {})
    assert result["status"] == "reuse_local"
    assert not reconcile.fingerprint_fields_match(local, observation(name="A. Example"))
    assert not reconcile.fingerprint_fields_match(local, observation(name="Example Akira", foot=1))


def test_known_unmaterialized_base_is_not_blocked_by_unrelated_namesake():
    local = dict(local_identity("ef:999"), height=160)
    known = dict(local_identity(), native_player_id=None)
    result = reconcile.resolve_identity(1000, [observation()], {local["key"]: local},
                                        {"testplayer0": [local]}, {1000: known})
    assert result["status"] == "new_web_player"
    assert result["verification"] == "web_and_locked_unmaterialized_base"


def league_fixture():
    scope = {"categories": [{"key": "test_league", "team_ids": [100, 101, 102]}],
             "teams": []}
    identities, owners, assignments, web = {}, {}, {}, {}
    for index, team_id in enumerate((100, 101, 102)):
        team = dict(catalog()["teams"][0], team_id=team_id,
                    physical_team_id=4000 + index, kind="national" if index == 2 else "club")
        scope["teams"].append(team)
        data = payload()
        data["data"].update(pes_id=team_id, is_national_team=int(index == 2))
        for slot, row in enumerate(data["data"]["player_assignments"]):
            base_id = 1000 + index * 100 + slot
            if index == 2 and slot == 0:
                base_id = 1000
            row["player"].update(pes_id=base_id, base_pes_id=base_id,
                                 player_name=f"Player Number {base_id}")
        web[team_id] = sync.normalize_team(data, team)
        assignments[4000 + index] = []
        for member in web[team_id]["members"]:
            base_id, native_id = member["base_id"], member["base_id"] + 50000
            key = f"ef:{base_id}"
            identities[key] = dict(member, key=key, native_player_id=native_id,
                                   aliases=[normalize_name(member["name"])], fingerprint="verified",
                                   status="active", native_present=True)
            owners[native_id] = key
            assignments[4000 + index].append(PlayerAssignment(
                native_id, 4000 + index, member["order"], member["shirt_number"]))
    return scope, identities, owners, assignments, web


def fixture_transfer(web):
    # Move a bench player to a different club; replacement is a new BaseId.
    incoming = dict(web[100]["members"][-1])
    web[100]["members"][-1].update(base_id=2000, card_id=2000, name="New Player")
    web[101]["members"][-1] = incoming


def test_full_reconcile_transfers_once_and_keeps_shared_national_identity():
    scope, identities, owners, assignments, web = league_fixture()
    fixture_transfer(web)
    report = reconcile.reconcile(scope, web, {}, identities, owners, assignments, True)
    assert report["status"] == "ready_to_stage"
    event = next(row for row in report["transfers"] if row["base_id"] == 1017)
    assert event["from_clubs"] == [100] and event["to_clubs"] == [101]
    shared = next(row for row in report["players"] if row["base_id"] == 1000)
    assert shared["team_ids"] == [100, 102] and shared["native_player_id"] == 51000
    # A departure is reported, not erased from the canonical identity registry.
    departed = next(row for row in report["transfers"] if row["base_id"] == 1117)
    assert departed["to_clubs"] == [] and "ef:1117" in identities


def test_missing_team_preserves_club_membership_seen_only_in_national_team():
    scope, identities, owners, assignments, web = league_fixture()
    del web[100]
    report = reconcile.reconcile(scope, web, {"100": "HTTP Error 404: Not Found"},
                                 identities, owners, assignments, True)
    assert report["status"] == "ready_to_stage"
    assert not report["transfers"]
    assert report["final_rosters"]["100"][0]["key"] == "ef:1000"


def test_retained_club_and_dependent_transfers_stay_exactly_unchanged():
    scope, identities, owners, assignments, web = league_fixture()
    fixture_transfer(web)
    del web[100]
    report = reconcile.reconcile(scope, web, {"100": "HTTP Error 404: Not Found"},
                                 identities, owners, assignments, True, keep_identity_teams=True)
    assert report["status"] == "ready_to_stage"
    assert report["updated_team_ids"] == [102]
    assert not report["transfers"]
    for team_id, physical in ((100, 4000), (101, 4001)):
        assert [row["native_player_id"] for row in report["final_rosters"][str(team_id)]] == [
            row.player_id for row in assignments[physical]]


def test_identity_review_defers_entire_team_not_one_guessed_replacement():
    scope, identities, owners, assignments, web = league_fixture()
    fixture_transfer(web)
    web[100]["members"][0]["name"] = "Different Person"
    report = reconcile.reconcile(scope, web, {}, identities, owners, assignments,
                                 True, keep_identity_teams=True)
    # The national roster independently confirms BaseId 1000; force every
    # observation to conflict so the example really is an unresolved identity.
    web[102]["members"][0]["name"] = "Different Person"
    report = reconcile.reconcile(scope, web, {}, identities, owners, assignments,
                                 True, keep_identity_teams=True)
    assert report["status"] == "ready_to_stage"
    assert report["updated_team_ids"] == []
    assert report["counts"]["blocked_identity_reviews"] == 0
    assert report["counts"]["identity_reviews"] == 1
    assert all(not row["apply"] for row in report["players"])


def test_timeouts_are_not_silently_treated_as_missing_rosters():
    scope, identities, owners, assignments, web = league_fixture()
    del web[100]
    report = reconcile.reconcile(scope, web, {"100": "timed out"}, identities,
                                 owners, assignments, True, keep_identity_teams=True)
    assert report["status"] == "blocked_identity_review"
    assert report["problems"][0]["reason"] == "source_unavailable"


def test_canonical_profile_resolves_unlicensed_alias_but_not_reused_identity():
    local = local_identity()
    result = reconcile.resolve_identity(1000, [observation(name="Fictional Card Label")],
                                         {local["key"]: local}, {}, profile=observation())
    assert result["status"] == "reuse_local"
    changed_profile = observation(name="Unrelated Current Person")
    assert reconcile.resolve_identity(1000, [observation()], {local["key"]: local}, {},
                                       profile=changed_profile)["status"] == "review_identity"


def test_canonical_club_only_removes_bench_duplicates_without_inventing_xi():
    _, _, _, _, web = league_fixture()
    duplicate = dict(web[100]["members"][-1], order=18)
    web[101]["members"].append(duplicate)
    changed, corrections = reconcile.effective_teams(web, {1017: {"club_id": 100}})
    assert len(changed[101]["members"]) == 18 and len(web[101]["members"]) == 19
    assert changed[101]["members"][:11] == web[101]["members"][:11]
    assert corrections[0]["canonical_club"] == 100
    web[101]["members"][0], web[101]["members"][-1] = duplicate, web[101]["members"][0]
    duplicate["order"] = 0
    changed, _ = reconcile.effective_teams(web, {1017: {"club_id": 100}})
    assert changed[101]["problems"] == ["canonical_club_conflict:1017"]


def test_known_unmaterialized_base_with_changed_fingerprint_is_held():
    result = reconcile.resolve_identity(1000, [observation(name="New Identity")], {}, {},
                                         {1000: observation()})
    assert result["status"] == "review_identity"
    assert result["reason"] == "unmaterialized_base_fingerprint_mismatch"


def test_one_canonical_biography_correction_keeps_verified_local_record():
    local = dict(local_identity(), name="Example Fullname", aliases=["examplefullname"],
                 age=25, position=5)
    profile = observation(name="Example Fullname", age=26, position=5, height=185)
    result = reconcile.resolve_identity(1000, [profile], {local["key"]: local}, {}, profile=profile)
    assert result["status"] == "reuse_local"
    assert result["biography_drift"]["field"] == "height"
    assert result["fingerprint"] == "locked" and result["stats_policy"] == "preserve_local"
    # No canonical profile, changed BaseId, multiple changed fields, initials,
    # impossible age or keeper/outfield identity changes must remain held.
    assert reconcile.canonical_biography_drift(local, None) is None
    for change in ({"base_id": 999}, {"foot": 1}, {"age": 15}, {"position": 0}, {"height": 200}):
        assert reconcile.canonical_biography_drift(local, dict(profile, **change)) is None
    assert reconcile.canonical_biography_drift(dict(local, name="E. Fullname"),
                                               dict(profile, name="E. Fullname")) is None


def test_approved_outgoing_does_not_empty_retained_club_or_duplicate_person():
    scope, identities, owners, assignments, web = league_fixture()
    fixture_transfer(web)
    del web[100]
    args = (scope, web, {"100": "HTTP Error 404: Not Found"}, identities, owners, assignments, True)
    # Original club has only 18: protect it, not a fabricated replacement.
    report = reconcile.reconcile(*args, keep_identity_teams=True, allow_retained_outgoing=True)
    assert report["updated_team_ids"] == [102]
    # With a spare verified player, the transfer can safely proceed.
    spare = dict(identities["ef:1016"], key="ef:1018", base_id=1018, native_player_id=51018)
    identities["ef:1018"] = spare
    owners[51018] = "ef:1018"
    assignments[4000].append(PlayerAssignment(51018, 4000, 18, 30))
    report = reconcile.reconcile(*args, keep_identity_teams=True, allow_retained_outgoing=True)
    assert report["updated_team_ids"] == [101, 102]
    assert report["local_outgoing"][0]["departing_keys"] == ["ef:1017"]
    assert len(report["final_rosters"]["100"]) == 18
    assert "ef:1017" not in [row["key"] for row in report["final_rosters"]["100"]]
