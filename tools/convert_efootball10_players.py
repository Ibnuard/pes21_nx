#!/usr/bin/env python3
"""Convert one EF10 team onto globally-unused native PES21 player slots.

PES21 Player.bin, PlayerAppearance.bin, and several auxiliary tables form a
parallel database. Appending Player.bin rows alone desynchronizes CommonWork
before Game Plan is created. This converter therefore keeps the original
record count and every PES21 unique ID. For each EF10-only player it allocates
a PES21 slot which is absent from every native PlayerAssignment and
SpecialPlayerAssignment row and from every stable custom runtime roster.
Surrogate slots are matched by registered position so a goalkeeper cannot
inherit a striker template. Four names and the 25 PES21-era displayed
abilities are converted from EF10. The roster generator consumes
surrogate-map.json so no unknown EF10 ID reaches the game.

PlayerAssignment.bin is copied byte-for-byte from PES21 because team membership
is installed by the runtime roster hook. TacticsFormation.bin is patched in
place: PES21 tactics IDs and record order are preserved, while the eleven
position/coordinate rows receive the corresponding EF10 team formation.
"""

from __future__ import annotations

import argparse
import collections
import json
import struct
import sys
import zlib
from pathlib import Path

from exhibition_team_catalog import (
    catalog_team_map,
    conversion_team_ids,
    load_catalog,
    parse_c_roster_arrays,
)
from pesdb import decode_wesys
from prepare_runtime import read_cpk_packet


EF10_PLAYER_SIZE = 392
PES21_PLAYER_SIZE = 312
EF10_ASSIGNMENT_SIZE = 24
PES21_ASSIGNMENT_SIZE = 16
TACTICS_SIZE = 12
TACTICS_FORMATION_SIZE = 12
EF10_NATIONALITY_OFFSET = 40
PES21_NATIONALITY_BIT = 232
PES21_NATIONALITY_WIDTH = 10

# Absolute LSB bit offsets in an EF10 392-byte Player.bin row.  Each ability
# is six bits and the displayed value is raw + 40.
EF10_ABILITY_BITS = {
    "set_piece_taking": 352,
    "gk_parrying": 358,
    "kicking_power": 364,
    "defensive_awareness": 370,
    "ball_control": 376,
    "heading": 384,
    "jumping": 390,
    "gk_catching": 396,
    "gk_reach": 402,
    "speed": 408,
    "tackling": 416,
    "gk_reflexes": 422,
    "gk_awareness": 428,
    "curl": 434,
    "stamina": 440,
    "acceleration": 448,
    "dribbling": 454,
    "offensive_awareness": 460,
    "balance": 466,
    "aggression": 472,
    "physical_contact": 480,
    "low_pass": 486,
    "finishing": 492,
    "lofted_pass": 498,
    "tight_possession": 518,
}

# Diagnostic seven-bit window starts in the 312-byte PES21-mobile Player.bin
# row.  The actual six-bit value occupies start+1..start+6; bit start belongs
# to the preceding packed field. PES21 calls the later "GK Parrying" attribute
# "GK Clearing", but it is the same ability.
PES21_ABILITY_BITS = {
    "set_piece_taking": 249,
    "low_pass": 262,
    "gk_parrying": 268,
    "defensive_awareness": 274,
    "ball_control": 280,
    "heading": 287,
    "jumping": 293,
    "gk_reach": 299,
    "speed": 305,
    "tackling": 311,
    "gk_reflexes": 319,
    "gk_awareness": 325,
    "curl": 331,
    "stamina": 337,
    "acceleration": 343,
    "dribbling": 351,
    "kicking_power": 357,
    "gk_catching": 363,
    "offensive_awareness": 369,
    "balance": 375,
    "aggression": 383,
    "physical_contact": 389,
    "finishing": 395,
    "lofted_pass": 401,
    "tight_possession": 415,
}

if set(EF10_ABILITY_BITS) != set(PES21_ABILITY_BITS):
    raise RuntimeError("EF10/PES21 converted ability sets differ")


