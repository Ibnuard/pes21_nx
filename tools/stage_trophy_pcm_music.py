#!/usr/bin/env python3
"""Stage the full supplied trophy clip as quiet native PCM16, without ADX loss.

Only this detached cue is attenuated. Original recordings, native routing,
other banks, category gains and playlists are not modified.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import wave

from entrance_scene_canary import digest
from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import rebuild_utf
from stage_trophy_music import ROOT, mobile_bank, row_copy, MOBILE_ACB_SHA
from stage_custom_trophy_music import NATIVE_COMMAND_SHA, NATIVE_STRINGS_SHA

ASSET = "Audio/trophy-user-pcm-v90.acb"
CUE = "FNX_TROPHY_USER_PCM_V90"
BANK_NAME = CUE
MAX_BANK = 4 * 1024 * 1024
GAIN_DB = -12.0
GAIN = 10.0 ** (GAIN_DB / 20.0)


def pcm_wave_info(audio: bytes) -> dict:
    if len(audio) < 44 or audio[:12] != b"RIFF" + struct.pack("<I", len(audio) - 8) + b"WAVE":
        raise ValueError("not a bounded RIFF WAVE recording")
    with wave.open(io.BytesIO(audio), "rb") as recording:
        channels, width, rate, samples = (recording.getnchannels(), recording.getsampwidth(),
                                         recording.getframerate(), recording.getnframes())
        if (recording.getcomptype() != "NONE" or channels != 2 or width != 2 or rate != 44100
                or not samples or len(audio) != 44 + samples * channels * width):
            raise ValueError("unreviewed native PCM format or sample bounds")
        pcm = recording.readframes(samples)
    return {"channels": channels, "sample_rate": rate, "samples": samples,
            "bits_per_sample": 16, "header_bytes": 44, "pcm_bytes": len(pcm),
            "duration_seconds": samples / rate, "cipher": 0, "lossy_codec": False}


def attenuate_pcm(pcm: bytes) -> bytes:
    if len(pcm) % 4:
        raise ValueError("stereo PCM frames are incomplete")
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    # Round once to PCM16. No clipping, compressor, normalization or dither;
    # the original remains exact and the maximum quantization error is 0.5 LSB.
    result = array("h", (round(sample * GAIN) for sample in samples))
    if sys.byteorder != "little":
        result.byteswap()
    return result.tobytes()


def wave_bytes(pcm: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(2)
        recording.setsampwidth(2)
        recording.setframerate(44100)
        recording.writeframes(pcm)
    result = output.getvalue()
    pcm_wave_info(result)
    return result


def routing(top: Utf) -> dict:
    command = top.child("SeqCommandTable").blob(5, "Command")
    strings = [row["StringValue"] for row in top.child("StringValueTable").rows]
    at, sends, categories = 0, [], []
    while at < len(command):
        if at + 3 > len(command):
            raise ValueError("incomplete native music command")
        opcode, count = struct.unpack_from(">HB", command, at)
        value = command[at + 3:at + 3 + count]
        if len(value) != count:
            raise ValueError("native music command bounds differ")
        if opcode == 0x6F:
            ident, level = struct.unpack(">HH", value)
            sends.append({"string_index": ident, "bus_name": strings[ident],
                          "level_10000": level, "gain": level / 10000.0})
        elif opcode == 0x41:
            categories.extend(struct.unpack(">" + "I" * (count // 4), value))
        at += 3 + count
    if [(row["bus_name"], row["level_10000"]) for row in sends] != [("MasterOut", 0), ("BUS8", 10000)]:
        raise ValueError("native music bus route differs")
    return {"native_sequence_command_index": 5, "native_command_sha256": digest(command),
            "category_ids": categories, "bus_sends": sends,
            "parallel_full_volume_master_and_bus8_sends": False}


def build_bank(mobile: bytes, audio: bytes) -> bytes:
    if digest(mobile) != MOBILE_ACB_SHA:
        raise ValueError("native music template differs")
    info, native = pcm_wave_info(audio), Utf(mobile)
    cue = row_copy(native.child("CueTable"), 5)
    cue.update(CueId=0, ReferenceType=3, ReferenceIndex=0, Length=0xFFFFFFFF)
    seq = row_copy(native.child("SequenceTable"), 5)
    seq.update(NumTracks=1, TrackIndex=b"\0\0", Type=0, ControlWorkArea1=0, ControlWorkArea2=0)
    track = row_copy(native.child("TrackTable"), 7)
    track.update(EventIndex=0, CommandIndex=65535, LocalAisacs=b"")
    synth = row_copy(native.child("SynthTable"), 7)
    synth.update(ReferenceItems=b"\0\x01\0\0", CommandIndex=65535,
                 ControlWorkArea1=0, ControlWorkArea2=0, LocalAisacs=b"")
    waveform = row_copy(native.child("WaveformTable"), 0)
    # Original ACB waveform reader maps EncodeType20 to native format5 (WAVE).
    # The original WAVE analyzer/create/decode path is independently executed.
    waveform.update(MemoryAwbId=0, EncodeType=20, Streaming=0, NumChannels=2,
                    LoopFlag=1, SamplingRate=info["sample_rate"], NumSamples=info["samples"],
                    ExtensionData=65535, StreamAwbPortNo=65535, StreamAwbId=65535)
    rows = {"CueTable": [cue], "CueNameTable": [{"CueName": CUE, "CueIndex": 0}],
            "SequenceTable": [seq], "TrackTable": [track], "SynthTable": [synth],
            "TrackEventTable": [{"Command": bytes.fromhex("07d00400020000000000")}],
            "WaveformTable": [waveform]}
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
    info, top = pcm_wave_info(audio), Utf(blob)
    if not 1000 < len(blob) <= MAX_BANK or top.rows[0]["Name"] != BANK_NAME:
        raise ValueError("PCM bank bound/identity differs")
    if top.child("CueNameTable").rows != [{"CueName": CUE, "CueIndex": 0}]:
        raise ValueError("PCM cue identity differs")
    if (top.child("SequenceTable").rows[0]["CommandIndex"] != 5 or
            digest(top.child("SeqCommandTable").blob(5, "Command")) != NATIVE_COMMAND_SHA or
            digest(top.blob(0, "StringValueTable")) != NATIVE_STRINGS_SHA):
        raise ValueError("PCM cue changed native music routing")
    routing(top)
    if native and (top.rows[0]["Version"] != native.rows[0]["Version"] or
                   top.blob(0, "AcfMd5Hash") != native.blob(0, "AcfMd5Hash") or
                   top.blob(0, "SeqCommandTable") != native.blob(0, "SeqCommandTable") or
                   top.blob(0, "StringValueTable") != native.blob(0, "StringValueTable")):
        raise ValueError("PCM cue changed native schema/ACF/routing tables")
    fields = ("CueTable", "SequenceTable", "TrackTable", "TrackEventTable", "SynthTable", "WaveformTable")
    if any(len(top.child(field).rows) != 1 for field in fields):
        raise ValueError("PCM graph is not one-to-one")
    cue, seq, track, event, synth, waveform = (top.child(field) for field in fields)
    if (cue.rows[0]["ReferenceType"] != 3 or cue.rows[0]["ReferenceIndex"] != 0 or
            seq.rows[0]["NumTracks"] != 1 or seq.blob(0, "TrackIndex") != b"\0\0" or
            track.rows[0]["EventIndex"] != 0 or
            event.blob(0, "Command") != bytes.fromhex("07d00400020000000000") or
            synth.blob(0, "ReferenceItems") != b"\0\x01\0\0" or
            waveform.rows[0] != dict(MemoryAwbId=0, EncodeType=20, Streaming=0, NumChannels=2,
                                    LoopFlag=1, SamplingRate=44100, NumSamples=info["samples"],
                                    ExtensionData=65535, StreamAwbPortNo=65535, StreamAwbId=65535)):
        raise ValueError("PCM graph/format differs")
    awb = top.blob(0, "AwbFile")
    if awb[:16] != struct.pack("<4s4BIHH", b"AFS2", 2, 4, 2, 0, 1, 32, 0):
        raise ValueError("PCM AWB bounds differ")
    ident = struct.unpack_from("<H", awb, 16)[0]
    start, end = struct.unpack_from("<II", awb, 18)
    if ident or end != len(awb) or awb[(start + 31) & ~31:end] != audio:
        raise ValueError("PCM recording roundtrip differs")


def catalog(blob: bytes, audio: bytes) -> str:
    return f'''/* Generated metadata only; the user recording remains ignored. */
#ifndef PESNX_TROPHY_AUDIO_CATALOG_H
#define PESNX_TROPHY_AUDIO_CATALOG_H
#define TROPHY_AUDIO_ASSET "{ASSET}"
#define TROPHY_AUDIO_CUE "{CUE}"
#define TROPHY_AUDIO_ENCODE_TYPE 20u
#define TROPHY_AUDIO_MAX_BANK_BYTES {MAX_BANK}u
#define TROPHY_AUDIO_GAIN_DB_X100 (-1200)
#define TROPHY_AUDIO_BYTES {len(blob)}u
#define TROPHY_AUDIO_FNV UINT64_C(0x{fnv64(blob):016x})
#define TROPHY_AUDIO_HEADER_BYTES 44u
#define TROPHY_AUDIO_HEADER_FNV UINT64_C(0x{fnv64(audio[:44]):016x})
#endif
'''


def stage(source: Path, obb: Path, output: Path, ffmpeg: Path) -> dict:
    output = output.resolve()
    if output.drive.upper() != "D:" or not output.is_relative_to(ROOT / "local-debug") or output.exists():
        raise ValueError("use a new ignored local-debug directory on D")
    original = source.read_bytes()
    source_sha = digest(original)
    if source_sha != "3655a2a1fbb297efb34d4629547e3943326c5ed5e1ee23ab8f88cbb02d6603ff":
        raise ValueError("supplied clip identity differs from the reviewed source")
    decoded = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror", "-i", str(source),
                              "-map", "0:a:0", "-vn", "-f", "s16le", "-"],
                             capture_output=True, timeout=120)
    if decoded.returncode or len(decoded.stdout) != 688128 * 4:
        raise ValueError("full supplied recording decode/sample count differs")
    pcm = attenuate_pcm(decoded.stdout)
    audio = wave_bytes(pcm)
    native = mobile_bank(obb)
    blob = build_bank(native, audio)
    output.mkdir(parents=True)
    recording = output / "trophy-user-quiet.wav"
    recording.write_bytes(audio)
    independent = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror", "-i",
                                  str(recording), "-f", "s16le", "-"], capture_output=True, timeout=120)
    if independent.returncode or independent.stdout != pcm:
        raise ValueError("independent full PCM decode changed samples")
    target = output / ASSET
    target.parent.mkdir()
    target.write_bytes(blob)
    (output / "trophy_audio_catalog.h").write_text(catalog(blob, audio), encoding="ascii", newline="\n")
    if source.read_bytes() != original:
        raise ValueError("supplied original changed during staging")
    values = struct.unpack("<" + "h" * (len(pcm) // 2), pcm)
    peak = max(abs(value) for value in values) / 32768.0
    rms = math.sqrt(sum((value / 32768.0) ** 2 for value in values) / len(values))
    report = {"schema": "PESNX_TROPHY_AUDIO_V90", "status": "staged_independent_pcm_verified",
              "source_path": str(source.resolve()), "source_bytes": len(original), "source_sha256": source_sha,
              "source_mutated": False, "source_pcm_s16le_sha256": digest(decoded.stdout),
              "source_pcm_bytes": len(decoded.stdout), "codec": "WAVE_PCM16", "codec_info": pcm_wave_info(audio),
              "cue_gain_db": GAIN_DB, "cue_gain_linear": GAIN,
              "gain_applied_before_playback": True, "normalization_or_compression": False,
              "trimmed_frames": 0, "downmixed_or_resampled": False, "lossy_transcode": False,
              "pcm_s16le_bytes": len(pcm), "pcm_s16le_sha256": digest(pcm),
              "staged_pcm_peak": peak, "staged_pcm_rms": rms, "staged_pcm_rms_dbfs": 20 * math.log10(rms),
              "staged_pcm_clipped_samples": sum(abs(value) >= 32767 for value in values),
              "wave_bytes": len(audio), "wave_sha256": digest(audio),
              "mobile_template_sha256": digest(native), "native_routing": routing(Utf(blob)),
              "mobile_acf_preserved": True, "global_gain_or_playlist_changed": False,
              "runtime_asset": ASSET, "runtime_cue": CUE, "bank_bytes": len(blob),
              "bank_max_bytes": MAX_BANK, "bank_sha256": digest(blob), "bank_fnv64": f"{fnv64(blob):016x}",
              "independent_full_pcm_roundtrip_exact": True, "loop": False,
              "native_codec_validation": "separate bounded original-ELF full decode required",
              "device_v89_music_audible": True, "device_v90_audio_accepted": False, "runtime_installed": False}
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
