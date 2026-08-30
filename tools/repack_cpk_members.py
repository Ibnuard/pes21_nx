#!/usr/bin/env python3
"""Replace uncompressed members in a CRI CPK while preserving its schema.

This is intentionally narrow: it keeps the original CPK/TOC packets, row
order, and all metadata columns, then rebuilds the aligned content area. Only
FileOffset, FileSize, and ExtractSize are changed for TOC rows. Replacement
members must be stored (FileSize == ExtractSize), as used by the PES database
WESYS tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from prepare_runtime import decrypt_utf, read_cpk_packet


NUMERIC_FORMATS = {
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


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) // boundary * boundary


def utf_value_width(value_type: int) -> int:
    if value_type in NUMERIC_FORMATS:
        return struct.calcsize(NUMERIC_FORMATS[value_type])
    if value_type == 10:
        return 4
    if value_type == 11:
        return 8
    raise RuntimeError(f"unsupported CRI UTF value type {value_type}")


def patch_utf_rows(packet: bytes, updates: list[dict[str, int]]) -> bytes:
    encrypted = packet[:4] != b"@UTF"
    table = bytearray(decrypt_utf(packet) if encrypted else packet)
    if table[:4] != b"@UTF":
        raise RuntimeError("invalid UTF packet")

    def u16(offset: int) -> int:
        return struct.unpack_from(">H", table, offset)[0]

    def u32(offset: int) -> int:
        return struct.unpack_from(">I", table, offset)[0]

    rows_offset = 8 + u32(8)
    strings_offset = 8 + u32(12)
    column_count = u16(24)
    row_length = u16(26)
    row_count = u32(28)
    if row_count != len(updates):
        raise RuntimeError(
            f"UTF update count mismatch: table={row_count}, updates={len(updates)}"
        )

    def string_at(relative: int) -> str:
        start = strings_offset + relative
        end = table.find(b"\0", start)
        if start < strings_offset or end < 0:
            raise RuntimeError("invalid UTF string")
        return bytes(table[start:end]).decode("utf-8")

    descriptors: list[tuple[str, int, int, int | None]] = []
    descriptor_offset = 32
    row_field_offset = 0
    for _ in range(column_count):
        flag = table[descriptor_offset]
        name = string_at(u32(descriptor_offset + 1))
        descriptor_offset += 5
        storage = flag & 0xF0
        value_type = flag & 0x0F
        width = utf_value_width(value_type)
        field_offset: int | None = None
        if storage == 0x30:
            field_offset = descriptor_offset
            descriptor_offset += width
        elif storage == 0x50:
            field_offset = row_field_offset
            row_field_offset += width
        elif storage != 0x10:
            raise RuntimeError(f"unsupported UTF storage {storage:#x}")
        descriptors.append((name, storage, value_type, field_offset))

    if row_field_offset != row_length:
        raise RuntimeError(
            f"UTF row layout mismatch: parsed={row_field_offset}, declared={row_length}"
        )

    for row_index, values in enumerate(updates):
        for name, value in values.items():
            descriptor = next((item for item in descriptors if item[0] == name), None)
            if descriptor is None:
                raise RuntimeError(f"UTF field not found: {name}")
            _name, storage, value_type, field_offset = descriptor
            if value_type not in NUMERIC_FORMATS or field_offset is None:
                raise RuntimeError(f"UTF field is not writable numeric data: {name}")
            if storage == 0x30:
                if row_index != 0:
                    continue
                offset = field_offset
            elif storage == 0x50:
                offset = rows_offset + row_index * row_length + field_offset
            else:
                raise RuntimeError(f"UTF field is fixed zero: {name}")
            struct.pack_into(NUMERIC_FORMATS[value_type], table, offset, value)

    result = bytes(table)
    return decrypt_utf(result) if encrypted else result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_replacements(values: list[str]) -> dict[str, Path]:
    replacements: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"replacement must be MEMBER=FILE: {value}")
        member, filename = value.split("=", 1)
        member = member.replace("\\", "/").strip("/")
        path = Path(filename).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        replacements[member] = path
    return replacements


def parse_replacement_manifest(path: Path | None) -> dict[str, Path]:
    if path is None:
        return {}
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("replacement manifest must be a JSON object")
    replacements: dict[str, Path] = {}
    for raw_member, raw_filename in payload.items():
        if not isinstance(raw_member, str) or not isinstance(raw_filename, str):
            raise ValueError("replacement manifest entries must map strings to strings")
        member = raw_member.replace("\\", "/").strip("/")
        filename = Path(raw_filename)
        if not filename.is_absolute():
            filename = resolved.parent / filename
        filename = filename.resolve()
        if not filename.is_file():
            raise FileNotFoundError(filename)
        replacements[member] = filename
    return replacements


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="MEMBER=FILE",
    )
    parser.add_argument(
        "--replace-manifest",
        type=Path,
        help="JSON object mapping CPK member paths to replacement files",
    )
    parser.add_argument(
        "--expect-members",
        type=int,
        help="refuse a source CPK whose TOC row count differs",
    )
    args = parser.parse_args()
    source_path = args.source.resolve()
    output_path = args.output.resolve()
    replacements = parse_replacement_manifest(args.replace_manifest)
    command_line_replacements = parse_replacements(args.replace)
    overlap = set(replacements) & set(command_line_replacements)
    if overlap:
        raise RuntimeError(f"duplicate replacements: {sorted(overlap)}")
    replacements.update(command_line_replacements)
    if source_path == output_path:
        raise RuntimeError("source and output must differ")

    with source_path.open("rb") as source:
        header = read_cpk_packet(source, 0, b"CPK ")[0]
        toc_offset = int(header["TocOffset"])
        content_offset = int(header["ContentOffset"])
        alignment = int(header["Align"])
        rows = read_cpk_packet(source, toc_offset, b"TOC ")
        if args.expect_members is not None and len(rows) != args.expect_members:
            raise RuntimeError(
                "CPK member count mismatch: "
                f"expected {args.expect_members}, found {len(rows)} in {source_path}"
            )
        data_base = min(toc_offset, content_offset)

        indexed_rows = list(enumerate(rows))
        indexed_rows.sort(key=lambda item: int(item[1]["FileOffset"]))
        updates: list[dict[str, int]] = [{} for _ in rows]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w+b") as output:
            source.seek(0)
            prefix = source.read(content_offset)
            if len(prefix) != content_offset:
                raise RuntimeError("truncated CPK prefix")
            output.write(prefix)

            consumed: set[str] = set()
            for row_index, row in indexed_rows:
                cursor = align(output.tell(), alignment)
                if cursor > output.tell():
                    output.write(b"\0" * (cursor - output.tell()))
                member = "/".join(
                    part
                    for part in (str(row.get("DirName") or ""), str(row["FileName"]))
                    if part and part != "<NULL>"
                )
                replacement = replacements.get(member)
                if replacement is not None:
                    if int(row["FileSize"]) != int(row["ExtractSize"]):
                        raise RuntimeError(f"compressed replacement is unsupported: {member}")
                    payload = replacement.read_bytes()
                    consumed.add(member)
                    file_size = len(payload)
                    extract_size = len(payload)
                else:
                    old_offset = data_base + int(row["FileOffset"])
                    file_size = int(row["FileSize"])
                    extract_size = int(row["ExtractSize"])
                    source.seek(old_offset)
                    payload = source.read(file_size)
                    if len(payload) != file_size:
                        raise RuntimeError(f"truncated CPK member: {member}")
                output.write(payload)
                updates[row_index] = {
                    "FileOffset": cursor - data_base,
                    "FileSize": file_size,
                    "ExtractSize": extract_size,
                }

            final_size = align(output.tell(), alignment)
            if final_size > output.tell():
                output.write(b"\0" * (final_size - output.tell()))

            missing = set(replacements) - consumed
            if missing:
                raise RuntimeError(f"CPK members not found: {sorted(missing)}")

            source.seek(toc_offset)
            packet_header = source.read(16)
            packet_size = struct.unpack_from("<Q", packet_header, 8)[0]
            packet = source.read(packet_size)
            patched_packet = patch_utf_rows(packet, updates)
            if len(patched_packet) != packet_size:
                raise RuntimeError("TOC packet size changed")
            output.seek(toc_offset)
            output.write(packet_header)
            output.write(patched_packet)

    with output_path.open("rb") as rebuilt:
        rebuilt_header = read_cpk_packet(rebuilt, 0, b"CPK ")[0]
        rebuilt_rows = read_cpk_packet(
            rebuilt, int(rebuilt_header["TocOffset"]), b"TOC "
        )
        rebuilt_base = min(
            int(rebuilt_header["TocOffset"]), int(rebuilt_header["ContentOffset"])
        )
        rebuilt_by_member = {
            "/".join(
                part
                for part in (str(row.get("DirName") or ""), str(row["FileName"]))
                if part and part != "<NULL>"
            ): row
            for row in rebuilt_rows
        }
        for member, replacement in replacements.items():
            row = rebuilt_by_member[member]
            rebuilt.seek(rebuilt_base + int(row["FileOffset"]))
            payload = rebuilt.read(int(row["FileSize"]))
            if hashlib.sha256(payload).hexdigest() != sha256(replacement):
                raise RuntimeError(f"replacement verification failed: {member}")

    print(f"rebuilt {output_path}")
    print(f"members: {len(rows)}")
    print(f"size: {output_path.stat().st_size}")
    print(f"sha256: {sha256(output_path)}")
    replacement_names = sorted(replacements)
    if len(replacement_names) <= 50:
        for member in replacement_names:
            print(f"replaced: {member}")
    else:
        for member in replacement_names[:20]:
            print(f"replaced: {member}")
        print(f"replaced: ... {len(replacement_names) - 20} more members")


if __name__ == "__main__":
    main()
