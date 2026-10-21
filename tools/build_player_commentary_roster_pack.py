#!/usr/bin/env python3
"""Build the local selected-roster audio archive and pinned metadata catalog.

Uses completed serial stage receipts only. It never rereads proprietary sound
containers, decodes already verified audio again, installs a bank or creates
all home/away pair files. `oracle` reconstructs one selected pair for inspection.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
from itertools import combinations

from batch_player_commentary import read, write, file_record, local_output, exclusive
from pack_runtime_assets import HEADER, ENTRY, MAGIC, verify as verify_archive
from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import TABLES, rebuild_utf, verify_preservation

MAX_BANK = 8 * 1024 * 1024
P0 = re.compile(r"EN_(A1|B1)_P0_R(\d{6})\Z")
STATUS = {"native_preserved": 1, "accepted_canary_preserved": 2}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def accepted_bank(path):
    data = Path(path).read_bytes()
    if (len(data) < 48 or data[:8] != b"NXCMT01\0" or
            struct.unpack_from("<II", data, 32) != (1, 0) or
            struct.unpack_from("<II", data, 40) != (0, len(data) - 48)):
        raise ValueError("accepted delta must be the pinned single-range bank")
    bank = data[48:]
    if len(bank) != struct.unpack_from("<I", data, 12)[0] or fnv64(bank) != struct.unpack_from("<Q", data, 24)[0]:
        raise ValueError("accepted bank identity mismatch")
    return bank


def awb_waves(blob):
    if len(blob) < 20 or blob[:8] != b"AFS2\x02\x04\x02\0":
        raise ValueError("unexpected memory AWB")
    count, alignment, key = struct.unpack_from("<IHH", blob, 8)
    if count > 65535 or alignment != 32 or key or 20 + 6 * count > len(blob):
        raise ValueError("invalid memory AWB")
    ids = struct.unpack_from(f"<{count}H", blob, 16)
    offsets = struct.unpack_from(f"<{count + 1}I", blob, 16 + 2 * count)
    result = {}
    for i, ident in enumerate(ids):
        first, last = (offsets[i] + 31) & ~31, offsets[i + 1]
        if ident in result or not 0 <= first < last <= len(blob):
            raise ValueError("invalid memory AWB ranges")
        result[ident] = blob[first:last]
    return result


def ensure_marker(output):
    """Add the tiny availability marker without repeating staging or bank work."""
    output = local_output(output)
    catalog = read(output / "catalog.local.json")
    marker = (catalog["runtime_pair"] + "\n").encode("ascii")
    if not 0 < len(marker) <= 64:
        raise ValueError("invalid pair availability marker")
    path = output / "players-v59.nxpa"
    with path.open("rb") as source:
        magic, count, stride, total, payload = HEADER.unpack(source.read(HEADER.size))
        if magic != MAGIC or count >= 4096 or stride != ENTRY.size:
            raise ValueError("invalid archive for marker")
        rows = [ENTRY.unpack(source.read(stride)) for _ in range(count)]
        present = [r for r in rows if r[0].split(b"\0", 1)[0] == b"catalog-id.txt"]
        if present:
            source.seek(present[0][1])
            if source.read(present[0][2]) != marker:
                raise ValueError("existing availability marker disagrees")
            return dict(asset="catalog-id.txt", bytes=len(marker), ascii=marker.decode())
        new_payload = payload + ENTRY.size
        extra = ENTRY.pack(b"catalog-id.txt", total + ENTRY.size, len(marker), fnv64(marker), 0, 0)
        index = b"".join(ENTRY.pack(name, at + ENTRY.size, n, hashed, flags, reserved)
                         for name, at, n, hashed, flags, reserved in rows) + extra
        temp = path.with_suffix(".marker.tmp")
        with temp.open("wb") as target:
            target.write(HEADER.pack(MAGIC, count + 1, stride, total + ENTRY.size + len(marker), new_payload))
            target.write(index)
            for _, at, n, expected, _, _ in rows:
                source.seek(at)
                data = source.read(n)
                if len(data) != n or fnv64(data) != expected:
                    raise ValueError("existing recording changed while adding marker")
                target.write(data)
            target.write(marker)
    temp.replace(path)
    proof = verify_archive(path, namespace_prefix="Commentary/players-v59")
    report_path = output / "PACK-RESULT.json"
    if report_path.exists():
        report = read(report_path)
        report["archive"] = proof
        report["availability_marker"] = dict(asset="catalog-id.txt", bytes=len(marker), ascii=marker.decode())
        write(report_path, report)
    return dict(asset="catalog-id.txt", bytes=len(marker), ascii=marker.decode())


def build(config_path, output, domain_path):
    cfg = read(config_path)
    work = Path(cfg["work_dir"])
    output = local_output(output)
    with exclusive(output):
        pointer = read(work / "LATEST-PLAN.json")
        if file_record(pointer["path"])["sha256"] != pointer["sha256"]:
            raise ValueError("stage plan hash mismatch")
        plan = read(pointer["path"])
        if plan["runtime_pair_id"] != cfg["runtime_pair_id"]:
            raise ValueError("stage runtime pair mismatch")
        domain = read(domain_path)
        if domain["plan_sha256"] != pointer["sha256"]:
            raise ValueError("carrier domain belongs to another stage plan")
        label_holds = {row["native_player_id"] for row in domain["rows"]}
        if file_record(cfg["accepted_delta"]) != cfg["accepted_delta_pin"]:
            raise ValueError("accepted canary delta changed")
        bank = accepted_bank(cfg["accepted_delta"])
        report = read(cfg["accepted_report"])
        owners, cues, assets, holds = [], [], {}, Counter()
        for row in sorted(plan["players"], key=lambda r: r["native_player_id"]):
            owner = {key: row.get(key, "") for key in
                     ("base_id", "native_player_id", "fingerprint", "active_row_sha256")}
            owner.update(status=STATUS.get(row["status"], 0), cue_first=len(cues), cue_count=0)
            if row["status"] == "source_validated_pending_stage":
                complete = sorted((work / "players" / str(row["base_id"])).glob("*/complete.json"))
                matching = []
                for path in complete:
                    receipt = read(path)
                    if (receipt.get("status") == "staged_decode_verified" and all(
                            receipt.get(key) == row.get(key) for key in
                            ("base_id", "native_player_id", "fingerprint", "active_row_sha256", "source_row_sha256"))):
                        matching.append((path, receipt))
                if len(matching) != 1:
                    raise ValueError(f"missing/ambiguous staged identity {row['base_id']}")
                receipt_path, receipt = matching[0]
                selected = [cue for cue in receipt["cues"] if P0.fullmatch(cue["native_cue"])]
                if row["native_player_id"] in label_holds:
                    owner["status"] = 4
                    holds["native_label_translation"] += 1
                elif not selected:
                    owner["status"] = 5
                    holds["no_literal_P0"] += 1
                else:
                    if len(selected) > 2 or len({P0.fullmatch(c["native_cue"])[1] for c in selected}) != len(selected):
                        raise ValueError("ambiguous literal P0 contexts")
                    owner["status"] = 3
                    for cue in sorted(selected, key=lambda c: c["native_cue"]):
                        path = (work / cue["file"]).resolve()
                        path.relative_to((work / "audio").resolve())
                        if file_record(path) != cue["payload"] or cue["payload"] != cue["source_payload"]:
                            raise ValueError("staged audio changed")
                        audio = path.read_bytes()
                        if len(audio) < 96 or audio[:4] != b"HCA\0" or b"ciph\0\0" not in audio[:96]:
                            raise ValueError("not the staged plaintext HCA")
                        if f"{fnv64(audio[:96]):016x}" != cue["plaintext_header_fnv64"]:
                            raise ValueError("staged header changed")
                        decode_path = path.with_suffix(".decode.json")
                        decoded = read(decode_path)
                        if decoded.get("payload") != cue["payload"] or decoded.get("full_decode_exit_code") != 0:
                            raise ValueError("recording lacks successful full decode proof")
                        asset = "audio/" + path.name.lower()
                        assets[asset] = path
                        cues.append(dict(owner_index=len(owners), type=0 if "_A1_" in cue["native_cue"] else 24,
                            name=cue["native_cue"], asset=asset, bytes=len(audio), duration_ms=cue["duration_ms"],
                            waveform=cue["waveform"], payload_fnv=f"{fnv64(audio):016x}",
                            header_fnv=cue["plaintext_header_fnv64"], payload=cue["payload"],
                            staged_receipt=str(receipt_path), decode_proof=file_record(decode_path)))
                    owner["cue_count"] = len(cues) - owner["cue_first"]
            owners.append(owner)
        if len({r["native_player_id"] for r in owners}) != len(owners):
            raise ValueError("ambiguous native owner")
        catalog = dict(schema_version=1, runtime_pair=cfg["runtime_pair_id"],
            base_bytes=len(bank), base_fnv=f"{fnv64(bank):016x}", base_sha256=digest(bank),
            owners=owners, cues=cues, baseline_headers=report["unique_plain_hca_header_fnv64"],
            stage_plan=pointer, domain_proof=file_record(domain_path), holds=dict(holds))
        archive = output / "players-v59.nxpa"
        temp = archive.with_suffix(".nxpa.tmp")
        index, cursor = bytearray(), HEADER.size + len(assets) * ENTRY.size
        for name, path in sorted(assets.items()):
            data = path.read_bytes()
            index += ENTRY.pack(name.encode("ascii"), cursor, len(data), fnv64(data), 0, 0)
            cursor += len(data)
        with temp.open("wb") as stream:
            stream.write(HEADER.pack(MAGIC, len(assets), ENTRY.size, cursor, HEADER.size + len(index)))
            stream.write(index)
            for _, path in sorted(assets.items()):
                stream.write(path.read_bytes())
        temp.replace(archive)
        archive_proof = verify_archive(archive, assets, namespace_prefix="Commentary/players-v59")
        (output / "accepted-v53.acb").write_bytes(bank)
        (output / "player_commentary_roster_catalog.h").write_text(c_header(catalog), encoding="utf-8", newline="\n")
        write(output / "catalog.local.json", catalog)
        summary = dict(state="offline_pack_verified_runtime_mount_pending", owners=len(owners),
            owner_status_counts=dict(Counter(o["status"] for o in owners)), new_cues=len(cues),
            unique_recordings=len(assets), archive=archive_proof,
            generated_header=file_record(output / "player_commentary_roster_catalog.h"),
            accepted_bank=dict(bytes=len(bank), sha256=digest(bank)), holds=dict(holds),
            runtime_modified=False, device_heard_new_players=0)
        write(output / "PACK-RESULT.json", summary)
        ensure_marker(output)
        return {k: v for k, v in summary.items() if k != "archive"}


def c_header(catalog):
    q = lambda s: json.dumps(s, ensure_ascii=True)
    lines = ["#ifndef PESNX_PLAYER_COMMENTARY_ROSTER_CATALOG_H", "#define PESNX_PLAYER_COMMENTARY_ROSTER_CATALOG_H",
             '#include "player_commentary_types.h"', "/* Generated identity/hash metadata; no game audio. */",
             "static const PcBankOwner pc_roster_owners[] = {"]
    for o in catalog["owners"]:
        lines.append("{%du,%du,%s,%s,%du,%du,%du}," % (o["base_id"] or 0, o["native_player_id"],
            q(o["fingerprint"]), q(o["active_row_sha256"]), o["status"], o["cue_first"], o["cue_count"]))
    lines += ["};", "static const PcBankCue pc_roster_cues[] = {"]
    for c in catalog["cues"]:
        w = c["waveform"]
        lines.append("{%du,%du,%s,%s,%du,%du,%du,%du,%du,%du,%du,UINT64_C(0x%s),UINT64_C(0x%s)}," % (
            c["owner_index"], c["type"], q(c["name"]), q(c["asset"]), c["bytes"], c["duration_ms"],
            w["EncodeType"], w["NumChannels"], w["LoopFlag"], w["SamplingRate"], w["NumSamples"],
            c["payload_fnv"], c["header_fnv"]))
    lines += ["};", "static const uint64_t pc_roster_baseline_headers[] = {"]
    lines += [f"UINT64_C(0x{h})," for h in catalog["baseline_headers"]]
    lines += ["};", "static const PcBankCatalog player_commentary_roster_catalog = {",
              "%s,%du,%du,%du,%du,UINT64_C(0x%s),pc_roster_owners,pc_roster_cues,pc_roster_baseline_headers};" % (
              q(catalog["runtime_pair"]), catalog["base_bytes"], len(catalog["owners"]), len(catalog["cues"]),
              len(catalog["baseline_headers"]), catalog["base_fnv"]), "#endif", ""]
    return "\n".join(lines)


def oracle(bank, catalog, ids, reader):
    top = Utf(bank)
    tables = {n: top.child(n) for n in TABLES}
    rows = {n: [dict(r) for r in t.rows] for n, t in tables.items()}
    existing = {r["CueName"]: r["CueIndex"] for r in rows["CueNameTable"]}
    owners = {o["native_player_id"]: o for o in catalog["owners"]}
    selected = []
    for ident in sorted(set(ids)):
        o = owners.get(ident)
        if o and o["status"] == 3:
            selected += catalog["cues"][o["cue_first"]:o["cue_first"] + o["cue_count"]]
    waves = awb_waves(top.blob(0, "AwbFile"))
    changed = set()
    for cue in sorted(selected, key=lambda c: c["name"]):
        name = cue["name"]
        if name in existing:
            index = existing[name]
        else:
            index = len(rows["CueTable"])
            if index >= 65535:
                raise ValueError("cue overflow")
            for n in TABLES:
                if n != "CueNameTable":
                    rows[n].append(dict(rows[n][0]))
            rows["CueNameTable"].append(dict(CueName=name, CueIndex=index))
            rows["CueTable"][index].update(CueId=index, ReferenceIndex=index)
            rows["SequenceTable"][index]["TrackIndex"] = struct.pack(">H", index)
            rows["TrackTable"][index]["EventIndex"] = index
            rows["SynthTable"][index]["ReferenceItems"] = struct.pack(">HH", 1, index)
            rows["CommandTable"][index]["Command"] = struct.pack(">HBHHHB", 2000, 4, 2, index, 0, 0)
        changed.add(index)
        rows["CueTable"][index]["Length"] = cue["duration_ms"]
        rows["WaveformTable"][index].update(cue["waveform"], Streaming=0, Id=index)
        if index in waves:
            raise ValueError("attempted overwrite of accepted embedded recording")
        waves[index] = reader(cue["asset"])
    rows["CueNameTable"].sort(key=lambda r: r["CueName"])
    children = {n: rebuild_utf(tables[n], rows[n]) for n in TABLES}
    children["AwbFile"] = memory_awb(list(waves.items()))
    outer = dict(top.rows[0])
    from stage_player_commentary import kinds
    for n, kind in kinds(top).items():
        if kind == 11:
            outer[n] = children.get(n, top.blob(0, n))
    result = rebuild_utf(top, [outer], compact_blobs=True)
    if len(result) + 48 > MAX_BANK:
        raise ValueError("bank/delta cap exceeded")
    verify_preservation(bank, result, changed)
    if any(awb_waves(Utf(result).blob(0, "AwbFile")).get(i) != payload for i, payload in awb_waves(top.blob(0, "AwbFile")).items()):
        raise ValueError("accepted canary recording changed")
    return result, changed


def verify_selected(config_path, output, teams):
    """Exercise the production C builder on one actual selected roster pair.

    The independent Python oracle compares every UTF field/blob and all AWB
    payloads. A successful check is reconstruction proof, never device sound.
    """
    cfg = read(config_path)
    output = local_output(output)
    pointer = read(Path(cfg["work_dir"]) / "LATEST-PLAN.json")
    plan = read(pointer["path"])
    catalog = read(output / "catalog.local.json")
    ids = list(dict.fromkeys(i for team in teams for i in plan["rosters"][str(team)]))
    if len(ids) > 80:
        raise ValueError("actual roster exceeds 80-owner runtime bound")
    cc = shutil.which("gcc")
    if not cc:
        raise RuntimeError("host gcc required for actual C reconstruction")
    validation = output / "validation"
    validation.mkdir(exist_ok=True)
    source = validation / "builder.c"
    source.write_text(r'''
#include <stdio.h>
#include "player_commentary_bank_builder.h"
#include "runtime_assets.h"
#include "player_commentary_roster_catalog.h"
static void *read_audio(void *ctx,const char *key,size_t max,size_t *n) {
 return nx_asset_read_archive((const char *)ctx,key,max,n);
}
int main(int argc,char **argv) {
 if(argc<5 || argc-4>80)return 2;
 FILE *f=fopen(argv[1],"rb");if(!f)return 3;
 fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);if(n<=0 || n>PC_BANK_MAX_BYTES)return 4;
 void *base=malloc(n);if(!base || fread(base,1,n,f)!=(size_t)n)return 5;fclose(f);
 uint32_t ids[80];for(int i=4;i<argc;i++)ids[i-4]=(uint32_t)strtoul(argv[i],NULL,10);
 PcBankResult r;if(!pc_bank_build(base,n,&player_commentary_roster_catalog,ids,argc-4,read_audio,argv[2],&r))return 6;
 f=fopen(argv[3],"wb");if(!f)return 7;if(fwrite(r.data,1,r.size,f)!=r.size)return 8;fclose(f);
 printf("{\"bank_bytes\":%u,\"selected_new_cues\":%u,\"selected_owners\":%u,\"header_count\":%u,\"scratch_peak\":%zu}",
 r.size,r.cue_count,r.player_count,r.header_count,r.scratch_peak);
 pc_bank_free(&r);free(base);return 0;
}
''', encoding="utf-8", newline="\n")
    exe = validation / "builder.exe"
    root = Path(__file__).resolve().parents[1]
    compiled = subprocess.run([cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I", output.as_posix(), "-I", (root / "source").as_posix(),
        source.as_posix(), "-o", exe.as_posix()], capture_output=True, text=True)
    if compiled.returncode:
        raise RuntimeError("C builder compilation failed: " + compiled.stderr)
    target = validation / ("teams-" + "-".join(map(str, teams)) + ".acb")
    actual = subprocess.run([str(exe), str(output / "accepted-v53.acb"), str(output / "players-v59.nxpa"),
        str(target), *map(str, ids)], check=True, capture_output=True, text=True)
    costs = json.loads(actual.stdout)
    # Read only selected archive spans through the independent fixture reader.
    def read_recording(key):
        with (output / "players-v59.nxpa").open("rb") as stream:
            magic, count, stride, _, _ = HEADER.unpack(stream.read(HEADER.size))
            if magic != MAGIC or stride != ENTRY.size:
                raise ValueError("archive contract changed")
            for _ in range(count):
                name, at, n, expected, _, _ = ENTRY.unpack(stream.read(stride))
                if name.split(b"\0", 1)[0].decode() == key:
                    stream.seek(at)
                    data = stream.read(n)
                    if fnv64(data) != expected:
                        raise ValueError("archive readback hash mismatch")
                    return data
        raise ValueError("selected recording absent")
    base = (output / "accepted-v53.acb").read_bytes()
    expected, changed = oracle(base, catalog, ids, read_recording)
    built = target.read_bytes()
    x, y = Utf(expected), Utf(built)
    for name in TABLES:
        a, b = x.child(name), y.child(name)
        if len(a.rows) != len(b.rows):
            raise ValueError("C/Python row count differs")
        from stage_player_commentary import kinds
        field_kinds = kinds(a)
        for i, row in enumerate(a.rows):
            for field, kind in field_kinds.items():
                left = a.blob(i, field) if kind == 11 else row[field]
                right = b.blob(i, field) if kind == 11 else b.rows[i][field]
                if left != right:
                    raise ValueError(f"C/Python graph differs {name}/{i}/{field}")
    if awb_waves(x.blob(0, "AwbFile")) != awb_waves(y.blob(0, "AwbFile")):
        raise ValueError("C/Python recording bytes differ")
    for field, kind in kinds(x).items():
        if field in (*TABLES, "AwbFile"):
            continue
        left = x.blob(0, field) if kind == 11 else x.rows[0][field]
        right = y.blob(0, field) if kind == 11 else y.rows[0][field]
        if left != right:
            raise ValueError("C/Python unrelated top metadata differs")
    baseline = awb_waves(Utf(base).blob(0, "AwbFile"))
    current = awb_waves(y.blob(0, "AwbFile"))
    if any(current.get(k) != v for k, v in baseline.items()):
        raise ValueError("accepted canary payload changed")
    result = dict(teams=teams, raw_selected_players=len(ids), actual_c_costs=costs,
        result_sha256=digest(built), result_bytes=len(built), changed_indices=len(changed),
        original_canary_waves_preserved=len(baseline), complete_UTF_graph_matches_python=True,
        all_selected_audio_already_decode_verified=True, runtime_mounted=False, device_heard=False,
        builder=file_record(root / "source/player_commentary_bank_builder.h"),
        catalog=file_record(output / "catalog.local.json"),
        generated_catalog=file_record(output / "player_commentary_roster_catalog.h"),
        archive=file_record(output / "players-v59.nxpa"))
    write(target.with_suffix(".VERIFIED.json"), result)
    return result


def metadata_costs(config_path, output):
    """Exact size arithmetic for every pair, without constructing any pair bank."""
    cfg = read(config_path)
    output = local_output(output)
    plan = read(read(Path(cfg["work_dir"]) / "LATEST-PLAN.json")["path"])
    catalog = read(output / "catalog.local.json")
    top = Utf((output / "accepted-v53.acb").read_bytes())
    from stage_player_commentary import kinds
    tables = {n: top.child(n) for n in TABLES}
    existing = {r["CueName"]: r["CueIndex"] for r in tables["CueNameTable"].rows}
    original = len(existing)
    waves = awb_waves(top.blob(0, "AwbFile"))
    if max(waves) != original - 1:
        raise ValueError("cost model requires accepted canary at final cue index")
    old_padded = sum((len(v) + 31) & ~31 for v in waves.values())
    old_last_padding = (-len(waves[max(waves)])) & 31
    mutable = {"CueTable": {"CueId", "ReferenceIndex", "Length"},
        "CueNameTable": {"CueIndex"}, "WaveformTable": {"Id", "Streaming", "EncodeType", "NumChannels",
        "LoopFlag", "SamplingRate", "NumSamples"}, "TrackTable": {"EventIndex"}}
    graph = {"SynthTable": ("ReferenceItems", 4), "CommandTable": ("Command", 10),
             "SequenceTable": ("TrackIndex", 2)}
    bit = 0
    constants, meta = [], {}
    for name, u in tables.items():
        promoted = []
        for field, (mode, fmt, _) in u.fields.items():
            if mode != 0x50 and field in mutable.get(name, set()):
                constants.append((bit, name, field, u.rows[0][field]))
                promoted.append((1 << bit, mode, struct.calcsize(fmt)))
                bit += 1
        graph_promotion = None
        if name in graph:
            field = graph[name][0]
            mode, fmt, _ = u.fields[field]
            if mode != 0x50:
                graph_promotion = (mode, struct.calcsize(fmt))
        meta[name] = dict(row=u.row_start, stride=u.stride, strings=u.blobs - u.strings,
            blobs=u.size - u.blobs, promoted=promoted, graph_promotion=graph_promotion)
    # Every graph index field in the accepted multi-row template is per-row.
    # This proves feature masks only depend on source waveform/length metadata.
    for _, name, field, _ in constants:
        if field in {"CueId", "ReferenceIndex", "CueIndex", "Id", "EventIndex"}:
            raise ValueError("cost model requires the pinned per-row graph-index schema")
    cue_stats = []
    for cue in catalog["cues"]:
        values = dict(cue["waveform"], Streaming=0, Length=cue["duration_ms"])
        mask = 0
        for bit, _, field, old in constants:
            if values.get(field, old) != old:
                mask |= 1 << bit
        new = cue["name"] not in existing
        cue_stats.append((cue["name"], cue["bytes"], new, mask))
    by_id = {o["native_player_id"]: o for o in catalog["owners"]}
    rosters = {int(team): set(ids) for team, ids in plan["rosters"].items()}
    names = {t["team_id"]: t["display_name"] for t in plan["teams"]}
    top_binary_lengths = {field: len(top.blob(0, field)) for field, kind in kinds(top).items() if kind == 11}
    max_bank, max_scratch, max_added, max_selected = None, None, None, None
    count, over, roster_holds, index_holds = 0, [], [], []
    for home, away in combinations(rosters, 2):
        ids = rosters[home] | rosters[away]
        selected = [cue_stats[k] for ident in ids if (o := by_id.get(ident)) and o["status"] == 3
                    for k in range(o["cue_first"], o["cue_first"] + o["cue_count"])]
        added = sum(c[2] for c in selected)
        rows = original + added
        mask = 0
        for cue in selected:
            mask |= cue[3]
        child_sizes = {}
        for name in TABLES:
            m = meta[name]
            row, stride = m["row"], m["stride"]
            for feature, mode, width in m["promoted"]:
                if mask & feature:
                    row -= width if mode == 0x30 else 0
                    stride += width
            if added and m["graph_promotion"]:
                mode, width = m["graph_promotion"]
                row -= width if mode == 0x30 else 0
                stride += width
            strings = m["strings"] + (sum(len(c[0]) + 1 for c in selected if c[2]) if name == "CueNameTable" else 0)
            blobs = m["blobs"]
            if added and name in graph:
                width = graph[name][1]
                blobs = ((blobs + 3) & ~3) + width + (added - 1) * ((width + 3) & ~3)
            child_sizes[name] = ((row + stride * rows + strings + 3) & ~3) + blobs
        added_cues = [c for c in selected if c[2]]
        last_pad = (-max(added_cues, key=lambda c: c[0])[1]) & 31 if added_cues else old_last_padding
        wave_count = len(waves) + len(selected)
        awb_capacity = 20 + wave_count * 6 + sum(31 + len(v) for v in waves.values()) + sum(31 + c[1] for c in selected)
        awb_size = ((20 + wave_count * 6 + 31) & ~31) + old_padded + sum((c[1] + 31) & ~31 for c in selected) - last_pad
        child_sizes["AwbFile"] = awb_size
        size = top.blobs
        for field, length in top_binary_lengths.items():
            size = ((size + 3) & ~3) + child_sizes.get(field, length)
        children_total = sum(child_sizes[n] for n in TABLES) + awb_capacity
        scratch = max(children_total + size, sum(child_sizes[n] for n in TABLES) + awb_capacity +
                      max((c[1] for c in selected), default=0))
        row = dict(team_ids=[home, away], team_names=[names[home], names[away]], selected_owners=len(ids),
            new_cues=len(selected), appended_cues=added, result_cues=rows, bank_bytes=size,
            delta_bytes=size + 48, scratch_peak=scratch)
        count += 1
        if max_bank is None or size > max_bank["bank_bytes"]:
            max_bank = row
        if max_scratch is None or scratch > max_scratch["scratch_peak"]:
            max_scratch = row
        if max_added is None or added > max_added["appended_cues"]:
            max_added = row
        if max_selected is None or len(selected) > max_selected["new_cues"]:
            max_selected = row
        if size + 48 > MAX_BANK or scratch > 18 * 1024 * 1024:
            over.append(row)
        if len(ids) > 80:
            roster_holds.append(row)
        if rows >= 65535 or len(selected) > 160:
            index_holds.append(row)
    result = dict(schema_version=1, pairs_examined=count, max_bank=max_bank, max_scratch=max_scratch,
        max_appended=max_added, max_selected=max_selected, over_budget_pairs=over,
        over_roster_bound_pairs=roster_holds, over_index_bound_pairs=index_holds,
        bank_cap=MAX_BANK, delta_cap=MAX_BANK, scratch_cap=18 * 1024 * 1024,
        exact_size_model="same UTF constant promotion/row/string/blob alignment and merged-AWB arithmetic as production C",
        source_audio_reads=0, pair_banks_constructed=0, device_playback=False,
        catalog=file_record(output / "catalog.local.json"), builder=file_record(Path(__file__).resolve().parents[1] / "source/player_commentary_bank_builder.h"))
    # Existing actual reconstructions independently check the arithmetic, not
    # just another version of the formula. Require each observation to agree.
    for proof in (output / "validation").glob("*.VERIFIED.json"):
        observed = read(proof)
        # A direct single-pair check is also exposed separately below.
        if observed["teams"] == max_bank["team_ids"] and observed["result_bytes"] != max_bank["bank_bytes"]:
            raise ValueError("exact model disagrees with actual maximum-pair C bank")
    write(output / "ALL-PAIR-COSTS.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--native-domain", required=True)
    parser.add_argument("--check-team", type=int, nargs=2,
                        help="verify one existing-pack home/away reconstruction instead of building")
    parser.add_argument("--metadata-costs", action="store_true", help="exact metadata-only sizes for all distinct pairs")
    parser.add_argument("--ensure-marker", action="store_true", help="add/verify tiny pair marker without rebuilding the pack")
    args = parser.parse_args()
    result = (ensure_marker(args.output) if args.ensure_marker else
              metadata_costs(args.config, args.output) if args.metadata_costs else
              verify_selected(args.config, args.output, args.check_team) if args.check_team else
              build(args.config, args.output, args.native_domain))
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
