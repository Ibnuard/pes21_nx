#!/usr/bin/env python3
"""Build and export the local PES21 NX master-data catalog.

The committed JSON registries remain the stable public identity contract.  A
local SQLite database joins those registries with the locked EF26 snapshot,
formation hints, generated lineups, player assets, and kit migration report.
Full source stats and local asset paths never need to be committed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data/pes21_player_registry.json"
DEFAULT_CATALOG = ROOT / "data/exhibition_team_catalog_migration.json"
DEFAULT_SNAPSHOT = (
    ROOT / "local-inputs/pes21-player-migration/eF26_v551/active-snapshot.json"
)
DEFAULT_TACTICS = (
    ROOT / "local-inputs/pes21-player-migration/eF26_v551/team-tactics-full.json"
)
DEFAULT_MIGRATION_MANIFEST = (
    ROOT / "local-debug/pes21-player-migration-full-v1/full-migration-manifest.json"
)
DEFAULT_PORTRAITS = (
    ROOT / "local-debug/pes21-player-migration-full-v1/portrait-report.json"
)
DEFAULT_KITS = (
    ROOT / "local-debug/full-mobile-kit-migration-v1/full-kit-migration-report.json"
)
DEFAULT_DATABASE = ROOT / "local-inputs/master-data/pes21_master.db"
DEFAULT_EXPORT = ROOT / "local-debug/master-exports"
DEFAULT_PUBLIC = ROOT / "data/master"
DEFAULT_DOCUMENT = ROOT / "docs/MASTER_DATA_CATALOG.md"

POSITION_NAMES = {
    0: "GK", 1: "CB", 2: "LB", 3: "RB", 4: "DMF", 5: "CMF",
    6: "LMF", 7: "RMF", 8: "AMF", 9: "LWF", 10: "RWF",
    11: "SS", 12: "CF",
}

TABLE_DESCRIPTIONS = {
    "metadata": "Snapshot versions, content IDs, source paths, and hashes.",
    "competitions": "Selector leagues/categories and their licensed labels.",
    "teams": "Logical EF team IDs and native PES21 physical slots.",
    "excluded_teams": "Teams deliberately excluded from the playable scope.",
    "ef_player_catalog": "Every EF26 BaseId in the locked 24,174-player index.",
    "players": "Materialized canonical players and stable native identities.",
    "player_stats": "Full canonical/highest-OVR EF data, one wide row per player.",
    "player_aliases": "Identity aliases retained by the resolver.",
    "team_rosters": "Club/national memberships, shirt numbers, and order.",
    "formation_slots": "Locked API formation roles and pitch coordinates.",
    "starting_lineups": "Final formation-aware selected eleven for each team.",
    "player_assets": "Portrait, face, and commentary ownership/status.",
    "team_kits": "Per-team migration or preservation state.",
    "kit_variants": "Converted home, away, and goalkeeper kit provenance.",
    "source_artifacts": "Input files and hashes used to build this database.",
    "field_dictionary": "Mapping from EF source field names to SQL columns.",
}


def load_json(path: Path, *, required: bool = True) -> dict[str, Any] | None:
    if not path.is_file():
        if required:
            raise FileNotFoundError(path)
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_csv(path: Path, columns: list[str], rows: Iterable[Iterable[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)
    os.replace(temporary, path)


def sql_name(source: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", source)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "value"


def sql_type(values: Iterable[Any]) -> str:
    types = {type(value) for value in values if value is not None}
    if not types or types <= {bool, int}:
        return "INTEGER"
    if types <= {bool, int, float}:
        return "REAL"
    return "TEXT"


def sqlite_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return canonical_json(value)
    return value


def optional_path(value: Path) -> Path | None:
    return value.resolve() if value.is_file() else None


def load_sources(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "player_registry": args.registry.resolve(),
        "team_catalog": args.catalog.resolve(),
        "active_snapshot": args.snapshot.resolve(),
        "team_tactics": optional_path(args.tactics),
        "migration_manifest": optional_path(args.migration_manifest),
        "portrait_report": optional_path(args.portraits),
        "kit_report": optional_path(args.kits),
    }
    sources = {
        "paths": paths,
        "registry": load_json(paths["player_registry"]),
        "catalog": load_json(paths["team_catalog"]),
        "snapshot": load_json(paths["active_snapshot"]),
        "tactics": load_json(paths["team_tactics"], required=False)
        if paths["team_tactics"] else None,
        "manifest": load_json(paths["migration_manifest"], required=False)
        if paths["migration_manifest"] else None,
        "portraits": load_json(paths["portrait_report"], required=False)
        if paths["portrait_report"] else None,
        "kits": load_json(paths["kit_report"], required=False)
        if paths["kit_report"] else None,
    }
    validate_source_identity(sources)
    return sources


def validate_source_identity(sources: dict[str, Any]) -> None:
    registry = sources["registry"]
    catalog = sources["catalog"]
    snapshot = sources["snapshot"]
    source_versions = {
        str(value) for value in (
            registry.get("source_version"), catalog.get("source_version"),
            snapshot.get("source_version"),
        ) if value
    }
    build_ids = {
        str(value) for value in (
            registry.get("migration_build_id"),
            catalog.get("migration_build_id"),
            snapshot.get("migration_build_id"),
            (sources["manifest"] or {}).get("migration_build_id"),
        ) if value
    }
    snapshot_ids = {
        str(value) for value in (
            registry.get("snapshot_content_id"),
            catalog.get("snapshot_content_id"), snapshot.get("content_id"),
        ) if value
    }
    if len(source_versions) != 1:
        raise ValueError(f"source version mismatch: {sorted(source_versions)}")
    if len(build_ids) != 1:
        raise ValueError(f"migration build mismatch: {sorted(build_ids)}")
    if len(snapshot_ids) != 1:
        raise ValueError(f"snapshot content mismatch: {sorted(snapshot_ids)}")


def create_schema(connection: sqlite3.Connection,
                  stat_fields: list[tuple[str, str, str]]) -> None:
    connection.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE competitions (
            category_key TEXT PRIMARY KEY,
            catalog_label TEXT NOT NULL,
            display_label TEXT NOT NULL,
            icon TEXT,
            kind TEXT NOT NULL,
            badge_slot INTEGER NOT NULL,
            badge_source TEXT,
            source_category_ids_json TEXT NOT NULL,
            team_count INTEGER NOT NULL
        );
        CREATE TABLE teams (
            team_id INTEGER PRIMARY KEY,
            physical_team_id INTEGER NOT NULL,
            display_name TEXT NOT NULL,
            source_name TEXT,
            kind TEXT NOT NULL,
            category_key TEXT NOT NULL REFERENCES competitions(category_key),
            category_position INTEGER NOT NULL,
            badge_slot INTEGER NOT NULL,
            badge_source TEXT,
            name_source TEXT,
            roster_source TEXT,
            player_count INTEGER NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE excluded_teams (
            team_id INTEGER PRIMARY KEY,
            physical_team_id INTEGER,
            display_name TEXT,
            source_name TEXT,
            kind TEXT,
            player_count INTEGER,
            status TEXT,
            reason TEXT
        );
        CREATE TABLE ef_player_catalog (
            base_id INTEGER PRIMARY KEY,
            source_card_id INTEGER NOT NULL,
            stats_source_card_id INTEGER NOT NULL,
            stats_overall INTEGER,
            fingerprint TEXT,
            active INTEGER NOT NULL CHECK(active IN (0, 1))
        );
        CREATE TABLE players (
            base_id INTEGER PRIMARY KEY,
            native_player_id INTEGER NOT NULL UNIQUE,
            physical_source_id INTEGER NOT NULL UNIQUE,
            canonical_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            status TEXT NOT NULL,
            allocation TEXT NOT NULL,
            source_card_id INTEGER NOT NULL,
            stats_source_card_id INTEGER NOT NULL,
            overall INTEGER,
            primary_position INTEGER,
            primary_position_name TEXT,
            country_id INTEGER,
            age INTEGER,
            height INTEGER,
            weight INTEGER,
            fingerprint TEXT NOT NULL,
            source_data_hash TEXT NOT NULL,
            team_ids_json TEXT NOT NULL
        );
        CREATE TABLE player_aliases (
            base_id INTEGER NOT NULL REFERENCES players(base_id),
            alias TEXT NOT NULL,
            alias_json TEXT NOT NULL,
            PRIMARY KEY(base_id, alias)
        );
        CREATE TABLE team_rosters (
            team_id INTEGER NOT NULL REFERENCES teams(team_id),
            base_id INTEGER NOT NULL REFERENCES players(base_id),
            native_player_id INTEGER NOT NULL,
            source_card_id INTEGER NOT NULL,
            position_order INTEGER NOT NULL,
            shirt_number INTEGER NOT NULL,
            captain INTEGER NOT NULL CHECK(captain IN (0, 1)),
            PRIMARY KEY(team_id, base_id),
            UNIQUE(team_id, position_order)
        );
        CREATE TABLE formation_slots (
            team_id INTEGER NOT NULL REFERENCES teams(team_id),
            strategy INTEGER NOT NULL,
            slot INTEGER NOT NULL,
            role INTEGER NOT NULL,
            role_name TEXT,
            depth INTEGER NOT NULL,
            width INTEGER NOT NULL,
            preferred_base_id INTEGER,
            preferred_name TEXT,
            source_url TEXT,
            source_sha256 TEXT,
            PRIMARY KEY(team_id, strategy, slot)
        );
        CREATE TABLE starting_lineups (
            team_id INTEGER NOT NULL REFERENCES teams(team_id),
            slot INTEGER NOT NULL,
            base_id INTEGER NOT NULL REFERENCES players(base_id),
            native_player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            role INTEGER NOT NULL,
            role_name TEXT,
            depth INTEGER NOT NULL,
            width INTEGER NOT NULL,
            overall INTEGER,
            source_position INTEGER,
            source_position_name TEXT,
            preferred_base_id INTEGER,
            preferred_missing INTEGER NOT NULL CHECK(preferred_missing IN (0, 1)),
            formation_adapted INTEGER NOT NULL CHECK(formation_adapted IN (0, 1)),
            tactics_hint_sha256 TEXT,
            PRIMARY KEY(team_id, slot)
        );
        CREATE TABLE player_assets (
            base_id INTEGER PRIMARY KEY REFERENCES players(base_id),
            native_player_id INTEGER NOT NULL,
            portrait_asset_id INTEGER,
            portrait_source_card_id INTEGER,
            portrait_status TEXT NOT NULL,
            portrait_sha256 TEXT,
            face_owner_id INTEGER,
            commentary_owner_id INTEGER,
            face_policy TEXT NOT NULL,
            commentary_policy TEXT NOT NULL
        );
        CREATE TABLE team_kits (
            team_id INTEGER PRIMARY KEY REFERENCES teams(team_id),
            physical_team_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            available_kits_json TEXT NOT NULL,
            reason TEXT,
            preview_count INTEGER NOT NULL
        );
        CREATE TABLE kit_variants (
            team_id INTEGER NOT NULL REFERENCES teams(team_id),
            kind TEXT NOT NULL,
            suffix TEXT NOT NULL,
            descriptor_target TEXT,
            descriptor_source_archive TEXT,
            body_target_member TEXT,
            body_sha256 TEXT,
            back_target_member TEXT,
            back_sha256 TEXT,
            preview_members_json TEXT NOT NULL,
            PRIMARY KEY(team_id, kind)
        );
        CREATE TABLE source_artifacts (
            artifact_key TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            required INTEGER NOT NULL CHECK(required IN (0, 1))
        );
        CREATE TABLE field_dictionary (
            source_field TEXT PRIMARY KEY,
            sql_column TEXT NOT NULL UNIQUE,
            sql_type TEXT NOT NULL,
            scope TEXT NOT NULL
        );
    """)
    columns = ["base_id INTEGER PRIMARY KEY REFERENCES players(base_id)"]
    columns.extend(f'"{column}" {kind}' for _source, column, kind in stat_fields)
    connection.execute(f"CREATE TABLE player_stats ({', '.join(columns)})")
    connection.executescript("""
        CREATE INDEX idx_players_name ON players(normalized_name);
        CREATE INDEX idx_players_face ON player_assets(face_owner_id);
        CREATE INDEX idx_players_commentary ON player_assets(commentary_owner_id);
        CREATE INDEX idx_rosters_player ON team_rosters(base_id);
        CREATE INDEX idx_teams_category ON teams(category_key, category_position);
        CREATE INDEX idx_lineups_player ON starting_lineups(base_id);
        CREATE VIEW v_team_rosters AS
            SELECT t.team_id, t.display_name AS team_name, r.position_order,
                   r.shirt_number, r.captain, p.base_id, p.native_player_id,
                   p.canonical_name, p.overall, p.primary_position_name
            FROM team_rosters r
            JOIN teams t ON t.team_id = r.team_id
            JOIN players p ON p.base_id = r.base_id;
        CREATE VIEW v_starting_eleven AS
            SELECT t.team_id, t.display_name AS team_name, l.slot, l.role_name,
                   l.depth, l.width, l.base_id, l.native_player_id,
                   l.player_name, l.overall, l.source_position_name
            FROM starting_lineups l
            JOIN teams t ON t.team_id = l.team_id;
    """)


