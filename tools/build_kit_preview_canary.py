#!/usr/bin/env python3
"""Build deterministic hub kit thumbnails from Football Life uniform textures.

The custom prematch Kits page reads native ``uni<UniformId>.png`` members from
dt240.  Match kits themselves live in dt120, so updating only the Uniform16
atlas leaves those thumbnails stale.  This canary converts the selected
Football Life body textures to the verified mobile atlas, projects the atlas
onto a project-authored curved 3D mesh, and replaces only the corresponding
128x128 hub thumbnails in a cloned full loose-CPK package.

The 128x512 ``_full`` native previews are deliberately outside this first
canary.  No proprietary texture or thumbnail is committed by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from kit_preview_mesh import RENDERER_VERSION, export_obj, render_mesh

from build_barca_real_madrid_mobile_kit_canary import (
    descriptor_texture_names,
    index_cpk,
    package_cpk,
    read_indexed,
)
from build_real_madrid_mobile_kit_canary import (
    convert_body,
    decode_ftex_top,
    source_indexes,
    winning_member,
)
from prepare_loose_cpk import clone_full, update, verify


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data/kit_preview_canary.json"
DEFAULT_SOURCE_MANIFEST = ROOT / "data/barca_real_madrid_mobile_kit_canary.json"
DEFAULT_LOOSE_BASE = ROOT / "local-debug/pes21-player-migration-full-v1"
DEFAULT_OUTPUT = ROOT / "local-debug/kit-preview-canary-v5"
HUB_KITS = (("1st", "p1", 0), ("2nd", "p2", 1))
THUMBNAIL_RE = re.compile(r"uni(\d+)\.png$")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def load_teams(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    teams = [
        dict(team, league=league.get("label", ""))
        for league in payload.get("leagues", [])
        for team in league.get("teams", [])
    ]
    identifiers = [int(team["team_id"]) for team in teams]
    if not teams or len(identifiers) != len(set(identifiers)):
        raise ValueError("kit preview config must contain unique teams")
    return teams


def thumbnail_members(index: dict[str, Any], team_id: int, kind: int) -> list[str]:
    members = []
    for entry in index["rows"].values():
        name = str(entry["name"])
        match = THUMBNAIL_RE.search(name)
        if not match:
            continue
        uniform_id = int(match.group(1))
        if uniform_id >> 14 == team_id and uniform_id & 0x7F == kind:
            members.append(name)
    return sorted(members)


def render_jersey(atlas_image: Image.Image, native_template: bytes) -> Image.Image:
    """Render the mesh; native PNG is used only to validate output dimensions."""
    with Image.open(io.BytesIO(native_template)) as template:
        if template.size != (128, 128):
            raise ValueError(f"expected 128x128 native thumbnail, got {template.size}")
    return render_mesh(atlas_image)


def write_contact_sheet(rows: list[dict[str, Any]], output: Path) -> None:
    width = 560
    height = 44 + 156 * len(rows)
    sheet = Image.new("RGBA", (width, height), (7, 14, 32, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 15), "KIT PREVIEW CANARY - FOOTBALL LIFE 2026", fill="white", font=font)
    for index, row in enumerate(rows):
        y = 44 + index * 156
        draw.text((18, y + 8), f"{row['team_id']}  {row['name']}", fill=(220, 232, 255, 255), font=font)
        for kit_index, kit in enumerate(row["kits"]):
            image = Image.open(kit["preview_path"]).convert("RGBA")
            x = 220 + kit_index * 150
            sheet.alpha_composite(image, (x, y + 18))
            draw.text((x + 48, y + 4), kit["suffix"].upper(), fill=(75, 201, 255, 255), font=font)
    sheet.save(output, format="PNG", optimize=False, compress_level=9)


def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    loose_base = args.loose_base.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    output.mkdir(parents=True)

    teams = load_teams(args.config.resolve())
    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    source_manifest["football_life"]["root"] = str(args.football_life_root.resolve())
    indexes = source_indexes(ROOT, source_manifest, args.football_life_root.resolve())
    texture_root = str(source_manifest["football_life"]["texture_root"])
    atlas_transform = source_manifest["atlas_transform"]

    base_manifest = verify(loose_base)
    dt120 = loose_base / "LooseCpk/dt120_mobile_all.cpk"
    dt200 = loose_base / "LooseCpk/dt200_mobile_all.cpk"
    dt240 = loose_base / "LooseCpk/dt240_mobile_all.cpk"
    dt120_index = index_cpk(dt120, "dt120", 0)
    dt200_index = index_cpk(dt200, "dt200", 0)
    dt240_index = index_cpk(dt240, "dt240", 0)
    replacements: dict[str, bytes] = {}
    payload_paths: dict[str, str] = {}
    team_reports = []

    for team in teams:
        team_id = int(team["team_id"])
        source_team_id = int(team.get("source_team_id", team_id))
        row = {
            "team_id": team_id,
            "source_team_id": source_team_id,
            "name": str(team["official_name"]),
            "kits": [],
        }
        for source_kind, suffix, kind in HUB_KITS:
            descriptor_member = (
                "common/character0/model/character/uniform/team/"
                f"{source_team_id}/{source_team_id}_DEF_{source_kind}_realUni.bin"
            )
            descriptor, descriptor_meta = winning_member(indexes, descriptor_member)
            body_reference = descriptor_texture_names(descriptor)[0]
            body_member = f"{texture_root}{body_reference}.ftex"
            body_payload, body_meta = winning_member(indexes, body_member)
            body_image, body_decode = decode_ftex_top(body_payload)
            atlas = convert_body(body_image, atlas_transform)

            atlas_path = output / "atlases" / str(team_id) / f"{suffix}.png"
            atlas_path.parent.mkdir(parents=True, exist_ok=True)
            atlas.save(atlas_path, format="PNG", optimize=False, compress_level=9)

            mobile_descriptor_member = (
                f"common/etc/uniform/team/{team_id}/"
                f"{team_id}_DEF_{source_kind}_realUni.bin"
            )
            mobile_descriptor = read_indexed(dt200_index, mobile_descriptor_member)
            mobile_body_reference = descriptor_texture_names(mobile_descriptor)[0]
            mobile_body_member = (
                f"Models/character/Uniform16/D/{mobile_body_reference}.png"
            )
            runtime_body = read_indexed(dt120_index, mobile_body_member)
            generated_body = atlas_path.read_bytes()
            if runtime_body != generated_body:
                raise RuntimeError(
                    f"{team_id}/{suffix}: Football Life conversion does not "
                    f"match installed {mobile_body_member}"
                )

            members = thumbnail_members(dt240_index, team_id, kind)
            if not members:
                raise ValueError(f"dt240 has no hub thumbnail for team={team_id} kind={kind}")
            rendered_path = output / "previews" / str(team_id) / f"{suffix}.png"
            rendered_path.parent.mkdir(parents=True, exist_ok=True)
            first_template = read_indexed(dt240_index, members[0])
            preview = render_jersey(atlas, first_template)
            preview_payload = png_bytes(preview)
            rendered_path.write_bytes(preview_payload)

            uniform_ids = []
            for member in members:
                template = read_indexed(dt240_index, member)
                member_preview = render_jersey(atlas, template)
                payload = png_bytes(member_preview)
                replacements[member] = payload
                payload_path = output / "payloads" / member
                payload_path.parent.mkdir(parents=True, exist_ok=True)
                payload_path.write_bytes(payload)
                payload_paths[member] = str(payload_path.resolve())
                match = THUMBNAIL_RE.search(member)
                uniform_ids.append(int(match.group(1)))

            row["kits"].append(
                {
                    "source_kind": source_kind,
                    "suffix": suffix,
                    "uniform_ids": uniform_ids,
                    "thumbnail_members": members,
                    "descriptor_source": descriptor_meta,
                    "body_source": body_meta,
                    "body_decode": body_decode,
                    "atlas_path": str(atlas_path),
                    "atlas_sha256": sha256_file(atlas_path),
                    "runtime_body_member": mobile_body_member,
                    "runtime_body_sha256": sha256_bytes(runtime_body),
                    "runtime_body_matches_source": True,
                    "preview_path": str(rendered_path),
                    "preview_sha256": sha256_bytes(preview_payload),
                }
            )
        team_reports.append(row)

    contact_sheet = output / "kit-preview-contact-sheet.png"
    write_contact_sheet(team_reports, contact_sheet)
    export_obj(output / "jersey.obj")
    if args.preview_only:
        preview_report = {
            "result": "preview_only",
            "renderer": RENDERER_VERSION,
            "teams": team_reports,
            "contact_sheet": str(contact_sheet),
        }
        (output / "preview-report.json").write_text(
            json.dumps(preview_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"result": "preview_only", "contact_sheet": str(contact_sheet)}))
        return preview_report

    cpk_output = output / "cpk-build"
    cpk_output.mkdir()
    actions = {member: "replace" for member in replacements}
    cpk_report = package_cpk(
        ROOT,
        cpk_output,
        "dt240",
        dt240,
        actions,
        replacements,
        payload_paths,
    )
    candidate = Path(cpk_report["candidate"])

    clone_full(loose_base, output, str(base_manifest["build_id"]))
    loose_report = update(output, "dt240_mobile_all.cpk", candidate)
    source_nro = loose_base / "pes21_nx.nro"
    if source_nro.is_file():
        shutil.copy2(source_nro, output / "pes21_nx.nro")

    report = {
        "schema_version": 1,
        "result": "awaiting_hardware_validation",
        "scope": "four_team_hub_thumbnail_canary",
        "teams": team_reports,
        "changed_thumbnail_members": sorted(replacements),
        "changed_thumbnail_count": len(replacements),
        "full_preview_policy": "128x512 _full members preserved in v1",
        "renderer": RENDERER_VERSION,
        "renderer_sha256": sha256_file(ROOT / "tools/kit_preview_mesh.py"),
        "contact_sheet": str(contact_sheet),
        "contact_sheet_sha256": sha256_file(contact_sheet),
        "cpk": cpk_report,
        "loose_cpk": {
            "build_id": loose_report["build_id"],
            "dt240_sha256": next(
                row["sha256"]
                for row in loose_report["files"]
                if row["name"] == "dt240_mobile_all.cpk"
            ),
        },
        "hardware_checks": [
            "barcelona_home_away_preview_matches_latest_kit",
            "manchester_city_home_away_preview_matches_latest_kit",
            "manchester_united_home_away_preview_matches_latest_kit",
            "real_madrid_home_away_preview_matches_latest_kit",
            "selected_preview_matches_in_match_uniform",
            "gameplan_goal_pause_and_restart_remain_stable",
        ],
    }
    report_path = output / "kit-preview-canary-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "result": report["result"],
                "teams": len(team_reports),
                "changed_thumbnail_members": len(replacements),
                "output": str(output),
                "contact_sheet": str(contact_sheet),
                "dt240_sha256": report["loose_cpk"]["dt240_sha256"],
            },
            sort_keys=True,
        )
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument(
        "--football-life-root",
        type=Path,
        default=Path("D:/Games/SP Football Life 2026"),
    )
    parser.add_argument("--loose-base", type=Path, default=DEFAULT_LOOSE_BASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preview-only", action="store_true",
                        help="render and audit thumbnails without packaging any CPK")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
