from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from pes21_master_data import sql_name, stat_dictionary  # noqa: E402


def test_sql_names_cover_ef_acronyms_without_colliding_with_base_id() -> None:
    assert sql_name("GKCatching") == "gk_catching"
    assert sql_name("OffensiveAwareness") == "offensive_awareness"
    assert sql_name("Country2") == "country2"
    fields = stat_dictionary([
        {"data": {"BaseId": 1, "Id": 1, "GK": 0, "GKCatching": 40}}
    ])
    assert ("BaseId", "base_id", "INTEGER") not in fields
    assert len({column for _source, column, _kind in fields}) == len(fields)


def test_committed_master_registry_matches_current_migration_identity() -> None:
    registry = json.loads(
        (ROOT / "data/pes21_player_registry.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (ROOT / "data/exhibition_team_catalog_migration.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (ROOT / "data/master/master-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["source_version"] == registry["source_version"]
    assert manifest["migration_build_id"] == registry["migration_build_id"]
    assert manifest["registry_content_id"] == registry["content_id"]
    assert manifest["catalog_content_id"] == catalog["content_id"]
    assert manifest["counts"]["active_players"] == len(registry["players"])
    assert manifest["counts"]["teams"] == len(catalog["teams"])


def test_master_schema_lists_query_surfaces() -> None:
    schema = json.loads(
        (ROOT / "data/master/master-schema.json").read_text(encoding="utf-8")
    )
    names = {row["name"] for row in schema["tables"]}
    assert {
        "players", "teams", "competitions", "team_rosters",
        "formation_slots", "starting_lineups", "player_assets",
        "team_kits", "kit_variants",
    } <= names
    assert "players.base_id -> team_rosters.base_id" in schema["relationships"]