def encode_pes21_wesys(raw: bytes) -> bytes:
    compressed = zlib.compress(raw, level=9)
    return b"\xff\x10\x81WESYS" + struct.pack(
        "<II", len(compressed), len(raw)
    ) + compressed


def records(raw: bytes, size: int) -> list[bytes]:
    if len(raw) % size:
        raise ValueError(f"raw table length {len(raw)} is not divisible by {size}")
    return [raw[offset : offset + size] for offset in range(0, len(raw), size)]


def read_bits(data: bytes, start: int, width: int) -> int:
    byte_start = start // 8
    byte_end = (start + width + 7) // 8
    value = int.from_bytes(data[byte_start:byte_end], "little")
    return (value >> (start % 8)) & ((1 << width) - 1)


def write_bits(data: bytearray, start: int, width: int, value: int) -> None:
    if not 0 <= value < (1 << width):
        raise ValueError(f"value {value} does not fit in {width} bits")
    byte_start = start // 8
    byte_end = (start + width + 7) // 8
    shift = start % 8
    current = int.from_bytes(data[byte_start:byte_end], "little")
    mask = ((1 << width) - 1) << shift
    current = (current & ~mask) | (value << shift)
    data[byte_start:byte_end] = current.to_bytes(byte_end - byte_start, "little")


def pes21_player_id(record: bytes) -> int:
    return struct.unpack_from("<I", record, 8)[0]


def ef10_player_id(record: bytes) -> int:
    return struct.unpack_from("<Q", record, 8)[0]


def ef10_name(record: bytes) -> str:
    return record[328:389].split(b"\0", 1)[0].decode("utf-8", errors="replace")


def pes21_name(record: bytes) -> str:
    return record[251:312].split(b"\0", 1)[0].decode("utf-8", errors="replace")


def ef10_nationality(record: bytes) -> int:
    return record[EF10_NATIONALITY_OFFSET]


def pes21_nationality(record: bytes) -> int:
    return read_bits(record, PES21_NATIONALITY_BIT, PES21_NATIONALITY_WIDTH)


def infer_nationality_map(
    ef10_by_id: dict[int, bytes], pes21_by_id: dict[int, bytes]
) -> tuple[dict[int, int], dict[int, dict[str, object]]]:
    """Infer EF10 -> PES21 nationality codes from shared player IDs.

    Both games store a compact database-specific country code rather than the
    Exhibition team ID. EF10 stores its country index as one byte; PES21 stores
    the same index shifted left by one in a ten-bit packed field. National-team
    rosters prove that relationship for every represented country. Shared IDs
    are retained as diagnostics because a few players changed nationality or
    reused an ID between revisions.
    """
    samples: dict[int, collections.Counter[int]] = collections.defaultdict(
        collections.Counter
    )
    for player_id in ef10_by_id.keys() & pes21_by_id.keys():
        samples[ef10_nationality(ef10_by_id[player_id])][
            pes21_nationality(pes21_by_id[player_id])
        ] += 1

    result: dict[int, int] = {}
    diagnostics: dict[int, dict[str, object]] = {}
    source_codes = {ef10_nationality(row) for row in ef10_by_id.values()}
    for source_code in sorted(source_codes):
        expected_code = source_code << 1
        counts = samples.get(source_code, collections.Counter())
        if counts:
            observed_code, votes = counts.most_common(1)[0]
            total = sum(counts.values())
            confidence = votes / total
        else:
            observed_code = None
            votes = 0
            total = 0
            confidence = 0.0
        diagnostics[source_code] = {
            "pes21_code": expected_code,
            "observed_majority_code": observed_code,
            "votes": votes,
            "samples": total,
            "confidence": confidence,
            "majority_matches_database_transform": (
                observed_code == expected_code if observed_code is not None else None
            ),
        }
        result[source_code] = expected_code
    return result, diagnostics


def ef10_player_position(record: bytes) -> int:
    """Return the EF10 registered-position nibble (GK=0 .. CF=12)."""
    return (struct.unpack_from("<I", record, 64)[0] >> 24) & 0x0F


def pes21_player_position(record: bytes) -> int:
    """Return the PES21 registered-position nibble (GK=0 .. CF=12)."""
    return (struct.unpack_from("<I", record, 52)[0] >> 18) & 0x0F


