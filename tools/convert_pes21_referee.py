"""Bake an owned FL26/PES21 referee bank with the compatible Mobile decoder.

This samples actual GANI/FRIG poses, including the native limb solver. The
animation and render skeletons must be the same PES21 20-bone profile. World
poses are mapped directly to the native renderer's 19 slots; no EF skeleton or
retargeting is involved. Horizontal root travel belongs to the live follower
and is removed from every bone. Render bind rotations are applied last.

The owned ELF runs only inside the existing sealed animation-math evaluator.
No game process, renderer, filesystem or networking import is available there.
Generated animation payloads are proprietary and must stay local and ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

try:
    from .audit_fl26_referee import BODY, CLIP_KEYS, MEMBER_LIMIT, inspect_mtar
    from .build_fl26_cup_catalog import cpk_member, index_cpk
    from .convert_ef_referee import (CLIPS, ENTRY, HEADER, MAGIC, POSE, SPEEDS,
                                     Sampler, normalized, read_skeleton,
                                     render_rotation, render_rotations, rotate,
                                     unpack_wesys)
    from .pack_runtime_assets import checksum
except ImportError:
    from audit_fl26_referee import BODY, CLIP_KEYS, MEMBER_LIMIT, inspect_mtar
    from build_fl26_cup_catalog import cpk_member, index_cpk
    from convert_ef_referee import (CLIPS, ENTRY, HEADER, MAGIC, POSE, SPEEDS,
                                    Sampler, normalized, read_skeleton,
                                    render_rotation, render_rotations, rotate,
                                    unpack_wesys)
    from pack_runtime_assets import checksum


NATIVE_ELF_SHA256 = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
SKELETON_SHA256 = {
    "body_anim_skel.ask": "f541c0718c3346846ac8653d2d01773d723ff42113e50409be6b0e7b866c6ed2",
    "body_render_skel.ask": "7c4279fbbc20e16df86290a18a069c8c0ada81b03ed1dd262e2a0f4cbc761c0b",
    "body_skel.frig": "52a57782e6be065a5a3b6ed251bdcf28f6a0068557a65d8934df5fc101574e49",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def select_motions(data: bytes) -> dict[str, bytes]:
    """Validate the complete MTAR table, then select full 64-bit identities."""
    requested = {key: name for name, key in CLIP_KEYS.items()}
    metadata = inspect_mtar(data, requested)
    found = {}
    count = struct.unpack_from("<I", data, 4)[0]
    for i in range(count):
        key, offset, size = struct.unpack_from("<QII", data, 32 + 16 * i)
        name = requested.get(key)
        if name in metadata:
            found[name] = data[offset:offset + size]
    return found


def read_bank(cpk: Path) -> tuple[dict[str, bytes], dict[str, bytes], dict]:
    index, base = index_cpk(cpk)

    def read(name: str) -> bytes:
        row = index.get(name)
        if row is None or not 0 < int(row["FileSize"]) <= MEMBER_LIMIT:
            raise ValueError("missing or oversized PES21 member: " + name)
        data = unpack_wesys(cpk_member(cpk, index, base, name))
        if not 0 < len(data) <= MEMBER_LIMIT:
            raise ValueError("decoded PES21 member outside size limit")
        return data

    skeletons = {}
    for name, expected in SKELETON_SHA256.items():
        data = read(BODY + "CharacterAssets/" + name)
        if digest(data) != expected:
            raise ValueError("unsupported PES21 skeleton/rig profile: " + name)
        skeletons[name] = data
    motions, metadata, archives = {}, {}, {}
    for number in range(10):
        name = f"body_anime_file{number}.mtar"
        data = read(BODY + name)
        archives[name] = {"bytes": len(data), "sha256": digest(data)}
        for motion, payload in select_motions(data).items():
            if motion in motions:
                raise ValueError("motion identity duplicated across MTARs")
            motions[motion] = payload
            metadata[motion] = {"archive": name, "bytes": len(payload),
                                "sha256": digest(payload),
                                "key": f"0x{CLIP_KEYS[motion]:012x}"}
    if set(motions) != set(CLIPS):
        raise ValueError("missing PES21 referee motions")
    return skeletons, motions, {"archives": archives, "motions": metadata}


def renderer_slots(vm, bones: list[dict]) -> list[str]:
    names = []
    index = vm.alloc(4)
    for i in range(19):
        vm.uc.mem_write(index, struct.pack("<I", i))
        result = vm.call("_ZN4draw8GetBonesERKi", index)
        address = struct.unpack("<Q", vm.read(result, 8))[0]
        names.append(vm.read(address, 64).split(b"\0", 1)[0].decode("ascii"))
    if len(set(names)) != 19 or not set(names) <= {bone["name"] for bone in bones}:
        raise ValueError("native renderer bone map mismatch")
    if names[0] != "dsk_hip" or "sk_root_hip" in names:
        raise ValueError("native renderer pelvis slot mismatch")
    return names


def native_pose(bones: list[dict], slots: list[str], conversions, q, p):
    """Keep solved native world poses and measure their skeletal consistency."""
    count = len(bones)
    if len(q) != count or len(p) != count or len(conversions) != count:
        raise ValueError("decoded pose size mismatch")
    by_name = {bone["name"]: i for i, bone in enumerate(bones)}
    if len(by_name) != count or len(set(slots)) != len(slots) or not set(slots) <= by_name.keys():
        raise ValueError("invalid renderer slot names")
    rotations = [normalized(rotation) for rotation in q]
    if any(len(position) < 3 or any(not math.isfinite(value) or abs(value) > 4
                                    for value in position[:3]) for position in p):
        raise ValueError("decoded native position outside bounds")
    positions = [(position[0] - p[0][0], position[1], position[2] - p[0][2])
                 for position in p]
    max_length_error = max_fk_error = 0.0
    for i, bone in enumerate(bones):
        parent = bone["parent"]
        if parent < 0:
            continue
        offset = rotate(rotations[parent], bone["pos"])
        expected = tuple(positions[parent][axis] + offset[axis] for axis in range(3))
        max_fk_error = max(max_fk_error, math.dist(positions[i], expected))
        max_length_error = max(max_length_error, abs(math.dist(positions[i], positions[parent]) -
                                                     math.sqrt(sum(v * v for v in bone["pos"]))))
    # This is a consistency guard, not a pose repair. Preserve the decoder's IK;
    # never reconstruct limbs to hide a decoder or skeleton mapping mismatch.
    if max_length_error > .002 or max_fk_error > .002:
        raise ValueError("decoded native pose violates skeletal consistency")
    pose = [(render_rotation(rotations[by_name[name]], conversions[by_name[name]]),
             positions[by_name[name]]) for name in slots]
    return pose, {"max_bone_length_error_m": max_length_error,
                  "max_fk_residual_m": max_fk_error}


def bake_motion(samples, bones, slots, conversions, loop: bool):
    frames, maximum = [], {"max_bone_length_error_m": 0.0, "max_fk_residual_m": 0.0}
    for q, p in samples:
        pose, metrics = native_pose(bones, slots, conversions, q, p)
        frames.append(pose)
        for key, value in metrics.items():
            maximum[key] = max(maximum[key], value)
    phase = 0
    if loop:
        left, right = slots.index("sk_foot_l"), slots.index("sk_foot_r")
        phase = max(range(len(frames)),
                    key=lambda i: frames[i][left][1][2] - frames[i][right][1][2])
        frames = frames[phase:] + frames[:phase]
    maximum.update(phase_shift=phase, frames=len(frames))
    maximum["max_adjacent_bone_displacement_m"] = max(
        math.dist(first[bone][1], second[bone][1])
        for first, second in zip(frames, frames[1:]) for bone in range(len(slots)))
    maximum["max_loop_bone_displacement_m"] = max(
        math.dist(frames[-1][bone][1], frames[0][bone][1]) for bone in range(len(slots)))
    return frames, maximum


def root_motion_metrics(samples, rate=30.0) -> dict:
    positions = [sample[1][0] for sample in samples]
    horizontal = [(position[0], position[2]) for position in positions]
    length = sum(math.dist(first, second) for first, second in zip(horizontal, horizontal[1:]))
    net = math.dist(horizontal[0], horizontal[-1])
    duration = (len(samples) - 1) / rate
    return {"root_horizontal_path_m": length, "root_horizontal_net_m": net,
            "root_net_speed_mps": net / duration,
            "root_path_speed_mps": length / duration, "duration_s": duration}


def whistle_contact(samples, bones, rate=30.0) -> dict:
    lookup = {bone["name"]: i for i, bone in enumerate(bones)}
    left, head = lookup["sk_hand_l"], lookup["sk_head"]
    distances = [math.dist(sample[1][left][:3], sample[1][head][:3]) for sample in samples]
    nearest = min(range(len(distances)), key=distances.__getitem__)
    threshold = min(distances) + max(.015, (max(distances) - min(distances)) * .12)
    begin = end = nearest
    while begin > 0 and distances[begin - 1] <= threshold:
        begin -= 1
    while end + 1 < len(distances) and distances[end + 1] <= threshold:
        end += 1
    return {"contact_begin_s": begin / rate, "contact_end_s": end / rate,
            "nearest_frame": nearest, "nearest_time_s": nearest / rate,
            "min_wrist_head_distance_m": min(distances),
            "max_wrist_head_distance_m": max(distances),
            "contact_threshold_m": threshold,
            "measurement": "contiguous left-wrist/head nearest plateau; min+max(15mm,12%range)"}


def encode_bank(clips, speeds, contact) -> bytes:
    if len(clips) != 8:
        raise ValueError("expected eight ordered PES21 referee clips")
    if (len(speeds) != 8 or speeds[0] != 0 or any(speed != 0 for speed in speeds[4:]) or
            any(not math.isfinite(speed) or not 0 <= speed <= 12 for speed in speeds) or
            any(speeds[i] - speeds[i - 1] < .1 for i in range(1, 4))):
        raise ValueError("invalid native locomotion speed knots")
    begin, end = contact
    if not math.isfinite(begin) or not math.isfinite(end) or not 0 <= begin <= end < (len(clips[4]) - 1) / 30:
        raise ValueError("invalid native whistle contact range")
    index, payload = bytearray(), bytearray()
    offset = HEADER.size + ENTRY.size * 8
    for number, (clip, speed) in enumerate(zip(clips, speeds)):
        if not 2 <= len(clip) <= 600:
            raise ValueError("invalid native clip frame count")
        row = bytearray(ENTRY.pack(len(clip), offset, 30.0, speed, 0, 0, 0, 0))
        if number == 4:
            struct.pack_into("<ff", row, 16, begin, end)
        index += row
        for frame in clip:
            if len(frame) != 19:
                raise ValueError("expected nineteen renderer slots")
            for q, p in frame:
                if len(q) != 4 or len(p) != 3 or any(not math.isfinite(v) or abs(v) > 4 for v in p):
                    raise ValueError("invalid native renderer pose")
                payload += POSE.pack(*normalized(q), *p, 1.0)
        offset += len(clip) * 19 * POSE.size
    content = index + payload
    result = HEADER.pack(MAGIC, 4, 8, 19, ENTRY.size, checksum(content)) + content
    if len(result) > 512 * 1024:
        raise ValueError("native clip bank exceeds runtime limit")
    return result


def convert(cpk: Path, native_lib: Path, output: Path) -> dict:
    if file_digest(native_lib) != NATIVE_ELF_SHA256:
        raise ValueError("unsupported Mobile decoder ELF identity")
    skeletons, motions, inputs = read_bank(cpk)
    try:
        from .native_animation_bake import NativeAnimationVM
    except ImportError:
        from native_animation_bake import NativeAnimationVM
    vm = NativeAnimationVM(native_lib)
    sampler = Sampler(vm, skeletons["body_anim_skel.ask"], skeletons["body_skel.frig"])
    if len(sampler.bones) != 20:
        raise ValueError("expected native PES21 twenty-bone profile")
    slots = renderer_slots(vm, sampler.bones)
    conversions = render_rotations(skeletons["body_render_skel.ask"], sampler.bones)
    clips, reports, contact_metrics = [], [], None
    for name in CLIPS:
        samples = sampler.sample(motions[name])
        frames, metrics = bake_motion(samples, sampler.bones, slots, conversions, name in CLIPS[1:4])
        metrics.update(root_motion_metrics(samples))
        if name == CLIPS[4]:
            contact_metrics = whistle_contact(samples, sampler.bones)
        clips.append(frames)
        reports.append({"name": name, **inputs["motions"][name], **metrics})
        print(f"{name}: {len(frames)} native frames decoded", flush=True)
    # Root curves are not always present in GANI (some use in-place locomotion).
    # Infer speed only when every curve is directional and increases with gait.
    root_speeds = [reports[i]["root_net_speed_mps"] for i in range(1, 4)]
    reliable = (all(.1 < speed <= 12 for speed in root_speeds) and
                all(root_speeds[i] - root_speeds[i - 1] >= .1 for i in range(1, 3)) and
                all(reports[i]["root_horizontal_net_m"] >= .95 * reports[i]["root_horizontal_path_m"]
                    for i in range(1, 4)))
    speeds = (0, *root_speeds, 0, 0, 0, 0) if reliable else SPEEDS
    contact = (contact_metrics["contact_begin_s"], contact_metrics["contact_end_s"])
    encoded = encode_bank(clips, speeds, contact)
    # Re-evaluate every source frame, including native rig state, to catch any
    # state-dependent first-clip or last-clip contamination before publishing.
    repeated = []
    for name in CLIPS:
        frames, _ = bake_motion(sampler.sample(motions[name]), sampler.bones, slots,
                                conversions, name in CLIPS[1:4])
        repeated.append(frames)
    if encode_bank(repeated, speeds, contact) != encoded:
        raise ValueError("native decoder rebake was not byte deterministic")
    report = {"schema_version": 1, "bytes": len(encoded), "sha256": digest(encoded),
              "source": str(cpk.resolve()), "source_cpk_sha256": file_digest(cpk),
              "native_elf_sha256": NATIVE_ELF_SHA256, "skeletons": SKELETON_SHA256,
              "archives": inputs["archives"], "clips": reports, "bank_version": 4,
              "speed_knots_mps": speeds,
              "speed_knots_source": "decoded native root travel" if reliable else "existing bounded follower knots; native root curves are not reliable speed evidence",
              "whistle_contact": contact_metrics,
              "source_bones": 20, "renderer_slots": slots, "full_clip_decode": True,
              "sampled_pose_count": sum(row["frames"] for row in reports),
              "repeat_full_decode_byte_identical": True,
              "rotation_space": "native PES21 world rotation multiplied by render bind rotation",
              "position_space": "native solved world positions minus horizontal root travel",
              "retargeted": False, "hardware_tested": False,
              "limitations": ["Offline motion evaluation does not port PC referee AI.",
                              "Rendering, runtime event integration and performance need device testing."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(output)
    output.with_suffix(".local.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpk", type=Path, required=True)
    parser.add_argument("--native-lib", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = convert(args.cpk, args.native_lib, args.output)
    print(json.dumps({"bytes": report["bytes"], "sha256": report["sha256"],
                      "sampled_pose_count": report["sampled_pose_count"],
                      "report": str(args.output.with_suffix(".local.json"))}, indent=2))


if __name__ == "__main__":
    main()
