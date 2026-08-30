#!/usr/bin/env python3
"""Infer PES21-mobile ability bit locations from shared EF10 player IDs.

This is a development diagnostic for the fixed-record mobile databases.  EF10
uses 6-bit abilities with a +40 display offset.  PES21 mobile uses a different
packed layout, so the script correlates every plausible 7-bit PES21 window
against the decoded EF10 ability for thousands of players present in both
tables.  It never writes either database.
"""

from __future__ import annotations

import argparse
import gzip
import html
import json
import math
import re
import struct
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from generate_efootball10_rosters import decode_wesys


EF10_RECORD_SIZE = 392
PES21_RECORD_SIZE = 312

# Absolute LSB bit offsets in the 392-byte EF10-mobile Player.bin row.  The
# values were recovered against archived v10 player pages and then checked as
# five contiguous packed 32-bit blocks.  Every ability is six bits plus 40.
EF10_ABILITIES = {
    "set_piece_taking": 352,
    "gk_parrying": 358,
    "kicking_power": 364,
    "defensive_awareness": 370,
    "ball_control": 376,
    "heading": 384,
    "jumping": 390,
    "gk_catching": 396,
    "gk_reach": 402,
    "speed": 408,
    "tackling": 416,
    "gk_reflexes": 422,
    "gk_awareness": 428,
    "curl": 434,
    "stamina": 440,
    "acceleration": 448,
    "dribbling": 454,
    "offensive_awareness": 460,
    "balance": 466,
    "aggression": 472,
    "physical_contact": 480,
    "low_pass": 486,
    "finishing": 492,
    "lofted_pass": 498,
    "defensive_engagement": 512,
    "tight_possession": 518,
}


def split_records(raw: bytes, size: int) -> list[bytes]:
    if len(raw) % size:
        raise ValueError(f"{len(raw)} is not divisible by record size {size}")
    return [raw[offset : offset + size] for offset in range(0, len(raw), size)]


def read_bits(data: bytes, start: int, width: int) -> int:
    value = int.from_bytes(data, "little")
    return (value >> start) & ((1 << width) - 1)


def ef10_ability(record: bytes, start_bit: int) -> int:
    return read_bits(record, start_bit, 6) + 40


def correlation(xs: list[int], ys: list[int]) -> float:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    denominator = math.sqrt(
        sum(value * value for value in dx) * sum(value * value for value in dy)
    )
    if not denominator:
        return 0.0
    return sum(a * b for a, b in zip(dx, dy)) / denominator


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 player-layout-audit/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
        if payload.startswith(b"\x1f\x8b"):
            payload = gzip.decompress(payload)
        return payload.decode("utf-8", errors="replace")


