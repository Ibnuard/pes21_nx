#!/usr/bin/env python3
"""Build a direct-ID Sadio Mane portrait test on the latest recovery OBB.

The existing recovery package accidentally represents Mane through reserved
player row 540390.  PES21 already has Mane's native row and portrait key 57304,
so this canary moves Al Nassr back to that identity, restores row 540390, and
replaces ``common/player/57304.png`` with the newly fetched PESDB portrait.
No runtime portrait alias is added.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from apply_pesdb_efootball import apply_verified_fields
from build_barca_real_madrid_mobile_kit_canary import (
    cpk_inventory,
    decode_wesys_payload,
    validate_cpk,
)
from build_eng_spa_license_pack import encode_wesys
from build_pesdb_famous_teams_candidate import (
    member_payload,
    package_outer_obb,
    validate_outer_obb,
)
from import_efootball10_portraits import normalize_portrait
from pesdb import parse_player_records


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = 16834520
DIRECT_ID = 57304
OLD_TARGET_ID = 540390
AL_NASSR_LOGICAL_ID = 18961
AL_NASSR_PHYSICAL_ID = 68113
PLAYER_MEMBER = "common/etc/pesdb/Player.bin"
ASSIGNMENT_MEMBER = "common/etc/pesdb/PlayerAssignment.bin"
DT200_MEMBER = "Expansion/dt200_mobile_all.cpk"
DT210_MEMBER = "Expansion/dt210_mobile_android.cpk"
DT241_MEMBER = "Expansion/dt241_mobile_all.cpk"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_name(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]",
        "",
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower(),
    )


def is_mane_name(value: str) -> bool:
    """Accept the lossy PES21 decoder's replacement of Mane's final accent."""
    compact = normalized_name(value)
    return compact in {"sman", "smane", "sadioman", "sadiomane"}


def raw_member(cpk: Path, member: str) -> bytes:
    return decode_wesys_payload(member_payload(cpk, member), member)[0]


def fit_portrait_to_native_slot(path: Path, capacity: int) -> dict[str, int]:
    """Use the stock portrait's indexed-PNG layout to keep its CPK slot stable."""
    original_size = path.stat().st_size
    if original_size <= capacity:
        return {"slot_capacity": capacity, "colors": 0, "bytes": original_size}
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
        for colors in (256, 192, 160, 128, 96, 64, 48, 32):
            indexed = rgba.quantize(
                colors=colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
            candidate = BytesIO()
            indexed.save(candidate, format="PNG", optimize=True)
            data = candidate.getvalue()
            if len(data) <= capacity:
                path.write_bytes(data)
                return {
                    "slot_capacity": capacity,
                    "colors": colors,
                    "bytes": len(data),
                }
    raise RuntimeError(f"portrait cannot fit native CPK slot ({original_size} > {capacity})")


def player_rows(raw: bytes) -> tuple[list[bytes], dict[int, bytes]]:
    if len(raw) % 312:
        raise ValueError("Player.bin has a partial row")
    ordered = [raw[offset : offset + 312] for offset in range(0, len(raw), 312)]
    by_id = {struct.unpack_from("<I", row, 8)[0]: row for row in ordered}
    if len(by_id) != len(ordered):
        raise ValueError("Player.bin contains duplicate IDs")
    return ordered, by_id


def patch_players(current_cpk: Path, donor_cpk: Path, snapshot: Path) -> tuple[bytes, dict[str, Any]]:
    current_order, current = player_rows(raw_member(current_cpk, PLAYER_MEMBER))
    _donor_order, donor = player_rows(raw_member(donor_cpk, PLAYER_MEMBER))
    players = json.loads(snapshot.read_text(encoding="utf-8"))["players"]
    source = players[str(SOURCE_ID)]
    names = parse_player_records(b"".join(current_order), "pes21")
    if not is_mane_name(names[DIRECT_ID].name):
        raise RuntimeError(f"native direct row {DIRECT_ID} is not Mane: {names[DIRECT_ID].name}")
    if not is_mane_name(names[OLD_TARGET_ID].name):
        raise RuntimeError(
            f"old target {OLD_TARGET_ID} is not the current Mane row: {names[OLD_TARGET_ID].name}"
        )
    patched_direct, fields = apply_verified_fields(current[DIRECT_ID], source)
    result = dict(current)
    result[DIRECT_ID] = patched_direct
    result[OLD_TARGET_ID] = donor[OLD_TARGET_ID]
    encoded = encode_wesys(
        b"".join(result[struct.unpack_from("<I", row, 8)[0]] for row in current_order)
    )
    final_names = parse_player_records(
        b"".join(result[struct.unpack_from("<I", row, 8)[0]] for row in current_order),
        "pes21",
    )
    if not is_mane_name(final_names[DIRECT_ID].name):
        raise RuntimeError("direct Mane row failed name validation")
    if result[OLD_TARGET_ID] != donor[OLD_TARGET_ID]:
        raise RuntimeError("old target row was not restored")
    return encoded, {
        "source_player_id": SOURCE_ID,
        "direct_pes21_id": DIRECT_ID,
        "old_reserved_target_restored": OLD_TARGET_ID,
        "name": source["player_name"],
        "base_overall": source["base_overall"],
        **fields,
    }


def patch_assignments(current_cpk: Path) -> tuple[bytes, dict[str, Any]]:
    raw = raw_member(current_cpk, ASSIGNMENT_MEMBER)
    if len(raw) % 16:
        raise ValueError("PlayerAssignment.bin has a partial row")
    records = [list(struct.unpack_from("<IIII", raw, offset)) for offset in range(0, len(raw), 16)]
    targets = [
        row for row in records
        if row[1] == OLD_TARGET_ID and row[2] == AL_NASSR_PHYSICAL_ID
    ]
    if len(targets) != 1:
        raise RuntimeError(f"expected one old Mane Al Nassr assignment, found {len(targets)}")
    if any(row[1] == DIRECT_ID and row[2] == AL_NASSR_PHYSICAL_ID for row in records):
        raise RuntimeError("direct Mane ID is already assigned to Al Nassr")
    targets[0][1] = DIRECT_ID
    return encode_wesys(b"".join(struct.pack("<IIII", *row) for row in records)), {
        "physical_team_id": AL_NASSR_PHYSICAL_ID,
        "assignment_id": targets[0][0],
        "before_player_id": OLD_TARGET_ID,
        "after_player_id": DIRECT_ID,
    }


def patch_runtime_include(source: Path, output: Path) -> dict[str, Any]:
    text = source.read_text(encoding="utf-8")
    owner_pattern = re.compile(
        r"(static const ExhibitionPesdbPlayerOwner exhibition_pesdb_player_owners\[\] = \{)(.*?)\n\};",
        re.S,
    )
    owner_match = owner_pattern.search(text)
    if not owner_match:
        raise RuntimeError("player owner table not found")
    owners = [(int(player), int(team)) for player, team in re.findall(r"\{(\d+)u, (\d+)u\}", owner_match[2])]
    if owners.count((OLD_TARGET_ID, AL_NASSR_LOGICAL_ID)) != 1:
        raise RuntimeError("old Mane owner row not found exactly once")
    owners.remove((OLD_TARGET_ID, AL_NASSR_LOGICAL_ID))
    if any(player == DIRECT_ID for player, _team in owners):
        raise RuntimeError("direct Mane ID already has a PESDB club owner")
    owners.append((DIRECT_ID, AL_NASSR_LOGICAL_ID))
    owners.sort()
    owner_body = "\n" + "".join(f"    {{{player}u, {team}u}},\n" for player, team in owners) + "};"
    text = text[: owner_match.start()] + owner_match[1] + owner_body + text[owner_match.end() :]

    rating_pattern = re.compile(
        r"(static const ExhibitionPesdbPlayerRating exhibition_pesdb_player_ratings\[\] = \{)(.*?)\n\};",
        re.S,
    )
    rating_match = rating_pattern.search(text)
    if not rating_match:
        raise RuntimeError("player rating table not found")
    ratings = {
        int(player): (int(overall), int(position))
        for player, overall, position in re.findall(
            r"\{(\d+)u, (\d+)u, (\d+)u\}", rating_match[2]
        )
    }
    old_rating = ratings.pop(OLD_TARGET_ID, None)
    if old_rating is None or DIRECT_ID in ratings:
        raise RuntimeError("Mane rating rows are not in the expected state")
    ratings[DIRECT_ID] = old_rating
    rating_body = "\n" + "".join(
        f"    {{{player}u, {value[0]}u, {value[1]}u}},\n"
        for player, value in sorted(ratings.items())
    ) + "};"
    text = text[: rating_match.start()] + rating_match[1] + rating_body + text[rating_match.end() :]

    roster_pattern = re.compile(
        r"(static const uint32_t exhibition_pesdb_team_18961_players\[\] = \{)(.*?)\n\};",
        re.S,
    )
    roster_match = roster_pattern.search(text)
    if not roster_match:
        raise RuntimeError("Al Nassr roster table not found")
    roster = [int(value) for value in re.findall(r"(\d+)u", roster_match[2])]
    if roster.count(OLD_TARGET_ID) != 1 or DIRECT_ID in roster:
        raise RuntimeError("Al Nassr Mane roster entry is not in the expected state")
    roster[roster.index(OLD_TARGET_ID)] = DIRECT_ID
    roster_body = "\n    " + ", ".join(f"{player}u" for player in roster) + ",\n};"
    text = text[: roster_match.start()] + roster_match[1] + roster_body + text[roster_match.end() :]
    output.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": str(output),
        "sha256": sha256_file(output),
        "owner_sorted": owners == sorted(owners),
        "ratings_sorted": list(sorted(ratings)) == sorted(ratings),
        "al_nassr_players": len(roster),
        "direct_id_occurrences": roster.count(DIRECT_ID),
        "old_target_occurrences": roster.count(OLD_TARGET_ID),
    }


