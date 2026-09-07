#!/usr/bin/env python3
"""Build an isolated original-ID player experiment from EF10 tables.

The normal converter keeps the PES21 player IDs and writes EF10 data into
globally-unused surrogate slots.  This experiment deliberately does the
opposite for a small, manifest-selected roster: shared IDs are updated in
place and EF10-only IDs replace retired PES21 rows while the fixed Player.bin
record count is preserved.  It is intentionally data-only; no runtime source
or release archive is changed.

Replacing a retired row is safer than appending EF10 records, but it still
has a known experimental risk: the replacement ID can create a non-monotonic
Player.bin sequence.  The report records that condition so it can be tested
on hardware before any wider rollout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, Iterable

from convert_efootball10_players import (
    EF10_ABILITY_BITS,
    EF10_PLAYER_SIZE,
    PES21_PLAYER_SIZE,
    encode_pes21_wesys,
    ef10_abilities,
    ef10_name,
    ef10_nationality,
    ef10_player_position,
    infer_nationality_map,
    pes21_name,
    pes21_player_position,
    replace_names_abilities_and_nationality,
    records,
)
from exhibition_team_catalog import catalog_team_map, load_catalog
from pesdb import (
    decode_wesys,
    parse_ef10_assignments,
    parse_pes21_assignments,
    parse_team_records,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EF10_DIR = Path("local-debug/efootball10-audit/tables/common/etc/pesdb")
DEFAULT_PES21_DIR = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_MANIFEST = Path("data/experimental_original_inter_miami.json")
DEFAULT_OUTPUT = Path("local-debug/efootball10-original-inter-miami-canary")

PLAYER_ID_OFFSET = 8
INSTALL_VERSION_ROW_SIZE = 8
PLAYER_DELETE_ROW_SIZE = 4
PLAYER_ASSIGNMENT_ROW_SIZE = 16
SPECIAL_ASSIGNMENT_ROW_SIZE = 16
PLAYER_WEEKLY_ROW_SIZE = 8


def resolve(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def player_id(row: bytes) -> int:
    return struct.unpack_from("<I", row, PLAYER_ID_OFFSET)[0]


def source_player_id(row: bytes) -> int:
    return struct.unpack_from("<Q", row, PLAYER_ID_OFFSET)[0]


def set_player_id(row: bytes, value: int) -> bytes:
    if not 0 < value <= 0xFFFFFFFF:
        raise ValueError(f"player ID does not fit PES21 field: {value}")
    result = bytearray(row)
    struct.pack_into("<I", result, PLAYER_ID_OFFSET, value)
    return bytes(result)


def set_registered_position(row: bytes, position: int) -> bytes:
    if not 0 <= position <= 0x0F:
        raise ValueError(f"invalid registered position: {position}")
    result = bytearray(row)
    word = struct.unpack_from("<I", result, 52)[0]
    word = (word & ~(0x0F << 18)) | (position << 18)
    struct.pack_into("<I", result, 52, word)
    return bytes(result)


def u32_rows(raw: bytes, row_size: int) -> list[list[int]]:
    if len(raw) % row_size:
        raise ValueError(f"raw table length {len(raw)} is not divisible by {row_size}")
    return [
        [struct.unpack_from("<I", raw, offset + field)[0] for field in range(0, row_size, 4)]
        for offset in range(0, len(raw), row_size)
    ]


def ids_from_player_assignment(raw: bytes) -> set[int]:
    if len(raw) % PLAYER_ASSIGNMENT_ROW_SIZE:
        raise ValueError("PlayerAssignment.bin has a partial row")
    return {
        struct.unpack_from("<I", raw, offset + 4)[0]
        for offset in range(0, len(raw), PLAYER_ASSIGNMENT_ROW_SIZE)
        if struct.unpack_from("<I", raw, offset + 4)[0]
    }


def ids_from_special_assignment(raw: bytes) -> set[int]:
    if len(raw) % SPECIAL_ASSIGNMENT_ROW_SIZE:
        raise ValueError("SpecialPlayerAssignment.bin has a partial row")
    return {
        struct.unpack_from("<I", raw, offset)[0]
        for offset in range(0, len(raw), SPECIAL_ASSIGNMENT_ROW_SIZE)
        if struct.unpack_from("<I", raw, offset)[0]
    }


def ids_from_delete_list(raw: bytes) -> list[int]:
    if len(raw) % PLAYER_DELETE_ROW_SIZE:
        raise ValueError("PlayerDeleteList.bin has a partial row")
    return [
        struct.unpack_from("<I", raw, offset)[0]
        for offset in range(0, len(raw), PLAYER_DELETE_ROW_SIZE)
    ]


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported experiment manifest schema")
    team = payload.get("team")
    if not isinstance(team, dict) or int(team.get("ef10_team_id", 0)) <= 0:
        raise ValueError(f"{path}: team.ef10_team_id is required")
    modes = payload.get("modes")
    if not isinstance(modes, dict):
        raise ValueError(f"{path}: modes must be an object")
    for mode in ("canary", "xi"):
        values = modes.get(mode)
        if not isinstance(values, list) or not values:
            raise ValueError(f"{path}: modes.{mode} must be a non-empty list")
        if any(int(value) <= 0 for value in values):
            raise ValueError(f"{path}: modes.{mode} contains an invalid player ID")
    return payload


def select_sources(
    *,
    roster_ids: list[int],
    pes21_ids: set[int],
    manifest: dict[str, Any],
    mode: str,
) -> tuple[list[int], list[int], list[int]]:
    shared = [player_id for player_id in roster_ids if player_id in pes21_ids]
    missing = [player_id for player_id in roster_ids if player_id not in pes21_ids]
    if mode == "full":
        selected_missing = missing
    else:
        configured = [int(value) for value in manifest["modes"][mode]]
        unknown = sorted(set(configured) - set(missing))
        if unknown:
            raise ValueError(
                f"manifest {mode} players are not missing from PES21: {unknown}"
            )
        selected_missing = [player_id for player_id in missing if player_id in configured]
    if not selected_missing:
        raise ValueError(f"mode {mode} selected no EF10-only players")
    include_shared = bool(manifest.get("policy", {}).get("include_shared_players", True))
    selected = [
        player_id
        for player_id in roster_ids
        if (include_shared and player_id in shared) or player_id in selected_missing
    ]
    if len(selected) != len(set(selected)):
        raise ValueError("EF10 roster contains duplicate selected player IDs")
    return selected, shared, missing


def reference_locations(
    *,
    candidate: int,
    pes21_dir: Path,
    raw_tables: dict[str, bytes],
) -> dict[str, int]:
    """Find known player-key references that make a donor unsafe to reuse."""
    locations: dict[str, int] = {}
    assignment = raw_tables.get("PlayerAssignment.bin", b"")
    for offset in range(0, len(assignment), PLAYER_ASSIGNMENT_ROW_SIZE):
        if struct.unpack_from("<I", assignment, offset + 4)[0] == candidate:
            locations["PlayerAssignment.bin"] = locations.get("PlayerAssignment.bin", 0) + 1

    special = raw_tables.get("SpecialPlayerAssignment.bin", b"")
    for offset in range(0, len(special), SPECIAL_ASSIGNMENT_ROW_SIZE):
        if struct.unpack_from("<I", special, offset)[0] == candidate:
            locations["SpecialPlayerAssignment.bin"] = locations.get(
                "SpecialPlayerAssignment.bin", 0
            ) + 1

    weekly = raw_tables.get("PlayerWeekly.bin", b"")
    if weekly:
        if len(weekly) % PLAYER_WEEKLY_ROW_SIZE:
            raise ValueError("PlayerWeekly.bin has a partial row")
        for offset in range(0, len(weekly), PLAYER_WEEKLY_ROW_SIZE):
            fields = struct.unpack_from("<II", weekly, offset)
            if candidate in fields:
                locations["PlayerWeekly.bin"] = locations.get("PlayerWeekly.bin", 0) + 1

    # These tables are not present in the supplied PES21 dt200, but newer
    # revisions may carry a player key in their first field.  Refuse a donor
    # with such a reference instead of guessing an opaque schema.
    for name, row_size in (("PlayerAppearance.bin", 60), ("BootsList.bin", 8)):
        path = pes21_dir / name
        if not path.is_file():
            continue
        raw = raw_tables.get(name)
        if raw is None:
            raw = decode_wesys(path)
            raw_tables[name] = raw
        if len(raw) % row_size:
            raise ValueError(f"{name} has a partial row")
        for offset in range(0, len(raw), row_size):
            if struct.unpack_from("<I", raw, offset)[0] == candidate:
                locations[name] = locations.get(name, 0) + 1
    return locations


def choose_donor(
    *,
    source_id: int,
    source_row: bytes,
    pes21_rows: list[bytes],
    pes21_by_id: dict[int, bytes],
    assigned_ids: set[int],
    special_ids: set[int],
    deleted_ids: set[int],
    used_donors: set[int],
    raw_tables: dict[str, bytes],
    pes21_dir: Path,
    require_deleted: bool,
    require_position_match: bool,
) -> tuple[int, dict[str, int]]:
    source_position = ef10_player_position(source_row)
    candidates: list[tuple[tuple[int, int, int], int, dict[str, int]]] = []
    for donor_id in sorted(pes21_by_id):
        if donor_id in used_donors or donor_id in assigned_ids or donor_id in special_ids:
            continue
        if donor_id <= 0 or not pes21_name(pes21_by_id[donor_id]):
            continue
        if require_deleted and donor_id not in deleted_ids:
            continue
        if require_position_match and pes21_player_position(pes21_by_id[donor_id]) != source_position:
            continue
        refs = reference_locations(
            candidate=donor_id,
            pes21_dir=pes21_dir,
            raw_tables=raw_tables,
        )
        if refs:
            continue
        priority = 0 if donor_id in deleted_ids else 1
        candidates.append(((priority, abs(donor_id - source_id), donor_id), donor_id, refs))
    if not candidates:
        raise RuntimeError(
            f"no safe PES21 donor slot for EF10 player {source_id} "
            f"(position {source_position})"
        )
    candidates.sort(key=lambda item: item[0])
    _key, donor_id, refs = candidates[0]
    return donor_id, refs


def patch_install_versions(
    raw: bytes, donor_to_source: dict[int, int], expected_player_ids: set[int]
) -> bytes:
    if len(raw) % INSTALL_VERSION_ROW_SIZE:
        raise ValueError("InstallVersionPlayer.bin has a partial row")
    rows = [bytearray(raw[offset : offset + INSTALL_VERSION_ROW_SIZE]) for offset in range(0, len(raw), INSTALL_VERSION_ROW_SIZE)]
    seen: dict[int, int] = {}
    for index, row in enumerate(rows):
        old_id = struct.unpack_from("<I", row, 0)[0]
        seen[old_id] = seen.get(old_id, 0) + 1
        if old_id in donor_to_source:
            struct.pack_into("<I", row, 0, donor_to_source[old_id])
    missing = sorted(set(donor_to_source) - set(seen))
    if missing:
        raise RuntimeError(f"donor IDs absent from InstallVersionPlayer.bin: {missing}")
    # PES21 groups this table by install version and sorts IDs inside each
    # group.  Keep those boundaries while restoring the ordering invariant
    # after a donor ID is replaced by an EF10 ID.
    grouped: list[bytearray] = []
    start = 0
    while start < len(rows):
        version = struct.unpack_from("<I", rows[start], 4)[0]
        end = start + 1
        while end < len(rows) and struct.unpack_from("<I", rows[end], 4)[0] == version:
            end += 1
        grouped.extend(sorted(rows[start:end], key=lambda row: struct.unpack_from("<I", row, 0)[0]))
        start = end
    result = b"".join(bytes(row) for row in grouped)
    actual = {struct.unpack_from("<I", result, offset)[0] for offset in range(0, len(result), 8)}
    if actual != expected_player_ids:
        raise RuntimeError("InstallVersionPlayer.bin IDs no longer match Player.bin")
    return result


def patch_delete_list(raw: bytes, donor_ids: set[int]) -> tuple[bytes, int]:
    values = ids_from_delete_list(raw)
    counts = {value: values.count(value) for value in donor_ids}
    missing = sorted(value for value, count in counts.items() if count != 1)
    if missing:
        raise RuntimeError(
            "each donor must occur exactly once in PlayerDeleteList.bin: "
            + ", ".join(map(str, missing))
        )
    filtered = [value for value in values if value not in donor_ids]
    return encode_pes21_wesys(b"".join(struct.pack("<I", value) for value in filtered)), len(values) - len(filtered)


def render_c_include(player_ids: list[int], shirts: list[int], mode: str) -> str:
    def wrapped(values: Iterable[int], suffix: str) -> str:
        values = list(values)
        return "\n".join(
            "    " + ", ".join(f"{value}{suffix}" for value in values[index : index + 8]) + ","
            for index in range(0, len(values), 8)
        )

    return (
        "// Generated by tools/experimental_import_ef10_original.py.\n"
        f"// Inter Miami original-ID experiment ({mode}); isolated artifact only.\n"
        "// Do not include this file in the runtime until the team alias is integrated.\n\n"
        "static const uint32_t experimental_inter_miami_players[] = {\n"
        + wrapped(player_ids, "u")
        + "\n};\n"
        "static const uint8_t experimental_inter_miami_shirts[] = {\n"
        + wrapped(shirts, "")
        + "\n};\n"
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    ef10_dir = resolve(root, args.ef10_dir)
    pes21_dir = resolve(root, args.pes21_dir)
    manifest_path = resolve(root, args.manifest)
    output_dir = resolve(root, args.output_dir)
    if output_dir in (ef10_dir, pes21_dir):
        raise RuntimeError("output directory must be separate from source databases")
    manifest = load_manifest(manifest_path)
    team_id = int(manifest["team"]["ef10_team_id"])
    physical_team_id = int(manifest["team"].get("pes21_physical_team_id") or 0)

    ef10_player_raw = decode_wesys(ef10_dir / "Player.bin")
    pes21_player_raw = decode_wesys(pes21_dir / "Player.bin")
    ef10_rows = records(ef10_player_raw, EF10_PLAYER_SIZE)
    pes21_rows = records(pes21_player_raw, PES21_PLAYER_SIZE)
    ef10_by_id = {source_player_id(row): row for row in ef10_rows}
    pes21_by_id = {player_id(row): row for row in pes21_rows}
    if len(ef10_by_id) != len(ef10_rows) or len(pes21_by_id) != len(pes21_rows):
        raise RuntimeError("source Player.bin contains duplicate IDs")

    assignments_raw = decode_wesys(ef10_dir / "PlayerAssignment.bin")
    assignments = parse_ef10_assignments(assignments_raw)
    roster = assignments.get(team_id, [])
    if not roster:
        raise RuntimeError(f"EF10 team {team_id} has no PlayerAssignment rows")
    roster_ids = [assignment.player_id for assignment in roster]
    selected_ids, shared_ids, missing_ids = select_sources(
        roster_ids=roster_ids,
        pes21_ids=set(pes21_by_id),
        manifest=manifest,
        mode=args.mode,
    )

    expected_shared = manifest.get("expected_shared_player_ids")
    if expected_shared is not None and sorted(map(int, expected_shared)) != sorted(
        player_id for player_id in shared_ids
    ):
        raise RuntimeError("manifest expected_shared_player_ids disagrees with source tables")
    expected_missing = manifest.get("expected_missing_player_ids")
    if expected_missing is not None and sorted(map(int, expected_missing)) != sorted(missing_ids):
        raise RuntimeError("manifest expected_missing_player_ids disagrees with source tables")

    raw_tables: dict[str, bytes] = {}
    for name in (
        "PlayerAssignment.bin",
        "SpecialPlayerAssignment.bin",
        "InstallVersionPlayer.bin",
        "PlayerDeleteList.bin",
        "PlayerWeekly.bin",
    ):
        path = pes21_dir / name
        if path.is_file():
            raw_tables[name] = decode_wesys(path)

    assigned_ids = ids_from_player_assignment(raw_tables["PlayerAssignment.bin"])
    special_ids = ids_from_special_assignment(raw_tables["SpecialPlayerAssignment.bin"])
    deleted_values = ids_from_delete_list(raw_tables["PlayerDeleteList.bin"])
    deleted_ids = set(deleted_values)
    pes21_rosters = parse_pes21_assignments(raw_tables["PlayerAssignment.bin"])
    pes21_teams = parse_team_records(
        decode_wesys(pes21_dir / "Team.bin"), "pes21"
    )
    catalog_path = root / "data" / "exhibition_team_catalog.json"
    catalog_by_id = catalog_team_map(load_catalog(catalog_path)) if catalog_path.is_file() else {}
    if physical_team_id:
        if physical_team_id not in pes21_teams:
            raise RuntimeError(
                f"reserved PES21 physical team {physical_team_id} is absent from Team.bin"
            )
        if physical_team_id in catalog_by_id:
            raise RuntimeError(
                f"reserved PES21 physical team {physical_team_id} is already exposed by the selector"
            )
        physical_roster_count = len(pes21_rosters.get(physical_team_id, []))
        if physical_roster_count < 18:
            raise RuntimeError(
                f"reserved PES21 physical team {physical_team_id} has only "
                f"{physical_roster_count} native players"
            )
    else:
        physical_roster_count = 0
    nationality_map, nationality_diagnostics = infer_nationality_map(ef10_by_id, pes21_by_id)
    require_deleted = bool(manifest.get("policy", {}).get("require_deleted_donor", True))
    require_position = bool(manifest.get("policy", {}).get("require_position_match", True))

    donor_to_source: dict[int, int] = {}
    source_to_target: dict[int, int] = {}
    mapping_rows: list[dict[str, Any]] = []
    used_donors: set[int] = set()
    for source_id in selected_ids:
        source_row = ef10_by_id[source_id]
        if source_id in pes21_by_id:
            target_id = source_id
            donor_id = None
            template = pes21_by_id[target_id]
            mode = "direct_shared_id"
        else:
            donor_id, refs = choose_donor(
                source_id=source_id,
                source_row=source_row,
                pes21_rows=pes21_rows,
                pes21_by_id=pes21_by_id,
                assigned_ids=assigned_ids,
                special_ids=special_ids,
                deleted_ids=deleted_ids,
                used_donors=used_donors,
                raw_tables=raw_tables,
                pes21_dir=pes21_dir,
                require_deleted=require_deleted,
                require_position_match=require_position,
            )
            if refs:
                raise RuntimeError(f"donor {donor_id} unexpectedly has references: {refs}")
            used_donors.add(donor_id)
            donor_to_source[donor_id] = source_id
            target_id = source_id
            template = pes21_by_id[donor_id]
            mode = "original_id_retired_slot"
        if target_id in source_to_target.values():
            raise RuntimeError(f"duplicate target ID selected: {target_id}")
        source_to_target[source_id] = target_id
        converted = replace_names_abilities_and_nationality(
            template, source_row, nationality_map
        )
        if require_position:
            converted = set_registered_position(converted, ef10_player_position(source_row))
        converted = set_player_id(converted, target_id)
        mapping_rows.append(
            {
                "ef10_player_id": source_id,
                "target_pes21_id": target_id,
                "donor_pes21_id": donor_id,
                "mode": mode,
                "name": ef10_name(source_row),
                "registered_position": ef10_player_position(source_row),
                "template_position": pes21_player_position(template),
                "template_name": pes21_name(template),
                "abilities": ef10_abilities(source_row),
                "ef10_nationality_code": ef10_nationality(source_row),
                "pes21_nationality_code": nationality_map[ef10_nationality(source_row)],
                "converted_sha256": sha256_bytes(converted),
            }
        )
        # Store the converted row on the mapping row temporarily; it is
        # consumed below by the target-index patch and then discarded.
        mapping_rows[-1]["_converted_row"] = converted

    row_index_by_id = {player_id(row): index for index, row in enumerate(pes21_rows)}
    patched_rows = list(pes21_rows)
    for mapping in mapping_rows:
        target_id = int(mapping["target_pes21_id"])
        donor_id = mapping["donor_pes21_id"]
        patch_index = row_index_by_id[int(donor_id)] if donor_id is not None else row_index_by_id[target_id]
        patched_rows[patch_index] = mapping["_converted_row"]  # type: ignore[assignment]
    for mapping in mapping_rows:
        mapping.pop("_converted_row", None)

    # Player.bin is ID-sorted in the stock database.  Re-sort after replacing
    # retired rows so the native lookup path sees the same ordering invariant.
    patched_rows.sort(key=player_id)
    patched_player_raw = b"".join(patched_rows)
    patched_ids = [player_id(row) for row in patched_rows]
    old_ids = set(pes21_by_id)
    expected_ids = (old_ids - set(donor_to_source)) | set(donor_to_source.values())
    if set(patched_ids) != expected_ids or len(patched_ids) != len(set(patched_ids)):
        raise RuntimeError("patched Player.bin ID set is inconsistent")
    if any(source_id not in set(patched_ids) for source_id in source_to_target.values()):
        raise RuntimeError("an original EF10 ID is absent from patched Player.bin")

    install_raw = patch_install_versions(
        raw_tables["InstallVersionPlayer.bin"], donor_to_source, set(patched_ids)
    )
    delete_raw, removed_delete_rows = patch_delete_list(
        raw_tables["PlayerDeleteList.bin"], set(donor_to_source)
    )
    if ids_from_player_assignment(raw_tables["PlayerAssignment.bin"]) != assigned_ids:
        raise RuntimeError("PlayerAssignment.bin changed while reading")
    if set(donor_to_source) & assigned_ids or set(donor_to_source) & special_ids:
        raise RuntimeError("a donor is referenced by a native assignment table")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_files = {
        "Player.bin": encode_pes21_wesys(patched_player_raw),
        "InstallVersionPlayer.bin": encode_pes21_wesys(install_raw),
        "PlayerDeleteList.bin": delete_raw,
        "PlayerAssignment.bin": (pes21_dir / "PlayerAssignment.bin").read_bytes(),
        "SpecialPlayerAssignment.bin": (pes21_dir / "SpecialPlayerAssignment.bin").read_bytes(),
    }
    for name, value in output_files.items():
        (output_dir / name).write_bytes(value)
    (output_dir / "cpk-replacement-manifest.json").write_text(
        json.dumps(
            {
                "common/etc/pesdb/Player.bin": "Player.bin",
                "common/etc/pesdb/InstallVersionPlayer.bin": "InstallVersionPlayer.bin",
                "common/etc/pesdb/PlayerDeleteList.bin": "PlayerDeleteList.bin",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    target_by_source = {int(row["ef10_player_id"]): int(row["target_pes21_id"]) for row in mapping_rows}
    shirts_by_source = {assignment.player_id: assignment.shirt for assignment in roster}
    roster_targets = [target_by_source[source_id] for source_id in selected_ids]
    roster_shirts = [shirts_by_source[source_id] for source_id in selected_ids]
    (output_dir / "inter_miami_original_roster.inc").write_text(
        render_c_include(roster_targets, roster_shirts, args.mode),
        encoding="utf-8",
        newline="\n",
    )

    source_hashes = {
        name: sha256_file(pes21_dir / name)
        for name in ("Player.bin", "InstallVersionPlayer.bin", "PlayerDeleteList.bin", "PlayerAssignment.bin")
    }
    output_hashes = {name: sha256_bytes(value) for name, value in output_files.items()}
    monotonic = all(left < right for left, right in zip(patched_ids, patched_ids[1:]))
    shared_memberships = []
    for source_id in shared_ids:
        memberships = []
        for physical_team_id, team_roster in sorted(pes21_rosters.items()):
            if any(assignment.player_id == source_id for assignment in team_roster):
                memberships.append(
                    {
                        "pes21_team_id": physical_team_id,
                        "pes21_team_name": pes21_teams.get(physical_team_id).name
                        if physical_team_id in pes21_teams
                        else "(unknown)",
                        "team_kind": catalog_by_id.get(physical_team_id, {}).get(
                            "kind", "unknown"
                        ),
                        "cleanup_action": (
                            "preserve_national_membership"
                            if catalog_by_id.get(physical_team_id, {}).get("kind")
                            == "national"
                            else "remove_legacy_club_membership"
                        ),
                    }
                )
        shared_memberships.append(
            {
                "player_id": source_id,
                "ef10_team_id": team_id,
                "existing_pes21_memberships": memberships,
                "cleanup_required_before_runtime": bool(memberships),
            }
        )
    warnings = [
        "This artifact does not add an Inter Miami Team.bin record or selector entry.",
        "Shared-player updates can temporarily leave the same player in legacy clubs; run legacy cleanup before runtime integration.",
    ]
    if not monotonic:
        warnings.append("Player.bin IDs are no longer strictly monotonic after retired-slot replacement; hardware validation is required.")
    report = {
        "schema_version": 1,
        "experiment": "inter_miami_original_id",
        "mode": args.mode,
        "team": {
            "ef10_team_id": team_id,
            "ef10_name": manifest["team"].get("ef10_name", ""),
            "logical_team_id": int(manifest["team"].get("logical_team_id", team_id)),
            "pes21_physical_team_id": manifest["team"].get("pes21_physical_team_id"),
            "pes21_physical_team_name": manifest["team"].get(
                "pes21_physical_team_name", ""
            ),
            "slot_policy": manifest["team"].get("slot_policy", ""),
            "team_record_imported": False,
            "physical_slot_in_pes21_team_table": physical_team_id in pes21_teams,
            "physical_slot_exposed_by_current_selector": physical_team_id in catalog_by_id,
            "physical_slot_native_roster_count": physical_roster_count,
            "roster_entries_selected": len(selected_ids),
            "roster_entries_total": len(roster_ids),
        },
        "source_sha256": source_hashes,
        "output_sha256": output_hashes,
        "players": mapping_rows,
        "counts": {
            "ef10_roster": len(roster_ids),
            "shared_roster_players": len(shared_ids),
            "missing_roster_players": len(missing_ids),
            "selected_players": len(selected_ids),
            "original_id_players": len(donor_to_source),
            "direct_shared_players": sum(1 for row in mapping_rows if row["mode"] == "direct_shared_id"),
            "player_records_before": len(pes21_rows),
            "player_records_after": len(patched_rows),
            "delete_rows_before": len(deleted_values),
            "delete_rows_removed": removed_delete_rows,
            "delete_rows_after": len(ids_from_delete_list(decode_wesys(output_dir / "PlayerDeleteList.bin"))),
            "shared_players_with_existing_pes21_memberships": sum(
                1 for row in shared_memberships if row["existing_pes21_memberships"]
            ),
        },
        "invariants": {
            "player_record_count_unchanged": len(pes21_rows) == len(patched_rows),
            "player_assignment_byte_identical": output_files["PlayerAssignment.bin"] == (pes21_dir / "PlayerAssignment.bin").read_bytes(),
            "original_ids_present": set(donor_to_source.values()).issubset(set(patched_ids)),
            "donor_ids_absent": not (set(donor_to_source) & set(patched_ids)),
            "install_version_ids_match_player_ids": set(struct.unpack_from("<I", install_raw, offset)[0] for offset in range(0, len(install_raw), 8)) == set(patched_ids),
            "donor_ids_removed_from_delete_list": not (set(donor_to_source) & set(ids_from_delete_list(decode_wesys(output_dir / "PlayerDeleteList.bin")))),
            "strictly_monotonic_player_ids": monotonic,
            "player_record_order_sorted_after_import": monotonic,
            "known_native_donor_references": False,
        },
        "nationality_mapping_diagnostics": {
            str(code): nationality_diagnostics[code]
            for code in sorted({ef10_nationality(ef10_by_id[player_id]) for player_id in selected_ids})
        },
        "shared_memberships": shared_memberships,
        "donor_to_original": {str(donor): source for donor, source in sorted(donor_to_source.items())},
        "warnings": warnings,
        "output_dir": str(output_dir),
    }
    (output_dir / "original-id-map.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "team_id": team_id,
                "mode": args.mode,
                "map": {str(source): target for source, target in sorted(source_to_target.items())},
                "donor_to_original": {str(donor): source for donor, source in sorted(donor_to_source.items())},
                "players": mapping_rows,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "validation-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "team-integration-pending.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "logical_ef10_team_id": team_id,
                "ef10_name": manifest["team"].get("ef10_name", ""),
                "pes21_physical_team_id": manifest["team"].get("pes21_physical_team_id"),
                "pes21_physical_team_name": manifest["team"].get(
                    "pes21_physical_team_name", ""
                ),
                "status": "player_only_experiment",
                "reason": "PES21 Team.bin has no Inter Miami record; the manifest reserves a physical slot, but selector/runtime integration remains a separate coordinated change.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> None:
    # Windows consoles often default to cp1252; reports contain source names
    # with accents, so keep the CLI output lossless like the JSON artifacts.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ef10-dir", type=Path, default=DEFAULT_EF10_DIR)
    parser.add_argument("--pes21-dir", type=Path, default=DEFAULT_PES21_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=("canary", "xi", "full"), default="canary")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
