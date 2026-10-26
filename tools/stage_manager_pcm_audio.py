#!/usr/bin/env python3
"""Decode the individually reviewed Manager recordings to native stereo PCM16.

The sealed v94 bank/review are inputs, never rewritten. Decode at the original
48kHz, remove declared HCA encoder delay/tail only, duplicate mono channels,
and apply the existing cue gain before PCM16 quantization (avoids clipping HCA
overshoot). No resampling, normalization, new speech, category or playlist edit.
Only generated metadata is public; every recording stays ignored/local.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import wave

import numpy as np
from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import rebuild_utf
from stage_manager_league_audio import awb_recording, ROLES
from stage_trophy_music import row_copy

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "84bade692c7e577fecacb769988d4be9f2b2dcba08cbe99cc6ee207a5e242318"
REVIEW_SHA = "364cf95bbd28b788236283af4526f5e7a7c9686628988a613cdacbb4fccba3f2"
ASSET = "Audio/manager-league-pcm-v96.acb"
MAX_BANK = 16 * 1024 * 1024


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def pcm_wave(pcm):
    output = io.BytesIO()
    with wave.open(output, "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(pcm)
    return output.getvalue()


def stage(blob, review, report, ffmpeg, out):
    if digest(blob) != SOURCE_SHA or digest(review) != REVIEW_SHA:
        raise ValueError("sealed Manager bank/individual semantic review differs")
    semantic = json.loads(review)
    if semantic["status"] != "individual_transcription_reviewed":
        raise ValueError("semantic review missing")
    native = Utf(blob)
    table = native.child("WaveformTable")
    clips, recordings = [], []
    for i, spec in enumerate(semantic["clips"]):
        old = report["clips"][i]
        audio = awb_recording(native.blob(0, "AwbFile"), i)
        w = table.rows[i]
        if spec["role"] != old["role"] or digest(audio) != spec["audio_sha256"]:
            raise ValueError("review does not bind source recording")
        if w["SamplingRate"] != 48000 or w["NumChannels"] not in (1, 2):
            raise ValueError("unreviewed original format")
        path = out / (spec["role"] + ".hca")
        path.write_bytes(audio)
        ran = subprocess.run([str(ffmpeg), "-nostdin", "-v", "error", "-xerror", "-i", str(path),
                              "-f", "f32le", "-"], capture_output=True, timeout=45)
        path.unlink()
        if ran.returncode:
            raise ValueError("full source decode failed: " + ran.stderr.decode(errors="replace"))
        frames, leading, trailing = struct.unpack_from(">IHH", audio, 16)
        samples = np.frombuffer(ran.stdout, "<f4").reshape(-1, w["NumChannels"])
        if len(samples) != frames * 1024 or not np.all(np.isfinite(samples)):
            raise ValueError("full HCA decode/block count differs")
        # ACB NumSamples is the native playback length. The looped bed's ACB
        # ends 256 samples before its HCA tail; preserve that declared boundary.
        end = leading + w["NumSamples"]
        if end > len(samples) - trailing:
            raise ValueError("declared source sample window is out of bounds")
        playable = samples[leading:end]
        if playable.shape[1] == 1:
            playable = np.repeat(playable, 2, axis=1)
        gained = playable.astype(np.float64) * old["gain"]
        quantized = np.rint(gained * 32768)
        if np.any(quantized < -32768) or np.any(quantized > 32767):
            raise ValueError("cue gain does not provide PCM headroom")
        pcm = quantized.astype("<i2").tobytes()
        recording = pcm_wave(pcm)
        (out / (spec["role"] + ".wav")).write_bytes(recording)
        recordings.append((i, recording))
        clips.append({**spec, "duration_ms": (len(playable) * 1000 + 47999) // 48000,
            "samples": len(playable), "source_channels": w["NumChannels"],
            "original_decoded_frames": len(samples), "encoder_leading_frames": leading,
            "encoder_trailing_frames": trailing, "native_tail_frames": len(samples) - end,
            "source_float_pcm_sha256": digest(ran.stdout), "gain_baked": old["gain"],
            "pcm_sha256": digest(pcm), "wave_sha256": digest(recording),
            "pcm_peak": float(np.max(np.abs(quantized)) / 32768),
            "pcm_quantization_error_max_lsb": float(np.max(np.abs(quantized - gained * 32768))),
            "mono_duplicated_without_attenuation": w["NumChannels"] == 1})
    top = row_copy(native, 0)
    for field in ("WaveformTable", "CueTable", "CueNameTable", "SeqCommandTable"):
        rows = []
        for i, clip in enumerate(clips):
            row = row_copy(native.child(field), i)
            if field == "WaveformTable":
                row.update(EncodeType=20, NumChannels=2, LoopFlag=1, ExtensionData=65535)
            elif field == "CueTable":
                row["Length"] = clip["duration_ms"]
            elif field == "CueNameTable":
                row["CueName"] = row["CueName"].replace("FNX_ML94_", "FNX_ML96_")
            else:
                # Preserve v95's explicit native MasterOut0/BUS8=1 route;
                # PCM/pool is the candidate change. Gain was applied once.
                row["Command"] = struct.pack(">HBfHBHHHBHH", 0x44, 4, 1.0,
                                               0x6f, 4, 1, 0, 0x6f, 4, 2, 10000)
            rows.append(row)
        top[field] = rebuild_utf(native.child(field), rows, compact_blobs=True)
    top.update(Name="FNX_MANAGER_LEAGUE_PCM_V96", AwbFile=memory_awb(recordings),
               AcbGuid=hashlib.sha256(b"FNX_ML96_PCM" + blob).digest()[:16])
    bank = rebuild_utf(native, [top], compact_blobs=True)
    if len(bank) > MAX_BANK:
        raise ValueError("PCM bank exceeds bounded memory")
    current = Utf(bank)
    for field in ("SequenceTable", "TrackTable", "SynthTable", "TrackEventTable",
                  "StringValueTable", "AcfMd5Hash"):
        if current.blob(0, field) != native.blob(0, field):
            raise ValueError("protected graph/schema/ACF changed: " + field)
    for i, recording in recordings:
        if awb_recording(current.blob(0, "AwbFile"), i) != recording:
            raise ValueError("PCM memory AWB roundtrip differs")
    lines = ["/* Generated metadata only; reviewed recordings remain ignored. */",
        "#ifndef PESNX_MANAGER_LEAGUE_AUDIO_CATALOG_H", "#define PESNX_MANAGER_LEAGUE_AUDIO_CATALOG_H",
        f'#define MLA_ASSET "{ASSET}"', f"#define MLA_BANK_BYTES {len(bank)}u",
        f"#define MLA_BANK_MAX_BYTES {MAX_BANK}u", f"#define MLA_BANK_FNV UINT64_C(0x{fnv64(bank):016x})",
        "typedef struct MlaClip { const char *cue; uint32_t duration; uint64_t header_fnv; } MlaClip;",
        "static const MlaClip mla_clips[MLA_CLIP_COUNT] = {"]
    by_role = {clip["role"]: clip for clip in clips}
    for role in ROLES:
        c = by_role.get(role)
        lines.append(f'  {{"FNX_ML96_{role.upper()}", {c["duration_ms"]}u, 0}},' if c else "  {NULL, 0u, 0},")
    header = "\n".join(lines + ["};", "#endif", ""])
    target = out / ASSET
    target.parent.mkdir(parents=True)
    target.write_bytes(bank)
    (out / "manager_league_audio_catalog.h").write_text(header)
    result = {"schema": "PESNX_MANAGER_PCM_V96", "asset": ASSET,
        "bank_bytes": len(bank), "bank_sha256": digest(bank), "bank_fnv64": f"{fnv64(bank):016x}",
        "source_bank_sha256": SOURCE_SHA, "semantic_review_sha256": REVIEW_SHA,
        "clips": clips, "native_format": "PCM16_STEREO_48000", "no_resampling": True,
        "no_lossy_reencoding": True, "cue_gain_baked_once": True,
        "native_pool_voices": 6, "logical_roles": 3, "global_gain_or_playlist_changes": False,
        "device_audibility_verified": False, "native_decoder_proof_required": True}
    (out / "AUDIO-REPORT.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--review", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--ffmpeg", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if not out.is_relative_to(ROOT / "local-debug") or out.exists():
        p.error("choose a new ignored local-debug directory")
    out.mkdir(parents=True)
    result = stage(a.input.read_bytes(), a.review.read_bytes(), json.loads(a.report.read_text()), a.ffmpeg, out)
    print(json.dumps({k: v for k, v in result.items() if k != "clips"}, indent=2))


if __name__ == "__main__":
    main()
