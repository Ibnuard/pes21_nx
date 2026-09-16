#!/usr/bin/env python3
"""Build the deterministic PES21PLAYERMIGRATION source and canary artifacts.

The eFootball BaseId is the cross-update identity.  A PES21 native ID is a
stable engine/storage address and is intentionally allowed to differ from the
BaseId when an existing face, commentary call, or occupied ID makes direct
reuse unsafe.

This tool never scrapes PESDB.  Its only player-data authority is the local
PESDBTools cache supplied with ``--pesdb-tools``.  The four stages are:

``sync``
    Lock the EF source, select playable teams, canonicalize BaseIds, and
    extract the current PES21 tables from the release OBB.
``audit``
    Validate the locked source and create/update the persistent native-ID
    registry without writing game binaries.
``canary``
    Patch only verified PES21 fields for representative teams and optionally
    build a detachable portrait/data OBB for hardware validation.
``build``
    Guard the future global build behind a signed-off hardware-canary report.
    The global binary rewrite deliberately remains fail-closed until every
    target field/table gate recorded by the audit is satisfied.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from build_inter_miami_release_experiment import cpk_index
from convert_efootball10_players import (
    PES21_ABILITY_BITS,
    PES21_PLAYER_SIZE,
    encode_pes21_wesys,
    pes21_name,
    pes21_player_id,
    pes21_player_position,
    records,
    set_pes21_english_name,
    set_pes21_registered_position,
    write_bits,
)
from import_efootball10_portraits import normalize_portrait
from pesdb import decode_wesys
from generate_exhibition_team_catalog import render_team_include
from generate_pesdb_runtime_rosters import choose_balanced_xi, load_tactic_roles


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "pes21_player_migration.json"
DEFAULT_CATALOG = ROOT / "data" / "exhibition_team_catalog.json"
DEFAULT_PESDB_TOOLS = ROOT.parent / "tools" / "PESDBTools"
DEFAULT_OBB = (
    ROOT
    / "local-checkpoints"
    / "2026-09-16-startup-brand-v4"
    / "patch.305030001.jp.nyan2021.pesam.obb"
)
DEFAULT_NRO = ROOT / "dist" / "pes21_nx" / "pes21_nx.nro"
DEFAULT_REGISTRY = ROOT / "data" / "pes21_player_registry.json"
DEFAULT_MIGRATION_CATALOG = ROOT / "data" / "exhibition_team_catalog_migration.json"
DEFAULT_MIGRATION_TEAM_INCLUDE = (
    ROOT / "source" / "exhibition_teams_migration_generated.inc"
)
DEFAULT_CANARY_ROSTER_INCLUDE = (
    ROOT / "source" / "exhibition_rosters_migration_canary_generated.inc"
)
DEFAULT_BASE_PAK = (
    ROOT
    / "dist"
    / "pes21_nx"
    / "PesMobile"
    / "Content"
    / "Paks"
    / "PesMobile-Android_ETC1.pak"
)
DEFAULT_REPAK = ROOT.parent / "tools" / "repak" / "repak.exe"

DT200_MEMBER = "Expansion/dt200_mobile_all.cpk"
DT241_MEMBER = "Expansion/dt241_mobile_all.cpk"
PLAYER_MEMBER = "common/etc/pesdb/Player.bin"
INSTALL_MEMBER = "common/etc/pesdb/InstallVersionPlayer.bin"
ASSIGNMENT_MEMBER = "common/etc/pesdb/PlayerAssignment.bin"
SPECIAL_ASSIGNMENT_MEMBER = "common/etc/pesdb/SpecialPlayerAssignment.bin"
DELETE_MEMBER = "common/etc/pesdb/PlayerDeleteList.bin"
WEEKLY_MEMBER = "common/etc/pesdb/PlayerWeekly.bin"
APPEARANCE_MEMBER = "common/etc/appearance/PlayerAppearance.bin"
BOOTS_MEMBER = "common/etc/appearance/BootsList.bin"
TACTICS_MEMBER = "common/etc/pesdb/Tactics.bin"
TACTICS_FORMATION_MEMBER = "common/etc/pesdb/TacticsFormation.bin"

PES21_POSITION_BITS = {
    "GK": 350,
    "CB": 468,
    "LB": 318,
    "RB": 474,
    "DMF": 414,
    "CMF": 456,
    "LMF": 466,
    "RMF": 460,
    "AMF": 464,
    "LWF": 472,
    "RWF": 476,
    "SS": 478,
    "CF": 470,
}

SOURCE_TO_PES21_STATS = {
    "set_piece_taking": "PlaceKicking",
    "low_pass": "LowPass",
    "gk_parrying": "GKParrying",
    "defensive_awareness": "DefensiveAwareness",
    "ball_control": "BallControl",
    "heading": "Header",
    "jumping": "Jump",
    "gk_reach": "GKReach",
    "speed": "Speed",
    "tackling": "BallWinning",
    "gk_reflexes": "GKReflexes",
    "gk_awareness": "GKAwareness",
    "curl": "Curl",
    "stamina": "Stamina",
    "acceleration": "Acceleration",
    "dribbling": "Dribbling",
    "kicking_power": "KickingPower",
    "gk_catching": "GKCatching",
    "offensive_awareness": "OffensiveAwareness",
    "balance": "Balance",
    "aggression": "Aggression",
    "physical_contact": "PhysicalContact",
    "finishing": "Finishing",
    "lofted_pass": "LoftedPass",
    "tight_possession": "TightPossession",
}

VERIFIED_CANARY_FIELDS = [
    "english_name",
    "registered_position",
    "position_familiarity",
    "nationality",
    "height_weight_age_foot",
    "weak_foot_form_injury_reputation_attitude",
    "25_gameplay_abilities",
    "ef26_authoritative_overall",
    "position_balanced_starting_xi",
]


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def write_json(path: Path, payload: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    separators = (",", ":") if compact else None
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=True,
            indent=None if compact else 2,
            separators=separators,
            sort_keys=compact,
        )
        + "\n",
        encoding="utf-8",
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_id(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)[:16]


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", errors="ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def name_tokens(value: str) -> list[str]:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", errors="ignore").decode("ascii").lower()
    return re.findall(r"[a-z0-9]+", text)


def names_compatible(left: str, right: str) -> bool:
    if normalize_name(left) == normalize_name(right):
        return True
    left_tokens = name_tokens(left)
    right_tokens = name_tokens(right)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    return (
        left_tokens[-1] == right_tokens[-1]
        and left_tokens[0][0] == right_tokens[0][0]
    )


def identity_fingerprint(player: dict[str, Any]) -> str:
    payload = {
        "base_id": int(player.get("BaseId", 0)),
        "name": normalize_name(str(player.get("Name", ""))),
        "country": int(player.get("Country", 0)),
        "height": int(player.get("Height", 0)),
        "foot": int(bool(player.get("Foot", 0))),
    }
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )[:20]


def member_payload(path: Path, member: str) -> bytes:
    _header, rows, data_base = cpk_index(path)
    row = rows.get(member)
    if row is None:
        raise RuntimeError(f"{path}: missing CPK member {member}")
    with path.open("rb") as source:
        source.seek(data_base + int(row["FileOffset"]))
        payload = source.read(int(row["FileSize"]))
    if len(payload) != int(row["FileSize"]):
        raise RuntimeError(f"{path}: truncated CPK member {member}")
    return payload


def load_source(path: Path) -> dict[str, Any]:
    source = read_json(path)
    for key in ("version", "players", "teams", "assigns"):
        if key not in source:
            raise ValueError(f"{path}: missing {key}")
    if not isinstance(source["players"], list) or not isinstance(source["teams"], dict):
        raise ValueError(f"{path}: invalid PESDBTools cache shape")
    return source


@dataclass(frozen=True)
class SourceView:
    source: dict[str, Any]
    players_by_id: dict[int, dict[str, Any]]
    variants_by_base: dict[int, list[dict[str, Any]]]
    teams_by_id: dict[int, dict[str, Any]]
    assignments_by_team: dict[int, list[dict[str, Any]]]


def source_view(source: dict[str, Any]) -> SourceView:
    players_by_id = {int(row["Id"]): row for row in source["players"]}
    if len(players_by_id) != len(source["players"]):
        raise ValueError("PESDBTools cache contains duplicate card IDs")
    variants_by_base: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in source["players"]:
        variants_by_base[int(row["BaseId"])].append(row)
    teams_by_id = {int(key): row for key, row in source["teams"].items()}
    assignments_by_team: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in source["assigns"]:
        assignments_by_team[int(row["TeamId"])].append(row)
    return SourceView(
        source=source,
        players_by_id=players_by_id,
        variants_by_base=dict(variants_by_base),
        teams_by_id=teams_by_id,
        assignments_by_team=dict(assignments_by_team),
    )


def select_teams(
    catalog: dict[str, Any], view: SourceView, minimum: int, maximum: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in catalog["teams"]:
        team_id = int(row["team_id"])
        source_team = view.teams_by_id.get(team_id)
        reason = None
        count = len(view.assignments_by_team.get(team_id, []))
        if source_team is None:
            reason = "missing_from_ef_source"
        elif (row["kind"] == "national") != bool(source_team["NationalTeam"]):
            reason = "team_kind_mismatch"
        elif count < minimum:
            reason = "roster_below_minimum"
        elif count > maximum:
            reason = "roster_above_maximum"
        detail = {
            "pes21_team_id": team_id,
            "physical_team_id": int(row.get("physical_team_id", team_id)),
            "ef_team_id": team_id if source_team is not None else None,
            "display_name": row["display_name"],
            "ef_name": source_team.get("NameEnglish") if source_team else None,
            "kind": row["kind"],
            "player_count": count,
        }
        if reason is None:
            detail["status"] = "active"
            selected.append(detail)
        else:
            detail.update({"status": "excluded", "reason": reason})
            excluded.append(detail)
    return selected, excluded


def choose_canonical(
    base_id: int,
    assigned_rows: list[tuple[dict[str, Any], dict[str, Any]]],
    view: SourceView,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Choose one real identity while treating unlicensed NT names as aliases."""
    club_rows = [item for item in assigned_rows if not item[1]["NationalTeam"]]
    club_names = {normalize_name(str(item[0]["Name"])) for item in club_rows}
    if len(club_names) > 1:
        raise RuntimeError(
            f"BaseId {base_id} resolves to multiple club identities: "
            + ", ".join(sorted({str(item[0]["Name"]) for item in club_rows}))
        )

    direct = next(
        (row for row in view.variants_by_base[base_id] if int(row["Id"]) == base_id),
        None,
    )
    if direct is not None and (not club_names or normalize_name(str(direct["Name"])) in club_names):
        return direct, {"method": "direct_base_card", "aliases": []}

    if club_rows:
        ranked = sorted(
            club_rows,
            key=lambda item: (
                int(item[0].get("CardType", 0)) != 0,
                not bool(item[1].get("Licensed", False)),
                int(item[0]["Id"]),
            ),
        )
        chosen = ranked[0][0]
        aliases = sorted(
            {
                str(player["Name"])
                for player, _team in assigned_rows
                if normalize_name(str(player["Name"]))
                != normalize_name(str(chosen["Name"]))
            }
        )
        return chosen, {"method": "club_assignment", "aliases": aliases}

    ranked = sorted(
        (item[0] for item in assigned_rows),
        key=lambda row: (int(row.get("CardType", 0)) != 0, int(row["Id"])),
    )
    if not ranked:
        raise RuntimeError(f"BaseId {base_id} has no assigned source row")
    return ranked[0], {"method": "national_assignment", "aliases": []}


