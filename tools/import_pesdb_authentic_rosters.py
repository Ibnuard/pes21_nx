#!/usr/bin/env python3
"""Snapshot current authentic club rosters from pesdb.net/efootball.

Team IDs come from PESDB's authentic catalog. Player names and values are
joined from an existing authentic player snapshot, so PES21 is never consulted
as a roster or value fallback. Missing player rows remain an explicit release
blocker unless this command is allowed to fetch and verify them from PESDB.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_pesdb_efootball import (
    DEFAULT_CACHE,
    DEFAULT_SITEMAP,
    build_snapshot,
    canonical_content_id,
    fetch_authentic_team_roster,
    load_sitemap_index,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAYER_SNAPSHOT = Path(
    "local-debug/pesdb-efootball-identity-snapshot-all-active.json"
)
DEFAULT_OUTPUT = Path("local-debug/pesdb-efootball-authentic-rosters.json")


def resolve(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def load_player_snapshot(path: Path) -> dict[int, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported player snapshot schema")
    if payload.get("source") != "authentic":
        raise ValueError(f"{path}: authentic PESDB data is required")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError(f"{path}: unexpected player-data authority")
    raw = payload.get("players")
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: players must be an object")
    result: dict[int, dict[str, Any]] = {}
    for key, row in raw.items():
        player_id = int(key)
        if not isinstance(row, dict) or row.get("source") != "authentic":
            raise ValueError(f"{path}: malformed authentic row {key}")
        result[player_id] = row
    return result


def merge_player_snapshots(paths: list[Path]) -> dict[int, dict[str, Any]]:
    """Merge authentic PESDB snapshots and reject conflicting rows."""
    merged: dict[int, dict[str, Any]] = {}
    for path in paths:
        current = load_player_snapshot(path)
        for player_id, row in current.items():
            previous = merged.get(player_id)
            if previous is not None and previous != row:
                raise ValueError(
                    f"PESDB player {player_id} differs between snapshots"
                )
            merged[player_id] = row
    return merged


def merge_roster_snapshot(
    roster_path: Path,
    *,
    player_snapshots: list[Path],
) -> dict[str, Any]:
    """Refresh player completeness for an already fetched PESDB roster list."""
    payload = json.loads(roster_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("source") != "authentic":
        raise ValueError(f"{roster_path}: authentic roster snapshot is required")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError(f"{roster_path}: unexpected PESDB authority")
    teams = payload.get("teams")
    if not isinstance(teams, dict):
        raise ValueError(f"{roster_path}: teams must be an object")
    players = merge_player_snapshots(player_snapshots)
    requested: set[int] = set()
    for raw_team, row in teams.items():
        if not isinstance(row, dict):
            raise ValueError(f"{roster_path}: malformed team {raw_team}")
        ids = [int(value) for value in row.get("player_ids", [])]
        requested.update(ids)
        row["player_count"] = len(ids)
        raw_shirts = row.get("shirt_numbers", {})
        if not isinstance(raw_shirts, dict):
            raw_shirts = {}
        row["shirt_numbers"] = {
            str(player_id): (
                int(raw_shirts[str(player_id)])
                if raw_shirts.get(str(player_id)) is not None
                else None
            )
            for player_id in ids
        }
        missing = sorted(set(ids) - set(players))
        row["verified_players"] = len(ids) - len(missing)
        row["missing_player_ids"] = missing
        row["complete"] = not missing
    payload["players"] = {
        str(player_id): players[player_id]
        for player_id in sorted(requested & set(players))
    }
    payload["failures"] = {
        "teams": payload.get("failures", {}).get("teams", {}),
        "players": {
            str(player_id): "missing authentic player snapshot"
            for player_id in sorted(requested - set(players))
        },
    }
    payload["counts"] = {
        "requested_teams": len(teams),
        "fetched_teams": len(teams),
        "failed_teams": len(payload["failures"]["teams"]),
        "requested_players": len(requested),
        "verified_players": len(requested & set(players)),
        "failed_players": len(requested - set(players)),
        "complete_teams": sum(bool(row.get("complete")) for row in teams.values()),
    }
    payload["generated_by"] = "tools/import_pesdb_authentic_rosters.py"
    payload["source"] = "authentic"
    payload["authority"] = "https://pesdb.net/efootball"
    payload["policy"] = {
        "pesdb_rosters_only": True,
        "pesdb_player_values_only": True,
        "pes21_roster_or_value_fallback": False,
        "incomplete_teams_block_release": True,
    }
    payload["content_id"] = canonical_content_id(payload)
    return payload


def build_roster_snapshot(
    team_ids: list[int],
    *,
    existing_players: dict[int, dict[str, Any]],
    standard_urls: dict[int, str],
    cache_dir: Path,
    timeout: float,
    delay: float,
    retries: int,
    offline: bool,
) -> dict[str, Any]:
    teams: dict[str, dict[str, Any]] = {}
    requested_players: set[int] = set()
    failures: dict[str, str] = {}
    for team_id in sorted(set(team_ids)):
        try:
            roster_rows = fetch_authentic_team_roster(
                team_id,
                timeout=timeout,
                delay=delay,
            )
        except Exception as error:  # Keep every team failure visible in the report.
            failures[str(team_id)] = f"{type(error).__name__}: {error}"
            continue
        player_ids = [int(row["player_id"]) for row in roster_rows]
        requested_players.update(player_ids)
        teams[str(team_id)] = {
            "pesdb_team_id": team_id,
            "player_ids": player_ids,
            "player_count": len(player_ids),
            "shirt_numbers": {
                str(int(row["player_id"])): row.get("shirt_number")
                for row in roster_rows
            },
        }

    missing = sorted(requested_players - set(existing_players))
    fetched_players: dict[int, dict[str, Any]] = {}
    player_failures: dict[str, str] = {}
    if missing:
        fetched = build_snapshot(
            missing,
            standard_urls=standard_urls,
            source="authentic",
            cache_dir=cache_dir,
            workers=1,
            retries=retries,
            timeout=timeout,
            delay=delay,
            offline=offline,
        )
        fetched_players = {
            int(key): row for key, row in fetched.get("players", {}).items()
        }
        player_failures = {
            str(key): str(reason)
            for key, reason in fetched.get("failures", {}).items()
        }
    players = {**existing_players, **fetched_players}
    for row in teams.values():
        ids = [int(value) for value in row["player_ids"]]
        absent = [player_id for player_id in ids if player_id not in players]
        row["verified_players"] = len(ids) - len(absent)
        row["missing_player_ids"] = absent
        row["complete"] = not absent

    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/import_pesdb_authentic_rosters.py",
        "source": "authentic",
        "authority": "https://pesdb.net/efootball",
        "policy": {
            "pesdb_rosters_only": True,
            "pesdb_player_values_only": True,
            "pes21_roster_or_value_fallback": False,
            "incomplete_teams_block_release": True,
        },
        "teams": teams,
        "players": {
            str(player_id): players[player_id]
            for player_id in sorted(requested_players & set(players))
        },
        "failures": {
            "teams": failures,
            "players": player_failures,
        },
        "counts": {
            "requested_teams": len(set(team_ids)),
            "fetched_teams": len(teams),
            "failed_teams": len(failures),
            "requested_players": len(requested_players),
            "verified_players": len(requested_players & set(players)),
            "failed_players": len(requested_players - set(players)),
            "complete_teams": sum(bool(row["complete"]) for row in teams.values()),
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    payload["content_id"] = canonical_content_id(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--team-id", action="append", type=int, default=[])
    parser.add_argument("--player-snapshot", type=Path, default=DEFAULT_PLAYER_SNAPSHOT)
    parser.add_argument(
        "--extra-player-snapshot",
        action="append",
        type=Path,
        default=[],
        help="additional authentic player snapshot; repeatable and conflict-checked",
    )
    parser.add_argument(
        "--roster-input",
        type=Path,
        help="reuse an existing fetched roster list without refetching team pages",
    )
    parser.add_argument("--sitemap-url", default=DEFAULT_SITEMAP)
    parser.add_argument("--sitemap-cache", type=Path, default=DEFAULT_CACHE / "sitemap.json")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    snapshot_paths = [resolve(root, args.player_snapshot)] + [
        resolve(root, path) for path in args.extra_player_snapshot
    ]
    if args.roster_input:
        payload = merge_roster_snapshot(
            resolve(root, args.roster_input),
            player_snapshots=snapshot_paths,
        )
    else:
        if not args.team_id:
            parser.error("at least one --team-id is required without --roster-input")
        sitemap = load_sitemap_index(
            resolve(root, args.sitemap_cache),
            sitemap_url=args.sitemap_url,
        )
        payload = build_roster_snapshot(
            args.team_id,
            existing_players=merge_player_snapshots(snapshot_paths),
            standard_urls=sitemap,
            cache_dir=resolve(root, args.cache_dir),
            timeout=args.timeout,
            delay=args.delay,
            retries=args.retries,
            offline=args.offline,
        )
    output = resolve(root, args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["counts"], sort_keys=True))
    if args.require_complete and (
        payload["counts"]["failed_teams"]
        or payload["counts"]["failed_players"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
