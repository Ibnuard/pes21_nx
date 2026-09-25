"""Host regression for the generated FL26 Cup selector and team pools."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_public_manifest_has_unique_playable_pools():
    catalog = json.loads((ROOT / "data/exhibition_team_catalog.json").read_text())
    cups = json.loads((ROOT / "data/fl26_cup_catalog.json").read_text())["cups"]
    assert [cup["competition_id"] for cup in cups] == [15, 17, 16, 35, 33, 27, 0]
    assert [cup["name"] for cup in cups] == [
        "FA CUP", "COPA DEL REY", "COPPA ITALIA", "AFC CUP",
        "UEFA EURO", "WORLD CUP", "FOOTBALLNX CUP"]
    categories = {row["key"]: set(row["team_ids"])
                  for row in catalog["categories"]}
    teams_by_id = {team["team_id"]: team for team in catalog["teams"]}
    playable = set(teams_by_id)
    assert len({cup["competition_id"] for cup in cups}) == len(cups)
    assert set(cups[0]["team_ids"]) & categories["english_second"]
    assert [cup["bracket_limit"] for cup in cups] == [
        32, 32, 24, 16, 16, 32, 32]
    assert len(cups[5]["team_ids"]) >= 32
    assert cups[6]["team_ids"] == [] and cups[6]["logo_file"] is None
    for cup in cups[:-1]:
        teams = cup["team_ids"]
        assert 2 <= len(teams) <= 512
        assert len(teams) == len(set(teams))
        assert set(teams) <= playable
        if cup["competition_id"] in {15, 17, 16}:
            assert cup["category_key"] in categories
            assert cup["logo_file"].startswith(
                f'emb_{cup["competition_id"]:04d}')
        else:
            assert all(teams_by_id[team]["kind"] == "national" for team in teams)
            assert cup["logo_file"] in {
                "cup-afc.png", "cup-euro.png", "cup-world.png"}


def test_frontend_can_open_and_seed_every_fl26_cup():
    compiler = shutil.which("gcc")
    if not compiler:
        pytest.skip("Host C compiler unavailable")
    with tempfile.TemporaryDirectory() as temp:
        binary = Path(temp) / "fl26-cup-catalog-test.exe"
        subprocess.run([
            compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-I", str(ROOT / "source"),
            str(ROOT / "tests/test_fl26_cup_catalog.c"),
            str(ROOT / "source/competition_frontend.c"),
            str(ROOT / "source/league_tournament.c"),
            str(ROOT / "source/league_save.c"),
            str(ROOT / "source/competition_entry_draft.c"),
            str(ROOT / "source/cup_tournament.c"),
            str(ROOT / "source/cup_save.c"),
            "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], cwd=temp, check=True)
