"""Identity, source ownership, serial cache and bank-limit boundaries."""
import copy
import json
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import batch_player_commentary as batch
from test_stage_player_commentary import audio, bank, identity_fixture


def test_active_row_fingerprint_registry_and_native_slot_must_agree():
    state, data = identity_fixture()
    identity = copy.deepcopy(state["identities"][0])
    identity["registry"].update(fingerprint=identity["fingerprint"],
        ef_base_id=identity["base_id"], native_player_id=identity["native_player_id"])
    rows = batch.player_rows(data)
    batch.validate_active(identity, rows)
    bad = copy.deepcopy(identity)
    bad["registry"]["ef_base_id"] = 162114
    with pytest.raises(ValueError, match="fingerprint"):
        batch.validate_active(bad, rows)
    bad = copy.deepcopy(identity)
    bad["native_sha256"] = "wrong current identity"
    with pytest.raises(ValueError, match="row_changed"):
        batch.validate_active(bad, rows)


def test_native_preservation_requires_original_owner_and_real_calls():
    state, data = identity_fixture()
    owner = state["identities"][0]
    rows = batch.player_rows(data)
    assert batch.native_owner_verified(owner, rows, rows, {110644: ["call"]})
    assert not batch.native_owner_verified(owner, rows, rows, {})
    changed = copy.deepcopy(owner)
    changed["registry"]["commentary_owner_id"] = None
    assert not batch.native_owner_verified(changed, rows, rows, {110644: ["call"]})
    changed["registry"]["commentary_owner_id"] = 110644
    changed["name"] = "Different Player"
    assert not batch.native_owner_verified(changed, rows, rows, {110644: ["call"]})


def test_source_numeric_id_alone_never_authorizes_recording():
    state, data = identity_fixture()
    rows = batch.player_rows(data)
    identity = state["identities"][1]
    batch.validate_source(identity, rows, rows)
    bad = bytearray(data)
    bad[312 + 251] = ord("X")
    with pytest.raises(ValueError, match="name_conflict"):
        batch.validate_source(identity, rows, batch.player_rows(bytes(bad)))
    with pytest.raises(ValueError, match="database_id_absent"):
        batch.validate_source(identity, rows, {})


def test_explicit_native_rekey_preserves_context_and_rejects_unproved_high_ids():
    assert batch.remap_cue("EN_A1B1_PMB_R162114_02", 162114, 558293) == "EN_A1B1_PMB_R558293_02"
    with pytest.raises(ValueError, match="identity_changed"):
        batch.remap_cue("EN_A1_P0_R110644", 162114, 558293)
    with pytest.raises(ValueError, match="translation_not_audited"):
        batch.remap_cue("EN_A1_P0_R162114", 162114, 1074403204)


def test_selector_roster_and_catalog_order_cover_every_team_once():
    text = "static const uint32_t exhibition_migration_team_108_players[] = {162114u, 110644u};"
    assert batch.selector_rosters(text) == {108: [162114, 110644]}
    with pytest.raises(ValueError, match="duplicate selector"):
        batch.selector_rosters(text + text)
    catalog = {"teams": [{"team_id": 1}, {"team_id": 108}],
               "categories": [{"team_ids": [108, 1]}, {"team_ids": [1]}]}
    assert [r["team_id"] for r in batch.ordered_teams(catalog)] == [108, 1]
    catalog["teams"].append({"team_id": 999})
    with pytest.raises(ValueError, match="uncategorized"):
        batch.ordered_teams(catalog)


def test_actual_compiled_pair_binds_catalog_not_historical_migration_parent():
    catalog = {"content_id": "catalog-v1", "migration_build_id": "old-parent",
               "categories": [{"key": "english_league", "team_ids": [108, 1]}]}
    text = "// Catalog content ID: catalog-v1\n// Paired loose CPK build ID: runtime-v2\n"
    text += "static const uint32_t exhibition_category_english_league_teams[] = {108u, 1u};"
    batch.validate_catalog_pair(catalog, text, "runtime-v2")
    with pytest.raises(ValueError, match="catalog/runtime pair"):
        batch.validate_catalog_pair(catalog, text, "old-parent")
    catalog["categories"][0]["team_ids"] = [1, 108]
    with pytest.raises(ValueError, match="category arrays differ"):
        batch.validate_catalog_pair(catalog, text, "runtime-v2")


