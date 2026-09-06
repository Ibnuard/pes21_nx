#!/usr/bin/env python3
"""Generate the safe cross-version Exhibition team catalog and native rosters."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pesdb import (
    PlayerAssignment,
    decode_wesys,
    parse_category_team_list,
    parse_ef10_assignments,
    parse_player_ids,
    parse_pes21_assignments,
    parse_tactics_team_ids,
    parse_team_records,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EF10_DIR = Path("local-debug/efootball10-audit/tables/common/etc/pesdb")
DEFAULT_PES21_DIR = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_EF10_TACTICS_DIR = Path(
    "local-debug/efootball10-audit/compare/new_dt200_mobile_all.cpk/common/etc/pesdb"
)
DEFAULT_SYMBOL_ROOT = Path("local-debug/cpk-emblem-check/common/render/symbol")


def resolve_from_root(root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ascii_display_name(value: str) -> str:
    replacements = {
        "ß": "ss",
        "Ø": "O",
        "ø": "o",
        "Đ": "D",
        "đ": "d",
        "Ł": "L",
        "ł": "l",
    }
    value = "".join(replacements.get(character, character) for character in value)
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", errors="ignore").decode("ascii")
    value = re.sub(r"\s+", " ", value).strip().upper()
    if not value:
        raise ValueError("team display name becomes empty after ASCII transliteration")
    return value


def team_symbol(team_id: int, display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip("_")
    return f"team_{team_id}_{slug}"[:79].rstrip("_")


def find_team_badge(symbol_root: Path, team_id: int) -> Path | None:
    flag_root = symbol_root / "flag"
    candidates = (
        flag_root / f"e_{team_id:06d}_r_l.png",
        flag_root / f"e_{team_id:06d}_r.png",
        flag_root / f"e_{team_id:06d}_r_b.png",
        flag_root / f"e_{team_id:06d}_f_l.png",
        flag_root / f"e_{team_id:06d}_f.png",
        flag_root / f"e_{team_id:06d}_r_w.png",
        flag_root / f"flag_{team_id}.png",
    )
    return next((path for path in candidates if path.is_file()), None)


def find_category_badge(symbol_root: Path, relative_path: str) -> Path | None:
    source = symbol_root / relative_path
    large = source.with_name(f"{source.stem}_l{source.suffix}")
    return next((path for path in (large, source) if path.is_file()), None)


def wrapped_uints(values: list[int], suffix: str, per_line: int = 8) -> str:
    return "\n".join(
        "    " + ", ".join(f"{value}{suffix}" for value in values[offset : offset + per_line]) + ","
        for offset in range(0, len(values), per_line)
    )


def c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def roster_player_count(roster: list[PlayerAssignment]) -> int:
    return len({assignment.player_id for assignment in roster if assignment.player_id})


def build_catalog(args: argparse.Namespace) -> tuple[dict[str, Any], dict[int, list[PlayerAssignment]]]:
    root = args.root.resolve()
    config_path = resolve_from_root(root, args.config)
    ef10_dir = resolve_from_root(root, args.ef10_dir)
    pes21_dir = resolve_from_root(root, args.pes21_dir)
    ef10_tactics_dir = resolve_from_root(root, args.ef10_tactics_dir)
    symbol_root = resolve_from_root(root, args.symbol_root)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError(f"{config_path}: unsupported category schema")

    source_paths = {
        "ef10_team": ef10_dir / "Team.bin",
        "ef10_players": ef10_dir / "Player.bin",
        "ef10_assignments": ef10_dir / "PlayerAssignment.bin",
        "ef10_categories": ef10_dir / "CategoryTeamList.bin",
        "ef10_tactics": ef10_tactics_dir / "Tactics.bin",
        "pes21_team": pes21_dir / "Team.bin",
        "pes21_players": pes21_dir / "Player.bin",
        "pes21_assignments": pes21_dir / "PlayerAssignment.bin",
        "pes21_tactics": pes21_dir / "Tactics.bin",
    }
    missing_sources = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing_sources:
        raise FileNotFoundError("missing catalog source files: " + ", ".join(missing_sources))
    if not symbol_root.is_dir():
        raise FileNotFoundError(f"missing extracted badge tree: {symbol_root}")

    ef10_teams = parse_team_records(decode_wesys(source_paths["ef10_team"]), "ef10")
    pes21_teams = parse_team_records(decode_wesys(source_paths["pes21_team"]), "pes21")
    ef10_player_ids = parse_player_ids(
        decode_wesys(source_paths["ef10_players"]), "ef10"
    )
    pes21_player_ids = parse_player_ids(
        decode_wesys(source_paths["pes21_players"]), "pes21"
    )
    ef10_rosters = parse_ef10_assignments(decode_wesys(source_paths["ef10_assignments"]))
    pes21_rosters = parse_pes21_assignments(decode_wesys(source_paths["pes21_assignments"]))
    source_categories = parse_category_team_list(
        decode_wesys(source_paths["ef10_categories"])
    )
    ef10_tactics = parse_tactics_team_ids(
        decode_wesys(source_paths["ef10_tactics"]), "ef10"
    )
    pes21_tactics = parse_tactics_team_ids(
        decode_wesys(source_paths["pes21_tactics"]), "pes21"
    )

    minimum_players = int(config["minimum_players"])
    maximum_players = int(config["maximum_players"])
    common_team_ids = set(ef10_teams) & set(pes21_teams)
    common_assignment_ids = set(ef10_rosters) & set(pes21_rosters)
    safe_team_ids: set[int] = set()
    rejected: dict[int, list[str]] = {}
    for team_id in sorted(common_team_ids):
        reasons: list[str] = []
        ef10_count = roster_player_count(ef10_rosters.get(team_id, []))
        pes21_count = roster_player_count(pes21_rosters.get(team_id, []))
        if team_id not in common_assignment_ids:
            reasons.append("missing roster in one version")
        if ef10_count < minimum_players:
            reasons.append(f"EF10 roster has {ef10_count} players")
        if pes21_count < minimum_players:
            reasons.append(f"PES21 roster has {pes21_count} players")
        if pes21_count > maximum_players:
            reasons.append(f"PES21 roster exceeds {maximum_players} players")
        missing_ef10_players = {
            assignment.player_id
            for assignment in ef10_rosters.get(team_id, [])
            if assignment.player_id not in ef10_player_ids
        }
        missing_pes21_players = {
            assignment.player_id
            for assignment in pes21_rosters.get(team_id, [])
            if assignment.player_id not in pes21_player_ids
        }
        if missing_ef10_players:
            reasons.append(
                f"EF10 roster references {len(missing_ef10_players)} missing players"
            )
        if missing_pes21_players:
            reasons.append(
                f"PES21 roster references {len(missing_pes21_players)} missing players"
            )
        if team_id not in ef10_tactics:
            reasons.append("missing EF10 tactics")
        if team_id not in pes21_tactics:
            reasons.append("missing PES21 tactics")
        badge = find_team_badge(symbol_root, team_id)
        if badge is None:
            reasons.append("missing native PES21 badge")
        if reasons:
            rejected[team_id] = reasons
        else:
            safe_team_ids.add(team_id)

    expected_safe_count = int(config["expected_safe_team_count"])
    if len(safe_team_ids) != expected_safe_count:
        raise RuntimeError(
            f"safe team count changed: {len(safe_team_ids)} != {expected_safe_count}"
        )

    legacy_team_ids = {int(team_id) for team_id in config["legacy_team_ids"]}
    for team_id in sorted(legacy_team_ids):
        if team_id in safe_team_ids:
            raise ValueError(f"legacy team {team_id} is already safe/generated")
        if team_id not in pes21_teams:
            raise ValueError(f"legacy team {team_id} is absent from PES21 Team.bin")
        if team_id not in pes21_tactics:
            raise ValueError(f"legacy team {team_id} has no PES21 tactics")
        if find_team_badge(symbol_root, team_id) is None:
            raise ValueError(f"legacy team {team_id} has no native PES21 badge")

    all_team_ids = safe_team_ids | legacy_team_ids
    assigned: set[int] = set()
    generated_categories: list[dict[str, Any]] = []
    category_keys: set[str] = set()
    team_category: dict[int, tuple[str, str, int, int]] = {}
    for category_config in config["categories"]:
        category_key = str(category_config["key"])
        if not re.fullmatch(r"[a-z][a-z0-9_]*", category_key):
            raise ValueError(f"invalid category key: {category_key}")
        if category_key in category_keys:
            raise ValueError(f"duplicate category key: {category_key}")
        category_keys.add(category_key)
        category_badge = find_category_badge(
            symbol_root, str(category_config["badge_source"])
        )
        if category_badge is None:
            raise ValueError(
                f"category {category_key} has no badge source: "
                f"{category_config['badge_source']}"
            )
        candidates: list[int] = []
        for source_category_id in category_config.get("source_category_ids", []):
            candidates.extend(
                entry.team_id
                for entry in source_categories.get(int(source_category_id), [])
            )
        candidates.extend(int(team_id) for team_id in category_config.get("team_ids", []))

        category_team_ids: list[int] = []
        seen_candidates: set[int] = set()
        for team_id in candidates:
            if team_id in seen_candidates:
                continue
            seen_candidates.add(team_id)
            if team_id not in all_team_ids or team_id in assigned:
                continue
            category_team_ids.append(team_id)
            assigned.add(team_id)

        if not category_team_ids and category_config.get("omit_if_empty", False):
            continue
        if not category_team_ids:
            raise ValueError(f"category {category_key} resolved to no teams")

        category_index = len(generated_categories)
        category = {
            "key": category_key,
            "label": ascii_display_name(str(category_config["label"])),
            "icon": ascii_display_name(str(category_config["icon"])),
            "kind": str(category_config["kind"]),
            "badge_source": category_badge.relative_to(symbol_root).as_posix(),
            "source_category_ids": [
                int(value) for value in category_config.get("source_category_ids", [])
            ],
            "team_ids": category_team_ids,
        }
        generated_categories.append(category)
        for position, team_id in enumerate(category_team_ids):
            team_category[team_id] = (
                category["key"],
                category["kind"],
                category_index,
                position,
            )

    unassigned = sorted(all_team_ids - assigned)
    if unassigned:
        raise RuntimeError(f"catalog categories did not claim team IDs: {unassigned}")

    sorted_team_ids = sorted(all_team_ids)
    badge_slots = {team_id: slot for slot, team_id in enumerate(sorted_team_ids, 1)}
    first_category_slot = len(sorted_team_ids) + 1
    for index, category in enumerate(generated_categories):
        category["badge_slot"] = first_category_slot + index

    teams: list[dict[str, Any]] = []
    for team_id in sorted_team_ids:
        is_safe = team_id in safe_team_ids
        source_record = ef10_teams[team_id] if is_safe else pes21_teams[team_id]
        display_name = ascii_display_name(source_record.name)
        category_key, kind, category_index, category_position = team_category[team_id]
        badge_path = find_team_badge(symbol_root, team_id)
        assert badge_path is not None
        teams.append(
            {
                "team_id": team_id,
                "symbol": team_symbol(team_id, display_name),
                "display_name": display_name,
                "source_name": source_record.name,
                "name_source": "ef10" if is_safe else "pes21_legacy",
                "kind": kind,
                "category": category_key,
                "category_index": category_index,
                "category_position": category_position,
                "badge_slot": badge_slots[team_id],
                "badge_source": badge_path.relative_to(symbol_root).as_posix(),
                "roster_source": "pes21_native" if is_safe else "legacy_manual",
                "conversion_eligible": is_safe,
                "ef10_player_count": roster_player_count(ef10_rosters.get(team_id, [])),
                "pes21_player_count": roster_player_count(pes21_rosters.get(team_id, [])),
                "has_ef10_tactics": team_id in ef10_tactics,
                "has_pes21_tactics": team_id in pes21_tactics,
            }
        )

    catalog: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/generate_exhibition_team_catalog.py",
        "policy": {
            "minimum_players": minimum_players,
            "maximum_players": maximum_players,
            "roster_priority": ["ef10_converted", "pes21_native", "legacy_manual"],
        },
        "counts": {
            "ef10_team_records": len(ef10_teams),
            "pes21_team_records": len(pes21_teams),
            "ef10_player_records": len(ef10_player_ids),
            "pes21_player_records": len(pes21_player_ids),
            "shared_team_ids": len(common_team_ids),
            "safe_shared_teams": len(safe_team_ids),
            "legacy_teams": len(legacy_team_ids),
            "selector_teams": len(all_team_ids),
            "categories": len(generated_categories),
            "badge_slots": len(all_team_ids) + len(generated_categories) + 1,
        },
        "source_sha256": {
            key: sha256_file(path) for key, path in sorted(source_paths.items())
        },
        "categories": generated_categories,
        "teams": teams,
        "rejected_shared_team_ids": {
            str(team_id): reasons for team_id, reasons in sorted(rejected.items())
        },
    }
    canonical = json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
    catalog["content_id"] = hashlib.sha256(canonical).hexdigest()[:16]
    return catalog, {team_id: pes21_rosters[team_id] for team_id in safe_team_ids}


def render_team_include(catalog: dict[str, Any]) -> str:
    lines = [
        "// Generated by tools/generate_exhibition_team_catalog.py.",
        f"// Catalog content ID: {catalog['content_id']}",
        "// Do not edit manually.",
        "",
    ]
    for category in catalog["categories"]:
        key = category["key"]
        lines.extend(
            [
                f"static const uint32_t exhibition_category_{key}_teams[] = {{",
                wrapped_uints(category["team_ids"], "u"),
                "};",
                "",
            ]
        )

    lines.append("static const ExhibitionTeamCategory exhibition_team_categories[] = {")
    for category in catalog["categories"]:
        key = category["key"]
        lines.extend(
            [
                "    {",
                f'        "{c_string(category["label"])}",',
                f'        "{c_string(category["icon"])}",',
                f"        exhibition_category_{key}_teams,",
                f"        (uint32_t)(sizeof(exhibition_category_{key}_teams) /",
                f"                   sizeof(exhibition_category_{key}_teams[0])),",
                f"        {category['badge_slot']}u,",
                "    },",
            ]
        )
    lines.extend(["};", ""])

    lines.append("static const ExhibitionTeamCatalogEntry exhibition_team_catalog[] = {")
    for team in catalog["teams"]:
        lines.append(
            f'    {{{team["team_id"]}u, "{c_string(team["display_name"])}", '
            f'{team["badge_slot"]}u}},'
        )
    lines.extend(["};", ""])
    return "\n".join(lines)


def render_roster_include(
    catalog: dict[str, Any], rosters: dict[int, list[PlayerAssignment]]
) -> str:
    player_ids: list[int] = []
    shirts: list[int] = []
    entries: list[tuple[int, int, int]] = []
    for team_id in sorted(rosters):
        roster = rosters[team_id]
        offset = len(player_ids)
        player_ids.extend(assignment.player_id for assignment in roster)
        shirts.extend(assignment.shirt for assignment in roster)
        entries.append((team_id, offset, len(roster)))

    lines = [
        "// Generated by tools/generate_exhibition_team_catalog.py.",
        f"// Catalog content ID: {catalog['content_id']}",
        "// Native PES21 fallback rosters for every safe shared team.",
        "// Do not edit manually.",
        "",
        "static const uint32_t exhibition_pes21_player_ids[] = {",
        wrapped_uints(player_ids, "u"),
        "};",
        "",
        "static const uint8_t exhibition_pes21_shirt_numbers[] = {",
        wrapped_uints(shirts, ""),
        "};",
        "",
        "static const ExhibitionMasterRoster exhibition_pes21_master_rosters[] = {",
    ]
    for team_id, offset, count in entries:
        lines.append(
            "    {"
            f"{team_id}u, exhibition_pes21_player_ids + {offset}u, "
            f"exhibition_pes21_shirt_numbers + {offset}u, {count}u"
            "},"
        )
    lines.extend(["};", ""])
    return "\n".join(lines)


def render_report(catalog: dict[str, Any], ef10_dir: Path) -> str:
    team_by_id = {int(team["team_id"]): team for team in catalog["teams"]}
    lines = [
        "# Exhibition Team Catalog",
        "",
        "This generated catalog is the source of truth for the custom team selector,",
        "team names, compact badge slots, and native PES21 fallback rosters.",
        "",
        "## Safety gate",
        "",
        f"- Catalog content ID: `{catalog['content_id']}`",
        f"- EF10 Team.bin records: {catalog['counts']['ef10_team_records']}",
        f"- PES21 Team.bin records: {catalog['counts']['pes21_team_records']}",
        f"- EF10 Player.bin records: {catalog['counts']['ef10_player_records']}",
        f"- PES21 Player.bin records: {catalog['counts']['pes21_player_records']}",
        f"- Team IDs present in both: {catalog['counts']['shared_team_ids']}",
        f"- Safe shared teams with complete rosters/tactics/badges: {catalog['counts']['safe_shared_teams']}",
        f"- Retained legacy-only selector teams: {catalog['counts']['legacy_teams']}",
        f"- Final selector teams: {catalog['counts']['selector_teams']}",
        f"- Compact atlas slots, including slot 0 and category emblems: {catalog['counts']['badge_slots']}",
        "",
        "Phase one deliberately uses the native PES21 roster for newly exposed teams.",
        "An existing converted EF10 roster wins when present; legacy manual rosters are",
        "only the final fallback. Full EF10 player conversion and duplicate-name cleanup",
        "remain separate later phases.",
        "",
        "## Generated runtime data",
        "",
        "- `data/exhibition_team_catalog.json`: canonical team/category manifest",
        "- `source/exhibition_teams_generated.inc`: selector order, names, and badge slots",
        "- `source/exhibition_rosters_pes21_generated.inc`: native PES21 fallback rosters",
        "- `source/badge_atlas.h`: compact atlas metadata and runtime symbol declaration",
        "- `data/badge_atlas.bin`: raw RGBA team/category badge atlas",
        "",
        "Team IDs are never used as atlas indexes. Compact slots are regenerated from",
        "the manifest, so high native IDs do not allocate sparse texture space.",
        "",
        "## Categories",
        "",
        "| Category | Shared | Legacy | Total |",
        "|---|---:|---:|---:|",
    ]
    for category in catalog["categories"]:
        category_teams = [team_by_id[int(team_id)] for team_id in category["team_ids"]]
        shared = sum(team["roster_source"] == "pes21_native" for team in category_teams)
        legacy = len(category_teams) - shared
        lines.append(f"| {category['label']} | {shared} | {legacy} | {len(category_teams)} |")

    lines.extend(
        [
            "",
            "## Top-flight source exclusions",
            "",
            "These EF10 league members were not admitted because the same team ID does",
            "not pass the cross-version safety gate.",
            "",
        ]
    )
    safe_ids = {
        int(team["team_id"])
        for team in catalog["teams"]
        if team["roster_source"] == "pes21_native"
    }
    legacy_ids = {
        int(team["team_id"])
        for team in catalog["teams"]
        if team["roster_source"] == "legacy_manual"
    }
    ef10_teams = parse_team_records(decode_wesys(ef10_dir / "Team.bin"), "ef10")
    source_categories = parse_category_team_list(
        decode_wesys(ef10_dir / "CategoryTeamList.bin")
    )
    top_flight = {
        113: "English League",
        119: "Spanish League",
        122: "Ligue 1",
        116: "Serie A",
        125: "Eredivisie",
        128: "Liga Portugal",
    }
    found_exclusion = False
    for category_id, label in top_flight.items():
        excluded = [
            entry.team_id
            for entry in source_categories.get(category_id, [])
            if entry.team_id not in safe_ids and entry.team_id not in legacy_ids
        ]
        if not excluded:
            continue
        found_exclusion = True
        values = ", ".join(
            f"{team_id} ({ascii_display_name(ef10_teams[team_id].name)})"
            for team_id in excluded
        )
        lines.append(f"- {label}: {values}")
    if not found_exclusion:
        lines.append("- None")
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
    parser.add_argument("--config", type=Path, default=Path("data/exhibition_team_categories.json"))
    parser.add_argument("--ef10-dir", type=Path, default=DEFAULT_EF10_DIR)
    parser.add_argument("--pes21-dir", type=Path, default=DEFAULT_PES21_DIR)
    parser.add_argument("--ef10-tactics-dir", type=Path, default=DEFAULT_EF10_TACTICS_DIR)
    parser.add_argument("--symbol-root", type=Path, default=DEFAULT_SYMBOL_ROOT)
    parser.add_argument(
        "--manifest-output", type=Path, default=Path("data/exhibition_team_catalog.json")
    )
    parser.add_argument(
        "--teams-output", type=Path, default=Path("source/exhibition_teams_generated.inc")
    )
    parser.add_argument(
        "--rosters-output",
        type=Path,
        default=Path("source/exhibition_rosters_pes21_generated.inc"),
    )
    parser.add_argument(
        "--report-output", type=Path, default=Path("EXHIBITION_TEAM_CATALOG.md")
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    catalog, rosters = build_catalog(args)
    root = args.root.resolve()
    outputs = {
        resolve_from_root(root, args.manifest_output): json.dumps(
            catalog, indent=2, ensure_ascii=True
        ),
        resolve_from_root(root, args.teams_output): render_team_include(catalog),
        resolve_from_root(root, args.rosters_output): render_roster_include(catalog, rosters),
        resolve_from_root(root, args.report_output): render_report(
            catalog, resolve_from_root(root, args.ef10_dir)
        ),
    }
    for path, content in outputs.items():
        write_or_check(path, content, args.check)
        if not args.check:
            print(f"generated {path}")
    print(
        f"catalog: {catalog['counts']['safe_shared_teams']} shared + "
        f"{catalog['counts']['legacy_teams']} legacy = "
        f"{catalog['counts']['selector_teams']} teams"
    )


if __name__ == "__main__":
    main()