def replace_names(template: bytes, source: bytes) -> bytes:
    result = bytearray(template)
    result[68:129] = source[80:141]
    result[129:190] = source[141:202]
    result[190:251] = source[202:263]
    result[251:312] = source[328:389]
    return bytes(result)


def ef10_abilities(record: bytes) -> dict[str, int]:
    return {
        name: read_bits(record, bit, 6) + 40
        for name, bit in EF10_ABILITY_BITS.items()
    }


def pes21_abilities(record: bytes) -> dict[str, int]:
    return {
        name: read_bits(record, bit + 1, 6) + 40
        for name, bit in PES21_ABILITY_BITS.items()
    }


def replace_names_abilities_and_nationality(
    template: bytes, source: bytes, nationality_map: dict[int, int]
) -> bytes:
    result = bytearray(replace_names(template, source))
    for name, value in ef10_abilities(source).items():
        if not 40 <= value <= 99:
            raise ValueError(f"EF10 {name} value outside PES21 range: {value}")
        write_bits(result, PES21_ABILITY_BITS[name] + 1, 6, value - 40)
    source_nationality = ef10_nationality(source)
    if source_nationality not in nationality_map:
        raise RuntimeError(
            f"no reliable PES21 nationality mapping for EF10 code "
            f"{source_nationality}"
        )
    write_bits(
        result,
        PES21_NATIONALITY_BIT,
        PES21_NATIONALITY_WIDTH,
        nationality_map[source_nationality],
    )
    return bytes(result)


def parse_ef10_assignment_rows(
    rows: list[bytes],
) -> tuple[dict[int, list[tuple[int, int]]], dict[int, list[tuple[int, int]]]]:
    by_player: dict[int, list[tuple[int, int]]] = {}
    by_team: dict[int, list[tuple[int, int]]] = {}
    for row in rows:
        player_id, team_id, _assignment_id, packed, _padding = struct.unpack(
            "<QIIII", row
        )
        # Bits above bit 15 are assignment flags. Only the low order byte is
        # the appointment order used for starter/bench sorting.
        order = (packed >> 8) & 0xFF
        by_player.setdefault(player_id, []).append((team_id, order))
        by_team.setdefault(team_id, []).append((player_id, order))
    return by_player, by_team


def parse_pes21_assignment_rows(
    rows: list[bytes],
) -> tuple[dict[int, list[tuple[int, int]]], set[int]]:
    by_team: dict[int, list[tuple[int, int]]] = {}
    assigned_player_ids: set[int] = set()
    for row in rows:
        _assignment_id, player_id, team_id, packed = struct.unpack("<IIII", row)
        by_team.setdefault(team_id, []).append((player_id, (packed >> 8) & 0xFF))
        if player_id:
            assigned_player_ids.add(player_id)
    return by_team, assigned_player_ids


def parse_pes21_special_player_ids(raw: bytes) -> set[int]:
    """Return player IDs from the PES21 16-byte special assignment rows."""
    special_rows = records(raw, 16)
    return {
        struct.unpack_from("<I", row, 0)[0]
        for row in special_rows
        if struct.unpack_from("<I", row, 0)[0]
    }


def parse_portrait_member_ids(path: Path) -> set[int]:
    """Return PES21 player IDs which have a replaceable native portrait."""
    with path.open("rb") as source:
        header = read_cpk_packet(source, 0, b"CPK ")[0]
        rows = read_cpk_packet(source, int(header["TocOffset"]), b"TOC ")
    result: set[int] = set()
    for row in rows:
        if str(row.get("DirName") or "") != "common/player":
            continue
        filename = str(row["FileName"])
        if not filename.endswith(".png") or not filename[:-4].isdigit():
            continue
        if int(row["FileSize"]) != int(row["ExtractSize"]):
            continue
        result.add(int(filename[:-4]))
    return result


