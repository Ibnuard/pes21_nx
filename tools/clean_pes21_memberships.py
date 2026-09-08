#!/usr/bin/env python3
"""Build an isolated global PES21 PlayerAssignment cleanup.

Ownership is derived from current PESDB eFootball Authentic rosters. PES21 and
EF10 tables are never used as a player-value or current-roster fallback. A
player may keep national team memberships, but once an authoritative club
owner is known, stale memberships in other known club slots are removed.
PESDB teams without an integrated runtime/catalog slot are reported and left
untouched until their physical team lane is complete.

The command writes only a local-debug WESYS patch.  Runtime integration is a
separate, reviewable step.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from exhibition_team_catalog import catalog_team_map, load_catalog
from pesdb import (
    decode_wesys,
    parse_category_team_list,
    parse_team_records,
)
from convert_efootball10_players import encode_pes21_wesys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PES21_DIR = Path(
    "local-debug/efootball10-audit/compare/"
    "old_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_CATALOG = Path("data/exhibition_team_catalog.json")
DEFAULT_CONFIG = Path("data/exhibition_team_categories.json")
DEFAULT_PESDB_ROSTERS = Path(
    "local-debug/pesdb-efootball-authentic-rosters-current-54-complete.json"
)
DEFAULT_OUTPUT = Path("local-debug/pes21-membership-cleanup")
DEFAULT_RUNTIME_ROSTER_METADATA = Path(
    "local-debug/pesdb-runtime-rosters-generated.json"
)
DEFAULT_EF10_CATEGORIES = Path(
    "local-debug/efootball10-audit/tables/common/etc/pesdb/CategoryTeamList.bin"
)
ASSIGNMENT_SIZE = 16


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def resolve(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def split_rows(raw: bytes) -> list[bytes]:
    if len(raw) % ASSIGNMENT_SIZE:
        raise ValueError("PlayerAssignment.bin has a partial row")
    return [raw[offset : offset + ASSIGNMENT_SIZE] for offset in range(0, len(raw), ASSIGNMENT_SIZE)]


def assignment_fields(row: bytes) -> tuple[int, int, int, int]:
    return struct.unpack("<IIII", row)


def load_target_map(
    path: Path | None,
    *,
    excluded_source_ids: set[int] | None = None,
) -> dict[int, int]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("map", payload)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a player map object")
    excluded_source_ids = excluded_source_ids or set()
    result = {
        int(source): int(target)
        for source, target in raw.items()
        if int(source) not in excluded_source_ids
    }
    if len(result) != len(set(result.values())):
        raise ValueError(f"{path}: duplicate target player IDs")
    return result


def load_target_maps(
    paths: list[Path],
    *,
    excluded_source_ids: set[int] | None = None,
) -> dict[int, int]:
    merged: dict[int, int] = {}
    for path in paths:
        current = load_target_map(
            path,
            excluded_source_ids=excluded_source_ids,
        )
        for source_id, target_id in current.items():
            previous = merged.get(source_id)
            if previous is not None and previous != target_id:
                raise ValueError(
                    f"conflicting target for EF10 player {source_id}: "
                    f"{previous} and {target_id}"
                )
            merged[source_id] = target_id
    if len(merged) != len(set(merged.values())):
        raise ValueError("combined target maps contain duplicate target player IDs")
    return merged


def load_retired_player_ids(path: Path | None) -> set[int]:
    """Load donor/source IDs deliberately removed by an original-ID import."""
    if path is None:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected an object")
    raw = payload.get("retired_player_ids")
    if raw is None:
        raw_map = payload.get("donor_to_original", {})
        if not isinstance(raw_map, dict):
            raise ValueError(f"{path}: donor_to_original must be an object")
        raw = list(raw_map)
    if not isinstance(raw, list):
        raise ValueError(f"{path}: retired_player_ids must be a list")
    result = {int(value) for value in raw}
    if any(value <= 0 for value in result):
        raise ValueError(f"{path}: retired player IDs must be positive")
    return result


def load_physical_team_map(path: Path | None) -> dict[int, int]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("physical_team_map", payload)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected logical-to-physical team map")
    result = {int(logical): int(physical) for logical, physical in raw.items()}
    if any(key <= 0 or value <= 0 for key, value in result.items()):
        raise ValueError(f"{path}: team IDs must be positive")
    if len(result) != len(set(result.values())):
        raise ValueError(f"{path}: duplicate physical team IDs")
    return result


def load_pesdb_roster_details(path: Path) -> dict[int, list[tuple[int, int]]]:
    """Load ordered player IDs and shirt numbers from PESDB Authentic only."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported PESDB roster schema")
    if payload.get("source") != "authentic":
        raise ValueError(f"{path}: PESDB Authentic roster data is required")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError(f"{path}: unexpected roster authority")
    policy = payload.get("policy", {})
    if policy.get("pes21_roster_or_value_fallback") is not False:
        raise ValueError(f"{path}: PES21 roster fallback is forbidden")
    teams = payload.get("teams")
    players = payload.get("players")
    if not isinstance(teams, dict) or not isinstance(players, dict):
        raise ValueError(f"{path}: teams and players must be objects")
    result: dict[int, list[tuple[int, int]]] = {}
    for raw_team, row in teams.items():
        team_id = int(raw_team)
        if not isinstance(row, dict) or not row.get("complete"):
            raise ValueError(f"{path}: team {team_id} is incomplete")
        player_ids = [int(value) for value in row.get("player_ids", [])]
        if not player_ids or len(player_ids) != len(set(player_ids)):
            raise ValueError(f"{path}: team {team_id} has invalid player IDs")
        missing = sorted(set(player_ids) - {int(value) for value in players})
        if missing:
            raise ValueError(
                f"{path}: team {team_id} is missing authentic players {missing[:20]}"
            )
        raw_shirts = row.get("shirt_numbers")
        if not isinstance(raw_shirts, dict):
            raise ValueError(f"{path}: team {team_id} has no PESDB shirt map")
        roster: list[tuple[int, int]] = []
        for player_id in player_ids:
            shirt = raw_shirts.get(str(player_id))
            if not isinstance(shirt, int) or not 0 <= shirt <= 255:
                raise ValueError(
                    f"{path}: team {team_id} player {player_id} has invalid shirt"
                )
            roster.append((player_id, shirt))
        nonzero_shirts = [shirt for _player_id, shirt in roster if shirt]
        if len(nonzero_shirts) != len(set(nonzero_shirts)):
            raise ValueError(f"{path}: team {team_id} has duplicate shirt numbers")
        result[team_id] = roster
    if not result:
        raise ValueError(f"{path}: no PESDB Authentic club rosters found")
    return result


