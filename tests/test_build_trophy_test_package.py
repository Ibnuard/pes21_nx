"""Synthetic installation and corruption checks; no game payload required."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_trophy_test_package as package
from prepare_loose_cpk import FULL_NAMES, PATCH_OBB, write_manifest


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def test_marker_is_exact_and_length_delimited():
    hashes = ("1" * 64, "2" * 64, "3" * 64)
    assert package.marker_bytes(*hashes) == (
        "PESNX_TROPHY_CANARY_V1\ncpk_sha256=" + hashes[0] +
        "\nmanifest_sha256=" + hashes[1] + "\npak_sha256=" + hashes[2] + "\n").encode()


@pytest.mark.parametrize("invalid", ["A" * 64, "0" * 64, "a" * 63, "a" * 65, "a" * 64 + "\n"])
def test_invalid_marker_hash_rejected(invalid):
    with pytest.raises(ValueError, match="SHA-256"):
        package.marker_bytes("1" * 64, invalid, "2" * 64)


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(package, "ROOT", tmp_path)
    root = tmp_path / "baseline"
    manifest = {"version": 2, "build_id": "e861c583ec78e9ae",
                "parent_obb_bytes": 5, "parent_obb_sha256": sha(b"dummy"), "files": []}
    save(root / PATCH_OBB, b"dummy")
    for name in FULL_NAMES:
        raw = ("owned synthetic CPK " + name).encode()
        save(root / "LooseCpk" / name, raw)
        manifest["files"].append({"name": name, "size": len(raw), "sha256": sha(raw)})
    write_manifest(root, manifest)
    native_sha = package.digest(root / package.CPK)
    monkeypatch.setattr(package.trophy, "BASELINE_DT220_SHA256", native_sha)
    monkeypatch.setattr(package, "checked_cpk", lambda _: None)
    monkeypatch.setattr(package, "checked_dummy_obb", lambda _: None)
    monkeypatch.setattr(package, "Cpk", lambda _: type("FakeCpk", (), {"read": lambda *a: b"native"})())
    monkeypatch.setattr(package, "parse_scene_table", lambda *a: {"scenes": [{"name": "ENT_MOBILE_CMN"}]})
    old_nro = save(root / "pes21_nx.nro", b"synthetic accepted NRO")
    monkeypatch.setattr(package, "ACCEPTED_NRO_SHA256", package.digest(old_nro))
    build_root = tmp_path / "build"
    new_nro = save(build_root / "pes21_nx.nro", b"synthetic integrated NRO")
    monkeypatch.setattr(package, "inspect_build", lambda *a: {**package.measured(new_nro),
                                                            "elf_load_segments_match": True})
    trophy_report = save(tmp_path / "trophy/trophy-report.json", b"{}")
    new_cpk = save(trophy_report.parent / "update" / package.CPK, b"synthetic trophy CPK")
    monkeypatch.setattr(package.audit, "check_trophy", lambda _: {
        "dt220_sha256": package.digest(new_cpk), "native_entrance_preserved": True})
    prop_pak = save(tmp_path / "cook/props.pak", b"synthetic cooked props")
    package_report = save(tmp_path / "cook/package.local.json", json.dumps({
        "schema": "PESNX_CINEMATIC_PROP_PACKAGE_V1", "package": str(prop_pak)}).encode())
    monkeypatch.setattr(package.audit, "check_package", lambda *a: {"pak_sha256": package.digest(prop_pak)})
    args = dict(build_root=build_root, baseline_nro=old_nro, baseline_root=root,
                baseline_manifest=root / package.MANIFEST, baseline_cpk_roots=(),
                trophy_report=trophy_report, package_report=package_report,
                cooked_audit=Path("unused"), repak=Path("unused"), unrealpak=Path("unused"),
                output=tmp_path / "local-debug/canary", entrance_policy="native")
    return args, root, manifest


def test_package_retains_native_intro_latest_rows_and_copies_no_obb_or_saves(case):
    args, root, manifest = case
    before = {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()}
    result = package.build_package(**args)
    output = args["output"]
    proof = result["verification"]
    assert not proof["hardware_tested"] and not proof["production_ready"]
    assert not proof["active_runtime_modified"] and not proof["obb_copied"]
    assert proof["native_entrance_preserved"]
    assert set(proof["installed_files"]) == set(package.TARGETS)
    assert {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()} == {
        "update/" + name for name in package.TARGETS} | {"INSTALL.txt", "Apply-Update.ps1", "VERIFICATION.json"}
    merged = package.read_manifest(output / "update")
    for before_row, after_row in zip(manifest["files"], merged["files"]):
        if before_row["name"] != Path(package.CPK).name:
            assert after_row == before_row
    assert {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()} == before
    with pytest.raises(ValueError, match="fresh"):
        package.build_package(**args)


def test_explicit_overlay_preserves_physique_update_without_copying_full_runtime(case):
    args, root, manifest = case
    overlay = root.parent / "physique/LooseCpk"
    changed = save(overlay / "dt200_mobile_all.cpk", b"updated physique")
    current = copy.deepcopy(manifest)
    row = next(r for r in current["files"] if r["name"] == changed.name)
    row.update(size=changed.stat().st_size, sha256=package.digest(changed))
    write_manifest(overlay.parent, current)
    args.update(baseline_manifest=overlay / "manifest.txt", baseline_cpk_roots=(overlay,))
    result = package.build_package(**args)
    assert result["verification"]["baseline"]["cpk_files"] == current["files"]
    candidate = package.read_manifest(args["output"] / "update")
    assert next(r for r in candidate["files"] if r["name"] == changed.name) == row


def test_corrupt_overlay_cannot_fall_back_to_original(case):
    args, root, _ = case
    overlay = root.parent / "overlay"
    save(overlay / "dt200_mobile_all.cpk", b"unexpected")
    args["baseline_cpk_roots"] = (overlay,)
    with pytest.raises(ValueError, match="baseline CPK differs"):
        package.build_package(**args)
    assert not args["output"].exists()


def test_alternate_entrance_is_rejected_even_with_self_consistent_manifest(case, monkeypatch):
    args, root, manifest = case
    save(root / package.CPK, b"FL26 walkout or another cinematic edit")
    row = next(r for r in manifest["files"] if r["name"] == Path(package.CPK).name)
    row.update(size=(root / package.CPK).stat().st_size, sha256=package.digest(root / package.CPK))
    write_manifest(root, manifest)
    with pytest.raises(ValueError, match="explicit merge"):
        package.build_package(**args)
    assert not args["output"].exists()


def test_current_runtime_output_and_wrong_accepted_nro_are_rejected(case):
    args, root, _ = case
    requested = dict(args, output=root)
    with pytest.raises(ValueError, match="local-debug"):
        package.build_package(**requested)
    with pytest.raises(ValueError, match="local-debug"):
        package.build_package(**dict(args, output=args["output"].parent))
    args["baseline_nro"].write_bytes(b"unaccepted NRO")
    with pytest.raises(ValueError, match="accepted v48"):
        package.build_package(**args)


def test_failing_asset_audit_emits_no_installable_package(case, monkeypatch):
    args, _, _ = case

    def failed(*args):
        raise ValueError("synthetic props corruption")

    monkeypatch.setattr(package.audit, "check_package", failed)
    with pytest.raises(ValueError, match="props corruption"):
        package.build_package(**args)
    assert not args["output"].exists() and not args["output"].with_suffix(".zip").exists()
    assert not list(args["output"].parent.iterdir())


def test_output_created_during_validation_is_preserved(case, monkeypatch):
    args, _, _ = case
    original = package.audit.check_package

    def concurrent_output(*params):
        save(args["output"] / "another-job.txt", b"preserve this directory")
        return original(*params)

    monkeypatch.setattr(package.audit, "check_package", concurrent_output)
    with pytest.raises(ValueError, match="output appeared"):
        package.build_package(**args)
    assert list(args["output"].iterdir()) == [args["output"] / "another-job.txt"]
    assert not args["output"].with_suffix(".zip").exists()


def test_integrated_nro_requires_capability_pair_and_matching_elf(tmp_path, monkeypatch):
    raw = bytearray(0x300)
    raw[16:20] = b"NRO0"
    raw[0x80:0x80 + len(package.CAPABILITY)] = package.CAPABILITY
    pair = "e861c583ec78e9ae"
    raw[0xc0:0xc0 + len(pair)] = pair.encode()
    for i in range(3):
        struct.pack_into("<II", raw, 0x20 + i * 8, i * 0x100, 0x100)
    save(tmp_path / "pes21_nx.nro", raw)
    save(tmp_path / "pes21_nx.elf", b"synthetic ELF decoder injected explicitly")

    class Segment(dict):
        def data(self):
            return bytes(raw[self["p_vaddr"]:self["p_vaddr"] + self["p_filesz"]])

    class Elf:
        def __init__(self, _):
            pass

        def iter_segments(self):
            return [Segment(p_type="PT_LOAD", p_vaddr=i * 0x100, p_filesz=0x100) for i in range(3)]

    monkeypatch.setattr(package, "ELFFile", Elf)
    assert package.inspect_build(tmp_path, pair)["elf_load_segments_match"]
    with pytest.raises(ValueError, match="CPK/PAK"):
        package.inspect_build(tmp_path, pair, ("f" * 64,))
    with pytest.raises(ValueError, match="pair"):
        package.inspect_build(tmp_path, "1111111111111111")
    data = bytearray(raw)
    data[-1] = 1
    (tmp_path / "pes21_nx.nro").write_bytes(data)
    with pytest.raises(ValueError, match="differs from linked"):
        package.inspect_build(tmp_path, pair)
    (tmp_path / "pes21_nx.nro").write_bytes(b"not a trophy-enabled NRO")
    with pytest.raises(ValueError, match="integrated"):
        package.inspect_build(tmp_path, pair)


@pytest.fixture
def install_case(case):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is unavailable; installer integration requires it")
    args, root, _ = case
    package.build_package(**args)
    save(root / "SaveData/do-not-change.bin", b"user save")
    (root / "PesMobile/Content/Paks").mkdir(parents=True)
    backup_root = root.parent / "rollback"

    def run(*extra, runtime=None, backup=None):
        return subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(args["output"] / "Apply-Update.ps1"), "-RuntimeRoot", str(runtime or root),
                               "-BackupRoot", str(backup or backup_root), *map(str, extra)],
                              capture_output=True, text=True, timeout=60)

    def snapshot():
        return {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()}

    return args, root, backup_root, run, snapshot


def test_installer_preflight_apply_and_exact_rollback_preserve_save(install_case):
    args, root, backup_root, run, snapshot = install_case
    before = snapshot()
    result = run("-CheckOnly")
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before and not backup_root.exists()
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    saved = next(backup_root.iterdir())
    after = snapshot()
    assert after["SaveData/do-not-change.bin"] == before["SaveData/do-not-change.bin"]
    assert after[PATCH_OBB] == before[PATCH_OBB]
    assert set(after) - set(before) == {package.PAK, package.MARKER}
    result = run("-RollbackDirectory", saved, "-CheckOnly")
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == after
    result = run("-RollbackDirectory", saved)
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before


@pytest.mark.parametrize("corrupt", ["baseline", "package", "unrelated_cpk", "unknown_pak", "stale_marker"])
def test_installer_refuses_conflicts_before_creating_backup_or_mutating(install_case, corrupt):
    args, root, backup_root, run, snapshot = install_case
    if corrupt == "baseline":
        (root / package.MANIFEST).write_bytes(b"wrong manifest")
    elif corrupt == "package":
        (args["output"] / "update" / package.CPK).write_bytes(b"bad archive")
    elif corrupt == "unrelated_cpk":
        (root / "LooseCpk/dt200_mobile_all.cpk").write_bytes(b"bad physique")
    elif corrupt == "unknown_pak":
        save(root / package.PAK, b"other unpublished props")
    else:
        save(root / package.MARKER, b"old active trophy package")
    before = snapshot()
    result = run()
    assert result.returncode != 0
    assert snapshot() == before and not backup_root.exists()


def test_rollback_does_not_overwrite_a_later_update(install_case):
    _, root, backup_root, run, snapshot = install_case
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    saved = next(backup_root.iterdir())
    (root / "pes21_nx.nro").write_bytes(b"next user update")
    before = snapshot()
    result = run("-RollbackDirectory", saved)
    assert result.returncode != 0 and snapshot() == before


def test_existing_identical_prop_pak_survives_rollback(install_case):
    args, root, backup_root, run, snapshot = install_case
    shutil.copy2(args["output"] / "update" / package.PAK, root / package.PAK)
    before = snapshot()
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    result = run("-RollbackDirectory", next(backup_root.iterdir()))
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before


def test_rollback_accepts_only_known_mixed_state_after_interruption(install_case):
    args, root, backup_root, run, snapshot = install_case
    before = snapshot()
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    saved = next(backup_root.iterdir())
    # Simulate an interruption before the new CPK/manifest and marker were copied.
    for name in (package.CPK, package.MANIFEST):
        shutil.copy2(saved / name, root / name)
    (root / package.MARKER).unlink()
    result = run("-RollbackDirectory", saved)
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before


def test_installer_never_accepts_save_as_a_target(install_case):
    args, root, backup_root, run, snapshot = install_case
    proof_path = args["output"] / "VERIFICATION.json"
    proof = json.loads(proof_path.read_text())
    proof["installed_files"]["SaveData/do-not-change.bin"] = package.measured(root / "SaveData/do-not-change.bin")
    proof_path.write_text(json.dumps(proof))
    before = snapshot()
    result = run()
    assert result.returncode != 0 and snapshot() == before and not backup_root.exists()


def test_runtime_trailing_slash_works_but_drive_root_is_rejected(install_case):
    _, root, backup_root, run, snapshot = install_case
    before = snapshot()
    result = run("-CheckOnly", runtime=str(root) + os.sep)
    assert result.returncode == 0, result.stdout + result.stderr
    result = run("-CheckOnly", runtime=root.anchor)
    assert result.returncode != 0 and "drive/share root" in result.stdout + result.stderr
    assert snapshot() == before and not backup_root.exists()


def test_backup_junction_or_symlink_rejected_even_in_preflight(install_case):
    args, root, backup_root, run, snapshot = install_case
    destination = root.parent / "actual-backup"
    destination.mkdir()
    if os.name == "nt":
        shell = shutil.which("pwsh") or shutil.which("powershell")
        quoted = lambda p: "'" + str(p).replace("'", "''") + "'"
        command = ("New-Item -ItemType Junction -Path " + quoted(backup_root) +
                   " -Target " + quoted(destination) + " | Out-Null")
        created = subprocess.run([shell, "-NoProfile", "-Command", command],
                                 capture_output=True, text=True, timeout=60)
        assert created.returncode == 0, created.stdout + created.stderr
    else:
        backup_root.symlink_to(destination, target_is_directory=True)
    before = snapshot()
    result = run("-CheckOnly", backup=backup_root / "new-child")
    assert result.returncode != 0 and "reparse point" in result.stdout + result.stderr
    assert snapshot() == before and not list(destination.iterdir())


@pytest.fixture
def combined_case(case, monkeypatch):
    args, root, manifest = case
    upgrade = root.parent / "delivered-v49"
    update = upgrade / "update"
    save(update / "pes21_nx.nro", b"known delivered v49 integrated NRO")
    save(update / package.CPK, (args["trophy_report"].parent / "update" / package.CPK).read_bytes())
    prop = Path(json.loads(args["package_report"].read_text())["package"])
    save(update / package.PAK, prop.read_bytes())
    write_manifest(update, package.with_cinematic_row(manifest, package.measured(update / package.CPK)))
    save(update / package.MARKER, package.marker_bytes(
        package.digest(update / package.CPK), package.digest(update / package.MANIFEST), package.digest(update / package.PAK)))
    files = {name: package.measured(update / name) for name in package.TARGETS}
    save(upgrade / "VERIFICATION.json", json.dumps({"schema": package.SCHEMA, "installed_files": files}).encode())
    save(update / "scene-runtime.log", b"user supplied diagnostic log")
    save(update / "trophy-runtime.log", b"user supplied trophy log")
    monkeypatch.setattr(package, "V49_FILES", copy.deepcopy(files))
    walkout_report = save(root.parent / "walkout/walkout-report.json", b"{}")
    walkout = save(walkout_report.parent / "update" / package.CPK, b"known reduced walking-in intro CPK")
    monkeypatch.setattr(package.trophy, "WALKOUT_DT220_SHA256", package.digest(walkout))
    combined_report = save(root.parent / "combined/combined-report.json",
                           json.dumps({"walkout_report": str(walkout_report)}).encode())
    combined_cpk = save(combined_report.parent / "update" / package.CPK, b"combined working walkout and trophy CPK")
    monkeypatch.setattr(package.trophy, "check_combined", lambda _: {
        "dt220_sha256": package.digest(combined_cpk), "working_walkout_preserved": True,
        "walkout_payloads_identical": 50, "trophy_payloads_identical": 28})
    monkeypatch.setattr(package, "CURRENT_NATIVE_MANIFEST_SHA256", package.digest(args["baseline_manifest"]))
    args.update(trophy_report=combined_report, entrance_policy="walkout", upgrade_package=upgrade)
    return args, root, manifest, walkout


def test_combined_package_explicitly_preserves_walkout_and_three_exact_baselines(combined_case):
    args, root, manifest, walkout = combined_case
    result = package.build_package(**args)
    proof = result["verification"]
    assert proof["entrance_policy"] == "walkout" and proof["working_walkout_preserved"]
    assert not proof["native_entrance_preserved"]
    states = {row["name"]: row for row in proof["baseline_states"]}
    assert set(states) == {"accepted-v48-native", "accepted-v48-walkout", "delivered-v49"}
    assert states["delivered-v49"]["marker"] == package.V49_FILES[package.MARKER]
    assert states["delivered-v49"]["prop_required"]
    assert states["accepted-v48-walkout"]["nro"]["sha256"] == package.ACCEPTED_NRO_SHA256
    for state in states.values():
        assert {r["name"]: r for r in state["cpk_files"] if r["name"] != walkout.name} == {
            r["name"]: r for r in manifest["files"] if r["name"] != walkout.name}
    assert (args["upgrade_package"] / "update/scene-runtime.log").read_bytes() == b"user supplied diagnostic log"
    assert not (args["output"] / "update/scene-runtime.log").exists()
    assert "walking-in/lineup" in (args["output"] / "INSTALL.txt").read_text()


def test_combined_known_manifest_required_and_native_upgrade_cannot_regress_intro(combined_case, monkeypatch):
    args, root, _, _ = combined_case
    with pytest.raises(ValueError, match="walkout entrance policy"):
        package.build_package(**dict(args, entrance_policy="native"))
    monkeypatch.setattr(package, "CURRENT_NATIVE_MANIFEST_SHA256", "f" * 64)
    with pytest.raises(ValueError, match="known current native manifest"):
        package.build_package(**args)
    assert not args["output"].exists()


@pytest.mark.parametrize("corruption", ["target", "relabelled", "unrelated_manifest", "marker"])
def test_upgrade_rejects_unknown_package_even_with_self_consistent_proof(combined_case, corruption, monkeypatch):
    args, root, manifest, _ = combined_case
    old = args["upgrade_package"]
    if corruption in ("target", "relabelled"):
        (old / "update/pes21_nx.nro").write_bytes(b"unknown NRO with a plausible proof")
        if corruption == "relabelled":
            proof = json.loads((old / "VERIFICATION.json").read_text())
            proof["installed_files"]["pes21_nx.nro"] = package.measured(old / "update/pes21_nx.nro")
            (old / "VERIFICATION.json").write_text(json.dumps(proof))
    elif corruption == "unrelated_manifest":
        # Even explicitly pinned synthetic files must match the selected current
        # non-cinematic rows. A proof cannot authorize silently changing physique.
        changed = package.read_manifest(old / "update")
        changed["files"][1]["sha256"] = "f" * 64
        write_manifest(old / "update", changed)
        package.V49_FILES[package.MANIFEST] = package.measured(old / "update" / package.MANIFEST)
        (old / "VERIFICATION.json").write_text(json.dumps({"schema": package.SCHEMA, "installed_files": package.V49_FILES}))
    else:
        (old / "update" / package.MARKER).write_bytes(b"relabelled but wrong marker")
        package.V49_FILES[package.MARKER] = package.measured(old / "update" / package.MARKER)
        (old / "VERIFICATION.json").write_text(json.dumps({"schema": package.SCHEMA, "installed_files": package.V49_FILES}))
    with pytest.raises(ValueError):
        package.verified_upgrade(old, manifest)


@pytest.fixture
def combined_install_case(combined_case):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is unavailable; installer integration requires it")
    args, root, manifest, walkout = combined_case
    package.build_package(**args)
    save(root / "SaveData/do-not-change.bin", b"user save")
    save(root / "scene-runtime.log", b"keep existing runtime diagnostic")
    (root / "PesMobile/Content/Paks").mkdir(parents=True)
    backup_root = root.parent / "rollback"

    def run(*extra):
        return subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                               str(args["output"] / "Apply-Update.ps1"), "-RuntimeRoot", str(root),
                               "-BackupRoot", str(backup_root), *map(str, extra)],
                              capture_output=True, text=True, timeout=60)

    def snapshot():
        return {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()}

    return args, root, manifest, walkout, backup_root, run, snapshot


@pytest.mark.parametrize("installed", ["native", "walkout", "v49"])
def test_combined_installer_upgrades_each_known_state_and_rolls_back_exactly(combined_install_case, installed):
    args, root, manifest, walkout, backup_root, run, snapshot = combined_install_case
    if installed == "walkout":
        shutil.copyfile(walkout, root / package.CPK)
        write_manifest(root, package.with_cinematic_row(manifest, package.measured(walkout)))
    elif installed == "v49":
        for name in package.TARGETS:
            shutil.copyfile(args["upgrade_package"] / "update" / name, root / name)
    before = snapshot()
    result = run("-CheckOnly")
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before and not backup_root.exists()
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    after = snapshot()
    assert after["SaveData/do-not-change.bin"] == before["SaveData/do-not-change.bin"]
    assert after["scene-runtime.log"] == before["scene-runtime.log"]
    for name in package.TARGETS:
        assert after[name] == package.digest(args["output"] / "update" / name)
    result = run("-RollbackDirectory", next(backup_root.iterdir()))
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before


@pytest.mark.parametrize("broken", [package.MARKER, package.PAK, package.CPK, "pes21_nx.nro"])
def test_combined_installer_rejects_mixed_v49_state_without_writes(combined_install_case, broken):
    args, root, manifest, walkout, backup_root, run, snapshot = combined_install_case
    for name in package.TARGETS:
        shutil.copyfile(args["upgrade_package"] / "update" / name, root / name)
    (root / broken).write_bytes(b"interrupted or unknown asset")
    before = snapshot()
    result = run()
    assert result.returncode != 0, result.stdout + result.stderr
    assert snapshot() == before and not backup_root.exists()


def test_installed_candidate_verify_and_idempotent_noop_are_read_only(combined_install_case):
    args, root, _, _, backup_root, run, snapshot = combined_install_case
    # Reproduce the supported ready-to-copy user flow, without invoking installer.
    for name in package.TARGETS:
        shutil.copyfile(args["output"] / "update" / name, root / name)
    save(root / "trophy-runtime.log", b"stale v49 journal cannot identify the loaded NRO")
    before = snapshot()
    for extra in (("-VerifyInstalled",), ("-CheckOnly",), ()):
        result = run(*extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Installed candidate verified" in result.stdout
        assert package.digest(root / "pes21_nx.nro") in result.stdout
        if extra != ("-VerifyInstalled",):
            assert "Already installed; no-op" in result.stdout
        assert snapshot() == before and not backup_root.exists()


def test_verify_installed_reports_all_missing_and_mismatched_targets(combined_install_case):
    args, root, _, _, backup_root, run, snapshot = combined_install_case
    for name in package.TARGETS:
        shutil.copyfile(args["output"] / "update" / name, root / name)
    (root / package.MARKER).unlink()
    (root / "pes21_nx.nro").write_bytes(b"a different NRO, independently of the log")
    (root / package.CPK).write_bytes(b"changed CPK")
    (root / package.PAK).write_bytes(b"changed PAK")
    (root / package.MANIFEST).write_bytes(b"changed manifest")
    save(root / "trophy-runtime.log", b"preserve old log")
    before = snapshot()
    result = run("-VerifyInstalled")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "MISSING trophy-canary.txt" in result.stdout
    for name in package.TARGETS[:-1]:
        assert "MISMATCH " + name + " expected_bytes=" in result.stdout
    assert "actual_sha256=" + package.digest(root / "pes21_nx.nro") in result.stdout
    assert "verification FAILED" in result.stdout
    assert snapshot() == before and not backup_root.exists()


@pytest.mark.parametrize("fault", ["other_cpk", "missing_other_cpk", "obb", "extra_pak"])
def test_five_matching_targets_do_not_hide_incomplete_runtime(combined_install_case, fault):
    args, root, _, _, backup_root, run, snapshot = combined_install_case
    for name in package.TARGETS:
        shutil.copyfile(args["output"] / "update" / name, root / name)
    if fault == "other_cpk":
        affected = "LooseCpk/dt200_mobile_all.cpk"
        (root / affected).write_bytes(b"incorrect physique")
    elif fault == "missing_other_cpk":
        affected = "LooseCpk/dt200_mobile_all.cpk"
        (root / affected).unlink()
    elif fault == "obb":
        affected = PATCH_OBB
        (root / affected).write_bytes(b"wrong dummy OBB")
    else:
        affected = "PesMobile/Content/Paks/Other-CinematicProps.pak"
        save(root / affected, b"conflicting cooked props")
    before = snapshot()
    for extra in (("-VerifyInstalled",), ()):
        result = run(*extra)
        assert result.returncode == 1, result.stdout + result.stderr
        assert affected in result.stdout
        assert snapshot() == before and not backup_root.exists()


def test_installed_read_only_mode_cannot_trigger_rollback_or_install_flags(combined_install_case):
    args, root, _, _, backup_root, run, snapshot = combined_install_case
    before = snapshot()
    for extra in (("-VerifyInstalled", "-CheckOnly"), ("-VerifyInstalled", "-RollbackDirectory", "unused")):
        result = run(*extra)
        assert result.returncode != 0
        assert "separate read-only mode" in result.stderr
        assert snapshot() == before and not backup_root.exists()


@pytest.fixture
def next_case(combined_case, monkeypatch):
    args, root, manifest, walkout = combined_case
    delivered = package.build_package(**args)
    v50_root = args["output"]
    monkeypatch.setattr(package, "V50_FILES", copy.deepcopy(delivered["verification"]["installed_files"]))
    save(v50_root / "update/scene-runtime.log", b"new user diagnostic")
    save(v50_root / "update/trophy-runtime.log", b"old byte-identical journal")
    args["output"] = v50_root.parent / "next-v51"
    args["upgrade_packages"] = (v50_root,)
    (args["build_root"] / "pes21_nx.nro").write_bytes(b"next candidate NRO")
    return args, root, manifest, v50_root


def test_next_package_retains_both_pinned_delivered_upgrade_states_without_changing_v50(next_case):
    args, root, manifest, v50_root = next_case
    before = {p.relative_to(v50_root).as_posix(): package.digest(p) for p in v50_root.rglob("*") if p.is_file()}
    result = package.build_package(**args)
    states = {row["name"]: row for row in result["verification"]["baseline_states"]}
    assert set(states) == {"accepted-v48-native", "accepted-v48-walkout", "delivered-v49", "delivered-v50"}
    assert states["delivered-v50"]["nro"] == package.V50_FILES["pes21_nx.nro"]
    assert states["delivered-v50"]["entrance"] == "walkout"
    assert states["delivered-v50"]["nro"] != result["verification"]["installed_files"]["pes21_nx.nro"]
    assert {p.relative_to(v50_root).as_posix(): package.digest(p) for p in v50_root.rglob("*") if p.is_file()} == before
    assert not (args["output"] / "update/trophy-runtime.log").exists()
    instructions = (args["output"] / "INSTALL.txt").read_text()
    assert "folder siap copy" in instructions and "salin SEMUA isinya" in instructions
    assert "OPSIONAL" in instructions and "-VerifyInstalled" in instructions
    assert "Do not bypass" not in instructions


def test_next_installer_upgrades_and_rolls_back_exact_v50_with_logs_preserved(next_case):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is unavailable; installer integration requires it")
    args, root, manifest, v50_root = next_case
    package.build_package(**args)
    for name in package.TARGETS:
        save(root / name, (v50_root / "update" / name).read_bytes())
    save(root / "SaveData/user.bin", b"keep save")
    save(root / "trophy-runtime.log", b"keep stale log")
    before = {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()}
    backup = root.parent / "rollback-v51"
    command = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(args["output"] / "Apply-Update.ps1"), "-RuntimeRoot", str(root), "-BackupRoot", str(backup)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run(command + ["-VerifyInstalled"], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Installed candidate verified" in result.stdout
    result = subprocess.run(command + ["-RollbackDirectory", str(next(backup.iterdir()))],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()} == before


def test_self_relabelled_v50_and_duplicate_upgrade_proofs_cannot_authorize_unknown_identity(next_case):
    args, root, manifest, v50_root = next_case
    with pytest.raises(ValueError, match="duplicate delivered"):
        package.build_package(**dict(args, upgrade_packages=(v50_root, v50_root)))
    (v50_root / "update/pes21_nx.nro").write_bytes(b"unrecognized relabelled NRO")
    proof = json.loads((v50_root / "VERIFICATION.json").read_text())
    proof["installed_files"]["pes21_nx.nro"] = package.measured(v50_root / "update/pes21_nx.nro")
    (v50_root / "VERIFICATION.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="known delivered"):
        package.verified_upgrade(v50_root, manifest)


def test_cli_accepts_repeatable_known_upgrade_packages(monkeypatch, capsys):
    argv = ["build_trophy_test_package.py", "--entrance-policy", "walkout"]
    for name in ("build-root", "baseline-nro", "baseline-root", "baseline-manifest", "trophy-report",
                 "package-report", "cooked-audit", "repak", "unrealpak", "output"):
        argv += ["--" + name, name]
    argv += ["--upgrade-package", "delivered-v49", "--upgrade-package", "delivered-v50",
             "--upgrade-package", "delivered-v51", "--sd-copy-output", "sd-copy"]
    monkeypatch.setattr(sys, "argv", argv)
    received = []
    monkeypatch.setattr(package, "build_package", lambda **kw: received.append(kw) or {"test": True})
    package.main()
    assert received[0]["upgrade_packages"] == (Path("delivered-v49"), Path("delivered-v50"), Path("delivered-v51"))
    assert received[0]["entrance_policy"] == "walkout"
    assert received[0]["sd_copy_output"] == Path("sd-copy")


def test_sd_copy_exact_layout_hashes_zip_and_device_instructions(case):
    args, root, _ = case
    destination = args["output"].parent / "SD-ready"
    result = package.build_package(**dict(args, sd_copy_output=destination))
    proof = result["verification"]
    expected = {"switch/pes21_nx/" + name for name in package.TARGETS} | {"BACA-DULU.txt"}
    assert {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()} == expected
    for name in package.TARGETS:
        assert package.measured(destination / "switch/pes21_nx" / name) == proof["installed_files"][name]
    note = (destination / "BACA-DULU.txt").read_text()
    assert "ROOT kartu SD" in note and "sdmc:/switch/pes21_nx/pes21_nx.nro" in note
    assert "MU vs Barca" in note and "final Custom Cup" in note and "masih menunggu" in note
    sd = result["sd_copy"]
    assert sd["zip_crc_verified"] and sd["zip_payload_hashes_verified"] and not sd["hardware_tested"]
    assert Path(sd["zip"]) == destination.with_name(destination.name + ".zip")
    assert package.measured(Path(sd["zip"])) == {key: sd[key] for key in ("bytes", "sha256")}
    with package.zipfile.ZipFile(sd["zip"]) as zipped:
        assert set(zipped.namelist()) == expected and zipped.testzip() is None
        for name in expected:
            assert zipped.read(name) == (destination / name).read_bytes()
    # Canonical package and its optional installer retain their original layout.
    assert (args["output"] / "Apply-Update.ps1").read_text() == package.INSTALLER
    assert not (args["output"] / "switch").exists()


@pytest.mark.parametrize("name", package.TARGETS)
def test_sd_copy_refuses_each_corrupted_source_payload_without_output(case, name):
    args, root, _ = case
    package.build_package(**args)
    save(args["output"] / "update/user.log", b"preserve diagnostic")
    (args["output"] / "update" / name).write_bytes(b"changed payload")
    before = {p.relative_to(args["output"]).as_posix(): package.digest(p)
              for p in args["output"].rglob("*") if p.is_file()}
    destination = args["output"].parent / "SD-ready"
    with pytest.raises(ValueError, match="canonical payload changed"):
        package.stage_sd_copy(args["output"], destination)
    assert not destination.exists() and not destination.with_name(destination.name + ".zip").exists()
    assert {p.relative_to(args["output"]).as_posix(): package.digest(p)
            for p in args["output"].rglob("*") if p.is_file()} == before


def test_sd_copy_existing_outputs_and_unsafe_paths_are_preserved_before_build(case):
    args, root, _ = case
    base = args["output"].parent
    existing = save(base / "SD-existing/user.txt", b"preserve existing output").parent
    zip_destination = base / "SD-zip-exists"
    prior_zip = save(zip_destination.with_name(zip_destination.name + ".zip"), b"preserve existing zip")
    for destination in (existing, zip_destination, root / "outside-local-debug", base,
                        args["output"], args["output"].with_suffix(".zip"), args["output"] / "nested-SD"):
        with pytest.raises(ValueError, match="fresh|separate"):
            package.build_package(**dict(args, sd_copy_output=destination))
    assert (existing / "user.txt").read_bytes() == b"preserve existing output"
    assert prior_zip.read_bytes() == b"preserve existing zip"
    assert not args["output"].exists()


def test_sd_copy_ignores_logs_saves_and_other_package_extras(case):
    args, root, _ = case
    package.build_package(**args)
    for name in ("scene-runtime.log", "trophy-runtime.log", "SaveData/user.bin", PATCH_OBB):
        save(args["output"] / "update" / name, b"not an SD update target")
    before = {p.relative_to(args["output"]).as_posix(): package.digest(p)
              for p in args["output"].rglob("*") if p.is_file()}
    destination = args["output"].parent / "SD-ready"
    package.stage_sd_copy(args["output"], destination)
    assert len([p for p in destination.rglob("*") if p.is_file()]) == len(package.TARGETS) + 1
    assert {p.relative_to(args["output"]).as_posix(): package.digest(p)
            for p in args["output"].rglob("*") if p.is_file()} == before


def test_sd_copy_detects_zip_payload_damage_even_with_valid_crc(case, monkeypatch):
    args, root, _ = case
    package.build_package(**args)
    zip_type = package.zipfile.ZipFile

    class AlteredZip(zip_type):
        def write(self, filename, arcname=None, *a, **kw):
            if arcname == "switch/pes21_nx/pes21_nx.nro":
                self.writestr(arcname, b"valid CRC but different NRO payload")
            else:
                super().write(filename, arcname, *a, **kw)

    monkeypatch.setattr(package.zipfile, "ZipFile", AlteredZip)
    destination = args["output"].parent / "SD-ready"
    with pytest.raises(ValueError, match="ZIP payload hash differs"):
        package.stage_sd_copy(args["output"], destination)
    assert not destination.exists() and not destination.with_name(destination.name + ".zip").exists()


def test_sd_copy_never_replaces_output_created_during_validation(case, monkeypatch):
    args, root, _ = case
    package.build_package(**args)
    original = package.zipfile.ZipFile.testzip
    destination = args["output"].parent / "SD-ready"

    def concurrent_output(zipped):
        save(destination / "another-task.txt", b"preserve concurrent work")
        return original(zipped)

    monkeypatch.setattr(package.zipfile.ZipFile, "testzip", concurrent_output)
    with pytest.raises(ValueError, match="appeared during validation"):
        package.stage_sd_copy(args["output"], destination)
    assert (destination / "another-task.txt").read_bytes() == b"preserve concurrent work"
    assert not (destination / "switch").exists()
    assert not destination.with_name(destination.name + ".zip").exists()


@pytest.fixture
def v52_case(next_case, monkeypatch):
    args, root, manifest, v50_root = next_case
    delivered = package.build_package(**args)
    v51_root = args["output"]
    monkeypatch.setattr(package, "V51_FILES", copy.deepcopy(delivered["verification"]["installed_files"]))
    save(v51_root / "update/trophy-runtime.log", b"retained v51 test journal")
    args["output"] = v51_root.parent / "next-v52"
    args["upgrade_packages"] += (v51_root,)
    args["sd_copy_output"] = v51_root.parent / "next-v52-SD"
    (args["build_root"] / "pes21_nx.nro").write_bytes(b"next v52 candidate NRO")
    return args, root, manifest, v51_root


def test_v52_accepts_exact_delivered_v51_and_keeps_ready_copy_delivery(v52_case):
    args, root, manifest, v51_root = v52_case
    before = {p.relative_to(v51_root).as_posix(): package.digest(p) for p in v51_root.rglob("*") if p.is_file()}
    result = package.build_package(**args)
    states = {state["name"]: state for state in result["verification"]["baseline_states"]}
    assert set(states) == {"accepted-v48-native", "accepted-v48-walkout", "delivered-v49", "delivered-v50", "delivered-v51"}
    assert states["delivered-v51"]["nro"] == package.V51_FILES["pes21_nx.nro"]
    assert states["delivered-v51"]["entrance"] == "walkout" and states["delivered-v51"]["prop_required"]
    assert states["delivered-v51"]["marker"] == package.V51_FILES[package.MARKER]
    assert {p.relative_to(v51_root).as_posix(): package.digest(p) for p in v51_root.rglob("*") if p.is_file()} == before
    assert result["sd_copy"]["zip_crc_verified"] and result["sd_copy"]["zip_payload_hashes_verified"]
    copied = args["sd_copy_output"] / "switch/pes21_nx"
    assert {p.relative_to(copied).as_posix() for p in copied.rglob("*") if p.is_file()} == set(package.TARGETS)
    assert not result["verification"]["hardware_tested"]


def test_v51_unknown_nro_cannot_be_authorized_by_relabelling_the_proof(v52_case):
    args, root, manifest, v51_root = v52_case
    (v51_root / "update/pes21_nx.nro").write_bytes(b"unapproved NRO")
    with pytest.raises(ValueError, match="upgrade target changed"):
        package.verified_upgrade(v51_root, manifest)
    proof = json.loads((v51_root / "VERIFICATION.json").read_text())
    proof["installed_files"]["pes21_nx.nro"] = package.measured(v51_root / "update/pes21_nx.nro")
    (v51_root / "VERIFICATION.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="known delivered"):
        package.verified_upgrade(v51_root, manifest)


def test_installer_upgrades_and_rolls_back_exact_delivered_v51(v52_case):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is unavailable; installer integration requires it")
    args, root, manifest, v51_root = v52_case
    package.build_package(**args)
    for name in package.TARGETS:
        save(root / name, (v51_root / "update" / name).read_bytes())
    save(root / "SaveData/user.bin", b"retained save")
    save(root / "trophy-runtime.log", b"retained v51 journal")
    before = {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()}
    backup = root.parent / "rollback-v52"
    command = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(args["output"] / "Apply-Update.ps1"), "-RuntimeRoot", str(root), "-BackupRoot", str(backup)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert package.measured(root / "pes21_nx.nro") != package.V51_FILES["pes21_nx.nro"]
    result = subprocess.run(command + ["-RollbackDirectory", str(next(backup.iterdir()))],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {p.relative_to(root).as_posix(): package.digest(p) for p in root.rglob("*") if p.is_file()} == before
