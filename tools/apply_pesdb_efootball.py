#!/usr/bin/env python3
"""Apply verified PESDB eFootball values to a PES21-mobile Player.bin.

This command is intentionally separate from the runtime build.  It writes an
isolated WESYS table and a coverage report, preserving the fixed PES21 row
count/order.  A source-to-target map can point EF10 IDs at PES21 surrogate
slots; absent mappings use the same ID only when that ID already exists in the
target table.

Only fields with a proven PES21-mobile layout are written: display name,
registered position, and the 25 gameplay abilities.  PESDB skills, foot,
playing style, form, body model, and OVR are retained in the report but are
not guessed into opaque target bits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any

from convert_efootball10_players import (
    PES21_ABILITY_BITS,
    PES21_PLAYER_SIZE,
    encode_pes21_wesys,
    pes21_name,
    pes21_player_id,
    pes21_player_position,
    pes21_abilities,
    read_bits,
    write_bits,
    decode_wesys,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = Path("local-debug/pesdb-efootball-snapshot.json")
DEFAULT_PLAYER = Path(
    "local-debug/efootball10-audit/compare/"
    "old_dt200_mobile_all.cpk/common/etc/pesdb/Player.bin"
)
DEFAULT_OUTPUT = Path("local-debug/pesdb-efootball-player-patch")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return sha256_bytes(canonical)[:16]


def split_rows(raw: bytes, size: int, label: str) -> list[bytes]:
    if len(raw) % size:
        raise ValueError(f"{label}: raw length is not divisible by {size}")
    return [raw[offset : offset + size] for offset in range(0, len(raw), size)]


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected an object")
    return payload


def load_target_map(path: Path | None) -> dict[int, int]:
    if path is None:
        return {}
    payload = load_json(path)
    raw = payload.get("map", payload.get("source_to_target", payload))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: map must be an object")
    result = {int(source): int(target) for source, target in raw.items()}
    if any(source <= 0 or target <= 0 for source, target in result.items()):
        raise ValueError(f"{path}: player IDs must be positive")
    if len(result) != len(set(result.values())):
        raise ValueError(f"{path}: target player IDs are duplicated")
    return result


def load_snapshot(
    path: Path,
    *,
    require_authentic: bool = False,
) -> dict[int, dict[str, Any]]:
    payload = load_json(path)
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported PESDB snapshot schema")
    source = payload.get("source")
    if source not in {"authentic", "standard"}:
        raise ValueError(f"{path}: unsupported PESDB source")
    if require_authentic and source != "authentic":
        raise ValueError(
            f"{path}: release application requires PESDB eFootball authentic data"
        )
    authority = payload.get("authority")
    if authority is not None and authority != "https://pesdb.net/efootball":
        raise ValueError(f"{path}: unexpected PESDB authority")
    raw = payload.get("players")
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: players must be an object")
    result: dict[int, dict[str, Any]] = {}
    for key, row in raw.items():
        player_id = int(key)
        if not isinstance(row, dict):
            raise ValueError(f"{path}: malformed player row {key}")
        if row.get("source") not in {None, source}:
            raise ValueError(
                f"{path}: player {player_id} source disagrees with snapshot"
            )
        row_id = int(row.get("player_id", 0))
        source_id = int(row.get("source_player_id", row_id))
        if row_id != player_id and source_id != player_id:
            raise ValueError(f"{path}: malformed player row {key}")
        stats = row.get("base_stats")
        if not isinstance(stats, dict):
            raise ValueError(f"{path}: player {player_id} lacks base_stats")
        missing = sorted(set(PES21_ABILITY_BITS) - set(stats))
        if missing:
            raise ValueError(
                f"{path}: player {player_id} lacks verified abilities: {', '.join(missing)}"
            )
        result[player_id] = row
    return result


def load_snapshots(
    paths: list[Path],
    *,
    require_authentic: bool = False,
) -> dict[int, dict[str, Any]]:
    """Merge PESDB snapshots without allowing conflicting player records."""
    merged: dict[int, dict[str, Any]] = {}
    for path in paths:
        current = load_snapshot(path, require_authentic=require_authentic)
        for player_id, row in current.items():
            previous = merged.get(player_id)
            if previous is not None and previous != row:
                raise ValueError(
                    f"PESDB player {player_id} differs between authentic snapshots"
                )
            merged[player_id] = row
    return merged


def set_player_name(row: bytes, name: str) -> bytes:
    encoded = name.encode("utf-8", errors="replace")
    if len(encoded) > 60:
        encoded = encoded[:60]
    result = bytearray(row)
    result[251:312] = encoded + b"\0" * (61 - len(encoded))
    return bytes(result)


def set_registered_position(row: bytes, position: int) -> bytes:
    if not 0 <= position <= 0x0F:
        raise ValueError(f"registered position outside PES21 range: {position}")
    result = bytearray(row)
    word = struct.unpack_from("<I", result, 52)[0]
    word = (word & ~(0x0F << 18)) | (position << 18)
    struct.pack_into("<I", result, 52, word)
    return bytes(result)


def apply_verified_fields(
    row: bytes,
    player: dict[str, Any],
    *,
    update_name: bool = True,
    update_position: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    result = bytearray(row)
    stats = player["base_stats"]
    for name, bit in PES21_ABILITY_BITS.items():
        value = int(stats[name])
        if not 40 <= value <= 99:
            raise ValueError(f"PESDB {name} value outside PES21 range: {value}")
        write_bits(result, bit + 1, 6, value - 40)
    if update_name:
        result = bytearray(set_player_name(bytes(result), str(player["player_name"])))
    position = player.get("primary_position_index")
    if update_position and position is not None:
        result = bytearray(set_registered_position(bytes(result), int(position)))
    checked = bytes(result)
    return checked, {
        "name_changed": pes21_name(checked) != pes21_name(row),
        "position_before": pes21_player_position(row),
        "position_after": pes21_player_position(checked),
        "abilities_verified": len(PES21_ABILITY_BITS),
        "unsupported_fields": list(player.get("unsupported_target_fields", [])),
    }


def apply_snapshot(
    player_raw: bytes,
    snapshot: dict[int, dict[str, Any]],
    target_map: dict[int, int],
    *,
    update_name: bool = True,
    update_position: bool = True,
) -> tuple[bytes, dict[str, Any]]:
    rows = split_rows(player_raw, PES21_PLAYER_SIZE, "PES21 Player.bin")
    by_id = {pes21_player_id(row): row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("PES21 Player.bin contains duplicate IDs")
    patched_by_id = dict(by_id)
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    used_targets: set[int] = set()
    for source_id, player in sorted(snapshot.items()):
        target_id = int(target_map.get(source_id, source_id))
        if target_id not in by_id:
            skipped.append({"source_player_id": source_id, "target_player_id": target_id, "reason": "target_missing"})
            continue
        if target_id in used_targets:
            raise ValueError(f"multiple PESDB players map to target {target_id}")
        used_targets.add(target_id)
        patched, fields = apply_verified_fields(
            by_id[target_id],
            player,
            update_name=update_name,
            update_position=update_position,
        )
        patched_by_id[target_id] = patched
        applied.append(
            {
                "source_player_id": source_id,
                "target_player_id": target_id,
                "name": player["player_name"],
                "source": player.get("source"),
                "base_overall": player.get("base_overall"),
                **fields,
            }
        )
    patched_rows = [patched_by_id[pes21_player_id(row)] for row in rows]
    report = {
        "schema_version": 1,
        "authority": "https://pesdb.net/efootball",
        "requested": len(snapshot),
        "applied": len(applied),
        "skipped": len(skipped),
        "verified_fields": ["name", "registered_position", "25_gameplay_abilities"],
        "unsupported_fields_not_written": [
            "overall", "player_skills", "ai_playing_styles", "attacking_playing_style",
            "defensive_playing_style", "stronger_foot", "form", "injury_resistance",
            "height_cm", "weight", "body_model", "nationality_code",
        ],
        "applied_players": applied,
        "skipped_players": skipped,
        "source_id_semantics": (
            "snapshot keys are current PESDB Authentic player IDs; target maps "
            "resolve them to physical PES21 rows"
        ),
        "pesdb_only": True,
    }
    return b"".join(patched_rows), report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--extra-snapshot",
        action="append",
        type=Path,
        default=[],
        help="additional PESDB Authentic snapshot; repeatable and conflict-checked",
    )
    parser.add_argument("--player", type=Path, default=DEFAULT_PLAYER)
    parser.add_argument("--target-map", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-authentic",
        action="store_true",
        help="release gate: accept only PESDB eFootball authentic rows",
    )
    parser.add_argument("--no-name", action="store_true")
    parser.add_argument("--no-position", action="store_true")
    parser.add_argument("--min-coverage", type=float, default=1.0)
    args = parser.parse_args()
    snapshot_paths = [args.snapshot, *args.extra_snapshot]
    snapshot = load_snapshots(
        snapshot_paths,
        require_authentic=args.require_authentic,
    )
    target_map = load_target_map(args.target_map)
    raw = decode_wesys(args.player)
    patched, report = apply_snapshot(
        raw,
        snapshot,
        target_map,
        update_name=not args.no_name,
        update_position=not args.no_position,
    )
    coverage = report["applied"] / report["requested"] if report["requested"] else 1.0
    report["coverage"] = coverage
    report["source_snapshots"] = [str(path.resolve()) for path in snapshot_paths]
    report["target_player"] = str(args.player.resolve())
    report["source_snapshot_sha256"] = {
        str(path): sha256_file(path) for path in snapshot_paths
    }
    report["target_map_sha256"] = (
        sha256_file(args.target_map) if args.target_map else None
    )
    report["target_player_sha256"] = sha256_file(args.player)
    report["patched_player_raw_sha256"] = sha256_bytes(patched)
    if coverage < args.min_coverage:
        raise RuntimeError(
            f"PESDB coverage {coverage:.3f} is below required {args.min_coverage:.3f}"
        )
    encoded = encode_pes21_wesys(patched)
    report["output_player_sha256"] = sha256_bytes(encoded)
    report["content_id"] = content_id(
        {
            "authority": report["authority"],
            "requested": report["requested"],
            "applied": report["applied"],
            "verified_fields": report["verified_fields"],
            "source_snapshot_sha256": report["source_snapshot_sha256"],
            "target_map_sha256": report["target_map_sha256"],
            "target_player_sha256": report["target_player_sha256"],
            "patched_player_raw_sha256": report["patched_player_raw_sha256"],
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "Player.bin").write_bytes(encoded)
    (args.output_dir / "coverage-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: report[key] for key in ("requested", "applied", "skipped", "coverage")}, sort_keys=True))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
