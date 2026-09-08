#!/usr/bin/env python3
"""Plan deterministic PESDB-player -> PES21-mobile physical slots.

The source of player identity and values is always ``pesdb.net/efootball``.
PES21 is inspected only for its fixed row layout and for retired, unassigned
physical rows that can hold the verified PESDB values.  No binary is changed
by this tool.  A missing or unsafe slot is reported instead of silently
falling back to a stale player.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Iterable

from convert_efootball10_players import (
    PES21_PLAYER_SIZE,
    pes21_name,
    pes21_player_position,
    records,
)
from experimental_import_ef10_original import (
    PLAYER_ASSIGNMENT_ROW_SIZE,
    SPECIAL_ASSIGNMENT_ROW_SIZE,
    decode_wesys,
    ids_from_delete_list,
    ids_from_player_assignment,
    ids_from_special_assignment,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = Path("local-debug/pesdb-efootball-identity-snapshot-all-active.json")
DEFAULT_ROSTERS = Path("local-debug/pesdb-efootball-authentic-rosters-famous-teams.json")
DEFAULT_PLAYER = Path("local-debug/inter-miami-pesdb-reserved-merge/Player.bin")
DEFAULT_ASSIGNMENT = Path(
    "local-debug/inter-miami-pesdb-reserved-merge/PlayerAssignment.bin"
)
DEFAULT_SPECIAL = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/"
    "common/etc/pesdb/SpecialPlayerAssignment.bin"
)
DEFAULT_DELETE = Path(
    "local-debug/inter-miami-pesdb-reserved-merge/PlayerDeleteList.bin"
)
DEFAULT_OUTPUT = Path("local-debug/pesdb-efootball-target-map.json")


def resolve(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


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


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def load_authentic_snapshot(path: Path) -> dict[int, dict[str, Any]]:
    payload = load_json(path)
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported snapshot schema")
    if payload.get("source") != "authentic":
        raise ValueError(f"{path}: only PESDB authentic data is accepted")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError(f"{path}: unexpected data authority")
    rows = payload.get("players")
    if not isinstance(rows, dict):
        raise ValueError(f"{path}: players must be an object")
    result: dict[int, dict[str, Any]] = {}
    for raw_id, row in rows.items():
        player_id = int(raw_id)
        if not isinstance(row, dict) or row.get("source") != "authentic":
            raise ValueError(f"{path}: malformed authentic player {raw_id}")
        row_id = int(row.get("player_id", row.get("source_player_id", 0)))
        if row_id != player_id:
            raise ValueError(f"{path}: row ID mismatch for {raw_id}")
        if not isinstance(row.get("primary_position_index"), int):
            raise ValueError(f"{path}: player {player_id} lacks a registered position")
        if not isinstance(row.get("base_stats"), dict):
            raise ValueError(f"{path}: player {player_id} lacks PESDB stats")
        result[player_id] = row
    return result


def load_roster_ids(path: Path | None) -> set[int]:
    if path is None or not path.is_file():
        return set()
    payload = load_json(path)
    if payload.get("schema_version") != 1 or payload.get("source") != "authentic":
        raise ValueError(f"{path}: roster snapshot must be PESDB authentic")
    teams = payload.get("teams")
    players = payload.get("players")
    if not isinstance(teams, dict) or not isinstance(players, dict):
        raise ValueError(f"{path}: roster snapshot is missing teams or players")
    result: set[int] = set()
    for raw_team, row in teams.items():
        if not isinstance(row, dict) or not row.get("complete"):
            raise ValueError(f"{path}: team {raw_team} is incomplete")
        values = [int(value) for value in row.get("player_ids", [])]
        result.update(values)
        missing = sorted(set(values) - {int(value) for value in players})
        if missing:
            raise ValueError(f"{path}: team {raw_team} has missing players {missing}")
    return result


def load_target_map(paths: Iterable[Path]) -> dict[int, int]:
    merged: dict[int, int] = {}
    targets: dict[int, int] = {}
    for path in paths:
        payload = load_json(path)
        raw = payload.get("map", payload.get("source_to_target", payload))
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: expected a source-to-target map")
        for source, target in raw.items():
            source_id, target_id = int(source), int(target)
            if source_id <= 0 or target_id <= 0:
                raise ValueError(f"{path}: player IDs must be positive")
            previous = merged.get(source_id)
            if previous is not None and previous != target_id:
                raise ValueError(
                    f"source {source_id} maps to both {previous} and {target_id}"
                )
            previous_source = targets.get(target_id)
            if previous_source is not None and previous_source != source_id:
                raise ValueError(
                    f"target slot {target_id} is reused by {previous_source} and {source_id}"
                )
            merged[source_id] = target_id
            targets[target_id] = source_id
    return merged


def parse_target_player(path: Path) -> tuple[dict[int, bytes], set[int]]:
    raw = decode_wesys(path)
    rows = records(raw, PES21_PLAYER_SIZE)
    by_id = {struct.unpack_from("<I", row, 8)[0]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError(f"{path}: duplicate Player.bin IDs")
    return by_id, set(by_id)


def referenced_player_ids(assignment: Path, special: Path | None) -> set[int]:
    refs = ids_from_player_assignment(decode_wesys(assignment))
    if special is not None and special.is_file():
        refs.update(ids_from_special_assignment(decode_wesys(special)))
    return refs


def allocate_target_map(
    snapshot: dict[int, dict[str, Any]],
    *,
    target_rows: dict[int, bytes],
    deleted_ids: set[int],
    referenced_ids: set[int],
    existing_map: dict[int, int],
    reserved_target_ids: set[int] | None = None,
) -> dict[str, Any]:
    """Resolve every source row without using a player-value fallback."""
    reserved_target_ids = set(reserved_target_ids or set())
    target_ids = set(target_rows)
    source_ids = sorted(snapshot)
    # Reviewed mappings are contractual: they must be used exactly as given,
    # and their physical slots may never be consumed as a new donor/direct ID.
    reviewed_targets = set(existing_map.values())
    if len(reviewed_targets) != len(existing_map):
        raise ValueError("existing mappings reuse a physical target slot")
    missing_reviewed = sorted(reviewed_targets - target_ids)
    if missing_reviewed:
        raise ValueError(
            "existing mappings point outside Player.bin: "
            + ", ".join(str(value) for value in missing_reviewed[:20])
        )
    reserved_target_ids.update(reviewed_targets)
    used_targets: set[int] = set()
    mapping: dict[int, int] = {}
    rows: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    # Donors must remain outside both the active PESDB source set and all
    # reviewed maps. This prevents a later merge from deleting another player.
    active_source_ids = set(source_ids)
    donor_pool = {
        candidate
        for candidate in deleted_ids
        if candidate in target_ids
        and candidate not in referenced_ids
        and candidate not in active_source_ids
        and candidate not in reserved_target_ids
        and pes21_name(target_rows[candidate])
    }
    by_position: dict[int, list[int]] = {}
    for candidate in sorted(donor_pool):
        by_position.setdefault(pes21_player_position(target_rows[candidate]), []).append(candidate)

    for source_id in source_ids:
        player = snapshot[source_id]
        source_position = int(player["primary_position_index"])
        explicit = existing_map.get(source_id)
        if explicit is not None:
            if explicit in used_targets:
                raise ValueError(
                    f"reviewed target slot {explicit} was already allocated"
                )
            target_id = explicit
            mode = "reviewed_existing_map"
            donor_id = None
        elif (
            source_id in target_ids
            and source_id not in used_targets
            and source_id not in reviewed_targets
        ):
            target_id = source_id
            mode = "direct_current_id"
            donor_id = None
        else:
            candidates = [
                value
                for value in by_position.get(source_position, [])
                if value not in used_targets
            ]
            if not candidates:
                blocked.append(
                    {
                        "source_player_id": source_id,
                        "player_name": player.get("player_name"),
                        "position": source_position,
                        "reason": "no_safe_retired_unassigned_target",
                    }
                )
                continue
            donor_id = min(candidates, key=lambda value: (abs(value - source_id), value))
            target_id = source_id
            # The physical row keeps its donor ID in the target map. The
            # converted Player.bin row may later carry the source ID when an
            # original-ID lane explicitly supports that operation.
            target_id = donor_id
            mode = "retired_unassigned_slot"
        if target_id in used_targets:
            raise ValueError(f"target slot {target_id} was allocated twice")
        used_targets.add(target_id)
        mapping[source_id] = target_id
        rows.append(
            {
                "source_player_id": source_id,
                "target_player_id": target_id,
                "player_name": player.get("player_name"),
                "position": source_position,
                "mode": mode,
                "donor_player_id": donor_id,
                "data_source": "pesdb_efootball_authentic",
            }
        )

    return {
        "schema_version": 1,
        "authority": "https://pesdb.net/efootball",
        "policy": {
            "pesdb_only": True,
            "pes21_values_allowed": False,
            "pes21_used_for": ["target_row_format", "physical_slot_inventory"],
            "missing_target_blocks_release": True,
        },
        "counts": {
            "requested": len(source_ids),
            "mapped": len(mapping),
            "blocked": len(blocked),
            "direct_current_ids": sum(row["mode"] == "direct_current_id" for row in rows),
            "reviewed_existing_map": sum(
                row["mode"] == "reviewed_existing_map" for row in rows
            ),
            "retired_unassigned_slots": sum(
                row["mode"] == "retired_unassigned_slot" for row in rows
            ),
        },
        "map": {str(source): target for source, target in sorted(mapping.items())},
        "rows": rows,
        "blocked": blocked,
        "content_id": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--rosters", type=Path, default=DEFAULT_ROSTERS)
    parser.add_argument("--player", type=Path, default=DEFAULT_PLAYER)
    parser.add_argument("--assignment", type=Path, default=DEFAULT_ASSIGNMENT)
    parser.add_argument("--special", type=Path, default=DEFAULT_SPECIAL)
    parser.add_argument("--delete-list", type=Path, default=DEFAULT_DELETE)
    parser.add_argument("--target-map", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--fail-on-blocked", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    snapshot_path = resolve(root, args.snapshot)
    roster_path = resolve(root, args.rosters)
    snapshot = load_authentic_snapshot(snapshot_path)
    snapshot.update(
        {
            player_id: row
            for player_id, row in load_authentic_snapshot(roster_path).items()
        }
        if roster_path.is_file() and roster_path != snapshot_path
        else {}
    )
    if roster_path.is_file():
        roster_payload = load_json(roster_path)
        roster_players = roster_payload.get("players", {})
        if isinstance(roster_players, dict):
            for raw_id, row in roster_players.items():
                player_id = int(raw_id)
                if isinstance(row, dict) and row.get("source") == "authentic":
                    snapshot[player_id] = row
    target_path = resolve(root, args.player)
    assignment_path = resolve(root, args.assignment)
    special_path = resolve(root, args.special)
    delete_path = resolve(root, args.delete_list)
    target_rows, _target_ids = parse_target_player(target_path)
    deleted_ids = set(ids_from_delete_list(decode_wesys(delete_path)))
    refs = referenced_player_ids(assignment_path, special_path)
    existing = load_target_map(resolve(root, path) for path in args.target_map)
    payload = allocate_target_map(
        snapshot,
        target_rows=target_rows,
        deleted_ids=deleted_ids,
        referenced_ids=refs,
        existing_map=existing,
    )
    payload["source_sha256"] = {
        "snapshot": sha256_file(snapshot_path),
        "rosters": sha256_file(roster_path) if roster_path.is_file() else None,
        "player": sha256_file(target_path),
        "assignment": sha256_file(assignment_path),
        "special": sha256_file(special_path) if special_path.is_file() else None,
        "delete_list": sha256_file(delete_path),
        "target_maps": [sha256_file(resolve(root, path)) for path in args.target_map],
    }
    payload["content_id"] = content_id(payload)
    output = resolve(root, args.output)
    content = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"target map is stale: {output}")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    print(json.dumps(payload["counts"], sort_keys=True))
    if args.fail_on_blocked and payload["counts"]["blocked"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
