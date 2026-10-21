#!/usr/bin/env python3
"""Audit and stage a detached Yamal/Raphinha FL26 commentary canary.

Owned recordings and rebuilt banks remain local. This does not rewrite a CPK,
player identity, active runtime, or save. Mobile's UTF schema and every
unaffected cue/sequence/track/synth/wave relationship are preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from build_fl26_cup_catalog import cpk_member, decoded_member, index_cpk
from convert_efootball10_players import read_bits
from pes21_player_migration import identity_fingerprint, normalize_name
from pesdb import decode_wesys, parse_player_records
from stage_indonesia_commentary import (FORMATS, HEADER, MAGIC, Utf, fnv64,
                                        memory_awb, mobile_index, read_awb_wave)

ROOT = Path(__file__).resolve().parents[1]
MAX_BANK = MAX_PATCH = 8 * 1024 * 1024
TABLES = ("CueTable", "CueNameTable", "WaveformTable", "SynthTable",
          "CommandTable", "TrackTable", "SequenceTable")
TARGETS = {
    110644: {"name": "Raphinha", "fingerprint": "a127e8032d5e1bdff42a",
             "pc_country": 292},
    162114: {"name": "Lamine Yamal", "fingerprint": "a7ded89f5960baa40983",
             "pc_country": 472},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def kinds(table: Utf) -> dict[str, int]:
    cursor = 32
    result = {}
    for name in table.fields:
        flag = table.data[cursor]
        result[name] = flag & 15
        cursor += 5 + (struct.calcsize(FORMATS[flag & 15])
                       if flag & 0xf0 == 0x30 else 0)
    return result


def rebuild_utf(table: Utf, rows: list[dict], *, compact_blobs: bool = False) -> bytes:
    """Retain UTF types/constants; promote changed constants, append strings/blobs.

    Existing binary values remain (offset, length) references. New binary
    values are bytes. Offsets are always relative to this table's data pool.
    """
    if not rows:
        raise ValueError("empty UTF table")
    types = kinds(table)
    strings = bytearray(table.data[table.strings:table.blobs])
    string_offsets = {}
    cursor = 0
    while cursor < len(strings):
        end = strings.index(0, cursor) + 1
        string_offsets.setdefault(bytes(strings[cursor:end]), cursor)
        cursor = end
    blobs = bytearray() if compact_blobs else bytearray(table.data[table.blobs:])
    descriptors = bytearray()
    encoded: dict[str, list[bytes]] = {}
    storage_by_name = {}
    for name, (storage, fmt, _) in table.fields.items():
        values = []
        for row in rows:
            value = row[name]
            if types[name] == 10:
                raw = value.encode("utf-8") + b"\0"
                if raw in string_offsets:
                    value = string_offsets[raw]
                else:
                    value = len(strings)
                    strings.extend(raw)
                    string_offsets[raw] = value
            elif types[name] == 11:
                if isinstance(value, bytes):
                    offset = (len(blobs) + 3) & ~3
                    blobs.extend(bytes(offset - len(blobs)))
                    blobs.extend(value)
                    value = offset, len(value)
                if (not isinstance(value, tuple) or len(value) != 2
                        or min(value) < 0 or sum(value) > len(blobs)):
                    raise ValueError(f"invalid UTF binary reference {name}")
            values.append(struct.pack(fmt, *(value if isinstance(value, tuple) else (value,))))
        if storage in (0x10, 0x30) and len(set(values)) > 1:
            storage = 0x50
        elif storage == 0x10 and any(any(v) for v in values):
            storage = 0x30
        if storage not in (0x10, 0x30, 0x50):
            raise ValueError("unsupported UTF storage")
        descriptors.extend(struct.pack(">BI", storage | types[name],
                                       string_offsets[name.encode() + b"\0"]))
        if storage == 0x30:
            descriptors.extend(values[0])
        encoded[name] = values
        storage_by_name[name] = storage
    stride = sum(struct.calcsize(table.fields[n][1]) for n in table.fields
                 if storage_by_name[n] == 0x50)
    row_data = b"".join(encoded[n][i] for i in range(len(rows)) for n in table.fields
                        if storage_by_name[n] == 0x50)
    row_start = 32 + len(descriptors)
    string_start = row_start + len(row_data)
    data_start = (string_start + len(strings) + 3) & ~3
    out = bytearray(table.data[:32]) + descriptors + row_data + strings
    out.extend(bytes(data_start - len(out)))
    out.extend(blobs)
    struct.pack_into(">I", out, 4, len(out) - 8)
    struct.pack_into(">H", out, 10, row_start - 8)
    struct.pack_into(">II", out, 12, string_start - 8, data_start - 8)
    struct.pack_into(">HI", out, 26, stride, len(rows))
    # Independently parse the result before it can become an ACB child.
    if len(Utf(bytes(out)).rows) != len(rows):
        raise ValueError("UTF rebuild row count changed")
    return bytes(out)


def validate_mobile_graph(top: Utf) -> dict[str, Utf]:
    if top.rows[0]["Name"] != "10_PLAYER" or top.rows[0]["AwbFile"] != (0, 0):
        raise ValueError("expected streaming-only mobile player bank")
    tables = {name: top.child(name) for name in TABLES}
    count = len(tables["CueTable"].rows)
    if not count or count >= 65535 or any(len(t.rows) != count for t in tables.values()):
        raise ValueError("mobile player bank is not one-to-one")
    names = tables["CueNameTable"].rows
    if (sorted(r["CueIndex"] for r in names) != list(range(count))
            or len({r["CueName"] for r in names}) != count):
        raise ValueError("mobile cue names share or miss references")
    for i in range(count):
        c, w = tables["CueTable"].rows[i], tables["WaveformTable"].rows[i]
        seq, track = tables["SequenceTable"].rows[i], tables["TrackTable"].rows[i]
        if (c["ReferenceType"] != 3 or c["ReferenceIndex"] != i or c["CueId"] != i
                or w["Streaming"] != 1 or seq["NumTracks"] != 1
                or tables["SequenceTable"].blob(i, "TrackIndex") != struct.pack(">H", i)
                or track["EventIndex"] != i
                or tables["SynthTable"].blob(i, "ReferenceItems") != struct.pack(">HH", 1, i)
                or tables["CommandTable"].blob(i, "Command") != struct.pack(">HBHHHB", 2000, 4, 2, i, 0, 0)):
            raise ValueError(f"unexpected mobile audio graph at {i}")
    return tables


def cue_identity(name: str) -> int | None:
    match = re.fullmatch(r"EN_(?:A1|B1|A1B1)_P[A-Z0-9]+_R(\d{6})(?:_\d{2})?", name)
    return int(match[1]) if match else None


def build_bank(base: bytes, donor: bytes, wave_reader, *, targets: set[int],
               preserved_mobile_ids: set[int]) -> tuple[bytes, dict]:
    top, donor_top = Utf(base), Utf(donor)
    tables = validate_mobile_graph(top)
    if donor_top.rows[0]["Name"] != "10_PLAYER":
        raise ValueError("wrong FL26 bank")
    source = {n: donor_top.child(n) for n in ("CueTable", "CueNameTable", "WaveformTable")}
    selected = [r for r in source["CueNameTable"].rows if cue_identity(r["CueName"]) in targets]
    if {cue_identity(r["CueName"]) for r in selected} != targets:
        raise ValueError("missing FL26 target cues")
    if len({r["CueName"] for r in selected}) != len(selected):
        raise ValueError("duplicate FL26 cue name")
    rows = {n: [dict(r) for r in t.rows] for n, t in tables.items()}
    existing = {r["CueName"]: r["CueIndex"] for r in rows["CueNameTable"]}
    donor_names = {r["CueName"] for r in selected}
    preserved = [n for n in existing if cue_identity(n) in targets and n not in donor_names]
    if any(cue_identity(n) not in preserved_mobile_ids for n in preserved):
        raise ValueError("unverified Mobile-only target cue ownership")
    recordings, reports, changed_indices = [], [], set()
    for name_row in sorted(selected, key=lambda r: r["CueName"]):
        name = name_row["CueName"]
        c = source["CueTable"].rows[name_row["CueIndex"]]
        if c["ReferenceType"] != 1:
            raise ValueError("FL26 cue is not direct waveform")
        w = source["WaveformTable"].rows[c["ReferenceIndex"]]
        if (w["Streaming"] != 1 or w["MemoryAwbId"] != 65535
                or w["StreamAwbPortNo"] != 0 or w["EncodeType"] != 2):
            raise ValueError("unsupported FL26 waveform")
        payload = wave_reader(w["StreamAwbId"])
        if len(payload) < 96 or payload[:4] != b"HCA\0" or b"ciph\0\0" not in payload[:96]:
            raise ValueError("expected audited plaintext HCA")
        if name in existing:
            index = existing[name]
            operation = "replace_exact_identity_cue"
        else:
            index = len(rows["CueTable"])
            if index >= 65535:
                raise ValueError("mobile cue index capacity exceeded")
            operation = "append_explicit_identity_cue"
            for table_name in TABLES:
                if table_name != "CueNameTable":
                    rows[table_name].append(dict(rows[table_name][0]))
            rows["CueNameTable"].append({"CueName": name, "CueIndex": index})
            rows["CueTable"][index].update(CueId=index, ReferenceIndex=index)
            rows["SequenceTable"][index]["TrackIndex"] = struct.pack(">H", index)
            rows["TrackTable"][index]["EventIndex"] = index
            rows["SynthTable"][index]["ReferenceItems"] = struct.pack(">HH", 1, index)
            rows["CommandTable"][index]["Command"] = struct.pack(">HBHHHB", 2000, 4, 2, index, 0, 0)
        changed_indices.add(index)
        rows["CueTable"][index]["Length"] = c["Length"]
        wave_row = rows["WaveformTable"][index]
        for key in ("EncodeType", "NumChannels", "LoopFlag", "SamplingRate", "NumSamples"):
            wave_row[key] = w[key]
        wave_row.update(Streaming=0, Id=index)
        recordings.append((index, payload))
        reports.append({"cue": name, "native_player_id": cue_identity(name),
                        "operation": operation, "cue_index": index, "duration_ms": c["Length"],
                        "audio_bytes": len(payload), "audio_sha256": sha(payload),
                        "plaintext_header_fnv64": f"{fnv64(payload[:96]):016x}"})
    rows["CueNameTable"].sort(key=lambda r: r["CueName"])
    children = {name: rebuild_utf(tables[name], rows[name]) for name in TABLES}
    children["AwbFile"] = memory_awb(recordings)
    # Repack every top-level binary field in its original field order. This
    # removes obsolete tables instead of retaining a second six-megabyte graph.
    outer = dict(top.rows[0])
    for name, kind in kinds(top).items():
        if kind == 11:
            outer[name] = children.get(name, top.blob(0, name))
    result = rebuild_utf(top, [outer], compact_blobs=True)
    if len(result) < len(base):
        raise ValueError("unexpected shrinking player bank")
    if len(result) > MAX_BANK:
        raise ValueError("player bank exceeds 8 MiB runtime limit")
    verify_preservation(base, result, changed_indices)
    # One bounded replacement range; no hidden dependence on append offsets.
    delta = HEADER.pack(MAGIC, len(base), len(result), fnv64(base), fnv64(result), 1, 0)
    delta += struct.pack("<II", 0, len(result)) + result
    if len(delta) > MAX_PATCH:
        raise ValueError("player delta exceeds 8 MiB runtime limit")
    return delta, {"cues": reports, "preserved_mobile_only_cues": sorted(preserved),
                   "base_bytes": len(base), "base_fnv64": f"{fnv64(base):016x}", "base_sha256": sha(base),
                   "result_bytes": len(result), "result_fnv64": f"{fnv64(result):016x}",
                   "result_sha256": sha(result), "delta_bytes": len(delta), "delta_sha256": sha(delta),
                   "delta_fnv64": f"{fnv64(delta):016x}",
                   "unique_plain_hca_header_fnv64": sorted({r["plaintext_header_fnv64"] for r in reports}),
                   "original_cues": len(tables["CueTable"].rows),
                   "result_cues": len(rows["CueTable"]),
                   "unaffected_original_cues": len(tables["CueTable"].rows) - len(changed_indices & set(range(len(tables["CueTable"].rows)))),
                   "streaming_awb_unchanged": True}


def verify_preservation(base: bytes, result: bytes, changed: set[int]) -> None:
    old, new = Utf(base), Utf(result)
    for name in TABLES:
        a, b = old.child(name), new.child(name)
        types = kinds(a)
        if name == "CueNameTable":
            after = {r["CueName"]: r["CueIndex"] for r in b.rows}
            if any(after.get(r["CueName"]) != r["CueIndex"] for r in a.rows):
                raise ValueError("original cue-name mapping changed")
            continue
        for i, row in enumerate(a.rows):
            for field, value in row.items():
                if i in changed and (name == "WaveformTable" or name == "CueTable" and field == "Length"):
                    continue
                if types[field] == 11:
                    if a.blob(i, field) != b.blob(i, field):
                        raise ValueError(f"unaffected binary reference changed {name}/{i}/{field}")
                elif value != b.rows[i][field]:
                    raise ValueError(f"unaffected cue field changed {name}/{i}/{field}")
    for name, kind in kinds(old).items():
        if name in (*TABLES, "AwbFile"):
            continue
        if kind == 11:
            if old.blob(0, name) != new.blob(0, name):
                raise ValueError(f"unrelated bank payload changed {name}")
        elif old.rows[0][name] != new.rows[0][name]:
            raise ValueError(f"unrelated bank metadata changed {name}")


def player_rows(data: bytes) -> dict[int, tuple[bytes, object]]:
    parsed = parse_player_records(data, "pes21")
    return {struct.unpack_from("<I", data, off + 8)[0]: (data[off:off + 312], parsed[struct.unpack_from("<I", data, off + 8)[0]])
            for off in range(0, len(data), 312)}


def audit_identities(state: dict, active: bytes, donor: bytes, original: bytes) -> list[dict]:
    active_rows, donor_rows, original_rows = map(player_rows, (active, donor, original))
    report = []
    identities = state["identities"]
    if isinstance(identities, dict):
        identities = identities.values()
    for base_id, expected in TARGETS.items():
        matches = [r for r in identities if r.get("base_id") == base_id]
        if len(matches) != 1:
            raise ValueError("ambiguous or absent BaseId identity")
        identity = matches[0]
        if (identity["status"] != "active" or not identity["native_identity_verified"]
                or identity["fingerprint"] != expected["fingerprint"]
                or normalize_name(identity["name"]) != normalize_name(expected["name"])):
            raise ValueError("target BaseId fingerprint changed")
        native_id = identity["native_player_id"]
        if native_id != base_id:
            raise ValueError("canary needs audited native label translation")
        row, player = active_rows[native_id]
        source_row, source = donor_rows[base_id]
        if (sha(row) != identity["native_sha256"]
                or normalize_name(player.name) != normalize_name(expected["name"])):
            raise ValueError("active Player.bin does not match identity state")
        canonical_fingerprint = identity_fingerprint({"BaseId": base_id, "Name": identity["name"],
            "Country": identity["country"], "Height": identity["height"], "Foot": identity["foot"]})
        if canonical_fingerprint != expected["fingerprint"]:
            raise ValueError("canonical biography fingerprint changed")
        if (normalize_name(source.name) != normalize_name(expected["name"])
                or source.nationality_code != expected["pc_country"]
                or source.nationality_code != player.nationality_code
                or read_bits(source_row, 216, 8) != read_bits(row, 216, 8)
                or read_bits(source_row, 514, 1) != read_bits(row, 514, 1)
                or abs(read_bits(source_row, 408, 6) - read_bits(row, 408, 6)) > 2):
            raise ValueError("FL26 identity biography does not match canonical target")
        original_match = original_rows.get(native_id)
        verified_owner = bool(original_match and
            normalize_name(original_match[1].name) == normalize_name(expected["name"]) and
            original_match[1].nationality_code == player.nationality_code and
            identity["registry"].get("commentary_owner_id") == native_id)
        report.append({"base_id": base_id, "name": expected["name"], "native_player_id": native_id,
                       "fingerprint": expected["fingerprint"], "active_row_sha256": sha(row),
                       "fl26_row_sha256": sha(source_row), "mobile_original_owner_verified": verified_owner,
                       "original_row_sha256": sha(original_match[0]) if verified_owner else None})
    return report


def policy_header(report: dict) -> str:
    """Public compatibility metadata only; no audio, HCA bytes or cipher key."""
    lines = ["#ifndef PESNX_PLAYER_COMMENTARY_CATALOG_H", "#define PESNX_PLAYER_COMMENTARY_CATALOG_H", "",
             "/* Audited compatibility metadata only; no game audio or cipher keys.",
             " * Generated by tools/stage_player_commentary.py --policy-header."]
    for base_id, target in TARGETS.items():
        lines.append(f" * {target['name']}: BaseId/native {base_id}, fingerprint {target['fingerprint']}.")
    lines += [" */", f'#define PLAYER_COMMENTARY_RUNTIME_PAIR "{report["runtime_pair_id"]}"',
              f'#define PLAYER_COMMENTARY_BASE_BYTES {report["base_bytes"]}u',
              f'#define PLAYER_COMMENTARY_RESULT_BYTES {report["result_bytes"]}u',
              f'#define PLAYER_COMMENTARY_BASE_FNV UINT64_C(0x{report["base_fnv64"]})',
              f'#define PLAYER_COMMENTARY_RESULT_FNV UINT64_C(0x{report["result_fnv64"]})',
              f'#define PLAYER_COMMENTARY_PATCH_BYTES {report["delta_bytes"]}u',
              f'#define PLAYER_COMMENTARY_PATCH_FNV UINT64_C(0x{report["delta_fnv64"]})',
              "static const uint64_t player_commentary_plain_headers[] = {"]
    lines += [f"    UINT64_C(0x{value})," for value in report["unique_plain_hca_header_fnv64"]]
    lines += ["};", "", "#endif", ""]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mobile-cpk", type=Path, required=True)
    p.add_argument("--fl26-cpk", type=Path, required=True)
    p.add_argument("--fl26-database-cpk", type=Path, required=True)
    p.add_argument("--active-database-cpk", type=Path, required=True)
    p.add_argument("--identity-state", type=Path, required=True)
    p.add_argument("--original-player-table", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--policy-header", action="store_true", help="also emit a metadata-only C header in the local output")
    args = p.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "local-debug") or output.exists():
        p.error("choose a new ignored local-debug output directory")
    database_member = "common/etc/pesdb/Player.bin"
    ai, ab = index_cpk(args.active_database_cpk)
    di, db = index_cpk(args.fl26_database_cpk)
    identities = audit_identities(json.loads(args.identity_state.read_text(encoding="utf-8")),
        decoded_member(args.active_database_cpk, ai, ab, database_member),
        decoded_member(args.fl26_database_cpk, di, db, database_member),
        decode_wesys(args.original_player_table))
    mobile, mb = mobile_index(args.mobile_cpk)
    fl26, fb = index_cpk(args.fl26_cpk)
    member = "eng/sound/acb/10_PLAYER.acb"
    base = cpk_member(args.mobile_cpk, mobile, mb, member)
    donor = cpk_member(args.fl26_cpk, fl26, fb, member)
    delta, report = build_bank(base, donor, lambda ident: read_awb_wave(
        args.fl26_cpk, fl26["eng/sound/awb/10_PLAYER.awb"], fb, ident),
        targets=set(TARGETS), preserved_mobile_ids={r["native_player_id"] for r in identities
                                                 if r["mobile_original_owner_verified"]})
    destination = output / "Commentary" / "players-yamal-raphinha.nxcp"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(delta)
    report.update(status="local_candidate_requires_switch_playback_check", identities=identities,
                  mobile_acb_sha256=sha(base), fl26_acb_sha256=sha(donor),
                  identity_state_sha256=sha(args.identity_state.read_bytes()),
                  original_player_table_sha256=sha(args.original_player_table.read_bytes()),
                  runtime_pair_id="e861c583ec78e9ae",
                  native_player_ids_unchanged=True, active_runtime_modified=False)
    (output / "player-commentary-report.local.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.policy_header:
        (output / "player_commentary_catalog.h").write_text(policy_header(report), encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("cues", "identities")}, indent=2))


if __name__ == "__main__":
    main()
