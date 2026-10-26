#!/usr/bin/env python3
"""Encode a user-supplied recording into one detached native ADX cue.

The supplied original stays read-only. No codec executable or game data is
embedded here; the local native music template supplies its ACF/schema only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from entrance_scene_canary import digest
from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import rebuild_utf
from stage_trophy_music import ROOT, MAX_BANK, mobile_bank, row_copy, MOBILE_ACB_SHA

ASSET = "Audio/trophy-user-v89.acb"
CUE = "FNX_TROPHY_USER_V89"
BANK_NAME = "FNX_TROPHY_USER_V89"
NATIVE_COMMAND_SHA = "3e3ec7ea2219024e1615ee036ffc751ad784f27176c6c914cbd88c75553f78b6"
NATIVE_STRINGS_SHA = "4c5e53c0359a37238539cdac34b5be0c354fd3dbdbfe088d4beb491dc41dea8d"


def adx_info(audio: bytes) -> dict:
    if len(audio) < 36 or audio[:2] != b"\x80\0":
        raise ValueError("not an ADX recording")
    start = struct.unpack_from(">H", audio, 2)[0] + 4
    encoding, block, bits, channels = audio[4:8]
    rate, samples = struct.unpack_from(">II", audio, 8)
    if ((encoding, block, bits, audio[18], audio[19]) != (3, 18, 4, 3, 0) or
            channels not in (1, 2) or not 8000 <= rate <= 48000 or not samples or
            start < 36 or audio[start - 6:start] != b"(c)CRI"):
        raise ValueError("unreviewed ADX codec/header")
    size = start + ((samples + 31) // 32) * block * channels
    if size != len(audio):
        raise ValueError("ADX declared frames differ from payload")
    return {"encoding": encoding, "block_bytes": block, "bits": bits,
            "channels": channels, "sample_rate": rate, "samples": samples,
            "header_bytes": start, "cipher": 0, "version": 3,
            "duration_seconds": samples / rate}


def remove_partial_footer(audio: bytes) -> tuple[bytes, bytes]:
    """Strip only ffmpeg's incomplete stereo terminal marker, never PCM frames."""
    if len(audio) < 36:
        raise ValueError("short ADX output")
    start = struct.unpack_from(">H", audio, 2)[0] + 4
    samples = struct.unpack_from(">I", audio, 12)[0]
    end = start + ((samples + 31) // 32) * audio[5] * audio[7]
    footer = audio[end:]
    if footer != bytes.fromhex("8001000e0000000000000000000000000000"):
        raise ValueError("unexpected ADX terminal bytes")
    body = audio[:end]
    adx_info(body)
    return body, footer


def build_bank(mobile: bytes, audio: bytes) -> bytes:
    if digest(mobile) != MOBILE_ACB_SHA:
        raise ValueError("native music template differs")
    info, native = adx_info(audio), Utf(mobile)
    cue = row_copy(native.child("CueTable"), 5)
    cue.update(CueId=0, ReferenceType=3, ReferenceIndex=0, Length=0xFFFFFFFF)
    seq = row_copy(native.child("SequenceTable"), 5)
    # Keep sequence 5's exact native cue-local music routing. Clearing its
    # CommandIndex also discarded authored categories/priority/bus sends.
    # The referenced command/string tables and ACF remain exact native data.
    seq.update(NumTracks=1, TrackIndex=b"\0\0",
               Type=0, ControlWorkArea1=0, ControlWorkArea2=0)
    track = row_copy(native.child("TrackTable"), 7)
    track.update(EventIndex=0, CommandIndex=65535, LocalAisacs=b"")
    synth = row_copy(native.child("SynthTable"), 7)
    synth.update(ReferenceItems=b"\0\x01\0\0", CommandIndex=65535,
                 ControlWorkArea1=0, ControlWorkArea2=0, LocalAisacs=b"")
    wave = row_copy(native.child("WaveformTable"), 0)
    # Original criAtomExAcb_GetWaveformInfoById maps EncodeType 0 to native
    # format 1 (ADX). LoopFlag 1/ExtensionData 65535 are native non-loop values.
    wave.update(MemoryAwbId=0, EncodeType=0, Streaming=0,
                NumChannels=info["channels"], LoopFlag=1,
                SamplingRate=info["sample_rate"], NumSamples=info["samples"],
                ExtensionData=65535, StreamAwbPortNo=65535, StreamAwbId=65535)
    rows = {"CueTable": [cue], "CueNameTable": [{"CueName": CUE, "CueIndex": 0}],
            "SequenceTable": [seq], "TrackTable": [track], "SynthTable": [synth],
            "TrackEventTable": [{"Command": bytes.fromhex("07d00400020000000000")}],
            "WaveformTable": [wave]}
    top = row_copy(native, 0)
    top.update({field: rebuild_utf(native.child(field), values, compact_blobs=True)
                for field, values in rows.items()})
    top.update(Name=BANK_NAME, AcbGuid=hashlib.sha256(CUE.encode() + audio).digest()[:16],
               AwbFile=memory_awb([(0, audio)]))
    for field in ("StreamAwbHash", "StreamAwbTocWorkOld", "StreamAwbTocWork_Old",
                  "StreamAwbTocWork", "StreamAwbAfs2Header"):
        if field in top:
            top[field] = b""
    result = rebuild_utf(native, [top], compact_blobs=True)
    verify_bank(result, audio, native)
    return result


def verify_bank(blob: bytes, audio: bytes, native: Utf | None = None) -> None:
    info, top = adx_info(audio), Utf(blob)
    if not 1000 < len(blob) <= MAX_BANK or top.rows[0]["Name"] != BANK_NAME:
        raise ValueError("custom bank bound/identity differs")
    if top.child("CueNameTable").rows != [{"CueName": CUE, "CueIndex": 0}]:
        raise ValueError("custom cue identity differs")
    if native and (top.rows[0]["Version"] != native.rows[0]["Version"] or
                   top.blob(0, "AcfMd5Hash") != native.blob(0, "AcfMd5Hash")):
        raise ValueError("custom bank changed native schema/ACF")
    if (top.child("SequenceTable").rows[0]["CommandIndex"] != 5 or
            len(top.child("SeqCommandTable").blob(5, "Command")) != 30 or
            digest(top.child("SeqCommandTable").blob(5, "Command")) != NATIVE_COMMAND_SHA or
            digest(top.blob(0, "StringValueTable")) != NATIVE_STRINGS_SHA):
        raise ValueError("custom cue discarded native music routing")
    if native and (top.blob(0, "SeqCommandTable") != native.blob(0, "SeqCommandTable") or
                   top.blob(0, "StringValueTable") != native.blob(0, "StringValueTable")):
        raise ValueError("custom cue changed native music command/string tables")
    fields = ("CueTable", "SequenceTable", "TrackTable", "TrackEventTable",
              "SynthTable", "WaveformTable")
    if any(len(top.child(field).rows) != 1 for field in fields):
        raise ValueError("custom graph is not one-to-one")
    cue, seq, track, event, synth, wave = (top.child(f) for f in fields)
    w = wave.rows[0]
    if (cue.rows[0]["ReferenceType"] != 3 or cue.rows[0]["ReferenceIndex"] or
            seq.rows[0]["NumTracks"] != 1 or seq.blob(0, "TrackIndex") != b"\0\0" or
            track.rows[0]["EventIndex"] or
            event.blob(0, "Command") != bytes.fromhex("07d00400020000000000") or
            synth.blob(0, "ReferenceItems") != b"\0\x01\0\0" or
            w != dict(MemoryAwbId=0, EncodeType=0, Streaming=0,
                      NumChannels=info["channels"], LoopFlag=1,
                      SamplingRate=info["sample_rate"], NumSamples=info["samples"],
                      ExtensionData=65535, StreamAwbPortNo=65535, StreamAwbId=65535)):
        raise ValueError("custom bank graph/codec differs")
    awb = top.blob(0, "AwbFile")
    if awb[:16] != struct.pack("<4s4BIHH", b"AFS2", 2, 4, 2, 0, 1, 32, 0):
        raise ValueError("custom AWB index differs")
    ident = struct.unpack_from("<H", awb, 16)[0]
    start, end = struct.unpack_from("<II", awb, 18)
    if ident or end != len(awb) or awb[(start + 31) & ~31:end] != audio:
        raise ValueError("custom recording roundtrip differs")


def catalog(blob: bytes, audio: bytes) -> str:
    info = adx_info(audio)
    return f'''/* Generated metadata only; the user recording remains ignored. */
#ifndef PESNX_TROPHY_AUDIO_CATALOG_H
#define PESNX_TROPHY_AUDIO_CATALOG_H
#define TROPHY_AUDIO_ASSET "{ASSET}"
#define TROPHY_AUDIO_CUE "{CUE}"
#define TROPHY_AUDIO_ENCODE_TYPE 0u
#define TROPHY_AUDIO_BYTES {len(blob)}u
#define TROPHY_AUDIO_FNV UINT64_C(0x{fnv64(blob):016x})
#define TROPHY_AUDIO_HEADER_BYTES {info["header_bytes"]}u
#define TROPHY_AUDIO_HEADER_FNV UINT64_C(0x{fnv64(audio[:info["header_bytes"]]):016x})
#endif
'''


def stage(source: Path, obb: Path, output: Path, ffmpeg: Path) -> dict:
    output = output.resolve()
    if (output.drive.upper() != "D:" or not output.is_relative_to(ROOT / "local-debug")
            or output.exists()):
        raise ValueError("use a new ignored local-debug directory on D")
    original = source.read_bytes()
    if not 1 <= len(original) <= MAX_BANK:
        raise ValueError("user recording outside bounded input")
    output.mkdir(parents=True)
    encoded = output / "encoded.adx"
    command = [str(ffmpeg), "-nostdin", "-v", "error", "-xerror", "-i", str(source),
               "-map", "0:a:0", "-vn", "-c:a", "adpcm_adx", "-f", "adx", str(encoded)]
    result = subprocess.run(command, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError("full recording encode failed: " + result.stderr.decode(errors="replace")[:600])
    raw = encoded.read_bytes()
    audio, footer = remove_partial_footer(raw)
    encoded.write_bytes(audio)
    info = adx_info(audio)
    decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror", "-i",
                              str(encoded), "-f", "s16le", "-"], capture_output=True, timeout=120)
    if decoded.returncode or len(decoded.stdout) != info["samples"] * info["channels"] * 2:
        raise ValueError("full encoded recording decode/sample check failed")
    supplied_pcm = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror", "-i",
                                   str(source), "-map", "0:a:0", "-vn", "-f", "s16le", "-"],
                                  capture_output=True, timeout=120)
    if supplied_pcm.returncode or len(supplied_pcm.stdout) != len(decoded.stdout):
        raise ValueError("encoded samples differ from the full supplied recording")
    native = mobile_bank(obb)
    blob = build_bank(native, audio)
    target = output / ASSET
    target.parent.mkdir()
    target.write_bytes(blob)
    (output / "trophy_audio_catalog.h").write_text(catalog(blob, audio), encoding="ascii", newline="\n")
    if source.read_bytes() != original:
        raise ValueError("supplied original changed during staging")
    report = {"schema": "PESNX_TROPHY_AUDIO_V89", "status": "staged_decode_verified",
              "source_path": str(source.resolve()), "source_bytes": len(original),
              "source_sha256": digest(original), "source_mutated": False,
              "conversion": "full recording, original sample rate/channels, no gain/trim/resample",
              "codec": "ADX", "codec_info": info, "encoded_bytes": len(audio),
              "encoded_sha256": digest(audio), "encoder_output_sha256": digest(raw),
              "removed_terminal_footer_hex": footer.hex(), "removed_audio_frames": 0,
              "pcm_s16le_bytes": len(decoded.stdout), "pcm_s16le_sha256": digest(decoded.stdout),
              "source_pcm_s16le_bytes": len(supplied_pcm.stdout),
              "source_pcm_s16le_sha256": digest(supplied_pcm.stdout),
              "full_desktop_decode_exit_code": 0,
              "mobile_template_sha256": digest(native), "mobile_acf_preserved": True,
              "native_music_sequence_command_index": 5,
              "native_music_command_bytes": 30, "native_music_command_sha256": NATIVE_COMMAND_SHA,
              "native_music_string_table_sha256": NATIVE_STRINGS_SHA,
              "native_music_routing_preserved": True, "global_gain_or_playlist_changed": False,
              "runtime_asset": ASSET, "runtime_cue": CUE,
              "bank_bytes": len(blob), "bank_sha256": digest(blob),
              "bank_fnv64": f"{fnv64(blob):016x}", "loop": False,
              "native_codec_validation": "separate bounded original-ELF probe required",
              "device_audio_accepted": False, "runtime_installed": False}
    (output / "AUDIO-REPORT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mobile-obb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.source, args.mobile_obb, args.output, args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
