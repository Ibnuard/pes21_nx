#!/usr/bin/env python3
"""Remove retired selector leagues without deleting native PESDB records.

The badge slots are deliberately not renumbered: existing atlases and saved
native team IDs remain stable. Borussia Dortmund moves from the retired
OTHER EUROPE category to the German category when present.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from generate_exhibition_team_catalog import render_team_include
from pes21_player_migration import content_id


RETIRED = frozenset({
    "belgian_league", "swiss_league", "other_europe", "brazil_serie_b",
    "colombian_league", "j2_league",
})
DORTMUND_ID = 126


def cleanse_catalog(source: dict) -> dict:
    if "badge_slots" in source.get("counts", {}):
        raise ValueError("cleanse the migration catalog, not the archived base atlas catalog")
    catalog = json.loads(json.dumps(source))
    categories = [row for row in catalog["categories"]
                  if row["key"] not in RETIRED]
    by_key = {row["key"]: row for row in categories}
    german = by_key["german_teams"]
    dortmund = next((row for row in catalog["teams"]
                     if int(row["team_id"]) == DORTMUND_ID), None)
    if dortmund is not None and DORTMUND_ID not in german["team_ids"]:
        german["team_ids"].append(DORTMUND_ID)

    allowed = {int(team) for row in categories for team in row["team_ids"]}
    if len(allowed) != sum(len(row["team_ids"]) for row in categories):
        raise ValueError("duplicate team in surviving selector categories")
    teams = [row for row in catalog["teams"]
             if int(row["team_id"]) in allowed]
    if len(teams) != len(allowed):
        raise ValueError("surviving category has missing or duplicate team")
    positions = {
        int(team): (index, category["key"], position)
        for index, category in enumerate(categories)
        for position, team in enumerate(category["team_ids"])
    }
    for team in teams:
        index, key, position = positions[int(team["team_id"])]
        team["category"] = key
        team["category_index"] = index
        team["category_position"] = position
    catalog["categories"] = categories
    catalog["teams"] = teams
    catalog["counts"]["selector_teams"] = len(teams)
    catalog["counts"]["categories"] = len(categories)
    catalog.pop("content_id", None)
    catalog["content_id"] = content_id(catalog)
    return catalog


def render_curated_include(catalog: dict, paired_build_id: str | None = None) -> str:
    include = render_team_include(catalog)
    if paired_build_id:
        marker = f"// Catalog content ID: {catalog['content_id']}\n"
        if marker not in include:
            raise ValueError("generated selector include has no content ID")
        include = include.replace(
            marker, marker + f"// Paired loose CPK build ID: {paired_build_id}\n", 1)
    return include


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-output", type=Path, required=True)
    parser.add_argument("--paired-build-id",
                        help="ID of the original staged selector/LooseCpk; only for a curated local subset")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = json.loads(args.catalog.read_text(encoding="utf-8"))
    if args.paired_build_id and (
            not re.fullmatch(r"[0-9a-f]{16}", args.paired_build_id)
            or source.get("content_id") != args.paired_build_id):
        raise ValueError("paired build ID must equal the original selector content ID")
    result = cleanse_catalog(source)
    manifest = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    include = render_curated_include(result, args.paired_build_id)
    if args.check:
        if (args.output.read_text(encoding="utf-8") != manifest or
                args.include_output.read_text(encoding="utf-8") != include):
            raise SystemExit("playable-category outputs are out of date")
    else:
        args.output.write_text(manifest, encoding="utf-8")
        args.include_output.write_text(include, encoding="utf-8")
    print(json.dumps({"selector_teams": len(result["teams"]),
                      "categories": len(result["categories"]),
                      "content_id": result["content_id"]}))


if __name__ == "__main__":
    main()
