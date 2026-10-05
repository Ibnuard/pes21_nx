"""Public-data checks for the staged national-team replacement."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_indonesia_selector import stage_catalog  # noqa: E402
from plan_fl26_player_identities import classify_player, curate_review  # noqa: E402
from plan_fl26_native_slots import choose_team_slots  # noqa: E402
from stage_fl26_bundesliga_indonesia_selector import (  # noqa: E402
    stage_catalog as stage_bundesliga_catalog,
)
from stage_fl26_paired_cpks import merge_team_overlay


def test_indonesia_stage_preserves_selector_and_badge_invariants() -> None:
    catalog = json.loads(
        (ROOT / "data/exhibition_team_catalog.json").read_text(encoding="utf-8")
    )
    original = next(row for row in catalog["teams"] if row["team_id"] == 1164)
    staged = stage_catalog(catalog)
    ids = [row["team_id"] for row in staged["teams"]]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids)) == len(catalog["teams"])
    assert 1164 not in ids
    assert ids.count(5750) == 1
    indonesia = next(row for row in staged["teams"] if row["team_id"] == 5750)
    assert indonesia["physical_team_id"] == 1164
    assert indonesia["badge_slot"] == original["badge_slot"]
    assert indonesia["category"] == "national_asia_oceania"
    assert len({row["badge_slot"] for row in staged["teams"]}) == len(ids)
    categories = {row["key"]: row for row in staged["categories"]}
    assert 5750 in categories["national_asia_oceania"]["team_ids"]
    assert 1164 not in categories["national_europe"]["team_ids"]
    assert any(row["team_id"] == 1164 for row in catalog["teams"])


def test_indonesia_stage_rejects_unexpected_source_catalog() -> None:
    catalog = json.loads(
        (ROOT / "data/exhibition_team_catalog.json").read_text(encoding="utf-8")
    )
    catalog["teams"] = [row for row in catalog["teams"] if row["team_id"] != 1164]
    with pytest.raises(ValueError, match="one Israel"):
        stage_catalog(catalog)


def test_bundesliga_player_reuses_verified_national_identity() -> None:
    pc = {"player_id": 100, "name": "Example Player", "country": 20,
          "height": 180, "foot": 0}
    active = {"base_id": 100, "name": "Example Player", "country": 10,
              "height": 181, "foot": 0, "native_player_id": 540100,
              "team_ids": [5750]}
    result = classify_player(pc, {100: active}, {"exampleplayer": [active]})
    assert result["status"] == "reuse_ef_base_id"
    assert result["base_id"] == 100
    assert result["native_player_id"] == 540100


def test_bundesliga_numeric_id_collision_never_reuses_donor() -> None:
    pc = {"player_id": 100, "name": "Different Person", "country": 20,
          "height": 180, "foot": 0}
    occupied = {"base_id": 100, "name": "Existing Player", "country": 10,
                "height": 180, "foot": 0, "native_player_id": 100,
                "team_ids": [1]}
    result = classify_player(pc, {100: occupied}, {})
    assert result == {
        "status": "review_identity",
        "candidate_base_ids": [100],
        "reason": "ambiguous_or_fingerprint_mismatch",
    }


def test_bundesliga_new_player_uses_separate_source_namespace() -> None:
    pc = {"player_id": 90000, "name": "New Player", "country": 420,
          "height": 190, "foot": 1}
    result = classify_player(pc, {}, {})
    assert result["status"] == "new_fl26_identity"
    assert result["source_key"] == "fl26:90000"
    assert len(result["fingerprint"]) == 20


def test_curated_numeric_collision_gets_new_native_identity() -> None:
    pc = {"player_id": 116646, "name": "Rani Khedira", "country": 420,
          "height": 188, "foot": 0, "age": 30, "position": 4}
    incumbent = {"base_id": 116646, "name": "Fredegar Baumeister",
                 "country": 92, "height": 188, "foot": 0, "age": 31,
                 "position": 4, "native_player_id": 116646, "team_ids": []}
    decision = classify_player(pc, {116646: incumbent}, {})
    curated = curate_review(pc, decision, {116646: incumbent})
    assert curated["status"] == "new_fl26_identity"
    assert curated["source_key"] == "fl26:116646"
    assert "native_player_id" not in curated


def test_curated_verified_name_preserves_base_identity() -> None:
    pc = {"player_id": 129369, "name": "Michael Olise", "country": 416,
          "height": 176, "foot": 1, "age": 24, "position": 10}
    incumbent = {"base_id": 129369, "name": "Michael Olise",
                 "country": 208, "height": 184, "foot": 1, "age": 24,
                 "position": 10, "native_player_id": 129369,
                 "team_ids": [15, 127]}
    decision = classify_player(pc, {129369: incumbent},
                               {"michaelolise": [incumbent]})
    curated = curate_review(pc, decision, {129369: incumbent})
    assert curated["status"] == "reuse_ef_base_id"
    assert curated["base_id"] == 129369
    assert curated["native_player_id"] == 129369


def test_bundesliga_team_donors_exclude_active_or_competition_slots() -> None:
    bundesliga = [126, 127, 128, *range(5000, 5015)]
    rows = {127, 128, 175, *range(4000, 4017)}
    result = choose_team_slots(bundesliga, rows, {4000}, {4001})
    assert len(result) == 18
    assert result[126] == 175
    assert result[127] == 127
    assert result[128] == 128
    assert set(result.values()).isdisjoint({4000, 4001})
    assert len(set(result.values())) == 18


def test_bundesliga_indonesia_stage_has_unique_teams_and_badges() -> None:
    catalog = json.loads(
        (ROOT / "data/exhibition_team_catalog_migration.json").read_text(
            encoding="utf-8")
    )
    bundesliga = [126, 127, 128, *range(5000, 5015)]
    identity = {
        "bundesliga_team_ids": bundesliga,
        "players": [
            {"bundesliga_team_ids": [team_id], "status": "new_fl26_identity",
             "portrait_available": True}
            for team_id in bundesliga for _ in range(23)
        ],
    }
    slot_plan = {"team_slots": [
        {"logical_team_id": team_id, "physical_team_id": physical_id}
        for team_id, physical_id in zip(
            bundesliga, [175, 127, 128, *range(4000, 4015)], strict=True)
    ]}
    staged = stage_bundesliga_catalog(
        catalog, identity, slot_plan,
        {team_id: f"Club {team_id}" for team_id in bundesliga}, 544,
    )
    ids = [row["team_id"] for row in staged["teams"]]
    badges = [row["badge_slot"] for row in staged["teams"]]
    expected = (({row["team_id"] for row in catalog["teams"]} - {1164}) |
                {5750, *bundesliga})
    assert len(ids) == len(set(ids)) == len(expected)
    assert set(ids) == expected
    assert len(badges) == len(set(badges))
    assert 5750 in ids and 1164 not in ids
    german = next(row for row in staged["categories"]
                  if row["key"] == "german_teams")
    assert german["label"] == "BUNDESLIGA"
    assert german["team_ids"] == bundesliga
    assert not any(row["key"] == "other_europe"
                   for row in staged["categories"])


def team_record(team_id, flag, name):
    raw = bytearray(1532)
    struct.pack_into("<I", raw, 8, team_id)
    raw[84] = flag
    raw[100:100 + len(name)] = name
    return bytes(raw)


def test_pairing_preserves_palmeiras_kit_flag_and_all_unrelated_team_bytes():
    # A stale native stage has an unlicensed Palmeiras row. Only the explicit
    # Bundesliga/Indonesia slots should replace the already licensed kit base.
    licensed = team_record(137, 15, b"PALMEIRAS")
    base = licensed + team_record(1164, 4, b"OLD NATION")
    indonesia = team_record(1164, 15, b"INDONESIA")
    staged = team_record(137, 0, b"STALE NAME") + indonesia
    merged = merge_team_overlay(base, staged, {1164})
    assert merged == licensed + indonesia
    assert merge_team_overlay(merged, staged, {1164}) == merged


def test_pairing_rejects_duplicate_missing_or_unexpected_team_ids():
    a, b = team_record(137, 15, b"A"), team_record(1164, 15, b"B")
    with pytest.raises(ValueError, match="duplicate"):
        merge_team_overlay(a + b, b + b, {1164})
    with pytest.raises(ValueError, match="ID set"):
        merge_team_overlay(a + b, a, {1164})
    with pytest.raises(ValueError, match="ID set"):
        merge_team_overlay(a + b, a + b, {99999})
