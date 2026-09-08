#!/usr/bin/env python3
"""Build a detachable PESDB-current famous-team OBB candidate.

Player identity, club membership, shirt numbers, positions, and abilities are
accepted only from PESDB eFootball Authentic artifacts. EF10 contributes team
identity and visual assets. PES21 contributes fixed binary schemas and donor
slots only. The stable ``dist`` files are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from build_inter_miami_release_experiment import (
    cpk_index,
    decode_wesys_bytes,
    encode_wesys_compact,
    validate_rebuilt_cpk,
)
from cooked_texture import Texture
from patch_cpk_slots import patch_slots


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = "https://pesdb.net/efootball"
DEFAULT_MANIFEST = Path("data/ef10_famous_team_imports.json")
DEFAULT_CATALOG = Path("data/exhibition_team_catalog.json")
DEFAULT_ROSTERS = Path(
    "local-debug/pesdb-efootball-authentic-rosters-current-54-shirts.json"
)
DEFAULT_PLAYER = Path(
    "local-debug/pesdb-efootball-stable-3231-authoritative-patch/Player.bin"
)
DEFAULT_PLAYER_REPORT = Path(
    "local-debug/pesdb-efootball-stable-3231-authoritative-patch/coverage-report.json"
)
DEFAULT_ASSIGNMENT = Path(
    "local-debug/pes21-membership-cleanup-pesdb-all-54-balanced-v6/PlayerAssignment.bin"
)
DEFAULT_CLEANUP_REPORT = Path(
    "local-debug/pes21-membership-cleanup-pesdb-all-54-balanced-v6/cleanup-report.json"
)
DEFAULT_BASE_OBB = Path("dist/pes21_nx/patch.305030001.jp.nyan2021.pesam.obb")
DEFAULT_KIT_ROOT = Path("local-debug/famous-kit-sources")
DEFAULT_OUTPUT = Path("local-debug/pesdb-famous-teams-candidate-v6")

DT120_MEMBER = "Expansion/dt120_mobile_all.cpk"
DT200_MEMBER = "Expansion/dt200_mobile_all.cpk"
DT240_MEMBER = "Expansion/dt240_mobile_all.cpk"
PLAYER_MEMBER = "common/etc/pesdb/Player.bin"
INSTALL_VERSION_MEMBER = "common/etc/pesdb/InstallVersionPlayer.bin"
DELETE_LIST_MEMBER = "common/etc/pesdb/PlayerDeleteList.bin"
ASSIGNMENT_MEMBER = "common/etc/pesdb/PlayerAssignment.bin"
TEAM_MEMBER = "common/etc/pesdb/Team.bin"
PLAYER_ROW_SIZE = 312
PLAYER_ID_OFFSET = 8
INSTALL_VERSION_ROW_SIZE = 8
DELETE_LIST_ROW_SIZE = 4
TEAM_ROW_SIZE = 1532
TEAM_ID_OFFSET = 8
TEAM_NAME_OFFSET = 368
TEAM_NAME_SIZE = 70
TEAM_SHORT_CODE_OFFSETS = (882, 1382)
KIT_ROLES = ("p1", "p2", "g1")


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


def fixed_row_ids(raw: bytes, row_size: int, id_offset: int, label: str) -> list[int]:
    if len(raw) % row_size:
        raise ValueError(f"{label}: partial {row_size}-byte row")
    values = [
        struct.unpack_from("<I", raw, offset + id_offset)[0]
        for offset in range(0, len(raw), row_size)
    ]
    if len(values) != len(set(values)):
        raise ValueError(f"{label}: duplicate IDs")
    return values


def activate_player_ids(
    delete_raw: bytes, required_ids: set[int]
) -> tuple[bytes, dict[str, Any]]:
    deleted = fixed_row_ids(
        delete_raw, DELETE_LIST_ROW_SIZE, 0, "PlayerDeleteList.bin"
    )
    deleted_set = set(deleted)
    removed = deleted_set & required_ids
    remaining = [player_id for player_id in deleted if player_id not in required_ids]
    if set(remaining) & required_ids:
        raise RuntimeError("a PESDB target remains in PlayerDeleteList.bin")
    return b"".join(struct.pack("<I", player_id) for player_id in remaining), {
        "required_active_players": len(required_ids),
        "already_active_players": len(required_ids - deleted_set),
        "delete_rows_before": len(deleted),
        "delete_rows_removed": len(removed),
        "delete_rows_after": len(remaining),
        "remaining_required_players_deleted": 0,
    }


def content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


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


def patch_fixed_ascii(row: bytearray, offset: int, size: int, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) >= size:
        raise ValueError(f"ASCII value does not fit {size}-byte field: {value}")
    row[offset : offset + size] = encoded + bytes(size - len(encoded))


def patch_team_table(raw: bytes, teams: list[dict[str, Any]]) -> tuple[bytes, dict[str, Any]]:
    if len(raw) % TEAM_ROW_SIZE:
        raise ValueError("Team.bin has a partial PES21 row")
    rows = [bytearray(raw[offset : offset + TEAM_ROW_SIZE]) for offset in range(0, len(raw), TEAM_ROW_SIZE)]
    by_id = {
        struct.unpack_from("<I", row, TEAM_ID_OFFSET)[0]: index
        for index, row in enumerate(rows)
    }
    if len(by_id) != len(rows):
        raise ValueError("Team.bin contains duplicate IDs")
    changed: list[dict[str, Any]] = []
    for team in teams:
        physical_id = int(team["physical_team_id"])
        index = by_id.get(physical_id)
        if index is None:
            raise ValueError(f"physical team {physical_id} is absent from Team.bin")
        row = rows[index]
        before = bytes(row)
        old_name = bytes(row[TEAM_NAME_OFFSET : TEAM_NAME_OFFSET + TEAM_NAME_SIZE])
        old_name = old_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
        patch_fixed_ascii(row, TEAM_NAME_OFFSET, TEAM_NAME_SIZE, str(team["display_name"]))
        for offset in TEAM_SHORT_CODE_OFFSETS:
            patch_fixed_ascii(row, offset, 4, str(team["short_code"]))
        allowed = set(range(TEAM_NAME_OFFSET, TEAM_NAME_OFFSET + TEAM_NAME_SIZE))
        for offset in TEAM_SHORT_CODE_OFFSETS:
            allowed.update(range(offset, offset + 4))
        if any(a != b and position not in allowed for position, (a, b) in enumerate(zip(before, row))):
            raise RuntimeError(f"team {physical_id}: patch escaped approved fields")
        changed.append(
            {
                "logical_team_id": int(team["ef10_team_id"]),
                "physical_team_id": physical_id,
                "old_name": old_name,
                "new_name": str(team["display_name"]),
                "short_code": str(team["short_code"]),
            }
        )
    return b"".join(bytes(row) for row in rows), {
        "records": len(rows),
        "changed_rows": len(changed),
        "unrelated_rows_byte_identical": len(rows) - len(changed),
        "teams": changed,
    }


def image_png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def convert_body(source: Path) -> bytes:
    image = Texture(source).decode().convert("RGB")
    image = image.resize((256, 384), Image.Resampling.BICUBIC)
    image = image.quantize(
        colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    return image_png_bytes(image)


def convert_back(source: Path) -> bytes:
    image = Texture(source).decode().convert("RGBA")
    return image_png_bytes(
        image.resize((320, 40), Image.Resampling.BICUBIC)
    )


def build_kit_replacements(
    teams: list[dict[str, Any]], kit_root: Path
) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    replacements: dict[str, bytes] = {}
    report: list[dict[str, Any]] = []
    for team in teams:
        if team.get("kit_mode") != "convert_ef10_mobile":
            continue
        logical_id = int(team["ef10_team_id"])
        physical_id = int(team["physical_team_id"])
        source_prefix = str(team["kit_source_prefix"])
        target_prefix = str(team["kit_target_prefix"])
        source_root = (
            kit_root
            / f"u{logical_id:04d}"
            / "PesMobile/Content/Assets/character/Uniform/LowTextures"
        )
        for role in KIT_ROLES:
            body_source = source_root / f"T_{source_prefix}{role}_Uni_D.uexp"
            back_source = source_root / f"T_{source_prefix}{role}_FontBack_D.uexp"
            if not body_source.is_file() or not back_source.is_file():
                raise FileNotFoundError(
                    body_source if not body_source.is_file() else back_source
                )
            body_member = f"Models/character/Uniform16/D/{target_prefix}{role}.png"
            back_member = f"Models/character/Uniform16/Font/{target_prefix}{role}_back.png"
            body = convert_body(body_source)
            back = convert_back(back_source)
            replacements[body_member] = body
            replacements[back_member] = back
            report.append(
                {
                    "logical_team_id": logical_id,
                    "physical_team_id": physical_id,
                    "role": role,
                    "body_member": body_member,
                    "body_sha256": sha256_bytes(body),
                    "back_member": back_member,
                    "back_sha256": sha256_bytes(back),
                }
            )
    return replacements, report


def build_badge_replacements(
    teams: list[dict[str, Any]], base_dt240: Path
) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    _header, rows, _data_base = cpk_index(base_dt240)
    replacements: dict[str, bytes] = {}
    report: list[dict[str, Any]] = []
    for team in teams:
        logical_id = int(team["ef10_team_id"])
        physical_id = int(team["physical_team_id"])
        variant = str(team["target_badge_variant"])
        source_path = ROOT / "data" / "exhibition_badges" / f"{logical_id}.png"
        with Image.open(source_path) as source:
            badge = source.convert("RGBA")
        for suffix, size in (("", 128), ("_l", 256), ("_s", 64)):
            member = (
                f"common/render/symbol/flag/e_{physical_id:06d}_{variant}{suffix}.png"
            )
            if member not in rows:
                raise FileNotFoundError(f"dt240 target badge is missing: {member}")
            image = badge.resize((size, size), Image.Resampling.LANCZOS)
            payload = image_png_bytes(image)
            replacements[member] = payload
            report.append(
                {
                    "logical_team_id": logical_id,
                    "physical_team_id": physical_id,
                    "member": member,
                    "size": len(payload),
                    "sha256": sha256_bytes(payload),
                }
            )
    return replacements, report


def load_release_teams(
    manifest_path: Path, catalog_path: Path, roster_path: Path
) -> list[dict[str, Any]]:
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ValueError(f"{manifest_path}: unsupported schema")
    policy = manifest.get("policy", {})
    if policy.get("player_value_source") != f"{AUTHORITY} (Authentic mode)":
        raise ValueError("famous-team manifest is not locked to PESDB Authentic")
    catalog = load_json(catalog_path)
    catalog_by_id = {
        int(team["team_id"]): team for team in catalog.get("teams", [])
    }
    rosters = load_json(roster_path)
    if (
        rosters.get("source") != "authentic"
        or rosters.get("authority") != AUTHORITY
        or rosters.get("policy", {}).get("pes21_roster_or_value_fallback") is not False
    ):
        raise ValueError("release roster input must be PESDB eFootball Authentic")
    roster_teams = rosters.get("teams", {})
    result: list[dict[str, Any]] = []
    physical_ids: set[int] = set()
    for raw_team in manifest.get("teams", []):
        if not raw_team.get("release_enabled"):
            continue
        team = dict(raw_team)
        logical_id = int(team["ef10_team_id"])
        physical_id = int(team["physical_team_id"])
        if physical_id in physical_ids:
            raise ValueError(f"physical team slot reused: {physical_id}")
        physical_ids.add(physical_id)
        catalog_team = catalog_by_id.get(logical_id)
        if not catalog_team or int(catalog_team["physical_team_id"]) != physical_id:
            raise ValueError(f"catalog mapping disagrees for team {logical_id}")
        roster = roster_teams.get(str(logical_id))
        if not isinstance(roster, dict) or not roster.get("complete"):
            raise ValueError(f"team {logical_id} lacks a complete PESDB roster")
        if int(roster.get("player_count", 0)) < 18:
            raise ValueError(f"team {logical_id} PESDB roster is too small")
        result.append(team)
    if len(result) != 9:
        raise ValueError(f"expected 9 release teams, found {len(result)}")
    return result


def validate_data_inputs(
    *,
    player: Path,
    player_report: Path,
    assignment: Path,
    cleanup_report: Path,
) -> tuple[dict[str, Any], set[int]]:
    player_meta = load_json(player_report)
    if (
        player_meta.get("authority") != AUTHORITY
        or player_meta.get("pesdb_only") is not True
        or player_meta.get("coverage") != 1.0
        or int(player_meta.get("skipped", -1)) != 0
        or player_meta.get("output_player_sha256") != sha256_file(player)
    ):
        raise ValueError("Player.bin is not a complete PESDB-only artifact")
    applied_players = player_meta.get("applied_players")
    if not isinstance(applied_players, list):
        raise ValueError("Player.bin report is missing applied player rows")
    target_player_ids = {
        int(row["target_player_id"])
        for row in applied_players
        if isinstance(row, dict) and "target_player_id" in row
    }
    if len(target_player_ids) != int(player_meta["applied"]):
        raise ValueError("Player.bin report has duplicate or malformed target IDs")
    cleanup = load_json(cleanup_report)
    replacement = cleanup.get("roster_replacement", {})
    if (
        cleanup.get("pesdb_only") is not True
        or cleanup.get("unresolved_pesdb_memberships") != 0
        or cleanup.get("integrated_rosters_replaced") is not True
        or replacement.get("club_duplicate_memberships") != 0
        or replacement.get("exact_roster_order_and_shirts") is not True
        or cleanup.get("output_sha256", {}).get("player_assignment_bin")
        != sha256_file(assignment)
    ):
        raise ValueError("PlayerAssignment.bin does not pass PESDB cleanup gates")
    return {
        "player_content_id": player_meta.get("content_id"),
        "cleanup_content_id": cleanup.get("content_id"),
        "players_applied": int(player_meta["applied"]),
        "memberships_removed": int(cleanup["removed_memberships"]),
        "memberships_inserted": int(replacement["pesdb_memberships_inserted"]),
        "integrated_teams": int(replacement["integrated_teams"]),
    }, target_player_ids


def validate_player_tables(
    player_payload: bytes,
    install_payload: bytes,
    target_player_ids: set[int],
) -> dict[str, Any]:
    player_ids = set(
        fixed_row_ids(
            decode_wesys_bytes(player_payload, "candidate Player.bin"),
            PLAYER_ROW_SIZE,
            PLAYER_ID_OFFSET,
            "Player.bin",
        )
    )
    install_ids = set(
        fixed_row_ids(
            decode_wesys_bytes(install_payload, "base InstallVersionPlayer.bin"),
            INSTALL_VERSION_ROW_SIZE,
            0,
            "InstallVersionPlayer.bin",
        )
    )
    if player_ids != install_ids:
        raise ValueError("Player.bin and InstallVersionPlayer.bin ID sets differ")
    missing = target_player_ids - player_ids
    if missing:
        raise ValueError(
            "PESDB target IDs are absent from player tables: "
            f"{sorted(missing)[:20]}"
        )
    return {
        "player_records": len(player_ids),
        "install_version_records": len(install_ids),
        "player_install_id_sets_match": True,
        "target_players_present": len(target_player_ids),
    }


def write_replacements(
    output: Path, folder: str, replacements: dict[str, bytes]
) -> Path:
    root = output / folder
    root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    for index, (member, payload) in enumerate(sorted(replacements.items())):
        path = root / f"{index:03d}-{Path(member).name}"
        path.write_bytes(payload)
        manifest[member] = str(path.relative_to(output)).replace("\\", "/")
    manifest_path = output / f"{folder}-replacement-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _row_metadata_without_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Return TOC metadata that is independent of a member's packed bytes."""
    return {
        key: value
        for key, value in row.items()
        if key not in {"FileOffset", "FileSize", "ExtractSize"}
    }


