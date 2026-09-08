#!/usr/bin/env python3
"""Generate the runtime Exhibition roster table from PESDB Authentic data.

PESDB eFootball is the sole authority for current player identity, club
membership, roster order, and shirt numbers.  PES21 is consulted only for the
physical row IDs that can hold the verified PESDB values.  A missing mapping,
duplicate target, incomplete team, or unresolved physical row blocks output.

The generated include is intentionally small: it contains no player names or
ability values, only the physical IDs and PESDB roster ordering consumed by
the runtime hook.  Player values are shipped separately in the patched
PES21-schema Player.bin artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROSTERS = Path(
    "local-debug/pesdb-efootball-authentic-rosters-current-54-shirts.json"
)
DEFAULT_TARGET_MAP = Path("local-debug/pesdb-efootball-stable-target-map.json")
DEFAULT_PLAYER = Path(
    "local-debug/pesdb-efootball-stable-3231-authoritative-patch/Player.bin"
)
DEFAULT_PLAYER_REPORT = Path(
    "local-debug/pesdb-efootball-stable-3231-authoritative-patch/coverage-report.json"
)
DEFAULT_CLEANUP_REPORT = Path(
    "local-debug/pes21-membership-cleanup-pesdb-all-54-replaced/cleanup-report.json"
)
DEFAULT_CATALOG = Path("data/exhibition_team_catalog.json")
DEFAULT_INTER_MIAMI_MAP = Path("data/experimental_original_inter_miami.json")
DEFAULT_TACTICS = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/"
    "common/etc/pesdb/Tactics.bin"
)
DEFAULT_TACTICS_FORMATION = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/"
    "common/etc/pesdb/TacticsFormation.bin"
)
DEFAULT_OUTPUT = Path("source/exhibition_rosters_pesdb_generated.inc")
DEFAULT_REPORT = Path("PESDB_RUNTIME_ROSTERS.md")
DEFAULT_METADATA_OUTPUT = Path(
    "local-debug/pesdb-runtime-rosters-generated.json"
)
AUTHORITY = "https://pesdb.net/efootball"
PLAYER_ROW_SIZE = 312


def resolve(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {key: value for key, value in payload.items() if key != "content_id"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def load_roster_snapshot(path: Path) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    payload = load_json(path)
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported roster schema")
    if payload.get("source") != "authentic" or payload.get("authority") != AUTHORITY:
        raise ValueError(f"{path}: PESDB eFootball Authentic data is required")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or not policy.get("pesdb_rosters_only"):
        raise ValueError(f"{path}: roster source is not PESDB-only")
    if not policy.get("pesdb_player_values_only"):
        raise ValueError(f"{path}: player values are not PESDB-only")
    if policy.get("pes21_roster_or_value_fallback") is not False:
        raise ValueError(f"{path}: PES21 roster/value fallback is forbidden")
    teams_raw = payload.get("teams")
    players_raw = payload.get("players")
    if not isinstance(teams_raw, dict) or not isinstance(players_raw, dict):
        raise ValueError(f"{path}: teams and players must be objects")

    players: dict[int, dict[str, Any]] = {}
    for raw_id, row in players_raw.items():
        player_id = int(raw_id)
        if not isinstance(row, dict) or row.get("source") != "authentic":
            raise ValueError(f"{path}: malformed PESDB player {raw_id}")
        if int(row.get("player_id", 0)) != player_id:
            raise ValueError(f"{path}: player key disagrees with row {raw_id}")
        players[player_id] = row

    teams: dict[int, dict[str, Any]] = {}
    for raw_id, row in teams_raw.items():
        team_id = int(raw_id)
        if not isinstance(row, dict) or not row.get("complete"):
            raise ValueError(f"{path}: team {team_id} is incomplete")
        player_ids = [int(value) for value in row.get("player_ids", [])]
        if not player_ids or len(player_ids) != len(set(player_ids)):
            raise ValueError(f"{path}: team {team_id} has duplicate/empty player IDs")
        if set(player_ids) - set(players):
            missing = sorted(set(player_ids) - set(players))
            raise ValueError(f"{path}: team {team_id} missing players {missing[:20]}")
        raw_shirts = row.get("shirt_numbers")
        if not isinstance(raw_shirts, dict):
            raise ValueError(f"{path}: team {team_id} has no PESDB shirt map")
        shirts: list[int] = []
        for player_id in player_ids:
            value = raw_shirts.get(str(player_id))
            if not isinstance(value, int) or not 0 <= value <= 255:
                raise ValueError(
                    f"{path}: team {team_id} player {player_id} has invalid shirt {value!r}"
                )
            shirts.append(value)
        nonzero = [value for value in shirts if value]
        if len(nonzero) != len(set(nonzero)):
            raise ValueError(f"{path}: team {team_id} has duplicate shirt numbers")
        if int(row.get("player_count", 0)) != len(player_ids):
            raise ValueError(f"{path}: team {team_id} player_count is stale")
        copied = dict(row)
        copied["shirt_values"] = shirts
        teams[team_id] = copied
    if not teams:
        raise ValueError(f"{path}: no PESDB teams found")
    return teams, players


def load_target_map(path: Path) -> dict[int, int]:
    payload = load_json(path)
    if payload.get("authority") != AUTHORITY:
        raise ValueError(f"{path}: target map has unexpected authority")
    policy = payload.get("policy", {})
    if not policy.get("pesdb_only") or policy.get("pes21_values_allowed"):
        raise ValueError(f"{path}: target map does not enforce PESDB-only values")
    raw = payload.get("map")
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: map must be an object")
    mapping = {int(source): int(target) for source, target in raw.items()}
    if any(source <= 0 or target <= 0 for source, target in mapping.items()):
        raise ValueError(f"{path}: player IDs must be positive")
    if len(mapping) != len(set(mapping.values())):
        raise ValueError(f"{path}: physical target slots are duplicated")
    return mapping


def load_player_ids(path: Path) -> set[int]:
    from experimental_import_ef10_original import decode_wesys

    raw = decode_wesys(path)
    if len(raw) % PLAYER_ROW_SIZE:
        raise ValueError(f"{path}: Player.bin has a partial row")
    ids = {
        struct.unpack_from("<I", raw, offset + 8)[0]
        for offset in range(0, len(raw), PLAYER_ROW_SIZE)
    }
    if len(ids) * PLAYER_ROW_SIZE != len(raw):
        raise ValueError(f"{path}: Player.bin contains duplicate IDs")
    return ids


def load_integrated_team_ids(path: Path) -> set[int]:
    payload = load_json(path)
    raw = payload.get("pesdb_authoritative_team_ids")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path}: cleanup report has no integrated PESDB teams")
    values = {int(value) for value in raw}
    if any(value <= 0 for value in values):
        raise ValueError(f"{path}: invalid integrated team ID")
    if payload.get("pesdb_only") is not True:
        raise ValueError(f"{path}: cleanup report is not PESDB-only")
    if payload.get("unresolved_pesdb_memberships") != 0:
        raise ValueError(f"{path}: unresolved PESDB memberships block release")
    return values


def load_runtime_team_metadata(path: Path) -> tuple[dict[int, int], set[int]]:
    payload = load_json(path)
    if isinstance(payload.get("teams"), list):
        result = {}
        club_team_ids: set[int] = set()
        for team in payload["teams"]:
            if not isinstance(team, dict):
                continue
            logical = int(team["team_id"])
            physical = int(team.get("physical_team_id", logical))
            kind = str(team.get("kind", ""))
            if kind not in {"club", "national"}:
                raise ValueError(f"{path}: team {logical} has invalid kind {kind!r}")
            if kind == "club":
                club_team_ids.add(logical)
            if physical != logical:
                result[logical] = physical
        if not club_team_ids:
            raise ValueError(f"{path}: catalog has no club teams")
        if len(result) != len(set(result.values())):
            raise ValueError(f"{path}: catalog physical team IDs are duplicated")
        return result, club_team_ids
    if isinstance(payload.get("physical_team_map"), dict):
        raw = payload["physical_team_map"]
        result = {int(logical): int(physical) for logical, physical in raw.items()}
        if len(result) != len(set(result.values())):
            raise ValueError(f"{path}: physical team IDs are duplicated")
        return result, set(result)
    team = payload.get("team")
    if not isinstance(team, dict):
        raise ValueError(f"{path}: expected an Inter Miami team map")
    logical = int(team.get("logical_team_id", 0))
    physical = int(team.get("pes21_physical_team_id", 0))
    if logical <= 0 or physical <= 0:
        raise ValueError(f"{path}: logical/physical team IDs must be positive")
    return {logical: physical}, {logical}


def load_authoritative_ratings(
    path: Path | None,
    *,
    players: dict[int, dict[str, Any]],
    target_map: dict[int, int],
) -> tuple[dict[int, tuple[int, int]], dict[str, Any]]:
    """Load PESDB base OVR/position rows keyed by physical player ID.

    The coverage report is generated by the PESDB-only Player.bin patcher.  A
    small fixture fallback keeps the generator unit-testable without requiring
    the large local report, but a real release invocation always supplies the
    complete 3,231-row report.
    """
    if path is not None and path.is_file():
        payload = load_json(path)
        if (
            payload.get("authority") != AUTHORITY
            or payload.get("pesdb_only") is not True
            or payload.get("coverage") != 1.0
            or int(payload.get("skipped", -1)) != 0
        ):
            raise ValueError(f"{path}: incomplete PESDB-only coverage report")
        raw_rows = payload.get("applied_players")
        if not isinstance(raw_rows, list) or int(payload.get("applied", 0)) != len(raw_rows):
            raise ValueError(f"{path}: malformed applied_players rows")
        ratings: dict[int, tuple[int, int]] = {}
        for row in raw_rows:
            if not isinstance(row, dict):
                raise ValueError(f"{path}: malformed applied player row")
            target_id = int(row["target_player_id"])
            overall = int(row["base_overall"])
            position = int(row["position_after"])
            if not 1 <= overall <= 100 or not 0 <= position <= 12:
                raise ValueError(f"{path}: invalid rating row {row!r}")
            if target_id in ratings:
                raise ValueError(f"{path}: duplicate target player {target_id}")
            ratings[target_id] = (overall, position)
        return ratings, {
            "authority": AUTHORITY,
            "source": str(path),
            "source_sha256": sha256_file(path),
            "rows": len(ratings),
            "complete": True,
        }

    # Test/fixture fallback: use only fields already present in the fixture.
    ratings = {}
    for source_id, row in players.items():
        target_id = target_map.get(source_id)
        if target_id is None:
            continue
        overall = int(row.get("base_overall", row.get("overall", 0)) or 0)
        position = int(
            row.get("primary_position_index", row.get("position_after", 0)) or 0
        )
        if overall:
            ratings[target_id] = (max(1, min(100, overall)), max(0, min(12, position)))
    return ratings, {
        "authority": AUTHORITY,
        "source": "fixture-player-rows",
        "source_sha256": None,
        "rows": len(ratings),
        "complete": False,
    }


def load_tactic_roles(
    tactics_path: Path | None,
    formation_path: Path | None,
    physical_team_map: dict[int, int],
) -> tuple[dict[int, list[int]], dict[str, Any]]:
    """Decode the first native formation role sequence for each physical team."""
    fallback = [0, 1, 1, 3, 2, 4, 5, 5, 10, 9, 12]
    if not tactics_path or not formation_path or not tactics_path.is_file() or not formation_path.is_file():
        return {team: list(fallback) for team in physical_team_map.values()}, {
            "source": "fallback-console-roles",
            "teams": 0,
            "complete": False,
        }
    from experimental_import_ef10_original import decode_wesys

    tactics_raw = decode_wesys(tactics_path)
    formation_raw = decode_wesys(formation_path)
    if len(tactics_raw) % 12 or len(formation_raw) % 12:
        raise ValueError("native tactics tables contain partial rows")
    tactic_by_team: dict[int, int] = {}
    for offset in range(0, len(tactics_raw), 12):
        tactic_id, physical_id, _flags = struct.unpack_from("<III", tactics_raw, offset)
        tactic_by_team.setdefault(physical_id, tactic_id)
    roles_by_tactic: dict[int, list[int]] = {}
    for offset in range(0, len(formation_raw), 12):
        tactic_id, role, packed = struct.unpack_from("<III", formation_raw, offset)
        # Each native tactic stores three 11-player phases. Phase zero is the
        # default attacking/defensive layout used when the page opens.
        if ((packed >> 20) & 0x3) != 0:
            continue
        roles = roles_by_tactic.setdefault(tactic_id, [])
        if len(roles) < 11:
            roles.append(int(role))
    result: dict[int, list[int]] = {}
    for physical_id in physical_team_map.values():
        result[physical_id] = list(
            roles_by_tactic.get(tactic_by_team.get(physical_id, -1), fallback)
        )
        if len(result[physical_id]) != 11:
            result[physical_id] = list(fallback)
    return result, {
        "source": str(tactics_path),
        "formation_source": str(formation_path),
        "source_sha256": sha256_file(tactics_path),
        "formation_source_sha256": sha256_file(formation_path),
        "teams": len(result),
        "complete": True,
    }


def role_compatibility(role: int, position: int) -> int:
    """Return a large score for exact native-role matches.

    Goalkeepers are never allowed to fill an outfield slot.  Other roles have
    conservative neighboring-position fallbacks so a short PESDB roster still
    receives a complete XI without letting raw roster order dictate slots.
    """
    if role == 0:
        return 100 if position == 0 else -1000000
    if position == 0:
        return -1000000
    if position == role:
        return 100
    neighbors = {
        1: {2, 3},
        2: {1, 3},
        3: {1, 2},
        4: {5, 6, 7, 8},
        5: {4, 6, 7, 8},
        6: {4, 5, 7, 8, 9, 10},
        7: {4, 5, 6, 8, 9, 10},
        8: {4, 5, 6, 7, 9, 10, 11, 12},
        9: {8, 10, 11, 12},
        10: {8, 9, 11, 12},
        11: {8, 9, 10, 12},
        12: {8, 9, 10, 11},
    }
    return 85 if position in neighbors.get(role, set()) else 0


def choose_balanced_xi(
    players: list[tuple[int, int, int]], roles: list[int]
) -> tuple[list[int], list[int]]:
    """Match roster players to native role slots with a bitmask DP."""
    if len(roles) != 11:
        raise ValueError("native formation must contain exactly 11 role slots")
    # mask -> (score, [(roster_index, role_index), ...])
    states: dict[int, tuple[int, tuple[tuple[int, int], ...]]] = {0: (0, ())}
    for roster_index, (_player_id, overall, position) in enumerate(players):
        next_states = dict(states)
        for mask, (score, chosen) in states.items():
            for role_index, role in enumerate(roles):
                bit = 1 << role_index
                if mask & bit:
                    continue
                candidate = (
                    score + role_compatibility(role, position) + overall,
                    chosen + ((roster_index, role_index),),
                )
                previous = next_states.get(mask | bit)
                if previous is None or candidate[0] > previous[0] or (
                    candidate[0] == previous[0] and candidate[1] < previous[1]
                ):
                    next_states[mask | bit] = candidate
        states = next_states
    full = (1 << 11) - 1
    if full not in states:
        raise ValueError("unable to assign a complete position-balanced XI")
    _score, chosen = states[full]
    chosen_by_role = [0] * 11
    selected: set[int] = set()
    for roster_index, role_index in chosen:
        chosen_by_role[role_index] = roster_index
        selected.add(roster_index)
    bench = [index for index in range(len(players)) if index not in selected]
    bench.sort(key=lambda index: (-players[index][1], index, players[index][0]))
    return chosen_by_role, bench


def symbol_for(team_id: int) -> str:
    return f"team_{team_id}"


def wrapped(values: list[int], suffix: str, per_line: int = 8) -> str:
    lines: list[str] = []
    for offset in range(0, len(values), per_line):
        chunk = ", ".join(f"{value}{suffix}" for value in values[offset : offset + per_line])
        lines.append(f"    {chunk},")
    return "\n".join(lines)


def generate(
    *,
    rosters_path: Path,
    target_map_path: Path,
    player_path: Path,
    cleanup_report_path: Path,
    physical_team_map_path: Path,
    output_path: Path,
    report_path: Path,
    player_report_path: Path | None = None,
    tactics_path: Path | None = None,
    tactics_formation_path: Path | None = None,
    metadata_output_path: Path | None = None,
    check: bool = False,
) -> dict[str, Any]:
    teams, players = load_roster_snapshot(rosters_path)
    target_map = load_target_map(target_map_path)
    physical_team_map, club_team_ids = load_runtime_team_metadata(
        physical_team_map_path
    )
    integrated_ids = load_integrated_team_ids(cleanup_report_path)
    player_ids = load_player_ids(player_path)
    ratings, rating_source = load_authoritative_ratings(
        player_report_path, players=players, target_map=target_map
    )

    missing_teams = sorted(integrated_ids - set(teams))
    if missing_teams:
        raise ValueError(f"integrated teams missing from PESDB roster snapshot: {missing_teams}")
    held_back = sorted(set(teams) - integrated_ids)
    if set(physical_team_map) - integrated_ids:
        raise ValueError("physical team map contains a non-integrated team")
    if integrated_ids - club_team_ids:
        raise ValueError("integrated PESDB roster contains a non-club team")
    missing_rating_rows = sorted(set(ratings) - player_ids)
    if missing_rating_rows:
        raise ValueError(
            "authoritative rating table contains absent Player.bin rows: "
            f"{missing_rating_rows[:20]}"
        )
    integrated_physical_map = {
        team_id: physical_team_map.get(team_id, team_id)
        for team_id in integrated_ids
    }
    tactic_roles, tactics_source = load_tactic_roles(
        tactics_path,
        tactics_formation_path,
        integrated_physical_map,
    )

    owner_by_target: dict[int, int] = {}
    generated: list[dict[str, Any]] = []
    missing_targets: list[dict[str, int]] = []
    for team_id in sorted(integrated_ids):
        row = teams[team_id]
        mapped_players: list[tuple[int, int, int]] = []
        for source_id, shirt in zip(row["player_ids"], row["shirt_values"]):
            target_id = target_map.get(int(source_id))
            if target_id is None:
                missing_targets.append({"team_id": team_id, "pesdb_player_id": int(source_id)})
                continue
            if target_id not in player_ids:
                raise ValueError(
                    f"PESDB player {source_id} maps to absent Player.bin row {target_id}"
                )
            if target_id in owner_by_target:
                raise ValueError(
                    f"PESDB physical target {target_id} is used by more than one club"
                )
            owner_by_target[target_id] = team_id
            rating = ratings.get(target_id)
            if rating is None:
                raise ValueError(
                    f"PESDB player {source_id} target {target_id} has no authoritative OVR"
                )
            mapped_players.append((target_id, rating[0], rating[1]))
        if len(mapped_players) != len(row["player_ids"]):
            continue
        if len(mapped_players) < 11:
            raise ValueError(f"PESDB team {team_id} has fewer than 11 mapped players")
        physical_id = integrated_physical_map[team_id]
        roles = tactic_roles[physical_id]
        starting_indices, bench_indices = choose_balanced_xi(mapped_players, roles)
        order = starting_indices + bench_indices
        target_ids = [mapped_players[index][0] for index in order]
        shirts = [row["shirt_values"][index] for index in order]
        source_ids = [int(row["player_ids"][index]) for index in order]
        xi = [mapped_players[index] for index in starting_indices]

        def rounded_average(values: list[int]) -> int:
            return (sum(values) + len(values) // 2) // len(values)

        defensive = [overall for (_pid, overall, _pos), role in zip(xi, roles) if role <= 3]
        midfield = [overall for (_pid, overall, _pos), role in zip(xi, roles) if 4 <= role <= 8]
        forward = [overall for (_pid, overall, _pos), role in zip(xi, roles) if role >= 9]
        if not defensive or not midfield or not forward:
            raise ValueError(f"PESDB team {team_id} has an invalid native role split")
        team_rating = {
            "forward": rounded_average(forward),
            "midfield": rounded_average(midfield),
            "defence": rounded_average(defensive),
            "overall": rounded_average([overall for _pid, overall, _pos in xi]),
        }
        generated.append(
            {
                "team_id": team_id,
                "physical_team_id": physical_id,
                "symbol": symbol_for(team_id),
                "target_ids": target_ids,
                "source_ids": source_ids,
                "shirts": shirts,
                "formation_roles": roles,
                "starting_overalls": [player[1] for player in xi],
                "starting_positions": [player[2] for player in xi],
                "team_rating": team_rating,
            }
        )
    if missing_targets:
        raise ValueError(f"PESDB target map is incomplete: {missing_targets[:20]}")

    metadata = {
        "schema_version": 1,
        "authority": AUTHORITY,
        "policy": {
            "pesdb_rosters_only": True,
            "pesdb_player_values_only": True,
            "pes21_used_for": ["target_row_format", "physical_slot_inventory"],
            "missing_target_blocks_release": True,
            "cross_club_duplicate_targets_block_release": True,
        },
        "roster_snapshot_sha256": sha256_file(rosters_path),
        "target_map_sha256": sha256_file(target_map_path),
        "player_bin_sha256": sha256_file(player_path),
        "cleanup_report_sha256": sha256_file(cleanup_report_path),
        "integrated_team_ids": [row["team_id"] for row in generated],
        "held_back_pesdb_team_ids": held_back,
        "physical_team_map": physical_team_map,
        "mapped_player_count": len(owner_by_target),
        "authoritative_rating_count": len(ratings),
        "authoritative_rating_source": rating_source,
        "native_tactics_source": tactics_source,
        "position_balanced_starting_xi": True,
        "catalog_club_count": len(club_team_ids),
        "preserve_national_team_membership": True,
        "team_count": len(generated),
        "content_id": None,
    }
    metadata["lineup_digest"] = hashlib.sha256(
        json.dumps(
            [
                {
                    "team_id": row["team_id"],
                    "physical_team_id": row["physical_team_id"],
                    "target_ids": row["target_ids"],
                    "formation_roles": row["formation_roles"],
                    "team_rating": row["team_rating"],
                }
                for row in generated
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    metadata["content_id"] = content_id(metadata)

    lines = [
        "// Generated by tools/generate_pesdb_runtime_rosters.py.",
        f"// PESDB eFootball Authentic content ID: {metadata['content_id']}",
        f"// Roster snapshot SHA-256: {metadata['roster_snapshot_sha256']}",
        "// Player IDs below are physical PES21-schema rows selected by the",
        "// reviewed PESDB target map; no PES21 player values are used as source.",
        "// Do not edit manually.",
        "",
        "static const uint32_t exhibition_pesdb_club_team_ids[] = {",
        wrapped(sorted(club_team_ids), "u"),
        "};",
        "",
        "static const ExhibitionPesdbPlayerOwner exhibition_pesdb_player_owners[] = {",
    ]
    for target_id, team_id in sorted(owner_by_target.items()):
        lines.append(f"    {{{target_id}u, {team_id}u}},")
    lines.extend(
        [
            "};",
            "",
            "static const ExhibitionPesdbPlayerRating exhibition_pesdb_player_ratings[] = {",
        ]
    )
    for target_id, (overall, position) in sorted(ratings.items()):
        lines.append(f"    {{{target_id}u, {overall}u, {position}u}},")
    lines.extend(
        [
            "};",
            "",
            "static const ExhibitionPesdbTeamRating exhibition_pesdb_team_ratings[] = {",
        ]
    )
    for row in generated:
        rating = row["team_rating"]
        lines.append(
            "    "
            f"{{{row['team_id']}u, {rating['forward']}u, {rating['midfield']}u, "
            f"{rating['defence']}u, {rating['overall']}u}},"
        )
    lines.extend(["};", ""])
    for row in generated:
        symbol = row["symbol"]
        target_ids = row["target_ids"]
        shirts = row["shirts"]
        lines.extend(
            [
                f"static const uint32_t exhibition_pesdb_{symbol}_players[] = {{",
                wrapped(target_ids, "u"),
                "};",
                f"static const uint8_t exhibition_pesdb_{symbol}_shirts[] = {{",
                wrapped(shirts, ""),
                "};",
                "",
            ]
        )
    lines.append("static const ExhibitionMasterRoster exhibition_pesdb_master_rosters[] = {")
    for row in generated:
        team_id = row["team_id"]
        symbol = row["symbol"]
        lines.extend(
            [
                "    {",
                f"        {team_id}u,",
                f"        exhibition_pesdb_{symbol}_players,",
                f"        exhibition_pesdb_{symbol}_shirts,",
                f"        sizeof(exhibition_pesdb_{symbol}_players) /",
                f"            sizeof(exhibition_pesdb_{symbol}_players[0]),",
                "    },",
            ]
        )
    lines.extend(["};", ""])
    output_content = "\n".join(lines)

    report_lines = [
        "# PESDB Runtime Rosters",
        "",
        "This generated runtime table uses `https://pesdb.net/efootball` Authentic",
        "as the sole source for current club membership, roster order, and shirt",
        "numbers. PES21 contributes only physical row layout/slot inventory.",
        "",
        f"- Content ID: `{metadata['content_id']}`",
        f"- Integrated teams: **{len(generated)}**",
        f"- Mapped physical player rows: **{len(owner_by_target)}**",
        f"- Authoritative PESDB base OVR rows: **{len(ratings)}**",
        f"- Catalog club teams protected by ownership filtering: **{len(club_team_ids)}**",
        f"- Held-back PESDB teams: **{len(held_back)}**",
        f"- Target-map coverage: **{len(owner_by_target)}/{sum(len(teams[team_id]['player_ids']) for team_id in integrated_ids)}**",
        "",
        "## Release policy",
        "",
        "- A missing PESDB row, target slot, or physical Player.bin row blocks generation.",
        "- Cross-club duplicate physical targets block generation.",
        "- PESDB-owned physical rows are filtered from every legacy club roster at runtime.",
        "- National-team memberships are deliberately preserved.",
        "- Base OVR is read from the generated PESDB table; non-PESDB rows retain the native calculation.",
        "- Starting XIs are assigned to the native formation roles before the bench is sorted by OVR.",
        "- Skills, foot, styles, form, body fields, and other unverified offsets remain report-only.",
        "",
        "## Teams",
        "",
        "| PESDB team | Mapped players | Runtime physical team |",
        "|---:|---:|---:|",
    ]
    for row in generated:
        report_lines.append(
            f"| {row['team_id']} | {len(row['target_ids'])} | {row['physical_team_id']} |"
        )
    report_lines.extend(
        [
            "",
            "Held-back team IDs: " + ", ".join(str(value) for value in held_back),
            "",
        ]
    )
    report_content = "\n".join(report_lines)
    machine_content = json.dumps(
        {
            **metadata,
            "teams": {
                str(row["team_id"]): {
                    "physical_team_id": row["physical_team_id"],
                    "ordered_source_ids": row["source_ids"],
                    "ordered_target_ids": row["target_ids"],
                    "ordered_shirts": row["shirts"],
                    "formation_roles": row["formation_roles"],
                    "starting_overalls": row["starting_overalls"],
                    "starting_positions": row["starting_positions"],
                    "team_rating": row["team_rating"],
                }
                for row in generated
            },
        },
        indent=2,
        ensure_ascii=True,
    ) + "\n"
    if check:
        generated_outputs = [
            (output_path, output_content),
            (report_path, report_content),
        ]
        if metadata_output_path:
            generated_outputs.append((metadata_output_path, machine_content))
        stale = [
            path
            for path, content in generated_outputs
            if not path.is_file() or path.read_text(encoding="ascii") != content
        ]
        if stale:
            raise RuntimeError(
                "generated PESDB runtime files are stale: "
                + ", ".join(str(path) for path in stale)
            )
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_content, encoding="ascii", newline="\n")
        report_path.write_text(report_content, encoding="ascii", newline="\n")
        if metadata_output_path:
            metadata_output_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_output_path.write_text(machine_content, encoding="ascii", newline="\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--rosters", type=Path, default=DEFAULT_ROSTERS)
    parser.add_argument("--target-map", type=Path, default=DEFAULT_TARGET_MAP)
    parser.add_argument("--player", type=Path, default=DEFAULT_PLAYER)
    parser.add_argument("--player-report", type=Path, default=DEFAULT_PLAYER_REPORT)
    parser.add_argument("--cleanup-report", type=Path, default=DEFAULT_CLEANUP_REPORT)
    parser.add_argument(
        "--physical-team-map",
        type=Path,
        default=DEFAULT_CATALOG,
        help="catalog or logical-to-physical team map",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT)
    parser.add_argument("--tactics", type=Path, default=DEFAULT_TACTICS)
    parser.add_argument(
        "--tactics-formation", type=Path, default=DEFAULT_TACTICS_FORMATION
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    values = {
        "rosters_path": resolve(root, args.rosters),
        "target_map_path": resolve(root, args.target_map),
        "player_path": resolve(root, args.player),
        "player_report_path": resolve(root, args.player_report),
        "cleanup_report_path": resolve(root, args.cleanup_report),
        "physical_team_map_path": resolve(root, args.physical_team_map),
        "output_path": resolve(root, args.output),
        "report_path": resolve(root, args.report),
        "metadata_output_path": resolve(root, args.metadata_output),
        "tactics_path": resolve(root, args.tactics),
        "tactics_formation_path": resolve(root, args.tactics_formation),
    }
    metadata = generate(**values, check=args.check)
    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
