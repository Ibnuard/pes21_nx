#!/usr/bin/env python3
"""Generate safe club-roster cleanup rules from active EF10 transfers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from exhibition_team_catalog import (
    catalog_team_map,
    load_catalog,
    parse_master_rosters,
)
from pesdb import (
    PlayerAssignment,
    decode_wesys,
    parse_ef10_assignments,
    parse_pes21_assignments,
    parse_player_records,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EF10_DIR = Path("local-debug/efootball10-audit/tables/common/etc/pesdb")
DEFAULT_PES21_DIR = Path(
    "local-debug/efootball10-audit/compare/"
    "old_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_ACTIVE_ROSTERS = Path("source/exhibition_rosters_ef10.inc")
DEFAULT_OUTPUT = Path("data/exhibition_legacy_player_cleanup.json")
DEFAULT_REPORT = Path("EFOOTBALL10_LEGACY_CLEANUP.md")
ACTIVE_ROSTER_SYMBOL = "exhibition_ef10_master_rosters"


def resolve_from_root(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def normalize_player_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", errors="ignore").decode("ascii").upper()
    return " ".join(re.findall(r"[A-Z0-9]+", value))


def unique_player_count(roster: list[PlayerAssignment]) -> int:
    return len({assignment.player_id for assignment in roster if assignment.player_id})


def build_cleanup(
    *,
    catalog: dict[str, Any],
    active_rosters_path: Path,
    ef10_dir: Path,
    pes21_dir: Path,
) -> dict[str, Any]:

    source_paths = {
        "active_ef10_rosters": active_rosters_path,
        "ef10_players": ef10_dir / "Player.bin",
        "ef10_assignments": ef10_dir / "PlayerAssignment.bin",
        "pes21_players": pes21_dir / "Player.bin",
        "pes21_assignments": pes21_dir / "PlayerAssignment.bin",
    }
    missing = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing cleanup source files: " + ", ".join(missing))

    team_by_id = catalog_team_map(catalog)
    catalog_club_ids = {
        team_id for team_id, team in team_by_id.items() if team["kind"] == "club"
    }
    active_rosters = parse_master_rosters(
        active_rosters_path, ACTIVE_ROSTER_SYMBOL
    )
    active_team_ids = list(active_rosters)
    unknown_active_ids = set(active_team_ids) - set(team_by_id)
    if unknown_active_ids:
        raise ValueError(
            "active EF10 rosters are absent from the team catalog: "
            + ", ".join(map(str, sorted(unknown_active_ids)))
        )
    active_club_ids = set(active_team_ids) & catalog_club_ids
    fallback_club_ids = catalog_club_ids - active_club_ids

    ef10_players = parse_player_records(
        decode_wesys(source_paths["ef10_players"]), "ef10"
    )
    pes21_players = parse_player_records(
        decode_wesys(source_paths["pes21_players"]), "pes21"
    )
    ef10_rosters = parse_ef10_assignments(
        decode_wesys(source_paths["ef10_assignments"])
    )
    pes21_rosters = parse_pes21_assignments(
        decode_wesys(source_paths["pes21_assignments"])
    )

    owner_by_player: dict[int, int] = {}
    for team_id in sorted(active_club_ids):
        resolved_player_ids = set(active_rosters[team_id][0])
        for assignment in ef10_rosters.get(team_id, []):
            if assignment.player_id not in resolved_player_ids:
                continue
            previous = owner_by_player.setdefault(assignment.player_id, team_id)
            if previous != team_id:
                raise RuntimeError(
                    f"EF10 player {assignment.player_id} belongs to active clubs "
                    f"{previous} and {team_id}"
                )

    minimum_players = int(catalog["policy"]["minimum_players"])
    removals: list[dict[str, int | str]] = []
    affected_counts: dict[int, int] = defaultdict(int)
    cleaned_counts: dict[int, int] = {}
    removed_pairs: set[tuple[int, int]] = set()
    for team_id in sorted(fallback_club_ids):
        roster = pes21_rosters.get(team_id)
        if not roster:
            raise RuntimeError(f"fallback club {team_id} has no PES21 roster")
        for assignment in roster:
            destination_team_id = owner_by_player.get(assignment.player_id)
            if destination_team_id is None:
                continue
            pair = (team_id, assignment.player_id)
            if pair in removed_pairs:
                raise RuntimeError(
                    f"duplicate cleanup membership for team {team_id}, "
                    f"player {assignment.player_id}"
                )
            removed_pairs.add(pair)
            affected_counts[team_id] += 1
            removals.append(
                {
                    "fallback_team_id": team_id,
                    "player_id": assignment.player_id,
                    "destination_team_id": destination_team_id,
                    "match": "shared_player_id",
                }
            )
        removed_count = affected_counts.get(team_id, 0)
        if removed_count:
            cleaned_count = unique_player_count(roster) - removed_count
            if cleaned_count < minimum_players:
                raise RuntimeError(
                    f"cleanup leaves team {team_id} with only {cleaned_count} players"
                )
            cleaned_counts[team_id] = cleaned_count

    # Same-name/different-ID matches are intentionally review-only. Namesakes
    # are common enough that deleting them automatically is not safe.
    active_by_name: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for player_id, team_id in sorted(owner_by_player.items()):
        player = ef10_players.get(player_id)
        if player is None:
            raise RuntimeError(f"active EF10 player record is missing: {player_id}")
        normalized = normalize_player_name(player.name)
        if normalized:
            active_by_name[normalized].append((player_id, team_id))

    name_only_review: list[dict[str, int | str]] = []
    for team_id in sorted(fallback_club_ids):
        for assignment in pes21_rosters[team_id]:
            if (team_id, assignment.player_id) in removed_pairs:
                continue
            player = pes21_players.get(assignment.player_id)
            if player is None:
                raise RuntimeError(
                    f"PES21 roster references missing player {assignment.player_id}"
                )
            normalized = normalize_player_name(player.name)
            candidates = active_by_name.get(normalized, [])
            if not normalized or len(candidates) != 1:
                continue
            active_player_id, destination_team_id = candidates[0]
            if active_player_id == assignment.player_id:
                continue
            active_player = ef10_players[active_player_id]
            if (
                player.nationality_code != active_player.nationality_code
                or player.position != active_player.position
            ):
                continue
            name_only_review.append(
                {
                    "fallback_team_id": team_id,
                    "pes21_player_id": assignment.player_id,
                    "active_ef10_player_id": active_player_id,
                    "destination_team_id": destination_team_id,
                    "normalized_name": normalized,
                    "match_evidence": ["normalized_name", "nationality", "position"],
                    "action": "review_only",
                }
            )

    removals.sort(
        key=lambda row: (
            int(row["fallback_team_id"]),
            int(row["player_id"]),
            int(row["destination_team_id"]),
        )
    )
    name_only_review.sort(
        key=lambda row: (
            int(row["fallback_team_id"]),
            int(row["pes21_player_id"]),
        )
    )
    minimum_cleaned_count = min(cleaned_counts.values()) if cleaned_counts else 0
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/generate_legacy_player_cleanup.py",
        "catalog_content_id": catalog["content_id"],
        "policy": {
            "scope": "club_to_club",
            "automatic_identity": "shared_player_id",
            "name_only_matches": "review_only",
            "preserve_national_team_membership": True,
            "minimum_players_after_cleanup": minimum_players,
        },
        "counts": {
            "active_ef10_teams": len(active_team_ids),
            "active_ef10_clubs": len(active_club_ids),
            "fallback_clubs": len(fallback_club_ids),
            "affected_fallback_clubs": len(affected_counts),
            "removed_legacy_memberships": len(removals),
            "minimum_cleaned_roster": minimum_cleaned_count,
            "name_only_review_candidates": len(name_only_review),
        },
        "source_sha256": {
            key: sha256_file(path) for key, path in sorted(source_paths.items())
        },
        "active_ef10_team_ids": active_team_ids,
        "active_ef10_club_team_ids": sorted(active_club_ids),
        "cleaned_player_counts": {
            str(team_id): count for team_id, count in sorted(cleaned_counts.items())
        },
        "removals": removals,
        "name_only_review": name_only_review,
    }
    payload["content_id"] = content_id(payload)
    return payload


def render_report(payload: dict[str, Any], catalog: dict[str, Any]) -> str:
    team_by_id = catalog_team_map(catalog)
    counts = payload["counts"]
    removals = payload["removals"]
    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in removals:
        by_team[int(row["fallback_team_id"])].append(row)

    lines = [
        "# eFootball 10 Legacy Player Cleanup",
        "",
        "This generated manifest removes stale club membership only when the same",
        "stable player ID belongs to an active EF10 club. National-team membership",
        "is deliberately preserved. Same-name/different-ID matches remain review-only",
        "because unrelated players can share a display name.",
        "",
        "## Result",
        "",
        f"- Cleanup content ID: `{payload['content_id']}`",
        f"- Active EF10 rosters: {counts['active_ef10_teams']}",
        f"- Active EF10 clubs: {counts['active_ef10_clubs']}",
        f"- Fallback clubs checked: {counts['fallback_clubs']}",
        f"- Affected fallback clubs: {counts['affected_fallback_clubs']}",
        f"- Stale club memberships removed: {counts['removed_legacy_memberships']}",
        f"- Smallest cleaned roster: {counts['minimum_cleaned_roster']} players",
        f"- Name-only candidates held for review: {counts['name_only_review_candidates']}",
        "",
        "## Retained legacy teams affected",
        "",
        "| Team | Removed | Players after cleanup |",
        "|---|---:|---:|",
    ]
    for team_id in (115, 127, 133, 134, 135):
        if team_id not in by_team:
            continue
        lines.append(
            f"| {team_by_id[team_id]['display_name']} | {len(by_team[team_id])} | "
            f"{payload['cleaned_player_counts'][str(team_id)]} |"
        )

    lewandowski = next(
        (
            row
            for row in removals
            if int(row["fallback_team_id"]) == 127
            and int(row["player_id"]) == 40002
            and int(row["destination_team_id"]) == 108
        ),
        None,
    )
    lines.extend(
        [
            "",
            "## Expected transfer sentinel",
            "",
            (
                "- PASS: player ID `40002` is removed from FC Bayern Munchen and "
                "retained by FC Barcelona."
                if lewandowski
                else "- FAIL: the Bayern to Barcelona Lewandowski sentinel is absent."
            ),
            "",
            "The cleanup is consumed by the generated PES21 fallback roster table.",
            "The team catalog generator refreshes this manifest and the fallback table",
            "together whenever the active EF10 roster set changes.",
            "",
        ]
    )
    review = payload["name_only_review"]
    if review:
        lines.extend(
            [
                "## Name-only review queue",
                "",
                "These rows match normalized name, nationality, and registered position,",
                "but use different player IDs. They are not removed without an explicit",
                "identity confirmation.",
                "",
                "| Old club | PES21 ID | Name key | EF10 ID | Candidate club |",
                "|---|---:|---|---:|---|",
            ]
        )
        for row in review:
            old_team_id = int(row["fallback_team_id"])
            destination_team_id = int(row["destination_team_id"])
            lines.append(
                f"| {team_by_id[old_team_id]['display_name']} | "
                f"{row['pes21_player_id']} | {row['normalized_name']} | "
                f"{row['active_ef10_player_id']} | "
                f"{team_by_id[destination_team_id]['display_name']} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_or_check(path: Path, content: str, check: bool) -> None:
    normalized = content.rstrip() + "\n"
    if check:
        existing = path.read_text(encoding="utf-8") if path.is_file() else None
        if existing != normalized:
            raise RuntimeError(f"generated file is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--catalog", type=Path, default=Path("data/exhibition_team_catalog.json")
    )
    parser.add_argument("--ef10-dir", type=Path, default=DEFAULT_EF10_DIR)
    parser.add_argument("--pes21-dir", type=Path, default=DEFAULT_PES21_DIR)
    parser.add_argument(
        "--active-rosters", type=Path, default=DEFAULT_ACTIVE_ROSTERS
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    catalog_path = resolve_from_root(root, args.catalog)
    catalog = load_catalog(catalog_path)
    payload = build_cleanup(
        catalog=catalog,
        active_rosters_path=resolve_from_root(root, args.active_rosters),
        ef10_dir=resolve_from_root(root, args.ef10_dir),
        pes21_dir=resolve_from_root(root, args.pes21_dir),
    )
    output_path = resolve_from_root(root, args.output)
    report_path = resolve_from_root(root, args.report)
    outputs = {
        output_path: json.dumps(payload, indent=2, ensure_ascii=True),
        report_path: render_report(payload, catalog),
    }
    for path, content in outputs.items():
        write_or_check(path, content, args.check)
        if not args.check:
            print(f"generated {path}")
    print(
        f"cleanup: {payload['counts']['removed_legacy_memberships']} memberships "
        f"from {payload['counts']['affected_fallback_clubs']} clubs"
    )


if __name__ == "__main__":
    main()
