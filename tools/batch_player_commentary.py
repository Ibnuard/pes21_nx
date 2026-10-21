#!/usr/bin/env python3
"""Serial per-team FL26 player-call audit and detached, checkpointed staging.

This stages owned HCA recordings and explicit NativeID cue mappings. It never
installs a bank, changes a player, or claims that a staged call plays on Switch.
The v53 bank's 8 MiB/16-bit limits remain unchanged; all-player runtime bank
integration is a separate, deliberately unimplemented step.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

from build_fl26_cup_catalog import cpk_member, decoded_member, index_cpk
from convert_efootball10_players import read_bits
from pes21_player_migration import identity_fingerprint, normalize_name
from pesdb import decode_wesys
from stage_indonesia_commentary import Utf, mobile_index, fnv64
from stage_player_commentary import cue_identity, player_rows

ROOT = Path(__file__).resolve().parents[1]
POLICY = "per-team-commentary-v57-v1"
DATABASE_MEMBER = "common/etc/pesdb/Player.bin"
ACB_MEMBER = "eng/sound/acb/10_PLAYER.acb"
AWB_MEMBER = "eng/sound/awb/10_PLAYER.awb"
PROTECTED = {110644, 162114}
READY = {"native_preserved", "accepted_canary_preserved", "staged_decode_verified"}
MAX_RECORDING_BYTES = 2 * 1024 * 1024
MAX_PLAYER_BYTES = 16 * 1024 * 1024


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_record(path):
    path = Path(path)
    with path.open("rb") as stream:
        return {"bytes": path.stat().st_size,
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def key(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=True,
                             separators=(",", ":")).encode())[:24]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n",
                         encoding="utf-8", newline="\n")
    temporary.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def local_output(path):
    path = Path(path).resolve()
    if (path.drive.upper() != "D:" or not path.is_relative_to(ROOT / "local-debug")
            or path == ROOT / "local-debug"):
        raise ValueError("Use a dedicated ignored local-debug output on D")
    return path


@contextmanager
def exclusive(work):
    """OS-held lock, so a stale receipt/PID cannot authorize a second runner."""
    work.mkdir(parents=True, exist_ok=True)
    with (work / "runner.lock").open("a+b") as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b"0"); stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("A commentary batch already owns this work directory") from error
        else:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("A commentary batch already owns this work directory") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def selector_rosters(text):
    found = re.findall(r"exhibition_migration_team_(\d+)_players\[\]\s*=\s*\{([^}]+)\}", text)
    result = {}
    for team, values in found:
        ids = [int(value) for value in re.findall(r"\b(\d+)u\b", values)]
        if not ids or len(ids) != len(set(ids)) or int(team) in result:
            raise ValueError("Invalid or duplicate selector roster")
        result[int(team)] = ids
    if not result:
        raise ValueError("No active selector rosters")
    return result


def ordered_teams(catalog):
    rows = {row["team_id"]: row for row in catalog["teams"]}
    if len(rows) != len(catalog["teams"]):
        raise ValueError("Duplicate catalog team")
    result = []
    for category in catalog["categories"]:
        for team in category["team_ids"]:
            if team not in rows:
                raise ValueError("Catalog category references absent team")
            if team not in result:
                result.append(team)
    if set(result) != rows.keys():
        raise ValueError("Catalog contains uncategorized teams")
    return [rows[team] for team in result]


def validate_catalog_pair(catalog, team_text, runtime_pair):
    # Catalog migration_build_id describes its historical authoring parent.
    # The generated include, whose hash is checked against accepted build
    # inputs by the caller, binds that catalog's content to the actual pair.
    if (f'Catalog content ID: {catalog["content_id"]}' not in team_text
            or f'Paired loose CPK build ID: {runtime_pair}' not in team_text):
        raise ValueError("Compiled team include is not the pinned catalog/runtime pair")
    arrays = {name: [int(v) for v in re.findall(r"\b(\d+)u\b", values)]
              for name, values in re.findall(r"exhibition_category_(\w+)_teams\[\]\s*=\s*\{([^}]+)\}", team_text)}
    if arrays != {row["key"]: row["team_ids"] for row in catalog["categories"]}:
        raise ValueError("Catalog category arrays differ from the accepted compiled selector")


def canonical_names(identity):
    return {normalize_name(identity["name"]),
            *(normalize_name(name) for name in identity.get("aliases", []))}


def validate_active(identity, active):
    native = identity["native_player_id"]
    if (identity.get("status") != "active" or not identity.get("native_identity_verified")
            or identity.get("base_id", 0) <= 0 or native not in active):
        raise ValueError("active_identity_missing_or_unverified")
    fp = identity_fingerprint({"BaseId": identity["base_id"], "Name": identity["name"],
        "Country": identity["country"], "Height": identity["height"], "Foot": identity["foot"]})
    registry = identity["registry"]
    if (fp != identity["fingerprint"] or registry.get("fingerprint") != fp
            or registry.get("ef_base_id") != identity["base_id"]
            or registry.get("native_player_id") != native):
        raise ValueError("canonical_identity_fingerprint_changed")
    row, player = active[native]
    if digest(row) != identity["native_sha256"] or normalize_name(player.name) not in canonical_names(identity):
        raise ValueError("active_player_row_changed")


def native_owner_verified(identity, active, original, mobile_cues):
    native = identity["native_player_id"]
    old = original.get(native)
    return bool(old and mobile_cues.get(native)
        and identity["registry"].get("commentary_owner_id") == native
        and normalize_name(old[1].name) in canonical_names(identity)
        and old[1].nationality_code == active[native][1].nationality_code)


def validate_source(identity, active, donor):
    base, native = identity["base_id"], identity["native_player_id"]
    if base not in donor:
        raise ValueError("source_database_id_absent")
    row, player = active[native]
    source_row, source = donor[base]
    if normalize_name(source.name) not in canonical_names(identity):
        raise ValueError("source_name_conflict")
    if (source.nationality_code != player.nationality_code
            or read_bits(source_row, 216, 8) != read_bits(row, 216, 8)
            or read_bits(source_row, 514, 1) != read_bits(row, 514, 1)
            or abs(read_bits(source_row, 408, 6) - read_bits(row, 408, 6)) > 2):
        raise ValueError("source_biography_conflict")


def remap_cue(name, source_id, native_id):
    if cue_identity(name) != source_id:
        raise ValueError("source_cue_identity_changed")
    if not 0 < native_id <= 999999:
        raise ValueError("native_label_translation_not_audited")
    result = re.sub(r"_R\d{6}(?=_|$)", f"_R{native_id:06d}", name)
    if cue_identity(result) != native_id:
        raise ValueError("native_cue_remap_failed")
    return result


def indexed_cues(top):
    names = top.child("CueNameTable").rows
    if len({row["CueName"] for row in names}) != len(names):
        raise ValueError("duplicate_source_cue_name")
    result = defaultdict(list)
    for row in names:
        owner = cue_identity(row["CueName"])
        if owner is not None:
            result[owner].append(dict(row))
    return dict(result)


def source_call_rows(tables, by_id, base, native):
    if base not in by_id:
        raise ValueError("source_recordings_absent")
    cues, waves = tables["CueTable"], tables["WaveformTable"]
    result = []
    for name in sorted(by_id[base], key=lambda row: row["CueName"]):
        cue = cues[name["CueIndex"]]
        if cue["ReferenceType"] != 1:
            raise ValueError("unsupported_source_cue_graph")
        wave = waves[cue["ReferenceIndex"]]
        if (wave["Streaming"] != 1 or wave["MemoryAwbId"] != 65535
                or wave["StreamAwbPortNo"] != 0 or wave["EncodeType"] != 2):
            raise ValueError("unsupported_source_waveform")
        result.append({"source_cue": name["CueName"],
            "native_cue": remap_cue(name["CueName"], base, native),
            "source_wave_id": wave["StreamAwbId"], "duration_ms": cue["Length"],
            "waveform": {field: wave[field] for field in
                ("EncodeType", "NumChannels", "LoopFlag", "SamplingRate", "NumSamples")}})
    return result


class AwbReader:
    """Index once, stream one bounded recording at a time; never extract AWB."""
    def __init__(self, path, member, base):
        self.path, self.start, self.size = Path(path), base + member["FileOffset"], member["FileSize"]
        with self.path.open("rb") as stream:
            stream.seek(self.start)
            header = stream.read(16)
            if len(header) != 16 or header[:4] != b"AFS2":
                raise ValueError("unsupported_awb_signature")
            width, id_width = header[5:7]
            count, alignment, subkey = struct.unpack_from("<IHH", header, 8)
            if width not in (2, 4) or id_width != 2 or not alignment or count > 65535 or subkey:
                raise ValueError("unsupported_awb_layout")
            metadata_size = count * id_width + (count + 1) * width
            if 16 + metadata_size > self.size:
                raise ValueError("awb_metadata_out_of_bounds")
            metadata = stream.read(metadata_size)
        if len(metadata) != metadata_size:
            raise ValueError("truncated_awb_metadata")
        self.index_sha256 = digest(header + metadata)
        ids = [int.from_bytes(metadata[i*2:i*2+2], "little") for i in range(count)]
        at = count * 2
        offsets = [int.from_bytes(metadata[at+i*width:at+(i+1)*width], "little") for i in range(count+1)]
        if len(set(ids)) != len(ids) or offsets != sorted(offsets):
            raise ValueError("ambiguous_awb_ids_or_offsets")
        self.ranges = {}
        for i, owner in enumerate(ids):
            first = (offsets[i] + alignment - 1) // alignment * alignment
            last = offsets[i+1]
            if not 16 + metadata_size <= first < last <= self.size:
                raise ValueError("awb_recording_out_of_bounds")
            self.ranges[owner] = first, last

    def read(self, ident):
        if ident not in self.ranges:
            raise ValueError("awb_recording_missing")
        first, last = self.ranges[ident]
        if last-first > MAX_RECORDING_BYTES:
            raise ValueError("source_recording_exceeds_bounded_staging_limit")
        with self.path.open("rb") as stream:
            stream.seek(self.start + first)
            result = stream.read(last - first)
        if len(result) != last - first or len(result) < 96 or result[:4] != b"HCA\0" or b"ciph\0\0" not in result[:96]:
            raise ValueError("unsupported_or_truncated_plaintext_hca")
        return result


def cache_valid(receipt, player_key, work):
    if receipt.get("player_key") != player_key or receipt.get("policy") != POLICY:
        return False
    try:
        for cue in receipt.get("cues", []):
            path = (work / cue["file"]).resolve()
            if not path.is_relative_to(work / "audio") or file_record(path) != cue["payload"]:
                return False
    except (OSError, KeyError, ValueError):
        return False
    return receipt.get("status") in {"staged_decode_verified", "diagnostic_hold"}


def stage_player(row, calls, source, decoder, work, source_key):
    # A resume proves its selected source bytes again before using a cache.
    # Keep only one player's bounded recordings resident, not the whole bank.
    payloads, actual_calls = {}, []
    try:
        for call in calls:
            ident = call["source_wave_id"]
            if ident not in payloads:
                payloads[ident] = source.read(ident)
                if sum(len(value) for value in payloads.values()) > MAX_PLAYER_BYTES:
                    raise ValueError("source_player_exceeds_bounded_staging_limit")
            payload = payloads[ident]
            record = {"bytes": len(payload), "sha256": digest(payload)}
            if call.get("source_payload", {}).get("bytes", len(payload)) != len(payload):
                raise ValueError("source_audio_size_changed_since_audit")
            actual_calls.append(dict(call, source_payload=record))
    except ValueError as error:
        player_key = key({"recipe": POLICY, "source": source_key, "identity": row,
                          "calls": calls, "source_hold": str(error)})
        receipt = dict(row, policy=POLICY, player_key=player_key, status="diagnostic_hold",
                       cues=[], reason=str(error), runtime_accepted=False, runtime_modified=False,
                       completed_utc=utc())
        write(work / "players" / str(row["base_id"]) / player_key / "complete.json", receipt)
        return receipt
    calls = actual_calls
    player_key = key({"recipe": POLICY, "source": source_key, "identity": row, "calls": calls})
    receipt_path = work / "players" / str(row["base_id"]) / player_key / "complete.json"
    if receipt_path.is_file():
        cached = read(receipt_path)
        if cache_valid(cached, player_key, work):
            return cached
    receipt = dict(row, policy=POLICY, player_key=player_key, status="staged_decode_verified",
                   cues=[], runtime_accepted=False, runtime_modified=False)
    try:
        for call in calls:
            payload = payloads[call["source_wave_id"]]
            record = {"bytes": len(payload), "sha256": digest(payload)}
            if call.get("source_payload", record) != record:
                raise ValueError("source_audio_changed_since_audit")
            relative = f"audio/{record['sha256']}.hca"
            path = work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            decode_path = path.with_suffix(".decode.json")
            payload_valid = path.is_file() and file_record(path) == record
            decoded = read(decode_path) if decode_path.is_file() else {}
            if not payload_valid:
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(payload); temporary.replace(path)
            if not payload_valid or decoded.get("source_key") != source_key or decoded.get("payload") != record:
                completed = subprocess.run([str(decoder), "-nostdin", "-v", "error", "-xerror",
                    "-err_detect", "explode", "-i", str(path), "-f", "null", "-"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
                if completed.returncode or completed.stderr:
                    raise ValueError("desktop_decode_failed: " + completed.stderr.decode("utf-8", "replace")[:500])
                write(decode_path, {"source_key": source_key, "payload": record,
                                   "decoder": str(decoder), "full_decode_exit_code": 0})
            if file_record(path) != record:
                raise ValueError("staged_audio_readback_failed")
            receipt["cues"].append(dict(call, file=relative, payload=record,
                plaintext_header_fnv64=f"{fnv64(payload[:96]):016x}"))
    except (ValueError, subprocess.TimeoutExpired) as error:
        receipt.update(status="diagnostic_hold", reason=str(error))
    receipt["completed_utc"] = utc()
    write(receipt_path, receipt)
    return receipt


def load_inputs(config):
    files = {name: Path(config[name]).resolve() for name in ("catalog", "selector", "team_include", "accepted_build_inputs", "identity_state",
        "active_database_cpk", "original_player_table", "mobile_cpk", "fl26_cpk", "fl26_database_cpk",
        "accepted_report", "accepted_delta", "decoder")}
    records = {}
    for name, path in files.items():
        if name in {"mobile_cpk", "fl26_cpk"}:
            # Hash every byte we actually use below, not multi-GB unrelated
            # recordings. Selected payload hashes also bind cache reuse.
            stat = path.stat()
            records[name] = {"bytes": stat.st_size, "last_write_ns": stat.st_mtime_ns,
                             "path": str(path)}
        else:
            records[name] = file_record(path)
        print(json.dumps({"phase": "input_identified", "input": name}), flush=True)
    if records["accepted_delta"] != config["accepted_delta_pin"]:
        raise ValueError("Accepted Yamal/Raphinha delta changed")
    print(json.dumps({"phase": "inputs_hashed", "files": len(records)}), flush=True)
    state = read(files["identity_state"])
    if state["build_id"] != config["runtime_pair_id"]:
        raise ValueError("Active runtime-pair identity changed")
    selector_text = files["selector"].read_text(encoding="utf-8-sig")
    if f'PES21_PLAYER_MIGRATION_BUILD_ID "{state["build_id"]}"' not in selector_text:
        raise ValueError("Selector is not the pinned runtime pair")
    catalog = read(files["catalog"])
    build_inputs = read(files["accepted_build_inputs"])
    for name in ("selector", "team_include"):
        relative = files[name].relative_to(ROOT).as_posix()
        if records[name] != build_inputs.get(relative):
            raise ValueError("Selector source differs from accepted runtime build inputs")
    validate_catalog_pair(catalog, files["team_include"].read_text(encoding="utf-8-sig"), state["build_id"])
    rosters = selector_rosters(selector_text)
    teams = ordered_teams(catalog)
    for row in teams:
        if row["team_id"] not in rosters:
            raise ValueError("Catalog team lacks active selector roster")
    active_index, active_base = index_cpk(files["active_database_cpk"])
    donor_index, donor_base = index_cpk(files["fl26_database_cpk"])
    active = player_rows(decoded_member(files["active_database_cpk"], active_index, active_base, DATABASE_MEMBER))
    donor = player_rows(decoded_member(files["fl26_database_cpk"], donor_index, donor_base, DATABASE_MEMBER))
    original = player_rows(decode_wesys(files["original_player_table"]))
    mi, mb = mobile_index(files["mobile_cpk"])
    fi, fb = index_cpk(files["fl26_cpk"])
    mobile_acb = cpk_member(files["mobile_cpk"], mi, mb, ACB_MEMBER)
    source_acb = cpk_member(files["fl26_cpk"], fi, fb, ACB_MEMBER)
    records["mobile_cpk"]["acb_sha256"] = digest(mobile_acb)
    records["fl26_cpk"]["acb_sha256"] = digest(source_acb)
    mobile_top, source_top = Utf(mobile_acb), Utf(source_acb)
    if mobile_top.rows[0]["Name"] != "10_PLAYER" or source_top.rows[0]["Name"] != "10_PLAYER":
        raise ValueError("Wrong commentary bank")
    mobile_cues, source_cues = indexed_cues(mobile_top), indexed_cues(source_top)
    source_tables = {name: source_top.child(name).rows for name in ("CueTable", "WaveformTable")}
    source = AwbReader(files["fl26_cpk"], fi[AWB_MEMBER], fb)
    records["fl26_cpk"]["awb_index_sha256"] = source.index_sha256
    accepted = read(files["accepted_report"])
    accepted_by_id = {row["base_id"]: row for row in accepted["identities"]}
    if set(accepted_by_id) != PROTECTED or accepted["delta_sha256"] != records["accepted_delta"]["sha256"]:
        raise ValueError("Accepted canary identity/delta proof changed")
    if (accepted["mobile_acb_sha256"] != records["mobile_cpk"]["acb_sha256"]
            or accepted["fl26_acb_sha256"] != records["fl26_cpk"]["acb_sha256"]):
        raise ValueError("Commentary ACB input differs from accepted source")
    native_owners = defaultdict(list)
    base_owners = defaultdict(list)
    values = state["identities"]
    for identity in values.values() if isinstance(values, dict) else values:
        if identity.get("status") == "active":
            native_owners[identity["native_player_id"]].append(identity)
            base_owners[identity["base_id"]].append(identity)
    rows = {}
    audio_ranges = {}
    for team in teams:
        for native in rosters[team["team_id"]]:
            if native in rows:
                rows[native]["team_ids"].append(team["team_id"])
                continue
            owners = native_owners.get(native, [])
            row = {"native_player_id": native, "team_ids": [team["team_id"]]}
            rows[native] = row
            if len(owners) != 1:
                row.update(status="identity_hold", reason="native_owner_absent_or_ambiguous")
                continue
            identity = owners[0]
            row.update(base_id=identity["base_id"], name=identity["name"], fingerprint=identity["fingerprint"],
                       active_row_sha256=identity["native_sha256"])
            try:
                if len(base_owners[identity["base_id"]]) != 1:
                    raise ValueError("base_owner_ambiguous")
                validate_active(identity, active)
            except ValueError as error:
                row.update(status="identity_hold", reason=str(error)); continue
            if identity["base_id"] in PROTECTED:
                protected = accepted_by_id[identity["base_id"]]
                if any(protected.get(k) != row[k] for k in ("native_player_id", "fingerprint", "active_row_sha256")):
                    raise ValueError("Protected canary active identity changed")
                row.update(status="accepted_canary_preserved", accepted_delta_sha256=records["accepted_delta"]["sha256"],
                           cue_count=sum(cue_identity(cue["cue"]) == identity["base_id"] for cue in accepted["cues"]))
                continue
            if native_owner_verified(identity, active, original, mobile_cues):
                row.update(status="native_preserved", cue_count=len(mobile_cues[native]),
                           original_row_sha256=digest(original[native][0]))
                continue
            try:
                validate_source(identity, active, donor)
                calls = source_call_rows(source_tables, source_cues, identity["base_id"], native)
                for call in calls:
                    ident = call["source_wave_id"]
                    if ident not in source.ranges:
                        raise ValueError("awb_recording_missing")
                    first, last = source.ranges[ident]
                    audio_ranges[ident] = {"first": first, "last": last}
                    call["source_payload"] = {"bytes": last-first}
                row.update(status="source_validated_pending_stage", source_row_sha256=digest(donor[identity["base_id"]][0]),
                           calls=calls, cue_count=len(calls), unsafe_mobile_cues_to_replace=len(mobile_cues.get(native, [])))
            except ValueError as error:
                row.update(status=("source_unavailable" if str(error) in {"source_database_id_absent", "source_recordings_absent"}
                                   else "source_or_translation_hold"), reason=str(error))
        print(json.dumps({"phase": "team_audited", "team_id": team["team_id"],
            "unique_players": len(rows), "source_recording_ranges_audited": len(audio_ranges)}), flush=True)
    proof = {"policy": POLICY, "runtime_pair_id": state["build_id"], "inputs": records,
        "recipe_sha256": file_record(Path(__file__))["sha256"], "teams": teams,
        "rosters": {str(team["team_id"]): rosters[team["team_id"]] for team in teams}, "players": list(rows.values()),
        "mobile_baseline_cue_count": sum(len(v) for v in mobile_cues.values()),
        "source_range_manifest_sha256": digest(json.dumps(audio_ranges, sort_keys=True).encode()),
        "source_payload_hashing": "exact selected audio hashed per player before staging/cache reuse",
        "runtime_bank_integration": "not_implemented; retain v53 limits and existing runtime",
        "runtime_modified": False, "device_acceptance": False}
    proof["input_key"] = key({k: proof[k] for k in ("policy", "runtime_pair_id", "inputs", "recipe_sha256",
                                                  "source_range_manifest_sha256")})
    return proof, source, files["decoder"]


def summarize(plan, results, completed_teams, phase, owner):
    audited = Counter(row["status"] for row in plan["players"])
    staged = Counter(row["status"] for row in results.values())
    return {"policy": POLICY, "phase": phase, "updated_utc": utc(), "owner": owner,
        "input_key": plan["input_key"], "teams_total": len(plan["teams"]), "teams_completed": completed_teams,
        "unique_players_audited": len(plan["players"]), "audit_counts": dict(audited),
        "unique_stage_results": len(results), "staging_counts": dict(staged),
        "recordings_staged_decode_verified": sum(len(row.get("cues", [])) for row in results.values()
                                                  if row["status"] == "staged_decode_verified"),
        "runtime_bank_integration": "pending; detached staging only", "runtime_accepted_players": 0,
        "existing_canary_preserved": True, "runtime_modified": False}


def run(config_path, *, audit_only=False, limit=None):
    config = read(config_path)
    if config.get("policy") != POLICY:
        raise ValueError("Explicit per-team commentary policy required")
    work = local_output(config["work_dir"])
    with exclusive(work):
        owner = {"pid": os.getpid(), "started_utc": utc(), "command": sys.argv,
                 "script": file_record(Path(__file__)), "config": file_record(config_path)}
        write(work / "OWNER.json", owner)
        write(work / "RUN-STATUS.json", {"phase": "hashing_and_auditing", "owner": owner, "updated_utc": utc()})
        plan, source, decoder = load_inputs(config)
        plan_path = work / "plans" / plan["input_key"] / "PLAN.json"
        write(plan_path, plan)
        write(work / "LATEST-PLAN.json", {"path": str(plan_path), "sha256": file_record(plan_path)["sha256"]})
        results = {}
        rows = {row["native_player_id"]: row for row in plan["players"]}
        completed_teams = 0
        if not audit_only:
            for team in plan["teams"]:
                if limit is not None and completed_teams >= limit:
                    break
                team_results = []
                for native in plan["rosters"][str(team["team_id"])]:
                    row = rows[native]
                    if native not in results:
                        if row["status"] == "source_validated_pending_stage":
                            calls = row["calls"]
                            clean = {k: v for k, v in row.items() if k != "calls"}
                            results[native] = stage_player(clean, calls, source, decoder, work, plan["input_key"])
                        else:
                            results[native] = row
                    team_results.append(results[native])
                completed_teams += 1
                team_proof = {"team": team, "input_key": plan["input_key"], "players": team_results,
                              "counts": dict(Counter(row["status"] for row in team_results)), "runtime_modified": False}
                write(work / "teams" / plan["input_key"] / f"{team['team_id']}.json", team_proof)
                status = summarize(plan, results, completed_teams, "staging", owner)
                write(work / "RUN-STATUS.json", status)
                print(json.dumps({"phase": "team_completed", "team_id": team["team_id"],
                    "team": team.get("display_name"), "teams_completed": completed_teams,
                    "teams_total": len(plan["teams"]), "counts": team_proof["counts"]}, ensure_ascii=True), flush=True)
        phase = ("audit_complete" if audit_only else "staging_complete_runtime_integration_pending"
                 if completed_teams == len(plan["teams"]) else "checkpoint_ready")
        status = summarize(plan, results, completed_teams, phase, owner)
        write(work / "RUN-STATUS.json", status)
        print(json.dumps(status, ensure_ascii=True), flush=True)
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("audit", "run", "status"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--max-teams", type=int)
    args = parser.parse_args()
    if args.max_teams is not None and args.max_teams <= 0:
        parser.error("--max-teams must be positive")
    if args.action == "status":
        print(json.dumps(read(local_output(read(args.config)["work_dir"]) / "RUN-STATUS.json"), ensure_ascii=True, indent=2))
    else:
        try:
            run(args.config, audit_only=args.action == "audit", limit=args.max_teams)
        except Exception as error:
            # A stale running receipt is explicitly terminal on normal failure.
            if not isinstance(error, RuntimeError) or "already owns" not in str(error):
                work = local_output(read(args.config)["work_dir"])
                write(work / "RUN-STATUS.json", {"phase": "failed", "updated_utc": utc(),
                      "pid": os.getpid(), "error": str(error), "runtime_modified": False})
            raise


if __name__ == "__main__":
    main()
