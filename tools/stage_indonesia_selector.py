#!/usr/bin/env python3
"""Stage an Indonesia-for-Israel selector candidate in ignored local-debug.

This deliberately does not patch the native Team.bin, roster, tactics or kits;
the staged files must not be promoted alone as a playable release.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from PIL import Image

from audit_fl26_bundesliga_indonesia import INDONESIA_ID, ISRAEL_ID, inspect
from build_fl26_cup_catalog import decoded_member, index_cpk
from build_full_mobile_kit_migration import (
    ATLAS_WIDTH,
    fit_badge,
    replace_badge_cell,
    write_badge_header,
)
from generate_exhibition_team_catalog import render_team_include
from pes21_player_migration import content_id


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "local-debug/indonesia-selector-candidate"


def stage_catalog(catalog: dict) -> dict:
    """Replace one logical national team, preserving compact atlas slots."""
    staged = copy.deepcopy(catalog)
    rows = [row for row in staged["teams"] if int(row["team_id"]) == ISRAEL_ID]
    if len(rows) != 1 or any(int(row["team_id"]) == INDONESIA_ID
                             for row in staged["teams"]):
        raise ValueError("expected one Israel team and no Indonesia team")
    original = rows[0]
    if (original["category"] != "national_europe"
            or int(original["physical_team_id"]) != ISRAEL_ID):
        raise ValueError("Israel slot/category differ from verified baseline")
    categories = {row["key"]: row for row in staged["categories"]}
    europe = categories["national_europe"]["team_ids"]
    asia = categories["national_asia_oceania"]["team_ids"]
    if europe.count(ISRAEL_ID) != 1 or INDONESIA_ID in asia:
        raise ValueError("national category membership differs from baseline")
    europe.remove(ISRAEL_ID)
    asia.append(INDONESIA_ID)

    replacement = dict(original)
    replacement.update({
        "team_id": INDONESIA_ID,
        "physical_team_id": ISRAEL_ID,
        "symbol": "team_5750_indonesia",
        "display_name": "INDONESIA",
        "source_name": "Indonesia",
        "name_source": "fl26_ef26_verified",
        "category": "national_asia_oceania",
        "category_index": next(index for index, row in enumerate(staged["categories"])
                               if row["key"] == "national_asia_oceania"),
        "category_position": len(asia) - 1,
        "badge_source": "flag/e_005750_r_l.png",
        "badge_source_root": "local_fl26",
        "roster_source": "ef26_migration_pending",
        "conversion_eligible": False,
        "ef10_player_count": 0,
        "pes21_player_count": 0,
        "pesdb_player_count": 26,
        "has_ef10_tactics": False,
        "has_pes21_tactics": False,
    })
    staged["teams"] = sorted(
        [row for row in staged["teams"] if int(row["team_id"]) != ISRAEL_ID]
        + [replacement],
        key=lambda row: int(row["team_id"]),
    )
    for row in staged["teams"]:
        if row["category"] in ("national_europe", "national_asia_oceania"):
            row["category_position"] = categories[row["category"]]["team_ids"].index(
                int(row["team_id"])
            )
    staged["generated_by"] = "tools/stage_indonesia_selector.py"
    staged.pop("content_id", None)
    staged["content_id"] = content_id(staged)
    return staged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--catalog", type=Path,
                        default=ROOT / "data/exhibition_team_catalog.json")
    parser.add_argument("--registry", type=Path,
                        default=ROOT / "data/pes21_player_registry.json")
    parser.add_argument("--ef-source", type=Path,
                        default=ROOT / "local-inputs/pes21-player-migration/eF26_v551/source-db.json")
    parser.add_argument("--atlas", type=Path, default=ROOT / "data/badge_atlas.bin")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    local_debug = (ROOT / "local-debug").resolve()
    if local_debug not in output.parents or output.exists():
        raise ValueError("output must be a new directory inside local-debug")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    source = json.loads(args.ef_source.read_text(encoding="utf-8"))
    preflight = inspect(args.fl26_root, catalog, registry, source)
    indonesia = preflight["indonesia"]
    if (indonesia["ef26_assignment_count"] < 18
            or indonesia["fl26_roster_count"] < 18
            or not indonesia["crest_present"]
            or not indonesia["required_kits_present"]):
        raise ValueError("Indonesia source roster, crest, or kits incomplete")

    staged = stage_catalog(catalog)
    symbol_path = args.fl26_root / "Data/dt15_x64.cpk"
    index, base = index_cpk(symbol_path)
    crest = decoded_member(
        symbol_path, index, base,
        "common/render/symbol/flag/e_005750_r_l.png",
    )
    raw = args.atlas.read_bytes()
    if len(raw) % (ATLAS_WIDTH * 4):
        raise ValueError("badge atlas RGBA shape invalid")
    atlas = Image.frombytes("RGBA", (ATLAS_WIDTH, len(raw) // (ATLAS_WIDTH * 4)), raw)
    slot = next(int(row["badge_slot"]) for row in staged["teams"]
                if int(row["team_id"]) == INDONESIA_ID)
    replace_badge_cell(atlas, slot, fit_badge(crest))

    output.mkdir(parents=True)
    (output / "exhibition_team_catalog.json").write_text(
        json.dumps(staged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output / "exhibition_teams_generated.inc").write_text(
        render_team_include(staged), encoding="utf-8"
    )
    (output / "badge_atlas.bin").write_bytes(atlas.tobytes())
    write_badge_header(output / "badge_atlas.h", staged, atlas)
    report = {
        "schema_version": 1,
        "status": "selector_staged_not_playable",
        "logical_team_id": INDONESIA_ID,
        "physical_team_id": ISRAEL_ID,
        "badge_slot": slot,
        "catalog_content_id": staged["content_id"],
        "ef26_assignment_count": indonesia["ef26_assignment_count"],
        "pending": ["native roster", "Team.bin identity", "tactics", "kits",
                    "native crest", "paired hardware validation"],
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), **report}, sort_keys=True))


if __name__ == "__main__":
    main()