def build_active_snapshot(
    source: dict[str, Any], catalog: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    view = source_view(source)
    selected, excluded = select_teams(
        catalog,
        view,
        int(config["minimum_players"]),
        int(config["maximum_players"]),
    )
    selected_ids = {int(row["ef_team_id"]) for row in selected}
    assigned_by_base: dict[
        int, list[tuple[dict[str, Any], dict[str, Any]]]
    ] = collections.defaultdict(list)
    roster_rows: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for team_id in sorted(selected_ids):
        team = view.teams_by_id[team_id]
        seen_base: set[int] = set()
        for assignment in view.assignments_by_team[team_id]:
            player = view.players_by_id.get(int(assignment["PlayerId"]))
            if player is None:
                raise RuntimeError(
                    f"team {team_id} assignment references missing card "
                    f"{assignment['PlayerId']}"
                )
            base_id = int(player["BaseId"])
            if base_id in seen_base:
                raise RuntimeError(f"team {team_id} contains duplicate BaseId {base_id}")
            seen_base.add(base_id)
            assigned_by_base[base_id].append((player, team))
            roster_rows[team_id].append(
                {
                    "base_id": base_id,
                    "source_card_id": int(player["Id"]),
                    "shirt_number": int(assignment.get("ShirtNumber", 0)),
                    "position_order": int(assignment.get("PositionId", 0)),
                    "captain": bool(assignment.get("Captain", False)),
                }
            )

    players: list[dict[str, Any]] = []
    canonical_by_base: dict[int, dict[str, Any]] = {}
    for base_id in sorted(assigned_by_base):
        canonical, resolution = choose_canonical(
            base_id, assigned_by_base[base_id], view
        )
        canonical_by_base[base_id] = canonical
        players.append(
            {
                "base_id": base_id,
                "source_card_id": int(canonical["Id"]),
                "name": str(canonical["Name"]),
                "fingerprint": identity_fingerprint(canonical),
                "resolution": resolution,
                "data": canonical,
            }
        )

    teams: list[dict[str, Any]] = []
    selected_by_id = {int(row["ef_team_id"]): row for row in selected}
    for team_id in sorted(selected_ids):
        team_row = dict(selected_by_id[team_id])
        team_row["roster"] = sorted(
            roster_rows[team_id],
            key=lambda row: (int(row["position_order"]), int(row["base_id"])),
        )
        teams.append(team_row)

    index_rows: list[dict[str, Any]] = []
    for base_id, variants in sorted(view.variants_by_base.items()):
        direct = next((row for row in variants if int(row["Id"]) == base_id), None)
        chosen = direct or sorted(
            variants,
            key=lambda row: (
                int(row.get("CardType", 0)) != 0,
                int(row["Id"]),
            ),
        )[0]
        index_rows.append(
            {
                "base_id": base_id,
                "source_card_id": int(chosen["Id"]),
                "fingerprint": identity_fingerprint(chosen),
                "active": base_id in canonical_by_base,
            }
        )

    core = {
        "schema_version": 1,
        "source_version": str(source["version"]),
        "policy": config["policy"],
        "counts": {
            "source_cards": len(view.players_by_id),
            "source_base_ids": len(view.variants_by_base),
            "catalog_teams": len(catalog["teams"]),
            "active_teams": len(teams),
            "excluded_teams": len(excluded),
            "active_players": len(players),
        },
        "teams": teams,
        "excluded_teams": excluded,
        "players": players,
        "master_index": index_rows,
    }
    core["content_id"] = content_id(core)
    return core


def extract_release_inputs(obb: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    dt200 = member_payload(obb, DT200_MEMBER)
    dt241 = member_payload(obb, DT241_MEMBER)
    dt200_path = output / "dt200_mobile_all.cpk"
    dt241_path = output / "dt241_mobile_all.cpk"
    dt200_path.write_bytes(dt200)
    dt241_path.write_bytes(dt241)
    extracted: dict[str, Any] = {
        "obb": {"path": str(obb), "sha256": sha256_file(obb)},
        "dt200": {"path": str(dt200_path), "sha256": sha256_bytes(dt200)},
        "dt241": {"path": str(dt241_path), "sha256": sha256_bytes(dt241)},
        "tables": {},
    }
    table_dir = output / "tables"
    table_dir.mkdir(exist_ok=True)
    for member in (
        PLAYER_MEMBER,
        INSTALL_MEMBER,
        ASSIGNMENT_MEMBER,
        SPECIAL_ASSIGNMENT_MEMBER,
        DELETE_MEMBER,
        WEEKLY_MEMBER,
        APPEARANCE_MEMBER,
        BOOTS_MEMBER,
        TACTICS_MEMBER,
        TACTICS_FORMATION_MEMBER,
    ):
        try:
            payload = member_payload(dt200_path, member)
        except RuntimeError:
            continue
        path = table_dir / Path(member).name
        path.write_bytes(payload)
        extracted["tables"][Path(member).name] = {
            "member": member,
            "path": str(path),
            "sha256": sha256_bytes(payload),
        }
    return extracted


def lock_face_inventory(base_pak: Path, repak: Path, output: Path) -> dict[str, Any]:
    """Lock native real-face owners from the exact PAK used by the release.

    Real faces are addressed directly by native player ID.  The inventory is
    therefore part of the source lock: an occupied face ID must never be used
    as a generic reserve slot merely because its current Player.bin row is not
    active in the EF26 scope.
    """

    if not base_pak.is_file():
        raise FileNotFoundError(f"base PES21 PAK not found: {base_pak}")
    if not repak.is_file():
        raise FileNotFoundError(f"repak not found: {repak}")
    completed = subprocess.run(
        [str(repak), "list", str(base_pak)],
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(
            f"repak could not inventory {base_pak}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    pattern = re.compile(
        r"(?:^|/)character/RealFace/(\d+)_face\.uasset$",
        re.IGNORECASE,
    )
    face_ids = sorted(
        {
            int(match.group(1))
            for line in completed.stdout.splitlines()
            for match in [pattern.search(line.strip())]
            if match is not None
        }
    )
    if len(face_ids) < 2_000 or not {4522, 7511}.issubset(face_ids):
        raise RuntimeError(
            "release face inventory failed sanity checks "
            f"(count={len(face_ids)}, Messi={7511 in face_ids}, "
            f"Ronaldo={4522 in face_ids})"
        )
    payload = {
        "schema_version": 1,
        "source_pak_sha256": sha256_file(base_pak),
        "count": len(face_ids),
        "ids": face_ids,
    }
    write_json(output, payload, compact=True)
    return {
        "path": str(output),
        "sha256": sha256_file(output),
        "source_pak_sha256": payload["source_pak_sha256"],
        "count": len(face_ids),
    }


def sync_command(args: argparse.Namespace) -> None:
    config = read_json(args.config)
    source_path = args.pesdb_tools / f"db_{config['source_version']}.json"
    if not source_path.is_file():
        raise FileNotFoundError(f"PESDBTools cache not found: {source_path}")
    if not args.obb.is_file():
        raise FileNotFoundError(f"release OBB not found: {args.obb}")
    source = load_source(source_path)
    if source["version"] != config["source_version"]:
        raise RuntimeError("PESDBTools cache version disagrees with migration config")
    catalog = read_json(args.catalog)
    snapshot = build_active_snapshot(source, catalog, config)
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    locked_source = work / "source-db.json"
    if locked_source.resolve() != source_path.resolve():
        shutil.copyfile(source_path, locked_source)
    release = extract_release_inputs(args.obb, work / "base")
    face_inventory = lock_face_inventory(
        args.base_pak,
        args.repak,
        work / "face-ids.json",
    )
    appearance_path = work / "ef-appearance.bin"
    appearance_error = None
    if not args.no_pull_appearance and not appearance_path.is_file():
        command = [
            sys.executable,
            str(args.pesdb_tools / "pull_pesdb.py"),
            "--version",
            str(config["source_version"]),
            "--type",
            "Appearance",
            "-o",
            str(appearance_path),
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode:
            appearance_error = (completed.stderr or completed.stdout).strip()
            appearance_path.unlink(missing_ok=True)
    source_lock = {
        "schema_version": 1,
        "authority": "PESDBTools",
        "source_version": config["source_version"],
        "source_cache": {
            "path": str(locked_source),
            "sha256": sha256_file(locked_source),
        },
        "appearance": (
            {"path": str(appearance_path), "sha256": sha256_file(appearance_path)}
            if appearance_path.is_file()
            else {"path": None, "error": appearance_error or "not requested"}
        ),
        "release": release,
        "face_inventory": face_inventory,
        "snapshot_content_id": snapshot["content_id"],
    }
    # Paths are useful diagnostics but are deliberately excluded from the ID,
    # so moving the same locked inputs to another machine remains reproducible.
    source_lock["migration_build_id"] = content_id(
        {
            "schema_version": source_lock["schema_version"],
            "source_version": source_lock["source_version"],
            "source_cache_sha256": source_lock["source_cache"]["sha256"],
            "appearance_sha256": source_lock["appearance"].get("sha256"),
            "obb_sha256": release["obb"]["sha256"],
            "dt200_sha256": release["dt200"]["sha256"],
            "dt241_sha256": release["dt241"]["sha256"],
            "face_inventory_sha256": face_inventory["sha256"],
            "snapshot_content_id": snapshot["content_id"],
        }
    )
    snapshot["migration_build_id"] = source_lock["migration_build_id"]
    write_json(work / "active-snapshot.json", snapshot)
    write_json(work / "source-lock.json", source_lock)
    print(
        json.dumps(
            {
                "work": str(work),
                "migration_build_id": source_lock["migration_build_id"],
                **snapshot["counts"],
            },
            sort_keys=True,
        )
    )


def load_player_rows(path: Path) -> tuple[list[bytes], dict[int, bytes]]:
    raw = decode_wesys(path)
    rows = records(raw, PES21_PLAYER_SIZE)
    by_id = {pes21_player_id(row): row for row in rows}
    if len(by_id) != len(rows):
        raise RuntimeError("PES21 Player.bin contains duplicate IDs")
    return rows, by_id


def table_raw(path: Path) -> bytes:
    payload = path.read_bytes()
    if len(payload) >= 8 and payload[3:8] == b"WESYS":
        return decode_wesys(path)
    return payload


def fixed_u32_ids(path: Path, row_size: int, offsets: tuple[int, ...]) -> set[int]:
    raw = table_raw(path)
    if len(raw) % row_size:
        raise ValueError(f"{path}: partial {row_size}-byte row")
    result: set[int] = set()
    for row_offset in range(0, len(raw), row_size):
        for field_offset in offsets:
            value = struct.unpack_from("<I", raw, row_offset + field_offset)[0]
            if value:
                result.add(value)
    return result


def protected_face_ids(path: Path) -> set[int]:
    if not path.is_file():
        raise FileNotFoundError(
            f"locked face inventory is missing: {path}; run sync first"
        )
    payload = read_json(path)
    result = {int(value) for value in payload.get("ids", [])}
    if len(result) != int(payload.get("count", -1)):
        raise RuntimeError(f"{path}: duplicate or invalid face IDs")
    if not {4522, 7511}.issubset(result):
        raise RuntimeError(f"{path}: mandatory Messi/Ronaldo face owners are missing")
    return result


def build_registry(
    snapshot: dict[str, Any],
    table_dir: Path,
    face_inventory_path: Path,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    player_path = table_dir / "Player.bin"
    rows, by_id = load_player_rows(player_path)
    face_ids = protected_face_ids(face_inventory_path)
    assigned_ids = fixed_u32_ids(
        table_dir / "PlayerAssignment.bin", 16, (4,)
    )
    special_ids = fixed_u32_ids(
        table_dir / "SpecialPlayerAssignment.bin", 8, (0,)
    )
    deleted_ids = fixed_u32_ids(
        table_dir / "PlayerDeleteList.bin", 4, (0,)
    )
    appearance_ids = fixed_u32_ids(
        table_dir / "PlayerAppearance.bin", 60, (0,)
    )
    boots_ids = fixed_u32_ids(table_dir / "BootsList.bin", 8, (0,))
    weekly_path = table_dir / "PlayerWeekly.bin"
    weekly_ids = (
        fixed_u32_ids(weekly_path, 8, (0, 4)) if weekly_path.is_file() else set()
    )
    referenced_auxiliary_ids = special_ids | appearance_ids | boots_ids | weekly_ids
    by_name: dict[str, list[int]] = collections.defaultdict(list)
    for player_id, row in by_id.items():
        name = normalize_name(pes21_name(row))
        if name:
            by_name[name].append(player_id)

    previous_rows = {
        int(row["ef_base_id"]): row
        for row in (
            (previous or {}).get("players", [])
            if int((previous or {}).get("schema_version", 0)) == 2
            else []
        )
    }
    previous_face_policy = int((previous or {}).get("face_policy_version", 0))
    active_base_ids = {
        int(player["base_id"]) for player in snapshot["players"]
    }
    previous_tombstones = {
        base_id: row
        for base_id, row in previous_rows.items()
        if base_id not in active_base_ids
    }
    blocked_native = {
        int(row["native_player_id"]) for row in previous_tombstones.values()
    }
    blocked_physical = {
        int(row.get("physical_source_id", row["native_player_id"]))
        for row in previous_tombstones.values()
    }
    used_native: set[int] = set()
    used_physical: set[int] = set()
    registry_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    active_players = sorted(snapshot["players"], key=lambda row: int(row["base_id"]))
    team_ids_by_base: dict[int, list[int]] = collections.defaultdict(list)
    for team in snapshot["teams"]:
        for roster in team["roster"]:
            team_ids_by_base[int(roster["base_id"])].append(
                int(team["ef_team_id"])
            )

    def accept(
        base_id: int,
        player: dict[str, Any],
        native_id: int,
        physical_source_id: int,
        method: str,
        face_owner_id: int | None = None,
    ) -> None:
        if native_id in used_native:
            raise RuntimeError(f"native PES21 ID {native_id} allocated twice")
        if physical_source_id in used_physical:
            raise RuntimeError(
                f"physical PES21 row {physical_source_id} allocated twice"
            )
        if physical_source_id not in by_id:
            raise RuntimeError(f"physical PES21 row {physical_source_id} is missing")
        used_native.add(native_id)
        used_physical.add(physical_source_id)
        current = by_id.get(native_id)
        name_matches = current is not None and names_compatible(
            pes21_name(current), player["name"]
        )
        registry_rows.append(
            {
                "master_uid": f"ef:{base_id}",
                "ef_base_id": base_id,
                "source_card_id": int(player["source_card_id"]),
                "canonical_name": str(player["name"]),
                "normalized_name": normalize_name(str(player["name"])),
                "native_player_id": native_id,
                "physical_source_id": physical_source_id,
                "fingerprint": player["fingerprint"],
                "source_data_hash": content_id(player["data"]),
                "team_ids": sorted(set(team_ids_by_base[base_id])),
                "allocation": method,
                "face_owner_id": face_owner_id,
                "commentary_owner_id": native_id if name_matches else None,
                "portrait_asset_id": native_id,
                "status": "active",
            }
        )

    pending: list[dict[str, Any]] = []
    for player in active_players:
        base_id = int(player["base_id"])
        old = previous_rows.get(base_id)
        if (
            previous_face_policy == 1
            and old is not None
            and old.get("fingerprint") == player["fingerprint"]
        ):
            native_id = int(old["native_player_id"])
            old_physical = int(old.get("physical_source_id", native_id))
            if native_id in by_id:
                old_physical = native_id
            inherited_face_owner = old.get("face_owner_id")
            face_safe = (
                native_id not in face_ids
                or native_id == base_id
                or (
                    previous_face_policy == 1
                    and inherited_face_owner is not None
                    and int(inherited_face_owner) == native_id
                )
            )
            if (
                old_physical in by_id
                and old_physical not in used_physical
                and native_id not in used_native
                and (native_id in by_id or (native_id not in face_ids))
                and face_safe
            ):
                accept(
                    base_id,
                    player,
                    native_id,
                    old_physical,
                    str(old.get("allocation", "registry_preserved")),
                    (
                        int(inherited_face_owner)
                        if inherited_face_owner is not None and face_safe
                        else None
                    ),
                )
                continue
        current = by_id.get(base_id)
        if current is not None and names_compatible(
            pes21_name(current), player["name"]
        ):
            accept(
                base_id,
                player,
                base_id,
                base_id,
                "direct_identity_match",
                base_id if base_id in face_ids else None,
            )
            continue
        names = [
            value
            for value in by_name.get(normalize_name(player["name"]), [])
            if value not in used_physical and value not in used_native
            and value not in face_ids
        ]
        if len(names) == 1:
            accept(base_id, player, names[0], names[0], "unique_name_match")
            continue
        pending.append(player)

    reserve = [
        player_id
        for player_id in sorted(by_id)
        if player_id not in used_physical
        and player_id not in blocked_physical
        and player_id not in face_ids
        and player_id not in assigned_ids
        and player_id not in referenced_auxiliary_ids
    ]
    reserve.sort(key=lambda value: (value not in deleted_ids, value))
    reserve_cursor = 0

    def take_reserve() -> int:
        nonlocal reserve_cursor
        while (
            reserve_cursor < len(reserve)
            and reserve[reserve_cursor] in used_physical
        ):
            reserve_cursor += 1
        if reserve_cursor >= len(reserve):
            raise RuntimeError("no clean physical reserve row remains")
        value = reserve[reserve_cursor]
        reserve_cursor += 1
        return value

    for player in pending:
        base_id = int(player["base_id"])
        if (
            base_id not in used_native
            and base_id not in blocked_native
            and base_id not in by_id
            and base_id not in face_ids
        ):
            try:
                donor_id = take_reserve()
            except RuntimeError:
                unresolved.append({"base_id": base_id, "reason": "no_clean_reserve_id"})
                continue
            accept(base_id, player, base_id, donor_id, "new_base_id")
            continue
        try:
            native_id = take_reserve()
        except RuntimeError:
            unresolved.append({"base_id": base_id, "reason": "no_clean_reserve_id"})
            continue
        accept(base_id, player, native_id, native_id, "clean_reserve_id")

    for base_id, row in sorted(previous_tombstones.items()):
        tombstone = dict(row)
        tombstone["status"] = "tombstone"
        registry_rows.append(tombstone)

    active_registry_rows = [
        row for row in registry_rows if row["status"] == "active"
    ]
    tombstone_rows = [
        row for row in registry_rows if row["status"] == "tombstone"
    ]
    reserved_physical_ids = sorted(
        set(by_id)
        - {int(row["physical_source_id"]) for row in active_registry_rows}
        - {
            int(row.get("physical_source_id", row["native_player_id"]))
            for row in tombstone_rows
        }
    )

    payload = {
        "schema_version": 2,
        "metadata_version": 1,
        "face_policy_version": 1,
        "source_version": snapshot["source_version"],
        "snapshot_content_id": snapshot["content_id"],
        "migration_build_id": snapshot["migration_build_id"],
        "policy": "stable_hybrid",
        "name_policy": "ef26_canonical",
        "counts": {
            "physical_rows": len(rows),
            "active_players": len(active_players),
            "allocated_players": len(active_registry_rows),
            "unresolved_players": len(unresolved),
            "tombstone_players": len(tombstone_rows),
            "protected_face_ids": len(face_ids),
            "clean_physical_reserve_rows": sum(
                value not in used_physical for value in reserve
            ),
            "reserve_rows": len(rows) - len(registry_rows),
        },
        "players": sorted(registry_rows, key=lambda row: int(row["ef_base_id"])),
        "reserve_physical_ids": reserved_physical_ids,
        "unresolved": unresolved,
    }
    payload["content_id"] = content_id(payload)
    return payload


def audit_command(args: argparse.Namespace) -> None:
    snapshot = read_json(args.work / "active-snapshot.json")
    source_lock = read_json(args.work / "source-lock.json")
    config = read_json(args.config)
    if snapshot["content_id"] != source_lock["snapshot_content_id"]:
        raise RuntimeError("snapshot does not match source lock")
    if snapshot["counts"]["source_base_ids"] != 24174:
        raise RuntimeError("EF source BaseId count changed; review the new version")
    if snapshot["counts"]["active_teams"] != 443:
        raise RuntimeError("playable team count differs from the approved 443-team scope")
    for team in snapshot["teams"]:
        count = len(team["roster"])
        if not int(config["minimum_players"]) <= count <= int(config["maximum_players"]):
            raise RuntimeError(f"team {team['ef_team_id']} has invalid roster size {count}")
        base_ids = [int(row["base_id"]) for row in team["roster"]]
        if len(base_ids) != len(set(base_ids)):
            raise RuntimeError(f"team {team['ef_team_id']} duplicates a BaseId")
    previous = read_json(args.registry) if args.registry.is_file() else None
    table_dir = args.work / "base" / "tables"
    registry = build_registry(
        snapshot,
        table_dir,
        args.work / "face-ids.json",
        previous,
    )
    if registry["unresolved"]:
        raise RuntimeError(
            f"native ID allocation has {len(registry['unresolved'])} unresolved players"
        )
    previous_active = {
        int(row["ef_base_id"]): row
        for row in (previous or {}).get("players", [])
        if row.get("status") == "active"
    }
    current_active = {
        int(row["ef_base_id"]): row
        for row in registry["players"]
        if row.get("status") == "active"
    }
    baseline = int((previous or {}).get("metadata_version", 0)) != 1
    change_report = {
        "schema_version": 1,
        "source_version": snapshot["source_version"],
        "migration_build_id": snapshot["migration_build_id"],
        "baseline": baseline,
        "added": sorted(current_active) if baseline else sorted(set(current_active) - set(previous_active)),
        "removed": [] if baseline else sorted(set(previous_active) - set(current_active)),
        "transferred": [] if baseline else sorted(
            base_id
            for base_id in set(previous_active) & set(current_active)
            if previous_active[base_id].get("team_ids")
            != current_active[base_id].get("team_ids")
        ),
        "stat_changed": [] if baseline else sorted(
            base_id
            for base_id in set(previous_active) & set(current_active)
            if previous_active[base_id].get("source_data_hash")
            != current_active[base_id].get("source_data_hash")
        ),
        "name_changed": [] if baseline else sorted(
            base_id
            for base_id in set(previous_active) & set(current_active)
            if previous_active[base_id].get("canonical_name")
            != current_active[base_id].get("canonical_name")
        ),
        "portrait_changed": [] if baseline else sorted(
            base_id
            for base_id in set(previous_active) & set(current_active)
            if previous_active[base_id].get("source_card_id")
            != current_active[base_id].get("source_card_id")
        ),
        "unresolved": registry["unresolved"],
    }
    change_report["counts"] = {
        key: len(change_report[key])
        for key in (
            "added",
            "removed",
            "transferred",
            "stat_changed",
            "name_changed",
            "portrait_changed",
            "unresolved",
        )
    }
    write_json(args.work / "change-report.json", change_report)
    write_json(args.registry, registry, compact=True)
    catalog = read_json(args.catalog)
    active_team_ids = {int(row["ef_team_id"]) for row in snapshot["teams"]}
    migration_catalog = {
        key: value
        for key, value in catalog.items()
        if key not in {"categories", "teams", "content_id", "counts"}
    }
    migration_catalog.update(
        {
            "generated_by": "tools/pes21_player_migration.py audit",
            "source_version": snapshot["source_version"],
            "migration_build_id": snapshot["migration_build_id"],
            "snapshot_content_id": snapshot["content_id"],
            "categories": [],
            "teams": [
                row
                for row in catalog["teams"]
                if int(row["team_id"]) in active_team_ids
            ],
        }
    )
    for category in catalog["categories"]:
        filtered = [
            int(value)
            for value in category["team_ids"]
            if int(value) in active_team_ids
        ]
        if filtered:
            next_category = dict(category)
            next_category["team_ids"] = filtered
            migration_catalog["categories"].append(next_category)
    migration_catalog["counts"] = {
        "selector_teams": len(migration_catalog["teams"]),
        "categories": len(migration_catalog["categories"]),
        "excluded_teams": len(snapshot["excluded_teams"]),
    }
    migration_catalog["content_id"] = content_id(migration_catalog)
    write_json(args.migration_catalog, migration_catalog)
    args.migration_team_include.parent.mkdir(parents=True, exist_ok=True)
    args.migration_team_include.write_text(
        render_team_include(migration_catalog).replace(
            "Generated by tools/generate_exhibition_team_catalog.py.",
            "Generated by tools/pes21_player_migration.py audit.",
            1,
        ),
        encoding="utf-8",
    )
    excluded = collections.Counter(row["reason"] for row in snapshot["excluded_teams"])
    report = {
        "schema_version": 1,
        "result": "pass",
        "migration_build_id": snapshot["migration_build_id"],
        "source_version": snapshot["source_version"],
        "source_lock_sha256": sha256_file(args.work / "source-lock.json"),
        "snapshot_sha256": sha256_file(args.work / "active-snapshot.json"),
        "registry_content_id": registry["content_id"],
        "counts": snapshot["counts"],
        "registry_counts": registry["counts"],
        "change_counts": change_report["counts"],
        "excluded_reasons": dict(sorted(excluded.items())),
        "verified_canary_fields": VERIFIED_CANARY_FIELDS,
        "global_build_blockers": [
            "unverified_full_PES21_field_mapping",
            "hardware_canary_not_signed_off",
        ],
    }
    write_json(args.work / "audit-report.json", report)
    print(json.dumps(report, sort_keys=True))


def registry_map(registry: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {int(row["ef_base_id"]): row for row in registry["players"]}


def patch_verified_player(template: bytes, source: dict[str, Any], native_id: int) -> bytes:
    row = bytearray(template)
    struct.pack_into("<I", row, 8, native_id)
    set_pes21_english_name(row, str(source["Name"]))
    set_pes21_registered_position(row, int(source.get("Position", 0)))

    # These offsets are shared by PESDatabase's PES21 parser/exporter.  They
    # are copied explicitly instead of being inherited from the physical donor
    # row, otherwise a newly allocated player can retain the donor's usable
    # positions and the native game will calculate/select the wrong role.
    for position_name, bit in PES21_POSITION_BITS.items():
        value = min(3, max(0, int(source.get(position_name, 0))))
        write_bits(row, bit, 2, value)
    write_bits(row, 216, 8, min(255, max(0, int(source.get("Height", 170)) - 100)))
    write_bits(row, 256, 7, min(127, max(0, int(source.get("Weight", 70)) - 30)))
    write_bits(row, 408, 6, min(63, max(0, int(source.get("Age", 25)) - 15)))
    write_bits(row, 514, 1, int(bool(source.get("Foot", False))))
    for source_name, bit, width, bias in (
        ("WeakFootUsage", 454, 2, 1),
        ("WeakFootAccuracy", 462, 2, 1),
        ("Form", 438, 3, 1),
        ("InjuryResistance", 458, 2, 1),
        ("Reputation", 451, 3, 1),
        ("PlayingAttitude", 382, 2, 1),
    ):
        value = int(source.get(source_name, bias)) - bias
        write_bits(row, bit, width, min((1 << width) - 1, max(0, value)))
    country = int(source.get("Country", 0)) << 1
    if not 0 <= country < (1 << 10):
        raise ValueError(f"source country code cannot fit PES21: {country}")
    write_bits(row, 232, 10, country)
    for target_name, source_name in SOURCE_TO_PES21_STATS.items():
        value = int(source.get(source_name, 40))
        value = min(99, max(40, value))
        write_bits(row, PES21_ABILITY_BITS[target_name] + 1, 6, value - 40)
    return bytes(row)


def order_canary_rosters(
    canary_teams: list[dict[str, Any]],
    players: dict[int, dict[str, Any]],
    table_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Put a best, position-compatible XI first for every canary team.

    EF assignment PositionId is not a dependable current starting-XI signal
    (Messi is assignment 21 at Inter Miami in eF26 v5.5.1).  PES21 treats the
    first eleven assignment/order entries as starters, so retain the native
    formation roles and solve the XI against authoritative EF26 OVR instead.
    """
    physical_map = {
        int(team["ef_team_id"]): int(team["physical_team_id"])
        for team in canary_teams
    }
    roles_by_physical, source_report = load_tactic_roles(
        table_dir / "Tactics.bin",
        table_dir / "TacticsFormation.bin",
        physical_map,
    )
    ordered_teams: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for team in canary_teams:
        team_copy = dict(team)
        roster = [dict(row) for row in team["roster"]]
        candidates = [
            (
                int(row["base_id"]),
                int(players[int(row["base_id"])]["data"].get("Overall", 40)),
                int(players[int(row["base_id"])]["data"].get("Position", 12)),
            )
            for row in roster
        ]
        roles = roles_by_physical[int(team["physical_team_id"])]
        starting, bench = choose_balanced_xi(candidates, roles)
        order = starting + bench
        team_copy["roster"] = [roster[index] for index in order]
        ordered_teams.append(team_copy)
        reports.append(
            {
                "ef_team_id": int(team["ef_team_id"]),
                "physical_team_id": int(team["physical_team_id"]),
                "formation_roles": roles,
                "starting_base_ids": [candidates[index][0] for index in starting],
                "starting_names": [
                    str(players[candidates[index][0]]["data"]["Name"])
                    for index in starting
                ],
                "starting_overalls": [candidates[index][1] for index in starting],
                "starting_positions": [candidates[index][2] for index in starting],
            }
        )
    return ordered_teams, {"tactics": source_report, "teams": reports}


def encode_fixed_rows(rows: Iterable[bytes]) -> bytes:
    return encode_pes21_wesys(b"".join(rows))


def patch_canary_tables(
    *,
    snapshot: dict[str, Any],
    registry: dict[str, Any],
    canary_teams: list[dict[str, Any]],
    output: Path,
    table_dir: Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    reg = registry_map(registry)
    players = {int(row["base_id"]): row for row in snapshot["players"]}
    base_ids = {
        int(roster["base_id"])
        for team in canary_teams
        for roster in team["roster"]
    }
    rows, by_id = load_player_rows(table_dir / "Player.bin")
    physical_to_base = {
        int(reg[base_id]["physical_source_id"]): base_id
        for base_id in base_ids
    }
    if len(physical_to_base) != len(base_ids):
        raise RuntimeError("canary physical rows are not one-to-one")
    physical_to_native = {
        physical_id: int(reg[base_id]["native_player_id"])
        for physical_id, base_id in physical_to_base.items()
    }
    missing_physical = set(physical_to_base) - set(by_id)
    if missing_physical:
        raise RuntimeError(
            f"canary physical source rows are missing: {sorted(missing_physical)}"
        )
    target_ids = set(physical_to_native.values())
    unchanged_ids = set(by_id) - set(physical_to_base)
    collisions = target_ids & unchanged_ids
    if collisions:
        raise RuntimeError(
            f"canary target IDs collide with retained rows: {sorted(collisions)}"
        )
    patched_players: list[bytes] = []
    for row in rows:
        physical_id = pes21_player_id(row)
        base_id = physical_to_base.get(physical_id)
        if base_id is None:
            patched_players.append(row)
            continue
        patched_players.append(
            patch_verified_player(
                row,
                players[base_id]["data"],
                int(reg[base_id]["native_player_id"]),
            )
        )
    patched_players.sort(key=pes21_player_id)
    result_ids = [pes21_player_id(row) for row in patched_players]
    if len(result_ids) != 43_074 or len(result_ids) != len(set(result_ids)):
        raise RuntimeError("canary Player.bin lost its fixed unique row set")
    if result_ids != sorted(result_ids):
        raise RuntimeError("canary Player.bin is not sorted")

    install_raw = table_raw(table_dir / "InstallVersionPlayer.bin")
    if len(install_raw) % 8:
        raise RuntimeError("InstallVersionPlayer.bin has a partial row")
    install_rows: list[tuple[int, int]] = []
    install_seen: collections.Counter[int] = collections.Counter()
    for offset in range(0, len(install_raw), 8):
        player_id, version = struct.unpack_from("<II", install_raw, offset)
        if player_id in physical_to_native:
            install_seen[player_id] += 1
            player_id = physical_to_native[player_id]
        install_rows.append((player_id, version))
    invalid_install = sorted(
        value for value in physical_to_native if install_seen[value] != 1
    )
    if invalid_install:
        raise RuntimeError(
            "canary donor InstallVersion rows must occur once: "
            f"{invalid_install}"
        )
    install_rows.sort(key=lambda row: (row[1], row[0]))
    install_ids = {row[0] for row in install_rows}
    if install_ids != set(result_ids) or len(install_rows) != len(result_ids):
        raise RuntimeError("Player/InstallVersion ID sets no longer match")

    delete_raw = table_raw(table_dir / "PlayerDeleteList.bin")
    if len(delete_raw) % 4:
        raise RuntimeError("PlayerDeleteList.bin has a partial row")
    retired_ids = set(physical_to_native) | target_ids
    delete_ids = [
        struct.unpack_from("<I", delete_raw, offset)[0]
        for offset in range(0, len(delete_raw), 4)
    ]
    delete_ids = sorted(value for value in delete_ids if value not in retired_ids)

    assignment_raw = table_raw(table_dir / "PlayerAssignment.bin")
    if len(assignment_raw) % 16:
        raise RuntimeError("PlayerAssignment.bin has a partial row")
    assignment_rows = [
        struct.unpack_from("<IIII", assignment_raw, offset)
        for offset in range(0, len(assignment_raw), 16)
    ]
    canary_physical_teams = {
        int(team["physical_team_id"]) for team in canary_teams
    }
    assignment_rows = [
        row for row in assignment_rows if int(row[2]) not in canary_physical_teams
    ]
    next_assignment_id = max(row[0] for row in assignment_rows) + 1
    inserted_assignments = 0
    for team in sorted(canary_teams, key=lambda row: int(row["ef_team_id"])):
        physical_team_id = int(team["physical_team_id"])
        for order, roster in enumerate(team["roster"]):
            native_id = int(reg[int(roster["base_id"])]["native_player_id"])
            shirt = int(roster["shirt_number"]) & 0xFF
            assignment_rows.append(
                (
                    next_assignment_id,
                    native_id,
                    physical_team_id,
                    (order << 8) | shirt,
                )
            )
            next_assignment_id += 1
            inserted_assignments += 1
    if len({row[0] for row in assignment_rows}) != len(assignment_rows):
        raise RuntimeError("PlayerAssignment unique IDs are duplicated")
    invalid_refs = sorted({row[1] for row in assignment_rows} - set(result_ids))
    if invalid_refs:
        raise RuntimeError(
            f"PlayerAssignment references missing players: {invalid_refs[:20]}"
        )

    output.mkdir(parents=True, exist_ok=True)
    files = {
        PLAYER_MEMBER: output / "Player.bin",
        INSTALL_MEMBER: output / "InstallVersionPlayer.bin",
        DELETE_MEMBER: output / "PlayerDeleteList.bin",
        ASSIGNMENT_MEMBER: output / "PlayerAssignment.bin",
    }
    files[PLAYER_MEMBER].write_bytes(encode_fixed_rows(patched_players))
    files[INSTALL_MEMBER].write_bytes(
        encode_fixed_rows(struct.pack("<II", *row) for row in install_rows)
    )
    files[DELETE_MEMBER].write_bytes(
        encode_fixed_rows(struct.pack("<I", value) for value in delete_ids)
    )
    files[ASSIGNMENT_MEMBER].write_bytes(
        encode_fixed_rows(struct.pack("<IIII", *row) for row in assignment_rows)
    )
    report = {
        "player_rows": len(result_ids),
        "players_patched": len(base_ids),
        "physical_rows_renamed": sum(
            physical != native
            for physical, native in physical_to_native.items()
        ),
        "install_id_set_matches": True,
        "delete_rows": len(delete_ids),
        "assignments_inserted": inserted_assignments,
        "assignment_references_valid": True,
        "files": {
            member: {"path": str(path), "sha256": sha256_file(path)}
            for member, path in files.items()
        },
    }
    return files, report


def write_canary_roster_include(
    path: Path,
    canary_teams: list[dict[str, Any]],
    registry: dict[str, Any],
    players_by_base: dict[int, dict[str, Any]],
    migration_build_id: str,
) -> None:
    reg = registry_map(registry)
    lines = [
        "// Generated by tools/pes21_player_migration.py canary.",
        f"// Migration build ID: {migration_build_id}",
        "// Do not edit manually.",
        "",
        f'#define PES21_PLAYER_MIGRATION_BUILD_ID "{migration_build_id}"',
        "",
    ]
    ratings: list[tuple[int, int, int]] = []
    for team in sorted(canary_teams, key=lambda row: int(row["ef_team_id"])):
        team_id = int(team["ef_team_id"])
        native_players = [
            int(reg[int(row["base_id"])]["native_player_id"])
            for row in team["roster"]
        ]
        shirts = [int(row["shirt_number"]) & 0xFF for row in team["roster"]]
        lines.append(
            f"static const uint32_t exhibition_migration_team_{team_id}_players[] = {{"
        )
        for start in range(0, len(native_players), 8):
            lines.append(
                "    "
                + " ".join(
                    f"{value}u," for value in native_players[start : start + 8]
                )
            )
        lines.append("};")
        lines.append(
            f"static const uint8_t exhibition_migration_team_{team_id}_shirts[] = {{"
        )
        for start in range(0, len(shirts), 12):
            lines.append(
                "    " + " ".join(f"{value}," for value in shirts[start : start + 12])
            )
        lines.extend(["};", ""])
        ratings.extend(
            (
                int(reg[int(row["base_id"])]["native_player_id"]),
                min(99, max(40, int(players_by_base[int(row["base_id"])]["data"].get("Overall", 40)))),
                min(12, max(0, int(players_by_base[int(row["base_id"])]["data"].get("Position", 12)))),
            )
            for row in team["roster"]
        )
    ratings = sorted(set(ratings))
    lines.append(
        "static const ExhibitionMigrationPlayerRating "
        "exhibition_player_migration_canary_ratings[] = {"
    )
    lines.extend(
        f"    {{{native_id}u, {overall}, {position}}},"
        for native_id, overall, position in ratings
    )
    lines.extend(["};", ""])
    lines.append(
        "static const ExhibitionMasterRoster "
        "exhibition_player_migration_canary_rosters[] = {"
    )
    for team in sorted(canary_teams, key=lambda row: int(row["ef_team_id"])):
        team_id = int(team["ef_team_id"])
        lines.extend(
            [
                "    {",
                f"        {team_id}u,",
                f"        exhibition_migration_team_{team_id}_players,",
                f"        exhibition_migration_team_{team_id}_shirts,",
                f"        sizeof(exhibition_migration_team_{team_id}_players) /",
                f"            sizeof(exhibition_migration_team_{team_id}_players[0]),",
                "    },",
            ]
        )
    lines.extend(["};", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def load_pesdb_module(tools: Path):
    module_path = tools / "pesdb_efootball.py"
    spec = importlib.util.spec_from_file_location("migration_pesdb_efootball", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def neutral_portrait(path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((45, 18, 83, 56), fill=(175, 180, 190, 230))
    draw.rounded_rectangle((31, 55, 97, 121), radius=25, fill=(125, 132, 145, 230))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def run_checked(command: list[str]) -> None:
    completed = subprocess.run(command, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}\n{completed.stderr}"
        )


def canary_command(args: argparse.Namespace) -> None:
    snapshot = read_json(args.work / "active-snapshot.json")
    registry = read_json(args.registry)
    config = read_json(args.config)
    reg = registry_map(registry)
    players = {int(row["base_id"]): row for row in snapshot["players"]}
    canary_team_ids = {int(value) for value in config["canary_team_ids"]}
    canary_teams = [
        row for row in snapshot["teams"] if int(row["ef_team_id"]) in canary_team_ids
    ]
    if {int(row["ef_team_id"]) for row in canary_teams} != canary_team_ids:
        raise RuntimeError("one or more configured canary teams are not active")
    canary_teams, lineup_report = order_canary_rosters(
        canary_teams,
        players,
        args.work / "base" / "tables",
    )
    canary_base_ids = {
        int(roster["base_id"])
        for team in canary_teams
        for roster in team["roster"]
    }
    required = {int(value) for value in config["required_canary_base_ids"]}
    if not required.issubset(canary_base_ids):
        raise RuntimeError(f"canary roster is missing required BaseIds: {sorted(required-canary_base_ids)}")
    identity_sentinels: list[dict[str, Any]] = []
    for base_id in (4522, 7511, 57304):
        row = reg[base_id]
        owners = (
            int(row["native_player_id"]),
            int(row["face_owner_id"] or 0),
            int(row["commentary_owner_id"] or 0),
        )
        if owners != (base_id, base_id, base_id):
            raise RuntimeError(
                f"protected identity {base_id} lost native/face/commentary ownership: "
                f"{owners}"
            )
        identity_sentinels.append(
            {
                "base_id": base_id,
                "name": str(row["canonical_name"]),
                "native_player_id": owners[0],
                "face_owner_id": owners[1],
                "commentary_owner_id": owners[2],
            }
        )
    manifest = {
        "schema_version": 1,
        "migration_build_id": snapshot["migration_build_id"],
        "source_version": snapshot["source_version"],
        "team_ids": sorted(canary_team_ids),
        "base_ids": sorted(canary_base_ids),
        "players": [reg[value] for value in sorted(canary_base_ids)],
        "identity_sentinels": identity_sentinels,
        "verified_fields": VERIFIED_CANARY_FIELDS,
        "lineups": lineup_report,
    }
    manifest["content_id"] = content_id(manifest)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "canary-manifest.json", manifest)
    write_canary_roster_include(
        args.canary_roster_include,
        canary_teams,
        registry,
        players,
        snapshot["migration_build_id"],
    )

    if not args.package:
        print(json.dumps({"result": "manifest", "output": str(output), "players": len(canary_base_ids)}))
        return

    table_files, table_report = patch_canary_tables(
        snapshot=snapshot,
        registry=registry,
        canary_teams=canary_teams,
        output=output / "tables",
        table_dir=args.work / "base" / "tables",
    )
    write_json(output / "table-report.json", table_report)

    portrait_dir = output / "portraits"
    portrait_dir.mkdir(exist_ok=True)
    pesdb_module = load_pesdb_module(args.pesdb_tools)
    portrait_rows: list[dict[str, Any]] = []
    previous_portrait_report = output / "portrait-report.json"
    previous_portraits = {}
    if previous_portrait_report.is_file():
        previous_portraits = {
            int(row["base_id"]): row
            for row in read_json(previous_portrait_report).get("portraits", [])
        }
    placeholder = output / "neutral-player.png"
    neutral_portrait(placeholder)
    for base_id in sorted(canary_base_ids):
        source = players[base_id]["data"]
        native_id = int(reg[base_id]["native_player_id"])
        raw = portrait_dir / f"{native_id}.raw.png"
        normalized = portrait_dir / f"{native_id}.png"
        downloaded = None
        previous_portrait = previous_portraits.get(base_id)
        cache_valid = (
            normalized.is_file()
            and previous_portrait is not None
            and int(previous_portrait["source_card_id"]) == int(source["Id"])
            and int(previous_portrait["native_player_id"]) == native_id
            and previous_portrait.get("sha256") == sha256_file(normalized)
        )
        if cache_valid:
            status = str(previous_portrait["status"])
        elif not args.no_portraits:
            downloaded = pesdb_module.PesDb.download_portrait(
                int(source["Id"]), raw, base_id
            )
        if not cache_valid and downloaded:
            normalize_portrait(raw, normalized)
            status = "downloaded"
        elif not cache_valid:
            shutil.copyfile(placeholder, normalized)
            status = "neutral_placeholder"
        raw.unlink(missing_ok=True)
        portrait_rows.append(
            {
                "base_id": base_id,
                "source_card_id": int(source["Id"]),
                "native_player_id": native_id,
                "status": status,
                "sha256": sha256_file(normalized),
            }
        )
    write_json(output / "portrait-report.json", {"portraits": portrait_rows})

    base_dt200 = args.work / "base" / "dt200_mobile_all.cpk"
    base_dt241 = args.work / "base" / "dt241_mobile_all.cpk"
    dt200 = output / "dt200_mobile_all.cpk"
    dt200.unlink(missing_ok=True)
    table_replacements = output / "table-replacements.json"
    write_json(
        table_replacements,
        {member: str(path) for member, path in table_files.items()},
    )
    run_checked(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(base_dt200),
            str(dt200),
            "--replace-manifest",
            str(table_replacements),
        ]
    )

    _header, portrait_members, _base = cpk_index(base_dt241)
    replacements: dict[str, str] = {}
    additions: dict[str, str] = {}
    for row in portrait_rows:
        member = f"common/player/{row['native_player_id']}.png"
        path = portrait_dir / f"{row['native_player_id']}.png"
        (replacements if member in portrait_members else additions)[member] = str(path)
    replacement_manifest = output / "portrait-replacements.json"
    write_json(replacement_manifest, replacements)
    replaced_dt241 = output / "dt241-replaced.cpk"
    replaced_dt241.unlink(missing_ok=True)
    if replacements:
        run_checked(
            [
                sys.executable,
                str(ROOT / "tools" / "repack_cpk_members.py"),
                str(base_dt241),
                str(replaced_dt241),
                "--replace-manifest",
                str(replacement_manifest),
            ]
        )
    else:
        shutil.copyfile(base_dt241, replaced_dt241)
    dt241 = output / "dt241_mobile_all.cpk"
    dt241.unlink(missing_ok=True)
    if additions:
        command = [
            sys.executable,
            str(ROOT / "tools" / "add_cpk_members_canary.py"),
            str(replaced_dt241),
            str(dt241),
        ]
        for member, path in sorted(additions.items()):
            command.extend(["--add", f"{member}={path}"])
        run_checked(command)
    else:
        shutil.copyfile(replaced_dt241, dt241)

    canary_obb = output / args.obb.name
    canary_obb.unlink(missing_ok=True)
    outer_manifest = output / "outer-replacements.json"
    write_json(
        outer_manifest,
        {DT200_MEMBER: str(dt200), DT241_MEMBER: str(dt241)},
    )
    run_checked(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(args.obb),
            str(canary_obb),
            "--replace-manifest",
            str(outer_manifest),
        ]
    )
    if not args.skip_nro_build:
        run_checked(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "build-wsl.ps1"),
                "-OutputDirectory",
                str(output.relative_to(ROOT)),
                "-ExpectedPatchObbSize",
                str(canary_obb.stat().st_size),
                "-DisablePesdbAuthoritativeOvr",
                "-PlayerMigrationCanary",
            ]
        )
    canary_nro = output / "pes21_nx.nro"
    if not canary_nro.is_file():
        raise RuntimeError(f"canary NRO was not built: {canary_nro}")
    report = {
        "schema_version": 1,
        "result": "awaiting_hardware_validation",
        "migration_build_id": snapshot["migration_build_id"],
        "canary_content_id": manifest["content_id"],
        "obb": {"path": str(canary_obb), "sha256": sha256_file(canary_obb)},
        "compatible_nro": {
            "path": str(canary_nro),
            "sha256": sha256_file(canary_nro),
        },
        "players": len(canary_base_ids),
        "tables": table_report,
        "lineups": lineup_report,
        "portrait_replacements": len(replacements),
        "portrait_additions": len(additions),
        "portrait_downloaded": sum(
            row["status"] == "downloaded" for row in portrait_rows
        ),
        "portrait_placeholders": sum(
            row["status"] == "neutral_placeholder" for row in portrait_rows
        ),
        "missing_portrait_base_ids": [
            row["base_id"]
            for row in portrait_rows
            if row["status"] == "neutral_placeholder"
        ],
        "hardware_checks": [
            "startup_branding_and_native_team_assets_match_v4",
            "gameplan_opens_without_crash",
            "inter_miami_starts_messi_82_and_suarez",
            "barcelona_starts_lamine_yamal_80",
            "match_player_name_matches_selected_gameplan_player",
            "portrait_identity_is_correct",
            "club_national_overlap_is_deduplicated",
            "messi_ronaldo_commentary_is_correct",
            "mane_and_yamal_identity_is_correct",
            "repeated_matches_are_stable",
        ],
    }
    write_json(output / "hardware-canary-report.json", report)
    print(json.dumps(report, sort_keys=True))


def build_command(args: argparse.Namespace) -> None:
    report = read_json(args.hardware_report)
    if report.get("result") != "hardware_pass":
        raise RuntimeError(
            "global build is intentionally blocked until the canary report "
            "has result=hardware_pass"
        )
    audit = read_json(args.work / "audit-report.json")
    blockers = set(audit.get("global_build_blockers", []))
    blockers.discard("hardware_canary_not_signed_off")
    if blockers:
        raise RuntimeError(
            "global build remains blocked: " + ", ".join(sorted(blockers))
        )
    raise RuntimeError("global build gate unexpectedly has no implementation blocker")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    result.add_argument("--pesdb-tools", type=Path, default=DEFAULT_PESDB_TOOLS)
    result.add_argument("--obb", type=Path, default=DEFAULT_OBB)
    result.add_argument("--nro", type=Path, default=DEFAULT_NRO)
    result.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    result.add_argument(
        "--migration-catalog", type=Path, default=DEFAULT_MIGRATION_CATALOG
    )
    result.add_argument(
        "--migration-team-include",
        type=Path,
        default=DEFAULT_MIGRATION_TEAM_INCLUDE,
    )
    result.add_argument(
        "--canary-roster-include",
        type=Path,
        default=DEFAULT_CANARY_ROSTER_INCLUDE,
    )
    result.add_argument("--base-pak", type=Path, default=DEFAULT_BASE_PAK)
    result.add_argument("--repak", type=Path, default=DEFAULT_REPAK)
    result.add_argument("--work", type=Path)
    sub = result.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--no-pull-appearance", action="store_true")
    sub.add_parser("audit")
    canary = sub.add_parser("canary")
    canary.add_argument("--output", type=Path, default=ROOT / "local-debug" / "pes21-player-migration-canary")
    canary.add_argument("--package", action="store_true")
    canary.add_argument("--no-portraits", action="store_true")
    canary.add_argument("--skip-nro-build", action="store_true")
    build = sub.add_parser("build")
    build.add_argument("--hardware-report", type=Path, required=True)
    return result


def main() -> None:
    args = parser().parse_args()
    args.config = args.config.resolve()
    args.catalog = args.catalog.resolve()
    args.pesdb_tools = args.pesdb_tools.resolve()
    args.obb = args.obb.resolve()
    args.nro = args.nro.resolve()
    args.registry = args.registry.resolve()
    args.migration_catalog = args.migration_catalog.resolve()
    args.migration_team_include = args.migration_team_include.resolve()
    args.canary_roster_include = args.canary_roster_include.resolve()
    args.base_pak = args.base_pak.resolve()
    args.repak = args.repak.resolve()
    config = read_json(args.config)
    args.work = (
        args.work.resolve()
        if args.work is not None
        else ROOT / "local-inputs" / "pes21-player-migration" / str(config["source_version"])
    )
    if hasattr(args, "output"):
        args.output = args.output.resolve()
    if hasattr(args, "hardware_report"):
        args.hardware_report = args.hardware_report.resolve()
    commands = {
        "sync": sync_command,
        "audit": audit_command,
        "canary": canary_command,
        "build": build_command,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