def public_labels(catalog: dict[str, Any], kits: dict[str, Any] | None) -> dict[str, str]:
    labels = {row["key"]: row["label"] for row in catalog["categories"]}
    if kits:
        for row in kits.get("league_branding", {}).get("rows", []):
            labels[str(row["key"])] = str(row["after"])
    else:
        config = load_json(ROOT / "data/full_mobile_kit_migration.json",
                           required=False) or {}
        for key, row in config.get("league_branding", {}).items():
            labels[str(key)] = str(row["label"])
    return labels


def stat_dictionary(players: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    source_fields = sorted({key for row in players for key in row["data"]})
    mapping = []
    used = {"base_id"}
    for source in source_fields:
        if source == "BaseId":
            continue
        column = sql_name(source)
        if column in used:
            column = "source_" + column
        if column in used:
            raise ValueError(f"duplicate SQL field for {source}: {column}")
        used.add(column)
        mapping.append((source, column,
                        sql_type(row["data"].get(source) for row in players)))
    return mapping


def populate_database(connection: sqlite3.Connection,
                      sources: dict[str, Any],
                      stat_fields: list[tuple[str, str, str]]) -> None:
    registry = sources["registry"]
    catalog = sources["catalog"]
    snapshot = sources["snapshot"]
    tactics = sources["tactics"]
    manifest = sources["manifest"]
    portraits = sources["portraits"]
    kits = sources["kits"]
    paths = sources["paths"]
    registry_by_base = {int(row["ef_base_id"]): row for row in registry["players"]}
    snapshot_by_base = {int(row["base_id"]): row for row in snapshot["players"]}
    labels = public_labels(catalog, kits)

    metadata = {
        "schema_version": "1",
        "source_version": registry["source_version"],
        "migration_build_id": registry["migration_build_id"],
        "snapshot_content_id": registry["snapshot_content_id"],
        "registry_content_id": registry["content_id"],
        "catalog_content_id": catalog["content_id"],
        "stats_policy": registry["stats_policy"],
        "name_policy": registry["name_policy"],
        "identity_policy": registry["policy"],
        "expected_ef_base_ids": str(len(snapshot["master_index"])),
        "expected_allocated_players": str(len(registry["players"])),
        "expected_active_players": str(registry["counts"]["active_players"]),
        "expected_teams": str(len(catalog["teams"])),
        "expected_competitions": str(len(catalog["categories"])),
    }
    connection.executemany(
        "INSERT INTO metadata(key, value) VALUES (?, ?)", sorted(metadata.items())
    )

    team_counts = Counter(
        int(team_id) for row in registry["players"] for team_id in row["team_ids"]
    )
    connection.executemany(
        "INSERT INTO competitions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(
            row["key"], row["label"], labels[row["key"]], row.get("icon"),
            row["kind"], int(row["badge_slot"]), row.get("badge_source"),
            canonical_json(row.get("source_category_ids", [])),
            len(row.get("team_ids", [])),
        ) for row in catalog["categories"]],
    )
    connection.executemany(
        "INSERT INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(
            int(row["team_id"]), int(row["physical_team_id"]),
            row["display_name"], row.get("source_name"), row["kind"],
            row["category"], int(row["category_position"]),
            int(row["badge_slot"]), row.get("badge_source"),
            row.get("name_source"), row.get("roster_source"),
            team_counts[int(row["team_id"])], "active",
        ) for row in catalog["teams"]],
    )
    connection.executemany(
        "INSERT INTO excluded_teams VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(
            int(row["pes21_team_id"]), row.get("physical_team_id"),
            row.get("display_name"), row.get("ef_name"), row.get("kind"),
            row.get("player_count"), row.get("status"), row.get("reason"),
        ) for row in snapshot.get("excluded_teams", [])],
    )
    connection.executemany(
        "INSERT INTO ef_player_catalog VALUES (?, ?, ?, ?, ?, ?)",
        [(
            int(row["base_id"]), int(row["source_card_id"]),
            int(row["stats_source_card_id"]), row.get("stats_overall"),
            row.get("fingerprint"), int(bool(row.get("active"))),
        ) for row in snapshot["master_index"]],
    )

    player_rows = []
    stat_rows = []
    alias_rows = []
    for base_id in sorted(registry_by_base):
        public = registry_by_base[base_id]
        source = snapshot_by_base.get(base_id, {})
        data = source.get("data", {})
        position = data.get("Position")
        player_rows.append((
            base_id, int(public["native_player_id"]),
            int(public["physical_source_id"]), public["canonical_name"],
            public["normalized_name"], public["status"], public["allocation"],
            int(public["source_card_id"]), int(public["stats_source_card_id"]),
            data.get("Overall"), position, POSITION_NAMES.get(position),
            data.get("Country"), data.get("Age"), data.get("Height"),
            data.get("Weight"), public["fingerprint"],
            public["source_data_hash"], canonical_json(public["team_ids"]),
        ))
        stat_rows.append(tuple(
            [base_id] + [sqlite_value(data.get(source_name))
                         for source_name, _column, _kind in stat_fields]
        ))
        for alias in source.get("resolution", {}).get("aliases", []):
            alias_text = alias if isinstance(alias, str) else (
                alias.get("name") or alias.get("alias") or canonical_json(alias)
            )
            alias_rows.append((base_id, str(alias_text), canonical_json(alias)))
    connection.executemany(
        "INSERT INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        player_rows,
    )
    placeholders = ",".join("?" for _ in range(1 + len(stat_fields)))
    connection.executemany(
        f"INSERT INTO player_stats VALUES ({placeholders})", stat_rows
    )
    connection.executemany(
        "INSERT INTO player_aliases VALUES (?, ?, ?)", alias_rows
    )
    connection.executemany(
        "INSERT INTO field_dictionary VALUES (?, ?, ?, 'player_stats')",
        stat_fields,
    )

    roster_rows = []
    for team in snapshot["teams"]:
        team_id = int(team["ef_team_id"])
        if team_id not in {int(row["team_id"]) for row in catalog["teams"]}:
            continue
        for member in team["roster"]:
            base_id = int(member["base_id"])
            public = registry_by_base[base_id]
            roster_rows.append((
                team_id, base_id, int(public["native_player_id"]),
                int(member["source_card_id"]), int(member["position_order"]),
                int(member["shirt_number"]), int(bool(member["captain"])),
            ))
    connection.executemany(
        "INSERT INTO team_rosters VALUES (?, ?, ?, ?, ?, ?, ?)", roster_rows
    )

    if tactics:
        formation_rows = []
        for team_id_text, team in tactics.get("teams", {}).items():
            team_id = int(team_id_text)
            for strategy in team.get("strategies", []):
                strategy_id = int(strategy["strategy"])
                for slot, item in enumerate(strategy["slots"]):
                    role = int(item["role"])
                    formation_rows.append((
                        team_id, strategy_id, slot, role,
                        POSITION_NAMES.get(role), int(item["depth"]),
                        int(item["width"]), item.get("preferred_base_id"),
                        item.get("preferred_name"), team.get("url"),
                        team.get("sha256"),
                    ))
        connection.executemany(
            "INSERT INTO formation_slots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            formation_rows,
        )

    if manifest:
        lineup_rows = []
        for team in manifest.get("lineups", {}).get("teams", []):
            team_id = int(team["ef_team_id"])
            missing = {int(value) for value in team.get("missing_preferred_base_ids", [])}
            roles = team["formation_roles"]
            coordinates = team["formation_coordinates"]
            for slot, base_id_value in enumerate(team["starting_base_ids"]):
                base_id = int(base_id_value)
                public = registry_by_base[base_id]
                role = int(roles[slot])
                preferred = None
                if tactics:
                    team_hint = tactics.get("teams", {}).get(str(team_id), {})
                    strategies = team_hint.get("strategies", [])
                    if strategies and slot < len(strategies[0].get("slots", [])):
                        preferred = strategies[0]["slots"][slot].get(
                            "preferred_base_id"
                        )
                lineup_rows.append((
                    team_id, slot, base_id, int(public["native_player_id"]),
                    team["starting_names"][slot], role, POSITION_NAMES.get(role),
                    int(coordinates[slot][0]), int(coordinates[slot][1]),
                    team["starting_overalls"][slot],
                    int(team["starting_positions"][slot]),
                    POSITION_NAMES.get(int(team["starting_positions"][slot])),
                    preferred, int(preferred in missing if preferred else False),
                    int(bool(team["formation_adapted"])),
                    team.get("tactics_hint_sha256"),
                ))
        connection.executemany(
            "INSERT INTO starting_lineups VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            lineup_rows,
        )

    portrait_by_base = {
        int(row["base_id"]): row
        for row in (portraits or {}).get("portraits", [])
    }
    asset_rows = []
    for base_id, public in registry_by_base.items():
        portrait = portrait_by_base.get(base_id, {})
        asset_rows.append((
            base_id, int(public["native_player_id"]),
            public.get("portrait_asset_id"), portrait.get("source_card_id"),
            portrait.get("status", "not_reported"), portrait.get("sha256"),
            public.get("face_owner_id"), public.get("commentary_owner_id"),
            "carry_only_when_base_id_and_fingerprint_match",
            "stable_native_id_or_none",
        ))
    connection.executemany(
        "INSERT INTO player_assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        asset_rows,
    )

    if kits:
        kit_rows = []
        variants = []
        for status, rows in (("migrated", kits.get("migrated_teams", [])),
                             ("preserved", kits.get("preserved_teams", []))):
            for team in rows:
                kit_rows.append((
                    int(team["team_id"]), int(team["physical_team_id"]),
                    status, canonical_json(team.get("available_kits", [])),
                    team.get("reason"), len(team.get("previews", [])),
                ))
                for variant in team.get("kits", []):
                    assets = {row["role"]: row for row in variant.get("assets", [])}
                    body = assets.get("body", {})
                    back = assets.get("back", {})
                    variants.append((
                        int(team["team_id"]), variant["kind"], variant["suffix"],
                        variant.get("descriptor_target"),
                        variant.get("descriptor_source_archive"),
                        body.get("target_member"), body.get("target_sha256"),
                        back.get("target_member"), back.get("target_sha256"),
                        canonical_json(variant.get("preview_members", [])),
                    ))
        connection.executemany(
            "INSERT INTO team_kits VALUES (?, ?, ?, ?, ?, ?)", kit_rows
        )
        connection.executemany(
            "INSERT INTO kit_variants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            variants,
        )

    required_keys = {"player_registry", "team_catalog", "active_snapshot"}
    artifact_rows = []
    for key, path in paths.items():
        if not path:
            continue
        artifact_rows.append((
            key, repo_path(path), path.stat().st_size, sha256_file(path),
            int(key in required_keys),
        ))
    connection.executemany(
        "INSERT INTO source_artifacts VALUES (?, ?, ?, ?, ?)", artifact_rows
    )


