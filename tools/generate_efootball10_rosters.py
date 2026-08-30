#!/usr/bin/env python3
"""Generate PES21-compatible Exhibition rosters from eFootball 10 tables.

The eFootball 10 database uses a newer Player record layout and 64-bit player
IDs. The Switch port still resolves players through a PES21-schema CommonWork
master database, so this generator imports only membership, ordering, and
shirt numbers for player IDs available in the selected PES21-schema table.
That table may be either the original PES21 Player.bin or the extended output
from convert_efootball10_players.py.

Unavailable players are listed in the generated report and are not inserted
as dangling IDs. A small number of players from the existing roster is
retained when necessary to keep a usable 18-player match squad.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MASK32 = 0xFFFFFFFF
EF10_PLAYER_RECORD_SIZE = 392
PES21_PLAYER_RECORD_SIZE = 312
EF10_ASSIGNMENT_RECORD_SIZE = 24
MIN_COMPATIBLE_PLAYERS = 11
MIN_MATCH_SQUAD = 18
MAX_MATCH_SQUAD = 40

KEY_CONSTANTS = {
    1: (378445824, 774547186, 214490323),
    2: (3982174560, 1246903118, 4087552941),
}


@dataclass(frozen=True)
class Assignment:
    player_id: int
    team_id: int
    order: int
    shirt: int


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
        raise ValueError(
            f"{path}: decoded {len(raw)} bytes, expected {raw_size}"
        )
    return raw


def parse_c_arrays(paths: list[Path]) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    players: dict[str, list[int]] = {}
    shirts: dict[str, list[int]] = {}
    pattern = re.compile(
        r"static\s+const\s+uint(32|8)_t\s+"
        r"exhibition_([a-z0-9_]+)_(players|shirts)\[\]\s*=\s*\{(.*?)\};",
        re.DOTALL,
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for width, name, kind, body in pattern.findall(text):
            values = [int(value) for value in re.findall(r"\b(\d+)u?\b", body)]
            target = players if kind == "players" else shirts
            target[name] = values
    return players, shirts


def parse_team_symbols(source: Path, nations: Path) -> dict[int, str]:
    text = source.read_text(encoding="utf-8")
    result = {
        int(team_id): symbol
        for team_id, symbol in re.findall(
            r"\{\s*(\d+),\s*exhibition_([a-z0-9_]+)_players,",
            text,
        )
    }
    nation_text = nations.read_text(encoding="utf-8")
    for symbol, team_id in re.findall(
        r"EXHIBITION_NATION\(\s*([a-z0-9_]+)\s*,\s*(\d+)", nation_text
    ):
        result[int(team_id)] = symbol
    return result


def parse_nation_team_ids(nations: Path) -> set[int]:
    return {
        int(team_id)
        for team_id in re.findall(
            r"EXHIBITION_NATION\(\s*[a-z0-9_]+\s*,\s*(\d+)",
            nations.read_text(encoding="utf-8"),
        )
    }


def parse_pes21_player_ids(raw: bytes) -> set[int]:
    if len(raw) % PES21_PLAYER_RECORD_SIZE:
        raise ValueError("PES21 Player.bin does not contain 312-byte records")
    return {
        struct.unpack_from("<I", raw, offset + 8)[0]
        for offset in range(0, len(raw), PES21_PLAYER_RECORD_SIZE)
    }


def parse_ef10_player_names(raw: bytes) -> dict[int, str]:
    if len(raw) % EF10_PLAYER_RECORD_SIZE:
        raise ValueError("EF10 Player.bin does not contain 392-byte records")
    result: dict[int, str] = {}
    for offset in range(0, len(raw), EF10_PLAYER_RECORD_SIZE):
        player_id = struct.unpack_from("<Q", raw, offset + 8)[0]
        name_bytes = raw[offset + 328 : offset + EF10_PLAYER_RECORD_SIZE]
        result[player_id] = name_bytes.split(b"\0", 1)[0].decode(
            "utf-8", errors="replace"
        )
    return result


def parse_ef10_assignments(raw: bytes) -> dict[int, list[Assignment]]:
    if len(raw) % EF10_ASSIGNMENT_RECORD_SIZE:
        raise ValueError("EF10 PlayerAssignment.bin does not contain 24-byte records")
    teams: dict[int, list[Assignment]] = {}
    for offset in range(0, len(raw), EF10_ASSIGNMENT_RECORD_SIZE):
        player_id, team_id, _assignment_id, packed, _padding = struct.unpack_from(
            "<QIIII", raw, offset
        )
        teams.setdefault(team_id, []).append(
            Assignment(
                player_id=player_id,
                team_id=team_id,
                # The upper bits are assignment flags, not appointment order.
                order=(packed >> 8) & 0xFF,
                shirt=packed & 0xFF,
            )
        )
    for assignments in teams.values():
        assignments.sort(key=lambda item: (item.order, item.player_id))
    return teams


def wrapped_values(values: list[int], suffix: str, per_line: int = 8) -> str:
    lines = []
    for index in range(0, len(values), per_line):
        chunk = ", ".join(f"{value}{suffix}" for value in values[index : index + per_line])
        lines.append(f"    {chunk},")
    return "\n".join(lines)


def build_roster(
    assignments: list[Assignment],
    available_ids: set[int],
    surrogate_map: dict[int, int],
    old_players: list[int],
    old_shirts: list[int],
) -> tuple[list[tuple[int, int]], list[Assignment], int]:
    compatible: list[tuple[int, int]] = []
    missing: list[Assignment] = []
    source_seen: set[int] = set()
    resolved_seen: set[int] = set()
    for assignment in assignments:
        if assignment.player_id in source_seen:
            continue
        source_seen.add(assignment.player_id)
        resolved_id = assignment.player_id
        if resolved_id not in available_ids:
            resolved_id = surrogate_map.get(assignment.player_id, 0)
        if resolved_id in available_ids and resolved_id not in resolved_seen:
            compatible.append((resolved_id, assignment.shirt))
            resolved_seen.add(resolved_id)
        else:
            missing.append(assignment)

    fallback_count = 0
    if len(compatible) >= MIN_COMPATIBLE_PLAYERS:
        for player_id, shirt in zip(old_players, old_shirts):
            if len(compatible) >= MIN_MATCH_SQUAD:
                break
            if player_id in resolved_seen:
                continue
            compatible.append((player_id, shirt))
            resolved_seen.add(player_id)
            fallback_count += 1
    return compatible[:MAX_MATCH_SQUAD], missing, fallback_count


def generate(args: argparse.Namespace) -> None:
    root = args.root.resolve()
    team_source_root = (
        args.team_source_root.resolve() if args.team_source_root else root
    )
    ef10_dir = root / args.ef10_dir
    pes21_dir = root / args.pes21_dir

    source = team_source_root / "source" / "ue4_hooks.c"
    nations = team_source_root / "source" / "exhibition_nations.inc"
    roster_sources = [path for path in [
        source,
        team_source_root / "source" / "exhibition_rosters.inc",
        team_source_root / "source" / "exhibition_migration.inc",
    ] if path.is_file()]
    old_players, old_shirts = parse_c_arrays(roster_sources)
    team_symbols = parse_team_symbols(source, nations)
    nation_team_ids = parse_nation_team_ids(nations)

    ef10_players_raw = decode_wesys(ef10_dir / "Player.bin")
    ef10_assignments_raw = decode_wesys(ef10_dir / "PlayerAssignment.bin")
    pes21_players_raw = decode_wesys(pes21_dir / "Player.bin")

    names = parse_ef10_player_names(ef10_players_raw)
    assignments_by_team = parse_ef10_assignments(ef10_assignments_raw)
    available_ids = parse_pes21_player_ids(pes21_players_raw)
    surrogate_map_path = root / args.surrogate_map
    surrogate_map: dict[int, int] = {}
    if surrogate_map_path.exists():
        payload = json.loads(surrogate_map_path.read_text(encoding="utf-8"))
        surrogate_map = {
            int(source_id): int(target_id)
            for source_id, target_id in payload.get("map", {}).items()
        }

    selected_team_ids: set[int] | None = None
    if args.team_id:
        selected_team_ids = {args.team_id}
        if args.include_related_nations:
            target_sources = {
                item.player_id
                for item in assignments_by_team.get(args.team_id, [])
                if item.player_id in available_ids or item.player_id in surrogate_map
            }
            selected_team_ids.update(
                team_id
                for team_id in nation_team_ids
                if any(
                    item.player_id in target_sources
                    for item in assignments_by_team.get(team_id, [])
                )
            )

    output_lines = [
        "// Generated by tools/generate_efootball10_rosters.py.",
        "// eFootball 10 membership/order/shirt data, restricted to player IDs",
        "// present in the selected PES21-schema master database. Do not edit manually.",
        "",
    ]
    map_entries: list[tuple[int, str]] = []
    report_rows: list[str] = []
    missing_sections: list[str] = []

    for team_id, symbol in sorted(team_symbols.items()):
        if selected_team_ids is not None and team_id not in selected_team_ids:
            continue
        assignments = assignments_by_team.get(team_id, [])
        base_players = old_players.get(symbol, [])
        base_shirts = old_shirts.get(symbol, [])
        if not assignments or not base_players or len(base_players) != len(base_shirts):
            continue

        roster, missing, fallback_count = build_roster(
            assignments,
            available_ids,
            surrogate_map,
            base_players,
            base_shirts,
        )
        compatible_count = sum(
            1
            for item in assignments
            if item.player_id in available_ids
            or surrogate_map.get(item.player_id, 0) in available_ids
        )
        if compatible_count < MIN_COMPATIBLE_PLAYERS:
            report_rows.append(
                f"| {team_id} | `{symbol}` | {len(assignments)} | "
                f"{compatible_count} | 0 | skipped (<{MIN_COMPATIBLE_PLAYERS}) |"
            )
            continue

        player_values = [player_id for player_id, _shirt in roster]
        shirt_values = [shirt for _player_id, shirt in roster]
        output_lines.extend(
            [
                f"static const uint32_t exhibition_ef10_{symbol}_players[] = {{",
                wrapped_values(player_values, "u"),
                "};",
                f"static const uint8_t exhibition_ef10_{symbol}_shirts[] = {{",
                wrapped_values(shirt_values, ""),
                "};",
                "",
            ]
        )
        map_entries.append((team_id, symbol))
        report_rows.append(
            f"| {team_id} | `{symbol}` | {len(assignments)} | "
            f"{compatible_count} | {fallback_count} | active ({len(roster)}) |"
        )
        if missing:
            lines = [f"### {team_id} / `{symbol}`", ""]
            for item in missing:
                lines.append(
                    f"- `{item.player_id}` — {names.get(item.player_id, '(unknown)')} "
                    f"(shirt {item.shirt})"
                )
            missing_sections.append("\n".join(lines))

    output_lines.extend(
        [
            "static const ExhibitionMasterRoster exhibition_ef10_master_rosters[] = {",
        ]
    )
    for team_id, symbol in map_entries:
        output_lines.extend(
            [
                "    {",
                f"        {team_id},",
                f"        exhibition_ef10_{symbol}_players,",
                f"        exhibition_ef10_{symbol}_shirts,",
                f"        sizeof(exhibition_ef10_{symbol}_players) /",
                f"            sizeof(exhibition_ef10_{symbol}_players[0]),",
                "    },",
            ]
        )
    output_lines.extend(["};", ""])

    output_path = root / args.output
    output_path.write_text("\n".join(output_lines), encoding="utf-8", newline="\n")

    report = [
        "# eFootball 10 Player/Roster Compatibility Update",
        "",
        "This report is generated from the locally supplied eFootball 10.0.0 XAPK.",
        "No source database records are redistributed: the compiled code contains only",
        "team membership IDs, order, and shirt numbers.",
        "Related national teams reuse the persistent surrogate ID selected for the",
        "same EF10 player in the converted club roster.",
        "",
        "## Result",
        "",
        "| Team ID | Symbol | EF10 entries | PES21-compatible | PES21 fallback | Status |",
        "|---:|---|---:|---:|---:|---|",
        *report_rows,
        "",
        "Players marked below exist in EF10 but not in the selected PES21-schema",
        "master database. They cannot be used safely by the current CommonWork runtime.",
        "",
        *missing_sections,
        "",
    ]
    report_path = root / args.report
    report_path.write_text("\n".join(report), encoding="utf-8", newline="\n")
    print(f"generated {output_path}")
    print(f"generated {report_path}")
    print(f"active EF10 team rosters: {len(map_entries)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--team-source-root",
        type=Path,
        help="optional source tree supplying the exposed team list and base rosters",
    )
    parser.add_argument(
        "--ef10-dir",
        default="local-debug/efootball10-audit/tables/common/etc/pesdb",
    )
    parser.add_argument(
        "--pes21-dir",
        default=(
            "local-debug/efootball10-audit/compare/"
            "old_dt200_mobile_all.cpk/common/etc/pesdb"
        ),
    )
    parser.add_argument("--output", default="source/exhibition_rosters_ef10.inc")
    parser.add_argument("--report", default="EFOOTBALL10_PLAYER_UPDATE.md")
    parser.add_argument(
        "--surrogate-map",
        default="local-debug/efootball10-player-patch/surrogate-map.json",
    )
    parser.add_argument(
        "--team-id",
        type=int,
        default=108,
        help="generate one proof-of-concept team; pass 0 to process all teams",
    )
    parser.add_argument(
        "--no-related-nations",
        action="store_false",
        dest="include_related_nations",
        help="do not refresh national teams containing converted club players",
    )
    parser.set_defaults(include_related_nations=True)
    generate(parser.parse_args())


if __name__ == "__main__":
    main()
