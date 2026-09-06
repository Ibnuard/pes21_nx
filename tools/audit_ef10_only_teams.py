#!/usr/bin/env python3
"""Inventory EF10 teams whose raw team IDs are absent from PES21.

The audit deliberately stops before runtime integration.  A different raw ID
can still represent the same club (for example, Al Nassr), so every row is
classified as either an alias candidate or a surrogate-required team instead
of being silently added to the selector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from pesdb import (
    decode_wesys,
    parse_category_team_list,
    parse_ef10_assignments,
    parse_player_ids,
    parse_team_records,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EF10_DIR = Path("local-debug/efootball10-audit/tables/common/etc/pesdb")
DEFAULT_PES21_DIR = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_CONFIG = Path("data/exhibition_team_categories.json")
DEFAULT_OUTPUT = Path("data/exhibition_ef10_only_teams.json")
DEFAULT_REPORT = Path("EFOOTBALL10_ONLY_TEAMS.md")

# These are intentionally only review markers, not automatic inclusion rules.
# They keep the generated report useful while alias/surrogate policy is being
# designed for the next runtime phase.
FOCUS_TEAM_IDS = {
    126,      # Borussia Dortmund
    5738,     # Inter Miami (EF10 name: Miami BP)
    18961,    # Al Nassr
    17730,    # Al Rayyan
    17733,    # Al Ahli Saudi
    17873,    # Al Hilal
    17877,    # Buriram United
    17962,    # Sydney FC
    20478,    # Shanghai Port
    20557,    # Al Sadd
    20560,    # Shabab Al Ahli Dubai
    21557,    # Shanghai Shenhua
}


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


def normalize_name(value: str, *, strip_suffixes: bool = False) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", errors="ignore").decode("ascii").upper()
    # Licensed strings sometimes spell the same suffix as ``F.C.`` or ``S.F.C.``.
    # Collapse those punctuation-separated forms before tokenizing so they do
    # not become stray one-letter name tokens.
    value = re.sub(r"\bS\s*\.\s*F\s*\.\s*C\s*\.?(?=\s|$)", "SFC", value)
    value = re.sub(r"\bF\s*\.\s*C\s*\.?(?=\s|$)", "FC", value)
    tokens = re.findall(r"[A-Z0-9]+", value)
    if strip_suffixes:
        suffixes = {
            "AFC",
            "AC",
            "CA",
            "CD",
            "CF",
            "CLUB",
            "FC",
            "FK",
            "SFC",
            "SC",
            "F",
            "C",
        }
        tokens = [token for token in tokens if token not in suffixes]
    return " ".join(tokens)


def load_category_metadata(
    config_path: Path,
    category_rows: dict[int, list[Any]],
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, str]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError(f"{config_path}: unsupported category schema")

    by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)
    source_labels: dict[int, str] = {}
    for category in config.get("categories", []):
        key = str(category["key"])
        label = str(category["label"])
        kind = str(category["kind"])
        for raw_category_id in category.get("source_category_ids", []):
            category_id = int(raw_category_id)
            source_labels[category_id] = label
            for entry in category_rows.get(category_id, []):
                by_team[entry.team_id].append(
                    {
                        "source_category_id": category_id,
                        "category_key": key,
                        "category_label": label,
                        "kind": kind,
                        "order": entry.order,
                    }
                )
        for raw_team_id in category.get("team_ids", []):
            by_team[int(raw_team_id)].append(
                {
                    "source_category_id": None,
                    "category_key": key,
                    "category_label": label,
                    "kind": kind,
                    "order": None,
                }
            )
    for rows in by_team.values():
        rows.sort(
            key=lambda row: (
                row["category_key"],
                row["source_category_id"]
                if row["source_category_id"] is not None
                else -1,
                row["order"] if row["order"] is not None else -1,
            )
        )
    return dict(by_team), source_labels


def classify_kind(rows: list[dict[str, Any]]) -> str:
    kinds = {str(row["kind"]) for row in rows}
    if "club" in kinds:
        return "club"
    if "national" in kinds:
        return "national"
    return "unknown"


def build_inventory(
    *,
    ef10_dir: Path,
    pes21_dir: Path,
    config_path: Path,
) -> dict[str, Any]:
    source_paths = {
        "category_config": config_path,
        "ef10_team": ef10_dir / "Team.bin",
        "ef10_players": ef10_dir / "Player.bin",
        "ef10_assignments": ef10_dir / "PlayerAssignment.bin",
        "ef10_categories": ef10_dir / "CategoryTeamList.bin",
        "pes21_team": pes21_dir / "Team.bin",
        "pes21_players": pes21_dir / "Player.bin",
    }
    missing = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing audit source files: " + ", ".join(missing))

    ef10_teams = parse_team_records(decode_wesys(source_paths["ef10_team"]), "ef10")
    pes21_teams = parse_team_records(
        decode_wesys(source_paths["pes21_team"]), "pes21"
    )
    ef10_player_ids = parse_player_ids(
        decode_wesys(source_paths["ef10_players"]), "ef10"
    )
    pes21_player_ids = parse_player_ids(
        decode_wesys(source_paths["pes21_players"]), "pes21"
    )
    ef10_assignments = parse_ef10_assignments(
        decode_wesys(source_paths["ef10_assignments"])
    )
    unknown_assignment_ids = {
        assignment.player_id
        for roster in ef10_assignments.values()
        for assignment in roster
        if assignment.player_id not in ef10_player_ids
    }
    if unknown_assignment_ids:
        raise RuntimeError(
            "EF10 assignments reference missing players: "
            + ", ".join(map(str, sorted(unknown_assignment_ids)))
        )
    category_rows = parse_category_team_list(
        decode_wesys(source_paths["ef10_categories"])
    )
    category_by_team, source_labels = load_category_metadata(
        config_path, category_rows
    )

    full_name_index: dict[str, list[int]] = defaultdict(list)
    generic_name_index: dict[str, list[int]] = defaultdict(list)
    for team_id, team in pes21_teams.items():
        full_name_index[normalize_name(team.name)].append(team_id)
        generic_name_index[normalize_name(team.name, strip_suffixes=True)].append(
            team_id
        )

    rows: list[dict[str, Any]] = []
    for team_id in sorted(set(ef10_teams) - set(pes21_teams)):
        team = ef10_teams[team_id]
        categories = category_by_team.get(team_id, [])
        kind = classify_kind(categories)
        roster = ef10_assignments.get(team_id, [])
        roster_ids = [assignment.player_id for assignment in roster]
        full_key = normalize_name(team.name)
        generic_key = normalize_name(team.name, strip_suffixes=True)
        full_candidates = sorted(set(full_name_index.get(full_key, [])))
        generic_candidates = sorted(set(generic_name_index.get(generic_key, [])))
        candidates = generic_candidates or full_candidates
        if len(candidates) == 1:
            classification = "alias_candidate"
        elif len(candidates) > 1:
            classification = "alias_review"
        else:
            classification = "surrogate_required"

        candidate_rows = [
            {
                "pes21_team_id": candidate_id,
                "pes21_name": pes21_teams[candidate_id].name,
            }
            for candidate_id in candidates
        ]
        rows.append(
            {
                "ef10_team_id": team_id,
                "ef10_name": team.name,
                "kind": kind,
                "focus": team_id in FOCUS_TEAM_IDS,
                "source_categories": categories,
                "source_category_labels": sorted(
                    {
                        source_labels[row["source_category_id"]]
                        for row in categories
                        if row["source_category_id"] in source_labels
                    }
                ),
                "ef10_roster_count": len(roster_ids),
                "direct_shared_player_count": len(
                    set(roster_ids) & pes21_player_ids
                ),
                "name_keys": {
                    "full": full_key,
                    "generic": generic_key,
                },
                "candidate_pes21_teams": candidate_rows,
                "classification": classification,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/audit_ef10_only_teams.py",
        "policy": {
            "raw_id_gap_is_not_proof_of_missing_team": True,
            "unique_name_aliases_are_review_only": True,
            "no_runtime_integration": True,
        },
        "counts": {
            "ef10_team_records": len(ef10_teams),
            "pes21_team_records": len(pes21_teams),
            "ef10_player_records": len(ef10_player_ids),
            "pes21_player_records": len(pes21_player_ids),
            "ef10_only_raw_ids": len(rows),
            "configured_club_ef10_only": sum(row["kind"] == "club" for row in rows),
            "configured_national_ef10_only": sum(
                row["kind"] == "national" for row in rows
            ),
            "unclassified_ef10_only": sum(
                row["kind"] == "unknown" for row in rows
            ),
            "alias_candidates": sum(
                row["classification"] == "alias_candidate" for row in rows
            ),
            "alias_review": sum(
                row["classification"] == "alias_review" for row in rows
            ),
            "surrogate_required": sum(
                row["classification"] == "surrogate_required" for row in rows
            ),
            "focus_teams": sum(bool(row["focus"]) for row in rows),
        },
        "source_sha256": {
            key: sha256_file(path) for key, path in sorted(source_paths.items())
        },
        "teams": rows,
    }
    payload["content_id"] = content_id(payload)
    return payload


def render_report(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    rows = payload["teams"]
    lines = [
        "# eFootball 10 Teams Missing From PES21 IDs",
        "",
        "This generated audit compares raw `Team.bin` IDs. A missing raw ID does",
        "not automatically mean a missing club: some teams were re-numbered or",
        "renamed between versions. Alias candidates therefore remain review-only.",
        "No runtime selector or database files are changed by this audit.",
        "",
        "## Counts",
        "",
        f"- Audit content ID: `{payload['content_id']}`",
        f"- EF10 team records: {counts['ef10_team_records']}",
        f"- PES21 team records: {counts['pes21_team_records']}",
        f"- EF10 player records: {counts['ef10_player_records']}",
        f"- PES21 player records: {counts['pes21_player_records']}",
        f"- EF10-only raw IDs: {counts['ef10_only_raw_ids']}",
        f"- Configured club IDs: {counts['configured_club_ef10_only']}",
        f"- Configured national IDs: {counts['configured_national_ef10_only']}",
        f"- Unclassified IDs: {counts['unclassified_ef10_only']}",
        f"- Alias candidates: {counts['alias_candidates']}",
        f"- Alias review rows: {counts['alias_review']}",
        f"- Surrogate-required rows: {counts['surrogate_required']}",
        "",
        "## Focus teams",
        "",
        "| EF10 ID | EF10 name | Kind | Roster | Shared players | Classification | PES21 candidate |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    focus_rows = [row for row in rows if row["focus"]]
    for row in focus_rows:
        candidates = row["candidate_pes21_teams"]
        candidate_text = ", ".join(
            f"`{candidate['pes21_team_id']}` {candidate['pes21_name']}"
            for candidate in candidates
        ) or "-"
        lines.append(
            f"| {row['ef10_team_id']} | {row['ef10_name']} | {row['kind']} | "
            f"{row['ef10_roster_count']} | {row['direct_shared_player_count']} | "
            f"{row['classification']} | {candidate_text} |"
        )

    lines.extend(
        [
            "",
            "## Surrogate-required clubs by source category",
            "",
            "Counts below are category memberships; a team can appear in more than one",
            "source category (notably `WORLD / EDIT CLUBS`).",
            "",
            "| Category | Teams |",
            "|---|---:|",
        ]
    )
    category_counts: Counter[str] = Counter()
    for row in rows:
        if row["kind"] != "club" or row["classification"] != "surrogate_required":
            continue
        labels = row["source_category_labels"] or ["UNCLASSIFIED"]
        for label in labels:
            category_counts[label] += 1
    for label, count in sorted(category_counts.items()):
        lines.append(f"| {label} | {count} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `alias_candidate`: one PES21 team has the same normalized club name;",
            "  confirm the mapping before using its native team slot.",
            "- `alias_review`: multiple PES21 teams share the normalized name;",
            "  requires an explicit mapping decision.",
            "- `surrogate_required`: no normalized PES21 name candidate exists;",
            "  a donor team slot and player conversion plan are required.",
            "",
        ]
    )
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
    parser.add_argument("--ef10-dir", type=Path, default=DEFAULT_EF10_DIR)
    parser.add_argument("--pes21-dir", type=Path, default=DEFAULT_PES21_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    payload = build_inventory(
        ef10_dir=resolve_from_root(root, args.ef10_dir),
        pes21_dir=resolve_from_root(root, args.pes21_dir),
        config_path=resolve_from_root(root, args.config),
    )
    outputs = {
        resolve_from_root(root, args.output): json.dumps(
            payload, indent=2, ensure_ascii=True
        ),
        resolve_from_root(root, args.report): render_report(payload),
    }
    for path, content in outputs.items():
        write_or_check(path, content, args.check)
        if not args.check:
            print(f"generated {path}")
    print(
        f"ef10-only: {payload['counts']['ef10_only_raw_ids']} IDs; "
        f"{payload['counts']['alias_candidates']} alias candidates; "
        f"{payload['counts']['surrogate_required']} surrogate-required"
    )


if __name__ == "__main__":
    main()