def database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    result = {}
    for table in TABLE_DESCRIPTIONS:
        result[table] = connection.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]
    return result


def audit_database(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    counts = database_counts(connection)
    checks: dict[str, dict[str, Any]] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    expected_players = int(metadata["expected_allocated_players"])
    expected_base_ids = int(metadata["expected_ef_base_ids"])
    expected_teams = int(metadata["expected_teams"])
    expected_competitions = int(metadata["expected_competitions"])
    check("allocated_player_count", counts["players"] == expected_players,
          counts["players"])
    check("ef_base_catalog_count", counts["ef_player_catalog"] == expected_base_ids,
          counts["ef_player_catalog"])
    check("playable_team_count", counts["teams"] == expected_teams,
          counts["teams"])
    check("competition_count", counts["competitions"] == expected_competitions,
          counts["competitions"])
    duplicate_native = connection.execute(
        "SELECT COUNT(*) FROM (SELECT native_player_id FROM players "
        "GROUP BY native_player_id HAVING COUNT(*) > 1)"
    ).fetchone()[0]
    check("native_player_ids_unique", duplicate_native == 0, duplicate_native)
    bad_rosters = connection.execute(
        "SELECT team_id, COUNT(*) AS count FROM team_rosters GROUP BY team_id "
        "HAVING count < 18 OR count > 40"
    ).fetchall()
    check("rosters_between_18_and_40", not bad_rosters,
          [dict(row) for row in bad_rosters])
    roster_coverage = connection.execute(
        "SELECT COUNT(DISTINCT team_id) FROM team_rosters"
    ).fetchone()[0]
    check("all_teams_have_rosters", roster_coverage == counts["teams"],
          roster_coverage)
    lineup_coverage = connection.execute(
        "SELECT COUNT(*) FROM (SELECT team_id FROM starting_lineups "
        "GROUP BY team_id HAVING COUNT(*) = 11)"
    ).fetchone()[0]
    if counts["starting_lineups"]:
        check("all_teams_have_starting_eleven",
              lineup_coverage == counts["teams"], lineup_coverage)
    formation_coverage = connection.execute(
        "SELECT COUNT(DISTINCT team_id) FROM formation_slots"
    ).fetchone()[0]
    if counts["formation_slots"]:
        check("all_teams_have_formation_hints",
              formation_coverage == counts["teams"], formation_coverage)
    portrait_coverage = connection.execute(
        "SELECT COUNT(*) FROM player_assets WHERE portrait_status != 'not_reported'"
    ).fetchone()[0]
    if portrait_coverage:
        check("all_players_have_portrait_policy",
              portrait_coverage == counts["players"], portrait_coverage)
    kit_coverage = counts["team_kits"]
    if kit_coverage:
        check("all_teams_have_kit_policy", kit_coverage == counts["teams"],
              kit_coverage)
    foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
    check("foreign_keys_valid", not foreign_key_errors,
          [list(row) for row in foreign_key_errors])
    quick = connection.execute("PRAGMA quick_check").fetchone()[0]
    check("sqlite_quick_check", quick == "ok", quick)
    connection.close()
    result = {
        "schema_version": 1,
        "database": repo_path(path),
        "database_sha256": sha256_file(path),
        "result": "pass" if all(row["passed"] for row in checks.values()) else "fail",
        "counts": counts,
        "checks": checks,
    }
    return result


def build_public_registry(sources: dict[str, Any], destination: Path,
                          database: Path) -> dict[str, Any]:
    registry = sources["registry"]
    catalog = sources["catalog"]
    kits = sources["kits"]
    labels = public_labels(catalog, kits)
    team_counts = Counter(
        int(team_id) for row in registry["players"] for team_id in row["team_ids"]
    )
    destination.mkdir(parents=True, exist_ok=True)
    player_columns = [
        "ef_base_id", "native_pes21_id", "physical_source_id",
        "canonical_name", "status", "source_card_id",
        "stats_source_card_id", "portrait_asset_id", "face_owner_id",
        "commentary_owner_id",
    ]
    player_path = destination / "player-id-registry.csv"
    write_csv(player_path, player_columns, [
        (
            row["ef_base_id"], row["native_player_id"],
            row["physical_source_id"], row["canonical_name"],
            row["status"], row["source_card_id"], row["stats_source_card_id"],
            row.get("portrait_asset_id"), row.get("face_owner_id"),
            row.get("commentary_owner_id"),
        ) for row in registry["players"]
    ])
    team_path = destination / "team-registry.csv"
    team_columns = [
        "source_version", "migration_build_id", "team_id", "physical_team_id",
        "display_name", "source_name", "kind", "category_key",
        "category_position", "badge_slot", "player_count", "status",
    ]
    write_csv(team_path, team_columns, [
        (
            registry["source_version"], registry["migration_build_id"],
            row["team_id"], row["physical_team_id"], row["display_name"],
            row.get("source_name"), row["kind"], row["category"],
            row["category_position"], row["badge_slot"],
            team_counts[int(row["team_id"])], "active",
        ) for row in catalog["teams"]
    ])
    competition_path = destination / "competition-registry.csv"
    competition_columns = [
        "source_version", "migration_build_id", "category_key",
        "catalog_label", "display_label", "kind", "badge_slot", "team_count",
    ]
    write_csv(competition_path, competition_columns, [
        (
            registry["source_version"], registry["migration_build_id"],
            row["key"], row["label"], labels[row["key"]], row["kind"],
            row["badge_slot"], len(row["team_ids"]),
        ) for row in catalog["categories"]
    ])
    asset_policy_path = destination / "asset-policy.json"
    asset_policy = {
        "schema_version": 1,
        "identity_key": "ef_base_id",
        "native_storage_key": "native_pes21_id",
        "portrait": "PESDBTools source card; neutral silhouette when unavailable",
        "face": "carry only when BaseId and fingerprint match",
        "commentary": "preserve stable native owner or leave unset",
        "forbidden": ["surrogate_player", "portrait_alias", "donor_face"],
    }
    atomic_text(asset_policy_path,
                json.dumps(asset_policy, indent=2, ensure_ascii=False) + "\n")
    schema_path = destination / "master-schema.json"
    schema = {
        "schema_version": 1,
        "database": repo_path(database),
        "tables": [
            {"name": name, "description": description}
            for name, description in TABLE_DESCRIPTIONS.items()
        ],
        "relationships": [
            "competitions.category_key -> teams.category_key",
            "players.base_id -> team_rosters.base_id",
            "players.base_id -> starting_lineups.base_id",
            "players.base_id -> player_assets.base_id",
            "teams.team_id -> formation_slots.team_id",
            "teams.team_id -> team_kits.team_id",
        ],
        "local_only_tables": [
            "ef_player_catalog", "player_stats", "team_rosters",
            "formation_slots", "starting_lineups", "player_assets",
            "team_kits", "kit_variants",
        ],
    }
    atomic_text(schema_path, json.dumps(schema, indent=2) + "\n")
    files = [player_path, team_path, competition_path, asset_policy_path, schema_path]
    manifest = {
        "schema_version": 1,
        "source_version": registry["source_version"],
        "migration_build_id": registry["migration_build_id"],
        "snapshot_content_id": registry["snapshot_content_id"],
        "registry_content_id": registry["content_id"],
        "catalog_content_id": catalog["content_id"],
        "local_database": {
            "path": repo_path(database),
            "bytes": database.stat().st_size,
            "sha256": sha256_file(database),
        },
        "counts": {
            "ef_base_ids": len(sources["snapshot"]["master_index"]),
            "active_players": int(registry["counts"]["active_players"]),
            "allocated_players": len(registry["players"]),
            "teams": len(catalog["teams"]),
            "competitions": len(catalog["categories"]),
        },
        "files": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in files
        },
    }
    manifest_path = destination / "master-manifest.json"
    atomic_text(manifest_path, json.dumps(manifest, indent=2) + "\n")
    return manifest


