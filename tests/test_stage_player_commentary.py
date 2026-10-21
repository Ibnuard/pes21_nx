"""Player audio staging uses synthetic CRI tables; owned fixtures are optional."""
import copy
import json
import os
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from stage_player_commentary import (TABLES, TARGETS, audit_identities, build_bank,
    cue_identity, fnv64, rebuild_utf, sha, verify_preservation)
from stage_indonesia_commentary import HEADER, Utf, mobile_index, read_awb_wave
from build_fl26_cup_catalog import cpk_member, decoded_member, index_cpk
from convert_efootball10_players import write_bits
from pesdb import decode_wesys


def utf(rows, schema, constants=()):
    """Independent minimal UTF fixture writer with explicit field types."""
    strings = bytearray(b"fixture\0")
    data = bytearray()
    def text(value):
        at = len(strings)
        strings.extend(value.encode() + b"\0")
        return at
    formats = {0: ">B", 2: ">H", 4: ">I", 10: ">I", 11: ">II"}
    def value(kind, v):
        if kind == 10:
            v = text(v)
        elif kind == 11:
            at = len(data)
            data.extend(v)
            v = (at, len(v)) if v else (0, 0)
        return struct.pack(formats[kind], *(v if isinstance(v, tuple) else (v,)))
    descriptor = bytearray()
    for key, kind in schema:
        descriptor.extend(struct.pack(">BI", (0x30 if key in constants else 0x50) | kind, text(key)))
        if key in constants:
            descriptor.extend(value(kind, rows[0][key]))
    values = b"".join(value(kind, row[key]) for row in rows for key, kind in schema if key not in constants)
    stride = sum(struct.calcsize(formats[kind]) for key, kind in schema if key not in constants)
    row_start = 32 + len(descriptor)
    string_start = row_start + len(values)
    blob_start = string_start + len(strings)
    return struct.pack(">4sIIIIIHHI", b"@UTF", blob_start + len(data) - 8,
                       row_start - 8, string_start - 8, blob_start - 8,
                       0, len(schema), stride, len(rows)) + descriptor + values + strings + data


def bank(names, donor=False, break_graph=False):
    count = len(names)
    tables = {
        "CueTable": utf([dict(CueId=i, ReferenceType=1 if donor else 3,
                              ReferenceIndex=i, Length=900 + i) for i in range(count)],
                        [("CueId", 4), ("ReferenceType", 0), ("ReferenceIndex", 2), ("Length", 4)]),
        "CueNameTable": utf([dict(CueName=n, CueIndex=i) for i, n in enumerate(names)],
                            [("CueName", 10), ("CueIndex", 2)]),
    }
    wave_schema = [("MemoryAwbId" if donor else "Id", 2), ("EncodeType", 0),
                   ("Streaming", 0), ("NumChannels", 0), ("LoopFlag", 0),
                   ("SamplingRate", 4), ("NumSamples", 4)]
    if donor:
        wave_schema += [("StreamAwbPortNo", 2), ("StreamAwbId", 2)]
    waves = []
    for i in range(count):
        row = dict(EncodeType=2, Streaming=1, NumChannels=1, LoopFlag=0,
                   SamplingRate=48000, NumSamples=43200 + i)
        if donor:
            row.update(MemoryAwbId=65535, StreamAwbPortNo=0, StreamAwbId=i)
        else:
            row["Id"] = i
        waves.append(row)
    tables["WaveformTable"] = utf(waves, wave_schema, constants=("Streaming",))
    if not donor:
        tables.update({
            "SequenceTable": utf([dict(NumTracks=1, TrackIndex=struct.pack(">H", i)) for i in range(count)],
                                 [("NumTracks", 2), ("TrackIndex", 11)]),
            "TrackTable": utf([dict(EventIndex=0 if break_graph else i) for i in range(count)], [("EventIndex", 2)]),
            "SynthTable": utf([dict(ReferenceItems=struct.pack(">HH", 1, i)) for i in range(count)], [("ReferenceItems", 11)]),
            "CommandTable": utf([dict(Command=struct.pack(">HBHHHB", 2000, 4, 2, i, 0, 0)) for i in range(count)], [("Command", 11)]),
        })
    row = dict(Name="10_PLAYER", Version=123, **tables, AwbFile=b"", Unrelated=b"untouched bank metadata")
    return utf([row], [("Name", 10), ("Version", 4)] + [(key, 11) for key in (*tables, "AwbFile", "Unrelated")])


