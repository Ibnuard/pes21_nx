#!/usr/bin/env python3
"""Stage a local-only audio delta from the user's mobile and FL26 sound banks.

The two explicit Indonesia cues replace the donor's plain team-name cues.
Their HCA payloads become an embedded memory AWB; the large streaming AWB is
unchanged. No extracted audio or generated delta belongs in the public tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from build_fl26_cup_catalog import cpk_member, index_cpk
from prepare_runtime import decrypt_utf, parse_utf_table, read_cpk_packet

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b"NXCMT01\0"
HEADER = struct.Struct("<8sIIQQII")
MAX_BANK = 8 * 1024 * 1024
MAX_PATCH = 1024 * 1024
# These must match the per-decoder plaintext policy in team_commentary_policy.h.
# They fingerprint metadata only, and contain no recording or cipher key.
PLAINTEXT_HEADER_FNV = {"A1": 0x1F86AAC769AAE1CB, "B1": 0xCC0F25261657DA3F}
FORMATS = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i",
           6: ">Q", 7: ">q", 8: ">f", 10: ">I", 11: ">II"}


def fnv64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


class Utf:
    """CRI UTF view retaining exact field locations for surgical edits."""

    def __init__(self, data: bytes, origin: int = 0):
        self.origin = origin
        if data[:4] != b"@UTF":
            raise ValueError("missing UTF signature")
        self.size = struct.unpack_from(">I", data, 4)[0] + 8
        if self.size > len(data):
            raise ValueError("truncated UTF")
        self.data = data[:self.size]
        # Offset 8 contains version/encoding, not the upper half of rows_offset.
        normalized = bytearray(self.data)
        normalized[8:10] = b"\0\0"
        self.rows = parse_utf_table(bytes(normalized))
        self.row_start = 8 + struct.unpack_from(">H", data, 10)[0]
        self.strings = 8 + struct.unpack_from(">I", data, 12)[0]
        self.blobs = 8 + struct.unpack_from(">I", data, 16)[0]
        self.stride = struct.unpack_from(">H", data, 26)[0]
        descriptor, relative = 32, 0
        self.fields = {}
        for _ in range(struct.unpack_from(">H", data, 24)[0]):
            flag = data[descriptor]
            name_offset = self.strings + struct.unpack_from(">I", data, descriptor + 1)[0]
            name = data[name_offset:data.index(b"\0", name_offset)].decode("utf-8")
            descriptor += 5
            fmt = FORMATS[flag & 15]
            storage = flag & 0xF0
            location = descriptor if storage == 0x30 else relative
            self.fields[name] = (storage, fmt, location)
            if storage == 0x30:
                descriptor += struct.calcsize(fmt)
            elif storage == 0x50:
                relative += struct.calcsize(fmt)
        if relative != self.stride:
            raise ValueError("UTF row stride mismatch")

    def cell(self, row: int, field: str) -> tuple[int, str]:
        storage, fmt, offset = self.fields[field]
        if storage != 0x50:
            raise ValueError(f"{field} is not a per-row field")
        return self.origin + self.row_start + row * self.stride + offset, fmt

    def child(self, field: str) -> "Utf":
        offset, length = self.rows[0][field]
        start = self.blobs + offset
        return Utf(self.data[start:start + length], self.origin + start)

    def blob(self, row: int, field: str) -> bytes:
        offset, length = self.rows[row][field]
        return self.data[self.blobs + offset:self.blobs + offset + length]


def rewrite_waveforms(table: Utf, rows: list[dict]) -> bytes:
    """Promote Streaming to a row field while retaining all waveform metadata."""
    strings = table.data[table.strings:table.blobs]
    name_offset = struct.unpack_from(">I", table.data, 20)[0]
    descriptors, values = bytearray(), bytearray()
    stride = 0
    for name, (storage, fmt, _) in table.fields.items():
        kind = next(k for k, v in FORMATS.items() if v == fmt)
        if kind in (10, 11) or name in ("StreamAwbId", "MemoryAwbId"):
            raise ValueError("expected mobile v1 numeric waveform schema")
        if name == "Streaming":
            storage = 0x50
        descriptors.extend(struct.pack(">BI", storage | kind,
                                       strings.index(name.encode() + b"\0")))
        if storage == 0x30:
            if any(r[name] != rows[0][name] for r in rows):
                raise ValueError(f"waveform constant {name} changed")
            descriptors.extend(struct.pack(fmt, rows[0][name]))
        elif storage == 0x50:
            stride += struct.calcsize(fmt)
    for row in rows:
        for name, (storage, fmt, _) in table.fields.items():
            if storage == 0x50 or name == "Streaming":
                values.extend(struct.pack(fmt, row[name]))
    start = 32 + len(descriptors)
    string_start = start + len(values)
    data_start = string_start + len(strings)
    header = bytearray(table.data[:32])
    struct.pack_into(">I", header, 4, data_start - 8)
    struct.pack_into(">H", header, 10, start - 8)
    struct.pack_into(">IIIHHI", header, 12, string_start - 8,
                     data_start - 8, name_offset, len(table.fields), stride, len(rows))
    return bytes(header + descriptors + values + strings)


def mobile_index(path: Path):
    try:
        return index_cpk(path)
    except (RuntimeError, UnicodeError, KeyError):
        # The supported legacy sound override damages three TOC column names.
        # Recover names for reading only; never rewrite the installed CPK.
        with path.open("rb") as stream:
            head = read_cpk_packet(stream, 0, b"CPK ")[0]
            stream.seek(head["TocOffset"] + 8)
            size, = struct.unpack("<Q", stream.read(8))
            table = bytearray(decrypt_utf(stream.read(size)))
        strings = 8 + struct.unpack_from(">I", table, 12)[0]
        for index, name in enumerate((b"DirName", b"FileName", b"FileSize")):
            struct.pack_into(">I", table, 33 + index * 5,
                             table.index(name + b"\0", strings) - strings)
        rows = parse_utf_table(bytes(table))
        return {f"{r['DirName']}/{r['FileName']}": r for r in rows}, min(
            head["TocOffset"], head["ContentOffset"])


def read_awb_wave(path: Path, member: dict, base: int, wave_id: int) -> bytes:
    with path.open("rb") as stream:
        start = base + member["FileOffset"]
        stream.seek(start)
        header = stream.read(16)
        if header[:4] != b"AFS2":
            raise ValueError("unsupported AWB signature")
        offset_width, id_width = header[5:7]
        count, alignment, subkey = struct.unpack_from("<IHH", header, 8)
        if (offset_width not in (2, 4) or id_width != 2 or not alignment
                or count > 65535 or subkey):
            raise ValueError("unsupported AWB layout/key")
        ids = [int.from_bytes(stream.read(id_width), "little") for _ in range(count)]
        offsets = [int.from_bytes(stream.read(offset_width), "little")
                   for _ in range(count + 1)]
        index = ids.index(wave_id)
        first = (offsets[index] + alignment - 1) // alignment * alignment
        last = offsets[index + 1]
        if not 0 <= first < last <= member["FileSize"]:
            raise ValueError("AWB wave range invalid")
        stream.seek(start + first)
        data = stream.read(last - first)
    # This policy copies only the two unencrypted, non-looping FL26 HCA cues.
    if data[:4] != b"HCA\0" or b"ciph\0\0" not in data[:96]:
        raise ValueError("expected unencrypted HCA recording")
    return data


def memory_awb(waves: list[tuple[int, bytes]]) -> bytes:
    waves = sorted(waves)
    count = len(waves)
    out = bytearray(16 + 2 * count + 4 * (count + 1))
    out[:16] = struct.pack("<4s4BIHH", b"AFS2", 2, 4, 2, 0, count, 32, 0)
    for i, (ident, data) in enumerate(waves):
        struct.pack_into("<H", out, 16 + i * 2, ident)
        struct.pack_into("<I", out, 16 + count * 2 + i * 4, len(out))
        out.extend(bytes((-len(out)) % 32))
        out.extend(data)
    struct.pack_into("<I", out, 16 + count * 2 + count * 4, len(out))
    return bytes(out)


def make_delta(base: bytes, target: bytes, ranges: list[tuple[int, int]]) -> bytes:
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    patch = bytearray(HEADER.pack(MAGIC, len(base), len(target), fnv64(base),
                                  fnv64(target), len(merged), 0))
    reconstructed = bytearray(base + bytes(len(target) - len(base)))
    for start, end in merged:
        patch.extend(struct.pack("<II", start, end - start))
        patch.extend(target[start:end])
        reconstructed[start:end] = target[start:end]
    if reconstructed != target or len(merged) > 64 or len(patch) > MAX_PATCH:
        raise ValueError("delta verification/size failed")
    return bytes(patch)


def build_patch(base: bytes, donor: bytes, wave_reader) -> tuple[bytes, dict]:
    top, source_top = Utf(base), Utf(donor)
    if top.rows[0]["Name"] != "00_TEAM" or top.rows[0]["AwbFile"] != (0, 0):
        raise ValueError("expected streaming-only mobile team bank")
    tables = {name: top.child(name) for name in (
        "CueTable", "CueNameTable", "WaveformTable", "SynthTable",
        "CommandTable", "TrackTable", "SequenceTable")}
    source = {name: source_top.child(name) for name in (
        "CueTable", "CueNameTable", "WaveformTable")}
    if any(not row["Streaming"] for row in tables["WaveformTable"].rows):
        raise ValueError("mobile memory wave IDs already occupied")
    wave_rows = [dict(row) for row in tables["WaveformTable"].rows]
    if sorted(r["CueIndex"] for r in tables["CueNameTable"].rows) != list(range(len(wave_rows))):
        raise ValueError("mobile cues have shared or missing name references")
    target = bytearray(base)
    ranges, waves, report = [], [], []

    def write(offset, data):
        target[offset:offset + len(data)] = data
        ranges.append((offset, offset + len(data)))

    def field(table, index, name, value):
        offset, fmt = table.cell(index, name)
        values = value if isinstance(value, tuple) else (value,)
        write(offset, struct.pack(fmt, *values))

    for speaker in ("A1", "B1"):
        old, new = f"EN_{speaker}_T0_R1164", f"EN_{speaker}_T0_R5750"
        names = tables["CueNameTable"]
        matching = [i for i, r in enumerate(names.rows) if r["CueName"] == old]
        originals = [r for r in source["CueNameTable"].rows if r["CueName"] == new]
        if len(matching) != 1 or len(originals) != 1 or any(
                r["CueName"] == new for r in names.rows):
            raise ValueError(f"expected unique donor/source label {old}/{new}")
        name_index = matching[0]
        cue_index = names.rows[name_index]["CueIndex"]
        cue = tables["CueTable"].rows[cue_index]
        # Verify this bank's one-cue/sequence/track/synth/wave chain. The two
        # affected waveform rows must not be shared with any other cue.
        counts = {len(t.rows) for t in tables.values()}
        if len(counts) != 1:
            raise ValueError("mobile bank is not the audited one-to-one layout")
        if any(c["ReferenceType"] != 3 or c["ReferenceIndex"] != i
               for i, c in enumerate(tables["CueTable"].rows)):
            raise ValueError("unexpected mobile cue graph")
        for i in range(len(tables["SequenceTable"].rows)):
            seq = tables["SequenceTable"].rows[i]
            track = tables["TrackTable"].rows[i]
            synth = tables["SynthTable"].rows[i]
            command = tables["CommandTable"].blob(i, "Command")
            if (seq["NumTracks"] != 1
                    or tables["SequenceTable"].blob(i, "TrackIndex") != struct.pack(">H", i)
                    or track["EventIndex"] != i
                    or tables["SynthTable"].blob(i, "ReferenceItems") != struct.pack(">HH", 1, i)
                    or command != struct.pack(">HBHHHB", 2000, 4, 2, i, 0, 0)):
                raise ValueError(f"unexpected/shared mobile audio chain at {i}")
        source_cue = source["CueTable"].rows[originals[0]["CueIndex"]]
        if source_cue["ReferenceType"] != 1:
            raise ValueError("source Indonesia cue is not a direct waveform")
        wave = source["WaveformTable"].rows[source_cue["ReferenceIndex"]]
        payload = wave_reader(wave["StreamAwbId"])
        header_hash = fnv64(payload[:96])
        if len(payload) < 96 or header_hash != PLAINTEXT_HEADER_FNV[speaker]:
            raise ValueError(f"unrecognized {speaker} HCA header; audit decoder policy before staging")
        waves.append((cue_index, payload))
        # Keep the original cue/sequence/track/synth graph. Only these two
        # terminal waveform rows switch from streaming to embedded memory.
        field(tables["CueTable"], cue_index, "Length", source_cue["Length"])
        for key in ("EncodeType", "NumChannels", "LoopFlag", "SamplingRate", "NumSamples"):
            wave_rows[cue_index][key] = wave[key]
        wave_rows[cue_index]["Streaming"] = 0
        wave_rows[cue_index]["Id"] = cue_index
        offset, _ = names.cell(name_index, "CueName")
        string = names.origin + names.strings + struct.unpack_from(">I", target, offset)[0]
        write(string, new.encode("ascii"))
        names.rows[name_index]["CueName"] = new
        report.append({"cue": new, "replaced": old, "duration_ms": source_cue["Length"],
                       "audio_bytes": len(payload), "audio_sha256": hashlib.sha256(payload).hexdigest(),
                       "plaintext_header_fnv64": f"{header_hash:016x}"})

    # CRI name lookup expects the rows to remain lexically sorted.
    names = tables["CueNameTable"]
    row_bytes = [base[names.origin + names.row_start + i * names.stride:
                      names.origin + names.row_start + (i + 1) * names.stride]
                 for i in range(len(names.rows))]
    ordering = sorted(range(len(names.rows)), key=lambda i: names.rows[i]["CueName"])
    write(names.origin + names.row_start, b"".join(row_bytes[i] for i in ordering))
    def append_blob(field_name, data):
        append_at = (len(target) + 31) // 32 * 32
        target.extend(bytes(append_at - len(target)))
        target.extend(data)
        field(top, 0, field_name, (append_at - top.blobs, len(data)))

    append_blob("WaveformTable", rewrite_waveforms(tables["WaveformTable"], wave_rows))
    awb = memory_awb(waves)
    append_blob("AwbFile", awb)
    ranges.append((len(base), len(target)))
    write(4, struct.pack(">I", len(target) - 8))
    if len(target) > MAX_BANK:
        raise ValueError("team bank exceeds runtime limit")
    delta = make_delta(base, bytes(target), ranges)
    return delta, {"cues": report, "base_bytes": len(base), "result_bytes": len(target),
                   "delta_bytes": len(delta), "base_fnv64": f"{fnv64(base):016x}",
                   "result_fnv64": f"{fnv64(target):016x}",
                   "base_sha256": hashlib.sha256(base).hexdigest(),
                   "result_sha256": hashlib.sha256(target).hexdigest(),
                   "other_cues_preserved": len(tables["CueTable"].rows) - 2,
                   "streaming_awb_unchanged": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mobile-cpk", type=Path, required=True)
    parser.add_argument("--fl26-cpk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="new ignored local output directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "local-debug"):
        parser.error("generated proprietary audio must stay under local-debug")
    if output.exists():
        parser.error("output already exists; choose a new staging directory")
    mobile, mb = mobile_index(args.mobile_cpk)
    fl26, fb = index_cpk(args.fl26_cpk)
    member = "eng/sound/acb/00_TEAM.acb"
    original = cpk_member(args.mobile_cpk, mobile, mb, member)
    source = cpk_member(args.fl26_cpk, fl26, fb, member)
    delta, report = build_patch(original, source, lambda ident: read_awb_wave(
        args.fl26_cpk, fl26["eng/sound/awb/00_TEAM.awb"], fb, ident))
    destination = output / "Commentary" / "indonesia.nxcp"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(delta)
    report["status"] = "local_candidate_requires_switch_playback_check"
    report["delta_sha256"] = hashlib.sha256(delta).hexdigest()
    (output / "commentary-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
