"""Repair the admitted Cup cut's file-list hole in a detached current runtime.

Native GetFileName treats the first empty slot as the end of the list. Only
the reviewed v86 list is admitted; other cinematic members remain exact.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

from build_trophy_test_package import marker_bytes
from compose_loose_cpk import compose_manifest
from entrance_scene_canary import Cpk, digest, output_directory
from fixdemo_scene_table import parse_scene_table, serialize_scene_table
from prepare_loose_cpk import digest as file_digest, read_manifest, write_manifest
from stage_trophy_ceremony import (CORE_FILES, CUT_ID, CUT_NAME, SCENE_ID,
                                  SCENE_NAME, TABLE, check_composition_members,
                                  raw_member)

ROOT = Path(__file__).resolve().parents[1]
V86_CPK_SHA256 = "72db80088df2a1648b6c9be3576a35ee6a14e707cb8304c3c289592fe654fd27"
PROP_PAK_SHA256 = "17673134cdf4c1c155fc11e271d9bdb69e525b1108d6ba14f618a9c7d67e1b5a"
PAK = "PesMobile/Content/Paks/PesMobile-CinematicProps-Android_ETC1_P.pak"


def repair_table(table: dict) -> dict:
    """Idempotent semantic repair; never infer a different scene/variant."""
    if (table["kind"] != 7 or table["version"] != 1 or table["file_count"] != 10 or
            table["condition_count"] != 10 or
            parse_scene_table(serialize_scene_table(table), 7) != table):
        raise ValueError("compatible ending-table roundtrip required")
    cuts = [r for r in table["cuts"] if r["id"] == CUT_ID]
    scenes = [r for r in table["scenes"] if r["id"] == SCENE_ID]
    if (len(cuts) != 1 or len(scenes) != 1 or cuts[0]["name"] != CUT_NAME or
            scenes[0]["name"] != SCENE_NAME or len(cuts[0]["variants"]) != 1):
        raise ValueError("reviewed Cup scene/cut identity required")
    variant = cuts[0]["variants"][0]
    rows = scenes[0]["cuts"]
    if (len(rows) != 2 or rows[0]["cut_id"] != CUT_ID or rows[1]["cut_id"] != 0 or
            rows[0]["human_changes"] != [[1, 0, 0]] or
            rows[0]["signed_params"] != [6, 0, 180, 0] or
            variant["conditions"] != [256] + [0] * 9 or
            variant["flags"] != 0x7FF or variant["human_mask"] != 3 or
            variant["move_distance"] != 0):
        raise ValueError("reviewed captain, timing and variant layout required")
    old = list(CORE_FILES[:3]) + ["", CORE_FILES[3]] + [""] * 5
    fixed = list(CORE_FILES) + [""] * 6
    if variant["files"] not in (old, fixed):
        raise ValueError("unreviewed file list; refuse generic compaction")
    result = copy.deepcopy(table)
    next(r for r in result["cuts"] if r["id"] == CUT_ID)["variants"][0]["files"] = fixed
    if parse_scene_table(serialize_scene_table(result), 7) != result:
        raise ValueError("repaired table did not roundtrip")
    return result


def stage(current: Path, output: Path) -> dict:
    output = output_directory(output)
    current = current.resolve()
    baseline = read_manifest(current)
    base = current / "LooseCpk/dt220_mobile_all.cpk"
    if baseline["version"] != 2 or file_digest(base) != V86_CPK_SHA256:
        raise ValueError("the admitted current v86 cinematic CPK is required")
    row = next(r for r in baseline["files"] if r["name"] == base.name)
    if row["sha256"] != V86_CPK_SHA256 or row["size"] != base.stat().st_size:
        raise ValueError("current manifest/cinematic pairing differs")
    pak_sha = file_digest(current / PAK)
    if (pak_sha != PROP_PAK_SHA256 or (current / "trophy-canary.txt").read_bytes() !=
            marker_bytes(V86_CPK_SHA256, file_digest(current / "LooseCpk/manifest.txt"), pak_sha)):
        raise ValueError("current marker/prop pairing differs")
    old = Cpk(base)
    raw = old.read(TABLE)
    if raw != raw_member(old, TABLE):
        raise ValueError("a new stored-table envelope requires a separate audit")
    table = parse_scene_table(raw, 7)
    repaired = repair_table(table)
    encoded = serialize_scene_table(repaired)
    if encoded == raw:
        raise ValueError("v86 repair unexpectedly made no change")
    output.mkdir(parents=True)
    payload = output / "table-end.local.bin"
    payload.write_bytes(encoded)
    update = output / "update"
    (update / "LooseCpk").mkdir(parents=True)
    candidate = update / "LooseCpk" / base.name
    replacements = output / "replace.local.json"
    replacements.write_text(json.dumps({TABLE: str(payload.resolve())}) + "\n")
    subprocess.run([sys.executable, str(ROOT / "tools/repack_cpk_members.py"),
                    str(base), str(candidate), "--expect-members", str(len(old.index)),
                    "--replace-manifest", str(replacements)], check=True, cwd=ROOT)
    new = Cpk(candidate)
    unchanged = check_composition_members(old, new, {TABLE: encoded}, TABLE)
    manifest = compose_manifest(current, {base.name: candidate})
    write_manifest(update, manifest)
    (update / "trophy-canary.txt").write_bytes(marker_bytes(
        file_digest(candidate), file_digest(update / "LooseCpk/manifest.txt"), pak_sha))
    before = next(r for r in table["cuts"] if r["id"] == CUT_ID)["variants"][0]["files"]
    after = next(r for r in repaired["cuts"] if r["id"] == CUT_ID)["variants"][0]["files"]
    report = dict(state="detached_cinematic_metadata_repaired", current=str(current),
                  baseline_cpk_sha256=V86_CPK_SHA256, cpk_sha256=file_digest(candidate),
                  cpk_bytes=candidate.stat().st_size, table_before_sha256=digest(raw),
                  table_after_sha256=digest(encoded), files_before=before, files_after=after,
                  changed_members=[TABLE], unchanged_stored_members=unchanged,
                  member_order_and_ids_preserved=True, update=str(update.resolve()),
                  manifest_sha256=file_digest(update / "LooseCpk/manifest.txt"),
                  marker_sha256=file_digest(update / "trophy-canary.txt"),
                  prop_pak_sha256=pak_sha, native_playback_verified=False)
    (output / "REPAIR-REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
    payload.unlink()
    replacements.unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.current, args.output), indent=2))


if __name__ == "__main__":
    main()
