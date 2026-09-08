#!/usr/bin/env python3
"""Build a detached FC Barcelona + Real Madrid mobile licensing canary."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any

from add_cpk_members_canary import rebuild as add_cpk_members
from build_eng_spa_license_pack import (
    encode_wesys,
    load_manifest as load_license_manifest,
    patch_team_rows,
)
from build_real_madrid_mobile_kit_canary import (
    convert_back,
    convert_body,
    image_png_bytes,
    index_cpk,
    output_metadata,
    sha256_bytes,
    source_indexes,
    validate_texture,
    verify_layout_masks,
    winning_member,
)
from pesdb import KEY_CONSTANTS, MASK32


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("data/barca_real_madrid_mobile_kit_canary.json")
DEFAULT_OUTPUT = Path("local-debug/barca-madrid-license-canary/generated-v6")
DEFAULT_PC_EDIT_REFERENCE = Path(
    "local-debug/real-madrid-mobile-kit-canary/pc-edit-reference"
)
DEFAULT_MOBILE_EDIT_REFERENCE = Path(
    "local-debug/real-madrid-mobile-kit-canary/mobile-edit-reference"
)


def resolve(root: Path, value: Path | str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def member_name(row: dict[str, Any]) -> str:
    return "/".join(
        str(part)
        for part in (row.get("DirName") or "", row.get("FileName") or "")
        if part and part != "<NULL>"
    ).replace("\\", "/")


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported canary schema")
    if payload.get("experiment") != "barcelona_real_madrid_pc_to_pes21_mobile_kit":
        raise ValueError(f"{path}: unexpected experiment")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("policy is required")
    required_policy = {
        "runtime_integration": False,
        "allow_anisotropic_resize": True,
        "allow_unverified_atlas_transform": False,
        "allow_cpk_member_addition": True,
        "additive_repacker_scope": "detached_canary_only",
        "converted_assets_are_runtime_ready": False,
        "stable_dist_overwrite": False,
    }
    for key, value in required_policy.items():
        if policy.get(key) != value:
            raise ValueError(f"policy.{key} must remain {value!r}")

    transform = payload.get("atlas_transform")
    if not isinstance(transform, dict):
        raise ValueError("atlas_transform is required")
    if transform.get("status") != "verified_same_part_layout":
        raise ValueError("atlas layout must be verified")
    if transform.get("source_size") != [2048, 2048]:
        raise ValueError("source atlas must be 2048x2048")
    if transform.get("target_size") != [256, 384]:
        raise ValueError("mobile atlas must be 256x384")
    if transform.get("crop") is not None or transform.get("part_reordering") is not False:
        raise ValueError("the verified transform may not crop or reorder parts")

    licensing = payload.get("licensing")
    if not isinstance(licensing, dict) or licensing.get("team_source_policy") != "extract_from_selected_dt200":
        raise ValueError("Team.bin must be extracted from the selected dt200 canary")

    teams = payload.get("teams")
    if not isinstance(teams, list) or [int(row.get("team_id", 0)) for row in teams] != [108, 109]:
        raise ValueError("canary team order must be Barcelona 108 then Real Madrid 109")
    expected = {
        108: ("FC Barcelona", "BAR", "u0108", 15, 15),
        109: ("Real Madrid CF", "RMA", "u0109", 4, 15),
    }
    for team in teams:
        team_id = int(team["team_id"])
        observed = (
            team.get("official_name"),
            team.get("short_code"),
            team.get("texture_prefix"),
            int(team.get("license_flag_before", -1)),
            int(team.get("license_flag_after", -1)),
        )
        if observed != expected[team_id]:
            raise ValueError(f"team {team_id}: identity/license contract drifted")
        kits = team.get("kits")
        if not isinstance(kits, list) or [kit.get("suffix") for kit in kits] != ["p1", "p2", "g1"]:
            raise ValueError(f"team {team_id}: expected home, away, and goalkeeper kits")
        if [kit.get("kind") for kit in kits] != ["1st", "2nd", "GK1st"]:
            raise ValueError(f"team {team_id}: descriptor kinds are invalid")
        for kit in kits:
            descriptor = kit.get("descriptor")
            if not isinstance(descriptor, dict) or descriptor.get("size") != 120:
                raise ValueError(f"team {team_id} {kit['suffix']}: invalid descriptor")
            for role in ("body", "back"):
                source = kit.get(role)
                if not isinstance(source, dict):
                    raise ValueError(f"team {team_id} {kit['suffix']}: missing {role}")
                for key in ("width", "height", "pixel_format", "mip_count", "sha256"):
                    if key not in source:
                        raise ValueError(f"team {team_id} {kit['suffix']} {role}: missing {key}")
    return payload


def target_members(manifest: dict[str, Any], team: dict[str, Any], kit: dict[str, Any]) -> dict[str, str]:
    mobile = manifest["pes21_mobile"]
    values = {
        "prefix": str(team["texture_prefix"]),
        "suffix": str(kit["suffix"]),
        "team_id": int(team["team_id"]),
        "kind": str(kit["kind"]),
    }
    return {
        "body": str(mobile["body_member_template"]).format(**values),
        "back": str(mobile["back_member_template"]).format(**values),
        "descriptor": str(mobile["descriptor_member_template"]).format(**values),
    }


def source_members(manifest: dict[str, Any], team: dict[str, Any], kit: dict[str, Any]) -> dict[str, str]:
    prefix = f"{team['texture_prefix']}{kit['suffix']}"
    texture_root = str(manifest["football_life"]["texture_root"])
    team_id = int(team["team_id"])
    kind = str(kit["kind"])
    return {
        "body": f"{texture_root}{prefix}.ftex",
        "back": f"{texture_root}{prefix}_back.ftex",
        "descriptor": (
            "common/character0/model/character/uniform/team/"
            f"{team_id}/{team_id}_DEF_{kind}_realUni.bin"
        ),
    }


def descriptor_texture_names(payload: bytes) -> list[str]:
    if len(payload) != 120:
        raise ValueError("real-uniform descriptor must be 120 bytes")
    names = []
    for offset in (40, 56, 88, 104):
        names.append(payload[offset : offset + 16].split(b"\0", 1)[0].decode("ascii"))
    return names


def decode_wesys_payload(payload: bytes, label: str) -> tuple[bytes, str]:
    """Decode a WESYS CPK member without materializing a temporary file."""
    if len(payload) < 16 or payload[3:8] != b"WESYS":
        return payload, "raw"
    compressed_size, raw_size = struct.unpack_from("<II", payload, 8)
    compressed = bytearray(payload[16 : 16 + compressed_size])
    if len(compressed) != compressed_size:
        raise ValueError(f"{label}: truncated WESYS payload")
    key_index = payload[1] & 0x0F
    if key_index in KEY_CONSTANTS:
        x, y, z = KEY_CONSTANTS[key_index]
        w = ((raw_size << 16) | compressed_size) & MASK32
        for offset in range(0, len(compressed) - 3, 4):
            t = (x ^ (x << 11)) & MASK32
            x, y, z, previous = y, z, w, w
            w = (previous ^ (((previous >> 11) ^ t) >> 8) ^ t) & MASK32
            word = struct.unpack_from("<I", compressed, offset)[0] ^ w
            struct.pack_into("<I", compressed, offset, word)
    raw = zlib.decompress(compressed)
    if len(raw) != raw_size:
        raise ValueError(f"{label}: decoded {len(raw)} bytes, expected {raw_size}")
    return raw, "wesys"


def build_licensed_team_payload(
    root: Path, manifest: dict[str, Any], dt200: Path
) -> tuple[bytes, dict[str, Any]]:
    licensing = manifest["licensing"]
    license_manifest_path = resolve(root, licensing["manifest"])
    license_manifest, all_license_teams = load_license_manifest(license_manifest_path)
    canary_ids = {int(team["team_id"]) for team in manifest["teams"]}
    license_teams = [
        team for team in all_license_teams if int(team["team_id"]) in canary_ids
    ]
    if {int(team["team_id"]) for team in license_teams} != canary_ids:
        raise ValueError("licensing manifest is missing a canary team")
    team_member = str(manifest["pes21_mobile"]["team_member"])
    source_index = index_cpk(dt200, "selected-dt200", 0)
    source_payload = read_indexed(source_index, team_member)
    raw, encoding = decode_wesys_payload(source_payload, team_member)
    patched, patch_report = patch_team_rows(raw, license_teams)

    record_size = int(licensing["team_record_size"])
    id_offset = int(licensing["team_id_offset"])
    flag_offset = int(licensing["license_flag_offset"])
    rows = [
        bytearray(patched[offset : offset + record_size])
        for offset in range(0, len(patched), record_size)
    ]
    by_id = {
        struct.unpack_from("<I", row, id_offset)[0]: row for row in rows
    }
    if len(by_id) != len(rows):
        raise ValueError("Team.bin contains duplicate IDs")
    flag_changes = []
    for team in manifest["teams"]:
        team_id = int(team["team_id"])
        row = by_id.get(team_id)
        if row is None:
            raise ValueError(f"Team.bin is missing canary team {team_id}")
        before = row[flag_offset]
        expected_before = int(team["license_flag_before"])
        after = int(team["license_flag_after"])
        if before != expected_before:
            raise ValueError(
                f"team {team_id}: expected license flag {expected_before}, found {before}"
            )
        row[flag_offset] = after
        flag_changes.append(
            {
                "team_id": team_id,
                "offset": flag_offset,
                "before": before,
                "after": after,
            }
        )
    patched = b"".join(bytes(row) for row in rows)
    return encode_wesys(patched), {
        "source": str(dt200),
        "source_member": team_member,
        "source_sha256": sha256_file(dt200),
        "source_encoding": encoding,
        "license_manifest": str(license_manifest_path),
        "license_manifest_content_id": license_manifest["content_id"],
        "team_patch": patch_report,
        "license_flag_changes": flag_changes,
        "decoded_sha256": sha256_bytes(patched),
    }


def write_or_check(path: Path, payload: bytes, check: bool) -> None:
    if check:
        if not path.is_file():
            raise FileNotFoundError(f"generated artifact is missing: {path}")
        if path.read_bytes() != payload:
            raise RuntimeError(f"generated artifact is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_payloads(
    output: Path, payloads: dict[str, bytes], check: bool
) -> dict[str, dict[str, Any]]:
    result = {}
    for relative, payload in sorted(payloads.items()):
        path = output / relative
        write_or_check(path, payload, check)
        result[relative] = {
            "size": len(payload),
            "sha256": sha256_bytes(payload),
        }
        if relative.endswith(".png"):
            result[relative].update(output_metadata(payload))
    return result


def cpk_inventory(path: Path) -> dict[str, dict[str, Any]]:
    source = index_cpk(path, path.stem, 0)
    return {
        name: entry["row"] for name, entry in (
            (entry["name"], entry) for entry in source["rows"].values()
        )
    }


def replacement_manifest(
    output: Path, payload_paths: dict[str, str], actions: dict[str, str], action: str
) -> Path:
    selected = {
        member: payload_paths[member]
        for member, observed in actions.items()
        if observed == action
    }
    path = output / f"{action}-manifest.json"
    path.write_bytes(json_bytes(selected))
    return path


def validate_cpk(
    base: Path,
    candidate: Path,
    expected_actions: dict[str, str],
    payloads_by_member: dict[str, bytes],
) -> dict[str, Any]:
    old_source = index_cpk(base, "old", 0)
    new_source = index_cpk(candidate, "new", 0)
    old_names = {entry["name"] for entry in old_source["rows"].values()}
    new_names = {entry["name"] for entry in new_source["rows"].values()}
    additions = {name for name, action in expected_actions.items() if action == "add"}
    if new_names != old_names | additions:
        raise RuntimeError("candidate CPK member set differs from the approved plan")

    changed = []
    unchanged = 0
    for name in sorted(new_names):
        new_payload = read_indexed(new_source, name)
        if name in payloads_by_member:
            if new_payload != payloads_by_member[name]:
                raise RuntimeError(f"candidate payload mismatch: {name}")
            changed.append(name)
        else:
            old_payload = read_indexed(old_source, name)
            if new_payload != old_payload:
                raise RuntimeError(f"unrelated CPK member changed: {name}")
            unchanged += 1
    return {
        "base": str(base),
        "candidate": str(candidate),
        "base_sha256": sha256_file(base),
        "candidate_sha256": sha256_file(candidate),
        "base_members": len(old_names),
        "candidate_members": len(new_names),
        "changed_members": changed,
        "unrelated_members_byte_identical": unchanged,
        "size": candidate.stat().st_size,
    }


def read_indexed(source: dict[str, Any], member: str) -> bytes:
    entry = source["rows"].get(member.lower())
    if entry is None:
        raise KeyError(member)
    row = entry["row"]
    if int(row["FileSize"]) != int(row["ExtractSize"]):
        raise ValueError(f"compressed CPK member is unsupported: {member}")
    with source["path"].open("rb") as stream:
        stream.seek(source["data_base"] + int(row["FileOffset"]))
        payload = stream.read(int(row["FileSize"]))
    if len(payload) != int(row["FileSize"]):
        raise ValueError(f"truncated CPK member: {member}")
    return payload


def package_cpk(
    root: Path,
    output: Path,
    label: str,
    base: Path,
    actions: dict[str, str],
    payloads_by_member: dict[str, bytes],
    payload_paths: dict[str, str],
) -> dict[str, Any]:
    replacements = {
        member: payload_paths[member]
        for member, action in actions.items()
        if action == "replace"
    }
    additions = {
        member: (output / payload_paths[member]).resolve()
        for member, action in actions.items()
        if action == "add"
    }
    replacement_path = output / f"{label}-replace-manifest.json"
    replacement_path.write_bytes(json_bytes(replacements))
    stage = output / f".{label}-replace-stage.cpk"
    candidate = output / f"{label}_barca_real_madrid_canary.cpk"
    if stage.exists() or candidate.exists():
        raise FileExistsError("refusing to overwrite an existing CPK canary")
    if replacements:
        subprocess.run(
            [
                sys.executable,
                str(root / "tools/repack_cpk_members.py"),
                str(base),
                str(stage),
                "--expect-members",
                str(len(cpk_inventory(base))),
                "--replace-manifest",
                str(replacement_path),
            ],
            cwd=root,
            check=True,
        )
    else:
        shutil.copyfile(base, stage)
    if additions:
        add_cpk_members(stage, candidate, additions)
        stage.unlink()
    else:
        stage.replace(candidate)
    return validate_cpk(base, candidate, actions, payloads_by_member)


def build(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve(ROOT, args.root)
    manifest_path = resolve(root, args.manifest)
    output = resolve(root, args.output_dir)
    manifest = load_manifest(manifest_path)
    football_life_root = (
        resolve(root, args.football_life_root)
        if args.football_life_root
        else Path(manifest["football_life"]["root"]).resolve()
    )
    indexes = source_indexes(root, manifest, football_life_root)
    dt120 = resolve(root, args.dt120 or manifest["pes21_mobile"]["dt120_source"])
    dt200 = resolve(root, args.dt200 or manifest["pes21_mobile"]["dt200_source"])
    if not dt120.is_file() or not dt200.is_file():
        raise FileNotFoundError(dt120 if not dt120.is_file() else dt200)
    for label, path in (("dt120", dt120), ("dt200", dt200)):
        expected = str(manifest["pes21_mobile"][f"{label}_source_sha256"])
        observed = sha256_file(path)
        if observed.lower() != expected.lower() and not args.allow_base_drift:
            raise ValueError(
                f"{label} base hash mismatch: {observed} != {expected}"
            )
    dt120_inventory = cpk_inventory(dt120)
    dt200_inventory = cpk_inventory(dt200)

    pc_edit = resolve(root, args.pc_edit_reference) if args.pc_edit_reference else None
    mobile_edit = resolve(root, args.mobile_edit_reference) if args.mobile_edit_reference else None
    layout_audit = verify_layout_masks(pc_edit, mobile_edit)
    if layout_audit.get("status") != "verified_same_part_layout":
        raise RuntimeError("the PC/mobile Uniform16 atlas audit is not verified")

    payloads: dict[str, bytes] = {}
    dt120_payloads: dict[str, bytes] = {}
    dt200_payloads: dict[str, bytes] = {}
    dt120_paths: dict[str, str] = {}
    dt200_paths: dict[str, str] = {}
    dt120_actions: dict[str, str] = {}
    dt200_actions: dict[str, str] = {}
    team_reports = []
    for team in manifest["teams"]:
        kit_reports = []
        for kit in team["kits"]:
            source_names = source_members(manifest, team, kit)
            targets = target_members(manifest, team, kit)
            body_raw, body_source = winning_member(indexes, source_names["body"])
            back_raw, back_source = winning_member(indexes, source_names["back"])
            descriptor, descriptor_source = winning_member(
                indexes, source_names["descriptor"]
            )
            body_image, body_meta = validate_texture(
                "body", body_raw, body_source, kit["body"], args.allow_source_drift
            )
            back_image, back_meta = validate_texture(
                "back", back_raw, back_source, kit["back"], args.allow_source_drift
            )
            expected_descriptor = kit["descriptor"]
            if len(descriptor) != int(expected_descriptor["size"]):
                raise ValueError("unexpected real-uniform descriptor size")
            if (
                sha256_bytes(descriptor).lower()
                != str(expected_descriptor["sha256"]).lower()
                and not args.allow_source_drift
            ):
                raise ValueError("real-uniform descriptor hash mismatch")
            expected_prefix = f"{team['texture_prefix']}{kit['suffix']}"
            names = descriptor_texture_names(descriptor)
            if names[0] != expected_prefix:
                raise ValueError(f"descriptor texture prefix mismatch: {names[0]}")

            body = image_png_bytes(convert_body(body_image, manifest["atlas_transform"]))
            back = image_png_bytes(convert_back(back_image, manifest["atlas_transform"]))
            body_relative = f"payloads/dt120/{Path(targets['body']).name}"
            back_relative = f"payloads/dt120/{Path(targets['back']).name}"
            descriptor_relative = (
                f"payloads/dt200/{team['team_id']}_{kit['kind']}_realUni.bin"
            )
            for member, relative, value in (
                (targets["body"], body_relative, body),
                (targets["back"], back_relative, back),
            ):
                payloads[relative] = value
                dt120_payloads[member] = value
                dt120_paths[member] = relative
                dt120_actions[member] = "replace" if member in dt120_inventory else "add"
            payloads[descriptor_relative] = descriptor
            dt200_payloads[targets["descriptor"]] = descriptor
            dt200_paths[targets["descriptor"]] = descriptor_relative
            dt200_actions[targets["descriptor"]] = (
                "replace" if targets["descriptor"] in dt200_inventory else "add"
            )
            kit_reports.append(
                {
                    "kind": kit["kind"],
                    "suffix": kit["suffix"],
                    "sources": {
                        "body": body_meta,
                        "back": back_meta,
                        "descriptor": descriptor_source,
                    },
                    "descriptor_texture_names": names,
                    "targets": {
                        "body": {
                            "member": targets["body"],
                            "action": dt120_actions[targets["body"]],
                            **output_metadata(body),
                        },
                        "back": {
                            "member": targets["back"],
                            "action": dt120_actions[targets["back"]],
                            **output_metadata(back),
                        },
                        "descriptor": {
                            "member": targets["descriptor"],
                            "action": dt200_actions[targets["descriptor"]],
                            "size": len(descriptor),
                            "sha256": sha256_bytes(descriptor),
                        },
                    },
                }
            )
        team_reports.append(
            {
                "team_id": int(team["team_id"]),
                "official_name": team["official_name"],
                "short_code": team["short_code"],
                "kits": kit_reports,
            }
        )

    team_payload, team_report = build_licensed_team_payload(root, manifest, dt200)
    team_member = str(manifest["pes21_mobile"]["team_member"])
    team_relative = "payloads/dt200/Team.bin"
    payloads[team_relative] = team_payload
    dt200_payloads[team_member] = team_payload
    dt200_paths[team_member] = team_relative
    dt200_actions[team_member] = "replace" if team_member in dt200_inventory else "add"

    generated = write_payloads(output, payloads, args.check)
    action_payloads = {
        "dt120": {
            "base": str(dt120),
            "base_sha256": sha256_file(dt120),
            "actions": dt120_actions,
            "paths": dt120_paths,
        },
        "dt200": {
            "base": str(dt200),
            "base_sha256": sha256_file(dt200),
            "actions": dt200_actions,
            "paths": dt200_paths,
        },
    }
    action_bytes = json_bytes(action_payloads)
    write_or_check(output / "cpk-actions.json", action_bytes, args.check)

    report: dict[str, Any] = {
        "schema_version": 1,
        "experiment": manifest["experiment"],
        "status": "assets_ready_for_detached_cpk_canary",
        "runtime_ready": False,
        "runtime_integration": False,
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "football_life_root": str(football_life_root),
        "layout_audit": layout_audit,
        "teams": team_reports,
        "licensing": team_report,
        "actions": {
            "dt120": {
                "replace": sum(action == "replace" for action in dt120_actions.values()),
                "add": sum(action == "add" for action in dt120_actions.values()),
            },
            "dt200": {
                "replace": sum(action == "replace" for action in dt200_actions.values()),
                "add": sum(action == "add" for action in dt200_actions.values()),
            },
        },
        "outputs": generated,
        "cpks": None,
        "safety": {
            "source_cpks_modified": False,
            "obb_modified": False,
            "runtime_source_modified": False,
            "makefile_modified": False,
            "stable_dist_modified": False,
        },
    }
    if args.package_cpks:
        if args.check:
            raise ValueError("--check and --package-cpks cannot be combined")
        report["cpks"] = {
            "dt120": package_cpk(
                root,
                output,
                "dt120",
                dt120,
                dt120_actions,
                dt120_payloads,
                dt120_paths,
            ),
            "dt200": package_cpk(
                root,
                output,
                "dt200",
                dt200,
                dt200_actions,
                dt200_payloads,
                dt200_paths,
            ),
        }
        report["status"] = "detached_cpk_canary_built"
    elif args.check:
        dt120_candidate = output / "dt120_barca_real_madrid_canary.cpk"
        dt200_candidate = output / "dt200_barca_real_madrid_canary.cpk"
        if dt120_candidate.is_file() or dt200_candidate.is_file():
            if not dt120_candidate.is_file() or not dt200_candidate.is_file():
                raise FileNotFoundError("detached CPK canary pair is incomplete")
            report["cpks"] = {
                "dt120": validate_cpk(
                    dt120,
                    dt120_candidate,
                    dt120_actions,
                    dt120_payloads,
                ),
                "dt200": validate_cpk(
                    dt200,
                    dt200_candidate,
                    dt200_actions,
                    dt200_payloads,
                ),
            }
            report["status"] = "detached_cpk_canary_built"
    report_bytes = json_bytes(report)
    write_or_check(output / "canary-report.json", report_bytes, args.check)
    result = {
        "check": "pass" if args.check else None,
        "status": report["status"],
        "output_dir": str(output),
        "teams": [108, 109],
        "kits": 6,
        "actions": report["actions"],
        "cpks": report["cpks"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--football-life-root", type=Path)
    parser.add_argument("--dt120", type=Path)
    parser.add_argument("--dt200", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--pc-edit-reference", type=Path, default=DEFAULT_PC_EDIT_REFERENCE
    )
    parser.add_argument(
        "--mobile-edit-reference", type=Path, default=DEFAULT_MOBILE_EDIT_REFERENCE
    )
    parser.add_argument("--allow-source-drift", action="store_true")
    parser.add_argument(
        "--allow-base-drift",
        action="store_true",
        help="accept an explicitly selected newer dt120/dt200 candidate base",
    )
    parser.add_argument("--package-cpks", action="store_true")
    parser.add_argument("--check", action="store_true")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
