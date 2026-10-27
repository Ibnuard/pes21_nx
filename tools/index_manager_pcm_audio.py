#!/usr/bin/env python3
"""Index exact reviewed v96 PCM ranges; emits metadata, never game recordings."""
import argparse
import hashlib
import io
from pathlib import Path
import struct
import wave

from stage_indonesia_commentary import Utf
from stage_manager_league_audio import ROLES, awb_recording

BANK_SHA = "ffc8f544530e49a54de2558630ba584c96ff9d5016e2969c4c2d77befe4b7b50"


def catalog(bank):
    if hashlib.sha256(bank).hexdigest() != BANK_SHA:
        raise ValueError("exact individually reviewed v96 PCM bank required")
    top = Utf(bank)
    waveforms = top.child("WaveformTable")
    cues = top.child("CueNameTable")
    entries = {}
    for cue in cues.rows:
        # Native cue names are alphabetically sorted; their row ordinal is not
        # a waveform index. The sealed graph binds CueIndex to this one-track
        # sequence/synth/waveform chain.
        i = cue["CueIndex"]
        sequence = top.child("CueTable").rows[i]
        if (sequence["ReferenceType"], sequence["ReferenceIndex"],
                waveforms.rows[i]["MemoryAwbId"]) != (3, i, i):
            raise ValueError("sealed cue/waveform graph differs")
        role = cue["CueName"].removeprefix("FNX_ML96_").lower()
        recording = awb_recording(top.blob(0, "AwbFile"), i)
        offset = bank.find(recording)
        if offset < 0 or bank.find(recording, offset + 1) >= 0:
            raise ValueError("recording is not uniquely located")
        with wave.open(io.BytesIO(recording), "rb") as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(),
                    source.getcomptype()) != (2, 2, 48000, "NONE"):
                raise ValueError("unexpected PCM format")
            frames = source.getnframes()
            pcm = source.readframes(frames)
        if (recording[12:16] != b"fmt " or recording[36:40] != b"data" or
                recording[44:] != pcm or len(pcm) != frames * 4 or
                waveforms.rows[i]["NumSamples"] != frames or offset % 4):
            raise ValueError("unexpected PCM layout")
        entries[role] = (offset, frames)
    lines = ["/* Exact reviewed v96 PCM locations only; no recordings embedded. */",
        "#ifndef PESNX_MANAGER_LEAGUE_PCM_CATALOG_H",
        "#define PESNX_MANAGER_LEAGUE_PCM_CATALOG_H",
        "typedef struct MlaPcmClip { uint32_t wave_offset, frames; } MlaPcmClip;",
        "static const MlaPcmClip mla_pcm_clips[MLA_CLIP_COUNT] = {"]
    for role in ROLES:
        offset, frames = entries.get(role, (0, 0))
        lines.append(f"  {{{offset}u, {frames}u}}, /* {role} */")
    return "\n".join(lines + ["};", "#endif", ""])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(catalog(args.bank.read_bytes()), encoding="utf-8")


if __name__ == "__main__":
    main()
