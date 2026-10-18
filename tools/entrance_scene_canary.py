#!/usr/bin/env python3
"""Audit local FixDemo cuts and stage only a detached, explicit asset canary.

FDC is a named-resource table containing a typed-record table plus embedded
resources. This reader checks the measured Mobile/PC container layout; it does
not claim that equal container formats prove animation, skeleton, or scene
compatibility. No proprietary bytes are emitted. Reports are restricted to a
new directory under local-debug; a separate reviewed builder owns any staging.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import zlib

from prepare_loose_cpk import cpk_layout, member_name
from fixdemo_scene_table import parse_scene_table, serialize_scene_table

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 16384
FDC_PREFIX = "common/demo/fixdemo/"
CHARACTER_PREFIX = "common/demo/anime/FoxAnim/FixDemo/CharacterAssets/"
RESOURCE_PATH = re.compile(
    rb"(?:cpk_dat/)?(?:common/|ent/|end/|goal/|foul/|result/|mode/)"
    rb"[A-Za-z0-9_./ -]+\.(?:gani|seq|ask|fpkd?|fmdl|canm|xml|fdc|ftex)\x00"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def asset_name(name: str) -> str:
    """Canonical virtual path; never turn arbitrary binary text into a path."""
    value = name.replace("\\", "/").removeprefix("cpk_dat/")
    path = PurePosixPath(value)
    if (not value or value.startswith("/") or ":" in value or
            any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError(f"unsafe asset path: {name!r}")
    return path.as_posix()


@dataclass(frozen=True)
class Entry:
    offset: int
    size: int
    metadata: int
    name: str = ""
    kind: int = -1


def table_entries(data: bytes, *, named: bool) -> tuple[Entry, ...]:
    """Strict table parser; metadata is a name or a NUL-terminated type byte."""
    if not 4 <= len(data) <= MAX_BYTES:
        raise ValueError("invalid FDC table size")
    count = struct.unpack_from("<I", data)[0]
    header_end = 4 + 12 * count
    if not 0 < count <= MAX_ENTRIES or header_end > len(data):
        raise ValueError("invalid FDC entry count")
    entries = []
    spans = []
    for index in range(count):
        offset, size, metadata = struct.unpack_from("<III", data, 4 + 12 * index)
        if size == 0 or offset < header_end or offset + size > len(data):
            raise ValueError("FDC payload outside table")
        if metadata < header_end or metadata >= len(data):
            raise ValueError("FDC metadata outside table")
        spans.append((offset, offset + size))
        if named:
            end = data.find(b"\0", metadata)
            if end < 0 or end - metadata > 1024:
                raise ValueError("unterminated/oversize FDC resource name")
            try:
                name = data[metadata:end].decode("ascii")
            except UnicodeDecodeError as exc:
                raise ValueError("non-ASCII FDC resource name") from exc
            asset_name(name)
            entries.append(Entry(offset, size, metadata, name=name))
            spans.append((metadata, end + 1))
        else:
            # This is a one-byte type stored as a C string, not a uint16:
            # type zero occupies one byte; nonzero types have a terminator.
            kind = data[metadata]
            width = 2 if kind else 1
            if metadata + width > len(data) or (kind and data[metadata + 1]):
                raise ValueError("unsupported/truncated FDC record type")
            entries.append(Entry(offset, size, metadata, kind=kind))
            spans.append((metadata, metadata + width))
    spans.sort()
    for previous, current in zip(spans, spans[1:]):
        if current[0] < previous[1]:
            raise ValueError("overlapping FDC payload/metadata ranges")
    return tuple(entries)


def payload(data: bytes, entry: Entry) -> bytes:
    return data[entry.offset:entry.offset + entry.size]


def gani_header(data: bytes) -> dict:
    """Measured common GANI envelope only, not a bone/track compatibility test."""
    if len(data) < 32 or len(data) > MAX_BYTES:
        raise ValueError("invalid GANI size")
    words = struct.unpack_from("<8I", data)
    if (words[0] != 0x0BFCA2D2 or words[1] != 32 or words[2] != len(data) or
            words[3:7] != (0, 0, 1, 0)):
        raise ValueError("unsupported GANI envelope")
    return {"magic": f"{words[0]:08x}", "header_bytes": words[1],
            "bytes": words[2], "version": words[5], "flags": words[7]}


def inspect_fdc(data: bytes) -> dict:
    entries = table_entries(data, named=True)
    if not entries[0].name.endswith(".fdc"):
        raise ValueError("first FDC resource is not the cut record table")
    inner = payload(data, entries[0])
    records = table_entries(inner, named=False)
    resources = []
    for entry in entries[1:]:
        raw = payload(data, entry)
        resources.append({"name": asset_name(entry.name), "bytes": len(raw),
                          "sha256": digest(raw), "placeholder": raw == b"\0" * 4})
    refs = sorted({asset_name(match[:-1].decode("ascii"))
                   for match in RESOURCE_PATH.findall(inner)})
    return {
        "bytes": len(data), "sha256": digest(data),
        "self_name": asset_name(entries[0].name),
        "record_types": dict(sorted(Counter(record.kind for record in records).items())),
        "record_sizes": {str(kind): sorted({record.size for record in records
                                            if record.kind == kind})
                         for kind in sorted({record.kind for record in records})},
        # Measured first uint16 only. The native integration owner validates
        # whether these IDs are supported actor slots; do not silently remap.
        "actor_id_words": {str(kind): [struct.unpack_from("<H", payload(inner, record))[0]
                                      for record in records
                                      if record.kind == kind and record.size >= 2]
                           for kind in (2, 4, 5)},
        "actor_float_prefixes": [
            {"kind": record.kind, "id_word": struct.unpack_from("<H", raw)[0],
             "offset4_floats": list(struct.unpack_from("<4f", raw, 4))}
            for record in records if record.kind in (4, 5) and record.size >= 20
            for raw in [payload(inner, record)]],
        "resources": resources, "path_references": refs,
    }


class Cpk:
    """Read only a bounded member, not a duplicate or extraction of its archive."""
    def __init__(self, path: Path):
        self.path = path.resolve()
        self.size = self.path.stat().st_size
        _, rows, self.base = cpk_layout(self.path)
        self.index = {}
        for row in rows:
            name = asset_name(member_name(row))
            if name in self.index:
                raise ValueError(f"duplicate CPK member: {name}")
            offset, size = self.base + int(row["FileOffset"]), int(row["FileSize"])
            if offset < 0 or size < 0 or offset + size > self.size:
                raise ValueError(f"out-of-bounds CPK member: {name}")
            self.index[name] = row

    def read(self, name: str) -> bytes:
        row = self.index[name]
        size = int(row["FileSize"])
        if size != int(row["ExtractSize"]) or not 0 < size <= MAX_BYTES:
            raise ValueError(f"CPK compression/size unsupported: {name}")
        with self.path.open("rb") as stream:
            stream.seek(self.base + int(row["FileOffset"]))
            data = stream.read(size)
        if len(data) != size:
            raise ValueError(f"truncated CPK member: {name}")
        if data[3:8] == b"WESYS":
            if len(data) < 16:
                raise ValueError("truncated WESYS header")
            packed_size, decoded_size = struct.unpack_from("<II", data, 8)
            if packed_size != len(data) - 16 or not 0 < decoded_size <= MAX_BYTES:
                raise ValueError("invalid WESYS bounds")
            decoder = zlib.decompressobj()
            decoded = decoder.decompress(data[16:], decoded_size + 1)
            if (len(decoded) != decoded_size or not decoder.eof or decoder.unused_data or
                    decoder.unconsumed_tail):
                raise ValueError("invalid/oversize WESYS compressed stream")
            data = decoded
        return data


def dependency_audit(cut: dict, source: Cpk, mobile: list[Cpk]) -> list[dict]:
    embedded = {row["name"]: row for row in cut["resources"]}
    result = []
    # Embedded names also matter: an eye-target .gani can be an external zero
    # placeholder even when its name is not repeated in the typed records.
    refs = sorted(set(cut["path_references"]) | set(embedded))
    for name in refs:
        if name == cut["self_name"]:
            continue
        resource = embedded.get(name)
        if resource and not resource["placeholder"]:
            result.append({"name": name, "resolution": "embedded", **resource})
            continue
        matches = [cpk for cpk in mobile if name in cpk.index]
        row = {"name": name, "placeholder": bool(resource)}
        if len(matches) > 1:
            row["resolution"] = "ambiguous_mobile"
        elif matches:
            data = matches[0].read(name)
            row.update(resolution="mobile", archive=str(matches[0].path),
                       bytes=len(data), sha256=digest(data))
            if name in source.index:
                donor_digest = digest(source.read(name))
                row["donor_sha256"] = donor_digest
                row["donor_identical"] = donor_digest == row["sha256"]
        elif name in source.index:
            data = source.read(name)
            row.update(resolution="donor_only", archive=str(source.path),
                       bytes=len(data), sha256=digest(data))
            if name.endswith(".gani"):
                try:
                    row["gani_envelope"] = gani_header(data)
                except ValueError as exc:
                    row["format_error"] = str(exc)
        else:
            row["resolution"] = "missing"
            # PC authored paths omit the platform segment. Finding a #Win
            # payload is evidence of an available donor model, NOT proof that
            # Mobile's loader accepts its FPK/FMDL/material/texture formats.
            parent, _, basename = name.rpartition("/")
            candidates = [candidate for candidate in source.index
                          if candidate.startswith(parent + "/#") and
                          candidate.rsplit("/", 1)[-1] == basename]
            if candidates:
                row["resolution"] = "donor_platform_only"
                row["platform_candidates"] = [
                    {"name": candidate, "bytes": len(raw := source.read(candidate)),
                     "sha256": digest(raw)} for candidate in candidates]
        result.append(row)
    return result


def cut_report(source: Cpk, name: str, mobile: list[Cpk]) -> dict:
    data = source.read(name)
    report = inspect_fdc(data)
    report["member"] = name
    report["dependencies"] = dependency_audit(report, source, mobile)
    report["dependency_counts"] = dict(Counter(
        row["resolution"] for row in report["dependencies"]))
    # Explicitly not a release qualification: unknown event/actor and animation
    # semantics must be checked by the runtime integration owner.
    report["runtime_verified"] = False
    return report


def variant_report(source: Cpk, mobile: list[Cpk], cut_name: str,
                   variant_index: int, *, selected_files: list[str] | None = None,
                   kind: int = 1) -> dict:
    """Audit one entrance/ending variant; explicit omissions remain visible."""
    if kind not in (1, 7):
        raise ValueError("variant audit supports entrance(1) or ending(7) only")
    bank = "ent" if kind == 1 else "end"
    table = parse_scene_table(source.read(FDC_PREFIX + bank + "/table_" + bank + ".bin"), kind)
    cut = next((row for row in table["cuts"] if row["name"] == cut_name), None)
    if cut is None or not 0 <= variant_index < len(cut["variants"]):
        raise ValueError("unknown entrance/ending cut/variant index")
    variant = cut["variants"][variant_index]
    available = [name for name in variant["files"] if name]
    chosen = available if selected_files is None else selected_files
    if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(available):
        raise ValueError("selected files must be a nonempty unique variant subset")
    cuts = [cut_report(source, FDC_PREFIX + bank + "/cut_data/" + asset_name(name), mobile)
            for name in chosen]
    deps = {}
    for item in cuts:
        for row in item["dependencies"]:
            if row["name"] in deps and deps[row["name"]].get("sha256") != row.get("sha256"):
                raise ValueError("different resource payloads share one virtual path")
            deps[row["name"]] = row
    return {"cut_name": cut_name, "kind": kind, "source_cut_id": cut["id"],
            "source_variant_index": variant_index, "source_variant": variant,
            "omitted_files": [name for name in available if name not in chosen],
            "cuts": cuts, "dependencies": list(deps.values()),
            "dependency_counts": dict(Counter(row["resolution"] for row in deps.values())),
            "donor_asset_bytes": sum(item["bytes"] for item in cuts) + sum(
                row["bytes"] for row in deps.values() if row["resolution"] == "donor_only"),
            "runtime_verified": False}


def skeleton_audit(source: Cpk, mobile: Cpk) -> dict:
    """Compare exact shared player/eye assets instead of inferring from names."""
    from convert_ef_referee import read_skeleton
    files = []
    names = ("body_anim_skel.ask", "body_render_skel.ask", "body_high_skel.ask",
             "body_skel.frig", "eyes_target_anim_skel.ask", "pes_eyes_target_150120.frig")
    for name in names:
        path = CHARACTER_PREFIX + name
        donor, native = source.read(path), mobile.read(path)
        item = {"name": path, "donor_sha256": digest(donor),
                "mobile_sha256": digest(native), "identical": donor == native}
        if name.endswith(".ask"):
            item["donor_bones"] = len(read_skeleton(donor))
            item["mobile_bones"] = len(read_skeleton(native))
        files.append(item)
    return {"files": files, "all_identical": all(row["identical"] for row in files)}


def probe_motion_decode(native_elf: Path, source: Cpk, mobile: Cpk,
                        dependencies: list[dict]) -> dict:
    """Evaluate three frame knots with the sealed local Mobile ARM64 decoder.

    No Android/game process, host game code, network, rendering or disk imports
    are available to NativeAnimationVM. Poses are checked then discarded; only
    hashes, counts and numeric validity summaries leave the emulator.
    """
    from native_animation_bake import NativeAnimationVM
    from convert_ef_referee import Sampler, normalized
    skeletons = skeleton_audit(source, mobile)
    if not skeletons["all_identical"]:
        raise ValueError("donor/Mobile skeleton or rig mismatch; decoding is not a retargeter")
    names = sorted({row["name"] for row in dependencies if row["name"].endswith(".gani")
                    and row["resolution"] in ("donor_only", "mobile")})
    if not names or len(names) > 128:
        raise ValueError("motion probe requires 1..128 explicitly audited GANI dependencies")
    vm = NativeAnimationVM(native_elf)
    samplers = {}
    for key, skel, rig in (
        ("body", "body_anim_skel.ask", "body_skel.frig"),
        ("eyes", "eyes_target_anim_skel.ask", "pes_eyes_target_150120.frig"),
    ):
        samplers[key] = Sampler(vm, mobile.read(CHARACTER_PREFIX + skel),
                                mobile.read(CHARACTER_PREFIX + rig))
    results = []
    for name in names:
        gani = source.read(name)
        gani_header(gani)
        if len(gani) < 164 or struct.unpack_from("<4I", gani, 0x60) != (3337172921, 0, 1, 48):
            raise ValueError("unsupported GANI unit-track layout")
        frames, scale = struct.unpack_from("<Ib", gani, 156)
        if not 2 <= frames <= 3000 or scale != 10:
            raise ValueError("unsupported bounded scene-motion timing")
        sampler = samplers["eyes" if name.endswith("_eyes_target.gani") else "body"]
        th = vm.alloc(len(gani), gani) + 144
        size = vm.call("_ZN3fox4anim12TrackControl19GetTrackControlSizeEPKNS0_11TrackHeaderE", th)
        tc = vm.alloc(size)
        vm.call("_ZN3fox4anim12TrackControlC2EPKNS0_11TrackHeaderEi", tc, th, 0)
        sample_frames = sorted({0, frames // 2, frames - 1})
        max_position = 0.0
        for frame in sample_frames:
            vm.uc.mem_write(sampler.p, sampler.default_positions)
            vm.uc.mem_write(sampler.q, sampler.default_rotations)
            vm.call("_ZN3fox4anim12TrackControl7SetDataEPKNS0_11TrackHeaderEff",
                    tc, th, floats=(frame * scale, 0.0))
            vm.call("_ZN3fox4anim7RigPose10UpdatePoseERKNS0_8BoneMaskEPKNS0_12TrackControlEPKNS0_6RigDefEPNS0_11RigSkeletonEj",
                    sampler.pose, sampler.mask, tc, sampler.rig, sampler.rs, 0)
            vm.call("_ZNK3fox4anim7RigPose14PoseToSkeletonEPNS0_11RigSkeletonEPKNS0_6RigDefE",
                    sampler.pose, sampler.rs, sampler.rig)
            for index in range(sampler.n):
                normalized(struct.unpack("<4f", vm.read(sampler.q + index * 16, 16)))
                position = struct.unpack("<3f", vm.read(sampler.p + index * 16, 12))
                if any(not math.isfinite(value) or abs(value) > 1000 for value in position):
                    raise ValueError("decoded scene pose is non-finite/out of bounds")
                max_position = max(max_position, *map(abs, position))
        results.append({"name": name, "sha256": digest(gani), "frames": frames,
                        "sampled_frames": sample_frames, "bones": sampler.n,
                        "finite_normalized_poses": True, "max_abs_position": max_position})
    return {"evidence": "isolated Mobile ARM64 animation decoder, not a game or renderer",
            "native_elf_sha256": digest(vm.raw), "skeletons": skeletons, "motions": results,
            "sampled_pose_count": sum(len(row["sampled_frames"]) for row in results),
            "hardware_tested": False, "full_clip_decode": False}


def audit(fl26: Path, mobile_loose: Path, selected: list[str]) -> tuple[dict, Cpk]:
    source = Cpk(fl26 / "Data/dt12_g4.cpk")
    mobile = [Cpk(mobile_loose / name) for name in
              ("dt220_mobile_all.cpk", "dt230_mobile_all.cpk")]
    native_name = FDC_PREFIX + "ent/cut_data/ent_001_mobile_st000_cam.fdc"
    native = cut_report(mobile[0], native_name, mobile)
    cuts = []
    for name in selected:
        name = asset_name(name)
        if not name.startswith(FDC_PREFIX) or not name.endswith(".fdc"):
            raise ValueError("select an explicit FixDemo .fdc member")
        cuts.append(cut_report(source, name, mobile))
    tables = []
    for kind in ("ent", "end"):
        name = FDC_PREFIX + kind + "/table_" + kind + ".bin"
        kind_id = 1 if kind == "ent" else 7
        target = mobile[0].read(name)
        donor = source.read(name)
        target_table = parse_scene_table(target, kind_id)
        donor_table = parse_scene_table(donor, kind_id)
        tables.append({"name": name,
                       "mobile_bytes": len(target),
                       "mobile_sha256": digest(target),
                       "donor_bytes": len(donor),
                       "donor_sha256": digest(donor),
                       "mobile_cut_count": len(target_table["cuts"]),
                       "mobile_scenes": [{"name": row["name"], "id": row["id"]}
                                         for row in target_table["scenes"]],
                       "donor_cut_count": len(donor_table["cuts"]),
                       "donor_scenes": [{"name": row["name"], "id": row["id"]}
                                        for row in donor_table["scenes"]],
                       "mobile_roundtrip_identical": serialize_scene_table(target_table) == target,
                       "donor_roundtrip_identical": serialize_scene_table(donor_table) == donor})
    counts = lambda index: dict(Counter(
        name.split("/")[3] for name in index
        if name.startswith(FDC_PREFIX) and name.endswith(".fdc")))
    native_gani = next(name for name in mobile[0].index if name.endswith(".gani"))
    return {
        "schema": "PESNX_FIXDEMO_ASSET_AUDIT_V1",
        "evidence": "offline CPK/FDC parsing; not runtime execution or REA output",
        "donor_archive": str(source.path), "donor_archive_bytes": source.size,
        "mobile_archives": [str(cpk.path) for cpk in mobile],
        "donor_fdc_counts": counts(source.index),
        "mobile_fdc_counts": counts(mobile[0].index),
        "tables": tables, "native_entrance": native,
        "native_gani_envelope": gani_header(mobile[0].read(native_gani)),
        "player_skeletons": skeleton_audit(source, mobile[0]),
        "selected_cuts": cuts,
        "limitations": [
            "Path references are measured strings, not a complete native load trace.",
            "FPK/model internals, bone mapping, motion tracks, and stadium transforms are not validated.",
            "Existing Mobile dependencies checked in dt220 and dt230 only.",
            "Matching envelopes do not establish semantic or hardware compatibility.",
        ], "runtime_verified": False,
    }, source


def output_directory(path: Path) -> Path:
    output = path.resolve()
    if (ROOT / "local-debug").resolve() not in output.parents:
        raise ValueError("output must be strictly inside ignored local-debug")
    if output.exists():
        raise FileExistsError("output must be a new directory; existing results are preserved")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path, required=True)
    parser.add_argument("--mobile-loose", type=Path, required=True)
    parser.add_argument("--cut", action="append", default=[])
    parser.add_argument("--variant", help="one CUT_NAME:ZERO_BASED_INDEX in --kind bank")
    parser.add_argument("--kind", type=int, choices=(1, 7), default=1,
                        help="variant bank: entrance1 (default) or ending7")
    parser.add_argument("--variant-file", action="append", default=[],
                        help="explicit subset of that variant; omissions stay in the report")
    parser.add_argument("--native-elf", type=Path,
                        help="opt in to bounded offline ARM64 motion decoding for --variant")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = output_directory(args.output)
    report, source = audit(args.fl26_root, args.mobile_loose, args.cut)
    if args.variant_file and not args.variant:
        parser.error("--variant-file requires --variant")
    if args.native_elf and not args.variant:
        parser.error("--native-elf requires --variant")
    if args.native_elf and args.kind != 1:
        parser.error("native motion probe currently supports entrance player/eye clips only")
    if args.variant:
        name, separator, index = args.variant.rpartition(":")
        if not separator or not index.isdecimal():
            parser.error("--variant must be CUT_NAME:ZERO_BASED_INDEX")
        mobile = [Cpk(args.mobile_loose / filename) for filename in
                  ("dt220_mobile_all.cpk", "dt230_mobile_all.cpk")]
        report["selected_variant"] = variant_report(
            source, mobile, name, int(index), selected_files=args.variant_file or None, kind=args.kind)
        if args.native_elf:
            report["native_motion_probe"] = probe_motion_decode(
                args.native_elf, source, mobile[0], report["selected_variant"]["dependencies"])
    output.mkdir(parents=True)
    (output / "asset-audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema": "PESNX_FIXDEMO_CANARY_PLAN_V1", "installable": False,
        "active_runtime_modified": False, "payloads_staged": [],
        "audit": "asset-audit.json",
        "required_before_install": [
            "Validated minimal scene table and actor assignments.",
            "Resolved/validated skeletal-animation and model dependency closure.",
            "Native skip, kickoff/result transition and repeated-match hardware checks.",
        ],
    }
    (output / "canary-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "selected_cuts": len(report["selected_cuts"]),
                      "installable": False, "payloads_staged": 0}))


if __name__ == "__main__":
    main()
