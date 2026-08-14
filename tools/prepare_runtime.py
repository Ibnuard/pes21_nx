#!/usr/bin/env python3
"""Prepare a validated PES 2021 NX runtime from three user-owned inputs."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import struct
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

from build_offline_responses import (
    EXPECTED_PAYLOAD_SIZES,
    apply_compatibility_overrides,
    load_apk_responses,
    write_responses,
)


TARGET_APK = {
    "size": 99_876_725,
    "sha256": "c9cc96236199444a6effceb75049d419642b004a2b07eaa664dd8cd42d0a1589",
}
TARGET_MAIN_OBB = {
    "size": 459_211_392,
    "sha256": "70a1d6a25dfa186034d4903e01a926fef71911260b6fcc6b13be3cb9a7f2cdd7",
}
TARGET_PATCH_OBB = {
    "size": 1_376_863_488,
    "sha256": "675533cd0d056450897d19821e6009072a6a0f9ac60ea273f57b709c45f0a490",
}

PATCH_OBB_NAME = "patch.305030001.jp.nyan2021.pesam.obb"
MAIN_PAK_PATH = "PesMobile/Content/Paks/PesMobile-Android_ETC1.pak"
CORE_RUNTIME_SIZES = {
    "libavs2-core.so": 491_032,
    "libafp-core.so": 1_401_216,
    "libUE4.so": 157_571_792,
    MAIN_PAK_PATH: 459_211_124,
    PATCH_OBB_NAME: 1_376_863_488,
}
LOCALE_CPK_SIZES = {
    "dt530_mobile_bra_all.cpk": 173_204,
    "dt530_mobile_can_all.cpk": 165_480,
    "dt530_mobile_eng_all.cpk": 198_701,
    "dt530_mobile_fra_all.cpk": 193_581,
    "dt530_mobile_ger_all.cpk": 188_884,
    "dt530_mobile_ita_all.cpk": 189_454,
    "dt530_mobile_jpn_all.cpk": 235_766,
    "dt530_mobile_kor_all.cpk": 129_215,
    "dt530_mobile_man_all.cpk": 165_584,
    "dt530_mobile_spa_all.cpk": 194_310,
}
APK_LIBRARIES = {
    "lib/arm64-v8a/libUE4.so": "libUE4.so",
    "lib/arm64-v8a/libafp-core.so": "libafp-core.so",
    "lib/arm64-v8a/libavs2-core.so": "libavs2-core.so",
}
APK_ICON_PATH = "res/drawable-xxxhdpi-v4/icon.png"
NRO_ASSET_HEADER_SIZE = 0x38
NRO_ASSET_OFFSET_FIELD = 0x18
NRO_ASSET_MAGIC = b"ASET"
NRO_ICON_DIMENSIONS = (256, 256)
BUFFER_SIZE = 8 * 1024 * 1024


def discover_sized_input(
    directory: Path, suffix: str, expected_size: int, label: str
) -> Path:
    candidates = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() == suffix
        and path.stat().st_size == expected_size
    ]
    if len(candidates) != 1:
        names = ", ".join(path.name for path in candidates) or "none"
        raise RuntimeError(
            f"expected exactly one supported {label} in {directory}; "
            f"size-matching candidates: {names}"
        )
    return candidates[0]


def discover_inputs(directory: Path) -> tuple[Path, Path, Path, Path]:
    directory = directory.resolve()
    if not directory.is_dir():
        raise RuntimeError(f"input directory not found: {directory}")

    apk = discover_sized_input(directory, ".apk", TARGET_APK["size"], "APK")
    main_obb = discover_sized_input(
        directory, ".obb", TARGET_MAIN_OBB["size"], "main OBB"
    )
    patch_obb = discover_sized_input(
        directory, ".obb", TARGET_PATCH_OBB["size"], "patch OBB"
    )

    nro_candidates = [
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() == ".nro"
    ]
    exact_nro = [
        path for path in nro_candidates if path.name.lower() == "pes21_nx.nro"
    ]
    if len(exact_nro) == 1:
        nro = exact_nro[0]
    elif len(nro_candidates) == 1:
        nro = nro_candidates[0]
    else:
        names = ", ".join(path.name for path in nro_candidates) or "none"
        raise RuntimeError(
            f"expected one NRO in {directory}; candidates: {names}. "
            "Keep only the release NRO or name the preferred file pes21_nx.nro."
        )

    print(f"Detected APK: {apk.name}")
    print(f"Detected main OBB: {main_obb.name}")
    print(f"Detected patch OBB: {patch_obb.name}")
    print(f"Detected NRO: {nro.name}")
    return apk, main_obb, patch_obb, nro


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(BUFFER_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_input(path: Path, label: str, expected: dict[str, Any]) -> str:
    if not path.is_file():
        raise RuntimeError(f"{label} not found: {path}")
    size = path.stat().st_size
    if size != expected["size"]:
        raise RuntimeError(
            f"{label} size mismatch: expected {expected['size']}, found {size}"
        )
    digest = sha256_file(path)
    if digest.lower() != expected["sha256"]:
        raise RuntimeError(
            f"{label} SHA-256 mismatch. This preparer supports only the tested "
            "PES 2021 Mobile v5.3.0 Nyan Mod Offline target."
        )
    return digest


def build_nro_icon(apk: Path) -> tuple[bytes, str]:
    try:
        from PIL import Image
    except ImportError as error:
        raise RuntimeError(
            "Pillow is required to convert the APK icon for the NRO"
        ) from error

    with zipfile.ZipFile(apk) as archive:
        try:
            source_icon = archive.read(APK_ICON_PATH)
        except KeyError as error:
            raise RuntimeError(
                f"APK icon is missing: {APK_ICON_PATH}"
            ) from error

    try:
        with Image.open(io.BytesIO(source_icon)) as image:
            image.load()
            image = image.convert("RGB")
            if image.size != NRO_ICON_DIMENSIONS:
                image = image.resize(NRO_ICON_DIMENSIONS, Image.Resampling.LANCZOS)
            encoded = io.BytesIO()
            image.save(
                encoded,
                format="JPEG",
                quality=95,
                optimize=True,
                progressive=False,
            )
    except Exception as error:
        raise RuntimeError("failed to decode the APK application icon") from error

    icon = encoded.getvalue()
    if not icon.startswith(b"\xff\xd8") or not icon.endswith(b"\xff\xd9"):
        raise RuntimeError("converted NRO icon is not a valid JPEG stream")
    return icon, hashlib.sha256(source_icon).hexdigest()


def inject_apk_icon_into_nro(apk: Path, nro: Path, output: Path) -> dict[str, Any]:
    source = nro.read_bytes()
    if len(source) < NRO_ASSET_OFFSET_FIELD + 4:
        raise RuntimeError("release NRO is too small to contain an NRO header")

    asset_offset = struct.unpack_from("<I", source, NRO_ASSET_OFFSET_FIELD)[0]
    if (
        asset_offset < NRO_ASSET_HEADER_SIZE
        or asset_offset + NRO_ASSET_HEADER_SIZE > len(source)
        or source[asset_offset : asset_offset + 4] != NRO_ASSET_MAGIC
    ):
        raise RuntimeError("release NRO has no valid ASET metadata header")

    old_header = source[asset_offset : asset_offset + NRO_ASSET_HEADER_SIZE]

    def read_asset(pair_offset: int, label: str) -> bytes:
        relative, size = struct.unpack_from("<QQ", old_header, pair_offset)
        if size == 0:
            return b""
        start = asset_offset + relative
        end = start + size
        if relative < NRO_ASSET_HEADER_SIZE or start < asset_offset or end > len(source):
            raise RuntimeError(f"release NRO has an invalid {label} asset range")
        return source[start:end]

    nacp = read_asset(0x18, "NACP")
    romfs = read_asset(0x28, "RomFS")
    if not nacp:
        raise RuntimeError("release NRO is missing its NACP metadata")

    icon, apk_icon_sha256 = build_nro_icon(apk)
    header = bytearray(old_header)
    payload = bytearray()
    cursor = NRO_ASSET_HEADER_SIZE
    for pair_offset, asset in ((0x08, icon), (0x18, nacp), (0x28, romfs)):
        if asset:
            struct.pack_into("<QQ", header, pair_offset, cursor, len(asset))
            payload.extend(asset)
            cursor += len(asset)
        else:
            struct.pack_into("<QQ", header, pair_offset, 0, 0)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as prepared:
        prepared.write(source[:asset_offset])
        prepared.write(header)
        prepared.write(payload)

    return {
        "source": APK_ICON_PATH,
        "source_sha256": apk_icon_sha256,
        "format": "JPEG",
        "width": NRO_ICON_DIMENSIONS[0],
        "height": NRO_ICON_DIMENSIONS[1],
        "size": len(icon),
        "sha256": hashlib.sha256(icon).hexdigest(),
    }


def copy_stream(source: BinaryIO, destination: Path, size: int | None = None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with destination.open("wb") as output:
        while True:
            limit = BUFFER_SIZE if size is None else min(BUFFER_SIZE, size - written)
            if limit <= 0:
                break
            chunk = source.read(limit)
            if not chunk:
                break
            output.write(chunk)
            written += len(chunk)
    if size is not None and written != size:
        raise RuntimeError(
            f"short extraction for {destination.name}: expected {size}, wrote {written}"
        )


def extract_zip_member(archive: zipfile.ZipFile, member: str, output: Path) -> None:
    try:
        info = archive.getinfo(member)
    except KeyError as error:
        raise RuntimeError(f"archive entry is missing: {member}") from error
    with archive.open(info, "r") as source:
        copy_stream(source, output, info.file_size)


def decrypt_utf(data: bytes) -> bytes:
    output = bytearray(data)
    key = 0x655F
    for index in range(len(output)):
        output[index] ^= key & 0xFF
        key = (key * 0x4115) & 0xFFFFFFFF
    return bytes(output)


def parse_utf_table(data: bytes) -> list[dict[str, Any]]:
    if data[:4] != b"@UTF":
        raise RuntimeError("invalid CRI UTF table signature")

    def u16(offset: int) -> int:
        return struct.unpack_from(">H", data, offset)[0]

    def u32(offset: int) -> int:
        return struct.unpack_from(">I", data, offset)[0]

    table_size = u32(4)
    rows_offset = 8 + u32(8)
    strings_offset = 8 + u32(12)
    columns = u16(24)
    row_length = u16(26)
    row_count = u32(28)
    if table_size + 8 > len(data):
        raise RuntimeError("truncated CRI UTF table")

    def string_at(relative: int) -> str:
        start = strings_offset + relative
        if start < strings_offset or start >= len(data):
            raise RuntimeError("invalid CRI UTF string offset")
        end = data.find(b"\0", start)
        if end < 0:
            raise RuntimeError("unterminated CRI UTF string")
        return data[start:end].decode("utf-8")

    numeric_formats = {
        0: ">B",
        1: ">b",
        2: ">H",
        3: ">h",
        4: ">I",
        5: ">i",
        6: ">Q",
        7: ">q",
        8: ">f",
    }

    def read_value(value_type: int, offset: int) -> tuple[Any, int]:
        if value_type in numeric_formats:
            fmt = numeric_formats[value_type]
            width = struct.calcsize(fmt)
            return struct.unpack_from(fmt, data, offset)[0], width
        if value_type == 10:
            return string_at(u32(offset)), 4
        if value_type == 11:
            return (u32(offset), u32(offset + 4)), 8
        raise RuntimeError(f"unsupported CRI UTF value type: {value_type}")

    descriptor_offset = 32
    descriptors: list[tuple[str, int, int, Any]] = []
    for _ in range(columns):
        flag = data[descriptor_offset]
        name = string_at(u32(descriptor_offset + 1))
        descriptor_offset += 5
        storage = flag & 0xF0
        value_type = flag & 0x0F
        constant = None
        if storage == 0x30:
            constant, width = read_value(value_type, descriptor_offset)
            descriptor_offset += width
        elif storage not in (0x10, 0x50):
            raise RuntimeError(f"unsupported CRI UTF storage type: {storage:#x}")
        descriptors.append((name, storage, value_type, constant))

    rows = []
    for row_index in range(row_count):
        value_offset = rows_offset + row_index * row_length
        row: dict[str, Any] = {}
        for name, storage, value_type, constant in descriptors:
            if storage == 0x10:
                row[name] = None if value_type in (10, 11) else 0
            elif storage == 0x30:
                row[name] = constant
            else:
                row[name], width = read_value(value_type, value_offset)
                value_offset += width
        rows.append(row)
    return rows


def read_cpk_packet(source: BinaryIO, offset: int, signature: bytes) -> list[dict[str, Any]]:
    source.seek(offset)
    header = source.read(16)
    if len(header) != 16 or header[:4] != signature:
        raise RuntimeError(
            f"invalid {signature.decode().strip()} packet at offset {offset}"
        )
    packet_size = struct.unpack_from("<Q", header, 8)[0]
    if packet_size <= 0 or packet_size > 64 * 1024 * 1024:
        raise RuntimeError(f"invalid CPK packet size: {packet_size}")
    packet = source.read(packet_size)
    if len(packet) != packet_size:
        raise RuntimeError("truncated CPK packet")
    if packet[:4] != b"@UTF":
        packet = decrypt_utf(packet)
    return parse_utf_table(packet)


def extract_locale_cpks(patch_obb: Path, output: Path) -> None:
    with patch_obb.open("rb") as source:
        header_rows = read_cpk_packet(source, 0, b"CPK ")
        if len(header_rows) != 1:
            raise RuntimeError("unexpected CPK header row count")
        header = header_rows[0]
        toc_offset = int(header["TocOffset"])
        content_offset = int(header["ContentOffset"])
        toc_rows = read_cpk_packet(source, toc_offset, b"TOC ")
        rows_by_name = {str(row["FileName"]): row for row in toc_rows}
        data_base = min(toc_offset, content_offset)

        for name, expected_size in LOCALE_CPK_SIZES.items():
            if name not in rows_by_name:
                raise RuntimeError(f"patch OBB is missing {name}")
            row = rows_by_name[name]
            packed_size = int(row["FileSize"])
            extracted_size = int(row["ExtractSize"])
            if packed_size != expected_size or extracted_size != expected_size:
                raise RuntimeError(
                    f"unsupported compressed or wrong-size CPK member {name}: "
                    f"packed={packed_size}, extracted={extracted_size}"
                )
            absolute_offset = data_base + int(row["FileOffset"])
            if absolute_offset < 0 or absolute_offset + packed_size > patch_obb.stat().st_size:
                raise RuntimeError(f"CPK member is outside the patch OBB: {name}")
            source.seek(absolute_offset)
            destination = output / "Download" / name
            copy_stream(source, destination, packed_size)
            with destination.open("rb") as extracted:
                if extracted.read(4) != b"CPK ":
                    raise RuntimeError(f"extracted locale has an invalid signature: {name}")


def expected_runtime_sizes(nro_size: int) -> dict[str, int]:
    expected = {"pes21_nx.nro": nro_size, **CORE_RUNTIME_SIZES}
    expected.update({f"Download/{name}": size for name, size in LOCALE_CPK_SIZES.items()})
    expected.update(
        {f"assets/responses/{name}": size for name, size in EXPECTED_PAYLOAD_SIZES.items()}
    )
    return expected


def validate_runtime(output: Path, nro_size: int) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    for relative, expected_size in expected_runtime_sizes(nro_size).items():
        path = output / Path(relative)
        if not path.is_file():
            raise RuntimeError(f"prepared runtime is missing {relative}")
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise RuntimeError(
                f"prepared runtime size mismatch for {relative}: "
                f"expected {expected_size}, found {actual_size}"
            )
        report[relative] = {"size": actual_size, "sha256": sha256_file(path)}
    return report


def resolve_nro(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    candidates = [
        Path(sys.executable).resolve().with_name("pes21_nx.nro"),
        Path(__file__).resolve().parents[1] / "pes21_nx.nro",
        Path.cwd() / "pes21_nx.nro",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "pes21_nx.nro was not found beside the preparer; pass --nro explicitly"
    )


def prepare_runtime(
    apk: Path, main_obb: Path, patch_obb: Path, nro: Path, output: Path
) -> None:
    apk = apk.resolve()
    main_obb = main_obb.resolve()
    patch_obb = patch_obb.resolve()
    nro = nro.resolve()
    output = output.resolve()
    if output.exists():
        raise RuntimeError(
            f"output already exists: {output}. Move or remove that folder before "
            "preparing again; it is never overwritten so SaveData stays protected."
        )
    if not nro.is_file() or nro.stat().st_size <= 0:
        raise RuntimeError(f"NRO not found or empty: {nro}")

    print("Validating the three game inputs...")
    input_hashes = {
        "apk": validate_input(apk, "APK", TARGET_APK),
        "main_obb": validate_input(main_obb, "main OBB", TARGET_MAIN_OBB),
        "patch_obb": validate_input(patch_obb, "patch OBB", TARGET_PATCH_OBB),
        "nro": sha256_file(nro),
    }

    staging = output.parent / f".{output.name}.staging-{uuid.uuid4().hex}"
    if staging.exists():
        raise RuntimeError(f"staging directory already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        print("Extracting native libraries from the APK...")
        with zipfile.ZipFile(apk) as archive:
            for member, destination in APK_LIBRARIES.items():
                extract_zip_member(archive, member, staging / destination)

        print("Extracting the main PAK from the main OBB...")
        with zipfile.ZipFile(main_obb) as archive:
            extract_zip_member(archive, MAIN_PAK_PATH, staging / MAIN_PAK_PATH)

        print("Copying the patch OBB...")
        shutil.copyfile(patch_obb, staging / PATCH_OBB_NAME)

        print("Extracting the ten locale CPK files...")
        extract_locale_cpks(patch_obb, staging)

        print("Generating the 48 offline responses...")
        responses = load_apk_responses(apk)
        apply_compatibility_overrides(responses)
        write_responses(responses, staging / "assets" / "responses", keep_json=False)

        print("Embedding the APK application icon into the NRO...")
        prepared_nro = staging / "pes21_nx.nro"
        nro_icon = inject_apk_icon_into_nro(apk, nro, prepared_nro)
        (staging / "SaveData").mkdir()

        print("Hashing and validating the completed runtime...")
        files = validate_runtime(staging, prepared_nro.stat().st_size)
        report = {
            "target": {
                "package": "jp.nyan2021.pesam",
                "version_code": 305030001,
                "game_version": "5.3.0",
            },
            "inputs": input_hashes,
            "nro_icon": nro_icon,
            "files": files,
            "result": "validated",
        }
        (staging / "install-report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging, output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"Runtime ready: {output}")


def interactive_input_directory() -> Path:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError as error:
        raise RuntimeError("interactive mode requires tkinter") from error

    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "PES 2021 NX Preparer",
        "Select one folder containing PES21.apk, the main OBB, the patch OBB, "
        "and the release NRO. A ready-to-copy switch/pes21_nx folder will be "
        "created inside it.",
    )
    selected = filedialog.askdirectory(
        title="Select the folder containing the four input files"
    )
    if not selected:
        raise RuntimeError("preparation canceled")
    root.destroy()
    return Path(selected)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build switch/pes21_nx from one folder containing a compatible APK, "
            "two OBB files, and the release NRO"
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="folder containing the APK, both OBBs, and one release NRO",
    )
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--main-obb", type=Path)
    parser.add_argument("--patch-obb", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--nro", type=Path)
    args = parser.parse_args()

    explicit_inputs = (args.apk, args.main_obb, args.patch_obb)
    interactive_mode = False
    try:
        if args.input_dir is not None:
            if (
                any(value is not None for value in explicit_inputs)
                or args.nro is not None
            ):
                parser.error("--input-dir cannot be combined with explicit APK/OBB/NRO paths")
            input_dir = args.input_dir.resolve()
            apk, main_obb, patch_obb, nro = discover_inputs(input_dir)
            output = args.output or input_dir / "switch" / "pes21_nx"
        elif (
            all(value is None for value in explicit_inputs)
            and args.output is None
            and args.nro is None
        ):
            interactive_mode = True
            input_dir = interactive_input_directory().resolve()
            apk, main_obb, patch_obb, nro = discover_inputs(input_dir)
            output = input_dir / "switch" / "pes21_nx"
        elif any(value is None for value in explicit_inputs) or args.output is None:
            parser.error("explicit mode requires --apk, --main-obb, --patch-obb, and --output")
        else:
            apk, main_obb, patch_obb = explicit_inputs  # type: ignore[misc]
            nro = resolve_nro(args.nro)
            output = args.output
        prepare_runtime(apk, main_obb, patch_obb, nro, output)
        if interactive_mode:
            from tkinter import messagebox

            messagebox.showinfo("PES 2021 NX Preparer", f"Runtime ready:\n{output}")
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if interactive_mode:
            try:
                from tkinter import messagebox

                messagebox.showerror("PES 2021 NX Preparer", str(error))
            except Exception:
                pass
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