def render_document(manifest: dict[str, Any], audit: dict[str, Any]) -> str:
    counts = manifest["counts"]
    table_lines = "\n".join(
        f"| `{name}` | {audit['counts'].get(name, 0):,} | {description} |"
        for name, description in TABLE_DESCRIPTIONS.items()
    )
    return f"""# PES21 NX master data catalog

This catalog is the stable lookup layer for player, team, competition,
formation, asset, and kit work. It is generated; do not hand-edit its CSV
registries or local SQLite database.

## Active snapshot

- Source: `{manifest['source_version']}`
- Migration build: `{manifest['migration_build_id']}`
- Snapshot content ID: `{manifest['snapshot_content_id']}`
- Local database SHA-256: `{manifest['local_database']['sha256']}`
- EF BaseIds indexed: **{counts['ef_base_ids']:,}**
- Materialized players: **{counts['active_players']:,}**
- Playable teams: **{counts['teams']:,}**
- Selector competitions/categories: **{counts['competitions']:,}**
- Audit: **{audit['result'].upper()}**

## Storage contract

- `local-inputs/master-data/pes21_master.db` is the complete local source for
  joins and ad-hoc SQL. It includes full player stats and local provenance and
  therefore remains ignored.
- `data/master/player-id-registry.csv` is the stable `BaseId` to native ID map.
- `data/master/team-registry.csv` maps logical teams to physical PES21 slots.
- `data/master/competition-registry.csv` records selector groups and licensed
  display labels.
- `local-debug/master-exports/` contains disposable full CSV exports.
- The locked EF snapshot remains under `local-inputs/`; raw game payloads are
  never copied into this public catalog.

## Database tables

| Table | Rows | Purpose |
|---|---:|---|
{table_lines}

Convenience views `v_team_rosters` and `v_starting_eleven` provide joined,
human-readable names and positions.

## Regeneration

```powershell
python tools/pes21_master_data.py sync
python tools/pes21_master_data.py audit
python tools/pes21_master_data.py export
```

Run `sync` whenever the locked EF version, migration build, formation hints,
portrait report, or kit report changes. `audit` blocks mismatched identities,
invalid references, incomplete rosters, or incomplete final lineups. `export`
creates one CSV for every master table and view without changing committed
registries.

## Common queries

```sql
-- Find a player and every club/national assignment.
SELECT * FROM v_team_rosters WHERE canonical_name LIKE '%Messi%';

-- Inspect one team's final eleven and pitch coordinates.
SELECT * FROM v_starting_eleven WHERE team_id = 108 ORDER BY slot;

-- Find portrait fallbacks or identities without commentary.
SELECT p.canonical_name, a.*
FROM player_assets a JOIN players p USING(base_id)
WHERE a.portrait_status = 'placeholder' OR a.commentary_owner_id IS NULL;
```
"""


