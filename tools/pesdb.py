#!/usr/bin/env python3
"""Small, schema-specific readers for the PES21 and eFootball 10 tables."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MASK32 = 0xFFFFFFFF
KEY_CONSTANTS = {
    1: (378445824, 774547186, 214490323),
    2: (3982174560, 1246903118, 4087552941),
}

EF10_TEAM_RECORD_SIZE = 1600
EF10_TEAM_ID_OFFSET = 12
EF10_TEAM_ENGLISH_NAME_OFFSET = 396
PES21_TEAM_RECORD_SIZE = 1532
PES21_TEAM_ID_OFFSET = 8
PES21_TEAM_ENGLISH_NAME_OFFSET = 368
TEAM_NAME_FIELD_SIZE = 70

EF10_PLAYER_RECORD_SIZE = 392
PES21_PLAYER_RECORD_SIZE = 312
PLAYER_ID_OFFSET = 8

EF10_ASSIGNMENT_RECORD_SIZE = 24
PES21_ASSIGNMENT_RECORD_SIZE = 16
TACTICS_RECORD_SIZE = 12
CATEGORY_TEAM_LIST_RECORD_SIZE = 12


@dataclass(frozen=True)
class TeamRecord:
    team_id: int
    name: str


@dataclass(frozen=True)
class PlayerAssignment:
    player_id: int
    team_id: int
    order: int
    shirt: int


@dataclass(frozen=True)
class CategoryTeamEntry:
    team_id: int
    category_id: int
    order: int


def decode_wesys(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) < 16 or data[3:8] != b"WESYS":
        raise ValueError(f"{path}: invalid WESYS header")

    compressed_size, raw_size = struct.unpack_from("<II", data, 8)
    payload = bytearray(data[16 : 16 + compressed_size])
    if len(payload) != compressed_size:
        raise ValueError(f"{path}: truncated compressed payload")

    key_index = data[1] & 0x0F
    if key_index in KEY_CONSTANTS:
        x, y, z = KEY_CONSTANTS[key_index]
        w = ((raw_size << 16) | compressed_size) & MASK32
        # The final partial word is not encrypted.
        for offset in range(0, len(payload) - 3, 4):
            t = (x ^ (x << 11)) & MASK32
            x, y, z, previous = y, z, w, w
            w = (previous ^ (((previous >> 11) ^ t) >> 8) ^ t) & MASK32
            word = struct.unpack_from("<I", payload, offset)[0] ^ w
            struct.pack_into("<I", payload, offset, word)

    raw = zlib.decompress(payload)
    if len(raw) != raw_size:
        raise ValueError(f"{path}: decoded {len(raw)} bytes, expected {raw_size}")
    return raw


def split_records(raw: bytes, record_size: int, label: str) -> list[bytes]:
    if len(raw) % record_size:
        raise ValueError(f"{label} does not contain {record_size}-byte records")
    return [raw[offset : offset + record_size] for offset in range(0, len(raw), record_size)]


def _decode_name(value: bytes) -> str:
    return value.split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()


def parse_team_records(raw: bytes, schema: str) -> dict[int, TeamRecord]:
    if schema == "ef10":
        record_size = EF10_TEAM_RECORD_SIZE
        id_offset = EF10_TEAM_ID_OFFSET
        name_offset = EF10_TEAM_ENGLISH_NAME_OFFSET
    elif schema == "pes21":
        record_size = PES21_TEAM_RECORD_SIZE
        id_offset = PES21_TEAM_ID_OFFSET
        name_offset = PES21_TEAM_ENGLISH_NAME_OFFSET
    else:
        raise ValueError(f"unknown Team.bin schema: {schema}")

    result: dict[int, TeamRecord] = {}
    for record in split_records(raw, record_size, f"{schema} Team.bin"):
        team_id = struct.unpack_from("<I", record, id_offset)[0]
        if not team_id or team_id in result:
            raise ValueError(f"{schema} Team.bin has invalid duplicate team ID {team_id}")
        name = _decode_name(record[name_offset : name_offset + TEAM_NAME_FIELD_SIZE])
        if not name:
            raise ValueError(f"{schema} Team.bin team {team_id} has no English name")
        result[team_id] = TeamRecord(team_id=team_id, name=name)
    return result


def parse_player_ids(raw: bytes, schema: str) -> set[int]:
    if schema == "ef10":
        record_size = EF10_PLAYER_RECORD_SIZE
        id_format = "<Q"
    elif schema == "pes21":
        record_size = PES21_PLAYER_RECORD_SIZE
        id_format = "<I"
    else:
        raise ValueError(f"unknown Player.bin schema: {schema}")

    result: set[int] = set()
    for record in split_records(raw, record_size, f"{schema} Player.bin"):
        player_id = struct.unpack_from(id_format, record, PLAYER_ID_OFFSET)[0]
        if not player_id or player_id in result:
            raise ValueError(
                f"{schema} Player.bin has invalid duplicate player ID {player_id}"
            )
        result.add(player_id)
    return result


def parse_ef10_assignments(raw: bytes) -> dict[int, list[PlayerAssignment]]:
    result: dict[int, list[PlayerAssignment]] = {}
    for row in split_records(raw, EF10_ASSIGNMENT_RECORD_SIZE, "EF10 PlayerAssignment.bin"):
        player_id, team_id, _assignment_id, packed, _padding = struct.unpack(
            "<QIIII", row
        )
        result.setdefault(team_id, []).append(
            PlayerAssignment(
                player_id=player_id,
                team_id=team_id,
                order=(packed >> 8) & 0xFF,
                shirt=packed & 0xFF,
            )
        )
    return _sort_unique_assignments(result, "EF10")


def parse_pes21_assignments(raw: bytes) -> dict[int, list[PlayerAssignment]]:
    result: dict[int, list[PlayerAssignment]] = {}
    for row in split_records(raw, PES21_ASSIGNMENT_RECORD_SIZE, "PES21 PlayerAssignment.bin"):
        _assignment_id, player_id, team_id, packed = struct.unpack("<IIII", row)
        result.setdefault(team_id, []).append(
            PlayerAssignment(
                player_id=player_id,
                team_id=team_id,
                order=(packed >> 8) & 0xFF,
                shirt=packed & 0xFF,
            )
        )
    return _sort_unique_assignments(result, "PES21")


def _sort_unique_assignments(
    assignments: dict[int, list[PlayerAssignment]], label: str
) -> dict[int, list[PlayerAssignment]]:
    for team_id, roster in assignments.items():
        roster.sort(key=lambda item: (item.order, item.player_id))
        player_ids = [item.player_id for item in roster]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError(f"{label} team {team_id} contains duplicate player IDs")
    return assignments


def parse_category_team_list(raw: bytes) -> dict[int, list[CategoryTeamEntry]]:
    result: dict[int, list[CategoryTeamEntry]] = {}
    for row in split_records(
        raw, CATEGORY_TEAM_LIST_RECORD_SIZE, "EF10 CategoryTeamList.bin"
    ):
        team_id, category_id, order = struct.unpack("<III", row)
        result.setdefault(category_id, []).append(
            CategoryTeamEntry(team_id=team_id, category_id=category_id, order=order)
        )
    for entries in result.values():
        entries.sort(key=lambda item: (item.order, item.team_id))
    return result


def parse_tactics_team_ids(raw: bytes, schema: str) -> set[int]:
    team_ids: set[int] = set()
    for row in split_records(raw, TACTICS_RECORD_SIZE, f"{schema} Tactics.bin"):
        first, second, _flags = struct.unpack("<III", row)
        if schema == "ef10":
            team_ids.add(first)
        elif schema == "pes21":
            team_ids.add(second)
        else:
            raise ValueError(f"unknown Tactics.bin schema: {schema}")
    return team_ids