def load_pesdb_rosters(path: Path) -> dict[int, list[int]]:
    return {
        team_id: [player_id for player_id, _shirt in roster]
        for team_id, roster in load_pesdb_roster_details(path).items()
    }


def load_position_balanced_rosters(
    path: Path,
    roster_details: dict[int, list[tuple[int, int]]],
    integrated_team_ids: set[int],
) -> dict[int, list[tuple[int, int]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("position_balanced_starting_xi") is not True:
        raise ValueError(f"{path}: runtime roster metadata is not position-balanced")
    teams = payload.get("teams")
    if not isinstance(teams, dict):
        raise ValueError(f"{path}: runtime roster metadata has no teams")
    result: dict[int, list[tuple[int, int]]] = {}
    for team_id in sorted(integrated_team_ids):
        row = teams.get(str(team_id))
        if not isinstance(row, dict):
            raise ValueError(f"{path}: missing runtime roster team {team_id}")
        source_ids = [int(value) for value in row.get("ordered_source_ids", [])]
        shirts = [int(value) for value in row.get("ordered_shirts", [])]
        roles = [int(value) for value in row.get("formation_roles", [])]
        original = roster_details.get(team_id, [])
        original_shirts = {player_id: shirt for player_id, shirt in original}
        if (
            len(source_ids) != len(original)
            or len(source_ids) != len(set(source_ids))
            or set(source_ids) != set(original_shirts)
            or len(shirts) != len(source_ids)
            or len(roles) != 11
        ):
            raise ValueError(f"{path}: invalid position-balanced roster {team_id}")
        ordered = list(zip(source_ids, shirts))
        if any(original_shirts[player_id] != shirt for player_id, shirt in ordered):
            raise ValueError(f"{path}: shirt map drift for team {team_id}")
        result[team_id] = ordered
    return result


def derive_physical_team_map(catalog: dict[str, Any]) -> dict[int, int]:
    """Read logical/physical mappings from the generated selector catalog."""
    result: dict[int, int] = {}
    for row in catalog.get("teams", []):
        logical = int(row.get("team_id", 0))
        physical = int(row.get("physical_team_id", logical))
        if physical == logical:
            continue
        if logical <= 0 or physical <= 0:
            raise ValueError("catalog logical/physical team IDs must be positive")
        if physical in result.values():
            raise ValueError("catalog teams reuse a physical team slot")
        result[logical] = physical
    return result


def classify_pes21_club_ids(
    *,
    pes21_team_path: Path,
    ef10_categories_path: Path,
    config: dict[str, Any],
    catalog: dict[str, Any],
) -> tuple[set[int], set[int]]:
    """Classify every physical PES21 team while preserving national squads."""
    pes21_team_ids = set(
        parse_team_records(decode_wesys(pes21_team_path), "pes21")
    )
    categories = parse_category_team_list(decode_wesys(ef10_categories_path))
    national_category_ids = {
        int(category_id)
        for row in config.get("categories", [])
        if row.get("kind") == "national"
        for category_id in row.get("source_category_ids", [])
    }
    if not national_category_ids:
        raise ValueError("team config does not identify national categories")
    national_team_ids = {
        entry.team_id
        for category_id in national_category_ids
        for entry in categories.get(category_id, [])
        if entry.team_id in pes21_team_ids
    }
    national_team_ids.update(
        int(team["physical_team_id"])
        for team in catalog.get("teams", [])
        if team.get("kind") == "national"
    )
    if not national_team_ids:
        raise RuntimeError("PES21 national-team classification is empty")
    return pes21_team_ids - national_team_ids, national_team_ids


def build_pesdb_authoritative_owners(
    *,
    pesdb_rosters: dict[int, list[int]],
    catalog: dict[str, Any],
    physical_team_map: dict[int, int],
    pes21_player_ids: set[int],
    target_map: dict[int, int],
    include_unintegrated: bool = False,
) -> tuple[
    dict[int, int],
    dict[int, list[int]],
    list[dict[str, Any]],
    dict[int, set[int]],
    set[int],
    set[int],
]:
    """Resolve current PESDB IDs to owners without an EF10 fallback.

    Returns owners, source memberships, unresolved rows, integrated team IDs,
    and PESDB teams intentionally held back because no runtime slot exists.
    """
    team_by_id = catalog_team_map(catalog)
    catalog_club_ids = {
        team_id
        for team_id, team in team_by_id.items()
        if str(team.get("kind")) == "club"
    }
    runtime_team_ids = catalog_club_ids | set(physical_team_map)
    runtime_team_ids |= set(physical_team_map.values())
    integrated_team_ids = (
        set(pesdb_rosters)
        if include_unintegrated
        else set(pesdb_rosters) & runtime_team_ids
    )
    held_back_team_ids = set(pesdb_rosters) - integrated_team_ids
    owner_by_player: dict[int, int] = {}
    player_sources: dict[int, list[int]] = defaultdict(list)
    memberships: dict[int, set[int]] = defaultdict(set)
    unresolved: list[dict[str, Any]] = []
    for logical_team_id in sorted(integrated_team_ids):
        physical_team_id = int(physical_team_map.get(logical_team_id, logical_team_id))
        for source_id in pesdb_rosters[logical_team_id]:
            target_player_id = int(target_map.get(source_id, source_id))
            if target_player_id not in pes21_player_ids:
                unresolved.append(
                    {
                        "team_id": logical_team_id,
                        "pesdb_player_id": source_id,
                        "reason": "target_player_missing",
                    }
                )
                continue
            previous = owner_by_player.get(target_player_id)
            if previous is not None and previous != physical_team_id:
                raise RuntimeError(
                    f"PESDB player {source_id} maps to multiple club owners: "
                    f"{previous} and {physical_team_id}"
                )
            owner_by_player[target_player_id] = physical_team_id
            player_sources[target_player_id].append(logical_team_id)
            memberships[physical_team_id].add(target_player_id)
    return (
        owner_by_player,
        player_sources,
        unresolved,
        dict(memberships),
        integrated_team_ids,
        held_back_team_ids,
    )


def clean_assignments(
    raw: bytes,
    *,
    owners: dict[int, int],
    known_club_ids: set[int],
    replaced_club_ids: set[int] | None = None,
    authoritative_memberships: dict[int, set[int]] | None = None,
    minimum_players: int,
    strict_minimum: bool = True,
    retired_player_ids: set[int] | None = None,
) -> tuple[bytes, dict[str, Any]]:
    rows = split_rows(raw)
    replaced_club_ids = replaced_club_ids or set()
    retired_player_ids = retired_player_ids or set()
    authoritative_memberships = authoritative_memberships or {}
    seen_pairs: set[tuple[int, int]] = set()
    before_counts: Counter[int] = Counter()
    after_counts: Counter[int] = Counter()
    removed_candidates: list[tuple[bytes, dict[str, int]]] = []
    for row in rows:
        assignment_id, player_id, team_id, packed = assignment_fields(row)
        pair = (team_id, player_id)
        if pair in seen_pairs:
            raise ValueError(f"duplicate PlayerAssignment membership: {pair}")
        seen_pairs.add(pair)
        before_counts[team_id] += 1
        owner = owners.get(player_id)
        is_retired_donor = player_id in retired_player_ids
        missing_from_current_roster = (
            team_id in authoritative_memberships
            and player_id not in authoritative_memberships[team_id]
        )
        should_remove = team_id in known_club_ids and (
            is_retired_donor
            or missing_from_current_roster
            or (owner is not None and team_id != owner)
        )
        if should_remove:
            removed_candidates.append(
                (
                    row,
                {
                    "assignment_id": assignment_id,
                    "player_id": player_id,
                    "stale_team_id": team_id,
                    "authoritative_team_id": owner,
                    "reason": (
                        "retired_donor_membership"
                        if is_retired_donor
                        else (
                            "stale_replaced_club_membership"
                            if missing_from_current_roster
                            else "stale_club_membership"
                        )
                    ),
                },
                )
            )
            continue
        after_counts[team_id] += 1

    candidate_by_team: defaultdict[int, list[tuple[bytes, dict[str, int]]]] = defaultdict(list)
    for row, detail in removed_candidates:
        candidate_by_team[int(detail["stale_team_id"])].append((row, detail))
    blocked: list[dict[str, int]] = []
    removed: list[dict[str, int]] = []
    remove_keys: set[tuple[int, int, int]] = set()
    for team_id, candidates in sorted(candidate_by_team.items()):
        has_authoritative_replacement = team_id in replaced_club_ids
        allowed = (
            len(candidates)
            if has_authoritative_replacement
            else max(0, before_counts[team_id] - minimum_players)
        )
        if strict_minimum and not has_authoritative_replacement and len(candidates) > allowed:
            raise RuntimeError(
                f"cleanup would leave club {team_id} below minimum "
                f"({before_counts[team_id] - len(candidates)} players)"
            )
        selected = candidates[:allowed] if not strict_minimum else candidates
        rejected = candidates[allowed:] if not strict_minimum else []
        for row, detail in selected:
            removed.append(detail)
            remove_keys.add(
                (
                    int(detail["assignment_id"]),
                    int(detail["player_id"]),
                    int(detail["stale_team_id"]),
                )
            )
        for row, detail in rejected:
            blocked.append({**detail, "reason": "minimum_roster_guard"})
            after_counts[team_id] += 1

    # Preserve the original assignment ordering; packed assignment IDs are
    # consumed by native lookup code and should not be renumbered here.
    kept = [
        row
        for row in rows
        if (
            assignment_fields(row)[0],
            assignment_fields(row)[1],
            assignment_fields(row)[2],
        )
        not in remove_keys
    ]

    affected = sorted({int(row["stale_team_id"]) for row in removed})
    guarded_affected = [
        team_id for team_id in affected if team_id not in replaced_club_ids
    ]
    too_small = {
        team_id: after_counts[team_id]
        for team_id in affected
        if team_id not in replaced_club_ids
        and after_counts[team_id] < minimum_players
    }
    if too_small and strict_minimum:
        raise RuntimeError(
            "cleanup would leave club rosters below minimum: "
            + ", ".join(f"{team}={count}" for team, count in sorted(too_small.items()))
        )
    report = {
        "assignment_rows_before": len(rows),
        "assignment_rows_after": len(kept),
        "removed_memberships": len(removed),
        "blocked_by_minimum_roster_guard": len(blocked),
        "authoritative_replacement_clubs": len(
            set(affected) & replaced_club_ids
        ),
        "affected_clubs": len(affected),
        "affected_team_ids": affected,
        "minimum_players_after_cleanup": (
            min(after_counts[team] for team in guarded_affected)
            if guarded_affected
            else 0
        ),
        "minimum_native_rows_in_replaced_clubs": (
            min(
                after_counts[team]
                for team in affected
                if team in replaced_club_ids
            )
            if set(affected) & replaced_club_ids
            else 0
        ),
        "removed": removed,
        "blocked": blocked,
        "retired_donor_memberships_removed": sum(
            row.get("reason") == "retired_donor_membership" for row in removed
        ),
    }
    return b"".join(kept), report


def replace_authoritative_rosters(
    raw: bytes,
    *,
    cleanup_report: dict[str, Any],
    roster_details: dict[int, list[tuple[int, int]]],
    integrated_team_ids: set[int],
    physical_team_map: dict[int, int],
    target_map: dict[int, int],
    pes21_player_ids: set[int],
    known_club_ids: set[int],
) -> tuple[bytes, dict[str, Any]]:
    """Replace integrated physical club rosters with exact PESDB ordering."""
    rows = split_rows(raw)
    parsed = [assignment_fields(row) for row in rows]
    cleanup_keys = {
        (
            int(item["assignment_id"]),
            int(item["player_id"]),
            int(item["stale_team_id"]),
        )
        for item in cleanup_report.get("removed", [])
    }

    authoritative: dict[int, list[tuple[int, int]]] = {}
    logical_by_physical: dict[int, int] = {}
    target_owner: dict[int, int] = {}
    for logical_team_id in sorted(integrated_team_ids):
        physical_team_id = int(
            physical_team_map.get(logical_team_id, logical_team_id)
        )
        if physical_team_id in authoritative:
            raise ValueError(
                f"physical team {physical_team_id} is assigned more than once"
            )
        source_roster = roster_details.get(logical_team_id)
        if not source_roster:
            raise ValueError(
                f"integrated team {logical_team_id} has no PESDB roster details"
            )
        resolved: list[tuple[int, int]] = []
        for source_player_id, shirt in source_roster:
            target_player_id = int(
                target_map.get(source_player_id, source_player_id)
            )
            if target_player_id not in pes21_player_ids:
                raise ValueError(
                    f"PESDB player {source_player_id} maps to missing row "
                    f"{target_player_id}"
                )
            previous = target_owner.get(target_player_id)
            if previous is not None and previous != physical_team_id:
                raise ValueError(
                    f"physical player {target_player_id} belongs to teams "
                    f"{previous} and {physical_team_id}"
                )
            target_owner[target_player_id] = physical_team_id
            resolved.append((target_player_id, shirt))
        authoritative[physical_team_id] = resolved
        logical_by_physical[physical_team_id] = logical_team_id

    physical_ids = set(authoritative)
    first_index: dict[int, int] = {}
    template_flags: dict[int, list[int]] = defaultdict(list)
    removed_ids: set[int] = set()
    removal_keys: set[tuple[int, int, int]] = set(cleanup_keys)
    for index, (assignment_id, player_id, team_id, packed) in enumerate(parsed):
        if team_id in physical_ids:
            first_index.setdefault(team_id, index)
            template_flags[team_id].append(packed & 0xFFFF0000)
            removal_keys.add((assignment_id, player_id, team_id))
        if (assignment_id, player_id, team_id) in removal_keys:
            removed_ids.add(assignment_id)

    missing_templates = sorted(physical_ids - set(first_index))
    if missing_templates:
        raise RuntimeError(
            "physical team slots have no PlayerAssignment template rows: "
            + ", ".join(map(str, missing_templates))
        )

    total_required = sum(len(roster) for roster in authoritative.values())
    if len(removed_ids) < total_required:
        raise RuntimeError(
            f"roster replacement needs {total_required} assignment IDs; "
            f"only {len(removed_ids)} safely removed IDs are available"
        )
    available_ids = iter(sorted(removed_ids))
    replacement_rows: dict[int, list[bytes]] = {}
    used_assignment_ids: set[int] = set()
    for physical_team_id in sorted(authoritative):
        flags = template_flags[physical_team_id]
        generated: list[bytes] = []
        for order, (player_id, shirt) in enumerate(authoritative[physical_team_id]):
            assignment_id = next(available_ids)
            used_assignment_ids.add(assignment_id)
            packed = flags[min(order, len(flags) - 1)] | ((order & 0xFF) << 8) | shirt
            generated.append(
                struct.pack(
                    "<IIII", assignment_id, player_id, physical_team_id, packed
                )
            )
        replacement_rows[first_index[physical_team_id]] = generated

    output_rows: list[bytes] = []
    for index, (raw_row, fields) in enumerate(zip(rows, parsed)):
        output_rows.extend(replacement_rows.get(index, []))
        assignment_id, player_id, team_id, _packed = fields
        if (assignment_id, player_id, team_id) in removal_keys:
            continue
        output_rows.append(raw_row)

    rebuilt = [assignment_fields(row) for row in output_rows]
    assignment_ids = [row[0] for row in rebuilt]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise RuntimeError("roster replacement produced duplicate assignment IDs")

    observed: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
    memberships: dict[int, list[int]] = defaultdict(list)
    for _assignment_id, player_id, team_id, packed in rebuilt:
        if team_id in physical_ids:
            observed[team_id].append((player_id, packed & 0xFF, (packed >> 8) & 0xFF))
        if player_id in target_owner:
            memberships[player_id].append(team_id)
    for physical_team_id, roster in authoritative.items():
        expected = [
            (player_id, shirt, order)
            for order, (player_id, shirt) in enumerate(roster)
        ]
        if observed.get(physical_team_id) != expected:
            raise RuntimeError(
                f"physical team {physical_team_id} does not match PESDB roster"
            )
    duplicate_clubs: list[dict[str, Any]] = []
    national_memberships = 0
    for player_id, team_ids in memberships.items():
        owner = target_owner[player_id]
        club_teams = [team_id for team_id in team_ids if team_id in known_club_ids]
        stale = [team_id for team_id in club_teams if team_id != owner]
        if stale:
            duplicate_clubs.append(
                {"player_id": player_id, "owner": owner, "stale_clubs": stale}
            )
        national_memberships += sum(team_id not in known_club_ids for team_id in team_ids)
    if duplicate_clubs:
        raise RuntimeError(
            f"authoritative players retain stale clubs: {duplicate_clubs[:20]}"
        )

    unused_removed_ids = removed_ids - used_assignment_ids
    return b"".join(output_rows), {
        "integrated_teams": len(authoritative),
        "logical_to_physical": {
            str(logical_by_physical[physical]): physical
            for physical in sorted(logical_by_physical)
        },
        "pesdb_memberships_inserted": total_required,
        "assignment_rows_before": len(rows),
        "assignment_rows_after": len(output_rows),
        "removed_assignment_ids_available": len(removed_ids),
        "removed_assignment_ids_unused": len(unused_removed_ids),
        "club_duplicate_memberships": 0,
        "national_memberships_preserved": national_memberships,
        "exact_roster_order_and_shirts": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--pes21-dir", type=Path, default=DEFAULT_PES21_DIR)
    parser.add_argument(
        "--player",
        type=Path,
        help="optional current/experimental Player.bin; defaults to --pes21-dir/Player.bin",
    )
    parser.add_argument(
        "--assignment",
        type=Path,
        help="optional current/experimental PlayerAssignment.bin; defaults to --pes21-dir/PlayerAssignment.bin",
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--ef10-categories",
        type=Path,
        default=DEFAULT_EF10_CATEGORIES,
        help="EF10 CategoryTeamList used only to preserve national memberships",
    )
    parser.add_argument(
        "--pesdb-rosters",
        type=Path,
        default=DEFAULT_PESDB_ROSTERS,
        help="complete current PESDB eFootball Authentic roster snapshot",
    )
    parser.add_argument(
        "--include-unintegrated-pesdb-teams",
        action="store_true",
        help="allow candidate PESDB teams without a runtime/catalog slot (unsafe for release)",
    )
    parser.add_argument(
        "--target-map",
        action="append",
        type=Path,
        default=[],
        help="source-to-target player map; repeat to merge conversion lanes",
    )
    parser.add_argument(
        "--retired-map",
        type=Path,
        help="original-ID map whose donor IDs were removed from Player.bin",
    )
    parser.add_argument("--physical-team-map", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--runtime-roster-metadata",
        type=Path,
        default=DEFAULT_RUNTIME_ROSTER_METADATA,
        help="generated PESDB XI/bench order consumed by runtime and assignment rows",
    )
    parser.add_argument("--minimum-players", type=int, default=18)
    parser.add_argument(
        "--replace-integrated-rosters",
        action="store_true",
        help="replace every integrated physical club roster with PESDB order/shirts",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    pes21_dir = resolve(root, args.pes21_dir)
    catalog = load_catalog(resolve(root, args.catalog))
    config = json.loads(resolve(root, args.config).read_text(encoding="utf-8"))
    pesdb_roster_path = resolve(root, args.pesdb_rosters)
    if not pesdb_roster_path.is_file():
        raise FileNotFoundError(
            "complete PESDB Authentic roster snapshot is required: "
            + str(pesdb_roster_path)
        )
    pesdb_roster_details = load_pesdb_roster_details(pesdb_roster_path)
    pesdb_rosters = {
        team_id: [player_id for player_id, _shirt in roster]
        for team_id, roster in pesdb_roster_details.items()
    }
    retired_ids = load_retired_player_ids(
        resolve(root, args.retired_map) if args.retired_map else None
    )
    target_map_paths = [resolve(root, path) for path in args.target_map]
    target_map = load_target_maps(target_map_paths)
    physical_map = load_physical_team_map(
        resolve(root, args.physical_team_map) if args.physical_team_map else None
    )
    if not args.physical_team_map:
        physical_map = derive_physical_team_map(catalog)
    player_path = resolve(root, args.player) if args.player else pes21_dir / "Player.bin"
    assignment_path = (
        resolve(root, args.assignment)
        if args.assignment
        else pes21_dir / "PlayerAssignment.bin"
    )
    player_raw = decode_wesys(player_path)
    player_ids = {
        struct.unpack_from("<I", player_raw, offset + 8)[0]
        for offset in range(0, len(player_raw), 312)
    }
    assignment_raw = decode_wesys(assignment_path)
    (
        owners,
        player_sources,
        unresolved,
        authoritative_memberships,
        integrated_pesdb_team_ids,
        held_back_pesdb_team_ids,
    ) = build_pesdb_authoritative_owners(
        pesdb_rosters=pesdb_rosters,
        catalog=catalog,
        physical_team_map=physical_map,
        pes21_player_ids=player_ids,
        target_map=target_map,
        include_unintegrated=args.include_unintegrated_pesdb_teams,
    )
    if unresolved:
        preview = ", ".join(
            f"{row['team_id']}:{row['pesdb_player_id']}" for row in unresolved[:20]
        )
        raise RuntimeError(
            f"PESDB cleanup blocked by {len(unresolved)} unresolved memberships: "
            + preview
        )
    known_club_ids, national_team_ids = classify_pes21_club_ids(
        pes21_team_path=pes21_dir / "Team.bin",
        ef10_categories_path=resolve(root, args.ef10_categories),
        config=config,
        catalog=catalog,
    )
    known_club_ids.update(physical_map.values())
    known_club_ids.update(integrated_pesdb_team_ids)
    patched_raw, report = clean_assignments(
        assignment_raw,
        owners=owners,
        known_club_ids=known_club_ids,
        replaced_club_ids=set(owners.values()),
        authoritative_memberships=authoritative_memberships,
        minimum_players=max(1, args.minimum_players),
        retired_player_ids=retired_ids,
    )
    if args.replace_integrated_rosters:
        runtime_roster_metadata = resolve(root, args.runtime_roster_metadata)
        if not runtime_roster_metadata.is_file():
            raise FileNotFoundError(runtime_roster_metadata)
        ordered_roster_details = load_position_balanced_rosters(
            runtime_roster_metadata,
            pesdb_roster_details,
            integrated_pesdb_team_ids,
        )
        patched_raw, replacement_report = replace_authoritative_rosters(
            assignment_raw,
            cleanup_report=report,
            roster_details=ordered_roster_details,
            integrated_team_ids=integrated_pesdb_team_ids,
            physical_team_map=physical_map,
            target_map=target_map,
            pes21_player_ids=player_ids,
            known_club_ids=known_club_ids,
        )
        replacement_report["position_balanced_starting_xi"] = True
        replacement_report["runtime_roster_metadata"] = str(
            args.runtime_roster_metadata
        )
        report["roster_replacement"] = replacement_report
    report.update(
        {
            "schema_version": 1,
            "authority": "https://pesdb.net/efootball (Authentic current rosters)",
            "catalog_content_id": catalog["content_id"],
            "source_sha256": {
                "pes21_player": sha256_bytes(player_raw),
                "pes21_assignment": sha256_file(assignment_path),
                "pesdb_rosters": sha256_file(pesdb_roster_path),
            },
            "authoritative_players": len(owners),
            "unresolved_pesdb_memberships": len(unresolved),
            "unresolved": unresolved,
            "pesdb_authoritative_team_ids": sorted(integrated_pesdb_team_ids),
            "pesdb_teams_held_back_without_runtime_slot": sorted(
                held_back_pesdb_team_ids
            ),
            "pesdb_only": True,
            "preserved_national_memberships": True,
            "classified_physical_club_teams": len(known_club_ids),
            "classified_national_teams": len(national_team_ids),
            "unknown_team_ids_untouched": False,
            "integrated_rosters_replaced": bool(args.replace_integrated_rosters),
            "target_maps": [str(path) for path in args.target_map],
            "physical_team_map": str(args.physical_team_map) if args.physical_team_map else None,
            "retired_map": str(args.retired_map) if args.retired_map else None,
            "retired_player_ids": sorted(retired_ids),
            "owner_team_counts": dict(sorted(Counter(owners.values()).items())),
        }
    )
    encoded_assignment = encode_pes21_wesys(patched_raw)
    report["output_sha256"] = {
        "player_assignment_raw": sha256_bytes(patched_raw),
        "player_assignment_bin": sha256_bytes(encoded_assignment),
    }
    report["content_id"] = content_id(report)
    output = resolve(root, args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "PlayerAssignment.bin").write_bytes(encoded_assignment)
    (output / "cleanup-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in ("removed_memberships", "affected_clubs", "unresolved_pesdb_memberships", "content_id")}, sort_keys=True))


if __name__ == "__main__":
    main()
