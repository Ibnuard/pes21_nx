"""Composition invariants with small authored archives, never owned game data."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_trophy_ceremony as stage


class Archive:
    def __init__(self, path, members):
        self.path, self.base, self.index = path, 0, {}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as output:
            for index, (name, data) in enumerate(members.items()):
                self.index[name] = {"ID": index, "FileOffset": output.tell(),
                                    "FileSize": len(data), "ExtractSize": len(data)}
                output.write(data)

    def read(self, name):
        return stage.raw_member(self, name)


@pytest.fixture
def archives(tmp_path):
    old = {stage.ENTRANCE_TABLE: b"working walkout", stage.TABLE: b"native endings",
           "retained.bin": b"unchanged fixture", "walkout-motion.gani": b"player motion"}
    payloads = {stage.TABLE: b"native + trophy endings", "trophy-motion.gani": b"cup motion"}
    new = dict(old)
    new[stage.TABLE] = payloads[stage.TABLE]
    new.update({n: payloads[n] for n in sorted(set(payloads) - set(old))})
    return Archive(tmp_path / "base.cpk", old), Archive(tmp_path / "new.cpk", new), payloads


def test_composition_preserves_walkout_ids_order_and_stored_bytes(archives):
    base, final, payloads = archives
    assert stage.check_composition_members(base, final, payloads, stage.TABLE) == len(base.index) - 1
    assert final.read(stage.ENTRANCE_TABLE) == base.read(stage.ENTRANCE_TABLE)


@pytest.mark.parametrize("mutation", ["id", "collision", "order", "missing", "unrelated", "size", "extract", "payload", "replace"])
def test_composition_rejects_intro_or_unrelated_archive_damage(archives, mutation):
    base, final, payloads = archives
    if mutation == "id":
        final.index[stage.ENTRANCE_TABLE]["ID"] += 1
    elif mutation == "collision":
        final.index["trophy-motion.gani"]["ID"] = final.index["walkout-motion.gani"]["ID"]
    elif mutation == "order":
        final.index = dict(reversed(list(final.index.items())))
    elif mutation == "missing":
        del final.index[stage.ENTRANCE_TABLE]
    elif mutation == "unrelated":
        raw = bytearray(final.path.read_bytes())
        raw[0] ^= 1
        final.path.write_bytes(raw)
    elif mutation == "size":
        final.index[stage.ENTRANCE_TABLE]["FileSize"] -= 1
    elif mutation == "extract":
        final.index[stage.ENTRANCE_TABLE]["ExtractSize"] += 1
    elif mutation == "payload":
        payloads[stage.TABLE] = b"different ending"
    else:
        payloads[stage.ENTRANCE_TABLE] = b"native entrance replacing working walkout"
    with pytest.raises(ValueError):
        stage.check_composition_members(base, final, payloads, stage.TABLE)


@pytest.fixture
def detached(tmp_path, monkeypatch):
    native_rows = {stage.ENTRANCE_TABLE: b"native intro", stage.TABLE: b"native ending", "keep.bin": b"keep"}
    native = Archive(tmp_path / "native/LooseCpk/dt220_mobile_all.cpk", native_rows)
    (native.path.parent / "manifest.txt").write_bytes(b"native manifest identity")
    baseline = {"version": 2, "build_id": stage.BASELINE_BUILD, "files": [
        {"name": native.path.name, "size": native.path.stat().st_size, "sha256": stage.file_digest(native.path)}]}
    monkeypatch.setattr(stage, "BASELINE_DT220_SHA256", stage.file_digest(native.path))
    monkeypatch.setattr(stage, "BASELINE_MANIFEST_SHA256", stage.file_digest(native.path.parent / "manifest.txt"))
    manifests = {native.path.parent.parent: baseline}
    cpks = {native.path: native}
    paths = []
    for tag, table, count, schema, status, constant in (
        ("walkout", stage.ENTRANCE_TABLE, 50, "PESNX_ENTRANCE_WALKOUT_CANARY_V1",
         "experimental_hardware_candidate", "WALKOUT_DT220_SHA256"),
        ("trophy", stage.TABLE, 28, "PESNX_TROPHY_ASSETS_V1", "asset_only_not_playable", "TROPHY_DT220_SHA256")):
        payloads = {table: ("new " + tag).encode()}
        payloads.update({f"{tag}-{i:02d}.gani": f"{tag} motion {i}".encode() for i in range(count - 1)})
        rows = dict(native_rows)
        rows[table] = payloads[table]
        rows.update({n: payloads[n] for n in sorted(set(payloads) - set(rows))})
        cpk = Archive(tmp_path / tag / "update/LooseCpk/dt220_mobile_all.cpk", rows)
        cpks[cpk.path] = cpk
        checksum = stage.file_digest(cpk.path)
        monkeypatch.setattr(stage, constant, checksum)
        manifest = copy.deepcopy(baseline)
        manifest["files"][0].update(size=cpk.path.stat().st_size, sha256=checksum)
        manifests[cpk.path.parent.parent] = manifest
        report = {"schema": schema, "status": status, "baseline_root": str(native.path.parent.parent),
                  "baseline_dt220_sha256": stage.BASELINE_DT220_SHA256, "baseline_build_id": stage.BASELINE_BUILD,
                  "baseline_manifest_sha256": stage.BASELINE_MANIFEST_SHA256,
                  "validation": {"candidate_sha256": checksum, "size": cpk.path.stat().st_size},
                  "payloads": [{"name": n, "bytes": len(b), "sha256": stage.digest(b)} for n, b in payloads.items()]}
        report_path = tmp_path / tag / (tag + "-report.json")
        report_path.write_text(json.dumps(report), encoding="utf-8")
        paths.append(report_path)
    monkeypatch.setattr(stage, "Cpk", lambda p: cpks[Path(p)])
    monkeypatch.setattr(stage, "read_manifest", lambda p: copy.deepcopy(manifests[Path(p)]))
    monkeypatch.setattr(stage, "parse_scene_table", lambda *args: {"scenes": [{"name": "NX_WALKOUT_CANARY_V1"}]})
    return paths, cpks, manifests


def test_detached_inputs_require_exact_pins_and_payload_closure(detached):
    paths, _, _ = detached
    result = stage.combined_inputs(*paths)
    assert len(result["walkout_payloads"]) == 50
    assert len(result["trophy_payloads"]) == 28
    assert not (result["walkout_payloads"].keys() & result["trophy_payloads"].keys())


@pytest.mark.parametrize("change", ["archive", "payload", "manifest", "provenance", "scene"])
def test_detached_unknown_or_corrupt_source_rejected(detached, monkeypatch, change):
    paths, cpks, manifests = detached
    report = json.loads(paths[0].read_text())
    cpk = cpks[paths[0].parent / "update/LooseCpk/dt220_mobile_all.cpk"]
    if change == "archive":
        cpk.path.write_bytes(cpk.path.read_bytes() + b"unknown")
    elif change == "payload":
        report["payloads"][0]["sha256"] = "0" * 64
    elif change == "manifest":
        manifests[cpk.path.parent.parent]["files"][0]["size"] += 1
    elif change == "provenance":
        report["baseline_manifest_sha256"] = "0" * 64
    else:
        monkeypatch.setattr(stage, "parse_scene_table", lambda *a: {"scenes": [{"name": "ENT_MOBILE_CMN"}]})
    paths[0].write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        stage.combined_inputs(*paths)


def test_combined_validator_does_not_accept_rehashed_entrance_regression(detached):
    paths, cpks, manifests = detached
    inputs = stage.combined_inputs(*paths)
    base = inputs["walkout"]
    rows = {name: base.read(name) for name in base.index}
    rows[stage.TABLE] = inputs["trophy_payloads"][stage.TABLE]
    rows.update({name: inputs["trophy_payloads"][name]
                 for name in sorted(set(inputs["trophy_payloads"]) - set(rows))})
    final = Archive(paths[0].parent.parent / "combined/update/LooseCpk/dt220_mobile_all.cpk", rows)
    cpks[final.path] = final
    expected = copy.deepcopy(inputs["baseline"])
    expected["files"][0].update(size=final.path.stat().st_size, sha256=stage.file_digest(final.path))
    manifests[final.path.parent.parent] = expected
    report_path = final.path.parent.parent.parent / "combined-report.json"
    report = {"schema": stage.COMBINED_SCHEMA, "status": "asset_only_not_playable",
              "walkout_report": str(paths[0]), "trophy_report": str(paths[1]),
              "validation": {"candidate_sha256": stage.file_digest(final.path), "size": final.path.stat().st_size}}
    report_path.write_text(json.dumps(report))
    result = stage.check_combined(report_path)
    assert result["working_walkout_preserved"] and result["walkout_payloads_identical"] == 50
    raw = bytearray(final.path.read_bytes())
    raw[0] ^= 1
    final.path.write_bytes(raw)
    report["validation"]["candidate_sha256"] = stage.file_digest(final.path)
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="unrelated stored CPK member changed"):
        stage.check_combined(report_path)


def test_merge_cli_requires_both_reports_and_cannot_mix_donor_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["stage", "--walkout-report", "walkout", "--trophy-report", "trophy", "--output", "out"])
    calls = []
    monkeypatch.setattr(stage, "merge_walkout_trophy", lambda *a: calls.append(a) or {
        "status": "asset_only_not_playable", "validation": {}, "composition_checks": {"working_walkout_preserved": True}})
    stage.main()
    assert calls == [(Path("walkout"), Path("trophy"), Path("out"))]
    assert json.loads(capsys.readouterr().out)["composition_checks"]["working_walkout_preserved"]
    for extra in (["--walkout-report", "walkout"], ["--walkout-report", "walkout", "--trophy-report", "trophy", "--fl26-root", "donor"]):
        monkeypatch.setattr(sys, "argv", ["stage", "--output", "out", *extra])
        with pytest.raises(SystemExit) as error:
            stage.main()
        assert error.value.code == 2
