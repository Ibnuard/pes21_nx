#!/usr/bin/env python3
"""Build a detachable full-roster Inter Miami NRO companion OBB.

The original-ID converter deliberately starts from the stock PES21 tables.
The deployed dt200 already contains unrelated team/player updates, so copying
those stock-based outputs would silently discard them. This tool merges all 27
Inter Miami players into the current dt200, patches one unused physical team's
name and native uniform definitions, replaces that physical team's three crest
PNGs in dt240, imports EF10 portraits into retired/shared dt241 slots, updates
the latest scoreboard in dt210, and optionally creates a separate OBB copy. Every unrelated CPK
and OBB member is verified byte-for-byte. Standard release files are never
overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT_CPK = Path("local-debug/inter-miami-runtime-base/dt200-current.cpk")
DEFAULT_CURRENT_DT210 = Path("local-debug/visual-v8-20260831/cpk-work/dt210-score.cpk")
DEFAULT_CURRENT_DT241 = Path(
    "local-debug/efootball10-all-teams-patch/dt241_mobile_all_ef10_all_teams.cpk"
)
DEFAULT_EF10_ASSIGNMENTS = Path(
    "local-debug/efootball10-audit/tables/common/etc/pesdb/PlayerAssignment.bin"
)
DEFAULT_EF10_CATEGORIES = Path(
    "local-debug/efootball10-audit/tables/common/etc/pesdb/CategoryTeamList.bin"
)
DEFAULT_CATALOG = Path("data/exhibition_team_catalog.json")
DEFAULT_CURRENT_DT240 = Path("local-debug/efootball10-audit/old-cpk/dt240_mobile_all.cpk")
DEFAULT_FULL_ARTIFACT = Path("local-debug/efootball10-original-inter-miami-full")
DEFAULT_OUTPUT_DIR = Path("local-debug/inter-miami-release-experiment")
DEFAULT_RELEASE_OBB = Path(
    "local-debug/inter-miami-runtime-base/patch.pre-inter-miami.obb"
)
DEFAULT_UNIFORM_SOURCE = Path("local-debug/inter-miami-visual-source/ef10-uniform-def")
DEFAULT_LOGO_SOURCE = Path("data")
DEFAULT_PORTRAIT_DIR = Path("local-debug/inter-miami-portraits/q128")
OBB_DT200_MEMBER = "Expansion/dt200_mobile_all.cpk"
OBB_DT210_MEMBER = "Expansion/dt210_mobile_android.cpk"
OBB_DT240_MEMBER = "Expansion/dt240_mobile_all.cpk"
OBB_DT241_MEMBER = "Expansion/dt241_mobile_all.cpk"
EXPECTED_DT200_MEMBERS = 2435
EXPECTED_DT210_MEMBERS = 422
EXPECTED_DT240_MEMBERS = 6550
EXPECTED_DT241_MEMBERS = 28119
PLAYER_SIZE = 312
PLAYER_ID_OFFSET = 8
INSTALL_VERSION_SIZE = 8
DELETE_SIZE = 4
TEAM_SIZE = 1532
TEAM_ID_OFFSET = 8
TEAM_NAME_OFFSET = 368
TEAM_NAME_SIZE = 70
TEAM_SHORT_CODE_OFFSETS = (882, 1382)
ASSIGNMENT_SIZE = 16
INTER_MIAMI_PHYSICAL_TEAM_ID = 2473
INTER_MIAMI_EF10_CATEGORY_ID = 603
INTER_MIAMI_CATEGORY_LABEL = "N AMERICA CLUBS"
INTER_MIAMI_NAME = "INTER MIAMI CF"
INTER_MIAMI_SHORT_CODE = "MIA"
DT200_REPLACED_MEMBERS = (
    "common/etc/pesdb/InstallVersionPlayer.bin",
    "common/etc/pesdb/Player.bin",
    "common/etc/pesdb/PlayerDeleteList.bin",
    "common/etc/pesdb/PlayerAssignment.bin",
    "common/etc/pesdb/Team.bin",
    "common/etc/uniform/team/2473/2473_DEF_1st.bin",
    "common/etc/uniform/team/2473/2473_DEF_2nd.bin",
    "common/etc/uniform/team/2473/2473_DEF_GK1st.bin",
)
DT240_REPLACED_MEMBERS = (
    "common/render/symbol/flag/e_002473_f.png",
    "common/render/symbol/flag/e_002473_f_l.png",
    "common/render/symbol/flag/e_002473_f_s.png",
)
PORTRAIT_MEMBER_PREFIX = "common/player/"


def load_catalog_team_kinds(path: Path) -> dict[int, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    teams = payload.get("teams")
    if not isinstance(teams, list):
        raise ValueError(f"{path}: catalog teams must be a list")
    result: dict[int, str] = {}
    for team in teams:
        team_id = int(team.get("team_id", 0))
        kind = str(team.get("kind", ""))
        if not team_id or kind not in {"club", "national"} or team_id in result:
            raise ValueError(f"{path}: invalid team kind row for {team_id}")
        result[team_id] = kind
    return result


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


def decode_wesys_bytes(data: bytes, label: str) -> bytes:
    if len(data) < 16 or data[3:8] != b"WESYS":
        raise ValueError(f"{label}: invalid WESYS header")
    compressed_size, raw_size = struct.unpack_from("<II", data, 8)
    payload = bytearray(data[16 : 16 + compressed_size])
    if len(payload) != compressed_size:
        raise ValueError(f"{label}: truncated compressed payload")

    key_constants = {
        1: (378445824, 774547186, 214490323),
        2: (3982174560, 1246903118, 4087552941),
    }
    key_index = data[1] & 0x0F
    if key_index in key_constants:
        mask = 0xFFFFFFFF
        x, y, z = key_constants[key_index]
        w = ((raw_size << 16) | compressed_size) & mask
        for offset in range(0, len(payload) - 3, 4):
            t = (x ^ (x << 11)) & mask
            x, y, z, previous = y, z, w, w
            w = (previous ^ (((previous >> 11) ^ t) >> 8) ^ t) & mask
            word = struct.unpack_from("<I", payload, offset)[0] ^ w
            struct.pack_into("<I", payload, offset, word)

    try:
        raw = zlib.decompress(payload)
    except zlib.error:
        # Uniform definition files use the WESYS cipher/header but store their
        # 96-byte body without zlib compression.
        if compressed_size != raw_size:
            raise
        raw = bytes(payload)
    if len(raw) != raw_size:
        raise ValueError(f"{label}: decoded {len(raw)} bytes, expected {raw_size}")
    return raw


def encode_wesys(raw: bytes) -> bytes:
    compressed = zlib.compress(raw, level=9)
    return b"\xff\x10\x81WESYS" + struct.pack("<II", len(compressed), len(raw)) + compressed


def encode_wesys_compact(raw: bytes) -> bytes:
    try:
        import zopfli.zlib as zopfli_zlib
    except ImportError as exc:
        raise RuntimeError(
            "zopfli is required to keep the experimental dt200 inside its fixed OBB slot"
        ) from exc
    compressed = zopfli_zlib.compress(raw, numiterations=1)
    return b"\xff\x10\x81WESYS" + struct.pack("<II", len(compressed), len(raw)) + compressed


def member_name(row: dict[str, Any]) -> str:
    return "/".join(
        part
        for part in (str(row.get("DirName") or ""), str(row.get("FileName") or ""))
        if part and part != "<NULL>"
    )


def cpk_index(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], int]:
    sys.path.insert(0, str(ROOT / "tools"))
    from prepare_runtime import read_cpk_packet

    with path.open("rb") as source:
        header = read_cpk_packet(source, 0, b"CPK ")[0]
        rows = read_cpk_packet(source, int(header["TocOffset"]), b"TOC ")
    return (
        header,
        {member_name(row): row for row in rows},
        min(int(header["TocOffset"]), int(header["ContentOffset"])),
    )


def read_members(path: Path, members: tuple[str, ...]) -> dict[str, bytes]:
    _header, rows, data_base = cpk_index(path)
    missing = sorted(set(members) - set(rows))
    if missing:
        raise RuntimeError(f"{path}: missing CPK members: {missing}")
    result: dict[str, bytes] = {}
    with path.open("rb") as source:
        for name in members:
            row = rows[name]
            source.seek(data_base + int(row["FileOffset"]))
            payload = source.read(int(row["FileSize"]))
            if len(payload) != int(row["FileSize"]):
                raise RuntimeError(f"{path}: truncated CPK member {name}")
            result[name] = payload
    return result


def split_rows(raw: bytes, size: int, label: str) -> list[bytes]:
    if len(raw) % size:
        raise ValueError(f"{label}: partial {size}-byte row")
    return [raw[offset : offset + size] for offset in range(0, len(raw), size)]


def player_id(row: bytes) -> int:
    return struct.unpack_from("<I", row, PLAYER_ID_OFFSET)[0]


def merge_player_table(
    current_raw: bytes, experiment_raw: bytes, players: list[dict[str, Any]]
) -> tuple[bytes, dict[str, Any]]:
    current_rows = split_rows(current_raw, PLAYER_SIZE, "current Player.bin")
    experiment_rows = split_rows(experiment_raw, PLAYER_SIZE, "experiment Player.bin")
    current_by_id = {player_id(row): row for row in current_rows}
    experiment_by_id = {player_id(row): row for row in experiment_rows}
    if len(current_by_id) != len(current_rows):
        raise RuntimeError("current Player.bin contains duplicate player IDs")
    if len(experiment_by_id) != len(experiment_rows):
        raise RuntimeError("experiment Player.bin contains duplicate player IDs")

    target_ids = {int(row["target_pes21_id"]) for row in players}
    donor_to_target = {
        int(row["donor_pes21_id"]): int(row["target_pes21_id"])
        for row in players
        if row.get("donor_pes21_id") is not None
    }
    direct_ids = target_ids - set(donor_to_target.values())
    if set(donor_to_target) - set(current_by_id):
        raise RuntimeError("a retired donor is absent from the current Player.bin")
    if set(donor_to_target.values()) & set(current_by_id):
        raise RuntimeError("an original Inter Miami ID already exists in current Player.bin")
    if direct_ids - set(current_by_id):
        raise RuntimeError("a shared Inter Miami ID is absent from current Player.bin")
    if target_ids - set(experiment_by_id):
        raise RuntimeError("the XI artifact is missing a selected converted player row")

    merged: dict[int, bytes] = dict(current_by_id)
    for donor_id in donor_to_target:
        del merged[donor_id]
    for target_id in target_ids:
        merged[target_id] = experiment_by_id[target_id]
    merged_rows = [merged[key] for key in sorted(merged)]

    if len(merged_rows) != len(current_rows):
        raise RuntimeError("Player.bin row count changed during merge")
    if any(player_id(left) >= player_id(right) for left, right in zip(merged_rows, merged_rows[1:])):
        raise RuntimeError("merged Player.bin is not strictly sorted by player ID")
    affected_before = direct_ids | set(donor_to_target)
    unrelated = 0
    for unique_id, before in current_by_id.items():
        if unique_id in affected_before:
            continue
        if merged.get(unique_id) != before:
            raise RuntimeError(f"unrelated current player row changed: {unique_id}")
        unrelated += 1
    return b"".join(merged_rows), {
        "records_before": len(current_rows),
        "records_after": len(merged_rows),
        "direct_rows_replaced": len(direct_ids),
        "donor_rows_replaced": len(donor_to_target),
        "unrelated_rows_byte_identical": unrelated,
        "target_ids": sorted(target_ids),
        "donor_to_original": {str(key): value for key, value in sorted(donor_to_target.items())},
    }


def merge_install_versions(raw: bytes, donor_to_target: dict[int, int]) -> bytes:
    rows = [bytearray(row) for row in split_rows(raw, INSTALL_VERSION_SIZE, "InstallVersionPlayer.bin")]
    seen = {donor: 0 for donor in donor_to_target}
    existing = {struct.unpack_from("<I", row, 0)[0] for row in rows}
    if set(donor_to_target.values()) & existing:
        raise RuntimeError("an original Inter Miami ID already exists in InstallVersionPlayer.bin")
    for row in rows:
        unique_id = struct.unpack_from("<I", row, 0)[0]
        if unique_id in donor_to_target:
            seen[unique_id] += 1
            struct.pack_into("<I", row, 0, donor_to_target[unique_id])
    invalid = sorted(key for key, count in seen.items() if count != 1)
    if invalid:
        raise RuntimeError(f"donor InstallVersion rows must occur once: {invalid}")

    result: list[bytearray] = []
    start = 0
    while start < len(rows):
        version = struct.unpack_from("<I", rows[start], 4)[0]
        end = start + 1
        while end < len(rows) and struct.unpack_from("<I", rows[end], 4)[0] == version:
            end += 1
        result.extend(sorted(rows[start:end], key=lambda row: struct.unpack_from("<I", row, 0)[0]))
        start = end
    return b"".join(bytes(row) for row in result)


def merge_delete_list(raw: bytes, donor_ids: set[int]) -> bytes:
    rows = split_rows(raw, DELETE_SIZE, "PlayerDeleteList.bin")
    values = [struct.unpack_from("<I", row, 0)[0] for row in rows]
    invalid = sorted(donor for donor in donor_ids if values.count(donor) != 1)
    if invalid:
        raise RuntimeError(f"donor delete-list rows must occur once: {invalid}")
    return b"".join(row for row in rows if struct.unpack_from("<I", row, 0)[0] not in donor_ids)


def validate_ef10_league(raw: bytes) -> dict[str, Any]:
    memberships = []
    for row in split_rows(raw, 12, "EF10 CategoryTeamList.bin"):
        team_id, category_id, order = struct.unpack("<III", row)
        if team_id == 5738:
            memberships.append({"category_id": category_id, "order": order})
    match = next(
        (
            row
            for row in memberships
            if row["category_id"] == INTER_MIAMI_EF10_CATEGORY_ID
        ),
        None,
    )
    if match is None:
        raise RuntimeError(
            f"EF10 team 5738 is not present in category {INTER_MIAMI_EF10_CATEGORY_ID}"
        )
    return {
        "ef10_category_id": INTER_MIAMI_EF10_CATEGORY_ID,
        "selector_label": INTER_MIAMI_CATEGORY_LABEL,
        "source_order": match["order"],
        "all_source_memberships": memberships,
    }


def patch_player_assignments(
    current_raw: bytes,
    ef10_raw: bytes,
    players: list[dict[str, Any]],
    team_kinds: dict[int, str],
    shared_memberships: list[dict[str, Any]],
) -> tuple[bytes, dict[str, Any]]:
    current_rows = split_rows(current_raw, ASSIGNMENT_SIZE, "PlayerAssignment.bin")
    parsed_current = [struct.unpack("<IIII", row) for row in current_rows]
    assignment_ids = [row[0] for row in parsed_current]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise RuntimeError("current PlayerAssignment.bin has duplicate assignment IDs")

    target_ids = [int(player["target_pes21_id"]) for player in players]
    if len(target_ids) != 27 or len(target_ids) != len(set(target_ids)):
        raise RuntimeError("Inter Miami assignment cleanup requires 27 unique players")

    source_by_player: dict[int, tuple[int, int]] = {}
    for row in split_rows(ef10_raw, 24, "EF10 PlayerAssignment.bin"):
        player_id, team_id, _assignment_id, packed, _padding = struct.unpack(
            "<QIIII", row
        )
        if team_id != 5738:
            continue
        if player_id in source_by_player:
            raise RuntimeError(f"duplicate EF10 Inter Miami player {player_id}")
        # Order and shirt fields are shared; opaque high flags are version-
        # specific and must not be copied from EF10 into the PES21 schema.
        source_by_player[int(player_id)] = (
            int(packed) & 0xFFFF,
            (int(packed) >> 8) & 0xFF,
        )
    if set(source_by_player) != set(target_ids):
        missing = sorted(set(target_ids) - set(source_by_player))
        extra = sorted(set(source_by_player) - set(target_ids))
        raise RuntimeError(
            f"EF10 Inter Miami assignment mismatch: missing={missing}, extra={extra}"
        )

    physical_rows = [
        row for row in parsed_current if row[2] == INTER_MIAMI_PHYSICAL_TEAM_ID
    ]
    if not physical_rows:
        raise RuntimeError("physical Inter Miami slot has no replaceable assignments")

    kept: list[bytes] = []
    removed: list[dict[str, Any]] = []
    removed_assignment_ids: list[int] = []
    preserved_national: list[dict[str, Any]] = []
    insert_at: int | None = None
    target_set = set(target_ids)
    for raw_row, (_assignment_id, player_id, team_id, _packed) in zip(
        current_rows, parsed_current
    ):
        if team_id == INTER_MIAMI_PHYSICAL_TEAM_ID:
            if insert_at is None:
                insert_at = len(kept)
            continue
        if player_id in target_set:
            kind = team_kinds.get(team_id)
            if kind == "national":
                preserved_national.append(
                    {"player_id": player_id, "team_id": team_id}
                )
            elif kind == "club":
                removed.append({"player_id": player_id, "team_id": team_id})
                removed_assignment_ids.append(_assignment_id)
                continue
            else:
                raise RuntimeError(
                    f"cannot classify existing membership player={player_id} team={team_id}"
                )
        kept.append(raw_row)
    if insert_at is None:
        raise RuntimeError("physical Inter Miami assignment insertion point is missing")

    # Reuse IDs from the replaced physical roster and removed legacy rows. No
    # new assignment identity is appended to the database.
    reusable_ids = [row[0] for row in physical_rows] + removed_assignment_ids
    if len(reusable_ids) < len(target_ids):
        raise RuntimeError("not enough removed PlayerAssignment IDs to reuse")

    inter_miami_rows: list[bytes] = []
    for index, player_id in enumerate(target_ids):
        source_fields, _order = source_by_player[player_id]
        template_flags = (
            physical_rows[index][3] & 0xFFFF0000
            if index < len(physical_rows)
            else 0
        )
        packed = template_flags | source_fields
        inter_miami_rows.append(
            struct.pack(
                "<IIII",
                reusable_ids[index],
                player_id,
                INTER_MIAMI_PHYSICAL_TEAM_ID,
                packed,
            )
        )
    merged_rows = kept[:insert_at] + inter_miami_rows + kept[insert_at:]
    parsed_merged = [struct.unpack("<IIII", row) for row in merged_rows]
    merged_assignment_ids = [row[0] for row in parsed_merged]
    if len(merged_assignment_ids) != len(set(merged_assignment_ids)):
        raise RuntimeError("merged PlayerAssignment.bin has duplicate assignment IDs")

    memberships: dict[int, list[int]] = {player_id: [] for player_id in target_ids}
    for _assignment_id, player_id, team_id, _packed in parsed_merged:
        if player_id in memberships:
            memberships[player_id].append(team_id)
    for player_id, team_ids in memberships.items():
        if team_ids.count(INTER_MIAMI_PHYSICAL_TEAM_ID) != 1:
            raise RuntimeError(
                f"player {player_id} does not have exactly one Inter Miami membership"
            )
        stale_clubs = [
            team_id
            for team_id in team_ids
            if team_id != INTER_MIAMI_PHYSICAL_TEAM_ID
            and team_kinds.get(team_id) == "club"
        ]
        if stale_clubs:
            raise RuntimeError(
                f"player {player_id} retains stale club memberships: {stale_clubs}"
            )

    removed.sort(key=lambda row: (row["player_id"], row["team_id"]))
    preserved_national.sort(key=lambda row: (row["player_id"], row["team_id"]))
    expected_removed: set[tuple[int, int]] = set()
    expected_preserved: set[tuple[int, int]] = set()
    for player in shared_memberships:
        player_id = int(player["player_id"])
        for membership in player.get("existing_pes21_memberships", []):
            pair = (player_id, int(membership["pes21_team_id"]))
            action = membership.get("cleanup_action")
            if action == "remove_legacy_club_membership":
                expected_removed.add(pair)
            elif action == "preserve_national_membership":
                expected_preserved.add(pair)
            else:
                raise RuntimeError(f"unknown Inter Miami cleanup action: {action}")
    observed_removed = {(row["player_id"], row["team_id"]) for row in removed}
    observed_preserved = {
        (row["player_id"], row["team_id"]) for row in preserved_national
    }
    if observed_removed != expected_removed:
        raise RuntimeError(
            "legacy club membership set changed: "
            f"observed={sorted(observed_removed)}, expected={sorted(expected_removed)}"
        )
    if observed_preserved != expected_preserved:
        raise RuntimeError(
            "national membership set changed: "
            f"observed={sorted(observed_preserved)}, "
            f"expected={sorted(expected_preserved)}"
        )
    return b"".join(merged_rows), {
        "records_before": len(current_rows),
        "records_after": len(merged_rows),
        "physical_roster_replaced": len(physical_rows),
        "inter_miami_memberships_added": len(inter_miami_rows),
        "legacy_club_memberships_removed": len(removed),
        "national_memberships_preserved": len(preserved_national),
        "removed": removed,
        "preserved_national": preserved_national,
        "target_memberships": {
            str(player_id): memberships[player_id] for player_id in target_ids
        },
    }


def patch_fixed_ascii(row: bytearray, offset: int, size: int, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) >= size:
        raise ValueError(f"ASCII value does not fit {size}-byte field: {value}")
    row[offset : offset + size] = encoded + bytes(size - len(encoded))


def patch_team_table(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    rows = [bytearray(row) for row in split_rows(raw, TEAM_SIZE, "Team.bin")]
    matches = [
        index
        for index, row in enumerate(rows)
        if struct.unpack_from("<I", row, TEAM_ID_OFFSET)[0]
        == INTER_MIAMI_PHYSICAL_TEAM_ID
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one physical team {INTER_MIAMI_PHYSICAL_TEAM_ID}, found {len(matches)}"
        )
    index = matches[0]
    row = rows[index]
    old_name = bytes(row[TEAM_NAME_OFFSET : TEAM_NAME_OFFSET + TEAM_NAME_SIZE])
    old_name = old_name.split(b"\0", 1)[0].decode("ascii", errors="replace")
    old_codes = [
        bytes(row[offset : offset + 4]).split(b"\0", 1)[0].decode("ascii", errors="replace")
        for offset in TEAM_SHORT_CODE_OFFSETS
    ]
    patch_fixed_ascii(row, TEAM_NAME_OFFSET, TEAM_NAME_SIZE, INTER_MIAMI_NAME)
    for offset in TEAM_SHORT_CODE_OFFSETS:
        patch_fixed_ascii(row, offset, 4, INTER_MIAMI_SHORT_CODE)
    return b"".join(bytes(item) for item in rows), {
        "physical_team_id": INTER_MIAMI_PHYSICAL_TEAM_ID,
        "record_index": index,
        "old_name": old_name,
        "new_name": INTER_MIAMI_NAME,
        "old_short_codes": old_codes,
        "new_short_code": INTER_MIAMI_SHORT_CODE,
        "unrelated_team_rows_byte_identical": len(rows) - 1,
    }


def load_uniform_definitions(source_dir: Path) -> dict[str, bytes]:
    source_by_kind = {
        "1st": source_dir / "5738_DEF_1st.bin",
        "2nd": source_dir / "5738_DEF_2nd.bin",
        "GK1st": source_dir / "5738_DEF_GK1st.bin",
    }
    replacements: dict[str, bytes] = {}
    for kind, source in source_by_kind.items():
        raw = decode_wesys_bytes(source.read_bytes(), f"EF10 {source.name}")
        if len(raw) != 96:
            raise RuntimeError(f"{source}: expected 96 decoded bytes, found {len(raw)}")
        replacements[
            f"common/etc/uniform/team/2473/2473_DEF_{kind}.bin"
        ] = raw
    return replacements


def load_logo_replacements(source_dir: Path) -> dict[str, bytes]:
    sources = {
        "common/render/symbol/flag/e_002473_f.png": source_dir
        / "experimental_inter_miami_logo.png",
        "common/render/symbol/flag/e_002473_f_l.png": source_dir
        / "experimental_inter_miami_logo_l.png",
        "common/render/symbol/flag/e_002473_f_s.png": source_dir
        / "experimental_inter_miami_logo_s.png",
    }
    png_signature = b"\x89PNG\r\n\x1a\n"
    result: dict[str, bytes] = {}
    for member, source in sources.items():
        payload = source.read_bytes()
        if not payload.startswith(png_signature):
            raise RuntimeError(f"{source}: invalid PNG")
        result[member] = payload
    return result


def load_portrait_replacements(
    portrait_dir: Path, players: list[dict[str, Any]]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Map each experimental player to a real EF10 PNG in a PES21 slot.

    Original EF10 IDs use the retired PES21 donor slot that the runtime maps
    in ``experimental_inter_miami_portrait_id``. Shared IDs keep their native
    slot, allowing the same package to cover the entire 27-player roster.
    """
    png_signature = b"\x89PNG\r\n\x1a\n"
    replacements: dict[str, bytes] = {}
    mapping: list[dict[str, Any]] = []
    for row in players:
        target_id = int(row["target_pes21_id"])
        slot_id = int(row.get("donor_pes21_id") or target_id)
        source = portrait_dir / f"{target_id}.png"
        if not source.is_file():
            raise FileNotFoundError(
                f"missing EF10 portrait for player {target_id}: {source}"
            )
        payload = source.read_bytes()
        if not payload.startswith(png_signature):
            raise RuntimeError(f"{source}: invalid PNG portrait")
        member = f"{PORTRAIT_MEMBER_PREFIX}{slot_id}.png"
        if member in replacements:
            raise RuntimeError(f"duplicate portrait slot: {member}")
        replacements[member] = payload
        mapping.append(
            {
                "target_pes21_id": target_id,
                "portrait_slot_id": slot_id,
                "source": str(source),
                "size": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    return replacements, {
        "count": len(mapping),
        "members": sorted(replacements),
        "mapping": mapping,
    }


def load_experiment(artifact: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    report_path = artifact / "validation-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("experiment") != "inter_miami_original_id" or report.get("mode") != "full":
        raise RuntimeError("release experiment requires the Inter Miami full artifact")
    players = report.get("players")
    if not isinstance(players, list) or len(players) != 27:
        raise RuntimeError("Inter Miami full artifact must contain exactly 27 players")
    if int(report.get("team", {}).get("pes21_physical_team_id", 0)) != INTER_MIAMI_PHYSICAL_TEAM_ID:
        raise RuntimeError("full artifact targets a different physical team slot")
    if int(players[0].get("registered_position", -1)) != 0:
        raise RuntimeError("Inter Miami runtime roster must start with a goalkeeper")
    return report, players


def validate_rebuilt_cpk(
    base: Path,
    rebuilt: Path,
    *,
    expected_member_count: int,
    expected_changed: tuple[str, ...],
) -> dict[str, Any]:
    _old_header, old_rows, old_base = cpk_index(base)
    _new_header, new_rows, new_base = cpk_index(rebuilt)
    if set(old_rows) != set(new_rows) or len(old_rows) != expected_member_count:
        raise RuntimeError("rebuilt dt200 changed the CPK member set")
    changed: list[str] = []
    unrelated = 0
    with base.open("rb") as old, rebuilt.open("rb") as new:
        for name, old_row in old_rows.items():
            new_row = new_rows[name]
            old.seek(old_base + int(old_row["FileOffset"]))
            old_payload = old.read(int(old_row["FileSize"]))
            new.seek(new_base + int(new_row["FileOffset"]))
            new_payload = new.read(int(new_row["FileSize"]))
            if old_payload != new_payload:
                changed.append(name)
            else:
                unrelated += 1
    if set(changed) != set(expected_changed):
        raise RuntimeError(f"unexpected changed CPK members: {changed}")
    return {
        "member_count": len(new_rows),
        "changed_members": sorted(changed),
        "unrelated_members_byte_identical": unrelated,
        "size": rebuilt.stat().st_size,
        "sha256": sha256_file(rebuilt),
    }


def validate_obb_base(
    obb: Path,
    current_dt200: Path,
    current_dt240: Path,
    current_dt241: Path,
    current_dt210: Path,
) -> dict[str, Any]:
    _header, rows, data_base = cpk_index(obb)
    bases = {
        OBB_DT200_MEMBER: current_dt200,
        OBB_DT240_MEMBER: current_dt240,
        OBB_DT241_MEMBER: current_dt241,
    }
    slots: dict[str, Any] = {}
    with obb.open("rb") as source:
        for member, current_cpk in bases.items():
            row = rows.get(member)
            if not row:
                raise RuntimeError(f"release OBB is missing {member}")
            source.seek(data_base + int(row["FileOffset"]))
            payload = source.read(int(row["FileSize"]))
            observed = sha256_bytes(payload)
            expected = sha256_file(current_cpk)
            if observed != expected:
                raise RuntimeError(
                    f"release OBB {member} differs from merge base: "
                    f"{observed} != {expected}"
                )
            slots[member] = {
                "size": int(row["FileSize"]),
                "sha256": observed,
            }
        scoreboard_row = rows.get(OBB_DT210_MEMBER)
        if not scoreboard_row:
            raise RuntimeError(f"release OBB is missing {OBB_DT210_MEMBER}")
        scoreboard_size = current_dt210.stat().st_size
        if scoreboard_size != int(scoreboard_row["FileSize"]):
            raise RuntimeError(
                "latest scoreboard size does not fit its fixed OBB slot: "
                f"{scoreboard_size} != {int(scoreboard_row['FileSize'])}"
            )
        source.seek(data_base + int(scoreboard_row["FileOffset"]))
        base_scoreboard = source.read(int(scoreboard_row["FileSize"]))
        slots[OBB_DT210_MEMBER] = {
            "size": int(scoreboard_row["FileSize"]),
            "sha256": sha256_bytes(base_scoreboard),
            "replacement_sha256": sha256_file(current_dt210),
        }
    return {
        "path": str(obb),
        "size": obb.stat().st_size,
        "sha256": sha256_file(obb),
        "member_count": len(rows),
        "slots": slots,
    }


def validate_patched_obb(
    base: Path,
    patched: Path,
    dt200: Path,
    dt210: Path,
    dt240: Path,
    dt241: Path,
) -> dict[str, Any]:
    _old_header, old_rows, old_base = cpk_index(base)
    _new_header, new_rows, new_base = cpk_index(patched)
    if set(old_rows) != set(new_rows):
        raise RuntimeError("experimental OBB changed the outer member set")
    replacements = {
        OBB_DT200_MEMBER: sha256_file(dt200),
        OBB_DT210_MEMBER: sha256_file(dt210),
        OBB_DT240_MEMBER: sha256_file(dt240),
        OBB_DT241_MEMBER: sha256_file(dt241),
    }
    changed: list[str] = []
    unchanged = 0
    with base.open("rb") as old, patched.open("rb") as new:
        for name, old_row in old_rows.items():
            new_row = new_rows[name]
            old.seek(old_base + int(old_row["FileOffset"]))
            old_payload = old.read(int(old_row["FileSize"]))
            new.seek(new_base + int(new_row["FileOffset"]))
            new_payload = new.read(int(new_row["FileSize"]))
            if name in replacements:
                if sha256_bytes(new_payload) != replacements[name]:
                    raise RuntimeError(f"experimental OBB replacement mismatch: {name}")
                if old_payload != new_payload:
                    changed.append(name)
            elif old_payload != new_payload:
                raise RuntimeError(f"unrelated OBB member changed: {name}")
            else:
                unchanged += 1
    if set(changed) != set(replacements):
        raise RuntimeError(f"unexpected changed OBB members: {changed}")
    return {
        "path": str(patched),
        "size": patched.stat().st_size,
        "sha256": sha256_file(patched),
        "member_count": len(new_rows),
        "changed_members": sorted(changed),
        "unrelated_members_byte_identical": unchanged,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    current_cpk = resolve(args.current_cpk)
    current_dt210 = resolve(args.current_dt210)
    current_dt240 = resolve(args.current_dt240)
    current_dt241 = resolve(args.current_dt241)
    ef10_assignments = resolve(args.ef10_assignments)
    ef10_categories = resolve(args.ef10_categories)
    catalog = resolve(args.catalog)
    artifact = resolve(args.artifact)
    output_dir = resolve(args.output_dir)
    release_obb = resolve(args.release_obb)
    uniform_source = resolve(args.uniform_source)
    logo_source = resolve(args.logo_source)
    portrait_dir = resolve(args.portrait_dir)
    report, players = load_experiment(artifact)
    current_members = read_members(current_cpk, DT200_REPLACED_MEMBERS)
    artifact_player = (artifact / "Player.bin").read_bytes()

    donor_to_target = {
        int(row["donor_pes21_id"]): int(row["target_pes21_id"])
        for row in players
        if row.get("donor_pes21_id") is not None
    }
    current_player_raw = decode_wesys_bytes(
        current_members["common/etc/pesdb/Player.bin"], "current Player.bin"
    )
    experiment_player_raw = decode_wesys_bytes(artifact_player, "full Player.bin")
    merged_player_raw, player_merge = merge_player_table(
        current_player_raw, experiment_player_raw, players
    )
    current_install_raw = decode_wesys_bytes(
        current_members["common/etc/pesdb/InstallVersionPlayer.bin"],
        "current InstallVersionPlayer.bin",
    )
    current_delete_raw = decode_wesys_bytes(
        current_members["common/etc/pesdb/PlayerDeleteList.bin"],
        "current PlayerDeleteList.bin",
    )
    merged_install_raw = merge_install_versions(current_install_raw, donor_to_target)
    merged_delete_raw = merge_delete_list(current_delete_raw, set(donor_to_target))
    current_assignment_raw = decode_wesys_bytes(
        current_members["common/etc/pesdb/PlayerAssignment.bin"],
        "current PlayerAssignment.bin",
    )
    merged_assignment_raw, assignment_cleanup = patch_player_assignments(
        current_assignment_raw,
        decode_wesys_bytes(ef10_assignments.read_bytes(), "EF10 PlayerAssignment.bin"),
        players,
        load_catalog_team_kinds(catalog),
        report.get("shared_memberships", []),
    )
    league_membership = validate_ef10_league(
        decode_wesys_bytes(ef10_categories.read_bytes(), "EF10 CategoryTeamList.bin")
    )

    player_ids = {
        player_id(row)
        for row in split_rows(merged_player_raw, PLAYER_SIZE, "merged Player.bin")
    }
    install_ids = {
        struct.unpack_from("<I", row, 0)[0]
        for row in split_rows(
            merged_install_raw, INSTALL_VERSION_SIZE, "merged InstallVersionPlayer.bin"
        )
    }
    if player_ids != install_ids:
        raise RuntimeError("merged Player and InstallVersion ID sets differ")
    delete_ids = {
        struct.unpack_from("<I", row, 0)[0]
        for row in split_rows(merged_delete_raw, DELETE_SIZE, "merged PlayerDeleteList.bin")
    }
    if set(donor_to_target) & delete_ids:
        raise RuntimeError("a retired donor remains in the merged delete list")

    current_team_raw = decode_wesys_bytes(
        current_members["common/etc/pesdb/Team.bin"], "current Team.bin"
    )
    merged_team_raw, team_patch = patch_team_table(current_team_raw)
    uniform_replacements = load_uniform_definitions(uniform_source)
    logo_replacements = load_logo_replacements(logo_source)
    portrait_replacements, portrait_report = load_portrait_replacements(
        portrait_dir, players
    )
    if set(uniform_replacements) != {
        member for member in DT200_REPLACED_MEMBERS if "/uniform/" in member
    }:
        raise RuntimeError("uniform replacement set is incomplete")
    if set(logo_replacements) != set(DT240_REPLACED_MEMBERS):
        raise RuntimeError("logo replacement set is incomplete")
    _dt210_header, dt210_rows, _dt210_base = cpk_index(current_dt210)
    if len(dt210_rows) != EXPECTED_DT210_MEMBERS:
        raise RuntimeError(
            f"latest scoreboard member count changed: {len(dt210_rows)}"
        )
    _dt241_header, dt241_rows, _dt241_base = cpk_index(current_dt241)
    if len(dt241_rows) != EXPECTED_DT241_MEMBERS:
        raise RuntimeError(
            f"portrait base member count changed: {len(dt241_rows)}"
        )
    missing_portrait_slots = sorted(set(portrait_replacements) - set(dt241_rows))
    if missing_portrait_slots:
        raise RuntimeError(
            f"portrait base is missing mapped slots: {missing_portrait_slots}"
        )

    release_preflight = validate_obb_base(
        release_obb, current_cpk, current_dt240, current_dt241, current_dt210
    )

    preflight = {
        "current_cpk": str(current_cpk),
        "current_cpk_size": current_cpk.stat().st_size,
        "current_cpk_sha256": sha256_file(current_cpk),
        "latest_scoreboard": str(current_dt210),
        "latest_scoreboard_size": current_dt210.stat().st_size,
        "latest_scoreboard_sha256": sha256_file(current_dt210),
        "current_dt240": str(current_dt240),
        "current_dt240_size": current_dt240.stat().st_size,
        "current_dt240_sha256": sha256_file(current_dt240),
        "current_dt241": str(current_dt241),
        "current_dt241_size": current_dt241.stat().st_size,
        "current_dt241_sha256": sha256_file(current_dt241),
        "artifact": str(artifact),
        "artifact_player_sha256": sha256_file(artifact / "Player.bin"),
        "artifact_mode": report["mode"],
        "player_merge": player_merge,
        "assignment_cleanup": assignment_cleanup,
        "league_membership": league_membership,
        "team_patch": team_patch,
        "uniform_definitions": {
            member: {"size": len(payload), "sha256": sha256_bytes(payload)}
            for member, payload in sorted(uniform_replacements.items())
        },
        "native_logos": {
            member: {"size": len(payload), "sha256": sha256_bytes(payload)}
            for member, payload in sorted(logo_replacements.items())
        },
        "ef10_portraits": portrait_report,
        "release_obb": release_preflight,
    }
    if args.check:
        return {"check": "pass", "preflight": preflight}

    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        raise RuntimeError(f"refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    dt200_replacements = {
        "common/etc/pesdb/Player.bin": encode_wesys_compact(merged_player_raw),
        "common/etc/pesdb/InstallVersionPlayer.bin": encode_wesys_compact(
            merged_install_raw
        ),
        "common/etc/pesdb/PlayerDeleteList.bin": encode_wesys(merged_delete_raw),
        "common/etc/pesdb/PlayerAssignment.bin": encode_wesys_compact(
            merged_assignment_raw
        ),
        "common/etc/pesdb/Team.bin": encode_wesys_compact(merged_team_raw),
        **uniform_replacements,
    }
    replacement_manifest: dict[str, str] = {}
    for member, payload in dt200_replacements.items():
        filename = member.rsplit("/", 1)[-1]
        path = output_dir / filename
        path.write_bytes(payload)
        replacement_manifest[member] = filename
    manifest_path = output_dir / "dt200-replacement-manifest.json"
    manifest_path.write_text(
        json.dumps(replacement_manifest, indent=2) + "\n", encoding="utf-8"
    )

    logo_manifest: dict[str, str] = {}
    for member, payload in logo_replacements.items():
        filename = member.rsplit("/", 1)[-1]
        path = output_dir / filename
        path.write_bytes(payload)
        logo_manifest[member] = filename
    logo_manifest_path = output_dir / "dt240-replacement-manifest.json"
    logo_manifest_path.write_text(
        json.dumps(logo_manifest, indent=2) + "\n", encoding="utf-8"
    )

    portrait_output_dir = output_dir / "portraits"
    portrait_output_dir.mkdir(parents=True, exist_ok=True)
    portrait_manifest: dict[str, str] = {}
    for member, payload in portrait_replacements.items():
        filename = member.rsplit("/", 1)[-1]
        path = portrait_output_dir / filename
        path.write_bytes(payload)
        portrait_manifest[member] = str(Path("portraits") / filename)
    portrait_manifest_path = output_dir / "dt241-replacement-manifest.json"
    portrait_manifest_path.write_text(
        json.dumps(portrait_manifest, indent=2) + "\n", encoding="utf-8"
    )

    output_cpk = output_dir / "dt200_mobile_all_inter_miami_full.cpk"
    output_dt240 = output_dir / "dt240_mobile_all_inter_miami.cpk"
    output_dt241 = output_dir / "dt241_mobile_all_inter_miami_portraits.cpk"
    for output in (output_cpk, output_dt240, output_dt241):
        if not output.exists():
            continue
        if not args.force:
            raise RuntimeError(f"refusing to overwrite {output}")
        output.unlink()
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(current_cpk),
            str(output_cpk),
            "--expect-members",
            str(EXPECTED_DT200_MEMBERS),
            "--replace-manifest",
            str(manifest_path),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(current_dt241),
            str(output_dt241),
            "--expect-members",
            str(EXPECTED_DT241_MEMBERS),
            "--replace-manifest",
            str(portrait_manifest_path),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(current_dt240),
            str(output_dt240),
            "--expect-members",
            str(EXPECTED_DT240_MEMBERS),
            "--replace-manifest",
            str(logo_manifest_path),
        ],
        check=True,
    )
    dt200_result = validate_rebuilt_cpk(
        current_cpk,
        output_cpk,
        expected_member_count=EXPECTED_DT200_MEMBERS,
        expected_changed=DT200_REPLACED_MEMBERS,
    )
    dt240_result = validate_rebuilt_cpk(
        current_dt240,
        output_dt240,
        expected_member_count=EXPECTED_DT240_MEMBERS,
        expected_changed=DT240_REPLACED_MEMBERS,
    )
    dt241_result = validate_rebuilt_cpk(
        current_dt241,
        output_dt241,
        expected_member_count=EXPECTED_DT241_MEMBERS,
        expected_changed=tuple(portrait_replacements),
    )
    dt200_slot = release_preflight["slots"][OBB_DT200_MEMBER]
    dt210_slot = release_preflight["slots"][OBB_DT210_MEMBER]
    dt240_slot = release_preflight["slots"][OBB_DT240_MEMBER]
    dt241_slot = release_preflight["slots"][OBB_DT241_MEMBER]
    if output_cpk.stat().st_size > dt200_slot["size"]:
        raise RuntimeError(
            "experimental dt200 exceeds the fixed release OBB slot: "
            f"{output_cpk.stat().st_size} > {dt200_slot['size']}"
        )
    if output_dt240.stat().st_size > dt240_slot["size"]:
        raise RuntimeError(
            "experimental dt240 exceeds the fixed release OBB slot: "
            f"{output_dt240.stat().st_size} > {dt240_slot['size']}"
        )
    if current_dt210.stat().st_size > dt210_slot["size"]:
        raise RuntimeError(
            "latest scoreboard exceeds the fixed release OBB slot: "
            f"{current_dt210.stat().st_size} > {dt210_slot['size']}"
        )
    if output_dt241.stat().st_size > dt241_slot["size"]:
        raise RuntimeError(
            "experimental dt241 exceeds the fixed release OBB slot: "
            f"{output_dt241.stat().st_size} > {dt241_slot['size']}"
        )

    obb_result: dict[str, Any] | None = None
    output_obb = output_dir / "patch.305030001.jp.nyan2021.pesam.obb"
    if args.package_obb:
        if output_obb.exists():
            if not args.force:
                raise RuntimeError(f"refusing to overwrite {output_obb}")
            output_obb.unlink()
        sys.path.insert(0, str(ROOT / "tools"))
        from patch_cpk_slots import patch_slots

        patch_slots(
            release_obb,
            output_obb,
            {
                OBB_DT200_MEMBER: output_cpk,
                OBB_DT210_MEMBER: current_dt210,
                OBB_DT240_MEMBER: output_dt240,
                OBB_DT241_MEMBER: output_dt241,
            },
        )
        obb_result = validate_patched_obb(
            release_obb,
            output_obb,
            output_cpk,
            current_dt210,
            output_dt240,
            output_dt241,
        )

    if sha256_file(release_obb) != release_preflight["sha256"]:
        raise RuntimeError("standard release OBB changed during experiment packaging")

    result = {
        "schema_version": 1,
        "experiment": "inter_miami_original_id_release_merge",
        "mode": "full",
        "runtime_flag": "PES_EXPERIMENT_INTER_MIAMI=1",
        "stable_release_files_overwritten": False,
        "preflight": preflight,
        "outputs": {
            "dt200": {"path": str(output_cpk), **dt200_result},
            "dt210": {
                "path": str(current_dt210),
                "member_count": len(dt210_rows),
                "size": current_dt210.stat().st_size,
                "sha256": sha256_file(current_dt210),
            },
            "dt240": {"path": str(output_dt240), **dt240_result},
            "dt241": {"path": str(output_dt241), **dt241_result},
            "obb": obb_result,
            "replacement_sha256": {
                "dt200": {
                    member: sha256_bytes(payload)
                    for member, payload in sorted(dt200_replacements.items())
                },
                "dt240": {
                    member: sha256_bytes(payload)
                    for member, payload in sorted(logo_replacements.items())
                },
                "dt241": {
                    member: sha256_bytes(payload)
                    for member, payload in sorted(portrait_replacements.items())
                },
            },
        },
        "rollback": {
            "action": "restore the standard NRO and standard patch OBB; the experiment uses separate filenames",
            "standard_obb": str(release_obb),
            "standard_obb_modified": False,
        },
    }
    (output_dir / "release-experiment-validation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-cpk", type=Path, default=DEFAULT_CURRENT_CPK)
    parser.add_argument("--current-dt210", type=Path, default=DEFAULT_CURRENT_DT210)
    parser.add_argument("--current-dt240", type=Path, default=DEFAULT_CURRENT_DT240)
    parser.add_argument("--current-dt241", type=Path, default=DEFAULT_CURRENT_DT241)
    parser.add_argument(
        "--ef10-assignments", type=Path, default=DEFAULT_EF10_ASSIGNMENTS
    )
    parser.add_argument(
        "--ef10-categories", type=Path, default=DEFAULT_EF10_CATEGORIES
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_FULL_ARTIFACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--release-obb", type=Path, default=DEFAULT_RELEASE_OBB)
    parser.add_argument("--uniform-source", type=Path, default=DEFAULT_UNIFORM_SOURCE)
    parser.add_argument("--logo-source", type=Path, default=DEFAULT_LOGO_SOURCE)
    parser.add_argument("--portrait-dir", type=Path, default=DEFAULT_PORTRAIT_DIR)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--package-obb", action="store_true")
    parser.add_argument("--force", action="store_true")
    result = build(parser.parse_args())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
