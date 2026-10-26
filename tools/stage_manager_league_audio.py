#!/usr/bin/env python3
"""Stage a small own-source Manager League HCA bank; never modify source CPKs.

Numeric commentary labels are not semantic evidence. The explicit local review
file binds each individually transcribed recording hash, role and cue label.
Only metadata/catalog source may be public; recordings remain under local-debug.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

from entrance_scene_canary import Cpk, digest
from stage_indonesia_commentary import Utf, fnv64, memory_awb, read_awb_wave
from stage_player_commentary import rebuild_utf
from stage_trophy_music import mobile_bank, row_copy

ROOT = Path(__file__).resolve().parents[1]
ASSET = "Audio/manager-league-v94.acb"
MAX_BANK = 4 * 1024 * 1024
ROLES = ["bed", "ball_pass", "ball_shot", "crowd_goal", "shot", "goal", "foul",
         "yellow", "substitution", "offside", "corner", "save", "half_time",
         "full_time", "kickoff"]
GAINS = {"bed": .10, "ball_pass": .30, "ball_shot": .30, "crowd_goal": .18}


def awb_recording(awb: bytes, ident: int) -> bytes:
    if len(awb) < 16 or awb[:4] != b"AFS2":
        raise ValueError("missing memory AWB")
    width, iw = awb[5:7]
    count, align, key = struct.unpack_from("<IHH", awb, 8)
    if width not in (2, 4) or iw != 2 or not align or key or count > 65535:
        raise ValueError("unreviewed memory AWB")
    needed = 16 + count * 2 + (count + 1) * width
    if needed > len(awb):
        raise ValueError("truncated memory AWB")
    ids = struct.unpack_from("<" + "H" * count, awb, 16)
    offsets = [int.from_bytes(awb[16+count*2+i*width:16+count*2+(i+1)*width], "little")
               for i in range(count + 1)]
    if len(set(ids)) != count or sorted(offsets) != offsets or ids.count(ident) != 1:
        raise ValueError("memory AWB identity/bounds differ")
    at = ids.index(ident)
    start, end = (offsets[at] + align - 1) // align * align, offsets[at+1]
    if not needed <= start < end <= len(awb):
        raise ValueError("memory AWB recording outside bank")
    return awb[start:end]


def source_clip(cpk: Cpk, spec: dict) -> dict:
    blob = cpk.read(spec["member"])
    if digest(blob) != spec["acb_sha256"]:
        raise ValueError("reviewed source ACB differs")
    top = Utf(blob)
    names = [r for r in top.child("CueNameTable").rows if r["CueName"] == spec["cue"]]
    if len(names) != 1:
        raise ValueError("source cue absent/ambiguous")
    cue = top.child("CueTable").rows[names[0]["CueIndex"]]
    wi = spec["wave_index"]
    if cue["ReferenceType"] == 1:
        if cue["ReferenceIndex"] != wi:
            raise ValueError("reviewed direct waveform edge differs")
    else:
        # SFX/cheer selections include a full inspected path from the named cue.
        seq, track, event, synth = (top.child(f) for f in (
            "SequenceTable", "TrackTable", "TrackEventTable", "SynthTable"))
        si = cue["ReferenceIndex"]
        ti, *chain = spec["path"]
        indices = seq.blob(si, "TrackIndex")[:seq.rows[si]["NumTracks"]*2]
        if cue["ReferenceType"] != 3 or struct.pack(">H", ti) not in [indices[i:i+2] for i in range(0, len(indices), 2)]:
            raise ValueError("reviewed source sequence/track edge differs")
        command = event.blob(track.rows[ti]["EventIndex"], "Command")
        reference = bytes.fromhex("07d0040002") + struct.pack(">H", chain[0])
        if reference not in command:
            raise ValueError("reviewed source track/synth edge differs")
        for at, index in enumerate(chain):
            target_type, target = (7, chain[at+1]) if at+1 < len(chain) else (1, wi)
            if synth.blob(index, "ReferenceItems") != struct.pack(">HH", target_type, target):
                raise ValueError("reviewed source nested synth/wave edge differs")
    waveform = row_copy(top.child("WaveformTable"), wi)
    if waveform["EncodeType"] != 2 or waveform["NumChannels"] not in (1, 2):
        raise ValueError("only original mono/stereo HCA is admitted")
    if waveform["Streaming"]:
        awb = spec["member"].replace("/acb/", "/awb/").replace(".acb", ".awb")
        audio = read_awb_wave(cpk.path, cpk.index[awb], cpk.base, waveform["StreamAwbId"])
    else:
        audio = awb_recording(top.blob(0, "AwbFile"), waveform["MemoryAwbId"])
    if digest(audio) != spec["audio_sha256"]:
        raise ValueError("individually reviewed recording differs")
    if audio[:4] != b"HCA\0" or b"ciph\0\0" not in audio[:96] or len(audio) < 96:
        raise ValueError("source is not an admitted original plaintext HCA")
    extension, extension_schema = None, None
    if waveform["LoopFlag"] == 2:
        extension_schema = top.child("WaveformExtensionDataTable").data
        extension = row_copy(Utf(extension_schema), waveform["ExtensionData"])
    duration = (waveform["NumSamples"] * 1000 + waveform["SamplingRate"]-1) // waveform["SamplingRate"]
    if not 0 < duration <= 30000:
        raise ValueError("selected recording exceeds finite 30-second bound")
    return {"spec": spec, "wave": waveform, "audio": audio, "extension": extension,
            "duration_ms": duration, "extension_schema": extension_schema}


def cue_command(gain: float) -> bytes:
    if not 0 < gain <= .65:
        raise ValueError("cue gain exceeds conservative headroom")
    # Native Mobile commands 0x44 (cue volume float) and 0x6f (bus send)
    # occur in the inspected native Movement/cheer/music banks. MasterOut index1
    # is kept from the Mobile music StringValueTable. No global/category writes.
    return struct.pack(">HBfHBHH", 0x44, 4, gain, 0x6f, 4, 1, 10000)


def build_bank(native_blob: bytes, clips: list[dict]) -> bytes:
    native = Utf(native_blob)
    if native.child("StringValueTable").rows[1] != {"StringValue": "MasterOut"}:
        raise ValueError("native MasterOut string binding differs")
    fields = ("CueTable", "CueNameTable", "SequenceTable", "TrackTable",
              "SynthTable", "TrackEventTable", "WaveformTable", "SeqCommandTable")
    rows = {field: [] for field in fields}
    extensions, waves = [], []
    for i, clip in enumerate(clips):
        role = clip["spec"]["role"]
        cue = row_copy(native.child("CueTable"), 5)
        cue.update(CueId=i, ReferenceType=3, ReferenceIndex=i,
                   Length=0xFFFFFFFF if clip["extension"] else clip["duration_ms"])
        seq = row_copy(native.child("SequenceTable"), 5)
        seq.update(NumTracks=1, TrackIndex=struct.pack(">H", i), Type=0,
                   CommandIndex=i, ControlWorkArea1=i, ControlWorkArea2=i,
                   LocalAisacs=b"", TrackValues=b"")
        track = row_copy(native.child("TrackTable"), 7)
        track.update(EventIndex=i, CommandIndex=65535, LocalAisacs=b"")
        synth = row_copy(native.child("SynthTable"), 7)
        synth.update(ReferenceItems=struct.pack(">HH", 1, i), CommandIndex=65535,
                     ControlWorkArea1=i, ControlWorkArea2=i, LocalAisacs=b"")
        w = row_copy(native.child("WaveformTable"), 0)
        w.update(clip["wave"])
        w.update(MemoryAwbId=i, Streaming=0, StreamAwbPortNo=65535, StreamAwbId=65535)
        if clip["extension"]:
            w["ExtensionData"] = len(extensions)
            extensions.append(clip["extension"])
        else:
            w["ExtensionData"] = 65535
        values = {"CueTable": cue, "CueNameTable": {"CueName": "FNX_ML94_"+role.upper(), "CueIndex": i},
                  "SequenceTable": seq, "TrackTable": track, "SynthTable": synth,
                  "TrackEventTable": {"Command": struct.pack(">HBHHHB", 2000, 4, 2, i, 0, 0)},
                  "WaveformTable": w, "SeqCommandTable": {"Command": cue_command(GAINS.get(role, .65))}}
        for field, value in values.items():
            rows[field].append(value)
        waves.append((i, clip["audio"]))
    rows["CueNameTable"].sort(key=lambda row: row["CueName"])
    top = row_copy(native, 0)
    for field, values in rows.items():
        top[field] = rebuild_utf(native.child(field), values, compact_blobs=True)
    if extensions:
        top["WaveformExtensionDataTable"] = rebuild_utf(
            Utf(next(c["extension_schema"] for c in clips if c["extension_schema"])),
            extensions, compact_blobs=True)
    top.update(Name="FNX_MANAGER_LEAGUE_V94", AcbGuid=hashlib.sha256(
        b"".join(clip["audio"] for clip in clips)).digest()[:16], AwbFile=memory_awb(waves))
    for field in ("StreamAwbHash", "StreamAwbTocWorkOld", "StreamAwbTocWork_Old",
                  "StreamAwbTocWork", "StreamAwbAfs2Header"):
        if field in top:
            top[field] = b""
    bank = rebuild_utf(native, [top], compact_blobs=True)
    verify_bank(bank, clips, native)
    return bank


def verify_bank(bank: bytes, clips: list[dict], native: Utf | None = None) -> None:
    if not 1000 < len(bank) <= MAX_BANK or not 4 <= len(clips) <= len(ROLES):
        raise ValueError("Manager bank envelope differs")
    top = Utf(bank)
    if top.rows[0]["Name"] != "FNX_MANAGER_LEAGUE_V94":
        raise ValueError("Manager bank identity differs")
    if native and (top.blob(0, "AcfMd5Hash") != native.blob(0, "AcfMd5Hash") or
                   top.rows[0]["Version"] != native.rows[0]["Version"] or
                   top.blob(0, "StringValueTable") != native.blob(0, "StringValueTable")):
        raise ValueError("native schema/ACF/string table differs")
    names = top.child("CueNameTable").rows
    if names != sorted(names, key=lambda row: row["CueName"]) or len(names) != len(clips):
        raise ValueError("cue lookup ordering/count differs")
    tables = {f: top.child(f) for f in ("CueTable", "SequenceTable", "TrackTable",
        "SynthTable", "TrackEventTable", "WaveformTable", "SeqCommandTable")}
    if any(len(table.rows) != len(clips) for table in tables.values()):
        raise ValueError("unrelated cue graph leaked into bank")
    for i, clip in enumerate(clips):
        role = clip["spec"]["role"]
        q, s, tr, sy, ev, w, cmd = (tables[f] for f in tables)
        if (q.rows[i]["ReferenceIndex"] != i or q.rows[i]["ReferenceType"] != 3 or
                q.rows[i]["Length"] != (0xFFFFFFFF if clip["extension"] else clip["duration_ms"]) or
                s.rows[i]["CommandIndex"] != i or s.rows[i]["NumTracks"] != 1 or
                s.blob(i, "TrackIndex") != struct.pack(">H", i) or
                tr.rows[i]["EventIndex"] != i or
                sy.blob(i, "ReferenceItems") != struct.pack(">HH", 1, i) or
                ev.blob(i, "Command") != struct.pack(">HBHHHB", 2000, 4, 2, i, 0, 0) or
                cmd.blob(i, "Command") != cue_command(GAINS.get(role, .65)) or
                w.rows[i]["MemoryAwbId"] != i or w.rows[i]["Streaming"] != 0 or
                w.rows[i]["NumSamples"] != clip["wave"]["NumSamples"] or
                w.rows[i]["LoopFlag"] != clip["wave"]["LoopFlag"] or
                awb_recording(top.blob(0, "AwbFile"), i) != clip["audio"]):
            raise ValueError("Manager graph/recording integrity differs")


def catalog(bank: bytes, clips: list[dict]) -> str:
    by_role = {c["spec"]["role"]: c for c in clips}
    lines = ["/* Generated metadata only; owned recordings remain ignored. */",
        "#ifndef PESNX_MANAGER_LEAGUE_AUDIO_CATALOG_H", "#define PESNX_MANAGER_LEAGUE_AUDIO_CATALOG_H",
        f'#define MLA_ASSET "{ASSET}"', f"#define MLA_BANK_BYTES {len(bank)}u",
        f"#define MLA_BANK_MAX_BYTES {MAX_BANK}u", f"#define MLA_BANK_FNV UINT64_C(0x{fnv64(bank):016x})",
        "typedef struct MlaClip { const char *cue; uint32_t duration; uint64_t header_fnv; } MlaClip;",
        "static const MlaClip mla_clips[MLA_CLIP_COUNT] = {"]
    for role in ROLES:
        c = by_role.get(role)
        lines.append(f'  {{"FNX_ML94_{role.upper()}", {c["duration_ms"]}u, UINT64_C(0x{fnv64(c["audio"][:96]):016x})}},' if c else "  {NULL, 0u, 0},")
    return "\n".join(lines + ["};", "#endif", ""])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review", type=Path, required=True)
    p.add_argument("--fl26-data", type=Path, required=True)
    p.add_argument("--mobile-obb", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if not out.is_relative_to(ROOT / "local-debug") or out.exists():
        p.error("choose a new ignored local-debug directory")
    review = json.loads(a.review.read_text(encoding="utf-8"))
    if review.get("status") != "individual_transcription_reviewed" or len({s["role"] for s in review["clips"]}) != len(review["clips"]):
        p.error("individual unique-role recording review is required")
    sources, clips = {}, []
    for spec in review["clips"]:
        if spec["role"] not in ROLES or not spec.get("meaning"):
            p.error("reviewed role/meaning is missing")
        source = sources.setdefault(spec["cpk"], Cpk(a.fl26_data/spec["cpk"]))
        clips.append(source_clip(source, spec))
    bank = build_bank(mobile_bank(a.mobile_obb), clips)
    (out/ASSET).parent.mkdir(parents=True)
    (out/ASSET).write_bytes(bank)
    (out/"manager_league_audio_catalog.h").write_text(catalog(bank, clips), encoding="utf-8")
    report = {"status": "host_validated_requires_switch_playback", "asset": ASSET,
        "bank_bytes": len(bank), "bank_sha256": digest(bank), "bank_fnv64": f"{fnv64(bank):016x}",
        "review_sha256": digest(a.review.read_bytes()), "native_template_sha256": digest(mobile_bank(a.mobile_obb)),
        "recordings_exact": True, "global_gain_or_playlist_changes": False,
        "clips": [{**c["spec"], "duration_ms": c["duration_ms"], "bytes": len(c["audio"]),
            "header_fnv64": f"{fnv64(c["audio"][:96]):016x}", "gain": GAINS.get(c["spec"]["role"], .65),
            "loop": bool(c["extension"])} for c in clips],
        "unavailable_roles": [r for r in ROLES if r not in {c["spec"]["role"] for c in clips}]}
    (out/"AUDIO-REPORT.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "clips"}, indent=2))


if __name__ == "__main__":
    main()