def validate_outer_obb(
    base: Path,
    candidate: Path,
    replacements: dict[str, Path],
    *,
    packaging_mode: str = "fixed_slot",
) -> dict[str, Any]:
    """Validate an outer OBB while distinguishing repacked TOC offsets.

    Fixed-slot patching must preserve every unrelated TOC row byte-for-byte.
    A repack is allowed to move rows after a larger replacement, but it must
    preserve the member set, all non-payload metadata, and every unrelated
    payload byte.
    """
    if packaging_mode not in {"fixed_slot", "repacked"}:
        raise ValueError(f"unsupported outer packaging mode: {packaging_mode}")
    old_header, old_rows, old_base = cpk_index(base)
    new_header, new_rows, new_base = cpk_index(candidate)
    if set(old_rows) != set(new_rows):
        raise RuntimeError("candidate OBB changed the member set")
    if old_header != new_header:
        raise RuntimeError("candidate OBB changed the CPK header")
    expected = {member: sha256_file(path) for member, path in replacements.items()}
    changed: list[str] = []
    metadata_changed: list[str] = []
    unchanged = 0
    with base.open("rb") as old, candidate.open("rb") as new:
        for member, old_row in old_rows.items():
            new_row = new_rows[member]
            old.seek(old_base + int(old_row["FileOffset"]))
            old_payload = old.read(int(old_row["FileSize"]))
            new.seek(new_base + int(new_row["FileOffset"]))
            new_payload = new.read(int(new_row["FileSize"]))
            if member in expected:
                if sha256_bytes(new_payload) != expected[member]:
                    raise RuntimeError(f"candidate OBB replacement mismatch: {member}")
                if new_payload != old_payload:
                    changed.append(member)
            else:
                if new_payload != old_payload:
                    raise RuntimeError(f"unrelated OBB payload changed: {member}")
                unchanged += 1
            if new_row != old_row:
                metadata_changed.append(member)
                if packaging_mode == "fixed_slot" and member not in expected:
                    raise RuntimeError(f"unrelated OBB metadata changed: {member}")
                if (
                    packaging_mode == "fixed_slot"
                    and int(new_row["FileOffset"]) != int(old_row["FileOffset"])
                ):
                    raise RuntimeError(f"fixed-slot OBB member moved: {member}")
                if _row_metadata_without_payload(new_row) != _row_metadata_without_payload(old_row):
                    raise RuntimeError(f"unrelated OBB TOC metadata changed: {member}")
    if set(changed) != set(expected):
        raise RuntimeError(f"unexpected OBB change set: {changed}")
    if packaging_mode == "fixed_slot" and candidate.stat().st_size != base.stat().st_size:
        raise RuntimeError("candidate OBB size changed")
    return {
        "path": str(candidate),
        "size": candidate.stat().st_size,
        "sha256": sha256_file(candidate),
        "packaging_mode": packaging_mode,
        "base_size": base.stat().st_size,
        "size_delta": candidate.stat().st_size - base.stat().st_size,
        "changed_members": sorted(changed),
        "metadata_changed_members": sorted(metadata_changed),
        "unrelated_members_byte_identical": unchanged,
    }


