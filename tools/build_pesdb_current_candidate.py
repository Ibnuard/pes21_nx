#!/usr/bin/env python3
"""Package a detachable PESDB-current candidate from the stable release OBB.

Only Player.bin and PlayerAssignment.bin are replaced inside the stable dt200.
All other dt200 members and all other outer OBB members must remain byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_inter_miami_release_experiment import (
    cpk_index,
    decode_wesys_bytes,
    encode_wesys_compact,
    validate_rebuilt_cpk,
)
from pesdb import decode_wesys
from patch_cpk_slots import patch_slots


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_DT200 = Path(
    "local-debug/pesdb-current-package-audit/pes21_nx-dt200.cpk"
)
DEFAULT_BASE_OBB = Path("dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb")
DEFAULT_PLAYER = Path(
    "local-debug/pesdb-efootball-stable-3231-authoritative-patch/Player.bin"
)
DEFAULT_PLAYER_REPORT = Path(
    "local-debug/pesdb-efootball-stable-3231-authoritative-patch/coverage-report.json"
)
DEFAULT_ASSIGNMENT = Path(
    "local-debug/pes21-membership-cleanup-pesdb-stable-54/PlayerAssignment.bin"
)
DEFAULT_CLEANUP_REPORT = Path(
    "local-debug/pes21-membership-cleanup-pesdb-stable-54/cleanup-report.json"
)
DEFAULT_OUTPUT = Path("dist/pes21_nx/pesdb_current_candidate")
DT200_MEMBER = "Expansion/dt200_mobile_all.cpk"
PLAYER_MEMBER = "common/etc/pesdb/Player.bin"
ASSIGNMENT_MEMBER = "common/etc/pesdb/PlayerAssignment.bin"
PLAYER_ROW_SIZE = 312
ASSIGNMENT_ROW_SIZE = 16


def resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def member_payload(path: Path, member: str) -> bytes:
    _header, rows, data_base = cpk_index(path)
    row = rows.get(member)
    if row is None:
        raise RuntimeError(f"{path}: missing CPK member {member}")
    with path.open("rb") as source:
        source.seek(data_base + int(row["FileOffset"]))
        payload = source.read(int(row["FileSize"]))
    if len(payload) != int(row["FileSize"]):
        raise RuntimeError(f"{path}: truncated CPK member {member}")
    return payload


def validate_inputs(
    base_dt200: Path,
    base_obb: Path,
    player: Path,
    player_report: Path,
    assignment: Path,
    cleanup_report: Path,
) -> dict[str, Any]:
    base_dt200_payload = member_payload(base_obb, DT200_MEMBER)
    if sha256_bytes(base_dt200_payload) != sha256_file(base_dt200):
        raise RuntimeError("the extracted dt200 does not match the stable release OBB")

    player_meta = load_json(player_report)
    if (
        player_meta.get("authority") != "https://pesdb.net/efootball"
        or player_meta.get("pesdb_only") is not True
        or player_meta.get("coverage") != 1.0
        or player_meta.get("skipped") != 0
    ):
        raise RuntimeError("Player.bin report is not a complete PESDB-only release input")
    if player_meta.get("output_player_sha256") != sha256_file(player):
        raise RuntimeError("Player.bin differs from its PESDB coverage report")

    cleanup_meta = load_json(cleanup_report)
    if (
        cleanup_meta.get("pesdb_only") is not True
        or cleanup_meta.get("unresolved_pesdb_memberships") != 0
        or not cleanup_meta.get("preserved_national_memberships")
    ):
        raise RuntimeError("membership cleanup report does not pass release gates")
    output_hashes = cleanup_meta.get("output_sha256", {})
    if output_hashes.get("player_assignment_bin") != sha256_file(assignment):
        raise RuntimeError("PlayerAssignment.bin differs from its cleanup report")

    base_player_raw = decode_wesys_bytes(
        member_payload(base_dt200, PLAYER_MEMBER), "stable dt200 Player.bin"
    )
    player_raw = decode_wesys(player)
    if len(base_player_raw) != len(player_raw) or len(player_raw) % PLAYER_ROW_SIZE:
        raise RuntimeError("Player.bin row layout/count changed")
    base_ids = {
        struct.unpack_from("<I", base_player_raw, offset + 8)[0]
        for offset in range(0, len(base_player_raw), PLAYER_ROW_SIZE)
    }
    candidate_ids = {
        struct.unpack_from("<I", player_raw, offset + 8)[0]
        for offset in range(0, len(player_raw), PLAYER_ROW_SIZE)
    }
    if base_ids != candidate_ids or len(candidate_ids) * PLAYER_ROW_SIZE != len(player_raw):
        raise RuntimeError("Player.bin physical IDs changed or contain duplicates")

    assignment_raw = decode_wesys(assignment)
    if len(assignment_raw) % ASSIGNMENT_ROW_SIZE:
        raise RuntimeError("PlayerAssignment.bin contains a partial row")
    assignment_ids = [
        struct.unpack_from("<I", assignment_raw, offset)[0]
        for offset in range(0, len(assignment_raw), ASSIGNMENT_ROW_SIZE)
    ]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise RuntimeError("PlayerAssignment.bin contains duplicate assignment IDs")

    return {
        "base_obb_sha256": sha256_file(base_obb),
        "base_dt200_sha256": sha256_file(base_dt200),
        "player_report_content_id": player_meta.get("content_id"),
        "cleanup_report_content_id": cleanup_meta.get("content_id"),
        "player_rows": len(candidate_ids),
        "assignment_rows": len(assignment_ids),
        "pesdb_players_applied": int(player_meta.get("applied", 0)),
        "legacy_memberships_removed": int(
            cleanup_meta.get("removed_memberships", 0)
        ),
    }


def validate_outer_obb(base: Path, candidate: Path, dt200: Path) -> dict[str, Any]:
    _old_header, old_rows, old_base = cpk_index(base)
    _new_header, new_rows, new_base = cpk_index(candidate)
    if set(old_rows) != set(new_rows):
        raise RuntimeError("candidate OBB changed the outer member set")

    expected_dt200 = sha256_file(dt200)
    changed: list[str] = []
    unchanged = 0
    with base.open("rb") as old, candidate.open("rb") as new:
        for name, old_row in old_rows.items():
            new_row = new_rows[name]
            if name != DT200_MEMBER and new_row != old_row:
                raise RuntimeError(f"unrelated OBB metadata changed: {name}")
            old.seek(old_base + int(old_row["FileOffset"]))
            old_payload = old.read(int(old_row["FileSize"]))
            new.seek(new_base + int(new_row["FileOffset"]))
            new_payload = new.read(int(new_row["FileSize"]))
            if name == DT200_MEMBER:
                if sha256_bytes(new_payload) != expected_dt200:
                    raise RuntimeError("candidate OBB dt200 payload mismatch")
                if old_payload != new_payload:
                    changed.append(name)
            elif old_payload != new_payload:
                raise RuntimeError(f"unrelated OBB payload changed: {name}")
            else:
                unchanged += 1
    if changed != [DT200_MEMBER]:
        raise RuntimeError(f"unexpected outer OBB change set: {changed}")
    if candidate.stat().st_size != base.stat().st_size:
        raise RuntimeError("candidate OBB size changed")
    return {
        "path": str(candidate),
        "size": candidate.stat().st_size,
        "sha256": sha256_file(candidate),
        "member_count": len(new_rows),
        "changed_members": changed,
        "unrelated_members_byte_identical": unchanged,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    base_dt200 = resolve(args.base_dt200)
    base_obb = resolve(args.base_obb)
    player = resolve(args.player)
    player_report = resolve(args.player_report)
    assignment = resolve(args.assignment)
    cleanup_report = resolve(args.cleanup_report)
    output = resolve(args.output_dir)
    expected_inputs = [
        base_dt200,
        base_obb,
        player,
        player_report,
        assignment,
        cleanup_report,
    ]
    for path in expected_inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() and any(output.iterdir()) and not args.force:
        raise RuntimeError(f"refusing to overwrite non-empty candidate directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    inputs = validate_inputs(
        base_dt200,
        base_obb,
        player,
        player_report,
        assignment,
        cleanup_report,
    )
    compact_player = output / "Player.bin"
    compact_assignment = output / "PlayerAssignment.bin"
    compact_player.write_bytes(encode_wesys_compact(decode_wesys(player)))
    compact_assignment.write_bytes(encode_wesys_compact(decode_wesys(assignment)))

    replacement_manifest = output / "dt200-replacement-manifest.json"
    replacement_manifest.write_text(
        json.dumps(
            {
                PLAYER_MEMBER: compact_player.name,
                ASSIGNMENT_MEMBER: compact_assignment.name,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    candidate_dt200 = output / "dt200_mobile_all_pesdb_current.cpk"
    candidate_obb = output / base_obb.name
    for path in (candidate_dt200, candidate_obb):
        if path.exists():
            if not args.force:
                raise RuntimeError(f"refusing to overwrite {path}")
            path.unlink()

    _header, base_rows, _data_base = cpk_index(base_dt200)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(base_dt200),
            str(candidate_dt200),
            "--expect-members",
            str(len(base_rows)),
            "--replace-manifest",
            str(replacement_manifest),
        ],
        check=True,
    )
    dt200_validation = validate_rebuilt_cpk(
        base_dt200,
        candidate_dt200,
        expected_member_count=len(base_rows),
        expected_changed=(PLAYER_MEMBER, ASSIGNMENT_MEMBER),
    )
    patch_slots(base_obb, candidate_obb, {DT200_MEMBER: candidate_dt200})
    obb_validation = validate_outer_obb(base_obb, candidate_obb, candidate_dt200)

    result = {
        "schema_version": 1,
        "candidate": "pesdb_efootball_current_stable_base",
        "authority": "https://pesdb.net/efootball",
        "policy": {
            "pesdb_player_values_only": True,
            "pesdb_rosters_only": True,
            "pes21_used_for": ["binary_schema", "physical_slot_inventory"],
            "stable_release_overwritten": False,
        },
        "inputs": inputs,
        "replacement_sha256": {
            PLAYER_MEMBER: sha256_file(compact_player),
            ASSIGNMENT_MEMBER: sha256_file(compact_assignment),
        },
        "outputs": {"dt200": dt200_validation, "obb": obb_validation},
    }
    manifest = output / "candidate-manifest.json"
    manifest.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dt200", type=Path, default=DEFAULT_BASE_DT200)
    parser.add_argument("--base-obb", type=Path, default=DEFAULT_BASE_OBB)
    parser.add_argument("--player", type=Path, default=DEFAULT_PLAYER)
    parser.add_argument("--player-report", type=Path, default=DEFAULT_PLAYER_REPORT)
    parser.add_argument("--assignment", type=Path, default=DEFAULT_ASSIGNMENT)
    parser.add_argument("--cleanup-report", type=Path, default=DEFAULT_CLEANUP_REPORT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    result = build(parser.parse_args())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