def audio(ident):
    header = bytearray(96)
    header[:4] = b"HCA\0"
    header[20:26] = b"ciph\0\0"
    header[30] = ident
    return bytes(header) + bytes([ident + 1]) * (10 + ident)


MOBILE_NAMES = ["EN_A1_P0_R111111", "EN_A1_P0_R110644", "EN_A1_PPA_R110644_01"]
DONOR_NAMES = ["EN_A1_P0_R110644", "EN_A1_P0_R162114", "EN_B1_P0_R162114"]


def build(base=None, donor=None, reader=audio, owners=None):
    return build_bank(base or bank(MOBILE_NAMES), donor or bank(DONOR_NAMES, donor=True), reader,
                      targets=set(TARGETS), preserved_mobile_ids={110644} if owners is None else owners)


def result_from_delta(delta):
    assert HEADER.unpack_from(delta)[5] == 1
    offset, size = struct.unpack_from("<II", delta, HEADER.size)
    assert offset == 0 and len(delta) == HEADER.size + 8 + size
    return delta[HEADER.size + 8:]


def test_new_cues_preserve_original_graph_and_exact_recordings():
    base = bank(MOBILE_NAMES)
    delta, report = build(base)
    result = result_from_delta(delta)
    assert report["result_cues"] == 5
    assert report["unaffected_original_cues"] == 2
    assert report["preserved_mobile_only_cues"] == [MOBILE_NAMES[2]]
    assert report["base_fnv64"] == f"{fnv64(base):016x}"
    assert report["result_fnv64"] == f"{fnv64(result):016x}"
    top = Utf(result)
    names = top.child("CueNameTable").rows
    assert [r["CueName"] for r in names] == sorted(MOBILE_NAMES + DONOR_NAMES[1:])
    mapping = {r["CueName"]: r["CueIndex"] for r in names}
    for name in MOBILE_NAMES:
        assert mapping[name] == MOBILE_NAMES.index(name)
    waves = top.child("WaveformTable").rows
    assert waves[0]["Streaming"] == waves[2]["Streaming"] == 1
    assert waves[1]["Streaming"] == waves[3]["Streaming"] == waves[4]["Streaming"] == 0
    for i, recording in enumerate(report["cues"]):
        assert recording["audio_sha256"] == sha(audio(i))
        assert audio(i) in top.blob(0, "AwbFile")
    assert top.blob(0, "Unrelated") == b"untouched bank metadata"
    assert build(base)[0] == delta


def test_missing_mobile_ownership_is_rejected():
    with pytest.raises(ValueError, match="unverified Mobile-only"):
        build(owners=set())


def test_source_missing_identity_or_duplicate_cue_is_rejected():
    with pytest.raises(ValueError, match="missing FL26"):
        build(donor=bank(DONOR_NAMES[:1], donor=True))
    with pytest.raises(ValueError, match="duplicate FL26"):
        build(donor=bank(DONOR_NAMES + DONOR_NAMES[:1], donor=True))


def test_shared_graph_and_encrypted_source_are_rejected():
    with pytest.raises(ValueError, match="unexpected mobile audio graph"):
        build(base=bank(MOBILE_NAMES, break_graph=True))
    with pytest.raises(ValueError, match="plaintext HCA"):
        build(reader=lambda ident: b"HCA\0" + bytes(100))


@pytest.mark.parametrize("name,ident", [("EN_A1_P0_R162114", 162114),
    ("EN_A1B1_PMB_R162114_02", 162114), ("EN_B1_PMA_R162114_01", 162114),
    ("EN_A1_T0_R162114", None), ("EN_A1_P0_R162114junk", None),
    ("EN_A1_P0_R162114_001", None), ("EN_A1_P0_R162114_01.bak", None)])
