#!/usr/bin/env python3
"""Build an isolated English/Spanish team licensing data pack.

The pack is deliberately detached from the runtime build.  It patches only
the known PES21 ``Team.bin`` name/code fields, emits a selector-name map, and
indexes Football Life uniform descriptors/textures for a later, verified
mobile texture conversion.  No CPK, OBB, NRO, or runtime source is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import unicodedata
import zlib
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("data/eng_spa_license_overrides.json")
DEFAULT_PES21_TEAM = Path(
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/"
    "common/etc/pesdb/Team.bin"
)
DEFAULT_FOOTBALL_LIFE_TEAM = Path(
    "local-debug/licensing-eng-spa-audit/football-life-Team.bin"
)
DEFAULT_FOOTBALL_LIFE_COMPETITION_ENTRY = Path(
    "local-debug/licensing-eng-spa-audit/football-life-CompetitionEntry.bin"
)
DEFAULT_OUTPUT_DIR = Path("local-debug/eng-spa-license-pack")

TEAM_RECORD_SIZE = 1532
TEAM_ID_OFFSET = 8
ENGLISH_NAME_OFFSET = 368
ENGLISH_NAME_SIZE = 70
SHORT_CODE_OFFSETS = (882, 1382)
SHORT_CODE_SIZE = 4

KIT_KINDS = {
    "1st": "p1",
    "2nd": "p2",
    "3rd": "p3",
    "GK1st": "g1",
}
DESCRIPTOR_SUFFIXES = tuple(KIT_KINDS)
TEXTURE_ROOT = "Asset/model/character/uniform/texture/#windx11/"


def resolve_from_root(root: Path, value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_id(payload: dict[str, Any]) -> str:
    canonical = {
        key: value for key, value in payload.items() if key != "content_id"
    }
    encoded = json.dumps(
        canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _ascii(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    try:
        value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must contain ASCII only") from error
    return value


def normalized_ascii(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    folded = folded.encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", " ", folded.upper()).strip()


def flatten_manifest_teams(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    leagues = manifest.get("leagues")
    if not isinstance(leagues, list) or not leagues:
        raise ValueError("manifest.leagues must be a non-empty list")

    flattened: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for league in leagues:
        if not isinstance(league, dict):
            raise ValueError("each league must be an object")
        league_key = _ascii(league.get("key"), "league.key")
        league_label = _ascii(league.get("label"), "league.label")
        competition_id = int(league.get("football_life_competition_id", 0))
        if competition_id <= 0:
            raise ValueError(f"{league_key}: invalid competition ID")
        teams = league.get("teams")
        if not isinstance(teams, list) or not teams:
            raise ValueError(f"{league_key}: teams must be a non-empty list")
        orders: list[int] = []
        for team in teams:
            if not isinstance(team, dict):
                raise ValueError(f"{league_key}: team must be an object")
            team_id = int(team.get("team_id", 0))
            if team_id <= 0 or team_id in seen_ids:
                raise ValueError(f"{league_key}: duplicate/invalid team ID {team_id}")
            seen_ids.add(team_id)
            order = int(team.get("order", 0))
            orders.append(order)
            name = _ascii(team.get("official_name"), f"team {team_id} name")
            short_code = _ascii(team.get("short_code"), f"team {team_id} short code")
            if len(name.encode("ascii")) >= ENGLISH_NAME_SIZE:
                raise ValueError(f"team {team_id} name does not fit Team.bin")
            if not 1 <= len(short_code.encode("ascii")) < SHORT_CODE_SIZE:
                raise ValueError(f"team {team_id} short code must fit 4 bytes")
            integration = str(team.get("catalog_integration", ""))
            policy = str(team.get("team_bin_policy", ""))
            if integration not in {"existing", "pending"}:
                raise ValueError(f"team {team_id}: invalid catalog_integration")
            if policy not in {"patch_existing", "pending_team_record"}:
                raise ValueError(f"team {team_id}: invalid team_bin_policy")
            if (integration == "pending") != (policy == "pending_team_record"):
                raise ValueError(
                    f"team {team_id}: pending integration and Team.bin policy disagree"
                )
            flattened.append(
                {
                    "team_id": team_id,
                    "order": order,
                    "official_name": name,
                    "short_code": short_code,
                    "catalog_integration": integration,
                    "team_bin_policy": policy,
                    "league": league_key,
                    "league_label": league_label,
                    "football_life_competition_id": competition_id,
                    "catalog_category": str(league.get("catalog_category", "")),
                }
            )
        if sorted(orders) != list(range(1, len(teams) + 1)):
            raise ValueError(f"{league_key}: team order must be contiguous from 1")

    if len(flattened) != 40:
        raise ValueError(f"expected 40 teams, found {len(flattened)}")
    pending = [row for row in flattened if row["team_bin_policy"] == "pending_team_record"]
    if [row["team_id"] for row in pending] != [396]:
        raise ValueError("Sunderland (396) must be the sole pending team-record target")
    return flattened


def load_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported licensing manifest schema")
    policy = payload.get("policy")
    table = payload.get("team_table")
    if not isinstance(policy, dict) or not isinstance(table, dict):
        raise ValueError(f"{path}: policy and team_table are required")
    if policy.get("runtime_integration") is not False:
        raise ValueError("licensing pack must remain runtime-disabled")
    expected_table = {
        "schema": "pes21_mobile",
        "record_size": TEAM_RECORD_SIZE,
        "team_id_offset": TEAM_ID_OFFSET,
        "english_name_offset": ENGLISH_NAME_OFFSET,
        "english_name_size": ENGLISH_NAME_SIZE,
        "short_code_offsets": list(SHORT_CODE_OFFSETS),
        "short_code_size": SHORT_CODE_SIZE,
    }
    for key, expected in expected_table.items():
        if table.get(key) != expected:
            raise ValueError(f"{path}: team_table.{key} must be {expected!r}")
    teams = flatten_manifest_teams(payload)
    declared_id = payload.get("content_id")
    calculated_id = content_id(payload)
    if declared_id is not None and declared_id != calculated_id:
        raise ValueError(
            f"{path}: content_id mismatch ({declared_id!r} != {calculated_id!r})"
        )
    payload["content_id"] = calculated_id
    return payload, teams


def decode_wesys_or_raw(path: Path, raw_record_size: int | None = None) -> tuple[bytes, str]:
    data = path.read_bytes()
    if len(data) >= 16 and data[3:8] == b"WESYS":
        sys.path.insert(0, str(ROOT / "tools"))
        from pesdb import decode_wesys

        return decode_wesys(path), "wesys"
    if raw_record_size is not None and len(data) % raw_record_size:
        raise ValueError(
            f"{path}: raw payload is not divisible by {raw_record_size}"
        )
    return data, "raw"


def decode_team_payload(path: Path) -> tuple[bytes, str]:
    return decode_wesys_or_raw(path, TEAM_RECORD_SIZE)


def encode_wesys(raw: bytes) -> bytes:
    compressed = zlib.compress(raw, level=9)
    return b"\xff\x10\x81WESYS" + struct.pack(
        "<II", len(compressed), len(raw)
    ) + compressed


def split_team_rows(raw: bytes) -> list[bytes]:
    if len(raw) % TEAM_RECORD_SIZE:
        raise ValueError(
            f"Team.bin decoded size {len(raw)} is not divisible by {TEAM_RECORD_SIZE}"
        )
    return [
        raw[offset : offset + TEAM_RECORD_SIZE]
        for offset in range(0, len(raw), TEAM_RECORD_SIZE)
    ]


def team_id(row: bytes) -> int:
    return struct.unpack_from("<I", row, TEAM_ID_OFFSET)[0]


def fixed_ascii(row: bytes, offset: int, size: int) -> str:
    return row[offset : offset + size].split(b"\0", 1)[0].decode(
        "utf-8", errors="replace"
    )


def set_fixed_ascii(row: bytearray, offset: int, size: int, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) >= size:
        raise ValueError(f"ASCII value does not fit {size}-byte field: {value}")
    row[offset : offset + size] = encoded + bytes(size - len(encoded))


def changed_ranges(before: bytes, after: bytes) -> list[tuple[int, int]]:
    changed = [index for index, (left, right) in enumerate(zip(before, after)) if left != right]
    ranges: list[tuple[int, int]] = []
    for index in changed:
        if not ranges or index > ranges[-1][1] + 1:
            ranges.append((index, index))
        else:
            ranges[-1] = (ranges[-1][0], index)
    return ranges


def range_allowed(ranges: Iterable[tuple[int, int]], allowed: Iterable[tuple[int, int]]) -> bool:
    allowed_ranges = list(allowed)
    return all(
        any(start >= left and end <= right for left, right in allowed_ranges)
        for start, end in ranges
    )


def patch_team_rows(
    raw: bytes, teams: list[dict[str, Any]]
) -> tuple[bytes, dict[str, Any]]:
    original_rows = split_team_rows(raw)
    rows = [bytearray(row) for row in original_rows]
    indexes: dict[int, int] = {}
    for index, row in enumerate(original_rows):
        identifier = team_id(row)
        if identifier == 0 or identifier in indexes:
            raise ValueError(f"Team.bin contains invalid duplicate team ID {identifier}")
        indexes[identifier] = index

    target_reports: list[dict[str, Any]] = []
    changed_team_rows = 0
    changed_bytes = 0
    pending_missing: list[int] = []
    for target in teams:
        identifier = int(target["team_id"])
        policy = target["team_bin_policy"]
        row_index = indexes.get(identifier)
        if policy == "pending_team_record":
            if row_index is None:
                pending_missing.append(identifier)
                status = "pending_missing"
            else:
                status = "pending_present_unpatched"
            target_reports.append(
                {
                    **target,
                    "team_bin_status": status,
                    "record_index": row_index,
                    "old_name": (
                        fixed_ascii(original_rows[row_index], ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE)
                        if row_index is not None
                        else None
                    ),
                    "new_name": None,
                    "old_short_codes": (
                        [
                            fixed_ascii(original_rows[row_index], offset, SHORT_CODE_SIZE)
                            for offset in SHORT_CODE_OFFSETS
                        ]
                        if row_index is not None
                        else None
                    ),
                    "changed_ranges": [],
                    "changed_bytes": 0,
                }
            )
            continue

        if row_index is None:
            raise ValueError(f"required PES21 team {identifier} is absent from Team.bin")
        before = bytes(rows[row_index])
        old_name = fixed_ascii(before, ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE)
        old_codes = [
            fixed_ascii(before, offset, SHORT_CODE_SIZE)
            for offset in SHORT_CODE_OFFSETS
        ]
        set_fixed_ascii(rows[row_index], ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE, target["official_name"])
        for offset in SHORT_CODE_OFFSETS:
            set_fixed_ascii(rows[row_index], offset, SHORT_CODE_SIZE, target["short_code"])
        after = bytes(rows[row_index])
        ranges = changed_ranges(before, after)
        allowed = [
            (ENGLISH_NAME_OFFSET, ENGLISH_NAME_OFFSET + ENGLISH_NAME_SIZE - 1),
            *[
                (offset, offset + SHORT_CODE_SIZE - 1)
                for offset in SHORT_CODE_OFFSETS
            ],
        ]
        if not range_allowed(ranges, allowed):
            raise RuntimeError(f"team {identifier}: patch escaped approved Team.bin fields")
        byte_count = sum(end - start + 1 for start, end in ranges)
        if byte_count:
            changed_team_rows += 1
            changed_bytes += byte_count
        target_reports.append(
            {
                **target,
                "team_bin_status": "patched" if byte_count else "already_current",
                "record_index": row_index,
                "old_name": old_name,
                "new_name": target["official_name"],
                "old_short_codes": old_codes,
                "new_short_code": target["short_code"],
                "changed_ranges": [[start, end] for start, end in ranges],
                "changed_bytes": byte_count,
            }
        )

    patched_raw = b"".join(bytes(row) for row in rows)
    unrelated_rows = 0
    target_ids = {int(target["team_id"]) for target in teams}
    for index, (before, after) in enumerate(zip(original_rows, split_team_rows(patched_raw))):
        if team_id(before) not in target_ids:
            if before != after:
                raise RuntimeError(f"unrelated Team.bin row changed at index {index}")
            unrelated_rows += 1

    report = {
        "record_size": TEAM_RECORD_SIZE,
        "records_before": len(original_rows),
        "records_after": len(rows),
        "target_count": len(teams),
        "patched_team_rows": changed_team_rows,
        "changed_bytes": changed_bytes,
        "unrelated_rows_byte_identical": unrelated_rows,
        "pending_missing_team_ids": pending_missing,
        "teams": sorted(target_reports, key=lambda row: int(row["team_id"])),
    }
    return patched_raw, report


def validate_football_life_sources(
    manifest: dict[str, Any],
    teams: list[dict[str, Any]],
    team_path: Path,
    competition_path: Path,
    allow_source_drift: bool,
) -> dict[str, Any]:
    if not team_path.is_file():
        raise FileNotFoundError(f"Football Life Team.bin not found: {team_path}")
    if not competition_path.is_file():
        raise FileNotFoundError(
            f"Football Life CompetitionEntry.bin not found: {competition_path}"
        )
    configured = manifest.get("sources", {})
    hashes = {
        "team": sha256_file(team_path),
        "competition_entry": sha256_file(competition_path),
    }
    expected_hashes = {
        "team": configured.get("football_life_team", {}).get("sha256"),
        "competition_entry": configured.get(
            "football_life_competition_entry", {}
        ).get("sha256"),
    }
    for label, observed in hashes.items():
        expected = expected_hashes[label]
        if expected and observed.lower() != str(expected).lower() and not allow_source_drift:
            raise RuntimeError(
                f"Football Life {label} SHA-256 mismatch: expected {expected}, "
                f"found {observed}; use --allow-source-drift only after reviewing it"
            )

    team_raw, _encoding = decode_team_payload(team_path)
    source_rows = split_team_rows(team_raw)
    source_by_id = {team_id(row): row for row in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("Football Life Team.bin contains duplicate team IDs")

    competition_raw, _competition_encoding = decode_wesys_or_raw(
        competition_path, 12
    )
    if len(competition_raw) % 12:
        raise ValueError("Football Life CompetitionEntry.bin has a partial row")
    competition_orders: dict[tuple[int, int], int] = {}
    for offset in range(0, len(competition_raw), 12):
        identifier, _entry_id, packed = struct.unpack_from(
            "<III", competition_raw, offset
        )
        competition_id = packed & 0xFF
        order = packed >> 8
        competition_orders[(competition_id, identifier)] = order

    verified: list[dict[str, Any]] = []
    for target in teams:
        identifier = int(target["team_id"])
        source_row = source_by_id.get(identifier)
        if source_row is None:
            raise ValueError(f"Football Life Team.bin is missing team {identifier}")
        source_name = fixed_ascii(source_row, ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE)
        source_code = fixed_ascii(source_row, SHORT_CODE_OFFSETS[0], SHORT_CODE_SIZE)
        if normalized_ascii(source_name) != normalized_ascii(target["official_name"]):
            raise ValueError(
                f"team {identifier}: manifest name {target['official_name']!r} "
                f"does not match Football Life {source_name!r}"
            )
        if source_code != target["short_code"]:
            raise ValueError(
                f"team {identifier}: manifest code {target['short_code']!r} "
                f"does not match Football Life {source_code!r}"
            )
        key = (int(target["football_life_competition_id"]), identifier)
        source_order = competition_orders.get(key)
        if source_order != int(target["order"]):
            raise ValueError(
                f"team {identifier}: competition order {source_order!r} "
                f"does not match manifest {target['order']}"
            )
        verified.append(
            {
                "team_id": identifier,
                "source_name_ascii": unicodedata.normalize("NFKD", source_name)
                .encode("ascii", errors="ignore")
                .decode("ascii"),
                "source_short_code": source_code,
                "competition_id": key[0],
                "competition_order": source_order,
            }
        )
    return {
        "team_path": str(team_path),
        "team_sha256": hashes["team"],
        "team_records": len(source_rows),
        "competition_entry_path": str(competition_path),
        "competition_entry_sha256": hashes["competition_entry"],
        "competition_entry_records": len(competition_raw) // 12,
        "verified_teams": verified,
    }


def cpk_member_name(row: dict[str, Any]) -> str:
    return "/".join(
        part
        for part in (str(row.get("DirName") or ""), str(row.get("FileName") or ""))
        if part and part != "<NULL>"
    ).replace("\\", "/")


def index_cpk(path: Path, key: str, precedence: int) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "tools"))
    from prepare_runtime import read_cpk_packet

    with path.open("rb") as source:
        header = read_cpk_packet(source, 0, b"CPK ")[0]
        rows = read_cpk_packet(source, int(header["TocOffset"]), b"TOC ")
    by_lower: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = cpk_member_name(row)
        if name:
            by_lower.setdefault(name.lower(), {"name": name, "row": row})
    return {
        "key": key,
        "path": path,
        "precedence": precedence,
        "rows": by_lower,
        "member_count": len(rows),
        "toc_offset": int(header["TocOffset"]),
        "content_offset": int(header["ContentOffset"]),
        "data_base": min(int(header["TocOffset"]), int(header["ContentOffset"])),
    }


def read_cpk_member(source: dict[str, Any], member: str) -> bytes | None:
    entry = source["rows"].get(member.lower())
    if entry is None:
        return None
    row = entry["row"]
    file_size = int(row["FileSize"])
    if file_size != int(row["ExtractSize"]):
        return None
    with source["path"].open("rb") as stream:
        stream.seek(source["data_base"] + int(row["FileOffset"]))
        value = stream.read(file_size)
    if len(value) != file_size:
        raise RuntimeError(f"truncated CPK member {member} in {source['path']}")
    return value


def source_entry(source: dict[str, Any], member: str, *, hash_payload: bool = False) -> dict[str, Any] | None:
    entry = source["rows"].get(member.lower())
    if entry is None:
        return None
    row = entry["row"]
    packed_size = int(row["FileSize"])
    extract_size = int(row["ExtractSize"])
    result: dict[str, Any] = {
        "archive": source["key"],
        "member": entry["name"],
        "packed_size": packed_size,
        "extract_size": extract_size,
        "compressed": packed_size != extract_size,
    }
    if hash_payload and packed_size == extract_size:
        payload = read_cpk_member(source, entry["name"])
        if payload is not None:
            result["sha256"] = sha256_bytes(payload)
    return result


def choose_member(
    sources: list[dict[str, Any]], member: str, *, hash_payload: bool = False
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for source in sources:
        found = source_entry(source, member, hash_payload=hash_payload)
        if found is not None:
            candidates.append(found)
    if not candidates:
        return None
    # Sources are ordered low-to-high; the last available member wins.
    winner = dict(candidates[-1])
    winner["candidates"] = candidates
    return winner


def discover_kit_paths(
    root: Path, manifest: dict[str, Any], explicit: list[Path], football_life_root: Path | None
) -> list[tuple[str, Path, int]]:
    if explicit:
        result: list[tuple[str, Path, int]] = []
        for index, path in enumerate(explicit):
            resolved = resolve_from_root(root, path)
            if resolved.is_file():
                result.append((resolved.stem, resolved, index))
        return result

    if football_life_root is None:
        return []

    discovered: list[tuple[str, Path, int]] = []
    for item in manifest.get("sources", {}).get("kit_cpks", []):
        if not isinstance(item, dict):
            continue
        relative = Path(str(item.get("path", "")))
        path = relative if relative.is_absolute() else football_life_root / relative
        if path.is_file():
            discovered.append((str(item.get("key", path.stem)), path.resolve(), int(item.get("precedence", 0))))
    return discovered


def mobile_template_status(root: Path, team_id: int, mobile_root: Path | None) -> dict[str, Any]:
    if mobile_root is None or not mobile_root.is_dir():
        return {"status": "unavailable", "files": {}}
    files: dict[str, Any] = {}
    real_count = 0
    generic_count = 0
    for kind in DESCRIPTOR_SUFFIXES:
        directory = mobile_root / str(team_id)
        real_path = directory / f"{team_id}_DEF_{kind}_realUni.bin"
        generic_path = directory / f"{team_id}_DEF_{kind}.bin"
        path = real_path if real_path.is_file() else generic_path
        if not path.is_file():
            files[kind] = {"status": "missing"}
            continue
        size = path.stat().st_size
        if size == 120:
            status = "native_real_descriptor"
            real_count += 1
        elif size == 96:
            status = "generic_descriptor"
            generic_count += 1
        else:
            status = "unexpected_size"
        files[kind] = {"status": status, "size": size, "member_name": path.name}
    if real_count == len(DESCRIPTOR_SUFFIXES):
        overall = "all_native_real"
    elif real_count:
        overall = "partial_native_real"
    elif generic_count or any(item.get("status") == "missing" for item in files.values()):
        overall = "generic_or_missing"
    else:
        overall = "unverified"
    return {"status": overall, "files": files}


def inventory_kits(
    root: Path,
    teams: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    mobile_root: Path | None,
) -> dict[str, Any]:
    source_rows = [
        {
            "key": source["key"],
            "path": source["path"].name,
            "precedence": source["precedence"],
            "member_count": source["member_count"],
        }
        for source in sources
    ]
    team_outputs: list[dict[str, Any]] = []
    descriptor_complete = 0
    texture_complete = 0
    template_counts = {
        "all_native_real": 0,
        "partial_native_real": 0,
        "generic_or_missing": 0,
        "unavailable": 0,
        "unverified": 0,
    }

    for target in sorted(teams, key=lambda row: int(row["team_id"])):
        identifier = int(target["team_id"])
        team_output: dict[str, Any] = {
            "team_id": identifier,
            "official_name": target["official_name"],
            "catalog_integration": target["catalog_integration"],
            "kits": {},
        }
        all_descriptors = True
        all_textures = True
        for kind, token in KIT_KINDS.items():
            descriptor = (
                f"common/character0/model/character/uniform/team/{identifier}/"
                f"{identifier}_DEF_{kind}_realUni.bin"
            )
            descriptor_source = choose_member(sources, descriptor, hash_payload=True)
            if descriptor_source is None:
                all_descriptors = False
            texture_members: list[dict[str, Any]] = []
            if sources:
                pattern = re.compile(
                    rf"^{re.escape(TEXTURE_ROOT)}u{identifier:04d}{re.escape(token)}(?:_[^/]*)?\.ftex$",
                    re.IGNORECASE,
                )
                names: set[str] = set()
                for source in sources:
                    for entry in source["rows"].values():
                        name = str(entry["name"])
                        if pattern.match(name):
                            names.add(name)
                for name in sorted(names, key=str.lower):
                    selected = choose_member(sources, name, hash_payload=False)
                    if selected is not None:
                        texture_members.append(selected)
            base_texture = next(
                (item for item in texture_members if re.search(rf"u{identifier:04d}{re.escape(token)}\.ftex$", item["member"], re.IGNORECASE)),
                None,
            )
            if base_texture is None:
                all_textures = False
            team_output["kits"][kind] = {
                "descriptor": descriptor_source,
                "texture_members": texture_members,
                "source_status": (
                    "source_ready" if descriptor_source is not None and base_texture is not None else "partial_or_missing"
                ),
                "conversion_status": "conversion_pending" if descriptor_source is not None and base_texture is not None else "source_missing",
            }
        if all_descriptors:
            descriptor_complete += 1
        if all_textures:
            texture_complete += 1
        template = mobile_template_status(root, identifier, mobile_root)
        template_counts[template["status"]] = template_counts.get(template["status"], 0) + 1
        team_output["mobile_template"] = template
        team_output["overall_source_status"] = (
            "source_ready" if all_descriptors and all_textures else "partial_or_missing"
        )
        team_output["overall_conversion_status"] = (
            "conversion_pending" if all_descriptors and all_textures else "blocked_missing_source"
        )
        team_outputs.append(team_output)

    return {
        "schema_version": 1,
        "source_policy": {
            "winner": "highest precedence archive per member",
            "precedence_direction": "base < season_a < season_b < season_c",
            "descriptor_hashes": True,
            "texture_hashes": False,
            "direct_pc_texture_transplant": False,
        },
        "archives": source_rows,
        "counts": {
            "teams": len(teams),
            "descriptor_complete_teams": descriptor_complete,
            "texture_complete_teams": texture_complete,
            "conversion_pending_teams": sum(
                1 for item in team_outputs if item["overall_conversion_status"] == "conversion_pending"
            ),
            "mobile_template_all_native_real": template_counts.get("all_native_real", 0),
            "mobile_template_partial_native_real": template_counts.get("partial_native_real", 0),
            "mobile_template_generic_or_missing": template_counts.get("generic_or_missing", 0),
            "mobile_template_unavailable": template_counts.get("unavailable", 0),
        },
        "teams": team_outputs,
    }


def selector_overrides(team_report: dict[str, Any], manifest_id: str) -> dict[str, Any]:
    rows = []
    for team in team_report["teams"]:
        rows.append(
            {
                "team_id": int(team["team_id"]),
                "league": team["league"],
                "league_label": team["league_label"],
                "order": int(team["order"]),
                "display_name": str(team["official_name"]).upper(),
                "official_name": team["official_name"],
                "short_code": team["short_code"],
                "catalog_integration": team["catalog_integration"],
                "team_bin_status": team["team_bin_status"],
            }
        )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_by": "tools/build_eng_spa_license_pack.py",
        "manifest_content_id": manifest_id,
        "runtime_integration": False,
        "teams": sorted(rows, key=lambda row: int(row["team_id"])),
    }
    payload["content_id"] = content_id(payload)
    return payload


def render_report(
    manifest: dict[str, Any],
    team_report: dict[str, Any],
    kit_report: dict[str, Any],
) -> str:
    by_team = {int(row["team_id"]): row for row in kit_report["teams"]}
    lines = [
        "# English and Spanish License Pack",
        "",
        "This generated pack stages official English/Spanish club names and the",
        "Football Life kit source inventory without touching runtime source, CPK/OBB",
        "archives, the NRO build, or stable release files.",
        "",
        "## Status",
        "",
        f"- Manifest content ID: `{manifest['content_id']}`",
        f"- PES21 team rows: {team_report['records_before']}",
        f"- Existing target rows patched: {team_report['patched_team_rows']}",
        f"- Unrelated rows byte-identical: {team_report['unrelated_rows_byte_identical']}",
        f"- Pending missing team IDs: {', '.join(map(str, team_report['pending_missing_team_ids']))}",
        f"- Kit descriptor sources complete: {kit_report['counts']['descriptor_complete_teams']}/40",
        f"- Kit base-texture sources complete: {kit_report['counts']['texture_complete_teams']}/40",
        "- Runtime integration: deferred",
        "- PC FTEX to mobile cooked-texture conversion: pending",
        "",
        "## Generated local output",
        "",
        "- `Team.bin`: 736-row PES21 table with only official name/code fields changed",
        "- `selector-name-overrides.json`: official uppercase selector labels, including pending Sunderland",
        "- `kit-source-manifest.json`: winning descriptor/texture member per CPK precedence",
        "- `validation-report.json`: hashes, byte-preservation checks, and safety warnings",
        "",
        "The default output directory is `local-debug/eng-spa-license-pack`, which is",
        "ignored by git. These artifacts are not embedded by the current Makefile.",
        "",
        "## League targets",
        "",
    ]
    for league in manifest["leagues"]:
        lines.extend(
            [
                f"### {league['label']}",
                "",
                "| Pos | ID | Official name | Code | Team row | Kit source |",
                "|---:|---:|---|---|---|---|",
            ]
        )
        team_report_by_id = {
            int(row["team_id"]): row for row in team_report["teams"]
        }
        for target in league["teams"]:
            identifier = int(target["team_id"])
            row = team_report_by_id[identifier]
            kits = by_team[identifier]
            lines.append(
                f"| {target['order']} | {identifier} | {target['official_name']} | "
                f"{target['short_code']} | {row['team_bin_status']} | "
                f"{kits['overall_source_status']} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Sunderland gate",
            "",
            "Football Life contains Sunderland AFC as team `396`, but the tested PES21",
            "mobile Team.bin has no row `396` and the current selector has no safe native",
            "entry for it. The generator records Sunderland as the twentieth English team",
            "but does not append/replace a Team.bin row and does not edit the selector.",
            "",
            "A later runtime phase must choose a validated physical slot or prove that all",
            "required database, roster, tactics, badge, uniform, and CPK member additions are",
            "supported together.",
            "",
            "## Kit boundary",
            "",
            "All 40 targets have four 120-byte Football Life real-uniform descriptors and",
            "matching base FTEX textures. The source winner is resolved per member with",
            "`dt34_g4.cpk < data_s2526a.cpk < data_s2526b.cpk < data_s2526c.cpk`.",
            "",
            "That is source readiness, not mobile readiness. PES21 Mobile uses UE4 cooked",
            "texture assets while the Football Life files are PC FTEX. Raw FTEX replacement",
            "is therefore prohibited. The existing CPK repacker also replaces known member",
            "names only; it cannot create Sunderland's absent members. A conversion phase",
            "must decode FTEX, preserve alpha/material channels, encode against a verified",
            "PES21 Mobile uniform texture template, repack a detachable test archive, and",
            "validate in Ryujinx/hardware before broad rollout.",
            "",
            "## Commands",
            "",
            "```powershell",
            "python tools/build_eng_spa_license_pack.py",
            "python tools/build_eng_spa_license_pack.py --check",
            "python -m pytest -q tests/test_eng_spa_license_pack.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True) + "\n"


def write_or_check(path: Path, value: bytes | str, check: bool) -> None:
    expected = value.encode("utf-8") if isinstance(value, str) else value
    if check:
        if not path.is_file() or path.read_bytes() != expected:
            raise RuntimeError(f"generated file is stale or missing: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)


def build_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = args.root.resolve()
    manifest_path = resolve_from_root(root, args.manifest)
    manifest, teams = load_manifest(manifest_path)
    pes21_team_path = resolve_from_root(root, args.pes21_team)
    if not pes21_team_path.is_file():
        raise FileNotFoundError(f"PES21 Team.bin not found: {pes21_team_path}")
    source_hash = sha256_file(pes21_team_path)
    expected_hash = (
        manifest.get("sources", {})
        .get("pes21_mobile_team", {})
        .get("sha256")
    )
    if expected_hash and source_hash.lower() != str(expected_hash).lower() and not args.allow_source_drift:
        raise RuntimeError(
            f"PES21 Team.bin SHA-256 mismatch: expected {expected_hash}, found {source_hash}; "
            "use --allow-source-drift only after reviewing the table revision"
        )

    football_life_team_path = resolve_from_root(root, args.football_life_team)
    football_life_competition_path = resolve_from_root(
        root, args.football_life_competition_entry
    )
    football_life_validation = validate_football_life_sources(
        manifest,
        teams,
        football_life_team_path,
        football_life_competition_path,
        args.allow_source_drift,
    )

    decoded, encoding = decode_team_payload(pes21_team_path)
    patched_raw, team_report = patch_team_rows(decoded, teams)
    team_report.update(
        {
            "source_path": str(pes21_team_path),
            "source_sha256": source_hash,
            "source_encoding": encoding,
            "output_decoded_sha256": sha256_bytes(patched_raw),
        }
    )

    explicit_cpk = [Path(value) for value in args.football_life_cpk]
    football_life_root = (
        resolve_from_root(root, args.football_life_root)
        if args.football_life_root is not None
        else None
    )
    discovered = discover_kit_paths(root, manifest, explicit_cpk, football_life_root)
    indexed_sources = [index_cpk(path, key, precedence) for key, path, precedence in discovered]
    indexed_sources.sort(key=lambda item: (int(item["precedence"]), item["key"]))
    mobile_root_value = manifest.get("sources", {}).get("mobile_uniform_root")
    mobile_root = resolve_from_root(root, Path(str(mobile_root_value))) if mobile_root_value else None
    kit_report = inventory_kits(root, teams, indexed_sources, mobile_root)
    kit_report["manifest_content_id"] = manifest["content_id"]
    kit_report["content_id"] = content_id(kit_report)

    overrides = selector_overrides(team_report, manifest["content_id"])
    output_dir = resolve_from_root(root, args.output_dir)
    output_files = {
        "Team.bin": encode_wesys(patched_raw),
        "selector-name-overrides.json": json_text(overrides),
        "kit-source-manifest.json": json_text(kit_report),
        "README.md": render_report(manifest, team_report, kit_report),
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "pack": "eng_spa_license_pack",
        "manifest_content_id": manifest["content_id"],
        "runtime_integration": False,
        "source": {
            "pes21_team": {
                "path": str(pes21_team_path),
                "sha256": source_hash,
            },
            "football_life_team": {
                "path": str(football_life_team_path),
                "sha256": football_life_validation["team_sha256"],
                "records": football_life_validation["team_records"],
            },
            "football_life_competition_entry": {
                "path": str(football_life_competition_path),
                "sha256": football_life_validation["competition_entry_sha256"],
                "records": football_life_validation["competition_entry_records"],
                "verified_target_teams": len(football_life_validation["verified_teams"]),
            },
            "kit_archives_indexed": len(indexed_sources),
        },
        "team_patch": team_report,
        "kits": {
            "content_id": kit_report["content_id"],
            "counts": kit_report["counts"],
        },
        "outputs": {
            name: {
                "path": name,
                "size": len(value.encode("utf-8")) if isinstance(value, str) else len(value),
                "sha256": sha256_bytes(value.encode("utf-8") if isinstance(value, str) else value),
            }
            for name, value in output_files.items()
        },
        "warnings": [
            "This pack is data-only; runtime selector and Makefile integration are intentionally deferred.",
            "Sunderland AFC remains pending because PES21 Team.bin has no team 396 row.",
            "Football Life PC uniform descriptors/textures are indexed for conversion, not transplanted into mobile assets.",
        ],
    }
    report["content_id"] = content_id(report)
    output_files["validation-report.json"] = json_text(report)
    for name, value in output_files.items():
        write_or_check(output_dir / name, value, args.check)
    return report


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pes21-team", type=Path, default=DEFAULT_PES21_TEAM)
    parser.add_argument("--football-life-team", type=Path, default=DEFAULT_FOOTBALL_LIFE_TEAM)
    parser.add_argument(
        "--football-life-competition-entry",
        type=Path,
        default=DEFAULT_FOOTBALL_LIFE_COMPETITION_ENTRY,
    )
    parser.add_argument("--football-life-root", type=Path)
    parser.add_argument("--football-life-cpk", action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--allow-source-drift", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_pack(args)
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
