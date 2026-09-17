#!/usr/bin/env python3
"""Build the full Football Life 2026 -> PES21 Mobile kit migration.

The Football Life team ID selects the source assets.  The migration catalog's
physical_team_id selects the native PES21 storage slot.  A team is changed only
when home, away, and goalkeeper descriptors all exist; otherwise its current
mobile payloads remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from build_barca_real_madrid_mobile_kit_canary import (
    cpk_inventory,
    decode_wesys_payload,
    descriptor_texture_names,
    package_cpk,
    read_indexed,
    validate_cpk,
)
from build_eng_spa_mobile_kits import mobile_descriptor, safe_reference
from build_kit_preview_canary import png_bytes, thumbnail_members
from kit_preview_mesh import build_mesh, render_mesh
from build_madrid_preserve_order import restore_order
from build_real_madrid_mobile_kit_canary import (
    convert_back,
    convert_body,
    decode_ftex_top,
    image_png_bytes,
    index_cpk,
    source_indexes,
    winning_member,
)
from generate_exhibition_team_catalog import render_team_include
from package_native_club_license import enable_real_kits
from pes21_player_migration import content_id
from prepare_loose_cpk import clone_full, update, verify


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data/full_mobile_kit_migration.json"
DEFAULT_LOOSE_BASE = ROOT / "local-debug/kit-preview-canary-v5"
DEFAULT_OUTPUT = ROOT / "local-debug/full-mobile-kit-migration-v1"
KINDS = (("1st", "p1", 0), ("2nd", "p2", 1), ("GK1st", "g1", None))
BODY_SIZES = {(1024, 1024), (2048, 2048)}
BACK_SIZES = {(1024, 128), (2048, 256), (4096, 512)}
ATLAS_WIDTH = 4096
BADGE_CELL = 128
_PREVIEW_MESH = None


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_descriptor(team_id: int, kind: str) -> str:
    return (
        "common/character0/model/character/uniform/team/"
        f"{team_id}/{team_id}_DEF_{kind}_realUni.bin"
    )


def target_descriptor(team_id: int, kind: str) -> str:
    return f"common/etc/uniform/team/{team_id}/{team_id}_DEF_{kind}_realUni.bin"


def source_available(indexes: list[dict[str, Any]], member: str) -> bool:
    key = member.lower()
    return any(key in index["rows"] for index in indexes)


def audit_teams(
    catalog: dict[str, Any],
    indexes: list[dict[str, Any]],
    texture_root: str = "Asset/model/character/uniform/texture/#windx11/",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    migrated, preserved = [], []
    for team in catalog["teams"]:
        source_id = int(team["team_id"])
        available = []
        missing_assets = []
        for kind, _suffix, _preview_kind in KINDS:
            descriptor_member = source_descriptor(source_id, kind)
            if not source_available(indexes, descriptor_member):
                missing_assets.append(descriptor_member)
                continue
            descriptor, _metadata = winning_member(indexes, descriptor_member)
            refs = descriptor_texture_names(descriptor)
            textures = [
                texture_root + safe_reference(refs[0]) + ".ftex",
                texture_root + safe_reference(refs[1]) + ".ftex",
            ]
            missing_textures = [
                member for member in textures
                if not source_available(indexes, member)
            ]
            if missing_textures:
                missing_assets.extend(missing_textures)
                continue
            available.append(kind)
        row = {
            "team_id": source_id,
            "physical_team_id": int(team["physical_team_id"]),
            "display_name": str(team["display_name"]),
            "category": str(team["category"]),
            "available_kits": available,
            "missing_assets": missing_assets,
        }
        if len(available) == len(KINDS):
            migrated.append(row)
        else:
            row["reason"] = "missing_or_partial_football_life_kit_set"
            preserved.append(row)
    return migrated, preserved


def write_payload(
    output: Path,
    label: str,
    member: str,
    payload: bytes,
    payloads: dict[str, bytes],
    paths: dict[str, str],
) -> None:
    previous = payloads.get(member)
    if previous is not None and previous != payload:
        raise ValueError(f"conflicting generated payload: {member}")
    payloads[member] = payload
    digest = sha256_bytes(member.encode("utf-8"))[:16]
    path = output / "payloads" / label / f"{digest}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    paths[member] = str(path.resolve())


def render_preview_payload(body_payload: bytes, native_template: bytes) -> bytes:
    """Process-pool worker; cache the expensive mesh once in each worker."""
    global _PREVIEW_MESH
    with Image.open(io.BytesIO(native_template)) as template:
        if template.size != (128, 128):
            raise ValueError(f"expected 128x128 native thumbnail, got {template.size}")
    with Image.open(io.BytesIO(body_payload)) as source:
        atlas = source.convert("RGBA")
    if _PREVIEW_MESH is None:
        _PREVIEW_MESH = build_mesh()
    return png_bytes(render_mesh(atlas, _PREVIEW_MESH))


def render_preview_sheet(rows: list[dict[str, Any]], output: Path, title: str) -> None:
    if not rows:
        return
    columns = 5
    cell_w, cell_h = 210, 170
    width = columns * cell_w
    height = 40 + ((len(rows) + columns - 1) // columns) * cell_h
    sheet = Image.new("RGBA", (width, height), (7, 14, 32, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((14, 14), title, fill="white", font=font)
    for index, row in enumerate(rows):
        x = (index % columns) * cell_w
        y = 40 + (index // columns) * cell_h
        draw.text(
            (x + 8, y + 4),
            f"{row['team_id']} {row['display_name'][:25]}",
            fill=(220, 232, 255, 255),
            font=font,
        )
        for kit_index, kit in enumerate(row["previews"]):
            with Image.open(kit["path"]) as source:
                image = source.convert("RGBA")
            sheet.alpha_composite(image, (x + 4 + kit_index * 98, y + 24))
            draw.text(
                (x + 42 + kit_index * 98, y + 150),
                kit["suffix"].upper(),
                fill=(75, 201, 255, 255),
                font=font,
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=False, compress_level=9)


def write_badge_header(path: Path, catalog: dict[str, Any], atlas: Image.Image) -> None:
    slots = max(
        [int(row["badge_slot"]) for row in catalog["teams"]]
        + [int(row["badge_slot"]) for row in catalog["categories"]]
    ) + 1
    rows = atlas.height // BADGE_CELL
    text = f'''/* Auto-generated by tools/build_full_mobile_kit_migration.py.
 * Catalog content ID: {catalog["content_id"]}
 */

#ifndef PES21_BADGE_ATLAS_H
#define PES21_BADGE_ATLAS_H

#include <stdint.h>

#define BADGE_ATLAS_CONTENT_ID "{catalog["content_id"]}"
#define BADGE_CELL_SIZE {BADGE_CELL}
#define BADGE_ATLAS_COLS {ATLAS_WIDTH // BADGE_CELL}
#define BADGE_ATLAS_CATALOG_SLOTS {slots}
#define BADGE_ATLAS_SLOTS {slots}
#define BADGE_ATLAS_ROWS {rows}
#define BADGE_ATLAS_W (BADGE_CELL_SIZE * BADGE_ATLAS_COLS)
#define BADGE_ATLAS_H (BADGE_CELL_SIZE * BADGE_ATLAS_ROWS)
#define BADGE_ATLAS_BYTES (BADGE_ATLAS_W * BADGE_ATLAS_H * 4u)

extern const uint8_t badge_atlas_bin[];
#define badge_atlas_rgba8 badge_atlas_bin

#endif
'''
    path.write_text(text, encoding="ascii", newline="\n")


def fit_badge(payload: bytes) -> Image.Image:
    with Image.open(io.BytesIO(payload)) as source:
        image = source.convert("RGBA")
    padding = BADGE_CELL // 16
    image.thumbnail(
        (BADGE_CELL - padding, BADGE_CELL - padding), Image.Resampling.LANCZOS
    )
    tile = Image.new("RGBA", (BADGE_CELL, BADGE_CELL), (0, 0, 0, 0))
    tile.alpha_composite(
        image,
        ((BADGE_CELL - image.width) // 2, (BADGE_CELL - image.height) // 2),
    )
    return tile


def replace_badge_cell(atlas: Image.Image, slot: int, badge: Image.Image) -> None:
    """Replace one atlas cell without retaining pixels from its old badge."""
    columns = ATLAS_WIDTH // BADGE_CELL
    x = (slot % columns) * BADGE_CELL
    y = (slot // columns) * BADGE_CELL
    if x + BADGE_CELL > atlas.width or y + BADGE_CELL > atlas.height:
        raise ValueError(f"badge slot {slot} is outside the atlas")
    # The licensed source logos have transparent margins. Alpha-compositing
    # them over the old cell leaves the original badge visible through those
    # margins, producing two superimposed league marks in the selector.
    atlas.paste((0, 0, 0, 0), (x, y, x + BADGE_CELL, y + BADGE_CELL))
    atlas.alpha_composite(badge, (x, y))


def build_league_branding(
    output: Path,
    catalog: dict[str, Any],
    branding: dict[str, Any],
    league_index: dict[str, Any],
) -> dict[str, Any]:
    branded = json.loads(json.dumps(catalog))
    categories = {str(row["key"]): row for row in branded["categories"]}
    atlas_payload = (ROOT / "data/badge_atlas.bin").read_bytes()
    if len(atlas_payload) % (ATLAS_WIDTH * 4):
        raise ValueError("base badge atlas has an invalid raw RGBA length")
    atlas_height = len(atlas_payload) // (ATLAS_WIDTH * 4)
    atlas = Image.frombytes("RGBA", (ATLAS_WIDTH, atlas_height), atlas_payload)
    rows = []
    logo_dir = output / "league-branding/categories"
    logo_dir.mkdir(parents=True, exist_ok=True)
    for key, spec in branding.items():
        if key not in categories:
            raise KeyError(f"unknown selector category: {key}")
        member = str(spec["member"])
        payload = read_indexed(league_index, member)
        logo_path = logo_dir / f"{key}.png"
        logo_path.write_bytes(payload)
        category = categories[key]
        old_label = str(category["label"])
        category["label"] = str(spec["label"])
        category["football_life_brand_member"] = member
        slot = int(category["badge_slot"])
        replace_badge_cell(atlas, slot, fit_badge(payload))
        rows.append(
            {
                "key": key,
                "before": old_label,
                "after": category["label"],
                "badge_slot": slot,
                "source_member": member,
                "source_sha256": sha256_bytes(payload),
                "logo_path": str(logo_path),
            }
        )
    branded.pop("content_id", None)
    branded["content_id"] = content_id(branded)
    catalog_path = output / "league-branding/exhibition_team_catalog.json"
    catalog_path.write_text(
        json.dumps(branded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    include_path = output / "league-branding/exhibition_teams_migration_generated.inc"
    include_path.write_text(render_team_include(branded), encoding="utf-8")
    atlas_path = output / "league-branding/badge_atlas.bin"
    atlas_path.write_bytes(atlas.tobytes())
    header_path = output / "league-branding/badge_atlas.h"
    write_badge_header(header_path, branded, atlas)

    contact = Image.new("RGBA", (720, 40 + len(rows) * 138), (7, 14, 32, 255))
    draw = ImageDraw.Draw(contact)
    font = ImageFont.load_default()
    draw.text((14, 14), "FOOTBALL LIFE 2026 LEAGUE BRANDING", fill="white", font=font)
    for index, row in enumerate(rows):
        y = 40 + index * 138
        with Image.open(row["logo_path"]) as source:
            logo = source.convert("RGBA")
        logo.thumbnail((120, 120), Image.Resampling.LANCZOS)
        contact.alpha_composite(logo, (8 + (120 - logo.width) // 2, y + (120 - logo.height) // 2))
        draw.text((150, y + 48), row["after"], fill=(220, 232, 255, 255), font=font)
        draw.text((150, y + 70), f"was: {row['before']}", fill=(120, 145, 180, 255), font=font)
    contact_path = output / "league-branding/contact-sheet.png"
    contact.save(contact_path, format="PNG", optimize=False, compress_level=9)
    return {
        "categories_updated": len(rows),
        "categories_preserved": len(branded["categories"]) - len(rows),
        "catalog_content_id": branded["content_id"],
        "catalog": str(catalog_path),
        "team_include": str(include_path),
        "badge_atlas": str(atlas_path),
        "badge_atlas_header": str(header_path),
        "badge_atlas_sha256": sha256_file(atlas_path),
        "contact_sheet": str(contact_path),
        "rows": rows,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)

    config = load_json(args.config.resolve())
    if int(config.get("schema_version", 0)) != 1:
        raise ValueError("unsupported full kit migration config")
    catalog = load_json(args.catalog.resolve())
    source_manifest = load_json(args.source_manifest.resolve())
    football_life_root = args.football_life_root.resolve()
    source_manifest["football_life"]["root"] = str(football_life_root)
    indexes = source_indexes(ROOT, source_manifest, football_life_root)
    texture_root = str(source_manifest["football_life"]["texture_root"])
    migrated, preserved = audit_teams(catalog, indexes, texture_root)

    loose_base = args.loose_base.resolve()
    base_manifest = verify(loose_base)
    base_paths = {
        label: loose_base / f"LooseCpk/{label}_mobile_all.cpk"
        for label in ("dt120", "dt200", "dt240")
    }
    indexes_mobile = {
        label: index_cpk(path, label, 0) for label, path in base_paths.items()
    }
    inventories = {label: cpk_inventory(path) for label, path in base_paths.items()}
    transform = source_manifest["atlas_transform"]
    payloads: dict[str, dict[str, bytes]] = {
        label: {} for label in base_paths
    }
    paths: dict[str, dict[str, str]] = {label: {} for label in base_paths}
    team_reports = []
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    preview_jobs = []

    for number, team in enumerate(migrated, 1):
        source_id = int(team["team_id"])
        target_id = int(team["physical_team_id"])
        row = dict(team, status="migrated", kits=[], previews=[])
        for kind, suffix, preview_kind in KINDS:
            descriptor_member = source_descriptor(source_id, kind)
            descriptor, descriptor_meta = winning_member(indexes, descriptor_member)
            refs = descriptor_texture_names(descriptor)
            prefix = f"u{target_id:04d}{suffix}"
            normalized_descriptor = mobile_descriptor(descriptor, prefix)
            target_member = target_descriptor(target_id, kind)
            write_payload(
                output, "dt200", target_member, normalized_descriptor,
                payloads["dt200"], paths["dt200"],
            )
            converted: dict[str, bytes] = {}
            source_assets = []
            for role, source_ref, target_ref in (
                ("body", refs[0], prefix),
                ("back", refs[1], prefix + "_back"),
            ):
                source_member = texture_root + safe_reference(source_ref) + ".ftex"
                raw, provenance = winning_member(indexes, source_member)
                image, metadata = decode_ftex_top(raw)
                expected = BODY_SIZES if role == "body" else BACK_SIZES
                if image.size not in expected:
                    raise ValueError(
                        f"{source_member}: unverified {role} layout {image.size}"
                    )
                converted_image = (
                    convert_body(image, transform)
                    if role == "body"
                    else convert_back(image, transform)
                )
                # PNG optimization is intentionally disabled here.  The
                # decoded pixels are identical, while the full migration has
                # thousands of tiny payloads and optimize=True dominates the
                # build time without helping runtime behavior.
                converted[role] = image_png_bytes(converted_image, optimize=False)
                folder = "D" if role == "body" else "Font"
                mobile_member = (
                    f"Models/character/Uniform16/{folder}/"
                    f"{safe_reference(target_ref)}.png"
                )
                write_payload(
                    output, "dt120", mobile_member, converted[role],
                    payloads["dt120"], paths["dt120"],
                )
                source_assets.append(
                    {
                        "role": role,
                        "source_member": source_member,
                        "source_archive": provenance["archive"],
                        "source_size": list(image.size),
                        "source_format": metadata.get("pixel_format"),
                        "target_member": mobile_member,
                        "target_sha256": sha256_bytes(converted[role]),
                    }
                )
            kit_report = {
                "kind": kind,
                "suffix": suffix,
                "descriptor_source_archive": descriptor_meta["archive"],
                "descriptor_target": target_member,
                "assets": source_assets,
            }
            if preview_kind is not None:
                members = thumbnail_members(
                    indexes_mobile["dt240"], target_id, preview_kind
                )
                if not members:
                    raise ValueError(
                        f"team {source_id}->{target_id}: missing native {suffix} preview"
                    )
                # The generated pixels are identical for every regulation
                # thumbnail member of one team/kind. Render once, then write
                # that payload to every native member.
                template = read_indexed(indexes_mobile["dt240"], members[0])
                preview_jobs.append({
                    "source_id": source_id,
                    "suffix": suffix,
                    "body": converted["body"],
                    "template": template,
                    "members": members,
                    "row": row,
                    "kit_report": kit_report,
                })
            row["kits"].append(kit_report)
        team_reports.append(row)
        by_category[row["category"]].append(row)
        if number % 25 == 0 or number == len(migrated):
            print(f"Converted kit textures {number}/{len(migrated)} teams", flush=True)

    print(
        f"Rendering {len(preview_jobs)} hub previews with "
        f"{args.preview_workers} workers",
        flush=True,
    )
    with ProcessPoolExecutor(max_workers=args.preview_workers) as executor:
        futures = {
            executor.submit(
                render_preview_payload, job["body"], job["template"]
            ): job
            for job in preview_jobs
        }
        for number, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            preview_payload = future.result()
            preview_path = (
                output / "previews" / str(job["source_id"])
                / f"{job['suffix']}.png"
            )
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_bytes(preview_payload)
            for member in job["members"]:
                write_payload(
                    output, "dt240", member, preview_payload,
                    payloads["dt240"], paths["dt240"],
                )
            preview_row = {
                "suffix": job["suffix"],
                "path": str(preview_path),
                "sha256": sha256_bytes(preview_payload),
                "members": job["members"],
            }
            job["row"]["previews"].append(preview_row)
            job["kit_report"]["preview_members"] = job["members"]
            if number % 50 == 0 or number == len(preview_jobs):
                print(
                    f"Rendered hub previews {number}/{len(preview_jobs)}",
                    flush=True,
                )

    for row in team_reports:
        row["previews"].sort(key=lambda item: item["suffix"])

    team_member = "common/etc/pesdb/Team.bin"
    original_team = read_indexed(indexes_mobile["dt200"], team_member)
    physical_ids = {int(row["physical_team_id"]) for row in migrated}
    patched_team, flag_changes = enable_real_kits(original_team, physical_ids)
    write_payload(
        output, "dt200", team_member, patched_team,
        payloads["dt200"], paths["dt200"],
    )

    sheets = []
    for category, rows in sorted(by_category.items()):
        path = output / "preview-sheets" / f"{category}.png"
        render_preview_sheet(rows, path, category.upper().replace("_", " "))
        sheets.append({"category": category, "teams": len(rows), "path": str(path)})

    league_archive = football_life_root / config["football_life_league_archive"]
    league_index = index_cpk(league_archive, "football_life_dt15", 0)
    league_branding = build_league_branding(
        output, catalog, config["league_branding"], league_index
    )

    cpk_reports = {}
    candidates = {}
    for label in ("dt120", "dt200", "dt240"):
        actions = {
            member: "replace" if member in inventories[label] else "add"
            for member in payloads[label]
        }
        build_dir = output / "cpk-build" / label
        build_dir.mkdir(parents=True)
        packaged = package_cpk(
            ROOT, build_dir, label, base_paths[label], actions,
            payloads[label], paths[label],
        )
        original_order = list(inventories[label])
        original_order.extend(
            sorted(member for member in payloads[label] if member not in inventories[label])
        )
        candidate = output / "cpk-build" / f"{label}_mobile_all.cpk"
        order_report = restore_order(Path(packaged["candidate"]), candidate, original_order)
        validation = validate_cpk(
            base_paths[label], candidate, actions, payloads[label]
        )
        cpk_reports[label] = {
            "actions": dict(Counter(actions.values())),
            "changed_members": len(payloads[label]),
            "unrelated_members_byte_identical": validation[
                "unrelated_members_byte_identical"
            ],
            "base_sha256": validation["base_sha256"],
            "candidate_sha256": validation["candidate_sha256"],
            "candidate_bytes": validation["size"],
            "sorted_flag": order_report["sorted_flag"],
        }
        candidates[label] = candidate
        payloads[label].clear()

    clone_full(loose_base, output, str(base_manifest["build_id"]))
    loose_updates = []
    for label, candidate in candidates.items():
        loose_updates.append(
            update(output, f"{label}_mobile_all.cpk", candidate)["changed"]
        )
    source_nro = loose_base / "pes21_nx.nro"
    if source_nro.is_file():
        shutil.copy2(source_nro, output / "pes21_nx.nro")

    report = {
        "schema_version": 1,
        "result": "awaiting_hardware_validation",
        "scope": "full_football_life_2026_mobile_kit_and_selector_branding",
        "source": {
            "football_life_root": str(football_life_root),
            "kit_archives": source_manifest["football_life"]["archive_precedence"],
            "league_archive": str(league_archive),
            "base_loose_build_id": base_manifest["build_id"],
        },
        "policy": config["policy"],
        "counts": {
            "catalog_teams": len(catalog["teams"]),
            "migrated_teams": len(migrated),
            "preserved_teams": len(preserved),
            "converted_kit_sets": len(migrated) * len(KINDS),
            "previewed_team_kits": len(migrated) * 2,
            "preview_members_replaced": cpk_reports["dt240"]["changed_members"],
            "league_categories_branded": league_branding["categories_updated"],
        },
        "migrated_teams": team_reports,
        "preserved_teams": preserved,
        "kit_teams_by_category": dict(sorted(Counter(
            row["category"] for row in migrated
        ).items())),
        "preview_sheets": sheets,
        "league_branding": league_branding,
        "team_flag_changes": flag_changes,
        "cpk": cpk_reports,
        "loose_cpk": {
            "updates": loose_updates,
            "verification": verify(output),
        },
        "hardware_checks": [
            "boot_with_dummy_obb_and_full_loose_cpk",
            "selector_uses_licensed_league_names_and_logos",
            "english_spanish_serie_a_and_national_team_previews_match_kits",
            "home_away_and_goalkeeper_kits_match_football_life_2026",
            "physical_slot_mappings_keep_rosters_faces_and_portraits",
            "a_preserved_missing-source_team_keeps_its_previous_mobile_kit",
            "gameplan_match_goal_pause_and_restart_remain_stable",
        ],
    }
    report_path = output / "full-kit-migration-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "result": report["result"],
        "migrated_teams": len(migrated),
        "preserved_teams": len(preserved),
        "preview_members": cpk_reports["dt240"]["changed_members"],
        "league_categories": league_branding["categories_updated"],
        "output": str(output),
    }, sort_keys=True), flush=True)
    return report


def finalize(output: Path) -> dict[str, Any]:
    output = output.resolve()
    report_path = output / "full-kit-migration-report.json"
    report = load_json(report_path)
    loose = verify(output)
    artifacts = {}
    for name in (
        "pes21_nx.nro",
        "pes21_nx.elf",
        "pes21_nx.nacp",
        "patch.305030001.jp.nyan2021.pesam.obb",
        "LooseCpk/manifest.txt",
        "league-branding/badge_atlas.bin",
        "league-branding/exhibition_teams_migration_generated.inc",
    ):
        path = output / name
        if not path.is_file():
            raise FileNotFoundError(path)
        artifacts[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    nro = (output / "pes21_nx.nro").read_bytes()
    required_labels = (
        b"PREMIER LEAGUE",
        b"EFL CHAMPIONSHIP",
        b"LALIGA EA SPORTS",
        b"SERIE A ENILIVE",
    )
    missing = [value.decode("ascii") for value in required_labels if value not in nro]
    if missing:
        raise RuntimeError(f"final NRO lacks branded selector labels: {missing}")
    report["result"] = "ready_for_hardware_validation"
    report["artifacts"] = artifacts
    report["final_validation"] = {
        "loose_cpk_verified": True,
        "loose_build_id": loose["build_id"],
        "loose_file_count": len(loose["files"]),
        "selector_labels_embedded_in_nro": [
            value.decode("ascii") for value in required_labels
        ],
        "public_payloads_embedded": False,
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "result": report["result"],
        "nro_sha256": artifacts["pes21_nx.nro"]["sha256"],
        "loose_build_id": loose["build_id"],
        "output": str(output),
    }, sort_keys=True))
    return report


def refresh_branding(args: argparse.Namespace) -> dict[str, Any]:
    """Regenerate only local selector branding after a mapping review."""
    output = args.output.resolve()
    config = load_json(args.config.resolve())
    catalog = load_json(args.catalog.resolve())
    football_life_root = args.football_life_root.resolve()
    league_archive = football_life_root / config["football_life_league_archive"]
    league_index = index_cpk(league_archive, "football_life_dt15", 0)
    result = build_league_branding(
        output, catalog, config["league_branding"], league_index
    )
    report_path = output / "full-kit-migration-report.json"
    if report_path.is_file():
        report = load_json(report_path)
        report["result"] = "branding_refreshed_nro_rebuild_required"
        report["league_branding"] = result
        report["counts"]["league_categories_branded"] = result[
            "categories_updated"
        ]
        report.pop("artifacts", None)
        report.pop("final_validation", None)
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "result": "branding_refreshed_nro_rebuild_required",
        "categories": result["categories_updated"],
        "catalog_content_id": result["catalog_content_id"],
    }, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--catalog", type=Path,
        default=ROOT / "data/exhibition_team_catalog_migration.json",
    )
    parser.add_argument(
        "--source-manifest", type=Path,
        default=ROOT / "data/barca_real_madrid_mobile_kit_canary.json",
    )
    parser.add_argument(
        "--football-life-root", type=Path,
        default=Path("D:/Games/SP Football Life 2026"),
    )
    parser.add_argument("--loose-base", type=Path, default=DEFAULT_LOOSE_BASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preview-workers", type=int, default=8)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--refresh-branding", action="store_true")
    args = parser.parse_args()
    if args.refresh_branding:
        refresh_branding(args)
    elif args.finalize:
        finalize(args.output)
    else:
        build(args)


if __name__ == "__main__":
    main()
