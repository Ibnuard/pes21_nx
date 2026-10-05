#!/usr/bin/env python3
"""Stage a supplied team crest in a paired local NRO/LooseCpk candidate.

Only the selected badge cell and native crest aliases are changed. Missing
real/fake variants must be added: switching to licensed kits selects ``_r``.
The supplied image and all proprietary CPK output stay under local-debug.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

from add_cpk_members_canary import rebuild as add_cpk_members
from build_barca_real_madrid_mobile_kit_canary import validate_cpk
from build_fl26_cup_catalog import index_cpk
from build_madrid_preserve_order import restore_order
from build_full_mobile_kit_migration import (
    ATLAS_WIDTH,
    BADGE_CELL,
    fit_badge,
    replace_badge_cell,
    write_badge_header,
)
from cleanse_playable_categories import render_curated_include
from prepare_loose_cpk import clone_full, verify as verify_loose, update


ROOT = Path(__file__).resolve().parents[1]
FLAG_PREFIX = "common/render/symbol/flag/"


def native_png(image: Image.Image, size: int) -> bytes:
    resized = image.resize((size, size), Image.Resampling.LANCZOS)
    stream = io.BytesIO()
    resized.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def native_crest_plan(index: dict, physical: int) -> dict[str, int]:
    """Complete both licensing paths, retaining existing emblemLc aliases."""
    if not 0 < physical <= 999999:
        raise ValueError("invalid native team ID")
    result = {}
    for suffix, size in (("", 128), ("_l", 256), ("_s", 64)):
        for form in ("f", "r"):
            result[f"{FLAG_PREFIX}e_{physical:06d}_{form}{suffix}.png"] = size
            for contrast in ("b", "w"):
                member = f"{FLAG_PREFIX}e_{physical:06d}_{form}_{contrast}{suffix}.png"
                if member in index:
                    result[member] = size
        for form in ("b", "w"):
            member = f"common/render/symbol/emblemLc/emb_{physical:04d}_{form}{suffix}.png"
            if member in index:
                result[member] = size
    if not set(result) & set(index):
        raise ValueError(f"no existing native crest identity for team {physical}")
    return result


def pack_native_crests(source: Path, payloads: dict[str, bytes], output: Path):
    """Replace/add approved crests without reordering existing CPK entries."""
    output.mkdir(parents=True, exist_ok=False)
    index, _ = index_cpk(source)
    paths = {}
    for number, (member, payload) in enumerate(sorted(payloads.items())):
        path = output / f"crest-{number:03d}.png"
        path.write_bytes(payload)
        paths[member] = path.resolve()
    replacements = {name: str(path) for name, path in paths.items() if name in index}
    additions = {name: path for name, path in paths.items() if name not in index}
    replaced = output / "replaced.cpk"
    manifest = output / "replacements.json"
    manifest.write_text(json.dumps(replacements, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools/repack_cpk_members.py"),
                    str(source), str(replaced), "--replace-manifest", str(manifest)],
                   check=True, stdout=subprocess.DEVNULL)
    final = output / "dt240_mobile_all.cpk"
    if additions:
        intermediate = output / "added.cpk"
        add_cpk_members(replaced, intermediate, additions)
        restore_order(intermediate, final, [*index, *sorted(additions)])
        intermediate.unlink()  # Only this tool's disposable intermediate.
    else:
        shutil.copyfile(replaced, final)
    replaced.unlink()
    actions = {name: "replace" if name in index else "add" for name in payloads}
    report = validate_cpk(source, final, actions, payloads)
    report["added_members"] = sorted(additions)
    return final, report


def team(catalog: dict, team_id: int) -> dict:
    matches = [row for row in catalog["teams"]
               if int(row["team_id"]) == team_id]
    if len(matches) != 1:
        raise ValueError(f"expected one selector entry for team {team_id}")
    return matches[0]


def stage(image_path: Path, candidate: Path, selector: Path,
          curated: Path, output: Path, team_id: int) -> dict:
    image_path = image_path.resolve()
    candidate = candidate.resolve()
    selector = selector.resolve()
    curated = curated.resolve()
    output = output.resolve()
    if ROOT / "local-debug" not in output.parents or output.exists():
        raise ValueError("output must be a new directory inside local-debug")
    source_manifest = verify_loose(candidate)
    if source_manifest["version"] != 2:
        raise ValueError("a full loose CPK candidate is required")
    full_catalog = json.loads((selector / "exhibition_team_catalog_migration.json")
                              .read_text(encoding="utf-8"))
    curated_catalog = json.loads((curated / "exhibition_team_catalog_migration.json")
                                 .read_text(encoding="utf-8"))
    full_team = team(full_catalog, team_id)
    curated_team = team(curated_catalog, team_id)
    for key in ("physical_team_id", "badge_slot"):
        if full_team[key] != curated_team[key]:
            raise ValueError(f"curated team {team_id} remaps {key}")
    physical = int(full_team["physical_team_id"])
    slot = int(full_team["badge_slot"])
    with Image.open(image_path) as source:
        if source.format != "PNG" or min(source.size) < 128:
            raise ValueError("crest must be a PNG of at least 128x128")
        image = source.convert("RGBA")
    if image.width != image.height:
        raise ValueError("crest must be square")
    if all(image.getpixel(point)[3] != 0 for point in
           ((0, 0), (image.width - 1, 0), (0, image.height - 1),
            (image.width - 1, image.height - 1))):
        raise ValueError("crest must have a transparent outer background")
    logo = image_path.read_bytes()
    old_id = source_manifest["build_id"]
    build_id = hashlib.sha256(old_id.encode("ascii") +
                              team_id.to_bytes(4, "little") + logo).hexdigest()[:16]

    native_source = candidate / "LooseCpk/dt240_mobile_all.cpk"
    native_index, _ = index_cpk(native_source)
    members = native_crest_plan(native_index, physical)

    output.mkdir(parents=True)
    shutil.copy2(image_path, output / "supplied-crest.png")
    clone_full(candidate, output, build_id)
    payloads = {member: native_png(image, size) for member, size in members.items()}
    native_output, native_report = pack_native_crests(
        native_source, payloads, output / "native-crests")
    update(output, "dt240_mobile_all.cpk", native_output)
    native_output.unlink()

    full_output = output / "selector"
    full_output.mkdir()
    for name in ("exhibition_team_catalog_migration.json",
                 "league_scorer_pool_generated.inc",
                 "league-scorer-pool-report.json"):
        shutil.copy2(selector / name, full_output / name)
    raw_atlas = (selector / "badge_atlas.bin").read_bytes()
    if len(raw_atlas) % (ATLAS_WIDTH * BADGE_CELL * 4):
        raise ValueError("source badge atlas has a partial row")
    atlas = Image.frombytes("RGBA", (ATLAS_WIDTH,
        len(raw_atlas) // (ATLAS_WIDTH * 4)), raw_atlas)
    replace_badge_cell(atlas, slot, fit_badge(logo))
    (full_output / "badge_atlas.bin").write_bytes(atlas.tobytes())
    header_catalog = dict(full_catalog, content_id=build_id)
    write_badge_header(full_output / "badge_atlas.h", header_catalog, atlas)
    roster = (selector / "exhibition_rosters_migration_canary_generated.inc").read_text(
        encoding="utf-8")
    if roster.count(old_id) != 2:
        raise ValueError("roster include has an unexpected paired build ID")
    (full_output / "exhibition_rosters_migration_canary_generated.inc").write_text(
        roster.replace(old_id, build_id), encoding="utf-8")

    curated_output = output / "curated"
    curated_output.mkdir()
    for name in ("exhibition_team_catalog_migration.json",
                 "fl26_cup_catalog_generated.h", "fl26_league_catalog_generated.h",
                 "fl26_league_catalog.json"):
        shutil.copy2(curated / name, curated_output / name)
    (curated_output / "exhibition_teams_migration_generated.inc").write_text(
        render_curated_include(curated_catalog, build_id), encoding="utf-8")
    result = {
        "status": "paired_crest_staged_hardware_pending",
        "team_id": team_id, "physical_team_id": physical,
        "badge_slot": slot, "native_members": sorted(members),
        "native_cpk": native_report,
        "base_build_id": old_id, "build_id": build_id,
        "image_sha256": hashlib.sha256(logo).hexdigest(),
        "loose_build_id": verify_loose(output)["build_id"],
    }
    (output / "crest-stage-report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--team-id", type=int, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--selector", type=Path, required=True)
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.image, args.candidate, args.selector,
                           args.curated, args.output, args.team_id),
                     sort_keys=True))


if __name__ == "__main__":
    main()
