"""Public League preset and playable-selector integrity checks."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cleanse_playable_categories import RETIRED, cleanse_catalog  # noqa: E402


def test_clean_selector_and_league_pools():
    catalog = json.loads((ROOT / "data/exhibition_team_catalog_migration.json")
                         .read_text(encoding="utf-8"))
    leagues = json.loads((ROOT / "data/fl26_league_catalog.json")
                         .read_text(encoding="utf-8"))
    assert leagues["catalog_content_id"] == catalog["content_id"]
    assert not RETIRED.intersection(row["key"] for row in catalog["categories"])
    assert len(catalog["teams"]) == 378
    assert len(catalog["categories"]) == 27
    header = (ROOT / "source/exhibition_team_catalog.h").read_text()
    assert '#include "exhibition_teams_migration_generated.inc"' in header
    assert '#include "exhibition_teams_generated.inc"' not in header
    assert any(row["team_id"] == 126 and row["category"] == "german_teams"
               for row in catalog["teams"])
    by_key = {row["key"]: row for row in catalog["categories"]}
    entries = leagues["leagues"]
    assert entries[-1]["name"] == "FOOTBALLNX LEAGUE"
    assert entries[-1]["team_ids"] == []
    assert len({row["competition_id"] for row in entries}) == len(entries)
    assert not {22, 23, 128, 137, 69}.intersection(
        row["competition_id"] for row in entries)
    assert all(row["competition_id"] != 39 for row in entries), (
        "Bundesliga is staged locally but has only two clubs in public catalog")
    for row in entries[:-1]:
        teams = row["team_ids"]
        assert 8 <= len(teams) <= 32
        assert len(teams) == len(set(teams))
        assert set(teams) <= set(by_key[row["category_key"]]["team_ids"])
        assert row["logo_file"].startswith(f'emb_{row["competition_id"]:04d}')


def test_cleanse_is_idempotent_and_preserves_badge_slots():
    source = json.loads((ROOT / "data/exhibition_team_catalog_migration.json")
                        .read_text(encoding="utf-8"))
    cleaned = cleanse_catalog(source)
    assert cleaned == source
    assert {row["team_id"]: row["badge_slot"] for row in cleaned["teams"]} == {
        row["team_id"]: row["badge_slot"] for row in source["teams"]}
    base = json.loads((ROOT / "data/exhibition_team_catalog.json")
                      .read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="archived base"):
        cleanse_catalog(base)