def repack(base: Path, output: Path, replacements: dict[str, Path]) -> dict[str, Any]:
    manifest = output.with_suffix(".replacements.json")
    manifest.write_text(
        json.dumps({member: str(path.resolve()) for member, path in replacements.items()}, indent=2) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "repack_cpk_members.py"),
            str(base),
            str(output),
            "--expect-members",
            str(len(cpk_inventory(base))),
            "--replace-manifest",
            str(manifest),
        ],
        cwd=ROOT,
        check=True,
    )
    actions = {member: "replace" for member in replacements}
    payloads = {member: path.read_bytes() for member, path in replacements.items()}
    return validate_cpk(base, output, actions, payloads)


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    base_obb = args.base_obb.resolve()
    donor_cpk = args.donor_cpk.resolve()
    snapshot = args.snapshot.resolve()
    portrait_source = args.portrait.resolve()
    runtime_include = args.runtime_include.resolve()
    for path in (base_obb, donor_cpk, snapshot, portrait_source, runtime_include):
        if not path.is_file():
            raise FileNotFoundError(path)

    base_dt200 = output / "base-dt200.cpk"
    base_dt241 = output / "base-dt241.cpk"
    base_dt200.write_bytes(member_payload(base_obb, DT200_MEMBER))
    base_dt241.write_bytes(member_payload(base_obb, DT241_MEMBER))
    scoreboard_before = sha256_bytes(member_payload(base_obb, DT210_MEMBER))

    payload_dir = output / "payloads"
    payload_dir.mkdir()
    player_payload, player_report = patch_players(base_dt200, donor_cpk, snapshot)
    assignment_payload, assignment_report = patch_assignments(base_dt200)
    player_path = payload_dir / "Player.bin"
    assignment_path = payload_dir / "PlayerAssignment.bin"
    player_path.write_bytes(player_payload)
    assignment_path.write_bytes(assignment_payload)
    dt200 = output / "dt200-direct-mane.cpk"
    dt200_report = repack(
        base_dt200,
        dt200,
        {PLAYER_MEMBER: player_path, ASSIGNMENT_MEMBER: assignment_path},
    )

    normalized = payload_dir / f"{DIRECT_ID}.png"
    normalize_portrait(portrait_source, normalized)
    portrait_member = f"common/player/{DIRECT_ID}.png"
    portrait_inventory = cpk_inventory(base_dt241)
    if portrait_member not in portrait_inventory:
        raise RuntimeError(f"native Mane portrait member is absent: {portrait_member}")
    portrait_offset = portrait_inventory[portrait_member]["FileOffset"]
    next_offsets = [
        row["FileOffset"]
        for row in portrait_inventory.values()
        if row["FileOffset"] > portrait_offset
    ]
    portrait_slot = min(next_offsets) - portrait_offset
    portrait_encoding = fit_portrait_to_native_slot(normalized, portrait_slot)
    dt241 = output / "dt241-direct-mane.cpk"
    dt241_report = repack(base_dt241, dt241, {portrait_member: normalized})

    candidate_obb = output / base_obb.name
    outer_replacements = {DT200_MEMBER: dt200, DT241_MEMBER: dt241}
    packaging_mode, packaging_note = package_outer_obb(
        base_obb, candidate_obb, outer_replacements
    )
    obb_report = validate_outer_obb(
        base_obb,
        candidate_obb,
        outer_replacements,
        packaging_mode=packaging_mode,
    )
    scoreboard_after = sha256_bytes(member_payload(candidate_obb, DT210_MEMBER))
    if scoreboard_after != scoreboard_before:
        raise RuntimeError("latest scoreboard changed while building Mane test")

    include_report = patch_runtime_include(
        runtime_include, output / runtime_include.name
    )
    report = {
        "schema_version": 1,
        "experiment": "al_nassr_mane_direct_id_portrait",
        "policy": {
            "portrait_alias_mapping": False,
            "direct_pes21_identity": DIRECT_ID,
            "pesdb_source_player_id": SOURCE_ID,
            "old_reserved_target_restored": OLD_TARGET_ID,
        },
        "player": player_report,
        "assignment": assignment_report,
        "portrait": {
            "source": str(portrait_source),
            "source_sha256": sha256_file(portrait_source),
            "normalized": str(normalized),
            "normalized_sha256": sha256_file(normalized),
            "member": portrait_member,
            "encoding": portrait_encoding,
        },
        "dt200": dt200_report,
        "dt241": dt241_report,
        "runtime_include": include_report,
        "scoreboard": {
            "member": DT210_MEMBER,
            "sha256_before": scoreboard_before,
            "sha256_after": scoreboard_after,
            "preserved": True,
        },
        "obb": obb_report,
        "packaging_note": packaging_note,
    }
    (output / "audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-obb",
        type=Path,
        default=ROOT / "local-debug/player-identity-recovery-v6-scoreboard/patch.305030001.jp.nyan2021.pesam.obb",
    )
    parser.add_argument(
        "--donor-cpk",
        type=Path,
        default=ROOT / "local-debug/national-team-all-kits-v2/dt200-original-order.cpk",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=ROOT / "local-debug/pesdb-efootball-authentic-rosters-current-54-shirts.json",
    )
    parser.add_argument(
        "--portrait",
        type=Path,
        default=ROOT / "local-debug/pesdb-authentic-portraits/16834520.png",
    )
    parser.add_argument(
        "--runtime-include",
        type=Path,
        default=ROOT / "source/exhibition_rosters_pesdb_generated.inc",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "local-debug/al-nassr-mane-direct-v3",
    )
    build(parser.parse_args())


if __name__ == "__main__":
    main()
