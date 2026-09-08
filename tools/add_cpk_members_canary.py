#!/usr/bin/env python3
"""Add detached members to an uncompressed CRI CPK canary.

The release repacker intentionally only replaces existing members.  This
small companion handles the one experiment that needs new Uniform16 names
while preserving the original CPK header/TOC schema and all old payloads.
It is not used by the runtime build and never writes its input archive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from prepare_runtime import decrypt_utf, read_cpk_packet


PACKET_HEADER = struct.Struct("<4s4xQ")
TOC_ROW_LENGTH = 28
TOC_ROWS_RELATIVE = 63
TOC_COLUMNS = 7
TOC_FIELD_OFFSETS = {
    "DirName": 0,
    "FileName": 4,
    "FileSize": 8,
    "ExtractSize": 12,
    "FileOffset": 16,
    "ID": 24,
}


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) // boundary * boundary


def member_name(row: dict[str, Any]) -> str:
    return "/".join(
        str(part)
        for part in (row.get("DirName") or "", row.get("FileName") or "")
        if part and part != "<NULL>"
    ).replace("\\", "/")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def packet_payload(source, offset: int, signature: bytes) -> tuple[bytes, bytes, bool]:
    source.seek(offset)
    header = source.read(16)
    if len(header) != 16 or header[:4] != signature:
        raise ValueError(f"invalid {signature!r} packet at {offset}")
    size = struct.unpack_from("<Q", header, 8)[0]
    payload = source.read(size)
    if len(payload) != size:
        raise ValueError("truncated CPK packet")
    encrypted = payload[:4] != b"@UTF"
    return header, decrypt_utf(payload) if encrypted else payload, encrypted


def utf_layout(packet: bytes) -> dict[str, int]:
    if packet[:4] != b"@UTF":
        raise ValueError("expected decoded CRI UTF packet")
    u16 = lambda offset: struct.unpack_from(">H", packet, offset)[0]
    u32 = lambda offset: struct.unpack_from(">I", packet, offset)[0]
    return {
        "table_size": u32(4),
        "rows": 8 + u32(8),
        "strings": 8 + u32(12),
        "data": 8 + u32(16),
        "columns": u16(24),
        "row_length": u16(26),
        "row_count": u32(28),
    }


def string_at(packet: bytes, strings_offset: int, relative: int) -> str:
    start = strings_offset + relative
    end = packet.find(b"\0", start)
    if start < strings_offset or end < 0:
        raise ValueError("invalid CRI UTF string offset")
    return packet[start:end].decode("utf-8")


def parse_toc_rows(packet: bytes) -> list[dict[str, Any]]:
    layout = utf_layout(packet)
    if (
        layout["columns"] != TOC_COLUMNS
        or layout["row_length"] != TOC_ROW_LENGTH
        or layout["rows"] != TOC_ROWS_RELATIVE + 8
    ):
        raise ValueError("unsupported CPK TOC schema")
    rows: list[dict[str, Any]] = []
    for index in range(layout["row_count"]):
        offset = layout["rows"] + index * TOC_ROW_LENGTH
        row = packet[offset : offset + TOC_ROW_LENGTH]
        if len(row) != TOC_ROW_LENGTH:
            raise ValueError("truncated CPK TOC row")
        dirname_rel, filename_rel = struct.unpack_from(">II", row, 0)
        rows.append(
            {
                "DirName": string_at(packet, layout["strings"], dirname_rel),
                "FileName": string_at(packet, layout["strings"], filename_rel),
                "FileSize": struct.unpack_from(">I", row, 8)[0],
                "ExtractSize": struct.unpack_from(">I", row, 12)[0],
                "FileOffset": struct.unpack_from(">Q", row, 16)[0],
                "ID": struct.unpack_from(">I", row, 24)[0],
                "_raw": row,
            }
        )
    return rows


def _append_string(strings: bytearray, offsets: dict[str, int], value: str) -> int:
    if value in offsets:
        return offsets[value]
    offset = len(strings)
    strings.extend(value.encode("utf-8"))
    strings.append(0)
    offsets[value] = offset
    return offset


def build_toc_packet(
    original: bytes,
    rows: list[dict[str, Any]],
    additions: list[dict[str, Any]],
) -> bytes:
    layout = utf_layout(original)
    strings = bytearray(original[layout["strings"] : layout["data"]])
    offsets: dict[str, int] = {}
    cursor = 0
    while cursor < len(strings):
        end = strings.find(b"\0", cursor)
        if end < 0:
            raise ValueError("unterminated CPK TOC string table")
        offsets.setdefault(strings[cursor:end].decode("utf-8"), cursor)
        cursor = end + 1

    # Detached intermediate layout only. Global sorting regressed hardware
    # behavior in the kit experiment. For the hardware-confirmed Madrid path,
    # build_madrid_preserve_order restores original row order and Sorted=0.
    # Do not infer native lookup compatibility from Python binary search alone.
    all_rows = sorted(rows + additions, key=lambda row: member_name(row).lower())
    row_bytes: list[bytes] = []
    for row in all_rows:
        raw = bytearray(row.get("_raw", bytes(TOC_ROW_LENGTH)))
        if len(raw) != TOC_ROW_LENGTH:
            raise ValueError("invalid TOC row size")
        struct.pack_into(
            ">II",
            raw,
            0,
            _append_string(strings, offsets, str(row["DirName"])),
            _append_string(strings, offsets, str(row["FileName"])),
        )
        struct.pack_into(">IIQ", raw, 8, int(row["FileSize"]), int(row["ExtractSize"]), int(row["FileOffset"]))
        struct.pack_into(">I", raw, 24, int(row["ID"]))
        row_bytes.append(bytes(raw))

    rows_relative = layout["rows"] - 8
    strings_relative = rows_relative + TOC_ROW_LENGTH * len(row_bytes)
    data_relative = strings_relative + len(strings)
    header = bytearray(original[: layout["rows"]])
    struct.pack_into(">I", header, 4, data_relative)
    struct.pack_into(">I", header, 12, strings_relative)
    struct.pack_into(">I", header, 16, data_relative)
    struct.pack_into(">I", header, 28, len(row_bytes))
    return bytes(header) + b"".join(row_bytes) + bytes(strings)


def read_member(source, base: int, row: dict[str, Any]) -> bytes:
    size = int(row["FileSize"])
    if size != int(row["ExtractSize"]):
        raise ValueError(f"compressed source member is unsupported: {member_name(row)}")
    source.seek(base + int(row["FileOffset"]))
    payload = source.read(size)
    if len(payload) != size:
        raise ValueError(f"truncated source member: {member_name(row)}")
    return payload


def rebuild(source_path: Path, output_path: Path, additions: dict[str, Path]) -> dict[str, Any]:
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path == output_path:
        raise ValueError("source and output must differ")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if output_path.exists():
        raise FileExistsError(output_path)

    with source_path.open("rb") as source:
        cpk_header_rows = read_cpk_packet(source, 0, b"CPK ")
        cpk_header = cpk_header_rows[0]
        toc_offset = int(cpk_header["TocOffset"])
        content_offset = int(cpk_header["ContentOffset"])
        alignment = int(cpk_header["Align"])
        data_base = min(toc_offset, content_offset)
        _toc_header, toc_packet, toc_encrypted = packet_payload(source, toc_offset, b"TOC ")
        rows = parse_toc_rows(toc_packet)
        existing = {member_name(row) for row in rows}
        overlap = existing.intersection(additions)
        if overlap:
            raise ValueError(f"members already exist; use replacement repacker: {sorted(overlap)}")
        if not additions:
            raise ValueError("at least one new member is required")

        additions_payload = []
        for name, path in sorted(additions.items()):
            if not path.is_file():
                raise FileNotFoundError(path)
            payload = path.read_bytes()
            additions_payload.append({"name": name, "path": path, "payload": payload})

        ordered = sorted(enumerate(rows), key=lambda item: int(item[1]["FileOffset"]))
        new_content_offset_guess = align(
            toc_offset + 16 + len(toc_packet) + 16 * len(additions_payload) + 256 * len(additions_payload),
            alignment,
        )
        cursor = new_content_offset_guess
        rebuilt_rows = [dict(row) for row in rows]
        payloads: list[tuple[int, bytes]] = []
        for row_index, row in ordered:
            cursor = align(cursor, alignment)
            payload = read_member(source, data_base, row)
            updated = rebuilt_rows[row_index]
            updated["FileOffset"] = cursor - data_base
            updated["FileSize"] = len(payload)
            updated["ExtractSize"] = len(payload)
            payloads.append((cursor, payload))
            cursor += len(payload)

        next_id = max(int(row["ID"]) for row in rows) + 1
        addition_rows: list[dict[str, Any]] = []
        for item in additions_payload:
            cursor = align(cursor, alignment)
            path = item["name"].replace("\\", "/").strip("/")
            dirname, filename = path.rsplit("/", 1) if "/" in path else ("", path)
            payload = item["payload"]
            addition_rows.append(
                {
                    "DirName": dirname,
                    "FileName": filename,
                    "FileSize": len(payload),
                    "ExtractSize": len(payload),
                    "FileOffset": cursor - data_base,
                    "ID": next_id,
                    "_raw": bytes(TOC_ROW_LENGTH),
                }
            )
            payloads.append((cursor, payload))
            cursor += len(payload)
            next_id += 1

        final_size = align(cursor, alignment)
        new_toc = build_toc_packet(toc_packet, rebuilt_rows, addition_rows)
        new_content_offset = align(toc_offset + 16 + len(new_toc), alignment)
        if new_content_offset != new_content_offset_guess:
            # Recompute offsets once the exact TOC size is known.
            shift = new_content_offset - new_content_offset_guess
            for row in rebuilt_rows:
                row["FileOffset"] = int(row["FileOffset"]) + shift
            for row in addition_rows:
                row["FileOffset"] = int(row["FileOffset"]) + shift
            payloads = [(offset + shift, payload) for offset, payload in payloads]
            final_size += shift
            new_toc = build_toc_packet(toc_packet, rebuilt_rows, addition_rows)

        header_updates = {
            "TocSize": 16 + len(new_toc),
            "ContentOffset": new_content_offset,
            "ContentSize": final_size - new_content_offset,
            "Files": len(rebuilt_rows) + len(addition_rows),
            "EnabledPackedSize": int(cpk_header.get("EnabledPackedSize", 0))
            + sum(len(item["payload"]) for item in additions_payload),
            "EnabledDataSize": int(cpk_header.get("EnabledDataSize", 0))
            + sum(len(item["payload"]) for item in additions_payload),
        }
        with source_path.open("rb") as source_raw:
            source_raw.seek(0)
            source_header = source_raw.read(16)
            header_size = struct.unpack_from("<Q", source_header, 8)[0]
            source_header_payload = source_raw.read(header_size)
            prefix = bytearray(source_raw.read(toc_offset - 16 - header_size))
        if len(prefix) != toc_offset - 16 - header_size:
            raise ValueError("truncated CPK prefix")
        from repack_cpk_members import patch_utf_rows

        patched_header = patch_utf_rows(source_header_payload, [header_updates])
        header_packet = source_header[:16] + patched_header
        encoded_toc = decrypt_utf(new_toc) if toc_encrypted else new_toc
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as output:
            output.write(header_packet)
            output.write(prefix)
            output.write(b"TOC ")
            output.write(b"\0\0\0\0")
            output.write(struct.pack("<Q", len(encoded_toc)))
            output.write(encoded_toc)
            if output.tell() < new_content_offset:
                output.write(b"\0" * (new_content_offset - output.tell()))
            for offset, payload in sorted(payloads, key=lambda item: item[0]):
                if output.tell() < offset:
                    output.write(b"\0" * (offset - output.tell()))
                if output.tell() != offset:
                    raise RuntimeError("content offset ordering failure")
                output.write(payload)
            if output.tell() < final_size:
                output.write(b"\0" * (final_size - output.tell()))

    # Parse the result to catch malformed TOC/header data before reporting it.
    with output_path.open("rb") as check:
        rebuilt_header = read_cpk_packet(check, 0, b"CPK ")[0]
        rebuilt_rows = read_cpk_packet(check, int(rebuilt_header["TocOffset"]), b"TOC ")
    rebuilt_names = {member_name(row) for row in rebuilt_rows}
    missing = set(additions) - rebuilt_names
    if missing:
        raise RuntimeError(f"new members missing after rebuild: {sorted(missing)}")
    return {
        "source": str(source_path),
        "output": str(output_path),
        "source_sha256": sha256_file(source_path),
        "output_sha256": sha256_file(output_path),
        "source_members": len(rows),
        "output_members": len(rebuilt_rows),
        "added_members": sorted(additions),
        "size": output_path.stat().st_size,
    }


def parse_additions(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"addition must be MEMBER=FILE: {value}")
        member, raw_path = value.split("=", 1)
        member = member.replace("\\", "/").strip("/")
        if not member or member in result:
            raise ValueError(f"duplicate/empty member: {member}")
        result[member] = Path(raw_path).resolve()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--add", action="append", default=[], metavar="MEMBER=FILE")
    args = parser.parse_args()
    report = rebuild(args.source, args.output, parse_additions(args.add))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