def test_cue_identity_exact_grammar(name, ident):
    assert cue_identity(name) == ident


def test_constant_promotes_and_binary_values_survive_utf_rebuild():
    original = Utf(utf([{"Name": "first", "Mode": 1, "Data": b"one"},
                        {"Name": "second", "Mode": 1, "Data": b"two"}],
                       [("Name", 10), ("Mode", 0), ("Data", 11)], constants=("Mode",)))
    rows = [dict(r) for r in original.rows]
    rows.append({"Name": "new", "Mode": 0, "Data": b"three"})
    rebuilt = Utf(rebuild_utf(original, rows))
    assert [r["Mode"] for r in rebuilt.rows] == [1, 1, 0]
    assert [rebuilt.blob(i, "Data") for i in range(3)] == [b"one", b"two", b"three"]


def identity_fixture():
    records, identities = [], []
    for base_id, target in TARGETS.items():
        row = bytearray(312)
        struct.pack_into("<I", row, 8, base_id)
        row[251:251 + len(target["name"])] = target["name"].encode()
        struct.pack_into("<H", row, 29, target["pc_country"])
        write_bits(row, 216, 8, (176 if base_id == 110644 else 180) - 100)
        write_bits(row, 514, 1, 1)
        write_bits(row, 408, 6, (29 if base_id == 110644 else 18) - 15)
        records.append(bytes(row))
        identities.append(dict(base_id=base_id, name=target["name"], native_player_id=base_id,
            status="active", native_identity_verified=True, native_sha256=sha(row),
            fingerprint=target["fingerprint"], country=146 if base_id == 110644 else 236,
            height=176 if base_id == 110644 else 180, foot=1,
            registry={"commentary_owner_id": base_id if base_id == 110644 else None}))
    return {"identities": identities}, b"".join(records)


def test_baseid_fingerprint_biography_and_original_owner_are_required():
    state, data = identity_fixture()
    report = audit_identities(state, data, data, data[:312])
    assert [r["mobile_original_owner_verified"] for r in report] == [True, False]
    stale = copy.deepcopy(state)
    stale["identities"][1]["fingerprint"] = "reused native slot"
    with pytest.raises(ValueError, match="fingerprint changed"):
        audit_identities(stale, data, data, data)
    altered = bytearray(data)
    altered[251] = ord("X")
    with pytest.raises(ValueError, match="identity state"):
        audit_identities(state, bytes(altered), data, data)
    donor = bytearray(data)
    donor[312 + 29] ^= 1
    with pytest.raises(ValueError, match="biography"):
        audit_identities(state, data, bytes(donor), data)


def test_local_owned_candidate_determinism_and_preservation():
    output = os.environ.get("PESNX_PLAYER_COMMENTARY_CANDIDATE")
    if not output:
        pytest.skip("set PESNX_PLAYER_COMMENTARY_CANDIDATE to ignored staged owned inputs")
    staged = Path(output)
    mobile_path = ROOT / "dist/pes21_nx/Download/dt510_mobile_eng_all.cpk"
    donor_path = Path(os.environ.get("PESNX_FL26_COMMENTARY_CPK", "D:/Games/SP Football Life 2026/Data/dt41_eng_all.cpk"))
    mobile, mb = mobile_index(mobile_path)
    donor, db = index_cpk(donor_path)
    member = "eng/sound/acb/10_PLAYER.acb"
    delta, report = build_bank(cpk_member(mobile_path, mobile, mb, member),
        cpk_member(donor_path, donor, db, member), lambda ident: read_awb_wave(
            donor_path, donor["eng/sound/awb/10_PLAYER.awb"], db, ident),
        targets=set(TARGETS), preserved_mobile_ids={110644})
    assert delta == (staged / "Commentary/players-yamal-raphinha.nxcp").read_bytes()
    saved = json.loads((staged / "player-commentary-report.local.json").read_text())
    assert all(saved[k] == v for k, v in report.items())
    assert (report["original_cues"], report["result_cues"], len(report["cues"])) == (64000, 64019, 27)
