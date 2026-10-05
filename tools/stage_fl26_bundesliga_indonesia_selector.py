#!/usr/bin/env python3
"""Stage the FL26 Bundesliga/Indonesia selector in ignored local-debug only.

This is deliberately not a playable package: native team/player tables, kits,
portraits and the matching NRO still need to be built and validated together.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image

from audit_fl26_bundesliga_indonesia import INDONESIA_ID, ISRAEL_ID
from build_fl26_cup_catalog import decoded_member, index_cpk
from build_full_mobile_kit_migration import (
    ATLAS_WIDTH,
    BADGE_CELL,
    brand_selector,
    fit_badge,
    replace_badge_cell,
    write_badge_header,
)
from generate_exhibition_team_catalog import render_team_include
from pes21_player_migration import content_id
from pesdb import parse_team_records
from stage_indonesia_selector import stage_catalog as replace_israel


ROOT = Path(__file__).resolve().parents[1]


def stage_catalog(base: dict, identity_plan: dict, slot_plan: dict,
                  team_names: dict[int, str], atlas_cells: int) -> dict:
    staged = replace_israel(base)
    bundesliga = [int(value) for value in identity_plan["bundesliga_team_ids"]]
    slots = {int(row["logical_team_id"]): int(row["physical_team_id"])
             for row in slot_plan["team_slots"]}
    if len(bundesliga) != 18 or set(slots) != set(bundesliga):
        raise ValueError("Bundesliga source and native slot plans differ")
    category = next(row for row in staged["categories"]
                    if row["key"] == "german_teams")
    category_index = staged["categories"].index(category)
    by_id = {int(row["team_id"]): row for row in staged["teams"]}
    existing_slots = {int(row["badge_slot"]) for row in staged["teams"]}
    existing_slots.update(int(row["badge_slot"]) for row in staged["categories"])
    free_slots = (slot for slot in range(atlas_cells)
                  if slot not in existing_slots)
    vetted_count = {
        team_id: sum(
            team_id in player["bundesliga_team_ids"]
            and player["status"] != "review_identity"
            and player["portrait_available"]
            for player in identity_plan["players"]
        )
        for team_id in bundesliga
    }
    if min(vetted_count.values()) < 18:
        raise ValueError("a Bundesliga club has fewer than 18 vetted players")

    for team_id in bundesliga:
        name = team_names[team_id]
        row = by_id.get(team_id)
        if row is None:
            row = dict(by_id[128])
            row["badge_slot"] = next(free_slots)
            staged["teams"].append(row)
            by_id[team_id] = row
        row.update({
            "team_id": team_id,
            "physical_team_id": slots[team_id],
            "symbol": f"team_{team_id}_{re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')}",
            "display_name": name.upper(),
            "source_name": name,
            "name_source": "fl26_local",
            "kind": "club",
            "category": "german_teams",
            "category_index": category_index,
            "badge_source": f"flag/e_{team_id:06d}_r_l.png",
            "badge_source_root": "local_fl26",
            "roster_source": "fl26_identity_staged",
            "conversion_eligible": False,
            "ef10_player_count": 0,
            "pes21_player_count": 0,
            "pesdb_player_count": vetted_count[team_id],
            "has_ef10_tactics": False,
            "has_pes21_tactics": False,
        })

    category["team_ids"] = bundesliga
    category["label"] = "BUNDESLIGA"
    for other in staged["categories"]:
        if other["key"] == "german_teams":
            continue
        other["team_ids"] = [value for value in other["team_ids"]
                             if value not in bundesliga]
    for row in staged["teams"]:
        group = next(item for item in staged["categories"]
                     if item["key"] == row["category"])
        row["category_position"] = group["team_ids"].index(int(row["team_id"]))
    staged["teams"].sort(key=lambda row: int(row["team_id"]))
    if len(by_id) != len(staged["teams"]) or ISRAEL_ID in by_id:
        raise RuntimeError("selector contains a duplicate team or Israel")
    if INDONESIA_ID not in by_id:
        raise RuntimeError("Indonesia is missing from selector")
    staged["counts"]["selector_teams"] = len(staged["teams"])
    staged["counts"]["excluded_teams"] = max(
        0,
        int(base["counts"]["excluded_teams"])
        - (len(staged["teams"]) - len(base["teams"])),
    )
    staged["generated_by"] = "tools/stage_fl26_bundesliga_indonesia_selector.py"
    staged.pop("content_id", None)
    staged["content_id"] = content_id(staged)
    return staged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--catalog", type=Path,
                        default=ROOT / "data/exhibition_team_catalog_migration.json")
    parser.add_argument("--identity-plan", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-identity-plan.json")
    parser.add_argument("--slot-plan", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--atlas", type=Path, default=ROOT / "data/badge_atlas.bin")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-selector")
    args = parser.parse_args()
    output = args.output.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents or output.exists():
        raise ValueError("output must be a new directory inside local-debug")
    source_path = args.fl26_root / "download/data_s2526c.cpk"
    source_index, source_base = index_cpk(source_path)
    source_teams = parse_team_records(decoded_member(
        source_path, source_index, source_base, "common/etc/pesdb/Team.bin"),
        "pes21",
    )
    symbols_path = args.fl26_root / "Data/dt15_x64.cpk"
    symbol_index, symbol_base = index_cpk(symbols_path)
    atlas_raw = args.atlas.read_bytes()
    if len(atlas_raw) % (ATLAS_WIDTH * BADGE_CELL * 4):
        raise ValueError("badge atlas has a partial 128px row")
    atlas = Image.frombytes("RGBA", (ATLAS_WIDTH,
                                     len(atlas_raw) // (ATLAS_WIDTH * 4)), atlas_raw)
    identity = json.loads(args.identity_plan.read_text(encoding="utf-8"))
    slots = json.loads(args.slot_plan.read_text(encoding="utf-8"))
    catalog = stage_catalog(
        json.loads(args.catalog.read_text(encoding="utf-8")), identity, slots,
        {team_id: team.name for team_id, team in source_teams.items()},
        atlas.width // BADGE_CELL * atlas.height // BADGE_CELL,
    )
    changed = set(int(value) for value in identity["bundesliga_team_ids"])
    changed.add(INDONESIA_ID)
    for row in catalog["teams"]:
        team_id = int(row["team_id"])
        if team_id not in changed:
            continue
        member = f"common/render/symbol/flag/e_{team_id:06d}_r_l.png"
        if member not in symbol_index:
            raise FileNotFoundError(f"FL26 crest missing: {member}")
        crest = decoded_member(symbols_path, symbol_index, symbol_base, member)
        replace_badge_cell(atlas, int(row["badge_slot"]), fit_badge(crest))
    branding = json.loads((ROOT / "data/full_mobile_kit_migration.json").read_text(
        encoding="utf-8"))["league_branding"]
    catalog, atlas, branded_categories = brand_selector(
        catalog, atlas, branding,
        lambda member: decoded_member(symbols_path, symbol_index, symbol_base, member),
    )
    output.mkdir(parents=True)
    (output / "exhibition_team_catalog_migration.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "exhibition_teams_migration_generated.inc").write_text(
        render_team_include(catalog), encoding="utf-8")
    (output / "badge_atlas.bin").write_bytes(atlas.tobytes())
    write_badge_header(output / "badge_atlas.h", catalog, atlas)
    report = {
        "schema_version": 1,
        "status": "selector_staged_not_playable",
        "bundesliga_teams": 18,
        "selector_teams": len(catalog["teams"]),
        "indonesia_replaces_israel": True,
        "catalog_content_id": catalog["content_id"],
        "fl26_branded_categories": [row["key"] for row in branded_categories],
        "pending": ["native tables", "club/national tactics", "kits", "native crests",
                    "FL26 portraits", "matching NRO", "hardware validation"],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                       encoding="utf-8")
    print(json.dumps({"output": str(output), **report}, sort_keys=True))


if __name__ == "__main__":
    main()
