#!/usr/bin/env python3
"""Stage one owned FL26 Cup celebration recording in a detached Mobile bank.

Only the named HCA range is read from FL26; neither its AWB nor the Mobile OBB
is extracted. Mobile's ACF identity/schema provide the one-cue playback graph.
The original HCA and loop metadata remain exact. All outputs stay ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from entrance_scene_canary import Cpk, digest
from prepare_loose_cpk import member_name
from prepare_runtime import read_cpk_packet
from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import kinds, rebuild_utf

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ACB = "common/sound/match/acb/BGM_Match.acb"
SOURCE_AWB = "common/sound/match/awb/BGM_Match.awb"
MOBILE_ACB = "common/sound/match/acb/BGM_Match_AM.acb"
SOURCE_CUE = "BGM1_ORG_CHAMP_CP"
CUE = "FNX_TROPHY_FL26_CUP_V88"
BANK_NAME = "FNX_TROPHY_V88"
ASSET = "Audio/trophy-fl26-v88.acb"
SOURCE_ACB_SHA = "ef593e7b4f27d45f090e4aaf6a4fe61c07401dbe31038f550e5e4b79c9b515b5"
MOBILE_ACB_SHA = "a3b7f37cd90748f5d3d5c7b341163cbc45be0dc1ae1bbd74b94b1d048545e9d1"
WAVE_SHA = "afa106ddb741b50e373c75642a37306d01895a75b45b29bbb790cbaa13ddabdf"
WAVE_BYTES = 1582342
MAX_BANK = 2 * 1024 * 1024


class MemberView:
    """Bound a file-like reader to one existing uncompressed nested member."""
    def __init__(self, stream, start: int, size: int):
        self.stream, self.start, self.size, self.at = stream, start, size, 0

    def seek(self, offset, whence=0):
        offset += self.at if whence == 1 else self.size if whence == 2 else 0
        if whence not in (0, 1, 2) or not 0 <= offset <= self.size:
            raise ValueError("nested CPK seek outside member")
        self.at = offset
        return offset

    def tell(self):
        return self.at

    def read(self, size=-1):
        size = self.size - self.at if size < 0 else size
        if size > self.size - self.at:
            raise ValueError("nested CPK read outside member")
        self.stream.seek(self.start + self.at)
        result = self.stream.read(size)
        self.at += len(result)
        return result


def mobile_bank(obb: Path) -> bytes:
    outer = Cpk(obb)
    row = outer.index["Expansion/dt540_mobile_all.cpk"]
    if row["FileSize"] != row["ExtractSize"]:
        raise ValueError("compressed sound CPK is not supported")
    with obb.open("rb") as stream:
        view = MemberView(stream, outer.base + row["FileOffset"], row["FileSize"])
        header = read_cpk_packet(view, 0, b"CPK ")[0]
        rows = read_cpk_packet(view, header["TocOffset"], b"TOC ")
        matches = [r for r in rows if member_name(r) == MOBILE_ACB]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous Mobile music bank")
        entry = matches[0]
        if entry["FileSize"] != entry["ExtractSize"] or entry["FileSize"] > 100000:
            raise ValueError("unexpected Mobile music bank envelope")
        view.seek(min(header["TocOffset"], header["ContentOffset"]) + entry["FileOffset"])
        blob = view.read(entry["FileSize"])
    if digest(blob) != MOBILE_ACB_SHA:
        raise ValueError("Mobile music template differs")
    return blob


def source_wave(source: Cpk, top: Utf) -> tuple[bytes, dict, dict]:
    """Prove every graph edge before accepting the single bounded recording."""
    names = [r for r in top.child("CueNameTable").rows if r["CueName"] == SOURCE_CUE]
    if names != [{"CueName": SOURCE_CUE, "CueIndex": 11}]:
        raise ValueError("Cup music cue identity differs")
    cue = top.child("CueTable").rows[11]
    sequence = top.child("SequenceTable")
    track = top.child("TrackTable").rows[13]
    event = top.child("TrackEventTable")
    synth = top.child("SynthTable")
    wave = top.child("WaveformTable").rows[10]
    if (cue["ReferenceType"] != 3 or cue["ReferenceIndex"] != 11 or
            sequence.rows[11]["NumTracks"] != 1 or sequence.blob(11, "TrackIndex") != b"\0\x0d" or
            track["EventIndex"] != 13 or event.blob(13, "Command") != bytes.fromhex("07d0040002000d000000") or
            synth.blob(13, "ReferenceItems") != b"\0\x01\0\x0a" or
            wave != {"MemoryAwbId": 65535, "EncodeType": 2, "Streaming": 1,
                     "NumChannels": 2, "LoopFlag": 2, "SamplingRate": 48000,
                     "NumSamples": 5429646, "ExtensionData": 0,
                     "StreamAwbPortNo": 0, "StreamAwbId": 49}):
        raise ValueError("Cup music source graph differs")
    loop = top.child("WaveformExtensionDataTable").rows[0]
    if loop != {"LoopStart": 0, "LoopEnd": 5429646}:
        raise ValueError("Cup music loop differs")
    row = source.index[SOURCE_AWB]
    if row["FileSize"] != row["ExtractSize"]:
        raise ValueError("compressed music AWB is not supported")
    with source.path.open("rb") as stream:
        start = source.base + row["FileOffset"]
        stream.seek(start)
        header = stream.read(16)
        if header[:8] != b"AFS2\x02\x04\x02\0":
            raise ValueError("unreviewed music AWB layout")
        count, alignment, subkey = struct.unpack_from("<IHH", header, 8)
        if (count, alignment, subkey) != (67, 32, 0):
            raise ValueError("unreviewed music AWB bounds")
        metadata = stream.read(count * 2 + (count + 1) * 4)
        ids = struct.unpack_from("<67H", metadata)
        offsets = struct.unpack_from("<68I", metadata, count * 2)
        if len(set(ids)) != count or tuple(sorted(offsets)) != offsets:
            raise ValueError("invalid music AWB index")
        index = ids.index(49)
        first, last = (offsets[index] + 31) & ~31, offsets[index + 1]
        if (first, last) != (33677248, 35259590) or last > row["FileSize"]:
            raise ValueError("Cup music wave range differs")
        stream.seek(start + first)
        audio = stream.read(last - first)
    if len(audio) != WAVE_BYTES or digest(audio) != WAVE_SHA:
        raise ValueError("Cup music payload differs")
    if audio[:4] != b"HCA\0" or audio[6:8] != b"\x01\x04" or audio[56:62] != b"ciph\0\0":
        raise ValueError("Cup music plaintext header differs")
    return audio, wave, loop


def row_copy(table: Utf, index: int) -> dict:
    result = dict(table.rows[index])
    for name, kind in kinds(table).items():
        if kind == 11:
            result[name] = table.blob(index, name)
    return result


def build_bank(mobile: bytes, source: bytes, audio: bytes, wave: dict, loop: dict) -> bytes:
    """One cue/sequence/track/synth/wave; no external bank or playlist links."""
    if (digest(mobile) != MOBILE_ACB_SHA or digest(source) != SOURCE_ACB_SHA or
            digest(audio) != WAVE_SHA):
        raise ValueError("music bank input provenance differs")
    native, original = Utf(mobile), Utf(source)
    children = {}
    cue = row_copy(native.child("CueTable"), 5)
    cue.update(CueId=0, ReferenceType=3, ReferenceIndex=0, Length=0xFFFFFFFF)
    name = {"CueName": CUE, "CueIndex": 0}
    sequence = row_copy(native.child("SequenceTable"), 5)
    sequence.update(NumTracks=1, TrackIndex=b"\0\0", CommandIndex=65535,
                    Type=0, ControlWorkArea1=0, ControlWorkArea2=0)
    track = row_copy(native.child("TrackTable"), 7)
    track.update(EventIndex=0, CommandIndex=65535, LocalAisacs=b"")
    synth = row_copy(native.child("SynthTable"), 7)
    synth.update(ReferenceItems=b"\0\x01\0\0", CommandIndex=65535,
                 ControlWorkArea1=0, ControlWorkArea2=0, LocalAisacs=b"")
    event = {"Command": bytes.fromhex("07d00400020000000000")}
    memory_wave = dict(wave, MemoryAwbId=0, Streaming=0,
                       StreamAwbPortNo=65535, StreamAwbId=65535)
    replacements = {"CueTable": [cue], "CueNameTable": [name],
                    "SequenceTable": [sequence], "TrackTable": [track],
                    "SynthTable": [synth], "TrackEventTable": [event],
                    "WaveformTable": [memory_wave]}
    for field, rows in replacements.items():
        children[field] = rebuild_utf(native.child(field), rows, compact_blobs=True)
    children["WaveformExtensionDataTable"] = rebuild_utf(
        original.child("WaveformExtensionDataTable"), [loop], compact_blobs=True)
    children["AwbFile"] = memory_awb([(0, audio)])
    row = row_copy(native, 0)
    row.update(Name=BANK_NAME, AcbGuid=hashlib.sha256(CUE.encode() + audio).digest()[:16])
    for field in ("StreamAwbHash", "StreamAwbTocWorkOld", "StreamAwbTocWork_Old",
                  "StreamAwbTocWork", "StreamAwbAfs2Header"):
        if field in row:
            row[field] = b""
    row.update(children)
    result = rebuild_utf(native, [row], compact_blobs=True)
    verify_bank(result, audio, native)
    return result


def verify_bank(blob: bytes, audio: bytes, native: Utf | None = None) -> None:
    if not 1000 < len(blob) <= MAX_BANK:
        raise ValueError("Cup music bank is outside bounded size")
    top = Utf(blob)
    if (top.rows[0]["Name"] != BANK_NAME or
            top.child("CueNameTable").rows != [{"CueName": CUE, "CueIndex": 0}]):
        raise ValueError("Cup music bank exposes unrelated cues")
    if native and (top.rows[0]["Version"] != native.rows[0]["Version"] or
                   top.blob(0, "AcfMd5Hash") != native.blob(0, "AcfMd5Hash")):
        raise ValueError("Cup music changed native schema/ACF binding")
    fields = ("CueTable", "SequenceTable", "TrackTable", "SynthTable",
              "TrackEventTable", "WaveformTable", "WaveformExtensionDataTable")
    if any(len(top.child(field).rows) != 1 for field in fields):
        raise ValueError("Cup music graph is not one-to-one")
    cue, seq, track, synth, event, wave, loop = (top.child(f) for f in fields)
    if (cue.rows[0]["ReferenceType"] != 3 or cue.rows[0]["ReferenceIndex"] != 0 or
            seq.rows[0]["NumTracks"] != 1 or seq.blob(0, "TrackIndex") != b"\0\0" or
            track.rows[0]["EventIndex"] != 0 or
            event.blob(0, "Command") != bytes.fromhex("07d00400020000000000") or
            synth.blob(0, "ReferenceItems") != b"\0\x01\0\0" or
            wave.rows[0]["MemoryAwbId"] != 0 or wave.rows[0]["Streaming"] != 0 or
            wave.rows[0]["NumSamples"] != 5429646 or wave.rows[0]["SamplingRate"] != 48000 or
            wave.rows[0]["ExtensionData"] != 0 or
            loop.rows[0] != {"LoopStart": 0, "LoopEnd": 5429646}):
        raise ValueError("Cup music graph/loop verification failed")
    awb = top.blob(0, "AwbFile")
    if awb[:16] != struct.pack("<4s4BIHH", b"AFS2", 2, 4, 2, 0, 1, 32, 0):
        raise ValueError("Cup music embedded AWB differs")
    ident = struct.unpack_from("<H", awb, 16)[0]
    start, end = struct.unpack_from("<II", awb, 18)
    if ident or end != len(awb) or awb[(start + 31) & ~31:end] != audio:
        raise ValueError("Cup music recording is not exact")


def catalog(blob: bytes, audio: bytes) -> str:
    return f'''/* Generated metadata only; the owned FL26 recording remains ignored. */
#ifndef PESNX_TROPHY_AUDIO_CATALOG_H
#define PESNX_TROPHY_AUDIO_CATALOG_H
#define TROPHY_AUDIO_ASSET "{ASSET}"
#define TROPHY_AUDIO_CUE "{CUE}"
#define TROPHY_AUDIO_BYTES {len(blob)}u
#define TROPHY_AUDIO_FNV UINT64_C(0x{fnv64(blob):016x})
#define TROPHY_AUDIO_HEADER_BYTES 260u
#define TROPHY_AUDIO_HEADER_FNV UINT64_C(0x{fnv64(audio[:260]):016x})
#endif
'''


def stage(fl26: Path, obb: Path, output: Path, decoder: Path) -> dict:
    output = output.resolve()
    if output.drive.upper() != "D:" or not output.is_relative_to(ROOT / "local-debug") or output.exists():
        raise ValueError("use a new ignored local-debug directory on D")
    source = Cpk(fl26)
    raw = source.read(SOURCE_ACB)
    if digest(raw) != SOURCE_ACB_SHA:
        raise ValueError("FL26 music bank differs")
    audio, wave, loop = source_wave(source, Utf(raw))
    mobile = mobile_bank(obb)
    blob = build_bank(mobile, raw, audio, wave, loop)
    output.mkdir(parents=True)
    recording = output / "trophy-source.hca"
    recording.write_bytes(audio)
    decoded = subprocess.run([str(decoder), "-nostdin", "-v", "error", "-xerror",
                              "-i", str(recording), "-f", "null", "-"],
                             capture_output=True, timeout=120)
    if decoded.returncode:
        raise ValueError("Cup music desktop decode failed: " + decoded.stderr.decode("utf-8", "replace")[:600])
    target = output / ASSET
    target.parent.mkdir()
    target.write_bytes(blob)
    (output / "trophy_audio_catalog.h").write_text(catalog(blob, audio), encoding="ascii", newline="\n")
    report = {"schema": "PESNX_TROPHY_AUDIO_V88", "status": "staged_decode_verified",
              "source_archive": str(fl26.resolve()), "source_acb_member": SOURCE_ACB,
              "source_acb_sha256": digest(raw), "source_cue": SOURCE_CUE,
              "source_awb_member": SOURCE_AWB, "source_wave_id": 49,
              "source_wave_bytes": len(audio), "source_wave_sha256": digest(audio),
              "source_graph": {"cue": 11, "sequence": 11, "track": 13,
                               "event": 13, "synth": 13, "waveform": 10},
              "mobile_template_sha256": digest(mobile), "mobile_acf_preserved": True,
              "runtime_asset": ASSET, "runtime_cue": CUE,
              "bank_bytes": len(blob), "bank_sha256": digest(blob), "bank_fnv64": f"{fnv64(blob):016x}",
              "loop": loop, "wave": wave, "full_desktop_decode_exit_code": 0,
              "device_audio_accepted": False, "source_mutated": False,
              "native_bank_unmodified": True, "runtime_installed": False}
    (output / "AUDIO-REPORT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    recording.unlink()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fl26-cpk", type=Path, required=True)
    parser.add_argument("--mobile-obb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.fl26_cpk, args.mobile_obb, args.output, args.decoder), indent=2))


if __name__ == "__main__":
    main()
