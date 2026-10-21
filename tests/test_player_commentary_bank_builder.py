"""Actual bounded C UTF/AWB builder versus independently parsed Python oracle."""
from pathlib import Path
import copy
import json
import os
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_player_commentary_roster_pack import c_header, oracle, awb_waves
import build_player_commentary_roster_pack as pack_builder
from stage_indonesia_commentary import Utf, fnv64, memory_awb
from stage_player_commentary import TABLES, kinds, rebuild_utf
from pack_runtime_assets import HEADER, ENTRY, MAGIC
from test_stage_player_commentary import bank, audio


def fixture():
    raw = Utf(bank(["EN_A1_P0_R100000", "EN_A1_P0_R300000"]))
    outer = dict(raw.rows[0])
    for name, kind in kinds(raw).items():
        if kind == 11:
            outer[name] = raw.blob(0, name)
    outer["AwbFile"] = memory_awb([(1, audio(7))])
    base = rebuild_utf(raw, [outer], compact_blobs=True)
    cues = []
    for name, kind, ident in [("EN_A1_P0_R100000", 0, 1), ("EN_B1_P0_R100000", 24, 2)]:
        payload = audio(ident)
        cues.append(dict(owner_index=0, type=kind, name=name, asset=f"audio/{ident}.hca", bytes=len(payload),
            duration_ms=1000 + ident, waveform=dict(EncodeType=2, NumChannels=1, LoopFlag=0,
            SamplingRate=48000, NumSamples=48000 + ident), payload_fnv=f"{fnv64(payload):016x}",
            header_fnv=f"{fnv64(payload[:96]):016x}"))
    catalog = dict(runtime_pair="fixture", base_bytes=len(base), base_fnv=f"{fnv64(base):016x}",
        baseline_headers=[f"{fnv64(audio(7)[:96]):016x}"],
        owners=[dict(base_id=111, native_player_id=100000, fingerprint="a" * 20,
            active_row_sha256="b" * 64, status=3, cue_first=0, cue_count=2),
            dict(base_id=222, native_player_id=200000, fingerprint="c" * 20,
            active_row_sha256="d" * 64, status=4, cue_first=2, cue_count=0),
            dict(base_id=333, native_player_id=300000, fingerprint="e" * 20,
            active_row_sha256="f" * 64, status=2, cue_first=2, cue_count=0)], cues=cues)
    return base, catalog, {"audio/1.hca": audio(1), "audio/2.hca": audio(2)}


def archive(path, assets):
    cursor = HEADER.size + ENTRY.size * len(assets)
    entries = []
    for name, payload in sorted(assets.items()):
        entries.append(ENTRY.pack(name.encode(), cursor, len(payload), fnv64(payload), 0, 0))
        cursor += len(payload)
    path.write_bytes(HEADER.pack(MAGIC, len(assets), ENTRY.size, cursor, HEADER.size + ENTRY.size * len(assets)) +
        b"".join(entries) + b"".join(v for _, v in sorted(assets.items())))


