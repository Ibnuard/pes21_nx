#!/usr/bin/env python3
"""Fetch PESDB rows for an explicit EF10-to-PESDB identity map.

``import_pesdb_efootball.py`` is intentionally ID-oriented.  This wrapper
handles the older EF10 IDs that were resolved by
``resolve_pesdb_player_ids.py`` and re-keys the resulting snapshot by EF10
source ID.  Each row retains ``pesdb_player_id`` so provenance is auditable.
No PES21 value is consulted or generated here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from import_pesdb_efootball import (
    DEFAULT_CACHE,
    DEFAULT_SITEMAP,
    build_snapshot,
    canonical_content_id,
    load_sitemap_index,
    write_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IDENTITY_MAP = Path("local-debug/pesdb-efootball-identity-map.json")
DEFAULT_SNAPSHOT = Path("local-debug/pesdb-efootball-identity-snapshot.json")


def load_identity_map(path: Path) -> dict[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("map", payload)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: map must be an object")
    result = {int(source): int(target) for source, target in raw.items()}
    if any(source <= 0 or target <= 0 for source, target in result.items()):
        raise ValueError(f"{path}: IDs must be positive")
    if len(result) != len(set(result.values())):
        raise ValueError(f"{path}: multiple EF10 IDs map to one PESDB ID")
    return result


def rekey_snapshot(
    identity_map: dict[int, int],
    fetched: dict[str, Any],
) -> dict[str, Any]:
    players: dict[str, dict[str, Any]] = {}
    failures: dict[str, str] = {}
    raw_players = fetched.get("players", {})
    raw_failures = fetched.get("failures", {})
    reverse = {remote: source for source, remote in identity_map.items()}
    for remote_key, row in raw_players.items():
        remote_id = int(remote_key)
        source_id = reverse.get(remote_id)
        if source_id is None:
            continue
        copied = dict(row)
        copied["player_id"] = source_id
        copied["source_player_id"] = source_id
        copied["pesdb_player_id"] = remote_id
        copied["identity_source"] = "explicit_ef10_to_pesdb_map"
        players[str(source_id)] = copied
    for remote_key, reason in raw_failures.items():
        remote_id = int(remote_key)
        source_id = reverse.get(remote_id)
        if source_id is not None:
            failures[str(source_id)] = str(reason)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/import_pesdb_identity_map.py",
        "source": "authentic",
        "authority": "https://pesdb.net/efootball",
        "identity_map": {str(source): remote for source, remote in sorted(identity_map.items())},
        "requested_player_ids": sorted(identity_map),
        "players": {key: players[key] for key in sorted(players, key=int)},
        "failures": {key: failures[key] for key in sorted(failures, key=int)},
        "counts": {
            "requested": len(identity_map),
            "fetched": len(players),
            "failed": len(failures),
            "verified_ability_rows": sum(
                isinstance(row.get("base_stats"), dict)
                for row in players.values()
            ),
        },
    }
    payload["content_id"] = canonical_content_id(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--identity-map", type=Path, default=DEFAULT_IDENTITY_MAP)
    parser.add_argument("--sitemap-url", default=DEFAULT_SITEMAP)
    parser.add_argument("--sitemap-cache", type=Path, default=DEFAULT_CACHE / "sitemap.json")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh-sitemap", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    def resolve(path: Path) -> Path:
        return path.resolve() if path.is_absolute() else root / path
    identity_map = load_identity_map(resolve(args.identity_map))
    sitemap = load_sitemap_index(
        resolve(args.sitemap_cache),
        sitemap_url=args.sitemap_url,
        refresh=args.refresh_sitemap,
    )
    remote_ids = sorted(set(identity_map.values()))
    fetched = build_snapshot(
        remote_ids,
        standard_urls=sitemap,
        source="authentic",
        cache_dir=resolve(args.cache_dir),
        workers=args.workers,
        retries=args.retries,
        timeout=args.timeout,
        delay=args.delay,
        offline=args.offline,
    )
    payload = rekey_snapshot(identity_map, fetched)
    output = resolve(args.snapshot)
    write_snapshot(output, payload, check=args.check)
    print(json.dumps(payload["counts"], sort_keys=True))
    if args.require_complete and payload["counts"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
