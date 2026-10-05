#!/usr/bin/env python3
"""Collect playable-team snapshots, then reconcile transfers against local IDs.

This is deliberately separate from the legacy formation-only importer. Raw web
responses and candidate databases belong in ignored local directories, not Git.
No command in this tool overwrites the active runtime or the source database.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from import_team_tactics import convert_team


ROOT = Path(__file__).resolve().parents[1]
API = "https://api.efootballdb.com/api/2022/teams/"
PLAYER_API = "https://api.efootballdb.com/api/2022/players/"
GENERATOR = "tools/sync_efootballdb_rosters.py"
RETIRED_CATEGORIES = frozenset({
    "belgian_league", "swiss_league", "other_europe", "brazil_serie_b",
    "colombian_league", "j2_league",
})


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(json_bytes(value))
    temporary.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_output(path: Path) -> Path:
    resolved = path.resolve()
    if not any((ROOT / part).resolve() in resolved.parents
               for part in ("local-inputs", "local-debug")):
        raise ValueError("output must be below local-inputs/ or local-debug/")
    return resolved


def playable_teams(catalog: dict) -> dict[int, dict]:
    """The curated selector, never the old master table, defines the scope."""
    categories = catalog["categories"]
    if RETIRED_CATEGORIES.intersection(row["key"] for row in categories):
        raise ValueError("catalog still contains retired selector categories")
    ids = [int(value) for category in categories for value in category["team_ids"]]
    rows = catalog["teams"]
    result = {int(row["team_id"]): row for row in rows}
    if len(ids) != len(set(ids)) or len(result) != len(rows) or set(ids) != set(result):
        raise ValueError("selector categories and team records are not one-to-one")
    physical = [int(row["physical_team_id"]) for row in rows]
    if len(physical) != len(set(physical)):
        raise ValueError("two playable teams share a native team slot")
    for category in categories:
        for team_id in category["team_ids"]:
            if result[int(team_id)]["category"] != category["key"]:
                raise ValueError("team category mismatch")
    if not result:
        raise ValueError("empty playable scope")
    return result


def normalize_player(player: dict) -> dict:
    national = player.get("nationality_a")
    # Spain is nationality row 57, but its PESDB country_id is 236.
    country = national.get("country_id") if isinstance(national, dict) else national
    return {
        "base_id": int(player["base_pes_id"]), "card_id": int(player["pes_id"]),
        "name": player["player_name"],
        "country": int(country) if country is not None else None,
        "height": int(player["height"]), "age": int(player["age"]),
        "foot": int(player["strong_foot"]), "position": int(player["main_position"]),
    }


def normalize_team(payload: dict, expected: dict) -> dict:
    team = payload["data"]
    team_id = int(team["pes_id"])
    if team_id != int(expected["team_id"]):
        raise ValueError("API response belongs to another team")
    kind = "national" if int(team["is_national_team"]) else "club"
    if kind != expected["kind"]:
        raise ValueError("API team kind differs from the local identity")
    members = []
    for assignment in team["player_assignments"]:
        player = assignment["player"]
        members.append({
            **normalize_player(player),
            "order": int(assignment["order_number"]),
            "shirt_number": int(assignment["shirt_number"]),
            "captain": int(assignment.get("captain", 0)),
        })
    members.sort(key=lambda row: (row["order"], row["base_id"]))
    problems = []
    if not 18 <= len(members) <= 40:
        problems.append(f"roster_count:{len(members)}")
    if len({row["base_id"] for row in members}) != len(members):
        problems.append("duplicate_base_id")
    if [row["order"] for row in members] != list(range(len(members))):
        problems.append("non_contiguous_assignment_order")
    if any(row["base_id"] <= 0 or not row["name"] for row in members):
        problems.append("missing_identity")
    if any(not 0 <= row["shirt_number"] <= 255 for row in members):
        problems.append("shirt_number_out_of_range")
    if any(row["captain"] not in (0, 1) for row in members):
        problems.append("invalid_captain")
    strategies = []
    try:
        tactics = convert_team(payload)
        strategies = tactics["strategies"]
        if len({row["strategy"] for row in strategies}) != len(strategies):
            problems.append("duplicate_strategy")
    except (KeyError, TypeError, ValueError) as error:
        problems.append(f"invalid_tactics:{error}")
    return {
        "team_id": team_id, "physical_team_id": int(expected["physical_team_id"]),
        "local_name": expected["display_name"], "name": team["english_name"],
        "kind": kind, "category": expected["category"], "members": members,
        "strategies": strategies, "problems": problems,
    }


def fetch_json(url: str, retries: int = 3) -> tuple[bytes, dict]:
    for attempt in range(retries):
        try:
            request = Request(url, headers={
                "User-Agent": "FootballNX-RosterSync/1.0",
                "Accept": "application/json",
            })
            with urlopen(request, timeout=30) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
                headers = {key: response.headers.get(key)
                           for key in ("ETag", "Last-Modified", "Date")}
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError("unexpectedly large team response")
            return raw, {"url": url, "fetched_at": now(), "headers": headers}
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt + 1 == retries:
                raise
            delay = 2 ** attempt
            if isinstance(error, HTTPError) and error.code == 429:
                retry_after = error.headers.get("Retry-After", "30")
                delay = max(delay, int(retry_after) if retry_after.isdigit() else 30)
            time.sleep(min(delay, 60))
    raise RuntimeError("unreachable fetch retry state")


def fetch_team(team_id: int, retries: int = 3) -> tuple[bytes, dict]:
    return fetch_json(API + str(team_id), retries)


def cached_team(folder: Path, team_id: int, entry: dict) -> bytes:
    # Never follow response-provided paths or a mutable manifest path field.
    raw = gzip.decompress((folder / "raw" / f"{team_id}.json.gz").read_bytes())
    if digest(raw) != entry["sha256"]:
        raise ValueError(f"cached API response checksum mismatch: {team_id}")
    return raw


def load_collection(folder: Path, require_complete: bool = True) -> tuple[dict, dict, dict]:
    manifest = read_json(folder / "collection.json")
    catalog_raw = (folder / "catalog.json").read_bytes()
    if manifest.get("generator") != GENERATOR or digest(catalog_raw) != manifest["catalog_sha256"]:
        raise ValueError("collection provenance mismatch")
    catalog = json.loads(catalog_raw)
    scope = playable_teams(catalog)
    if manifest["requested_team_ids"] != sorted(scope):
        raise ValueError("collection scope differs from the locked selector")
    if require_complete and (manifest.get("errors") or
                             set(map(int, manifest["teams"])) != set(scope)):
        raise ValueError("collect ALL playable teams before planning any transfers")
    teams = {}
    for key, entry in manifest["teams"].items():
        team_id = int(key)
        teams[team_id] = normalize_team(
            json.loads(cached_team(folder, team_id, entry)), scope[team_id])
    return manifest, catalog, teams


def collect(args: argparse.Namespace) -> None:
    folder = local_output(args.output)
    catalog = read_json(args.catalog)
    scope = playable_teams(catalog)
    catalog_raw = json_bytes(catalog)
    if args.resume:
        manifest, _old_catalog, _teams = load_collection(folder, require_complete=False)
        if manifest["catalog_sha256"] != digest(catalog_raw):
            raise ValueError("cannot resume a different playable scope")
        started = datetime.fromisoformat(manifest["started_at"])
        if (datetime.now(timezone.utc) - started).total_seconds() > 24 * 3600:
            raise ValueError("snapshot collection is over 24 hours old; start a new snapshot")
    else:
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "raw").mkdir()
        (folder / "catalog.json").write_bytes(catalog_raw)
        manifest = {
            "schema_version": 1, "generator": GENERATOR,
            "started_at": now(), "source": API,
            "source_version": "live_unversioned_api",
            "catalog_sha256": digest(catalog_raw),
            "catalog_content_id": catalog.get("content_id"),
            "requested_team_ids": sorted(scope), "teams": {}, "errors": {},
        }
        write_json(folder / "collection.json", manifest)
    pending = sorted(set(scope) - set(map(int, manifest["teams"])))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(fetch_team, team_id, args.retries): team_id
                   for team_id in pending}
        for future in concurrent.futures.as_completed(futures):
            team_id = futures[future]
            try:
                raw, provenance = future.result()
                normalized = normalize_team(json.loads(raw), scope[team_id])
                (folder / "raw" / f"{team_id}.json.gz").write_bytes(
                    gzip.compress(raw, mtime=0))
                manifest["teams"][str(team_id)] = {
                    **provenance, "sha256": digest(raw), "bytes": len(raw),
                    "name": normalized["name"], "members": len(normalized["members"]),
                    "problems": normalized["problems"],
                }
                manifest["errors"].pop(str(team_id), None)
            except Exception as error:
                manifest["errors"][str(team_id)] = str(error)
            manifest["finished_at"] = now()
            write_json(folder / "collection.json", manifest)
            done = len(manifest["teams"]) + len(manifest["errors"])
            if done % 25 == 0 or done == len(scope):
                print(f"Collected {len(manifest['teams'])}/{len(scope)}; "
                      f"errors={len(manifest['errors'])}", flush=True)
    manifest["complete"] = not manifest["errors"] and len(manifest["teams"]) == len(scope)
    manifest["snapshot_id"] = digest(json_bytes({
        "catalog": manifest["catalog_sha256"],
        "teams": {key: row["sha256"] for key, row in manifest["teams"].items()},
    }))[:16]
    write_json(folder / "collection.json", manifest)
    print(json.dumps({"snapshot_id": manifest["snapshot_id"],
                      "complete": manifest["complete"],
                      "teams": len(manifest["teams"]),
                      "unusable_teams": sum(bool(row["problems"])
                                            for row in manifest["teams"].values()),
                      "errors": manifest["errors"]}, ensure_ascii=False))
    if not manifest["complete"]:
        raise SystemExit(2)


def collect_profiles(args: argparse.Namespace) -> None:
    """Supplement a complete team audit with canonical profiles, never cards."""
    manifest, _catalog, _teams = load_collection(args.collection, require_complete=False)
    report = read_json(args.plan)
    if report["collection_snapshot_id"] != manifest["snapshot_id"]:
        raise ValueError("player audit and team snapshot differ")
    requested = sorted({row["base_id"] for row in report["players"]
                        if row["status"] in ("review_identity", "new_web_player")})
    folder = local_output(args.output)
    if args.resume:
        result = read_json(folder / "profiles.json")
        if (result["collection_snapshot_id"] != manifest["snapshot_id"]
                or result["requested_base_ids"] != requested):
            raise ValueError("cannot resume a different profile scope")
        started = datetime.fromisoformat(result["started_at"])
        if (datetime.now(timezone.utc) - started).total_seconds() > 24 * 3600:
            raise ValueError("profile collection is over 24 hours old; use a new snapshot")
        for key, entry in result["players"].items():
            cached_team(folder, int(key), entry)
    else:
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "raw").mkdir()
        result = {"schema_version": 1, "generator": GENERATOR, "source": PLAYER_API,
                  "collection_snapshot_id": manifest["snapshot_id"],
                  "started_at": now(), "requested_base_ids": requested,
                  "players": {}, "errors": {}}
    pending = sorted(set(requested) - set(map(int, result["players"])))
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(fetch_json, PLAYER_API + str(base), args.retries): base
                   for base in pending}
        for future in concurrent.futures.as_completed(futures):
            base = futures[future]
            try:
                raw, provenance = future.result()
                player = json.loads(raw)["data"]
                if int(player["pes_id"]) != base or int(player["base_pes_id"]) != base:
                    raise ValueError("canonical profile returned a different BaseId/card")
                normalize_player(player)
                (folder / "raw" / f"{base}.json.gz").write_bytes(gzip.compress(raw, mtime=0))
                result["players"][str(base)] = {**provenance, "sha256": digest(raw)}
                result["errors"].pop(str(base), None)
            except Exception as error:
                result["errors"][str(base)] = str(error)
            result["finished_at"] = now()
            write_json(folder / "profiles.json", result)
            done = len(result["players"]) + len(result["errors"])
            if done % 100 == 0 or done == len(requested):
                print(f"Profiles {len(result['players'])}/{len(requested)}; "
                      f"errors={len(result['errors'])}", flush=True)
    result["complete"] = not result["errors"]
    result["snapshot_id"] = digest(json_bytes({
        "collection": result["collection_snapshot_id"],
        "players": {key: row["sha256"] for key, row in result["players"].items()},
    }))[:16]
    write_json(folder / "profiles.json", result)
    print(json.dumps({"profiles": len(result["players"]), "errors": result["errors"],
                      "snapshot_id": result["snapshot_id"]}))


def load_profiles(folder: Path, collection_id: str) -> tuple[dict, dict]:
    manifest = read_json(folder / "profiles.json")
    if (manifest.get("generator") != GENERATOR or manifest.get("source") != PLAYER_API
            or manifest["collection_snapshot_id"] != collection_id):
        raise ValueError("profile provenance differs from the team collection")
    players = {}
    for key, entry in manifest["players"].items():
        base_id = int(key)
        data = json.loads(cached_team(folder, base_id, entry))["data"]
        player = normalize_player(data)
        if player["base_id"] != base_id or player["card_id"] != base_id:
            raise ValueError("canonical profile BaseId/card mismatch")
        club = data.get("current_club_id")
        player["club_id"] = int(club["pes_id"]) if isinstance(club, dict) else None
        players[base_id] = player
    return manifest, players


def player_payloads(folder: Path, profiles_folder: Path | None = None) -> tuple[dict, dict]:
    """Select canonical profiles, falling back to consistent frozen team cards."""
    manifest, _catalog, _teams = load_collection(folder, require_complete=False)
    result = {}
    def rank(row):
        return (int(row["pes_id"]) != int(row["base_pes_id"]),
                int(row["card_type"]) != 0, int(row["fake_version"]), int(row["pes_id"]))
    for key, entry in sorted(manifest["teams"].items(), key=lambda pair: int(pair[0])):
        team = json.loads(cached_team(folder, int(key), entry))["data"]
        for assignment in team["player_assignments"]:
            player = assignment["player"]
            base = int(player["base_pes_id"])
            if base not in result or rank(player) < rank(result[base]):
                result[base] = player
    profiles = {}
    if profiles_folder:
        profile_manifest, _ = load_profiles(profiles_folder, manifest["snapshot_id"])
        for key, entry in profile_manifest["players"].items():
            profiles[int(key)] = json.loads(cached_team(profiles_folder, int(key), entry))["data"]
        result.update(profiles)
    return result, profiles


def assemble_plan(args: argparse.Namespace) -> tuple[dict, dict]:
    from efootballdb_reconcile import load_local_identities, native_baseline, reconcile

    manifest, catalog, teams = load_collection(args.collection, require_complete=False)
    native, assignments = native_baseline(args.native_cpk)
    registry = read_json(args.registry)
    identities, owners, known_bases = load_local_identities(
        registry, read_json(args.source_db), native, args.master_db,
        read_json(args.fl26_slots) if args.fl26_slots else {})
    profiles = load_profiles(args.profiles, manifest["snapshot_id"])[1] if args.profiles else {}
    from efootballdb_player_import import web_player_to_source
    payloads, raw_profiles = player_payloads(args.collection, args.profiles)
    import_errors = {}
    for base, player in payloads.items():
        if f"ef:{base}" not in identities:
            try:
                web_player_to_source(player)
            except (KeyError, TypeError, ValueError) as error:
                import_errors[base] = str(error)
    report = reconcile(catalog, teams, manifest["errors"], identities, owners,
                       assignments, args.keep_unavailable, known_bases, profiles,
                       args.keep_identity_teams, args.allow_retained_outgoing, import_errors)
    report["collection_snapshot_id"] = manifest.get("snapshot_id")
    report["inputs"] = {key: {"path": str(path.resolve()),
                             "sha256": digest(path.read_bytes())}
                        for key, path in {
                            "registry": args.registry, "master_db": args.master_db,
                            "source_db": args.source_db, "native_cpk": args.native_cpk,
                            "collection": args.collection / "collection.json",
                            **({"profiles": args.profiles / "profiles.json"} if args.profiles else {}),
                            **({"fl26_slots": args.fl26_slots} if args.fl26_slots else {}),
                        }.items()}
    tactics = {
        "schema_version": 2, "source_snapshot_id": manifest.get("snapshot_id"),
        "teams": {str(team_id): {
            "team_id": team_id, "name": team["name"], "strategies": team["strategies"],
            "url": manifest["teams"][str(team_id)]["url"],
            "sha256": manifest["teams"][str(team_id)]["sha256"],
        } for team_id, team in teams.items() if team_id in report["updated_team_ids"]},
    }
    return report, {"catalog": catalog, "identities": identities, "native": native,
                    "payloads": payloads, "profiles": raw_profiles, "tactics": tactics}


def plan(args: argparse.Namespace) -> None:
    folder = local_output(args.output)
    if folder.exists():
        raise ValueError("plan output must be a new directory")
    report, context = assemble_plan(args)
    folder.mkdir(parents=True)
    write_json(folder / "transfer-plan.json", report)
    write_json(folder / "identity-review.json", report["identity_reviews"])
    write_json(folder / "team-tactics.json", context["tactics"])
    print(json.dumps({"status": report["status"], **report["counts"],
                      "output": str(folder)}, ensure_ascii=False))
    if report["status"] != "ready_to_stage":
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("collect", help="freeze every playable team's raw API response")
    fetch.add_argument("--catalog", type=Path, required=True)
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    fetch.add_argument("--retries", type=int, choices=range(1, 5), default=3)
    fetch.add_argument("--resume", action="store_true")
    fetch.set_defaults(run=collect)
    reconcile = commands.add_parser("plan", help="offline BaseId/FL26 transfer audit; no runtime writes")
    reconcile.add_argument("--collection", type=Path, required=True)
    reconcile.add_argument("--registry", type=Path, required=True)
    reconcile.add_argument("--master-db", type=Path, required=True)
    reconcile.add_argument("--source-db", type=Path, required=True)
    reconcile.add_argument("--native-cpk", type=Path, required=True)
    reconcile.add_argument("--fl26-slots", type=Path)
    reconcile.add_argument("--profiles", type=Path)
    reconcile.add_argument("--output", type=Path, required=True)
    reconcile.add_argument("--keep-unavailable", action="store_true",
                           help="explicitly preserve local teams with absent/unusable web rosters")
    reconcile.add_argument("--keep-identity-teams", action="store_true",
                           help="keep ambiguous teams and dependent transfers unchanged; stage only a safe subset")
    reconcile.add_argument("--allow-retained-outgoing", action="store_true",
                           help="approved verified departures from retained clubs; keep >=18 players and a goalkeeper")
    reconcile.set_defaults(run=plan)
    profiles = commands.add_parser("profiles", help="freeze canonical profiles for new/ambiguous players")
    profiles.add_argument("--collection", type=Path, required=True)
    profiles.add_argument("--plan", type=Path, required=True)
    profiles.add_argument("--output", type=Path, required=True)
    profiles.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    profiles.add_argument("--retries", type=int, choices=range(1, 5), default=3)
    profiles.add_argument("--resume", action="store_true")
    profiles.set_defaults(run=collect_profiles)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
