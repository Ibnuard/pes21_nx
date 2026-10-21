"""Bounded RGBA region reader for owned legacy-compressed FL26 UI atlases.

The PC texture envelope can be shorter than its referenced payload span. Read
references against the complete supplied member, never decode the whole atlas,
and retain only a caller-bounded rectangle. This is a local format-aware parser,
not REA provider output or evidence of native playback.
"""
from __future__ import annotations

import struct

from PIL import Image

MAX_DECODED = 64 * 1024 * 1024
MAX_CROP_BYTES = 2 * 1024 * 1024


def read_regions(container: bytes) -> list[dict]:
    base = container.index(b"TXP2")
    txp = memoryview(container)[base:]
    count, table, mapping = struct.unpack_from(">III", txp, 36)
    named = struct.unpack_from(">I", txp, mapping + 16)[0]
    names_table = struct.unpack_from(">I", txp, mapping + 24)[0]
    if count != named or not 0 < count <= 4096:
        raise ValueError("unsupported region mapping")
    result = [None] * count
    for i in range(count):
        _, index, name_offset = struct.unpack_from(">III", txp, names_table + i * 12)
        if index >= count or result[index] is not None:
            raise ValueError("ambiguous region mapping")
        end = container.index(b"\0", base + name_offset)
        name = container[base + name_offset:end]
        if name and name[0] >= 0xa0:
            name = bytes((c + 128) & 255 for c in name)
        result[index] = {"name": name.decode("ascii"), "index": index,
                         "rect": struct.unpack_from(">5H", txp, table + index * 10)}
    return result


def decode_ranges(data: bytes, expected: int, ranges: list[tuple[int, int]]) -> bytes:
    """Retain sorted disjoint byte ranges using only the 4 KiB LZSS window."""
    if not 0 < expected <= MAX_DECODED or not ranges:
        raise ValueError("invalid sparse decode bound")
    previous = 0
    for start, end in ranges:
        if start < previous or end <= start or end > expected:
            raise ValueError("invalid sparse decode range")
        previous = end
    if sum(end - start for start, end in ranges) > MAX_CROP_BYTES:
        raise ValueError("crop exceeds retained pixel budget")
    window = bytearray(4096)
    output = bytearray()
    head, cursor, position, selected = 4078, 0, 0, 0
    limit = ranges[-1][1]
    while position < limit:
        if cursor >= len(data):
            raise ValueError("truncated LZSS control")
        control = data[cursor]
        cursor += 1
        for bit in range(8):
            if position >= limit:
                break
            literal = bool(control & (1 << bit))
            if literal:
                if cursor >= len(data):
                    raise ValueError("truncated LZSS literal")
                source, length = cursor, 1
                cursor += 1
            else:
                if cursor + 2 > len(data):
                    raise ValueError("truncated LZSS match")
                source = data[cursor] | ((data[cursor + 1] & 0xf0) << 4)
                length = (data[cursor + 1] & 15) + 3
                cursor += 2
            for _ in range(min(length, limit - position)):
                value = data[source] if literal else window[source]
                source = (source + 1) & 4095
                window[head] = value
                head = (head + 1) & 4095
                if position >= ranges[selected][1]:
                    selected += 1
                if position >= ranges[selected][0]:
                    output.append(value)
                position += 1
    return bytes(output)


def crop_rgba(container: bytes, texture: int, rect: tuple[int, int, int, int]):
    """Read a selected texture rectangle without allocating its full pixels."""
    base = container.index(b"TXP2")
    txp = memoryview(container)[base:]
    flags, count, table = struct.unpack_from(">III", txp, 20)
    if not flags & 4 or not 0 <= texture < count <= 64:
        raise ValueError("expected legacy-compressed texture")
    _, length, offset = struct.unpack_from(">III", txp, table + texture * 12)
    if length < 8 or offset + length > len(txp):
        raise ValueError("texture reference outside complete member")
    expanded, packed = struct.unpack_from(">II", txp, offset)
    if packed != length - 8:
        raise ValueError("compressed texture size mismatch")
    stream = txp[offset + 8:offset + length]
    header = decode_ranges(stream, expanded, [(0, 64)])
    if header[:4] != b"TXDT" or header[20:24] != bytes.fromhex("11221015"):
        raise ValueError("only verified ARGB32 texture crops are supported")
    width, height = struct.unpack_from(">HH", header, 16)
    if expanded != 64 + width * height * 4:
        raise ValueError("ARGB32 texture dimensions do not match expanded bytes")
    left, top, right, bottom = rect
    if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
        raise ValueError("crop outside atlas")
    ranges = [(64 + (y * width + left) * 4, 64 + (y * width + right) * 4)
              for y in range(top, bottom)]
    pixels = decode_ranges(stream, expanded, ranges)
    return Image.frombytes("RGBA", (right - left, bottom - top), pixels,
                           "raw", "ARGB"), {
        "source_atlas": [width, height], "source_decoded_bytes": expanded,
        "crop": list(rect), "retained_pixel_bytes": len(pixels),
        "decoder_window_bytes": 4096, "full_atlas_allocated": False,
    }
