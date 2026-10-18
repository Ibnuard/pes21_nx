#!/usr/bin/env python3
"""Build an isolated, experimental FL26 walkout update from owned local data.

This is a deliberately reduced scene: two cameras, 22 players, three referees.
PC audience/extra actors/effects are excluded. Native Skip, timing callbacks
and kickoff remain engine-owned. Static validation is not hardware sign-off.
Only dt220 and its manifest are emitted; never duplicate a whole runtime/OBB.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct
import tempfile

from entrance_scene_canary import (Cpk, FDC_PREFIX, asset_name, cut_report,
                                  digest, gani_header, output_directory,
                                  payload, table_entries)
from fixdemo_scene_table import parse_scene_table, serialize_scene_table
from prepare_loose_cpk import digest as file_digest, verify, write_manifest
from build_barca_real_madrid_mobile_kit_canary import package_cpk, validate_cpk
from build_madrid_preserve_order import restore_order

ROOT = Path(__file__).resolve().parents[1]
TABLE = FDC_PREFIX + "ent/table_ent.bin"
MOTION_PREFIX = "common/demo/anime/FoxAnim/FixDemo/Animations/"
CORE_FILES = (
    "ent_012_st000_cmn_cam1.fdc",
    "ent_012_st000_cmn_cam2.fdc",
    "ent_012_st000_cmn_pl.fdc",
)


def build_walkout_table(native: dict, donor: dict) -> dict:
    """Author one explicit canary, not a general-purpose PC scene transplant."""
    if native["kind"] != 1 or donor["kind"] != 1:
        raise ValueError("entrance tables required; ending IDs must never be remapped here")
    if (len(native["scenes"]) != 1 or len(native["cuts"]) != 1 or
            native["scenes"][0]["id"] != 0x10001 or native.get("controls") or
            native.get("has_controls") or native["file_count"] != 10 or
            native["condition_count"] != 10):
        raise ValueError("unsupported Mobile entrance table")
    terminal = native["scenes"][0]["cuts"][-1]
    if terminal["cut_id"] != 0:
        raise ValueError("native terminal cut is required")
    cuts = [cut for cut in donor["cuts"] if cut["name"] == "ENT_012_CMN"]
    if len(cuts) != 1 or not cuts[0]["variants"]:
        raise ValueError("expected unique donor walkout cut")
    cut = cuts[0]
    variant = copy.deepcopy(cut["variants"][0])
    if (variant["files"][:3] != list(CORE_FILES) or variant["flags"] != 0x1ffffff or
            variant["human_mask"] != 3 or variant["move_distance"] != 0):
        raise ValueError("donor actor/camera layout changed")
    scene = next((s for s in donor["scenes"] if s["name"] == "ENT_ANTH0_CMN"), None)
    rows = [r for r in scene["cuts"] if r["cut_id"] == cut["id"]] if scene else []
    if len(rows) != 1:
        raise ValueError("donor walkout sequence descriptor is unavailable")
    row = copy.deepcopy(rows[0])
    if (row["signed_params"] != [0, 0, 0, 0] or row["tail_value"] != -1 or
            row["human_changes"] != [[3, 1, 0], [1, 0, 0], [4, 12, 0], [2, 11, 0]]):
        raise ValueError("donor timing/assignment descriptor changed")
    result = copy.deepcopy(native)
    # The Mobile selector always chooses scene0x10001. Its generic condition is
    # kept deliberately; this canary must first be tested in the Konami stadium.
    variant["conditions"] = copy.deepcopy(native["cuts"][0]["variants"][0]["conditions"])
    if variant["conditions"] != [256] + [0] * 9:
        raise ValueError("unsupported native generic stadium condition")
    variant["files"] = list(CORE_FILES) + [""] * 7
    result["cuts"] = [{"id": 0x10001, "name": "NX_WALKOUT_CANARY_V1", "variants": [variant]}]
    row["cut_id"] = 0x10001
    result["scenes"] = [{"id": 0x10001, "name": "NX_WALKOUT_CANARY_V1",
                         "cuts": [row, copy.deepcopy(terminal)]}]
    # Enforce native binary bounds and cross-field shape before staging assets.
    encoded = serialize_scene_table(result)
    if parse_scene_table(encoded, 1) != result:
        raise ValueError("canary table failed semantic roundtrip")
    return result


def validate_walkout_actors(data: bytes) -> None:
    outer = table_entries(data, named=True)
    records_data = payload(data, outer[0])
    records = table_entries(records_data, named=False)
    if {r.kind for r in records} != {2, 4}:
        raise ValueError("unreviewed actor record type")
    actors = []
    controllers = []
    for record in records:
        if record.size != (364 if record.kind == 4 else 92):
            raise ValueError("actor record does not match the measured Mobile layout")
        word = struct.unpack_from("<I", records_data, record.offset)[0]
        if record.kind == 4:
            if word >> 16 != 1:
                raise ValueError("unreviewed actor assignment bank")
            actors.append(word & 0xffff)
        else:
            controllers.append(word & 0xffff)
    if sorted(actors) != list(range(25)) or sorted(controllers) != [23, 24]:
        raise ValueError("walkout must use exactly 22 field players and three native referees")


def validate_motion_path(name: str) -> str:
    name = asset_name(name)
    if (not name.startswith(MOTION_PREFIX + "dml_ent_") or
            "/" in name[len(MOTION_PREFIX):] or not name.endswith(".gani")):
        raise ValueError(f"unreviewed external asset class: {name}")
    return name


def collect_payloads(source: Cpk, mobile: list[Cpk]) -> tuple[dict[str, bytes], list[dict]]:
    payloads: dict[str, bytes] = {}
    reports = []
    for filename in CORE_FILES:
        name = FDC_PREFIX + "ent/cut_data/" + filename
        report = cut_report(source, name, mobile)
        if report["self_name"] != name:
            raise ValueError("donor cut self-name differs from its virtual path")
        raw = source.read(name)
        if filename.endswith("_pl.fdc"):
            validate_walkout_actors(raw)
        payloads[name] = raw
        reports.append(report)
        for dependency in report["dependencies"]:
            resolution = dependency["resolution"]
            if resolution == "embedded":
                continue
            dep_name = asset_name(dependency["name"])
            # Do not let a PC scene silently inherit an unrelated Mobile motion.
            if resolution == "mobile":
                if dep_name not in source.index or digest(source.read(dep_name)) != dependency["sha256"]:
                    raise ValueError(f"Mobile/donor shared motion differs: {dep_name}")
                continue
            if resolution != "donor_only" or dependency.get("format_error"):
                raise ValueError(f"unresolved/unsupported dependency: {dep_name} ({resolution})")
            validate_motion_path(dep_name)
            motion = source.read(dep_name)
            gani_header(motion)
            if digest(motion) != dependency["sha256"]:
                raise ValueError("donor changed during dependency audit")
            if dep_name in payloads and payloads[dep_name] != motion:
                raise ValueError("conflicting dependency payload")
            payloads[dep_name] = motion
    return payloads, reports


def stage(fl26_root: Path, mobile_root: Path, output: Path) -> dict:
    output = output_directory(output)
    mobile_root = mobile_root.resolve()
    manifest = verify(mobile_root)
    if manifest["version"] != 2:
        raise ValueError("a validated full LooseCpk V2 baseline is required")
    source = Cpk(fl26_root / "Data/dt12_g4.cpk")
    mobile = [Cpk(mobile_root / "LooseCpk" / name) for name in
              ("dt220_mobile_all.cpk", "dt230_mobile_all.cpk")]
    native_table = parse_scene_table(mobile[0].read(TABLE), 1)
    donor_table = parse_scene_table(source.read(TABLE), 1)
    table = build_walkout_table(native_table, donor_table)
    payloads, cut_reports = collect_payloads(source, mobile)
    payloads[TABLE] = serialize_scene_table(table)
    # An unexpected pre-existing donor asset is a different baseline. Refuse
    # to overwrite it, even if replacing it might appear to work.
    if set(payloads) & set(mobile[0].index) != {TABLE}:
        raise ValueError("baseline already contains one or more walkout assets")
    actions = {name: "replace" if name == TABLE else "add" for name in payloads}
    output.mkdir(parents=True)
    update_root = output / "update"
    loose = update_root / "LooseCpk"
    loose.mkdir(parents=True)
    base = mobile[0].path
    final = loose / base.name
    # Disposable own temporary files only; no full runtime/OBB is cloned.
    with tempfile.TemporaryDirectory(prefix="work-", dir=output) as temporary:
        work = Path(temporary)
        paths = {}
        for index, (name, raw) in enumerate(payloads.items()):
            path = work / f"asset-{index}.bin"
            path.write_bytes(raw)
            paths[name] = str(path.resolve())
        packed = package_cpk(ROOT, work, "walkout", base, actions, payloads, paths)
        order = list(mobile[0].index) + sorted(set(payloads) - set(mobile[0].index))
        restore_order(Path(packed["candidate"]), final, order)
    validation = validate_cpk(base, final, actions, payloads)
    final_cpk = Cpk(final)
    if list(final_cpk.index) != order:
        raise ValueError("original CPK row order changed")
    for name, old in mobile[0].index.items():
        if final_cpk.index[name]["ID"] != old["ID"]:
            raise ValueError("original CPK member ID changed")
    updated_manifest = copy.deepcopy(manifest)
    for entry in updated_manifest["files"]:
        if entry["name"] == base.name:
            entry.update(size=final.stat().st_size, sha256=file_digest(final))
    write_manifest(update_root, updated_manifest)
    (update_root / "cinematic-trace.txt").write_bytes(b"PESNX_CINEMATIC_TRACE_V1\n")
    report = {
        "schema": "PESNX_ENTRANCE_WALKOUT_CANARY_V1",
        "status": "experimental_hardware_candidate", "runtime_verified": False,
        "active_runtime_modified": False, "save_format_changed": False,
        "baseline_root": str(mobile_root), "baseline_build_id": manifest["build_id"],
        "baseline_dt220_sha256": file_digest(base),
        "baseline_manifest_sha256": file_digest(mobile_root / "LooseCpk/manifest.txt"),
        "source_table_sha256": digest(source.read(TABLE)),
        "native_table_sha256": digest(mobile[0].read(TABLE)),
        "scene_id": 0x10001, "table_sha256": digest(payloads[TABLE]),
        "scope": "one generic walkout, two cameras,22players,three referees; no PC mobs/audience",
        "donor_payload_bytes": sum(len(raw) for name, raw in payloads.items() if name != TABLE),
        "payloads": [{"name": name, "bytes": len(raw), "sha256": digest(raw)}
                     for name, raw in payloads.items()],
        "validation": validation, "cut_reports": cut_reports,
        "remaining_checks": [
            "Native animation/skeleton playback, positions and camera framing on Switch.",
            "Full playback and Skip both reach kickoff and restore thread FPS.",
            "High/Low; home/away; two consecutive matches without retained actors or slowdown.",
            "Crowd, additional stadium geometry and trophy lifting are not included.",
        ],
    }
    (output / "walkout-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "INSTALL.txt").write_text(
        "EXPERIMENTAL ENTRANCE WALKOUT - NOT A PRODUCTION RELEASE\n\n"
        "Use only over the exact LooseCpk baseline hashes in walkout-report.json.\n"
        "Back up the installed LooseCpk/dt220_mobile_all.cpk and manifest.txt.\n"
        "Copy update/ over that runtime;23other CPKs, PAK and OBB are unchanged.\n"
        "The matching NRO with the opt-in trace records cinematic-trace.log.\n"
        "Begin with Konami stadium. Test natural completion, then Skip, then a second match.\n"
        "Rollback: restore BOTH backed-up files and remove cinematic-trace.txt.\n"
        "No save or live runtime was changed by preparation. Trophy scene is NOT enabled.\n",
        encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path, required=True)
    parser.add_argument("--mobile-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = stage(args.fl26_root, args.mobile_root, args.output)
    print(json.dumps({"output": str(args.output), "status": report["status"],
                      "assets": len(report["payloads"]),
                      "runtime_verified": False}))


if __name__ == "__main__":
    main()