def patch_tactics_formations(
    pes21_dir: Path,
    ef10_tactics_dir: Path,
    tracked_team_ids: set[int],
) -> tuple[bytes, int, int]:
    """Overlay EF10 formations while preserving the PES21 table schema.

    EF10 Tactics.bin stores (team_id, tactics_id, flags), whereas PES21 stores
    (tactics_id, team_id, flags). Formation rows use the inverse first two
    fields as well. Keeping every PES21 tactics ID and row index avoids the
    CommonWork count/index regressions caused by importing the newer table.
    """
    old_tactics = records(
        decode_wesys(pes21_dir / "Tactics.bin"), TACTICS_SIZE
    )
    new_tactics = records(
        decode_wesys(ef10_tactics_dir / "Tactics.bin"), TACTICS_SIZE
    )
    old_formations = records(
        decode_wesys(pes21_dir / "TacticsFormation.bin"),
        TACTICS_FORMATION_SIZE,
    )
    new_formations = records(
        decode_wesys(ef10_tactics_dir / "TacticsFormation.bin"),
        TACTICS_FORMATION_SIZE,
    )

    old_tactics_by_team: dict[int, list[int]] = {}
    for row in old_tactics:
        tactics_id, team_id, _flags = struct.unpack("<III", row)
        old_tactics_by_team.setdefault(team_id, []).append(tactics_id)

    new_tactics_by_team: dict[int, list[int]] = {}
    for row in new_tactics:
        team_id, tactics_id, _flags = struct.unpack("<III", row)
        new_tactics_by_team.setdefault(team_id, []).append(tactics_id)

    old_form_indices: dict[int, list[int]] = {}
    for index, row in enumerate(old_formations):
        tactics_id, _position, _packed = struct.unpack("<III", row)
        old_form_indices.setdefault(tactics_id, []).append(index)

    new_forms_by_tactics: dict[int, list[tuple[int, int]]] = {}
    for row in new_formations:
        position, tactics_id, packed = struct.unpack("<III", row)
        new_forms_by_tactics.setdefault(tactics_id, []).append((position, packed))

    patched = list(old_formations)
    patched_teams = 0
    patched_rows = 0
    for team_id in sorted(tracked_team_ids):
        old_ids = old_tactics_by_team.get(team_id, [])
        new_ids = new_tactics_by_team.get(team_id, [])
        if not old_ids or not new_ids:
            continue

        # EF10 pairs commonly contain the same eleven formation points. The
        # first table entry is the primary/offensive setup used by Exhibition.
        source_rows = new_forms_by_tactics.get(new_ids[0], [])
        if len(source_rows) != 11:
            continue
        source_rows = sorted(source_rows, key=lambda item: (item[1] >> 16) & 0xFF)

        team_rows = 0
        for old_tactics_id in old_ids:
            indices = old_form_indices.get(old_tactics_id, [])
            # PES21 stores three 11-player phases per tactics record (slot
            # ranges 0..10, 16..26, and 32..42). EF10 stores one phase. Apply
            # its shape to all three while preserving each PES21 slot byte.
            if not indices or len(indices) % 11:
                continue
            indices = sorted(
                indices,
                key=lambda index: (
                    struct.unpack("<III", old_formations[index])[2] >> 16
                )
                & 0xFF,
            )
            for phase_start in range(0, len(indices), 11):
                for index, (position, source_packed) in zip(
                    indices[phase_start : phase_start + 11], source_rows
                ):
                    _old_tid, _old_position, old_packed = struct.unpack(
                        "<III", old_formations[index]
                    )
                    packed = (old_packed & 0x00FF0000) | (
                        source_packed & 0x0000FFFF
                    )
                    patched[index] = struct.pack(
                        "<III", old_tactics_id, position, packed
                    )
                    team_rows += 1
        if team_rows:
            patched_teams += 1
            patched_rows += team_rows

    patched_raw = b"".join(patched)
    if len(patched_raw) != len(b"".join(old_formations)):
        raise RuntimeError("TacticsFormation.bin raw size changed")
    for before, after in zip(old_formations, patched):
        if struct.unpack_from("<I", before)[0] != struct.unpack_from("<I", after)[0]:
            raise RuntimeError("TacticsFormation.bin tactics ID/order changed")
    return encode_pes21_wesys(patched_raw), patched_teams, patched_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ef10-dir",
        type=Path,
        default=Path("local-debug/efootball10-audit/tables/common/etc/pesdb"),
    )
    parser.add_argument(
        "--pes21-dir",
        type=Path,
        default=Path(
            "local-debug/efootball10-audit/compare/"
            "old_dt200_mobile_all.cpk/common/etc/pesdb"
        ),
    )
    parser.add_argument(
        "--ef10-tactics-dir",
        type=Path,
        default=Path(
            "local-debug/efootball10-audit/compare/"
            "new_dt200_mobile_all.cpk/common/etc/pesdb"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("local-debug/efootball10-player-patch"),
    )
    parser.add_argument(
        "--team-id",
        type=int,
        default=108,
        help=(
            "single EF10 team to convert; pass 0 for every team exposed by "
            "the selected Exhibition source tree"
        ),
    )
    parser.add_argument(
        "--portrait-cpk",
        type=Path,
        default=Path(
            "local-debug/efootball10-player-patch/dt241_mobile_all.cpk"
        ),
        help="PES21 portrait CPK used to require a replaceable portrait slot",
    )
    parser.add_argument(
        "--surrogate-registry",
        type=Path,
        default=Path(
            "local-debug/efootball10-player-patch/surrogate-registry.json"
        ),
        help="persistent EF10-to-PES21 surrogate allocation registry",
    )
    parser.add_argument(
        "--supersede-migration-rosters",
        action="store_true",
        help=(
            "do not reserve IDs from exhibition_migration.inc; use only when "
            "every migrated team is replaced by the generated EF10 roster"
        ),
    )
    parser.add_argument(
        "--reallocate-direct-conflicts",
        action="store_true",
        help=(
            "move an existing surrogate when its PES21 ID is a direct EF10 "
            "player in an expanded all-team conversion"
        ),
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("data/exhibition_team_catalog.json"),
        help="generated team catalog relative to --root",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    ef10_players = records(
        decode_wesys(args.ef10_dir / "Player.bin"), EF10_PLAYER_SIZE
    )
    pes21_players = records(
        decode_wesys(args.pes21_dir / "Player.bin"), PES21_PLAYER_SIZE
    )
    ef10_assignments = records(
        decode_wesys(args.ef10_dir / "PlayerAssignment.bin"),
        EF10_ASSIGNMENT_SIZE,
    )
    pes21_assignments = records(
        decode_wesys(args.pes21_dir / "PlayerAssignment.bin"),
        PES21_ASSIGNMENT_SIZE,
    )

    old_by_id = {pes21_player_id(row): row for row in pes21_players}
    new_by_id = {ef10_player_id(row): row for row in ef10_players}
    old_ids = set(old_by_id)
    nationality_map, nationality_diagnostics = infer_nationality_map(
        new_by_id, old_by_id
    )
    ef10_by_player, ef10_by_team = parse_ef10_assignment_rows(ef10_assignments)

    catalog_path = args.catalog if args.catalog.is_absolute() else root / args.catalog
    catalog = load_catalog(catalog_path)
    team_by_id = catalog_team_map(catalog)
    eligible_team_ids = conversion_team_ids(catalog)
    if args.team_id == 0:
        tracked_team_ids = {
            team_id for team_id in eligible_team_ids if ef10_by_team.get(team_id)
        }
        target_symbol = "all_exhibition_teams"
    elif args.team_id in eligible_team_ids:
        tracked_team_ids = {args.team_id}
        target_symbol = str(team_by_id[args.team_id]["symbol"])
    else:
        raise ValueError(
            f"team ID {args.team_id} is not conversion-eligible in the Exhibition catalog"
        )
    if not tracked_team_ids:
        raise RuntimeError("no selected Exhibition teams have EF10 assignments")
    roster_paths = [
        root / "source" / "exhibition_rosters.inc",
    ]
    if not args.supersede_migration_rosters:
        roster_paths.append(root / "source" / "exhibition_migration.inc")
    roster_players, _roster_shirts = parse_c_roster_arrays(
        [path for path in roster_paths if path.is_file()]
    )
    reserved_ids = {
        player_id for values in roster_players.values() for player_id in values
    }

    registry_path = args.surrogate_registry.resolve()
    registry_mapping: dict[int, int] = {}
    if registry_path.is_file():
        registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_mapping = {
            int(source_id): int(target_id)
            for source_id, target_id in registry_payload.get("map", {}).items()
        }

    _old_by_team, assigned_player_ids = parse_pes21_assignment_rows(
        pes21_assignments
    )
    special_player_ids = parse_pes21_special_player_ids(
        decode_wesys(args.pes21_dir / "SpecialPlayerAssignment.bin")
    )
    native_used_ids = assigned_player_ids | special_player_ids

    target_roster: list[tuple[int, int]] = []
    seen_target_players: set[int] = set()
    target_assignment_count = 0
    for team_id in sorted(tracked_team_ids):
        team_roster = sorted(
            ef10_by_team.get(team_id, []), key=lambda item: (item[1], item[0])
        )
        target_assignment_count += len(team_roster)
        for player_id, order in team_roster:
            if player_id in seen_target_players:
                continue
            seen_target_players.add(player_id)
            target_roster.append((player_id, order))
    target_ids = {
        player_id
        for player_id, _order in target_roster
        if player_id <= 0xFFFFFFFF and player_id not in old_ids
    }
    direct_ef10_ids = {
        player_id for player_id, _order in target_roster if player_id in old_ids
    }
    reserved_ids.update(direct_ef10_ids)
    relocated_registry_sources: list[int] = []
    if args.reallocate_direct_conflicts:
        relocated_registry_sources = sorted(
            source_id
            for source_id, target_id in registry_mapping.items()
            if target_id in direct_ef10_ids and source_id != target_id
        )
        for source_id in relocated_registry_sources:
            del registry_mapping[source_id]
    registry_target_ids = set(registry_mapping.values())
    if len(registry_target_ids) != len(registry_mapping):
        raise RuntimeError("persistent surrogate registry contains duplicate targets")

    portrait_member_ids = parse_portrait_member_ids(args.portrait_cpk.resolve())
    missing_direct_portraits = direct_ef10_ids - portrait_member_ids
    if missing_direct_portraits:
        raise RuntimeError(
            "direct EF10/PES21 players lack native portrait members: "
            + ", ".join(map(str, sorted(missing_direct_portraits)))
        )
    missing_registry_portraits = registry_target_ids - portrait_member_ids
    if missing_registry_portraits:
        raise RuntimeError(
            "persistent surrogate targets lack native portrait members: "
            + ", ".join(map(str, sorted(missing_registry_portraits)))
        )

    # A surrogate is eligible only if PES21 never assigns it to a native team,
    # special squad, or one of the stable custom runtime rosters.  This is the
    # key safety invariant: changing its name/stats cannot mutate a donor team.
    # It must also own a stored dt241 PNG so the EF10 portrait can replace a
    # native member without changing the CPK schema.
    available_ids = {
        player_id
        for player_id, row in old_by_id.items()
        if player_id > 0
        and player_id not in native_used_ids
        and player_id not in reserved_ids
        and player_id not in registry_target_ids
        and player_id in portrait_member_ids
        and pes21_name(row)
    }
    initial_available_count = len(available_ids)
    if len(available_ids) < len(target_ids):
        raise RuntimeError(
            f"only {len(available_ids)} globally-unused PES21 slots for "
            f"{len(target_ids)} EF10-only players"
        )

    mapping: dict[int, int] = {}
    details: list[dict[str, object]] = []
    pools_by_position: dict[int, list[int]] = {}
    for player_id in sorted(available_ids):
        position = pes21_player_position(old_by_id[player_id])
        pools_by_position.setdefault(position, []).append(player_id)

    source_order = [
        player_id for player_id, _order in target_roster if player_id in target_ids
    ]
    for source_id in source_order:
        source_assignments = ef10_by_player.get(source_id, [])
        source_position = ef10_player_position(new_by_id[source_id])
        surrogate_id = registry_mapping.get(source_id, 0)
        allocation_mode = "persistent_globally_unassigned_position_slot"
        if surrogate_id:
            if surrogate_id not in old_by_id:
                raise RuntimeError(
                    f"registered surrogate {surrogate_id} for {source_id} is absent"
                )
            if surrogate_id in native_used_ids or surrogate_id in reserved_ids:
                raise RuntimeError(
                    f"registered surrogate {surrogate_id} for {source_id} is now used"
                )
            if pes21_player_position(old_by_id[surrogate_id]) != source_position:
                raise RuntimeError(
                    f"registered surrogate position mismatch for {source_id}"
                )
        else:
            global_pool = pools_by_position.get(source_position, [])
            surrogate_id = next(
                (player_id for player_id in global_pool if player_id in available_ids),
                0,
            )
            allocation_mode = "new_globally_unassigned_position_slot"
        if not surrogate_id:
            raise RuntimeError(
                f"globally-unused surrogate pool exhausted for position "
                f"{source_position}"
            )
        available_ids.discard(surrogate_id)
        mapping[source_id] = surrogate_id
        registry_mapping[source_id] = surrogate_id
        source_row = new_by_id[source_id]
        details.append(
            {
                "ef10_player_id": source_id,
                "surrogate_pes21_id": surrogate_id,
                "name": ef10_name(source_row),
                "template_name": pes21_name(old_by_id[surrogate_id]),
                "registered_position": source_position,
                "template_position": pes21_player_position(
                    old_by_id[surrogate_id]
                ),
                "teams": sorted(
                    {
                        team_id
                        for team_id, _order in source_assignments
                        if team_id in tracked_team_ids
                    }
                ),
                "allocation_mode": allocation_mode,
                "globally_unassigned": True,
                "ef10_nationality_code": ef10_nationality(source_row),
                "pes21_nationality_code": nationality_map[
                    ef10_nationality(source_row)
                ],
                "abilities": ef10_abilities(source_row),
            }
        )

    replacement_sources = {
        **{surrogate_id: source_id for source_id, surrogate_id in mapping.items()},
        **{player_id: player_id for player_id in direct_ef10_ids},
    }
    replacement_by_id = {
        target_id: replace_names_abilities_and_nationality(
            old_by_id[target_id], new_by_id[source_id], nationality_map
        )
        for target_id, source_id in replacement_sources.items()
    }
    patched_players = [
        replacement_by_id.get(pes21_player_id(row), row) for row in pes21_players
    ]
    (output / "Player.bin").write_bytes(
        encode_pes21_wesys(b"".join(patched_players))
    )
    (output / "PlayerAssignment.bin").write_bytes(
        (args.pes21_dir / "PlayerAssignment.bin").read_bytes()
    )
    tactics_blob, patched_tactics_teams, patched_tactics_rows = (
        patch_tactics_formations(
            args.pes21_dir,
            args.ef10_tactics_dir,
            tracked_team_ids,
        )
    )
    (output / "TacticsFormation.bin").write_bytes(tactics_blob)

    map_payload = {
        "team_id": args.team_id,
        "team_ids": sorted(tracked_team_ids),
        "team_symbol": target_symbol,
        "map": {str(source): target for source, target in sorted(mapping.items())},
        "details": details,
    }
    (output / "surrogate-map.json").write_text(
        json.dumps(map_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "map": {
                    str(source): target
                    for source, target in sorted(registry_mapping.items())
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    check_players = records(
        decode_wesys(output / "Player.bin"), PES21_PLAYER_SIZE
    )
    check_assignments = records(
        decode_wesys(output / "PlayerAssignment.bin"), PES21_ASSIGNMENT_SIZE
    )
    if [pes21_player_id(row) for row in check_players] != [
        pes21_player_id(row) for row in pes21_players
    ]:
        raise RuntimeError("Player.bin ID order/count changed")
    if b"".join(check_assignments) != b"".join(pes21_assignments):
        raise RuntimeError("PlayerAssignment.bin changed")
    if len(mapping.values()) != len(set(mapping.values())):
        raise RuntimeError("two EF10 players share one surrogate")
    if set(mapping.values()) & native_used_ids:
        raise RuntimeError("a surrogate is present in a native assignment table")
    if set(mapping.values()) & reserved_ids:
        raise RuntimeError("a surrogate is present in a stable runtime roster")

    checked_by_id = {pes21_player_id(row): row for row in check_players}
    validation_players: list[dict[str, object]] = []
    for target_id, source_id in sorted(replacement_sources.items()):
        source_row = new_by_id[source_id]
        patched_row = checked_by_id[target_id]
        source_stats = ef10_abilities(source_row)
        patched_stats = pes21_abilities(patched_row)
        if patched_stats != source_stats:
            raise RuntimeError(
                f"ability round-trip mismatch for {source_id} -> {target_id}"
            )
        if pes21_name(patched_row) != ef10_name(source_row):
            raise RuntimeError(f"name round-trip mismatch for {source_id}")
        source_nationality = ef10_nationality(source_row)
        target_nationality = nationality_map[source_nationality]
        if pes21_nationality(patched_row) != target_nationality:
            raise RuntimeError(
                f"nationality round-trip mismatch for {source_id} -> {target_id}"
            )
        if source_id != target_id and (
            pes21_player_position(patched_row)
            != ef10_player_position(source_row)
        ):
            raise RuntimeError(f"position mismatch for surrogate {source_id}")
        validation_players.append(
            {
                "ef10_player_id": source_id,
                "pes21_player_id": target_id,
                "name": ef10_name(source_row),
                "mode": "direct" if source_id == target_id else "surrogate",
                "abilities_verified": len(source_stats),
                "ef10_nationality_code": source_nationality,
                "pes21_nationality_code": target_nationality,
            }
        )

    validation = {
        "team_id": args.team_id,
        "team_ids": sorted(tracked_team_ids),
        "team_symbol": target_symbol,
        "player_id_order_unchanged": True,
        "player_assignment_byte_identical": True,
        "surrogates_globally_unassigned": True,
        "surrogate_registry": str(registry_path),
        "converted_abilities_per_player": len(PES21_ABILITY_BITS),
        "nationalities_verified": len(validation_players),
        "nationality_code_map": {
            str(source): nationality_map[source]
            for source in sorted(
                {ef10_nationality(new_by_id[player_id]) for player_id, _ in target_roster}
            )
        },
        "players": validation_players,
    }
    (output / "validation-report.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    summary = {
        "conversion_mode": (
            "all_exhibition_teams_persistent_global_unused_surrogates_"
            "with_stats_nationality_portraits"
            if args.team_id == 0
            else "single_team_persistent_global_unused_surrogates_"
            "with_stats_nationality_portraits"
        ),
        "target_team_id": args.team_id,
        "target_team_ids": sorted(tracked_team_ids),
        "target_team_count": len(tracked_team_ids),
        "target_team_symbol": target_symbol,
        "pes21_player_records": len(check_players),
        "target_roster_players": len(target_roster),
        "target_assignment_entries": target_assignment_count,
        "mapped_ef10_only_players": len(mapping),
        "direct_ef10_players": len(direct_ef10_ids),
        "players_with_converted_names_and_stats": len(replacement_sources),
        "converted_abilities_per_player": len(PES21_ABILITY_BITS),
        "players_with_converted_nationality": len(replacement_sources),
        "inferred_nationality_codes": len(nationality_map),
        "nationality_mapping_diagnostics": {
            str(source): nationality_diagnostics[source]
            for source in sorted(
                {ef10_nationality(new_by_id[player_id]) for player_id, _ in target_roster}
            )
        },
        "native_assigned_player_ids": len(assigned_player_ids),
        "special_assigned_player_ids": len(special_player_ids),
        "reserved_roster_ids": len(reserved_ids),
        "native_portrait_members": len(portrait_member_ids),
        "initial_globally_unused_slots": initial_available_count,
        "remaining_unused_slots": len(available_ids),
        "reallocated_direct_conflict_sources": relocated_registry_sources,
        "player_assignment_records": len(check_assignments),
        "patched_tactics_teams": patched_tactics_teams,
        "patched_tactics_formation_records": patched_tactics_rows,
        "output_dir": str(output.resolve()),
    }
    (output / "conversion-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
