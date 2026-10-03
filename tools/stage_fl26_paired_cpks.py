#!/usr/bin/env python3
"""Pair local FL26 tables, kits, crests and portraits into loose CPKs.

This is a disposable hardware candidate, not a release. It does not build the
matching NRO or sign off native gameplay; all outputs stay in local-debug.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

from add_cpk_members_canary import rebuild as add_cpk_members
from build_fl26_cup_catalog import decoded_member, index_cpk
from pes21_player_migration import repack_migration_cpks
from prepare_loose_cpk import clone_full, update, verify


ROOT = Path(__file__).resolve().parents[1]
FLAG_PREFIX = "common/render/symbol/flag/"


def resized_png(raw: bytes, width: int) -> bytes:
    with Image.open(io.BytesIO(raw)) as source:
        source.load()
        image = source.convert("RGBA")
        if image.size != (width, width):
            image = image.resize((width, width), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def stage_crests(fl26_root: Path, kit_dt240: Path, team_slots: list[dict],
                 output: Path) -> tuple[Path, dict]:
    source = fl26_root / "Data/dt15_x64.cpk"
    source_index, source_base = index_cpk(source)
    native_index, _ = index_cpk(kit_dt240)
    replacements: dict[str, str] = {}
    additions: dict[str, Path] = {}
    count = 0
    for row in [*team_slots,
                {"logical_team_id": 5750, "physical_team_id": 1164}]:
        logical = int(row["logical_team_id"])
        physical = int(row["physical_team_id"])
        large = f"{FLAG_PREFIX}e_{logical:06d}_r_l.png"
        regular = f"{FLAG_PREFIX}e_{logical:06d}_r.png"
        if large not in source_index or regular not in source_index:
            raise FileNotFoundError(f"FL26 crest variants missing for {logical}")
        source_large = decoded_member(source, source_index, source_base, large)
        source_regular = decoded_member(source, source_index, source_base, regular)
        for variant, size in (("", 128), ("_l", 256), ("_s", 64)):
            raw = source_large if size == 256 else source_regular
            payload = resized_png(raw, size)
            path = output / "crests" / f"{physical}_{size}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            for form in ("r", "f"):
                member = f"{FLAG_PREFIX}e_{physical:06d}_{form}{variant}.png"
                if form == "f" and member not in native_index:
                    continue
                if member in native_index:
                    replacements[member] = str(path.resolve())
                else:
                    additions[member] = path
            count += 1

    manifest = output / "crest-replacements.json"
    manifest.write_text(json.dumps(replacements, indent=2) + "\n",
                        encoding="utf-8")
    replaced = output / "dt240-crest-replaced.cpk"
    subprocess.run([
        sys.executable, str(ROOT / "tools/repack_cpk_members.py"),
        str(kit_dt240), str(replaced), "--replace-manifest", str(manifest),
    ], check=True, stdout=subprocess.DEVNULL)
    final = output / "dt240_mobile_all.cpk"
    if additions:
        add_cpk_members(replaced, final, additions)
    else:
        shutil.copyfile(replaced, final)
    return final, {"teams": len(team_slots) + 1, "sizes": count,
                   "replacements": len(replacements), "additions": len(additions)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path,
                        default=Path("D:/Games/SP Football Life 2026"))
    parser.add_argument("--native", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-native")
    parser.add_argument("--portraits", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-portraits")
    parser.add_argument("--kit", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-kit-candidate")
    parser.add_argument("--selector", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-selector")
    parser.add_argument("--slots", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-native-slot-plan.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "local-debug/fl26-bundesliga-indonesia-paired")
    args = parser.parse_args()
    output = args.output.resolve()
    args.native = args.native.resolve()
    args.portraits = args.portraits.resolve()
    args.kit = args.kit.resolve()
    args.selector = args.selector.resolve()
    args.slots = args.slots.resolve()
    args.fl26_root = args.fl26_root.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents or output.exists():
        raise ValueError("output must be a new directory inside local-debug")
    native_report = json.loads((args.native / "native-table-report.json").read_text(
        encoding="utf-8"))
    portrait_report = json.loads((args.portraits / "report.json").read_text(
        encoding="utf-8"))
    slots = json.loads(args.slots.read_text(encoding="utf-8"))
    selector = json.loads((args.selector / "exhibition_team_catalog_migration.json").read_text(
        encoding="utf-8"))
    if (native_report["status"] != "native_tables_staged_not_packaged"
            or portrait_report["count"] != native_report["players_imported"]
            or len(slots["team_slots"]) != 18
            or len(selector["teams"]) != 459):
        raise ValueError("candidate stage reports are inconsistent")
    output.mkdir(parents=True)
    dt200_base = args.kit / "LooseCpk/dt200_mobile_all.cpk"
    dt200_index, _ = index_cpk(dt200_base)
    table_files = {
        f"common/etc/pesdb/{path.name}": path
        for path in (args.native / "tables").iterdir()
        if path.is_file() and f"common/etc/pesdb/{path.name}" in dt200_index
    }
    required_tables = {"Team.bin", "Player.bin", "PlayerAssignment.bin",
                       "InstallVersionPlayer.bin", "PlayerDeleteList.bin",
                       "CompetitionEntry.bin", "TacticsFormation.bin"}
    if not required_tables.issubset({Path(key).name for key in table_files}):
        raise ValueError("required mobile PESDB tables are absent from dt200")
    portraits = [{"native_player_id": int(row["native_player_id"])}
                 for row in portrait_report["portraits"]]
    dt200, dt241, packed = repack_migration_cpks(
        table_files=table_files, portrait_rows=portraits,
        portrait_dir=args.portraits,
        base_dt200=dt200_base,
        base_dt241=args.kit / "LooseCpk/dt241_mobile_all.cpk",
        output=output,
    )
    dt240, crests = stage_crests(
        args.fl26_root, args.kit / "LooseCpk/dt240_mobile_all.cpk",
        slots["team_slots"], output,
    )
    clone_full(args.kit, output, selector["content_id"])
    for name, path in (("dt200_mobile_all.cpk", dt200),
                       ("dt241_mobile_all.cpk", dt241),
                       ("dt240_mobile_all.cpk", dt240)):
        update(output, name, path)
    loose = verify(output)
    report = {
        "schema_version": 1,
        "status": "paired_cpks_nro_and_hardware_pending",
        "selector_content_id": selector["content_id"],
        "bundesliga_teams": 18,
        "indonesia_replaces_israel": True,
        "players_imported": native_report["players_imported"],
        "portraits": portrait_report["count"],
        "kits": 19,
        "cpk": packed,
        "auxiliary_tables_not_present_in_dt200": sorted(
            path.name for path in (args.native / "tables").iterdir()
            if path.is_file() and f"common/etc/pesdb/{path.name}" not in dt200_index
        ),
        "crests": crests,
        "loose_build_id": loose["build_id"],
        "pending": ["matching selector NRO", "native tactics review",
                    "paired hardware match and gameplan test"],
    }
    (output / "paired-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "status": report["status"],
                      "players": report["players_imported"],
                      "portraits": report["portraits"],
                      "crests": crests}, sort_keys=True))


if __name__ == "__main__":
    main()
