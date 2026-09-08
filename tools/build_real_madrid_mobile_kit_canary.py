#!/usr/bin/env python3
"""Convert the Football Life Real Madrid kit into PES21 Mobile PNGs.

This is a detached canary generator. It decodes the winning PC FTEX members,
applies the verified Uniform16 anisotropic resize, and emits PNG/import reports.
It never edits a CPK, OBB, runtime source, Makefile, NRO, or release directory.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path("data/real_madrid_mobile_kit_canary.json")
DEFAULT_OUTPUT_DIR = Path("local-debug/real-madrid-mobile-kit-canary/generated")
DEFAULT_MOBILE_DT120 = Path(
    "local-debug/real-madrid-mobile-kit-canary/mobile-source/dt120_mobile_all.cpk"
)
DEFAULT_PC_EDIT_REFERENCE = Path(
    "local-debug/real-madrid-mobile-kit-canary/pc-edit-reference"
)
DEFAULT_MOBILE_EDIT_REFERENCE = Path(
    "local-debug/real-madrid-mobile-kit-canary/mobile-edit-reference"
)

FTEX_HEADER = struct.Struct("<8shhhhBBhiiiBBBBiii16s")
FTEX_MIP = struct.Struct("<iiiBBh")
FTEX_CHUNK = struct.Struct("<HHI")
FTEX_MAGIC = b"FTEX\x85\xeb\x01@"
FTEX_FORMATS = {
    2: {"name": "DXT1", "fourcc": b"DXT1", "block_size": 8},
    4: {"name": "DXT5", "fourcc": b"DXT5", "block_size": 16},
}


def resolve(root: Path, value: Path) -> Path:
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported manifest schema")
    if payload.get("experiment") != "real_madrid_pc_to_pes21_mobile_kit":
        raise ValueError(f"{path}: unexpected experiment")

    team = payload.get("team")
    policy = payload.get("policy")
    transform = payload.get("atlas_transform")
    if not all(isinstance(item, dict) for item in (team, policy, transform)):
        raise ValueError(f"{path}: team, policy, and atlas_transform are required")
    if int(team.get("team_id", 0)) != 109:
        raise ValueError("the canary must remain scoped to Real Madrid team ID 109")
    if policy.get("runtime_integration") is not False:
        raise ValueError("the canary must remain detached from runtime integration")
    if policy.get("allow_unverified_atlas_transform") is not False:
        raise ValueError("unverified atlas transforms must remain disabled")
    if policy.get("allow_anisotropic_resize") is not True:
        raise ValueError("the verified anisotropic resize must be enabled")
    if policy.get("converted_assets_are_runtime_ready") is not False:
        raise ValueError("converted PNGs must not be labelled runtime-ready")
    if transform.get("status") != "verified_same_part_layout":
        raise ValueError("atlas transform has not been verified")
    if transform.get("version") != "uniform16-anisotropic-v1":
        raise ValueError("unexpected atlas transform version")
    if transform.get("source_size") != [2048, 2048]:
        raise ValueError("source body size must be 2048x2048")
    if transform.get("target_size") != [256, 384]:
        raise ValueError("mobile body size must be 256x384")
    if float(transform.get("scale_x", 0)) != 0.125:
        raise ValueError("atlas scale_x must be 1/8")
    if float(transform.get("scale_y", 0)) != 0.1875:
        raise ValueError("atlas scale_y must be 3/16")
    if transform.get("crop") is not None or transform.get("part_reordering") is not False:
        raise ValueError("Uniform16 conversion must not crop or reorder parts")

    source = payload.get("football_life")
    mobile = payload.get("pes21_mobile")
    if not isinstance(source, dict) or not isinstance(mobile, dict):
        raise ValueError(f"{path}: football_life and pes21_mobile are required")
    textures = source.get("textures")
    if not isinstance(textures, dict) or set(textures) != {
        "body",
        "back",
        "leg",
        "name",
        "material",
    }:
        raise ValueError("manifest must describe all five PC kit textures")
    for role, item in textures.items():
        if not isinstance(item, dict):
            raise ValueError(f"football_life.textures.{role} must be an object")
        for key in ("member", "width", "height", "pixel_format", "mip_count", "sha256"):
            if key not in item:
                raise ValueError(f"football_life.textures.{role}.{key} is required")

    return payload


def parse_ftex(payload: bytes) -> dict[str, Any]:
    if len(payload) < FTEX_HEADER.size:
        raise ValueError("FTEX payload is smaller than its header")
    values = FTEX_HEADER.unpack_from(payload)
    (
        magic,
        pixel_format_type,
        width,
        height,
        depth,
        mip_count,
        nrt_flag,
        flags,
        constant_one,
        constant_zero,
        texture_type,
        ftexs_file_count,
        additional_ftexs_file_count,
        zero_byte_a,
        zero_byte_b,
        zero_int_a,
        zero_int_b,
        zero_int_c,
        source_hash,
    ) = values
    if magic != FTEX_MAGIC:
        raise ValueError("invalid FTEX magic")
    if pixel_format_type not in FTEX_FORMATS:
        raise ValueError(f"unsupported FTEX pixel format {pixel_format_type}")
    if width <= 0 or height <= 0 or mip_count <= 0:
        raise ValueError("invalid FTEX dimensions or mip count")
    if constant_one != 1 or constant_zero != 0:
        raise ValueError("unexpected FTEX header constants")
    if any((zero_byte_a, zero_byte_b, zero_int_a, zero_int_b, zero_int_c)):
        raise ValueError("unexpected non-zero FTEX reserved fields")
    mip_table_end = FTEX_HEADER.size + mip_count * FTEX_MIP.size
    if mip_table_end > len(payload):
        raise ValueError("truncated FTEX mip table")

    mips = []
    for index in range(mip_count):
        offset, decoded_size, packed_size, mip_index, file_number, chunks = (
            FTEX_MIP.unpack_from(payload, FTEX_HEADER.size + index * FTEX_MIP.size)
        )
        if mip_index != index:
            raise ValueError(f"unexpected FTEX mip index {mip_index} at {index}")
        if offset < mip_table_end or decoded_size <= 0 or packed_size <= 0:
            raise ValueError(f"invalid FTEX mip metadata at {index}")
        mips.append(
            {
                "offset": offset,
                "decoded_size": decoded_size,
                "packed_size": packed_size,
                "index": mip_index,
                "file_number": file_number,
                "chunk_count": chunks,
            }
        )

    return {
        "pixel_format_type": pixel_format_type,
        "pixel_format": FTEX_FORMATS[pixel_format_type]["name"],
        "width": width,
        "height": height,
        "depth": depth,
        "mip_count": mip_count,
        "nrt_flag": nrt_flag,
        "flags": flags,
        "texture_type": texture_type,
        "ftexs_file_count": ftexs_file_count,
        "additional_ftexs_file_count": additional_ftexs_file_count,
        "source_hash": source_hash.hex(),
        "mips": mips,
    }


def decode_embedded_mip(payload: bytes, metadata: dict[str, Any], mip_index: int) -> bytes:
    mip = metadata["mips"][mip_index]
    if mip["file_number"] != 0 or metadata["ftexs_file_count"] != 0:
        raise ValueError("external FTEXS streams are unsupported by this canary")
    offset = int(mip["offset"])
    chunk_count = int(mip["chunk_count"])
    if chunk_count == 0:
        end = offset + int(mip["packed_size"])
        if end > len(payload):
            raise ValueError("truncated unchunked FTEX mip")
        result = payload[offset:end]
    else:
        index_end = offset + chunk_count * FTEX_CHUNK.size
        if index_end > len(payload):
            raise ValueError("truncated FTEX chunk index")
        pieces: list[bytes] = []
        for chunk_index in range(chunk_count):
            packed_size, decoded_size, encoded_offset = FTEX_CHUNK.unpack_from(
                payload, offset + chunk_index * FTEX_CHUNK.size
            )
            relative = (
                encoded_offset - 0x80000000
                if encoded_offset > 0x80000000
                else encoded_offset
            )
            start = offset + relative
            end = start + packed_size
            if start < index_end or end > len(payload):
                raise ValueError("FTEX chunk points outside its payload")
            piece = payload[start:end]
            if packed_size != decoded_size:
                try:
                    piece = zlib.decompress(piece)
                except zlib.error as error:
                    raise ValueError("invalid compressed FTEX chunk") from error
            if len(piece) != decoded_size:
                raise ValueError("FTEX chunk decoded-size mismatch")
            pieces.append(piece)
        result = b"".join(pieces)
    if len(result) != int(mip["decoded_size"]):
        raise ValueError("FTEX mip decoded-size mismatch")
    return result


def dds_top_mip(metadata: dict[str, Any], block_data: bytes) -> bytes:
    width = int(metadata["width"])
    height = int(metadata["height"])
    format_info = FTEX_FORMATS[int(metadata["pixel_format_type"])]
    expected = ((width + 3) // 4) * ((height + 3) // 4) * format_info["block_size"]
    if len(block_data) != expected:
        raise ValueError(
            f"FTEX block size mismatch: expected {expected}, found {len(block_data)}"
        )
    header = struct.pack(
        "<I6I11I",
        124,
        0x00081007,
        height,
        width,
        expected,
        0,
        1,
        *([0] * 11),
    )
    pixel_format = struct.pack(
        "<II4s5I", 32, 0x4, format_info["fourcc"], 0, 0, 0, 0, 0
    )
    caps = struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return b"DDS " + header + pixel_format + caps + block_data


def decode_ftex_top(payload: bytes) -> tuple[Image.Image, dict[str, Any]]:
    metadata = parse_ftex(payload)
    block_data = decode_embedded_mip(payload, metadata, 0)
    try:
        with Image.open(io.BytesIO(dds_top_mip(metadata, block_data))) as image:
            image.load()
            decoded = image.convert("RGBA")
    except Exception as error:
        raise ValueError("Pillow could not decode the FTEX DDS payload") from error
    metadata = {key: value for key, value in metadata.items() if key != "mips"}
    metadata["top_mip_sha256"] = sha256_bytes(block_data)
    return decoded, metadata


def image_png_bytes(image: Image.Image, *, optimize: bool = True) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=optimize)
    return output.getvalue()


def convert_body(image: Image.Image, transform: dict[str, Any]) -> Image.Image:
    target = tuple(int(value) for value in transform["target_size"])
    resized = image.convert("RGB").resize(target, Image.Resampling.BICUBIC)
    settings = transform["body_output"]
    if settings != {"mode": "P", "colors": 256, "dither": False}:
        raise ValueError("unexpected mobile body output settings")
    return resized.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )


def convert_back(image: Image.Image, transform: dict[str, Any]) -> Image.Image:
    settings = transform["back_output"]
    if settings.get("mode") != "RGBA" or settings.get("resampling") != "bicubic":
        raise ValueError("unexpected mobile back output settings")
    target = tuple(int(value) for value in settings["target_size"])
    return image.convert("RGBA").resize(target, Image.Resampling.BICUBIC)


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
        "member_count": len(rows),
        "data_base": min(int(header["TocOffset"]), int(header["ContentOffset"])),
        "rows": by_lower,
    }


def read_indexed_member(source: dict[str, Any], member: str) -> bytes:
    entry = source["rows"].get(member.lower())
    if entry is None:
        raise KeyError(member)
    row = entry["row"]
    if int(row["FileSize"]) != int(row["ExtractSize"]):
        raise ValueError(f"compressed CPK member is unsupported: {member}")
    with source["path"].open("rb") as stream:
        stream.seek(source["data_base"] + int(row["FileOffset"]))
        payload = stream.read(int(row["FileSize"]))
    if len(payload) != int(row["FileSize"]):
        raise ValueError(f"truncated CPK member: {member}")
    return payload


def source_indexes(root: Path, manifest: dict[str, Any], football_life_root: Path) -> list[dict[str, Any]]:
    archives = manifest["football_life"].get("archive_precedence")
    if not isinstance(archives, list) or not archives:
        raise ValueError("football_life.archive_precedence must be non-empty")
    indexed = []
    for item in sorted(archives, key=lambda row: int(row["precedence"])):
        path = Path(str(item["path"]))
        path = path if path.is_absolute() else football_life_root / path
        if not path.is_file():
            raise FileNotFoundError(path)
        indexed.append(index_cpk(path.resolve(), str(item["key"]), int(item["precedence"])))
    return indexed


def winning_member(indexes: list[dict[str, Any]], member: str) -> tuple[bytes, dict[str, Any]]:
    candidates = []
    for source in indexes:
        entry = source["rows"].get(member.lower())
        if entry is not None:
            row = entry["row"]
            candidates.append(
                {
                    "archive": source["key"],
                    "path": str(source["path"]),
                    "member": entry["name"],
                    "precedence": source["precedence"],
                    "packed_size": int(row["FileSize"]),
                    "extract_size": int(row["ExtractSize"]),
                    "source": source,
                }
            )
    if not candidates:
        raise FileNotFoundError(f"Football Life CPKs do not contain {member}")
    winner = candidates[-1]
    payload = read_indexed_member(winner.pop("source"), str(winner["member"]))
    winner["sha256"] = sha256_bytes(payload)
    winner["candidates"] = [
        {key: value for key, value in item.items() if key != "source"}
        for item in candidates
    ]
    return payload, winner


def validate_texture(
    role: str,
    payload: bytes,
    source: dict[str, Any],
    expected: dict[str, Any],
    allow_source_drift: bool,
) -> tuple[Image.Image, dict[str, Any]]:
    digest = sha256_bytes(payload)
    if digest.lower() != str(expected["sha256"]).lower() and not allow_source_drift:
        raise ValueError(
            f"{role} FTEX hash mismatch: expected {expected['sha256']}, found {digest}"
        )
    image, metadata = decode_ftex_top(payload)
    observed = {
        "width": metadata["width"],
        "height": metadata["height"],
        "pixel_format": metadata["pixel_format"],
        "mip_count": metadata["mip_count"],
    }
    configured = {
        "width": int(expected["width"]),
        "height": int(expected["height"]),
        "pixel_format": str(expected["pixel_format"]),
        "mip_count": int(expected["mip_count"]),
    }
    if observed != configured:
        raise ValueError(f"{role} FTEX metadata mismatch: {observed} != {configured}")
    return image, {
        **source,
        "sha256": digest,
        "ftex": metadata,
    }


def inspect_mobile_targets(path: Path | None, manifest: dict[str, Any]) -> dict[str, Any]:
    texture_members = manifest["pes21_mobile"]["target_members"][:2]
    if path is None or not path.is_file():
        return {
            "status": "unavailable",
            "path": str(path) if path is not None else None,
            "members": [{"member": member, "exists": None} for member in texture_members],
        }
    source = index_cpk(path, "pes21_dt120", 0)
    members = []
    for member in texture_members:
        entry = source["rows"].get(str(member).lower())
        members.append(
            {
                "member": member,
                "exists": entry is not None,
                "size": int(entry["row"]["FileSize"]) if entry else None,
            }
        )
    return {
        "status": "audited",
        "path": str(path),
        "sha256": sha256_file(path),
        "member_count": source["member_count"],
        "members": members,
    }


def verify_layout_masks(pc_dir: Path | None, mobile_dir: Path | None) -> dict[str, Any]:
    if pc_dir is None or mobile_dir is None or not pc_dir.is_dir() or not mobile_dir.is_dir():
        return {"status": "unavailable"}
    names = sorted(
        path.name
        for path in pc_dir.glob("*.png")
        if (mobile_dir / path.name).is_file()
        and path.stem.startswith(("ca_", "pa_", "sh_", "so_"))
    )
    if not names:
        return {"status": "unavailable"}
    absolute_error = 0
    exact = 0
    pixels = 0
    for name in names:
        with Image.open(pc_dir / name) as pc_image, Image.open(mobile_dir / name) as mobile_image:
            pc_alpha = pc_image.convert("RGBA").getchannel("A").resize(
                (256, 384), Image.Resampling.BICUBIC
            )
            mobile_alpha = mobile_image.convert("RGBA").getchannel("A")
            if mobile_alpha.size != (256, 384):
                raise ValueError(f"unexpected mobile edit-mask size: {name}")
            left = pc_alpha.tobytes()
            right = mobile_alpha.tobytes()
            absolute_error += sum(abs(a - b) for a, b in zip(left, right))
            exact += sum(a == b for a, b in zip(left, right))
            pixels += len(left)
    mean_absolute_error = absolute_error / pixels
    exact_ratio = exact / pixels
    status = (
        "verified_same_part_layout"
        if len(names) >= 150 and mean_absolute_error < 1.0 and exact_ratio > 0.98
        else "failed"
    )
    return {
        "status": status,
        "paired_masks": len(names),
        "pc_size": list(Image.open(pc_dir / names[0]).size),
        "mobile_size": [256, 384],
        "resampling": "bicubic",
        "mean_alpha_mae": mean_absolute_error,
        "exact_alpha_ratio": exact_ratio,
    }


def output_metadata(payload: bytes) -> dict[str, Any]:
    with Image.open(io.BytesIO(payload)) as image:
        image.load()
        return {
            "size": len(payload),
            "sha256": sha256_bytes(payload),
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "colors": len(image.getcolors(maxcolors=1_000_000) or []),
        }


def write_or_check(path: Path, payload: bytes, check: bool) -> None:
    if check:
        if not path.is_file():
            raise FileNotFoundError(f"generated artifact is missing: {path}")
        if path.read_bytes() != payload:
            raise RuntimeError(f"generated artifact is stale: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def build(args: argparse.Namespace) -> dict[str, Any]:
    root = resolve(ROOT, args.root)
    manifest_path = resolve(root, args.manifest)
    output_dir = resolve(root, args.output_dir)
    manifest = load_manifest(manifest_path)
    football_life_root = (
        resolve(root, args.football_life_root)
        if args.football_life_root is not None
        else Path(str(manifest["football_life"]["root"])).resolve()
    )
    if not football_life_root.is_dir():
        raise FileNotFoundError(football_life_root)
    indexes = source_indexes(root, manifest, football_life_root)

    texture_root = str(manifest["football_life"]["texture_root"])
    images: dict[str, Image.Image] = {}
    source_report: dict[str, Any] = {"textures": {}}
    for role, expected in manifest["football_life"]["textures"].items():
        member = texture_root + str(expected["member"])
        payload, source = winning_member(indexes, member)
        image, report = validate_texture(
            role, payload, source, expected, args.allow_source_drift
        )
        images[role] = image
        source_report["textures"][role] = report

    descriptor_member = str(manifest["football_life"]["descriptor_member"])
    descriptor, descriptor_source = winning_member(indexes, descriptor_member)
    expected_descriptor = manifest["football_life"]["descriptor"]
    if len(descriptor) != int(expected_descriptor["size"]):
        raise ValueError("unexpected Football Life real-uniform descriptor size")
    if (
        sha256_bytes(descriptor).lower() != str(expected_descriptor["sha256"]).lower()
        and not args.allow_source_drift
    ):
        raise ValueError("Football Life real-uniform descriptor hash mismatch")
    source_report["descriptor"] = descriptor_source

    body = convert_body(images["body"], manifest["atlas_transform"])
    back = convert_back(images["back"], manifest["atlas_transform"])
    prefix = str(manifest["team"]["mobile_texture_prefix"])
    body_name = f"{prefix}.png"
    back_name = f"{prefix}_back.png"
    body_payload = image_png_bytes(body)
    back_payload = image_png_bytes(back)

    mobile_dt120 = resolve(root, args.mobile_dt120) if args.mobile_dt120 else None
    target_audit = inspect_mobile_targets(mobile_dt120, manifest)
    pc_edit = resolve(root, args.pc_edit_reference) if args.pc_edit_reference else None
    mobile_edit = (
        resolve(root, args.mobile_edit_reference) if args.mobile_edit_reference else None
    )
    layout_audit = verify_layout_masks(pc_edit, mobile_edit)
    if layout_audit["status"] == "failed":
        raise RuntimeError("PC/Mobile edit masks rejected the configured atlas transform")

    target_exists = [item["exists"] for item in target_audit["members"]]
    if target_audit["status"] == "audited" and not all(target_exists):
        packaging_status = "blocked_missing_target_members"
    elif target_audit["status"] == "audited":
        packaging_status = "replacement_members_available"
    else:
        packaging_status = "not_audited"

    outputs = {
        body_name: body_payload,
        back_name: back_payload,
    }
    import_manifest = {
        "schema_version": 1,
        "experiment": manifest["experiment"],
        "status": "converted_canary",
        "runtime_integration": False,
        "packaging_status": packaging_status,
        "assets": [
            {
                "file": body_name,
                "member": manifest["pes21_mobile"]["target_members"][0],
                "action": (
                    "replace_existing"
                    if target_exists and target_exists[0]
                    else "add_required"
                ),
            },
            {
                "file": back_name,
                "member": manifest["pes21_mobile"]["target_members"][1],
                "action": (
                    "replace_existing"
                    if len(target_exists) > 1 and target_exists[1]
                    else "add_required"
                ),
            },
        ],
        "descriptor_dependency": manifest["pes21_mobile"]["target_members"][2],
    }
    report = {
        "schema_version": 1,
        "experiment": manifest["experiment"],
        "status": "converted_canary",
        "runtime_ready": False,
        "runtime_integration": False,
        "team": manifest["team"],
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "football_life_root": str(football_life_root),
        "source": source_report,
        "transform": manifest["atlas_transform"],
        "layout_audit": layout_audit,
        "mobile_target_audit": target_audit,
        "packaging_status": packaging_status,
        "outputs": {
            name: output_metadata(payload) for name, payload in outputs.items()
        },
        "safety": {
            "cpk_modified": False,
            "obb_modified": False,
            "runtime_source_modified": False,
            "makefile_modified": False,
            "dist_modified": False,
        },
    }
    outputs["mobile-import-manifest.json"] = json_bytes(import_manifest)
    outputs["conversion-report.json"] = json_bytes(report)
    for name, payload in outputs.items():
        write_or_check(output_dir / name, payload, args.check)

    result = {
        "check": "pass" if args.check else None,
        "status": report["status"],
        "output_dir": str(output_dir),
        "packaging_status": packaging_status,
        "outputs": report["outputs"],
        "layout_audit": layout_audit,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--football-life-root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mobile-dt120", type=Path, default=DEFAULT_MOBILE_DT120)
    parser.add_argument(
        "--pc-edit-reference", type=Path, default=DEFAULT_PC_EDIT_REFERENCE
    )
    parser.add_argument(
        "--mobile-edit-reference", type=Path, default=DEFAULT_MOBILE_EDIT_REFERENCE
    )
    parser.add_argument("--allow-source-drift", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
