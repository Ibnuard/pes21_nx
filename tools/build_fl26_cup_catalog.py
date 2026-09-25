#!/usr/bin/env python3
"""Build the public Cup ID/team manifest from a user's local FL26 install.

Only IDs, names, and validated playable-team mappings are written to the
repository. Original competition emblems are copied byte-for-byte only when
--logo-output points to an ignored, local runtime directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from prepare_runtime import read_cpk_packet  # noqa: E402


# PC Cup ID, parent league ID, primary selector category, visible name,
# competition key, optional user-supplied logo. Selector order is intentional;
# save format v3 migrates the earlier 17-entry catalog's indices.
CUPS = (
    (15, 9, "english_league", "FA CUP", "ENGLAND_D1_CUP", None),
    (17, 11, "spanish_league", "COPA DEL REY", "SPAIN_D1_CUP", None),
    (16, 10, "serie_a", "COPPA ITALIA", "ITALY_D1_CUP", None),
    (35, 0, "national_asia_oceania", "AFC CUP", "AFC_ASIA_CUP", "cup-afc.png"),
    (33, 0, "national_europe", "UEFA EURO", "EURO", "cup-euro.png"),
    (27, 0, None, "WORLD CUP", "FIFA_WORLD_CUP", "cup-world.png"),
)

CUP_BRACKET_LIMITS = {15: 32, 17: 32, 16: 24, 35: 16, 33: 16, 27: 32}


def index_cpk(path: Path) -> tuple[dict[str, dict], int]:
    with path.open("rb") as stream:
        header = read_cpk_packet(stream, 0, b"CPK ")[0]
        rows = read_cpk_packet(stream, int(header["TocOffset"]), b"TOC ")
    base = min(int(header["TocOffset"]), int(header["ContentOffset"]))
    return {
        "/".join((str(row.get("DirName") or ""), str(row["FileName"]))): row
        for row in rows
    }, base


def cpk_member(path: Path, index: dict[str, dict], base: int,
               name: str) -> bytes:
    row = index.get(name)
    if row is None:
        raise ValueError(f"{path}: missing {name}")
    with path.open("rb") as stream:
        stream.seek(base + int(row["FileOffset"]))
        data = stream.read(int(row["FileSize"]))
    if len(data) != int(row["FileSize"]):
        raise ValueError(f"{path}: truncated {name}")
    return data


def decoded_member(path: Path, index: dict[str, dict], base: int,
                   name: str) -> bytes:
    data = cpk_member(path, index, base, name)
    return zlib.decompress(data[16:]) if data[3:8] == b"WESYS" else data


def competition_keys(payload: bytes) -> dict[int, str]:
    if len(payload) % 36:
        raise ValueError("FL26 Competition.bin has a partial record")
    result = {}
    for offset in range(0, len(payload), 36):
        row = payload[offset:offset + 36]
        competition_id = int.from_bytes(row[4:6], "big")
        name = row[8:36].split(b"\0", 1)[0].decode("ascii")
        if competition_id in result:
            raise ValueError(f"duplicate FL26 competition {competition_id}")
        result[competition_id] = name
    return result


def competition_members(payload: bytes) -> dict[int, list[int]]:
    if len(payload) % 12:
        raise ValueError("FL26 CompetitionEntry.bin has a partial record")
    ordered: dict[int, list[tuple[int, int]]] = {}
    for offset in range(0, len(payload), 12):
        team_id, _entry_id, packed = struct.unpack_from("<III", payload, offset)
        ordered.setdefault(packed & 0xFF, []).append((packed >> 8, team_id))
    result = {}
    for competition_id, entries in ordered.items():
        seen = set()
        result[competition_id] = []
        for _order, team_id in sorted(entries):
            if team_id not in seen:
                result[competition_id].append(team_id)
                seen.add(team_id)
    return result


def select_logo(cup_id: int, logo_index: dict[str, dict]) -> str:
    stem = f"emb_{cup_id:04d}"
    for suffix in ("_w_l.png", "_l.png", "_b_l.png"):
        name = stem + suffix
        if "common/render/symbol/emblemLc/" + name in logo_index:
            return name
    raise ValueError(f"FL26 logo missing for Cup {cup_id}")


def build_manifest(root: Path, catalog_path: Path) -> dict:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    categories = {row["key"]: (index, row)
                  for index, row in enumerate(catalog["categories"])}
    playable = {team for row in catalog["categories"]
                for team in row["team_ids"]}
    competition_path = root / "download/data_s2526.cpk"
    entry_path = root / "download/data_s2526c.cpk"
    logo_path = root / "Data/dt15_x64.cpk"
    competition_index, competition_base = index_cpk(competition_path)
    entry_index, entry_base = index_cpk(entry_path)
    logo_index, _logo_base = index_cpk(logo_path)
    competition_raw = decoded_member(
        competition_path, competition_index, competition_base,
        "common/etc/pesdb/Competition.bin")
    entry_raw = decoded_member(
        entry_path, entry_index, entry_base,
        "common/etc/pesdb/CompetitionEntry.bin")
    keys = competition_keys(competition_raw)
    memberships = competition_members(entry_raw)
    cups = []
    for cup_id, league_id, category_key, label, expected_key, custom_logo in CUPS:
        if keys.get(cup_id) != expected_key:
            raise ValueError(f"Cup {cup_id}: expected {expected_key}, got {keys.get(cup_id)}")
        if category_key is not None and category_key not in categories:
            raise ValueError(f"selector category missing: {category_key}")
        category_index = categories[category_key][0] if category_key else 255
        # Domestic Cups can include second-division clubs. International Cups
        # span national-team categories. In both cases, use FL26's own ordered
        # CompetitionEntry membership, filtered to playable Switch teams.
        pool = [team for team in memberships.get(cup_id, [])
                if team in playable]
        if cup_id == 27:
            # The PC World Cup entry has only 18 Switch-playable teams. Keep
            # its original order, then offer the remaining playable national
            # teams so a 32-team Cup can be filled without duplicates.
            seen = set(pool)
            for category in catalog["categories"]:
                if not category["key"].startswith("national_"):
                    continue
                for team in category["team_ids"]:
                    if team not in seen:
                        pool.append(team)
                        seen.add(team)
        limit = CUP_BRACKET_LIMITS[cup_id]
        if len(pool) < limit or len(pool) > 512:
            raise ValueError(f"Cup {cup_id}: {len(pool)} playable teams")
        cups.append({
            "competition_id": cup_id,
            "league_competition_id": league_id,
            "name": label,
            "category_key": category_key,
            "category_index": category_index,
            "bracket_limit": limit,
            "team_ids": pool,
            "logo_file": custom_logo or select_logo(cup_id, logo_index),
        })
    cups.append({
        "competition_id": 0,
        "league_competition_id": 0,
        "name": "FOOTBALLNX CUP",
        "category_key": None,
        "category_index": 255,
        "bracket_limit": 32,
        "team_ids": [],
        "logo_file": None,
    })
    return {
        "schema_version": 1,
        "source": "SP Football Life 2026 local Competition.bin, "
                  "CompetitionEntry.bin and dt15_x64.cpk",
        "competition_sha256": hashlib.sha256(competition_raw).hexdigest(),
        "entry_sha256": hashlib.sha256(entry_raw).hexdigest(),
        "catalog_content_id": catalog["content_id"],
        "cups": cups,
    }


def render_header(manifest: dict) -> str:
    cups = manifest["cups"]
    lines = [
        "/* Generated by tools/build_fl26_cup_catalog.py; do not edit. */",
        "#ifndef PES21_FL26_CUP_CATALOG_GENERATED_H",
        "#define PES21_FL26_CUP_CATALOG_GENERATED_H",
        "#include <stdint.h>",
        "typedef struct {",
        "  uint16_t competition_id;",
        "  uint8_t category_index;",
        "  uint8_t bracket_limit;",
        "  const char *name;",
        "  const char *logo_file;",
        "  const uint32_t *team_ids;",
        "  uint32_t pool_count;",
        "} Fl26CupCatalogEntry;",
    ]
    for index, cup in enumerate(cups[:-1]):
        teams = ", ".join(f"{team}u" for team in cup["team_ids"])
        lines.append(f"static const uint32_t fl26_cup_pool_{index}[] = {{{teams}}};")
    lines.append("static const Fl26CupCatalogEntry fl26_cup_catalog[] = {")
    for index, cup in enumerate(cups[:-1]):
        lines.append(
            f'  {{{cup["competition_id"]}u, {cup["category_index"]}u, '
            f'{cup["bracket_limit"]}u, "{cup["name"]}", '
            f'"{cup["logo_file"]}", fl26_cup_pool_{index}, '
            f'{len(cup["team_ids"])}u}},'
        )
    lines.append('  {0u, 255u, 32u, "FOOTBALLNX CUP", 0, 0, 0u},')
    lines.extend((
        "};",
        f"#define FL26_CUP_CUSTOM_INDEX {len(cups) - 1}u",
        "#define FL26_CUP_CATALOG_COUNT ((uint32_t)(sizeof(fl26_cup_catalog) / "
        "sizeof(fl26_cup_catalog[0])))",
        "#endif",
        "",
    ))
    return "\n".join(lines)


def export_logos(root: Path, cups: list[dict], output: Path) -> None:
    path = root / "Data/dt15_x64.cpk"
    index, base = index_cpk(path)
    output.mkdir(parents=True, exist_ok=True)
    for cup in cups[:-1]:
        name = cup["logo_file"]
        if not name.startswith("emb_"):
            target = output / name
            if not target.is_file() or not target.read_bytes().startswith(
                    b"\x89PNG\r\n\x1a\n"):
                raise FileNotFoundError(f"user-supplied Cup logo missing: {target}")
            continue
        source = "common/render/symbol/emblemLc/" + name
        data = cpk_member(path, index, base, source)
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 2_000_000:
            raise ValueError(f"invalid competition emblem: {name}")
        target = output / name
        if target.exists() and target.read_bytes() != data:
            raise FileExistsError(f"refusing to replace different logo: {target}")
        if not target.exists():
            target.write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path,
                        default=ROOT / "data/exhibition_team_catalog.json")
    parser.add_argument("--manifest-output", type=Path,
                        default=ROOT / "data/fl26_cup_catalog.json")
    parser.add_argument("--header-output", type=Path,
                        default=ROOT / "source/fl26_cup_catalog_generated.h")
    parser.add_argument("--logo-output", type=Path,
                        help="ignored runtime CupLogos directory; copies original PNGs")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build_manifest(args.fl26_root, args.catalog)
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"
    header_text = render_header(manifest)
    if args.check:
        if (args.manifest_output.read_text(encoding="utf-8") != manifest_text or
                args.header_output.read_text(encoding="utf-8") != header_text):
            raise SystemExit("FL26 Cup catalog is out of date")
    else:
        args.manifest_output.write_text(manifest_text, encoding="utf-8")
        args.header_output.write_text(header_text, encoding="utf-8")
        if args.logo_output:
            export_logos(args.fl26_root, manifest["cups"], args.logo_output)
    print(f'{len(manifest["cups"]) - 1} FL26 cups; '
          f'{sum(len(c["team_ids"]) for c in manifest["cups"])} pool entries')


if __name__ == "__main__":
    main()