def package_outer_obb(
    base: Path,
    candidate: Path,
    replacements: dict[str, Path],
) -> tuple[str, str | None]:
    """Use fixed slots when possible, then safely fall back to a CPK repack."""
    try:
        patch_slots(base, candidate, replacements)
        return "fixed_slot", None
    except ValueError as error:
        message = str(error)
        if "slot capacity" not in message:
            raise
        # patch_slots validates all capacities before creating the output, but
        # remove a partial path defensively before invoking the repacker.
        candidate.unlink(missing_ok=True)

    manifest = candidate.parent / "outer-replacement-manifest.json"
    manifest.write_text(
        json.dumps(
            {member: str(path.resolve()) for member, path in replacements.items()},
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(base),
            str(candidate),
            "--expect-members",
            str(len(cpk_index(base)[1])),
            "--replace-manifest",
            str(manifest),
        ],
        cwd=ROOT,
        check=True,
    )
    return "repacked", "slot capacity exceeded; outer CPK was repacked"


def build(args: argparse.Namespace) -> dict[str, Any]:
    manifest = resolve(args.manifest)
    catalog = resolve(args.catalog)
    rosters = resolve(args.rosters)
    player = resolve(args.player)
    player_report = resolve(args.player_report)
    assignment = resolve(args.assignment)
    cleanup_report = resolve(args.cleanup_report)
    base_obb = resolve(args.base_obb)
    kit_root = resolve(args.kit_root)
    output = resolve(args.output_dir)
    for path in (
        manifest,
        catalog,
        rosters,
        player,
        player_report,
        assignment,
        cleanup_report,
        base_obb,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    if output == (ROOT / "dist").resolve() or (ROOT / "dist").resolve() in output.parents:
        raise ValueError("candidate output must stay outside stable dist")
    base_obb_sha256 = sha256_file(base_obb)
    teams = load_release_teams(manifest, catalog, rosters)
    data_report, target_player_ids = validate_data_inputs(
        player=player,
        player_report=player_report,
        assignment=assignment,
        cleanup_report=cleanup_report,
    )
    if args.check:
        return {"check": "pass", "release_teams": len(teams), **data_report}
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty output: {output}")
    output.mkdir(parents=True, exist_ok=True)

    base_cpks: dict[str, Path] = {}
    for member in (DT120_MEMBER, DT200_MEMBER, DT240_MEMBER):
        path = output / f"base-{Path(member).name}"
        path.write_bytes(member_payload(base_obb, member))
        base_cpks[member] = path

    dt200_members = {
        member: member_payload(base_cpks[DT200_MEMBER], member)
        for member in (TEAM_MEMBER, INSTALL_VERSION_MEMBER, DELETE_LIST_MEMBER)
    }
    player_table_report = validate_player_tables(
        player.read_bytes(),
        dt200_members[INSTALL_VERSION_MEMBER],
        target_player_ids,
    )
    delete_raw = decode_wesys_bytes(
        dt200_members[DELETE_LIST_MEMBER], "base PlayerDeleteList.bin"
    )
    active_delete_raw, activation_report = activate_player_ids(
        delete_raw, target_player_ids
    )
    team_raw = decode_wesys_bytes(dt200_members[TEAM_MEMBER], "base Team.bin")
    patched_team_raw, team_report = patch_team_table(team_raw, teams)
    dt200_replacements = {
        PLAYER_MEMBER: player.read_bytes(),
        DELETE_LIST_MEMBER: encode_wesys_compact(active_delete_raw),
        ASSIGNMENT_MEMBER: assignment.read_bytes(),
        TEAM_MEMBER: encode_wesys_compact(patched_team_raw),
    }
    kit_replacements, kit_report = build_kit_replacements(teams, kit_root)
    badge_replacements, badge_report = build_badge_replacements(
        teams, base_cpks[DT240_MEMBER]
    )

    dt200_manifest = write_replacements(output, "dt200", dt200_replacements)
    dt120_manifest = write_replacements(output, "dt120", kit_replacements)
    dt240_manifest = write_replacements(output, "dt240", badge_replacements)
    candidate_cpks = {
        DT120_MEMBER: output / "dt120_mobile_all_pesdb_famous.cpk",
        DT200_MEMBER: output / "dt200_mobile_all_pesdb_famous.cpk",
        DT240_MEMBER: output / "dt240_mobile_all_pesdb_famous.cpk",
    }
    for member, replacement_manifest in (
        (DT120_MEMBER, dt120_manifest),
        (DT200_MEMBER, dt200_manifest),
        (DT240_MEMBER, dt240_manifest),
    ):
        base_cpk = base_cpks[member]
        _header, rows, _base = cpk_index(base_cpk)
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "repack_cpk_members.py"),
                str(base_cpk),
                str(candidate_cpks[member]),
                "--expect-members",
                str(len(rows)),
                "--replace-manifest",
                str(replacement_manifest),
            ],
            cwd=ROOT,
            check=True,
        )

    cpk_reports = {
        DT120_MEMBER: validate_rebuilt_cpk(
            base_cpks[DT120_MEMBER],
            candidate_cpks[DT120_MEMBER],
            expected_member_count=len(cpk_index(base_cpks[DT120_MEMBER])[1]),
            expected_changed=tuple(kit_replacements),
        ),
        DT200_MEMBER: validate_rebuilt_cpk(
            base_cpks[DT200_MEMBER],
            candidate_cpks[DT200_MEMBER],
            expected_member_count=len(cpk_index(base_cpks[DT200_MEMBER])[1]),
            expected_changed=tuple(dt200_replacements),
        ),
        DT240_MEMBER: validate_rebuilt_cpk(
            base_cpks[DT240_MEMBER],
            candidate_cpks[DT240_MEMBER],
            expected_member_count=len(cpk_index(base_cpks[DT240_MEMBER])[1]),
            expected_changed=tuple(badge_replacements),
        ),
    }

    candidate_obb = output / base_obb.name
    packaging_mode, packaging_note = package_outer_obb(
        base_obb, candidate_obb, candidate_cpks
    )
    obb_report = validate_outer_obb(
        base_obb,
        candidate_obb,
        candidate_cpks,
        packaging_mode=packaging_mode,
    )
    if packaging_note:
        obb_report["packaging_note"] = packaging_note
    if sha256_file(base_obb) != base_obb_sha256:
        raise RuntimeError("stable OBB changed during candidate build")

    result: dict[str, Any] = {
        "schema_version": 1,
        "candidate": "pesdb_efootball_famous_teams_v1",
        "authority": AUTHORITY,
        "policy": {
            "pesdb_authentic_player_data_only": True,
            "pesdb_authentic_rosters_only": True,
            "pes21_used_for": ["binary_schema", "physical_slot_inventory"],
            "ef10_used_for": ["team_identity", "badge", "kit"],
            "stable_dist_overwritten": False,
            "held_back_team_ids": [17733],
        },
        "content_id": None,
        "data": data_report,
        "player_tables": player_table_report,
        "player_activation": activation_report,
        "release_team_ids": [int(team["ef10_team_id"]) for team in teams],
        "logical_to_physical": {
            str(team["ef10_team_id"]): int(team["physical_team_id"])
            for team in teams
        },
        "team_patch": team_report,
        "kit_conversions": kit_report,
        "badge_conversions": badge_report,
        "cpks": cpk_reports,
        "obb": obb_report,
        "base_obb_sha256": base_obb_sha256,
    }
    result["content_id"] = content_id(result)
    (output / "candidate-manifest.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--rosters", type=Path, default=DEFAULT_ROSTERS)
    parser.add_argument("--player", type=Path, default=DEFAULT_PLAYER)
    parser.add_argument("--player-report", type=Path, default=DEFAULT_PLAYER_REPORT)
    parser.add_argument("--assignment", type=Path, default=DEFAULT_ASSIGNMENT)
    parser.add_argument("--cleanup-report", type=Path, default=DEFAULT_CLEANUP_REPORT)
    parser.add_argument("--base-obb", type=Path, default=DEFAULT_BASE_OBB)
    parser.add_argument("--kit-root", type=Path, default=DEFAULT_KIT_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    result = build(parser.parse_args())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
