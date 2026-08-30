#!/usr/bin/env python3
"""Extract the converted team's original EF10 thumbnails as PNG files.

EF10 stores its standard-player thumbnails as UE4.26 Texture2D assets in the
pc1000 IO Store container. Retoc first converts the selected Zen packages to
legacy ``.uasset``/``.uexp`` files. The cooked texture payload is ETC2 RGBA;
``texture2ddecoder`` returns BGRA bytes, which are channel-swapped into an
ordinary transparent 128x128 PNG for the PES21 portrait importer.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path

from PIL import Image

try:
    import texture2ddecoder
except ImportError as error:
    raise RuntimeError(
        "texture2ddecoder is required to decode EF10 ETC2 thumbnails"
    ) from error


DEFAULT_AES_KEY = (
    "0x4552D45005DFE94964893F4925EC747D"
    "3D591401E060ED8B3D58BE5721C81295"
)
PIXEL_FORMAT = b"PF_ETC2_RGBA\0"


def decode_texture(uexp: Path, output: Path) -> dict[str, int | str]:
    data = uexp.read_bytes()
    format_offset = data.find(PIXEL_FORMAT)
    if format_offset < 16:
        raise RuntimeError(f"ETC2 RGBA platform data not found: {uexp}")

    width, height, slices, string_length = struct.unpack_from(
        "<IIII", data, format_offset - 16
    )
    if string_length != len(PIXEL_FORMAT):
        raise RuntimeError(
            f"unexpected pixel format string length in {uexp}: {string_length}"
        )
    if slices != 1 or width <= 0 or height <= 0:
        raise RuntimeError(
            f"unexpected texture dimensions in {uexp}: {width}x{height}x{slices}"
        )

    # Cooked FTexturePlatformData immediately follows the pixel-format string:
    # first-mip, mip-count, inline flag, then FByteBulkData. The EF10 thumbnail
    # bulk data has a 32-byte prefix and is stored inline.
    platform_tail = format_offset + len(PIXEL_FORMAT)
    first_mip, mip_count, inline_flag, bulk_flags = struct.unpack_from(
        "<IIII", data, platform_tail
    )
    element_count, size_on_disk = struct.unpack_from("<II", data, platform_tail + 16)
    payload_offset = platform_tail + 32
    if first_mip != 0 or mip_count < 1 or inline_flag != 1:
        raise RuntimeError(
            f"unsupported EF10 thumbnail mip layout in {uexp}: "
            f"first={first_mip}, count={mip_count}, inline={inline_flag}"
        )
    if not bulk_flags & 0x40:
        raise RuntimeError(f"EF10 thumbnail payload is not inline: {uexp}")
    if element_count != size_on_disk:
        raise RuntimeError(f"compressed EF10 thumbnail payload is unsupported: {uexp}")
    expected_size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if size_on_disk != expected_size:
        raise RuntimeError(
            f"unexpected ETC2 payload size in {uexp}: "
            f"expected {expected_size}, found {size_on_disk}"
        )
    payload = data[payload_offset : payload_offset + size_on_disk]
    if len(payload) != size_on_disk:
        raise RuntimeError(f"truncated ETC2 thumbnail payload: {uexp}")

    bgra = texture2ddecoder.decode_etc2a8(payload, width, height)
    image = Image.frombytes("RGBA", (width, height), bgra)
    blue, green, red, alpha = image.split()
    image = Image.merge("RGBA", (red, green, blue, alpha))
    if not image.getchannel("A").getbbox():
        raise RuntimeError(f"decoded EF10 thumbnail is fully transparent: {uexp}")
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    return {
        "width": width,
        "height": height,
        "payload_offset": payload_offset,
        "payload_size": size_on_disk,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--container-dir",
        type=Path,
        default=Path("local-debug/efootball10-audit/pad-assets/assets"),
        help="directory containing pc1000_mobile_and.utoc/ucas and global.utoc/ucas",
    )
    parser.add_argument(
        "--retoc",
        type=Path,
        default=Path("local-debug/tools/retoc-v0.1.5/retoc.exe"),
    )
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=Path(
            "local-debug/efootball10-player-patch/validation-report.json"
        ),
    )
    parser.add_argument(
        "--legacy-dir",
        type=Path,
        default=Path("local-debug/efootball10-portrait-legacy"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("local-debug/efootball10-portraits"),
    )
    parser.add_argument(
        "--blank-missing",
        action="store_true",
        help=(
            "write a transparent 128x128 PNG when EF10 has no thumbnail asset; "
            "this prevents the PES21 surrogate's unrelated portrait from leaking"
        ),
    )
    parser.add_argument("--aes-key", default=DEFAULT_AES_KEY)
    args = parser.parse_args()

    container_dir = args.container_dir.resolve()
    retoc = args.retoc.resolve()
    validation_report = args.validation_report.resolve()
    legacy_dir = args.legacy_dir.resolve()
    output_dir = args.output_dir.resolve()
    required_containers = (
        "pc1000_mobile_and.utoc",
        "pc1000_mobile_and.ucas",
        "global.utoc",
        "global.ucas",
    )
    for name in required_containers:
        if not (container_dir / name).is_file():
            raise FileNotFoundError(container_dir / name)
    if not retoc.is_file():
        raise FileNotFoundError(retoc)
    if not validation_report.is_file():
        raise FileNotFoundError(validation_report)

    conversion = json.loads(validation_report.read_text(encoding="utf-8"))
    players = conversion["players"]
    legacy_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[dict[str, object]] = []
    blank_count = 0
    for index, player in enumerate(players, 1):
        player_id = int(player["ef10_player_id"])
        relative = (
            Path("PesMobile/Content/Assets/ui/Data/Thumbnail/Player")
            / f"{player_id}_"
        )
        uexp = legacy_dir / relative.with_suffix(".uexp")
        output = output_dir / f"{player_id}.png"
        placeholder = False
        if not uexp.is_file():
            if args.blank_missing:
                Image.new("RGBA", (128, 128), (0, 0, 0, 0)).save(
                    output, format="PNG", optimize=True
                )
                placeholder = True
                blank_count += 1
            else:
                command = [
                    str(retoc),
                    "--aes-key",
                    args.aes_key,
                    "--override-container-header-version",
                    "PreInitial",
                    "to-legacy",
                    str(container_dir),
                    str(legacy_dir),
                    "--filter",
                    f"{player_id}_",
                    "--version",
                    "UE4_26",
                    "--no-shaders",
                    "--no-parallel",
                ]
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                if result.returncode != 0 or not uexp.is_file():
                    raise RuntimeError(
                        f"retoc failed to extract EF10 portrait {player_id}:\n"
                        f"{result.stdout}"
                    )

        if placeholder:
            texture: dict[str, int | str] = {
                "width": 128,
                "height": 128,
                "payload_offset": 0,
                "payload_size": 0,
            }
        else:
            texture = decode_texture(uexp, output)
        extracted.append(
            {
                "ef10_player_id": player_id,
                "pes21_player_id": int(player["pes21_player_id"]),
                "name": player["name"],
                "source": None if placeholder else str(uexp),
                "output": str(output),
                "placeholder": placeholder,
                **texture,
            }
        )
        if index == 1 or index % 100 == 0 or index == len(players):
            print(
                f"[{index}/{len(players)}] {player_id} -> {output.name}",
                flush=True,
            )

    report = {
        "team_id": conversion["team_id"],
        "team_symbol": conversion["team_symbol"],
        "real_portraits": len(extracted) - blank_count,
        "blank_portraits": blank_count,
        "portraits": extracted,
    }
    report_path = output_dir / "extraction-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"extracted portraits: {len(extracted)}")
    print(f"real portraits: {len(extracted) - blank_count}")
    print(f"blank portraits: {blank_count}")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
