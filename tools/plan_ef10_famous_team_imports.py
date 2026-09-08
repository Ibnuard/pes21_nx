#!/usr/bin/env python3
"""Validate and report a detachable famous-team import batch.

This is a planning gate, not a runtime integrator.  It verifies EF10 identity,
roster/tactics availability, candidate PES21 physical slots, and currently
available badge/uniform assets.  A team becomes integration-ready only when
every fail-closed requirement is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from convert_efootball10_players import PES21_ABILITY_BITS
from pesdb import (
    decode_wesys,
    parse_ef10_assignments,
    parse_pes21_assignments,
    parse_tactics_team_ids,
    parse_team_records,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("data/ef10_famous_team_imports.json")
DEFAULT_INVENTORY = Path("data/exhibition_ef10_only_teams.json")
DEFAULT_EF10_DIR = Path("local-debug/efootball10-audit/tables/common/etc/pesdb")
DEFAULT_EF10_TACTICS_DIR = Path(
    "local-debug/efootball10-audit/compare/new_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_PES21_DIR = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_ASSET_ROOT = Path("local-debug/ef10-famous-team-assets")
DEFAULT_OUTPUT = Path("local-debug/ef10-famous-team-plan")
DEFAULT_PESDB_IDENTITY_MAP = Path(
    "local-debug/pesdb-efootball-identity-map-all-active.json"
)
DEFAULT_PESDB_SNAPSHOT = Path(
    "local-debug/pesdb-efootball-identity-snapshot-all-active.json"
)
DEFAULT_PESDB_ROSTERS = Path(
    "local-debug/pesdb-efootball-authentic-rosters-famous-teams.json"
)
DEFAULT_TARGET_PLAYER = Path(
    "local-debug/inter-miami-pesdb-reserved-merge/Player.bin"
)
DEFAULT_TARGET_MAP = Path("local-debug/pesdb-efootball-current-target-map.json")


def resolve(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def asset_candidates(asset_root: Path, team_id: int) -> dict[str, list[Path]]:
    badge = [
        asset_root / "badges" / f"e_{team_id:06d}_f.png",
        asset_root / "badges" / f"e_{team_id:06d}_f_l.png",
        asset_root / "badges" / f"e_{team_id:06d}_r.png",
        asset_root / "badges" / f"e_{team_id:06d}_r_l.png",
    ]
    uniform = [
        asset_root / "uniform" / str(team_id) / f"{team_id}_DEF_1st.bin",
        asset_root / "uniform" / str(team_id) / f"{team_id}_DEF_2nd.bin",
        asset_root / "uniform" / str(team_id) / f"{team_id}_DEF_GK1st.bin",
    ]
    return {"badge": badge, "uniform": uniform}


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def load_pesdb_identity_map(payload: dict[str, Any] | None) -> dict[int, int]:
    if payload is None:
        return {}
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported PESDB identity-map schema")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError("PESDB identity map has an unexpected authority")
    policy = payload.get("policy")
    if not isinstance(policy, dict) or not policy.get("pesdb_only"):
        raise ValueError("PESDB identity map does not enforce pesdb_only")
    if policy.get("pes21_values_allowed") is not False:
        raise ValueError("PESDB identity map permits PES21 player values")
    raw = payload.get("map")
    if not isinstance(raw, dict):
        raise ValueError("PESDB identity map is missing map")
    return {int(source): int(remote) for source, remote in raw.items()}


def load_pesdb_snapshot(payload: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
    if payload is None:
        return {}
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported PESDB snapshot schema")
    if payload.get("source") != "authentic":
        raise ValueError("famous-team release requires PESDB authentic data")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError("PESDB snapshot has an unexpected authority")
    raw = payload.get("players")
    if not isinstance(raw, dict):
        raise ValueError("PESDB snapshot is missing players")
    result: dict[int, dict[str, Any]] = {}
    for raw_source_id, row in raw.items():
        source_id = int(raw_source_id)
        if not isinstance(row, dict):
            raise ValueError(f"malformed PESDB row for source player {source_id}")
        if row.get("source") != "authentic":
            raise ValueError(f"PESDB player {source_id} is not authentic data")
        stats = row.get("base_stats")
        if not isinstance(stats, dict) or not set(PES21_ABILITY_BITS).issubset(stats):
            raise ValueError(
                f"PESDB player {source_id} lacks the verified gameplay abilities"
            )
        result[source_id] = row
    return result


def load_pesdb_rosters(
    payload: dict[str, Any] | None,
) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    """Validate current team membership and player values from PESDB Authentic."""
    if payload is None:
        return {}, {}
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported PESDB roster schema")
    if payload.get("source") != "authentic":
        raise ValueError("famous-team release requires PESDB authentic rosters")
    if payload.get("authority") != "https://pesdb.net/efootball":
        raise ValueError("PESDB roster snapshot has an unexpected authority")
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("PESDB roster snapshot is missing policy")
    if not policy.get("pesdb_rosters_only") or not policy.get("pesdb_player_values_only"):
        raise ValueError("PESDB roster snapshot does not enforce PESDB-only data")
    if policy.get("pes21_roster_or_value_fallback") is not False:
        raise ValueError("PESDB roster snapshot permits PES21 fallback")

    raw_players = payload.get("players")
    raw_teams = payload.get("teams")
    if not isinstance(raw_players, dict) or not isinstance(raw_teams, dict):
        raise ValueError("PESDB roster snapshot is missing teams or players")
    players: dict[int, dict[str, Any]] = {}
    for raw_id, row in raw_players.items():
        player_id = int(raw_id)
        if not isinstance(row, dict) or row.get("source") != "authentic":
            raise ValueError(f"malformed PESDB authentic player {raw_id}")
        if int(row.get("player_id", 0)) != player_id:
            raise ValueError(f"PESDB player key disagrees with row ID: {raw_id}")
        stats = row.get("base_stats")
        if not isinstance(stats, dict) or not set(PES21_ABILITY_BITS).issubset(stats):
            raise ValueError(f"PESDB player {player_id} lacks verified abilities")
        players[player_id] = row

    teams: dict[int, dict[str, Any]] = {}
    for raw_id, row in raw_teams.items():
        team_id = int(raw_id)
        if not isinstance(row, dict) or int(row.get("pesdb_team_id", 0)) != team_id:
            raise ValueError(f"malformed PESDB authentic team {raw_id}")
        player_ids = [int(value) for value in row.get("player_ids", [])]
        if not player_ids or len(player_ids) != len(set(player_ids)):
            raise ValueError(f"PESDB team {team_id} has an invalid roster")
        missing = sorted(set(player_ids) - set(players))
        if int(row.get("player_count", -1)) != len(player_ids):
            raise ValueError(f"PESDB team {team_id} player count is stale")
        copied = dict(row)
        copied["player_ids"] = player_ids
        copied["verified_players"] = len(player_ids) - len(missing)
        copied["missing_player_ids"] = missing
        copied["complete"] = not missing and bool(row.get("complete"))
        teams[team_id] = copied
    return teams, players


def load_player_target_map(payload: dict[str, Any] | None) -> dict[int, int]:
    if payload is None:
        return {}
    raw = payload.get("map", payload.get("source_to_target", payload))
    if not isinstance(raw, dict):
        raise ValueError("player target map must be an object")
    result = {int(source): int(target) for source, target in raw.items()}
    if any(source <= 0 or target <= 0 for source, target in result.items()):
        raise ValueError("player target map IDs must be positive")
    if len(result) != len(set(result.values())):
        raise ValueError("player target map reuses a physical player slot")
    return result


def target_player_ids(path: Path) -> set[int]:
    raw = decode_wesys(path)
    if len(raw) % 312:
        raise ValueError(f"{path}: Player.bin has a partial row")
    result = {
        struct.unpack_from("<I", raw, offset + 8)[0]
        for offset in range(0, len(raw), 312)
    }
    if len(result) != len(raw) // 312:
        raise ValueError(f"{path}: Player.bin has duplicate IDs")
    return result


def map_pesdb_roster_to_targets(
    roster_ids: list[int],
    *,
    target_ids: set[int],
    identity_map: dict[int, int],
    target_map: dict[int, int],
) -> dict[str, Any]:
    """Resolve current PESDB IDs to reviewed physical PES21-mobile slots."""
    reverse_identity: dict[int, int] = {}
    for source_id, pesdb_id in identity_map.items():
        previous = reverse_identity.get(pesdb_id)
        if previous is not None and previous != source_id:
            raise ValueError(f"PESDB player {pesdb_id} has multiple source identities")
        reverse_identity[pesdb_id] = source_id

    mapped: list[dict[str, Any]] = []
    missing: list[int] = []
    used_targets: set[int] = set()
    for pesdb_id in sorted(set(map(int, roster_ids))):
        # New target maps are keyed by the current PESDB Authentic ID. Check
        # that namespace first; legacy EF10 identity maps remain a fallback
        # only for rows explicitly reviewed in the older lane.
        reviewed_target = target_map.get(pesdb_id)
        if reviewed_target is not None:
            target_id = int(reviewed_target)
            source_id = reverse_identity.get(pesdb_id)
            mode = "reviewed_pesdb_target_map"
        elif pesdb_id in target_ids:
            target_id = pesdb_id
            source_id = reverse_identity.get(pesdb_id)
            mode = "direct_current_id"
        else:
            source_id = reverse_identity.get(pesdb_id)
            target_id = target_map.get(source_id, source_id) if source_id is not None else None
            if target_id not in target_ids:
                missing.append(pesdb_id)
                continue
            mode = "reviewed_legacy_identity_target"
        if target_id in used_targets:
            raise ValueError(f"current roster reuses physical player target {target_id}")
        used_targets.add(int(target_id))
        mapped.append(
            {
                "pesdb_player_id": pesdb_id,
                "source_player_id": source_id,
                "target_player_id": int(target_id),
                "mode": mode,
            }
        )
    return {
        "roster_players": len(set(roster_ids)),
        "mapped_players": len(mapped),
        "direct_current_ids": sum(row["mode"] == "direct_current_id" for row in mapped),
        "reviewed_pesdb_target_maps": sum(
            row["mode"] == "reviewed_pesdb_target_map" for row in mapped
        ),
        "reviewed_legacy_identity_targets": sum(
            row["mode"] == "reviewed_legacy_identity_target" for row in mapped
        ),
        "missing_target_player_ids": missing,
        "complete": not missing,
        "map": mapped,
    }


def pesdb_roster_coverage(
    roster_ids: list[int],
    identity_map: dict[int, int],
    snapshot: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    roster = sorted(set(map(int, roster_ids)))
    missing_identity = [player_id for player_id in roster if player_id not in identity_map]
    missing_snapshot = [player_id for player_id in roster if player_id not in snapshot]
    return {
        "roster_players": len(roster),
        "identity_players": len(roster) - len(missing_identity),
        "snapshot_players": len(roster) - len(missing_snapshot),
        "missing_identity_player_ids": missing_identity,
        "missing_snapshot_player_ids": missing_snapshot,
        "identity_complete": not missing_identity,
        "authentic_snapshot_complete": not missing_snapshot,
    }


def build_plan(
    *,
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    ef10_dir: Path,
    ef10_tactics_dir: Path,
    pes21_dir: Path,
    asset_root: Path,
    pesdb_identity_map: dict[int, int],
    pesdb_snapshot: dict[int, dict[str, Any]],
    pesdb_rosters: dict[int, dict[str, Any]] | None = None,
    pesdb_roster_players: dict[int, dict[str, Any]] | None = None,
    target_ids: set[int] | None = None,
    player_target_map: dict[int, int] | None = None,
) -> dict[str, Any]:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported famous-team manifest schema")
    if inventory.get("schema_version") != 1:
        raise ValueError("unsupported EF10-only inventory schema")
    rows = manifest.get("teams")
    if not isinstance(rows, list) or not rows:
        raise ValueError("manifest teams must be a non-empty list")
    ids = [int(row["ef10_team_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("manifest contains duplicate EF10 team IDs")
    priorities = [int(row["priority"]) for row in rows]
    if sorted(priorities) != list(range(1, len(rows) + 1)):
        raise ValueError("team priorities must be unique and contiguous")
    physical = [
        int(row["physical_team_id"])
        for row in rows
        if row.get("physical_team_id") is not None
    ]
    if len(physical) != len(set(physical)):
        raise ValueError("manifest reuses a physical PES21 team slot")

    inventory_by_id = {int(row["ef10_team_id"]): row for row in inventory["teams"]}
    ef10_teams = parse_team_records(decode_wesys(ef10_dir / "Team.bin"), "ef10")
    ef10_rosters = parse_ef10_assignments(decode_wesys(ef10_dir / "PlayerAssignment.bin"))
    ef10_tactics = parse_tactics_team_ids(
        decode_wesys(ef10_tactics_dir / "Tactics.bin"), "ef10"
    )
    pes21_teams = parse_team_records(decode_wesys(pes21_dir / "Team.bin"), "pes21")
    pes21_rosters = parse_pes21_assignments(decode_wesys(pes21_dir / "PlayerAssignment.bin"))
    minimum = int(manifest["policy"]["require_minimum_players"])
    pesdb_rosters = pesdb_rosters or {}
    pesdb_roster_players = pesdb_roster_players or {}
    target_ids = target_ids or set()
    player_target_map = player_target_map or {}
    result_rows: list[dict[str, Any]] = []
    for configured in sorted(rows, key=lambda row: int(row["priority"])):
        team_id = int(configured["ef10_team_id"])
        source = ef10_teams.get(team_id)
        inventory_row = inventory_by_id.get(team_id)
        current_roster = pesdb_rosters.get(team_id)
        current_roster_ids = (
            [int(value) for value in current_roster["player_ids"]]
            if current_roster is not None
            else []
        )
        requirements: dict[str, bool] = {
            "present_in_ef10_team_table": source is not None,
            "absent_from_pes21_by_same_id": team_id not in pes21_teams,
            "inventory_classified": inventory_row is not None,
            "ef10_tactics": team_id in ef10_tactics,
            "pesdb_current_roster_present": current_roster is not None,
            "pesdb_current_roster_minimum": len(current_roster_ids) >= minimum,
            "pesdb_current_roster_complete": bool(
                current_roster is not None and current_roster.get("complete")
            ),
        }
        source_roster_ids = [row.player_id for row in ef10_rosters.get(team_id, [])]
        legacy_pesdb_coverage = pesdb_roster_coverage(
            source_roster_ids, pesdb_identity_map, pesdb_snapshot
        )
        target_coverage = map_pesdb_roster_to_targets(
            current_roster_ids,
            target_ids=target_ids,
            identity_map=pesdb_identity_map,
            target_map=player_target_map,
        )
        requirements["pesdb_target_mapping_complete"] = bool(target_coverage["complete"])
        physical_id = configured.get("physical_team_id")
        if physical_id is None:
            requirements["physical_slot_selected"] = False
            physical_name = None
            physical_roster_count = 0
        else:
            physical_id = int(physical_id)
            physical_team = pes21_teams.get(physical_id)
            requirements["physical_slot_selected"] = physical_team is not None
            physical_name = physical_team.name if physical_team else None
            physical_roster_count = len(pes21_rosters.get(physical_id, []))
        candidates = asset_candidates(asset_root, team_id)
        badge_files = [path for path in candidates["badge"] if path.is_file()]
        uniform_files = [path for path in candidates["uniform"] if path.is_file()]
        requirements["badge_asset"] = bool(badge_files)
        requirements["uniform_assets_complete"] = len(uniform_files) == len(candidates["uniform"])
        ready = all(requirements.values())
        result_rows.append(
            {
                "ef10_team_id": team_id,
                "ef10_name": source.name if source else None,
                "display_name": configured["display_name"],
                "category": configured["category"],
                "priority": int(configured["priority"]),
                "mode": configured["mode"],
                "classification": inventory_row.get("classification") if inventory_row else None,
                "ef10_roster_count": len(ef10_rosters.get(team_id, [])),
                "pesdb_current_roster_count": len(current_roster_ids),
                "direct_shared_player_count": inventory_row.get("direct_shared_player_count", 0) if inventory_row else 0,
                "physical_team_id": physical_id,
                "physical_team_name": physical_name,
                "physical_roster_count": physical_roster_count,
                "requirements": requirements,
                "ready_for_detachable_integration": ready,
                "missing_requirements": sorted(key for key, value in requirements.items() if not value),
                "assets": {
                    "badges": [str(path.relative_to(asset_root)).replace("\\", "/") for path in badge_files],
                    "uniforms": [str(path.relative_to(asset_root)).replace("\\", "/") for path in uniform_files],
                },
                "legacy_roster_identity_coverage": legacy_pesdb_coverage,
                "pesdb_target_coverage": target_coverage,
                "pesdb_players_verified": sum(
                    player_id in pesdb_roster_players for player_id in current_roster_ids
                ),
            }
        )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/plan_ef10_famous_team_imports.py",
        "policy": manifest["policy"],
        "player_data_authority": "https://pesdb.net/efootball",
        "counts": {
            "planned": len(result_rows),
            "ready": sum(row["ready_for_detachable_integration"] for row in result_rows),
            "blocked": sum(not row["ready_for_detachable_integration"] for row in result_rows),
            "alias_candidates_with_slots": sum(row["physical_team_id"] is not None for row in result_rows),
            "new_slots_required": sum(row["physical_team_id"] is None for row in result_rows),
            "current_pesdb_roster_players": sum(
                row["pesdb_current_roster_count"] for row in result_rows
            ),
            "current_pesdb_players_without_target": sum(
                len(row["pesdb_target_coverage"]["missing_target_player_ids"])
                for row in result_rows
            ),
        },
        "source_sha256": {
            "ef10_team": sha256_file(ef10_dir / "Team.bin"),
            "ef10_assignments": sha256_file(ef10_dir / "PlayerAssignment.bin"),
            "ef10_tactics": sha256_file(ef10_tactics_dir / "Tactics.bin"),
            "pes21_team": sha256_file(pes21_dir / "Team.bin"),
            "pes21_assignments": sha256_file(pes21_dir / "PlayerAssignment.bin"),
        },
        "teams": result_rows,
    }
    payload["content_id"] = content_id(payload)
    return payload


def render_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# EF10 famous-team import plan",
        "",
        "Player values are sourced from `pesdb.net/efootball/authentic`. PES21",
        "is used only for target format and physical slot inventory.",
        "",
        f"- Content ID: `{payload['content_id']}`",
        f"- Planned teams: {counts['planned']}",
        f"- Ready: {counts['ready']}",
        f"- Blocked (fail-closed): {counts['blocked']}",
        f"- Existing alias slots: {counts['alias_candidates_with_slots']}",
        f"- New physical slots required: {counts['new_slots_required']}",
        f"- Current PESDB roster rows: {counts['current_pesdb_roster_players']}",
        f"- Current PESDB players needing slots: {counts['current_pesdb_players_without_target']}",
        "",
        "| Priority | Team | EF10 ID | PES21 physical | Roster | Status | Missing |",
        "|---:|---|---:|---:|---:|---|---|",
    ]
    for row in payload["teams"]:
        physical = row["physical_team_id"] if row["physical_team_id"] is not None else "TBD"
        status = "READY" if row["ready_for_detachable_integration"] else "BLOCKED"
        lines.append(
            f"| {row['priority']} | {row['display_name']} | {row['ef10_team_id']} | "
            f"{physical} | {row['pesdb_current_roster_count']} | {status} | "
            f"{', '.join(row['missing_requirements']) or '-'} |"
        )
    lines.extend(
        [
            "",
            "No team is integrated until its physical slot, badge, three uniform",
            "definitions, EF10 tactics, and minimum roster all pass this gate.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--ef10-dir", type=Path, default=DEFAULT_EF10_DIR)
    parser.add_argument("--ef10-tactics-dir", type=Path, default=DEFAULT_EF10_TACTICS_DIR)
    parser.add_argument("--pes21-dir", type=Path, default=DEFAULT_PES21_DIR)
    parser.add_argument("--asset-root", type=Path, default=DEFAULT_ASSET_ROOT)
    parser.add_argument(
        "--pesdb-identity-map",
        type=Path,
        default=DEFAULT_PESDB_IDENTITY_MAP,
    )
    parser.add_argument(
        "--pesdb-snapshot",
        type=Path,
        default=DEFAULT_PESDB_SNAPSHOT,
    )
    parser.add_argument("--pesdb-rosters", type=Path, default=DEFAULT_PESDB_ROSTERS)
    parser.add_argument("--target-player", type=Path, default=DEFAULT_TARGET_PLAYER)
    parser.add_argument("--player-target-map", type=Path, default=DEFAULT_TARGET_MAP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads(resolve(root, args.manifest).read_text(encoding="utf-8"))
    inventory = json.loads(resolve(root, args.inventory).read_text(encoding="utf-8"))
    identity_payload = load_optional_json(resolve(root, args.pesdb_identity_map))
    snapshot_payload = load_optional_json(resolve(root, args.pesdb_snapshot))
    roster_path = resolve(root, args.pesdb_rosters)
    roster_payload = load_optional_json(roster_path)
    roster_teams, roster_players = load_pesdb_rosters(roster_payload)
    target_player_path = resolve(root, args.target_player)
    player_target_path = resolve(root, args.player_target_map)
    payload = build_plan(
        manifest=manifest,
        inventory=inventory,
        ef10_dir=resolve(root, args.ef10_dir),
        ef10_tactics_dir=resolve(root, args.ef10_tactics_dir),
        pes21_dir=resolve(root, args.pes21_dir),
        asset_root=resolve(root, args.asset_root),
        pesdb_identity_map=load_pesdb_identity_map(identity_payload),
        pesdb_snapshot=load_pesdb_snapshot(snapshot_payload),
        pesdb_rosters=roster_teams,
        pesdb_roster_players=roster_players,
        target_ids=target_player_ids(target_player_path) if target_player_path.is_file() else set(),
        player_target_map=load_player_target_map(load_optional_json(player_target_path)),
    )
    payload["source_sha256"].update(
        {
            "pesdb_rosters": sha256_file(roster_path) if roster_path.is_file() else None,
            "target_player": sha256_file(target_player_path) if target_player_path.is_file() else None,
            "player_target_map": sha256_file(player_target_path) if player_target_path.is_file() else None,
        }
    )
    payload["content_id"] = content_id({key: value for key, value in payload.items() if key != "content_id"})
    output = resolve(root, args.output_dir)
    files = {
        output / "import-plan.json": json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        output / "README.md": render_report(payload),
    }
    if args.check:
        for path, content in files.items():
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                raise RuntimeError(f"generated plan is stale: {path}")
    else:
        output.mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            path.write_text(content, encoding="utf-8")
    print(json.dumps(payload["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