def sync(args: argparse.Namespace) -> dict[str, Any]:
    sources = load_sources(args)
    players = sources["snapshot"]["players"]
    stat_fields = stat_dictionary(players)
    database = args.database.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    temporary = database.with_suffix(database.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        create_schema(connection, stat_fields)
        populate_database(connection, sources, stat_fields)
        connection.commit()
        quick = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick}")
    finally:
        connection.close()
    preflight = audit_database(temporary)
    if preflight["result"] != "pass":
        temporary.unlink(missing_ok=True)
        raise RuntimeError(canonical_json(preflight["checks"]))
    os.replace(temporary, database)
    audit = audit_database(database)
    manifest = build_public_registry(sources, args.public_dir.resolve(), database)
    atomic_text(args.document.resolve(), render_document(manifest, audit))
    print(json.dumps({
        "result": "synced", "database": str(database),
        "database_sha256": audit["database_sha256"],
        "counts": manifest["counts"],
    }, sort_keys=True))
    return audit


def audit_command(args: argparse.Namespace) -> dict[str, Any]:
    result = audit_database(args.database.resolve())
    output = args.output.resolve()
    atomic_text(output, json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "result": result["result"], "database": result["database"],
        "output": str(output), "checks": len(result["checks"]),
    }, sort_keys=True))
    if result["result"] != "pass":
        raise SystemExit(1)
    return result


