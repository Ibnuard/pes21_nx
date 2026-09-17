from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_full_mobile_kit_migration import (  # noqa: E402
    BADGE_CELL,
    ATLAS_WIDTH,
    audit_teams,
    fit_badge,
    replace_badge_cell,
)


def test_full_kit_config_targets_migration_catalog_and_safe_fallback() -> None:
    config = json.loads(
        (ROOT / "data/full_mobile_kit_migration.json").read_text(encoding="utf-8")
    )
    assert config["team_catalog"] == "data/exhibition_team_catalog_migration.json"
    assert config["policy"]["source_team_key"] == "team_id"
    assert config["policy"]["target_team_key"] == "physical_team_id"
    assert config["policy"]["missing_source_team"] == "preserve_existing_mobile_team"
    assert config["policy"]["required_kits"] == ["1st", "2nd", "GK1st"]


def test_league_branding_has_unique_members_and_official_english_name() -> None:
    config = json.loads(
        (ROOT / "data/full_mobile_kit_migration.json").read_text(encoding="utf-8")
    )
    branding = config["league_branding"]
    assert branding["english_league"]["label"] == "PREMIER LEAGUE"
    assert branding["english_second"]["label"] == "EFL CHAMPIONSHIP"
    assert branding["spanish_league"]["label"] == "LALIGA EA SPORTS"
    assert branding["serie_a"]["label"] == "SERIE A ENILIVE"
    members = [row["member"] for row in branding.values()]
    assert len(members) == len(set(members))


def test_league_badge_replaces_entire_old_atlas_cell() -> None:
    atlas = Image.new("RGBA", (ATLAS_WIDTH, BADGE_CELL), (255, 0, 0, 255))
    source = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(8, 24):
        for y in range(8, 24):
            source.putpixel((x, y), (0, 255, 0, 255))
    buffer = io.BytesIO()
    source.save(buffer, format="PNG")

    replace_badge_cell(atlas, 0, fit_badge(buffer.getvalue()))

    # Transparent margins must reveal the selector background, never the
    # legacy red badge that occupied the slot before migration.
    assert atlas.getpixel((0, 0)) == (0, 0, 0, 0)
    assert atlas.getpixel((BADGE_CELL // 2, BADGE_CELL // 2))[1] > 0


def test_audit_uses_logical_source_but_keeps_physical_target() -> None:
    catalog = {
        "teams": [
            {
                "team_id": 5738,
                "physical_team_id": 2473,
                "display_name": "INTER MIAMI CF",
                "category": "north_america_clubs",
            },
            {
                "team_id": 9999,
                "physical_team_id": 12,
                "display_name": "NO SOURCE",
                "category": "other_europe",
            },
        ]
    }
    rows = {}
    for kind in ("1st", "2nd", "GK1st"):
        name = (
            "common/character0/model/character/uniform/team/"
            f"5738/5738_DEF_{kind}_realUni.bin"
        )
        descriptor = bytearray(120)
        for offset, value in ((40, "test_body"), (56, "test_back"),
                              (88, "test_leg"), (104, "test_name")):
            descriptor[offset:offset + 16] = value.encode("ascii").ljust(16, b"\0")
        rows[name.lower()] = {
            "name": name,
            "payload": bytes(descriptor),
            "row": {"FileSize": 120, "ExtractSize": 120, "FileOffset": 0},
        }
    for ref in ("test_body", "test_back"):
        name = f"Asset/model/character/uniform/texture/#windx11/{ref}.ftex"
        rows[name.lower()] = {"name": name, "payload": b"texture"}
    # Keep the unit fixture independent of real CPK files.
    def fake_winner(indexes, member):
        return rows[member.lower()]["payload"], {"archive": "fixture"}

    import build_full_mobile_kit_migration as module
    original = module.winning_member
    module.winning_member = fake_winner
    try:
        migrated, preserved = audit_teams(catalog, [{"rows": rows}])
    finally:
        module.winning_member = original
    assert [(row["team_id"], row["physical_team_id"]) for row in migrated] == [
        (5738, 2473)
    ]
    assert preserved[0]["team_id"] == 9999
    assert preserved[0]["reason"] == "missing_or_partial_football_life_kit_set"
