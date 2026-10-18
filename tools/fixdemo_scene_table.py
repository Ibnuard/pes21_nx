#!/usr/bin/env python3
"""Strict offline reader/writer for locally supplied FixDemo scene tables.

This describes the Mobile v5.3.0 SceneCutTableDataBody loader's typed-stream
format. It is not a cutscene player and does not establish asset compatibility.
Only entrance/end/result/mode tables are admitted; the goal table has a separate
goal-specific extension. No proprietary table or extracted data is distributed.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import struct
from pathlib import Path

SUPPORTED_KINDS = (1, 7, 8, 9)
MAX_TABLE_BYTES = 16 * 1024 * 1024
_FORMATS = ("f", "I", "I", "I", "H", "B", "B")
_WIDTHS = (4, 4, 4, 4, 2, 1, 1)


class TableError(ValueError):
    """Malformed, unsupported, or incomplete local scene table."""


def _check_kind(kind: int) -> None:
    if kind not in SUPPORTED_KINDS:
        raise TableError("only entrance(1), ending(7), result(8), mode(9) are supported")


class _Reader:
    def __init__(self, data: bytes):
        if not 56 <= len(data) <= MAX_TABLE_BYTES:
            raise TableError("invalid typed-stream table size")
        header = struct.unpack_from("<14I", data)
        self.counts, offsets = header[:7], header[7:]
        if self.counts[2] != 1:
            raise TableError("expected one scene-table block")
        spans = []
        self.streams = []
        for count, offset, width, fmt in zip(self.counts, offsets, _WIDTHS, _FORMATS):
            end = offset + count * width
            if offset < 56 or end > len(data):
                raise TableError("typed stream exceeds file bounds")
            if count:
                spans.append((offset, end))
            self.streams.append(struct.unpack_from(f"<{count}{fmt}", data, offset))
        spans.sort()
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            raise TableError("overlapping typed streams")
        string_ends = self.streams[1]
        if any(a > b for a, b in zip((0,) + string_ends, string_ends)):
            raise TableError("non-monotonic string endpoints")
        if (string_ends[-1] if string_ends else 0) != self.counts[6]:
            raise TableError("string endpoints do not cover the string pool")
        self.string_bytes = data[offsets[6]:offsets[6] + self.counts[6]]
        self.positions = [0] * 7
        self.read_count = 0
        self.block_end = self.streams[2][0]
        expected = sum(self.counts[i] for i in (0, 1, 3, 4, 5))
        if self.block_end != expected:
            raise TableError("block read count does not match typed streams")

    def take(self, stream: int):
        pos = self.positions[stream]
        if pos >= self.counts[stream]:
            raise TableError(f"truncated typed stream {stream}")
        self.positions[stream] += 1
        self.read_count += 1
        value = self.streams[stream][pos]
        if stream == 0 and not math.isfinite(value):
            raise TableError("non-finite scene scalar")
        return value

    def u8(self):
        return self.take(5)

    def u16(self):
        return self.take(4)

    def u32(self):
        return self.take(3)

    def floating(self):
        return self.take(0)

    def signed(self, bits: int):
        value = self.u8() if bits == 8 else self.u16()
        return value - (1 << bits) if value & (1 << (bits - 1)) else value

    def string(self):
        pos = self.positions[1]
        end = self.take(1)
        start = self.streams[1][pos - 1] if pos else 0
        raw = self.string_bytes[start:end]
        if b"\0" in raw:
            raise TableError("embedded NUL in scene name/path")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TableError("invalid scene string encoding") from exc

    def at_end(self):
        return self.read_count == self.block_end

    def finish(self):
        if not self.at_end() or any(self.positions[i] != self.counts[i]
                                    for i in (0, 1, 3, 4, 5)):
            raise TableError("unconsumed scene-table fields")


def _named_groups(reader: _Reader, count: int):
    indices = [(reader.u16(), reader.u16()) for _ in range(count)]
    names = [reader.string() for _ in range(count)]
    if any(not name for name in names) or len(set(names)) != len(names):
        raise TableError("empty or duplicate scene-table names")
    return indices, names


def _group_records(indices, names, records, kind, key):
    result = []
    for index, ((start, count), name) in enumerate(zip(indices, names)):
        if start + count > len(records):
            raise TableError("scene-table index exceeds record array")
        result.append({"name": name, "id": kind << 16 | index + 1,
                       key: copy.deepcopy(records[start:start + count])})
    return result


def parse_scene_table(data: bytes, kind: int) -> dict:
    """Decode a non-goal table; return owned JSON-compatible metadata.

    The four signed SceneInfo fields remain ``signed_params`` because their
    exact authored meaning is not assumed. ``tail_value`` is the v1 signed
    field at SceneInfo+52, not a confirmed control index.
    """
    _check_kind(kind)
    reader = _Reader(data)
    first = reader.u16()
    version = 1 if first == 1 else 0
    cut_count = reader.u16() if version else first
    cut_indices, cut_names = _named_groups(reader, cut_count)
    variant_count = reader.u16()
    condition_count, file_count = reader.u8(), reader.u8()
    if condition_count > 10 or file_count > 10:
        raise TableError("cut variant exceeds the Mobile ten-slot ABI")
    variants = []
    for _ in range(variant_count):
        variants.append({
            "conditions": [reader.u16() for _ in range(condition_count)],
            "files": [reader.string() for _ in range(file_count)],
            "flags": reader.u32(),
            "move_distance": reader.floating(),
            "human_mask": reader.u32(),
        })
    scene_count = reader.u16()
    scene_indices, scene_names = _named_groups(reader, scene_count)
    scene_record_count = reader.u16()
    scene_records = []
    for _ in range(scene_record_count):
        row = {"fade": reader.u8(), "fade_time": reader.floating(),
               "cut_id": reader.u32(), "flags": reader.u32(),
               "signed_params": [reader.signed(8), reader.signed(8),
                                  reader.signed(16), reader.signed(16)]}
        changes = reader.u8()
        if changes > 10:
            raise TableError("human assignment list exceeds the Mobile ten-slot ABI")
        row["human_changes"] = [[reader.u8(), reader.u8(), reader.u8()]
                                for _ in range(changes)]
        row["tail_value"] = reader.signed(16) if version else -1
        scene_records.append(row)
    controls = []
    control_condition_count = 0
    has_controls = not reader.at_end()
    if has_controls:
        control_count = reader.u16()
        control_indices, control_names = _named_groups(reader, control_count)
        control_record_count = reader.u16()
        control_condition_count = reader.u8()
        if control_condition_count > 10:
            raise TableError("control variant exceeds the Mobile ten-slot ABI")
        control_records = []
        for _ in range(control_record_count):
            conditions = [reader.u16() for _ in range(control_condition_count)]
            num_float, num_uint = reader.u8(), reader.u8()
            # Native retains at most four floats and one uint. Reject extra
            # fields instead of silently dropping donor-authored behavior.
            if num_float > 4 or num_uint > 1:
                raise TableError("control data exceeds the Mobile four/one-slot ABI")
            control_records.append({"conditions": conditions,
                                    "floats": [reader.floating() for _ in range(num_float)],
                                    "uints": [reader.u32() for _ in range(num_uint)]})
        controls = _group_records(control_indices, control_names,
                                  control_records, kind, "variants")
    reader.finish()
    return {"version": version, "kind": kind,
            "condition_count": condition_count, "file_count": file_count,
            "cuts": _group_records(cut_indices, cut_names, variants, kind, "variants"),
            "scenes": _group_records(scene_indices, scene_names, scene_records, kind, "cuts"),
            "has_controls": has_controls,
            "control_condition_count": control_condition_count, "controls": controls}


class _Writer:
    def __init__(self):
        self.values = [[] for _ in range(7)]
        self.strings = bytearray()

    def put(self, stream, value):
        try:
            struct.pack("<" + _FORMATS[stream], value)
        except (struct.error, OverflowError, TypeError) as exc:
            raise TableError("value outside typed-stream field width") from exc
        if stream == 0 and not math.isfinite(value):
            raise TableError("non-finite scene scalar")
        self.values[stream].append(value)

    def string(self, value):
        if not isinstance(value, str) or "\0" in value:
            raise TableError("invalid scene string")
        self.strings.extend(value.encode("utf-8"))
        self.put(1, len(self.strings))

    def signed(self, bits, value):
        if not isinstance(value, int) or not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
            raise TableError("signed scene parameter outside field width")
        self.put(5 if bits == 8 else 4, value & ((1 << bits) - 1))

    def finish(self):
        self.values[2] = [sum(len(self.values[i]) for i in (0, 1, 3, 4, 5))]
        self.values[6] = self.strings
        counts = [len(values) for values in self.values]
        offsets = [0] * 7
        output = bytearray(56)
        # The native writer emits block boundaries and string endpoints first.
        for stream in (2, 1, 0, 3, 4, 5, 6):
            offsets[stream] = len(output)
            values = self.values[stream]
            output.extend(struct.pack(f"<{len(values)}{_FORMATS[stream]}", *values))
        struct.pack_into("<14I", output, 0, *(counts + offsets))
        return bytes(output)


def _write_groups(writer, groups, key, kind):
    writer.put(4, len(groups))
    records = []
    names = []
    for index, group in enumerate(groups):
        if group.get("id") != kind << 16 | index + 1:
            raise TableError("group ID does not match its kind and table index")
        name = group["name"]
        if not name or name in names:
            raise TableError("empty or duplicate group name")
        names.append(name)
        writer.put(4, len(records))
        writer.put(4, len(group[key]))
        records.extend(group[key])
    for name in names:
        writer.string(name)
    writer.put(4, len(records))
    return records


def serialize_scene_table(table: dict) -> bytes:
    """Build a bounded v1 table. Does not copy assets or enable a native scene."""
    kind = table["kind"]
    _check_kind(kind)
    if table.get("version", 1) != 1:
        raise TableError("writer only emits the validated v1 format")
    writer = _Writer()
    writer.put(4, 1)
    variants = _write_groups(writer, table["cuts"], "variants", kind)
    condition_count = table.get("condition_count", 10)
    file_count = table.get("file_count", 10)
    writer.put(5, condition_count)
    writer.put(5, file_count)
    for row in variants:
        if len(row["conditions"]) != condition_count or len(row["files"]) != file_count:
            raise TableError("inconsistent cut field dimensions")
        for value in row["conditions"]:
            writer.put(4, value)
        for value in row["files"]:
            writer.string(value)
        writer.put(3, row["flags"])
        writer.put(0, row["move_distance"])
        writer.put(3, row["human_mask"])
    rows = _write_groups(writer, table["scenes"], "cuts", kind)
    for row in rows:
        writer.put(5, row["fade"])
        writer.put(0, row["fade_time"])
        writer.put(3, row["cut_id"])
        writer.put(3, row["flags"])
        params = row["signed_params"]
        if len(params) != 4:
            raise TableError("scene requires four signed parameters")
        for bits, value in zip((8, 8, 16, 16), params):
            writer.signed(bits, value)
        writer.put(5, len(row["human_changes"]))
        for change in row["human_changes"]:
            if len(change) != 3:
                raise TableError("human assignment requires three bytes")
            for value in change:
                writer.put(5, value)
        writer.signed(16, row.get("tail_value", -1))
    if table.get("has_controls", bool(table.get("controls"))):
        records = _write_groups(writer, table.get("controls", []), "variants", kind)
        condition_count = table.get("control_condition_count", 10)
        writer.put(5, condition_count)
        for row in records:
            if len(row["conditions"]) != condition_count:
                raise TableError("inconsistent control condition dimensions")
            for value in row["conditions"]:
                writer.put(4, value)
            writer.put(5, len(row["floats"]))
            writer.put(5, len(row["uints"]))
            for value in row["floats"]:
                writer.put(0, value)
            for value in row["uints"]:
                writer.put(3, value)
    output = writer.finish()
    parse_scene_table(output, kind)  # enforce all bounds on authored output too
    return output


def select_scene(table: dict, scene_id: int, *, name: str | None = None) -> dict:
    """Select one scene, retaining/remapping referenced cuts without guessing.

    All variants/conditions are retained. Missing or cross-kind references are
    rejected. Entrance is mapped to the Mobile entrance slot (0x10001). Other
    banks preserve all scene/cut IDs: native actor setup branches on ending IDs
    0x70001/0x70002, so compacting those indices would change scene semantics.
    Unselected groups in those banks retain names/IDs but have no records.

    This selection is audit material, not a complete replacement for a shipped
    table: native fallback scenes must be retained separately before deployment.
    The caller must audit every dependency, actor and condition before enabling
    a scene. No controller tables are silently discarded.
    """
    kind = table["kind"]
    _check_kind(kind)
    scene = next((row for row in table["scenes"] if row["id"] == scene_id), None)
    if scene is None:
        raise TableError("selected scene does not exist")
    selected = copy.deepcopy(scene)
    wanted = list(dict.fromkeys(row["cut_id"] for row in selected["cuts"] if row["cut_id"]))
    by_id = {row["id"]: row for row in table["cuts"]}
    if any(value not in by_id for value in wanted):
        raise TableError("scene references a missing or cross-kind cut")
    if kind != 1:
        result = copy.deepcopy(table)
        result["version"] = 1
        for cut in result["cuts"]:
            if cut["id"] not in wanted:
                cut["variants"] = []
        for row in result["scenes"]:
            if row["id"] != scene_id:
                row["cuts"] = []
            elif name is not None:
                row["name"] = name
        return result
    mapping = {value: kind << 16 | index + 1 for index, value in enumerate(wanted)}
    cuts = []
    for value in wanted:
        cut = copy.deepcopy(by_id[value])
        cut["id"] = mapping[value]
        cuts.append(cut)
    selected["id"] = kind << 16 | 1
    if name is not None:
        selected["name"] = name
    for row in selected["cuts"]:
        if row["cut_id"]:
            row["cut_id"] = mapping[row["cut_id"]]
    result = copy.deepcopy(table)
    result.update(version=1, cuts=cuts, scenes=[selected])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("--kind", type=int, required=True, choices=SUPPORTED_KINDS)
    args = parser.parse_args()
    table = parse_scene_table(args.table.read_bytes(), args.kind)
    print(json.dumps(table, indent=2))


if __name__ == "__main__":
    main()