def export_database(database: Path, output: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database)
    output.mkdir(parents=True, exist_ok=True)
    names = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    files = {}
    for name in names:
        cursor = connection.execute(f'SELECT * FROM "{name}"')
        columns = [row[0] for row in cursor.description]
        path = output / f"{name}.csv"
        write_csv(path, columns, cursor)
        files[name] = {
            "path": repo_path(path), "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    connection.close()
    manifest = {
        "schema_version": 1,
        "database": repo_path(database),
        "database_sha256": sha256_file(database),
        "files": files,
    }
    atomic_text(output / "export-manifest.json",
                json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({
        "result": "exported", "tables": len(files), "output": str(output),
    }, sort_keys=True))
    return manifest


def add_sync_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--tactics", type=Path, default=DEFAULT_TACTICS)
    parser.add_argument("--migration-manifest", type=Path,
                        default=DEFAULT_MIGRATION_MANIFEST)
    parser.add_argument("--portraits", type=Path, default=DEFAULT_PORTRAITS)
    parser.add_argument("--kits", type=Path, default=DEFAULT_KITS)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--public-dir", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sync_parser = commands.add_parser("sync", help="build the master database")
    add_sync_paths(sync_parser)
    audit_parser = commands.add_parser("audit", help="validate the master database")
    audit_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    audit_parser.add_argument("--output", type=Path,
                              default=DEFAULT_EXPORT / "master-audit.json")
    export_parser = commands.add_parser("export", help="export all tables as CSV")
    export_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    export_parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT)
    args = parser.parse_args()
    if args.command == "sync":
        sync(args)
    elif args.command == "audit":
        audit_command(args)
    else:
        export_database(args.database.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
