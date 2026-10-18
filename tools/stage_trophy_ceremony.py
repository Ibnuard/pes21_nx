#!/usr/bin/env python3
"""Stage a detached, asset-only Cup ceremony from legally owned local data.

No scene is enabled. The two prop model paths remain explicit renderer/cook
requirements; PC models are not copied or described as Mobile-compatible.
Only the validated dt220 candidate and its paired manifest leave temporary work.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile

from entrance_scene_canary import (
    Cpk, CHARACTER_PREFIX, FDC_PREFIX, RESOURCE_PATH, asset_name,
    dependency_audit, digest, gani_header, inspect_fdc, output_directory,
    payload, skeleton_audit, table_entries,
)
from fixdemo_scene_table import parse_scene_table, serialize_scene_table
from prepare_loose_cpk import digest as file_digest, verify, write_manifest
from build_barca_real_madrid_mobile_kit_canary import package_cpk, validate_cpk
from build_madrid_preserve_order import restore_order

ROOT = Path(__file__).resolve().parents[1]
TABLE = FDC_PREFIX + "end/table_end.bin"
ENTRANCE_TABLE = FDC_PREFIX + "ent/table_ent.bin"
SCENE_ID, CUT_ID, VARIANT_INDEX = 0x70007, 0x7002B, 1
SCENE_NAME, CUT_NAME = "END_CUP_CMN", "END_TROPHY_01_CUP"
MOTION_PREFIX = "common/demo/anime/FoxAnim/FixDemo/Animations/"
CORE_FILES = (
    "end_trophy_01_cupint.fdc", "end_trophy_01_cam_ucl.fdc",
    "end_trophy_01_pl_few.fdc", "end_obj_platform_cmn.fdc",
)
FX_FILE = "end_trophy_01_fx.fdc"
DONOR_FILES = list(CORE_FILES[:3]) + [FX_FILE, CORE_FILES[3]] + [""] * 5
TEAMMATE_STEMS = (
    "hug01", "hug01_sub01", "joy07", "joy02", "joy08", "joy04",
    "joy05", "joy06", "joy03", "joy01",
)
MOB_MODELS = tuple("common/demo/mob/" + stem + "/" + stem + ".fpk"
                   for stem in ("mob_low_su00b", "mob_low_su01b"))
MOB_RESOURCES = (
    MOTION_PREFIX + "dml_mobH_cmn_clap03.gani",
    CHARACTER_PREFIX + "mob_high_anim_skel.ask",
    MOTION_PREFIX + "dml_mobH_cmn_clap01.gani",
)
PROP_MODELS = (
    "common/demo/prop/cup_int_hi/cup_int_hi.fpk",
    "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.fpk",
)
BASELINE_BUILD = "e861c583ec78e9ae"
BASELINE_DT220_SHA256 = "d83d98bfd1d25838a55a524875abf29d10693f13c9a73ee775745afa3d42a82a"


def references(raw: bytes) -> tuple[str, ...]:
    return tuple(asset_name(value[:-1].decode("ascii"))
                 for value in RESOURCE_PATH.findall(raw))


def encode_resource_table(items: list[tuple[str | int, bytes]], *, named: bool) -> bytes:
    """Rebuild container offsets while preserving item order and payload bytes."""
    data = bytearray(4 + 12 * len(items))
    struct.pack_into("<I", data, 0, len(items))
    for index, (key, raw) in enumerate(items):
        data.extend(b"\0" * (-len(data) % 4))
        offset = len(data)
        data.extend(raw)
        metadata = len(data)
        if named:
            asset_name(key)
            data.extend(key.encode("ascii") + b"\0")
        else:
            if not isinstance(key, int) or not 0 <= key <= 255:
                raise ValueError("invalid FDC record type")
            data.extend(bytes([key, 0]) if key else b"\0")
        struct.pack_into("<III", data, 4 + 12 * index, offset, len(raw), metadata)
    result = bytes(data)
    rows = table_entries(result, named=named)
    for row, (key, raw) in zip(rows, items):
        if (row.name if named else row.kind) != key or payload(result, row) != raw:
            raise ValueError("FDC table roundtrip changed a retained entry")
    return result


def strip_trailing_suit_mobs(raw: bytes) -> tuple[bytes, dict]:
    """Accept only the measured 10-human/4-mob layout, never arbitrary actors.

    Removed records and resources must be trailing. All retained ordinals,
    human IDs, sequence data and motion names remain byte-identical. Named
    dependency closure is checked before and after rebuilding container offsets.
    This validates the static edit, not native execution of the FDC sequences.
    """
    outer = table_entries(raw, named=True)
    if asset_name(outer[0].name) != FDC_PREFIX + "end/cut_data/" + CORE_FILES[2]:
        raise ValueError("unexpected teammate cut identity")
    inner = payload(raw, outer[0])
    records = table_entries(inner, named=False)
    if len(records) != 14 or len(outer) != 34:
        raise ValueError("unreviewed teammate record/resource count")
    expected_resources = []
    kept_refs = set()
    for index, stem in enumerate(TEAMMATE_STEMS):
        record = records[index]
        body = payload(inner, record)
        motion = MOTION_PREFIX + "dml_end_trophy01_" + stem
        expected = (motion + ".gani", motion + ".seq")
        if (record.kind != 4 or record.size != 364 or
                struct.unpack_from("<I", body)[0] != 0x10000 + index + 1 or
                references(body) != expected):
            raise ValueError("teammate actor ID/order/dependency layout changed")
        kept_refs.update(expected)
        expected_resources.extend((*expected, motion + "_eyes_target.gani"))
    if [asset_name(row.name) for row in outer[1:31]] != expected_resources:
        raise ValueError("retained resource ordinals no longer match teammate tracks")
    for row in outer[1:31]:
        body = payload(raw, row)
        if row.name.endswith(".gani") and body != b"\0" * 4:
            raise ValueError("teammate external motion placeholder changed")
        if row.name.endswith(".seq") and (body == b"\0" * 4 or references(body)):
            raise ValueError("unreviewed embedded teammate sequence dependency")
    for index, record in enumerate(records[10:]):
        body = payload(inner, record)
        model = MOB_MODELS[1 if index in (0, 3) else 0]
        motion = MOB_RESOURCES[0 if index in (0, 3) else 2]
        if (record.kind != 5 or record.size != 444 or
                struct.unpack_from("<I", body)[0] != 0x10000 + index + 2 or
                references(body) != (model, MOB_RESOURCES[1], motion)):
            raise ValueError("trailing object is not a proved suit-mob record")
    if [asset_name(row.name) for row in outer[31:]] != list(MOB_RESOURCES):
        raise ValueError("removed resource ordinals are not the trailing mob-only set")
    if any(payload(raw, row) != b"\0" * 4 for row in outer[31:]):
        raise ValueError("unreviewed embedded mob resource")
    if kept_refs & set(MOB_RESOURCES):
        raise ValueError("a retained actor still depends on a removed resource")
    new_inner = encode_resource_table(
        [(row.kind, payload(inner, row)) for row in records[:10]], named=False)
    reduced = encode_resource_table(
        [(outer[0].name, new_inner)] +
        [(row.name, payload(raw, row)) for row in outer[1:31]], named=True)
    checked = inspect_fdc(reduced)
    if (checked["record_types"] != {4: 10} or
            checked["actor_id_words"]["4"] != list(range(1, 11)) or
            set(checked["path_references"]) != kept_refs or
            any("mob" in row["name"] for row in checked["resources"])):
        raise ValueError("reduced actor/dependency/index validation failed")
    return reduced, {
        "input_sha256": digest(raw), "output_sha256": digest(reduced),
        "retained_record_ordinals": list(range(10)),
        "removed_record_ordinals": [10, 11, 12, 13],
        "removed_object_ids": [2, 3, 4, 5],
        "retained_resource_ordinals": list(range(31)),
        "removed_resource_ordinals": [31, 32, 33],
        "removed_resources": list(MOB_RESOURCES),
        "retained_human_ids": list(range(1, 11)),
        "retained_record_and_resource_payloads_identical": True,
        "container_offsets_rebuilt_and_bounds_checked": True,
        "retained_dependency_ordinals_validated": True,
        "native_sequence_execution_verified": False,
    }


def build_trophy_table(native: dict, donor: dict) -> dict:
    """Append reserved slots, never renumber/replace unrelated native groups."""
    if any(table["kind"] != 7 or table["version"] != 1 or
           table["condition_count"] != 10 or table["file_count"] != 10
           for table in (native, donor)):
        raise ValueError("validated v1 ten-slot ending tables required")
    # Re-parse to reject malformed group IDs rather than compacting them.
    if parse_scene_table(serialize_scene_table(native), 7) != native:
        raise ValueError("native ending table is not a semantic roundtrip")
    scene = next((row for row in donor["scenes"] if row["id"] == SCENE_ID), None)
    cut = next((row for row in donor["cuts"] if row["id"] == CUT_ID), None)
    if (not scene or scene["name"] != SCENE_NAME or not cut or
            cut["name"] != CUT_NAME or len(cut["variants"]) <= VARIANT_INDEX):
        raise ValueError("audited trophy scene/cut identity unavailable")
    variant = copy.deepcopy(cut["variants"][VARIANT_INDEX])
    if (variant["conditions"] != [513, 16384, 256] + [0] * 7 or
            variant["files"] != DONOR_FILES or variant["flags"] != 0x7FF or
            variant["human_mask"] != 3 or variant["move_distance"] != 0):
        raise ValueError("variant 1 is no longer the matching cup_int_hi/few layout")
    rows = [row for row in scene["cuts"] if row["cut_id"] == CUT_ID]
    if len(rows) != 1:
        raise ValueError("trophy sequence descriptor must be unique")
    row, terminal = copy.deepcopy(rows[0]), copy.deepcopy(scene["cuts"][-1])
    if (row["human_changes"] != [[1, 0, 0]] or
            row["signed_params"] != [6, 0, 180, 0] or row["tail_value"] != -1 or
            row["flags"] != 0 or row["fade"] != 3 or row["fade_time"] != .5 or
            terminal["cut_id"] != 0 or terminal["human_changes"] or
            terminal["signed_params"] != [0, 0, 0, 0] or
            terminal["tail_value"] != -1 or terminal["flags"] != 0):
        raise ValueError("captain/timing/terminal descriptor changed")
    # The caller's future final gate supplies eligibility. Like the native
    # Mobile endings, this one explicit variant uses the generic condition.
    generic = [256] + [0] * 9
    if not any(v["conditions"] == generic for c in native["cuts"] for v in c["variants"]):
        raise ValueError("native generic ending condition is unavailable")
    variant["conditions"] = generic
    variant["files"][3] = ""  # Preserve all other file-slot indices.
    result = copy.deepcopy(native)
    for key, target, name, records in (
        ("cuts", CUT_ID, CUT_NAME, [variant]),
        ("scenes", SCENE_ID, SCENE_NAME, [row, terminal]),
    ):
        field = "variants" if key == "cuts" else "cuts"
        target_index = (target & 0xFFFF) - 1
        if len(result[key]) > target_index:
            raise ValueError("trophy target ID collides with an existing native group")
        while len(result[key]) < target_index:
            index = len(result[key]) + 1
            result[key].append({"id": 0x70000 | index,
                                "name": f"NX_RESERVED_END_{key.upper()}_{index:04X}",
                                field: []})
        result[key].append({"id": target, "name": name, field: records})
    encoded = serialize_scene_table(result)
    if parse_scene_table(encoded, 7) != result:
        raise ValueError("trophy ending table failed semantic roundtrip")
    for key in ("cuts", "scenes"):
        if result[key][:len(native[key])] != native[key]:
            raise ValueError("unrelated native ending group changed")
    for key in ("controls", "has_controls", "control_condition_count"):
        if result[key] != native[key]:
            raise ValueError("native ending control data changed")
    return result


def validate_trophy_actors(files: dict[str, bytes]) -> None:
    expected = {
        CORE_FILES[0]: [(2, 92, 0x1303E8), (4, 364, 0x10000), (5, 444, 0x1006E)],
        CORE_FILES[2]: [(4, 364, 0x10000 + i) for i in range(1, 11)],
        CORE_FILES[3]: [(5, 444, 0x10190)],
    }
    for name, shape in expected.items():
        raw = files[name]
        outer = table_entries(raw, named=True)
        if asset_name(outer[0].name) != FDC_PREFIX + "end/cut_data/" + name:
            raise ValueError("trophy FDC self-name changed")
        inner = payload(raw, outer[0])
        records = table_entries(inner, named=False)
        measured = [(r.kind, r.size, struct.unpack_from("<I", inner, r.offset)[0])
                    for r in records]
        if measured != shape:
            raise ValueError("unreviewed captain/player/platform actor layout")
    if PROP_MODELS[0] not in inspect_fdc(files[CORE_FILES[0]])["path_references"]:
        raise ValueError("captain cut uses a different cup model")
    if inspect_fdc(files[CORE_FILES[3]])["path_references"] != [PROP_MODELS[1]]:
        raise ValueError("platform model dependency changed")


def collect_payloads(source: Cpk, mobile: list[Cpk]) -> tuple[dict, list, dict]:
    files = {name: source.read(FDC_PREFIX + "end/cut_data/" + name)
             for name in CORE_FILES}
    files[CORE_FILES[2]], reduction = strip_trailing_suit_mobs(files[CORE_FILES[2]])
    validate_trophy_actors(files)
    payloads = {FDC_PREFIX + "end/cut_data/" + name: raw for name, raw in files.items()}
    reports = []
    external_models = set()
    for name, raw in files.items():
        report = inspect_fdc(raw)
        if report["self_name"] != FDC_PREFIX + "end/cut_data/" + name:
            raise ValueError("trophy cut virtual path mismatch")
        dependencies = dependency_audit(report, source, mobile)
        for row in dependencies:
            name, resolution = row["name"], row["resolution"]
            if resolution == "embedded":
                continue
            if resolution == "mobile":
                if name not in source.index or digest(source.read(name)) != row["sha256"]:
                    raise ValueError("shared Mobile/donor dependency differs: " + name)
                continue
            if resolution == "donor_platform_only" and name in PROP_MODELS:
                parent, basename = name.rsplit("/", 1)
                if [c["name"] for c in row["platform_candidates"]] != [parent + "/#Win/" + basename]:
                    raise ValueError("prop model platform candidate is ambiguous")
                external_models.add(name)
                row["required_backend"] = "verified cooked StaticMesh and native prop bridge"
                continue
            if (resolution != "donor_only" or row.get("format_error") or
                    not name.startswith(MOTION_PREFIX + "dml_end_trophy01_") or
                    "/" in name[len(MOTION_PREFIX):] or not name.endswith(".gani")):
                raise ValueError(f"unreviewed trophy dependency: {name} ({resolution})")
            motion = source.read(name)
            gani_header(motion)
            if digest(motion) != row["sha256"] or (name in payloads and payloads[name] != motion):
                raise ValueError("conflicting or changed motion payload")
            payloads[name] = motion
        report["dependencies"] = dependencies
        report["dependency_counts"] = dict(Counter(row["resolution"] for row in dependencies))
        reports.append(report)
    if external_models != set(PROP_MODELS):
        raise ValueError("exactly the cup and platform renderer dependencies are required")
    return payloads, reports, reduction


def stage(fl26_root: Path, mobile_root: Path, output: Path) -> dict:
    output = output_directory(output)
    output.mkdir(parents=True)
    report = {"schema": "PESNX_TROPHY_ASSETS_V1", "status": "blocked_asset_validation",
              "runtime_verified": False, "hardware_tested": False, "scene_enabled": False,
              "active_runtime_modified": False, "save_format_changed": False,
              "native_fps_skip_callbacks_changed": False}
    try:
        mobile_root = mobile_root.resolve()
        manifest = verify(mobile_root)
        base = mobile_root / "LooseCpk/dt220_mobile_all.cpk"
        if (manifest["version"] != 2 or manifest["build_id"] != BASELINE_BUILD or
                file_digest(base) != BASELINE_DT220_SHA256):
            raise ValueError("the accepted full LooseCpk V2 baseline is required")
        source = Cpk(fl26_root / "Data/dt12_g4.cpk")
        mobile = [Cpk(mobile_root / "LooseCpk" / name) for name in
                  ("dt220_mobile_all.cpk", "dt230_mobile_all.cpk")]
        native_raw, donor_raw = mobile[0].read(TABLE), source.read(TABLE)
        native, donor = parse_scene_table(native_raw, 7), parse_scene_table(donor_raw, 7)
        table = build_trophy_table(native, donor)
        payloads, cuts, reduction = collect_payloads(source, mobile)
        skeletons = skeleton_audit(source, mobile[0])
        if not skeletons["all_identical"]:
            raise ValueError("player/eye skeleton or rig differs from Mobile")
        cup_skeletons = []
        for name in ("cup_anim_skel.ask", "cup_skel.frig"):
            path = CHARACTER_PREFIX + name
            if source.read(path) != mobile[0].read(path):
                raise ValueError("cup skeleton or rig differs from Mobile")
            cup_skeletons.append({"name": path, "sha256": digest(source.read(path)),
                                  "mobile_identical": True})
        payloads[TABLE] = serialize_scene_table(table)
        if set(payloads) & set(mobile[0].index) != {TABLE}:
            raise ValueError("baseline contains unexpected pre-existing trophy assets")
        actions = {name: "replace" if name == TABLE else "add" for name in payloads}
        with tempfile.TemporaryDirectory(prefix="work-", dir=output) as temp:
            work = Path(temp)
            paths = {}
            for index, (name, raw) in enumerate(payloads.items()):
                path = work / f"asset-{index}.bin"
                path.write_bytes(raw)
                paths[name] = str(path.resolve())
            packed = package_cpk(ROOT, work, "trophy", base, actions, payloads, paths)
            update = work / "update"
            loose = update / "LooseCpk"
            loose.mkdir(parents=True)
            final = loose / base.name
            order = list(mobile[0].index) + sorted(set(payloads) - set(mobile[0].index))
            order_report = restore_order(Path(packed["candidate"]), final, order)
            validation = validate_cpk(base, final, actions, payloads)
            candidate = Cpk(final)
            if list(candidate.index) != order or any(candidate.index[n]["ID"] != r["ID"]
                                                      for n, r in mobile[0].index.items()):
                raise ValueError("existing CPK IDs or row order changed")
            if candidate.read(ENTRANCE_TABLE) != mobile[0].read(ENTRANCE_TABLE):
                raise ValueError("native entrance table changed")
            updated_manifest = copy.deepcopy(manifest)
            entry = next(row for row in updated_manifest["files"] if row["name"] == base.name)
            entry.update(size=final.stat().st_size, sha256=file_digest(final))
            write_manifest(update, updated_manifest)
            update.replace(output / "update")
        validation["candidate"] = str(output / "update/LooseCpk" / base.name)
        report.update(
            status="asset_only_not_playable", baseline_root=str(mobile_root),
            baseline_build_id=manifest["build_id"], baseline_dt220_sha256=BASELINE_DT220_SHA256,
            baseline_manifest_sha256=file_digest(mobile_root / "LooseCpk/manifest.txt"),
            donor_archive=str(source.path), donor_table_sha256=digest(donor_raw),
            native_table_sha256=digest(native_raw), table_sha256=digest(payloads[TABLE]),
            scene_id=SCENE_ID, cut_id=CUT_ID, donor_variant_index=VARIANT_INDEX,
            variant_reason="variant 1 authors cup_int_hi and its captain motion; variant 13 uses cup_intclub_hi",
            actor_mask=0x7FF, human_mask=3, captain_assignment=[[1, 0, 0]],
            selected_files=list(CORE_FILES), omitted_files=[FX_FILE], mob_reduction=reduction,
            unchanged_native_scene_ids=[row["id"] for row in native["scenes"]],
            unchanged_native_cut_ids=[row["id"] for row in native["cuts"]],
            controls_preserved=True, native_entrance_preserved=True,
            payloads=[{"name": name, "bytes": len(raw), "sha256": digest(raw)}
                      for name, raw in payloads.items()],
            payload_bytes=sum(map(len, payloads.values())), cut_reports=cuts,
            player_skeletons=skeletons, cup_skeletons=cup_skeletons,
            validation=validation, cpk_sorted_flag=order_report["sorted_flag"],
            barriers=[
                "Cup/platform PC model paths require a separately verified cooked mesh and renderer bridge.",
                "No native factory hook, fresh final-result integration, or scene activation is installed.",
                "Native sequences, animation playback, camera framing, FPS restoration and Skip need hardware validation.",
                "The reduced scene retains platform height and native captain-parent/cup animation transforms.",
                "Entrance and trophy packages replace the same dt220/manifest pair; they cannot be overlaid independently.",
            ])
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        report["barriers"] = [str(exc)]
    (output / "trophy-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "NOT-PLAYABLE.txt").write_text(
        "ASSET-ONLY TROPHY CANDIDATE - NOT PLAYABLE OR A RUNTIME UPDATE\n"
        "Do not install this detached package by itself. See trophy-report.json.\n"
        "No PAK, NRO, activation marker, active runtime or save was changed.\n"
        "The existing entrance and unrelated native ending paths are retained.\n"
        "No Switch/hardware validation has been performed.\n"
        "Entrance and trophy candidates replace the SAME dt220/manifest pair.\n"
        "Do not overlay them independently; an explicit merge and revalidation are required.\n",
        encoding="utf-8")
    return report


def probe_trophy_motions(fl26_root: Path, mobile_root: Path, native_elf: Path,
                         output: Path) -> dict:
    """Optional sealed decoder samples, not full clips or a running game.

    Reuse the entrance probe for actual body/eye skeletons. The cup's rigid
    motion is evaluated separately with its shared one-bone cup skeleton/rig;
    interpreting it as a player track would be the wrong validation topology.
    Only pose validity summaries and input hashes are retained.
    """
    output = output_directory(output)
    output.mkdir(parents=True)
    report = {"schema": "PESNX_TROPHY_MOTION_SAMPLES_V1",
              "status": "sampled_motion_decode_incomplete", "hardware_tested": False,
              "full_clip_decode": False, "scene_playback_verified": False,
              "evidence": "isolated Mobile ARM64 animation decoder; first/middle/last poses only"}
    try:
        from entrance_scene_canary import probe_motion_decode
        from native_animation_bake import NativeAnimationVM
        from convert_ef_referee import Sampler, normalized, read_skeleton

        source = Cpk(fl26_root / "Data/dt12_g4.cpk")
        mobile = [Cpk(mobile_root / "LooseCpk" / name) for name in
                  ("dt220_mobile_all.cpk", "dt230_mobile_all.cpk")]
        _, cuts, _ = collect_payloads(source, mobile)
        dependencies = {row["name"]: row for cut in cuts for row in cut["dependencies"]}
        cup_name = MOTION_PREFIX + "dml_end_trophy01_cup_int_cup_int_hi.gani"
        if cup_name not in dependencies:
            raise ValueError("the authored rigid cup motion is missing")
        report["players_and_captain"] = probe_motion_decode(
            native_elf, source, mobile[0],
            [row for name, row in dependencies.items() if name != cup_name])
        skeleton_name = CHARACTER_PREFIX + "cup_anim_skel.ask"
        rig_name = CHARACTER_PREFIX + "cup_skel.frig"
        skeleton, rig = mobile[0].read(skeleton_name), mobile[0].read(rig_name)
        if skeleton != source.read(skeleton_name) or rig != source.read(rig_name):
            raise ValueError("rigid cup skeleton/rig differs from Mobile")
        if read_skeleton(skeleton) != [{"name": "sk_prop", "parent": -1, "pos": (0., 0., 0.)}]:
            raise ValueError("rigid cup does not have the audited one-bone skeleton")
        gani = source.read(cup_name)
        gani_header(gani)
        if len(gani) < 164 or struct.unpack_from("<4I", gani, 0x60) != (3337172921, 0, 1, 48):
            raise ValueError("rigid cup uses an unsupported unit-track layout")
        frames, scale = struct.unpack_from("<Ib", gani, 156)
        if not 2 <= frames <= 3000 or scale != 10:
            raise ValueError("rigid cup has unsupported bounded timing")
        vm = NativeAnimationVM(native_elf)
        sampler = Sampler(vm, skeleton, rig)
        th = vm.alloc(len(gani), gani) + 144
        size = vm.call("_ZN3fox4anim12TrackControl19GetTrackControlSizeEPKNS0_11TrackHeaderE", th)
        tc = vm.alloc(size)
        vm.call("_ZN3fox4anim12TrackControlC2EPKNS0_11TrackHeaderEi", tc, th, 0)
        sample_frames = sorted({0, frames // 2, frames - 1})
        max_position = 0.
        for frame in sample_frames:
            vm.uc.mem_write(sampler.p, sampler.default_positions)
            vm.uc.mem_write(sampler.q, sampler.default_rotations)
            vm.call("_ZN3fox4anim12TrackControl7SetDataEPKNS0_11TrackHeaderEff",
                    tc, th, floats=(frame * scale, 0.))
            vm.call("_ZN3fox4anim7RigPose10UpdatePoseERKNS0_8BoneMaskEPKNS0_12TrackControlEPKNS0_6RigDefEPNS0_11RigSkeletonEj",
                    sampler.pose, sampler.mask, tc, sampler.rig, sampler.rs, 0)
            vm.call("_ZNK3fox4anim7RigPose14PoseToSkeletonEPNS0_11RigSkeletonEPKNS0_6RigDefE",
                    sampler.pose, sampler.rs, sampler.rig)
            normalized(struct.unpack("<4f", vm.read(sampler.q, 16)))
            position = struct.unpack("<3f", vm.read(sampler.p, 12))
            if any(not math.isfinite(value) or abs(value) > 1000 for value in position):
                raise ValueError("rigid cup sample position is non-finite/out of bounds")
            max_position = max(max_position, *map(abs, position))
        report["rigid_cup"] = {
            "name": cup_name, "sha256": digest(gani), "frames": frames,
            "sampled_frames": sample_frames, "bones": sampler.n,
            "skeleton_sha256": digest(skeleton), "rig_sha256": digest(rig),
            "finite_normalized_poses": True, "max_abs_position": max_position,
        }
        report["sampled_pose_count"] = (
            report["players_and_captain"]["sampled_pose_count"] + len(sample_frames))
        report["status"] = "sampled_motion_decode_passed"
    except Exception as exc:
        # Optional probe failures must leave the already validated asset-only
        # package usable for further inspection; never turn a gap into a pass.
        report["gap"] = f"{type(exc).__name__}: {exc}"
    (output / "motion-samples.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path, required=True)
    parser.add_argument("--mobile-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-native-elf", type=Path,
                        help="optionally sample retained motions with the sealed Mobile decoder")
    args = parser.parse_args()
    report = stage(args.fl26_root, args.mobile_root, args.output)
    print(json.dumps({"output": str(args.output), "status": report["status"],
                      "assets": len(report.get("payloads", [])),
                      "barriers": report["barriers"]}))
    if report["status"] != "asset_only_not_playable":
        raise SystemExit(1)
    if args.sample_native_elf:
        sampled = probe_trophy_motions(args.fl26_root, args.mobile_root,
                                       args.sample_native_elf, args.output / "pose-samples")
        print(json.dumps({"motion_samples": sampled["status"],
                          "sampled_poses": sampled.get("sampled_pose_count", 0),
                          "gap": sampled.get("gap")}))
        # The caller explicitly requested this validation. A valid detached
        # asset stage must not hide a failed decoder behind exit code zero.
        if sampled["status"] != "sampled_motion_decode_passed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
