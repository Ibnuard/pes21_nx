#!/usr/bin/env python3
"""Repair EF10 native names, licensed crests, and Inter Miami portraits.

The licensed-kit builder used to create real (``_r``) crest members from the
old fake (``_f``) payload, then update only members present in the base CPK.
That left the newly added ``_r`` members displaying fake crests on native game
surfaces.  This builder patches all ten imported EF10 team identities in
``Team.bin``, replaces every native crest variant for every licensed catalog
team, and packages a complete portrait set for the active Inter Miami roster.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

from build_al_nassr_mane_direct_portrait import repack
from build_inter_miami_release_experiment import (
    decode_wesys_bytes,
    encode_wesys_compact,
)
from build_barca_real_madrid_mobile_kit_canary import (
    cpk_inventory,
    package_cpk,
    validate_cpk,
)
from build_madrid_preserve_order import restore_order
from build_pesdb_famous_teams_candidate import (
    member_payload,
    package_outer_obb,
    patch_team_table,
    validate_outer_obb,
)
from import_efootball10_portraits import normalize_portrait


ROOT = Path(__file__).resolve().parents[1]
INTER_MIAMI_TEAM_ID = 5738
DT120_MEMBER = "Expansion/dt120_mobile_all.cpk"
DT200_MEMBER = "Expansion/dt200_mobile_all.cpk"
DT210_MEMBER = "Expansion/dt210_mobile_android.cpk"
DT240_MEMBER = "Expansion/dt240_mobile_all.cpk"
DT241_MEMBER = "Expansion/dt241_mobile_all.cpk"
TEAM_MEMBER = "common/etc/pesdb/Team.bin"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def licensed_catalog_teams(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    teams = [
        row
        for row in payload["teams"]
        if row.get("name_source") == "football_life_license"
    ]
    if len(teams) != 58:
        raise RuntimeError(f"expected 58 licensed catalog teams, found {len(teams)}")
    if len({int(row["team_id"]) for row in teams}) != len(teams):
        raise RuntimeError("licensed catalog contains duplicate team IDs")
    return teams


def external_active_teams(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("external_active_clubs", [])
    if len(rows) != 10:
        raise RuntimeError(f"expected 10 external active clubs, found {len(rows)}")
    teams = [
        {
            "ef10_team_id": int(row["team_id"]),
            "physical_team_id": int(row["physical_team_id"]),
            "display_name": str(row["display_name"]),
            "short_code": str(row["short_code"]),
        }
        for row in rows
    ]
    if len({row["ef10_team_id"] for row in teams}) != len(teams):
        raise RuntimeError("external club list contains duplicate logical IDs")
    if len({row["physical_team_id"] for row in teams}) != len(teams):
        raise RuntimeError("external club list reuses a physical team slot")
    return teams


def build_native_team_names(
    base: Path,
    output: Path,
    external_teams_path: Path,
) -> tuple[Path, dict[str, Any]]:
    teams = external_active_teams(external_teams_path)
    current = member_payload(base, TEAM_MEMBER)
    decoded = decode_wesys_bytes(current, "current Team.bin")
    patched, report = patch_team_table(decoded, teams)
    payload_root = output / "payloads" / "native-team-names"
    payload_root.mkdir(parents=True)
    payload = payload_root / "Team.bin"
    payload.write_bytes(encode_wesys_compact(patched))
    candidate = output / "dt200-ef10-native-names.cpk"
    cpk_report = repack(base, candidate, {TEAM_MEMBER: payload})

    packaged = decode_wesys_bytes(
        member_payload(candidate, TEAM_MEMBER), "packaged Team.bin"
    )
    _verified, verification = patch_team_table(packaged, teams)
    stale = [
        row
        for row in verification["teams"]
        if row["old_name"] != row["new_name"]
    ]
    if stale:
        raise RuntimeError(f"native team names were not packaged: {stale}")
    return candidate, {
        **report,
        "source": str(external_teams_path),
        "cpk": cpk_report,
        "verified_names": len(verification["teams"]),
    }


def native_crest_members(inventory: dict[str, Any], team_id: int) -> list[str]:
    patterns = (
        re.compile(rf"common/render/symbol/flag/e_{team_id:06d}_.+\.png$"),
        re.compile(rf"common/render/symbol/emblemLc/emb_{team_id:04d}_.+\.png$"),
    )
    return sorted(
        name for name in inventory if any(pattern.fullmatch(name) for pattern in patterns)
    )


def build_crests(
    base: Path,
    output: Path,
    catalog: Path,
) -> tuple[Path, dict[str, Any]]:
    inventory = cpk_inventory(base)
    payload_root = output / "payloads" / "crests"
    payload_root.mkdir(parents=True)
    replacements: dict[str, Path] = {}
    teams_report: list[dict[str, Any]] = []
    for team in licensed_catalog_teams(catalog):
        team_id = int(team["team_id"])
        crest_source = ROOT / str(team["badge_source"])
        if not crest_source.is_file():
            raise FileNotFoundError(crest_source)
        members = native_crest_members(inventory, team_id)
        if not members:
            raise RuntimeError(f"licensed team {team_id} has no native crest members")
        with Image.open(crest_source) as source_image:
            crest = source_image.convert("RGBA")
            if not crest.getchannel("A").getbbox():
                raise RuntimeError(f"licensed team {team_id} crest is transparent")
            variants: list[dict[str, Any]] = []
            for index, member in enumerate(members):
                old_payload = member_payload(base, member)
                with Image.open(io.BytesIO(old_payload)) as old:
                    size = old.size
                buffer = io.BytesIO()
                crest.resize(size, Image.Resampling.LANCZOS).save(
                    buffer, format="PNG", optimize=True
                )
                data = buffer.getvalue()
                path = payload_root / f"{team_id}-{index:02d}.png"
                path.write_bytes(data)
                replacements[member] = path
                variants.append(
                    {
                        "member": member,
                        "size": list(size),
                        "before_sha256": sha256_bytes(old_payload),
                        "after_sha256": sha256_bytes(data),
                    }
                )
        teams_report.append(
            {
                "team_id": team_id,
                "name": team["display_name"],
                "source": str(crest_source),
                "variants": variants,
            }
        )
    candidate = output / "dt240-licensed-crests.cpk"
    cpk_report = repack(base, candidate, replacements)
    inter = next(row for row in teams_report if row["team_id"] == 119)
    inter_real = [row for row in inter["variants"] if "_r" in row["member"]]
    if not inter_real or any(row["before_sha256"] == row["after_sha256"] for row in inter_real):
        raise RuntimeError("Inter Milan real crest variants were not repaired")
    return candidate, {
        "licensed_teams": len(teams_report),
        "changed_variants": len(replacements),
        "teams": teams_report,
        "cpk": cpk_report,
    }


def inter_miami_targets(runtime_include: Path, identity_audit: Path) -> list[dict[str, Any]]:
    text = runtime_include.read_text(encoding="utf-8")
    match = re.search(
        r"exhibition_pesdb_team_5738_players\[\] = \{(.*?)\};", text, re.S
    )
    if not match:
        raise RuntimeError("active Inter Miami PESDB roster was not found")
    targets = [int(value) for value in re.findall(r"(\d+)u", match.group(1))]
    if len(targets) < 11 or len(targets) != len(set(targets)):
        raise RuntimeError("active Inter Miami roster is incomplete or duplicated")
    audit = json.loads(identity_audit.read_text(encoding="utf-8"))
    by_target = {int(row["target"]): row for row in audit["remaps"]}
    result: list[dict[str, Any]] = []
    for target in targets:
        row = by_target.get(target)
        if row is None:
            raise RuntimeError(f"Inter Miami target {target} is missing identity provenance")
        result.append(
            {
                "target": target,
                "source": int(row["source"]),
                "name": row["name"],
                "canonical": bool(row["canonical"]),
            }
        )
    return result


def compact_portrait(source: Path | None, output: Path) -> dict[str, Any]:
    if source is not None:
        normalize_portrait(source, output)
        status = "pesdb"
    else:
        Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(
            output, format="PNG", optimize=True
        )
        status = "transparent_no_pesdb_portrait"
    with Image.open(output) as image:
        rgba = image.convert("RGBA")
        if rgba.size != (128, 128):
            raise RuntimeError(f"unexpected portrait size: {rgba.size}")
        has_pixels = rgba.getchannel("A").getbbox() is not None
        indexed = rgba.quantize(
            colors=128,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.FLOYDSTEINBERG,
        )
        buffer = io.BytesIO()
        indexed.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()
    output.write_bytes(data)
    if source is not None and not has_pixels:
        raise RuntimeError(f"PESDB portrait is transparent: {source}")
    return {
        "status": status,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "has_visible_pixels": has_pixels,
    }


def build_inter_miami_portraits(
    base: Path,
    output: Path,
    runtime_include: Path,
    identity_audit: Path,
    portrait_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    inventory = cpk_inventory(base)
    original_names = list(inventory)
    payload_root = output / "payloads" / "inter-miami"
    payload_root.mkdir(parents=True)
    payloads: dict[str, bytes] = {}
    payload_paths: dict[str, str] = {}
    actions: dict[str, str] = {}
    players_report: list[dict[str, Any]] = []
    for row in inter_miami_targets(runtime_include, identity_audit):
        target = int(row["target"])
        source_id = int(row["source"])
        source = portrait_dir / f"{source_id}.png"
        source_or_none = source if source.is_file() else None
        path = payload_root / f"{target}.png"
        portrait = compact_portrait(source_or_none, path)
        member = f"common/player/{target}.png"
        data = path.read_bytes()
        payloads[member] = data
        payload_paths[member] = str(path.resolve())
        actions[member] = "replace" if member in inventory else "add"
        players_report.append(
            {
                **row,
                "member": member,
                "action": actions[member],
                "source_path": str(source) if source_or_none else None,
                **portrait,
            }
        )

    package_report = package_cpk(
        ROOT,
        output,
        "dt241-inter-miami",
        base,
        actions,
        payloads,
        payload_paths,
    )
    stage = output / "dt241-inter-miami_barca_real_madrid_canary.cpk"
    additions = sorted(member for member, action in actions.items() if action == "add")
    final = output / "dt241-inter-miami-portraits.cpk"
    order_report = restore_order(stage, final, original_names + additions)
    final_report = validate_cpk(base, final, actions, payloads)
    final_inventory = cpk_inventory(final)
    missing = sorted(set(payloads) - set(final_inventory))
    if missing:
        raise RuntimeError(f"Inter Miami portraits missing after package: {missing}")
    return final, {
        "active_players": len(players_report),
        "real_portraits": sum(row["status"] == "pesdb" for row in players_report),
        "transparent_fallbacks": sum(
            row["status"] != "pesdb" for row in players_report
        ),
        "replaced_members": sum(row["action"] == "replace" for row in players_report),
        "added_members": sum(row["action"] == "add" for row in players_report),
        "players": players_report,
        "package": package_report,
        "order": order_report,
        "cpk": final_report,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    base_obb = args.base_obb.resolve()
    catalog = args.catalog.resolve()
    external_teams = args.external_teams.resolve()
    runtime_include = args.runtime_include.resolve()
    identity_audit = args.identity_audit.resolve()
    portrait_dir = args.portrait_dir.resolve()
    for path in (
        base_obb,
        catalog,
        external_teams,
        runtime_include,
        identity_audit,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not portrait_dir.is_dir():
        raise FileNotFoundError(portrait_dir)

    base_dt200 = output / "base-dt200.cpk"
    base_dt240 = output / "base-dt240.cpk"
    base_dt241 = output / "base-dt241.cpk"
    base_dt200.write_bytes(member_payload(base_obb, DT200_MEMBER))
    base_dt240.write_bytes(member_payload(base_obb, DT240_MEMBER))
    base_dt241.write_bytes(member_payload(base_obb, DT241_MEMBER))
    preserved_before = {
        member: sha256_bytes(member_payload(base_obb, member))
        for member in (DT120_MEMBER, DT210_MEMBER)
    }

    dt200, native_names = build_native_team_names(
        base_dt200, output, external_teams
    )
    dt240, crests = build_crests(base_dt240, output, catalog)
    dt241, portraits = build_inter_miami_portraits(
        base_dt241,
        output,
        runtime_include,
        identity_audit,
        portrait_dir,
    )
    candidate = output / base_obb.name
    replacements = {
        DT200_MEMBER: dt200,
        DT240_MEMBER: dt240,
        DT241_MEMBER: dt241,
    }
    mode, note = package_outer_obb(base_obb, candidate, replacements)
    obb = validate_outer_obb(
        base_obb, candidate, replacements, packaging_mode=mode
    )
    preserved_after = {
        member: sha256_bytes(member_payload(candidate, member))
        for member in preserved_before
    }
    if preserved_after != preserved_before:
        raise RuntimeError("kits or scoreboard changed unexpectedly")

    report = {
        "schema_version": 1,
        "experiment": "ef10_native_names_licensed_crests_inter_miami_portraits_fix",
        "base_obb": {
            "path": str(base_obb),
            "size": base_obb.stat().st_size,
            "sha256": sha256_file(base_obb),
        },
        "native_team_names": native_names,
        "crests": crests,
        "inter_miami_portraits": portraits,
        "preserved_outer_members": {
            member: {
                "before": preserved_before[member],
                "after": preserved_after[member],
            }
            for member in preserved_before
        },
        "obb": obb,
        "packaging_note": note,
    }
    (output / "audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "native_team_names": {
                    "teams": native_names["changed_rows"],
                    "verified": native_names["verified_names"],
                },
                "crests": {
                    "teams": crests["licensed_teams"],
                    "variants": crests["changed_variants"],
                },
                "portraits": {
                    key: portraits[key]
                    for key in (
                        "active_players",
                        "real_portraits",
                        "transparent_fallbacks",
                        "replaced_members",
                        "added_members",
                    )
                },
                "obb": obb,
            },
            indent=2,
        )
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-obb",
        type=Path,
        default=ROOT
        / "local-debug/al-nassr-mane-direct-v3/patch.305030001.jp.nyan2021.pesam.obb",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=ROOT / "data/exhibition_team_catalog.json",
    )
    parser.add_argument(
        "--external-teams",
        type=Path,
        default=ROOT / "data/exhibition_team_categories.json",
    )
    parser.add_argument(
        "--runtime-include",
        type=Path,
        default=ROOT / "source/exhibition_rosters_pesdb_generated.inc",
    )
    parser.add_argument(
        "--identity-audit",
        type=Path,
        default=ROOT / "local-debug/player-identity-recovery-v5/audit.json",
    )
    parser.add_argument(
        "--portrait-dir",
        type=Path,
        default=ROOT / "local-debug/pesdb-authentic-portraits-inter-miami-v1",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "local-debug/ef10-native-names-native-input-probe-v1",
    )
    build(parser.parse_args())


if __name__ == "__main__":
    main()
