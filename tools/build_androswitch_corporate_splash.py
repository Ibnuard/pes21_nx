"""Build the AndroSwitch native titleCorporate splash and patch a release OBB.

The mobile AFP uses a 1560x720 overscan canvas split across six regions for
wide screens and a 1280x960 canvas split across two regions for 4:3 screens.
Only atlas pixels are replaced; AFP layout, scripts, region metadata, member
order, and every unrelated OBB member remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from afp_texture_patch import lzss_decode, lzss_encode  # noqa: E402
from build_inter_miami_release_experiment import cpk_index  # noqa: E402
from patch_cpk_slots import patch_slots  # noqa: E402


DT210_MEMBER = "Expansion/dt210_mobile_android.cpk"
NORMAL_MEMBER = (
    "common/menu/general/titleCorporate_tex/titleCorporate_konami.bin"
)
WIDE_MEMBER = (
    "common/menu/general/titleCorporate_tex/titleCorporate_konami_wide.bin"
)
WESYS_TAG = b"WESYS"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def member_bytes(cpk: Path, member: str) -> bytes:
    _header, rows, base = cpk_index(cpk)
    row = rows[member]
    with cpk.open("rb") as source:
        source.seek(base + int(row["FileOffset"]))
        result = source.read(int(row["FileSize"]))
    if len(result) != int(row["FileSize"]):
        raise RuntimeError(f"truncated CPK member: {member}")
    return result


def extract_member(cpk: Path, member: str, output: Path) -> None:
    _header, rows, base = cpk_index(cpk)
    row = rows[member]
    remaining = int(row["FileSize"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with cpk.open("rb") as source, output.open("wb") as destination:
        source.seek(base + int(row["FileOffset"]))
        while remaining:
            chunk = source.read(min(4 * 1024 * 1024, remaining))
            if not chunk:
                raise RuntimeError(f"truncated CPK member: {member}")
            destination.write(chunk)
            remaining -= len(chunk)


def decode_wesys(payload: bytes) -> bytes:
    if len(payload) < 16 or payload[3:8] != WESYS_TAG:
        raise ValueError("invalid WESYS titleCorporate payload")
    packed_size, raw_size = struct.unpack_from("<II", payload, 8)
    if packed_size != len(payload) - 16:
        raise ValueError("WESYS compressed size mismatch")
    raw = zlib.decompress(payload[16:])
    if len(raw) != raw_size:
        raise ValueError("WESYS expanded size mismatch")
    return raw


def encode_wesys(raw: bytes, source_header: bytes) -> bytes:
    if len(source_header) != 8 or source_header[3:8] != WESYS_TAG:
        raise ValueError("invalid source WESYS header")
    compressed = zlib.compress(raw, 9)
    check = zlib.decompress(compressed)
    if check != raw:
        raise RuntimeError("WESYS zlib roundtrip failed")
    return source_header + struct.pack("<II", len(compressed), len(raw)) + compressed


def read_multi_atlas(container: bytes) -> tuple[list[bytes], list[dict], tuple]:
    base = container.find(b"TXP2")
    if base < 0:
        raise ValueError("missing TXP2")
    txp_length = struct.unpack_from(">I", container, base + 12)[0]
    txp = container[base : base + txp_length]
    flags, count, table = struct.unpack_from(">III", txp, 20)
    if flags != 0x37FDF or count != 2:
        raise ValueError(f"unsupported titleCorporate atlas schema {flags:x}/{count}")
    atlases: list[bytes] = []
    entries: list[tuple[int, int, int]] = []
    for index in range(count):
        name, length, offset = struct.unpack_from(">III", txp, table + index * 12)
        raw_size, packed_size = struct.unpack_from(">II", txp, offset)
        if packed_size != length - 8 or offset + length > len(txp):
            raise ValueError("invalid titleCorporate atlas payload")
        atlas = lzss_decode(txp[offset + 8 : offset + length], raw_size)
        width, height = struct.unpack_from(">HH", atlas, 16)
        if len(atlas) != 64 + width * height * 4:
            raise ValueError("unsupported titleCorporate pixel layout")
        atlases.append(atlas)
        entries.append((name, length, offset))

    region_count, region_table, region_names = struct.unpack_from(">III", txp, 36)
    named_count = struct.unpack_from(">I", txp, region_names + 16)[0]
    names_table = struct.unpack_from(">I", txp, region_names + 24)[0]
    if named_count != region_count:
        raise ValueError("titleCorporate region count mismatch")
    regions: list[dict | None] = [None] * region_count
    for item in range(named_count):
        _crc, index, name_offset = struct.unpack_from(
            ">III", txp, names_table + item * 12
        )
        name = txp[name_offset : txp.index(b"\0", name_offset)]
        if name and name[0] >= 0xA0:
            name = bytes((value + 128) & 255 for value in name)
        rect = struct.unpack_from(">5H", txp, region_table + index * 10)
        regions[index] = {"name": name.decode("ascii"), "rect": rect}
    if any(region is None for region in regions):
        raise ValueError("unnamed titleCorporate region")
    return atlases, list(regions), (base, table, entries)


def atlas_box(rect: tuple[int, int, int, int, int]) -> tuple[int, int, int, int]:
    _atlas, left, top, right, bottom = rect
    if not all(value & 1 for value in (left, top, right, bottom)):
        raise ValueError(f"unexpected titleCorporate half-pixel rectangle: {rect}")
    return ((left - 1) // 2, (top - 1) // 2,
            (right + 1) // 2, (bottom + 1) // 2)


def rgba_to_argb(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA").tobytes()
    argb = bytearray(len(rgba))
    argb[0::4] = rgba[3::4]
    argb[1::4] = rgba[0::4]
    argb[2::4] = rgba[1::4]
    argb[3::4] = rgba[2::4]
    return bytes(argb)


def replace_multi_atlas(container: bytes, images: list[Image.Image]) -> bytes:
    originals, original_regions, layout = read_multi_atlas(container)
    base, table, entries = layout
    if len(images) != len(originals):
        raise ValueError("must replace every titleCorporate atlas")

    packed: list[bytes] = []
    expected_pixels: list[bytes] = []
    for original, image in zip(originals, images):
        width, height = struct.unpack_from(">HH", original, 16)
        if image.size != (width, height):
            raise ValueError(f"atlas size changed: {image.size} != {(width, height)}")
        pixels = rgba_to_argb(image)
        atlas = original[:64] + pixels
        compressed = lzss_encode(atlas, candidate_limit=32, min_match=3)
        if lzss_decode(compressed, len(atlas)) != atlas:
            raise RuntimeError("titleCorporate LZSS roundtrip failed")
        packed.append(struct.pack(">II", len(atlas), len(compressed)) + compressed)
        expected_pixels.append(pixels)

    first_offset = min(entry[2] for entry in entries)
    output = bytearray(container[: base + first_offset])
    for index, payload in enumerate(packed):
        while (len(output) - base) & 3:
            output.append(0)
        offset = len(output) - base
        output.extend(payload)
        name = entries[index][0]
        struct.pack_into(">III", output, base + table + index * 12,
                         name, len(payload), offset)
    txp_length = len(output) - base
    struct.pack_into(">I", output, base + 12, txp_length)
    # The outer AFP header mirrors the TXP2 byte length on this exact asset.
    struct.pack_into("<I", output, 12, txp_length)
    output.extend(b"\0" * ((-len(output)) % 16))

    verified, verified_regions, _ = read_multi_atlas(bytes(output))
    if verified_regions != original_regions:
        raise RuntimeError("titleCorporate region metadata changed")
    for atlas, pixels in zip(verified, expected_pixels):
        if atlas[64:] != pixels:
            raise RuntimeError("titleCorporate atlas verification failed")
    return bytes(output)


def composite_atlases(
    decoded: bytes,
    canvas: Image.Image,
    source_boxes: dict[str, tuple[int, int, int, int]],
) -> tuple[bytes, list[dict]]:
    raw_atlases, regions, _layout = read_multi_atlas(decoded)
    atlas_images: list[Image.Image] = []
    for atlas in raw_atlases:
        width, height = struct.unpack_from(">HH", atlas, 16)
        atlas_images.append(
            Image.frombytes("RGBA", (width, height), atlas[64:], "raw", "ARGB")
        )

    report: list[dict] = []
    observed = set()
    for region in regions:
        name = region["name"]
        if name not in source_boxes:
            raise ValueError(f"unexpected titleCorporate region: {name}")
        observed.add(name)
        rect = tuple(region["rect"])
        atlas_index = rect[0]
        destination = atlas_box(rect)
        source = source_boxes[name]
        tile = canvas.crop(source)
        if tile.size != (destination[2] - destination[0],
                         destination[3] - destination[1]):
            raise ValueError(
                f"tile geometry mismatch for {name}: {tile.size} -> {destination}"
            )
        atlas_images[atlas_index].paste(tile, destination)
        report.append({"region": name, "atlas": atlas_index,
                       "source": source, "destination": destination})
    if observed != set(source_boxes):
        raise ValueError(f"missing titleCorporate regions: {set(source_boxes) - observed}")
    return replace_multi_atlas(decoded, atlas_images), report


def build_canvas(frame: Image.Image, size: tuple[int, int], offset: tuple[int, int]) -> Image.Image:
    background = frame.getpixel((0, 0))
    canvas = Image.new("RGBA", size, background)
    canvas.alpha_composite(frame, offset)
    return canvas


def flatten_splash_background(authored: Image.Image) -> Image.Image:
    """Keep the approved wordmark while matching the requested flat blue.

    The generated source contains low-amplitude blue texture. Native Konami
    atlases are intentionally tiny because their background is flat; retaining
    that noise makes the replacement over 1 MiB and no longer fits the verified
    CPK slots. The red channel cleanly separates the white/yellow wordmark from
    the blue reference, so it also gives us smooth antialiased edges.
    """
    source = authored.convert("RGBA")
    red, green, blue, _alpha = source.split()
    foreground = red.point(lambda value: 255 if value > 12 else 0)
    yellow = ImageChops.multiply(
        ImageChops.multiply(
            red.point(lambda value: 255 if value > 35 else 0),
            green.point(lambda value: 255 if value > 45 else 0),
        ),
        blue.point(lambda value: 255 if value < 120 else 0),
    )
    white = ImageChops.subtract(foreground, yellow)
    flat = Image.new("RGBA", source.size, (0, 28, 97, 255))
    flat.paste((248, 248, 250, 255), (0, 0), white)
    flat.paste((210, 235, 20, 255), (0, 0), yellow)
    return flat


def quantize_brand_palette(image: Image.Image) -> Image.Image:
    palette = Image.new("P", (1, 1))
    # Explicit intermediate colors retain smooth font edges without allowing
    # the adaptive quantizer to discard the much smaller lime PROJECT line.
    colors = [
        0, 28, 97,
        82, 101, 148,
        165, 175, 199,
        248, 248, 250,
        70, 97, 71,
        140, 166, 46,
        210, 235, 20,
    ]
    palette.putpalette(colors + [0] * (768 - len(colors)))
    return image.convert("RGB").quantize(
        palette=palette, dither=Image.Dither.NONE
    ).convert("RGBA")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-obb", type=Path, required=True)
    parser.add_argument(
        "--splash", type=Path,
        default=ROOT / "art/main_menu/androswitch-boot-splash-v3.png",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "local-debug/startup-brand-v2",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source_obb = args.source_obb.resolve()
    splash_path = args.splash.resolve()
    output = args.output.resolve()
    work = output / "cpk-work"
    install = output / "install"
    output_obb = install / source_obb.name
    dt210 = work / "dt210_mobile_android.cpk"
    patched_dt210 = work / "dt210_mobile_android-androswitch.cpk"
    normal_path = work / "titleCorporate_konami-androswitch.bin"
    wide_path = work / "titleCorporate_konami_wide-androswitch.bin"
    generated = (dt210, patched_dt210, normal_path, wide_path, output_obb)
    for path in generated:
        if path.exists():
            if not args.force:
                raise FileExistsError(f"refusing to overwrite {path}; pass --force")
            path.unlink()
    work.mkdir(parents=True, exist_ok=True)
    install.mkdir(parents=True, exist_ok=True)

    extract_member(source_obb, DT210_MEMBER, dt210)
    normal_payload = member_bytes(dt210, NORMAL_MEMBER)
    wide_payload = member_bytes(dt210, WIDE_MEMBER)

    authored = Image.open(splash_path).convert("RGBA")
    if authored.size != (1920, 1080):
        raise ValueError("AndroSwitch splash must be authored at 1920x1080")
    authored = flatten_splash_background(authored)
    authored.save(output / "corporate-source-flattened-preview.png")
    frame = quantize_brand_palette(
        authored.resize((1280, 720), Image.Resampling.LANCZOS)
    )
    wide_canvas = build_canvas(frame, (1560, 720), (140, 0))
    normal_canvas = build_canvas(frame, (1280, 960), (0, 120))
    wide_canvas.crop((140, 0, 1420, 720)).save(
        output / "corporate-wide-visible-preview.png"
    )
    normal_canvas.save(output / "corporate-normal-canvas-preview.png")

    normal_boxes = {
        "titleCorporate-konami-0": (0, 0, 1024, 960),
        "titleCorporate-konami-1": (1024, 0, 1280, 960),
    }
    wide_boxes = {
        "titleCorporate-konami-wide-0": (0, 0, 1024, 512),
        "titleCorporate-konami-wide-1": (1024, 0, 1536, 512),
        "titleCorporate-konami-wide-2": (1536, 0, 1560, 512),
        "titleCorporate-konami-wide-3": (0, 512, 1024, 720),
        "titleCorporate-konami-wide-4": (1024, 512, 1536, 720),
        "titleCorporate-konami-wide-5": (1536, 512, 1560, 720),
    }
    normal_raw, normal_report = composite_atlases(
        decode_wesys(normal_payload), normal_canvas, normal_boxes
    )
    wide_raw, wide_report = composite_atlases(
        decode_wesys(wide_payload), wide_canvas, wide_boxes
    )
    normal_path.write_bytes(encode_wesys(normal_raw, normal_payload[:8]))
    wide_path.write_bytes(encode_wesys(wide_raw, wide_payload[:8]))

    inner_report = patch_slots(dt210, patched_dt210, {
        NORMAL_MEMBER: normal_path,
        WIDE_MEMBER: wide_path,
    })
    outer_report = patch_slots(source_obb, output_obb, {
        DT210_MEMBER: patched_dt210,
    })
    report = {
        "status": "androswitch_native_corporate_splash_built",
        "source_obb": str(source_obb),
        "source_obb_sha256": sha256_file(source_obb),
        "output_obb": str(output_obb),
        "output_obb_sha256": sha256_file(output_obb),
        "obb_size_unchanged": output_obb.stat().st_size == source_obb.stat().st_size,
        "dt210_size_unchanged": patched_dt210.stat().st_size == dt210.stat().st_size,
        "splash": str(splash_path),
        "normal_regions": normal_report,
        "wide_regions": wide_report,
        "inner_patch": inner_report,
        "outer_patch": outer_report,
    }
    report_path = output / "build-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
