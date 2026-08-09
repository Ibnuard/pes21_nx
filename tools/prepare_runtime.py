#!/usr/bin/env python3
"""Prepare a validated PES 2021 NX runtime from three user-owned inputs."""

from __future__ import annotations

import argparse
import hashlib
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
BUFFER_SIZE = 8 * 1024 * 1024


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
            f"output already exists: {output}. Select a new destination to protect SaveData."
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

        shutil.copyfile(nro, staging / "pes21_nx.nro")
        (staging / "SaveData").mkdir()

        print("Hashing and validating the completed runtime...")
        files = validate_runtime(staging, nro.stat().st_size)
        report = {
            "target": {
                "package": "jp.nyan2021.pesam",
                "version_code": 305030001,
                "game_version": "5.3.0",
            },
            "inputs": input_hashes,
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


def interactive_arguments() -> tuple[Path, Path, Path, Path]:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except ImportError as error:
        raise RuntimeError("interactive mode requires tkinter") from error

    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo(
        "PES 2021 NX Preparer",
        "Select the compatible PES21.apk, main OBB, patch OBB, then an output parent folder.",
    )

    def select_file(title: str, patterns: list[tuple[str, str]]) -> Path:
        selected = filedialog.askopenfilename(title=title, filetypes=patterns)
        if not selected:
            raise RuntimeError("preparation canceled")
        return Path(selected)

    apk = select_file("Select PES21.apk", [("Android APK", "*.apk")])
    main_obb = select_file("Select main OBB", [("Android OBB", "*.obb"), ("All", "*")])
    patch_obb = select_file("Select patch OBB", [("Android OBB", "*.obb"), ("All", "*")])
    parent = filedialog.askdirectory(title="Select the output parent folder")
    if not parent:
        raise RuntimeError("preparation canceled")
    root.destroy()
    return apk, main_obb, patch_obb, Path(parent) / "pes21_nx"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build switch/pes21_nx from a compatible APK and two OBB files"
    )
    parser.add_argument("--apk", type=Path)
    parser.add_argument("--main-obb", type=Path)
    parser.add_argument("--patch-obb", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--nro", type=Path)
    args = parser.parse_args()

    provided = (args.apk, args.main_obb, args.patch_obb, args.output)
    try:
        if all(value is None for value in provided):
            apk, main_obb, patch_obb, output = interactive_arguments()
        elif any(value is None for value in provided):
            parser.error("--apk, --main-obb, --patch-obb, and --output are required together")
        else:
            apk, main_obb, patch_obb, output = provided  # type: ignore[misc]
        prepare_runtime(apk, main_obb, patch_obb, resolve_nro(args.nro), output)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        if all(value is None for value in provided):
            try:
                from tkinter import messagebox

                messagebox.showerror("PES 2021 NX Preparer", str(error))
            except Exception:
                pass
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