def test_direct_graph_and_plaintext_ownership_are_pinned():
    top = batch.Utf(bank(["EN_A1_P0_R162114"], donor=True))
    names = batch.indexed_cues(top)
    tables = {name: top.child(name).rows for name in ("CueTable", "WaveformTable")}
    calls = batch.source_call_rows(tables, names, 162114, 558293)
    assert calls[0]["native_cue"] == "EN_A1_P0_R558293"
    tables["CueTable"][0]["ReferenceType"] = 3
    with pytest.raises(ValueError, match="unsupported_source_cue_graph"):
        batch.source_call_rows(tables, names, 162114, 558293)


def awb(path, payload, *, duplicated=False):
    # Independently authored minimal AFS2 fixture, one metadata block.
    count = 2 if duplicated else 1
    header = struct.pack("<4s4BIHH", b"AFS2", 2, 4, 2, 0, count, 32, 0)
    ids = struct.pack("<" + "H" * count, *([7] * count))
    start = 32
    offsets = struct.pack("<" + "I" * (count + 1), *([start] * count + [start + len(payload)]))
    out = header + ids + offsets
    path.write_bytes(out + bytes(start-len(out)) + payload)
    return {"FileOffset": 0, "FileSize": path.stat().st_size}


def test_awb_streaming_index_bounds_duplicate_ids_and_no_archive_copy(tmp_path):
    source = tmp_path / "source.cpk"
    member = awb(source, audio(0))
    reader = batch.AwbReader(source, member, 0)
    assert reader.read(7) == audio(0)
    with pytest.raises(ValueError, match="missing"):
        reader.read(8)
    awb(source, audio(0), duplicated=True)
    with pytest.raises(ValueError, match="ambiguous"):
        batch.AwbReader(source, {"FileOffset": 0, "FileSize": source.stat().st_size}, 0)


def test_cached_payload_reuse_and_tamper_detection(tmp_path):
    work = tmp_path.resolve()
    payload = audio(0)
    source_calls = {"reads": 0}
    class Source:
        def read(self, ident):
            source_calls["reads"] += 1
            return payload
    class Completed:
        returncode = 0
        stderr = b""
    old = batch.subprocess.run
    batch.subprocess.run = lambda *args, **kwargs: Completed()
    try:
        calls = [{"source_wave_id": 7, "native_cue": "EN_A1_P0_R558293"}]
        row = {"base_id": 162114, "native_player_id": 558293, "fingerprint": "explicit"}
        a = batch.stage_player(row, calls, Source(), Path("decoder"), work, "source-key")
        b = batch.stage_player(row, calls, Source(), Path("decoder"), work, "source-key")
        assert a == b and source_calls["reads"] == 2  # source bytes checked again, no re-decode
        assert a["status"] == "staged_decode_verified" and not a["runtime_accepted"]
        (work / a["cues"][0]["file"]).write_bytes(b"different identity")
        c = batch.stage_player(row, calls, Source(), Path("decoder"), work, "source-key")
        assert c["cues"][0]["payload"] == a["cues"][0]["payload"] and source_calls["reads"] == 3
    finally:
        batch.subprocess.run = old


def test_deterministic_decode_failure_is_held_without_retry(tmp_path, monkeypatch):
    class Source:
        def read(self, ident):
            return audio(0)
    calls = {"count": 0}
    class Completed:
        returncode = 1
        stderr = b"bad codec"
    def failed(*args, **kwargs):
        calls["count"] += 1
        return Completed()
    monkeypatch.setattr(batch.subprocess, "run", failed)
    row = {"base_id": 162114, "native_player_id": 558293}
    selected = [{"source_wave_id": 7}]
    one = batch.stage_player(row, selected, Source(), Path("decoder"), tmp_path, "source-key")
    two = batch.stage_player(row, selected, Source(), Path("decoder"), tmp_path, "source-key")
    assert one == two and one["status"] == "diagnostic_hold" and calls["count"] == 1


def test_lock_prevents_duplicate_runner_and_releases_after_exception(tmp_path):
    with batch.exclusive(tmp_path):
        with pytest.raises(RuntimeError, match="already owns"):
            with batch.exclusive(tmp_path):
                pass
    with batch.exclusive(tmp_path):
        pass


def test_existing_runtime_limits_are_not_enlarged_by_batch():
    # The detached staging path intentionally never emits a runtime nxcp bank.
    source = (ROOT / "tools/batch_player_commentary.py").read_text(encoding="utf-8")
    assert "player_commentary_catalog.h" not in source
    assert "build_bank(" not in source
    from stage_player_commentary import MAX_BANK, MAX_PATCH
    assert MAX_BANK == MAX_PATCH == 8 * 1024 * 1024
