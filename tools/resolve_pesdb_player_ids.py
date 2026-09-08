#!/usr/bin/env python3
"""Resolve legacy EF10 player identities against the current PESDB catalog.

EF10 player IDs are not guaranteed to be current eFootball IDs.  This tool
therefore creates an explicit ``EF10 source -> PESDB player`` map before any
network fetch or Player.bin patch.  Exact-name candidates are reported but are
not accepted by default; a release map must be reviewed with
``--accept-exact-name`` (and ambiguous/missing rows always remain blocked).

PES21 is intentionally absent from this resolver.  It is only a later target
format/slot inventory, never an identity or value source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pesdb import decode_wesys, parse_ef10_assignments, parse_player_records


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EF10_DIR = Path("local-debug/efootball10-audit/tables/common/etc/pesdb")
DEFAULT_SITEMAP = Path("local-debug/pesdb-efootball-cache/sitemap.json")
DEFAULT_OUTPUT = Path("local-debug/pesdb-efootball-identity-map.json")


def normalize_name(value: str) -> str:
    """Normalize accents, punctuation, and repeated whitespace for matching."""
    value = value.translate(
        str.maketrans(
            {
                "ı": "i", "İ": "I", "ł": "l", "Ł": "L",
                "ø": "o", "Ø": "O", "đ": "d", "Đ": "D",
                "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th",
                "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
            }
        )
    )
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def sitemap_slug_name(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"-\d+$", "", slug)
    return slug.replace("-", " ")


def same_name_tokens(left: str, right: str) -> bool:
    """Treat PESDB surname-first display order as the same identity."""
    return sorted(normalize_name(left).split()) == sorted(normalize_name(right).split())


def load_sitemap_players(path: Path) -> dict[int, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    players = payload.get("players")
    if not isinstance(players, dict):
        raise ValueError(f"{path}: sitemap players must be an object")
    result: dict[int, str] = {}
    for raw_id, raw_url in players.items():
        player_id = int(raw_id)
        if player_id <= 0 or not isinstance(raw_url, str) or not raw_url:
            continue
        result[player_id] = raw_url
    return result


def assigned_player_ids(ef10_dir: Path, team_ids: set[int] | None = None) -> list[int]:
    assignments = parse_ef10_assignments(
        decode_wesys(ef10_dir / "PlayerAssignment.bin")
    )
    selected = assignments
    if team_ids is not None:
        selected = {team_id: assignments.get(team_id, []) for team_id in team_ids}
    return sorted({int(row.player_id) for rows in selected.values() for row in rows})


def source_ids_from_file(path: Path) -> list[int]:
    """Read IDs from a conversion report/map or a plain numeric text file."""
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        players = payload.get("players") if isinstance(payload, dict) else None
        if isinstance(players, list):
            values = [
                int(row["ef10_player_id"])
                for row in players
                if isinstance(row, dict) and row.get("ef10_player_id") is not None
            ]
            if values:
                return values
        raw_map = payload.get("map") if isinstance(payload, dict) else None
        if isinstance(raw_map, dict):
            return [int(value) for value in raw_map]
        raise ValueError(f"{path}: no EF10 player IDs found in JSON")
    return [
        int(value)
        for value in re.findall(r"\d+", path.read_text(encoding="utf-8"))
    ]


def resolve_identities(
    ef10_players: dict[int, Any],
    sitemap_players: dict[int, str],
    source_ids: list[int],
    *,
    accept_exact_name: bool = False,
    accept_id_name_mismatch: bool = False,
) -> dict[str, Any]:
    by_name: dict[str, list[int]] = {}
    for player_id, url in sitemap_players.items():
        by_name.setdefault(normalize_name(sitemap_slug_name(url)), []).append(player_id)
    for values in by_name.values():
        values.sort()

    rows: list[dict[str, Any]] = []
    accepted: dict[int, int] = {}
    for source_id in sorted(set(int(value) for value in source_ids if int(value) > 0)):
        source = ef10_players.get(source_id)
        if source is None:
            rows.append({
                "ef10_player_id": source_id,
                "status": "source_missing",
                "reason": "EF10 Player.bin has no row",
            })
            continue
        source_name = str(source.name)
        source_key = normalize_name(source_name)
        direct_url = sitemap_players.get(source_id)
        direct_name = sitemap_slug_name(direct_url) if direct_url else None
        direct_key = normalize_name(direct_name or "")
        if direct_url and direct_key == source_key:
            accepted[source_id] = source_id
            rows.append({
                "ef10_player_id": source_id,
                "ef10_name": source_name,
                "pesdb_player_id": source_id,
                "pesdb_name": direct_name,
                "status": "direct_id_exact",
                "confidence": "high",
            })
            continue
        if direct_url and same_name_tokens(source_name, direct_name or ""):
            accepted[source_id] = source_id
            rows.append({
                "ef10_player_id": source_id,
                "ef10_name": source_name,
                "pesdb_player_id": source_id,
                "pesdb_name": direct_name,
                "status": "direct_id_reordered_name",
                "confidence": "high",
            })
            continue
        if direct_url and direct_key != source_key:
            accepted_direct = bool(accept_id_name_mismatch)
            if accepted_direct:
                accepted[source_id] = source_id
            rows.append({
                "ef10_player_id": source_id,
                "ef10_name": source_name,
                "pesdb_player_id": source_id,
                "pesdb_name": direct_name,
                "status": "direct_id_name_mismatch",
                "confidence": "review",
                "accepted": accepted_direct,
            })
            continue
        candidates = by_name.get(source_key, [])
        if len(candidates) == 1:
            remote_id = candidates[0]
            accepted_candidate = bool(accept_exact_name)
            if accepted_candidate:
                if remote_id in accepted.values():
                    raise ValueError(
                        f"multiple EF10 players resolve to PESDB player {remote_id}"
                    )
                accepted[source_id] = remote_id
            rows.append({
                "ef10_player_id": source_id,
                "ef10_name": source_name,
                "pesdb_player_id": remote_id,
                "pesdb_name": sitemap_slug_name(sitemap_players[remote_id]),
                "status": "exact_name_unique",
                "confidence": "medium",
                "accepted": accepted_candidate,
            })
        elif candidates:
            rows.append({
                "ef10_player_id": source_id,
                "ef10_name": source_name,
                "status": "ambiguous_name",
                "confidence": "review",
                "candidates": candidates,
                "candidate_names": [sitemap_slug_name(sitemap_players[item]) for item in candidates],
            })
        else:
            rows.append({
                "ef10_player_id": source_id,
                "ef10_name": source_name,
                "status": "unresolved",
                "confidence": "none",
            })

    counts = {
        "requested": len(rows),
        "accepted": len(accepted),
        "direct_id_exact": sum(row.get("status") == "direct_id_exact" for row in rows),
        "direct_id_reordered_name": sum(
            row.get("status") == "direct_id_reordered_name" for row in rows
        ),
        "direct_id_name_mismatch": sum(row.get("status") == "direct_id_name_mismatch" for row in rows),
        "exact_name_unique": sum(row.get("status") == "exact_name_unique" for row in rows),
        "ambiguous_name": sum(row.get("status") == "ambiguous_name" for row in rows),
        "unresolved": sum(row.get("status") == "unresolved" for row in rows),
        "source_missing": sum(row.get("status") == "source_missing" for row in rows),
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "authority": "https://pesdb.net/efootball",
        "policy": {
            "pesdb_only": True,
            "pes21_values_allowed": False,
            "exact_name_requires_review": not accept_exact_name,
            "ambiguous_and_unresolved_block_release": True,
        },
        "counts": counts,
        "map": {str(source): target for source, target in sorted(accepted.items())},
        "rows": rows,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    payload["content_id"] = hashlib.sha256(canonical).hexdigest()[:16]
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ef10-dir", type=Path, default=DEFAULT_EF10_DIR)
    parser.add_argument("--sitemap", type=Path, default=DEFAULT_SITEMAP)
    parser.add_argument("--ids-file", action="append", type=Path)
    parser.add_argument("--team-id", action="append", type=int)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--accept-exact-name", action="store_true")
    parser.add_argument("--accept-id-name-mismatch", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    ef10_dir = args.ef10_dir if args.ef10_dir.is_absolute() else root / args.ef10_dir
    sitemap_path = args.sitemap if args.sitemap.is_absolute() else root / args.sitemap
    ef10_players = parse_player_records(
        decode_wesys(ef10_dir / "Player.bin"), "ef10"
    )
    if args.ids_file:
        source_ids = []
        for value in args.ids_file:
            ids_path = value if value.is_absolute() else root / value
            source_ids.extend(source_ids_from_file(ids_path))
    else:
        source_ids = assigned_player_ids(ef10_dir, set(args.team_id) if args.team_id else None)
    payload = resolve_identities(
        ef10_players,
        load_sitemap_players(sitemap_path),
        source_ids,
        accept_exact_name=args.accept_exact_name,
        accept_id_name_mismatch=args.accept_id_name_mismatch,
    )
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], sort_keys=True))
    if args.require_complete and payload["counts"]["accepted"] != payload["counts"]["requested"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