def run_c(tmp_path, base, catalog, assets, ids=(100000, 200000, 300000), body=""):
    cc = shutil.which("gcc")
    if not cc:
        pytest.skip("host gcc unavailable")
    (tmp_path / "catalog.h").write_text(c_header(catalog), encoding="utf-8")
    (tmp_path / "base.acb").write_bytes(base)
    archive(tmp_path / "pack.nxpa", assets)
    code = r'''
#include <stdio.h>
#include <assert.h>
#include "player_commentary_bank_builder.h"
#include "runtime_assets.h"
#include "catalog.h"
static void *reader(void *ctx,const char *name,size_t cap,size_t *n) {
  return nx_asset_read_archive((const char *)ctx,name,cap,n);
}
int main(void) {
 FILE *f=fopen("base.acb","rb");assert(f);fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
 unsigned char *base=malloc(n);assert(base);assert(fread(base,1,n,f)==(size_t)n);fclose(f);
 PcBankCatalog catalog=player_commentary_roster_catalog;
 PcBankResult result;
 uint32_t ids[]={IDS};
 BODY
 int ok=pc_bank_build(base,n,&catalog,ids,sizeof(ids)/sizeof(ids[0]),reader,"pack.nxpa",&result);
 if(ok) {f=fopen("out.acb","wb");assert(f);fwrite(result.data,1,result.size,f);fclose(f);
  printf("%u %u %u %u %zu\n",result.size,result.cue_count,result.player_count,result.header_count,result.scratch_peak);
  assert(result.scratch_peak<=PC_BANK_MAX_SCRATCH);pc_bank_free(&result);
 } else { assert(!result.data && !result.size && !result.header_count);puts("rejected"); }
 free(base);return 0;
}
'''.replace("IDS", ",".join(str(i) for i in ids)).replace("BODY", body)
    (tmp_path / "test.c").write_text(code, encoding="utf-8")
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
        "-I", (ROOT / "source").as_posix(), (tmp_path / "test.c").as_posix(), "-o", (tmp_path / "test.exe").as_posix()], check=True,
        capture_output=True)
    return subprocess.run([str(tmp_path / "test.exe")], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()


def same_semantics(a, b):
    x, y = Utf(a), Utf(b)
    for name in TABLES:
        u, v = x.child(name), y.child(name)
        assert len(u.rows) == len(v.rows)
        for i, row in enumerate(u.rows):
            for key, kind in kinds(u).items():
                if kind == 11:
                    assert u.blob(i, key) == v.blob(i, key), (name, i, key)
                else:
                    assert row[key] == v.rows[i][key], (name, i, key)
    assert awb_waves(x.blob(0, "AwbFile")) == awb_waves(y.blob(0, "AwbFile"))
    assert x.blob(0, "Unrelated") == y.blob(0, "Unrelated")


def test_c_actual_reconstruction_matches_python_graph_canary_and_static_names(tmp_path):
    base, catalog, assets = fixture()
    status = run_c(tmp_path, base, catalog, assets, ids=(300000, 100000, 100000, 200000))
    assert status.split()[1:4] == ["2", "3", "3"]
    expected, changed = oracle(base, catalog, [100000, 300000, 200000], assets.__getitem__)
    actual = (tmp_path / "out.acb").read_bytes()
    same_semantics(expected, actual)
    assert awb_waves(Utf(actual).blob(0, "AwbFile"))[1] == audio(7)
    assert len(changed) == 2


@pytest.mark.parametrize("mutation", ["base", "audio", "header", "missing", "owner", "cuecount", "overflow", "wrong_name", "wrong_context", "fingerprint"])
def test_rejects_corruption_identity_graph_limits_and_missing_optional_data(tmp_path, mutation):
    base, catalog, assets = fixture()
    body = ""
    if mutation == "base":
        base = base[:40] + bytes([base[40] ^ 1]) + base[41:]
    elif mutation == "audio":
        assets["audio/1.hca"] = assets["audio/1.hca"][:-1] + b"X"
    elif mutation == "header":
        catalog["cues"][0]["header_fnv"] = "0" * 16
    elif mutation == "missing":
        del assets["audio/1.hca"]
    elif mutation == "owner":
        catalog["cues"][0]["owner_index"] = 1
    elif mutation == "cuecount":
        catalog["owners"][0]["cue_count"] = 3
    elif mutation == "overflow":
        catalog["cues"][0]["bytes"] = 2 * 1024 * 1024 + 1
    elif mutation == "wrong_name":
        catalog["cues"][0]["name"] = "EN_A1_P0_R999999"
    elif mutation == "wrong_context":
        catalog["cues"][0]["type"] = 24
    else:
        catalog["owners"][0]["fingerprint"] = ""
    assert run_c(tmp_path, base, catalog, assets, body=body) == "rejected"


def test_held_and_native_owners_do_not_read_or_import_recordings(tmp_path):
    base, catalog, assets = fixture()
    status = run_c(tmp_path, base, catalog, {}, ids=(200000, 300000))
    assert status.split()[1:4] == ["0", "2", "1"]
    assert awb_waves(Utf((tmp_path / "out.acb").read_bytes()).blob(0, "AwbFile"))[1] == audio(7)


def test_malformed_utf_rejected_even_with_matching_recomputed_bank_hash(tmp_path):
    base, catalog, assets = fixture()
    broken = bytearray(base)
    struct.pack_into(">I", broken, 16, len(base) + 99)
    catalog["base_fnv"] = f"{fnv64(broken):016x}"
    assert run_c(tmp_path, bytes(broken), catalog, assets) == "rejected"


def test_81_raw_ids_rejected_before_catalog_or_audio_access(tmp_path):
    base, catalog, assets = fixture()
    assert run_c(tmp_path, base, catalog, assets, ids=tuple(range(81))) == "rejected"


def test_null_optional_base_or_catalog_storage_returns_empty_failure(tmp_path):
    base, catalog, assets = fixture()
    body = '''
 PcBankResult empty;
 assert(!pc_bank_build(NULL,n,&catalog,ids,3,reader,"pack.nxpa",&empty));
 assert(!empty.data && !empty.size);
 PcBankCatalog missing=catalog;missing.owners=NULL;
 assert(!pc_bank_build(base,n,&missing,ids,3,reader,"pack.nxpa",&empty));
 assert(!empty.data && !empty.size);
 missing=catalog;missing.cues=NULL;
 assert(!pc_bank_build(base,n,&missing,ids,3,reader,"pack.nxpa",&empty));
 missing=catalog;missing.baseline_headers=NULL;
 assert(!pc_bank_build(base,n,&missing,ids,3,reader,"pack.nxpa",&empty));
'''
    assert run_c(tmp_path, base, catalog, assets, body=body) != "rejected"


def test_availability_marker_is_bounded_exact_and_preserves_all_recordings(tmp_path, monkeypatch):
    _, catalog, assets = fixture()
    catalog["runtime_pair"] = "0123456789abcdef"
    (tmp_path / "catalog.local.json").write_text(json.dumps(catalog))
    archive(tmp_path / "players-v59.nxpa", assets)
    monkeypatch.setattr(pack_builder, "local_output", lambda p: Path(p))
    result = pack_builder.ensure_marker(tmp_path)
    first = (tmp_path / "players-v59.nxpa").read_bytes()
    assert result == {"asset": "catalog-id.txt", "bytes": 17, "ascii": "0123456789abcdef\n"}
    pack_builder.ensure_marker(tmp_path)
    assert (tmp_path / "players-v59.nxpa").read_bytes() == first
    with (tmp_path / "players-v59.nxpa").open("rb") as stream:
        _, count, stride, _, _ = HEADER.unpack(stream.read(HEADER.size))
        entries = [ENTRY.unpack(stream.read(stride)) for _ in range(count)]
        for name, at, size, expected, _, _ in entries:
            stream.seek(at)
            data = stream.read(size)
            assert fnv64(data) == expected
            key = name.split(b"\0", 1)[0].decode()
            assert data == (result["ascii"].encode() if key == "catalog-id.txt" else assets[key])


def test_metadata_only_exact_size_matches_actual_c_without_reading_audio(tmp_path, monkeypatch):
    base, catalog, assets = fixture()
    status = run_c(tmp_path, base, catalog, assets)
    (tmp_path / "catalog.local.json").write_text(json.dumps(catalog))
    (tmp_path / "accepted-v53.acb").write_bytes(base)
    plan = {"rosters": {"1": [100000, 200000], "2": [300000]},
            "teams": [{"team_id": 1, "display_name": "one"}, {"team_id": 2, "display_name": "two"}]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "LATEST-PLAN.json").write_text(json.dumps({"path": str(tmp_path / "plan.json")}))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"work_dir": str(tmp_path)}))
    monkeypatch.setattr(pack_builder, "local_output", lambda p: Path(p))
    result = pack_builder.metadata_costs(config, tmp_path)
    assert result["pairs_examined"] == 1
    assert result["source_audio_reads"] == result["pair_banks_constructed"] == 0
    assert result["max_bank"]["bank_bytes"] == int(status.split()[0])
    assert result["max_scratch"]["scratch_peak"] == int(status.split()[4])