def cached_archived_player_stats(
    game_path: str,
    timestamp: str,
    player_ids: list[int],
    cache_dir: Path,
) -> dict[int, dict[str, int]]:
    """Fetch PESDB pages once and retain only labeled numeric attributes."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    result: dict[int, dict[str, int]] = {}
    pattern = re.compile(
        r"<tr><th>([^<]+):</th><td[^>]*\bid=\"a\d+\"[^>]*>(\d+)</td>",
        re.IGNORECASE,
    )
    for index, player_id in enumerate(player_ids, 1):
        cache_path = cache_dir / f"{game_path}-{player_id}.json"
        if cache_path.is_file():
            stats = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            detail_url = (
                f"https://web.archive.org/web/{timestamp}id_/"
                f"https://pesdb.net/{game_path}/?id={player_id}"
            )
            try:
                page = fetch_html(detail_url)
            except Exception as error:
                print(
                    f"archive {index:02d}/{len(player_ids):02d}: {player_id} "
                    f"unavailable ({error})",
                    file=sys.stderr,
                )
                continue
            stats = {
                html.unescape(name).strip().lower().replace(" ", "_"): int(value)
                for name, value in pattern.findall(page)
            }
            if stats:
                cache_path.write_text(
                    json.dumps(stats, sort_keys=True) + "\n", encoding="utf-8"
                )
            time.sleep(0.2)
        if stats:
            result[player_id] = stats
        print(
            f"archive {index:02d}/{len(player_ids):02d}: {player_id} "
            f"({len(stats)} abilities)",
            file=sys.stderr,
        )
    return result


def infer_pes21_fields(
    rows_by_id: dict[int, bytes],
    reference: dict[int, dict[str, int]],
    top: int,
) -> None:
    shared_ids = sorted(rows_by_id.keys() & reference.keys())
    print(f"reference player IDs present in PES21 binary: {len(shared_ids)}")
    if len(shared_ids) < 3:
        raise RuntimeError("not enough archived PES21 records to infer bit layout")
    stat_names = sorted(
        set.intersection(*(set(reference[player_id]) for player_id in shared_ids))
    )
    windows: dict[int, list[int]] = {}
    for bit in range(68 * 8 - 7 + 1):
        # A matching seven-bit window is one preceding packed bit followed by
        # the six-bit (displayed value - 40) ability.  Floor division discards
        # that preceding bit while scoring candidate starts.
        values = [
            read_bits(rows_by_id[player_id][:68], bit, 7) // 2 + 40
            for player_id in shared_ids
        ]
        plausible = sum(40 <= value <= 99 for value in values) / len(values)
        if plausible >= 0.90 and max(values) - min(values) >= 4:
            windows[bit] = values
    for name in stat_names:
        source = [reference[player_id][name] for player_id in shared_ids]
        if max(source) - min(source) < 3:
            continue
        ranked = sorted(
            (
                (
                    correlation(source, values),
                    bit,
                    sum(a == b for a, b in zip(source, values)),
                    max(abs(a - b) for a, b in zip(source, values)),
                )
                for bit, values in windows.items()
            ),
            reverse=True,
        )[:top]
        print(
            f"{name:24s} "
            + ", ".join(
                f"bit {bit} (byte {bit // 8}+{bit % 8}, r={score:.4f}, "
                f"exact={exact}/{len(shared_ids)}, maxerr={max_error})"
                for score, bit, exact, max_error in ranked
            )
        )


def archived_barcelona_stats(
    timestamp: str, goalkeepers_only: bool = False
) -> dict[int, dict[str, int]]:
    """Read archived PESDB detail pages; no files or cookies are written."""
    query = urllib.parse.quote_plus('"FC Barcelona"')
    list_url = (
        f"https://web.archive.org/web/{timestamp}id_/https://pesdb.net/"
        f"efootball/?all=1&featured=0&club_team={query}"
        "&sort=club_number&order=a"
    )
    list_page = fetch_html(list_url)
    print(f"archive list: {list_url} ({len(list_page)} bytes)", file=sys.stderr)
    player_ids = sorted(
        {int(value) for value in re.findall(r'href="\./\?id=(\d+)"', list_page)}
    )
    # A broader goalkeeper sample disambiguates the five GK-only ability
    # fields; most club outfield players carry the same floor value there.
    goalkeeper_ids = {
        40571,
        40937,
        44104,
        44383,
        46815,
        47472,
        60447,
        61672,
        101520,
        108279,
    }
    player_ids = sorted(goalkeeper_ids if goalkeepers_only else set(player_ids) | goalkeeper_ids)
    if not player_ids:
        print(re.sub(r"\s+", " ", list_page[:1000]), file=sys.stderr)
    result: dict[int, dict[str, int]] = {}
    pattern = re.compile(
        r"<tr><th>([^<]+):</th><td><span[^>]*\bid=\"a\d+\"[^>]*>"
        r"(\d+)</span>",
        re.IGNORECASE,
    )
    for index, player_id in enumerate(player_ids, 1):
        detail_url = (
            f"https://web.archive.org/web/{timestamp}id_/"
            f"https://pesdb.net/efootball/?id={player_id}"
        )
        try:
            page = fetch_html(detail_url)
        except Exception as error:  # Archive coverage is intentionally sparse.
            print(
                f"archive {index:02d}/{len(player_ids):02d}: {player_id} "
                f"unavailable ({error})",
                file=sys.stderr,
            )
            continue
        stats = {
            html.unescape(name).strip().lower().replace(" ", "_"): int(value)
            for name, value in pattern.findall(page)
        }
        if stats:
            result[player_id] = stats
        print(
            f"archive {index:02d}/{len(player_ids):02d}: {player_id} "
            f"({len(stats)} abilities)",
            file=sys.stderr,
        )
    return result


def infer_six_bit_fields(
    rows_by_id: dict[int, bytes],
    reference: dict[int, dict[str, int]],
    core_bytes: int,
    top: int,
) -> None:
    shared_ids = sorted(rows_by_id.keys() & reference.keys())
    print(f"reference player IDs present in binary: {len(shared_ids)}")
    stat_names = sorted(
        set.intersection(*(set(reference[player_id]) for player_id in shared_ids))
    )
    windows: dict[int, list[int]] = {}
    for bit in range(core_bytes * 8 - 6 + 1):
        values = [
            read_bits(rows_by_id[player_id][:core_bytes], bit, 6) + 40
            for player_id in shared_ids
        ]
        if all(40 <= value <= 103 for value in values) and max(values) - min(values) >= 5:
            windows[bit] = values
    for name in stat_names:
        source = [reference[player_id][name] for player_id in shared_ids]
        if max(source) - min(source) < 3:
            continue
        ranked = sorted(
            ((correlation(source, values), bit) for bit, values in windows.items()),
            reverse=True,
        )[:top]
        print(
            f"{name:24s} "
            + ", ".join(
                f"bit {bit} (byte {bit // 8}+{bit % 8}, r={score:.4f})"
                for score, bit in ranked
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ef10-player",
        type=Path,
        default=Path("local-debug/efootball10-audit/tables/common/etc/pesdb/Player.bin"),
    )
    parser.add_argument(
        "--pes21-player",
        type=Path,
        default=Path(
            "local-debug/efootball10-audit/compare/"
            "old_dt200_mobile_all.cpk/common/etc/pesdb/Player.bin"
        ),
    )
    parser.add_argument("--top", type=int, default=4)
    parser.add_argument(
        "--wayback-ef10",
        action="store_true",
        help="infer EF10-mobile slots from archived eFootball 2025 Barcelona stats",
    )
    parser.add_argument("--wayback-timestamp", default="20250824032348")
    parser.add_argument("--wayback-goalkeepers-only", action="store_true")
    parser.add_argument(
        "--wayback-pes21",
        action="store_true",
        help="infer PES21-mobile slots from archived PES 2021 player stats",
    )
    parser.add_argument("--wayback-pes21-timestamp", default="20210619123339")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("local-debug/player-stat-layout-cache"),
    )
    args = parser.parse_args()

    ef10_rows = split_records(decode_wesys(args.ef10_player), EF10_RECORD_SIZE)
    pes21_rows = split_records(decode_wesys(args.pes21_player), PES21_RECORD_SIZE)
    ef10_by_id = {struct.unpack_from("<Q", row, 8)[0]: row for row in ef10_rows}
    pes21_by_id = {struct.unpack_from("<I", row, 8)[0]: row for row in pes21_rows}
    if args.wayback_pes21:
        # PES21 Barcelona supplies a broad outfield spread.  Extra elite and
        # reserve goalkeepers disambiguate the five goalkeeper-only fields.
        player_ids = [
            7511, 8639, 37422, 38568, 40425, 42316, 42641, 42892, 43202,
            45330, 60622, 61672, 104418, 108662, 110626, 114661, 116578,
            121314, 121985, 122908, 126426, 126673, 132153, 132535, 132544,
            133157, 133215, 138292, 138298, 138300,
            40571, 44104, 44383, 46815, 47472, 60447, 101520, 108279,
        ]
        reference = cached_archived_player_stats(
            "pes2021",
            args.wayback_pes21_timestamp,
            player_ids,
            args.cache_dir,
        )
        infer_pes21_fields(pes21_by_id, reference, args.top)
        return
    if args.wayback_ef10:
        reference = archived_barcelona_stats(
            args.wayback_timestamp, args.wayback_goalkeepers_only
        )
        infer_six_bit_fields(ef10_by_id, reference, 80, args.top)
        return
    shared_ids = sorted(
        player_id
        for player_id in ef10_by_id.keys() & pes21_by_id.keys()
        if 0 < player_id < 1_000_000
    )
    print(f"shared base player IDs: {len(shared_ids)}")

    # Player core ends where the first 61-byte name starts.
    windows: dict[int, list[int]] = {}
    for bit in range(0, 68 * 8 - 7 + 1):
        values = [read_bits(pes21_by_id[player_id][:68], bit, 7) for player_id in shared_ids]
        plausible = sum(40 <= value <= 109 for value in values) / len(values)
        if plausible >= 0.90 and max(values) - min(values) >= 12:
            windows[bit] = values

    for name, field in EF10_ABILITIES.items():
        source = [ef10_ability(ef10_by_id[player_id], field) for player_id in shared_ids]
        ranked = sorted(
            (
                (correlation(source, values), bit, min(values), max(values))
                for bit, values in windows.items()
            ),
            reverse=True,
        )[: args.top]
        matches = ", ".join(
            f"bit {bit} (byte {bit // 8}+{bit % 8}, r={score:.4f}, {low}..{high})"
            for score, bit, low, high in ranked
        )
        print(f"{name:24s} {matches}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
