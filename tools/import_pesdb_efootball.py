#!/usr/bin/env python3
"""Import current eFootball player data from pesdb.net.

The live eFootball database is the authority for values in this pipeline.  A
PES21 database is accepted only as a target-format/reference input by later
conversion steps; it is never used to fill a missing PESDB value.

The importer deliberately separates fields that have a verified PES21-mobile
bit layout (the 25 gameplay abilities) from fields whose target offsets still
need proof (skills, foot, form, body model, and playing style).  Unsupported
fields remain in the snapshot and in the coverage report instead of being
silently guessed.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITEMAP = "https://pesdb.net/sitemaps/sitemap.xml"
DEFAULT_CACHE = Path("local-debug/pesdb-efootball-cache")
DEFAULT_SNAPSHOT = Path("local-debug/pesdb-efootball-snapshot.json")
USER_AGENT = "public-pesnx-pesdb-importer/1.0"

POSITION_NAMES = (
    "GK", "CB", "LB", "RB", "DMF", "CMF", "LMF", "RMF", "AMF",
    "LWF", "RWF", "SS", "CF",
)

# These names and offsets are verified by tools/convert_efootball10_players.py.
VERIFIED_ABILITY_NAMES = (
    "set_piece_taking", "gk_parrying", "kicking_power",
    "defensive_awareness", "ball_control", "heading", "jumping",
    "gk_catching", "gk_reach", "speed", "tackling", "gk_reflexes",
    "gk_awareness", "curl", "stamina", "acceleration", "dribbling",
    "offensive_awareness", "balance", "aggression", "physical_contact",
    "low_pass", "finishing", "lofted_pass", "tight_possession",
)
ALL_ABILITY_NAMES = VERIFIED_ABILITY_NAMES + ("defensive_engagement",)

SCRIPT_RE = re.compile(
    r'<script[^>]+id=["\']player-progression-data["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.IGNORECASE | re.DOTALL)
PLAYER_URL_RE = re.compile(r"/efootball/players/[^/]+-(\d+)(?:[/?#]|$)")
AUTHENTIC_PLAYER_URL_RE = re.compile(
    r'href=["\']/efootball/authentic/players/[^"\']+-(\d+)["\']'
)
PAGINATION_RE = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_content_id(payload: dict[str, Any]) -> str:
    # Fetch time is provenance metadata, not player content. Excluding it keeps
    # identical PESDB rows reproducible across refreshes and makes --check useful.
    canonical = json.dumps(
        {
            key: value
            for key, value in payload.items()
            if key not in {"content_id", "generated_at_utc"}
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def clean_text(value: str) -> str:
    value = html_lib.unescape(TAG_RE.sub(" ", value))
    return SPACE_RE.sub(" ", value).strip()


def fetch_bytes_with_headers(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_bytes(url: str, *, timeout: float = 30.0) -> bytes:
    return fetch_bytes_with_headers(url, timeout=timeout)


def parse_sitemap(text: str) -> dict[int, str]:
    """Return base player ID -> standard PESDB URL from a sitemap."""
    result: dict[int, str] = {}
    try:
        root = ET.fromstring(text)
        locations = [element.text or "" for element in root.iter() if element.tag.endswith("loc")]
    except ET.ParseError:
        locations = LOC_RE.findall(text)
    for location in locations:
        location = html_lib.unescape(location.strip())
        match = PLAYER_URL_RE.search(location)
        if not match or "/efootball/players/" not in location:
            continue
        player_id = int(match.group(1))
        previous = result.get(player_id)
        if previous is None or len(location) < len(previous):
            result[player_id] = location
    return result


def parse_sitemap_locations(text: str) -> list[str]:
    """Return child sitemap URLs from a sitemap index."""
    try:
        root = ET.fromstring(text)
        return [
            (element.text or "").strip()
            for element in root.iter()
            if element.tag.endswith("loc") and element.text
        ]
    except ET.ParseError:
        return [value.strip() for value in LOC_RE.findall(text)]


def load_sitemap_index(
    cache_path: Path,
    *,
    sitemap_url: str = DEFAULT_SITEMAP,
    refresh: bool = False,
) -> dict[int, str]:
    """Load a cached sitemap, refreshing it only when requested or absent."""
    if cache_path.is_file() and not refresh:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") == 1 and payload.get("sitemap_url") == sitemap_url:
            return {int(key): str(value) for key, value in payload.get("players", {}).items()}
    raw = fetch_bytes(sitemap_url)
    raw_text = raw.decode("utf-8", errors="replace")
    locations = parse_sitemap_locations(raw_text)
    if "<sitemapindex" in raw_text.lower() and locations:
        mapping: dict[int, str] = {}
        player_sitemaps = [
            location for location in locations
            if "players-" in location and location.endswith(".xml")
        ]
        for child_url in player_sitemaps:
            child_raw = fetch_bytes(child_url)
            mapping.update(parse_sitemap(child_raw.decode("utf-8", errors="replace")))
    else:
        mapping = parse_sitemap(raw_text)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "sitemap_url": sitemap_url,
                "sha256": sha256_bytes(raw),
                "player_count": len(mapping),
                "players": {str(key): value for key, value in sorted(mapping.items())},
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return mapping


def extract_progression_json(page: str) -> dict[str, Any]:
    match = SCRIPT_RE.search(page)
    if not match:
        raise ValueError("player-progression-data JSON block is missing")
    value = html_lib.unescape(match.group(1)).strip()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid player-progression-data JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("player-progression-data is not an object")
    return payload


def visible_details(page: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_key, raw_value in re.findall(
        r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>",
        page,
        re.IGNORECASE | re.DOTALL,
    ):
        key = clean_text(raw_key).lower().replace(" ", "_")
        value = clean_text(raw_value)
        if key and value and key not in result:
            result[key] = value
    return result


def normalize_player_payload(
    progression: dict[str, Any],
    *,
    requested_player_id: int | None = None,
    page_url: str = "",
    page_sha256: str = "",
    page_details: dict[str, str] | None = None,
) -> dict[str, Any]:
    compare = progression.get("compare")
    if not isinstance(compare, dict):
        compare = {}
    raw_id = progression.get("playerId", compare.get("playerId", requested_player_id))
    try:
        player_id = int(raw_id)
    except (TypeError, ValueError) as error:
        raise ValueError("player ID is missing from PESDB payload") from error
    if requested_player_id is not None and player_id != requested_player_id:
        raise ValueError(
            f"requested player {requested_player_id}, page contains {player_id}"
        )
    position = progression.get("position")
    position_index = int(position) if isinstance(position, int) else None
    positions = [str(value) for value in progression.get("positions", []) if value]
    if position_index is not None and not 0 <= position_index < len(POSITION_NAMES):
        raise ValueError(f"PESDB position index out of range: {position_index}")
    base_stats_raw = progression.get("baseStats")
    if not isinstance(base_stats_raw, dict):
        raise ValueError("PESDB baseStats is missing")
    base_stats: dict[str, int] = {}
    for name in ALL_ABILITY_NAMES:
        value = base_stats_raw.get(name)
        if value is None:
            continue
        value = int(value)
        if not 0 <= value <= 99:
            raise ValueError(f"PESDB ability {name} is outside 0..99: {value}")
        base_stats[name] = value
    if not set(VERIFIED_ABILITY_NAMES).issubset(base_stats):
        missing = sorted(set(VERIFIED_ABILITY_NAMES) - set(base_stats))
        raise ValueError("PESDB payload lacks verified abilities: " + ", ".join(missing))
    details = progression.get("compare", {}).get("details", {})
    if not isinstance(details, dict):
        details = {}
    player_name = str(compare.get("playerName") or progression.get("playerName") or "").strip()
    if not player_name:
        raise ValueError("PESDB player name is missing")
    skills = compare.get("playerSkills", [])
    ai_styles = compare.get("aiPlayingStyles", [])
    if not isinstance(skills, list) or not all(isinstance(value, str) for value in skills):
        raise ValueError("PESDB playerSkills is malformed")
    if not isinstance(ai_styles, list) or not all(isinstance(value, str) for value in ai_styles):
        raise ValueError("PESDB aiPlayingStyles is malformed")
    result: dict[str, Any] = {
        "player_id": player_id,
        "player_name": player_name,
        "source": str(progression.get("source") or compare.get("source") or "authentic"),
        "url": page_url or str(compare.get("playerUrl") or ""),
        "page_sha256": page_sha256,
        "primary_position_index": position_index,
        "primary_position": (
            POSITION_NAMES[position_index] if position_index is not None else None
        ),
        "positions": positions,
        "height_cm": int(progression["height"]) if progression.get("height") is not None else None,
        "base_overall": int(progression["baseOverall"]) if progression.get("baseOverall") is not None else None,
        "database_max_overall": int(progression["databaseMaxOverall"]) if progression.get("databaseMaxOverall") is not None else None,
        "base_stats": base_stats,
        "player_skills": list(skills),
        "ai_playing_styles": list(ai_styles),
        "attacking_playing_style": compare.get("attackingPlayingStyle"),
        "defensive_playing_style": compare.get("defensivePlayingStyle"),
        "team_name": compare.get("teamName"),
        "nationality": compare.get("nationality"),
        "weak_foot_accuracy_numeric": progression.get("weakFootAccuracy"),
        "details": {
            "weak_foot_usage": details.get("weak_foot_usage"),
            "weak_foot_accuracy": details.get("weak_foot_accuracy"),
            "form": details.get("form"),
            "injury_resistance": details.get("injury_resistance"),
            "stronger_foot": (page_details or {}).get("stronger_foot"),
            "weight": (page_details or {}).get("weight"),
        },
        "unsupported_target_fields": [
            "player_skills", "ai_playing_styles", "attacking_playing_style",
            "defensive_playing_style", "stronger_foot", "form",
            "injury_resistance", "height_cm", "weight",
        ],
    }
    return result


def parse_player_page(
    page: str,
    *,
    requested_player_id: int | None = None,
    page_url: str = "",
) -> dict[str, Any]:
    return normalize_player_payload(
        extract_progression_json(page),
        requested_player_id=requested_player_id,
        page_url=page_url,
        page_sha256=sha256_bytes(page.encode("utf-8")),
        page_details=visible_details(page),
    )


def authentic_url(standard_url: str, player_id: int) -> str:
    match = re.search(r"/efootball/players/([^/]+)", standard_url)
    if not match:
        return f"https://pesdb.net/efootball/authentic/players/player-{player_id}"
    return f"https://pesdb.net/efootball/authentic/players/{match.group(1)}"


def requested_url(
    player_id: int,
    standard_urls: dict[int, str],
    source: str,
) -> str:
    standard = standard_urls.get(player_id)
    if standard is None:
        slug = f"player-{player_id}"
        standard = f"https://pesdb.net/efootball/players/{slug}"
    return authentic_url(standard, player_id) if source == "authentic" else standard


def parse_authentic_team_page(page: str) -> tuple[list[int], int]:
    """Return authentic player IDs and the total result page count."""
    player_ids = sorted({int(value) for value in AUTHENTIC_PLAYER_URL_RE.findall(page)})
    pages = [int(total) for _current, total in PAGINATION_RE.findall(page)]
    return player_ids, max(pages, default=1)


def parse_authentic_team_table(page: str) -> tuple[list[dict[str, int | None]], int]:
    """Parse table-view roster rows, including PESDB club shirt numbers."""
    rows: list[dict[str, int | None]] = []
    for raw_row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", page, re.IGNORECASE | re.DOTALL):
        ids = AUTHENTIC_PLAYER_URL_RE.findall(raw_row)
        if not ids:
            continue
        player_id = int(ids[0])
        cells = re.findall(
            r'data-copy-value=["\']([^"\']*)["\']', raw_row, re.IGNORECASE
        )
        # Table columns are position, name, club shirt number, ... . Keep a
        # null number explicit when PESDB publishes a blank/non-numeric value.
        shirt: int | None = None
        if len(cells) >= 3 and re.fullmatch(r"\d+", cells[2].strip()):
            shirt = int(cells[2].strip())
        rows.append({"player_id": player_id, "shirt_number": shirt})
    pages = [int(total) for _current, total in PAGINATION_RE.findall(page)]
    return rows, max(pages, default=1)


def _authentic_team_headers() -> dict[str, str]:
    preference = {
        "view": "table",
        "columns": ["pos", "name", "shirt_number", "overall_rating"],
        "sort": "shirt_number",
        "order": "asc",
    }
    return {
        "Cookie": "pesdb_efootball_search="
        + urllib.parse.quote(json.dumps(preference, separators=(",", ":")))
    }


def fetch_authentic_team_roster(
    team_id: int,
    *,
    timeout: float = 30.0,
    delay: float = 0.35,
) -> list[dict[str, int | None]]:
    """Fetch current Authentic IDs and club shirt numbers for one PESDB team."""
    if team_id <= 0:
        raise ValueError("PESDB team ID must be positive")
    base_url = f"https://pesdb.net/efootball/authentic/players/?team_id={team_id}"
    headers = _authentic_team_headers()
    first = fetch_bytes_with_headers(base_url, headers=headers, timeout=timeout).decode(
        "utf-8", errors="replace"
    )
    roster, page_count = parse_authentic_team_table(first)
    if not roster:
        ids, page_count = parse_authentic_team_page(first)
        roster = [{"player_id": player_id, "shirt_number": None} for player_id in ids]
    seen = {int(row["player_id"]) for row in roster}
    for page_number in range(2, page_count + 1):
        if delay:
            time.sleep(delay)
        raw = fetch_bytes_with_headers(
            f"{base_url}&page={page_number}",
            headers=headers,
            timeout=timeout,
        )
        page = raw.decode("utf-8", errors="replace")
        current, current_pages = parse_authentic_team_table(page)
        if not current:
            ids, current_pages = parse_authentic_team_page(page)
            current = [{"player_id": player_id, "shirt_number": None} for player_id in ids]
        if current_pages != page_count:
            raise ValueError(
                f"PESDB team {team_id} pagination changed during fetch: "
                f"{page_count} -> {current_pages}"
            )
        for row in current:
            player_id = int(row["player_id"])
            if player_id not in seen:
                roster.append(row)
                seen.add(player_id)
    if not roster:
        raise ValueError(f"PESDB team {team_id} returned no authentic players")
    return roster


def fetch_authentic_team_player_ids(
    team_id: int,
    *,
    timeout: float = 30.0,
    delay: float = 0.35,
) -> list[int]:
    """Fetch the current authentic roster for one PESDB team ID."""
    if team_id <= 0:
        raise ValueError("PESDB team ID must be positive")
    base_url = f"https://pesdb.net/efootball/authentic/players/?team_id={team_id}"
    first = fetch_bytes(base_url, timeout=timeout).decode("utf-8", errors="replace")
    player_ids, page_count = parse_authentic_team_page(first)
    seen = set(player_ids)
    for page_number in range(2, page_count + 1):
        if delay:
            time.sleep(delay)
        raw = fetch_bytes(f"{base_url}&page={page_number}", timeout=timeout)
        current_ids, current_pages = parse_authentic_team_page(
            raw.decode("utf-8", errors="replace")
        )
        if current_pages != page_count:
            raise ValueError(
                f"PESDB team {team_id} pagination changed during fetch: "
                f"{page_count} -> {current_pages}"
            )
        seen.update(current_ids)
    if not seen:
        raise ValueError(f"PESDB team {team_id} returned no authentic players")
    return sorted(seen)


def load_cached_player(cache_dir: Path, source: str, player_id: int) -> dict[str, Any] | None:
    path = cache_dir / f"{source}-{player_id}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or int(payload.get("player_id", 0)) != player_id:
        raise ValueError(f"invalid cached PESDB player: {path}")
    if payload.get("source") != source:
        raise ValueError(f"cached PESDB player source mismatch: {path}")
    return payload


def fetch_player(
    player_id: int,
    *,
    standard_urls: dict[int, str],
    source: str,
    cache_dir: Path,
    retries: int = 2,
    timeout: float = 30.0,
    delay: float = 0.0,
    offline: bool = False,
) -> tuple[int, dict[str, Any] | None, str | None]:
    cached = load_cached_player(cache_dir, source, player_id)
    if cached is not None:
        return player_id, cached, None
    if player_id not in standard_urls:
        return player_id, None, "not present in PESDB eFootball base-player sitemap"
    if offline:
        return player_id, None, "cache miss in offline mode"
    url = requested_url(player_id, standard_urls, source)
    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            raw = fetch_bytes(url, timeout=timeout)
            page = raw.decode("utf-8", errors="replace")
            payload = parse_player_page(page, requested_player_id=player_id, page_url=url)
            payload["schema_version"] = 1
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"{source}-{player_id}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            if delay:
                time.sleep(delay)
            return player_id, payload, None
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as error:
            last_error = f"{type(error).__name__}: {error}"
            if attempt < retries:
                time.sleep(min(2.0, 0.25 * (attempt + 1)))
    return player_id, None, last_error or "unknown fetch error"


def build_snapshot(
    player_ids: Iterable[int],
    *,
    standard_urls: dict[int, str],
    source: str = "authentic",
    cache_dir: Path = DEFAULT_CACHE,
    workers: int = 4,
    retries: int = 2,
    timeout: float = 30.0,
    delay: float = 0.0,
    offline: bool = False,
) -> dict[str, Any]:
    ids = sorted({int(value) for value in player_ids if int(value) > 0})
    if source not in {"authentic", "standard"}:
        raise ValueError("source must be authentic or standard")
    players: dict[int, dict[str, Any]] = {}
    failures: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        futures = {
            executor.submit(
                fetch_player,
                player_id,
                standard_urls=standard_urls,
                source=source,
                cache_dir=cache_dir,
                retries=retries,
                timeout=timeout,
                delay=delay,
                offline=offline,
            ): player_id
            for player_id in ids
        }
        for future in as_completed(futures):
            player_id, payload, error = future.result()
            if payload is not None:
                players[player_id] = payload
            else:
                failures[player_id] = error or "unknown error"
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/import_pesdb_efootball.py",
        "source": source,
        "authority": "https://pesdb.net/efootball",
        "requested_player_ids": ids,
        "players": {str(key): players[key] for key in sorted(players)},
        "failures": {str(key): failures[key] for key in sorted(failures)},
        "counts": {
            "requested": len(ids),
            "fetched": len(players),
            "failed": len(failures),
            "verified_ability_rows": sum(
                set(VERIFIED_ABILITY_NAMES).issubset(value.get("base_stats", {}))
                for value in players.values()
            ),
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    snapshot["content_id"] = canonical_content_id(snapshot)
    return snapshot


def write_snapshot(path: Path, payload: dict[str, Any], *, check: bool = False) -> None:
    content = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    if check:
        if not path.is_file():
            raise RuntimeError(f"snapshot is stale: {path}")
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"snapshot is stale: {path}") from error
        # `generated_at_utc` is intentionally allowed to move forward. Compare
        # the content-addressed payload instead of making a timestamp part of
        # the generated-file check.
        if (
            existing.get("content_id") != payload.get("content_id")
            or canonical_content_id(existing) != canonical_content_id(payload)
        ):
            raise RuntimeError(f"snapshot is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ids_from_file(path: Path) -> list[int]:
    values: list[int] = []
    for token in re.findall(r"\d+", path.read_text(encoding="utf-8")):
        value = int(token)
        if value > 0:
            values.append(value)
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player-id", action="append", type=int, default=[])
    parser.add_argument("--ids-file", type=Path)
    parser.add_argument("--sitemap-url", default=DEFAULT_SITEMAP)
    parser.add_argument("--sitemap-cache", type=Path, default=DEFAULT_CACHE / "sitemap.json")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--source", choices=("authentic", "standard"), default="authentic")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="concurrent requests (keep at 1 for PESDB rate-limit safety)",
    )
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="delay after each network fetch; cached rows are not delayed",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--refresh-sitemap", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="fail unless every requested player has a verified PESDB row",
    )
    parser.add_argument(
        "--failure-report",
        type=Path,
        help="optional full failure JSON; stderr prints only a compact summary",
    )
    args = parser.parse_args()
    ids = list(args.player_id)
    if args.ids_file:
        ids.extend(ids_from_file(args.ids_file))
    if not ids:
        parser.error("at least one --player-id or --ids-file is required")
    sitemap = load_sitemap_index(
        args.sitemap_cache,
        sitemap_url=args.sitemap_url,
        refresh=args.refresh_sitemap,
    )
    snapshot = build_snapshot(
        ids,
        standard_urls=sitemap,
        source=args.source,
        cache_dir=args.cache_dir,
        workers=args.workers,
        retries=args.retries,
        timeout=args.timeout,
        delay=args.delay,
        offline=args.offline,
    )
    write_snapshot(args.snapshot, snapshot, check=args.check)
    print(json.dumps(snapshot["counts"], sort_keys=True))
    if snapshot["failures"]:
        if args.failure_report:
            args.failure_report.parent.mkdir(parents=True, exist_ok=True)
            args.failure_report.write_text(
                json.dumps(snapshot["failures"], indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
        first = list(snapshot["failures"].items())[:10]
        print(
            json.dumps(
                {"failed": len(snapshot["failures"]), "first": dict(first)},
                indent=2,
            ),
            file=sys.stderr,
        )
        if args.check or args.require_complete:
            raise SystemExit(1)
    if args.require_complete and snapshot["counts"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
